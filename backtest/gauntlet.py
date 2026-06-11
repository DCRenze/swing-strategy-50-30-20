"""Phase 4 validation gauntlet.

For each Tier-1 strategy:
  1. Baseline config run on full / in-sample / out-of-sample windows
     (IS = 2005-06..2022-12, OOS = 2023-01..present — OOS is never used
     for parameter selection)
  2. Parameter-sensitivity variants run on IS only (plateau check)
  3. Regime slices computed from the full-window equity curve
     (2020 crash year, 2022 bear, 2023-25 chop)
  4. Trade-resampling Monte Carlo drawdown distribution (full window)

Pass bar (from the project plan): OOS profit factor > 1.3, max DD < 25%,
>= 100 trades full-window, OOS Sharpe >= OOS SPY Sharpe.

Run:  python -m backtest.gauntlet            # everything (~30-60 min)
      python -m backtest.gauntlet rsi2_pullback double7   # subset

Writes results/gauntlet_<strategy>.json incrementally and a final
results/GAUNTLET_SUMMARY.md.
"""

from __future__ import annotations

import importlib
import json
import sys
import time

import numpy as np

from backtest.data import load_benchmarks, load_panel
from backtest.engine import RESULTS_DIR, run_backtest
from backtest.indicators import monte_carlo_drawdown
from backtest.metrics import max_drawdown, sharpe, summarize
from backtest.strategies.common import spy_regime

START = "2005-06-01"
IS_END = "2022-12-31"
OOS_START = "2023-01-01"
SLIPPAGE = 5.0

REGIME_SLICES = {
    "2020_crash_recovery": ("2020-01-01", "2020-12-31"),
    "2022_bear": ("2022-01-01", "2022-12-31"),
    "2023_25_chop": ("2023-01-01", "2025-12-31"),
}

# variants: list of (label, param-overrides). Baseline = {}.
PLAN: dict[str, dict] = {
    "rsi2_pullback": {
        "baseline": {},
        "variants": [
            ("rsi5", {"rsi_entry": 5.0}),
            ("cum35", {"cumulative": 35.0}),
            ("cum10", {"cumulative": 10.0}),
            ("exit_rsi65", {"exit_rule": "rsi65"}),
            ("sma100", {"trend_sma": 100}),
            ("next_open", {"entry_mode": "next_open"}),
        ],
    },
    "three_lower_lows": {
        "baseline": {},
        "variants": [
            ("stretch0.25", {"stretch": 0.25}),
            ("stretch0.75", {"stretch": 0.75}),
            ("stretch1.0", {"stretch": 1.0}),
            ("sma200", {"trend_sma": 200}),
        ],
    },
    "band_ibs": {
        "baseline": {},  # basket port, next_open
        "variants": [
            ("mult2.0", {"band_mult": 2.0}),
            ("mult3.0", {"band_mult": 3.0}),
            ("ibs0.25", {"ibs_max": 0.25}),
            ("ibs0.4", {"ibs_max": 0.4}),
            ("no_disaster", {"disaster_sma": None}),
        ],
    },
    "double7": {
        "baseline": {},
        "variants": [
            ("lb5", {"lookback": 5}),
            ("lb10", {"lookback": 10}),
            ("exit_sma5", {"exit_rule": "sma5"}),
        ],
    },
    "momentum_burst": {
        "baseline": {},
        "variants": [
            ("burst3pct", {"burst_pct": 0.03}),
            ("burst5pct", {"burst_pct": 0.05}),
            ("hold3", {"hold_days": 3}),
            ("ibs0.5", {"min_ibs": 0.5}),
            ("regime_on", {"_regime": "spy200"}),
        ],
    },
    "high52_breakout": {
        "baseline": {},
        "variants": [
            ("hold10", {"hold_days": 10}),
            ("stop3pct", {"stop_frac": 0.03}),
            ("stop8pct", {"stop_frac": 0.08}),
            ("no_vol", {"vol_confirm": False}),
            ("lb126", {"lookback": 126}),
        ],
    },
    "turnaround_tuesday": {
        "baseline": {},
        "variants": [
            ("ibs0.3", {"ibs_max": 0.3}),
            ("ts3", {"time_stop": 3}),
            ("ts5", {"time_stop": 5}),
            ("bull_only", {"_regime": "spy200"}),
            ("bear_only", {"_regime": "below_spy200"}),
        ],
    },
    "turn_of_month": {
        "baseline": {},
        "variants": [
            ("entry4", {"entry_days_before_eom": 4}),
            ("exit1", {"exit_day_of_month": 1}),
            ("top50", {"top_n": 50}),
        ],
    },
}


def build_spec(panel, bench, strategy: str, params: dict):
    params = dict(params)
    regime_key = params.pop("_regime", None)
    if regime_key == "spy200":
        params["regime_ok"] = spy_regime(bench, 200)
    elif regime_key == "below_spy200":
        params["regime_ok"] = ~spy_regime(bench, 200)
    mod = importlib.import_module(f"backtest.strategies.{strategy}")
    return mod.build(panel, bench, **params)


def windowed_stats(panel, bench, spec, start, end) -> dict:
    res = run_backtest(panel, spec, start=start, end=end, slippage_bps=SLIPPAGE)
    return summarize(res, benchmark=bench["spy"]), res


def slice_equity(equity, start, end) -> dict:
    eq = equity.loc[start:end]
    if len(eq) < 10:
        return {}
    return {
        "return": round(float(eq.iloc[-1] / eq.iloc[0] - 1), 4),
        "max_dd": round(max_drawdown(eq), 4),
        "sharpe": round(sharpe(eq), 2),
    }


def gauntlet_one(panel, bench, strategy: str) -> dict:
    plan = PLAN[strategy]
    out: dict = {"strategy": strategy, "windows": {}, "variants": {}, "regimes": {}}
    t0 = time.time()

    spec = build_spec(panel, bench, strategy, plan["baseline"])
    out["baseline_name"] = spec.name

    full_stats, full_res = windowed_stats(panel, bench, spec, START, None)
    is_stats, _ = windowed_stats(panel, bench, spec, START, IS_END)
    oos_stats, _ = windowed_stats(panel, bench, spec, OOS_START, None)
    out["windows"] = {"full": full_stats, "is": is_stats, "oos": oos_stats}

    for label, (s, e) in REGIME_SLICES.items():
        out["regimes"][label] = slice_equity(full_res.equity, s, e)

    if len(full_res.trades) >= 20:
        dds = monte_carlo_drawdown(full_res.equity.pct_change().dropna().to_numpy())
        out["mc_drawdown"] = {
            "p50": round(float(np.percentile(dds, 50)), 4),
            "p95": round(float(np.percentile(dds, 95)), 4),
            "p99": round(float(np.percentile(dds, 99)), 4),
        }

    for label, overrides in plan["variants"]:
        vspec = build_spec(panel, bench, strategy, {**plan["baseline"], **overrides})
        vstats, _ = windowed_stats(panel, bench, vspec, START, IS_END)
        out["variants"][label] = {
            k: vstats.get(k)
            for k in ("cagr", "sharpe", "max_dd", "trades", "win_rate", "avg_ret", "profit_factor", "exposure")
        }
        print(f"    variant {label}: sharpe={vstats['sharpe']} pf={vstats['profit_factor']}", flush=True)

    oos = out["windows"]["oos"]
    out["pass_bar"] = {
        "oos_pf_gt_1.3": (oos.get("profit_factor") or 0) > 1.3,
        "oos_maxdd_lt_25pct": (oos.get("max_dd") or -1) > -0.25,
        "full_trades_gte_100": full_stats["trades"] >= 100,
        "oos_sharpe_beats_spy": (oos.get("sharpe") or 0) >= (oos.get("bench_sharpe") or 0),
    }
    out["pass_all"] = all(out["pass_bar"].values())
    out["runtime_s"] = round(time.time() - t0, 1)

    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / f"gauntlet_{strategy}.json").write_text(json.dumps(out, indent=2))
    full_res.trades.to_csv(RESULTS_DIR / f"gauntlet_{strategy}_trades.csv", index=False)
    full_res.equity.to_csv(RESULTS_DIR / f"gauntlet_{strategy}_equity.csv")
    return out


def write_summary(results: list[dict]) -> None:
    lines = [
        "# Gauntlet Summary",
        "",
        f"Windows: full {START}+, IS ends {IS_END}, OOS starts {OOS_START}. Slippage {SLIPPAGE} bps/side.",
        "",
        "| Strategy | OOS PF | OOS Sharpe | OOS MaxDD | OOS SPY Sharpe | Full trades | Full CAGR | Full MaxDD | MC p95 DD | PASS |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        oos, full = r["windows"]["oos"], r["windows"]["full"]
        mc = r.get("mc_drawdown", {})
        lines.append(
            f"| {r['strategy']} | {oos.get('profit_factor')} | {oos.get('sharpe')} | {oos.get('max_dd')} "
            f"| {oos.get('bench_sharpe')} | {full['trades']} | {full['cagr']} | {full['max_dd']} "
            f"| {mc.get('p95')} | {'PASS' if r['pass_all'] else 'fail'} |"
        )
    lines += ["", "Per-strategy details: `gauntlet_<strategy>.json` (windows, variants, regimes, pass bar)."]
    (RESULTS_DIR / "GAUNTLET_SUMMARY.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main() -> None:
    strategies = sys.argv[1:] or list(PLAN)
    panel = load_panel()
    bench = load_benchmarks()
    results = []
    for s in strategies:
        print(f"\n=== {s} ===", flush=True)
        r = gauntlet_one(panel, bench, s)
        oos = r["windows"]["oos"]
        print(
            f"  baseline OOS: pf={oos.get('profit_factor')} sharpe={oos.get('sharpe')} "
            f"dd={oos.get('max_dd')} | pass={r['pass_all']} ({r['runtime_s']}s)",
            flush=True,
        )
        results.append(r)
    write_summary(results)


if __name__ == "__main__":
    main()
