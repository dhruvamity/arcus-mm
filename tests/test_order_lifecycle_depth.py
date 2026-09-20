from __future__ import annotations

"""Unit test suite for Phase 4 Order Lifecycle, L2 Depth Replay, and In-Flight Adverse Selection.

- Order status state machine transitions: SUBMITTING -> RESTING -> CANCEL_REQUESTED -> CANCELLED.
- In-place modification preserves queue priority.
- Price modification triggers cancel-replace with latency delay.
- In-flight cancellation window adverse selection: trade fills old quote before cancel ACK arrives.
- L2 depth replay queue volume calculation.
"""

import unittest
import pandas as pd
from decimal import Decimal

from src.models.fill import FillModelType, SimulatedQueueOrder, OrderStatus
from src.models.latency import LatencyConfig
from src.models.pnl import PnLAttributionEngine
from src.strategies.fixed_spread import FixedSpreadStrategy
from src.backtester import ArcusEventBacktester


class TestOrderLifecycleDepth(unittest.TestCase):

    def setUp(self):
        self.strategy = FixedSpreadStrategy(
            market="BTC-USD",
            tick_size=0.1,
            step_size=0.0001,
            spread_bps=4.0,
            clip_notional=10.0,
            min_notional=5.0,
        )
        self.latency = LatencyConfig(
            feed_latency_ms=10.0,
            decision_latency_ms=5.0,
            send_latency_ms=10.0,
            ack_latency_ms=5.0,
            cancel_latency_ms=10.0,
        )

    def test_inplace_size_reduction_preserves_priority(self):
        """Mandate §6: Same-price size decrease preserves queue priority and remains RESTING."""
        order = SimulatedQueueOrder(
            order_id="b1",
            side="BUY",
            price=80000.0,
            size=1.0,
            created_ts_ns=1_000_000_000,
            queue_ahead_volume=5.0,
            status=OrderStatus.RESTING,
        )
        # Modify to smaller size at same price
        preserved = order.modify(new_price=80000.0, new_size=0.5, current_queue_at_price=10.0)
        self.assertTrue(preserved, "Priority must be preserved on same-price size reduction")
        self.assertEqual(order.size, 0.5)
        self.assertEqual(order.queue_ahead_volume, 5.0, "Queue ahead must NOT be reset to new depth")

        # Modify price -> loses priority
        preserved_price_change = order.modify(new_price=80001.0, new_size=0.5, current_queue_at_price=10.0)
        self.assertFalse(preserved_price_change, "Priority must be lost on price change")
        self.assertEqual(order.queue_ahead_volume, 10.0, "Queue ahead must join back of queue")

    def test_in_flight_cancel_fill_race_condition(self):
        """Mandate §6: An order in CANCEL_REQUESTED can still be filled during transit latency."""
        backtester = ArcusEventBacktester(
            strategy=self.strategy,
            fill_model=FillModelType.MODEL_A_OPTIMISTIC,
            latency_config=self.latency,
        )

        t0 = 1_000_000_000
        # Place initial bid at $80,000.00
        df_bbo = pd.DataFrame([
            {
                "recv_ts_ns": t0,
                "bid_price": 80000.0,
                "ask_price": 80002.0,
                "mid_price": 80001.0,
                "spread_bps": 2.5,
                "bid_size": 2.0,
                "ask_size": 2.0,
            },
            # BBO shifts at t0 + 100ms (100ms later), strategy requotes to $79,990.00
            {
                "recv_ts_ns": t0 + 100_000_000,
                "bid_price": 79990.0,
                "ask_price": 79992.0,
                "mid_price": 79991.0,
                "spread_bps": 2.5,
                "bid_size": 2.0,
                "ask_size": 2.0,
            },
        ])

        # Trade hits old bid price ($80,000.00) at t0 + 110ms (during cancel transit latency!)
        # Total cancel latency is 30ms (feed 10 + decision 5 + cancel 10 + ack 5 = 30ms)
        # Cancel requested at t0 + 100ms, effective at t0 + 130ms.
        # Trade arrives at t0 + 110ms (< 130ms) -> Must FILL the in-flight old quote!
        df_trades = pd.DataFrame([
            {
                "recv_ts_ns": t0 + 110_000_000,
                "side": "SELL",
                "price": 79985.0,
                "size": 0.001,
                "notional": 79.985,
            }
        ])

        res = backtester.run_simulation(df_bbo=df_bbo, df_trades=df_trades)
        self.assertEqual(res.in_flight_fills_count, 1, "In-flight cancel must be filled during cancel transit latency")
        self.assertEqual(res.pnl_summary["total_trades_count"], 1)
        self.assertTrue(res.pnl_summary["identity_verified"], "Balance-sheet identity must hold after in-flight fill")

    def test_l2_depth_replay_queue_determination(self):
        """Mandate §7: Backtester uses L2 cumulative depth for queue volume."""
        backtester = ArcusEventBacktester(
            strategy=self.strategy,
            fill_model=FillModelType.MODEL_B_MODERATE,
            latency_config=self.latency,
        )

        t0 = 1_000_000_000
        # L2 snapshot with depth
        df_l2 = pd.DataFrame([
            {
                "recv_ts_ns": t0,
                "is_snapshot": True,
                "sequence_id": 100,
                "bids": [[80000.0, 1.5], [79999.0, 2.5]],
                "asks": [[80002.0, 1.2], [80003.0, 3.0]],
            }
        ])

        df_bbo = pd.DataFrame([
            {
                "recv_ts_ns": t0 + 1_000_000,
                "bid_price": 80000.0,
                "ask_price": 80002.0,
                "mid_price": 80001.0,
                "spread_bps": 2.5,
                "bid_size": 1.5,
                "ask_size": 1.2,
            }
        ])

        df_trades = pd.DataFrame([])

        res = backtester.run_simulation(df_bbo=df_bbo, df_trades=df_trades, df_l2=df_l2)
        self.assertEqual(res.fidelity, "HIGH_FIDELITY_L2", "Must record HIGH_FIDELITY_L2 when L2 updates provided")
        self.assertTrue(backtester.orderbook.is_synced)
        # Cumulative depth at 80000.0 in orderbook is 1.5
        self.assertAlmostEqual(backtester.orderbook.get_cumulative_bid_depth(Decimal("80000.0")), 1.5)

    def test_submitting_latency_prevents_premature_fill(self):
        """Mandate §6: An order still in SUBMITTING cannot be filled before place latency passes."""
        backtester = ArcusEventBacktester(
            strategy=self.strategy,
            fill_model=FillModelType.MODEL_A_OPTIMISTIC,
            latency_config=self.latency,
        )

        t0 = 1_000_000_000
        df_bbo = pd.DataFrame([
            {
                "recv_ts_ns": t0,
                "bid_price": 80000.0,
                "ask_price": 80002.0,
                "mid_price": 80001.0,
                "spread_bps": 2.5,
                "bid_size": 2.0,
                "ask_size": 2.0,
            }
        ])

        # Place latency is 35ms (feed 10 + decision 5 + send 10 + ack 5 = 30ms or 35ms)
        # Trade arrives at t0 + 10ms (before place latency expires at t0 + 30ms)
        df_trades = pd.DataFrame([
            {
                "recv_ts_ns": t0 + 10_000_000,
                "side": "SELL",
                "price": 79985.0,
                "size": 0.001,
                "notional": 79.985,
            }
        ])

        res = backtester.run_simulation(df_bbo=df_bbo, df_trades=df_trades)
        self.assertEqual(res.pnl_summary["total_trades_count"], 0, "Order still in transit must not fill")

    def test_cancel_expiration_prevents_fill(self):
        """Mandate §6: Once cancel transit latency passes, order is CANCELLED and does not fill."""
        backtester = ArcusEventBacktester(
            strategy=self.strategy,
            fill_model=FillModelType.MODEL_A_OPTIMISTIC,
            latency_config=self.latency,
        )

        t0 = 1_000_000_000
        df_bbo = pd.DataFrame([
            {
                "recv_ts_ns": t0,
                "bid_price": 80000.0,
                "ask_price": 80002.0,
                "mid_price": 80001.0,
                "spread_bps": 2.5,
                "bid_size": 2.0,
                "ask_size": 2.0,
            },
            # Requote at t0 + 100ms
            {
                "recv_ts_ns": t0 + 100_000_000,
                "bid_price": 79990.0,
                "ask_price": 79992.0,
                "mid_price": 79991.0,
                "spread_bps": 2.5,
                "bid_size": 2.0,
                "ask_size": 2.0,
            },
        ])

        # Cancel transit is 30ms (effective at t0 + 130ms).
        # Trade arrives at t0 + 200ms (> 130ms) -> Must NOT fill expired cancel!
        df_trades = pd.DataFrame([
            {
                "recv_ts_ns": t0 + 200_000_000,
                "side": "SELL",
                "price": 79985.0,
                "size": 0.001,
                "notional": 79.985,
            }
        ])

        res = backtester.run_simulation(df_bbo=df_bbo, df_trades=df_trades)
        self.assertEqual(res.in_flight_fills_count, 0, "Expired cancel order must not fill")

    def test_forced_flatten_executable_sides_with_slippage(self):
        """Mandate §13: Forced flatten liquidates at executable side with slippage, not mid."""
        pnl = PnLAttributionEngine(initial_capital=100.0, maker_fee_bps=0.0, taker_fee_bps=2.25)
        # Buy 1 BTC at $80,000.00
        pnl.record_fill("BUY", 80000.0, 1.0, mid_at_fill=80000.0)
        self.assertEqual(pnl.position, 1.0)

        # Force flatten with executable bid = 80100.0, ask = 80102.0, mid = 80101.0, slippage = 5.0 bps
        # Long position must sell against the BID minus 5 bps:
        # Expected exit price = 80100.0 * (1 - 0.0005) = 80059.95
        pnl.force_flatten(current_bid=80100.0, current_ask=80102.0, current_mid=80101.0, slippage_bps=5.0)
        self.assertEqual(pnl.position, 0.0)
        self.assertEqual(pnl.total_trades_count, 2)
        # Exit fill record check
        exit_fill = pnl.fills[-1]
        self.assertEqual(exit_fill["side"], "SELL")
        self.assertAlmostEqual(exit_fill["price"], 80059.95, places=2)
        self.assertTrue(exit_fill["is_taker"])
        self.assertTrue(pnl.taker_fee_costs > 0)
        self.assertTrue(pnl.verify_accounting_identity(80101.0))


if __name__ == "__main__":
    unittest.main()

