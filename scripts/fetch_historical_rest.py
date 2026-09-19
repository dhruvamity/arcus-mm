"""Fetches historical trades, funding rates, and candles via Arcus REST API.

Enriches the normalized dataset with historical trade series to power
Phase 4 (Market Characterization), Phase 6 (Adverse Selection Study),
and Phase 7 (Backtester calibration).
"""

import asyncio
import datetime
import json
import logging
from pathlib import Path
import pandas as pd

from src.rest_client import ArcusRestClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("hist_fetcher")


async def main():
    client = ArcusRestClient()
    markets = ["HYPE-USD", "ZEC-USD", "NEAR-USD", "SPCX-USD", "LIT-USD", "UNI-USD", "SLV-USD"]
    date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    for m in markets:
        out_dir = Path(f"data/normalized/{date_str}/{m}")
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. Fetch Trades
        try:
            trades = await client.get_trades(m, limit=200)
            logger.info(f"[{m}] Fetched {len(trades)} historical trades from REST")
            if trades:
                rows = []
                for t in trades:
                    price = float(t.get("price", 0.0))
                    size = float(t.get("size", 0.0))
                    ts_us = t.get("timestamp") or 0
                    ts_ns = int(ts_us * 1000)
                    rows.append({
                        "recv_ts_ns": ts_ns,
                        "exch_ts_ns": ts_ns,
                        "market": m,
                        "side": t.get("side", "").upper(),
                        "price": price,
                        "size": size,
                        "notional": price * size,
                        "trade_id": str(t.get("tradeId", "")),
                        "sequence_number": t.get("sequenceNumber", 0),
                        "maker_order_id": str(t.get("makerOrderId", "")),
                        "taker_order_id": str(t.get("takerOrderId", "")),
                        "session_id": "rest_historical",
                    })

                df_new = pd.DataFrame(rows)
                parquet_path = out_dir / "trades.parquet"
                if parquet_path.exists():
                    df_existing = pd.read_parquet(parquet_path)
                    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                    df_combined.drop_duplicates(subset=["trade_id"], inplace=True)
                    df_combined.sort_values(by="recv_ts_ns", inplace=True)
                    df_combined.to_parquet(parquet_path, index=False)
                else:
                    df_new.sort_values(by="recv_ts_ns", inplace=True)
                    df_new.to_parquet(parquet_path, index=False)
        except Exception as e:
            logger.warning(f"[{m}] Error fetching REST trades: {e}")

        # 2. Fetch Funding Rates
        try:
            funding = await client.get_funding_rates(market=m)
            if funding:
                funding_path = out_dir / "funding.json"
                with open(funding_path, "w", encoding="utf-8") as f:
                    json.dump(funding, f, indent=2)
                logger.info(f"[{m}] Saved funding rate history")
        except Exception as e:
            logger.warning(f"[{m}] Error fetching funding rates: {e}")

    logger.info("Historical data enrichment complete.")


if __name__ == "__main__":
    asyncio.run(main())
