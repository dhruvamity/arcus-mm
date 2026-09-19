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

