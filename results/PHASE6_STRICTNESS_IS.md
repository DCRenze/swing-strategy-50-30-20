# Phase 6 strictness sweep - in-sample results

Window 2005-06-01 -> 2022-12-31, 5.0 bps/side.
Sleeve H fixed at `high52_breakout[252,15d,stop5%]`; deployed 60/40 A/H blend.

Pre-registration and pass/kill criteria: `STRICTNESS_HYPOTHESIS.md`.

`baseline` = the deployed A config (no extra confirmation). Every other row adds
entry filters only; no exit, stretch, trend SMA or slot count moves.

| Config | A win% | A PF | A CAGR | A maxDD | A trades | A expo | Ens CAGR | Ens Sharpe | Ens maxDD | corrW |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **baseline** | 61.3% | 1.35 | 18.34% | -36.5% | 9607 | 0.58 | 13.37% | 0.97 | -20.0% | 0.441 |
| rsi5 | 62.6% | 1.47 | 11.56% | -18.3% | 4668 | 0.28 | 9.38% | 0.84 | -16.3% | 0.335 |
| ibs0.2 | 62.2% | 1.4 | 10.76% | -15.5% | 5116 | 0.31 | 8.89% | 0.78 | -18.0% | 0.381 |
| bband | 63.2% | 1.51 | 8.83% | -14.1% | 3265 | 0.19 | 7.75% | 0.73 | -15.9% | 0.304 |
| trend10 | 61.9% | 1.37 | 14.05% | -25.3% | 6747 | 0.41 | 10.84% | 0.86 | -24.8% | 0.439 |
| ll4 | 62.1% | 1.37 | 12.51% | -25.6% | 6512 | 0.39 | 9.95% | 0.82 | -21.5% | 0.407 |
| ll5 | 63.3% | 1.47 | 9.37% | -22.7% | 3826 | 0.23 | 8.07% | 0.77 | -17.4% | 0.309 |
| rsi5+ibs | 62.3% | 1.46 | 7.06% | -12.6% | 2884 | 0.17 | 6.69% | 0.68 | -16.8% | 0.286 |
| rsi5+ibs+bb | 64.3% | 1.73 | 5.49% | -10.2% | 1543 | 0.09 | 5.73% | 0.63 | -16.1% | 0.225 |
| rsi5+ibs+bb+ll4 | 63.9% | 1.75 | 3.77% | -7.1% | 1059 | 0.06 | 4.68% | 0.55 | -16.4% | 0.191 |
| everything | 67.2% | 1.88 | 1.55% | -5.2% | 344 | 0.02 | 3.34% | 0.42 | -16.4% | 0.127 |

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
