"""Data models and enums for Arcus perpetuals."""

from enum import Enum, IntEnum
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class OrderSide(str, Enum):
    """Order side: BUY or SELL."""
    BUY = "BUY"
    SELL = "SELL"

    @property
    def int_code(self) -> int:
        return 0 if self == OrderSide.BUY else 1


class OrderType(str, Enum):
    """Order type: LIMIT or MARKET."""
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class TimeInForce(str, Enum):
    """Order Time In Force."""
    GTT = "GTT"   # Good Til Time (rests until filled or expiry)
    FOK = "FOK"   # Fill Or Kill (fills completely or cancels entirely)
    IOC = "IOC"   # Immediate Or Cancel (fills immediately, cancels remainder)
    ALO = "ALO"   # Add Liquidity Only (Post-Only; rejected if it would take)

    @property
    def int_code(self) -> int:
        mapping = {"GTT": 0, "FOK": 1, "IOC": 2, "ALO": 3}
        return mapping[self.value]


class Operation(IntEnum):
    """Operation code for Arcus signed payloads."""
    PLACE = 1
    CANCEL = 2
    MODIFY = 3
    TPSL = 4


class MarketMetadata(BaseModel):
    """Arcus market specification and parameters."""
    marketId: int
    marketDisplayName: str
    fullAssetName: Optional[str] = None
    status: str = "ONLINE"
    baseAsset: str
    quoteAsset: str
    tickSize: str
    stepSize: str
    oraclePrice: Optional[str] = None
    makerFee: Optional[str] = None
    takerFee: Optional[str] = None
    minOrderSize: Optional[str] = None
    minOrderNotional: Optional[str] = None
    fundingRate: Optional[str] = None
    openInterest: Optional[str] = None
    tickTiers: Optional[List[Dict[str, Any]]] = None

    @property
    def tick_decimal(self) -> Decimal:
        return Decimal(self.tickSize)

    @property
    def step_decimal(self) -> Decimal:
        return Decimal(self.stepSize)


class BBO(BaseModel):
    """Best Bid and Offer representation."""
    market: str
    marketId: Optional[int] = None
    bidPrice: Optional[Decimal] = None
    bidSize: Optional[Decimal] = None
    askPrice: Optional[Decimal] = None
    askSize: Optional[Decimal] = None
    lastSequenceId: Optional[int] = None
    timestamp: Optional[int] = None

    @property
    def spread(self) -> Optional[Decimal]:
        if self.bidPrice is not None and self.askPrice is not None:
            return self.askPrice - self.bidPrice
        return None

    @property
    def mid(self) -> Optional[Decimal]:
        if self.bidPrice is not None and self.askPrice is not None:
            return (self.askPrice + self.bidPrice) / Decimal("2")
        return None


class OrderRequest(BaseModel):
    """High-level order placement parameter model."""
    marketId: int
    side: OrderSide
    price: Decimal
    quantity: Decimal
    timeInForce: TimeInForce = TimeInForce.ALO
    orderType: OrderType = OrderType.LIMIT
    goodTilTimeMicros: Optional[int] = None
    reduceOnly: bool = False
    clientId: Optional[str] = None


class OrderResponse(BaseModel):
    """Response returned after order submission."""
    orderId: Optional[str] = None
    clientId: Optional[str] = None
    status: str
    accountIndex: Optional[int] = None
    marketId: Optional[int] = None
    rateLimit: Optional[Dict[str, Any]] = None
    raw: Optional[Dict[str, Any]] = None


class SubaccountPoolStatus(BaseModel):
    """Per-subaccount rate limit pool status."""
    used: int
    cap: int
    nextAvailableMs: int

    @property
    def remaining(self) -> int:
        return max(0, self.cap - self.used)


class RateLimitSnapshot(BaseModel):
    """Full rate-limit report for an account and IP."""
    address: str
    accountIndex: int
    orderPool: SubaccountPoolStatus
    cancelPool: SubaccountPoolStatus
    ipWeightRemaining: float = 1500.0
