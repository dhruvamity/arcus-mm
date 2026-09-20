# Quantitative Methodology & Simulation Engine Specification

**Document:** `research/methodology.md`  
**Consolidated From:** `latency_model.md`, `multiple_testing.md`, `pnl_accounting.md`, `rate_limit_economics.md`, `strategy_protocol.md`  
**Status:** CANONICAL METHODOLOGY SPECIFICATION  
**Last Updated:** 2026-09-20 (Mandate v3 §16)

---

## 1. Architecture Overview & Single Event Flow

The Arcus market-making simulation and execution platform operates on a single canonical event loop (`src/sim/engine.py`). Both historical replay and live paper trading feed identical structured event records (`BBO`, `L2_DELTA`, `TRADE`, `FUNDING`, `MARK`, `CLOCK_TICK`).

```text
Market Data Stream (WebSocket / Recorded JSONL)
                    │
                    ▼
       ┌────────────────────────┐
       │   Canonical Loader     │  (src/data/loader.py)
       │ (Chronological Order)  │
       └────────────┬───────────┘
                    │
                    ▼
       ┌────────────────────────┐
       │       SimEngine        │  (src/sim/engine.py)
       │  - LocalOrderBook L2   │
       │  - Latency Pipeline    │
       │  - Action Rate Limiter │
       │  - Risk State Machine  │
       │  - Discrete Funding    │
       └────────────┬───────────┘
                    │
                    ▼
  ┌─────────────────┴─────────────────┐
  │ Independent Fill Worlds (Model C) │
  └───────────────────────────────────┘
```

---

## 2. Latency Pipeline & Empirical Benchmark Sampling

Realistic passive market making simulations fail when latency is treated as a constant scalar or ignored during requoting. The platform models a multi-stage latency pipeline with empirical distributions derived from live ping and order round-trip time (RTT) measurements.

### 2.1 Latency Stages
1. **Feed Latency ($t_{\text{feed}}$):** Network transit from exchange gateway to host socket, plus JSON deserialization.
2. **Decision Latency ($t_{\text{dec}}$):** Strategy evaluation, signal extraction (OFI, microprice), and quote recalculation.
3. **Send Latency ($t_{\text{send}}$):** Network transit of outbound signed order payload from host to matching engine.
4. **Matching Engine ACK ($t_{\text{ack}}$):** Sequencer ingestion, validation, and book insertion.
5. **Effective Arrival Timestamp:**
   $$t_{\text{effective}} = t_{\text{event}} + t_{\text{feed}} + t_{\text{dec}} + t_{\text{send}} + t_{\text{ack}}$$

### 2.2 Empirical Latency Sampling (Fix V-11)
Instead of arbitrary hardcoded delays, `EmpiricalLatencyModel` samples transit times from recorded distribution histograms:
- **Baseline Crypto RTT (p50):** $77.8\,\text{ms}$ (interdecile range: $74.4\,\text{ms}$ to $78.8\,\text{ms}$).
- **In-flight Adverse Selection:** An order in `CANCEL_REQUESTED` state remains resting on the venue book until $t_{\text{effective\_cancel}}$. Incoming aggressive trades matching within this transit window execute against the resting quote, recording authentic in-flight adverse selection.

---

## 3. Rate-Limit Economics & Action-Pool Mechanics (Fix V-10)

On Arcus, rate limits are an economic resource budget enforced at the subaccount level, not simply an IP connection ceiling.

### 3.1 Dual Action Pools
- **Order Pool:** Starting capacity of $20,000$ action units. Consumed by `placeOrder` (1.0 unit) and `modifyOrder` (1.0 unit).
- **Cancel Pool:** Starting capacity of $40,000$ action units. Consumed by `cancelOrder` (1.0 unit) and `cancelAllOrders` ($1,000.0$ units).
- **Action Replenishment:** Realized trading volume replenishes both pools continuously:
  $$\Delta \text{Units} = \frac{\text{Fill Notional USD}}{\$0.10} = 10.0 \times \text{Notional USD}$$
  Pool capacities are bounded at their initial maximums ($20,000$ and $40,000$).

### 3.2 Exhausted-Pool Drip Regime
When a pool's balance falls below $1.0$ unit:
$$\Delta t_{\text{action}} \ge 10.0\,\text{seconds}$$
Actions attempted prior to the 10-second drip interval are rejected with rate-limit denial exceptions. Strategies must enforce threshold quoting ($\ge 2$ ticks) to prevent quote churn from exhausting the pools.

---

## 4. PnL Accounting Identity & Discrete Funding (Fix V-08, V-14)

### 4.1 Balance-Sheet Identity
At every simulation timestamp $t$, portfolio equity $E_t$ satisfies:
$$E_t = \text{Cash}_t + \text{Position}_t \cdot S_t$$
where $S_t$ is the contemporaneous mark price. Over interval $[0, t]$, net equity change decomposes without leakage into:
$$\Delta E_t = \Pi_{\text{realized}} + \Pi_{\text{mtm}} + \Pi_{\text{funding}} - C_{\text{maker\_fee}} - C_{\text{taker\_fee}}$$

### 4.2 Discrete Funding Settlement (Fix V-08)
- Streaming `predictedFunding` frames carry estimated 1-hour rates ($\sim 60$ frames/hour). These update predictive state but **never debit cash**.
- Cash is debited **strictly at discrete settlement timestamps** ($t_k$ on hourly clock boundaries or explicit settlement events):
  $$\text{Cash}_{t_k} \leftarrow \text{Cash}_{t_k} - \left(\text{Position}_{t_k} \cdot S_{t_k} \cdot F_{t_k}\right)$$
  This prevents the 60x overcharge bug where continuous ticks repeatedly debited hourly rates.

### 4.3 Executable-Side Forced Liquidation
When risk thresholds or stop-loss limits are breached, positions cannot be liquidated at mid-price. Longs execute against contemporaneous Best Bid; shorts execute against Best Ask with slippage and standard 2.25 bps taker fees.

---

## 5. Forward Markout Attribution & Adverse Selection

Adverse selection is evaluated as an empirical markout against reference prices across standard horizons:
$$H \in [100\,\text{ms}, 500\,\text{ms}, 1\,\text{s}, 5\,\text{s}, 10\,\text{s}, 30\,\text{s}, 60\,\text{s}]$$

For a passive fill at $t_{\text{fill}}$ with price $P_{\text{fill}}$:
- **Maker BUY:** $\text{AS}_{\text{bps}}(H) = \frac{P_{\text{fill}} - S_{t_{\text{fill}} + H}}{P_{\text{fill}}} \cdot 10,000$
- **Maker SELL:** $\text{AS}_{\text{bps}}(H) = \frac{S_{t_{\text{fill}} + H} - P_{\text{fill}}}{P_{\text{fill}}} \cdot 10,000$

Observations extending past recording boundaries ($t_{\text{fill}} + H > t_{\text{end}}$) are dropped rather than clamped. Markout metrics are tracked strictly as research diagnostics and are never subtracted from balance-sheet equity.

---

## 6. Statistical Multiple-Testing Control (Fix V-25)

Searching across candidate parameters, spread multipliers, and market universes creates false-discovery bias.

### 6.1 Step-Down Holm-Bonferroni FWER Control
For a family of $M$ candidate configurations, raw p-values are ranked in ascending order:
$$p_{(1)} \le p_{(2)} \le \dots \le p_{(M)}$$
For rank $k = 1, \dots, M$, the hypothesis is tested against:
$$\alpha_k = \frac{\alpha}{M - k + 1}$$
Testing terminates the moment $p_{(k)} > \alpha_k$, retaining all subsequent null hypotheses.

### 6.2 Sample Size & Power Formulation (Fix V-25)
Sample size requirements for statistical power $\ge 80\%$ at one-sided $\alpha = 0.10$ incorporate design effect ($\text{DEFF}$) from intra-day serial correlation:
$$N = \left(\frac{z_\alpha + z_\beta}{\text{edge} / \sigma}\right)^2 \cdot \text{DEFF}$$
where $z_\alpha = 1.2816$, $z_\beta = 0.8416$, and $\sigma$ is the empirical standard deviation of net return per fill.

---

## 7. Machine-Enforced Validation Gates

Before any candidate configuration is considered validated, it must satisfy:
1. **Gate 1 (Fill Count):** $N \ge 300$ fills ($N \ge 100$ on low-frequency pairs).
2. **Gate 2 (Positive Expectancy):** Mean net bps per fill $> 0.0$.
3. **Gate 3 (Confidence Bound):** $90\%$ lower confidence bound $> 0.0\,\text{bps}$.
4. **Gate 4 (Temporal Consistency):** Positive daily PnL on $\ge 3$ of 5 OOS days.
5. **Gate 5 (PnL Concentration):** Max single-day PnL share $\le 50\%$.
6. **Gate 6 (Drawdown Bound):** Peak-to-trough intraday drawdown $< 10.0\%$.
7. **Gate 7 (Capital Envelope):** Zero breaches of $\$100$ capital envelope.
8. **Gate 8 (Fill Monotonicity):** $\text{Fills}(A) \ge \text{Fills}(B) \ge \text{Fills}(C)$.
