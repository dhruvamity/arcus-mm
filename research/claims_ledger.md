# Arcus MM Claims Ledger & Provenance Map

**Purpose:** Enforce Non-negotiable Rule 3: every quantitative claim in prose must trace directly to a computed table cell.  
**Repository:** `arcus-mm`  
**Status:** Audited & Updated (Corrective Pass 2) — 2026-09-19 18:35:00 UTC

---

## 1. Superseded & Withdrawn Claims Ledger (Phases 0–13 Invalidation)

Per the withdrawal banner in `reports/final_research_report.md` and the findings in `research/audit.md`, all empirical claims originating from Phase 0–13 smoke tests are formally **WITHDRAWN**:

| Claim ID | Original Claim Text | Original Source | Audit Defect Reference | Concrete Audit Finding & Reason for Withdrawal | Current Status |
|---|---|---|---|---|---|
| **CLM-01** | *"Small-clip AS is -2.21 to +0.8 bps; yields +1.8 to +3.5 bps net edge per completed clip"* | Phase 6 §4.2, Final Report §1 | C1, C3 | **Clamped Forward Horizons**: Lookahead horizon was clamped to end of 20s recording. Table in Phase 6 actually showed LIT +171.23 bps and ZEC -20.36 bps. | **WITHDRAWN** |
| **CLM-02** | *"ZEC, SPCX, and SLV are Certified for Deployment / CONDITIONAL YES"* | Phase 7, Phase 10, Final Report | C4, D5 | **Unvalidated Smoke Runs**: Derived from ~20s recordings; SPCX had 0.0s recording and 3 events; evaluated during weekend when equity perps are closed. | **WITHDRAWN** |
| **CLM-03** | *"HYPE maintains positive net PnL across all three fill models / HYPE QUALIFIED"* | Phase 7 §3, Final Report §2 | C2, D8 | **Falsified by Table**: Backtest table showed Model C had -0.11% net return and OOS return was -0.09%. Model C failed. | **WITHDRAWN** |
| **CLM-04** | *"Model B survives at 60ms and +500ms latency"* | Phase 7 Table | C2 | **Non-Binding Queue Depth**: Model A and Model B produced 100% identical fills in all 63 rows; queue was completely bypassed. | **WITHDRAWN** |
| **CLM-05** | *"Pool exhaustion risk: ZERO / perpetually sustainable action pools"* | Phase 11 Report, Final Report §4 | D9 | **Severe Sample Insufficiency**: Phase 11 test ran for 15s with 0 fills; consumed 23 action units while reporting 0 orders placed. | **WITHDRAWN** |
| **CLM-06** | *"1.5 to 3.2 actions/fill requote efficiency"* | Phase 8 Report, Final Report §4 | D9 | **Unvalidated Extrapolation**: Derived from a 20-second sample with 1 fill; not statistically representative. | **WITHDRAWN** |
| **CLM-07** | *"Optimal capital allocation: $60 ZEC with $8.00 clips / $40 SPCX"* | Phase 13 Report, Final Report §7 | D6 | **Sub-Minimum Order Rejection**: Venue `/v1/markets` sets `minOrderSize = 0.01 ZEC` ($14.82–$15.34). An $8 clip would be rejected by exchange engine. | **WITHDRAWN** |
| **CLM-08** | *"NEAR, LIT, BTC, ETH, SOL REJECTED due to negative smoke PnL"* | Phase 7 Table, Final Report §2 | D8 | **Premature Rejection**: 20-second smoke runs under non-representative weekend liquidity cannot establish true weekday viability. | **WITHDRAWN** |
| **CLM-09** | *"UNI HOLD recommendation"* | Phase 7 Table, Final Report §2 | D8 | **Unsubstantiated Classification**: Arbitrary classification based on insufficient smoke data. | **WITHDRAWN** |
| **CLM-10** | *"Proceed to testnet execution"* | Final Report §7, §8 | D10 | **Violation of Governance Gates**: No testnet deployment permitted until Gates G1–G4 pass on multi-day weekday data. | **WITHDRAWN** |
| **CLM-11** | *"Empirically validated / complete and verified across all 13 phases"* | Final Report §8 | D10 | **False Synthesis**: Audit proved empirical findings were invalid smoke artifacts. Engineering scaffold works, but zero strategies validated. | **WITHDRAWN** |
| **CLM-12** | *"Pool replenishment rate: 1 unit per $0.10 traded volume"* | Phase 0 Report, Phase 11 | D9 | **Docs-Only Unverified**: Venue docs claim this formula, but no live venue probe has confirmed whether replenishment is instantaneous or batched. | **WITHDRAWN (Downgraded to [DOCS_ONLY])** |

---

## 2. Status of Phase 14 & Phase 15 Reports: Evaluation Scaffolds vs. Real Results

> [!IMPORTANT]
> **Plain Statement of Verdict Status**:
> Any occurrence of the word `VALIDATED` in `reports/phase_14_backtest_7d.md`, `reports/phase_15_live_paper_report.md`, or the pre-registered protocol is strictly an **evaluation scaffold and target schema definition**. 
> - In `reports/phase_14_backtest_7d.md`: Every single one of the 20 markets currently has the verdict **`INSUFFICIENT DATA (<300 fills)`**.
> - In `reports/phase_15_live_paper_report.md`: Every single one of the 10 evaluated markets currently has the verdict **`INSUFFICIENT DATA (<30 fills)`**.
> - **Zero strategies or markets have achieved a validated verdict.** Validation is strictly conditioned on completing the 7-day data accumulation and passing the 5-day OOS walk-forward test (Sep 28 – Oct 2).

---

## 3. Active Audited Claims Ledger (Forward-Tracing)

Every active quantitative assertion in current reports traces directly to an audited table cell:

| Claim ID | Market / Entity | Metric / Assertion | Numerical Value | Source Document | Table Reference | Column / Cell Reference | Status in Report | `scripts/verify_report.py` Validated? |
|---|---|---|---|---|---|---|---|---|
| **CLM-14-01** | Venue | REST `/v1/markets` p50 Latency | 185.23 ms | `reports/latency_summary.md` | Table 1 | Row REST, Column p50 | Audited Live Sample | YES |
| **CLM-14-02** | Venue | REST `/v1/markets` p95 Latency | 703.47 ms | `reports/latency_summary.md` | Table 1 | Row REST, Column p95 | Audited Live Sample | YES |
| **CLM-14-03** | Venue | WebSocket Ping/Pong p50 Latency | 137.11 ms | `reports/latency_summary.md` | Table 1 | Row WS Ping, Column p50 | Audited Live Sample | YES |
| **CLM-14-04** | Venue | Local Host Median Clock Skew | -73.54 ms | `reports/latency_summary.md` | §Clock Skew | Median Skew | Audited Live Sample | YES |
| **CLM-14-05** | All 20 Markets | Phase 14 Interim Backtest Verdict | `INSUFFICIENT DATA` | `reports/phase_14_backtest_7d.md` | Table 1 | Column: Verdict | Real Result (Scaffold Phase) | YES |
| **CLM-14-06** | All 10 Markets | Phase 15 Interim Live Paper Verdict | `INSUFFICIENT DATA` | `reports/phase_15_live_paper_report.md` | Table 1 | Column: Verdict | Real Result (Scaffold Phase) | YES |
| **CLM-14-07** | Criteria | Backtest Fill Gating Threshold | 300 fills (High) / 100 fills (Mid) | `reports/phase_14_backtest_7d.md` | Table 2 | Row CRIT-1 | Pre-Registered Rule | YES |
| **CLM-14-08** | Criteria | Max Portfolio Drawdown Cap | 10.0% | `reports/phase_14_backtest_7d.md` | Table 2 | Row CRIT-4 | Pre-Registered Rule | YES |
| **CLM-14-09** | Criteria | Forced Flatten Taker Liquidation Fee | 2.25 bps | `reports/phase_14_backtest_7d.md` | Table 2 | Row CRIT-4 | Fee Tiers API Verified | YES |
| **CLM-14-10** | BTC-USD | Live Venue Min Executable Clip | $8.14 (or $8.12–$8.15) | `research/prereg_backtest.md` | Table 1 | Row BTC-USD | `/v1/markets` Live Verified | YES |
| **CLM-14-11** | ZEC-USD | Live Venue Min Executable Clip | $14.82 (or $14.82–$15.34) | `research/prereg_backtest.md` | Table 1 | Row ZEC-USD | `/v1/markets` Live Verified | YES |
| **CLM-14-12** | SLV-USD | Live Venue Min Executable Clip | $6.00 | `research/prereg_backtest.md` | Table 1 | Row SLV-USD | `/v1/markets` Live Verified | YES |
| **CLM-14-13** | AMD-USD | Live Venue Min Executable Clip | $5.54 | `research/prereg_backtest.md` | Table 1 | Row AMD-USD | `/v1/markets` Live Verified | YES |
| **CLM-14-14** | HYPE-USD | Live Venue Tick Size | 0.001 | `research/prereg_backtest.md` | Table 1 | Row HYPE-USD | `/v1/markets` Live Verified | YES |
| **CLM-14-15** | ZEC-USD | Live Venue Tick Size | 0.001 | `research/prereg_backtest.md` | Table 1 | Row ZEC-USD | `/v1/markets` Live Verified | YES |
