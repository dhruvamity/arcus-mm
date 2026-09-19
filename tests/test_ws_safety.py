"""Unit tests for WebSocket Order-Write Safety Lock.

Fulfills Mandate Section 26 of prompt.md:
- Hard mainnet mutation lock for WebSocket RPC operations:
  placeOrder, modifyOrder, cancelOrder, cancelAllOrders, scheduleCancel.
- Confirms PermissionError is raised on mainnet mutations.
"""

import unittest
import asyncio

from src.auth import ArcusSigner
from src.config import ArcusConfig
from src.ws_client import ArcusWsClient


class TestWebSocketSafetyLock(unittest.TestCase):

    def setUp(self):
        self.signer = ArcusSigner.generate()
        self.mainnet_config = ArcusConfig(
            environment="mainnet",
            mainnet_order_lock=True,
            paper_trading_mode=False,
            wallet_address="0x1234567890123456789012345678901234567890",
            api_private_key=self.signer.private_key_hex,
        )
        self.ws_client = ArcusWsClient(config=self.mainnet_config, signer=self.signer)

    def test_ws_mainnet_order_lock(self):
        """Mandate §26: WebSocket placeOrder is hard-blocked on mainnet."""
        with self.assertRaises(PermissionError) as ctx:
            asyncio.run(
                self.ws_client.place_order(
                    canonical_payload="dummy_place",
                    body_payload={"op": 1, "market": "BTC-USD"},
                )
            )
        self.assertIn("placeOrder", str(ctx.exception))
        self.assertIn("MAINNET", str(ctx.exception))

    def test_ws_mainnet_cancel_lock(self):
        """Mandate §26: WebSocket cancelOrder is hard-blocked on mainnet."""
        with self.assertRaises(PermissionError) as ctx:
            asyncio.run(
                self.ws_client.cancel_order(
                    canonical_payload="dummy_cancel",
                    body_payload={"op": 2, "id": "order-123"},
                )
            )
        self.assertIn("cancelOrder", str(ctx.exception))
        self.assertIn("MAINNET", str(ctx.exception))

    def test_ws_mainnet_modify_lock(self):
        """Mandate §26: WebSocket modifyOrder is hard-blocked on mainnet."""
        with self.assertRaises(PermissionError) as ctx:
            asyncio.run(
                self.ws_client.modify_order(
                    canonical_payload="dummy_modify",
                    body_payload={"op": 3, "id": "order-123", "p": 80000, "q": 100},
                )
            )
        self.assertIn("modifyOrder", str(ctx.exception))
        self.assertIn("MAINNET", str(ctx.exception))

    def test_ws_mainnet_cancel_all_lock(self):
        """Mandate §26: WebSocket cancelAllOrders is hard-blocked on mainnet."""
        with self.assertRaises(PermissionError) as ctx:
            asyncio.run(
                self.ws_client.cancel_all_orders(
                    canonical_payload="dummy_cancel_all",
                    body_payload={"op": 4},
                )
            )
        self.assertIn("cancelAllOrders", str(ctx.exception))
        self.assertIn("MAINNET", str(ctx.exception))

    def test_ws_mainnet_schedule_cancel_lock(self):
        """Mandate §26: WebSocket scheduleCancel is hard-blocked on mainnet."""
        with self.assertRaises(PermissionError) as ctx:
            asyncio.run(
                self.ws_client.schedule_cancel(
                    canonical_payload="dummy_schedule_cancel",
                    body_payload={"op": 5, "timestamp": 123456789},
                )
            )
        self.assertIn("scheduleCancel", str(ctx.exception))
        self.assertIn("MAINNET", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
