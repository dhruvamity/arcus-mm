"""Download Binance public market data (data.binance.vision) for Arcus-equivalent assets.

Monthly zips are fetched with their published .CHECKSUM and verified (SHA-256) before being
kept under data/binance/<spot|futures/um>/<kind>/<SYMBOL>/[<interval>/]. Existing verified
files are skipped, so re-running only adds new months.

Usage:
    .venv/bin/python scripts/pull_binance.py --kinds klines --symbols futures/um:HYPEUSDT,spot:PAXGUSDT
    .venv/bin/python scripts/pull_binance.py --kinds aggTrades,fundingRate --since 2023-09
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "binance"
LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DL = "https://data.binance.vision/"
INTERVALS = ["5m", "15m", "1h", "4h", "1d", "1w"]

# Arcus market -> Binance proxy (market type, symbol). LIT is omitted: Binance LITUSDT is Litentry,
# not Lighter. GLD uses PAXG (spot, 2020+) and XAU (perp, 2025-12+).
DEFAULT = ("futures/um:HYPEUSDT,futures/um:NVDAUSDT,futures/um:SPYUSDT,futures/um:QQQUSDT,futures/um:XAUUSDT,"
           "futures/um:XAGUSDT,spot:PAXGUSDT,futures/um:ZECUSDT,futures/um:BTCUSDT,futures/um:ETHUSDT,futures/um:SOLUSDT")


def list_keys(c: httpx.Client, prefix: str) -> list[str]:
    keys, marker = [], ""
    while True:
        r = get(c, LIST + "?" + urllib.parse.urlencode({"prefix": prefix, "marker": marker}))
        ks = re.findall(r"<Key>([^<]+)</Key>", r.text)
        keys += ks
        if "<IsTruncated>true</IsTruncated>" not in r.text or not ks:
            return [k for k in keys if k.endswith(".zip")]
        marker = ks[-1]


def get(c: httpx.Client, url: str, attempts: int = 6) -> httpx.Response:
    for i in range(attempts):
        try:
            r = c.get(url)
            if r.status_code < 500:
                r.raise_for_status()
                return r
        except (httpx.TimeoutException, httpx.TransportError) as e:
            print(f"  {type(e).__name__} on {url.rsplit('/', 1)[-1]}, retry {i + 1}/{attempts}", file=sys.stderr, flush=True)
        time.sleep(min(60, 2 ** i))
    raise RuntimeError(f"giving up on {url}")


def fetch(c: httpx.Client, key: str) -> str:
    dest = OUT / key.removeprefix("data/")
    if dest.exists():
        return "skip"
    for _ in range(3):  # a corrupted transfer fails the checksum: download again
        want = get(c, DL + urllib.parse.quote(key) + ".CHECKSUM").text.split()[0]
        data = get(c, DL + urllib.parse.quote(key)).content
        if hashlib.sha256(data).hexdigest() == want:
            break
    else:
        raise RuntimeError(f"checksum mismatch 3 times: {key}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return f"{len(data) / 1e6:.1f} MB"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=DEFAULT)
    ap.add_argument("--kinds", default="klines", help="klines,aggTrades,fundingRate")
    ap.add_argument("--since", default="2023-09", help="first month (YYYY-MM)")
    ap.add_argument("--daily", default="", help="YYYY-MM: fetch that month's daily files instead (for the current month)")
    a = ap.parse_args()
    with httpx.Client(timeout=300, follow_redirects=True, limits=httpx.Limits(max_connections=16)) as c:
        for spec in a.symbols.split(","):
            mtype, sym = spec.split(":")
            for kind in a.kinds.split(","):
                if kind == "fundingRate" and mtype == "spot":
                    continue
                subs = [f"{sym}/{iv}/" for iv in INTERVALS] if kind == "klines" else [f"{sym}/"]
                for sub in subs:
                    if a.daily:
                        keys = list_keys(c, f"data/{mtype}/daily/{kind}/{sub}{sub.split('/')[0]}-{kind}-{a.daily}")
                    else:
                        keys = [k for k in list_keys(c, f"data/{mtype}/monthly/{kind}/{sub}")
                                if re.search(r"(\d{4}-\d{2})\.zip$", k).group(1) >= a.since]
                    with ThreadPoolExecutor(8) as pool:  # httpx.Client is thread-safe
                        got = sum(r != "skip" for r in pool.map(lambda k: fetch(c, k), keys))
                    print(f"{mtype} {kind} {sub}: {len(keys)} months ({got} new)", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
