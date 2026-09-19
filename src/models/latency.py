"""Latency Pipeline Model for Arcus Market Making.

Fulfills Section 18 of prompt.md:
- Feed latency (WS market data arrival)
- Decision latency (strategy compute time)
- Send latency (network transit to gateway)
- Exchange ACK latency (matching engine process & confirmation)
- Cancel latency
- Modify latency

Supports testing at baseline, +100ms, +500ms, +1s, +5s.
"""

from typing import Dict, Any


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
    ):
        self.feed_latency_ms = feed_latency_ms
        self.decision_latency_ms = decision_latency_ms
        self.send_latency_ms = send_latency_ms
        self.ack_latency_ms = ack_latency_ms
        self.cancel_latency_ms = cancel_latency_ms
        self.modify_latency_ms = modify_latency_ms
        self.additional_stress_latency_ms = additional_stress_latency_ms

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
