"""Probe script to stream live WebSocket frames from Arcus and inspect schemas."""

import asyncio
import json
import logging
from src.ws_client import ArcusWsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    client = ArcusWsClient()
    await client.connect()

    received = {}

    async def on_msg(channel: str, market: str, msg: dict):
        if channel not in received:
            received[channel] = msg
            print(f"\n--- Sample Message for channel: '{channel}' (Market: {market}) ---")
            print(json.dumps(msg, indent=2)[:500] + "...")

    markets = ["HYPE-USD", "NEAR-USD", "ZEC-USD"]
    channels = ["bbo", "trades", "l2OrderbookUpdates", "oraclePrices", "predictedFunding"]

    for market in markets:
        for ch in channels:
            async def cb(msg, ch=ch, m=market):
                await on_msg(ch, m, msg)

            extra = {"nLevels": 20} if ch == "l2OrderbookUpdates" else None
            await client.subscribe(ch, market, cb, extra_fields=extra)

    print("Subscribed. Listening for 5 seconds...")
    await asyncio.sleep(5.0)

    print(f"\nSummary: Received channels: {list(received.keys())}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
