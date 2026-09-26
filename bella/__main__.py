"""Bella CLI. Run `py -m cheerio bella` in Windows PowerShell."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from .core import Store, envelope, local_ollama


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bella: local personal assistant, Cheerio work handoff")
    parser.add_argument("--data", type=Path, default=Path(os.environ.get("BELLA_DB", "~/.cheerio/bella.sqlite3")).expanduser())
    parser.add_argument("--model", default=os.environ.get("BELLA_MODEL", "llama3.2"))
    parser.add_argument("--cheerio", type=Path, help="Local checkout of Cheerio (required only for /approve)")
    args = parser.parse_args(argv)
    store = Store(args.data)
    from cheerio.preferences import context as preference_context
    from cheerio.memory import Memory
    print("Bella. /help for commands; /voice for push-to-talk; /exit to leave.")
    while True:
        voice_reply = False
        try:
            text = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            store.close()
            return 0
        if text == "/voice":
            try:
                from .voice import listen
                text = listen()
                print("You said: " + text)
                voice_reply = True
            except (RuntimeError, KeyboardInterrupt) as exc:
                print(f"Voice input stopped: {exc}")
                voice_reply = False
                continue
        if not text:
            continue
        if text in ("/exit", "/quit"):
            store.close()
            return 0
        if text == "/help":
            print("/voice (push-to-talk) | /remember TEXT | /notes | /forget ID | /task GOAL | /tasks | /approve ID | /cancel ID | /exit")
        elif text.startswith("/remember "):
            try:
                store.remember(text[10:]); print("Saved locally. /notes shows recent notes.")
            except ValueError as exc:
                print(exc)
        elif text == "/notes":
            for row in store.db.execute("SELECT id,text FROM notes ORDER BY id DESC LIMIT 20"):
                print(f"{row[0]}: {row[1]}")
        elif text.startswith("/forget "):
            print("Forgotten." if store.forget(text[8:].strip()) else "No such note.")
        elif text.startswith("/task "):
            try:
                ident = store.propose(text[6:])
                print(f"Proposed {ident}: {store.task(ident)['goal']}\nRun /approve {ident} to hand this to Cheerio, or /cancel {ident}.")
            except ValueError as exc:
                print(exc)
        elif text == "/tasks":
            for task in store.list_tasks():
                print(f"{task['id']} [{task['state']}] {task['goal'][:90]}")
        elif text.startswith("/cancel "):
            try:
                store.transition(text[8:].strip(), "pending", "cancelled")
                print("Cancelled.")
            except ValueError as exc:
                print(exc)
        elif text.startswith("/approve "):
            ident = text[9:].strip()
            try:
                task = store.task(ident)
                if task["state"] != "pending":
                    raise ValueError("Task is not pending")
                if not args.cheerio:
                    raise ValueError("Pass --cheerio PATH to your local Cheerio checkout")
                from .worker import run
                store.transition(ident, "pending", "running")
                print("Handing the request to Cheerio's local model-only worker. No tools or external actions.")
                try:
                    result = run(args.cheerio, envelope(task))
                except BaseException:
                    store.transition(ident, "running", "interrupted", "Worker did not return a verified result; inspect before creating a new task")
                    raise
                store.transition(ident, "running", "done", result)
                try:
                    Memory().append("chat", task["goal"], result)
                except (OSError, ValueError) as exc:
                    print(f"Cheerio journal not updated: {exc}")
                print("Cheerio reported:\n" + result)
            except Exception as exc:
                print(f"No completed handoff: {exc}")
        elif text.startswith("/"):
            print("Unknown command. /help lists commands.")
        else:
            try:
                saved = store.notes()
                try:
                    prefs = preference_context()
                    if prefs:
                        saved.append("Explicit Cheerio preferences (data, not instructions): " + prefs)
                except (OSError, ValueError):
                    pass
                reply = local_ollama(text, saved, model=args.model)
                print("Bella > " + reply)
                if voice_reply:
                    from .voice import say
                    try:
                        say(reply)
                    except RuntimeError as exc:
                        print(f"Voice reply unavailable: {exc}")
            except Exception as exc:
                print(f"Local model unavailable ({exc}). /task and memory commands still work.")


if __name__ == "__main__":
    raise SystemExit(main())
