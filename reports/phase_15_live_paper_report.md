# Phase 15 — Primary Live Paper Trading & Replay Parity Report

**Session ID:** `monday_paper_20260921_130021`  
**Start UTC:** `2026-09-21T13:00:21.352905+00:00`  
**End UTC:** `2026-09-21T13:00:32.009165+00:00`  
**Active Markets (12):** `BTC-USD, ETH-USD, SOL-USD, SPY-USD, QQQ-USD, NVDA-USD, AMD-USD, TSLA-USD, GOOGL-USD, SPCX-USD, SLV-USD, GLD-USD`  
**Total Simulated Fills (All Models):** `20`  
**Unique Physical Match Events:** `8`  
**Bit-for-Bit Replay Parity:** **PASS** (Hash: `ee81a72dc9346f06`)  

---

## 1. Executive Summary & Verification Preconditions

- **Execution Mode:** Read-only live mainnet public WebSocket stream fed into canonical `SimEngine`.
- **Live Order Placement:** **ZERO real orders placed** on venue orderbook.
- **Replay Parity:** Bit-for-bit event reconstruction from `raw_stream.jsonl` matching live execution hash.
- **Rule 11 Compliance:** Strategy session outcomes judged strictly on threshold >= 30 fills.

## 2. Strategy Performance & Session Outcomes

| Strategy ID | Market | Model B PnL ($) | Model B Fills | Model C PnL ($) | Model C Fills | Risk State | Outcome Label |
|---|---|---|---|---|---|---|---|
| `AMD-USD_adaptive_c100` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `AMD-USD_adaptive_c50` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `AMD-USD_donothing_c100` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `AMD-USD_donothing_c50` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `AMD-USD_fixed_c100` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `AMD-USD_fixed_c50` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `AMD-USD_randomside_c100` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `AMD-USD_randomside_c50` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `AMD-USD_volclock_c100` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `AMD-USD_volclock_c50` | **AMD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_adaptive_c100` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_adaptive_c50` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_donothing_c100` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_donothing_c50` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_fixed_c100` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_fixed_c50` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_randomside_c100` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_randomside_c50` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_volclock_c100` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_volclock_c50` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_adaptive_c100` | **ETH-USD** | $+0.0001 | 1 | $+0.0001 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_adaptive_c50` | **ETH-USD** | $+0.0001 | 1 | $+0.0001 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_donothing_c100` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_donothing_c50` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_fixed_c100` | **ETH-USD** | $+0.0002 | 1 | $+0.0002 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_fixed_c50` | **ETH-USD** | $+0.0002 | 1 | $+0.0002 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_randomside_c100` | **ETH-USD** | $-0.0000 | 1 | $-0.0000 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_randomside_c50` | **ETH-USD** | $-0.0000 | 1 | $-0.0000 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_volclock_c100` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_volclock_c50` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_adaptive_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_adaptive_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_donothing_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_donothing_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_fixed_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_fixed_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_randomside_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_randomside_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_volclock_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_volclock_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_adaptive_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_adaptive_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_donothing_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_donothing_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_fixed_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_fixed_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_randomside_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_randomside_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_volclock_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_volclock_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_adaptive_c100` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_adaptive_c50` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_donothing_c100` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_donothing_c50` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_fixed_c100` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_fixed_c50` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_randomside_c100` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_randomside_c50` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_volclock_c100` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NVDA-USD_volclock_c50` | **NVDA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_adaptive_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_adaptive_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_donothing_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_donothing_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_fixed_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_fixed_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_randomside_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_randomside_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_volclock_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_volclock_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_adaptive_c100` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_adaptive_c50` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_donothing_c100` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_donothing_c50` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_fixed_c100` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_fixed_c50` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_randomside_c100` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_randomside_c50` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_volclock_c100` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SLV-USD_volclock_c50` | **SLV-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_adaptive_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_adaptive_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_donothing_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_donothing_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_fixed_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_fixed_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_randomside_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_randomside_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_volclock_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_volclock_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_adaptive_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_adaptive_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_donothing_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_donothing_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_fixed_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_fixed_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_randomside_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_randomside_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_volclock_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_volclock_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_adaptive_c100` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_adaptive_c50` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_donothing_c100` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_donothing_c50` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_fixed_c100` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_fixed_c50` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_randomside_c100` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_randomside_c50` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_volclock_c100` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPY-USD_volclock_c50` | **SPY-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_adaptive_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_adaptive_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_donothing_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_donothing_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_fixed_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_fixed_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_randomside_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_randomside_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_volclock_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_volclock_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `PAUSED_STALE_FEED` | **`SESSION: INSUFFICIENT`** |

---

## 3. Replay Parity Integrity Attestation

- **Live Execution Fill Hash:** `ee81a72dc9346f0672613ef7f4c31937916645bf414b720e22aaf2ef82ab5062`
- **Offline Replay Fill Hash:** `ee81a72dc9346f0672613ef7f4c31937916645bf414b720e22aaf2ef82ab5062`
- **Fills Count Discrepancy:** `0`
- **Parity Status:** **VERIFIED (0 discrepancy)**

