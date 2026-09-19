"""Phase 0 Order Lifecycle Test Suite.

Validates order construction, Scheme 1 typing, ALO flag encoding,
goodTilTime constraints, modify priority semantics, and mainnet safety lock.
"""

import unittest
import json
from decimal import Decimal

from src.auth import ArcusSigner
from src.config import ArcusConfig
from src.rest_client import ArcusRestClient
from src.models import OrderRequest, OrderSide, TimeInForce, MarketMetadata
from src.utils import good_til_time_micros, now_micros


class TestArcusOrderLifecycle(unittest.TestCase):
    """Tests order construction and venue rule enforcement."""

    def setUp(self):
        self.signer = ArcusSigner.generate()
        self.sample_market = MarketMetadata(
            marketId=1,
            marketDisplayName="BTC-USD",
            baseAsset="BTC",
            quoteAsset="USD",
            tickSize="0.1",
            stepSize="0.00000001",
            minOrderNotional="5.0",
            minOrderSize="0.0001",
        )

    def test_alo_post_only_payload_structure(self):
        """Validates that ALO orders are properly encoded with t=3."""
        payload_str, sig, ts = self.signer.build_place_order_payload(
            address="0x1234567890123456789012345678901234567890",
            account_index=0,
            market_id=1,
            side_int=0,
            price_ticks=800000,
            quantity_quantums=10000,
            tif_int=3,  # ALO
        )
        parsed = json.loads(payload_str)
        self.assertEqual(parsed["t"], 3, "Time-in-force for ALO must be integer 3")
        self.assertEqual(parsed["op"], 1, "Operation for placeOrder must be 1")

    def test_good_til_time_lead_bound(self):
        """Verifies that goodTilTime is generated at least 30 days ahead."""
        g_micros = good_til_time_micros(days_ahead=40)
        now_us = now_micros()
        diff_days = (g_micros - now_us) / (86_400 * 1_000_000)
        self.assertGreaterEqual(diff_days, 30.0, "goodTilTime must be >= 30 days ahead")

    def test_mainnet_order_safety_lock(self):
        """Asserts that client hard-blocks mutating order submission on mainnet."""
        mainnet_config = ArcusConfig(
            environment="mainnet",
            mainnet_order_lock=True,
            paper_trading_mode=False,
            wallet_address="0x1234567890123456789012345678901234567890",
            api_private_key=self.signer.private_key_hex,
        )
        client = ArcusRestClient(config=mainnet_config, signer=self.signer)

        order = OrderRequest(
            marketId=1,
            side=OrderSide.BUY,
            price=Decimal("80000.0"),
            quantity=Decimal("0.001"),
            timeInForce=TimeInForce.ALO,
        )

        with self.assertRaises(PermissionError) as ctx:
            client._assert_trading_allowed()
        self.assertIn("MAINNET", str(ctx.exception))

    def test_modify_order_payload(self):
        """Verifies Scheme 1 modifyOrder payload format echoing immutable fields."""
        payload_str, sig, ts = self.signer.build_modify_order_payload(
            address="0x1234567890123456789012345678901234567890",
            account_index=0,
            market_id=1,
            order_id="server-1234",
            side_int=0,
            price_ticks=810000,
            quantity_quantums=5000,
            tif_int=3,
            good_til_nanos=4102444800000000000,
        )
        parsed = json.loads(payload_str)
        self.assertEqual(parsed["op"], 3)
        self.assertEqual(parsed["id"], "server-1234")
        self.assertEqual(parsed["p"], 810000)
        self.assertEqual(parsed["q"], 5000)


if __name__ == "__main__":
    unittest.main()
