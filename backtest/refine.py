"""Phase 4 refinement round.

Configs below were selected on IN-SAMPLE evidence only (gauntlet variant
sweeps). Each gets exactly one OOS confirmation here — no further iteration
on OOS results, to keep the OOS window honest.

Also: slippage sensitivity for the top candidate, corrected Monte Carlo
drawdowns (daily-return block bootstrap), and a capital-split ensemble test.

Run:  python -m backtest.refine
Writes results/REFINEMENT.md + refine_*.json
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from backtest.data import load_benchmarks, load_panel
from backtest.engine import RESULTS_DIR, run_backtest
from backtest.gauntlet import IS_END, OOS_START, START, build_spec
from backtest.indicators import monte_carlo_drawdown
from backtest.metrics import cagr, max_drawdown, sharpe, summarize

SLIPPAGE = 5.0

# label -> (strategy, params). IS-selected refinements.
CONFIGS = {
    "3ll_refined": ("three_lower_lows", {"stretch": 0.75, "trend_sma": 200}),
    "tom_exit1": ("turn_of_month", {"exit_day_of_month": 1}),
    "double7_lb10": ("double7", {"lookback": 10}),
    "tt_bear": ("turnaround_tuesday", {"_regime": "below_spy200"}),
    "h52_fast_regime": ("high52_breakout", {"_regime": "spy100"}),
}

ENSEMBLE = ["3ll_refined", "tom_exit1", "tt_bear"]  # capital split 50/30/20
ENSEMBLE_WEIGHTS = [0.5, 0.3, 0.2]


def stats_block(res, bench, start, end) -> dict:
    eq = res.equity.loc[start:end] if (start or end) else res.equity
    tr = res.trades
    if start:
        tr = tr[tr["exit_date"] >= pd.Timestamp(start)]
    if end:
        tr = tr[tr["exit_date"] <= pd.Timestamp(end)]
    spy = bench["spy"].reindex(eq.index).ffill().dropna()
    spy_eq = spy / spy.iloc[0]
    wins = tr.loc[tr["ret"] > 0, "ret"].sum()
    losses = -tr.loc[tr["ret"] < 0, "ret"].sum()
    return {
        "cagr": round(cagr(eq), 4),
        "sharpe": round(sharpe(eq), 2),
        "max_dd": round(max_drawdown(eq), 4),
        "trades": int(len(tr)),
        "win_rate": round(float((tr["ret"] > 0).mean()), 3) if len(tr) else None,
        "profit_factor": round(float(wins / losses), 2) if losses > 0 else None,
        "spy_sharpe": round(sharpe(spy_eq), 2),
    }


def main() -> None:
    panel = load_panel()
    bench = load_benchmarks()
    from backtest.strategies.common import spy_regime

    out: dict = {"configs": {}}
    equities: dict[str, pd.Series] = {}

    for label, (strategy, params) in CONFIGS.items():
        params = dict(params)
        if params.get("_regime") == "spy100":
            params.pop("_regime")
            params["regime_ok"] = spy_regime(bench, 100)
        spec = build_spec(panel, bench, strategy, params)
        res = run_backtest(panel, spec, start=START, slippage_bps=SLIPPAGE)
        equities[label] = res.equity
        daily = res.equity.pct_change().dropna().to_numpy()
        dds = monte_carlo_drawdown(daily)
        out["configs"][label] = {
            "spec": spec.name,
            "is": stats_block(res, bench, START, IS_END),
            "oos": stats_block(res, bench, OOS_START, None),
            "full": stats_block(res, bench, None, None),
            "mc_dd_p95": round(float(np.percentile(dds, 95)), 4),
            "mc_dd_p99": round(float(np.percentile(dds, 99)), 4),
        }
        print(f"{label}: OOS {out['configs'][label]['oos']}", flush=True)

    # slippage sensitivity for the top mean-reversion candidate
    out["slippage_sensitivity_3ll"] = {}
    spec = build_spec(panel, bench, *CONFIGS["3ll_refined"])
    for bps in (0.0, 5.0, 10.0, 20.0):
        res = run_backtest(panel, spec, start=START, slippage_bps=bps)
        out["slippage_sensitivity_3ll"][f"{bps:.0f}bps"] = {
            "full_cagr": round(cagr(res.equity), 4),
            "full_sharpe": round(sharpe(res.equity), 2),
        }
        print(f"3ll slippage {bps}bps: {out['slippage_sensitivity_3ll'][f'{bps:.0f}bps']}", flush=True)

    # ensemble: capital split across sleeves (daily-return weighted sum)
    rets = pd.DataFrame({k: equities[k].pct_change() for k in ENSEMBLE}).dropna()
    ens_ret = sum(w * rets[k] for k, w in zip(ENSEMBLE, ENSEMBLE_WEIGHTS))
    ens_eq = (1 + ens_ret).cumprod()
    spy = bench["spy"].reindex(ens_eq.index).ffill()
    blocks = {}
    for label, (s, e) in (("is", (None, IS_END)), ("oos", (OOS_START, None)), ("full", (None, None))):
        eq = ens_eq.loc[s:e]
        spy_eq = (spy.loc[s:e] / spy.loc[s:e].iloc[0]).dropna()
        blocks[label] = {
            "cagr": round(cagr(eq), 4),
            "sharpe": round(sharpe(eq), 2),
            "max_dd": round(max_drawdown(eq), 4),
            "spy_sharpe": round(sharpe(spy_eq), 2),
        }
    dds = monte_carlo_drawdown(ens_ret.to_numpy())
    out["ensemble"] = {
        "components": dict(zip(ENSEMBLE, ENSEMBLE_WEIGHTS)),
        **blocks,
        "mc_dd_p95": round(float(np.percentile(dds, 95)), 4),
    }
    print(f"ensemble: {json.dumps(out['ensemble'], indent=2)}", flush=True)

    (RESULTS_DIR / "refine_results.json").write_text(json.dumps(out, indent=2))

    lines = [
        "# Refinement Round (IS-selected configs, single OOS confirmation each)",
        "",
        f"Slippage {SLIPPAGE} bps/side. IS ends {IS_END}; OOS starts {OOS_START}.",
        "",
        "| Config | IS Sharpe | IS PF | OOS Sharpe | OOS PF | OOS MaxDD | Full CAGR | Full Sharpe | MC p95 DD |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for label, c in out["configs"].items():
        lines.append(
            f"| {label} | {c['is']['sharpe']} | {c['is']['profit_factor']} | {c['oos']['sharpe']} "
            f"| {c['oos']['profit_factor']} | {c['oos']['max_dd']} | {c['full']['cagr']} "
            f"| {c['full']['sharpe']} | {c['mc_dd_p95']} |"
        )
    e = out["ensemble"]
    lines += [
        "",
        f"**Ensemble** ({', '.join(f'{k} {w:.0%}' for k, w in zip(ENSEMBLE, ENSEMBLE_WEIGHTS))}): "
        f"IS Sharpe {e['is']['sharpe']}, OOS Sharpe {e['oos']['sharpe']}, full CAGR {e['full']['cagr']}, "
        f"full MaxDD {e['full']['max_dd']}, MC p95 DD {e['mc_dd_p95']}",
        "",
        "Slippage sensitivity (3ll_refined, full window): "
        + ", ".join(f"{k}: CAGR {v['full_cagr']}, Sharpe {v['full_sharpe']}" for k, v in out["slippage_sensitivity_3ll"].items()),
    ]
    (RESULTS_DIR / "REFINEMENT.md").write_text("\n".join(lines))
    print("\nSaved -> results/REFINEMENT.md")


if __name__ == "__main__":
    main()
