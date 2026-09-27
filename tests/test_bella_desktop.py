import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bella.actions import approve
from bella.core import Store
from bella.desktop import VoiceCapture


class DesktopBoundaryTests(unittest.TestCase):
    def test_same_safety_boundary_interrupted_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'data.db')
            ident = store.propose('look up the weather')
            def fail(checkout, request):
                self.assertEqual(request['schema'], 'bella.cheerio.task.v1')
                self.assertEqual(store.task(ident)['state'], 'running')
                raise RuntimeError('worker died')
            with self.assertRaises(RuntimeError):
                approve(store, ident, Path(folder), worker=fail)
            self.assertEqual(store.task(ident)['state'], 'interrupted')
            with self.assertRaisesRegex(ValueError, 'not pending'):
                approve(store, ident, Path(folder), worker=fail)
            store.close()

    def test_voice_capture_has_no_automatic_submit(self):
        # Transcription returns data only; GUI stages it in the composer.
        self.assertFalse(hasattr(VoiceCapture, 'approve'))


if __name__ == '__main__':
    unittest.main()

class PackagingTests(unittest.TestCase):
    def test_console_entry_points(self):
        from pathlib import Path
        content = (Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text()
        for name in ('cheerio =', 'bella =', 'bella-desktop ='):
            self.assertIn(name, content)

    def test_frozen_desktop_handoff_stays_blocked(self):
        from pathlib import Path
        from unittest.mock import patch
        from bella.worker import run
        import sys
        with patch.object(sys, 'frozen', True, create=True):
            with self.assertRaisesRegex(RuntimeError, 'source install'):
                run(Path('.'), {'schema': 'bella.cheerio.task.v1', 'approval': 'explicit-local-user', 'goal': 'x'})
