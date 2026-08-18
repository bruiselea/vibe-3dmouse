"""Persistent mapping between fourteen SpaceMouse inputs and target actions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .actions import ACTION_BY_KEY
from .detector import AXES, BUTTONS


CONTROLS = tuple(f"{axis}{sign}" for axis in AXES for sign in ("+", "-")) + tuple(
    name for _, name in BUTTONS
)

CONTROL_LABELS = {
    "tx+": "平行移動 X +",
    "tx-": "平行移動 X −",
    "ty+": "平行移動 Y +",
    "ty-": "平行移動 Y −",
    "tz+": "平行移動 Z +",
    "tz-": "平行移動 Z −",
    "rx+": "傾き X +",
    "rx-": "傾き X −",
    "ry+": "傾き Y +",
    "ry-": "傾き Y −",
    "rz+": "ひねり Z +",
    "rz-": "ひねり Z −",
    "button_left": "左ボタン",
    "button_right": "右ボタン",
}


def default_assignments() -> dict[str, str]:
    return {
        "tx+": "analog_right",
        "tx-": "analog_left",
        "ty+": "analog_down",
        "ty-": "new_chat",
        "tz+": "mic_ptt",
        "tz-": "send",
        "rx+": "agent_next",
        "rx-": "agent_previous",
        "ry+": "encoder_cw",
        "ry-": "encoder_ccw",
        "rz+": "fast",
        "rz-": "analog_up",
        "button_left": "ng",
        "button_right": "ok",
    }


@dataclass(slots=True)
class MappingConfig:
    press_threshold: int = 180
    release_threshold: int = 90
    dominance_ratio: float = 1.25
    activation_ms: float = 40.0
    assignments: dict[str, str] = field(default_factory=default_assignments)

    def validate(self) -> None:
        if self.press_threshold <= 0:
            raise ValueError("DOWN閾値は正の値にしてください")
        if self.release_threshold < 0 or self.release_threshold >= self.press_threshold:
            raise ValueError("UP閾値は0以上かつDOWN閾値未満にしてください")
        if self.dominance_ratio < 1.0:
            raise ValueError("優先軸比率は1.0以上にしてください")
        if self.activation_ms < 0:
            raise ValueError("入力継続時間は0以上にしてください")
        unknown_controls = set(self.assignments) - set(CONTROLS)
        if unknown_controls:
            raise ValueError(f"不明な入力: {', '.join(sorted(unknown_controls))}")
        unknown_actions = set(self.assignments.values()) - set(ACTION_BY_KEY)
        if unknown_actions:
            raise ValueError(f"不明な操作: {', '.join(sorted(unknown_actions))}")
        for control in CONTROLS:
            self.assignments.setdefault(control, "unassigned")

    def save(self, path: Path) -> None:
        self.validate()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "press_threshold": self.press_threshold,
            "release_threshold": self.release_threshold,
            "dominance_ratio": self.dominance_ratio,
            "activation_ms": self.activation_ms,
            "assignments": self.assignments,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "MappingConfig":
        payload = json.loads(path.read_text(encoding="utf-8"))
        config = cls(
            press_threshold=int(payload.get("press_threshold", 180)),
            release_threshold=int(payload.get("release_threshold", 90)),
            dominance_ratio=float(payload.get("dominance_ratio", 1.25)),
            activation_ms=float(payload.get("activation_ms", 40.0)),
            assignments=dict(payload.get("assignments", {})),
        )
        config.validate()
        return config
