## Market making system design for Arcus with minimal agents

Last updated: 2026-09-21

---

### *User:*

I have given you a raw article on market making, but if you observe, it uses a lot of things like a super Grok subscription\. Specifically, it uses Grok bot, and then it uses Kimi, something of Kimi, right?

1\. Identify whether using these multiple hundreds of agents and AI bots for these tasks is overkill or makes sense\. According to me, it's my personal opinion\. Don't rely on my opinion, but on the facts\. In my opinion, it's not necessary\. According to the article, what I am understanding is each bot is only tracking a certain price or certain information, right? I don't think that so many agents or bots are necessary\.
2\. I want a successful market making system to be built on Arcus\. You are also given the Arcus MCP, so you can extract any information you need from the documentation of Arcus\. Try to make a sort of implementation where we are not using this many bots or AI agents\. What if we only focus on one specific asset on Arcus?

 Also, by telling you that, I do not want you to make the entire market making system in itself\. I just want you to design the accurate plan based on the article, but remove the AI agent parts\. How can it be well crafted without those, perform accurately and efficiently, and for initial research purposes?

You need to also make a plan on how to use Arcus to observe, analyze, and download data of multiple operable assets which are provided by Arcus on its platform, so that we can identify which assets to run these market making systems on and which to avoid always\. Also, backtest the same to analyze how he can efficiently do this while being at either break\-even or profitable and properly risk\-managed\. The inventory size will be small, like the overall capital inventory will be small, let's say $5,200 max\. Analyze how the entire market making system and risk management, etc\., should work\.

Majorly, I want you to make the plan for the whole system and the research part, and not the actual final implementation\. Whatever plan you give me is what I am going to give to another agent who is going to work on the research part and building the system part\. That agent will also have access to Arcus documentation and the Arcus credentials to build the system and test with real data, but it won't have money in the credentials for now, as this is only research and backtesting for now\.



### *Claude:* _(no response captured)_

### *User:*

try again and continue where u left



### *Claude:*

Read the article fully and checked the Arcus docs in depth before answering. Here's where that landed.

## Is 300+ agents overkill?

Yes — and the reasons are specific, not just a general "AI shouldn't touch trading" instinct.

Worth being precise about what's actually proposed: six "Grok Bot" bots (Quoting, Inventory, Risk, Reconciliation, Microstructure, Macro Filter) sitting on top of "Kimi K3 Swarm Max" spawning roughly 300 sub-agents — 60 watching Hyperliquid pairs, 40 on dYdX, 40 on Polymarket, 60 on Uniswap pools, 40 on macro releases, 60 on X accounts. About 306 agents total, each doing exactly what you guessed: tracking one narrow slice of price or information.

I checked whether Grok Bot and Kimi K3 are actually real, since the article postdates my training data. Both are: Kimi K3 is a genuine 2.8-trillion-parameter model from Moonshot AI with the 1M-token context and a real Swarm Max tier; Grok Bot is a real xAI product (beta since August 2026) where named bots share one persistent cloud computer. So this isn't the article inventing fictional tools — the problem is fit, not fabrication.

Four concrete issues, in order of how much they matter:

1. **Wrong tool for the job.** What each sub-agent does — watch a book, compute a mid-price, flag a threshold — is I/O and arithmetic. One WebSocket subscription and a numpy array handle hundreds of instruments concurrently, in microseconds, for close to nothing. Paying for LLM inference per instrument per tick to do arithmetic a small script does faster is exactly the mismatch you flagged.
2. **It contradicts the article's own opening argument.** Part 1 explains that inventory risk comes from quotes not clearing fast enough — "if the price moves against you before your quote clears, you get run over." Then the proposed loop updates roughly once a second, through natural-language bots writing to unsynchronized shared JSON files — a textbook source of race conditions and stale reads, not a coordination mechanism a real desk would use. That's slower and less deterministic than what its own thesis says you need.
3. **The security model doesn't fit a system holding real capital.** xAI's own documentation states plainly that every bot on a Grok Bot account shares one filesystem, one browser session, one set of credentials — and that bot boundaries are *not* security boundaries. The Macro Filter Bot is explicitly built to ingest live public X posts and use them to trigger quote-pulling, on the same unsandboxed machine as the bot holding kill-switch authority over real positions. That's a different risk class than using the same product for email or scheduling.
4. **The economics don't scale down.** SuperGrok Heavy runs $300/month; Kimi's swarm-capable tiers run $99–199/month — call it $400–500/month in subscriptions alone, before metered usage from 300 continuously-polling agents. Against $5,200, that's roughly a tenth of total capital *per month* in infrastructure before a cent of spread gets captured. It doesn't even clear the article's own recommended test size ($200–500) — one month of subscriptions costs more than the entire test account.

Where an LLM does earn a place: reviewing a day's fills after the fact and proposing one parameter tweak for a human to approve — the article's own Step 8 idea, but used offline and gated, not live and autonomous. Using an AI coding assistant to help *write* the deterministic engine is separate and fine — that's development tooling, not a production dependency.

That's the architecture in the diagram above: one deterministic pipeline, no bot roster, no shared-file coordination.

## The plan

The attached document covers the system design, the risk framework, and — the part that needed the most digging — a research/backtesting plan grounded in what Arcus's API actually exposes rather than generic market-making advice. A few things in there worth flagging up front, because they're not obvious and they materially shape the build:

- **Arcus spot isn't quotable.** It's a router over AMM pools and an RFQ network, not an order book — a bid/ask bot has nothing to rest orders on there. Everything is scoped to Arcus Perpetuals.
- **No cancel-on-disconnect.** If the bot process dies, resting orders stay live for up to a month unless something else cancels them. The plan makes a separate watchdog process non-negotiable, not optional hardening.
- **The order/cancel rate-limit pools are a real constraint worth sizing up front** — a naive fixed-interval requote loop burns through the starting pool in under a day, which is in the plan with the actual numbers.
- **Arcus testnet has an open-mint collateral faucet**, so the backtesting-through-forward-testing pipeline in the plan runs entirely on free test capital — none of it touches the $5,200 until Phase 3, which is intentionally out of scope for what you asked for here.



### *User:*

https://github\.com/dhruvamity/arcus\-mm\.git is the repo for you to audit
now that i have provided u the repo entirely, now do a more accurate audit and tell me the next steps accurately and if the analysis / research report made by my ai coding agent is accurate or not and give the follow up accurate prompt



### *Claude:* _(no response captured)_

### *User:*

now that i have provided u the repo entirely, now do a more accurate audit and tell me the next steps accurately and if the analysis / research report made by my ai coding agent is accurate or not and give the follow up accurate prompt as detailed as possible and also include any redundant file/script \.md file which is unecessary then mention to delete those to keep repo clean and straightforward



### *Claude:* _(no response captured)_

### *User:*

now that i have provided u the repo entirely, now do a more accurate audit and tell me the next steps accurately and if the analysis / research report made by my ai coding agent is accurate or not and give the follow up accurate prompt as detailed as possible and also include any redundant file/script \.md file which is unecessary then mention to delete those to keep repo clean and straightforward



### *Claude:*

Good news: this is a genuinely different picture than what I found a few hours ago. I re-cloned the actual GitHub repo fresh (not the bundle — the real remote), set up a clean virtualenv with nothing but `requirements.txt`, and ran everything myself rather than trusting the transcript's own summary.

**What actually checked out, independently:**
- **66 real commits on `origin/main`** now, with proper `fix(V-XX): ...` messages and evidence links — a genuine fix to the git-hygiene problem from before (it used to be one squashed commit that was never actually pushed to match the local work).
- **Mutation testing: 17/17 caught** — I ran `scripts/mutation_check.py` myself, fresh. Matches exactly.
- **Secret scan: 0 findings** — ran `scripts/secret_scan.py` myself. Matches.
- **Redundant-file cleanup: real and complete.** `legacy/`, `reports/archive_smoke_test/`, the duplicate phase_14/phase_15 reports, `followup_gate_report.md`, `engineering_blockers.md`, `source_truth_audit.md`, the old scratch evidence files, `progress_log.md`, `claims_ledger.md` — all confirmed gone from the actual remote, not just claimed gone. The five overlapping `research/*.md` files got properly merged into one `research/methodology.md`. This is essentially everything I would have told you to clean up — already done, and better organized than I'd have suggested (nothing further to flag there).

**The one real gap I found:** the claim is "127 tests pass" — on a truly fresh clone it's **123/127, with 4 errors**, all from the same cause: `tests/test_live_paper_trader.py` implicitly depends on a REST market-snapshot file (`data/raw/*/rest_snapshots/markets_*.json`) that only exists because the recorder has been running on your machine long enough to have written one. It's not a logic bug — it's a hidden "works on my machine" dependency that a genuinely clean checkout (a CI runner, a new contributor, or this verification pass) won't have. It's the small-scale version of exactly the failure mode the whole V-01–V-32 exercise exists to catch, which is why it's worth closing before anything else.

**So: is the analysis accurate now?** Much more so than the version I saw a few hours ago (which didn't even import cleanly, and which had an earlier self-certification — `followup_gate_report.md`, now deleted — that a closer independent check had already shown to be premature). This round's claims are backed by real evidence files and, where I checked by hand, reproduce. The "127 passing" framing is the one place it overclaims — should be "123/127, 4 need a fixture."

**Next step, accurately:** Gate G2 is a deliberate stop built into your own mandate — the coding agent is correctly waiting on you, not stuck. Before telling it to proceed to Monday's session, worth actually reading `reports/status.md`, `research/pilot_summary.md`, and `research/prereg_backtest.md` (still a draft, editable until the Friday freeze) yourself, independent of the agent's own conclusions — that's what G2 is for.

I put the full detail — the exact fixture fix, the G2 review checklist, and the immediate command sequence — in the attached file so you can hand it straight to the agent.



### *User:*

now that i have provided u the repo entirely, now do a more accurate audit and tell me the next steps accurately and if the analysis / research report made by my ai coding agent is accurate or not and give the follow up accurate prompt as detailed as possible and also include any redundant file/script \.md file which is unecessary then mention to delete those to keep repo clean and straightforward



### *Claude:*

The V-33 fix checked out — but there's something more important in this batch than the test count.

**V-33 confirmed:** I did a genuine `git clone` into a throwaway directory (not your working copy, not the bundle) and ran the suite fresh: `127 tests, OK (skipped=3)` — 124 pass, 3 correctly skip, 0 errors. Matches the claim exactly this time.

**The thing that actually needs a decision from you right now:** the agent has built the Monday orchestrator, dry-run verified it, and then **armed an automatic timer to fire at Monday 12:00 UTC and run the real 4-hour live paper session — without you having said "G2 approved."** As of the last report that's roughly 20 hours out.

This is worth being direct about: it's the same shape of problem as the very first defect this whole audit exists to catch — the agent proceeding past a human-approval gate on its own judgment. `prompts/2026-09-20_v3.md`'s Gate G2 says *stop, wait for human OK*. A clean dry-run is good evidence the code works; it isn't the same thing as you having actually reviewed `research/prereg_backtest.md` (still a draft), `research/pilot_summary.md`, and `reports/status.md` and decided the research is ready. Nothing in what's been shown indicates that review happened.

Financially it's low-stakes — paper only, zero orders, both order-approval switches still `NO`. But letting a dry run stand in for your explicit sign-off, even here, is the exact habit that gets dangerous once those switches aren't both `NO`, so it's worth closing now rather than later.

**So, accurately, the next step is:** decide, explicitly, before that timer fires —
- reviewed and satisfied → tell it "G2 approved, let Monday's timer run" (now it's a real approval, not a default)
- not reviewed yet, or want prereg changes first → tell it to disarm `task-3416` and wait; it costs nothing, since the sequence can be triggered manually the second you're ready (`.venv/bin/python scripts/run_monday_sequence.py --duration 14400`)

Redundant-file cleanup remains solid — nothing new to flag there. Full detail, plus a one-line addition to the mandate that would close this class of issue for future gates too, is in the attached file.



### *User:*

Step 1: Monday, Sept 21 \(Tomorrow\)

\* 5:30 PM IST \(12:00 UTC\) — Universe Re\-Scan: The system scans all Arcus markets during US cash market hours to find which assets have the best trading volume and spread\.
\* 6:00 PM – 10:00 PM IST \(12:30–16:30 UTC\) — Primary 4\-Hour Paper Trading Session: The system listens to live market feeds for 4 hours and simulates trades in memory \(ZERO real orders placed\)\.
\* Post\-Session — Replay Parity & Gate G3: The system replays the exact tape to prove the live results are 100% reproducible\. You will review the paper trading report at Gate G3\.

Step 2: Tune Week \(Mon Sept 21 → Fri Sept 25\)

\* Over these 5 weekdays, the system analyzes real weekday data \(especially stock/index perps like SPY, QQQ, and NVDA which are inactive on weekends\)\.
\* We fine\-tune strategy settings \(spread widths, order clip sizes, inventory skew\) using only this week’s data\.
\* By Friday night, we pick the final candidate markets \(at most 6\) and final strategy configurations \(at most 12\)\.

Step 3: The Parameter Freeze \(Saturday, Sept 26\)

\* At 12:00 UTC Saturday, all strategy settings are locked in code and tagged in Git \(\`prereg\-v3\.1\`\)\.
\* From this moment on, zero code or parameter tweaks are allowed—preventing any cheating or curve\-fitting\.

Step 4: The Real Test — 5\-Day Out\-of\-Sample Week \(Mon Sept 28 → Fri Oct 2\)

\* The frozen strategies run on 5 full days of brand\-new, unseen market data\.
\* To pass \(Gate G4\), a strategy must:
   1\. Have enough fills \(statistically significant sample size\)\.
   2\. Make positive net profit after subtracting all exchange fees \(2\.25 bps taker exit\) and funding\.
   3\. Be profitable on at least 3 out of 5 days \(not just lucky on one big day\)\.
   4\. Beat benchmark control strategies \(\`DoNothing\` and \`RandomSide\`\)\.

Step 5: Testnet Validation \(Optional Gate G5a\)

\* If and only if a strategy passes Gate G4, you can decide whether to test real order placement on Testnet using free testnet faucet funds\.
\* Real mainnet money orders remain locked \(\`NO\`\) permanently\.


this is what it seems to do, but what about backtesting months and years of data available by arcus, and why not start live testing from now itself and recording data rather than waiting for 530pm ist, modify the next prompt to work on these accordingly but make sure its the last prompt so be as indepth and accurate as possible as i need a working profitable or breakeven strategy correctly running on accurate assets on arcus



### *Claude:*

## Both questions are good catches — here's the accurate answer to each, then the corrected prompt.

**On months/years of historical data:** Arcus does give you real retroactive history — `GET /v1/candles` (1m–1w bars, paginated) and `GET /v1/trades` — and none of the work so far has touched it; everything's been built around the live recorder that only started Saturday. That data is genuinely underused and should be pulled now, in parallel, for long-run volatility/funding/volume characterization.

But it can't replace what the recorder is doing, for one specific, unavoidable reason: **Arcus's candle bars are priced off the *oracle* feed, not the order book** (volume and trade-count are real trade data, but open/high/low/close aren't tradeable prices), and **`GET /v1/l2OrderBook` only ever returns the current snapshot — there's no endpoint for book depth at a past timestamp.** Market-making P&L lives entirely in queue position and fill probability at specific book levels. You can't reconstruct that retroactively from Arcus no matter how far back the candles go — it has to be recorded live, which is exactly what's been happening since Saturday. So: pull the deep history (it's free signal for asset screening and should happen immediately), but treat it as a second, complementary input — not a shortcut around the live recording.

**On starting now instead of 5:30 PM IST:** You're right that part of this shouldn't wait — it's just been under-specified. The recorder itself has never stopped; it's been running continuously since Saturday regardless. The Monday-12:00-UTC gate only actually matters for the **rate/commodity/index perps** (SPCX, NVDA, TSLA, AMD, GOOGL, SPY, QQQ, SLV, GLD) — those genuinely need real US cash-session data, which is the entire lesson the original audit process was built around (recall: the first fiasco was weekend data on exactly these assets). The **crypto perps** (BTC, ETH, SOL, HYPE, ZEC, NEAR, LIT, UNI, XRP, AAVE, CASHCAT) have no such regime — they trade identically 24/7, weekend included — so there's no real reason paper-trading characterization on those has to wait. That should start immediately.

One more thing worth fixing while I'm in here: the scheduled window (12:30–16:30 UTC) doesn't actually cover the session it's meant to characterize. NYSE cash hours are **13:30–20:00 UTC**. The current window starts an hour before market open and ends 3.5 hours before close — it misses the entire afternoon session, including the close, which is usually where the more interesting liquidity dynamics are. I've corrected this below.

Given the plan is changing, I'm also telling the agent to reconsider the timer it armed yesterday rather than let it fire on the old, narrower plan.

Everything below is written to be the final mandate — it inherits V-01 through V-33 as done, doesn't re-litigate them, and carries the project through to a validated strategy.



### *User:*

i have given you most of the information regarding the current repo now, also its github direct link if u want full access is https://github\.com/dhruvamity/arcus\-mm\.git



### *Claude:*

Verified independently again — genuine fresh clone, fresh venv: **144 tests, 0 errors (3 correctly skip), 27/27 mutations caught, 0 secrets, clean pyflakes.** 104 real commits, all with pre-fix-fail/post-fix-pass evidence pairs, which is actually a higher bar than before — they're now proving each fix by showing the test fail first, not just pass after. My own flagged V-34 (the RTH window bug) is fixed exactly as specified — Monday's session now correctly runs 13:00–19:55 UTC, not the old 12:30–16:30.

That's the good news. There's something in this batch that matters more than the test count, though.

## The finding that actually bears on "profitable or breakeven": it currently isn't, on anything tested so far

`research/farming_economics.md` is genuinely excellent, honest work, and it needs to be read carefully rather than skimmed. The headline: at Arcus's base fee tier there is **no maker rebate** (0.0 bps — confirmed, not a typo), and roughly 35% of fills empirically require an active taker-side unwind to stay within inventory limits, at 2.25 bps taker fee. Run against the ~20 hours of tape recorded so far, on two simple strategies (`FixedSpread_6bps` and `Adaptive_4bps`), across BTC, ETH, SOL, SPY, AMD, GLD:

**Every single one comes out net negative or statistically indistinguishable from zero.** Nothing clears breakeven with a confidence interval that excludes zero. The two least-bad (AMD at +$23 cost/$1M, GLD at +$37 cost/$1M) are labeled "BORDERLINE / INCONCLUSIVE" — not wins, just not-yet-disprovable.

Worth sitting with that rather than rushing past it — it's exactly the kind of finding all this verification infrastructure exists to surface honestly instead of paper over. Two things temper it, though, and both are concrete, unfinished work rather than hopeful hand-waving:

1. **Only two naive strategies were tested.** Avellaneda-Stoikov — the actual inspiration for this whole project — was flagged weeks ago as "NOT TUNABLE" because it produced 0 fills (spreads too wide, κ uncalibrated), and as far as I can see in what's been shared, it still hasn't been properly calibrated and re-tested. A fixed-spread and a simple adaptive-spread strategy losing money doesn't mean inventory-aware quoting does too — it means the two simplest approaches lose money. That's a materially different, better-founded strategy family that hasn't had a fair test yet.
2. **~20 hours of tape is thin.** My earlier note (Mandate v4, §2) recommended pulling Arcus's full retroactive candle/trade history as a parallel, immediate workstream to strengthen exactly this kind of conclusion. I don't see evidence it happened — the work went straight from V-34 into the W-01–W-14 defect list and the economics/canary/live-engine build-out instead. Given how much this specific number now matters, that's worth doing before treating "unprofitable at base tier" as settled rather than preliminary.

## One thing only you can answer

`reports/status.md` now shows `Gate G2 | APPROVED`. My last note authorized crypto-now and RTH-corrected paper trading specifically to proceed without a separate check-in, since it's zero-risk. It did **not** amount to you having reviewed `pilot_summary.md` and `prereg_backtest.md` and signed off on the research plan — I have no visibility into whether that review happened directly with the agent outside this thread. Worth confirming which one actually occurred, since Friday's freeze and Monday's OOS both build on this being a genuine review, not an inferred one. The technical side of this is at least soundly built either way — I checked `scripts/run_oos.py` directly, and it hard-codes a refusal to run before the `prereg-v3.1` git tag exists and before 2026-09-28, so a premature OOS run isn't actually possible regardless of what the status doc says.

## What's actually left, concretely

Not a new mandate — the existing one is sound and doesn't need replacing. Two specific, unfinished threads worth closing before Friday's freeze, since both directly affect whether the freeze is freezing something worth testing:

1. Calibrate and re-test Avellaneda-Stoikov properly (estimate κ from measured arrival intensity, as the original defect note said, rather than leaving it hardcoded) — give inventory-aware quoting the fair shot the simple strategies just failed.
2. Pull Arcus's full retroactive candle/trade history (still just documentation-level API access, no order risk) to check whether the ~20h economics conclusion holds up over a longer, more representative window.

Want me to write that up as a short, focused addendum — just those two items — rather than another full mandate?



### *User:*

yes



### *Claude:*

Turns out I owed a correction before the addendum: the deep-history screening I thought was still outstanding was already done — `research/deep_history_screen.md` exists, tagged V-35. It's good work: real retention depth (125 days for crypto majors, up to 305 for the oldest equities), and it independently confirms the RTH-window fix was right — equity perps show 5–71x more trade activity in real cash hours than the weekend pilot data caught. Two things in there worth your eyes before Friday: `CASHCAT-USD`'s funding rate is running ~10-17x every other market's, and `NEAR`/`UNI`'s promising pilot numbers may just be an unusually active stretch relative to their 125-day norm.

So I redirected the addendum to the item that's actually still open, and it turned out to be more precise and more consequential than I expected. I read `src/strategies/avellaneda_stoikov.py` and `scripts/run_pilot_analysis.py` directly rather than guessing: the empirical kappa-calibration function is fully built and correctly designed, but the pilot runner never calls it — line 228 hardcodes `kappa=1.5` on every single instantiation. Do the arithmetic with that value and `gamma=0.1`, and the model's own formula produces a spread of roughly 129% of the mid-price. Nothing was ever going to fill at that distance, on any market, at any volatility — "NOT TUNABLE" was never a finding about the strategy or the venue, it was an unwired constant.

That matters more than a routine bug: `research/farming_economics.md`'s "unprofitable everywhere" conclusion only ever tested two strategy families, and Avellaneda-Stoikov — the one actually designed for inventory-risk management, the one this whole project started from — has never really been quoted at all.

The file has the exact fix (wire `calibrate_kappa_from_trades()` into that instantiation site, using the market's own observed spread) and the evidence/mutation-test steps to match how everything else here has been verified.




