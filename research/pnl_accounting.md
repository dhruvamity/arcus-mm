# PnL Accounting Identity & Markout Attribution Specification

**Status:** IMPLEMENTED & TEST-VERIFIED  
**Date:** September 20, 2026  
**Scope:** Fulfills Mandate Sections 12, 13, 14, 15 of `prompt.md`  

---

## 1. Executive Summary

This specification formalizes the quantitative accounting system and research attribution models for Arcus perpetuals market making. It establishes:
1. A strict balance-sheet identity enforced at every fill and settlement tick without double counting.
2. Executable-side liquidation for forced risk flattens (charging taker fees and realistic slippage).
3. Discrete time-aware funding cash flows applied to instantaneous positions held at funding ticks.
4. An empirical forward markout engine covering $[100\text{ms}, 500\text{ms}, 1\text{s}, 5\text{s}, 10\text{s}, 30\text{s}, 60\text{s}]$ kept strictly separate from the accounting ledger.

---

## 2. Fundamental Balance-Sheet Identity

At any simulation or live timestamp $t$, portfolio equity $E_t$ is defined by:
$$E_t = \text{Cash}_t + \text{Position}_t \cdot S_t$$
where $\text{Cash}_t$ is the quote currency collateral balance, $\text{Position}_t$ is open contract inventory in base asset units ($+ \text{long}, - \text{short}$), and $S_t$ is the contemporaneous mid price.

### 2.1 Attribution Decomposition

Net PnL over interval $[0, t]$ satisfies the exact balance-sheet equality:
$$\Delta E_t = E_t - E_0 = \Pi_{\text{realized}} + \Pi_{\text{mtm}} + \Pi_{\text{funding}} - C_{\text{maker\_fee}} - C_{\text{taker\_fee}}$$

Where:
- **$\Pi_{\text{realized}}$ (Realized Trading PnL):** Accumulated spread capture and inventory round-trips:
  - For long reduction: $(P_{\text{exit}} - \bar{P}_{\text{entry}}) \cdot Q$
  - For short reduction: $(\bar{P}_{\text{entry}} - P_{\text{exit}}) \cdot Q$
- **$\Pi_{\text{mtm}}$ (Unrealized Mark-to-Market):**
  $$\Pi_{\text{mtm}} = \text{Position}_t \cdot (S_t - \bar{P}_{\text{entry}})$$
- **$\Pi_{\text{funding}}$ (Funding Cash Flows):** Discrete sum of all periodic settlement payments:
  $$\Pi_{\text{funding}} = \sum_{k} \left( - \text{Position}_{t_k} \cdot S_{t_k} \cdot F_{t_k} \right)$$
- **$C_{\text{maker\_fee}}$:** 0 bps maker fee on passive limit fills.
- **$C_{\text{taker\_fee}}$:** 2.25 bps taker fee incurred on emergency risk flattens or aggressive cross fills.

Every component is mutually coherent, and the test suite verifies that `attrib_sum == net_pnl` within $10^{-5}$ precision at every event tick.

---

## 3. Forced Flattening & Emergency Exits (Mandate §13)

Under Mandate Section 13, emergency risk management and kill-switch executions **must never execute at mid price**:
- **Long Inventory Flatten:** Sold aggressively against the contemporaneous **Best Bid** with non-zero modeled slippage:
  $$P_{\text{exec}} = P_{\text{bid}} \cdot \left(1 - \frac{\text{slippage\_bps}}{10,000}\right)$$
- **Short Inventory Flatten:** Bought aggressively against the contemporaneous **Best Ask** with non-zero modeled slippage:
  $$P_{\text{exec}} = P_{\text{ask}} \cdot \left(1 + \frac{\text{slippage\_bps}}{10,000}\right)$$
- **Fee:** Automatically charged standard Arcus taker fee of 2.25 bps ($0.000225 \cdot \text{Notional}$).

Zero slippage or zero fee credits for forced exits are strictly prohibited.

---

## 4. Time-Aware Funding Engine (Mandate §12)

Arcus perpetual funding operates on discrete settlement intervals (hourly / 8-hourly):
1. **Settlement Injection:** Discrete settlement events are inserted into the chronological replay event stream at exact settlement timestamps $t_k$.
2. **Instantaneous State:** The funding rate $F_{t_k}$ applies **strictly to the position held at $t_k$**:
   $$\text{Cash}_{t_k} \leftarrow \text{Cash}_{t_k} - \left(\text{Position}_{t_k} \cdot S_{t_k} \cdot F_{t_k}\right)$$
3. **No Post-Hoc Smearing:** Funding is never approximated by smearing a single initial funding rate across the total simulation duration.

---

## 5. Forward Markout Engine & Adverse Selection Diagnostics (Mandate §14)

Adverse selection is evaluated as an empirical markout against future reference prices across standard horizons:
$$H \in [100\text{ms}, 500\text{ms}, 1\text{s}, 5\text{s}, 10\text{s}, 30\text{s}, 60\text{s}]$$

### 5.1 Formulation
For a passive maker fill at timestamp $t_{\text{fill}}$ with price $P_{\text{fill}}$:
- **Maker BUY fill (adverse if future price drops):**
  $$\text{AS}_{\text{bps}}(H) = \frac{P_{\text{fill}} - S_{t_{\text{fill}} + H}}{P_{\text{fill}}} \cdot 10,000$$
- **Maker SELL fill (adverse if future price rises):**
  $$\text{AS}_{\text{bps}}(H) = \frac{S_{t_{\text{fill}} + H} - P_{\text{fill}}}{P_{\text{fill}}} \cdot 10,000$$

### 5.2 Censoring & Boundary Handling
If $t_{\text{fill}} + H > t_{\text{end}}$, the observation is **strictly dropped** (never clamped to final price). Sample size $N(H)$ naturally contracts as horizon $H$ approaches the end of the recording.

### 5.3 Reporting Metrics
For each horizon $H$, the engine computes:
- $N$: Sample count of resolvable fills
- Mean markout ($\text{bps}$)
- Median markout ($\text{bps}$)
- Quantiles ($P_{25}, P_{75}, P_5, P_{95}$)
- 90% Confidence Interval: $\bar{x} \pm 1.645 \cdot \frac{s}{\sqrt{N}}$
- Breakdown by side: Bid fills vs. Ask fills
- Breakdown by size bucket at 5s horizon: Small ($<\$15$), Medium ($\$15-\$50$), Large ($>\$50$)

Markout metrics are archived strictly as research diagnostics and are **never subtracted from the accounting equity** (avoiding double counting).
