"""Client-side rate limit tracking for Arcus.

Accurately models Arcus's two distinct throttling layers:
1. Per-IP token bucket (1,500 weight capacity, 25 weight/second continuous refill).
2. Per-subaccount trading pools (20,000 order pool, 40,000 cancel pool, fill-based replenishment, and 1 action / 10s drip).
"""

import time
import asyncio
from typing import Dict, Any, Optional
from src.models import SubaccountPoolStatus, RateLimitSnapshot


class RateLimiter:
    """Manages IP weight tokens and subaccount trading pools."""

    # Endpoint base weights according to Arcus docs
    ENDPOINT_WEIGHTS: Dict[str, int] = {
        # Weight 0
        "health": 0,
        "placeOrder": 0,
        "cancelOrder": 0,
        "modifyOrder": 0,
        "cancelAllOrders": 0,
        # Weight 1
        "time": 1,
        "compliance": 1,
        # Weight 2
        "bbo": 2,
        "mids": 2,
        "account": 2,
        "positions": 2,
        "order": 2,
        "feeTiers": 2,
        "leverages": 2,
        "accountStats": 2,
        "rateLimit": 2,
        # Weight 20
        "prices": 20,
        "markets": 20,
        "trades": 20,
        "candles": 20,
        "portfolio": 20,
        "openOrders": 20,
        "orders": 20,
        "fills": 20,
        "funding": 20,
        "fundingRates": 20,
        "apiKeys": 20,
        "createApiKey": 20,
        # Weight 125
        "setLeverage": 125,
        "withdraw": 125,
        "transfer": 125,
    }

    def __init__(
        self,
        ip_capacity: float = 1500.0,
        ip_refill_per_sec: float = 25.0,
        starting_order_cap: int = 20000,
        starting_cancel_cap: int = 40000,
    ):
        self.ip_capacity = ip_capacity
        self.ip_refill_per_sec = ip_refill_per_sec
        self.ip_tokens = ip_capacity
        self.last_refill_time = time.monotonic()
        self._lock = asyncio.Lock()

        # Subaccount pool defaults
        self.order_pool = SubaccountPoolStatus(
            used=0, cap=starting_order_cap, nextAvailableMs=0
        )
        self.cancel_pool = SubaccountPoolStatus(
            used=0, cap=starting_cancel_cap, nextAvailableMs=0
        )

    def _refill_ip_tokens(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill_time
        self.last_refill_time = now
        self.ip_tokens = min(self.ip_capacity, self.ip_tokens + elapsed * self.ip_refill_per_sec)

    async def acquire_ip_weight(self, weight: int, timeout: float = 10.0) -> bool:
        """Acquires IP weight tokens, awaiting refill if necessary."""
        if weight <= 0:
            return True

        deadline = time.monotonic() + timeout
        while True:
            async with self._lock:
                self._refill_ip_tokens()
                if self.ip_tokens >= weight:
                    self.ip_tokens -= weight
                    return True
                deficit = weight - self.ip_tokens
                wait_time = deficit / self.ip_refill_per_sec

            if time.monotonic() + wait_time > deadline:
                return False

            await asyncio.sleep(min(wait_time, 0.5))

    def update_from_venue_response(self, data: Dict[str, Any]) -> None:
        """Updates internal subaccount pool state from /v1/rateLimit JSON."""
        if "order" in data:
            self.order_pool = SubaccountPoolStatus(
                used=data["order"].get("used", self.order_pool.used),
                cap=data["order"].get("cap", self.order_pool.cap),
                nextAvailableMs=data["order"].get("nextAvailableMs", 0),
            )
        if "cancel" in data:
            self.cancel_pool = SubaccountPoolStatus(
                used=data["cancel"].get("used", self.cancel_pool.used),
                cap=data["cancel"].get("cap", self.cancel_pool.cap),
                nextAvailableMs=data["cancel"].get("nextAvailableMs", 0),
            )

    def record_fill(self, fill_notional_usd: float) -> None:
        """Replenishes pool headroom by +1 unit per $0.10 traded."""
        replenishment = int(fill_notional_usd / 0.10)
        self.order_pool.cap += replenishment
        self.cancel_pool.cap += replenishment

    def get_pool_status(self) -> Dict[str, Any]:
        """Returns dictionary representation of current pool capacities and usage."""
        orders_avail = max(0, self.order_pool.cap - self.order_pool.used)
        cancels_avail = max(0, self.cancel_pool.cap - self.cancel_pool.used)
        return {
            "order_units_available": float(orders_avail),
            "cancel_units_available": float(cancels_avail),
            "order_pool_cap": self.order_pool.cap,
            "cancel_pool_cap": self.cancel_pool.cap,
            "orders_used": self.order_pool.used,
            "cancels_used": self.cancel_pool.used,
            "total_actions_used": self.order_pool.used + self.cancel_pool.used,
        }

    def get_snapshot(self, address: str = "", account_index: int = 0) -> RateLimitSnapshot:
        """Returns snapshot of current limiter state."""
        self._refill_ip_tokens()
        return RateLimitSnapshot(
            address=address,
            accountIndex=account_index,
            orderPool=self.order_pool,
            cancelPool=self.cancel_pool,
            ipWeightRemaining=self.ip_tokens,
        )
