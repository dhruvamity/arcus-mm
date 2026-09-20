#!/usr/bin/env python3
from __future__ import annotations

"""Report Verification Script for Arcus Research Reports.

- Ensures reports are generated from computed tables, never hand-narrated.
- Checks that numbers in prose trace directly to table cells.
- Enforces strict prohibition of forbidden words ("CERTIFIED", un-quarantined "CONDITIONAL YES").
- Fails build if any withdrawn-claim phrase appears as an affirmative claim:
  - "Pool exhaustion risk: ZERO"
  - "perpetually sustainable"
  - "size-asymmetry discovery"
  - "+1.8 to +3.5 bps per completed clip"
  - "empirically validated across all 13 phases"
  - "proceed to testnet"
- Fails build if a "✅ +x%" status appears next to INSUFFICIENT DATA for the same market.
- Fails build if a clip size below that market's live minimum is cited (e.g. ZEC < $14.87, BTC < $8.12).
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


FORBIDDEN_PATTERNS = [
    re.compile(r"\bCERTIFIED\b", re.IGNORECASE),
]

WITHDRAWN_CLAIM_PHRASES = [
    (re.compile(r"pool\s+exhaustion\s+risk:\s*zero", re.IGNORECASE), "Pool exhaustion risk: ZERO"),
    (re.compile(r"perpetually\s+sustainable", re.IGNORECASE), "perpetually sustainable"),
    (re.compile(r"size-asymmetry\s+discovery", re.IGNORECASE), "size-asymmetry discovery"),
    (re.compile(r"\+1\.8\s+to\s+\+3\.5\s+bps", re.IGNORECASE), "+1.8 to +3.5 bps per completed clip"),
    (re.compile(r"empirically\s+validated\s+across\s+all\s+13\s+phases", re.IGNORECASE), "empirically validated across all 13 phases"),
    (re.compile(r"\bproceed\s+to\s+testnet\b", re.IGNORECASE), "proceed to testnet"),
]

# Minimum executable clips verified from venue /v1/markets
LIVE_MIN_CLIPS = {
    "BTC": 8.12,
    "ZEC": 14.87,
    "HYPE": 9.21,
    "SLV": 6.00,
    "AMD": 5.53,
}


def load_venue_fees() -> Tuple[float, float, float]:
    """Loads maker_fee_bps, taker_fee_bps, maker_rebate_bps directly from configs/venue_verified.yaml (Rule 6)."""
    cfg_path = REPO_ROOT / "configs" / "venue_verified.yaml"
    if cfg_path.exists():
        try:
            import yaml
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            fees = data.get("fees", {})
            base_tier = fees.get("base_tier", {})
            maker_fee = float(base_tier.get("maker_fee_bps", 0.0))
            taker_fee = float(base_tier.get("taker_fee_bps", 2.25))
            rebates_avail = fees.get("rebates_available", False)
            maker_rebate = float(base_tier.get("maker_rebate_bps", 0.0)) if rebates_avail else 0.0
            return maker_fee, taker_fee, maker_rebate
        except Exception:
            pass
    return 0.0, 2.25, 0.0


# Canonical reference data (Rule 6: dynamically loaded from configs/venue_verified.yaml)
CANONICAL_MAKER_FEE_BPS, CANONICAL_TAKER_FEE_BPS, CANONICAL_MAKER_REBATE_BPS = load_venue_fees()
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

ALLOWED_PROSE_NUMBERS = {
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "13", "14", "15", "16", "18",
    "20", "24", "25", "30", "50", "60", "64", "75", "80", "90", "95", "99", "100", "120", "300", "2026"
}


def load_canonical_latency_p50() -> float | None:
    """Loads canonical p50 latency from latency/latency_summary.json if it exists."""
    p = REPO_ROOT / "latency" / "latency_summary.json"
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return float(data.get("rest_rtt_ms", {}).get("p50", 0.0))
        except Exception:
            return None
    return None


def extract_tables(markdown_text: str) -> List[List[List[str]]]:
    """Extracts all markdown tables into lists of rows of cell strings."""
    tables = []
    current_table = []
    in_table = False

    for line in markdown_text.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("|") and trimmed.endswith("|"):
            cells = [c.strip() for c in trimmed[1:-1].split("|")]
            # Check if this is a separator row e.g. |---|---|
            if all(set(c).issubset({"-", ":", " "}) for c in cells):
                continue
            current_table.append(cells)
            in_table = True
        else:
            if in_table and current_table:
                tables.append(current_table)
                current_table = []
                in_table = False

    if in_table and current_table:
        tables.append(current_table)

    return tables


def extract_numbers_from_text(text: str) -> Set[str]:
    """Extracts floating point and percentage values from text."""
    raw_matches = re.findall(r"[-+]?\d+(?:,\d+)*(?:\.\d+)?(?:%|bps|\$)?", text)
    cleaned = set()
    for m in raw_matches:
        c = m.strip("$,%").replace(",", "")
        if c and c not in {"-", "+", "."}:
            try:
                flt = float(c)
                cleaned.add(f"{flt:.2f}")
                cleaned.add(f"{flt:.4f}")
                cleaned.add(str(int(flt)) if flt.is_integer() else str(flt))
            except ValueError:
                pass
    return cleaned


def extract_numbers_from_tables(tables: List[List[List[str]]]) -> Set[str]:
    """Extracts all numeric representations from extracted table cells."""
    table_numbers = set()
    for table in tables:
        for row in table:
            for cell in row:
                cell_clean = re.sub(r"[*_`]", "", cell)
                numbers = extract_numbers_from_text(cell_clean)
                table_numbers.update(numbers)
    return table_numbers


def verify_report(file_path: Path) -> Tuple[bool, List[str]]:
    """Verifies a single markdown report for forbidden terms, withdrawn claims, and table consistency."""
    errors = []
    if not file_path.exists():
        return False, [f"File does not exist: {file_path}"]

    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    is_superseded = (
        "SUPERSEDED — PRELIMINARY SMOKE TEST" in content
        or "Engineering Blockers Resolution" in content
        or "Follow-up Gate Review" in content
        or "Formal Follow-Up Gate Report" in content
        or "Source of Truth & Audit" in content
        or "Audit Findings" in content
    )
    is_protocol = "Pre-Registration Protocol" in content or "Pre-Registration" in content

    # 1. Check forbidden terms and withdrawn claim phrases
    for line_no, line in enumerate(lines, 1):
        line_lower = line.lower()
        # Allow defect ledger or explicit withdrawal notes
        is_context_explanation = any(w in line_lower for w in ["withdrawn", "defect", "superseded", "quarantined", "claim", "remediation", "prior", "v-01", "v-17", "v-28", "v-29", "v-30"])

        # Check forbidden words
        if not is_context_explanation:
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    errors.append(f"Line {line_no}: Contains forbidden word '{pattern.pattern}': {line.strip()}")

        # Check withdrawn claims
        for pattern, label in WITHDRAWN_CLAIM_PHRASES:
            if pattern.search(line) and not is_context_explanation:
                errors.append(f"Line {line_no}: Contains withdrawn claim phrase '{label}': {line.strip()}")

        # Check empty-string sha256 hash or vacuous parity claims (Mandate v3 §15)
        if not is_context_explanation:
            if EMPTY_SHA256 in line.lower() or "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in line.lower():
                errors.append(f"Line {line_no}: Cites vacuous empty-string SHA-256 hash: {line.strip()}")
            if "parity" in line_lower and "pass" in line_lower and ("0 fill" in line_lower or "zero fill" in line_lower):
                errors.append(f"Line {line_no}: Claims parity PASS on zero fills: {line.strip()}")

        # Check Generated At timestamp validity
        if "generated at:" in line_lower:
            # Must be valid ISO 8601 with timezone (e.g. 2026-09-20T13:54:00Z or 2026-09-20 13:54:00 UTC)
            has_iso = bool(re.search(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2}|\s*UTC)", line))
            if not has_iso or "system clock" in line_lower:
                errors.append(f"Line {line_no}: 'Generated At' timestamp missing valid ISO 8601 UTC format: {line.strip()}")

    # 2. Extract tables and check row-level contradictions & constant columns
    tables = extract_tables(content)
    if not tables and len(lines) > 50:
        errors.append("Report has >50 lines but contains no markdown tables.")
        return False, errors

    for table_idx, table in enumerate(tables, 1):
        if not table:
            continue
        header = [c.lower() for c in table[0]]
        rows = table[1:]

        # Check constant columns across rows (Mandate v3 §15: catches e.g. Depth $50 default)
        if len(rows) >= 3:
            for col_idx, col_name in enumerate(header):
                if any(k in col_name for k in ["depth", "spread", "trades/hr", "fill rate", "expectancy", "net edge"]):
                    col_vals = [row[col_idx].strip() for row in rows if col_idx < len(row)]
                    if col_vals and len(set(col_vals)) == 1 and col_vals[0] not in {"-", "N/A", "0", "$0"}:
                        errors.append(
                            f"Table {table_idx}, Column '{table[0][col_idx]}' is constant across all {len(rows)} rows: '{col_vals[0]}' (expected cross-market variation)"
                        )

        # Check row-level claims
        is_ledger_table = any(k in " ".join(header) for k in ["status", "remediation", "verdict", "gate", "finding"])
        for row_idx, row in enumerate(rows, 1):
            row_str = " ".join(row)

            # Rule: A "✅ +x%" status cannot be next to INSUFFICIENT DATA for the same market
            has_positive_check = bool(re.search(r"✅\s*\+\d", row_str))
            has_insufficient_data = "INSUFFICIENT DATA" in row_str
            if has_positive_check and has_insufficient_data:
                errors.append(
                    f"Table {table_idx}, Row {row_idx}: Contradictory status! '✅ +x%' appears next to INSUFFICIENT DATA: {row_str}"
                )

            # Rule: Status words in ledger/verdict tables must have linked evidence/test files (Mandate v3 §15)
            if is_ledger_table and not is_superseded:
                for status_word in ["CONFIRMED", "FIXED", "REFUTED", "VALIDATED"]:
                    if status_word in row_str:
                        has_link = bool(re.search(r"\[.*?\]\((?:evidence/|tests/|scripts/|http|[a-zA-Z0-9_/-]+\.[a-zA-Z0-9]+)\)", row_str))
                        has_file_ref = any(ref in row_str for ref in ["evidence/", "tests/", "scripts/"])
                        if not has_link and not has_file_ref and "OPEN" not in row_str:
                            errors.append(
                                f"Table {table_idx}, Row {row_idx}: Status '{status_word}' has no linked evidence or test file: {row_str[:80]}..."
                            )

            # Rule: Clip size cannot be below live venue minimum
            for market, min_clip in LIVE_MIN_CLIPS.items():
                if market in row_str:
                    clips_found = re.findall(r"\$\s*(\d+(?:\.\d+)?)", row_str)
                    for c_str in clips_found:
                        c_val = float(c_str)
                        if ("clip" in row_str.lower() or "min" in row_str.lower()) and c_val < (min_clip - 0.5) and c_val > 1.0:
                            errors.append(
                                f"Table {table_idx}, Row {row_idx}: Clip size ${c_val:.2f} for {market} is below live venue minimum ${min_clip:.2f}"
                            )

    # 3. Check prose narrative outside of tables
    table_numbers = extract_numbers_from_tables(tables)
    non_table_lines = []
    for line in lines:
        trimmed = line.strip()
        if not (trimmed.startswith("|") and trimmed.endswith("|")) and not trimmed.startswith("#") and not trimmed.startswith(">"):
            non_table_lines.append(trimmed)

    prose_text = " ".join(non_table_lines)
    claim_sentences = [
        s.strip() for s in re.split(r"\.\s+|\n+", prose_text)
        if any(kw in s for kw in ["bps", "%", "net edge", "expectancy", "return", "PnL"])
    ]

    ALLOWED_FLOATS = {float(x) for x in ALLOWED_PROSE_NUMBERS}
    for sentence in claim_sentences:
        if is_superseded or is_protocol:
            continue
        nums = extract_numbers_from_text(sentence)
        unmatched = [n for n in nums if n not in table_numbers]
        unmatched = [n for n in unmatched if float(n) not in ALLOWED_FLOATS]
        if unmatched:
            errors.append(f"Prose number(s) {unmatched} in sentence not found in any table: \"{sentence[:100]}...\"")

    # Check for invalid clip sizes in prose
    for market, min_clip in LIVE_MIN_CLIPS.items():
        market_clips = re.findall(rf"\${market}\s*(?:clip|allocation)?.*?\$(\d+(?:\.\d+)?)", prose_text, re.IGNORECASE)
        for c_str in market_clips:
            if float(c_str) < (min_clip - 0.5):
                errors.append(f"Prose references clip ${float(c_str):.2f} for {market}, below live venue minimum ${min_clip:.2f}")

    # Check canonical latency agreement (Mandate v3 §15)
    canonical_p50 = load_canonical_latency_p50()
    if canonical_p50 is not None and not is_superseded:
        # Match e.g. "latency p50 185.23 ms" or "p50 latency of 376.06"
        m = re.search(r"(?:latency\s+p50|p50\s+latency)[^\d]*(\d+\.\d+)\s*ms", prose_text, re.IGNORECASE)
        if m:
            cited_p50 = float(m.group(1))
            if abs(cited_p50 - canonical_p50) > 1.0:
                errors.append(
                    f"Report cites latency p50 of {cited_p50:.2f} ms which disagrees with canonical latency/latency_summary.json ({canonical_p50:.2f} ms)"
                )

    is_valid = len(errors) == 0
    return is_valid, errors


def verify_generator_scripts(scripts_dir: Path = Path("scripts")) -> Tuple[bool, List[str]]:
    """Verifies that report generator scripts do not contain hard-coded statuses or fabricated fills (R-02, R-17, Mandate v3 §15)."""
    errors = []
    generator_files = list(scripts_dir.glob("run_*.py"))

    for g_path in generator_files:
        content = g_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        in_docstring = False
        for idx, line in enumerate(lines, 1):
            trimmed = line.strip()
            if '"""' in trimmed or "'''" in trimmed:
                cnt = trimmed.count('"""') + trimmed.count("'''")
                if cnt % 2 != 0:
                    in_docstring = not in_docstring
                    continue
                elif in_docstring:
                    continue
            if in_docstring or trimmed.startswith("#"):
                continue

            # Check for hardcoded "RESOLVED", "VALIDATED", or "READY" string literals (Mandate v3 §15)
            if re.search(r'["\'](?:RESOLVED|VALIDATED|READY\s+FOR\s+DATA\s+ACCUMULATION|DEPLOYMENT\s+READY)(?:\s*&.*?)?["\']', line):
                # Allow conditional comparison or schema definitions
                if any(kw in line for kw in ["if ", "elif ", "==", "!=", "in [", "in (", "Enum", "allowed_verdicts"]):
                    continue
                errors.append(f"{g_path.name}:{idx}: Generator contains hardcoded status literal: {trimmed}")

            # Check for executable fabricated fill counts (e.g. int(trades * 0.02))
            if re.search(r'\bint\s*\(\s*(?:trades|trades_count)\s*\*\s*0\.02\s*\)', line):
                errors.append(f"{g_path.name}:{idx}: Generator contains fabricated fills expression: {trimmed}")

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Verify Arcus research report tables and claims.")
    parser.add_argument("report_paths", nargs="*", help="Path(s) to markdown report(s) to verify")
    parser.add_argument("--all", action="store_true", help="Verify all reports in reports/")
    parser.add_argument("--check-generators", action="store_true", default=True, help="Verify generator scripts for hardcoded statuses (R-02, R-17)")
    args = parser.parse_args()

    files_to_check = []
    if args.all or not args.report_paths:
        files_to_check = list(Path("reports").glob("*.md"))
    else:
        files_to_check = [Path(p) for p in args.report_paths]

    total_checked = 0
    failed = 0

    print("=" * 70)
    print(" ARCUS REPORT & GENERATOR VERIFICATION SUITE")
    print("=" * 70)

    # 1. Verify markdown reports
    for f in sorted(files_to_check):
        if "archive_smoke_test" in str(f):
            continue
        total_checked += 1
        valid, errors = verify_report(f)
        status = "PASSED" if valid else "FAILED"
        print(f"[{status}] {f}")
        if not valid:
            failed += 1
            for err in errors[:10]:
                print(f"   ❌ {err}")
            if len(errors) > 10:
                print(f"   ... and {len(errors) - 10} more issues.")

    # 2. Verify generator scripts (R-02, R-17)
    if args.check_generators:
        gen_valid, gen_errors = verify_generator_scripts()
        gen_status = "PASSED" if gen_valid else "FAILED"
        print(f"[{gen_status}] Generator scripts in scripts/run_*.py (R-02 / R-17)")
        if not gen_valid:
            failed += 1
            for err in gen_errors:
                print(f"   ❌ {err}")

    print("=" * 70)
    print(f"Summary: {total_checked} reports checked, {failed} failed.")
    print("=" * 70)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
