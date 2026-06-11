"""Vectorized indicators on wide (date x ticker) DataFrames or Series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.DataFrame | pd.Series, n: int):
    return close.rolling(n, min_periods=n).mean()


def rsi(close: pd.DataFrame | pd.Series, n: int):
    """Wilder RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()
    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    # avg_loss == 0 -> RSI 100; avg_gain == 0 handled by formula (0)
    return out.where(avg_loss != 0, 100.0)


def atr(high, low, close, n: int):
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    return tr.ewm(alpha=1.0 / n, min_periods=n, adjust=False).mean()


def ibs(high, low, close):
    rng = high - low
    out = (close - low) / rng
    return out.where(rng > 0, 0.5)


def rolling_max(s, n: int):
    return s.rolling(n, min_periods=n).max()


def rolling_min(s, n: int):
    return s.rolling(n, min_periods=n).min()


def dollar_volume(raw_close, volume, n: int = 20):
    return (raw_close * volume).rolling(n, min_periods=n).mean()


def liquidity_mask(
    panel: dict, min_price: float = 5.0, min_dollar_vol: float = 20e6
) -> pd.DataFrame:
    """Tradeable-universe mask: raw price and 20-day average dollar volume floors."""
    dv = dollar_volume(panel["raw_close"], panel["volume"])
    return (panel["raw_close"] > min_price) & (dv > min_dollar_vol)


def monte_carlo_drawdown(trade_returns: np.ndarray, n_paths: int = 2000, seed: int = 7):
    """Bootstrap trade sequences; return distribution of max drawdowns (on compounded equity)."""
    rng = np.random.default_rng(seed)
    n = len(trade_returns)
    dds = np.empty(n_paths)
    for i in range(n_paths):
        seq = rng.choice(trade_returns, size=n, replace=True)
        eq = np.cumprod(1.0 + seq)
        peak = np.maximum.accumulate(eq)
        dds[i] = ((eq - peak) / peak).min()
    return dds
