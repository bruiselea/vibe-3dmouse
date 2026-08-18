import threading
import unittest

from spacemouse_input.device import DeviceInfo, SpaceMouseDevice


class DeviceReportTests(unittest.TestCase):
    def test_reports_honors_stop_before_next_hid_read(self):
        info = DeviceInfo(b"test", 0x256F, 0xC635, "", "", "")
        device = SpaceMouseDevice(info)

        class ShouldNotRead:
            def read(self, _size):
                raise AssertionError("HID read occurred after stop")

        device._device = ShouldNotRead()  # type: ignore[assignment]
        stop_event = threading.Event()
        stop_event.set()

        self.assertEqual(list(device.reports(stop_event=stop_event)), [])


if __name__ == "__main__":
    unittest.main()
