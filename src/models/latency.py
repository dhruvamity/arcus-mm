from __future__ import annotations

"""Latency Pipeline Model for Arcus Market Making.

- Feed latency (WS market data arrival)
- Decision latency (strategy compute time)
- Send latency (network transit to gateway)
- Exchange ACK latency (matching engine process & confirmation)
- Cancel latency
- Modify latency

Supports testing at baseline, +100ms, +500ms, +1s, +5s.
"""

from typing import Dict, Any, Optional


class LatencyConfig:
    """Latency parameters in milliseconds."""

    def __init__(
        self,
        feed_latency_ms: float = 20.0,
        decision_latency_ms: float = 5.0,
        send_latency_ms: float = 25.0,
        ack_latency_ms: float = 10.0,
        cancel_latency_ms: float = 25.0,
        modify_latency_ms: float = 30.0,
        additional_stress_latency_ms: float = 0.0,
        order_entry_latency_ms: Optional[float] = None,
        **kwargs: Any,
    ):
        if order_entry_latency_ms is not None:
            self.send_latency_ms = float(order_entry_latency_ms)
            self.feed_latency_ms = 0.0
            self.decision_latency_ms = 0.0
            self.ack_latency_ms = 0.0
        else:
            self.send_latency_ms = float(send_latency_ms)
            self.feed_latency_ms = float(feed_latency_ms)
            self.decision_latency_ms = float(decision_latency_ms)
            self.ack_latency_ms = float(ack_latency_ms)
        self.cancel_latency_ms = float(cancel_latency_ms)
        self.modify_latency_ms = float(modify_latency_ms)
        self.additional_stress_latency_ms = float(additional_stress_latency_ms)

    @property
    def order_entry_latency_ms(self) -> float:
        return self.total_place_latency_ms

    @property
    def total_place_latency_ms(self) -> float:
        return (
            self.feed_latency_ms
            + self.decision_latency_ms
            + self.send_latency_ms
            + self.ack_latency_ms
            + self.additional_stress_latency_ms
        )

    @property
    def total_cancel_latency_ms(self) -> float:
        return (
            self.feed_latency_ms
            + self.decision_latency_ms
            + self.cancel_latency_ms
            + self.ack_latency_ms
            + self.additional_stress_latency_ms
        )

    @property
    def total_modify_latency_ms(self) -> float:
        return (
            self.feed_latency_ms
            + self.decision_latency_ms
            + self.modify_latency_ms
            + self.ack_latency_ms
            + self.additional_stress_latency_ms
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feed_latency_ms": self.feed_latency_ms,
            "decision_latency_ms": self.decision_latency_ms,
            "send_latency_ms": self.send_latency_ms,
            "ack_latency_ms": self.ack_latency_ms,
            "cancel_latency_ms": self.cancel_latency_ms,
            "modify_latency_ms": self.modify_latency_ms,
            "additional_stress_latency_ms": self.additional_stress_latency_ms,
            "total_place_latency_ms": self.total_place_latency_ms,
            "total_cancel_latency_ms": self.total_cancel_latency_ms,
        }
