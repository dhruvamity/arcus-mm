# Arcus MM — Mainnet Canary Deployment Plan

**Date:** `2026-09-20`  
**Status:** `DESIGN SPECIFICATION ONLY — DORMANT UNTIL GATES PASS`  
**Target Venue:** Arcus Mainnet (`https://api.arcus.xyz`, `wss://api.arcus.xyz/ws`)  
**Mandate Reference:** Mandate v5 §8 (Workstream E)  

---

## 1. Prerequisites & Gating Conditions

> [!IMPORTANT]
> **MAINNET CANARY CANNOT RUN UNDER CURRENT GOVERNANCE.**  
> Real mainnet trading is strictly locked (`APPROVE_MAINNET_ORDERS = NO`). This plan is an approved architectural specification defining how canary testing will proceed **if and only if** all prior empirical validation gates pass and explicit written human approval is granted.

Before this canary plan can be activated, the following gates must be met:
1. **Gate G4 (OOS Walk-Forward Protocol):** Out-of-sample evaluation on tune-week data (Sep 21–25) produces at least one strategy-market candidate with a machine-verified verdict of `VALIDATED` under the day-level paired t-test, Holm-Bonferroni FWER control, and 10,000-sample block bootstrap.
2. **Gate G5a (Testnet Strategy Conformance):** Live execution loop running against Arcus testnet demonstrates zero rejected orders, flawless `scheduleCancel` dead-man's switch refreshes, subaccount rate-limit conformance, and clean REST/WS state reconciliation.
3. **Explicit Written Human Approval:** The human operator explicitly sets `APPROVE_MAINNET_ORDERS = YES` in governance and executes the run command with the cryptographic confirmation phrase.
4. **Two-Key Mainnet Guard:** Both keys must be satisfied simultaneously:
   - Key 1: `mainnet_order_lock=False` in configuration
   - Key 2: CLI environment token `ARCUS_MAINNET_MUTATING_CONFIRMATION='I_ACCEPT_PERMANENT_LOSS_OF_FUNDS'`

---

## 2. Market Selection & Order Mechanics

### 2.1 Single Instrument Scope
- The canary operates on **exactly one market** chosen from the highest-ranked `VALIDATED` candidate from Gate G4 (recommended: `ETH-USD`).
- Multi-market, cross-asset, or multi-account deployments are strictly prohibited during canary phase.

### 2.2 Order Type & Quantization Rules
- **Order Type:** Strictly Post-Only (Add Liquidity Only / ALO). Any order that would take liquidity crosses is rejected venue-side and client-side.
- **Order Size:** Minimum executable clip size only (e.g. $10.00 notional, well above the $5.00 venue floor `minOrderNotional`).
- **Inventory Ceiling:** Absolute hard maximum inventory of **2 clips** ($20.00 notional).
- **Reduce-Only Unwind:** If inventory reaches 2 clips on one side, quoting on that side is immediately suppressed. The opposing quote is marked `reduce_only=True` to passively work off the position. If inventory exceeds 2 clips (due to latency race), an aggressive IOC reduce-only order unwinds the excess back to 1 clip.

---

## 3. Hard Loss Limits & Circuit Breakers

The canary engine continuously tracks cumulative and daily equity delta:

$$\Delta\text{Equity}_t = \text{Realized PnL}_t + \text{Unrealized MTM}_t - \text{Fees}_t + \text{Funding}_t$$

| Circuit Breaker | Trigger Threshold | Engine Action | Recovery Mechanism |
|---|---|---|---|
| **Daily Loss Stop** | Cumulative Day Net Equity $\le -\$5.00$ | Cancel all resting orders, market-flatten open position, transition to `PAUSED_DAILY_STOP`. | Manual review required; no automatic restart until next UTC day (00:00 UTC). |
| **Total Canary Stop** | Lifetime Canary Net Equity $\le -\$15.00$ | Immediate emergency cancel-all, market flatten, write diagnostic dump, transition to `HALTED_PERMANENT`. | Canary terminated permanently. Requires code revision and new pre-registration. |
| **Hourly Sanity Invariant** | $|\Delta\text{Equity}_{\text{1h}}| > \$2.00$ | Immediate quote cancellation, state transition to `PAUSED_ANOMALY`. | Operator inspection of tape and fills. |
| **Rate Limit Backpressure** | Subaccount pool $< 10$ actions | Suspend quoting until pool drips above 30. | Automatic drip recovery. |

---

## 4. Venue Liveness & Safety Mechanisms

### 4.1 Dead-Man's Switch (`scheduleCancel`)
- At engine startup and every **15 seconds** thereafter, the engine sends a signed `scheduleCancel` RPC setting a cancellation deadline **60 seconds** in the future.
- If the trading process crashes, network connectivity fails, or the event loop hangs, Arcus venue automatically cancels all open resting quotes within 60 seconds of the last heartbeat.

### 4.2 Stale-Feed Watchdog
- Every cycle of the execution loop checks `time.time() - last_bbo_ts`.
- If no BBO frame or L2 update has arrived within **5.0 seconds**, the engine logs a warning, cancels resting quotes, and transitions to `PAUSED_STALE_FEED` until fresh valid quotes arrive.

### 4.3 Margin Mode Initialization
- Before submitting the very first order, the engine calls `GET /v1/positions` and `GET /v1/account` to confirm that the account margin mode is correctly configured (e.g. `isolated` or `cross` per strategy spec) and that no legacy rogue positions exist.
- Per Arcus venue mechanics, margin mode cannot be altered while an open position exists.

---

## 5. Session Calendar & Asset Regime Restrictions

1. **Crypto Markets (`ETH-USD`, `BTC-USD`, `SOL-USD`):**
   - Traded 24/7, subject to continuous heartbeat and rate-limit tracking.
2. **Equity & Commodity Perps (`SPY-USD`, `QQQ-USD`, `AMD-USD`, `GLD-USD`):**
   - **Cash Hours Only (US-RTH):** Quotes are submitted strictly between **13:30 UTC and 19:55 UTC** on US equity trading days.
   - **Mandatory Flatten Before Close:** At 19:55 UTC (5 minutes before the 20:00 UTC NYSE close), all resting quotes are withdrawn, and any residual open inventory is flattened to exactly **0 units**.
   - **Weekend Restriction:** No orders or open positions may be carried over the weekend (Friday 20:00 UTC to Sunday 22:00 UTC).

---

## 6. Daily Sim-to-Live Parity Comparison

To ensure that live execution faithfully mirrors simulated behavior and is not experiencing unexpected toxic flow:
1. **Parallel Shadow Simulation:** A paper instance of `SimEngine` runs concurrently on the exact same market tape during the canary session.
2. **Daily Metrics Reconciled:**
   - **Fill Count Parity:** Ratio of Live Fills to Model C Fills (expected range: $0.80 \le \text{Ratio} \le 1.25$).
   - **Realized Slippage:** Live fill price vs arrival mid price.
   - **Post-Fill Markout Drag (15s & 60s):** Empirical adverse selection on live fills vs simulated fills.
3. **Parity Divergence Circuit Breaker:**
   - If live adverse selection markout is worse than simulated markout by $> 2.0$ bps over $\ge 20$ fills:
   - **Action:** Canary is automatically halted. Investigation required for toxic order flow, queue front-running, or unexpected speed-bump latency disadvantages.

---

## 7. Canary Success Criteria & Abort Conditions

### 7.1 Canary Duration
- **Maximum Lifespan:** Exactly **5 consecutive trading days** (or 150 total fills, whichever occurs first).

### 7.2 Pre-Declared Success Criteria
At the conclusion of the 5-day canary run, the deployment is declared a **SUCCESS** only if:
1. **Net Equity Change:** $\Delta\text{Equity}_{\text{total}} \ge -\$2.50$ (cumulative loss does not exceed $2.50, demonstrating survival of adverse selection and fee drag within acceptable pilot bounds).
2. **Parity Agreement:** Live fill markouts agree with simulated Model C markouts within 1.5 bps ($p > 0.05$ on two-sample Kolmogorov-Smirnov test).
3. **Operational Flawlessness:**
   - 0 unhandled exceptions or crashes
   - 0 missed dead-man's switch refreshes
   - 0 rate-limit HTTP 429 penalties
   - 0 accidental taker trades (100% of opening fills were ALO post-only maker).

### 7.3 Abort Conditions
The canary is immediately and permanently **ABORTED** upon:
- Breaching the $15.00 lifetime stop-loss
- Breaching the $5.00 daily stop-loss twice
- Any order rejection indicating a protocol violation (e.g. `InvalidRequest`, non-positive spread, self-trade detection)
- Any attempt to bypass the two-key mainnet guard.

### 7.4 Scaling Prohibition
Under no circumstances may position size, clip count, or market universe be expanded based on canary results alone. Scaling requires a full post-canary audit report, stakeholder signoff, and a new pre-registration protocol.
