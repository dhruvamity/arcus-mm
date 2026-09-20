#!/usr/bin/env python3
from __future__ import annotations

"""Continuous Empirical Latency Measurement for Arcus Perpetuals.

- Measures real RTT from the local machine:
  1. REST /v1/markets round-trip time.
  2. WebSocket ping/pong round-trip time.
  3. WebSocket subscribe-ack round-trip time.
- Drops pseudo 'clock skew' metric (which measured BBO book staleness rather than network skew).
- Records every raw sample with UTC timestamp in latency/latency_raw_samples.jsonl.
- Computes empirical p50, p95, p99 latency distributions.
- Supports continuous 24h background sampling every 10–30 seconds.
"""

import argparse

import asyncio
import datetime
import json
import logging
import time
import sys
from pathlib import Path
from typing import List, Dict, Any
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rest_client import ArcusRestClient
from src.ws_client import ArcusWsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("latency_bench")


async def measure_rest_rtt(client: ArcusRestClient) -> float:
    """Measures single REST round-trip time in milliseconds."""
    t0 = time.perf_counter()
    await client._request("GET", "/v1/markets", "markets")
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0


async def measure_ws_ping_rtt(ws_client: ArcusWsClient) -> float:
    """Measures WebSocket ping/pong RTT in milliseconds."""
    if not ws_client.is_connected or not ws_client._ws:
        return -1.0
    t0 = time.perf_counter()
    pong_waiter = await ws_client._ws.ping()
    await pong_waiter
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0


async def measure_ws_subscribe_ack_rtt(ws_client: ArcusWsClient, market: str = "BTC-USD") -> float:
    """Measures WebSocket subscribe-to-ack round-trip time in milliseconds."""
    sub_future = asyncio.get_running_loop().create_future()

    async def callback(msg: Dict[str, Any]):
        if not sub_future.done():
            sub_future.set_result(True)

    t0 = time.perf_counter()
    await ws_client.subscribe("bbo", market, callback)
    try:
        await asyncio.wait_for(sub_future, timeout=5.0)
        t1 = time.perf_counter()
        return (t1 - t0) * 1000.0
    except asyncio.TimeoutError:
        return -1.0


async def run_benchmark(
    samples: int = 50,
    interval_sec: float = 0.1,
    output_dir: str = "reports",
    canonical_dir: str = "latency",
) -> Dict[str, Any]:
    run_start_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.info(f"Starting Arcus empirical latency benchmark ({samples} samples, interval {interval_sec}s)...")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    canon_path = Path(canonical_dir)
    canon_path.mkdir(parents=True, exist_ok=True)

    raw_samples_file = out_path / "latency_raw_samples.jsonl"
    canon_raw_file = canon_path / "latency_raw_samples.jsonl"
    raw_f = open(raw_samples_file, "a", encoding="utf-8")
    canon_raw_f = open(canon_raw_file, "a", encoding="utf-8")

    rest_client = ArcusRestClient()
    ws_client = ArcusWsClient()
    await ws_client.connect()

    rest_rtts = []
    ws_ping_rtts = []

    try:
        for i in range(samples):
            ts_sample = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # 1. REST RTT
            try:
                r_rtt = await measure_rest_rtt(rest_client)
                rest_rtts.append(r_rtt)
                record = {
                    "sample_idx": i,
                    "timestamp_utc": ts_sample,
                    "channel": "REST",
                    "endpoint": "/v1/markets",
                    "rtt_ms": round(r_rtt, 3),
                    "status": "ok",
                }
                raw_f.write(json.dumps(record) + "\n")
                canon_raw_f.write(json.dumps(record) + "\n")
            except Exception as e:
                logger.warning(f"REST ping failed: {e}")
                err_record = {
                    "sample_idx": i,
                    "timestamp_utc": ts_sample,
                    "channel": "REST",
                    "endpoint": "/v1/markets",
                    "error": str(e),
                    "status": "error",
                }
                raw_f.write(json.dumps(err_record) + "\n")
                canon_raw_f.write(json.dumps(err_record) + "\n")

            # 2. WS Ping RTT
            try:
                w_rtt = await measure_ws_ping_rtt(ws_client)
                if w_rtt > 0:
                    ws_ping_rtts.append(w_rtt)
                    w_record = {
                        "sample_idx": i,
                        "timestamp_utc": ts_sample,
                        "channel": "WS_PING",
                        "rtt_ms": round(w_rtt, 3),
                        "status": "ok",
                    }
                    raw_f.write(json.dumps(w_record) + "\n")
                    canon_raw_f.write(json.dumps(w_record) + "\n")
            except Exception as e:
                logger.warning(f"WS ping failed: {e}")

            raw_f.flush()
            canon_raw_f.flush()
            if interval_sec > 0:
                await asyncio.sleep(interval_sec)

        # 3. Single subscribe-ack test
        sub_ack_rtt = await measure_ws_subscribe_ack_rtt(ws_client, "BTC-USD")
        sub_record = {
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "channel": "WS_SUBSCRIBE_ACK",
            "market": "BTC-USD",
            "rtt_ms": round(sub_ack_rtt, 3),
            "status": "ok" if sub_ack_rtt > 0 else "timeout",
        }
        raw_f.write(json.dumps(sub_record) + "\n")
        canon_raw_f.write(json.dumps(sub_record) + "\n")

    finally:
        raw_f.close()
        canon_raw_f.close()
        await ws_client.disconnect()
        await rest_client.close()

    run_end_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def calc_stats(arr: List[float]) -> Dict[str, float]:
        if not arr:
            return {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "min": 0.0, "max": 0.0, "std": 0.0}
        a = np.array(arr)
        return {
            "count": len(a),
            "p50": round(float(np.percentile(a, 50)), 2),
            "p95": round(float(np.percentile(a, 95)), 2),
            "p99": round(float(np.percentile(a, 99)), 2),
            "mean": round(float(np.mean(a)), 2),
            "min": round(float(np.min(a)), 2),
            "max": round(float(np.max(a)), 2),
            "std": round(float(np.std(a)), 2),
        }

    results = {
        "version": "2.0.0",
        "description": "Canonical Empirical Latency Distribution for Arcus MM",
        "run_start_utc": run_start_utc,
        "run_end_utc": run_end_utc,
        "total_samples": samples,
        "rest_rtt_ms": calc_stats(rest_rtts),
        "ws_ping_rtt_ms": calc_stats(ws_ping_rtts),
        "ws_subscribe_ack_ms": round(sub_ack_rtt, 2),
        "raw_samples_log": str(canon_raw_file),
    }

    # Save to canonical directory and reports directory
    canon_json = canon_path / "empirical_samples.json"
    canon_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    report_json = out_path / "latency_benchmarks.json"
    report_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Generate Markdown Summary
    md_lines = [
        "# Empirical Latency Benchmark Summary",
        "",
        f"**Run Start:** {run_start_utc}  ",
        f"**Run End:** {run_end_utc}  ",
        f"**Samples:** {samples}  ",
        f"**Raw Samples Log:** `{canon_raw_file}`  ",
        "",
        "## Measured RTT Distribution (ms)",
        "",
        "| Endpoint / Channel | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) | Min (ms) | Max (ms) |",
        "|---|---|---|---|---|---|---|",
        f"| **REST API (`/v1/markets`)** | {results['rest_rtt_ms']['p50']} | {results['rest_rtt_ms']['p95']} | {results['rest_rtt_ms']['p99']} | {results['rest_rtt_ms']['mean']} | {results['rest_rtt_ms']['min']} | {results['rest_rtt_ms']['max']} |",
        f"| **WebSocket Ping/Pong** | {results['ws_ping_rtt_ms']['p50']} | {results['ws_ping_rtt_ms']['p95']} | {results['ws_ping_rtt_ms']['p99']} | {results['ws_ping_rtt_ms']['mean']} | {results['ws_ping_rtt_ms']['min']} | {results['ws_ping_rtt_ms']['max']} |",
        f"| **WebSocket Subscribe-Ack** | {results['ws_subscribe_ack_ms']} | - | - | - | - | - |",
        "",
        "## Engine Latency Pipeline Parameterization",
        "",
        f"- **Empirical One-Way Feed Latency:** {results['ws_ping_rtt_ms']['p50'] / 2.0:.2f} ms",
        f"- **Empirical Order Entry Latency:** {results['rest_rtt_ms']['p50'] / 2.0:.2f} ms",
        f"- **Empirical p95 Latency:** {results['rest_rtt_ms']['p95']:.2f} ms",
        f"- **Stress Latency (+500ms):** {results['rest_rtt_ms']['p95'] + 500.0:.2f} ms",
    ]

    summary_path = out_path / "latency_summary.md"
    summary_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    logger.info(f"Latency benchmark complete. Saved to {canon_json} and {summary_path}")
    return results


async def continuous_sampler(interval_sec: float = 15.0):
    """Runs continuous background latency sampling across all hours."""
    logger.info(f"Starting continuous latency sampler with {interval_sec}s interval...")
    while True:
        try:
            await run_benchmark(samples=10, interval_sec=interval_sec)
        except Exception as e:
            logger.error(f"Error in continuous latency sampler: {e}")
        await asyncio.sleep(interval_sec)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Arcus Empirical Latency Benchmark")
    parser.add_argument("--samples", type=int, default=50, help="Number of ping samples")
    parser.add_argument("--interval", type=float, default=0.1, help="Interval between samples in seconds")
    parser.add_argument("--continuous", action="store_true", help="Run continuously in background (every 15s)")
    args = parser.parse_args()

    if args.continuous:
        asyncio.run(continuous_sampler(interval_sec=args.interval if args.interval > 0.1 else 15.0))
    else:
        asyncio.run(run_benchmark(samples=args.samples, interval_sec=args.interval))
