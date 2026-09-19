#!/usr/bin/env python3
"""Continuous Empirical Latency Measurement for Arcus Perpetuals.

Fulfills Section 4.6 of prompt.md:
- Measures real RTT from the local machine:
  1. REST /v1/markets (or /health) round-trip time.
  2. WebSocket ping/pong round-trip time.
  3. WebSocket subscribe-ack round-trip time.
- Measures clock skew against venue timestamps.
- Computes empirical p50, p95, p99 latency distributions.
- Emits results to reports/latency_benchmarks.json and reports/latency_summary.md.
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

from src.config import settings
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


async def run_benchmark(samples: int = 50, output_dir: str = "reports") -> Dict[str, Any]:
    logger.info(f"Starting Arcus latency benchmark with {samples} samples...")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    rest_client = ArcusRestClient()
    ws_client = ArcusWsClient()
    await ws_client.connect()

    rest_rtts = []
    ws_ping_rtts = []
    clock_skews_ms = []

    try:
        for i in range(samples):
            # 1. REST RTT
            try:
                r_rtt = await measure_rest_rtt(rest_client)
                rest_rtts.append(r_rtt)
            except Exception as e:
                logger.warning(f"REST ping failed: {e}")

            # 2. WS Ping RTT
            try:
                w_rtt = await measure_ws_ping_rtt(ws_client)
                if w_rtt > 0:
                    ws_ping_rtts.append(w_rtt)
            except Exception as e:
                logger.warning(f"WS ping failed: {e}")

            # 3. Clock skew measurement against REST timestamp
            try:
                t_local_before = time.time() * 1000.0
                bbo_res = await rest_client._request("GET", "/v1/bbo/BTC-USD", "bbo")
                t_local_after = time.time() * 1000.0
                venue_ts_us = bbo_res.get("timestamp")
                if venue_ts_us:
                    venue_ts_ms = venue_ts_us / 1000.0
                    local_mid_ms = (t_local_before + t_local_after) / 2.0
                    skew = venue_ts_ms - local_mid_ms
                    clock_skews_ms.append(skew)
            except Exception as e:
                pass

            await asyncio.sleep(0.1)

        # 4. Single subscribe-ack test
        sub_ack_rtt = await measure_ws_subscribe_ack_rtt(ws_client, "BTC-USD")

    finally:
        await ws_client.disconnect()
        await rest_client.close()

    def calc_stats(arr: List[float]) -> Dict[str, float]:
        if not arr:
            return {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "min": 0.0, "max": 0.0}
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
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_samples": samples,
        "rest_rtt_ms": calc_stats(rest_rtts),
        "ws_ping_rtt_ms": calc_stats(ws_ping_rtts),
        "ws_subscribe_ack_ms": round(sub_ack_rtt, 2),
        "clock_skew_ms": calc_stats(clock_skews_ms),
    }

    # Save JSON
    json_path = out_path / "latency_benchmarks.json"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Generate Markdown Summary
    md_lines = [
        "# Empirical Latency Benchmark Summary",
        "",
        f"**Date:** {results['timestamp_utc']}  ",
        f"**Samples:** {samples}  ",
        "",
        "## Measured RTT Distribution (ms)",
        "",
        "| Endpoint / Channel | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) | Min (ms) | Max (ms) |",
        "|---|---|---|---|---|---|---|",
        f"| **REST API (`/v1/markets`)** | {results['rest_rtt_ms']['p50']} | {results['rest_rtt_ms']['p95']} | {results['rest_rtt_ms']['p99']} | {results['rest_rtt_ms']['mean']} | {results['rest_rtt_ms']['min']} | {results['rest_rtt_ms']['max']} |",
        f"| **WebSocket Ping/Pong** | {results['ws_ping_rtt_ms']['p50']} | {results['ws_ping_rtt_ms']['p95']} | {results['ws_ping_rtt_ms']['p99']} | {results['ws_ping_rtt_ms']['mean']} | {results['ws_ping_rtt_ms']['min']} | {results['ws_ping_rtt_ms']['max']} |",
        f"| **WebSocket Subscribe-Ack** | {results['ws_subscribe_ack_ms']} | - | - | - | - | - |",
        "",
        "## Clock Skew vs Venue",
        "",
        f"- **Median Skew:** {results['clock_skew_ms']['p50']:.2f} ms",
        f"- **p95 Skew:** {results['clock_skew_ms']['p95']:.2f} ms",
        "",
        "## Backtester Latency Pipeline Parameterization",
        "",
        f"- **Empirical p50 Latency:** {results['ws_ping_rtt_ms']['p50'] / 2.0 + results['rest_rtt_ms']['p50'] / 2.0:.2f} ms",
        f"- **Empirical p95 Latency:** {results['rest_rtt_ms']['p95']:.2f} ms",
        f"- **Stress Latency (+500ms):** {results['rest_rtt_ms']['p95'] + 500.0:.2f} ms",
    ]

    summary_path = out_path / "latency_summary.md"
    summary_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    logger.info(f"Latency benchmark complete. Saved to {json_path} and {summary_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Arcus Latency Benchmark")
    parser.add_argument("--samples", type=int, default=50, help="Number of ping samples")
    parser.add_argument("--continuous", action="store_true", help="Run continuously every hour")
    args = parser.parse_args()

    if args.continuous:
        async def continuous_loop():
            while True:
                try:
                    await run_benchmark(samples=args.samples)
                except Exception as err:
                    logger.error(f"Benchmark error: {err}")
                await asyncio.sleep(3600.0)
        asyncio.run(continuous_loop())
    else:
        asyncio.run(run_benchmark(samples=args.samples))
