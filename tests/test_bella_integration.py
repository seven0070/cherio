import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cheerio.__main__ import main as cheerio_main


class BellaIntegrationTests(unittest.TestCase):
    def test_voice_cannot_approve_transcribed_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            inputs = iter(['/voice', '/exit'])
            with patch.dict('os.environ', {'BELLA_DB': str(Path(temp) / 'bella.db')}):
                with patch('builtins.input', side_effect=lambda prompt='': next(inputs)), patch('bella.voice.listen', return_value='/approve fakeid'), redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(cheerio_main(['bella']), 0)
                self.assertIn('Voice commands are disabled', out.getvalue())


    def test_entrypoint_exits_without_model(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict('os.environ', {'BELLA_DB': str(Path(temp) / 'bella.db')}):
                with patch('builtins.input', return_value='/exit'), redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(cheerio_main(['bella']), 0)
                self.assertIn('Bella', out.getvalue())


if __name__ == '__main__':
    unittest.main()
