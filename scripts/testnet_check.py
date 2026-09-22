"""End-to-end order-path check on Arcus testnet: place -> read -> modify -> cancel -> dead man's switch.

Orders are placed far from the market (default 20% away) and post-only, so they rest untouched
and are cancelled again; on an unfunded account the venue rejects them, which still proves the
signing path. Never runs against mainnet.

    ARCUS_ENVIRONMENT=testnet ARCUS_PAPER_TRADING_MODE=false \
        .venv/bin/python scripts/testnet_check.py --market BTC-USD
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import ArcusConfig  # noqa: E402
from src.models.core import OrderRequest, OrderSide, TimeInForce  # noqa: E402
from src.quoting import round_to_tick  # noqa: E402
from src.rest_client import ArcusRestClient  # noqa: E402


def show(step, ok, detail=""):
    print(f"[{'ok ' if ok else 'FAIL'}] {step}{(': ' + str(detail)[:300]) if detail else ''}", flush=True)
    return ok


async def main_async(a):
    cfg = ArcusConfig()
    if cfg.environment != "testnet":
        sys.exit("refusing to run: ARCUS_ENVIRONMENT must be 'testnet'")
    if cfg.paper_trading_mode:
        sys.exit("set ARCUS_PAPER_TRADING_MODE=false, otherwise every call is simulated locally")
    results = []
    async with ArcusRestClient(config=cfg) as r:
        results.append(show("health", (await r.get_health()).get("status") == "ok"))
        meta = {m.marketDisplayName: m for m in await r.get_markets()}[a.market]
        bbo = await r.get_bbo(a.market)
        mid = (float(bbo.bidPrice) + float(bbo.askPrice)) / 2
        tick = float(meta.tickSize)
        px = round_to_tick(mid * (1 - a.away_pct / 100), tick, up=False)
        qty = max(float(meta.minOrderSize or 0), float(meta.minOrderNotional or 5) / px)
        step = float(meta.stepSize)
        qty = max(1, -(-qty // step)) * step        # round the size up onto the step grid
        print(f"{a.market}: mid {mid:.4f}, resting BUY {qty} @ {px} ({a.away_pct:g}% below)")

        try:
            funded = await r.get_account()
            print(f"account equity: {funded.get('equity')}, free collateral: {funded.get('freeCollateral')}")
        except Exception as e:
            print(f"account: {e}")
            print("-> unfunded: orders will be rejected as UNDERCOLLATERALIZED, which still tests signing")

        order_id = None
        try:
            res = await r.place_order(OrderRequest(
                marketId=meta.marketId, side=OrderSide.BUY, price=Decimal(str(px)), quantity=Decimal(str(qty)),
                timeInForce=TimeInForce.ALO), meta)
            order_id = res.orderId
            results.append(show("placeOrder signed and accepted", str(res.status).upper() in ("ACK", "PLACED", "OPEN"),
                                f"status={res.status} id={order_id} rateLimit={res.rateLimit}"))
        except Exception as e:
            ok = "UNDERCOLLATERALIZED" in str(e).upper()
            results.append(show("placeOrder signed (rejected for funds only)" if ok else "placeOrder", ok, e))

        if order_id:
            opens = await r.get_open_orders(market_id=meta.marketId)
            results.append(show("openOrders shows it", any(str(o.get("orderId")) == str(order_id) for o in opens),
                                f"{len(opens)} open"))
            try:
                m = await r.modify_order(market_id=meta.marketId, order_id=order_id,
                                         price=Decimal(str(round_to_tick(px * 0.999, tick, up=False))),
                                         quantity=Decimal(str(qty)), side=OrderSide.BUY, market=meta)
                order_id = m.orderId or order_id
                results.append(show("modifyOrder", str(m.status).upper() in ("ACK", "PLACED", "OPEN"), m.status))
            except Exception as e:
                results.append(show("modifyOrder", False, e))
            try:
                c = await r.cancel_order(market_id=meta.marketId, order_id=order_id)
                results.append(show("cancelOrder", True, c.status))
            except Exception as e:
                results.append(show("cancelOrder", False, e))

        try:
            import time
            await r.schedule_cancel(int((time.time() + 60) * 1e6))
            await r.schedule_cancel(None)
            results.append(show("scheduleCancel arm + disarm (dead man's switch)", True))
        except Exception as e:
            results.append(show("scheduleCancel", False, e))

        try:
            await r.cancel_all_orders(market_id=meta.marketId)
            results.append(show("cancelAllOrders", True))
        except Exception as e:
            results.append(show("cancelAllOrders", False, e))

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="BTC-USD")
    ap.add_argument("--away-pct", type=float, default=20.0, help="how far below mid to rest the test order")
    sys.exit(asyncio.run(main_async(ap.parse_args())))


if __name__ == "__main__":
    main()
