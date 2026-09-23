"""Check src/sweeps.py's quote-free estimate against true BBO on recorded Arcus tape.

For each market and depth bucket, prints maker rs30 computed two ways on the same trades:
  true   depth beyond the recorded best bid/ask, markout vs recorded mid
  proxy  depth beyond the sweep's first print, markout vs mid estimated from prints only

Usage:
    .venv/bin/python scripts/validate_sweep_proxy.py [--markets SPY-USD,HYPE-USD]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import sweeps  # noqa: E402
from src.tape import _lines, load_bbo, market_days  # noqa: E402


def recorded_trades(market):
    rows, seen = [], set()
    for line in _lines(market_days(market), "trades.jsonl"):
        for t in (json.loads(line).get("data") or {}).get("contents") or []:
            if t["tradeId"] not in seen:
                seen.add(t["tradeId"])
                rows.append((t["timestamp"], float(t["price"]), float(t["size"]), t["side"] == "BUY", t["sequenceNumber"]))
    a = np.array(rows, dtype=float)
    return a[:, 0].astype(np.int64), a[:, 1], a[:, 2], a[:, 3].astype(bool), a[:, 4].astype(np.int64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default="SPY-USD,HYPE-USD,NVDA-USD,GLD-USD,BTC-USD,ETH-USD")
    a = ap.parse_args()
    print("| market | bucket | true rs30 (n) | proxy rs30 (n) |\n|---|---|---:|---:|")
    for mk in a.markets.split(","):
        ts, px, q, tb, g = recorded_trades(mk)
        _, dep, rs, n = sweeps.sweep_table(ts, px, q, tb, g)
        prox = {lab: (c, v) for lab, c, v in sweeps.by_bucket(dep, rs, n)}
        b = load_bbo(mk)
        i0 = b.asof(ts)
        ok = (i0 >= 0) & (ts + 30_000_000 <= b.ts[-1])
        i0 = np.maximum(i0, 0)
        sg = np.where(tb, 1.0, -1.0)
        m0 = b.mid[i0]
        d = sg * (px - np.where(tb, b.ask[i0], b.bid[i0])) / m0 * 1e4
        d = np.where(np.abs(d) < 1e-6, 0.0, d)
        r = sg * (px - b.mid[b.asof(ts + 30_000_000)]) / m0 * 1e4
        true = {lab: (c, v) for lab, c, v in sweeps.by_bucket(d[ok], r[ok], (px * q)[ok])}
        for _, _, lab in sweeps.BUCKETS:
            t, p = true.get(lab), prox.get(lab)
            if t or p:
                f = lambda x: f"{x[1]:+.2f} ({x[0]})" if x else "—"  # noqa: E731
                print(f"| {mk} | {lab} | {f(t)} | {f(p)} |")


if __name__ == "__main__":
    main()
