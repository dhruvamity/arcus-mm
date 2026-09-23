"""Load recorded BBO and trade tape into numpy arrays.

Reads data/raw/<YYYY-MM-DD>/<MARKET>/{bbo,trades}.jsonl written by src/recorder.py.
Timestamps are exchange timestamps in microseconds. Rows duplicated by the recorder's
overlapping sockets are dropped (BBO by sequence id + content, trades by tradeId).
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import numpy as np

RAW_ROOT = Path(__file__).resolve().parent.parent / "data" / "raw"
GZ_ROOT = RAW_ROOT.parent / "compressed"  # scripts/storage_manager.py --daily-close output


def open_tape(day: str, market: str, name: str):
    """Binary handle on data/raw/<day>/<market>/<name>, or its verified .gz copy; None if neither exists."""
    raw = RAW_ROOT / day / market / name
    if raw.exists():
        return open(raw, "rb")
    gz = GZ_ROOT / day / market / (name + ".gz")
    return gzip.open(gz, "rb") if gz.exists() else None


def tape_days(market: str) -> List[str]:
    """UTC dates with recorded data for market, raw or compressed."""
    return sorted({p.name for root in (RAW_ROOT, GZ_ROOT) if root.exists()
                   for p in root.iterdir() if (p / market).is_dir()})


@dataclass
class Bbo:
    ts: np.ndarray        # int64 exchange µs, sorted
    bid: np.ndarray
    ask: np.ndarray
    bid_sz: np.ndarray
    ask_sz: np.ndarray

    @property
    def mid(self) -> np.ndarray:
        return (self.bid + self.ask) / 2.0

    def asof(self, t: np.ndarray) -> np.ndarray:
        """Index of the last quote strictly before each t (-1 if none)."""
        return np.searchsorted(self.ts, t, side="left") - 1


@dataclass
class Trades:
    ts: np.ndarray        # int64 exchange µs, sorted
    price: np.ndarray
    size: np.ndarray
    taker_buy: np.ndarray  # bool: taker side is BUY (verified against BBO)
    maker: np.ndarray      # object: maker address
    taker: np.ndarray      # object: taker address


def market_days(market: str) -> List[Path]:
    return [RAW_ROOT / d / market for d in tape_days(market)]


def _lines(paths: Iterable[Path], name: str):
    """paths are <root>/<day>/<market> dirs; only their day and market names are used."""
    for d in paths:
        fh = open_tape(d.parent.name, d.name, name)
        if fh is not None:
            with fh:
                yield from fh


def load_bbo(market: str, days: Iterable[Path] | None = None) -> Bbo:
    days = list(days) if days is not None else market_days(market)
    seen = set()
    rows = []
    for line in _lines(days, "bbo.jsonl"):
        c = json.loads(line)["data"]["contents"]
        bb, ba = c.get("bestBid"), c.get("bestAsk")
        if not bb or not ba:
            continue
        # content, not the sequence id alone: Arcus can send two different frames under one id
        key = (c.get("globalSequenceId") or (c["timestamp"], c.get("lastSequenceId")),
               bb["price"], bb["size"], ba["price"], ba["size"])
        if key in seen:
            continue
        seen.add(key)
        rows.append((c["timestamp"], float(bb["price"]), float(ba["price"]),
                     float(bb["size"]), float(ba["size"])))
    rows.sort(key=lambda r: r[0])
    a = np.array(rows, dtype=float).reshape(-1, 5)
    ok = a[:, 2] > a[:, 1]  # drop crossed/locked snapshots
    a = a[ok]
    return Bbo(a[:, 0].astype(np.int64), a[:, 1], a[:, 2], a[:, 3], a[:, 4])


def load_trades(market: str, days: Iterable[Path] | None = None) -> Trades:
    days = list(days) if days is not None else market_days(market)
    seen = set()
    rows = []
    for line in _lines(days, "trades.jsonl"):
        for t in json.loads(line)["data"]["contents"]:
            if t["tradeId"] in seen:
                continue
            seen.add(t["tradeId"])
            rows.append((t["timestamp"], float(t["price"]), float(t["size"]),
                         t["side"] == "BUY", t.get("makerAddress", ""), t.get("takerAddress", "")))
    rows.sort(key=lambda r: r[0])
    if not rows:
        e = np.array([])
        return Trades(e.astype(np.int64), e, e, e.astype(bool), e.astype(object), e.astype(object))
    ts, px, sz, tb, mk, tk = zip(*rows)
    return Trades(np.array(ts, dtype=np.int64), np.array(px), np.array(sz), np.array(tb),
                  np.array(mk, dtype=object), np.array(tk, dtype=object))
