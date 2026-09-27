import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cheerio.improve import approve_skill_fix, propose_skill_fix
from cheerio.memory import Memory
from cheerio.skills import save_skill

OLD = {"name": "double_number", "description": "Double a number represented as text", "code": "def double_number(text):\n    return str(int(text) * 2)", "tests": [{"input": "3", "expected": "6"}]}
NEW = {**OLD, "code": "def double_number(text):\n    return str(int(float(text)) * 2)", "tests": [{"input": "3", "expected": "6"}, {"input": "4.0", "expected": "8"}]}

class ImproveTests(unittest.TestCase):
    def test_failure_to_proposal_to_human_approval(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            db = Memory(folder / "memory.db")
            original = save_skill(OLD, folder)
            db.append("skill_use_failed", "double_number", "4.0 was not parsed")
            with patch("cheerio.improve.draft_skill", return_value=NEW), patch.dict("os.environ", {"CHEERIO_MEMORY_DB": str(folder / "memory.db")}, clear=False):
                proposal, candidate, results, digest = propose_skill_fix("double_number", {"x": "y"}, db, folder)
                self.assertTrue(proposal.exists())
                self.assertEqual(json.loads(original.read_text())["code"], OLD["code"])
                self.assertFalse(approve_skill_fix("double_number", "yes", folder, digest))
                self.assertEqual(json.loads(original.read_text())["code"], OLD["code"])
                self.assertTrue(approve_skill_fix("double_number", "APPROVE", folder, digest))
                self.assertEqual(json.loads(original.read_text())["code"], NEW["code"])
                self.assertFalse(proposal.exists())

    def test_refuses_missing_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            save_skill(OLD, folder)
            with self.assertRaises(ValueError):
                propose_skill_fix("double_number", {}, Memory(folder / "db"), folder)
