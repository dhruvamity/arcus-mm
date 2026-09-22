"""Independent completeness and integrity check of downloaded history.

Binance (data/binance): for every symbol/kind/interval we pull, list the files Binance publishes
(since --since), report any missing locally, re-verify each local zip's SHA-256 against Binance's
.CHECKSUM, and test that it unzips cleanly.

Arcus (data/history/trades): for each market, fetch --samples random pages of /v1/trades from
inside the file's time range and check every returned trade is present in the file and identical.

Usage:
    .venv/bin/python scripts/verify_downloads.py [--skip-binance] [--skip-arcus]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from pull_binance import DEFAULT, DL, INTERVALS, OUT, get, list_keys  # noqa: E402
from pull_trade_history import API, get_with_retry  # noqa: E402

AGG = "futures/um:HYPEUSDT,futures/um:NVDAUSDT,futures/um:SPYUSDT,futures/um:QQQUSDT,futures/um:XAUUSDT,futures/um:XAGUSDT,spot:PAXGUSDT,futures/um:ZECUSDT"


def check_file(c, key):
    p = OUT / key.removeprefix("data/")
    if not p.exists():
        return key, "MISSING"
    want = get(c, DL + key + ".CHECKSUM").text.split()[0]
    if hashlib.sha256(p.read_bytes()).hexdigest() != want:
        return key, "CHECKSUM MISMATCH"
    try:
        with zipfile.ZipFile(p) as z:
            if z.testzip() is not None:
                return key, "CORRUPT ZIP"
    except zipfile.BadZipFile:
        return key, "CORRUPT ZIP"
    return key, "ok"


def verify_binance(since):
    jobs = []
    with httpx.Client(timeout=300, follow_redirects=True, limits=httpx.Limits(max_connections=16)) as c:
        for spec in DEFAULT.split(","):
            mtype, sym = spec.split(":")
            subs = [("klines", f"{sym}/{iv}/") for iv in INTERVALS]
            if mtype != "spot":
                subs.append(("fundingRate", f"{sym}/"))
            if spec in AGG.split(","):
                subs.append(("aggTrades", f"{sym}/"))
            for kind, sub in subs:
                keys = [k for k in list_keys(c, f"data/{mtype}/monthly/{kind}/{sub}")
                        if re.search(r"(\d{4}-\d{2})\.zip$", k).group(1) >= since]
                jobs += keys
        print(f"Binance: {len(jobs)} published files to check", file=sys.stderr, flush=True)
        with ThreadPoolExecutor(8) as pool:
            res = list(pool.map(lambda k: check_file(c, k), jobs))
    bad = [(k, s) for k, s in res if s != "ok"]
    local = {str(p.relative_to(OUT)) for p in OUT.glob("**/monthly/**/*.zip")}
    expected = {k.removeprefix("data/") for k in jobs}
    print(f"Binance: {len(res) - len(bad)}/{len(res)} ok; {len(local - expected)} local files not in the expected set")
    for k, s in bad:
        print(f"  {s}: {k}")
    return bad


def verify_arcus(samples):
    bad_total = 0
    rng = random.Random(7)
    with httpx.Client(base_url=API, timeout=60) as c:
        for f in sorted((ROOT / "data" / "history" / "trades").glob("*.jsonl.gz")):
            m = f.name.removesuffix(".jsonl.gz")
            with gzip.open(f, "rt") as fh:
                have = {t["tradeId"]: t for t in map(json.loads, fh)}
            ts = sorted(t["timestamp"] for t in have.values())
            lo, hi = ts[0], ts[-1]
            checked = missing = differ = 0
            for _ in range(samples):
                to = rng.randint(lo + 3_600_000_000, hi)
                page = get_with_retry(c, {"market": m, "to": to, "limit": 1000}).json().get("trades", [])
                for t in page:
                    if not lo <= t["timestamp"] <= hi:
                        continue
                    checked += 1
                    if t["tradeId"] not in have:
                        missing += 1
                    elif have[t["tradeId"]] != t:
                        differ += 1
            bad_total += missing + differ
            print(f"Arcus {m:12s}: {checked:6,} sampled trades, {missing} missing, {differ} differ", flush=True)
    return bad_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2023-09")
    ap.add_argument("--samples", type=int, default=40)
    ap.add_argument("--skip-binance", action="store_true")
    ap.add_argument("--skip-arcus", action="store_true")
    a = ap.parse_args()
    bad = 0
    if not a.skip_binance:
        bad += len(verify_binance(a.since))
    if not a.skip_arcus:
        bad += verify_arcus(a.samples)
    print("ALL DOWNLOADS VERIFIED" if bad == 0 else f"{bad} PROBLEMS FOUND")


if __name__ == "__main__":
    main()
