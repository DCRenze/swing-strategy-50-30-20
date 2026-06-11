# Refinement Round (IS-selected configs, single OOS confirmation each)

Slippage 5.0 bps/side. IS ends 2022-12-31; OOS starts 2023-01-01.

| Config | IS Sharpe | IS PF | OOS Sharpe | OOS PF | OOS MaxDD | Full CAGR | Full Sharpe | MC p95 DD |
|---|---|---|---|---|---|---|---|---|
| 3ll_refined | 1.13 | 1.33 | 0.93 | 1.19 | -0.1507 | 0.167 | 1.1 | -0.1842 |
| tom_exit1 | 0.59 | 1.5 | 0.57 | 1.33 | -0.2761 | 0.0719 | 0.58 | -0.1875 |
| double7_lb10 | 0.65 | 1.29 | 0.59 | 1.21 | -0.1438 | 0.0848 | 0.64 | -0.215 |
| tt_bear | 0.56 | 1.4 | 0.81 | 1.88 | -0.0417 | 0.0688 | 0.55 | -0.1947 |
| h52_fast_regime | 0.33 | 1.16 | 0.98 | 1.37 | -0.1986 | 0.0754 | 0.45 | -0.2834 |

**Ensemble** (3ll_refined 50%, tom_exit1 30%, tt_bear 20%): IS Sharpe 1.18, OOS Sharpe 1.08, full CAGR 0.1232, full MaxDD -0.1653, MC p95 DD -0.1193

Slippage sensitivity (3ll_refined, full window): 0bps: CAGR 0.235, Sharpe 1.48, 5bps: CAGR 0.167, Sharpe 1.1, 10bps: CAGR 0.1027, Sharpe 0.72, 20bps: CAGR -0.0154, Sharpe -0.03