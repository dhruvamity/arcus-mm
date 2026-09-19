"""Unit tests for Independent Watchdog and Dead-Man's Switch.

Fulfills Mandate Section 27 of prompt.md:
- Tests heartbeat recording.
- Tests watchdog trigger on heartbeat stall.
- Tests emergency cleanup invocation.
"""

import asyncio
import os
import shutil
import tempfile
import time
import unittest

from src.watchdog import WatchdogMonitor, WatchdogStatus


class TestWatchdogMonitor(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.heartbeat_path = os.path.join(self.temp_dir, "engine_heartbeat.json")
        self.cleanup_invoked = False

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def _mock_emergency_cleanup(self):
        self.cleanup_invoked = True

    def test_watchdog_active_heartbeat_prevents_trigger(self):
        """Active engine heartbeat maintains ARMED status and does not trigger."""
        watchdog = WatchdogMonitor(
            heartbeat_file=self.heartbeat_path,
            timeout_seconds=1.0,
            check_interval_seconds=0.1,
            emergency_cleanup_cb=self._mock_emergency_cleanup,
        )
        watchdog.record_heartbeat({"market": "BTC-USD"})

        is_alive = asyncio.run(watchdog.check_once())
        self.assertTrue(is_alive)
        self.assertEqual(watchdog.status, WatchdogStatus.ARMED)
        self.assertFalse(self.cleanup_invoked)

    def test_watchdog_stalled_heartbeat_triggers_cleanup(self):
        """When heartbeat stops and timeout elapses, watchdog fires emergency cleanup."""
        watchdog = WatchdogMonitor(
            heartbeat_file=self.heartbeat_path,
            timeout_seconds=0.05,  # 50ms timeout for test
            check_interval_seconds=0.01,
            emergency_cleanup_cb=self._mock_emergency_cleanup,
        )
        watchdog.record_heartbeat({"state": "initial"})

        # Simulate stalled process by sleeping past timeout
        time.sleep(0.08)

        is_alive = asyncio.run(watchdog.check_once())
        self.assertFalse(is_alive, "Expired watchdog check must return False")
        self.assertEqual(watchdog.status, WatchdogStatus.TRIGGERED)
        self.assertTrue(self.cleanup_invoked, "Emergency cleanup callback must be called")
        self.assertEqual(watchdog.trigger_count, 1)


if __name__ == "__main__":
    unittest.main()
