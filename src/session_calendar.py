"""Market Calendar and Regime Tagging Engine for Arcus Perpetuals.

Fulfills Mandate v2 Section 5.4 & closes Defect R-18:
- dow_class: weekend / weekday (UTC and exchange-local).
- session (UTC / EDT):
  - WEEKEND: Entire weekend periods (resolving R-18 mislabeling as US_LATE).
  - ASIA (00:00-07:00 UTC on weekdays)
  - EU/US-PRE (07:00-13:30 UTC on weekdays)
  - US-RTH (09:30-16:00 ET = 13:30-20:00 UTC on normal weekdays; closes 13:00 ET on early close days)
  - US-LATE (20:00-24:00 UTC on weekdays)
  Uses tz-aware zoneinfo.ZoneInfo("America/New_York") to avoid hardcoded DST offsets.
- underlying_open: per asset class from US equity calendar (crypto always open).
- Early closes modeled: 13:00 ET on 2026-07-02, 2026-11-27, 2026-12-24.
- Event windows: OPEN_30 (09:30-10:00 ET), CLOSE_30 (15:30-16:00 ET or 12:30-13:00 ET early close).
- MON_GAP: Sunday 20:00 UTC -> Monday 14:00 UTC. Sourced from CME Globex / Robinhood 24-Hour Market
  Sunday evening reopen and Asian cash gap risk (documented in configs/venue_verified.yaml).
"""

import datetime
from dataclasses import dataclass
from typing import Optional, Set, Dict
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
UTC_TZ = datetime.timezone.utc

# 2026 US Stock Market Holidays (NYSE / NASDAQ)
US_HOLIDAYS_2026: Set[datetime.date] = {
    datetime.date(2026, 1, 1),   # New Year's Day
    datetime.date(2026, 1, 19),  # Martin Luther King Jr. Day
    datetime.date(2026, 2, 16),  # Washington's Birthday / Presidents Day
    datetime.date(2026, 4, 3),   # Good Friday
    datetime.date(2026, 5, 25),  # Memorial Day
    datetime.date(2026, 6, 19),  # Juneteenth
    datetime.date(2026, 7, 3),   # Independence Day (Observed)
    datetime.date(2026, 9, 7),   # Labor Day
    datetime.date(2026, 11, 26), # Thanksgiving Day
    datetime.date(2026, 12, 25), # Christmas Day
}

# 2026 US Stock Market Scheduled Early Closes (13:00 ET / 1:00 PM)
US_EARLY_CLOSES_2026: Dict[datetime.date, datetime.time] = {
    datetime.date(2026, 7, 2): datetime.time(13, 0),   # Day before Independence Day observed
    datetime.date(2026, 11, 27): datetime.time(13, 0),  # Black Friday (day after Thanksgiving)
    datetime.date(2026, 12, 24): datetime.time(13, 0),  # Christmas Eve
}


@dataclass(frozen=True)
class MarketRegimeTag:
    """Regime annotations applied to every event and fill."""
    dow_class: str          # "WEEKEND" or "WEEKDAY"
    session: str            # "WEEKEND", "ASIA", "EU_US_PRE", "US_RTH", "US_LATE"
    underlying_open: bool   # True if underlying cash market is open
    event_window: Optional[str] = None  # "OPEN_30", "CLOSE_30", "MON_GAP", or None


def is_us_equity_holiday(d: datetime.date) -> bool:
    return d in US_HOLIDAYS_2026


def get_us_equity_close_time(d: datetime.date) -> datetime.time:
    """Returns scheduled regular market close time (13:00 ET on early close days, else 16:00 ET)."""
    return US_EARLY_CLOSES_2026.get(d, datetime.time(16, 0))


def classify_regime(ts_ns: int, asset_class: str = "crypto") -> MarketRegimeTag:
    """Classifies a timestamp (nanoseconds) into market regime tags."""
    dt_utc = datetime.datetime.fromtimestamp(ts_ns / 1e9, tz=UTC_TZ)
    dt_ny = dt_utc.astimezone(NY_TZ)

    # 1. Day-of-week classification
    is_weekend_utc = dt_utc.weekday() >= 5  # 5=Saturday, 6=Sunday
    is_weekend_ny = dt_ny.weekday() >= 5
    dow_class = "WEEKEND" if is_weekend_utc else "WEEKDAY"

    # 2. Session classification (UTC based, but aligned to NY ET for RTH)
    ny_time = dt_ny.time()
    ny_date = dt_ny.date()
    rth_start = datetime.time(9, 30)
    rth_end = get_us_equity_close_time(ny_date)

    if is_weekend_utc or is_weekend_ny:
        session = "WEEKEND"
    elif not is_us_equity_holiday(ny_date) and (rth_start <= ny_time < rth_end):
        session = "US_RTH"
    else:
        utc_hour = dt_utc.hour
        if 0 <= utc_hour < 7:
            session = "ASIA"
        elif 7 <= utc_hour < 13 or (utc_hour == 13 and dt_utc.minute < 30):
            session = "EU_US_PRE"
        else:
            session = "US_LATE"

    # 3. Underlying market open check
    norm_asset = asset_class.lower()
    if norm_asset in ("crypto", "digital"):
        underlying_open = True
    else:
        # Equities, commodities, ETFs, indices
        if is_weekend_ny or is_us_equity_holiday(ny_date):
            underlying_open = False
        else:
            underlying_open = (rth_start <= ny_time < rth_end)

    # 4. Event windows
    event_window = None

    if not is_weekend_ny and not is_us_equity_holiday(ny_date):
        open_30_end = datetime.time(10, 0)
        # Close 30 is 30 mins before rth_end
        close_30_start = datetime.time(rth_end.hour - 1, 30) if rth_end.minute == 0 else datetime.time(rth_end.hour, rth_end.minute - 30)

        if rth_start <= ny_time < open_30_end:
            event_window = "OPEN_30"
        elif close_30_start <= ny_time < rth_end:
            event_window = "CLOSE_30"

    # Monday Gap window: Sunday 20:00 UTC through Monday 14:00 UTC
    if event_window is None:
        if (dt_utc.weekday() == 6 and dt_utc.hour >= 20) or (dt_utc.weekday() == 0 and dt_utc.hour < 14):
            event_window = "MON_GAP"

    return MarketRegimeTag(
        dow_class=dow_class,
        session=session,
        underlying_open=underlying_open,
        event_window=event_window,
    )
