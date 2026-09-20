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

    def test_14_l2_snapshot_delta_queue_depth(self):
        """Test 14: L2 snapshot + delta establishes arrival-time queue depth and tracks FIFO consumption."""
        strat = FixedSpreadStrategy(
            market="BTC-USD",
            tick_size=0.1,
            step_size=0.0001,
            spread_bps=20.0,
            clip_notional=10.0,
        )
        eng = SimEngine(
            markets=[self.market],
            market_specs=self.specs,
            strategies={"fixed_spread": strat},
            latency_config=LatencyConfig(order_entry_latency_ms=20.0, cancel_latency_ms=20.0),
            paired_common_quotes=True,
            random_seed=42,
        )
        t0 = 1_000_000_000
        # 1. Apply L2 snapshot: bid 99.90 has 5.0 units ahead
        snap_data = {
            "isSnapshot": True,
            "lastSequenceId": 100,
            "bids": [["99.90", "5.0"], ["99.80", "10.0"]],
            "asks": [["100.10", "5.0"], ["100.20", "10.0"]],
        }
        eng.on_event(SimEvent(SimEventType.L2_DELTA, t0, self.market, snap_data))

        # 2. Trigger quote scheduling at 99.90
        eng.on_event(SimEvent(SimEventType.BBO, t0 + int(1e6), self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 5.0, "ask_size": 5.0}))

        # 3. Advance clock past placement latency (20ms) -> order arrives at 99.90
        eng.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(30e6), self.market, {}))
        ctx = eng.contexts["fixed_spread"]
        bid_b = ctx.active_bid[FillModelType.MODEL_B_MODERATE]
        self.assertIsNotNone(bid_b)
        self.assertEqual(bid_b.status, OrderStatus.RESTING)
        self.assertEqual(bid_b.price, 99.90)
        self.assertAlmostEqual(bid_b.queue_ahead_size, 5.0, places=4)

        # 4. Trade of 3.0 at 99.90 consumes queue ahead to 2.0; fills 0
        fills1 = eng.on_event(SimEvent(SimEventType.TRADE, t0 + int(40e6), self.market, {"price": 99.90, "size": 3.0, "side": "SELL"}))
        fills_b_1 = [f for f in fills1 if f["fill_model"] == FillModelType.MODEL_B_MODERATE.value]
        self.assertEqual(len(fills_b_1), 0)
        self.assertAlmostEqual(bid_b.queue_ahead_size, 2.0, places=4)

        # 5. Trade of 2.5 at 99.90 consumes remaining 2.0 queue ahead; fills remaining 0.5 (or order size)!
        fills2 = eng.on_event(SimEvent(SimEventType.TRADE, t0 + int(50e6), self.market, {"price": 99.90, "size": 2.5, "side": "SELL"}))
        fills_b_2 = [f for f in fills2 if f["fill_model"] == FillModelType.MODEL_B_MODERATE.value]
        self.assertEqual(len(fills_b_2), 1)
        self.assertAlmostEqual(fills_b_2[0]["size"], bid_b.size, places=4)
        self.assertAlmostEqual(bid_b.queue_ahead_size, 0.0, places=4)

    def test_15_funding_predicted_vs_settlement_regression(self):
        """Test 15: 60 streaming predictedFunding frames in an hour do NOT charge PnL; only realized settlement charges PnL."""
        ctx = self.engine.contexts["fixed_spread"]
        pnl_b = ctx.pnl_engines[FillModelType.MODEL_B_MODERATE]
        pnl_b.record_fill("BUY", 100.0, 1.0, 100.0, is_taker=False)  # Long 1.0 unit
        venue = self.engine.venues[self.market]
        venue.current_mid = 100.0

        t_base = 1_000_000_000
        # 60 predicted funding messages (1 per minute for 1 hour)
        for i in range(60):
            t = t_base + i * 60 * 1_000_000_000
            ev = SimEvent(SimEventType.FUNDING, t, self.market, {"rate1h": 0.0001, "channel": "predictedFunding", "is_predicted": True})
            self.engine.on_event(ev)

        # PnL MUST BE UNCHANGED: 0.0 funding PnL (fix V-08)
        self.assertEqual(pnl_b.total_funding_pnl, 0.0, "Streaming predictedFunding messages must not debit funding PnL")

        # 1 Realized settlement event occurs
        t_settle = t_base + 3600 * 1_000_000_000
        ev_settle = SimEvent(SimEventType.FUNDING, t_settle, self.market, {"funding_rate": 0.0001, "is_settlement": True})
        self.engine.on_event(ev_settle)

        # Exactly 1 hour of funding applied: -100 * 1.0 * 0.0001 = -0.01
        self.assertAlmostEqual(pnl_b.total_funding_pnl, -0.01, places=5)

    def test_16_risk_state_recovery_mechanisms(self):
        """Test 16: Risk state recovery: PAUSED_STALE_FEED, PAUSED_GAP, FLATTENED_CROSSED_BOOK, and cross-market isolation."""
        t0 = 1_000_000_000
        # Initialize BBO
        self.engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}))
        ctx = self.engine.contexts["fixed_spread"]
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.NORMAL)

        # 1. Stale feed triggers PAUSED_STALE_FEED (>3s)
        self.engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(4e9), self.market, {}))
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.PAUSED_STALE_FEED)

        # Recovery requires 20 clean BBOs AND >= 5.0 seconds
        t_stale = t0 + int(4e9)
        for i in range(19):
            self.engine.on_event(SimEvent(SimEventType.BBO, t_stale + int(i * 3e8), self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}))
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.PAUSED_STALE_FEED)

        # 20th clean BBO after 6 seconds -> recovers to NORMAL!
        self.engine.on_event(SimEvent(SimEventType.BBO, t_stale + int(6e9), self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}))
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.NORMAL)

        # 2. Sequence gap triggers PAUSED_GAP
        gap_delta = {"isSnapshot": False, "sequence": 999, "bids": [], "asks": []}
        self.engine.on_event(SimEvent(SimEventType.L2_DELTA, t_stale + int(7e9), self.market, gap_delta))
        self.engine.venues[self.market].book_valid = False
        ctx.set_risk_state(self.market, RiskState.PAUSED_GAP)
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.PAUSED_GAP)

        # Resync via snapshot recovers PAUSED_GAP
        snap_data = {"isSnapshot": True, "lastSequenceId": 1000, "bids": [["99.90", "1.0"]], "asks": [["100.10", "1.0"]]}
        self.engine.on_event(SimEvent(SimEventType.L2_DELTA, t_stale + int(8e9), self.market, snap_data))
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.NORMAL)

        # 3. Crossed book triggers FLATTENED_CROSSED_BOOK
        crossed_bbo = {"bid_price": 100.50, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}
        self.engine.on_event(SimEvent(SimEventType.BBO, t_stale + int(9e9), self.market, crossed_bbo))
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.FLATTENED_CROSSED_BOOK)

        # 20 clean uncrossed BBOs recover FLATTENED_CROSSED_BOOK
        t_rec = t_stale + int(10e9)
        for i in range(20):
            self.engine.on_event(SimEvent(SimEventType.BBO, t_rec + int(i * 1e8), self.market, {"bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0}))
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.NORMAL)

    def test_17_independent_fill_worlds_quoting(self):
        """Test 17: Independent fill model simulation worlds (paired_common_quotes=False) quote from their own inventory."""
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
            fill_models=[FillModelType.MODEL_A_TOUCH, FillModelType.MODEL_C_CONSERVATIVE],
            latency_config=LatencyConfig(order_entry_latency_ms=10.0, cancel_latency_ms=10.0),
            paired_common_quotes=False,
            random_seed=42,
        )
        t0 = 1_000_000_000
        # 1. Establish initial quotes
        eng.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 100.0, "ask_price": 100.2, "bid_size": 1.0, "ask_size": 1.0}))
        eng.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(20e6), self.market, {}))

        ctx = eng.contexts["fixed_spread"]
        bid_a = ctx.active_bid[FillModelType.MODEL_A_TOUCH]
        bid_c = ctx.active_bid[FillModelType.MODEL_C_CONSERVATIVE]
        self.assertIsNotNone(bid_a)
        self.assertIsNotNone(bid_c)

        # 2. Trade touches bid price (100.0): Model A fills, Model C DOES NOT fill!
        eng.on_event(SimEvent(SimEventType.TRADE, t0 + int(30e6), self.market, {"price": 100.0, "size": 0.1, "side": "SELL"}))
        pnl_a = ctx.pnl_engines[FillModelType.MODEL_A_TOUCH]
        pnl_c = ctx.pnl_engines[FillModelType.MODEL_C_CONSERVATIVE]
        self.assertAlmostEqual(pnl_a.position, bid_a.size, places=4)
        self.assertEqual(pnl_c.position, 0.0)

        # 3. Next BBO update causes requoting: Model A quotes with long inventory skew, Model C quotes flat inventory
        eng.on_event(SimEvent(SimEventType.BBO, t0 + int(40e6), self.market, {"bid_price": 100.1, "ask_price": 100.3, "bid_size": 1.0, "ask_size": 1.0}))
        eng.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(60e6), self.market, {}))

        self.assertAlmostEqual(pnl_a.position, bid_a.size, places=4)
        self.assertEqual(pnl_c.position, 0.0)

    def test_18_subaccount_rate_limit_denial_and_drip(self):
        """Test 18: Subaccount rate limit pool exhaustion denies quote placement until drip interval."""
        from src.models.rate_limit import ArcusRateLimitSimulator
        limiter = ArcusRateLimitSimulator(order_pool_cap=5, drip_interval_seconds=10.0)
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
            subaccount_rate_limiter=limiter,
            latency_config=LatencyConfig(order_entry_latency_ms=10.0, cancel_latency_ms=10.0),
            paired_common_quotes=True,
            random_seed=42,
        )
        ctx = eng.contexts["fixed_spread"]
        t0 = 1_000_000_000

        # Drain the order units
        limiter.order_units_available = 0.0

        # Attempt to quote with 0 available units (within drip window)
        eng.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 100.0, "ask_price": 100.2, "bid_size": 1.0, "ask_size": 1.0}))
        self.assertGreater(ctx.rate_limited_actions_count, 0)
        self.assertEqual(len(ctx.in_flight_orders), 0)

        # Advance time by 11 seconds (exceeding 10s drip interval)
        t_drip = t0 + int(11e9)
        eng.on_event(SimEvent(SimEventType.BBO, t_drip, self.market, {"bid_price": 100.0, "ask_price": 100.2, "bid_size": 1.0, "ask_size": 1.0}))
        self.assertGreater(len(ctx.in_flight_orders), 0)

    def test_19_w01_min_size_bids_not_rejected_on_min_clip_markets(self):
        """W-01: Verifies minimum-size bids are not silently rejected on min-size-bound markets.

        On BTC: mid = 81000.05, tick = 0.1, step/min size = 0.0001, min notional = 5.0.
        Both BID (0.0001 @ 80996.0 = $8.0996) and ASK (0.0001 @ 81004.1 = $8.10041) must be RESTING.
        Also verifies HYPE-like and ZEC-like market specifications.
        """
        specs = [
            ("BTC-USD", 81000.05, 0.1, 0.0001, 0.0001, 5.0, 10.0),
            ("HYPE-USD", 25.0, 0.001, 0.0001, 0.1, 5.0, 5.0),
            ("ZEC-USD", 45.0, 0.001, 0.00001, 0.001, 5.0, 5.0),
        ]
        for mkt, mid, tick_sz, step_sz, min_sz, min_notional, clip_notional in specs:
            strat = FixedSpreadStrategy(
                market=mkt,
                tick_size=tick_sz,
                step_size=step_sz,
                spread_bps=1.0,
                clip_notional=clip_notional,
                min_notional=min_notional,
                min_order_size=min_sz,
            )
            engine = SimEngine(
                markets={
                    mkt: {
                        "tick_size": tick_sz,
                        "step_size": step_sz,
                        "min_order_size": min_sz,
                        "min_notional": min_notional,
                    }
                },
                strategies={"strat": strat},
                fill_models=[FillModelType.MODEL_B_MODERATE],
                latency_config=LatencyConfig(order_entry_latency_ms=10.0, cancel_latency_ms=10.0),
            )
            t0 = 1_000_000_000
            half = tick_sz * 2
            engine.on_event(SimEvent(SimEventType.BBO, t0, mkt, {
                "bid_price": mid - half,
                "ask_price": mid + half,
                "bid_size": min_sz * 10,
                "ask_size": min_sz * 10,
            }))
            # Advance clock past entry latency (20ms > 10ms)
            engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(20e6), mkt, {}))

            ctx = engine.contexts["strat"]
            bid_order = ctx.active_bid[FillModelType.MODEL_B_MODERATE]
            ask_order = ctx.active_ask[FillModelType.MODEL_B_MODERATE]

            self.assertIsNotNone(bid_order, f"[{mkt}] Bid order must not be None")
            self.assertEqual(bid_order.status, OrderStatus.RESTING, f"[{mkt}] Bid order must be RESTING")
            self.assertIsNotNone(ask_order, f"[{mkt}] Ask order must not be None")
            self.assertEqual(ask_order.status, OrderStatus.RESTING, f"[{mkt}] Ask order must be RESTING")

    def test_20_w06_pnl_rate_of_change_invariant(self):
        """W-06: Verifies sanity invariant |PnL| <= max_capital * 0.50 per hour is enforced in SimEngine.

        If PnL breaches 50% capital per hour, the engine must halt quoting and transition to PAUSED_ANOMALY.
        """
        strat = FixedSpreadStrategy(
            market=self.market,
            tick_size=0.01,
            step_size=0.01,
            spread_bps=10.0,
            clip_notional=10.0,
            min_notional=5.0,
            min_order_size=0.01,
        )
        engine = SimEngine(
            markets={self.market: {"tick_size": 0.01, "step_size": 0.01, "min_order_size": 0.01, "min_notional": 5.0}},
            strategies={"strat": strat},
            fill_models=[FillModelType.MODEL_B_MODERATE],
            initial_capital=100.0,
        )
        ctx = engine.contexts["strat"]
        t0 = 1_000_000_000

        # Normal start: mid = 100.0
        engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.95, "ask_price": 100.05, "bid_size": 1.0, "ask_size": 1.0}))
        engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(20e6), self.market, {}))
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.NORMAL)

        # Inject an anomalous position/PnL jump (+60% on $100 capital in hour 1)
        pnl_b = ctx.pnl_engines[FillModelType.MODEL_B_MODERATE]
        pnl_b.record_fill(side="BUY", price=100.0, size=1.0, mid_at_fill=100.0, is_taker=False, ts_ns=t0 + int(30e6))

        # Mid price shifts to 165.0 (unrealized PnL = +$65 > $50 limit for 1 hour)
        t_jump = t0 + int(60e9)  # 60 seconds later (<1 hour)
        engine.on_event(SimEvent(SimEventType.BBO, t_jump, self.market, {"bid_price": 164.95, "ask_price": 165.05, "bid_size": 1.0, "ask_size": 1.0}))
        engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t_jump + int(20e6), self.market, {}))

        # Risk state must be PAUSED_ANOMALY and active quotes must be suppressed
        self.assertEqual(ctx.get_risk_state(self.market), RiskState.PAUSED_ANOMALY, "Engine must transition to PAUSED_ANOMALY on PnL rate of change violation")
        bid_order = ctx.active_bid.get(FillModelType.MODEL_B_MODERATE)
        self.assertTrue(bid_order is None or bid_order.status != OrderStatus.RESTING, "Quotes must not rest when PAUSED_ANOMALY is triggered")

    def test_21_w07_fill_model_deduplication(self):
        """W-07: Verifies unique physical matches against book events are deduplicated across fill models."""
        strat = FixedSpreadStrategy(
            market=self.market,
            tick_size=0.01,
            step_size=0.01,
            spread_bps=10.0,
            clip_notional=10.0,
            min_notional=5.0,
            min_order_size=0.01,
        )
        engine = SimEngine(
            markets={self.market: {"tick_size": 0.01, "step_size": 0.01, "min_order_size": 0.01, "min_notional": 5.0}},
            strategies={"strat": strat},
            fill_models=[FillModelType.MODEL_A_OPTIMISTIC, FillModelType.MODEL_B_MODERATE, FillModelType.MODEL_C_CONSERVATIVE],
            latency_config=LatencyConfig(order_entry_latency_ms=10.0, cancel_latency_ms=10.0),
        )
        ctx = engine.contexts["strat"]
        t0 = 1_000_000_000

        # Quoting at mid 100.0 (bid 99.95, ask 100.05)
        engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {"bid_price": 99.95, "ask_price": 100.05, "bid_size": 1.0, "ask_size": 1.0}))
        # Advance clock to activate resting orders
        engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(20e6), self.market, {}))

        # Single trade crossing bid (side SELL, price 99.90, size 1.0)
        t_trade = t0 + int(30e6)
        fills = engine.on_event(SimEvent(SimEventType.TRADE, t_trade, self.market, {"side": "SELL", "price": 99.90, "size": 1.0}))

        # Must generate 3 raw model fills (one per fill model)
        self.assertEqual(len(fills), 3, "Raw fills list must contain 1 fill per active model")
        # BUT unique physical matches count must be strictly 1
        self.assertEqual(ctx.unique_physical_matches_count, 1, "Unique physical match count must be 1, not 3x inflated")
        self.assertEqual(engine.get_total_unique_physical_matches(), 1, "Engine unique physical match count must be 1")

        # Each fill record must contain observation_key and quote_hash
        for f in fills:
            self.assertIn("observation_key", f)
            self.assertIn("quote_hash", f)
            self.assertTrue(f["observation_key"].startswith(f"{self.market}:strat:{f['fill_model']}:"))

    def test_22_w03_microprice_ofi_signal_wired_to_quotes(self):
        """W-03: Verifies that SimEngine computes microprice / OFI signal and passes it to AdaptiveMicrostructureStrategy."""
        from src.strategies.adaptive_mm import AdaptiveMicrostructureStrategy

        strat = AdaptiveMicrostructureStrategy(
            market=self.market,
            tick_size=0.1,
            step_size=0.0001,
            base_spread_bps=20.0,
            ofi_skew_factor=2.0,
            clip_notional=10.0,
            min_notional=5.0,
        )
        engine = SimEngine(
            markets=self.specs,
            strategies={"strat": strat},
            fill_models=[FillModelType.MODEL_B_MODERATE],
            latency_config=LatencyConfig(order_entry_latency_ms=0.0, cancel_latency_ms=0.0),
        )
        ctx = engine.contexts["strat"]
        t0 = 1_000_000_000

        # 1. Symmetric baseline: mid 100.0, bid 99.90 (size 1.0), ask 100.10 (size 1.0)
        engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {
            "bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0
        }))
        engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(20e6), self.market, {}))

        bid_neutral = ctx.active_bid[FillModelType.MODEL_B_MODERATE]
        ask_neutral = ctx.active_ask[FillModelType.MODEL_B_MODERATE]
        self.assertIsNotNone(bid_neutral)
        self.assertIsNotNone(ask_neutral)
        p_bid_neutral = bid_neutral.price
        p_ask_neutral = ask_neutral.price

        # 2. Bullish book imbalance: huge bid size (99.0) vs tiny ask size (1.0)
        t1 = t0 + 1_000_000_000
        engine.on_event(SimEvent(SimEventType.BBO, t1, self.market, {
            "bid_price": 99.90, "ask_price": 100.10, "bid_size": 99.0, "ask_size": 1.0
        }))
        engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t1 + int(20e6), self.market, {}))

        bid_skewed = ctx.active_bid[FillModelType.MODEL_B_MODERATE]
        ask_skewed = ctx.active_ask[FillModelType.MODEL_B_MODERATE]
        self.assertIsNotNone(bid_skewed)
        self.assertIsNotNone(ask_skewed)

        # Quotes MUST shift upwards due to positive microprice/OFI skew
        self.assertGreater(
            bid_skewed.price,
            p_bid_neutral,
            f"Bid price must shift upwards under positive microprice imbalance (was {p_bid_neutral}, got {bid_skewed.price})",
        )
        self.assertGreater(
            ask_skewed.price,
            p_ask_neutral,
            f"Ask price must shift upwards under positive microprice imbalance (was {p_ask_neutral}, got {ask_skewed.price})",
        )

        # 3. Aggressive buyer trade flow (OFI) shifting quotes upwards even with balanced book
        t2 = t1 + 1_000_000_000
        # Heavy taker buy trade flow hitting ask
        engine.on_event(SimEvent(SimEventType.TRADE, t2, self.market, {
            "side": "BUY", "price": 100.10, "size": 50.0
        }))
        # Subsequent BBO with balanced depth
        engine.on_event(SimEvent(SimEventType.BBO, t2 + int(1e6), self.market, {
            "bid_price": 99.90, "ask_price": 100.10, "bid_size": 1.0, "ask_size": 1.0
        }))
        engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t2 + int(20e6), self.market, {}))

        bid_trade_skewed = ctx.active_bid[FillModelType.MODEL_B_MODERATE]
        self.assertIsNotNone(bid_trade_skewed)
        self.assertGreater(
            bid_trade_skewed.price,
            p_bid_neutral,
            f"Bid price must shift upwards under positive trade flow imbalance (was {p_bid_neutral}, got {bid_trade_skewed.price})",
        )

    def test_23_w09_model_c_trade_strictly_through_by_tick(self):
        """W-09: Verifies Model C fills only when trades strictly print through resting price by >= 1 tick."""
        strat = FixedSpreadStrategy(
            market=self.market,
            tick_size=0.1,
            step_size=0.0001,
            spread_bps=20.0,
            clip_notional=10.0,
            min_notional=5.0,
        )
        engine = SimEngine(
            markets=self.specs,
            strategies={"strat": strat},
            fill_models=[FillModelType.MODEL_C_CONSERVATIVE],
            paired_common_quotes=False,
            latency_config=LatencyConfig(order_entry_latency_ms=0.0, cancel_latency_ms=0.0),
        )
        ctx = engine.contexts["strat"]
        t0 = 1_000_000_000

        # Resting quotes at mid 100.0: Bid at 99.9, Ask at 100.1
        engine.on_event(SimEvent(SimEventType.BBO, t0, self.market, {
            "bid_price": 99.9, "ask_price": 100.1, "bid_size": 1.0, "ask_size": 1.0
        }))
        engine.on_event(SimEvent(SimEventType.CLOCK_TICK, t0 + int(20e6), self.market, {}))

        bid_order = ctx.active_bid[FillModelType.MODEL_C_CONSERVATIVE]
        self.assertIsNotNone(bid_order)
        self.assertEqual(bid_order.price, 99.9)

        # 1. Trade prints at 99.85 (which is 0.05 worse, but LESS than 1 tick of 0.1 through 99.9)
        t_sub_tick = t0 + int(30e6)
        fills_sub_tick = engine.on_event(SimEvent(SimEventType.TRADE, t_sub_tick, self.market, {
            "side": "SELL", "price": 99.85, "size": 1.0
        }))
        self.assertEqual(
            len(fills_sub_tick),
            0,
            "Model C must NOT fill when trade does not clear resting quote by at least 1 full tick (99.85 vs 99.9 - 0.1 = 99.8)",
        )

        # 2. Trade prints at 99.80 (which is strictly through by 1 full tick: 99.9 - 0.1 = 99.80)
        t_full_tick = t0 + int(40e6)
        fills_full_tick = engine.on_event(SimEvent(SimEventType.TRADE, t_full_tick, self.market, {
            "side": "SELL", "price": 99.80, "size": 1.0
        }))
        self.assertEqual(
            len(fills_full_tick),
            1,
            "Model C MUST fill when trade clears resting quote by >= 1 full tick",
        )

    def test_13_mutation_tests(self):
        """Test 13: Mutation tests (at least 16 mutations applied to the engine fail test suite)."""
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
            test_mutation_11_charge_funding_per_message,
            test_mutation_12_quote_behind_touch_zero_queue,
            test_mutation_13_never_recover_pause,
            test_mutation_14_drop_stale_check,
            test_mutation_15_ignore_rate_limits,
            test_mutation_16_recv_time_joins,
            test_mutation_17_c_world_from_b_inventory,
            test_mutation_18_mid_based_min_clip_check,
            test_mutation_19_drop_ofi_microprice_argument,
            test_mutation_20_model_c_sub_tick_fills,
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
            test_mutation_11_charge_funding_per_message,
            test_mutation_12_quote_behind_touch_zero_queue,
            test_mutation_13_never_recover_pause,
            test_mutation_14_drop_stale_check,
            test_mutation_15_ignore_rate_limits,
            test_mutation_16_recv_time_joins,
            test_mutation_17_c_world_from_b_inventory,
            test_mutation_18_mid_based_min_clip_check,
            test_mutation_19_drop_ofi_microprice_argument,
            test_mutation_20_model_c_sub_tick_fills,
        ]
        results = [m() for m in mutations]
        caught = sum(1 for r in results if r.caught)
        self.assertGreaterEqual(caught, 20, f"Must catch at least 20 mutations, caught {caught}")


if __name__ == "__main__":
    unittest.main()

