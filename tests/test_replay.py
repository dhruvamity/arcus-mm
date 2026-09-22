"""Fill-rule tests for src/replay.py on hand-built tapes."""

import unittest

import numpy as np

from src.replay import BBO, DELTA, SNAP, TRADE, Params, simulate

MS = 1_000_000


def tape(rows):
    """rows: (seq, kind, recv_ms, side, px, sz) -> sorted column dict."""
    a = np.array(rows, dtype=float)
    cols = dict(seq=a[:, 0].astype(np.int64), kind=a[:, 1].astype(np.int8), recv=(a[:, 2] * MS).astype(np.int64),
                side=a[:, 3].astype(np.int8), px=a[:, 4], sz=a[:, 5], aux=np.zeros(len(a)))
    o = np.lexsort((cols["kind"], cols["seq"]))
    return {k: v[o] for k, v in cols.items()}


def book(seq=1, t=0):
    """Snapshot: bids 99.99 x1, 99.95 x2; asks 100.01 x1, 100.05 x2; then BBO."""
    return [(seq, SNAP, t, 0, 0, 0), (seq, SNAP, t, 1, 99.99, 1), (seq, SNAP, t, 1, 99.95, 2),
            (seq, SNAP, t, -1, 100.01, 1), (seq, SNAP, t, -1, 100.05, 2), (seq + 1, BBO, t, 0, 99.99, 100.01)]


# bid target = floor(100 * (1 - 5bps)) = 99.95, ask = 100.05; clip $100 -> 1.0 unit
P = dict(depth_bps=5.0, requote_bps=100.0, clip_usd=100.0, max_pos_usd=1e9, rtt_ms=100, tick=0.01, step=1.0, min_notional=1)


class TestReplayFills(unittest.TestCase):
    def run_(self, extra):
        return simulate(tape(book() + extra), Params(**P))

    def test_queue_ahead_consumed_before_fill(self):
        r = self.run_([(10, TRADE, 200, -1, 99.95, 1.5)])     # taker sells 1.5 into 2.0 ahead
        self.assertEqual(r.fills, [])
        r = self.run_([(10, TRADE, 200, -1, 99.95, 1.5), (11, TRADE, 210, -1, 99.95, 1.0)])
        self.assertEqual(len(r.fills), 1)
        self.assertAlmostEqual(r.fills[0][3], 0.5)            # 2.5 traded - 2.0 ahead
        self.assertAlmostEqual(r.final_pos, 0.5)

    def test_trade_through_fills_fully(self):
        r = self.run_([(10, TRADE, 200, -1, 99.94, 0.01)])
        self.assertAlmostEqual(r.final_pos, 1.0)
        self.assertAlmostEqual(r.cash, -99.95)

    def test_cancel_ahead_improves_queue(self):
        r = self.run_([(10, DELTA, 200, 1, 99.95, 0.2), (11, TRADE, 210, -1, 99.95, 0.5)])
        self.assertAlmostEqual(r.final_pos, 0.3)

    def test_not_live_before_rtt(self):
        r = self.run_([(10, TRADE, 50, -1, 99.90, 5.0)])       # 50 ms < 100 ms RTT
        self.assertEqual(r.fills, [])

    def test_ask_side_and_fee(self):
        p = dict(P, maker_fee_bps=1.0)
        r = simulate(tape(book() + [(10, TRADE, 200, 1, 100.06, 0.1)]), Params(**p))
        self.assertAlmostEqual(r.final_pos, -1.0)
        self.assertAlmostEqual(r.cash, 100.05 - 100.05 * 1e-4)

    def test_off_book_needs_trade_through(self):
        # no snapshot -> book unknown -> a trade exactly at our price must not fill us
        rows = [(2, BBO, 0, 0, 99.99, 100.01), (10, TRADE, 200, -1, 99.95, 50.0)]
        r = simulate(tape(rows), Params(**P))
        self.assertEqual(r.fills, [])
        rows.append((11, TRADE, 210, -1, 99.94, 0.01))
        r = simulate(tape(rows), Params(**P))
        self.assertAlmostEqual(r.final_pos, 1.0)

    def test_post_only_reject_when_crossing_on_arrival(self):
        # book moves down before our bid arrives: best ask 99.94 <= our bid 99.95
        rows = book() + [(5, BBO, 50, 0, 99.90, 99.94), (10, TRADE, 200, -1, 99.80, 1.0)]
        p = dict(P, requote_bps=1e9)
        r = simulate(tape(rows), Params(**p))
        self.assertGreaterEqual(r.rejects, 1)
        self.assertEqual([f for f in r.fills if f[1] == 1], [])

    def test_inventory_cap_stops_quoting_that_side(self):
        p = dict(P, max_pos_usd=50.0)                          # one fill ($99.95) exceeds the cap
        rows = book() + [(10, TRADE, 200, -1, 99.90, 5.0), (11, BBO, 300, 0, 99.99, 100.01),
                         (20, TRADE, 600, -1, 99.80, 5.0)]
        r = simulate(tape(rows), Params(**p))
        self.assertAlmostEqual(r.final_pos, 1.0)

    def test_fair_value_anchor(self):
        # fair says 99.00 while Arcus mid is 100.00: bid goes to 99.00*(1-5bps)=98.95, ask stays
        # above the Arcus bid (clamped to 99.99 + tick = 100.00) instead of 99.05
        fair = (np.array([0], dtype=np.int64), np.array([99.0]))
        rows = book() + [(10, TRADE, 200, -1, 98.94, 0.01), (11, TRADE, 210, 1, 100.01, 0.01)]
        r = simulate(tape(rows), Params(**dict(P, fair=fair)))
        self.assertEqual(sorted((f[1], round(f[2], 2)) for f in r.fills), [(-1, 100.0), (1, 98.95)])

    def test_daily_stop_pulls_quotes(self):
        # bid fills at 99.95, then the market drops: equity falls $4.95 < -$1 stop -> no more quoting today
        p = dict(P, daily_stop_usd=1.0)
        rows = book() + [(10, TRADE, 200, -1, 99.90, 5.0), (11, BBO, 300, 0, 95.00, 95.10),
                         (20, TRADE, 900, -1, 90.00, 5.0)]
        r = simulate(tape(rows), Params(**p))
        self.assertEqual(r.stops, 1)
        self.assertAlmostEqual(r.final_pos, 1.0)             # second sweep finds no bid of ours

        r = simulate(tape(rows), Params(**P))                 # without the stop it buys again
        self.assertAlmostEqual(r.final_pos, 2.0)

    def test_rate_limit_budget(self):
        # 1 order unit. t=0: bid paid from the unit, ask rides the drip (next drip at 10 s).
        # t=1 s: mid moved 1%, both requotes refused. t=13 s: one requote rides the drip.
        p = dict(P, requote_bps=1.0, rate_limit=True, order_units=1, cancel_units=0, max_pos_usd=1e9)
        rows = book() + [(10, BBO, 1000, 0, 98.99, 99.01), (11, BBO, 13000, 0, 97.99, 98.01)]
        r = simulate(tape(rows), Params(**p))
        self.assertEqual(r.actions, 3)
        self.assertEqual(r.throttled, 3)

    def test_fills_refill_budget(self):
        p = dict(P, rate_limit=True, order_units=2, cancel_units=0)
        r = simulate(tape(book() + [(10, TRADE, 200, -1, 99.94, 0.01)]), Params(**p))
        self.assertAlmostEqual(r.order_units_left, 10 * 99.95)   # both units spent, $99.95 filled

    def test_stop_loss_flattens_as_taker(self):
        # long 1.0 @ 99.95, then mid falls to 95.05 (~490 bps against) -> taker sell at bid - tick
        p = dict(P, stop_loss_bps=100.0)
        rows = book() + [(10, TRADE, 200, -1, 99.90, 5.0), (11, BBO, 300, 0, 95.00, 95.10)]
        r = simulate(tape(rows), Params(**p))
        self.assertEqual(r.stop_losses, 1)
        self.assertAlmostEqual(r.final_pos, 0.0)
        last = r.fills[-1]
        self.assertEqual((last[1], round(last[2], 2), last[6]), (-1, 94.99, True))
        self.assertAlmostEqual(last[5], 94.99 * 2.25e-4)             # taker fee charged
        self.assertAlmostEqual(r.cash, -99.95 + 94.99 - 94.99 * 2.25e-4)

    def test_exit_at_touch_while_holding_inventory(self):
        # after the bid fills, the closing ask joins the best ask (100.01) instead of mid+5 bps (100.05)
        p = dict(P, exit_mode="touch", requote_bps=0.0)
        rows = book() + [(10, TRADE, 200, -1, 99.90, 5.0), (11, BBO, 300, 0, 99.99, 100.01),
                         (20, TRADE, 600, 1, 100.02, 5.0)]
        r = simulate(tape(rows), Params(**p))
        sells = [f for f in r.fills if f[1] == -1]
        self.assertEqual([round(f[2], 2) for f in sells], [100.01])
        self.assertAlmostEqual(r.final_pos, 0.0)


if __name__ == "__main__":
    unittest.main()
