# Arcus Market-Making System — Research & Build Plan

**What this document is.** A design and research plan — not an implementation, and not a set of code to run. It's written to be handed to a build/research agent that has Arcus API documentation access and Arcus credentials but **no funded live capital yet**. Every phase described here (screening, backtesting, forward-testing) runs on public market data and/or the Arcus **testnet**, which has an open-mint collateral faucet — none of it needs the $5,200 ceiling deployed. That ceiling only shapes the position-sizing *framework* in Section 5, written for if/when this graduates to live capital — a decision that is explicitly out of scope here.

---

## 1. Why this isn't built as an AI-agent swarm

The reviewed article's design is six "Grok Bot" interface bots (Quoting, Inventory, Risk, Reconciliation, Microstructure, Macro Filter) sitting on top of a "Kimi K3 Swarm Max" layer spawning roughly 300 parallel sub-agents (one per traded pair / monitored account / macro feed) — about 306 LLM agents total, coordinating through shared JSON files.

Both underlying products are real (verified independently, not just taken from the article): Kimi K3 is Moonshot AI's 2.8T-parameter MoE model with a 1M-token context and a genuine "Swarm Max" parallel-agent tier, and Grok Bot is a real xAI product (beta, August 2026) where named bots share one persistent cloud computer. So the critique below is about **fit for this task**, not about the tools being fake.

Four concrete reasons this doesn't carry over to a real trading system, in order of how much they matter:

1. **The job is I/O and arithmetic, not language reasoning.** What each of the 300 sub-agents does — watch a book, compute a mid-price, flag a threshold breach — is exactly what one WebSocket subscription plus vectorized numeric code handles for *hundreds* of instruments concurrently, in microseconds, at near-zero marginal cost. Spinning up LLM inference per instrument per polling tick to do arithmetic a `numpy` array does faster is the mismatch your own intuition flagged, and it's correct.
2. **It contradicts the article's own opening thesis.** Part 1 of the article correctly explains that inventory risk comes from quotes not being pulled fast enough when price moves — "if the price moves against you before your quote clears, you get run over." But the proposed loop updates quotes roughly once a second, mediated by natural-language bots and unsynchronized shared JSON files (a classic source of race conditions and stale reads, not a professional coordination mechanism). That's slower and less deterministic than what Part 1 says you need, even on the "retail-friendly" venues.
3. **Shared-everything security model, wired to real capital and public internet content.** xAI's own documentation states plainly that bots on one Grok Bot account share one filesystem, one set of browser sessions, and one set of credentials, and that **bot boundaries are not security boundaries**. The article's Macro Filter Bot is explicitly designed to ingest live, adversarial public content (X posts) and use it to trigger quote-pulling behavior, on the same shared machine as the bot holding kill-switch authority over real positions. That's a meaningfully different risk profile than using the same product for email or scheduling.
4. **The economics don't scale down.** SuperGrok Heavy runs $300/month; Kimi's tiers with swarm/parallel-agent access run $99–199/month — call it $400–500/month in subscriptions alone, before metered API usage from 300 continuously-polling agents. Against a $5,200 account, that's 8–10% of total capital *per month* in infrastructure, before a single cent of spread is captured. It doesn't even clear the article's own recommended test size ($200–500 on Polymarket) — one month of the required subscriptions costs more than the whole test account.

Where an LLM genuinely earns its place: **offline, low-frequency, human-gated analysis** — e.g., a periodic (daily, not per-tick) review of fills and PnL that proposes a parameter adjustment for a human to approve before it ships (the article's own Step 8 idea, used correctly: offline and gated, not live and autonomous). Using an AI coding assistant to help *write* the deterministic engine is a separate and unobjectionable use of AI — that's development tooling, not a production dependency. Arcus even documents first-party Claude Code / MCP integration for exactly this (`/ai-tools/claude-code`, `/ai-tools/mcp`).

**What replaces the swarm:** one process (or a small number of cooperating processes/threads), holding all state in memory, doing deterministic math on a WebSocket feed. See Section 3.

---

## 2. Product scope: Arcus **Perpetuals**, not Spot

This matters enough to state up front, because it determines the entire rest of the plan.

Arcus runs two structurally different products:

| | Perpetuals | Spot ("Stock Tokens") |
|---|---|---|
| Mechanism | Off-chain **central limit order book** (hybrid DEX: ~20ms trade confirmation, 100k+ orders/sec, non-custodial settlement via appchain + EVM rootchain) | **Router**, not an order book — sources liquidity from on-chain AMM pools and an RFQ network of pre-integrated professional makers |
| Can a retail bot post resting bid/ask quotes? | **Yes** — this is the whole product | **No** — there is no book of Arcus's own to rest an order on |
| Asset classes | Crypto, single-stock equities, commodity ETFs, index ETFs, all from one collateral balance | Tokenized equities only |

A classic post-bid/post-ask market-making bot has nothing to quote on in the spot product — becoming a spot liquidity source means formally integrating as an RFQ maker, a different undertaking entirely. **Every recommendation below is scoped to Arcus Perpetuals.**

---

## 3. System architecture (deterministic, single asset)

Five components, one continuous loop. No natural-language interface, no LLM in the hot path.

1. **Market data feed** — WebSocket subscriptions (`l2Orderbook`/`l2OrderbookUpdates`, `trades`, `bbo`, `funding`, mark/oracle price) for the one chosen market. Arcus's own latency guidance is explicit: WebSocket over REST polling for anything that changes frequently, 2 CPU/4GB minimum (4 CPU/8GB for full-depth subscriptions), and — since the exchange itself is hosted in Asia — network round-trip is dominated by distance from there.
2. **Fair value & volatility engine** — maintains a rolling mid/impact-mid estimate and a realized-volatility estimate (e.g. EWMA of squared returns) from the live feed. This is the `σ` input to the model below.
3. **Quoting engine** — the Avellaneda–Stoikov (2008) model the article correctly cites: reservation price `r = s − q·γ·σ²·(T−t)` and optimal half-spread `δ = γ·σ²·(T−t) + (2/γ)·ln(1+γ/κ)`, where `q` is current inventory, `γ` risk aversion, and `κ` the order-arrival-rate parameter estimated from recent trade flow. Standard, public, well-understood math — the plan is to implement it directly, not through a bot interpreting natural-language parameter changes.
4. **Risk manager** — inventory bands, drawdown kill-switch, and the dead-man's-switch/watchdog (Section 4). This is the one place a hard rule beats a clever one.
5. **Order execution & reconciliation** — places/cancels/modifies orders, handles every rejection reason Arcus can return, and continuously reconciles the account's actual reported position/fills against the engine's internal book.

All five run as one deterministic pipeline against Arcus, with the loop closing as fills and book changes flow back into the market-data layer. (See the diagram above.)

---

## 4. Risk management

### 4.1 Kill-switches don't live on the exchange alone

Arcus's take-profit/stop-loss orders are **reduce-only, dormant trigger orders** — they sit inert until a trigger condition fires server-side. That's a normal, sound mechanism, but it is inherently conditional, and Arcus's own API surfaces the failure mode directly as a named rejection reason (`REDUCE_ONLY_WOULD_INCREASE` — a reduce-only order rejected because filling it would have opened or grown the position instead of shrinking it). Dormant/conditional trigger orders on *any* venue are a backstop, not a primary control, for exactly this reason.

**Design rule:** the risk manager polls actual position and equity state directly (REST or the account-scoped WebSocket channels — both are public reads, no auth needed) on a short interval, and issues its own immediate reduce-only IOC order the moment a threshold is breached, rather than waiting on a passive TP/SL leg to fire. The exchange-native TP/SL can still be placed as a second layer, but the active poll-and-act loop is the one the system actually depends on.

### 4.2 No cancel-on-disconnect — build the watchdog

Arcus states this explicitly: dropping a WebSocket connection tears down your *subscriptions* but does **not** cancel resting orders. An order rests until filled, explicitly cancelled, or its `goodTilTime` expires — and `goodTilTime` must be set at least ~1 month out, on every order type including IOC/FOK. If the bot process dies mid-session, its quotes simply sit on the book, unattended, for up to a month.

**Design rule:** a separate watchdog process (ideally on different infrastructure than the main engine) heartbeats the main process and calls `cancelAllOrders` the moment it stops hearing from it. This is not optional hardening — Arcus's docs say outright that building this yourself is the only way to get it.

### 4.3 Order-rejection handling

Arcus's rejection taxonomy is extensive (`POST_ONLY_WOULD_CROSS`, `UNDERCOLLATERALIZED`, `SELF_TRADE`, `OPEN_INTEREST_CAP_EXCEEDED`, `FILL_WILL_EXCEED_TRADING_BOUND`, `POSITION_SIZE_CAP_EXCEEDED`, and about a dozen more, all documented on the order endpoints). The execution layer needs an explicit handler per reason, not a catch-all retry. Two worth calling out specifically:

- `POST_ONLY_WOULD_CROSS` on an ALO quote is a live signal that the pricing engine is already stale relative to the book — treat repeated occurrences as a trigger to widen or pause, not just a rejected order to resubmit.
- `REDUCE_ONLY_WOULD_INCREASE` (4.1) should page/alert immediately — it means the risk manager's view of current inventory has drifted from the exchange's.

### 4.4 Margin mode and leverage

Set **isolated margin** for the chosen market before ever opening a position — switching from cross to isolated is rejected (`HAS_OPEN_POSITION`) once a position is open, so this is a one-time setup step, not something to fix later. Isolated mode walls the position's collateral off from the rest of the account; a loss on this strategy cannot pull down other funds. Leverage should be sized conservatively relative to the market's maximum (up to 50x is available per-market, but a market maker's goal is capturing spread inside a tight inventory band, not directional leverage — high leverage mainly buys capital efficiency at scale, which isn't the priority at $5,200).

### 4.5 Funding cost is a real P&L line, not a rounding error

Crypto perps on Arcus charge funding hourly, base rate 0.01%/8h (~10.95%/year annualized) plus a premium term tied to how far the perp trades from oracle. Even a strategy with near-zero *average* inventory will pay/receive funding on whatever skew exists at each hourly mark. **The backtester must model this explicitly**, using the documented formula, not treat spread capture as the only P&L source.

### 4.6 The order/cancel-pool budget is a real constraint, and it's worth doing the arithmetic once

Order writes are free on Arcus's per-IP weight limit, but they draw from a separate **per-subaccount pool**: 20,000 starting capacity for `placeOrder`/`modifyOrder`, 40,000 for `cancelOrder`. Once a pool is exhausted, requests drip through at **1 action per 10 seconds** — which would be crippling for a market maker mid-session. The pool refills with trading volume ($0.10 of realized notional buys 1 unit of headroom on each pool), but a small, low-volume account starts out with only the base allowance.

Worked example: quoting both sides with a naive fixed 2-second cancel+replace cycle costs roughly 1 place + 1 cancel per side every 2 seconds → sustained ~1 place/sec and ~1 cancel/sec. At that rate the 20,000-unit order pool is gone in **~5.6 hours**, and the 40,000-unit cancel pool in **~11 hours** — both well inside a single trading day, before any meaningful volume has been built to refill them.

**Design rule:** requote on an event-driven basis (mid moves beyond a tick threshold, inventory crosses a band edge, volatility estimate shifts materially) rather than a fixed timer, and prefer `modifyOrder` over cancel+replace when the price is unchanged and size is equal-or-smaller (this keeps queue priority *and* only draws from the order pool, not both pools). Track `GET /v1/rateLimit` continuously and treat approaching either cap as a signal to slow down, the same way the exchange's own docs recommend.

### 4.7 Capital containment while multiple projects share one Arcus account

If this strategy ever runs on the same Arcus account as anything else, isolated margin (4.4) plus a hard-coded position-notional cap for this market are what keep a bad day in this strategy from touching the rest of the account.

---

## 5. Capital allocation framework ($5,200 ceiling)

This section is a *framework* for when live capital is eventually considered — nothing in Sections 6–7 requires it.

- **Isolated allocation, not the whole balance.** Move a deliberate subset of the $5,200 into the isolated margin leg for the chosen market; hold the rest back as an un-deployed reserve, reviewed manually before any top-up. A reasonable starting split is roughly 70–80% deployed / 20–30% held back, but the right number depends on the chosen asset's realized volatility, which is exactly what Phase 0/1 below will produce — treat the split as a Phase-1 output, not a number to fix in advance.
- **Leverage as a position-sizing tool, not a return multiplier.** Choose isolated-margin allocation and target inventory band together so that a defined adverse move (calibrated from the asset's own realized volatility, once known) doesn't threaten maintenance margin. Keep effective leverage well under the market's maximum.
- **Drawdown kill-switch band.** A starting default in the 8–15% range of the isolated allocation is a reasonable circuit-breaker to backtest against and tune — analogous in spirit to the article's own 5% rule, but this is explicitly a starting point for Phase 1 calibration, not a derived optimum.
- **Funding and fees are drawn from the same allocation**, not tracked separately — the backtest P&L (4.5, Section 7) should already net them in.

---

## 6. Phase 0 — Asset research & screening methodology

**Goal:** across Arcus's full perpetuals universe, produce a ranked shortlist and select one asset, with an explicit, data-backed reason to avoid every asset that's rejected.

### 6.1 First pass — one call, whole universe

`GET /v1/markets` returns every market in one response: symbol, `status`, `category` (CRYPTO / EQUITIES / COMMODITIES / INDICES / FOREX), `type` (filter to `PERPETUAL` — see Section 2), tick/step size, `minOrderNotional`/`minOrderSize`/`maxOrderSize`, `regularTradingHours` (null = 24/7), 24h volume/notional/high/low/trade count, open interest and its cap, funding rate, and initial/maintenance/off-hours margin fractions. This is a ready-made screening table — start here before pulling anything deeper.

### 6.2 Screening criteria, by category

**Liquidity & size fit (relative to $5,200)**

| Signal | What to check |
|---|---|
| `volume24hNotional` | Enough that the bot's own quotes wouldn't dominate the book |
| `minOrderNotional` / `minOrderSize` | Reject if the minimum lot alone consumes an outsized share of allocated capital |
| L2 depth at top levels | Sampled via `GET /v1/l2OrderBook/{market}` — enough resting size that the bot isn't the only liquidity, but not so deep that a small order never gets queue priority |

**Volatility & spread economics**

| Signal | What to check |
|---|---|
| Realized volatility | From `GET /v1/candles` returns (note: candle OHLC is oracle-price-derived, not trade-derived — fine for volatility, not a substitute for actual book spread) |
| Observed spread | `GET /v1/l2OrderBook`/`bbo`, sampled repeatedly across the screening window (there's no retroactive spread-history endpoint, so build one by polling) |
| Funding rate stability | Erratic or persistently one-sided funding bleeds directional cost into a nominally flat inventory |

**Market structure fit**

| Signal | What to check |
|---|---|
| `category` | Prefer **CRYPTO** first — `regularTradingHours` is null, meaning no off-hours regime at all (constant margin, live funding, no price bands to reason about). EQUITIES/COMMODITIES/INDICES add a real second state machine (4.4-style session-boundary handling) — a plausible Phase-2 expansion once the crypto build is proven, not a v1 target |
| `status` | Filter out anything not actively tradable |
| Tick/step size | Sane granularity relative to price — avoid distorting spread capture |
| Maker concentration | `GET /v1/trades` includes maker *and* taker address per fill — a quick pass over recent trades shows whether a handful of addresses already dominate resting liquidity (established competition) or it's fragmented (more room) |

**Risk & margin parameters**

| Signal | What to check |
|---|---|
| `maintenanceMarginFraction` / `initialMarginFraction` | Higher required margin is the exchange's own risk signal for that market |
| Max leverage offered | Arcus's own docs note lower max leverage tracks higher volatility / lower liquidity — a useful cross-check against the volatility read above |
| `openInterestCap` headroom | Avoid a market already near its cap, which can restrict the ability to build or exit inventory |

### 6.3 Output of Phase 0

A ranked shortlist with the criteria above scored per candidate, and a single selected asset with the rejected alternatives' specific disqualifying reasons recorded (not just "seemed less good") — this record is what Phase 1's backtest gets pointed at, and what justifies *not* re-testing the rejected assets later.

---

## 7. Phase 1–2 — Backtesting & forward-testing

### 7.1 A data-availability constraint that shapes the whole plan

Arcus exposes **retroactive** history for candles and trade tape, but the L2 order-book endpoint only returns the **current** snapshot — there's no "book as of time X in the past" endpoint. Realistic fill/queue simulation needs book depth, so:

- **Phase 0's screening data** (candles + trades, both genuinely retroactive) is enough for the coarse ranking in Section 6.
- **High-fidelity backtesting on the single selected asset** requires the build agent to start **logging forward** — continuously recording `l2OrderbookUpdates`, `trades`, `bbo`, and funding via WebSocket from the moment Phase 0 concludes, to build a proprietary historical order-book dataset. There's no way around this; it isn't retroactively purchasable from the API.

### 7.2 Backtest tiers

1. **Coarse (Phase 0, all candidates):** candle-volatility + trade-tape-derived volume/fill-count statistics, used only to rank and filter — optimistic by construction (assumes fills whenever the trade tape crosses a hypothetical quote level, ignoring queue position), so treat it as directional, not a P&L estimate to trust.
2. **High-fidelity (Phase 1, selected asset only):** event-driven replay against the logged L2 book, modeling FIFO queue position at each price level, simulating `POST_ONLY_WOULD_CROSS` rejections when a hypothetical ALO quote would have crossed, and valuing inventory at **mark price** (the documented blend of oracle + impact-mid, not naive mid) to mirror how Arcus actually computes margin and PnL. Apply the live fee schedule from `GET /v1/feetiers` (rates aren't published in the docs and shift with volume tier — always read them live) and the funding formula from 4.5.
3. **Forward/paper test (Phase 2):** the real (non-AI-agent) engine, running against Arcus **testnet** in real time. Testnet has an open-mint USDG faucet (~$1,000 instantly via the web app's "Testnet Deposit" button, or programmatically via `mint → approve → initiateDeposit` for a test harness) — genuinely free, unlimited test capital, which is exactly the "credentials but no funded money" situation described. Run this for a meaningful observation window before any live-capital conversation happens.

### 7.3 Metrics to track (all three tiers, where applicable)

| Category | Metrics |
|---|---|
| Profitability | Net PnL (spread captured − fees − net funding − realized adverse-selection loss), realized spread vs. quoted spread (the gap between these two is the adverse-selection signature) |
| Risk | Max drawdown, time-in-inventory-band %, count and severity of kill-switch triggers |
| Operational efficiency | Fill rate, requote/order-action count against the pool budget in 4.6, average holding time / inventory turnover |

A viable result for this phase is **break-even to modestly profitable net of all costs, with drawdown staying inside the band from Section 5** — not a headline return number. The point of Phase 1–2 is to find out whether the mechanics hold together, not to optimize for return yet.

---

## 8. Roadmap

| Phase | What happens | Capital needed |
|---|---|---|
| 0 — Screen | Pull `GET /v1/markets`, rank candidates against Section 6, select one asset | $0 (public data) |
| 1 — Backtest | Start forward-logging the book; run coarse then high-fidelity backtests per Section 7.2 | $0 |
| 2 — Forward test | Deploy the real engine on Arcus testnet | $0 (testnet faucet) |
| 3 — Live (out of scope here) | Only after 1–2 clear their bars; sizing per Section 5 | Up to $5,200 |

---

## 9. Handoff notes for the build/research agent

- Scope is **Arcus Perpetuals**, one market, chosen via Section 6 — not spot, not multi-asset, not the AI-agent architecture from the source article.
- Build the watchdog/dead-man's-switch (4.2) and the active poll-based risk loop (4.1) before anything else — these are the two controls Arcus's own docs flag as the client's responsibility, not the exchange's.
- Read fees (`GET /v1/feetiers`) and market parameters (`GET /v1/markets`) live at runtime rather than hardcoding anything from this document — both are explicitly documented as subject to change, and testnet has been shipping near-daily updates.
- All account-scoped reads (positions, fills, orders) are public and unauthenticated on Arcus — only writes need a signed request. Useful for monitoring tooling, but note it also means this account's activity is publicly observable by address.
- A monitoring/dashboard surface isn't needed for Phases 0–2, but if one gets built, extending the existing `propr-tracker` trading-terminal codebase is a shorter path than starting a new one.
- Arcus documents first-party Claude Code and MCP integration (`/ai-tools/claude-code`, `/ai-tools/mcp`) for the build tooling itself — worth using for the implementation work this plan hands off to.

# Arcus MM — Source-Audited Follow-Up Engineering & Quant Research Prompt

## ROLE

You are the next quantitative research + trading-systems engineering agent working inside the `arcus-mm` repository.

You have access to the complete repository source tree, tests, research specifications, reports, and historical smoke-test artifacts.

Your task is to continue the project from the **actual current source state**, not from the claims made by previous reports.

The central research question remains:

> Can a deterministic passive market-making strategy on Arcus perpetuals produce robust positive net expectancy at approximately **$50–$100** of experimental capital after realistic fills, queue position, rate-limit budget, fees, funding, inventory effects, latency, discrete tick/step constraints, venue mechanics, and adverse selection?

The current empirical answer is:

```text
INCONCLUSIVE
NO STRATEGY VALIDATED
NO LIVE CAPITAL AUTHORIZED
NO MAINNET ORDERS ALLOWED
```

Do not change that status until the pre-registered gates are genuinely satisfied.

---

# 1. IMPORTANT: THE PREVIOUS REPORT IS ONLY PARTLY TRUSTWORTHY

The repository's current `reports/final_research_report.md` is correct to withdraw the old 20-second smoke-test profitability and deployment claims.

However, do NOT inherit its stronger engineering statements such as:

```text
"complete deterministic research and trading scaffold"
"resolved & tested"
"replay parity"
"rate-limit sustainability"
"calibrated"
"validated"
```

without checking the actual source implementation.

The source audit has identified material gaps that must be fixed before any new profitability result can be considered meaningful.

The strongest current evidence is:

- the old smoke-test conclusions are withdrawn;
- the deterministic unit-test suite has 30 passing tests;
- several local invariants are tested;
- mainnet REST order submission is hard-blocked;
- live paper trading uses public mainnet data only;
- the current multi-day recorder exists;
- empirical strategy viability is still unproven.

The following sections define the source-level corrections that now take priority.

---

# 2. ABSOLUTE SAFETY RULES

## 2.1 Mainnet

NEVER submit mutating orders to Arcus mainnet.

No:

```text
placeOrder
modifyOrder
cancelOrder
cancelAllOrders
scheduleCancel
batch order mutation
```

may be sent to mainnet by this project.

Mainnet is for:

```text
public market-data collection
read-only research
paper execution
latency/data observation
```

Only testnet may be used for future execution probes, and only after the explicit testnet gate.

## 2.2 Credentials

Use only a dedicated testnet trade-only credential for approved testnet probes.

Never use:

- a withdrawal-capable credential;
- the user's main wallet signing key when avoidable;
- a production credential for experiments;
- credentials embedded in source, logs, reports, notebooks, fixtures, or commits.

## 2.3 Human gates

Never automatically advance from research to testnet or from testnet to live.

Required gates:

```text
G1 — Source / venue / safety integrity
G2 — Data integrity and sufficient representative data
G3 — Backtest validity
G4 — Paper-trading validity
G5 — Testnet execution validation
G6 — Live-capital consideration
```

At the end of each gate:

1. write an evidence report;
2. stop;
3. do not execute the next higher-risk phase without explicit approval.

## 2.4 Market conduct

Do not implement or test:

```text
spoofing
layering
wash trading
self-trading
quote stuffing
cross-account manipulation
venue-rule evasion
geo-restriction bypasses
```

---

# 3. FIRST TASK — COMPLETE SOURCE-TRUTH AUDIT

Before changing the quantitative model, inspect the actual files.

At minimum audit:

```text
src/config.py
src/rest_client.py
src/ws_client.py
src/auth.py

src/recorder.py
src/normalizer.py
src/orderbook.py

src/models/fill.py
src/models/rate_limit.py
src/models/latency.py
src/models/pnl.py

src/backtester.py
src/paper_trader.py

src/strategies/base.py
src/strategies/fixed_spread.py
src/strategies/avellaneda_stoikov.py
src/strategies/volatility_clock.py
src/strategies/adaptive_mm.py

src/walk_forward.py
src/adverse_selection.py

scripts/run_backtest_matrix.py
scripts/run_phase_14_backtest.py
scripts/run_walk_forward.py
scripts/run_paper_trader.py
scripts/test_replay_parity.py
scripts/verify_report.py

tests/

configs/venue_verified.yaml

research/
reports/
```

Create:

```text
reports/source_truth_audit.md
reports/source_truth_matrix.csv
```

Every important claim must be classified as one of:

```text
SOURCE_VERIFIED
TEST_VERIFIED
DATA_VERIFIED
VENUE_VERIFIED
SIMULATOR_ONLY
DOCS_ONLY
REPORT_ONLY
HYPOTHESIS
BROKEN
UNIMPLEMENTED
```

Never call a simulator-only behavior venue-verified.

---

# 4. P0 BLOCKERS THAT MUST BE FIXED

The following are blockers. Do not run a new formal backtest until they are addressed.

## P0-1 — BACKTESTER/P&L API MISMATCH

The current backtester calls `PnlAttributionEngine.record_fill(...)` with:

```text
adverse_selection_bps=1.0
```

but the current `record_fill` function does not accept that parameter.

Fix this inconsistency.

Then add an execution test that actually instantiates and runs `ArcusEventBacktester`.

A unit test suite passing while the core backtester cannot execute is not acceptable.

Required test:

```text
test_backtester_minimal_end_to_end_run
```

---

## P0-2 — WALK-FORWARD IMPORT / EXECUTION VALIDITY

Audit `src/walk_forward.py`.

The current implementation uses `Optional[...]` without importing `Optional`.

Fix all runtime/import errors.

Then actually execute:

```bash
python scripts/run_walk_forward.py
```

against a small synthetic fixture.

Do not merely compile the file.

Add:

```text
test_walk_forward_cli_smoke
```

---

## P0-3 — PAPER TELEMETRY API MISMATCH

The current paper trader calls:

```text
self.rate_limiter.get_pool_status()
```

but the current `ArcusRateLimitSimulator` does not expose that method.

Fix the interface.

Then run a paper session long enough for the telemetry loop to execute.

Required test:

```text
test_paper_telemetry_after_60_seconds_equivalent
```

Use a deterministic test clock if necessary; do not require a real 60-second CI delay.

---

# 5. P0 — RATE-LIMIT MODEL MUST BE CORRECT

The rate-limit model is an economic constraint, not an observability statistic.

The project must distinguish:

```text
initial order pool
initial cancel pool
order placement cost
modify cost
cancel cost
cancelAll cost
fill replenishment
exhausted-pool drip
```

Do not assume the previous simulator implementation is correct.

## 5.1 Placement vs modify

A first quote placement is NOT a modification.

The current backtester/paper trader uses:

```text
can_modify_order()
record_order_modification()
```

to create the initial simulated quote.

Fix this.

Model separately:

```text
PLACE
MODIFY
CANCEL
CANCEL_ALL
```

Use current Arcus documentation/venue evidence to assign the actual unit cost.

The current research correction says:

> A modify consumes an order unit, while cancelAll has a distinct cancel-pool cost.

Verify the current venue rule before freezing it.

## 5.2 Queue priority

Model:

```text
same-price size decrease
    -> preserves queue priority

price change
    -> loses priority

size increase
    -> loses priority
```

Do not charge a cancel unit merely because the conceptual modification is implemented internally as cancel+replace unless the venue's actual rate-limit accounting does so.

## 5.3 Replenishment

Implement current venue replenishment behavior explicitly.

Do not confuse:

```text
pool capacity
```

with:

```text
currently available headroom
```

The simulator and client-side limiter must use the same accounting semantics.

## 5.4 Drip behavior

The current simulator does not implement a genuine time-based exhausted-pool drip.

Implement and test the actual rule:

```text
when depleted
-> at most 1 eligible action per configured drip interval
```

with exact venue semantics.

## 5.5 cancelAll

Model the actual cost of `cancelAllOrders`.

Do not let:

```text
risk kill switch
stale feed
reconnect
```

magically clear simulated orders at zero economic/action cost.

---

# 6. P0 — BACKTESTER ORDER LIFECYCLE IS NOT REALISTIC ENOUGH

The current backtester creates a new `active_bid_order` / `active_ask_order` when a quote changes, but it does not properly model:

```text
old quote cancellation
cancel latency
cancel acknowledgement
replacement
period in which old quote may remain live
action cost
queue-priority consequences
```

Overwriting a Python object is not equivalent to canceling an exchange order.

Implement an explicit order state machine:

```text
CREATED
SUBMITTING
RESTING
PARTIALLY_FILLED
FILLED
CANCEL_REQUESTED
CANCELLED
REPLACE_REQUESTED
EXPIRED
REJECTED
```

For a price change:

```text
existing order
-> cancel / replace semantics
-> queue priority reset
-> new order enters queue after latency
```

For same-price size decrease:

```text
modify in place
-> preserve priority
```

where venue rules establish that behavior.

---

# 7. P0 — THE BACKTESTER MUST USE L2, NOT JUST BBO + TRADES

The current `ArcusEventBacktester` only accepts:

```text
df_bbo
df_trades
funding_data
```

It does not actually replay the high-fidelity L2 stream.

That means the current "queue-aware FIFO" model is not genuinely reconstructing queue state from Arcus L2.

Build:

```text
Historical event stream
    |
    +-- L2 snapshot
    +-- L2 deltas
    +-- BBO
    +-- trades
    +-- oracle
    +-- mark
    +-- funding
    +-- market metadata
    |
    v
Local book replay
```

Then:

```text
strategy
-> quote
-> venue-validity check
-> queue placement
-> fills
-> inventory
-> PnL
```

The queue model must use actual historical book-depth events where available.

BBO-only mode may remain as:

```text
LOW_FIDELITY_RESEARCH
```

but it must never be called the high-fidelity MM backtest.

---

# 8. P0 — STOP SYNTHETIC BBO FROM ENTERING ANY FORMAL MM BACKTEST

The old candle-synthesis path must remain quarantined.

Do not construct:

```text
synthetic BBO
synthetic spread
synthetic queue
```

from candles for any formal MM PnL claim.

Candle data can be used for:

```text
coarse volatility characterization
```

but not:

```text
realistic passive fill PnL
queue research
adverse selection inference
formal deployment validation
```

---

# 9. P0 — PHASE 14 IS CURRENTLY A COVERAGE REPORT, NOT A BACKTEST

`run_phase_14_backtest.py` currently estimates:

```text
simulated fills = 2% × trade count
```

Do not use this.

This is an arbitrary fill-rate placeholder, not a simulation.

Replace Phase 14 with the actual deterministic replay pipeline.

The final Phase 14 report must be based on actual simulated fills, not:

```python
int(trades_count * 0.02)
```

The output must clearly distinguish:

```text
DATA COVERAGE REPORT
```

from:

```text
FORMAL BACKTEST REPORT
```

---

# 10. P0 — PER-MARKET EXECUTABLE CLIP MUST BE REAL

The current strategies default to approximately:

```text
clip_notional = $8
```

across markets.

That is invalid for markets whose actual minimum executable clip is larger, such as:

```text
BTC
ZEC
HYPE
other markets where minOrderSize × price > minOrderNotional
```

Do not hard-code a universal clip.

At runtime, derive:

```text
min_executable_clip =
max(minOrderNotional,
    minOrderSize × relevant reference price)
```

Then snap quantity exactly to the venue's step size.

Reject quotes that remain below the live minimum.

Run all core strategies at:

```text
$50
$100
```

using actual per-market constraints.

---

# 11. P0 — EXACT INTEGER QUANTIZATION

Do not rely on:

```python
round(price / tick)
round(size / step)
```

using floats for canonical venue math.

Represent:

```text
price ticks
quantity steps
notional
```

exactly using integer/Decimal arithmetic.

The backtest and execution engine must use the same quantization path.

Test:

```text
BTC tick 0.1
BTC step 1e-8
HYPE tick 0.001
ZEC tick 0.001
```

and every candidate's exact live metadata.

---

# 12. P0 — FUNDING IS CURRENTLY MODELED INCORRECTLY

The current backtester reads one funding rate and applies it once at the end of the simulation.

Do not do this for the formal research.

Build a time-aware funding engine.

It must model:

```text
funding observations
funding timestamps
position held at funding event
actual funding settlement interval
funding sign
funding cash flow
```

Funding must be applied to the position that actually existed at the relevant settlement event.

Do not extrapolate one initial funding rate across a multi-day test.

---

# 13. P0 — FORCED FLATTENING MUST NOT FILL AT MID BY DEFAULT

The current forced flatten uses:

```text
current_mid
```

as execution price.

That is optimistic.

For formal risk/exit simulation, use the appropriate contemporaneous executable side:

```text
long -> sell against bid / modeled taker execution
short -> buy against ask / modeled taker execution
```

and include:

```text
taker fee
slippage
latency
available depth
```

at the selected fidelity.

Do not credit zero slippage simply because the kill switch triggered.

---

# 14. P0 — ADVERSE SELECTION MUST BE FUTURE MARKOUT, NOT FILL-TO-MID

The current PnL engine stores an `adverse_selection_cost` based on the fill price relative to the contemporaneous mid.

That is not the same thing as adverse selection.

Formal adverse selection should be based on:

```text
fill at t
-> reference price at t + horizon
```

using:

```text
100ms
500ms
1s
5s
10s
30s
60s
```

where resolvable.

Drop unresolvable horizons.

Report:

```text
N
mean
median
quantiles
confidence interval
```

separately for:

```text
bid fills
ask fills
```

and by market state.

Keep this research attribution separate from the accounting identity.

---

# 15. P0 — PNL ATTRIBUTION NEEDS TO BE REDEFINED

Do not claim five-way attribution is exact unless the components are mutually coherent and sum to equity change.

Use an explicit decomposition such as:

```text
gross realized trading PnL
+ inventory MTM
+ funding
- maker fees
- taker fees
- execution/slippage cost
= net PnL
```

Then derive:

```text
quoted spread capture
adverse selection / markout
```

as research diagnostics unless they are explicitly incorporated into the accounting ledger without double counting.

The current contemporaneous fill-to-mid "adverse selection" diagnostic should not be subtracted again if it is already embedded in inventory/equity PnL.

---

# 16. P0 — VOLATILITY IS CURRENTLY A CONSTANT IN THE CORE REPLAY

The current backtester feeds a fixed volatility value into strategies rather than calculating it dynamically from the replayed market state.

The paper engine also initializes a fixed volatility value.

That means the current:

```text
VolatilityClock
A-S
AdaptiveMM
```

results do not yet represent genuinely adaptive volatility behavior.

Implement a deterministic volatility estimator from historical/live BBO or mid data.

Specify:

```text
return horizon
sampling frequency
EWMA window
annualization convention
missing-data handling
outlier/jump handling
```

Then store the feature in the replay event state.

---

# 17. P0 — AVELLANEDA–STOIKES MUST BE DIMENSIONALLY CORRECT

The current strategy claims to use corrected A-S, but still contains hard-coded:

```text
gamma = 0.05
kappa = 1.5
H = 0.5 hours
```

and performs ad-hoc scaling.

Do not treat this as calibrated A-S.

Implement one clearly documented convention.

For example:

```text
reservation price:
r = s - q * gamma * sigma^2 * T

total spread:
delta =
gamma * sigma^2 * T
+
(2/gamma) * ln(1 + gamma/kappa)

bid = r - delta/2
ask = r + delta/2
```

Define units consistently.

If:

```text
sigma = annualized volatility
```

then:

```text
T = years
```

If:

```text
sigma = hourly volatility
```

then:

```text
T = hours
```

Do not mix annualized sigma with hour-valued T.

## 17.1 Kappa

Do not use `kappa=1.5` merely because it produces quotes.

Fit or estimate empirical order-arrival intensity from observed data.

Document:

```text
distance definition
arrival event definition
observation window
censoring
fit method
sample count
confidence interval
stability
```

If empirical calibration is not possible:

```text
A-S NOT CALIBRATED
```

---

# 18. P0 — WALK-FORWARD PROTOCOL IS NOT IMPLEMENTED AS REGISTERED

The pre-registration specifies:

```text
tuning week
parameter freeze
five-day OOS
one-shot evaluation
```

The current `WalkForwardValidator` uses a generic 60/40 timestamp split.

Replace that with the actual committed protocol.

Required chronology:

```text
Tuning:
2026-09-21 through 2026-09-25

Freeze:
2026-09-26 12:00 UTC

OOS:
2026-09-28 through 2026-10-02
```

No random k-fold.

No OOS retuning.

No parameter updates after freeze.

---

# 19. P0 — MULTIPLE-TESTING CONTROL IS CURRENTLY ONLY DECORATIVE

The repository contains a Holm-Bonferroni helper, but the current walk-forward execution does not provide a full p-value pipeline and does not actually apply the correction to formal strategy-selection results.

Do not claim:

```text
Holm-Bonferroni controlled
```

until:

1. the hypothesis family is defined;
2. all tested market × strategy × parameter configurations are registered;
3. p-values or an equivalent formal inferential framework are computed;
4. the correction is applied to the complete pre-declared family;
5. the corrected result is stored in the report.

For practical go/no-go research, also make the out-of-sample result primary rather than relying on significance language alone.

---

# 20. P0 — REQUIRED CONTROLS ARE MISSING FROM FORMAL VALIDATION

The pre-registration requires comparison against:

```text
do-nothing baseline
random-side quoting baseline
```

Implement these controls.

Do not claim "beats baseline" without running them on the same event set, capital, latency, fee, fill, and risk assumptions.

---

# 21. P0 — NUMERIC SUCCESS CRITERIA MUST ACTUALLY BE COMPUTED

The current pre-registration requires, where applicable:

```text
N >= 300 / 100 fills
mean net bps/fill > 0
90% CI lower bound > 0
positive >= 3 / 5 OOS days
max single-day concentration <= 50%
max intraday drawdown < 10%
zero inventory-limit breaches
beats controls
Model B materially differs from Model A
$50 and $100 evaluation
```

Implement all of these as machine-checkable gates.

Do not replace them with:

```text
PnL > 0
```

or:

```text
fills >= 30
```

or:

```text
stress PnL > -$0.50
```

unless the pre-registration itself has been formally amended before the OOS run.

---

# 22. P0 — PHASE 15 VERDICT LOGIC MUST NOT SAY "VALIDATED" FROM POSITIVE PNL

The current paper report logic effectively does:

```text
fills < 30
    -> insufficient

else pnl > 0
    -> validated
```

This is not the registered validation standard.

Change it.

Paper trading must be labeled:

```text
PAPER OBSERVATION
```

or:

```text
INSUFFICIENT DATA
```

and never `VALIDATED` merely because a live paper run made money.

---

# 23. P0 — REPLAY PARITY IS NOT ACTUAL PARITY YET

The current parity script claims to compare:

```text
fills
positions
equity curves
```

but the implementation primarily compares a fill-count field and currently expects a telemetry key that does not correspond to the telemetry structure.

Fix parity to compare:

```text
event-by-event quote actions
fill sequence
fill side
fill price
fill quantity
inventory path
fees
funding
equity path
risk/kill events
final state
```

Use identical:

```text
raw event stream
strategy version
parameters
latency seed/path
fill model
initial capital
```

Parity should fail on any material mismatch.

---

# 24. P0 — RECORDER SEQUENCE GAPS MUST INVALIDATE THE BOOK

The recorder currently detects mid-stream sequence gaps but continues recording subsequent data instead of forcing a book invalidation/resync state.

Change behavior:

```text
gap detected
-> mark stream/book invalid
-> stop treating subsequent deltas as trusted for continuous replay
-> resync from a fresh snapshot
-> record gap interval
-> resume only after valid synchronization
```

For research storage, retain the raw frames.

For normalized high-fidelity replay, mark the interval:

```text
INVALID_BOOK_INTERVAL
```

so no quote/fill simulation crosses it silently.

---

# 25. P0 — TRADE DEDUPLICATION MUST COVER THE ENTIRE FRAME

The recorder's current trade dedup logic can use the first trade's identifier from a trade frame.

Do not assume that deduplicates every trade in a multi-trade frame.

Deduplicate every trade event by the strongest available identifier.

Store:

```text
trade_id
sequence_number
recv_ts_ns
```

and retain provenance.

---

# 26. P0 — MAINNET WEBSOCKET ORDER-WRITE SAFETY

The REST client has a mainnet order lock.

The WebSocket `rpc_post` path is also capable of authenticated trading RPCs.

Do not assume the REST lock protects the WebSocket path.

Add the same hard mainnet mutation gate to:

```text
WS order placement
WS modify
WS cancel
WS cancelAll
WS scheduleCancel
```

Required negative tests:

```text
test_ws_mainnet_order_lock
test_ws_mainnet_cancel_lock
test_ws_mainnet_modify_lock
```

---

# 27. P0 — WATCHDOG / DEAD-MAN'S SWITCH

The design calls for a watchdog/dead-man mechanism, but the current system does not yet provide a complete independent watchdog that protects resting orders if the main process dies.

Implement and test:

```text
main engine heartbeat
watchdog
venue-side scheduleCancel where appropriate
recovery/reconciliation
```

Test:

```text
process dies
network stalls
heartbeat stops
watchdog fires
expected order cleanup occurs
```

Keep this separate from the strategy's AI/research layer.

---

# 28. RESEARCH STRATEGY ORDER

After P0 engineering correctness is complete, use this order.

## Backbone

### S0 — Fixed symmetric spread

```text
bid = reference - spread/2
ask = reference + spread/2
```

No skew.

This is the raw economic control.

If it cannot approach or clear realistic breakeven, document that before adding complexity.

### S1 — Avellaneda–Stoikov

Only after unit consistency and empirical kappa calibration are correct.

### S2 — Volatility-clock

```text
spread ∝ k * sigma
```

using a real volatility estimator.

Compare S1 vs S2 rather than assuming A-S must win.

---

# 29. OVERLAYS

Only after S0–S2 have valid results:

## O1 — Microprice / order-book imbalance

Test:

```text
reference-price skew
quote asymmetry
toxicity reduction
```

Do not assume the current `AdaptiveMicrostructureStrategy` is correct merely because it exists.

Measure:

```text
fill probability
adverse selection
inventory directional risk
net expectancy
```

## O2 — Requote threshold + queue discipline

Test:

```text
0 tick
1 tick
2 tick
3 tick
5 tick
```

only if pre-registered and computationally feasible.

Primary metric:

```text
incremental net edge per action-unit consumed
```

not trade count.

## O3 — IST heavy/light/no-trade schedule

Reuse the existing user's session segmentation if present.

Map:

```text
heavy
light
no-trade
```

to:

```text
normal quotes
reduced/wider quotes
flat
```

and report incremental contribution.

## O4 — News defensive kill

Use the existing Telegram/news extractor only as a defensive risk overlay:

```text
event detected
-> widen/pull
-> optionally arm dead-man switch
```

It is not alpha until demonstrated.

---

# 30. SEPARATE CARRY FROM MARKET MAKING

Funding tilt must be reported separately.

Produce:

```text
MM-only PnL
Funding PnL
Combined PnL
```

Do not allow positive funding to hide a negative quoting edge.

---

# 31. SEPARATE EXTERNAL LEAD-LAG FROM LOCAL MM

If a deeper external venue is used:

```text
local MM edge
+
external-reference edge
```

must be decomposed.

Model:

```text
reference latency
staleness
disconnect
basis
fallback
quote-pull threshold
```

If the external feed disappears:

```text
pull quotes
```

---

# 32. DATA COLLECTION PROTOCOL

Once the recorder implementation is repaired:

1. restart the recorder;
2. preserve every old dataset;
3. maintain raw immutable event storage;
4. collect at least the full registered data window;
5. verify:
   - no unexplained gaps;
   - socket rotation continuity;
   - sufficient message coverage;
   - valid L2 snapshots;
   - valid delta continuity;
   - trade continuity;
   - timestamps;
   - market metadata snapshots;
   - funding observations.

For each market report:

```text
coverage duration
event counts
trade count
BBO count
L2 count
sequence gaps
invalid intervals
reconnects
rotation count
```

Do not require every market to have identical coverage, but define minimum coverage before formal evaluation.

---

# 33. MARKET SELECTION

Do not decide that BTC, HYPE, ZEC, or any other asset is the winner before completing the objective screening.

However, do not spend high-fidelity compute on every market forever.

Use:

```text
broad low-cost screening
-> objective candidate filter
-> deep L2 recording
-> high-fidelity simulation
```

A candidate filter must consider:

```text
min executable clip
spread
depth
trade intensity
volatility
funding
adverse-selection potential
capital fit
rate-limit economics
```

---

# 34. ECONOMIC BREAK-EVEN SCREEN

Before expensive parameter search, calculate:

```text
Net Edge / Fill =
captured spread
+ maker incentive/rebate
- maker fee
- adverse selection
- inventory carrying cost
- forced-exit cost
- execution/slippage cost
- rate-limit opportunity cost
```

Then:

```text
capacity-adjusted expected daily PnL
=
net edge/fill
× achievable fills/day
```

where achievable fills are constrained by:

```text
market activity
queue position
rate-limit capacity
minimum order size
capital
risk limits
```

If the lower confidence bound is not economically positive:

```text
STOP
```

or document why further research is justified.

---

# 35. FORMAL BACKTEST ARCHITECTURE

The high-fidelity backtester must become:

```text
raw event stream
    |
    v
book reconstruction
    |
    v
feature/state engine
    |
    v
strategy
    |
    v
venue-valid quote
    |
    v
latency
    |
    v
queue placement
    |
    v
order lifecycle
    |
    v
fills
    |
    v
inventory
    |
    +--> funding
    +--> fees
    +--> slippage
    |
    v
PnL
    |
    v
risk engine
    |
    v
metrics / gate evaluator
```

No future event may enter a decision at time `t`.

---

# 36. LATENCY MODEL

Do not use a single hard-coded 60ms latency as the primary model.

Build an empirical latency dataset for:

```text
market-data receive
order submission
cancel
modify
acknowledgement
```

Store:

```text
p50
p75
p90
p95
p99
max
```

For stochastic simulation:

```text
seed
distribution
sample path
```

must be recorded per experiment.

Include a separate stress test.

Do not confuse:

```text
REST /health RTT
```

with:

```text
order placement lifecycle latency
```

---

# 37. STATISTICAL VALIDATION

For each formal strategy-market combination:

Report:

```text
N fills
net bps/fill
gross spread capture
fees
funding
adverse-selection markout
inventory PnL
max drawdown
daily PnL
quote lifetime
fill rate
action units/fill
action units/day
```

Where applicable compute:

```text
90% confidence interval
bootstrap or appropriate block-resampling method
```

Cluster by time blocks rather than pretending fills are iid.

---

# 38. NO MULTIPLE-TESTING LEAKAGE

Register every tested:

```text
market
strategy
parameter configuration
overlay
latency model
fill model
```

before formal OOS.

Do not cherry-pick the best run.

Never call a best-of-many in-sample winner an independent statistical discovery.

---

# 39. FORMAL OOS PROTOCOL

Implement exactly the registered chronology:

```text
Tune:
2026-09-21 -> 2026-09-25

Parameter freeze:
2026-09-26 12:00 UTC

Held-out weekend:
2026-09-26 -> 2026-09-27

OOS:
2026-09-28 -> 2026-10-02
```

After freeze:

```text
NO RETUNING
NO PARAMETER CHANGES
NO STRATEGY RESELECTION
```

If the dataset does not contain the required evidence:

```text
INSUFFICIENT DATA
```

---

# 40. VALIDATION GATES

A strategy-market combination can only reach:

```text
VALIDATED
```

after satisfying the registered criteria, including where applicable:

```text
N >= required threshold
mean net bps/fill > 0
90% CI lower bound > 0
positive >= 3/5 OOS days
daily concentration constraint
drawdown < 10%
zero inventory-limit breaches
beats do-nothing baseline
beats random-side baseline
Model B materially differs from A
$50 evaluation
$100 evaluation
```

Also include:

```text
rate-limit capacity gate
```

because a strategy that requires more actions than the venue budget supports is not executable.

---

# 41. PAPER TRADING

Paper trading must remain:

```text
MAINNET PUBLIC DATA
+
ZERO MAINNET MUTATIONS
```

It is an execution-reality observation layer.

Track:

```text
paper quote events
simulated fills
inventory
markouts
action budget
latency
quote lifetime
```

Do not call positive paper PnL "validated".

---

# 42. TESTNET

Only after G2/G3/G4 approval.

Use testnet to validate venue mechanics:

```text
ALO
POST_ONLY_WOULD_CROSS
SELF_TRADE
goodTilTime
place
cancel
modify
same-price size decrease
queue priority
scheduleCancel
rate-limit observations
reconciliation
```

Do not infer that testnet PnL automatically represents mainnet economics.

Use mainnet public-data paper trading for market-economic inference.

---

# 43. REPORT INTEGRITY

The current report verifier is not sufficient as a provenance system.

Strengthen it so that a formal report can only be generated from machine-produced result artifacts.

Each numeric claim must map:

```text
claim_id
experiment_id
dataset version/hash
git commit
strategy version
config hash
table row/column
```

The verifier must not merely check whether a number appears somewhere in any table.

Numbers copied from unrelated tables must fail provenance validation.

---

# 44. REQUIRED DELIVERABLES

Create/update:

```text
reports/source_truth_audit.md
reports/source_truth_matrix.csv

reports/engineering_blockers.md
reports/phase_14_data_coverage.md
reports/phase_14_backtest.md
reports/phase_15_paper_validation.md

research/rate_limit_economics.md
research/latency_model.md
research/pnl_accounting.md
research/multiple_testing.md
research/strategy_protocol.md

tests/test_backtester_execution.py
tests/test_rate_limit_semantics.py
tests/test_ws_safety.py
tests/test_recorder_integrity.py
tests/test_pnl_accounting.py
tests/test_strategy_math.py
tests/test_walk_forward_protocol.py
tests/test_report_provenance.py
```

Preserve historical smoke-test files under their archive directory.

Do not overwrite them with new data.

---

# 45. ACCEPTANCE TESTS FOR THIS FOLLOW-UP

The follow-up is NOT complete until:

```text
1. full Python test suite passes
2. backtester executes on a deterministic synthetic fixture
3. walk-forward runner executes on a deterministic fixture
4. paper telemetry executes without API mismatch
5. rate-limit simulator matches the documented semantics
6. placement and modification are distinct actions
7. drip behavior is implemented
8. funding is time-aware
9. per-market minimum executable clip is enforced
10. exact tick/step quantization is deterministic
11. A-S units are dimensionally consistent
12. kappa calibration is empirical or explicitly unavailable
13. L2 is used in high-fidelity replay
14. order lifecycle includes cancellation/replacement
15. recorder gaps trigger invalidation/resync
16. WS mainnet mutation lock is hard
17. replay parity compares the actual state path
18. validation gates are machine-enforced
19. multiple-testing accounting is real
20. no current research report claims a strategy is profitable
```

---

# 46. FINAL STOP CONDITION

After completing the source fixes, run:

```text
python3 -m unittest discover tests
```

and the new deterministic fixture suite.

Then produce:

```text
reports/followup_gate_report.md
```

with exactly one final status:

```text
BLOCKED — ENGINEERING FIXES REMAIN
```

or:

```text
READY FOR DATA ACCUMULATION
```

or:

```text
READY FOR FORMAL BACKTEST
```

Do NOT output:

```text
VALIDATED
PROFITABLE
DEPLOYMENT READY
```

at this stage unless the full pre-registered OOS protocol has actually been completed.

---

# 47. IMMEDIATE PRIORITY ORDER

Do not start with strategy optimization.

Execute in this exact order:

```text
1. Source-truth audit
2. Backtester runtime fixes
3. Rate-limit model correction
4. Order lifecycle correction
5. Funding/PnL correction
6. Per-market sizing + exact quantization
7. Dynamic volatility
8. A-S mathematical correction
9. Recorder gap/resync correction
10. WS safety lock
11. Watchdog/dead-man switch
12. Walk-forward protocol implementation
13. Report provenance/gating correction
14. Restart/finalize multi-day data recording
15. Formal S0/S1/S2 backtests
16. Microstructure overlays
17. OOS
18. Paper/testnet gates
```

The objective is not to produce the most complex market maker.

The objective is to determine, reproducibly and without optimism, whether a very small Arcus passive MM has measurable positive economics.

