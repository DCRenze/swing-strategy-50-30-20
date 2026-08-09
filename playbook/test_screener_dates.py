"""Tests for the as-of invariant that PLAYBOOK 3.1 depends on.

The production failure these lock down: the panel silently included the
in-progress session, so Sleeve H's volume filter could never pass and Sleeve A
exited a session early. See results/LIVE_REVIEW_2026-08.md.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playbook import screener as scr  # noqa: E402


def at(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm)


class TestLastCompletedSession:
    def test_morning_run_uses_yesterday(self):
        # 09:35 ET Thursday -> Wednesday's bar is the last final one
        assert scr.last_completed_session(at(2026, 8, 6, 9, 35)) == dt.date(2026, 8, 5)

    def test_before_close_is_not_final(self):
        # 15:59 ET: today's daily bar is still forming
        assert scr.last_completed_session(at(2026, 8, 6, 15, 59)) == dt.date(2026, 8, 5)

    def test_after_close_is_final(self):
        assert scr.last_completed_session(at(2026, 8, 6, 16, 45)) == dt.date(2026, 8, 6)

    def test_monday_morning_skips_the_weekend(self):
        # Mon 2026-08-10 09:35 -> Fri 2026-08-07
        assert scr.last_completed_session(at(2026, 8, 10, 9, 35)) == dt.date(2026, 8, 7)

    def test_skips_holiday(self):
        # Mon 2026-07-06 09:35 -> Fri 2026-07-03 is a holiday -> Thu 2026-07-02
        assert scr.last_completed_session(at(2026, 7, 6, 9, 35)) == dt.date(2026, 7, 2)

    def test_run_on_a_holiday_still_resolves_backwards(self):
        assert scr.last_completed_session(at(2026, 7, 3, 9, 35)) == dt.date(2026, 7, 2)


class TestIsTradingDay:
    def test_weekend_and_holiday_are_not_trading_days(self):
        assert not scr.is_trading_day(dt.date(2026, 8, 8))   # Saturday
        assert not scr.is_trading_day(dt.date(2026, 7, 3))   # holiday
        assert scr.is_trading_day(dt.date(2026, 8, 6))


class TestBrokerSymbols:
    def test_round_trip(self):
        for feed, broker in [("BRK-B", "BRK.B"), ("BF-A", "BF.A"), ("AAPL", "AAPL")]:
            assert scr.to_broker_symbol(feed) == broker
            assert scr.from_broker_symbol(broker) == feed


@pytest.fixture
def panel_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(scr, "DATA_DIR", tmp_path)
    return tmp_path


def _write_panel(dir_, dates, tickers=("AAA", "BBB")):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    for name in ["raw_open", "raw_high", "raw_low", "raw_close", "adj_close", "volume"]:
        df = pd.DataFrame(1.0, index=idx, columns=list(tickers))
        df.to_parquet(dir_ / f"{scr.RECENT_PREFIX}{name}.parquet")


class TestLoadRecentPanel:
    def test_drops_the_in_progress_session(self, panel_dir):
        # panel carries a row for today (2026-08-06) but only 08-05 is final
        _write_panel(panel_dir, ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"])
        panel = scr.load_recent_panel(expected_as_of=dt.date(2026, 8, 5))
        assert panel["close"].index[-1] == pd.Timestamp("2026-08-05")

    def test_accepts_a_panel_that_already_ends_correctly(self, panel_dir):
        _write_panel(panel_dir, ["2026-08-04", "2026-08-05"])
        panel = scr.load_recent_panel(expected_as_of=dt.date(2026, 8, 5))
        assert panel["close"].index[-1] == pd.Timestamp("2026-08-05")

    def test_raises_when_the_feed_is_behind(self, panel_dir):
        # last row is 08-04 but 08-05 was a completed session -> stand down
        _write_panel(panel_dir, ["2026-08-03", "2026-08-04"])
        with pytest.raises(scr.StaleDataError, match="data feed is behind"):
            scr.load_recent_panel(expected_as_of=dt.date(2026, 8, 5))
