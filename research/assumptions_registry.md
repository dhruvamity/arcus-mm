# Assumptions Registry (Phase 14+ Audited)

Versioned log of all modeling assumptions, empirical sources, and validation status.  
**Last Audited:** 2026-09-19 18:32:00 UTC (Corrective Pass 2)

| Assumption Area | Baseline Model | Source | Verified Status | Venue Verification Requirement / Limitations |
|---|---|---|---|---|
| **Maker Fee** | 0.0 bps (Base tier) | `GET /v1/feeTiers` | `YES` | Higher volume tiers do not increase maker fee; rebate only at VIP ($1B vol) |
| **Taker Fee** | 2.25 bps (Base tier) | `GET /v1/feeTiers` | `YES` | Charged on aggressive uncrossing, forced flatten, and taker inventory limit exits |
| **Min Order Notional** | $5.00 USD | `GET /v1/markets` | `YES` | Orders below $5 rejected by venue engine; clip sizes strictly enforced per-market |
| **Order Pool Starting** | 20,000 units | `GET /v1/rateLimit` | `[DOCS_ONLY]` | Keyed strictly on `(address, accountIndex)` |
| **Cancel Pool Starting** | 40,000 units | `GET /v1/rateLimit` | `[DOCS_ONLY]` | `cancelAll` charges flat 1,000 units |
| **Pool Replenishment** | +1 unit per $0.10 fill notional | Arcus documentation | `[DOCS_ONLY]` | 10 units per $1.00 traded notional |
| **Drip Headroom** | 1 action per 10 seconds | Arcus documentation | `[DOCS_ONLY]` | Active when pool reaches 0 |
| **Queue Priority Model** | Size decrease at same price preserves priority; price change or size increase loses priority and joins back of queue | Arcus documentation (`/guides/orders`, `/api-reference/exchange/modify-order`) | `VERIFIED_SIMULATOR_ONLY` | **Venue unverified.** Unit tests (`test_queue_fifo_and_priority_modification`) verify local simulator logic only. **To verify against venue:** Must place resting order at queue tail on testnet, send modifyOrder reducing size, place separate order from a secondary account behind it, trigger partial matching fill, and verify fill order via fills stream. |
| **Adverse Selection** | Empirical forward markout across 100ms–60s horizons; unresolvable dropped | Phase 14+ Study (`src/adverse_selection.py`) | `IN PROGRESS` | Prior Phase 6 claim (-2.21 bps small vs sweeps) WITHDRAWN due to 20s clamped window artifact |
| **GoodTilTime** | >= 30 days ahead | Arcus documentation | `[DOCS_ONLY]` | Mandated on all orders for replay protection; enforced in signing layer |
| **Fill Models** | Evaluated under Model A, Model B, and Model C (Gating) | `src/models/fill.py` | `YES` | Model C strictly requires trade through price by >= 1 tick; prior Phase 7 smoke claims withdrawn |
| **Requote Policy** | 2-tick requote threshold discipline | Parameter specification | `HYPOTHESIS` | Prior "1.5–3.2 actions/fill" claim was derived from preliminary 20s smoke run and is **WITHDRAWN**. True actions/fill ratio will be empirically measured during multi-hour live paper trading runs on Sep 20 and Sep 21. |
| **Capital Scale Envelope** | $50–$100 experimental capital | Master prompt mandate | `YES` | Enforces min executable clips ($5.00–$14.82), max position limits |
| **Safety Invariance** | Strict read-only on Mainnet; zero live mainnet orders | Codebase configuration | `YES` | Enforced at networking layer, config guards (`mainnet_order_lock=True`), and paper engine |
| **Host Latency** | Empirical RTT distribution ($p50=185.23\text{ms}, p95=703.47\text{ms}$, stress=$1,203.47\text{ms}$) | `reports/latency_raw_samples.jsonl` | `YES (Local Host)` | Measured from local development machine. If production execution runs on an external server or cloud VM, latency MUST be re-measured on target host before validation. |
| **Regime Stratification** | Weekday US-RTH vs Weekend vs Off-hours | `src/calendar.py` | `YES` | Weekend results cannot transfer to weekdays |