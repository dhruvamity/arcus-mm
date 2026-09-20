# Arcus MM

> Quantitative Research, Market Microstructure Analysis, and Passive Market-Making Simulation Framework for Arcus Perpetuals.

---

## Current Status

**Headline Status:** `INCONCLUSIVE — no strategy validated`  
**Current Milestone:** Gate G2 Checkpoint (Pre-Registration Protocol v3.1 Draft & WS-G Pilot Microstructure Analysis complete).  
**Operating Constraints:**
- `APPROVE_MAINNET_ORDERS = NO`: Zero real mainnet order placement. Public read-only streaming and local simulation only.
- `APPROVE_TESTNET_FAUCET_FUNDING = NO`: No testnet faucet funding or order placement.
- `APPROVE_RECORDER_HANDOVER = NO`: Continuous PID 11661 tape audit without termination.
- `APPROVE_REPO_CLEANUP = YES`: Stale legacy files purged per Mandate v3 Appendix B.

---

## Overview

**Arcus MM** is a quantitative research and simulation platform built to investigate whether passive market-making on Arcus perpetual futures can produce robust, positive net expectancy under realistic fill dynamics, queue positioning, rate limits, discrete hourly funding, wire latency, and adverse selection.

The codebase enforces strict empirical honesty: no hard-coded statuses, zero imputation of variance or sample sizes, verified two-clock time separation, independent simulation contexts per fill model, and automated mutation testing to prevent regression.

---

## Architecture & Directory Layout

```
arcus-mm/
├── configs/
│   └── venue_verified.yaml         # Verified venue constraints, fees, speed bumps, off-hours rules
├── src/
│   ├── venue.py                    # Canonical venue metadata, fee tiers, and market specifications
│   ├── auth.py                     # Ed25519 cryptographic request signing (Scheme 1 & 2)
│   ├── session_calendar.py         # Timezone-aware regime classifier (US-RTH, OPEN_30, MON_GAP)
│   ├── config.py                   # Pydantic environment configuration & safety locks
│   ├── ws_client.py                # High-resilience WebSocket client with heartbeat & reconnect
│   ├── rest_client.py              # REST API client with IP rate-limit bucket tracking
│   ├── orderbook.py                # LocalOrderBook with sequence tracking & gap invalidation
│   ├── recorder.py                 # Multi-socket stream recorder with connection pooling
│   ├── paper_trader.py             # Live mainnet paper execution pump
│   ├── adverse_selection.py        # Markout horizons analyzer (1s to 60s)
│   ├── sim/
│   │   └── engine.py               # Canonical unified SimEngine (replaces legacy backtester)
│   ├── models/
│   │   ├── fill.py                 # Fill models (Model A Touch, Model B FIFO Queue, Model C Gating)
│   │   ├── pnl.py                  # PnL accounting identity & 5-way attribution
│   │   ├── latency.py              # Empirical latency sampling models
│   │   └── rate_limit.py           # Subaccount action budget simulator (order/cancel pools)
│   └── strategies/
│       ├── base.py                 # Abstract strategy interface
│       ├── fixed_spread.py         # Static spread control baseline
│       ├── adaptive_mm.py          # Adaptive MM with OFI & inventory leaning
│       ├── volatility_clock.py     # Microstructural volatility clock adaptation
│       ├── avellaneda_stoikov.py   # Inventory risk quoting (uncalibrated / NOT TUNABLE)
│       ├── donothing.py            # Paired control baseline (0 bps)
│       └── random_side.py          # Paired control baseline (structural selection test)
├── scripts/
│   ├── ci.sh                       # Multi-version CI runner (Py3.12/Py3.14, pyflakes, tests, mutations)
│   ├── ev.sh                       # Rule-3 evidence capture wrapper
│   ├── run_recorder.py             # Multi-socket detached recorder runner
│   ├── check_recorder_health.py    # Recorder telemetry & disk monitor
│   ├── run_paper.py                # Unified live paper session runner
│   ├── run_pilot_analysis.py       # WS-G pilot microstructure & power analysis runner
│   ├── measure_latency.py          # Empirical wire latency benchmarking (/v1/time)
│   ├── storage_manager.py          # Daily close compression & 40GB alarm monitor
│   ├── data_manifest.py            # SHA-256 chained cryptographic manifest generator
│   ├── reconcile_trades.py         # REST-to-tape trade reconciliation
│   ├── verify_trade_side_semantics.py # Pre-trade BBO trade side classification verifier
│   ├── mutation_check.py           # SimEngine 17/17 mutation harness
│   ├── generate_audit_report.py    # Generates research/audit.md from audit_status.json
│   ├── generate_status_report.py   # Generates reports/status.md from live telemetry
│   └── verify_report.py            # Report consistency & provenance verifier
├── tests/
│   ├── test_sim_engine.py          # SimEngine unit tests (queue, discrete funding, risk recovery)
│   ├── test_harness_integrity.py   # Fill monotonicity, PnL identity, quantisation tests
│   ├── test_report_provenance.py   # Report verifier tests (empty hash, constant columns, latency)
│   ├── test_calendar_regimes.py    # Timezone integrity & market calendar tests
│   ├── test_storage_manager.py     # Daily close compression & manifest chaining tests
│   ├── test_security_scanner.py    # Git history & bundle secret scanner tests
│   └── arcus_*/                    # Venue connectivity, order lifecycle, sequence tests
├── research/
│   ├── audit.md                    # Master Audit Ledger (V-01 through V-32)
│   ├── audit_status.json           # Machine-readable audit source of truth
│   ├── methodology.md              # Consolidated mathematical & economic methodology
│   ├── prereg_backtest.md          # Pre-Registration Protocol v3.1 Draft
│   ├── pilot_summary.md            # WS-G Pilot Microstructure & Power Analysis report
│   ├── power_analysis_table.csv    # Empirical power and feasibility table (Market × Strategy)
│   └── assumptions_registry.md    # Venue mechanics and modeling assumptions
└── reports/
    ├── status.md                   # Machine-attested active system status (<= 1 page)
    └── clock_offset_analysis.md    # Empirical two-clock wire latency distribution
```

---

## Getting Started

### Prerequisites
- Python 3.12 reference interpreter (tested on Python 3.12.14 and 3.14.5)
- Git

### Installation
```bash
git clone https://github.com/dhruvamity/arcus-mm.git
cd arcus-mm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
```

### Running Continuous Integration (CI)
The unified CI suite runs pyflakes, the complete offline unit test suite across Python 3.12 and 3.14, the 17-mutation architectural harness, and an automated secret scan:
```bash
./scripts/ci.sh
```

### Running Individual Tools
- **Verify Reports**: `python3 scripts/verify_report.py reports/status.md research/pilot_summary.md`
- **Audit Reference Check**: `python3 scripts/check_audit_refs.py`
- **Measure Latency**: `python3 scripts/measure_latency.py --samples 50`
- **Run Pilot Analysis**: `python3 scripts/run_pilot_analysis.py --data-dir data/raw/2026-09-20 --output-dir research`
- **Run Mutation Harness**: `python3 scripts/mutation_check.py`
- **Run Live Paper Session**: `python3 scripts/run_paper.py --duration 120`

---

## Non-Negotiable Safety & Governance Invariants

1. **Zero Real Mainnet Orders**: Hardcoded mainnet order-submission locks are enforced across all execution modules.
2. **Deterministic Evidence (Rule 3 & 4)**: Every status claim in research ledgers must link to an evidence file generated via `scripts/ev.sh <ID> <slug> -- <command...>`. Hand-typed statuses and empty-string hashes are prohibited.
3. **Regime Stratification**: Weekend data is labeled `WEEKEND-ONLY, NOT TRANSFERABLE` and is never pooled with weekday US-RTH sessions.
4. **Honest Reporting**: `INSUFFICIENT DATA` and `NOT TUNABLE` are valid and expected classifications for illiquid instruments or uncalibrated models.

---

## License

MIT License. Copyright (c) 2026 Arcus MM Contributors.
