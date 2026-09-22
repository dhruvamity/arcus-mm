"""Queue-aware replay of recorded Arcus L2 tape for passive quoting rules.

Event stream per market, ordered by the venue's global sequence number (trades, L2
deltas and BBO share one sequence space; a match and the book delta it causes carry the
same number, so trades are applied first). Timing is in local receive time: an order
sent when we observe an event at time t is live for events received after t + RTT, which
is exactly what a process on this host would experience.

Fill rules for a resting virtual order at price p (price-time priority):
  * a trade strictly through p            -> fully filled (the level was exhausted)
  * a trade at p                           -> queue_ahead is consumed first, remainder fills us
  * the displayed level at p shrinks below queue_ahead -> queue_ahead = displayed size
    (someone ahead cancelled; the displayed size never includes our virtual order)
  * p outside the known book when we arrive -> queue unknown: only trade-through fills
Our order does not change the book (clips are tiny relative to depth). Post-only orders
that would cross on arrival are rejected, as ALO is on Arcus.

Parsed tape is cached as .npz under data/derived/ (gitignored).
"""

from __future__ import annotations

import json
import math
from array import array
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from src.tape import RAW_ROOT, open_tape, tape_days

DERIVED = RAW_ROOT.parent / "derived"

# event kinds; at equal sequence numbers trades go first, then deltas, then snapshots, then BBO
TRADE, DELTA, SNAP, BBO = 0, 1, 2, 3
VISIBLE_LEVELS = 45


def _parse_day(day: str, market: str):
    """Flatten one day's L2/trades/BBO into columns: seq, kind, recv_ns, side(+1 bid/-1 ask), price, size, aux."""
    seq, kind, recv = array("q"), array("b"), array("q")
    side, px, sz, aux = array("b"), array("d"), array("d"), array("d")

    def put(s, k, r, sd, p, q, a=0.0):
        seq.append(s); kind.append(k); recv.append(r); side.append(sd); px.append(p); sz.append(q); aux.append(a)

    seen = set()
    fh = open_tape(day, market, "l2OrderbookUpdates.jsonl")
    if fh is not None:
        with fh:
            for line in fh:
                r = json.loads(line)
                d = r["data"]
                c = d.get("contents")
                if d.get("type") not in ("subscribed", "channel_data") or not c or "globalSequenceId" not in c:
                    continue  # unsubscribe/error frames
                g = c["globalSequenceId"]
                if d["type"] == "subscribed":
                    k = SNAP
                    put(g, k, r["recv_ts_ns"], 0, 0.0, 0.0)  # marker: reset book before these levels
                else:
                    if g in seen:
                        continue
                    seen.add(g)
                    k = DELTA
                for p, q in c["bids"]:
                    put(g, k, r["recv_ts_ns"], 1, float(p), float(q))
                for p, q in c["asks"]:
                    put(g, k, r["recv_ts_ns"], -1, float(p), float(q))
    seen = set()
    with open_tape(day, market, "trades.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            for t in r["data"]["contents"]:
                if t["tradeId"] in seen:
                    continue
                seen.add(t["tradeId"])
                # side = +1 when the taker bought (hits asks), -1 when the taker sold (hits bids)
                put(t["sequenceNumber"], TRADE, r["recv_ts_ns"], 1 if t["side"] == "BUY" else -1,
                    float(t["price"]), float(t["size"]))
    seen = set()
    with open_tape(day, market, "bbo.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            c = r["data"]["contents"]
            if "bestBid" not in c or "bestAsk" not in c:
                continue
            g = c["globalSequenceId"]
            if g in seen:
                continue
            seen.add(g)
            put(g, BBO, r["recv_ts_ns"], 0, float(c["bestBid"]["price"]), float(c["bestAsk"]["price"]),
                float(c["timestamp"]))
    cols = dict(seq=np.frombuffer(seq, np.int64), kind=np.frombuffer(kind, np.int8),
                recv=np.frombuffer(recv, np.int64), side=np.frombuffer(side, np.int8),
                px=np.frombuffer(px, np.float64), sz=np.frombuffer(sz, np.float64),
                aux=np.frombuffer(aux, np.float64))
    order = np.lexsort((cols["kind"], cols["seq"]))
    return {k: v[order] for k, v in cols.items()}


def load_tape(market: str, days: Optional[List[str]] = None) -> Dict[str, np.ndarray]:
    """Concatenated, sequence-ordered event columns for a market across recorded days."""
    DERIVED.mkdir(parents=True, exist_ok=True)
    parts = []
    for day in (days or tape_days(market)):
        cache = DERIVED / f"{market}_{day}.npz"
        src = RAW_ROOT / day / market
        # re-parse if the day's raw files are still growing (the recorder writes the current day)
        mtime = max((f.stat().st_mtime for f in src.iterdir()), default=0.0) if src.is_dir() else 0.0
        if cache.exists() and cache.stat().st_mtime > mtime:
            with np.load(cache) as z:
                parts.append({k: z[k] for k in z.files})
        else:
            cols = _parse_day(day, market)
            np.savez(cache, **cols)
            parts.append(cols)
    out = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    order = np.lexsort((out["kind"], out["seq"]))
    return {k: v[order] for k, v in out.items()}


@dataclass
class Order:
    side: int              # +1 bid, -1 ask
    price: float
    qty: float
    live_at: int           # recv-time ns when it reaches the book
    cancel_at: int = 1 << 62
    queue: float = -1.0    # size ahead of us; -1 = not yet live, math.inf = unknown (off-book)


@dataclass
class Params:
    depth_bps: float = 5.0          # quote distance from mid
    requote_bps: float = 1.0        # move quote only when target drifts this far
    clip_usd: float = 25.0
    max_pos_usd: float = 100.0
    skew_bps: float = 0.0           # at max inventory, shift both quotes by this much toward flat
    rtt_ms: float = 200.0
    maker_fee_bps: float = 0.0
    taker_fee_bps: float = 2.25
    tick: float = 0.01
    step: float = 1e-8
    min_notional: float = 5.0
    active: Optional[callable] = None   # f(recv_ns) -> bool; outside, pull quotes
    # optional external fair value (e.g. Binance mid + Arcus basis): (observed_ns sorted, price).
    # When set, quotes are placed around fair instead of the Arcus mid, never crossing the touch.
    fair: Optional[tuple] = None
    # stop quoting for the rest of the UTC day once equity is down this much from the day's start
    daily_stop_usd: float = 0.0
    # Arcus per-subaccount action budget (docs: api-reference/rate-limits). Headroom starts at
    # these values (20k/40k for a fresh subaccount), grows 10 units per $ filled, and once spent
    # allows one action per 10 s per pool. A requote is a modify (1 order unit); pulling a quote
    # is a cancel (1 cancel unit). Actions the budget cannot pay for are simply not taken.
    rate_limit: bool = False
    order_units: float = 20_000.0
    cancel_units: float = 40_000.0


@dataclass
class Result:
    fills: List[tuple] = field(default_factory=list)   # (recv_ns, side, price, qty, mid)
    actions: int = 0
    rejects: int = 0
    stops: int = 0
    throttled: int = 0
    order_units_left: float = 0.0
    cancel_units_left: float = 0.0
    final_pos: float = 0.0
    cash: float = 0.0
    final_mid: float = float("nan")
    max_abs_pos_usd: float = 0.0
    hours: float = 0.0


def simulate(t: Dict[str, np.ndarray], p: Params) -> Result:
    bids: Dict[float, float] = {}
    asks: Dict[float, float] = {}
    book_known = {1: False, -1: False}
    bb = ba = float("nan")
    rtt = int(p.rtt_ms * 1e6)
    orders: List[Order] = []          # resting + in-flight
    working = {1: None, -1: None}     # latest order we intend to keep per side
    pos = cash = 0.0
    res = Result()
    in_snap = -1
    day_ns = 86_400 * 10**9
    cur_day, day_start_eq, stopped = -1, 0.0, False
    units = {"o": p.order_units, "c": p.cancel_units}
    next_drip = {"o": 0, "c": 0}

    def pay(pool, now):
        """Charge one action to a pool; False if the budget cannot pay for it right now."""
        if not p.rate_limit:
            return True
        if units[pool] >= 1:
            units[pool] -= 1
            return True
        if now >= next_drip[pool]:
            next_drip[pool] = now + 10 * 10**9
            return True
        res.throttled += 1
        return False

    def rnd(x, up):
        n = x / p.tick
        return (math.ceil(n - 1e-9) if up else math.floor(n + 1e-9)) * p.tick

    def qty_for(price):
        q = max(1, round(p.clip_usd / price / p.step)) * p.step
        while q * price < p.min_notional:
            q += p.step
        return q

    def fill(o: Order, q: float, now: int):
        nonlocal pos, cash
        q = min(q, o.qty)
        if q <= 0:
            return
        o.qty -= q
        pos += o.side * q
        cash -= o.side * q * o.price + q * o.price * p.maker_fee_bps * 1e-4
        res.fills.append((now, o.side, o.price, q, (bb + ba) / 2))
        units["o"] += 10 * q * o.price
        units["c"] += 10 * q * o.price
        res.max_abs_pos_usd = max(res.max_abs_pos_usd, abs(pos) * o.price)

    seq, kind, recv, side, px, sz, aux = (t[k] for k in ("seq", "kind", "recv", "side", "px", "sz", "aux"))
    n = len(seq)
    first_recv = int(recv[0]) if n else 0
    for i in range(n):
        k = kind[i]
        now = int(recv[i])

        # activate / retire orders whose timing has arrived
        if orders:
            keep = []
            for o in orders:
                if o.cancel_at <= now or o.qty <= 1e-12:
                    continue
                if o.queue < 0 and o.live_at <= now:
                    if (o.side == 1 and ba == ba and o.price >= ba) or (o.side == -1 and bb == bb and o.price <= bb):
                        res.rejects += 1  # ALO would cross
                        if working[o.side] is o:
                            working[o.side] = None
                        continue
                    book = bids if o.side == 1 else asks
                    # feed carries ~50 levels; levels that drift out of that window are never
                    # zeroed, so only trust the book for prices within the top VISIBLE levels
                    better = sum(1 for x in book if (x > o.price if o.side == 1 else x < o.price))
                    if not book_known[o.side] or better >= VISIBLE_LEVELS:
                        o.queue = math.inf
                    else:
                        o.queue = book.get(o.price, 0.0)
                keep.append(o)
            orders = keep

        if k == SNAP:
            if in_snap != seq[i]:
                in_snap = seq[i]
                if side[i] == 0:
                    bids.clear(); asks.clear()
                    book_known[1] = book_known[-1] = True
                    continue
            b = bids if side[i] == 1 else asks
            if sz[i] > 0:
                b[px[i]] = sz[i]
            continue
        if k == DELTA:
            b = bids if side[i] == 1 else asks
            if sz[i] > 0:
                b[px[i]] = sz[i]
            else:
                b.pop(px[i], None)
            for o in orders:
                if o.side == side[i] and o.price == px[i] and 0 <= o.queue < math.inf:
                    o.queue = min(o.queue, sz[i])
            continue
        if k == TRADE:
            tp, tq = px[i], sz[i]
            hit = -side[i]  # taker buy hits asks (our side -1)
            for o in orders:
                if o.side != hit or o.queue < 0:
                    continue
                through = tp < o.price if hit == 1 else tp > o.price
                if through:
                    fill(o, o.qty, now)
                elif tp == o.price and o.queue < math.inf:
                    rem = tq - o.queue
                    o.queue = max(0.0, o.queue - tq)
                    if rem > 0:
                        fill(o, rem, now)
            continue

        # BBO: observe and decide
        bb, ba = px[i], sz[i]
        mid = (bb + ba) / 2
        on = p.active(now) if p.active else True
        if p.daily_stop_usd > 0:
            eq = cash + pos * mid
            if now // day_ns != cur_day:
                cur_day, day_start_eq, stopped = now // day_ns, eq, False
            if eq - day_start_eq <= -p.daily_stop_usd:
                if not stopped:
                    res.stops += 1
                stopped = True
            on = on and not stopped
        ref = mid
        if p.fair is not None:
            k = int(np.searchsorted(p.fair[0], now, side="right")) - 1
            if k < 0 or not p.fair[1][k] > 0:
                on = False
            else:
                ref = float(p.fair[1][k])
        inv_usd = pos * mid
        skew = -p.skew_bps * max(-1.0, min(1.0, inv_usd / p.max_pos_usd)) if p.max_pos_usd > 0 else 0.0
        for s in (1, -1):
            w = working[s]
            want = on and not (s * inv_usd >= p.max_pos_usd)
            if want:
                target = ref * (1 - s * p.depth_bps * 1e-4 + skew * 1e-4)
                target = rnd(target, up=(s == -1))
                if p.fair is not None:  # post-only: rest at best at most one tick inside the spread
                    target = min(target, ba - p.tick) if s == 1 else max(target, bb + p.tick)
                if w is not None and w.qty > 1e-12 and w.cancel_at > now and abs(w.price - target) / mid * 1e4 < p.requote_bps:
                    continue
            elif w is None or w.cancel_at <= now:
                working[s] = None
                continue
            alive = w is not None and w.cancel_at > now and w.qty > 1e-12
            # requote = one modify (order pool); pull = cancel (cancel pool); new = place (order pool)
            if not pay("o" if want else "c", now):
                continue
            if alive:
                w.cancel_at = now + rtt
            working[s] = None
            res.actions += 1
            if want:
                o = Order(side=s, price=target, qty=qty_for(target), live_at=now + rtt)
                orders.append(o)
                working[s] = o

    res.final_pos, res.cash = pos, cash
    res.order_units_left, res.cancel_units_left = units["o"], units["c"]
    res.final_mid = (bb + ba) / 2
    res.hours = (int(recv[-1]) - first_recv) / 3.6e12 if n else 0.0
    return res
