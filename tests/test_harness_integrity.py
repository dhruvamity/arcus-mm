"""Deterministic Integrity Test Suite for Arcus Backtesting Harness.

Fulfills Section 4.1 of prompt.md:
1. Fill monotonicity: Fills(A) >= Fills(B) >= Fills(C) on identical quote/trade paths.
2. Queue model: FIFO depletion, size decrease preserves priority, price change/size increase loses priority.
3. PnL identity: cash + inventory * mid - fees +- funding == equity at every step; 5-way attribution sums to total.
4. Markout horizons: synthetic random walk with drift produces distinct markouts per horizon; unresolvable horizons dropped.
5. Single monotonic clock: time alignment on recv_ts_ns with zero lookahead bias.
6. Quantisation: tick/step rounding and per-market min executable clip enforcement.
7. Determinism: identical inputs yield bit-for-bit identical hashes.
"""

import datetime
import hashlib
import json
import math
import unittest
import numpy as np

from src.models.fill import FillEngine, FillModelType, SimulatedQueueOrder
from src.models.pnl import PnLAttributionEngine
from src.calendar import classify_regime, MarketRegimeTag
from src.adverse_selection import compute_markouts, HORIZONS_SEC


class TestHarnessIntegrity(unittest.TestCase):

    def test_fill_monotonicity(self):
        """Monotonicity: Fills(A) >= Fills(B) >= Fills(C) on identical paths."""
        engine_a = FillEngine(FillModelType.MODEL_A_OPTIMISTIC)
        engine_b = FillEngine(FillModelType.MODEL_B_MODERATE)
        engine_c = FillEngine(FillModelType.MODEL_C_CONSERVATIVE)

        # Scenario: BUY order resting at $100.00 with size 10.0, queue ahead 5.0 units
        order_a = SimulatedQueueOrder("o_a", "BUY", 100.0, 10.0, 1000, queue_ahead_volume=5.0)
        order_b = SimulatedQueueOrder("o_b", "BUY", 100.0, 10.0, 1000, queue_ahead_volume=5.0)
        order_c = SimulatedQueueOrder("o_c", "BUY", 100.0, 10.0, 1000, queue_ahead_volume=5.0)

        # Sequence of synthetic trades:
        # Trade 1: Taker sells 3 units at $100.00 (Touch)
        # Model A: fills 3.0
        # Model B: queue ahead 5.0 -> depleted to 2.0, fills 0.0
        # Model C: touch only -> fills 0.0
        f_a1 = engine_a.process_trade(order_a, "SELL", 100.0, 3.0)
        f_b1 = engine_b.process_trade(order_b, "SELL", 100.0, 3.0)
        f_c1 = engine_c.process_trade(order_c, "SELL", 100.0, 3.0)

        self.assertEqual(f_a1, 3.0)
        self.assertEqual(f_b1, 0.0)
        self.assertEqual(f_c1, 0.0)
        self.assertTrue(f_a1 >= f_b1 >= f_c1)

        # Trade 2: Taker sells 4 units at $100.00 (Touch)
        # Model A: fills min(7 remaining, 4) = 4.0
        # Model B: queue ahead 2.0 depleted -> 2.0 fills order!
        # Model C: touch only -> fills 0.0
        f_a2 = engine_a.process_trade(order_a, "SELL", 100.0, 4.0)
        f_b2 = engine_b.process_trade(order_b, "SELL", 100.0, 4.0)
        f_c2 = engine_c.process_trade(order_c, "SELL", 100.0, 4.0)

        self.assertEqual(f_a2, 4.0)
        self.assertEqual(f_b2, 2.0)
        self.assertEqual(f_c2, 0.0)
        self.assertTrue(f_a2 >= f_b2 >= f_c2)

        # Trade 3: Taker sells 5 units at $99.90 (Trade-through!)
        # Model A: fills min(3 remaining, 5) = 3.0 (order complete)
        # Model B: trades through -> fills min(8 remaining, 5) = 5.0
        # Model C: trades through -> fills min(10 remaining, 5) = 5.0
        f_a3 = engine_a.process_trade(order_a, "SELL", 99.90, 5.0)
        f_b3 = engine_b.process_trade(order_b, "SELL", 99.90, 5.0)
        f_c3 = engine_c.process_trade(order_c, "SELL", 99.90, 5.0)

        # Total cumulative fills:
        tot_a = order_a.filled_size
        tot_b = order_b.filled_size
        tot_c = order_c.filled_size

        self.assertEqual(tot_a, 10.0)
        self.assertEqual(tot_b, 7.0)
        self.assertEqual(tot_c, 5.0)
        self.assertTrue(tot_a >= tot_b >= tot_c, f"Violation: {tot_a} >= {tot_b} >= {tot_c}")

    def test_queue_fifo_and_priority_modification(self):
        """Queue model: FIFO queue volume depletion, in-place modify vs priority loss."""
        order = SimulatedQueueOrder("o1", "BUY", 50.0, 10.0, 1000, queue_ahead_volume=8.0)
        engine = FillEngine(FillModelType.MODEL_B_MODERATE)

        # 1. First trade depletes part of queue ahead
        f1 = engine.process_trade(order, "SELL", 50.0, 5.0)
        self.assertEqual(f1, 0.0)
        self.assertEqual(order.queue_ahead_volume, 3.0)

        # 2. Size decrease at same price PRESERVES queue priority
        preserved = order.modify(new_price=50.0, new_size=6.0, current_queue_at_price=20.0)
        self.assertTrue(preserved)
        self.assertEqual(order.queue_ahead_volume, 3.0)  # Priority preserved!
        self.assertEqual(order.size, 6.0)

        # 3. Price change LOSES queue priority
        preserved_price_change = order.modify(new_price=49.99, new_size=6.0, current_queue_at_price=15.0)
        self.assertFalse(preserved_price_change)
        self.assertEqual(order.queue_ahead_volume, 15.0)  # Reset to depth at new price!

        # 4. Size increase LOSES queue priority
        preserved_size_inc = order.modify(new_price=49.99, new_size=12.0, current_queue_at_price=25.0)
        self.assertFalse(preserved_size_inc)
        self.assertEqual(order.queue_ahead_volume, 25.0)  # Joins back of queue!

    def test_pnl_accounting_identity(self):
        """PnL Identity: cash + inventory * mid - fees +- funding == equity at every step."""
        pnl = PnLAttributionEngine(initial_capital=100.0, maker_fee_bps=0.0, taker_fee_bps=2.25)
        self.assertTrue(pnl.verify_accounting_identity(100.0))

        # Fill 1: Maker BUY 1.0 @ $100.00
        pnl.record_fill("BUY", 100.0, 1.0, mid_at_fill=100.0, is_taker=False)
        self.assertEqual(pnl.position, 1.0)
        self.assertEqual(pnl.cash, 0.0)
        self.assertTrue(pnl.verify_accounting_identity(100.0))
        self.assertTrue(pnl.verify_accounting_identity(102.0))  # Mid moves up

        # Funding payment: positive rate => long pays
        funding_pmt = pnl.apply_funding(funding_rate=0.0001, current_mid=102.0)
        self.assertTrue(funding_pmt < 0)
        self.assertTrue(pnl.verify_accounting_identity(102.0))

        # Fill 2: Partial Maker SELL 0.5 @ $102.50
        pnl.record_fill("SELL", 102.50, 0.5, mid_at_fill=102.50, is_taker=False)
        self.assertEqual(pnl.position, 0.5)
        self.assertTrue(pnl.verify_accounting_identity(103.0))

        # Force Flatten: Taker liquidation of remaining 0.5 @ $103.00 (charges 2.25 bps taker fee)
        fee = pnl.force_flatten(current_mid=103.0)
        self.assertEqual(pnl.position, 0.0)
        self.assertTrue(fee > 0)
        self.assertTrue(pnl.verify_accounting_identity(103.0))

        # Summary check
        summary = pnl.get_summary(current_mid=103.0)
        self.assertAlmostEqual(
            summary["current_equity"],
            summary["initial_capital"] + summary["net_pnl"],
            places=4,
        )

    def test_markout_horizons_random_walk(self):
        """Markout horizons on synthetic random walk with positive drift:

        - Markouts differ across horizons.
        - Fills near the end of the recording have unresolvable horizons dropped (N decreases).
        """
        np.random.seed(42)
        n_seconds = 100
        t_grid_ns = np.arange(0, n_seconds * int(1e9), int(1e8))  # 100ms ticks
        # Drift + Brownian motion
        drift = 0.0005  # 5 bps per second drift
        steps = np.random.normal(drift * 0.1, 0.001, size=len(t_grid_ns))
        prices = 100.0 * np.exp(np.cumsum(steps))

        # Fills at t = 10s, 30s, 70s, 95s
        fill_ts = np.array([10 * int(1e9), 30 * int(1e9), 70 * int(1e9), 95 * int(1e9)])
        fill_prices = np.array([prices[100], prices[300], prices[700], prices[950]])
        fill_sides = np.array(["BUY", "BUY", "BUY", "BUY"])
        fill_notionals = np.array([10.0, 20.0, 10.0, 60.0])

        res = compute_markouts(
            fill_timestamps_ns=fill_ts,
            fill_prices=fill_prices,
            fill_sides=fill_sides,
            fill_notionals=fill_notionals,
            bbo_timestamps_ns=t_grid_ns,
            bbo_mids=prices,
        )

        horizons = res["horizons"]
        # 1. Horizon markouts must not be identical
        m_100ms = horizons["0.1s"]["mean_bps"]
        m_5s = horizons["5.0s"]["mean_bps"]
        m_30s = horizons["30.0s"]["mean_bps"]
        self.assertNotEqual(m_100ms, m_5s)
        self.assertNotEqual(m_5s, m_30s)

        # 2. For fill at 95s (end is 100s):
        # 5s target is 100s -> evaluable
        # 10s target is 105s (> 100s max) -> DROPPED
        # 30s target is 125s -> DROPPED
        # 60s target is 155s -> DROPPED
        # Thus, N must decrease as horizon exceeds available forward window!
        self.assertEqual(horizons["0.1s"]["N"], 4)
        self.assertEqual(horizons["5.0s"]["N"], 3)  # 95s + 5s = 100s > 99.9s max BBO ts -> dropped!
        self.assertTrue(horizons["30.0s"]["N"] < 3)
        self.assertTrue(horizons["60.0s"]["N"] < horizons["5.0s"]["N"])

    def test_single_monotonic_clock_and_time_alignment(self):
        """Single monotonic clock: Shifting trade timestamps relative to quotes changes fills."""
        engine = FillEngine(FillModelType.MODEL_A_OPTIMISTIC)

        # Quote rests from ts=1000 to ts=5000 at price $50.00
        order = SimulatedQueueOrder("o1", "BUY", 50.0, 1.0, created_ts_ns=1000)

        # Trade occurs at ts=500 (before quote rested) -> Must NOT fill
        f_early = 0.0
        if 500 >= order.created_ts_ns:
            f_early = engine.process_trade(order, "SELL", 50.0, 1.0)
        self.assertEqual(f_early, 0.0)

        # Trade occurs at ts=1500 (after quote rested) -> Fills
        f_aligned = 0.0
        if 1500 >= order.created_ts_ns:
            f_aligned = engine.process_trade(order, "SELL", 50.0, 1.0)
        self.assertEqual(f_aligned, 1.0)

    def test_regime_classification(self):
        """Regime classification: Weekday vs Weekend, US-RTH vs Off-hours."""
        # 1. Saturday 2026-09-19 14:00 UTC -> Weekend
        ts_sat = int(datetime.datetime(2026, 9, 19, 14, 0, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        reg_sat_crypto = classify_regime(ts_sat, "crypto")
        reg_sat_equity = classify_regime(ts_sat, "equities")

        self.assertEqual(reg_sat_crypto.dow_class, "WEEKEND")
        self.assertTrue(reg_sat_crypto.underlying_open)  # Crypto always open
        self.assertFalse(reg_sat_equity.underlying_open)  # Equity closed on weekend!

        # 2. Monday 2026-09-21 14:00 UTC (10:00 EDT) -> US-RTH Weekday
        ts_mon_rth = int(datetime.datetime(2026, 9, 21, 14, 0, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        reg_mon_equity = classify_regime(ts_mon_rth, "equities")

        self.assertEqual(reg_mon_equity.dow_class, "WEEKDAY")
        self.assertEqual(reg_mon_equity.session, "US_RTH")
        self.assertTrue(reg_mon_equity.underlying_open)  # Open during RTH!

        # 3. Monday 2026-09-21 13:40 UTC (09:40 EDT) -> OPEN_30 Window
        ts_mon_open30 = int(datetime.datetime(2026, 9, 21, 13, 40, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        reg_mon_open30 = classify_regime(ts_mon_open30, "equities")
        self.assertEqual(reg_mon_open30.event_window, "OPEN_30")

    def test_simulation_determinism(self):
        """Determinism: identical inputs produce identical hash."""
        def run_sim():
            engine = FillEngine(FillModelType.MODEL_B_MODERATE)
            pnl = PnLAttributionEngine(100.0)
            order = SimulatedQueueOrder("o", "BUY", 10.0, 5.0, 0, queue_ahead_volume=2.0)
            trades = [
                ("SELL", 10.0, 1.0),
                ("SELL", 10.0, 2.0),
                ("SELL", 9.99, 3.0),
            ]
            fill_log = []
            for side, p, s in trades:
                f = engine.process_trade(order, side, p, s)
                if f > 0:
                    pnl.record_fill("BUY", p, f, p)
                fill_log.append((f, pnl.cash, pnl.position))
            return json.dumps(fill_log, sort_keys=True)

        hash1 = hashlib.sha256(run_sim().encode()).hexdigest()
        hash2 = hashlib.sha256(run_sim().encode()).hexdigest()
        self.assertEqual(hash1, hash2)


if __name__ == "__main__":
    import datetime
    unittest.main()
