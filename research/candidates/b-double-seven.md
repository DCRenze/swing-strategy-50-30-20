# Double 7s (Connors/Alvarez)
- Agent: B (Forums & platform communities)
- Sources: https://alvarezquanttrading.com/blog/double-7s-strategy/
  https://www.quantifiedstrategies.com/larry-connors-double-seven-strategy-does-it-still-work/
  https://quantifiedstrategies.substack.com/p/larry-connors-double-seven-trading-bad
  https://thepatternsite.com/Double7sSetup.html
  https://statoasis.com/post/connors-double-7-strategy-your-beginner-s-guide-to-algo-trading-success
- Thesis: In an established uptrend, a close at a 7-day low marks a short-term capitulation that statistically resolves upward; selling at a 7-day high captures the snap-back symmetrically without any oscillator.
- Entry rules:
  - Close > SMA(200)
  - Today's close is the lowest close of the last 7 trading days
  - Buy at the close (Alvarez retest used next-open execution)
  - Alvarez stock-portfolio variant: index (SPX/NDX) close > its 200-day MA AND stock close > its 200-day MA; 10% position size, max 10 positions
- Exit rules:
  - Sell at the close when today's close is the highest close of the last 7 trading days
  - No stop loss, no profit target, no time stop in original rules
- Indicators & parameters: SMA(200); 7-day lowest close (entry); 7-day highest close (exit). Beware two interpretations of "7-day low": Close <= LLV(Close,7) vs Close < Ref(LLV(Close,6),-1)
- Claimed performance: QuantifiedStrategies on SPY since 1993: 154 trades, avg gain 1.18%/trade, 82.5% win rate, profit factor 2.58, Sharpe 1.4, CAGR ~6.3% (low exposure); another run: 1189 trades, 0.63% avg gain. Alvarez: beat buy-and-hold on SPY/QQQ 2000-2007 with ~26% exposure; underperformed 2008-2015; on S&P500/NDX100 stocks returns marginally beat buy-and-hold with ~1/3 lower drawdown.
- Evidence quality: 4
- Long-only fit: yes
- 2-15 day fit: yes (typical hold a few days to ~2 weeks)
- Codability: yes — pure daily OHLCV
- Notes: Multiple independent backtests agree on the broad picture: high win rate, larger average loser than winner (2.99% vs 2.06% on one SPY test), and a decaying edge — "almost all gains happened before 2010" (QuantifiedStrategies) and Alvarez concludes the edge has "shrunk or disappeared" as mean reversion became crowded. 2008 produced one catastrophic trade in the no-stop version. The stock-basket variant with dual 200-day MA filters is the form most relevant to this project.
