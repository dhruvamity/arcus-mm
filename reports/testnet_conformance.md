# Arcus Testnet Conformance & Order-Path Verification Report
> **Generated:** `2026-09-20T20:28:39Z`  
> **Governance Status:** `BLOCKED: APPROVE_TESTNET_FAUCET_FUNDING = NO`  
> **Target Market:** `BTC-USD`  
> **Venue:** Arcus Testnet (`https://api.testnet.arcus.xyz`)

## 1. Governance Halt Notice

> [!IMPORTANT]
> **Single-Line Governance Halt Notice (Mandate v5 §1 Rule 2):**  
> `BLOCKED: APPROVE_TESTNET_FAUCET_FUNDING = NO. Testnet order placement and live faucet funding halted per governance constraints.`

In accordance with Mandate v5 Section 1 Rule 2 and Section 5, zero mutating testnet requests, faucet mints, or signed order actions were dispatched. Mainnet execution remains hard-locked under `APPROVE_MAINNET_ORDERS = NO` and the two-key safety guard.

## 2. Testnet Conformance Specification Matrix

The following 12 venue interactions are implemented and staged in `src/exec/live_engine.py` and `scripts/testnet_conformance.py` awaiting testnet faucet approval (`APPROVE_TESTNET_FAUCET_FUNDING = YES`):

| ID | Interaction | Expected Venue Behaviour | Implementation Status |
|---|---|---|---|
| **TC-01** | ALO Place Far from Touch | HTTP 202 ACK; status `RESTING` on orderbook | **STAGED / GUARDED** |
| **TC-02** | In-Place Modify (Size Decrease) | Queue priority preserved; modifies remaining size | **STAGED / GUARDED** |
| **TC-03** | Cancel Single Order | Immediate removal; cancel reason `USER_CANCELED` | **STAGED / GUARDED** |
| **TC-04** | `cancelAllOrders` (Market Scope) | Bulk cancellation; cost 1,000 cancel pool units | **STAGED / GUARDED** |
| **TC-05** | `scheduleCancel` (Dead-Man's Switch) | Deadline armed (5s-300s); auto-cancels if unrefreshed | **STAGED / GUARDED** |
| **TC-06** | Post-Only Crossing Rejection | Immediate reject code `POST_ONLY_WOULD_CROSS` | **STAGED / GUARDED** |
| **TC-07** | Below Min-Notional Rejection | Immediate reject code `MIN_NOTIONAL_VIOLATION` | **STAGED / GUARDED** |
| **TC-08** | Tick/Step Quantization Violation | Immediate reject code `QUANTIZATION_INVALID` | **STAGED / GUARDED** |
| **TC-09** | Self-Trade Prevention | Crossing own resting order rejects aggressor | **STAGED / GUARDED** |
| **TC-10** | Rate Limit Pool Read-back | Subaccount order/cancel pool query via `/v1/rateLimit` | **STAGED / GUARDED** |
| **TC-11** | First Natural Fill Priority | FIFO execution behind reconstructed depth | **STAGED / GUARDED** |
| **TC-12** | Account & Position Reconcile | Periodic REST reconciliation against `/v1/positions` | **STAGED / GUARDED** |

## 3. Order-Path Latency Characterization

- **Status:** `PROVISIONAL` (Derived from empirical REST `/v1/time` benchmarks pending testnet order authorization).
- **Canonical Baseline (REST p50):** `173.99 ms`.
- **Canonical Tail (REST p95):** `386.86 ms`.
- **Pre-Declared Sensitivity Grid:** `[25.0, 60.0, 150.0, 300.0, 700.0] ms` (W-08 / configs/latency_model.yaml).

## 4. Architectural Model Alignments & Simulator Feedback

1. **Taker Speed Bump Modeling (W-05):** Venue enforces a 50 ms delay for aggressive taker flow; maker ALO placements and cancels bypass this queue, giving in-flight cancels priority over aggressive fills.
2. **Discrete Funding (V-08):** Discrete hourly settlement on integer hour boundaries confirmed; continuous streaming funding frames provide predicted rates without debiting balance.
3. **Queue Position Re-computation (V-07):** New quotes join the tail of arrival-time depth; size decreases preserve queue priority while price changes cancel-replace.
4. **Two-Key Mainnet Guard (W-13 / §5.3):** Any mainnet mutating path requires both `mainnet_order_lock=False` and the secret CLI confirmation phrase.

## 5. Next Steps to Unlock Active Conformance

1. Human operator updates `APPROVE_TESTNET_FAUCET_FUNDING = YES` in governance settings.
2. Run `.venv/bin/python scripts/testnet_conformance.py --market BTC-USD` to execute live 500-sample testnet order-path benchmark.
3. Replace provisional latency numbers with measured place-ack, cancel-ack, and fill-ack RTT distributions.
