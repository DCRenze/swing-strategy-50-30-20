"""Phase 3: can a Sleeve-A-only book put more of the account to work?

Sleeve A run at 100% of capital with its validated 10 slots averages ~60%
invested: the engine sizes every position at equity/max_positions, so on days
when fewer than ten setups fire the rest sits in cash. In the live 60/40 book
that compounds - A holds 60% of the account, so ~36% of total equity is working
on an average day and much less on a quiet one.

The account cannot be leveraged (PLAYBOOK: never margin), so the only honest
lever is concentration: fewer slots means each position is a bigger share of
equity, and the same signals deploy more capital. That is a genuine trade -
more of the account working, fewer names to spread the risk across, and the
liquidity ranking has to throw away real signals on busy days.

This sweep measures both sides of it. Selection in-sample; --stage oos confirms.

Run:  python -m backtest.phase3_sleeve_a --stage is
      python -m backtest.phase3_sleeve_a --stage oos --confirm slots5
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd

from backtest.data import load_benchmarks, load_panel
from backtest.engine import RESULTS_DIR, run_backtest
from backtest.gauntlet import IS_END, OOS_START, START, build_spec
from backtest.indicators import monte_carlo_drawdown
from backtest.metrics import cagr, max_drawdown, profit_factor, sharpe

SLIPPAGE = 5.0
SLEEVE_A = {"stretch": 0.75, "trend_sma": 200}

# label -> slots. 10 is the validated baseline.
VARIANTS: list[tuple[str, int]] = [
    ("slots10_baseline", 10),
    ("slots8", 8),
    ("slots6", 6),
    ("slots5", 5),
    ("slots4", 4),
    ("slots3", 3),
    ("slots2", 2),
]


def block(res, start, end, spy) -> dict:
    eq = res.equity.loc[start:end]
    exp = res.exposure.loc[start:end]
    tr = res.trades
    if len(tr):
        m = pd.Series(True, index=tr.index)
        if start:
            m &= tr["exit_date"] >= pd.Timestamp(start)
        if end:
            m &= tr["exit_date"] <= pd.Timestamp(end)
        tr = tr[m]
    spy_eq = spy.reindex(eq.index).ffill().dropna()
    spy_eq = spy_eq / spy_eq.iloc[0]
    dds = monte_carlo_drawdown(eq.pct_change().dropna().to_numpy())
    return {
        "cagr": round(cagr(eq), 4),
        "sharpe": round(sharpe(eq), 2),
        "max_dd": round(max_drawdown(eq), 4),
        "mc_dd_p95": round(float(np.percentile(dds, 95)), 4),
        "avg_exposure": round(float(exp.mean()), 3),
        "pct_days_over_90": round(float((exp > 0.90).mean()), 3),
        "pct_days_under_10": round(float((exp < 0.10).mean()), 3),
        "trades": int(len(tr)),
        "profit_factor": round(profit_factor(tr), 2) if len(tr) else None,
        "spy_sharpe": round(sharpe(spy_eq), 2),
    }


def run(stage: str, confirm: list[str]) -> dict:
    panel, bench = load_panel(), load_benchmarks()
    spy = bench["spy"]
    known = dict(VARIANTS)

    if stage == "is":
        labels, w_start, w_end = [lb for lb, _ in VARIANTS], START, IS_END
    else:
        labels = ["slots10_baseline"] + [c for c in confirm if c != "slots10_baseline"]
        unknown = set(labels) - set(known)
        if unknown:
            raise SystemExit(f"unknown variant(s): {sorted(unknown)}")
        w_start, w_end = OOS_START, None

    print(f"Sleeve-A-only sizing sweep - {'in-sample' if stage == 'is' else 'OOS'} "
          f"window, {len(labels)} config(s)", flush=True)
    out: dict = {"stage": stage, "window": {"start": w_start, "end": w_end},
                 "slippage_bps": SLIPPAGE, "variants": {}}

    for label in labels:
        t0 = time.time()
        slots = known[label]
        spec = build_spec(panel, bench, "three_lower_lows",
                          {**SLEEVE_A, "max_positions": slots})
        res = run_backtest(panel, spec, start=START, slippage_bps=SLIPPAGE)
        s = block(res, w_start, w_end, spy)
        s["slots"] = slots
        s["position_size_pct"] = round(1.0 / slots, 3)
        out["variants"][label] = s
        print(f"  {label:18} exposure {s['avg_exposure']:>5.1%}  CAGR {s['cagr']:>7.2%}  "
              f"maxDD {s['max_dd']:>7.1%}  MCp95 {s['mc_dd_p95']:>7.1%}  "
              f"Sharpe {s['sharpe']:<5} PF {s['profit_factor']:<5} n={s['trades']:<6} "
              f"({time.time() - t0:.0f}s)", flush=True)
    return out


def write_report(out: dict) -> None:
    stage = out["stage"]
    b = out["variants"]["slots10_baseline"]
    w = out["window"]
    lines = [
        f"# Phase 3 - Sleeve-A-only capital utilisation "
        f"({'in-sample' if stage == 'is' else 'OOS confirmation'})",
        "",
        f"Window {w['start']} .. {w['end'] or 'present'} · slippage {out['slippage_bps']} bps/side · "
        "Sleeve A at 100% of capital, no Sleeve H, no leverage.",
        "",
        "Fewer slots = a bigger share of equity per position, so the same signals put more"
        " of the account to work. The cost is concentration and, on busy days, discarding"
        " real signals the liquidity ranking cannot fit.",
        "",
        "| Config | Size each | Avg exposure | Days >90% | Days <10% | CAGR | maxDD | MC p95 DD | Sharpe | PF | Trades |",
        "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for label, s in out["variants"].items():
        name = f"**{label}**" if label == "slots10_baseline" else label
        lines.append(
            f"| {name} | {s['position_size_pct']:.0%} | {s['avg_exposure']:.1%} | "
            f"{s['pct_days_over_90']:.0%} | {s['pct_days_under_10']:.0%} | {s['cagr']:.2%} | "
            f"{s['max_dd']:.1%} | {s['mc_dd_p95']:.1%} | {s['sharpe']} | {s['profit_factor']} | "
            f"{s['trades']} |"
        )
    lines += [
        "",
        f"Baseline (10 slots): exposure {b['avg_exposure']:.1%}, CAGR {b['cagr']:.2%}, "
        f"maxDD {b['max_dd']:.1%}, Sharpe {b['sharpe']}.",
        "",
        "**Read maxDD and MC p95 before CAGR.** Concentration raises return and drawdown"
        " together; a config is only better if return rises faster than the drawdown it"
        " buys. MC p95 is the more honest risk figure - maxDD is the single worst path that"
        " happened to occur, while MC p95 estimates what bad luck could plausibly deliver.",
    ]
    if stage == "is":
        lines += [
            "",
            "In-sample only. Pick by plateau, then confirm once:",
            "",
            "```",
            "python -m backtest.phase3_sleeve_a --stage oos --confirm <label>",
            "```",
        ]
    name = "PHASE3_SLEEVE_A_IS.md" if stage == "is" else "PHASE3_SLEEVE_A_OOS.md"
    (RESULTS_DIR / name).write_text("\n".join(lines) + "\n")
    print(f"\nwrote results/{name}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["is", "oos"], default="is")
    ap.add_argument("--confirm", nargs="*", default=[])
    args = ap.parse_args()
    if args.stage == "oos" and not args.confirm:
        raise SystemExit("--stage oos needs --confirm with the IS-selected labels")
    out = run(args.stage, args.confirm)
    suffix = "is" if args.stage == "is" else "oos"
    (RESULTS_DIR / f"phase3_sleeve_a_{suffix}.json").write_text(json.dumps(out, indent=2))
    write_report(out)


if __name__ == "__main__":
    main()
