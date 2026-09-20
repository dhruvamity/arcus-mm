from __future__ import annotations

"""Tests for Backtester Execution, Paper Telemetry, and Walk-Forward Smoke."""

import unittest
import pandas as pd

from src.sim.engine import ArcusEventBacktester
from src.models.fill import FillModelType
from src.models.rate_limit import ArcusRateLimitSimulator
from src.strategies.fixed_spread import FixedSpreadStrategy
from src.walk_forward import WalkForwardValidator


class TestBacktesterExecution(unittest.TestCase):
    """Verifies that the core backtester executes end-to-end on synthetic data."""

    def test_backtester_minimal_end_to_end_run(self):
        """P0-1: Asserts that ArcusEventBacktester executes without parameter mismatch."""
        strategy = FixedSpreadStrategy(
            market="BTC-USD",
            tick_size=0.1,
            step_size=0.00000001,
            spread_bps=10.0,
            clip_notional=8.15,
            min_notional=5.0,
        )
        backtester = ArcusEventBacktester(
            strategy=strategy,
            fill_model=FillModelType.MODEL_B_MODERATE,
            initial_capital=100.0,
            maker_fee_bps=0.0,
        )

        # Create synthetic BBO data: mid = $100.0, bid = $99.95, ask = $100.05
        t0 = 1_000_000_000  # 1s in ns
        bbo_rows = []
        for i in range(10):
            t = t0 + i * int(1e8)  # 100ms ticks
            bbo_rows.append({
                "recv_ts_ns": t,
                "mid_price": 100.0,
                "spread_bps": 10.0,
                "bid_price": 99.95,
                "bid_size": 1.0,
                "ask_price": 100.05,
                "ask_size": 1.0,
            })
        df_bbo = pd.DataFrame(bbo_rows)

        # Create synthetic Trade data: trades at $99.95 (taker sell fills maker buy)
        # Trade at t = t0 + 500ms (after quote transit latency)
        trade_rows = [
            {
                "recv_ts_ns": t0 + int(5e8),
                "price": 99.95,
                "size": 0.0815,
                "side": "SELL",
            },
            {
                "recv_ts_ns": t0 + int(8e8),
                "price": 100.05,
                "size": 0.0815,
                "side": "BUY",
            },
        ]
        df_trades = pd.DataFrame(trade_rows)

        # Run backtest simulation - MUST NOT crash on record_fill
        result = backtester.run_simulation(
            df_bbo=df_bbo,
            df_trades=df_trades,
            funding_data=[{"timestamp": t0, "fundingRate": 0.0001}],
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.market, "BTC-USD")
        self.assertTrue(result.pnl_summary["total_trades_count"] >= 0)
        # Verify that accounting identity holds at the end of the simulation
        self.assertTrue(
            backtester.pnl_engine.verify_accounting_identity(backtester.latest_mid_price)
        )

    def test_paper_telemetry_after_60_seconds_equivalent(self):
        """P0-3: Asserts that rate limiter exposes get_pool_status() without AttributeError."""
        limiter = ArcusRateLimitSimulator(order_pool_cap=20_000, cancel_pool_cap=40_000)

        # Perform simulated actions
        self.assertTrue(limiter.record_order_placement())
        self.assertTrue(limiter.record_order_modification())
        self.assertTrue(limiter.record_order_cancellation())
        limiter.record_fill(fill_notional=100.0)

        status = limiter.get_pool_status()
        self.assertIsInstance(status, dict)
        self.assertIn("order_units_available", status)
        self.assertIn("cancel_units_available", status)
        self.assertIn("total_actions_used", status)
        self.assertIn("orders_placed", status)
        self.assertIn("orders_modified", status)
        self.assertIn("orders_cancelled", status)

        self.assertEqual(status["orders_placed"], 1)
        self.assertEqual(status["orders_modified"], 1)
        self.assertEqual(status["orders_cancelled"], 1)
        self.assertEqual(status["total_actions_used"], 3)

    def test_walk_forward_cli_smoke(self):
        """P0-2: Asserts that WalkForwardValidator imports and executes without NameError."""
        validator = WalkForwardValidator(in_sample_ratio=0.60)
        specs = {
            "tick_size": 0.1,
            "step_size": 0.00000001,
            "min_notional": 5.0,
        }

        # Construct synthetic dataframe
        t0 = 1_000_000_000
        bbo_rows = []
        trade_rows = []
        for i in range(20):
            t = t0 + i * int(1e8)
            bbo_rows.append({
                "recv_ts_ns": t,
                "mid_price": 100.0,
                "spread_bps": 10.0,
                "bid_price": 99.95,
                "bid_size": 1.0,
                "ask_price": 100.05,
                "ask_size": 1.0,
            })
            if i % 5 == 0:
                trade_rows.append({
                    "recv_ts_ns": t + int(5e7),
                    "price": 99.95,
                    "size": 0.1,
                    "side": "SELL",
                })

        df_bbo = pd.DataFrame(bbo_rows)
        df_trades = pd.DataFrame(trade_rows)

        # Must execute without Optional NameError
        wf_res = validator.run_walk_forward(
            market="BTC-USD",
            specs=specs,
            df_bbo=df_bbo,
            df_trades=df_trades,
            funding_data=None,
        )

        self.assertIn("in_sample", wf_res)
        self.assertIn("out_of_sample", wf_res)
        self.assertIn("stress_oos_model_c", wf_res)


if __name__ == "__main__":
    unittest.main()
