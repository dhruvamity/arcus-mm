"""Rate-Limit-Aware Execution Simulator for Arcus Perpetuals.

Fulfills Section 5 of prompt.md:
- Models separate subaccount pools:
  - Order pool: 20,000 initial capacity
  - Cancel pool: 40,000 initial capacity
- Distinct action costs:
  - PLACE: 1 order unit
  - MODIFY: 1 order unit (does not consume cancel pool)
  - CANCEL: 1 cancel unit
  - CANCEL_ALL: 1,000 cancel units
- Fill replenishment: +1 unit per $0.10 traded notional (+10 units per $1.00).
  Headroom cannot exceed initial pool capacity.
- Exhausted-pool drip: When a pool reaches 0, at most 1 action per 10 seconds.
- Exposes `get_pool_status()` for real-time telemetry and paper trader logging.
"""

import time
from typing import Dict, Any, Optional


class ArcusRateLimitSimulator:
    """Simulates Arcus venue rate limit accounting with strict pool separation and drip."""

    def __init__(
        self,
        order_pool_cap: int = 20_000,
        cancel_pool_cap: int = 40_000,
        requote_threshold_ticks: int = 2,
        drip_interval_seconds: float = 10.0,
    ):
        self.order_pool_cap = order_pool_cap
        self.cancel_pool_cap = cancel_pool_cap
        self.requote_threshold_ticks = requote_threshold_ticks
        self.drip_interval_seconds = drip_interval_seconds

        self.order_units_available = float(order_pool_cap)
        self.cancel_units_available = float(cancel_pool_cap)

        self.orders_placed = 0
        self.orders_modified = 0
        self.orders_cancelled = 0
        self.cancel_all_count = 0

        self.fills_generated = 0
        self.total_fill_notional = 0.0

        self.order_replenishment_earned = 0.0
        self.cancel_replenishment_earned = 0.0
        self.pool_exhaustion_count = 0

        # Drip tracking timestamps
        self.last_order_drip_ts: float = 0.0
        self.last_cancel_drip_ts: float = 0.0

    def _current_time(self, now_ts: Optional[float] = None) -> float:
        return now_ts if now_ts is not None else time.time()

    # --------------------------------------------------------------------------
    # Capacity & Headroom Queries
    # --------------------------------------------------------------------------

    def can_place_order(self, now_ts: Optional[float] = None) -> bool:
        """Evaluates whether an order placement can proceed (units >= 1 or drip eligible)."""
        if self.order_units_available >= 1.0:
            return True
        # Check exhausted drip eligibility
        t = self._current_time(now_ts)
        return (t - self.last_order_drip_ts) >= self.drip_interval_seconds

    def can_modify_order(self, now_ts: Optional[float] = None) -> bool:
        """Evaluates whether a quote modification can proceed (consumes 1 order unit)."""
        return self.can_place_order(now_ts)

    def can_cancel_order(self, now_ts: Optional[float] = None) -> bool:
        """Evaluates whether a cancellation can proceed (cancel units >= 1 or drip eligible)."""
        if self.cancel_units_available >= 1.0:
            return True
        t = self._current_time(now_ts)
        return (t - self.last_cancel_drip_ts) >= self.drip_interval_seconds

    def can_cancel_all(self, now_ts: Optional[float] = None) -> bool:
        """Evaluates whether a cancelAll can proceed (1,000 cancel units or drip eligible)."""
        if self.cancel_units_available >= 1000.0:
            return True
        t = self._current_time(now_ts)
        return (t - self.last_cancel_drip_ts) >= self.drip_interval_seconds

    # --------------------------------------------------------------------------
    # Action Consumption
    # --------------------------------------------------------------------------

    def record_order_placement(self, now_ts: Optional[float] = None) -> bool:
        """Consumes 1 order unit for initial quote placement."""
        t = self._current_time(now_ts)
        if self.order_units_available >= 1.0:
            self.order_units_available -= 1.0
            self.orders_placed += 1
            return True
        elif (t - self.last_order_drip_ts) >= self.drip_interval_seconds:
            # Drip headroom action allowed
            self.last_order_drip_ts = t
            self.orders_placed += 1
            return True
        self.pool_exhaustion_count += 1
        return False

    def record_order_modification(self, now_ts: Optional[float] = None) -> bool:
        """Consumes 1 order unit for in-place or replacement modification."""
        t = self._current_time(now_ts)
        if self.order_units_available >= 1.0:
            self.order_units_available -= 1.0
            self.orders_modified += 1
            return True
        elif (t - self.last_order_drip_ts) >= self.drip_interval_seconds:
            self.last_order_drip_ts = t
            self.orders_modified += 1
            return True
        self.pool_exhaustion_count += 1
        return False

    def record_order_cancellation(self, now_ts: Optional[float] = None) -> bool:
        """Consumes 1 cancel unit for single order cancellation."""
        t = self._current_time(now_ts)
        if self.cancel_units_available >= 1.0:
            self.cancel_units_available -= 1.0
            self.orders_cancelled += 1
            return True
        elif (t - self.last_cancel_drip_ts) >= self.drip_interval_seconds:
            self.last_cancel_drip_ts = t
            self.orders_cancelled += 1
            return True
        self.pool_exhaustion_count += 1
        return False

    def record_cancel_all(self, now_ts: Optional[float] = None) -> bool:
        """Consumes 1,000 cancel units for cancelAll operation."""
        t = self._current_time(now_ts)
        if self.cancel_units_available >= 1000.0:
            self.cancel_units_available -= 1000.0
            self.cancel_all_count += 1
            return True
        elif (t - self.last_cancel_drip_ts) >= self.drip_interval_seconds:
            self.last_cancel_drip_ts = t
            self.cancel_all_count += 1
            return True
        self.pool_exhaustion_count += 1
        return False

    def record_cancellation(self, now_ts: Optional[float] = None) -> bool:
        return self.record_order_cancellation(now_ts)

    def record_placement(self, now_ts: Optional[float] = None) -> bool:
        return self.record_order_placement(now_ts)

    def record_modify(self, now_ts: Optional[float] = None) -> bool:
        return self.record_order_modification(now_ts)

    def record_cancel(self, now_ts: Optional[float] = None) -> bool:
        return self.record_order_cancellation(now_ts)

    # --------------------------------------------------------------------------
    # Replenishment
    # --------------------------------------------------------------------------

    def record_fill(self, fill_notional: float) -> None:
        """Replenishes pools: +1 unit per $0.10 traded notional (+10 units per $1.00).

        Cannot exceed maximum initial capacity.
        """
        self.fills_generated += 1
        self.total_fill_notional += fill_notional

        units = fill_notional / 0.10
        self.order_replenishment_earned += units
        self.cancel_replenishment_earned += units

        self.order_units_available = min(float(self.order_pool_cap), self.order_units_available + units)
        self.cancel_units_available = min(float(self.cancel_pool_cap), self.cancel_units_available + units)

    # --------------------------------------------------------------------------
    # Telemetry and Reporting
    # --------------------------------------------------------------------------

    def get_pool_status(self) -> Dict[str, Any]:
        """Provides real-time pool status and action counts for telemetry reporting."""
        total_actions = (
            self.orders_placed
            + self.orders_modified
            + self.orders_cancelled
            + (self.cancel_all_count * 1000)
        )
        return {
            "order_units_available": self.order_units_available,
            "cancel_units_available": self.cancel_units_available,
            "order_pool_cap": self.order_pool_cap,
            "cancel_pool_cap": self.cancel_pool_cap,
            "orders_placed": self.orders_placed,
            "orders_modified": self.orders_modified,
            "orders_cancelled": self.orders_cancelled,
            "cancel_all_count": self.cancel_all_count,
            "total_actions_used": total_actions,
            "fills_generated": self.fills_generated,
            "total_fill_notional": self.total_fill_notional,
            "pool_exhaustion_count": self.pool_exhaustion_count,
        }

    def to_metrics(self) -> Dict[str, Any]:
        """Returns consolidated rate-limit performance metrics."""
        status = self.get_pool_status()
        fills = max(1, self.fills_generated)
        status.update({
            "orders_per_fill": round((self.orders_placed + self.orders_modified) / fills, 2),
            "cancels_per_fill": round(self.orders_cancelled / fills, 2),
            "actions_per_fill": round(status["total_actions_used"] / fills, 2),
            "is_sustainable": status["pool_exhaustion_count"] == 0 and status["order_units_available"] > 0,
        })
        return status
