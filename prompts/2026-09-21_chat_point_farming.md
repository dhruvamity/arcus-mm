## Arcus point farming strategies and prompt

Last updated: 2026-09-21

---

### *User:*

You have access to arcus docs

I want you to generate a accurate prompt to be given to grok ai which has access to entire twitter database asking it for best strategies or proven strategies based on arcus docs or all the possible best strategies to farm arcus efficiently to gain max points with almost no cost incurred



### *Claude:*

I couldn't open the Arcus docs (the connector call wasn't approved), so I didn't guess at the mechanics. This prompt makes Grok pull them from the docs itself. Fill in the two brackets:

```
You are a research analyst with full X (Twitter) search access. Research how to farm points on Arcus as efficiently as possible at near-zero cost.

Project: Arcus — docs at docs.arcus.xyz, official X account [@HANDLE], [one line: what Arcus is]. Several projects share this name, so confirm you have the right one and tell me if unsure.

GOAL: maximum points per dollar and per hour of effort, on one legitimate account, with minimal fees and no meaningful capital at risk.

STEP 1 — DOCS FIRST
Read docs.arcus.xyz and extract exactly how points are earned and calculated: every eligible action, multipliers, caps, decay, referrals, seasons/snapshot dates, eligibility, what points convert into, and the anti-abuse rules. Confirm the program is live and note recent rule changes. Cite the page for each claim.

STEP 2 — X RESEARCH
Search X for Arcus farming guides, threads and replies from the official account, team members and credible users. Be exhaustive, including lesser-known tactics. Prioritize the last 60 days and give each post's date. Look for proof: leaderboard screenshots, point totals, tx links, before/after results. Ignore paid shills, giveaway bait, bots and unverifiable claims. Call a strategy "proven" only if several independent accounts report it AND it fits the docs.

STEP 3 — OUTPUT
1. Ranked table: strategy | points | cost (fees/capital/time) | effort | risk | evidence | deadline
2. A simple daily/weekly routine for max points at ~zero cost
3. Label every item CONFIRMED (docs), REPORTED (X only) or SPECULATION
4. Flag anything that could get points voided (multi-accounting, bots, wash trading): don't recommend it, just tell me what the docs say and what's getting people banned
5. Warn about scams (fake claim sites, phishing, wallet drainers)
6. List all sources (doc pages + X links). If you can't find something, say so — never invent numbers or links.
```

I steered it away from multi-account and bot tactics because projects often void those points. If you approve the docs connector or paste the points/rewards page here, I'll tighten the prompt with the exact mechanics.



### *User:*

try generating prompt again, this time i will make sure u are able to read all arcus docs as well



### *Claude:*

The docs opened fine this time, and the main finding is that they describe no points, XP, season or airdrop program anywhere. What they do document is fee tiers, referral commissions, a public leaderboard, vaults, invite codes and a free testnet. The only hint of a rewards feature is an unexplained "rewards page" in the pre-launch iOS app. So I rebuilt the prompt to have Grok first check whether a points program actually exists, with the documented facts preloaded so it doesn't invent mechanics:

```
You are a research analyst with full X (Twitter) search. Research how to earn Arcus (arcus.xyz) rewards/points as efficiently as possible at near-zero cost.

VERIFIED FROM THE OFFICIAL DOCS (docs.arcus.xyz, read 19 Sep 2026):
- Arcus is a non-custodial perps + spot DEX: crypto, single-stock and ETF perps (24/7) plus tokenized-stock spot. Collateral is USDG. Mainnet is live; testnet gives ~$1,000 free paper collateral.
- The docs describe NO points, XP, season or airdrop program. Do not assume one exists. The only hint is a "rewards page showing your distribution history" in the pre-launch iOS app (unexplained).
- Documented levers: 7 fee tiers by rolling 30-day volume, with maker rebates at high tiers (live rates: api.arcus.xyz/v1/feetiers); referral commissions of ~10% of referees' trading fees (15% for VIP/Max), 3% for the referrer's referrer and 2% for the next level, with an optional 0-50% referee kickback; public leaderboard by volume/PnL/fees; vaults; up to 10 API-only subaccounts per wallet; invite codes that grant perps access (1 earned per $1M lifetime volume; testnet only so far).
- Costs: no Arcus deposit/withdrawal fee; spot "free at launch" (the app now itemizes network + platform fees on swaps); perps maker/taker fees; plus funding, spread and liquidation risk.
- Eligibility: not available in the US, Canada, UK and other restricted regions.

TASK
1. Search X (official account, team, announcements, credible users) for any Arcus points/rewards/airdrop program, including whether testnet, referrals or vault deposits count. Label it CONFIRMED (official), RUMORED or NONE FOUND.
2. If confirmed, extract the exact rules: eligible actions, formula, multipliers, caps, seasons/snapshot dates, anti-abuse terms.
3. Find strategies people report for maximizing it (or, if none exists, for the documented levers above), with proof: leaderboard screenshots, point totals, tx links. Be exhaustive, prioritize the last 60 days, give each post's date, and ignore paid shills, bots, giveaway bait and unverifiable claims. Call a strategy "proven" only if several independent accounts report it AND it fits the docs.

OUTPUT
- Ranked table: strategy | how it earns | est. cost (fees, funding, spread, gas, capital at risk) | effort | risk | evidence | deadline
- A simple daily/weekly routine for max return at ~zero cost
- Label every claim CONFIRMED (docs/official), REPORTED (X only) or SPECULATION
- Flag anything that could void rewards (multiple accounts, self-referral, wash trading, bypassing geo-restrictions). Don't recommend it; tell me what's getting people banned
- Warn about scams (fake claim sites, phishing, wallet drainers)
- Cite every source (X links, doc pages). If you can't find something, say so. Never invent numbers or links.
```

Volume farming on perps is never truly zero-cost (fees, spread, funding, price risk), so the prompt makes Grok price that in. If you've seen an official points post or page, paste the link under the prompt as extra context.



### *User:*

audit if this prompt is good enough for a market makng bot task to a ai agent



### *Claude:*

**Verdict: a strong research spec, but not yet a safe or executable agent brief.** The quant discipline is unusually good: falsification-first, three fill models (optimistic, base, conservative), walk-forward validation, a deterministic hot path with hard kill switches, and staged gates before any live capital. Keep all of that. The gaps are what's missing around it, plus a few places where it clashes with how Arcus works (I checked the Arcus docs).

**Fix before giving it to an agent**

1. **No permissions or stop points.** §55 says run Phases 0–12 in order and §58 says start with Phases 0–1, so an agent can read it as "do everything." Say explicitly:
   - Stop after Phase 1 for approval.
   - Never place mainnet orders.
   - Use only a testnet, trade-only API key, never your wallet key or a withdraw-scoped key.
   - No self-trading, spoofing/layering, or geo-restriction workarounds.

2. **Arcus's rate-limit pools are missing, and they could decide the whole question.** Each subaccount starts with 20,000 order and 40,000 cancel units. These grow by 1 per $0.10 of filled notional, then drip one action per 10 seconds. A modify costs an order unit, and `cancelAllOrders` costs a flat 1,000 cancel units. So "CANCEL ALL on every stale-data event" would drain the starting cancel pool in about 40 triggers. At $5 fills, each fill buys about 50 units, so the sustainable order-to-fill ratio is roughly 50:1. The simulator must enforce this, and Arcus's `scheduleCancel` dead-man's switch (5 s–5 min, 10 auto-fires per day) should be the venue-side failsafe.

3. **The L2 sequence rule would misfire.** §10 treats any gap as corruption. The docs say the first delta after a snapshot may be several sequences ahead (don't require +1), only mid-stream gaps are real, and repeated prices in one frame apply in order. Also:
   - Sockets auto-close after 24 h, and the trades channel has no snapshot, so the recorder needs overlapping connections or it will have daily holes.
   - With 100 subscriptions per socket and a 25 weight/s REST budget per IP, universe scans must use WebSockets, not polling.

4. **Testnet can't validate economics.** Phase 11 compares predicted vs actual fills and adverse selection on testnet. Unless Phase 0 shows testnet has real flow, that only tests plumbing (order lifecycle, latency, reconciliation). Economics have to come from mainnet-data paper trading and, eventually, the micro live experiment.

5. **Feasibility comes too late, and success isn't numeric.** At $5–$10 quotes, 1 bp of net edge is $0.0005–$0.001 per fill, so about 2,000 fills a day to earn $1. Add an early go/no-go before building recorders: spread minus Base-tier fees minus adverse selection, times the fills achievable within the pool budget. Then replace "acceptable drawdown / reasonable fill rate / stable region" with numbers, for example:
   - Bootstrap confidence interval above zero under the conservative fill model.
   - A minimum number of fills per fold.
   - A drawdown cap.
   - Positive results in k of n walk-forward folds.
   - A stop rule if S0–S3 fail.

**Smaller fixes**
- Cut the backstory (Kimi, Grok, 300 agents, "the source research says…") and the ~10 repeats of "no LLM in the hot path." At 56 KB, it works better as a stable spec plus short per-phase tasks with acceptance criteria and a progress log.
- Avellaneda–Stoikov needs a defined horizon T for a perp (rolling or infinite-horizon variant), a statement that δ is the *total* spread (bid = r − δ/2, ask = r + δ/2), and how κ is fitted. Otherwise expect a 2× spread error.
- Add Arcus execution details:
  - Quote with ALO (post-only).
  - Handle POST_ONLY_WOULD_CROSS and SELF_TRADE rejections.
  - Every order needs a goodTilTime (≥ 1 month ahead).
  - A modify is cancel+place, and only same-price size decreases keep queue priority, which the queue model needs.
- Record exchange and local receive timestamps, use integer ticks instead of floats, and correct for multiple testing across markets × strategies × parameters.

If your real goal is farming volume rather than proving profit, this prompt's headline metric (positive net expectancy) is a much stricter bar, and it would reject strategies that are fine for farming.

Want me to rewrite it as a tighter v2 .md with these fixes?



### *User:*

just suggest the strategies which are possible to do for breakeven or net positive expectancy as anyways all strategies should be backtested and hope the prompt also includes that



### *Claude:* _(no response captured)_

### *User:*

now that i have provided u the repo entirely, now do a more accurate audit and tell me the next steps accurately and if the analysis / research report made by my ai coding agent is accurate or not and give the follow up accurate prompt as detailed as possible and also include any redundant file/script \.md file which is unecessary then mention to delete those to keep repo clean and straightforward



### *Claude:* _(no response captured)_

### *User:*

resume where u left



### *Claude:* _(no response captured)_

### *User:*

now that i have provided u the repo entirely, now do a more accurate audit and tell me the next steps accurately and if the analysis / research report made by my ai coding agent is accurate or not and give the follow up accurate prompt as detailed as possible and also include any redundant file/script \.md file which is unecessary then mention to delete those to keep repo clean and straightforward



### *Claude:*






