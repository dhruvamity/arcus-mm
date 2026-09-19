# Arcus MM Claims Ledger & Provenance Map

**Purpose:** Enforce Non-negotiable Rule 3: every quantitative claim in prose must trace directly to a computed table cell.
**Status:** Initialized for Phase 14+.

---

## 1. Superseded Claims Ledger (Phases 0–13 Invalidation)

| ID | Original Claim | Original Source | Audit Finding | Status |
|---|---|---|---|---|
| **CLM-01** | *"Small-clip AS is -2.2 to +0.8 bps; yields +1.8 to +3.5 bps per completed clip"* | Phase 6 §4.2, Final Report §1 | Table in Phase 6 actually showed LIT +171.23 bps and ZEC -20.36 bps. Clamped 20s horizons. | **WITHDRAWN** |
| **CLM-02** | *"ZEC, SPCX, and SLV are Certified for Deployment"* | Phase 7, Phase 10, Final Report | Based on ~20s recordings; SPCX had 0.0s recording and 3 raw events; weekend frozen markets. | **WITHDRAWN** |
| **CLM-03** | *"HYPE maintains positive net PnL across all three fill models"* | Phase 7 §3 | Table showed Model C was -0.11% and OOS was -0.09%. | **WITHDRAWN** |
| **CLM-04** | *"Model B survives at 60ms and +500ms"* | Phase 7 Table | Model A and Model B produced identical fills in all 63 rows due to non-binding queue depth. | **WITHDRAWN** |
| **CLM-05** | *"Zero rate-limit pool exhaustion"* | Phase 11 Report | Paper test ran for 15 seconds with 0 fills; pool consumed 23 units despite reporting 0 orders placed. | **WITHDRAWN** |

---

## 2. Active Phase 14+ Claims Ledger (Forward-Tracing)

Every active claim in new reports (`reports/phase_14_backtest_7d.md`, `reports/phase_15_live_paper_report.md`, `reports/latency_summary.md`, etc.) must be added here with exact table and cell references before publication.

| Claim ID | Market | Metric / Assertion | Numerical Value | Source Document | Table / Figure | Cell / Column Reference | `scripts/verify_report.py` Validated? |
|---|---|---|---|---|---|---|---|
| **CLM-14-01** | Venue | REST `/v1/markets` p50 Latency | 159.08 ms | `reports/latency_summary.md` | Table 1 | REST Endpoint p50 | YES |
| **CLM-14-02** | Venue | REST `/v1/markets` p95 Latency | 640.26 ms | `reports/latency_summary.md` | Table 1 | REST Endpoint p95 | YES |
| **CLM-14-03** | Venue | WebSocket Ping/Pong p50 Latency | 157.93 ms | `reports/latency_summary.md` | Table 1 | WS Ping/Pong p50 | YES |
| **CLM-14-04** | Venue | Host Median Clock Skew | -73.60 ms | `reports/latency_summary.md` | Table 1 | Clock Skew p50 | YES |
| **CLM-14-05** | All 20 | Phase 14 Initial Backtest Verdict | INSUFFICIENT DATA (<300 fills) | `reports/phase_14_backtest_7d.md` | Table 1 | Column: Verdict | YES |
| **CLM-14-06** | All 10 | Phase 15 Live Paper Verdict | INSUFFICIENT DATA (<30 fills) | `reports/phase_15_live_paper_report.md` | Table 1 | Column: Verdict | YES |
| **CLM-14-07** | Criteria | Backtest Fill Gating Threshold | 300 fills | `reports/phase_14_backtest_7d.md` | Table 2 | Row CRIT-1 | YES |
| **CLM-14-08** | Criteria | Max Portfolio Drawdown Cap | 10.0% | `reports/phase_14_backtest_7d.md` | Table 2 | Row CRIT-4 | YES |
| **CLM-14-09** | Criteria | Forced Flatten Taker Fee | 2.25 bps | `reports/phase_14_backtest_7d.md` | Table 2 | Row CRIT-5 | YES |
