"""MR-4: Double 7s on a stock basket (Connors/Alvarez).

Baseline: index > SMA(200) AND stock close > SMA(200); buy when close is the
lowest close of 7 days; exit when close is the highest close of 7 days.
Variants: lookback 5/7/10 (fragility check), SMA(5) exit.
"""

from __future__ import annotations

from backtest.engine import StrategySpec
from backtest.indicators import liquidity_mask, rolling_max, rolling_min, sma
from backtest.strategies.common import spy_regime


def build(
    panel: dict,
    bench: dict,
    lookback: int = 7,
    exit_rule: str = "high7",          # high7 | sma5
    entry_mode: str = "close",
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    close = panel["close"]
    if regime_ok is None:
        regime_ok = spy_regime(bench, 200)
    entry = (
        (close <= rolling_min(close, lookback))
        & (close > sma(close, 200))
        & liquidity_mask(panel)
    )
    if exit_rule == "high7":
        exit_sig = close >= rolling_max(close, lookback)
    elif exit_rule == "sma5":
        exit_sig = close > sma(close, 5)
    else:
        raise ValueError(exit_rule)

    dist = close / rolling_min(close, lookback) - 1.0
    return StrategySpec(
        name=f"double7[{lookback},{exit_rule}]",
        entry_signal=entry,
        entry_mode=entry_mode,
        exit_signal=exit_sig,
        exit_mode="close",
        time_stop=15,
        rank=dist,  # closest to the N-day low first
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(lookback=lookback, exit_rule=exit_rule, entry_mode=entry_mode),
    )
