import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cheerio.skills import load_skills, run_skill, save_skill, test_skill, validate
from cheerio.__main__ import main


GOOD = {"name": "double_number", "description": "Double a number represented as text", "code": "def double_number(text):\n    return str(int(text) * 2)\n", "tests": [{"input": "3", "expected": "6"}, {"input": "8", "expected": "16"}]}


class SkillTests(unittest.TestCase):
    def test_validate_execute_and_tests(self):
        self.assertEqual(run_skill(GOOD, "7"), "14")
        self.assertTrue(all(x["pass"] for x in test_skill(GOOD)))

    def test_rejects_unsafe_code(self):
        for code in ["import os\ndef double_number(text): return text", "def double_number(text):\n    return open(text).read()", "def double_number(text):\n    return text.__class__", "def double_number(text):\n    return __import__('os')", "def double_number(text):\n    return 2 ** 100000000"]:
            with self.subTest(code=code), self.assertRaises(ValueError):
                validate({**GOOD, "code": code})

    def test_failed_test(self):
        self.assertFalse(test_skill({**GOOD, "tests": [{"input": "3", "expected": "9"}]})[0]["pass"])

    def test_save_load_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            saved = save_skill(GOOD, folder)
            self.assertTrue(saved.exists())
            self.assertEqual(load_skills(folder)[0].forward("4"), "8")
            with self.assertRaises(ValueError):
                save_skill(GOOD, folder)

    def test_cli_cannot_be_approved_by_model(self):
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"CHEERIO_SKILLS_DIR": d}), patch("cheerio.__main__.draft_skill", return_value=GOOD), patch("cheerio.__main__.saved_local_model", return_value="installed:latest"), patch("cheerio.__main__.assess_local", return_value={"confidence": 0.95, "concerns": [], "suggested_tests": []}), patch("builtins.input", return_value="no"):
            self.assertEqual(main(["skill", "double a number"]), 0)
            self.assertEqual(list(Path(d).glob("*.json")), [])
        with tempfile.TemporaryDirectory() as d, patch.dict("os.environ", {"CHEERIO_SKILLS_DIR": d}), patch("cheerio.__main__.draft_skill", return_value=GOOD), patch("cheerio.__main__.saved_local_model", return_value="installed:latest"), patch("cheerio.__main__.assess_local", return_value={"confidence": 0.95, "concerns": [], "suggested_tests": []}), patch("builtins.input", return_value="APPROVE"):
            self.assertEqual(main(["skill", "double a number"]), 0)
            self.assertEqual(len(list(Path(d).glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
