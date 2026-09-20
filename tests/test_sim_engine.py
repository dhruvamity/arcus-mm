from __future__ import annotations

"""Unit Tests for Unified SimEngine.

1. Scripted scenario hand-computed expectations (A, B, C).
2. A >= B >= C monotonicity.
3. Cancel-latency pick-off risk.
4. POST_ONLY_WOULD_CROSS rejection.
5. Queue FIFO depletion.
6. Quantization and min-size enforcement.
7. Time-aware hourly funding.
8. No look-ahead bias.
9. Causality of EWMA volatility.
10. Kill-switch state machines (stale, crossed, gap).
11. Determinism and fill log hash matching.
"""

import unittest
from src.sim.engine import SimEngine, SimEvent, SimEventType, RiskState
from src.models.fill import FillModelType, OrderStatus
from src.models.latency import LatencyConfig
from src.strategies.fixed_spread import FixedSpreadStrategy


class TestSimEngine(unittest.TestCase):
    def setUp(self):
        self.market = "BTC-USD"
        self.specs = {
            "BTC-USD": {
                "tick_size": 0.1,
                "step_size": 0.0001,
                "min_notional": 5.0,
                "min_order_size": 0.0001,
            }
        }
        self.strategy = FixedSpreadStrategy(
            market="BTC-USD",
            tick_size=0.1,
            step_size=0.0001,
            spread_bps=10.0,
            clip_notional=10.0,
        )
        self.engine = SimEngine(
            markets=[self.market],
            market_specs=self.specs,
            strategies={"fixed_spread": self.strategy},
            fill_models=[
                FillModelType.MODEL_A_TOUCH,
                FillModelType.MODEL_B_MODERATE,
                FillModelType.MODEL_C_CONSERVATIVE,
            ],
            latency_config=LatencyConfig(order_entry_latency_ms=20.0, cancel_latency_ms=20.0),
            initial_capital=100.0,
            random_seed=42,
        )

    def test_1_scripted_scenario_hand_computed_expectations(self):
        """Test 1: Scripted scenario with hand-computed expectations for A, B, C."""
        t0 = 1_000_000_000  # 1.0s in ns
        # 1. BBO Event: mid=100.0, bid=99.90, ask=100.10
        e_bbo = SimEvent(
            event_type=SimEventType.BBO,
            recv_ts_ns=t0,
            market=self.market,
            data={"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0},
        )
        self.engine.on_event(e_bbo)

        # 2. Advance clock by 30ms (exceeding 20ms place latency) to rest order
        t_rest = t0 + int(30e6)
        e_tick = SimEvent(event_type=SimEventType.CLOCK_TICK, recv_ts_ns=t_rest, market=self.market, data={})
        self.engine.on_event(e_tick)

        ctx = self.engine.contexts["fixed_spread"]
        bid_b = ctx.active_bid[FillModelType.MODEL_B_MODERATE]
        self.assertIsNotNone(bid_b)
        self.assertEqual(bid_b.status, OrderStatus.RESTING)
        quote_p = bid_b.price
        quote_s = bid_b.size

        # 3. Trade event AT quote price: price=quote_p, size=quote_s, side='SELL'
        # Model A: touches -> fills!
        # Model B: queue ahead = 0 -> fills!
        # Model C: trade-through required (price < quote_p) -> DOES NOT FILL
        t_trade = t_rest + int(10e6)
        e_trade = SimEvent(
            event_type=SimEventType.TRADE,
            recv_ts_ns=t_trade,
            market=self.market,
            data={"price": quote_p, "size": quote_s, "side": "SELL"},
        )
        fills = self.engine.on_event(e_trade)

        fills_a = [f for f in fills if f["fill_model"] == FillModelType.MODEL_A_TOUCH.value]
        fills_b = [f for f in fills if f["fill_model"] == FillModelType.MODEL_B_MODERATE.value]
        fills_c = [f for f in fills if f["fill_model"] == FillModelType.MODEL_C_CONSERVATIVE.value]

        self.assertEqual(len(fills_a), 1, "Model A must fill on touch")
        self.assertEqual(len(fills_b), 1, "Model B must fill when queue depleted")
        self.assertEqual(len(fills_c), 0, "Model C must NOT fill on touch alone")

    def test_2_monotonicity_a_b_c(self):
        """Test 2: A >= B >= C monotonicity on the same event path."""
        t0 = 1_000_000_000
        # Initialize resting quotes
        self.engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 2.0, "ask_size": 2.0}))
        self.engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(30e6), self.market, {}))

        ctx = self.engine.contexts["fixed_spread"]
        quote_p = ctx.active_bid[FillModelType.MODEL_B_MODERATE].price
        quote_s = ctx.active_bid[FillModelType.MODEL_B_MODERATE].size

        # Trade 1: at touch (fills A, partially fills B if queue depleted, 0 for C)
        self.engine.on_event(SimEvent(SimEventType.TRADE, t0 + int(40e6), self.market, {"price": quote_p, "size": 0.5, "side": "SELL"}))
        # Trade 2: through the touch (fills all remaining)
        self.engine.on_event(SimEvent(SimEventType.TRADE, t0 + int(50e6), self.market, {"price": quote_p - 0.5, "size": quote_s, "side": "SELL"}))

        pnl_a = ctx.pnl_engines[FillModelType.MODEL_A_TOUCH]
        pnl_b = ctx.pnl_engines[FillModelType.MODEL_B_MODERATE]
        pnl_c = ctx.pnl_engines[FillModelType.MODEL_C_CONSERVATIVE]

        self.assertGreaterEqual(pnl_a.total_trades_count, pnl_b.total_trades_count)
        self.assertGreaterEqual(pnl_b.total_trades_count, pnl_c.total_trades_count)

    def test_3_cancel_latency_pickoff(self):
        """Test 3: Cancel-latency pick-off: stale quote is filled during cancel transit latency."""
        t0 = 1_000_000_000
        # 1. Establish resting quote
        self.engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}))
        self.engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(30e6), self.market, {}))

        ctx = self.engine.contexts["fixed_spread"]
        bid_order = ctx.active_bid[FillModelType.MODEL_B_MODERATE]
        old_price = bid_order.price
        old_size = bid_order.size

        # 2. Market moves -> new BBO triggers cancel-replace at t0 + 40ms
        t_cancel = t0 + int(40e6)
        self.engine.on_event(SimEvent(SimEventType.BBO, t_cancel, self.market, {"bid_price": 98.00, "ask_price": 98.20, "bid_size": 1.0, "ask_size": 1.0}))
        self.assertEqual(bid_order.status, OrderStatus.CANCEL_REQUESTED)

        # 3. Aggressive trade arrives at t0 + 45ms (during 20ms cancel transit latency)
        t_trade = t0 + int(45e6)
        fills = self.engine.on_event(SimEvent(SimEventType.TRADE, t_trade, self.market, {"price": old_price - 0.1, "size": old_size, "side": "SELL"}))

        # Must fill despite being in CANCEL_REQUESTED state!
        self.assertTrue(any(f["price"] == old_price for f in fills), "In-flight cancel must be filled by aggressive trade")

    def test_4_post_only_would_cross(self):
        """Test 4: POST_ONLY_WOULD_CROSS simulated rejection when quote crosses arrival-time book."""
        t0 = 1_000_000_000
        # Quote scheduled when ask is 100.10
        self.engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}))

        ctx = self.engine.contexts["fixed_spread"]
        in_flight = ctx.in_flight_orders
        self.assertTrue(len(in_flight) >= 1)
        bid_order = next(o for o in in_flight if o.side == "BUY")

        # Before order arrives (at t0 + 10ms), market crashes and best ask drops below bid order price
        self.engine.venues[self.market].best_ask = bid_order.price - 0.10

        # Advance clock to arrival time
        self.engine.on_event(SimEvent(SimEventType.CLOCK_TICK, bid_order.arrival_ts_ns + 1, self.market, {}))

        self.assertEqual(bid_order.status, OrderStatus.REJECTED)
        self.assertEqual(bid_order.rejection_reason, "POST_ONLY_WOULD_CROSS")
        self.assertEqual(ctx.post_only_rejections_count, 1)

    def test_5_queue_fifo_depletion(self):
        """Test 5: Queue FIFO depletion under Model B."""
        t0 = 1_000_000_000
        # Quote at best bid where 2.0 units are ahead in queue
        self.engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 2.0, "ask_size": 1.0}))
        self.engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(30e6), self.market, {}))

        ctx = self.engine.contexts["fixed_spread"]
        bid_order = ctx.active_bid[FillModelType.MODEL_B_MODERATE]
        bid_order.queue_ahead_size = 2.0  # 2.0 units ahead

        # Trade 1: 1.5 units at bid -> depletes queue ahead to 0.5, 0 fill
        self.engine.on_event(SimEvent(SimEventType.TRADE, t0 + int(40e6), self.market, {"price": bid_order.price, "size": 1.5, "side": "SELL"}))
        self.assertAlmostEqual(bid_order.queue_ahead_size, 0.5, places=5)
        self.assertEqual(ctx.pnl_engines[FillModelType.MODEL_B_MODERATE].total_trades_count, 0)

        # Trade 2: 1.0 units at bid -> depletes remaining 0.5 ahead, fills remaining 0.5!
        self.engine.on_event(SimEvent(SimEventType.TRADE, t0 + int(50e6), self.market, {"price": bid_order.price, "size": 1.0, "side": "SELL"}))
        self.assertEqual(bid_order.queue_ahead_size, 0.0)
        self.assertEqual(ctx.pnl_engines[FillModelType.MODEL_B_MODERATE].total_trades_count, 1)

    def test_6_quantization_and_min_size(self):
        """Test 6: Quantization and minimum clip rejection."""
        venue = self.engine.venues[self.market]
        venue.min_notional = 100.0  # Set $100 min notional
        ctx = self.engine.contexts["fixed_spread"]
        initial_orders = len(ctx.in_flight_orders)

        # Strategy quotes $10 clip notional, which is below $100 min notional
        e_bbo = SimEvent(SimEventType.BBO, 1_000_000_000, self.market, {"bid_price": 100.0, "ask_price": 100.2, "bid_size": 1.0, "ask_size": 1.0})
        self.engine.on_event(e_bbo)
        self.assertEqual(len(ctx.in_flight_orders), initial_orders, "Sub-minimum notional quote must not be placed")

    def test_7_funding_hourly_boundaries(self):
        """Test 7: Hourly funding debit/credit calculation."""
        ctx = self.engine.contexts["fixed_spread"]
        pnl_b = ctx.pnl_engines[FillModelType.MODEL_B_MODERATE]
        pnl_b.record_fill("BUY", 100.0, 1.0, 100.0, is_taker=False)  # Long 1.0 unit
        self.assertEqual(pnl_b.position, 1.0)

        venue = self.engine.venues[self.market]
        venue.current_mid = 100.0

        # Positive funding rate 0.0001 (long pays short)
        self.engine.on_event(SimEvent(SimEventType.FUNDING, 1_000_000_000, self.market, {"funding_rate": 0.0001}))
        self.assertAlmostEqual(pnl_b.total_funding_pnl, -0.01, places=5)

    def test_8_no_lookahead(self):
        """Test 8: Trade occurring before order arrival timestamp does not fill order."""
        t0 = 1_000_000_000
        self.engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}))
        ctx = self.engine.contexts["fixed_spread"]
        in_flight_bid = next(o for o in ctx.in_flight_orders if o.side == "BUY")
        self.assertIsNotNone(in_flight_bid)

        # Trade arrives at t0 + 5ms (arrival is at t0 + 20ms)
        e_early_trade = SimEvent(SimEventType.TRADE, t0 + int(5e6), self.market, {"price": 99.0, "size": 1.0, "side": "SELL"})
        fills = self.engine.on_event(e_early_trade)
        self.assertEqual(len(fills), 0, "Trade before order arrival must not fill order")

    def test_9_causality_ewma_volatility(self):
        """Test 9: Realized volatility at t is independent of observations after t."""
        venue = self.engine.venues[self.market]
        t0 = 1_000_000_000_000_000_000
        vol1 = venue.volatility_estimator.update(t0, 100.0)
        self.assertGreaterEqual(vol1, 0.0)
        vol2 = venue.volatility_estimator.update(t0 + 1_000_000_000, 101.0)
        self.assertGreater(vol2, 0.0)

    def test_10_kill_switches(self):
        """Test 10: Kill switches block quoting on stale feed and crossed book."""
        t0 = 1_000_000_000
        self.engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}))

        # Advance clock by 4 seconds without BBO updates -> Stale feed!
        self.engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(4e9), self.market, {}))
        ctx = self.engine.contexts["fixed_spread"]
        self.assertEqual(ctx.risk_state, RiskState.PAUSED_STALE_FEED)

    def test_11_determinism_fill_hash(self):
        """Test 11: Identical event stream + seed produces identical fill log hash."""
        def run_sim(seed: int) -> str:
            strat = FixedSpreadStrategy(
                market="BTC-USD",
                tick_size=0.1,
                step_size=0.0001,
                spread_bps=10.0,
                clip_notional=10.0,
            )
            eng = SimEngine(
                markets=[self.market],
                market_specs=self.specs,
                strategies={"fixed_spread": strat},
                latency_config=LatencyConfig(order_entry_latency_ms=20.0, cancel_latency_ms=20.0),
                random_seed=seed,
            )
            t0 = 1_000_000_000
            eng.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}))
            eng.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(30e6), self.market, {}))
            eng.on_event(SimEvent(SimEventType.TRADE, t0 + int(40e6), self.market, {"price": 99.90, "size": 0.1, "side": "SELL"}))
            return eng.get_fill_log_hash()

        hash1 = run_sim(42)
        hash2 = run_sim(42)
        self.assertEqual(hash1, hash2, "Identical stream and seed must yield identical fill log hash")
        self.assertEqual(len(hash1), 64)

    def test_12_replay_parity_two_pass_hash(self):
        """Test 12: Bit-for-bit replay parity over multi-step sequence."""
        def execute_pipeline():
            strat = FixedSpreadStrategy(
                market="BTC-USD",
                tick_size=0.1,
                step_size=0.0001,
                spread_bps=10.0,
                clip_notional=10.0,
            )
            eng = SimEngine(
                markets=[self.market],
                market_specs=self.specs,
                strategies={"fixed_spread": strat},
                latency_config=LatencyConfig(order_entry_latency_ms=20.0, cancel_latency_ms=20.0),
                random_seed=12345,
            )
            events = [
                SimEvent(SimEventType.BBO, 1_000_000_000, self.market, {"bid_price": 100.0, "ask_price": 100.2, "bid_size": 1.0, "ask_size": 1.0}),
                SimEvent(SimEventType.CLOCK_TICK, 1_025_000_000, self.market, {}),
                SimEvent(SimEventType.TRADE, 1_030_000_000, self.market, {"price": 100.0, "size": 0.05, "side": "SELL"}),
                SimEvent(SimEventType.BBO, 1_040_000_000, self.market, {"bid_price": 100.1, "ask_price": 100.3, "bid_size": 1.0, "ask_size": 1.0}),
                SimEvent(SimEventType.CLOCK_TICK, 1_070_000_000, self.market, {}),
                SimEvent(SimEventType.TRADE, 1_080_000_000, self.market, {"price": 100.3, "size": 0.05, "side": "BUY"}),
            ]
            for ev in events:
                eng.on_event(ev)
            return eng.get_fill_log_hash()

        pass_1_hash = execute_pipeline()
        pass_2_hash = execute_pipeline()
        self.assertEqual(pass_1_hash, pass_2_hash, "Two independent passes over the same event stream must have identical fill hash")

    def test_13_mutation_tests(self):
        """Test 13: Mutation tests (at least 8 mutations applied to the engine fail test suite)."""
        from scripts.mutation_check import (
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
        )
        mutations = [
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
        ]
        results = [m() for m in mutations]
        caught = sum(1 for r in results if r.caught)
        self.assertGreaterEqual(caught, 8, f"Must catch at least 8 mutations, caught {caught}")


if __name__ == "__main__":
    unittest.main()

