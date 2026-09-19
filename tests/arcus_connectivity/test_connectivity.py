"""Phase 0 Connectivity Test Suite.

Validates REST and WebSocket connectivity, health checks, clock synchronization,
and public channel snapshots.
"""

import unittest
import asyncio
import time
from src.config import settings
from src.rest_client import ArcusRestClient
from src.ws_client import ArcusWsClient


class TestArcusConnectivity(unittest.IsolatedAsyncioTestCase):
    """Verifies live venue connectivity and latency bounds."""

    async def asyncSetUp(self):
        self.rest_client = ArcusRestClient()
        self.ws_client = ArcusWsClient()

    async def asyncTearDown(self):
        await self.rest_client.close()
        if self.ws_client.is_connected:
            await self.ws_client.disconnect()

    async def test_rest_health_and_clock(self):
        """Validates GET /health and clock synchronization."""
        health = await self.rest_client.get_health()
        self.assertEqual(health.get("status"), "ok")

        t_start = time.time_ns()
        server_time_ns = await self.rest_client.get_server_time()
        t_end = time.time_ns()

        round_trip_ms = (t_end - t_start) / 1_000_000
        # Clock skew estimation
        estimated_local_at_server = (t_start + t_end) // 2
        skew_ms = abs(estimated_local_at_server - server_time_ns) / 1_000_000

        self.assertLess(round_trip_ms, 2000.0, "REST latency exceeded 2000ms")
        self.assertLess(skew_ms, 5000.0, "Clock skew exceeded 5s")

    async def test_rest_markets_retrieval(self):
        """Validates market universe retrieval and basic metadata."""
        markets = await self.rest_client.get_markets()
        self.assertGreaterEqual(len(markets), 50, "Expected at least 50 perpetual markets")
        symbols = [m.marketDisplayName for m in markets]
        self.assertIn("BTC-USD", symbols)
        self.assertIn("ETH-USD", symbols)

    async def test_ws_public_stream_handshake(self):
        """Validates WebSocket connection, subscription, and immediate snapshot."""
        await self.ws_client.connect()
        self.assertTrue(self.ws_client.is_connected)

        received_snapshots = []
        async def on_bbo(msg):
            if msg.get("type") == "subscribed":
                received_snapshots.append(msg)

        await self.ws_client.subscribe("bbo", "BTC-USD", callback=on_bbo)

        # Await snapshot frame
        for _ in range(25):
            if received_snapshots:
                break
            await asyncio.sleep(0.1)

        self.assertEqual(len(received_snapshots), 1, "Failed to receive initial snapshot on subscribe")
        snapshot = received_snapshots[0]
        self.assertEqual(snapshot.get("channel"), "bbo")
        self.assertIn("contents", snapshot)
        self.assertIn("bestBid", snapshot["contents"])
        self.assertIn("bestAsk", snapshot["contents"])


if __name__ == "__main__":
    unittest.main()
