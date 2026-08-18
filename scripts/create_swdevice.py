"""Create a persistent software-enumerated instance for the UMDF HID driver."""

from __future__ import annotations

import ctypes
import threading


HRESULT = ctypes.c_long
HSWDEVICE = ctypes.c_void_p


class SW_DEVICE_CREATE_INFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("pszInstanceId", ctypes.c_wchar_p),
        ("pszzHardwareIds", ctypes.c_wchar_p),
        ("pszzCompatibleIds", ctypes.c_wchar_p),
        ("pContainerId", ctypes.c_void_p),
        ("CapabilityFlags", ctypes.c_ulong),
        ("pszDeviceDescription", ctypes.c_wchar_p),
        ("pszDeviceLocation", ctypes.c_wchar_p),
        ("pSecurityDescriptor", ctypes.c_void_p),
    ]


CALLBACK = ctypes.WINFUNCTYPE(
    None,
    HSWDEVICE,
    HRESULT,
    ctypes.c_void_p,
    ctypes.c_wchar_p,
)


def failed(value: int) -> bool:
    return value < 0


def main() -> int:
    cfgmgr32 = ctypes.WinDLL("cfgmgr32", use_last_error=True)
    create = cfgmgr32.SwDeviceCreate
    create.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.POINTER(SW_DEVICE_CREATE_INFO),
        ctypes.c_ulong,
        ctypes.c_void_p,
        CALLBACK,
        ctypes.c_void_p,
        ctypes.POINTER(HSWDEVICE),
    ]
    create.restype = HRESULT
    set_lifetime = cfgmgr32.SwDeviceSetLifetime
    set_lifetime.argtypes = [HSWDEVICE, ctypes.c_int]
    set_lifetime.restype = HRESULT
    close = cfgmgr32.SwDeviceClose
    close.argtypes = [HSWDEVICE]
    close.restype = None

    hardware_ids = ctypes.create_unicode_buffer("root\\CodexMicroHid\0\0")
    info = SW_DEVICE_CREATE_INFO()
    info.cbSize = ctypes.sizeof(info)
    info.pszInstanceId = "SPACEMOUSE_CODEX"
    info.pszzHardwareIds = ctypes.cast(hardware_ids, ctypes.c_wchar_p)
    # Allow creation before PnP selects our staged UMDF package. The installer
    # applies that package explicitly after this node exists.
    info.CapabilityFlags = 0x02  # SilentInstall
    info.pszDeviceDescription = "Codex Micro SpaceMouse Bridge"
    info.pszDeviceLocation = "Software Device"

    completed = threading.Event()
    callback_result: dict[str, object] = {}

    @CALLBACK
    def on_created(_handle, result, _context, instance_id):
        callback_result["result"] = int(result)
        callback_result["instance_id"] = instance_id
        completed.set()

    handle = HSWDEVICE()
    hr = int(
        create(
            "VID_303A&PID_8360",
            "HTREE\\ROOT\\0",
            ctypes.byref(info),
            0,
            None,
            on_created,
            None,
            ctypes.byref(handle),
        )
    )
    if failed(hr):
        raise OSError(f"SwDeviceCreate failed: 0x{hr & 0xFFFFFFFF:08X}")
    try:
        if not completed.wait(15):
            raise TimeoutError("Software device enumeration timed out")
        result = int(callback_result.get("result", -1))
        if failed(result):
            raise OSError(f"software device creation failed: 0x{result & 0xFFFFFFFF:08X}")
        # Keep the software device present after this helper exits. It is removed
        # automatically when its root parent is no longer present (for example,
        # during shutdown).
        hr = int(set_lifetime(handle, 1))  # SWDeviceLifetimeParentPresent
        if failed(hr):
            raise OSError(f"SwDeviceSetLifetime failed: 0x{hr & 0xFFFFFFFF:08X}")
        print(callback_result["instance_id"])
    finally:
        if handle:
            close(handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
