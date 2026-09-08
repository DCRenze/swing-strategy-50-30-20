"""Phase 6: does stacking entry-confirmation filters buy a higher win rate?

Pre-registered in results/STRICTNESS_HYPOTHESIS.md - read that first.

The question David asked: pick only the very best setups, confirmed by several
indicators at once, so the trade "almost always" works. This measures exactly
that - and, critically, measures what it COSTS, because a filter that removes
99% of signals also removes 99% of the compounding.

Every filter here varies BETWEEN NAMES ON THE SAME DAY. That is the test Phase 4
(same-day breadth) and Phase 5 (entry ATR) both failed: both features mostly
varied between days, so filtering on them just switched the strategy off in
certain market conditions. RSI(2), IBS, trend strength, lower-low depth and
Bollinger position all compare a stock to itself, so they survive that test.

Entry selection only. Stretch, trend SMA, the limit offset, the exit rule, the
15-day time stop and the slot count all stay at validated values; the empty
config reproduces the deployed baseline exactly.

Run:  python -m backtest.phase6_strictness --stage is
      python -m backtest.phase6_strictness --stage oos --confirm rsi5
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

# Sleeve H is held fixed at its validated config; only A varies.
SLEEVE_H = ("high52_breakout", {"_regime": "spy100"})
A_WEIGHT, H_WEIGHT = 0.60, 0.40

# label -> params layered on the validated A baseline. Grouped from loosest to
# strictest so the report reads as a frontier: what does each extra filter buy,
# and what does it cost?
VARIANTS: list[tuple[str, dict]] = [
    ("baseline", {}),
    # --- one filter at a time
    ("rsi5", {"max_rsi2": 5.0}),
    ("ibs0.2", {"max_ibs": 0.20}),
    ("bband", {"below_lower_band": True}),
    ("trend10", {"min_trend_strength": 0.10}),
    ("ll4", {"n_lower_lows": 4}),
    ("ll5", {"n_lower_lows": 5}),
    # --- stacked, progressively stricter
    ("rsi5+ibs", {"max_rsi2": 5.0, "max_ibs": 0.20}),
    ("rsi5+ibs+bb", {"max_rsi2": 5.0, "max_ibs": 0.20, "below_lower_band": True}),
    ("rsi5+ibs+bb+ll4", {"max_rsi2": 5.0, "max_ibs": 0.20, "below_lower_band": True,
                         "n_lower_lows": 4}),
    # --- the kitchen sink: every confirmation at once, ~1% of signals survive
    ("everything", {"max_rsi2": 5.0, "max_ibs": 0.20, "below_lower_band": True,
                    "n_lower_lows": 4, "min_trend_strength": 0.10}),
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

    if stage == "is":
        labels = [lb for lb, _ in VARIANTS]
        w_start, w_end, tag = START, IS_END, "in-sample"
    else:
        labels = ["baseline"] + [c for c in confirm if c != "baseline"]
        unknown = set(labels) - {lb for lb, _ in VARIANTS}
        if unknown:
            raise SystemExit(f"unknown variant(s): {sorted(unknown)}")
        w_start, w_end, tag = OOS_START, None, "out-of-sample"

    print(f"Phase 6 strictness sweep - {tag} window, {len(labels)} config(s)", flush=True)

    h_spec = build_spec(panel, bench, *SLEEVE_H)
    h_res = run_backtest(panel, h_spec, start=START, slippage_bps=SLIPPAGE)
    print(f"  sleeve H fixed at {h_spec.name}", flush=True)

    out: dict = {"stage": stage, "window": {"start": w_start, "end": w_end},
                 "slippage_bps": SLIPPAGE, "sleeve_h": h_spec.name, "variants": {}}
    params_by_label = dict(VARIANTS)

    for label in labels:
        t0 = time.time()
        params = dict(params_by_label[label])
        params.update({"stretch": 0.75, "trend_sma": 200})
        spec = build_spec(panel, bench, "three_lower_lows", params)
        res = run_backtest(panel, spec, start=START, slippage_bps=SLIPPAGE)

        a_eq = res.equity.loc[w_start:w_end]
        ens_eq = blend(res.equity, h_res.equity).loc[w_start:w_end]
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
        rets = pd.DataFrame({"a": res.equity.pct_change(),
                             "h": h_res.equity.pct_change()}).dropna()
        rets = rets.loc[w_start:w_end]
        wins = rets.clip(lower=rets.quantile(0.01), upper=rets.quantile(0.99), axis=1)

        # Exposure is the cost side of the trade-off: a filter that discards most
        # of the candidate pool can leave a dip-buyer with nothing to buy
        # (PHASE3_CONCLUSION.md - you cannot deploy capital that has no setups).
        entry_days = int(res.trades["entry_date"].nunique()) if len(res.trades) else 0

        out["variants"][label] = {
            "spec": spec.name,
            "sleeve_a": stats(a_eq, trades, spy),
            "ensemble": {
                "cagr": round(cagr(ens_eq), 4),
                "sharpe": round(sharpe(ens_eq), 2),
                "max_dd": round(max_drawdown(ens_eq), 4),
            },
            "diversification": {
                "a_exposure": round(float(res.exposure.loc[w_start:w_end].mean()), 3),
                "corr_a_h_pearson": round(float(rets["a"].corr(rets["h"])), 3),
                "corr_a_h_winsor": round(float(wins["a"].corr(wins["h"])), 3),
                "entry_days_full": entry_days,
            },
        }
        v = out["variants"][label]
        a, e, dv = v["sleeve_a"], v["ensemble"], v["diversification"]
        print(f"  {label:12} A: win {a['win_rate']:.1%} PF {a['profit_factor']} "
              f"CAGR {a['cagr']:.2%} DD {a['max_dd']:.1%} n={a['trades']} "
              f"expo {dv['a_exposure']:.2f} | ens CAGR {e['cagr']:.2%} "
              f"Sharpe {e['sharpe']} DD {e['max_dd']:.1%} | corrW "
              f"{dv['corr_a_h_winsor']} ({time.time() - t0:.0f}s)", flush=True)
    return out


def write_report(out: dict) -> None:
    stage = out["stage"]
    base = out["variants"]["baseline"]
    tag = "IS" if stage == "is" else "OOS"
    w = out["window"]
    lines = [
        f"# Phase 6 strictness sweep - {'in-sample' if stage == 'is' else 'out-of-sample'} results",
        "",
        f"Window {w['start']} -> {w['end'] or 'present'}, {out['slippage_bps']} bps/side.",
        f"Sleeve H fixed at `{out['sleeve_h']}`; deployed 60/40 A/H blend.",
        "",
        "Pre-registration and pass/kill criteria: `STRICTNESS_HYPOTHESIS.md`.",
        "",
        "`baseline` = the deployed A config (no extra confirmation). Every other row adds",
        "entry filters only; no exit, stretch, trend SMA or slot count moves.",
        "",
        "| Config | A win% | A PF | A CAGR | A maxDD | A trades | A expo | Ens CAGR | Ens Sharpe | Ens maxDD | corrW |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for label, v in out["variants"].items():
        a, e, dv = v["sleeve_a"], v["ensemble"], v["diversification"]
        lines.append(
            f"| {'**' + label + '**' if label == 'baseline' else label} "
            f"| {a['win_rate']:.1%} | {a['profit_factor']} | {a['cagr']:.2%} "
            f"| {a['max_dd']:.1%} | {a['trades']} | {dv['a_exposure']:.2f} "
            f"| {e['cagr']:.2%} | {e['sharpe']} | {e['max_dd']:.1%} "
            f"| {dv['corr_a_h_winsor']} |"
        )
    lines += [
        "",
        "## Read this before drawing a conclusion",
        "",
        "**Win rate rising while ensemble CAGR falls is the expected shape, and it is the",
        "whole question - not a win and not a failure.** Calm names win more often and pay",
        "less per win, so a tighter cap should trade return for hit rate. The pre-registration",
        "reports this as two verdicts: whether the win rate rises (Verdict A) and whether the",
        "book is better off (Verdict B). Read the ensemble CAGR column next to the win-rate",
        "column, not on its own.",
        "",
        "**Read the win-rate column NEXT TO the trades and exposure columns.** A filter that",
        "keeps 1% of signals can post a flattering win rate on a handful of trades while the",
        "account sits in cash. Win rate is a percentage; compounding needs occurrences.",
    ]
    if stage == "oos":
        lines += [
            "",
            "## OOS confirmation",
            "",
            f"Baseline OOS: win rate {base['sleeve_a']['win_rate']:.1%}, "
            f"PF {base['sleeve_a']['profit_factor']}, "
            f"ensemble Sharpe {base['ensemble']['sharpe']}, "
            f"ensemble maxDD {base['ensemble']['max_dd']:.1%}.",
            "",
            "OOS is spent. Any further iteration on these numbers invalidates the window.",
        ]
    path = RESULTS_DIR / f"PHASE6_STRICTNESS_{tag}.md"
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
    (RESULTS_DIR / f"phase6_strictness_{tag}.json").write_text(json.dumps(out, indent=2))
    write_report(out)


if __name__ == "__main__":
    main()
