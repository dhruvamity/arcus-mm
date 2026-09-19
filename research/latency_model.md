# Latency Pipeline & Order Lifecycle Dynamics

**Status:** IMPLEMENTED & TEST-VERIFIED  
**Date:** September 20, 2026  
**Scope:** Fulfills Mandate Sections 6 & 18 of `prompt.md`  

---

## 1. Executive Summary

Realistic passive market making simulations fail when latency is treated as a simple delay or ignored during requoting. This document defines the four-stage latency pipeline, order lifecycle state machine, and in-flight cancellation risk modeled in `src/backtester.py`.

---

## 2. Four-Stage Latency Pipeline

Every quote creation, modification, or cancellation incurs distinct physical and network latencies:

```text
Market Event (t_event)
      |
      v
1. Feed Latency (t_feed) --------> Ingress network packet arrival from WebSocket
      |
      v
2. Decision Latency (t_dec) -----> Strategy computation & signal evaluation
      |
      v
3. Send Latency (t_send) --------> Egress network transit to exchange gateway
      |
      v
4. ACK Latency (t_ack) ----------> Matching engine processing & order acceptance
      |
      v
Resting on Book (t_effective = t_event + t_feed + t_dec + t_send + t_ack)
```

### 2.1 Baseline Parameters (Milliseconds)
- **Feed Latency:** $20.0\,\text{ms}$
- **Decision Latency:** $5.0\,\text{ms}$
- **Send Transit:** $25.0\,\text{ms}$
- **Exchange ACK:** $10.0\,\text{ms}$
- **Cancel Transit:** $25.0\,\text{ms}$
- **Modify Transit:** $30.0\,\text{ms}$
- **Total Place Latency:** $60.0\,\text{ms}$
- **Total Cancel Latency:** $60.0\,\text{ms}$

Stress test regimes evaluate latency perturbations at: Baseline, $+100\,\text{ms}$, $+500\,\text{ms}$, $+1\,\text{s}$, and $+5\,\text{s}$.

---

## 3. Explicit Order State Machine & In-Flight Adverse Selection (Mandate §6)

A limit order progresses through deterministic states:

```text
[CREATED] 
    |
    v
[SUBMITTING] ----(t < t_effective: incoming trades cannot match)
    |
    v
[RESTING] <===========================\\
    |                                  || (Same-price size decrease:
    +---> [PARTIALLY_FILLED]           ||  in-place modification,
    |                                  ||  priority preserved)
    +---> [FILLED]                     ||
    |                                  //
    +---> [CANCEL_REQUESTED] =========//
              |
              | (Transit Window: t_req <= t < t_cancel_ack)
              | **ORDER IS STILL LIVE ON VENUE BOOK!**
              | **TRADES HIT AND FILL DURING THIS WINDOW**
              v
          [CANCELLED]
```

### 3.1 The In-Flight Cancellation Race Condition
When the market moves against a resting quote, the strategy requests a cancellation/requote:
1. The old quote enters `CANCEL_REQUESTED`.
2. Until the cancellation request traverses network transit and arrives at the exchange matching engine ($t_{\text{cancel\_ack}}$), **the order remains resting and vulnerable**.
3. If an aggressive counterparty hits the book during this transit interval, the old quote fills at the stale price.
4. The backtester records this fill, increments `in_flight_fills_count`, updates portfolio inventory and cash, and credits action pool replenishment.
