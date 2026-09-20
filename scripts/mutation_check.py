#!/usr/bin/env python3
from __future__ import annotations

"""Programmatic Mutation Verification Suite for Arcus Unified SimEngine.

Applies deliberate code/logic mutations to SimEngine and its core
subsystems, verifying that the unit test suite FAILS on each mutation (confirming
the tests are sensitive to real defects and have no blind spots).

Mutations tested:
1. Invert Queue Priority: Model B order jumps queue ahead to 0.
2. Lookahead Bias: Orders fill before arrival timestamp on past trades.
3. Zero Latency: Cancel latency set to 0, eliminating cancel transit pickoff.
4. Funding Sign Flip: Hourly funding payment sign inverted.
5. Trade Side Semantics Inversion: Invert BUY/SELL aggressor semantics.
6. Bypass Minimum Clip: Sub-minimum notional quotes bypass validation.
7. Bypass Post-Only Crossing: Post-only order rests instead of being rejected when crossing book.
8. Disable Kill-Switch: Stale BBO watchdog ignored; quoting continues.
9. Flip Fee Accounting Sign: Maker/taker fee credited instead of debited.
10. Clamp Markout Window: Forward adverse selection markout returns clamped to constant.
"""

import sys
import unittest
from pathlib import Path
from typing import Callable, Any, Tuple, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.sim.engine import SimEngine, StrategyInstanceContext, RiskState, SimEventType
from src.models.fill import FillModelType, OrderStatus
from src.models.pnl import PnLAttributionEngine
from src.models.rate_limit import ArcusRateLimitSimulator
from tests.test_sim_engine import TestSimEngine
from tests.test_harness_integrity import TestHarnessIntegrity
from tests.test_pnl_accounting import TestPnLAccounting


class MutationResult:
    def __init__(
        self,
        mutation_id: str,
        name: str,
        target_test: str,
        description: str,
        caught: bool,
        error_msg: str = "",
    ):
        self.mutation_id = mutation_id
        self.name = name
        self.target_test = target_test
        self.description = description
        self.caught = caught
        self.error_msg = error_msg


import io


def run_targeted_test(test_class: Any, test_method_name: str) -> Tuple[bool, str]:
    """Runs a single test method and returns (failed_or_errored, failure_details)."""
    suite = unittest.TestSuite()
    suite.addTest(test_class(test_method_name))
    runner = unittest.TextTestRunner(stream=io.StringIO(), resultclass=unittest.TestResult)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        errs = result.errors + result.failures
        msg = errs[0][1].strip().split("\n")[-1] if errs else "Test failed as expected"
        return True, msg
    return False, "Test unexpectedly PASSED under mutation!"


def test_mutation_1_invert_queue() -> MutationResult:
    """Mutation 1: Invert Queue Priority in Model B (instant jump to front of queue)."""
    orig_eval = SimEngine._evaluate_fill_quantity

    def mutated_eval(self, fill_model, order, trade_side, trade_price, trade_size):
        if fill_model == FillModelType.MODEL_B_MODERATE and order.side == "BUY" and trade_side == "SELL":
            # BUG: Ignore queue ahead entirely!
            order.queue_ahead_size = 0.0
            return min(order.remaining_size, trade_size)
        return orig_eval(self, fill_model, order, trade_side, trade_price, trade_size)

    SimEngine._evaluate_fill_quantity = mutated_eval
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_5_queue_fifo_depletion")
        return MutationResult("MUT-01", "Invert Queue Priority", "TestSimEngine.test_5_queue_fifo_depletion", "Model B ignores queue ahead and fills immediately", failed, msg)
    finally:
        SimEngine._evaluate_fill_quantity = orig_eval


def test_mutation_2_lookahead_bias() -> MutationResult:
    """Mutation 2: Inject 1-event lookahead bias (early trade fills before arrival)."""
    orig_on_event = SimEngine.on_event

    def mutated_on_event(self, event):
        # BUG: Activate in-flight orders immediately regardless of timestamp!
        for ctx in self.contexts.values():
            for o in list(ctx.in_flight_orders):
                o.status = OrderStatus.RESTING
                for fm in ctx.fill_models:
                    if o.side == "BUY":
                        ctx.active_bid[fm] = o.copy()
                    else:
                        ctx.active_ask[fm] = o.copy()
            ctx.in_flight_orders.clear()
        return orig_on_event(self, event)

    SimEngine.on_event = mutated_on_event
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_8_no_lookahead")
        return MutationResult("MUT-02", "Lookahead Bias", "TestSimEngine.test_8_no_lookahead", "In-flight orders rest immediately, filling on past trades", failed, msg)
    finally:
        SimEngine.on_event = orig_on_event


def test_mutation_3_zero_latency() -> MutationResult:
    """Mutation 3: Set cancel latency to 0ms (cancels take effect instantly)."""
    orig_sample = SimEngine.sample_latency_ns

    def mutated_sample(self, action):
        if action == "cancel":
            return 0  # 0ns latency
        return orig_sample(self, action)

    SimEngine.sample_latency_ns = mutated_sample
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_3_cancel_latency_pickoff")
        return MutationResult("MUT-03", "Zero Cancel Latency", "TestSimEngine.test_3_cancel_latency_pickoff", "Cancel latency set to 0ns, eliminating transit fill risk", failed, msg)
    finally:
        SimEngine.sample_latency_ns = orig_sample


def test_mutation_4_funding_sign_flip() -> MutationResult:
    """Mutation 4: Flip sign of funding payment (credit instead of debit for longs)."""
    orig_funding = PnLAttributionEngine.apply_funding

    def mutated_funding(self, funding_rate, current_mid):
        # BUG: Flipped sign (+ instead of -)
        payment = + (self.position * current_mid * funding_rate)
        self.total_funding_pnl += payment
        self.cash += payment
        return payment

    PnLAttributionEngine.apply_funding = mutated_funding
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_7_funding_hourly_boundaries")
        return MutationResult("MUT-04", "Funding Sign Flip", "TestSimEngine.test_7_funding_hourly_boundaries", "Inverts funding payment sign from debit to credit", failed, msg)
    finally:
        PnLAttributionEngine.apply_funding = orig_funding


def test_mutation_5_trade_side_inversion() -> MutationResult:
    """Mutation 5: Invert trade side semantics (expect BUY aggressor to hit BUY maker order)."""
    orig_eval = SimEngine._evaluate_fill_quantity

    def mutated_eval(self, fill_model, order, trade_side, trade_price, trade_size):
        # BUG: Invert side semantics
        inv_side = "BUY" if trade_side == "SELL" else "SELL"
        return orig_eval(self, fill_model, order, inv_side, trade_price, trade_size)

    SimEngine._evaluate_fill_quantity = mutated_eval
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_1_scripted_scenario_hand_computed_expectations")
        return MutationResult("MUT-05", "Trade Side Semantics Inversion", "TestSimEngine.test_1_scripted_scenario_hand_computed_expectations", "Inverts taker BUY/SELL aggressor matching convention", failed, msg)
    finally:
        SimEngine._evaluate_fill_quantity = orig_eval


def test_mutation_6_min_size_bypass() -> MutationResult:
    """Mutation 6: Bypass minimum order clip size enforcement."""
    orig_sched = SimEngine._schedule_quote_update

    def mutated_sched(self, venue, ctx, fill_model, target_bid, target_ask, ts_ns):
        # Temporarily lower min_notional to 0
        old_min = venue.min_notional
        venue.min_notional = 0.0
        try:
            return orig_sched(self, venue, ctx, fill_model, target_bid, target_ask, ts_ns)
        finally:
            venue.min_notional = old_min

    SimEngine._schedule_quote_update = mutated_sched
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_6_quantization_and_min_size")
        return MutationResult("MUT-06", "Bypass Minimum Size", "TestSimEngine.test_6_quantization_and_min_size", "Bypasses minimum order notional clip validation", failed, msg)
    finally:
        SimEngine._schedule_quote_update = orig_sched


def test_mutation_7_post_only_bypass() -> MutationResult:
    """Mutation 7: Bypass POST_ONLY_WOULD_CROSS rejection check."""
    orig_process = SimEngine._process_in_flight_arrivals

    def mutated_process(self, current_ts_ns):
        # Disable post-only would cross checks
        for ctx in self.contexts.values():
            for o in list(ctx.in_flight_orders):
                if o.arrival_ts_ns <= current_ts_ns and o.status == OrderStatus.SUBMITTING:
                    o.status = OrderStatus.RESTING
                    for fm in ctx.fill_models:
                        if o.side == "BUY":
                            ctx.active_bid[fm] = o.copy()
                        else:
                            ctx.active_ask[fm] = o.copy()
                    ctx.in_flight_orders.remove(o)
        return orig_process(self, current_ts_ns)

    SimEngine._process_in_flight_arrivals = mutated_process
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_4_post_only_would_cross")
        return MutationResult("MUT-07", "Bypass Post-Only Crossing", "TestSimEngine.test_4_post_only_would_cross", "Quotes crossing the opposite book rest instead of rejecting", failed, msg)
    finally:
        SimEngine._process_in_flight_arrivals = orig_process


def test_mutation_8_disable_kill_switch() -> MutationResult:
    """Mutation 8: Disable stale BBO watchdog kill switch."""
    orig_tick = SimEngine._handle_clock_tick

    def mutated_tick(self, venue, ts_ns):
        # BUG: Do nothing on clock tick; never pause on stale feed!
        pass

    SimEngine._handle_clock_tick = mutated_tick
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_10_kill_switches")
        return MutationResult("MUT-08", "Disable Stale Watchdog", "TestSimEngine.test_10_kill_switches", "Disables stale feed detector; quoting continues unabated", failed, msg)
    finally:
        SimEngine._handle_clock_tick = orig_tick


def test_mutation_9_fee_sign_flip() -> MutationResult:
    """Mutation 9: Flip sign of fee deduction in PnL accounting."""
    orig_record_fill = PnLAttributionEngine.record_fill

    def mutated_fill(self, side, price, size, mid_at_fill, is_taker=False, ts_ns=None):
        ret = orig_record_fill(self, side, price, size, mid_at_fill, is_taker, ts_ns)
        # Flip sign of tracked fee costs
        if is_taker:
            self.taker_fee_costs = - abs(self.taker_fee_costs)
        else:
            self.maker_fee_costs = - abs(self.maker_fee_costs)
        self.total_fee_costs = - abs(self.total_fee_costs)
        return -ret

    PnLAttributionEngine.record_fill = mutated_fill
    try:
        failed, msg = run_targeted_test(TestPnLAccounting, "test_fee_separation_maker_vs_taker")
        return MutationResult("MUT-09", "Fee Sign Flip", "TestPnLAccounting.test_fee_separation_maker_vs_taker", "Inverts sign of tracked fee costs", failed, msg)
    finally:
        PnLAttributionEngine.record_fill = orig_record_fill


def test_mutation_10_markout_clamping() -> MutationResult:
    """Mutation 10: Clamp adverse selection markout returns to 0.0."""
    import tests.test_harness_integrity as harness_test_mod
    orig_compute = harness_test_mod.compute_markouts

    def mutated_markouts(*args, **kwargs):
        res = orig_compute(*args, **kwargs)
        for h in res.get("horizons", {}):
            res["horizons"][h]["mean_bps"] = 0.0
            res["horizons"][h]["median_bps"] = 0.0
        return res

    harness_test_mod.compute_markouts = mutated_markouts
    try:
        failed, msg = run_targeted_test(TestHarnessIntegrity, "test_markout_horizons_random_walk")
        return MutationResult("MUT-10", "Clamp Markout Horizons", "TestHarnessIntegrity.test_markout_horizons_random_walk", "Forces forward horizon returns to 0.0", failed, msg)
    finally:
        harness_test_mod.compute_markouts = orig_compute


def test_mutation_11_charge_funding_per_message() -> MutationResult:
    """Mutation 11: Charge funding per streaming message (causes 60x overcharge)."""
    orig_handle_funding = SimEngine._handle_funding_event

    def mutated_handle_funding(self, venue, data, ts_ns):
        rate = float(data.get("rate1h") or data.get("rate") or data.get("funding_rate") or 0.0)
        venue.predicted_funding_rate = rate
        # BUG: Settle funding on every message without checking is_settlement!
        ref_price = venue.current_mid if venue.current_mid > 0 else 1.0
        for ctx in self.contexts.values():
            for pnl_eng in ctx.pnl_engines.values():
                pnl_eng.apply_funding(rate, ref_price)

    SimEngine._handle_funding_event = mutated_handle_funding
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_15_funding_predicted_vs_settlement_regression")
        return MutationResult("MUT-11", "Charge Funding Per Message", "TestSimEngine.test_15_funding_predicted_vs_settlement_regression", "Charges funding on every predictedFunding frame (60x overcharge)", failed, msg)
    finally:
        SimEngine._handle_funding_event = orig_handle_funding


def test_mutation_12_quote_behind_touch_zero_queue() -> MutationResult:
    """Mutation 12: Treat resting quote queue depth as 0 regardless of book state."""
    orig_arrivals = SimEngine._process_in_flight_arrivals

    def mutated_arrivals(self, current_ts_ns):
        ret = orig_arrivals(self, current_ts_ns)
        for ctx in self.contexts.values():
            for fm in ctx.fill_models:
                if ctx.active_bid[fm]:
                    ctx.active_bid[fm].queue_ahead_size = 0.0
                if ctx.active_ask[fm]:
                    ctx.active_ask[fm].queue_ahead_size = 0.0
        return ret

    SimEngine._process_in_flight_arrivals = mutated_arrivals
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_14_l2_snapshot_delta_queue_depth")
        return MutationResult("MUT-12", "Zero Queue Behind Touch", "TestSimEngine.test_14_l2_snapshot_delta_queue_depth", "Treats queue ahead size as 0, ignoring book depth", failed, msg)
    finally:
        SimEngine._process_in_flight_arrivals = orig_arrivals


def test_mutation_13_never_recover_pause() -> MutationResult:
    """Mutation 13: Never recover from risk pause state (latch permanent pause)."""
    orig_set_risk = StrategyInstanceContext.set_risk_state

    def mutated_set_risk(self, market, state):
        curr = self.get_risk_state(market)
        # BUG: Once paused, never return to NORMAL
        if curr != RiskState.NORMAL and state == RiskState.NORMAL:
            return
        orig_set_risk(self, market, state)

    StrategyInstanceContext.set_risk_state = mutated_set_risk
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_16_risk_state_recovery_mechanisms")
        return MutationResult("MUT-13", "Never Recover From Pause", "TestSimEngine.test_16_risk_state_recovery_mechanisms", "Disables state machine transitions from PAUSED back to NORMAL", failed, msg)
    finally:
        StrategyInstanceContext.set_risk_state = orig_set_risk


def test_mutation_14_drop_stale_check() -> MutationResult:
    """Mutation 14: Drop stale BBO feed watchdog in clock tick."""
    orig_tick = SimEngine._handle_clock_tick

    def mutated_tick(self, venue, ts_ns):
        # BUG: Drop stale feed check; only run funding rollover
        current_hour = ts_ns // (3600 * 1_000_000_000)
        venue.last_settled_hour = current_hour

    SimEngine._handle_clock_tick = mutated_tick
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_10_kill_switches")
        return MutationResult("MUT-14", "Drop Stale Feed Watchdog", "TestSimEngine.test_10_kill_switches", "Omits stale BBO elapsed duration check on clock ticks", failed, msg)
    finally:
        SimEngine._handle_clock_tick = orig_tick


def test_mutation_15_ignore_rate_limits() -> MutationResult:
    """Mutation 15: Ignore rate limit pool exhaustion and denials."""
    orig_can_place = ArcusRateLimitSimulator.can_place_order

    def mutated_can_place(self, now_ts=None):
        return True  # BUG: Always allow place even if 0 units and in drip window

    ArcusRateLimitSimulator.can_place_order = mutated_can_place
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_18_subaccount_rate_limit_denial_and_drip")
        return MutationResult("MUT-15", "Ignore Rate Limit Denials", "TestSimEngine.test_18_subaccount_rate_limit_denial_and_drip", "Ignores exhausted rate limit pool and allows orders anyway", failed, msg)
    finally:
        ArcusRateLimitSimulator.can_place_order = orig_can_place


def test_mutation_16_recv_time_joins() -> MutationResult:
    """Mutation 16: Use event receive time instead of arrival timestamp for order fill checks."""
    orig_on_event = SimEngine.on_event

    def mutated_on_event(self, event):
        # BUG: Advance all in-flight arrivals to event.recv_ts_ns before trade check
        if event.event_type == SimEventType.TRADE:
            for ctx in self.contexts.values():
                for o in ctx.in_flight_orders:
                    o.arrival_ts_ns = event.recv_ts_ns
        return orig_on_event(self, event)

    SimEngine.on_event = mutated_on_event
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_8_no_lookahead")
        return MutationResult("MUT-16", "Recv Time Order Fill (Lookahead)", "TestSimEngine.test_8_no_lookahead", "Fills orders based on event receive time rather than arrival timestamp", failed, msg)
    finally:
        SimEngine.on_event = orig_on_event


def test_mutation_17_c_world_from_b_inventory() -> MutationResult:
    """Mutation 17: C-world shares or quotes from Model A/B inventory."""
    orig_init = SimEngine.__init__

    def mutated_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        for ctx in self.contexts.values():
            if FillModelType.MODEL_C_CONSERVATIVE in ctx.pnl_engines and FillModelType.MODEL_A_TOUCH in ctx.pnl_engines:
                # BUG: Model C uses Model A's PnL engine / inventory!
                ctx.pnl_engines[FillModelType.MODEL_C_CONSERVATIVE] = ctx.pnl_engines[FillModelType.MODEL_A_TOUCH]

    SimEngine.__init__ = mutated_init
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_17_independent_fill_worlds_quoting")
        return MutationResult("MUT-17", "C-World Shares Inventory", "TestSimEngine.test_17_independent_fill_worlds_quoting", "Model C quotes and tracks from Model A/B inventory instead of independent state", failed, msg)
    finally:
        SimEngine.__init__ = orig_init


def test_mutation_18_mid_based_min_clip_check() -> MutationResult:
    """Mutation 18: Reintroduce mid-based min-clip check on quotes (W-01 regression)."""
    from src.utils import snap_to_tick, snap_to_step
    orig_sched = SimEngine._schedule_quote_update

    def mutated_sched(self, venue, ctx, fill_model, target_bid, target_ask, ts_ns):
        # BUG: Mid-based clip comparison rejects minimum-size bids below mid
        min_clip = venue.get_min_executable_clip()
        if target_bid:
            p = float(snap_to_tick(target_bid.price, venue.tick_size))
            s = float(snap_to_step(target_bid.size, venue.step_size))
            if s * p < min_clip - 1e-6:
                target_bid = None
        if target_ask:
            p = float(snap_to_tick(target_ask.price, venue.tick_size))
            s = float(snap_to_step(target_ask.size, venue.step_size))
            if s * p < min_clip - 1e-6:
                target_ask = None
        return orig_sched(self, venue, ctx, fill_model, target_bid, target_ask, ts_ns)

    SimEngine._schedule_quote_update = mutated_sched
    try:
        failed, msg = run_targeted_test(TestSimEngine, "test_19_w01_min_size_bids_not_rejected_on_min_clip_markets")
        return MutationResult("MUT-18", "Mid-Based Min-Clip Check", "TestSimEngine.test_19_w01_min_size_bids_not_rejected_on_min_clip_markets", "Reintroduces mid-based clip validation rejecting min-size bids below mid", failed, msg)
    finally:
        SimEngine._schedule_quote_update = orig_sched


def main():
    mutations: List[Callable[[], MutationResult]] = [
        test_mutation_1_invert_queue,
        test_mutation_2_lookahead_bias,
        test_mutation_3_zero_latency,
        test_mutation_4_funding_sign_flip,
        test_mutation_5_trade_side_inversion,
        test_mutation_6_min_size_bypass,
        test_mutation_7_post_only_bypass,
        test_mutation_8_disable_kill_switch,
        test_mutation_9_fee_sign_flip,
        test_mutation_10_markout_clamping,
        test_mutation_11_charge_funding_per_message,
        test_mutation_12_quote_behind_touch_zero_queue,
        test_mutation_13_never_recover_pause,
        test_mutation_14_drop_stale_check,
        test_mutation_15_ignore_rate_limits,
        test_mutation_16_recv_time_joins,
        test_mutation_17_c_world_from_b_inventory,
        test_mutation_18_mid_based_min_clip_check,
    ]

    print("=" * 80)
    print("ARCUS SIMENGINE MUTATION VERIFICATION SUITE")
    print(f"Applying {len(mutations)} deliberate architectural mutations to verify test sensitivity...")
    print("=" * 80)

    results: List[MutationResult] = []
    for test_fn in mutations:
        res = test_fn()
        results.append(res)
        status_str = "CAUGHT (PASS)" if res.caught else "SLIPPED (FAIL)"
        print(f"[{res.mutation_id}] {res.name:32} | {status_str:14} | Target: {res.target_test}")
        if res.caught:
            print(f"        Failure Reason: {res.error_msg}")
        else:
            print("        ERROR: Unit test did not catch this mutation!")

    print("-" * 80)
    all_caught = all(r.caught for r in results)
    total_caught = sum(1 for r in results if r.caught)
    print(f"Summary: {total_caught}/{len(results)} mutations caught by unit test suite.")
    print("=" * 80)

    # Write evidence report to evidence/mutation_check.txt
    evidence_path = PROJECT_ROOT / "evidence" / "mutation_check.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with open(evidence_path, "w", encoding="utf-8") as f:
        f.write("ARCUS SIMENGINE MUTATION VERIFICATION REPORT\n")
        f.write(f"Generated: 2026-09-20 | Total Mutations: {len(results)} | Caught: {total_caught}\n\n")
        f.write("| ID | Mutation Name | Target Test | Status | Defect Description |\n")
        f.write("|---|---|---|---|---|\n")
        for r in results:
            status = "CAUGHT" if r.caught else "SLIPPED"
            f.write(f"| {r.mutation_id} | {r.name} | `{r.target_test}` | **{status}** | {r.description} |\n")
        f.write("\nDetailed Failure Traces:\n")
        for r in results:
            f.write(f"\n--- {r.mutation_id}: {r.name} ---\n")
            f.write(f"Description: {r.description}\n")
            f.write(f"Target: {r.target_test}\n")
            f.write(f"Outcome: {'CAUGHT BY TEST' if r.caught else 'UNCAUGHT'}\n")
            f.write(f"Test Exception Message: {r.error_msg}\n")

    print(f"Detailed evidence written to: {evidence_path}")
    if not all_caught:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
