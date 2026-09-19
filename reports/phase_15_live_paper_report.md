# Phase 15 — Live Mainnet Paper Trading Report

**Date:** 2026-09-19 16:00:16 UTC  
**Session ID:** `paper_20260919_155931`  
**Session Duration:** 0.01 hours (30 seconds)  
**Execution Mode:** Live Public Mainnet Feeds (ZERO REAL MAINNET ORDERS)  

## 1. Executive Summary

This session evaluated live passive market making execution across simultaneous candidates and control markets.
Both **Model C (Conservative Gating)** and **Model B (Queue-Aware Shadow)** were logged in parallel.
All raw WebSocket frames were recorded to enable post-session replay parity testing.

## 2. Multi-Market Performance Matrix ($100 Research Capital Scenario)

| Market | Asset Class | Model C Fills | Model C PnL ($) | Model C Net (%) | Model B Fills | Model B PnL ($) | Max DD (%) | Fill Rate (/hr) | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **BTC-USD** | crypto | 0 | $+0.00 | +0.00% | 0 | $+0.00 | 0.00% | 0.0/hr | **INSUFFICIENT DATA (<30 fills)** |
| **HYPE-USD** | crypto | 0 | $+0.00 | +0.00% | 0 | $+0.00 | 0.00% | 0.0/hr | **INSUFFICIENT DATA (<30 fills)** |
| **LIT-USD** | crypto | 0 | $+0.00 | +0.00% | 0 | $+0.00 | 0.00% | 0.0/hr | **INSUFFICIENT DATA (<30 fills)** |
| **NEAR-USD** | crypto | 1 | $+0.00 | +0.00% | 1 | $+0.00 | 0.00% | 100.0/hr | **INSUFFICIENT DATA (<30 fills)** |
| **NVDA-USD** | equities | 0 | $+0.00 | +0.00% | 0 | $+0.00 | 0.00% | 0.0/hr | **INSUFFICIENT DATA (<30 fills)** |
| **SLV-USD** | commodities | 0 | $+0.00 | +0.00% | 0 | $+0.00 | 0.00% | 0.0/hr | **INSUFFICIENT DATA (<30 fills)** |
| **SPCX-USD** | equities | 0 | $+0.00 | +0.00% | 0 | $+0.00 | 0.00% | 0.0/hr | **INSUFFICIENT DATA (<30 fills)** |
| **TSLA-USD** | equities | 0 | $+0.00 | +0.00% | 0 | $+0.00 | 0.00% | 0.0/hr | **INSUFFICIENT DATA (<30 fills)** |
| **UNI-USD** | crypto | 0 | $+0.00 | +0.00% | 0 | $+0.00 | 0.00% | 0.0/hr | **INSUFFICIENT DATA (<30 fills)** |
| **ZEC-USD** | crypto | 0 | $+0.00 | +0.00% | 0 | $+0.00 | 0.00% | 0.0/hr | **INSUFFICIENT DATA (<30 fills)** |

## 3. Capital Scaling Comparison ($50 vs $100 Scenario)

| Market | Min Clip ($) | $100 Capital Net PnL ($) | $50 Capital Net PnL ($) | Capital Dependent? |
|---|---|---|---|---|
| **BTC-USD** | $5.00 | $+0.00 | $+0.00 | NO |
| **HYPE-USD** | $9.24 | $+0.00 | $+0.00 | NO |
| **LIT-USD** | $5.00 | $+0.00 | $+0.00 | NO |
| **NEAR-USD** | $5.00 | $+0.00 | $-0.00 | YES |
| **NVDA-USD** | $5.00 | $+0.00 | $+0.00 | NO |
| **SLV-USD** | $5.00 | $+0.00 | $+0.00 | NO |
| **SPCX-USD** | $5.00 | $+0.00 | $+0.00 | NO |
| **TSLA-USD** | $5.00 | $+0.00 | $+0.00 | NO |
| **UNI-USD** | $5.00 | $+0.00 | $+0.00 | NO |
| **ZEC-USD** | $15.34 | $+0.00 | $+0.00 | NO |

## 4. Replay Parity Verification

All incoming WebSocket messages were recorded locally.
Replay parity requires that replaying persisted ticks through the deterministic backtester produces identical fills and equity curves within numerical precision.
