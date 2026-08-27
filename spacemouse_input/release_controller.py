"""Codex-linked bridge state machine for the distributable application."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from time import monotonic
from typing import Callable

from .device import enumerate_devices
from .mapping import MappingConfig
from .official_driver import driver_is_running, resume_driver_if_installed
from .process_monitor import codex_is_running
from .protocol import enumerate_codex_devices
from .runtime import run_bridge
from .virtual_hid_recovery import request_virtual_hid_recovery


STATE_DISABLED = "disabled"
STATE_WAITING = "waiting"
STATE_STARTING = "starting"
STATE_ACTIVE = "active"
STATE_STOPPING = "stopping"
STATE_SUSPENDED = "suspended"
STATE_ERROR = "error"
STATE_STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class ControllerSnapshot:
    state: str
    message: str
    detail: str
    enabled: bool
    suspended: bool
    codex_present: bool
    spacemouse_present: bool
    codex_hid_present: bool
    driver_running: bool


class CodexLinkPolicy:
    """Pure start/stop policy, separated so debounce behavior is testable."""

    def __init__(self, missing_limit: int = 5) -> None:
        if missing_limit < 1:
            raise ValueError("missing_limit must be at least one")
        self.missing_limit = missing_limit
        self.misses = 0

    def observe(
        self,
        *,
        enabled: bool,
        suspended: bool,
        codex_present: bool,
        bridge_running: bool,
    ) -> str:
        if codex_present:
            self.misses = 0
        else:
            self.misses += 1
        if not enabled or suspended:
            return "stop" if bridge_running else "none"
        if codex_present:
            return "none" if bridge_running else "start"
        if bridge_running and self.misses >= self.missing_limit:
            return "stop"
        return "none"


class BridgeController:
    """Own exactly one bridge worker and follow the Codex process lifecycle."""

    def __init__(
        self,
        config_path,
        *,
        enabled: bool = True,
        poll_interval: float = 1.0,
        retry_interval: float = 5.0,
        missing_limit: int = 5,
        on_snapshot: Callable[[ControllerSnapshot], None] | None = None,
        codex_probe: Callable[[], bool] = codex_is_running,
        spacemouse_probe: Callable[[], bool] | None = None,
        codex_hid_probe: Callable[[], bool] | None = None,
        driver_probe: Callable[[], bool] = driver_is_running,
        driver_resume: Callable[[], bool] = resume_driver_if_installed,
        hid_recover: Callable[[], bool] = request_virtual_hid_recovery,
        bridge_runner=run_bridge,
        config_loader=MappingConfig.load,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config_path = config_path
        self.poll_interval = poll_interval
        self.retry_interval = retry_interval
        self.on_snapshot = on_snapshot
        self.codex_probe = codex_probe
        self.spacemouse_probe = spacemouse_probe or (lambda: bool(enumerate_devices()))
        self.codex_hid_probe = codex_hid_probe or (lambda: bool(enumerate_codex_devices()))
        self.driver_probe = driver_probe
        self.driver_resume = driver_resume
        self.hid_recover = hid_recover
        self.bridge_runner = bridge_runner
        self.config_loader = config_loader
        self.logger = logger or logging.getLogger(__name__)

        self.policy = CodexLinkPolicy(missing_limit)
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._shutdown = threading.Event()
        self._bridge_stop = threading.Event()
        self._monitor_thread: threading.Thread | None = None
        self._bridge_thread: threading.Thread | None = None
        self._next_retry = 0.0
        self._last_snapshot: ControllerSnapshot | None = None

        self._enabled = enabled
        self._suspended = False
        self._state = STATE_WAITING if enabled else STATE_DISABLED
        self._message = "Codexの起動を待っています" if enabled else "自動連動はオフです"
        self._detail = ""
        self._codex_present = False
        self._spacemouse_present = False
        self._codex_hid_present = False
        self._driver_running = False

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def bridge_running(self) -> bool:
        with self._lock:
            return self._bridge_thread is not None and self._bridge_thread.is_alive()

    def start(self) -> None:
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            return
        self._shutdown.clear()
        self._heal_official_driver_if_idle()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="codex-link-monitor",
            daemon=True,
        )
        self._monitor_thread.start()

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = enabled
        if not enabled:
            self._request_bridge_stop("自動連動を停止しています")
        self.logger.info("Codex automatic link: %s", "enabled" if enabled else "disabled")
        self._wake.set()

    def connect_now(self) -> None:
        """Enable automatic linking and retry immediately when Codex is available."""

        with self._lock:
            self._enabled = True
            self._next_retry = 0.0
            self.policy.misses = 0
        self.logger.info("Immediate Bridge connection requested")
        self._wake.set()

    def suspend(self) -> None:
        with self._lock:
            self._suspended = True
        self._request_bridge_stop("詳細設定のため一時停止しています")
        self.logger.info("Bridge suspended for advanced settings")
        self._wake.set()

    def resume(self) -> None:
        with self._lock:
            self._suspended = False
        self.logger.info("Bridge resumed after advanced settings")
        self._wake.set()

    def wait_for_bridge_stop(self, timeout: float = 20.0) -> bool:
        with self._lock:
            thread = self._bridge_thread
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def shutdown(self, timeout: float = 25.0) -> None:
        self.logger.info("Release controller shutdown requested")
        self._shutdown.set()
        self._wake.set()
        self._request_bridge_stop("アプリを終了しています")
        self.wait_for_bridge_stop(timeout)
        try:
            self.driver_resume()
        except Exception:
            self.logger.exception("Failed to restore 3DxWare during shutdown")
        monitor = self._monitor_thread
        if monitor is not None and monitor is not threading.current_thread():
            monitor.join(min(timeout, 5.0))
        self._set_status(STATE_STOPPED, "停止しました")

    def tick(self) -> None:
        """Run one monitor iteration. Public for deterministic tests."""

        codex_present = self._safe_probe(self.codex_probe, "Codex process")
        spacemouse_present = self._safe_probe(self.spacemouse_probe, "SpaceMouse")
        codex_hid_present = self._safe_probe(self.codex_hid_probe, "Codex HID")
        driver_running = self._safe_probe(self.driver_probe, "3DxWare")
        with self._lock:
            self._codex_present = codex_present
            self._spacemouse_present = spacemouse_present
            self._codex_hid_present = codex_hid_present
            self._driver_running = driver_running
            enabled = self._enabled
            suspended = self._suspended
            bridge_running = self._bridge_thread is not None and self._bridge_thread.is_alive()

        action = self.policy.observe(
            enabled=enabled,
            suspended=suspended,
            codex_present=codex_present,
            bridge_running=bridge_running,
        )
        if action == "stop":
            reason = "詳細設定のため一時停止しています" if suspended else "Codexを終了しました"
            self._request_bridge_stop(reason)
        elif action == "start" and monotonic() >= self._next_retry:
            if not spacemouse_present:
                self._next_retry = monotonic() + self.retry_interval
                self._set_status(
                    STATE_ERROR,
                    "SpaceMouseが見つかりません",
                    "SpaceMouse CompactをUSBへ接続してください。5秒後に再試行します。",
                )
            elif not codex_hid_present:
                self._next_retry = monotonic() + self.retry_interval
                recovery_requested = self._safe_probe(self.hid_recover, "virtual HID recovery")
                self._set_status(
                    STATE_ERROR,
                    "Codex Micro仮想HIDが見つかりません",
                    (
                        "自動復旧を開始しました。数秒後に再試行します。"
                        if recovery_requested
                        else "自動復旧タスクがありません。管理者権限で復旧設定を実行してください。"
                    ),
                )
            else:
                self._start_bridge()
        elif not bridge_running:
            if suspended:
                self._set_status(STATE_SUSPENDED, "詳細設定のため一時停止しています")
            elif not enabled:
                self._set_status(STATE_DISABLED, "自動連動はオフです")
                self._heal_official_driver_if_idle()
            elif not codex_present:
                self._set_status(STATE_WAITING, "Codexの起動を待っています")
                self._heal_official_driver_if_idle()
        self._emit_snapshot()

    def snapshot(self) -> ControllerSnapshot:
        with self._lock:
            return ControllerSnapshot(
                state=self._state,
                message=self._message,
                detail=self._detail,
                enabled=self._enabled,
                suspended=self._suspended,
                codex_present=self._codex_present,
                spacemouse_present=self._spacemouse_present,
                codex_hid_present=self._codex_hid_present,
                driver_running=self._driver_running,
            )

    def _monitor_loop(self) -> None:
        self.logger.info("Codex link monitor started")
        while not self._shutdown.is_set():
            self.tick()
            self._wake.wait(self.poll_interval)
            self._wake.clear()

    def _start_bridge(self) -> None:
        with self._lock:
            if not self._enabled or self._suspended or self._shutdown.is_set():
                return
            if self._bridge_thread is not None and self._bridge_thread.is_alive():
                return
            self._bridge_stop = threading.Event()
            self._state = STATE_STARTING
            self._message = "3DxWareを停止してCodexへ接続しています"
            self._detail = "初回接続には数秒かかる場合があります。"
            thread = threading.Thread(target=self._bridge_worker, name="codex-bridge", daemon=True)
            self._bridge_thread = thread
        self.logger.info("Starting SpaceMouse bridge")
        self._emit_snapshot()
        thread.start()

    def _bridge_worker(self) -> None:
        error: Exception | None = None
        try:
            config = self.config_loader(self.config_path)
            self.bridge_runner(
                config,
                stop_event=self._bridge_stop,
                pause_3dx=True,
                on_status=self._bridge_status,
                on_event=self._bridge_event,
            )
        except Exception as caught:
            error = caught
            self.logger.exception("Bridge stopped with an error")
        finally:
            requested = self._bridge_stop.is_set() or self._shutdown.is_set()
            with self._lock:
                self._bridge_thread = None
                if error is not None and not requested:
                    self._state = STATE_ERROR
                    self._message = "Bridgeを開始できませんでした"
                    self._detail = str(error)
                    self._next_retry = monotonic() + self.retry_interval
                elif self._suspended:
                    self._state = STATE_SUSPENDED
                    self._message = "詳細設定のため一時停止しています"
                    self._detail = ""
                elif not self._enabled:
                    self._state = STATE_DISABLED
                    self._message = "自動連動はオフです"
                    self._detail = ""
                else:
                    self._state = STATE_WAITING
                    self._message = "Codexの起動を待っています"
                    self._detail = ""
            self._emit_snapshot()
            self._wake.set()

    def _bridge_status(self, status: str) -> None:
        self.logger.info("Bridge status: %s", status)
        if status == "running":
            self._set_status(STATE_ACTIVE, "Codexに接続中", "SpaceMouse入力を送信しています。")

    def _bridge_event(self, event, action: str, emitted: list[str]) -> None:
        self.logger.debug("%s %s -> %s [%s]", event.edge, event.control, action, ",".join(emitted))

    def _request_bridge_stop(self, message: str) -> None:
        with self._lock:
            running = self._bridge_thread is not None and self._bridge_thread.is_alive()
            if running:
                self._bridge_stop.set()
                self._state = STATE_STOPPING
                self._message = message
                self._detail = "入力を解放し、3DxWareを復帰しています。"
        if running:
            self.logger.info("Stopping bridge: %s", message)
            self._emit_snapshot()

    def _heal_official_driver_if_idle(self) -> None:
        if self.bridge_running:
            return
        try:
            self.driver_resume()
        except Exception:
            self.logger.exception("Failed to restore 3DxWare while idle")

    def _set_status(self, state: str, message: str, detail: str = "") -> None:
        with self._lock:
            self._state = state
            self._message = message
            self._detail = detail
        self._emit_snapshot()

    def _emit_snapshot(self) -> None:
        snapshot = self.snapshot()
        with self._lock:
            if snapshot == self._last_snapshot:
                return
            self._last_snapshot = snapshot
        if self.on_snapshot is not None:
            try:
                self.on_snapshot(snapshot)
            except Exception:
                self.logger.exception("Snapshot callback failed")

    def _safe_probe(self, probe: Callable[[], bool], label: str) -> bool:
        try:
            return bool(probe())
        except Exception:
            self.logger.exception("%s probe failed", label)
            return False
