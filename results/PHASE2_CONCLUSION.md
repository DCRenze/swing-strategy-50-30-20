# Phase 2 conclusion — Sleeve H keeps its exits

**Verdict: no change. Both IS-selected upside rules failed out-of-sample and neither
clears the gauntlet bar the deployed config already clears. `screener.py` is untouched.**

## The question

Sleeve H truncates its left tail with a 5% stop and its right tail with a 15-day clock,
and does nothing in between for a trade that has already worked. Live, all ten closed H
trades were green at some point, eight closed red, and the mean giveback from peak close
to exit was 5.95 points — ACHC peaked at +20.67% and exited at +17.11%. Phase 2 asked
whether any upside rule fixes that over 2005–2026.

## What was tested

Five families, 20 configs, on the full panel (5,434 sessions × 1,010 tickers), 5 bps/side.
Selection in-sample only (2005-06→2022-12); one OOS confirmation (2023-01→present) for the
two finalists, then the full gauntlet for both.

Baseline reconciliation: the harness reproduces `refine_results.json`'s `h52_fast_regime`
in-sample to PF 1.16 / Sharpe 0.33 / maxDD −44.03% / 2,524 trades vs 2,522. The deltas
below are measured against the real validated config.

## In-sample selected two finalists

| Family | IS verdict |
|---|---|
| `hold_sma20` (trend-conditional hold extension) | plateau: +0.11/+0.13/**+0.15**/+0.15/+0.15 ens Sharpe for caps 25/40/60/80/none — converges, because the SMA20 condition ends trades on its own |
| `trail_atr` | interior maximum at k=1.5 (**+0.12**), falling off both sides |
| `profit_target` | non-monotone across 10/15/20/25 (+0.13/+0.07/+0.08/+0.13) — noise, not a plateau |
| `giveback` | +0.05..+0.06 but at 2–2.3× turnover on 4–6 day holds |
| `breakeven` | +0.00 / +0.02; the 5% variant makes drawdown worse |

## Out-of-sample killed both

Ensemble Sharpe, 60/40 A/H:

| Config | IS | OOS | |
|---|--:|--:|---|
| baseline (deployed) | 0.97 | **1.20** | |
| `trail_atr1.5` | 1.09 (+0.12) | 0.88 (**−0.32**) | sign flip |
| `hold_sma20_max60` | 1.12 (+0.15) | 0.85 (**−0.35**) | sign flip |

Both reversed sign, and by more out-of-sample than they gained in-sample. On the sleeve
itself, OOS H profit factor went 1.39 (baseline) → 1.15 (`trail_atr1.5`) → 1.20
(`hold_sma20_max60`).

**This is not a regime artifact.** The obvious objection is that 2023–2026 was a strong
momentum tape, so anything cutting winners early would underperform. That explanation
fails: the two finalists move holding period in *opposite* directions — `trail_atr1.5`
shortens the average hold to 8.8 days, `hold_sma20_max60` lengthens it to 15.7 — and both
underperformed. The flat 15-day clock beat a tighter exit and a looser one in the same
window, which is what a well-calibrated parameter looks like.

## Gauntlet confirms it

Full treatment on both finalists plus a like-for-like deployed baseline
(`gauntlet_high52_*.json`). Every individual strategy fails the gauntlet — that is
expected and is why the ensemble exists — so what matters is *which bars* each clears:

| Config | OOS PF >1.3 | OOS maxDD <25% | ≥100 trades | OOS Sharpe ≥ SPY |
|---|:--:|:--:|:--:|:--:|
| `high52_deployed` | **✓ 1.39** | ✓ −20.1% | ✓ 3,147 | ✗ 0.98 vs 1.47 |
| `high52_trail_atr` | ✗ 1.17 | ✓ −22.1% | ✓ 3,789 | ✗ 0.51 |
| `high52_hold_sma20` | ✗ 1.20 | ✓ −19.7% | ✓ 2,167 | ✗ 0.43 |

Both finalists **lose a bar the incumbent currently clears**. That settles it.

## The one result worth remembering

`hold_sma20_max60` is dramatically better on drawdown and in bad regimes, even though it
loses on OOS profit factor:

| | deployed | hold_sma20_max60 |
|---|--:|--:|
| Full-window maxDD | −44.6% | **−24.1%** |
| Monte-Carlo p95 DD | −29.4% | **−25.7%** |
| 2022 bear return | −14.1% | **+0.7%** |
| 2020 crash/recovery | +3.3% | **+22.6%** |

That is a real property, not noise — halving the sleeve's worst drawdown and turning the
2022 bear from −14% to flat. It did not earn a ship under the rule agreed in advance, and
it is not being shipped. But "extend the hold while the trend holds" looks less like an
edge rule and more like a *drawdown* rule, and it should be re-tested that way — against a
drawdown objective, pre-registered, with its own fresh OOS window. Re-running it against
the same OOS data under a new objective would be exactly the p-hacking the stage split
exists to prevent.

## Notes

- The two tables differ by ~5 trades on the same config because the gauntlet restarts the
  backtest at the OOS boundary while the sweep runs continuously from 2005 and slices.
  Both are legitimate; neither difference is material.
- The A/H correlation figure quoted in `CLAUDE.md` (~0.26) is a raw Pearson on daily
  returns and is fragile: the baseline H curve contains a +34% and a −24% session, and
  whether one such day falls inside the window swings it between 0.26 and 0.41. Winsorized
  and rank estimates put it at ~0.45 across every variant tested, baseline included. This
  does not invalidate the ensemble — Pearson is the right input to portfolio variance — but
  the diversification claim is less comfortable than 0.26 suggests, and it is worth
  re-deriving on its own terms.
- Panel coverage runs 643 tickers in 2005 to 1,010 in 2026 because `universe.csv` is
  today's index membership. That survivorship bias inflates absolute returns for the
  baseline and every variant equally, so the comparisons hold; it is inherited from the
  existing validation, not introduced here.

## Reproduce

```
python -m backtest.phase2_upside --stage is
python -m backtest.phase2_upside --stage oos --confirm trail_atr1.5 hold_sma20_max60
python -m backtest.gauntlet high52_deployed high52_trail_atr high52_hold_sma20
```
