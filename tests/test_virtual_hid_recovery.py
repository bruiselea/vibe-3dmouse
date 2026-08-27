import unittest
from unittest.mock import patch

from spacemouse_input.virtual_hid_recovery import request_virtual_hid_recovery


class VirtualHidRecoveryTests(unittest.TestCase):
    @patch("spacemouse_input.virtual_hid_recovery.subprocess.run")
    def test_successful_task_start_returns_true(self, run):
        run.return_value.returncode = 0
        self.assertTrue(request_virtual_hid_recovery())
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["schtasks.exe", "/run"])

    @patch("spacemouse_input.virtual_hid_recovery.subprocess.run")
    def test_failed_task_start_returns_false(self, run):
        run.return_value.returncode = 1
        self.assertFalse(request_virtual_hid_recovery())
