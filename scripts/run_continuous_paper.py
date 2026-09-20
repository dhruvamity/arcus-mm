#!/usr/bin/env python3
from __future__ import annotations

"""WS-M: Continuous 24/7 Crypto Paper Trading Daemon for Arcus MM.
Fulfills Mandate v4 Section 3a and Section 6.

- Streams live mainnet public WebSocket feeds across 11 crypto instruments:
  BTC-USD, ETH-USD, SOL-USD, HYPE-USD, ZEC-USD, NEAR-USD, LIT-USD, UNI-USD, XRP-USD, AAVE-USD, CASHCAT-USD
- Zero real orders placed (read-only live mainnet feed into canonical SimEngine).
- Runs continuously through Friday 2026-09-25 parameter freeze.
- Emits raw stream to data/live_paper/<session_id>/raw_stream.jsonl.
- Periodically appends daily rollups to reports/paper_session_daily.md.
- Generates SHA-256 manifests and supports daily Bit-for-Bit Replay Parity.
"""

import argparse
import asyncio
import datetime
import json
import logging
from pathlib import Path
import sys
import time
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.paper_trader import ArcusLivePaperTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("continuous_paper")

CRYPTO_MARKETS_11 = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "HYPE-USD",
    "ZEC-USD",
    "NEAR-USD",
    "LIT-USD",
    "UNI-USD",
    "XRP-USD",
    "AAVE-USD",
    "CASHCAT-USD",
]


def ensure_daily_report_header(report_path: Path) -> None:
    if not report_path.exists():
        header = [
            "# Arcus MM — Daily Live Paper Trading Rollup",
            "",
            "> [!IMPORTANT]",
            "> Continuous read-only paper evaluation on live mainnet WebSocket stream.",
            "> ZERO real orders placed. Evaluated under Model B (volume-depleting FIFO) and Model C (trade-through floor).",
            "",
            "| Timestamp (UTC) | Session ID | Market | Strategy ID | Model B Net PnL ($) | Model B Fills | Model C Net PnL ($) | Model C Fills | Risk State | Session Outcome |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        report_path.write_text("\n".join(header) + "\n", encoding="utf-8")


def append_daily_rollup(report_path: Path, session_id: str, trader: ArcusLivePaperTrader) -> None:
    """Appends snapshot of all strategy metrics to reports/paper_session_daily.md."""
    ensure_daily_report_header(report_path)
    summary = trader.get_session_summary()
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    rows = []
    strategies = summary.get("strategies", {})
    for sid, s_data in sorted(strategies.items()):
        m = s_data.get("market", "")
        sum_b = s_data.get("model_b", {})
        sum_c = s_data.get("model_c", {})
        risk = s_data.get("risk_state", "NORMAL")
        outcome = s_data.get("outcome", "SESSION: INSUFFICIENT")

        pnl_b = sum_b.get("net_pnl", 0.0)
        fills_b = sum_b.get("total_trades_count", 0)
        pnl_c = sum_c.get("net_pnl", 0.0)
        fills_c = sum_c.get("total_trades_count", 0)

        rows.append(
            f"| `{now_utc}` | `{session_id}` | **{m}** | `{sid}` | ${pnl_b:+.4f} | {fills_b} | ${pnl_c:+.4f} | {fills_c} | `{risk}` | **`{outcome}`** |"
        )

    if rows:
        with open(report_path, "a", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
        logger.info(f"Appended {len(rows)} strategy rollups to {report_path}")


async def run_continuous_crypto_paper(
    markets: Optional[List[str]] = None,
    duration_sec: int = 0,  # 0 = run until interrupted / freeze
    output_dir: str = "data/live_paper",
    rollup_interval_sec: int = 3600,  # default: hourly rollup
) -> None:
    selected_markets = markets or CRYPTO_MARKETS_11
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    session_id = f"crypto_continuous_{now_str}"
    report_path = REPO_ROOT / "reports" / "paper_session_daily.md"
    heartbeat_path = Path(output_dir) / session_id / "heartbeat.json"

    logger.info(f"=== Initiating WS-M Continuous Crypto Paper Trading Session: {session_id} ===")
    logger.info(f"Markets ({len(selected_markets)}): {selected_markets}")

    trader = ArcusLivePaperTrader(
        markets=selected_markets,
        session_id=session_id,
        output_dir=output_dir,
        initial_capital=100.0,
        capital_scenarios=[50.0, 100.0],
        strategy_types=["adaptive", "fixed_spread", "vol_clock", "donothing", "random_side"],
        enable_crypto_pause=False,  # 24/7 crypto execution
    )

    t0 = time.time()
    last_rollup = t0
    await trader.start()

    try:
        while True:
            t_curr = time.time()
            elapsed = t_curr - t0

            # Heartbeat update
            heartbeat_data = {
                "session_id": session_id,
                "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "uptime_seconds": int(elapsed),
                "fills_count": trader.session_fills_count,
                "markets_count": len(selected_markets),
                "is_running": trader._running,
            }
            heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            heartbeat_path.write_text(json.dumps(heartbeat_data), encoding="utf-8")

            # Check periodic rollup
            if t_curr - last_rollup >= rollup_interval_sec:
                append_daily_rollup(report_path, session_id, trader)
                last_rollup = t_curr

            if duration_sec > 0 and elapsed >= duration_sec:
                logger.info(f"Continuous paper duration limit reached ({duration_sec}s). Stopping.")
                break

            await asyncio.sleep(5.0)
    finally:
        await trader.stop()
        append_daily_rollup(report_path, session_id, trader)
        logger.info(f"=== Session {session_id} finalized with SHA-256 manifest ===")


def main():
    parser = argparse.ArgumentParser(description="Run WS-M Continuous Crypto Live Paper Trading Daemon")
    parser.add_argument("--duration", type=int, default=0, help="Duration in seconds (0 = run indefinitely)")
    parser.add_argument("--rollup-interval", type=int, default=3600, help="Interval in seconds to append daily rollups")
    parser.add_argument("--markets", nargs="*", default=None, help="Explicit market list")
    args = parser.parse_args()

    asyncio.run(
        run_continuous_crypto_paper(
            markets=args.markets,
            duration_sec=args.duration,
            rollup_interval_sec=args.rollup_interval,
        )
    )


if __name__ == "__main__":
    main()
