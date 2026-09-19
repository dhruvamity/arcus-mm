"""Phase 0 Order Book Sequence Integrity Test Suite.

Verifies Arcus L2 sequence rules:
1. Baseline sequence initialization from snapshot.
2. Initial post-snapshot delta offset tolerance.
3. Mid-stream sequence gap detection and book invalidation.
4. In-frame repeated price update ordering.
5. Level deletion on size == 0.
"""

import unittest
from decimal import Decimal
from src.orderbook import LocalOrderBook


class TestOrderBookSequenceIntegrity(unittest.TestCase):
    """Validates sequence state machine and error handling."""

    def test_initial_snapshot_and_boundary_jump(self):
        """Rule: First delta may begin several sequence numbers ahead of snapshot."""
        book = LocalOrderBook("ETH-USD")
        snapshot = {
            "bids": [["3000.0", "10.0"]],
            "asks": [["3005.0", "12.0"]],
            "lastSequenceId": 500,
        }
        book.apply_snapshot(snapshot)
        self.assertTrue(book.is_synced)
        self.assertEqual(book.last_sequence_id, 500)

        # First delta arrives at sequence 505 (ahead of snapshot 500)
        # MUST BE ACCEPTED (not marked corrupted)
        delta_first = {
            "bids": [["3001.0", "5.0"]],
            "asks": [],
            "lastSequenceId": 505,
        }
        applied = book.apply_delta(delta_first)
        self.assertTrue(applied)
        self.assertTrue(book.is_synced)
        self.assertFalse(book.sequence_gap_detected)
        self.assertEqual(book.last_sequence_id, 505)

    def test_mid_stream_sequence_gap_invalidates_book(self):
        """Rule: Mid-stream sequence gaps must invalidate the book."""
        book = LocalOrderBook("SOL-USD")
        book.apply_snapshot({"bids": [["150.0", "20.0"]], "asks": [["151.0", "20.0"]], "lastSequenceId": 100})

        # Delta 1: initial offset
        book.apply_delta({"bids": [], "asks": [["150.5", "10.0"]], "lastSequenceId": 102})
        self.assertTrue(book.is_synced)

        # Delta 2: contiguous
        book.apply_delta({"bids": [["150.1", "5.0"]], "asks": [], "lastSequenceId": 103})
        self.assertTrue(book.is_synced)

        # Delta 3: GAP! Got 105 instead of 104
        applied = book.apply_delta({"bids": [], "asks": [["150.8", "2.0"]], "lastSequenceId": 105})
        self.assertFalse(applied)
        self.assertFalse(book.is_synced)
        self.assertTrue(book.sequence_gap_detected)

    def test_repeated_price_in_frame_order(self):
        """Rule: Updates to the same price within a frame are applied in frame order."""
        book = LocalOrderBook("BTC-USD")
        book.apply_snapshot({"bids": [["80000.0", "1.0"]], "asks": [["80100.0", "1.0"]], "lastSequenceId": 10})

        # Single frame contains two updates for 80000.0: first to 5.0, then to 2.5
        frame_delta = {
            "bids": [["80000.0", "5.0"], ["80000.0", "2.5"]],
            "asks": [],
            "lastSequenceId": 11,
        }
        book.apply_delta(frame_delta)
        # Must reflect the final value in frame (2.5)
        self.assertEqual(book.bids[Decimal("80000.0")], Decimal("2.5"))

    def test_level_deletion(self):
        """Rule: size == 0 removes the level from the book."""
        book = LocalOrderBook("BTC-USD")
        book.apply_snapshot({"bids": [["80000.0", "1.0"], ["79900.0", "2.0"]], "asks": [], "lastSequenceId": 10})

        book.apply_delta({"bids": [["80000.0", "0.0"]], "asks": [], "lastSequenceId": 11})
        self.assertNotIn(Decimal("80000.0"), book.bids)
        self.assertIn(Decimal("79900.0"), book.bids)


if __name__ == "__main__":
    unittest.main()
