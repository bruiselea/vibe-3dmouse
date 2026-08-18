import unittest

from spacemouse_input.detector import InputDetector
from spacemouse_input.reports import SpaceMouseState, parse_report


class ReportTests(unittest.TestCase):
    def test_translation_report_decodes_signed_little_endian(self):
        state = parse_report(bytes([1, 200, 0, 56, 255, 0, 0]), SpaceMouseState())
        self.assertEqual((state.tx, state.ty, state.tz), (200, -200, 0))

    def test_rotation_and_buttons_preserve_other_state(self):
        initial = SpaceMouseState(tx=10, ty=20, tz=30)
        rotated = parse_report(bytes([2, 1, 0, 2, 0, 3, 0]), initial)
        pressed = parse_report(bytes([3, 3]), rotated)
        self.assertEqual((pressed.tx, pressed.rx, pressed.ry, pressed.rz), (10, 1, 2, 3))
        self.assertEqual(pressed.buttons, 3)


class DetectorTests(unittest.TestCase):
    def test_axis_hysteresis(self):
        detector = InputDetector(press_threshold=180, release_threshold=100, activation_delay=0)
        self.assertEqual(detector.update(SpaceMouseState(tx=179)), [])
        events = detector.update(SpaceMouseState(tx=180))
        self.assertEqual([(event.control, event.pressed) for event in events], [("tx+", True)])
        self.assertEqual(detector.update(SpaceMouseState(tx=120)), [])
        events = detector.update(SpaceMouseState(tx=99))
        self.assertEqual([(event.control, event.pressed) for event in events], [("tx+", False)])

    def test_direction_change_releases_then_presses(self):
        detector = InputDetector(press_threshold=180, release_threshold=100, activation_delay=0)
        detector.update(SpaceMouseState(rz=250))
        events = detector.update(SpaceMouseState(rz=-250))
        self.assertEqual([(event.control, event.pressed) for event in events], [("rz+", False)])
        events = detector.update(SpaceMouseState(rz=-250))
        self.assertEqual([(event.control, event.pressed) for event in events], [("rz-", True)])

    def test_two_buttons_are_independent(self):
        detector = InputDetector()
        events = detector.update(SpaceMouseState(buttons=3))
        self.assertEqual(
            [(event.control, event.pressed) for event in events],
            [("button_left", True), ("button_right", True)],
        )
        events = detector.update(SpaceMouseState(buttons=2))
        self.assertEqual([(event.control, event.pressed) for event in events], [("button_left", False)])

    def test_dominant_axis_blocks_calibrated_crosstalk(self):
        detector = InputDetector(activation_delay=0)
        events = detector.update(SpaceMouseState(ty=350, tz=220, ry=142))
        self.assertEqual([(event.control, event.pressed) for event in events], [("ty+", True)])

    def test_ambiguous_axes_do_not_trigger(self):
        detector = InputDetector(activation_delay=0)
        events = detector.update(SpaceMouseState(tx=200, ty=190))
        self.assertEqual(events, [])

    def test_default_activation_delay_filters_short_spike(self):
        detector = InputDetector()
        self.assertEqual(detector.update(SpaceMouseState(rx=300), timestamp=1.0), [])
        self.assertEqual(detector.update(SpaceMouseState(rx=0), timestamp=1.02), [])
        self.assertEqual(detector.update(SpaceMouseState(rx=300), timestamp=2.0), [])
        events = detector.update(SpaceMouseState(rx=300), timestamp=2.04)
        self.assertEqual([(event.control, event.pressed) for event in events], [("rx+", True)])


if __name__ == "__main__":
    unittest.main()
