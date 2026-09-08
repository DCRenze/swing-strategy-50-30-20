# Phase 6 conclusion — strictness buys a high win rate in-sample and gives almost all of it back

**Verdict: rejected. In-sample, stacking confirmations raised Sleeve A's win rate 61.3% →
67.2% and profit factor 1.35 → 1.88. Out-of-sample, every configuration with enough trades to
measure landed within 0.3 points of baseline, while ensemble CAGR fell 15.6% → 9.7–11.5%.
Nothing ships; `screener.py` untouched.**

Pre-registration: `STRICTNESS_HYPOTHESIS.md`. Evidence: `PHASE6_STRICTNESS_IS.md`,
`PHASE6_STRICTNESS_OOS.md`, `phase6_strictness_{is,oos}.json`.

## The question

> "What if we took stricter chosen stocks with a high projected win rate through multiple
> indicators / rules, that almost guarantees it will take profit?"

Five entry confirmations, each of which passes the Phase 4/5 test of varying *between names on
the same day*: RSI(2) ≤ 5, IBS ≤ 0.20, close below its own lower Bollinger band, ≥10% above
its own SMA(200), and 4–5 consecutive lower lows instead of 3. Tested alone and stacked.

## In-sample: it works, and it is expensive

| Config | A win% | A PF | A CAGR | A maxDD | A trades | A expo | Ens CAGR | Ens Sharpe |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | 61.3% | 1.35 | **18.34%** | −36.5% | 9607 | **0.58** | **13.37%** | **0.97** |
| rsi5 | 62.6% | 1.47 | 11.56% | −18.3% | 4668 | 0.28 | 9.38% | 0.84 |
| ibs0.2 | 62.2% | 1.40 | 10.76% | −15.5% | 5116 | 0.31 | 8.89% | 0.78 |
| bband | 63.2% | 1.51 | 8.83% | −14.1% | 3265 | 0.19 | 7.75% | 0.73 |
| trend10 | 61.9% | 1.37 | 14.05% | −25.3% | 6747 | 0.41 | 10.84% | 0.86 |
| ll4 | 62.1% | 1.37 | 12.51% | −25.6% | 6512 | 0.39 | 9.95% | 0.82 |
| ll5 | 63.3% | 1.47 | 9.37% | −22.7% | 3826 | 0.23 | 8.07% | 0.77 |
| rsi5+ibs | 62.3% | 1.46 | 7.06% | −12.6% | 2884 | 0.17 | 6.69% | 0.68 |
| rsi5+ibs+bb | 64.3% | 1.73 | 5.49% | −10.2% | 1543 | 0.09 | 5.73% | 0.63 |
| +ll4 | 63.9% | 1.75 | 3.77% | −7.1% | 1059 | 0.06 | 4.68% | 0.55 |
| **everything** | **67.2%** | **1.88** | **1.55%** | −5.2% | 344 | **0.02** | 3.34% | 0.42 |

**Every filter individually improves trade quality.** Profit factor rises monotonically with
strictness, 1.35 → 1.88. This is *not* the Phase 4/5 failure mode — the filters do exactly
what they claim. The pre-registered same-day-variation test worked.

**And return collapses just as monotonically**, 18.34% → 1.55%. Look at the exposure column:
0.58 → 0.02. The strictest config is invested 2% of the time.

## Out-of-sample: the win-rate gain does not survive

| Config | A win% | A PF | A CAGR | A trades | A expo | Ens CAGR | Ens Sharpe | Ens maxDD |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | **60.1%** | 1.16 | **10.67%** | 2303 | 0.69 | **15.58%** | **1.09** | −15.5% |
| rsi5 | 60.2% | 1.12 | 4.19% | 1238 | 0.37 | 11.45% | 0.97 | −11.1% |
| rsi5+ibs+bb | 60.4% | 1.21 | 2.30% | 371 | 0.11 | 10.25% | 1.03 | −8.6% |
| everything | 65.9% | 1.75 | 1.49% | **82** | 0.02 | 9.73% | 1.06 | −7.3% |

**The win-rate improvement is gone.** `rsi5` gained +1.3 points in-sample and **+0.1** out of
sample. `rsi5+ibs+bb` gained +3.0 in-sample and **+0.3** out of sample. Against a 60.1%
baseline, those are nothing.

**`everything` held its win rate — on 82 trades.** The pre-registration set a floor of 100 OOS
trades precisely so this could not be counted, and it is below it. 82 trades over 3.5 years is
about two a month; a 65.9% rate on that sample has a margin of error of roughly ±10 points. It
is not measurable, and "not measurable" is not "proven."

Verdict A fails for everything testable. Verdict B fails outright: ensemble CAGR drops 4–6
points in every configuration.

## Why: quality and quantity trade against each other, and compounding needs both

Phases 4 and 5 failed because the filters didn't work. **Phase 6 failed because they did.**

The confirmations really do isolate better trades — in-sample profit factor 1.88 versus 1.35
is a large, genuine improvement, and it partially persists out-of-sample (1.75 vs 1.16). The
problem is that a better trade you almost never take cannot compound. Exposure falls from 69%
to 2%, so the account spends its life in cash, and a 65.9% win rate on 2% exposure produces
1.49% a year against the baseline's 10.67%.

This is the same wall `PHASE3_CONCLUSION.md` hit from the other direction: **you cannot deploy
capital that has nothing to buy.** Phase 3 tried to raise utilisation by concentrating into
fewer, larger positions and found the exposure gain was small and the drawdown cost large.
Phase 6 tries to raise quality and finds the utilisation cost enormous. The binding constraint
on this book is not the quality of its entry rule. It is **how many good setups the universe
produces per year.**

## The honest nuance — this is a risk dial, and a decent one

Strictness reliably buys one thing out-of-sample: **risk reduction.** Ensemble max drawdown
falls −15.5% → −7.3%, and ensemble Sharpe barely moves (1.09 → 1.06 for `everything`, 1.03 for
`rsi5+ibs+bb`). Risk-adjusted, these configurations are roughly as efficient as the baseline —
they are simply smaller.

That is a legitimate thing to want, and it is the same shape as the Phase 5 finding. Priced
plainly: **roughly 6 points of CAGR to halve the drawdown.** At the book's current −3.9%
drawdown that is far too expensive, but it is now measured and on the shelf.

## The one genuinely open question this raises

Filters find better trades; the universe does not supply enough of them. That points somewhere
specific and **untested**: if the constraint is setup *supply*, then a materially larger
universe (beyond the current ~1,000 names) run with a quality filter could plausibly deliver
`rsi5+ibs+bb`'s trade quality at baseline's exposure. That would be having both.

This is a hypothesis, not a recommendation. It needs its own pre-registration, a universe
build, and a fresh OOS window. Note the obvious risk: a wider universe means smaller, less
liquid names, and Sleeve A's edge is already cost-fragile (zero CAGR at 20 bps/side per
`PHASE3_CONCLUSION.md`). Liquidity screening would have to be part of the hypothesis, not an
afterthought.

## Do not revisit without

- A way to increase the *supply* of qualifying setups, not just the strictness of the screen.
  Adding filters to the current universe is now a closed question.
- A drawdown-framed hypothesis if the motivation is risk — priced at ~6 points of CAGR.

Already tested and rejected, do not revisit without a new pre-registered hypothesis:
upside management (`PHASE2_CONCLUSION.md`), slot concentration (`PHASE3_CONCLUSION.md`),
entry-breadth gating and clustering throttles (`PHASE4_CONCLUSION.md`), Sleeve A volatility
filtering (`PHASE5_CONCLUSION.md`), stacked entry confirmations (this document).
