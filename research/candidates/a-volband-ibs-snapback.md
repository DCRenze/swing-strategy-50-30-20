# Volatility-Band Snapback (Rolling-High Lower Band + IBS Filter)
- Agent: A (Reddit & social)
- Sources: https://www.reddit.com/r/algotrading/comments/1cwsco8/a_mean_reversion_strategy_with_211_sharpe/
  https://www.quantitativo.com/p/a-mean-reversion-strategy-with-211 (full write-up by the same author, u/ucals)
  https://github.com/fxhuhn/backtesting-trading-strategies/blob/main/strategies/mean_reversion_ndx100.ipynb (independent replication on NDX-100 stocks, linked in thread)
- Thesis: When an index ETF closes more than 2.5x its average daily range below its recent 10-day high AND closes near the bottom of its daily range, the selloff is statistically overdone and snaps back within days. Posted to r/algotrading (May 2024, 202 upvotes, u/ucals) with full rules, equity curves, and parameter-sensitivity replies; author credits the rule set to a quant blog.
- Entry rules:
  - Compute rolling mean of (High - Low) over last 25 days
  - Lower band = (rolling 10-day high) - 2.5 x (25-day mean of High-Low)
  - Compute IBS = (Close - Low) / (High - Low)
  - Go long when close < lower band AND IBS < 0.3
  - Execution: author states orders filled at next day's open
- Exit rules:
  - Original: exit when close > yesterday's high
  - Improved ("dynamic stop"): same exit, plus close the trade if price falls below the 300-day SMA (regime stop)
  - No profit target; no fixed time stop (typical hold a few days)
- Indicators & parameters: 25-day mean range; 10-day rolling high; band multiplier 2.5; IBS < 0.3; exit close > prior high; 300-day SMA regime stop
- Claimed performance: On QQQ, ~25-31 years: Sharpe 2.11, 13.0% annualized (vs 9.2% B&H), max DD -20.3% (vs -83% B&H), 414 trades, 0.79% avg/trade, 69% win rate, profit factor 1.98. Robustness reply in-thread: with 21-day range and IBS 0.25 instead, Sharpe 1.96, 11.5% ann., -18% maxDD, 68% WR — "equity curve almost identical." (Blog's dynamic-stop table cites 155 trades for one variant — trade-count bookkeeping differs between post and blog.)
- Evidence quality: 4 (published backtest with complete rules, stats, robustness check on request, plus an independent user's replication notebook on Nasdaq-100 stocks; minus one point for single-instrument focus, in-sample tuning of the 300SMA stop, and the SPY/QQQ ambiguity in the original post)
- Long-only fit: yes
- 2-15 day fit: yes (exit on first close above prior high — typically 2-10 trading days)
- Codability: yes — pure daily OHLCV
- Notes: OVERLAP WARNING — uses IBS as a secondary filter, so it is a cousin of the already-carded IBS mean reversion; the materially different element is the volatility-scaled distance-from-rolling-high band as the primary trigger (a "rubber band" stretch measure) and the close-above-prior-high exit. Top comment warns of overfitting risk given 4 tunable parameters and few trades/short duration; another notes the strategy class implicitly assumes the post-2000 "market always bounced" regime. The author planned a forward test and an extension trading all NDX-100 components in parallel (more trades, less idiosyncratic risk) — that portfolio version is the form most relevant to this project. Buying at next open after a band-break close materially changes fills vs close execution; test both.
