# Multiple-Testing Control & Statistical Inference Specification

**Status:** IMPLEMENTED & TEST-VERIFIED  
**Date:** September 20, 2026  
**Scope:** Fulfills Mandate Section 19 of `prompt.md`  

---

## 1. Executive Summary

In algorithmic market making research, searching across multiple markets, strategies, spread multipliers, and inventory skew factors without statistical correction induces severe false-discovery rates (data snooping / p-hacking).

Mandate Section 19 prohibits declaring any strategy "validated" or "Holm-Bonferroni controlled" without a formal pre-declared hypothesis family and inferential correction. This document specifies the exact inferential pipeline implemented in `src/walk_forward.py`.

---

## 2. Pre-Declared Hypothesis Family

The candidate hypothesis family $\mathcal{F}$ consists of $M$ pre-declared hypotheses:
$$H_{0, m}: \mu_m \le 0 \quad \text{vs.} \quad H_{1, m}: \mu_m > 0$$
where $\mu_m$ is the expected net profit (in basis points per fill) for candidate configuration $m = (\text{Market}, \text{Strategy}, \text{Parameters})$.

### 2.1 Family Enumeration ($M = 28$ Configurations)
The formal evaluation matrix encompasses:
- **Markets (7):** `HYPE-USD`, `ZEC-USD`, `NEAR-USD`, `SPCX-USD`, `LIT-USD`, `UNI-USD`, `SLV-USD`
- **Strategies (4):**
  1. `FixedSpreadStrategy` (S0 Control Baseline)
  2. `AvellanedaStoikovStrategy` (S1 Dimensionally Corrected)
  3. `VolatilityClockStrategy` (S2 Realized Volatility Sized)
  4. `AdaptiveMicrostructureStrategy` (S3 OFI + Microprice Skew)

Total family size: $M = 7 \times 4 = 28$ testing configurations.

---

## 3. Inferential Test Statistic & p-Value Formulation

For each configuration $m$, the backtester generates a sequence of $N_m$ executed fills with net returns $r_i$ (in bps):
$$r_i = \begin{cases}
\frac{S_{\text{mid}, i} - P_{\text{fill}, i}}{S_{\text{mid}, i}} \cdot 10,000 - \text{Fee}_{\text{bps}} & \text{for maker BUY} \\
\frac{P_{\text{fill}, i} - S_{\text{mid}, i}}{S_{\text{mid}, i}} \cdot 10,000 - \text{Fee}_{\text{bps}} & \text{for maker SELL}
\end{cases}$$

### 3.1 Sample Statistics
$$\bar{\mu} = \frac{1}{N} \sum_{i=1}^N r_i, \quad s = \sqrt{\frac{1}{N-1} \sum_{i=1}^N (r_i - \bar{\mu})^2}$$

### 3.2 Student's t-Statistic
$$t = \frac{\bar{\mu}}{s / \sqrt{N}}$$

### 3.3 Two-Sided p-Value
Using the Student's t-distribution with $\nu = N - 1$ degrees of freedom:
$$p = 2 \cdot \left[1 - F_t(|t|, \nu)\right]$$
where $F_t$ is the cumulative distribution function of the Student's t-distribution.

---

## 4. Step-Down Holm-Bonferroni FWER Control

To control the Family-Wise Error Rate at overall significance level $\alpha = 0.05$:

1. **Sort p-values:** Order the $M$ hypotheses in ascending order of raw p-values:
   $$p_{(1)} \le p_{(2)} \le \dots \le p_{(M)}$$
2. **Sequential Threshold Comparison:** For rank $k = 1, 2, \dots, M$:
   $$\alpha_k = \frac{\alpha}{M - k + 1}$$
3. **Rejection Rule:**
   - If $p_{(k)} \le \alpha_k$, reject $H_{0, (k)}$ (statistically significant positive expectancy).
   - The moment $p_{(k)} > \alpha_k$, **stop testing** and retain all remaining null hypotheses $H_{0, (j)}$ for $j \ge k$.

### 4.1 Strict Empirical Primacy
Statistical significance is a necessary condition, but **never sufficient** for live deployment. An out-of-sample configuration is only validated if it satisfies both the Holm-Bonferroni test AND all machine-checkable economic gates in Mandate Section 21.
