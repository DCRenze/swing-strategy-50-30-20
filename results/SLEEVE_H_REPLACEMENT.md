# Replacing Sleeve H — allocation options

Decision support for retiring the 52-week-high momentum sleeve (David, Aug 2026).
Stated objectives, in David's words: **short turnaround** and **capital utilised all the
time**.

Figures are computed from the saved per-sleeve equity curves and trade ledgers in
`results/`. **Method check:** the same blending code reproduces `REFINEMENT.md`'s
published legacy ensemble exactly (CAGR 0.1232 vs 0.1232, MaxDD −0.1653 vs −0.1653).

> **Revision note.** An earlier version of this file recommended A 60 / TOM 20 / TT 20.
> That was optimised for Sharpe and hold length only. Measured against the utilisation
> objective it is the **worst** option on the board (50% invested) — see below. The
> recommendation is superseded.

## Utilisation is the missing measurement

Trades-per-year says nothing about how much capital is actually deployed. What matters is
**slot occupancy**: the fraction of a sleeve's 10 position slots filled on an average day.
Measured over the OOS window (2023+), from each sleeve's trade ledger:

| Sleeve | slot occupancy | days fully idle | avg hold |
|---|---|---|---|
| **H** `high52_breakout` | **88%** | 4% | 11.8d |
| `double7` | **83%** | 3% | 7.8d |
| `momentum_burst` | 81% | 1% | 4.6d |
| `rsi2_pullback` | 78% | 1% | 4.0d |
| **A** `3ll_refined` | 74% | 6% | 1.7d |
| `range_reversion` | 72% | 2% | 3.1d |
| `band_ibs` | 62% | 1% | 1.9d |
| `turnaround_tuesday` *(base)* | 54% | 27% | 3.1d |
| `turn_of_month` *(base)* | 33% | 67% | 7.0d |
| **TOM** `tom_exit1` | **23%** | **76%** | 5.0d |
| **TT** `tt_bear` | **4%** | **94%** | 3.0d |

Three conclusions fall straight out:

1. **H was the most heavily utilised sleeve in the book — 88%, higher than A's 74%.**
   The idle capital observed in July was the partial-bar bug (H dormant 26 of 28 days),
   not the design. With H working, the A60/H40 book runs **80% invested** — the highest
   of any configuration tested.
2. **TOM and TT are the worst possible replacements for this objective.** `tom_exit1`
   holds capital 23% of the time and `tt_bear` 4%. `refine.py` already says as much in a
   comment: the A/H switch "replaces the rarely-used turn-of-month / turnaround-tuesday
   sleeves."
3. **`tt_bear`'s 4% is the bear-regime filter, not the strategy.** Unfiltered
   `turnaround_tuesday` occupies 54% of its slots. If TT is wanted for utilisation rather
   than crash insurance, the unfiltered version is the one to use.

**The real tension:** occupancy comes either from *long holds* (H: 88% off 11.8-day holds)
or from *very frequent signals* (`rsi2` / `momentum_burst` / `band_ibs`). Wanting both
"turns over fast" and "always deployed" from one sleeve is a genuine constraint, not a
free lunch — it forces high signal frequency, which is where the weaker edges live.

## Candidate books

Sleeve A = the deployed `3ll_refined`; candidates at their baseline gauntlet configs.
`invest%` = Σ(weight × occupancy). `wHold` = occupancy-weighted average hold.

| Book | invest% | wHold | CAGR | Sharpe | MaxDD | OOS Sharpe | OOS MaxDD |
|---|---|---|---|---|---|---|---|
| A 60 / H 40 *(current, H working)* | **80%** | 6.2d | 14.3% | 1.01 | −26.5% | **1.29** | −17.9% |
| A 60 / D7 40 | 78% | 4.3d | 13.1% | 1.01 | −25.2% | 0.93 | −14.5% |
| A 60 / RSI2 40 | 76% | 2.6d | 14.2% | 0.97 | **−38.2%** | 0.82 | −15.1% |
| **A 100%** | 74% | **1.7d** | **16.7%** | **1.10** | −29.3% | 0.93 | −15.1% |
| A 50 / TT 20 / D7 20 / H 10 | 73% | 4.5d | 13.1% | 1.04 | −23.6% | 1.14 | −12.9% |
| **A 60 / TT 20 / D7 20** | **72%** | **3.3d** | 13.7% | 1.05 | −24.2% | 1.01 | −12.1% |
| A 50 / TT 25 / D7 25 | 71% | 3.7d | 12.9% | 1.01 | **−23.5%** | 1.01 | **−11.4%** |
| A 60 / TT 40 | 66% | 2.2d | 14.1% | 1.02 | −25.3% | 1.03 | −9.7% |
| *A 60 / TOM 20 / TT 20 (superseded rec)* | *50%* | *2.0d* | *13.2%* | *1.17* | *−19.0%* | *1.04* | *−13.0%* |

Correlation with A (OOS): H 0.39 · `momentum_burst` 0.43 · `turnaround_tuesday` 0.47 ·
`band_ibs` 0.47 · `double7` 0.57 · `rsi2_pullback` 0.62 · `range_reversion` 0.66.

## Recommendation

**A 60 / TT 20 / D7 20** — 72% invested at a 3.3-day weighted hold. It is the best
balance of the two objectives: near-A utilisation, turnaround roughly half of A/H's, and
it *improves* on the current book's drawdown (−24.2% vs −26.5%) while holding OOS Sharpe
at 1.01. Two decorrelated sleeves rather than one keeps the ensemble argument intact.

**A 50 / TT 25 / D7 25** if drawdown matters more than return — same utilisation band,
best OOS drawdown of the diversified set (−11.4%).

### Honest update on A 100%

Measured against *these* objectives it scores better than the previous version of this
file allowed: **74% invested** (statistically indistinguishable from the 72% recommended
book), the **fastest turnaround in the catalogue at 1.7 days**, and the **highest return
and Sharpe** of any option. The case against it is no longer utilisation — it is a
**−29.3% max drawdown, 5 points worse** than the recommended book for ~3% more CAGR, plus
total dependence on a single signal (PLAYBOOK §1: every strategy fails the gauntlet
individually; the ensemble is what clears the bar). It is a defensible choice if
drawdown tolerance is genuinely high, but it buys nothing on utilisation.

### Rejected

- **`rsi2_pullback`** — 76% invested and fast, but **−38.2% MaxDD** and 0.62-correlated
  with A: it is another oversold dip-buyer that fails in the same conditions, so it adds
  size to A's bad days rather than offsetting them.
- **`range_reversion`** — 0.66 correlation; already rejected once for exactly this reason
  (PLAYBOOK §1).
- **`momentum_burst`** — 81% invested but a −70.6% full-window drawdown.
- **Re-tuning H's hold** — its edge is letting winners run (avg win +9.75% OOS);
  shortening the hold destroys it and needs full re-validation.

## Two operational consequences

1. **A near-close checkpoint is unavoidable.** Every mean-reversion alternative in the
   catalogue — `double7`, `turnaround_tuesday`, `rsi2_pullback` — is
   `entry_mode="close"` / `exit_mode="close"`. Only sleeves A and H execute at the open.
   Whatever replaces H, the "nearclose" runner (~3:45pm ET) has to come back. Alpaca
   fractional orders are DAY-only, so this is a near-close market order rather than a
   true MOC; measure the drift against the backtest's close fills once live.
2. **Sleeve A's own cap is a free utilisation lever.** A occupies 7.4 of 10 slots, and
   live it was oversubscribed constantly — **75 "sleeve full" skips in 28 days**, because
   its limit orders only fill when price trades down to `close − 0.75×ATR`. Raising
   `max_positions` would lift deployment *and* dilute the sector concentration flagged in
   `LIVE_REVIEW_2026-08.md`, at the cost of smaller positions. It is a validated
   parameter, so it needs `gauntlet.py` + `refine.py` before it moves.

## A caveat worth stating

Utilisation is a means, not an end. A fully-deployed book of a weak signal is worse than a
half-deployed book of a strong one — `rsi2_pullback` above is exactly that trap: it wins
on utilisation and loses 38% in a drawdown. The reason to prefer deployment is that idle
cash earns nothing, which is the same reasoning behind the June switch to the aggressive
config. Rank options by risk-adjusted return *within* an acceptable utilisation band
rather than by utilisation itself.

## Work required to deploy

The sleeve components are individually gauntlet-tested, but **no blend below is in the
evidence chain** — `double7_lb10` is a refined config, plain `turnaround_tuesday` has
never been refined, and the weights are new.

1. Rebuild the data panel (`python -m backtest.data`) — needs open outbound network.
2. Add the chosen configs to `refine.py::CONFIGS`, re-run `gauntlet.py` + `refine.py`,
   update `REFINEMENT.md` and `refine_results.json`.
3. Restore the near-close runner and its workflow.
4. Update `playbook/screener.py` (`SLEEVES`), `PLAYBOOK.md`, `run_daily.py`, `CLAUDE.md`.
5. Wind down the 10 open H positions on their existing exit rules rather than
   liquidating, so the ledger stays clean.
