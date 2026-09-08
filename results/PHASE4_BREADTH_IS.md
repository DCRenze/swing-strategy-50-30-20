# Phase 4 breadth sweep - in-sample results

Window 2005-06-01 -> 2022-12-31, 5.0 bps/side.
Sleeve A fixed at `three_lower_lows[stretch0.75,sma200]`; deployed 60/40 A/H blend.

Pre-registration and pass/kill criteria: `BREADTH_HYPOTHESIS.md`.

`baseline` = the deployed H config (no breadth gate). Every other row changes
only `min_same_day_signals`; no exit, stop, lookback, slot count or ranking moves.

| Config | H PF | H win% | H Sharpe | H maxDD | H trades | H expo | Ens CAGR | Ens Sharpe | Ens maxDD | corrW |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | 1.15 | 48.7% | 0.32 | -44.0% | 2520 | 0.70 | 13.37% | 0.97 | -20.0% | 0.441 |
| breadth2 | 1.22 | 49.6% | 0.43 | -43.6% | 2487 | 0.69 | 14.40% | 1.04 | -19.1% | 0.437 |
| breadth5 | 1.19 | 50.7% | 0.37 | -45.5% | 2395 | 0.67 | 13.83% | 1.01 | -19.2% | 0.432 |
| breadth8 | 1.1 | 49.7% | 0.22 | -48.3% | 2286 | 0.64 | 12.43% | 0.94 | -24.2% | 0.412 |
| breadth12 | 1.17 | 49.6% | 0.32 | -48.9% | 2024 | 0.56 | 13.07% | 1.03 | -23.2% | 0.389 |
| breadth16 | 1.14 | 47.7% | 0.3 | -27.7% | 1808 | 0.51 | 12.38% | 1.04 | -25.6% | 0.381 |
| breadth20 | 1.16 | 48.7% | 0.32 | -24.5% | 1563 | 0.44 | 12.36% | 1.07 | -24.0% | 0.357 |
| breadth25 | 1.09 | 48.3% | 0.18 | -26.2% | 1286 | 0.36 | 11.57% | 1.03 | -26.9% | 0.339 |

## Read this before drawing a conclusion

**Profit factor rising while ensemble CAGR falls is the expected shape, not a win.**
A breadth gate removes sessions, so it removes trades and idles capital. The retained
trades have to be enough better to pay for the lost compounding. Criterion 3 in the
pre-registration (ensemble Sharpe) is the one that decides, not H's profit factor.

**A threshold that works with worse neighbours on both sides is an artifact.** The
Phase 2 finalists both showed clean in-sample plateaus and still flipped sign out of
sample; a lone in-sample spike is weaker evidence than that, not stronger.
