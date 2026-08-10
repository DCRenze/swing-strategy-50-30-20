"""How much open profit does a sleeve give back before it exits?

Motivated by a live observation (David, Aug 2026): ACHC ran to a large open gain
and then handed part of it back before Sleeve H's 15-day time stop fired. Sleeve H
has **no profit target and no trailing stop** -- the only exits are a 5% stop
measured from the ENTRY price (it never trails) and the 15-day time stop -- so by
construction 100% of an open gain is exposed until day 15. This script measures how
much that costs across every trade in a saved ledger, instead of one anecdote.

For each trade it computes, on closes between entry and exit:
  MFE      max favourable excursion - the best unrealised return reached
  giveback MFE - realised return, i.e. profit handed back before the exit fired

It then runs two INDICATIVE what-ifs on the same trades:
  profit target   exit at the next open once a close is >= T% above entry
  trailing stop   exit at the next open once a close is >= R% below the running peak

    python -m backtest.excursion                              # sleeve H, default
    python -m backtest.excursion --trades results/ensemble_3ll_refined_trades.csv
    python -m backtest.excursion --targets 10,15,20 --trails 5,8,10

*** These what-ifs are NOT a backtest. *** They re-price existing trades in
isolation: they do not model slot competition, do not redeploy the capital an early
exit frees up, and cannot create the trades a different exit rule would have taken
later. Read them as "is this worth putting through the gauntlet?", never as a
validated result. Deploying any of it requires backtest/gauntlet.py + refine.py per
the golden rule in CLAUDE.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.data import load_panel  # noqa: E402

DEFAULT_TRADES = ROOT / "results" / "gauntlet_high52_breakout_trades.csv"


def per_trade_paths(trades: pd.DataFrame, close: pd.DataFrame):
    """Yield (row, closes-between-entry-and-exit, open-price-series) per trade."""
    idx = close.index
    for row in trades.itertuples():
        if row.ticker not in close.columns:
            continue
        lo = idx.searchsorted(row.entry_date, "right")   # first close AFTER entry
        hi = idx.searchsorted(row.exit_date, "right")
        seg = close[row.ticker].iloc[lo:hi].dropna()
        if len(seg):
            yield row, seg


def analyse(trades: pd.DataFrame, panel: dict, targets, trails) -> None:
    close, open_ = panel["close"], panel["open"]
    idx = close.index
    recs, sims = [], []
    for row, seg in per_trade_paths(trades, close):
        rets = seg / row.entry_px - 1.0
        mfe = float(rets.max())
        recs.append({"ticker": row.ticker, "entry": row.entry_date, "ret": row.ret,
                     "mfe": mfe, "giveback": mfe - row.ret, "hold": row.hold_days})
        # --- indicative what-ifs, exiting at the open after the trigger close ---
        sim = {"ret": row.ret}
        for t in targets:
            hit = rets[rets >= t / 100.0]
            sim[f"pt{t}"] = _exit_next_open(row, hit, open_, idx) if len(hit) else row.ret
        peak = seg.cummax()
        dd = seg / peak - 1.0
        for r in trails:
            hit = dd[dd <= -r / 100.0]
            sim[f"ts{r}"] = _exit_next_open(row, hit, open_, idx) if len(hit) else row.ret
        sims.append(sim)

    d = pd.DataFrame(recs)
    if d.empty:
        print("No trades matched the panel - is data/ built? (python -m backtest.data)")
        return
    win = d[d.ret > 0]
    print(f"\n=== excursion: {len(d)} trades ===")
    print(f"  realised return   mean {d.ret.mean():+.2%}   median {d.ret.median():+.2%}")
    print(f"  peak open gain    mean {d.mfe.mean():+.2%}   median {d.mfe.median():+.2%}")
    print(f"  GIVEBACK          mean {d.giveback.mean():.2%}   median {d.giveback.median():.2%}")
    print(f"  winners only ({len(win)}): peak {win.mfe.mean():+.2%} -> exit {win.ret.mean():+.2%}"
          f"  (gave back {win.giveback.mean():.2%}, "
          f"{win.giveback.mean() / win.mfe.mean():.0%} of the peak)")
    for thr in (0.10, 0.15, 0.20):
        got = d[d.mfe >= thr]
        if len(got):
            kept = got[got.ret >= thr]
            print(f"  reached +{thr:.0%} at some point: {len(got):5d} trades "
                  f"({len(got)/len(d):5.1%}) - only {len(kept)/len(got):5.1%} still held +{thr:.0%} at exit; "
                  f"they exited at {got.ret.mean():+.2%} on average")

    s = pd.DataFrame(sims)
    print("\n=== indicative what-ifs (NOT a backtest - see module docstring) ===")
    print(f"  {'rule':16s}{'mean ret':>10}{'vs actual':>11}{'win rate':>10}")
    print(f"  {'actual':16s}{s.ret.mean():>10.2%}{'':>11}{(s.ret > 0).mean():>10.1%}")
    for col in [c for c in s.columns if c != "ret"]:
        kind = "profit target" if col.startswith("pt") else "trailing stop"
        pct = col[2:]
        print(f"  {kind + ' ' + pct + '%':16s}{s[col].mean():>10.2%}"
              f"{s[col].mean() - s.ret.mean():>+11.2%}{(s[col] > 0).mean():>10.1%}")
    print("\n  Reminder: freed capital is not redeployed here, so these understate any rule")
    print("  that exits early. Treat a clear win as a reason to run the gauntlet, not as evidence.")


def _exit_next_open(row, hit: pd.Series, open_: pd.DataFrame, idx) -> float:
    """Return realised return if we sold at the open after `hit`'s first trigger close."""
    trigger = hit.index[0]
    pos = idx.searchsorted(trigger, "right")
    if pos >= len(idx):
        return float(row.ret)
    px = open_[row.ticker].iloc[pos]
    if not np.isfinite(px):
        return float(row.ret)
    return float(px / row.entry_px - 1.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", default=str(DEFAULT_TRADES))
    ap.add_argument("--start", default=None, help="only trades entered on/after this date")
    ap.add_argument("--targets", default="10,15,20", help="profit-target %% to test")
    ap.add_argument("--trails", default="5,8,10", help="trailing-stop %% to test")
    a = ap.parse_args()

    trades = pd.read_csv(a.trades, parse_dates=["entry_date", "exit_date"])
    if a.start:
        trades = trades[trades.entry_date >= a.start]
    print(f"ledger: {a.trades}  ({len(trades)} trades)")
    analyse(trades, load_panel(),
            [float(x) for x in a.targets.split(",")],
            [float(x) for x in a.trails.split(",")])


if __name__ == "__main__":
    main()
