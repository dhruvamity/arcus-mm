"""High-Resilience Public WebSocket Market Data Recorder for Arcus Perpetuals.

Fulfills Section 5 (Workstream 2) of prompt.md:
- Multi-socket pool management with deterministic subscription assignment (<=50 subs per socket).
- Scheduled socket rotation (<23h lifetime) with overlapping connections (15s overlap).
- Microsecond/nanosecond local receive timestamping (recv_ts_ns) alongside venue timestamps.
- Monotonic sequence tracking and deduplication with the Arcus splice rule.
- Raw immutable JSONL persistence partitioned by date, market, and channel.
- Hourly REST snapshots for /v1/markets and /v1/fundingRates.
- Continuous heartbeat logging (data/recorder_heartbeat.json) every 5 seconds.
- Hourly integrity report generation (reports/recorder_health/).
- Disk space monitoring with free-space alarm (<2GB).
"""

import asyncio
import datetime
import json
import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

from src.config import ArcusConfig, settings
from src.ws_client import ArcusWsClient
from src.rest_client import ArcusRestClient
from src.utils import now_ns

logger = logging.getLogger(__name__)


class ArcusStreamRecorder:
    """Records high-frequency streaming market data across multiple candidate markets."""

    def __init__(
        self,
        markets: List[str],
        channels: Optional[List[str]] = None,
        output_dir: str = "data/raw",
        rotation_interval_secs: float = 23 * 3600.0,  # 23 hours default rotation
        overlap_secs: float = 15.0,  # 15 seconds overlap during socket rotation
        flush_interval_secs: float = 1.0,
        markets_per_socket: int = 10,  # Max 10 markets (50 subscriptions) per socket
        snapshot_interval_secs: float = 3600.0,  # 1 hour REST snapshotting
        health_interval_secs: float = 3600.0,  # 1 hour integrity reports
        config: Optional[ArcusConfig] = None,
    ):
        self.markets = markets
        self.channels = channels or [
            "bbo",
            "trades",
            "l2OrderbookUpdates",
            "predictedFunding",
            "oraclePrices",
        ]
        self.output_dir = Path(output_dir)
        self.rotation_interval_secs = rotation_interval_secs
        self.overlap_secs = overlap_secs
        self.flush_interval_secs = flush_interval_secs
        self.markets_per_socket = markets_per_socket
        self.snapshot_interval_secs = snapshot_interval_secs
        self.health_interval_secs = health_interval_secs
        self.config = config or settings

        self._start_time = time.time()
        self._running = False
        self._write_queues: Dict[str, asyncio.Queue] = {}
        self._file_handles: Dict[str, Any] = {}

        # Tasks
        self._flush_task: Optional[asyncio.Task] = None
        self._rotation_tasks: List[asyncio.Task] = []
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._snapshot_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None

        # Socket pools: pool_idx -> dict of active sessions: session_id -> ArcusWsClient
        self._pools: Dict[int, Dict[str, ArcusWsClient]] = {}
        self._pool_markets: Dict[int, List[str]] = {}

        # Deduplication cache: (channel, market, dedup_key) -> seen_timestamp
        self._seen_keys: Set[str] = set()
        self._seen_keys_order: List[str] = []
        self._max_seen_cache: int = 100_000

        # Sequence tracking & book validity: (market, channel) -> state
        self._last_sequences: Dict[str, int] = {}
        self._first_delta_received: Dict[str, bool] = {}
        self._book_valid: Dict[str, bool] = {}
        self._invalid_intervals: List[Dict[str, Any]] = []

        # Hourly market/channel message counters for integrity reports
        self._hourly_message_counts: Dict[str, Dict[str, int]] = {
            m: {c: 0 for c in self.channels} for m in self.markets
        }

        self._metrics = {
            "messages_recorded": 0,
            "bytes_recorded": 0,
            "trades_recorded": 0,
            "book_updates_recorded": 0,
            "bbo_updates_recorded": 0,
            "duplicates_dropped": 0,
            "sequence_gaps": 0,
            "rotations_completed": 0,
            "rest_snapshots_saved": 0,
            "reconnects": 0,
        }

    @property
    def metrics(self) -> Dict[str, Any]:
        res = dict(self._metrics)
        res["uptime_secs"] = round(time.time() - self._start_time, 2)
        res["active_sockets"] = sum(len(pool) for pool in self._pools.values())
        return res

    def _get_channel_file_key(self, market: str, channel: str) -> str:
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        return f"{date_str}/{market}/{channel}"

    def _get_or_open_file(self, file_key: str):
        if file_key in self._file_handles:
            return self._file_handles[file_key]

        full_path = self.output_dir / f"{file_key}.jsonl"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(full_path, "a", encoding="utf-8")
        self._file_handles[file_key] = handle
        return handle

    async def _flush_loop(self) -> None:
        """Asynchronous disk writer worker flushing message queues."""
        while self._running or any(not q.empty() for q in self._write_queues.values()):
            for file_key, queue in list(self._write_queues.items()):
                lines = []
                while not queue.empty() and len(lines) < 2000:
                    try:
                        record = queue.get_nowait()
                        lines.append(json.dumps(record, separators=(",", ":")) + "\n")
                    except asyncio.QueueEmpty:
                        break

                if lines:
                    f = self._get_or_open_file(file_key)
                    f.writelines(lines)
                    f.flush()
                    total_bytes = sum(len(line) for line in lines)
                    self._metrics["bytes_recorded"] += total_bytes

            await asyncio.sleep(self.flush_interval_secs)

    def _is_seen_trade(self, market: str, tr: Dict[str, Any]) -> bool:
        """Deduplicates every trade in a multi-trade frame by strongest available identifier.

        Fulfills Mandate Section 25:
        - Deduplicate every trade event individually (never just the first).
        - Key on tradeId, or composite (sequenceNumber, timestamp, price, size).
        """
        t_id = tr.get("tradeId")
        if not t_id:
            seq = tr.get("sequenceNumber", "")
            ts = tr.get("timestamp", "")
            p = tr.get("price", "")
            s = tr.get("size", "")
            t_id = f"{seq}_{ts}_{p}_{s}"

        dedup_key = f"trade:{market}:{t_id}"
        if dedup_key in self._seen_keys:
            return True
        self._seen_keys.add(dedup_key)
        self._seen_keys_order.append(dedup_key)
        if len(self._seen_keys_order) > self._max_seen_cache:
            evict = self._seen_keys_order.pop(0)
            self._seen_keys.discard(evict)
        return False

    def _is_duplicate_or_update_sequence(
        self, channel: str, market: str, msg_type: str, contents: Any, session_id: str, recv_ts: int
    ) -> bool:
        """Checks for duplicate trades or out-of-order sequence frames using the Arcus splice rule."""
        if channel in ("l2OrderbookUpdates", "bbo"):
            if isinstance(contents, dict):
                seq_id = contents.get("lastSequenceId") or contents.get("globalSequenceId")
                if seq_id is not None:
                    key = f"{market}:{channel}"
                    if msg_type == "subscribed":
                        self._last_sequences[key] = seq_id
                        self._first_delta_received[key] = False
                        self._book_valid[key] = True
                        return False

                    last_seq = self._last_sequences.get(key)
                    if last_seq is not None and seq_id <= last_seq:
                        return True

                    if channel == "l2OrderbookUpdates":
                        if not self._first_delta_received.get(key, False):
                            # First delta after snapshot: allow boundary sequence offset per Arcus splice rule
                            self._first_delta_received[key] = True
                        elif last_seq is not None and seq_id > last_seq + 1:
                            # Mandate §24: Genuine mid-stream gap detected!
                            self._metrics["sequence_gaps"] += 1
                            self._book_valid[key] = False
                            gap_info = {
                                "market": market,
                                "channel": channel,
                                "expected_seq": last_seq + 1,
                                "received_seq": seq_id,
                                "gap_size": seq_id - (last_seq + 1),
                                "ts_ns": recv_ts,
                            }
                            self._invalid_intervals.append(gap_info)
                            logger.error(
                                f"[{market}] Sequence gap in {channel}: expected {last_seq + 1}, got {seq_id}. "
                                f"Marking book INVALID and emitting INVALID_BOOK_INTERVAL."
                            )
                            # Queue INVALID_BOOK_INTERVAL marker so persistence records it
                            file_key = self._get_channel_file_key(market, channel)
                            if file_key not in self._write_queues:
                                self._write_queues[file_key] = asyncio.Queue()
                            self._write_queues[file_key].put_nowait({
                                "session_id": session_id,
                                "recv_ts_ns": recv_ts,
                                "market": market,
                                "channel": channel,
                                "type": "INVALID_BOOK_INTERVAL",
                                "gap_info": gap_info,
                            })

                    self._last_sequences[key] = seq_id
        return False

    def _handle_message(
        self,
        session_id: str,
        channel: str,
        market: str,
        raw_msg: Dict[str, Any],
    ) -> None:
        """Processes and queues raw streaming message with frame-wide dedup and gap marking."""
        recv_ts = now_ns()
        msg_type = raw_msg.get("type")
        contents = raw_msg.get("contents")

        # Mandate §25: Multi-trade frame deduplication
        if channel == "trades" and isinstance(contents, list):
            new_trades = [tr for tr in contents if not self._is_seen_trade(market, tr)]
            if not new_trades:
                self._metrics["duplicates_dropped"] += 1
                return
            raw_msg["contents"] = new_trades
        else:
            if self._is_duplicate_or_update_sequence(channel, market, msg_type or "", contents, session_id, recv_ts):
                self._metrics["duplicates_dropped"] += 1
                return

        file_key = self._get_channel_file_key(market, channel)
        if file_key not in self._write_queues:
            self._write_queues[file_key] = asyncio.Queue()

        record = {
            "session_id": session_id,
            "recv_ts_ns": recv_ts,
            "market": market,
            "channel": channel,
            "type": msg_type,
            "data": raw_msg,
        }

        self._write_queues[file_key].put_nowait(record)
        self._metrics["messages_recorded"] += 1

        if market in self._hourly_message_counts and channel in self._hourly_message_counts[market]:
            self._hourly_message_counts[market][channel] += 1

        if channel == "trades":
            if isinstance(contents, list):
                self._metrics["trades_recorded"] += len(contents)
        elif channel == "l2OrderbookUpdates":
            self._metrics["book_updates_recorded"] += 1
        elif channel == "bbo":
            self._metrics["bbo_updates_recorded"] += 1

    async def _spawn_socket_session(
        self, pool_idx: int, session_id: str, pool_markets: List[str]
    ) -> ArcusWsClient:
        """Spawns an active WebSocket connection and registers subscriptions for a market pool."""
        logger.info(
            f"Pool {pool_idx}: Initializing socket session [{session_id}] for {len(pool_markets)} markets..."
        )
        client = ArcusWsClient(config=self.config)
        await client.connect()

        for market in pool_markets:
            for ch in self.channels:
                def make_callback(c=ch, m=market, sid=session_id):
                    async def cb(msg: Dict[str, Any]):
                        self._handle_message(sid, c, m, msg)
                    return cb

                extra = {"nLevels": 50} if ch == "l2OrderbookUpdates" else None
                await client.subscribe(ch, market, make_callback(), extra_fields=extra)

        if pool_idx not in self._pools:
            self._pools[pool_idx] = {}
        self._pools[pool_idx][session_id] = client
        logger.info(
            f"Pool {pool_idx}: Socket session [{session_id}] subscribed to {len(pool_markets) * len(self.channels)} channels."
        )
        return client

    async def _pool_rotation_loop(self, pool_idx: int, pool_markets: List[str]) -> None:
        """Executes scheduled socket rotation with overlapping continuity for one market pool."""
        session_counter = 1
        while self._running:
            await asyncio.sleep(self.rotation_interval_secs)
            if not self._running:
                break

            session_counter += 1
            new_session_id = f"pool_{pool_idx}_sess_{session_counter}_{uuid.uuid4().hex[:6]}"
            logger.info(
                f"Pool {pool_idx}: Initiating scheduled rotation. Spawning replacement [{new_session_id}]..."
            )

            try:
                # 1. Connect new socket and establish subscriptions
                new_client = await self._spawn_socket_session(pool_idx, new_session_id, pool_markets)

                # 2. Overlap period: keep old socket open while new starts receiving
                logger.info(f"Pool {pool_idx}: Overlapping rotation active for {self.overlap_secs}s...")
                await asyncio.sleep(self.overlap_secs)

                # 3. Gracefully tear down older sockets for this pool
                old_session_ids = [
                    sid for sid in list(self._pools.get(pool_idx, {}).keys()) if sid != new_session_id
                ]
                for old_sid in old_session_ids:
                    logger.info(f"Pool {pool_idx}: Retiring old session [{old_sid}]...")
                    old_client = self._pools[pool_idx].pop(old_sid, None)
                    if old_client:
                        await old_client.disconnect()

                self._metrics["rotations_completed"] += 1
                logger.info(f"Pool {pool_idx}: Rotation completed. Active session [{new_session_id}].")
            except Exception as e:
                logger.error(f"Pool {pool_idx}: Error during socket rotation: {e}", exc_info=True)

    async def _heartbeat_loop(self) -> None:
        """Writes heartbeat file every 5 seconds for watchdog monitoring."""
        heartbeat_file = Path("data/recorder_heartbeat.json")
        heartbeat_file.parent.mkdir(parents=True, exist_ok=True)

        while self._running:
            try:
                total, used, free = shutil.disk_usage(self.output_dir.resolve().parent)
                free_gb = free / (1024 ** 3)
                if free_gb < 2.0:
                    logger.error(f"CRITICAL DISK ALARM: Free disk space is only {free_gb:.2f} GB!")

                heartbeat_data = {
                    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "pid": os.getpid(),
                    "uptime_secs": round(time.time() - self._start_time, 2),
                    "markets_count": len(self.markets),
                    "active_pools": len(self._pools),
                    "active_sockets": sum(len(p) for p in self._pools.values()),
                    "disk_free_gb": round(free_gb, 2),
                    "metrics": self.metrics,
                }
                heartbeat_file.write_text(json.dumps(heartbeat_data, indent=2), encoding="utf-8")
            except Exception as err:
                logger.warning(f"Error writing heartbeat: {err}")

            await asyncio.sleep(5.0)

    async def _snapshot_loop(self) -> None:
        """Periodically snapshots REST /v1/markets and /v1/fundingRates."""
        client = ArcusRestClient(config=self.config)
        while self._running:
            try:
                now = datetime.datetime.now(datetime.timezone.utc)
                date_str = now.strftime("%Y-%m-%d")
                ts_str = now.strftime("%Y%m%d_%H%M%S")
                snap_dir = self.output_dir / f"{date_str}/rest_snapshots"
                snap_dir.mkdir(parents=True, exist_ok=True)

                markets_res = await client._request("GET", "/v1/markets", "markets")
                funding_all = {}
                for m in self.markets:
                    try:
                        rates = await client.get_funding_rates(market=m)
                        funding_all[m] = rates
                    except Exception as fe:
                        logger.debug(f"Failed to fetch funding rate for {m}: {fe}")

                (snap_dir / f"markets_{ts_str}.json").write_text(
                    json.dumps(markets_res, separators=(",", ":")), encoding="utf-8"
                )
                (snap_dir / f"funding_{ts_str}.json").write_text(
                    json.dumps(funding_all, separators=(",", ":")), encoding="utf-8"
                )
                self._metrics["rest_snapshots_saved"] += 1
                logger.info(f"Saved hourly REST snapshot at {ts_str} for {len(self.markets)} markets")
            except Exception as e:
                logger.warning(f"Failed to fetch REST snapshot: {e}")

            await asyncio.sleep(self.snapshot_interval_secs)

    async def _health_report_loop(self) -> None:
        """Periodically writes hourly integrity reports to reports/recorder_health/."""
        health_dir = Path("reports/recorder_health")
        health_dir.mkdir(parents=True, exist_ok=True)

        while self._running:
            await asyncio.sleep(self.health_interval_secs)
            if not self._running:
                break

            try:
                now = datetime.datetime.now(datetime.timezone.utc)
                date_hour_str = now.strftime("%Y%m%d_%H00")
                report_file = health_dir / f"health_{date_hour_str}.json"

                total, used, free = shutil.disk_usage(self.output_dir.resolve().parent)
                free_gb = free / (1024 ** 3)

                report_data = {
                    "report_timestamp_utc": now.isoformat(),
                    "uptime_hours": round((time.time() - self._start_time) / 3600.0, 2),
                    "disk_free_gb": round(free_gb, 2),
                    "overall_metrics": self.metrics,
                    "hourly_message_counts": self._hourly_message_counts,
                }
                report_file.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

                # Generate updated summary markdown
                md_lines = [
                    "# Multi-Day Recorder Health & Integrity Dashboard",
                    "",
                    f"**Last Updated:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}  ",
                    f"**Recorder Uptime:** {(time.time() - self._start_time) / 3600.0:.2f} hours  ",
                    f"**Disk Free:** {free_gb:.2f} GB  ",
                    f"**Total Messages Recorded:** {self._metrics['messages_recorded']:,}  ",
                    f"**Total Bytes Recorded:** {self._metrics['bytes_recorded'] / 1e6:.2f} MB  ",
                    f"**Mid-Stream Sequence Gaps:** {self._metrics['sequence_gaps']}  ",
                    f"**Duplicates Dropped:** {self._metrics['duplicates_dropped']}  ",
                    "",
                    "## Market Activity in Current Window",
                    "",
                    "| Market | BBO Messages | Trades | L2 Updates | Funding | Oracle | Total |",
                    "|---|---|---|---|---|---|---|",
                ]

                for m in sorted(self.markets):
                    counts = self._hourly_message_counts.get(m, {})
                    bbo = counts.get("bbo", 0)
                    trades = counts.get("trades", 0)
                    l2 = counts.get("l2OrderbookUpdates", 0)
                    fund = counts.get("predictedFunding", 0)
                    oracle = counts.get("oraclePrices", 0)
                    tot = bbo + trades + l2 + fund + oracle
                    md_lines.append(f"| **{m}** | {bbo:,} | {trades:,} | {l2:,} | {fund:,} | {oracle:,} | **{tot:,}** |")

                (health_dir / "latest_health.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
                logger.info(f"Generated hourly integrity report: {report_file}")

                # Reset hourly counters
                self._hourly_message_counts = {m: {c: 0 for c in self.channels} for m in self.markets}
            except Exception as e:
                logger.error(f"Error generating health report: {e}", exc_info=True)

    async def start(self) -> None:
        """Starts the multi-socket market data recorder."""
        self._running = True
        logger.info(
            f"Starting ArcusStreamRecorder across {len(self.markets)} markets: {self.markets}"
        )
        self._flush_task = asyncio.create_task(self._flush_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        self._health_task = asyncio.create_task(self._health_report_loop())

        # Partition markets into socket pools of <= markets_per_socket
        num_pools = (len(self.markets) + self.markets_per_socket - 1) // self.markets_per_socket
        for p_idx in range(num_pools):
            sub_markets = self.markets[p_idx * self.markets_per_socket : (p_idx + 1) * self.markets_per_socket]
            self._pool_markets[p_idx] = sub_markets
            initial_sid = f"pool_{p_idx}_sess_1_{uuid.uuid4().hex[:6]}"
            await self._spawn_socket_session(p_idx, initial_sid, sub_markets)

            # Start rotation monitor for this pool
            rot_task = asyncio.create_task(self._pool_rotation_loop(p_idx, sub_markets))
            self._rotation_tasks.append(rot_task)

    async def stop(self) -> None:
        """Stops the recorder, drains queues, and closes file handles."""
        logger.info("Stopping ArcusStreamRecorder...")
        self._running = False

        for rot_task in self._rotation_tasks:
            rot_task.cancel()
            try:
                await rot_task
            except asyncio.CancelledError:
                pass
        self._rotation_tasks.clear()

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._snapshot_task:
            self._snapshot_task.cancel()
        if self._health_task:
            self._health_task.cancel()

        # Disconnect all active sockets across all pools
        for pool_idx, pool in self._pools.items():
            for sid, client in list(pool.items()):
                await client.disconnect()
            pool.clear()
        self._pools.clear()

        # Wait for disk queues to drain
        if self._flush_task:
            await self._flush_task

        # Close open file handles
        for handle in self._file_handles.values():
            handle.flush()
            handle.close()
        self._file_handles.clear()

        logger.info(f"ArcusStreamRecorder stopped. Final metrics: {self.metrics}")
