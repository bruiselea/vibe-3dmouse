"""Build and send the vendor HID reports understood by Codex Micro.

Compatibility framing was implemented with reference to GOROman/vibewatch,
Copyright (c) 2026 GOROman, MIT License. The complete license is distributed in
THIRD_PARTY_LICENSES/GOROman-vibewatch-MIT.txt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import hid


CODEX_MICRO_VENDOR_ID = 0x303A
CODEX_MICRO_PRODUCT_ID = 0x8360
VENDOR_REPORT_ID = 6
INJECTION_REPORT_ID = 7
INJECTION_USAGE_PAGE = 0xFF01
REPORT_DATA_LENGTH = 63
RPC_CHUNK_LENGTH = 61
CHANNEL_JSON_RPC = 2


def build_notification(method: str, params: dict[str, Any]) -> bytes:
    payload = (
        json.dumps({"m": method, "p": params}, separators=(",", ":"), ensure_ascii=True)
        + "\r\n"
    ).encode("ascii")
    if len(payload) > RPC_CHUNK_LENGTH:
        raise ValueError(f"JSON-RPC payload is too long: {len(payload)} > {RPC_CHUNK_LENGTH}")

    report_data = bytearray(REPORT_DATA_LENGTH)
    report_data[0] = CHANNEL_JSON_RPC
    report_data[1] = len(payload)
    report_data[2 : 2 + len(payload)] = payload
    return bytes((VENDOR_REPORT_ID,)) + bytes(report_data)


def build_key_report(key: str, act: int) -> bytes:
    if act not in (0, 1, 2):
        raise ValueError("act must be 0 (release), 1 (press), or 2 (encoder step)")
    return build_notification("v.oai.hid", {"k": key, "act": act})


def build_joystick_report(angle: float, distance: float) -> bytes:
    if not 0.0 <= angle <= 1.0:
        raise ValueError("angle must be between 0 and 1")
    if not 0.0 <= distance <= 1.0:
        raise ValueError("distance must be between 0 and 1")
    # Device Kit uses the compact wire keys `a` and `d`.
    return build_notification("v.oai.rad", {"a": angle, "d": distance})


@dataclass(frozen=True, slots=True)
class CodexDeviceInfo:
    path: bytes
    manufacturer: str
    product: str
    usage_page: int
    usage: int

    @property
    def native_codex_compatible(self) -> bool:
        path = self.path.lower()
        return b"vid_303a" in path and b"pid_8360" in path


def enumerate_codex_devices() -> list[CodexDeviceInfo]:
    devices = []
    for raw in hid.enumerate(CODEX_MICRO_VENDOR_ID, CODEX_MICRO_PRODUCT_ID):
        path = raw.get("path")
        if not path:
            continue
        devices.append(
            CodexDeviceInfo(
                path=path,
                manufacturer=raw.get("manufacturer_string") or "",
                product=raw.get("product_string") or "",
                usage_page=int(raw.get("usage_page") or 0),
                usage=int(raw.get("usage") or 0),
            )
        )
    vendor = [device for device in devices if device.usage_page == 0xFF00]
    selected = vendor or devices
    return sorted(selected, key=lambda device: not device.native_codex_compatible)


class CodexMicroDevice:
    def __init__(self, info: CodexDeviceInfo) -> None:
        self.info = info
        self._devices: list[hid.device] = []

    def __enter__(self) -> "CodexMicroDevice":
        injection_paths = [
            raw.get("path")
            for raw in hid.enumerate(CODEX_MICRO_VENDOR_ID, CODEX_MICRO_PRODUCT_ID)
            if int(raw.get("usage_page") or 0) == INJECTION_USAGE_PAGE
            and raw.get("path")
        ]
        if not injection_paths:
            raise OSError("Codex bridge injection HID (usage page FF01) was not found")
        opened: list[hid.device] = []
        for path in injection_paths:
            device = hid.device()
            try:
                device.open_path(path)
            except OSError:
                device.close()
                continue
            opened.append(device)
        if not opened:
            raise OSError("Codex bridge injection HID could not be opened")
        self._devices = opened
        return self

    def __exit__(self, *_: object) -> None:
        for device in self._devices:
            device.close()
        self._devices = []

    def send_report(self, report: bytes) -> None:
        if not self._devices:
            raise RuntimeError("Codex Micro device is not open")
        if len(report) != REPORT_DATA_LENGTH + 1 or report[0] != VENDOR_REPORT_ID:
            raise ValueError("expected a 64-byte report beginning with report ID 6")
        injected = bytes((INJECTION_REPORT_ID,)) + report[1:]
        for device in self._devices:
            written = device.write(injected)
            if written != len(injected):
                raise OSError(f"short Codex injection write: {written}/{len(injected)} bytes")

    def send_key(self, key: str, act: int) -> None:
        self.send_report(build_key_report(key, act))

    def send_joystick(self, angle: float, distance: float) -> None:
        self.send_report(build_joystick_report(angle, distance))
