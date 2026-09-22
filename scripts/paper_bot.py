"""Paper trading bot: record live Arcus tape, score the frozen strategies on it, keep results.

Paper trading here = the backtest engine (src/replay.py) run on tape recorded live, a few
minutes behind real time. Using the same code path as the research means paper results and
backtests cannot drift apart. No orders are sent and no keys are needed: only public
WebSocket data is read (mainnet order lock stays on).

  run      start the recorder (restarted if it dies) and the scoring schedule
  score    score one UTC day now:  paper_bot.py score --day 2026-09-22 [--final]
  summary  rebuild data/paper/SUMMARY.md from stored day results

Everything is written under data/ (mount it as a volume; copy it to move results):
  data/raw/<day>/<market>/*.jsonl        live tape (today)
  data/compressed/<day>/...jsonl.gz      closed days, SHA-256 verified
  data/paper/days/<day>/<strategy>.<variant>.json   day result (final: true once the day closed)
  data/paper/days/<day>/<strategy>.<variant>.fills.csv
  data/paper/ledger.csv, data/paper/SUMMARY.md       all days, all strategies
  data/paper/status.json                              bot heartbeat
  data/logs/                                          recorder and bot logs
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from deep_quote_backtest import evaluate  # noqa: E402
from src.replay import DERIVED, Params, load_tape, simulate  # noqa: E402
from src.tape import RAW_ROOT, tape_days  # noqa: E402

DATA = ROOT / "data"
PAPER = DATA / "paper"
LOGS = DATA / "logs"
CONFIG = ROOT / "configs" / "paper.yaml"
DAY_NS = 86_400 * 10**9
log = logging.getLogger("paper_bot")


def load_config():
    return yaml.safe_load(CONFIG.read_text())


def market_specs():
    """Live /v1/markets, cached; falls back to the cache or a recorder snapshot when offline."""
    cache = PAPER / "markets.json"
    try:
        r = httpx.get("https://api.arcus.xyz/v1/markets", timeout=20)
        r.raise_for_status()
        items = r.json()
        items = items["markets"] if isinstance(items, dict) else items
        PAPER.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(items))
    except Exception as e:  # offline: use what we have
        log.warning("markets fetch failed (%s); using cached specs", e)
        if cache.exists():
            items = json.loads(cache.read_text())
        else:
            snap = sorted(RAW_ROOT.glob("*/rest_snapshots/markets_*.json"))[-1]
            items = json.loads(snap.read_text())
            items = items["markets"] if isinstance(items, dict) else items
    return {m["marketDisplayName"]: m for m in items}


def carried_units(day, stem, p):
    """Action budget left at the end of the previous final day (a real subaccount keeps it)."""
    prev = sorted(d.name for d in (PAPER / "days").glob("*") if d.name < day and (d / f"{stem}.json").exists())
    if prev:
        r = json.loads((PAPER / "days" / prev[-1] / f"{stem}.json").read_text())
        if r.get("final") and r.get("order_units_left") is not None:
            return r["order_units_left"], r["cancel_units_left"]
    return float(p["order_units"]), float(p["cancel_units"])


def params_for(strat, variant, cfg, spec, start_ns, end_ns, day):
    p = {**cfg["defaults"], **cfg["variants"][variant]}
    ou, cu = carried_units(day, f"{strat['id']}.{variant}", p)
    min_notional = max(float(spec["minOrderNotional"]), float(spec["minOrderSize"]) * float(spec["markPrice"]))
    return Params(depth_bps=float(strat["depth_bps"]), requote_bps=float(p["requote_bps"]), clip_usd=float(p["clip_usd"]),
                  max_pos_usd=float(p["max_pos_usd"]), rtt_ms=float(p["rtt_ms"]), maker_fee_bps=float(p["maker_fee_bps"]),
                  daily_stop_usd=float(p["daily_stop_usd"]), rate_limit=bool(p["rate_limit"]), order_units=ou, cancel_units=cu,
                  tick=float(spec["tickSize"]), step=float(spec["stepSize"]),
                  min_notional=min_notional, active=lambda ns: start_ns <= ns < end_ns)


def score_day(day: str, final: bool = False):
    """Replay every strategy x variant on one UTC day (previous day replays only to build the book)."""
    cfg = load_config()
    specs = market_specs()
    start_ns = int(dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp()) * 10**9
    end_ns = start_ns + DAY_NS
    prev = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat()
    out_dir = PAPER / "days" / day
    out_dir.mkdir(parents=True, exist_ok=True)
    for market in sorted({s["market"] for s in cfg["strategies"]}):
        days = [d for d in (prev, day) if d in tape_days(market)]
        if day not in days:
            log.warning("%s: no tape for %s", market, day)
            continue
        tp = load_tape(market, days)
        for strat in (s for s in cfg["strategies"] if s["market"] == market):
            for variant in cfg["variants"]:
                p = params_for(strat, variant, cfg, specs[market], start_ns, end_ns, day)
                res = simulate(tp, p)
                r = evaluate(tp, res, p, start_ns)
                row = dict(day=day, strategy=strat["id"], variant=variant, market=market, depth_bps=strat["depth_bps"],
                           role=strat.get("role", ""), final=final, fills=r["fills"], notional_usd=round(r["notional"], 2),
                           pnl_usd=round(float(r["pnl"]), 4), pnl_bps=None if np.isnan(r["pnl_bps"]) else round(float(r["pnl_bps"]), 3),
                           markout30_bps=None if np.isnan(r["rs30"]) else round(float(r["rs30"]), 3),
                           end_inventory_usd=round(float(r["end_pos_usd"]), 2), max_inventory_usd=round(r["max_pos_usd"], 2),
                           order_actions=r["actions"], throttled_actions=res.throttled, post_only_rejects=r["rejects"],
                           loss_stops=res.stops, order_units_left=round(res.order_units_left, 1),
                           cancel_units_left=round(res.cancel_units_left, 1),
                           hours_covered=round(r["hours"], 2), params={k: v for k, v in vars(p).items() if k not in ("active", "fair")},
                           scored_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
                stem = f"{strat['id']}.{variant}"
                (out_dir / f"{stem}.json").write_text(json.dumps(row, indent=1))
                with open(out_dir / f"{stem}.fills.csv", "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["time_utc", "side", "price", "qty", "mid_at_fill"])
                    for t, side, px, q, mid in res.fills:
                        w.writerow([dt.datetime.fromtimestamp(t / 1e9, dt.timezone.utc).isoformat(timespec="milliseconds"),
                                    "BUY" if side > 0 else "SELL", round(px, 10), round(q, 10), round(mid, 10)])
                log.info("%s %s %-8s fills=%d pnl=$%.2f%s", day, strat["id"], variant, r["fills"], r["pnl"], " FINAL" if final else "")
    write_summary()


def write_summary():
    rows = [json.loads(f.read_text()) for f in sorted((PAPER / "days").glob("*/*.json"))]
    if not rows:
        return
    keys = [k for k in rows[0] if k != "params"]
    with open(PAPER / "ledger.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    L = ["# Paper trading summary", "",
         f"Updated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/paper_bot.py`. "
         "Replay of live-recorded Arcus tape; no orders sent. Days marked * are still in progress.", "",
         "| strategy | variant | market | depth | days | days + | fills | notional $ | PnL $ | worst day $ |",
         "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    groups = {}
    for r in rows:
        groups.setdefault((r["strategy"], r["variant"]), []).append(r)
    for (sid, var), rs in sorted(groups.items()):
        pnl = [x["pnl_usd"] for x in rs]
        L.append(f"| {sid} | {var} | {rs[0]['market']} | {rs[0]['depth_bps']} | {len(rs)} | {sum(p > 0 for p in pnl)} | "
                 f"{sum(x['fills'] for x in rs)} | {sum(x['notional_usd'] for x in rs):,.0f} | {sum(pnl):.2f} | {min(pnl):.2f} |")
    days = sorted({r["day"] for r in rows})
    L += ["", "## PnL by day ($)", "", "| strategy.variant | " + " | ".join(d + ("" if all(x["final"] for x in rows if x["day"] == d) else "*") for d in days) + " |",
          "|---|" + "---:|" * len(days)]
    for (sid, var), rs in sorted(groups.items()):
        by = {x["day"]: x["pnl_usd"] for x in rs}
        L.append(f"| {sid}.{var} | " + " | ".join(f"{by[d]:.2f}" if d in by else "—" for d in days) + " |")
    (PAPER / "SUMMARY.md").write_text("\n".join(L) + "\n")


def close_day(day: str, cfg):
    """Final score, then compress the day's raw tape (verified) and drop stale parse caches."""
    score_day(day, final=True)
    if (RAW_ROOT / day).is_dir():
        from storage_manager import run_daily_close
        res = run_daily_close(day, keep_raw=False)
        log.info("compressed %s: %.0f MB -> %.0f MB", day, res["raw_mb"], res["compressed_mb"])
        shutil.rmtree(RAW_ROOT / day, ignore_errors=True)  # only empty dirs remain after verified deletes
    keep = dt.date.fromisoformat(day) - dt.timedelta(days=int(cfg["schedule"]["keep_parse_cache_days"]))
    for f in DERIVED.glob("*.npz"):
        if f.stem.rsplit("_", 1)[-1] < keep.isoformat():
            f.unlink()


def start_recorder(cfg):
    LOGS.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "ARCUS_ENVIRONMENT": "mainnet", "ARCUS_MAINNET_ORDER_LOCK": "true",
           "ARCUS_HEALTH_DIR": str(LOGS / "health"), "ARCUS_HEARTBEAT_FILE": str(DATA / "recorder_heartbeat.json")}
    cmd = [sys.executable, str(ROOT / "scripts" / "run_recorder.py"), "--duration", "0",
           "--markets", ",".join(cfg["markets_to_record"]), "--output-dir", str(RAW_ROOT),
           "--log-file", str(LOGS / "recorder.log")]
    log.info("starting recorder for %s", cfg["markets_to_record"])
    return subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=open(LOGS / "recorder.stderr", "a"))


def run():
    cfg = load_config()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # docker stop -> run finally, stop recorder
    for d in (RAW_ROOT, PAPER / "days", LOGS):  # fresh volume on a new machine
        d.mkdir(parents=True, exist_ok=True)
    rec = start_recorder(cfg)
    closed = {f.parent.name for f in (PAPER / "days").glob("*/*.json") if json.loads(f.read_text()).get("final")}
    last_score = 0.0
    hh, mm = map(int, cfg["schedule"]["close_after_utc"].split(":"))
    try:
        while True:
            if rec.poll() is not None:
                log.error("recorder exited with %s; restarting", rec.returncode)
                rec = start_recorder(cfg)
            now = dt.datetime.now(dt.timezone.utc)
            today = now.date().isoformat()
            # finalize every recorded day before today that is not closed yet (covers downtime)
            if now.hour * 60 + now.minute >= hh * 60 + mm:
                for d in [d for d in sorted({p.name for p in RAW_ROOT.iterdir() if p.is_dir()}) if d < today]:
                    if d not in closed:
                        try:
                            close_day(d, cfg)
                            closed.add(d)
                        except Exception:
                            log.exception("closing %s failed; will retry", d)
            if time.time() - last_score >= 60 * cfg["schedule"]["score_every_min"]:
                last_score = time.time()
                try:
                    score_day(today)
                except Exception:
                    log.exception("scoring %s failed; will retry", today)
            PAPER.mkdir(parents=True, exist_ok=True)
            (PAPER / "status.json").write_text(json.dumps({
                "updated_utc": now.isoformat(timespec="seconds"), "recorder_pid": rec.pid,
                "recorder_alive": rec.poll() is None, "markets": cfg["markets_to_record"],
                "disk_free_gb": round(shutil.disk_usage(DATA).free / 1e9, 1), "closed_days": sorted(closed)}, indent=1))
            time.sleep(30)
    finally:
        rec.terminate()
        try:
            rec.wait(timeout=20)
        except subprocess.TimeoutExpired:
            rec.kill()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    s = sub.add_parser("score")
    s.add_argument("--day", required=True)
    s.add_argument("--final", action="store_true")
    sub.add_parser("summary")
    a = ap.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOGS / "paper_bot.log")])
    if a.cmd == "run":
        run()
    elif a.cmd == "score":
        score_day(a.day, a.final)
    else:
        write_summary()


if __name__ == "__main__":
    main()
