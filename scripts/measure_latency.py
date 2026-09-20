#!/usr/bin/env python3
from __future__ import annotations

"""Empirical Latency Measurement for Arcus Perpetuals.
Fulfills Mandate v3 WS-I and Finding V-27.

- Measures real RTT from the local machine:
  1. REST /v1/time (weight 1) or /health (weight 0) round-trip time, avoiding high-weight endpoints.
  2. WebSocket ping/pong round-trip time.
  3. WebSocket subscribe-ack round-trip time.
- Excludes pseudo 'clock skew' metric (which measured book staleness rather than network skew).
- Records every raw sample with UTC timestamp and HTTP status in latency/latency_samples.jsonl.
- Computes empirical p50, p95, p99 latency distributions and writes latency/latency_summary.json.
- Explicitly flags order-path latency as PROVISIONAL pending testnet faucet funding.
- Supports single-run benchmarks or continuous background sampling.
"""

import argparse
import asyncio
import datetime
import json
import logging
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rest_client import ArcusRestClient
from src.ws_client import ArcusWsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("latency_bench")

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = REPO_ROOT / "latency"


async def measure_rest_rtt(client: ArcusRestClient, endpoint: str = "/v1/time", endpoint_key: str = "time") -> Tuple[float, int, str]:
    """Measures single REST round-trip time in milliseconds against lightweight endpoint."""
    t0 = time.perf_counter()
    await client._request("GET", endpoint, endpoint_key)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0, 200, endpoint


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
    samples: int = 30,
    interval_sec: float = 0.2,
    endpoint: str = "/v1/time",
    endpoint_key: str = "time",
) -> Dict[str, Any]:
    run_start_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.info(f"Starting Arcus latency measurement ({samples} samples against {endpoint})...")

    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    canon_samples_file = CANONICAL_DIR / "latency_samples.jsonl"
    canon_summary_file = CANONICAL_DIR / "latency_summary.json"

    # Legacy compatibility paths
    legacy_raw_file = CANONICAL_DIR / "latency_raw_samples.jsonl"
    legacy_summary_file = CANONICAL_DIR / "empirical_samples.json"

    raw_f = open(canon_samples_file, "a", encoding="utf-8")
    legacy_raw_f = open(legacy_raw_file, "a", encoding="utf-8")

    rest_client = ArcusRestClient()
    ws_client = ArcusWsClient()
    await ws_client.connect()

    rest_rtts: List[float] = []
    ws_ping_rtts: List[float] = []

    try:
        for i in range(samples):
            ts_sample = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # 1. REST RTT
            try:
                r_rtt, status_code, ep = await measure_rest_rtt(rest_client, endpoint=endpoint, endpoint_key=endpoint_key)
                rest_rtts.append(r_rtt)
                record = {
                    "sample_idx": i,
                    "timestamp_utc": ts_sample,
                    "channel": "REST",
                    "endpoint": ep,
                    "http_status": status_code,
                    "rtt_ms": round(r_rtt, 3),
                    "status": "ok",
                }
                raw_f.write(json.dumps(record) + "\n")
                legacy_raw_f.write(json.dumps(record) + "\n")
            except Exception as e:
                logger.warning(f"REST ping failed: {e}")
                err_record = {
                    "sample_idx": i,
                    "timestamp_utc": ts_sample,
                    "channel": "REST",
                    "endpoint": endpoint,
                    "http_status": 0,
                    "error": str(e),
                    "status": "error",
                }
                raw_f.write(json.dumps(err_record) + "\n")
                legacy_raw_f.write(json.dumps(err_record) + "\n")

            # 2. WS Ping RTT
            try:
                w_rtt = await measure_ws_ping_rtt(ws_client)
                if w_rtt > 0:
                    ws_ping_rtts.append(w_rtt)
                    w_record = {
                        "sample_idx": i,
                        "timestamp_utc": ts_sample,
                        "channel": "WS_PING",
                        "endpoint": ws_client.config.ws_url,
                        "rtt_ms": round(w_rtt, 3),
                        "status": "ok",
                    }
                    raw_f.write(json.dumps(w_record) + "\n")
                    legacy_raw_f.write(json.dumps(w_record) + "\n")
            except Exception as e:
                logger.warning(f"WS ping failed: {e}")

            raw_f.flush()
            legacy_raw_f.flush()
            if interval_sec > 0:
                await asyncio.sleep(interval_sec)

        # 3. Single subscribe-ack test
        sub_ack_rtt = await measure_ws_subscribe_ack_rtt(ws_client, "BTC-USD")
        sub_record = {
            "sample_idx": samples,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "channel": "WS_SUBSCRIBE_ACK",
            "endpoint": "bbo:BTC-USD",
            "rtt_ms": round(sub_ack_rtt, 3),
            "status": "ok" if sub_ack_rtt > 0 else "timeout",
        }
        raw_f.write(json.dumps(sub_record) + "\n")
        legacy_raw_f.write(json.dumps(sub_record) + "\n")

    finally:
        raw_f.close()
        legacy_raw_f.close()
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

    rest_stats = calc_stats(rest_rtts)
    ws_stats = calc_stats(ws_ping_rtts)

    results = {
        "version": "3.0.0",
        "status": "PROVISIONAL",
        "provisional_reason": "APPROVE_TESTNET_FAUCET_FUNDING = NO; order-path ACK latency provisional pending testnet faucet funding.",
        "description": "Canonical Empirical Latency Distribution for Arcus MM",
        "endpoint": endpoint,
        "endpoint_weight": 1 if endpoint == "/v1/time" else 0,
        "run_start_utc": run_start_utc,
        "run_end_utc": run_end_utc,
        "total_samples": samples,
        "rest_rtt_ms": rest_stats,
        "ws_ping_rtt_ms": ws_stats,
        "ws_subscribe_ack_ms": round(sub_ack_rtt, 2),
        "one_way_feed_latency_ms": round(ws_stats["p50"] / 2.0, 2),
        "one_way_order_entry_latency_ms": round(rest_stats["p50"] / 2.0, 2),
        "scenario_grid_ms": [25.0, 60.0, 150.0, 300.0, 700.0],
        "stress_latency_p95_plus_500ms": round(rest_stats["p95"] + 500.0, 2),
        "raw_samples_log": "latency/latency_samples.jsonl",
    }

    canon_summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    legacy_summary_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

    logger.info(f"Latency benchmark complete. Saved to {canon_summary_file}")
    return results


async def continuous_sampler(interval_sec: float = 15.0, endpoint: str = "/v1/time"):
    """Runs continuous background latency sampling across all hours."""
    logger.info(f"Starting continuous latency sampler with {interval_sec}s interval against {endpoint}...")
    while True:
        try:
            await run_benchmark(samples=5, interval_sec=1.0, endpoint=endpoint)
        except Exception as e:
            logger.error(f"Error in continuous latency sampler: {e}")
        await asyncio.sleep(interval_sec)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Arcus Empirical Latency Benchmark (Mandate v3 WS-I)")
    parser.add_argument("--samples", type=int, default=30, help="Number of ping samples")
    parser.add_argument("--interval", type=float, default=0.2, help="Interval between samples in seconds")
    parser.add_argument("--endpoint", type=str, default="/v1/time", help="Lightweight endpoint (/v1/time or /health)")
    parser.add_argument("--continuous", action="store_true", help="Run continuously in background (every 15s)")
    args = parser.parse_args()

    ep_key = "health" if "health" in args.endpoint else "time"

    if args.continuous:
        asyncio.run(continuous_sampler(interval_sec=args.interval if args.interval > 1.0 else 15.0, endpoint=args.endpoint))
    else:
        asyncio.run(run_benchmark(samples=args.samples, interval_sec=args.interval, endpoint=args.endpoint, endpoint_key=ep_key))
