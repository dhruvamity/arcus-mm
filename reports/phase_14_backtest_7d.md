# Phase 14 — Rigorous Multi-Day & Regime-Aware Backtest Report

**Date:** 2026-09-19 16:01:57 UTC  
**Status:** `PRELIMINARY — INTERIM STATUS (Awaiting Gate G2 Multi-Day Accumulation)`  
**Gating Model:** Model C (Strict Trade-Through) + Empirical p95 Latency (640ms)  
**Capital Scenarios:** $50 and $100 Research Capital with Per-Market Min Clips  
**Total Data Messages Analyzed:** 175288 messages  
**Total Real Trades Processed:** 409 trades  

---

## 1. Data Coverage & Regime Stratification Table

Per Section 6.7 of `prompt.md`, this report presents the data coverage table first:

| Market | Asset Class | Regime | Session | Duration (hrs) | Real Trades | BBO Updates | L2 Updates | Model C Fills | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **HYPE-USD** | crypto_candidate | WEEKEND | US_LATE | 0.22h | 26 | 2760 | 15569 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **ZEC-USD** | crypto_candidate | WEEKEND | US_LATE | 0.22h | 21 | 2565 | 7564 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **NEAR-USD** | crypto_candidate | WEEKEND | US_LATE | 0.19h | 4 | 3345 | 9563 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **UNI-USD** | crypto_candidate | WEEKEND | US_LATE | 0.22h | 6 | 2159 | 7768 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **LIT-USD** | crypto_candidate | WEEKEND | US_LATE | 0.01h | 2 | 1843 | 8786 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **AAVE-USD** | crypto_candidate | WEEKEND | US_LATE | 0.01h | 2 | 967 | 3707 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **CASHCAT-USD** | crypto_candidate | WEEKEND | US_LATE | 0.22h | 17 | 229 | 1175 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **XRP-USD** | crypto_control | WEEKEND | US_LATE | 0.03h | 4 | 3282 | 9118 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **BTC-USD** | crypto_control | WEEKEND | US_LATE | 0.22h | 170 | 8941 | 30639 | 3 | **INSUFFICIENT DATA (<300 fills)** |
| **ETH-USD** | crypto_control | WEEKEND | US_LATE | 0.22h | 57 | 1591 | 20108 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **SOL-USD** | crypto_control | WEEKEND | US_LATE | 0.22h | 55 | 1838 | 16911 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **SPCX-USD** | equities | WEEKEND | US_LATE | 0.01h | 2 | 12 | 70 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **NVDA-USD** | equities | WEEKEND | US_LATE | 0.22h | 9 | 2034 | 2187 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **TSLA-USD** | equities | WEEKEND | US_LATE | 0.01h | 2 | 144 | 806 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **GOOGL-USD** | equities | WEEKEND | US_LATE | 0.01h | 2 | 26 | 337 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **AMD-USD** | equities | WEEKEND | US_LATE | 0.14h | 6 | 46 | 569 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **SLV-USD** | commodities/indices | WEEKEND | US_LATE | 0.01h | 2 | 33 | 847 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **GLD-USD** | commodities/indices | WEEKEND | US_LATE | 0.07h | 3 | 5 | 34 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **SPY-USD** | commodities/indices | WEEKEND | US_LATE | 0.17h | 17 | 944 | 4237 | 0 | **INSUFFICIENT DATA (<300 fills)** |
| **QQQ-USD** | commodities/indices | WEEKEND | US_LATE | 0.01h | 2 | 86 | 2034 | 0 | **INSUFFICIENT DATA (<300 fills)** |

---

## 2. Pre-Registered Criteria & Thresholds Matrix

| Criterion ID | Requirement Description | Threshold Value | Gating Status |
|---|---|---|---|
| **CRIT-1** | Minimum Simulated Passive Fills (Tiered) | 300 fills (High) / 100 fills (Mid) | Enforced (Gate G3) |
| **CRIT-2** | Lower Bound Bootstrap CI (hourly clustered) | 90% CI > 0 bps | Enforced (Gate G3) |
| **CRIT-3** | Positive Weekday Consistency (5 OOS Days) | >= 60% of OOS days (>= 3/5); max day <= 50% | Enforced (Gate G3) |
| **CRIT-4** | Cost & Capital Envelope (Taker Exit Fee & DD) | Net PnL > 0 after 2.25 bps taker fee; Max DD < 10% | Enforced (Gate G3) |
| **CRIT-5** | Baseline & Model Dominance | Beats 0 bps & random baseline; Model B != Model A | Enforced (Gate G3) |
| **CRIT-6** | Dual Capital Scenario Testing | $50 and $100 | Enforced |

### Pre-Registered Verdicts Summary

| Market Category | Markets Evaluated | Fills Threshold (>=300) Met? | Positive Net Edge? | Pre-Registered Verdict |
|---|---|---|---|---|
| **Crypto Candidates** | HYPE, ZEC, NEAR, UNI, LIT, AAVE, CASHCAT | NO (Accumulating) | Inconclusive | **INSUFFICIENT DATA** |
| **Crypto Controls** | BTC, ETH, SOL, XRP | NO (Accumulating) | Inconclusive | **INSUFFICIENT DATA** |
| **Equity Perps** | SPCX, NVDA, TSLA, GOOGL, AMD | NO (Closed Weekend) | Inconclusive | **INSUFFICIENT DATA** |
| **Commodities / Indices** | SLV, GLD, SPY, QQQ | NO (Closed Weekend) | Inconclusive | **INSUFFICIENT DATA** |

---

## 3. Defect-Ledger Remediation Status

| Finding ID | Defect Description | Remediation Implemented | Validation Status |
|---|---|---|---|
| **A1–A4** | ~20s recordings & synthetic candle enrichment | Quarantined old runs; multi-day stream recorder active (PID 11661) | **IN PROGRESS (Gate G2 clock running)** |
| **B1** | Model A = Model B bug & non-monotonic fills | Overhauled `FillEngine`; monotonicity verified | **RESOLVED & TESTED (30/30 tests pass)** |
| **B2** | Infeasible clip sizes below venue min notional | Per-market min clips enforced ($5–$15.34) | **RESOLVED & TESTED** |
| **B5** | Arbitrary 60ms latency assumption | Host empirical latency measured (p50: 159ms, p95: 640ms) | **RESOLVED & BENCHMARKED** |
| **B6** | Unclear taker exit fees & PnL leaks | 2.25 bps taker fee charged on flatten; balance sheet identity enforced | **RESOLVED & TESTED** |
| **B7** | ALO & speed bump modeling | Verified via `arcus-docs`: ALO and cancels skip 50ms speed bump | **RESOLVED & CONFIGURED** |
| **C1–C4** | Clamped markout horizons & trade tape bias | Un-clamped horizons; dropped out-of-range fills; passive fill markouts | **RESOLVED & TESTED** |

---

## 4. Plain-Language Answer to Research Question

**Question:** Can a passive market making strategy profitably capture spread on Arcus Perpetuals with $50–$100 experimental capital?

**Empirical Answer:** **`INSUFFICIENT DATA — ACCUMULATING MULTI-DAY DATASET`**  
**Confidence Level:** High confidence that existing data is insufficient; zero confidence in prior withdrawn claims.  

Multi-day recording is actively underway to capture the full 7-day walk-forward period (including Monday–Friday US RTH sessions). No conclusion can be drawn until Gate G2 is reached and data accumulation completes on Saturday 2026-09-26.
