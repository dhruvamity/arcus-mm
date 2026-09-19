Corrective pass — do not touch new out-of-sample data until every item below is done and evidenced

1. Fix the final report body, not just the banner and §1.

Delete or stub every section from §2 onward that still shows smoke-data results: the ZEC/SPCX/SLV "✅ +0.20%"/"+0.11%" rows next to INSUFFICIENT DATA, HYPE QUALIFIED, UNI HOLD, and NEAR/LIT/BTC/ETH/SOL REJECTED.
Remove "Pool exhaustion risk: ZERO" and the size-asymmetry claims — both are withdrawn in your own ledger.
Remove the $60 ZEC allocation with $8 clips (ZEC's real minimum is $15.34) and the "proceed to testnet" line.
Remove the "empirically validated / complete and verified" closing synthesis. Nothing has been validated yet.
Update verify_report.py so it fails the build if the report contains: any withdrawn-claim phrase, a "✅ +x%" status next to INSUFFICIENT DATA for the same market, or a clip size below that market's live minimum.

2. Produce an evidence pack. A sentence is not evidence — every line below needs a file, a command output, or a timestamp.

Full python3 -m unittest -v output, not a summary.
The commit hash for "28 of 28 fixed," and the diff or file list it touched.
The raw latency log: every sample with a timestamp, plus the run's real start and end time.
The exact line from venue_verified.yaml documenting the speed bump, in full.
The recorder health report for the 20-market run.
A mutation check: on a branch, reintroduce the old markout clamp and the Model A = B bug, rerun the suite, and show the relevant tests fail. If they pass anyway, they weren't testing what you think.
A list of which of the 8 named tests are real tests vs. references to verify_report.py, source files, or a YAML file — and whether the FIFO queue test from the log exists, and where.

3. Fix the pre-registered protocol.

Out-of-sample window: five OOS weekdays, not two. With two days, "no single day above 50% of PnL" is mathematically impossible and "60% positive days" requires both days positive — nothing could ever reach VALIDATED. Rewrite the pass/fail math for a 5-day window.
Fill threshold: adjust the "300 fills in two days" rule so slower markets aren't automatically INSUFFICIENT DATA, or split the criterion by liquidity tier.
Latency model: stop applying a flat 640ms to every order. Sample per-order latency from the measured distribution, and report a separate stress case using p95 + 500ms.
Market table: generate min clip sizes and tick sizes from /v1/markets at runtime. Re-verify BTC ($8.12, not ~$5), SLV ($6.01), AMD ($5.53), and the HYPE/ZEC tick sizes (0.001 vs 0.01) against that source.
Add a dated changelog entry for every change made in this pass.

4. Fix the assumptions registry and claims ledger.

Relabel the queue-priority rule — your unit tests verify the simulator, not the venue. State what would actually verify it against the venue.
Drop or re-source the "1.5–3.2 actions/fill" figure; it's from the withdrawn smoke test.
State plainly whether phase_14_backtest_7d.md and phase_15_live_paper_report.md's "validated" verdicts are real results or placeholders.
Fix CLM-14-09: it cites CRIT-5, but the taker fee is under criterion 4.
Audit the full ledger against the withdrawal banner and list every withdrawn claim, not just 5.

5. State where this actually runs. If production won't be this machine, re-measure latency from the real host before any of the above counts as evidence.

Timeline — hold this regardless of what this pass finds:

Sun 20 Sep: 3–4 hr weekend paper baseline, replay parity.
Mon 21 Sep: re-scan 12:00 UTC; live session 12:30–16:30 UTC minimum.
Tue 22–Fri 25 Sep: recorder only, PRELIMINARY reports; commit and tag frozen in-sample parameters before looking at Thu–Fri data.
Sat 26 Sep: G2 coverage check + a first-look 7-day backtest — dev-only, not validation (the 2-day OOS math is exactly why).
Keep recording through Fri 2 Oct: week of Sep 21–25 is tune, week of Sep 28–Oct 2 is the real 5-day OOS test.
No funding, no mainnet orders, until G3–G5 actually pass. A good Sat 26 Sep number does not count.