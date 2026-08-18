"""Shared SpaceMouse-to-Codex bridge runtime for CLI and GUI."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
from time import monotonic

from .bridge import ActionDispatcher
from .detector import InputDetector, InputEvent
from .device import SpaceMouseDevice, enumerate_devices
from .mapping import MappingConfig
from .official_driver import temporarily_paused
from .protocol import CodexMicroDevice, enumerate_codex_devices
from .reports import SpaceMouseState, parse_report


StateCallback = Callable[[SpaceMouseState], None]
EventCallback = Callable[[InputEvent, str, list[str]], None]
StatusCallback = Callable[[str], None]


def run_bridge(
    config: MappingConfig,
    *,
    stop_event: Event | None = None,
    pause_3dx: bool = True,
    seconds: float | None = None,
    on_state: StateCallback | None = None,
    on_event: EventCallback | None = None,
    on_status: StatusCallback | None = None,
) -> None:
    """Run the bridge until stopped, optionally reporting state and events."""

    config.validate()
    spacemice = enumerate_devices()
    codex_devices = enumerate_codex_devices()
    if not spacemice:
        raise OSError("SpaceMouse Compact (256F:C635) が見つかりません。")
    if not codex_devices:
        raise OSError("Codex Micro互換HID (303A:8360) が見つかりません。")

    detector = InputDetector(
        config.press_threshold,
        config.release_threshold,
        dominance_ratio=config.dominance_ratio,
        activation_delay=config.activation_ms / 1000.0,
    )
    state = SpaceMouseState()
    deadline = monotonic() + seconds if seconds is not None else None

    with temporarily_paused(pause_3dx) as stopped_3dx:
        if on_status is not None:
            on_status("3DxWareを一時停止" if stopped_3dx else "3DxWareは停止済み")
        with (
            SpaceMouseDevice(spacemice[0]) as spacemouse,
            CodexMicroDevice(codex_devices[0]) as codex,
        ):
            dispatcher = ActionDispatcher(codex)
            if on_status is not None:
                on_status("running")
            try:
                for report in spacemouse.reports(deadline, stop_event):
                    try:
                        state = parse_report(report, state)
                    except ValueError:
                        continue
                    if on_state is not None:
                        on_state(state)
                    for event in detector.update(state):
                        action = config.assignments[event.control]
                        emitted = dispatcher.dispatch(event, action)
                        if on_event is not None:
                            on_event(event, action, emitted)
            finally:
                dispatcher.release_all()

