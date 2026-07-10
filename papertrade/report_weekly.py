"""Generate the weekly portfolio report (self-contained HTML) and optionally post
it to Discord as a file attachment.

Sections: equity + week / since-inception P/L, drawdown vs high-water mark and
circuit-breaker posture, per-sleeve realized performance (net P/L, win rate,
profit factor) this week and since inception vs backtest benchmarks, open
positions grouped by sleeve, market regime (SPY vs SMA100/200), and alerts
raised in the journal this week.

Reads live Alpaca (equity, positions, per-sleeve unrealized P/L) when
ALPACA_API_KEY / ALPACA_SECRET_KEY are set. Always reads
papertrade/trades.jsonl + state.json + journal/*.jsonl and yfinance. If Alpaca
keys are missing, the report still builds from committed data (noted in the
output). READ-ONLY - never trades.

Usage:
  python -m papertrade.report_weekly --out reports/weekly/2026-07-10.html
  python -m papertrade.report_weekly --out reports/weekly/2026-07-10.html \
      --narrative '<p>...</p>' --discord
"""

from __future__ import annotations

import argparse
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

SLEEVE_NAMES = {"A": "A · three-lower-lows dip-buyer (mean-reversion, 60%)",
                "H": "H · 52-week-high momentum (40%)"}
# Backtest benchmarks from playbook/PLAYBOOK.md
BENCHMARK_PF = {"A": {"full": 1.30, "oos": 1.19}, "H": {"oos": 1.37}}
INCEPTION_EQUITY = 100_000.0
DRAWDOWN_HALT_A = -0.15
DRAWDOWN_HALT_ALL = -0.20
DECAY_PF_FLOOR = 1.0


# ---------- data loading ----------

def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"positions": {}, "hwm": 0.0}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:  # noqa: BLE001
        return {"positions": {}, "hwm": 0.0}


def load_trades() -> list[dict]:
    if not TRADES_PATH.exists():
        return []
    out = []
    for ln in TRADES_PATH.read_text().splitlines():
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def load_journal_entries() -> list[dict]:
    entries = []
    if not JOURNAL_DIR.exists():
        return entries
    for path in sorted(JOURNAL_DIR.glob("*.jsonl")):
        for ln in path.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            r["_date"] = path.stem
            entries.append(r)
    return entries


def equity_curve(entries: list[dict]) -> list[tuple[str, float]]:
    """(date, equity) from real (non-dry-run) morning run_start events, deduped per day (last wins)."""
    by_day: dict[str, float] = {}
    for r in entries:
        if r.get("kind") == "run_start" and r.get("mode") == "morning" and not r.get("dry_run", False):
            eq = r.get("equity")
            if eq is not None:
                by_day[r["_date"]] = float(eq)
    return sorted(by_day.items())


def week_bounds(today: dt.date) -> tuple[dt.date, dt.date]:
    monday = today - dt.timedelta(days=today.weekday())
    return monday, monday + dt.timedelta(days=4)


# ---------- sections ----------

def market_regime() -> dict:
    import yfinance as yf

    raw = yf.download(["SPY", "QQQ", "^VIX"], period="400d", auto_adjust=True, progress=False)
    close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
    spy = close["SPY"].dropna()
    asof = spy.index[-1].date()
    above200 = bool(spy.iloc[-1] > spy.rolling(200).mean().iloc[-1])
    above100 = bool(spy.iloc[-1] > spy.rolling(100).mean().iloc[-1])
    vix = close["^VIX"].dropna()
    week_ret = None
    if len(spy) >= 6:
        week_ret = float(spy.iloc[-1] / spy.iloc[-6] - 1)
    return {
        "asof": str(asof),
        "spy_close": float(spy.iloc[-1]),
        "spy_week_ret": week_ret,
        "above_sma200": above200,
        "above_sma100": above100,
        "vix": float(vix.iloc[-1]) if len(vix) else None,
        "h_gate_on": above100,
    }


def sleeve_stats(trades: list[dict], sleeve: str, since: str | None = None) -> dict:
    ts = [t for t in trades if t.get("sleeve") == sleeve and (since is None or t.get("exit_date", "") >= since)]
    n = len(ts)
    wins = [t for t in ts if t["pnl"] > 0]
    losses = [t for t in ts if t["pnl"] < 0]
    net = sum(t["pnl"] for t in ts)
    gross_w = sum(t["pnl"] for t in wins)
    gross_l = -sum(t["pnl"] for t in losses)
    pf = (gross_w / gross_l) if gross_l > 0 else (float("inf") if gross_w > 0 else 0.0)
    wr = (len(wins) / n * 100) if n else 0.0
    return {"n": n, "net": net, "win_rate": wr, "pf": pf, "wins": len(wins), "losses": len(losses)}


def account_snapshot(state: dict) -> dict:
    """Live Alpaca account/positions if keys are set, else None."""
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        return None
    from alpaca.trading.client import TradingClient

    client = TradingClient(key, secret, paper=True)
    acct = client.get_account()
    positions = list(client.get_all_positions())
    return {"equity": float(acct.equity), "cash": float(acct.cash), "positions": positions}


def alerts_this_week(entries: list[dict], mon: dt.date, fri: dt.date) -> list[str]:
    out = []
    for r in entries:
        try:
            d = dt.date.fromisoformat(r["_date"])
        except ValueError:
            continue
        if not (mon <= d <= fri):
            continue
        if r.get("kind") in ("action_needed", "unattributed_position"):
            out.append(f"{r['_date']}: {r.get('msg') or r.get('note') or ''}")
        elif r.get("kind") == "warning":
            out.append(f"{r['_date']}: {r.get('msg', '')} ({r.get('ticker', '')})")
    return out


# ---------- HTML assembly ----------

def _fmt_pf(pf: float) -> str:
    return "∞" if pf == float("inf") else f"{pf:.2f}"


def build_html(report_date: dt.date, narrative: str | None) -> str:
    state = load_state()
    trades = load_trades()
    entries = load_journal_entries()
    curve = equity_curve(entries)
    mon, fri = week_bounds(report_date)
    week_start_date = mon.isoformat()

    try:
        acct = account_snapshot(state)
    except Exception as e:  # noqa: BLE001 - Alpaca unreachable/misconfigured: fall back to committed data
        print(f"Alpaca account fetch failed, falling back to committed data: {e}", file=sys.stderr)
        acct = None
    alpaca_live = acct is not None

    if alpaca_live:
        equity = acct["equity"]
        cash = acct["cash"]
        positions = acct["positions"]
    else:
        equity = curve[-1][1] if curve else INCEPTION_EQUITY
        cash = None
        positions = None

    hwm = max(float(state.get("hwm", 0.0) or 0.0), equity)
    dd = (equity / hwm - 1) if hwm > 0 else 0.0
    halt_a = dd <= DRAWDOWN_HALT_A
    halt_all = dd <= DRAWDOWN_HALT_ALL

    # week-start equity: last recorded equity strictly before Monday of this week,
    # falling back to the first entry on/after Monday.
    week_start_equity = None
    for d, eq in curve:
        if d < week_start_date:
            week_start_equity = eq
    if week_start_equity is None:
        for d, eq in curve:
            if d >= week_start_date:
                week_start_equity = eq
                break
    if week_start_equity is None:
        week_start_equity = equity

    week_pl = equity - week_start_equity
    week_pl_pct = (week_pl / week_start_equity) if week_start_equity else 0.0
    since_incep_pl = equity - INCEPTION_EQUITY
    since_incep_pct = (since_incep_pl / INCEPTION_EQUITY) if INCEPTION_EQUITY else 0.0

    # historical max drawdown from the recorded equity curve (+ live equity as the latest point)
    running_max = 0.0
    max_dd = 0.0
    for _, eq in curve + ([("today", equity)] if alpaca_live else []):
        running_max = max(running_max, eq)
        if running_max > 0:
            max_dd = min(max_dd, eq / running_max - 1)

    try:
        regime = market_regime()
    except Exception as e:  # noqa: BLE001
        regime = {"error": str(e)}

    sleeve_rows = []
    for sk in ("A", "H"):
        week = sleeve_stats(trades, sk, since=week_start_date)
        incep = sleeve_stats(trades, sk, since=None)
        bench = BENCHMARK_PF[sk]
        decay = incep["n"] > 0 and incep["pf"] < DECAY_PF_FLOOR
        sleeve_rows.append({
            "sleeve": sk, "label": SLEEVE_NAMES[sk], "week": week, "incep": incep,
            "bench": bench, "decay": decay,
        })

    alerts = alerts_this_week(entries, mon, fri)

    # ---- positions table ----
    pos_rows_html = []
    if positions is not None:
        meta = state.get("positions", {})
        groups = defaultdict(list)
        for p in positions:
            groups[meta.get(p.symbol, {}).get("sleeve", "?")].append(p)
        for sk in ("A", "H", "?"):
            ps = groups.get(sk)
            if not ps:
                continue
            for p in sorted(ps, key=lambda p: -abs(float(p.market_value))):
                m = meta.get(p.symbol, {})
                pos_rows_html.append(
                    f"<tr><td>{sk}</td><td>{p.symbol}</td><td>{m.get('entry_date', '?')}</td>"
                    f"<td>${float(p.market_value):,.2f}</td>"
                    f"<td class=\"{'pos' if float(p.unrealized_pl) >= 0 else 'neg'}\">"
                    f"${float(p.unrealized_pl):+,.2f} ({float(p.unrealized_plpc) * 100:+.1f}%)</td></tr>"
                )
    else:
        for ticker, m in state.get("positions", {}).items():
            pos_rows_html.append(
                f"<tr><td>{m.get('sleeve', '?')}</td><td>{ticker}</td><td>{m.get('entry_date', '?')}</td>"
                f"<td colspan=2>entry ${m.get('entry_px', 0):,.2f} "
                f"<i>(no live Alpaca data - unrealized P/L unavailable)</i></td></tr>"
            )
    if not pos_rows_html:
        pos_rows_html.append("<tr><td colspan=5>No open positions.</td></tr>")

    sleeve_rows_html = []
    for row in sleeve_rows:
        w, i, b = row["week"], row["incep"], row["bench"]
        bench_txt = " / ".join(f"{k.upper()} {v:.2f}" for k, v in b.items())
        decay_flag = ' <span class="flag">⚠ DECAY WATCH (PF &lt; 1.0)</span>' if row["decay"] else ""
        sleeve_rows_html.append(f"""
        <tr><td rowspan=2><b>{row['label']}</b>{decay_flag}<br><small>Backtest PF: {bench_txt}</small></td>
            <td>This week</td><td>{w['n']}</td><td>{w['win_rate']:.0f}%</td>
            <td class="{'pos' if w['net'] >= 0 else 'neg'}">${w['net']:+,.2f}</td><td>{_fmt_pf(w['pf'])}</td></tr>
        <tr><td>Since inception</td><td>{i['n']}</td><td>{i['win_rate']:.0f}%</td>
            <td class="{'pos' if i['net'] >= 0 else 'neg'}">${i['net']:+,.2f}</td><td>{_fmt_pf(i['pf'])}</td></tr>
        """)

    if "error" in regime:
        regime_html = f"<p><i>Market regime unavailable: {regime['error']}</i></p>"
    else:
        wk_ret = f"{regime['spy_week_ret'] * 100:+.2f}%" if regime["spy_week_ret"] is not None else "n/a"
        vix_txt = f"{regime['vix']:.2f}" if regime["vix"] is not None else "n/a"
        regime_html = f"""
        <p>SPY close {regime['spy_close']:.2f} ({wk_ret} this week) as of {regime['asof']}
        &middot; VIX {vix_txt}
        &middot; SPY {'above' if regime['above_sma200'] else 'below'} SMA200
        &middot; SPY {'above' if regime['above_sma100'] else 'below'} SMA100
        &rarr; Sleeve H entry gate is <b>{'ON' if regime['h_gate_on'] else 'OFF'}</b></p>
        """

    breaker_html = "<p><b>Circuit breaker: normal</b> — all entries active.</p>"
    if halt_all:
        breaker_html = (f"<p class=\"flag\"><b>Circuit breaker: ALL new entries halted</b> "
                         f"(drawdown {dd:.1%} &le; {DRAWDOWN_HALT_ALL:.0%}). Exits continue as normal.</p>")
    elif halt_a:
        breaker_html = (f"<p class=\"flag\"><b>Circuit breaker: Sleeve A entries halted</b> "
                         f"(drawdown {dd:.1%} &le; {DRAWDOWN_HALT_A:.0%}). Sleeve H and all exits continue.</p>")

    alerts_html = "<p>No alerts raised this week.</p>"
    if alerts:
        alerts_html = "<ul>" + "".join(f"<li>{a}</li>" for a in alerts) + "</ul>"

    data_note = ("" if alpaca_live else
                 "<p><i>Live Alpaca data unavailable in this environment (missing keys or unreachable API) — "
                 "equity, cash, and live unrealized P/L are unavailable. This report is built "
                 "entirely from committed papertrade/state.json, trades.jsonl, and journal data.</i></p>")

    narrative_html = f'<div class="narrative">{narrative}</div>' if narrative else ""

    return f"""<title>Weekly Portfolio Report — {report_date.isoformat()}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; max-width: 900px;
          margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.6rem; }}
  h2 {{ font-size: 1.15rem; border-bottom: 1px solid #ddd; padding-bottom: 0.25rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0 1rem; font-size: 0.92rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #eee; }}
  th {{ background: #f7f7f7; }}
  .pos {{ color: #0a7a2a; font-weight: 600; }}
  .neg {{ color: #b3261e; font-weight: 600; }}
  .flag {{ color: #b3261e; }}
  .stat {{ display: inline-block; margin: 0 1.5rem 0.5rem 0; }}
  .stat b {{ display: block; font-size: 1.3rem; }}
  .narrative {{ background: #f5f7fa; border-left: 4px solid #4a6fa5; padding: 0.75rem 1rem; margin: 1rem 0; }}
</style>
<h1>Weekly Portfolio Report — {report_date.isoformat()}</h1>
<p>Strategy: 60/40 A/H ensemble (Sleeve A three-lower-lows mean-reversion, Sleeve H 52-week-high momentum).
Week: {mon.isoformat()} &ndash; {fri.isoformat()}.</p>
{data_note}
{narrative_html}

<h2>Account</h2>
<div>
  <div class="stat">Equity<b>${equity:,.2f}</b></div>
  <div class="stat">Week P/L<b class="{'pos' if week_pl >= 0 else 'neg'}">${week_pl:+,.2f} ({week_pl_pct:+.2%})</b></div>
  <div class="stat">Since inception<b class="{'pos' if since_incep_pl >= 0 else 'neg'}">${since_incep_pl:+,.2f} ({since_incep_pct:+.2%})</b></div>
  <div class="stat">High-water mark<b>${hwm:,.2f}</b></div>
  <div class="stat">Drawdown vs HWM<b class="{'neg' if dd < 0 else 'pos'}">{dd:+.2%}</b></div>
  <div class="stat">Max drawdown (recorded)<b class="neg">{max_dd:+.2%}</b></div>
  {f'<div class="stat">Cash<b>${cash:,.2f}</b></div>' if cash is not None else ''}
</div>
{breaker_html}

<h2>Market regime</h2>
{regime_html}

<h2>Sleeve performance vs backtest benchmark</h2>
<table>
<tr><th>Sleeve</th><th>Window</th><th>Trades</th><th>Win rate</th><th>Net P/L</th><th>Profit factor</th></tr>
{''.join(sleeve_rows_html)}
</table>

<h2>Open positions</h2>
<table>
<tr><th>Sleeve</th><th>Ticker</th><th>Entry date</th><th>Market value</th><th>Unrealized P/L</th></tr>
{''.join(pos_rows_html)}
</table>

<h2>Alerts this week</h2>
{alerts_html}
"""


# ---------- Discord ----------

def post_to_discord(html_path: Path, summary: str) -> bool:
    import requests

    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        return False
    with open(html_path, "rb") as f:
        files = {"file": (html_path.name, f, "text/html")}
        data = {"content": summary}
        resp = requests.post(webhook, data=data, files=files, timeout=30)
        resp.raise_for_status()
    return True


# ---------- CLI ----------

def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Output HTML path")
    parser.add_argument("--narrative", default=None, help="HTML commentary to inject")
    parser.add_argument("--narrative-file", default=None, help="Path to a file containing HTML commentary to inject")
    parser.add_argument("--discord", action="store_true", help="Post the report to Discord as a file attachment")
    args = parser.parse_args()

    narrative = args.narrative
    if args.narrative_file:
        narrative = Path(args.narrative_file).read_text(encoding="utf-8")

    report_date = dt.date.today()
    html = build_html(report_date, narrative)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")

    if args.discord:
        summary = f"\U0001F4C8 **Weekly Portfolio Report — {report_date.isoformat()}**"
        try:
            ok = post_to_discord(out_path, summary)
            if ok:
                print("Posted weekly report to Discord.")
            else:
                print("No DISCORD_WEBHOOK_URL set - skipped Discord post.")
        except Exception as e:  # noqa: BLE001 - never fail the pipeline over a report
            print(f"Discord post failed: {e}")


if __name__ == "__main__":
    main()
