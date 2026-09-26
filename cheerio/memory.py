"""Bounded, local event memory. No model write access to database controls."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3


MAX_EVENTS = 500
MAX_FIELD = 1000


def memory_path():
    return Path(os.environ.get("CHEERIO_MEMORY_DB", str(Path.home() / ".cheerio" / "memory.sqlite3")))


class Memory:
    """Local task/outcome journal. Only host application calls append/clear."""
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else memory_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, request TEXT NOT NULL, outcome TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def append(self, kind, request, outcome):
        if kind not in {"chat", "skill_created", "skill_failed", "skill_used", "skill_use_failed", "skill_fix_proposed", "core_change_proposed"}:
            raise ValueError("Unknown memory event kind")
        with self._connect() as conn:
            conn.execute("INSERT INTO events(kind, request, outcome) VALUES (?,?,?)", (kind, str(request)[:MAX_FIELD], str(outcome)[:MAX_FIELD]))
            conn.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT ?)", (MAX_EVENTS,))

    def recent(self, limit=8, kinds=None):
        limit = max(1, min(int(limit), 30))
        with self._connect() as conn:
            if kinds:
                kinds = tuple(k for k in kinds if k in {"chat", "skill_created", "skill_failed", "skill_used", "skill_use_failed", "skill_fix_proposed", "core_change_proposed"})
                if not kinds:
                    return []
                rows = conn.execute(f"SELECT id, kind, request, outcome, created FROM events WHERE kind IN ({','.join('?' for _ in kinds)}) ORDER BY id DESC LIMIT ?", (*kinds, limit))
            else:
                rows = conn.execute("SELECT id, kind, request, outcome, created FROM events ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(zip(("id", "kind", "request", "outcome", "created"), row)) for row in rows]

    def forget(self, event_id=None):
        with self._connect() as conn:
            if event_id is None:
                conn.execute("DELETE FROM events")
            else:
                conn.execute("DELETE FROM events WHERE id=?", (int(event_id),))

    def context(self):
        # Context is data, explicitly demoted from instructions; cap 8 events and 3200 chars.
        items = list(reversed(self.recent(8)))
        return "\n".join(f"- [{item['kind']}] request={item['request']!r}; outcome={item['outcome']!r}" for item in items)[:3200]
