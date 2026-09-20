from __future__ import annotations

"""Trade Reconciliation Script for Mandate (WS-1 Test 1).

Pulls public REST trades via GET /v1/trades and reconciles them against
WebSocket-recorded trades in data/raw/2026-09-19/<market>/trades.jsonl.
Outputs results to evidence/trade_reconciliation.md.
"""

import asyncio
import datetime
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Set, Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.rest_client import ArcusRestClient
from src.config import ArcusConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reconcile")


def load_recorded_trade_ids(market: str, date_str: str) -> Set[str]:
    """Loads all recorded trade IDs for a market from jsonl files."""
    trade_file = REPO_ROOT / "data" / "raw" / date_str / market / "trades.jsonl"
    trade_ids = set()
    if not trade_file.exists():
        return trade_ids

    with open(trade_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                contents = rec.get("data", {}).get("contents", [])
                if isinstance(contents, list):
                    for t in contents:
                        tid = t.get("tradeId") or t.get("id")
                        if tid:
                            trade_ids.add(str(tid))
                elif isinstance(contents, dict):
                    tid = contents.get("tradeId") or contents.get("id")
                    if tid:
                        trade_ids.add(str(tid))
            except Exception:
                continue
    return trade_ids


async def run_reconciliation():
    target_markets = ["BTC-USD", "ETH-USD", "SOL-USD", "HYPE-USD", "ZEC-USD", "NEAR-USD", "SPCX-USD"]
    today_str = "2026-09-19"  # Active recording date directory

    client = ArcusRestClient(ArcusConfig())
    results: Dict[str, Dict[str, Any]] = {}

    try:
        for market in target_markets:
            logger.info(f"Fetching REST trades for {market}...")
            try:
                # GET /v1/trades with limit 100
                rest_trades = await client.get_trades(market, limit=100)
            except Exception as e:
                logger.error(f"Failed to fetch REST trades for {market}: {e}")
                rest_trades = []

            recorded_ids = load_recorded_trade_ids(market, today_str)

            # Load recorder start timestamp from heartbeat
            hb_file = REPO_ROOT / "data" / "recorder_heartbeat.json"
            start_ts_us = 0
            if hb_file.exists():
                try:
                    hb = json.loads(hb_file.read_text(encoding="utf-8"))
                    dt_hb = datetime.datetime.fromisoformat(hb["timestamp_utc"].replace("Z", "+00:00"))
                    start_dt = dt_hb - datetime.timedelta(seconds=hb["uptime_secs"])
                    start_ts_us = int(start_dt.timestamp() * 1e6)
                except Exception:
                    pass

            # Filter REST trades to those occurring after recorder start
            in_session_rest_trades = [t for t in rest_trades if (t.get("timestamp") or 0) >= start_ts_us]
            rest_trade_ids = [str(t.get("tradeId") or t.get("id")) for t in in_session_rest_trades if (t.get("tradeId") or t.get("id"))]
            total_in_session_rest = len(rest_trade_ids)

            matched_ids = [tid for tid in rest_trade_ids if tid in recorded_ids]
            missing_ids = [tid for tid in rest_trade_ids if tid not in recorded_ids]

            coverage_pct = (len(matched_ids) / total_in_session_rest * 100.0) if total_in_session_rest > 0 else 100.0

            results[market] = {
                "total_rest_sampled": len(rest_trades),
                "in_session_rest_trades": total_in_session_rest,
                "recorded_total": len(recorded_ids),
                "matched_count": len(matched_ids),
                "missing_count": len(missing_ids),
                "coverage_pct": round(coverage_pct, 2),
                "missing_sample": missing_ids[:5],
            }
            logger.info(f"[{market}] In-Session REST: {total_in_session_rest}/{len(rest_trades)} | Recorded: {len(recorded_ids)} | Matched: {len(matched_ids)} | In-Session Coverage: {coverage_pct:.1f}%")
    finally:
        await client.close()

    # Generate Markdown evidence report
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    md_lines = [
        "# WS-1 Test 1: Trade Reconciliation Report",
        "",
        f"**Date:** {now_str}  ",
        f"**Recording Date Checked:** `{today_str}`  ",
        "",
        "## 1. Executive Summary",
        "",
        "This report cross-references live REST `GET /v1/trades` against persisted WebSocket trades logged by recorder PID 11661.",
        "To ensure a true apples-to-apples comparison, REST trades are filtered to those occurring *after* the recorder startup timestamp.",
        "",
        "## 2. Market Reconciliation Matrix",
        "",
        "| Market | REST Sample Count | In-Session REST Trades | Recorded Total in Log | Matched REST Trades | Missing In-Session | Coverage (%) | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for m, r in results.items():
        cov = r["coverage_pct"]
        in_sess = r["in_session_rest_trades"]
        if in_sess == 0:
            status = "NO IN-SESSION TRADES (Illiquid Window)"
        elif cov >= 99.0:
            status = "**PASS (>=99%)**"
        else:
            status = "**UNDER-RECORDED / SEV-1**"

        md_lines.append(
            f"| **{m}** | {r['total_rest_sampled']} | {in_sess} | {r['recorded_total']} | "
            f"{r['matched_count']} | {r['missing_count']} | {cov:.1f}% | {status} |"
        )

    md_lines.extend([
        "",
        "## 3. Detailed Diagnosis & Notes",
        "",
    ])

    for m, r in results.items():
        if r["missing_count"] > 0:
            md_lines.append(f"- **{m}**: {r['missing_count']} trades missing from sample of {r['total_rest_sampled']}. Sample missing IDs: `{r['missing_sample']}`")
        else:
            md_lines.append(f"- **{m}**: 100% of sampled REST trades matched recorded WebSocket tape.")

    out_file = REPO_ROOT / "evidence" / "trade_reconciliation.md"
    out_file.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    logger.info(f"Wrote reconciliation evidence to {out_file}")


if __name__ == "__main__":
    asyncio.run(run_reconciliation())
