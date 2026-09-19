"""Abstract Strategy Base for Arcus Perpetuals Market Making."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any


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
        max_capital_envelope: float = 100.0,
    ):
        self.market = market
        self.tick_size = tick_size
        self.step_size = step_size
        self.min_notional = min_notional
        self.max_capital_envelope = max_capital_envelope

    def round_to_tick(self, price: float) -> float:
        """Rounds price to venue discrete tick."""
        ticks = round(price / self.tick_size)
        return round(ticks * self.tick_size, 6)

    def round_to_step(self, size: float) -> float:
        """Rounds size to venue discrete step."""
        steps = round(size / self.step_size)
        return round(steps * self.step_size, 6)

    @abstractmethod
    def generate_quotes(
        self,
        mid_price: float,
        inventory_units: float,
        volatility: float,
        market_spread_bps: float,
        microprice_dev_bps: float = 0.0,
    ) -> Optional[Tuple[Quote, Quote]]:
        """Generates two-sided (Bid, Ask) quotes given current market state."""
        pass
