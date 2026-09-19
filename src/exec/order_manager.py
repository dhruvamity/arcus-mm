"""Order Manager and Rate-Limit Pool Accounting for Arcus MM Execution Stack.

Fulfills Mandate Section 10:
- Place / modify / cancel / cancelAll order management
- Rate-limit pools per venue docs:
  - place: 1 order unit
  - modify: 1 order unit
  - cancel: 1 cancel unit
  - cancelAll: 1,000 cancel units
  - +1 unit per $0.10 filled notional (both pools)
  - 1 action / 10s drip at zero
- Isolated-margin setup per market
- Rejection handling integration
"""

import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any
from src.exec.rejection_handlers import RejectionHandler, RejectionReason


class OrderStatus(str, Enum):
    PENDING_PLACE = "PENDING_PLACE"
    RESTING = "RESTING"
    PENDING_MODIFY = "PENDING_MODIFY"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELLED = "CANCELLED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"


class ExecutionOrder:
    def __init__(
        self,
        order_id: str,
        market: str,
        side: str,
        price: float,
        size: float,
        post_only: bool = True,
        reduce_only: bool = False,
    ):
        self.order_id = order_id
        self.client_order_id = f"arcus-{uuid.uuid4().hex[:12]}"
        self.market = market
        self.side = side.lower()
        self.price = price
        self.size = size
        self.filled_size = 0.0
        self.post_only = post_only
        self.reduce_only = reduce_only
        self.status = OrderStatus.PENDING_PLACE
        self.created_ts = time.time()
        self.updated_ts = self.created_ts

    @property
    def remaining_size(self) -> float:
        return max(0.0, self.size - self.filled_size)


class TestnetOrderManager:
    """Manages testnet active orders, rate limit pools, and isolated margin settings."""

    def __init__(
        self,
        initial_order_pool: int = 100,
        initial_cancel_pool: int = 100,
        max_pool_capacity: int = 500,
    ):
        self.order_pool = initial_order_pool
        self.cancel_pool = initial_cancel_pool
        self.max_pool_capacity = max_pool_capacity
        self.last_drip_ts = time.time()

        self.orders: Dict[str, ExecutionOrder] = {}
        self.isolated_margin: Dict[str, Dict[str, Any]] = {}
        self.rejection_handler = RejectionHandler()

        # Pool metrics tracking
        self.min_order_pool_seen = initial_order_pool
        self.min_cancel_pool_seen = initial_cancel_pool

    def update_drip(self, now: Optional[float] = None):
        """Replenishes 1 action per 10s if pool is depleted."""
        if now is None:
            now = time.time()
        elapsed = now - self.last_drip_ts
        if elapsed >= 10.0:
            drip_units = int(elapsed // 10.0)
            self.order_pool = min(self.max_pool_capacity, self.order_pool + drip_units)
            self.cancel_pool = min(self.max_pool_capacity, self.cancel_pool + drip_units)
            self.last_drip_ts = now

    def configure_isolated_margin(self, market: str, leverage: float, collateral: float):
        """Sets up isolated margin parameters for a specific market."""
        self.isolated_margin[market] = {
            "leverage": leverage,
            "collateral": collateral,
            "configured_ts": time.time(),
        }

    def place_order(
        self,
        market: str,
        side: str,
        price: float,
        size: float,
        post_only: bool = True,
        reduce_only: bool = False,
    ) -> Optional[ExecutionOrder]:
        """Places an order, charging 1 order pool unit."""
        self.update_drip()
        if self.order_pool < 1:
            self.rejection_handler.handle_rejection(
                RejectionReason.RATE_LIMIT_EXCEEDED.value,
                {"market": market, "side": side, "price": price, "size": size, "details": "Order pool exhausted"},
            )
            return None

        self.order_pool -= 1
        self.min_order_pool_seen = min(self.min_order_pool_seen, self.order_pool)

        order_id = f"ord-{uuid.uuid4().hex[:10]}"
        order = ExecutionOrder(
            order_id=order_id,
            market=market,
            side=side,
            price=price,
            size=size,
            post_only=post_only,
            reduce_only=reduce_only,
        )
        self.orders[order_id] = order
        order.status = OrderStatus.RESTING
        return order

    def modify_order(self, order_id: str, new_price: float, new_size: float) -> bool:
        """Modifies order price/size, charging 1 order pool unit (venue verified docs)."""
        self.update_drip()
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        if order.status != OrderStatus.RESTING:
            return False

        if self.order_pool < 1:
            self.rejection_handler.handle_rejection(
                RejectionReason.RATE_LIMIT_EXCEEDED.value,
                {"order_id": order_id, "market": order.market, "details": "Order pool exhausted for modify"},
            )
            return False

        self.order_pool -= 1
        self.min_order_pool_seen = min(self.min_order_pool_seen, self.order_pool)

        order.price = new_price
        order.size = new_size
        order.updated_ts = time.time()
        return True

    def cancel_order(self, order_id: str) -> bool:
        """Cancels order, charging 1 cancel pool unit."""
        self.update_drip()
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        if order.status not in {OrderStatus.RESTING, OrderStatus.PENDING_PLACE}:
            return False

        if self.cancel_pool < 1:
            self.rejection_handler.handle_rejection(
                RejectionReason.RATE_LIMIT_EXCEEDED.value,
                {"order_id": order_id, "market": order.market, "details": "Cancel pool exhausted"},
            )
            return False

        self.cancel_pool -= 1
        self.min_cancel_pool_seen = min(self.min_cancel_pool_seen, self.cancel_pool)

        order.status = OrderStatus.CANCELLED
        order.updated_ts = time.time()
        return True

    def cancel_all_orders(self, market: Optional[str] = None) -> int:
        """Cancels all resting orders, charging 1,000 cancel pool units (per venue docs)."""
        self.update_drip()
        if self.cancel_pool < 1000:
            # Venue charges 1000 cancel units for cancelAll
            self.rejection_handler.handle_rejection(
                RejectionReason.RATE_LIMIT_EXCEEDED.value,
                {"market": market or "ALL", "details": "Insufficient cancel pool for cancelAll (needs 1000)"},
            )
            return 0

        self.cancel_pool -= 1000
        self.min_cancel_pool_seen = min(self.min_cancel_pool_seen, self.cancel_pool)

        cancelled_count = 0
        now = time.time()
        for order in self.orders.values():
            if market is not None and order.market != market:
                continue
            if order.status == OrderStatus.RESTING:
                order.status = OrderStatus.CANCELLED
                order.updated_ts = now
                cancelled_count += 1

        return cancelled_count

    def record_fill(self, order_id: str, fill_size: float, fill_price: float) -> bool:
        """Records fill and replenishes rate-limit pools (+1 unit per $0.10 filled notional)."""
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]
        order.filled_size += fill_size
        order.updated_ts = time.time()

        if order.remaining_size <= 1e-9:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        # Rate limit replenishment: +1 unit per $0.10 filled notional to both pools
        filled_notional = fill_size * fill_price
        units_earned = int(filled_notional / 0.10)
        if units_earned > 0:
            self.order_pool = min(self.max_pool_capacity, self.order_pool + units_earned)
            self.cancel_pool = min(self.max_pool_capacity, self.cancel_pool + units_earned)

        return True

    def get_pool_status(self) -> Dict[str, Any]:
        return {
            "order_pool": self.order_pool,
            "cancel_pool": self.cancel_pool,
            "min_order_pool_seen": self.min_order_pool_seen,
            "min_cancel_pool_seen": self.min_cancel_pool_seen,
            "active_orders_count": sum(1 for o in self.orders.values() if o.status == OrderStatus.RESTING),
        }
