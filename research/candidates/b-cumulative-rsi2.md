# Cumulative RSI(2) Strategy (Connors/Alvarez)
- Agent: B (Forums & platform communities)
- Sources: https://easycators.com/thinkscript/cumulative-rsi-2-trading-strategy/
  https://www.quantitativo.com/p/squeezing-more-profits-with-cumulative
  https://easylanguagemastery.com/strategies/connors-2-period-rsi-update-2019/
- Thesis: Summing the last two readings of RSI(2) demands *persistent* short-term oversold pressure rather than a single washout bar, filtering out noise trades and improving risk-adjusted returns versus vanilla RSI(2).
- Entry rules:
  - Close > SMA(200) (long-term uptrend filter)
  - Cumulative RSI = RSI(2) today + RSI(2) yesterday
  - Book rules (Short Term Trading Strategies That Work, p.67): enter long at close when cumulative RSI < 35
  - Quantitativo single-stock variant: cumulative RSI < 10; max 3 concurrent positions; prefer lower market cap when more than 3 signals; liquidity filter (traded all sessions past 3 months, position <= 5% of median ADV)
- Exit rules:
  - Exit at close when cumulative RSI > 65
  - No stop loss in book version; quantitativo variant also used no hard stop
- Indicators & parameters: RSI(2); cumulative window 2 days; entry < 35 (book) or < 10 (stocks variant); exit > 65; SMA(200) filter
- Claimed performance: Book (SPY 1993-2008): "88% accurate... earning 65.53 SPY points with an average gain of 1.26% and average holding period of 3.7 trading days." Quantitativo on large/mega-cap US stocks 1999-2024: 26.6% annual return, Sharpe 1.18, max DD 37%, ~65% win rate (vs vanilla RSI(2): 26.8% / 1.05 / 57% DD); sensitivity analysis across 198 parameter sets: mean return 25.7% (range 16.2%-31%).
- Evidence quality: 5
- Long-only fit: yes
- 2-15 day fit: yes (avg hold ~3.7 trading days)
- Codability: yes — pure daily OHLCV
- Notes: One of the few candidates with a published parameter-sensitivity analysis, which raises trust. Caveats from the same source: performance deteriorated post-2013 ("losing its edge"), the 37% max drawdown made the author decline to trade it live, and EasyLanguage Mastery's 2019 update found the strategy underperformed in 2014/2016/2018 after beating the S&P every year 2000-2013. No-stop design means tail risk on single names must be handled by position limits.
