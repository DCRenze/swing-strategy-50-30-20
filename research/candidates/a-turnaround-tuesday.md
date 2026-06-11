# Turnaround Tuesday (Monday-Weakness Buy)
- Agent: A (Reddit & social)
- Sources: https://therobusttrader.com/turnaround-tuesday-trading-strategy/
  https://quantifiedstrategies.substack.com/p/turnaround-tuesday-strategy-backtest
  https://www.reddit.com/r/StockMarket/comments/9opqdl/welcome_to_turnaround_tuesday_market_seeing_its/ (evidence the effect is community folklore; no rules content)
- Thesis: A calendar/behavioral effect: weekend news digestion and Monday liquidation pressure create Monday weakness in equity indices that disproportionately reverses on Tuesday and the following days ("markets that fall on Monday often rebound on Tuesday or the days after"). Traces to 1980s floor-trader folklore; the phrase recurs constantly across finance Twitter/Reddit; the only public rule-level treatments are the Quantified Strategies / Robust Trader backtests (same authors).
- Entry rules (Robust Trader published version 1):
  - Today is Monday
  - Close is at least 1% lower than Friday's close
  - Buy at the close
- Entry rules (published version 2):
  - Today is Monday; close < open; IBS < 0.2; buy at the close
- Exit rules:
  - Version 1 and 2 as published: sell at Tuesday's close (1-day hold — below our horizon)
  - Extended variants (paywalled rules, stats public): holding "several days" / exiting on strength (e.g., close > yesterday's high) lifts CAGR from ~1.8% to ~6.5% and win rate from 56% to ~60-69% — the multi-day variant is the one relevant to this project: buy Monday weakness at close, exit first close > prior day's high or after ~5 trading days
- Indicators & parameters: Monday-only filter; -1% vs Friday threshold (v1); IBS < 0.2 (v2); exit Tuesday close, or strength-exit for multi-day variant
- Claimed performance: SPY 1993-2021 (v1): 163 trades, 63% win rate, avg winner 1.75% / avg loser -1.05%, CAGR ~9% quoted on ~2.25% exposure (per-trade avg ~0.7%). V2: 247 trades, 60% WR. Quantified Strategies substack (SPY): simple version 212 trades, 0.3%/trade, 56% WR, CAGR 1.8% at 2.5% exposure; "extended holding period" version 0.45%/trade, 60% WR, CAGR 6.5%; advanced version 0.46%/trade, 69% WR, CAGR 7%.
- Evidence quality: 3 (published backtests with stats, but the best multi-day exit rules are partially paywalled; effectively a single source family (QS/Robust Trader are the same shop); reddit/Twitter presence is folklore-level, not independent backtests)
- Long-only fit: yes
- 2-15 day fit: partial — canonical version is a 1-day hold (out of scope); the documented extended variant (hold until close > prior high, max ~5 days) fits and is what should be tested
- Codability: yes — trivial on daily OHLCV (day-of-week + return/IBS conditions; close-to-close execution)
- Notes: Day-of-week effects are notorious for decaying after publication (the classic "weekend effect" inverted after the 1980s); QS's own numbers show thin per-trade edge (0.3-0.46%) that is sensitive to execution at the close and commissions. Worth testing mainly as a timing overlay/filter on the other mean-reversion cards (e.g., does the IBS or vol-band entry perform better when triggered on a Monday?) rather than as a standalone return stream. Note buying the close requires acting on ~3:55pm data; next-open entry should be sensitivity-tested.
