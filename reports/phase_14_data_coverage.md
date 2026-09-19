# Phase 14 — Market Data Coverage & Regime Stratification Report

**Generated At:** 2026-09-19 19:25:49 UTC  
**Report Type:** `DATA COVERAGE REPORT` (Distinct from Formal Backtest Report per Section 9)  
**Total Streaming Messages Recorded:** 4,597,219  
**Total Genuine Real Trades Logged:** 7,524  
**Peak Market Duration:** 3.62 hours  

---

## 1. Multi-Market Recording Coverage Table

| Market | Asset Class | Regime | Session | Duration (hrs) | Real Trades | BBO Updates | L2 Updates | Oracle Updates | Total Frames | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| **HYPE-USD** | crypto_candidate | WEEKEND | US_LATE | 3.62h | 455 | 48,468 | 257,887 | 48,205 | 355,015 | `ACCUMULATING` |
| **ZEC-USD** | crypto_candidate | WEEKEND | US_LATE | 3.59h | 234 | 57,390 | 158,298 | 52,801 | 268,723 | `ACCUMULATING` |
| **NEAR-USD** | crypto_candidate | WEEKEND | US_LATE | 3.57h | 105 | 66,682 | 182,961 | 42,569 | 292,317 | `ACCUMULATING` |
| **UNI-USD** | crypto_candidate | WEEKEND | US_LATE | 3.51h | 54 | 36,344 | 133,857 | 45,962 | 216,217 | `ACCUMULATING` |
| **LIT-USD** | crypto_candidate | WEEKEND | US_LATE | 2.91h | 94 | 39,531 | 173,509 | 41,627 | 254,761 | `ACCUMULATING` |
| **AAVE-USD** | crypto_candidate | WEEKEND | US_LATE | 3.51h | 26 | 27,690 | 89,835 | 35,165 | 152,716 | `ACCUMULATING` |
| **CASHCAT-USD** | crypto_candidate | WEEKEND | US_LATE | 3.59h | 276 | 3,482 | 17,662 | 28,688 | 50,108 | `ACCUMULATING` |
| **XRP-USD** | crypto_control | WEEKEND | US_LATE | 3.58h | 83 | 60,333 | 209,562 | 40,155 | 310,133 | `ACCUMULATING` |
| **BTC-USD** | crypto_control | WEEKEND | US_LATE | 3.61h | 2,453 | 81,575 | 391,025 | 56,896 | 531,949 | `ACCUMULATING` |
| **ETH-USD** | crypto_control | WEEKEND | US_LATE | 3.61h | 1,425 | 31,964 | 375,995 | 45,471 | 454,855 | `ACCUMULATING` |
| **SOL-USD** | crypto_control | WEEKEND | US_LATE | 3.61h | 1,984 | 41,940 | 376,667 | 49,789 | 470,380 | `ACCUMULATING` |
| **SPCX-USD** | equities | WEEKEND | US_LATE | 2.06h | 17 | 299 | 1,530 | 114,454 | 116,300 | `ACCUMULATING` |
| **NVDA-USD** | equities | WEEKEND | US_LATE | 3.28h | 56 | 27,403 | 32,944 | 113,538 | 173,941 | `ACCUMULATING` |
| **TSLA-USD** | equities | WEEKEND | US_LATE | 2.06h | 15 | 1,241 | 9,073 | 113,765 | 124,094 | `ACCUMULATING` |
| **GOOGL-USD** | equities | WEEKEND | US_LATE | 2.47h | 15 | 272 | 3,542 | 113,562 | 117,391 | `ACCUMULATING` |
| **AMD-USD** | equities | WEEKEND | US_LATE | 2.38h | 33 | 1,360 | 8,876 | 114,396 | 124,665 | `ACCUMULATING` |
| **SLV-USD** | commodities/indices | WEEKEND | US_LATE | 2.06h | 18 | 833 | 9,136 | 113,651 | 123,638 | `ACCUMULATING` |
| **GLD-USD** | commodities/indices | WEEKEND | US_LATE | 2.06h | 17 | 55 | 530 | 113,824 | 114,426 | `ACCUMULATING` |
| **SPY-USD** | commodities/indices | WEEKEND | US_LATE | 3.55h | 86 | 14,087 | 51,414 | 114,116 | 179,703 | `ACCUMULATING` |
| **QQQ-USD** | commodities/indices | WEEKEND | US_LATE | 3.26h | 78 | 11,282 | 40,655 | 113,872 | 165,887 | `ACCUMULATING` |

---

## 2. Integrity & Sequence Continuity Summary

- **Sequence Continuity:** 0 gaps observed across all recorded candidate streams.
- **Splice Reconciliations:** Snapshot boundary sequence offsets cleanly reconciled.
- **Trade Frame Deduplication:** Frame-wide trade deduplication applied across all events.
- **Next Step:** Continuous background recording continues toward the pre-registered 5-day OOS testing window (2026-09-28 through 2026-10-02).
