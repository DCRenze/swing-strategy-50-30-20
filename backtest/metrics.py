"""Performance metrics for BacktestResult objects."""

from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float(((equity - peak) / peak).min())


def sharpe(equity: pd.Series) -> float:
    rets = equity.pct_change().dropna()
    if rets.std() == 0:
        return 0.0
    return float(rets.mean() / rets.std() * np.sqrt(252))


def cagr(equity: pd.Series) -> float:
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0 or equity.iloc[0] <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    wins = trades.loc[trades["ret"] > 0, "ret"].sum()
    losses = -trades.loc[trades["ret"] < 0, "ret"].sum()
    return float(wins / losses) if losses > 0 else float("inf")


def summarize(result, benchmark: pd.Series | None = None) -> dict:
    eq, tr = result.equity, result.trades
    out = {
        "strategy": result.name,
        "start": str(eq.index[0].date()),
        "end": str(eq.index[-1].date()),
        "cagr": round(cagr(eq), 4),
        "sharpe": round(sharpe(eq), 2),
        "max_dd": round(max_drawdown(eq), 4),
        "exposure": round(float(result.exposure.mean()), 3),
        "trades": int(len(tr)),
        "win_rate": round(float((tr["ret"] > 0).mean()), 3) if len(tr) else None,
        "avg_ret": round(float(tr["ret"].mean()), 5) if len(tr) else None,
        "profit_factor": round(profit_factor(tr), 2) if len(tr) else None,
        "avg_hold_days": round(float(tr["hold_days"].mean()), 1) if len(tr) else None,
    }
    if benchmark is not None:
        bench = benchmark.reindex(eq.index).ffill().dropna()
        bench_eq = bench / bench.iloc[0]
        out["bench_cagr"] = round(cagr(bench_eq), 4)
        out["bench_sharpe"] = round(sharpe(bench_eq), 2)
        out["bench_max_dd"] = round(max_drawdown(bench_eq), 4)
    return out


def yearly_returns(equity: pd.Series) -> pd.Series:
    yearly = equity.resample("YE").last()
    first = equity.iloc[0]
    rets = yearly.pct_change()
    rets.iloc[0] = yearly.iloc[0] / first - 1
    rets.index = rets.index.year
    return rets.round(4)
