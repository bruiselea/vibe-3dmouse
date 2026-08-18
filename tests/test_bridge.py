import unittest

from spacemouse_input.bridge import ActionDispatcher
from spacemouse_input.detector import InputEvent


class FakeSender:
    def __init__(self):
        self.events = []

    def send_key(self, key, act):
        self.events.append(("key", key, act))

    def send_joystick(self, angle, distance):
        self.events.append(("joystick", angle, distance))


def event(control: str, pressed: bool) -> InputEvent:
    return InputEvent(control, pressed, 200 if pressed else 0, 1.0)


class BridgeTests(unittest.TestCase):
    def test_agent_next_cycles_and_clicks_native_agent_key(self):
        sender = FakeSender()
        dispatcher = ActionDispatcher(sender, report_spacing=0)
        dispatcher.dispatch(event("rx+", True), "agent_next")
        dispatcher.dispatch(event("rx+", False), "agent_next")
        self.assertEqual(sender.events, [("key", "AG01", 1), ("key", "AG01", 0)])

    def test_encoder_is_native_act_two_event(self):
        sender = FakeSender()
        dispatcher = ActionDispatcher(sender, report_spacing=0)
        dispatcher.dispatch(event("ry+", True), "encoder_cw")
        dispatcher.dispatch(event("ry+", False), "encoder_cw")
        self.assertEqual(sender.events, [("key", "ENC_CW", 2)])

    def test_analog_direction_returns_to_center(self):
        sender = FakeSender()
        dispatcher = ActionDispatcher(sender, report_spacing=0)
        dispatcher.dispatch(event("rz-", True), "analog_up")
        dispatcher.dispatch(event("rz-", False), "analog_up")
        self.assertEqual(
            sender.events,
            [("joystick", 0.75, 1.0), ("joystick", 0.75, 0.0)],
        )

    def test_ptt_emits_both_physical_mic_keys(self):
        sender = FakeSender()
        dispatcher = ActionDispatcher(sender, report_spacing=0)
        dispatcher.dispatch(event("tz+", True), "mic_ptt")
        dispatcher.dispatch(event("tz+", False), "mic_ptt")
        self.assertEqual(
            sender.events,
            [
                ("key", "ACT10", 1),
                ("key", "ACT11", 1),
                ("key", "ACT10", 0),
                ("key", "ACT11", 0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
