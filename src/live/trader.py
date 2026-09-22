"""Live quoting on Arcus, using the same decision rule as the backtests (src/quoting.py).

One post-only (ALO) bid and ask per market, resting `depth_bps` from the mid, moved with a
single modify when their target drifts by `requote_bps`. Nothing here decides anything the
replay does not: this module only turns those decisions into venue calls and keeps our view of
orders and position honest.

Safety, all enforced here and independent of the venue:
  * dry run by default: intents are logged, no mutating request is sent
  * inventory cap per market; the closing quote keeps working when opening is halted
  * daily loss stop per market (UTC day), closing quote stays live
  * stale feed: no BBO for stale_s -> pull that market's quotes
  * dead man's switch refreshed every dms_refresh_s so the venue cancels everything if we die
  * a STOP file in the log directory -> cancel everything and exit
  * periodic reconcile against the venue's own positions and open orders; on mismatch the
    venue wins and unknown orders are cancelled
Mainnet orders additionally need the two-key guard in src/rest_client.py.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

from src.models.core import MarketMetadata, OrderRequest, OrderSide, TimeInForce
from src.quoting import QuoteRules, needs_requote, plan

log = logging.getLogger("live")
NS = 1_000_000_000


@dataclass
class MarketState:
    market: str
    meta: MarketMetadata
    rules: QuoteRules
    daily_stop_usd: float = 0.0
    bb: float = float("nan")
    ba: float = float("nan")
    last_bbo_ns: int = 0
    pos: float = 0.0                       # base units, signed
    avg_px: float = 0.0
    realized: float = 0.0                  # cash from fills today, net of fees
    day: str = ""
    day_start_equity: float = 0.0
    stopped: bool = False
    working: Dict[int, Optional[dict]] = field(default_factory=lambda: {1: None, -1: None})
    inflight: Dict[int, bool] = field(default_factory=lambda: {1: False, -1: False})

    @property
    def mid(self) -> float:
        return (self.bb + self.ba) / 2

    def equity(self) -> float:
        return self.realized + self.pos * self.mid if self.mid == self.mid else self.realized


class LiveTrader:
    def __init__(self, cfg: dict, rest, ws, log_dir: Path, dry_run: bool = True):
        self.cfg = cfg
        self.rest = rest
        self.ws = ws
        self.dry_run = dry_run
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.states: Dict[str, MarketState] = {}
        self.running = False
        self.actions = 0
        self.last_msg_ns = time.time_ns()   # any frame on the socket; a quiet market is not a dead feed
        self._events = open(self.log_dir / "events.jsonl", "a", buffering=1)

    # ---------------------------------------------------------------- logging
    def event(self, kind: str, **fields):
        rec = {"ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds"),
               "kind": kind, "dry_run": self.dry_run, **fields}
        self._events.write(json.dumps(rec, default=str) + "\n")
        log.info("%s %s", kind, " ".join(f"{k}={v}" for k, v in fields.items()))

    # ------------------------------------------------------------------ setup
    async def start(self):
        metas = {m.marketDisplayName: m for m in await self.rest.get_markets()}
        for m in self.cfg["markets"]:
            meta = metas[m["market"]]
            rules = QuoteRules(
                depth_bps=float(m["depth_bps"]), requote_bps=float(self.cfg["requote_bps"]),
                clip_usd=float(m.get("clip_usd", self.cfg["clip_usd"])),
                max_pos_usd=float(m.get("max_pos_usd", self.cfg["max_pos_usd"])),
                min_notional=max(float(meta.minOrderNotional or 5.0),
                                 float(meta.minOrderSize or 0) * float(meta.oraclePrice or 0)),
                tick=float(meta.tickSize), step=float(meta.stepSize),
                exit_mode=self.cfg.get("exit_mode", "mid"),
                trend_guard_bps=float(self.cfg.get("trend_guard_bps", 0.0)))
            self.states[m["market"]] = MarketState(market=m["market"], meta=meta, rules=rules,
                                                   daily_stop_usd=float(m.get("daily_stop_usd", self.cfg.get("daily_stop_usd", 0.0))))
        await self.reconcile(initial=True)
        for mk in self.states:
            await self.ws.subscribe("bbo", mk, self.on_bbo)
        addr = self.rest.config.wallet_address
        await self.ws.subscribe("userFills", addr, self.on_fill, {"accountIndex": self.rest.config.account_index})
        self.event("started", markets=list(self.states), dry_run=self.dry_run,
                   env=self.rest.config.environment, clip=self.cfg["clip_usd"])

    # --------------------------------------------------------------- feed in
    async def on_bbo(self, msg: Dict[str, Any]):
        mk = msg.get("id") or msg.get("market")
        st = self.states.get(mk)
        c = msg.get("contents") or {}
        if not st or "bestBid" not in c or "bestAsk" not in c:
            return
        st.bb, st.ba = float(c["bestBid"]["price"]), float(c["bestAsk"]["price"])
        st.last_bbo_ns = self.last_msg_ns = time.time_ns()
        await self.quote(st)

    async def on_fill(self, msg: Dict[str, Any]):
        self.last_msg_ns = time.time_ns()
        c = msg.get("contents")
        rows = c.get("fills", []) if isinstance(c, dict) else (c if isinstance(c, list) else [])
        for f in rows:
            if not isinstance(f, dict):
                continue
            mk = f.get("marketDisplayName") or f.get("market")
            st = self.states.get(mk)
            if not st or f.get("size") is None:
                continue
            side = 1 if str(f.get("side", "")).upper() == "BUY" else -1
            q, px = float(f["size"]), float(f["price"])
            fee = float(f.get("fee", 0) or 0)
            new_pos = st.pos + side * q
            if st.pos == 0 or (st.pos > 0) == (side > 0):
                st.avg_px = (abs(st.pos) * st.avg_px + q * px) / max(abs(new_pos), 1e-12)
            elif abs(new_pos) > 1e-12 and (new_pos > 0) != (st.pos > 0):
                st.avg_px = px
            st.pos = new_pos if abs(new_pos) > 1e-12 else 0.0
            st.realized -= side * q * px + fee
            self.event("fill", market=mk, side="BUY" if side > 0 else "SELL", price=px, qty=q, fee=fee,
                       position=round(st.pos, 10), day_pnl=round(st.equity() - st.day_start_equity, 4))

    # -------------------------------------------------------------- decisions
    async def quote(self, st: MarketState):
        if not self.running or st.mid != st.mid:
            return
        today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        if st.day != today:                      # new UTC day: reset the loss stop
            st.day, st.day_start_equity, st.stopped = today, st.equity(), False
        if st.daily_stop_usd > 0 and st.equity() - st.day_start_equity <= -st.daily_stop_usd and not st.stopped:
            st.stopped = True
            self.event("daily_stop", market=st.market, day_pnl=round(st.equity() - st.day_start_equity, 4))
        fresh = self.feed_ok()
        targets = plan(st.rules, bb=st.bb, ba=st.ba, ref=st.mid, pos=st.pos,
                       allow_open=not st.stopped and fresh, allow_close=fresh)
        for side in (1, -1):
            if st.inflight[side]:
                continue
            tgt, cur = targets[side], st.working[side]
            if tgt is None:
                if cur:
                    await self.cancel(st, side)
            elif cur is None:
                await self.place(st, side, tgt)
            elif needs_requote(cur["price"], tgt, st.mid, st.rules.requote_bps):
                await self.modify(st, side, tgt)

    def feed_ok(self) -> bool:
        """Our data path is alive: socket connected and something arrived recently.

        A market that simply has no updates (GLD can be quiet for minutes overnight) is not a
        stale feed — Arcus only sends BBO frames when the book changes.
        """
        if hasattr(self.ws, "is_connected") and not self.ws.is_connected:
            return False
        return (time.time_ns() - self.last_msg_ns) < float(self.cfg.get("stale_s", 300)) * NS

    # ------------------------------------------------------------ venue calls
    async def place(self, st: MarketState, side: int, tgt):
        cid = uuid.uuid4().hex[:16]
        self.actions += 1
        self.event("place", market=st.market, side="BUY" if side > 0 else "SELL",
                   price=tgt.price, qty=tgt.qty, client_id=cid)
        if self.dry_run:
            st.working[side] = {"order_id": f"dry-{cid}", "client_id": cid, "price": tgt.price, "qty": tgt.qty}
            return
        st.inflight[side] = True
        try:
            res = await self.rest.place_order(
                OrderRequest(marketId=st.meta.marketId, side=OrderSide.BUY if side > 0 else OrderSide.SELL,
                             price=Decimal(str(tgt.price)), quantity=Decimal(str(tgt.qty)),
                             timeInForce=TimeInForce.ALO, clientId=cid), st.meta)
            if str(res.status).upper() in ("REJECTED", "ERROR"):
                self.event("rejected", market=st.market, side=side, reason=str(res.raw)[:200])
                st.working[side] = None
            else:
                st.working[side] = {"order_id": res.orderId, "client_id": cid, "price": tgt.price, "qty": tgt.qty}
        except Exception as e:
            self.event("place_error", market=st.market, error=str(e)[:300])
            st.working[side] = None
        finally:
            st.inflight[side] = False

    async def modify(self, st: MarketState, side: int, tgt):
        """Re-price with one modify (1 order unit); falls back to cancel+place if unsupported."""
        cur = st.working[side]
        self.actions += 1
        self.event("modify", market=st.market, side="BUY" if side > 0 else "SELL",
                   old_price=cur["price"], price=tgt.price, qty=tgt.qty, order_id=cur["order_id"])
        if self.dry_run:
            st.working[side] = {**cur, "price": tgt.price, "qty": tgt.qty}
            return
        st.inflight[side] = True
        try:
            res = await self.rest.modify_order(market_id=st.meta.marketId, order_id=cur["order_id"],
                                               price=Decimal(str(tgt.price)), quantity=Decimal(str(tgt.qty)),
                                               side=OrderSide.BUY if side > 0 else OrderSide.SELL, market=st.meta)
            if str(res.status).upper() in ("REJECTED", "ERROR", "NOT_FOUND"):
                st.working[side] = None
                self.event("modify_rejected", market=st.market, side=side, reason=str(res.raw)[:200])
            else:
                st.working[side] = {**cur, "order_id": res.orderId or cur["order_id"], "price": tgt.price, "qty": tgt.qty}
        except Exception as e:
            self.event("modify_error", market=st.market, error=str(e)[:300])
            st.working[side] = None
        finally:
            st.inflight[side] = False

    async def cancel(self, st: MarketState, side: int):
        cur = st.working[side]
        if not cur:
            return
        self.actions += 1
        self.event("cancel", market=st.market, side="BUY" if side > 0 else "SELL", order_id=cur["order_id"])
        st.working[side] = None
        if self.dry_run:
            return
        try:
            await self.rest.cancel_order(market_id=st.meta.marketId, order_id=cur["order_id"])
        except Exception as e:
            self.event("cancel_error", market=st.market, error=str(e)[:300])

    # -------------------------------------------------------------- guardians
    async def reconcile(self, initial: bool = False):
        """The venue is the source of truth for position and open orders."""
        try:
            positions = await self.rest.get_positions()
        except Exception as e:
            self.event("reconcile_error", error=str(e)[:300])
            return
        seen = {}
        for p in positions:
            mk = p.get("marketDisplayName") or p.get("market")
            if mk in self.states:
                sign = 1.0 if str(p.get("positionSide", "LONG")).upper() in ("LONG", "BUY") else -1.0
                seen[mk] = sign * abs(float(p.get("size") or p.get("quantity") or 0))
        for mk, st in self.states.items():
            venue_pos = seen.get(mk, 0.0)
            if abs(venue_pos - st.pos) > float(st.meta.stepSize):
                self.event("position_mismatch", market=mk, ours=st.pos, venue=venue_pos, action="adopt venue")
                st.pos = venue_pos
            try:
                open_orders = await self.rest.get_open_orders(market_id=st.meta.marketId)
            except Exception:
                continue
            ours = {o["order_id"] for o in st.working.values() if o}
            stray = [o for o in open_orders if str(o.get("orderId")) not in ours]
            if stray and not self.dry_run:
                self.event("stray_orders", market=mk, count=len(stray), action="cancel")
                for o in stray:
                    try:
                        await self.rest.cancel_order(market_id=st.meta.marketId, order_id=str(o.get("orderId")))
                    except Exception:
                        pass

    async def dead_mans_switch(self):
        """Arcus cancels everything for this subaccount if we stop refreshing this deadline."""
        window = float(self.cfg.get("dms_window_s", 60))
        while self.running:
            if not self.dry_run:
                try:
                    await self.rest.schedule_cancel(int((time.time() + window) * 1e6))
                except Exception as e:
                    self.event("dms_error", error=str(e)[:200])
            await asyncio.sleep(float(self.cfg.get("dms_refresh_s", 20)))

    async def watchdog(self):
        while self.running:
            if not self.feed_ok():
                for st in self.states.values():
                    if st.working[1] or st.working[-1]:
                        self.event("feed_down", market=st.market,
                                   quiet_s=round((time.time_ns() - self.last_msg_ns) / NS, 1),
                                   connected=getattr(self.ws, "is_connected", True))
                        for side in (1, -1):
                            await self.cancel(st, side)
            if (self.log_dir / "STOP").exists():
                self.event("stop_file", action="shutting down")
                self.running = False
            self.write_status()
            await asyncio.sleep(2)

    def write_status(self):
        (self.log_dir / "status.json").write_text(json.dumps({
            "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "dry_run": self.dry_run, "environment": self.rest.config.environment, "actions": self.actions,
            "markets": {mk: {"bid": st.bb, "ask": st.ba, "position": round(st.pos, 10),
                             "position_usd": round(st.pos * st.mid, 2) if st.mid == st.mid else None,
                             "day_pnl_usd": round(st.equity() - st.day_start_equity, 4), "stopped": st.stopped,
                             "quotes": {("bid" if s > 0 else "ask"): (o or {}).get("price") for s, o in st.working.items()}}
                        for mk, st in self.states.items()}}, indent=1))

    # ------------------------------------------------------------------- run
    async def run(self):
        self.running = True
        await self.start()
        tasks = [asyncio.create_task(t) for t in (self.dead_mans_switch(), self.watchdog(), self._reconcile_loop())]
        try:
            while self.running:
                await asyncio.sleep(0.5)
        finally:
            self.running = False
            for t in tasks:
                t.cancel()
            await self.shutdown()

    async def _reconcile_loop(self):
        while self.running:
            await asyncio.sleep(float(self.cfg.get("reconcile_s", 30)))
            await self.reconcile()

    async def shutdown(self):
        self.event("shutdown", action="cancel all + disarm dead man's switch")
        for st in self.states.values():
            for side in (1, -1):
                await self.cancel(st, side)
        if not self.dry_run:
            try:
                await self.rest.cancel_all_orders()
                await self.rest.schedule_cancel(None)
            except Exception as e:
                self.event("shutdown_error", error=str(e)[:300])
        self.write_status()
        self._events.close()
