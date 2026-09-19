"""Command-line launcher for Arcus Market Data Recorder.

Fulfills Phase 14+ requirements from prompt.md:
- Records across ~20 market universe (Crypto candidates, controls, equities, commodities, indices).
- Multi-socket partitioning (<=50 subscriptions/socket).
- Heartbeat file at data/recorder_heartbeat.json.
- Hourly health integrity reports in reports/recorder_health/.
- Default duration is 0 (indefinite continuous run).

Usage:
  python3 scripts/run_recorder.py --duration 0
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.recorder import ArcusStreamRecorder

DEFAULT_MARKETS = [
    # Crypto candidates
    "HYPE-USD", "ZEC-USD", "NEAR-USD", "LIT-USD", "UNI-USD", "AAVE-USD", "CASHCAT-USD",
    # Crypto control
    "XRP-USD",
    # Mega-cap controls
    "BTC-USD", "ETH-USD", "SOL-USD",
    # Equity perps
    "SPCX-USD", "NVDA-USD", "TSLA-USD", "GOOGL-USD", "AMD-USD",
    # Commodities / indices
    "SLV-USD", "GLD-USD", "SPY-USD", "QQQ-USD",
]


def setup_logging(log_file: Path):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


async def main():
    parser = argparse.ArgumentParser(description="Run Arcus Market Data Recorder")
    parser.add_argument(
        "--markets",
        type=str,
        default=",".join(DEFAULT_MARKETS),
        help="Comma-separated list of markets to record",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=0.0,
        help="Recording duration in seconds (0 for indefinite multi-day recording)",
    )
    parser.add_argument(
        "--rotation-interval",
        type=float,
        default=23 * 3600.0,
        help="Scheduled socket rotation interval in seconds",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/raw",
        help="Directory to persist raw JSONL events",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="reports/recorder_health/recorder.log",
        help="Log file path",
    )
    args = parser.parse_args()

    setup_logging(Path(args.log_file))
    logger = logging.getLogger("recorder_cli")

    pid_file = Path("data/recorder.pid")
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()), encoding="utf-8")

    market_list = [m.strip() for m in args.markets.split(",") if m.strip()]
    logger.info(f"Configuring recorder for {len(market_list)} markets: {market_list}")

    recorder = ArcusStreamRecorder(
        markets=market_list,
        output_dir=args.output_dir,
        rotation_interval_secs=args.rotation_interval,
        markets_per_socket=10,
    )

    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received termination signal. Requesting stop...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    await recorder.start()

    try:
        if args.duration > 0:
            logger.info(f"Recording scheduled for {args.duration:.1f} seconds...")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=args.duration)
            except asyncio.TimeoutError:
                logger.info("Target duration elapsed.")
        else:
            logger.info("Recording running indefinitely (multi-day recording active).")
            await stop_event.wait()
    finally:
        await recorder.stop()
        metrics = recorder.metrics
        print("\n" + "=" * 60)
        print(" RECORDER RUN SUMMARY")
        print("=" * 60)
        for k, v in metrics.items():
            print(f" - {k:25s}: {v}")
        print("=" * 60)
        if pid_file.exists():
            pid_file.unlink()


if __name__ == "__main__":
    asyncio.run(main())
