"""Open and stream reports from supported SpaceMouse USB HID devices."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from time import monotonic, sleep
from typing import Iterator

import hid


THREEDCONNEXION_VENDOR_ID = 0x256F
SPACEMOUSE_COMPACT_PRODUCT_ID = 0xC635


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    path: bytes
    vendor_id: int
    product_id: int
    manufacturer: str
    product: str
    serial_number: str

    @property
    def identifier(self) -> str:
        return f"{self.vendor_id:04X}:{self.product_id:04X}"


def enumerate_devices(
    vendor_id: int = THREEDCONNEXION_VENDOR_ID,
    product_id: int = SPACEMOUSE_COMPACT_PRODUCT_ID,
) -> list[DeviceInfo]:
    devices = []
    for raw in hid.enumerate(vendor_id, product_id):
        path = raw.get("path")
        if not path:
            continue
        devices.append(
            DeviceInfo(
                path=path,
                vendor_id=raw["vendor_id"],
                product_id=raw["product_id"],
                manufacturer=raw.get("manufacturer_string") or "",
                product=raw.get("product_string") or "",
                serial_number=raw.get("serial_number") or "",
            )
        )
    return devices


class SpaceMouseDevice:
    def __init__(self, info: DeviceInfo, poll_interval: float = 0.005) -> None:
        self.info = info
        self.poll_interval = poll_interval
        self._device: hid.device | None = None

    def __enter__(self) -> "SpaceMouseDevice":
        device = hid.device()
        device.open_path(self.info.path)
        device.set_nonblocking(True)
        self._device = device
        return self

    def __exit__(self, *_: object) -> None:
        if self._device is not None:
            self._device.close()
            self._device = None

    def reports(
        self,
        deadline: float | None = None,
        stop_event: Event | None = None,
    ) -> Iterator[bytes]:
        if self._device is None:
            raise RuntimeError("device is not open")
        while True:
            if stop_event is not None and stop_event.is_set():
                return
            if deadline is not None and monotonic() >= deadline:
                return
            report = self._device.read(64)
            if report:
                yield bytes(report)
            else:
                sleep(self.poll_interval)
