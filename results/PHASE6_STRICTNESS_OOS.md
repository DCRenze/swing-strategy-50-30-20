# Phase 6 strictness sweep - out-of-sample results

Window 2023-01-01 -> present, 5.0 bps/side.
Sleeve H fixed at `high52_breakout[252,15d,stop5%]`; deployed 60/40 A/H blend.

Pre-registration and pass/kill criteria: `STRICTNESS_HYPOTHESIS.md`.

`baseline` = the deployed A config (no extra confirmation). Every other row adds
entry filters only; no exit, stretch, trend SMA or slot count moves.

| Config | A win% | A PF | A CAGR | A maxDD | A trades | A expo | Ens CAGR | Ens Sharpe | Ens maxDD | corrW |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | 60.1% | 1.16 | 10.67% | -14.3% | 2303 | 0.69 | 15.58% | 1.09 | -15.5% | 0.385 |
| rsi5 | 60.2% | 1.12 | 4.19% | -11.6% | 1238 | 0.37 | 11.45% | 0.97 | -11.1% | 0.302 |
| rsi5+ibs+bb | 60.4% | 1.21 | 2.30% | -6.6% | 371 | 0.11 | 10.25% | 1.03 | -8.6% | 0.186 |
| everything | 65.9% | 1.75 | 1.49% | -3.6% | 82 | 0.02 | 9.73% | 1.06 | -7.3% | 0.17 |

## Read this before drawing a conclusion

**Win rate rising while ensemble CAGR falls is the expected shape, and it is the
whole question - not a win and not a failure.** Calm names win more often and pay
less per win, so a tighter cap should trade return for hit rate. The pre-registration
reports this as two verdicts: whether the win rate rises (Verdict A) and whether the
book is better off (Verdict B). Read the ensemble CAGR column next to the win-rate
column, not on its own.

**Read the win-rate column NEXT TO the trades and exposure columns.** A filter that
keeps 1% of signals can post a flattering win rate on a handful of trades while the
account sits in cash. Win rate is a percentage; compounding needs occurrences.

## OOS confirmation

Baseline OOS: win rate 60.1%, PF 1.16, ensemble Sharpe 1.09, ensemble maxDD -15.5%.

OOS is spent. Any further iteration on these numbers invalidates the window.
