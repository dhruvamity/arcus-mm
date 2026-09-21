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

## 5. Side experiment: Propr (`propr/`)

REST loop polling every 2 s, quoting BTC on Hyperliquid through Propr at a **1.5 bps maker fee**.
Arcus tape shows BTC makers near the touch lose ~1 bps *before* fees, and the real fills on
2026-09-21 netted ≈ −$0.02 over 21 fills (+$0.012 captured, −$0.033 fees). Structurally negative;
recommend shelving it. Its tests also need `requests`, which is not in `requirements.txt`.
