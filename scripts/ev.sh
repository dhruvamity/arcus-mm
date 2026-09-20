#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <ID> [slug] -- <command...>" >&2
    exit 1
fi

ID="$1"
shift

SLUG="evidence"
if [ "$1" != "--" ]; then
    SLUG="$1"
    shift
fi

if [ "$1" = "--" ]; then
    shift
else
    echo "Expected '--' before command" >&2
    exit 1
fi

COMMAND_ARGS=("$@")
COMMAND=$(printf '%q ' "${COMMAND_ARGS[@]}")

DATE=$(date -u +%Y-%m-%d)
OUTDIR="evidence/${DATE}"
mkdir -p "${OUTDIR}"
OUTFILE="${OUTDIR}/${ID}_${SLUG}.txt"

GIT_HEAD=$(git rev-parse HEAD 2>/dev/null || echo "UNKNOWN")
TIMESTAMP=$(date -u +%FT%TZ)
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
else
    PYTHON_BIN=$(which python3 2>/dev/null || which python 2>/dev/null || echo "python")
fi
PYTHON_VERSION=$($PYTHON_BIN --version 2>&1 || echo "UNKNOWN")

TMP_OUTPUT=$(mktemp)

set +e
"${COMMAND_ARGS[@]}" > "$TMP_OUTPUT" 2>&1
EXIT_CODE=$?
set -e

{
    echo "COMMAND: $COMMAND"
    echo "GIT_HEAD: $GIT_HEAD"
    echo "TIMESTAMP: $TIMESTAMP"
    echo "PYTHON_VERSION: $PYTHON_VERSION"
    echo "EXIT_CODE: $EXIT_CODE"
    echo "--- OUTPUT ---"
    cat "$TMP_OUTPUT"
} > "$OUTFILE"

rm -f "$TMP_OUTPUT"

echo "Evidence saved to: $OUTFILE (exit code: $EXIT_CODE)"
exit "$EXIT_CODE"
