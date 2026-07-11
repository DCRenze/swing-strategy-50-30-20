# CLAUDE.md — operating context for Claude agents

Read this before touching anything. It is the fast orientation; `playbook/PLAYBOOK.md` is the
**authoritative** trading spec and always wins on any rule detail.

## What this is

A research-and-execution pipeline for a **long-only US-stock swing strategy** (2–15 trading-day
holds) run on **Alpaca paper trading**. Flow: `research/` (strategy cards) → `backtest/`
(vectorized engine + robustness gauntlet) → `results/` (validation evidence) → `playbook/`
(agent-executable spec + live screener) → `papertrade/` (daily Alpaca runner + reporting).

## ⚠️ Naming trap — read this twice

The repo is named **`swing-strategy-50-30-20`**, but that name is **stale**. The **live book is
the aggressive 60/40 "A/H" ensemble** adopted June 2026:

- **Sleeve A — three-lower-lows dip buy — 60%** (mean-reversion)
- **Sleeve H — 52-week-high breakout — 40%** (momentum)

The old **50/30/20 A/B/C** ensemble (3-lower-lows 50 / turn-of-month 30 / turnaround-Tuesday 20)
is **retired**, kept only for comparison in `results/REFINEMENT.md` ("Legacy ensemble"). When you
see "50/30/20", it is history, not the live config. Sleeve labels in code/data are **A** and
**H** (`?` = untracked/unattributed position).

## The two sleeves (one line each)

- **A · dip-buyer (60%, mean-reversion):** `close>SMA200`, `close<SMA5`, 3 consecutive lower
  lows, liquid → **limit buy at `close − 0.75×ATR(10)`** (DAY order). Exit: sell at open on the
  first close > prior close, or a hard **15-day time stop**. **No stop-loss** (validated: stops
  hurt this sleeve). Max 10 positions (~6% equity each).
- **H · momentum (40%):** new **252-day closing high** on above-average volume, liquid, **only
  when SPY > SMA(100)** → **market buy at the open**, ranked by 6-month momentum. Exit: **5% stop**
  (a close ≤ entry×0.95) or **15-day time stop**. Max 10 positions (~4% equity each).

The two are only ~0.26 correlated — pairing them shrinks drawdown. Validated 2005–2026 (5 bps/side
slippage, last 3.5y out-of-sample): full CAGR 13.6%, Sharpe 0.99, MaxDD −24.9%; OOS CAGR 17.4%.

## Risk guardrails (enforced in `papertrade/run_daily.py`, not just prose)

- Account **high-water mark** lives in `papertrade/state.json`; each run computes
  `drawdown = equity/HWM − 1`.
- drawdown ≤ **−15%** → halt Sleeve A entries (the knife-catcher); H entries + all exits continue.
- drawdown ≤ **−20%** → halt **all** new entries; exits always run.
- **Never** short, use margin, or trade options. **Never** override an exit rule for news/conviction.
- Fat-finger guard: the screener excludes any A limit ≥10% below the last close.

## Data & file map

| Path | What it holds |
|---|---|
| `papertrade/state.json` | Live state: `positions{ticker→{sleeve,entry_date,entry_px}}` + `hwm`. Alpaca is the source of truth for holdings; this file adds sleeve attribution. |
| `papertrade/trades.jsonl` | Realized closed-trade ledger, one JSON/line: `{ticker,sleeve,entry_date,exit_date,entry_px,exit_px,qty,ret,pnl}`. |
| `papertrade/journal/YYYY-MM-DD.jsonl` | Per-day decision log. `kind` ∈ run_start (carries daily `equity`/`hwm`/`drawdown`), order_submitted, skip, exit_reason, trade_closed, position_adopted, action_needed, warning, run_end, … |
| `data/universe.csv` | Tradable universe: `ticker,name,source` (sp500 ∪ russell1000). |
| `results/` | Backtest evidence: `GAUNTLET_SUMMARY.md`, `REFINEMENT.md`, `gauntlet_*.json`, equity/trades CSVs. |
| `playbook/screener.py` | Live daily screener; all tunable params are constants at the top. |
| git-ignored | `.env` (Alpaca keys), `data/*.parquet` (regenerated), generated `reports/`. |

## Automation

- **`.github/workflows/morning-run.yml`** — one daily run (~9:35am ET, fired by an external
  scheduler via `workflow_dispatch`): reconcile → drawdown gate → A exits/entries → H
  exits/entries; commits `state.json` + `journal/` + `trades.jsonl`; posts a Discord morning report.
- **`.github/workflows/eod-report.yml`** — read-only end-of-day Discord wrap-up (cron).
- **`.github/workflows/weekly-report.yml`** — `papertrade/report_weekly.py` builds a
  self-contained HTML PM dashboard and posts it to Discord every Friday after the close
  (read-only, `--discord`). The workflow installs headless Chromium so the report is rendered
  to a PNG and posted **inline** (Discord doesn't render `.html`), with the HTML attached as a
  zoomable backup; both are also kept as a workflow artifact. It runs on GitHub Actions, not a
  Claude routine, because it needs open outbound network — Alpaca (live equity/positions),
  yfinance (SPY/QQQ/VIX), and Discord — which the Claude env blocks by egress policy. Uses the
  same three Actions secrets as the daily workflows. (A disabled Claude Routine for a
  narrative-added variant exists; re-enable it only after opening the env network policy, and
  then avoid double-posting.)
- Keys come from `.env` locally (template: `.env.example`) or GitHub Actions secrets in CI.

## Conventions & decay watch

- **Day counting:** entry day = day 0; "15-day time stop" = sell at the open once day 15 is reached.
- **Backtest benchmarks** for spotting strategy decay (PLAYBOOK §8): Sleeve A profit factor 1.30
  full / 1.19 OOS; Sleeve H OOS PF 1.37. A sleeve below PF 1.0 for 6+ rolling months → flag David.
- Every strategy **fails** the gauntlet individually (`GAUNTLET_SUMMARY.md`); the **ensemble** is
  what clears the bar via diversification. Don't judge a sleeve in isolation.

## Golden rule

Every parameter in the playbook/screener is backed by evidence in `results/`. **Never change a
validated parameter** (weights, thresholds, stops, lookbacks) without re-running
`backtest/gauntlet.py` + `backtest/refine.py` and updating the evidence — changing it silently
invalidates the whole validation chain. Reporting/tooling changes are additive and read-only;
they must never place, modify, or cancel an order.
