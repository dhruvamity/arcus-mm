from __future__ import annotations

"""Market Specifications for Arcus Perpetuals.
Delegates to canonical src/venue.py per Mandate v3 Rule 10.
"""

from typing import Dict, Any
from src.venue import VenueMetadata, get_market_spec as venue_get_market_spec


class _MarketSpecsProxy(dict):
    def __getitem__(self, key: str) -> Dict[str, Any]:
        return VenueMetadata.get_spec(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return VenueMetadata.get_spec(key)
        except (KeyError, FileNotFoundError):
            return default

    def __contains__(self, key: object) -> bool:
        try:
            return key in VenueMetadata.load_all_specs()
        except Exception:
            return False


MARKET_SPECS: Dict[str, Dict[str, Any]] = _MarketSpecsProxy()


def get_market_spec(market: str) -> Dict[str, Any]:
    try:
        return venue_get_market_spec(market)
    except Exception:
        return {"tick_size": 0.001, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.0001}
