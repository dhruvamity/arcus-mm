"""Compare two independent pulls of Arcus trade history (scripts/pull_trade_history.py).

For each market: rows in each pull, trade IDs in both / only one, and IDs whose fields differ.
Rows only in the newer pull *after* the older pull's last timestamp are expected (new trades);
anything else is a gap or a corruption in one of the pulls.

Usage:
    .venv/bin/python scripts/compare_history.py data/history/trades data/history/trades_v2
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path


def load(f: Path) -> dict:
    with gzip.open(f, "rt") as fh:
        return {t["tradeId"]: t for t in map(json.loads, fh)}


def main():
    a_dir, b_dir = Path(sys.argv[1]), Path(sys.argv[2])
    print("| market | pull A | pull B | both | only A | only B (before A's end) | only B (newer) | fields differ | span B (days) |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    bad = 0
    for fb in sorted(b_dir.glob("*.jsonl.gz")):
        m = fb.name.removesuffix(".jsonl.gz")
        fa = a_dir / fb.name
        b = load(fb)
        a = load(fa) if fa.exists() else {}
        a_end = max((t["timestamp"] for t in a.values()), default=0)
        both = a.keys() & b.keys()
        only_a = a.keys() - b.keys()
        only_b = b.keys() - a.keys()
        only_b_old = [k for k in only_b if b[k]["timestamp"] <= a_end]
        differ = [k for k in both if a[k] != b[k]]
        ts = [t["timestamp"] for t in b.values()]
        span = (max(ts) - min(ts)) / 86400e6 if ts else 0
        bad += len(only_a) + len(only_b_old) + len(differ)
        print(f"| {m} | {len(a):,} | {len(b):,} | {len(both):,} | {len(only_a):,} | {len(only_b_old):,} | "
              f"{len(only_b) - len(only_b_old):,} | {len(differ):,} | {span:.1f} |")
    print(f"\n{'CONSISTENT' if bad == 0 else f'{bad:,} inconsistent rows'}")


if __name__ == "__main__":
    main()
