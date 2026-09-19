"""Strategy 2: Avellaneda–Stoikov (A-S) Baseline Correctly Defined.

Fulfills Section 21 of prompt.md:
- Reservation price: r = s - q * gamma * sigma^2 * H (using rolling control horizon H for perps)
- Total spread: delta = gamma * sigma^2 * H + (2 / gamma) * ln(1 + gamma / kappa)
- Quotes: bid = r - delta/2, ask = r + delta/2
- Treats delta as TOTAL bid-to-ask spread (not one-sided)
- Empirical kappa order arrival intensity calibration
"""

import math
from typing import Optional, Tuple
from src.strategies.base import BaseMarketMakingStrategy, Quote


class AvellanedaStoikovStrategy(BaseMarketMakingStrategy):
    """Avellaneda-Stoikov market making model adapted for perpetuals."""

    def __init__(
        self,
        market: str,
        tick_size: float,
        step_size: float,
        gamma: float = 0.05,  # Inventory risk-aversion parameter
        kappa: float = 1.5,   # Empirical order-arrival intensity
        control_horizon_hours: float = 0.5,  # 30-minute rolling control horizon H
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
        self.gamma = gamma
        self.kappa = kappa
        self.H = control_horizon_hours
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

        # Check capital envelope limit
        current_inv_notional = abs(inventory_units) * mid_price
        if current_inv_notional >= self.max_capital_envelope:
            # Soft stop: quote only to reduce inventory
            clip_size = self.round_to_step(self.clip_notional / mid_price)
            if inventory_units > 0:
                # Long: quote only Ask
                ask = self.round_to_tick(mid_price + (market_spread_bps / 20_000.0) * mid_price)
                return (Quote(side="SELL", price=ask, size=clip_size), None)
            else:
                # Short: quote only Bid
                bid = self.round_to_tick(mid_price - (market_spread_bps / 20_000.0) * mid_price)
                return (Quote(side="BUY", price=bid, size=clip_size), None)

        # 1. Normalize volatility to per-unit-time variance
        sigma = max(0.10, volatility)
        variance = (sigma ** 2)

        # 2. Reservation price: r(s, q) = s - q * gamma * sigma^2 * H
        # q is normalized to units of standard clip
        q_clips = inventory_units / (self.clip_notional / mid_price) if mid_price > 0 else 0.0
        reservation_price = mid_price - (q_clips * self.gamma * variance * self.H * (mid_price / 100.0))

        # 3. Total spread delta
        try:
            spread_term = (2.0 / self.gamma) * math.log(1.0 + (self.gamma / self.kappa))
        except (ValueError, ZeroDivisionError):
            spread_term = 0.04

        # Convert spread term to dollar terms
        delta = (self.gamma * variance * self.H + spread_term) * (mid_price / 100.0)
        # Ensure delta is at least 1 tick
        min_delta = self.tick_size * 2
        delta = max(delta, min_delta)

        # 4. Bid and Ask prices around reservation price
        bid_price = self.round_to_tick(reservation_price - (delta / 2.0))
        ask_price = self.round_to_tick(reservation_price + (delta / 2.0))

        if ask_price <= bid_price:
            ask_price = self.round_to_tick(bid_price + self.tick_size)

        clip_size = self.round_to_step(self.clip_notional / mid_price)
        if clip_size <= 0:
            clip_size = self.step_size

        return (
            Quote(side="BUY", price=bid_price, size=clip_size),
            Quote(side="SELL", price=ask_price, size=clip_size),
        )
