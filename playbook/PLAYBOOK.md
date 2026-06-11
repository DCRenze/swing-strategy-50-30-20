# ENSEMBLE PLAYBOOK — Long-Only US Stock Swing Strategy

**Audience: a Claude agent (or human) executing trades in David's Alpaca account.**
This document is the complete operating specification. Follow it exactly. Do not
modify any parameter without re-running the validation gauntlet (`backtest/gauntlet.py`)
— every number here is backed by the evidence in `results/` and changing it
silently invalidates that evidence.

---

## 1. What you are trading and why we trust it

A 50/30/20 capital-split ensemble of three independently validated long-only sleeves.
Validated 2005–2026 on ~1,000 liquid US stocks, 5 bps/side slippage, with the last
3.5 years held out of sample (details: `results/REFINEMENT.md`, `results/refine_results.json`,
chart: `results/ensemble_equity.png`):

| | Full window (2005–2026) | Out-of-sample (2023+) |
|---|---|---|
| CAGR | 12.3% | 9.7% |
| Sharpe | 1.16 (SPY: 0.64) | 1.08 (SPY: 1.43*) |
| Max drawdown | −16.5% (SPY: −55%) | −13.2% |
| Monte Carlo p95 DD | −11.9% | — |

*The 2023–26 window was a near-record bull run; SPY's 1.43 Sharpe there is an
outlier no low-exposure strategy matched. The strategy's purpose is surviving
ALL regimes, which is what the drawdown profile shows.

**Sleeves and the regimes they cover:**
- **A. Three-lower-lows dip buy (50%)** — mean reversion in uptrending stocks. Earns in bull/normal markets. Full-window Sharpe 1.10, CAGR 16.7%, PF 1.30, 62% win rate, ~11,900 trades.
- **B. Turn-of-month (30%)** — institutional-flow calendar effect, regime-neutral. PF 1.47 full, 1.33 OOS; invested only ~1/3 of the time.
- **C. Turnaround Tuesday, bear-regime only (20%)** — buys Monday panic *only when SPY < 200-day SMA*. PF 1.42 full, 1.88 OOS, OOS MaxDD −4%. Idle in bull markets — that is by design; it is the bear-market diversifier.

## 2. Hard parameters (validated config — do not change)

| Parameter | Value |
|---|---|
| Universe | S&P 500 ∪ Russell 1000 (`data/universe.csv`; rebuild monthly via `backtest/universe.py`) |
| Sleeve A | close > SMA200, close < SMA5, 3 consecutive lower lows, price > $1, 20d avg dollar vol > $10M → next-day **limit buy at close − 0.75×ATR(10)**, day-only. Exit: sell next OPEN after first close > prior close; hard 15-day time stop. No stop loss (validated: stops hurt this sleeve). Max 10 positions × 5% of equity. |
| Sleeve B | Buy MOC on the **5th-last trading day** of the month: top-10 by 20d dollar volume (from top 100). Exit MOC on **trading day 1** of the new month. Max 10 × 3% of equity. |
| Sleeve C | Monday + SPY < SMA200 + stock down day + IBS < 0.5 + price > $5 + dollar vol > $20M → buy MOC, lowest-IBS 10 names. Exit: close > prior day's high (sell at that close) or 4-day time stop. Max 10 × 2% of equity. |
| Slippage budget | Strategy was validated at 5 bps/side. Sleeve A **dies at ~20 bps/side** (see §6). |

## 3. Daily operating procedure — two checkpoints

### 3.1 Evening run (after ~4:30 pm ET, every trading day) — the main run

```
cd "E:\Swing Trade Strategy Research"
.\.venv\Scripts\python.exe -m playbook.screener --refresh --equity <CURRENT_ACCOUNT_EQUITY>
```

The screener's as-of date MUST equal today (the just-completed session). If it
lags, data is stale: do not place Sleeve A orders (their signals are valid for
the immediately following session only) — investigate per §5.

1. **Sleeve A exits:** for each open A position, using today's completed bar:
   - if today was the position's first close > prior close → submit a market-on-open (Alpaca `opg`) SELL for tomorrow's open, tonight;
   - else if tomorrow will be holding day 15 → plan a MOC sell for tomorrow (submit before 3:45 pm ET tomorrow). Overdue stops (missed for any reason): sell at the first available close.
2. **Sleeve A entries:** submit the screener's printed day-only LIMIT buys for tomorrow. **Never chase, never convert to market** — unfilled means no trade. Skip a ticker if it is currently held in Sleeve A *unless* its exit order (step 1) executes before tomorrow's session — exit-then-re-enter is legitimate and matches the backtest.
3. **Sleeve B calendar check:** the screener prints `trading_days_left_in_month` / `trading_day_of_month`. If TOMORROW is the entry day (5th-last of month) or exit day (1st of new month), put the corresponding MOC order list on tomorrow's 3:40 pm checklist (B's rankings barely move in a day, so tonight's list is valid).

### 3.2 Near-close run (3:30–3:45 pm ET, only on flagged days)

Needed on: Sleeve B entry/exit days (known a day ahead from 3.1.3), and Mondays
when SPY closed below its 200-day SMA on Friday (Sleeve C live).

- **B:** submit the MOC (`cls`) buys/sells from the evening list before 3:45 pm ET.
- **C:** requires *today's intraday* prices (down-day + IBS < 0.5 near the close). With Alpaca real-time data, the papertrade runner computes this automatically. **If only end-of-day data is available, skip C entries and journal the skip** — do not approximate with yesterday's bar.
- **C exits:** if a C position is trading above yesterday's high near the close, or hits its 4-day time stop today → MOC sell.

### 3.3 Conventions (resolve all boundary cases)

- **Day counting:** entry day = day 0. "15-day time stop" = sell at the close of day 15 (A); "4-day" = close of day 4 (C).
- **Staleness:** as-of must equal the last completed NYSE session. Sessions dropped by the screener that match the `US_MARKET_HOLIDAYS` list (or today's in-progress session during market hours) are benign and are not staleness.
- **One company = one slot** per sleeve at any instant; share classes count as one company (screener dedupes).
- **Fat-finger guard:** the screener now prints `last_close` and `limit_vs_close_pct` per A order and automatically EXCLUDES any limit ≥ 10% below the last close (printed under `warnings`). If warnings appear repeatedly, flag to David.
- **Journal** every order, fill, skip, and warning with a reason (the papertrade runner does this automatically).

## 4. When signals exceed slots

- A: take the highest 20-day dollar-volume names (fill quality; backtest used random selection — this substitution favors liquidity and was not the source of the edge).
- B: highest dollar volume.
- C: lowest IBS (most panicked close).

## 5. Risk guardrails and stand-down rules

- Per-position caps: 5% (A) / 3% (B) / 2% (C) of account equity. Recompute from current equity daily.
- **Stand down (no new entries; manage exits only) when:**
  - Account drawdown from its high-water mark exceeds **15%** → halt sleeve A; at **20%** halt everything and alert David. (Historical max was −16.5%; MC p95 −11.9%. 20% means something is off — regime, data, or decay.)
  - Data integrity fails: screener as-of date stale (per §3.3 definition), > 5% of universe missing bars, or repeated fat-finger warnings (§3.3).
  - A position's ticker has a pending acquisition/delisting headline — exit at next open, flag it.
- Never short. Never use margin beyond cash. Never trade options. Never override an exit rule because of news or conviction.

## 6. Execution discipline (this is where the edge lives or dies)

Sleeve A slippage sensitivity (full window): 0 bps → 23.5% CAGR · 5 bps → 16.7% · 10 bps → 10.3% · **20 bps → negative**.
Sleeve A's limit orders *provide* liquidity (you are the resting bid in a falling
stock), so realized slippage should be ~0 — but only if orders are genuine resting
limits. Any "chase the fill" behavior converts the sleeve to a knife-catching
market-order strategy that loses money. B and C use MOC orders in the most liquid
names, where closing-auction impact at this size is negligible.

## 7. Expected behavior and failure modes (read before judging a losing week)

- **Sleeve A** loses fastest in waterfall crashes (knife-catching by construction; 2008-type regimes drove its −29% standalone DD) and earns most in choppy uptrends. ~60% win rate; average win small; expect streaks of 5+ losers.
- **Sleeve B** loses when month-end coincides with macro selloffs (its OOS DD −27.6% came from April 2025); it is a thin per-trade edge (~0.5%) harvested ~12× a year.
- **Sleeve C** does nothing for months (even years) in bull markets. Do not "fix" it. Its job starts when SPY < 200dma.
- The ensemble's worst historical year is roughly flat-to-−10%; 2 of 21 calendar years were negative in backtest. A losing quarter is within distribution; a −20% drawdown is not (§5).

## 8. Monitoring and decay protocol

- **Monthly:** rebuild the universe (`python -m backtest.universe`); compare rolling 12-month realized PF per sleeve vs backtest expectation (A: 1.30, B: 1.47, C: 1.42). One sleeve below 1.0 for 6+ rolling months → flag to David.
- **Quarterly:** compare paper/live fills vs signal prices (realized slippage). Sleeve A realized slippage > 10 bps → execution problem, halt and investigate.
- **Yearly:** extend data (`python -m backtest.data`) and re-run `python -m backtest.gauntlet` + `python -m backtest.refine`; confirm the ensemble's edge persists out-of-sample-extended. Update `US_MARKET_HOLIDAYS` in `playbook/screener.py` for the new year.

## 9. Known limitations (inherited from the research, documented honestly)

- **Survivorship bias:** the backtest universe is today's index members projected backward. Mean-reversion dip-buying tends to *benefit* from this bias (the dip-buyers' graveyard is delisted names). The OOS window and paper trading are the corrective lenses; treat backtest CAGR as optimistic.
- Backtest entry prices assume fills at the limit when the day's low touches it (standard but optimistic by half a tick); MOC entries assume the close print.
- yfinance is the data dependency; if it breaks, the screener fails loudly (see stand-down rules). Alpaca's data API is the planned replacement in the papertrade runner.
- The 2026 holiday calendar is hardcoded; extend annually (§8).

## 10. Provenance chain (for auditing any rule)

Research cards → `research/candidates/` and `research/CATALOG.md` (24 candidates, ranked)
→ gauntlet evidence → `results/gauntlet_*.json`, `results/GAUNTLET_SUMMARY.md` (what failed and why)
→ refinement + ensemble selection → `results/REFINEMENT.md`, `results/refine_results.json`
→ this playbook. Engine assumptions: `backtest/engine.py` docstring; engine tests: `backtest/test_engine.py`.
