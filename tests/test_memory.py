import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cheerio.memory import Memory
from cheerio.__main__ import chat_loop


class FakeAgent:
    def __init__(self):
        self.prompts = []
    def run(self, prompt, reset=True):
        self.prompts.append(prompt)
        return "answer"


class MemoryTests(unittest.TestCase):
    def test_write_read_reopen_forget(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "memory.db"
            m = Memory(path)
            m.append("chat", "first task", "done")
            item = Memory(path).recent()[0]
            self.assertIn("first task", m.context())
            m.forget(item["id"])
            self.assertEqual(m.recent(), [])
            m.append("skill_failed", "s", "oops")
            m.forget()
            self.assertEqual(m.recent(), [])

    def test_chat_context_and_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "memory.db")
            m.append("chat", "earlier", "worked")
            agent = FakeAgent()
            with patch("builtins.input", side_effect=["new question", "/exit"]), patch("builtins.print"):
                chat_loop(agent, m)
            self.assertIn("earlier", agent.prompts[0])
            self.assertIn("untrusted data", agent.prompts[0])
            self.assertEqual(m.recent()[0]["request"], "new question")

    def test_invalid_kind_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                Memory(Path(d) / "memory.db").append("DELETE FROM", "x", "y")
