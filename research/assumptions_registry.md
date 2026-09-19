# Assumptions Registry (Phase 14+ Audited)

Versioned log of all modeling assumptions, empirical sources, and validation status.

| Assumption Area | Baseline Model | Source | Verified? | Sensitivity / Limitations |
|---|---|---|---|---|
| **Maker Fee** | 0.0 bps (Base tier) | `GET /v1/feeTiers` | `YES` | Higher volume tiers do not increase maker fee; rebate only at VIP ($1B vol) |
| **Taker Fee** | 2.25 bps (Base tier) | `GET /v1/feeTiers` | `YES` | Charged on aggressive uncrossing, forced flatten, and taker inventory limit exits |
| **Min Order Notional** | $5.00 USD | `GET /v1/markets` | `YES` | Orders below $5 rejected by venue engine; clip sizes strictly enforced per-market |
| **Order Pool Starting** | 20,000 units | `GET /v1/rateLimit` | `[DOCS_ONLY]` | Keyed strictly on (address, accountIndex) |
| **Cancel Pool Starting** | 40,000 units | `GET /v1/rateLimit` | `[DOCS_ONLY]` | cancelAllCharges flat 1,000 units |
| **Pool Replenishment** | +1 unit per $0.10 fill notional | Arcus documentation | `[DOCS_ONLY]` | 10 units per $1.00 traded notional |
| **Drip Headroom** | 1 action per 10 seconds | Arcus documentation | `[DOCS_ONLY]` | Active when pool reaches 0 |
| **Queue Priority Model** | Size decrease preserves priority; price/increase loses | Arcus documentation | `YES` | Enforced in `FillEngine` & verified by deterministic unit tests |
| **Adverse Selection** | Empirical markout measured across 100ms–60s horizons | Phase 14+ Study (`src/adverse_selection.py`) | `IN PROGRESS` | Prior Phase 6 claim (-2.2 to +0.8 bps) WITHDRAWN due to 20s clamped window |
| **GoodTilTime** | >= 30 days ahead | Arcus documentation | `[DOCS_ONLY]` | Mandated on all orders for replay protection |
| **Fill Models** | Evaluated under Model A, Model B, and Model C (Gating) | `src/models/fill.py` | `YES` | Model C strictly requires trade through price; prior certification withdrawn |
| **Requote Policy** | 2-tick requote threshold discipline | Phase 7 & 8 Simulators | `YES` | Limits actions to 1.5–3.2 actions/fill; eliminates pool churn |
| **Capital Scale Envelope** | $50–$100 experimental capital | Master prompt mandate | `YES` | Enforces min executable clips ($5–$15.34), max 4 clips position limits |
| **Safety Invariance** | Strict read-only on Mainnet; zero live mainnet orders | Codebase configuration | `YES` | Enforced at networking layer, config guards, and paper engine |
| **Host Latency** | Empirical RTT distribution (p50: 158.5ms, p95: 640.3ms) | `scripts/measure_latency.py` | `YES` | Measured from test machine; replaces arbitrary 60ms assumption |
| **Regime Stratification** | Weekday US-RTH vs Weekend vs Off-hours | `src/calendar.py` | `YES` | Weekend results cannot transfer to weekdays |