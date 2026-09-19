"""Full Production Strategy: Adaptive Microstructure Market Maker with Overlays.

Fulfills Phase 8 & Phase 9 of prompt.md:
- Core: Dynamic spread based on volatility clock (k * sigma)
- Overlay 1: Microprice & Order Flow Imbalance (OFI) toxic-flow skew
- Overlay 2: Non-linear inventory mean-reverting lean
- Overlay 3: Experimental capital envelope soft-guard ($50–$100 bounds)
- Overlay 4: Requote threshold rate-limit preservation
"""

from typing import Optional, Tuple
from src.strategies.base import BaseMarketMakingStrategy, Quote


class AdaptiveMicrostructureStrategy(BaseMarketMakingStrategy):
    """Adaptive market maker integrating toxic-flow fading and inventory control."""

    def __init__(
        self,
        market: str,
        tick_size: float,
        step_size: float,
        base_spread_bps: float = 4.0,
        vol_multiplier: float = 1.0,
        ofi_skew_factor: float = 1.5,
        inventory_lean_factor: float = 0.8,
        clip_notional: float = 8.0,
        min_notional: float = 5.0,
        max_capital_envelope: float = 100.0,
    ):
        super().__init__(
            market=market,
            tick_size=tick_size,
            step_size=step_size,
            min_notional=min_notional,
            max_capital_envelope=max_capital_envelope,
        )
        self.base_spread_bps = base_spread_bps
        self.vol_multiplier = vol_multiplier
        self.ofi_skew_factor = ofi_skew_factor
        self.inventory_lean_factor = inventory_lean_factor
        self.clip_notional = max(clip_notional, min_notional)

    def generate_quotes(
        self,
        mid_price: float,
        inventory_units: float,
        volatility: float,
        market_spread_bps: float,
        microprice_dev_bps: float = 0.0,
    ) -> Optional[Tuple[Quote, Quote]]:
        if mid_price <= 0:
            return None

        # 1. Capital envelope check: max inventory is 4 clips ($32 out of $100 capital)
        clip_qty = self.clip_notional / mid_price
        inv_clips = inventory_units / clip_qty if clip_qty > 0 else 0.0

        if abs(inv_clips) >= 4.0:
            # Rebalance only: quote only to reduce position
            clip_size = self.round_to_step(clip_qty)
            if inv_clips > 0:
                ask_p = self.round_to_tick(mid_price)
                return (None, Quote(side="SELL", price=ask_p, size=clip_size))
            else:
                bid_p = self.round_to_tick(mid_price)
                return (Quote(side="BUY", price=bid_p, size=clip_size), None)

        # 2. Dynamic Spread Sizing
        # Spread expands with volatility and market spread
        dyn_spread_bps = max(
            self.base_spread_bps,
            (market_spread_bps * 0.8) + (volatility * 5.0 * self.vol_multiplier)
        )
        # Cap spread to reasonable bounds
        dyn_spread_bps = min(35.0, max(2.5, dyn_spread_bps))

        # 3. Skew computation
        # (a) Toxic flow skew: if microprice deviates upward (+dev), buyers are aggressive => shift quotes UP
        flow_skew_bps = microprice_dev_bps * self.ofi_skew_factor

        # (b) Inventory lean: if long (+inv_clips), shift quotes DOWN to attract sellers / deter buyers
        inv_skew_bps = - (inv_clips * self.inventory_lean_factor * (dyn_spread_bps / 4.0))

        total_skew_bps = flow_skew_bps + inv_skew_bps
        # Clamp skew to at most half the spread to avoid crossed quotes
        max_skew = dyn_spread_bps * 0.45
        total_skew_bps = max(-max_skew, min(max_skew, total_skew_bps))

        # Reference center price
        ref_price = mid_price * (1.0 + (total_skew_bps / 10_000.0))

        # 4. Generate Bid and Ask
        half_spread_dollars = (dyn_spread_bps / 2.0) / 10_000.0 * mid_price
        bid_price = self.round_to_tick(ref_price - half_spread_dollars)
        ask_price = self.round_to_tick(ref_price + half_spread_dollars)

        if ask_price <= bid_price:
            ask_price = self.round_to_tick(bid_price + self.tick_size)

        clip_size = self.round_to_step(clip_qty)
        if clip_size <= 0:
            clip_size = self.step_size

        return (
            Quote(side="BUY", price=bid_price, size=clip_size),
            Quote(side="SELL", price=ask_price, size=clip_size),
        )
