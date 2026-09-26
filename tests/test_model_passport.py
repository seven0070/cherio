"""Offline exam/router tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cheerio import model_passport as p


class PassportTests(unittest.TestCase):
    def test_exam_three_calls_and_unknown_vision(self):
        responses = iter([
            ({'choices': [{'message': {'tool_calls': [{'function': {'name': 'ping'}}]}}]}, 1),
            ({'choices': [{'message': {'content': '{"ok":true}'}}], 'usage': {'completion_tokens': 20}}, 2),
            ({'choices': [{'message': {'content': '4'}}]}, 1),
        ])
        with patch.object(p, '_chat', side_effect=lambda *args, **kwargs: next(responses)):
            passport = p.examine('http://127.0.0.1:11434/v1', 'local')
        self.assertTrue(passport['exam']['tools']['passed'])
        self.assertEqual(passport['exam']['json']['tokens_per_second'], 10)
        self.assertTrue(passport['exam']['logic']['passed'])
        self.assertIsNone(passport['exam']['vision']['passed'])

    def test_no_remote_exam(self):
        with self.assertRaises(ValueError):
            p.examine('https://api.openai.com/v1', 'model')

    def test_router_excludes_failed_tools_and_feedback_changes_ranking(self):
        def item(name, good=0, bad=0, tool=True):
            return {'endpoint': 'http://127.0.0.1:11434/v1', 'model': name,
                    'exam': {'tools': {'passed': tool}, 'logic': {'passed': True}, 'json': {'passed': True}},
                    'feedback': {'good': good, 'bad': bad}}
        self.assertEqual(p.route('code', [item('a', bad=10), item('b', good=10)])['model'], 'b')
        self.assertEqual(p.route('hi', [item('a', tool=False), item('b')])['model'], 'b')
        with self.assertRaises(ValueError):
            p.route('hi', [item('a', tool=False)])

    def test_save_and_explicit_feedback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'passport.json'
            item = {'endpoint': 'http://127.0.0.1:11434/v1', 'model': 'x', 'feedback': {'good': 0, 'bad': 0}, 'exam': {}}
            p.save_passports([item], path)
            p.record_feedback(item['endpoint'], 'x', 'good', path)
            self.assertEqual(p.read_passports(path)[0]['feedback']['good'], 1)

    def test_refresh_preserves_feedback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'passport.json'
            item = {'endpoint': 'http://127.0.0.1:11434/v1', 'model': 'x', 'feedback': {'good': 2, 'bad': 0}, 'exam': {}}
            p.save_passports([item], path)
            with patch.object(p, 'inspect_endpoints', return_value=[{'endpoint': item['endpoint'], 'status': 'reachable', 'models': [{'id': 'x'}]}]), patch.object(p, 'examine', return_value={**item, 'feedback': {'good': 0, 'bad': 0}}):
                self.assertEqual(p.refresh_passports(path)[0]['feedback']['good'], 2)


if __name__ == '__main__':
    unittest.main()
