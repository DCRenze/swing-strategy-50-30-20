# Live Review — A/H ensemble, 2026-07-01 → 2026-08-07

Paper account: **$100,000 → $96,586** (−3.4%; −3.8% from the $100,432.77 HWM).
Realized ledger: **41 closed trades, −$1,635**.

**Headline: the edge is not broken — the executor is.** The realized shortfall is well
inside normal variance, but the live system has not been running the validated rules.
Sleeve H was silently dormant on 26 of 28 trading days, and roughly half of Sleeve A's
exits fired on a signal that is structurally impossible in the backtest. The P&L to date
therefore carries almost no information about whether the strategy works.

---

## 1. Scoreboard vs. validated benchmarks

| | Live | Backtest OOS (2023+) | Verdict |
|---|---|---|---|
| **Sleeve A** n | 31 | 2,292 | |
| win rate | 48.4% | 59.7% | z = −1.29, **not significant** |
| avg win / avg loss | +2.41% / −3.04% | +2.14% / −2.67% | shape matches |
| profit factor | 0.80 | 1.19 | |
| **Sleeve H** n | 10 | 644 | |
| win rate | 20.0% | 48.4% | z = −1.80, **not significant** |
| avg win / avg loss | +10.30% / −5.98% | +9.75% / −6.14% | shape matches almost exactly |
| profit factor | 0.44 | 1.49 | |

Expected P&L on this trade count was **+$1,001**; actual **−$1,635**.
That gap is **−0.81σ (A)** and **−1.00σ (H)** — an ordinary bad month.

The per-trade *magnitudes* are the tell: average win and average loss on both sleeves
land almost exactly on the backtest. The machinery that sizes and prices trades is fine.
Only the hit rate is low, on a sample far too small to conclude anything.

**Two hypotheses were tested and rejected:**

- *Position sizing drift.* Audited all 41 trades. 38 sized to spec (0.97–1.02× target).
  The 3 oversized ones (NUE, GM, RCL at ~11% vs 6%) were legacy positions adopted during
  the June migration — and all three were **winners**. Re-sizing every trade to spec makes
  P&L *worse* (−$1,842). Not the cause.
- *Strategy decay.* Neither sleeve's hit-rate deviation is significant, and PLAYBOOK §8's
  decay bar (PF < 1.0 for 6+ rolling months) is nowhere near met on 5 weeks of data.

---

## 2. Root cause: the screener acts on the *in-progress* session

The runner fires at 13:32 UTC — **~2 minutes after the 09:30 ET open**. `refresh_data()`
pulls yfinance, and `load_recent_panel()` (`playbook/screener.py:109`) keeps any trailing
session where ≥50% of tickers have a close. A row for the current, half-formed session
clears that bar easily. PLAYBOOK §3.1 requires the opposite:

> "The screener's as-of date MUST equal the last completed session."

That invariant is **never asserted and never journaled** — `run_start` is written before
the screener runs, so `as_of` appears nowhere in 36 days of logs. The failure is silent.

### 2a. Sleeve H was dormant on 26 of 28 days — proven

H's entry filter requires `volume > sma(volume, 50)` (`screener.py:233`). Two minutes of
volume can never exceed a 50-day daily average, so on any day the in-progress bar is
present, **every H candidate is filtered out and the sleeve produces zero orders** — and
because the order loop simply doesn't execute, nothing is journaled at all.

| | Live | Backtest OOS |
|---|---|---|
| days with H entries | **2 of 28 (7%)** | **43% of trading days** |
| max entries in one day | **10** (2026-08-06) | 9 — once in 3.5 years |
| trades | 11 | ~20 expected over the same window |

On 2026-08-06 the panel evidently ended on a completed session; H immediately produced a
**full 10-name slate in a single day**, something that never happens in 3.5 backtest
years. That bimodal on/off pattern is the signature of the bug, not of the strategy.

The SPY > SMA(100) gate was **not** the cause — no `skip` with `reason_inactive` was ever
logged, so the gate was open the whole time.

**Consequence:** the momentum sleeve — the one with the best out-of-sample profit factor
(1.37–1.49) and the one whose 0.26 correlation with A is the entire reason drawdown is
tamed — was effectively switched off. The book averaged **34% invested** (median 26%)
against a design target near 100%. Point estimate of forgone H expectancy: **~$550**,
with wide error bars. More importantly, the diversification that makes the ensemble
clear the gauntlet was absent.

### 2b. Sleeve A exits fired a day early — proven

Backtest: an up close at day *t* → sell at the open of *t+1*. So the shortest possible
round trip spans **2 trading days**; 1-day gaps are 7.2% of backtest trades.

Live: **16 of 31 (51.6%)** A trades closed with a 1-day gap. For the exit condition at
`run_daily.py:261` (`closes = s[s.index > entry]`) to be non-empty on the day after entry,
the panel *must* contain a row for the in-progress session. Arithmetic, not inference.

| trading-day gap | live | backtest OOS | z |
|---|---|---|---|
| 1 | **51.6%** | 7.2% | **+9.60** |
| 2 | 9.7% | 48.5% | **−4.33** |
| 3 | 29.0% | 22.6% | +0.86 |

The whole distribution is shifted one session earlier. The live rule is effectively
*"sell at the open if the stock ticks up"*, not *"sell the open after a confirmed up
close"* — it gives up the bounce day the strategy is designed to capture.

Worked example (2026-07-30): AMAT, CAT, KLAC, NXPI, ON all filled on 07-29 and were sold
at 13:33 UTC on 07-30. No completed 07-30 close existed at that moment.

### 2c. Sleeve H's 5% stop is an intraday stop, in mixed units

`run_daily.py:320` compares `closes_since.min()` — which includes the partial bar — against
`avg_entry_price`. Two defects:

1. **Intraday trigger.** The validated stop needs a *completed* close ≤ entry × 0.95. Live
   fires on an intraday touch. Evidence: **TER was stopped out on its entry day**
   (`days_held=0`) — the engine explicitly forbids same-day round trips
   (`engine.py:236`). CAT exited at −4.44% and OKTA at −4.97%, both *above* the stop level.
   Live H trades ending ≤ −5%: **50%** vs **33.2%** in the backtest.
2. **Unit mismatch.** `closes_since` is *adjusted* close; `avg_entry_price` is Alpaca's
   *raw* fill. The screener carefully converts to raw space for A's limit price
   (`screener.py:195`) but nothing does so here. Any dividend going ex during the hold
   biases the series downward and trips the stop early. `engine.py:151` compares adjusted
   to adjusted — consistent.

---

## 3. Secondary defects

**Stranded-position branch.** `run_daily.py:263` exits only when the single up-close *is*
the latest session. If exactly one up-close occurred but the latest session was down, no
branch fires — not the exit, not the time stop, not the `>1` overdue path — and the
position is held until a second up-close or day 15. The `elif len(up_closes) > 1` overdue
warning fired 5 times (BROS, WAT, ADI, AWK, BBY), so the miss path is live, not theoretical.

**No trading-calendar guard.** The runner executed on **2026-07-03, a market holiday
listed in its own `US_MARKET_HOLIDAYS`**, submitting 9 A limit buys and logging 3 H stops
into a closed market.

**Sector concentration from the tie-break.** `screener.py:212` ranks A candidates by
20-day dollar volume; the backtest picked randomly among signals (`engine.py:172`) and
`screener.py:221` documents the swap. On a sector-wide selloff the highest-dollar-volume
names *are* that sector, so the live book takes concentrated bets the backtest never did:

- 2026-07-24 — GFS, ADI, ENTG (all semis): **−$1,014**
- 2026-07-29 — AMAT, KLAC, NXPI, ON, CAT (4 semis): **+$1,053**

Backtest same-day baskets carry ρ ≈ 0.24 (≈2.55 effective bets from 5 trades). The live
tie-break pushes ρ higher, widening the P&L swing in both directions. Oversubscription is
routine — **75 A / 29 H** candidates were skipped as "sleeve full".

**Symbol mapping.** `BRK-B` was rejected by Alpaca (`asset "BRK-B" not found`) — Alpaca
uses `BRK.B`. One missed entry.

**Duplicate-run noise.** 63 of 68 order errors were `client_order_id must be unique` from
re-runs on 06-22 / 07-01 / 07-02. The idempotency guard worked as intended; benign, but it
masks real errors in the logs.

---

## 4. Why individual trades lost — the honest answer

Grouped by cause:

| Cause | Trades | P&L |
|---|---|---|
| The 07-01 legacy H cohort (adopted at migration, 9 names at once) | RRX, CAT, MKSI, GEV, HAYW, CRL, JBHT, JAZZ, ACHC | −$849 |
| Semis cluster, 07-24 | GFS, ADI, ENTG | −$1,014 |
| Ordinary A losers within backtest distribution | 13 trades | −$1,100 |
| Winners | 17 trades | +$3,114 |

The five worst trades (ENTG −$527, FTAI −$526, MKSI −$433, GFS −$424, GEV −$301) are
**not** anomalies: −8.96%, −8.76%, −11.35%, −7.22%, −7.75% all sit inside the backtest's
p05 tail (A: −5.1%; H: −9.0%). No single trade failed in a way the strategy didn't predict.

What's abnormal is the *composition*: too many correlated bets landing on the same day,
and a momentum sleeve that wasn't there to offset them.

---

## 5. Improvement plan

Ordered by expected impact. **P0 items restore the validated spec — they are bug fixes,
not parameter changes, so they do not require re-running the gauntlet.** Nothing below
alters a validated parameter.

### P0 — restore correct execution (do before the next run)

1. **Assert the as-of invariant.** In `screener.py`, compute the expected last completed
   NYSE session and **hard-fail** if `as_of` doesn't match. Raise the coverage threshold
   and explicitly drop any row dated today. This single fix resolves §2a, §2b and half of §2c.
2. **Journal `as_of` on every run** — in `run_start` and in each order record. The invariant
   the playbook calls critical is currently unobservable.
3. **Alert on a silent sleeve.** Log an explicit `skip` with the candidate count when a
   sleeve produces zero orders, so "H found nothing" is distinguishable from "H is broken".
4. **Fix the H stop** — compare completed closes only, in a consistent price space (convert
   the raw fill to adjusted via the same ratio used at `screener.py:195`, or compare raw to raw).
5. **Fix the stranded-position branch** — exit whenever ≥1 up-close has occurred since
   entry, matching `engine.py`'s "any up close → sell next open".
6. **Add a trading-calendar guard** — exit early if today isn't an NYSE session.
7. **Map Alpaca symbols** (`BRK-B` → `BRK.B`, and the rest of the dotted class tickers).

### P1 — reduce the concentration the backtest never had

8. **Cap same-sector exposure** in Sleeve A (e.g. max 3 of 10 slots per GICS sector), or
   revert the tie-break to random selection among candidates to match `engine.py`.
   Recommendation: a sector cap — it keeps live fill quality *and* restores diversification.
   This changes selection among equally-valid signals, not an entry/exit rule, but it
   should still be **backtested before deployment** since it alters realized trade mix.
9. **Stagger sleeve deployment from flat.** Cap new entries per sleeve per day (e.g. 3–4)
   so a cold start can't put the entire 40% momentum allocation into one day's cohort, as
   happened on 07-01 and again on 08-06. Backtest first.

### P2 — measurement

10. **Re-baseline the evaluation window.** Treat 07-01 → 08-07 as *invalid for judging the
    strategy*. Start the PLAYBOOK §8 rolling-PF clock from the first clean run after P0 ships.
11. **Quarterly slippage check** (PLAYBOOK §8) has never run. Sleeve A dies at ~20 bps/side;
    with limits filling at or inside the limit price, realized slippage should be ≈0 — worth
    confirming from the fills now that a month of data exists.

### What *not* to do

Do not touch weights, thresholds, stops, or lookbacks. Nothing in this data challenges a
single validated parameter, and changing one now would discard the evidence chain while the
executor is still the confounder.

---

## 6. Bottom line

A −3.4% drawdown over five weeks is entirely normal for a book with a −24.9% historical
max drawdown, and both sleeves' win/loss magnitudes match the backtest closely. But the
system spent those five weeks running a materially different strategy from the validated
one: momentum offline ~93% of days, mean-reversion exits firing a session early, and a
stop that triggers intraday. **Fix the executor, then re-measure. The current P&L is not
evidence about the edge in either direction.**
