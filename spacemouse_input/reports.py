"""Decode HID input reports produced by a SpaceMouse Compact."""

from __future__ import annotations

from dataclasses import dataclass, replace


TRANSLATION_REPORT_ID = 1
ROTATION_REPORT_ID = 2
BUTTON_REPORT_ID = 3


@dataclass(frozen=True, slots=True)
class SpaceMouseState:
    """Latest complete six-axis and button state."""

    tx: int = 0
    ty: int = 0
    tz: int = 0
    rx: int = 0
    ry: int = 0
    rz: int = 0
    buttons: int = 0


def _signed_16(low: int, high: int) -> int:
    value = low | (high << 8)
    return value - 0x10000 if value & 0x8000 else value


def _three_axes(report: bytes) -> tuple[int, int, int]:
    if len(report) < 7:
        raise ValueError(f"axis report is too short: {len(report)} bytes")
    return (
        _signed_16(report[1], report[2]),
        _signed_16(report[3], report[4]),
        _signed_16(report[5], report[6]),
    )


def parse_report(report: bytes | bytearray | list[int], previous: SpaceMouseState) -> SpaceMouseState:
    """Merge one HID report into the latest state.

    SpaceMouse Compact sends translation, rotation, and buttons in separate
    reports. Unknown report IDs are rejected so a protocol mismatch is visible.
    """

    data = bytes(report)
    if not data:
        raise ValueError("empty HID report")

    report_id = data[0]
    if report_id == TRANSLATION_REPORT_ID:
        tx, ty, tz = _three_axes(data)
        return replace(previous, tx=tx, ty=ty, tz=tz)
    if report_id == ROTATION_REPORT_ID:
        rx, ry, rz = _three_axes(data)
        return replace(previous, rx=rx, ry=ry, rz=rz)
    if report_id == BUTTON_REPORT_ID:
        if len(data) < 2:
            raise ValueError(f"button report is too short: {len(data)} bytes")
        buttons = int.from_bytes(data[1:], byteorder="little", signed=False)
        return replace(previous, buttons=buttons)

    raise ValueError(f"unknown HID report ID: {report_id}")

