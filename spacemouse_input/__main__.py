"""Command-line monitor for SpaceMouse input detection."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from time import monotonic

from .detector import AXES, InputDetector
from .device import SpaceMouseDevice, enumerate_devices
from .mapping import MappingConfig
from .official_driver import driver_is_running, pause_driver, resume_driver
from .protocol import CodexMicroDevice, build_key_report, enumerate_codex_devices
from .reports import SpaceMouseState, parse_report
from .runtime import run_bridge


def _device_or_exit():
    devices = enumerate_devices()
    if not devices:
        raise SystemExit("SpaceMouse Compact (256F:C635) が見つかりません。")
    return devices[0]


def list_devices() -> int:
    devices = enumerate_devices()
    if not devices:
        print("SpaceMouse Compact (256F:C635) が見つかりません。")
        return 1
    for index, device in enumerate(devices):
        print(f"[{index}] {device.manufacturer} {device.product} ({device.identifier})")
    return 0


def list_codex_devices() -> int:
    devices = enumerate_codex_devices()
    if not devices:
        print("Codex Micro互換HID (303A:8360) が見つかりません。")
        return 1
    for index, device in enumerate(devices):
        compatibility = " native-path" if device.native_codex_compatible else " legacy-path"
        print(
            f"[{index}] {device.manufacturer} {device.product} "
            f"usage={device.usage_page:04X}:{device.usage:04X}{compatibility}"
        )
    return 0


def send_codex_event(args: argparse.Namespace) -> int:
    devices = enumerate_codex_devices()
    if not devices:
        print("Codex Micro互換HID (303A:8360) が見つかりません。", file=sys.stderr)
        return 1
    # Validate before opening the device so errors are immediate and readable.
    build_key_report(args.key, args.act)
    with CodexMicroDevice(devices[0]) as device:
        device.send_key(args.key, args.act)
    print(f"HID {args.key} act={args.act} を送信しました。")
    return 0


def bridge(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    config = MappingConfig.load(config_path)
    print(f"SpaceMouse -> Codex Micro を開始: {config_path}")
    print("Ctrl+C で終了")

    def show_status(status: str) -> None:
        if status == "3DxWareを一時停止":
            print("3DxWareを一時停止しました。bridge終了時に自動で再開します。")

    def show_event(event, action: str, emitted: list[str]) -> None:
        codes = ",".join(emitted) if emitted else "-"
        print(f"{event.edge:<4} {event.control:<12} -> {action:<16} [{codes}]")

    try:
        run_bridge(
            config,
            pause_3dx=args.pause_3dx,
            seconds=args.seconds,
            on_event=show_event,
            on_status=show_status,
        )
    except KeyboardInterrupt:
        print("\n終了しました。")
    except OSError as error:
        print(f"HIDを開けませんでした: {error}", file=sys.stderr)
        return 2
    return 0


def manage_3dx(args: argparse.Namespace) -> int:
    try:
        if args.action == "status":
            print("3DxWare: running" if driver_is_running() else "3DxWare: stopped")
        elif args.action == "pause":
            changed = pause_driver()
            print("3DxWareを一時停止しました。" if changed else "3DxWareはすでに停止しています。")
        else:
            changed = resume_driver()
            print("3DxWareを再開しました。" if changed else "3DxWareはすでに動作しています。")
    except (FileNotFoundError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"3DxWare操作に失敗しました: {error}", file=sys.stderr)
        return 3
    return 0


def monitor(args: argparse.Namespace) -> int:
    info = _device_or_exit()
    detector = InputDetector(
        args.threshold,
        args.release_threshold,
        dominance_ratio=args.dominance_ratio,
        activation_delay=args.activation_ms / 1000.0,
    )
    state = SpaceMouseState()
    minima = {axis: 0 for axis in AXES}
    maxima = {axis: 0 for axis in AXES}
    detected_controls: set[str] = set()
    deadline = monotonic() + args.seconds if args.seconds is not None else None
    print(f"接続: {info.manufacturer} {info.product} ({info.identifier})")
    print(
        f"判定: DOWN >= {args.threshold}, UP < {args.release_threshold}, "
        f"優先比 {args.dominance_ratio:.2f}, 継続 {args.activation_ms}ms | "
        "Ctrl+C で終了"
    )

    try:
        with SpaceMouseDevice(info) as device:
            for report in device.reports(deadline):
                try:
                    state = parse_report(report, state)
                except ValueError as error:
                    if args.raw:
                        print(f"RAW? {report.hex(' ')} ({error})")
                    continue

                for axis in AXES:
                    value = getattr(state, axis)
                    minima[axis] = min(minima[axis], value)
                    maxima[axis] = max(maxima[axis], value)

                if args.raw:
                    axes = " ".join(f"{axis}={getattr(state, axis):+5d}" for axis in AXES)
                    print(f"RAW {report.hex(' '):<24} | {axes} buttons={state.buttons:02b}")

                for event in detector.update(state):
                    print(f"INPUT {event.edge:<4} {event.control:<12} value={event.value:+d}")
                    if event.pressed:
                        detected_controls.add(event.control)
            if deadline is not None:
                print("採取時間が終了しました。")
    except KeyboardInterrupt:
        print("\n終了しました。")
    except OSError as error:
        print(f"SpaceMouseを開けませんでした: {error}", file=sys.stderr)
        return 2
    print("軸範囲: " + " ".join(f"{axis}={minima[axis]:+d}..{maxima[axis]:+d}" for axis in AXES))
    detected = ", ".join(sorted(detected_controls)) if detected_controls else "なし"
    print(f"検出入力: {detected}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SpaceMouse 14入力判定モニター")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="対応デバイスを一覧表示")
    subparsers.add_parser("codex-list", help="Codex Micro互換HIDを一覧表示")
    subparsers.add_parser("gui", help="入力割り当てGUIを開く")
    release_parser = subparsers.add_parser("release", help="配布版ダッシュボードを開く")
    release_parser.add_argument("--background", action="store_true", help="タスクトレイへ最小化")
    bridge_parser = subparsers.add_parser("bridge", help="SpaceMouse入力をCodexへ直接送信")
    bridge_parser.add_argument("--config", default="config/mapping.json")
    bridge_parser.add_argument("--seconds", type=float)
    driver_mode = bridge_parser.add_mutually_exclusive_group()
    driver_mode.add_argument(
        "--pause-3dx",
        dest="pause_3dx",
        action="store_true",
        default=True,
        help="bridge中だけ公式3DxWareを止め、終了時に自動復帰（既定）",
    )
    driver_mode.add_argument(
        "--keep-3dx",
        dest="pause_3dx",
        action="store_false",
        help="公式3DxWareを停止せずbridgeと共存させる",
    )
    driver_parser = subparsers.add_parser("3dx", help="公式3DxWareを一時停止・再開")
    driver_parser.add_argument("action", choices=("status", "pause", "resume"))
    send_parser = subparsers.add_parser("send", help="Codex Microキーイベントを1件送信")
    send_parser.add_argument("key", help="AG00..AG05 / ACT06..ACT12 / ENC_CW / ENC_CC")
    send_parser.add_argument("--act", type=int, choices=(0, 1, 2), default=1)
    monitor_parser = subparsers.add_parser("monitor", help="入力を監視")
    monitor_parser.add_argument("--threshold", type=int, default=180, help="DOWN判定値")
    monitor_parser.add_argument(
        "--release-threshold", type=int, default=90, help="UP判定値（DOWNより小さくする）"
    )
    monitor_parser.add_argument(
        "--dominance-ratio", type=float, default=1.25, help="最大軸に必要な次点軸との比率"
    )
    monitor_parser.add_argument(
        "--activation-ms", type=float, default=40.0, help="DOWNまで同じ方向を保つ時間"
    )
    monitor_parser.add_argument("--raw", action="store_true", help="HIDレポートと6軸値も表示")
    monitor_parser.add_argument(
        "--seconds", type=float, help="指定秒数で自動終了（省略時はCtrl+Cまで継続）"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "list":
        return list_devices()
    if args.command == "codex-list":
        return list_codex_devices()
    if args.command == "gui":
        from .gui import run_gui

        run_gui()
        return 0
    if args.command == "release":
        from .release_app import main as release_main

        return release_main(["--background"] if args.background else [])
    if args.command == "bridge":
        return bridge(args)
    if args.command == "3dx":
        return manage_3dx(args)
    if args.command == "send":
        return send_codex_event(args)
    return monitor(args)


if __name__ == "__main__":
    raise SystemExit(main())
