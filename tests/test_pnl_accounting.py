from __future__ import annotations

"""Unit Tests for Rigorous PnL Accounting & Five-Way Attribution.

- Strict balance-sheet identity: Cash + Position * Mid == Equity
- 5-Way attribution summing to Net PnL: Realized Spread + MTM - Fees + Funding == Net PnL
- Separate Maker (0 bps) and Taker (2.25 bps) fee accounting
- Forced exit at executable side with slippage + taker fee (never mid)
- Time-aware funding payment calculations
"""

import unittest
from src.models.pnl import PnLAttributionEngine


class TestPnLAccounting(unittest.TestCase):
    def setUp(self):
        self.engine = PnLAttributionEngine(
            initial_capital=100.0,
            maker_fee_bps=0.0,
            taker_fee_bps=2.25,
        )

    def test_balance_sheet_identity_clean_buy_sell(self):
        """Verify Cash + Position * Mid == Equity across maker round trips."""
        mid = 100.0
        # Buy 1.0 unit at 99.5 (maker)
        self.engine.record_fill(side="BUY", price=99.5, size=1.0, mid_at_fill=100.0, is_taker=False)
        self.assertEqual(self.engine.position, 1.0)
        self.assertAlmostEqual(self.engine.cash, 100.0 - 99.5, places=5)
        self.assertTrue(self.engine.verify_accounting_identity(current_mid=100.0))

        # Mid shifts to 101.0
        mid = 101.0
        self.assertTrue(self.engine.verify_accounting_identity(current_mid=mid))

        # Sell 1.0 unit at 101.5 (maker)
        self.engine.record_fill(side="SELL", price=101.5, size=1.0, mid_at_fill=101.0, is_taker=False)
        self.assertEqual(self.engine.position, 0.0)
        self.assertAlmostEqual(self.engine.cash, 100.0 + 2.0, places=5)
        self.assertAlmostEqual(self.engine.realized_spread_pnl, 2.0, places=5)
        self.assertTrue(self.engine.verify_accounting_identity(current_mid=mid))

    def test_fee_separation_maker_vs_taker(self):
        """Verify maker and taker fees are tracked separately and correctly."""
        # Maker fill: 0 bps fee
        fee_maker = self.engine.record_fill(side="BUY", price=100.0, size=1.0, mid_at_fill=100.0, is_taker=False)
        self.assertEqual(fee_maker, 0.0)
        self.assertEqual(self.engine.maker_fee_costs, 0.0)

        # Taker fill: 2.25 bps fee on $100 notional = $0.0225
        fee_taker = self.engine.record_fill(side="SELL", price=100.0, size=1.0, mid_at_fill=100.0, is_taker=True)
        self.assertAlmostEqual(fee_taker, 0.0225, places=6)
        self.assertAlmostEqual(self.engine.taker_fee_costs, 0.0225, places=6)
        self.assertAlmostEqual(self.engine.total_fee_costs, 0.0225, places=6)

    def test_forced_flatten_executable_prices(self):
        """Verify forced flattening executes on bid/ask with slippage and taker fee, NEVER at mid."""
        # Build long position of 2.0 units
        self.engine.record_fill(side="BUY", price=100.0, size=2.0, mid_at_fill=100.0, is_taker=False)
        self.assertEqual(self.engine.position, 2.0)

        # Force flatten long: must SELL at BID (99.0) minus 2 bps slippage
        bid = 99.0
        ask = 101.0
        mid = 100.0
        slippage_bps = 2.0
        expected_exit_price = bid * (1.0 - 2.0 / 10_000.0)  # 98.9802

        fee = self.engine.force_flatten(current_bid=bid, current_ask=ask, current_mid=mid, slippage_bps=slippage_bps)
        self.assertGreater(fee, 0.0)
        self.assertEqual(self.engine.position, 0.0)
        last_fill = self.engine.fills[-1]
        self.assertEqual(last_fill["side"], "SELL")
        self.assertAlmostEqual(last_fill["price"], expected_exit_price, places=5)
        self.assertTrue(last_fill["is_taker"])
        self.assertNotEqual(last_fill["price"], mid)
        self.assertTrue(self.engine.verify_accounting_identity(current_mid=mid))

        # Test short forced flatten: must BUY at ASK (101.0) plus 2 bps slippage
        self.engine.record_fill(side="SELL", price=100.0, size=1.0, mid_at_fill=100.0, is_taker=False)
        self.assertEqual(self.engine.position, -1.0)

        expected_short_exit = ask * (1.0 + 2.0 / 10_000.0)  # 101.0202
        self.engine.force_flatten(current_bid=bid, current_ask=ask, current_mid=mid, slippage_bps=slippage_bps)
        self.assertEqual(self.engine.position, 0.0)
        short_fill = self.engine.fills[-1]
        self.assertEqual(short_fill["side"], "BUY")
        self.assertAlmostEqual(short_fill["price"], expected_short_exit, places=5)
        self.assertTrue(short_fill["is_taker"])
        self.assertTrue(self.engine.verify_accounting_identity(current_mid=mid))

    def test_funding_accounting(self):
        """Verify time-aware funding payment is correctly applied to cash and attribution."""
        self.engine.record_fill(side="BUY", price=100.0, size=2.0, mid_at_fill=100.0, is_taker=False)
        # Position is +2.0 long. Positive funding rate means long pays short.
        # Payment = - (pos * mid * rate) = - (2.0 * 100 * 0.0001) = -0.02
        payment = self.engine.apply_funding(funding_rate=0.0001, current_mid=100.0)
        self.assertAlmostEqual(payment, -0.02, places=6)
        self.assertAlmostEqual(self.engine.total_funding_pnl, -0.02, places=6)
        self.assertTrue(self.engine.verify_accounting_identity(current_mid=100.0))

    def test_w04_no_unsupported_maker_rebate_constants(self):
        """W-04: Verifies no script contains a maker rebate constant not equal to venue config."""
        import yaml
        import re
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        cfg_path = repo_root / "configs" / "venue_verified.yaml"
        with open(cfg_path, "r", encoding="utf-8") as f:
            venue_cfg = yaml.safe_load(f)

        rebates_avail = venue_cfg.get("fees", {}).get("rebates_available", False)
        base_rebate = venue_cfg.get("fees", {}).get("base_tier", {}).get("maker_rebate_bps", 0.0) if rebates_avail else 0.0

        scripts_to_check = [
            repo_root / "scripts" / "run_pilot_analysis.py",
            repo_root / "scripts" / "verify_report.py",
        ]
        pattern = re.compile(r"^\s*(?:CANONICAL_)?MAKER_REBATE_BPS\s*=\s*([0-9.]+)", re.MULTILINE)

        mismatches = []
        for p in scripts_to_check:
            if not p.exists():
                continue
            content = p.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                val = float(match.group(1))
                if abs(val - base_rebate) > 1e-6:
                    mismatches.append(f"{p.name}: found MAKER_REBATE_BPS = {val}, expected {base_rebate}")

        self.assertEqual(len(mismatches), 0, f"Maker rebate constants must match venue config ({base_rebate} bps): {mismatches}")


if __name__ == "__main__":
    unittest.main()
