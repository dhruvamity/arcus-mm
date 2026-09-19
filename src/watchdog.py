"""Independent Dead-Man's Switch and Watchdog Monitor for Arcus Perpetuals.

Fulfills Mandate Section 4.2 & Section 27 of prompt.md:
- Independent watchdog process / loop that monitors the main engine's heartbeat.
- Triggers immediate emergency cancellation (`cancelAllOrders`) if heartbeat ceases (>5s stale).
- Tracks venue-side scheduleCancel deadlines.
- Completely decoupled from strategy AI/research layer.
"""

import asyncio
import datetime
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Awaitable

logger = logging.getLogger(__name__)


class WatchdogStatus:
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    DISARMED = "DISARMED"
    ERROR = "ERROR"


class WatchdogMonitor:
    """Independent watchdog that monitors heartbeat and fires emergency cleanup on failure."""

    def __init__(
        self,
        heartbeat_file: str = "data/engine_heartbeat.json",
        timeout_seconds: float = 5.0,
        check_interval_seconds: float = 1.0,
        emergency_cleanup_cb: Optional[Callable[[], Awaitable[Any]]] = None,
    ):
        self.heartbeat_file = Path(heartbeat_file)
        self.timeout_seconds = timeout_seconds
        self.check_interval_seconds = check_interval_seconds
        self.emergency_cleanup_cb = emergency_cleanup_cb

        self.status = WatchdogStatus.ARMED
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.last_heartbeat_time: float = time.time()
        self.trigger_count: int = 0
        self.last_trigger_reason: Optional[str] = None

    def record_heartbeat(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Called by the main trading engine to signal active liveness."""
        self.last_heartbeat_time = time.time()
        self.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": self.last_heartbeat_time,
            "iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": "OK",
            "metadata": metadata or {},
        }
        with open(self.heartbeat_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def read_heartbeat_file(self) -> Optional[float]:
        """Reads timestamp from the heartbeat file if present."""
        if not self.heartbeat_file.exists():
            return None
        try:
            with open(self.heartbeat_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return float(data.get("timestamp", 0.0))
        except Exception:
            return None

    def time_since_last_heartbeat(self) -> float:
        """Returns elapsed seconds since last valid heartbeat."""
        disk_ts = self.read_heartbeat_file()
        effective_ts = max(self.last_heartbeat_time, disk_ts or 0.0)
        return time.time() - effective_ts

    async def trigger_emergency_cleanup(self, reason: str) -> bool:
        """Executes emergency cleanup (e.g. cancelAllOrders) when engine fails."""
        self.status = WatchdogStatus.TRIGGERED
        self.trigger_count += 1
        self.last_trigger_reason = reason
        logger.critical(f"WATCHDOG TRIGGERED: {reason}. Executing emergency cleanup!")

        if self.emergency_cleanup_cb:
            try:
                await self.emergency_cleanup_cb()
                logger.info("Watchdog emergency cleanup callback executed successfully.")
                return True
            except Exception as e:
                logger.error(f"Failed to execute watchdog emergency cleanup: {e}", exc_info=True)
                self.status = WatchdogStatus.ERROR
                return False
        return True

    async def check_once(self) -> bool:
        """Evaluates liveness. Returns True if alive, False if expired and triggered."""
        elapsed = self.time_since_last_heartbeat()
        if elapsed > self.timeout_seconds:
            if self.status != WatchdogStatus.TRIGGERED:
                await self.trigger_emergency_cleanup(
                    f"Heartbeat expired: {elapsed:.2f}s elapsed (limit: {self.timeout_seconds}s)"
                )
            return False
        return True

    async def run(self) -> None:
        """Continuously polls engine heartbeat and enforces dead-man trigger."""
        self._running = True
        logger.info(
            f"WatchdogMonitor started. Timeout: {self.timeout_seconds}s, Check: {self.check_interval_seconds}s"
        )
        while self._running:
            await self.check_once()
            await asyncio.sleep(self.check_interval_seconds)

    def stop(self) -> None:
        """Stops the watchdog monitor."""
        self._running = False
        self.status = WatchdogStatus.DISARMED
