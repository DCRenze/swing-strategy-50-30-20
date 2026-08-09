"""Tests for the live exit rules, pinned to backtest/engine.py semantics.

Regressions these lock down (see results/LIVE_REVIEW_2026-08.md):
  - exits firing off the in-progress session, a full day early
  - a position stranded when its only up close was not the latest session
  - the 1-day round trip being impossible because the entry day's close was excluded
  - the 5% stop comparing adjusted closes against a raw fill price
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from papertrade.run_daily import a_exit_decision, h_entry_in_adjusted_space  # noqa: E402

TIME_STOP = 15


def series(pairs):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in pairs])
    return pd.Series([v for _, v in pairs], index=idx)


class TestSleeveAExit:
    def test_no_exit_before_any_completed_session(self):
        # run on the morning after entry, as_of still precedes the fill date
        s = series([("2026-08-03", 100.0), ("2026-08-04", 99.0)])
        got = a_exit_decision(s, pd.Timestamp("2026-08-05"), pd.Timestamp("2026-08-04"), 0, TIME_STOP)
        assert got == (False, None, False)

    def test_entry_day_up_close_exits_next_open(self):
        # filled 08-04, that day closed up vs 08-03 -> sell at the 08-05 open.
        # engine.py allows this 1-day round trip (7.2% of backtest A trades).
        s = series([("2026-08-03", 100.0), ("2026-08-04", 101.0)])
        should, reason, overdue = a_exit_decision(
            s, pd.Timestamp("2026-08-04"), pd.Timestamp("2026-08-04"), 0, TIME_STOP)
        assert (should, reason, overdue) == (True, "first up close", False)

    def test_entry_day_down_close_holds(self):
        s = series([("2026-08-03", 100.0), ("2026-08-04", 99.0)])
        should, _, _ = a_exit_decision(
            s, pd.Timestamp("2026-08-04"), pd.Timestamp("2026-08-04"), 0, TIME_STOP)
        assert should is False

    def test_first_up_close_after_a_down_day(self):
        s = series([("2026-08-03", 100.0), ("2026-08-04", 99.0), ("2026-08-05", 100.5)])
        should, reason, overdue = a_exit_decision(
            s, pd.Timestamp("2026-08-04"), pd.Timestamp("2026-08-05"), 1, TIME_STOP)
        assert (should, reason, overdue) == (True, "first up close", False)

    def test_missed_up_close_still_exits_when_latest_session_is_down(self):
        # 08-05 closed up (the exit signal) but was not acted on; 08-06 closed down.
        # The old rule fired none of its branches and stranded the position.
        s = series([("2026-08-03", 100.0), ("2026-08-04", 99.0),
                    ("2026-08-05", 100.5), ("2026-08-06", 98.0)])
        should, reason, overdue = a_exit_decision(
            s, pd.Timestamp("2026-08-04"), pd.Timestamp("2026-08-06"), 2, TIME_STOP)
        assert should is True and overdue is True and reason == "up close (overdue)"

    def test_multiple_up_closes_flagged_overdue(self):
        s = series([("2026-08-03", 100.0), ("2026-08-04", 99.0),
                    ("2026-08-05", 100.5), ("2026-08-06", 101.0)])
        should, reason, overdue = a_exit_decision(
            s, pd.Timestamp("2026-08-04"), pd.Timestamp("2026-08-06"), 2, TIME_STOP)
        assert should is True and overdue is True

    def test_time_stop_fires_without_an_up_close(self):
        pairs = [("2026-08-03", 100.0)] + [
            (d, 100.0 - i) for i, d in enumerate(pd.bdate_range("2026-08-04", periods=16).strftime("%Y-%m-%d"), start=1)
        ]
        s = series(pairs)
        should, reason, _ = a_exit_decision(
            s, pd.Timestamp("2026-08-04"), s.index[-1], 15, TIME_STOP)
        assert (should, reason) == (True, "15d time stop")

    def test_no_time_stop_before_day_15(self):
        pairs = [("2026-08-03", 100.0)] + [
            (d, 100.0 - i) for i, d in enumerate(pd.bdate_range("2026-08-04", periods=6).strftime("%Y-%m-%d"), start=1)
        ]
        s = series(pairs)
        should, _, _ = a_exit_decision(s, pd.Timestamp("2026-08-04"), s.index[-1], 5, TIME_STOP)
        assert should is False


class TestHStopPriceSpace:
    def test_converts_raw_fill_into_adjusted_space(self):
        # a $1 dividend went ex during the hold: adjusted closes sit below raw
        assert h_entry_in_adjusted_space(100.0, adj_last=99.0, raw_last=100.0) == pytest.approx(99.0)

    def test_no_adjustment_when_prices_agree(self):
        assert h_entry_in_adjusted_space(100.0, adj_last=105.0, raw_last=105.0) == pytest.approx(100.0)

    def test_falls_back_to_the_raw_fill_on_bad_inputs(self):
        assert h_entry_in_adjusted_space(100.0, adj_last=0.0, raw_last=0.0) == 100.0

    def test_stop_no_longer_trips_early_on_a_dividend(self):
        # entry 100 raw, 1% dividend -> a -4.5% adjusted close must NOT trip a 5% stop
        entry_adj = h_entry_in_adjusted_space(100.0, adj_last=99.0, raw_last=100.0)
        worst_close = 99.0 * 0.955  # 4.5% below the adjusted entry
        assert not worst_close < entry_adj * 0.95
