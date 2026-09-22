"""The quoting rule, shared by the backtest replay and the live trader.

Pure functions: given the current book, our position and a few flags, decide where the two
post-only quotes belong and whether an existing quote is far enough off to be worth moving.
src/replay.py and src/live/trader.py both call this, so a backtested rule and a live rule
cannot drift apart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class QuoteRules:
    depth_bps: float = 3.0          # how far from the reference price each quote rests
    requote_bps: float = 1.0        # move a quote only once its target drifts this far
    clip_usd: float = 25.0          # size of each quote
    max_pos_usd: float = 100.0      # stop quoting the side that would grow inventory past this
    min_notional: float = 5.0       # venue minimum order value
    tick: float = 0.01
    step: float = 1e-8
    exit_mode: str = "mid"          # "mid": closing quote sits at ref ± depth; "touch": joins the best price
    skew_bps: float = 0.0           # shift both quotes toward flat, scaled by inventory
    trend_guard_bps: float = 0.0    # don't add to a position the mid has moved this far against
    anchored: bool = False          # reference is an external fair value -> never cross the touch


@dataclass
class QuoteTarget:
    side: int                       # +1 bid, -1 ask
    price: float
    qty: float


def round_to_tick(price: float, tick: float, up: bool) -> float:
    """Snap to the tick grid, then clear binary dust so the price is exactly on tick.

    Without the final round, 10010 * 0.01 is 100.10000000000001 and the venue rejects it.
    """
    n = math.ceil(price / tick - 1e-9) if up else math.floor(price / tick + 1e-9)
    return round(n * tick, max(0, -math.floor(math.log10(tick)) + 1))


def qty_for(rules: QuoteRules, price: float) -> float:
    """Clip size in base units, on the step grid and at or above the venue minimum."""
    q = max(1, round(rules.clip_usd / price / rules.step)) * rules.step
    while q * price < rules.min_notional:
        q += rules.step
    return q


def plan(
    rules: QuoteRules,
    *,
    bb: float,
    ba: float,
    ref: float,
    pos: float,
    trend_bps: float = 0.0,
    allow_open: bool = True,
    allow_close: bool = True,
) -> Dict[int, Optional[QuoteTarget]]:
    """Where each side should rest now; None means that side should not be quoted.

    allow_open False (daily loss stop, session closed) still lets the inventory-closing side
    work when allow_close is True. allow_close False (cooldown after a stop-loss) pulls both.
    """
    mid = (bb + ba) / 2
    inv_usd = pos * mid
    skew = -rules.skew_bps * max(-1.0, min(1.0, inv_usd / rules.max_pos_usd)) if rules.max_pos_usd > 0 else 0.0
    out: Dict[int, Optional[QuoteTarget]] = {1: None, -1: None}
    for s in (1, -1):
        reduces = s * pos < 0
        want = (allow_open or reduces) and allow_close
        if want and s * inv_usd >= rules.max_pos_usd:
            want = False            # this side would grow inventory past the cap
        if want and rules.trend_guard_bps > 0 and s * pos > 0 and -s * trend_bps >= rules.trend_guard_bps:
            want = False            # already long into a fall (or short into a rally): stop adding
        if not want:
            continue
        if reduces and rules.exit_mode == "touch":
            price = ba if s == -1 else bb          # join the best price on the closing side
        else:
            price = round_to_tick(ref * (1 - s * rules.depth_bps * 1e-4 + skew * 1e-4), rules.tick, up=(s == -1))
        if rules.anchored:                          # post-only against an external reference:
            price = min(price, ba - rules.tick) if s == 1 else max(price, bb + rules.tick)
        out[s] = QuoteTarget(side=s, price=price, qty=qty_for(rules, price))
    return out


def needs_requote(current_price: float, target: QuoteTarget, mid: float, requote_bps: float) -> bool:
    """True when the resting quote is far enough from its target to be worth a modify."""
    return abs(current_price - target.price) / mid * 1e4 >= requote_bps
