# Arcus MM — Follow-Up Mandate (Phase 14+)
## Audit remediation → ≥7-day data and backtest → weekday-aware live test

**Issued:** Saturday 2026-09-19 (weekend). **Repo:** `arcus-mm`.
**Effect:** Supersedes the `GOAL_COMPLETE` status and the conclusions of Phases 0–13.

---

## 0. Situation

An independent audit of the Phase 0–13 reports and the agent log found that the **infrastructure is a reasonable scaffold**, but the **empirical conclusions are not supported by the data collected**. The whole Phase 1 → Phase 13 pipeline ran in ~17 minutes of wall-clock (13:41 → 13:58 UTC) on WebSocket recordings of ~20 seconds per market. "CONDITIONAL YES" and "CERTIFIED FOR DEPLOYMENT" are withdrawn. The correct current status is **INCONCLUSIVE — smoke-tested only**.

Your job now:
1. Withdraw the unsupported claims and log every defect (Section 2, 3).
2. Fix the harness so it can be trusted (Section 4).
3. **Start multi-day data collection immediately** — it cannot be recovered later (Section 5).
4. Run a rigorous, regime-aware **backtest on ≥ 7 days** of recorded data (Section 6).
5. Run a **live test of ≥ 3–4 hours on mainnet data with paper execution**, centred on Monday's US market open (Section 7).
6. Report honestly. **NO and INCONCLUSIVE are valid, welcome outcomes.**

---

## 1. Non-negotiable rules

1. **No real mainnet orders.** The hardcoded mainnet order-submission lock stays. Any real-money or funded step requires my explicit written approval. The account is unfunded, so the live test is **paper execution on live public mainnet data**.
2. **Hard gates.** Stop at each gate in Section 8, summarise, and wait when the gate says STOP. (The Phase 1 report said execution stops for approval before Phase 2, and the pipeline ran straight through anyway. State in `research/audit.md` whether approval was given. Do not repeat this.)
3. **Reports are generated from computed tables**, never hand-narrated. Every number in prose must trace to a table cell. Write `scripts/verify_report.py`, which fails if a narrated number does not match its table, and run it before finalising any report.
4. **Every metric carries N** (fills, trades, hours, days) and a confidence interval. No conclusions from zero or a handful of fills.
5. **No word "CERTIFIED".** Allowed verdicts: `VALIDATED`, `NOT VALIDATED`, `INSUFFICIENT DATA`.
6. **No moving goalposts.** Thresholds in Section 6.6 are pre-registered. You may tighten them, never loosen them, and never after seeing results. Do not tune on out-of-sample data. List every market or config you drop and why.
7. Never delete existing data. Move the 20-second dataset to `data/smoke_test/`.

---

## 2. Audit ledger — known defects (copy into `research/audit.md` with status columns: Confirmed / Fixed / Test added)

### A. Data insufficiency and time-base
| ID | Finding (evidence) | Required action |
|---|---|---|
| A1 | Phase 3 recordings are 18–20 s per market. **SPCX: 0.0 s, 3 raw records.** SLV: 52 records. Yet Phase 7 reports 32–86 fills per run. | Explain exactly what data each backtest replayed. Invalidate all Phase 7/10 results. |
| A2 | SPCX and SLV have spread P5 = median = P95 (single static value) and annualized vol = NaN → effectively **one frozen BBO snapshot**. Consistent with a closed underlying market on Saturday. "Certification" of both is invalid. | Treat weekend equity/commodity/index perps as a separate regime (Section 5.4, 6.2). |
| A3 | Suspected time-base mismatch: `fetch_historical_rest.py` pulls ~200 REST trades and `enrich_with_candles.py` synthesises data; ZEC trades ~5,168/day (~0.06/s) cannot produce 41 fills in 20 s. | Prove alignment or remove it. **Fill simulation must use only WS-recorded trades + book on one monotonic clock.** REST trades/candles are for backfill studies only (vol, volume seasonality, funding), never quote-fill simulation. |
| A4 | All data is weekend data (Sat 2026-09-19). | Section 5 and 7. |

### B. Backtester and fill-model suspicion
| ID | Finding | Required action |
|---|---|---|
| B1 | **Model A ≡ Model B in every row** of Phase 7. Model C sometimes beats A/B (SPCX Fixed: A −0.01% vs C +0.05%; SLV VolClock A +0.03% vs C +0.06%; UNI OOS stress +0.45% vs base +0.24%). A stricter fill model should not earn more on the same path. | Queue logic is likely not binding or buggy. Fix; add monotonicity tests (Section 4). |
| B2 | **Infeasible clip sizes.** Backtests imply ~$8 clips on ZEC ($320 / 40 fills) and HYPE, but Phase 1 lists min executable clip ZEC $15.34, HYPE $9.24. | Enforce `minOrderSize`, step size, `minOrderNotional` per market; reject invalid sizes; use per-market min executable clip. |
| B3 | Avellaneda-Stoikov produced **0 fills** on HYPE/ZEC/SLV → quotes never reach touch; γ/κ mis-parameterised. | Calibrate from measured arrival intensity or report "not tunable". Zero-fill rows are not evidence. |
| B4 | Headline "ZEC Adaptive/Vol-Clock +0.20%" is actually **FixedSpread**; ZEC VolClock is +0.07/+0.07/+0.04%. Best-of-63 selection; Holm-Bonferroni claimed but no p-values shown. | Count all configs tried; report adjusted results or use Section 6.6 rules. |
| B5 | Latency fixed at 60 ms, not measured from the host that will run this. | Measure RTT distribution (Section 4.6); use empirical p50/p95/p99. |
| B6 | Unclear whether taker fee (2.25 bps) is charged on inventory-limit flattening and whether funding uses actual recorded rates. | Verify in code; add PnL identity test. |
| B7 | Phase 0 says ALO skips the 50 ms taker speed bump. The "colocated low-latency takers dominate" rationale for excluding majors ignores this. | Read docs: does the bump apply to cancels/modifies? Model it. Re-derive the mega-cap exclusion from data. |

### C. Markout study is degenerate
| ID | Finding | Required action |
|---|---|---|
| C1 | Phase 6: adverse selection is **identical at 500 ms, 1 s, 5 s and 30 s** for every market (HYPE −1.49 at all; NEAR +47.65 at all) → horizons are clamped to the last observation of a ~20 s window; 30 s/60 s are undefined on this data. | Strict horizons from recorded BBO mid; drop fills whose t+h exceeds data; report N per horizon; unit-test on synthetic random walk. |
| C2 | ZEC −16 to −20 bps "favourable" and LIT small-clip **+171 bps** are implausible; 200-trade sample with one-sided drift. | Recompute on ≥ 7 days; report distributions, not means only. |
| C3 | "Size-asymmetry discovery" contradicts its own table: small-clip AS is +171.23 (LIT) and −20.36 (ZEC), not "−2.2 to +0.8"; large-clip HYPE (−0.81) and ZEC (−12.05) are *favourable*. "Small" is defined vs the sample's median taker size ($27 HYPE … $1,165 SLV), unrelated to our clip, and quoting a small clip does not avoid being hit by a sweep. The "+1.8 to +3.5 bps per completed clip" appears in no table. | Withdraw. Re-test with fill-size buckets defined in $ and by sweep-cluster features. |
| C4 | Trade-tape markouts ignore fill selection (winner's curse): passive fills skew toward moves against you. | Measure markouts on *simulated passive fills* (Model B/C), not just tape trades; compare. |

### D. Reports contradict their own data
| ID | Finding |
|---|---|
| D1 | Phase 6 §4.3 claims NEAR/LIT/UNI net edge positive (+0.4 to +3.8 bps); table shows −43.45 / −83.61 / −27.94 bps. |
| D2 | Phase 7 §3 claims HYPE A-S and VolClock positive under all models and ZEC A-S positive; matrix shows A-S = 0 fills and HYPE VolClock −0.10/−0.10/−0.13%. |
| D3 | Phase 10 marks HYPE **PASS** with OOS −0.09%, stress −0.12%; SPCX OOS −0.00%; text claims positive OOS for HYPE/SPCX. The pass rule is evidently drawdown-only. UNI is PASS in Phase 10, HOLD in the final report. |
| D4 | Final report says HYPE is viable and "survives Model C" while its own table shows −0.11% (Model C) and −0.09% (OOS). SPCX "certified" at OOS 0.00%. |
| D5 | Phase 4 takeaways cite spreads (ZEC 3.5–4.5, NEAR 5.0–5.8 bps) that don't match the Phase 4 table (6.77, 8.40); SLV "mean-reverting" is a frozen market. |
| D6 | Phase 1 spreads for majors differ between reports (BTC 0.22 vs 0.012; ETH 0.04 vs 0.53; SOL 1.25 vs 0.09 bps); "SOL >30k trades/day" vs scan 19,431. The −1.49/−1.23/−1.46 bps "Model C survival" for BTC/ETH/SOL are Phase 1 heuristics, **never backtested**. |
| D7 | Phase 1 "Est. adverse selection" is a heuristic (1.5 bps floor, ≈0.225 × spread) so "net edge = half-spread − f(spread)": **wider spread always ranks better**. Circular, not evidence. |
| D8 | Phase 3 PASS gate has no minimum duration/coverage; 3 markets show 1 unexplained sequence discontinuity; SPCX has 0.0 s. |
| D9 | "Zero pool exhaustion" rests on a 15 s paper run with 0 fills; report says 0 orders placed yet pool shows 23 units consumed (unexplained). |
| D10 | Inconsistent sizing text: 8–16% vs 8–13% equity per clip; "leverage ≤ 2×" vs "≈ 0.5×". |

### E. Process and validation gaps
| ID | Finding | Required action |
|---|---|---|
| E1 | Phase 11 = 15 s, 0 fills. Phase 12 = local signing only; no venue round-trip. | Mark both `SMOKE TEST ONLY`. |
| E2 | Many Phase 0 items are tagged `[VERIFIED_API/DOCS]` but were never exercised (cancelAllOrders cost, modify cost, scheduleCancel, batch weights, speed bump). | Re-tag `[DOCS_ONLY]` until exercised. |
| E3 | The 23 tests cover connectivity/lifecycle/sequencing; none cover fill models, PnL accounting, markout horizons, time alignment or quantisation. | Add them (Section 4). |

**Keep (but treat as unverified under load):** the Phase 0 venue-mechanics registry as a hypothesis list, Ed25519 Scheme 1/2 signing, the L2 state machine + splice rule, Parquet pipeline structure, the rate-limit pool model, the universe-scan structure.

---

## 3. Immediate housekeeping (first 30 minutes)
1. Create `research/audit.md` from Section 2.
2. Prepend to `reports/final_research_report.md` and `research/progress_log.md`: **"SUPERSEDED — PRELIMINARY SMOKE TEST. Conclusions withdrawn pending Phase 14+."** Move old reports to `reports/archive_smoke_test/`.
3. Downgrade every "CERTIFIED"/"CONDITIONAL YES" string in the repo.
4. **Start the recorder (Section 5) before doing anything else long-running.** The 7-day clock starts when it starts.

---

## 4. Workstream 1 — Fix the harness (run in parallel with data collection)

**4.1 Tests (synthetic, deterministic).** Add and pass:
- **Fill monotonicity:** on an identical quote path, fills(A) ≥ fills(B) ≥ fills(C); and per-fill PnL differences explained. A stricter model must never produce a better result on the same path.
- **Queue model:** queue-ahead volume is consumed by trades in FIFO order; price change or size increase loses priority; size decrease keeps it.
- **PnL identity:** `cash + inventory × mid − fees ± funding == equity` at every step; 5-way attribution sums to total.
- **Markout horizons:** synthetic random walk with known drift → markout differs by horizon; unresolvable horizons dropped, never clamped.
- **Time alignment / lookahead:** one monotonic clock (`recv_ts_ns`); shifting trades vs book must change fills; assert no future data at decision time.
- **Quantisation:** tick/step rounding; reject below min size/notional; per-market min executable clip.
- **Determinism:** same input → identical output hash.

**4.2 Fill models.** A (touch, diagnostic only), B (queue-aware FIFO behind displayed depth; cancel/replace loses priority), **C (trade strictly through the price) is the gating model.** B ≠ A must be demonstrable.

**4.3 Cost and venue model.** Maker 0 bps, taker 2.25 bps (charged on any forced flatten), hourly funding from recorded rates, order/cancel pools with +1 unit per $0.10 traded notional and 1/10 s drip, 2-tick requote threshold as a parameter, 50 ms taker speed bump per docs, `cancelAllOrders` cost.

**4.4 Strategies.** Fixed spread (control), calibrated Avellaneda-Stoikov, Volatility Clock, Adaptive + OFI/microprice overlay, plus **baselines: do-nothing and random-side quoting.** Add rules for (a) inventory limits with passive reduce-only unwind, (b) flatten-before-close and pause/widen around session opens for equity/commodity/index perps.

**4.5 Docs research (use the `arcus-docs` MCP).** Record findings with sources in `configs/venue_verified.yaml`:
market hours and holiday handling for non-crypto perps; oracle/mark behaviour when the underlying is closed; funding formula; price bands/circuit breakers/halts; liquidation and margin (isolated vs cross); whether cancels/modifies are exempt from the speed bump; ALO semantics; testnet faucet or collateral options; how far back `/trades`, `/candles`, `/fundingRates` go and their pagination.

**4.6 Real latency.** Measure RTT from the exact machine/network that will run the tests: REST `/health`, WS subscribe-ack and ping, at several times of day for ≥ 24 h, logging p50/p95/p99 and clock skew. Feed the empirical distribution to the latency model; drop the hardcoded 60 ms.

**4.7 Quantisation of capital scenarios.** Run every simulation at both **$50 and $100** using each market's real minimum executable clip (Phase 1 shows ZEC $15.34, MU $10.08, HYPE $9.24, others ~$5). Markets whose min clip breaks the inventory envelope are excluded, and listed.

---

## 5. Workstream 2 — Multi-day data collection (start now; ≥ 7 × 24 h, ideally 10–14 days)

**5.1 Schedule.** Start immediately (Sat 2026-09-19). Minimum end: **Sat 2026-09-26**, covering this weekend, Mon–Fri weekdays and the following weekend start. Extend to a second weekend if possible. Interim rolling reports are allowed but must be labelled `PRELIMINARY`. Nothing is called a result until ≥ 7 days are recorded.

**5.2 Universe (~16 markets; ≤ 100 subscriptions per socket, so use several sockets with overlapped rotation < 23 h):**
- **Crypto candidates:** HYPE, ZEC, NEAR, LIT, UNI, AAVE, CASHCAT
- **Crypto control:** XRP
- **Mega-cap controls (test the exclusion with data):** BTC, ETH, SOL
- **Equity perps:** SPCX, NVDA, TSLA, GOOGL, AMD (add HOOD or MU if volume justifies)
- **Commodities/indices:** SLV, GLD, SPY, QQQ

Adjust after the Monday-morning universe re-scan (Section 7), but never drop a market mid-week; add only.

**5.3 Channels per market:** `l2OrderbookUpdates` (nLevels ≥ 20), `trades`, `bbo`, plus market/oracle/mark and funding data. Snapshot `/markets` and `/fundingRates` hourly. Backfill whatever REST history exists (≥ 14 days of 1m candles, funding) and report the achievable lookback. **L2 book history probably cannot be backfilled, so forward recording is the only source of book-level data. Say so explicitly if confirmed.**

**5.4 Regime tagging (`src/calendar.py`), applied to every event and every fill:**
- `dow_class`: weekend / weekday (UTC and exchange-local).
- `session` (UTC): ASIA 00:00–07:00, EU/US-PRE 07:00–13:30, **US-RTH 13:30–20:00** (EDT; use tz-aware `America/New_York`, do not hardcode offsets), US-LATE 20:00–24:00.
- `underlying_open` per asset class from an exchange calendar (equities/ETFs/indices/commodity ETFs; crypto always open) and a US holiday table.
- Event windows: `OPEN_30` (first 30 min after cash open), `CLOSE_30`, `MON_GAP` (Sun evening → Mon 14:00 UTC), and scheduled macro/earnings windows from a sourced static file (CPI, FOMC, NFP, relevant earnings). Mark source and uncertainty.

**5.5 Reliability (this must survive days unattended):**
- Run detached (`nohup`/`launchd`/`tmux`) and wrapped in `caffeinate -dimsu` so a laptop sleep doesn't create gaps; the agent session ending must not kill it.
- Watchdog + heartbeat file; auto-reconnect; overlapped socket rotation; disk rotation/compression; free-space alarm.
- **Hourly integrity report** (`reports/recorder_health/`): message rate per market/channel, sequence gaps, reconnects, gap intervals, disk use.
- On any gap: mark the interval; **never interpolate**; the backtester skips gap windows.
- **Data-quality gate (replaces Phase 3):** per market-day ≥ 98% wall-clock coverage excluding flagged gaps, zero unexplained mid-stream sequence gaps, minimum trade count. Failing market-days are excluded and listed.

---

## 6. Workstream 3 — ≥ 7-day backtest (weekday-aware)

**6.1 Principle.** Weekend results **do not transfer** to weekdays. Equity/commodity/index perps are likely frozen or thin on weekends (see A2) while weekdays bring informed flow, gaps and news. **Weekday US-RTH behaviour is the primary basis for any deployment decision; weekend is a separate, secondary regime.** Never pool regimes into one headline number.

**6.2 Regime-stratified reporting.** For every market: report separately (i) weekend, (ii) weekday by session, (iii) for non-crypto: underlying-closed vs underlying-open, (iv) `OPEN_30`/`CLOSE_30`/macro windows. Include a **regime-transfer table**: weekend-only estimates of spread, volume, trades/day, realised vol, toxicity, markouts, fill rate and PnL vs what actually happened on weekdays. Pooled numbers may appear only next to the per-regime numbers.

**6.3 Splits and walk-forward.** Chronological day-blocks only. Write `research/prereg_backtest.md` **and commit it before running any OOS evaluation.** Suggested design (adjust to the data you actually have, but fix it in advance): tune on the first weekdays (Mon–Wed), test on the remaining weekdays (Thu–Fri); evaluate weekend days as a separate held-out regime; ensure the OOS set contains ≥ 2 weekdays for every market you intend to validate.

**6.4 Simulation requirements.** Fill models A/B/C as in 4.2, gating on **Model C with empirical p95 latency and a +500 ms stress**; funding from recorded rates; taker fee on forced exits; pools and requote budgets; per-market min clip; $50 and $100 scenarios; multi-market portfolio with shared capital and the venue's actual margin mode.

**6.5 Robustness.** Sensitivity to clip size (1×/2×/3× min executable), spread floor, requote threshold, skew strength — as heatmaps; choose plateaus, not peaks. Compare against do-nothing and random-quoting baselines. Report time at inventory limits, worst day, max drawdown, actions per fill, pool low-water mark, and the markout curve at 100 ms, 500 ms, 1 s, 5 s, 30 s, 60 s **with N per horizon**.

**6.6 Pre-registered validation criteria (per market × strategy, weekday OOS, Model C + p95 latency):**
1. ≥ 300 simulated fills (else `INSUFFICIENT DATA`).
2. Net bps per fill > 0 with the lower bound of a 90% CI (bootstrap clustered by hour) > 0.
3. Positive on ≥ 60% of OOS weekday-days; no single day contributes > 50% of total PnL.
4. Positive after worst-case funding and taker-exit costs; max drawdown < 10% of capital; inventory limits respected.
5. Beats both baselines; Model B ≠ Model A and all Section 4.1 tests pass.
6. Result holds at both $50 and $100 scenarios (or is explicitly flagged as capital-dependent).

**6.7 Output.** `reports/phase_14_backtest_7d.md`: coverage table first (hours, trades, fills per market/regime), then verdict per market (`VALIDATED` / `NOT VALIDATED` / `INSUFFICIENT DATA`), the defect-ledger status, and a plain-language answer to the research question with its confidence level.

---

## 7. Workstream 4 — Live test (mainnet data, paper execution, ≥ 3–4 h)

**7.1 Mode.** Live public mainnet WebSocket feeds; simulated exchange; **zero real orders**. If the docs show a testnet faucet, tell me before proceeding: a funded-testnet order lifecycle (place → modify → cancel → cancelAll → scheduleCancel) would close the Phase 12 gap. If not fundable, propose the safest way to prove signatures are accepted (e.g. a signed testnet order expected to be rejected for collateral rather than auth) and **ask before sending it.**

**7.2 Timing.**
- **Primary session: Monday 2026-09-21, 12:30 → ≥ 16:30 UTC (target 17:00)**: one hour before US cash open (13:30 UTC), the open itself, and the first ~3 hours of RTH.
- **Weekend baseline:** one 3–4 h session this weekend (Sunday), same code, same markets.
- **Optional:** a Tue–Thu afternoon/close session (17:00–21:00 UTC) and an Asia-session run.
- If a feed drops or a session is invalid, rerun; do not stitch.

**7.3 Monday-morning universe re-scan.** Re-run the Phase 1 scanner around 12:00 UTC Monday (US pre-market). Quantify the weekend → weekday shift per market (spread, 24 h volume, trades, depth) and update the candidate pool. Explicitly list markets that were unattractive on Saturday but improve on Monday, and vice versa.

**7.4 Markets.** 8–10 simultaneously across categories: crypto (HYPE, ZEC, NEAR, UNI, LIT), equities (top-volume names from the Monday re-scan, e.g. SPCX/NVDA/TSLA/GOOGL/AMD), commodity (SLV or GLD), index (SPY or QQQ), plus BTC/ETH/SOL quoted in paper as controls. Independent paper capital per market, with $50 and $100 scenarios run side by side.

**7.5 Engine requirements.**
- **Dual fill logging in the same session:** Model C (gate) and Model B (shadow).
- Persist all raw WS data for the session, then **replay it through the backtester: replay parity test.** Paper fills and PnL must match the replay within tolerance; investigate any difference (this is the strongest check of the whole harness).
- Telemetry every 60 s: live quotes, requotes, actions used, pool levels, inventory, PnL attribution, spread, stale-feed ms, measured RTT.
- Kill switches (simulated): stale BBO > 3 s, crossed book, sequence gap (resync), inventory limit, paper daily-loss limit → cancel-all.
- **A/B in shadow:** strategy with the equity-open protocol (pause/widen around `OPEN_30`, flatten before close) vs without, to measure whether it matters.

**7.6 Success criteria (pre-declared).** A market is judged only if it reaches ≥ 30 paper fills in the session; otherwise `INSUFFICIENT DATA` (0 fills is never "positive"). Report fill rate per hour, realised vs backtest-expected fills for the same window, markouts, inventory path, action-pool usage, and per-hour PnL. Compare weekend vs Monday sessions directly.

**7.7 Output.** `reports/phase_15_live_paper_report.md`, with the per-market per-hour table, the regime comparison, replay-parity result, and RTT/latency findings.

---

## 8. Gates
| Gate | Condition | Action |
|---|---|---|
| G1 | Section 4.1 tests pass; audit ledger written; reports downgraded | Summarise, continue |
| G2 | ≥ 7 days recorded; data-quality gate passed per Section 5.5 | **STOP — summarise coverage, wait for OK** |
| G3 | Phase 14 backtest complete with Section 6.6 verdicts | **STOP — wait for OK** |
| G4 | Phase 15 live paper sessions complete, replay parity checked | **STOP — wait for OK** |
| G5 | Any funded step (testnet with collateral, then a tiny mainnet size with dead-man's `scheduleCancel`, hard loss cap, kill switch) | **My explicit written approval required** |

---

## 9. Deliverables
`research/audit.md`, `research/prereg_backtest.md`, `research/claims_ledger.md` (every claim → table/cell), `configs/venue_verified.yaml` (updated with sources), `src/calendar.py`, expanded `tests/`, `scripts/verify_report.py`, `reports/recorder_health/*`, `reports/phase_14_backtest_7d.md`, `reports/phase_15_live_paper_report.md`, updated `research/progress_log.md` and `research/assumptions_registry.md`, and a final short **status note** with: what was done and wall-clock durations, coverage table, defects fixed, verdicts, and the honest answer to the research question.

## 10. Order of operations
1. Housekeeping (Section 3). 2. **Start the recorder** (5.2–5.5). 3. Latency measurement (4.6) and docs research (4.5) while data accumulates. 4. Harness fixes and tests (4). 5. Weekend live baseline (7.2). 6. Monday: re-scan, then the primary live session. 7. Tue–Fri: monitor recorder health, produce PRELIMINARY interim reports only. 8. From 2026-09-26: final ≥ 7-day backtest (6) and reports. Stop at G2, G3, G4.
