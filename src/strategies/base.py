from __future__ import annotations

"""Abstract Strategy Base for Arcus Perpetuals Market Making."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any

from src.utils import snap_to_tick, snap_to_step, to_decimal


class Quote:
    """Represents a generated two-sided quote."""

    def __init__(self, side: str, price: float, size: float):
        self.side = side  # "BUY" or "SELL"
        self.price = price
        self.size = size

    def to_dict(self) -> Dict[str, Any]:
        return {"side": self.side, "price": self.price, "size": self.size}


class BaseMarketMakingStrategy(ABC):
    """Base class for market making strategies on Arcus."""

    def __init__(
        self,
        market: str,
        tick_size: float,
        step_size: float,
        min_notional: float = 5.0,
        min_order_size: float = 0.0,
        max_capital_envelope: float = 100.0,
    ):
        self.market = market
        self.tick_size = tick_size
        self.step_size = step_size
        self.min_notional = min_notional
        self.min_order_size = min_order_size
        self.max_capital_envelope = max_capital_envelope

    def round_to_tick(self, price: float) -> float:
        """Snaps price to venue discrete tick boundary using exact Decimal arithmetic."""
        return float(snap_to_tick(price, self.tick_size))

    def round_to_step(self, size: float) -> float:
        """Snaps size to venue discrete step boundary using exact Decimal arithmetic."""
        return float(snap_to_step(size, self.step_size))

    def get_min_executable_clip(self, reference_price: float) -> float:
        """Derives runtime minimum executable clip per Mandate Section 10:

        min_executable_clip = max(minOrderNotional, minOrderSize * reference_price)
        """
        min_by_size = self.min_order_size * reference_price if reference_price > 0 else 0.0
        return max(self.min_notional, min_by_size)

    def calculate_clip_size(self, target_notional: float, reference_price: float) -> float:
        """Calculates order quantity snapped to step size satisfying minimum clip."""
        if reference_price <= 0:
            return 0.0
        min_clip_notional = self.get_min_executable_clip(reference_price)
        eff_notional = max(target_notional, min_clip_notional)
        raw_qty = eff_notional / reference_price
        snapped_qty = self.round_to_step(raw_qty)
        # Ensure snapped quantity does not fall below minOrderNotional due to downward rounding
        if snapped_qty * reference_price < min_clip_notional - 1e-6:
            snapped_qty = float(to_decimal(snapped_qty) + to_decimal(self.step_size))
        return snapped_qty

    @abstractmethod
    def generate_quotes(
        self,
        mid_price: float,
        inventory_units: float,
        volatility: float,
        market_spread_bps: float,
        microprice_dev_bps: float = 0.0,
    ) -> Optional[Tuple[Optional[Quote], Optional[Quote]]]:
        """Generates two-sided (Bid, Ask) quotes given current market state."""
        pass

