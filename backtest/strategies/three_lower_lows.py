"""MR-2: 3 lower lows + ATR-stretch limit buy (Alvarez).

Baseline: close > SMA(100); close < SMA(5); 3 consecutive lower lows;
next-day limit at close - 0.5*ATR(10); exit next open after first up close;
no stop; 10 positions. Universe: $10M+ ADV, price > $1 (Alvarez spec).

`max_atr_pct` (default None = the validated baseline) adds an optional calmness
filter, skipping signals in names whose ATR(10) exceeds that fraction of price.
See results/VOLATILITY_HYPOTHESIS.md. Research only until the gauntlet clears it.
"""

from __future__ import annotations

from backtest.engine import StrategySpec
from backtest.indicators import atr, bollinger, ibs, liquidity_mask, rsi, sma


def build(
    panel: dict,
    bench: dict,
    stretch: float = 0.5,
    trend_sma: int = 100,
    min_dollar_vol: float = 10e6,
    min_price: float = 1.0,
    max_atr_pct: float | None = None,
    # --- Phase 6 entry-confirmation filters; all None/default = validated baseline.
    # Every one of these varies BETWEEN NAMES ON THE SAME DAY, which is the test
    # Phase 4 (breadth) and Phase 5 (ATR) both failed - see PHASE5_CONCLUSION.md.
    n_lower_lows: int = 3,
    max_rsi2: float | None = None,
    max_ibs: float | None = None,
    min_trend_strength: float | None = None,
    below_lower_band: bool = False,
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    close, low, high = panel["close"], panel["low"], panel["high"]
    lower_lows = low < low.shift(1)
    for k in range(1, n_lower_lows):
        lower_lows = lower_lows & (low.shift(k) < low.shift(k + 1))
    entry = (
        (close > sma(close, trend_sma))
        & (close < sma(close, 5))
        & lower_lows
        & liquidity_mask(panel, min_price=min_price, min_dollar_vol=min_dollar_vol)
    )
    tags = []
    if n_lower_lows != 3:
        tags.append(f"ll{n_lower_lows}")
    if max_rsi2 is not None:
        # Deeper oversold. RSI is normalised per name, so this compares stocks
        # to themselves rather than to the market's mood.
        entry = entry & (rsi(close, 2) <= max_rsi2)
        tags.append(f"rsi{max_rsi2:g}")
    if max_ibs is not None:
        # Close sitting near the low of its own daily range - capitulation
        # rather than a drift lower. Bounded 0-1 by construction.
        entry = entry & (ibs(high, low, close) <= max_ibs)
        tags.append(f"ibs{max_ibs:g}")
    if min_trend_strength is not None:
        # Buy dips only in names in a genuinely strong long-term uptrend, not
        # ones barely clinging above the moving average.
        entry = entry & ((close / sma(close, trend_sma) - 1.0) >= min_trend_strength)
        tags.append(f"trend{min_trend_strength:.0%}")
    if below_lower_band:
        _mid, _upper, lower = bollinger(close, 20, 2.0)
        entry = entry & (close < lower)
        tags.append("bb")
    atr10 = atr(panel["high"], low, close, 10)
    if max_atr_pct is not None:
        # Calmness filter: skip names whose average daily range is a large
        # fraction of their price. Applied to the ENTRY signal only - sizing,
        # the limit offset, the exit and the slot count are all untouched.
        entry = entry & ((atr10 / close) <= max_atr_pct)
    limit_price = close - stretch * atr10
    exit_sig = close > close.shift(1)  # first up close -> sell next open

    return StrategySpec(
        name=(f"three_lower_lows[stretch{stretch},sma{trend_sma}"
              + (f",maxatr{max_atr_pct:.1%}" if max_atr_pct is not None else "")
              + ("," + ",".join(tags) if tags else "") + "]"),
        entry_signal=entry,
        entry_mode="limit",
        limit_price=limit_price,
        exit_signal=exit_sig,
        exit_mode="next_open",
        time_stop=15,
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(stretch=stretch, trend_sma=trend_sma, min_dollar_vol=min_dollar_vol,
                    max_atr_pct=max_atr_pct, n_lower_lows=n_lower_lows, max_rsi2=max_rsi2,
                    max_ibs=max_ibs, min_trend_strength=min_trend_strength,
                    below_lower_band=below_lower_band),
    )
