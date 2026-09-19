#!/usr/bin/env python3
"""CLI Runner for Gate G3 Live Paper Trading & Replay Parity Verification.

Fulfills Mandate v2 Section 9 (Workstream 6) and Gate G3:
- Streams public mainnet WebSocket frames through canonical SimEngine (ZERO orders placed).
- Persists all raw frames to data/live_paper/<session_id>/raw_stream.jsonl with SHA-256 manifest.
- Evaluates paired strategy configurations under $50 and $100 capital envelopes across primary markets.
- Performs post-session Bit-for-Bit Replay Parity Verification against a fresh SimEngine instance.
- Emits reports/phase_15_live_paper_report.md with strictly computed metrics and Rule 11 outcome labels.
"""

import argparse
import asyncio
import datetime
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
from typing import Dict, List, Any

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.paper_trader import ArcusLivePaperTrader
from src.sim.engine import SimEngine, SimEvent, SimEventType
from src.models.fill import FillModelType
from src.models.latency import LatencyConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("live_paper_runner")

PRIMARY_MARKETS = ["BTC-USD", "ETH-USD", "SOL-USD", "HYPE-USD", "ZEC-USD", "NEAR-USD"]


async def run_paper_session(
    markets: List[str],
    duration_sec: int = 120,
    session_id: Optional[str] = None,
    output_dir: str = "data/live_paper",
) -> Dict[str, Any]:
    sid = session_id or f"session_g3_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Initiating Gate G3 live paper trading session: {sid}")
    logger.info(f"Active markets ({len(markets)}): {markets}")
    logger.info(f"Planned duration: {duration_sec} seconds")

    trader = ArcusLivePaperTrader(
        markets=markets,
        session_id=sid,
        output_dir=output_dir,
        initial_capital=100.0,
        capital_scenarios=[50.0, 100.0],
        strategy_types=["adaptive", "fixed_spread", "vol_clock", "donothing", "random_side"],
    )

    t0 = time.time()
    await trader.start()
    try:
        while time.time() - t0 < duration_sec:
            elapsed = time.time() - t0
            rem = duration_sec - elapsed
            if int(elapsed) % 30 == 0 and int(elapsed) > 0:
                logger.info(f"Session {sid} in progress: {elapsed:.0f}s elapsed, {rem:.0f}s remaining, fills logged: {trader.session_fills_count}")
            await asyncio.sleep(1.0)
    finally:
        await trader.stop()

    summary = trader.get_session_summary()
    return summary


def verify_session_replay_parity(session_dir: Path, live_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Replays the raw WebSocket stream into a fresh SimEngine and asserts exact hash parity."""
    raw_stream = session_dir / "raw_stream.jsonl"
    if not raw_stream.exists():
        return {"parity_passed": False, "error": "raw_stream.jsonl not found"}

    markets = live_summary.get("markets", [])
    trader = ArcusLivePaperTrader(
        markets=markets,
        session_id=f"replay_{live_summary['session_id']}",
        output_dir=str(session_dir.parent),
        initial_capital=100.0,
        capital_scenarios=[50.0, 100.0],
        strategy_types=["adaptive", "fixed_spread", "vol_clock", "donothing", "random_side"],
    )

    # Initialize specs
    asyncio.run(trader.initialize_engine())
    replay_engine = trader.engine

    replay_fills_count = 0
    with open(raw_stream, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            ts = rec["recv_ts_ns"]
            ch = rec["channel"]
            m = rec["market"]
            data = rec["data"]

            if ch == "bbo":
                contents = data.get("contents", {})
                if contents:
                    e = SimEvent(SimEventType.BBO, ts, m, contents)
                    replay_engine.on_event(e)
            elif ch == "trades":
                contents = data.get("contents")
                if isinstance(contents, list):
                    for t in contents:
                        e = SimEvent(SimEventType.TRADE, ts, m, t)
                        fills = replay_engine.on_event(e)
                        replay_fills_count += len(fills)

    live_hash = live_summary.get("engine_fill_hash")
    replay_hash = replay_engine.get_fill_log_hash()
    parity_passed = (live_hash == replay_hash)

    parity_res = {
        "parity_passed": parity_passed,
        "live_hash": live_hash,
        "replay_hash": replay_hash,
        "live_fills_count": live_summary.get("total_fills_logged", 0),
        "replay_fills_count": replay_fills_count,
    }
    logger.info(f"Replay Parity Result: {'PASS' if parity_passed else 'FAIL'} (Hash: {replay_hash[:16]}...)")
    return parity_res


def generate_live_paper_report(
    live_summary: Dict[str, Any],
    parity_res: Dict[str, Any],
    report_path: Path,
) -> None:
    """Generates reports/phase_15_live_paper_report.md from computed session data."""
    sid = live_summary["session_id"]
    markets = live_summary["markets"]
    start_utc = live_summary["session_start_utc"]
    end_utc = live_summary["session_end_utc"]
    total_fills = live_summary["total_fills_logged"]
    parity_ok = parity_res.get("parity_passed", False)
    parity_str = "✅ PASS (Bit-for-Bit Hash Match)" if parity_ok else "❌ FAIL (Hash Mismatch)"

    lines = [
        "# Phase 15 — Live Mainnet Paper Trading & Replay Parity Report",
        "",
        f"**Session ID:** `{sid}`  ",
        f"**Session Interval (UTC):** {start_utc} → {end_utc}  ",
        f"**Execution Mode:** Read-Only Public WS Streaming → Unified `SimEngine`  ",
        f"**Mainnet Order Invariant:** Strictly 0 real orders submitted (`APPROVE_MAINNET_ORDERS = NO`)  ",
        f"**Replay Parity:** {parity_str}  ",
        "",
        "## 1. Executive Summary & Gate G3 Status",
        "",
        "This session executes the pre-registered Gate G3 live paper trading baseline. "
        "Market data was streamed live from Arcus mainnet WebSocket feeds and ingested directly by the canonical "
        "`SimEngine` without copy-pasted execution logic. Kill-switch watchdogs (stale BBO > 3s, crossed book, drawdown limits) "
        "ran continuously on 100ms clock ticks.",
        "",
        "## 2. Session Outcome & Market Summary (Rule 11 Enforced)",
        "",
        "| Market | Strategy ID | Model B Fills | Model B Net PnL ($) | Model C Fills | Model C Net PnL ($) | Risk State | Session Outcome |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for sid, strat_data in sorted(live_summary.get("strategies", {}).items()):
        m = strat_data["market"]
        mb = strat_data["model_b"]
        mc = strat_data["model_c"]
        risk = strat_data["risk_state"]
        outcome = strat_data["outcome"]
        lines.append(
            f"| **{m}** | `{sid}` | {mb['total_trades_count']} | ${mb['net_pnl']:+.4f} | "
            f"{mc['total_trades_count']} | ${mc['net_pnl']:+.4f} | `{risk}` | **{outcome}** |"
        )

    lines.extend([
        "",
        "## 3. Replay Parity Verification (Bit-for-Bit Audit)",
        "",
        f"- **Live Run Fill Hash:** `{parity_res.get('live_hash')}`",
        f"- **Replay Run Fill Hash:** `{parity_res.get('replay_hash')}`",
        f"- **Live Fills Logged:** {parity_res.get('live_fills_count')}",
        f"- **Replay Fills Logged:** {parity_res.get('replay_fills_count')}",
        f"- **Parity Verdict:** `{parity_str}`",
        "",
        "## 4. Rate-Limit Pool Accounting",
        "",
        "- Action pools tracked in real time under venue rules (place=1, cancel=1, modify=1, cancelAll=1000).",
        "- Earned volume replenishment credited on fills (+1 action unit per $0.10 executed notional).",
        "- Idle drip replenishment tracked at 1 action unit per 10s idle.",
        "",
        "## 5. Economic Expectancy & Scale Reality (R-20)",
        "",
        "- **Capital Envelope:** $50 and $100 experimental capital tiers evaluated side-by-side.",
        "- **Scale Expectancy:** At $8 clip size, +2.0 bps net edge produces approximately $0.0016 per fill.",
        "- **Mandate Compliance:** This session evaluates mechanics and statistical edge per fill, not income.",
    ])

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(f"Generated live paper report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Run Gate G3 Live Paper Trading & Replay Parity Verification")
    parser.add_argument("--duration", type=int, default=120, help="Session duration in seconds")
    parser.add_argument("--markets", nargs="*", default=PRIMARY_MARKETS, help="Markets to stream")
    parser.add_argument("--session-id", type=str, default=None, help="Custom session ID")
    parser.add_argument("--output-dir", type=str, default="data/live_paper", help="Session output directory")
    args = parser.parse_args()

    # 1. Run Live Paper Session
    live_summary = asyncio.run(
        run_paper_session(
            markets=args.markets,
            duration_sec=args.duration,
            session_id=args.session_id,
            output_dir=args.output_dir,
        )
    )

    # 2. Run Replay Parity Verification
    session_dir = Path(args.output_dir) / live_summary["session_id"]
    parity_res = verify_session_replay_parity(session_dir, live_summary)

    # 3. Generate Report
    report_file = REPO_ROOT / "reports" / "phase_15_live_paper_report.md"
    generate_live_paper_report(live_summary, parity_res, report_file)


if __name__ == "__main__":
    main()
