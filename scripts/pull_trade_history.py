"""Download Arcus public trade history (the venue keeps a rolling ~30 days).

Pages GET /v1/trades backwards with `to` (epoch µs, inclusive; pages overlap, deduped by
tradeId) until the venue returns nothing older. Writes
data/history/trades/<MARKET>.jsonl.gz (oldest first, one trade per line) and merges with
any earlier pull, so re-running extends coverage instead of losing it.

Usage:
    .venv/bin/python scripts/pull_trade_history.py --markets SPY-USD,GLD-USD
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "history" / "trades"
API = "https://api.arcus.xyz"
MIN_REAL_US = 1_750_000_000_000_000  # ignore placeholder rows dated 2026-01-01 and earlier


def get_with_retry(client: httpx.Client, params: dict, attempts: int = 8) -> httpx.Response:
    """GET /v1/trades, retrying timeouts, connection errors, 429 and 5xx with backoff."""
    for i in range(attempts):
        try:
            r = client.get("/v1/trades", params=params)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            print(f"\n  {type(e).__name__}, retry {i + 1}/{attempts}", file=sys.stderr)
            time.sleep(min(60, 2 ** i))
            continue
        if r.status_code == 429:
            time.sleep(float(r.json().get("retryAfterMs", 2000)) / 1000)
            continue
        if r.status_code >= 500:
            time.sleep(min(60, 2 ** i))
            continue
        r.raise_for_status()
        return r
    raise RuntimeError(f"/v1/trades failed {attempts} times for {params}")


def pull(client: httpx.Client, market: str, stop_us: int) -> dict:
    trades: dict = {}
    to = int(time.time() * 1e6)
    while True:
        r = get_with_retry(client, {"market": market, "to": to, "limit": 1000})
        page = [t for t in r.json().get("trades", []) if t["timestamp"] >= max(MIN_REAL_US, stop_us)]
        new = [t for t in page if t["tradeId"] not in trades]
        for t in new:
            trades[t["tradeId"]] = t
        if not new:
            break
        oldest = min(t["timestamp"] for t in page)
        if oldest >= to:  # >1000 trades share one microsecond; step past it
            oldest = to - 1
        to = oldest
        print(f"\r{market}: {len(trades):>9,} trades back to "
              f"{time.strftime('%Y-%m-%d %H:%M', time.gmtime(oldest / 1e6))}", end="", file=sys.stderr, flush=True)
        time.sleep(0.9)  # /v1/trades weighs 20 of the 25/s IP budget
    print(file=sys.stderr)
    return trades


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", required=True)
    ap.add_argument("--out-dir", default=str(OUT))
    a = ap.parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=API, timeout=60) as c:
        for m in a.markets.split(","):
            f = out / f"{m}.jsonl.gz"
            old = {}
            if f.exists():
                with gzip.open(f, "rt") as fh:
                    old = {t["tradeId"]: t for t in map(json.loads, fh)}
            newest_old = max((t["timestamp"] for t in old.values()), default=0)
            got = pull(c, m, stop_us=newest_old)
            old.update(got)
            rows = sorted(old.values(), key=lambda t: (t["timestamp"], t["sequenceNumber"]))
            tmp = f.with_suffix(".tmp")
            with gzip.open(tmp, "wt") as fh:
                for t in rows:
                    fh.write(json.dumps(t, separators=(",", ":")) + "\n")
            tmp.replace(f)
            span = (rows[-1]["timestamp"] - rows[0]["timestamp"]) / 86400e6 if rows else 0
            print(f"{m}: {len(rows):,} trades over {span:.1f} days -> {f}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
