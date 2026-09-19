"""Execution Watchdog and Dead-Man's Switch for Arcus MM.

Fulfills Mandate Section 10:
- Implements scheduleCancel dead-man's switch logic
- Monitors heartbeat and executes emergency cancelAll on heartbeat loss
- Provides fail-safe mechanisms for automated quoting safety
"""

import time
from typing import Callable, Optional, Dict, Any


class ExecutionWatchdog:
    """Monitors connectivity heartbeats and triggers emergency cancel-all if dead-man timer expires."""

    def __init__(
        self,
        dead_man_timeout_sec: float = 10.0,
        emergency_cancel_callback: Optional[Callable[[], int]] = None,
    ):
        self.dead_man_timeout_sec = dead_man_timeout_sec
        self.emergency_cancel_callback = emergency_cancel_callback
        self.last_heartbeat_ts = time.time()
        self.is_tripped = False
        self.emergency_cancels_fired = 0
        self.scheduled_cancel_window_sec = dead_man_timeout_sec

    def heartbeat(self, now: Optional[float] = None):
        """Refreshes the heartbeat and resets the dead-man timer."""
        if now is None:
            now = time.time()
        self.last_heartbeat_ts = now
        self.is_tripped = False

    def schedule_cancel(self, delay_sec: float) -> Dict[str, Any]:
        """Simulates or issues venue scheduleCancel payload to reset the exchange-side dead-man switch."""
        self.scheduled_cancel_window_sec = delay_sec
        self.heartbeat()
        return {
            "status": "SCHEDULED",
            "cancel_in_sec": delay_sec,
            "scheduled_ts": self.last_heartbeat_ts,
        }

    def check_liveness(self, now: Optional[float] = None) -> bool:
        """Evaluates elapsed time against timeout.
        
        Returns True if alive, False if expired and emergency action triggered.
        """
        if now is None:
            now = time.time()

        elapsed = now - self.last_heartbeat_ts
        if elapsed > self.dead_man_timeout_sec:
            if not self.is_tripped:
                self.is_tripped = True
                self.emergency_cancels_fired += 1
                if self.emergency_cancel_callback is not None:
                    try:
                        self.emergency_cancel_callback()
                    except Exception as e:
                        print(f"Error during emergency cancel callback: {e}")
            return False

        return True
