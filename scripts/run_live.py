"""Run the live quoter. Dry run by default: it decides and logs, but sends no orders.

    .venv/bin/python scripts/run_live.py                      # dry run, no orders
    .venv/bin/python scripts/run_live.py --live               # sends real orders (guards must pass)

Live orders additionally require, in the environment:
    ARCUS_PAPER_TRADING_MODE=false
    ARCUS_MAINNET_ORDER_LOCK=false                 (mainnet only)
    ARCUS_MAINNET_MUTATING_CONFIRMATION=I_ACCEPT_PERMANENT_LOSS_OF_FUNDS   (mainnet only)
Stop it any time with Ctrl+C, or by creating a file named STOP in the log directory.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import signal
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import settings  # noqa: E402
from src.live.trader import LiveTrader  # noqa: E402
from src.rest_client import ArcusRestClient  # noqa: E402
from src.ws_client import ArcusWsClient  # noqa: E402


async def main_async(a):
    cfg = yaml.safe_load(Path(a.config).read_text())
    log_dir = Path(a.log_dir or ROOT / "data" / "live" / dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"))
    dry = not a.live
    print(f"environment={settings.environment}  dry_run={dry}  paper_mode={settings.paper_trading_mode}  "
          f"mainnet_lock={settings.mainnet_order_lock}\nmarkets={[m['market'] for m in cfg['markets']]}  "
          f"clip=${cfg['clip_usd']}  max_pos=${cfg['max_pos_usd']}  logs={log_dir}")
    if not dry and settings.paper_trading_mode:
        sys.exit("--live requires ARCUS_PAPER_TRADING_MODE=false (it would simulate silently otherwise)")
    async with ArcusRestClient() as rest:
        ws = ArcusWsClient()
        await ws.connect()
        trader = LiveTrader(cfg, rest, ws, log_dir=log_dir, dry_run=dry)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: setattr(trader, "running", False))
        if a.duration:
            loop.call_later(a.duration, lambda: setattr(trader, "running", False))
        try:
            await trader.run()
        finally:
            await ws.disconnect()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "live.yaml"))
    ap.add_argument("--live", action="store_true", help="actually send orders")
    ap.add_argument("--duration", type=float, default=0.0, help="stop after N seconds (0 = run until stopped)")
    ap.add_argument("--log-dir", default="")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(main_async(a))


if __name__ == "__main__":
    main()
