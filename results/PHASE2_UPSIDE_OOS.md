# Phase 2 - Sleeve H upside management (OOS confirmation)

Window 2023-01-01 .. present · slippage 5.0 bps/side · Sleeve A fixed at `three_lower_lows[stretch0.75,sma200]` · ensemble = 60/40 A/H daily-return split.

Deltas are versus the validated baseline. A variant must improve **both** the sleeve and the ensemble to be worth carrying forward.

| Variant | H PF | H Sharpe | H maxDD | H trades | H hold | Ens Sharpe | Ens maxDD | ΔEns Sharpe | corr(A,H) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | 1.39 | 0.99 | -20.1% | 623 | 11.1d | 1.2 | -16.2% | +0.00 | 0.384 |
| trail_atr1.5 | 1.15 | 0.47 | -22.1% | 767 | 8.7d | 0.88 | -17.2% | -0.32 | 0.381 |
| hold_sma20_max60 | 1.2 | 0.42 | -19.7% | 459 | 15.7d | 0.85 | -16.0% | -0.35 | 0.408 |

Baseline reference: H PF 1.39, Sharpe 0.99, maxDD -20.1%; ensemble Sharpe 1.2, maxDD -16.2%, corr(A,H) 0.384.

corr(A,H) is 1%-winsorized. Raw Pearson on daily returns is unusable for comparing variants here - the baseline H curve contains a +34% and a -24% session, and whether one such day survives swings Pearson between 0.26 and 0.41 across neighbouring parameters. Both figures are in the JSON. ⚠ marks a variant whose winsorized correlation runs 25% above baseline, i.e. one buying its ensemble gain by making H behave more like A.

## Decision

One confirmation, no iteration. A variant ships only if it improves the ensemble here as it did in-sample; anything that only worked in-sample is discarded, and the baseline stands.
