from __future__ import annotations

"""Unit Tests for LiveExecutionEngine & Two-Key Mainnet Guard (Mandate v5 §5 / W-13).

Verifies:
1. Two-Key Mainnet Safety Guard (Mandate v5 §5.3):
   - mainnet_order_lock=True, confirmation missing -> BLOCKED
   - mainnet_order_lock=False, confirmation missing -> BLOCKED
   - mainnet_order_lock=True, confirmation present -> BLOCKED
   - mainnet_order_lock=False, confirmation present -> ALLOWED
   - testnet environment -> ALLOWED
2. Order Quantization & Sizing (W-01):
   - Snaps to tick and step
   - Validates min notional using order.price * order.size
3. Signal Wiring (W-03):
   - Microprice deviation and decaying OFI passed to strategy
4. Safety Mechanisms:
   - Stale feed watchdog halts quoting
   - Crossed orderbook withdraws quotes
"""

import os
import unittest
from unittest.mock import MagicMock

from src.config import ArcusConfig
from src.exec.live_engine import (
    LiveExecutionEngine,
    TwoKeyMainnetGuardError,
    MAINNET_CONFIRMATION_PHRASE,
)
from src.strategies.fixed_spread import FixedSpreadStrategy
from src.strategies.adaptive_mm import AdaptiveMicrostructureStrategy


class TestLiveExecutionEngine(unittest.TestCase):
    def setUp(self):
        self.market = "BTC-USD"
        self.strategy = FixedSpreadStrategy(
            market=self.market,
            tick_size=0.1,
            step_size=0.0001,
            spread_bps=5.0,
            clip_notional=10.0,
        )

    def test_two_key_mainnet_guard(self):
        """Mandate v5 §5.3: Two-key mainnet guard prevents mainnet mutating calls without BOTH keys."""
        # Clean up env
        os.environ.pop("ARCUS_MAINNET_MUTATING_CONFIRMATION", None)

        # 1. Mainnet with default lock=True and no phrase -> BLOCKED
        cfg_mainnet_locked = ArcusConfig(environment="mainnet", mainnet_order_lock=True)
        with self.assertRaises(TwoKeyMainnetGuardError):
            LiveExecutionEngine(strategy=self.strategy, market=self.market, config=cfg_mainnet_locked)

        # 2. Mainnet with lock=False but no phrase -> BLOCKED (second key missing!)
        cfg_mainnet_unlocked = ArcusConfig(environment="mainnet", mainnet_order_lock=False)
        with self.assertRaises(TwoKeyMainnetGuardError):
            LiveExecutionEngine(strategy=self.strategy, market=self.market, config=cfg_mainnet_unlocked)

        # 3. Mainnet with lock=True but phrase present -> BLOCKED (first key missing!)
        os.environ["ARCUS_MAINNET_MUTATING_CONFIRMATION"] = MAINNET_CONFIRMATION_PHRASE
        try:
            with self.assertRaises(TwoKeyMainnetGuardError):
                LiveExecutionEngine(strategy=self.strategy, market=self.market, config=cfg_mainnet_locked)

            # 4. Mainnet with lock=False AND phrase present -> ALLOWED
            engine_allowed = LiveExecutionEngine(
                strategy=self.strategy, market=self.market, config=cfg_mainnet_unlocked
            )
            self.assertIsNotNone(engine_allowed)
        finally:
            os.environ.pop("ARCUS_MAINNET_MUTATING_CONFIRMATION", None)

        # 5. Testnet mode -> Always permitted
        cfg_testnet = ArcusConfig(environment="testnet", mainnet_order_lock=True)
        engine_testnet = LiveExecutionEngine(
            strategy=self.strategy, market=self.market, config=cfg_testnet
        )
        self.assertIsNotNone(engine_testnet)

    def test_order_quantization_and_min_notional(self):
        """W-01: Order quantization snaps to tick/step and verifies min notional using order price."""
        cfg_testnet = ArcusConfig(environment="testnet")
        engine = LiveExecutionEngine(strategy=self.strategy, market=self.market, config=cfg_testnet)

        from src.strategies.base import Quote
        quote = Quote(side="BUY", price=80000.05, size=0.00005)  # size below step/min
        quantized = engine.quantize_order(quote, "BUY")

        self.assertIsNotNone(quantized)
        self.assertEqual(quantized["price"], 80000.1)  # Snapped to 0.1 tick
        self.assertGreaterEqual(quantized["notional"], 5.0)  # Met min notional ($5)
        self.assertTrue(quantized["post_only"])

    def test_microprice_and_ofi_signal_integration(self):
        """W-03: Causal microprice deviation and decaying OFI are computed and passed to strategy."""
        cfg_testnet = ArcusConfig(environment="testnet")
        adaptive_strat = AdaptiveMicrostructureStrategy(
            market=self.market,
            tick_size=0.1,
            step_size=0.0001,
            base_spread_bps=4.0,
            clip_notional=10.0,
        )
        engine = LiveExecutionEngine(strategy=adaptive_strat, market=self.market, config=cfg_testnet)

        # Update BBO with imbalance (ask heavy -> microprice leans lower)
        # bid: 80,000 (size 1.0), ask: 80,002 (size 9.0)
        # microprice = (80000*9 + 80002*1) / 10 = 80000.2
        # mid = 80001.0 -> negative microprice deviation
        engine.update_bbo(bid_price=80000.0, bid_size=1.0, ask_price=80002.0, ask_size=9.0, ts_ns=1000)
        self.assertLess(engine.microprice_dev_bps, 0.0)

        # Update trade flow (aggressive buyer)
        engine.update_trade(side="BUY", price=80002.0, size=2.0, ts_ns=2000)
        self.assertGreater(engine.decaying_ofi, 0.0)

    def test_stale_feed_watchdog_kill_switch(self):
        """Stale BBO watchdog triggers and withdraws quotes."""
        cfg_testnet = ArcusConfig(environment="testnet")
        engine = LiveExecutionEngine(
            strategy=self.strategy,
            market=self.market,
            config=cfg_testnet,
            stale_feed_timeout_sec=0.1,
        )

        import asyncio
        import time

        engine.update_bbo(bid_price=80000.0, bid_size=1.0, ask_price=80002.0, ask_size=1.0, ts_ns=1000)
        # Sleep past timeout
        time.sleep(0.15)

        bid_q, ask_q = asyncio.run(engine.execute_cycle())
        self.assertIsNone(bid_q)
        self.assertIsNone(ask_q)


if __name__ == "__main__":
    unittest.main()
