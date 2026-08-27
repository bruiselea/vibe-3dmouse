"""Per-user Windows login startup registration for the release app."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "VibeSpaceMouseBridgeForCodex"


def build_startup_command(executable: str | Path | None = None, *, frozen: bool | None = None) -> str:
    """Return the quiet background command stored in the HKCU Run key."""

    executable_path = Path(executable or sys.executable).resolve()
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        return subprocess.list2cmdline([str(executable_path), "--background"])

    pythonw = executable_path.with_name("pythonw.exe")
    launcher = pythonw if pythonw.exists() else executable_path
    source_entry = Path(__file__).resolve().parent.parent / "release_main.py"
    return subprocess.list2cmdline([str(launcher), str(source_entry), "--background"])


def set_start_with_windows(enabled: bool, command: str | None = None) -> None:
    """Create or remove the current user's login startup entry."""

    if os.name != "nt":
        return
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(
                key,
                RUN_VALUE,
                0,
                winreg.REG_SZ,
                command or build_startup_command(),
            )
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass


def is_start_with_windows_enabled() -> bool:
    if os.name != "nt":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, RUN_VALUE)
        return bool(value)
    except FileNotFoundError:
        return False
