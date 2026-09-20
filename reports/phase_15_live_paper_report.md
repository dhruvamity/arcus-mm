# Phase 15 — Primary Live Paper Trading & Replay Parity Report

**Session ID:** `monday_paper_20260920_153030`  
**Start UTC:** `2026-09-20T15:30:30.255474+00:00`  
**End UTC:** `2026-09-20T15:30:41.068124+00:00`  
**Active Markets (10):** `BTC-USD, ETH-USD, SOL-USD, HYPE-USD, ZEC-USD, NEAR-USD, SPY-USD, QQQ-USD, NVDA-USD, SLV-USD`  
**Total Simulated Fills:** `12`  
**Bit-for-Bit Replay Parity:** **PASS** (Hash: `07352806167a39fd`)  

---

## 1. Executive Summary & Verification Preconditions

- **Execution Mode:** Read-only live mainnet public WebSocket stream fed into canonical `SimEngine`.
- **Live Order Placement:** **ZERO real orders placed** on venue orderbook.
- **Replay Parity:** Bit-for-bit event reconstruction from `raw_stream.jsonl` matching live execution hash.
- **Rule 11 Compliance:** Strategy session outcomes judged strictly on threshold >= 30 fills.

## 2. Strategy Performance & Session Outcomes

| Strategy ID | Market | Model B PnL ($) | Model B Fills | Model C PnL ($) | Model C Fills | Risk State | Outcome Label |
|---|---|---|---|---|---|---|---|
| `BTC-USD_adaptive_c100` | **BTC-USD** | $+240.8159 | 1 | $+240.8159 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_adaptive_c50` | **BTC-USD** | $+240.8159 | 1 | $+240.8159 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_donothing_c100` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_donothing_c50` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_fixed_c100` | **BTC-USD** | $+240.8039 | 1 | $+240.8039 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_fixed_c50` | **BTC-USD** | $+240.8039 | 1 | $+240.8039 | 1 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_randomside_c100` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_randomside_c50` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_volclock_c100` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `BTC-USD_volclock_c50` | **BTC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
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
| `HYPE-USD_adaptive_c100` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `HYPE-USD_adaptive_c50` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `HYPE-USD_donothing_c100` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `HYPE-USD_donothing_c50` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `HYPE-USD_fixed_c100` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `HYPE-USD_fixed_c50` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `HYPE-USD_randomside_c100` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `HYPE-USD_randomside_c50` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `HYPE-USD_volclock_c100` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `HYPE-USD_volclock_c50` | **HYPE-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_adaptive_c100` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_adaptive_c50` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_donothing_c100` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_donothing_c50` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_fixed_c100` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_fixed_c50` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_randomside_c100` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_randomside_c50` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_volclock_c100` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `NEAR-USD_volclock_c50` | **NEAR-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
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
| `ZEC-USD_adaptive_c100` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ZEC-USD_adaptive_c50` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ZEC-USD_donothing_c100` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ZEC-USD_donothing_c50` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ZEC-USD_fixed_c100` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ZEC-USD_fixed_c50` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ZEC-USD_randomside_c100` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ZEC-USD_randomside_c50` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ZEC-USD_volclock_c100` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |
| `ZEC-USD_volclock_c50` | **ZEC-USD** | $+0.0000 | 0 | $+0.0000 | 0 | `NORMAL` | **`SESSION: INSUFFICIENT`** |

---

## 3. Replay Parity Integrity Attestation

- **Live Execution Fill Hash:** `07352806167a39fdc4d27df55be038f7a952631b1c207e7de55ca71bf261b292`
- **Offline Replay Fill Hash:** `07352806167a39fdc4d27df55be038f7a952631b1c207e7de55ca71bf261b292`
- **Fills Count Discrepancy:** `0`
- **Parity Status:** **VERIFIED (0 discrepancy)**

