# Phase 4 pre-registration — does entry-day breadth predict Sleeve H trade quality?

**Written before any Phase 4 backtest was run.** Pass/fail criteria below are fixed at
authoring time so the OOS window cannot be re-cut after seeing it. This is the "new
pre-registered hypothesis" that `CLAUDE.md` requires before re-opening anything about
Sleeve H.

## Where this came from

The Aug 2026 live review (`LIVE_REVIEW_2026-08.md`) listed entry clustering as open item
G2, on the assumption that filling all ten H slots in one session (07-01, 08-06) was a
*risk* worth throttling. Bucketing the 3,147 recorded `high52_deployed` backtest trades by
how many H entries fired on the same session says the opposite:

| Entries that session | n | Win rate | Avg return | Profit factor |
|---|--:|--:|--:|--:|
| 1–2 | 1769 | 45.6% | +0.48% | 1.16 |
| 3–5 | 994 | 50.7% | +0.55% | 1.22 |
| 6–7 | 133 | 53.4% | +0.89% | 1.41 |
| **8–10** | **251** | **57.4%** | **+1.22%** | **1.63** |

OOS-only (2023+) the ordering holds: 45.1% / 50.6% / 66.7% / 69.2%.

So G2 as originally framed — *throttle* clustered entries — would delete the sleeve's best
trades. It is rejected on this evidence and should not be built.

## Hypothesis (H1)

A session on which many liquid names simultaneously print a new 252-day closing high on
above-average volume is a **market-breadth thrust**, and breakouts bought into that thrust
have a materially higher hit rate than an isolated breakout. Therefore **requiring a
minimum number of same-day H signals, and taking none when the count falls short**, should
raise Sleeve H's profit factor and win rate without relying on any change to the exit.

This is an *entry-selection* rule. It touches no validated parameter: lookback (252), stop
(5%), time stop (15d), regime gate (SPY > SMA100), slot count (10) and ranking (6-month
momentum) all stay exactly as deployed. `min_same_day_signals=None` reproduces the
deployed config bit-for-bit.

### Why this is not a re-litigation of Phase 2 or Phase 3

- **Phase 2** (`PHASE2_CONCLUSION.md`) tested *upside management* — trailing stops, profit
  targets, give-back stops, breakeven stops, hold extension. All exit-side. H1 changes no
  exit.
- **Phase 3** (`PHASE3_CONCLUSION.md`) tested *slot concentration* for Sleeve A — position
  sizing. H1 changes no sizing and is Sleeve H.

Neither covers entry selection by same-day signal count.

### The obvious way this is wrong

The bucket table is computed on *trades that were actually taken*, which is already filtered
by the engine's 10-slot cap and momentum ranking. On a high-breadth day the engine takes the
10 highest-momentum names out of many candidates; on a 1-signal day it takes whatever the
single name is. So some of the measured edge is **selection quality from a deeper candidate
pool**, not breadth per se — and that part is *already captured* by the deployed config. The
backtest below is what separates the two, because a breadth gate only changes which
*sessions* trade, not which names are picked within a session.

There is also a straightforward exposure cost: gating out low-breadth sessions removes
trades and idles capital. If the retained trades are not enough better to pay for the lost
compounding, the sleeve's CAGR falls even as its profit factor rises.

## Method

`backtest/phase4_breadth.py`, two stages, mirroring `phase2_upside.py`:

- **Stage 1 (`--stage is`)** — thresholds N ∈ {1 (baseline), 2, 5, 8, 12, 16, 20, 25} on
  **in-sample only** (2005-06 → 2022-12). Selection happens here.

  *Grid correction, made before any performance number was computed:* the first draft of
  this document proposed N ∈ {2,3,4,5,7,10}. Measuring the raw signal distribution showed a
  mean of **9.9 H signals per session** (median 7, p75 14, p90 23, max 156) — the universe
  throws far more breakouts than the 10 slots can take, so N=3 would gate out only 15% of
  sessions and would barely be a treatment at all. The grid was rewidened to span the actual
  quantiles (p25 → p90). This was chosen from signal *density* only; no equity curve,
  profit factor or return had been looked at.

  That measurement also sharpens the pre-registered objection below: a "10-entry day" in the
  motivating bucket table means *ten slots happened to be free and at least ten signals
  existed*. It is partly a measure of free capital, not of breadth.
- **Stage 2 (`--stage oos --confirm <label>`)** — **one** OOS confirmation
  (2023-01 → present) for the IS-selected finalist(s). OOS is spent once.

Sleeve A is held at its validated config. 5 bps/side slippage. Both the sleeve and the
deployed 60/40 A/H ensemble are measured, because the ensemble is what clears the gauntlet.

## Pass criteria (fixed now)

A threshold is adopted **only if all five hold**, each measured against the baseline in the
*same run* rather than against a quoted historical figure:

1. **IS plateau, not a peak.** The selected N sits inside a run of neighbouring thresholds
   that all beat baseline on sleeve profit factor. A single N that works with worse
   neighbours on both sides is an artifact — this is precisely what disqualified the Phase 2
   finalists.
2. **Sleeve H OOS profit factor > baseline OOS profit factor**, and > 1.30 absolute.
3. **Ensemble OOS Sharpe ≥ baseline ensemble OOS Sharpe.** A sleeve improvement that the
   book does not see is not an improvement.
4. **Ensemble OOS max drawdown no worse than baseline by more than 2 percentage points.**
5. **Diversification preserved** — winsorized A/H correlation rises by no more than 0.05.
   The book's edge is the 0.26 correlation; a variant that buys sleeve quality by making H
   behave like A is spending the thing that clears the bar.

Trade-count floor: ≥ 100 full-window H trades, or the result is not interpretable.

## Kill criteria

Any of these ends it, with the result written up as a rejection and no code shipped:

- The IS curve is non-monotone / no plateau exists.
- The finalist's OOS profit factor flips below baseline (the Phase 2 failure mode).
- Ensemble OOS Sharpe falls.
- The gate removes so many sessions that full-window trades drop under 100.

## What ships either way

Nothing in `playbook/screener.py` or `papertrade/run_daily.py` changes as part of this
phase. `min_same_day_signals` defaults to `None`, so the deployed H config is untouched
until a separate, explicit deployment decision is made on this evidence.
