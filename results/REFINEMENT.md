# Refinement Round (IS-selected configs, single OOS confirmation each)

Slippage 5.0 bps/side. IS ends 2022-12-31; OOS starts 2023-01-01.

| Config | IS Sharpe | IS PF | OOS Sharpe | OOS PF | OOS MaxDD | Full CAGR | Full Sharpe | MC p95 DD |
|---|---|---|---|---|---|---|---|---|
| 3ll_refined | 1.16 | 1.34 | 0.98 | 1.21 | -0.1331 | 0.1703 | 1.13 | -0.1808 |
| 3ll_nostop | 1.18 | 1.35 | 0.78 | 1.16 | -0.1431 | 0.1693 | 1.11 | -0.1775 |
| tom_exit1 | 0.59 | 1.5 | 0.59 | 1.37 | -0.2761 | 0.0735 | 0.58 | -0.1894 |
| double7_lb10 | 0.7 | 1.31 | 0.57 | 1.21 | -0.1438 | 0.09 | 0.67 | -0.2146 |
| tt_bear | 0.55 | 1.39 | 0.78 | 1.88 | -0.0417 | 0.067 | 0.54 | -0.1967 |
| h52_fast_regime | 0.32 | 1.15 | 1.01 | 1.41 | -0.187 | 0.0741 | 0.44 | -0.2996 |

**Deployed ensemble** (3ll_refined 60%, h52_fast_regime 40%): IS Sharpe 0.96, OOS Sharpe 1.21, full CAGR 0.1377, full MaxDD -0.207, MC p95 DD -0.1689

**Legacy ensemble (for comparison)** (3ll_refined 50%, tom_exit1 30%, tt_bear 20%): IS Sharpe 1.19, OOS Sharpe 1.13, full CAGR 0.125, full MaxDD -0.1796, MC p95 DD -0.1179

Slippage sensitivity (3ll_refined, full window): 0bps: CAGR 0.2378, Sharpe 1.51, 5bps: CAGR 0.1703, Sharpe 1.13, 10bps: CAGR 0.1068, Sharpe 0.76, 20bps: CAGR -0.01, Sharpe 0.01