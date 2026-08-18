"""Windows process probes used by the Codex-linked release controller."""

from __future__ import annotations

import subprocess


def process_is_running(image_name: str) -> bool:
    result = subprocess.run(
        ["tasklist.exe", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return image_name.casefold() in result.stdout.casefold()


def codex_is_running() -> bool:
    return process_is_running("codex.exe")

