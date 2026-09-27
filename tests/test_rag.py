import tempfile
import unittest
from pathlib import Path
from cheerio.rag import index_folder, search, forget_folder, build_rag_tool

class RagTests(unittest.TestCase):
    def test_index_search_refresh_and_forget(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'docs'; root.mkdir()
            db = Path(d) / 'index.db'
            (root/'notes.md').write_text('The blue oyster project has a Saturday deadline', encoding='utf-8')
            (root/'ignored.py').write_text('blue oyster secret', encoding='utf-8')
            self.assertEqual(index_folder(root, db)['files'], 1)
            matches = search('oyster', db)
            self.assertEqual(len(matches), 1)
            self.assertIn('notes.md', matches[0]['path'])
            self.assertEqual(search('nonexistentword', db), [])
            (root/'notes.md').write_text('The cobalt project changed', encoding='utf-8')
            index_folder(root, db)
            self.assertEqual(search('oyster', db), [])
            self.assertTrue(search('cobalt', db))
            forget_folder(root, db)
            self.assertEqual(search('cobalt', db), [])

    def test_tool_without_index(self):
        with tempfile.TemporaryDirectory() as d:
            from unittest.mock import patch
            with patch.dict('os.environ', {'CHEERIO_RAG_DB': str(Path(d)/'missing.db')}):
                self.assertIn('No indexed', build_rag_tool().forward('test'))
