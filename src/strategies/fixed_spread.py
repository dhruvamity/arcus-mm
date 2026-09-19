"""Strategy 1: Fixed-Spread Symmetric Quoting (Control Baseline).

Fulfills Section 22 of prompt.md:
- Posts both sides at a static offset from reference price.
- No inventory skew.
- No adaptive spread.
- Flat target inventory.
- Serves as the control benchmark to establish whether raw market making can clear breakeven.
"""

from typing import Optional, Tuple
from src.strategies.base import BaseMarketMakingStrategy, Quote


class FixedSpreadStrategy(BaseMarketMakingStrategy):
    """Posts static symmetric quotes around reference mid-price."""

    def __init__(
        self,
        market: str,
        tick_size: float,
        step_size: float,
        spread_bps: float = 4.0,  # 4 bps total spread (2 bps per side)
        clip_notional: float = 8.0,  # $8 per quote clip
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
        self.spread_bps = spread_bps
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
        if current_inv_notional >= self.max_capital_envelope:
            return None

        half_spread = (self.spread_bps / 2.0) / 10_000.0 * mid_price
        bid_price = self.round_to_tick(mid_price - half_spread)
        ask_price = self.round_to_tick(mid_price + half_spread)

        # Enforce minimum tick separation
        if ask_price <= bid_price:
            ask_price = self.round_to_tick(bid_price + self.tick_size)

        clip_size = self.calculate_clip_size(self.clip_notional, mid_price)
        if clip_size <= 0:
            clip_size = self.step_size

        return (
            Quote(side="BUY", price=bid_price, size=clip_size),
            Quote(side="SELL", price=ask_price, size=clip_size),
        )

