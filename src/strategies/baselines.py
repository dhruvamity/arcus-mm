from __future__ import annotations

"""Control Baselines for Formal Market Making Validation.

- S0 Do-Nothing Baseline: Zero active quotes, flat inventory, zero PnL.
- Random-Side Quoting Baseline: Randomly quotes only Bid or only Ask (seeded pseudo-randomly).
"""

import random
from typing import Optional, Tuple
from src.strategies.base import BaseMarketMakingStrategy, Quote


class DoNothingStrategy(BaseMarketMakingStrategy):
    """Control Strategy: Posts no quotes; stays 100% idle."""

    def generate_quotes(
        self,
        mid_price: float,
        inventory_units: float,
        volatility: float,
        market_spread_bps: float,
        microprice_dev_bps: float = 0.0,
    ) -> Optional[Tuple[Optional[Quote], Optional[Quote]]]:
        return (None, None)


class RandomSideQuotingStrategy(BaseMarketMakingStrategy):
    """Control Strategy: Randomly selects either Bid or Ask side per tick with static spread."""

    def __init__(
        self,
        market: str,
        tick_size: float,
        step_size: float,
        spread_bps: float = 4.0,
        clip_notional: float = 8.0,
        min_notional: float = 5.0,
        min_order_size: float = 0.0,
        max_capital_envelope: float = 100.0,
        random_seed: int = 42,
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
        self.rng = random.Random(random_seed)

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

        current_inv_notional = abs(inventory_units) * mid_price
        if current_inv_notional >= self.max_capital_envelope:
            return (None, None)

        clip_size = self.calculate_clip_size(self.clip_notional, mid_price)
        if clip_size <= 0:
            clip_size = self.step_size

        half_spread = (self.spread_bps / 2.0) / 10_000.0 * mid_price

        # Randomly choose one side to quote
        if self.rng.random() < 0.5:
            # Quote only BID
            bid_price = self.round_to_tick(mid_price - half_spread)
            bid_size = self.calculate_clip_size(self.clip_notional, bid_price)
            if bid_size <= 0:
                bid_size = self.step_size
            return (Quote(side="BUY", price=bid_price, size=bid_size), None)
        else:
            # Quote only ASK
            ask_price = self.round_to_tick(mid_price + half_spread)
            ask_size = self.calculate_clip_size(self.clip_notional, ask_price)
            if ask_size <= 0:
                ask_size = self.step_size
            return (None, Quote(side="SELL", price=ask_price, size=ask_size))
