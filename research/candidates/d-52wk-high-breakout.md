# 52-Week-High Proximity / Breakout Momentum (Long Leg, Short-Horizon Adaptation)
- Agent: D (Academic & quant literature)
- Sources: https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2004.00695.x — George & Hwang, "The 52-Week High and Momentum Investing," Journal of Finance 2004 (also https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1104491)
  https://gattonweb.uky.edu/faculty/lium/52weekhigh.pdf — Hong, Jordan & Liu, "Industry information and the 52-week high effect"
  https://jurf.org/wp-content/uploads/2017/01/ostasheva-wenhao-2016.pdf — Ostasheva & Wenhao, partial replication of George & Hwang, 2016
  https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365 — McLean & Pontiff, "Does Academic Research Destroy Stock Return Predictability?," Journal of Finance 2016 (decay context)
- Thesis: Investors anchor on the 52-week high and are reluctant to bid prices through it, so good news arriving near the high is incorporated only slowly; stocks at/near their 52-week high subsequently drift upward, and unlike past-return momentum the effect does not reverse long-term (George & Hwang 2004).
- Entry rules:
  - Universe: US common stocks; for our pipeline restrict to liquid names (price > $5, top ~1000 by dollar volume). [Liquidity screen is MY addition]
  - Compute ratio R = close / max(high over trailing 252 trading days).
  - Paper spec: each month, long the top 30% of stocks by R. SWING TRANSLATION (mine): buy when a stock CLOSES at a new 52-week high (R crosses 1.0), or closes with R >= 0.98 after touching a new intraday 52-week high, ideally with volume above its 50-day average [volume filter is mine].
  - Skip entries when the overall market is below its 200-day MA (George-Hwang profits are regime-dependent; momentum crashes occur in rebounds). [MY addition]
- Exit rules: Paper holds 6 months (overlapping monthly portfolios). ADAPTATION (mine): hold 10-15 trading days, or exit early if close falls more than ~5% below the breakout level. The documented effect is slow drift, so a short hold captures only a slice of it.
- Indicators & parameters: 52-week (252-day) rolling high; paper ranks by price/52wk-high ratio, top 30% = winners; monthly rebalance, 6-month hold; equal weight.
- Claimed performance: George & Hwang 2004: 52-week-high winner-minus-loser strategy earns ~0.45% per month US 1963-2001 (their measure dominates Jegadeesh-Titman past-return momentum; risk-adjusted past-return momentum drops from 0.59%/mo to 0.21%/mo once nearness-to-high is controlled). International replications: 0.60-0.94%/mo, significant in most of 20 markets. All GROSS of costs.
- Evidence quality: 4 for the monthly-horizon anomaly (top journal, heavily replicated); effectively 3 for this card because the 10-15-day breakout implementation is my translation, not the paper's tested spec.
- Long-only fit: partial — documented as winner-minus-loser; the long (near-high) leg is standalone-implementable and is where the underreaction mechanism lives.
- 2-15 day fit: partial — documented holding is 6 months; short-horizon slice is plausible (drift is continuous) but not separately measured in the source papers.
- Codability: yes — pure daily OHLCV.
- Notes: McLean & Pontiff (2016) document an average 58% post-publication decay across 97 anomalies; 52-week-high momentum was widely published by 2004 and is heavily traded. The effect in the paper is cross-sectional and slow — converting it to an event-style breakout trade adds unmodeled risk (false breakouts). Momentum-family strategies suffer sharp crashes in market rebounds (e.g., 2009). Gross-of-cost results; however, turnover of a near-high portfolio is modest and the names are typically liquid, so cost survival is better than for reversal-type effects. The long leg concentrates in stocks with recent strength — overlaps with standard momentum exposure.
