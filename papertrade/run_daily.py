"""Alpaca paper-trading runner for the validated 50/30/20 ensemble.

Implements the PLAYBOOK.md two-checkpoint procedure against the Alpaca PAPER
endpoint. Keys come from .env in the project root (never committed):

    ALPACA_API_KEY=...
    ALPACA_SECRET_KEY=...

Usage (venv python, from project root):
  python -m papertrade.run_daily evening              # after ~4:30 pm ET, daily
  python -m papertrade.run_daily nearclose            # 3:30-3:45 pm ET, flagged days
  python -m papertrade.run_daily evening --dry-run    # print orders, submit nothing
  python -m papertrade.run_daily status               # account + tracked positions

Position state: Alpaca is the source of truth for what is held; sleeve
attribution and entry dates live in papertrade/state.json, keyed by client
order IDs of the form  <SLEEVE>-<TICKER>-<YYYYMMDD>.
Every decision (order, skip, warning) is journaled to papertrade/journal/.
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

SLEEVE_TIME_STOPS = {"A": scr.A_TIME_STOP, "C": scr.C_TIME_STOP}


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
    return {"positions": {}}  # ticker -> {sleeve, entry_date}


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
                 side: str, qty: int, order_type: str, tif: str,
                 limit_price: float | None = None) -> None:
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

    coid = f"{sleeve}-{ticker}-{dt.date.today():%Y%m%d}-{side}"
    info = dict(sleeve=sleeve, ticker=ticker, side=side, qty=qty,
                order_type=order_type, tif=tif, limit_price=limit_price, client_order_id=coid)
    if dry:
        journal.log("dry_run_order", **info)
        return
    tif_map = {"day": TimeInForce.DAY, "opg": TimeInForce.OPG, "cls": TimeInForce.CLS}
    common = dict(symbol=ticker, qty=qty,
                  side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                  time_in_force=tif_map[tif], client_order_id=coid)
    try:
        if order_type == "limit":
            req = LimitOrderRequest(limit_price=round(limit_price, 2), **common)
        else:
            req = MarketOrderRequest(**common)
        client.submit_order(req)
        journal.log("order_submitted", **info)
    except Exception as e:  # noqa: BLE001
        journal.log("order_error", error=str(e), **info)


def reconcile(client, state: dict, journal: Journal) -> dict:
    """Sync state.json with Alpaca: drop entries for positions no longer held,
    adopt fills from our client order IDs."""
    held = {p.symbol: int(float(p.qty)) for p in client.get_all_positions()}
    for ticker in list(state["positions"]):
        if ticker not in held:
            journal.log("position_closed", ticker=ticker, **state["positions"][ticker])
            del state["positions"][ticker]
    # adopt unknown holdings from recent closed orders (fills since yesterday)
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    orders = client.get_orders(
        GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=200,
                         after=dt.datetime.now() - dt.timedelta(days=7))
    )
    for o in orders:
        sym = o.symbol
        if sym in held and sym not in state["positions"] and o.client_order_id:
            parts = str(o.client_order_id).split("-")
            if len(parts) >= 4 and parts[0] in ("A", "B", "C") and parts[-1] == "buy" and o.filled_at:
                state["positions"][sym] = {
                    "sleeve": parts[0],
                    "entry_date": str(pd.Timestamp(o.filled_at).date()),
                }
                journal.log("position_adopted", ticker=sym, **state["positions"][sym])
    for sym in held:
        if sym not in state["positions"]:
            journal.log("unattributed_position", ticker=sym, qty=held[sym],
                        note="held in account but not in state - attribute manually")
    return held


def run_evening(client, dry: bool) -> None:
    journal = Journal()
    state = load_state()
    held = reconcile(client, state, journal) if not dry or STATE_PATH.exists() else {}
    if client is not None:
        acct = client.get_account()
        equity = float(acct.equity)
    else:
        equity = 100_000.0
    journal.log("run_start", mode="evening", equity=equity, dry_run=dry)

    print("Refreshing data...")
    scr.refresh_data()
    signals = scr.screen(equity)
    as_of = signals["as_of"]
    last_session = str(scr.load_recent_panel()["close"].index[-1].date())
    if as_of != last_session:  # defensive; screen() already trims
        journal.log("warning", msg=f"as_of {as_of} != last session {last_session}")

    panel = scr.load_recent_panel()
    c = panel["close"]

    # ---- Sleeve A exits: first up-close today -> OPG sell tomorrow; time stops
    for ticker, meta in list(state["positions"].items()):
        if meta["sleeve"] != "A" or ticker not in held:
            continue
        s = c[ticker].dropna()
        if len(s) < 2:
            continue
        entry = pd.Timestamp(meta["entry_date"])
        closes = s[s.index > entry]
        up_closes = closes[closes > s.shift(1).reindex(closes.index)]
        days_held = trading_days_between(meta["entry_date"], as_of)
        if len(up_closes) and up_closes.index[-1] == s.index[-1] and len(up_closes) == 1:
            submit_order(client, journal, dry, sleeve="A", ticker=ticker, side="sell",
                         qty=held[ticker], order_type="market", tif="opg")
        elif days_held >= SLEEVE_TIME_STOPS["A"]:
            journal.log("action_needed", ticker=ticker,
                        msg=f"A time stop reached ({days_held}d) - submit MOC sell before 3:45pm ET tomorrow")
        elif len(up_closes) > 1:
            journal.log("warning", ticker=ticker,
                        msg="multiple up-closes since entry without exit - exit at next open (overdue)")
            submit_order(client, journal, dry, sleeve="A", ticker=ticker, side="sell",
                         qty=held[ticker], order_type="market", tif="opg")

    # ---- Sleeve A entries: day-only limits for tomorrow
    a = signals["sleeves"]["A_three_lower_lows"]
    for w in a.get("warnings", []):
        journal.log("fat_finger_excluded", detail=w)
    a_held = [t for t, m in state["positions"].items() if m["sleeve"] == "A"]
    slots = scr.SLEEVES["A_three_lower_lows"]["max_positions"] - len(a_held)
    for order in a["orders"]:
        t = order["ticker"]
        if slots <= 0:
            journal.log("skip", sleeve="A", ticker=t, reason="sleeve full")
            continue
        if t in a_held:
            journal.log("skip", sleeve="A", ticker=t, reason="already held in sleeve")
            continue
        if order["shares"] < 1:
            journal.log("skip", sleeve="A", ticker=t, reason="position size < 1 share")
            continue
        submit_order(client, journal, dry, sleeve="A", ticker=t, side="buy",
                     qty=order["shares"], order_type="limit", tif="day",
                     limit_price=order["limit_price"])
        slots -= 1

    # ---- Sleeve B calendar flags for tomorrow
    cal = signals["sleeves"]["B_turn_of_month"]["calendar"]
    if cal["trading_days_left_in_month"] == scr.B_ENTRY_DAYS_BEFORE_EOM + 1:
        journal.log("action_needed", msg="TOMORROW is the turn-of-month ENTRY day - run nearclose mode before 3:45pm ET")
    b_held = [t for t, m in state["positions"].items() if m["sleeve"] == "B"]
    if b_held:
        journal.log("action_needed",
                    msg=f"B positions open ({b_held}) - exit MOC on trading day {scr.B_EXIT_DAY_OF_MONTH} of new month (run nearclose)")
    spy_above = signals["spy_above_200dma"]
    if not spy_above:
        journal.log("action_needed", msg="SPY below 200dma - if next session is Monday, sleeve C is live (run nearclose)")

    save_state(state)
    journal.log("run_end", mode="evening")


def run_nearclose(client, dry: bool) -> None:
    journal = Journal()
    state = load_state()
    held = reconcile(client, state, journal)
    acct = client.get_account()
    equity = float(acct.equity)
    journal.log("run_start", mode="nearclose", equity=equity, dry_run=dry)

    print("Refreshing data (today's partial bars expected)...")
    scr.refresh_data()
    # near the close we accept today's partial bar as the acting session
    signals = scr.screen(equity)
    today = dt.date.today()
    cal = signals["sleeves"]["B_turn_of_month"]["calendar"]

    # ---- B exit day?
    b_held = {t: m for t, m in state["positions"].items() if m["sleeve"] == "B" and t in held}
    if cal["trading_day_of_month"] == scr.B_EXIT_DAY_OF_MONTH and b_held:
        for t in b_held:
            submit_order(client, journal, dry, sleeve="B", ticker=t, side="sell",
                         qty=held[t], order_type="market", tif="cls")

    # ---- B entry day?
    b = signals["sleeves"]["B_turn_of_month"]
    if b["entry_today"]:
        for order in b["orders"]:
            t = order["ticker"]
            if t in state["positions"]:
                journal.log("skip", sleeve="B", ticker=t, reason="already held")
                continue
            if order["shares"] < 1:
                journal.log("skip", sleeve="B", ticker=t, reason="size < 1 share")
                continue
            submit_order(client, journal, dry, sleeve="B", ticker=t, side="buy",
                         qty=order["shares"], order_type="market", tif="cls")

    # ---- C exits (close > prior high, or 4-day stop)
    panel = scr.load_recent_panel()
    c_, h_ = panel["close"], panel["high"]
    for t, m in list(state["positions"].items()):
        if m["sleeve"] != "C" or t not in held:
            continue
        s_c, s_h = c_[t].dropna(), h_[t].dropna()
        days_held = trading_days_between(m["entry_date"], str(today))
        above_prior_high = len(s_c) >= 2 and s_c.iloc[-1] > s_h.iloc[-2]
        if above_prior_high or days_held >= SLEEVE_TIME_STOPS["C"]:
            submit_order(client, journal, dry, sleeve="C", ticker=t, side="sell",
                         qty=held[t], order_type="market", tif="cls")

    # ---- C entries (Monday + bear regime; needs today's bar in the data)
    c_sig = signals["sleeves"]["C_tt_bear"]
    if c_sig["active"] and signals["as_of"] == str(today):
        for order in c_sig["orders"]:
            t = order["ticker"]
            if t in state["positions"]:
                journal.log("skip", sleeve="C", ticker=t, reason="already held")
                continue
            if order["shares"] < 1:
                journal.log("skip", sleeve="C", ticker=t, reason="size < 1 share")
                continue
            submit_order(client, journal, dry, sleeve="C", ticker=t, side="buy",
                         qty=order["shares"], order_type="market", tif="cls")
    elif c_sig["active"]:
        journal.log("skip", sleeve="C",
                    reason=f"today's bars not yet in data (as_of {signals['as_of']}) - per playbook, skip rather than approximate")

    save_state(state)
    journal.log("run_end", mode="nearclose")


def run_status(client) -> None:
    acct = client.get_account()
    state = load_state()
    print(f"Equity: ${float(acct.equity):,.2f}  Cash: ${float(acct.cash):,.2f}  "
          f"Buying power: ${float(acct.buying_power):,.2f}")
    print(f"Tracked positions ({len(state['positions'])}):")
    for t, m in state["positions"].items():
        print(f"  {t}: sleeve {m['sleeve']}, entered {m['entry_date']}")
    for p in client.get_all_positions():
        print(f"  Alpaca: {p.symbol} qty={p.qty} avg=${float(p.avg_entry_price):.2f} "
              f"PnL=${float(p.unrealized_pl):,.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["evening", "nearclose", "status"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    client = None
    if not (args.dry_run and args.mode == "evening"):
        client = get_clients()

    if args.mode == "evening":
        run_evening(client, args.dry_run)
    elif args.mode == "nearclose":
        run_nearclose(client, args.dry_run)
    else:
        run_status(client)


if __name__ == "__main__":
    main()
