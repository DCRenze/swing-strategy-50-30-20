# Qullamaggie-style High-ADR Flag Breakout
- Agent: A (Reddit & social)
- Sources: https://www.reddit.com/r/wallstreetbetsOGs/comments/om7h73/trade_like_a_professional_breakout_swing_trading/
  https://www.reddit.com/r/qullamaggie/comments/qc7dvx/breakout_swing_trading_guide_the_4k_to_1m/
  https://www.reddit.com/r/qullamaggie/comments/1cpk4aa/backtestingpracticing_kks_breakout_strategy/
- Thesis: Stocks that have already made an explosive move (institutional accumulation) digest gains in a tightening flag/pennant near the rising 20SMA; when the range breaks upward on volume, the prior momentum resumes and the "most explosive part of the move" plays out over the next 3-20 days. Popularized by Kristjan Kullamagi (Qullamaggie); the r/wallstreetbetsOGs guide by u/OptionsTrader14 (very widely cross-referenced, dedicated r/qullamaggie subreddit exists) is the most mechanical public writeup.
- Entry rules:
  - Universe scan (run nightly): ADR(20) > 5% (high average daily range); dollar volume (close x volume) > $3M; listed stocks only (no OTC)
  - Momentum filter (any of): price +25% vs 22 days ago, OR +50% vs 67 days ago, OR +150% vs 126 days ago
  - Price within 15% of 6-day high and within 15% of 6-day low (i.e., tight recent range)
  - Stock has consolidated sideways with tightening range (flag/pennant) for days-to-weeks after the big move, riding or bouncing off the 20-day SMA (10-day SMA acceptable but higher failure rate)
  - Buy when price breaks above the top of the consolidation range on rising volume (intraday alert; do NOT anticipate the breakout)
  - Position size 10-25% of account (source's discretion guidance)
- Exit rules:
  - Initial stop: low of the breakout day
  - Day 2: optionally raise stop to breakeven
  - After 3-5 days or strong gain: sell 1/4 to 1/2 into strength
  - Trail remainder: close the whole position when price closes below the 10-day SMA ("soft" close-based stop)
- Indicators & parameters: ADR(20) > 5%; SMA(10), SMA(20); momentum lookbacks 22/67/126 days with +25%/+50%/+150% thresholds; $vol > 3M; 6-day high/low proximity 15%
- Claimed performance: Author claimed +16.5% ($658) in week 1 of a $4k-to-$1M challenge, and example trades of 17-42% gains in 1-4 days (IDT +25%/1d, SPCE +42%/3d, LPI +33%/4d, CRCT +17%/3d) — all unverified anecdote with screenshots. In the r/qullamaggie backtesting thread, u/pb0316 reports his own simulations found "amazing exposure to more right tail events (fat right tail)"; Kullamagi himself claims to have turned ~$5k into tens of millions with this + EPs (audited claims discussed in community, not independently verified here).
- Evidence quality: 3 (full mechanical scan + exit rules published; performance is anecdote; independent practitioners corroborate the fat-right-tail character but no published full backtest)
- Long-only fit: yes
- 2-15 day fit: yes (3-5 day partial, 10SMA trail typically exits within 1-3 weeks)
- Codability: partly — scan filters and MA-trail exits are pure daily OHLCV; the flag/pennant "tightening range" is discretionary (proxies: N-day range contraction, higher lows), and the canonical entry (intraday range break with stop at low-of-day) needs intraday data. Daily approximation: enter next open after a close above the N-day consolidation high, stop at signal-day low.
- Notes: Community itself flags regime dependence — in the May 2024 r/qullamaggie thread, u/goat__botherer: "breakouts just don't seem to be working currently... If KK himself... says he isn't really trading breakouts any more, I think you'd be wise to take that on board." Edge is concentrated in strong bull/momentum regimes (2020-21); expect low win rate (~30-40% per community discussion) with rare huge winners, so backtest results will be highly sensitive to a handful of trades. Stock selection ("hot sectors") is an additional discretionary layer the backtest can't capture. Variants worth testing: with/without market regime filter (QQQ > 20/50SMA), 10SMA vs 20SMA trail, 1-month vs 3-month momentum legs separately.
