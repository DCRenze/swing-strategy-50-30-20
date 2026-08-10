"""Exit-rule correctness tests, including replays of the July 2026 tapes that
exposed the in-progress-bar defect.

Run:  python -m papertrade.test_run_daily
"""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from papertrade.run_daily import a_exit_signal, h_stop_signal
from playbook import screener as scr

ET = ZoneInfo("America/New_York")


def series(pairs) -> pd.Series:
    """[(date, close), ...] -> close series."""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in pairs])
    return pd.Series([v for _, v in pairs], index=idx)


# ---------------------------------------------------------------- sessions ---
def test_session_complete():
    morning = dt.datetime(2026, 7, 23, 9, 35, tzinfo=ET)
    after_close = dt.datetime(2026, 7, 23, 16, 30, tzinfo=ET)

    assert not scr.session_complete("2026-07-23", morning), "today is in progress at 9:35"
    assert scr.session_complete("2026-07-22", morning), "yesterday is complete"
    assert scr.session_complete("2026-07-23", after_close), "today is complete after 4pm"
    assert not scr.session_complete("2026-07-24", morning), "future session is not complete"
    print("ok: in-progress session identified from market time")


def test_panel_excludes_in_progress_row():
    """The coverage guard alone does not catch today's row: liquid names populate
    immediately, so it looks dense and is not."""
    dates = pd.DatetimeIndex(["2026-07-21", "2026-07-22", "2026-07-23"])
    frame = pd.DataFrame({"OKTA": [141.71, 136.69, 135.75],
                          "SPY": [600.0, 601.0, 602.0]}, index=dates)
    with tempfile.TemporaryDirectory() as tmp:
        original = scr.DATA_DIR
        scr.DATA_DIR = Path(tmp)
        try:
            for name in ["raw_open", "raw_high", "raw_low", "raw_close", "adj_close", "volume"]:
                frame.to_parquet(scr.DATA_DIR / f"{scr.RECENT_PREFIX}{name}.parquet")
            morning = scr.load_recent_panel(ref_et=dt.datetime(2026, 7, 23, 9, 35, tzinfo=ET))
            evening = scr.load_recent_panel(ref_et=dt.datetime(2026, 7, 23, 16, 30, tzinfo=ET))
        finally:
            scr.DATA_DIR = original

    assert str(morning["close"].index[-1].date()) == "2026-07-22", morning["close"].index[-1]
    assert 135.75 not in set(morning["raw_close"]["OKTA"]), "live tick leaked into the panel"
    assert str(evening["close"].index[-1].date()) == "2026-07-23", "completed session must be kept"
    print("ok: in-progress row excluded intraday, kept after the close")


# ------------------------------------------------------- sleeve H · 5% stop ---
OKTA_ENTRY_PX = 142.9706
OKTA_COMPLETED = series([                      # 2026-07-02 entry .. 07-22 close
    ("2026-07-02", 141.42), ("2026-07-06", 148.60), ("2026-07-07", 148.47),
    ("2026-07-08", 146.77), ("2026-07-09", 148.84), ("2026-07-10", 138.63),
    ("2026-07-13", 139.53), ("2026-07-14", 154.62), ("2026-07-15", 150.86),
    ("2026-07-16", 147.74), ("2026-07-17", 149.35), ("2026-07-20", 148.41),
    ("2026-07-21", 141.71), ("2026-07-22", 136.69),
])


def test_okta_tape_does_not_trip_the_stop():
    """2026-07-23: the live runner logged a '5% stop' on OKTA. The stop level was
    135.8221 and no completed close ever reached it - 135.75 printed intraday at
    13:33 UTC, four minutes into the session."""
    assert h_stop_signal(OKTA_COMPLETED, "2026-07-02", OKTA_ENTRY_PX, 0.05) is None

    leaked = pd.concat([OKTA_COMPLETED, series([("2026-07-23", 135.75)])])
    tripped = h_stop_signal(leaked, "2026-07-02", OKTA_ENTRY_PX, 0.05)
    assert tripped is not None, "sanity: the leaked tick is what used to trip it"
    print("ok: OKTA holds on completed closes, trips only on the leaked intraday tick")


def test_real_breach_still_stops():
    """RRX 2026-07-01: entry 232.6423, stop level 221.01, 07-02 closed 218.45."""
    rrx = series([("2026-07-01", 229.36), ("2026-07-02", 218.45)])
    sig = h_stop_signal(rrx, "2026-07-01", 232.6423, 0.05)
    assert sig is not None and sig["reason"] == "5% stop", sig
    assert sig["trigger_close"] == 218.45 and sig["trigger_session"] == "2026-07-02", sig
    print("ok: a genuine completed-close breach still stops out")


def test_stop_uses_unadjusted_closes():
    """A dividend going ex mid-hold scales pre-ex closes down. Measured against a
    raw fill price that manufactures a drawdown that never happened."""
    raw = series([("2026-08-06", 96.00), ("2026-08-07", 95.50), ("2026-08-10", 95.20)])
    adjusted = raw * 0.9917  # $0.80 dividend on a ~$96 stock

    assert h_stop_signal(raw, "2026-08-06", 100.0, 0.05) is None, "raw never breaches 95.00"
    assert h_stop_signal(adjusted, "2026-08-06", 100.0, 0.05) is not None, \
        "sanity: the adjusted series is what used to trip it"
    print("ok: H stop reads unadjusted closes, so dividends cannot trip it")


# ------------------------------------------------ sleeve A · first up-close ---
def test_amat_tape_holds_on_entry_day():
    """AMAT 2026-07-29 entry. On the 07-30 run the only completed session since
    entry is the entry day itself, so there is no up-close to act on yet - the
    live runner sold anyway, on the morning tick."""
    amat = series([("2026-07-28", 476.35), ("2026-07-29", 436.45)])
    assert a_exit_signal(amat, "2026-07-29") is None
    print("ok: AMAT holds - no completed up-close since entry")


def test_first_up_close_exits():
    closes = series([("2026-07-29", 100.0), ("2026-07-30", 98.0), ("2026-07-31", 99.5)])
    sig = a_exit_signal(closes, "2026-07-29")
    assert sig is not None and sig["reason"] == "first up-close", sig
    assert sig["trigger_close"] == 99.5 and sig["prior_close"] == 98.0, sig
    print("ok: first completed up-close since entry exits")


def test_missed_up_close_is_flagged_overdue():
    closes = series([("2026-07-29", 100.0), ("2026-07-30", 101.0), ("2026-07-31", 102.0)])
    sig = a_exit_signal(closes, "2026-07-29")
    assert sig is not None and sig["reason"] == "up-close (overdue)", sig
    assert sig["up_closes_since_entry"] == 2, sig
    print("ok: a missed up-close still exits, flagged overdue")


def test_no_up_close_holds():
    closes = series([("2026-07-29", 100.0), ("2026-07-30", 99.0), ("2026-07-31", 98.0)])
    assert a_exit_signal(closes, "2026-07-29") is None
    print("ok: monotonically lower closes hold")


if __name__ == "__main__":
    test_session_complete()
    test_panel_excludes_in_progress_row()
    test_okta_tape_does_not_trip_the_stop()
    test_real_breach_still_stops()
    test_stop_uses_unadjusted_closes()
    test_amat_tape_holds_on_entry_day()
    test_first_up_close_exits()
    test_missed_up_close_is_flagged_overdue()
    test_no_up_close_holds()
    print("\nall exit-rule tests passed")
