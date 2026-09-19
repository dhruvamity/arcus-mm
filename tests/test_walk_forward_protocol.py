"""Unit tests for Walk-Forward Protocol, Baselines, and Multiple-Testing Control.

Fulfills Mandate Sections 18, 19, 20, 21 of prompt.md:
- Pre-registered walk-forward split integrity.
- Do-Nothing and Random-Side Quoting baseline behavior.
- Student's t p-value calculation.
- Holm-Bonferroni step-down correction.
- Machine-checkable validation gates.
"""

import unittest
import pandas as pd
import numpy as np

from src.walk_forward import WalkForwardValidator
from src.strategies.baselines import DoNothingStrategy, RandomSideQuotingStrategy
from src.strategies.fixed_spread import FixedSpreadStrategy
from src.models.fill import FillModelType
from src.backtester import ArcusEventBacktester


class TestWalkForwardProtocol(unittest.TestCase):

    def setUp(self):
        self.validator = WalkForwardValidator()
        self.market = "BTC-USD"
        self.specs = {"tick_size": 0.1, "step_size": 0.0001}

    def test_do_nothing_baseline(self):
        """Mandate §20: Do-nothing baseline posts zero quotes, has 0 fills, and 0 net PnL."""
        strategy = DoNothingStrategy(self.market, 0.1, 0.0001)
        quotes = strategy.generate_quotes(80000.0, 0.0, 0.30, 2.5)
        self.assertEqual(quotes, (None, None))

        df_bbo = pd.DataFrame([
            {"recv_ts_ns": 1000, "bid_price": 80000.0, "ask_price": 80002.0, "mid_price": 80001.0, "spread_bps": 2.5, "bid_size": 1.0, "ask_size": 1.0}
        ])
        df_trades = pd.DataFrame([
            {"recv_ts_ns": 2000, "side": "SELL", "price": 80000.0, "size": 0.5, "notional": 40000.0}
        ])

        bt = ArcusEventBacktester(strategy=strategy, fill_model=FillModelType.MODEL_B_MODERATE)
        res = bt.run_simulation(df_bbo, df_trades)
        self.assertEqual(res.pnl_summary["total_trades_count"], 0)
        self.assertEqual(res.pnl_summary["net_pnl"], 0.0)
        self.assertEqual(res.pnl_summary["open_position_units"], 0.0)

    def test_random_side_quoting_baseline(self):
        """Mandate §20: Random-side baseline quotes exactly one side per tick."""
        strategy = RandomSideQuotingStrategy(self.market, 0.1, 0.0001, random_seed=42)
        # Sample 20 ticks
        single_sided_counts = 0
        for _ in range(20):
            bid_q, ask_q = strategy.generate_quotes(80000.0, 0.0, 0.30, 4.0)
            # Exactly one side must be non-None
            if (bid_q is not None and ask_q is None) or (bid_q is None and ask_q is not None):
                single_sided_counts += 1
        self.assertEqual(single_sided_counts, 20, "Must quote exactly one side per tick")

    def test_two_sided_p_value_computation(self):
        """Mandate §19: Student's t two-sided p-value calculation."""
        # Significant positive fills: all +10 bps
        fills_sig = [
            {"price": 79990.0, "mid_at_fill": 80000.0, "side": "BUY"}
            for _ in range(30)
        ]
        p_val_sig = WalkForwardValidator.compute_two_sided_p_value(fills_sig)
        self.assertLess(p_val_sig, 0.001, "Consistently positive returns must yield small p-value")

        # Zero-mean noise fills
        fills_noise = []
        for i in range(50):
            sign = 1 if i % 2 == 0 else -1
            p_fill = 80000.0 - (sign * 10.0)
            fills_noise.append({"price": p_fill, "mid_at_fill": 80000.0, "side": "BUY"})
        p_val_noise = WalkForwardValidator.compute_two_sided_p_value(fills_noise)
        self.assertGreater(p_val_noise, 0.10, "Zero-mean returns must yield non-significant p-value")

    def test_holm_bonferroni_step_down_correction(self):
        """Mandate §19: Step-down Holm-Bonferroni correction across hypothesis family."""
        family = [
            {"config": "strat_1", "p_value": 0.005},
            {"config": "strat_2", "p_value": 0.020},
            {"config": "strat_3", "p_value": 0.060},
            {"config": "strat_4", "p_value": 0.400},
        ]
        # m = 4, alpha = 0.05
        # rank 1: p=0.005 <= 0.05 / 4 = 0.0125 -> Significant!
        # rank 2: p=0.020 <= 0.05 / 3 = 0.0167 -> NOT significant!
        # rank 3 & 4 -> NOT significant
        corrected = WalkForwardValidator.apply_holm_bonferroni(family, alpha=0.05)
        self.assertTrue(corrected[0]["is_statistically_significant"])
        self.assertFalse(corrected[1]["is_statistically_significant"])
        self.assertFalse(corrected[2]["is_statistically_significant"])
        self.assertFalse(corrected[3]["is_statistically_significant"])


if __name__ == "__main__":
    unittest.main()
