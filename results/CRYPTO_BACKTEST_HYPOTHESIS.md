# Crypto backtest pre-registration — the deployed config, unchanged, on crypto

**Written before any crypto backtest was run. Criteria fixed at authoring time.**

## The question David asked

> "why did you use the strict filters? Just use what we're doing now. For backtest,
> make the range 3 years from now"

Two things. First, a correction: `CRYPTO_FEASIBILITY.md` did **not** use Phase 6's
strict filters. Its 127-setups-a-year figure is the deployed Sleeve A rule exactly as
it runs today. Phase 6's filters appeared only as a one-line comparison. The chat
summary implied otherwise and was wrong.

Second, the instruction: run the backtest anyway, over the last three years.
`CRYPTO_FEASIBILITY.md` declined to, arguing the window cannot support a verdict.
David has read that and asked for the number regardless. That is his call, so this
phase runs it — pre-registered first, as PLAYBOOK discipline requires.

## What is being run

**The deployed configuration, unmodified.** No new filters, no tuning, no parameter
search. Sleeve A from `backtest/strategies/three_lower_lows.py` with
`refine.py`'s `3ll_refined` parameters, which are what `playbook/screener.py` runs:

| Parameter | Value | Source |
|---|---|---|
| `stretch` | 0.75 (limit = close − 0.75×ATR10) | `screener.A_STRETCH` |
| `trend_sma` | 200 | `screener.A_TREND_SMA` |
| `min_dollar_vol` | $10M, 20-day average | `screener.A_MIN_DOLLAR_VOL` |
| `time_stop` | 15 | `screener.A_TIME_STOP` |
| `max_positions` | 10 | `screener.SLEEVES` |
| stop loss | none | PLAYBOOK §2 |
| exit | first up close → sell next open | PLAYBOOK §2 |

Sleeve H is run alongside at its deployed parameters (252-day high, volume > 50-day
average, 5% stop, 15-day stop, 126-day momentum ranking, $20M ADV).

**Window: 2023-09-14 → 2026-09-14** (three years to today), with data loaded from
2022-01 so the 200-day and 252-day lookbacks are warm at the start.

**Universe:** the 19 non-stablecoin USD-quoted spot pairs on Alpaca's supported list.

## Two deliberate adaptations, declared now

Neither is a tuning choice, and both are reported both ways where it is possible to
do so.

1. **`min_price = $1` is dropped** (run at $0). In equities this is a penny-stock
   filter. In crypto the price level is an arbitrary unit convention — SHIB trades
   near $0.00001 and DOGE near $0.20 without being "cheap" in any meaningful sense.
   Keeping it would silently delete names for no economic reason. **The $1 filter is
   also run as a sensitivity** so the effect is visible.

2. **Sleeve H's `SPY > SMA(100)` gate becomes `BTC > SMA(100)`.** H's gate is a
   market-health switch; the crypto market's is not SPY. There is no non-arbitrary
   choice here, which is itself worth noting — this is the one place a judgment call
   is unavoidable, and it is a judgment call about a sleeve whose crypto version has
   never been validated.

Everything else in the strategy modules and in `backtest/engine.py` is untouched.
`engine.py` needs no change: `CRYPTO_FEASIBILITY.md` verified it indexes by row, not
by session.

One plumbing detail, not a rule change: Yahoo reports crypto `Volume` already in USD,
while `indicators.liquidity_mask` expects share counts and multiplies by price. The
panel is therefore built with `volume = usd_volume / close`, so the existing
liquidity screen computes the correct dollar figure against unmodified code.

## Benchmarks — the number is meaningless without them

The last three years were a crypto bull market. Any long-only crypto strategy will
show a positive return. The only interesting question is whether it beats **holding
the asset**, so the comparison set is fixed now:

- **BTC buy-and-hold** over the identical window.
- **Equal-weight buy-and-hold** of the same 19 pairs, rebalanced never.
- **Sleeve A on US equities** over the identical window, as the incumbent.

## Costs — three settings, fixed now

`PHASE3_CONCLUSION.md` established Sleeve A is cost-fragile. Crypto costs are higher
and, unlike equities, have a hard floor because Alpaca charges a maker fee even on a
resting limit order:

| Setting | bps/side | What it represents |
|---|--:|---|
| `slip5` | 5 | the repo's modelled assumption, for comparability only |
| `slip15` | 15 | Alpaca base-tier **maker** fee — the floor if every A limit rests |
| `slip25` | 25 | Alpaca base-tier **taker** fee — realistic for exits and H entries |

**`slip15` is the headline.** Sleeve A places resting limit orders, so maker is the
right assumption for its entries; `slip25` is the honest stress case given exits are
market orders.

## Pass criteria (fixed now)

**Verdict A — does the deployed rule work at all on crypto?** Passes if, at `slip15`:

1. Profit factor > **1.3** (README's playbook bar).
2. At least **100 trades** in the window (README's bar).
3. Max drawdown better than **−25%** (README's bar).

**Verdict B — is it worth building?** Passes only if Verdict A passes **and**:

4. Sharpe ≥ **BTC buy-and-hold Sharpe** over the same window. A strategy that
   underperforms simply owning the asset is not a strategy.
5. CAGR remains **positive at `slip25`**.
6. Sharpe ≥ **Sleeve A's own equity OOS Sharpe of 0.98** (`PHASE3_CONCLUSION.md`).
   New sleeves must beat the incumbent, not merely make money.

## Kill criteria

- Fewer than 100 trades → untestable, per the README bar. Report and stop.
- Negative CAGR at `slip25` → the realistic-cost case is dead.
- Profit factor below 1.3 → below the bar every deployed sleeve had to clear.

## What no result here can establish

Fixed in advance so a good number cannot be over-read later:

1. **Survivorship.** The universe is Alpaca's list *as it stands today*, projected
   backwards. Every coin that died is absent by construction. Ammann et al. (SSRN
   4287573) put the annualised survivorship-and-delisting bias in equal-weighted
   crypto portfolios at 62%. This is not correctable with available data, and it
   biases the result **upward**.
2. **One regime.** 2023-09 → 2026-09 is a crypto bull market. `CRYPTO_FEASIBILITY.md`
   measured 40 qualifying setups in all of 2022, the last crypto bear — the rule is
   structurally switched off in downturns, so this window contains no test of what
   happens then.
3. **No in-sample/out-of-sample split.** Three years is one window. There is no
   held-out data, so nothing here is a confirmation of anything.
4. **The supply finding is unaffected either way.** 127 setups a year and a 10–21%
   exposure ceiling are properties of the universe, not of the returns. A good Sharpe
   on 15% exposure does not move them.

A passing result would therefore mean "worth a pre-registered second look with a
point-in-time universe," never "build it."

## What ships either way

Nothing in `playbook/screener.py` or `papertrade/run_daily.py`. No orders. This is a
measurement.

## Reproduce

```
python -m backtest.crypto_backtest
```
