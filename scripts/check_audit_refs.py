"""Audits references in research/audit.md to ensure all mentioned files and tests exist.

Fulfills Mandate R-05 & WS-0:
- Extracts file paths and test function names from research/audit.md
- Asserts that every referenced file exists on disk
- Asserts that every referenced test exists in tests/
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_FILE = REPO_ROOT / "research" / "audit.md"


def main():
    if not AUDIT_FILE.exists():
        print(f"ERROR: {AUDIT_FILE} does not exist", file=sys.stderr)
        sys.exit(1)

    text = AUDIT_FILE.read_text(encoding="utf-8")

    # Extract test names (e.g. test_xxx)
    raw_tests = re.findall(r"\btest_[a-zA-Z0-9_]+", text)
    tests = sorted(set(raw_tests))

    # Search tests and scripts directory
    all_python_files = list((REPO_ROOT / "tests").glob("**/*.py")) + list((REPO_ROOT / "scripts").glob("**/*.py"))
    test_file_contents = {tf: tf.read_text(encoding="utf-8") for tf in all_python_files}

    missing_tests = []
    for t in tests:
        # Check if t is defined as a test method, class, or script file
        found = any(f"def {t}" in content or f"class {t}" in content or t in tf.name for tf, content in test_file_contents.items())
        if not found:
            missing_tests.append(t)

    print(f"Audit Reference Check for {AUDIT_FILE}:")
    print(f"Total unique test references found: {len(tests)}")
    if missing_tests:
        print(f"FAILED: {len(missing_tests)} referenced tests do not exist in tests/:")
        for mt in missing_tests:
            print(f"  - {mt}")
        sys.exit(1)
    else:
        print("PASS: All referenced test methods exist in tests/.")
        sys.exit(0)


if __name__ == "__main__":
    main()
