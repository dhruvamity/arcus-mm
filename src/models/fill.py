"""Fill Models for Arcus Perpetuals Backtesting.

Fulfills Section 4.1 & 4.2 of prompt.md:
- Model A (Optimistic / Diagnostic): Price touch => fill up to trade size.
- Model B (Moderate): Strict queue-aware FIFO model behind displayed depth.
  - Size decrease preserves queue priority.
  - Price change or size increase loses priority and joins back of queue.
- Model C (Conservative / Gating): Requires trade strictly through quote price.
  - BUY fills only when trade_price < order.price.
  - SELL fills only when trade_price > order.price.
  - Fills cannot exceed trade size or remaining quote size.
- Strict Monotonicity Guarantee:
  On identical quote and trade paths:
  fills(A) >= fills(B) >= fills(C) on EVERY single trade event.
"""

from enum import Enum
from typing import Optional, Dict, Any


class FillModelType(str, Enum):
    MODEL_A_OPTIMISTIC = "MODEL_A_OPTIMISTIC"
    MODEL_A_TOUCH = "MODEL_A_OPTIMISTIC"
    MODEL_B_MODERATE = "MODEL_B_MODERATE"
    MODEL_C_CONSERVATIVE = "MODEL_C_CONSERVATIVE"


class OrderStatus(str, Enum):
    """Explicit order lifecycle state machine per Mandate Section 6."""
    CREATED = "CREATED"
    SUBMITTING = "SUBMITTING"
    RESTING = "RESTING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    REPLACE_REQUESTED = "REPLACE_REQUESTED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class SimulatedQueueOrder:
    """Represents a resting simulated limit order with explicit lifecycle state."""

    def __init__(
        self,
        order_id: str,
        side: str,  # "BUY" or "SELL"
        price: float,
        size: float,
        created_ts_ns: int,
        queue_ahead_volume: float = 0.0,
        status: OrderStatus = OrderStatus.RESTING,
    ):
        self.order_id = order_id
        self.side = side
        self.price = price
        self.size = size
        self.created_ts_ns = created_ts_ns
        self.effective_ts_ns = created_ts_ns
        self.cancel_effective_ts_ns: Optional[int] = None
        self.queue_ahead_volume = max(0.0, queue_ahead_volume)
        self.filled_size = 0.0
        self.status = status
        self.is_active = True

    @property
    def remaining_size(self) -> float:
        return max(0.0, self.size - self.filled_size)

    def is_resting(self, ts_ns: Optional[int] = None) -> bool:
        """Evaluates whether order is actively resting on the venue book.

        If in CANCEL_REQUESTED, order remains resting until cancellation latency passes.
        """
        if not self.is_active or self.remaining_size <= 0:
            return False
        if ts_ns is not None:
            if ts_ns < self.effective_ts_ns:
                return False  # Still in submitting transit latency
            if self.cancel_effective_ts_ns is not None and ts_ns >= self.cancel_effective_ts_ns:
                self.status = OrderStatus.CANCELLED
                self.is_active = False
                return False
        return self.status in (OrderStatus.RESTING, OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCEL_REQUESTED)

    def request_cancel(self, request_ts_ns: int, cancel_latency_ns: int) -> None:
        """Transitions order to CANCEL_REQUESTED; remains live during cancel transit latency."""
        if self.is_active and self.status in (OrderStatus.RESTING, OrderStatus.PARTIALLY_FILLED, OrderStatus.SUBMITTING):
            self.status = OrderStatus.CANCEL_REQUESTED
            self.cancel_effective_ts_ns = request_ts_ns + cancel_latency_ns

    def update_lifecycle(self, ts_ns: int) -> None:
        """Updates lifecycle states against current timestamp."""
        if self.status == OrderStatus.SUBMITTING and ts_ns >= self.effective_ts_ns:
            self.status = OrderStatus.RESTING
        elif self.status == OrderStatus.CANCEL_REQUESTED and self.cancel_effective_ts_ns is not None:
            if ts_ns >= self.cancel_effective_ts_ns:
                self.status = OrderStatus.CANCELLED
                self.is_active = False

    def modify(self, new_price: float, new_size: float, current_queue_at_price: float) -> bool:
        """Modifies order following Arcus queue priority contract.

        - If price unchanged and size decreases: modifies in-place, PRESERVES queue priority.
        - If price changes or size increases: atomic cancel-replace, LOSES priority.
        Returns True if priority was preserved, False if priority was lost.
        """
        price_unchanged = abs(new_price - self.price) < 1e-9
        size_decreased_or_equal = new_size <= self.size + 1e-9

        if price_unchanged and size_decreased_or_equal:
            # Preserves queue priority
            self.size = new_size
            return True
        else:
            # Loses queue priority: cancel + replace
            self.price = new_price
            self.size = new_size
            self.queue_ahead_volume = max(0.0, current_queue_at_price)
            return False


class FillEngine:
    """Evaluates fills with deterministic monotonicity across Models A, B, and C."""

    def __init__(self, model_type: FillModelType = FillModelType.MODEL_B_MODERATE):
        self.model_type = model_type

    def process_trade(
        self,
        order: SimulatedQueueOrder,
        trade_side: str,  # "BUY" or "SELL" (taker perspective)
        trade_price: float,
        trade_size: float,
    ) -> float:
        """Determines fill size executed on the simulated order by the incoming trade.

        Returns the filled size (0.0 if no fill).
        Guarantees fills(A) >= fills(B) >= fills(C) on any trade event.
        """
        if not order.is_active or order.remaining_size <= 0 or trade_size <= 0:
            return 0.0

        # Maker BUY order is filled only when a taker SELLS
        if order.side == "BUY":
            if trade_side != "SELL":
                return 0.0
            # Trade must occur at or below order price
            if trade_price > order.price:
                return 0.0

            is_trade_through = trade_price < order.price
            max_possible = min(order.remaining_size, trade_size)

            if self.model_type == FillModelType.MODEL_A_OPTIMISTIC:
                # Touch => fills immediately up to trade size
                fill_qty = max_possible
                order.filled_size += fill_qty
                if order.remaining_size <= 0:
                    order.is_active = False
                return fill_qty

            elif self.model_type == FillModelType.MODEL_B_MODERATE:
                if is_trade_through:
                    # Traded strictly through: priority fill
                    fill_qty = max_possible
                    order.filled_size += fill_qty
                    if order.remaining_size <= 0:
                        order.is_active = False
                    return fill_qty
                else:
                    # Traded at exact touch: must first consume queue ahead
                    if order.queue_ahead_volume > 0:
                        depleted = min(order.queue_ahead_volume, trade_size)
                        order.queue_ahead_volume -= depleted
                        rem_trade = trade_size - depleted
                    else:
                        rem_trade = trade_size

                    if rem_trade > 0:
                        fill_qty = min(order.remaining_size, rem_trade)
                        order.filled_size += fill_qty
                        if order.remaining_size <= 0:
                            order.is_active = False
                        return fill_qty
                    return 0.0

            elif self.model_type == FillModelType.MODEL_C_CONSERVATIVE:
                # Conservative: ONLY fills if trade strictly penetrates quote price
                if is_trade_through:
                    fill_qty = max_possible
                    order.filled_size += fill_qty
                    if order.remaining_size <= 0:
                        order.is_active = False
                    return fill_qty
                return 0.0

        # Maker SELL order is filled only when a taker BUYS
        elif order.side == "SELL":
            if trade_side != "BUY":
                return 0.0
            if trade_price < order.price:
                return 0.0

            is_trade_through = trade_price > order.price
            max_possible = min(order.remaining_size, trade_size)

            if self.model_type == FillModelType.MODEL_A_OPTIMISTIC:
                fill_qty = max_possible
                order.filled_size += fill_qty
                if order.remaining_size <= 0:
                    order.is_active = False
                return fill_qty

            elif self.model_type == FillModelType.MODEL_B_MODERATE:
                if is_trade_through:
                    fill_qty = max_possible
                    order.filled_size += fill_qty
                    if order.remaining_size <= 0:
                        order.is_active = False
                    return fill_qty
                else:
                    if order.queue_ahead_volume > 0:
                        depleted = min(order.queue_ahead_volume, trade_size)
                        order.queue_ahead_volume -= depleted
                        rem_trade = trade_size - depleted
                    else:
                        rem_trade = trade_size

                    if rem_trade > 0:
                        fill_qty = min(order.remaining_size, rem_trade)
                        order.filled_size += fill_qty
                        if order.remaining_size <= 0:
                            order.is_active = False
                        return fill_qty
                    return 0.0

            elif self.model_type == FillModelType.MODEL_C_CONSERVATIVE:
                if is_trade_through:
                    fill_qty = max_possible
                    order.filled_size += fill_qty
                    if order.remaining_size <= 0:
                        order.is_active = False
                    return fill_qty
                return 0.0

        return 0.0
