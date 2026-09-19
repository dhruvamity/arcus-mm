"""Live Mainnet Paper Trading Engine for Arcus Perpetuals Rebuilt on Unified SimEngine.

Fulfills Mandate v2 Section 5 & 9 (Closing Defect R-08):
- Single-path execution: Feeds live public mainnet WebSocket frames into canonical SimEngine.on_event().
- ZERO real orders placed (read-only mainnet data stream).
- Single shared WebSocket connection across all subscribed markets (eliminating duplicate sockets).
- Dynamic metadata loading: Queries GET /v1/markets at initialization for live tick/step/minOrder sizes.
- Real state-machine kill switches checked on every clock tick (<= 250ms):
  - Stale feed > 3s triggers PAUSED_STALE_FEED and order cancellation.
  - Crossed book triggers FLATTENED_CROSSED_BOOK.
  - Drawdown limit triggers emergency flattening.
- Asset-class gating: OPEN_30 / CLOSE_30 pauses apply strictly to equities/commodities/indices (crypto pause default off).
- Concurrent paired evaluation: Evaluates Model B (central estimate) and Model C (robustness floor) independently.
- Rule 11 Session Outcomes: Judged only with >= 30 fills, labeled SESSION: POSITIVE / NEGATIVE / INSUFFICIENT.
- Replay parity logging: Persists raw JSONL messages and computes SHA-256 session manifest.
"""

import asyncio
import datetime
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Dict, List, Optional, Any, Union

from src.config import ArcusConfig, settings
from src.ws_client import ArcusWsClient
from src.rest_client import ArcusRestClient
from src.sim.engine import (
    SimEngine,
    SimEvent,
    SimEventType,
    RiskState,
)
from src.models.fill import FillModelType
from src.models.latency import LatencyConfig
from src.strategies.adaptive_mm import AdaptiveMicrostructureStrategy
from src.strategies.fixed_spread import FixedSpreadStrategy
from src.strategies.volatility_clock import VolatilityClockStrategy
from src.strategies.avellaneda_stoikov import AvellanedaStoikovStrategy
from src.strategies.baselines import DoNothingStrategy, RandomSideQuotingStrategy
from src.calendar import classify_regime
from src.utils import now_ns

logger = logging.getLogger("paper_trader")


DEFAULT_MARKET_SPECS: Dict[str, Dict[str, Any]] = {
    "BTC-USD": {"tick_size": 0.1, "step_size": 0.00000001, "min_notional": 5.0, "min_order_size": 0.0001},
    "ETH-USD": {"tick_size": 0.01, "step_size": 0.000001, "min_notional": 5.0, "min_order_size": 0.001},
    "SOL-USD": {"tick_size": 0.01, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.01},
    "HYPE-USD": {"tick_size": 0.001, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.01},
    "ZEC-USD": {"tick_size": 0.001, "step_size": 0.00001, "min_notional": 5.0, "min_order_size": 0.001},
    "NEAR-USD": {"tick_size": 0.001, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.01},
    "UNI-USD": {"tick_size": 0.001, "step_size": 0.001, "min_notional": 5.0, "min_order_size": 0.1},
    "LIT-USD": {"tick_size": 0.0001, "step_size": 0.001, "min_notional": 5.0, "min_order_size": 0.1},
    "SPCX-USD": {"tick_size": 0.01, "step_size": 0.001, "min_notional": 5.0, "min_order_size": 0.01},
    "SLV-USD": {"tick_size": 0.01, "step_size": 0.001, "min_notional": 5.0, "min_order_size": 0.01},
}


class ArcusLivePaperTrader:
    """Streams live mainnet market data into a canonical SimEngine instance for paper trading."""

    def __init__(
        self,
        markets: Union[str, List[str]],
        session_id: Optional[str] = None,
        output_dir: str = "data/live_paper",
        initial_capital: float = 100.0,
        capital_scenarios: Optional[List[float]] = None,
        strategy_types: Optional[List[str]] = None,
        enable_crypto_pause: bool = False,
        enable_equity_pause: bool = True,
        latency_config: Optional[LatencyConfig] = None,
        config: Optional[ArcusConfig] = None,
    ):
        self.markets = [markets] if isinstance(markets, str) else list(markets)
        self.initial_capital = initial_capital
        self.capital_scenarios = capital_scenarios or [initial_capital]
        self.strategy_types = strategy_types or ["adaptive", "fixed_spread", "vol_clock", "donothing", "random_side"]
        self.enable_crypto_pause = enable_crypto_pause
        self.enable_equity_pause = enable_equity_pause
        self.latency_config = latency_config or LatencyConfig()
        self.config = config or settings

        self.session_id = session_id or f"paper_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.session_dir = Path(output_dir) / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.ws_client = ArcusWsClient(config=self.config)
        self.rest_client = ArcusRestClient(config=self.config)

        self.market_specs: Dict[str, Dict[str, Any]] = {}
        self.engine: Optional[SimEngine] = None
        self._running = False

        # Raw logging & Telemetry
        self.raw_stream_path = self.session_dir / "raw_stream.jsonl"
        self.telemetry_path = self.session_dir / "telemetry.jsonl"
        self.fills_path = self.session_dir / "fills.jsonl"
        self._raw_file = None
        self._telemetry_file = None
        self._fills_file = None

        self._clock_task: Optional[asyncio.Task] = None
        self._telemetry_task: Optional[asyncio.Task] = None
        self.session_start_utc: Optional[str] = None
        self.session_fills_count = 0

    async def initialize_engine(self) -> None:
        """Dynamically loads live venue specs from REST /v1/markets and initializes SimEngine."""
        logger.info("Querying live market metadata from GET /v1/markets...")
        try:
            markets_res = await self.rest_client._request("GET", "/v1/markets", "markets")
            items = markets_res.get("markets") or markets_res if isinstance(markets_res, list) else []
            for item in items:
                m_name = item.get("market") or item.get("name")
                if m_name in self.markets:
                    self.market_specs[m_name] = {
                        "tick_size": float(item.get("tickSize", 0.001)),
                        "step_size": float(item.get("stepSize", 0.0001)),
                        "min_notional": float(item.get("minOrderNotional", 5.0)),
                        "min_order_size": float(item.get("minOrderSize", 0.0)),
                        "max_order_size": float(item.get("maxOrderSize", 1_000_000.0)),
                    }
                    logger.info(f"Loaded live metadata for {m_name}: {self.market_specs[m_name]}")
        except Exception as e:
            logger.warning(f"Could not load live /v1/markets ({e}). Falling back to conservative venue metadata.")

        # Ensure all markets have specs
        for m in self.markets:
            if m not in self.market_specs:
                self.market_specs[m] = DEFAULT_MARKET_SPECS.get(
                    m, {"tick_size": 0.01, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.001}
                )

        # Build strategy instances per market and capital scenario
        strategies: Dict[str, Any] = {}
        for m in self.markets:
            spec = self.market_specs[m]
            tick_sz = spec["tick_size"]
            step_sz = spec["step_size"]
            min_notional = spec["min_notional"]

            for cap in self.capital_scenarios:
                cap_tag = f"c{int(cap)}"
                clip = max(min_notional, 8.0)

                if "adaptive" in self.strategy_types:
                    sid = f"{m}_adaptive_{cap_tag}"
                    strategies[sid] = AdaptiveMicrostructureStrategy(
                        market=m, tick_size=tick_sz, step_size=step_sz, clip_notional=clip, base_spread_bps=4.0
                    )

                if "fixed_spread" in self.strategy_types:
                    sid = f"{m}_fixed_{cap_tag}"
                    strategies[sid] = FixedSpreadStrategy(
                        market=m, tick_size=tick_sz, step_size=step_sz, clip_notional=clip, spread_bps=4.5
                    )

                if "vol_clock" in self.strategy_types:
                    sid = f"{m}_volclock_{cap_tag}"
                    strategies[sid] = VolatilityClockStrategy(
                        market=m, tick_size=tick_sz, step_size=step_sz, clip_notional=clip
                    )

                if "donothing" in self.strategy_types:
                    sid = f"{m}_donothing_{cap_tag}"
                    strategies[sid] = DoNothingStrategy(market=m, tick_size=tick_sz, step_size=step_sz)

                if "random_side" in self.strategy_types:
                    sid = f"{m}_randomside_{cap_tag}"
                    strategies[sid] = RandomSideQuotingStrategy(
                        market=m, tick_size=tick_sz, step_size=step_sz, clip_notional=clip
                    )

        fill_models = [
            FillModelType.MODEL_B_MODERATE,
            FillModelType.MODEL_C_CONSERVATIVE,
            FillModelType.MODEL_A_TOUCH,
        ]

        self.engine = SimEngine(
            markets=self.markets,
            market_specs=self.market_specs,
            strategies=strategies,
            fill_models=fill_models,
            latency_config=self.latency_config,
            initial_capital=self.initial_capital,
        )
        logger.info(f"SimEngine initialized with {len(self.markets)} markets and {len(strategies)} strategy instances.")

    def _persist_raw_ws(self, channel: str, market: str, msg: Dict[str, Any], recv_ts: int) -> None:
        """Persists raw incoming WebSocket message for exact replay parity verification."""
        if self._raw_file:
            row = {
                "recv_ts_ns": recv_ts,
                "channel": channel,
                "market": market,
                "data": msg,
            }
            self._raw_file.write(json.dumps(row, separators=(",", ":")) + "\n")

    async def _on_bbo_update(self, msg: Dict[str, Any]) -> None:
        """Handles incoming BBO WebSocket frame."""
        t_recv = now_ns()
        market = msg.get("market") or self.markets[0]
        self._persist_raw_ws("bbo", market, msg, t_recv)

        contents = msg.get("contents", {})
        if not isinstance(contents, dict) or not contents:
            return

        # Check regime-specific pause
        is_equity = any(eq in market for eq in ["SPCX", "NVDA", "TSLA", "GOOGL", "AMD", "SLV", "GLD", "SPY", "QQQ"])
        regime = classify_regime(t_recv, "equities" if is_equity else "crypto")

        if is_equity and self.enable_equity_pause and regime.event_window in ("OPEN_30", "CLOSE_30"):
            # Equities pause during volatile open/close
            return
        if not is_equity and self.enable_crypto_pause and regime.event_window in ("OPEN_30", "CLOSE_30"):
            return

        event = SimEvent(SimEventType.BBO, t_recv, market, contents)
        self.engine.on_event(event)

    async def _on_trades_update(self, msg: Dict[str, Any]) -> None:
        """Handles incoming Trades WebSocket frame."""
        t_recv = now_ns()
        market = msg.get("market") or self.markets[0]
        self._persist_raw_ws("trades", market, msg, t_recv)

        contents = msg.get("contents")
        if not isinstance(contents, list) or not contents:
            return

        for trade_data in contents:
            event = SimEvent(SimEventType.TRADE, t_recv, market, trade_data)
            fills = self.engine.on_event(event)
            if fills:
                self._record_fills(fills)

    def _record_fills(self, fills: List[Dict[str, Any]]) -> None:
        """Logs simulated fills to disk."""
        self.session_fills_count += len(fills)
        if self._fills_file:
            for f in fills:
                self._fills_file.write(json.dumps(f, separators=(",", ":")) + "\n")
            self._fills_file.flush()

    async def _clock_loop(self) -> None:
        """Ticks engine clock every 100ms to enforce watchdogs, latency arrivals, and rate limits."""
        while self._running:
            try:
                t_now = now_ns()
                for m in self.markets:
                    event = SimEvent(SimEventType.CLOCK_TICK, t_now, m, {})
                    self.engine.on_event(event)
                await asyncio.sleep(0.10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in paper trader clock loop: {e}")
                await asyncio.sleep(0.10)

    async def _telemetry_loop(self) -> None:
        """Emits telemetry every 60 seconds formatted with Rule 11 outcome labels."""
        while self._running:
            try:
                await asyncio.sleep(60.0)
                if not self._running:
                    break

                ts_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                for m in self.markets:
                    venue = self.engine.venues.get(m)
                    if not venue:
                        continue

                    stale_ms = (now_ns() - venue.last_bbo_ts_ns) / 1e6 if venue.last_bbo_ts_ns > 0 else 999999.0
                    spread_bps = ((venue.best_ask - venue.best_bid) / venue.current_mid * 10_000.0) if venue.current_mid > 0 else 0.0

                    for sid, ctx in self.engine.contexts.items():
                        if hasattr(ctx.strategy, "market") and ctx.strategy.market != m:
                            continue

                        sum_b = ctx.pnl_engines[FillModelType.MODEL_B_MODERATE].get_summary(venue.current_mid)
                        sum_c = ctx.pnl_engines[FillModelType.MODEL_C_CONSERVATIVE].get_summary(venue.current_mid)
                        pool = ctx.rate_limiter.get_pool_status()

                        # Rule 11 Outcome Labeling
                        fills_c = sum_c["total_trades_count"]
                        if fills_c < 30:
                            session_label = "SESSION: INSUFFICIENT"
                        elif sum_c["net_pnl"] > 0:
                            session_label = "SESSION: POSITIVE"
                        else:
                            session_label = "SESSION: NEGATIVE"

                        telemetry_record = {
                            "timestamp_utc": ts_utc,
                            "market": m,
                            "strategy_id": sid,
                            "mid": round(venue.current_mid, 4),
                            "spread_bps": round(spread_bps, 2),
                            "volatility": round(venue.current_volatility, 4),
                            "stale_ms": round(stale_ms, 1),
                            "risk_state": ctx.risk_state.value,
                            "model_b": {
                                "equity": round(sum_b["current_equity"], 4),
                                "net_pnl": round(sum_b["net_pnl"], 4),
                                "fills": sum_b["total_trades_count"],
                                "position": round(sum_b["open_position_units"], 6),
                            },
                            "model_c": {
                                "equity": round(sum_c["current_equity"], 4),
                                "net_pnl": round(sum_c["net_pnl"], 4),
                                "fills": fills_c,
                                "position": round(sum_c["open_position_units"], 6),
                            },
                            "rate_limit_pools": {
                                "order_units_avail": round(pool["order_units_available"], 1),
                                "cancel_units_avail": round(pool["cancel_units_available"], 1),
                                "actions_used": pool["total_actions_used"],
                            },
                            "outcome_label": session_label,
                        }

                        if self._telemetry_file:
                            self._telemetry_file.write(json.dumps(telemetry_record, separators=(",", ":")) + "\n")

                if self._telemetry_file:
                    self._telemetry_file.flush()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in paper trader telemetry loop: {e}")

    async def start(self) -> None:
        """Starts the live paper trader."""
        self._running = True
        self.session_start_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        logger.info(f"Starting ArcusLivePaperTrader session {self.session_id} on markets {self.markets}...")

        self._raw_file = open(self.raw_stream_path, "a", encoding="utf-8")
        self._telemetry_file = open(self.telemetry_path, "a", encoding="utf-8")
        self._fills_file = open(self.fills_path, "a", encoding="utf-8")

        await self.initialize_engine()
        await self.ws_client.connect()

        # Subscribe across all designated markets on the shared connection
        for m in self.markets:
            await self.ws_client.subscribe("bbo", m, self._on_bbo_update)
            await self.ws_client.subscribe("trades", m, self._on_trades_update)

        self._clock_task = asyncio.create_task(self._clock_loop())
        self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        logger.info(f"Live paper trader fully operational. Persisting to {self.session_dir}")

    async def stop(self) -> None:
        """Stops live paper trader, cancels tasks, and generates SHA-256 session manifest."""
        self._running = False
        logger.info(f"Stopping live paper trader session {self.session_id}...")

        if self._clock_task:
            self._clock_task.cancel()
        if self._telemetry_task:
            self._telemetry_task.cancel()

        await self.ws_client.disconnect()
        await self.rest_client.close()

        if self._raw_file:
            self._raw_file.close()
        if self._telemetry_file:
            self._telemetry_file.close()
        if self._fills_file:
            self._fills_file.close()

        # Generate SHA-256 Session Manifest for Replay Parity
        manifest_path = self.session_dir / "MANIFEST.sha256"
        manifest_lines = []
        for p in sorted(self.session_dir.glob("*.*")):
            if p.name == "MANIFEST.sha256":
                continue
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            manifest_lines.append(f"{h}  {p.name}")
        manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        logger.info(f"Session {self.session_id} finalized with SHA-256 manifest: {manifest_path}")

    def get_session_summary(self) -> Dict[str, Any]:
        """Returns consolidated session summary across all evaluated strategies."""
        summary = {
            "session_id": self.session_id,
            "session_start_utc": self.session_start_utc,
            "session_end_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "markets": self.markets,
            "total_fills_logged": self.session_fills_count,
            "engine_fill_hash": self.engine.get_fill_log_hash() if self.engine else None,
            "strategies": {},
        }
        if self.engine:
            for sid, ctx in self.engine.contexts.items():
                m = ctx.strategy.market
                venue = self.engine.venues.get(m)
                mid = venue.current_mid if venue else 0.0
                sum_b = ctx.pnl_engines[FillModelType.MODEL_B_MODERATE].get_summary(mid)
                sum_c = ctx.pnl_engines[FillModelType.MODEL_C_CONSERVATIVE].get_summary(mid)
                fills_c = sum_c["total_trades_count"]
                if fills_c < 30:
                    outcome = "SESSION: INSUFFICIENT"
                elif sum_c["net_pnl"] > 0:
                    outcome = "SESSION: POSITIVE"
                else:
                    outcome = "SESSION: NEGATIVE"

                summary["strategies"][sid] = {
                    "market": m,
                    "model_b": sum_b,
                    "model_c": sum_c,
                    "risk_state": ctx.risk_state.value,
                    "outcome": outcome,
                }
        return summary
