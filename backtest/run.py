"""CLI runner: backtest a named strategy and write results to results/.

Usage:
  python -m backtest.run band_ibs --param ticker=QQQ --start 2005-06-01
  python -m backtest.run rsi2_pullback --param cumulative=35 --end 2022-12-31
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

from backtest.data import load_benchmarks, load_panel
from backtest.engine import RESULTS_DIR, run_backtest
from backtest.metrics import summarize, yearly_returns

STRATEGIES = [
    "rsi2_pullback",
    "three_lower_lows",
    "band_ibs",
    "double7",
    "momentum_burst",
    "high52_breakout",
    "turnaround_tuesday",
    "turn_of_month",
]


def parse_value(v: str):
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lower() in ("none", "null"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("strategy", choices=STRATEGIES)
    ap.add_argument("--param", action="append", default=[], help="key=value, repeatable")
    ap.add_argument("--start", default="2005-06-01")  # ~100 sessions of indicator warmup
    ap.add_argument("--end", default=None)
    ap.add_argument("--slippage-bps", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--tag", default="", help="suffix for the results filename")
    args = ap.parse_args()

    params = {}
    for p in args.param:
        k, _, v = p.partition("=")
        params[k] = parse_value(v)

    panel = load_panel()
    bench = load_benchmarks()
    mod = importlib.import_module(f"backtest.strategies.{args.strategy}")
    spec = mod.build(panel, bench, **params)

    res = run_backtest(
        panel, spec, start=args.start, end=args.end,
        slippage_bps=args.slippage_bps, seed=args.seed,
    )
    stats = summarize(res, benchmark=bench["spy"])
    stats["slippage_bps"] = args.slippage_bps
    stats["params"] = res.params
    stats["yearly"] = {str(k): v for k, v in yearly_returns(res.equity).items()}

    RESULTS_DIR.mkdir(exist_ok=True)
    safe = res.name.replace("[", "_").replace("]", "").replace(",", "-").replace("%", "pct")
    tag = f"_{args.tag}" if args.tag else ""
    out = RESULTS_DIR / f"{safe}{tag}.json"
    out.write_text(json.dumps(stats, indent=2))
    res.trades.to_csv(RESULTS_DIR / f"{safe}{tag}_trades.csv", index=False)
    res.equity.to_csv(RESULTS_DIR / f"{safe}{tag}_equity.csv")

    print(json.dumps(stats, indent=2))
    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
