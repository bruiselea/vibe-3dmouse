import tempfile
import unittest
from pathlib import Path

from spacemouse_input.release_settings import ReleaseSettings


class ReleaseSettingsTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            ReleaseSettings(auto_link_enabled=False, start_with_windows=False).save(path)
            loaded = ReleaseSettings.load(path)
        self.assertFalse(loaded.auto_link_enabled)
        self.assertFalse(loaded.start_with_windows)

    def test_invalid_file_uses_safe_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not-json", encoding="utf-8")
            loaded = ReleaseSettings.load(path)
        self.assertTrue(loaded.auto_link_enabled)
        self.assertTrue(loaded.start_with_windows)


if __name__ == "__main__":
    unittest.main()
