# Empirical Latency Benchmark Summary

**Run Start:** 2026-09-19T19:59:03.143688+00:00  
**Run End:** 2026-09-19T19:59:07.093729+00:00  
**Samples:** 5  
**Raw Samples Log:** `latency/latency_raw_samples.jsonl`  

## Measured RTT Distribution (ms)

| Endpoint / Channel | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| **REST API (`/v1/markets`)** | 376.06 | 863.94 | 959.0 | 444.22 | 194.25 | 982.77 |
| **WebSocket Ping/Pong** | 139.45 | 140.05 | 140.12 | 139.56 | 139.19 | 140.14 |
| **WebSocket Subscribe-Ack** | 141.09 | - | - | - | - | - |

## Engine Latency Pipeline Parameterization

- **Empirical One-Way Feed Latency:** 69.72 ms
- **Empirical Order Entry Latency:** 188.03 ms
- **Empirical p95 Latency:** 863.94 ms
- **Stress Latency (+500ms):** 1363.94 ms
