# Empirical Latency Benchmark Summary

**Date:** 2026-09-19T15:50:07.360449+00:00  
**Samples:** 30  

## Measured RTT Distribution (ms)

| Endpoint / Channel | p50 (ms) | p95 (ms) | p99 (ms) | Mean (ms) | Min (ms) | Max (ms) |
|---|---|---|---|---|---|---|
| **REST API (`/v1/markets`)** | 159.08 | 640.26 | 836.74 | 220.38 | 154.35 | 839.15 |
| **WebSocket Ping/Pong** | 157.93 | 199.98 | 486.55 | 174.99 | 156.55 | 591.21 |
| **WebSocket Subscribe-Ack** | 163.22 | - | - | - | - | - |

## Clock Skew vs Venue

- **Median Skew:** -73.60 ms
- **p95 Skew:** -24.97 ms

## Backtester Latency Pipeline Parameterization

- **Empirical p50 Latency:** 158.50 ms
- **Empirical p95 Latency:** 640.26 ms
- **Stress Latency (+500ms):** 1140.26 ms
