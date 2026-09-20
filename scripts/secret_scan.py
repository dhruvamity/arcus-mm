#!/usr/bin/env python3
r"""
Secret scanner for Arcus MM repository.
Fulfills Mandate v3 Section 6.

Rules:
1. ARCUS_(API_KEY|API_PRIVATE_KEY|WALLET_ADDRESS) = \S{16,}
2. 64-hex assigned to a variable whose name contains KEY / SECRET / PRIVATE / TOKEN
3. 0x[0-9a-fA-F]{40} outside test fixtures
4. ghp_... (GitHub personal access tokens)
5. PEM blocks (BEGIN ... PRIVATE KEY)

OUTPUT: file, line, rule, value length only. NEVER the secret value.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

RULE_ARCUS_VARS = re.compile(
    r'(?:ARCUS_(?:API_KEY|API_PRIVATE_KEY|WALLET_ADDRESS))\s*=\s*["\']?([^\s#"\']{16,})'
)
RULE_HEX64_ASSIGN = re.compile(
    r'(?i)(?:key|secret|private|token)\w*\s*[:=]\s*["\']?([0-9a-fA-F]{64})["\']?'
)
RULE_ETH_ADDR = re.compile(
    r'\b(0x[0-9a-fA-F]{40})\b'
)
RULE_GHP_TOKEN = re.compile(
    r'\b(ghp_[a-zA-Z0-9]{36,})\b'
)
RULE_PEM_BLOCK = re.compile(
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----'
)

# Files or patterns allowed to contain dummy ETH addresses or fixtures
FIXTURE_PATH_PATTERNS = [
    re.compile(r'(^|/)tests?/'),
    re.compile(r'(^|/)fixtures?/'),
    re.compile(r'\.env\.example$'),
]

DUMMY_VALUES = {
    "0" * 64,
    "1" * 64,
    "f" * 64,
    "F" * 64,
    "0x" + "0" * 40,
    "0x" + "1" * 40,
    "0x0000000000000000000000000000000000000000",
}


def is_dummy(val: str) -> bool:
    if val in DUMMY_VALUES:
        return True
    if len(val) >= 32 and len(set(val.lower().replace("0x", ""))) <= 1:
        return True
    return False


def is_fixture_file(path_str: str) -> bool:
    normalized = path_str.replace("\\", "/")
    return any(p.search(normalized) for p in FIXTURE_PATH_PATTERNS)


def scan_content(filename: str, content: str) -> list[tuple[str, int, str, int]]:
    """
    Returns list of (filename, line_no, rule_name, match_length).
    NEVER returns the matched value itself.
    """
    findings = []
    lines = content.splitlines()
    fixture = is_fixture_file(filename)

    for line_no, line in enumerate(lines, start=1):
        # 1. Arcus env vars
        for m in RULE_ARCUS_VARS.finditer(line):
            val = m.group(1)
            if not (fixture and is_dummy(val)):
                findings.append((filename, line_no, "ARCUS_CREDENTIAL_VAR", len(val)))

        # 2. 64-hex assigned to sensitive names
        for m in RULE_HEX64_ASSIGN.finditer(line):
            val = m.group(1)
            if not is_dummy(val):
                findings.append((filename, line_no, "HEX64_KEY_ASSIGNMENT", len(val)))

        # 3. ETH address outside test fixtures
        if not fixture:
            for m in RULE_ETH_ADDR.finditer(line):
                val = m.group(1)
                if not is_dummy(val):
                    findings.append((filename, line_no, "ETH_ADDRESS_OUTSIDE_FIXTURES", len(val)))

        # 4. GitHub token
        for m in RULE_GHP_TOKEN.finditer(line):
            val = m.group(1)
            findings.append((filename, line_no, "GITHUB_TOKEN", len(val)))

        # 5. PEM block
        for m in RULE_PEM_BLOCK.finditer(line):
            val = m.group(0)
            findings.append((filename, line_no, "PEM_PRIVATE_KEY", len(val)))

    return findings


def scan_file(path: Path) -> list[tuple[str, int, str, int]]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return scan_content(str(path), content)
    except Exception:
        return []


def get_git_tracked_files(root: Path) -> list[Path]:
    try:
        cmd = ["git", "ls-files"]
        out = subprocess.check_output(cmd, cwd=root, text=True)
        return [root / f.strip() for f in out.splitlines() if f.strip()]
    except Exception:
        return []


def scan_git_history(root: Path) -> list[tuple[str, int, str, int]]:
    """Scan all commits in git history for leaks."""
    findings = []
    try:
        cmd = ["git", "log", "--all", "--format=%H"]
        commits = subprocess.check_output(cmd, cwd=root, text=True).splitlines()
        for commit in commits:
            commit = commit.strip()
            if not commit:
                continue
            show_cmd = ["git", "show", "--format=", "--name-only", commit]
            changed_files = subprocess.check_output(show_cmd, cwd=root, text=True).splitlines()
            for rel_file in changed_files:
                rel_file = rel_file.strip()
                if not rel_file:
                    continue
                try:
                    file_content = subprocess.check_output(
                        ["git", "show", f"{commit}:{rel_file}"],
                        cwd=root,
                        text=True,
                        stderr=subprocess.DEVNULL,
                        errors="ignore"
                    )
                    file_findings = scan_content(rel_file, file_content)
                    # Prefix with commit hash for display
                    findings.extend([(f"{commit[:8]}:{fn}", line, rule, l) for fn, line, rule, l in file_findings])
                except subprocess.CalledProcessError:
                    pass
    except Exception as e:
        print(f"Error scanning git history: {e}", file=sys.stderr)
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Arcus MM Secret Scanner")
    parser.add_argument("--history", action="store_true", help="Scan git commit history")
    parser.add_argument("--path", type=str, default=None, help="Scan specific file or dir")
    parser.add_argument("--all-files", action="store_true", help="Scan all filesystem files (including untracked)")
    args = parser.parse_args()

    root = Path.cwd()
    findings = []

    if args.history:
        print("Scanning entire git history across all branches and commits...")
        findings = scan_git_history(root)
    elif args.path:
        target = Path(args.path)
        if target.is_file():
            findings = scan_file(target)
        else:
            for p in target.rglob("*"):
                if p.is_file() and not any(part.startswith(".") for part in p.parts):
                    findings.extend(scan_file(p))
    elif args.all_files:
        for p in root.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                findings.extend(scan_file(p))
    else:
        # Default: scan git-tracked files
        files = get_git_tracked_files(root)
        for f in files:
            if f.is_file():
                findings.extend(scan_file(f))

    if findings:
        print(f"FAILED: Found {len(findings)} potential secret(s):", file=sys.stderr)
        for fn, line, rule, val_len in findings:
            print(f"  {fn}:{line} [{rule}] (value_length={val_len})", file=sys.stderr)
        return 1
    else:
        print("PASS: No secrets found (0 findings).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
