# Phase 15 — Rehearsal Live Paper Trading & Replay Parity Report [PRE-FIX]

> [!WARNING]
> **REHEARSAL DRY RUN (PRE-FIX) — NOT FOR STATISTICAL INFERENCE (W-06 / Rule 8)**  
> This dry-run session ran on Sunday 2026-09-20 (11 seconds). The reported +$238.76 net PnL was an artifact of cross-market message misattribution in `src/paper_trader.py` (W-06: ETH-USD trades routed to BTC-USD). This artifact is preserved strictly for historical audit trail and is excluded from all tuning, inference, and validation.

**Session ID:** `monday_paper_20260920_183928`  
**Start UTC:** `2026-09-20T18:39:28.626381+00:00`  
**End UTC:** `2026-09-20T18:39:39.486939+00:00`  
**Active Markets (12):** `BTC-USD, ETH-USD, SOL-USD, SPY-USD, QQQ-USD, NVDA-USD, AMD-USD, TSLA-USD, GOOGL-USD, SPCX-USD, SLV-USD, GLD-USD`  
**Total Simulated Fills:** `24`  
**Bit-for-Bit Replay Parity:** **PASS** (Hash: `e43b0ad96e59c92b`)  

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
| `BTC-USD_adaptive_c100` | **BTC-USD** | $+238.7604 | 1 | $+238.7604 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_adaptive_c50` | **BTC-USD** | $+238.7604 | 1 | $+238.7604 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_donothing_c100` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_donothing_c50` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_fixed_c100` | **BTC-USD** | $+238.7607 | 1 | $+238.7607 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_fixed_c50` | **BTC-USD** | $+238.7607 | 1 | $+238.7607 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_randomside_c100` | **BTC-USD** | $+238.7604 | 1 | $+238.7604 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_randomside_c50` | **BTC-USD** | $+238.7604 | 1 | $+238.7604 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_volclock_c100` | **BTC-USD** | $+238.7619 | 1 | $+238.7619 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_volclock_c50` | **BTC-USD** | $+238.7619 | 1 | $+238.7619 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_adaptive_c100` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_adaptive_c50` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_donothing_c100` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_donothing_c50` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_fixed_c100` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_fixed_c50` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_randomside_c100` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_randomside_c50` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_volclock_c100` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ETH-USD_volclock_c50` | **ETH-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_adaptive_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_adaptive_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_donothing_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_donothing_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_fixed_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_fixed_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_randomside_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_randomside_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_volclock_c100` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GLD-USD_volclock_c50` | **GLD-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_adaptive_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_adaptive_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_donothing_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_donothing_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_fixed_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_fixed_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_randomside_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_randomside_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_volclock_c100` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `GOOGL-USD_volclock_c50` | **GOOGL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
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
| `QQQ-USD_adaptive_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_adaptive_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_donothing_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_donothing_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_fixed_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_fixed_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_randomside_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_randomside_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_volclock_c100` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `QQQ-USD_volclock_c50` | **QQQ-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
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
| `SOL-USD_adaptive_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_adaptive_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_donothing_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_donothing_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_fixed_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_fixed_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_randomside_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_randomside_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_volclock_c100` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SOL-USD_volclock_c50` | **SOL-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_adaptive_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_adaptive_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_donothing_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_donothing_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_fixed_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_fixed_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_randomside_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_randomside_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_volclock_c100` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `SPCX-USD_volclock_c50` | **SPCX-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
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
| `TSLA-USD_adaptive_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_adaptive_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_donothing_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_donothing_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_fixed_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_fixed_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_randomside_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_randomside_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_volclock_c100` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `TSLA-USD_volclock_c50` | **TSLA-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |

---

## 3. Replay Parity Integrity Attestation

- **Live Execution Fill Hash:** `e43b0ad96e59c92bfe05a2eedb556d09b6aea9f9ddacabdc14a9c576a252c55b`
- **Offline Replay Fill Hash:** `e43b0ad96e59c92bfe05a2eedb556d09b6aea9f9ddacabdc14a9c576a252c55b`
- **Fills Count Discrepancy:** `0`
- **Parity Status:** **VERIFIED (0 discrepancy)**

