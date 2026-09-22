from __future__ import annotations

"""Asynchronous REST Client for Arcus Perpetuals."""

import logging
import os
from typing import Dict, Any, Optional, List
from decimal import Decimal
import httpx

from src.config import ArcusConfig, settings
from src.auth import ArcusSigner
from src.rate_limiter import RateLimiter
from src.utils import (
    to_ticks,
    to_quantums,
    good_til_time_micros,
    now_ns,
)
from src.models import (
    MarketMetadata,
    BBO,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderType,
    TimeInForce,
)

logger = logging.getLogger(__name__)


class ArcusRestClient:
    """Async REST Client providing public and authenticated access to Arcus."""

    def __init__(
        self,
        config: Optional[ArcusConfig] = None,
        signer: Optional[ArcusSigner] = None,
    ):
        self.config = config or settings
        self.base_url = self.config.rest_url.rstrip("/")

        # Initialize signer if private key is available
        if signer:
            self.signer: Optional[ArcusSigner] = signer
        elif self.config.api_private_key and self.config.api_private_key != "0" * 64:
            self.signer = ArcusSigner(self.config.api_private_key)
        else:
            self.signer = None

        self.rate_limiter = RateLimiter()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "ArcusRestClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.config.request_timeout_secs,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.config.request_timeout_secs,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Closes the underlying httpx client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # --------------------------------------------------------------------------
    # Request Execution & Rate Limit Handling
    # --------------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        endpoint_key: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Dispatches an HTTP request respecting rate limits and handling 429 retries."""
        weight = self.rate_limiter.ENDPOINT_WEIGHTS.get(endpoint_key, 20)
        acquired = await self.rate_limiter.acquire_ip_weight(weight)
        if not acquired:
            raise RuntimeError(f"Rate limit timeout acquiring {weight} IP weight for {path}")

        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)

        response = await self.client.request(
            method=method,
            url=path,
            params=params,
            json=json_body,
            headers=req_headers,
        )

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "1")
            body = response.json() if response.text else {}
            reason = body.get("reason", "ip")
            retry_ms = body.get("retryAfterMs", int(retry_after) * 1000)
            logger.warning(
                f"Rate limited by {reason} on {path}. Retry after {retry_ms} ms."
            )
            raise RuntimeError(f"Rate limited (429) on {path}: {body}")

        if response.status_code >= 400:
            error_text = response.text
            logger.error(f"HTTP {response.status_code} error from {path}: {error_text}")
            raise RuntimeError(f"HTTP {response.status_code} on {path}: {error_text}")

        return response.json() if response.text else {}

    # --------------------------------------------------------------------------
    # Public Market Data Endpoints
    # --------------------------------------------------------------------------

    async def get_health(self) -> Dict[str, Any]:
        """Health check endpoint (weight 0)."""
        return await self._request("GET", "/health", "health")

    async def get_server_time(self) -> int:
        """Gets exchange current server time."""
        res = await self._request("GET", "/v1/time", "time")
        return res.get("serverTime", now_ns())

    async def get_markets(self) -> List[MarketMetadata]:
        """Fetches all perpetual markets and parameters."""
        res = await self._request("GET", "/v1/markets", "markets")
        raw_markets = res.get("markets", [])
        return [MarketMetadata(**m) for m in raw_markets]

    async def get_bbo(self, market: str) -> BBO:
        """Fetches BBO for a specific market (e.g. 'BTC-USD')."""
        path = f"/v1/bbo/{market}"
        res = await self._request("GET", path, "bbo")
        best_bid = res.get("bestBid") or {}
        best_ask = res.get("bestAsk") or {}
        return BBO(
            market=market,
            bidPrice=Decimal(best_bid["price"]) if best_bid.get("price") else None,
            bidSize=Decimal(best_bid["size"]) if best_bid.get("size") else None,
            askPrice=Decimal(best_ask["price"]) if best_ask.get("price") else None,
            askSize=Decimal(best_ask["size"]) if best_ask.get("size") else None,
            lastSequenceId=res.get("lastSequenceId"),
            timestamp=res.get("timestamp"),
        )

    async def get_l2_orderbook(
        self,
        market: str,
        n_levels: int = 20,
    ) -> Dict[str, Any]:
        """Fetches L2 order book snapshot."""
        return await self._request(
            "GET",
            f"/v1/l2OrderBook/{market}",
            "order",
            params={"nLevels": n_levels},
        )

    async def get_trades(
        self,
        market: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetches recent public trades for a market."""
        params = {"market": market, "limit": limit}
        res = await self._request("GET", "/v1/trades", "trades", params=params)
        return res.get("trades", [])

    async def get_candles(
        self,
        market: str,
        timeframe: str = "1m",
        to_us: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetches historical OHLCV candles."""
        import time
        target_to = to_us if to_us is not None else int(time.time() * 1e6)
        params = {"market": market, "timeframe": timeframe, "to": target_to, "limit": limit}
        res = await self._request("GET", "/v1/candles", "candles", params=params)
        return res.get("candles", [])

    async def get_funding_rates(self, market: str) -> List[Dict[str, Any]]:
        """Fetches historical funding rates for a market."""
        params = {"market": market}
        res = await self._request("GET", "/v1/fundingRates", "fundingRates", params=params)
        return res.get("fundingRates", [])

    async def get_fee_tiers(self) -> List[Dict[str, Any]]:
        """Fetches venue fee tier table."""
        res = await self._request("GET", "/v1/feeTiers", "feeTiers")
        return res.get("feeTiers", [])

    # --------------------------------------------------------------------------
    # Authenticated Read Endpoints
    # --------------------------------------------------------------------------

    async def get_account(self, address: Optional[str] = None) -> Dict[str, Any]:
        """Fetches account balance, equity, and free collateral."""
        addr = (address or self.config.wallet_address).lower()
        params = {"address": addr}
        headers = {"X-API-Key": self.signer.api_key} if self.signer else {}
        return await self._request("GET", "/v1/account", "account", params=params, headers=headers)

    async def get_positions(self, address: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetches open perpetual positions for an address."""
        addr = (address or self.config.wallet_address).lower()
        params = {"address": addr}
        res = await self._request("GET", "/v1/positions", "positions", params=params)
        return res.get("positions", [])

    async def get_open_orders(
        self,
        address: Optional[str] = None,
        market_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches resting open orders for an address."""
        addr = (address or self.config.wallet_address).lower()
        params: Dict[str, Any] = {"address": addr}
        if market_id is not None:
            params["marketId"] = market_id
        res = await self._request("GET", "/v1/openOrders", "openOrders", params=params)
        return res.get("orders", [])

    async def get_rate_limit(
        self,
        address: Optional[str] = None,
        account_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Fetches live snapshot of per-subaccount order and cancel pools."""
        addr = (address or self.config.wallet_address).lower()
        idx = account_index if account_index is not None else self.config.account_index
        params = {"address": addr, "accountIndex": idx}
        res = await self._request("GET", "/v1/rateLimit", "rateLimit", params=params)
        self.rate_limiter.update_from_venue_response(res)
        return res

    # --------------------------------------------------------------------------
    # Authenticated Trading Endpoints (Scheme 1 & Scheme 2)
    # --------------------------------------------------------------------------

    def _assert_trading_allowed(self) -> None:
        """Enforces hard trading safety rules with two-key mainnet guard (Mandate v5 §5.3)."""
        if self.config.environment == "mainnet":
            confirmation_token = os.environ.get("ARCUS_MAINNET_MUTATING_CONFIRMATION", "")
            if self.config.mainnet_order_lock or confirmation_token != "I_ACCEPT_PERMANENT_LOSS_OF_FUNDS":
                raise PermissionError(
                    "SUBMITTING ORDERS ON MAINNET IS HARD-BLOCKED by two-key safety guard! "
                    "Requires both mainnet_order_lock=False and ARCUS_MAINNET_MUTATING_CONFIRMATION='I_ACCEPT_PERMANENT_LOSS_OF_FUNDS'."
                )
        if not self.signer:
            raise ValueError("Signer not configured with a valid private key")

    async def place_order(
        self,
        order: OrderRequest,
        market: MarketMetadata,
    ) -> OrderResponse:
        """Places a limit order using Scheme 1 typed payload."""
        self._assert_trading_allowed()

        # Simulated Paper Trading Mode
        if self.config.paper_trading_mode:
            logger.info(f"[PAPER TRADING] Simulating {order.side} {order.quantity} @ {order.price}")
            return OrderResponse(
                orderId="paper-order-id-simulated",
                clientId=order.clientId,
                status="ACK",
                marketId=order.marketId,
                raw={"paper": True},
            )

        # Convert price and size to exact integer ticks and quantums
        price_ticks = to_ticks(order.price, market.tickSize)
        quantity_quantums = to_quantums(order.quantity, market.stepSize)

        good_til_micros = order.goodTilTimeMicros or good_til_time_micros()
        good_til_nanos = good_til_micros * 1000

        # Build Scheme 1 signed canonical payload
        payload_str, signature, ts = self.signer.build_place_order_payload(
            address=self.config.wallet_address,
            account_index=self.config.account_index,
            market_id=order.marketId,
            side_int=order.side.int_code,
            price_ticks=price_ticks,
            quantity_quantums=quantity_quantums,
            tif_int=order.timeInForce.int_code,
            good_til_nanos=good_til_nanos,
            reduce_only=1 if order.reduceOnly else 0,
            client_id=order.clientId,
        )

        body: Dict[str, Any] = {
            "address": self.config.wallet_address,
            "accountIndex": self.config.account_index,
            "marketId": order.marketId,
            "orderSide": order.side.value,
            "orderType": order.orderType.value,
            "quantity": str(order.quantity),
            "price": str(order.price),
            "timeInForce": order.timeInForce.value,
            "goodTilTime": str(good_til_micros),
            "timestamp": ts,
        }
        if order.clientId:
            body["clientId"] = order.clientId

        headers = self.signer.get_auth_headers(signature, ts)
        res = await self._request("POST", "/v1/placeOrder", "placeOrder", json_body=body, headers=headers)
        return OrderResponse(
            orderId=res.get("orderId"),
            clientId=res.get("clientId", order.clientId),
            status=res.get("status", "ACK"),
            marketId=order.marketId,
            rateLimit=res.get("rateLimit"),
            raw=res,
        )

    async def modify_order(
        self,
        market_id: int,
        order_id: str,
        price: Decimal,
        quantity: Decimal,
        side: OrderSide,
        market: MarketMetadata,
        client_id: Optional[str] = None,
        good_til_micros: Optional[int] = None,
    ) -> OrderResponse:
        """Re-prices a resting ALO order (cancel-replace on the venue, 1 order-pool unit)."""
        self._assert_trading_allowed()

        if self.config.paper_trading_mode:
            logger.info(f"[PAPER TRADING] Simulating modify {order_id} -> {quantity} @ {price}")
            return OrderResponse(orderId=order_id, clientId=client_id, status="ACK",
                                 marketId=market_id, raw={"paper": True})

        good_til_micros = good_til_micros or good_til_time_micros()
        payload_str, signature, ts = self.signer.build_modify_order_payload(
            address=self.config.wallet_address,
            account_index=self.config.account_index,
            market_id=market_id,
            order_id=str(order_id),
            side_int=side.int_code,
            price_ticks=to_ticks(price, market.tickSize),
            quantity_quantums=to_quantums(quantity, market.stepSize),
            tif_int=TimeInForce.ALO.int_code,
            good_til_nanos=good_til_micros * 1000,
            reduce_only=0,
            client_id=client_id,
        )
        body: Dict[str, Any] = {
            "address": self.config.wallet_address,
            "accountIndex": self.config.account_index,
            "marketId": market_id,
            "orderId": str(order_id),
            "orderSide": side.value,
            "orderType": OrderType.LIMIT.value,
            "quantity": str(quantity),
            "price": str(price),
            "timeInForce": TimeInForce.ALO.value,
            "goodTilTime": str(good_til_micros),
            "timestamp": ts,
        }
        if client_id:
            body["clientId"] = client_id
        headers = self.signer.get_auth_headers(signature, ts)
        res = await self._request("POST", "/v1/modifyOrder", "modifyOrder", json_body=body, headers=headers)
        return OrderResponse(orderId=res.get("orderId", order_id), clientId=res.get("clientId", client_id),
                             status=res.get("status", "ACK"), marketId=market_id,
                             rateLimit=res.get("rateLimit"), raw=res)

    async def cancel_order(
        self,
        market_id: int,
        order_id: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> OrderResponse:
        """Cancels an order by orderId or clientId using Scheme 1."""
        self._assert_trading_allowed()

        if self.config.paper_trading_mode:
            logger.info(f"[PAPER TRADING] Simulating cancel orderId={order_id}, clientId={client_id}")
            return OrderResponse(
                orderId=order_id,
                clientId=client_id,
                status="CANCELED",
                marketId=market_id,
                raw={"paper": True},
            )

        payload_str, signature, ts = self.signer.build_cancel_order_payload(
            address=self.config.wallet_address,
            account_index=self.config.account_index,
            market_id=market_id,
            order_id=order_id,
            client_id=client_id,
        )

        body: Dict[str, Any] = {
            "address": self.config.wallet_address,
            "accountIndex": self.config.account_index,
            "marketId": market_id,
            "timestamp": ts,
        }
        if order_id:
            body["kind"] = "orderId"
            body["orderId"] = str(order_id)
        else:
            body["kind"] = "clientId"
            body["clientId"] = str(client_id)

        headers = self.signer.get_auth_headers(signature, ts)
        res = await self._request("POST", "/v1/cancelOrder", "cancelOrder", json_body=body, headers=headers)
        return OrderResponse(
            orderId=order_id,
            clientId=client_id,
            status=res.get("status", "CANCELED"),
            marketId=market_id,
            rateLimit=res.get("rateLimit"),
            raw=res,
        )

    async def cancel_all_orders(
        self,
        market_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Cancels all open orders (charges 1,000 cancel units). Uses Scheme 2."""
        self._assert_trading_allowed()

        body: Dict[str, Any] = {
            "address": self.config.wallet_address,
            "accountIndex": self.config.account_index,
        }
        if market_id is not None:
            body["marketId"] = market_id

        signature, ts = self.signer.sign_scheme_2("cancelAllOrders", body)
        headers = self.signer.get_auth_headers(signature, ts)
        return await self._request("POST", "/v1/cancelAllOrders", "cancelAllOrders", json_body=body, headers=headers)

    async def schedule_cancel(
        self,
        deadline_micros: Optional[int],
    ) -> Dict[str, Any]:
        """Arms, refreshes, or disarms dead man's switch.

        Pass absolute epoch microseconds (5s to 5min ahead) to arm/refresh, or None to disarm.
        """
        self._assert_trading_allowed()

        body: Dict[str, Any] = {
            "address": self.config.wallet_address,
            "accountIndex": self.config.account_index,
            "time": deadline_micros,
        }
        signature, ts = self.signer.sign_scheme_2("scheduleCancel", body)
        headers = self.signer.get_auth_headers(signature, ts)
        params = {"address": self.config.wallet_address}
        return await self._request(
            "POST",
            "/v1/scheduleCancel",
            "cancelOrder",
            params=params,
            json_body=body,
            headers=headers,
        )
