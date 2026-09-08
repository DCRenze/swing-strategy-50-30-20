# Phase 5 volatility sweep - in-sample results

Window 2005-06-01 -> 2022-12-31, 5.0 bps/side.
Sleeve H fixed at `high52_breakout[252,15d,stop5%]`; deployed 60/40 A/H blend.

Pre-registration and pass/kill criteria: `VOLATILITY_HYPOTHESIS.md`.

`baseline` = the deployed A config (no calmness filter). Every other row changes
only `max_atr_pct`; no exit, stretch, trend SMA or slot count moves.

| Config | A win% | A PF | A CAGR | A maxDD | A trades | A expo | Ens CAGR | Ens Sharpe | Ens maxDD | corrW |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | 61.3% | 1.35 | 18.34% | -36.5% | 9607 | 0.58 | 13.37% | 0.97 | -20.0% | 0.441 |
| maxatr2.0 | 60.6% | 1.2 | 4.53% | -22.5% | 6089 | 0.37 | 5.11% | 0.52 | -18.7% | 0.414 |
| maxatr2.5 | 61.2% | 1.29 | 9.33% | -20.8% | 7709 | 0.47 | 7.98% | 0.73 | -19.5% | 0.456 |
| maxatr3.0 | 61.4% | 1.28 | 10.69% | -21.6% | 8469 | 0.52 | 8.79% | 0.77 | -20.8% | 0.477 |
| maxatr3.5 | 61.8% | 1.32 | 13.71% | -23.2% | 8971 | 0.54 | 10.59% | 0.88 | -21.3% | 0.468 |
| maxatr4.0 | 61.0% | 1.29 | 12.93% | -23.4% | 9155 | 0.56 | 10.14% | 0.81 | -20.8% | 0.476 |
| maxatr5.0 | 61.1% | 1.28 | 13.35% | -32.6% | 9336 | 0.57 | 10.41% | 0.81 | -23.7% | 0.47 |

## Read this before drawing a conclusion

**Win rate rising while ensemble CAGR falls is the expected shape, and it is the
whole question - not a win and not a failure.** Calm names win more often and pay
less per win, so a tighter cap should trade return for hit rate. The pre-registration
reports this as two verdicts: whether the win rate rises (Verdict A) and whether the
book is better off (Verdict B). Read the ensemble CAGR column next to the win-rate
column, not on its own.

**Exposure is the hidden cost.** A cap that discards most of the candidate pool leaves
a dip-buyer with nothing to buy; PHASE3_CONCLUSION.md established that idle capital
cannot be redeployed. Watch the A expo column fall as the cap tightens.
