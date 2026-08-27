"""Tray-resident distributable shell for Vibe SpaceMouse Bridge for Codex."""

from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .gui import MappingApp
from .logging_setup import configure_release_logging
from .paths import (
    ensure_user_config,
    resource_path,
    user_log_path,
    user_settings_path,
)
from .release_controller import (
    STATE_ACTIVE,
    STATE_ERROR,
    STATE_STARTING,
    STATE_STOPPING,
    BridgeController,
    ControllerSnapshot,
)
from .release_settings import ReleaseSettings
from .startup import set_start_with_windows
from .version import PRODUCT_NAME, PRODUCT_VERSION
from .winipc import NamedEvent, SingleInstance, signal_named_event
from .wintray import NativeTrayIcon


MUTEX_NAME = r"Local\SpaceMouseCodexBridge.ReleaseApp"
SHOW_EVENT_NAME = r"Local\SpaceMouseCodexBridge.Show"
SHUTDOWN_EVENT_NAME = r"Local\SpaceMouseCodexBridge.Shutdown"
ADVANCED_EVENT_NAME = r"Local\SpaceMouseCodexBridge.Advanced"


class ReleaseDashboard:
    def __init__(
        self,
        root: tk.Tk,
        *,
        start_hidden: bool = False,
        show_event: NamedEvent | None = None,
        shutdown_event: NamedEvent | None = None,
        advanced_event: NamedEvent | None = None,
    ) -> None:
        self.root = root
        self.root.title(PRODUCT_NAME)
        self.root.geometry("640x610")
        self.root.minsize(590, 565)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        self.config_path = ensure_user_config()
        self.settings_path = user_settings_path()
        self.log_path = user_log_path()
        self.settings = ReleaseSettings.load(self.settings_path)
        self.logger = configure_release_logging(self.log_path)
        self.logger.info("%s %s starting", PRODUCT_NAME, PRODUCT_VERSION)

        self.show_event = show_event
        self.shutdown_event = shutdown_event
        self.advanced_event = advanced_event
        self.snapshot_queue: queue.Queue[ControllerSnapshot] = queue.Queue(maxsize=64)
        self.last_snapshot: ControllerSnapshot | None = None
        self.tray_icon: NativeTrayIcon | None = None
        self.advanced_process: subprocess.Popen | None = None
        self.exiting = False
        self.shutdown_thread: threading.Thread | None = None

        self.auto_link_var = tk.BooleanVar(value=self.settings.auto_link_enabled)
        self.startup_var = tk.BooleanVar(value=self.settings.start_with_windows)
        self.status_var = tk.StringVar(value="起動しています…")
        self.detail_var = tk.StringVar(value="")
        self.codex_var = tk.StringVar(value="確認中")
        self.spacemouse_var = tk.StringVar(value="確認中")
        self.hid_var = tk.StringVar(value="確認中")
        self.driver_var = tk.StringVar(value="確認中")

        self._build_ui()
        self._sync_startup(show_error=False)
        self.controller = BridgeController(
            self.config_path,
            enabled=self.settings.auto_link_enabled,
            on_snapshot=self._enqueue_snapshot,
            logger=self.logger,
        )
        self.controller.start()
        self._start_tray()
        self.root.after(100, self._drain_snapshots)
        self.root.after(400, self._poll_ipc)
        if start_hidden:
            self.root.withdraw()

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.configure("ReleaseTitle.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("ReleaseStatus.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("ReleaseGood.TLabel", foreground="#16803a", font=("Segoe UI", 15, "bold"))
        style.configure("ReleaseBusy.TLabel", foreground="#0878d1", font=("Segoe UI", 15, "bold"))
        style.configure("ReleaseError.TLabel", foreground="#b3261e", font=("Segoe UI", 15, "bold"))

        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text=PRODUCT_NAME, style="ReleaseTitle.TLabel").pack(side="left")
        ttk.Label(header, text=PRODUCT_VERSION, foreground="#68727d").pack(
            side="left", padx=(10, 0), pady=(8, 0)
        )
        ttk.Checkbutton(
            header,
            text="Codex自動連動",
            variable=self.auto_link_var,
            command=self._toggle_auto_link,
        ).pack(side="right", pady=(6, 0))

        status = ttk.LabelFrame(outer, text="現在の状態", padding=14)
        status.pack(fill="x", pady=(18, 12))
        self.status_label = ttk.Label(status, textvariable=self.status_var, style="ReleaseStatus.TLabel")
        self.status_label.pack(anchor="w")
        ttk.Label(status, textvariable=self.detail_var, wraplength=530, foreground="#59636e").pack(
            anchor="w", pady=(6, 0)
        )

        devices = ttk.LabelFrame(outer, text="接続", padding=12)
        devices.pack(fill="x")
        rows = (
            ("Codex", self.codex_var),
            ("SpaceMouse Compact", self.spacemouse_var),
            ("Codex Micro 仮想HID", self.hid_var),
            ("公式 3DxWare", self.driver_var),
        )
        for row, (name, variable) in enumerate(rows):
            ttk.Label(devices, text=name).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Label(devices, textvariable=variable).grid(row=row, column=1, sticky="e", pady=4)
        devices.columnconfigure(0, weight=1)

        info = ttk.LabelFrame(outer, text="使い方", padding=12)
        info.pack(fill="x", pady=(12, 0))
        ttk.Label(
            info,
            text=(
                "Codexを開くとSpaceMouseを自動接続し、Codexを閉じると3DxWareへ戻します。\n"
                "画面を閉じても通知領域で常駐し、アイコンのダブルクリックで再表示できます。\n"
                "割り当てや感度は「詳細設定」から変更できます。"
            ),
            justify="left",
        ).pack(anchor="w")
        ttk.Checkbutton(
            info,
            text="Windowsログイン時に通知領域へ常駐",
            variable=self.startup_var,
            command=self._toggle_startup,
        ).pack(anchor="w", pady=(8, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", side="bottom", pady=(16, 0))
        self.connect_button = ttk.Button(buttons, text="今すぐ接続", command=self.connect_now)
        self.connect_button.pack(side="left")
        self.advanced_button = ttk.Button(buttons, text="詳細設定", command=self.open_advanced)
        self.advanced_button.pack(side="left", padx=(7, 0))
        ttk.Button(buttons, text="ログを開く", command=self.open_logs).pack(side="left", padx=7)
        ttk.Button(buttons, text="トレイへ隠す", command=self.hide).pack(side="left")
        ttk.Button(buttons, text="終了", command=self.request_exit).pack(side="right")

    def _toggle_auto_link(self) -> None:
        enabled = self.auto_link_var.get()
        self.settings.auto_link_enabled = enabled
        self.settings.save(self.settings_path)
        self.controller.set_enabled(enabled)
        if self.tray_icon is not None:
            self.tray_icon.update()

    def _toggle_startup(self) -> None:
        self.settings.start_with_windows = self.startup_var.get()
        self.settings.save(self.settings_path)
        self._sync_startup(show_error=True)

    def _sync_startup(self, *, show_error: bool) -> None:
        try:
            set_start_with_windows(self.settings.start_with_windows)
        except OSError as error:
            self.logger.exception("Could not update Windows login startup")
            self.startup_var.set(False)
            if show_error:
                messagebox.showerror(
                    "自動起動を設定できませんでした",
                    f"Windowsのログイン時起動を更新できませんでした。\n{error}",
                    parent=self.root,
                )

    def connect_now(self) -> None:
        self.auto_link_var.set(True)
        self.settings.auto_link_enabled = True
        self.settings.save(self.settings_path)
        self.controller.connect_now()
        self.status_var.set("接続を再試行しています…")
        self.detail_var.set("Codex、SpaceMouse、仮想HIDを確認しています。")
        if self.tray_icon is not None:
            self.tray_icon.update()

    def _enqueue_snapshot(self, snapshot: ControllerSnapshot) -> None:
        try:
            self.snapshot_queue.put_nowait(snapshot)
        except queue.Full:
            try:
                self.snapshot_queue.get_nowait()
            except queue.Empty:
                pass
            self.snapshot_queue.put_nowait(snapshot)

    def _drain_snapshots(self) -> None:
        latest = None
        while True:
            try:
                latest = self.snapshot_queue.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            self._show_snapshot(latest)
        if not self.exiting:
            self.root.after(100, self._drain_snapshots)

    def _show_snapshot(self, snapshot: ControllerSnapshot) -> None:
        self.last_snapshot = snapshot
        self.status_var.set(snapshot.message)
        self.detail_var.set(snapshot.detail)
        self.codex_var.set("● 検出済み" if snapshot.codex_present else "○ 待機中")
        self.spacemouse_var.set("● 接続済み" if snapshot.spacemouse_present else "× 未検出")
        self.hid_var.set("● 準備完了" if snapshot.codex_hid_present else "× 未検出")
        self.driver_var.set("● 実行中" if snapshot.driver_running else "○ Bridge使用中 / 停止")
        if snapshot.state == STATE_ACTIVE:
            style = "ReleaseGood.TLabel"
        elif snapshot.state in (STATE_STARTING, STATE_STOPPING):
            style = "ReleaseBusy.TLabel"
        elif snapshot.state == STATE_ERROR:
            style = "ReleaseError.TLabel"
        else:
            style = "ReleaseStatus.TLabel"
        self.status_label.configure(style=style)
        self.connect_button.configure(
            text="接続中" if snapshot.state == STATE_ACTIVE else "今すぐ接続 / 再試行",
            state=(
                "disabled"
                if snapshot.state in (STATE_ACTIVE, STATE_STARTING, STATE_STOPPING)
                else "normal"
            ),
        )
        if self.tray_icon is not None:
            self.tray_icon.update(f"{PRODUCT_NAME} — {snapshot.message}")

    def _start_tray(self) -> None:
        try:
            self.tray_icon = NativeTrayIcon(
                resource_path("spacemouse_input", "assets", "vibe-6dof.ico"),
                PRODUCT_NAME,
                status_text=self._tray_status_text,
                is_enabled=lambda: self.controller.enabled,
                on_show=lambda: self._dispatch(self.show),
                on_connect=lambda: self._dispatch(self.connect_now),
                on_toggle=lambda: self._dispatch(self._toggle_from_tray),
                on_advanced=lambda: self._dispatch(self.open_advanced),
                on_logs=lambda: self._dispatch(self.open_logs),
                on_exit=lambda: self._dispatch(self.request_exit),
            )
            self.tray_icon.start()
        except (OSError, RuntimeError):
            self.tray_icon = None
            self.logger.exception("Native Windows tray icon could not be started")
            return

    def _tray_status_text(self) -> str:
        return self.last_snapshot.message if self.last_snapshot else "起動しています…"

    def _dispatch(self, callback) -> None:
        self.root.after(0, callback)

    def _toggle_from_tray(self) -> None:
        self.auto_link_var.set(not self.controller.enabled)
        self._toggle_auto_link()

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self) -> None:
        self.root.withdraw()

    def open_logs(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        os.startfile(self.log_path.parent)  # type: ignore[attr-defined]

    def open_advanced(self) -> None:
        if self.advanced_process is not None and self.advanced_process.poll() is None:
            return
        self.advanced_button.configure(state="disabled")
        self.controller.suspend()
        threading.Thread(target=self._advanced_worker, name="advanced-launcher", daemon=True).start()

    def _advanced_worker(self) -> None:
        if not self.controller.wait_for_bridge_stop(25.0):
            self.logger.error("Bridge did not stop before advanced settings")
            self.root.after(0, self._advanced_failed)
            return
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--advanced-child"]
        else:
            command = [sys.executable, "-m", "spacemouse_input.release_app", "--advanced-child"]
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.advanced_process = subprocess.Popen(command, creationflags=creationflags)
            self.root.after(0, self.hide)
            self.advanced_process.wait()
        except OSError:
            self.logger.exception("Failed to open advanced settings")
        finally:
            self.advanced_process = None
            self.controller.resume()
            self.root.after(0, self._advanced_finished)

    def _advanced_failed(self) -> None:
        self.controller.resume()
        self.advanced_button.configure(state="normal")
        messagebox.showerror(
            "詳細設定",
            "Bridgeを停止できなかったため、詳細設定を開けませんでした。ログを確認してください。",
            parent=self.root,
        )

    def _advanced_finished(self) -> None:
        self.advanced_button.configure(state="normal")
        self.show()

    def _poll_ipc(self) -> None:
        if self.show_event is not None and self.show_event.consume():
            self.show()
        if self.advanced_event is not None and self.advanced_event.consume():
            self.open_advanced()
        if self.shutdown_event is not None and self.shutdown_event.consume():
            self.request_exit()
        if not self.exiting:
            self.root.after(400, self._poll_ipc)

    def request_exit(self) -> None:
        if self.exiting:
            return
        if self.advanced_process is not None and self.advanced_process.poll() is None:
            self.show()
            messagebox.showinfo(
                "詳細設定を閉じてください",
                "安全に3DxWareへ戻すため、詳細設定画面を閉じてから終了してください。",
                parent=self.root,
            )
            return
        self.exiting = True
        self.status_var.set("終了処理中…")
        self.detail_var.set("入力を解放し、3DxWareを復帰しています。")
        self.auto_link_var.set(False)
        self.shutdown_thread = threading.Thread(target=self.controller.shutdown, name="release-shutdown")
        self.shutdown_thread.start()
        self.root.after(100, self._poll_shutdown)

    def _poll_shutdown(self) -> None:
        if self.shutdown_thread is not None and self.shutdown_thread.is_alive():
            self.root.after(100, self._poll_shutdown)
            return
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.logger.info("Release application stopped cleanly")
        self.root.destroy()


def run_advanced() -> int:
    root = tk.Tk()
    MappingApp(root, ensure_user_config())
    root.mainloop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=PRODUCT_NAME)
    parser.add_argument("--advanced", action="store_true", help="詳細設定画面を開く")
    parser.add_argument("--advanced-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--background", action="store_true", help="タスクトレイへ最小化して起動")
    parser.add_argument("--shutdown", action="store_true", help="実行中の配布版を安全に終了")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.advanced_child:
        return run_advanced()
    if args.advanced:
        if signal_named_event(ADVANCED_EVENT_NAME):
            return 0
        return run_advanced()
    if args.shutdown:
        return 0 if signal_named_event(SHUTDOWN_EVENT_NAME) else 1

    instance = SingleInstance(MUTEX_NAME)
    if not instance.acquired:
        signal_named_event(SHOW_EVENT_NAME)
        instance.close()
        return 0
    show_event = NamedEvent(SHOW_EVENT_NAME)
    shutdown_event = NamedEvent(SHUTDOWN_EVENT_NAME)
    advanced_event = NamedEvent(ADVANCED_EVENT_NAME)
    try:
        root = tk.Tk()
        ReleaseDashboard(
            root,
            start_hidden=args.background,
            show_event=show_event,
            shutdown_event=shutdown_event,
            advanced_event=advanced_event,
        )
        root.mainloop()
    finally:
        show_event.close()
        shutdown_event.close()
        advanced_event.close()
        instance.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
