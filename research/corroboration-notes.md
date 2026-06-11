# Corroboration notes & cross-agent findings

Collected from research agents' final reports (Phase 1). These supplement the strategy cards in `candidates/` with independent backtests and community findings that didn't warrant their own cards.

## Corroboration for existing cards

### Connors RSI(2) pullback above SMA200 (`b-rsi2-sma200-pullback.md`)
- **Reddit independent 34-yr backtest** (r/algotrading, u/Russ_CW, 1990–2024 SPX, code public):
  https://www.reddit.com/r/algotrading/comments/1fm5lfj/backtest_results_for_connors_rsi2_strategy/
  Confirms high win-rate / low-exposure profile. Key findings: adding a 200MA-based stop-loss made results *worse* on every metric; time-based exits underperformed the 5MA-cross exit. Parameter heatmap (RSI 2–20 × thresholds 5–40) published.
- **Quantified Strategies** (SPY since 1993, snippet-sourced): basic RSI2 avg 0.9%/trade, ~9% annual, MaxDD 34%, 28% exposure; with 200MA filter avg 0.95%/trade, CAGR 6.8%, MaxDD 31%, 18% exposure.
- **Alvarez Quant Trading** — materially actionable universe insight:
  https://alvarezquanttrading.com/blog/rsi2-strategy-double-returns-with-a-simple-rule-change/
  Russell 3000, 2007–2018, RSI2<10 + close>100MA + 5%-below limit entry, exit RSI2>50 or 10 days, 1,947 trades. Switching universe to **ex-index stocks** (formerly in Russell 3000): CAR +121%, MaxDD −54%, avg P/L +150%, Sharpe +172%.
- **Quantitativo** — https://www.quantitativo.com/p/trading-the-mean-reversion-curve
  Sharpe-weighted blend of RSI2-threshold (5–30) stock portfolios: 25.7% annual since 2010 vs 17.6% benchmark, Sharpe 1.14 vs 0.89, MaxDD 28% vs 36%.

### Double Seven (`b-double-seven.md`)
- **Reddit 34-yr backtest** (same author): https://www.reddit.com/r/algotrading/comments/1g2rzw7/backtest_results_for_larry_connors_double_7/
  1990–2024: 74% win rate, R:R 0.66, ~18% time-in-market. Warns drawdown explodes (~2.5×) moving from 7→8 day lookback (parameter fragility); close-above-5MA exit more robust than canonical 7-day-high exit.
- **Quantified Strategies** (SPY since 1993): 154 trades, avg 1.18%/trade, 82.5% win, CAGR 6.3%, PF 2.58, Sharpe 1.4, MaxDD 33% vs 55% B&H, 26% exposure. **Almost all gains pre-2010 — decay warning.**

### IBS mean reversion (`b-ibs-mean-reversion.md`)
- **Reddit "buy the dip" thread** (671 upvotes): https://www.reddit.com/r/algotrading/comments/1f0689m/backtest_results_for_a_simple_buy_the_dip_strategy/
  "Close distance %" = IBS; win rate rises monotonically as IBS falls; outperformed B&H on 5 indices; symmetric short version fails. Quoted X variant (@RelSentTech): buy SPY when IBS<0.10, hold until 3 consecutive days without IBS<0.10 → claimed 1.9× B&H, Sharpe 1.9 vs 0.6, MaxDD −21% vs −55%; cites SSRN 4339128. Ex-prop-trader comment: firm's biggest strategy was long-only SPY dip-buying.
- **Quantified Strategies**: CAGR 15.3% at 36% exposure, 583 trades, avg hold 5.8 days, 74% win, MaxDD 22%, PF 2.73, Sharpe 1.7.
- **Alvarez**: IBS<0.10 as filter on an S&P 500 RSI2 system → +58% avg P/L on 34% of trades; win rate ~71% low-IBS vs ~57% high-IBS. **IBS is best used as a filter layered on other entries.**

### PEAD long leg (`d-pead-ear-long-leg.md`)
- r/wallstreetbetsOGs episodic-pivot guide grounds the EP setup in academic PEAD literature ("strength inversely related to firm size", "active institutional ownership weakens PEAD"):
  https://www.reddit.com/r/wallstreetbetsOGs/comments/q5xtno/

## Recurring community themes (Agent A)
1. **Long beats short, everywhere.** Every poster testing the symmetric short version of a long edge reported failure or break-even. Supports the long-only mandate.
2. **Plain breakouts decayed post-2021** per the breakout community itself (r/qullamaggie: "KK himself isn't really trading breakouts any more"); community migrated to episodic pivots / catalyst gaps. Momentum cards need regime filters and feast-or-famine expectations.
3. **High win rate ≠ edge; stops hurt index mean reversion.** Two independent systematic testers found hyped high-WR setups have negative expectancy after costs; both RSI2/Double7 tests found stop losses degrade index mean reversion — consistent with Connors literature. Most reddit "swing backtests" actually exit same/next day; genuine 2–15 day systems are rarer than post volume suggests.

## Popular-but-probably-bogus (skip; don't backtest)
- RSI(14) + Bollinger touch reversal — tested across 280 instruments × 8 timeframes, "mostly fails": https://www.reddit.com/r/swingtrading/comments/1pt0etu/
- Fibonacci 61.8% retracement fades — "breaks down fast": https://www.reddit.com/r/swingtrading/comments/1pn9zjb/
- Pure ADX-cross entries — overfit criticism in-thread; only the Raschke "Holy Grail" directional variant is worth testing.
- Trendline/diagonal-breakout "72% win rate" posts, account-flip challenges — no mechanical rules / options / survivorship porn.
- Bollinger Band Squeeze breakout — QS: "doesn't perform particularly well for most assets" despite many versions. Deprioritize low-vol-breakout variants.
- VCP claims of "90.77% success rate" (finermarketpoints.com) — marketing, no methodology. **No credible US-stock mechanized VCP backtest found anywhere**; NR7/inside-day compression is the closest tested primitive.

## Source-trust flags (Agent C)
- `quantifiedstrategies.com` — honest and internally consistent, but bot-walled (stats via snippets/Substack mirror), best variants paywalled, headline win rates cherry-picked. Treat numbers as hypotheses.
- `easycators.com` — ThinkScript vendor but faithfully republishes Connors/Alvarez book rules; acceptable secondary source.
- `journeymaninvestor.com`, `finermarketpoints.com` — promotional; ignore.

## Known duplicates to merge in catalog
- `a-turnaround-tuesday.md` ≡ `c-turnaround-tuesday.md` (same effect; merge, keep both source sets)
- `a-volband-ibs-snapback.md` ≡ `c-quantitativo-band-ibs.md` (same Quantitativo band+IBS setup found via different routes — strong cross-beat corroboration signal)
