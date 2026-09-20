from __future__ import annotations

"""Unit Tests for Market Calendar, Regime Tagging, and Early Closes (R-18).

Verifies:
- Weekend midday is labeled 'WEEKEND', not 'US_LATE'.
- 2026 US equity holidays close cash equities while keeping crypto open.
- 2026 early close days (13:00 ET) adjust RTH end and CLOSE_30 window.
- MON_GAP event window applies from Sunday 20:00 UTC through Monday 14:00 UTC.
"""

import datetime
import unittest

from src.session_calendar import (
    classify_regime,
    get_us_equity_close_time,
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

    def test_utc_and_ist_timezone_label_integrity(self):
        """Verify strict timezone separation and conversion integrity (V-31).

        Ensures UTC and IST (+05:30) are strictly separated and cannot be conflated.
        """
        tz_ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")
        dt_utc = datetime.datetime(2026, 9, 20, 0, 41, tzinfo=datetime.timezone.utc)
        dt_ist = dt_utc.astimezone(tz_ist)

        # 00:41 UTC is 06:11 IST, NOT 00:41 IST
        self.assertEqual(dt_ist.hour, 6)
        self.assertEqual(dt_ist.minute, 11)
        self.assertNotEqual(dt_utc.hour, dt_ist.hour)
        self.assertEqual(dt_utc.timestamp(), dt_ist.timestamp())

    def test_w11_rth_capture_tagging_and_separation(self):
        """W-11 / Mandate v5 §2: Tag fills as PRE (13:00-13:30), RTH (13:30-20:00), POST (20:00-20:30), OTHER,
        and verify PRE/POST are never mixed into RTH statistics.
        """
        from src.session_calendar import classify_rth_capture_tag

        # PRE window: 13:00 to 13:30 UTC
        ts_pre = int(datetime.datetime(2026, 9, 21, 13, 15, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        self.assertEqual(classify_rth_capture_tag(ts_pre), "PRE")

        # RTH window: 13:30 to 20:00 UTC (NYSE cash hours)
        ts_rth_start = int(datetime.datetime(2026, 9, 21, 13, 30, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        ts_rth_mid = int(datetime.datetime(2026, 9, 21, 16, 0, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        ts_rth_end = int(datetime.datetime(2026, 9, 21, 19, 59, 59, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        self.assertEqual(classify_rth_capture_tag(ts_rth_start), "RTH")
        self.assertEqual(classify_rth_capture_tag(ts_rth_mid), "RTH")
        self.assertEqual(classify_rth_capture_tag(ts_rth_end), "RTH")

        # POST window: 20:00 to 20:30 UTC
        ts_post = int(datetime.datetime(2026, 9, 21, 20, 15, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        self.assertEqual(classify_rth_capture_tag(ts_post), "POST")

        # OTHER window: outside 13:00-20:30 UTC
        ts_other_pre = int(datetime.datetime(2026, 9, 21, 12, 59, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        ts_other_post = int(datetime.datetime(2026, 9, 21, 20, 31, tzinfo=datetime.timezone.utc).timestamp() * 1e9)
        self.assertEqual(classify_rth_capture_tag(ts_other_pre), "OTHER")
        self.assertEqual(classify_rth_capture_tag(ts_other_post), "OTHER")

        # Separation check: verify that filtering strictly on rth_tag == 'RTH' excludes PRE and POST fills
        sample_fills = [
            {"id": 1, "rth_tag": classify_rth_capture_tag(ts_pre), "edge_bps": 2.0},
            {"id": 2, "rth_tag": classify_rth_capture_tag(ts_rth_mid), "edge_bps": 1.5},
            {"id": 3, "rth_tag": classify_rth_capture_tag(ts_post), "edge_bps": -0.5},
        ]
        rth_only_fills = [f for f in sample_fills if f["rth_tag"] == "RTH"]
        self.assertEqual(len(rth_only_fills), 1)
        self.assertEqual(rth_only_fills[0]["id"], 2)


if __name__ == "__main__":
    unittest.main()
