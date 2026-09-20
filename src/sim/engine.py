from __future__ import annotations

"""Unified Single-Path Simulation Engine (SimEngine) for Arcus Perpetuals.
Fulfills Mandate v3 WS-D (Section 9) & Findings V-05 through V-12.

- One engine, one code path for Replay, Backtest, Live Paper, and Testnet.
- Consumes single time-ordered stream of events: BBO, L2_DELTA, TRADE, FUNDING, ORACLE_MARK, CLOCK_TICK.
- L2 Order Book reconstructor integration with real arrival-time queue depth (V-06, V-07).
- Discrete funding settlement protecting against 60x predicted funding overcharge (V-08).
- Per-(market, strategy) risk manager state machine with automatic recovery (V-09).
- Subaccount-level shared rate limit pools with pre-action gating and drip (V-10).
- LatencyModel abstraction supporting Constant and Empirical distribution sampling (V-11).
- Independent fill-model simulation worlds for Model A, Model B, and Model C (V-12).
- Paired common quotes diagnostic mode strictly preserved for monotonicity checks.
- Venue mechanics with mark price tracking and margin checks (V-14).
"""

from dataclasses import dataclass
from enum import Enum
import hashlib
import logging
import math
import random
from typing import Dict, List, Optional, Any, Set
import pandas as pd

from src.models.fill import FillModelType, OrderStatus
from src.models.latency import LatencyConfig, LatencyModel, ConstantLatencyModel
from src.models.pnl import PnLAttributionEngine, TimeAwareFundingModel
from src.models.rate_limit import ArcusRateLimitSimulator
from src.orderbook import LocalOrderBook
from src.strategies.base import BaseMarketMakingStrategy, Quote
from src.utils import snap_to_tick, snap_to_step
from src.venue import get_market_spec
from src.volatility import RealizedVolatilityEstimator
from src.session_calendar import classify_rth_capture_tag

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
    fill_model: Optional[FillModelType] = None
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
            fill_model=self.fill_model,
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
    PAUSED_ANOMALY = "PAUSED_ANOMALY"
    FLATTENED_LOSS_LIMIT = "FLATTENED_LOSS_LIMIT"
    FLATTENED_CROSSED_BOOK = "FLATTENED_CROSSED_BOOK"
    FLATTENED_LIQUIDATION = "FLATTENED_LIQUIDATION"


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
        category: str = "CRYPTO",
        initial_margin_fraction: float = 0.05,
        maintenance_margin_fraction: float = 0.03,
    ):
        self.market = market
        self.tick_size = tick_size
        self.step_size = step_size
        self.min_notional = min_notional
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size
        self.category = category
        self.initial_margin_fraction = initial_margin_fraction
        self.maintenance_margin_fraction = maintenance_margin_fraction

        self.best_bid: float = 0.0
        self.best_ask: float = 0.0
        self.best_bid_size: float = 0.0
        self.best_ask_size: float = 0.0
        self.current_mid: float = 0.0
        self.current_mark: float = 0.0
        self.last_bbo_ts_ns: int = 0
        self.clean_bbo_count_since_stale: int = 0
        self.stale_recovery_start_ts_ns: int = 0

        self.orderbook = LocalOrderBook(market=market)
        self.volatility_estimator = RealizedVolatilityEstimator(half_life_sec=300.0)
        self.current_volatility: float = 0.30

        self.last_seq: Optional[int] = None
        self.book_valid: bool = True
        self.invalid_intervals: List[Dict[str, Any]] = []

        # Funding tracking
        self.predicted_funding_rate: float = 0.0
        self.last_settled_hour: Optional[int] = None
        self.is_outside_rth: bool = False

        # Microprice and Order Flow Imbalance (OFI) tracking (fix W-03)
        self.decaying_buy_vol: float = 0.0
        self.decaying_sell_vol: float = 0.0
        self.last_trade_decay_ts_ns: int = 0
        self.tfi_half_life_sec: float = 30.0

    def update_trade_flow(self, side: str, size: float, ts_ns: int) -> None:
        """Updates exponentially decaying trade flow imbalance (causal, no lookahead)."""
        if self.last_trade_decay_ts_ns > 0 and ts_ns > self.last_trade_decay_ts_ns:
            dt_sec = (ts_ns - self.last_trade_decay_ts_ns) / 1e9
            decay = math.exp(-0.69314718056 * dt_sec / self.tfi_half_life_sec)
            self.decaying_buy_vol *= decay
            self.decaying_sell_vol *= decay
        self.last_trade_decay_ts_ns = ts_ns

        side_upper = side.upper()
        if side_upper == "BUY":
            self.decaying_buy_vol += size
        elif side_upper == "SELL":
            self.decaying_sell_vol += size

    def get_microprice_and_ofi_deviation(self, current_ts_ns: int) -> float:
        """Computes combined microprice deviation and trade-flow imbalance in bps."""
        # 1. Top of book microprice deviation
        micro_dev_bps = 0.0
        if self.best_bid > 0 and self.best_ask > 0 and self.current_mid > 0:
            tot_depth = self.best_bid_size + self.best_ask_size
            if tot_depth > 1e-9:
                microprice = (self.best_bid * self.best_ask_size + self.best_ask * self.best_bid_size) / tot_depth
                micro_dev_bps = ((microprice - self.current_mid) / self.current_mid) * 10_000.0

        # 2. Causal trade flow imbalance (OFI)
        b_vol = self.decaying_buy_vol
        s_vol = self.decaying_sell_vol
        if self.last_trade_decay_ts_ns > 0 and current_ts_ns > self.last_trade_decay_ts_ns:
            dt_sec = (current_ts_ns - self.last_trade_decay_ts_ns) / 1e9
            decay = math.exp(-0.69314718056 * dt_sec / self.tfi_half_life_sec)
            b_vol *= decay
            s_vol *= decay

        tot_vol = b_vol + s_vol
        tfi = (b_vol - s_vol) / (tot_vol + 1e-9) if tot_vol > 1e-9 else 0.0

        spread_bps = 0.0
        if self.current_mid > 0 and self.best_ask > self.best_bid:
            spread_bps = ((self.best_ask - self.best_bid) / self.current_mid) * 10_000.0

        ofi_component_bps = tfi * (spread_bps * 0.25)
        return micro_dev_bps + ofi_component_bps

    def get_min_executable_clip(self) -> float:
        ref_p = self.current_mid if self.current_mid > 0 else 1.0
        return max(self.min_notional, self.min_order_size * ref_p)


class StrategyInstanceContext:
    """Manages strategy execution, independent fill engines, risk state, and PnL attribution."""

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

        # Per-market risk states (scoped to affected market, fix V-09)
        self.risk_states: Dict[str, RiskState] = {}
        self._default_risk_state: RiskState = RiskState.NORMAL

        # Separate PnL attribution and resting orders per fill model (fix V-12)
        self.pnl_engines: Dict[FillModelType, PnLAttributionEngine] = {
            fm: PnLAttributionEngine(initial_capital=initial_capital, maker_fee_bps=0.0, taker_fee_bps=2.25)
            for fm in fill_models
        }
        self.active_bid: Dict[FillModelType, Optional[SimulatedOrder]] = {fm: None for fm in fill_models}
        self.active_ask: Dict[FillModelType, Optional[SimulatedOrder]] = {fm: None for fm in fill_models}

        # In-flight scheduled actions
        self.in_flight_orders: List[SimulatedOrder] = []
        self.fill_records: List[Dict[str, Any]] = []
        self.unique_physical_matches: Set[str] = set()
        self.order_counter: int = 0
        self.post_only_rejections_count: int = 0
        self.rate_limited_actions_count: int = 0

    @property
    def unique_physical_matches_count(self) -> int:
        return len(self.unique_physical_matches)

    @property
    def risk_state(self) -> RiskState:
        for state in self.risk_states.values():
            if state != RiskState.NORMAL:
                return state
        return self._default_risk_state

    @risk_state.setter
    def risk_state(self, state: RiskState) -> None:
        self._default_risk_state = state
        for m in list(self.risk_states.keys()):
            self.risk_states[m] = state

    def get_risk_state(self, market: str) -> RiskState:
        return self.risk_states.get(market, self._default_risk_state)

    def set_risk_state(self, market: str, state: RiskState) -> None:
        self.risk_states[market] = state


class SimEngine:
    """Deterministic Multi-Market, Multi-Strategy Simulation Engine."""

    def __init__(
        self,
        markets: List[str],
        market_specs: Optional[Dict[str, Dict[str, Any]]] = None,
        strategies: Optional[Dict[str, BaseMarketMakingStrategy]] = None,
        fill_models: Optional[List[FillModelType]] = None,
        latency_model: Optional[LatencyModel] = None,
        latency_config: Optional[LatencyConfig] = None,
        paired_common_quotes: bool = True,
        initial_capital: float = 100.0,
        max_inventory_clips: float = 3.0,
        subaccount_rate_limiter: Optional[ArcusRateLimitSimulator] = None,
        random_seed: int = 42,
        taker_speed_bump_ms: float = 0.0,
    ):
        if isinstance(markets, dict) and market_specs is None:
            market_specs = markets
            markets = list(markets.keys())
        self.markets = markets
        self.fill_models = fill_models or [
            FillModelType.MODEL_A_TOUCH,
            FillModelType.MODEL_B_MODERATE,
            FillModelType.MODEL_C_CONSERVATIVE,
        ]
        self.paired_common_quotes = paired_common_quotes
        self.initial_capital = initial_capital
        self.max_inventory_clips = max_inventory_clips
        self.random_seed = random_seed
        self.rng = random.Random(random_seed)
        self.taker_speed_bump_ms = taker_speed_bump_ms

        # Latency model (Constant or Empirical, fix V-11)
        if latency_model is not None:
            self.latency_model = latency_model
        elif latency_config is not None:
            self.latency_model = ConstantLatencyModel(latency_config)
        else:
            self.latency_model = ConstantLatencyModel(LatencyConfig())

        # Subaccount-level shared rate limiter pool (fix V-10)
        self.subaccount_rate_limiter = subaccount_rate_limiter or ArcusRateLimitSimulator(
            requote_threshold_ticks=2
        )

        # Market venues
        self.venues: Dict[str, MarketState] = {}
        for m in markets:
            if market_specs and m in market_specs:
                spec = market_specs[m]
            else:
                try:
                    spec = get_market_spec(m)
                except Exception:
                    spec = {}

            self.venues[m] = MarketState(
                market=m,
                tick_size=float(spec.get("tick_size", 0.001)),
                step_size=float(spec.get("step_size", 0.000001)),
                min_notional=float(spec.get("min_notional", 5.0)),
                min_order_size=float(spec.get("min_order_size", 0.0)),
                max_order_size=float(spec.get("max_order_size", 1_000_000.0)),
                category=str(spec.get("category", "CRYPTO")),
                initial_margin_fraction=float(spec.get("initial_margin_fraction", 0.05)),
                maintenance_margin_fraction=float(spec.get("maintenance_margin_fraction", 0.03)),
            )

        # Strategy contexts
        self.contexts: Dict[str, StrategyInstanceContext] = {}
        if strategies:
            for sid, strat in strategies.items():
                self.contexts[sid] = StrategyInstanceContext(
                    strategy_id=sid,
                    strategy=strat,
                    fill_models=self.fill_models,
                    initial_capital=initial_capital,
                    max_inventory_clips=max_inventory_clips,
                )

        self.funding_model = TimeAwareFundingModel()
        self.current_clock_ts_ns: int = 0
        self.session_start_ts_ns: int = 0
        self.fill_log_hasher = hashlib.sha256()

    def sample_latency_ns(self, action: str) -> int:
        """Draws latency in nanoseconds using configured LatencyModel."""
        return self.latency_model.sample_ns(action, self.rng)

    def on_event(self, event: SimEvent) -> List[Dict[str, Any]]:
        """Processes a single event in strict timestamp order and returns any fills generated."""
        ts_ns = event.recv_ts_ns
        self.current_clock_ts_ns = max(self.current_clock_ts_ns, ts_ns)
        if self.session_start_ts_ns == 0:
            self.session_start_ts_ns = ts_ns
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
            venue.current_mark = float(event.data.get("mark_price") or event.data.get("oracle_price") or venue.current_mid)

        elif event.event_type == SimEventType.CLOCK_TICK:
            self._handle_clock_tick(venue, ts_ns)

        return generated_fills

    def _process_in_flight_arrivals(self, current_ts_ns: int) -> None:
        """Activates scheduled place/modify/cancel order arrivals when timestamp arrives.
        Calculates queue ahead depth at actual arrival time using local order book (fix V-07).
        """
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

                    # Resting order established! Calculate queue ahead at ARRIVAL time (fix V-07)
                    order.status = OrderStatus.RESTING

                    if order.side == "BUY":
                        queue_size = 0.0
                        for p, s in venue.orderbook.bids.items():
                            if abs(float(p) - order.price) < 1e-6:
                                queue_size = float(s)
                                break
                        if queue_size > 0:
                            order.queue_ahead_size = queue_size
                        elif abs(order.price - venue.best_bid) < 1e-6:
                            order.queue_ahead_size = venue.best_bid_size
                        else:
                            order.queue_ahead_size = 0.0
                    else:  # SELL
                        queue_size = 0.0
                        for p, s in venue.orderbook.asks.items():
                            if abs(float(p) - order.price) < 1e-6:
                                queue_size = float(s)
                                break
                        if queue_size > 0:
                            order.queue_ahead_size = queue_size
                        elif abs(order.price - venue.best_ask) < 1e-6:
                            order.queue_ahead_size = venue.best_ask_size
                        else:
                            order.queue_ahead_size = 0.0

                    # Assign order to active model slot
                    if order.fill_model is not None and not self.paired_common_quotes:
                        if order.side == "BUY":
                            ctx.active_bid[order.fill_model] = order
                        else:
                            ctx.active_ask[order.fill_model] = order
                    else:
                        for fm in ctx.fill_models:
                            if order.side == "BUY":
                                ctx.active_bid[fm] = order.copy()
                            else:
                                ctx.active_ask[fm] = order.copy()

                elif order.status == OrderStatus.CANCEL_REQUESTED:
                    order.status = OrderStatus.CANCELLED
                    target_models = [order.fill_model] if (order.fill_model and not self.paired_common_quotes) else ctx.fill_models
                    for fm in target_models:
                        if order.side == "BUY" and ctx.active_bid[fm] and ctx.active_bid[fm].order_id == order.order_id:
                            ctx.active_bid[fm] = None
                        elif order.side == "SELL" and ctx.active_ask[fm] and ctx.active_ask[fm].order_id == order.order_id:
                            ctx.active_ask[fm] = None

            # Process in-place cancel requests whose cancel arrival has reached current_ts_ns
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
        """Updates venue BBO, checks crossed book, and handles risk recovery (fix V-09)."""
        contents = data.get("contents") if isinstance(data.get("contents"), dict) else data
        best_bid = contents.get("bestBid") or data.get("bestBid") or {}
        best_ask = contents.get("bestAsk") or data.get("bestAsk") or {}
        bid = float(data.get("bid_price") or contents.get("bid_price") or best_bid.get("price") or 0.0)
        ask = float(data.get("ask_price") or contents.get("ask_price") or best_ask.get("price") or 0.0)
        bid_s = float(data.get("bid_size") or contents.get("bid_size") or best_bid.get("size") or 0.0)
        ask_s = float(data.get("ask_size") or contents.get("ask_size") or best_ask.get("size") or 0.0)

        if bid > 0 and ask > 0:
            if bid >= ask:
                venue.book_valid = False
                for ctx in self.contexts.values():
                    ctx.set_risk_state(venue.market, RiskState.FLATTENED_CROSSED_BOOK)
                return

            venue.best_bid = bid
            venue.best_ask = ask
            venue.best_bid_size = bid_s
            venue.best_ask_size = ask_s
            venue.current_mid = (bid + ask) / 2.0
            venue.last_bbo_ts_ns = ts_ns

            if venue.clean_bbo_count_since_stale == 0:
                venue.stale_recovery_start_ts_ns = ts_ns
            venue.clean_bbo_count_since_stale += 1

            # Recovery transitions for PAUSED_STALE_FEED, PAUSED_GAP, and FLATTENED_CROSSED_BOOK (fix V-09)
            for ctx in self.contexts.values():
                curr_state = ctx.get_risk_state(venue.market)
                if curr_state == RiskState.PAUSED_STALE_FEED:
                    if venue.clean_bbo_count_since_stale >= 20 and (ts_ns - venue.stale_recovery_start_ts_ns) >= 5_000_000_000:
                        ctx.set_risk_state(venue.market, RiskState.NORMAL)
                        logger.info(f"[{venue.market}] Recovered from PAUSED_STALE_FEED to NORMAL")
                elif curr_state == RiskState.PAUSED_GAP:
                    if venue.book_valid and venue.orderbook.is_synced:
                        ctx.set_risk_state(venue.market, RiskState.NORMAL)
                        logger.info(f"[{venue.market}] Recovered from PAUSED_GAP to NORMAL")
                elif curr_state == RiskState.FLATTENED_CROSSED_BOOK:
                    if venue.clean_bbo_count_since_stale >= 20:
                        ctx.set_risk_state(venue.market, RiskState.NORMAL)
                        logger.info(f"[{venue.market}] Recovered from FLATTENED_CROSSED_BOOK to NORMAL")

            # Update causal realized volatility
            venue.current_volatility = venue.volatility_estimator.update(ts_ns, venue.current_mid)

    def _handle_l2_delta_event(self, venue: MarketState, data: Dict[str, Any], ts_ns: int) -> None:
        """Applies order book snapshot/delta to LocalOrderBook (fix V-06)."""
        contents = data.get("contents") if isinstance(data.get("contents"), dict) else data
        seq = contents.get("lastSequenceId") or contents.get("sequence") or data.get("lastSequenceId")
        venue.last_seq = seq

        is_snapshot = (
            bool(data.get("isSnapshot"))
            or data.get("type") == "subscribed"
            or (isinstance(contents, dict) and len(contents.get("bids", [])) > 5 and len(contents.get("asks", [])) > 5)
        )

        if is_snapshot:
            venue.orderbook.apply_snapshot(data)
            venue.book_valid = True
            for ctx in self.contexts.values():
                if ctx.get_risk_state(venue.market) == RiskState.PAUSED_GAP:
                    ctx.set_risk_state(venue.market, RiskState.NORMAL)
        else:
            applied = venue.orderbook.apply_delta(data)
            if not applied or venue.orderbook.sequence_gap_detected:
                venue.book_valid = False
                venue.invalid_intervals.append({
                    "market": venue.market,
                    "expected": venue.last_seq + 1 if venue.last_seq else None,
                    "received": seq,
                    "ts_ns": ts_ns
                })
                for ctx in self.contexts.values():
                    ctx.set_risk_state(venue.market, RiskState.PAUSED_GAP)

    def _handle_trade_event(self, venue: MarketState, data: Dict[str, Any], ts_ns: int) -> List[Dict[str, Any]]:
        """Processes trade fills against resting and in-flight cancel-requested orders."""
        trades_list: List[Dict[str, Any]] = []
        if isinstance(data.get("contents"), list):
            trades_list = data["contents"]
        elif isinstance(data.get("contents"), dict) and "price" in data["contents"]:
            trades_list = [data["contents"]]
        elif isinstance(data, dict) and "price" in data:
            trades_list = [data]

        if not trades_list:
            return []

        fills_generated: List[Dict[str, Any]] = []

        for single_trade in trades_list:
            trade_p = float(single_trade.get("price") or 0.0)
            trade_s = float(single_trade.get("size") or 0.0)
            trade_side = str(single_trade.get("side", "")).upper()

            if trade_p <= 0 or trade_s <= 0 or not trade_side:
                continue

            # Update venue trade flow for OFI tracking (fix W-03)
            venue.update_trade_flow(trade_side, trade_s, ts_ns)

            for ctx in self.contexts.values():
                if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                    continue
                for fm in ctx.fill_models:
                    pnl_eng = ctx.pnl_engines[fm]

                    # 1. Check BID fills (taker sells hitting our bid)
                    bid_order = ctx.active_bid[fm]
                    if bid_order and bid_order.status in (OrderStatus.RESTING, OrderStatus.CANCEL_REQUESTED):
                        # Speed bump modeling (fix W-05): MM ALO cancels bypass the taker speed bump
                        if (
                            bid_order.status == OrderStatus.CANCEL_REQUESTED
                            and bid_order.cancel_arrival_ts_ns
                            and self.taker_speed_bump_ms > 0
                        ):
                            effective_taker_match_ts = ts_ns + int(self.taker_speed_bump_ms * 1e6)
                            if bid_order.cancel_arrival_ts_ns <= effective_taker_match_ts:
                                bid_order.status = OrderStatus.CANCELLED
                                ctx.active_bid[fm] = None
                                continue

                        was_in_flight = (bid_order.status == OrderStatus.CANCEL_REQUESTED)
                        fill_qty = self._evaluate_fill_quantity(fm, bid_order, trade_side, trade_p, trade_s, venue.tick_size)
                        if fill_qty > 0:
                            fee = pnl_eng.record_fill("BUY", bid_order.price, fill_qty, venue.current_mid, is_taker=False, ts_ns=ts_ns)
                            self.subaccount_rate_limiter.record_fill(fill_qty * bid_order.price)
                            bid_order.remaining_size -= fill_qty
                            if bid_order.remaining_size <= 1e-9:
                                bid_order.status = OrderStatus.FILLED
                                ctx.active_bid[fm] = None

                            quote_hash = hashlib.sha256(f"{bid_order.market}:{bid_order.side}:{bid_order.price:.5f}:{bid_order.created_ts_ns}:{bid_order.order_id}".encode()).hexdigest()[:16]
                            obs_key = f"{venue.market}:{ctx.strategy_id}:{fm.value}:{quote_hash}"
                            match_key = f"{venue.market}:{ctx.strategy_id}:{ts_ns}:{trade_side}:{trade_p}:{trade_s}"
                            ctx.unique_physical_matches.add(match_key)

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
                                "was_in_flight_cancel": was_in_flight,
                                "observation_key": obs_key,
                                "quote_hash": quote_hash,
                                "rth_tag": classify_rth_capture_tag(ts_ns),
                            }
                            fills_generated.append(fill_rec)
                            ctx.fill_records.append(fill_rec)
                            self._hash_fill_record(fill_rec)

                    # 2. Check ASK fills (taker buys lifting our ask)
                    ask_order = ctx.active_ask[fm]
                    if ask_order and ask_order.status in (OrderStatus.RESTING, OrderStatus.CANCEL_REQUESTED):
                        # Speed bump modeling (fix W-05): MM ALO cancels bypass the taker speed bump
                        if (
                            ask_order.status == OrderStatus.CANCEL_REQUESTED
                            and ask_order.cancel_arrival_ts_ns
                            and self.taker_speed_bump_ms > 0
                        ):
                            effective_taker_match_ts = ts_ns + int(self.taker_speed_bump_ms * 1e6)
                            if ask_order.cancel_arrival_ts_ns <= effective_taker_match_ts:
                                ask_order.status = OrderStatus.CANCELLED
                                ctx.active_ask[fm] = None
                                continue

                        was_in_flight = (ask_order.status == OrderStatus.CANCEL_REQUESTED)
                        fill_qty = self._evaluate_fill_quantity(fm, ask_order, trade_side, trade_p, trade_s, venue.tick_size)
                        if fill_qty > 0:
                            fee = pnl_eng.record_fill("SELL", ask_order.price, fill_qty, venue.current_mid, is_taker=False, ts_ns=ts_ns)
                            self.subaccount_rate_limiter.record_fill(fill_qty * ask_order.price)
                            ask_order.remaining_size -= fill_qty
                            if ask_order.remaining_size <= 1e-9:
                                ask_order.status = OrderStatus.FILLED
                                ctx.active_ask[fm] = None

                            quote_hash = hashlib.sha256(f"{ask_order.market}:{ask_order.side}:{ask_order.price:.5f}:{ask_order.created_ts_ns}:{ask_order.order_id}".encode()).hexdigest()[:16]
                            obs_key = f"{venue.market}:{ctx.strategy_id}:{fm.value}:{quote_hash}"
                            match_key = f"{venue.market}:{ctx.strategy_id}:{ts_ns}:{trade_side}:{trade_p}:{trade_s}"
                            ctx.unique_physical_matches.add(match_key)

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
                                "was_in_flight_cancel": was_in_flight,
                                "quote_hash": quote_hash,
                                "observation_key": obs_key,
                                "rth_tag": classify_rth_capture_tag(ts_ns),
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
        tick_size: float = 0.0,
    ) -> float:
        """Applies exact fill model semantics: Model A (touch), Model B (queue), Model C (trade-through by >= 1 tick)."""
        tick = tick_size if tick_size > 0 else 1e-6
        if order.side == "BUY":
            if trade_side != "SELL":
                return 0.0

            if fill_model == FillModelType.MODEL_A_TOUCH:
                return min(order.remaining_size, trade_size) if trade_price <= order.price else 0.0

            elif fill_model == FillModelType.MODEL_C_CONSERVATIVE:
                # W-09: Trade strictly through resting order price by at least 1 tick
                return min(order.remaining_size, trade_size) if trade_price <= (order.price - tick + 1e-6) else 0.0

            elif fill_model == FillModelType.MODEL_B_MODERATE:
                if trade_price < order.price - 1e-6:
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

        elif order.side == "SELL":
            if trade_side != "BUY":
                return 0.0

            if fill_model == FillModelType.MODEL_A_TOUCH:
                return min(order.remaining_size, trade_size) if trade_price >= order.price else 0.0

            elif fill_model == FillModelType.MODEL_C_CONSERVATIVE:
                # W-09: Trade strictly through resting order price by at least 1 tick
                return min(order.remaining_size, trade_size) if trade_price >= (order.price + tick - 1e-6) else 0.0

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
        microprice_dev_bps = venue.get_microprice_and_ofi_deviation(ts_ns)

        elapsed_hours = max(1.0, (ts_ns - self.session_start_ts_ns) / (3600.0 * 1e9)) if self.session_start_ts_ns > 0 else 1.0

        for ctx in self.contexts.values():
            if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                continue

            # Maintenance margin & liquidation check (W-05 / V-14)
            is_liquidated = False
            for fm in ctx.fill_models:
                pnl_eng = ctx.pnl_engines[fm]
                pos = pnl_eng.position
                if abs(pos) > 1e-9:
                    mid = venue.current_mid
                    mark = venue.current_mark if venue.current_mark > 0 else mid
                    equity = pnl_eng.compute_equity(mid)
                    mmf = getattr(venue, "maintenance_margin_fraction", 0.03)
                    maint_margin = abs(pos) * mark * mmf
                    if equity <= maint_margin:
                        is_liquidated = True
                        ctx.set_risk_state(venue.market, RiskState.FLATTENED_LIQUIDATION)
                        if ctx.active_bid[fm]:
                            ctx.active_bid[fm].status = OrderStatus.CANCELLED
                            ctx.active_bid[fm] = None
                        if ctx.active_ask[fm]:
                            ctx.active_ask[fm].status = OrderStatus.CANCELLED
                            ctx.active_ask[fm] = None

                        flatten_side = "SELL" if pos > 0 else "BUY"
                        flatten_qty = abs(pos)
                        flatten_price = (venue.best_bid - venue.tick_size) if flatten_side == "SELL" else (venue.best_ask + venue.tick_size)
                        if flatten_price <= 0:
                            flatten_price = mid * (0.99 if flatten_side == "SELL" else 1.01)

                        pnl_eng.record_fill(flatten_side, flatten_price, flatten_qty, mid, is_taker=True, ts_ns=ts_ns)
                        logger.warning(
                            f"[{venue.market}] LIQUIDATION TRIGGERED on {ctx.strategy_id} ({fm.value}): "
                            f"Equity ${equity:.2f} <= MaintMargin ${maint_margin:.2f}. Forced flatten {flatten_side} {flatten_qty} @ {flatten_price:.4f}"
                        )

            if is_liquidated or ctx.get_risk_state(venue.market) in (
                RiskState.PAUSED_GAP,
                RiskState.PAUSED_STALE_FEED,
                RiskState.PAUSED_ANOMALY,
                RiskState.FLATTENED_CROSSED_BOOK,
                RiskState.FLATTENED_LIQUIDATION,
            ):
                continue

            # Sanity invariant: |PnL| <= initial_capital * 0.50 per hour (W-06)
            max_pnl = ctx.initial_capital * 0.50 * elapsed_hours
            pnl_anomalous = False
            for fm, pnl_eng in ctx.pnl_engines.items():
                eq = pnl_eng.compute_equity(venue.current_mid)
                net = eq - pnl_eng.initial_capital
                if abs(net) > max_pnl:
                    pnl_anomalous = True
                    break

            if pnl_anomalous:
                if ctx.get_risk_state(venue.market) != RiskState.PAUSED_ANOMALY:
                    logger.warning(
                        f"[{venue.market}] PnL sanity invariant breached on {ctx.strategy_id} "
                        f"(|PnL| > ${max_pnl:.2f} in {elapsed_hours:.2f}h). Transitioning to PAUSED_ANOMALY."
                    )
                    ctx.set_risk_state(venue.market, RiskState.PAUSED_ANOMALY)
                    for fm in ctx.fill_models:
                        if ctx.active_bid[fm]:
                            ctx.active_bid[fm].status = OrderStatus.CANCELLED
                            ctx.active_bid[fm] = None
                        if ctx.active_ask[fm]:
                            ctx.active_ask[fm].status = OrderStatus.CANCELLED
                            ctx.active_ask[fm] = None
                continue

            if self.paired_common_quotes:
                # Diagnostic mode: quote keyed to Model B inventory (legacy behavior)
                pnl_b = ctx.pnl_engines[FillModelType.MODEL_B_MODERATE]
                inv_units = pnl_b.position
                quotes = ctx.strategy.generate_quotes(
                    mid_price=venue.current_mid,
                    inventory_units=inv_units,
                    volatility=venue.current_volatility,
                    market_spread_bps=spread_bps,
                    microprice_dev_bps=microprice_dev_bps,
                )
                if quotes:
                    target_bid, target_ask = quotes
                    self._schedule_quote_update(venue, ctx, None, target_bid, target_ask, ts_ns)
            else:
                # Independent fill model simulation worlds (fix V-12)
                for fm in ctx.fill_models:
                    pnl_eng = ctx.pnl_engines[fm]
                    inv_units = pnl_eng.position

                    # Check inventory cap
                    clip_notional = venue.get_min_executable_clip()
                    if abs(inv_units * venue.current_mid) > ctx.max_inventory_clips * clip_notional:
                        ctx.set_risk_state(venue.market, RiskState.REDUCE_ONLY)

                    quotes = ctx.strategy.generate_quotes(
                        mid_price=venue.current_mid,
                        inventory_units=inv_units,
                        volatility=venue.current_volatility,
                        market_spread_bps=spread_bps,
                        microprice_dev_bps=microprice_dev_bps,
                    )
                    if not quotes:
                        continue

                    target_bid, target_ask = quotes
                    # In reduce only, prevent increasing quotes
                    if ctx.get_risk_state(venue.market) == RiskState.REDUCE_ONLY:
                        if inv_units > 0:
                            target_bid = None  # Long: cannot buy more
                        elif inv_units < 0:
                            target_ask = None  # Short: cannot sell more

                    self._schedule_quote_update(venue, ctx, fm, target_bid, target_ask, ts_ns)

    def _schedule_quote_update(
        self,
        venue: MarketState,
        ctx: StrategyInstanceContext,
        fill_model: Optional[FillModelType],
        target_bid: Optional[Quote],
        target_ask: Optional[Quote],
        ts_ns: int,
    ) -> None:
        """Schedules place, modify, or cancel-replace with latency and rate-limit enforcement (fix V-10)."""
        now_sec = ts_ns / 1e9
        models_to_update = [fill_model] if (fill_model is not None and not self.paired_common_quotes) else [None]

        # 1. Update BID
        if target_bid:
            target_p = float(snap_to_tick(target_bid.price, venue.tick_size))
            target_s = float(snap_to_step(target_bid.size, venue.step_size))
            if (
                target_s >= venue.min_order_size - 1e-9
                and target_s <= venue.max_order_size + 1e-9
                and target_s * target_p >= venue.min_notional - 1e-6
            ):
                for fm in models_to_update:
                    existing_bid = ctx.active_bid.get(fm) if fm is not None else (ctx.active_bid.get(ctx.fill_models[0]) if ctx.fill_models else None)
                    if existing_bid and existing_bid.status == OrderStatus.RESTING:
                        # Requote threshold check (fix V-10)
                        price_diff = abs(target_p - existing_bid.price)
                        if price_diff < venue.tick_size * self.subaccount_rate_limiter.requote_threshold_ticks and abs(target_s - existing_bid.remaining_size) < 1e-9:
                            continue  # Keep priority! Do not cancel

                        # Check rate limit before cancel
                        if not self.subaccount_rate_limiter.can_cancel_order(now_sec):
                            ctx.rate_limited_actions_count += 1
                            continue
                        self.subaccount_rate_limiter.record_cancellation(now_sec)
                        cancel_lat = self.sample_latency_ns("cancel")
                        if fm is None:
                            for m in ctx.fill_models:
                                if ctx.active_bid[m]:
                                    ctx.active_bid[m].status = OrderStatus.CANCEL_REQUESTED
                                    ctx.active_bid[m].cancel_arrival_ts_ns = ts_ns + cancel_lat
                        else:
                            existing_bid.status = OrderStatus.CANCEL_REQUESTED
                            existing_bid.cancel_arrival_ts_ns = ts_ns + cancel_lat

                    # Check rate limit before place
                    if not self.subaccount_rate_limiter.can_place_order(now_sec):
                        ctx.rate_limited_actions_count += 1
                        continue
                    self.subaccount_rate_limiter.record_order_placement(now_sec)

                    place_lat = self.sample_latency_ns("place")
                    ctx.order_counter += 1
                    new_order = SimulatedOrder(
                        order_id=f"{ctx.strategy_id}_{fm.value if fm else 'all'}_bid_{ctx.order_counter}",
                        client_order_id=f"cl_{ctx.order_counter}",
                        market=venue.market,
                        side="BUY",
                        price=target_p,
                        size=target_s,
                        remaining_size=target_s,
                        status=OrderStatus.SUBMITTING,
                        created_ts_ns=ts_ns,
                        arrival_ts_ns=ts_ns + place_lat,
                        fill_model=fm,
                    )
                    ctx.in_flight_orders.append(new_order)

        # 2. Update ASK
        if target_ask:
            target_p = float(snap_to_tick(target_ask.price, venue.tick_size))
            target_s = float(snap_to_step(target_ask.size, venue.step_size))
            if (
                target_s >= venue.min_order_size - 1e-9
                and target_s <= venue.max_order_size + 1e-9
                and target_s * target_p >= venue.min_notional - 1e-6
            ):
                for fm in models_to_update:
                    existing_ask = ctx.active_ask.get(fm) if fm is not None else (ctx.active_ask.get(ctx.fill_models[0]) if ctx.fill_models else None)
                    if existing_ask and existing_ask.status == OrderStatus.RESTING:
                        price_diff = abs(target_p - existing_ask.price)
                        if price_diff < venue.tick_size * self.subaccount_rate_limiter.requote_threshold_ticks and abs(target_s - existing_ask.remaining_size) < 1e-9:
                            continue

                        if not self.subaccount_rate_limiter.can_cancel_order(now_sec):
                            ctx.rate_limited_actions_count += 1
                            continue
                        self.subaccount_rate_limiter.record_cancellation(now_sec)
                        cancel_lat = self.sample_latency_ns("cancel")
                        if fm is None:
                            for m in ctx.fill_models:
                                if ctx.active_ask[m]:
                                    ctx.active_ask[m].status = OrderStatus.CANCEL_REQUESTED
                                    ctx.active_ask[m].cancel_arrival_ts_ns = ts_ns + cancel_lat
                        else:
                            existing_ask.status = OrderStatus.CANCEL_REQUESTED
                            existing_ask.cancel_arrival_ts_ns = ts_ns + cancel_lat

                    if not self.subaccount_rate_limiter.can_place_order(now_sec):
                        ctx.rate_limited_actions_count += 1
                        continue
                    self.subaccount_rate_limiter.record_order_placement(now_sec)

                    place_lat = self.sample_latency_ns("place")
                    ctx.order_counter += 1
                    new_order = SimulatedOrder(
                        order_id=f"{ctx.strategy_id}_{fm.value if fm else 'all'}_ask_{ctx.order_counter}",
                        client_order_id=f"cl_{ctx.order_counter}",
                        market=venue.market,
                        side="SELL",
                        price=target_p,
                        size=target_s,
                        remaining_size=target_s,
                        status=OrderStatus.SUBMITTING,
                        created_ts_ns=ts_ns,
                        arrival_ts_ns=ts_ns + place_lat,
                        fill_model=fm,
                    )
                    ctx.in_flight_orders.append(new_order)

    def _handle_funding_event(self, venue: MarketState, data: Dict[str, Any], ts_ns: int) -> None:
        """Handles funding events. Settle funding only on realized settlements, protecting against 60x overcharge (fix V-08)."""
        rate = float(data.get("rate1h") or data.get("rate") or data.get("funding_rate") or 0.0)
        venue.predicted_funding_rate = rate

        is_predicted = bool(data.get("is_predicted") or data.get("channel") == "predictedFunding")
        is_settlement = (
            bool(data.get("is_settlement") or data.get("event_type") == "REALIZED" or data.get("is_realized"))
            or ("funding_rate" in data and not is_predicted)
        )
        if not is_settlement:
            # Predicted rate update only; do NOT charge PnL on every streaming predictedFunding message (fix V-08)
            return

        ref_price = venue.current_mark if venue.current_mark > 0 else (venue.current_mid if venue.current_mid > 0 else 1.0)
        if venue.category in ("EQUITIES", "COMMODITIES", "INDICES") and venue.is_outside_rth:
            rate = 0.000005  # Fixed off-hours rate

        for ctx in self.contexts.values():
            if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                continue
            for fm, pnl_eng in ctx.pnl_engines.items():
                pnl_eng.apply_funding(rate, ref_price)

    def _handle_clock_tick(self, venue: MarketState, ts_ns: int) -> None:
        """Evaluates stale BBO watchdogs, hourly discrete settlements, and periodic risk checks."""
        # 1. Stale BBO (> 3 seconds)
        if venue.last_bbo_ts_ns > 0 and (ts_ns - venue.last_bbo_ts_ns) > 3_000_000_000:
            for ctx in self.contexts.values():
                if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                    continue
                if ctx.get_risk_state(venue.market) != RiskState.PAUSED_STALE_FEED:
                    ctx.set_risk_state(venue.market, RiskState.PAUSED_STALE_FEED)
                    venue.clean_bbo_count_since_stale = 0
                    venue.stale_recovery_start_ts_ns = ts_ns
                    for fm in ctx.fill_models:
                        if ctx.active_bid[fm]:
                            ctx.active_bid[fm].status = OrderStatus.CANCELLED
                            ctx.active_bid[fm] = None
                        if ctx.active_ask[fm]:
                            ctx.active_ask[fm].status = OrderStatus.CANCELLED
                            ctx.active_ask[fm] = None

        # 2. Hourly discrete funding settlement on clock rollover
        current_hour = ts_ns // (3600 * 1_000_000_000)
        if venue.last_settled_hour is not None and current_hour > venue.last_settled_hour:
            ref_price = venue.current_mark if venue.current_mark > 0 else (venue.current_mid if venue.current_mid > 0 else 1.0)
            rate = venue.predicted_funding_rate
            for ctx in self.contexts.values():
                if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                    continue
                for fm, pnl_eng in ctx.pnl_engines.items():
                    pnl_eng.apply_funding(rate, ref_price)
            venue.last_settled_hour = current_hour
        elif venue.last_settled_hour is None:
            venue.last_settled_hour = current_hour

        # 3. Sanity invariant: |PnL| <= initial_capital * 0.50 per hour (W-06)
        elapsed_hours = max(1.0, (ts_ns - self.session_start_ts_ns) / (3600.0 * 1e9)) if self.session_start_ts_ns > 0 else 1.0
        for ctx in self.contexts.values():
            if hasattr(ctx.strategy, "market") and ctx.strategy.market != venue.market:
                continue
            max_pnl = ctx.initial_capital * 0.50 * elapsed_hours
            for fm, pnl_eng in ctx.pnl_engines.items():
                eq = pnl_eng.compute_equity(venue.current_mid)
                net = eq - pnl_eng.initial_capital
                if abs(net) > max_pnl:
                    if ctx.get_risk_state(venue.market) != RiskState.PAUSED_ANOMALY:
                        logger.warning(
                            f"[{venue.market}] Clock tick PnL sanity invariant breached on {ctx.strategy_id} "
                            f"(|PnL| > ${max_pnl:.2f} in {elapsed_hours:.2f}h). Transitioning to PAUSED_ANOMALY."
                        )
                        ctx.set_risk_state(venue.market, RiskState.PAUSED_ANOMALY)
                        for m in ctx.fill_models:
                            if ctx.active_bid[m]:
                                ctx.active_bid[m].status = OrderStatus.CANCELLED
                                ctx.active_bid[m] = None
                            if ctx.active_ask[m]:
                                ctx.active_ask[m].status = OrderStatus.CANCELLED
                                ctx.active_ask[m] = None
                    break

    def _hash_fill_record(self, fill_rec: Dict[str, Any]) -> None:
        """Appends deterministic canonical hash of fill record for bit-for-bit replay parity."""
        msg = f"{fill_rec['strategy_id']}:{fill_rec['fill_model']}:{fill_rec['side']}:{fill_rec['price']:.5f}:{fill_rec['size']:.6f}:{fill_rec['ts_ns']}"
        self.fill_log_hasher.update(msg.encode())

    def get_fill_log_hash(self) -> str:
        return self.fill_log_hasher.hexdigest()

    def get_total_unique_physical_matches(self) -> int:
        """Returns total unique physical trade events matched across all strategies (W-07 deduplication)."""
        return sum(ctx.unique_physical_matches_count for ctx in self.contexts.values())


class BacktestRunResult:
    """Encapsulates backtest simulation output and research diagnostics."""

    def __init__(
        self,
        market: str,
        strategy_name: str,
        fill_model: str,
        fidelity: str,
        latency_ms: float,
        pnl_summary: Dict[str, Any],
        rate_limit_metrics: Dict[str, Any],
        markout_metrics: Dict[str, Any],
        event_count: int,
        duration_hours: float,
        in_flight_fills_count: int = 0,
        in_place_modifications_count: int = 0,
        cancel_replace_count: int = 0,
    ):
        self.market = market
        self.strategy_name = strategy_name
        self.fill_model = fill_model
        self.fidelity = fidelity
        self.latency_ms = latency_ms
        self.pnl_summary = pnl_summary
        self.rate_limit_metrics = rate_limit_metrics
        self.markout_metrics = markout_metrics
        self.event_count = event_count
        self.duration_hours = duration_hours
        self.in_flight_fills_count = in_flight_fills_count
        self.in_place_modifications_count = in_place_modifications_count
        self.cancel_replace_count = cancel_replace_count

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "market": self.market,
            "strategy": self.strategy_name,
            "fill_model": self.fill_model,
            "fidelity": self.fidelity,
            "latency_ms": self.latency_ms,
            "duration_hours": round(self.duration_hours, 2),
            "events_simulated": self.event_count,
            "in_flight_fills_count": self.in_flight_fills_count,
            "in_place_modifications_count": self.in_place_modifications_count,
            "cancel_replace_count": self.cancel_replace_count,
        }
        res.update(self.pnl_summary)
        res.update(self.rate_limit_metrics)
        res["markouts"] = self.markout_metrics
        return res


class ArcusEventBacktester:
    """Adapter running historical DataFrames through SimEngine."""

    def __init__(
        self,
        strategy: BaseMarketMakingStrategy,
        fill_model: FillModelType = FillModelType.MODEL_B_MODERATE,
        latency_config: Optional[LatencyConfig] = None,
        initial_capital: float = 100.0,
        maker_fee_bps: float = 0.0,
        taker_fee_bps: float = 2.25,
        requote_threshold_ticks: int = 2,
    ):
        self.strategy = strategy
        self.fill_model = fill_model
        self.latency = latency_config or LatencyConfig()
        self.initial_capital = initial_capital
        self.maker_fee_bps = maker_fee_bps
        self.taker_fee_bps = taker_fee_bps
        self.requote_threshold_ticks = requote_threshold_ticks

        self.market = strategy.market
        self.specs = {
            self.market: {
                "tick_size": getattr(strategy, "tick_size", 0.1),
                "step_size": getattr(strategy, "step_size", 0.0001),
                "min_notional": getattr(strategy, "min_notional", 5.0),
                "min_order_size": getattr(strategy, "min_order_size", 0.0),
            }
        }

        self.engine = SimEngine(
            markets=[self.market],
            market_specs=self.specs,
            strategies={self.strategy.__class__.__name__: self.strategy},
            fill_models=[self.fill_model],
            latency_config=self.latency,
            initial_capital=self.initial_capital,
            paired_common_quotes=False,
            subaccount_rate_limiter=ArcusRateLimitSimulator(
                requote_threshold_ticks=requote_threshold_ticks
            ),
        )

    @property
    def pnl_engine(self) -> PnLAttributionEngine:
        ctx = self.engine.contexts[self.strategy.__class__.__name__]
        return ctx.pnl_engines[self.fill_model]

    @property
    def rate_limiter(self) -> ArcusRateLimitSimulator:
        return self.engine.subaccount_rate_limiter

    @property
    def orderbook(self) -> LocalOrderBook:
        return self.engine.venues[self.market].orderbook

    @property
    def latest_mid_price(self) -> float:
        return self.engine.venues[self.market].current_mid

    def run_simulation(
        self,
        df_bbo: pd.DataFrame,
        df_trades: pd.DataFrame,
        funding_data: Optional[List[Dict[str, Any]]] = None,
        df_l2: Optional[pd.DataFrame] = None,
    ) -> BacktestRunResult:
        fidelity = "HIGH_FIDELITY_L2" if (df_l2 is not None and not df_l2.empty) else "LOW_FIDELITY_BBO"
        sim_events: List[SimEvent] = []

        if df_bbo is not None and not df_bbo.empty:
            for row in df_bbo.itertuples():
                sim_events.append(SimEvent(
                    event_type=SimEventType.BBO,
                    recv_ts_ns=int(row.recv_ts_ns),
                    market=self.market,
                    data={
                        "bid_price": float(row.bid_price),
                        "ask_price": float(row.ask_price),
                        "bid_size": float(getattr(row, "bid_size", 1.0)),
                        "ask_size": float(getattr(row, "ask_size", 1.0)),
                        "mid_price": float(getattr(row, "mid_price", (row.bid_price + row.ask_price) / 2.0)),
                        "spread_bps": float(getattr(row, "spread_bps", 0.0)),
                    }
                ))

        if df_trades is not None and not df_trades.empty:
            for row in df_trades.itertuples():
                sim_events.append(SimEvent(
                    event_type=SimEventType.TRADE,
                    recv_ts_ns=int(row.recv_ts_ns),
                    market=self.market,
                    data={
                        "price": float(row.price),
                        "size": float(row.size),
                        "side": str(row.side).upper(),
                    }
                ))

        if df_l2 is not None and not df_l2.empty:
            for row in df_l2.itertuples():
                is_snap = bool(getattr(row, "is_snapshot", False))
                seq = getattr(row, "sequence_id", None) or getattr(row, "lastSequenceId", None)
                sim_events.append(SimEvent(
                    event_type=SimEventType.L2_DELTA,
                    recv_ts_ns=int(row.recv_ts_ns),
                    market=self.market,
                    data={
                        "isSnapshot": is_snap,
                        "lastSequenceId": seq,
                        "bids": getattr(row, "bids_json", getattr(row, "bids", [])),
                        "asks": getattr(row, "asks_json", getattr(row, "asks", [])),
                    }
                ))

        if funding_data:
            for item in funding_data:
                ts = int(item.get("timestamp") or item.get("ts_ns") or 0)
                rate = float(item.get("fundingRate") or item.get("rate") or item.get("rate1h") or 0.0)
                sim_events.append(SimEvent(
                    event_type=SimEventType.FUNDING,
                    recv_ts_ns=ts,
                    market=self.market,
                    data={"funding_rate": rate, "is_settlement": True},
                ))

        sim_events.sort(key=lambda ev: ev.recv_ts_ns)
        if not sim_events:
            raise ValueError("No historical events available for simulation")

        start_ts_ns = sim_events[0].recv_ts_ns
        end_ts_ns = sim_events[-1].recv_ts_ns
        duration_hours = max(0.01, (end_ts_ns - start_ts_ns) / (1e9 * 3600.0))

        # Replay events through SimEngine
        for ev in sim_events:
            self.engine.on_event(ev)

        # Force clock tick at end to settle pending actions if needed
        self.engine.on_event(SimEvent(
            event_type=SimEventType.CLOCK_TICK,
            recv_ts_ns=end_ts_ns + int(1e9),
            market=self.market,
            data={},
        ))

        ctx = self.engine.contexts[self.strategy.__class__.__name__]
        pnl_summary = self.pnl_engine.get_summary(current_mid=self.latest_mid_price)
        rl_metrics = self.rate_limiter.to_metrics()

        # Markouts
        markout_metrics = {}
        if df_bbo is not None and not df_bbo.empty:
            bbo_ts_arr = df_bbo["recv_ts_ns"].values
            bbo_mid_arr = df_bbo["mid_price"].values
            markout_metrics = self.pnl_engine.get_fill_markouts(bbo_ts_arr, bbo_mid_arr)

        in_flight_fills = sum(1 for f in ctx.fill_records if f.get("was_in_flight_cancel", False))

        return BacktestRunResult(
            market=self.market,
            strategy_name=self.strategy.__class__.__name__,
            fill_model=self.fill_model.value,
            fidelity=fidelity,
            latency_ms=self.latency.total_place_latency_ms,
            pnl_summary=pnl_summary,
            rate_limit_metrics=rl_metrics,
            markout_metrics=markout_metrics,
            event_count=len(sim_events),
            duration_hours=duration_hours,
            in_flight_fills_count=in_flight_fills,
            in_place_modifications_count=self.rate_limiter.orders_modified,
            cancel_replace_count=self.rate_limiter.orders_cancelled,
        )
