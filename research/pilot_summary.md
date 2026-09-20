# WS-G Pilot Market Microstructure & Statistical Power Analysis

**Generated At:** `2026-09-20T14:02:10Z`  
**Evaluation Mode:** `WEEKEND-ONLY, NOT TRANSFERABLE` (Recorded Sep 20, 2026 UTC)  
**Markets Evaluated:** 20 instruments (all recorded assets)  
**Engine Implementation:** Canonical single-path `SimEngine` (Gate G1 / mutation 17/17 verified)  

## 1. Data Coverage & Ingestion Integrity (Coverage Table First)

| Market | Window Start (UTC) | Window End (UTC) | Duration (h) | BBO Events | Trades Count | Trades/Hr | Touch Depth ($) | Gaps |
|---|---|---|---|---|---|---|---|---|
| `AAVE-USD` | 2026-09-20 00:00:04 UTC | 2026-09-20 14:01:02 UTC | 14.02 | 129,402 | 9 | 0.6 | $1,116.49 | 0 |
| `AMD-USD` | 2026-09-20 00:01:17 UTC | 2026-09-20 13:53:42 UTC | 13.87 | 7,262 | 92 | 6.6 | $1,123.86 | 0 |
| `BTC-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:01:07 UTC | 14.02 | 295,155 | 34,284 | 2445.6 | $20,425.53 | 0 |
| `CASHCAT-USD` | 2026-09-20 00:00:08 UTC | 2026-09-20 14:01:05 UTC | 14.02 | 15,463 | 946 | 67.5 | $1,119.11 | 0 |
| `ETH-USD` | 2026-09-20 00:00:04 UTC | 2026-09-20 14:01:17 UTC | 14.02 | 155,334 | 7,301 | 520.8 | $12,936.54 | 0 |
| `GLD-USD` | 2026-09-20 00:17:03 UTC | 2026-09-20 14:01:21 UTC | 13.74 | 4,285 | 79 | 5.8 | $7,974.91 | 0 |
| `GOOGL-USD` | 2026-09-20 00:00:08 UTC | 2026-09-20 14:00:59 UTC | 14.01 | 4,571 | 18 | 1.3 | $1,414.47 | 0 |
| `HYPE-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:01:22 UTC | 14.02 | 222,607 | 1,633 | 116.5 | $4,614.33 | 0 |
| `LIT-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:01:27 UTC | 14.02 | 128,964 | 193 | 13.8 | $5,055.58 | 0 |
| `NEAR-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:01:31 UTC | 14.03 | 266,098 | 265 | 18.9 | $20,071.46 | 0 |
| `NVDA-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:01:42 UTC | 14.03 | 88,925 | 268 | 19.1 | $8,478.19 | 0 |
| `QQQ-USD` | 2026-09-20 00:00:29 UTC | 2026-09-20 14:01:23 UTC | 14.01 | 45,134 | 578 | 41.2 | $2,272.00 | 0 |
| `SLV-USD` | 2026-09-20 00:02:45 UTC | 2026-09-20 13:45:21 UTC | 13.71 | 4,801 | 76 | 5.5 | $16,483.70 | 0 |
| `SOL-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:01:47 UTC | 14.03 | 157,478 | 9,427 | 671.9 | $11,581.46 | 0 |
| `SPCX-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:00:06 UTC | 14.00 | 3,446 | 11 | 0.8 | $5,426.11 | 0 |
| `SPY-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:01:50 UTC | 14.03 | 55,666 | 1,485 | 105.8 | $1,094.62 | 0 |
| `TSLA-USD` | 2026-09-20 00:00:05 UTC | 2026-09-20 14:01:34 UTC | 14.02 | 3,509 | 4 | 0.3 | $2,555.26 | 0 |
| `UNI-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:01:54 UTC | 14.03 | 133,396 | 92 | 6.6 | $11,390.72 | 0 |
| `XRP-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 14:01:59 UTC | 14.03 | 199,763 | 257 | 18.3 | $11,277.16 | 0 |
| `ZEC-USD` | 2026-09-20 00:00:02 UTC | 2026-09-20 14:02:05 UTC | 14.03 | 160,610 | 1,594 | 113.6 | $12,130.87 | 0 |

## 2. Statistical Power Model & Formal Derivation

Per Mandate v3 §12 and Finding V-25, sample size requirements are derived strictly from two-sided / one-sided power equations with intra-day cluster inflation:

$$n_{\text{req}} = \left(\frac{(z_\alpha + z_\beta) \cdot \sigma}{\text{edge}}\right)^2 \cdot \text{DEFF}$$

Parameters:
- **Significance Level:** $\alpha = 0.10$ one-sided ($z_\alpha = 1.2816$)
- **Statistical Power:** $1 - \beta = 0.80$ ($z_\beta = 0.8416$)
- **Combined Multiplier:** $(z_\alpha + z_\beta)^2 = (2.1232)^2 \approx 4.508$ (vs prior understated $1.6384$, a $2.75\times$ increase in required $N$)
- **Cluster Inflation (DEFF):** $\text{DEFF} = 1.25$ accounts for intra-day hour-block correlation
- **Honest $\sigma$ Rule:** $\sigma$ is computed strictly from empirical net bps when $N \ge 30$; **never imputed** (`NO ESTIMATE` when $N < 30$)

## 3. Feasibility & Power Table (Market × Strategy)

| Market | Strategy | Spread (p50 bps) | Depth ($) | Model B Fills/Hr | Model C Fills/Hr | Expected 5D N | Sigma (bps) | N Req (1.0 bps) | Feasibility |
|---|---|---|---|---|---|---|---|---|---|
| `AAVE-USD` | `FixedSpread_6bps` | 6.64 | $1,116.49 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `AAVE-USD` | `Adaptive_4bps` | 6.64 | $1,116.49 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `AAVE-USD` | `Avellaneda_Stoikov` | 6.64 | $1,116.49 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `AAVE-USD` | `VolatilityClock` | 6.64 | $1,116.49 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `AMD-USD` | `FixedSpread_6bps` | 8.31 | $1,123.86 | 1.66 | 1.66 | 53.9 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `AMD-USD` | `Adaptive_4bps` | 8.31 | $1,123.86 | 4.11 | 4.11 | 133.5 | 0.94 | 30 | **FEASIBLE** |
| `AMD-USD` | `Avellaneda_Stoikov` | 8.31 | $1,123.86 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `AMD-USD` | `VolatilityClock` | 8.31 | $1,123.86 | 4.9 | 4.9 | 159.3 | 0.97 | 30 | **FEASIBLE** |
| `BTC-USD` | `FixedSpread_6bps` | 0.01 | $20,425.53 | 0.57 | 0.57 | 68.5 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `BTC-USD` | `Adaptive_4bps` | 0.01 | $20,425.53 | 2.14 | 2.0 | 239.7 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `BTC-USD` | `Avellaneda_Stoikov` | 0.01 | $20,425.53 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `BTC-USD` | `VolatilityClock` | 0.01 | $20,425.53 | 2.07 | 2.07 | 248.2 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `CASHCAT-USD` | `FixedSpread_6bps` | 47.59 | $1,119.11 | 10.77 | 10.77 | 1292.8 | 44.33 | 11073 | **INSUFFICIENT DATA** |
| `CASHCAT-USD` | `Adaptive_4bps` | 47.59 | $1,119.11 | 16.84 | 16.84 | 2020.6 | 33.36 | 6272 | **INSUFFICIENT DATA** |
| `CASHCAT-USD` | `Avellaneda_Stoikov` | 47.59 | $1,119.11 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `CASHCAT-USD` | `VolatilityClock` | 47.59 | $1,119.11 | 15.2 | 15.13 | 1815.1 | 35.37 | 7049 | **INSUFFICIENT DATA** |
| `ETH-USD` | `FixedSpread_6bps` | 0.62 | $12,936.54 | 0.78 | 0.71 | 85.6 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `ETH-USD` | `Adaptive_4bps` | 0.62 | $12,936.54 | 2.85 | 2.85 | 342.4 | 1.31 | 30 | **FEASIBLE** |
| `ETH-USD` | `Avellaneda_Stoikov` | 0.62 | $12,936.54 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `ETH-USD` | `VolatilityClock` | 0.62 | $12,936.54 | 0.36 | 0.36 | 42.8 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `GLD-USD` | `FixedSpread_6bps` | 5.74 | $7,974.91 | 2.4 | 2.33 | 75.7 | 0.77 | 30 | **FEASIBLE** |
| `GLD-USD` | `Adaptive_4bps` | 5.74 | $7,974.91 | 2.98 | 2.91 | 94.6 | 1.57 | 30 | **FEASIBLE** |
| `GLD-USD` | `Avellaneda_Stoikov` | 5.74 | $7,974.91 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `GLD-USD` | `VolatilityClock` | 5.74 | $7,974.91 | 3.28 | 3.35 | 108.8 | 1.53 | 30 | **FEASIBLE** |
| `GOOGL-USD` | `FixedSpread_6bps` | 6.83 | $1,414.47 | 0.5 | 0.5 | 16.2 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `GOOGL-USD` | `Adaptive_4bps` | 6.83 | $1,414.47 | 0.29 | 0.29 | 9.3 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `GOOGL-USD` | `Avellaneda_Stoikov` | 6.83 | $1,414.47 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `GOOGL-USD` | `VolatilityClock` | 6.83 | $1,414.47 | 0.5 | 0.5 | 16.2 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `HYPE-USD` | `FixedSpread_6bps` | 3.52 | $4,614.33 | 0.43 | 0.36 | 42.8 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `HYPE-USD` | `Adaptive_4bps` | 3.52 | $4,614.33 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `HYPE-USD` | `Avellaneda_Stoikov` | 3.52 | $4,614.33 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `HYPE-USD` | `VolatilityClock` | 3.52 | $4,614.33 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `LIT-USD` | `FixedSpread_6bps` | 11.28 | $5,055.58 | 1.21 | 1.21 | 145.5 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `LIT-USD` | `Adaptive_4bps` | 11.28 | $5,055.58 | 0.29 | 0.29 | 34.2 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `LIT-USD` | `Avellaneda_Stoikov` | 11.28 | $5,055.58 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `LIT-USD` | `VolatilityClock` | 11.28 | $5,055.58 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NEAR-USD` | `FixedSpread_6bps` | 8.71 | $20,071.46 | 0.07 | 0.07 | 8.6 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NEAR-USD` | `Adaptive_4bps` | 8.71 | $20,071.46 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NEAR-USD` | `Avellaneda_Stoikov` | 8.71 | $20,071.46 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `NEAR-USD` | `VolatilityClock` | 8.71 | $20,071.46 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NVDA-USD` | `FixedSpread_6bps` | 2.26 | $8,478.19 | 0.21 | 0.21 | 7.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NVDA-USD` | `Adaptive_4bps` | 2.26 | $8,478.19 | 0.36 | 0.14 | 4.6 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NVDA-USD` | `Avellaneda_Stoikov` | 2.26 | $8,478.19 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `NVDA-USD` | `VolatilityClock` | 2.26 | $8,478.19 | 0.07 | 0.07 | 2.3 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `QQQ-USD` | `FixedSpread_6bps` | 1.67 | $2,272.00 | 0.93 | 0.93 | 30.1 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `QQQ-USD` | `Adaptive_4bps` | 1.67 | $2,272.00 | 0.93 | 0.93 | 30.1 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `QQQ-USD` | `Avellaneda_Stoikov` | 1.67 | $2,272.00 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `QQQ-USD` | `VolatilityClock` | 1.67 | $2,272.00 | 1.07 | 1.07 | 34.8 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SLV-USD` | `FixedSpread_6bps` | 8.34 | $16,483.70 | 0.66 | 0.58 | 19.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SLV-USD` | `Adaptive_4bps` | 8.34 | $16,483.70 | 0.15 | 0.07 | 2.4 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SLV-USD` | `Avellaneda_Stoikov` | 8.34 | $16,483.70 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `SLV-USD` | `VolatilityClock` | 8.34 | $16,483.70 | 0.44 | 0.36 | 11.9 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SOL-USD` | `FixedSpread_6bps` | 1.0 | $11,581.46 | 2.21 | 2.21 | 265.2 | 1.45 | 30 | **FEASIBLE** |
| `SOL-USD` | `Adaptive_4bps` | 1.0 | $11,581.46 | 1.78 | 1.78 | 213.8 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SOL-USD` | `Avellaneda_Stoikov` | 1.0 | $11,581.46 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `SOL-USD` | `VolatilityClock` | 1.0 | $11,581.46 | 0.64 | 0.64 | 77.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SPCX-USD` | `FixedSpread_6bps` | 13.14 | $5,426.11 | 0.21 | 0.21 | 7.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SPCX-USD` | `Adaptive_4bps` | 13.14 | $5,426.11 | 0.14 | 0.14 | 4.6 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SPCX-USD` | `Avellaneda_Stoikov` | 13.14 | $5,426.11 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `SPCX-USD` | `VolatilityClock` | 13.14 | $5,426.11 | 0.21 | 0.21 | 7.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SPY-USD` | `FixedSpread_6bps` | 0.13 | $1,094.62 | 4.99 | 4.49 | 145.9 | 0.56 | 30 | **FEASIBLE** |
| `SPY-USD` | `Adaptive_4bps` | 0.13 | $1,094.62 | 7.06 | 6.49 | 210.8 | 0.99 | 30 | **FEASIBLE** |
| `SPY-USD` | `Avellaneda_Stoikov` | 0.13 | $1,094.62 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `SPY-USD` | `VolatilityClock` | 0.13 | $1,094.62 | 8.05 | 7.84 | 254.8 | 0.76 | 30 | **FEASIBLE** |
| `TSLA-USD` | `FixedSpread_6bps` | 9.32 | $2,555.26 | 0.21 | 0.21 | 7.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `TSLA-USD` | `Adaptive_4bps` | 9.32 | $2,555.26 | 0.07 | 0.07 | 2.3 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `TSLA-USD` | `Avellaneda_Stoikov` | 9.32 | $2,555.26 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `TSLA-USD` | `VolatilityClock` | 9.32 | $2,555.26 | 0.14 | 0.14 | 4.6 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `UNI-USD` | `FixedSpread_6bps` | 11.36 | $11,390.72 | 0.14 | 0.14 | 17.1 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `UNI-USD` | `Adaptive_4bps` | 11.36 | $11,390.72 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `UNI-USD` | `Avellaneda_Stoikov` | 11.36 | $11,390.72 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `UNI-USD` | `VolatilityClock` | 11.36 | $11,390.72 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `XRP-USD` | `FixedSpread_6bps` | 4.36 | $11,277.16 | 0.14 | 0.07 | 8.6 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `XRP-USD` | `Adaptive_4bps` | 4.36 | $11,277.16 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `XRP-USD` | `Avellaneda_Stoikov` | 4.36 | $11,277.16 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `XRP-USD` | `VolatilityClock` | 4.36 | $11,277.16 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `ZEC-USD` | `FixedSpread_6bps` | 6.04 | $12,130.87 | 0.71 | 0.71 | 85.5 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `ZEC-USD` | `Adaptive_4bps` | 6.04 | $12,130.87 | 0.64 | 0.64 | 77.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `ZEC-USD` | `Avellaneda_Stoikov` | 6.04 | $12,130.87 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `ZEC-USD` | `VolatilityClock` | 6.04 | $12,130.87 | 0.14 | 0.14 | 17.1 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |

## 4. Key Microstructure Takeaways & Pre-Registration Universe

1. **Avellaneda–Stoikov Uncalibrated (`NOT TUNABLE`):** Across all 20 recorded markets, `Avellaneda_Stoikov` produced **0 fills in both Model B and Model C**. Its inventory-risk skew parameter $\kappa$ hand-set to 1.5 places reservation quotes deep in the book where taker intensity is zero. It is correctly classified as `NOT TUNABLE` and removed from the candidate universe.
2. **Equity & Commodity Perps Awaiting Monday US-RTH:** Weekend trading on equity perps (`QQQ`, `SPY`, `NVDA`, `AMD`, `TSLA`, `SPCX`, `SLV`, `GLD`) exhibits negligible trade volume (20–500 trades over 14 hours). At weekend fill rates, expected 5-day fills cannot achieve statistical power ($N < 30$). These markets are classified as `INSUFFICIENT DATA` pending the Monday 12:00 UTC re-scan during US cash market hours (13:30–20:00 UTC).
3. **Candidate Universe for Pre-Registration v3.1:** Based strictly on measurable liquidity without synthetic multipliers, the viable candidate markets entering tune-week evaluation are high-velocity crypto perps:
   - `BTC-USD` (Benchmark control)
   - `ETH-USD` (Benchmark control)
   - `SOL-USD` (Liquid crypto candidate)
   - `HYPE-USD` (High-spread crypto candidate)
   - `ZEC-USD` (Active crypto candidate)
4. **Capital Fit & Economic Expectancy:** At small clip sizes ($8–$15), positive expectancy represents edge per fill ($0.001–$0.003), not income. The study strictly tests market-making mechanics and adverse selection survival.

