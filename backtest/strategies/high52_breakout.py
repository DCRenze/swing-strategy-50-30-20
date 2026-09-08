"""MOM-2: 52-week-high breakout, swing translation (George & Hwang adaptation).

Baseline: close makes a new 252-day closing high (yesterday wasn't one);
volume > 50-day average; SPY > SMA(200) gate; buy next open; hold 15 days
or exit on 5% stop from entry.

`min_same_day_signals` (default None = the validated baseline) adds an optional
breadth gate; see results/BREADTH_HYPOTHESIS.md. It is research-only until the
gauntlet clears it - the deployed config does not set it.
"""

from __future__ import annotations

from backtest.engine import StrategySpec
from backtest.indicators import atr, liquidity_mask, rolling_max, sma
from backtest.strategies.common import spy_regime


def build(
    panel: dict,
    bench: dict,
    lookback: int = 252,
    hold_days: int = 15,
    stop_frac: float = 0.05,
    vol_confirm: bool = True,
    min_same_day_signals: int | None = None,
    max_positions: int = 10,
    regime_ok=None,
    # --- Phase 2 upside management; all None = the validated baseline ---
    trail_atr_mult: float | None = None,
    trail_atr_n: int = 10,
    trail_giveback_frac: float | None = None,
    profit_target_frac: float | None = None,
    breakeven_after_frac: float | None = None,
    hold_extend_sma: int | None = None,
    max_hold_days: int | None = None,
    **_,
) -> StrategySpec:
    c, v = panel["close"], panel["volume"]
    hh = rolling_max(c, lookback)
    new_high = (c >= hh) & (c.shift(1) < hh.shift(1))
    entry = new_high & liquidity_mask(panel)
    if vol_confirm:
        entry = entry & (v > sma(v, 50))
    if min_same_day_signals is not None and min_same_day_signals > 1:
        # Breadth gate: a day on which many names simultaneously print a new
        # 52-week high is a market-wide thrust, and those cohorts historically
        # carry a much higher hit rate than a lone breakout. Require at least N
        # qualifying signals on the session, otherwise take none of them.
        # Counted AFTER liquidity/volume filters so it reflects tradable names,
        # and BEFORE the regime gate + ranking, which the engine applies.
        breadth_ok = entry.sum(axis=1) >= min_same_day_signals
        entry = entry.mul(breadth_ok, axis=0).astype(bool)
    if regime_ok is None:
        regime_ok = spy_regime(bench, 200)

    mom6 = c / c.shift(126) - 1.0

    upside = {}
    tag = ""
    if min_same_day_signals is not None and min_same_day_signals > 1:
        tag += f",breadth{min_same_day_signals}"
    if trail_atr_mult is not None:
        upside["trail_atr_mult"] = trail_atr_mult
        upside["trail_atr"] = atr(panel["high"], panel["low"], c, trail_atr_n)
        tag += f",trailATR{trail_atr_mult}x{trail_atr_n}"
    if trail_giveback_frac is not None:
        upside["trail_giveback_frac"] = trail_giveback_frac
        tag += f",giveback{trail_giveback_frac:.0%}"
    if profit_target_frac is not None:
        upside["profit_target_frac"] = profit_target_frac
        tag += f",target{profit_target_frac:.0%}"
    if breakeven_after_frac is not None:
        upside["breakeven_after_frac"] = breakeven_after_frac
        tag += f",be{breakeven_after_frac:.0%}"
    if hold_extend_sma is not None:
        upside["hold_while"] = c > sma(c, hold_extend_sma)
        upside["hold_while_max"] = max_hold_days
        tag += f",holdSMA{hold_extend_sma}" + (f"max{max_hold_days}" if max_hold_days else "")

    return StrategySpec(
        name=f"high52_breakout[{lookback},{hold_days}d,stop{stop_frac:.0%}{tag}]",
        entry_signal=entry,
        entry_mode="next_open",
        exit_signal=None,
        time_stop=hold_days,
        stop_loss_frac=stop_frac,
        rank=-mom6,  # strongest 6-month momentum first
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(lookback=lookback, hold_days=hold_days, stop_frac=stop_frac,
                    vol_confirm=vol_confirm, min_same_day_signals=min_same_day_signals,
                    trail_atr_mult=trail_atr_mult,
                    trail_giveback_frac=trail_giveback_frac,
                    profit_target_frac=profit_target_frac,
                    breakeven_after_frac=breakeven_after_frac,
                    hold_extend_sma=hold_extend_sma, max_hold_days=max_hold_days),
        **upside,
    )
