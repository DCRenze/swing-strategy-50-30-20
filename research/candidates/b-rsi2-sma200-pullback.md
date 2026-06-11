# Connors RSI(2) Pullback (long leg)
- Agent: B (Forums & platform communities)
- Sources: https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2
  https://github.com/handiko/RSI-2-Stock-Trading-Strategy-Pinescript
  https://quantopian-archive.netlify.app/forum/threads/spy-master-rsi2-mean-reversion-strategy-for-spy.html
  https://www.tradingview.com/script/QJSXeJnv/
  https://www.marketinout.com/stock-screener/backtest/backtest_strategy.php?strategy=larry-connors-rsi-2
- Thesis: Stocks/indices in a long-term uptrend that suffer an extreme 1-2 day oversold washout tend to snap back within days; the 2-period RSI isolates those extremes while the 200-day MA keeps you on the right side of the trend.
- Entry rules:
  - Close > SMA(200) (long-term uptrend filter)
  - RSI(2) < 10 (Connors found lower thresholds, e.g. < 5, gave higher per-trade returns)
  - Buy at the close of the signal bar (or next open in practical implementations)
- Exit rules:
  - Classic Connors: exit long when close > SMA(5); no stop loss (Connors' testing found stops hurt performance on stocks/indices)
  - TradingView/GitHub Pine variant (handiko): exit when close exceeds the previous bar's high
  - Alternative community variant: exit when RSI(2) > 70
- Indicators & parameters: RSI(2) < 10 entry (variant: < 5); SMA(200) trend filter; SMA(5) exit (or prior-bar-high exit, or RSI(2) > 70 exit)
- Claimed performance: StockCharts/Connors research: "the lower RSI dipped, the higher the returns on subsequent long positions." A quantifiedstrategies.com backtest summary (page itself bot-walled on fetch) reports ~0.95% average gain per trade, 76% win rate, max DD 31%, CAGR 6.8% with ~18% time invested. Recent Medium backtests (2024–2026 SPY) show the raw RSI(2)-without-trend-filter version losing money (30% win rate, -28.9%).
- Evidence quality: 4
- Long-only fit: yes (Connors also published a short leg; long leg stands alone)
- 2-15 day fit: yes (typical hold 2-7 trading days)
- Codability: yes — pure daily OHLCV
- Notes: The most replicated swing strategy in forum/platform communities; dozens of TradingView/QuantConnect/Quantopian implementations. Quantopian "SPY Master" thread replies are an important counterweight: one user computed a t-value of only 0.109 for RSI2 signals, others noted it "underperforms SPY by quite a bit" outside crash regimes and may be overfit to 2008. Variant worth testing (EdgeTools "Larry Connors RSI 3" on TradingView): require RSI(2) to have declined 3 consecutive days starting from above 60 with final value < 10, exit RSI > 70 — fewer, more selective signals. Consensus across sources: edge persists but has shrunk since ~2010; works better as a stock-basket strategy with a regime filter than on a single ticker.
