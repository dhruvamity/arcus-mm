# Arcus MM

> Quantitative Research, Market Microstructure Analysis, and Passive Market-Making Framework for Arcus Perpetuals.

---

## Overview

**Arcus MM** is an empirical quantitative trading and research platform designed to evaluate and execute passive market-making strategies on Arcus perpetual futures contracts under low-capital envelopes ($50–$100).

The system implements high-fidelity market data recording, strict deterministic event-driven backtesting, venue microstructure modeling, and live paper execution against real-time mainnet WebSocket streams.

---

## Architecture & Core Components

```
arcus-mm/
├── configs/
│   └── venue_verified.yaml         # Verified venue constraints, fees, speed bumps, off-hours rules
├── src/
│   ├── auth.py                     # Ed25519 cryptographic signing (Scheme 1 & 2)
│   ├── session_calendar.py         # Timezone-aware regime classifier (US-RTH, OPEN_30, MON_GAP)
│   ├── config.py                   # Pydantic environment configuration & safety locks
│   ├── ws_client.py                # High-resilience WebSocket client with heartbeat & reconnect
│   ├── rest_client.py              # REST API client with IP rate-limit bucket tracking
│   ├── orderbook.py                # L2 orderbook reconstructor with sequence validation
│   ├── recorder.py                 # Multi-socket stream recorder with connection pooling
│   ├── paper_trader.py             # Live mainnet paper execution engine (dual Model C/B)
│   ├── backtester.py               # Deterministic event-driven historical playback engine
│   ├── adverse_selection.py        # Markout horizons analyzer (100ms to 60s)
│   ├── normalizer.py               # Raw JSONL to Parquet normalization pipeline
│   ├── models/
│   │   ├── fill.py                 # Strict fill engines (Model A, B, and gating Model C)
│   │   ├── pnl.py                  # Balance sheet accounting identity & 5-way attribution
│   │   ├── latency.py              # Empirical latency models (p50/p95/p99)
│   │   └── rate_limit.py           # Dual-pool action budget simulator
│   └── strategies/
│       ├── base.py                 # Abstract market-making strategy interface
│       ├── fixed_spread.py         # Static spread control baseline
│       ├── avellaneda_stoikov.py   # Calibrated inventory risk-aversion quoting
│       ├── volatility_clock.py     # Microstructural volatility clock adaptation
│       └── adaptive_mm.py          # Production adaptive MM with OFI & inventory leaning
├── scripts/
│   ├── run_recorder.py             # Multi-socket detached recorder runner
│   ├── check_recorder_health.py    # Recorder health telemetry & disk monitoring
│   ├── run_paper_trader.py         # Multi-market live paper trading runner
│   ├── test_replay_parity.py       # Replay parity verification suite
│   ├── run_phase_14_backtest.py    # Phase 14 walk-forward backtest runner
│   ├── measure_latency.py          # Empirical host RTT & clock skew benchmarking
│   └── verify_report.py            # Prose-to-table numerical consistency validator
├── tests/
│   ├── test_harness_integrity.py   # Deterministic unit tests (monotonicity, PnL identity, queue)
│   ├── test_auth_and_signing.py    # Cryptographic signature verification
│   └── arcus_*/                    # Connectivity, lifecycle, and sequence tests
├── research/
│   ├── audit.md                    # Defect ledger and technical remediation tracking
│   ├── prereg_backtest.md          # Pre-registered walk-forward splits & gating criteria
│   ├── claims_ledger.md            # Forward-tracing prose claim-to-table provenance map
│   ├── progress_log.md             # Research progress and gate milestone logs
│   └── assumptions_registry.md    # Venue mechanics and modeling assumptions
└── reports/
    ├── latency_summary.md          # Measured host round-trip latency distribution
    ├── phase_14_backtest_7d.md     # Multi-day walk-forward backtest report
    └── phase_15_live_paper_report.md # Multi-market live paper trading report
```

---

## Key Engineering Features

### 1. High-Resilience Multi-Socket Stream Recorder
- Subscribes to 20 perpetual markets across 2 socket pools ($\le 50$ subs/socket, avoiding venue disconnect limits).
- Automated 23-hour connection rotation with 15-second overlapped handoff.
- Continuous sequence gap detection, duplicate filtering, and hourly REST state snapshots (`/v1/markets`, `/v1/fundingRates`).
- Runs detached under `caffeinate -dimsu` to withstand operating system sleep.

### 2. Timezone-Aware Regime Engine (`America/New_York`)
- Distinguishes 24/7 crypto perpetuals from equity/commodity perps that trade with underlying closed markets.
- Identifies specific microstructural regimes:
  - `US_RTH`: 13:30–20:00 UTC (09:30–16:00 EDT)
  - `OPEN_30`: First 30 minutes of regular trading hours (widen/pause quotes)
  - `CLOSE_30`: Last 30 minutes before regular trading close
  - `MON_GAP`: Weekend-to-weekday transition window

### 3. Strict Fill Monotonicity & FIFO Queue Mechanics
- Guaranteed fill ordering: $\text{Fills}(\text{Model A}) \ge \text{Fills}(\text{Model B}) \ge \text{Fills}(\text{Model C})$.
- **Model A (Optimistic)**: Immediate touch fill (diagnostic upper bound).
- **Model B (Queue-Aware)**: Strict FIFO queue volume depletion behind displayed depth; size decreases preserve queue priority, while price modifications or size increases forfeit priority.
- **Model C (Conservative Gating)**: Requires trades strictly through the quoted price; gating model for all deployment decisions.

### 4. Mathematical PnL & Attribution Identity
Enforces the balance sheet identity at every simulation step:
$$\text{Cash} + \text{Position} \times \text{Mid} - \text{Fees} \pm \text{Funding} \equiv \text{Equity}$$
- Charges 2.25 bps taker fee on forced inventory flattens.
- Exact 5-way attribution: Spread PnL, Inventory MTM, Adverse Selection, Fees, and Funding.

### 5. Replay Parity Testing
- Live paper sessions record raw WebSocket messages tick-by-tick.
- `scripts/test_replay_parity.py` feeds raw ticks back into the deterministic backtester to verify that simulated paper execution matches backtest replay within numerical precision.

---

## Getting Started

### Prerequisites
- Python 3.11+
- Virtual environment recommended

### Installation
```bash
git clone https://github.com/dhruvamity/arcus-mm.git
cd arcus-mm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration
Copy the template and configure your environment:
```bash
cp .env.example .env
```
*(Note: Never commit your `.env` file or API keys to version control. Strict safety guards prevent real mainnet order placement).*

### Running Unit Tests
```bash
python3 -m unittest discover tests
```

### Checking Report Verification
```bash
python3 scripts/verify_report.py
```

### Measuring Host Latency
```bash
python3 scripts/measure_latency.py --samples 50
```

### Running Live Paper Trading (Simulated Execution on Live Mainnet Feeds)
```bash
python3 scripts/run_paper_trader.py --duration 300 --markets "HYPE-USD,ZEC-USD,NEAR-USD,SPCX-USD,BTC-USD"
```

### Verifying Replay Parity
```bash
python3 scripts/test_replay_parity.py
```

---

## Safety & Non-Negotiable Rules

1. **Zero Real Mainnet Orders**: Hardcoded mainnet order-submission locks are active. The framework exclusively performs public read-only streaming and local paper execution.
2. **Report Integrity**: Non-negotiable Rule 3 requires that every prose metric in research reports traces directly to an underlying computed table cell validated by `scripts/verify_report.py`.
3. **Regime Stratification**: Weekend data and weekday US-RTH sessions are treated as strictly distinct regimes and are never pooled into misleading headline numbers.

---

## Secrets Policy & Key Management

1. **Never Commit Secrets**: Never commit `.env`, `.pem`, `.key`, or any sensitive credentials to git. The `.gitignore` strictly excludes these.
2. **Never Share Bundles Containing Secrets**: Always generate bundles using `python scripts/generate_repo_bundle.py`, which validates against `git ls-files`, strictly ignores `.env*` (except `.env.example`), and runs an automated AST/regex secret scan prior to generation.
3. **Immediate Rotation on Exposure**: If credentials ever appear in untrusted environments or unredacted files, immediately revoke and rotate API keys via the Arcus console.
4. **Secret Scanner in CI**: Run `python scripts/secret_scan.py` to inspect tracked files. CI fails automatically if any potential private keys, API secrets, or unmocked wallet addresses are detected.

---

## License

Apache-2.0 or MIT (Proprietary Quantitative Research Scaffold).
