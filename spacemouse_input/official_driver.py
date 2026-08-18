"""Temporarily stop and restart the user-mode 3DxWare driver.

The physical HID device remains enabled so the SpaceMouse bridge can still read
it.  This calls the same executable and arguments as 3Dconnexion's installed
"Stop 3DxWare" and "Start 3DxWare" shortcuts.
"""

from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from time import monotonic, sleep
from typing import Iterator


PROCESS_NAME = "3DxService.exe"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_3dxservice() -> Path:
    candidates: list[Path] = []
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(variable)
        if root:
            candidates.append(
                Path(root) / "3Dconnexion" / "3DxWare" / "3DxWinCore" / PROCESS_NAME
            )
            candidates.append(
                Path(root) / "3Dconnexion" / "3DxWare" / "3DxWinCore64" / PROCESS_NAME
            )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("3DxService.exe が見つかりません。3DxWareの導入状態を確認してください。")


def driver_is_running() -> bool:
    result = subprocess.run(
        ["tasklist.exe", "/FI", f"IMAGENAME eq {PROCESS_NAME}", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=NO_WINDOW,
    )
    return PROCESS_NAME.casefold() in result.stdout.casefold()


def _wait_for_state(running: bool, timeout: float = 5.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if driver_is_running() is running:
            return True
        sleep(0.1)
    return driver_is_running() is running


def pause_driver() -> bool:
    """Stop 3DxWare and return whether it was running before this call."""

    was_running = driver_is_running()
    if not was_running:
        return False
    executable = find_3dxservice()
    subprocess.run(
        [str(executable), "-quiet", "-shutdown"],
        cwd=executable.parent,
        check=True,
        creationflags=NO_WINDOW,
    )
    if not _wait_for_state(False):
        raise RuntimeError("3DxWareを停止できませんでした。")
    return True


def resume_driver() -> bool:
    """Start 3DxWare and return True when a new process was launched."""

    executable = find_3dxservice()
    if driver_is_running():
        return False
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | NO_WINDOW
    subprocess.Popen(
        [str(executable)],
        cwd=executable.parent,
        creationflags=creationflags,
        close_fds=True,
    )
    if not _wait_for_state(True):
        raise RuntimeError("3DxWareを再開できませんでした。")
    return True


def resume_driver_if_installed() -> bool:
    """Resume 3DxWare when installed, otherwise behave as a harmless no-op."""

    if driver_is_running():
        return False
    try:
        find_3dxservice()
    except FileNotFoundError:
        return False
    return resume_driver()


@contextmanager
def temporarily_paused(enabled: bool) -> Iterator[bool]:
    """Restore 3DxWare on exit only when this context stopped it."""

    stopped_here = pause_driver() if enabled else False
    try:
        yield stopped_here
    finally:
        if stopped_here:
            resume_driver()
