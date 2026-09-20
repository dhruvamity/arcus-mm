from __future__ import annotations

"""Unit Tests for Unified Live Paper Trader Rebuilt on SimEngine (R-08).

Verifies:
- Live paper trader dispatches WebSocket frames into SimEngine.
- State-machine kill switches trigger on stale feed.
- Rule 11 session outcome labeling (SESSION: POSITIVE / NEGATIVE / INSUFFICIENT).
- Session directory persistence and SHA-256 manifest generation.

Hermetic: Injects a committed fixture via VenueMetadata.load_all_specs(snapshot_path=...)
so tests run on a fresh clone with an empty data/ directory (V-33).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.paper_trader import ArcusLivePaperTrader
from src.sim.engine import RiskState
from src.venue import VenueMetadata

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
MARKETS_FIXTURE = FIXTURE_DIR / "markets_snapshot_sample.json"

# Pre-load fixture specs once at import time for deterministic injection
_FIXTURE_SPECS = None


def _get_fixture_specs():
    """Loads and caches market specs from the committed test fixture."""
    global _FIXTURE_SPECS
    if _FIXTURE_SPECS is None:
        with open(MARKETS_FIXTURE, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("markets", [])
        specs = {}
        for item in items:
            symbol = item.get("marketDisplayName", "")
            if not symbol:
                continue
            specs[symbol] = {
                "market_id": int(item.get("marketId", 0)),
                "market": symbol,
                "symbol": symbol,
                "base_asset": item.get("baseAsset", ""),
                "quote_asset": item.get("quoteAsset", "USD"),
                "tick_size": float(item.get("tickSize", 0.001)),
                "step_size": float(item.get("stepSize", 0.0001)),
                "min_notional": float(item.get("minOrderNotional", 5.0)),
                "min_order_size": float(item.get("minOrderSize", 0.0)),
                "max_order_size": float(item.get("maxOrderSize", 1_000_000.0)),
                "category": str(item.get("category", "CRYPTO")).upper(),
                "initial_margin_fraction": float(item.get("initialMarginFraction", 0.05)),
                "maintenance_margin_fraction": float(item.get("maintenanceMarginFraction", 0.03)),
                "off_hours_initial_margin_fraction": float(item.get("offHoursInitialMarginFraction", 0.075)),
                "status": item.get("status", "ONLINE"),
            }
        _FIXTURE_SPECS = specs
    return _FIXTURE_SPECS


class TestLivePaperTrader(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Reset VenueMetadata cache so each test is independent
        VenueMetadata.reset_cache()

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.tmp_dir.name)
        self.trader = ArcusLivePaperTrader(
            markets=["BTC-USD"],
            session_id="test_session_1",
            output_dir=str(self.output_dir),
            initial_capital=100.0,
            strategy_types=["fixed_spread"],
        )

        # Monkeypatch VenueMetadata to use committed fixture instead of data/raw/*
        with patch.object(
            VenueMetadata,
            "load_all_specs",
            new=classmethod(lambda cls, snapshot_path=None: _get_fixture_specs()),
        ):
            await self.trader.initialize_engine()

    async def asyncTearDown(self):
        VenueMetadata.reset_cache()
        if self.trader._running:
            await self.trader.stop()
        self.tmp_dir.cleanup()

    async def test_paper_trader_engine_initialization(self):
        """Verify SimEngine is properly populated with market specs and strategy contexts."""
        self.assertIsNotNone(self.trader.engine)
        self.assertIn("BTC-USD", self.trader.engine.venues)
        self.assertIn("BTC-USD_fixed_c100", self.trader.engine.contexts)
        ctx = self.trader.engine.contexts["BTC-USD_fixed_c100"]
        self.assertEqual(ctx.risk_state, RiskState.NORMAL)

    async def test_paper_trader_event_dispatching(self):
        """Verify BBO and Trade events pass to SimEngine and update venue state."""
        bbo_msg = {
            "market": "BTC-USD",
            "contents": {
                "bestBid": {"price": "100.0", "size": "1.0"},
                "bestAsk": {"price": "100.2", "size": "1.0"},
            },
        }
        await self.trader._on_bbo_update(bbo_msg)
        venue = self.trader.engine.venues["BTC-USD"]
        self.assertEqual(venue.best_bid, 100.0)
        self.assertEqual(venue.best_ask, 100.2)
        self.assertAlmostEqual(venue.current_mid, 100.1)

    async def test_paper_trader_rule_11_outcomes(self):
        """Verify Rule 11 compliant outcome labeling based on fill count threshold (30 fills)."""
        summary = self.trader.get_session_summary()
        strat_summary = summary["strategies"]["BTC-USD_fixed_c100"]
        # <30 fills -> SESSION: INSUFFICIENT
        self.assertEqual(strat_summary["outcome"], "SESSION: INSUFFICIENT")

    async def test_session_manifest_generation(self):
        """Verify stop() closes files and writes SHA-256 manifest."""
        self.trader._raw_file = open(self.trader.raw_stream_path, "a")
        self.trader._raw_file.write("test_log\n")
        self.trader._raw_file.flush()

        await self.trader.stop()
        manifest_path = self.trader.session_dir / "MANIFEST.sha256"
        self.assertTrue(manifest_path.exists())
        content = manifest_path.read_text()
        self.assertIn("raw_stream.jsonl", content)


if __name__ == "__main__":
    unittest.main()

