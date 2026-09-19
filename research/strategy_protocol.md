# Pre-Registered Strategy Protocol & Validation Gates

**Status:** PRE-REGISTERED & HARD-LOCKED  
**Date:** September 20, 2026  
**Scope:** Fulfills Mandate Sections 18, 20, 21 of `prompt.md`  

---

## 1. Pre-Registered Chronological Windows (Mandate §18)

Per Mandate Section 18, all parameter tuning, model freezing, and out-of-sample evaluations follow an immutable temporal sequence:

| Phase | Start Date (UTC) | End Date (UTC) | Rules & Constraints |
|---|---|---|---|
| **In-Sample Tuning** | 2026-09-21 00:00:00 | 2026-09-25 23:59:59 | Exploration permitted; hyperparameter searches; feature selection. |
| **Parameter Freeze** | 2026-09-26 12:00:00 | — | Complete codebase and parameter freeze; cryptographic commit hash locked. |
| **Out-of-Sample (OOS)** | 2026-09-28 00:00:00 | 2026-10-02 23:59:59 | Strictly blind 5-day evaluation; ZERO parameter adjustments; one-shot run. |

### 1.1 Strict Prohibitions
- **NO random k-fold cross-validation** (violates temporal causality in financial time series).
- **NO out-of-sample retuning** or post-hoc threshold adjustment.
- **NO parameter modifications** after the freeze deadline at 2026-09-26 12:00 UTC.

---

## 2. Required Empirical Controls (Mandate §20)

Every candidate strategy must be evaluated concurrently against two mandatory controls executed on the **identical event stream, latency, fee, fill model, and capital settings**:

1. **S0 — Do-Nothing Baseline:**
   - Quotes posted: 0
   - Fills generated: 0
   - Net PnL: Exactly $\$0.00$
   - Risk: Zero inventory drift
2. **Random-Side Quoting Baseline:**
   - At each event tick, flips a pseudo-random coin to quote either only the Bid or only the Ask.
   - Preserves identical clip notional and spread offset without intelligent inventory skewing or order flow imbalance adaptation.

A strategy is classified as failing if its net PnL fails to exceed both the Do-Nothing baseline and the Random-Side quoting baseline.

---

## 3. Machine-Checkable Validation Gates (Mandate §21)

Every candidate configuration must pass all 8 machine-checkable gates before deployment consideration:

```text
[GATE-1] Fill Sample Size:        N >= 300 fills (N >= 100 on low-frequency markets)
[GATE-2] Positive Net Return:     Mean net bps per fill > 0.0
[GATE-3] Statistical Bounds:      90% Confidence Interval Lower Bound > 0.0 bps
[GATE-4] Temporal Consistency:    Positive daily net PnL on >= 3 out of 5 OOS days
[GATE-5] PnL Concentration:       Max single-day PnL share <= 50% of total PnL
[GATE-6] Drawdown Bound:          Max intraday peak-to-trough drawdown < 10.0%
[GATE-7] Inventory Envelope:      Zero breaches of max capital envelope ($100 cap)
[GATE-8] Fill Monotonicity:       Fills(Model A) >= Fills(Model B) >= Fills(Model C)
```

---

## 4. Capital Scale Specifications

All core backtests must be evaluated at two discrete experimental capital tiers:
1. **$\$50$ Experimental Envelope:** Tests capital constraints, minimum lot sizing constraints, and rate limit replenishability at fractional scale.
2. **$\$100$ Research Scale:** Full standard experimental capital for single-clip market making across candidate pairs.
