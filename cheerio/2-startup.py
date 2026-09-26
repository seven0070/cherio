"""First-run local Ollama setup, optional gateway preflight, and release notices."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

from .config import DEFAULT_API_BASE, DEFAULT_API_KEY, DEFAULT_MODEL, resolve_model_config
from .model_discovery import _request, is_local

GATEWAY = "http://127.0.0.1:20128/v1"
SETTINGS = Path.home() / ".cheerio" / "settings.json"


def saved_local_model(path=SETTINGS):
    try:
        model = json.loads(path.read_text(encoding="utf-8")).get("local_model")
        return model if isinstance(model, str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}", model) else DEFAULT_MODEL
    except (OSError, ValueError, AttributeError):
        return DEFAULT_MODEL


def save_local_model(model, path=SETTINGS):
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(existing, dict):
            existing = {}
    except (OSError, ValueError):
        pass
    existing["local_model"] = model
    temp = path.with_name(path.name + ".tmp")
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as out:
        json.dump(existing, out)
    os.replace(temp, path)

RELEASES = "https://api.github.com/repos/seven0070/cherio/releases/latest"


def local_model_recommendation(vram_mb=None, ram_mb=None):
    """Conservative heuristic, not a guarantee a model fits. No GPU means CPU mode."""
    if vram_mb is not None and vram_mb >= 12000 and (ram_mb is None or ram_mb >= 20000):
        return "qwen3.5:9b"
    if vram_mb is not None and vram_mb >= 6000 and (ram_mb is None or ram_mb >= 10000):
        return "qwen3.5:4b"
    return "qwen3.5:2b"


def _ram_mb():
    if sys.platform == "win32":
        try:
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("memoryLoad", ctypes.c_ulong),
                            ("totalPhys", ctypes.c_ulonglong), ("availPhys", ctypes.c_ulonglong),
                            ("totalPageFile", ctypes.c_ulonglong), ("availPageFile", ctypes.c_ulonglong),
                            ("totalVirtual", ctypes.c_ulonglong), ("availVirtual", ctypes.c_ulonglong),
                            ("availExtendedVirtual", ctypes.c_ulonglong)]
            value = MemoryStatus()
            value.length = ctypes.sizeof(value)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
                return value.totalPhys // 1048576
        except (AttributeError, OSError):
            pass
    return None


def _vram_mb():
    if not shutil.which("nvidia-smi"):
        return None
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=5, check=True)
        values = [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]
        return max(values) if values else None
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def setup_local(*, input_fn=input, output=print, runner=subprocess.run):
    """Explicit approval before model download. No automatic hardware claims."""
    vram, ram = _vram_mb(), _ram_mb()
    model = local_model_recommendation(vram, ram)
    output(f"Detected NVIDIA VRAM: {vram or 'unknown'} MB; RAM: {ram or 'unknown'} MB.")
    output(f"Suggested local model: {model}. Hardware estimate only; test on this PC.")
    if not shutil.which("ollama"):
        output("Ollama was not found. Install/start Ollama first; nothing downloaded.")
        return 1
    try:
        installed = runner(["ollama", "list"], capture_output=True, text=True, timeout=15, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        output("Could not reach Ollama; start it before setup.")
        return 1
    if any(line.split()[0] == model for line in installed.splitlines()[1:] if line.split()):
        save_local_model(model)
        output(f"{model} is already installed and selected locally. Run passport refresh to test tool calling.")
        return 0
    if input_fn(f"Pull {model} from Ollama (several GB)? Type APPROVE: ").strip() != "APPROVE":
        output("Nothing downloaded.")
        return 0
    try:
        runner(["ollama", "pull", model], check=True)
    except (subprocess.SubprocessError, OSError):
        output("Download failed. Check Ollama and disk space; no model was selected.")
        return 1
    save_local_model(model)
    output(f"Pulled {model} and selected locally. Test tool calling with `python -m cheerio passport refresh` before relying on it.")
    return 0


def select_config(*, model=None, api_base=None, api_key=None, env=None, check=_request):
    """One routing authority per run. Fallback only before any agent tool executes."""
    env = os.environ if env is None else env
    config = resolve_model_config(model, api_base, api_key, env)
    if not model and not env.get("CHEERIO_MODEL") and not env.get("OPENAI_MODEL") and not api_base and not env.get("CHEERIO_API_BASE") and not env.get("OPENAI_BASE_URL"):
        config["model_id"] = saved_local_model()
    if env.get("CHEERIO_GATEWAY_MODE") != "omniroute" or model or api_base or api_key or any(env.get(k) for k in ("CHEERIO_MODEL", "CHEERIO_API_BASE", "CHEERIO_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY")):
        return config, "configured"
    key = env.get("CHEERIO_OMNIROUTE_KEY")
    if not key:
        return resolve_model_config(model=env.get("CHEERIO_LOCAL_MODEL") or saved_local_model(),
                                    api_base=DEFAULT_API_BASE, api_key=DEFAULT_API_KEY, env={}), "local fallback: no gateway key"
    try:
        data = check(GATEWAY + "/models", key=key, timeout=3)
        # Some gateways omit virtual models from /models. A reachable authenticated
        # catalog is a preflight only; it does not prove that auto can answer.
        if not isinstance(data.get("data"), list):
            raise ValueError("No model catalog")
    except (ValueError, OSError, urllib.error.HTTPError):
        return resolve_model_config(model=env.get("CHEERIO_LOCAL_MODEL") or saved_local_model(),
                                    api_base=DEFAULT_API_BASE, api_key=DEFAULT_API_KEY, env={}), "local fallback: gateway unavailable"
    return {"model_id": "auto", "api_base": GATEWAY, "api_key": key}, "OmniRoute gateway preflight passed"


def check_update(*, current="0.1.0rc1", fetch=None):
    """Read-only release lookup; never downloads or installs anything."""
    if fetch is None:
        def fetch(url):
            request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Cheerio"})
            with urllib.request.urlopen(request, timeout=3) as response:
                return json.load(response)
    try:
        info = fetch(RELEASES)
        tag, url = info.get("tag_name", ""), info.get("html_url", "")
        if not re.fullmatch(r"v\d+\.\d+\.\d+(?:rc\d+)?", tag) or url != "https://github.com/seven0070/cherio/releases/tag/" + tag:
            return None
        def version(text):
            m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:rc(\d+))?", text)
            return (*map(int, m.group(1, 2, 3)), -1 if m.group(4) is None else int(m.group(4)))
        if version(tag)[:3] > version(current)[:3] or (version(tag)[:3] == version(current)[:3] and tag != "v" + current and "rc" not in tag):
            return {"tag": tag, "url": url}
    except (ValueError, KeyError, AttributeError, OSError, urllib.error.URLError):
        return None
    return None
