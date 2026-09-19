# Final Quantitative Research Report: Arcus Perpetual Market-Making Feasibility ($50–$100 Capital Mandate)

> [!WARNING]
> # SUPERSEDED — PRELIMINARY SMOKE TEST. Conclusions withdrawn pending Phase 14+.
> The empirical conclusions below were based on ~20s recordings, REST backfills, and candle synthesis during a weekend regime. All claims of "CERTIFIED FOR DEPLOYMENT" and "CONDITIONAL YES" are withdrawn. Current status is **INCONCLUSIVE — smoke-tested only**. See [research/audit.md](../research/audit.md) for the defect ledger.

**Author:** Quantitative Research & Market Microstructure Systems Agent  
**Date:** 2026-09-19 13:58:00 UTC (Audited & Corrected: 2026-09-19 18:25:00 UTC)  
**Evaluation Scope:** Phases 0 through 13 under Master Research Mandate ([prompt.md](../prompt.md))  
**Registered Testnet Address:** `[REDACTED_FOR_SECURITY]`  
**API Key Status:** Verified ACTIVE on Arcus Venue (`[REDACTED]`)  
**Account Balance:** $0.00 (Unfunded as declared by user)  
**Current Status:** **`INCONCLUSIVE — SMOKE TEST ONLY`**  

---

## 1. Executive Summary & The Empirical Answer

> ### The Primary Research Mandate
> **Can a simple, executable passive market-making strategy on Arcus produce robust positive net expectancy at approximately $50–$100 of experimental capital after realistic passive fills, queue position, rate-limit budget, maker fees/rebates, funding, inventory effects, latency, discrete tick/step constraints, venue mechanics, and adverse selection?**

### The Definitive Empirical Answer: **INCONCLUSIVE — SMOKE TEST ONLY (Conclusions Withdrawn)**

Our preliminary scaffold confirmed engineering and venue connectivity, but **empirical viability remains INCONCLUSIVE**. 

The empirical conclusions in prior iterations rested on ~20 seconds of WebSocket recordings per market, REST trade backfills, and candle synthesis on frozen weekend equity markets. No strategy has been validated for live deployment. Full empirical validation is deferred to the Phase 14+ multi-day recording and 5-day weekday out-of-sample walk-forward evaluation.

---

## 2. Market Universe & Screening Status (STUBBED / PENDING PHASE 14+)

All preliminary returns and performance percentages from the Phase 7 smoke test are formally **WITHDRAWN**.

The table below reflects the current audited status and live venue specifications retrieved directly from `/v1/markets`:

| Symbol | Category | Tick Size | Step Size | Live Min Clip ($) | Pre-Registered Fills Threshold | Phase 14 Status |
|---|---|---|---|---|---|---|
| **`BTC-USD`** | Crypto Control | 0.1 | 0.00000001 | $8.15 | $\ge 300$ fills | **INSUFFICIENT DATA** |
| **`ETH-USD`** | Crypto Control | 0.01 | 0.0000001 | $5.00 | $\ge 300$ fills | **INSUFFICIENT DATA** |
| **`SOL-USD`** | Crypto Control | 0.001 | 0.000001 | $5.00 | $\ge 300$ fills | **INSUFFICIENT DATA** |
| **`HYPE-USD`** | Crypto Candidate | 0.001 | 0.000001 | $9.21 | $\ge 300$ fills | **INSUFFICIENT DATA** |
| **`ZEC-USD`** | Crypto Candidate | 0.001 | 0.000001 | $14.87 | $\ge 100$ fills | **INSUFFICIENT DATA** |
| **`NEAR-USD`** | Crypto Candidate | 0.001 | 0.000001 | $5.00 | $\ge 300$ fills | **INSUFFICIENT DATA** |
| **`UNI-USD`** | Crypto Candidate | 0.001 | 0.000001 | $5.00 | $\ge 100$ fills | **INSUFFICIENT DATA** |
| **`LIT-USD`** | Crypto Candidate | 0.0001 | 0.00001 | $5.00 | $\ge 300$ fills | **INSUFFICIENT DATA** |
| **`SPCX-USD`** | Equities Perp | 0.01 | 0.0000001 | $5.00 | $\ge 100$ fills | **INSUFFICIENT DATA** |
| **`NVDA-USD`** | Equities Perp | 0.01 | 0.0000001 | $5.00 | $\ge 100$ fills | **INSUFFICIENT DATA** |
| **`TSLA-USD`** | Equities Perp | 0.01 | 0.0000001 | $5.00 | $\ge 100$ fills | **INSUFFICIENT DATA** |
| **`AMD-USD`** | Equities Perp | 0.01 | 0.0000001 | $5.54 | $\ge 100$ fills | **INSUFFICIENT DATA** |
| **`SLV-USD`** | Commodities Perp | 0.01 | 0.0000001 | $6.00 | $\ge 100$ fills | **INSUFFICIENT DATA** |

*(Note: Prior claims that ZEC could be traded at $8.00 clips were invalid; ZEC's venue minimum order size is 0.01 ZEC, equating to ~$14.87–$15.34. Sizing models have been corrected accordingly).*

---

## 3. Fill Model Sensitivity Analysis (STUBBED / UNDER REMEDIATION)

The independent audit identified that prior Phase 7 runs suffered from a non-binding queue defect where Model A and Model B yielded identical fills across all runs, and Model C occasionally produced higher returns than Model A.

The fill engine has been overhauled and verified with deterministic unit tests:
- **Fill Monotonicity Guarantee**: $Fills(A) \ge Fills(B) \ge Fills(C)$ on every event path.
- **Model A (Optimistic)**: Immediate touch fill (diagnostic upper bound only).
- **Model B (Queue-Aware FIFO)**: Resting quotes join behind displayed depth; strict volume depletion; cancel-replace loses priority; in-place size reduction keeps priority.
- **Model C (Conservative Gating)**: Requires trades strictly through the quoted price by at least one tick. Gating model for all deployment decisions.

All preliminary fill model conclusions from Phase 7 are **WITHDRAWN**. New results will be evaluated only when $\ge 7$ days of data are recorded.

---

## 4. Rate-Limit & Action Pool Feasibility (AUDITED STATUS)

The claim of "Pool exhaustion risk: ZERO" and assertions of "perpetually sustainable action pools" from earlier smoke tests are **WITHDRAWN** per Defect D9 and CLM-05:
- The Phase 11 test ran for only 15 seconds with 0 fills, yet consumed 23 units while reporting 0 orders placed.
- The "1.5 to 3.2 actions/fill" estimate was derived from a 20-second sample and is not considered validated.
- Venue action pool sustainability will be empirically measured during the multi-hour live paper trading sessions (Sunday baseline and Monday US-RTH).

---

## 5. Adverse Selection & Markout Study (STUBBED / UNDER REMEDIATION)

All claims of "size-asymmetry discovery" (-2.21 bps small clip vs toxic large sweeps) and the "+1.8 to +3.5 bps per completed clip" assertion are **WITHDRAWN** per Defect C1, C3, and CLM-01:
- Phase 6 markouts were identical across 500ms, 1s, 5s, and 30s because horizons were clamped to the end of a ~20-second recording window.
- The adverse selection engine has been overhauled: out-of-range forward horizons are dropped rather than clamped, and fill counts $N$ will be reported per horizon.
- Markout distributions will be recomputed across the multi-day dataset.

---

## 6. Software Architecture Status

The repository provides a complete, deterministic research and trading scaffold:
1. **`src/config.py`**: Configuration with hardcoded mainnet order submission lock.
2. **`src/auth.py`**: Cryptographic Ed25519 Scheme 1 and Scheme 2 signers.
3. **`src/calendar.py`**: Timezone-aware regime engine (`America/New_York`) distinguishing US-RTH from off-hours.
4. **`src/recorder.py`**: Multi-socket continuous stream recorder with connection pooling and automated rotation.
5. **`src/models/fill.py`**: Deterministic fill engine guaranteeing fill monotonicity ($A \ge B \ge C$).
6. **`src/models/pnl.py`**: Strict balance sheet accounting identity ($Cash + Position \times Mid - Fees \pm Funding \equiv Equity$) and 2.25 bps taker fee on forced exits.
7. **`src/paper_trader.py`**: Live mainnet streaming paper execution engine (zero live orders submitted).
8. **`scripts/verify_report.py`**: Automated report verifier enforcing table-to-prose consistency and prohibiting withdrawn claims.
9. **`scripts/test_replay_parity.py`**: Bit-for-bit replay parity verification between paper execution and backtest replay.
10. **`tests/`**: 30 automated unit tests passing 100%.

---

## 7. Capital Allocation & Live Experiment Recommendations (LOCKED / PENDING VALIDATION)

All prior recommendations to proceed to testnet execution or live capital allocation are **WITHDRAWN**.

Per the Non-Negotiable Rules of [prompt.md](../prompt.md):
- **Hard Mainnet Lock**: No real mainnet orders may be submitted under any circumstances.
- **Unfunded State**: The account is unfunded ($0.00 balance). Live evaluation is restricted to paper execution against live public mainnet data.
- **Allocation Decisions Suspended**: No capital allocation (such as the prior $60 ZEC / $40 SPCX proposal) will be made until Gates G2, G3, and G4 have been reached, fully evaluated, and formally approved.

---

## 8. Closing Synthesis

The engineering scaffold and simulation harness have been thoroughly remediated, debugged, and verified via 30 deterministic unit tests. 

However, **no empirical market-making strategy has yet been validated**. Empirical conclusions will be drawn strictly after the completion of the 7-day data recording window (Sat 2026-09-19 to Sat 2026-09-26+) and the 5-day out-of-sample walk-forward backtest under conservative Model C execution.
