"""src/live/trader.py against a fake venue: order handling, caps, stops and shutdown."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.live.trader import LiveTrader
from src.models.core import MarketMetadata, OrderResponse

META = MarketMetadata(marketId=7, marketDisplayName="X-USD", baseAsset="X", quoteAsset="USD",
                      tickSize="0.01", stepSize="0.001", minOrderSize="0.001", minOrderNotional="5",
                      oraclePrice="100")
CFG = {"markets": [{"market": "X-USD", "depth_bps": 10, "clip_usd": 25, "max_pos_usd": 50, "daily_stop_usd": 1}],
       "requote_bps": 5.0, "clip_usd": 25, "max_pos_usd": 50, "daily_stop_usd": 1, "stale_s": 5}





class FakeRest:
    def __init__(self):
        self.config = SimpleNamespace(active_wallet_address="0xabc", account_index=0, environment="testnet")
        self.calls = []
        self.positions = []
        self.open_orders = []
        self.n = 0

    async def get_markets(self):
        return [META]

    async def get_positions(self):
        return self.positions

    async def get_open_orders(self, market_id=None):
        return self.open_orders

    async def place_order(self, order, market):
        self.n += 1
        self.calls.append(("place", str(order.side.value), float(order.price), float(order.quantity),
                           order.timeInForce.value))
        return OrderResponse(orderId=f"o{self.n}", clientId=order.clientId, status="ACK", marketId=market.marketId)

    async def modify_order(self, market_id, order_id, price, quantity, side, market, **kw):
        self.calls.append(("modify", order_id, float(price)))
        return OrderResponse(orderId=order_id, status="ACK", marketId=market_id)

    async def cancel_order(self, market_id, order_id=None, client_id=None):
        self.calls.append(("cancel", order_id))
        return OrderResponse(orderId=order_id, status="CANCELED", marketId=market_id)

    async def cancel_all_orders(self, market_id=None):
        self.calls.append(("cancel_all",))
        return {}

    async def schedule_cancel(self, deadline_micros):
        self.calls.append(("dms", deadline_micros))
        return {}


class FakeWs:
    def __init__(self):
        self.subs = []

    is_connected = True

    async def subscribe(self, channel, sub_id, cb=None, extra=None):
        self.subs.append((channel, sub_id, extra))


def bbo(bid, ask, market="X-USD"):
    return {"id": market, "contents": {"bestBid": {"price": str(bid), "size": "5"},
                                       "bestAsk": {"price": str(ask), "size": "5"}}}


def fill(side, price, qty, market="X-USD", snapshot=False):
    row = {"marketDisplayName": market, "side": side, "price": str(price), "size": str(qty), "fee": "0"}
    return {"contents": {"fills": [row]}} if snapshot else {"contents": [row]}


class TestLiveTrader(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rest = FakeRest()
        self.t = LiveTrader(CFG, self.rest, FakeWs(), Path(self.tmp.name), dry_run=False)
        await self.t.start()
        self.t.running = True

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_places_post_only_quotes_at_planned_prices(self):
        await self.t.on_bbo(bbo(99.99, 100.01))
        places = [c for c in self.rest.calls if c[0] == "place"]
        self.assertEqual(len(places), 2)
        self.assertEqual({(c[1], c[2], c[4]) for c in places},
                         {("BUY", 99.90, "ALO"), ("SELL", 100.10, "ALO")})          # mid ± 10 bps
        self.assertAlmostEqual(places[0][3], 0.25)                                   # $25 / 100

    async def test_small_move_holds_big_move_modifies(self):
        await self.t.on_bbo(bbo(99.99, 100.01))
        self.rest.calls.clear()
        await self.t.on_bbo(bbo(100.00, 100.02))      # ~1 bp: below the 5 bp requote threshold
        self.assertEqual(self.rest.calls, [])
        await self.t.on_bbo(bbo(100.09, 100.11))      # ~10 bp: both sides re-priced with modify
        self.assertEqual([c[0] for c in self.rest.calls], ["modify", "modify"])

    async def test_inventory_cap_pulls_the_opening_side_only(self):
        await self.t.on_bbo(bbo(99.99, 100.01))
        await self.t.on_fill(fill("BUY", 99.90, 0.6))          # $60 long > $50 cap
        self.rest.calls.clear()
        await self.t.on_bbo(bbo(99.99, 100.01))
        self.assertEqual([c[0] for c in self.rest.calls], ["cancel"])   # bid pulled, ask still working
        self.assertIsNone(self.t.states["X-USD"].working[1])
        self.assertIsNotNone(self.t.states["X-USD"].working[-1])

    async def test_daily_stop_keeps_the_closing_quote(self):
        st = self.t.states["X-USD"]
        await self.t.on_bbo(bbo(99.99, 100.01))
        await self.t.on_fill(fill("BUY", 100.00, 0.2))         # long 0.2 @ 100
        await self.t.on_bbo(bbo(89.99, 90.01))                 # mark down: day PnL < -$1 stop
        self.assertTrue(st.stopped)
        self.assertIsNone(st.working[1])                        # no new longs
        self.assertIsNotNone(st.working[-1])                    # exit quote still live

    async def test_dead_feed_pulls_quotes_but_a_quiet_market_does_not(self):
        st = self.t.states["X-USD"]
        await self.t.on_bbo(bbo(99.99, 100.01))
        st.last_bbo_ns -= 60 * 10**9            # this market simply had no updates for a minute
        await self.t.quote(st)
        self.assertIsNotNone(st.working[1])      # quotes stay: the book just did not change
        self.t.last_msg_ns -= 10 * 10**9        # nothing at all on the socket for 10 s (limit 5 s)
        await self.t.quote(st)
        self.assertEqual((st.working[1], st.working[-1]), (None, None))

    async def test_shutdown_cancels_everything_and_disarms(self):
        await self.t.on_bbo(bbo(99.99, 100.01))
        await self.t.shutdown()
        kinds = [c[0] for c in self.rest.calls]
        self.assertIn("cancel_all", kinds)
        self.assertEqual(self.rest.calls[-1], ("dms", None))    # dead man's switch disarmed last

    async def test_dry_run_sends_nothing(self):
        t = LiveTrader(CFG, FakeRest(), FakeWs(), Path(self.tmp.name), dry_run=True)
        await t.start()
        t.running = True
        await t.on_bbo(bbo(99.99, 100.01))
        self.assertEqual([c for c in t.rest.calls if c[0] in ("place", "modify", "cancel")], [])
        self.assertIsNotNone(t.states["X-USD"].working[1])      # but it tracks what it would have placed

    async def test_fill_snapshot_shape_is_handled(self):
        await self.t.on_bbo(bbo(99.99, 100.01))
        await self.t.on_fill({"contents": "subscribed"})            # junk shapes must not crash
        await self.t.on_fill({"contents": [{"marketDisplayName": "X-USD"}]})
        await self.t.on_fill(fill("BUY", 100.0, 0.1, snapshot=True))  # snapshot: {"fills": [...]}
        self.assertAlmostEqual(self.t.states["X-USD"].pos, 0.1)

    async def test_quantities_are_exact_multiples_of_the_step(self):
        await self.t.on_bbo(bbo(402.41, 402.67))
        for c in [c for c in self.rest.calls if c[0] == "place"]:
            qty, step = c[3], float(META.stepSize)
            self.assertAlmostEqual(qty / step, round(qty / step), places=6, msg=f"{qty} off the step grid")

    async def test_reconcile_readopts_our_own_order_instead_of_cancelling(self):
        await self.t.on_bbo(bbo(99.99, 100.01))
        st = self.t.states["X-USD"]
        cid = st.working[1]["client_id"]
        st.working[1] = None                       # a failed modify lost the id, order still resting
        self.rest.open_orders = [{"orderId": "kept", "clientId": cid, "side": "BUY", "price": "99.90",
                                  "remainingSize": "0.25", "goodTilTime": "1"}]
        self.rest.calls.clear()
        await self.t.reconcile()
        self.assertEqual(st.working[1]["order_id"], "kept")
        self.assertNotIn("cancel", [c[0] for c in self.rest.calls])

    async def test_reconcile_adopts_venue_position_and_kills_strays(self):
        self.rest.positions = [{"marketDisplayName": "X-USD", "positionSide": "SHORT", "size": "0.4"}]
        self.rest.open_orders = [{"orderId": "ghost"}]
        await self.t.reconcile()
        self.assertAlmostEqual(self.t.states["X-USD"].pos, -0.4)
        self.assertIn(("cancel", "ghost"), self.rest.calls)


if __name__ == "__main__":
    unittest.main()
