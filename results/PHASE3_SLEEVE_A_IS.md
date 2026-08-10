# Phase 3 - Sleeve-A-only capital utilisation (in-sample)

Window 2005-06-01 .. 2022-12-31 · slippage 5.0 bps/side · Sleeve A at 100% of capital, no Sleeve H, no leverage.

Fewer slots = a bigger share of equity per position, so the same signals put more of the account to work. The cost is concentration and, on busy days, discarding real signals the liquidity ranking cannot fit.

| Config | Size each | Avg exposure | Days >90% | Days <10% | CAGR | maxDD | MC p95 DD | Sharpe | PF | Trades |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **slots10_baseline** | 10% | 58.5% | 38% | 18% | 18.37% | -30.2% | -17.1% | 1.18 | 1.35 | 9636 |
| slots8 | 12% | 62.1% | 43% | 14% | 22.47% | -35.2% | -17.4% | 1.33 | 1.4 | 8206 |
| slots6 | 17% | 66.4% | 50% | 13% | 22.13% | -36.8% | -20.1% | 1.22 | 1.36 | 6519 |
| slots5 | 20% | 68.8% | 54% | 14% | 24.63% | -30.4% | -19.2% | 1.32 | 1.39 | 5690 |
| slots4 | 25% | 71.4% | 58% | 14% | 23.14% | -42.7% | -22.6% | 1.14 | 1.35 | 4657 |
| slots3 | 33% | 74.6% | 65% | 15% | 25.22% | -36.4% | -22.5% | 1.17 | 1.37 | 3652 |
| slots2 | 50% | 78.0% | 72% | 15% | 29.40% | -60.1% | -27.3% | 1.15 | 1.42 | 2590 |

Baseline (10 slots): exposure 58.5%, CAGR 18.37%, maxDD -30.2%, Sharpe 1.18.

**Read maxDD and MC p95 before CAGR.** Concentration raises return and drawdown together; a config is only better if return rises faster than the drawdown it buys. MC p95 is the more honest risk figure - maxDD is the single worst path that happened to occur, while MC p95 estimates what bad luck could plausibly deliver.

In-sample only. Pick by plateau, then confirm once:

```
python -m backtest.phase3_sleeve_a --stage oos --confirm <label>
```
