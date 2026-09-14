# Crypto backtest result — the deployed config makes 1% a year on 2% of the account

**Verdict: fails 4 of 6 pre-registered criteria, including two of the three that
define "does this work at all". Over three years of crypto bull market, the deployed
Sleeve A config returned 1.0% a year with the account 2% invested, against 43.1% for
simply holding bitcoin. Nothing ships; `screener.py` and `run_daily.py` untouched.**

Pre-registration: `CRYPTO_BACKTEST_HYPOTHESIS.md` (criteria fixed before any run).
Evidence: `crypto_backtest.json`. Reproduce: `python -m backtest.crypto_backtest`.

## What was run

The deployed configuration, unmodified — `three_lower_lows.build` at
`stretch=0.75, trend_sma=200, $10M ADV, 15-day stop, 10 slots`, and
`high52_breakout.build` at module defaults with a 100-day regime gate. These are
`refine.py`'s `3ll_refined` and `h52_fast_regime`, which is what `screener.py` runs.
No filters were added and nothing was tuned.

Window **2023-09-14 → 2026-09-14**, the three years David asked for. Universe: the 19
non-stablecoin USD-quoted Alpaca spot pairs.

## The result

Headline row is `slip15` — Alpaca's base-tier maker fee, the floor for Sleeve A's
resting limit orders.

| | CAGR | Sharpe | MaxDD | Exposure | Trades | Win% | PF |
|---|--:|--:|--:|--:|--:|--:|--:|
| **BTC buy-and-hold** | **43.1%** | **1.00** | −53.1% | 100% | — | — | — |
| Equal-weight 19 pairs | 19.6% | 0.60 | −74.2% | 100% | — | — | — |
| | | | | | | | |
| Crypto Sleeve A, 5 bps | 1.7% | 0.21 | −14.4% | 2% | 91 | 57.1% | 1.26 |
| **Crypto Sleeve A, 15 bps** | **1.0%** | **0.15** | −14.8% | **2%** | **91** | 53.8% | **1.17** |
| Crypto Sleeve A, 25 bps | 0.4% | 0.09 | −15.2% | 2% | 91 | 53.8% | 1.09 |
| Crypto Sleeve H, 15 bps | 3.2% | 0.33 | −12.4% | 5% | 62 | 27.4% | 1.31 |
| Crypto ensemble 60/40, 15 bps | 2.2% | 0.30 | −9.4% | 3% | 153 | 43.1% | 1.25 |
| | | | | | | | |
| Equity Sleeve A, 5 bps | 6.5% | 0.70 | −9.7% | 25% | 681 | 58.3% | 1.25 |
| Equity Sleeve A, 25 bps | −2.8% | −0.24 | −20.5% | 25% | 681 | 51.7% | 0.93 |

The equity rows use the same 120-name sample as `crypto_feasibility.py`, not the live
1,000-name universe, so their exposure (25%) and CAGR are below the deployed book's.
They are here as a like-for-like control, not as a restatement of the playbook's
numbers.

## Against the pre-registered criteria

| | Criterion | Actual | |
|---|---|--:|---|
| A1 | profit factor > 1.30 | 1.17 | **FAIL** |
| A2 | at least 100 trades | 91 | **FAIL** |
| A3 | max drawdown better than −25% | −14.8% | PASS |
| B4 | Sharpe ≥ BTC buy-and-hold (1.00) | 0.15 | **FAIL** |
| B5 | CAGR positive at 25 bps/side | 0.4% | PASS |
| B6 | Sharpe ≥ equity Sleeve A OOS 0.98 | 0.15 | **FAIL** |

**Verdict A (does the rule work on crypto?): FAIL.**
**Verdict B (worth building?): FAIL.**

A2 is worth pausing on. 91 trades in three years is **below the README's own
minimum** for a testable result — and that is in the most favourable three-year
window crypto has ever had, on a universe that excludes every coin that died. The
sample is not merely disappointing; it is too small to support a conclusion in
either direction, which was blocker 5 in `CRYPTO_FEASIBILITY.md` and is now
demonstrated rather than argued.

## The number that matters most

**2% exposure.** The account sits in cash 98% of the time.

That is not a near-miss on a good idea. It is, to the decimal place, the Phase 6
`everything` configuration — the one that stacked five confirmation filters, achieved
a genuinely better trade quality, ran **2% exposure**, returned **1.55% a year**, and
was rejected because *a better trade you almost never take cannot compound*.

Crypto reproduces that outcome exactly, with **no filters added at all**. Phase 6 had
to work hard to get to 2% exposure. Crypto starts there.

## The obvious objection, tested and closed

The natural response is that `stretch=0.75` was tuned for equity volatility, so in an
asset three times more volatile the limit sits too far below the close and never
fills — meaning the low exposure is a parameter problem, not a supply problem.

Measured:

| | Signals | Limit fills | Fill rate | Limit depth below close | ATR(10) as % of price |
|---|--:|--:|--:|--:|--:|
| Crypto | 404 | 84 | **20.8%** | 5.47% | 7.30% |
| Equity | 2,964 | 668 | **22.5%** | 1.99% | 2.66% |

**The fill rates match.** The limit is ATR-scaled, so it self-adjusts to the asset's
volatility — that is what `stretch` in ATR units is *for*, and it transfers correctly.
The limit sits 5.47% below the close in crypto against 1.99% in equities, and catches
essentially the same share of signals.

So retuning `stretch` would not rescue this, and the 2% exposure is not an artefact of
a mispriced limit. **404 signals versus 2,964 is the whole story**, and 404 across 17
crypto names over three years is the 127-a-year supply figure from
`CRYPTO_FEASIBILITY.md`, confirmed independently by a different code path.

## Two results that look better than they are

**The $1 min-price sensitivity.** Keeping the equity penny-stock filter — which
excludes DOGE, SHIB and XRP on a price level that means nothing in crypto — gives
Sleeve A a profit factor of **1.61** and Sharpe 0.37, materially better than dropping
it. That is the best-looking number in this document and it should not be believed:
it rests on **69 trades**, further below the 100-trade bar, and the pre-registration
fixed that bar precisely so a small-sample result could not be counted. It is also
still 2% exposure and 2.8% CAGR against bitcoin's 43.1%. Filed as an observation, not
a finding.

**Sleeve H's profit factor of 1.31.** It clears 1.30 — the only cell in the table
that does — on 62 trades and a 27.4% win rate, with the account 5% invested. Note also
that H's `$5` price floor is hardcoded inside `high52_breakout.build` and was left
alone rather than edit validated code; in crypto that floor cuts the universe to a
median of **8 of 19 names** (AAVE, AVAX, BCH, BTC, DOT, ETH, LINK, LTC, MKR, YFI). So
this is a 62-trade result on eight large-cap coins in a bull market. It is not
evidence of anything, and it is well below the 48.5% win rate H shows in equities.

## What this run cannot tell you, restated

Fixed in the pre-registration before the numbers existed, and unchanged by them:

1. **Survivorship.** The universe is today's Alpaca list projected backwards. Every
   dead coin is absent. This biases the result **upward** — and it still failed.
2. **One regime.** Three years of crypto bull market. 2022, the last crypto bear,
   produced 40 qualifying setups in the entire year. Nothing here tests a downturn.
3. **No held-out data.** One window, no split. This is a measurement, not a validation.

The direction of every one of these is favourable to crypto, which makes the failure
more informative than a pass would have been.

## What changed, and what did not

Nothing in `CRYPTO_FEASIBILITY.md`'s recommendation changes. Its central claim was
that setup supply, not entry quality, is what crypto fails on, and that a backtest
could not settle the question because the window is one bull regime on a survivor-only
universe. Both held: the backtest produced 91 trades at 2% exposure, and the criteria
that failed are the supply-driven ones.

One thing did change, in crypto's favour and worth recording: the feasibility document
estimated a **10–21% exposure ceiling**. The realised figure is **2%**, because roughly
four in five signals never fill. The ceiling estimate was too generous by a factor of
five to ten.

## Recommendation

Unchanged: **do not build a crypto sleeve.** The backtest David asked for was run
under the most favourable conditions available and failed 4 of 6 pre-registered
criteria, including the trade-count minimum that makes a result interpretable at all.

The open thread from `PHASE6_CONCLUSION.md` remains where it was — a materially larger
**equity** universe with a liquidity screen built into the hypothesis. That direction
has ~10,000 setups a year, three cycles of history, a working execution path, and
10 bps costs.

## Do not revisit without

- A point-in-time crypto universe including delisted assets, which does not currently
  exist in any free source.
- A crypto bear market in the test window.
- A supply mechanism, not a parameter change. The fill-rate diagnostic closes the
  `stretch` objection; any new proposal has to explain where more than 404 signals in
  three years would come from.

Already tested and rejected, do not revisit without a new pre-registered hypothesis:
upside management (`PHASE2_CONCLUSION.md`), slot concentration (`PHASE3_CONCLUSION.md`),
entry-breadth gating and clustering throttles (`PHASE4_CONCLUSION.md`), Sleeve A
volatility filtering (`PHASE5_CONCLUSION.md`), stacked entry confirmations
(`PHASE6_CONCLUSION.md`), a spot crypto sleeve (`CRYPTO_FEASIBILITY.md` and this
document).
