"""One safety boundary shared by the Bella CLI and desktop. No tool execution."""
from __future__ import annotations

from pathlib import Path
from .core import Store, envelope
from .worker import run


def approve(store: Store, ident: str, checkout: Path, *, worker=run):
    task = store.task(ident)
    if task["state"] != "pending":
        raise ValueError("Task is not pending")
    if not checkout:
        raise ValueError("Cheerio source checkout required")
    request = envelope(task)
    store.transition(ident, "pending", "running")
    try:
        result = worker(checkout, request)
    except BaseException:
        store.transition(ident, "running", "interrupted", "Worker did not return a verified result; inspect before making a new task")
        raise
    store.transition(ident, "running", "done", result)
    try:
        from cheerio.memory import Memory
        Memory().append("chat", task["goal"], result)
    except (OSError, ValueError):
        pass
    return result
