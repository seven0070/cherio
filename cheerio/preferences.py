"""Explicit local preference/project notes, never inferred from chat history."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re


def store_path():
    return Path(os.environ.get("CHEERIO_PREFERENCES", str(Path.home() / ".cheerio" / "preferences.json")))


def read(path=None):
    path = Path(path) if path else store_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict) or len(data) > 40 or any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 300 for k, v in data.items()):
        raise ValueError("Invalid preference store")
    return data


def update(key, value, path=None):
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{2,40}", key):
        raise ValueError("Invalid preference key")
    if value is not None and (not isinstance(value, str) or not 1 <= len(value) <= 300):
        raise ValueError("Preference value must be 1-300 characters")
    path = Path(path) if path else store_path()
    if path.is_symlink():
        raise ValueError("Symlink store refused")
    data = read(path)
    if value is None:
        data.pop(key, None)
    else:
        if len(data) >= 40 and key not in data:
            raise ValueError("Preference store full")
        data[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    try:
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return data


def context(path=None):
    data = read(path)
    return "\n".join(f"{key}: {value}" for key, value in sorted(data.items()))[:3000]
