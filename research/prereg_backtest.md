# Pre-Registration Protocol v3 — Out-of-Sample Evaluation & Gating Specification

**Status:** COMMITTED & LOCKED in advance of out-of-sample data collection (Phase 14R).  
**Repository:** `arcus-mm`  
**Engine Version:** `v0.2.0-frozen` (Canonical single-path `SimEngine`)  
**Standard:** Strict zero look-ahead bias, pre-registered chronological splits, and deterministic gating.  
**Last Audited & Updated:** 2026-09-20 01:20:00 UTC (Pre-Registration v3)  

---

## 1. Principles & Non-Negotiable Protocol Rules

1. **Regime Segregation & RTH Definition**:
   - Weekday US-RTH (**13:30–20:00 UTC / 09:30–16:00 ET**) is the primary basis for any live or capital deployment decision.
   - Weekend results **do not transfer** to weekdays. Weekend trading is evaluated strictly as a separate, secondary regime.
   - Weekend and weekday performance metrics are **never pooled** into one headline number.

2. **Chronological Splits & 5-Day Out-of-Sample Window (Zero Data Leakage)**:
   - Chronological day-blocks only (no random k-fold, bootstrap shuffling, or cross-validation).
   - **Tune Week (In-Sample / Tuning)**: Monday 2026-09-21 00:00 UTC through Friday 2026-09-25 23:59 UTC (5 full weekdays).
   - **Parameter Freeze**: Saturday 2026-09-26 12:00 UTC. All hyperparameters, spreads, skew coefficients, and threshold rules are committed to git and tagged (`v0.2.0-frozen`).
   - **Validation Week (Out-of-Sample / OOS Testing)**: Monday 2026-09-28 00:00 UTC through Friday 2026-10-02 23:59 UTC (**5 full OOS weekdays**).
   - **Held-Out Secondary Regimes**: Weekend days (Saturday 2026-09-26 and Sunday 2026-09-27).
   - **Single-Shot OOS Evaluation**: The OOS walk-forward evaluation is executed **once** after parameter freeze. Any iterative re-tuning on OOS data instantly disqualifies the run.

3. **Mathematical Consistency in OOS Window (5-Day Multi-Day Stability)**:
   - Criterion 3 ("positive on $\ge 60\%$ of days"): Requires $\ge 3$ out of 5 OOS weekdays positive ($k \ge 3$).
   - Criterion 3 ("no single day contributes $> 50\%$ of total PnL"): Enforces multi-day stability and prevents outlier-driven false positives.

4. **Primary Gating Model**:
   - Primary deployment gate: **Fill Model C (Trade strictly through quote price by at least 1 tick)**.
   - Fill Model B (Queue-Aware FIFO with volume depletion) is tracked as reference.
   - Fill Model A (Touch) is an unconstrained diagnostic upper bound only.

5. **Dynamic Per-Order Latency Sampling & Stress Testing**:
   - Orders are **never** subjected to a static flat delay.
   - Empirical latency distribution sampled with replacement: $p50 = 185.2\text{ ms}$, $\text{Mean} = 290.9\text{ ms}$, $p95 = 703.5\text{ ms}$.
   - **Stress Testing Gate**: Evaluated independently under $\tau_{\text{stress}} = p95 + 500\text{ ms} = 1,203.5\text{ ms}$.

---

## 2. Pre-Registered Candidate Universe & Strategy Grid

Based on empirical data sufficiency from the WS-5 pilot analysis (`research/pilot_summary.md`), the candidate universe is restricted to markets with demonstrated taker flow and statistically feasible sample sizes:

### 2.1 Primary Candidate Universe (6 Markets)

| Symbol | Category | Tick Size | Step Size | Min Executable Clip | Pilot Trades/Hr | Expected 5D N (Model C) | Power Gating Status |
|---|---|---|---|---|---|---|---|
| `BTC-USD` | Mega-Cap Crypto Control | 0.1 | 0.0001 | $8.14 | 23,238.8 | 1,080 | **FEASIBLE** |
| `ETH-USD` | Large-Cap Crypto Control | 0.01 | 0.001 | $5.00 | 1,435.2 | 1,633 | **FEASIBLE** |
| `SOL-USD` | High-Beta Layer 1 | 0.01 | 0.01 | $5.00 | 1,833.0 | 1,590 | **FEASIBLE** |
| `HYPE-USD` | Hyperliquid Liquid Perp | 0.001 | 0.0001 | $9.20 | 563.8 | 2,701 | **FEASIBLE** |
| `ZEC-USD` | Mid-Cap Liquid Alt | 0.001 | 0.00001 | $14.82 | 188.7 | 1,874 | **FEASIBLE** |
| `NEAR-USD` | Liquid Alt | 0.001 | 0.0001 | $5.00 | 123.2 | 678 | **FEASIBLE** |

*Pre-Declared `INSUFFICIENT DATA` Universe*:  
Equities and commodities perps (`SPCX-USD`, `TSLA-USD`, `NVDA-USD`, `AMD-USD`, `GOOGL-USD`, `SPY-USD`, `QQQ-USD`, `SLV-USD`, `GLD-USD`) show near-zero taker volume during weekend trading ($< 5\text{ trades/hr}$). They are pre-declared `INSUFFICIENT DATA` for weekend evaluation and will only be evaluated under weekday RTH if Monday's live data confirms $E[N] \ge 100$.

### 2.2 Pre-Registered Strategy Grid (≤ 12 Configurations Total)

Every candidate strategy quotes relative to the **live book** (distance-to-touch logged in ticks):

1. **`FixedSpread`**:
   - Config 1: `spread_bps = 4.0`, clip notional = min executable clip
   - Config 2: `spread_bps = 6.0`, clip notional = min executable clip
2. **`Adaptive` (Microprice / OFI Lean)**:
   - Config 3: `base_spread_bps = 3.0`, OFI inventory skew = 0.5
   - Config 4: `base_spread_bps = 5.0`, OFI inventory skew = 0.5
3. **`VolatilityClock` (EWMA $\sigma$ Sizing)**:
   - Config 5: `k_factor = 1.0`, `min_spread_bps = 3.0`, `max_spread_bps = 25.0`
   - Config 6: `k_factor = 1.5`, `min_spread_bps = 4.0`, `max_spread_bps = 30.0`
4. **`AvellanedaStoikov` (Calibrated Dimensionally Consistent)**:
   - Config 7: $\gamma = 0.05, \kappa = 2.0$
   - Config 8: $\gamma = 0.10, \kappa = 1.5$

**Paired Control Baselines (Run concurrently on identical event stream)**:
- **`DoNothing`**: Zero quotes, zero fills, 0 bps return.
- **`RandomSide`**: Randomly quotes bid or ask with identical 5 bps spread to test whether edge exceeds random selection.

---

## 3. Formal Hypotheses & Power Analysis Gating

### 3.1 Formal Hypotheses

- **$H_1$ (Positive Net Expectancy)**:  
  For each candidate $(M, S)$, the mean net bps per fill under Fill Model C after all fees (2.25 bps taker exit) and funding satisfies:
  $$\mu_{\text{net}} > 0 \quad \text{and} \quad \text{Lower Bound of } 90\% \text{ Bootstrap CI} > 0$$
- **$H_2$ (Queue-Aware Model Realism)**:  
  Fill Model B fills exceed Fill Model C ($N_B \ge N_C$), with $N_C \ge 300$ fills over 5 weekdays.
- **$H_3$ (Structural Edge Over Controls)**:  
  Strategy PnL strictly dominates both `DoNothing` (0 bps) and `RandomSide` quoting on the identical event stream:
  $$\text{PnL}(S) > \text{PnL}(\text{RandomSide}) > \text{PnL}(\text{DoNothing})$$

### 3.2 Power Analysis & Multiple Testing Correction

- **Required Sample Size Formula**:
  $$n \approx \left(\frac{1.28 \cdot \sigma}{\text{edge}}\right)^2$$
  Based on pilot empirical per-fill variance ($\sigma \approx 2.5–5.0\text{ bps}$ for liquid crypto), $N \ge 300$ fills provides $> 80\%$ statistical power at $\alpha = 0.05$ to detect a true edge of $1.0\text{ bps}$.
- **Multiple Testing**: **Holm–Bonferroni step-down correction** applied across the family of pre-declared tests ($m = 6\text{ markets} \times 4\text{ strategies} = 24\text{ hypotheses}$). Both raw and adjusted $p$-values will be reported.
- **Bootstrap Clustering**: 1-hour block bootstrap (1,000 resamples) to account for intra-day serial correlation of returns.

---

## 4. Pre-Registered Validation Criteria (Mandatory Gate G4)

For any market × strategy combination to achieve a verdict of `VALIDATED`, it must satisfy all 6 criteria simultaneously on the 5-day Weekday Out-of-Sample (OOS) period under Model C:

| Criterion # | Requirement | Tier / Threshold | Failure Action |
|---|---|---|---|
| **1. Sample Size** | Simulated fills across 5-day weekday OOS window | High-Liquidity ($N \ge 300$ fills); Mid-Liquidity ($N \ge 100$ fills) | Mark `INSUFFICIENT DATA` |
| **2. Net Expectancy & CI** | Net bps per fill and 90% block-bootstrap CI | Mean Net bps $> 0$ AND Lower Bound of 90% CI $> 0$ | Mark `NOT VALIDATED` |
| **3. Multi-Day Consistency** | Daily profitability across 5 OOS weekdays | Net PnL $> 0$ on $\ge 3$ of 5 OOS weekdays ($\ge 60\%$); Max single day $\le 50.0\%$ total PnL | Mark `NOT VALIDATED` |
| **4. Cost & Capital Envelope** | Costs inclusive of 2.25 bps taker exit; drawdown and inventory limits | Net PnL $> 0$; Max Intraday Drawdown $< 10.0\%$; Zero inventory limit breaches | Mark `NOT VALIDATED` |
| **5. Baseline & Model Dominance** | Comparison against controls and model differentiation | Beats Do-Nothing (0 bps); Beats Random-Side Quoting; Model B $\ne$ Model A demonstrable; 13/13 SimEngine tests pass | Mark `NOT VALIDATED` |
| **6. Capital Scale Invariance** | Performance across capital tiers | Evaluated at both **$50 and $100** capital; if viable only at $100, flagged as `CAPITAL_CONSTRAINED` | Flag capital dependency |

---

## 5. Dated Amendment Log

- **2026-09-20 (Pre-Registration v3)**:
  1. *Pilot & Power Integration*: Integrated empirical trade rates and variance from WS-5 pilot analysis (`research/pilot_summary.md`). Selected 6 primary candidate markets (`BTC`, `ETH`, `SOL`, `HYPE`, `ZEC`, `NEAR`). Pre-declared low-activity equities as `INSUFFICIENT DATA` for weekend evaluation.
  2. *Single-Path SimEngine Pinning*: Pinned execution to canonical `SimEngine` (`v0.2.0-frozen`). Verified with 13/13 unit tests, bit-for-bit replay parity, and 10/10 mutation checks.
  3. *Strategy Grid Bound*: Bounded candidate strategies to 4 classes and 8 active parameter configurations + 2 paired control baselines (`DoNothing`, `RandomSide`).
  4. *RTH Clarification*: Formally defined US-RTH as 13:30–20:00 UTC (09:30–16:00 ET).
  5. *Multiple Testing*: Added explicit Holm–Bonferroni family-wise error rate control across all pre-declared tests.
  6. *OOS Assurance Statement*: **No Out-of-Sample (OOS) data has been collected or evaluated. The OOS test window remains strictly in the future (Sep 28 – Oct 2, 2026).**
- **2026-09-19 (Corrective Pass 2)**:
  1. Expanded Out-of-Sample window from flawed 2-day split (Thu–Fri) to full 5-day weekday split (Mon Sep 28 to Fri Oct 2, 2026).
  2. Fixed mathematical impossibility in Criterion 3: daily concentration limit $\le 50\%$ and $\ge 60\%$ consistency defined for 5 days ($k \ge 3$).
  3. Replaced flat latency model with empirical sampling ($p50=185\text{ms}, p95=703\text{ms}$) plus stress case at $1,203\text{ms}$.
  4. Segmented Criterion 1 fill count thresholds by liquidity tier.
