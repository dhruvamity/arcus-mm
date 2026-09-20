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
from typing import Optional, Tuple

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


def get_previous_manifest(date_str: str, manifest_dir: Optional[Path] = None) -> Tuple[Optional[Path], Optional[str]]:
    """Finds the chronological manifest immediately preceding date_str and returns (path, hash)."""
    target_dir = manifest_dir or DATA_DIR
    manifests = sorted(target_dir.glob("MANIFEST_*.sha256")) if target_dir.exists() else []
    target_name = f"MANIFEST_{date_str}.sha256"
    prev_path = None
    for m in manifests:
        if m.name < target_name:
            prev_path = m
        else:
            break
    if prev_path and prev_path.exists():
        return prev_path, hash_file(prev_path)
    return None, "0000000000000000000000000000000000000000000000000000000000000000 (GENESIS_ROOT)"


def generate_manifest_for_date(
    date_str: str,
    source_dirs: Optional[list[Path]] = None,
    manifest_dir: Optional[Path] = None,
) -> Path:
    """Generates a cryptographically chained SHA-256 manifest file for a specific date."""
    target_dir = manifest_dir or DATA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    if source_dirs is None:
        source_dirs = []
        raw_target = RAW_DIR / date_str
        comp_target = DATA_DIR / "compressed" / date_str
        if raw_target.exists():
            source_dirs.append(raw_target)
        if comp_target.exists():
            source_dirs.append(comp_target)

    if not source_dirs:
        raise FileNotFoundError(f"No data directories found for date {date_str}")

    manifest_path = target_dir / f"MANIFEST_{date_str}.sha256"
    prev_manifest, prev_hash = get_previous_manifest(date_str, manifest_dir=target_dir)

    lines = [
        f"# ARCUS DATA INTEGRITY MANIFEST: {date_str}",
        f"# PREV_MANIFEST: {prev_manifest.name if prev_manifest else 'GENESIS'}",
        f"# PREV_MANIFEST_SHA256: {prev_hash}",
        f"# CREATED_AT: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
        "# FORMAT: <sha256_checksum>  <repo_relative_path>",
        "",
    ]

    all_files = []
    for sdir in source_dirs:
        all_files.extend([p for p in sdir.glob("**/*") if p.is_file() and not p.name.startswith(".")])
    all_files = sorted(set(all_files))

    print(f"Hashing {len(all_files)} files for date {date_str} (chain parent: {prev_hash[:16]}...)...")

    file_entries = []
    for fpath in all_files:
        sha256 = hash_file(fpath)
        try:
            rel_path = fpath.resolve().relative_to(REPO_ROOT.resolve())
        except ValueError:
            rel_path = fpath.name
        file_entries.append(f"{sha256}  {rel_path}")

    lines.extend(sorted(file_entries))

    # Compute manifest digest over all file entries
    content_to_digest = "\n".join(file_entries)
    manifest_digest = hashlib.sha256(content_to_digest.encode("utf-8")).hexdigest()
    lines.append("")
    lines.append(f"# MANIFEST_DIGEST: {manifest_digest}")

    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated chained manifest: {manifest_path} ({len(file_entries)} files, digest {manifest_digest[:16]}...)")
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description="Generate chained SHA-256 data manifest")
    parser.add_argument(
        "--date",
        type=str,
        default=(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
        help="Date string YYYY-MM-DD (default: yesterday UTC for closed days)",
    )
    args = parser.parse_args()

    try:
        generate_manifest_for_date(args.date)
    except Exception as e:
        print(f"Error generating manifest: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
