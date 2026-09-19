# Empirical Latency Benchmark Summary

**Run Start:** 2026-09-19T18:23:19.561351+00:00  
**Run End:** 2026-09-19T18:23:59.225143+00:00  
**Samples:** 50  
**Raw Samples Log:** `reports/latency_raw_samples.jsonl`  

## Measured RTT Distribution (ms)

| Endpoint / Channel | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| **REST API (`/v1/markets`)** | 185.23 | 703.47 | 1638.29 | 290.9 | 161.53 | 2004.56 |
| **WebSocket Ping/Pong** | 137.11 | 360.03 | 698.93 | 177.07 | 134.16 | 1020.09 |
| **WebSocket Subscribe-Ack** | 140.35 | - | - | - | - | - |

## Clock Skew vs Venue

- **Median Skew:** -73.54 ms
- **p95 Skew:** -4.01 ms

## Backtester Latency Pipeline Parameterization

- **Empirical p50 Latency:** 161.17 ms
- **Empirical p95 Latency:** 703.47 ms
- **Stress Latency (+500ms):** 1203.47 ms
