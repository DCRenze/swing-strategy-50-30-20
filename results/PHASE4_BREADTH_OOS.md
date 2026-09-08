# Phase 4 breadth sweep - out-of-sample results

Window 2023-01-01 -> present, 5.0 bps/side.
Sleeve A fixed at `three_lower_lows[stretch0.75,sma200]`; deployed 60/40 A/H blend.

Pre-registration and pass/kill criteria: `BREADTH_HYPOTHESIS.md`.

`baseline` = the deployed H config (no breadth gate). Every other row changes
only `min_same_day_signals`; no exit, stop, lookback, slot count or ranking moves.

| Config | H PF | H win% | H Sharpe | H maxDD | H trades | H expo | Ens CAGR | Ens Sharpe | Ens maxDD | corrW |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | 1.41 | 48.4% | 1.01 | -18.7% | 624 | 0.77 | 15.58% | 1.09 | -15.5% | 0.385 |
| breadth2 | 1.44 | 48.6% | 1.06 | -20.6% | 622 | 0.77 | 16.19% | 1.13 | -16.3% | 0.378 |
| breadth5 | 1.36 | 48.8% | 0.86 | -23.5% | 605 | 0.75 | 14.26% | 1.0 | -17.6% | 0.404 |

## Read this before drawing a conclusion

**Profit factor rising while ensemble CAGR falls is the expected shape, not a win.**
A breadth gate removes sessions, so it removes trades and idles capital. The retained
trades have to be enough better to pay for the lost compounding. Criterion 3 in the
pre-registration (ensemble Sharpe) is the one that decides, not H's profit factor.

**A threshold that works with worse neighbours on both sides is an artifact.** The
Phase 2 finalists both showed clean in-sample plateaus and still flipped sign out of
sample; a lone in-sample spike is weaker evidence than that, not stronger.

## OOS confirmation

Baseline OOS: PF 1.41, ensemble Sharpe 1.09, ensemble maxDD -15.5%.

OOS is spent. Any further iteration on these numbers invalidates the window.
