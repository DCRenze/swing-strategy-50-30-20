"""Post a daily trade + market report to a Discord webhook (no LLM, free).

Modes:
  morning - just after the open trade run: what was ordered, current positions, regime.
  eod     - after the close: the day's index moves + VIX, today's orders, positions P&L.

Reads Alpaca (orders/positions/equity) and yfinance (SPY/QQQ/VIX) only. It is
READ-ONLY with respect to trading - it never places or cancels orders. Any error
is swallowed (exit 0) so a reporting hiccup can never break the trade pipeline.

Env vars (from GitHub Secrets or .env):
  ALPACA_API_KEY, ALPACA_SECRET_KEY   - paper keys (account section; optional)
  DISCORD_WEBHOOK_URL                 - target channel (if unset, prints instead)

Usage:
  python -m papertrade.report_discord morning
  python -m papertrade.report_discord eod
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

JOURNAL_DIR = Path(__file__).resolve().parent / "journal"
DISCORD_LIMIT = 1990  # Discord hard-caps message content at 2000 chars


def market_snapshot() -> list[str]:
    """SPY/QQQ day move, VIX level, and the SPY regime (drives Sleeve H's gate)."""
    import yfinance as yf

    raw = yf.download(["SPY", "QQQ", "^VIX"], period="400d",
                      auto_adjust=True, progress=False)
    close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
    asof = close.index[-1].date()
    lines = [f"**Market** (as of {asof})"]
    for sym, label in (("SPY", "S&P 500"), ("QQQ", "Nasdaq 100")):
        s = close[sym].dropna()
        if len(s) >= 2:
            chg = s.iloc[-1] / s.iloc[-2] - 1.0
            lines.append(f"- {label}: {chg * 100:+.2f}%  (close {s.iloc[-1]:.2f})")
    vix = close["^VIX"].dropna()
    if len(vix):
        lines.append(f"- VIX: {vix.iloc[-1]:.2f}")
    spy = close["SPY"].dropna()
    above200 = spy.iloc[-1] > spy.rolling(200).mean().iloc[-1]
    above100 = spy.iloc[-1] > spy.rolling(100).mean().iloc[-1]
    lines.append(
        f"- Regime: SPY {'above' if above200 else 'below'} 200-day avg; "
        f"momentum sleeve {'ON' if above100 else 'OFF (SPY < 100-day avg)'}"
    )
    return lines


def alpaca_summary() -> list[str]:
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        return ["_(no Alpaca keys - account section skipped)_"]
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    client = TradingClient(key, secret, paper=True)
    acct = client.get_account()
    lines = [f"**Account**: equity ${float(acct.equity):,.2f} | cash ${float(acct.cash):,.2f}"]

    after = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    orders = list(client.get_orders(
        GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100, after=after)))
    if orders:
        lines.append(f"**Today's orders ({len(orders)})**:")
        for o in orders[:12]:
            side = str(o.side).split(".")[-1].lower()
            qty = o.filled_qty if float(o.filled_qty or 0) > 0 else o.qty
            px = f"@ ${float(o.filled_avg_price):.2f}" if o.filled_avg_price else f"({str(o.status).split('.')[-1].lower()})"
            lines.append(f"- {side} {float(qty):.4g} {o.symbol} {px}")
        if len(orders) > 12:
            lines.append(f"- ...and {len(orders) - 12} more")
    else:
        lines.append("**Today's orders**: none")

    positions = list(client.get_all_positions())
    if positions:
        total_pl = sum(float(p.unrealized_pl) for p in positions)
        lines.append(f"**Open positions ({len(positions)})** | unrealized P/L ${total_pl:+,.2f}:")
        for p in sorted(positions, key=lambda p: -abs(float(p.market_value)))[:15]:
            lines.append(f"- {p.symbol}: {float(p.qty):.4g} sh, "
                         f"${float(p.market_value):,.2f} ({float(p.unrealized_plpc) * 100:+.1f}%)")
        if len(positions) > 15:
            lines.append(f"- ...and {len(positions) - 15} more")
    else:
        lines.append("**Open positions**: none")
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
        if r.get("kind") in ("action_needed", "order_error"):
            alerts.append(r.get("msg") or r.get("error") or "")
    if not alerts:
        return []
    return ["**⚠️ Alerts**:"] + [f"- {m}" for m in alerts[:6]]


def build_report(mode: str) -> str:
    today = dt.date.today().isoformat()
    label = "Morning" if mode == "morning" else "End of Day"
    parts = [f"\U0001F4C8 **Swing Bot — {label} report** ({today})"]
    for section in (market_snapshot, alpaca_summary, journal_alerts):
        try:
            block = section()
        except Exception as e:  # noqa: BLE001
            block = [f"_({section.__name__} failed: {e})_"]
        if block:
            parts.append("")
            parts.extend(block)
    return "\n".join(parts)


def main() -> None:
    try:  # allow emoji when printing to a Windows (cp1252) console
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    mode = sys.argv[1] if len(sys.argv) > 1 else "eod"
    if mode not in ("morning", "eod"):
        raise SystemExit("mode must be 'morning' or 'eod'")
    content = build_report(mode)[:DISCORD_LIMIT]

    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("No DISCORD_WEBHOOK_URL set - printing report instead:\n")
        print(content)
        return
    try:
        import requests
        resp = requests.post(webhook, json={"content": content}, timeout=15)
        resp.raise_for_status()
        print("Report posted to Discord.")
    except Exception as e:  # noqa: BLE001 - never fail the pipeline over a report
        print(f"Discord post failed (ignored): {e}")
        print(content)


if __name__ == "__main__":
    main()
