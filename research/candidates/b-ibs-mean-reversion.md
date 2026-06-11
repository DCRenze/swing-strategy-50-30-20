# Internal Bar Strength (IBS) Mean Reversion
- Agent: B (Forums & platform communities)
- Sources: https://www.tradingview.com/script/I3PUR2GA-Internal-Bar-Strength-IBS-Strategy/
  https://alvarezquanttrading.com/blog/internal-bar-strength-for-mean-reversion/
  https://www.quantconnect.com/forum/discussion/12403/who-039-s-wrong-me-or-amibroker/
  https://www.quantifiedstrategies.com/ibs-internal-bar-strength-indicator-strategies/
- Thesis: A close near the bottom of the day's range (low IBS) signals intraday capitulation that tends to mean-revert over the next day(s); buying weakness and selling strength on the close exploits this overnight/short-horizon reversion.
- Entry rules:
  - IBS = (Close - Low) / (High - Low)
  - Buy at the close when IBS < 0.2 (aggressive variant: < 0.1)
  - Alvarez stock version uses IBS as a *filter* on a base mean-reversion system: S&P 500 members, close > SMA(200), 126-day S&P 500 return > 0, RSI(2) crosses below 2.5, AND IBS < 0.25 (best bucket: IBS < 0.10); buy next open
- Exit rules:
  - TradingView script: sell at the close when IBS >= 0.8
  - Alvarez base system: exit next open after RSI(2) closes above 50
  - No stop loss in either published version
- Indicators & parameters: IBS entry < 0.2 (or < 0.1/0.25), exit > 0.8; Alvarez filter combo: RSI(2) < 2.5, SMA(200), 126-day index return > 0
- Claimed performance: QuantifiedStrategies: SPY simple IBS strategy ~0.8% avg gain/trade, 78% win rate; QQQ 1.33% avg gain, 75% win rate. Alvarez (S&P 500 stocks, AmiBroker/Norgate): IBS < 10 bucket gave 58% average-profit improvement over baseline on 34% of trades with 71% win rate; IBS < 25 retained 63% of trades with 21% profit improvement. QuantConnect thread: same QQQ-style IBS strategy showed 15.1% CAGR / 28% DD in AmiBroker vs 5.5% CAGR / 33% DD on QuantConnect.
- Evidence quality: 4
- Long-only fit: yes
- 2-15 day fit: partial (many trades resolve in 1-3 days; some are next-day exits)
- Codability: yes — IBS is computed directly from daily OHLCV
- Notes: Strong cross-source corroboration (TradingView open-source script, two independent quant blogs, QuantConnect thread). Two big trust caveats: (1) the QuantConnect-vs-AmiBroker discrepancy shows results are highly sensitive to fill assumptions, commissions, and adjusted-vs-raw prices — buy-on-close execution near 4pm is required to match backtests; (2) multiple sources state IBS works best on indices/diversified ETFs and is weaker standalone on single stocks — Alvarez explicitly recommends it as a filter layered on another mean-reversion entry, which is the form to test for this project.
