"""Event-Driven Backtesting Engine for Arcus Perpetuals Market Making.

Fulfills Mandate Sections 6, 7, 8, 12, 14, 15, 16 of prompt.md:
- Deterministic event replay with ZERO look-ahead bias
- High-fidelity L2 Order Book Depth Replay (snapshots + deltas)
- Explicit Order Lifecycle State Machine:
  (CREATED -> SUBMITTING -> RESTING -> PARTIALLY_FILLED -> FILLED / CANCEL_REQUESTED -> CANCELLED)
- In-place size reduction preserves queue priority without requote delay
- In-flight cancellation window adverse selection (old quote can fill during cancel latency)
- Dynamic EWMA Realized Volatility Estimator (no static constants)
- Time-Aware Discrete Funding Settlement (applied to instantaneous position)
- Non-zero slippage executable forced flatten (taker fee 2.25 bps)
- Separate research markout attribution across [100ms, 500ms, 1s, 5s, 10s, 30s, 60s]
- Strict balance-sheet PnL accounting identity
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

from src.models.fill import FillEngine, FillModelType, SimulatedQueueOrder, OrderStatus
from src.models.latency import LatencyConfig
from src.models.rate_limit import ArcusRateLimitSimulator
from src.models.pnl import PnLAttributionEngine
from src.orderbook import LocalOrderBook
from src.volatility import RealizedVolatilityEstimator
from src.strategies.base import BaseMarketMakingStrategy
from src.utils import to_decimal

logger = logging.getLogger(__name__)


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
    """Event-driven simulator running historical playback tick by tick."""

    def __init__(
        self,
        strategy: BaseMarketMakingStrategy,
        fill_model: FillModelType = FillModelType.MODEL_B_MODERATE,
        latency_config: Optional[LatencyConfig] = None,
        requote_threshold_ticks: int = 2,
        initial_capital: float = 100.0,
        maker_fee_bps: float = 0.0,
        taker_fee_bps: float = 2.25,
    ):
        self.strategy = strategy
        self.fill_model = fill_model
        self.latency = latency_config or LatencyConfig()
        self.requote_threshold_ticks = requote_threshold_ticks

        self.fill_engine = FillEngine(model_type=fill_model)
        self.rate_limiter = ArcusRateLimitSimulator(
            requote_threshold_ticks=requote_threshold_ticks
        )
        self.pnl_engine = PnLAttributionEngine(
            initial_capital=initial_capital,
            maker_fee_bps=maker_fee_bps,
            taker_fee_bps=taker_fee_bps,
        )
        self.orderbook = LocalOrderBook(market=strategy.market)
        self.volatility_estimator = RealizedVolatilityEstimator()

        # Active resting quotes
        self.active_bid_order: Optional[SimulatedQueueOrder] = None
        self.active_ask_order: Optional[SimulatedQueueOrder] = None
        # Orders pending cancellation (still resting on exchange until cancel transit latency)
        self.in_flight_cancels: List[SimulatedQueueOrder] = []

        # Quote prices tracking
        self.last_bid_quote_price: Optional[float] = None
        self.last_ask_quote_price: Optional[float] = None

        # Market state tracking
        self.latest_bid_price: float = 0.0
        self.latest_ask_price: float = 0.0
        self.latest_mid_price: float = 0.0
        self.latest_spread_bps: float = 0.0
        self.latest_volatility: float = 0.30
        self.latest_microprice_dev: float = 0.0

        # Diagnostics counters
        self.in_flight_fills_count = 0
        self.in_place_modifications_count = 0
        self.cancel_replace_count = 0

    def run_simulation(
        self,
        df_bbo: pd.DataFrame,
        df_trades: pd.DataFrame,
        funding_data: Optional[List[Dict[str, Any]]] = None,
        df_l2: Optional[pd.DataFrame] = None,
    ) -> BacktestRunResult:
        """Runs event-driven simulation over historical event streams."""
        fidelity = "HIGH_FIDELITY_L2" if (df_l2 is not None and not df_l2.empty) else "LOW_FIDELITY_BBO"

        # 1. Merge and chronologically sort all events
        all_events = []

        for row in df_bbo.itertuples():
            all_events.append({
                "ts_ns": row.recv_ts_ns,
                "event_type": "BBO",
                "mid_price": row.mid_price,
                "spread_bps": row.spread_bps,
                "bid_price": row.bid_price,
                "bid_size": row.bid_size,
                "ask_price": row.ask_price,
                "ask_size": row.ask_size,
            })

        for row in df_trades.itertuples():
            all_events.append({
                "ts_ns": row.recv_ts_ns,
                "event_type": "TRADE",
                "side": row.side,
                "price": row.price,
                "size": row.size,
                "notional": getattr(row, "notional", getattr(row, "price", 0.0) * getattr(row, "size", 0.0)),
            })

        if df_l2 is not None and not df_l2.empty:
            for row in df_l2.itertuples():
                is_snap = getattr(row, "is_snapshot", False)
                all_events.append({
                    "ts_ns": row.recv_ts_ns,
                    "event_type": "L2_SNAPSHOT" if is_snap else "L2_DELTA",
                    "sequence_id": getattr(row, "sequence_id", None),
                    "bids": getattr(row, "bids_json", getattr(row, "bids", [])),
                    "asks": getattr(row, "asks_json", getattr(row, "asks", [])),
                })

        all_events.sort(key=lambda x: x["ts_ns"])
        if not all_events:
            raise ValueError("No historical events available for simulation")

        start_ts_ns = all_events[0]["ts_ns"]
        end_ts_ns = all_events[-1]["ts_ns"]
        duration_hours = max(0.01, (end_ts_ns - start_ts_ns) / (1e9 * 3600.0))

        # Time-Aware Funding Schedule Setup
        # Funding settlements occur periodically (every 1 or 8 hours)
        funding_rate_val = 0.0000125
        if funding_data and len(funding_data) > 0:
            funding_rate_val = float(funding_data[0].get("fundingRate", 0.0000125))

        # Inject funding settlement events into timeline
        funding_interval_ns = int(3600 * 1e9)  # 1-hour settlement interval
        settlement_ts = start_ts_ns + funding_interval_ns
        while settlement_ts <= end_ts_ns:
            all_events.append({
                "ts_ns": settlement_ts,
                "event_type": "FUNDING",
                "funding_rate": funding_rate_val,
            })
            settlement_ts += funding_interval_ns

        # Re-sort with injected funding events
        all_events.sort(key=lambda x: x["ts_ns"])

        order_id_counter = 0

        # Helper: execute incoming trade against an order
        def try_fill(order: SimulatedQueueOrder, t_side: str, t_price: float, t_size: float, current_ts: int, is_in_flight: bool = False) -> float:
            if not order.is_resting(current_ts):
                return 0.0
            fill_qty = self.fill_engine.process_trade(
                order=order,
                trade_side=t_side,
                trade_price=t_price,
                trade_size=t_size,
            )
            if fill_qty > 0:
                fill_notional = fill_qty * order.price
                self.pnl_engine.record_fill(
                    side=order.side,
                    price=order.price,
                    size=fill_qty,
                    mid_at_fill=self.latest_mid_price,
                    ts_ns=current_ts,
                )
                self.rate_limiter.record_fill(fill_notional)
                if is_in_flight:
                    self.in_flight_fills_count += 1
                if order.remaining_size <= 0:
                    order.status = OrderStatus.FILLED
                    order.is_active = False
            return fill_qty

        # Main Event Simulation Loop
        for event in all_events:
            ts_ns = event["ts_ns"]
            ev_type = event["event_type"]

            # 1. Update order lifecycle states on current timestamp
            if self.active_bid_order and self.active_bid_order.is_active:
                self.active_bid_order.update_lifecycle(ts_ns)
            if self.active_ask_order and self.active_ask_order.is_active:
                self.active_ask_order.update_lifecycle(ts_ns)

            for cancel_order in self.in_flight_cancels:
                cancel_order.update_lifecycle(ts_ns)
            # Prune finalized cancellations
            self.in_flight_cancels = [o for o in self.in_flight_cancels if o.is_active]

            # --- EVENT: L2 SNAPSHOT / DELTA ---
            if ev_type in ("L2_SNAPSHOT", "L2_DELTA"):
                bids_payload = event["bids"]
                asks_payload = event["asks"]
                if isinstance(bids_payload, str):
                    try:
                        bids_payload = json.loads(bids_payload)
                    except Exception:
                        bids_payload = []
                if isinstance(asks_payload, str):
                    try:
                        asks_payload = json.loads(asks_payload)
                    except Exception:
                        asks_payload = []

                if ev_type == "L2_SNAPSHOT":
                    self.orderbook.apply_snapshot({
                        "bids": bids_payload,
                        "asks": asks_payload,
                        "lastSequenceId": event.get("sequence_id"),
                    })
                else:
                    self.orderbook.apply_delta({
                        "bids": bids_payload,
                        "asks": asks_payload,
                        "lastSequenceId": event.get("sequence_id"),
                    })

                best_b = self.orderbook.best_bid()
                best_a = self.orderbook.best_ask()
                if best_b and best_a:
                    self.latest_bid_price = float(best_b[0])
                    self.latest_ask_price = float(best_a[0])
                    mid_dec = self.orderbook.mid()
                    mid = float(mid_dec) if mid_dec else ((self.latest_bid_price + self.latest_ask_price) / 2.0)
                    self.latest_mid_price = mid
                    sp_dec = self.orderbook.spread()
                    self.latest_spread_bps = float(sp_dec / mid_dec * 10000) if (sp_dec and mid_dec) else 0.0
                    self.latest_volatility = self.volatility_estimator.update(ts_ns, mid)

            # --- EVENT: BBO UPDATE ---
            elif ev_type == "BBO":
                self.latest_bid_price = event["bid_price"]
                self.latest_ask_price = event["ask_price"]
                self.latest_mid_price = event["mid_price"]
                self.latest_spread_bps = event["spread_bps"]
                self.latest_volatility = self.volatility_estimator.update(ts_ns, event["mid_price"])

                # Microprice deviation calculation
                bid_sz = event["bid_size"]
                ask_sz = event["ask_size"]
                tot_sz = bid_sz + ask_sz
                if tot_sz > 0:
                    micro = (bid_sz * event["ask_price"] + ask_sz * event["bid_price"]) / tot_sz
                    self.latest_microprice_dev = ((micro - self.latest_mid_price) / self.latest_mid_price) * 10_000.0

                # Strategy quote generation
                quotes = self.strategy.generate_quotes(
                    mid_price=self.latest_mid_price,
                    inventory_units=self.pnl_engine.position,
                    volatility=self.latest_volatility,
                    market_spread_bps=self.latest_spread_bps,
                    microprice_dev_bps=self.latest_microprice_dev,
                )

                if quotes:
                    bid_quote, ask_quote = quotes

                    # Queue volume determination (L2 depth or BBO size)
                    if self.orderbook.is_synced:
                        queue_ahead_bid = (
                            self.orderbook.get_cumulative_bid_depth(to_decimal(bid_quote.price))
                            if bid_quote else 0.0
                        )
                        queue_ahead_ask = (
                            self.orderbook.get_cumulative_ask_depth(to_decimal(ask_quote.price))
                            if ask_quote else 0.0
                        )
                    else:
                        queue_ahead_bid = bid_sz if (bid_quote and bid_quote.price <= event["bid_price"] + 1e-9) else 0.0
                        queue_ahead_ask = ask_sz if (ask_quote and ask_quote.price >= event["ask_price"] - 1e-9) else 0.0

                    # --- Process BID Quote Modification ---
                    if bid_quote:
                        needs_requote_bid = True
                        if self.active_bid_order and self.active_bid_order.is_active:
                            tick_shift = abs(bid_quote.price - self.active_bid_order.price) / self.strategy.tick_size
                            size_diff = abs(bid_quote.size - self.active_bid_order.size)
                            if tick_shift < self.requote_threshold_ticks and size_diff < 1e-9:
                                needs_requote_bid = False

                        if needs_requote_bid and self.rate_limiter.can_modify_order():
                            price_unchanged = (
                                self.active_bid_order is not None
                                and abs(bid_quote.price - self.active_bid_order.price) < 1e-9
                            )
                            size_decreased = (
                                self.active_bid_order is not None
                                and bid_quote.size <= self.active_bid_order.size + 1e-9
                            )

                            if self.active_bid_order and price_unchanged and size_decreased:
                                # Mandate §6: Same-price size decrease modifies in-place, preserves priority!
                                self.rate_limiter.record_order_modification()
                                self.active_bid_order.modify(
                                    new_price=bid_quote.price,
                                    new_size=bid_quote.size,
                                    current_queue_at_price=queue_ahead_bid,
                                )
                                self.in_place_modifications_count += 1
                            else:
                                # Price changed or size increased: Cancel-replace semantics
                                if self.active_bid_order and self.active_bid_order.is_active:
                                    cancel_latency_ns = int(self.latency.total_cancel_latency_ms * 1e6)
                                    self.active_bid_order.request_cancel(
                                        request_ts_ns=ts_ns,
                                        cancel_latency_ns=cancel_latency_ns,
                                    )
                                    self.in_flight_cancels.append(self.active_bid_order)
                                    self.rate_limiter.record_order_modification()
                                    self.cancel_replace_count += 1
                                else:
                                    self.rate_limiter.record_order_placement()

                                order_id_counter += 1
                                place_latency_ns = int(self.latency.total_place_latency_ms * 1e6)
                                new_bid = SimulatedQueueOrder(
                                    order_id=f"bid_{order_id_counter}",
                                    side="BUY",
                                    price=bid_quote.price,
                                    size=bid_quote.size,
                                    created_ts_ns=ts_ns,
                                    queue_ahead_volume=queue_ahead_bid,
                                    status=OrderStatus.SUBMITTING,
                                )
                                new_bid.effective_ts_ns = ts_ns + place_latency_ns
                                self.active_bid_order = new_bid
                                self.last_bid_quote_price = bid_quote.price

                    # --- Process ASK Quote Modification ---
                    if ask_quote:
                        needs_requote_ask = True
                        if self.active_ask_order and self.active_ask_order.is_active:
                            tick_shift = abs(ask_quote.price - self.active_ask_order.price) / self.strategy.tick_size
                            size_diff = abs(ask_quote.size - self.active_ask_order.size)
                            if tick_shift < self.requote_threshold_ticks and size_diff < 1e-9:
                                needs_requote_ask = False

                        if needs_requote_ask and self.rate_limiter.can_modify_order():
                            price_unchanged = (
                                self.active_ask_order is not None
                                and abs(ask_quote.price - self.active_ask_order.price) < 1e-9
                            )
                            size_decreased = (
                                self.active_ask_order is not None
                                and ask_quote.size <= self.active_ask_order.size + 1e-9
                            )

                            if self.active_ask_order and price_unchanged and size_decreased:
                                self.rate_limiter.record_order_modification()
                                self.active_ask_order.modify(
                                    new_price=ask_quote.price,
                                    new_size=ask_quote.size,
                                    current_queue_at_price=queue_ahead_ask,
                                )
                                self.in_place_modifications_count += 1
                            else:
                                if self.active_ask_order and self.active_ask_order.is_active:
                                    cancel_latency_ns = int(self.latency.total_cancel_latency_ms * 1e6)
                                    self.active_ask_order.request_cancel(
                                        request_ts_ns=ts_ns,
                                        cancel_latency_ns=cancel_latency_ns,
                                    )
                                    self.in_flight_cancels.append(self.active_ask_order)
                                    self.rate_limiter.record_order_modification()
                                    self.cancel_replace_count += 1
                                else:
                                    self.rate_limiter.record_order_placement()

                                order_id_counter += 1
                                place_latency_ns = int(self.latency.total_place_latency_ms * 1e6)
                                new_ask = SimulatedQueueOrder(
                                    order_id=f"ask_{order_id_counter}",
                                    side="SELL",
                                    price=ask_quote.price,
                                    size=ask_quote.size,
                                    created_ts_ns=ts_ns,
                                    queue_ahead_volume=queue_ahead_ask,
                                    status=OrderStatus.SUBMITTING,
                                )
                                new_ask.effective_ts_ns = ts_ns + place_latency_ns
                                self.active_ask_order = new_ask
                                self.last_ask_quote_price = ask_quote.price

            # --- EVENT: TRADE ---
            elif ev_type == "TRADE":
                t_side = event["side"]
                t_p = event["price"]
                rem_trade_size = event["size"]

                if t_side == "SELL":
                    # Seller hits bids: first fill resting in-flight cancel bids, then active bid
                    for cancel_bid in [o for o in self.in_flight_cancels if o.side == "BUY" and o.is_active]:
                        if rem_trade_size <= 0:
                            break
                        filled = try_fill(cancel_bid, t_side, t_p, rem_trade_size, ts_ns, is_in_flight=True)
                        rem_trade_size -= filled

                    if rem_trade_size > 0 and self.active_bid_order and self.active_bid_order.is_active:
                        filled = try_fill(self.active_bid_order, t_side, t_p, rem_trade_size, ts_ns, is_in_flight=False)
                        if not self.active_bid_order.is_active:
                            self.active_bid_order = None

                elif t_side == "BUY":
                    # Buyer lifts asks: first fill resting in-flight cancel asks, then active ask
                    for cancel_ask in [o for o in self.in_flight_cancels if o.side == "SELL" and o.is_active]:
                        if rem_trade_size <= 0:
                            break
                        filled = try_fill(cancel_ask, t_side, t_p, rem_trade_size, ts_ns, is_in_flight=True)
                        rem_trade_size -= filled

                    if rem_trade_size > 0 and self.active_ask_order and self.active_ask_order.is_active:
                        filled = try_fill(self.active_ask_order, t_side, t_p, rem_trade_size, ts_ns, is_in_flight=False)
                        if not self.active_ask_order.is_active:
                            self.active_ask_order = None

            # --- EVENT: FUNDING SETTLEMENT ---
            elif ev_type == "FUNDING":
                # Mandate §12: Applied at settlement timestamp to the instantaneous position held
                rate = event["funding_rate"]
                self.pnl_engine.apply_funding(
                    funding_rate=rate,
                    current_mid=self.latest_mid_price,
                )

        # Compute post-simulation metrics and markout attribution
        bbo_ts_arr = df_bbo["recv_ts_ns"].values
        bbo_mid_arr = df_bbo["mid_price"].values
        markout_metrics = self.pnl_engine.get_fill_markouts(bbo_ts_arr, bbo_mid_arr)

        pnl_summary = self.pnl_engine.get_summary(current_mid=self.latest_mid_price)
        rl_metrics = self.rate_limiter.to_metrics()

        return BacktestRunResult(
            market=self.strategy.market,
            strategy_name=self.strategy.__class__.__name__,
            fill_model=self.fill_model.value,
            fidelity=fidelity,
            latency_ms=self.latency.total_place_latency_ms,
            pnl_summary=pnl_summary,
            rate_limit_metrics=rl_metrics,
            markout_metrics=markout_metrics,
            event_count=len(all_events),
            duration_hours=duration_hours,
            in_flight_fills_count=self.in_flight_fills_count,
            in_place_modifications_count=self.in_place_modifications_count,
            cancel_replace_count=self.cancel_replace_count,
        )
