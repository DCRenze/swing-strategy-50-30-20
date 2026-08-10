"""Tests for the excursion / giveback measurement."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.excursion import per_trade_paths  # noqa: E402


@pytest.fixture
def achc_like():
    """A path shaped like the live ACHC trade: peaks near +20%, exits at +17.11%."""
    dates = pd.bdate_range("2026-07-01", periods=17)
    px = [29.51, 30.5, 31.4, 32.0, 33.1, 34.0, 34.8, 35.41,
          35.2, 34.9, 34.7, 35.0, 34.8, 34.6, 34.5, 34.56, 34.56]
    close = pd.DataFrame({"ACHC": px}, index=dates)
    trades = pd.DataFrame([{
        "ticker": "ACHC", "entry_date": dates[0], "exit_date": dates[15],
        "entry_px": 29.51, "exit_px": 34.56, "ret": 0.1711, "hold_days": 15,
    }])
    return trades, close


def test_mfe_and_giveback(achc_like):
    trades, close = achc_like
    (row, seg), = per_trade_paths(trades, close)
    rets = seg / row.entry_px - 1.0
    mfe = rets.max()
    assert mfe == pytest.approx(0.1999, abs=1e-4)
    assert mfe - row.ret == pytest.approx(0.0288, abs=1e-4)


def test_path_excludes_the_entry_close_and_includes_the_exit(achc_like):
    trades, close = achc_like
    (row, seg), = per_trade_paths(trades, close)
    # entry-day close is not an excursion; the exit-day close is the last point
    assert seg.index[0] == close.index[1]
    assert seg.index[-1] == close.index[15]


def test_missing_ticker_is_skipped():
    dates = pd.bdate_range("2026-07-01", periods=3)
    close = pd.DataFrame({"AAA": [1.0, 2.0, 3.0]}, index=dates)
    trades = pd.DataFrame([{
        "ticker": "ZZZ", "entry_date": dates[0], "exit_date": dates[2],
        "entry_px": 1.0, "exit_px": 3.0, "ret": 2.0, "hold_days": 2,
    }])
    assert list(per_trade_paths(trades, close)) == []
