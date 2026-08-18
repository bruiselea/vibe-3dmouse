"""Tkinter control panel for mapping and running the Codex bridge."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from .actions import ACTION_BY_KEY, ACTION_BY_LABEL, TARGET_ACTIONS
from .detector import AXES, InputEvent
from .device import enumerate_devices
from .mapping import CONTROLS, CONTROL_LABELS, MappingConfig
from .protocol import enumerate_codex_devices
from .reports import SpaceMouseState
from .runtime import run_bridge


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "mapping.json"
DEVICE_ART_PATH = Path(__file__).resolve().parent / "assets" / "vibe-6dof.png"
LEFT_CALLOUTS = (
    ("tz-", "↑  Z− 引き上げ"),
    ("rz-", "↺  左ひねり"),
    ("ty-", "↖  Y− スライド"),
    ("tx-", "←  X− スライド"),
    ("rx-", "↶  X− 傾き"),
    ("ry-", "↶  Y− 傾き"),
    ("button_left", "●  左ボタン"),
)
RIGHT_CALLOUTS = (
    ("tz+", "Z+ 押し込み  ↓"),
    ("rz+", "右ひねり  ↻"),
    ("ty+", "Y+ スライド  ↘"),
    ("tx+", "X+ スライド  →"),
    ("rx+", "X+ 傾き  ↷"),
    ("ry+", "Y+ 傾き  ↷"),
    ("button_right", "右ボタン  ●"),
)


class SpaceMouseDiagram(ttk.Frame):
    """Clickable vector illustration with one callout for each physical input."""

    def __init__(
        self,
        parent: tk.Widget,
        assignments: dict[str, tk.StringVar],
        on_select,
    ) -> None:
        super().__init__(parent)
        self.assignments = assignments
        self.on_select = on_select
        self.selected = "tz+"
        self.active: set[str] = set()
        self.values = {control: 0 for control in CONTROLS}
        self.canvas = tk.Canvas(
            self,
            background="#f7f8fa",
            highlightthickness=0,
            width=850,
            height=610,
        )
        self.asset_source: tk.PhotoImage | None = None
        self.device_art: tk.PhotoImage | None = None
        try:
            self.asset_source = tk.PhotoImage(file=str(DEVICE_ART_PATH))
            self.device_art = self.asset_source.subsample(4, 4)
        except tk.TclError:
            # The vector-like Canvas drawing below remains as a safe fallback.
            pass
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.draw())

    def select(self, control: str) -> None:
        self.selected = control
        self.draw()

    def update_state(self, state: SpaceMouseState) -> None:
        for axis in AXES:
            value = getattr(state, axis)
            self.values[f"{axis}+"] = max(value, 0)
            self.values[f"{axis}-"] = max(-value, 0)
        self.values["button_left"] = 1 if state.buttons & 1 else 0
        self.values["button_right"] = 1 if state.buttons & 2 else 0
        self.draw()

    def update_event(self, event: InputEvent) -> None:
        if event.pressed:
            self.active.add(event.control)
        else:
            self.active.discard(event.control)
        self.draw()

    def clear_live_state(self) -> None:
        self.active.clear()
        for control in self.values:
            self.values[control] = 0
        self.draw()

    def draw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 760)
        height = max(canvas.winfo_height(), 560)
        cx = width / 2
        cy = height * 0.48
        ink = "#3f4854"
        faint = "#9aa4af"

        # SpaceMouse base and cap: intentionally simple line art, not a photo.
        canvas.create_oval(cx - 150, cy + 80, cx + 150, cy + 190, outline=ink, width=3)
        canvas.create_arc(
            cx - 150, cy + 25, cx + 150, cy + 150,
            start=180, extent=180, style="arc", outline=ink, width=3,
        )
        canvas.create_line(cx - 150, cy + 84, cx - 150, cy + 120, fill=ink, width=3)
        canvas.create_line(cx + 150, cy + 84, cx + 150, cy + 120, fill=ink, width=3)
        canvas.create_oval(cx - 91, cy - 118, cx + 91, cy - 46, outline=ink, width=3)
        canvas.create_line(cx - 91, cy - 82, cx - 91, cy + 55, fill=ink, width=3)
        canvas.create_line(cx + 91, cy - 82, cx + 91, cy + 55, fill=ink, width=3)
        canvas.create_arc(
            cx - 91, cy + 18, cx + 91, cy + 88,
            start=180, extent=180, style="arc", outline=ink, width=3,
        )
        canvas.create_arc(cx - 71, cy - 101, cx + 71, cy - 58, outline=faint, width=2)
        canvas.create_oval(cx - 118, cy + 102, cx - 65, cy + 126, outline=ink, width=2)
        canvas.create_oval(cx + 65, cy + 102, cx + 118, cy + 126, outline=ink, width=2)

        # Motion hints around the cap.
        canvas.create_line(cx - 126, cy - 12, cx + 126, cy - 12, fill=faint, width=2, arrow="both")
        canvas.create_line(cx, cy - 151, cx, cy - 34, fill=faint, width=2, arrow="both")
        canvas.create_arc(
            cx - 126, cy - 143, cx + 126, cy - 15,
            start=24, extent=132, style="arc", outline=faint, width=2,
        )
        canvas.create_text(cx, cy + 158, text="SpaceMouse", fill=faint, font=("Segoe UI", 10, "bold"))

        if self.device_art is not None:
            # Cover the fallback drawing and place the generated transparent asset.
            canvas.create_rectangle(
                cx - 196,
                cy - 164,
                cx + 196,
                cy + 196,
                fill="#f7f8fa",
                outline="",
            )
            canvas.create_image(cx, cy + 28, image=self.device_art, anchor="center")

        row_gap = (height - 44) / 7
        box_width = min(225, max(195, width * 0.26))
        box_height = min(58, row_gap - 7)
        left_x1, left_x2 = 12, 12 + box_width
        right_x1, right_x2 = width - 12 - box_width, width - 12

        left_anchors = (
            (cx, cy - 92), (cx - 100, cy - 58), (cx - 110, cy - 35),
            (cx - 130, cy), (cx - 125, cy + 35), (cx - 115, cy + 65),
            (cx - 145, cy + 45),
        )
        right_anchors = (
            (cx, cy - 92), (cx + 100, cy - 58), (cx + 110, cy - 35),
            (cx + 130, cy), (cx + 125, cy + 35), (cx + 115, cy + 65),
            (cx + 145, cy + 45),
        )

        for index, ((control, gesture), anchor) in enumerate(zip(LEFT_CALLOUTS, left_anchors)):
            y1 = 14 + index * row_gap
            self._draw_callout(control, gesture, left_x1, y1, left_x2, y1 + box_height, anchor, "left")
        for index, ((control, gesture), anchor) in enumerate(zip(RIGHT_CALLOUTS, right_anchors)):
            y1 = 14 + index * row_gap
            self._draw_callout(control, gesture, right_x1, y1, right_x2, y1 + box_height, anchor, "right")

        canvas.create_text(
            cx,
            height - 12,
            text="吹き出しをクリックして割り当て  •  緑: 入力中  •  青: 編集対象",
            fill="#66717d",
            font=("Segoe UI", 9),
        )

    def _draw_callout(
        self,
        control: str,
        gesture: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        anchor: tuple[float, float],
        side: str,
    ) -> None:
        selected = control == self.selected
        active = control in self.active
        outline = "#16a05d" if active else "#1777d2" if selected else "#a8b1bb"
        fill = "#e4f7ec" if active else "#eaf3fc" if selected else "#ffffff"
        width = 3 if active or selected else 1
        line_x = x2 if side == "left" else x1
        self.canvas.create_line(
            line_x, (y1 + y2) / 2, anchor[0], anchor[1], fill=outline, width=width
        )
        tag = f"control:{control}"
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width, tags=tag)
        text_x = x1 + 11 if side == "left" else x2 - 11
        anchor_name = "w" if side == "left" else "e"
        self.canvas.create_text(
            text_x, y1 + 16, text=f"{gesture}   {control}", anchor=anchor_name,
            fill="#26313d", font=("Segoe UI", 9, "bold"), tags=tag,
        )
        action = self.assignments[control].get()
        if len(action) > 25:
            action = action[:24] + "…"
        value = self.values[control]
        suffix = f"  [{value}]" if value else ""
        self.canvas.create_text(
            text_x, y1 + 38, text=f"→ {action}{suffix}", anchor=anchor_name,
            fill="#52606d", font=("Segoe UI", 9), tags=tag,
        )
        self.canvas.tag_bind(tag, "<Button-1>", lambda _event, c=control: self.on_select(c))
        self.canvas.tag_bind(tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))


class MappingApp:
    def __init__(self, root: tk.Tk, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        self.root = root
        self.config_path = config_path
        self.root.title("Vibe SpaceMouse Mapper for Codex")
        self.root.geometry("1280x900")
        self.root.minsize(1120, 760)

        self.config = self._load_or_default()
        self.active_config = self.config
        self.assignment_vars = {
            control: tk.StringVar(value=ACTION_BY_KEY[self.config.assignments[control]].label)
            for control in CONTROLS
        }
        self.editable_widgets: list[tk.Widget] = []
        self.message_queue: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1024)
        self.bridge_stop_event = threading.Event()
        self.bridge_thread: threading.Thread | None = None
        self.closing = False
        self.applying_config = False

        self.press_var = tk.IntVar(value=self.config.press_threshold)
        self.release_var = tk.IntVar(value=self.config.release_threshold)
        self.dominance_var = tk.DoubleVar(value=self.config.dominance_ratio)
        self.activation_var = tk.DoubleVar(value=self.config.activation_ms)
        self.device_var = tk.StringVar(value="デバイスを確認中…")
        self.bridge_var = tk.StringVar(value="停止中")
        self.event_var = tk.StringVar(value="Bridgeを開始すると入力を確認できます")
        self.dirty_var = tk.StringVar(value="保存済み")
        self.selected_control = "tz+"
        self.selected_title_var = tk.StringVar()
        self.selected_action_var = tk.StringVar()
        self.selected_code_var = tk.StringVar()

        self._build_ui()
        self._bind_dirty_tracking()
        self._refresh_device_status()
        self.root.after(25, self._drain_messages)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _load_or_default(self) -> MappingConfig:
        if self.config_path.exists():
            try:
                return MappingConfig.load(self.config_path)
            except (OSError, ValueError):
                pass
        return MappingConfig()

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Running.TLabel", foreground="#16803a", font=("Segoe UI", 10, "bold"))
        style.configure("Stopped.TLabel", foreground="#666666", font=("Segoe UI", 10, "bold"))
        style.configure("Active.TLabel", foreground="#0878d1", font=("Segoe UI", 9, "bold"))
        style.configure("Dirty.TLabel", foreground="#b05a00")

        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 12))
        title_area = ttk.Frame(header)
        title_area.pack(side="left", fill="x", expand=True)
        ttk.Label(title_area, text="SpaceMouse → Codex Micro", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_area, textvariable=self.device_var).pack(anchor="w", pady=(2, 0))

        self.start_button = ttk.Button(header, text="▶  Bridge開始", command=self.start_bridge, width=17)
        self.start_button.pack(side="left", padx=(8, 5), ipady=5)
        self.stop_button = ttk.Button(
            header, text="■  停止", command=self.stop_bridge, state="disabled", width=11
        )
        self.stop_button.pack(side="left", padx=5, ipady=5)
        self.bridge_status_label = ttk.Label(
            header, textvariable=self.bridge_var, style="Stopped.TLabel", width=14
        )
        self.bridge_status_label.pack(side="left", padx=(10, 0))

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, minsize=305)
        body.rowconfigure(0, weight=1)

        diagram_frame = ttk.LabelFrame(body, text="操作する方向をクリック", padding=4)
        diagram_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.diagram = SpaceMouseDiagram(diagram_frame, self.assignment_vars, self._select_control)
        self.diagram.pack(fill="both", expand=True)

        side = ttk.Frame(body)
        side.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._build_assignment_editor(side)
        self._build_settings(side)
        self._build_event_panel(side)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(12, 0))
        self.save_button = ttk.Button(footer, text="設定を保存", command=self.save)
        self.save_button.pack(side="left")
        self.reload_button = ttk.Button(footer, text="再読込", command=self.reload)
        self.reload_button.pack(side="left", padx=6)
        self.defaults_button = ttk.Button(footer, text="既定値に戻す", command=self.reset_defaults)
        self.defaults_button.pack(side="left")
        ttk.Label(footer, textvariable=self.dirty_var, style="Dirty.TLabel").pack(
            side="left", padx=12
        )
        ttk.Label(footer, text=str(self.config_path)).pack(side="right")
        self.editable_widgets.extend((self.save_button, self.reload_button, self.defaults_button))

        self._select_control(self.selected_control)

    def _build_assignment_editor(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="選択した入力", padding=11)
        frame.pack(fill="x")
        ttk.Label(frame, textvariable=self.selected_title_var, style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, textvariable=self.selected_code_var, foreground="#66717d").pack(
            anchor="w", pady=(2, 9)
        )
        combo = ttk.Combobox(
            frame,
            textvariable=self.selected_action_var,
            values=[action.label for action in TARGET_ACTIONS],
            state="readonly",
            width=30,
        )
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", self._assignment_changed)
        self.editable_widgets.append(combo)

    def _select_control(self, control: str) -> None:
        self.selected_control = control
        self.selected_title_var.set(CONTROL_LABELS[control])
        self.selected_action_var.set(self.assignment_vars[control].get())
        self._update_selected_code()
        self.diagram.select(control)

    def _assignment_changed(self, *_: object) -> None:
        self.assignment_vars[self.selected_control].set(self.selected_action_var.get())
        self._update_selected_code()
        self.diagram.draw()
        self._mark_dirty()

    def _update_selected_code(self) -> None:
        action = ACTION_BY_LABEL[self.selected_action_var.get()]
        codes = " + ".join(action.codes) if action.codes else action.key
        self.selected_code_var.set(f"{self.selected_control}  →  {codes}")

    def _build_settings(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="入力判定", padding=10)
        frame.pack(fill="x", pady=(10, 0))
        fields = (
            ("DOWN 閾値", self.press_var, 1, 1000, 1, "これ以上で入力候補"),
            ("UP 閾値", self.release_var, 0, 999, 1, "中央へ戻った判定"),
            ("優先軸比率", self.dominance_var, 1.0, 5.0, 0.05, "他軸との混入を除外"),
            ("入力継続 ms", self.activation_var, 0, 500, 5, "誤発火を抑える待ち時間"),
        )
        for row, (label, variable, minimum, maximum, increment, help_text) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row * 2, column=0, sticky="w", pady=(4, 0))
            spinbox = ttk.Spinbox(
                frame,
                from_=minimum,
                to=maximum,
                increment=increment,
                textvariable=variable,
                width=9,
            )
            spinbox.grid(row=row * 2, column=1, sticky="e", pady=(4, 0))
            ttk.Label(frame, text=help_text, foreground="#666666").grid(
                row=row * 2 + 1, column=0, columnspan=2, sticky="w", pady=(0, 4)
            )
            self.editable_widgets.append(spinbox)
        frame.columnconfigure(0, weight=1)

        hint = ttk.LabelFrame(parent, text="動作", padding=10)
        hint.pack(fill="x", pady=(10, 0))
        ttk.Label(
            hint,
            text=(
                "開始時に設定を保存し、3DxWareを一時停止します。\n"
                "停止時・画面終了時に3DxWareを自動復帰します。"
            ),
            wraplength=260,
            justify="left",
        ).pack(anchor="w")

    def _build_event_panel(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="ライブ入力", padding=10)
        frame.pack(fill="both", expand=True, pady=(10, 0))
        ttk.Label(frame, textvariable=self.event_var, wraplength=260, justify="left").pack(
            fill="x", anchor="w", pady=(0, 7)
        )
        self.event_tree = ttk.Treeview(
            frame,
            columns=("input", "action"),
            show="headings",
            height=9,
            selectmode="none",
        )
        self.event_tree.heading("input", text="入力")
        self.event_tree.heading("action", text="操作")
        self.event_tree.column("input", width=78, stretch=False)
        self.event_tree.column("action", width=165, stretch=True)
        self.event_tree.pack(fill="both", expand=True)

    def _bind_dirty_tracking(self) -> None:
        for variable in (
            self.press_var,
            self.release_var,
            self.dominance_var,
            self.activation_var,
        ):
            variable.trace_add("write", self._mark_dirty)

    def _mark_dirty(self, *_: object) -> None:
        if not self.applying_config:
            self.dirty_var.set("未保存の変更あり")

    def _refresh_device_status(self) -> None:
        physical = enumerate_devices()
        virtual = enumerate_codex_devices()
        if physical and virtual:
            self.device_var.set("SpaceMouse / Codex Micro HID を検出済み")
            self.start_button.configure(state="normal")
        else:
            missing = []
            if not physical:
                missing.append("SpaceMouse")
            if not virtual:
                missing.append("Codex Micro HID")
            self.device_var.set("未検出: " + " / ".join(missing))
            self.start_button.configure(state="disabled")

    def _config_from_ui(self) -> MappingConfig:
        assignments = {
            control: ACTION_BY_LABEL[variable.get()].key
            for control, variable in self.assignment_vars.items()
        }
        config = MappingConfig(
            press_threshold=self.press_var.get(),
            release_threshold=self.release_var.get(),
            dominance_ratio=self.dominance_var.get(),
            activation_ms=self.activation_var.get(),
            assignments=assignments,
        )
        config.validate()
        return config

    def save(self, notify: bool = True) -> bool:
        try:
            self.config = self._config_from_ui()
            self.config.save(self.config_path)
        except (OSError, ValueError, tk.TclError) as error:
            messagebox.showerror("保存エラー", str(error), parent=self.root)
            return False
        self.dirty_var.set("保存済み")
        if notify:
            self.event_var.set("設定を保存しました")
        return True

    def reload(self) -> None:
        try:
            self.config = MappingConfig.load(self.config_path)
        except (OSError, ValueError) as error:
            messagebox.showerror("読込エラー", str(error), parent=self.root)
            return
        self._apply_config_to_ui()
        self.dirty_var.set("保存済み")

    def reset_defaults(self) -> None:
        self.config = MappingConfig()
        self._apply_config_to_ui()
        self.dirty_var.set("未保存の変更あり")

    def _apply_config_to_ui(self) -> None:
        self.applying_config = True
        try:
            self.press_var.set(self.config.press_threshold)
            self.release_var.set(self.config.release_threshold)
            self.dominance_var.set(self.config.dominance_ratio)
            self.activation_var.set(self.config.activation_ms)
            for control, variable in self.assignment_vars.items():
                variable.set(ACTION_BY_KEY[self.config.assignments[control]].label)
            self.selected_action_var.set(self.assignment_vars[self.selected_control].get())
            self._update_selected_code()
            self.diagram.draw()
        finally:
            self.applying_config = False

    def start_bridge(self) -> None:
        if self.bridge_thread is not None and self.bridge_thread.is_alive():
            return
        if not self.save(notify=False):
            return
        self.active_config = self.config
        self.bridge_stop_event.clear()
        self._set_running(True)
        self.bridge_var.set("接続中…")
        self.event_var.set("3DxWareを停止してHIDへ接続しています…")
        self._clear_live_state()
        self.bridge_thread = threading.Thread(target=self._bridge_worker, name="codex-bridge")
        self.bridge_thread.start()

    def _bridge_worker(self) -> None:
        try:
            run_bridge(
                self.active_config,
                stop_event=self.bridge_stop_event,
                pause_3dx=True,
                on_state=lambda state: self._put_message(("state", state)),
                on_event=lambda event, action, emitted: self._put_message(
                    ("event", (event, action, emitted))
                ),
                on_status=lambda status: self._put_message(("status", status)),
            )
        except Exception as error:
            self._put_message(("error", str(error)))
        finally:
            self._put_message(("stopped", None))

    def stop_bridge(self) -> None:
        if self.bridge_thread is None or not self.bridge_thread.is_alive():
            return
        self.bridge_stop_event.set()
        self.bridge_var.set("停止処理中…")
        self.stop_button.configure(state="disabled")
        self.event_var.set("入力を解放し、3DxWareを復帰しています…")

    def _set_running(self, running: bool) -> None:
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        self.bridge_status_label.configure(
            style="Running.TLabel" if running else "Stopped.TLabel"
        )
        for widget in self.editable_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="disabled" if running else "readonly")
            else:
                widget.configure(state="disabled" if running else "normal")

    def _put_message(self, message: tuple[str, object]) -> None:
        try:
            self.message_queue.put_nowait(message)
        except queue.Full:
            pass

    def _drain_messages(self) -> None:
        latest_state: SpaceMouseState | None = None
        while True:
            try:
                kind, payload = self.message_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "state":
                latest_state = payload  # type: ignore[assignment]
            elif kind == "event":
                event, action, emitted = payload  # type: ignore[misc]
                self._show_event(event, action, emitted)
            elif kind == "status":
                if payload == "running":
                    self.bridge_var.set("● 動作中")
                    self.event_var.set("入力待機中")
                else:
                    self.event_var.set(str(payload))
            elif kind == "error":
                self.bridge_var.set("エラー")
                self.event_var.set(f"Bridgeエラー: {payload}")
                if not self.closing:
                    messagebox.showerror("Bridgeエラー", str(payload), parent=self.root)
            elif kind == "stopped":
                self.bridge_thread = None
                if self.closing:
                    self.root.destroy()
                    return
                self._set_running(False)
                if self.bridge_var.get() != "エラー":
                    self.bridge_var.set("停止中")
                    self.event_var.set("停止しました。3DxWareは復帰済みです")
                self.root.after(100, self._refresh_device_status)
        if latest_state is not None:
            self._show_state(latest_state)
        self.root.after(25, self._drain_messages)

    def _show_state(self, state: SpaceMouseState) -> None:
        self.diagram.update_state(state)

    def _show_event(self, event: InputEvent, action_key: str, emitted: list[str]) -> None:
        label = ACTION_BY_KEY[action_key].label
        self.diagram.update_event(event)
        codes = "+".join(emitted) if emitted else "—"
        self.event_var.set(
            f"{event.edge}  {CONTROL_LABELS[event.control]} → {label}  [{codes}]"
        )
        stamp = datetime.now().strftime("%H:%M:%S")
        self.event_tree.insert("", 0, values=(f"{stamp} {event.control}", label))
        children = self.event_tree.get_children()
        for item in children[12:]:
            self.event_tree.delete(item)

    def _clear_live_state(self) -> None:
        self.diagram.clear_live_state()
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)

    def close(self) -> None:
        if self.closing:
            return
        if self.bridge_thread is not None and self.bridge_thread.is_alive():
            self.closing = True
            self.root.title("Vibe SpaceMouse Mapper for Codex — 終了処理中")
            self.stop_bridge()
            return
        self.root.destroy()


def run_gui() -> None:
    root = tk.Tk()
    MappingApp(root)
    root.mainloop()
