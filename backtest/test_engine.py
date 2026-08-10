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


# ------------------------------------------------ upside management (Phase 2) ---
# Shared tape: buy at day-1 open (100), peak close 112 on day 3, then fade.
UPSIDE_CLOSES = [100, 100, 106, 112, 109, 100, 100, 100, 100, 100]


def upside_spec(name, **kw):
    panel = make_panel(UPSIDE_CLOSES)
    return panel, StrategySpec(
        name=name,
        entry_signal=frame_like(panel, [0]),
        entry_mode="next_open",  # buy day 1 open = 100
        max_positions=1,
        **kw,
    )


def test_upside_fields_default_to_noop():
    """A spec that sets none of them must behave exactly as before."""
    panel, spec = upside_spec("u0", time_stop=4)
    res = run_backtest(panel, spec, slippage_bps=0)
    tr = res.trades.iloc[0]
    assert tr["entry_px"] == 100 and tr["hold_days"] == 4 and tr["exit_px"] == 100, tr
    print("ok: upside fields default to no-op")


def test_profit_target():
    # day 3 close 112 >= 100 * 1.10 -> sell day 4 open = 109
    panel, spec = upside_spec("u1", profit_target_frac=0.10)
    res = run_backtest(panel, spec, slippage_bps=0)
    tr = res.trades.iloc[0]
    assert tr["exit_px"] == 109, tr
    print("ok: profit target exits at the open after the target close")


def test_trailing_giveback():
    # peak 112, open profit 12, give back half -> level 106
    # day 4 close 109 > 106 holds; day 5 close 100 < 106 -> sell day 6 open = 100
    panel, spec = upside_spec("u2", trail_giveback_frac=0.5)
    res = run_backtest(panel, spec, slippage_bps=0)
    tr = res.trades.iloc[0]
    assert tr["exit_px"] == 100 and str(tr["exit_date"].date()) == str(DATES[6].date()), tr
    print("ok: give-back stop exits after surrendering half the open profit")


def test_trailing_atr():
    # ATR fixed at 2.0, k=2 -> trail level = peak - 4 = 108
    # day 4 close 109 > 108 holds; day 5 close 100 < 108 -> sell day 6 open
    panel, spec = upside_spec("u3", trail_atr_mult=2.0,
                              trail_atr=panel_atr(make_panel(UPSIDE_CLOSES), 2.0))
    res = run_backtest(panel, spec, slippage_bps=0)
    tr = res.trades.iloc[0]
    assert str(tr["exit_date"].date()) == str(DATES[6].date()), tr
    print("ok: ATR trailing stop exits below peak - k*ATR")


def test_trailing_atr_requires_frame():
    _, spec = upside_spec("u3b", trail_atr_mult=2.0)
    try:
        run_backtest(make_panel(UPSIDE_CLOSES), spec, slippage_bps=0)
    except ValueError:
        print("ok: ATR trailing stop without an ATR frame is rejected")
        return
    raise AssertionError("expected ValueError for trail_atr_mult without trail_atr")


def test_breakeven_stop():
    # peak 106 on day 2 arms the stop (>= 105); day 3 close 99 < 100 -> sell day 4 open
    closes = [100, 100, 106, 99, 95, 95, 95, 95, 95, 95]
    panel = make_panel(closes)
    spec = StrategySpec(
        name="u4", entry_signal=frame_like(panel, [0]), entry_mode="next_open",
        breakeven_after_frac=0.05, max_positions=1,
    )
    res = run_backtest(panel, spec, slippage_bps=0)
    tr = res.trades.iloc[0]
    assert tr["exit_px"] == 95 and str(tr["exit_date"].date()) == str(DATES[4].date()), tr
    # unarmed: never reaches +5%, so the breakeven stop must not fire
    flat = make_panel([100, 100, 101, 99, 95, 95, 95, 95, 95, 95])
    spec2 = StrategySpec(
        name="u4b", entry_signal=frame_like(flat, [0]), entry_mode="next_open",
        breakeven_after_frac=0.05, max_positions=1,
    )
    assert len(run_backtest(flat, spec2, slippage_bps=0).trades) == 0
    print("ok: breakeven stop only fires once armed by peak profit")


def test_hold_while_defers_time_stop():
    panel = make_panel(UPSIDE_CLOSES)
    hold = pd.DataFrame(False, index=DATES, columns=["TST"])
    hold.iloc[3] = True  # day 3 would be the time stop; defer it one session
    spec = StrategySpec(
        name="u5", entry_signal=frame_like(panel, [0]), entry_mode="next_open",
        time_stop=2, hold_while=hold, max_positions=1,
    )
    res = run_backtest(panel, spec, slippage_bps=0)
    tr = res.trades.iloc[0]
    assert tr["hold_days"] == 3 and tr["exit_px"] == 109, tr  # day 4 close
    # without the deferral the same spec exits a day earlier, at day 3 close 112
    spec2 = StrategySpec(
        name="u5b", entry_signal=frame_like(panel, [0]), entry_mode="next_open",
        time_stop=2, max_positions=1,
    )
    tr2 = run_backtest(panel, spec2, slippage_bps=0).trades.iloc[0]
    assert tr2["hold_days"] == 2 and tr2["exit_px"] == 112, tr2
    print("ok: hold_while defers the time stop while the condition holds")


def test_hold_while_max_caps_the_deferral():
    panel = make_panel(UPSIDE_CLOSES)
    hold = pd.DataFrame(True, index=DATES, columns=["TST"])  # would defer forever
    spec = StrategySpec(
        name="u6", entry_signal=frame_like(panel, [0]), entry_mode="next_open",
        time_stop=2, hold_while=hold, hold_while_max=4, max_positions=1,
    )
    tr = run_backtest(panel, spec, slippage_bps=0).trades.iloc[0]
    assert tr["hold_days"] == 4, tr
    # without the cap the position never exits inside the tape
    spec2 = StrategySpec(
        name="u6b", entry_signal=frame_like(panel, [0]), entry_mode="next_open",
        time_stop=2, hold_while=hold, max_positions=1,
    )
    assert len(run_backtest(panel, spec2, slippage_bps=0).trades) == 0
    print("ok: hold_while_max caps an otherwise unbounded deferral")


def panel_atr(panel, value: float):
    """Constant ATR frame shaped like the panel."""
    return panel["close"] * 0.0 + value


if __name__ == "__main__":
    test_next_open_entry_close_exit()
    test_slippage()
    test_limit_entry()
    test_time_stop_and_stop_loss()
    test_no_lookahead_and_position_cap()
    test_upside_fields_default_to_noop()
    test_profit_target()
    test_trailing_giveback()
    test_trailing_atr()
    test_trailing_atr_requires_frame()
    test_breakeven_stop()
    test_hold_while_defers_time_stop()
    test_hold_while_max_caps_the_deferral()
    print("\nAll engine tests passed.")
