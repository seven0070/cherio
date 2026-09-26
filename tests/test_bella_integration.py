import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cheerio.__main__ import main as cheerio_main


class BellaIntegrationTests(unittest.TestCase):
    def test_entrypoint_exits_without_model(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict('os.environ', {'BELLA_DB': str(Path(temp) / 'bella.db')}):
                with patch('builtins.input', return_value='/exit'), redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(cheerio_main(['bella']), 0)
                self.assertIn('Bella', out.getvalue())


if __name__ == '__main__':
    unittest.main()
