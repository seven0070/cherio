import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cheerio.intelligence import choose_route, complexity, plan, check_answer, world_digest, _local_chat
from cheerio.preferences import update, read, context


class IntelligenceTests(unittest.TestCase):
    def test_complexity_and_cloud_gate(self):
        self.assertEqual(complexity('hello'), 'easy')
        self.assertEqual(complexity('investigate this'), 'hard')
        with patch('cheerio.intelligence.saved_local_model', return_value='local:latest'):
            config, origin, kind = choose_route('investigate this', env={'CHEERIO_GATEWAY_MODE': 'omniroute', 'CHEERIO_OMNIROUTE_KEY': 'secret'}, check=lambda *a, **k: self.fail('network without opt-in'))
            self.assertEqual(origin, 'local')
            self.assertEqual(config['model_id'], 'local:latest')
            config, origin, kind = choose_route('investigate this', allow_cloud=True, env={'CHEERIO_GATEWAY_MODE': 'omniroute', 'CHEERIO_OMNIROUTE_KEY': 'secret'}, check=lambda *a, **k: {'data': []})
            self.assertEqual((config['model_id'], origin), ('auto', 'gateway: cloud may cost money and receive task text'))
            config, origin, kind = choose_route('hello', allow_cloud=True, env={'CHEERIO_GATEWAY_MODE': 'omniroute', 'CHEERIO_OMNIROUTE_KEY': 'secret'}, check=lambda *a, **k: self.fail('no gateway for easy'))
            self.assertEqual(origin, 'local')
            with self.assertRaises(ValueError):
                choose_route('investigate', env={'OPENAI_API_BASE': 'https://bad.example/v1', 'CHEERIO_API_BASE': 'https://bad.example/v1'})

    def test_think_harder_local_only_and_advisory(self):
        config = {'api_base': 'http://127.0.0.1:11434/v1', 'model_id': 'local:latest'}
        def fake(url, **kw):
            self.assertEqual(url, 'http://127.0.0.1:11434/v1/chat/completions')
            self.assertNotIn('tools', kw['data'])
            return {'choices': [{'message': {'content': 'Check a source'}}]}
        self.assertIn('verify current facts', plan('investigate', config, send=lambda *a, **k: self.fail('no planning network')))
        self.assertEqual(check_answer('question', 'answer', config, send=fake), 'Check a source')
        with self.assertRaises(ValueError):
            _local_chat({'api_base': 'http://127.0.0.1:20128/v1', 'model_id': 'auto'}, 'x', send=fake)
        with self.assertRaises(ValueError):
            _local_chat({'api_base': 'http://user:pw@localhost:11434/v1', 'model_id': 'x'}, 'x', send=fake)

    def test_preferences_explicit_local_forget(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'preferences.json'
            self.assertEqual(read(path), {})
            update('project', 'Cheerio', path)
            self.assertIn('Cheerio', context(path))
            update('project', None, path)
            self.assertEqual(read(path), {})
            with self.assertRaises(ValueError): update('../other', 'oops', path)

    def test_think_harder_refuses_gateway(self):
        from cheerio.__main__ import main
        with patch.dict('os.environ', {'CHEERIO_GATEWAY_MODE': 'omniroute'}, clear=False):
            self.assertEqual(main(['web', 'find a source', '--think-harder']), 2)
        self.assertEqual(main(['web', 'find a source', '--smart-route', '--allow-cloud', '--think-harder']), 2)

    def test_world_digest_explicit_headlines_with_sources(self):
        rss = b'<rss><channel><item><title>World event</title><link>https://www.bbc.com/news/one</link><pubDate>today</pubDate></item><item><title>Bad</title><link>javascript:alert(1)</link></item></channel></rss>'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'digest.json'
            digest = world_digest(fetch=lambda url: rss, path=path)
            self.assertEqual(len(digest['items']), 1)
            self.assertEqual(digest['items'][0]['url'], 'https://www.bbc.com/news/one')
            self.assertEqual(json.loads(path.read_text())['items'], digest['items'])
            with self.assertRaises(ValueError): world_digest(fetch=lambda url: b'<rss/>', path=path)
            self.assertEqual(json.loads(path.read_text())['items'], digest['items'])

if __name__ == '__main__': unittest.main()
