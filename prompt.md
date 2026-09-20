# Arcus MM — Independent Verification of Mandate v3 & Gate G2 Follow-Up

**Purpose:** This is a short addendum, not a new mandate. `prompts/2026-09-20_v3.md` remains the governing document — do not replace or overwrite it. This note records what an independent, from-scratch verification (fresh clone, fresh venv, no access to your locally-recorded data) found when checking the V-01–V-32 remediation claims, and lays out the one concrete gap plus the approval checklist Gate G2 is actually waiting on.

---

## 1. What was independently re-verified (fresh clone, no shortcuts)

Starting from a clean `git clone` of `github.com/dhruvamity/arcus-mm` (66 commits, matches local) and a brand-new virtualenv with nothing but `requirements.txt` installed:

| Claim in `walkthrough.md` / `research/audit.md` | Independently reproduced? | Detail |
|---|---|---|
| Mutation suite: 17/17 caught | **Confirmed** | Ran `scripts/mutation_check.py` fresh — identical 17/17 result. |
| Secret scan: 0 findings | **Confirmed** | Ran `scripts/secret_scan.py` fresh — 0 findings, git history clean. |
| Redundant/stale files removed (Appendix B.A–H) | **Confirmed** | `legacy/`, `reports/archive_smoke_test/`, `followup_gate_report.md`, `engineering_blockers.md`, `source_truth_audit.md`, `phase_14_backtest_7d.md`, the old `evidence/reproduce_R_*.txt`, `research/progress_log.md`, `research/claims_ledger.md`, etc. are genuinely gone from `origin/main`, not just locally. |
| Git hygiene (one commit per defect, pushed) | **Confirmed** | 66 real commits with `fix(V-XX): ...` / evidence links, actually on `origin/main` — a real improvement over the earlier single squashed commit. |
| "127 tests pass" | **Partially — 123/127, not 127/127** | See §2. Not a logic bug, but the claim as written overstates it. |

This is a substantially different, more credible result than the audit found a few hours earlier (at that point the repo didn't even import cleanly). The `from __future__ import annotations` sweep and the `scripts/ev.sh` evidence-wrapper discipline visible in this session are real, structural improvements, not cosmetic ones.

## 2. The one concrete gap: `test_live_paper_trader.py` is not actually hermetic

Running `bash scripts/ci.sh` fresh gives:

```
Ran 127 tests in 0.671s
FAILED (errors=4, skipped=3)
```

All 4 errors are the same root cause, in `src/venue.py::VenueMetadata.load_all_specs()`:

```
FileNotFoundError: No markets snapshot found in data/raw/*/rest_snapshots/
```

`src/venue.py` is correct to prefer live venue data over hardcoded tables (that's the right call, and it's exactly what Mandate v3 asked for — V-15). But `tests/test_live_paper_trader.py`'s `asyncSetUp` calls `initialize_engine()`, which calls this loader with no fallback and no fixture. On your machine this passes silently, only because the recorder has already been running long enough to have written a real `data/raw/*/rest_snapshots/markets_*.json` — so the dependency is invisible locally. On a genuinely fresh checkout (a new contributor, a CI runner, or this verification pass) there is no such file yet, and these 4 tests cannot run at all. That means the "clean clone" evidence (`evidence/2026-09-20/clean_clone_clean_clone.txt`) most likely also has this file present by the time it ran, rather than testing the truly-empty-`data/` case.

**Fix (small, one place):** give `tests/test_live_paper_trader.py` its own fixture — either commit a minimal `tests/fixtures/markets_snapshot_sample.json` and pass it explicitly via `VenueMetadata.load_all_specs(snapshot_path=...)`, or monkeypatch/inject a small in-memory spec dict in `asyncSetUp` instead of hitting the filesystem. Either way, re-run `scripts/ci.sh` from a directory with `data/` genuinely empty and confirm 127/127 (or update the test count claim to match reality if 3 stay skipped by design).

This isn't a blocker for anything currently gated — it doesn't affect the engine, the fill models, or the PnL logic, all of which are covered elsewhere and did pass. It's worth fixing before Monday mainly because it's exactly the kind of "passes on my machine, not provably elsewhere" gap the whole V-01–V-32 exercise exists to catch, and it's cheap to close.

## 3. Redundant files: nothing further to flag

The Appendix B cleanup (legacy/, archive_smoke_test/, the duplicate phase_14/phase_15 reports, the old prompt-adjacent scratch evidence, progress_log.md/claims_ledger.md, and the research/*.md consolidation into `research/methodology.md`) covers everything that looked redundant in the previous pass. Current tree (167 tracked files) is organized and I don't see further duplication worth flagging. No action needed here.

## 4. What Gate G2 is actually waiting on

Per `prompts/2026-09-20_v3.md`'s own gating rule, G2 = **STOP, wait for human OK** — this isn't a task for the coding agent to clear on its own; it's specifically the point where it's waiting on you. Before telling it to proceed to Monday's 12:00 UTC universe re-scan and paper session, worth actually reading (not just skimming) three files, since this is the point where a wrong pre-registration or a bad market pick costs a week, not an hour:

- `reports/status.md` — current one-page state
- `research/pilot_summary.md` — does the ranked market list and the "not tunable" labels look right to you, independent of what the agent concluded?
- `research/prereg_backtest.md` — this is a **draft**, editable until Friday 09-25 EOD UTC freeze. Check the market list (≤6), strategy grid, and sample-size thresholds actually match what the pilot data supports, not what would be convenient.

Once you're satisfied with those three, the go-ahead is a one-line instruction to the agent (e.g. "G2 approved, proceed to the Monday sequence"). Nothing else needs your input before that.

## 5. Immediate next commands (in order)

1. Fix the `test_live_paper_trader.py` fixture gap (§2); confirm `bash scripts/ci.sh` is green with `data/` empty.
2. Commit as `fix(V-33): hermetic fixture for live paper trader tests`, evidence via `scripts/ev.sh`, push.
3. You review the three files in §4.
4. On approval, resume Mandate v3's Monday sequence (12:00 UTC universe re-scan → 12:30–16:30+ UTC primary paper session) exactly as written there — no changes needed to that plan.
5. Keep the recorder (PID 11661) untouched through this — it's still the only source of the irreplaceable multi-day data everything else depends on.