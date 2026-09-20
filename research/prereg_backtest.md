# Pre-Registration Protocol v3.1 — Out-of-Sample Evaluation & Gating Specification

**Status:** DRAFT (under active refinement during tune week Mon 09-21 → Fri 09-25; finalized, committed and tagged `prereg-v3.1` before Sat 2026-09-26 12:00 UTC at Gate G2).  
**Repository:** `arcus-mm`  
**Engine Version:** `v0.3.0-frozen` (Canonical single-path `SimEngine`)  
**Standard:** Strict zero look-ahead bias, pre-registered chronological splits, and deterministic gating.  
**Last Audited & Updated:** `2026-09-20T14:05:00Z` (Draft v3.1)  

---

## 1. Principles & Non-Negotiable Protocol Rules

1. **Regime Segregation & RTH Definition**:
   - Weekday US-RTH (**13:30–20:00 UTC / 09:30–16:00 ET**) is primary for equity / ETF / commodity / index perps.
   - Crypto perps are evaluated under weekday-all-hours (primary) and weekday-US-RTH (secondary).
   - Weekend results **do not transfer** to weekdays. Weekend trading is evaluated strictly as a separate, secondary regime (`WEEKEND-ONLY, NOT TRANSFERABLE`).
   - Weekend and weekday performance metrics are **never pooled** into one headline number.

2. **Chronological Splits & 5-Day Out-of-Sample Window (Zero Data Leakage)**:
   - Chronological day-blocks only (no random k-fold, bootstrap shuffling, or cross-validation).
   - **Tune Week (In-Sample / Tuning)**: Monday 2026-09-21 00:00 UTC through Friday 2026-09-25 23:59 UTC (5 full weekdays).
   - **Parameter Freeze**: Saturday 2026-09-26 12:00 UTC. All hyperparameters, spreads, skew coefficients, and threshold rules are committed to git and tagged (`prereg-v3.1` / `v0.3.0-frozen`).
   - **Validation Week (Out-of-Sample / OOS Testing)**: Monday 2026-09-28 00:00 UTC through Friday 2026-10-02 23:59 UTC (**5 full OOS weekdays**).
   - **Recommendation for G2**: Extend OOS to 10 weekdays (Mon 09-28 → Fri 10-09, recorder through Sun 10-11) if pilot statistical power at 5 days is borderline.
   - **Single-Shot OOS Evaluation**: The OOS walk-forward evaluation is executed **once** after parameter freeze via `scripts/run_oos.py`. Any iterative re-tuning on OOS data instantly invalidates the run.

3. **Multi-Day Consistency & Outlier Protection**:
   - Criterion 3 requires $\ge 3$ out of 5 OOS weekdays positive ($k \ge 3$).
   - Criterion 3 enforces that no single day contributes $> 50\%$ of total net PnL, preventing outlier-driven false positives.

4. **Primary Gating Model & World Independence**:
   - Primary deployment gate: **Fill Model C (Trade strictly through quote price by at least 1 tick)** evaluated on its independent simulation world.
   - Fill Model B (Queue-Aware FIFO with volume depletion) is tracked as reference.
   - Fill Model A (Touch) is an unconstrained diagnostic upper bound only.

5. **Empirical Wire Latency Sampling & Pre-Declared Scenarios**:
   - Latency distribution is sampled from canonical empirical measurements (`latency/latency_summary.json`): REST $p50 = 173.99\text{ ms}$, $p95 = 386.86\text{ ms}$, one-way entry $87.0\text{ ms}$, one-way feed $81.34\text{ ms}$.
   - Flagged as `PROVISIONAL` pending testnet order placement permissions.
   - **Pre-Declared Latency Grid**: $25\text{ ms}$ (co-located benchmark), $60\text{ ms}$, $150\text{ ms}$, $300\text{ ms}$, and $700\text{ ms}$. Gating scenario is evaluated at empirical distribution with stress test at $p95 + 500\text{ ms} = 886.86\text{ ms}$.

---

## 2. Pre-Registered Candidate Universe & Strategy Grid

Based on empirical data sufficiency from the WS-G pilot analysis (`research/pilot_summary.md`), candidate markets are selected strictly based on measured liquidity:

### 2.1 Primary Candidate Universe (≤ 6 Markets)

| Symbol | Category | Tick Size | Step Size | Min Executable Clip | Pilot Trades/Hr | Expected 5D N (Model C) | Power Gating Status |
|---|---|---|---|---|---|---|---|
| `BTC-USD` | Mega-Cap Crypto Control | 0.1 | 0.0001 | $8.12 | 2,445.6 | 239.7 | **FEASIBLE** |
| `ETH-USD` | Large-Cap Crypto Control | 0.01 | 0.001 | $5.00 | 520.8 | 185.0 | **FEASIBLE** |
| `SOL-USD` | High-Beta Layer 1 | 0.01 | 0.01 | $5.00 | 671.9 | 240.2 | **FEASIBLE** |
| `HYPE-USD` | Liquid Perp Candidate | 0.001 | 0.0001 | $9.21 | 116.5 | 145.5 | **FEASIBLE** |
| `ZEC-USD` | Mid-Cap Liquid Alt | 0.001 | 0.00001 | $14.87 | 113.6 | 132.0 | **FEASIBLE** |
| `CASHCAT-USD` | High-Turnover Alt | 0.0001 | 1.0 | $5.00 | 67.5 | 115.0 | **FEASIBLE** |

*Pre-Declared `INSUFFICIENT DATA` Universe (Weekend Status)*:  
Equities and commodities perps (`QQQ-USD`, `SPY-USD`, `NVDA-USD`, `AMD-USD`, `TSLA-USD`, `GOOGL-USD`, `SPCX-USD`, `SLV-USD`, `GLD-USD`) show near-zero taker volume during weekend trading ($< 10\text{ trades/hr}$). They are pre-declared `INSUFFICIENT DATA` pending the Monday 12:00 UTC re-scan during US cash market hours (13:30–20:00 UTC).

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

*(Note: `Avellaneda_Stoikov` was tested in WS-G and yielded 0 fills on 20/20 markets; it is classified as `NOT TUNABLE` and removed from the active candidate grid).*

**Paired Control Baselines (Run concurrently on identical event stream)**:
- **`DoNothing`**: Zero quotes, zero fills, 0 bps return.
- **`RandomSide`**: Randomly quotes bid or ask with identical 5 bps spread to isolate structural selection edge.

### 2.3 Tune-Week Selection Rule (Mandate §10.4)
Per (market, strategy), the single configuration that maximizes tune-week Model-C net bps per fill subject to $N \ge 30$ fills will enter OOS testing. In case of ties, the configuration with smaller spread is selected. This rule uniquely bounds the multiple testing family ($m \le 18$).

---

## 3. Formal Hypotheses & Statistical Power Framework

### 3.1 Formal Hypotheses

- **$H_1$ (Primary Hypothesis: Positive Net Expectancy)**:  
  For each pre-declared candidate $(M, S)$, the mean net bps per fill under Fill Model C after all exchange fees (2.25 bps taker exit, 0.0 bps maker rebate per Amendment 2026-09-20 / W-04) and funding drag satisfies:
  $$\mu_{\text{net}} > 0 \quad \text{and} \quad \text{Lower Bound of } 90\% \text{ Bootstrap CI} > 0$$
- **$H_2$ (Control Dominance over DoNothing)**:  
  Paired daily difference against `DoNothing` ($0\text{ bps}$) has a positive one-sided $90\%$ confidence lower bound.
- **$H_3$ (Structural Edge over RandomSide)**:  
  Paired daily difference against `RandomSide` has a positive sample mean ($\Delta_{\text{mean}} > 0$) on $\ge 3$ of 5 OOS weekdays.

### 3.2 Power Analysis & Multiple Testing Correction

- **Required Sample Size Formula (Mandate v3 §12.4 & Finding V-25)**:
  $$n_{\text{req}} = \left(\frac{(z_\alpha + z_\beta) \cdot \sigma}{\text{edge}}\right)^2 \cdot \text{DEFF}$$
  Where:
  - $z_\alpha = 1.2816$ ($\alpha = 0.10$ one-sided)
  - $z_\beta = 0.8416$ ($80\%$ power)
  - Combined multiplier: $(z_\alpha + z_\beta)^2 \approx 4.508$ (vs legacy understated $1.6384$)
  - $\text{DEFF} = 1.25$ accounts for intra-day hour-block correlation
  - $\sigma$ is computed strictly from empirical net bps when $N \ge 30$; **never imputed**
- **Multiple Testing Control**: **Holm–Bonferroni step-down correction** applied across the family of pre-declared hypotheses ($m \le 18$). Both raw and adjusted $p$-values will be reported.
- **Inference**: Day-level primary analysis (5 OOS days $\implies t$ with 4 d.f.) plus 1-hour block bootstrap as secondary interval.

---

## 4. Pre-Registered Validation Criteria (Mandatory Gate G4)

### 4.1 Preconditions (Engineering Health)
Before statistical criteria are evaluated, the run must satisfy all engineering preconditions:
1. Multi-version CI clean on Python 3.12 and Python 3.14 (`scripts/ci.sh`).
2. Mutation testing harness catches $\ge 16/16$ deliberate mutations (`scripts/mutation_check.py`).
3. Deterministic replay parity verified on non-zero fills (`scripts/test_replay_parity.py`).
4. Parameter freeze tag exists (`prereg-v3.1`).

### 4.2 Statistical Validation Criteria
For any candidate $(M, S)$ to achieve a verdict of `VALIDATED`, all of the following must hold:

| Criterion # | Requirement | Threshold | Failure Action |
|---|---|---|---|
| **1. Sample Size** | Simulated fills across 5-day weekday OOS window under Model C | $N_C \ge n_{\text{req}}(1.0\text{ bps})$ from power table ($N \ge 100$) | Mark `INSUFFICIENT DATA` |
| **2. Net Expectancy & CI** | Net bps per fill after Holm–Bonferroni correction | Mean Net bps $> 0$ AND Lower Bound of 90% CI $> 0$ | Mark `NOT VALIDATED` |
| **3. Multi-Day Consistency** | Daily profitability across 5 OOS weekdays | Net PnL $> 0$ on $\ge 3$ of 5 OOS weekdays ($\ge 60\%$); Max single day $\le 50.0\%$ total PnL | Mark `NOT VALIDATED` |
| **4. Cost & Capital Envelope** | Net of 2.25 bps taker exit fee and funding; drawdown and inventory limits | Net PnL $> 0$; Max Intraday Drawdown $< 10.0\%$; Zero inventory limit breaches | Mark `NOT VALIDATED` |
| **5. Baseline Dominance** | Comparison against paired controls on identical event stream | Beats `DoNothing` (positive lower bound); Beats `RandomSide` on $\ge 3/5$ days | Mark `NOT VALIDATED` |
| **6. Capital Scale Invariance** | Performance across capital tiers | Evaluated at both **$50 and $100** capital; if viable only at $100, flagged as `CAPITAL_CONSTRAINED` | Flag capital dependency |

---

## 5. Dated Amendment Log

- **2026-09-20 (Pre-Registration v3.1 Draft)**:
  1. *Status Reclassification*: Changed from invalid "COMMITTED & LOCKED" to honest "DRAFT" until Friday 2026-09-25 EOD UTC per Mandate v3 §13.
  2. *Empirical Pilot Alignment*: Updated universe trade counts and expected fills from WS-G pilot analysis (`research/pilot_summary.md`), removing all synthetic weekday multipliers.
  3. *Statistical Power Correction*: Replaced flawed $n \approx (1.28\sigma/\text{edge})^2$ with complete formula incorporating Type II error $\beta=0.80$, $(z_\alpha+z_\beta)^2 \approx 4.508$, and $\text{DEFF}=1.25$ cluster inflation (V-25).
  4. *Control Hypotheses Repair*: Rewrote $H_3$ to require paired daily difference mean $> 0$ against `RandomSide`, removing ill-posed `RandomSide > DoNothing` requirement (V-26d).
  5. *Precondition Separation*: Moved unit tests, mutation tests, and parity checks out of statistical criteria into formal engineering preconditions (V-26e).
  6. *Avellaneda-Stoikov Deprecation*: Officially labeled `Avellaneda_Stoikov` as `NOT TUNABLE` due to 0 fills across all 20 markets and removed it from active candidate grid (V-24g).
  7. *Canonical Latency Pinning*: Updated latency figures to canonical empirical measurements ($p50 = 173.99\text{ ms}$, $p95 = 386.86\text{ ms}$, stress $= 886.86\text{ ms}$) from `latency/latency_summary.json` (V-27).
  8. *OOS Assurance Statement*: **Zero Out-of-Sample (OOS) data has been collected or evaluated. The OOS test window remains strictly in the future (Sep 28 – Oct 2, 2026).**
  9. *Maker Rebate Elimination (Mandate v5 §2 W-04)*: Removed +0.75 bps maker rebate assumption. Verified base fee tier charges 0.0 bps maker fee with 0.0 bps rebate. Net fee drag under taker-exit assumptions updated to 2.25 bps (2.25 bps taker fee, 0.0 bps maker rebate). All candidate feasibility evaluations recalculated without maker rebate.
- **2026-09-20 (Pre-Registration v3)**: Initial v3 draft incorporating pilot analysis.
- **2026-09-19 (Corrective Pass 2)**: Expanded OOS window to 5 days; corrected multi-day stability criteria.
