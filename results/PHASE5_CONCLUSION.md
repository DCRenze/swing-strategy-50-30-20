# Phase 5 conclusion — the calmness filter is rejected, and the win rate never even moved

**Verdict: H2 fails its first kill criterion in-sample. The win rate does not rise, and
returns collapse. Nothing ships; `screener.py` untouched. OOS was NOT spent — the
pre-registration says a kill criterion ends it in-sample, and it did.**

Pre-registration: `VOLATILITY_HYPOTHESIS.md`. Evidence: `PHASE5_VOLATILITY_IS.md`,
`phase5_volatility_is.json`.

## The question

David asked the obvious and correct question: if calm stocks win 62.7% of the time and jumpy
ones only 57.0%, why take the jumpy ones at all? This phase capped Sleeve A entries at a
maximum ATR(10) as a fraction of price and measured what happened.

## In-sample result

| Config | A win% | A PF | A CAGR | A maxDD | A trades | A expo | Ens CAGR | Ens Sharpe |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | **61.3%** | **1.35** | **18.34%** | −36.5% | 9607 | 0.58 | **13.37%** | **0.97** |
| maxatr2.0 | 60.6% | 1.20 | 4.53% | −22.5% | 6089 | 0.37 | 5.11% | 0.52 |
| maxatr2.5 | 61.2% | 1.29 | 9.33% | −20.8% | 7709 | 0.47 | 7.98% | 0.73 |
| maxatr3.0 | 61.4% | 1.28 | 10.69% | −21.6% | 8469 | 0.52 | 8.79% | 0.77 |
| maxatr3.5 | 61.8% | 1.32 | 13.71% | −23.2% | 8971 | 0.54 | 10.59% | 0.88 |
| maxatr4.0 | 61.0% | 1.29 | 12.93% | −23.4% | 9155 | 0.56 | 10.14% | 0.81 |
| maxatr5.0 | 61.1% | 1.28 | 13.35% | −32.6% | 9336 | 0.57 | 10.41% | 0.81 |

**The win rate does not move.** Baseline 61.3%; every cap lands between 60.6% and 61.8%. The
*tightest* filter — keeping only the calmest 38% of signals — produces a **lower** win rate
than taking everything (60.6% vs 61.3%). The bucket table predicted 62.7%. It did not
happen.

**Returns collapse.** Sleeve A CAGR falls 18.34% → 4.53% at the tightest cap; the ensemble
falls 13.37% → 5.11% and Sharpe 0.97 → 0.52. Every single cap is worse than baseline on both
sleeve CAGR and ensemble Sharpe, with no exception and no plateau.

Kill criterion 1 ("win rate does not rise at all → reject and stop") is met, so **the OOS
window was not spent.** It remains available for a hypothesis that earns it.

## Why the bucket table lied — ATR is a fear gauge, not a stock trait

The pre-registration flagged the return trade-off but missed the deeper problem, which the
data makes obvious:

- **Correlation between the typical stock's ATR% and the VIX: 0.914.**
- Typical stock ATR is **1.95%** on the calmest quarter of days and **3.94%** on the most
  stressed quarter.
- Under a 3% cap, **12% of stocks are excluded in calm markets and 52% in stressed markets.**

So ATR barely distinguishes one stock from another — it mostly says *what kind of market day
it is*. "Low ATR trades" are overwhelmingly trades taken in quiet bull markets, and "high ATR
trades" are trades taken in panics. The 62.7% vs 57.0% gradient was never a fact about calm
*stocks*; it was a fact about calm *markets*.

That is why the filter behaves the way it does. It does not hand you the same trades in
quieter names — it switches the strategy off exactly when the market is frightened. Exposure
drops from 0.58 to 0.37. And for a dip-buyer, frightened markets are where the setups and
the outsized snap-backs live. You remove the losses *and* the payoffs, and since the win rate
inside each regime was never the thing driving returns, you are left with a worse strategy
that wins just as often.

Note the one thing the filter genuinely does buy: **drawdown.** Max DD improves from −36.5%
to −22.5%, and the ensemble's from −20.0% to −18.7%. That is real, and it is the same open
thread Phase 2 left behind (hold-extension halving H's drawdown). If Sleeve A's drawdown ever
becomes the binding constraint, this is a *risk* dial worth revisiting — priced honestly at
roughly 14 points of CAGR, which is far too expensive at current drawdown levels.

## The general lesson, now twice confirmed

Phase 4 and Phase 5 failed the same way. Both started from a compelling table that sorted
*already-taken trades* by some attribute and found a clean gradient. Both gradients vanished
when turned into a rule, because in each case the attribute was a proxy for something the
strategy was already exploiting:

- **Phase 4:** same-day signal count was a proxy for *free capital and selection depth*.
- **Phase 5:** entry-day ATR is a proxy for *the market regime*.

Sorting historical trades by a feature tells you where returns *landed*. It does not tell you
that filtering on that feature would have *produced* them. Before the next such hypothesis,
check first whether the feature is mostly measuring the calendar rather than the choice.

## For the record: why Sleeve A takes jumpy stocks

Because that is where its edge is. Volatile conditions are dip-buying conditions. Avoiding
them costs about 14 points of annual return and does not improve the hit rate at all.

## Do not revisit without

- A feature that varies *between names on the same day*, not one that mostly varies between
  days. That is the test Phase 4 and Phase 5 both failed.
- A drawdown-framed hypothesis if the motivation is risk rather than edge — and an
  acknowledgement that the price is roughly 14 points of CAGR at the tight end.

Already tested and rejected, do not revisit without a new pre-registered hypothesis:
upside management (`PHASE2_CONCLUSION.md`), slot concentration (`PHASE3_CONCLUSION.md`),
entry-breadth gating and clustering throttles (`PHASE4_CONCLUSION.md`), Sleeve A volatility
filtering (this document).
