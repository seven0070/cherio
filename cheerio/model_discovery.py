"""Bounded, read-only discovery of local OpenAI-compatible model servers.

No full-drive crawl, remote requests, credential printing or model downloads.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
LOCAL_ENDPOINTS = (
    ("ollama", "http://127.0.0.1:11434/v1"),
    ("lm-studio", "http://127.0.0.1:1234/v1"),
    ("llama.cpp/other", "http://127.0.0.1:8080/v1"),
)
MAX_RESPONSE = 1_000_000


def is_local(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme == "http" and parsed.hostname in LOCAL_HOSTS and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment


def provider_for(url):
    """Endpoint hints only. API key spelling cannot identify its provider."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    if host in LOCAL_HOSTS:
        try:
            port = urllib.parse.urlsplit(url).port
        except ValueError:
            return "invalid endpoint"
        return {11434: "ollama", 1234: "lm-studio", 8080: "llama.cpp/other"}.get(port, "local OpenAI-compatible")
    for suffix, name in (("api.openai.com", "openai"), ("api.groq.com", "groq"),
                         ("openrouter.ai", "openrouter"), ("api.together.xyz", "together")):
        if host == suffix:
            return name
    return "unknown OpenAI-compatible"


def _request(url, key=None, data=None, timeout=2):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Invalid endpoint URL")
    if parsed.scheme == "http" and not is_local(url):
        raise ValueError("Remote HTTP is refused; use HTTPS")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    # Do not forward credentials through redirects to another host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError("Redirect refused")
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE + 1)
            if len(body) > MAX_RESPONSE:
                raise ValueError("Response too large")
            return json.loads(body)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Endpoint did not return a valid JSON response") from exc


def _models(data):
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ValueError("Invalid model-list response")
    return [entry["id"] for entry in data["data"][:100] if isinstance(entry, dict) and isinstance(entry.get("id"), str)][:100]


def _ollama_metadata(base, model):
    url = base.removesuffix("/v1") + "/api/show"
    try:
        data = _request(url, data={"model": model})
    except ValueError:
        return {}
    caps = data.get("capabilities", []) if isinstance(data, dict) else []
    details = data.get("model_info", {}) if isinstance(data, dict) else {}
    context = next((v for k, v in details.items() if k.endswith(".context_length") and isinstance(v, int)), None) if isinstance(details, dict) else None
    return {"declared_capabilities": sorted(c for c in caps if isinstance(c, str)) if isinstance(caps, list) else [], "context_length": context}


def probe_tools(base, model, key=None):
    """Opt-in small live generation probe. Successful call establishes tool-call response only."""
    payload = {"model": model, "messages": [{"role": "user", "content": "Call the ping tool with value ok."}],
               "tools": [{"type": "function", "function": {"name": "ping", "description": "Test tool", "parameters": {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}}}],
               "tool_choice": "required", "max_tokens": 32, "stream": False}
    try:
        result = _request(base.rstrip("/") + "/chat/completions", key, payload, timeout=12)
        choice = result.get("choices", [{}])[0]
        return bool(choice.get("message", {}).get("tool_calls"))
    except (ValueError, KeyError, IndexError, TypeError):
        return False


def inspect_endpoints(endpoints=(), *, include_remote=False, probe=False, env=None):
    env = os.environ if env is None else env
    candidates = list(LOCAL_ENDPOINTS)
    configured = env.get("CHEERIO_API_BASE") or env.get("OPENAI_BASE_URL")
    if configured:
        candidates.append(("configured", configured))
    candidates.extend(("specified", endpoint) for endpoint in endpoints)
    seen, results = set(), []
    key = env.get("CHEERIO_API_KEY") or env.get("OPENAI_API_KEY")
    for _, base in candidates:
        base = base.rstrip("/")
        if base in seen:
            continue
        seen.add(base)
        # Never print URL-embedded credentials, query strings or fragments.
        parts = urllib.parse.urlsplit(base)
        if parts.username or parts.password or parts.query or parts.fragment:
            results.append({"endpoint": "[redacted invalid URL]", "provider": "unknown", "status": "invalid endpoint"})
            continue
        if not is_local(base) and not include_remote:
            results.append({"endpoint": base, "provider": provider_for(base), "status": "remote skipped (explicit --remote required)"})
            continue
        if not is_local(base) and urllib.parse.urlsplit(base).scheme != "https":
            results.append({"endpoint": base, "provider": provider_for(base), "status": "invalid or insecure endpoint"})
            continue
        try:
            # The configured credential belongs only to its configured endpoint, not arbitrary --endpoint hosts.
            credential = key if not is_local(base) and base == (configured or "").rstrip("/") else None
            ids = _models(_request(base + "/models", credential))
            models = []
            for model in ids:
                metadata = _ollama_metadata(base, model) if provider_for(base) == "ollama" else {}
                item = {"id": model, "tool_calling": "unknown", "vision": "unknown", "embedding": "unknown", "context_length": metadata.get("context_length")}
                for capability, field in (("tools", "tool_calling"), ("vision", "vision"), ("embedding", "embedding")):
                    if capability in metadata.get("declared_capabilities", []):
                        item[field] = "declared by runtime"
                if probe and (is_local(base) or include_remote):
                    item["tool_calling"] = "probe passed" if probe_tools(base, model, credential) else "probe failed or inconclusive"
                models.append(item)
            results.append({"endpoint": base, "provider": provider_for(base), "status": "reachable", "models": models})
        except (ValueError, urllib.error.HTTPError):
            # Avoid embedding server errors or response bodies that might include sensitive data.
            results.append({"endpoint": base, "provider": provider_for(base), "status": "unavailable or unauthorized"})
    return results


def find_gguf(roots, max_files=2000, max_dirs=500):
    """Explicit bounded roots, no symlinks, hidden dirs, or whole-PC traversal."""
    found = []
    for root in roots:
        root = Path(root).expanduser()
        if not root.is_dir() or root.is_symlink():
            continue
        count = 0
        visited = 0
        for directory, dirs, files in os.walk(root, followlinks=False):
            visited += 1
            if visited > max_dirs:
                dirs[:] = []
                break
            dirs[:] = [d for d in dirs if not d.startswith(".") and not (Path(directory) / d).is_symlink()][:100]
            for name in files:
                count += 1
                if count > max_files:
                    break
                path = Path(directory) / name
                if name.lower().endswith(".gguf") and not path.is_symlink():
                    found.append(str(path))
            if count > max_files:
                break
    return found
