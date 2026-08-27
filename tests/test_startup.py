import unittest

from spacemouse_input.startup import build_startup_command


class StartupTests(unittest.TestCase):
    def test_frozen_command_uses_background_switch(self):
        command = build_startup_command(r"C:\Program Files\Vibe App\app.exe", frozen=True)
        self.assertEqual(command, '"C:\\Program Files\\Vibe App\\app.exe" --background')

    def test_source_command_uses_absolute_entry_script(self):
        command = build_startup_command(r"E:\Project\.venv\Scripts\python.exe", frozen=False)
        self.assertIn("release_main.py", command)
        self.assertIn("--background", command)
        self.assertNotIn(" -m ", command)


if __name__ == "__main__":
    unittest.main()
