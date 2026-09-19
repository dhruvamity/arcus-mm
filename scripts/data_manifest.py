"""Generates cryptographic SHA-256 manifests for recorded raw data files.

Fulfills Rule 6 & WS-1 of Mandate v2:
- Generates data/MANIFEST_YYYY-MM-DD.sha256
- Computes SHA-256 hash for every file in the day's directory
- Allows verification of recorded dataset integrity and provenance
"""

import argparse
import datetime
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"


def hash_file(filepath: Path) -> str:
    """Computes SHA-256 hex digest of a file in streaming chunks."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest_for_date(date_str: str) -> Path:
    """Generates a SHA-256 manifest file for a specific date directory."""
    target_dir = RAW_DIR / date_str
    if not target_dir.exists():
        raise FileNotFoundError(f"Raw data directory not found for date: {target_dir}")

    manifest_path = DATA_DIR / f"MANIFEST_{date_str}.sha256"
    lines = []

    all_files = sorted([p for p in target_dir.glob("**/*") if p.is_file()])
    print(f"Hashing {len(all_files)} files for date {date_str}...")

    for fpath in all_files:
        sha256 = hash_file(fpath)
        rel_path = fpath.relative_to(REPO_ROOT)
        lines.append(f"{sha256}  {rel_path}")

    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated manifest: {manifest_path} ({len(lines)} files)")
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description="Generate SHA-256 data manifest")
    parser.add_argument(
        "--date",
        type=str,
        default=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        help="Date string YYYY-MM-DD (default: current UTC date)",
    )
    args = parser.parse_args()

    try:
        generate_manifest_for_date(args.date)
    except Exception as e:
        print(f"Error generating manifest: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
