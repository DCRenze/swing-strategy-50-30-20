# Phase 5 pre-registration — can Sleeve A buy a higher win rate by avoiding jumpy stocks?

**Written before any Phase 5 backtest was run.** Criteria fixed at authoring time.

## The question David actually asked

> "If the win rate is higher on calmer stocks, why take the risk on jumpy ones?"

Fair question, and the honest answer is that win rate is only half of a bet. A calm stock
and a jumpy stock are different *sizes* of bet, so a lower win rate on bigger moves can
still make more money. This phase measures which effect wins.

## The observation this comes from

Bucketing recorded backtest trades by the stock's ATR(10) as a percentage of its price on
the entry day:

**Sleeve A (11,790 trades, 2005–2026)**

| Volatility at entry | n | Win rate | Avg return | Profit factor |
|---|--:|--:|--:|--:|
| <2% (calm) | 4240 | **62.7%** | +0.24% | **1.44** |
| 2–3% | 4285 | 61.1% | +0.29% | 1.32 |
| 3–4% | 1828 | 58.6% | +0.32% | 1.26 |
| >4% (jumpy) | 1437 | **57.0%** | **+0.40%** | 1.20 |

Sleeve H shows the same shape, more steeply (55.0% → 39.8%).

Unlike the Phase 4 breadth table, this gradient is **monotone in both win rate and profit
factor, in both sleeves, across ~15,000 trades**. That is a much stronger prior than the
sawtooth that killed Phase 4.

**But note the column that runs the other way.** Average return per trade *rises* with
volatility: +0.24% → +0.40%. Calm names win more often and pay less. So a calmness filter
is a bet that the higher hit rate outweighs the smaller winners — it is emphatically not a
free lunch, and the whole point of the test is to price that trade-off.

There is also an exposure cost: capping at 2% ATR discards 62% of Sleeve A's signals. With
10 slots and a dip-buyer that needs dips, throwing away most of the candidate pool may leave
capital idle — and `PHASE3_CONCLUSION.md` already established you cannot deploy capital that
has nothing to buy.

## Hypothesis (H2)

Restricting Sleeve A entries to names whose ATR(10) is at or below a fixed fraction of price
raises the sleeve's win rate. **Whether it raises the sleeve's and the book's return is the
open question.**

Entry filter only. Stretch (0.75), trend SMA (200), the limit offset, the exit rule, the
15-day time stop and the 10-slot cap are untouched; `max_atr_pct=None` reproduces the
deployed config exactly.

### Why this is not a re-litigation

- **Phase 2** was Sleeve H exits. **Phase 3** was Sleeve A *sizing* (slot count).
- **Phase 4** was Sleeve H *entry timing* (which sessions to trade).
- H2 is Sleeve A *entry selection* (which names to trade within a session) — which is
  precisely the direction `PHASE4_CONCLUSION.md` named as the one worth pursuing.

## Method

`backtest/phase5_volatility.py`, same two-stage discipline as Phase 2 and Phase 4:

- **Stage 1 (`--stage is`)** — caps at 2.0%, 2.5%, 3.0%, 3.5%, 4.0%, 5.0% plus the uncapped
  baseline, **in-sample only** (2005-06 → 2022-12). Grid spans the signal distribution
  (median 2.24%, p75 2.98%, p90 3.99%), chosen from signal density before any result.
- **Stage 2 (`--stage oos --confirm <label>`)** — one OOS confirmation. Spent once.

Sleeve H held at its validated config, 5 bps/side, 60/40 blend measured alongside the sleeve.

## Pass criteria (fixed now)

Because the stated goal is win rate, this phase reports **two verdicts, not one.**

**Verdict A — "does it raise the win rate?"** Passes if:
1. Win rate rises monotonically with tightening caps in-sample (expected; the filter is
   mechanical, so a *non*-monotone result would mean something is wrong with the test).
2. The selected cap's OOS win rate beats baseline's OOS win rate.

**Verdict B — "should we deploy it?"** Passes only if Verdict A passes **and**:
3. Sleeve A OOS profit factor ≥ baseline OOS profit factor.
4. Ensemble OOS Sharpe ≥ baseline ensemble OOS Sharpe.
5. Ensemble OOS CAGR ≥ baseline − 1.0 percentage point. A filter that buys comfort by
   giving up a point of return a year is a decision for David, not a default.
6. Ensemble OOS max drawdown no worse than baseline by more than 2 points.
7. ≥ 100 OOS trades survive the filter.

**Verdict A passing while Verdict B fails is a real and expected outcome**, and it is the
answer to the question as asked: *yes you can buy a higher win rate, here is exactly what it
costs.* That result gets reported with the price tag attached, and the decision goes to
David rather than being made by the pass/fail table.

## Kill criteria

- Win rate does not rise at all → the volatility gradient does not survive being turned into
  a rule, exactly as the Phase 4 breadth gradient did not. Reject and stop.
- The filter starves the sleeve (OOS trades < 100, or exposure collapses) → reject.
- OOS win rate flips below baseline → reject, and treat the bucket table as another artifact.

## What ships either way

Nothing in `playbook/screener.py` or `papertrade/run_daily.py` changes in this phase.
`max_atr_pct` defaults to `None`. Deployment is a separate, explicit decision made on these
numbers.
