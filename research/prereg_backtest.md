# Pre-Registered Backtest Protocol & Evaluation Specification

**Status:** Committed in advance of out-of-sample data collection (Phase 14+).  
**Repository:** `arcus-mm`  
**Standard:** Strict zero look-ahead bias, pre-registered chronological splits, and deterministic gating.

---

## 1. Principles & Non-Negotiable Rules

1. **Regime Segregation**:
   - Weekend results **do not transfer** to weekdays.
   - Weekday US-RTH (13:30–20:00 EDT) is the primary basis for any deployment decision.
   - Weekend is evaluated as a separate, secondary regime; regimes are never pooled into one headline number.
2. **Chronological Splits (Zero Data Leakage)**:
   - Chronological day-blocks only (no random k-fold or shuffled cross-validation).
   - In-Sample (Tuning): First 3 weekdays (Monday 00:00 UTC through Wednesday 23:59 UTC).
   - Out-of-Sample (Testing): Remaining weekdays (Thursday 00:00 UTC through Friday 23:59 UTC).
   - Held-Out Regime: Weekend days (Saturday and Sunday).
   - OOS evaluation is executed **once** after parameter freeze. No iterative re-tuning on OOS data.
3. **Primary Gating Model**:
   - Primary evaluation gate: **Fill Model C (Trade strictly through quote price)**.
   - Baseline Latency: Empirical measured host p95 latency = **640 ms**.
   - Stress Latency: Empirical p95 + 500 ms = **1,140 ms**.
   - Model B (Queue-Aware FIFO) is logged in shadow; Model A is diagnostic upper-bound only.

---

## 2. Pre-Registered Validation Criteria (Section 6.6)

For any market × strategy combination to achieve a verdict of `VALIDATED`, it must satisfy all 6 conditions simultaneously on the Weekday Out-of-Sample (OOS) period under Model C with p95 latency:

| Criterion # | Requirement | Threshold | Failure Action |
|---|---|---|---|
| **1. Sample Size** | Simulated fills in weekday OOS window | $N \ge 300$ fills | Mark `INSUFFICIENT DATA` (zero or handful of fills is never positive) |
| **2. Net Expectancy & CI** | Net bps per fill and 90% bootstrap confidence interval (clustered by hour) | Mean Net bps $> 0$ AND Lower Bound of 90% CI $> 0$ | Mark `NOT VALIDATED` |
| **3. Consistency** | Day-by-day profitability and concentration | Positive on $\ge 60\%$ of OOS weekday-days; no single day contributes $> 50\%$ of total PnL | Mark `NOT VALIDATED` (unstable / outlier-driven) |
| **4. Cost & Capital Envelope** | Net PnL after funding and taker forced-exit fees; drawdown limit; inventory limits | Net PnL $> 0$; Max DD $< 10.0\%$; Zero inventory limit violations | Mark `NOT VALIDATED` |
| **5. Baseline & Model Dominance** | Comparison against controls and model differentiation | Beats Do-Nothing baseline (0 bps); Beats Random-Side Quoting baseline; Model B $\ne$ Model A demonstrable; All Section 4.1 tests pass | Mark `NOT VALIDATED` |
| **6. Capital Scale Invariance** | Performance across capital tiers | Validated at both **$50 and $100** capital (or explicitly flagged as capital-dependent) | Flag capital dependency |

---

## 3. Candidate Universe & Capital Scenarios

Simulations are executed across two discrete capital allocations:
- **Scenario A**: \$100 Experimental Research Capital
- **Scenario B**: \$50 Minimal Experimental Capital

Each market enforces its actual venue minimum executable clip:
$$\text{Min Executable Clip} = \max\left(\text{minOrderNotional}, \text{minOrderSize} \times \text{mid}\right)$$

| Category | Market | Tick Size | Step Size | Venue Min Notional | Min Executable Clip | Capital Cushion ($50) | Capital Cushion ($100) |
|---|---|---|---|---|---|---|---|
| **Crypto Candidates** | `HYPE-USD` | 0.001 | 0.000001 | \$5.00 | ~\$9.24 | 18.5% | 9.2% |
| | `ZEC-USD` | 0.001 | 0.000001 | \$5.00 | ~\$15.34 | 30.7% | 15.3% |
| | `NEAR-USD` | 0.001 | 0.000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `LIT-USD` | 0.0001 | 0.00001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `UNI-USD` | 0.001 | 0.000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `AAVE-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `CASHCAT-USD` | 0.000001 | 0.001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| **Crypto Control** | `XRP-USD` | 0.0001 | 0.00001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| **Mega-Cap Controls** | `BTC-USD` | 0.1 | 0.00000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `ETH-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `SOL-USD` | 0.001 | 0.000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| **Equity Perps** | `SPCX-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `NVDA-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `TSLA-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `GOOGL-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `AMD-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| **Commodities/Indices** | `SLV-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `GLD-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `SPY-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |
| | `QQQ-USD` | 0.01 | 0.0000001 | \$5.00 | ~\$5.00 | 10.0% | 5.0% |

Markets whose min clip requires $> 35\%$ of total capital at \$50 are flagged as capital-constrained.

---

## 4. Stratified Reporting Format

Results will be presented in `reports/phase_14_backtest_7d.md` using the exact pre-registered table schemas:

1. **Coverage Table**: Hours recorded, message counts, trades recorded, fills generated per regime.
2. **Regime Transfer Matrix**: Weekend estimated spread/vol/PnL vs Weekday realized spread/vol/PnL.
3. **Pre-Registered Gate Verdicts**: Table indicating PASS/FAIL across all 6 criteria for each candidate. Allowed verdicts: `VALIDATED`, `NOT VALIDATED`, `INSUFFICIENT DATA`.
