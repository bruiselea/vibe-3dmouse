import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from spacemouse_input.release_controller import (
    STATE_ACTIVE,
    STATE_ERROR,
    BridgeController,
    CodexLinkPolicy,
)


class MutableProbe:
    def __init__(self, value=False):
        self.value = value

    def __call__(self):
        return self.value


class ReleasePolicyTests(unittest.TestCase):
    def test_starts_when_codex_is_present(self):
        policy = CodexLinkPolicy(missing_limit=5)
        self.assertEqual(
            policy.observe(
                enabled=True,
                suspended=False,
                codex_present=True,
                bridge_running=False,
            ),
            "start",
        )

    def test_five_missing_samples_are_required_before_stop(self):
        policy = CodexLinkPolicy(missing_limit=5)
        for _ in range(4):
            action = policy.observe(
                enabled=True,
                suspended=False,
                codex_present=False,
                bridge_running=True,
            )
            self.assertEqual(action, "none")
        self.assertEqual(
            policy.observe(
                enabled=True,
                suspended=False,
                codex_present=False,
                bridge_running=True,
            ),
            "stop",
        )

    def test_suspend_stops_immediately(self):
        policy = CodexLinkPolicy()
        self.assertEqual(
            policy.observe(
                enabled=True,
                suspended=True,
                codex_present=True,
                bridge_running=True,
            ),
            "stop",
        )


class ReleaseControllerTests(unittest.TestCase):
    def make_controller(self, **overrides):
        defaults = dict(
            config_path=Path("mapping.json"),
            poll_interval=0.01,
            retry_interval=0.01,
            codex_probe=lambda: True,
            spacemouse_probe=lambda: True,
            codex_hid_probe=lambda: True,
            driver_probe=lambda: True,
            driver_resume=lambda: False,
            config_loader=lambda _path: object(),
        )
        defaults.update(overrides)
        return BridgeController(**defaults)

    def test_missing_spacemouse_does_not_start_bridge(self):
        runner = Mock()
        controller = self.make_controller(spacemouse_probe=lambda: False, bridge_runner=runner)
        controller.tick()
        self.assertEqual(controller.snapshot().state, STATE_ERROR)
        runner.assert_not_called()

    def test_active_bridge_stops_after_codex_debounce(self):
        codex = MutableProbe(True)
        started = threading.Event()

        def runner(_config, *, stop_event, on_status, **_kwargs):
            on_status("running")
            started.set()
            stop_event.wait(2.0)

        controller = self.make_controller(codex_probe=codex, bridge_runner=runner)
        controller.tick()
        self.assertTrue(started.wait(1.0))
        self.assertEqual(controller.snapshot().state, STATE_ACTIVE)

        codex.value = False
        for _ in range(5):
            controller.tick()
        self.assertTrue(controller.wait_for_bridge_stop(1.0))
        controller.shutdown()

    def test_multiple_positive_samples_do_not_start_duplicate_bridge(self):
        started = threading.Event()
        release = threading.Event()
        call_count = 0

        def runner(_config, *, stop_event, on_status, **_kwargs):
            nonlocal call_count
            call_count += 1
            on_status("running")
            started.set()
            while not stop_event.is_set() and not release.is_set():
                time.sleep(0.005)

        controller = self.make_controller(bridge_runner=runner)
        controller.tick()
        self.assertTrue(started.wait(1.0))
        controller.tick()
        controller.tick()
        self.assertEqual(call_count, 1)
        release.set()
        controller.set_enabled(False)
        controller.tick()
        controller.wait_for_bridge_stop(1.0)
        controller.shutdown()


if __name__ == "__main__":
    unittest.main()

