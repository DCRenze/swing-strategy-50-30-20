"""MOM-1: Stockbee 4% momentum burst.

Baseline: close >= 1.04 * prior close; volume > prior day and > 100k shares;
prior day quiet (down or narrow range); not extended (<2 prior 4% up days in
last 5); closes near its high; buy at close; exit by day 5 (sell into
strength is discretionary - the codable version is the time stop), stop at
breakout-day low.
"""

from __future__ import annotations

from backtest.engine import StrategySpec
from backtest.indicators import ibs, liquidity_mask, sma


def build(
    panel: dict,
    bench: dict,
    burst_pct: float = 0.04,
    hold_days: int = 5,
    min_ibs: float = 0.6,
    entry_mode: str = "close",
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    c, h, l, v = panel["close"], panel["high"], panel["low"], panel["volume"]
    ret1 = c / c.shift(1) - 1.0
    burst = ret1 >= burst_pct
    vol_ok = (v > v.shift(1)) & (v > 100_000)
    rng = h - l
    quiet_prior = (c.shift(1) <= c.shift(2)) | (rng.shift(1) < rng.rolling(10).mean().shift(1))
    extended = (ret1 >= burst_pct).rolling(5).sum().shift(1) >= 2
    near_high = ibs(h, l, c) >= min_ibs

    entry = burst & vol_ok & quiet_prior & ~extended & near_high & liquidity_mask(panel)

    return StrategySpec(
        name=f"momentum_burst[{burst_pct:.0%},{hold_days}d]",
        entry_signal=entry,
        entry_mode=entry_mode,
        exit_signal=None,
        time_stop=hold_days,
        stop_at_signal_low=True,
        rank=-ret1,  # strongest burst first
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(burst_pct=burst_pct, hold_days=hold_days, min_ibs=min_ibs, entry_mode=entry_mode),
    )
