"""Market Specifications and Instrument Parameters for Arcus Perpetuals."""

from typing import Dict, Any

MARKET_SPECS: Dict[str, Dict[str, Any]] = {
    "BTC-USD": {"tick_size": 0.1, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.0001},
    "ETH-USD": {"tick_size": 0.01, "step_size": 0.001, "min_notional": 5.0, "min_order_size": 0.001},
    "SOL-USD": {"tick_size": 0.01, "step_size": 0.01, "min_notional": 5.0, "min_order_size": 0.01},
    "HYPE-USD": {"tick_size": 0.001, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.0001},
    "ZEC-USD": {"tick_size": 0.001, "step_size": 0.00001, "min_notional": 5.0, "min_order_size": 0.00001},
    "NEAR-USD": {"tick_size": 0.001, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.0001},
    "SPCX-USD": {"tick_size": 0.01, "step_size": 0.001, "min_notional": 5.0, "min_order_size": 0.001},
    "LIT-USD": {"tick_size": 0.0001, "step_size": 0.001, "min_notional": 5.0, "min_order_size": 0.001},
    "UNI-USD": {"tick_size": 0.001, "step_size": 0.001, "min_notional": 5.0, "min_order_size": 0.001},
    "SLV-USD": {"tick_size": 0.01, "step_size": 0.001, "min_notional": 5.0, "min_order_size": 0.001},
}


def get_market_spec(market: str) -> Dict[str, Any]:
    """Returns specifications for market or reasonable defaults."""
    if market in MARKET_SPECS:
        return MARKET_SPECS[market].copy()
    return {"tick_size": 0.001, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.0001}
