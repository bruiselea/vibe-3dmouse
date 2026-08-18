import tempfile
import unittest
from pathlib import Path

from spacemouse_input.mapping import CONTROLS, MappingConfig


class MappingConfigTests(unittest.TestCase):
    def test_defaults_match_decided_controls(self):
        config = MappingConfig()
        self.assertEqual(config.assignments["tz+"], "mic_ptt")
        self.assertEqual(config.assignments["tz-"], "send")
        self.assertEqual(config.assignments["rx+"], "agent_next")
        self.assertEqual(config.assignments["ry+"], "encoder_cw")
        self.assertEqual(config.assignments["rz+"], "fast")
        self.assertEqual(config.assignments["rz-"], "analog_up")
        self.assertEqual(config.assignments["button_left"], "ng")
        self.assertEqual(config.assignments["button_right"], "ok")
        self.assertEqual(set(config.assignments), set(CONTROLS))

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            original = MappingConfig()
            original.assignments["rz+"] = "agent_1"
            original.save(path)
            loaded = MappingConfig.load(path)
        self.assertEqual(loaded.press_threshold, 180)
        self.assertEqual(loaded.release_threshold, 90)
        self.assertEqual(loaded.dominance_ratio, 1.25)
        self.assertEqual(loaded.activation_ms, 40.0)
        self.assertEqual(loaded.assignments, original.assignments)

    def test_rejects_unknown_action(self):
        config = MappingConfig()
        config.assignments["tx+"] = "not-real"
        with self.assertRaises(ValueError):
            config.validate()


if __name__ == "__main__":
    unittest.main()
