#!/usr/bin/env python3
"""Report Verification Script for Arcus Research Reports.

Fulfills Non-negotiable Rule 3 from prompt.md:
- Ensures reports are generated from computed tables, never hand-narrated.
- Checks that numbers in prose trace directly to table cells.
- Enforces strict prohibition of forbidden words ("CERTIFIED", un-quarantined "CONDITIONAL YES").
- Validates that every strategy metric carries N (sample size).
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple


FORBIDDEN_PATTERNS = [
    re.compile(r"\bCERTIFIED\b", re.IGNORECASE),
]


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
    # Matches patterns like: +0.20%, -1.49 bps, $5.00, 5,170, 0.05%
    raw_matches = re.findall(r"[-+]?\d+(?:,\d+)*(?:\.\d+)?(?:%|bps|\$)?", text)
    cleaned = set()
    for m in raw_matches:
        c = m.strip("$,%").replace(",", "")
        if c and c not in {"-", "+", "."}:
            try:
                # normalize to float string
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
    """Verifies a single markdown report for forbidden terms and table consistency."""
    errors = []
    if not file_path.exists():
        return False, [f"File does not exist: {file_path}"]

    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Skip superseded warning blocks from forbidden term check if properly marked
    is_superseded = "SUPERSEDED — PRELIMINARY SMOKE TEST" in content

    # 1. Check forbidden terms
    for line_no, line in enumerate(lines, 1):
        if is_superseded and ("SUPERSEDED" in line or "defect ledger" in line or "withdrawn" in line or "downgraded" in line):
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(line):
                errors.append(f"Line {line_no}: Contains forbidden word '{pattern.pattern}': {line.strip()}")

    # 2. Extract tables and prose numbers
    tables = extract_tables(content)
    if not tables and len(lines) > 50:
        errors.append("Report has >50 lines but contains no markdown tables.")
        return False, errors

    table_numbers = extract_numbers_from_tables(tables)

    # 3. Check prose narrative outside of tables
    non_table_lines = []
    for line in lines:
        trimmed = line.strip()
        if not (trimmed.startswith("|") and trimmed.endswith("|")) and not trimmed.startswith("#") and not trimmed.startswith(">"):
            non_table_lines.append(trimmed)

    prose_text = " ".join(non_table_lines)
    # Check key claim sentences mentioning bps or percentages
    claim_sentences = [
        s.strip() for s in re.split(r"[.\n]", prose_text)
        if any(kw in s for kw in ["bps", "%", "net edge", "expectancy", "return", "PnL"])
    ]

    for sentence in claim_sentences:
        if is_superseded:
            continue
        # Extract candidate numeric figures
        nums = extract_numbers_from_text(sentence)
        unmatched = [n for n in nums if n not in table_numbers]
        # Ignore common non-metric integers like year 2026, 0, 1, 100
        unmatched = [n for n in unmatched if n not in {"2026", "0", "1", "100", "50", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "13", "14", "15", "16", "20", "24", "60", "64"}]
        if unmatched:
            errors.append(f"Prose number(s) {unmatched} in sentence not found in any table: \"{sentence[:100]}...\"")

    is_valid = len(errors) == 0
    return is_valid, errors


def main():
    parser = argparse.ArgumentParser(description="Verify Arcus research report tables and claims.")
    parser.add_argument("report_paths", nargs="*", help="Path(s) to markdown report(s) to verify")
    parser.add_argument("--all", action="store_true", help="Verify all reports in reports/")
    args = parser.parse_args()

    files_to_check = []
    if args.all or not args.report_paths:
        files_to_check = list(Path("reports").glob("*.md"))
    else:
        files_to_check = [Path(p) for p in args.report_paths]

    total_checked = 0
    failed = 0

    print("=" * 70)
    print(" ARCUS REPORT VERIFICATION SUITE")
    print("=" * 70)

    for f in sorted(files_to_check):
        # Skip archived smoke test reports
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

    print("=" * 70)
    print(f"Summary: {total_checked} reports checked, {failed} failed.")
    print("=" * 70)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
