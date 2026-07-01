# ENSEMBLE PLAYBOOK — Long-Only US Stock Swing Strategy (A/H 60/40)

**Audience: a Claude agent (or human) executing trades in David's Alpaca account.**
This document is the complete operating specification. Follow it exactly. Do not
modify any parameter without re-running the validation gauntlet (`backtest/gauntlet.py`)
and refinement (`backtest/refine.py`) — every number here is backed by the evidence
in `results/` and changing it silently invalidates that evidence.

> **This is the aggressive configuration David chose (June 2026).** It replaced the
> conservative 50/30/20 A/B/C ensemble to put idle capital to work and raise return.
> It earns more in the recent regime but takes a deeper worst-case drawdown. The old
> ensemble is preserved for comparison in `results/REFINEMENT.md` ("Legacy ensemble").

---

## 1. What you are trading and why we trust it

A 60/40 capital split of two **uncorrelated** long-only sleeves — a mean-reversion
dip-buyer paired with a momentum breakout. Validated 2005–2026 on ~1,000 liquid US
stocks, 5 bps/side slippage, last 3.5 years held out of sample
(`results/REFINEMENT.md`, `results/refine_results.json`):

| | Full window (2005–2026) | Out-of-sample (2023+) |
|---|---|---|
| CAGR | 13.6% | 17.4% |
| Sharpe | 0.99 (SPY: 0.64) | 1.16 (SPY: 1.43*) |
| Max drawdown | **−24.9%** (SPY: −55%) | −16.3% |
| Monte Carlo p95 DD | −16.8% | — |

*2023–26 was a near-record bull run; SPY's 1.43 Sharpe there is an outlier no
low-exposure long/flat strategy matched.

**Why these two sleeves and not two mean-reversion sleeves:** A and H have a return
correlation of only **0.26** — they profit in different conditions and take turns, so
pairing them *shrinks* drawdown relative to either alone. (A second mean-reversion
sleeve was built and rejected precisely because it was 0.69-correlated with A and
nearly doubled drawdown for no extra return — see `backtest/strategies/range_reversion.py`
and the `2023_25_chop` slice in `results/gauntlet_range_reversion.json`.)

**Sleeves and the regimes they cover:**
- **A. Three-lower-lows dip buy (60%)** — mean reversion in uptrending stocks. Earns
  in bull/normal/choppy markets. Full-window Sharpe 1.10, CAGR 16.7%, PF 1.30, 61%
  win rate, ~11,900 trades. Standalone MaxDD −29% (knife-catching by construction).
- **H. 52-week-high momentum breakout (40%)** — buys new 252-day-high breakouts on
  above-average volume, **only when SPY > SMA(100)**. Full CAGR 7.5%, PF 1.21;
  **OOS CAGR 21.9%, OOS PF 1.37, OOS Sharpe 0.98** (best OOS profit factor of any
  sleeve tested). Standalone full MaxDD −44.6% — momentum crashes hard in 2008-type
  reversals; the pairing with A and the 5% stop are what tame it in the ensemble.

## 2. Hard parameters (validated config — do not change)

| Parameter | Value |
|---|---|
| Universe | S&P 500 ∪ Russell 1000 (`data/universe.csv`; rebuild monthly via `backtest/universe.py`) |
| Sleeve A (60%) | close > SMA200, close < SMA5, 3 consecutive lower lows, price > $1, 20d avg dollar vol > $10M → **limit buy at close − 0.75×ATR(10)**, DAY order at the open. Exit: sell at the open after the first close > prior close; hard 15-day time stop. **No stop loss** (validated: stops hurt this sleeve). Max 10 positions (~6% equity each). |
| Sleeve H (40%) | close makes a new **252-day closing high** (yesterday did not), volume > 50-day avg, price > $5, 20d dollar vol > $20M, **SPY > SMA(100)** → **market buy at the open**, ranked by 6-month momentum. Exit: **5% stop** (a close ≤ entry×0.95) OR 15-day time stop; sell at the open. Max 10 positions (~4% equity each). |
| Shares | **Fractional.** Position size = weight/10 of equity; qty = size ÷ price. Enables the full 20-name book on a $1–2k account. Alpaca allows fractional only on **DAY market/limit** orders — hence the single at-the-open run below. Orders under $1 notional are skipped. |
| Slippage budget | Validated at 5 bps/side. Sleeve A **dies at ~20 bps/side** (see §6). |

## 3. Daily operating procedure — one checkpoint

Both sleeves act at the **open**, so there is a single daily run. Signals come from
yesterday's completed daily bar and are executed at today's open — exactly the
backtest's timing.

### 3.1 Morning run (~9:35 am ET, every trading day)

```
cd "E:\Swing Trade Strategy Research"
.\.venv\Scripts\python.exe -m papertrade.run_daily morning        # live
.\.venv\Scripts\python.exe -m papertrade.run_daily morning --dry-run   # preview, submit nothing
```

The runner, in order: reconciles held positions with Alpaca; updates the account
high-water mark and applies the drawdown circuit breaker (§5); refreshes data and
screens; then:

1. **Sleeve A exits** (market sell at open): first close > prior close since entry,
   or 15-day time stop.
2. **Sleeve A entries** (limit DAY buys at close − 0.75×ATR). Never converted to
   market — an unfilled limit is simply no trade. Skipped if already held.
3. **Sleeve H exits** (market sell at open): a close ≤ entry×0.95 (5% stop) or
   15-day time stop.
4. **Sleeve H entries** (market buys at open) when SPY > SMA(100); skipped if the
   gate is off or already held.

The screener's as-of date MUST equal the last completed session. If it lags, data is
stale — the run acts on old signals; investigate per §5.

### 3.2 Conventions (resolve all boundary cases)

- **Day counting:** entry day = day 0. "15-day time stop" = sell at the open after
  day 15 is reached.
- **Staleness:** as-of must equal the last completed NYSE session. Sessions dropped
  by the screener that match `US_MARKET_HOLIDAYS` (or today's in-progress session)
  are benign.
- **One company = one slot** per sleeve; share classes count as one company (screener
  dedupes). A ticker already held (either sleeve) is not re-bought.
- **Fat-finger guard:** the screener EXCLUDES any A limit ≥ 10% below the last close
  (printed under `warnings`). Repeated warnings → flag to David.
- **Journal** every order, fill, skip, exit reason, and warning (automatic).

## 4. When signals exceed slots

- A: highest 20-day dollar-volume names (fill quality; backtest used random selection).
- H: strongest 6-month momentum.

## 5. Risk guardrails and stand-down rules

- **Per-position caps:** ~6% (A) / ~4% (H) of equity, recomputed daily. Max 10 per sleeve.
- **Account drawdown circuit breaker (now enforced in code, not just prose):** a
  high-water mark is stored in `papertrade/state.json`; each run computes drawdown =
  equity ÷ HWM − 1.
  - drawdown ≤ **−15%** → halt Sleeve A entries (the knife-catcher). Momentum entries and all exits continue.
  - drawdown ≤ **−20%** → halt **all** new entries. Exits always run. (Full-window MaxDD was −24.9%, so −20% is within distribution here — but it is the point to stand down and check for a data/regime problem before adding risk.)
- **Also stand down when:** screener as-of date is stale, > 5% of the universe is
  missing bars, repeated fat-finger warnings, or a held ticker has a pending
  acquisition/delisting headline (exit at next open, flag it).
- Never short. Never use margin beyond cash. Never trade options. Never override an
  exit rule because of news or conviction.

## 6. Execution discipline (this is where the edge lives or dies)

- **Sleeve A** slippage sensitivity (full window): 0 bps → 23.5% CAGR · 5 bps → 16.7%
  · 10 bps → 10.3% · **20 bps → negative**. A's limit orders *provide* liquidity, so
  realized slippage should be ~0 — but only if they stay resting limits. Any "chase
  the fill" behavior converts A into a knife-catching market strategy that loses money.
- **Sleeve H** buys/sells at the open with market orders in liquid names. It is *not*
  slippage-fragile like A, but momentum breakouts can gap. Scheduled cloud runs
  (GitHub Actions) can start several minutes late, so realized fills may drift from
  the 9:30 open the backtest assumed — for tighter fills, run locally at the open.
- **Fractional fills** at Alpaca settle at the same price as the whole-share order;
  the only constraint is the $1 minimum notional (auto-skipped).

## 7. Expected behavior and failure modes (read before judging a losing week)

- **Sleeve A** loses fastest in waterfall crashes (2008-type regimes drove its −29%
  standalone DD) and earns most in choppy uptrends. ~61% win rate; small average win;
  expect streaks of 5+ losers.
- **Sleeve H** has a **low win rate (~48%)** — momentum pays through a few large
  winners, not hit rate. It suffers "momentum crashes" (violent trend reversals:
  2008–09, spring 2020) — its standalone MaxDD was −44.6%. The SPY>SMA(100) gate keeps
  it flat in unhealthy markets, and the 5% stop caps individual losers.
- **The ensemble's** worst historical drawdown was −24.9%. A losing quarter — even a
  −20% stretch — is within distribution (§5); it is aggressive by design.

## 8. Monitoring and decay protocol

- **Monthly:** rebuild the universe (`python -m backtest.universe`); compare rolling
  12-month realized PF per sleeve vs backtest (A full 1.30 / OOS 1.19; H OOS 1.37).
  A sleeve below 1.0 for 6+ rolling months → flag to David.
- **Quarterly:** compare paper/live fills vs signal prices. Sleeve A realized slippage
  > 10 bps → execution problem, halt and investigate. Check H open-fill drift.
- **Yearly:** extend data (`python -m backtest.data`) and re-run
  `python -m backtest.gauntlet` + `python -m backtest.refine`; confirm the edge
  persists. Update `US_MARKET_HOLIDAYS` in `playbook/screener.py`.

## 9. Known limitations (documented honestly)

- **Survivorship bias:** the backtest universe is today's index members projected
  backward. Mean-reversion *benefits* from this bias (the graveyard is delisted names);
  momentum is less affected but not immune. Treat backtest CAGR as optimistic — the
  OOS window and paper trading are the corrective lenses.
- **Aggressive by choice:** this config carries a deeper drawdown (−24.9%) than the
  legacy 50/30/20 ensemble (−16.5%) in exchange for higher return. That is the
  accepted trade, not a bug.
- **Fractional-share execution** depends on Alpaca DAY order support and its $1 minimum;
  cloud-scheduled runs may fill momentum orders a few minutes off the open.
- yfinance is the data dependency; if it breaks, the screener fails loudly (§5).
- The 2026–27 holiday calendar is hardcoded; extend annually (§8).

## 10. Provenance chain (for auditing any rule)

Research cards → `research/candidates/`, `research/CATALOG.md`
→ gauntlet evidence → `results/gauntlet_*.json`, `results/GAUNTLET_SUMMARY.md`
→ refinement + ensemble selection → `results/REFINEMENT.md`, `results/refine_results.json`
→ this playbook. Engine assumptions: `backtest/engine.py` docstring; engine tests:
`backtest/test_engine.py`. Rejected mean-reversion alternative (for the record):
`backtest/strategies/range_reversion.py`.
