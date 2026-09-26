import unittest
from unittest.mock import patch
from bella.voice import say


class VoiceTests(unittest.TestCase):
    def test_missing_optional_tts_is_actionable(self):
        with patch.dict('sys.modules', {'pyttsx3': None}):
            with self.assertRaisesRegex(RuntimeError, 'requirements-voice.txt'):
                say('hi')


if __name__ == '__main__':
    unittest.main()
