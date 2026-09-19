# Pre-Registered Backtest Protocol & Evaluation Specification

**Status:** COMMITTED & LOCKED in advance of out-of-sample data collection (Phase 14+).  
**Repository:** `arcus-mm`  
**Standard:** Strict zero look-ahead bias, pre-registered chronological splits, and deterministic gating.  
**Last Audited & Updated:** 2026-09-19 18:30:00 UTC (Corrective Pass 2)

---

## 1. Principles & Non-Negotiable Protocol Rules

1. **Regime Segregation**:
   - Weekend results **do not transfer** to weekdays.
   - Weekday US-RTH (13:30–20:00 EDT / 17:30–00:00 UTC) is the primary basis for any live or capital deployment decision.
   - Weekend is evaluated strictly as a separate, secondary regime; weekend and weekday performance metrics are **never pooled** into one headline number.

2. **Chronological Splits & 5-Day Out-of-Sample Window (Zero Data Leakage)**:
   - Chronological day-blocks only (no random k-fold, bootstrap shuffling, or cross-validation).
   - **Tune Week (In-Sample / Tuning)**: Monday 2026-09-21 00:00 UTC through Friday 2026-09-25 23:59 UTC (5 full weekdays).
   - **Parameter Freeze**: Saturday 2026-09-26 12:00 UTC. All hyperparameters, spreads, skew coefficients, and threshold rules are committed to git and tagged (`v0.1.0-frozen`).
   - **Validation Week (Out-of-Sample / OOS Testing)**: Monday 2026-09-28 00:00 UTC through Friday 2026-10-02 23:59 UTC (**5 full OOS weekdays**).
   - **Held-Out Secondary Regimes**: Weekend days (Saturday 2026-09-26 and Sunday 2026-09-27).
   - **Single-Shot OOS Evaluation**: The OOS walk-forward evaluation is executed **once** after parameter freeze. Any iterative re-tuning on OOS data instantly disqualifies the run.

3. **Mathematical Correction to OOS Window (5-Day vs. Flawed 2-Day)**:
   - Under the prior 2-day OOS design (Thu–Fri):
     - Criterion 3 ("no single day contributes > 50% of total PnL") was **mathematically impossible** for any strategy with positive total PnL across both days (if Day 1 + Day 2 = Total, at least one day must be $\ge 50\%$, unless both are identically 50.000%).
     - Criterion 3 ("positive on $\ge 60\%$ of days") mathematically required 100% (2 out of 2 days positive).
   - Under the corrected **5-Day OOS Window** (Mon–Fri, Sep 28–Oct 2):
     - $\ge 60\%$ positive days means $\ge 3$ out of 5 days positive ($k \ge 3$).
     - No single day $> 50\%$ is mathematically realistic and enforces true multi-day stability (e.g. daily PnL proportions like 30%, 25%, 20%, 15%, 10%).

4. **Primary Gating Model**:
   - Primary deployment gate: **Fill Model C (Trade strictly through quote price by at least 1 tick)**.
   - Fill Model B (Queue-Aware FIFO with volume depletion) is tracked as reference.
   - Fill Model A (Touch) is an unconstrained diagnostic upper bound only.

5. **Dynamic Per-Order Latency Sampling & Stress Testing**:
   - Orders are **never** subjected to a static flat delay.
   - For every simulated order placement and cancellation, latency $\tau$ is drawn at random from the empirical distribution measured during live benchmarking:
     - Empirical REST distribution: $p50 = 185.23\text{ ms}$, $\text{Mean} = 290.90\text{ ms}$, $p95 = 703.47\text{ ms}$.
     - Log-normal parameterization fitted to measured samples: $\mu_{\ln} = 5.42, \sigma_{\ln} = 0.58$.
   - **Separate Stress Testing Gate**: Every strategy must independently be simulated under the high-latency stress case:
     $$\tau_{\text{stress}} = p95 + 500\text{ ms} = 1,203.47\text{ ms}$$
     A strategy that collapses under the stress latency gate cannot be marked `VALIDATED`.

---

## 2. Pre-Registered Validation Criteria (Section 6.6)

For any market × strategy combination to achieve a verdict of `VALIDATED`, it must satisfy all 6 conditions simultaneously on the 5-day Weekday Out-of-Sample (OOS) period under Model C:

| Criterion # | Requirement | Tier / Threshold | Failure Action |
|---|---|---|---|
| **1. Sample Size** | Simulated fills across 5-day weekday OOS window | **High-Liquidity Tier** (BTC, ETH, SOL, HYPE, NEAR, LIT, XRP): $N \ge 300$ fills<br>**Mid-Liquidity / Equities Tier** (ZEC, SPCX, NVDA, TSLA, AMD, SLV, UNI, GLD, etc.): $N \ge 100$ fills | Mark `INSUFFICIENT DATA` (a zero or handful of fills is never positive) |
| **2. Net Expectancy & CI** | Net bps per fill and 90% bootstrap confidence interval (clustered by 1-hour blocks) | Mean Net bps $> 0$ AND Lower Bound of 90% CI $> 0$ | Mark `NOT VALIDATED` |
| **3. Multi-Day Consistency** | Day-by-day profitability and concentration across 5 OOS weekdays | Net PnL $> 0$ on $\ge 3$ of 5 OOS weekdays ($\ge 60\%$);<br>Max single-day PnL $\le 50.0\%$ of total net PnL | Mark `NOT VALIDATED` (unstable / outlier-driven) |
| **4. Cost & Capital Envelope** | Net PnL after funding and taker forced-exit fees (2.25 bps); drawdown limit; inventory limits | Net PnL $> 0$; Max Intraday Drawdown $< 10.0\%$; Zero inventory limit breaches | Mark `NOT VALIDATED` |
| **5. Baseline & Model Dominance** | Comparison against controls and model differentiation | Beats Do-Nothing baseline (0 bps); Beats Random-Side Quoting baseline; Model B $\ne$ Model A demonstrable on the dataset; All 30 unit tests pass | Mark `NOT VALIDATED` |
| **6. Capital Scale Invariance** | Performance across capital tiers | Evaluated at both **$50 and $100** capital; if viable only at $100, explicitly flagged as `CAPITAL_CONSTRAINED` | Flag capital dependency |

---

## 3. Candidate Universe & Live Venue Specifications

Clip sizes, tick sizes, and step sizes are verified directly against the live venue `/v1/markets` endpoint.

$$\text{Min Executable Clip} = \max\left(\text{minOrderNotional}, \text{minOrderSize} \times \text{oraclePrice}\right)$$

| Category | Symbol | Tick Size | Step Size | Min Order Size | Oracle Price (Live) | Min Notional | Min Executable Clip | Capital Cushion ($50) | Capital Cushion ($100) | Liquidity Tier (Fill Threshold) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Mega-Cap Control** | `BTC-USD` | 0.1 | 0.00000001 | 0.0001 | $81,423.70 | $5.00 | **$8.14** | 16.3% | 8.1% | High-Liquidity ($N \ge 300$) |
| | `ETH-USD` | 0.01 | 0.0000001 | 0.001 | $2,640.02 | $5.00 | **$5.00** | 10.0% | 5.0% | High-Liquidity ($N \ge 300$) |
| | `SOL-USD` | 0.001 | 0.000001 | 0.01 | $110.92 | $5.00 | **$5.00** | 10.0% | 5.0% | High-Liquidity ($N \ge 300$) |
| **Crypto Candidates** | `HYPE-USD` | 0.001 | 0.000001 | 0.1 | $92.03 | $5.00 | **$9.20** | 18.4% | 9.2% | High-Liquidity ($N \ge 300$) |
| | `ZEC-USD` | 0.001 | 0.000001 | 0.01 | $1,481.72 | $5.00 | **$14.82** | 29.6% | 14.8% | Mid-Liquidity ($N \ge 100$) |
| | `NEAR-USD` | 0.001 | 0.000001 | 0.1 | $3.64 | $5.00 | **$5.00** | 10.0% | 5.0% | High-Liquidity ($N \ge 300$) |
| | `LIT-USD` | 0.0001 | 0.00001 | 1.0 | $4.94 | $5.00 | **$5.00** | 10.0% | 5.0% | High-Liquidity ($N \ge 300$) |
| | `UNI-USD` | 0.001 | 0.000001 | 0.1 | $8.63 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |
| | `XRP-USD` | 0.0001 | 0.00001 | 1.0 | $1.42 | $5.00 | **$5.00** | 10.0% | 5.0% | High-Liquidity ($N \ge 300$) |
| | `AAVE-USD` | 0.01 | 0.0000001 | 0.01 | $142.19 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |
| | `CASHCAT-USD` | 0.000001 | 0.001 | 1.0 | $0.19 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |
| **Equities Perps** | `SPCX-USD` | 0.01 | 0.0000001 | 0.01 | $152.68 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |
| | `NVDA-USD` | 0.01 | 0.0000001 | 0.01 | $222.09 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |
| | `TSLA-USD` | 0.01 | 0.0000001 | 0.01 | $364.95 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |
| | `AMD-USD` | 0.01 | 0.0000001 | 0.01 | $554.24 | $5.00 | **$5.54** | 11.1% | 5.5% | Mid-Liquidity ($N \ge 100$) |
| | `GOOGL-USD` | 0.01 | 0.0000001 | 0.01 | $350.90 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |
| | `SPY-USD` | 0.01 | 0.0000001 | 0.001 | $763.69 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |
| | `QQQ-USD` | 0.01 | 0.0000001 | 0.001 | $720.89 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |
| **Commodities Perps** | `SLV-USD` | 0.01 | 0.0000001 | 0.1 | $60.02 | $5.00 | **$6.00** | 12.0% | 6.0% | Mid-Liquidity ($N \ge 100$) |
| | `GLD-USD` | 0.01 | 0.0000001 | 0.01 | $401.29 | $5.00 | **$5.00** | 10.0% | 5.0% | Mid-Liquidity ($N \ge 100$) |

*Key Venue Verifications*:
- `BTC-USD`: Min order size is `0.0001 BTC` $\times$ $\$81,423.70 = \$8.14$ (prior assumption of ~$5 was invalid).
- `SLV-USD`: Min order size is `0.1 SLV` $\times$ $\$60.02 = \$6.00$ (prior assumption of ~$5 was invalid).
- `AMD-USD`: Min order size is `0.01 AMD` $\times$ $\$554.24 = \$5.54$ (prior assumption of ~$5 was invalid).
- `HYPE-USD`: Tick size is `0.001` (prior claim of 0.01 was invalid); Min clip is $\$9.20$.
- `ZEC-USD`: Tick size is `0.001` (prior claim of 0.01 was invalid); Min clip is $\$14.82$.

---

## 4. Stratified Reporting Output & Gating Ledger

Results from the 5-day OOS backtest will be reported in `reports/phase_14_backtest_7d.md` using the exact pre-registered table schemas:
1. **Coverage Table**: Hours recorded, message counts, trades recorded, fills generated per regime.
2. **Regime Transfer Matrix**: Weekend estimated spread/vol/PnL vs Weekday realized spread/vol/PnL.
3. **Pre-Registered Gate Verdicts**: Table indicating PASS/FAIL across all 6 criteria for each candidate. Allowed verdicts: `VALIDATED`, `NOT VALIDATED`, `INSUFFICIENT DATA`.

---

## 5. Dated Protocol Changelog

- **2026-09-19 (Corrective Pass 2)**:
  1. Expanded Out-of-Sample window from flawed 2-day split (Thu–Fri) to full 5-day weekday split (Mon Sep 28 to Fri Oct 2, 2026).
  2. Fixed mathematical impossibility in Criterion 3: daily concentration limit $\le 50\%$ and $\ge 60\%$ consistency are now properly defined for 5 days ($k \ge 3$).
  3. Replaced flat 640ms latency model with dynamic per-order empirical sampling ($p50=185\text{ms}, p95=703\text{ms}$) plus separate stress case at $p95+500\text{ms} = 1,203\text{ms}$.
  4. Segmented Criterion 1 fill count thresholds by liquidity tier: High-Liquidity ($N \ge 300$), Mid/Slow ($N \ge 100$).
  5. Updated market specifications directly from live venue `/v1/markets`: BTC min clip corrected to $8.14, SLV to $6.00, AMD to $5.54, HYPE/ZEC tick size confirmed as 0.001.
