# Gauntlet Summary

Windows: full 2005-06-01+, IS ends 2022-12-31, OOS starts 2023-01-01. Slippage 5.0 bps/side.

| Strategy | OOS PF | OOS Sharpe | OOS MaxDD | OOS SPY Sharpe | Full trades | Full CAGR | Full MaxDD | MC p95 DD | PASS |
|---|---|---|---|---|---|---|---|---|---|
| rsi2_pullback | 1.12 | 0.49 | -0.1811 | 1.43 | 9445 | 0.0996 | -0.5014 | -0.2556 | fail |
| three_lower_lows | 1.13 | 0.69 | -0.1223 | 1.43 | 14546 | 0.179 | -0.2535 | -0.1962 | fail |
| band_ibs | 1.04 | 0.25 | -0.2561 | 1.43 | 17745 | 0.1084 | -0.4101 | -0.3583 | fail |
| double7 | 1.23 | 0.68 | -0.1575 | 1.43 | 4955 | 0.074 | -0.2485 | -0.2217 | fail |
| momentum_burst | 1.1 | 0.49 | -0.4114 | 1.43 | 8738 | 0.0691 | -0.7057 | -0.4335 | fail |
| high52_breakout | 1.49 | 1.19 | -0.236 | 1.43 | 3248 | 0.0912 | -0.4524 | -0.2984 | fail |
| turnaround_tuesday | 1.19 | 0.82 | -0.1622 | 1.43 | 9468 | 0.0927 | -0.3575 | -0.2717 | fail |
| turn_of_month | 1.63 | 0.89 | -0.2575 | 1.43 | 2511 | 0.1011 | -0.2575 | -0.2092 | fail |
| range_reversion | 1.07 | 0.33 | -0.2795 | 1.43 | 11399 | 0.0616 | -0.2951 | -0.2453 | fail |

Per-strategy details: `gauntlet_<strategy>.json` (windows, variants, regimes, pass bar).