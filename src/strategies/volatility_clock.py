from __future__ import annotations

"""Strategy 3: Volatility-Clock Spread Sizing.

- Spread proportional to k * sigma from dynamic realized volatility estimator.
- Dynamic spread adaptation to volatility bursts.
- Inventory lean: shifts reservation price to induce rebalancing fills.
- Exact Decimal quantization and runtime per-market clip sizing.
"""

from typing import Optional, Tuple
from src.strategies.base import BaseMarketMakingStrategy, Quote


class VolatilityClockStrategy(BaseMarketMakingStrategy):
    """Dynamically sizes quotes based on short-term realized volatility."""

    def __init__(
        self,
        market: str,
        tick_size: float,
        step_size: float,
        k_factor: float = 1.2,  # Multiplier on volatility
        min_spread_bps: float = 3.0,
        max_spread_bps: float = 30.0,
        inventory_skew_factor: float = 0.5,  # Leaning factor per clip of inventory
        clip_notional: float = 8.0,
        min_notional: float = 5.0,
        min_order_size: float = 0.0,
        max_capital_envelope: float = 100.0,
    ):
        super().__init__(
            market=market,
            tick_size=tick_size,
            step_size=step_size,
            min_notional=min_notional,
            min_order_size=min_order_size,
            max_capital_envelope=max_capital_envelope,
        )
        self.k_factor = k_factor
        self.min_spread_bps = min_spread_bps
        self.max_spread_bps = max_spread_bps
        self.inventory_skew_factor = inventory_skew_factor
        self.clip_notional = max(clip_notional, min_notional)

    def generate_quotes(
        self,
        mid_price: float,
        inventory_units: float,
        volatility: float,
        market_spread_bps: float,
        microprice_dev_bps: float = 0.0,
    ) -> Optional[Tuple[Optional[Quote], Optional[Quote]]]:
        if mid_price <= 0:
            return None

        # Check capital envelope limit
        current_inv_notional = abs(inventory_units) * mid_price
        clip_size = self.calculate_clip_size(self.clip_notional, mid_price)
        if clip_size <= 0:
            clip_size = self.step_size

        if current_inv_notional >= self.max_capital_envelope:
            # Soft stop: quote only to reduce inventory
            half_sp = (market_spread_bps / 20_000.0) * mid_price
            if inventory_units > 0:
                ask = self.round_to_tick(mid_price + half_sp)
                return (None, Quote(side="SELL", price=ask, size=clip_size))
            else:
                bid = self.round_to_tick(mid_price - half_sp)
                return (Quote(side="BUY", price=bid, size=clip_size), None)

        # 1. Compute dynamic spread bps = max(min_spread, k * sigma_bps)
        # Volatility is annualized float (e.g. 0.30 for 30%); convert to intraday bps
        daily_vol_bps = (volatility / (365.25 ** 0.5)) * 10_000.0
        hourly_vol_bps = daily_vol_bps / (24.0 ** 0.5)
        raw_spread_bps = self.k_factor * (hourly_vol_bps / 5.0)
        clamped_spread_bps = max(self.min_spread_bps, min(self.max_spread_bps, raw_spread_bps))

        # 2. Inventory skew: shift reference price opposite to position
        q_clips = inventory_units / clip_size if clip_size > 0 else 0.0
        skew_bps = q_clips * self.inventory_skew_factor * (clamped_spread_bps / 4.0)
        skew_bps = max(-clamped_spread_bps * 0.8, min(clamped_spread_bps * 0.8, skew_bps))

        ref_price = mid_price * (1.0 - (skew_bps / 10_000.0))

        half_spread_dollars = (clamped_spread_bps / 2.0) / 10_000.0 * mid_price
        bid_price = self.round_to_tick(ref_price - half_spread_dollars)
        ask_price = self.round_to_tick(ref_price + half_spread_dollars)

        if ask_price <= bid_price:
            ask_price = self.round_to_tick(bid_price + self.tick_size)

        return (
            Quote(side="BUY", price=bid_price, size=clip_size),
            Quote(side="SELL", price=ask_price, size=clip_size),
        )
