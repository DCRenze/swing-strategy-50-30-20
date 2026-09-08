"""Phase 4: does entry-day breadth predict Sleeve H trade quality?

Pre-registered in results/BREADTH_HYPOTHESIS.md - read that first; the pass and
kill criteria were fixed before this ran.

H1: a session on which many liquid names simultaneously print a new 252-day
closing high on above-average volume is a market-breadth thrust, and breakouts
bought into that thrust beat isolated breakouts. So requiring a minimum count of
same-day H signals - and taking none when the count falls short - should raise
Sleeve H's profit factor without touching any exit.

This is entry selection only. Lookback, stop, time stop, regime gate, slot count
and ranking all stay at their validated values; min_same_day_signals=None
reproduces the deployed config exactly.

Discipline (same as gauntlet.py / refine.py / phase2_upside.py):
  Stage 1  --stage is    every threshold on IN-SAMPLE only (2005-06..2022-12).
                         Selection happens here.
  Stage 2  --stage oos --confirm LABEL [LABEL...]
                         one OOS confirmation for the IS-selected finalists.

Splitting the stages is the point: OOS is spent once, on configs chosen without
seeing it. Running stage 2 across the whole grid would burn it.

A threshold has to clear two bars, not one:
  - the H sleeve itself must improve, and
  - the deployed 60/40 A/H ensemble must improve, since diversification is what
    clears the gauntlet (GAUNTLET_SUMMARY.md) - a sleeve that gets better while
    decorrelating less can still make the book worse.

Run:  python -m backtest.phase4_breadth --stage is
      python -m backtest.phase4_breadth --stage oos --confirm breadth3
"""

from __future__ import annotations

import argparse
import json
import time

import pandas as pd

from backtest.data import load_benchmarks, load_panel
from backtest.engine import RESULTS_DIR, run_backtest
from backtest.gauntlet import IS_END, OOS_START, START, build_spec
from backtest.metrics import cagr, max_drawdown, profit_factor, sharpe
from backtest.strategies.common import spy_regime

SLIPPAGE = 5.0

# Sleeve A is held fixed at its validated config; only H varies.
SLEEVE_A = ("three_lower_lows", {"stretch": 0.75, "trend_sma": 200})
A_WEIGHT, H_WEIGHT = 0.60, 0.40

# label -> params layered on the validated H baseline.
#
# Grid set from the SIGNAL distribution, not from any performance result: the
# raw H signal pool runs a mean of 9.9 names/session (median 7, p75 14, p90 23,
# max 156), because the universe throws far more breakouts than the 10 slots can
# take. A threshold of 3 would gate out only 15% of sessions - it would barely be
# a treatment. The grid therefore spans the actual quantiles, from p25 (2) to
# roughly p90 (25), so a plateau has room to show both edges instead of sitting
# on the grid boundary.
#
# NOTE the trap this exposes, and which BREADTH_HYPOTHESIS.md pre-registered as
# "the obvious way this is wrong": the bucket table that motivated H1 counted
# entries per day among trades ACTUALLY TAKEN, which the engine caps at 10 slots.
# A "10-entry day" there means "10 slots were free and >=10 signals existed" - it
# is partly a measure of free capital, not of breadth. This sweep is what
# separates the two.
VARIANTS: list[tuple[str, dict]] = [
    ("baseline", {}),
    ("breadth2", {"min_same_day_signals": 2}),
    ("breadth5", {"min_same_day_signals": 5}),
    ("breadth8", {"min_same_day_signals": 8}),
    ("breadth12", {"min_same_day_signals": 12}),
    ("breadth16", {"min_same_day_signals": 16}),
    ("breadth20", {"min_same_day_signals": 20}),
    ("breadth25", {"min_same_day_signals": 25}),
]


def stats(equity: pd.Series, trades: pd.DataFrame, spy: pd.Series) -> dict:
    spy_eq = spy.reindex(equity.index).ffill().dropna()
    spy_eq = spy_eq / spy_eq.iloc[0]
    return {
        "cagr": round(cagr(equity), 4),
        "sharpe": round(sharpe(equity), 2),
        "max_dd": round(max_drawdown(equity), 4),
        "profit_factor": round(profit_factor(trades), 2) if len(trades) else None,
        "trades": int(len(trades)),
        "win_rate": round(float((trades["ret"] > 0).mean()), 3) if len(trades) else None,
        "avg_hold_days": round(float(trades["hold_days"].mean()), 1) if len(trades) else None,
        "spy_sharpe": round(sharpe(spy_eq), 2),
    }


def blend(a_eq: pd.Series, h_eq: pd.Series) -> pd.Series:
    """Daily-return capital split, matching refine.compute_ensemble."""
    rets = pd.DataFrame({"a": a_eq.pct_change(), "h": h_eq.pct_change()}).dropna()
    ens = A_WEIGHT * rets["a"] + H_WEIGHT * rets["h"]
    return (1 + ens).cumprod()


def run(stage: str, confirm: list[str]) -> dict:
    panel = load_panel()
    bench = load_benchmarks()
    spy = bench["spy"]
    h_regime = spy_regime(bench, 100)

    if stage == "is":
        labels = [lb for lb, _ in VARIANTS]
        w_start, w_end, tag = START, IS_END, "in-sample"
    else:
        labels = ["baseline"] + [c for c in confirm if c != "baseline"]
        unknown = set(labels) - {lb for lb, _ in VARIANTS}
        if unknown:
            raise SystemExit(f"unknown variant(s): {sorted(unknown)}")
        w_start, w_end, tag = OOS_START, None, "out-of-sample"

    print(f"Phase 4 breadth sweep - {tag} window, {len(labels)} config(s)", flush=True)

    a_spec = build_spec(panel, bench, *SLEEVE_A)
    a_res = run_backtest(panel, a_spec, start=START, slippage_bps=SLIPPAGE)
    print(f"  sleeve A fixed at {a_spec.name}", flush=True)

    out: dict = {"stage": stage, "window": {"start": w_start, "end": w_end},
                 "slippage_bps": SLIPPAGE, "sleeve_a": a_spec.name, "variants": {}}
    params_by_label = dict(VARIANTS)

    for label in labels:
        t0 = time.time()
        params = dict(params_by_label[label])
        params["regime_ok"] = h_regime
        spec = build_spec(panel, bench, "high52_breakout", params)
        res = run_backtest(panel, spec, start=START, slippage_bps=SLIPPAGE)

        h_eq = res.equity.loc[w_start:w_end]
        ens_eq = blend(a_res.equity, res.equity).loc[w_start:w_end]
        trades = res.trades
        if len(trades):
            mask = pd.Series(True, index=trades.index)
            if w_start:
                mask &= trades["exit_date"] >= pd.Timestamp(w_start)
            if w_end:
                mask &= trades["exit_date"] <= pd.Timestamp(w_end)
            trades = trades[mask]

        # Diversification check - see phase2_upside for why both correlations are
        # reported. The winsorized figure is the one to compare across variants.
        rets = pd.DataFrame({"a": a_res.equity.pct_change(),
                             "h": res.equity.pct_change()}).dropna()
        rets = rets.loc[w_start:w_end]
        wins = rets.clip(lower=rets.quantile(0.01), upper=rets.quantile(0.99), axis=1)

        # How much of the calendar the gate actually removes - the exposure cost
        # that has to be paid for by better retained trades.
        entry_days = int(res.trades["entry_date"].nunique()) if len(res.trades) else 0

        out["variants"][label] = {
            "spec": spec.name,
            "sleeve_h": stats(h_eq, trades, spy),
            "ensemble": {
                "cagr": round(cagr(ens_eq), 4),
                "sharpe": round(sharpe(ens_eq), 2),
                "max_dd": round(max_drawdown(ens_eq), 4),
            },
            "diversification": {
                "h_exposure": round(float(res.exposure.loc[w_start:w_end].mean()), 3),
                "corr_a_h_pearson": round(float(rets["a"].corr(rets["h"])), 3),
                "corr_a_h_winsor": round(float(wins["a"].corr(wins["h"])), 3),
                "entry_days_full": entry_days,
            },
        }
        v = out["variants"][label]
        h, e, dv = v["sleeve_h"], v["ensemble"], v["diversification"]
        print(f"  {label:12} H: PF {h['profit_factor']} win {h['win_rate']} "
              f"Sharpe {h['sharpe']} DD {h['max_dd']:.1%} n={h['trades']} "
              f"expo {dv['h_exposure']:.2f} | ens CAGR {e['cagr']:.2%} "
              f"Sharpe {e['sharpe']} DD {e['max_dd']:.1%} | corrW "
              f"{dv['corr_a_h_winsor']} ({time.time() - t0:.0f}s)", flush=True)
    return out


def write_report(out: dict) -> None:
    stage = out["stage"]
    base = out["variants"]["baseline"]
    tag = "IS" if stage == "is" else "OOS"
    w = out["window"]
    lines = [
        f"# Phase 4 breadth sweep - {'in-sample' if stage == 'is' else 'out-of-sample'} results",
        "",
        f"Window {w['start']} -> {w['end'] or 'present'}, {out['slippage_bps']} bps/side.",
        f"Sleeve A fixed at `{out['sleeve_a']}`; deployed 60/40 A/H blend.",
        "",
        "Pre-registration and pass/kill criteria: `BREADTH_HYPOTHESIS.md`.",
        "",
        "`baseline` = the deployed H config (no breadth gate). Every other row changes",
        "only `min_same_day_signals`; no exit, stop, lookback, slot count or ranking moves.",
        "",
        "| Config | H PF | H win% | H Sharpe | H maxDD | H trades | H expo | Ens CAGR | Ens Sharpe | Ens maxDD | corrW |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for label, v in out["variants"].items():
        h, e, dv = v["sleeve_h"], v["ensemble"], v["diversification"]
        lines.append(
            f"| {'**' + label + '**' if label == 'baseline' else label} "
            f"| {h['profit_factor']} | {h['win_rate']:.1%} | {h['sharpe']} "
            f"| {h['max_dd']:.1%} | {h['trades']} | {dv['h_exposure']:.2f} "
            f"| {e['cagr']:.2%} | {e['sharpe']} | {e['max_dd']:.1%} "
            f"| {dv['corr_a_h_winsor']} |"
        )
    lines += [
        "",
        "## Read this before drawing a conclusion",
        "",
        "**Profit factor rising while ensemble CAGR falls is the expected shape, not a win.**",
        "A breadth gate removes sessions, so it removes trades and idles capital. The retained",
        "trades have to be enough better to pay for the lost compounding. Criterion 3 in the",
        "pre-registration (ensemble Sharpe) is the one that decides, not H's profit factor.",
        "",
        "**A threshold that works with worse neighbours on both sides is an artifact.** The",
        "Phase 2 finalists both showed clean in-sample plateaus and still flipped sign out of",
        "sample; a lone in-sample spike is weaker evidence than that, not stronger.",
    ]
    if stage == "oos":
        lines += [
            "",
            "## OOS confirmation",
            "",
            f"Baseline OOS: PF {base['sleeve_h']['profit_factor']}, "
            f"ensemble Sharpe {base['ensemble']['sharpe']}, "
            f"ensemble maxDD {base['ensemble']['max_dd']:.1%}.",
            "",
            "OOS is spent. Any further iteration on these numbers invalidates the window.",
        ]
    path = RESULTS_DIR / f"PHASE4_BREADTH_{tag}.md"
    path.write_text("\n".join(lines) + "\n")
    print(f"wrote {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["is", "oos"], required=True)
    ap.add_argument("--confirm", nargs="*", default=[],
                    help="stage 2 only: IS-selected labels to confirm on OOS")
    args = ap.parse_args()
    if args.stage == "oos" and not args.confirm:
        raise SystemExit("--stage oos requires --confirm LABEL [LABEL...]")

    out = run(args.stage, args.confirm)
    tag = "is" if args.stage == "is" else "oos"
    (RESULTS_DIR / f"phase4_breadth_{tag}.json").write_text(json.dumps(out, indent=2))
    write_report(out)


if __name__ == "__main__":
    main()
