# Phase 3 conclusion — Sleeve-A-only capital utilisation

**Verdict: keep 10 slots. Going pure-A roughly doubles capital utilisation on its own;
squeezing further buys risk, not return. Nothing shipped — `screener.py` untouched.**

## The question

Live, Sleeve A appears to use only 20–30% of the account, so a lot of money looks idle.
Could a Sleeve-A-only book put more of it to work?

## First: where the idle cash actually comes from

Sleeve A run at **100% of capital** with its validated 10 slots already averages **60.5%
invested** over 2005–2026. The low live figure is an allocation effect, not a sizing
defect: A holds 60% of the account in the 60/40 book, so 60% × 60.5% ≈ **36%** of total
equity works on an average day.

So dropping Sleeve H recovers most of the gap by itself, before any sizing change.

The remaining cash is not waste. The exposure distribution is bimodal — **40.6% of
sessions are >90% invested, 17.1% are near-empty**. A dip-buyer needs dips; on days with
no setups, cash *is* the position. There is no leverage available (PLAYBOOK forbids
margin), so the only lever is concentration: fewer slots, bigger positions.

## Concentration raises exposure far less than expected

| Slots | Size each | Avg exposure (IS) | CAGR | maxDD | MC p95 DD | Sharpe |
|---|--:|--:|--:|--:|--:|--:|
| **10 (validated)** | 10% | **58.5%** | 18.37% | −30.2% | −17.1% | 1.18 |
| 8 | 12.5% | 62.1% | 22.47% | −35.2% | −17.4% | 1.33 |
| 6 | 16.7% | 66.4% | 22.13% | −36.8% | −20.1% | 1.22 |
| 5 | 20% | 68.8% | 24.63% | −30.4% | −19.2% | 1.32 |
| 4 | 25% | 71.4% | 23.14% | −42.7% | −22.6% | 1.14 |
| 3 | 33% | 74.6% | 25.22% | −36.4% | −22.5% | 1.17 |
| 2 | 50% | 78.0% | 29.40% | −60.1% | −27.3% | 1.15 |

Cutting slots from 10 to 2 — a fivefold increase in position size — lifts average exposure
only from 58.5% to 78%. **You cannot deploy capital that has nothing to buy.** Meanwhile
max drawdown doubles, from −30% to −60%.

Sharpe is jagged across the grid — 1.18, 1.33, 1.22, 1.32, 1.14, 1.17, 1.15. Adjacent
settings disagree with no mechanism to explain it. That is the same noise signature the
Phase 2 profit-target family showed, and it means concentration is a **risk dial, not an
edge**: return and drawdown rise together, and risk-adjusted return does not reliably
improve.

## Out-of-sample killed the in-sample picks

The two best in-sample Sharpes were 8 slots (1.33) and 5 slots (1.32):

| Config | IS Sharpe | OOS Sharpe | OOS CAGR | OOS maxDD |
|---|--:|--:|--:|--:|
| 10 slots (baseline) | 1.18 | **0.98** | 14.22% | −14.6% |
| 8 slots | 1.33 | 0.80 | 12.23% | −15.0% |
| 5 slots | 1.32 | 0.81 | 14.46% | −16.7% |
| 2 slots | 1.15 | 1.03 | 25.36% | −25.0% |

Both finalists underperformed the baseline out-of-sample. Same story as Phase 2: an
in-sample edge that does not persist.

**On 2 slots.** It looks excellent out-of-sample and it is not a candidate. It was never
an in-sample pick — it ranked sixth of seven on Sharpe — so its OOS figure is not a
confirmation of anything; it was run out of curiosity, which is peeking. Its in-sample
−60.1% max drawdown disqualifies it independently: a book that halves twice over is not
one anybody holds through, and the risk gate would have halted entries long before the
recovery.

## Trading costs dominate all of this

Sleeve A's edge is unusually cost-fragile, and it is worth seeing the whole grid:

| Slots | 0 bps | 5 bps *(modelled)* | 10 bps | 12 bps *(measured live)* | 20 bps |
|---|--:|--:|--:|--:|--:|
| 10 | 25.05% | **18.37%** | 12.04% | **9.61%** | 0.40% |
| 8 | 29.84% | 22.47% | 15.52% | 12.85% | 2.78% |
| 5 | 32.97% | 24.63% | 16.81% | 13.82% | 2.61% |
| 3 | 34.20% | 25.22% | 16.84% | 13.64% | 1.72% |
| 2 | 39.29% | 29.40% | 20.21% | 16.72% | 3.75% |

Fewer slots do help here — fewer trades, less friction, and the relative advantage widens
as costs rise. But the headline finding is the column, not the row: **at the 12 bps
actually measured on live fills, the baseline's 18.4% becomes 9.6%**, and at 20 bps every
configuration is worthless. Any expectation set from the 5 bps column is optimistic.

## And pure-A still loses to the current book out-of-sample

| Full window | CAGR | maxDD | Sharpe | | OOS 2023–2026 | CAGR | Sharpe |
|---|--:|--:|--:|---|---|--:|--:|
| Sleeve A alone | 16.70% | −29.3% | 1.10 | | Sleeve A alone | 14.22% | 0.98 |
| Deployed 60/40 | 13.64% | −24.9% | 0.99 | | Deployed 60/40 | **17.35%** | **1.16** |

Pure-A wins on the full window — where its parameters were chosen — and loses on the
untouched window, on both return and risk-adjusted return. That asymmetry is the case for
keeping Sleeve H.

## Recommendation

1. **Don't reduce slot count.** It is a leverage dial disguised as an efficiency gain, and
   the in-sample winners did not survive.
2. **If the goal is putting more capital to work,** dropping Sleeve H does it (≈36% → ≈60%
   average utilisation) — but costs 3 points of OOS return and 0.18 of OOS Sharpe. That is
   a real price for the utilisation.
3. **The more promising thread is the A/H weight**, not the slot count: A alone beats 60/40
   on the full window, so a 70/30 or 80/20 tilt may dominate without abandoning
   diversification. Untested.
4. **Before any of this, measure real slippage.** Every number here moves more with the
   cost assumption than with any parameter in the sweep. That is Phase 1 work.

## Reproduce

```
python -m backtest.phase3_sleeve_a --stage is
python -m backtest.phase3_sleeve_a --stage oos --confirm slots8 slots5
```
