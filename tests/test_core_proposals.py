import json
import tempfile
import unittest
from pathlib import Path
from cheerio.core_proposals import propose_core, summarize_patterns
from cheerio.memory import Memory

IDEA = {"title": "Limit repeated tool failures", "reason": "Three failures appeared in journal", "file": "cheerio/agents.py", "change": "Add a bounded retry policy", "test_plan": "Add a fake-model test", "risk": "May stop recoverable calls"}

class CoreProposalTests(unittest.TestCase):
    def test_requires_evidence_and_writes_note_not_code(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            m = Memory(folder / "m.db")
            with self.assertRaises(ValueError):
                summarize_patterns(m)
            for n in range(3):
                m.append("skill_use_failed", "foo", f"failure {n}")
            note, idea = propose_core({}, m, folder / "notes", json.dumps(IDEA))
            self.assertEqual(note.suffix, ".json")
            self.assertEqual(json.loads(note.read_text())["status"], "needs human review")
            self.assertEqual(list((folder / "notes").glob("*.py")), [])
            with self.assertRaises(ValueError):
                propose_core({}, m, folder / "notes", json.dumps({**IDEA, "file": "../../evil.py"}))

if __name__ == "__main__":
    unittest.main()
