"""Post a daily trade + market + performance report to a Discord webhook (no LLM).

Modes:
  morning - just after the open trade run.
  eod     - after the close.

Sections (both modes): market snapshot; account & risk (daily P/L, drawdown,
exposure, per-sleeve capital split); open positions grouped by sleeve with
biggest mover + time-stop warnings; today's orders (tagged by sleeve); exits
triggered today; realized P/L by sleeve (closed-trade ledger); alerts.

Reads Alpaca (account/positions/orders), yfinance (SPY/QQQ/VIX), the runner's
state.json (sleeve attribution + high-water mark), trades.jsonl (realized ledger),
and today's journal. READ-ONLY - never trades. Errors are swallowed (exit 0) so a
reporting hiccup never breaks the pipeline. Long reports are split across multiple
Discord messages.

Env: ALPACA_API_KEY, ALPACA_SECRET_KEY, DISCORD_WEBHOOK_URL.
Usage: python -m papertrade.report_discord [morning|eod]
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

HERE = Path(__file__).resolve().parent
JOURNAL_DIR = HERE / "journal"
STATE_PATH = HERE / "state.json"
TRADES_PATH = HERE / "trades.jsonl"
DISCORD_LIMIT = 1990
SLEEVE_NAMES = {"A": "A · dip-buyer (mean-reversion)", "H": "H · momentum"}
TIME_STOP = {"A": 15, "H": 15}   # trading-day time stops per sleeve
NEAR_STOP = 13                   # flag positions this many trading days in
MAX_POSITIONS = 20               # 10 per sleeve


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"positions": {}, "hwm": 0.0}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:  # noqa: BLE001
        return {"positions": {}, "hwm": 0.0}


def trading_days_since(entry_date: str) -> int:
    import pandas as pd

    try:
        days = pd.bdate_range(pd.Timestamp(entry_date), pd.Timestamp(dt.date.today()))
        return max(len(days) - 1, 0)
    except Exception:  # noqa: BLE001
        return 0


# ---------- sections ----------

def market_snapshot() -> list[str]:
    import yfinance as yf

    raw = yf.download(["SPY", "QQQ", "^VIX"], period="400d", auto_adjust=True, progress=False)
    close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
    asof = close.index[-1].date()
    lines = [f"**Market** (as of {asof})"]
    for sym, label in (("SPY", "S&P 500"), ("QQQ", "Nasdaq 100")):
        s = close[sym].dropna()
        if len(s) >= 2:
            lines.append(f"- {label}: {(s.iloc[-1] / s.iloc[-2] - 1) * 100:+.2f}%  (close {s.iloc[-1]:.2f})")
    vix = close["^VIX"].dropna()
    if len(vix):
        lines.append(f"- VIX: {vix.iloc[-1]:.2f}")
    spy = close["SPY"].dropna()
    above200 = spy.iloc[-1] > spy.rolling(200).mean().iloc[-1]
    above100 = spy.iloc[-1] > spy.rolling(100).mean().iloc[-1]
    lines.append(f"- Regime: SPY {'above' if above200 else 'below'} 200-day avg; "
                 f"momentum sleeve {'ON' if above100 else 'OFF'}")
    return lines


def account_and_risk(acct, positions, state) -> list[str]:
    equity = float(acct.equity)
    cash = float(acct.cash)
    last_eq = float(getattr(acct, "last_equity", equity) or equity)
    dchg = equity - last_eq
    dpct = (dchg / last_eq * 100) if last_eq else 0.0
    hwm = float(state.get("hwm", 0.0) or 0.0)
    dd = (equity / hwm - 1) * 100 if hwm > 0 else 0.0
    mv = sum(float(p.market_value) for p in positions)
    smap = {t: m.get("sleeve", "?") for t, m in state.get("positions", {}).items()}
    by = defaultdict(float)
    for p in positions:
        by[smap.get(p.symbol, "?")] += float(p.market_value)
    lines = [
        "**Account & risk**",
        f"- Equity: ${equity:,.2f}  (day {dchg:+,.2f}, {dpct:+.2f}%)",
        f"- Cash: ${cash:,.2f}  ·  Invested: {mv / equity * 100:.0f}%" if equity else f"- Cash: ${cash:,.2f}",
        f"- Drawdown vs high-water ${hwm:,.0f}: {dd:+.1f}%",
    ]
    if equity:
        lines.append(f"- Capital by sleeve: A {by.get('A', 0) / equity * 100:.0f}% · "
                     f"H {by.get('H', 0) / equity * 100:.0f}% "
                     f"(target A 60 / H 40)")
    lines.append(f"- Open positions: {len(positions)} / {MAX_POSITIONS} cap")
    return lines


def positions_by_sleeve(positions, state) -> list[str]:
    if not positions:
        return ["**Open positions**: none"]
    meta = state.get("positions", {})
    total_pl = sum(float(p.unrealized_pl) for p in positions)
    lines = [f"**Open positions ({len(positions)})** | total unrealized P/L ${total_pl:+,.2f}"]
    groups = defaultdict(list)
    for p in positions:
        groups[meta.get(p.symbol, {}).get("sleeve", "?")].append(p)
    for sk in ("A", "H", "?"):
        ps = groups.get(sk)
        if not ps:
            continue
        sub_pl = sum(float(p.unrealized_pl) for p in ps)
        sub_mv = sum(float(p.market_value) for p in ps)
        label = SLEEVE_NAMES.get(sk, "untracked (not in state.json)")
        lines.append(f"**{label}** — {len(ps)} pos · ${sub_mv:,.0f} · P/L ${sub_pl:+,.2f}")
        for p in sorted(ps, key=lambda p: -abs(float(p.market_value))):
            entry = meta.get(p.symbol, {}).get("entry_date")
            held = trading_days_since(entry) if entry else None
            warn = " ⏳ near time-stop" if held is not None and held >= NEAR_STOP else ""
            age = f", {held}d" if held is not None else ""
            lines.append(f"- {p.symbol}: {float(p.qty):.4g} sh, ${float(p.market_value):,.2f} "
                         f"({float(p.unrealized_plpc) * 100:+.1f}%{age}){warn}")
    # biggest mover
    best = max(positions, key=lambda p: float(p.unrealized_plpc))
    worst = min(positions, key=lambda p: float(p.unrealized_plpc))
    lines.append(f"- Top: {best.symbol} {float(best.unrealized_plpc) * 100:+.1f}% · "
                 f"Worst: {worst.symbol} {float(worst.unrealized_plpc) * 100:+.1f}%")
    return lines


def todays_orders(orders) -> list[str]:
    if not orders:
        return ["**Today's orders**: none"]
    lines = [f"**Today's orders ({len(orders)})** _(sleeve in brackets)_:"]
    for o in orders[:12]:
        coid = str(o.client_order_id or "")
        sk = coid.split("-", 1)[0] if coid[:1] in ("A", "H") else "?"
        side = str(o.side).split(".")[-1].lower()
        qty = o.filled_qty if float(o.filled_qty or 0) > 0 else o.qty
        px = f"@ ${float(o.filled_avg_price):.2f}" if o.filled_avg_price else f"({str(o.status).split('.')[-1].lower()})"
        lines.append(f"- `[{sk}]` {side} {float(qty):.4g} {o.symbol} {px}")
    if len(orders) > 12:
        lines.append(f"- ...and {len(orders) - 12} more")
    return lines


def todays_exits() -> list[str]:
    path = JOURNAL_DIR / f"{dt.date.today().isoformat()}.jsonl"
    if not path.exists():
        return []
    counts = defaultdict(int)
    for ln in path.read_text().splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("kind") == "exit_reason":
            counts[f"{r.get('sleeve', '?')}: {r.get('reason', '?')}"] += 1
    if not counts:
        return []
    return ["**Exits triggered today**"] + [f"- {k} ×{v}" for k, v in counts.items()]


def realized_by_sleeve() -> list[str]:
    if not TRADES_PATH.exists():
        return ["**Realized P/L (closed trades)**: none yet"]
    trades = []
    for ln in TRADES_PATH.read_text().splitlines():
        try:
            trades.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    if not trades:
        return ["**Realized P/L (closed trades)**: none yet"]
    lines = ["**Realized P/L by sleeve (closed trades, all-time)**"]
    groups = defaultdict(list)
    for t in trades:
        groups[t.get("sleeve", "?")].append(t)
    for sk in ("A", "H", "?"):
        ts = groups.get(sk)
        if not ts:
            continue
        wins = [t for t in ts if t["pnl"] > 0]
        losses = [t for t in ts if t["pnl"] < 0]
        tot = sum(t["pnl"] for t in ts)
        wr = len(wins) / len(ts) * 100
        avg_w = (sum(t["pnl"] for t in wins) / len(wins)) if wins else 0.0
        avg_l = (sum(t["pnl"] for t in losses) / len(losses)) if losses else 0.0
        gross_w = sum(t["pnl"] for t in wins)
        gross_l = -sum(t["pnl"] for t in losses)
        pf = f"{gross_w / gross_l:.2f}" if gross_l > 0 else "∞"
        label = SLEEVE_NAMES.get(sk, "untracked")
        lines.append(f"**{label}**: {len(ts)} trades · win {wr:.0f}% · net ${tot:+,.2f} · "
                     f"avg win ${avg_w:,.2f} / avg loss ${avg_l:,.2f} · PF {pf}")
    today = dt.date.today().isoformat()
    td = [t for t in trades if t.get("exit_date") == today]
    if td:
        lines.append(f"- Closed today: {len(td)} trade(s), ${sum(t['pnl'] for t in td):+,.2f}")
    return lines


def journal_alerts() -> list[str]:
    path = JOURNAL_DIR / f"{dt.date.today().isoformat()}.jsonl"
    if not path.exists():
        return []
    alerts = []
    for ln in path.read_text().splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("kind") in ("action_needed", "unattributed_position"):
            alerts.append(r.get("msg") or r.get("note") or "")
    if not alerts:
        return []
    return ["**⚠️ Alerts**"] + [f"- {m}" for m in alerts[:6]]


# ---------- assembly ----------

def _safe(fn, *args) -> list[str]:
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001
        return [f"_({fn.__name__} failed: {e})_"]


def build_report(mode: str) -> str:
    label = "Morning" if mode == "morning" else "End of Day"
    parts = [f"\U0001F4C8 **Swing Bot — {label} report** ({dt.date.today().isoformat()})"]
    parts += [""] + _safe(market_snapshot)

    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if key and secret:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        client = TradingClient(key, secret, paper=True)
        acct = client.get_account()
        positions = list(client.get_all_positions())
        after = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        orders = list(client.get_orders(
            GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100, after=after)))
        state = load_state()
        for section in (
            lambda: account_and_risk(acct, positions, state),
            lambda: positions_by_sleeve(positions, state),
            lambda: todays_orders(orders),
            todays_exits,
            realized_by_sleeve,
        ):
            block = _safe(section)
            if block:
                parts += [""] + block
    else:
        parts += ["", "_(no Alpaca keys - account sections skipped)_"]

    alerts = _safe(journal_alerts)
    if alerts:
        parts += [""] + alerts
    return "\n".join(parts)


def _chunk(text: str) -> list[str]:
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > DISCORD_LIMIT:
            chunks.append(cur)
            cur = line[:DISCORD_LIMIT]
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)
    return chunks


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    mode = sys.argv[1] if len(sys.argv) > 1 else "eod"
    if mode not in ("morning", "eod"):
        raise SystemExit("mode must be 'morning' or 'eod'")
    content = build_report(mode)

    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("No DISCORD_WEBHOOK_URL set - printing report instead:\n")
        print(content)
        return
    try:
        import requests
        for chunk in _chunk(content):
            requests.post(webhook, json={"content": chunk}, timeout=15).raise_for_status()
        print("Report posted to Discord.")
    except Exception as e:  # noqa: BLE001 - never fail the pipeline over a report
        print(f"Discord post failed (ignored): {e}")
        print(content)


if __name__ == "__main__":
    main()
