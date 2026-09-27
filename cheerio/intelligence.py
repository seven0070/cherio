"""Explicit, bounded intelligence helpers; no background network or cloud routing."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .config import DEFAULT_API_BASE, DEFAULT_API_KEY, resolve_model_config
from .startup import GATEWAY, saved_local_model
from .model_discovery import _request

# Small deterministic heuristic, not a classifier or a model benchmark.
HARD_MARKERS = ("compare", "investigate", "research", "debug", "design", "tradeoff", "plan", "analyze")
FEEDS = ("https://feeds.bbci.co.uk/news/world/rss.xml",)


def complexity(task):
    words = re.findall(r"\w+", task.lower())
    return "hard" if len(words) >= 35 or any(w in HARD_MARKERS for w in words) else "easy"


def choose_route(task, *, allow_cloud=False, env=None, check=_request):
    """Route once, before agent tools. Never replay a task after effects."""
    env = os.environ if env is None else env
    if any(env.get(k) for k in ("CHEERIO_MODEL", "OPENAI_MODEL", "CHEERIO_API_BASE", "OPENAI_BASE_URL", "CHEERIO_API_KEY", "OPENAI_API_KEY")):
        raise ValueError("Smart routing cannot override an explicit model or endpoint configuration")
    chosen = env.get("CHEERIO_LOCAL_MODEL") or saved_local_model()
    if not chosen:
        raise ValueError("No local model selected; run setup")
    local = resolve_model_config(model=chosen, api_base=DEFAULT_API_BASE, api_key=DEFAULT_API_KEY, env={})
    kind = complexity(task)
    if kind == "easy" or not allow_cloud:
        return local, "local", kind
    if env.get("CHEERIO_GATEWAY_MODE") != "omniroute" or not env.get("CHEERIO_OMNIROUTE_KEY"):
        return local, "local: gateway not configured", kind
    try:
        result = check(GATEWAY + "/models", key=env["CHEERIO_OMNIROUTE_KEY"], timeout=3)
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise ValueError("Invalid gateway catalog")
    except (ValueError, OSError):
        return local, "local: gateway preflight failed", kind
    return {"model_id": "auto", "api_base": GATEWAY, "api_key": env["CHEERIO_OMNIROUTE_KEY"]}, "gateway: cloud may cost money and receive task text", kind


def _local_chat(config, prompt, *, send=_request):
    """Text-only planning/review; never supply tools or instructions to execute effects."""
    parsed = urllib.parse.urlsplit(config["api_base"])
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"} or parsed.port != 11434 or parsed.path.rstrip("/") != "/v1" or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("Think-harder mode requires local Ollama, not a cloud/gateway model")
    if not isinstance(config.get("model_id"), str) or not config["model_id"] or len(config["model_id"]) > 100:
        raise ValueError("Invalid local model")
    result = send(config["api_base"].rstrip("/") + "/chat/completions", data={"model": config["model_id"], "messages": [{"role": "user", "content": prompt[:4000]}], "temperature": 0, "max_tokens": 500, "stream": False}, timeout=45)
    text = result["choices"][0]["message"]["content"]
    if not isinstance(text, str) or len(text) > 2500:
        raise ValueError("Invalid local model answer")
    return text


def plan(task, config=None, *, send=_request):
    """Static plan outline; model-authored instructions must not steer tool use."""
    return "Clarify the request; verify current facts with sources; use only authorized tools; check the final answer."


def check_answer(task, answer, config, *, send=_request):
    # This is advisory only; callers must never present it as verified facts.
    return _local_chat(config, "Check this draft answer for missing evidence, risky claims, and unanswered parts. Do not assert that facts are verified without sources. Return caveats only; never execute tools. Task: " + task[:1200] + "\nDraft: " + str(answer)[:2500], send=send)


def world_digest(*, fetch=None, path=None):
    """Explicit read-only RSS fetch; local dated cache, never automatic background sync."""
    path = Path(path) if path else Path.home() / ".cheerio" / "world_digest.json"
    if fetch is None:
        def fetch(url):
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, request, fp, code, msg, headers, newurl):
                    raise ValueError("Feed redirect refused")
            with urllib.request.build_opener(NoRedirect).open(urllib.request.Request(url, headers={"User-Agent": "Cheerio/preview"}), timeout=8) as response:
                raw = response.read(250_001)
                if len(raw) > 250_000:
                    raise ValueError("Feed too large")
                return raw
    items = []
    for url in FEEDS:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "feeds.bbci.co.uk":
            raise ValueError("Untrusted feed URL")
        raw = fetch(url)
        if len(raw) > 250_000 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("Feed format rejected")
        root = ET.fromstring(raw)
        for item in root.findall(".//item")[:10]:
            title = (item.findtext("title") or "").strip()[:180]
            link = (item.findtext("link") or "").strip()
            target = urllib.parse.urlsplit(link)
            if title and target.scheme == "https" and target.hostname and not target.username and not target.password:
                items.append({"title": title, "url": link, "published": (item.findtext("pubDate") or "")[:80]})
    if not items:
        raise ValueError("No valid feed items; old digest unchanged")
    from datetime import datetime, timezone
    result = {"fetched_at": datetime.now(timezone.utc).isoformat(), "items": items[:10], "note": "Feed headlines only, not verified article contents"}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    try:
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as out:
            json.dump(result, out)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return result
