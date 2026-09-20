from __future__ import annotations

"""Canonical Single-Path Historical Replay Loader for Arcus Perpetuals.
Fulfills Mandate v3 Section 9.1 & 9.7 (WS-D).

Turns raw, compressed, or normalized recorded files into a single strictly
time-ordered (recv_ts_ns) stream of SimEvent instances:
- BBO
- L2_DELTA
- TRADE
- FUNDING (with predicted vs realized distinction)
- ORACLE_MARK
- CLOCK_TICK (synthesizes ticks at <= 100ms when not present)
"""

import gzip
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("data_loader")


class SimEventType(str, Enum):
    BBO = "BBO"
    L2_DELTA = "L2_DELTA"
    TRADE = "TRADE"
    FUNDING = "FUNDING"
    ORACLE_MARK = "ORACLE_MARK"
    CLOCK_TICK = "CLOCK_TICK"


@dataclass
class SimEvent:
    event_type: SimEventType
    recv_ts_ns: int
    market: str
    data: Dict[str, Any]


def open_file_auto(path: Path):
    """Opens plain text or gzip compressed files seamlessly."""
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="ignore")
    return open(path, "r", encoding="utf-8", errors="ignore")


class CanonicalDataLoader:
    """Loads and merges multi-channel market recordings into a single sorted event stream."""

    def __init__(
        self,
        market: str,
        data_dir: Path,
        max_events: Optional[int] = None,
        synthesize_clock_ticks: bool = True,
        tick_interval_ns: int = 100_000_000,  # 100ms
    ):
        self.market = market
        self.data_dir = Path(data_dir)
        self.max_events = max_events
        self.synthesize_clock_ticks = synthesize_clock_ticks
        self.tick_interval_ns = tick_interval_ns

    def _parse_timestamp(self, raw_row: Dict[str, Any]) -> int:
        """Extracts nanosecond receive timestamp with robust fallbacks."""
        if "recv_ts_ns" in raw_row:
            return int(raw_row["recv_ts_ns"])
        if "timestamp" in raw_row:
            ts = int(raw_row["timestamp"])
            # If microseconds, convert to nanoseconds
            if ts < 10_000_000_000_000:
                return ts * 1_000
            return ts
        if "ts_ns" in raw_row:
            return int(raw_row["ts_ns"])
        contents = raw_row.get("contents") or raw_row.get("data", {}).get("contents")
        if isinstance(contents, dict) and "timestamp" in contents:
            return int(contents["timestamp"]) * 1_000
        return 0

    def load_events(self) -> List[SimEvent]:
        """Loads and returns all events sorted chronologically by recv_ts_ns."""
        events: List[Tuple[int, int, SimEvent]] = []  # (recv_ts_ns, file_order, SimEvent)
        counter = 0

        # Market directory (e.g. data/raw/2026-09-19/BTC-USD or session_dir)
        m_dir = self.data_dir if (self.data_dir / "bbo.jsonl").exists() or (self.data_dir / "raw_stream.jsonl").exists() else (self.data_dir / self.market)

        # 1. Check for single unified raw_stream.jsonl (from live paper session)
        raw_stream_f = m_dir / "raw_stream.jsonl"
        if not raw_stream_f.exists() and (self.data_dir / "raw_stream.jsonl").exists():
            raw_stream_f = self.data_dir / "raw_stream.jsonl"

        if raw_stream_f.exists():
            with open_file_auto(raw_stream_f) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue

                    # Filter by market if multi-market stream
                    ev_market = row.get("market") or self.market
                    if ev_market != self.market:
                        continue

                    ts_ns = self._parse_timestamp(row)
                    ev_type_str = row.get("event_type") or row.get("type", "").upper()
                    
                    if ev_type_str in SimEventType.__members__:
                        ev_type = SimEventType(ev_type_str)
                    elif "bbo" in ev_type_str.lower():
                        ev_type = SimEventType.BBO
                    elif "trade" in ev_type_str.lower():
                        ev_type = SimEventType.TRADE
                    elif "l2" in ev_type_str.lower():
                        ev_type = SimEventType.L2_DELTA
                    elif "funding" in ev_type_str.lower():
                        ev_type = SimEventType.FUNDING
                    elif "clock" in ev_type_str.lower():
                        ev_type = SimEventType.CLOCK_TICK
                    else:
                        continue

                    ev = SimEvent(event_type=ev_type, recv_ts_ns=ts_ns, market=ev_market, data=row.get("data") or row)
                    events.append((ts_ns, counter, ev))
                    counter += 1
                    if self.max_events and counter >= self.max_events:
                        break

            events.sort(key=lambda x: (x[0], x[1]))
            return [e[2] for e in events]

        # 2. Replay from per-channel files (bbo, trades, l2OrderbookUpdates, predictedFunding)
        channels = [
            ("bbo.jsonl", SimEventType.BBO),
            ("trades.jsonl", SimEventType.TRADE),
            ("l2OrderbookUpdates.jsonl", SimEventType.L2_DELTA),
            ("predictedFunding.jsonl", SimEventType.FUNDING),
        ]

        for fname, ev_type in channels:
            p = m_dir / fname
            if not p.exists():
                p_gz = m_dir / f"{fname}.gz"
                if p_gz.exists():
                    p = p_gz
                else:
                    continue

            with open_file_auto(p) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue

                    ts_ns = self._parse_timestamp(row)
                    data_payload = row.get("data") or row
                    # For funding, parse rate1h
                    if ev_type == SimEventType.FUNDING:
                        if "contents" in data_payload and isinstance(data_payload["contents"], dict):
                            rate1h = data_payload["contents"].get("rate1h") or data_payload["contents"].get("rate")
                            data_payload["rate1h"] = rate1h
                            data_payload["rate"] = rate1h
                        data_payload["is_settlement"] = False

                    ev = SimEvent(event_type=ev_type, recv_ts_ns=ts_ns, market=self.market, data=data_payload)
                    events.append((ts_ns, counter, ev))
                    counter += 1

        # Sort strictly by timestamp, with file insertion order tie-break
        events.sort(key=lambda x: (x[0], x[1]))

        if self.max_events:
            events = events[:self.max_events]

        sorted_events = [e[2] for e in events]

        # Synthesize clock ticks if requested and no clock ticks present
        if self.synthesize_clock_ticks and sorted_events:
            clock_events = self._synthesize_ticks(sorted_events)
            # Re-merge
            all_merged = []
            ev_idx = 0
            clk_idx = 0
            while ev_idx < len(sorted_events) and clk_idx < len(clock_events):
                if clock_events[clk_idx].recv_ts_ns <= sorted_events[ev_idx].recv_ts_ns:
                    all_merged.append(clock_events[clk_idx])
                    clk_idx += 1
                else:
                    all_merged.append(sorted_events[ev_idx])
                    ev_idx += 1
            all_merged.extend(clock_events[clk_idx:])
            all_merged.extend(sorted_events[ev_idx:])
            return all_merged

        return sorted_events

    def _synthesize_ticks(self, events: List[SimEvent]) -> List[SimEvent]:
        ticks = []
        if not events:
            return ticks

        start_ts = events[0].recv_ts_ns
        end_ts = events[-1].recv_ts_ns

        curr = start_ts + self.tick_interval_ns
        while curr < end_ts:
            ticks.append(SimEvent(
                event_type=SimEventType.CLOCK_TICK,
                recv_ts_ns=curr,
                market=self.market,
                data={"synthesized": True}
            ))
            curr += self.tick_interval_ns
        return ticks


def load_canonical_events(
    market: str,
    data_dir: Path,
    max_events: Optional[int] = None,
    synthesize_clock_ticks: bool = True,
) -> List[SimEvent]:
    loader = CanonicalDataLoader(
        market=market,
        data_dir=data_dir,
        max_events=max_events,
        synthesize_clock_ticks=synthesize_clock_ticks,
    )
    return loader.load_events()
