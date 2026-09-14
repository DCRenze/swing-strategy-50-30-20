# Alpaca fractional-order constraints — measured, not assumed (2026-09-14)

Run against the **live paper account** via `paper-api.alpaca.markets`. Every order was placed
with the market closed and a stop price far from the market ($900 on AAPL), then cancelled
immediately. Account verified unchanged before and after: equity $97,159.15, 8 positions,
0 open orders, both sides.

## Results

| Test | Result |
|---|---|
| Fractional **stop** order, DAY | ✅ **ACCEPTED** (0.05 sh, status NEW) |
| Whole-share stop order, DAY (control) | ✅ ACCEPTED |
| Fractional **bracket** (entry + stop + target) | ❌ REJECTED — `fractional orders must be simple orders` |
| Whole-share bracket (control) | ✅ ACCEPTED |
| Fractional stop, **GTC** | ❌ REJECTED — `stop/stop_limit fractional GTC orders are not enabled` |

## What this corrects

`papertrade/run_daily.py`'s module docstring claimed market and limit were *"the only order
types Alpaca allows fractional quantities on."* **That was wrong.** Stop and stop-limit orders
accept fractional quantities. The docstring has been corrected.

The two constraints that *are* real:

1. **No brackets on fractional orders.** A stop cannot be attached to the entry. It must be a
   separate order placed after the position exists.
2. **DAY time-in-force only.** A fractional stop cannot be GTC, so it expires at every close
   and must be re-placed each morning.

## What it means for the book

**A resting broker-side stop is available** — placed each morning for each open position,
expiring at the close. That is a real capability the book does not currently use, and it
covers a real gap: right now nothing protects a position between 09:30 and 16:00, because the
rules are evaluated once pre-open.

**It does not cover overnight gaps**, which is where this book's worst losses came from:

- SRPT 2016-01-15: closed 31.63 → next close 14.28, and *opened* at 15.00 (−53% at the open).
- YETI (Sleeve H, Aug 2026): −13.9% against a nominal 5% stop.

A DAY stop is switched off during exactly those moves. Anything that sells at the open —
whether the current close-based rule or a resting stop that never got the chance to trigger —
fills at the same gapped price.

## The unsolved problem this does NOT fix

The bigger gap remains: **if the morning script does not run, nothing protects the book at
all.** A DAY-only stop expires the same afternoon, so it cannot serve as a standing safety net
across an outage — the very scenario it would be most wanted for. Covering that needs either
whole-share positions (GTC stops become available) or a second, independent process.

## Caveats on this measurement

- Order *acceptance* was tested, not *execution*. Whether a fractional stop actually triggers
  and fills as expected intraday is a separate question, untested here.
- Tested on AAPL only. Behaviour is not expected to vary by symbol among liquid names, but it
  was not checked across the universe.
- Paper account. Live-account behaviour is assumed identical but unverified.

## Reproducing

Keys are in the environment (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_ENDPOINT` →
`https://paper-api.alpaca.markets/v2`). Note `api.alpaca.markets` (the **live** endpoint) is
blocked by this environment's egress policy; `paper-api.alpaca.markets` and
`data.alpaca.markets` are reachable. An earlier session wrongly concluded from a failed probe
of the live endpoint that Alpaca was unreachable and that no credentials were present.
