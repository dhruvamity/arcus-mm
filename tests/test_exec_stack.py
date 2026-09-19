"""Unit Tests for Arcus MM Execution Stack (WS-7 / Section 10).

Fulfills Mandate Section 10:
- Verifies order manager order lifecycle (place, modify, cancel, cancelAll)
- Verifies rate-limit pool accounting (modify=1 order unit, cancelAll=1000 cancel units, +1 per $0.10 filled)
- Verifies isolated margin configuration
- Verifies all per-reason rejection handlers (POST_ONLY_WOULD_CROSS, UNDERCOLLATERALIZED, etc.)
- Verifies state reconciliation (positions, ghost orders, missing orders, Sev-1 trigger)
- Verifies scheduleCancel dead-man's switch and watchdog heartbeat expiry
"""

import unittest
from src.exec.order_manager import TestnetOrderManager, OrderStatus
from src.exec.rejection_handlers import RejectionHandler, RejectionReason
from src.exec.reconciler import ExecutionReconciler
from src.exec.watchdog import ExecutionWatchdog


class TestExecutionStack(unittest.TestCase):
    def setUp(self):
        self.om = TestnetOrderManager(initial_order_pool=10, initial_cancel_pool=1005)
        self.reconciler = ExecutionReconciler()

    def test_order_placement_and_pool_deduction(self):
        order = self.om.place_order(market="BTC-USD", side="buy", price=65000.0, size=0.001)
        self.assertIsNotNone(order)
        self.assertEqual(order.status, OrderStatus.RESTING)
        self.assertEqual(self.om.order_pool, 9)  # 1 unit deducted

    def test_order_modify_pool_deduction(self):
        order = self.om.place_order(market="BTC-USD", side="buy", price=65000.0, size=0.001)
        # Venue docs: modify charges 1 ORDER unit
        success = self.om.modify_order(order.order_id, new_price=65010.0, new_size=0.001)
        self.assertTrue(success)
        self.assertEqual(self.om.order_pool, 8)  # 10 - 1 (place) - 1 (modify) = 8
        self.assertEqual(order.price, 65010.0)

    def test_order_cancel_and_cancel_all_pools(self):
        order1 = self.om.place_order(market="BTC-USD", side="buy", price=65000.0, size=0.001)
        order2 = self.om.place_order(market="BTC-USD", side="sell", price=66000.0, size=0.001)

        # Cancel 1 order: charges 1 CANCEL unit
        self.om.cancel_order(order1.order_id)
        self.assertEqual(order1.status, OrderStatus.CANCELLED)
        self.assertEqual(self.om.cancel_pool, 1004)

        # CancelAll: charges 1000 CANCEL units
        cancelled_count = self.om.cancel_all_orders()
        self.assertEqual(cancelled_count, 1)  # order2 cancelled
        self.assertEqual(order2.status, OrderStatus.CANCELLED)
        self.assertEqual(self.om.cancel_pool, 4)  # 1004 - 1000 = 4

    def test_order_pool_exhaustion_blocks_orders(self):
        # Deplete order pool (started with 10)
        for _ in range(10):
            self.om.place_order(market="BTC-USD", side="buy", price=65000.0, size=0.001)
        self.assertEqual(self.om.order_pool, 0)

        # 11th order rejected due to pool exhaustion
        rejected_order = self.om.place_order(market="BTC-USD", side="buy", price=65000.0, size=0.001)
        self.assertIsNone(rejected_order)
        self.assertGreater(self.om.rejection_handler.rejection_counts[RejectionReason.RATE_LIMIT_EXCEEDED], 0)

    def test_fill_pool_replenishment(self):
        order = self.om.place_order(market="BTC-USD", side="buy", price=65000.0, size=0.001)
        # Initial: order_pool=9, cancel_pool=1005
        # Fill $65 notional (0.001 * 65,000 = $65.0) -> +650 units (capped at max 500)
        self.om.order_pool = 10
        self.om.cancel_pool = 10
        self.om.record_fill(order.order_id, fill_size=0.001, fill_price=65000.0)

        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(self.om.order_pool, 500)  # Capped at max_pool_capacity
        self.assertEqual(self.om.cancel_pool, 500)

    def test_isolated_margin_configuration(self):
        self.om.configure_isolated_margin(market="SOL-USD", leverage=5.0, collateral=100.0)
        self.assertIn("SOL-USD", self.om.isolated_margin)
        self.assertEqual(self.om.isolated_margin["SOL-USD"]["leverage"], 5.0)
        self.assertEqual(self.om.isolated_margin["SOL-USD"]["collateral"], 100.0)

    def test_rejection_handlers(self):
        rh = RejectionHandler()
        reasons = [
            (RejectionReason.POST_ONLY_WOULD_CROSS, "WIDEN_QUOTE_AND_RETRY"),
            (RejectionReason.UNDERCOLLATERALIZED, "HALT_QUOTING_AND_CHECK_BALANCE"),
            (RejectionReason.SELF_TRADE, "CANCEL_OPPOSITE_RESTING_ORDER"),
            (RejectionReason.REDUCE_ONLY_WOULD_INCREASE, "CLEAR_REDUCE_ONLY_FLAG"),
            (RejectionReason.POSITION_LIMIT_EXCEEDED, "REDUCE_ONLY_ACTIVE"),
            (RejectionReason.TRADING_BOUND_REJECTION, "ADJUST_PRICE_TO_VENUE_BOUNDS"),
        ]
        for reason, expected_action in reasons:
            record = rh.handle_rejection(reason.value, {"order_id": "test-1", "market": "BTC-USD"})
            self.assertEqual(record["reason"], reason)
            self.assertEqual(record["corrective_action"], expected_action)
            self.assertEqual(rh.rejection_counts[reason], 1)

    def test_reconciliation_engine(self):
        # Scenario 1: Clean
        rep_clean = self.reconciler.reconcile(
            local_positions={"BTC-USD": 0.05},
            venue_positions={"BTC-USD": 0.05},
            local_open_order_ids=["ord-1"],
            venue_open_order_ids=["ord-1"],
            local_cash=100.0,
            venue_cash=100.0,
        )
        self.assertTrue(rep_clean.is_clean)
        self.assertFalse(rep_clean.sev1_triggered)

        # Scenario 2: Ghost orders and position mismatch (triggers Sev-1)
        rep_mismatch = self.reconciler.reconcile(
            local_positions={"BTC-USD": 0.05},
            venue_positions={"BTC-USD": 0.10},  # Mismatch!
            local_open_order_ids=["ord-1"],
            venue_open_order_ids=["ord-1", "ghost-99"],  # Ghost order!
            local_cash=100.0,
            venue_cash=90.0,
        )
        self.assertFalse(rep_mismatch.is_clean)
        self.assertTrue(rep_mismatch.sev1_triggered)
        self.assertEqual(len(rep_mismatch.position_discrepancies), 1)
        self.assertEqual(len(rep_mismatch.order_discrepancies), 1)

    def test_watchdog_and_dead_mans_switch(self):
        fired = []
        wd = ExecutionWatchdog(dead_man_timeout_sec=0.1, emergency_cancel_callback=lambda: fired.append(True))

        # Heartbeat active
        wd.heartbeat()
        self.assertTrue(wd.check_liveness())
        self.assertEqual(len(fired), 0)

        # Timeout expired
        import time
        time.sleep(0.15)
        is_alive = wd.check_liveness()
        self.assertFalse(is_alive)
        self.assertEqual(len(fired), 1)
        self.assertEqual(wd.emergency_cancels_fired, 1)

        # scheduleCancel payload
        payload = wd.schedule_cancel(delay_sec=5.0)
        self.assertEqual(payload["status"], "SCHEDULED")
        self.assertEqual(payload["cancel_in_sec"], 5.0)


if __name__ == "__main__":
    unittest.main()
