from __future__ import annotations

"""Local L2 Order Book reconstructor and sequence validator.

Implements exact Arcus L2 sequence rules:
- Establishes baseline from initial snapshot (lastSequenceId).
- Accommodates expected initial boundary gap (snapshot lags delta stream).
- Detects mid-stream sequence gaps and triggers resynchronization.
- Applies repeated-price updates within frames in frame order.
- Computes microprice, spread, and book imbalance.
"""

from typing import Dict, Tuple, Optional, Any
from decimal import Decimal
import logging
from src.utils import to_decimal

logger = logging.getLogger(__name__)


class OrderBookLevel:
    """Represents a price level in the order book."""
    __slots__ = ("price", "size")

    def __init__(self, price: Decimal, size: Decimal):
        self.price = price
        self.size = size


class LocalOrderBook:
    """Maintains a local reconstructed L2 order book for a single market."""

    def __init__(self, market: str):
        self.market = market
        self.bids: Dict[Decimal, Decimal] = {}  # price -> size
        self.asks: Dict[Decimal, Decimal] = {}  # price -> size
        self.last_sequence_id: Optional[int] = None
        self.global_sequence_id: Optional[int] = None
        self.is_synced: bool = False
        self.has_received_first_delta: bool = False
        self.sequence_gap_detected: bool = False

    def reset(self) -> None:
        """Resets the book state."""
        self.bids.clear()
        self.asks.clear()
        self.last_sequence_id = None
        self.global_sequence_id = None
        self.is_synced = False
        self.has_received_first_delta = False
        self.sequence_gap_detected = False

    def apply_snapshot(self, snapshot_data: Dict[str, Any]) -> None:
        """Applies an L2 snapshot and initializes book state."""
        self.reset()

        raw_bids = snapshot_data.get("bids", [])
        raw_asks = snapshot_data.get("asks", [])

        for item in raw_bids:
            p, s = self._parse_level(item)
            if s > 0:
                self.bids[p] = s

        for item in raw_asks:
            p, s = self._parse_level(item)
            if s > 0:
                self.asks[p] = s

        self.last_sequence_id = snapshot_data.get("lastSequenceId")
        self.global_sequence_id = snapshot_data.get("globalSequenceId")
        self.is_synced = True
        self.has_received_first_delta = False
        self.sequence_gap_detected = False

    def apply_delta(self, delta_data: Dict[str, Any]) -> bool:
        """Applies an incremental L2 delta update.

        Returns True if update was applied, False if rejected or gap detected.
        """
        if not self.is_synced:
            logger.warning(f"[{self.market}] Delta received while orderbook is not synchronized")
            return False

        seq = delta_data.get("lastSequenceId")
        if seq is None:
            return False

        # Sequence gap check
        if self.last_sequence_id is not None:
            if not self.has_received_first_delta:
                # Initial post-snapshot delta boundary check:
                # Arcus snapshot is periodic and lags live head, so first delta
                # might be ahead of snapshot.lastSequenceId.
                if seq <= self.last_sequence_id:
                    # Stale update from before snapshot; skip
                    return False
                self.has_received_first_delta = True
            else:
                # Mid-stream check: contiguous sequence expected
                if seq <= self.last_sequence_id:
                    # Duplicate or out of order
                    return False
                if seq > self.last_sequence_id + 1:
                    logger.error(
                        f"[{self.market}] Mid-stream sequence gap: expected {self.last_sequence_id + 1}, got {seq}"
                    )
                    self.sequence_gap_detected = True
                    self.is_synced = False
                    return False

        self.last_sequence_id = seq
        self.global_sequence_id = delta_data.get("globalSequenceId", self.global_sequence_id)

        # Apply bids in frame order
        for item in delta_data.get("bids", []):
            p, s = self._parse_level(item)
            if s <= 0:
                self.bids.pop(p, None)
            else:
                self.bids[p] = s

        # Apply asks in frame order
        for item in delta_data.get("asks", []):
            p, s = self._parse_level(item)
            if s <= 0:
                self.asks.pop(p, None)
            else:
                self.asks[p] = s

        return True

    def _parse_level(self, item: Any) -> Tuple[Decimal, Decimal]:
        """Parses [price, size] tuple or dict into (Decimal, Decimal)."""
        if isinstance(item, (list, tuple)):
            return to_decimal(item[0]), to_decimal(item[1])
        elif isinstance(item, dict):
            return to_decimal(item["price"]), to_decimal(item["size"])
        raise ValueError(f"Unknown level format: {item}")

    def get_cumulative_bid_depth(self, price: Decimal) -> float:
        """Returns cumulative volume of all resting bids at or strictly above price."""
        vol = Decimal(0)
        for p, s in self.bids.items():
            if p >= price:
                vol += s
        return float(vol)

    def get_cumulative_ask_depth(self, price: Decimal) -> float:
        """Returns cumulative volume of all resting asks at or strictly below price."""
        vol = Decimal(0)
        for p, s in self.asks.items():
            if p <= price:
                vol += s
        return float(vol)

    def best_bid(self) -> Optional[Tuple[Decimal, Decimal]]:
        """Returns (price, size) for the best bid, or None if book is empty."""
        if not self.bids:
            return None
        p = max(self.bids.keys())
        return p, self.bids[p]

    def best_ask(self) -> Optional[Tuple[Decimal, Decimal]]:
        """Returns (price, size) for the best ask, or None if book is empty."""
        if not self.asks:
            return None
        p = min(self.asks.keys())
        return p, self.asks[p]

    def mid(self) -> Optional[Decimal]:
        """Returns mid price = (best_bid + best_ask) / 2."""
        bb = self.best_bid()
        ba = self.best_ask()
        if bb and ba:
            return (bb[0] + ba[0]) / Decimal("2")
        return None

    def spread(self) -> Optional[Decimal]:
        """Returns spread = best_ask - best_bid."""
        bb = self.best_bid()
        ba = self.best_ask()
        if bb and ba:
            return ba[0] - bb[0]
        return None

    def microprice(self) -> Optional[Decimal]:
        """Returns top-of-book size-weighted microprice:

        (bid_price * ask_size + ask_price * bid_size) / (bid_size + ask_size)
        """
        bb = self.best_bid()
        ba = self.best_ask()
        if bb and ba:
            bid_p, bid_s = bb
            ask_p, ask_s = ba
            total_size = bid_s + ask_s
            if total_size > 0:
                return (bid_p * ask_s + ask_p * bid_s) / total_size
        return None

    def imbalance(self) -> Optional[Decimal]:
        """Returns top-of-book order imbalance:

        (bid_size - ask_size) / (bid_size + ask_size)
        """
        bb = self.best_bid()
        ba = self.best_ask()
        if bb and ba:
            bid_s = bb[1]
            ask_s = ba[1]
            total_size = bid_s + ask_s
            if total_size > 0:
                return (bid_s - ask_s) / total_size
        return None

    def depth_within_bps(self, bps: float) -> Tuple[Decimal, Decimal]:
        """Computes cumulative bid and ask notional within bps of mid."""
        m = self.mid()
        if not m:
            return Decimal("0"), Decimal("0")

        ratio = Decimal(str(bps)) / Decimal("10000")
        min_bid = m * (Decimal("1") - ratio)
        max_ask = m * (Decimal("1") + ratio)

        bid_depth = sum((p * s for p, s in self.bids.items() if p >= min_bid), Decimal("0"))
        ask_depth = sum((p * s for p, s in self.asks.items() if p <= max_ask), Decimal("0"))
        return bid_depth, ask_depth
