# Audit v3 Ledger — Ground Truth & Defect Remediation

**Generated At:** `2026-09-20 09:26:18 UTC`  
**Evaluation Scope:** All Findings (V-01 through V-32) from Mandate v3 (`prompts/2026-09-20_v3.md`)  
**Commit Discrepancy Note:** Prior reports referenced commit hash `23a03f3` which does not exist on the remote GitHub repository. This occurred because the initial repository setup was committed and pushed via a squashed root commit (`0905008`), obliterating local scratch commit IDs. From this point forward, strict verifiable linear Git history is maintained with one commit per defect/milestone.  

---

## 1. Master Audit Ledger (V-01 through V-32)

| ID | Severity | Category | Finding Summary | Repro Status | Remediation | Evidence File | Commit |
|---|---|---|---|---|---|---|---|
| **V-01** | `BLOCKER` | SECURITY | Credentials in the bundle (.env unredacted in generate_repo_bundle.py) | **CONFIRMED** | **FIXED** | [`evidence/2026-09-20/V-01_history_clean_git_log.txt`](evidence/2026-09-20/V-01_history_clean_git_log.txt) | `dfc69b4` |
| **V-02** | `BLOCKER` | ENVIRONMENT | Python 3.12 compatibility failure due to missing Optional / annotations | **CONFIRMED** | **FIXED** | [`evidence/2026-09-20/V-02_py312_pyflakes_fixed.txt`](evidence/2026-09-20/V-02_py312_pyflakes_fixed.txt) | `02e8195` |
| **V-03** | `MAJOR` | ENVIRONMENT | Reproducibility evidence not real (global pip freeze and local clone test) | **CONFIRMED** | **FIXED** | [`evidence/2026-09-20/clean_clone_clean_clone.txt`](evidence/2026-09-20/clean_clone_clean_clone.txt) | `e3e17c9` |
| **V-04** | `MINOR` | TESTING | Test inventory misreported across historical reports | **CONFIRMED** | **FIXED** | [`evidence/2026-09-20/clean_clone_clean_clone.txt`](evidence/2026-09-20/clean_clone_clean_clone.txt) | `e3e17c9` |
| **V-05** | `BLOCKER` | ENGINE | Two engines; legacy ArcusEventBacktester violates fill monotonicity | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-05_legacy_not_monotone.txt`](evidence/2026-09-20/V-05_legacy_not_monotone.txt) | - |
| **V-06** | `BLOCKER` | ENGINE | SimEngine crashes on first L2 event (calls non-existent handle_snapshot / handle_l2_update) | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt`](evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt) | - |
| **V-07** | `BLOCKER` | ENGINE | Queue position ignores L2 depth (queue_ahead_size is 0.0 behind the touch) | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt`](evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt) | - |
| **V-08** | `BLOCKER` | ENGINE | Funding charged on every message (60x overcharge) and TimeAwareFundingModel unused | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-08_funding_overcharge.txt`](evidence/2026-09-20/V-08_funding_overcharge.txt) | - |
| **V-09** | `BLOCKER` | RISK | Risk manager never recovers from PAUSED_STALE_FEED or PAUSED_GAP | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt`](evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt) | - |
| **V-10** | `MAJOR` | EXECUTION | Rate limits recorded but never enforced before order actions | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt`](evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt) | - |
| **V-11** | `MAJOR` | LATENCY | Latency is constant jitter rather than empirical distribution sampling | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-11_no_empirical_latency_loader.txt`](evidence/2026-09-20/V-11_no_empirical_latency_loader.txt) | - |
| **V-12** | `MAJOR` | ENGINE | Three fill model worlds not independent (Model C quotes keyed to Model B inventory) | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt`](evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt) | - |
| **V-13** | `BLOCKER` | RESEARCH | Machine-enforced gates not pre-registered criteria (no bootstrap) | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-25_no_bootstrap_walk_forward.txt`](evidence/2026-09-20/V-25_no_bootstrap_walk_forward.txt) | - |
| **V-14** | `MAJOR` | EXECUTION | Missing venue mechanics (mark price PnL mark, margin liquidation checks, off-hours bands) | **CONFIRMED** | **OPEN** | - | - |
| **V-15** | `BLOCKER` | PAPER | Dynamic metadata never loads due to operator precedence bug in paper trader | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-15_paper_trader_metadata_loader.txt`](evidence/2026-09-20/V-15_paper_trader_metadata_loader.txt) | - |
| **V-16** | `MAJOR` | PAPER | Pause logic starves engine during OPEN_30 / CLOSE_30 pauses | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt`](evidence/2026-09-20/V-06_V-07_V-09_risk_l2_queue.txt) | - |
| **V-17** | `BLOCKER` | PARITY | Replay parity PASS is vacuous (empty fill hash comparison on 0 fills) | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-17_empty_hash_parity.txt`](evidence/2026-09-20/V-17_empty_hash_parity.txt) | - |
| **V-18** | `BLOCKER` | RECORDER | Running recorder PID 11661 runs old code without socket rotation | **CONFIRMED** | **OPEN** | - | - |
| **V-19** | `MAJOR` | DATA | Trade reconciliation mis-reported (NEAR-USD missing trade IDs) | **CONFIRMED** | **OPEN** | - | - |
| **V-20** | `MAJOR` | DATA | Trade-side semantics unresolved, not proven | **CONFIRMED** | **OPEN** | - | - |
| **V-21** | `MINOR` | DATA | Sequence-field evidence incomplete (lacks raw L2 delta frame) | **CONFIRMED** | **OPEN** | - | - |
| **V-22** | `MAJOR` | DATA | Storage and provenance not automated (no scheduled compression or static manifests) | **CONFIRMED** | **OPEN** | - | - |
| **V-23** | `MINOR` | DATA | Two clocks recorded, only local clock used in simulation | **CONFIRMED** | **OPEN** | - | - |
| **V-24** | `BLOCKER` | RESEARCH | The pilot analysis is invalid (event truncation, heuristic spread sigma, synthetic multipliers) | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-24_pilot_analysis_bugs.txt`](evidence/2026-09-20/V-24_pilot_analysis_bugs.txt) | - |
| **V-25** | `BLOCKER` | RESEARCH | Power analysis is statistically wrong (n formula gives 50% power, ignores clustering) | **CONFIRMED** | **OPEN** | [`evidence/2026-09-20/V-25_no_bootstrap_walk_forward.txt`](evidence/2026-09-20/V-25_no_bootstrap_walk_forward.txt) | - |
| **V-26** | `MAJOR` | RESEARCH | Pre-registration v3 is not ready to lock | **CONFIRMED** | **OPEN** | - | - |
| **V-27** | `MAJOR` | LATENCY | Latency evidence far below spec (5 samples in 4 seconds on REST) | **CONFIRMED** | **OPEN** | - | - |
| **V-28** | `MAJOR` | DOCS | followup_gate_report.md overclaims ready for accumulation with broken criteria | **CONFIRMED** | **OPEN** | - | - |
| **V-29** | `MAJOR` | DOCS | Ledger status column was handwritten rather than machine-attested | **CONFIRMED** | **OPEN** | - | - |
| **V-30** | `MAJOR` | DOCS | verify_report.py cannot catch fabricated generator data or invalid claims | **CONFIRMED** | **OPEN** | - | - |
| **V-31** | `MINOR` | DOCS | Time labels are unreliable (IST labeled as UTC in reports) | **CONFIRMED** | **OPEN** | - | - |
| **V-32** | `MINOR` | DOCS | Repo clutter and duplicates (~70 stale/duplicate files) | **CONFIRMED** | **OPEN** | - | - |

---

## 2. Machine Reference Integrity Verification

All referenced evidence and test suites are machine-validated to exist on disk:
- ✅ **All linked evidence files exist and are verified on disk.**
- ✅ **All referenced test suites exist and are verified in `tests/`.**

---

## 3. Progress Metrics

- **Total Findings Audited:** 32
- **Confirmed Defects:** 32
- **Refuted Defects:** 0
- **Remediated (FIXED):** 4
- **In Progress:** 0
- **Open:** 28

