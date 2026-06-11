"""MOM-2: 52-week-high breakout, swing translation (George & Hwang adaptation).

Baseline: close makes a new 252-day closing high (yesterday wasn't one);
volume > 50-day average; SPY > SMA(200) gate; buy next open; hold 15 days
or exit on 5% stop from entry.
"""

from __future__ import annotations

from backtest.engine import StrategySpec
from backtest.indicators import liquidity_mask, rolling_max, sma
from backtest.strategies.common import spy_regime


def build(
    panel: dict,
    bench: dict,
    lookback: int = 252,
    hold_days: int = 15,
    stop_frac: float = 0.05,
    vol_confirm: bool = True,
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    c, v = panel["close"], panel["volume"]
    hh = rolling_max(c, lookback)
    new_high = (c >= hh) & (c.shift(1) < hh.shift(1))
    entry = new_high & liquidity_mask(panel)
    if vol_confirm:
        entry = entry & (v > sma(v, 50))
    if regime_ok is None:
        regime_ok = spy_regime(bench, 200)

    mom6 = c / c.shift(126) - 1.0
    return StrategySpec(
        name=f"high52_breakout[{lookback},{hold_days}d,stop{stop_frac:.0%}]",
        entry_signal=entry,
        entry_mode="next_open",
        exit_signal=None,
        time_stop=hold_days,
        stop_loss_frac=stop_frac,
        rank=-mom6,  # strongest 6-month momentum first
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(lookback=lookback, hold_days=hold_days, stop_frac=stop_frac, vol_confirm=vol_confirm),
    )
