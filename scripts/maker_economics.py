"""Model-free maker economics per market from recorded tape.

For every real trade, the passive (maker) side earned
    realized_spread(H) = side * (trade_price - mid[t + H]) / mid[t-] * 1e4   [bps]
with side = +1 when the maker sold (taker bought). Averaged over trades (notional
weighted), this is what an average resting order earned per fill before fees, with no
fill model involved. Arcus base-tier maker fee is 0 bps, so at the touch this is the net.

It splits as: realized = effective half-spread (vs pre-trade mid) - adverse selection.

Usage:
    .venv/bin/python scripts/maker_economics.py [--markets BTC-USD,SPY-USD] [--out research/maker_economics.md]
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.tape import GZ_ROOT, RAW_ROOT, load_bbo, load_trades, tape_days  # noqa: E402

EQUITY_LIKE = {"SPCX", "NVDA", "TSLA", "GOOGL", "AMD", "SLV", "GLD", "SPY", "QQQ"}
HORIZONS_S = (1, 5, 30, 60)
BLOCK_US = 5 * 60 * 1_000_000
RNG = np.random.default_rng(7)


def is_rth(ts_us: np.ndarray) -> np.ndarray:
    """US cash session, 13:30-20:00 UTC on weekdays (ignores holidays and DST shifts)."""
    secs = ts_us // 1_000_000
    tod = secs % 86400
    weekday = ((secs // 86400) + 3) % 7  # 1970-01-01 was a Thursday -> Mon=0
    return (weekday < 5) & (tod >= 13 * 3600 + 1800) & (tod < 20 * 3600)


def block_ratio_ci(block_id, num, den, n_boot=2000):
    """Mean of num/den with a 95% CI from a bootstrap over 5-minute blocks."""
    ub, inv = np.unique(block_id, return_inverse=True)
    bn = np.bincount(inv, weights=num)
    bd = np.bincount(inv, weights=den)
    est = bn.sum() / bd.sum()
    if len(ub) < 5:
        return est, np.nan, np.nan
    idx = RNG.integers(0, len(ub), size=(n_boot, len(ub)))
    boots = bn[idx].sum(1) / bd[idx].sum(1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return est, lo, hi


def spread_stats(bbo, mask_fn):
    dur = np.diff(bbo.ts, append=bbo.ts[-1]).astype(float)
    dur = np.minimum(dur, 60e6)  # cap gaps at 60 s so outages don't dominate
    keep = mask_fn(bbo.ts) & (dur > 0)
    if not keep.any():
        return None
    mid = bbo.mid[keep]
    sp_bps = (bbo.ask[keep] - bbo.bid[keep]) / mid * 1e4
    w = dur[keep]
    order = np.argsort(sp_bps)
    cw = np.cumsum(w[order]) / w.sum()
    med = sp_bps[order][np.searchsorted(cw, 0.5)]
    tick = float(np.min(np.diff(np.unique(np.round(np.concatenate([bbo.bid, bbo.ask]), 9)))))
    one_tick = np.abs((bbo.ask[keep] - bbo.bid[keep]) - tick) < tick * 0.01
    touch_usd = np.minimum(bbo.bid_sz[keep], bbo.ask_sz[keep]) * mid
    return {
        "hours": w.sum() / 3.6e9,
        "spread_med_bps": med,
        "spread_mean_bps": float(np.average(sp_bps, weights=w)),
        "pct_one_tick": float(np.average(one_tick, weights=w) * 100),
        "tick_bps": float(tick / np.median(mid) * 1e4),
        "touch_usd_med": float(np.median(touch_usd)),
    }


def analyse(market: str, days):
    bbo = load_bbo(market, days)
    tr = load_trades(market, days)
    if len(bbo.ts) < 100 or len(tr.ts) < 20:
        return []
    equity = market.split("-")[0] in EQUITY_LIKE
    regimes = [("RTH", lambda t: is_rth(t)), ("off-RTH", lambda t: ~is_rth(t))] if equity else [("24/7", lambda t: np.ones(len(t), bool))]

    i0 = bbo.asof(tr.ts)
    ok = i0 >= 0
    out = []
    for name, fn in regimes:
        m = ok & fn(tr.ts)
        if m.sum() < 20:
            continue
        ss = spread_stats(bbo, fn)
        ts, px, sz = tr.ts[m], tr.price[m], tr.size[m]
        sgn = np.where(tr.taker_buy[m], 1.0, -1.0)  # +1: maker sold
        m0 = bbo.mid[i0[m]]
        notional = px * sz
        at_touch = np.where(sgn > 0, px <= bbo.ask[i0[m]] + 1e-12, px >= bbo.bid[i0[m]] - 1e-12)
        blocks = ts // BLOCK_US
        row = {"market": market, "regime": name, "trades": int(m.sum()), **(ss or {})}
        row["trades_per_hr"] = row["trades"] / row["hours"] if ss else np.nan
        row["notional_per_hr"] = notional.sum() / row["hours"] if ss else np.nan
        row["pct_at_touch"] = float(at_touch.mean() * 100)
        eff = sgn * (px - m0) / m0 * 1e4
        row["eff_half_bps"] = float(np.average(eff, weights=notional))
        for h in HORIZONS_S:
            ih = bbo.asof(ts + h * 1_000_000)
            valid = ih >= 0
            mh = bbo.mid[ih]
            rs = sgn * (px - mh) / m0 * 1e4
            est, lo, hi = block_ratio_ci(blocks[valid], (rs * notional)[valid], notional[valid])
            row[f"rs{h}"], row[f"rs{h}_lo"], row[f"rs{h}_hi"] = est, lo, hi
        # who provides liquidity
        mk = tr.maker[m]
        u, inv = np.unique(mk, return_inverse=True)
        share = np.bincount(inv, weights=notional) / notional.sum()
        top = np.argsort(share)[::-1][:3]
        row["n_makers"] = len(u)
        row["top1_maker_share"] = float(share[top[0]] * 100)
        row["top3_maker_share"] = float(share[top].sum() * 100)
        ih = bbo.asof(ts + 30 * 1_000_000)
        rs30 = sgn * (px - bbo.mid[ih]) / m0 * 1e4
        sel = inv == top[0]
        row["top1_rs30"] = float(np.average(rs30[sel], weights=notional[sel]))
        out.append(row)
    return out


DEPTH_BUCKETS = [(0, 0, "at touch"), (1, 2, "touch+1..2"), (3, 9, "touch+3..9"), (10, 10**9, "touch+10+")]


def by_depth(market: str, days):
    """Maker realized spread (30 s) split by how many ticks beyond the pre-trade touch the fill printed."""
    bbo, tr = load_bbo(market, days), load_trades(market, days)
    i0 = bbo.asof(tr.ts)
    ok = i0 >= 0
    if ok.sum() < 20:
        return []
    ts, px, sz, i0 = tr.ts[ok], tr.price[ok], tr.size[ok], i0[ok]
    sgn = np.where(tr.taker_buy[ok], 1.0, -1.0)
    m0 = bbo.mid[i0]
    touch = np.where(sgn > 0, bbo.ask[i0], bbo.bid[i0])
    tick = float(np.min(np.diff(np.unique(np.round(np.concatenate([bbo.bid, bbo.ask]), 9)))))
    lvl = np.round(np.abs(px - touch) / tick).astype(int)
    n = px * sz
    eff = sgn * (px - m0) / m0 * 1e4
    rs = sgn * (px - bbo.mid[bbo.asof(ts + 30_000_000)]) / m0 * 1e4
    out = []
    for lo, hi, lab in DEPTH_BUCKETS:
        s = (lvl >= lo) & (lvl <= hi)
        if s.sum() < 10:
            continue
        est, clo, chi = block_ratio_ci((ts // BLOCK_US)[s], (rs * n)[s], n[s])
        out.append(dict(market=market, bucket=lab, fills=int(s.sum()), share=n[s].sum() / n.sum() * 100,
                        eff=np.average(eff[s], weights=n[s]), rs30=est, lo=clo, hi=chi, med_usd=float(np.median(n[s]))))
    return out


def fmt(x, nd=2):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default="")
    ap.add_argument("--out", default=str(ROOT / "research" / "maker_economics.md"))
    args = ap.parse_args()
    roots = [r for r in (RAW_ROOT, GZ_ROOT) if r.exists()]
    markets = args.markets.split(",") if args.markets else sorted(
        {m.name for r in roots for d in r.iterdir() if d.is_dir() for m in d.iterdir() if m.name.endswith("-USD")})
    all_days = sorted({d for mk in markets for d in tape_days(mk)})

    rows = []
    for mk in markets:
        print(f"{mk} ...", file=sys.stderr, flush=True)
        rows += analyse(mk, [RAW_ROOT / d / mk for d in tape_days(mk)])
    rows.sort(key=lambda r: -r["rs30"])

    span = f"{all_days[0]} → {all_days[-1]} (UTC)"
    L = [
        "# Maker economics from recorded tape",
        "",
        f"Generated by `scripts/maker_economics.py` on {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC. Tape: {span}.",
        "",
        "`rsH` = realized spread earned by the maker side of real trades, marked to mid H seconds later,",
        "notional-weighted, in bps; brackets are 95% CIs from a 5-minute block bootstrap.",
        "`eff½` = maker edge versus pre-trade mid. Adverse selection = `eff½ − rsH`.",
        "Arcus base tier: maker 0 bps, taker 2.25 bps. A maker round trip at the touch nets ≈ 2 × rs.",
        "",
        "| market | regime | hrs | trades/hr | $/hr | spread med (bps) | 1-tick % | tick (bps) | touch $ med | at-touch % | eff½ | rs1 | rs5 | rs30 | rs30 95% CI | rs60 | makers | top1 % | top3 % | top1 rs30 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        L.append("| " + " | ".join([
            r["market"], r["regime"], fmt(r.get("hours"), 1), fmt(r.get("trades_per_hr"), 0), fmt(r.get("notional_per_hr"), 0),
            fmt(r.get("spread_med_bps")), fmt(r.get("pct_one_tick"), 0), fmt(r.get("tick_bps"), 3), fmt(r.get("touch_usd_med"), 0),
            fmt(r["pct_at_touch"], 0), fmt(r["eff_half_bps"]), fmt(r["rs1"]), fmt(r["rs5"]), fmt(r["rs30"]),
            f"[{fmt(r['rs30_lo'])}, {fmt(r['rs30_hi'])}]", fmt(r["rs60"]), str(r["n_makers"]),
            fmt(r["top1_maker_share"], 0), fmt(r["top3_maker_share"], 0), fmt(r["top1_rs30"]),
        ]) + " |")
    L += ["", "## By depth of the maker's fill", "",
          "Ticks beyond the pre-trade best price at which the maker's order printed (all regimes pooled).", "",
          "| market | depth | fills | notional % | eff½ | rs30 | rs30 95% CI | median fill $ |",
          "|---|---|---:|---:|---:|---:|---|---:|"]
    for mk in markets:
        for r in by_depth(mk, [RAW_ROOT / d / mk for d in tape_days(mk)]):
            L.append(f"| {r['market']} | {r['bucket']} | {r['fills']} | {r['share']:.1f} | {fmt(r['eff'])} | {fmt(r['rs30'])} | "
                     f"[{fmt(r['lo'])}, {fmt(r['hi'])}] | {r['med_usd']:,.0f} |")
    Path(args.out).write_text("\n".join(L) + "\n")
    import csv
    with open(Path(args.out).with_suffix(".csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
