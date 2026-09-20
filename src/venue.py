from __future__ import annotations

"""Single Canonical Venue Metadata Loader for Arcus MM.
Fulfills Mandate v3 Rule 10 & WS-D (V-15).

Eliminates divergent hardcoded tables by loading ground-truth market specifications
from recorded REST snapshots (data/raw/*/rest_snapshots/markets_*.json).
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_latest_markets_snapshot(repo_root: Optional[Path] = None) -> Optional[Path]:
    root = repo_root or REPO_ROOT
    snapshots = sorted(root.glob("data/raw/*/rest_snapshots/markets_*.json"))
    if snapshots:
        return snapshots[-1]
    fallback = root / "tests/fixtures/markets_snapshot_sample.json"
    if fallback.exists():
        return fallback
    return None


class VenueMetadata:
    _cached_specs: Optional[Dict[str, Dict[str, Any]]] = None

    @classmethod
    def load_all_specs(cls, snapshot_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
        """Loads canonical market specifications from recorded REST snapshot."""
        if cls._cached_specs is not None and snapshot_path is None:
            return cls._cached_specs

        path = snapshot_path or find_latest_markets_snapshot()
        if not path or not path.exists():
            raise FileNotFoundError("No markets snapshot found in data/raw/*/rest_snapshots/")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_items = data.get("markets") if isinstance(data, dict) else data
        if not isinstance(raw_items, list):
            raw_items = []

        specs: Dict[str, Dict[str, Any]] = {}
        for item in raw_items:
            symbol = item.get("marketDisplayName") or item.get("market") or item.get("name")
            if not symbol:
                continue

            specs[symbol] = {
                "market_id": int(item.get("marketId", 0)),
                "market": symbol,
                "symbol": symbol,
                "base_asset": item.get("baseAsset", ""),
                "quote_asset": item.get("quoteAsset", "USD"),
                "tick_size": float(item.get("tickSize", 0.001)),
                "step_size": float(item.get("stepSize", 0.0001)),
                "min_notional": float(item.get("minOrderNotional", 5.0)),
                "min_order_size": float(item.get("minOrderSize", 0.0)),
                "max_order_size": float(item.get("maxOrderSize", 1_000_000.0)),
                "category": str(item.get("category", "CRYPTO")).upper(),
                "initial_margin_fraction": float(item.get("initialMarginFraction", 0.05)),
                "maintenance_margin_fraction": float(item.get("maintenanceMarginFraction", 0.03)),
                "off_hours_initial_margin_fraction": float(item.get("offHoursInitialMarginFraction", 0.075)),
                "status": item.get("status", "ONLINE"),
            }

        if snapshot_path is None:
            cls._cached_specs = specs
        return specs

    @classmethod
    def get_spec(cls, market: str) -> Dict[str, Any]:
        """Retrieves spec for a specific market symbol."""
        specs = cls.load_all_specs()
        if market not in specs:
            raise KeyError(f"Market '{market}' not found in canonical venue metadata.")
        return specs[market]

    @classmethod
    def reset_cache(cls) -> None:
        cls._cached_specs = None


def get_market_spec(market: str) -> Dict[str, Any]:
    """Convenience accessor matching legacy API."""
    return VenueMetadata.get_spec(market)


def load_market_specs(markets: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Loads specs for given markets, or all if None."""
    all_specs = VenueMetadata.load_all_specs()
    if markets is None:
        return all_specs
    return {m: all_specs[m] for m in markets if m in all_specs}
