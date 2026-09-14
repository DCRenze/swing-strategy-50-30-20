# Options feasibility — the ban should stand

**Verdict: keep the ban. Nothing here justifies lifting it.** The evidence against is not
mainly that options are expensive — that turned out to be the weakest of the five objections.
It is that (a) an options overlay does not touch the constraint this book actually has, (b)
the validated risk model has no options analogue at this account size, and (c) the one result
that came close is a bet on a quantity that cannot be measured without data this project
cannot practically buy.

Pre-registration: `OPTIONS_COST_HYPOTHESIS.md`. Evidence: `OPTIONS_OVERLAY.md`,
`options_overlay.json`, `backtest/options_overlay.py`.

**Nothing in `playbook/` or `papertrade/` was touched. No order was placed.** Any decision to
change the ban is David's, and would additionally require the full gauntlet + refine chain in
CLAUDE.md's Golden Rule before anything shipped.

**Confidence: high** that the ban should stand for the book as it exists today. **Moderate**
on the narrower claim that no options strategy could ever work here — see §9, which is
deliberately the strongest case against my own conclusion.

---

## 1. The question that comes first: does this address the real constraint?

It does not, and this is the single most important finding in the document.

`PHASE6_CONCLUSION.md` identified the binding constraint on this book explicitly:

> "The binding constraint on this book is not the quality of its entry rule. It is **how many
> good setups the universe produces per year.**"

Phase 3 hit the same wall from the other side — "you cannot deploy capital that has nothing
to buy" — and Phase 6's one open thread was a *larger universe*, i.e. more underlyings.

**Options are derivatives of the same ~1,000 names.** A call on AMAT fires on exactly the
days the AMAT stock signal fires. An options overlay changes the *payoff shape* of trades the
book already takes; it produces **zero additional setups**. Whatever else is true, this
project cannot be the answer to the problem Phase 6 identified.

What an options overlay *does* supply is **leverage** — 5–25× delta-equivalent exposure per
dollar of premium, per §7's model. So the honest description of "use options to put idle
capital to work" is: *apply leverage to the same trades*. PLAYBOOK §5 bans margin in the same
sentence it bans options, and Phase 3 already priced concentration — the other way of adding
position risk — and found it "a leverage dial disguised as an efficiency gain," with
in-sample winners that did not survive out-of-sample.

This is Phase 4 and Phase 5's failure mode arriving one level up. Both died because a
compelling feature turned out to be a proxy for something the strategy already exploited, or
already had. Here, the proposal is a proxy for a risk decision the playbook has already made
twice. **If the real question is "should this book take more risk per setup," that question
should be asked directly, tested as a sizing change, and answered on its own evidence — not
smuggled in as an instrument choice.**

## 2. Blocker 1 — historical data: surmountable for money, but not at the right time of day

This was nominated as the critical path. It is serious but it is **not** the thing that kills
the project, and reporting it as fatal would be wrong.

**Data with real bid/ask does exist, and is buyable at hobbyist prices:**

| Source | Bid/ask? | History | Price | Granularity |
|---|---|---|---|--:|---|
| DeltaNeutral / historicaloptiondata.com L2 | yes (bid, ask, OI, volume, IV, greeks) | **2002–present**, ~5,900 underlyings | **$1,495 one-time** (L3: $2,035) | end-of-day |
| ORATS Near-EOD | yes (full chain, IV, greeks) | 2007–present, 5,000+ symbols | $599 one-time + $99/mo | ~14 min before the close |
| ORATS 1-minute intraday | yes | **Aug 2020 only** (~6 yrs), ~28 TB | $399/mo | 1-minute |
| Cboe DataShop quote intervals | yes (NBBO) | 2004–present | ~$1,000/mo (10-min) – $5,000/mo (1-min) | intraday |
| Alpaca historical options | yes (OPRA) | **Feb 2024 only** (~2.6 yrs) | free tier 15-min delayed; OPRA via paid add-on | intraday |
| yfinance | live chain only, **no history** | — | free | — |
| dolthub/options (free) | yes | 2019–mid-2024, ~2,100 symbols, unverified provenance | free | EOD |

So "there is no data" is false. **$1,495 buys 24 years of end-of-day bid/ask across the whole
US equity options market.** That is a real option and I will not pretend otherwise.

**The problem is the time of day, and it is specific to this system.** Every rule in this
repo is "signal from the last completed close, execute at the next **open**" — the whole of
Phase 0 and the August live review is about honouring that timing. An EOD or near-close
options snapshot gives a quote at 15:46 or 16:00. **You cannot backtest a 09:30 fill with a
16:00 quote.** For stocks that mismatch is a rounding error, because the spread is 1–5 bps
and roughly constant through the day. For options it is not: quotes are widest at the open
(the U-shaped intraday spread pattern), and the spread *is* the entire question.

Data at the right time of day is either 6 years deep and 28 TB (ORATS 1-minute, $399/mo) or
$1,000–5,000/month (Cboe). Neither is compatible with a project whose standard is 21 years of
free daily bars that anyone can reproduce.

**Verdict on Blocker 1: not fatal, but it downgrades the evidentiary standard from
"reproducible on free data over 21 years including 2008 and 2020" to "a paid, unauditable,
shorter dataset measured at the wrong moment of the session."** For a project whose entire
culture is the validation chain, that is a large step down, and it should be priced as one.

## 3. Blocker 2 — the risk model does not survive contract granularity

This is a hard structural failure and the clearest reason to stop.

The book's sizing is **fractional shares**: position = weight/10 of equity, qty = size ÷
price. PLAYBOOK §2 is explicit that this is what "enables the full 20-name book on a $1–2k
account." **Options have no fractional equivalent. The minimum is one contract = 100 shares.**

At the live account (equity $96,900 on 2026-08-18) and the median entry price of the 89
trades actually taken since 2026-07-01 ($216.60):

| | |
|---|--:|
| Sleeve A per-position cap (6%) | $5,814 |
| Sleeve H per-position cap (4%) | $3,876 |
| 1 contract, raw notional | $21,660 = **22.4% of equity** |
| 1 contract at 0.55 delta, delta-equivalent | $11,913 = **12.3% of equity** |
| 1 contract at 0.85 delta, delta-equivalent | $18,411 = **19.0% of equity** |

One contract at a normal delta is **2–3× the position cap the whole validation rests on.**

Tuning to a low delta partly escapes this — a 0.25-delta contract on the median name is
$5,415, or 5.6%, which does fit inside A's 6% cap. But:

| entry delta | max underlying price for 1 contract to fit the cap | share of live-traded names that fit |
|---|--:|--:|
| 0.25 (Sleeve A, 6%) | $233 | **56%** |
| 0.55 (Sleeve A, 6%) | $106 | 24% |
| 0.25 (Sleeve H, 4%) | $155 | **39%** |
| 0.55 (Sleeve H, 4%) | $70 | 9% |

So even in the most favourable corner, **44% of the names Sleeve A actually trades cannot be
expressed as a single option contract without breaching the validated position cap**, and for
Sleeve H it is 61%. And inside that corner, sizing is all-or-nothing: one contract or none,
with no ability to size to the cap.

The alternatives are both disqualifying. Size by *premium spent* instead of delta and a $5,814
Sleeve A slot buys **6.1 contracts** of a 30-day 0.55-delta call on the median name (σ=35%,
$948/contract) — **$73,000 of delta-equivalent exposure, 75% of the account in one position**.
At 0.25 delta it is 18.8 contracts and **105% of the account**. That is leverage, which the
playbook forbids in the same sentence as options. Or restrict the universe to cheap stocks, which is a different
strategy with a different (and per Phase 6, liquidity-fragile) universe that would need its
own validation from scratch.

**There is no version of this that honours the deployed risk model at this account size.**
The drawdown circuit breaker in `papertrade/run_daily.py` is not the problem — it reads
account equity and would work unchanged. The problem is upstream: the per-position cap, which
is what keeps a −24.9% ensemble drawdown from being a −60% one, cannot be expressed.

## 4. Blocker 3 — unattended execution, with an expiry date attached

The system checks positions **once per morning**, computes everything from completed bars, and
**leaves nothing resting at the broker**. If the run does not fire, nothing happens at all.

It has already missed. On **2026-08-18** the journal records
`signal_date: 2026-08-14, trade_date: 2026-08-18` — signals one session stale (2026-08-17 was
a Monday). Exits that session were evaluated against Friday's close. No exit fired.

**On stock, that costs one day of drift.** A Sleeve A position is worth what it is worth; the
exit happens a session later at a slightly different price, and the August review measured the
whole class of timing error at roughly −19 bps per Sleeve A exit.

**On options, the same miss is categorically different**, for three reasons, in ascending
order of seriousness:

1. **Decay runs on a calendar, not on the trade.** A missed session is a missed session of
   theta whether or not the underlying moved. At 30 DTE that is ~1.7% of premium per calendar
   day, and the weekend the 08-18 incident spanned was three of them.
2. **Leverage multiplies the drift.** The same one-day underlying move that costs a stock
   position 19 bps costs a 12× levered option position ~230 bps of premium.
3. **Expiry is a hard wall with assignment behind it.** Alpaca auto-exercises long options
   ITM by $0.01+ at expiry, and stops accepting opening orders in expiring contracts from
   15:30 ET on expiration day. If the account cannot fund the resulting stock purchase,
   Alpaca liquidates the position itself shortly before expiry — and per its own support
   material, if it cannot, the customer is liable for the shortfall. A once-a-day unattended
   runner that has already skipped a session would be delegating that decision to the broker's
   auto-liquidation logic, on the broker's timing, at whatever price it gets.

Point 3 is the one that matters. The playbook's stand-down rules assume that *not acting* is
always safe — "an unfilled limit is simply no trade." **With options that assumption is
false**: not acting is itself an irreversible decision that expiry makes for you. Every
guardrail in §5 of the PLAYBOOK is built on the premise it would break.

*(Source note: Alpaca's exercise, assignment and expiry-liquidation policies are from Alpaca's
own support and API documentation, reached via search — `docs.alpaca.markets` and
`alpaca.markets` are blocked by this environment's egress proxy, so I could not load and quote
the primary pages verbatim. These should be read directly before anyone relies on them.)*

## 5. Blocker 4 — costs: real, but the *weakest* of the five objections

This was expected to be decisive. On the evidence it is not, and saying so is more useful
than confirming the expectation.

Published spread data, converted to underlying-equivalent terms, is survivable:

- SEC Options Market Structure Roundtable supporting data (April 2026): median **effective**
  spread on options on the **10 most liquid underlying equities** fell from 1.3% (2012) to
  **0.9%** (2025); ETP options fell 1.9% → 1.4%. Effective spreads for the *remaining*
  underliers **rose** over the same period.
- Muravyev & Pearson, *Options Trading Costs Are Lower than You Think* (RFS 2020): effective
  spreads for traders who time executions are under 40% of conventional measures — **but that
  result requires timed limit execution, not a market order at the open**, which is exactly
  what this system sends.
- CCMR / Bryzgalova-Pavlova-Sikorskaya on retail flow: average quoted spread **13.4%**,
  effective **11.1%** market-wide; for weekly options quoted 12.6% / effective 6.6%. Retail
  self-selects into cheap, short-dated, wide-percentage contracts.
- Penny Interval Program: ~300 most active classes on sub-$200 underlyings quote in $0.01
  under $3.00 and $0.05 above; everything else is $0.05/$0.10. That tick floor alone puts
  1–3% of value into the spread on a modestly priced contract.

Against the model in §7, a **2–3% round-trip spread on a liquid name is inside Sleeve A's
breakeven** at its measured volatility, and comfortably inside Sleeve H's. The cost objection,
taken alone, does not kill this. It bites hard in the low-delta / short-dated corner — the
only corner where §3's sizing constraint is satisfiable — where spreads run 6–13%, but that is
a squeeze, not a knockout.

*(The SEC figures above are from search summaries of the SEC's PDF; `sec.gov` is also blocked
by this environment's egress proxy, so I could not verify them against the primary document.
The 0.9% top-10 figure was independently corroborated across searches; treat the rest as
needing a direct read.)*

## 6. Alpaca capability check — no obstacle here

For completeness, the broker is not the limitation:

- **Level 2** permits long calls and puts; **Level 3** adds spreads, straddles, condors,
  submitted as single multi-leg (`mleg`, 2–4 leg) API orders. No uncovered short options at
  any level, which is consistent with the playbook's own prohibitions.
- **No Alpaca commission**; pass-through regulatory fees are roughly $0.05/contract per side
  (ORF ~$0.023, OCC $0.025, plus TAF on sells) — negligible against any premium at the sizes
  in §3.
- **Index options are now live** on the Trading API (announced early September 2026; SPX,
  SPXW, VIX, VIXW, DJX, XSP in the paper rollout), so the "coming soon" status in the brief is
  out of date. These are cash-settled and European-style, which removes early assignment —
  genuinely relevant, and picked up in §9.
- Paper trading supports single and multi-leg options, but fills are simulated and order size
  is **not** checked against real NBBO size, so paper fills would systematically overstate
  achievable liquidity. Paper trading could not be used to validate this.

## 7. What was measured, and what it says

`backtest/options_overlay.py` prices every trade in the two deployed ledgers (A: n=14,546; H:
n=3,147; 2005–2026) as a long call bought at entry and sold at exit, and solves for the
**round-trip bid/ask, as a percentage of premium, at which the edge reaches zero.** It needs
no option chains, because the underlying path endpoints are already in `results/`.

Every assumption is set in options' favour: implied vol equals the sleeve's own measured
realized vol (**zero variance risk premium**), no skew, no term structure, no IV path, no
dividends, both legs fill at mid with the spread applied separately. Volatility is measured
from the buckets *not* selected on outcome — Sleeve A's 1-day exits (n=8,773 → **35.4%**) and
Sleeve H's 15-day time stops (n=2,054 → **31.6%**). Cells where the option expires before the
trade exits are excluded as artifacts; only DTE ≥ 30 is interpreted. The estimator correction
that produced these figures is recorded in the pre-registration, including that it was made
after seeing results and that it helped the hypothesis.

### The one number that does not depend on the volatility assumption

Leverage does **not** buy cost tolerance. It scales the edge and the cost by the same factor,
so the honest comparison is the option spread re-expressed in the bps/side units
`PHASE3_CONCLUSION.md` already measured the stock sleeve in:

| Sleeve A, breakeven cost in underlying-equivalent terms | |
|---|--:|
| across all DTE ≥ 30 cells, σ = 35% | **12.9 – 19.0 bps/side** |
| PHASE3: Sleeve A CAGR at 12 bps/side (measured live) | 9.6% |
| PHASE3: Sleeve A CAGR at **20 bps/side** | **0.4% — the cost cliff** |

**The options version of Sleeve A tolerates roughly the same cost the stock version already
dies at.** That is not a coincidence and it is not fixable by strike or expiry selection: it
is the same trades, and re-expressing them through a levered instrument cannot manufacture
edge the underlying move does not contain.

### The number that kills Sleeve A specifically

The model assumes a flat implied-vol path. Sleeve A cannot have one. It buys after **three
consecutive lower lows** and sells on the **first up-close** — it enters into a falling tape
and exits into a bounce, typically the next day. `PHASE5_CONCLUSION.md` measured the mechanism
directly: entry-day stock ATR correlates **0.914** with the VIX — so A's entries are
concentrated in frightened markets by construction. The ledgers corroborate it internally:
A's own realized entry volatility is **35.4%** against Sleeve H's **31.6%**, and H trades only
when SPY > SMA(100), i.e. in explicitly healthy markets. A buys volatility when it is locally
high and sells it one session after it starts to fall.

How many vol points of IV decline erase the entire edge:

| Sleeve A, σ = 35%, DTE ≥ 30 | vol points of IV crush to zero |
|---|--:|
| best cell (DTE 30, delta 0.25) | **1.08** |
| range across all cells | **0.53 – 3.45** |

**One vol point.** A 2–5 point IV drop on the day a beaten-down stock turns is entirely
ordinary. The adverse IV path is worth several times the whole edge, and the model does not
even include it — adding it would push Sleeve A decisively negative. This is the mechanism
that makes an options version of Sleeve A worse than the stock version, not merely more
expensive: *the instrument is structurally short the thing the strategy is long.*

### Pre-registered criteria, applied as written

| | Criterion 1: breakeven ≥ 15% round-trip at measured σ | Criterion 2: survives +3 vol pts | Criterion 3: fits the position cap |
|---|---|---|---|
| **Sleeve A** (σ = 35.4%) | **FAIL** — best 6.42% | FAIL — 4.72% | FAIL (§3) |
| **Sleeve H** (σ = 31.6%) | **PASS** — best 19.84% | **FAIL** — 8.03% | FAIL (§3) |

**Rejected.** Two kill criteria met. `screener.py` and `run_daily.py` untouched.

### Sleeve H came closer than expected, and its failure is instructive

Sleeve H passed criterion 1 and failed only on the variance risk premium. Its collapse across
σ is violent — best breakeven **26.9% at σ=30%, 7.0% at σ=35%, 2.2% at σ=40%**, with 9 of 20
cells negative *before any cost at all* by σ=40% and 16 of 20 by σ=50%. That is not a plateau.
It is the sawtooth signature Phase 2 and Phase 4 both died on, on an axis this project cannot
measure.

And the direction of the bet is unattractive. Sleeve H passes only if implied volatility on
52-week-high breakout names is at or below their realized volatility — i.e. only if the
variance risk premium on exactly those names, at exactly those moments, is **negative**. That
is the opposite of the documented sign for equity index options and is at best neutral for
single names. It is also, precisely, the quantity §2 says cannot be measured at the right time
of day without $399–5,000/month of data.

**The honest summary of Sleeve H: the one configuration that clears the bar is a bet on an
unmeasured parameter, which flips to a loss on a 3-point move in that parameter.** That is a
coin flip with a data bill attached, not an edge.

## 8. If it were built anyway, this is the list

Recorded so the cost is visible, not as a plan:

1. Historical options data purchase + ingestion (~$1,495 one-time for EOD, or $399/mo for the
   6-year intraday set that matches the execution model), plus a chain-storage layer — the
   current `data/` is a few hundred MB of daily bars; an options panel is orders of magnitude
   larger.
2. A new backtest engine. `backtest/engine.py` assumes one price series per name. Options need
   strike/expiry selection, roll logic, expiry handling, assignment, and per-contract costs.
3. A replacement position-sizing model that works in whole contracts, plus a re-derivation of
   the per-position caps and the drawdown breaker thresholds against an instrument that can go
   to zero.
4. Expiry-aware exit logic and a *second* daily checkpoint — the once-a-day unattended design
   is not safe near expiry (§4).
5. Alpaca Level 2/3 approval and a complete re-run of the gauntlet + refine chain on the new
   engine, with a fresh out-of-sample window reserved.

Every one of those is larger than any phase this project has run, and item 3 has no solution
at the current account size.

## 9. The strongest argument against my conclusion

Stated as well as I can make it, because it is not nothing.

**Defined-risk long puts as a drawdown tool, on index options.** Phases 2, 5 and 6 each ended
with the same orphan finding: this book can buy large drawdown reductions, but only by paying
6–14 points of CAGR for them. Phase 2 found hold-extension halved Sleeve H's max drawdown
(−44.6% → −24.1%); Phase 5 found an ATR cap took Sleeve A's from −36.5% to −22.5%; Phase 6
found strictness took the ensemble's from −15.5% to −7.3%. All were rejected as *edge* rules
while explicitly being left on the shelf as *risk* dials.

A long put on SPX or XSP is a fourth way to buy that same drawdown reduction, and it dodges
most of this document:

- It is **one position on one index**, so §3's granularity problem largely disappears — XSP is
  one-tenth the size of SPX, and index options are now live on Alpaca (§6).
- Index options are **European-style and cash-settled**, so there is no early assignment and
  no stock-delivery shortfall — most of §4's expiry risk goes away.
- Index options are the **most liquid options in existence**, so §5's cost objection is at its
  weakest.
- It is a hedge, not a leverage play, so it does not run into §1's "this is really a risk
  decision in disguise" — it *is* a risk decision, honestly framed.

**Why I still say no.** First, it is a different project: it is portfolio insurance on the
ensemble, not an options *strategy*, and it should be compared against the three cheaper
drawdown dials already measured and shelved — not adopted because it is new. Second, the
index variance risk premium is *documented as positive*, which means systematic put buying has
a known, measured, negative expected return; you are buying insurance and should expect to pay
for it. Third, and decisively, the book's drawdown is **−3.9%** (Phase 6). Phase 6 priced
halving the drawdown at ~6 points of CAGR and called it "far too expensive at current drawdown
levels." The same judgement applies here with more force, because the put also costs premium.

**It becomes worth re-opening if and only if the book's drawdown becomes the binding
constraint** — which would mean a drawdown deep enough to approach the −15% Sleeve A halt. At
that point this should be pre-registered as a *drawdown* hypothesis and benchmarked against
hold-extension, the ATR cap and strictness, which are already measured and cost nothing to
implement. Not before.

## 10. Recommendation

1. **Keep the options ban in `CLAUDE.md` and PLAYBOOK §5 exactly as written.** No change.
2. **Close single-name long options as a line of enquiry.** The risk model cannot express them
   at this account size (§3), the instrument is structurally adverse to Sleeve A's mechanism
   (§7), and neither sleeve clears its pre-registered bar.
3. **Do not treat this as the answer to Phase 6.** The setup-supply constraint needs more
   *underlyings*, and Phase 6 already named the hypothesis — a larger universe with liquidity
   screening built in, not bolted on. That is where the effort should go.
4. **Index puts as a drawdown tool stay shelved with the other three drawdown dials** (§9),
   re-openable only on a drawdown-framed pre-registration if drawdown ever becomes binding.
5. If David wants this re-examined anyway, the **cheapest decisive test** is not a backtest. It
   is to record Alpaca's live option chain (free tier, 15-minute delayed) for the names the
   screener fires on, every morning, for three months, and measure the actual spread and
   implied vol **at the open** on real signals. That costs nothing, answers the one question
   the $1,495 dataset cannot (§2), and would either kill the idea for good or earn it a real
   pre-registration.

## 11. What would change my mind

- Measured at-the-open implied vol on Sleeve A signal names coming in *at or below* those
  names' realized vol — i.e. a negative single-name variance risk premium at exactly the
  moments A trades. §7 says this is the load-bearing assumption and it is currently unmeasured.
- An account large enough that one contract at a normal delta fits inside a 4–6% cap. At 0.55
  delta and the median traded name ($216.60) that needs **$198,550** of equity for Sleeve A's
  6% cap and **$297,825** for Sleeve H's 4%; the book has $97k.
  This is the one blocker that money alone fixes.
- The book's drawdown approaching the −15% halt, which would reopen §9 on its merits.

None of these is true today.

---

### Provenance and limitations of this document

- `PHASE4_CONCLUSION.md`, `PHASE5_CONCLUSION.md`, `PHASE6_CONCLUSION.md`,
  `BREADTH_HYPOTHESIS.md` and the phase 4–6 scripts **are not on `main`**. They live on
  `claude/portfolio-trading-history-pdlkej` and were read from there. Everything this document
  cites from them is quoted from that branch; if it is ever rebased or dropped, the citations
  move with it.
- External figures (Alpaca policies, vendor pricing, SEC and academic spread data) were
  gathered by subagents and then re-verified by me via independent search. **This environment's
  egress proxy blocks `docs.alpaca.markets`, `alpaca.markets`, `sec.gov`, `orats.com`,
  `polygon.io` and `historicaloptiondata.com` directly**, so no primary source below could be
  loaded and quoted verbatim. Vendor prices (DeltaNeutral $1,495 / ORATS $599 + $99/mo /
  ORATS intraday $399/mo) and the SEC top-10 effective-spread figure (0.9%) were corroborated
  across independent searches; the rest should be read from source before any purchase or
  policy decision. **No conclusion in §1, §3, §4 or §7 depends on an unverified external
  figure** — those rest on this repo's own ledgers and the model in `options_overlay.py`.
- The overlay's limitations are listed in the pre-registration and are unchanged: two-point
  repricing, flat constant σ, pooled volatility, inherited survivorship bias, no dividends or
  early assignment. All were chosen to favour the options case.
- Yahoo/yfinance was unreachable from this environment, so no fresh market data was
  downloaded. Every repo number here is computed from files committed in `results/` and
  `papertrade/`.

### Reproduce

```
python3 -m backtest.options_overlay      # writes results/OPTIONS_OVERLAY.md + options_overlay.json
```

### Already tested and rejected — do not revisit without a new pre-registered hypothesis

upside management (`PHASE2_CONCLUSION.md`), slot concentration (`PHASE3_CONCLUSION.md`),
entry-breadth gating and clustering throttles (`PHASE4_CONCLUSION.md`), Sleeve A volatility
filtering (`PHASE5_CONCLUSION.md`), stacked entry confirmations (`PHASE6_CONCLUSION.md`),
**single-name long options on either sleeve (this document)**.
