# arcus-mm — how to run it

Market-making research and a paper trading bot for Arcus perpetuals. Nothing here places real
orders. What the research found is in [`research/FINDINGS.md`](research/FINDINGS.md); this file
only explains how to run things.

---

## 1. Paper trading bot with Docker (recommended)

### Do I need a `.env`?

**No.** The bot only reads public market data, so it needs no Arcus keys or wallet. The Docker
image already sets everything it needs (mainnet data, order lock on). Your `.env` is never copied
into the image, even if one sits in the folder.

### What you need
- Docker Desktop (Mac/Windows) or Docker Engine + Compose (Linux), running.
- Internet access, and about 2 GB free disk for the first day (finished days are compressed to
  roughly 50–100 MB each).

### Start, check, watch, stop

Run these from the repo folder (the one with `docker-compose.yml`):

```bash
docker compose up -d --build
```
Builds the image and starts the bot in the background. It restarts itself after a crash or reboot.

```bash
docker compose ps
```
Shows whether it is running and `healthy`.

```bash
docker compose logs -f
```
Live log. Ctrl+C stops watching, not the bot.

```bash
docker compose down
```
Stops the bot cleanly. Your data stays.

### What it does
1. Records the live Arcus order book, trades and prices for GLD, NVDA, HYPE, SPY and ETH.
2. Every 30 minutes, replays today's recording through the strategy using the same engine as the
   backtests. That engine models queue position, delay, post-only rules and Arcus's action limits.
   Each strategy runs twice:
   - `frozen`: the pre-registered settings.
   - `guarded`: double the delay, plus a $2/day loss stop.
3. Shortly after midnight UTC, finalises yesterday's results and compresses yesterday's recording.

### Where the results are
Everything goes into the `paper_data/` folder next to `docker-compose.yml`:

| file | what's in it |
|---|---|
| `paper_data/paper/SUMMARY.md` | the scoreboard: PnL, fills, worst day per strategy, and PnL by day |
| `paper_data/paper/ledger.csv` | one row per strategy per day (opens in Excel/Sheets) |
| `paper_data/paper/days/<date>/` | full result and every simulated fill for that day |
| `paper_data/paper/status.json` | recorder alive or not, free disk, finished days |
| `paper_data/raw/`, `paper_data/compressed/` | the recorded market data itself |
| `paper_data/logs/` | bot and recorder logs |

A `*` next to a date in `SUMMARY.md` means that day is still in progress.

### Moving results to another laptop
1. On the server: `docker compose down`.
2. Copy the whole `paper_data/` folder (USB, AirDrop, `scp`…) into this repo folder on the other
   laptop, next to `docker-compose.yml`.
3. Optional: rebuild the scoreboard there with `docker compose run --rm paper summary`.
   - Without Docker, copy the *contents* of `paper_data/` into `data/` instead, then run
     `.venv/bin/python scripts/paper_bot.py summary`.

Every number can be recomputed from the recorded data, so nothing is lost in the move.

### Changing what it trades
1. Edit [`configs/paper.yaml`](configs/paper.yaml): markets, distance from mid, order size, limits.
2. Rebuild with `docker compose up -d --build`.

Leave strategies C1–C4, K1 and K2 unchanged until the 2026-09-22 → 09-28 test week has been
scored (see `research/oos_plan.md`). Add new ideas under new ids.

### One-off commands inside Docker
```bash
docker compose run --rm paper score --day 2026-09-22
```
Re-scores one day now. Add `--final` only for a day that has finished.

```bash
docker compose run --rm paper summary
```
Rebuilds `SUMMARY.md` and `ledger.csv`.

---

## 2. Running things without Docker

### One-time setup
Needs Python 3.12. Create the environment:

```bash
python3.12 -m venv .venv
```

Install the pinned dependencies:

```bash
.venv/bin/pip install -r requirements.lock
```

### Do I need a `.env` here?
- **Paper bot, downloads, analyses, backtests:** no.
- **The recorder, when you start it by hand:** it must be told `ARCUS_ENVIRONMENT=mainnet`, or it
  records the testnet instead. Put that one line in `.env`, or prefix the command with it (shown
  below). No keys needed.
- **Only for the signed testnet order tests** (`scripts/validate_testnet_plumbing.py`,
  `scripts/testnet_conformance.py`):
  1. Copy `.env.example` to `.env`.
  2. Fill in `ARCUS_WALLET_ADDRESS`, `ARCUS_ACCOUNT_INDEX`, `ARCUS_API_KEY` and
     `ARCUS_API_PRIVATE_KEY`. `scripts/generate_keys.py` makes a keypair.
  3. Leave `ARCUS_MAINNET_ORDER_LOCK=true`, and never commit `.env`.

### Paper bot (same as Docker, directly on your machine)
Results go to `data/paper/`.

```bash
.venv/bin/python scripts/paper_bot.py run
```
Records and scores continuously.

```bash
.venv/bin/python scripts/paper_bot.py score --day 2026-09-22
```
Scores one day.

```bash
.venv/bin/python scripts/paper_bot.py summary
```
Rebuilds the scoreboard.

### Recorder only
```bash
ARCUS_ENVIRONMENT=mainnet .venv/bin/python scripts/run_recorder.py --duration 0 --markets GLD-USD,NVDA-USD,HYPE-USD
```
Runs until you press Ctrl+C and writes to `data/raw/<date>/<market>/`. Leave out `--markets` to
record the default 20 markets.

```bash
.venv/bin/python scripts/check_recorder_health.py
```
Health report for a running recorder.

```bash
.venv/bin/python scripts/storage_manager.py --daily-close 2026-09-21 --delete-raw
```
Compresses a **finished** day (checksum-verified) and removes its raw files. Never run it on today's date.

### Download history
```bash
.venv/bin/python scripts/pull_trade_history.py --markets SPY-USD,HYPE-USD
```
Downloads every Arcus trade since 2026-06-30 to `data/history/trades/`. Re-running only adds new trades.

```bash
.venv/bin/python scripts/pull_binance.py --kinds aggTrades,klines,fundingRate
```
Downloads Binance trade data, candles (5m, 15m, 1h, 4h, 1d, 1w) and funding since 2023-09 for the
Arcus-equivalent assets, to `data/binance/`. Useful options:
- `--symbols futures/um:HYPEUSDT`: one asset only.
- `--since 2021-01`: go further back.
- `--daily 2026-09`: the current month's daily files.

```bash
.venv/bin/python scripts/verify_downloads.py
```
Checks nothing is missing or corrupted. It re-verifies Binance checksums and spot-checks Arcus
trades against the live API.

### Research and backtests
Each command writes a report to `research/`.

```bash
.venv/bin/python scripts/maker_economics.py
```
Who makes money providing liquidity on the recorded data, per market and depth.

```bash
.venv/bin/python scripts/deep_quote_backtest.py --markets GLD-USD,NVDA-USD --depths 2,3,5 --rate-limit --stop-usd 2
```
Replays the strategy on the recorded order book. Useful options:
- `--rtt 400`: a slower connection.
- `--from-day` / `--to-day`: choose the dates.
- `--order-units 0 --cancel-units 0`: start with no action budget left.

```bash
.venv/bin/python scripts/sweep_history.py
```
Profit of resting orders by depth: week by week on Arcus, month by month on Binance.

```bash
.venv/bin/python scripts/validate_sweep_proxy.py
```
Checks the trade-only estimate used by `sweep_history.py` against real quotes.

```bash
.venv/bin/python scripts/fair_value_study.py
```
Whether Binance's price predicts which Arcus fills win.

```bash
.venv/bin/python scripts/fair_value_backtest.py
```
Replays quoting around Binance's price. `--rtt 20 --feed-delay 5` simulates a co-located server.

```bash
.venv/bin/python scripts/binance_replay.py
```
The strategy replayed on Binance's own trade history.

### Score the frozen test week (after 2026-09-29 00:00 UTC)
```bash
.venv/bin/python scripts/deep_quote_backtest.py --markets GLD-USD,NVDA-USD,HYPE-USD,SPY-USD,ETH-USD --depths 2,3,5 --from-day 2026-09-22 --to-day 2026-09-28 --out research/oos_result.md
```
The pass/fail rules are in `research/oos_plan.md`.

### Tests
```bash
bash scripts/ci.sh
```
Runs the code check, all unit tests and the secret scan. Run it before every commit.

---

## 3. Folder map

```
configs/     venue facts, latency model, paper bot settings (paper.yaml)
src/         Arcus clients, recorder, tape loaders, replay engine (replay.py), strategies
scripts/     everything runnable (listed above)
research/    findings and generated reports
tests/       unit tests
prompts/     the original plan and later instructions
data/        recordings and downloads (not in git)
paper_data/  Docker bot output (not in git)
propr/       separate Propr experiment, not used by anything above
```
