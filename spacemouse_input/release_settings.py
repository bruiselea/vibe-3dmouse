"""Small per-user settings document for the release shell."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class ReleaseSettings:
    auto_link_enabled: bool = True
    start_with_windows: bool = True

    @classmethod
    def load(cls, path: Path) -> "ReleaseSettings":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return cls()
        return cls(
            auto_link_enabled=bool(payload.get("auto_link_enabled", True)),
            start_with_windows=bool(payload.get("start_with_windows", True)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"version": 1, **asdict(self)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
