# Phase 0 — Environment & Venue Validation Report

**Venue:** Arcus Perpetuals  
**Date:** 2026-09-19  
**Target Capital Scope:** $50–$100 Experimental Research Capital  
**Author:** Quantitative Research & Systems Engineering Agent  
**Status:** **PHASE 0 PASSED**

---

## 1. Executive Summary

This report documents the exhaustive verification of Arcus venue mechanics, network interfaces, authentication protocols, fee schedules, rate-limit structures, order lifecycle semantics, and orderbook reconstruction rules as mandated by Section 9 of the Master Prompt.

Every parameter is classified into one of four empirical confidence levels:
1. `[VERIFIED_API/DOCS]`: Directly confirmed from live Arcus endpoints or official documentation.
2. `[OBSERVED_EMPIRICAL]`: Confirmed through live network probing and test suites.
3. `[ASSUMED_PENDING]`: Derived from working assumptions; awaiting further empirical replay.
4. `[UNKNOWN]`: Unresolved or unexposed by public interfaces.

---

## 2. Verified Venue Mechanics Registry

| # | Venue Feature / Constraint | Value / Behavior | Classification | Notes |
|---|---|---|---|---|
| 1 | Mainnet REST Host | `https://api.arcus.xyz` | `[VERIFIED_API/DOCS]` | Verified 200 OK via `GET /health` |
| 2 | Mainnet WS Host | `wss://api.arcus.xyz/v1/ws` | `[VERIFIED_API/DOCS]` | Verified multiplexed streaming |
| 3 | Testnet REST Host | `https://api.testnet.arcus.xyz` | `[VERIFIED_API/DOCS]` | Verified 200 OK |
| 4 | Testnet WS Host | `wss://api.testnet.arcus.xyz/v1/ws` | `[VERIFIED_API/DOCS]` | Verified streaming |
| 5 | Authentication Type | Ed25519 (non-custodial) | `[VERIFIED_API/DOCS]` | 32-byte keypair, EIP-712 wallet registration |
| 6 | Order Signing Scheme | Scheme 1 (Typed Payload) | `[VERIFIED_API/DOCS]` | Compact, key-sorted canonical JSON |
| 7 | Legacy Signing Scheme | Scheme 2 (`ts + action + body`) | `[VERIFIED_API/DOCS]` | For `cancelAllOrders`, `scheduleCancel`, WS auth |
| 8 | Active Markets Count | 64 markets on Mainnet (65 on Testnet) | `[VERIFIED_API/DOCS]` | 22 Crypto, 34 Equities, 4 Commodities, 4 Indices |
| 9 | Maker Fee (Base Tier) | **0.00 bps** (0 ppm) | `[VERIFIED_API/DOCS]` | Query from `GET /v1/feeTiers` |
| 10 | Taker Fee (Base Tier) | **2.25 bps** (225 ppm) | `[VERIFIED_API/DOCS]` | Query from `GET /v1/feeTiers` |
| 11 | Maker Rebates | **0.00 bps** for tiers 0–4 | `[VERIFIED_API/DOCS]` | Rebates only activate at VIP tier (>= $1B volume) |
| 12 | Minimum Order Notional | **$5.00 USD** | `[VERIFIED_API/DOCS]` | Enforced per market (`minOrderNotional: "5"`) |
| 13 | Minimum Order Size | e.g. 0.0001 BTC, 0.001 ETH, 0.0001 NVDA | `[VERIFIED_API/DOCS]` | Enforced per market (`minOrderSize`) |
| 14 | Post-Only Quoting | Supported via `timeInForce: "ALO"` (`t: 3`) | `[VERIFIED_API/DOCS]` | Skips 50ms taker speed bump; rejects on cross |
| 15 | Cross Rejection Code | `POST_ONLY_WOULD_CROSS` | `[VERIFIED_API/DOCS]` | Engine-level rejection code |
| 16 | Self-Trade Prevention | Blocked with `SELF_TRADE` | `[VERIFIED_API/DOCS]` | Engine-level rejection code |
| 17 | `goodTilTime` Constraint | Mandatory epoch $\mu$s $\ge$ 30 days ahead | `[VERIFIED_API/DOCS]` | Required even on IOC/FOK for replay protection |
| 18 | Integer Price Ticks (`p`) | `price ÷ tickSize` (exact integer) | `[VERIFIED_API/DOCS]` | Any fractional tick raises validation reject |
| 19 | Integer Size Quantums (`q`)| `quantity ÷ stepSize` (exact integer) | `[VERIFIED_API/DOCS]` | Any fractional quantum raises validation reject |
| 20 | Subaccount Order Pool | 20,000 starting cap | `[VERIFIED_API/DOCS]` | Verified live from `GET /v1/rateLimit` |
| 21 | Subaccount Cancel Pool | 40,000 starting cap | `[VERIFIED_API/DOCS]` | Verified live from `GET /v1/rateLimit` |
| 22 | Action Pool Replenishment| +1 unit per $0.10 traded notional | `[VERIFIED_API/DOCS]` | Verified from documentation |
| 23 | Drip Headroom Rate | 1 action per 10 seconds per pool | `[VERIFIED_API/DOCS]` | Active when pool reaches 0 |
| 24 | `cancelAllOrders` Cost | 1,000 cancel pool units | `[VERIFIED_API/DOCS]` | Flat charge against cancel pool |
| 25 | Modify Order Cost | 1 order pool unit | `[VERIFIED_API/DOCS]` | Single modify charges order pool |
| 26 | IP Weight Capacity | 1,500 units | `[VERIFIED_API/DOCS]` | Token bucket per IP |
| 27 | IP Weight Refill | 25 units / second (1,500 / min) | `[VERIFIED_API/DOCS]` | Continuous token refill |
| 28 | Order Write IP Cost | **0 IP weight** | `[VERIFIED_API/DOCS]` | Single writes are free on IP layer |
| 29 | Batch Write IP Cost | $\lfloor N / 40 \rfloor$ IP weight | `[VERIFIED_API/DOCS]` | Up to 39 orders costs 0 IP weight |
| 30 | Dead-Man's Switch | `POST /v1/scheduleCancel` | `[VERIFIED_API/DOCS]` | 5s to 300s window; 10 auto-fires/day cap |
| 31 | WS Subscriptions Limit | 100 per connection, 1,000 per IP | `[VERIFIED_API/DOCS]` | Connection auto-closed after 24h |
| 32 | WS Snapshot Delivery | In `subscribed` frame | `[OBSERVED_EMPIRICAL]` | Verified live on `bbo` and `markets` channels |
| 33 | WS Initial Sequence Jump| Snapshot lags delta stream | `[VERIFIED_API/DOCS]` | Initial gap > snapshot.lastSequenceId is valid |
| 34 | Mid-Stream Sequence Gap | Must be strictly contiguous ($+1$) | `[VERIFIED_API/DOCS]` | Gaps indicate loss; require full resync |
| 35 | In-Frame Repeated Prices| Applied strictly in frame order | `[VERIFIED_API/DOCS]` | Verified in order book state machine tests |
| 36 | Queue Priority (Modify) | Size decrease preserves; price/increase loses | `[VERIFIED_API/DOCS]` | Documented queue-priority behavior |
| 37 | Funding Settlement | Hourly (3600 seconds) | `[VERIFIED_API/DOCS]` | Spaced by 3600s intervals |
| 38 | Reference Prices | Oracle (`pythId`), Mark, Last Trade | `[VERIFIED_API/DOCS]` | Exposed on each market row |
| 39 | Initial Margin Fraction | 0.025 on BTC/ETH (40x leverage) | `[VERIFIED_API/DOCS]` | Up to 0.10 on equities (10x) |
| 40 | Account Read Privacy | Publicly readable with `?address=` | `[VERIFIED_API/DOCS]` | No auth required for reads; auth for writes |

---

## 3. High-Priority Implications for $50–$100 Market Making

1. **Zero Maker Fee Advantage**:
   - At Base tier, maker fees are **0.0 bps**.
   - Unlike venues charging 1–2 bps to makers, Arcus does not penalize passive fills with a fee.
   - However, **no maker rebate exists** at this capital tier (rebates start at VIP tier requiring $1B volume). Every basis point of net edge must come entirely from **gross spread captured minus adverse selection**.

2. **$5 Minimum Notional Constraint**:
   - With $50 capital, a single $5 clip represents **10% of total equity**.
   - With $100 capital, a $5 clip represents **5% of total equity**.
   - Two-sided quoting ($5 bid + $5 ask) consumes $10 notional, or 10–20% of capital per market. This is viable, but precludes simultaneous quoting across more than 2–3 markets.

3. **Rate-Limit Action Budget**:
   - Starting pool: 20,000 orders and 40,000 cancels.
   - For a fill of $5, volume replenishment is $5 / $0.10 = 50 units.
   - An aggressive quote-churn strategy submitting 100 requotes per fill will rapidly exhaust the 20,000 unit starting pool and fall into the 1-action-per-10s drip throttle.
   - **Mandatory Strategy Implication**: Quoting must implement strict requote thresholds (minimum reservation price displacement or time threshold) to prevent wasteful churn.

---

## 4. Phase 0 Acceptance Criteria Verification

- [x] Current venue mechanics documented and versioned in `reports/phase_0_venue_constraints.json` and `configs/venue_verified.yaml`.
- [x] Testnet & Mainnet connectivity verified live.
- [x] L2 reconstruction and sequence rules implemented and verified by 23 passing tests.
- [x] Order lifecycle representation validated (Scheme 1 canonical JSON, integer ticks/quantums, goodTilTime bounds).
- [x] Action-budget rate limit rules modeled.
- [x] Research is technically feasible.

**Phase 0 Status: APPROVED & COMPLETE.** Proceeding to Phase 1.
