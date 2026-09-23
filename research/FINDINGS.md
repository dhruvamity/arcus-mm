# Findings — 2026-09-22

Everything below is reproducible from scripts in this repo on the recorded tape
(2026-09-19 → 2026-09-21 UTC, ~52 h, 20 markets). Three days include a weekend, so treat
every number as in-sample until the out-of-sample week in `oos_plan.md` is scored.

## 1. What the previous agents' results were worth

| Claim | Status | Why |
|---|---|---|
| 24 h crypto paper session "+$20,911 on $100" | **Invalid** | 71,846 of 75,645 fills were priced >1% away from their own market's mid: frames from ETH/SOL/etc. were processed as BTC. Final position +79 BTC on a $100 cap. |
| `farming_economics.md` cost table ("zero candidates", 35% unwind share, CIs) | **Unverified** | No script produced it; numbers were typed. Its headline for BTC/ETH turns out roughly right, for other reasons (§2). |
| A-S "calibrated" κ (V-36) | **Not a calibration** | `ln(trades/hr)/(half_spread·100)` fits nothing; inventory skew was ~0.01 bps/clip, i.e. a fixed-spread quoter. |
| Venue facts: 0 bps maker / 2.25 bps taker at base tier, ALO/cancels skip the 50 ms taker speed bump, CASHCAT funding ≈ +1.68 bps/h (≈13× others) | **Confirmed** | `configs/venue_verified.yaml`, `data/deep_history/*_funding.json`. |

## 2. Where passive liquidity makes money on Arcus (model-free)

`scripts/maker_economics.py` → `maker_economics.md`. For every real trade, the maker side's
realized spread = edge vs the mid 30 s later, notional-weighted, 95% CI from a 5-minute block
bootstrap. No fill model involved.

* **At the touch, makers lose** on almost every liquid market (rs30, bps): BTC −1.00 [−1.27, −0.75],
  ETH −1.95, HYPE −0.27, SPY −0.14, NVDA −0.11, GLD −0.15. Queue-joining at the best price is a
  losing seat at our latency; this is what every strategy in the old repo effectively tried.
* **Deeper in the book, makers earn** — fills there come from large sweeps that partially revert:
  HYPE 3–9 ticks +2.73 [1.08, 4.45], 10+ ticks +4.71 [1.67, 6.96]; NVDA 3–9 +3.31 [2.08, 4.97];
  SPY 10+ +1.89 [1.52, 2.27]; GLD 10+ +3.68 [1.84, 4.45]. BTC/ETH stay ≤ +0.7 and not significant.
* Market-level, SPY makers were positive on every day and regime (+0.58 to +0.89 bps); BTC/ETH
  negative on every day.

## 3. Can a small, slow participant capture it? (queue-aware replay)

> **Correction 2026-09-23 — the numbers in this section and §6 came from a buggy tape loader.**
> Arcus can send two *different* BBO / L2 frames under one `globalSequenceId` (e.g. "bid back"
> then "ask back" 12 µs apart). The loader de-duplicated on the id alone, kept the first and
> dropped the real final book: about a third of NVDA's BBO frames on 2026-09-23. Found because
> the live shadow run re-priced NVDA 4× more than the replay on the same window; after the fix
> they agree within 0.5% (1,334 vs 1,327 actions). Re-run on corrected data, Sep 19–22 (80 h),
> rate limits on, $2 daily stop (`deep_quote_backtest.py --markets GLD-USD,NVDA-USD,HYPE-USD,SPY-USD
> --depths 2,3,5,8 --rate-limit --stop-usd 2 --rtt 200|400 --to-day 2026-09-22`; the 200 ms run is
> `deep_quote_backtest.md`):
>
> | market, depth | PnL 200 ms | days + | PnL 400 ms | days + | daily PnL (200 ms) |
> |---|---:|---|---:|---|---|
> | **GLD 3 bps** | **+$1.26** | **4/4** | **+$1.39** | **4/4** | 0.02, 0.15, 0.31, 0.77 |
> | GLD 2 bps | +$0.62 | 4/4 | +$0.44 | 3/4 | 0.02, 0.10, 0.04, 0.46 |
> | NVDA 3 bps | +$1.21 | 2/4 | +$1.22 | 2/4 | 0.00, 0.63, 0.59, −0.02 |
> | HYPE 5 bps | −$0.62 | 2/4 | +$3.95 | 3/4 | 2.00, 1.98, −2.17, −2.43 |
> | SPY 3 bps | +$0.05 | 3/4 | +$0.06 | 3/4 | 0.05, 0.36, −0.60, 0.24 |
>
> **GLD 3 bps still holds on every day at both latencies. NVDA 3 bps is positive overall but no
> longer on every day** (Sep 22 slightly negative), and needs ~950 actions/hour — it drains the
> order budget. HYPE is unstable. The first real-money run is GLD only.

`src/replay.py` + `scripts/deep_quote_backtest.py` → `deep_quote_backtest.md`. Replays the
sequenced L2 + trade tape with price-time priority, RTT latency on every place/cancel, ALO
rejection, and conservative handling of levels outside the 50-level feed. Rule: one bid at
mid−d, one ask at mid+d, requote on ≥1 bps drift, $25 clips, ≤$100 inventory, 0 bps maker fee.

| market, depth | PnL over 52 h | days positive | rs30 of our fills | at RTT 20 / 400 ms |
|---|---:|---|---:|---|
| GLD 2 bps | +$0.87 | 3/3 | −0.6 | 3/3, 3/3 positive |
| GLD 3 bps | +$0.69 | 3/3 | −0.3 | 3/3, 3/3 positive |
| NVDA 3 bps | +$0.90 | 3/3 | +1.2 | 3/3, 3/3 positive |
| HYPE 5 bps | +$6.79 | 2/3 (3rd flat) | −2.7 | 3/3 positive, markout +4.9 at 20 ms |
| SPY 2 bps | −$0.03 | 2/3 | +0.3 | ≈ breakeven |
| ETH, any depth | −$1 to −$28 | ≤1/3 | −2 to −5 | — |

Takeaways:
1. **ETH/BTC/SOL: do not quote** at base tier and this latency. Consistent across both methods.
2. **GLD and NVDA at 2–3 bps are the only configs positive on all days at all latencies.** Small
   samples (80–110 fills), small dollars.
3. **HYPE is latency-bound**: our fills get picked off at 200 ms but mark out strongly positive at
   20 ms. A VPS near Arcus's matching engine is the cheapest real improvement available.
4. **Skewing quotes toward flat made results worse** almost everywhere (tested at 3 bps skew).
5. Capacity is small: $25 clips earn cents to a few dollars per day. As a *volume farming*
   rule, GLD/NVDA/SPY at 2–3 bps manufacture ~$1–2k/day of maker volume per market at roughly
   zero net cost — that meets the "breakeven or better" bar; it is not an income source.

## 4. Known limits of the replay

* Queue position assumes cancels ahead of us happen only when the displayed level shrinks below
  our queue estimate (never optimistic, sometimes pessimistic).
* Our orders do not affect the book or other participants.
* Funding is not charged (inventory is small and short-held; ~0.1–0.2 bps/h on these markets).
* 52 hours; one trend day (BTC +6.5% on 2026-09-21). Multiple configs were tried, so the
  best ones are biased upward — hence the frozen out-of-sample test.

## 5. Full Arcus history and Binance (added 2026-09-22)

Data: Arcus keeps public trades back to **2026-06-30** (public perps launch; no older history
exists, and no historical order book at all) — `scripts/pull_trade_history.py`. Binance
aggTrades/klines via `scripts/pull_binance.py`: HYPE since 2025-05, NVDA/SPY/QQQ since 2026-03/04,
gold (PAXG) since 2020. Candles alone cannot test this strategy (its edge lives in the 30 s after
a sweep), so trade-by-trade data is used; candles are for regimes.

**Trade-only estimate is validated** (`scripts/validate_sweep_proxy.py`): beyond the touch it
matches true-BBO results in sign everywhere and is close or conservative in size (SPY 2–5 bps:
true +2.05, estimate +1.79; BTC −0.53 vs −0.48). Not usable at the touch on thin markets or for GLD.

**Deep-fill edge across Arcus's whole history** (`scripts/sweep_history.py` → `sweep_history.md`,
weekly; history downloaded twice and cross-checked trade-by-trade with `scripts/compare_history.py`:
0 missing, 0 differing rows). Only markets where the estimate was validated against true quotes
are listed — thin markets (GLD, LIT, XRP, UNI, AAVE, CASHCAT, SLV, TSLA, GOOGL, AMD, SPCX, NEAR)
come out inflated and are excluded.

| market | 0–2 bps: weeks + | 2–5 bps: weeks + | 2–5 bps pooled | recent weeks (2–5 bps) |
|---|---|---|---:|---|
| SPY | 10/10 | 9/9 | +2.51 | still positive (+1.2 to +1.9) |
| NVDA | 10/10 | 10/10 | +5.71 | still positive (+2.8 to +4.6) |
| QQQ | 10/10 | 7/8 | +2.72 | positive |
| HYPE | 9/9 | 9/9 | +3.65 | positive (+0.3 to +3.7) |
| BTC | 10/13 | 12/13 | +1.13 | decayed to ≈0 / negative in September |
| ETH | 11/11 | 8/10 | +1.87 | mixed, ≈0 in September |
| SOL | 7/11 | 10/10 | +2.61 | small (+0.2 to +0.4), unstable |
| ZEC | 5/6 | 5/6 | +4.24 | turned sharply negative in week 39 (−5.5) |

The edge is **shrinking** as Arcus grows (SPY 2–5 bps ≈ +14 bps/fill in late July → ≈ +1.2 in
September) and has already gone for the crypto majors. At the touch, BTC/ETH/SOL makers lose in
most weeks.

**Multi-year Binance check** (`binance_sweep_history.md`, monthly): fills 2–5 bps behind the touch
were positive in 34/34 months for gold (PAXG, 2023-09 → 2026-08), 6/6 NVDA, 5/5 SPY, 5/5 QQQ, 9/9 XAU;
at the touch they lost in nearly every month for every asset. HYPE needs ≥5 bps (14/16 months) and
ZEC is negative until 10+ bps (29/36) — sweeps there are more informed. A 16-month queue-aware
replay of the rule on Binance HYPE lost at 5 bps (0/16 months) and was positive only at 15 bps
(13/16 months, +0.81 bps/fill) — `binance_replay.md`.

**On Binance's own tape the same rule loses** (HYPE: −2.2 bps/fill): Binance is where price is
discovered, so sweeps there are informed. The Arcus edge is local — Arcus sweeps revert toward
the price set elsewhere.

**Binance price sorts Arcus maker fills into winners and losers** (`scripts/fair_value_study.py`,
Sep 1–20, trailing basis only): fills priced 2–5 bps better than Binance-implied fair value won
97% (SPY), 88% (NVDA), 68% (HYPE) of the time; fills worse than fair lost 70–96%. Binance leads
Arcus by ~1–3 s.

**But a slow quoter can't harvest that** (`scripts/fair_value_backtest.py`, queue-aware replay,
Sep 19–20): with our real delays (Binance seen 150 ms late, 200 ms RTT to Arcus) every
Binance-anchored config marks out negative (rs30 −1 to −4 bps) — faster makers take the good fills
and we get picked off. With co-located delays (5 ms / 20 ms) markouts turn positive on HYPE, ETH
and BTC (+0.2 to +3.9 bps), but PnL is still mixed (ETH 1 bps +$2.11, HYPE −$1 to −$3) because
inventory drifts with the Arcus/Binance basis. Two weekend days only; stock perps need weekday
Binance data (Sep 21 publishes 2026-09-22).

## 6. Can it run from this host without bleeding? (2026-09-22)

> Superseded in part: see the correction at the top of §3 (tape de-duplication bug, 2026-09-23).

**No backtest here can promise zero losses; what it can do is bound them and show where the edge
survives our latency.** Evidence that is trustworthy:

* **Order-book replay, Sep 19–21, daily loss stop $2/market** (`deep_quote_backtest.py --stop-usd 2`):
  positive on every day at both 200 ms and 400 ms RTT for GLD 3 bps (+0.02/+0.17/+0.31 and
  +0.02/+0.17/+0.40), NVDA 3 bps (+0.01/+0.29/+0.68; +0.01/+0.09/+0.92) and HYPE 5–8 bps
  (e.g. 8 bps: +0.84/+4.40/+1.63; +0.76/+3.61/+4.69). SPY ≈ 0; QQQ lost on Monday; skip both for now.
* **Depth statistics over all Arcus history** (§5): deep fills on these markets paid in almost
  every week, and gold's did on Binance in 34/34 months.

**Rejected tool:** a replay over the 12-week trade history (no order book) was built and calibrated
against the order-book replay on the same days: it produced ~5× the fills and flipped HYPE 3 bps
from +$5.58 to −$44.58, because quotes re-centred on a mid estimated from prints chase noise. It
cannot judge the strategy either way and was deleted.

**Arcus's action budget does not break it.** The replay now enforces the documented per-subaccount
pools (20k order / 40k cancel units, +10 per $ traded, then one action per 10 s; a requote is one
modify). With a fresh budget and with zero starting budget (steady state), at 200 and 400 ms,
GLD 3 bps (+$0.50/+$0.59) and NVDA 3 bps (+$1.19/+$1.73) stayed positive on every day; HYPE 5 bps
made +$3.8 to +$7.2 with one −$0.53 day in two of the four settings. Unthrottled, NVDA would have
needed ~120k actions/day — far over budget — so earlier replays overstated re-quoting freedom.

**Loss-bounding rules for any live run** (all testable in `src/replay.py`): post-only only (never
pay the 2.25 bps taker fee); $25 clips, ≤$100 inventory per market; stop a market for the day at
−$2; quote only GLD/NVDA/HYPE at the frozen depths; pull a market whose trailing public deep-maker
edge turns ≤0 (ZEC/BTC/ETH already fail this). With 3 markets the designed worst day is ≈ −$6 plus
the adverse move on ≤$300 of open inventory. The frozen Sep 22–28 week is the next real evidence;
the recorder adds one day of order-book replay per day.

## 7. Side experiment: Propr (`propr/`)

REST loop polling every 2 s, quoting BTC on Hyperliquid through Propr at a **1.5 bps maker fee**.
Arcus tape shows BTC makers near the touch lose ~1 bps *before* fees, and the real fills on
2026-09-21 netted ≈ −$0.02 over 21 fills (+$0.012 captured, −$0.033 fees). Structurally negative;
recommend shelving it. Its tests also need `requests`, which is not in `requirements.txt`.
