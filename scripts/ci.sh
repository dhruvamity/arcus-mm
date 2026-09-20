#!/usr/bin/env bash
# Continuous Integration runner for Arcus MM Quantitative Trading Platform
# Fulfills Mandate v3 Section 7
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Running CI for Arcus MM ==="

# Check Python 3.12 presence
PY312_BIN=""
if [ -f ".venv/bin/python" ]; then
    PY312_BIN=".venv/bin/python"
elif command -v /opt/homebrew/bin/python3.12 >/dev/null 2>&1; then
    PY312_BIN="/opt/homebrew/bin/python3.12"
elif command -v python3.12 >/dev/null 2>&1; then
    PY312_BIN="$(command -v python3.12)"
fi

if [ -z "$PY312_BIN" ]; then
    echo "ERROR: Python 3.12 is required as the reference interpreter, but was not found." >&2
    exit 1
fi

echo "Using reference interpreter: $($PY312_BIN --version)"

# Check available interpreters
INTERPRETERS=("$PY312_BIN")

if command -v python3.13 >/dev/null 2>&1; then
    INTERPRETERS+=("$(command -v python3.13)")
fi

if command -v /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 >/dev/null 2>&1; then
    INTERPRETERS+=("/Library/Frameworks/Python.framework/Versions/3.14/bin/python3")
elif command -v python3.14 >/dev/null 2>&1; then
    INTERPRETERS+=("$(command -v python3.14)")
fi

for PY in "${INTERPRETERS[@]}"; do
    echo ""
    echo "--- Testing with $($PY --version) ---"
    
    # 1. Pyflakes syntax and import check
    echo "Running pyflakes..."
    $PY -m pyflakes src scripts tests
    
    # 2. Deterministic unit tests (offline)
    echo "Running offline unit tests..."
    $PY -m unittest discover -s tests -p "test_*.py"
done

# 3. Mutation check suite (>= 16 mutations caught)
echo ""
echo "--- Running mutation verification suite ---"
$PY312_BIN scripts/mutation_check.py

# 4. Secret scan on tracked files
echo ""
echo "--- Running secret scanner on git-tracked files ---"
$PY312_BIN scripts/secret_scan.py

echo ""
echo "=== ALL CI CHECKS PASSED ==="
