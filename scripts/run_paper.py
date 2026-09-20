#!/usr/bin/env python3
from __future__ import annotations

"""Unified Live Paper Trading & Replay Parity Runner for Arcus MM.
Fulfills Mandate v3 §11, §16 (consolidates run_paper_trader.py and run_live_paper_session.py).

- Streams public mainnet WebSocket frames through canonical SimEngine (ZERO orders placed).
- Persists all raw frames to data/live_paper/<session_id>/raw_stream.jsonl with SHA-256 manifest.
- Evaluates paired strategy configurations under $50 and $100 capital envelopes across primary markets.
- Performs post-session Bit-for-Bit Replay Parity Verification against a fresh SimEngine instance.
- Emits reports with strictly computed metrics.
"""

import argparse
import asyncio
import datetime
import json
import logging
from pathlib import Path
import sys
import time
from typing import Dict, List, Any, Optional

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.paper_trader import ArcusLivePaperTrader
from src.sim.engine import SimEvent, SimEventType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("paper_runner")

PRIMARY_MARKETS = ["BTC-USD", "ETH-USD", "SOL-USD", "HYPE-USD", "ZEC-USD", "NEAR-USD"]


async def run_paper_session(
    markets: List[str],
    duration_sec: int = 120,
    session_id: Optional[str] = None,
    output_dir: str = "data/live_paper",
) -> Dict[str, Any]:
    sid = session_id or f"session_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Initiating live paper trading session: {sid}")
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


def main():
    parser = argparse.ArgumentParser(description="Run Arcus MM Live Paper Trading & Replay Parity Verification")
    parser.add_argument("--duration", type=int, default=120, help="Session duration in seconds")
    parser.add_argument("--markets", nargs="*", default=PRIMARY_MARKETS, help="Markets to stream")
    parser.add_argument("--session-id", type=str, default=None, help="Custom session ID")
    parser.add_argument("--output-dir", type=str, default="data/live_paper", help="Session output directory")
    args = parser.parse_args()

    live_summary = asyncio.run(
        run_paper_session(
            markets=args.markets,
            duration_sec=args.duration,
            session_id=args.session_id,
            output_dir=args.output_dir,
        )
    )

    session_dir = Path(args.output_dir) / live_summary["session_id"]
    verify_session_replay_parity(session_dir, live_summary)


if __name__ == "__main__":
    main()
