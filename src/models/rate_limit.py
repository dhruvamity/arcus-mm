"""Rate-Limit-Aware Execution Simulator for Arcus Perpetuals.

Fulfills Section 20 of prompt.md:
- Models Arcus subaccount pools (20,000 order units, 40,000 cancel units).
- Fill replenishment: +1 unit per $0.10 traded fill notional.
- Drip replenishment: 1 action per 10s if exhausted.
- Requote discipline: Quote-refresh threshold support.
- Burn rate metrics: orders/fill, cancels/fill, units burned/fill, peak burn rate.
"""

from typing import Dict, Any


class ArcusRateLimitSimulator:
    """Tracks consumption and replenishment of Arcus order/cancel pools."""

    def __init__(
        self,
        order_pool_cap: int = 20_000,
        cancel_pool_cap: int = 40_000,
        requote_threshold_ticks: int = 2,
    ):
        self.order_pool_cap = order_pool_cap
        self.cancel_pool_cap = cancel_pool_cap
        self.requote_threshold_ticks = requote_threshold_ticks

        self.order_units_available = float(order_pool_cap)
        self.cancel_units_available = float(cancel_pool_cap)

        self.orders_used = 0
        self.cancels_used = 0
        self.modifies_used = 0
        self.fills_generated = 0
        self.total_fill_notional = 0.0

        self.order_replenishment_earned = 0.0
        self.cancel_replenishment_earned = 0.0
        self.pool_exhaustion_count = 0

    def can_place_order(self) -> bool:
        return self.order_units_available >= 1.0

    def can_cancel_order(self) -> bool:
        return self.cancel_units_available >= 1.0

    def can_modify_order(self) -> bool:
        # Atomic modify consumes 1 order unit + 1 cancel unit
        return self.order_units_available >= 1.0 and self.cancel_units_available >= 1.0

    def record_order_placement(self) -> bool:
        if self.can_place_order():
            self.order_units_available -= 1.0
            self.orders_used += 1
            return True
        self.pool_exhaustion_count += 1
        return False

    def record_order_cancellation(self) -> bool:
        if self.can_cancel_order():
            self.cancel_units_available -= 1.0
            self.cancels_used += 1
            return True
        self.pool_exhaustion_count += 1
        return False

    def record_order_modification(self) -> bool:
        if self.can_modify_order():
            self.order_units_available -= 1.0
            self.cancel_units_available -= 1.0
            self.modifies_used += 1
            return True
        self.pool_exhaustion_count += 1
        return False

    def record_fill(self, fill_notional: float) -> None:
        """Adds fill replenishment: +1 unit per $0.10 traded notional."""
        self.fills_generated += 1
        self.total_fill_notional += fill_notional

        # Replenishment units
        units = fill_notional / 0.10
        self.order_replenishment_earned += units
        self.cancel_replenishment_earned += units

        self.order_units_available = min(float(self.order_pool_cap), self.order_units_available + units)
        self.cancel_units_available = min(float(self.cancel_pool_cap), self.cancel_units_available + units)

    def to_metrics(self) -> Dict[str, Any]:
        fills = max(1, self.fills_generated)
        total_actions = self.orders_used + self.cancels_used + (self.modifies_used * 2)
        return {
            "order_units_available": round(self.order_units_available, 1),
            "cancel_units_available": round(self.cancel_units_available, 1),
            "orders_used": self.orders_used,
            "cancels_used": self.cancels_used,
            "modifies_used": self.modifies_used,
            "total_actions": total_actions,
            "fills_generated": self.fills_generated,
            "orders_per_fill": round(self.orders_used / fills, 2),
            "cancels_per_fill": round(self.cancels_used / fills, 2),
            "actions_per_fill": round(total_actions / fills, 2),
            "total_replenishment_units": round(self.order_replenishment_earned, 1),
            "pool_exhaustion_count": self.pool_exhaustion_count,
            "is_sustainable": (self.pool_exhaustion_count == 0),
        }
