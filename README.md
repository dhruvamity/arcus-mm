# arcus-mm

Research code for passive market making on **Arcus perpetuals** (`api.arcus.xyz`).
Goal: find a market and quoting rule that is breakeven or better **net of fees, funding and
adverse selection**, prove it on recorded tape, then on testnet. No LLM in the trading path.
The original plan is in [`prompts/2026-09-19_v1.md`](prompts/2026-09-19_v1.md).

## Status (2026-09-22)

- **No strategy is validated yet.** Earlier "results" in this repo came from a paper trader that
  mixed prices across markets, and from hand-written tables with no generating script. Both
  were removed; see git history before commit `be35fca` if you need them.
- **Recorded tape is real and is the main asset**: full L2 deltas, trades, BBO, oracle and
  funding for 20 markets since 2026-09-19 (`data/raw/<date>/<market>/*.jsonl`, not in git).
- Mainnet orders are hard-locked (`ARCUS_MAINNET_ORDER_LOCK`). Nothing here places real orders.

## Layout

```
configs/      venue facts (fees, rate-limit pools, speed bump) and latency model
src/          clients (REST/WS/auth), recorder, order book, sim engine, fill/PnL models,
              strategies, execution stack (order manager, reconciler, watchdog)
scripts/      recorder + health/storage tools, universe and deep-history screens,
              latency/clock measurement, testnet plumbing, secret scan, ci.sh
research/     findings produced by scripts in this repo (each names its generator)
tests/        offline unit tests
prompts/      mandates and chat history that defined the project
propr/        isolated side experiment: Propr $5k trial on Hyperliquid (not Arcus)
```

## Setup

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.lock
cp .env.example .env   # fill in only if you need signed endpoints
bash scripts/ci.sh     # pyflakes + unit tests + secret scan
```

## Recorder

```bash
nohup caffeinate -dimsu .venv/bin/python scripts/run_recorder.py --duration 0 &
.venv/bin/python scripts/check_recorder_health.py
```

Raw JSONL grows by ~11–13 GB/day. `scripts/storage_manager.py` gzips closed days (~17× smaller).
