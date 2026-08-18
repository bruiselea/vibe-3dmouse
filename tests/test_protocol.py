import json
import unittest
from unittest.mock import patch

from spacemouse_input.protocol import (
    build_joystick_report,
    build_key_report,
    enumerate_codex_devices,
)


def decode_report(report: bytes) -> dict:
    assert len(report) == 64
    assert report[0] == 6
    assert report[1] == 2
    size = report[2]
    return json.loads(report[3 : 3 + size].decode("ascii"))


class ProtocolTests(unittest.TestCase):
    @patch("spacemouse_input.protocol.hid.enumerate")
    def test_native_codex_path_is_preferred(self, enumerate_hid):
        common = {
            "vendor_id": 0x303A,
            "product_id": 0x8360,
            "manufacturer_string": "test",
            "product_string": "test",
            "usage_page": 0xFF00,
            "usage": 1,
        }
        enumerate_hid.return_value = [
            {**common, "path": b"hid#hidclass&col04"},
            {**common, "path": b"hid#vid_303a&pid_8360&col04"},
        ]
        devices = enumerate_codex_devices()
        self.assertTrue(devices[0].native_codex_compatible)

    def test_key_report_matches_vibewatch_wire_format(self):
        report = build_key_report("ACT07", 1)
        self.assertEqual(len(report), 64)
        self.assertEqual(
            report[3 : 3 + report[2]],
            b'{"m":"v.oai.hid","p":{"k":"ACT07","act":1}}\r\n',
        )
        self.assertEqual(decode_report(report)["p"], {"k": "ACT07", "act": 1})

    def test_encoder_step_uses_act_two(self):
        report = build_key_report("ENC_CW", 2)
        self.assertEqual(decode_report(report)["p"], {"k": "ENC_CW", "act": 2})

    def test_joystick_uses_compact_device_kit_keys(self):
        down = decode_report(build_joystick_report(0.75, 1.0))
        center = decode_report(build_joystick_report(0.75, 0.0))
        self.assertEqual(down, {"m": "v.oai.rad", "p": {"a": 0.75, "d": 1.0}})
        self.assertEqual(center["p"]["d"], 0.0)


if __name__ == "__main__":
    unittest.main()
