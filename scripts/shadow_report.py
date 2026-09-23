"""Compare a dry-run shadow session of the live trader with the backtest replay of the same window.

The shadow (scripts/run_live.py without --live, shadow_fills: true) runs the real live code on
the mainnet feed and books a fill whenever a real trade prints strictly through one of its
resting prices. Here the replay (src/replay.py) is run on the tape the recorder captured over
the same window, twice:

  replay-tt     same fill rule as the shadow (trade-through only): should match it closely
  replay-queue  the research model (also fills at our own price once the queue ahead is gone)

If shadow and replay-tt agree, the live code does what the backtest assumed; the gap between
replay-tt and replay-queue is how much of the edge depends on queue fills a real order may or
may not get.

    .venv/bin/python scripts/shadow_report.py --log-dir data/live/shadow-2026-09-23
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import httpx
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.replay import Params, load_tape, simulate  # noqa: E402
from src.tape import tape_days  # noqa: E402


def ts_ns(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp() * 1e9)


def specs():
    items = httpx.get("https://api.arcus.xyz/v1/markets", timeout=20).json()
    items = items["markets"] if isinstance(items, dict) else items
    return {m["marketDisplayName"]: m for m in items}


def shadow_side(events, market, mark):
    fills = [e for e in events if e["kind"] == "fill" and e.get("market") == market and e.get("shadow")]
    pos = sum((1 if f["side"] == "BUY" else -1) * f["qty"] for f in fills)
    cash = -sum((1 if f["side"] == "BUY" else -1) * f["qty"] * f["price"] for f in fills)
    notional = sum(f["qty"] * f["price"] for f in fills)
    edge = [(f["mid"] - f["price"]) / f["mid"] * 1e4 * (1 if f["side"] == "BUY" else -1) for f in fills if f.get("mid")]
    return dict(fills=len(fills), notional=notional, pnl=cash + pos * mark, end_pos_usd=pos * mark,
                edge_bps=float(np.mean(edge)) if edge else float("nan"),
                times=[(ts_ns(f["ts_utc"]), 1 if f["side"] == "BUY" else -1, f["price"]) for f in fills])


def replay_side(tp, p, mark):
    r = simulate(tp, p)
    notional = sum(q * px for _, _, px, q, *_ in r.fills)
    edge = [(mid - px) / mid * 1e4 * s for _, s, px, _, mid, *_ in r.fills]
    return dict(fills=len(r.fills), notional=notional, pnl=r.cash + r.final_pos * mark, end_pos_usd=r.final_pos * mark,
                edge_bps=float(np.mean(edge)) if edge else float("nan"),
                times=[(t, s, px) for t, s, px, *_ in r.fills], throttled=r.throttled)


def matched(a, b, tol_ns):
    """Fills in a that have a same-side, same-price fill in b within tol_ns."""
    return sum(any(s == s2 and abs(px - px2) < 1e-9 and abs(t - t2) <= tol_ns for t2, s2, px2 in b) for t, s, px in a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--config", default=str(ROOT / "configs" / "live.yaml"))
    ap.add_argument("--rtt-ms", type=float, default=250.0, help="replay latency (the shadow's shadow_latency_ms)")
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.config).read_text())
    log_dir = Path(a.log_dir)
    events = [json.loads(line) for line in open(log_dir / "events.jsonl")]
    starts = [e for e in events if e["kind"] == "started"]
    start_ns, end_ns = ts_ns(starts[-1]["ts_utc"]), ts_ns(events[-1]["ts_utc"])
    events = [e for e in events if ts_ns(e["ts_utc"]) >= start_ns]
    status = json.loads((log_dir / "status.json").read_text())
    sp = specs()
    hours = (end_ns - start_ns) / 3.6e12
    print(f"window {starts[-1]['ts_utc'][:19]} -> {events[-1]['ts_utc'][:19]} UTC ({hours:.2f} h), replay rtt {a.rtt_ms:g} ms\n")
    print(f"{'market':9} {'run':13} {'fills':>6} {'notional$':>10} {'pnl$':>8} {'pnl bps':>8} {'edge bps':>9} {'end inv$':>9}")
    for m in cfg["markets"]:
        mk = m["market"]
        q = status["markets"][mk]
        mark = (q["bid"] + q["ask"]) / 2
        day0 = dt.datetime.fromtimestamp(start_ns / 1e9, dt.timezone.utc).date()
        day1 = dt.datetime.fromtimestamp(end_ns / 1e9, dt.timezone.utc).date()
        want = {(day0 - dt.timedelta(days=1)).isoformat()} | {
            (day0 + dt.timedelta(days=i)).isoformat() for i in range((day1 - day0).days + 1)}
        tp = load_tape(mk, [d for d in tape_days(mk) if d in want])
        keep = tp["recv"] <= end_ns
        tp = {k: v[keep] for k, v in tp.items()}
        s = sp[mk]
        base = dict(depth_bps=float(m["depth_bps"]), requote_bps=float(cfg["requote_bps"]),
                    clip_usd=float(m.get("clip_usd", cfg["clip_usd"])), max_pos_usd=float(m.get("max_pos_usd", cfg["max_pos_usd"])),
                    daily_stop_usd=float(m.get("daily_stop_usd", cfg.get("daily_stop_usd", 0))), rtt_ms=a.rtt_ms,
                    rate_limit=True, tick=float(s["tickSize"]), step=float(s["stepSize"]),
                    min_notional=max(float(s["minOrderNotional"]), float(s["minOrderSize"]) * float(s["markPrice"])),
                    active=lambda ns: start_ns <= ns < end_ns)
        runs = {"shadow": shadow_side(events, mk, mark),
                "replay-tt": replay_side(tp, Params(**base, trade_through_only=True), mark),
                "replay-queue": replay_side(tp, Params(**base), mark)}
        for name, r in runs.items():
            bps = r["pnl"] / r["notional"] * 1e4 if r["notional"] else float("nan")
            print(f"{mk:9} {name:13} {r['fills']:6d} {r['notional']:10.2f} {r['pnl']:8.3f} {bps:8.2f} "
                  f"{r['edge_bps']:9.2f} {r['end_pos_usd']:9.2f}")
        sh, tt = runs["shadow"]["times"], runs["replay-tt"]["times"]
        print(f"{'':9} match: {matched(sh, tt, 2 * 10**9)}/{len(sh)} shadow fills have a replay-tt twin within 2 s, "
              f"{matched(tt, sh, 2 * 10**9)}/{len(tt)} the other way\n")


if __name__ == "__main__":
    main()
