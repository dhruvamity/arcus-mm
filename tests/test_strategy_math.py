"""Unit Tests for Strategy Mathematics, Quantization, and Volatility.

Fulfills Mandate Sections 10, 11, 16, 17 & 44:
- Exact integer quantization (round_to_tick, round_to_step)
- Per-market minimum executable clip derivation
- Dimensionally consistent Avellaneda-Stoikov formulation
- Empirical kappa calibration vs uncalibrated labeling
- Jump-clipped EWMA realized volatility estimation
"""

import unittest
import pandas as pd
from src.strategies.fixed_spread import FixedSpreadStrategy
from src.strategies.avellaneda_stoikov import AvellanedaStoikovStrategy, calibrate_kappa_from_trades
from src.volatility import RealizedVolatilityEstimator


class TestStrategyMath(unittest.TestCase):
    def test_snap_to_tick_and_step(self):
        """Verify exact decimal quantization eliminates float precision artifacts."""
        strat = FixedSpreadStrategy(
            market="TEST-USD",
            tick_size=0.001,
            step_size=0.0001,
        )
        price = 12.3456789
        snapped_p = strat.round_to_tick(price)
        self.assertEqual(snapped_p, 12.346)

        size = 1.2345678
        snapped_s = strat.round_to_step(size)
        self.assertEqual(snapped_s, 1.2345)

    def test_per_market_minimum_executable_clip(self):
        """Verify clip satisfies max(minOrderNotional, minOrderSize * price)."""
        strat_1 = FixedSpreadStrategy(
            market="ZEC-USD",
            tick_size=0.001,
            step_size=0.000001,
            min_notional=5.0,
            min_order_size=0.1,  # at $153.40, min size notional is $15.34
        )
        clip_1 = strat_1.get_min_executable_clip(153.40)
        self.assertAlmostEqual(clip_1, 15.34, places=2)

        strat_2 = FixedSpreadStrategy(
            market="NEAR-USD",
            tick_size=0.001,
            step_size=0.000001,
            min_notional=5.0,
            min_order_size=0.1,  # at $2.50, min size notional is $0.25 -> 5.0 dominates
        )
        clip_2 = strat_2.get_min_executable_clip(2.50)
        self.assertAlmostEqual(clip_2, 5.0, places=2)

    def test_avellaneda_stoikov_dimensional_consistency(self):
        """Verify A-S quotes skew correctly with inventory under dimensional normalization."""
        mid = 100.0
        strat = AvellanedaStoikovStrategy(
            market="TEST-USD",
            tick_size=0.01,
            step_size=0.001,
            gamma=0.1,
            kappa=1.5,
            control_horizon_hours=0.5,
            clip_notional=10.0,
        )

        # Quotes with 0 inventory
        bid_0, ask_0 = strat.generate_quotes(mid_price=mid, inventory_units=0.0, volatility=0.30, market_spread_bps=4.0)
        self.assertIsNotNone(bid_0)
        self.assertIsNotNone(ask_0)
        spread_0 = ask_0.price - bid_0.price
        self.assertGreater(spread_0, 0.0)

        # Quotes with long inventory (+10 units = $1000 >> envelope)
        # Should lean towards selling
        bid_long, ask_long = strat.generate_quotes(mid_price=mid, inventory_units=0.5, volatility=0.30, market_spread_bps=4.0)
        self.assertIsNotNone(bid_long)
        self.assertIsNotNone(ask_long)
        # When long, bid is lower and ask is lower (incentivizing sell, penalizing buy)
        self.assertLessEqual(bid_long.price, bid_0.price)
        self.assertLessEqual(ask_long.price, ask_0.price)

    def test_as_kappa_uncalibrated_warning(self):
        """Verify strategy flags uncalibrated state when empirical kappa is not fitted."""
        strat = AvellanedaStoikovStrategy(
            market="TEST-USD",
            tick_size=0.01,
            step_size=0.001,
            is_calibrated=False,
        )
        self.assertFalse(strat.is_calibrated)
        self.assertEqual(strat.status, "A-S NOT CALIBRATED")

        # Test calibration function
        df_trades_empty = pd.DataFrame()
        kappa, res = calibrate_kappa_from_trades(df_trades_empty, duration_hours=0.0)
        self.assertFalse(res["is_calibrated"])
        self.assertIn("NOT CALIBRATED", res["status"])

        # Test calibration with sufficient trades
        df_trades = pd.DataFrame([
            {"price": 100.0, "size": 1.0} for _ in range(50)
        ])
        kappa_fitted, res_fitted = calibrate_kappa_from_trades(df_trades, duration_hours=1.0)
        self.assertTrue(res_fitted["is_calibrated"])
        self.assertEqual(res_fitted["status"], "CALIBRATED")
        self.assertGreater(kappa_fitted, 0.0)

    def test_realized_volatility_jump_clipping(self):
        """Verify 500 bps jump clipping prevents outlier distortion in volatility estimator."""
        estimator = RealizedVolatilityEstimator(half_life_sec=60.0, max_jump_bps=500.0)

        t0 = 1_000_000_000_000_000_000  # 1.0s in ns
        estimator.update(ts_ns=t0, mid_price=100.0)

        # Next second: normal return (5 bps move = 100.05)
        estimator.update(ts_ns=t0 + 1_000_000_000, mid_price=100.05)
        vol_normal = estimator.get_annualized_volatility()
        self.assertGreater(vol_normal, 0.0)

        # Next second: massive 2000 bps jump (price goes to 120.0)
        # It must be clipped to max 500 bps (5%)
        estimator.update(ts_ns=t0 + 2_000_000_000, mid_price=120.0)
        vol_clipped = estimator.get_annualized_volatility()
        # Annualized vol shouldn't blow up beyond reason
        self.assertLess(vol_clipped, 50.0)
        self.assertEqual(estimator.outliers_clipped, 1)


if __name__ == "__main__":
    unittest.main()
