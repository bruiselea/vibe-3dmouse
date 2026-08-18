"""Convert continuous SpaceMouse state into fourteen digital inputs."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from .reports import SpaceMouseState


AXES = ("tx", "ty", "tz", "rx", "ry", "rz")
BUTTONS = ((0, "button_left"), (1, "button_right"))


@dataclass(frozen=True, slots=True)
class InputEvent:
    control: str
    pressed: bool
    value: int
    timestamp: float

    @property
    def edge(self) -> str:
        return "DOWN" if self.pressed else "UP"


class InputDetector:
    """Dominant-axis detector with hysteresis for 12 directions and 2 buttons.

    An axis direction becomes active at ``press_threshold`` and remains active
    until it falls below ``release_threshold``. Positive and negative directions
    are tracked separately. Only the strongest axis can become active, and it
    must remain dominant briefly. Once active, that axis is locked until the
    control returns near centre. Buttons remain independent.
    """

    def __init__(
        self,
        press_threshold: int = 180,
        release_threshold: int = 90,
        dominance_ratio: float = 1.25,
        activation_delay: float = 0.040,
    ) -> None:
        if press_threshold <= 0:
            raise ValueError("press_threshold must be positive")
        if release_threshold < 0 or release_threshold >= press_threshold:
            raise ValueError("release_threshold must be >= 0 and below press_threshold")
        if dominance_ratio < 1.0:
            raise ValueError("dominance_ratio must be at least 1.0")
        if activation_delay < 0:
            raise ValueError("activation_delay must not be negative")
        self.press_threshold = press_threshold
        self.release_threshold = release_threshold
        self.dominance_ratio = dominance_ratio
        self.activation_delay = activation_delay
        self._active = {f"{axis}{sign}": False for axis in AXES for sign in ("+", "-")}
        self._active.update({name: False for _, name in BUTTONS})
        self._active_axis_control: str | None = None
        self._candidate: str | None = None
        self._candidate_since = 0.0

    @property
    def active_controls(self) -> tuple[str, ...]:
        return tuple(name for name, active in self._active.items() if active)

    def update(self, state: SpaceMouseState, timestamp: float | None = None) -> list[InputEvent]:
        now = monotonic() if timestamp is None else timestamp
        events: list[InputEvent] = []

        events.extend(self._update_axes(state, now))

        for bit, name in BUTTONS:
            pressed = bool(state.buttons & (1 << bit))
            if pressed != self._active[name]:
                self._active[name] = pressed
                events.append(InputEvent(name, pressed, 1 if pressed else 0, now))

        return events

    def _update_axes(self, state: SpaceMouseState, timestamp: float) -> list[InputEvent]:
        if self._active_axis_control is not None:
            control = self._active_axis_control
            axis = control[:2]
            raw_value = getattr(state, axis)
            signed_magnitude = raw_value if control.endswith("+") else -raw_value
            if signed_magnitude >= self.release_threshold:
                return []
            self._active[control] = False
            self._active_axis_control = None
            self._candidate = None
            return [InputEvent(control, False, raw_value, timestamp)]

        ranked = sorted(
            ((abs(getattr(state, axis)), axis, getattr(state, axis)) for axis in AXES),
            reverse=True,
        )
        strongest, axis, raw_value = ranked[0]
        second_strongest = ranked[1][0]
        if strongest < self.press_threshold or (
            second_strongest > 0 and strongest < second_strongest * self.dominance_ratio
        ):
            self._candidate = None
            return []

        control = f"{axis}{'+' if raw_value >= 0 else '-'}"
        if control != self._candidate:
            self._candidate = control
            self._candidate_since = timestamp
            if self.activation_delay > 0:
                return []
        elif timestamp - self._candidate_since < self.activation_delay:
            return []

        self._candidate = None
        self._active[control] = True
        self._active_axis_control = control
        return [InputEvent(control, True, raw_value, timestamp)]
