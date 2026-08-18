"""Codex Micro compatible action catalogue."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TargetAction:
    key: str
    label: str
    codes: tuple[str, ...] = ()


TARGET_ACTIONS = (
    TargetAction("unassigned", "未割り当て"),
    TargetAction("agent_previous", "前のAgent"),
    TargetAction("agent_next", "次のAgent"),
    TargetAction("agent_1", "Agent 1", ("AG00",)),
    TargetAction("agent_2", "Agent 2", ("AG01",)),
    TargetAction("agent_3", "Agent 3", ("AG02",)),
    TargetAction("agent_4", "Agent 4", ("AG03",)),
    TargetAction("agent_5", "Agent 5", ("AG04",)),
    TargetAction("agent_6", "Agent 6", ("AG05",)),
    TargetAction("fast", "FAST 切り替え", ("ACT06",)),
    TargetAction("ok", "OK / 承認", ("ACT07",)),
    TargetAction("ng", "NG / 却下", ("ACT08",)),
    TargetAction("new_chat", "新しいチャットで続ける", ("ACT09",)),
    TargetAction("mic_ptt", "マイク / PTT", ("ACT10", "ACT11")),
    TargetAction("send", "送信", ("ACT12",)),
    TargetAction("analog_up", "Analog 上（既定: PLAN）"),
    TargetAction("analog_right", "Analog 右（既定: 履歴を進む）"),
    TargetAction("analog_down", "Analog 下（既定: サイドバー）"),
    TargetAction("analog_left", "Analog 左（既定: 履歴を戻る）"),
    TargetAction("encoder_cw", "Encoder 右回し"),
    TargetAction("encoder_ccw", "Encoder 左回し"),
)

ACTION_BY_KEY = {action.key: action for action in TARGET_ACTIONS}
ACTION_BY_LABEL = {action.label: action for action in TARGET_ACTIONS}
