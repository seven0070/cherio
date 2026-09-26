"""Data-only handoff to the user's local Cheerio checkout. Never shell-interpolate goals."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(checkout, request, *, runner=subprocess.run):
    checkout = Path(checkout).expanduser().resolve(strict=True)
    if request.get("schema") != "bella.cheerio.task.v1" or request.get("approval") != "explicit-local-user":
        raise ValueError("Unsupported handoff envelope")
    goal = request.get("goal", "")
    if not isinstance(goal, str) or not 0 < len(goal) <= 2000:
        raise ValueError("Invalid task goal")
    if not (checkout / "cheerio" / "__init__.py").is_file():
        raise ValueError("Not a Cheerio checkout")
    # The dedicated bridge captures Cheerio's answer as JSON, without conversation with user.
    command = [sys.executable, "-m", "bella.runner", str(checkout)]
    try:
        proc = runner(command, input=json.dumps(request), text=True, capture_output=True, timeout=900)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Cheerio timed out; check its side effects before retrying") from exc
    if proc.returncode:
        raise RuntimeError("Cheerio failed; check its side effects before retrying: " + proc.stderr[-500:])
    output = json.loads(proc.stdout)
    if output.get("task_id") != request.get("task_id") or not isinstance(output.get("result"), str):
        raise ValueError("Mismatched worker response")
    return output["result"]
