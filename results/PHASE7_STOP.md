# Phase 7 conclusion — Sleeve A gets a 15% disaster stop

**Verdict: shipped.** `A_STOP_FRAC = 0.15` in `playbook/screener.py`, wired into
`papertrade/run_daily.py` ahead of the up-close exit. The validation chain
(`backtest/refine.py`) has been re-run and `REFINEMENT.md` regenerated, per the Golden Rule.

Pre-registration and selection rule: `STOP_HYPOTHESIS.md`. Prior measurement:
`SLEEVE_A_CRITIQUE_2026-09.md`.

## Decision

David decided Sleeve A should carry a stop, explicitly accepting a small return cost for
bounded downside. This phase implemented that decision and chose the level by a rule fixed
before the split was run. It did not relitigate the decision.

## Effect on the validated book

| | No stop (previous) | 15% stop (deployed) |
|---|--:|--:|
| Full-window CAGR | 13.64% | **13.77%** |
| Full-window max drawdown | −24.87% | **−20.70%** |
| IS Sharpe | 0.95 | 0.96 |
| OOS Sharpe | 1.16 | **1.21** |
| Monte Carlo p95 drawdown | −16.83% | −16.89% |

**The accepted cost was not charged.** Max drawdown improved 4.2 points with no return
given up. That is a better outcome than the decision required, and it should be read as
"the stop is free at this level", not as "the stop earns 0.13 points" — see the caveats.

## How 15% was selected

The pre-registered rule was: *the widest level whose in-sample CAGR cost is ≤ 0.50 points
and whose in-sample ensemble Sharpe is within 0.05 of no-stop*, then four out-of-sample
confirmation criteria. Grid: 30 / 25 / 20 / 15 / 12 / 10%.

In-sample, **every** level from 30% down to 12% cost essentially nothing (−0.00 to −0.01
CAGR points, ensemble Sharpe unchanged at 0.96–0.97). So the in-sample stage did not
discriminate, and the rule's "widest" tiebreak initially selected 30%.

**30%, 25% and 20% then failed OOS confirmation criterion 3** (must reduce the worst single
trade). Inspection showed why, and it is the whole story of this phase:

| OOS | Worst trade | Trades worse than −20% | Sum of those losses |
|---|--:|--:|--:|
| no stop | −31.6% | 3 | −0.82 |
| 30% stop | **−35.2%** | 3 | −0.86 |
| **15% stop** | **−24.8%** | **2** | **−0.48** |

At 30%, the *only* out-of-sample trade the stop touched was ELF (2025-11-04). Without the
stop it exited at −31.6% after 4 days; with it, the stop fired and sold into a gap-down at
−35.2% after 2 days. Every other trade was byte-identical. **A 30% stop on this book is
theatre: it binds once and makes that one case worse.**

15% is the widest level that actually truncates the tail, and it passed all four criteria:
ensemble cost ≤ 1.0 point (it gained), drawdown not worsened (improved), worst trade reduced
(−31.6% → −24.8%), trade count preserved (99.8%).

Note that 15% was also the in-sample peak in the earlier full-window run, which is normally
a warning sign. Here it was selected by the *tail* criterion, not the return criterion, and
by a rule written before the split — but the coincidence is recorded rather than hidden.

## Why not 5%, like Sleeve H?

Asked directly, and worth recording because it will be asked again.

| Stop | IS CAGR | OOS CAGR | Ensemble CAGR | Worst trade | Trades hitting it |
|---|--:|--:|--:|--:|--:|
| none | 18.34% | 10.67% | 13.72% | −43.5% | — |
| **15%** | 17.71% | **14.08%** | **13.77%** | **−35.6%** | **0.5%** |
| 10% | 16.05% | 14.89% | 13.04% | **−52.8%** | 1.6% |
| 7% | 16.40% | 9.05% | 12.60% | −35.6% | 3.8% |
| 5% | 17.27% | 10.63% | 13.16% | **−52.8%** | 6.8% |

Three reasons, in order of importance:

**1. The two sleeves buy opposite things, so the same stop means opposite things.** Sleeve H
buys *strength* — a new 252-day high. A 5% fall from that entry is evidence the breakout
failed, so cutting is correct. Sleeve A buys *weakness* — three consecutive lower lows, then
a limit order still further below the close. It is entering a falling stock on purpose. A 5%
move against it is not evidence of anything; it is the thesis in progress.

**2. 5% is inside the noise on the holding period.** Median Sleeve A entry has an ATR(10) of
**2.24% of price**, and the average hold is **1.7 days**. A 5% stop is therefore about two
ordinary days of range — it fires on normal movement, on 6.8% of trades versus 0.5% at 15%,
roughly a 14× higher firing rate.

**3. Tight stops make the tail WORSE here, not better.** Both 5% and 10% produce a −52.8%
worst trade against −43.5% with no stop at all. The mechanic is the one documented above: a
close-based stop sells at the next open, so every firing is exposed to a gap. Firing 14× more
often means catching 14× more gaps. A stop that fires often under this execution model is not
a smaller loss, it is more chances to be gapped through.

The ensemble figures close the argument: 15% delivers 13.77% against 13.16% at 5% and 12.60%
at 7%. Tighter is worse on return *and* worse on the tail.

**It is not a guaranteed maximum loss.** The rule reads a completed close and sells at the
next open. A gap-down fills below the level. That is exactly what happened to ELF at wider
settings, and it is the same mechanic that produced YETI −13.9% against Sleeve H's nominal
5% stop. The PLAYBOOK and CLAUDE.md describe it as a **disaster brake**; keep that wording.

**It does not resolve the survivorship problem.** `SLEEVE_A_CRITIQUE_2026-09.md` stands in
full: `data/universe.csv` is today's index membership, so the loss distribution this level
was chosen against excludes every company that fell and never came back. The direction of
the bias is favourable — the biased sample is the one most hostile to stops, so the measured
cost is an upper bound and the measured benefit a lower bound — which is why shipping a
*wide* stop is defensible on this data where an optimised tight one would not be. But the
level itself should be revisited once a point-in-time universe exists.

**The OOS window is no longer pristine for this question.** The earlier full-window stop
curve touched it in aggregate before this split was run. Disclosed in `STOP_HYPOTHESIS.md`;
treat the OOS confirmation as weaker than a first look.

**The OOS return improvement is probably noise.** Sleeve A OOS CAGR 10.67% → 14.08% on 2,300
trades over 3.5 years is a large move to attribute to a brake that fires rarely. The
drawdown and tail improvements are the results to believe; the return gain is a bonus that
may not repeat.

## Implementation notes

- Evaluated **before** the up-close exit, so a position that has already broken the level
  exits even if an up-close has since appeared. `test_run_daily.py` pins that ordering.
- Measured on `raw_close` against the real fill price, never the dividend-adjusted series —
  the same trap the H stop documents.
- Five new tests, including one that pins `A_STOP_FRAC == 0.15` and `H` at 0.05, so a silent
  drift breaks the build rather than the evidence chain.
- `3ll_nostop` retained in `refine.py` as a standing comparison, so the counterfactual stays
  measurable rather than becoming folklore.

## Follow-ups

1. The point-in-time universe (Test 1 in the critique) remains the blocking item. Re-run
   this grid on it when available; the correct level may be tighter once real delistings are
   in the sample.
2. A resting broker-side stop would additionally close the "nothing protects the book if the
   morning script fails" gap. This change does **not** do that — the stop is still evaluated
   once a day by the script.
3. The fill-rate measurement (Test 3) is still unrun and still the cheapest high-value item.
