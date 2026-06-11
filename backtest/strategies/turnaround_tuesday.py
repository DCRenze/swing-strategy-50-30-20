"""CAL-1: Turnaround Tuesday, multi-day variant, on a stock basket.

Baseline: Monday close < Friday close AND IBS < 0.5 -> buy Monday close;
exit at close when close > prior high, or 4-day time stop.
"""

from __future__ import annotations

import pandas as pd

from backtest.engine import StrategySpec
from backtest.indicators import ibs, liquidity_mask


def build(
    panel: dict,
    bench: dict,
    ibs_max: float = 0.5,
    time_stop: int = 4,
    entry_mode: str = "close",
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    c, h, l = panel["close"], panel["high"], panel["low"]
    is_monday = pd.Series(c.index.dayofweek == 0, index=c.index)
    ibs_v = ibs(h, l, c)
    down_day = c < c.shift(1)
    entry = down_day & (ibs_v < ibs_max) & liquidity_mask(panel)
    entry = entry & is_monday.values[:, None]

    exit_sig = c > h.shift(1)
    return StrategySpec(
        name=f"turnaround_tuesday[ibs{ibs_max},{time_stop}d]",
        entry_signal=entry,
        entry_mode=entry_mode,
        exit_signal=exit_sig,
        exit_mode="close",
        time_stop=time_stop,
        rank=ibs_v,  # weakest close first
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(ibs_max=ibs_max, time_stop=time_stop, entry_mode=entry_mode),
    )
