# Replacing Sleeve H — allocation options

Decision support for retiring the 52-week-high momentum sleeve (David, Aug 2026).
All figures below are computed from the saved per-sleeve equity curves in
`results/ensemble_equity.csv`. **Method check:** the same code reproduces
`REFINEMENT.md`'s published legacy ensemble exactly (CAGR 0.1232 vs 0.1232,
MaxDD −0.1653 vs −0.1653), so the blends below are trustworthy.

## Why H felt slow — and what was actually the bug

Two separate things got tangled:

| Observation | Cause |
|---|---|
| H dormant for weeks, then 10 entries in one day | **Bug** (partial-bar volume filter) — fixed |
| Positions riding 15 sessions to a time stop | **By design** — H's real hold is 11.8d avg, **15d median** |

The dormancy was the defect. The *hold length* is genuine: H is the slowest thing in the
book by a factor of seven, and its edge comes precisely from letting winners run
(avg win +9.75% OOS). Shortening its hold would not make it a faster H — it would
destroy the edge and require full re-validation. If a 15-day median hold is unacceptable,
replacing the sleeve is the right call, not re-tuning it.

## Turnaround times — the thing you're optimising for

| Sleeve | avg hold | median | max | trades/yr | corr. with A (OOS) |
|---|---|---|---|---|---|
| **A** `3ll_refined` | 1.7d | 1d | 15d | 578 | — |
| `tt_bear` | 3.0d | 3d | **4d** | 99 | 0.25 |
| `tom_exit1` | 5.0d | 5d | **5d** | 120 | 0.16 |
| `double7_lb10` | 7.8d | 7d | 15d | 241 | 0.57 |
| **H** `h52_fast_regime` | **11.8d** | **15d** | 15d | 159 | 0.39 |

`tom_exit1` and `tt_bear` have **hard-bounded** holds (5 and 4 days) — a position can
never sit longer. Both are also less correlated with A than H is (0.16 / 0.25 vs 0.39),
so diversification improves rather than degrades.

## Allocation options

Full window 2005–2026; OOS = 2023+.

| Allocation | CAGR | Sharpe | MaxDD | OOS CAGR | OOS Sharpe | OOS MaxDD |
|---|---|---|---|---|---|---|
| **A 100%** (drop H, no replacement) | 16.7% | 1.10 | **−29.3%** | 13.2% | 0.93 | −15.1% |
| A 60 / TOM 40 | 13.2% | 1.14 | −17.8% | 10.7% | 1.00 | −15.9% |
| A 60 / TT 40 | 13.1% | 1.10 | −20.7% | 9.6% | 1.02 | **−9.9%** |
| **A 60 / TOM 20 / TT 20** | 13.2% | **1.17** | −19.0% | 10.2% | 1.04 | −13.0% |
| A 50 / TOM 30 / TT 20 *(legacy)* | 12.3% | 1.16 | **−16.5%** | 9.5% | 1.06 | −13.2% |
| A 70 / TOM 15 / TT 15 | **14.1%** | 1.17 | −21.1% | 11.0% | 1.01 | −13.5% |
| *A 60 / H 40 (current, published)* | *13.6%* | *0.99* | *−24.9%* | — | *1.16* | — |

### Answering the direct question: no, do not go to A 100%

It is the **worst** risk option on the board. You give up every diversification benefit
and take a −29.3% max drawdown — 4.4 points worse than today's already-aggressive book
and nearly double the legacy ensemble's −16.5%. The extra 3.1% CAGR is not compensation
for running a single knife-catching signal with nothing to offset it. PLAYBOOK §1 makes
this point already: every strategy fails the gauntlet alone; the ensemble is what clears
the bar.

## Recommendation

**Primary: A 60 / TOM 20 / TT 20.** Best Sharpe of anything tested (1.17), essentially
the same return as today (13.2% vs 13.6%), and drawdown improves by ~6 points
(−19.0% vs −24.9%). Sleeve A stays at its validated 60% weight. Nothing in the book
holds longer than 5 days except A's rarely-binding 15-day time stop.

**Conservative fallback: revert to the legacy 50/30/20.** Slightly lower return (12.3%)
but the best drawdown (−16.5%) — and, decisively, **it is already fully validated and
documented**. Switching back needs no new evidence, only the code path restored.

**Not recommended: A 100%**, and **not recommended: re-tuning H's hold** (destroys the
edge, needs full re-validation).

## Two things to weigh before committing

1. **Both replacements need a second daily checkpoint.** `tom_exit1` and `tt_bear` are
   both `entry_mode="close"` / `exit_mode="close"` — they act near the close (~3:45pm ET),
   not at the open. The A/H design deliberately collapsed the day to a single
   at-the-open run (PLAYBOOK §3); going back means restoring the "nearclose" runner and a
   second workflow. Alpaca fractional orders are DAY-only, so this is a near-close market
   order, not a true MOC — a small execution difference from the backtest's close fills
   that should be measured once live.

2. **`tt_bear` only trades when SPY < SMA(200) — it is crash insurance, not a workhorse.**
   Trades by year: 2023: 30 · **2024: 0** · 2025: 71 · 2026: 26. In a continuing bull
   market that 20% sleeve sits in cash most of the time, which is exactly why its OOS
   MaxDD is only −4.2%. `tom_exit1` (a steady 120/yr, 10 names × 12 months) is the
   sleeve that actually fills H's hole day to day. Do not expect `tt_bear` to contribute
   until the market turns — that is the point of it.

   Corollary: if you want the replacement to *trade* rather than *insure*, weight toward
   TOM. If you want the drawdown protection, keep TT.

## Work required to deploy

Per the golden rule, the sleeve components (`tom_exit1`, `tt_bear`) are individually
validated with IS/OOS confirmation in `REFINEMENT.md` — but the **60/20/20 weighting is
new** and must go through `backtest/gauntlet.py` + `backtest/refine.py` before it is
deployable. The legacy 50/30/20 needs none of that.

1. Rebuild the data panel (`python -m backtest.data`) — needs open outbound network.
2. Re-run `backtest/gauntlet.py` and `backtest/refine.py` with the chosen weights;
   update `REFINEMENT.md` and `refine_results.json`.
3. Restore the near-close runner and its workflow.
4. Update `playbook/screener.py` (`SLEEVES`), `PLAYBOOK.md`, `run_daily.py`, `CLAUDE.md`.
5. Wind down the 10 open H positions — let their existing exit rules run rather than
   liquidating, so the ledger stays clean.
