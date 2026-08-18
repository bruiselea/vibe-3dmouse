import subprocess
import unittest
from unittest.mock import patch

from spacemouse_input.__main__ import build_parser
from spacemouse_input.official_driver import driver_is_running, pause_driver, temporarily_paused


class OfficialDriverTests(unittest.TestCase):
    @patch("spacemouse_input.official_driver.subprocess.run")
    def test_status_probe_never_opens_a_console_window(self, run):
        run.return_value.stdout = '"INFO: No tasks are running"'

        self.assertFalse(driver_is_running())

        self.assertEqual(
            run.call_args.kwargs["creationflags"],
            getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def test_bridge_pauses_3dx_by_default(self):
        args = build_parser().parse_args(["bridge"])
        self.assertTrue(args.pause_3dx)

    def test_bridge_can_explicitly_keep_3dx_running(self):
        args = build_parser().parse_args(["bridge", "--keep-3dx"])
        self.assertFalse(args.pause_3dx)

    @patch("spacemouse_input.official_driver.resume_driver")
    @patch("spacemouse_input.official_driver.pause_driver", return_value=True)
    def test_temporarily_paused_restores_driver_it_stopped(self, pause, resume):
        with temporarily_paused(True) as stopped:
            self.assertTrue(stopped)
        pause.assert_called_once_with()
        resume.assert_called_once_with()

    @patch("spacemouse_input.official_driver.resume_driver")
    @patch("spacemouse_input.official_driver.pause_driver", return_value=False)
    def test_temporarily_paused_does_not_start_previously_stopped_driver(self, pause, resume):
        with temporarily_paused(True) as stopped:
            self.assertFalse(stopped)
        resume.assert_not_called()

    @patch("spacemouse_input.official_driver.pause_driver")
    def test_disabled_context_does_not_touch_driver(self, pause):
        with temporarily_paused(False) as stopped:
            self.assertFalse(stopped)
        pause.assert_not_called()

    @patch("spacemouse_input.official_driver.find_3dxservice")
    @patch("spacemouse_input.official_driver.driver_is_running", return_value=False)
    def test_missing_stopped_3dxware_is_a_no_op(self, _running, find):
        self.assertFalse(pause_driver())
        find.assert_not_called()


if __name__ == "__main__":
    unittest.main()
