"""MR-1: RSI(2)-family pullback on a stock basket (Connors school).

Baseline: stock close > SMA(200); RSI(2) < 10; enter at close; exit when
close > SMA(5); no stop. Variants: cumulative RSI(2) thresholds, RSI exit,
SMA(100) trend filter, next-open entry.
"""

from __future__ import annotations

from backtest.engine import StrategySpec
from backtest.indicators import liquidity_mask, rsi, sma


def build(
    panel: dict,
    bench: dict,
    rsi_entry: float = 10.0,
    cumulative: float | None = None,   # e.g. 35.0 -> use cumRSI(2) < 35 instead
    exit_rule: str = "sma5",           # sma5 | rsi65 | cum65
    trend_sma: int = 200,
    entry_mode: str = "close",
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    close = panel["close"]
    r2 = rsi(close, 2)
    trend = close > sma(close, trend_sma)
    if cumulative is not None:
        cum = r2 + r2.shift(1)
        oversold = cum < cumulative
        rank = cum
    else:
        oversold = r2 < rsi_entry
        rank = r2
    entry = oversold & trend & liquidity_mask(panel)

    if exit_rule == "sma5":
        exit_sig = close > sma(close, 5)
    elif exit_rule == "rsi65":
        exit_sig = r2 > 65
    elif exit_rule == "cum65":
        exit_sig = (r2 + r2.shift(1)) > 65
    else:
        raise ValueError(exit_rule)

    return StrategySpec(
        name=f"rsi2_pullback[{'cum' + str(cumulative) if cumulative else 'rsi' + str(rsi_entry)},{exit_rule},sma{trend_sma}]",
        entry_signal=entry,
        entry_mode=entry_mode,
        exit_signal=exit_sig,
        exit_mode="close",
        time_stop=15,
        rank=rank,
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(rsi_entry=rsi_entry, cumulative=cumulative, exit_rule=exit_rule, trend_sma=trend_sma, entry_mode=entry_mode),
    )
