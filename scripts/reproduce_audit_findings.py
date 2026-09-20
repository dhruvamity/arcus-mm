#!/usr/bin/env python3
"""
Reproduction script for Mandate v3 Appendix A findings.
Usage: python scripts/reproduce_audit_findings.py <finding_id>
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def reproduce_v05() -> None:
    """A2: Legacy engine is not monotone (V-05)"""
    from src.backtester import ArcusEventBacktester
    from src.models.fill import FillModelType as F
    from src.strategies.fixed_spread import FixedSpreadStrategy

    def data(seed: int, n: int = 3000):
        r = random.Random(seed)
        mid, t = 100000.0, 1_000_000_000
        bbo, trd = [], []
        for _ in range(n):
            t += r.randint(1_000_000, 200_000_000)
            mid += r.gauss(0, 15)
            h = r.choice([0.5, 1, 2, 5])
            b, a = round(mid - h, 1), round(mid + h, 1)
            if r.random() < 0.55:
                bbo.append(dict(
                    recv_ts_ns=t, mid_price=(a + b) / 2,
                    spread_bps=(a - b) / ((a + b) / 2) * 1e4,
                    bid_price=b, bid_size=r.uniform(0.05, 2),
                    ask_price=a, ask_size=r.uniform(0.05, 2)
                ))
            else:
                s = r.choice(["BUY", "SELL"])
                off = r.choice([0, 0, 0.1, 0.5, 2])
                trd.append(dict(
                    recv_ts_ns=t,
                    price=round(a + off if s == "BUY" else b - off, 1),
                    size=r.uniform(0.001, 0.5), side=s
                ))
        return pd.DataFrame(bbo), pd.DataFrame(trd)

    viol = 0
    for seed in range(60):
        bbo, trd = data(seed)
        n = {}
        for fm in (F.MODEL_A_TOUCH, F.MODEL_B_MODERATE, F.MODEL_C_CONSERVATIVE):
            s = FixedSpreadStrategy(market="BTC-USD", tick_size=0.1, step_size=0.0001, spread_bps=4.0, clip_notional=10.0)
            n[fm] = ArcusEventBacktester(
                strategy=s, fill_model=fm, initial_capital=100.0, maker_fee_bps=0.0
            ).run_simulation(df_bbo=bbo, df_trades=trd, funding_data=[]).pnl_summary["total_trades_count"]
        a, b, c = n[F.MODEL_A_TOUCH], n[F.MODEL_B_MODERATE], n[F.MODEL_C_CONSERVATIVE]
        if not (a >= b >= c):
            viol += 1
            print(f"VIOLATION seed {seed}: A={a}, B={b}, C={c}")
    print(f"violations: {viol} / 60")
    if viol > 0:
        print("CONFIRMED: V-05 legacy engine violates monotonicity.")


def reproduce_v05_positive_control() -> None:
    """A3: SimEngine monotonicity positive control"""
    from src.sim.engine import SimEngine, SimEvent, SimEventType as T
    from src.models.fill import FillModelType as F
    from src.models.latency import LatencyConfig
    from src.strategies.fixed_spread import FixedSpreadStrategy

    def run(seed: int, n: int = 3000):
        r = random.Random(seed)
        m = "BTC-USD"
        specs = {m: {"tick_size": 0.1, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.0001}}
        s = FixedSpreadStrategy(market=m, tick_size=0.1, step_size=0.0001, spread_bps=r.choice([2.0, 4.0, 6.0]), clip_notional=10.0)
        e = SimEngine([m], specs, {"fs": s}, latency_config=LatencyConfig(order_entry_latency_ms=25.0, cancel_latency_ms=25.0), random_seed=seed)
        mid, t = 100000.0, 1_000_000_000
        for _ in range(n):
            t += r.randint(1_000_000, 200_000_000)
            mid += r.gauss(0, 15)
            h = r.choice([0.5, 1, 2, 5])
            b, a = round(mid - h, 1), round(mid + h, 1)
            x = r.random()
            if x < 0.55:
                e.on_event(SimEvent(T.BBO, t, m, {"bid_price": b, "ask_price": a, "bid_size": r.uniform(0.05, 2), "ask_size": r.uniform(0.05, 2)}))
            elif x < 0.95:
                side = r.choice(["BUY", "SELL"])
                off = r.choice([0, 0, 0.1, 0.5, 2])
                e.on_event(SimEvent(T.TRADE, t, m, {"price": round(a + off if side == "BUY" else b - off, 1), "size": r.uniform(0.001, 0.5), "side": side}))
            else:
                e.on_event(SimEvent(T.CLOCK_TICK, t, m, {}))
        c = e.contexts["fs"]
        return [c.pnl_engines[k].total_trades_count for k in (F.MODEL_A_TOUCH, F.MODEL_B_MODERATE, F.MODEL_C_CONSERVATIVE)]

    bad = sum(1 for sd in range(200) if not (lambda r: r[0] >= r[1] >= r[2])(run(sd)))
    print(f"violations: {bad} / 200")
    if bad == 0:
        print("CONFIRMED: SimEngine preserves A >= B >= C monotonicity in 200/200 runs.")


def reproduce_v08() -> None:
    """A4: Funding overcharge (V-08)"""
    from src.sim.engine import SimEngine, SimEvent, SimEventType as T
    from src.models.fill import FillModelType as F
    from src.strategies.fixed_spread import FixedSpreadStrategy

    m = "BTC-USD"
    specs = {m: {"tick_size": 0.1, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.0001}}
    e = SimEngine([m], specs, {"fs": FixedSpreadStrategy(market=m, tick_size=0.1, step_size=0.0001, spread_bps=10.0, clip_notional=10.0)}, random_seed=1)
    p = e.contexts["fs"].pnl_engines[F.MODEL_B_MODERATE]
    p.record_fill("BUY", 100.0, 1.0, 100.0, is_taker=False)
    e.venues[m].current_mid = 100.0
    for i in range(60):
        e.on_event(SimEvent(T.FUNDING, 1_000_000_000 + i * 60_000_000_000, m, {"funding_rate": 1e-4}))
    print(f"charged for one hour: {p.total_funding_pnl} | correct: {-1.0 * 100.0 * 1e-4}")
    has_funding_model = "funding_model." in open("src/sim/engine.py").read()
    print(f"TimeAwareFundingModel used by engine: {has_funding_model}")
    if abs(p.total_funding_pnl - (-0.6)) < 1e-5 and not has_funding_model:
        print("CONFIRMED: V-08 charges funding on every message (60x overcharge) and ignores TimeAwareFundingModel.")


def reproduce_v06_v07_v09() -> None:
    """A5: Risk state never recovers; L2 crash; queue behind touch (V-06, V-07, V-09)"""
    from src.sim.engine import SimEngine, SimEvent, SimEventType as T
    from src.models.latency import LatencyConfig
    from src.strategies.fixed_spread import FixedSpreadStrategy

    m = "BTC-USD"
    specs = {m: {"tick_size": 0.1, "step_size": 0.0001, "min_notional": 5.0, "min_order_size": 0.0001}}

    def mk(bps: float = 10.0):
        s = FixedSpreadStrategy(market=m, tick_size=0.1, step_size=0.0001, spread_bps=bps, clip_notional=10.0)
        return SimEngine([m], specs, {"fs": s}, latency_config=LatencyConfig(order_entry_latency_ms=20.0, cancel_latency_ms=20.0), random_seed=7)

    bbo = lambda t: SimEvent(T.BBO, t, m, {"bid_price": 99.9, "ask_price": 100.1, "bid_size": 1, "ask_size": 1})
    t0 = 1_000_000_000

    # V-09: Risk recovery failure
    e = mk()
    c = e.contexts["fs"]
    e.on_event(bbo(t0))
    e.on_event(SimEvent(T.CLOCK_TICK, t0 + int(4e9), m, {}))
    print(f"after 4 s silence: {c.risk_state.value}")
    for i in range(1, 201):
        e.on_event(bbo(t0 + int(4e9) + i * int(1e8)))
    print(f"after 200 clean BBO: {c.risk_state.value}")
    if c.risk_state.value == "PAUSED_STALE_FEED":
        print("CONFIRMED: V-09 Risk state never recovers from PAUSED_STALE_FEED.")

    # V-06: L2 crash
    try:
        e = mk()
        e.on_event(SimEvent(T.L2_DELTA, t0, m, {"isSnapshot": True, "bids": [["99.9", "1"]], "asks": [["100.1", "1"]], "lastSequenceId": 10}))
        print("L2 event processed without error (unexpected)")
    except AttributeError as ex:
        print(f"CONFIRMED: V-06 L2 event -> AttributeError: {ex}")

    # V-07: Queue behind the touch
    e = mk(40.0)
    c = e.contexts["fs"]
    e.on_event(bbo(t0))
    o = [x for x in c.in_flight_orders if x.side == "BUY"][0]
    e.on_event(SimEvent(T.CLOCK_TICK, t0 + int(50e6), m, {}))
    fills = e.on_event(SimEvent(T.TRADE, t0 + int(60e6), m, {"price": o.price, "size": 0.01, "side": "SELL"}))
    print(f"quote: {o.price}, queue_ahead: {o.queue_ahead_size}, fills: {[f['fill_model'] for f in fills]}")
    if o.queue_ahead_size == 0.0 and len(fills) >= 2:
        print("CONFIRMED: V-07 Quote behind the touch gets queue_ahead 0.0 instead of L2 depth.")


def reproduce_v15() -> None:
    """A6: Paper-trader metadata loader crash (V-15)"""
    def load(res):
        try:
            return res.get("markets") or res if isinstance(res, list) else []
        except Exception as ex:
            return f"EXC {type(ex).__name__}: {ex}"

    dict_res = load({"markets": [{"market": "BTC-USD"}]})
    list_res = load([{"market": "BTC-USD"}])
    print(f"dict input: {dict_res}")
    print(f"list input: {list_res}")
    if dict_res == [] and "EXC AttributeError" in str(list_res):
        print("CONFIRMED: V-15 Paper-trader metadata loader returns [] on dict and raises AttributeError on list.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/reproduce_audit_findings.py <v05|v05_pos|v06_v07_v09|v08|v15>")
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == "v05":
        reproduce_v05()
    elif cmd == "v05_pos":
        reproduce_v05_positive_control()
    elif cmd == "v08":
        reproduce_v08()
    elif cmd in ("v06", "v07", "v09", "v06_v07_v09"):
        reproduce_v06_v07_v09()
    elif cmd == "v15":
        reproduce_v15()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
