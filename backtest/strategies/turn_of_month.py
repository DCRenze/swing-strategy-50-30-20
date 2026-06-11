"""CAL-2: Turn-of-month on the largest, most liquid names.

Baseline: buy at close of the 5th-to-last trading day of the month; sell at
close of the 3rd trading day of the new month (~7 trading days). Universe:
top-N by 20-day average dollar volume (pension-flow large caps).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.engine import StrategySpec
from backtest.indicators import dollar_volume


def build(
    panel: dict,
    bench: dict,
    entry_days_before_eom: int = 5,
    exit_day_of_month: int = 3,
    top_n: int = 100,
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    c = panel["close"]
    idx = c.index

    month = idx.to_period("M")
    # rank of each session within its month, from start (1-based) and from end
    pos_in_month = pd.Series(np.arange(len(idx)), index=idx).groupby(month).cumcount() + 1
    month_size = pd.Series(idx, index=idx).groupby(month).transform("size")
    pos_from_end = month_size - pos_in_month + 1  # 1 = last session of month

    entry_day = pd.Series(pos_from_end.values == entry_days_before_eom, index=idx)
    exit_day = pd.Series(pos_in_month.values == exit_day_of_month, index=idx)

    dv = dollar_volume(panel["raw_close"], panel["volume"])
    top_mask = dv.rank(axis=1, ascending=False) <= top_n

    entry = top_mask & entry_day.values[:, None] & c.notna()
    exit_sig = c.notna() & exit_day.values[:, None]

    return StrategySpec(
        name=f"turn_of_month[-{entry_days_before_eom},+{exit_day_of_month},top{top_n}]",
        entry_signal=entry,
        entry_mode="close",
        exit_signal=exit_sig,
        exit_mode="close",
        time_stop=12,
        rank=-dv,  # most liquid first
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(entry_days_before_eom=entry_days_before_eom, exit_day_of_month=exit_day_of_month, top_n=top_n),
    )
