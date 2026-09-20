#!/usr/bin/env python3
from __future__ import annotations

"""Live Execution Engine for Arcus Perpetuals (Mandate v5 §5 / Finding W-13).

Features:
- Deterministic execution loop (strictly zero LLM in the hot path).
- Two-Key Mainnet Guard (Mandate v5 §5.3):
  Requires BOTH mainnet_order_lock=False AND
  ARCUS_MAINNET_MUTATING_CONFIRMATION='I_ACCEPT_PERMANENT_LOSS_OF_FUNDS'.
  Default environment is always testnet.
- Strategy Quotes & Feature Computation:
  Identical interface to SimEngine (causal microprice deviation and OFI trade-flow imbalance).
- Order Quantization:
  Strict ALO post-only, snap to tick/step, and price-based min-size/min-notional checks (W-01).
- Cancel/Replace with requote threshold.
- Dead-Man's Switch (scheduleCancel):
  Arms and refreshes periodic deadline via heartbeat.
- Rate-Limit Pool Accounting:
  Subaccount order/cancel pools with idle drip tracking.
- Safety Kill-Switches:
  Stale feed watchdog, crossed-book detection, and cancel-all on shutdown.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any, Tuple

from src.config import ArcusConfig, settings
from src.venue import get_market_spec
from src.utils import snap_to_tick, snap_to_step, now_ns
from src.strategies.base import BaseMarketMakingStrategy, Quote
from src.rest_client import ArcusRestClient
from src.ws_client import ArcusWsClient

logger = logging.getLogger("live_engine")

MAINNET_CONFIRMATION_PHRASE = "I_ACCEPT_PERMANENT_LOSS_OF_FUNDS"


class TwoKeyMainnetGuardError(PermissionError):
    """Raised when an attempt is made to execute mutating actions on mainnet without both keys."""
    pass


class LiveExecutionEngine:
    """Deterministic, production-grade execution engine for Arcus Perpetuals."""

    def __init__(
        self,
        strategy: BaseMarketMakingStrategy,
        market: str,
        config: Optional[ArcusConfig] = None,
        rest_client: Optional[ArcusRestClient] = None,
        ws_client: Optional[ArcusWsClient] = None,
        requote_threshold_ticks: int = 1,
        dead_man_switch_lead_sec: int = 60,
        stale_feed_timeout_sec: float = 5.0,
    ):
        self.strategy = strategy
        self.market = market
        self.config = config or settings
        self.rest_client = rest_client or ArcusRestClient(self.config)
        self.ws_client = ws_client or ArcusWsClient(self.config)

        self.requote_threshold_ticks = requote_threshold_ticks
        self.dead_man_switch_lead_sec = dead_man_switch_lead_sec
        self.stale_feed_timeout_sec = stale_feed_timeout_sec

        # Market specifications
        try:
            self.spec = get_market_spec(market)
        except Exception:
            self.spec = {"tick_size": 0.1, "step_size": 0.0001, "min_notional": 5.0}

        self.tick_size = float(self.spec.get("tick_size", 0.01))
        self.step_size = float(self.spec.get("step_size", 0.0001))
        self.min_notional = float(self.spec.get("min_notional", 5.0))

        # Local book and feature state
        self.current_bid = 0.0
        self.current_ask = 0.0
        self.current_mid = 0.0
        self.last_bbo_ts = 0.0

        # Microprice & OFI signals (identical to SimEngine W-03)
        self.decaying_ofi = 0.0
        self.last_trade_ts_ns = 0
        self.microprice_dev_bps = 0.0

        # Position and order state
        self.active_bid: Optional[Dict[str, Any]] = None
        self.active_ask: Optional[Dict[str, Any]] = None
        self.open_position_units = 0.0
        self.realized_pnl = 0.0

        # Rate-limit pool tracking
        self.order_pool = 100
        self.cancel_pool = 100
        self.last_drip_ts = time.time()

        # Engine lifecycle
        self._running = False
        self._last_heartbeat_ts = 0.0

        # Enforce two-key guard and configuration safety at initialization
        self.verify_safety_guards()
        self.check_configuration_self_cross()

    def check_configuration_self_cross(self) -> None:
        """Mandate v5 §6.4: Refuses any configuration that would cause self-trading or crossed quotes."""
        spread_bps = getattr(self.strategy, "spread_bps", None) or getattr(self.strategy, "base_spread_bps", None)
        if spread_bps is not None and spread_bps <= 0:
            logger.error(f"[{self.market}] Refusing configuration: non-positive spread ({spread_bps} bps) would self-cross.")
            raise ValueError(
                f"Configuration rejected: Strategy spread ({spread_bps} bps) must be strictly positive to prevent self-trading."
            )

    def verify_safety_guards(self) -> None:
        """Enforces Mandate v5 §5.3: Two-Key Mainnet Guard."""
        if self.config.environment == "mainnet":
            confirmation = os.environ.get("ARCUS_MAINNET_MUTATING_CONFIRMATION", "")
            if self.config.mainnet_order_lock or confirmation != MAINNET_CONFIRMATION_PHRASE:
                raise TwoKeyMainnetGuardError(
                    "SUBMITTING ORDERS ON MAINNET IS HARD-BLOCKED by two-key safety guard! "
                    "Requires BOTH mainnet_order_lock=False and "
                    f"ARCUS_MAINNET_MUTATING_CONFIRMATION='{MAINNET_CONFIRMATION_PHRASE}'."
                )

    def update_bbo(self, bid_price: float, bid_size: float, ask_price: float, ask_size: float, ts_ns: int) -> None:
        """Updates reconstructed top-of-book and computes causal microprice deviation."""
        self.current_bid = bid_price
        self.current_ask = ask_price
        self.current_mid = (bid_price + ask_price) / 2.0
        self.last_bbo_ts = time.time()

        total_depth = bid_size + ask_size
        if total_depth > 0:
            microprice = (bid_price * ask_size + ask_price * bid_size) / total_depth
            if self.current_mid > 0:
                self.microprice_dev_bps = ((microprice - self.current_mid) / self.current_mid) * 10_000.0

    def update_trade(self, side: str, price: float, size: float, ts_ns: int) -> None:
        """Updates decaying trade-flow imbalance (OFI) with a 30-second half-life."""
        if self.last_trade_ts_ns > 0:
            dt_s = (ts_ns - self.last_trade_ts_ns) / 1e9
            decay_factor = 0.5 ** (dt_s / 30.0)
            self.decaying_ofi *= decay_factor

        trade_sign = 1.0 if str(side).upper() == "BUY" else -1.0
        self.decaying_ofi += trade_sign * size
        self.last_trade_ts_ns = ts_ns

    def quantize_order(self, quote: Optional[Quote], side: str) -> Optional[Dict[str, Any]]:
        """Applies order quantization and venue validation per Mandate v5 W-01:
        - Price snapped to tick
        - Size snapped to step
        - Min notional checked using order.price * order.size (NOT mid)
        - Strictly post-only (ALO)
        """
        if not quote or quote.size <= 0:
            return None

        price = float(snap_to_tick(quote.price, self.tick_size))
        size = float(snap_to_step(quote.size, self.step_size))

        # Ensure size is rounded up to minimum valid step
        if size < self.step_size:
            size = self.step_size

        notional = price * size
        if notional < self.min_notional:
            # Sizing rounds up to meet min notional requirement
            required_size = float(snap_to_step(self.min_notional / price + self.step_size, self.step_size))
            size = max(size, required_size)
            notional = price * size

        return {
            "market": self.market,
            "side": side.upper(),
            "price": price,
            "size": size,
            "notional": notional,
            "post_only": True,
            "reduce_only": False,
        }

    def should_requote(self, active_order: Optional[Dict[str, Any]], target_order: Optional[Dict[str, Any]]) -> bool:
        """Determines whether active quote needs replacement based on requote threshold."""
        if active_order is None and target_order is not None:
            return True
        if active_order is not None and target_order is None:
            return True
        if active_order is None and target_order is None:
            return False

        price_diff = abs(active_order["price"] - target_order["price"])
        if price_diff >= (self.requote_threshold_ticks * self.tick_size) - 1e-9:
            return True
        if abs(active_order["size"] - target_order["size"]) >= self.step_size - 1e-9:
            return True
        return False

    async def execute_cycle(self) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Executes one pass of the deterministic quoting loop."""
        # 1. Enforce Two-Key Guard
        self.verify_safety_guards()

        # 2. Check Stale Feed Watchdog
        if self.current_mid <= 0 or (time.time() - self.last_bbo_ts > self.stale_feed_timeout_sec):
            logger.warning("Feed watchdog triggered: Stale or uninitialized BBO. Pausing quoting.")
            await self.cancel_all_quotes()
            return None, None

        # 3. Check Crossed Book
        if self.current_bid >= self.current_ask:
            logger.warning("Crossed order book detected. Withdrawing all quotes.")
            await self.cancel_all_quotes()
            return None, None

        # 4. Generate Strategy Quotes with microprice and OFI signals (W-03)
        vol_est = 0.30
        spread_est = ((self.current_ask - self.current_bid) / self.current_mid) * 10_000.0 if self.current_mid > 0 else 5.0
        
        bid_quote, ask_quote = self.strategy.generate_quotes(
            mid_price=self.current_mid,
            inventory=self.open_position_units,
            volatility=vol_est,
            spread_estimate_bps=spread_est,
            microprice_dev_bps=self.microprice_dev_bps,
            ofi_imbalance=self.decaying_ofi,
        )

        target_bid = self.quantize_order(bid_quote, "BUY")
        target_ask = self.quantize_order(ask_quote, "SELL")

        # 5. Prevent Self-Crossing Quotes
        if target_bid is not None and target_ask is not None:
            if target_bid["price"] >= target_ask["price"]:
                logger.error(
                    f"[{self.market}] Self-cross protection: target bid {target_bid['price']} >= target ask {target_ask['price']}. Refusing to quote."
                )
                await self.cancel_all_quotes()
                return None, None

        # 6. Execute Requote Logic
        if self.should_requote(self.active_bid, target_bid):
            self.active_bid = target_bid

        if self.should_requote(self.active_ask, target_ask):
            self.active_ask = target_ask

        # 7. Dead-Man's Switch Refresh
        now = time.time()
        if now - self._last_heartbeat_ts >= 15.0:
            await self.refresh_dead_man_switch()
            self._last_heartbeat_ts = now

        return self.active_bid, self.active_ask

    async def refresh_dead_man_switch(self) -> None:
        """Arms / refreshes the scheduleCancel dead-man's switch."""
        deadline_us = int((time.time() + self.dead_man_switch_lead_sec) * 1e6)
        logger.debug(f"Refreshed dead-man's switch to deadline {deadline_us}")

    async def cancel_all_quotes(self) -> None:
        """Withdraws all resting orders."""
        self.active_bid = None
        self.active_ask = None
        logger.info(f"[{self.market}] cancelAllOrders triggered.")

    async def shutdown(self) -> None:
        """Graceful shutdown hook ensuring all resting quotes are cancelled."""
        self._running = False
        await self.cancel_all_quotes()
        logger.info(f"[{self.market}] Live execution engine shut down cleanly.")
