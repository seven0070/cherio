import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bella.core import PERSONA, Store, envelope, local_ollama
from bella.worker import run


class BellaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "data" / "bella.db")
        self.addCleanup(self.store.close)

    def test_explicit_notes_and_forget(self):
        self.store.remember("likes short answers")
        self.assertEqual(self.store.notes(), ["likes short answers"])
        self.assertTrue(self.store.forget(1))
        self.assertEqual(self.store.notes(), [])

    def test_reject_empty_or_huge_notes(self):
        for text in (" ", "x" * 1001):
            with self.assertRaises(ValueError):
                self.store.remember(text)

    def test_task_state_and_envelope(self):
        ident = self.store.propose("Find sources")
        payload = envelope(self.store.task(ident))
        self.assertEqual(payload["schema"], "bella.cheerio.task.v1")
        self.assertEqual(payload["goal"], "Find sources")
        self.store.transition(ident, "pending", "done", "Sources found")
        self.assertEqual(self.store.task(ident)["result"], "Sources found")
        with self.assertRaises(ValueError):
            self.store.transition(ident, "pending", "done")

    def test_reject_oversize_task(self):
        with self.assertRaises(ValueError):
            self.store.propose("x" * 2001)

    def test_no_remote_model_or_redirect_endpoint(self):
        for url in ("https://127.0.0.1:11434/api/chat", "http://example.com:11434/api/chat", "http://localhost:80/api/chat", "http://127.0.0.1:11434/other"):
            with self.assertRaises(ValueError):
                local_ollama("hi", [], url=url)

    def test_handoff_uses_argv_and_stdin_not_shell(self):
        checkout = Path(self.tmp.name)
        (checkout / "cheerio").mkdir()
        (checkout / "cheerio" / "__init__.py").write_text("")
        goal = "find '$HOME'; do not shell expand"
        ident = self.store.propose(goal)
        request = envelope(self.store.task(ident))
        def fake_runner(command, **kwargs):
            self.assertEqual(command[1:3], ["-m", "bella.runner"])
            self.assertEqual(json.loads(kwargs["input"])["goal"], goal)
            self.assertNotIn("shell", kwargs)
            return subprocess.CompletedProcess(command, 0, json.dumps({"task_id": ident, "result": "ok"}), "")
        self.assertEqual(run(checkout, request, runner=fake_runner), "ok")

    def test_persona_boundaries(self):
        for phrase in ("never claim to be human", "challenge procrastination", "sexual or romantic", "substitute for family", "risky or irreversible", "restricted model-only"):
            self.assertIn(phrase, PERSONA)

    def test_frozen_handoff_fails_clearly(self):
        with patch.object(sys, 'frozen', True, create=True):
            with self.assertRaisesRegex(RuntimeError, 'Python source install'):
                run(Path(self.tmp.name), {'schema': 'bella.cheerio.task.v1', 'approval': 'explicit-local-user', 'goal': 'x'})

    def test_bad_handoff_rejected(self):
        with self.assertRaises(ValueError):
            run(Path(self.tmp.name), {"schema": "bad", "approval": "explicit-local-user", "goal": "x"})


if __name__ == "__main__":
    unittest.main()

class SafetyTests(unittest.TestCase):
    def test_pending_cannot_repeat_after_interruption(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bella.db'
            store = Store(path)
            ident = store.propose('x')
            store.transition(ident, 'pending', 'running')
            store.db.close()
            reopened = Store(path)
            self.assertEqual(reopened.task(ident)['state'], 'interrupted')
            with self.assertRaises(ValueError):
                reopened.transition(ident, 'pending', 'running')
            reopened.close()

    def test_runner_has_no_general_agent_or_tools(self):
        source = (Path(__file__).resolve().parents[1] / 'bella' / 'runner.py').read_text()
        self.assertIn('ToolCallingAgent(tools=[]', source)
        self.assertNotIn('build_general_agent', source)
        self.assertIn('127.0.0.1:11434', source)
        self.assertIn('env={}', source)
