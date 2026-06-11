"""Sanity-count tickers passing each Sleeve A condition (debug aid)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.indicators import dollar_volume, sma  # noqa: E402
from playbook.screener import (  # noqa: E402
    A_MIN_DOLLAR_VOL, A_MIN_PRICE, A_TREND_SMA, load_recent_panel,
)

panel = load_recent_panel()
c, l, v, raw_c = panel["close"], panel["low"], panel["volume"], panel["raw_close"]
print("rows:", len(c), "cols:", c.shape[1], "last date:", c.index[-1].date())

dv = dollar_volume(raw_c, v)
liq = ((raw_c > A_MIN_PRICE) & (dv > A_MIN_DOLLAR_VOL)).iloc[-1]
trend = (c > sma(c, A_TREND_SMA)).iloc[-1]
below5 = (c < sma(c, 5)).iloc[-1]
low3 = ((l < l.shift(1)) & (l.shift(1) < l.shift(2)) & (l.shift(2) < l.shift(3))).iloc[-1]
sma200_valid = sma(c, A_TREND_SMA).iloc[-1].notna()

print("liquidity pass     :", int(liq.sum()))
print("sma200 computable  :", int(sma200_valid.sum()))
print("above sma200       :", int(trend.sum()))
print("below sma5         :", int(below5.sum()))
print("3 lower lows       :", int(low3.sum()))
print("all combined       :", int((liq & trend & below5 & low3).sum()))
print("trend+below5       :", int((trend & below5).sum()))
print("below5+low3        :", int((below5 & low3).sum()))
