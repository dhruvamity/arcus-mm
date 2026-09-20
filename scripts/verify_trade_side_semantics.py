from __future__ import annotations

"""Verifies trade side semantics from recorded BBO + Trades (WS-1 Test 2).

Determines whether trade['side'] represents taker side or maker side by
evaluating whether trades labeled 'BUY' trade at/above contemporaneous best ask,
and trades labeled 'SELL' trade at/below contemporaneous best bid.
Outputs to evidence/trade_side_semantics.md.
"""

import json
from pathlib import Path
from typing import Dict, Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_market_side_semantics(market: str, date_str: str = "2026-09-19") -> Dict[str, Any]:
    bbo_file = REPO_ROOT / "data" / "raw" / date_str / market / "bbo.jsonl"
    trade_file = REPO_ROOT / "data" / "raw" / date_str / market / "trades.jsonl"

    if not bbo_file.exists() or not trade_file.exists():
        return {"error": "Files missing"}

    # Load BBO timeline
    bbo_events = []
    with open(bbo_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            ts = rec.get("recv_ts_ns", 0)
            contents = rec.get("data", {}).get("contents", {})
            bid = float(contents.get("bidPrice") or contents.get("bestBid", {}).get("price") or 0.0)
            ask = float(contents.get("askPrice") or contents.get("bestAsk", {}).get("price") or 0.0)
            if bid > 0 and ask > 0:
                bbo_events.append((ts, bid, ask))

    # Load trades
    trades = []
    with open(trade_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            ts = rec.get("recv_ts_ns", 0)
            contents = rec.get("data", {}).get("contents", [])
            if isinstance(contents, list):
                for t in contents:
                    p = float(t.get("price") or 0.0)
                    s = t.get("side", "").upper()
                    if p > 0 and s:
                        trades.append((ts, s, p))

    if not bbo_events or not trades:
        return {"error": "Empty data"}

    # Compare trade price with contemporaneous BBO (as-of join: last BBO <= trade_ts)
    bbo_idx = 0
    n_bbo = len(bbo_events)

    buy_at_or_above_mid = 0
    buy_at_or_above_ask = 0
    buy_at_or_below_bid = 0
    total_buys = 0

    sell_at_or_below_mid = 0
    sell_at_or_below_bid = 0
    sell_at_or_above_ask = 0
    total_sells = 0

    for ts, side, price in trades:
        while bbo_idx + 1 < n_bbo and bbo_events[bbo_idx + 1][0] <= ts:
            bbo_idx += 1
        b_ts, bid, ask = bbo_events[bbo_idx]
        mid = (bid + ask) / 2.0

        if side == "BUY":
            total_buys += 1
            if price >= ask - 1e-6:
                buy_at_or_above_ask += 1
            if price >= mid:
                buy_at_or_above_mid += 1
            if price <= bid + 1e-6:
                buy_at_or_below_bid += 1
        elif side == "SELL":
            total_sells += 1
            if price <= bid + 1e-6:
                sell_at_or_below_bid += 1
            if price <= mid:
                sell_at_or_below_mid += 1
            if price >= ask - 1e-6:
                sell_at_or_above_ask += 1

    return {
        "market": market,
        "total_buys": total_buys,
        "buy_at_or_above_ask_pct": (buy_at_or_above_ask / total_buys * 100.0) if total_buys else 0.0,
        "buy_at_or_above_mid_pct": (buy_at_or_above_mid / total_buys * 100.0) if total_buys else 0.0,
        "buy_at_or_below_bid_pct": (buy_at_or_below_bid / total_buys * 100.0) if total_buys else 0.0,
        "total_sells": total_sells,
        "sell_at_or_below_bid_pct": (sell_at_or_below_bid / total_sells * 100.0) if total_sells else 0.0,
        "sell_at_or_below_mid_pct": (sell_at_or_below_mid / total_sells * 100.0) if total_sells else 0.0,
        "sell_at_or_above_ask_pct": (sell_at_or_above_ask / total_sells * 100.0) if total_sells else 0.0,
    }


def main():
    markets = ["BTC-USD", "ETH-USD", "SOL-USD", "HYPE-USD"]
    lines = [
        "# WS-1 Test 2: Trade Side Semantics Verification",
        "",
        "## 1. Methodology",
        "Evaluates whether `trade.side` in Arcus streaming represents the **taker/aggressor side** (standard exchange convention)",
        "or the maker side. If `side == 'BUY'` is taker buy, trade price will execute at or above contemporaneous ask/mid.",
        "If `side == 'SELL'` is taker sell, trade price will execute at or below contemporaneous bid/mid.",
        "",
        "## 2. Empirical Verification Matrix",
        "",
        "| Market | Total Buys | Buy >= Ask (%) | Buy >= Mid (%) | Total Sells | Sell <= Bid (%) | Sell <= Mid (%) | Verified Taker Side? |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for m in markets:
        res = test_market_side_semantics(m)
        if "error" in res:
            continue
        is_taker = (res["buy_at_or_above_mid_pct"] > 80.0) and (res["sell_at_or_below_mid_pct"] > 80.0)
        verdict = "**CONFIRMED (Taker Aggressor)**" if is_taker else "INCONCLUSIVE"
        lines.append(
            f"| **{m}** | {res['total_buys']} | {res['buy_at_or_above_ask_pct']:.1f}% | {res['buy_at_or_above_mid_pct']:.1f}% | "
            f"{res['total_sells']} | {res['sell_at_or_below_bid_pct']:.1f}% | {res['sell_at_or_below_mid_pct']:.1f}% | {verdict} |"
        )

    lines.extend([
        "",
        "## 3. Venue Documentation Citation",
        "Per Arcus Perpetuals WebSocket documentation for the `trades` channel:",
        "> `side`: Direction of the market taker order (`BUY` or `SELL`). A `BUY` trade executed by a taker hitting a resting ask order.",
        "",
        "Therefore, market maker passive fill logic MUST assert that: ",
        "- A passive maker BID order is filled when `side == 'SELL'` (an aggressive seller hits our resting bid).",
        "- A passive maker ASK order is filled when `side == 'BUY'` (an aggressive buyer lifts our resting ask).",
    ])

    out_file = REPO_ROOT / "evidence" / "trade_side_semantics.md"
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote trade side semantics report to {out_file}")


if __name__ == "__main__":
    main()
