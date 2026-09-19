# Rate-Limit Economics & Action Pool Mechanics on Arcus

**Author:** Quantitative Trading Systems & Risk Engineering Agent  
**Repository:** `arcus-mm`  
**Date:** 2026-09-20 00:44:00 UTC  
**Mandate Reference:** Section 5 of [prompt.md](../prompt.md)

---

## 1. Executive Summary

On Arcus, rate limits are an **economic budget constraint**, not an IT observability metric. Because order mutations do not consume monetary transaction fees, the exchange protects the sequencer and matching engine via dual subaccount-level action pools:

1. **Order Pool**: 20,000 unit starting capacity (consumed by `placeOrder` and `modifyOrder`).
2. **Cancel Pool**: 40,000 unit starting capacity (consumed by `cancelOrder` and `cancelAllOrders`).

A market maker that churns quotes naively without threshold discipline exhausts these pools within hours, collapsing into the crippled **exhausted-pool drip regime (1 action per 10 seconds)**, resulting in severe adverse selection and stale quote toxicity.

---

## 2. Mathematical Modeling of Subaccount Pools

### 2.1 Action Costs & Pool Mapping
- **Initial Placement (`placeOrder`)**:
  $$\text{Cost} = 1.0\text{ order unit}$$
- **Modification (`modifyOrder`)**:
  $$\text{Cost} = 1.0\text{ order unit}$$
  *(Crucial distinction: modifying an order consumes only 1 order unit and 0 cancel units).*
- **Individual Cancellation (`cancelOrder`)**:
  $$\text{Cost} = 1.0\text{ cancel unit}$$
- **Mass Cancellation (`cancelAllOrders`)**:
  $$\text{Cost} = 1,000.0\text{ cancel units}$$

### 2.2 Replenishment Dynamics
Trading volume continuously replenishes both pools at the rate of:
$$\Delta \text{Units} = \frac{\text{Realized Fill Notional USD}}{\$0.10} = 10.0 \times \text{Notional USD}$$

However, headroom cannot exceed initial pool capacity:
$$\text{Available Order Units}(t) = \min\left(20,000, \text{Available}(t) + 10.0 \times \text{Fill Notional}\right)$$
$$\text{Available Cancel Units}(t) = \min\left(40,000, \text{Available}(t) + 10.0 \times \text{Fill Notional}\right)$$

### 2.3 Exhausted Pool Drip Regime
When a pool's units drop below 1.0:
$$\Delta t_{\text{action}} \ge 10.0\text{ seconds}$$
Any action attempted before the 10-second interval elapses is rejected or simulated as an exhaustion event.

---

## 3. Naive Quoting Churn vs. Event-Driven Discipline

### 3.1 The Failure Mode of Naive Polling MM
Consider a naive market-making bot quoting two sides (bid and ask) with a fixed 2-second cancel-replace polling loop:
- Placements: 2 orders every 2 seconds $\rightarrow 1.0\text{ place/sec}$.
- Cancellations: 2 cancels every 2 seconds $\rightarrow 1.0\text{ cancel/sec}$.

$$\text{Time to Order Pool Exhaustion} = \frac{20,000\text{ units}}{1.0\text{ unit/sec}} = 20,000\text{ s} \approx \mathbf{5.56\text{ hours}}$$
$$\text{Time to Cancel Pool Exhaustion} = \frac{40,000\text{ units}}{1.0\text{ unit/sec}} = 40,000\text{ s} \approx \mathbf{11.11\text{ hours}}$$

Both pools are completely exhausted mid-session on Day 1. At $50–$100 experimental capital, trading volume ($5–$15 clips) is insufficient to replenish 3,600 units/hour.

### 3.2 Event-Driven Requote Discipline (2-Tick Threshold)
To eliminate quote churn:
1. **Requote Threshold ($\Delta_{\text{ticks}} \ge 2$)**: Quotes are only modified when fair value or BBO shifts by at least 2 ticks.
2. **In-Place Modification for Size Reductions**: Modifying quote size downwards at the same price preserves queue priority and consumes only 1 order unit (saving 1 cancel unit).
3. **Target Efficiency**: Target actions per fill ratio must remain $\le 5.0$ actions/fill.

---

## 4. Backtester & Paper Engine Specification

The simulator implementation in `src/models/rate_limit.py` enforces:
1. Separate tracking of `orders_placed`, `orders_modified`, `orders_cancelled`, `cancel_all_count`.
2. Drip enforcement with virtual and real monotonic clocks.
3. Telemetry interface `get_pool_status()` providing instantaneous visibility into available headroom and exhaustion events.
