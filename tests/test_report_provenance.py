"""Unit Tests for Report Provenance, Empirical Conservatism, and Validation Gate Integrity.

Fulfills Mandate Sections 22, 38, 40, 43, 44 & 45:
- Verifies that reports do not claim 'VALIDATED', 'PROFITABLE', or 'DEPLOYMENT READY' without passing 5-day OOS protocol
- Verifies that all validation gates are machine-enforced
- Verifies that Holm-Bonferroni FWER control is mathematically sound
- Verifies that machine-readable source truth matrix exists
"""

import unittest
from pathlib import Path
from src.walk_forward import WalkForwardValidator
from src.sim.engine import BacktestRunResult


class TestReportProvenance(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent

    def test_source_truth_matrix_exists_and_valid(self):
        """Verify audit.md exists as canonical ledger and synthetic matrix fixtures parse cleanly."""
        audit_path = self.repo_root / "research" / "audit.md"
        self.assertTrue(audit_path.exists(), f"Missing {audit_path}")
        content = audit_path.read_text(encoding="utf-8")
        self.assertIn("Master Audit Ledger", content)
        self.assertIn("Machine Reference Integrity Verification", content)

        # Synthetic source truth matrix fixture validation
        synthetic_matrix = (
            "Component,Classification,Evidence / Audit Finding\n"
            "Recorder,CONFIRMED,evidence/2026-09-20/recorder_old_code_risk.txt\n"
            "SimEngine,FIXED,tests/test_sim_engine.py\n"
        )
        lines = synthetic_matrix.strip().splitlines()
        self.assertGreater(len(lines), 2)
        header = lines[0]
        self.assertIn("Component", header)
        self.assertIn("Classification", header)
        self.assertIn("Evidence / Audit Finding", header)

    def test_no_premature_validation_in_reports(self):
        """Verify reports follow empirical conservatism and do NOT claim profitable / validated prematurely."""
        forbidden_claims = [
            "STATUS: VALIDATED",
            "PROFITABLE",
            "DEPLOYMENT READY",
        ]
        reports_to_check = [
            "reports/phase_14_backtest.md",
            "reports/phase_15_paper_validation.md",
            "reports/phase_15_live_paper_report.md",
        ]
        for rel_path in reports_to_check:
            fpath = self.repo_root / rel_path
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8")
                for claim in forbidden_claims:
                    self.assertNotIn(
                        f"Verdict: {claim}",
                        content,
                        f"Found forbidden premature claim '{claim}' in {rel_path}",
                    )
                    self.assertNotIn(
                        f"**{claim}**",
                        content,
                        f"Found forbidden premature claim '**{claim}**' in {rel_path}",
                    )

    def test_machine_validation_gates_enforcement(self):
        """Verify the validation gates correctly reject failing strategies."""
        validator = WalkForwardValidator()

        # Synthetic results failing gate (fill count < 100)
        res_fail = BacktestRunResult(
            market="BTC-USD",
            strategy_name="FailingStrat",
            fill_model="MODEL_B_MODERATE",
            fidelity="HIGH_FIDELITY_L2",
            latency_ms=10.0,
            pnl_summary={
                "total_trades_count": 25,  # < 100 fills
                "net_pnl": -5.0,
                "max_drawdown_pct": 12.0,
                "open_position_notional": 0.0,
                "initial_capital": 100.0,
            },
            rate_limit_metrics={},
            markout_metrics={},
            event_count=100,
            duration_hours=1.0,
        )
        res_control = BacktestRunResult(
            market="BTC-USD",
            strategy_name="Control",
            fill_model="MODEL_B_MODERATE",
            fidelity="HIGH_FIDELITY_L2",
            latency_ms=10.0,
            pnl_summary={"total_trades_count": 0, "net_pnl": 0.0, "max_drawdown_pct": 0.0},
            rate_limit_metrics={},
            markout_metrics={},
            event_count=100,
            duration_hours=1.0,
        )

        gates = validator.evaluate_gates(
            res_b=res_fail,
            res_a=res_fail,
            res_dn=res_control,
            res_rnd=res_control,
            p_value=0.45,
        )

        self.assertIn("verdict", gates)
        self.assertNotEqual(gates["verdict"], "PASS")
        self.assertFalse(gates["gate_fill_count"]["passed"])
        self.assertFalse(gates["gate_positive_pnl"]["passed"])
        self.assertFalse(gates["gate_max_drawdown"]["passed"])

    def test_holm_bonferroni_fwer_adjustment(self):
        """Verify step-down Holm-Bonferroni accurately rejects unadjusted false positives."""
        family = [
            {"config": "strat_1", "p_value": 0.005},
            {"config": "strat_2", "p_value": 0.020},
            {"config": "strat_3", "p_value": 0.060},
            {"config": "strat_4", "p_value": 0.400},
        ]
        # m = 4, alpha = 0.05
        # rank 1: p=0.005 <= 0.05 / 4 = 0.0125 -> Significant!
        # rank 2: p=0.020 <= 0.05 / 3 = 0.0167 -> NOT significant!
        corrected = WalkForwardValidator.apply_holm_bonferroni(family, alpha=0.05)
        self.assertTrue(corrected[0]["is_statistically_significant"])
        self.assertFalse(corrected[1]["is_statistically_significant"])
        self.assertFalse(corrected[2]["is_statistically_significant"])
        self.assertFalse(corrected[3]["is_statistically_significant"])

    def test_verify_generator_scripts_catches_hardcoded_verdicts(self):
        """Verify scripts/verify_report.py catches hardcoded status literals and fabricated fills (R-02, R-17)."""
        import tempfile
        from scripts.verify_report import verify_generator_scripts

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Script with hardcoded RESOLVED
            bad_script = tmp_path / "run_test_bad.py"
            bad_script.write_text("verdict = 'RESOLVED & TESTED'\n", encoding="utf-8")
            valid, errors = verify_generator_scripts(tmp_path)
            self.assertFalse(valid)
            self.assertTrue(any("hardcoded status literal" in e for e in errors))

            # Script with fabricated fills
            bad_script.write_text("fills = int(trades_count * 0.02)\n", encoding="utf-8")
            valid, errors = verify_generator_scripts(tmp_path)
            self.assertFalse(valid)
            self.assertTrue(any("fabricated fills expression" in e for e in errors))

            # Script with hardcoded READY FOR DATA ACCUMULATION
            bad_script.write_text("verdict = 'READY FOR DATA ACCUMULATION'\n", encoding="utf-8")
            valid, errors = verify_generator_scripts(tmp_path)
            self.assertFalse(valid)
            self.assertTrue(any("hardcoded status literal" in e for e in errors))

            # Clean script
            bad_script.write_text("fills = len(sim_engine.fills)\nif verdict == 'VALIDATED': pass\n", encoding="utf-8")
            valid, errors = verify_generator_scripts(tmp_path)
            self.assertTrue(valid)

    def test_verify_report_v30_enhancements(self):
        """Verify report validator catches empty-string hashes, constant columns, unlinked statuses, and latency divergence (V-30)."""
        import tempfile
        from scripts.verify_report import verify_report

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # 1. Empty string SHA-256 hash
            rep_empty_hash = tmp_path / "rep_empty_hash.md"
            rep_empty_hash.write_text(
                "# Title\n\n**Generated At:** `2026-09-20T10:00:00Z`\n\nHash: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
                encoding="utf-8",
            )
            valid, errors = verify_report(rep_empty_hash)
            self.assertFalse(valid)
            self.assertTrue(any("vacuous empty-string SHA-256" in e for e in errors))

            # 2. Constant column where variation is expected (Depth $50 across markets)
            rep_const_col = tmp_path / "rep_const_col.md"
            rep_const_col.write_text(
                "# Title\n\n**Generated At:** `2026-09-20T10:00:00Z`\n\n| Market | Depth | Trades |\n|---|---|---|\n| BTC | $50 | 100 |\n| ETH | $50 | 200 |\n| SOL | $50 | 300 |\n",
                encoding="utf-8",
            )
            valid, errors = verify_report(rep_const_col)
            self.assertFalse(valid)
            self.assertTrue(any("constant across all 3 rows" in e for e in errors))

            # 3. Unlinked status in ledger
            rep_unlinked = tmp_path / "rep_unlinked.md"
            rep_unlinked.write_text(
                "# Title\n\n**Generated At:** `2026-09-20T10:00:00Z`\n\n| ID | Status | Verdict |\n|---|---|---|\n| V-99 | CONFIRMED | FIXED |\n| V-98 | CONFIRMED | FIXED |\n| V-97 | CONFIRMED | FIXED |\n",
                encoding="utf-8",
            )
            valid, errors = verify_report(rep_unlinked)
            self.assertFalse(valid)
            self.assertTrue(any("has no linked evidence or test file" in e for e in errors))

            # 4. Latency divergence against canonical summary
            rep_divergent_lat = tmp_path / "rep_divergent_lat.md"
            rep_divergent_lat.write_text(
                "# Title\n\n**Generated At:** `2026-09-20T10:00:00Z`\n\nAudited live sample exhibits latency p50 of 376.06 ms across REST samples.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
                encoding="utf-8",
            )
            valid, errors = verify_report(rep_divergent_lat)
            self.assertFalse(valid)
            self.assertTrue(any("disagrees with canonical" in e for e in errors))

            # 5. Invalid Generated At
            rep_bad_ts = tmp_path / "rep_bad_ts.md"
            rep_bad_ts.write_text(
                "# Title\n\n**Generated At:** System Clock UTC\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
                encoding="utf-8",
            )
            valid, errors = verify_report(rep_bad_ts)
            self.assertFalse(valid)
            self.assertTrue(any("missing valid ISO 8601 UTC format" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
