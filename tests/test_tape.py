"""src/tape.py: dedupe and transparent fallback to storage_manager's .gz copies."""

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import tape


def bbo_line(seq, ts, bid, ask):
    c = {"bestBid": {"price": str(bid), "size": "1"}, "bestAsk": {"price": str(ask), "size": "2"},
         "timestamp": ts, "globalSequenceId": seq}
    return json.dumps({"recv_ts_ns": ts * 1000, "data": {"contents": c}}) + "\n"


def trade_line(tid, ts, side, px):
    t = {"tradeId": tid, "timestamp": ts, "side": side, "price": str(px), "size": "0.5",
         "makerAddress": "0xm", "takerAddress": "0xt", "sequenceNumber": ts}
    return json.dumps({"recv_ts_ns": ts * 1000, "data": {"contents": [t]}}) + "\n"


class TestTape(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.raw, self.gz = root / "raw", root / "compressed"
        bbo = bbo_line(1, 10, 99, 101) + bbo_line(1, 10, 99, 101) + bbo_line(2, 20, 100, 102)  # dup seq 1
        trades = trade_line("a", 15, "BUY", 101) + trade_line("a", 15, "BUY", 101) + trade_line("b", 25, "SELL", 100)
        d1 = self.raw / "2026-01-01" / "X-USD"
        d1.mkdir(parents=True)
        (d1 / "bbo.jsonl").write_text(bbo)
        (d1 / "trades.jsonl").write_text(trades)
        d2 = self.gz / "2026-01-02" / "X-USD"   # a closed day that only exists compressed
        d2.mkdir(parents=True)
        with gzip.open(d2 / "bbo.jsonl.gz", "wt") as f:
            f.write(bbo_line(3, 30, 101, 103))
        with gzip.open(d2 / "trades.jsonl.gz", "wt") as f:
            f.write(trade_line("c", 35, "BUY", 103))
        self.p = mock.patch.multiple(tape, RAW_ROOT=self.raw, GZ_ROOT=self.gz)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.tmp.cleanup()

    def test_days_span_raw_and_gz(self):
        self.assertEqual(tape.tape_days("X-USD"), ["2026-01-01", "2026-01-02"])

    def test_dedupe_and_gz_fallback(self):
        b = tape.load_bbo("X-USD")
        self.assertEqual(list(b.ts), [10, 20, 30])
        self.assertEqual(list(b.mid), [100.0, 101.0, 102.0])
        t = tape.load_trades("X-USD")
        self.assertEqual(list(t.ts), [15, 25, 35])
        self.assertEqual(list(t.taker_buy), [True, False, True])

    def test_same_sequence_id_different_content_is_kept(self):
        # Arcus sent "bid back" then "ask back" under one globalSequenceId (NVDA 2026-09-23); the
        # second frame is the real book. Only byte-identical copies (overlapping sockets) are dupes.
        d = self.raw / "2026-01-03" / "Y-USD"
        d.mkdir(parents=True)
        (d / "bbo.jsonl").write_text(bbo_line(7, 70, 228.34, 228.46) + bbo_line(7, 71, 228.34, 228.39)
                                     + bbo_line(7, 71, 228.34, 228.39))
        (d / "trades.jsonl").write_text("")
        self.assertEqual(list(tape.load_bbo("Y-USD").ask), [228.46, 228.39])
        from src.replay import BBO, _parse_day
        cols = _parse_day("2026-01-03", "Y-USD")
        self.assertEqual(list(cols["sz"][cols["kind"] == BBO]), [228.46, 228.39])   # replay keeps ask in sz


if __name__ == "__main__":
    unittest.main()
