# Strategy Catalog — Ranked Master List

Synthesized 2026-06-10 from 24 strategy cards (`candidates/`) + cross-agent corroboration (`corroboration-notes.md`).
Mandate: **long-only, US stocks, 2–15 trading day holds, codable on daily OHLCV.**

Scoring criteria (from the project plan): rule precision · evidence quality · cross-source corroboration · mandate fit · codability.

## Merges & duplicates

| Kept | Merged in | Reason |
|---|---|---|
| `c-quantitativo-band-ibs` | `a-volband-ibs-snapback` | Same Quantitativo strategy found independently by two beats — treated as strong corroboration |
| `c-turnaround-tuesday` | `a-turnaround-tuesday` | Same calendar effect; C card has fuller rule/stat detail |
| `d-pead-ear-long-leg` | `a-episodic-pivot-gap` (partial) | EP is the practitioner implementation of the PEAD long leg; kept separate below because entry mechanics differ materially |

## Families

- **MR — Oversold pullback / mean reversion in uptrend** (Connors school): rsi2-sma200, cumulative-rsi2, 3-lower-lows, connorsrsi-limit, sma-pullback-rsi5, percent-b, ibs, band+ibs, quiet-gap-down, weekly-reversal
- **MOM — Momentum / breakout**: stockbee-burst, 52wk-high, qullamaggie-flag, episodic-pivot, nr7, adx25
- **CAL — Calendar effects**: turnaround-tuesday, turn-of-month
- **Overlays** (filters, not standalone strategies): IBS bucket filter, VIX-stretch gate, index regime filter

Cross-agent consensus worth remembering: long-only beats short everywhere it was tested; stop losses *degrade* index mean reversion in three independent tests; plain breakouts decayed post-2021 per the breakout community itself; most published mean-reversion edges have visibly shrunk since ~2010 — which is exactly what our out-of-sample gauntlet is for.

---

## Tier 1 — Backtest finalists (8 modules)

### MR-1 · RSI(2)-family pullback on a stock basket
**Cards:** `b-rsi2-sma200-pullback`, `b-cumulative-rsi2` · **Evidence 4–5** · most-corroborated setup in the entire sweep (StockCharts, QS, Alvarez, Quantitativo, independent 34-yr Reddit backtest with code)
**Baseline spec:** stock close > SMA(200); RSI(2) < 10 (variant: cumulative RSI(2)+RSI(2)[1] < 35 / < 10); buy next open; exit close > SMA(5) (variants: RSI(2) > 65, cumRSI > 65); no stop (corroborated: stops hurt); max 10 positions, equal weight.
**Key variants:** SMA(100) vs SMA(200) trend filter; Alvarez **ex-index universe** insight (+121% CAR switching to formerly-in-index stocks); limit entry 5% below close; index regime gate.
**Known risks:** edge decay post-2010/2013 across multiple sources; high win rate masks larger avg losers.

### MR-2 · 3 lower lows + ATR-stretch limit buy (Alvarez)
**Card:** `c-alvarez-3-lower-lows-atr-dip` · **Evidence 5** — the only candidate tested directly on a US stock universe with full spec + Monte Carlo (Russell 1000 2004–2014: CAGR 22.4%, MaxDD 21%, 7,183 trades)
**Baseline spec:** Russell-1000-class universe, $10M+ ADV, close > $1; close > SMA(100); close < SMA(5); 3 consecutive lower lows; next-day limit buy at close − 0.5×ATR(10), day-only; exit next open after first up close; no stop; 10 positions × 10%.
**Key variants:** stretch 0.25–1.0×ATR; RSI(2)<5 instead of lower lows; skip recent >10% gappers (Alvarez's own improvement); SMA(200) filter.
**Known risks:** test ends mid-2014 — post-2014 decay is THE question; limit-fill assumptions dominate; buys falling knives by construction.

### MR-3 · Band + IBS snapback, ported to stocks (Quantitativo)
**Cards:** `c-quantitativo-band-ibs` + `a-volband-ibs-snapback` (dual discovery) · **Evidence 5** (QQQ 1993–2024: Sharpe 2.11, 13% ann., MaxDD −20%, + published robustness study + independent replication notebook)
**Baseline spec:** lower band = 10-day rolling high − 2.5 × 25-day mean(High−Low); entry when close < band AND IBS < 0.3; exit close > prior high; SMA(300) disaster stop.
**Plan:** replicate published QQQ result first (engine validation), then port to liquid stock basket (the author's own suggested extension — NDX-100 replication notebook exists).
**Known risks:** 4 tunable parameters; assumes the post-2000 "market always bounces" regime; edge concentrates in high-volatility periods (use NATR bucket analysis).

### MR-4 · Double 7s, stock-basket variant
**Card:** `b-double-seven` · **Evidence 4** (multiple independent backtests agree)
**Baseline spec:** index close > SMA(200) AND stock close > SMA(200); buy when close = lowest close of 7 days; exit when close = highest close of 7 days; no stop; 10 positions × 10%.
**Key variants:** exit close > SMA(5) (more robust per 34-yr Reddit test); lookback 5/7/10 (drawdown explodes 7→8 — fragility check is mandatory).
**Known risks:** "almost all gains pre-2010" (QS); cheap to test since it shares MR infrastructure — kept mainly as a robustness comparison for MR-1.

### MOM-1 · Stockbee 4% momentum burst
**Card:** `a-stockbee-momentum-burst` · **Evidence 3** — the only fully daily-codable momentum representative with stable 15-year published scan rules
**Baseline spec:** close ≥ 1.04 × prior close; volume > prior day AND > 100k; prior day narrow-range or down; 3–20 day consolidation precedes; not extended (< 2 prior 4% days in last 5); buy at close (sensitivity: next open); exit day 3–5 time stop, stop at breakout-day low.
**Known risks:** originator curates heavily — naive scan will underperform claims; small-cap skew = slippage; expect feast-or-famine regimes.

### MOM-2 · 52-week-high breakout (swing translation)
**Card:** `d-52wk-high-breakout` · **Evidence 4** for the monthly anomaly (George & Hwang JF 2004, heavily replicated); **3** for our 10–15 day translation
**Baseline spec:** liquid universe; close makes new 252-day high (or ≥ 0.98 × 252-day high after intraday touch) on volume > 50-day average; index > SMA(200) gate; hold 10–15 days or exit on close < 95% of breakout level.
**Known risks:** post-publication decay (~58% average per McLean-Pontiff); momentum crashes in rebounds; our short-hold slice is untested in the source literature.

### CAL-1 · Turnaround Tuesday (multi-day variant)
**Cards:** `c-turnaround-tuesday` + `a-turnaround-tuesday` · **Evidence 4** (three independent shops: QS, Quantitativo, Quantifiable Edges)
**Baseline spec:** Monday close < Friday close AND IBS < 0.5 → buy Monday close (variant: two down closes into Tue/Wed → buy open); exit close > prior high or 4-day time stop.
**Plan:** test standalone on stock basket AND as a timing overlay on MR-1/MR-2 entries.
**Known risks:** thin per-trade edge (0.3–0.46% on SPY) → cost-sensitive; day-of-week effects decay; QE finds effect strongest *below* the 200MA — test both regimes.

### CAL-2 · Turn-of-month
**Card:** `c-turn-of-month` · **Evidence 4** (61-year backtest; academic lineage to Lakonishok & Smidt 1988)
**Baseline spec:** buy close of 5th-last trading day of month; sell close of 3rd trading day of new month (~7-day hold); large-cap basket port (S&P-100-class names).
**Plan:** test as standalone sleeve AND as an entry-window overlay (upsize MR entries during the window).
**Known risks:** edge is risk-adjusted (matches B&H at 33% exposure), not raw alpha; most-published anomaly in finance → decay watch.

### Overlay dimensions (toggled across all finalists, not standalone)
- **IBS filter** (`b-ibs-mean-reversion`, evidence 4): require IBS < 0.25 at entry — Alvarez: +58% avg P/L on the surviving third of trades. Best documented use of IBS.
- **VIX-stretch gate** (`c-vix-stretch-mr`, evidence 3): VIX > 5% above its 10-day SMA for 3 days — fear-overdone gate for MR entries; VIX series from FRED/CBOE.
- **Index regime filter:** SPX/SPY > SMA(200) — default ON for MOM, *tested both ways* for MR (Alvarez found it kills the ConnorsRSI edge 2006–2015; QE finds TT strongest below the 200MA).

---

## Tier 2 — Test only if Tier 1 disappoints, or as refinements

| Strategy | Card | Why not Tier 1 |
|---|---|---|
| ConnorsRSI pullback grid | `c-connorsrsi-pullback-limit` | Same family as MR-1/MR-2; vendor stats promotional; limit-fill-dominated; Alvarez corroborates *an* edge — fold its ADX(10)>30 + stretch-limit ideas into MR variants |
| %b 3-day persistence | `c-connors-percent-b` | Cousin of MR-1 with volatility-normalized oversold; revisit if MR-1 wins and we want persistence variants |
| SMA(20) pullback + RSI(5) | `c-sma-pullback-rsi5` | Same family, snippet-only stats; the 20-day-MA pullback condition is an MR-1 variant toggle |
| NR7 compression | `c-nr7-compression-entry` | Publisher itself calls raw edge marginal (0.27%/trade); keep as building block: NR7-at-highs + trend filter is the mechanized-VCP primitive for MOM refinement |
| Quiet gap-down fill | `c-quiet-gap-down-fill` | Setup must be re-derived (target rule + universe unrecoverable behind bot wall); promising but underspecified |
| Weekly reversal (long losers) | `d-weekly-reversal-liquid-losers` | Evidence 4 but ~100% weekly turnover → slippage assumptions dominate; long-leg-only net returns unpublished; crisis-concentrated |

## Tier 3 — Parked (not codable / data-blocked / weak)

| Strategy | Card | Reason |
|---|---|---|
| Qullamaggie flag breakout | `a-qullamaggie-flag-breakout` | Core pattern (tightening flag) is discretionary; canonical entry needs intraday data; community itself says decayed post-2021. Revisit via daily approximation only if MOM-1/2 show promise |
| Episodic pivot gap | `a-episodic-pivot-gap` | Needs intraday entry + float/fundamentals data; low-float names un-backtestable with free daily data. The PEAD mechanism is carded separately |
| PEAD via EAR | `d-pead-ear-long-leg` | Needs reliable historical earnings-date data (hard for free); Martineau 2022: effect vanished in non-microcaps ~2001–2006 |
| SPY higher-low pullback | `a-spy-higher-low-pullback` | Evidence 2; fuzzy pivot definition; OP sells subscriptions. The buy-stop-above-pullback-bar *entry mechanic* is worth an MR variant toggle |
| ADX-25 cross | `a-adx25-trend-burst` | Evidence 2; in-thread overfit consensus; ADX-only entry is directionless in principle. Only the Raschke Holy-Grail variant deserves a Tier-2 look |

## Rejected (do not backtest)

See `corroboration-notes.md` § Popular-but-probably-bogus: RSI(14)+Bollinger touch, Fibonacci retracement fades, trendline-breakout win-rate porn, Bollinger squeeze breakouts, unverified VCP success-rate claims.

---

## What the backtest must answer, per finalist

1. Does the published edge survive on **our** data with **our** execution assumptions (next-open entries, slippage)?
2. Does it survive **post-2014/post-publication** out-of-sample?
3. Does it survive on a **survivorship-aware liquid universe** (not just SPY/QQQ)?
4. Which overlays (IBS / VIX / regime / calendar) help vs hurt — with parameter-plateau evidence, not single-point optima?
