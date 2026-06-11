"""Regenerate the chosen ensemble, save component + combined equity curves and a chart."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from backtest.data import load_benchmarks, load_panel
from backtest.engine import RESULTS_DIR, run_backtest
from backtest.gauntlet import START, build_spec
from backtest.refine import CONFIGS, ENSEMBLE, ENSEMBLE_WEIGHTS, SLIPPAGE


def main() -> None:
    panel = load_panel()
    bench = load_benchmarks()
    eqs = {}
    for label in ENSEMBLE:
        spec = build_spec(panel, bench, *CONFIGS[label])
        res = run_backtest(panel, spec, start=START, slippage_bps=SLIPPAGE)
        eqs[label] = res.equity
        res.trades.to_csv(RESULTS_DIR / f"ensemble_{label}_trades.csv", index=False)

    rets = pd.DataFrame({k: v.pct_change() for k, v in eqs.items()}).dropna()
    ens_ret = sum(w * rets[k] for k, w in zip(ENSEMBLE, ENSEMBLE_WEIGHTS))
    ens_eq = (1 + ens_ret).cumprod()
    df = pd.DataFrame({**{k: v / v.iloc[0] for k, v in eqs.items()}, "ensemble": ens_eq})
    spy = bench["spy"].reindex(df.index).ffill()
    df["SPY"] = spy / spy.iloc[0]
    df.to_csv(RESULTS_DIR / "ensemble_equity.csv")

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    for col, lw in [("ensemble", 2.2), ("SPY", 1.6)]:
        ax1.plot(df.index, df[col], label=col, linewidth=lw)
    for col in ENSEMBLE:
        ax1.plot(df.index, df[col], label=col, linewidth=0.9, alpha=0.55)
    ax1.set_yscale("log")
    ax1.legend(loc="upper left", fontsize=9)
    ax1.set_title("Ensemble (3ll 50% / turn-of-month 30% / TT-bear 20%) vs SPY — growth of $1, log scale")
    dd = ens_eq / ens_eq.cummax() - 1
    spy_dd = df["SPY"] / df["SPY"].cummax() - 1
    ax2.fill_between(dd.index, dd, 0, alpha=0.6, label="ensemble DD")
    ax2.plot(spy_dd.index, spy_dd, linewidth=0.8, alpha=0.7, label="SPY DD")
    ax2.axvline(pd.Timestamp("2023-01-01"), linestyle="--", linewidth=1)
    ax1.axvline(pd.Timestamp("2023-01-01"), linestyle="--", linewidth=1)
    ax2.legend(loc="lower left", fontsize=8)
    ax2.set_title("Drawdown (dashed line = OOS boundary)", fontsize=9)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "ensemble_equity.png", dpi=130)
    print(f"Saved -> {RESULTS_DIR / 'ensemble_equity.png'} and ensemble_equity.csv")


if __name__ == "__main__":
    main()
