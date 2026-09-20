#!/usr/bin/env python3
"""Repository Bundler for Arcus MM Quantitative Trading Platform.
Fulfills Mandate v3 Section 6.

Rules:
1. Walks git ls-files only (never the filesystem).
2. Explicitly excludes .env* except .env.example.
3. Aborts if secret_scan returns non-zero.
4. Prints summary table: included files, excluded files, byte count.
5. Bundle header generated from scan results, never hand-written.
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.secret_scan import scan_content


def get_git_tracked_files(repo_root: Path) -> list[str]:
    """Retrieves strictly git-tracked files using `git ls-files`."""
    try:
        output = subprocess.check_output(
            ["git", "ls-files"], cwd=repo_root, text=True
        )
        return sorted([line.strip() for line in output.splitlines() if line.strip()])
    except Exception as e:
        print(f"Error executing git ls-files: {e}", file=sys.stderr)
        sys.exit(1)


def is_excluded(rel_path: str) -> tuple[bool, str]:
    """Returns (is_excluded, reason)."""
    p = Path(rel_path)
    name = p.name

    if name.startswith(".env") and name != ".env.example":
        return True, "matches .env* exclusion rule"
    if name.endswith(".pem") or name.endswith(".key"):
        return True, "matches *.pem / *.key exclusion rule"
    if name.endswith(".parquet"):
        return True, "matches *.parquet exclusion rule"
    if rel_path.startswith("data/") or rel_path.startswith("data\\"):
        return True, "matches data/** exclusion rule"
    if name in {"FULL_REPO_BUNDLE.md", ".DS_Store"} or name.endswith(".bundle.md"):
        return True, "bundle artifact / OS metadata"
    if name == ".gitkeep":
        return True, "gitkeep placeholder"

    return False, ""


def detect_language(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    mapping = {
        ".py": "python",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".jsonl": "json",
        ".csv": "csv",
        ".txt": "text",
        ".sh": "bash",
        ".example": "text",
    }
    basename = os.path.basename(file_path)
    if basename == ".gitignore":
        return "gitignore"
    return mapping.get(ext, "text")


def determine_fence(content: str) -> str:
    max_consecutive = 0
    curr = 0
    for char in content:
        if char == "`":
            curr += 1
            if curr > max_consecutive:
                max_consecutive = curr
        else:
            curr = 0
    fence_len = max(4, max_consecutive + 1)
    return "`" * fence_len


def categorize_file(path_str: str) -> str:
    if path_str.startswith("src/exec/"):
        return "Execution Stack Plumbing (`src/exec/`)"
    elif path_str.startswith("src/sim/"):
        return "Simulation & Replay Engine (`src/sim/`)"
    elif path_str.startswith("src/strategies/"):
        return "Market Making Strategies (`src/strategies/`)"
    elif path_str.startswith("src/models/"):
        return "Financial & Execution Models (`src/models/`)"
    elif path_str.startswith("src/"):
        return "Core Platform Modules (`src/`)"
    elif path_str.startswith("scripts/"):
        return "Operational & Analysis Runners (`scripts/`)"
    elif path_str.startswith("tests/"):
        return "Deterministic Test Suite (`tests/`)"
    elif path_str.startswith("configs/"):
        return "Venue Configurations (`configs/`)"
    elif path_str.startswith("research/"):
        return "Research Specifications & Ledgers (`research/`)"
    elif path_str.startswith("reports/"):
        return "Research Reports & Health (`reports/`)"
    elif path_str.startswith("evidence/"):
        return "Empirical Evidence Artifacts (`evidence/`)"
    elif path_str.startswith("prompts/"):
        return "Mandate & Prompt History (`prompts/`)"
    elif path_str.startswith("legacy/"):
        return "Quarantined Legacy Code (`legacy/`)"
    else:
        return "Root Project & Setup Files"


def generate_bundle(repo_root: Path, output_file: Path) -> None:
    tracked_files = get_git_tracked_files(repo_root)

    included_files: list[str] = []
    excluded_files: list[tuple[str, str]] = []

    for f in tracked_files:
        excluded, reason = is_excluded(f)
        if excluded:
            excluded_files.append((f, reason))
        else:
            included_files.append(f)

    # Pre-scan all included files with secret scanner
    print("Running pre-bundle secret scan...")
    all_findings = []
    for rel_path in included_files:
        full_path = repo_root / rel_path
        if full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                findings = scan_content(rel_path, content)
                all_findings.extend(findings)
            except Exception as e:
                print(f"Error scanning {rel_path}: {e}", file=sys.stderr)
                sys.exit(1)

    if all_findings:
        print(f"ABORTING BUNDLE GENERATION: Secret scan detected {len(all_findings)} finding(s):", file=sys.stderr)
        for fn, line, rule, val_len in all_findings:
            print(f"  {fn}:{line} [{rule}] (value_length={val_len})", file=sys.stderr)
        sys.exit(1)

    print("Secret scan clean (0 findings). Proceeding with bundling.")

    if output_file.exists():
        output_file.unlink()

    file_metadata: list[dict[str, Any]] = []
    total_lines = 0
    total_bytes = 0

    for rel_path in included_files:
        full_path = repo_root / rel_path
        if not full_path.exists() or not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            lines = len(content.splitlines())
            size = len(content.encode("utf-8"))
            total_lines += lines
            total_bytes += size
            file_metadata.append({
                "path": rel_path,
                "lines": lines,
                "size": size,
                "category": categorize_file(rel_path),
                "lang": detect_language(rel_path),
                "content": content,
            })
        except Exception as e:
            print(f"Warning: Could not read {rel_path}: {e}", file=sys.stderr)

    # Print summary table
    print("\n--- BUNDLE SUMMARY ---")
    print(f"Tracked files evaluated: {len(tracked_files)}")
    print(f"Files included in bundle: {len(file_metadata)}")
    print(f"Files excluded from bundle: {len(excluded_files)}")
    print(f"Total content lines: {total_lines:,}")
    print(f"Total content size: {total_bytes / 1024:.1f} KB ({total_bytes / (1024*1024):.2f} MB)")
    if excluded_files:
        print("\nExcluded files details:")
        for ef, r in excluded_files:
            print(f"  - {ef} ({r})")
    print("----------------------\n")

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Generate document
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("# Arcus Market-Making Quantitative Platform — Codebase Bundle\n\n")
        out.write("> [!IMPORTANT]\n")
        out.write("> **LOCAL ONLY EXPORT BUNDLE — DO NOT COMMIT OR PUSH TO GITHUB**\n")
        out.write("> Source: `git ls-files` tracked files only.\n")
        out.write("> Secret Scan Status: 0 findings verified at build time.\n")
        out.write(f"> Generated At: {now_utc}\n\n")

        out.write(f"- **Total Files:** {len(file_metadata)}\n")
        out.write(f"- **Total Lines:** {total_lines:,}\n")
        out.write(f"- **Total Size:** {total_bytes / 1024:.1f} KB ({total_bytes / (1024*1024):.2f} MB)\n")
        out.write(f"- **Excluded Files Count:** {len(excluded_files)}\n\n")

        out.write("## Table of Contents\n\n")

        categories = [
            "Root Project & Setup Files",
            "Core Platform Modules (`src/`)",
            "Execution Stack Plumbing (`src/exec/`)",
            "Simulation & Replay Engine (`src/sim/`)",
            "Market Making Strategies (`src/strategies/`)",
            "Financial & Execution Models (`src/models/`)",
            "Operational & Analysis Runners (`scripts/`)",
            "Deterministic Test Suite (`tests/`)",
            "Venue Configurations (`configs/`)",
            "Research Specifications & Ledgers (`research/`)" ,
            "Research Reports & Health (`reports/`)",
            "Empirical Evidence Artifacts (`evidence/`)",
            "Mandate & Prompt History (`prompts/`)",
            "Quarantined Legacy Code (`legacy/`)",
        ]

        for cat in categories:
            cat_files = [f for f in file_metadata if f["category"] == cat]
            if not cat_files:
                continue
            out.write(f"### {cat}\n\n")
            out.write("| File Path | Lines | Size (KB) | Type |\n")
            out.write("|---|---|---|---|\n")
            for f in cat_files:
                p = f["path"]
                size_kb = f["size"] / 1024.0
                anchor = f"file-{p.replace('/', '-').replace('.', '-').replace('_', '-').lower()}"
                out.write(f"| [`{p}`](#{anchor}) | {f['lines']} | {size_kb:.1f} KB | `{f['lang']}` |\n")
            out.write("\n")

        out.write("---\n\n")
        out.write("## Full Repository Content\n\n")

        for idx, f in enumerate(file_metadata, 1):
            p = f["path"]
            lang = f["lang"]
            fence = determine_fence(f["content"])
            anchor_id = f"file-{p.replace('/', '-').replace('.', '-').replace('_', '-').lower()}"

            out.write(f"### File {idx}/{len(file_metadata)}: `{p}`\n")
            out.write(f"<a id=\"{anchor_id}\"></a>\n\n")
            out.write(f"- **Relative Path:** `{p}`\n")
            out.write(f"- **Category:** {f['category']}\n")
            out.write(f"- **Language / Syntax:** `{lang}`\n")
            out.write(f"- **Lines:** {f['lines']} | **Size:** {f['size']:,} bytes\n\n")
            out.write(f"{fence}{lang}\n")
            out.write(f["content"])
            if not f["content"].endswith("\n"):
                out.write("\n")
            out.write(f"{fence}\n\n")
            out.write("---\n\n")

    print(f"Successfully generated {output_file.name} ({output_file.stat().st_size / (1024*1024):.2f} MB).")


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    output_file = repo_root / "FULL_REPO_BUNDLE.md"
    generate_bundle(repo_root, output_file)


if __name__ == "__main__":
    main()
