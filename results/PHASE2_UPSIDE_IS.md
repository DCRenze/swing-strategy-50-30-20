# Phase 2 - Sleeve H upside management (in-sample)

Window 2005-06-01 .. 2022-12-31 · slippage 5.0 bps/side · Sleeve A fixed at `three_lower_lows[stretch0.75,sma200]` · ensemble = 60/40 A/H daily-return split.

Deltas are versus the validated baseline. A variant must improve **both** the sleeve and the ensemble to be worth carrying forward.

| Variant | H PF | H Sharpe | H maxDD | H trades | H hold | Ens Sharpe | Ens maxDD | ΔEns Sharpe | corr(A,H) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | 1.16 | 0.33 | -44.0% | 2524 | 11.9d | 0.97 | -23.3% | +0.00 | 0.452 |
| trail_atr1.0 | 1.2 | 0.4 | -28.7% | 3798 | 7.2d | 1.04 | -22.2% | +0.07 | 0.407 |
| trail_atr1.5 | 1.28 | 0.51 | -34.4% | 3022 | 9.6d | 1.09 | -22.1% | +0.12 | 0.435 |
| trail_atr2.0 | 1.27 | 0.49 | -30.1% | 2706 | 10.9d | 1.07 | -22.4% | +0.10 | 0.455 |
| trail_atr2.5 | 1.2 | 0.4 | -38.2% | 2588 | 11.6d | 1.01 | -23.5% | +0.04 | 0.455 |
| trail_atr3.0 | 1.18 | 0.37 | -47.1% | 2538 | 11.9d | 1.0 | -23.1% | +0.03 | 0.454 |
| giveback20 | 1.16 | 0.37 | -33.5% | 5808 | 4.3d | 1.02 | -22.0% | +0.05 | 0.401 |
| giveback33 | 1.18 | 0.37 | -25.9% | 5176 | 5.0d | 1.03 | -21.9% | +0.06 | 0.404 |
| giveback50 | 1.19 | 0.38 | -25.9% | 4597 | 5.8d | 1.02 | -22.1% | +0.05 | 0.41 |
| target10 | 1.21 | 0.57 | -24.8% | 2736 | 11.0d | 1.1 | -22.3% | +0.13 | 0.469 |
| target15 | 1.18 | 0.45 | -25.6% | 2595 | 11.6d | 1.04 | -22.1% | +0.07 | 0.476 |
| target20 | 1.18 | 0.46 | -27.3% | 2562 | 11.7d | 1.05 | -22.5% | +0.08 | 0.471 |
| target25 | 1.23 | 0.56 | -27.3% | 2520 | 12.0d | 1.1 | -22.5% | +0.13 | 0.47 |
| breakeven5 | 1.15 | 0.32 | -47.7% | 2559 | 11.7d | 0.97 | -22.5% | +0.00 | 0.455 |
| breakeven8 | 1.17 | 0.36 | -42.3% | 2524 | 11.9d | 0.99 | -23.3% | +0.02 | 0.454 |
| hold_sma20_max25 | 1.26 | 0.51 | -28.7% | 2013 | 15.4d | 1.08 | -22.3% | +0.11 | 0.461 |
| hold_sma20_max40 | 1.39 | 0.54 | -35.5% | 1780 | 17.6d | 1.1 | -21.7% | +0.13 | 0.443 |
| hold_sma20_max60 | 1.37 | 0.6 | -24.1% | 1708 | 18.4d | 1.12 | -21.7% | +0.15 | 0.46 |
| hold_sma20_max80 | 1.38 | 0.6 | -24.1% | 1700 | 18.6d | 1.12 | -21.8% | +0.15 | 0.459 |
| hold_sma20_nocap | 1.39 | 0.6 | -24.1% | 1692 | 18.6d | 1.12 | -21.8% | +0.15 | 0.46 |

Baseline reference: H PF 1.16, Sharpe 0.33, maxDD -44.0%; ensemble Sharpe 0.97, maxDD -23.3%, corr(A,H) 0.452.

corr(A,H) is 1%-winsorized. Raw Pearson on daily returns is unusable for comparing variants here - the baseline H curve contains a +34% and a -24% session, and whether one such day survives swings Pearson between 0.26 and 0.41 across neighbouring parameters. Both figures are in the JSON. ⚠ marks a variant whose winsorized correlation runs 25% above baseline, i.e. one buying its ensemble gain by making H behave more like A.

## Reading this

In-sample only - nothing here is evidence a rule works. Pick finalists by plateau (a whole neighbourhood of parameters improving, not one lucky cell), then spend the OOS window once:

```
python -m backtest.phase2_upside --stage oos --confirm <label> [<label> ...]
```

If no variant shows a plateau, the finding is that the flat 15-day hold is already right and Sleeve H keeps its current exits.
