"""MR-4: Always-on RSI(2) range reversion for choppy/sideways markets (Sleeve D).

Buys short-term oversold names and sells the snapback to the mean. Unlike the
uptrend dip-buyers already in the repo (three_lower_lows, rsi2_pullback,
band_ibs — all gated on close > SMA(200)), this sleeve is designed to keep
working when the market goes nowhere:

  - soft trend filter (close > SMA(100)) instead of a hard uptrend gate, so it
    fires in ranging tape but still steps off names in outright freefall;
  - MOC entry/exit (slippage-robust, like the retired B/C sleeves) rather than
    a resting limit whose edge dies at ~20 bps;
  - a disaster stop (close < SMA(200)) that the account no longer gets from the
    Turnaround-Tuesday bear offset.

Optional gates (off in baseline, swept in the gauntlet):
  - use_bollinger: enter on close < lower Bollinger band instead of RSI(2);
  - ranging_gate: require Kaufman efficiency_ratio(close) < threshold, i.e. the
    name itself is chopping sideways rather than trending.
"""

from __future__ import annotations

from backtest.engine import StrategySpec
from backtest.indicators import (
    bollinger,
    efficiency_ratio,
    ibs,
    liquidity_mask,
    rsi,
    sma,
)


def build(
    panel: dict,
    bench: dict,
    rsi_entry: float = 10.0,
    trend_sma: int | None = 100,      # soft "not in freefall" filter; None = off
    ibs_max: float = 0.5,
    exit_rule: str = "either",        # sma5 | rsi65 | either
    time_stop: int = 6,
    disaster_sma: int | None = 200,   # hard exit if close < SMA(disaster_sma)
    use_bollinger: bool = False,      # enter on close < lower band instead of RSI(2)
    band_n: int = 20,
    band_k: float = 2.5,
    ranging_gate: float | None = None,  # require efficiency_ratio < this (choppy-only)
    er_window: int = 20,
    entry_mode: str = "close",        # MOC by default
    max_positions: int = 10,
    regime_ok=None,
    **_,
) -> StrategySpec:
    close = panel["close"]
    r2 = rsi(close, 2)

    if use_bollinger:
        _, _, lower = bollinger(close, band_n, band_k)
        oversold = close < lower
        rank = close - lower  # deepest below band first (most negative)
    else:
        oversold = r2 < rsi_entry
        rank = r2  # lowest RSI(2) first

    entry = oversold & (ibs(panel["high"], panel["low"], close) < ibs_max) & liquidity_mask(panel)
    if trend_sma:
        entry = entry & (close > sma(close, trend_sma))
    if ranging_gate is not None:
        entry = entry & (efficiency_ratio(close, er_window) < ranging_gate)

    if exit_rule == "sma5":
        exit_sig = close > sma(close, 5)
    elif exit_rule == "rsi65":
        exit_sig = r2 > 65
    elif exit_rule == "either":
        exit_sig = (close > sma(close, 5)) | (r2 > 65)
    else:
        raise ValueError(exit_rule)
    if disaster_sma:
        exit_sig = exit_sig | (close < sma(close, disaster_sma))

    entry_tag = f"bb{band_k}" if use_bollinger else f"rsi{rsi_entry}"
    gate_tag = "" if ranging_gate is None else f",er{ranging_gate}"
    trend_tag = "none" if not trend_sma else str(trend_sma)
    return StrategySpec(
        name=f"range_reversion[{entry_tag},sma{trend_tag},{exit_rule},ts{time_stop},ds{disaster_sma}{gate_tag}]",
        entry_signal=entry,
        entry_mode=entry_mode,
        exit_signal=exit_sig,
        exit_mode="close",
        time_stop=time_stop,
        rank=rank,
        max_positions=max_positions,
        regime_ok=regime_ok,
        params=dict(
            rsi_entry=rsi_entry, trend_sma=trend_sma, ibs_max=ibs_max, exit_rule=exit_rule,
            time_stop=time_stop, disaster_sma=disaster_sma, use_bollinger=use_bollinger,
            band_k=band_k, ranging_gate=ranging_gate, entry_mode=entry_mode,
        ),
    )
