import tempfile
import unittest
from pathlib import Path
from cheerio.memory import Memory
from cheerio.skill_scores import rank_skills

class ScoreTests(unittest.TestCase):
    def test_failures_rank_above_successes(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory(Path(d)/'memory.db')
            m.append('skill_used','good','ok')
            m.append('skill_use_failed','bad','ValueError')
            ranked=rank_skills(m)
            self.assertEqual(ranked[0]['name'],'bad')
            self.assertEqual(ranked[0]['last_failure'],'ValueError')
            self.assertEqual(ranked[1]['failure'],0)
