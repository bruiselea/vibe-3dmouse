"""Dispatch SpaceMouse digital edges as native Codex Micro HID events."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import sleep
from typing import Protocol

from .actions import ACTION_BY_KEY
from .detector import InputEvent


class CodexSender(Protocol):
    def send_key(self, key: str, act: int) -> None: ...

    def send_joystick(self, angle: float, distance: float) -> None: ...


JOYSTICK_ANGLES = {
    "analog_right": 0.0,
    "analog_down": 0.25,
    "analog_left": 0.5,
    "analog_up": 0.75,
}


@dataclass(slots=True)
class ActionDispatcher:
    sender: CodexSender
    agent_index: int = 0
    report_spacing: float = 0.012
    _held_codes: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def dispatch(self, event: InputEvent, action_key: str) -> list[str]:
        if action_key == "unassigned":
            return []
        if action_key not in ACTION_BY_KEY:
            raise ValueError(f"unknown action: {action_key}")

        if action_key in ("agent_previous", "agent_next"):
            if not event.pressed:
                return []
            step = -1 if action_key == "agent_previous" else 1
            self.agent_index = (self.agent_index + step) % 6
            code = f"AG{self.agent_index:02d}"
            self.sender.send_key(code, 1)
            sleep(self.report_spacing)
            self.sender.send_key(code, 0)
            return [code]

        if action_key in ("encoder_cw", "encoder_ccw"):
            if not event.pressed:
                return []
            code = "ENC_CW" if action_key == "encoder_cw" else "ENC_CC"
            self.sender.send_key(code, 2)
            return [code]

        if action_key in JOYSTICK_ANGLES:
            self.sender.send_joystick(
                JOYSTICK_ANGLES[action_key],
                1.0 if event.pressed else 0.0,
            )
            return [action_key]

        codes = ACTION_BY_KEY[action_key].codes
        if event.pressed:
            self._held_codes[event.control] = codes
        else:
            codes = self._held_codes.pop(event.control, codes)
        act = 1 if event.pressed else 0
        for index, code in enumerate(codes):
            if index:
                sleep(self.report_spacing)
            self.sender.send_key(code, act)
        return list(codes)

    def release_all(self) -> None:
        for codes in self._held_codes.values():
            for index, code in enumerate(codes):
                if index:
                    sleep(self.report_spacing)
                self.sender.send_key(code, 0)
        self._held_codes.clear()
