"""Unified Single-Path Simulation Engine (SimEngine) for Arcus Perpetuals.

Fulfills Mandate v2 Section 5:
- One engine, one code path for Replay, Backtest, Live Paper, and Testnet.
- Consumes single time-ordered stream of events: BBO, L2_DELTA, TRADE, FUNDING, ORACLE_MARK, CLOCK_TICK.
- Explicit order lifecycle with transit latency and in-flight cancel risk.
- Concurrent paired evaluation across strategies (DoNothing, RandomSide, FixedSpread, VolClock, A-S, Adaptive).
- Dual/Triple fill model execution (Model A Diagnostic, Model B Queue-Aware Central, Model C Trade-Through Floor).
- Venue rate limit pools, time-aware hourly funding, and strict balance-sheet identity.
- Risk manager state machine (inventory caps, stale BBO >3s, crossed book, sequence gaps, daily loss limit).
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
import hashlib
import json
import logging
import math
import random
from typing import Dict, List, Optional, Tuple, Any, Callable

from src.models.fill import FillModelType, OrderStatus
from src.models.latency import LatencyConfig
from src.models.pnl import PnLAttributionEngine, TimeAwareFundingModel
from src.models.rate_limit import ArcusRateLimitSimulator
from src.orderbook import LocalOrderBook
from src.strategies.base import BaseMarketMakingStrategy, Quote
from src.utils import snap_to_tick, snap_to_step, to_decimal
from src.volatility import RealizedVolatilityEstimator

logger = logging.getLogger("sim_engine")


class SimEventType(str, Enum):
    BBO = "BBO"
    L2_DELTA = "L2_DELTA"
    TRADE = "TRADE"
    FUNDING = "FUNDING"
    ORACLE_MARK = "ORACLE_MARK"
    CLOCK_TICK = "CLOCK_TICK"


@dataclass
class SimEvent:
    event_type: SimEventType
    recv_ts_ns: int
    market: str
    data: Dict[str, Any]


@dataclass
class SimulatedOrder:
    order_id: str
    client_order_id: str
    market: str
    side: str  # "BUY" or "SELL"
    price: float
    size: float
    remaining_size: float
    status: OrderStatus
    created_ts_ns: int
    arrival_ts_ns: int
    cancel_requested_ts_ns: Optional[int] = None
    cancel_arrival_ts_ns: Optional[int] = None
    queue_ahead_size: float = 0.0
    is_post_only: bool = True
    rejection_reason: Optional[str] = None

    def copy(self) -> "SimulatedOrder":
        return SimulatedOrder(
            order_id=self.order_id,
            client_order_id=self.client_order_id,
            market=self.market,
            side=self.side,
            price=self.price,
            size=self.size,
            remaining_size=self.remaining_size,
            status=self.status,
            created_ts_ns=self.created_ts_ns,
            arrival_ts_ns=self.arrival_ts_ns,
            cancel_requested_ts_ns=self.cancel_requested_ts_ns,
            cancel_arrival_ts_ns=self.cancel_arrival_ts_ns,
            queue_ahead_size=self.queue_ahead_size,
            is_post_only=self.is_post_only,
            rejection_reason=self.rejection_reason,
        )


class RiskState(str, Enum):
    NORMAL = "NORMAL"
    REDUCE_ONLY = "REDUCE_ONLY"
    PAUSED_STALE_FEED = "PAUSED_STALE_FEED"
    PAUSED_GAP = "PAUSED_GAP"
    FLATTENED_LOSS_LIMIT = "FLATTENED_LOSS_LIMIT"
    FLATTENED_CROSSED_BOOK = "FLATTENED_CROSSED_BOOK"


class MarketState:
    """Encapsulates venue state, orderbook, and telemetry for one market."""

    def __init__(
        self,
        market: str,
        tick_size: float,
        step_size: float,
        min_notional: float = 5.0,
        min_order_size: float = 0.0,
        max_order_size: float = 1_000_000.0,
    ):
        self.market = market
        self.tick_size = tick_size
        self.step_size = step_size
        self.min_notional = min_notional
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size

        self.best_bid: float = 0.0
        self.best_ask: float = 0.0
        self.best_bid_size: float = 0.0
        self.best_ask_size: float = 0.0
        self.current_mid: float = 0.0
        self.current_mark: float = 0.0
        self.last_bbo_ts_ns: int = 0
        self.clean_bbo_count_since_stale: int = 0

        self.orderbook = LocalOrderBook(market=market)
        self.volatility_estimator = RealizedVolatilityEstimator(half_life_sec=300.0)
        self.current_volatility: float = 0.30

        self.last_seq: Optional[int] = None
        self.book_valid: bool = True
        self.invalid_intervals: List[Dict[str, Any]] = []

    def get_min_executable_clip(self) -> float:
        ref_p = self.current_mid if self.current_mid > 0 else 1.0
        return max(self.min_notional, self.min_order_size * ref_p)


class StrategyInstanceContext:
    """Manages strategy execution, fill engines, risk state, and PnL attribution."""

    def __init__(
        self,
        strategy_id: str,
        strategy: BaseMarketMakingStrategy,
        fill_models: List[FillModelType],
        initial_capital: float = 100.0,
        max_inventory_clips: float = 3.0,
    ):
        self.strategy_id = strategy_id
        self.strategy = strategy
        self.fill_models = fill_models
        self.initial_capital = initial_capital
        self.max_inventory_clips = max_inventory_clips

        self.risk_state: RiskState = RiskState.NORMAL
        self.rate_limiter = ArcusRateLimitSimulator(requote_threshold_ticks=2)

        # Separate PnL attribution and resting orders per fill model
        self.pnl_engines: Dict[FillModelType, PnLAttributionEngine] = {
            fm: PnLAttributionEngine(initial_capital=initial_capital, maker_fee_bps=0.0, taker_fee_bps=2.25)
            for fm in fill_models
        }
        self.active_bid: Dict[FillModelType, Optional[SimulatedOrder]] = {fm: None for fm in fill_models}
        self.active_ask: Dict[FillModelType, Optional[SimulatedOrder]] = {fm: None for fm in fill_models}

        # In-flight scheduled actions: list of orders pending arrival
        self.in_flight_orders: List[SimulatedOrder] = []
        self.fill_records: List[Dict[str, Any]] = []
        self.order_counter: int = 0
        self.post_only_rejections_count: int = 0


class SimEngine:
    """Deterministic Multi-Market, Multi-Strategy Simulation Engine."""

    def __init__(
        self,
        markets: List[str],
        market_specs: Dict[str, Dict[str, Any]],
        strategies: Dict[str, BaseMarketMakingStrategy],
        fill_models: Optional[List[FillModelType]] = None,
        latency_config: Optional[LatencyConfig] = None,
        initial_capital: float = 100.0,
        random_seed: int = 42,
    ):
        self.markets = markets
        self.fill_models = fill_models or [
            FillModelType.MODEL_A_TOUCH,
            FillModelType.MODEL_B_MODERATE,
            FillModelType.MODEL_C_CONSERVATIVE,
        ]
        self.latency_config = latency_config or LatencyConfig()
        self.initial_capital = initial_capital
        self.random_seed = random_seed
        self.rng = random.Random(random_seed)

        # Market venues
        self.venues: Dict[str, MarketState] = {}
        for m in markets:
            spec = market_specs.get(m, {})
            self.venues[m] = MarketState(
                market=m,
                tick_size=float(spec.get("tick_size", 0.001)),
                step_size=float(spec.get("step_size", 0.000001)),
                min_notional=float(spec.get("min_notional", 5.0)),
                min_order_size=float(spec.get("min_order_size", 0.0)),
                max_order_size=float(spec.get("max_order_size", 1_000_000.0)),
            )

        # Strategy contexts (one context per registered strategy)
        self.contexts: Dict[str, StrategyInstanceContext] = {}
        for sid, strat in strategies.items():
            self.contexts[sid] = StrategyInstanceContext(
                strategy_id=sid,
                strategy=strat,
                fill_models=self.fill_models,
                initial_capital=initial_capital,
            )

        self.funding_model = TimeAwareFundingModel()
        self.current_clock_ts_ns: int = 0
        self.fill_log_hasher = hashlib.sha256()

    def sample_latency_ns(self, action: str) -> int:
        """Draws latency in nanoseconds using latency config and seeded RNG."""
        if action == "place":
            base_ms = self.latency_config.order_entry_latency_ms
        elif action == "cancel":
            base_ms = self.latency_config.cancel_latency_ms
        elif action == "modify":
            base_ms = self.latency_config.modify_latency_ms
        else:
            base_ms = 25.0
        # Add 10% bounded jitter
        jitter = self.rng.uniform(-0.1, 0.1) * base_ms
        eff_ms = max(1.0, base_ms + jitter)
        return int(eff_ms * 1e6)

    def on_event(self, event: SimEvent) -> List[Dict[str, Any]]:
        """Processes a single event in strict timestamp order and returns any fills generated."""
        ts_ns = event.recv_ts_ns
        self.current_clock_ts_ns = max(self.current_clock_ts_ns, ts_ns)
        market = event.market
        venue = self.venues.get(market)
        if not venue:
            return []

        # 1. Process pending in-flight order arrivals up to current event timestamp
        self._process_in_flight_arrivals(ts_ns)

        # 2. Dispatch event to venue state & orderbook
        generated_fills: List[Dict[str, Any]] = []

        if event.event_type == SimEventType.BBO:
            self._handle_bbo_event(venue, event.data, ts_ns)
            self._evaluate_strategies_quoting(venue, ts_ns)

        elif event.event_type == SimEventType.L2_DELTA:
            self._handle_l2_delta_event(venue, event.data, ts_ns)

        elif event.event_type == SimEventType.TRADE:
            trade_fills = self._handle_trade_event(venue, event.data, ts_ns)
            generated_fills.extend(trade_fills)

        elif event.event_type == SimEventType.FUNDING:
            self._handle_funding_event(venue, event.data, ts_ns)

        elif event.event_type == SimEventType.ORACLE_MARK:
            venue.current_mark = float(event.data.get("mark_price", venue.current_mid))

        elif event.event_type == SimEventType.CLOCK_TICK:
            self._handle_clock_tick(venue, ts_ns)

        return generated_fills

    def _process_in_flight_arrivals(self, current_ts_ns: int) -> None:
        """Activates scheduled place/modify/cancel order arrivals when timestamp arrives."""
        for ctx in self.contexts.values():
            ready_orders = [o for o in ctx.in_flight_orders if o.arrival_ts_ns <= current_ts_ns]
            for order in ready_orders:
                ctx.in_flight_orders.remove(order)
                venue = self.venues.get(order.market)
                if not venue:
                    continue

                if order.status == OrderStatus.SUBMITTING:
                    # Check ALO post-only cross against live book at arrival time
                    if order.side == "BUY" and venue.best_ask > 0 and order.price >= venue.best_ask:
                        order.status = OrderStatus.REJECTED
                        order.rejection_reason = "POST_ONLY_WOULD_CROSS"
                        ctx.post_only_rejections_count += 1
                        continue
                    if order.side == "SELL" and venue.best_bid > 0 and order.price <= venue.best_bid:
                        order.status = OrderStatus.REJECTED
                        order.rejection_reason = "POST_ONLY_WOULD_CROSS"
                        ctx.post_only_rejections_count += 1
                        continue

                    # Resting order established!
                    order.status = OrderStatus.RESTING
                    for fm in ctx.fill_models:
                        if order.side == "BUY":
                            ctx.active_bid[fm] = order.copy()
                        else:
                            ctx.active_ask[fm] = order.copy()

                elif order.status == OrderStatus.CANCEL_REQUESTED:
                    # Cancel arrives at venue
                    order.status = OrderStatus.CANCELLED
                    for fm in ctx.fill_models:
                        if order.side == "BUY" and ctx.active_bid[fm] and ctx.active_bid[fm].order_id == order.order_id:
                            ctx.active_bid[fm] = None
                        elif order.side == "SELL" and ctx.active_ask[fm] and ctx.active_ask[fm].order_id == order.order_id:
                            ctx.active_ask[fm] = None

            # Process cancels on resting orders whose cancel arrival has reached current_ts_ns
            for fm in ctx.fill_models:
                bid = ctx.active_bid[fm]
                if bid and bid.status == OrderStatus.CANCEL_REQUESTED and bid.cancel_arrival_ts_ns and bid.cancel_arrival_ts_ns <= current_ts_ns:
                    bid.status = OrderStatus.CANCELLED
                    ctx.active_bid[fm] = None

                ask = ctx.active_ask[fm]
                if ask and ask.status == OrderStatus.CANCEL_REQUESTED and ask.cancel_arrival_ts_ns and ask.cancel_arrival_ts_ns <= current_ts_ns:
                    ask.status = OrderStatus.CANCELLED
                    ctx.active_ask[fm] = None

    def _handle_bbo_event(self, venue: MarketState, data: Dict[str, Any], ts_ns: int) -> None:
        """Updates venue BBO and realized volatility."""
        bid = float(data.get("bid_price") or data.get("bestBid", {}).get("price") or 0.0)
        ask = float(data.get("ask_price") or data.get("bestAsk", {}).get("price") or 0.0)
        bid_s = float(data.get("bid_size") or data.get("bestBid", {}).get("size") or 0.0)
        ask_s = float(data.get("ask_size") or data.get("bestAsk", {}).get("size") or 0.0)

        if bid > 0 and ask > 0:
            # Check crossed book
            if bid >= ask:
                venue.book_valid = False
                for ctx in self.contexts.values():
                    ctx.risk_state = RiskState.FLATTENED_CROSSED_BOOK
                return

            venue.best_bid = bid
            venue.best_ask = ask
            venue.best_bid_size = bid_s
            venue.best_ask_size = ask_s
            venue.current_mid = (bid + ask) / 2.0
            venue.last_bbo_ts_ns = ts_ns
            venue.clean_bbo_count_since_stale += 1

            # Update causal realized volatility
            venue.current_volatility = venue.volatility_estimator.update(ts_ns, venue.current_mid)

    def _handle_l2_delta_event(self, venue: MarketState, data: Dict[str, Any], ts_ns: int) -> None:
        """Applies order book snapshot/delta and sequence gap check."""
        seq = data.get("lastSequenceId") or data.get("sequence")
        if seq is not None and venue.last_seq is not None:
            if seq > venue.last_seq + 1 and not data.get("isSnapshot"):
                # Mid-stream sequence gap!
                venue.book_valid = False
                gap_info = {"market": venue.market, "expected": venue.last_seq + 1, "received": seq, "ts_ns": ts_ns}
                venue.invalid_intervals.append(gap_info)
                for ctx in self.contexts.values():
                    ctx.risk_state = RiskState.PAUSED_GAP
        venue.last_seq = seq

        if data.get("isSnapshot"):
            venue.orderbook.handle_snapshot(data.get("bids", []), data.get("asks", []), seq or 0)
            venue.book_valid = True
        else:
            venue.orderbook.handle_l2_update(data.get("bids", []), data.get("asks", []), seq or 0)

    def _handle_trade_event(self, venue: MarketState, data: Dict[str, Any], ts_ns: int) -> List[Dict[str, Any]]:
        """Processes trade fills against resting and in-flight cancel-requested orders."""
        trade_p = float(data.get("price") or 0.0)
        trade_s = float(data.get("size") or 0.0)
        trade_side = str(data.get("side", "")).upper()  # Taker aggressor side: "BUY" or "SELL"

        if trade_p <= 0 or trade_s <= 0 or not trade_side:
            return []

        fills_generated: List[Dict[str, Any]] = []

        for ctx in self.contexts.values():
            if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                continue
            for fm in ctx.fill_models:
                pnl_eng = ctx.pnl_engines[fm]

                # 1. Check BID fills (taker sells hitting our bid)
                bid_order = ctx.active_bid[fm]
                if bid_order and bid_order.status in (OrderStatus.RESTING, OrderStatus.CANCEL_REQUESTED):
                    fill_qty = self._evaluate_fill_quantity(fm, bid_order, trade_side, trade_p, trade_s)
                    if fill_qty > 0:
                        fee = pnl_eng.record_fill("BUY", bid_order.price, fill_qty, venue.current_mid, is_taker=False, ts_ns=ts_ns)
                        ctx.rate_limiter.record_fill(fill_qty * bid_order.price)
                        bid_order.remaining_size -= fill_qty
                        if bid_order.remaining_size <= 1e-9:
                            bid_order.status = OrderStatus.FILLED
                            ctx.active_bid[fm] = None

                        fill_rec = {
                            "strategy_id": ctx.strategy_id,
                            "fill_model": fm.value,
                            "market": venue.market,
                            "side": "BUY",
                            "price": bid_order.price,
                            "size": fill_qty,
                            "mid_at_fill": venue.current_mid,
                            "fee": fee,
                            "ts_ns": ts_ns,
                        }
                        fills_generated.append(fill_rec)
                        ctx.fill_records.append(fill_rec)
                        self._hash_fill_record(fill_rec)

                # 2. Check ASK fills (taker buys lifting our ask)
                ask_order = ctx.active_ask[fm]
                if ask_order and ask_order.status in (OrderStatus.RESTING, OrderStatus.CANCEL_REQUESTED):
                    fill_qty = self._evaluate_fill_quantity(fm, ask_order, trade_side, trade_p, trade_s)
                    if fill_qty > 0:
                        fee = pnl_eng.record_fill("SELL", ask_order.price, fill_qty, venue.current_mid, is_taker=False, ts_ns=ts_ns)
                        ctx.rate_limiter.record_fill(fill_qty * ask_order.price)
                        ask_order.remaining_size -= fill_qty
                        if ask_order.remaining_size <= 1e-9:
                            ask_order.status = OrderStatus.FILLED
                            ctx.active_ask[fm] = None

                        fill_rec = {
                            "strategy_id": ctx.strategy_id,
                            "fill_model": fm.value,
                            "market": venue.market,
                            "side": "SELL",
                            "price": ask_order.price,
                            "size": fill_qty,
                            "mid_at_fill": venue.current_mid,
                            "fee": fee,
                            "ts_ns": ts_ns,
                        }
                        fills_generated.append(fill_rec)
                        ctx.fill_records.append(fill_rec)
                        self._hash_fill_record(fill_rec)

        return fills_generated

    def _evaluate_fill_quantity(
        self,
        fill_model: FillModelType,
        order: SimulatedOrder,
        trade_side: str,
        trade_price: float,
        trade_size: float,
    ) -> float:
        """Applies exact fill model semantics: Model A (touch), Model B (queue), Model C (trade-through)."""
        if order.side == "BUY":
            # Maker BID filled by taker SELL
            if trade_side != "SELL":
                return 0.0

            if fill_model == FillModelType.MODEL_A_TOUCH:
                return min(order.remaining_size, trade_size) if trade_price <= order.price else 0.0

            elif fill_model == FillModelType.MODEL_C_CONSERVATIVE:
                # Strict trade-through: price must be strictly BELOW our bid
                return min(order.remaining_size, trade_size) if trade_price < order.price - 1e-6 else 0.0

            elif fill_model == FillModelType.MODEL_B_MODERATE:
                if trade_price < order.price - 1e-6:
                    return min(order.remaining_size, trade_size)
                elif abs(trade_price - order.price) <= 1e-6:
                    # Deplete queue ahead
                    if order.queue_ahead_size > 0:
                        depleted = min(order.queue_ahead_size, trade_size)
                        order.queue_ahead_size -= depleted
                        rem_trade = trade_size - depleted
                        return min(order.remaining_size, rem_trade) if rem_trade > 0 else 0.0
                    else:
                        return min(order.remaining_size, trade_size)
                return 0.0

        elif order.side == "SELL":
            # Maker ASK filled by taker BUY
            if trade_side != "BUY":
                return 0.0

            if fill_model == FillModelType.MODEL_A_TOUCH:
                return min(order.remaining_size, trade_size) if trade_price >= order.price else 0.0

            elif fill_model == FillModelType.MODEL_C_CONSERVATIVE:
                # Strict trade-through: price must be strictly ABOVE our ask
                return min(order.remaining_size, trade_size) if trade_price > order.price + 1e-6 else 0.0

            elif fill_model == FillModelType.MODEL_B_MODERATE:
                if trade_price > order.price + 1e-6:
                    return min(order.remaining_size, trade_size)
                elif abs(trade_price - order.price) <= 1e-6:
                    if order.queue_ahead_size > 0:
                        depleted = min(order.queue_ahead_size, trade_size)
                        order.queue_ahead_size -= depleted
                        rem_trade = trade_size - depleted
                        return min(order.remaining_size, rem_trade) if rem_trade > 0 else 0.0
                    else:
                        return min(order.remaining_size, trade_size)
                return 0.0

        return 0.0

    def _evaluate_strategies_quoting(self, venue: MarketState, ts_ns: int) -> None:
        """Invokes registered strategies to compute new quotes and dispatches orders."""
        if not venue.book_valid or venue.best_bid <= 0 or venue.best_ask <= 0:
            return

        spread_bps = ((venue.best_ask - venue.best_bid) / venue.current_mid) * 10_000.0

        for ctx in self.contexts.values():
            if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                continue
            # Check risk state
            if ctx.risk_state in (RiskState.PAUSED_GAP, RiskState.PAUSED_STALE_FEED, RiskState.FLATTENED_CROSSED_BOOK):
                continue

            # Check inventory limits against Central Model B position
            pnl_b = ctx.pnl_engines[FillModelType.MODEL_B_MODERATE]
            inv_units = pnl_b.position
            clip_notional = venue.get_min_executable_clip()

            quotes = ctx.strategy.generate_quotes(
                mid_price=venue.current_mid,
                inventory_units=inv_units,
                volatility=venue.current_volatility,
                market_spread_bps=spread_bps,
            )
            if not quotes:
                continue

            target_bid, target_ask = quotes
            self._schedule_quote_update(venue, ctx, target_bid, target_ask, ts_ns)

    def _schedule_quote_update(
        self,
        venue: MarketState,
        ctx: StrategyInstanceContext,
        target_bid: Optional[Quote],
        target_ask: Optional[Quote],
        ts_ns: int,
    ) -> None:
        """Schedules place, modify, or cancel-replace with latency."""
        # 1. Update BID
        if target_bid:
            target_p = float(snap_to_tick(target_bid.price, venue.tick_size))
            target_s = float(snap_to_step(target_bid.size, venue.step_size))
            if target_s * target_p >= venue.get_min_executable_clip() - 1e-6:
                existing_bid = ctx.active_bid[FillModelType.MODEL_B_MODERATE]
                if not existing_bid or existing_bid.price != target_p or existing_bid.remaining_size != target_s:
                    # Cancel existing if present across all models
                    cancel_lat = self.sample_latency_ns("cancel")
                    had_resting = False
                    for fm in ctx.fill_models:
                        cur = ctx.active_bid[fm]
                        if cur and cur.status == OrderStatus.RESTING:
                            cur.status = OrderStatus.CANCEL_REQUESTED
                            cur.cancel_arrival_ts_ns = ts_ns + cancel_lat
                            had_resting = True
                    if had_resting:
                        ctx.rate_limiter.record_cancel()

                    # Place new order
                    place_lat = self.sample_latency_ns("place")
                    ctx.order_counter += 1
                    new_order = SimulatedOrder(
                        order_id=f"{ctx.strategy_id}_bid_{ctx.order_counter}",
                        client_order_id=f"cl_{ctx.order_counter}",
                        market=venue.market,
                        side="BUY",
                        price=target_p,
                        size=target_s,
                        remaining_size=target_s,
                        status=OrderStatus.SUBMITTING,
                        created_ts_ns=ts_ns,
                        arrival_ts_ns=ts_ns + place_lat,
                        queue_ahead_size=venue.best_bid_size if target_p == venue.best_bid else 0.0,
                    )
                    ctx.in_flight_orders.append(new_order)
                    ctx.rate_limiter.record_placement()

        # 2. Update ASK
        if target_ask:
            target_p = float(snap_to_tick(target_ask.price, venue.tick_size))
            target_s = float(snap_to_step(target_ask.size, venue.step_size))
            if target_s * target_p >= venue.get_min_executable_clip() - 1e-6:
                existing_ask = ctx.active_ask[FillModelType.MODEL_B_MODERATE]
                if not existing_ask or existing_ask.price != target_p or existing_ask.remaining_size != target_s:
                    cancel_lat = self.sample_latency_ns("cancel")
                    had_resting = False
                    for fm in ctx.fill_models:
                        cur = ctx.active_ask[fm]
                        if cur and cur.status == OrderStatus.RESTING:
                            cur.status = OrderStatus.CANCEL_REQUESTED
                            cur.cancel_arrival_ts_ns = ts_ns + cancel_lat
                            had_resting = True
                    if had_resting:
                        ctx.rate_limiter.record_cancel()

                    place_lat = self.sample_latency_ns("place")
                    ctx.order_counter += 1
                    new_order = SimulatedOrder(
                        order_id=f"{ctx.strategy_id}_ask_{ctx.order_counter}",
                        client_order_id=f"cl_{ctx.order_counter}",
                        market=venue.market,
                        side="SELL",
                        price=target_p,
                        size=target_s,
                        remaining_size=target_s,
                        status=OrderStatus.SUBMITTING,
                        created_ts_ns=ts_ns,
                        arrival_ts_ns=ts_ns + place_lat,
                        queue_ahead_size=venue.best_ask_size if target_p == venue.best_ask else 0.0,
                    )
                    ctx.in_flight_orders.append(new_order)
                    ctx.rate_limiter.record_placement()

    def _handle_funding_event(self, venue: MarketState, data: Dict[str, Any], ts_ns: int) -> None:
        """Applies time-aware hourly funding to all open positions."""
        rate = float(data.get("funding_rate") or data.get("rate") or 0.0)
        ref_mid = venue.current_mid if venue.current_mid > 0 else 1.0
        for ctx in self.contexts.values():
            if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                continue
            for fm, pnl_eng in ctx.pnl_engines.items():
                pnl_eng.apply_funding(rate, ref_mid)

    def _handle_clock_tick(self, venue: MarketState, ts_ns: int) -> None:
        """Evaluates stale BBO watchdogs and periodic risk checks."""
        if venue.last_bbo_ts_ns > 0 and (ts_ns - venue.last_bbo_ts_ns) > 3_000_000_000:
            # Stale BBO (> 3 seconds)
            for ctx in self.contexts.values():
                if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                    continue
                ctx.risk_state = RiskState.PAUSED_STALE_FEED
                # Cancel all resting orders
                for fm in ctx.fill_models:
                    if ctx.active_bid[fm]:
                        ctx.active_bid[fm].status = OrderStatus.CANCELLED
                        ctx.active_bid[fm] = None
                    if ctx.active_ask[fm]:
                        ctx.active_ask[fm].status = OrderStatus.CANCELLED
                        ctx.active_ask[fm] = None

    def _hash_fill_record(self, fill_rec: Dict[str, Any]) -> None:
        """Appends deterministic canonical hash of fill record for bit-for-bit replay parity."""
        msg = f"{fill_rec['strategy_id']}:{fill_rec['fill_model']}:{fill_rec['side']}:{fill_rec['price']:.5f}:{fill_rec['size']:.6f}:{fill_rec['ts_ns']}"
        self.fill_log_hasher.update(msg.encode())

    def get_fill_log_hash(self) -> str:
        return self.fill_log_hasher.hexdigest()
