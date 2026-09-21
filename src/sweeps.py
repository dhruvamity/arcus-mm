"""Maker realized spread by sweep depth from trade prints alone (no quote history needed).

Works on any venue's trade tape given (ts_us, price, qty, taker_buy, group). `group` identifies
one taker order: Arcus `sequenceNumber`, or for Binance aggTrades consecutive rows sharing
(transact_time, side). The first fill of a sweep sits at the touch; later fills are deeper.

Quotes are estimated from prints: ask ~ price of the latest taker buy, bid ~ price of the latest
taker sell (mid falls back to the last print when those cross). scripts/validate_sweep_proxy.py
checks this estimate against true BBO on recorded Arcus tape.
"""

from __future__ import annotations

import numpy as np

BUCKETS = [(-1e-9, 1e-9, "touch"), (1e-9, 2, "0-2 bps"), (2, 5, "2-5 bps"), (5, 10, "5-10 bps"), (10, 1e9, "10+ bps")]


def proxy_mid(ts, price, taker_buy):
    """Mid estimate *after* each print, from the latest taker-buy and taker-sell prices."""
    n = len(ts)
    ask = np.where(taker_buy, price, np.nan)
    bid = np.where(~taker_buy, price, np.nan)
    # forward fill
    idx_a = np.where(~np.isnan(ask), np.arange(n), 0)
    np.maximum.accumulate(idx_a, out=idx_a)
    idx_b = np.where(~np.isnan(bid), np.arange(n), 0)
    np.maximum.accumulate(idx_b, out=idx_b)
    a, b = price[idx_a], price[idx_b]
    have = (~np.isnan(ask[idx_a])) & (~np.isnan(bid[idx_b]))
    mid = np.where(have & (a >= b), (a + b) / 2, price)
    return mid


def sweep_table(ts, price, qty, taker_buy, group, horizon_s=30.0):
    """Per-print arrays: depth_bps beyond sweep start, maker realized spread (bps) at horizon, notional."""
    # within one taker order, walk the book from the touch outward (sources differ in row order:
    # the WS feed is in match order, REST history is newest-first)
    walk = np.where(taker_buy, price, -price)
    order = np.lexsort((walk, group, ts))
    ts, price, qty, taker_buy, group = ts[order], price[order], qty[order], taker_buy[order], group[order]
    mid_after = proxy_mid(ts, price, taker_buy)
    new = np.ones(len(ts), bool)
    new[1:] = group[1:] != group[:-1]
    start = np.maximum.accumulate(np.where(new, np.arange(len(ts)), 0))
    first_px = price[start]
    # mid before the sweep = proxy after the print preceding the sweep's first print
    pre = np.clip(start - 1, 0, None)
    m0 = mid_after[pre]
    sgn = np.where(taker_buy, 1.0, -1.0)  # +1: maker sold
    depth = sgn * (price - first_px) / m0 * 1e4
    j = np.searchsorted(ts, ts + int(horizon_s * 1e6), side="right") - 1
    rs = sgn * (price - mid_after[j]) / m0 * 1e4
    valid = (start > 0) & (ts + int(horizon_s * 1e6) <= ts[-1])  # tape must cover the horizon
    return ts[valid], depth[valid], rs[valid], (price * qty)[valid]


def by_bucket(depth, rs, notional):
    out = []
    for lo, hi, lab in BUCKETS:
        s = (depth > lo) & (depth <= hi) if lo >= 0 else (np.abs(depth) <= hi)
        if s.sum() >= 10:
            out.append((lab, int(s.sum()), float(np.average(rs[s], weights=notional[s]))))
    return out
