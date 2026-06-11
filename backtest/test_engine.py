"""Engine correctness tests on synthetic data with hand-computed outcomes.

Run:  python -m backtest.test_engine
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.engine import StrategySpec, run_backtest

DATES = pd.bdate_range("2024-01-01", periods=10)


def make_panel(closes, opens=None, highs=None, lows=None, ticker="TST"):
    c = pd.DataFrame({ticker: closes}, index=DATES[: len(closes)])
    o = pd.DataFrame({ticker: opens}, index=c.index) if opens else c.copy()
    h = pd.DataFrame({ticker: highs}, index=c.index) if highs else c + 1.0
    l = pd.DataFrame({ticker: lows}, index=c.index) if lows else c - 1.0
    v = c * 0 + 1_000_000
    return {"open": o, "high": h, "low": l, "close": c, "raw_close": c, "volume": v}


def frame_like(panel, rows: dict):
    """Bool frame, True at given row indices."""
    f = pd.DataFrame(False, index=panel["close"].index, columns=panel["close"].columns)
    for r in rows:
        f.iloc[r] = True
    return f


def test_next_open_entry_close_exit():
    closes = [100, 100, 100, 110, 120, 130, 130, 130, 130, 130]
    opens = [100, 100, 105, 110, 120, 130, 130, 130, 130, 130]
    panel = make_panel(closes, opens)
    spec = StrategySpec(
        name="t1",
        entry_signal=frame_like(panel, [1]),   # signal at close of day 1
        entry_mode="next_open",                # -> buy at open of day 2 = 105
        exit_signal=frame_like(panel, [4]),    # exit at close of day 4 = 120
        exit_mode="close",
        max_positions=1,
    )
    res = run_backtest(panel, spec, slippage_bps=0)
    assert len(res.trades) == 1, res.trades
    tr = res.trades.iloc[0]
    assert tr["entry_px"] == 105 and tr["exit_px"] == 120
    expected = 120 / 105 - 1
    assert abs(tr["ret"] - expected) < 1e-12
    # equity: 100k invested fully at 105 -> 100000 * 120/105
    assert abs(res.equity.iloc[-1] - 100_000 * 120 / 105) < 1e-6
    print("ok: next_open entry / close exit / equity math")


def test_slippage():
    closes = [100, 100, 100, 110, 120, 130, 130, 130, 130, 130]
    opens = [100, 100, 105, 110, 120, 130, 130, 130, 130, 130]
    panel = make_panel(closes, opens)
    spec = StrategySpec(
        name="t2",
        entry_signal=frame_like(panel, [1]),
        entry_mode="next_open",
        exit_signal=frame_like(panel, [4]),
        exit_mode="close",
        max_positions=1,
    )
    res = run_backtest(panel, spec, slippage_bps=10)
    tr = res.trades.iloc[0]
    assert abs(tr["entry_px"] - 105 * 1.001) < 1e-9
    assert abs(tr["exit_px"] - 120 * 0.999) < 1e-9
    print("ok: slippage charged on both sides")


def test_limit_entry():
    closes = [100, 100, 99, 98, 105, 105, 105, 105, 105, 105]
    lows = [99, 99, 95, 97, 104, 104, 104, 104, 104, 104]
    opens = [100, 100, 100, 98, 105, 105, 105, 105, 105, 105]
    panel = make_panel(closes, opens, lows=lows)
    limit = panel["close"] * 0 + 97.0  # limit at 97
    # signal day 1: next day low=95 <= 97 -> fill at min(open=100, 97) = 97
    spec = StrategySpec(
        name="t3",
        entry_signal=frame_like(panel, [1]),
        entry_mode="limit",
        limit_price=limit,
        exit_signal=frame_like(panel, [4]),
        exit_mode="close",
        max_positions=1,
    )
    res = run_backtest(panel, spec, slippage_bps=0)
    assert len(res.trades) == 1
    assert res.trades.iloc[0]["entry_px"] == 97.0
    # signal day 0: next day low=99 > 97 -> no fill (single signal day tested above)
    spec2 = StrategySpec(
        name="t3b",
        entry_signal=frame_like(panel, [0]),
        entry_mode="limit",
        limit_price=limit,
        exit_signal=frame_like(panel, [4]),
        exit_mode="close",
        max_positions=1,
    )
    res2 = run_backtest(panel, spec2, slippage_bps=0)
    assert len(res2.trades) == 0
    print("ok: limit fills only when low <= limit, at min(open, limit)")


def test_time_stop_and_stop_loss():
    closes = [100, 100, 100, 90, 80, 80, 80, 80, 80, 80]
    opens = [100, 100, 100, 95, 85, 80, 80, 80, 80, 80]
    panel = make_panel(closes, opens)
    spec = StrategySpec(
        name="t4",
        entry_signal=frame_like(panel, [1]),
        entry_mode="next_open",  # buy day 2 open = 100
        stop_loss_frac=0.05,     # day 3 close 90 < 95 -> sell day 4 open = 85
        max_positions=1,
    )
    res = run_backtest(panel, spec, slippage_bps=0)
    tr = res.trades.iloc[0]
    assert tr["entry_px"] == 100 and tr["exit_px"] == 85, tr
    # time stop: no stop loss, exit at close after 3 held days
    spec2 = StrategySpec(
        name="t4b",
        entry_signal=frame_like(panel, [1]),
        entry_mode="next_open",
        time_stop=3,
        max_positions=1,
    )
    res2 = run_backtest(panel, spec2, slippage_bps=0)
    tr2 = res2.trades.iloc[0]
    assert tr2["hold_days"] == 3 and tr2["exit_px"] == 80  # day 5 close
    print("ok: stop-loss exits next open; time stop exits at close")


def test_no_lookahead_and_position_cap():
    # signal on the LAST day must produce no trade in next_open mode
    closes = [100] * 10
    panel = make_panel(closes)
    spec = StrategySpec(
        name="t5",
        entry_signal=frame_like(panel, [9]),
        entry_mode="next_open",
        max_positions=1,
    )
    res = run_backtest(panel, spec, slippage_bps=0)
    assert len(res.trades) == 0 and len(panel["close"]) == 10
    # position cap: two tickers signal same day, cap 1 -> only one entered
    c2 = pd.DataFrame({"A": [100.0] * 10, "B": [100.0] * 10}, index=DATES)
    panel2 = {
        "open": c2, "high": c2 + 1, "low": c2 - 1, "close": c2,
        "raw_close": c2, "volume": c2 * 0 + 1e6,
    }
    sig = pd.DataFrame(False, index=DATES, columns=["A", "B"])
    sig.iloc[1] = True
    spec2 = StrategySpec(
        name="t5b", entry_signal=sig, entry_mode="next_open",
        time_stop=2, max_positions=1,
    )
    res2 = run_backtest(panel2, spec2, slippage_bps=0)
    assert len(res2.trades) == 1
    print("ok: no look-ahead on final-day signal; max_positions enforced")


if __name__ == "__main__":
    test_next_open_entry_close_exit()
    test_slippage()
    test_limit_entry()
    test_time_stop_and_stop_loss()
    test_no_lookahead_and_position_cap()
    print("\nAll engine tests passed.")
