"""Unit tests for Arcus authentication, signing, tick arithmetic, and orderbook reconstruction."""

import unittest
import json
from decimal import Decimal
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.utils import (
    to_ticks,
    from_ticks,
    to_quantums,
    from_quantums,
    canonical_json,
    snap_to_tick,
)
from src.auth import ArcusSigner
from src.rate_limiter import RateLimiter
from src.orderbook import LocalOrderBook


class TestArcusUtils(unittest.TestCase):
    """Tests Decimal tick/step conversions and canonical JSON."""

    def test_exact_tick_conversion(self):
        # BTC-USD tickSize = 0.1
        self.assertEqual(to_ticks("50000.1", "0.1"), 500001)
        self.assertEqual(to_ticks(50000, 1), 50000)
        self.assertEqual(from_ticks(500001, "0.1"), Decimal("50000.1"))

    def test_inexact_tick_conversion_raises_error(self):
        with self.assertRaises(ValueError):
            to_ticks("50000.05", "0.1")  # not a multiple of 0.1

    def test_exact_quantum_conversion(self):
        # BTC-USD stepSize = 0.00000001
        self.assertEqual(to_quantums("0.00000005", "0.00000001"), 5)
        self.assertEqual(from_quantums(5, "0.00000001"), Decimal("0.00000005"))

    def test_inexact_quantum_conversion_raises_error(self):
        with self.assertRaises(ValueError):
            to_quantums("0.000000001", "0.00000001")

    def test_snap_to_tick(self):
        snapped = snap_to_tick("50000.14", "0.1")
        self.assertEqual(snapped, Decimal("50000.1"))
        snapped_up = snap_to_tick("50000.16", "0.1")
        self.assertEqual(snapped_up, Decimal("50000.2"))

    def test_canonical_json_sorting_and_compactness(self):
        data = {"z": 1, "a": "test", "m": [3, 2, 1], "d": {"k": "v"}}
        res = canonical_json(data)
        # Verify no spaces and sorted top-level keys
        self.assertEqual(res, '{"a":"test","d":{"k":"v"},"m":[3,2,1],"z":1}')


class TestArcusAuth(unittest.TestCase):
    """Tests Ed25519 signing schemes."""

    def setUp(self):
        self.signer = ArcusSigner.generate()

    def test_keypair_properties(self):
        self.assertEqual(len(self.signer.private_key_hex), 64)
        self.assertEqual(len(self.signer.api_key), 64)

    def test_scheme_1_place_order(self):
        addr = "0xAbCd1234567890AbCd1234567890AbCd12345678"
        payload_str, signature, ts = self.signer.build_place_order_payload(
            address=addr,
            account_index=0,
            market_id=1,
            side_int=0,
            price_ticks=500000,
            quantity_quantums=100,
            tif_int=3,  # ALO
            good_til_nanos=4102444800000000000,
            client_id="test-cid-1",
            timestamp_ns=1700000000000000000,
        )

        parsed = json.loads(payload_str)
        # Ensure address was lowercased
        self.assertEqual(parsed["ad"], addr.lower())
        self.assertEqual(parsed["ai"], 0)
        self.assertEqual(parsed["op"], 1)
        self.assertEqual(parsed["p"], 500000)
        self.assertEqual(parsed["q"], 100)
        self.assertEqual(parsed["t"], 3)
        self.assertEqual(parsed["c"], "test-cid-1")

        # Verify signature length is 128 hex characters (64 bytes)
        self.assertEqual(len(signature), 128)

        # Cryptographically verify signature using public key
        pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.signer.api_key))
        pub.verify(bytes.fromhex(signature), payload_str.encode("utf-8"))

    def test_scheme_1_cancel_order(self):
        addr = "0x1234567890123456789012345678901234567890"
        payload_str, signature, ts = self.signer.build_cancel_order_payload(
            address=addr,
            account_index=0,
            market_id=1,
            order_id="server-ord-99",
            timestamp_ns=1700000000000000000,
        )

        parsed = json.loads(payload_str)
        self.assertEqual(parsed["op"], 2)
        self.assertEqual(parsed["id"], "server-ord-99")
        self.assertNotIn("c", parsed)

        # Verify signature
        pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.signer.api_key))
        pub.verify(bytes.fromhex(signature), payload_str.encode("utf-8"))

    def test_scheme_2_signing(self):
        body = {"address": "0x1234567890123456789012345678901234567890", "accountIndex": 0}
        sig, ts = self.signer.sign_scheme_2("cancelAllOrders", body, timestamp_ns=1700000000000000000)

        # Verify Scheme 2 signature
        expected_msg = f"{ts}cancelAllOrders{canonical_json(body)}".encode("utf-8")
        pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(self.signer.api_key))
        pub.verify(bytes.fromhex(sig), expected_msg)


class TestRateLimiter(unittest.TestCase):
    """Tests IP weight and subaccount pool replenishment math."""

    def test_fill_replenishment(self):
        limiter = RateLimiter(starting_order_cap=20000, starting_cancel_cap=40000)
        # $50 fill => 50 / 0.10 = 500 units added
        limiter.record_fill(fill_notional_usd=50.0)
        self.assertEqual(limiter.order_pool.cap, 20500)
        self.assertEqual(limiter.cancel_pool.cap, 40500)


class TestOrderBook(unittest.TestCase):
    """Tests L2 Order Book reconstruction and sequence rules."""

    def test_snapshot_and_deltas(self):
        book = LocalOrderBook("BTC-USD")
        snapshot = {
            "bids": [["50000.0", "1.0"], ["49990.0", "2.0"]],
            "asks": [["50010.0", "1.5"], ["50020.0", "3.0"]],
            "lastSequenceId": 100,
        }
        book.apply_snapshot(snapshot)
        self.assertTrue(book.is_synced)
        self.assertEqual(book.best_bid(), (Decimal("50000.0"), Decimal("1.0")))
        self.assertEqual(book.best_ask(), (Decimal("50010.0"), Decimal("1.5")))
        self.assertEqual(book.spread(), Decimal("10.0"))
        self.assertEqual(book.mid(), Decimal("50005.0"))

        # Rule: Initial delta sequence offset is permitted (e.g. seq 105 > 100)
        delta_1 = {
            "bids": [["50001.0", "0.5"]],
            "asks": [],
            "lastSequenceId": 105,
        }
        applied = book.apply_delta(delta_1)
        self.assertTrue(applied)
        self.assertTrue(book.is_synced)
        self.assertEqual(book.best_bid(), (Decimal("50001.0"), Decimal("0.5")))

        # Subsequent delta must be contiguous (106)
        delta_2 = {
            "bids": [],
            "asks": [["50008.0", "0.8"]],
            "lastSequenceId": 106,
        }
        applied = book.apply_delta(delta_2)
        self.assertTrue(applied)
        self.assertEqual(book.best_ask(), (Decimal("50008.0"), Decimal("0.8")))

        # Mid-stream gap: seq 110 > 106 + 1 => must invalidate book
        delta_gap = {
            "bids": [],
            "asks": [["50007.0", "1.0"]],
            "lastSequenceId": 110,
        }
        applied = book.apply_delta(delta_gap)
        self.assertFalse(applied)
        self.assertFalse(book.is_synced)
        self.assertTrue(book.sequence_gap_detected)


if __name__ == "__main__":
    unittest.main()
