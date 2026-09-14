# Sleeve A — response to the survivorship/no-stop critique (Sep 2026)

**Headline: the critique is right on the central point, and one of its predictions is already
confirmed. "Stops hurt this sleeve" does not survive contact with the data — a 15–20% stop is
free on the very sample that should be most hostile to it.**

Status: diagnostic measurement, nothing shipped. `screener.py` and `run_daily.py` untouched.

## 1. Is the universe point-in-time? **No. The critique is correct.**

`backtest/universe.py` builds `data/universe.csv` from **today's** Wikipedia constituent tables
for the S&P 500 and Russell 1000. Its own docstring says so: *"current-constituent —
survivorship bias documented in README"*. 1,006 tickers, all of them companies that exist and
are index members in September 2026.

The bias is documented in three places (`README.md:19`, `PLAYBOOK.md:160-163`, `CATALOG.md:113`)
and `PLAYBOOK.md` even states the direction correctly: *"Mean-reversion benefits from this bias
(the graveyard is delisted names)."*

**Documenting a bias is not measuring it.** The no-stop decision was validated on the sample the
bias was known to flatter, and that gap was never closed. That is a fair hit.

### The confirming evidence the critique did not have

In 11,910 backtest trades, the 15-day timeout fires **once**. Average hold is **1.7 days**.

That looks reassuring — "the 15-day window is never actually load-bearing" — and it is the
opposite. A dip-buyer exits on the first up-close. **A name that is delisting never has an
up-close.** A timeout rate of 1-in-11,910 is not evidence that the timeout is harmless; it is a
direct measurement of a universe in which every name eventually recovers. The exact scenario the
no-stop design has no defence against has been removed from the sample, and the near-zero
timeout rate is the fingerprint of that removal.

So the critique's structural argument is not merely plausible here. It is visible in the data.

## 2. The stop-loss curve — run now, on the biased universe, and it matters anyway

The critique asks for this on an unbiased universe, correctly. But it is informative *now*,
because of an asymmetry:

**The survivorship-biased universe is the worst case for stops.** Every name in it recovered
enough to still be in an index today, so every stop-out is disproportionately likely to be
selling a dip that later came back. Whatever a stop costs here is an **upper bound** on what it
costs in reality; whatever it protects is a **lower bound**.

Sleeve A standalone, 2005-2026, 5 bps/side, everything else fixed:

| Stop | CAGR | Sharpe | maxDD | Worst trade | Win% | PF |
|---|--:|--:|--:|--:|--:|--:|
| **none (live)** | **16.93%** | 1.11 | **−36.5%** | **−43.5%** | 61.0% | 1.31 |
| 25% | 16.81% | 1.11 | −35.7% | −35.6% | 61.1% | 1.31 |
| 20% | 16.88% | 1.11 | −35.7% | −35.6% | 61.1% | 1.31 |
| 15% | **17.03%** | 1.13 | **−33.2%** | −35.6% | 61.2% | 1.31 |
| 10% | 15.81% | 1.08 | −30.4% | −52.8% | 60.8% | 1.28 |
| 7% | 15.06% | 1.05 | −26.9% | −35.6% | 60.8% | 1.26 |
| 5% | 16.05% | 1.12 | −23.2% | −52.8% | 60.8% | 1.27 |

**A 20% stop costs 0.05 CAGR points. A 15% stop costs nothing and improves max drawdown by 3.3
points.** The "stops hurt this sleeve" claim in `CLAUDE.md` is true only for *tight* stops — 7%
costs 1.87 points — and was over-generalised to all stops.

Read the curve carefully, though:

- **Wide levels (15/20/25%) are indistinguishable from each other and from no-stop on return.**
  The 15% "improvement" is noise, not a peak to select. This is a flat region, which is the good
  kind of result: the conclusion is *wide stops are free*, not *15% is optimal*.
- **The 5% and 7% rows are non-monotone** (5% beats 7% on CAGR). That sawtooth is the same
  warning sign that killed Phase 4. Do not read anything into the tight end.
- **Worst-trade gets *worse* at 10% and 5% (−52.8%).** A close-based stop sells at the next open,
  so a tight stop can force a sale into a gap-down that the no-stop version would have ridden to
  a better up-close exit. A stop is not a guarantee of a bounded loss under this execution model.

## 3. Answers to the eight questions

1. **Point-in-time universe?** No — current constituents, delisted names absent. Obtainable only
   from a paid vendor (see §4).
2. **"Long-term uptrend"?** `close > SMA(200)` in the deployed config (the published source spec
   used SMA(100); 200 was selected here from the gauntlet variants). SMA is a trailing rolling
   window, so it is point-in-time *within* each surviving name's history — the bias is in *which
   names exist*, not in the indicator.
3. **Worst single-position loss:** −43.5% (LEN, March 2020). Position size ~10% of sleeve = ~6%
   of account, so ≈ −2.6% of the account. Tail: 0.08% of trades worse than −20%, 1.25% worse than
   −10%. **All of these are survivors.**
4. **Timeout vs up-day:** 1 timeout in 11,910 trades. Average hold 1.7 days. See §1 — this is a
   symptom, not a reassurance.
5. **Where 3 days and 15 days came from:** **inherited, not fitted.** `research/CATALOG.md:35-38`
   documents this as "MR-2 · 3 lower lows + ATR-stretch limit buy (**Alvarez**)" with the
   published baseline spec. The 3-day count and the exit-on-first-up-close rule are the external
   author's. What *this repo* tuned is the stretch (0.5 → 0.75) and the trend filter (SMA100 →
   SMA200). The 15-day time stop is a house addition not in the source spec. So the provenance is
   better than the critique assumed for the entry, and the overfit surface is 2 parameters, not 4.
6. **Held-out period?** Yes, genuinely. `backtest/refine.py` selects on in-sample only
   (2005-06→2022-12) and spends OOS (2023-01→present) exactly once. **But this does not help
   here** — the universe is survivorship-biased in *both* windows, so the OOS window cannot
   correct for it. An honest out-of-sample test of a biased sample is still a test of a biased
   sample.
7. **Limit offset:** volatility-scaled — `close − 0.75 × ATR(10)`, not a fixed percentage.
8. **Fill rates:** backtest 11,910 trades from 205,067 signals (5.8%), but that conflates
   limit-misses with the 10-slot cap and is **not** a fill rate. Live since 2026-08-11: 132
   Sleeve A limit buys submitted, 21 positions opened — **15.9%**. These two numbers are not
   comparable as measured; a proper comparison needs per-order fill/no-fill against the bar's low,
   which is Test 3 and is not yet built.

## 4. What a point-in-time universe actually costs

yfinance cannot supply this — delisted tickers simply disappear. Realistic options are paid:
Norgate, Sharadar (Nasdaq Data Link), Polygon, or CRSP. Order of magnitude is tens of dollars a
month for the retail vendors; CRSP is institutional. A partial free reconstruction of *membership*
is possible from Wikipedia's S&P 500 changes table, but that gives tickers, not the **price
history of dead names**, which is the part that matters.

This is the one blocking dependency for Test 1, and Test 1 is the test that decides whether the
−9% worst year and −25% max drawdown are real numbers.

## 5. What this changes

- `CLAUDE.md`'s "**No stop-loss** (validated: stops hurt this sleeve)" is **over-stated** and
  should be corrected to: *tight stops (≤10%) cost 1–2 CAGR points; wide stops (15–25%) are
  free on the tested sample, which is the sample most hostile to them.*
- A wide disaster stop is no longer an idea that needs to justify itself against a return cost.
  It has no measurable return cost. It now only needs to justify itself against **execution
  risk** — a resting broker stop also closes the "nothing protects the book if the morning script
  fails" gap that is already on the open list.
- None of this ships without Test 1. A stop level chosen on a biased sample is a level chosen on
  the wrong loss distribution.

## 6. Priority, revised

1. **Test 1 — point-in-time universe.** Blocking, needs a paid feed. Everything else is
   provisional until this runs.
2. **Test 3 — realized vs modelled fills.** Measurable this week, needs no new data, and decides
   whether the return projection is 10% or 4%. Highest value per unit of effort.
3. **Test 5 — exit decomposition.** Already run (§1, Q4). Result: the timeout is inert *in this
   sample*, and that is itself the finding.
4. **Test 2 — stop curve.** Run above on the biased universe; re-run on the unbiased one after
   Test 1.
5. **Test 4 — parameter neighbourhood.** Lower priority than it looks: the entry parameters are
   inherited from a published source, not fitted here, so the overfit surface is the stretch and
   the trend filter only.

## 7. Not addressed here

The conditional-correlation point — that A and H decouple in exactly the selloffs where it
matters — is correct in principle and untested. `phase2_upside.py` already computes a winsorized
A/H correlation; what is missing is the same figure **conditioned on market stress** (e.g. SPY
down >2%, or VIX top decile). That is cheap to compute and not yet done.
