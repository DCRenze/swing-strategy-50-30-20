# Phase 3 - Sleeve-A-only capital utilisation (OOS confirmation)

Window 2023-01-01 .. present · slippage 5.0 bps/side · Sleeve A at 100% of capital, no Sleeve H, no leverage.

Fewer slots = a bigger share of equity per position, so the same signals put more of the account to work. The cost is concentration and, on busy days, discarding real signals the liquidity ranking cannot fit.

| Config | Size each | Avg exposure | Days >90% | Days <10% | CAGR | maxDD | MC p95 DD | Sharpe | PF | Trades |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **slots10_baseline** | 10% | 70.3% | 51% | 12% | 14.22% | -14.6% | -10.0% | 0.98 | 1.21 | 2297 |
| slots8 | 12% | 72.9% | 57% | 10% | 12.23% | -15.0% | -11.4% | 0.8 | 1.17 | 1906 |
| slots5 | 20% | 78.3% | 67% | 10% | 14.46% | -16.7% | -13.3% | 0.81 | 1.19 | 1302 |
| slots2 | 50% | 84.3% | 82% | 12% | 25.36% | -25.0% | -16.8% | 1.03 | 1.33 | 563 |

Baseline (10 slots): exposure 70.3%, CAGR 14.22%, maxDD -14.6%, Sharpe 0.98.

**Read maxDD and MC p95 before CAGR.** Concentration raises return and drawdown together; a config is only better if return rises faster than the drawdown it buys. MC p95 is the more honest risk figure - maxDD is the single worst path that happened to occur, while MC p95 estimates what bad luck could plausibly deliver.
