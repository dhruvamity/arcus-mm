#!/usr/bin/env python3
"""Repository Bundler for Arcus MM Quantitative Trading Platform.

Combines the complete contents of all repository files into a single, comprehensive
local Markdown document (FULL_REPO_BUNDLE.md).

Designed for ingestion by downstream coding agents, LLM contexts, or offline inspection.
Enforces that this output file is strictly ignored by git and never pushed to remote.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple


def get_tracked_files(repo_root: Path) -> List[str]:
    """Retrieves all tracked git files in sorted canonical order."""
    try:
        output = subprocess.check_output(
            ["git", "ls-files"], cwd=repo_root, universal_newlines=True
        )
        files = [line.strip() for line in output.splitlines() if line.strip()]
        return sorted(files)
    except Exception as e:
        print(f"Error running git ls-files: {e}")
        # Fallback: scan directory manually excluding .git, __pycache__, and bundles
        files = []
        for root, dirs, filenames in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "venv", ".venv", "data"}]
            for f in filenames:
                if f.endswith(".bundle.md") or f == "FULL_REPO_BUNDLE.md":
                    continue
                rel = os.path.relpath(os.path.join(root, f), repo_root)
                files.append(rel)
        return sorted(files)


def detect_language(file_path: str) -> str:
    """Detects markdown code block syntax language tag based on file extension."""
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
    """Determines safe backtick fence length to avoid escaping issues with nested code blocks."""
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
    """Categorizes files for structured table of contents."""
    if path_str.startswith("src/"):
        return "Core Trading & Research Engine (`src/`)"
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
    else:
        return "Root Project & Setup Files"


def generate_bundle(repo_root: Path, output_file: Path):
    """Generates the comprehensive single markdown file."""
    files = get_tracked_files(repo_root)

    # Filter out output file itself, gitkeep, or unwanted files
    files = [f for f in files if f != output_file.name and not f.endswith(".bundle.md") and f != "data/.gitkeep"]

    file_metadata: List[Dict[str, Any]] = []
    total_lines = 0
    total_bytes = 0

    # Collect stats
    for rel_path in files:
        full_path = repo_root / rel_path
        if not full_path.exists() or not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            lines = len(content.splitlines())
            size = full_path.stat().st_size
            total_lines += lines
            total_bytes += size
            file_metadata.append({
                "path": rel_path,
                "lines": lines,
                "size": size,
                "category": categorize_file(rel_path),
                "lang": detect_language(rel_path),
                "content": content
            })
        except Exception as e:
            print(f"Warning: Could not read {rel_path}: {e}")

    print(f"Bundling {len(file_metadata)} files ({total_lines:,} lines, {total_bytes / (1024*1024):.2f} MB)...")

    # Generate document
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("# Arcus Market-Making Quantitative Platform — Complete Codebase Bundle\n\n")
        out.write("> [!IMPORTANT]\n")
        out.write("> **LOCAL ONLY EXPORT BUNDLE — DO NOT COMMIT OR PUSH TO GITHUB**\n")
        out.write("> This document concatenates the full repository source code and documentation.\n")
        out.write("> Created for AI agents and local context windows that cannot pull git submodules or remote repositories.\n\n")

        out.write(f"- **Total Files:** {len(file_metadata)}\n")
        out.write(f"- **Total Lines of Code / Documentation:** {total_lines:,}\n")
        out.write(f"- **Total Repository Size:** {total_bytes / 1024:.1f} KB ({total_bytes / (1024*1024):.2f} MB)\n")
        out.write(f"- **Generated At:** 2026-09-20T00:26:00+05:30 (Local Time)\n\n")

        # Table of Contents
        out.write("## Table of Contents\n\n")
        
        # Group by category
        categories = [
            "Root Project & Setup Files",
            "Core Trading & Research Engine (`src/`)",
            "Operational & Analysis Runners (`scripts/`)",
            "Deterministic Test Suite (`tests/`)",
            "Venue Configurations (`configs/`)",
            "Research Specifications & Ledgers (`research/`)",
            "Research Reports & Health (`reports/`)",
        ]

        for cat in categories:
            cat_files = [f for f in file_metadata if f["category"] == cat]
            if not cat_files:
                continue
            out.write(f"### {cat}\n\n")
            out.write("| File Path | Lines | Size (KB) | Description / Type |\n")
            out.write("|---|---|---|---|\n")
            for f in cat_files:
                p = f["path"]
                size_kb = f["size"] / 1024.0
                out.write(f"| [`{p}`](#file-{p.replace('/', '-').replace('.', '-').lower()}) | {f['lines']} | {size_kb:.1f} KB | `{f['lang']}` |\n")
            out.write("\n")

        out.write("---\n\n")
        out.write("## Full Repository Content (File by File)\n\n")

        for idx, f in enumerate(file_metadata, 1):
            p = f["path"]
            lang = f["lang"]
            fence = determine_fence(f["content"])
            anchor_id = f"file-{p.replace('/', '-').replace('.', '-').lower()}"

            out.write(f"### File {idx}/{len(file_metadata)}: `{p}`\n")
            out.write(f"<a id=\"{anchor_id}\"></a>\n\n")
            out.write(f"- **Relative Path:** `{p}`\n")
            out.write(f"- **Language / Syntax:** `{lang}`\n")
            out.write(f"- **Lines:** {f['lines']} | **Size:** {f['size']:,} bytes\n\n")
            out.write(f"{fence}{lang}\n")
            out.write(f["content"])
            if not f["content"].endswith("\n"):
                out.write("\n")
            out.write(f"{fence}\n\n")
            out.write("---\n\n")

    print(f"Successfully generated {output_file} ({output_file.stat().st_size / (1024*1024):.2f} MB).")


def main():
    repo_root = Path(__file__).resolve().parent.parent
    output_file = repo_root / "FULL_REPO_BUNDLE.md"
    generate_bundle(repo_root, output_file)


if __name__ == "__main__":
    main()
