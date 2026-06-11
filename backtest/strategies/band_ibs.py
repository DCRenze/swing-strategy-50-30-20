"""MR-3: Range-stretch lower band + IBS snapback (Quantitativo).

Baseline: lower band = 10-day rolling high - 2.5 * 25-day mean(High-Low);
entry when close < band AND IBS < 0.3; exit at close when close > prior
high; SMA(300) disaster stop. Published on QQQ (Sharpe 2.11) - we replicate
on QQQ to validate the engine, then port to the liquid stock basket.
"""

from __future__ import annotations

from backtest.engine import StrategySpec
from backtest.indicators import ibs, liquidity_mask, rolling_max, sma


def build(
    panel: dict,
    bench: dict,
    band_mult: float = 2.5,
    range_window: int = 25,
    high_window: int = 10,
    ibs_max: float = 0.3,
    disaster_sma: int | None = 300,
    ticker: str | None = None,        # e.g. "QQQ" for single-instrument validation
    entry_mode: str = "next_open",
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    o, h, l, c = panel["open"], panel["high"], panel["low"], panel["close"]
    if ticker:
        cols = [ticker]
        o, h, l, c = o[cols], h[cols], l[cols], c[cols]
        mask = c.notna()
        max_positions = 1
    else:
        mask = liquidity_mask(panel)

    mean_range = (h - l).rolling(range_window, min_periods=range_window).mean()
    band = rolling_max(h, high_window) - band_mult * mean_range
    ibs_v = ibs(h, l, c)
    entry = (c < band) & (ibs_v < ibs_max) & mask

    exit_sig = c > h.shift(1)
    if disaster_sma:
        exit_sig = exit_sig | (c < sma(c, disaster_sma))

    stretch = (band - c) / mean_range  # how far below the band, in range units
    return StrategySpec(
        name=f"band_ibs[{ticker or 'basket'},x{band_mult},ibs{ibs_max},ds{disaster_sma}]",
        entry_signal=entry,
        entry_mode=entry_mode,
        exit_signal=exit_sig,
        exit_mode="close",
        time_stop=15,
        rank=-stretch,  # deepest stretch first
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(band_mult=band_mult, ibs_max=ibs_max, disaster_sma=disaster_sma, ticker=ticker, entry_mode=entry_mode),
    )
