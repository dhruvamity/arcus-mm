#!/usr/bin/env bash
# Offline CI: static check, unit tests, secret scan.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PY="${PY:-.venv/bin/python}"
echo "Using $($PY --version)"

$PY -m pyflakes src scripts tests
$PY -m unittest discover -s tests -p "test_*.py"
$PY scripts/secret_scan.py

echo "CI OK"
