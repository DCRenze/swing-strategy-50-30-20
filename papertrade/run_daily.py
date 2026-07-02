"""Alpaca paper-trading runner for the 60/40 A/H ensemble (fractional shares).

Single daily checkpoint, run shortly after the open (~9:35 am ET). Signals are
computed from yesterday's completed daily bar and acted on at today's open, which
matches the backtest's timing exactly. Fractional shares let a small ($1-2k)
account hold the full 20-position book, so every order is a DAY order (market or
limit) - the only order types Alpaca allows fractional quantities on.

    ALPACA_API_KEY=...        # in .env at the project root (never committed)
    ALPACA_SECRET_KEY=...

Usage (venv python, from project root):
  python -m papertrade.run_daily morning              # ~9:35 am ET, every trading day
  python -m papertrade.run_daily morning --dry-run    # compute + print orders, submit nothing
  python -m papertrade.run_daily status               # account + tracked positions

Sleeves:
  A three_lower_lows (60%) - limit DAY buys at close-0.75*ATR; sell at open on
                             first up-close or 15-day time stop. No stop loss.
  H momentum         (40%) - 52-week-high breakouts, market DAY buys at the open
                             when SPY>SMA(100); 5% stop loss or 15-day time stop.

Risk: an account high-water-mark lives in state.json. Drawdown <= -15% halts
Sleeve A entries (the knife-catcher); <= -20% halts all new entries. Exits always
run. Per-position cap and max 10 positions/sleeve come from the screener.

Position state: Alpaca is the source of truth for holdings; sleeve attribution and
entry dates live in papertrade/state.json, keyed by client order IDs of the form
<SLEEVE>-<TICKER>-<YYYYMMDD>-<side>. Every decision is journaled to journal/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import os  # noqa: E402

import pandas as pd  # noqa: E402

from playbook import screener as scr  # noqa: E402

STATE_PATH = Path(__file__).resolve().parent / "state.json"
JOURNAL_DIR = Path(__file__).resolve().parent / "journal"
TRADES_PATH = Path(__file__).resolve().parent / "trades.jsonl"  # realized closed-trade ledger

SLEEVE_TIME_STOPS = {"A": scr.A_TIME_STOP, "H": scr.H_HOLD_DAYS}

DRAWDOWN_HALT_A = -0.15    # halt Sleeve A (mean-reversion) new entries
DRAWDOWN_HALT_ALL = -0.20  # halt all new entries
MIN_NOTIONAL = 1.0         # Alpaca fractional minimum order value ($1)


def get_clients():
    from alpaca.trading.client import TradingClient

    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise SystemExit(
            "Missing ALPACA_API_KEY / ALPACA_SECRET_KEY in .env - see papertrade/run_daily.py docstring"
        )
    return TradingClient(key, secret, paper=True)


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"positions": {}, "hwm": 0.0}  # ticker -> {sleeve, entry_date}; hwm = high-water mark


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


class Journal:
    def __init__(self) -> None:
        JOURNAL_DIR.mkdir(exist_ok=True)
        self.path = JOURNAL_DIR / f"{dt.date.today().isoformat()}.jsonl"

    def log(self, kind: str, **kw) -> None:
        rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "kind": kind, **kw}
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"  [{kind}] " + json.dumps(kw))


def trading_days_between(start: str, end: str) -> int:
    """Trading days from entry date to today, entry day = day 0."""
    holidays = {pd.Timestamp(h) for h in scr.US_MARKET_HOLIDAYS}
    days = pd.bdate_range(pd.Timestamp(start), pd.Timestamp(end))
    days = [d for d in days if d not in holidays]
    return max(len(days) - 1, 0)


def submit_order(client, journal: Journal, dry: bool, *, sleeve: str, ticker: str,
                 side: str, qty: float, order_type: str, limit_price: float | None = None) -> None:
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

    qty = round(float(qty), 4)
    coid = f"{sleeve}-{ticker}-{dt.date.today():%Y%m%d}-{side}"
    info = dict(sleeve=sleeve, ticker=ticker, side=side, qty=qty,
                order_type=order_type, limit_price=limit_price, client_order_id=coid)
    if dry:
        journal.log("dry_run_order", **info)
        return
    # every order is a fractional-capable DAY order
    common = dict(symbol=ticker, qty=qty,
                  side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                  time_in_force=TimeInForce.DAY, client_order_id=coid)
    try:
        if order_type == "limit":
            req = LimitOrderRequest(limit_price=round(limit_price, 2), **common)
        else:
            req = MarketOrderRequest(**common)
        client.submit_order(req)
        journal.log("order_submitted", **info)
    except Exception as e:  # noqa: BLE001
        journal.log("order_error", error=str(e), **info)


def _record_closed_trade(meta: dict, ticker: str, sell, journal: Journal) -> None:
    """Append a realized round-trip to trades.jsonl when a tracked position closes."""
    entry_px = meta.get("entry_px")
    if not entry_px or sell is None:
        journal.log("trade_unrecorded", ticker=ticker,
                    reason="missing entry price or closing fill - realized P/L not logged")
        return
    exit_px, exit_qty, exit_at = sell
    rec = {
        "ticker": ticker, "sleeve": meta.get("sleeve", "?"),
        "entry_date": meta.get("entry_date"), "exit_date": str(exit_at.date()),
        "entry_px": round(entry_px, 4), "exit_px": round(exit_px, 4),
        "qty": round(exit_qty, 4), "ret": round(exit_px / entry_px - 1.0, 4),
        "pnl": round((exit_px - entry_px) * exit_qty, 2),
    }
    with TRADES_PATH.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    journal.log("trade_closed", **rec)


def reconcile(client, state: dict, journal: Journal) -> dict:
    """Sync state.json with Alpaca: record realized P/L for closed positions, adopt
    new fills (with entry price + sleeve), and backfill entry prices for known ones.
    Returns {symbol: {qty, avg_entry_price}} for held names."""
    held = {
        p.symbol: {"qty": float(p.qty), "avg_entry_price": float(p.avg_entry_price)}
        for p in client.get_all_positions()
    }
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    orders = client.get_orders(
        GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=200,
                         after=dt.datetime.now() - dt.timedelta(days=7))
    )
    # latest filled buy/sell per symbol over the last week
    buy_fills: dict = {}   # symbol -> (price, timestamp, sleeve)
    sell_fills: dict = {}  # symbol -> (price, qty, timestamp)
    for o in sorted((o for o in orders if o.filled_at and o.filled_avg_price),
                    key=lambda o: pd.Timestamp(o.filled_at)):
        side = str(o.side).split(".")[-1].lower()
        ts = pd.Timestamp(o.filled_at)
        if side == "sell":
            sell_fills[o.symbol] = (float(o.filled_avg_price), float(o.filled_qty or 0), ts)
        elif side == "buy":
            coid = str(o.client_order_id or "")
            sk = coid.split("-")[0] if coid[:1] in ("A", "H") else None
            buy_fills[o.symbol] = (float(o.filled_avg_price), ts, sk)

    # closed positions: record realized P/L, then drop from state
    for ticker in list(state["positions"]):
        if ticker not in held:
            meta = state["positions"][ticker]
            _record_closed_trade(meta, ticker, sell_fills.get(ticker), journal)
            journal.log("position_closed", ticker=ticker, **meta)
            del state["positions"][ticker]

    # adopt new holdings (with entry price); backfill entry_px for already-tracked
    for sym in held:
        if sym not in state["positions"]:
            bf = buy_fills.get(sym)
            if bf and bf[2] in ("A", "H"):
                px, ts, sk = bf
                state["positions"][sym] = {
                    "sleeve": sk, "entry_date": str(ts.date()), "entry_px": round(px, 4),
                }
                journal.log("position_adopted", ticker=sym, **state["positions"][sym])
            else:
                journal.log("unattributed_position", ticker=sym, qty=held[sym]["qty"],
                            note="held in account but no attributable buy fill - attribute manually")
        elif "entry_px" not in state["positions"][sym]:
            state["positions"][sym]["entry_px"] = round(held[sym]["avg_entry_price"], 4)
    return held


def drawdown_gate(state: dict, equity: float, journal: Journal):
    """Update the high-water mark and return (drawdown, halt_a, halt_all)."""
    hwm = max(float(state.get("hwm", 0.0)), equity)
    dd = (equity / hwm - 1.0) if hwm > 0 else 0.0
    state["hwm"] = hwm
    halt_all = dd <= DRAWDOWN_HALT_ALL
    halt_a = dd <= DRAWDOWN_HALT_A
    if halt_all:
        journal.log("action_needed",
                    msg=f"Account drawdown {dd:.1%} <= {DRAWDOWN_HALT_ALL:.0%}: ALL new entries halted (exits only).")
    elif halt_a:
        journal.log("action_needed",
                    msg=f"Account drawdown {dd:.1%} <= {DRAWDOWN_HALT_A:.0%}: Sleeve A entries halted (momentum + exits continue).")
    return dd, halt_a, halt_all


def run_morning(client, dry: bool) -> None:
    journal = Journal()
    state = load_state()
    held = reconcile(client, state, journal) if client is not None else {}
    equity = float(client.get_account().equity) if client is not None else 100_000.0
    dd, halt_a, halt_all = drawdown_gate(state, equity, journal)
    journal.log("run_start", mode="morning", equity=equity, hwm=round(state["hwm"], 2),
                drawdown=round(dd, 4), dry_run=dry)

    print("Refreshing data...")
    scr.refresh_data()
    signals = scr.screen(equity)
    as_of = signals["as_of"]
    panel = scr.load_recent_panel()
    c = panel["close"]

    # ---- Sleeve A exits (market sell at open): first up-close since entry, or time stop
    for ticker, meta in list(state["positions"].items()):
        if meta["sleeve"] != "A" or ticker not in held:
            continue
        days_held = trading_days_between(meta["entry_date"], as_of)
        qty = held[ticker]["qty"]
        if ticker not in c.columns:
            # held name missing from today's data (e.g. dropped from the universe):
            # can't evaluate the price-based exit, but still honor the time stop.
            if days_held >= SLEEVE_TIME_STOPS["A"]:
                submit_order(client, journal, dry, sleeve="A", ticker=ticker, side="sell",
                             qty=qty, order_type="market")
                journal.log("exit_reason", ticker=ticker, sleeve="A",
                            reason="time stop (ticker absent from data)", days_held=days_held)
            else:
                journal.log("warning", ticker=ticker,
                            msg="A position absent from current data - price exit skipped, review manually")
            continue
        s = c[ticker].dropna()
        if len(s) < 2:
            continue
        entry = pd.Timestamp(meta["entry_date"])
        closes = s[s.index > entry]
        up_closes = closes[closes > s.shift(1).reindex(closes.index)]
        if len(up_closes) and up_closes.index[-1] == s.index[-1] and len(up_closes) == 1:
            submit_order(client, journal, dry, sleeve="A", ticker=ticker, side="sell",
                         qty=qty, order_type="market")
        elif days_held >= SLEEVE_TIME_STOPS["A"]:
            submit_order(client, journal, dry, sleeve="A", ticker=ticker, side="sell",
                         qty=qty, order_type="market")
            journal.log("exit_reason", ticker=ticker, sleeve="A", reason="15d time stop", days_held=days_held)
        elif len(up_closes) > 1:
            journal.log("warning", ticker=ticker, msg="multiple up-closes since entry - exiting now (overdue)")
            submit_order(client, journal, dry, sleeve="A", ticker=ticker, side="sell",
                         qty=qty, order_type="market")

    # ---- Sleeve A entries (limit DAY buys)
    a = signals["sleeves"]["A_three_lower_lows"]
    for w in a.get("warnings", []):
        journal.log("fat_finger_excluded", detail=w)
    a_held = [t for t, m in state["positions"].items() if m["sleeve"] == "A"]
    slots = scr.SLEEVES["A_three_lower_lows"]["max_positions"] - len(a_held)
    if halt_a or halt_all:
        journal.log("skip", sleeve="A", reason=f"drawdown halt ({dd:.1%})")
    else:
        for order in a["orders"]:
            t = order["ticker"]
            if slots <= 0:
                journal.log("skip", sleeve="A", ticker=t, reason="sleeve full")
                continue
            if t in a_held or t in held:
                journal.log("skip", sleeve="A", ticker=t, reason="already held")
                continue
            if order["qty"] * order["limit_price"] < MIN_NOTIONAL:
                journal.log("skip", sleeve="A", ticker=t, reason="notional < $1")
                continue
            submit_order(client, journal, dry, sleeve="A", ticker=t, side="buy",
                         qty=order["qty"], order_type="limit", limit_price=order["limit_price"])
            slots -= 1

    # ---- Sleeve H exits (market sell at open): 5% stop (any close since entry) or time stop
    h_stop_mult = 1.0 - scr.H_STOP_FRAC
    for ticker, meta in list(state["positions"].items()):
        if meta["sleeve"] != "H" or ticker not in held:
            continue
        days_held = trading_days_between(meta["entry_date"], as_of)
        if ticker not in c.columns:
            # missing from today's data: honor the time stop, else flag for review.
            if days_held >= SLEEVE_TIME_STOPS["H"]:
                submit_order(client, journal, dry, sleeve="H", ticker=ticker, side="sell",
                             qty=held[ticker]["qty"], order_type="market")
                journal.log("exit_reason", ticker=ticker, sleeve="H",
                            reason="time stop (ticker absent from data)", days_held=days_held)
            else:
                journal.log("warning", ticker=ticker,
                            msg="H position absent from current data - stop check skipped, review manually")
            continue
        s = c[ticker].dropna()
        entry = pd.Timestamp(meta["entry_date"])
        closes_since = s[s.index >= entry]
        avg = held[ticker]["avg_entry_price"]
        stop_hit = len(closes_since) > 0 and float(closes_since.min()) < avg * h_stop_mult
        if stop_hit or days_held >= SLEEVE_TIME_STOPS["H"]:
            submit_order(client, journal, dry, sleeve="H", ticker=ticker, side="sell",
                         qty=held[ticker]["qty"], order_type="market")
            journal.log("exit_reason", ticker=ticker, sleeve="H",
                        reason="5% stop" if stop_hit else "15d time stop", days_held=days_held)

    # ---- Sleeve H entries (market DAY buys at open; SPY>SMA100 gate)
    hsig = signals["sleeves"]["H_momentum"]
    h_held = [t for t, m in state["positions"].items() if m["sleeve"] == "H"]
    slots_h = scr.SLEEVES["H_momentum"]["max_positions"] - len(h_held)
    if not hsig["active"]:
        journal.log("skip", sleeve="H", reason=hsig.get("reason_inactive") or "momentum gate off")
    elif halt_all:
        journal.log("skip", sleeve="H", reason=f"drawdown halt-all ({dd:.1%})")
    else:
        for order in hsig["orders"]:
            t = order["ticker"]
            if slots_h <= 0:
                journal.log("skip", sleeve="H", ticker=t, reason="sleeve full")
                continue
            if t in h_held or t in held:
                journal.log("skip", sleeve="H", ticker=t, reason="already held")
                continue
            if order["qty"] * order["last_close"] < MIN_NOTIONAL:
                journal.log("skip", sleeve="H", ticker=t, reason="notional < $1")
                continue
            submit_order(client, journal, dry, sleeve="H", ticker=t, side="buy",
                         qty=order["qty"], order_type="market")
            slots_h -= 1

    save_state(state)
    journal.log("run_end", mode="morning")


def run_status(client) -> None:
    acct = client.get_account()
    state = load_state()
    print(f"Equity: ${float(acct.equity):,.2f}  Cash: ${float(acct.cash):,.2f}  "
          f"Buying power: ${float(acct.buying_power):,.2f}  HWM: ${float(state.get('hwm', 0)):,.2f}")
    print(f"Tracked positions ({len(state['positions'])}):")
    for t, m in state["positions"].items():
        print(f"  {t}: sleeve {m['sleeve']}, entered {m['entry_date']}")
    for p in client.get_all_positions():
        print(f"  Alpaca: {p.symbol} qty={p.qty} avg=${float(p.avg_entry_price):.2f} "
              f"PnL=${float(p.unrealized_pl):,.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["morning", "status"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    client = None
    if args.mode == "status":
        client = get_clients()
    else:
        try:
            client = get_clients()
        except SystemExit:
            if not args.dry_run:
                raise
            print("No API keys found - dry-run preview without account (no reconcile/exits).")

    if args.mode == "morning":
        run_morning(client, args.dry_run)
    else:
        run_status(client)


if __name__ == "__main__":
    main()
