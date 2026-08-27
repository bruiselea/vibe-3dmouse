"""Small Windows notification-area wrapper with no third-party runtime dependency."""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Callable


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

# ctypes assumes a 32-bit integer return value unless told otherwise. Window
# handles are pointer-sized, so declaring these signatures is required on x64.
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.RegisterClassW.argtypes = [ctypes.c_void_p]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
user32.CreateWindowExW.restype = wintypes.HWND
user32.LoadImageW.argtypes = [
    wintypes.HINSTANCE,
    wintypes.LPCWSTR,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
user32.LoadImageW.restype = wintypes.HANDLE
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.DestroyIcon.restype = wintypes.BOOL
user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.UnregisterClassW.restype = wintypes.BOOL
user32.CreatePopupMenu.argtypes = []
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.AppendMenuW.restype = wintypes.BOOL
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.DestroyMenu.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.c_void_p]
user32.GetCursorPos.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.TrackPopupMenu.argtypes = [
    wintypes.HMENU,
    wintypes.UINT,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    ctypes.c_void_p,
]
user32.TrackPopupMenu.restype = wintypes.UINT
user32.GetMessageW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.c_void_p]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL


WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_UPDATE_ICON = WM_APP + 2
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIM_SETVERSION = 0x00000004
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NOTIFYICON_VERSION_4 = 4

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040

MF_STRING = 0x0000
MF_GRAYED = 0x0001
MF_CHECKED = 0x0008
MF_SEPARATOR = 0x0800
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class NativeTrayIcon:
    """Own a hidden Win32 window and one notification-area icon."""

    def __init__(
        self,
        icon_path: Path,
        title: str,
        *,
        status_text: Callable[[], str],
        is_enabled: Callable[[], bool],
        on_show: Callable[[], None],
        on_connect: Callable[[], None],
        on_toggle: Callable[[], None],
        on_advanced: Callable[[], None],
        on_logs: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.icon_path = Path(icon_path)
        self.title = title
        self.status_text = status_text
        self.is_enabled = is_enabled
        self.callbacks = {
            1001: on_show,
            1002: on_connect,
            1003: on_toggle,
            1004: on_advanced,
            1005: on_logs,
            1006: on_exit,
        }
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._hwnd: int | None = None
        self._icon: int | None = None
        self._nid: NOTIFYICONDATAW | None = None
        self._wndproc = WNDPROC(self._window_proc)
        self._taskbar_created = ctypes.windll.user32.RegisterWindowMessageW("TaskbarCreated")

    def start(self) -> None:
        if os.name != "nt":
            raise OSError("The native tray icon is available only on Windows.")
        self._thread = threading.Thread(target=self._run, name="native-tray", daemon=True)
        self._thread.start()
        if not self._ready.wait(5.0) or self._hwnd is None:
            raise RuntimeError("Windows tray icon could not be started.")

    def update(self, title: str | None = None) -> None:
        if title is not None:
            self.title = title
        if self._hwnd:
            ctypes.windll.user32.PostMessageW(self._hwnd, WM_UPDATE_ICON, 0, 0)

    def stop(self) -> None:
        if self._hwnd:
            ctypes.windll.user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        instance = kernel32.GetModuleHandleW(None)
        class_name = f"VibeSpaceMouseTray.{os.getpid()}"
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = self._wndproc
        window_class.hInstance = instance
        window_class.lpszClassName = class_name
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            self._ready.set()
            return
        hwnd = user32.CreateWindowExW(
            0, class_name, class_name, 0, 0, 0, 0, 0, None, None, instance, None
        )
        if not hwnd:
            self._ready.set()
            return
        self._hwnd = hwnd
        icon = user32.LoadImageW(
            None,
            str(self.icon_path),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
        if not icon:
            user32.DestroyWindow(hwnd)
            self._hwnd = None
            self._ready.set()
            return
        self._icon = icon
        self._add_icon()
        self._ready.set()

        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))

        user32.UnregisterClassW(class_name, instance)
        self._hwnd = None

    def _make_nid(self) -> NOTIFYICONDATAW:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._icon
        nid.szTip = self.title[:127]
        return nid

    def _add_icon(self) -> None:
        self._nid = self._make_nid()
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._nid))
        self._nid.uVersion = NOTIFYICON_VERSION_4
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(self._nid))

    def _update_icon(self) -> None:
        if self._nid is None:
            return
        self._nid.szTip = self.title[:127]
        self._nid.uFlags = NIF_ICON | NIF_TIP | NIF_MESSAGE
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def _show_menu(self) -> None:
        user32 = ctypes.windll.user32
        menu = user32.CreatePopupMenu()
        try:
            user32.AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, self.status_text()[:80])
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, 1001, "ダッシュボードを開く")
            user32.AppendMenuW(menu, MF_STRING, 1002, "今すぐ接続 / 再試行")
            toggle_flags = MF_STRING | (MF_CHECKED if self.is_enabled() else 0)
            user32.AppendMenuW(menu, toggle_flags, 1003, "Codex自動連動")
            user32.AppendMenuW(menu, MF_STRING, 1004, "詳細設定")
            user32.AppendMenuW(menu, MF_STRING, 1005, "ログを開く")
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, 1006, "終了")
            point = POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(self._hwnd)
            command = user32.TrackPopupMenu(
                menu,
                TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                point.x,
                point.y,
                0,
                self._hwnd,
                None,
            )
        finally:
            user32.DestroyMenu(menu)
        callback = self.callbacks.get(command)
        if callback is not None:
            callback()

    def _window_proc(self, hwnd, message, wparam, lparam):
        user32 = ctypes.windll.user32
        if message == WM_TRAYICON:
            event = int(lparam) & 0xFFFF
            if event == WM_LBUTTONDBLCLK:
                self.callbacks[1001]()
            elif event == WM_RBUTTONUP:
                self._show_menu()
            return 0
        if message == WM_UPDATE_ICON:
            self._update_icon()
            return 0
        if message == self._taskbar_created:
            self._add_icon()
            return 0
        if message == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if message == WM_DESTROY:
            if self._nid is not None:
                ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
            if self._icon:
                user32.DestroyIcon(self._icon)
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)
