# Arcus MM Engineering Blockers Resolution Report

**Date:** 2026-09-20 00:43:00 UTC  
**Scope:** Immediate Resolution of P0 Engineering Blockers (§4 of prompt.md)  
**Verification:** Automated Unit Test Suite (`tests/test_backtester_execution.py`)

---

## 1. Summary of Resolved P0 Blockers

| Blocker ID | Affected Component | Defect Description | Resolution Applied | Verification Status |
|---|---|---|---|---|
| **P0-1** | `src/backtester.py` | `record_fill()` called with unexpected keyword argument `adverse_selection_bps=1.0`, raising `TypeError` upon simulated fills. Trade `notional` attribute lookup caused `AttributeError`. | Removed `adverse_selection_bps` from `record_fill()` call to preserve exact accounting identity. Replaced hard lookup with safe `getattr(row, "notional", row.price * row.size)`. | **RESOLVED** (`test_backtester_minimal_end_to_end_run` passes) |
| **P0-2** | `src/walk_forward.py` & `scripts/run_walk_forward.py` | `Optional` used without import in `src/walk_forward.py`, causing `NameError` during type annotation evaluation. `scripts/run_walk_forward.py` lacked `sys.path` project root, failing CLI execution. | Added `Optional` to `typing` imports in `src/walk_forward.py`. Added `sys.path.insert(0, ...)` to `scripts/run_walk_forward.py`. Added fallback `.get("is_sustainable")`. | **RESOLVED** (`test_walk_forward_cli_smoke` passes) |
| **P0-3** | `src/paper_trader.py` | `_telemetry_loop()` called `self.rate_limiter.get_pool_status()`, which was unimplemented in `ArcusRateLimitSimulator` and `RateLimiter`, crashing the paper trader after 60 seconds. | Implemented `get_pool_status()` on both `ArcusRateLimitSimulator` and `RateLimiter`, returning real-time orders, cancels, actions used, and pool capacity. | **RESOLVED** (`test_paper_telemetry_after_60_seconds_equivalent` passes) |

---

## 2. Code Diffs & Verification Commands

### P0-1: Backtester Signature Fix (`src/backtester.py`)
```diff
@@ -125,7 +125,7 @@
                 "side": row.side,
                 "price": row.price,
                 "size": row.size,
-                "notional": row.notional,
+                "notional": getattr(row, "notional", getattr(row, "price", 0.0) * getattr(row, "size", 0.0)),
             })

@@ -240,7 +240,6 @@
                                 price=self.active_bid_order.price,
                                 size=fill_qty,
                                 mid_at_fill=self.latest_mid_price,
-                                adverse_selection_bps=1.0,  # Empirical conservative baseline
                             )
```

### P0-2: Walk-Forward Import & CLI Fix (`src/walk_forward.py`)
```diff
@@ -12,1 +12,1 @@
-from typing import Dict, List, Tuple, Any
+from typing import Dict, List, Tuple, Any, Optional
```

### P0-3: Rate Limiter Telemetry API (`src/models/rate_limit.py` & `src/rate_limiter.py`)
```python
def get_pool_status(self) -> Dict[str, Any]:
    total_actions = (
        self.orders_placed
        + self.orders_modified
        + self.orders_cancelled
        + (self.cancel_all_count * 1000)
    )
    return {
        "order_units_available": self.order_units_available,
        "cancel_units_available": self.cancel_units_available,
        "order_pool_cap": self.order_pool_cap,
        "cancel_pool_cap": self.cancel_pool_cap,
        "orders_placed": self.orders_placed,
        "orders_modified": self.orders_modified,
        "orders_cancelled": self.orders_cancelled,
        "cancel_all_count": self.cancel_all_count,
        "total_actions_used": total_actions,
        "fills_generated": self.fills_generated,
        "total_fill_notional": self.total_fill_notional,
        "pool_exhaustion_count": self.pool_exhaustion_count,
    }
```

### Automated Verification Output
```
Ran 3 tests in 0.005s

OK (tests.test_backtester_execution)
```
