import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cheerio import cognee_memory as cm

class FakeCognee:
    class SearchType:
        CHUNKS = 'chunks'
    def __init__(self): self.calls=[]
    async def add(self, text, **kw): self.calls.append(('add', text, kw))
    async def cognify(self, **kw): self.calls.append(('cognify', kw))
    async def search(self, text, **kw): self.calls.append(('search', text, kw)); return ['local fact']

class CogneeTests(unittest.TestCase):
    def test_disabled_without_import_or_writes(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(cm.importlib,'import_module') as importing:
            with self.assertRaises(RuntimeError): cm.add_note('hello')
            importing.assert_not_called()

    def test_local_profile_rejects_cloud_provider(self):
        with patch.dict(os.environ, {'CHEERIO_COGNEE_ENABLED':'1','EMBEDDING_PROVIDER':'openai'}, clear=True), patch.object(cm.importlib,'import_module') as importing:
            with self.assertRaises(ValueError): cm.search_notes('question')
            importing.assert_not_called()

    def test_explicit_add_and_read(self):
        fake=FakeCognee()
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {'CHEERIO_COGNEE_ENABLED':'1'}, clear=True), patch.object(Path,'home',return_value=Path(home)), patch.object(cm.importlib,'import_module',return_value=fake):
            self.assertIn('processed', cm.add_note('Remember this'))
            self.assertEqual(cm.search_notes('what'), "['local fact']")
            self.assertEqual([c[0] for c in fake.calls], ['add','cognify','search'])
            self.assertEqual(os.environ['TELEMETRY_DISABLED'],'true')
            self.assertEqual(os.environ['EMBEDDING_PROVIDER'],'ollama')
