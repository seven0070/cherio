import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cheerio import startup as s

class StartupTests(unittest.TestCase):
    def test_conservative_size(self):
        self.assertEqual(s.local_model_recommendation(None, None), 'qwen3.5:2b')
        self.assertEqual(s.local_model_recommendation(8000, 16000), 'qwen3.5:4b')
        self.assertEqual(s.local_model_recommendation(24000, 32000), 'qwen3.5:9b')

    def test_no_auto_pull_without_exact_approval(self):
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            return type('Result', (), {'stdout': 'NAME ID SIZE\n'})()
        with patch.object(s.shutil, 'which', return_value='ollama'), patch.object(s, '_vram_mb', return_value=8000), patch.object(s, '_ram_mb', return_value=16000):
            self.assertEqual(s.setup_local(input_fn=lambda _: 'no', output=lambda _: None, runner=runner), 0)
        self.assertEqual(calls, [['ollama', 'list']])

    def test_gateway_preflight_and_local_fallback(self):
        env = {'CHEERIO_GATEWAY_MODE': 'omniroute', 'CHEERIO_OMNIROUTE_KEY': 'hidden'}
        cfg, source = s.select_config(env=env, check=lambda url, key, timeout: {'data':[{'id':'auto'}]})
        self.assertEqual((cfg['model_id'], cfg['api_base'], cfg['api_key']), ('auto', s.GATEWAY, 'hidden'))
        self.assertIn('preflight', source)
        cfg, source = s.select_config(env=env, check=lambda url, key, timeout: (_ for _ in ()).throw(ValueError('down')))
        self.assertEqual(cfg['api_base'], s.DEFAULT_API_BASE)
        self.assertNotIn('hidden', repr(cfg))
        self.assertIn('fallback', source)

    def test_update_read_only_and_strict_url(self):
        self.assertEqual(s.check_update(fetch=lambda _: {'tag_name':'v0.2.0','html_url':'https://github.com/seven0070/cherio/releases/tag/v0.2.0'})['tag'],'v0.2.0')
        self.assertIsNone(s.check_update(fetch=lambda _: {'tag_name':'v0.2.0','html_url':'https://github.com/seven0070/cherio/releases/tag/v0.2.0.evil'}))

    def test_saved_local_model(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'settings.json'
            s.save_local_model('qwen3.5:2b',path)
            self.assertEqual(s.saved_local_model(path),'qwen3.5:2b')

if __name__ == '__main__': unittest.main()
