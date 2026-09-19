"""State Reconciliation Engine for Arcus MM Execution Stack.

Fulfills Mandate Section 10:
- Reconciles positions, open orders, and fills against exchange venue state
- Detects discrepancies, missing orders, and ghost orders
- Emits structured ReconciliationReport and flags Sev-1 mismatches
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import time


@dataclass
class ReconciliationReport:
    timestamp: float
    is_clean: bool
    position_discrepancies: List[Dict[str, Any]] = field(default_factory=list)
    order_discrepancies: List[Dict[str, Any]] = field(default_factory=list)
    balance_discrepancy: float = 0.0
    sev1_triggered: bool = False
    details: str = "Clean"


class ExecutionReconciler:
    """Performs state-vs-venue reconciliation for orders, positions, and equity."""

    def __init__(self, tolerance_size: float = 1e-6, tolerance_cash: float = 0.05):
        self.tolerance_size = tolerance_size
        self.tolerance_cash = tolerance_cash
        self.history: List[ReconciliationReport] = []

    def reconcile(
        self,
        local_positions: Dict[str, float],
        venue_positions: Dict[str, float],
        local_open_order_ids: List[str],
        venue_open_order_ids: List[str],
        local_cash: float,
        venue_cash: float,
    ) -> ReconciliationReport:
        """Compares local execution state against venue ground truth."""
        pos_errors = []
        order_errors = []
        sev1 = False

        # 1. Position reconciliation
        all_markets = set(local_positions.keys()).union(venue_positions.keys())
        for mkt in all_markets:
            loc_pos = local_positions.get(mkt, 0.0)
            ven_pos = venue_positions.get(mkt, 0.0)
            diff = abs(loc_pos - ven_pos)
            if diff > self.tolerance_size:
                pos_errors.append({
                    "market": mkt,
                    "local_position": loc_pos,
                    "venue_position": ven_pos,
                    "delta": loc_pos - ven_pos,
                })
                sev1 = True

        # 2. Order reconciliation
        local_set = set(local_open_order_ids)
        venue_set = set(venue_open_order_ids)

        ghost_orders = list(venue_set - local_set)
        if ghost_orders:
            order_errors.append({
                "type": "GHOST_ORDERS",
                "order_ids": ghost_orders,
                "description": "Orders active on venue but missing in local state",
            })
            sev1 = True

        missing_orders = list(local_set - venue_set)
        if missing_orders:
            order_errors.append({
                "type": "MISSING_ORDERS",
                "order_ids": missing_orders,
                "description": "Orders resting in local state but not found on venue",
            })

        # 3. Cash balance reconciliation
        cash_diff = abs(local_cash - venue_cash)
        if cash_diff > self.tolerance_cash:
            if cash_diff > 1.0:
                sev1 = True

        is_clean = len(pos_errors) == 0 and len(order_errors) == 0 and cash_diff <= self.tolerance_cash
        details = "CLEAN" if is_clean else f"MISMATCH: {len(pos_errors)} pos diffs, {len(order_errors)} order diffs, cash delta ${cash_diff:.2f}"

        report = ReconciliationReport(
            timestamp=time.time(),
            is_clean=is_clean,
            position_discrepancies=pos_errors,
            order_discrepancies=order_errors,
            balance_discrepancy=cash_diff,
            sev1_triggered=sev1,
            details=details,
        )
        self.history.append(report)
        return report
