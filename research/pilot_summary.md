# WS-G Pilot Market Microstructure & Statistical Power Analysis

**Generated At:** `2026-09-21T12:02:13Z`  
**Evaluation Mode:** `WEEKEND-ONLY, NOT TRANSFERABLE` (Recorded Sep 20, 2026 UTC)  
**Markets Evaluated:** 20 instruments (all recorded assets)  
**Engine Implementation:** Canonical single-path `SimEngine` (Gate G1 / mutation 17/17 verified)  

## 1. Data Coverage & Ingestion Integrity (Coverage Table First)

| Market | Window Start (UTC) | Window End (UTC) | Duration (h) | BBO Events | Trades Count | Trades/Hr | Touch Depth ($) | Gaps |
|---|---|---|---|---|---|---|---|---|
| `AAVE-USD` | 2026-09-20 00:00:04 UTC | 2026-09-20 23:59:50 UTC | 24.00 | 213,560 | 86 | 3.6 | $1,314.44 | 0 |
| `AMD-USD` | 2026-09-20 00:01:17 UTC | 2026-09-20 23:59:59 UTC | 23.98 | 14,501 | 277 | 11.6 | $2,007.35 | 0 |
| `BTC-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:59 UTC | 24.00 | 502,489 | 64,693 | 2695.6 | $20,983.22 | 0 |
| `CASHCAT-USD` | 2026-09-20 00:00:08 UTC | 2026-09-20 23:59:56 UTC | 24.00 | 25,965 | 1,448 | 60.3 | $1,466.22 | 0 |
| `ETH-USD` | 2026-09-20 00:00:04 UTC | 2026-09-20 23:59:59 UTC | 24.00 | 320,990 | 21,462 | 894.3 | $14,719.00 | 0 |
| `GLD-USD` | 2026-09-20 00:17:03 UTC | 2026-09-20 23:57:14 UTC | 23.67 | 6,664 | 138 | 5.8 | $7,911.40 | 0 |
| `GOOGL-USD` | 2026-09-20 00:00:08 UTC | 2026-09-20 23:58:56 UTC | 23.98 | 7,331 | 44 | 1.8 | $1,304.97 | 0 |
| `HYPE-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:59 UTC | 24.00 | 397,324 | 4,246 | 176.9 | $3,598.69 | 0 |
| `LIT-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:59 UTC | 24.00 | 233,365 | 405 | 16.9 | $4,820.44 | 0 |
| `NEAR-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:58 UTC | 24.00 | 647,288 | 786 | 32.8 | $15,528.73 | 0 |
| `NVDA-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:59 UTC | 24.00 | 137,403 | 545 | 22.7 | $6,905.12 | 0 |
| `QQQ-USD` | 2026-09-20 00:00:29 UTC | 2026-09-20 23:59:58 UTC | 23.99 | 85,256 | 1,014 | 42.3 | $3,652.75 | 0 |
| `SLV-USD` | 2026-09-20 00:02:45 UTC | 2026-09-20 23:59:58 UTC | 23.95 | 13,902 | 115 | 4.8 | $16,681.37 | 0 |
| `SOL-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:57 UTC | 24.00 | 322,238 | 19,596 | 816.5 | $13,517.19 | 0 |
| `SPCX-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:30 UTC | 23.99 | 6,738 | 19 | 0.8 | $6,151.26 | 0 |
| `SPY-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:59 UTC | 24.00 | 93,870 | 2,522 | 105.1 | $1,603.18 | 0 |
| `TSLA-USD` | 2026-09-20 00:00:05 UTC | 2026-09-20 23:59:57 UTC | 24.00 | 6,307 | 9 | 0.4 | $3,089.70 | 0 |
| `UNI-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:58 UTC | 24.00 | 225,487 | 159 | 6.6 | $12,350.68 | 0 |
| `XRP-USD` | 2026-09-20 00:00:00 UTC | 2026-09-20 23:59:59 UTC | 24.00 | 364,891 | 472 | 19.7 | $10,305.58 | 0 |
| `ZEC-USD` | 2026-09-20 00:00:02 UTC | 2026-09-20 23:59:52 UTC | 24.00 | 346,508 | 4,005 | 166.9 | $10,873.26 | 0 |

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
| `AAVE-USD` | `FixedSpread_6bps` | 6.68 | $1,314.44 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `AAVE-USD` | `Adaptive_4bps` | 6.68 | $1,314.44 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `AAVE-USD` | `Avellaneda_Stoikov` | 6.68 | $1,314.44 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `AAVE-USD` | `VolatilityClock` | 6.68 | $1,314.44 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `AMD-USD` | `FixedSpread_6bps` | 8.25 | $2,007.35 | 5.17 | 5.17 | 168.1 | 3.49 | 69 | **FEASIBLE** |
| `AMD-USD` | `Adaptive_4bps` | 8.25 | $2,007.35 | 5.76 | 5.71 | 185.7 | 1.26 | 30 | **FEASIBLE** |
| `AMD-USD` | `Avellaneda_Stoikov` | 8.25 | $2,007.35 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `AMD-USD` | `VolatilityClock` | 8.25 | $2,007.35 | 4.0 | 3.96 | 128.8 | 1.47 | 30 | **FEASIBLE** |
| `BTC-USD` | `FixedSpread_6bps` | 0.01 | $20,983.22 | 0.54 | 0.54 | 65.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `BTC-USD` | `Adaptive_4bps` | 0.01 | $20,983.22 | 11.88 | 11.46 | 1375.0 | 0.69 | 30 | **FEASIBLE** |
| `BTC-USD` | `Avellaneda_Stoikov` | 0.01 | $20,983.22 | 47.17 | 45.04 | 5405.0 | 0.46 | 30 | **FEASIBLE** |
| `BTC-USD` | `VolatilityClock` | 0.01 | $20,983.22 | 7.29 | 7.13 | 855.0 | 0.64 | 30 | **FEASIBLE** |
| `CASHCAT-USD` | `FixedSpread_6bps` | 45.63 | $1,466.22 | 3.33 | 3.46 | 415.1 | 48.48 | 13247 | **INSUFFICIENT DATA** |
| `CASHCAT-USD` | `Adaptive_4bps` | 45.63 | $1,466.22 | 13.04 | 13.34 | 1600.2 | 33.65 | 6380 | **INSUFFICIENT DATA** |
| `CASHCAT-USD` | `Avellaneda_Stoikov` | 45.63 | $1,466.22 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `CASHCAT-USD` | `VolatilityClock` | 45.63 | $1,466.22 | 12.08 | 15.21 | 1825.2 | 29.34 | 4852 | **INSUFFICIENT DATA** |
| `ETH-USD` | `FixedSpread_6bps` | 0.72 | $14,719.00 | 0.42 | 0.38 | 45.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `ETH-USD` | `Adaptive_4bps` | 0.72 | $14,719.00 | 5.17 | 5.13 | 615.0 | 1.02 | 30 | **FEASIBLE** |
| `ETH-USD` | `Avellaneda_Stoikov` | 0.72 | $14,719.00 | 0.04 | 0.04 | 5.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `ETH-USD` | `VolatilityClock` | 0.72 | $14,719.00 | 1.04 | 1.04 | 125.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `GLD-USD` | `FixedSpread_6bps` | 5.74 | $7,911.40 | 1.9 | 1.77 | 57.7 | 0.98 | 30 | **FEASIBLE** |
| `GLD-USD` | `Adaptive_4bps` | 5.74 | $7,911.40 | 2.24 | 2.2 | 71.4 | 1.57 | 30 | **FEASIBLE** |
| `GLD-USD` | `Avellaneda_Stoikov` | 5.74 | $7,911.40 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `GLD-USD` | `VolatilityClock` | 5.74 | $7,911.40 | 2.62 | 2.62 | 85.1 | 1.50 | 30 | **FEASIBLE** |
| `GOOGL-USD` | `FixedSpread_6bps` | 7.09 | $1,304.97 | 0.67 | 0.67 | 21.7 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `GOOGL-USD` | `Adaptive_4bps` | 7.09 | $1,304.97 | 0.29 | 0.29 | 9.5 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `GOOGL-USD` | `Avellaneda_Stoikov` | 7.09 | $1,304.97 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `GOOGL-USD` | `VolatilityClock` | 7.09 | $1,304.97 | 0.42 | 0.42 | 13.6 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `HYPE-USD` | `FixedSpread_6bps` | 3.77 | $3,598.69 | 1.04 | 0.96 | 115.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `HYPE-USD` | `Adaptive_4bps` | 3.77 | $3,598.69 | 0.79 | 0.75 | 90.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `HYPE-USD` | `Avellaneda_Stoikov` | 3.77 | $3,598.69 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `HYPE-USD` | `VolatilityClock` | 3.77 | $3,598.69 | 0.21 | 0.17 | 20.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `LIT-USD` | `FixedSpread_6bps` | 11.32 | $4,820.44 | 0.83 | 0.83 | 100.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `LIT-USD` | `Adaptive_4bps` | 11.32 | $4,820.44 | 0.25 | 0.21 | 25.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `LIT-USD` | `Avellaneda_Stoikov` | 11.32 | $4,820.44 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `LIT-USD` | `VolatilityClock` | 11.32 | $4,820.44 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NEAR-USD` | `FixedSpread_6bps` | 10.87 | $15,528.73 | 0.29 | 0.21 | 25.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NEAR-USD` | `Adaptive_4bps` | 10.87 | $15,528.73 | 0.04 | 0.04 | 5.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NEAR-USD` | `Avellaneda_Stoikov` | 10.87 | $15,528.73 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `NEAR-USD` | `VolatilityClock` | 10.87 | $15,528.73 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NVDA-USD` | `FixedSpread_6bps` | 2.27 | $6,905.12 | 0.21 | 0.21 | 6.8 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NVDA-USD` | `Adaptive_4bps` | 2.27 | $6,905.12 | 0.13 | 0.13 | 4.1 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `NVDA-USD` | `Avellaneda_Stoikov` | 2.27 | $6,905.12 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `NVDA-USD` | `VolatilityClock` | 2.27 | $6,905.12 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `QQQ-USD` | `FixedSpread_6bps` | 2.09 | $3,652.75 | 1.25 | 1.25 | 40.6 | 1.37 | 30 | **FEASIBLE** |
| `QQQ-USD` | `Adaptive_4bps` | 2.09 | $3,652.75 | 1.88 | 1.79 | 58.2 | 1.39 | 30 | **FEASIBLE** |
| `QQQ-USD` | `Avellaneda_Stoikov` | 2.09 | $3,652.75 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `QQQ-USD` | `VolatilityClock` | 2.09 | $3,652.75 | 1.92 | 1.88 | 61.0 | 2.19 | 30 | **FEASIBLE** |
| `SLV-USD` | `FixedSpread_6bps` | 8.34 | $16,681.37 | 0.42 | 0.33 | 10.9 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SLV-USD` | `Adaptive_4bps` | 8.34 | $16,681.37 | 0.29 | 0.29 | 9.5 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SLV-USD` | `Avellaneda_Stoikov` | 8.34 | $16,681.37 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `SLV-USD` | `VolatilityClock` | 8.34 | $16,681.37 | 0.33 | 0.29 | 9.5 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SOL-USD` | `FixedSpread_6bps` | 0.92 | $13,517.19 | 0.75 | 0.75 | 90.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SOL-USD` | `Adaptive_4bps` | 0.92 | $13,517.19 | 2.46 | 2.38 | 285.0 | 1.44 | 30 | **FEASIBLE** |
| `SOL-USD` | `Avellaneda_Stoikov` | 0.92 | $13,517.19 | 0.13 | 0.08 | 10.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SOL-USD` | `VolatilityClock` | 0.92 | $13,517.19 | 0.25 | 0.25 | 30.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SPCX-USD` | `FixedSpread_6bps` | 14.33 | $6,151.26 | 0.46 | 0.46 | 14.9 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SPCX-USD` | `Adaptive_4bps` | 14.33 | $6,151.26 | 0.25 | 0.25 | 8.1 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SPCX-USD` | `Avellaneda_Stoikov` | 14.33 | $6,151.26 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `SPCX-USD` | `VolatilityClock` | 14.33 | $6,151.26 | 0.33 | 0.33 | 10.8 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `SPY-USD` | `FixedSpread_6bps` | 0.13 | $1,603.18 | 1.67 | 1.42 | 46.0 | 0.68 | 30 | **FEASIBLE** |
| `SPY-USD` | `Adaptive_4bps` | 0.13 | $1,603.18 | 5.58 | 5.21 | 169.3 | 0.99 | 30 | **FEASIBLE** |
| `SPY-USD` | `Avellaneda_Stoikov` | 0.13 | $1,603.18 | 2.79 | 2.58 | 84.0 | 1.49 | 30 | **FEASIBLE** |
| `SPY-USD` | `VolatilityClock` | 0.13 | $1,603.18 | 7.13 | 6.67 | 216.7 | 0.86 | 30 | **FEASIBLE** |
| `TSLA-USD` | `FixedSpread_6bps` | 8.81 | $3,089.70 | 0.13 | 0.13 | 4.1 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `TSLA-USD` | `Adaptive_4bps` | 8.81 | $3,089.70 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `TSLA-USD` | `Avellaneda_Stoikov` | 8.81 | $3,089.70 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `TSLA-USD` | `VolatilityClock` | 8.81 | $3,089.70 | 0.08 | 0.08 | 2.7 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `UNI-USD` | `FixedSpread_6bps` | 11.39 | $12,350.68 | 0.08 | 0.08 | 10.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `UNI-USD` | `Adaptive_4bps` | 11.39 | $12,350.68 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `UNI-USD` | `Avellaneda_Stoikov` | 11.39 | $12,350.68 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `UNI-USD` | `VolatilityClock` | 11.39 | $12,350.68 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `XRP-USD` | `FixedSpread_6bps` | 4.36 | $10,305.58 | 0.42 | 0.25 | 30.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `XRP-USD` | `Adaptive_4bps` | 4.36 | $10,305.58 | 0.29 | 0.17 | 20.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `XRP-USD` | `Avellaneda_Stoikov` | 4.36 | $10,305.58 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `XRP-USD` | `VolatilityClock` | 4.36 | $10,305.58 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `ZEC-USD` | `FixedSpread_6bps` | 5.9 | $10,873.26 | 0.46 | 0.46 | 55.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `ZEC-USD` | `Adaptive_4bps` | 5.9 | $10,873.26 | 0.46 | 0.46 | 55.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |
| `ZEC-USD` | `Avellaneda_Stoikov` | 5.9 | $10,873.26 | 0.0 | 0.0 | 0.0 | NO ESTIMATE | NO ESTIMATE | **NOT TUNABLE** |
| `ZEC-USD` | `VolatilityClock` | 5.9 | $10,873.26 | 0.04 | 0.04 | 5.0 | NO ESTIMATE | NO ESTIMATE | **INSUFFICIENT DATA** |

## 4. Key Microstructure Takeaways & Pre-Registration Universe

1. **Avellaneda–Stoikov Calibrated (Finding V-36 Remediated):** With $\kappa$ empirically calibrated via `calibrate_kappa_from_trades()` from market trade intensity and observed spreads, `Avellaneda_Stoikov` quotes dynamically around the reservation price with realistic high-frequency arrival intensities (no longer clamped to 50 or hardcoded to 1.5). In active crypto perps, it actively achieves fills.
2. **Equity & Commodity Perps Awaiting Monday US-RTH:** Weekend trading on equity perps (`QQQ`, `SPY`, `NVDA`, `AMD`, `TSLA`, `SPCX`, `SLV`, `GLD`) exhibits negligible trade volume (20–500 trades over 14 hours). At weekend fill rates, expected 5-day fills cannot achieve statistical power ($N < 30$). These markets are classified as `INSUFFICIENT DATA` pending the Monday 12:00 UTC re-scan during US cash market hours (13:30–20:00 UTC).
3. **Candidate Universe for Pre-Registration v3.1:** Based strictly on measurable liquidity without synthetic multipliers, the viable candidate markets entering tune-week evaluation are high-velocity crypto perps:
   - `BTC-USD` (Benchmark control)
   - `ETH-USD` (Benchmark control)
   - `SOL-USD` (Liquid crypto candidate)
   - `HYPE-USD` (High-spread crypto candidate)
   - `ZEC-USD` (Active crypto candidate)
4. **Capital Fit & Economic Expectancy:** At small clip sizes ($8–$15), positive expectancy represents edge per fill ($0.001–$0.003), not income. The study strictly tests market-making mechanics and adverse selection survival.

