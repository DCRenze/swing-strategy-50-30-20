# Weekly Short-Term Reversal — Long Losers in Liquid Large Caps
- Agent: D (Academic & quant literature)
- Sources: https://academic.oup.com/qje/article-abstract/105/1/1/1928416 — Lehmann, "Fads, Martingales, and Market Efficiency," QJE 1990
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1605049 — de Groot, Huij & Zhou, "Another Look at Trading Costs and Short-Term Reversal Profits," 2011 (also https://repub.eur.nl/pub/25718/AnotherLook_2011.pdf)
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=555968 — Avramov, Chordia & Goyal, "Liquidity and Autocorrelations in Individual Stock Returns," Journal of Finance 2006
  https://www.nber.org/system/files/working_papers/w17653/w17653.pdf — Nagel, "Evaporating Liquidity," NBER WP 17653 / RFS 2012
  https://quantpedia.com/strategies/short-term-reversal-in-stocks — Quantpedia, "Short Term Reversal Effect in Stocks"
- Thesis: One-week losers bounce the following week because large short-horizon price moves are partly liquidity-demand pressure rather than information; the reversal return is compensation earned by liquidity providers (Lehmann 1990; Nagel 2012). The premium is time-varying and largest when volatility/VIX is elevated.
- Entry rules:
  - Universe: ~100-500 largest US stocks by market cap or dollar volume (de Groot et al. show net profitability requires restricting to large caps; Quantpedia spec uses the 100 biggest). [Universe size beyond 100 is my extension]
  - At each weekly rebalance (paper: weekly; daily-staggered tranches are MY translation), rank stocks by trailing 5-trading-day total return.
  - Buy the bottom decile (or the 10 worst among the top 100) at the close.
  - Optional regime filter (MY translation of Nagel 2012): only deploy, or upsize, when VIX is above its 1-year median — expected reversal returns are strongly increasing in VIX.
- Exit rules: Hold 5 trading days (one week), then sell at close and re-rank. Documented spec is a fixed 1-week holding period with weekly rebalancing.
- Indicators & parameters: Formation = past 5 trading days return; holding = 5 trading days; portfolio = bottom decile / bottom 10 of top-100 universe; equal weight.
- Claimed performance: Quantpedia backtest of de Groot et al. spec (100 largest US stocks, long losers / short prior-month winners, weekly): 16.25% annual NET of costs, Sharpe 1.09, vol 14.9%, max DD -52.9%, 1990-2009. de Groot et al. report 30-50 bps per week net of transaction costs for the largest-cap universe. Lehmann 1990 reported gross weekly L/S profits that he argued survived plausible costs (1962-1986 sample) — later work disputes this for the broad universe.
- Evidence quality: 4
- Long-only fit: partial — academic spec is long-short; the long (loser) leg is documented to carry a large share of the profit and is standalone-implementable, but published net-return numbers are for the L/S spread.
- 2-15 day fit: yes — 5-day formation, 5-day hold.
- Codability: yes — close-to-close returns only; VIX filter needs VIX series.
- Notes: CRITICAL cost sensitivity: Avramov-Chordia-Goyal 2006 show reversal profits concentrate in illiquid, high-turnover stocks and are smaller than likely costs in the broad universe; the effect only survives costs when traded in the largest, cheapest-to-trade names (de Groot et al.: up to ~30 bps/week net in largest US stocks). Turnover is extreme (~100% weekly), so slippage assumptions dominate results. Post-decimalization (2001+) literature finds general attenuation of short-horizon anomalies as liquidity improved. Nagel 2012: expect lumpy, crisis-concentrated returns (strategy is short liquidity, long volatility events). Quantpedia's 16.25% net figure ends in 2009 and includes the 2008-09 spike — expect materially lower in calm regimes.
