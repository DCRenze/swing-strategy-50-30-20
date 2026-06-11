"""MR-2: 3 lower lows + ATR-stretch limit buy (Alvarez).

Baseline: close > SMA(100); close < SMA(5); 3 consecutive lower lows;
next-day limit at close - 0.5*ATR(10); exit next open after first up close;
no stop; 10 positions. Universe: $10M+ ADV, price > $1 (Alvarez spec).
"""

from __future__ import annotations

from backtest.engine import StrategySpec
from backtest.indicators import atr, liquidity_mask, sma


def build(
    panel: dict,
    bench: dict,
    stretch: float = 0.5,
    trend_sma: int = 100,
    min_dollar_vol: float = 10e6,
    min_price: float = 1.0,
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    close, low = panel["close"], panel["low"]
    lower_lows = (low < low.shift(1)) & (low.shift(1) < low.shift(2)) & (low.shift(2) < low.shift(3))
    entry = (
        (close > sma(close, trend_sma))
        & (close < sma(close, 5))
        & lower_lows
        & liquidity_mask(panel, min_price=min_price, min_dollar_vol=min_dollar_vol)
    )
    limit_price = close - stretch * atr(panel["high"], low, close, 10)
    exit_sig = close > close.shift(1)  # first up close -> sell next open

    return StrategySpec(
        name=f"three_lower_lows[stretch{stretch},sma{trend_sma}]",
        entry_signal=entry,
        entry_mode="limit",
        limit_price=limit_price,
        exit_signal=exit_sig,
        exit_mode="next_open",
        time_stop=15,
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(stretch=stretch, trend_sma=trend_sma, min_dollar_vol=min_dollar_vol),
    )
