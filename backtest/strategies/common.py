"""Shared building blocks for strategy modules."""

from __future__ import annotations

import pandas as pd

from backtest.indicators import sma


def spy_regime(bench: dict, n: int = 200) -> pd.Series:
    """True when SPY close > its n-day SMA."""
    spy = bench["spy"]
    return spy > sma(spy, n)


def vix_stretch_gate(bench: dict, stretch: float = 0.05, days: int = 3) -> pd.Series:
    """True when VIX has closed >= stretch above its 10-day SMA for `days` consecutive days."""
    vix = bench["vix"]
    above = vix > sma(vix, 10) * (1.0 + stretch)
    return above.rolling(days).sum() >= days
