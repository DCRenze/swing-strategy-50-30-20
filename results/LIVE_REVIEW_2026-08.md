# Live review — 60/40 A/H book, 2026-07-01 → 2026-08-07

**The live loss is not evidence about the strategy. Replaying the same 41 trades under
the corrected exit rules turns −$1,635 into +$2,058.**

## The record

| | |
|---|--:|
| Equity | $97,190 |
| High-water mark | $100,433 |
| Return vs $100k start | **−2.81%** |
| SPY, same window | **+3.55%** |
| Realised P&L (41 closed) | −$1,635 |
| Unrealised (14 open) | −$745 |

| Sleeve | Closed | Net | Win rate | Profit factor |
|---|--:|--:|--:|--:|
| A | 31 | −$583 | 48.4% | 0.80 |
| H | 10 | −$1,052 | 20.0% | 0.44 |

## Cause 1 — the in-progress-bar defect (~$3,693)

The book ran for five weeks on exit rules that read a live intraday tick instead of a
completed daily close (see `PHASE2_CONCLUSION.md` context and the Phase 0 commit). Holding
entries fixed and replaying only the exits under the corrected rules:

| Sleeve | Actual | Corrected exits | Delta |
|---|--:|--:|--:|
| A | −$583 | +$2,524 | **+$3,107** |
| H | −$1,052 | −$466 | **+$586** |
| **Total** | **−$1,635** | **+$2,058** | **+$3,693** |

Robustness: **31 of 41 trades (76%) improved**, median +$76/trade, and excluding the three
largest contributors it is still +$2,301. This is not one lucky trade.

**The mechanism is systematic and it is worst for Sleeve A specifically.** On 2026-07-29
the market fell (SPY −1.54%, QQQ −2.04%) and Sleeve A bought the dip — AMAT, CAT, KLAC,
NXPI, ON all entered that day. On 07-30 the market rallied hard (SPY +1.68%, QQQ +3.30%)
and the buggy rule sold them **at that morning's open**, capturing only the overnight gap.
The correct rule waits for a completed up-close and sells the following open, capturing the
whole rally. For a dip-buyer, selling into the first tick of the bounce is precisely the
worst possible error: the strategy did its job, and the implementation cut the trade short
at the moment it started to pay.

AMAT is the clearest case: sold for +$493 on 07-30, worth +$1,205 under the correct rule.

## Cause 2 — execution lands ~4 minutes after the open (~$795)

The backtest fills at the official opening print. Live, the workflow fires at ~9:32, spends
~2 minutes downloading ~1,000 tickers, and submits around 9:34. Measured against each day's
official open:

| Exit execution | n | Mean | Median | Worst |
|---|--:|--:|--:|--:|
| Sleeve A | 31 | −19.1 bps | −15.5 bps | −369 bps |
| Sleeve H | 10 | −104.2 bps | −51.6 bps | −433 bps |

Dollar cost of that timing gap: **A −$391, H −$404, total −$795** over five weeks. Entry
side is consistent — H entries averaged **+12.2 bps** against the open, with a −612 to +500
bps spread.

Some of H's −104 bps is selection rather than pure slippage: H exits cluster on stop-outs,
and a stock triggering a stop often keeps falling in the first minutes. But the direction
and the size are real, and the backtest models none of it — it assumes 5 bps/side.

This matters disproportionately because Sleeve A's edge is cost-fragile: at 5 bps its CAGR
is 18.4%, at 12 bps it is 9.6%, at 20 bps it is zero (`PHASE3_CONCLUSION.md`).

Note the two causes overlap — the $3,693 counterfactual assumes perfect fills at the open,
so the $795 sits inside it. Roughly $2,900 is the wrong exit day and $795 is the late fill.

## The improvement this points to

**Move the signal computation to before the open.** Since Phase 0, every rule in the system
reads only the last *completed* session — nothing in the morning run needs today's data:

- entry signals → last completed close
- exit rules → last completed close
- day counting → today's calendar date, known in advance
- only the equity read, the drawdown gate and order submission need to be live

So the ~2-minute data refresh no longer has to happen after the bell. Computing signals the
prior evening and submitting at 9:30:00 would recover most of the $795, and it is a
*fidelity* change rather than a strategy change — it moves live execution toward the
backtest's assumption instead of away from it. No validated parameter moves.

Second, cheaper win: **bound the tail with marketable limit orders** rather than pure market
orders. The worst single exits ran −369 bps (A) and −433 bps (H). A limit a defined distance
through the touch caps that without materially reducing fill rates in names this liquid.

## What this review does not show

Five weeks and 41 trades prove nothing either way. Corrected, the book would have made
roughly +2% over a period when SPY made +3.55% — still behind, and still meaningless at this
sample size. Sleeve H's 0.44 profit factor is far below its 1.37 OOS benchmark, but
PLAYBOOK §8 sets the decay trigger at six rolling months below 1.0 for good reason, and
seven of H's ten exits ran on the defective stop.

**The decay clock should re-baseline from the Phase 0 fix date.** Everything before it
measures a different rule.

## Ranked next steps

1. **Pre-open signal computation** — worth ~$795/5 weeks on this sample, no strategy change.
2. **Phase 1 verification harness** — the defect ran five weeks undetected and cost ~3.7% of
   the account. Nothing else compares on expected value.
3. **Marketable limit orders on exits** — caps the −400 bps tail.
4. **Entry clustering (G2)** — H filled all ten slots on a single day twice (07-01, 08-06),
   with visible sector concentration. Untested.

Already tested and rejected, do not revisit without a fresh hypothesis: upside management
(`PHASE2_CONCLUSION.md`), slot concentration (`PHASE3_CONCLUSION.md`).
