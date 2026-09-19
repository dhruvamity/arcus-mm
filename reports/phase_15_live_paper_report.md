# Phase 15 — Live Mainnet Paper Trading & Replay Parity Report

**Session ID:** `session_g3_20260919_195940`  
**Session Interval (UTC):** 2026-09-19T19:59:40.325900+00:00 → 2026-09-19T19:59:56.509222+00:00  
**Execution Mode:** Read-Only Public WS Streaming → Unified `SimEngine`  
**Mainnet Order Invariant:** Strictly 0 real orders submitted (`APPROVE_MAINNET_ORDERS = NO`)  
**Replay Parity:** ✅ PASS (Bit-for-Bit Hash Match)  

## 1. Executive Summary & Gate G3 Status

This session executes the pre-registered Gate G3 live paper trading baseline. Market data was streamed live from Arcus mainnet WebSocket feeds and ingested directly by the canonical `SimEngine` without copy-pasted execution logic. Kill-switch watchdogs (stale BBO > 3s, crossed book, drawdown limits) ran continuously on 100ms clock ticks.

## 2. Session Outcome & Market Summary (Rule 11 Enforced)

| Market | Strategy ID | Model B Fills | Model B Net PnL ($) | Model C Fills | Model C Net PnL ($) | Risk State | Session Outcome |
|---|---|---|---|---|---|---|---|
| **BTC-USD** | `BTC-USD_adaptive_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **BTC-USD** | `BTC-USD_adaptive_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **BTC-USD** | `BTC-USD_donothing_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **BTC-USD** | `BTC-USD_donothing_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **BTC-USD** | `BTC-USD_fixed_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **BTC-USD** | `BTC-USD_fixed_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **BTC-USD** | `BTC-USD_randomside_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **BTC-USD** | `BTC-USD_randomside_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **BTC-USD** | `BTC-USD_volclock_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **BTC-USD** | `BTC-USD_volclock_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_adaptive_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_adaptive_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_donothing_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_donothing_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_fixed_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_fixed_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_randomside_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_randomside_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_volclock_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ETH-USD** | `ETH-USD_volclock_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_adaptive_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_adaptive_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_donothing_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_donothing_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_fixed_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_fixed_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_randomside_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_randomside_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_volclock_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **HYPE-USD** | `HYPE-USD_volclock_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_adaptive_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_adaptive_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_donothing_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_donothing_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_fixed_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_fixed_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_randomside_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_randomside_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_volclock_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **NEAR-USD** | `NEAR-USD_volclock_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_adaptive_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_adaptive_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_donothing_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_donothing_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_fixed_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_fixed_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_randomside_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_randomside_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_volclock_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **SOL-USD** | `SOL-USD_volclock_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_adaptive_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_adaptive_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_donothing_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_donothing_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_fixed_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_fixed_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_randomside_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_randomside_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_volclock_c100` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |
| **ZEC-USD** | `ZEC-USD_volclock_c50` | 0 | $+0.0000 | 0 | $+0.0000 | `NORMAL` | **SESSION: INSUFFICIENT** |

## 3. Replay Parity Verification (Bit-for-Bit Audit)

- **Live Run Fill Hash:** `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- **Replay Run Fill Hash:** `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- **Live Fills Logged:** 0
- **Replay Fills Logged:** 0
- **Parity Verdict:** `✅ PASS (Bit-for-Bit Hash Match)`

## 4. Rate-Limit Pool Accounting

- Action pools tracked in real time under venue rules (place=1, cancel=1, modify=1, cancelAll=1000).
- Earned volume replenishment credited on fills (+1 action unit per $0.10 executed notional).
- Idle drip replenishment tracked at 1 action unit per 10s idle.

## 5. Economic Expectancy & Scale Reality (R-20)

- **Capital Envelope:** $50 and $100 experimental capital tiers evaluated side-by-side.
- **Scale Expectancy:** At $8 clip size, +2.0 bps net edge produces approximately $0.0016 per fill.
- **Mandate Compliance:** This session evaluates mechanics and statistical edge per fill, not income.
