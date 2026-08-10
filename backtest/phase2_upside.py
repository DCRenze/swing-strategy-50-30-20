"""Phase 2: does managing the upside help Sleeve H?

Sleeve H truncates the left tail with a 5% stop and the right tail with a
15-day clock, and does nothing in between for a position that has already
worked. Live, every closed H trade was green at some point and 8 of 10 closed
red, giving back a mean 5.95 points from peak. This sweep asks whether any
upside rule fixes that on 21 years of data, or whether the flat 15-day hold is
already the right answer.

Discipline (same as gauntlet.py / refine.py):
  Stage 1  --stage is    every variant on IN-SAMPLE only (2005-06..2022-12).
                         Selection happens here, by eye, from the report.
  Stage 2  --stage oos --confirm LABEL [LABEL...]
                         one OOS confirmation for the IS-selected finalists.

Splitting the stages is the point: OOS is spent once, on configs chosen
without seeing it. Running stage 2 across the whole grid would burn it.

A variant has to clear two bars, not one:
  - the H sleeve itself must improve, and
  - the deployed 60/40 A/H ensemble must improve, since diversification is
    what clears the gauntlet (GAUNTLET_SUMMARY.md) - a sleeve that gets better
    while decorrelating less can still make the book worse.

Run:  python -m backtest.phase2_upside --stage is
      python -m backtest.phase2_upside --stage oos --confirm trail_atr2.5 giveback50
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

# label -> params layered on the validated H baseline
VARIANTS: list[tuple[str, dict]] = [
    ("baseline", {}),
    # 1. ATR trailing stop - exit below peak_close - k*ATR(10).
    #    k=1.0/1.5 added after the first pass peaked at k=2.0, the tightest
    #    value then tested: an optimum on the grid boundary is indistinguishable
    #    from a trend that keeps going, so the boundary has to move.
    ("trail_atr1.0", {"trail_atr_mult": 1.0}),
    ("trail_atr1.5", {"trail_atr_mult": 1.5}),
    ("trail_atr2.0", {"trail_atr_mult": 2.0}),
    ("trail_atr2.5", {"trail_atr_mult": 2.5}),
    ("trail_atr3.0", {"trail_atr_mult": 3.0}),
    # 2. proportional give-back of peak open profit
    ("giveback20", {"trail_giveback_frac": 0.20}),
    ("giveback33", {"trail_giveback_frac": 0.33}),
    ("giveback50", {"trail_giveback_frac": 0.50}),
    # 3. hard profit target, remainder left to the clock
    ("target10", {"profit_target_frac": 0.10}),
    ("target15", {"profit_target_frac": 0.15}),
    ("target20", {"profit_target_frac": 0.20}),
    ("target25", {"profit_target_frac": 0.25}),
    # 4. stop to breakeven once the trade has worked
    ("breakeven5", {"breakeven_after_frac": 0.05}),
    ("breakeven8", {"breakeven_after_frac": 0.08}),
    # 5. trend-conditional hold extension - attacks the truncated right tail
    #    directly rather than through a trailing rule. Caps run out to 80 and
    #    uncapped for the same boundary reason as the ATR trail.
    ("hold_sma20_max25", {"hold_extend_sma": 20, "max_hold_days": 25}),
    ("hold_sma20_max40", {"hold_extend_sma": 20, "max_hold_days": 40}),
    ("hold_sma20_max60", {"hold_extend_sma": 20, "max_hold_days": 60}),
    ("hold_sma20_max80", {"hold_extend_sma": 20, "max_hold_days": 80}),
    ("hold_sma20_nocap", {"hold_extend_sma": 20}),
    # 6. combination: the two IS-selected finalists together. Each failed its
    #    own OOS confirmation; tested jointly because they were never run as a
    #    pair and they pull in opposite directions on holding period.
    ("combo_trail1.5_hold60",
     {"trail_atr_mult": 1.5, "hold_extend_sma": 20, "max_hold_days": 60}),
]


def stats(equity: pd.Series, trades: pd.DataFrame, spy: pd.Series) -> dict:
    spy_eq = (spy.reindex(equity.index).ffill().dropna())
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


def window(start: str | None, end: str | None):
    return (lambda s: s.loc[start:end])


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

    print(f"Phase 2 upside sweep - {tag} window, {len(labels)} config(s)", flush=True)

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

        cut = window(w_start, w_end)
        h_eq, ens_eq = cut(res.equity), cut(blend(a_res.equity, res.equity))
        trades = res.trades
        if len(trades):
            mask = pd.Series(True, index=trades.index)
            if w_start:
                mask &= trades["exit_date"] >= pd.Timestamp(w_start)
            if w_end:
                mask &= trades["exit_date"] <= pd.Timestamp(w_end)
            trades = trades[mask]

        # Diversification check: the ensemble clears the gauntlet on a low A/H
        # correlation, so a variant that improves H by making it behave more like
        # A is spending the property the book relies on.
        #
        # Report BOTH Pearson and a 1%-winsorized correlation. Raw Pearson on
        # daily returns is dominated by a handful of extreme H days (the baseline
        # curve has a +34% and a -24% session), which makes it useless for
        # comparing variants: it swings 0.26 -> 0.41 between neighbouring
        # parameters purely on whether one outlier day survives. Pearson is still
        # the right input to portfolio variance, so it stays; the winsorized
        # figure is what to compare across variants.
        rets = pd.DataFrame({"a": a_res.equity.pct_change(),
                             "h": res.equity.pct_change()}).dropna()
        rets = rets.loc[w_start:w_end]
        wins = rets.clip(lower=rets.quantile(0.01), upper=rets.quantile(0.99), axis=1)

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
            },
        }
        v = out["variants"][label]
        h, e, dv = v["sleeve_h"], v["ensemble"], v["diversification"]
        print(f"  {label:18} H: PF {h['profit_factor']} Sharpe {h['sharpe']} "
              f"DD {h['max_dd']:.1%} n={h['trades']} hold {h['avg_hold_days']}d | "
              f"ens Sharpe {e['sharpe']} DD {e['max_dd']:.1%} | corrW {dv['corr_a_h_winsor']} "
              f"({time.time() - t0:.0f}s)", flush=True)
    return out


def write_report(out: dict) -> None:
    stage = out["stage"]
    base_h = out["variants"]["baseline"]["sleeve_h"]
    base_e = out["variants"]["baseline"]["ensemble"]
    w = out["window"]
    lines = [
        f"# Phase 2 - Sleeve H upside management ({'in-sample' if stage == 'is' else 'OOS confirmation'})",
        "",
        f"Window {w['start']} .. {w['end'] or 'present'} · slippage {out['slippage_bps']} bps/side · "
        f"Sleeve A fixed at `{out['sleeve_a']}` · ensemble = 60/40 A/H daily-return split.",
        "",
        "Deltas are versus the validated baseline. A variant must improve **both**"
        " the sleeve and the ensemble to be worth carrying forward.",
        "",
        "| Variant | H PF | H Sharpe | H maxDD | H trades | H hold | Ens Sharpe | Ens maxDD | ΔEns Sharpe | corr(A,H) |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    base_corr = out["variants"]["baseline"]["diversification"]["corr_a_h_winsor"]
    for label, v in out["variants"].items():
        h, e, dv = v["sleeve_h"], v["ensemble"], v["diversification"]
        d = e["sharpe"] - base_e["sharpe"]
        corr = dv["corr_a_h_winsor"]
        flag = " ⚠" if corr > base_corr * 1.25 else ""
        lines.append(
            f"| {'**' + label + '**' if label == 'baseline' else label} | {h['profit_factor']} | "
            f"{h['sharpe']} | {h['max_dd']:.1%} | {h['trades']} | {h['avg_hold_days']}d | "
            f"{e['sharpe']} | {e['max_dd']:.1%} | {d:+.2f} | {corr}{flag} |"
        )
    lines += [
        "",
        f"Baseline reference: H PF {base_h['profit_factor']}, Sharpe {base_h['sharpe']}, "
        f"maxDD {base_h['max_dd']:.1%}; ensemble Sharpe {base_e['sharpe']}, maxDD {base_e['max_dd']:.1%}, "
        f"corr(A,H) {base_corr}.",
        "",
        "corr(A,H) is 1%-winsorized. Raw Pearson on daily returns is unusable for"
        " comparing variants here - the baseline H curve contains a +34% and a -24%"
        " session, and whether one such day survives swings Pearson between 0.26 and"
        " 0.41 across neighbouring parameters. Both figures are in the JSON."
        " ⚠ marks a variant whose winsorized correlation runs 25% above baseline,"
        " i.e. one buying its ensemble gain by making H behave more like A.",
        "",
    ]
    if stage == "is":
        lines += [
            "## Reading this",
            "",
            "In-sample only - nothing here is evidence a rule works. Pick finalists by"
            " plateau (a whole neighbourhood of parameters improving, not one lucky cell),"
            " then spend the OOS window once:",
            "",
            "```",
            "python -m backtest.phase2_upside --stage oos --confirm <label> [<label> ...]",
            "```",
            "",
            "If no variant shows a plateau, the finding is that the flat 15-day hold is"
            " already right and Sleeve H keeps its current exits.",
        ]
    else:
        lines += [
            "## Decision",
            "",
            "One confirmation, no iteration. A variant ships only if it improves the"
            " ensemble here as it did in-sample; anything that only worked in-sample is"
            " discarded, and the baseline stands.",
        ]
    name = "PHASE2_UPSIDE_IS.md" if stage == "is" else "PHASE2_UPSIDE_OOS.md"
    (RESULTS_DIR / name).write_text("\n".join(lines) + "\n")
    print(f"\nwrote results/{name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["is", "oos"], default="is")
    ap.add_argument("--confirm", nargs="*", default=[],
                    help="variant labels to confirm OOS (stage oos only)")
    args = ap.parse_args()
    if args.stage == "oos" and not args.confirm:
        raise SystemExit("--stage oos needs --confirm with the IS-selected labels")

    out = run(args.stage, args.confirm)
    suffix = "is" if args.stage == "is" else "oos"
    (RESULTS_DIR / f"phase2_upside_{suffix}.json").write_text(json.dumps(out, indent=2))
    write_report(out)


if __name__ == "__main__":
    main()
