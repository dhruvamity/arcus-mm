"""Unit test suite for Recorder Multi-Trade Dedup and Sequence Gap Invalidation.

Fulfills Mandate Sections 24 & 25 of prompt.md:
- Multi-trade frames deduplicated across every trade (never just first trade).
- Sequence gaps mark book invalid, record INVALID_BOOK_INTERVAL, and track gap info.
- Subsequent snapshot resets book validity to True.
"""

import unittest
from src.recorder import ArcusStreamRecorder


class TestRecorderResync(unittest.TestCase):

    def setUp(self):
        self.recorder = ArcusStreamRecorder(markets=["BTC-USD"], channels=["trades", "l2OrderbookUpdates"])

    def test_multi_trade_frame_deduplication(self):
        """Mandate §25: Deduplicates every individual trade in multi-trade frames."""
        raw_frame_1 = {
            "type": "channel_data",
            "contents": [
                {"tradeId": "t1", "price": "80000.0", "size": "0.1", "side": "buy"},
                {"tradeId": "t2", "price": "80001.0", "size": "0.2", "side": "sell"},
            ],
        }

        # First frame should process both trades
        self.recorder._handle_message("sess_1", "trades", "BTC-USD", raw_frame_1)
        self.assertEqual(len(raw_frame_1["contents"]), 2)
        self.assertEqual(self.recorder._metrics["messages_recorded"], 1)

        # Second frame contains t2 (duplicate) and t3 (new)
        raw_frame_2 = {
            "type": "channel_data",
            "contents": [
                {"tradeId": "t2", "price": "80001.0", "size": "0.2", "side": "sell"},
                {"tradeId": "t3", "price": "80002.0", "size": "0.3", "side": "buy"},
            ],
        }
        self.recorder._handle_message("sess_1", "trades", "BTC-USD", raw_frame_2)
        # Only t3 should remain in contents
        self.assertEqual(len(raw_frame_2["contents"]), 1)
        self.assertEqual(raw_frame_2["contents"][0]["tradeId"], "t3")

        # Third frame contains only duplicates
        raw_frame_3 = {
            "type": "channel_data",
            "contents": [
                {"tradeId": "t1", "price": "80000.0", "size": "0.1", "side": "buy"},
                {"tradeId": "t3", "price": "80002.0", "size": "0.3", "side": "buy"},
            ],
        }
        self.recorder._handle_message("sess_1", "trades", "BTC-USD", raw_frame_3)
        self.assertEqual(self.recorder._metrics["duplicates_dropped"], 1)

    def test_sequence_gap_invalidates_book_and_emits_marker(self):
        """Mandate §24: Sequence gaps mark book invalid and queue INVALID_BOOK_INTERVAL."""
        key = "BTC-USD:l2OrderbookUpdates"

        # 1. Initial snapshot
        snap_msg = {
            "type": "subscribed",
            "contents": {"lastSequenceId": 100, "bids": [], "asks": []},
        }
        self.recorder._handle_message("sess_1", "l2OrderbookUpdates", "BTC-USD", snap_msg)
        self.assertTrue(self.recorder._book_valid.get(key))

        # 2. First delta (boundary offset allowed per Arcus splice rule)
        delta_1 = {
            "type": "channel_data",
            "contents": {"lastSequenceId": 105, "bids": [], "asks": []},
        }
        self.recorder._handle_message("sess_1", "l2OrderbookUpdates", "BTC-USD", delta_1)
        self.assertTrue(self.recorder._book_valid.get(key))

        # 3. Gap: expected 106, got 110
        delta_gap = {
            "type": "channel_data",
            "contents": {"lastSequenceId": 110, "bids": [], "asks": []},
        }
        self.recorder._handle_message("sess_1", "l2OrderbookUpdates", "BTC-USD", delta_gap)
        self.assertFalse(self.recorder._book_valid.get(key), "Book must be marked invalid upon sequence gap")
        self.assertEqual(self.recorder._metrics["sequence_gaps"], 1)

        # Check that INVALID_BOOK_INTERVAL was queued
        file_key = self.recorder._get_channel_file_key("BTC-USD", "l2OrderbookUpdates")
        queue = self.recorder._write_queues.get(file_key)
        self.assertIsNotNone(queue)
        # Drain items from queue to verify marker
        items = []
        while not queue.empty():
            items.append(queue.get_nowait())
        gap_records = [item for item in items if item.get("type") == "INVALID_BOOK_INTERVAL"]
        self.assertEqual(len(gap_records), 1)
        self.assertEqual(gap_records[0]["gap_info"]["expected_seq"], 106)
        self.assertEqual(gap_records[0]["gap_info"]["received_seq"], 110)

        # 4. Resync snapshot restores book validity
        snap_resync = {
            "type": "subscribed",
            "contents": {"lastSequenceId": 200, "bids": [], "asks": []},
        }
        self.recorder._handle_message("sess_1", "l2OrderbookUpdates", "BTC-USD", snap_resync)
        self.assertTrue(self.recorder._book_valid.get(key), "Subsequent snapshot must restore book validity")


if __name__ == "__main__":
    unittest.main()
