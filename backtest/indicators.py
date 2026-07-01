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


def bollinger(close: pd.DataFrame | pd.Series, n: int = 20, k: float = 2.0):
    """Bollinger bands: (mid, upper, lower) around an n-day SMA, +/- k std devs.

    Population std (ddof=0) matches the Connors/Bollinger convention.
    """
    mid = close.rolling(n, min_periods=n).mean()
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return mid, mid + k * sd, mid - k * sd


def efficiency_ratio(close: pd.DataFrame | pd.Series, n: int = 20):
    """Kaufman efficiency ratio: |net move over n| / sum of |daily moves| over n.

    ~1.0 = a clean directional trend; ~0.0 = choppy/ranging (lots of motion,
    little net progress). A low-ER gate isolates the sideways regime this
    mean-reversion sleeve is built for.
    """
    net = close.diff(n).abs()
    path = close.diff().abs().rolling(n, min_periods=n).sum()
    return (net / path).where(path > 0, 0.0)


def liquidity_mask(
    panel: dict, min_price: float = 5.0, min_dollar_vol: float = 20e6
) -> pd.DataFrame:
    """Tradeable-universe mask: raw price and 20-day average dollar volume floors."""
    dv = dollar_volume(panel["raw_close"], panel["volume"])
    return (panel["raw_close"] > min_price) & (dv > min_dollar_vol)


def monte_carlo_drawdown(
    daily_returns: np.ndarray, n_paths: int = 2000, block: int = 5, seed: int = 7
):
    """Block-bootstrap the portfolio's daily returns; return max-drawdown distribution.

    Uses daily portfolio returns (not per-trade returns) so position sizing and
    overlap are preserved; 5-day blocks retain short-horizon autocorrelation.
    """
    rng = np.random.default_rng(seed)
    r = np.asarray(daily_returns)
    r = r[np.isfinite(r)]
    n = len(r)
    n_blocks = -(-n // block)
    starts_max = max(n - block, 1)
    dds = np.empty(n_paths)
    for i in range(n_paths):
        starts = rng.integers(0, starts_max, size=n_blocks)
        seq = np.concatenate([r[s : s + block] for s in starts])[:n]
        eq = np.cumprod(1.0 + seq)
        peak = np.maximum.accumulate(eq)
        dds[i] = ((eq - peak) / peak).min()
    return dds
