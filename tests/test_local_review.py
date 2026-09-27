import json
import unittest
from unittest.mock import patch

from cheerio.local_review import _local_endpoint, assess_local, decide
from cheerio.__main__ import main

SPEC = {"name": "double_number", "description": "Double numeric text", "code": "def double_number(text):\n    return str(int(text)*2)", "tests": [{"input": "3", "expected": "6"}]}
PASS = [{"input": "3", "expected": "6", "actual": "6", "pass": True}]
GOOD = {"confidence": .91, "concerns": [], "suggested_tests": []}


class LocalReviewTests(unittest.TestCase):
    def test_deterministic_gate(self):
        self.assertEqual(decide(PASS, GOOD)[0], "ASK_USER")
        self.assertEqual(decide(PASS, GOOD, False)[0], "STOP")
        self.assertEqual(decide([{**PASS[0], "pass": False}], GOOD)[0], "STOP")
        self.assertEqual(decide(PASS, None)[0], "VERIFY")
        self.assertEqual(decide(PASS, {**GOOD, "concerns": ["Might fail on decimal"]})[0], "VERIFY")
        self.assertEqual(decide(PASS, {**GOOD, "suggested_tests": ["test negative"]})[0], "VERIFY")
        self.assertEqual(decide(PASS, {**GOOD, "confidence": True})[0], "VERIFY")
        self.assertEqual(decide(PASS, {**GOOD, "confidence": 1.1})[0], "VERIFY")
        self.assertEqual(decide(PASS, {**GOOD, "directive": "APPROVE"})[0], "VERIFY")

    def test_loopback_only_no_remote_or_redirect_hop(self):
        for url in ["https://api.example.com/v1", "http://evil.example/v1", "http://127.0.0.1.evil/v1", "http://user:pw@127.0.0.1:11434/v1", "http://[::1]:11434/v1", "http://127.0.0.1:11434/v1/../../secret"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                _local_endpoint({"api_base": url})
        self.assertEqual(_local_endpoint({"api_base": "http://127.0.0.1:11434/v1"}), "http://127.0.0.1:11434/v1")

    def test_gateway_on_loopback_is_not_local_model(self):
        with self.assertRaises(ValueError):
            assess_local(SPEC, PASS, {"api_base": "http://127.0.0.1:20128/v1", "model_id": "auto"}, opener=lambda *a, **k: self.fail("network called"))

    def test_local_assessment_never_directly_installs(self):
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, n): return json.dumps({"choices": [{"message": {"content": json.dumps(GOOD)}}]}).encode()
        def opener(req, timeout):
            self.assertEqual(req.full_url, "http://localhost:11434/v1/chat/completions")
            self.assertEqual(json.loads(req.data)["model"], "local:latest")
            return Reply()
        result = assess_local(SPEC, PASS, {"api_base": "http://localhost:11434/v1", "model_id": "local:latest"}, opener=opener)
        self.assertEqual(decide(PASS, result)[0], "ASK_USER")

    def test_new_skill_review_unavailable_prevents_save(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ', {'CHEERIO_SKILLS_DIR': d}, clear=False), patch('cheerio.__main__.draft_skill', return_value=SPEC), patch('cheerio.__main__.saved_local_model', return_value='installed:latest'), patch('cheerio.__main__.assess_local', side_effect=ValueError('remote')), patch('builtins.input') as prompt:
            self.assertEqual(main(['skill', 'double a number']), 0)
            prompt.assert_not_called()
            self.assertEqual(list(Path(d).glob('*.json')), [])

    def test_review_unavailable_never_prompts_approval_or_installs(self):
        import tempfile
        from pathlib import Path
        from cheerio.memory import Memory
        from cheerio.skills import save_skill
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            save_skill(SPEC, folder)
            Memory(folder / 'memory.db').append('skill_use_failed', SPEC['name'], 'failed')
            fixed = {**SPEC, 'tests': [*SPEC['tests'], {'input': '4', 'expected': '8'}]}
            with patch.dict('os.environ', {'CHEERIO_SKILLS_DIR': d, 'CHEERIO_MEMORY_DB': str(folder/'memory.db')}, clear=False), patch('cheerio.__main__.draft_skill', return_value=fixed), patch('cheerio.__main__.saved_local_model', return_value='installed:latest'), patch('cheerio.improve.draft_skill', return_value=fixed), patch('cheerio.__main__.assess_local', side_effect=ValueError('remote')), patch('builtins.input') as prompt:
                self.assertEqual(main(['fix-skill', SPEC['name']]), 0)
                prompt.assert_not_called()
            self.assertEqual(json.loads((folder / (SPEC['name'] + '.json')).read_text())['tests'], SPEC['tests'])
            self.assertTrue((folder / (SPEC['name'] + '.proposal.json')).exists())

if __name__ == '__main__': unittest.main()
