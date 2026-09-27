import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cheerio import startup as s

class StartupTests(unittest.TestCase):
    def test_setup_chooses_installed_model_without_pull(self):
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            return type('Result', (), {'stdout': 'NAME ID SIZE\ninstalled:latest xx 2GB\nother:latest yy 3GB\n'})()
        with tempfile.TemporaryDirectory() as t, patch.object(s, 'SETTINGS', Path(t)/'settings.json'), patch.object(s.shutil, 'which', return_value='ollama'), patch.object(s, '_vram_mb', return_value=8000), patch.object(s, '_ram_mb', return_value=16000), patch.object(s, 'save_local_model') as save:
            self.assertEqual(s.setup_local(input_fn=lambda _: '2', output=lambda _: None, runner=runner), 0)
            save.assert_called_once_with('other:latest')
        self.assertEqual(calls, [['ollama', 'list']])

    def test_no_installed_model_does_not_pull(self):
        def runner(args, **kwargs):
            return type('Result', (), {'stdout': 'NAME ID SIZE\n'})()
        with patch.object(s.shutil, 'which', return_value='ollama'), patch.object(s, '_vram_mb', return_value=None), patch.object(s, '_ram_mb', return_value=None):
            self.assertEqual(s.setup_local(input_fn=lambda _: '1', output=lambda _: None, runner=runner), 1)

    def test_first_chat_runs_setup_before_building_agent(self):
        from cheerio.__main__ import main
        with patch('cheerio.__main__.saved_local_model', return_value=None), patch('cheerio.__main__.setup_local', return_value=1) as setup, patch.dict('os.environ', {}, clear=True):
            self.assertEqual(main(['chat']), 1)
            setup.assert_called_once()

    def test_gateway_preflight_and_local_fallback(self):
        env = {'CHEERIO_GATEWAY_MODE': 'omniroute', 'CHEERIO_OMNIROUTE_KEY': 'hidden'}
        cfg, source = s.select_config(env=env, check=lambda url, key, timeout: {'data':[{'id':'auto'}]})
        self.assertEqual((cfg['model_id'], cfg['api_base'], cfg['api_key']), ('auto', s.GATEWAY, 'hidden'))
        self.assertIn('preflight', source)
        with patch.object(s, 'saved_local_model', return_value='installed:latest'):
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
            s.save_local_model('installed:latest',path)
            self.assertEqual(s.saved_local_model(path),'installed:latest')

if __name__ == '__main__': unittest.main()
