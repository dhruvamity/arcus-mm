"""Unit Tests for Market Calendar, Regime Tagging, and Early Closes (R-18).

Verifies:
- Weekend midday is labeled 'WEEKEND', not 'US_LATE'.
- 2026 US equity holidays close cash equities while keeping crypto open.
- 2026 early close days (13:00 ET) adjust RTH end and CLOSE_30 window.
- MON_GAP event window applies from Sunday 20:00 UTC through Monday 14:00 UTC.
"""

import datetime
import unittest
from zoneinfo import ZoneInfo

from src.calendar import (
    classify_regime,
    is_us_equity_holiday,
    get_us_equity_close_time,
    US_EARLY_CLOSES_2026,
    MarketRegimeTag,
)


class TestCalendarRegimes(unittest.TestCase):
    def test_weekend_session_labeling(self):
        """Verify weekend daytime is labeled session='WEEKEND' rather than US_LATE (R-18)."""
        # Saturday 2026-09-19 14:00 UTC (10:00 EDT)
        dt_sat = datetime.datetime(2026, 9, 19, 14, 0, tzinfo=datetime.timezone.utc)
        ts_sat = int(dt_sat.timestamp() * 1e9)
        reg_crypto = classify_regime(ts_sat, "crypto")
        reg_equity = classify_regime(ts_sat, "equities")

        self.assertEqual(reg_crypto.dow_class, "WEEKEND")
        self.assertEqual(reg_crypto.session, "WEEKEND")
        self.assertEqual(reg_equity.dow_class, "WEEKEND")
        self.assertEqual(reg_equity.session, "WEEKEND")
        self.assertTrue(reg_crypto.underlying_open)
        self.assertFalse(reg_equity.underlying_open)

    def test_weekday_us_rth_and_event_windows(self):
        """Verify regular weekday RTH and OPEN_30 / CLOSE_30 windows."""
        # Monday 2026-09-21 13:40 UTC (09:40 EDT) -> OPEN_30
        ts_open = int(datetime.datetime(2026, 9, 21, 13, 40, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        reg_open = classify_regime(ts_open, "equities")
        self.assertEqual(reg_open.dow_class, "WEEKDAY")
        self.assertEqual(reg_open.session, "US_RTH")
        self.assertEqual(reg_open.event_window, "OPEN_30")
        self.assertTrue(reg_open.underlying_open)

        # Monday 2026-09-21 19:40 UTC (15:40 EDT) -> CLOSE_30
        ts_close = int(datetime.datetime(2026, 9, 21, 19, 40, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        reg_close = classify_regime(ts_close, "equities")
        self.assertEqual(reg_close.event_window, "CLOSE_30")
        self.assertTrue(reg_close.underlying_open)

    def test_us_equity_holidays_2026(self):
        """Verify 2026 market holidays close equity trading while crypto remains open."""
        # Good Friday: 2026-04-03 at 14:00 UTC (10:00 EDT)
        dt_good_friday = datetime.datetime(2026, 4, 3, 14, 0, tzinfo=datetime.timezone.utc)
        ts_gf = int(dt_good_friday.timestamp() * 1e9)
        reg_gf_equity = classify_regime(ts_gf, "equities")
        reg_gf_crypto = classify_regime(ts_gf, "crypto")

        self.assertFalse(reg_gf_equity.underlying_open)
        self.assertNotEqual(reg_gf_equity.session, "US_RTH")
        self.assertTrue(reg_gf_crypto.underlying_open)

    def test_early_close_days_2026(self):
        """Verify early close days (13:00 ET close, 12:30 CLOSE_30)."""
        # Black Friday: 2026-11-27
        close_time = get_us_equity_close_time(datetime.date(2026, 11, 27))
        self.assertEqual(close_time, datetime.time(13, 0))

        # 12:40 ET (17:40 UTC) -> CLOSE_30 on early close day
        dt_early = datetime.datetime(2026, 11, 27, 17, 40, tzinfo=datetime.timezone.utc)
        ts_early = int(dt_early.timestamp() * 1e9)
        reg_early = classify_regime(ts_early, "equities")
        self.assertEqual(reg_early.event_window, "CLOSE_30")
        self.assertTrue(reg_early.underlying_open)

        # 13:10 ET (18:10 UTC) -> Market closed after early close
        dt_after_early = datetime.datetime(2026, 11, 27, 18, 10, tzinfo=datetime.timezone.utc)
        ts_after = int(dt_after_early.timestamp() * 1e9)
        reg_after = classify_regime(ts_after, "equities")
        self.assertFalse(reg_after.underlying_open)

    def test_monday_gap_event_window(self):
        """Verify MON_GAP window from Sunday 20:00 UTC through Monday 14:00 UTC."""
        # Sunday 2026-09-20 21:00 UTC -> MON_GAP
        ts_sun = int(datetime.datetime(2026, 9, 20, 21, 0, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        reg_sun = classify_regime(ts_sun, "crypto")
        self.assertEqual(reg_sun.event_window, "MON_GAP")

        # Monday 2026-09-21 04:00 UTC -> MON_GAP
        ts_mon_asia = int(datetime.datetime(2026, 9, 21, 4, 0, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        reg_mon_asia = classify_regime(ts_mon_asia, "crypto")
        self.assertEqual(reg_mon_asia.event_window, "MON_GAP")


if __name__ == "__main__":
    unittest.main()
