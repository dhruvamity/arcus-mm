#!/usr/bin/env python3
from __future__ import annotations

"""Generates or updates the Recorder Health & Integrity Dashboard.

Reads data/recorder_heartbeat.json and scans data/raw/ to produce
reports/recorder_health/latest_health.md.
"""

import datetime
import json
import sys
from pathlib import Path


def generate_dashboard():
    heartbeat_path = Path("data/recorder_heartbeat.json")
    if not heartbeat_path.exists():
        print("Heartbeat file data/recorder_heartbeat.json not found.")
        sys.exit(1)

    hb = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    metrics = hb.get("metrics", {})
    now = datetime.datetime.now(datetime.timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    raw_dir = Path(f"data/raw/{date_str}")
    market_stats = []

    if raw_dir.exists():
        for m_dir in sorted(raw_dir.iterdir()):
            if m_dir.is_dir() and m_dir.name != "rest_snapshots":
                m_name = m_dir.name
                total_bytes = sum(f.stat().st_size for f in m_dir.glob("*.jsonl"))
                bbo_sz = (m_dir / "bbo.jsonl").stat().st_size if (m_dir / "bbo.jsonl").exists() else 0
                trades_sz = (m_dir / "trades.jsonl").stat().st_size if (m_dir / "trades.jsonl").exists() else 0
                l2_sz = (m_dir / "l2OrderbookUpdates.jsonl").stat().st_size if (m_dir / "l2OrderbookUpdates.jsonl").exists() else 0
                market_stats.append({
                    "market": m_name,
                    "total_kb": round(total_bytes / 1024.0, 1),
                    "bbo_kb": round(bbo_sz / 1024.0, 1),
                    "trades_kb": round(trades_sz / 1024.0, 1),
                    "l2_kb": round(l2_sz / 1024.0, 1),
                })

    md_lines = [
        "# Multi-Day Recorder Health & Integrity Dashboard",
        "",
        f"**Last Updated:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
        f"**Process PID:** {hb.get('pid')}  ",
        f"**Recorder Uptime:** {hb.get('uptime_secs', 0)/3600.0:.2f} hours ({hb.get('uptime_secs', 0):.0f}s)  ",
        f"**Active Sockets:** {hb.get('active_sockets', 0)} ({hb.get('active_pools', 0)} pools)  ",
        f"**Disk Free:** {hb.get('disk_free_gb', 0.0):.2f} GB  ",
        f"**Total Messages Recorded:** {metrics.get('messages_recorded', 0):,}  ",
        f"**Total Bytes Recorded:** {metrics.get('bytes_recorded', 0) / 1e6:.2f} MB  ",
        f"**Trades Recorded:** {metrics.get('trades_recorded', 0):,}  ",
        f"**L2 Updates Recorded:** {metrics.get('book_updates_recorded', 0):,}  ",
        f"**BBO Updates Recorded:** {metrics.get('bbo_updates_recorded', 0):,}  ",
        f"**Mid-Stream Sequence Gaps:** {metrics.get('sequence_gaps', 0)}  ",
        f"**Duplicates Dropped:** {metrics.get('duplicates_dropped', 0)}  ",
        f"**REST Snapshots Saved:** {metrics.get('rest_snapshots_saved', 0)}  ",
        "",
        "## Per-Market Raw Persistence Size",
        "",
        "| Market | BBO Size (KB) | Trades Size (KB) | L2 Updates (KB) | Total Size (KB) |",
        "|---|---|---|---|---|",
    ]

    for stat in market_stats:
        md_lines.append(
            f"| **{stat['market']}** | {stat['bbo_kb']:.1f} KB | {stat['trades_kb']:.1f} KB | "
            f"{stat['l2_kb']:.1f} KB | **{stat['total_kb']:.1f} KB** |"
        )

    out_file = Path("reports/recorder_health/latest_health.md")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Updated {out_file}")


if __name__ == "__main__":
    generate_dashboard()
