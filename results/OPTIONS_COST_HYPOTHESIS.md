# Options feasibility pre-registration — the cost-threshold test

**Written before any number was computed.** Pass/fail criteria are fixed at authoring time,
in the same form as `BREADTH_HYPOTHESIS.md` / `VOLATILITY_HYPOTHESIS.md`.

## What this is, and what it is not

This is **not** a strategy search and it selects **no parameter**. It is a *costing*
calculation: given the trades the deployed A and H sleeves already took, what would the same
trades have returned if expressed as long options instead of stock, and how large a
transaction cost can that structure absorb before the edge is gone?

Because nothing is selected, **no out-of-sample window is spent.** The full 2005–2026 ledger
is used deliberately: this is a measurement of an already-validated config, not a fit to it.
If the answer is favourable, a real strategy hypothesis with a real OOS reservation would
still have to be written afterwards — and could not be run at all without historical options
data (see `OPTIONS_FEASIBILITY.md`, Blocker 1).

## Why the question can be answered without historical options data

The realized *underlying* path endpoints are already in the ledger: every trade has an entry
price, an exit price and a hold length. A European-style option's value at those two instants
is a deterministic function of (S, K, T, r, σ). So the trade can be repriced synthetically
under an assumed implied-vol surface, and the **cost threshold** — the round-trip bid/ask, as
a percentage of premium, at which the strategy's edge reaches zero — falls out exactly.

What this *cannot* do is tell us the actual spread, the actual IV level, or the actual IV
path. That is precisely the data blocker. So the test is deliberately framed the other way
round: instead of asking "what would it have earned", it asks **"what would the options market
have to look like for this to work at all"**, and then asks whether such a market exists.

## Hypothesis (H3)

Expressing Sleeve A and/or Sleeve H entries as long single-name call options, rather than
stock, produces a structure whose **breakeven round-trip transaction cost is wide enough to be
achievable in the real US equity options market** for the names the sleeves actually trade.

## Method

`backtest/options_overlay.py` (new, research-only; touches nothing in `playbook/` or
`papertrade/`).

For each trade in `results/gauntlet_three_lower_lows_trades.csv` (n=14,546) and
`results/gauntlet_high52_deployed_trades.csv` (n=3,147):

1. Normalise the underlying to S₀ = 100 and apply the trade's realized return to get S₁.
2. Price a call at entry with Black–Scholes at (S₀, K, T₀, σ_IV) and at exit at
   (S₁, K, T₀ − hold/252, σ_IV).
3. Strike selected by entry delta target; expiry selected as a fixed DTE.
4. Option return per trade = P₁/P₀ − 1, before costs.
5. Apply a round-trip spread cost c (% of premium, half paid on each side) and solve for the
   **breakeven c** at which mean option return per trade = 0.

**σ_IV is set equal to the realized volatility implied by the ledger's own return
dispersion.** This is deliberate and is the assumption most favourable to options: it sets the
variance risk premium to **zero**, i.e. it assumes the trader buys volatility at exactly fair
value. Any real VRP makes the result worse, never better. It is reported as a sensitivity, not
built into the headline.

Grid (fixed now): entry delta ∈ {0.25, 0.40, 0.55, 0.70, 0.85}; DTE ∈ {14, 30, 45, 60, 90};
σ_IV ∈ {realized, realized+3 vol pts, realized+6 vol pts}; r = 4%.

### Estimator correction — made AFTER a first set of numbers was seen

Recorded here rather than quietly patched, because it is exactly the kind of change this
project's discipline exists to police. **It was not made because the result was unfavourable;
it was made because the estimator was demonstrably wrong, and correcting it moved the answer
in options' favour, not against.**

The first draft estimated σ from the ledger as `stdev(ret / √hold)`. That is invalid here
because **exits are endogenous**: a trade's hold length is determined by the return path, so
conditioning on hold conditions on the outcome. Sleeve H's short-hold trades are *defined* by
having hit the −5% stop — the hold=1 bucket (n=175) has mean −7.32% and a standard deviation
of only 3.72%, because every member of it is a stop-out. Dividing a near-constant −7% by √1
produced an implied annual vol of 59%, and pooling that across buckets gave σ = 50.7% for
Sleeve H, which is not that sleeve's volatility — it is an artifact of the stop.

Estimated instead on the buckets that are *not* selected on outcome:

| Sleeve | Unconditional bucket | n | implied annual vol |
|---|---|--:|--:|
| A | hold = 1 day (the modal exit, 60% of trades) | 8,773 | **35.4%** |
| H | hold = 15 days (the time stop, 65% of trades) | 2,054 | **31.6%** |

Both land at 30–35%, a plausible single-name range. σ is therefore now an **explicit stated
parameter swept over {20, 25, 30, 35, 40, 50}%** rather than a quantity derived from
contaminated data. The pre-registered criteria are evaluated at the measured value for each
sleeve (≈35%), with the rest of the sweep reported as the sensitivity.

Under the original biased estimator Sleeve H was negative before costs in almost every cell.
Under the corrected one it is positive across a wide range. The correction helps the
hypothesis; it is recorded because it was made with results already on screen.

### Two additions made at the same time, for the same reason

1. **Expiry guard.** Cells where the option expires at or before the trade's exit are marked.
   A 14-DTE option is ≈9.7 *trading* days, and Sleeve H's mean hold is 11.78, so every
   14-DTE H cell was pricing an expiry payoff rather than the exit the sleeve actually took.
   Those cells showed the study's largest apparent edge and are artifacts. Every cell at
   DTE ≥ 30 has 0.0% expiry contamination and only those are interpreted.
2. **Vega reported as "vol points of IV crush that erase the edge."** Added because the
   breakeven-spread framing silently assumes a flat IV path, and for Sleeve A specifically
   that assumption is not neutral — see `PHASE5_CONCLUSION.md` (entry-day stock ATR correlates
   0.914 with the VIX). Adding this column could only hurt the hypothesis, and it is added
   for that reason rather than despite it.

## Pass criteria (fixed now)

The options route is judged **feasible enough to justify writing a real strategy
pre-registration** only if all three hold:

1. **Breakeven round-trip spread ≥ 15% of premium** for at least one (delta, DTE) cell, at
   σ_IV = realized. Rationale: published retail round-trip costs on liquid single-name
   options sit in the mid-single-digit to low-double-digit percent-of-premium range, so a
   breakeven below that leaves no margin at all; 15% is the minimum that could survive a
   realistic spread plus any slippage.
2. **The winning cell survives a +3 vol-point variance risk premium** — i.e. it still has a
   positive expected return with σ_IV set 3 points above realized, before spread.
3. **The winning cell is implementable inside the deployed risk model**: one contract of the
   median traded name occupies ≤ the sleeve's validated per-position cap (6% A / 4% H of
   equity) in **delta-equivalent** exposure, at the live account size.

## Kill criteria

Any of these ends it, written up as a rejection with nothing shipped:

- No cell clears a 15%-of-premium breakeven spread.
- The breakeven is positive only because σ_IV was set below any plausible market level.
- Contract granularity forces a delta-equivalent position above the validated cap for the
  median traded name (criterion 3 fails) — the risk model cannot be honoured, so the
  structure cannot be deployed regardless of its edge.

## Known limitations, stated before the run

- **Two-point repricing.** The overlay prices entry and exit only. It cannot model the
  intraday path, an early-exercise decision, or an exit forced by expiry rather than signal.
  For a *long* option with a known exit date this is a minor approximation; it would not be
  for anything short.
- **Flat, constant σ.** No skew, no term structure, no IV path. This is the largest
  simplification and it is why criterion 2 exists.
- **Pooled volatility.** Each sleeve gets one σ estimated from its own pooled cross-sectional
  return dispersion, not a per-name vol. Sleeve A's entries are known to cluster in
  high-volatility conditions (`PHASE5_CONCLUSION.md`: stock ATR vs VIX correlation 0.914), so
  a pooled σ *understates* the entry-time IV A would actually pay, again in options' favour.
- **Survivorship bias** carries over from the underlying ledger unchanged (PLAYBOOK §9).
- **No dividends**, no early assignment, no financing. All small for long calls at these
  horizons and all in options' favour.

Every one of these simplifications is chosen to be generous to the options case. If the
result is negative under assumptions this friendly, it is negative.

## What ships either way

Nothing. `playbook/screener.py` and `papertrade/run_daily.py` are untouched by this phase.
The options ban in `CLAUDE.md` and PLAYBOOK §5 remains in force unless David decides
otherwise on the evidence.
