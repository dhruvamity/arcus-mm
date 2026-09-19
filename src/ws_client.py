"""Asynchronous WebSocket Client for Arcus Perpetuals."""

import asyncio
import json
import logging
import ssl
from typing import Dict, Any, Optional, Callable, Awaitable, Set, Union, Tuple
import websockets
from websockets.protocol import State
try:
    import certifi
    DEFAULT_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    DEFAULT_SSL_CONTEXT = ssl.create_default_context()

from src.config import ArcusConfig, settings
from src.auth import ArcusSigner
from src.utils import now_ns

logger = logging.getLogger(__name__)

CallbackType = Callable[[Dict[str, Any]], Awaitable[None]]


class ArcusWsClient:
    """Manages WebSocket connection, subscriptions, and RPC messaging for Arcus."""

    def __init__(
        self,
        config: Optional[ArcusConfig] = None,
        signer: Optional[ArcusSigner] = None,
    ):
        self.config = config or settings
        self.ws_url = self.config.ws_url
        self.signer = signer or (
            ArcusSigner(self.config.api_private_key)
            if self.config.api_private_key and self.config.api_private_key != "0" * 64
            else None
        )

        self._ws: Optional[Any] = None
        self._running: bool = False
        self._listener_task: Optional[asyncio.Task] = None

        # Callbacks: (channel, sub_id) -> list of callbacks, plus channel -> list of callbacks
        self._subscription_callbacks: Dict[Tuple[str, str], list[CallbackType]] = {}
        self._channel_callbacks: Dict[str, list[CallbackType]] = {}
        # Subscriptions to restore upon reconnect: (channel, sub_id) -> subscription message dict
        self._active_subscriptions: Dict[Tuple[str, str], Dict[str, Any]] = {}

        # Pending RPC request futures: request_id -> Future
        self._pending_requests: Dict[Union[int, str], asyncio.Future] = {}
        self._next_request_id: int = 1

    @property
    def is_connected(self) -> bool:
        if self._ws is None:
            return False
        if hasattr(self._ws, "state"):
            return self._ws.state == State.OPEN
        return not getattr(self._ws, "closed", True)

    async def connect(self) -> None:
        """Connects to the Arcus WebSocket server and starts background listener."""
        if self.is_connected:
            return

        logger.info(f"Connecting to Arcus WebSocket at {self.ws_url}...")
        ssl_ctx = DEFAULT_SSL_CONTEXT if self.ws_url.startswith("wss://") else None
        self._ws = await websockets.connect(
            self.ws_url,
            ssl=ssl_ctx,
            ping_interval=self.config.ws_ping_interval_secs,
            ping_timeout=10,
        )
        self._running = True
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info("Connected to Arcus WebSocket.")

        # Re-subscribe to any previously active subscriptions
        for sub_msg in self._active_subscriptions.values():
            await self._send_raw(sub_msg)

    async def disconnect(self) -> None:
        """Disconnects and tears down listener."""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("Disconnected from Arcus WebSocket.")

    async def _send_raw(self, payload: Dict[str, Any]) -> None:
        """Sends a JSON message over the active socket."""
        if not self.is_connected or not self._ws:
            raise ConnectionError("WebSocket is not connected")
        await self._ws.send(json.dumps(payload))

    async def subscribe(
        self,
        channel: str,
        subscription_id: str,
        callback: Optional[CallbackType] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Subscribes to a channel (e.g. bbo, l2Orderbook, trades, markets).

        Public subscriptions require no authentication.
        """
        msg: Dict[str, Any] = {
            "type": "subscribe",
            "channel": channel,
            "id": subscription_id,
        }
        if extra_fields:
            msg.update(extra_fields)

        key = (channel, subscription_id)
        self._active_subscriptions[key] = msg
        if callback:
            self._subscription_callbacks.setdefault(key, []).append(callback)

        await self._send_raw(msg)
        logger.info(f"Subscribed to channel '{channel}' (id: {subscription_id})")

    async def unsubscribe(self, channel: str, subscription_id: str) -> None:
        """Unsubscribes from an active channel."""
        msg = {
            "type": "unsubscribe",
            "channel": channel,
            "id": subscription_id,
        }
        key = (channel, subscription_id)
        self._active_subscriptions.pop(key, None)
        self._subscription_callbacks.pop(key, None)
        await self._send_raw(msg)
        logger.info(f"Unsubscribed from channel '{channel}' (id: {subscription_id})")

    async def rpc_get(
        self,
        request_type: str,
        payload: Dict[str, Any],
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Sends a 'get' request and awaits correlated response."""
        req_id = self._next_request_id
        self._next_request_id += 1

        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_requests[req_id] = fut

        msg = {
            "type": "get",
            "id": req_id,
            "request": {
                "type": request_type,
                "payload": payload,
            },
        }
        await self._send_raw(msg)

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending_requests.pop(req_id, None)

    MUTATING_WS_METHODS = {
        "placeOrder",
        "modifyOrder",
        "cancelOrder",
        "cancelAllOrders",
        "scheduleCancel",
    }

    def _assert_trading_allowed(self, method: str) -> None:
        """Enforces Mandate Section 26: Mainnet WebSocket Order-Write Safety Lock.

        Hard-blocks mutating WebSocket RPCs when mainnet_order_lock is active.
        """
        if method in self.MUTATING_WS_METHODS:
            if self.config.environment == "mainnet" and self.config.mainnet_order_lock:
                raise PermissionError(
                    f"WEBSOCKET {method} ON MAINNET IS HARD-BLOCKED by prompt.md Section 26 safety lock!"
                )
        if not self.signer:
            raise ValueError("Signer required for authenticated WebSocket trading RPC")

    async def rpc_post(
        self,
        method: str,
        canonical_signed_payload: str,
        body_payload: Dict[str, Any],
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Sends an authenticated 'post' trading request and awaits correlated response."""
        self._assert_trading_allowed(method)

        req_id = self._next_request_id
        self._next_request_id += 1

        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_requests[req_id] = fut

        ts = now_ns()
        sig = self.signer.sign_bytes(canonical_signed_payload.encode("utf-8"))

        msg = {
            "type": "post",
            "id": req_id,
            "request": {
                "type": method,
                "payload": body_payload,
                "apiKey": self.signer.api_key,
                "timestamp": str(ts),
                "signature": sig,
            },
        }
        await self._send_raw(msg)

        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending_requests.pop(req_id, None)

    async def place_order(self, canonical_payload: str, body_payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Places order via WebSocket RPC, guarded by Section 26 lock."""
        return await self.rpc_post("placeOrder", canonical_payload, body_payload, timeout=timeout)

    async def modify_order(self, canonical_payload: str, body_payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Modifies order via WebSocket RPC, guarded by Section 26 lock."""
        return await self.rpc_post("modifyOrder", canonical_payload, body_payload, timeout=timeout)

    async def cancel_order(self, canonical_payload: str, body_payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Cancels order via WebSocket RPC, guarded by Section 26 lock."""
        return await self.rpc_post("cancelOrder", canonical_payload, body_payload, timeout=timeout)

    async def cancel_all_orders(self, canonical_payload: str, body_payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Cancels all orders via WebSocket RPC, guarded by Section 26 lock."""
        return await self.rpc_post("cancelAllOrders", canonical_payload, body_payload, timeout=timeout)

    async def schedule_cancel(self, canonical_payload: str, body_payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """Schedules cancel via WebSocket RPC, guarded by Section 26 lock."""
        return await self.rpc_post("scheduleCancel", canonical_payload, body_payload, timeout=timeout)

    async def _listen_loop(self) -> None:
        """Background listener reading messages and dispatching to callbacks or futures."""
        while self._running:
            try:
                if not self._ws:
                    break
                raw_msg = await self._ws.recv()
                msg = json.loads(raw_msg)
                msg_type = msg.get("type")

                # Handle RPC correlated responses
                if "id" in msg and msg.get("id") in self._pending_requests:
                    fut = self._pending_requests.get(msg["id"])
                    if fut and not fut.done():
                        fut.set_result(msg)
                    continue

                # Handle subscribed snapshot or live channel data
                channel = msg.get("channel")
                sub_id = msg.get("id")
                if channel:
                    if sub_id and (channel, sub_id) in self._subscription_callbacks:
                        for cb in self._subscription_callbacks[(channel, sub_id)]:
                            asyncio.create_task(cb(msg))
                    if channel in self._channel_callbacks:
                        for cb in self._channel_callbacks[channel]:
                            asyncio.create_task(cb(msg))

            except asyncio.CancelledError:
                break
            except websockets.ConnectionClosed:
                logger.warning("Arcus WebSocket connection closed unexpectedly.")
                if self._running:
                    await self._handle_reconnect()
                break
            except Exception as e:
                logger.error(f"Error processing WS frame: {e}", exc_info=True)

    async def _handle_reconnect(self) -> None:
        """Handles graceful reconnect logic with exponential backoff."""
        delay = 1.0
        max_delay = 30.0
        while self._running:
            try:
                logger.info(f"Attempting to reconnect in {delay:.1f}s...")
                await asyncio.sleep(delay)
                await self.connect()
                return
            except Exception as e:
                logger.warning(f"Reconnect failed: {e}")
                delay = min(max_delay, delay * 1.5)
