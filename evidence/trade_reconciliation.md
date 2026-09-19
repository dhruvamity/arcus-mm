# WS-1 Test 1: Trade Reconciliation Report

**Date:** 2026-09-19 19:37:02 UTC  
**Recording Date Checked:** `2026-09-19`  

## 1. Executive Summary

This report cross-references live REST `GET /v1/trades` against persisted WebSocket trades logged by recorder PID 11661.
To ensure a true apples-to-apples comparison, REST trades are filtered to those occurring *after* the recorder startup timestamp.

## 2. Market Reconciliation Matrix

| Market | REST Sample Count | In-Session REST Trades | Recorded Total in Log | Matched REST Trades | Missing In-Session | Coverage (%) | Status |
|---|---|---|---|---|---|---|---|
| **BTC-USD** | 100 | 100 | 8989 | 100 | 0 | 100.0% | **PASS (>=99%)** |
| **ETH-USD** | 100 | 100 | 2354 | 100 | 0 | 100.0% | **PASS (>=99%)** |
| **SOL-USD** | 100 | 100 | 2615 | 100 | 0 | 100.0% | **PASS (>=99%)** |
| **HYPE-USD** | 100 | 100 | 676 | 100 | 0 | 100.0% | **PASS (>=99%)** |
| **ZEC-USD** | 100 | 100 | 258 | 100 | 0 | 100.0% | **PASS (>=99%)** |
| **NEAR-USD** | 100 | 100 | 109 | 98 | 2 | 98.0% | **UNDER-RECORDED / SEV-1** |
| **SPCX-USD** | 100 | 3 | 3 | 3 | 0 | 100.0% | **PASS (>=99%)** |

## 3. Detailed Diagnosis & Notes

- **BTC-USD**: 100% of sampled REST trades matched recorded WebSocket tape.
- **ETH-USD**: 100% of sampled REST trades matched recorded WebSocket tape.
- **SOL-USD**: 100% of sampled REST trades matched recorded WebSocket tape.
- **HYPE-USD**: 100% of sampled REST trades matched recorded WebSocket tape.
- **ZEC-USD**: 100% of sampled REST trades matched recorded WebSocket tape.
- **NEAR-USD**: 2 trades missing from sample of 100. Sample missing IDs: `['5813624', '5813461']`
- **SPCX-USD**: 100% of sampled REST trades matched recorded WebSocket tape.
