"""Multi-Market Live Mainnet Paper Trading Runner.

Fulfills Phase 15 requirements from prompt.md:
- Runs 8–10 markets simultaneously across categories:
  Crypto (HYPE, ZEC, NEAR, UNI, LIT), Equities (SPCX, NVDA, TSLA), Commodity/Index (SLV, SPY), Controls (BTC, ETH, SOL).
- Zero real mainnet orders (strict public streaming + local paper execution).
- Dual Model C (gating) and Model B (shadow) fill logging.
- Runs both $50 and $100 capital scenarios.
- Records all raw WS frames for post-session replay parity verification.
- Generates reports/phase_15_live_paper_report.md.
"""

import argparse
import asyncio
import datetime
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.paper_trader import ArcusLivePaperTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("paper_runner")

# Market specifications
MARKET_METADATA = {
    "HYPE-USD": {"tick_size": 0.001, "step_size": 0.000001, "asset_class": "crypto", "clip": 9.24},
    "ZEC-USD": {"tick_size": 0.001, "step_size": 0.000001, "asset_class": "crypto", "clip": 15.34},
    "NEAR-USD": {"tick_size": 0.001, "step_size": 0.000001, "asset_class": "crypto", "clip": 5.0},
    "UNI-USD": {"tick_size": 0.001, "step_size": 0.000001, "asset_class": "crypto", "clip": 5.0},
    "LIT-USD": {"tick_size": 0.0001, "step_size": 0.00001, "asset_class": "crypto", "clip": 5.0},
    "SPCX-USD": {"tick_size": 0.01, "step_size": 0.0000001, "asset_class": "equities", "clip": 5.0},
    "NVDA-USD": {"tick_size": 0.01, "step_size": 0.0000001, "asset_class": "equities", "clip": 5.0},
    "TSLA-USD": {"tick_size": 0.01, "step_size": 0.0000001, "asset_class": "equities", "clip": 5.0},
    "SLV-USD": {"tick_size": 0.01, "step_size": 0.0000001, "asset_class": "commodities", "clip": 5.0},
    "BTC-USD": {"tick_size": 0.1, "step_size": 0.00000001, "asset_class": "crypto", "clip": 5.0},
}


def generate_paper_report(
    session_id: str,
    duration_secs: float,
    results_100: Dict[str, Dict[str, Any]],
    results_50: Dict[str, Dict[str, Any]],
    output_md: Path,
):
    """Generates the Phase 15 Live Paper Trading Report."""
    hours = max(0.01, duration_secs / 3600.0)
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md_lines = [
        "# Phase 15 — Live Mainnet Paper Trading Report",
        "",
        f"**Date:** {now_str}  ",
        f"**Session ID:** `{session_id}`  ",
        f"**Session Duration:** {hours:.2f} hours ({duration_secs:.0f} seconds)  ",
        f"**Execution Mode:** Live Public Mainnet Feeds (ZERO REAL MAINNET ORDERS)  ",
        "",
        "## 1. Executive Summary",
        "",
        "This session evaluated live passive market making execution across simultaneous candidates and control markets.",
        "Both **Model C (Conservative Gating)** and **Model B (Queue-Aware Shadow)** were logged in parallel.",
        "All raw WebSocket frames were recorded to enable post-session replay parity testing.",
        "",
        "## 2. Multi-Market Performance Matrix ($100 Research Capital Scenario)",
        "",
        "| Market | Asset Class | Model C Fills | Model C PnL ($) | Model C Net (%) | Model B Fills | Model B PnL ($) | Max DD (%) | Fill Rate (/hr) | Verdict |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for m, r_c in sorted(results_100.items()):
        sum_c = r_c["summary_c"]
        sum_b = r_c["summary_b"]
        fills_c = sum_c["total_trades_count"]
        pnl_c = sum_c["net_pnl"]
        pct_c = sum_c["net_pnl_pct"]
        fills_b = sum_b["total_trades_count"]
        pnl_b = sum_b["net_pnl"]
        dd = sum_c["max_drawdown_pct"]
        fill_rate = fills_c / hours

        if fills_c < 30:
            verdict = "INSUFFICIENT DATA (<30 fills)"
        elif pnl_c > 0:
            verdict = "PAPER OBSERVATION (Positive Net, Pending 5-Day OOS Protocol)"
        else:
            verdict = "PAPER OBSERVATION (Non-Positive Net)"

        md_lines.append(
            f"| **{m}** | {r_c['asset_class']} | {fills_c} | ${pnl_c:+.2f} | {pct_c:+.2f}% | "
            f"{fills_b} | ${pnl_b:+.2f} | {dd:.2f}% | {fill_rate:.1f}/hr | **{verdict}** |"
        )

    md_lines.extend([
        "",
        "## 3. Capital Scaling Comparison ($50 vs $100 Scenario)",
        "",
        "| Market | Min Clip ($) | $100 Capital Net PnL ($) | $50 Capital Net PnL ($) | Capital Dependent? |",
        "|---|---|---|---|---|",
    ])

    for m in sorted(results_100.keys()):
        pnl_100 = results_100[m]["summary_c"]["net_pnl"]
        pnl_50 = results_50.get(m, {}).get("summary_c", {}).get("net_pnl", 0.0)
        clip = MARKET_METADATA.get(m, {}).get("clip", 5.0)
        cap_dep = "YES" if (pnl_100 > 0 and pnl_50 <= 0) else "NO"
        md_lines.append(f"| **{m}** | ${clip:.2f} | ${pnl_100:+.2f} | ${pnl_50:+.2f} | {cap_dep} |")

    md_lines.extend([
        "",
        "## 4. Replay Parity Verification",
        "",
        "All incoming WebSocket messages were recorded locally.",
        "Replay parity requires that replaying persisted ticks through the deterministic backtester produces identical fills and equity curves within numerical precision.",
    ])

    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    logger.info(f"Generated Phase 15 paper report: {output_md}")


async def main():
    parser = argparse.ArgumentParser(description="Run Arcus Multi-Market Live Paper Trader")
    parser.add_argument(
        "--markets",
        type=str,
        default="HYPE-USD,ZEC-USD,NEAR-USD,UNI-USD,LIT-USD,SPCX-USD,NVDA-USD,TSLA-USD,SLV-USD,BTC-USD",
        help="Comma-separated list of markets to paper trade",
    )
    parser.add_argument("--duration", type=float, default=60.0, help="Duration in seconds")
    parser.add_argument("--output-md", type=str, default="reports/phase_15_live_paper_report.md")
    args = parser.parse_args()

    market_list = [m.strip() for m in args.markets.split(",") if m.strip()]
    session_id = f"paper_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"Starting Multi-Market Paper Session [{session_id}] for {len(market_list)} markets across $50 and $100 scenarios...")

    traders_100: Dict[str, ArcusLivePaperTrader] = {}
    traders_50: Dict[str, ArcusLivePaperTrader] = {}

    for m in market_list:
        specs = MARKET_METADATA.get(m, {"tick_size": 0.001, "step_size": 0.000001, "asset_class": "crypto", "clip": 5.0})
        t100 = ArcusLivePaperTrader(
            market=m,
            tick_size=specs["tick_size"],
            step_size=specs["step_size"],
            asset_class=specs["asset_class"],
            initial_capital=100.0,
            clip_notional=specs["clip"],
            session_id=f"{session_id}_100",
        )
        t50 = ArcusLivePaperTrader(
            market=m,
            tick_size=specs["tick_size"],
            step_size=specs["step_size"],
            asset_class=specs["asset_class"],
            initial_capital=50.0,
            clip_notional=specs["clip"],
            session_id=f"{session_id}_50",
        )
        traders_100[m] = t100
        traders_50[m] = t50

    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received interrupt. Stopping paper trading...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    # Start all traders
    for m in market_list:
        await traders_100[m].start()
        await traders_50[m].start()

    t_start = time.time()
    try:
        if args.duration > 0:
            logger.info(f"Paper trading scheduled for {args.duration:.1f} seconds ({args.duration/3600.0:.2f} hours)...")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=args.duration)
            except asyncio.TimeoutError:
                logger.info("Target duration elapsed.")
        else:
            await stop_event.wait()
    finally:
        elapsed = time.time() - t_start
        logger.info(f"Stopping all paper traders after {elapsed:.1f} seconds...")
        results_100 = {}
        results_50 = {}

        for m in market_list:
            await traders_100[m].stop()
            await traders_50[m].stop()

            sum_100_c = traders_100[m].pnl_engine_c.get_summary(traders_100[m].current_mid)
            sum_100_b = traders_100[m].pnl_engine_b.get_summary(traders_100[m].current_mid)
            results_100[m] = {
                "summary_c": sum_100_c,
                "summary_b": sum_100_b,
                "asset_class": MARKET_METADATA.get(m, {}).get("asset_class", "crypto"),
            }

            sum_50_c = traders_50[m].pnl_engine_c.get_summary(traders_50[m].current_mid)
            sum_50_b = traders_50[m].pnl_engine_b.get_summary(traders_50[m].current_mid)
            results_50[m] = {
                "summary_c": sum_50_c,
                "summary_b": sum_50_b,
                "asset_class": MARKET_METADATA.get(m, {}).get("asset_class", "crypto"),
            }

        generate_paper_report(session_id, elapsed, results_100, results_50, Path(args.output_md))


if __name__ == "__main__":
    asyncio.run(main())
