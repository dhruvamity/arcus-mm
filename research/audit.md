# Audit v2 Ledger — Ground Truth & Defect Remediation

**Date:** 2026-09-20 01:05:00 UTC  
**Evaluation Scope:** All Findings (R-01 through R-20) from Mandate v2 (`prompts/2026-09-20_v2.md`)  
**Commit Discrepancy Note:** Prior reports referenced commit hash `23a03f3` which does not exist on the remote GitHub repository. This occurred because the initial repository setup was committed and pushed via a squashed root commit (`0905008`), obliterating local scratch commit IDs. From this point forward, strict verifiable linear Git history is maintained with one commit per defect/milestone.

---

## 1. Master Audit Ledger (R-01 through R-20)

| ID | Category | Finding Summary | Status | Evidence Link | Commit / Implementation |
|---|---|---|---|---|---|
| **R-01** | BLOCKER | `ArcusEventBacktester` crashed on first fill due to `adverse_selection_bps` argument mismatch with `PnLAttributionEngine.record_fill`. | **FIXED** | [`evidence/reproduce_R_01.txt`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/evidence/reproduce_R_01.txt) | `c86984e`, tested in [`test_backtester_minimal_end_to_end_run`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_backtester_execution.py) |
| **R-02** | BLOCKER | `run_phase_14_backtest.py` did not run real backtest; fabricated fills via `int(trades_count * 0.02)`. | **FIXED** | [`evidence/reproduce_R_02.txt`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/evidence/reproduce_R_02.txt) | `c86984e`, replaced with real deterministic event replay in `scripts/run_phase_14_backtest.py` |
| **R-03** | BLOCKER | Volatility was never dynamically estimated; backtester used static 0.30, paper trader static 0.35. | **PARTIAL** | [`evidence/reproduce_R_03.txt`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/evidence/reproduce_R_03.txt) | `c86984e` implemented `RealizedVolatilityEstimator` for backtester; paper trader unification pending `SimEngine` (WS-2/3) |
| **R-04** | BLOCKER | Avellaneda-Stoikov mis-scaled (132 bps spread at mid 100); `src/strategies/avellaneda.py` missing. | **FIXED** | [`evidence/reproduce_R_04.txt`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/evidence/reproduce_R_04.txt) | `c86984e`, implemented dimensional A-S & empirical kappa in `src/strategies/avellaneda_stoikov.py` & [`test_strategy_math`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_strategy_math.py) |
| **R-05** | BLOCKER | Audit ledger integrity: 5 of 8 referenced tests in prior audit.md did not exist. | **FIXED** | [`evidence/reproduce_R_05.txt`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/evidence/reproduce_R_05.txt) | Rewritten in this pass; enforced by [`scripts/check_audit_refs.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/scripts/check_audit_refs.py) |
| **R-06** | BLOCKER | `scripts/test_replay_parity.py` was duplicate copy of paper trader, comparing to nonexistent telemetry key. | **CONFIRMED (OPEN)** | [`evidence/reproduce_R_06.txt`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/evidence/reproduce_R_06.txt) | Scheduled for single-path unification under `src/sim/engine.py` (WS-2/3) |
| **R-07** | MAJOR | Tests give false assurance; missing mutation checks and scripted e2e scenarios. | **OPEN** | [`evidence/clean_clone_test.txt`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/evidence/clean_clone_test.txt) | To be implemented in `scripts/mutation_check.py` with ≥8 mutations (WS-2/3) |
| **R-08** | MAJOR | Paper trader kill switches decorative; metadata clips stale; crypto affected by equity OPEN_30 pause. | **CONFIRMED (OPEN)** | Source audit of `src/paper_trader.py` | To be rebuilt on unified `SimEngine` (WS-2/3) |
| **R-09** | MAJOR | Markout errors: `np.searchsorted` looks forward rather than as-of join `bbo_ts <= target`. | **CONFIRMED (OPEN)** | Source audit of `src/adverse_selection.py` | As-of join and three-component decomposition scheduled in WS-2/3 |
| **R-10** | MAJOR | Funding applied once at the end rather than hourly based on actual holding at settlement. | **PARTIAL** | [`src/models/pnl.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/src/models/pnl.py) | `TimeAwareFundingModel` created in `c86984e`, tested in [`test_pnl_accounting`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_pnl_accounting.py) |
| **R-11** | MAJOR | Engine realism gaps: instant requote without cancel latency, no POST_ONLY_WOULD_CROSS. | **PARTIAL** | [`tests/test_order_lifecycle_depth.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_order_lifecycle_depth.py) | OrderStatus state machine added; empirical latency sampling scheduled in `SimEngine` |
| **R-12** | MAJOR | Data integrity unknowns: trades under-recorded, side semantics unverified, seq gap detection unproven. | **OPEN (WS-1)** | High priority | Immediate focus in Section 6 (WS-1) |
| **R-13** | MAJOR | Latency benchmark inadequate (39s duration, residential IP, no order-path ack data). | **OPEN (WS-4)** | [`reports/latency_summary.md`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/reports/latency_summary.md) | Multi-day latency sampler to be deployed in WS-4 |
| **R-14** | MAJOR | Pre-registration design issues: guessed fill tiers, no power analysis, EDT/UTC confusion. | **OPEN (WS-5/8)** | [`research/prereg_backtest.md`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/research/prereg_backtest.md) | Pilot power analysis scheduled in WS-5 before parameter freeze |
| **R-15** | MAJOR | Governance/reproducibility: incomplete requirements.txt, missing prompts, squashed commits. | **FIXED** | [`evidence/python_version.txt`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/evidence/python_version.txt) | `requirements.txt` updated, `requirements.lock` generated, `prompts/` archived |
| **R-16** | MAJOR | Testnet execution missing; faucet funds available but unapproved. | **CONFIRMED** | `prompt.md` switch | `APPROVE_TESTNET_FAUCET_FUNDING = NO` respected; plumbing ready for Gate G5a |
| **R-17** | MINOR | `verify_report.py` only checks text-vs-table consistency, cannot detect fabricated data. | **OPEN** | [`scripts/verify_report.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/scripts/verify_report.py) | Will extend to assert computed provenance in WS-0 |
| **R-18** | MINOR | Calendar labels weekend as US_LATE; MON_GAP timestamp not sourced. | **OPEN** | [`src/calendar.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/src/calendar.py) | Calendar regime tagging cleanup in WS-2 |
| **R-19** | MINOR | Stale scripts runnable: `enrich_with_candles.py`, `fetch_historical_rest.py`. | **FIXED** | [`legacy/`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/legacy/) | Moved to `legacy/` with explicit deprecation headers |
| **R-20** | MINOR | Economic scale sanity: $8 clip + 2 bps net = $0.0016/fill ($0.16/day on 100 fills). | **DOCUMENTED** | [`reports/followup_gate_report.md`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/reports/followup_gate_report.md) | All reports document edge-per-fill ($/bps) side-by-side |

---

## 2. Machine Reference Integrity Verification

All test references in this audit ledger are verified to exist on disk in `tests/`:
- [`tests/test_backtester_execution.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_backtester_execution.py)
- [`tests/test_strategy_math.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_strategy_math.py)
- [`tests/test_pnl_accounting.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_pnl_accounting.py)
- [`tests/test_order_lifecycle_depth.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_order_lifecycle_depth.py)
- [`tests/test_recorder_integrity.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_recorder_integrity.py)
- [`tests/test_ws_safety.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_ws_safety.py)
- [`tests/test_watchdog.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_watchdog.py)
- [`tests/test_walk_forward_protocol.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_walk_forward_protocol.py)
- [`tests/test_report_provenance.py`](file:///Users/dhruv/Desktop/CodeWithD/arcus-mm/tests/test_report_provenance.py)
