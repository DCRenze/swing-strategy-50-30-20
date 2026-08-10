# Gauntlet Summary

Windows: full 2005-06-01+, IS ends 2022-12-31, OOS starts 2023-01-01. Slippage 5.0 bps/side.

| Strategy | OOS PF | OOS Sharpe | OOS MaxDD | OOS SPY Sharpe | Full trades | Full CAGR | Full MaxDD | MC p95 DD | PASS |
|---|---|---|---|---|---|---|---|---|---|
| band_ibs | 1.04 | 0.25 | -0.2561 | 1.43 | 17745 | 0.1084 | -0.4101 | -0.3583 | fail |
| double7 | 1.23 | 0.68 | -0.1575 | 1.43 | 4955 | 0.074 | -0.2485 | -0.2217 | fail |
| high52_breakout | 1.49 | 1.19 | -0.236 | 1.43 | 3248 | 0.0912 | -0.4524 | -0.2984 | fail |
| high52_combo | 1.27 | 0.61 | -0.186 | 1.47 | 2933 | 0.0661 | -0.2957 | -0.2598 | fail |
| high52_deployed | 1.39 | 0.98 | -0.2014 | 1.47 | 3147 | 0.0753 | -0.4464 | -0.2936 | fail |
| high52_hold_sma20 | 1.2 | 0.43 | -0.1971 | 1.47 | 2167 | 0.0819 | -0.2414 | -0.2569 | fail |
| high52_trail_atr | 1.17 | 0.51 | -0.2213 | 1.47 | 3789 | 0.0866 | -0.3797 | -0.2718 | fail |
| momentum_burst | 1.1 | 0.49 | -0.4114 | 1.43 | 8738 | 0.0691 | -0.7057 | -0.4335 | fail |
| range_reversion | 1.07 | 0.33 | -0.2795 | 1.43 | 11399 | 0.0616 | -0.2951 | -0.2453 | fail |
| rsi2_pullback | 1.12 | 0.49 | -0.1811 | 1.43 | 9445 | 0.0996 | -0.5014 | -0.2556 | fail |
| three_lower_lows | 1.13 | 0.69 | -0.1223 | 1.43 | 14546 | 0.179 | -0.2535 | -0.1962 | fail |
| turn_of_month | 1.63 | 0.89 | -0.2575 | 1.43 | 2511 | 0.1011 | -0.2575 | -0.2092 | fail |
| turnaround_tuesday | 1.19 | 0.82 | -0.1622 | 1.43 | 9468 | 0.0927 | -0.3575 | -0.2717 | fail |

Per-strategy details: `gauntlet_<strategy>.json` (windows, variants, regimes, pass bar).