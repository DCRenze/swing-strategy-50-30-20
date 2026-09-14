# Crypto sleeve feasibility — rejected before design, on supply and testability

**Verdict: do not build it. Crypto was proposed as an answer to the setup-supply
constraint `PHASE6_CONCLUSION.md` identified. Measured, the Alpaca crypto universe
supplies ~127 qualifying Sleeve A setups a year against ~10,000 from the current
stock universe — 1.3% — and produces zero setups on 84% of days. A 10-slot crypto
book has a hard ceiling of roughly 10–21% invested before any question of edge
arises. That is the Phase 6 `everything` configuration (2% exposure, 1.55% CAGR,
rejected) reached by a different route.**

**No backtest was run for this document.** Two blockers are fatal on their own, and
`PHASE5_CONCLUSION.md` sets the precedent: a kill criterion met before the
confirmation stage ends the phase there. Nothing in `playbook/` or `papertrade/` was
touched; no order of any kind was placed.

> **Update — a backtest was subsequently run at David's instruction.** He asked for
> the deployed config over the last three years, having read this document's argument
> that the window cannot support a verdict. Pre-registered in
> `CRYPTO_BACKTEST_HYPOTHESIS.md`, results in `CRYPTO_BACKTEST_RESULT.md`. It failed
> 4 of 6 pre-registered criteria: 1.0% CAGR at 2% exposure against bitcoin's 43.1%,
> on 91 trades — below the README's 100-trade minimum for a testable result. It also
> closed the one objection this document could not: retuning the ATR limit would not
> help, because crypto and equity fill rates are already the same (20.8% vs 22.5%).
> The only correction it forces is in this document's favour: the exposure ceiling
> estimated below as 10–21% is realised at **2%**.

Evidence and reproduction: `backtest/crypto_feasibility.py` (measurement only — it
contains no strategy and no backtest).

---

## Scope note

Leveraged perpetuals are out of scope by PLAYBOOK §5 (never margin). This document
covers **long-only spot crypto** only. Alpaca's spot and perpetuals products are
separate asset classes with separate endpoints, so the boundary is clean.

A housekeeping finding, relevant to anyone auditing this: **`PHASE4_CONCLUSION.md`,
`PHASE5_CONCLUSION.md`, `PHASE6_CONCLUSION.md`, `BREADTH_HYPOTHESIS.md`,
`STRICTNESS_HYPOTHESIS.md` and `VOLATILITY_HYPOTHESIS.md` are not on `main`.** They
exist only on the unmerged branch `claude/portfolio-trading-history-pdlkej` (tip
`92822b0`, 2026-09-08). Everything below cites them from there. Three rejected
hypotheses and the reasoning that killed them are one branch deletion away from
being lost, which is worth fixing independently of this decision.

---

## The five blockers, in the order they were confronted

| # | Blocker | Answer | Fatal? |
|---|---|---|---|
| 1 | Universe size | 19 non-stablecoin USD pairs; **2.2 effective independent bets** | **Yes, combined with 5** |
| 2 | Execution model | Engine transfers untouched; the **live layer is a rewrite** | No — costed below |
| 3 | Data | 2017-11 for the main cohort; **survivorship bias is structural and unfixable** | Serious, near-fatal |
| 4 | Costs | ~55–100 bps round trip, but vol is 3.3× — **not disqualifying on its own** | **No** |
| 5 | Regime length | ~1.5 cycles in-sample, and the one bear year yields 40 setups | **Yes** |

---

## Blocker 1 — the universe is smaller than 19 names, because it is one bet

Alpaca's supported list gives **21 USD-quoted spot pairs**, of which USDC and USDT
are stablecoins and not swing-tradable. That leaves **19 candidates**. Of those,
16 clear Sleeve A's `$10M` 20-day dollar-volume screen (PLAYBOOK §2) — and that
figure uses *global* volume aggregated across all venues, so the liquidity actually
reachable on Alpaca's own book is a fraction of it. Applying Sleeve H's stricter
`$20M` screen would cut further.

But the count is the less interesting number. The question is how many *independent*
bets 19 names represent:

| | Crypto (19 Alpaca USD pairs) | Equity (120-name universe sample) |
|---|--:|--:|
| avg pairwise daily-return correlation | **0.428** | 0.307 |
| PC1 share of variance | 50.2% | 32.8% |
| effective independent bets, N/(1+(N−1)ρ) | **2.2** | 3.2 |

Both windows are 2017-11 onward so the comparison is like-for-like. A 10-position
crypto book would hold **53% of the entire universe simultaneously**, and those ten
positions would carry roughly **two** independent bets between them.

This is precisely the concentration the PLAYBOOK is built to prevent. The ~6%
per-position cap and the 10-slot limit (§5) are only meaningful if the slots are
different bets; here they are the same bet sized ten ways. `PHASE3_CONCLUSION.md`
rejected 2-slot concentration in equities partly on a −60.1% in-sample drawdown. A
19-name crypto book is structurally closer to that than to the deployed config,
without ever setting a parameter that says so.

**Note the comparison that matters most.** The repo's own case for the 60/40 pairing
is that A and H correlate only **0.26**, and that a second mean-reversion sleeve was
rejected for correlating **0.69** with A. Measured against an equal-weighted equity
market proxy, Bitcoin's daily-return correlation is:

| Window | BTC vs equity market |
|---|--:|
| 2017-11 → 2020-12 | +0.217 |
| 2021-01 → 2022-12 | **+0.443** |
| 2023-01 → now | +0.347 |
| Full | +0.285 |

**Crypto is not uncorrelated with equities, and it is least uncorrelated when that
would matter most** — the correlation peaked in the 2021–22 drawdown. At +0.285
full-window, a crypto sleeve would be *more* correlated with the existing book than
Sleeve H already is with Sleeve A (0.26). The diversification argument that motivates
the whole idea does not survive measurement.

---

## Blocker 2 — the engine transfers; the live layer does not

The brief's premise here is wrong, and it is worth correcting because it changes the
cost estimate.

**`backtest/engine.py` contains no calendar or session assumption at all.** It
indexes by row, not by date. Verified empirically rather than by reading: the same
synthetic panel run on a weekday index and on a 7-day calendar index produces an
identical trade ledger and an identical equity curve, and the 7-day run happily
enters positions on Saturdays and Sundays.

```
trades         : 5-day index 299   7-day index 299
final equity   : 5-day index 86,597.25   7-day index 86,597.25
equity identical ignoring date labels : True
trade ledger identical                : True
weekdays entered on the 7-day index   : [0, 1, 2, 3, 4, 5, 6]
```

`"next_open"` means "the Open field of the next row"; `time_stop` counts rows. Feed it
365-row-a-year crypto bars and it runs. **No engine change is required.**

What does not transfer is everything downstream of it:

| Component | Coupling that breaks | Work |
|---|---|---|
| `playbook/screener.py` (339 lines) | `session_complete()`, `US_MARKET_HOLIDAYS`, `America/New_York`, `pd.bdate_range` for month-end math, `"LIMIT buy, day-only, for NEXT session"` | Near-total rewrite |
| `papertrade/run_daily.py` (519 lines) | single pre-open run, `--submit-at 09:30`, `TimeInForce.DAY` on every order, session-anchored day counting, `trigger_session` | Near-total rewrite |
| `.github/workflows/morning-run.yml` | weekday-only pre-open cron | 365-day schedule |
| `papertrade/state.json`, journal | day counts anchored to NYSE sessions | Schema change |
| `papertrade/test_run_daily.py` | guards the completed-bar/raw-close invariants for sessions | New tests |

Two substantive mechanics problems sit underneath the line count:

1. **Alpaca crypto does not support `DAY` time-in-force** — only `gtc` and `ioc`.
   Sleeve A's entire execution discipline is "a resting limit DAY order that simply
   expires unfilled; never convert to market" (PLAYBOOK §3.1, §6). There is no DAY
   order to expire. You would have to emulate expiry by cancelling at a self-chosen
   24-hour boundary, which is new stateful logic in the one place the PLAYBOOK says
   the edge lives or dies. Alpaca also does not support plain stop orders for crypto,
   only stop-limit — relevant if Sleeve H were ever ported.

2. **"The next open" does not mean anything in a continuous market.** In equities the
   open is an auction: a real, liquid, single-price event, and the close→open gap is
   where a dip-buyer's overnight reversion is actually monetised — `LIVE_REVIEW_2026-08.md`
   is a five-week case study in exactly how much that timing is worth. In crypto the
   "open" is whatever printed just after an arbitrary UTC midnight in a market that
   never stopped. The rule would still *execute*; it would no longer be capturing the
   thing it was validated to capture. Yahoo's crypto index is timezone-naive, so the
   exact cutoff cannot even be determined from the data.

Honest estimate: **600–900 lines of new code plus tests**, one to two weeks of careful
work, and a parallel live-execution path to maintain forever alongside the equity one.
That is a real cost but it is not the reason to say no.

---

## Blocker 3 — the data exists, the survivorship problem does not go away

yfinance works for crypto in this environment (via `backtest/yfsession.py`, which
falls back to the `safari` TLS impersonation as documented). What it serves:

- **Genuine 7-day-a-week daily bars.** 4,380 rows for BTC-USD across 4,381 calendar
  days, distributed 625–626 per weekday. Weekends are real bars, not fills.
- **`Adj Close` is identical to `Close`** across the entire panel (max difference
  exactly 0.0) — no dividend/split adjustment, so the repo's adjusted-vs-raw
  distinction collapses. That actually *simplifies* `data.py`.
- **`Volume` is already denominated in USD**, not in coins. BTC-USD's last bar reads
  13.6bn, which is plausible daily spot notional; multiplying by close gives $1.05
  quadrillion, which is not. Any port of `data.py` that reuses the equity
  `close × volume` convention would overstate liquidity by five orders of magnitude.
  (The first-pass probe of this made exactly that error; it was caught on re-run.)
- **History depth:** BTC and LTC from 2014-09-17. The main cohort — ETH, XRP, BCH,
  LINK, DOGE, ADA, XTZ, BAT, MKR — from 2017-11-09. The DeFi cohort (AAVE, AVAX,
  DOT, CRV, SUSHI, YFI, SHIB) from mid-2020. Requesting `start="2010-01-01"` surfaces
  nothing earlier.

**Three of the 19 currently-listed Alpaca pairs are unusable from the free source.**
GRT-USD ends 2022-04-01. UNI-USD ends 2025-04-17 and reports a median daily dollar
volume of $11. MKR-USD reports $170k, implausible for that asset. These are live,
tradable pairs whose free history is broken or truncated — so the data source silently
disagrees with the broker's list, in both directions.

The deeper problem is not fixable with a better data source:

**The universe is Alpaca's list as it stands today, projected backwards.** PLAYBOOK §9
already flags this for equities and notes mean-reversion *benefits* from it. In crypto
the bias is far larger and there is no remedy, because there is no crypto equivalent of
`backtest/universe.py` reconstructing point-in-time index membership. Ammann, Burdorf,
Liebi & Stöckl (SSRN 4287573, 2022) put the annualised survivorship-and-delisting bias
in equal-weighted crypto portfolios at **62.19%**, against 0.93% value-weighted, across
3,904 assets of which ~1,222 delisted between 2014 and 2021. A CryptoRank study
(2026-07-30) finds 13 of the July-2021 top 100 dead or delisted five years on, four of
them from inside the top 40. Free data sources largely drop dead coins: CoinGecko gates
inactive-coin history behind paid tiers, and Yahoo returns "possibly delisted, no price
data" once a symbol goes.

So a crypto backtest would be run on the survivors, by construction, with a documented
bias an order of magnitude larger than the one the repo already treats as a serious
caveat. There is no honest way to correct for it with the sources available.

---

## Blocker 4 — costs are a real headwind, but they are NOT disqualifying

This blocker does not fire, and saying so matters more than piling on.

Alpaca's crypto fee schedule, base tier ($0–$100k monthly volume): **0.15% maker /
0.25% taker**. Quoted spreads on major venues are ~0.1–5 bps for BTC/ETH and, on a
lower-rigour secondary estimate, ~20–50 bps for rank-20-to-100 alts. Round trip:

| | Round-trip cost |
|---|--:|
| Crypto, BTC/ETH, taker both sides | ~51–55 bps |
| Crypto, mid-cap alt, taker both sides | ~70–100 bps |
| Equities, modelled | 10 bps |
| Equities, measured live (`PHASE3_CONCLUSION.md`) | ~24 bps |

Set against `PHASE3_CONCLUSION.md`'s finding that Sleeve A is at zero CAGR by 20 bps
*per side*, that looks instantly fatal. **It is not, and the reason is volatility.**
Median annualised volatility across the crypto universe is **112.5%** against **34.5%**
for the equity sample — a factor of **3.3**. A mean-reversion edge scales with the
amplitude of the moves it harvests, so the meaningful quantity is cost as a share of
available edge, not cost in absolute bps:

- Equities: ~10 bps cost against a ~40 bps round-trip breakeven → cost consumes **~25%**
  of the edge.
- Crypto: ~75 bps cost against a vol-scaled ~132 bps breakeven → cost consumes **~55%**.

Roughly twice as punishing, not five times. That is a serious headwind and it would
make an already cost-fragile sleeve considerably more fragile — but on its own it would
not stop a genuinely good strategy, and this document should not pretend otherwise.

**One asymmetry is worth flagging even so.** Sleeve A survives its cost-fragility in
equities only because its resting limit orders *provide* liquidity at a commission-free
broker, so realised slippage should approach zero. On Alpaca crypto, a filled resting
maker order still pays 15 bps. The escape hatch is closed: the floor is **30 bps round
trip no matter how patiently you execute**, before any spread. There is no version of
this where careful execution gets you to the 5 bps the validation assumed.

The vol-scaling argument above also assumes the mean-reversion edge exists in crypto at
all and scales linearly with volatility. Neither is established. It is offered to keep
this blocker honest, not as a finding.

---

## Blocker 5 — the window cannot carry the test, and one bear year proves it

Applying the repo's own split to the data that exists:

| | In-sample | Out-of-sample |
|---|---|---|
| Equities (deployed) | 2005-06 → 2022-12, **17.5 yrs**, 3+ cycles incl. 2008 | 2023+, 3.5 yrs |
| Crypto (best available) | 2017-11 → 2022-12, **5.1 yrs** | 2023-01 → now, 3.7 yrs |

Raw signal counts clear the README's ≥100-trade bar — 446 in-sample and 675
out-of-sample, after the $10M liquidity screen. But those numbers are far weaker than
they look:

- They land on **224 and 290 distinct dates**, active on only **12% and 21% of days**,
  at ~2 names per active date, with **31–36% of all signals on the busiest 10% of active
  dates**. At ρ=0.428 across names, same-date signals are near-duplicates of one
  another. This is exactly the diagnostic `PHASE4_CONCLUSION.md` applied to the live
  record — "27 trades came from 8 distinct entry dates, 19 of them from just two
  sessions — roughly three independent bets."
- Equities, same measure, same windows: active on **66% and 88%** of days at ~6 names
  per active date.

And the in-sample window contains essentially one testable bear:

```
crypto qualifying setups by calendar year
  2018:   10        2022:   40        <- the two crypto bear markets
  2019:  131        2023:  201
  2020:  130        2024:  228
  2021:  189        2025:  233
```

**2022 produced 40 setups for the entire year across 16 names.** The strategy is
structurally switched off in crypto bear markets, so the in-sample window tests one
bull regime, and the out-of-sample window (2023–2026) is *also* predominantly bull.
You would be fitting a bull-market rule and confirming it in a bull market. By this
repo's standards that result would be uninterpretable whichever way it came out — which
is the definition of untestable by construction.

---

## Why it fails: the entry rule stops being a per-name rule

The cleanest way to see the problem is to apply `PHASE5_CONCLUSION.md`'s own test to
Sleeve A's entry feature — dip depth below the 5-day mean, scaled by each name's own
volatility:

| | between-DAY variance share | within-DAY share |
|---|--:|--:|
| Crypto | **59.7%** | 40.3% |
| Equity | 29.9% | 70.1% |

Phase 5 killed an ATR filter for being a regime proxy rather than a per-name choice.
**In crypto, Sleeve A's existing entry feature is twice as much a regime proxy as it is
in equities.** This is not a new filter failing the test; it is the deployed rule
failing it on the new asset class.

The mechanism is visible in the trend gate. `close > SMA200` is written as a per-name
filter. Measured as the fraction of the universe above its own 200-day average on a
given day:

| | p05 | p25 | p50 | p75 | p95 | days <10% up | days >90% up | days 40–60% |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Crypto | 0% | 10% | 30% | 70% | 94% | **21.3%** | **9.3%** | 12.5% |
| Equity | 22% | 48% | 62% | 72% | 87% | 0.8% | 2.7% | 28.1% |

**On 30.6% of days the crypto gate is effectively all-off or all-on for the entire
book at once**, against 3.5% in equities. A per-name trend filter degenerates into a
single market-timing switch. That is where the 84% zero-setup days come from, and why
2022 yielded 40 signals: in a crypto bear market every name fails the gate on the same
day.

---

## The answer to the question that prompted this

`PHASE6_CONCLUSION.md` closed with: *"if the constraint is setup supply, then a
materially larger universe run with a quality filter could plausibly deliver
`rsi5+ibs+bb`'s trade quality at baseline's exposure."* Crypto was a candidate answer.

Measured:

| | Crypto (16 liquid pairs) | Equity (live ~1,000 names) |
|---|--:|--:|
| qualifying setups per year | **127** | ~10,043 |
| per name per year | 6.7 | 10.0 |
| days with zero setups | **84.1%** | 24.8% |

**Crypto supplies 1.3% of current setup supply, and fewer setups per name per year
than equities despite trading 365 days instead of 252.** Apply Phase 6's quality
filter at its ~11% retention rate and the crypto universe yields roughly **14 setups a
year**.

The consequence needs no backtest. `PHASE3_CONCLUSION.md` established that you cannot
deploy capital that has nothing to buy. With 127 setups a year, 10 slots, and Sleeve
A's 3–6 day realised hold:

| avg hold | ceiling on crypto exposure, 10 slots |
|---|--:|
| 3 days | **10.4%** |
| 4.5 days | **15.7%** |
| 6 days | **20.9%** |

That is a hard upper bound, independent of any edge, against the 58.5% Sleeve A
actually averages. And it is generous: it assumes every setup is takeable, none
collides with a held name, and slots are never blocked.

**A crypto sleeve is the Phase 6 `everything` configuration arrived at from the other
direction.** Phase 6 reached 2% exposure and 1.55% CAGR by filtering a large universe
down to almost nothing, and rejected it because *a better trade you almost never take
cannot compound*. Crypto starts there. The answer is already in the file.

---

## The strongest argument for building it anyway

Stated as well as it can be, because it is not empty:

> Crypto's volatility is 3.3× equities'. A dip-buyer's profit per trade scales with the
> amplitude of the dip, so 127 trades a year on 112% vol could out-earn 1,000 trades a
> year on 34% vol even at 15% exposure. The exposure ceiling is only damning if you
> assume return per unit of exposure is constant, and it is not. Sleeve H already runs
> a low win rate and earns through a few large winners; crypto is that shape, more so.
> And 24/7 trading means a signal is never blocked by a weekend.

Three things defeat it.

1. **It is not testable.** Even if true, the only window available is one bull cycle
   in-sample and another out-of-sample, on a survivor-only universe with a 62%/yr
   documented survivorship bias in equal-weighted crypto portfolios. A favourable
   result would not be evidence. Blocker 5 is not a prediction about the answer; it is
   a statement that the question cannot be asked here.
2. **The vol argument cuts both ways.** 112% annualised volatility at ~53% of the
   universe held in 2.2 independent bets is not a Sleeve A risk profile. The book's
   −15%/−20% drawdown circuit breakers (PLAYBOOK §5) were sized against a −24.9%
   ensemble worst case. A sleeve like this would trip them on ordinary crypto weeks,
   which is a different failure than losing money — it would halt the *equity* sleeves
   too.
3. **The diversification premise is false.** BTC correlates +0.285 with the equity
   market full-window and +0.347 since 2023 — worse than the 0.26 A/H correlation the
   book already has. The main reason to want a crypto sleeve does not hold up.

---

## Recommendation

**Do not build a crypto sleeve. Confidence: high** on blockers 1 and 5 (these are
measurements of the data, not inferences about strategy), **moderate** on blocker 3
(survivorship is well documented but the bias magnitude is drawn from published studies,
not re-derived here), **low confidence that costs matter much either way** — blocker 4
does not fire and should not be cited as a reason.

The honest summary is that crypto fails on the exact axis it was proposed to fix. It
was a reasonable hypothesis: uncorrelated, continuous, more hours in the year. Two of
those three turn out not to be true, and the third does not produce more setups.

If setup supply remains the thing to solve, the live thread from
`PHASE6_CONCLUSION.md` is unchanged and still untested: **a materially larger equity
universe with a liquidity screen built into the hypothesis rather than bolted on.**
That direction still has ~10,000 setups a year to work with, a 17-year in-sample
window covering three cycles, a working execution path, and 10 bps costs. Nothing
here displaces it.

---

## What would change this answer

Not a better strategy idea — the blockers are about the asset class, not the rules.
Specifically:

- Alpaca listing enough uncorrelated USD spot pairs to get effective independent bets
  meaningfully above ~5, **and** a point-in-time universe source that includes
  delisted assets.
- A third full crypto cycle of history, so an in-sample window can contain two bears.
- Not a cost improvement. Costs are not what is wrong here.

## Do not revisit without

- A measured answer to the supply question above, not an argument that returns per
  trade are higher. The exposure ceiling is arithmetic; it does not yield to conviction.
- A response to the +0.285 equity correlation, since diversification is the premise.
- A fresh out-of-sample window. This one was **not** spent and remains available.

Already tested and rejected, do not revisit without a new pre-registered hypothesis:
upside management (`PHASE2_CONCLUSION.md`), slot concentration (`PHASE3_CONCLUSION.md`),
entry-breadth gating and clustering throttles (`PHASE4_CONCLUSION.md`), Sleeve A
volatility filtering (`PHASE5_CONCLUSION.md`), stacked entry confirmations
(`PHASE6_CONCLUSION.md`), a spot crypto sleeve (this document).

## Reproduce

```
python -m backtest.crypto_feasibility                 # all sections
python -m backtest.crypto_feasibility --section engine   # the calendar-agnosticism test
python -m backtest.crypto_feasibility --section supply   # the 127-vs-10,000 figure
```

Nothing in that module trades, backtests, or writes. The equity comparison is a
seeded 120-name sample of `data/universe.csv`; the crypto universe is the 19
non-stablecoin USD-quoted pairs on Alpaca's supported list.

## Sourcing and confidence

Facts gathered by subagents were re-derived here where they carried weight. The
per-pair history, liquidity, weekday coverage, `Adj Close`/`Close` identity and
volume-unit findings were re-run directly and corrected — a first-pass probe reported
dollar volumes computed as `close × volume`, which is wrong for Yahoo crypto bars by
five orders of magnitude.

The following could **not** be verified from primary sources in this environment and
should be re-checked before any of it is relied on. Alpaca's own domains, Coinbase,
Kraken and the academic repositories were all blocked to direct fetch, so these come
from search-result extracts:

- The exact current pair count (sources give both 52 and 56) and the full enumeration.
  The USD-quoted list used here is 21 assets including two stablecoins.
- The fee tier table. Two independent searches returned identical numbers, which is
  reassuring but is not the same as reading the disclosure PDF.
- Crypto `gtc`/`ioc`-only time-in-force and the absence of plain stop orders — single
  source each, and load-bearing for the Blocker 2 rewrite estimate.
- Mid-cap altcoin spreads of 20–50 bps, which come from a low-rigour secondary source
  and are an order-of-magnitude estimate only. No study was found giving effective
  spread or realised slippage at $1k–$10k order sizes for rank-20-to-100 assets.

None of these load-bearing uncertainties sit under blockers 1 or 5, which rest on
measurements re-run in this session against data in hand.
