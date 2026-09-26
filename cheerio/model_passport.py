"""Opt-in local model exams and transparent routing from measured evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
import time

from .model_discovery import _request, inspect_endpoints, is_local

MAX_MODELS = 20


def passport_path(env=None):
    env = os.environ if env is None else env
    return Path(env.get("CHEERIO_PASSPORT_DB", str(Path.home() / ".cheerio" / "passports.json")))


def read_passports(path=None):
    path = Path(path) if path else passport_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (ValueError, OSError):
        raise ValueError("Passport store is invalid or unreadable") from None
    if not isinstance(data, list):
        raise ValueError("Passport store is invalid")
    return data


def save_passports(passports, path=None):
    path = Path(path) if path else passport_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as out:
            json.dump(passports[:MAX_MODELS], out, indent=2)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _answer(payload):
    choices = payload.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        raise ValueError("No model response")
    message = choices[0].get("message", {})
    return message.get("content") or "", message.get("tool_calls") or []


def _chat(endpoint, model, prompt, *, tools=None):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 80, "temperature": 0, "stream": False}
    if tools:
        body["tools"] = [{"type": "function", "function": {"name": "ping", "description": "Return an acknowledgement", "parameters": {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}}}]
        body["tool_choice"] = "required"
    start = time.monotonic()
    result = _request(endpoint.rstrip("/") + "/chat/completions", data=body, timeout=45)
    return result, round(time.monotonic() - start, 2)


def examine(endpoint, model):
    """Three small local requests; no user data. A single question isn't a benchmark."""
    if not is_local(endpoint):
        raise ValueError("Passport exam accepts only local loopback endpoints")
    if not isinstance(model, str) or not model or len(model) > 200:
        raise ValueError("Invalid model name")
    record = {"endpoint": endpoint.rstrip("/"), "model": model, "exam": {}, "feedback": {"good": 0, "bad": 0}, "measured_at": int(time.time())}
    questions = (
        ("tools", "Call the ping tool with value ok.", True),
        ("json", 'Reply with only this JSON object: {"ok":true}', False),
        ("logic", "A box has two red balls and three blue balls. If one red ball is removed, how many balls remain? Reply with only the number.", False),
    )
    for name, prompt, tools in questions:
        try:
            response, seconds = _chat(endpoint, model, prompt, tools=tools)
            content, calls = _answer(response)
            if name == "tools":
                passed = any(isinstance(call, dict) and call.get("function", {}).get("name") == "ping" for call in calls)
            elif name == "json":
                passed = json.loads(content.strip()) == {"ok": True}
            else:
                passed = content.strip() == "4"
            usage = response.get("usage") or {}
            tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
            record["exam"][name] = {"passed": passed, "seconds": seconds, "tokens_per_second": round(tokens / seconds, 1) if isinstance(tokens, int) and seconds > 0 else None}
        except (ValueError, OSError, TypeError, KeyError):
            record["exam"][name] = {"passed": False, "seconds": None, "tokens_per_second": None, "inconclusive": True}
    # Vision is not tested with text-only requests. Do not turn unknown into a fail.
    record["exam"]["vision"] = {"passed": None, "inconclusive": True}
    return record


def refresh_passports(path=None):
    """Explicit scan/exam, not a background monitor. Skip configured remote providers."""
    local = [entry for entry in inspect_endpoints() if entry.get("status") == "reachable" and is_local(entry.get("endpoint", ""))]
    current = {(p["endpoint"], p["model"]): p for p in read_passports(path)}
    updated = []
    for entry in local:
        endpoint = entry["endpoint"]
        if not is_local(endpoint):
            continue
        for model in entry["models"]:
            if len(updated) >= MAX_MODELS:
                break
            item = examine(endpoint, model["id"])
            previous = current.get((endpoint, model["id"]))
            if previous:
                item["feedback"] = previous.get("feedback", {"good": 0, "bad": 0})
            item["declared"] = {k: model.get(k) for k in ("tool_calling", "vision", "embedding", "context_length")}
            updated.append(item)
    save_passports(updated, path)
    return updated


def record_feedback(endpoint, model, outcome, path=None):
    """Explicit human feedback, not inferred answer quality."""
    if outcome not in {"good", "bad"}:
        raise ValueError("Feedback must be good or bad")
    passports = read_passports(path)
    for passport in passports:
        if (passport.get("endpoint"), passport.get("model")) == (endpoint, model):
            votes = passport.setdefault("feedback", {"good": 0, "bad": 0})
            votes[outcome] = min(1000, votes.get(outcome, 0) + 1)
            save_passports(passports, path)
            return
    raise ValueError("Model has no passport")


def route(task, passports=None, *, require_tools=True):
    """Predictable local-only choice; never sends task text or starts a model."""
    if not isinstance(task, str):
        raise ValueError("Task must be text")
    passports = read_passports() if passports is None else passports
    category = "code" if any(word in task.lower() for word in ("code", "python", "debug", "script")) else "chat"
    candidates = []
    for p in passports:
        if not is_local(p.get("endpoint", "")):
            continue
        exam = p.get("exam", {})
        if require_tools and not exam.get("tools", {}).get("passed"):
            continue
        feedback = p.get("feedback", {})
        good = min(feedback.get("good", 0), 1000)
        bad = min(feedback.get("bad", 0), 1000)
        score = (3 if exam.get("logic", {}).get("passed") else 0) + (2 if exam.get("json", {}).get("passed") else 0)
        speed = [x.get("tokens_per_second") for x in exam.values() if isinstance(x, dict) and isinstance(x.get("tokens_per_second"), (int, float))]
        score += min(max(speed, default=0), 100) / (100 if category == "code" else 25)
        score += 2 * (good - bad) / (good + bad + 2)
        candidates.append((score, p))
    if not candidates:
        raise ValueError("No local passport passed the tool-call test; run models passport or choose --model explicitly")
    candidates.sort(key=lambda x: (-x[0], x[1]["model"], x[1]["endpoint"]))
    score, winner = candidates[0]
    return {"model": winner["model"], "endpoint": winner["endpoint"], "category": category, "score": round(score, 2), "reason": "local tool pass, simple JSON/logic/speed samples, and explicit feedback"}
