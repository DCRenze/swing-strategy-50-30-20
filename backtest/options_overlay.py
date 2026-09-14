"""Synthetic long-call overlay on the deployed sleeves' realized trade ledgers.

RESEARCH ONLY. Imports nothing from playbook/ or papertrade/ and writes nothing
outside results/. Pre-registration: results/OPTIONS_COST_HYPOTHESIS.md.

The question this answers is NOT "what would an options version have earned" —
that needs historical option chains this project does not have. It is the
inverse: **how much round-trip transaction cost could an options version absorb
before its edge is gone?** That threshold is computable from the underlying path
endpoints already in results/gauntlet_*_trades.csv, because a European call's
value at entry and exit is a deterministic function of (S, K, T, r, sigma).

Every modelling choice here is deliberately generous to the options case:
  * implied vol is set to the sleeve's own realized dispersion, i.e. zero
    variance risk premium (the trader buys vol at fair value);
  * no skew, no term structure, no IV path, no dividends, no early assignment;
  * entry and exit both fill at the option's mid, with the spread applied
    afterwards as an explicit, separately-reported cost.
If the answer is negative under assumptions this friendly, it is negative.

Usage:  python3 -m backtest.options_overlay            # writes results/OPTIONS_OVERLAY.md
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

TRADING_DAYS = 252.0
RISK_FREE = 0.04

# Pre-registered grid (OPTIONS_COST_HYPOTHESIS.md) - fixed before any number was computed.
DELTAS = [0.25, 0.40, 0.55, 0.70, 0.85]
DTES = [14, 30, 45, 60, 90]

# Implied-vol grid. See the "Estimator correction" note in OPTIONS_COST_HYPOTHESIS.md:
# the first draft estimated sigma from the ledger as stdev(ret / sqrt(hold)), which is
# badly biased when exits are endogenous - Sleeve H's short holds are stop-outs, a set
# defined by having hit -5%, so their dispersion is artificially tiny and their implied
# daily vol artificially huge. Per-hold-bucket estimates on the unconditional buckets
# (A hold=1, n=8773 -> 35.4%; H hold=15, n=2054 -> 31.6%) both land near 30-35%, so
# sigma is now an explicit stated parameter rather than a derived one.
SIGMAS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
BASE_SIGMA = 0.35

LEDGERS = {
    "A": ("Sleeve A - three lower lows", RESULTS / "gauntlet_three_lower_lows_trades.csv"),
    "H": ("Sleeve H - 52w high breakout", RESULTS / "gauntlet_high52_deployed_trades.csv"),
}


# ---------------------------------------------------------------- Black-Scholes
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(S: float, K: float, T: float, sigma: float, r: float = RISK_FREE) -> float:
    """Black-Scholes call value. T in years. Intrinsic at/after expiry."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    srt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / srt
    d2 = d1 - srt
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def bs_delta(S: float, K: float, T: float, sigma: float, r: float = RISK_FREE) -> float:
    if T <= 0 or sigma <= 0:
        return 1.0 if S > K else 0.0
    srt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / srt
    return _norm_cdf(d1)


def bs_vega(S: float, K: float, T: float, sigma: float, r: float = RISK_FREE) -> float:
    """dP/dsigma per 1.00 of vol (so divide by 100 for one vol point)."""
    if T <= 0 or sigma <= 0:
        return 0.0
    srt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / srt
    phi = math.exp(-0.5 * d1 * d1) / math.sqrt(2.0 * math.pi)
    return S * phi * math.sqrt(T)


def strike_for_delta(S: float, T: float, sigma: float, target_delta: float,
                     r: float = RISK_FREE) -> float:
    """Bisect on strike so that the call's entry delta equals the target.

    Delta falls monotonically in K, so a plain bisection is exact enough.
    """
    lo, hi = S * 0.20, S * 5.00
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if bs_delta(S, mid, T, sigma, r) > target_delta:
            lo = mid          # delta too high -> strike must rise
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ------------------------------------------------------------------- the ledger
def load_ledger(path: Path) -> list[dict]:
    out = []
    with path.open() as f:
        for row in csv.DictReader(f):
            out.append({
                "ret": float(row["ret"]),
                "hold": max(int(float(row["hold_days"])), 0),
                "entry_date": row["entry_date"],
            })
    return out


def bucket_vols(trades: list[dict]) -> list[tuple[int, int, float, float]]:
    """Annualised vol implied separately by each hold-length bucket.

    Reported as diagnostics, NOT used to set sigma. Buckets whose membership is
    defined by the exit rule (Sleeve H's stop-outs; Sleeve A's up-close exits)
    are conditioned on the return itself and their dispersion is meaningless as
    a vol estimate. Only the buckets that are NOT selected on outcome - A's
    one-day exits and H's 15-day time stops - carry information.
    """
    by: dict[int, list[float]] = {}
    for t in trades:
        by.setdefault(max(t["hold"], 1), []).append(t["ret"])
    out = []
    for h in sorted(by):
        v = by[h]
        if len(v) < 50:
            continue
        mean = sum(v) / len(v)
        sd = math.sqrt(sum((x - mean) ** 2 for x in v) / len(v))
        out.append((h, len(v), mean, sd / math.sqrt(h) * math.sqrt(TRADING_DAYS)))
    return out


# ------------------------------------------------------------------ the overlay
def overlay(trades: list[dict], target_delta: float, dte: int, sigma: float) -> dict:
    """Price each trade as a long call bought at entry and sold at exit.

    Underlying is normalised to S0 = 100; only the trade's realized return and
    hold length matter, because Black-Scholes is scale-invariant in (S, K).
    Returns the distribution of option returns BEFORE any spread cost.
    """
    S0 = 100.0
    T0 = dte / 365.0
    K = strike_for_delta(S0, T0, sigma, target_delta)
    P0 = bs_call(S0, K, T0, sigma)
    if P0 <= 1e-9:
        return {}

    delta0 = bs_delta(S0, K, T0, sigma)
    rets = []
    expired = 0
    for t in trades:
        held_years = t["hold"] / TRADING_DAYS
        T1 = T0 - held_years
        if T1 <= 0:
            expired += 1
        S1 = S0 * (1.0 + t["ret"])
        P1 = bs_call(S1, K, max(T1, 0.0), sigma)
        rets.append(P1 / P0 - 1.0)

    n = len(rets)
    mean = sum(rets) / n
    wins = sum(1 for r in rets if r > 0)
    gross_win = sum(r for r in rets if r > 0)
    gross_loss = -sum(r for r in rets if r <= 0)
    return {
        "strike_pct_of_spot": K / S0,
        "premium_pct_of_spot": P0 / S0,
        # Delta-equivalent leverage: $1 of premium controls this much stock exposure.
        "leverage": delta0 * S0 / P0,
        "mean_option_ret": mean,
        "win_rate": wins / n,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        # Breakeven round-trip spread, as a fraction of premium.
        # Buying at mid*(1+c/2) and selling at mid*(1-c/2), the gross gross
        # multiple (1+mean) is scaled by (1-c/2)/(1+c/2); setting that to 1 and
        # solving gives c = 2*mean/(2+mean) for mean > 0.
        "breakeven_rt_spread": (2.0 * mean / (2.0 + mean)) if mean > 0 else 0.0,
        # PHASE3_CONCLUSION.md measured Sleeve A at zero CAGR by 20 bps/side on the
        # STOCK, i.e. 40 bps round trip. An option spread of c% of premium costs
        # c/leverage in underlying-equivalent terms, so the option spread that
        # matches that already-fatal stock cost is 0.0040 * leverage.
        "spread_matching_phase3_cliff": 0.0040 * delta0 * S0 / P0,
        # Underlying-equivalent cost tolerance: the breakeven option spread
        # re-expressed in the bps/side units PHASE3_CONCLUSION.md measured the
        # stock sleeve in. Leverage scales edge and cost equally, so this is the
        # apples-to-apples number.
        "breakeven_bps_per_side": (2.0 * mean / (2.0 + mean)) / (delta0 * S0 / P0) / 2.0 * 10000.0
                                  if mean > 0 else 0.0,
        # Vega, as a fraction of premium, per ONE vol point of implied-vol move.
        # Sleeve A buys into falling tape (PHASE5: stock ATR vs VIX corr 0.914) and
        # sells on the first up-close, so the IV path is structurally adverse: this
        # is how many vol points of IV crush erase the whole breakeven.
        "vega_pct_of_premium_per_vol_pt": bs_vega(S0, K, T0, sigma) / 100.0 / P0,
        "vol_pts_of_crush_to_erase_edge": (mean / (bs_vega(S0, K, T0, sigma) / 100.0 / P0))
                                          if mean > 0 and bs_vega(S0, K, T0, sigma) > 0 else 0.0,
        # Fraction of trades whose exit falls at or after the option's expiry. A
        # material number here means the cell is a model artifact, not a strategy:
        # the overlay is pricing an expiry payoff, not the exit the sleeve took.
        "frac_expired_before_exit": expired / n,
        "n": n,
    }


def main() -> None:
    report: dict = {"risk_free": RISK_FREE, "sleeves": {}}
    lines: list[str] = []

    for key, (label, path) in LEDGERS.items():
        trades = load_ledger(path)
        stock_mean = sum(t["ret"] for t in trades) / len(trades)
        mean_hold = sum(t["hold"] for t in trades) / len(trades)
        buckets = bucket_vols(trades)

        sleeve = {
            "label": label, "n": len(trades),
            "stock_mean_ret": stock_mean, "mean_hold_days": mean_hold,
            "hold_bucket_vols": [
                {"hold": h, "n": n_, "mean_ret": m, "ann_vol": v} for h, n_, m, v in buckets],
            "cells": [],
        }
        lines.append(f"\n## {label}  (n={len(trades)})\n")
        lines.append(f"Stock mean return per trade: **{stock_mean * 100:.3f}%** · "
                     f"mean hold {mean_hold:.2f} trading days\n")
        lines.append("Hold-bucket diagnostics (vol estimates from outcome-selected buckets "
                     "are not meaningful — see the module docstring):\n")
        lines.append("| hold (days) | n | mean return | implied ann. vol |")
        lines.append("|---|--:|--:|--:|")
        for h, n_, m, v in buckets:
            lines.append(f"| {h} | {n_} | {m * 100:+.2f}% | {v * 100:.1f}% |")

        for sigma in SIGMAS:
            lines.append(f"\n### implied vol = {sigma * 100:.0f}%\n")
            lines.append("| DTE | delta | premium (% of spot) | leverage | mean option ret | "
                         "win% | PF | breakeven round-trip spread | = bps/side on underlying | "
                         "vol pts of IV crush to erase edge | % trades expiring before exit |")
            lines.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
            for dte in DTES:
                for d in DELTAS:
                    c = overlay(trades, d, dte, sigma)
                    if not c:
                        continue
                    c.update(dte=dte, delta=d, sigma=sigma)
                    sleeve["cells"].append(c)
                    be = c["breakeven_rt_spread"]
                    be_s = f"**{be * 100:.2f}%**" if be > 0 else "— (negative before costs)"
                    exp_s = (f"**{c['frac_expired_before_exit'] * 100:.1f}%**"
                             if c['frac_expired_before_exit'] > 0.02
                             else f"{c['frac_expired_before_exit'] * 100:.1f}%")
                    lines.append(
                        f"| {dte} | {d:.2f} | {c['premium_pct_of_spot'] * 100:.2f}% | "
                        f"{c['leverage']:.1f}x | {c['mean_option_ret'] * 100:+.2f}% | "
                        f"{c['win_rate'] * 100:.1f}% | {c['profit_factor']:.2f} | {be_s} | "
                        f"{c['breakeven_bps_per_side']:.1f} | "
                        f"{c['vol_pts_of_crush_to_erase_edge']:.2f} | {exp_s} |")
        report["sleeves"][key] = sleeve

    (RESULTS / "options_overlay.json").write_text(json.dumps(report, indent=2))
    (RESULTS / "OPTIONS_OVERLAY.md").write_text(
        "# Options overlay — raw output\n\n"
        "Generated by `backtest/options_overlay.py`. Pre-registration:\n"
        "`OPTIONS_COST_HYPOTHESIS.md`. Read the interpretation in\n"
        "`OPTIONS_FEASIBILITY.md` — this file is the evidence, not the argument.\n"
        + "\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
