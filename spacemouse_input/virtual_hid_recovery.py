"""Trigger the privileged virtual-HID recovery task without opening a console."""

from __future__ import annotations

import subprocess


RECOVERY_TASK_NAME = "VibeSpaceMouseBridge-EnsureVirtualHid"


def request_virtual_hid_recovery() -> bool:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["schtasks.exe", "/run", "/tn", RECOVERY_TASK_NAME],
            capture_output=True,
            creationflags=creationflags,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
