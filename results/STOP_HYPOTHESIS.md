# Phase 7 pre-registration — adding a disaster stop to Sleeve A

**Written before the in-sample/out-of-sample split was run.** Selection rule fixed here.

## The decision being made

David has decided Sleeve A should carry a stop-loss, accepting a small return cost for bounded
downside. That is his call to make and this phase implements it properly rather than relitigating
it. The open question is **which level**, and whether the validated evidence chain supports it.

## What is already established

`SLEEVE_A_CRITIQUE_2026-09.md` measured the stop curve full-window on the current
(survivorship-biased) universe:

| Stop | CAGR | maxDD | Worst trade |
|---|--:|--:|--:|
| none | 16.93% | −36.5% | −43.5% |
| 25% | 16.81% | −35.7% | −35.6% |
| 20% | 16.88% | −35.7% | −35.6% |
| 15% | 17.03% | −33.2% | −35.6% |
| 10% | 15.81% | −30.4% | −52.8% |
| 7% | 15.06% | −26.9% | −35.6% |

**Disclosure:** that run was full-window and therefore touched the OOS period in aggregate. It
selected nothing. This phase does the IS/OOS split properly, but the OOS window is no longer
pristine for this question and the confirmation below should be read as *weaker* than a first
look would be. Recorded rather than hidden.

## Why a wide stop is defensible now, despite the biased universe

The critique correctly says a stop level chosen on a survivorship-biased sample is chosen on the
wrong loss distribution. That argument bites hardest on *tight, optimised* levels. It bites least
on a **wide disaster stop**, because of an asymmetry:

- **The cost is measured accurately.** Cost comes from stopping out of dips that later recovered
  — and the biased universe is *full* of names that recovered. So the measured cost is an upper
  bound on the true cost.
- **The benefit is understated.** Benefit comes from names that never recover. Those are exactly
  the names the universe omits. The true benefit can only be larger than measured.

So for a wide level, the biased data says "costs about nothing" and the bias direction says "and
protects more than shown." That is a decision that survives the data problem. A tight level
optimised on the same data would not, and is out of scope here.

## Selection rule (fixed now, before looking)

**Choose the WIDEST stop level whose in-sample CAGR cost is ≤ 0.50 percentage points versus no
stop, and whose in-sample ensemble Sharpe is within 0.05 of no stop.**

Widest, not best. This is deliberate:

- The purpose is disaster protection, not return enhancement. A level that improves returns is a
  bonus, never the objective.
- Picking the in-sample *peak* (15% in the table above) is exactly the overfitting trap that
  killed Phases 4, 5 and 6. The full-window curve is non-monotone at the tight end (5% beat 7%),
  which is the signature of noise.
- A wider stop sits further from the noisy region and is less sensitive to the universe bias.

Candidate grid: 30%, 25%, 20%, 15%, 12%, 10%. Tighter than 10% is not considered — the measured
cost there exceeds what a disaster stop should ever pay.

## Confirmation criteria

The selected level must, out-of-sample:

1. Cost ≤ 1.0 CAGR point versus no stop on the **ensemble** (the book, not the sleeve).
2. Not worsen ensemble max drawdown.
3. Reduce the worst single-trade loss versus no stop.
4. Keep ≥ 95% of the no-stop trade count — a stop that changes the strategy's character rather
   than truncating its tail is not a disaster stop.

If the selected level fails these, report the failure and the next-widest candidate rather than
searching the grid for something that passes.

## Execution-model caveat that must be carried into implementation

A close-based stop that sells at the next open **does not bound loss**. The full-window run showed
worst-trade getting *worse* at 10% and 5% (−52.8% vs −43.5% with no stop), because the stop forced
a sale into a gap-down that the no-stop version rode to a better up-close. This is the same
mechanic that produced YETI −13.9% in Sleeve H against a nominal 5% stop.

The stop must therefore be described honestly in the PLAYBOOK as a **disaster brake, not a
guaranteed maximum loss**, and criterion 3 above exists to catch a level that makes the tail worse.

## What ships

If the criteria pass: `max_stop_frac` wired into `playbook/screener.py` and
`papertrade/run_daily.py` with tests, plus the full gauntlet + refine re-run required by the
Golden Rule, plus updated evidence in `results/`. If they fail: nothing ships and the failure is
written up.
