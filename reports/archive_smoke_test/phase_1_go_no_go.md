# Phase 1 — Early Feasibility Decision (Go / No-Go)

**Date:** 2026-09-19 13:41:09 UTC
**Target Capital Scope:** $50–$100 Experimental Research Capital  
**Decision:** **GO (CANDIDATES IDENTIFIED)**

---

## 1. Decision Rationale

1. **Candidate Availability**: **20 of 64 markets** meet all strict feasibility criteria. The hypothesis that Arcus perps offer executable passive opportunities at $50–$100 capital survived the initial screening.
2. **Zero Maker Fee Viability**: At the Base fee tier (Level 0), maker fees are **0.00 bps**. Fills are not taxed by exchange maker fees.
3. **Capital Feasibility**: Top candidates like `NEAR-USD`, `SPCX-USD`, `LIT-USD`, `UNI-USD`, `AAVE-USD` have minimum clip sizes of exactly **$5.00** (5% to 10% of total capital), allowing 2-sided quoting without margin exhaustion.
4. **Action Budget Sustainability**: At a $5.00 fill, the venue replenishes 50 actions (+1 unit per $0.10 traded). Prime candidates with 300–6,800 trades per day generate sufficient volume replenishment to sustain disciplined requote cycles.

---

## 2. Key Empirical Findings

- **Mega-Caps are Unviable for Small-Scale Passive MM**: BTC-USD (0.012 bps spread), SOL-USD (0.09 bps spread), and ETH-USD (0.53 bps spread) cannot be profitably quoted over standard REST/WS without colocated ultra-low-latency infrastructure and VIP rebate status.
- **Edge Lies in Active Mid-Caps**: Markets with $100k–$2M daily volume and 3–12 bps spreads (`HYPE-USD`, `ZEC-USD`, `NEAR-USD`, `SPCX-USD`, `LIT-USD`) provide the required spread cushion to withstand adverse selection.

---

## 3. Recommended Phase 2 Recording Universe

Select the top 5–7 candidate markets for Phase 2 high-fidelity public data recording:
1. `HYPE-USD` (Crypto)
2. `ZEC-USD` (Crypto)
3. `NEAR-USD` (Crypto)
4. `SPCX-USD` (Equities)
5. `LIT-USD` (Crypto)
6. `SLV-USD` (Commodities)
7. `UNI-USD` (Crypto)

---

## 4. Permission Gate Notice

> [!IMPORTANT]
> Per Section 1.1 and Section 10.5 of prompt.md, execution **STOPS** here.
> Human approval is required before beginning Phase 2 (Broad Mainnet Public-Data Recording).