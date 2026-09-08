# Phase 4 conclusion — the breadth hypothesis is rejected, and so is G2

**Verdict: H1 fails its own pre-registered criteria. Nothing ships. `screener.py` and
`run_daily.py` are untouched. Sleeve H's expected win rate remains ~48.5%, and no
entry-side gate tested here moves it.**

Pre-registration: `BREADTH_HYPOTHESIS.md` (criteria fixed before any run).
Evidence: `PHASE4_BREADTH_IS.md`, `PHASE4_BREADTH_OOS.md`, `phase4_breadth_{is,oos}.json`.

## What was asked

Live Sleeve H is running an 18.5% win rate against a 48.5% backtest benchmark. Bucketing
the 3,147 recorded backtest H trades by same-session entry count suggested a strong
gradient — 45.6% win rate on 1–2 entry days rising to 57.4% on 8–10 entry days, profit
factor 1.16 → 1.63 — which held out-of-sample. H1 asked whether requiring a minimum count
of same-day signals, and skipping the session otherwise, converts that gradient into edge.

## In-sample: a sawtooth, not a plateau

| Config | H PF | H win% | Ens Sharpe | Ens maxDD | H expo |
|---|--:|--:|--:|--:|--:|
| **baseline** | **1.15** | **48.7%** | **0.97** | **−20.0%** | 0.70 |
| breadth2 | 1.22 | 49.6% | 1.04 | −19.1% | 0.69 |
| breadth5 | 1.19 | 50.7% | 1.01 | −19.2% | 0.67 |
| breadth8 | **1.10** | 49.7% | 0.94 | −24.2% | 0.64 |
| breadth12 | 1.17 | 49.6% | 1.03 | −23.2% | 0.56 |
| breadth16 | 1.14 | 47.7% | 1.04 | −25.6% | 0.51 |
| breadth20 | 1.16 | 48.7% | 1.07 | −24.5% | 0.44 |
| breadth25 | 1.09 | 48.3% | 1.03 | −26.9% | 0.36 |

Profit factor across the grid: 1.15 → **1.22 → 1.19 → 1.10 → 1.17 → 1.14 → 1.16 → 1.09**.
That is a sawtooth. `breadth8` sits *below baseline* between two above-baseline points, and
the sequence never settles. Criterion 1 (IS plateau, not a peak) is not met anywhere on the
grid. Only `breadth2` and `breadth5` beat baseline at all, and they form a two-point run
bounded by baseline on one side and a collapse on the other.

Note also how little the win rate moves: 48.7% → 49.6% → 50.7%. The bucket table implied
46% → 57%. **Nine points of the apparent gradient did not survive being turned into a rule.**

## Out-of-sample: one sign flip, one null

OOS was spent once, on `breadth2` and `breadth5` — the only two configs that beat baseline
in-sample.

| Config | H PF | H win% | H trades | Ens CAGR | Ens Sharpe | Ens maxDD | corrW |
|---|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | **1.41** | **48.4%** | 624 | 15.58% | **1.09** | −15.5% | 0.385 |
| breadth2 | 1.44 | 48.6% | 622 | 16.19% | 1.13 | −16.3% | 0.378 |
| breadth5 | **1.36** | 48.8% | 605 | 14.26% | **1.00** | −17.6% | 0.404 |

**`breadth5` flipped sign.** In-sample it beat baseline (PF 1.19 vs 1.15); out-of-sample it
lost to baseline on profit factor (1.36 vs 1.41) *and* dragged ensemble Sharpe from 1.09 to
1.00. This is precisely the Phase 2 failure mode — a clean in-sample improvement that
reverses on fresh data — and it triggers the pre-registered kill criterion.

**`breadth2` is a null dressed as a pass.** It technically clears criteria 2–5: OOS PF 1.44
> 1.41, ensemble Sharpe 1.13 ≥ 1.09, drawdown 0.8pp worse (inside the 2pp allowance),
correlation slightly *improved* (0.378 vs 0.385). But it fails criterion 1, and the reason
is fatal on inspection: **it removes 2 of 624 OOS trades.** A profit-factor gain resting on
two observations is not evidence of anything. Its in-sample treatment was barely larger — 33
trades of 2,520. Requiring "at least 2 signals today" is not a strategy change; it is a
coin-flip on a handful of sessions.

Applying the pre-registered rule as written: `breadth5` is killed by the sign flip,
`breadth2` is killed by criterion 1. **No config is adopted.**

## Why the bucket table lied

`BREADTH_HYPOTHESIS.md` pre-registered the objection, and it is what happened.

The raw H signal pool averages **9.9 names per session** (median 7, p75 14, p90 23, max
156) — the universe throws far more breakouts than 10 slots can hold. So a "10-entry day"
in the motivating table does not mean *the market was broad*. It means **ten slots happened
to be free**, and the engine then picked the ten highest-momentum names from a deep pool.

That gradient is therefore mostly two things the deployed config **already captures**:

1. **Selection depth** — a deeper candidate pool makes the momentum ranking more selective,
   and the ranking is already in the deployed spec.
2. **Free capital** — slots empty because prior positions just resolved, which correlates
   with market conditions in ways that have nothing to do with today's breadth.

A breadth gate changes only *which sessions trade*, never *which names are picked within a
session*. That is why it recovers almost none of the apparent effect: the effect was never
in the sessions.

## G2 is also closed

The Aug 2026 live review listed entry clustering (G2) as untested, on the assumption that
filling ten H slots in one session was a risk worth throttling. It is not: clustered-entry
trades are the sleeve's *best* trades (PF 1.63 on 8–10 entry days vs 1.16 on 1–2), and the
ordering holds out-of-sample. **Throttling them would delete the best cohort.** G2 should be
struck from the open list — not implemented, and not re-raised in that form.

## What this means for the live record

Sleeve H's live 18.5% win rate over 27 trades is **not** something an entry rule fixes,
because there is no entry-side defect to fix. Those 27 trades came from 8 distinct entry
dates, 19 of them from just two sessions — roughly three independent bets. The expected win
rate is ~48.5%, the deployed config reproduces it out-of-sample (48.4%), and nothing in this
sweep moved it by more than a point in either direction.

The honest conclusion is the uncomfortable one: **there is no win-rate problem to solve in
Sleeve H yet, and the sample is far too small to claim one exists.** PLAYBOOK §8's six-
rolling-month trigger remains the right instrument, re-baselined from the Phase 0 fix date.

## Do not revisit without

- A hypothesis about *which names to pick within a session*, not which sessions to trade —
  that is where the deployed config's edge actually lives, and where the bucket table's
  gradient came from.
- A fresh OOS window. This one is spent.

Already tested and rejected, do not revisit without a new pre-registered hypothesis:
upside management (`PHASE2_CONCLUSION.md`), slot concentration (`PHASE3_CONCLUSION.md`),
entry-breadth gating and clustering throttles (this document).
