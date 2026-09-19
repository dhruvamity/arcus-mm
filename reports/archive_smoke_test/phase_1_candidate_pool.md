# Phase 1 — Candidate Pool Report

**Date:** 2026-09-19 13:41:09 UTC  
**Target Capital:** $50–$100 Experimental Research Capital  
**Surviving Candidates:** 20 of 64 markets  

## 1. Executive Candidate Summary

A market qualifies for the research candidate pool only if it clears all feasibility criteria:
1. **Capital Fit**: Minimum executable clip size $\le$ $25 (consumes $\le$ 50% of $50 capital and $\le$ 25% of $100 capital).
2. **Fee & Spread Viability**: Spread is not excessively tight ($> 1.0$ bps) or artificially wide ($< 500$ bps).
3. **Net Expectancy**: Estimated net edge per fill $> 0$ after conservative adverse selection model and 0 bps maker fee.
4. **Liquidity & Churn**: 24h trade count $\ge$ 100 and 24h volume $\ge$ $10,000 USD.
5. **Tick Granularity**: Discrete tick coarseness $\le$ 25 bps.

## 2. Surviving Candidates Table (Ranked by 24h Volume)

| Rank | Symbol | Category | Oracle Price | Spread (bps) | 24h Volume (USD) | 24h Trades | Min Clip ($) | Est. Adverse Selection | Net Edge / Fill | Replenishment / Clip |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **HYPE-USD** | CRYPTO | $92.4030 | 3.68 bps | $2,165,386 | 6,834 | $9.24 | 1.50 bps | **+0.34 bps** | +92 units |
| 2 | **ZEC-USD** | CRYPTO | $1,534.1780 | 4.13 bps | $2,007,546 | 5,168 | $15.34 | 1.50 bps | **+0.56 bps** | +153 units |
| 3 | **NEAR-USD** | CRYPTO | $3.5710 | 5.59 bps | $602,624 | 381 | $5.00 | 1.50 bps | **+1.30 bps** | +50 units |
| 4 | **SPCX-USD** | EQUITIES | $152.7100 | 5.24 bps | $417,426 | 279 | $5.00 | 1.50 bps | **+1.12 bps** | +50 units |
| 5 | **LIT-USD** | CRYPTO | $5.1023 | 10.79 bps | $237,944 | 754 | $5.10 | 2.43 bps | **+2.97 bps** | +51 units |
| 6 | **GOOGL-USD** | EQUITIES | $350.3400 | 7.13 bps | $199,788 | 117 | $5.00 | 1.61 bps | **+1.96 bps** | +50 units |
| 7 | **BE-USD** | EQUITIES | $267.9700 | 10.44 bps | $183,062 | 253 | $5.00 | 2.35 bps | **+2.87 bps** | +50 units |
| 8 | **CASHCAT-USD** | CRYPTO | $0.2140 | 21.55 bps | $181,212 | 713 | $5.00 | 4.85 bps | **+5.93 bps** | +50 units |
| 9 | **UNI-USD** | CRYPTO | $8.9390 | 12.26 bps | $178,935 | 197 | $5.00 | 2.76 bps | **+3.37 bps** | +50 units |
| 10 | **SLV-USD** | COMMODITIES | $60.0700 | 6.66 bps | $145,305 | 105 | $6.01 | 1.50 bps | **+1.83 bps** | +60 units |
| 11 | **AAVE-USD** | CRYPTO | $142.7900 | 4.91 bps | $138,878 | 131 | $5.00 | 1.50 bps | **+0.95 bps** | +50 units |
| 12 | **SKHY-USD** | EQUITIES | $186.2100 | 12.34 bps | $129,966 | 427 | $5.00 | 2.78 bps | **+3.39 bps** | +50 units |
| 13 | **GLD-USD** | COMMODITIES | $401.1400 | 5.23 bps | $127,571 | 242 | $5.00 | 1.50 bps | **+1.12 bps** | +50 units |
| 14 | **CRCL-USD** | EQUITIES | $91.8500 | 6.53 bps | $126,495 | 315 | $5.00 | 1.50 bps | **+1.77 bps** | +50 units |
| 15 | **MU-USD** | EQUITIES | $1,007.4100 | 6.75 bps | $110,984 | 278 | $10.08 | 1.52 bps | **+1.86 bps** | +101 units |
| 16 | **DRAM-USD** | EQUITIES | $59.2400 | 5.06 bps | $106,693 | 722 | $5.00 | 1.50 bps | **+1.03 bps** | +50 units |
| 17 | **AMD-USD** | EQUITIES | $553.1800 | 8.32 bps | $99,445 | 237 | $5.53 | 1.87 bps | **+2.29 bps** | +55 units |
| 18 | **NBIS-USD** | EQUITIES | $219.7900 | 9.10 bps | $65,283 | 152 | $5.00 | 2.05 bps | **+2.50 bps** | +50 units |
| 19 | **TSLA-USD** | EQUITIES | $364.4300 | 8.51 bps | $41,717 | 132 | $5.00 | 1.91 bps | **+2.34 bps** | +50 units |
| 20 | **MSFT-USD** | EQUITIES | $494.2700 | 7.89 bps | $36,705 | 113 | $5.00 | 1.78 bps | **+2.17 bps** | +50 units |

## 3. High-Priority Research Tiers for Phase 2

### Tier 1: Prime Candidates (High Liquidity + Wide Spread + Sustainable Replenishment)
- **`HYPE-USD`** (Crypto): $2.18M 24h volume, 6,841 trades/day, 3.46 bps spread, $9.25 min clip (+92 units replenished/fill).
- **`ZEC-USD`** (Crypto): $2.01M 24h volume, 5,171 trades/day, 4.13 bps spread, $15.32 min clip (+153 units replenished/fill).
- **`NEAR-USD`** (Crypto): $602k 24h volume, 382 trades/day, 5.61 bps spread, $5.00 min clip (+50 units replenished/fill).
- **`SPCX-USD`** (Equities): $460k 24h volume, 302 trades/day, 5.24 bps spread, $5.00 min clip (+50 units replenished/fill).
- **`LIT-USD`** (Crypto): $238k 24h volume, 757 trades/day, 8.82 bps spread, $5.10 min clip (+51 units replenished/fill).

### Tier 2: Mid-Liquidity Candidates
- **`GOOGL-USD`**, **`BE-USD`**, **`UNI-USD`**, **`SLV-USD`**, **`AAVE-USD`**, **`CRCL-USD`**, **`MU-USD`**.

### Why Mega-Caps (BTC-USD, ETH-USD, SOL-USD) Were Excluded
- **BTC-USD**: Top-of-book spread is 0.012 bps ($0.10). Adverse selection from colocated low-latency taker flow completely dominates. Net expectancy is negative (-1.49 bps) for standard API access.
- **ETH-USD**: Top-of-book spread is 0.53 bps. Net expectancy is negative (-1.23 bps) after adverse selection.
- **SOL-USD**: Top-of-book spread is 0.09 bps. Net expectancy is negative (-1.46 bps).