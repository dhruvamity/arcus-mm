from __future__ import annotations

"""Deterministic Unit Test Suite for Arcus Rate-Limit Economics.

- Independent Order and Cancel pool separation (20,000 order / 40,000 cancel).
- Unit costs: PLACE (1 order), MODIFY (1 order), CANCEL (1 cancel), CANCEL_ALL (1,000 cancel).
- Fill replenishment: +1 unit per $0.10 traded notional, bounded by pool capacity.
- Exhausted-pool drip: at most 1 action per 10.0 seconds when pool is depleted.
- Queue priority: modify preserves priority without cancel pool penalty.
"""

import unittest
from src.models.rate_limit import ArcusRateLimitSimulator
from src.models.fill import SimulatedQueueOrder


class TestRateLimitSemantics(unittest.TestCase):
    """Verifies exact venue-aligned rate limit accounting."""

    def setUp(self):
        self.simulator = ArcusRateLimitSimulator(
            order_pool_cap=20_000,
            cancel_pool_cap=40_000,
            requote_threshold_ticks=2,
            drip_interval_seconds=10.0,
        )

    def test_order_and_cancel_pool_separation(self):
        """Verify that placement/modification consume order units only, while cancel consumes cancel units."""
        # Initial capacity
        self.assertEqual(self.simulator.order_units_available, 20_000.0)
        self.assertEqual(self.simulator.cancel_units_available, 40_000.0)

        # 1. Order Placement consumes 1 order unit, 0 cancel units
        ok_place = self.simulator.record_order_placement()
        self.assertTrue(ok_place)
        self.assertEqual(self.simulator.order_units_available, 19_999.0)
        self.assertEqual(self.simulator.cancel_units_available, 40_000.0)

        # 2. Order Modification consumes 1 order unit, 0 cancel units
        ok_mod = self.simulator.record_order_modification()
        self.assertTrue(ok_mod)
        self.assertEqual(self.simulator.order_units_available, 19_998.0)
        self.assertEqual(self.simulator.cancel_units_available, 40_000.0)

        # 3. Order Cancellation consumes 1 cancel unit, 0 order units
        ok_cancel = self.simulator.record_order_cancellation()
        self.assertTrue(ok_cancel)
        self.assertEqual(self.simulator.order_units_available, 19_998.0)
        self.assertEqual(self.simulator.cancel_units_available, 39_999.0)

        self.assertEqual(self.simulator.orders_placed, 1)
        self.assertEqual(self.simulator.orders_modified, 1)
        self.assertEqual(self.simulator.orders_cancelled, 1)

    def test_cancel_all_cost_units(self):
        """Verify that cancelAll consumes flat 1,000 cancel units."""
        ok = self.simulator.record_cancel_all()
        self.assertTrue(ok)
        self.assertEqual(self.simulator.cancel_units_available, 39_000.0)
        self.assertEqual(self.simulator.order_units_available, 20_000.0)
        self.assertEqual(self.simulator.cancel_all_count, 1)

    def test_fill_replenishment_cap(self):
        """Verify +1 unit per $0.10 traded, capped strictly at initial capacity."""
        # Burn 100 order units and 500 cancel units
        for _ in range(100):
            self.simulator.record_order_placement()
        for _ in range(500):
            self.simulator.record_order_cancellation()

        self.assertEqual(self.simulator.order_units_available, 19_900.0)
        self.assertEqual(self.simulator.cancel_units_available, 39_500.0)

        # Fill of $5.00 notional generates 50 units
        self.simulator.record_fill(fill_notional=5.0)
        self.assertEqual(self.simulator.order_units_available, 19_950.0)
        self.assertEqual(self.simulator.cancel_units_available, 39_550.0)

        # Large fill of $1000 notional generates 10,000 units, but capped at 20,000 / 40,000
        self.simulator.record_fill(fill_notional=1000.0)
        self.assertEqual(self.simulator.order_units_available, 20_000.0)
        self.assertEqual(self.simulator.cancel_units_available, 40_000.0)

    def test_exhausted_pool_drip_rate(self):
        """Verify that when a pool is exhausted, actions drip at 1 per 10s."""
        # Manually exhaust order pool
        self.simulator.order_units_available = 0.0

        t0 = 1000.0
        # First attempt: drip eligible
        can_act = self.simulator.can_place_order(now_ts=t0)
        self.assertTrue(can_act)
        ok = self.simulator.record_order_placement(now_ts=t0)
        self.assertTrue(ok)

        # Immediate next attempt at t0 + 2s: BLOCKED (needs 10s interval)
        can_act_fast = self.simulator.can_place_order(now_ts=t0 + 2.0)
        self.assertFalse(can_act_fast)
        ok_fast = self.simulator.record_order_placement(now_ts=t0 + 2.0)
        self.assertFalse(ok_fast)
        self.assertEqual(self.simulator.pool_exhaustion_count, 1)

        # Attempt after 10s (t0 + 10.1s): ALLOWED by drip
        can_act_drip = self.simulator.can_place_order(now_ts=t0 + 10.1)
        self.assertTrue(can_act_drip)
        ok_drip = self.simulator.record_order_placement(now_ts=t0 + 10.1)
        self.assertTrue(ok_drip)

    def test_queue_priority_in_place_modify_semantics(self):
        """Verify that size reduction modifies in place without losing queue priority."""
        order = SimulatedQueueOrder("ord_1", "BUY", price=100.0, size=10.0, created_ts_ns=1000, queue_ahead_volume=15.0)

        # Size decrease at same price preserves priority
        preserved = order.modify(new_price=100.0, new_size=5.0, current_queue_at_price=50.0)
        self.assertTrue(preserved)
        self.assertEqual(order.size, 5.0)
        self.assertEqual(order.queue_ahead_volume, 15.0)  # Unchanged!

        # Price change loses priority
        preserved_price = order.modify(new_price=99.9, new_size=5.0, current_queue_at_price=25.0)
        self.assertFalse(preserved_price)
        self.assertEqual(order.queue_ahead_volume, 25.0)  # Joins back of depth at 99.9!


if __name__ == "__main__":
    unittest.main()
