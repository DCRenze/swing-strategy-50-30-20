"""Shared portfolio backtest engine.

Strategies are declarative StrategySpec objects: boolean signal frames plus
execution modes. The engine runs one realistic day loop for all of them, so
every candidate faces identical execution assumptions.

Execution model (daily OHLCV, adjusted prices):
  - entry_mode "next_open":  signal at close of day t -> buy at open of t+1
  - entry_mode "close":      signal at close of day t -> buy at close of t
                             (MOC order from a near-close calculation; matches
                             how the Connors-school sources tested)
  - entry_mode "limit":      signal at close of day t -> limit order working
                             day t+1 at limit_price[t]; fills at
                             min(open, limit) if low[t+1] <= limit
  - exit_mode "close":       exit signal evaluated at close of day t -> sell
                             at close of t
  - exit_mode "next_open":   exit condition seen at close of t -> sell at
                             open of t+1
  - time_stop: exit at close after N trading days held (entry day = day 0)
  - stop_loss_frac: if close < entry_px*(1-frac) -> sell next open
  - stop_at_signal_low: stop level = signal-day low; close < stop -> sell next open

Slippage is charged on both sides (default 5 bps each way). No commissions
(commission-free brokers), but slippage covers spread costs.

Look-ahead guard: all signal frames are *evaluated at the close of their row
date*; the engine only ever acts on information from row t-1 (or row t for
explicit at-the-close modes). Entries never use data after the fill.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


@dataclass
class StrategySpec:
    name: str
    entry_signal: pd.DataFrame              # bool, date x ticker, true at close
    entry_mode: str = "next_open"           # next_open | close | limit
    limit_price: pd.DataFrame | None = None  # required for entry_mode "limit"
    exit_signal: pd.DataFrame | None = None  # bool, date x ticker, true at close
    exit_mode: str = "close"                # close | next_open
    time_stop: int | None = None
    stop_loss_frac: float | None = None
    stop_at_signal_low: bool = False
    rank: pd.DataFrame | None = None        # lower value = higher priority
    max_positions: int = 10
    regime_ok: pd.Series | None = None      # bool, indexed by date
    params: dict = field(default_factory=dict)


@dataclass
class BacktestResult:
    name: str
    equity: pd.Series
    trades: pd.DataFrame
    exposure: pd.Series
    params: dict


def run_backtest(
    panel: dict,
    spec: StrategySpec,
    start: str | None = None,
    end: str | None = None,
    initial_capital: float = 100_000.0,
    slippage_bps: float = 5.0,
    seed: int = 7,
) -> BacktestResult:
    open_, high, low, close = panel["open"], panel["high"], panel["low"], panel["close"]
    dates = close.index
    if start:
        dates = dates[dates >= pd.Timestamp(start)]
    if end:
        dates = dates[dates <= pd.Timestamp(end)]
    tickers = close.columns

    entry = spec.entry_signal.reindex(index=close.index, columns=tickers).fillna(False)
    if spec.regime_ok is not None:
        entry = entry & spec.regime_ok.reindex(close.index).fillna(False).values[:, None]
    exit_sig = (
        spec.exit_signal.reindex(index=close.index, columns=tickers).fillna(False)
        if spec.exit_signal is not None
        else None
    )
    rank = spec.rank.reindex(index=close.index, columns=tickers) if spec.rank is not None else None
    limit = (
        spec.limit_price.reindex(index=close.index, columns=tickers)
        if spec.limit_price is not None
        else None
    )

    # numpy views for speed
    o_v, h_v, l_v, c_v = (df.to_numpy() for df in (open_, high, low, close))
    e_v = entry.to_numpy()
    x_v = exit_sig.to_numpy() if exit_sig is not None else None
    r_v = rank.to_numpy() if rank is not None else None
    lim_v = limit.to_numpy() if limit is not None else None
    date_pos = {d: i for i, d in enumerate(close.index)}
    rng = np.random.default_rng(seed)

    slip = slippage_bps / 10_000.0
    cash = initial_capital
    positions: dict[int, dict] = {}  # ticker idx -> position dict
    trades: list[dict] = []
    equity_out = np.empty(len(dates))
    exposure_out = np.empty(len(dates))

    def sell(ti: int, px: float, di: int, reason: str) -> None:
        nonlocal cash
        pos = positions.pop(ti)
        px = px * (1.0 - slip)
        proceeds = pos["shares"] * px
        cash += proceeds
        trades.append(
            {
                "ticker": tickers[pos["ti"]],
                "entry_date": pos["entry_date"],
                "exit_date": dates[di],
                "entry_px": pos["entry_px"],
                "exit_px": px,
                "ret": px / pos["entry_px"] - 1.0,
                "hold_days": pos["days_held"],
                "reason": reason,
            }
        )

    for di, d in enumerate(dates):
        gi = date_pos[d]  # global row index into panel arrays

        # ---- 1. exits at today's open, decided from yesterday's close ----
        if gi > 0:
            for ti in list(positions):
                pos = positions[ti]
                if pos["entry_gi"] >= gi:  # entered today or later: skip
                    continue
                yi = gi - 1
                flag = False
                if pos.get("pending_exit"):
                    flag = True
                if not flag and spec.exit_mode == "next_open" and x_v is not None and x_v[yi, ti]:
                    flag = True
                if not flag and spec.stop_loss_frac is not None:
                    yc = c_v[yi, ti]
                    if np.isfinite(yc) and yc < pos["entry_px"] * (1.0 - spec.stop_loss_frac):
                        flag = True
                if not flag and pos.get("stop_level") is not None:
                    yc = c_v[yi, ti]
                    if np.isfinite(yc) and yc < pos["stop_level"]:
                        flag = True
                if flag:
                    px = o_v[gi, ti]
                    if np.isfinite(px):
                        sell(ti, px, di, "open_exit")

        # ---- 2. entries ----
        # 2a. next_open / limit orders generated at yesterday's close
        if gi > 0 and spec.entry_mode in ("next_open", "limit"):
            yi = gi - 1
            sig_idx = np.flatnonzero(e_v[yi])
            sig_idx = [ti for ti in sig_idx if ti not in positions]
            if sig_idx:
                if r_v is not None:
                    order = np.argsort([r_v[yi, ti] for ti in sig_idx], kind="stable")
                    sig_idx = [sig_idx[k] for k in order]
                else:
                    rng.shuffle(sig_idx)
                slots = spec.max_positions - len(positions)
                # mark-to-yesterday-close equity for sizing
                eq_now = cash + sum(
                    p["shares"] * (c_v[gi - 1, p["ti"]] if np.isfinite(c_v[gi - 1, p["ti"]]) else p["entry_px"])
                    for p in positions.values()
                )
                target = eq_now / spec.max_positions
                for ti in sig_idx:
                    if slots <= 0 or cash < target * 0.5:
                        break
                    if spec.entry_mode == "next_open":
                        px = o_v[gi, ti]
                        if not np.isfinite(px):
                            continue
                        fill = px * (1.0 + slip)
                    else:  # limit
                        lp = lim_v[yi, ti]
                        lo, op = l_v[gi, ti], o_v[gi, ti]
                        if not (np.isfinite(lp) and np.isfinite(lo) and np.isfinite(op)):
                            continue
                        if lo > lp:
                            continue  # no fill
                        fill = min(op, lp) * (1.0 + slip)
                    invest = min(target, cash)
                    shares = invest / fill
                    cash -= shares * fill
                    positions[ti] = {
                        "ti": ti,
                        "entry_date": d,
                        "entry_gi": gi,
                        "entry_px": fill,
                        "shares": shares,
                        "days_held": 0,
                        "stop_level": (l_v[yi, ti] if spec.stop_at_signal_low else None),
                    }
                    slots -= 1

        # 2b. at-the-close entries from today's signal
        if spec.entry_mode == "close":
            sig_idx = [ti for ti in np.flatnonzero(e_v[gi]) if ti not in positions]
            if sig_idx:
                if r_v is not None:
                    order = np.argsort([r_v[gi, ti] for ti in sig_idx], kind="stable")
                    sig_idx = [sig_idx[k] for k in order]
                else:
                    rng.shuffle(sig_idx)
                slots = spec.max_positions - len(positions)
                eq_now = cash + sum(
                    p["shares"] * (c_v[gi, p["ti"]] if np.isfinite(c_v[gi, p["ti"]]) else p["entry_px"])
                    for p in positions.values()
                )
                target = eq_now / spec.max_positions
                for ti in sig_idx:
                    if slots <= 0 or cash < target * 0.5:
                        break
                    px = c_v[gi, ti]
                    if not np.isfinite(px):
                        continue
                    fill = px * (1.0 + slip)
                    invest = min(target, cash)
                    shares = invest / fill
                    cash -= shares * fill
                    positions[ti] = {
                        "ti": ti,
                        "entry_date": d,
                        "entry_gi": gi,
                        "entry_px": fill,
                        "shares": shares,
                        "days_held": 0,
                        "stop_level": (l_v[gi, ti] if spec.stop_at_signal_low else None),
                    }
                    slots -= 1

        # ---- 3. at-the-close exits ----
        for ti in list(positions):
            pos = positions[ti]
            if pos["entry_gi"] == gi:
                continue  # no same-day round trips
            pos["days_held"] += 1
            exit_now = False
            if spec.exit_mode == "close" and x_v is not None and x_v[gi, ti]:
                exit_now = True
            if not exit_now and spec.time_stop is not None and pos["days_held"] >= spec.time_stop:
                exit_now = True
            if exit_now:
                px = c_v[gi, ti]
                if np.isfinite(px):
                    sell(ti, px, di, "close_exit")
                else:
                    pos["pending_exit"] = True

        # ---- 4. mark to market ----
        pos_val = sum(
            p["shares"] * (c_v[gi, p["ti"]] if np.isfinite(c_v[gi, p["ti"]]) else p["entry_px"])
            for p in positions.values()
        )
        equity_out[di] = cash + pos_val
        exposure_out[di] = pos_val / equity_out[di] if equity_out[di] > 0 else 0.0

    equity = pd.Series(equity_out, index=dates, name="equity")
    exposure = pd.Series(exposure_out, index=dates, name="exposure")
    trades_df = pd.DataFrame(trades)
    return BacktestResult(spec.name, equity, trades_df, exposure, dict(spec.params))
