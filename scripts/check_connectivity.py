#!/usr/bin/env python3
"""Arcus Connectivity Diagnostic Tool.

Validates REST and WebSocket connectivity against Arcus (testnet or mainnet).
Tests public endpoints immediately without credentials, and tests authenticated
endpoints if credentials are configured in .env.
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.rest_client import ArcusRestClient
from src.ws_client import ArcusWsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("connectivity_check")


async def check_public_rest(client: ArcusRestClient) -> bool:
    print("\n--- 1. Testing Public REST Endpoints ---")
    try:
        # Check health
        health = await client.get_health()
        print(f"✅ GET /v1/health: OK (response: {health})")

        # Check time
        server_time_ns = await client.get_server_time()
        local_time_ns = time.time_ns()
        skew_ms = abs(local_time_ns - server_time_ns) / 1_000_000
        print(f"✅ GET /v1/time: OK (Server time: {server_time_ns}, Skew: {skew_ms:.2f} ms)")

        # Check markets
        markets = await client.get_markets()
        print(f"✅ GET /v1/markets: Found {len(markets)} active perpetual markets")
        if markets:
            btc_mkt = next((m for m in markets if m.marketDisplayName == "BTC-USD"), markets[0])
            print(
                f"   Sample Market [{btc_mkt.marketDisplayName}] ID={btc_mkt.marketId}, "
                f"TickSize={btc_mkt.tickSize}, StepSize={btc_mkt.stepSize}, Status={btc_mkt.status}"
            )

        # Check BBO
        bbo = await client.get_bbo("BTC-USD")
        if isinstance(bbo, list):
            bbo = bbo[0] if bbo else None
        if bbo and bbo.bidPrice and bbo.askPrice:
            print(
                f"✅ GET /v1/bbo (BTC-USD): Bid={bbo.bidPrice} (size: {bbo.bidSize}) | "
                f"Ask={bbo.askPrice} (size: {bbo.askSize}) | Spread={bbo.spread}"
            )
        else:
            print("⚠️ GET /v1/bbo returned empty or partial BBO")

        return True
    except Exception as e:
        print(f"❌ Public REST failed: {e}")
        return False


async def check_public_ws(ws_client: ArcusWsClient) -> bool:
    print("\n--- 2. Testing Public WebSocket Feeds ---")
    received_messages = []

    async def on_bbo_message(msg):
        received_messages.append(msg)

    try:
        await ws_client.connect()
        print(f"✅ WebSocket connected to {ws_client.ws_url}")

        sub_id = "BTC-USD"
        await ws_client.subscribe("bbo", sub_id, callback=on_bbo_message)
        print(f"   Subscribed to 'bbo' channel for {sub_id}. Listening for initial snapshot/update...")

        # Wait up to 4 seconds for a message
        start = time.monotonic()
        while time.monotonic() - start < 4.0:
            if received_messages:
                break
            await asyncio.sleep(0.2)

        if received_messages:
            sample = received_messages[0]
            contents = sample.get("contents", {})
            print(f"✅ Streamed WebSocket message received on channel '{sample.get('channel')}'!")
            print(f"   Message type: {sample.get('type')}, ID: {sample.get('id')}")
            if "bestBid" in contents and "bestAsk" in contents:
                bb = contents.get("bestBid") or {}
                ba = contents.get("bestAsk") or {}
                print(f"   Top-of-Book from WS: Bid={bb.get('price')} | Ask={ba.get('price')}")
        else:
            print("⚠️ No BBO message arrived during observation window.")

        await ws_client.unsubscribe("bbo", sub_id)
        await ws_client.disconnect()
        return True
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        try:
            await ws_client.disconnect()
        except Exception:
            pass
        return False


async def check_authenticated_rest(client: ArcusRestClient) -> bool:
    print("\n--- 3. Testing Authenticated REST Endpoints ---")
    if not settings.has_credentials:
        print("ℹ️ No valid credentials found in .env (or dummy values present).")
        print("   Skipping authenticated tests until credentials are provided.")
        return True

    try:
        # Check Rate Limits
        print(f"   Querying rate limits for: {settings.wallet_address} (accountIndex: {settings.account_index})")
        rl = await client.get_rate_limit()
        print(
            f"✅ GET /v1/rateLimit: Order pool cap={rl.get('order', {}).get('cap')}, "
            f"Cancel pool cap={rl.get('cancel', {}).get('cap')}"
        )

        # Check API Keys registration
        api_keys_res = await client._request("GET", f"/v1/apiKeys?address={settings.wallet_address}", "apiKeys")
        registered_keys = api_keys_res.get("apiKeys", [])
        matching_key = next((k for k in registered_keys if k.get("apiKey") == settings.api_key), None)
        if matching_key:
            print(f"✅ GET /v1/apiKeys: API key verified & ACTIVE on venue (name: {matching_key.get('apiWalletName')})")
        else:
            print(f"⚠️ GET /v1/apiKeys: Key {settings.api_key[:8]}... not found among registered keys")

        # Check Account
        print(f"   Querying account for wallet: {settings.wallet_address}")
        try:
            account = await client.get_account()
            print(f"✅ GET /v1/account: Equity={account.get('equity')}, FreeCollateral={account.get('freeCollateral')}")
        except RuntimeError as err:
            if "no activity yet" in str(err):
                print("ℹ️ GET /v1/account: Account has no deposit/activity yet (Balance: $0.00)")
            else:
                raise err

        return True
    except Exception as e:
        print(f"❌ Authenticated REST check failed: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Arcus connectivity check")
    parser.add_argument("--public-only", action="store_true", help="Run only public checks")
    args = parser.parse_args()

    print("=" * 70)
    print(f" Arcus Connectivity Diagnostic (Environment: {settings.environment.upper()})")
    print(f" REST Target: {settings.rest_url}")
    print(f" WS Target:   {settings.ws_url}")
    print("=" * 70)

    async with ArcusRestClient() as rest_client:
        public_rest_ok = await check_public_rest(rest_client)

        ws_client = ArcusWsClient()
        public_ws_ok = await check_public_ws(ws_client)

        auth_ok = True
        if not args.public_only:
            auth_ok = await check_authenticated_rest(rest_client)

    print("\n" + "=" * 70)
    print(" SUMMARY")
    print(f" - Public REST:      {'PASS' if public_rest_ok else 'FAIL'}")
    print(f" - Public WebSocket: {'PASS' if public_ws_ok else 'FAIL'}")
    print(f" - Authenticated:    {'PASS / SKIPPED' if auth_ok else 'FAIL'}")
    print("=" * 70)

    if public_rest_ok and public_ws_ok and auth_ok:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
