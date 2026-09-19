# WS-5 Pilot Market Microstructure & Power Analysis

**Date:** 2026-09-19 19:48:11 UTC  
**Recording Window Analyzed:** Sep 19–20, 2026 (1.44 hours elapsed)  
**Markets Evaluated:** 20 instruments  
**Engine Implementation:** Canonical single-path `SimEngine` (Gate G1 validated)  

## 1. Executive Summary & Feasibility Gating

This pilot evaluates live empirical trade frequencies, spread distributions, and fill yield under Fill Models B and C.
Sample size requirement is derived directly from statistical power theory:

$$n \approx \left(\frac{1.28 \cdot \sigma}{\text{edge}}\right)^2$$

For a candidate strategy to be included in the 5-day OOS evaluation window, its projected sample size must satisfy $E[N] \ge n_{\text{req}}(1.0\text{ bps})$.

## 2. Market Microstructure Summary Table

| Market | Trades/Hr | Spread (p50 bps) | Spread (Mean bps) | Depth ($) | Model B Fills/Hr | Model C Fills/Hr | Expected 5D Fills | Feasibility |
|---|---|---|---|---|---|---|---|---|
| `CASHCAT-USD` | 87.9 | 35.39 | 35.77 | $50 | 9.52 | 9.52 | 2856 | **FEASIBLE** |
| `HYPE-USD` | 563.8 | 3.76 | 3.71 | $50 | 9.0 | 9.0 | 2701 | **FEASIBLE** |
| `ZEC-USD` | 188.7 | 5.15 | 5.89 | $50 | 6.25 | 6.25 | 1874 | **FEASIBLE** |
| `BTC-USD` | 23238.8 | 0.13 | 0.28 | $50 | 7.5 | 7.5 | 1080 | **FEASIBLE** |
| `XRP-USD` | 85.4 | 4.88 | 4.82 | $50 | 4.38 | 3.29 | 986 | **FEASIBLE** |
| `NEAR-USD` | 123.2 | 8.36 | 9.7 | $50 | 2.26 | 2.26 | 678 | **FEASIBLE** |
| `NVDA-USD` | 27.5 | 2.7 | 3.15 | $50 | 1.04 | 1.04 | 311 | **FEASIBLE** |
| `UNI-USD` | 45.1 | 12.43 | 13.45 | $50 | 0.69 | 0.69 | 208 | **FEASIBLE** |
| `LIT-USD` | 80.6 | 10.17 | 10.6 | $50 | 0.64 | 0.64 | 193 | **FEASIBLE** |
| `AAVE-USD` | 10.5 | 5.61 | 6.41 | $50 | 0.52 | 0.52 | 157 | **FEASIBLE** |
| `GOOGL-USD` | 1.3 | 7.7 | 8.38 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |
| `GLD-USD` | 1.5 | 5.48 | 5.08 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |
| `AMD-USD` | 4.8 | 7.93 | 7.64 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |
| `QQQ-USD` | 21.3 | 2.08 | 3.09 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |
| `SLV-USD` | 1.0 | 6.66 | 6.74 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |
| `SOL-USD` | 1833.0 | 0.98 | 0.99 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |
| `SPCX-USD` | 0.8 | 8.51 | 8.78 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |
| `SPY-USD` | 57.5 | 0.13 | 0.45 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |
| `TSLA-USD` | 0.3 | 9.04 | 9.4 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |
| `ETH-USD` | 1435.2 | 0.57 | 0.92 | $50 | 0.0 | 0.0 | 0 | **INSUFFICIENT DATA** |

## 3. Power Analysis & Sample Size Feasibility (Market × Strategy)

| Market | Strategy | Sigma (bps) | N Req (0.5 bps) | N Req (1.0 bps) | N Req (2.0 bps) | Expected 5D N | Gating Status |
|---|---|---|---|---|---|---|---|
| `AAVE-USD` | `FixedSpread_6bps` | 5.95 | 233 | 59 | 30 | 471 | **FEASIBLE** |
| `AAVE-USD` | `Adaptive_4bps` | 5.0 | 164 | 41 | 30 | 157 | **FEASIBLE** |
| `AAVE-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `AAVE-USD` | `VolatilityClock` | 11.26 | 832 | 208 | 52 | 471 | **FEASIBLE** |
| `AMD-USD` | `FixedSpread_6bps` | 0.0 | 30 | 30 | 30 | 1353 | **FEASIBLE** |
| `AMD-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `AMD-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `AMD-USD` | `VolatilityClock` | 0.58 | 30 | 30 | 30 | 1353 | **FEASIBLE** |
| `BTC-USD` | `FixedSpread_6bps` | 2.04 | 30 | 30 | 30 | 720 | **FEASIBLE** |
| `BTC-USD` | `Adaptive_4bps` | 1.89 | 30 | 30 | 30 | 1080 | **FEASIBLE** |
| `BTC-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `BTC-USD` | `VolatilityClock` | 2.76 | 50 | 30 | 30 | 720 | **FEASIBLE** |
| `CASHCAT-USD` | `FixedSpread_6bps` | 28.33 | 5261 | 1316 | 329 | 1954 | **FEASIBLE** |
| `CASHCAT-USD` | `Adaptive_4bps` | 27.04 | 4791 | 1198 | 300 | 2856 | **FEASIBLE** |
| `CASHCAT-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `CASHCAT-USD` | `VolatilityClock` | 31.29 | 6415 | 1604 | 401 | 3232 | **FEASIBLE** |
| `ETH-USD` | `FixedSpread_6bps` | 6.7 | 295 | 74 | 30 | 1633 | **FEASIBLE** |
| `ETH-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `ETH-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `ETH-USD` | `VolatilityClock` | 7.4 | 360 | 90 | 30 | 1547 | **FEASIBLE** |
| `GLD-USD` | `FixedSpread_6bps` | 5.0 | 164 | 41 | 30 | 76 | **FEASIBLE** |
| `GLD-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `GLD-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `GLD-USD` | `VolatilityClock` | 1.09 | 30 | 30 | 30 | 228 | **FEASIBLE** |
| `GOOGL-USD` | `FixedSpread_6bps` | 0.94 | 30 | 30 | 30 | 226 | **FEASIBLE** |
| `GOOGL-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `GOOGL-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `GOOGL-USD` | `VolatilityClock` | 0.87 | 30 | 30 | 30 | 226 | **FEASIBLE** |
| `HYPE-USD` | `FixedSpread_6bps` | 1.88 | 30 | 30 | 30 | 1719 | **FEASIBLE** |
| `HYPE-USD` | `Adaptive_4bps` | 3.32 | 73 | 30 | 30 | 2701 | **FEASIBLE** |
| `HYPE-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `HYPE-USD` | `VolatilityClock` | 2.87 | 54 | 30 | 30 | 491 | **FEASIBLE** |
| `LIT-USD` | `FixedSpread_6bps` | 2.27 | 34 | 30 | 30 | 4063 | **FEASIBLE** |
| `LIT-USD` | `Adaptive_4bps` | 5.0 | 164 | 41 | 30 | 193 | **FEASIBLE** |
| `LIT-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `LIT-USD` | `VolatilityClock` | 5.0 | 164 | 41 | 30 | 193 | **FEASIBLE** |
| `NEAR-USD` | `FixedSpread_6bps` | 2.09 | 30 | 30 | 30 | 678 | **FEASIBLE** |
| `NEAR-USD` | `Adaptive_4bps` | 4.87 | 156 | 39 | 30 | 678 | **FEASIBLE** |
| `NEAR-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `NEAR-USD` | `VolatilityClock` | 5.0 | 164 | 41 | 30 | 339 | **FEASIBLE** |
| `NVDA-USD` | `FixedSpread_6bps` | 0.92 | 30 | 30 | 30 | 467 | **FEASIBLE** |
| `NVDA-USD` | `Adaptive_4bps` | 1.15 | 30 | 30 | 30 | 311 | **FEASIBLE** |
| `NVDA-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `NVDA-USD` | `VolatilityClock` | 0.63 | 30 | 30 | 30 | 778 | **FEASIBLE** |
| `QQQ-USD` | `FixedSpread_6bps` | 1.57 | 30 | 30 | 30 | 451 | **FEASIBLE** |
| `QQQ-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `QQQ-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `QQQ-USD` | `VolatilityClock` | 1.28 | 30 | 30 | 30 | 827 | **FEASIBLE** |
| `SLV-USD` | `FixedSpread_6bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SLV-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SLV-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SLV-USD` | `VolatilityClock` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SOL-USD` | `FixedSpread_6bps` | 1.48 | 30 | 30 | 30 | 1590 | **FEASIBLE** |
| `SOL-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SOL-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SOL-USD` | `VolatilityClock` | 1.72 | 30 | 30 | 30 | 894 | **FEASIBLE** |
| `SPCX-USD` | `FixedSpread_6bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SPCX-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SPCX-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SPCX-USD` | `VolatilityClock` | 0.33 | 30 | 30 | 30 | 152 | **FEASIBLE** |
| `SPY-USD` | `FixedSpread_6bps` | 0.21 | 30 | 30 | 30 | 318 | **FEASIBLE** |
| `SPY-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SPY-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `SPY-USD` | `VolatilityClock` | 0.83 | 30 | 30 | 30 | 795 | **FEASIBLE** |
| `TSLA-USD` | `FixedSpread_6bps` | 5.0 | 164 | 41 | 30 | 76 | **FEASIBLE** |
| `TSLA-USD` | `Adaptive_4bps` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `TSLA-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `TSLA-USD` | `VolatilityClock` | 5.0 | 164 | 41 | 30 | 76 | **FEASIBLE** |
| `UNI-USD` | `FixedSpread_6bps` | 4.73 | 147 | 37 | 30 | 3535 | **FEASIBLE** |
| `UNI-USD` | `Adaptive_4bps` | 5.0 | 164 | 41 | 30 | 208 | **FEASIBLE** |
| `UNI-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `UNI-USD` | `VolatilityClock` | 13.17 | 1137 | 285 | 72 | 832 | **FEASIBLE** |
| `XRP-USD` | `FixedSpread_6bps` | 3.37 | 75 | 30 | 30 | 986 | **FEASIBLE** |
| `XRP-USD` | `Adaptive_4bps` | 3.37 | 75 | 30 | 30 | 986 | **FEASIBLE** |
| `XRP-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `XRP-USD` | `VolatilityClock` | 5.0 | 164 | 41 | 30 | 329 | **FEASIBLE** |
| `ZEC-USD` | `FixedSpread_6bps` | 8.85 | 514 | 129 | 33 | 3123 | **FEASIBLE** |
| `ZEC-USD` | `Adaptive_4bps` | 2.77 | 51 | 30 | 30 | 1874 | **FEASIBLE** |
| `ZEC-USD` | `Avellaneda_Stoikov` | 8.0 | 420 | 105 | 30 | 0 | **INSUFFICIENT DATA** |
| `ZEC-USD` | `VolatilityClock` | 9.87 | 639 | 160 | 40 | 2290 | **FEASIBLE** |

## 4. Pre-Registration v3 Candidate Universe Recommendation

Based on statistical power and trade sufficiency:
- **Primary Liquid Crypto Universe (Passed Gate)**: `BTC-USD`, `ETH-USD`, `SOL-USD`, `HYPE-USD`, `CASHCAT-USD`.
- **Secondary / Low Activity (Pre-declared `INSUFFICIENT DATA`)**: Equities and commodities perps during weekend trading show near-zero taker flow; must wait for Monday RTH volume.
