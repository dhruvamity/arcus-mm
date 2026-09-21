# Arcus MM — Farming Economics, Fee Drag & Venue Compliance

**Date:** `2026-09-20`  
**Status:** `EMPIRICAL ANALYSIS — HONEST ACCOUNTING`  
**Target Venue:** Arcus Perpetuals (`https://arcus.xyz`)  
**Mandate Reference:** Mandate v5 §6 (Workstream D)  

---

## Executive Summary

This document presents an empirical, non-speculative economic model of passive market-making ("farming") on Arcus perpetual futures. It directly answers two questions:
1. **What volume can a passive quoting strategy generate at minimum clip?**
2. **What does that volume cost to manufacture in fees, adverse selection, and inventory unwinds?**

All volume and cost estimates are derived strictly from the verified WS-G pilot dataset (~20h tape across 20 markets, re-evaluated under canonical `SimEngine` Gate G1 conditions) without synthetic multipliers. Reward value is set to **$0.00** because Arcus has published no official tokenomics or points conversion schedule.

---

## 1. Volume Model per Market (Unique Model B/C Fills at Minimum Clip)

### 1.1 Methodology & Invariants
- **Minimum Executable Clip:** Each market requires meeting venue constraints:
  - Snap to price `tick_size` and size `step_size`
  - Venue minimum order notional of **$5.00** (`minOrderNotional` per Arcus API metadata)
  - Target minimum clip sizing: $10.00 notional (buffer over $5 floor to avoid rejection on adverse mid shifts)
- **Zero Synthetic Multipliers:** Fills are taken directly from empirical Model B (FIFO queue with 50ms speed bump) and Model C (trade-through by $\ge 1$ full tick) fill rates.
- **Regime Stratification:**
  - **Weekday US-RTH:** 13:30–20:00 UTC (6.5 hours/day)
  - **Weekday Other / Off-Hours:** 00:00–13:30 and 20:00–24:00 UTC (17.5 hours/day for 24/7 crypto; equity perps trade in restricted off-hours bands)
  - **Weekend:** Saturday 00:00 to Sunday 24:00 UTC (48 hours; crypto 24/7, equities illiquid/closed)

### 1.2 Volume Generation Table by Market & Regime

Estimates assume resting single-clip quotes ($10 notional per clip) on both sides using `Adaptive_4bps` (or `FixedSpread_6bps` where adaptive is uncalibrated):

| Market | Asset Class | Min Clip ($) | Model C Fills/Hr | Daily Fills (RTH 6.5h) | Daily Fills (Other 17.5h) | Daily Fills (Weekend 24h) | Estimated Daily Notional ($) | Estimated 30D Notional ($) |
|---|---|---|---|---|---|---|---|---|
| **BTC-USD** | Crypto | $10.00 | 1.20 | 7.8 | 21.0 | 28.8 | $288 | $8,640 |
| **ETH-USD** | Crypto | $10.00 | 4.21 | 27.4 | 73.7 | 101.0 | $1,010 | $30,300 |
| **SOL-USD** | Crypto | $10.00 | 1.85 | 12.0 | 32.4 | 44.4 | $444 | $13,320 |
| **HYPE-USD** | Crypto | $10.00 | 0.30 | 2.0 | 5.3 | 7.2 | $72 | $2,160 |
| **ZEC-USD** | Crypto | $10.00 | 0.80 | 5.2 | 14.0 | 19.2 | $192 | $5,760 |
| **SPY-USD** | Equity Perp | $10.00 | 6.26 | 40.7 | 0.0* | 0.0* | $407 | $8,954** |
| **QQQ-USD** | Equity Perp | $10.00 | 1.95 | 12.7 | 0.0* | 0.0* | $127 | $2,794** |
| **AMD-USD** | Equity Perp | $10.00 | 5.23 | 34.0 | 0.0* | 0.0* | $340 | $7,480** |
| **GLD-USD** | Commodity Perp | $10.00 | 2.53 | 16.4 | 0.0* | 0.0* | $164 | $3,608** |

*\*Equity perps are assumed flat outside US-RTH (13:30–20:00 UTC) due to wide spreads, low depth, and weekend close.*  
*\*\*Equity perps 30D volume is calculated across 22 trading days per month.*

---

## 2. Cost Model & Breakeven Analysis

### 2.1 Fee Drag & Slippage Accounting
Per canonical venue parameters loaded from [`configs/venue_verified.yaml`](../configs/venue_verified.yaml):
1. **Maker Rebate:** `0.0 bps` (Base tier maker fee is 0 bps; there is **no maker rebate** per W-04 audit correction).
2. **Taker Exit Fee:** `2.25 bps` (Charged on all aggressive taker orders, inventory stop-outs, speed-bump forced unwinds, and liquidations).
3. **Adverse Selection (Markout Drag):** Measured empirical price decay at 5s/15s/60s post-fill.
4. **Funding Drag:** Hourly discrete cash settlement based on premium to index.
5. **Inventory Unwind Ratio:** Empirically ~35% of resting fills require active taker rebalancing/unwinds to stay within inventory limits ($\le 2$ clips).

### 2.2 Mathematical Identity for Net Edge per Notional Traded

$$\text{Net BPS} = \text{Half-Spread}_{\text{earned}} - \text{Adverse Selection}_{\tau} - (\text{Taker Fee} \times \text{Unwind Share}) - \text{Funding}$$

$$\text{Cost per \$1,000,000 Traded} = -\text{Net BPS} \times \$100.00$$

### 2.3 Empirical Cost Breakdown (Model C Fills, 95% Confidence Intervals)

| Candidate Market | Half-Spread (bps) | Adverse Selection (15s markout, bps) | Taker Fee Drag (2.25 bps × 35%) | Funding Drag (bps/fill) | Net Edge (bps) | 95% CI (bps) | Cost per $1M Traded ($) | Breakeven Status |
|---|---|---|---|---|---|---|---|---|
| **ETH-USD** (`Adaptive_4bps`) | +2.00 | -1.85 | -0.79 | -0.05 | **-0.69** | [-1.08, -0.30] | **+$69.00 cost** | **UNPROFITABLE** (Below Breakeven) |
| **SOL-USD** (`Adaptive_4bps`) | +2.00 | -2.10 | -0.79 | -0.08 | **-0.97** | [-1.40, -0.54] | **+$97.00 cost** | **UNPROFITABLE** (Below Breakeven) |
| **SPY-USD** (`Adaptive_4bps`) | +0.65 | -0.80 | -0.79 | -0.02 | **-0.96** | [-1.32, -0.60] | **+$96.00 cost** | **UNPROFITABLE** (Below Breakeven) |
| **AMD-USD** (`FixedSpread_6bps`) | +3.00 | -2.40 | -0.79 | -0.04 | **-0.23** | [-0.80, +0.34] | **+$23.00 cost** | **BORDERLINE / INCONCLUSIVE** |
| **GLD-USD** (`Adaptive_4bps`) | +2.00 | -1.55 | -0.79 | -0.03 | **-0.37** | [-0.92, +0.18] | **+$37.00 cost** | **BORDERLINE / INCONCLUSIVE** |
| **BTC-USD** (`FixedSpread_6bps`) | +0.50 | -0.65 | -0.79 | -0.02 | **-0.96** | [-1.55, -0.37] | **+$96.00 cost** | **UNPROFITABLE** (Below Breakeven) |

### 2.4 Breakeven Verdict
> [!WARNING]
> **Zero candidates achieve statistically significant positive net edge at base fee tier.**  
> Without a maker rebate (W-04), every $1,000,000 of volume manufactured passively costs between **$23 and $97 in net cash drag** due to the 2.25 bps taker exit penalty and adverse selection. Running a market maker purely to "farm volume" without external compensation is a cash-negative operation.

### 2.5 Avellaneda-Stoikov Empirical Performance (Finding V-36 Remediated)
Prior to remediation of Finding V-36, Avellaneda-Stoikov produced 0 fills across all markets due to an uncalibrated default ($\kappa = 1.5$, yielding reservation spread $> 120\%$). Following the wiring of `calibrate_kappa_from_trades()` and relaxation of the arrival intensity clamp to high-frequency regimes:
- **BTC-USD (`Avellaneda_Stoikov`):** Empirically fitted $\kappa \approx 9,877$ brings reservation spread down to ~2.0 bps. Model C fill rate reaches **45.04 fills/hr** (5,405 expected 5-day fills, $\sigma = 0.46$ bps, $N_{\text{req}} = 30$, **FEASIBLE**).
- **ETH-USD & SOL-USD:** Empirically calibrated $\kappa \approx 1,058$ and $\approx 1,444$ produce active quoting with 0.04 to 0.08 fills/hr under Model C (insufficient for 5-day statistical power without further tuning of risk aversion $\gamma$).
- **Inventory Skew Economics:** Inventory-dependent reservation pricing lowers adverse selection compared to static fixed-spread quoting, but the base-tier absence of maker rebates (W-04) and the 2.25 bps taker rebalance fee drag keep net operational edge near breakeven or slightly negative unless maker rebates are unlocked.

---

## 3. Reward Status & Tokenomics Audit

### 3.1 Official Documentation Review
An exhaustive review of Arcus documentation ([`https://docs.arcus.xyz`](https://docs.arcus.xyz)) as of September 2026 reveals:
1. **No Native Token Published:** Arcus has published no token contract, no token ticker, and no tokenomics whitepaper.
2. **No Points Program Formally Specified:** The official docs describe order mechanics, RFQ, margin modes, and notifications, but have **zero documentation regarding trading points, reward multipliers, or airdrop eligibility schedules**.
3. **Leaderboard Scope:** Arcus operates an all-traders leaderboard endpoint (`GET /v1/leaderboard`), but it tracks volume, fees, and realized PnL for ranking only. No point allocation formula is documented.

### 3.2 Imputation Policy
- **Assumed Reward Value:** **$0.0000**.
- Any quantitative model that assumes future token value, points conversion rates, or FDV projections is strictly unscientific and prohibited.
- If rewards are later announced, they must be treated as contingent non-operating revenue with unknown strike price and zero baseline value.

---

## 4. Legal Compliance & Conduct Rules

### 4.1 Terms of Use Summary
Per Arcus Terms of Use ([`https://arcus.xyz/legal/terms`](https://arcus.xyz/legal/terms)) and Disclaimer ([`https://docs.arcus.xyz/concepts/disclaimer`](https://docs.arcus.xyz/concepts/disclaimer)):
1. **Restricted Jurisdictions:** Arcus is strictly unavailable to persons or entities residing in, located in, or incorporated in:
   - The United States of America
   - The United Kingdom
   - Canada
   - Sanctioned jurisdictions (OFAC/UN/EU lists)
   - Geo-restrictions are programmatically enforced via `GET /v1/compliance/status` returning HTTP `403` with machine-readable error code `GEO_RESTRICTED`.
2. **Prohibition of Circumvention:** Accessing the protocol via VPN, proxy, or IP obfuscation to bypass territorial restrictions constitutes a material breach of the Terms of Use.
3. **KYC / Screening:** Public address screening occurs at key creation and withdrawal.

### 4.2 Repository Compliance Invariants
1. **Single Account Invariant:** All research and automation interact strictly via a single master Ethereum address and subaccount index. No multi-accounting or Sybil clusters.
2. **Zero Wash Trading / Zero Self-Trading:** No orders may ever cross against another order submitted by the same participant.
3. **Startup & Runtime Self-Cross Checks:**
   - As implemented in [`src/exec/live_engine.py`](../src/exec/live_engine.py), the quoting loop validates that candidate bid prices are strictly less than candidate ask prices (`bid_price < ask_price`).
   - Strategy spread configurations $\le 0$ bps are rejected at engine startup with `ValueError`.
   - Any state where resting orders would self-match triggers an immediate `cancelAllOrders` and halts execution.

---

## 5. Scale Statement (Share of Arcus Venue Volume)

### 5.1 Monthly Quoting Volume Estimate
Summing the empirical 30-day notional estimates across all feasible candidate markets at minimum clip ($10 notional):
- **Crypto Portfolio (ETH + SOL + BTC + ZEC + HYPE):** ~$60,000 / month
- **Equity / Commodity Portfolio (SPY + AMD + QQQ + GLD):** ~$23,000 / month
- **Total Combined Monthly MM Volume:** **~$83,000 / month** ($2,700–$3,000 / day).

### 5.2 Venue Market Share Comparison
- **Arcus Reported Daily Venue Volume:** ~$100,000,000 / day ($100M/day, or ~$3,000,000,000 / month across all perpetual markets, as reported via public venue stats and leaderboard aggregates).
- **MM Strategy Daily Share:**
  $$\frac{\$2,800}{\$100,000,000} \approx 0.0028\% \quad (2.8 \text{ parts per hundred thousand})$$
- **MM Strategy Monthly Share:**
  $$\frac{\$83,000}{\$3,000,000,000} \approx 0.0028\%$$

### 5.3 Economic Conclusion
1. **Negligible Market Impact:** Generating $83,000 in monthly volume represents less than $0.003\%$ of Arcus's aggregate activity. It creates zero market distortion and zero systemic footprint.
2. **Farming Inefficiency:** Because volume generation incurs a net cost of ~$50 to $90 per $1M traded, manufacturing $83,000 of monthly volume produces an **expected net cash loss of $4.15 to $7.47 per month** in adverse selection and taker unwinds.
3. **Strategic Recommendation:** Passive quoting on Arcus cannot be justified as an economic "farming" strategy in the absence of explicit, verified maker fee rebates or contractual market-maker incentives. Quoting should only proceed if pure alpha/microstructure edge is demonstrated on out-of-sample data.
