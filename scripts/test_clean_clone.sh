#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(pwd)"
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo "Cloning repository from $REPO_ROOT into $TMPDIR/repo..."
git clone "$REPO_ROOT" "$TMPDIR/repo"

cd "$TMPDIR/repo"
echo "Creating fresh virtual environment with Python 3.12..."
if command -v python3.12 >/dev/null 2>&1; then
    PY312="python3.12"
elif [ -f "/opt/homebrew/bin/python3.12" ]; then
    PY312="/opt/homebrew/bin/python3.12"
else
    echo "ERROR: python3.12 binary not found" >&2
    exit 1
fi

$PY312 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt pyflakes

echo "Running pyflakes on clean clone..."
.venv/bin/python -m pyflakes src scripts tests

echo "Running offline unit tests on clean clone..."
.venv/bin/python -m unittest discover -s tests -p "test_*.py"

echo "Running secret scanner on clean clone..."
.venv/bin/python scripts/secret_scan.py

echo "=== CLEAN CLONE TEST SUCCESSFUL ==="
