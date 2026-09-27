"""Offline tests of the bounded model discovery path."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cheerio import model_discovery as d


class DiscoveryTests(unittest.TestCase):
    def test_provider_host_not_key_guess(self):
        self.assertEqual(d.provider_for('https://api.openai.com/v1'), 'openai')
        self.assertEqual(d.provider_for('http://localhost:1234/v1'), 'lm-studio')
        self.assertEqual(d.provider_for('https://example.com/v1'), 'unknown OpenAI-compatible')

    def test_remote_requires_opt_in_and_does_not_print_key(self):
        results = d.inspect_endpoints(env={'CHEERIO_API_BASE': 'https://api.openai.com/v1', 'CHEERIO_API_KEY': 'top-secret'})
        self.assertIn('remote skipped', str(results))
        self.assertNotIn('top-secret', str(results))

    def test_url_credentials_are_redacted(self):
        results = d.inspect_endpoints(['https://name:secret@example.com/v1'], env={})
        self.assertNotIn('secret', str(results))
        self.assertIn('invalid', str(results))

    def test_list_and_declared_caps(self):
        def fake(url, key=None, data=None, timeout=2):
            if url.endswith('/models'):
                return {'data': [{'id': 'my-model'}]}
            return {'capabilities': ['tools', 'vision'], 'model_info': {'a.context_length': 8192}}
        with patch.object(d, '_request', side_effect=fake):
            item = d.inspect_endpoints(env={})[0]['models'][0]
        self.assertEqual(item['tool_calling'], 'declared by runtime')
        self.assertEqual(item['vision'], 'declared by runtime')
        self.assertEqual(item['embedding'], 'unknown')
        self.assertEqual(item['context_length'], 8192)

    def test_explicit_folder_only_and_no_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'model.gguf').write_bytes(b'not a model')
            (base / '.hidden').mkdir()
            (base / '.hidden' / 'private.gguf').write_bytes(b'no')
            self.assertEqual(d.find_gguf([base]), [str(base / 'model.gguf')])

    def test_key_only_to_configured_remote(self):
        calls = []
        def fake(url, key=None, data=None, timeout=2):
            calls.append((url, key))
            return {'data': []}
        with patch.object(d, '_request', side_effect=fake):
            d.inspect_endpoints(['https://other.example/v1'], include_remote=True,
                                env={'CHEERIO_API_BASE': 'https://api.openai.com/v1', 'CHEERIO_API_KEY': 'secret'})
        self.assertEqual([key for url, key in calls if url.startswith('https://other.example')], [None])
        self.assertEqual([key for url, key in calls if url.startswith('https://api.openai.com')], ['secret'])


if __name__ == '__main__':
    unittest.main()
