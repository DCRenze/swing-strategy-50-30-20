# Phase 6 pre-registration — can stacking confirmation filters buy a near-certain win rate?

**Written before any Phase 6 backtest was run.** Criteria fixed at authoring time.

## The question David asked

> "What if we took stricter chosen stocks with a high projected win rate through multiple
> indicators / rules, that almost guarantees it will take profit?"

The intuition is sound and worth testing: if one entry rule gives 61%, do five agreeing rules
give 80%? This phase measures the actual **win-rate / return frontier** — how high a win rate
Sleeve A can be pushed, and exactly what each step costs.

## What "almost guarantees" can and cannot mean

Stated plainly up front, because it shapes how the result should be read:

1. **A high win rate is trivially purchasable and not the same as profit.** Any strategy's win
   rate can be pushed toward 100% by taking profits sooner and holding losers longer. That
   trade is what destroys accounts: 95% wins at +1% against 5% losses at −25% loses money.
   Sleeve A already has this shape mildly — it exits on the *first* up-close, and has **no
   stop-loss** — so its 61% win rate is already partly bought with open-ended downside.
2. **Filters cut sample size fast.** The stacked configs below keep 1–13% of signals. With few
   enough trades, any in-sample win rate can be produced by chance, which is exactly why the
   OOS window exists and is spent once.
3. **A dip-buyer needs dips.** `PHASE3_CONCLUSION.md` established that idle capital cannot be
   redeployed. A filter keeping 1% of signals leaves the account mostly in cash, so a high win
   rate on 90 trades a year can still compound to less than a mediocre one on 900.

So the honest deliverable is not pass/fail. It is a **priced frontier**: here is the win rate
you can buy, and here is the return you give up for it.

## Hypothesis (H3)

Requiring several independent entry confirmations to agree raises Sleeve A's win rate above
its 61.3% baseline. Whether it raises **return** is the open question.

## The filters, and why each one passes the Phase 4/5 test

`PHASE5_CONCLUSION.md` established the rule that killed the last two ideas: **a filter must
vary between names on the same day, not mostly between days.** Same-day breadth and entry ATR
both failed it — they were proxies for free capital and market fear respectively. Each filter
here compares a stock to *itself*:

| Filter | What it demands | Same-day variation? |
|---|---|---|
| `max_rsi2` | RSI(2) ≤ 5 — deeply oversold | Yes; RSI is normalised per name |
| `max_ibs` | close in the bottom 20% of its own daily range | Yes; bounded 0–1 by construction |
| `below_lower_band` | close under its own 20-day lower Bollinger band | Yes; scaled by the name's own σ |
| `min_trend_strength` | ≥10% above its own SMA(200) | Yes; a per-name trend quality measure |
| `n_lower_lows` | 4 or 5 consecutive lower lows, not 3 | Yes; a per-name pattern depth |

## Method

`backtest/phase6_strictness.py`, same two-stage discipline as Phases 2, 4 and 5.

- **Stage 1 (`--stage is`)** — baseline, each filter alone, then progressively stacked
  combinations up to all five at once, **in-sample only** (2005-06 → 2022-12).
- **Stage 2 (`--stage oos --confirm <label>`)** — one OOS confirmation for whatever stage 1
  selects. Spent once.

Sleeve H fixed at its validated config. 5 bps/side. The 60/40 ensemble measured alongside.

## Pass criteria (fixed now)

**Verdict A — does strictness raise the win rate?** Passes if the stacked configs show a
higher IS win rate than baseline, and the selected config's OOS win rate also beats baseline.

**Verdict B — should it be deployed?** Passes only if Verdict A passes **and**:
1. Ensemble OOS Sharpe ≥ baseline ensemble OOS Sharpe.
2. Ensemble OOS CAGR ≥ baseline − 1.0 percentage point.
3. Ensemble OOS max drawdown no worse than baseline by more than 2 points.
4. ≥ 100 OOS trades survive — below that the win rate is not measurable, whatever it reads.

**Verdict A passing while Verdict B fails is the expected outcome** and is a real answer, not
a failure: *yes, you can buy a higher win rate; here is the bill.* That result gets reported
with the price attached and the decision goes to David.

## Kill criteria

- Win rate does not rise with strictness → the confirmation stack does not do what it claims;
  reject, as in Phases 4 and 5.
- Fewer than 100 OOS trades survive → the config is untestable, not good.
- Ensemble OOS Sharpe falls materially → reject for deployment regardless of win rate.

## What ships either way

Nothing in `playbook/screener.py` or `papertrade/run_daily.py`. All new parameters default to
the validated baseline. Deployment is a separate, explicit decision.
