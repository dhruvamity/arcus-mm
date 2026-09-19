"""Rejection Handlers for Arcus MM Execution Stack.

Fulfills Mandate Section 10:
Handles venue rejection reasons:
- POST_ONLY_WOULD_CROSS
- UNDERCOLLATERALIZED
- SELF_TRADE
- REDUCE_ONLY_WOULD_INCREASE
- POSITION_LIMIT_EXCEEDED
- TRADING_BOUND_REJECTION
"""

from enum import Enum
from typing import Dict, Any, Optional, Callable


class RejectionReason(str, Enum):
    POST_ONLY_WOULD_CROSS = "POST_ONLY_WOULD_CROSS"
    UNDERCOLLATERALIZED = "UNDERCOLLATERALIZED"
    SELF_TRADE = "SELF_TRADE"
    REDUCE_ONLY_WOULD_INCREASE = "REDUCE_ONLY_WOULD_INCREASE"
    POSITION_LIMIT_EXCEEDED = "POSITION_LIMIT_EXCEEDED"
    TRADING_BOUND_REJECTION = "TRADING_BOUND_REJECTION"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    UNKNOWN_REJECTION = "UNKNOWN_REJECTION"


class RejectionHandler:
    """Manages rejection callbacks, strategy notification, and corrective actions."""

    def __init__(self):
        self.rejection_counts: Dict[RejectionReason, int] = {r: 0 for r in RejectionReason}
        self.rejection_log: list = []
        self._custom_handlers: Dict[RejectionReason, Callable[[Dict[str, Any]], None]] = {}

    def register_handler(self, reason: RejectionReason, handler: Callable[[Dict[str, Any]], None]):
        self._custom_handlers[reason] = handler

    def handle_rejection(self, reason_str: str, order_info: Dict[str, Any]) -> Dict[str, Any]:
        """Parses rejection reason string, updates counters, and executes corrective actions."""
        try:
            reason = RejectionReason(reason_str)
        except ValueError:
            reason = RejectionReason.UNKNOWN_REJECTION

        self.rejection_counts[reason] += 1
        record = {
            "reason": reason,
            "order_id": order_info.get("order_id"),
            "market": order_info.get("market"),
            "side": order_info.get("side"),
            "price": order_info.get("price"),
            "size": order_info.get("size"),
            "details": order_info.get("details", ""),
        }
        self.rejection_log.append(record)

        # Execute custom handler if registered
        if reason in self._custom_handlers:
            self._custom_handlers[reason](order_info)

        # Default corrective recommendations
        action = "LOG_AND_CONTINUE"
        if reason == RejectionReason.POST_ONLY_WOULD_CROSS:
            action = "WIDEN_QUOTE_AND_RETRY"
        elif reason == RejectionReason.UNDERCOLLATERALIZED:
            action = "HALT_QUOTING_AND_CHECK_BALANCE"
        elif reason == RejectionReason.SELF_TRADE:
            action = "CANCEL_OPPOSITE_RESTING_ORDER"
        elif reason == RejectionReason.REDUCE_ONLY_WOULD_INCREASE:
            action = "CLEAR_REDUCE_ONLY_FLAG"
        elif reason == RejectionReason.POSITION_LIMIT_EXCEEDED:
            action = "REDUCE_ONLY_ACTIVE"
        elif reason == RejectionReason.TRADING_BOUND_REJECTION:
            action = "ADJUST_PRICE_TO_VENUE_BOUNDS"

        record["corrective_action"] = action
        return record
