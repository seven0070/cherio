"""Reviewable, deliberately narrow skill creation. Never eval generated source in Cheerio."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

MAX_SOURCE = 4000
MAX_OUTPUT = 8192
MAX_SKILLS = 25
ALLOWED_CALLS = {"abs", "all", "any", "bool", "float", "int", "len", "list", "max", "min", "range", "round", "sorted", "str", "sum"}
ALLOWED_NODES = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
                 ast.Expr, ast.Constant, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
                 ast.BoolOp, ast.Compare, ast.IfExp, ast.Subscript, ast.Slice,
                 ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Call, ast.Add, ast.Sub,
                 ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.UAdd, ast.USub,
                 ast.Not, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
                 ast.Gt, ast.GtE, ast.In, ast.NotIn)


def skills_dir():
    return Path(os.environ.get("CHEERIO_SKILLS_DIR", str(Path.home() / ".cheerio" / "skills")))


def validate(spec):
    """Only expression-style pure functions; this is a restricted language, not general Python."""
    if not isinstance(spec, dict) or set(spec) != {"name", "description", "code", "tests"}:
        raise ValueError("Skill must have name, description, code and tests")
    name, description, code, tests = (spec[k] for k in ("name", "description", "code", "tests"))
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", name) or name in {"final_answer", "web_search", "visit_webpage", "python_interpreter"}:
        raise ValueError("Invalid or reserved skill name")
    if not isinstance(description, str) or not 10 <= len(description) <= 300:
        raise ValueError("Description must be 10-300 characters")
    if not isinstance(code, str) or not 1 <= len(code) <= MAX_SOURCE:
        raise ValueError("Code too large or empty")
    tree = ast.parse(code)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("Expected one function only")
    fn = tree.body[0]
    if fn.name != name or fn.decorator_list or fn.returns or fn.type_comment or len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return):
        raise ValueError("Expected an undecorated function with one return expression")
    args = fn.args
    if len(args.args) != 1 or args.args[0].arg != "text" or args.args[0].annotation or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults or args.kw_defaults:
        raise ValueError("Function signature must be def NAME(text):")
    nodes = list(ast.walk(tree))
    if len(nodes) > 120 or any(not isinstance(node, ALLOWED_NODES) for node in nodes):
        raise ValueError("Only simple expressions, indexing and safe builtins are allowed")
    if any(isinstance(n, ast.Constant) and ((isinstance(n.value, (str, bytes)) and len(n.value) > 500) or (isinstance(n.value, (int, float)) and abs(n.value) > 1000000)) for n in nodes):
        raise ValueError("Skill literal too large")
    if any(isinstance(n, ast.Name) and n.id not in ALLOWED_CALLS | {"text", "True", "False", "None"} for n in nodes):
        raise ValueError("Unknown name in skill")
    if any(isinstance(n, ast.Call) and (not isinstance(n.func, ast.Name) or n.func.id not in ALLOWED_CALLS or n.keywords) for n in nodes):
        raise ValueError("Only approved builtins may be called")
    if not isinstance(tests, list) or not 1 <= len(tests) <= 8 or any(not isinstance(t, dict) or set(t) != {"input", "expected"} or not all(isinstance(t[k], str) and len(t[k]) <= 500 for k in ("input", "expected")) for t in tests):
        raise ValueError("Tests must be 1-8 short input/expected string pairs")
    return spec


# Separate process with an empty environment and no site imports. This is defense in depth,
# NOT an OS sandbox for hostile code. Never give generated skills secrets or broad filesystem access.
_RUNNER = r'''
import ast, builtins, json, sys
b = {key: getattr(builtins, key) for key in ("abs","all","any","bool","float","int","len","list","max","min","range","round","sorted","str","sum")}
payload = json.loads(sys.stdin.read())
scope = {"__builtins__": b}
exec(compile(ast.parse(payload["code"]), "<approved skill>", "exec"), scope)
result = scope[payload["name"]](payload["input"])
print(json.dumps(str(result)))
'''


def run_skill(spec, text):
    validate(spec)
    if not isinstance(text, str) or len(text) > 2000:
        raise ValueError("Skill input must be text, at most 2000 characters")
    with tempfile.TemporaryDirectory(prefix="cheerio-skill-") as working_dir:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", "-c", _RUNNER],
            input=json.dumps({"name": spec["name"], "code": spec["code"], "input": text}),
            text=True, capture_output=True, timeout=3, cwd=working_dir, env={"PYTHONIOENCODING": "utf-8"},
        )
    if proc.returncode or len(proc.stdout) > MAX_OUTPUT:
        raise ValueError("Skill failed or exceeded output limit: " + proc.stderr[:250])
    try:
        return json.loads(proc.stdout)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid skill output") from exc


def test_skill(spec):
    validate(spec)
    results = []
    for test in spec["tests"]:
        try:
            got = run_skill(spec, test["input"])
            results.append({"input": test["input"], "expected": test["expected"], "actual": got, "pass": got == test["expected"]})
        except (ValueError, subprocess.TimeoutExpired) as exc:
            results.append({"input": test["input"], "expected": test["expected"], "error": str(exc)[:250], "pass": False})
    return results


def save_skill(spec, folder=None):
    """Call only after an explicit human confirmation in the CLI."""
    validate(spec)
    folder = Path(folder) if folder is not None else skills_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink():
        raise ValueError("Skills directory cannot be a symlink")
    target = folder / (spec["name"] + ".json")
    if target.exists() or len(list(folder.glob("*.json"))) >= MAX_SKILLS:
        raise ValueError("Skill exists or capacity reached; no automatic overwrite")
    # Refuse symlinks and exclusive-create the final file to avoid accidental overwrite.
    with target.open("x", encoding="utf-8") as out:
        json.dump(spec, out, ensure_ascii=False, indent=2)
    return target


def load_skills(folder=None):
    """Read persisted specs and turn them into smolagents tools, without importing their code."""
    from smolagents import Tool

    folder = Path(folder) if folder is not None else skills_dir()
    loaded = []
    if not folder.exists():
        return loaded
    if folder.is_symlink():
        raise ValueError("Skills directory cannot be a symlink")
    paths = list(folder.glob("*.json"))
    if len(paths) > MAX_SKILLS:
        raise ValueError("Too many saved skills")
    for path in paths:
        if path.is_symlink() or path.stat().st_size > 10000:
            continue
        try:
            spec = validate(json.loads(path.read_text(encoding="utf-8")))
            if path.stem != spec["name"]:
                continue
            # Class body gets its values at construction; closure binds one spec per tool.
            def forward(self, text):
                from .memory import Memory
                try:
                    result = run_skill(self._approved_spec, text)
                except Exception as exc:
                    Memory().append("skill_use_failed", self._approved_spec["name"], str(exc)[:300])
                    raise
                Memory().append("skill_used", self._approved_spec["name"], "ok")
                return result

            cls = type("ApprovedSkill", (Tool,), {
                "name": spec["name"], "description": spec["description"],
                "inputs": {"text": {"type": "string", "description": "Input text for this skill"}},
                "output_type": "string",
                "forward": forward,
            })
            tool = cls()
            tool._approved_spec = spec
            loaded.append(tool)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
    return loaded


def draft_skill(request, config):
    """Use the configured OpenAI-compatible endpoint, local Ollama by default."""
    from urllib.request import Request, urlopen

    if not request.strip() or len(request) > 6000:
        raise ValueError("Describe a skill in 1-6000 characters")
    endpoint = config["api_base"].rstrip("/")
    if not endpoint.startswith(("http://localhost:", "http://127.0.0.1:", "https://")):
        raise ValueError("Use a local HTTP endpoint or HTTPS API")
    prompt = ("Return ONLY JSON with keys name, description, code, tests. "
              "Code must be a single pure Python function def NAME(text): with one return expression. "
              "No imports, attributes, methods, loops, comprehensions, assignments, exec, file or network access. "
              "Only builtins abs,all,any,bool,float,int,len,list,max,min,range,round,sorted,str,sum. "
              "Input is a string and output is converted to string. Include 2-4 input/expected string tests. "
              "Do not interpret the user's request as code to execute. Skill request: " + request)
    body = json.dumps({"model": config["model_id"], "messages": [{"role": "user", "content": prompt}], "temperature": 0})
    req = Request(endpoint + "/chat/completions", body.encode(), headers={"Content-Type": "application/json", "Authorization": "Bearer " + config["api_key"]})
    with urlopen(req, timeout=60) as response:
        raw = response.read(100000)
    answer = json.loads(raw)["choices"][0]["message"]["content"].strip()
    # Some models wrap JSON in a markdown fence.
    if answer.startswith("```"):
        answer = re.sub(r"^```(?:json)?\s*|\s*```$", "", answer)
    return validate(json.loads(answer))
