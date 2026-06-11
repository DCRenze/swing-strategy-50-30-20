"""Daily signal screener for the validated 50/30/20 ensemble.

Produces today's orders for the three sleeves:
  A. three_lower_lows  (50%) - next-day limit buys + exit checks
  B. turn_of_month     (30%) - calendar MOC entries/exits
  C. tt_bear           (20%) - Monday-weakness MOC buys when SPY < SMA200

Usage (from the project root, venv python):
  python -m playbook.screener --refresh     # download fresh bars first (1-2 min)
  python -m playbook.screener               # use cached bars
  python -m playbook.screener --equity 100000 --json signals.json

Data: downloads its own ~450-calendar-day window to data/recent_*.parquet
(does not touch the research panel). Run --refresh after each market close,
or intraday near the close for the MOC sleeves (today's partial bar then
stands in for the close - acceptable within ~15 min of 4pm ET).

The screener is STATELESS about positions: it emits entry signals and the
exit RULES; whoever executes (human or agent) checks open positions against
the exit rules printed per sleeve. The papertrade runner automates that.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest.indicators import atr, dollar_volume, ibs, sma  # noqa: E402

DATA_DIR = ROOT / "data"
RECENT_PREFIX = "recent_"
LOOKBACK_CAL_DAYS = 450

# ---- ensemble parameters (validated in Phase 4 - do not change casually; ----
# ---- any change invalidates the backtest evidence in results/ ) ----
SLEEVES = {
    "A_three_lower_lows": {"weight": 0.50, "max_positions": 10},
    "B_turn_of_month": {"weight": 0.30, "max_positions": 10},
    "C_tt_bear": {"weight": 0.20, "max_positions": 10},
}
A_STRETCH = 0.75          # limit = close - 0.75 * ATR(10)
A_TREND_SMA = 200
A_MIN_DOLLAR_VOL = 10e6
A_MIN_PRICE = 1.0
A_TIME_STOP = 15
B_ENTRY_DAYS_BEFORE_EOM = 5   # buy close of 5th-last trading day of month
B_EXIT_DAY_OF_MONTH = 1       # sell close of 1st trading day of new month
B_TOP_N = 100
C_IBS_MAX = 0.5
C_TIME_STOP = 4

# Dual-listed share classes: map secondary -> primary so one company never
# occupies two position slots. (Backtest did not dedupe; this only reduces
# concentration, it does not change entry/exit rules.)
SHARE_CLASS_MAP = {"GOOG": "GOOGL", "FOXA": "FOX", "NWSA": "NWS", "UAA": "UA"}

# US market holidays (NYSE) for month-end calendar math; extend yearly.
US_MARKET_HOLIDAYS = [
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
]


def refresh_data() -> None:
    import yfinance as yf

    uni = pd.read_csv(DATA_DIR / "universe.csv")
    tickers = sorted(set(uni["ticker"]) | {"SPY", "QQQ", "^VIX"})
    start = (dt.date.today() - dt.timedelta(days=LOOKBACK_CAL_DAYS)).isoformat()
    print(f"Refreshing {len(tickers)} tickers from {start}...", flush=True)
    fields = {"Open": "raw_open", "High": "raw_high", "Low": "raw_low",
              "Close": "raw_close", "Adj Close": "adj_close", "Volume": "volume"}
    parts: dict[str, list] = {f: [] for f in fields}
    for i in range(0, len(tickers), 100):
        batch = tickers[i : i + 100]
        df = yf.download(batch, start=start, auto_adjust=False, actions=False,
                         group_by="column", threads=True, progress=False)
        if df is None or df.empty:
            continue
        if not isinstance(df.columns, pd.MultiIndex):
            df.columns = pd.MultiIndex.from_product([df.columns, batch])
        for f in fields:
            if f in df.columns.get_level_values(0):
                parts[f].append(df[f])
        print(f"  batch {i // 100 + 1}/{-(-len(tickers) // 100)}", flush=True)
    for f, name in fields.items():
        wide = pd.concat(parts[f], axis=1, sort=True)
        wide = wide.loc[:, ~wide.columns.duplicated()].sort_index().dropna(axis=1, how="all")
        wide.index = pd.to_datetime(wide.index)
        wide.to_parquet(DATA_DIR / f"{RECENT_PREFIX}{name}.parquet")
    print("Refresh complete.")


def load_recent_panel(min_coverage: float = 0.5) -> dict:
    """Load the recent panel, trimming trailing sessions with sparse data.

    yfinance often returns today's row before most tickers' daily bars are
    populated (NaN for ~all names). Acting on that row would zero out every
    signal, so we cut back to the last session where >= min_coverage of
    tickers have a close.
    """
    names = ["raw_open", "raw_high", "raw_low", "raw_close", "adj_close", "volume"]
    raw = {n: pd.read_parquet(DATA_DIR / f"{RECENT_PREFIX}{n}.parquet") for n in names}
    coverage = raw["adj_close"].notna().mean(axis=1)
    good_rows = coverage[coverage >= min_coverage].index
    if good_rows.empty:
        raise SystemExit("No session has adequate data coverage - refresh failed?")
    dropped = coverage.index.difference(good_rows)
    if len(dropped):
        print(f"NOTE: dropping {len(dropped)} sparse session(s) "
              f"({', '.join(str(d.date()) for d in dropped[:5])}); "
              f"acting as of {good_rows[-1].date()}")
    raw = {n: df.loc[good_rows] for n, df in raw.items()}
    factor = raw["adj_close"] / raw["raw_close"]
    return {
        "open": raw["raw_open"] * factor,
        "high": raw["raw_high"] * factor,
        "low": raw["raw_low"] * factor,
        "close": raw["adj_close"],
        "raw_close": raw["raw_close"],
        "volume": raw["volume"],
    }


def dedupe_share_classes(tickers: list[str]) -> list[str]:
    seen_companies: set[str] = set()
    out = []
    for t in tickers:
        company = SHARE_CLASS_MAP.get(t, t)
        if company in seen_companies:
            continue
        seen_companies.add(company)
        out.append(t)
    return out


def trading_days_left_in_month(today: pd.Timestamp) -> int:
    """Trading days remaining in the month INCLUDING today."""
    holidays = {pd.Timestamp(h) for h in US_MARKET_HOLIDAYS}
    end = today + pd.offsets.MonthEnd(0)
    days = pd.bdate_range(today, end)
    return len([d for d in days if d not in holidays])


def trading_day_of_month(today: pd.Timestamp) -> int:
    """1-based index of today among the month's trading days so far."""
    holidays = {pd.Timestamp(h) for h in US_MARKET_HOLIDAYS}
    days = pd.bdate_range(today.replace(day=1), today)
    return len([d for d in days if d not in holidays])


def screen(equity: float) -> dict:
    panel = load_recent_panel()
    c, h, l, v = panel["close"], panel["high"], panel["low"], panel["volume"]
    raw_c = panel["raw_close"]
    today = c.index[-1]
    out: dict = {"as_of": str(today.date()), "equity": equity, "sleeves": {}}

    spy = c["SPY"].dropna()
    spy_above_200 = bool(spy.iloc[-1] > spy.rolling(200).mean().iloc[-1])
    out["spy_above_200dma"] = spy_above_200

    dv = dollar_volume(raw_c, v)

    # ---------- Sleeve A: three lower lows -> next-day limit buys ----------
    a_size = equity * SLEEVES["A_three_lower_lows"]["weight"] / SLEEVES["A_three_lower_lows"]["max_positions"]
    lower3 = (l < l.shift(1)) & (l.shift(1) < l.shift(2)) & (l.shift(2) < l.shift(3))
    liq = (raw_c > A_MIN_PRICE) & (dv > A_MIN_DOLLAR_VOL)
    sig = (
        (c > sma(c, A_TREND_SMA)) & (c < sma(c, 5)) & lower3 & liq
    ).iloc[-1]
    a_atr = atr(h, l, c, 10).iloc[-1]
    candidates = []
    warnings = []
    for t in sig.index[sig.fillna(False)]:
        if t in ("SPY", "QQQ", "^VIX"):
            continue
        adj_close_t = c[t].iloc[-1]
        # express the limit in RAW (tradeable) price space
        ratio = raw_c[t].iloc[-1] / adj_close_t
        limit_raw = (adj_close_t - A_STRETCH * a_atr[t]) * ratio
        last_close_raw = float(raw_c[t].iloc[-1])
        dist_pct = limit_raw / last_close_raw - 1.0
        if dist_pct <= -0.10:
            warnings.append(
                f"{t}: limit {limit_raw:.2f} is {dist_pct:.1%} below last close "
                f"{last_close_raw:.2f} - fat-finger guard, ORDER EXCLUDED"
            )
            continue
        candidates.append(
            {"ticker": t, "limit_price": round(float(limit_raw), 2),
             "last_close": round(last_close_raw, 2),
             "limit_vs_close_pct": round(float(dist_pct), 4),
             "dollar_volume_20d": float(dv[t].iloc[-1]),
             "shares": int(a_size // limit_raw)}
        )
    candidates.sort(key=lambda x: -x["dollar_volume_20d"])
    keep = set(dedupe_share_classes([x["ticker"] for x in candidates]))
    candidates = [x for x in candidates if x["ticker"] in keep]
    out["sleeves"]["A_three_lower_lows"] = {
        "orders": candidates[: SLEEVES["A_three_lower_lows"]["max_positions"]],
        "order_type": "LIMIT buy, day-only, for NEXT session; never convert to market",
        "position_size_usd": round(a_size, 2),
        "exit_rules": "Sell next OPEN after first close > prior close; "
                      f"hard time stop {A_TIME_STOP} trading days (sell at close).",
        "note": "Backtest selected randomly when oversubscribed; live ranks by liquidity (fill quality).",
        "warnings": warnings,
    }

    # ---------- Sleeve B: turn of month ----------
    b_size = equity * SLEEVES["B_turn_of_month"]["weight"] / SLEEVES["B_turn_of_month"]["max_positions"]
    days_left = trading_days_left_in_month(today)
    day_of = trading_day_of_month(today)
    b_orders = []
    if days_left == B_ENTRY_DAYS_BEFORE_EOM:
        top = dv.iloc[-1].drop(labels=["SPY", "QQQ", "^VIX"], errors="ignore").nlargest(B_TOP_N)
        picks = dedupe_share_classes(list(top.index))[: SLEEVES["B_turn_of_month"]["max_positions"]]
        b_orders = [
            {"ticker": t, "shares": int(b_size // raw_c[t].iloc[-1])}
            for t in picks
        ]
    out["sleeves"]["B_turn_of_month"] = {
        "entry_today": bool(b_orders),
        "orders": b_orders,
        "order_type": "Market-on-close TODAY (submit ~15 min before close)",
        "position_size_usd": round(b_size, 2),
        "exit_rules": f"Sell market-on-close on trading day {B_EXIT_DAY_OF_MONTH} of the new month.",
        "calendar": {"trading_days_left_in_month": days_left, "trading_day_of_month": day_of},
    }

    # ---------- Sleeve C: Turnaround Tuesday (bear only) ----------
    c_size = equity * SLEEVES["C_tt_bear"]["weight"] / SLEEVES["C_tt_bear"]["max_positions"]
    c_orders = []
    is_monday = today.dayofweek == 0
    if is_monday and not spy_above_200:
        ibs_today = ibs(h, l, c).iloc[-1]
        down = (c.iloc[-1] < c.iloc[-2])
        liq_today = liq.iloc[-1] if hasattr(liq, "iloc") else liq
        # standard liquidity floor for this sleeve ($5 / $20M, as backtested)
        liq2 = ((raw_c > 5.0) & (dv > 20e6)).iloc[-1]
        cond = down & (ibs_today < C_IBS_MAX) & liq2
        ranked = ibs_today[cond.fillna(False)].drop(labels=["SPY", "QQQ", "^VIX"], errors="ignore").nsmallest(
            SLEEVES["C_tt_bear"]["max_positions"] * 2
        )
        picks = dedupe_share_classes(list(ranked.index))[: SLEEVES["C_tt_bear"]["max_positions"]]
        c_orders = [
            {"ticker": t, "ibs": round(float(ibs_today[t]), 3),
             "shares": int(c_size // raw_c[t].iloc[-1])}
            for t in picks
        ]
    out["sleeves"]["C_tt_bear"] = {
        "active": is_monday and not spy_above_200,
        "reason_inactive": None if (is_monday and not spy_above_200) else
            ("not Monday" if not is_monday else "SPY above 200dma (sleeve only trades in bear regime)"),
        "orders": c_orders,
        "order_type": "Market-on-close TODAY (submit ~15 min before close)",
        "position_size_usd": round(c_size, 2),
        "exit_rules": "Sell at close when close > prior day's high, "
                      f"or after {C_TIME_STOP} trading days (whichever first).",
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="download fresh bars first")
    ap.add_argument("--equity", type=float, default=100_000.0)
    ap.add_argument("--json", default=None, help="also write signals to this path")
    args = ap.parse_args()

    if args.refresh:
        refresh_data()
    signals = screen(args.equity)

    print(f"\n=== Ensemble signals as of {signals['as_of']} "
          f"(equity ${signals['equity']:,.0f}; SPY>200dma: {signals['spy_above_200dma']}) ===")
    for name, s in signals["sleeves"].items():
        print(f"\n--- {name} (per-position ${s['position_size_usd']:,.0f}) ---")
        print(f"  exits: {s['exit_rules']}")
        orders = s.get("orders") or []
        if not orders:
            why = s.get("reason_inactive") or ("no entry window today" if name.startswith("B") else "no setups today")
            print(f"  no orders ({why})")
        for o in orders:
            print("  " + json.dumps(o))
        print(f"  order type: {s['order_type']}")

    if args.json:
        Path(args.json).write_text(json.dumps(signals, indent=2))
        print(f"\nSignals written -> {args.json}")


if __name__ == "__main__":
    main()
