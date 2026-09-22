"""Replay "deep" two-sided quoting on recorded L2 tape and report net economics.

Rule: rest one post-only bid at mid*(1 - d) and one ask at mid*(1 + d) (d in bps), move a
quote only when its target drifts by >= requote_bps, stop quoting the side that would
grow inventory past max_pos_usd. Latency = RTT on every place/cancel. See src/replay.py
for fill rules.

Usage:
    .venv/bin/python scripts/deep_quote_backtest.py --markets SPY-USD,HYPE-USD --depths 2,3,5,8,12
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.replay import BBO, Params, load_tape, simulate  # noqa: E402
from src.tape import RAW_ROOT, tape_days  # noqa: E402

EQUITY_LIKE = {"SPCX", "NVDA", "TSLA", "GOOGL", "AMD", "SLV", "GLD", "SPY", "QQQ"}


def market_specs():
    snaps = sorted(RAW_ROOT.glob("*/rest_snapshots/markets_*.json"))
    items = json.loads(snaps[-1].read_text())
    items = items["markets"] if isinstance(items, dict) else items
    return {m["marketDisplayName"]: m for m in items}


def rth(ns: int) -> bool:
    s = ns // 1_000_000_000
    tod, wd = s % 86400, ((s // 86400) + 3) % 7
    return wd < 5 and 48600 <= tod < 72000


def evaluate(tp, res, params, start_ns=0):
    """Equity path, per-day PnL, markouts from fills + BBO mids."""
    b = tp["kind"] == BBO
    t_b = tp["recv"][b]
    mid_b = (tp["px"][b] + tp["sz"][b]) / 2
    f = np.array([x[:6] for x in res.fills], dtype=float).reshape(-1, 6)  # t, side, px, qty, mid, fee
    hours = (t_b[-1] - max(t_b[0], start_ns)) / 3.6e12
    out = {"fills": len(f), "hours": hours, "actions": res.actions, "rejects": res.rejects,
           "max_pos_usd": res.max_abs_pos_usd}
    notional = float((f[:, 2] * f[:, 3]).sum()) if len(f) else 0.0
    pnl = res.cash + res.final_pos * res.final_mid
    out.update(notional=notional, pnl=pnl, pnl_bps=pnl / notional * 1e4 if notional else np.nan,
               end_pos_usd=res.final_pos * res.final_mid)
    if len(f):
        ts = f[:, 0].astype(np.int64)
        j = np.searchsorted(t_b, ts + 30_000_000_000) - 1
        mk = f[:, 1] * (mid_b[j] - f[:, 2]) / f[:, 4] * 1e4  # +: price moved our way
        out["rs30"] = float(np.average(mk, weights=f[:, 2] * f[:, 3]))
    else:
        out["rs30"] = np.nan
    # daily equity marks (UTC days)
    day_ns = 86400 * 10**9
    days = np.arange(max(t_b[0], start_ns) // day_ns, t_b[-1] // day_ns + 1)
    cash = pos = 0.0
    k = 0
    eq_prev = 0.0
    daily = []
    for d in days:
        end = (d + 1) * day_ns
        while k < len(f) and f[k, 0] < end:
            s, p_, q = f[k, 1], f[k, 2], f[k, 3]
            pos += s * q
            cash -= s * q * p_ + f[k, 5]
            k += 1
        j = np.searchsorted(t_b, end) - 1
        eq = cash + pos * mid_b[j]
        daily.append(eq - eq_prev)
        eq_prev = eq
    out["daily"] = daily
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default="SPY-USD,HYPE-USD,NVDA-USD,GLD-USD,LIT-USD,QQQ-USD,ETH-USD,BTC-USD")
    ap.add_argument("--depths", default="1,2,3,5,8,12,20")
    ap.add_argument("--requote", type=float, default=1.0)
    ap.add_argument("--clip", type=float, default=25.0)
    ap.add_argument("--max-pos", type=float, default=100.0)
    ap.add_argument("--rtt", type=float, default=200.0)
    ap.add_argument("--skew", type=float, default=0.0, help="bps shift toward flat at max inventory")
    ap.add_argument("--maker-fee", type=float, default=0.0)
    ap.add_argument("--stop-usd", type=float, default=0.0, help="daily loss stop per market ($, 0 = off)")
    ap.add_argument("--rate-limit", action="store_true", help="enforce the Arcus per-subaccount action budget")
    ap.add_argument("--order-units", type=float, default=20_000.0, help="starting order-pool headroom")
    ap.add_argument("--cancel-units", type=float, default=40_000.0, help="starting cancel-pool headroom")
    ap.add_argument("--exit-mode", default="mid", choices=["mid", "touch"], help="where the inventory-closing quote rests")
    ap.add_argument("--stop-loss-bps", type=float, default=0.0, help="taker-flatten when mid is this far against entry (0 = off)")
    ap.add_argument("--rth-only", action="store_true", help="equity-like markets quote only 13:30-20:00 UTC weekdays")
    ap.add_argument("--from-day", default="", help="YYYY-MM-DD: quote only from this UTC date (prior day replays as book warm-up)")
    ap.add_argument("--to-day", default="", help="YYYY-MM-DD: last UTC date of tape to use (inclusive)")
    ap.add_argument("--out", default=str(ROOT / "research" / "deep_quote_backtest.md"))
    a = ap.parse_args()

    specs = market_specs()
    rows = []
    for m in a.markets.split(","):
        s = specs[m]
        print(f"{m}: loading tape ...", file=sys.stderr, flush=True)
        days = tape_days(m)
        start_ns = 0
        if a.from_day:
            start_ns = int(dt.datetime.fromisoformat(a.from_day).replace(tzinfo=dt.timezone.utc).timestamp()) * 10**9
            days = [d for d in days if d >= (dt.date.fromisoformat(a.from_day) - dt.timedelta(days=1)).isoformat()]
        if a.to_day:
            days = [d for d in days if d <= a.to_day]
        tp = load_tape(m, days)
        eq = m.split("-")[0] in EQUITY_LIKE
        gate_rth = a.rth_only and eq

        def active(ns, start_ns=start_ns, gate_rth=gate_rth):
            return ns >= start_ns and (not gate_rth or rth(ns))
        for d in [float(x) for x in a.depths.split(",")]:
            p = Params(depth_bps=d, exit_mode=a.exit_mode, stop_loss_bps=a.stop_loss_bps, requote_bps=a.requote, skew_bps=a.skew, daily_stop_usd=a.stop_usd, rate_limit=a.rate_limit,
                       order_units=a.order_units, cancel_units=a.cancel_units, clip_usd=a.clip, max_pos_usd=a.max_pos, rtt_ms=a.rtt,
                       maker_fee_bps=a.maker_fee, tick=float(s["tickSize"]), step=float(s["stepSize"]),
                       min_notional=max(float(s["minOrderNotional"]), float(s["minOrderSize"]) * float(s["markPrice"])),
                       active=active if (start_ns or gate_rth) else None)
            r = evaluate(tp, simulate(tp, p), p, start_ns)
            r.update(market=m, depth=d)
            rows.append(r)
            print(f"  d={d:>5} fills={r['fills']:5d} notional=${r['notional']:>10,.0f} pnl=${r['pnl']:8.2f} "
                  f"({r['pnl_bps']:6.2f} bps) rs30={r['rs30']:6.2f} days={[round(float(x), 2) for x in r['daily']]}",
                  file=sys.stderr, flush=True)

    L = ["# Deep-quote replay on recorded L2 tape", "",
         f"Generated by `scripts/deep_quote_backtest.py` on {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC.",
         f"Params: clip ${a.clip:g}, max inventory ${a.max_pos:g}, requote ≥{a.requote:g} bps, RTT {a.rtt:g} ms, "
         f"skew {a.skew:g} bps, daily stop ${a.stop_usd:g}, exit {a.exit_mode}, stop-loss {a.stop_loss_bps:g} bps, "
         f"{f'rate limit on (start {a.order_units:g}/{a.cancel_units:g} units)' if a.rate_limit else 'no rate limit'}, maker fee {a.maker_fee:g} bps, {'RTH-only for equity perps' if a.rth_only else 'all hours'}"
         f"{f', quoting from {a.from_day} UTC' if a.from_day else ''}.",
         "PnL is net of maker fees and marked to mid at the end of the tape. `rs30` = fill markout at 30 s.",
         "", "| market | depth (bps) | hours | fills | fills/hr | notional $ | PnL $ | PnL bps/notional | rs30 | +days/days | daily PnL $ | max inv $ | actions/hr | pool units/hr net |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|"]
    for r in rows:
        pos_days = sum(1 for x in r["daily"] if x > 0)
        # order pool: each place costs 1 order unit, each cancel 1 cancel unit; refill 10 units per $ filled
        pool_net = (r["actions"] / 2 - 10 * r["notional"]) / r["hours"] if r["hours"] else np.nan
        L.append(f"| {r['market']} | {r['depth']:g} | {r['hours']:.1f} | {r['fills']} | {r['fills']/r['hours']:.1f} | "
                 f"{r['notional']:,.0f} | {r['pnl']:.2f} | {r['pnl_bps']:.2f} | {r['rs30']:.2f} | {pos_days}/{len(r['daily'])} | "
                 f"{', '.join(f'{x:.2f}' for x in r['daily'])} | {r['max_pos_usd']:.0f} | {r['actions']/r['hours']:.0f} | {pool_net:,.0f} |")
    Path(a.out).write_text("\n".join(L) + "\n")
    print(f"wrote {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
