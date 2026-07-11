"""Weekly portfolio-manager HTML report for the 60/40 A/H ensemble (no LLM logic here;
the PM narrative is supplied externally via --narrative-file and dropped in verbatim).

Sections: account & equity (equity, week P/L, since-inception P/L, drawdown vs
high-water mark, Sharpe/Sortino/vol), per-sleeve realized performance (net P/L, win
rate, profit factor vs backtest benchmark), open positions by sleeve, market regime
(SPY/QQQ/VIX, momentum gate), alerts from the past week's journals, PM commentary.

Reads Alpaca (equity/positions/portfolio history) when ALPACA_API_KEY/ALPACA_SECRET_KEY
are set and reachable, papertrade/trades.jsonl (realized closed-trade ledger),
papertrade/state.json (sleeve attribution + high-water mark), papertrade/journal/*.jsonl
(last 7 days, for alerts), and yfinance (SPY/QQQ/VIX). Any of these being unavailable
(missing keys, network error, missing file) degrades that section gracefully rather
than failing the whole report - always builds from committed data at minimum.
READ-ONLY - never trades, never modifies state.json/trades.jsonl/journal.

Usage:
  python -m papertrade.report_weekly --out reports/weekly/2026-07-11.html
  python -m papertrade.report_weekly --out reports/weekly/2026-07-11.html \
      --narrative-file /tmp/pm_narrative.html --discord

Env: ALPACA_API_KEY, ALPACA_SECRET_KEY, DISCORD_WEBHOOK_URL.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
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

SLEEVE_NAMES = {"A": "A · three-lower-lows (mean reversion, 60%)", "H": "H · 52-week-high (momentum, 40%)"}
# Backtest benchmark profit factors from playbook/PLAYBOOK.md and results/REFINEMENT.md
BENCHMARK_PF = {"A": {"full": 1.30, "oos": 1.19}, "H": {"oos": 1.37}}
WEEK_DAYS = 7  # calendar days considered "this week" for the weekly window


# ---------------------------------------------------------------------------
# Local data (always available)
# ---------------------------------------------------------------------------

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
    trades = []
    for ln in TRADES_PATH.read_text().splitlines():
        try:
            trades.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return trades


def load_recent_alerts(days: int = WEEK_DAYS) -> list[dict]:
    if not JOURNAL_DIR.exists():
        return []
    cutoff = dt.date.today() - dt.timedelta(days=days)
    alerts = []
    for path in sorted(JOURNAL_DIR.glob("*.jsonl")):
        try:
            file_date = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if file_date < cutoff:
            continue
        for ln in path.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("kind") in ("action_needed", "unattributed_position", "fat_finger_excluded"):
                alerts.append({**r, "date": path.stem})
    return alerts


def sleeve_stats(trades: list[dict], sleeve: str) -> dict:
    ts = [t for t in trades if t.get("sleeve") == sleeve]
    if not ts:
        return {"n": 0, "net_pnl": 0.0, "win_rate": None, "pf": None}
    wins = [t for t in ts if t["pnl"] > 0]
    losses = [t for t in ts if t["pnl"] < 0]
    gross_w = sum(t["pnl"] for t in wins)
    gross_l = -sum(t["pnl"] for t in losses)
    return {
        "n": len(ts),
        "net_pnl": sum(t["pnl"] for t in ts),
        "win_rate": len(wins) / len(ts) * 100,
        "pf": (gross_w / gross_l) if gross_l > 0 else (math.inf if gross_w > 0 else None),
        "avg_win": (gross_w / len(wins)) if wins else 0.0,
        "avg_loss": (-gross_l / len(losses)) if losses else 0.0,
    }


def week_trades(trades: list[dict]) -> list[dict]:
    cutoff = (dt.date.today() - dt.timedelta(days=WEEK_DAYS)).isoformat()
    return [t for t in trades if (t.get("exit_date") or "") >= cutoff]


# ---------------------------------------------------------------------------
# Live data (Alpaca + yfinance) - each independently optional
# ---------------------------------------------------------------------------

def fetch_alpaca() -> dict:
    """Returns {ok, reason, account, positions, history} - reason explains why
    ok is False (no keys vs. a connection/API error) so the caller can be honest
    about which it is."""
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        return {"ok": False, "reason": "ALPACA_API_KEY / ALPACA_SECRET_KEY not set"}
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetPortfolioHistoryRequest

        client = TradingClient(key, secret, paper=True)
        account = client.get_account()
        positions = list(client.get_all_positions())
        history = client.get_portfolio_history(
            GetPortfolioHistoryRequest(period="1A", timeframe="1D")
        )
        return {"ok": True, "account": account, "positions": positions, "history": history}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"Alpaca unreachable ({e.__class__.__name__}): {e}"}


def fetch_market_regime() -> dict:
    try:
        import yfinance as yf

        raw = yf.download(["SPY", "QQQ", "^VIX"], period="400d", auto_adjust=True, progress=False)
        close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
        if close.dropna(how="all").empty:
            return {"ok": False, "reason": "yfinance returned no data"}
        asof = close.index[-1].date()
        spy = close["SPY"].dropna()
        qqq = close["QQQ"].dropna()
        vix = close["^VIX"].dropna()
        above200 = bool(spy.iloc[-1] > spy.rolling(200).mean().iloc[-1])
        above100 = bool(spy.iloc[-1] > spy.rolling(100).mean().iloc[-1])
        return {
            "ok": True, "asof": asof,
            "spy_chg": (spy.iloc[-1] / spy.iloc[-2] - 1) * 100 if len(spy) >= 2 else None,
            "spy_close": float(spy.iloc[-1]),
            "qqq_chg": (qqq.iloc[-1] / qqq.iloc[-2] - 1) * 100 if len(qqq) >= 2 else None,
            "qqq_close": float(qqq.iloc[-1]) if len(qqq) else None,
            "vix": float(vix.iloc[-1]) if len(vix) else None,
            "above200": above200, "above100": above100,
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"yfinance unreachable ({e.__class__.__name__}): {e}"}


def risk_metrics(history) -> dict:
    """Sharpe/Sortino/vol (annualized, rf=0) + week & since-inception P/L from an
    Alpaca PortfolioHistory object."""
    equity = [e for e in history.equity if e is not None]
    ts = history.timestamp[:len(equity)]
    if len(equity) < 2:
        return {}
    rets = [(equity[i] / equity[i - 1] - 1.0) for i in range(1, len(equity)) if equity[i - 1]]
    if not rets:
        return {}
    mean_r = sum(rets) / len(rets)
    var = sum((r - mean_r) ** 2 for r in rets) / len(rets)
    std = math.sqrt(var)
    downside = [r for r in rets if r < 0]
    dstd = math.sqrt(sum(r ** 2 for r in downside) / len(downside)) if downside else 0.0
    sharpe = (mean_r / std * math.sqrt(252)) if std > 0 else None
    sortino = (mean_r / dstd * math.sqrt(252)) if dstd > 0 else None
    vol = std * math.sqrt(252) * 100

    # week P/L: nearest equity point >= 7 calendar days back
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - WEEK_DAYS * 86400
    week_start_idx = 0
    for i, t in enumerate(ts):
        if t >= cutoff:
            week_start_idx = i
            break
    else:
        week_start_idx = len(ts) - 1
    week_base = equity[max(week_start_idx - 1, 0)]
    week_pl = equity[-1] - week_base
    week_pl_pct = (equity[-1] / week_base - 1) * 100 if week_base else None

    base_value = history.base_value or equity[0]
    since_pl = equity[-1] - base_value
    since_pl_pct = (equity[-1] / base_value - 1) * 100 if base_value else None

    return {
        "sharpe": sharpe, "sortino": sortino, "vol_annual_pct": vol,
        "week_pl": week_pl, "week_pl_pct": week_pl_pct,
        "since_pl": since_pl, "since_pl_pct": since_pl_pct,
        "n_days": len(equity),
    }


def load_journal_equity_series() -> list[tuple[dt.date, float, float, float]]:
    """(date, equity, hwm, drawdown) from the live ensemble's real morning
    run_start records (mode=morning, not dry-run) - one point per day, last
    logged reading if a day has retries. Used only when Alpaca is unreachable;
    these are pre-open reconciliation snapshots, not official closes."""
    if not JOURNAL_DIR.exists():
        return []
    by_day: dict[dt.date, tuple] = {}
    for path in sorted(JOURNAL_DIR.glob("*.jsonl")):
        try:
            file_date = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        for ln in path.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("kind") == "run_start" and r.get("mode") == "morning" and not r.get("dry_run"):
                by_day[file_date] = (r.get("equity"), r.get("hwm"), r.get("drawdown"))
    return sorted((d, *v) for d, v in by_day.items())


def journal_risk_metrics(series: list[tuple[dt.date, float, float, float]]) -> dict:
    """Same shape as risk_metrics() but derived from journal snapshots."""
    if len(series) < 2:
        return {}
    dates = [d for d, e, h, dd in series]
    equity = [e for d, e, h, dd in series]
    rets = [(equity[i] / equity[i - 1] - 1.0) for i in range(1, len(equity)) if equity[i - 1]]
    if not rets:
        return {}
    mean_r = sum(rets) / len(rets)
    var = sum((r - mean_r) ** 2 for r in rets) / len(rets)
    std = math.sqrt(var)
    downside = [r for r in rets if r < 0]
    dstd = math.sqrt(sum(r ** 2 for r in downside) / len(downside)) if downside else 0.0
    sharpe = (mean_r / std * math.sqrt(252)) if std > 0 else None
    sortino = (mean_r / dstd * math.sqrt(252)) if dstd > 0 else None
    vol = std * math.sqrt(252) * 100 if std > 0 else None

    last_date = dates[-1]
    cutoff = last_date - dt.timedelta(days=WEEK_DAYS)
    week_base = equity[0]
    for d, e in zip(dates, equity):
        if d >= cutoff:
            week_base = e
            break
    week_pl = equity[-1] - week_base
    week_pl_pct = (equity[-1] / week_base - 1) * 100 if week_base else None
    since_pl = equity[-1] - equity[0]
    since_pl_pct = (equity[-1] / equity[0] - 1) * 100 if equity[0] else None

    return {
        "sharpe": sharpe, "sortino": sortino, "vol_annual_pct": vol,
        "week_pl": week_pl, "week_pl_pct": week_pl_pct,
        "since_pl": since_pl, "since_pl_pct": since_pl_pct,
        "n_days": len(equity), "last_date": last_date, "first_date": dates[0],
        "last_equity": equity[-1],
    }


# ---------------------------------------------------------------------------
# HTML assembly
# ---------------------------------------------------------------------------

def _fmt_money(x) -> str:
    if x is None:
        return "n/a"
    return f"${x:,.2f}"


def _fmt_pct(x, digits=2) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.{digits}f}%"


def _pf_str(pf) -> str:
    if pf is None:
        return "n/a"
    if pf == math.inf:
        return "&infin;"
    return f"{pf:.2f}"


def build_html(*, narrative_html: str, state: dict, trades: list[dict],
                alerts: list[dict], alpaca: dict, regime: dict) -> str:
    today = dt.date.today().isoformat()
    week = week_trades(trades)
    week_pnl = sum(t["pnl"] for t in week)

    data_notes = []
    metrics = {}
    equity = None
    metrics_source = None
    if alpaca.get("ok"):
        metrics = risk_metrics(alpaca["history"])
        equity = float(alpaca["account"].equity)
        metrics_source = "alpaca"
    else:
        data_notes.append(f"Alpaca account/equity data unavailable this run: {alpaca.get('reason')}.")
        jseries = load_journal_equity_series()
        metrics = journal_risk_metrics(jseries)
        if metrics:
            equity = metrics["last_equity"]
            metrics_source = "journal"
            data_notes.append(
                f"Using committed journal equity snapshots ({metrics['first_date']} to "
                f"{metrics['last_date']}, pre-open readings, {metrics['n_days']} points) as a "
                "substitute - Sharpe/Sortino/vol are low-confidence on this little history."
            )

    hwm = float(state.get("hwm", 0.0) or 0.0)
    dd = (equity / hwm - 1) * 100 if (equity and hwm > 0) else None

    if not regime.get("ok"):
        data_notes.append(f"Market regime data (yfinance) unavailable this run: {regime.get('reason')}.")

    # ---- account & equity table ----
    acct_rows = []
    if equity is not None:
        label = "Equity" if metrics_source == "alpaca" else f"Equity (journal, as of {metrics.get('last_date')})"
        acct_rows.append((label, _fmt_money(equity)))
    if metrics:
        acct_rows.append(("Week P/L", f"{_fmt_money(metrics['week_pl'])} ({_fmt_pct(metrics['week_pl_pct'])})"))
        acct_rows.append(("Since-inception P/L", f"{_fmt_money(metrics['since_pl'])} ({_fmt_pct(metrics['since_pl_pct'])})"))
        acct_rows.append(("Sharpe (annualized)", f"{metrics['sharpe']:.2f}" if metrics.get("sharpe") is not None else "n/a"))
        acct_rows.append(("Sortino (annualized)", f"{metrics['sortino']:.2f}" if metrics.get("sortino") is not None else "n/a"))
        vol = metrics.get("vol_annual_pct")
        acct_rows.append(("Volatility (annualized)", f"{vol:.1f}%" if vol is not None else "n/a"))
    acct_rows.append(("High-water mark", _fmt_money(hwm) if hwm else "n/a"))
    acct_rows.append(("Drawdown vs HWM", _fmt_pct(dd, 1) if dd is not None else "n/a"))
    acct_html = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in acct_rows)

    # ---- weekly realized trades this run ----
    week_html = ""
    if week:
        week_html = (f"<p><b>Trades closed this week:</b> {len(week)}, "
                     f"net {_fmt_money(week_pnl)}</p>")
    else:
        week_html = "<p><b>Trades closed this week:</b> none</p>"

    # ---- per-sleeve realized performance ----
    sleeve_table = "<table><tr><th>Sleeve</th><th>Trades</th><th>Net P/L</th><th>Win rate</th><th>Profit factor</th><th>Backtest benchmark PF</th></tr>"
    for sk in ("A", "H"):
        s = sleeve_stats(trades, sk)
        bench = BENCHMARK_PF[sk]
        bench_str = " / ".join(f"{k} {v:.2f}" for k, v in bench.items())
        flag = ""
        if s["n"] and s["pf"] is not None and s["pf"] != math.inf and s["pf"] < 1.0:
            flag = ' &#9888;<span style="color:#b00"> decay watch (PF&lt;1.0)</span>'
        if s["n"]:
            sleeve_table += (
                f"<tr><td>{SLEEVE_NAMES[sk]}</td><td>{s['n']}</td><td>{_fmt_money(s['net_pnl'])}</td>"
                f"<td>{s['win_rate']:.0f}%</td><td>{_pf_str(s['pf'])}{flag}</td><td>{bench_str}</td></tr>"
            )
        else:
            sleeve_table += (
                f"<tr><td>{SLEEVE_NAMES[sk]}</td><td>0</td><td>n/a</td><td>n/a</td><td>n/a</td><td>{bench_str}</td></tr>"
            )
    sleeve_table += "</table>"

    # ---- open positions ----
    pos_html = "<p>No open positions.</p>"
    if alpaca.get("ok") and alpaca["positions"]:
        meta = state.get("positions", {})
        rows = []
        for p in sorted(alpaca["positions"], key=lambda p: -abs(float(p.market_value))):
            sk = meta.get(p.symbol, {}).get("sleeve", "?")
            entry = meta.get(p.symbol, {}).get("entry_date", "?")
            rows.append(
                f"<tr><td>{p.symbol}</td><td>{SLEEVE_NAMES.get(sk, sk)}</td><td>{entry}</td>"
                f"<td>{float(p.qty):.4g}</td><td>{_fmt_money(float(p.market_value))}</td>"
                f"<td>{_fmt_pct(float(p.unrealized_plpc) * 100, 1)}</td></tr>"
            )
        pos_html = ("<table><tr><th>Ticker</th><th>Sleeve</th><th>Entry date</th>"
                    "<th>Qty</th><th>Market value</th><th>Unrealized P/L</th></tr>"
                    + "".join(rows) + "</table>")
    elif state.get("positions"):
        # fall back to last-known state.json snapshot (no live price/P&L)
        rows = []
        for t, m in state["positions"].items():
            rows.append(f"<tr><td>{t}</td><td>{SLEEVE_NAMES.get(m.get('sleeve','?'), m.get('sleeve','?'))}</td>"
                        f"<td>{m.get('entry_date','?')}</td><td>{_fmt_money(m.get('entry_px'))}</td></tr>")
        pos_html = ("<p><i>Live prices unavailable - showing last committed state.json snapshot (entry data only).</i></p>"
                    "<table><tr><th>Ticker</th><th>Sleeve</th><th>Entry date</th><th>Entry price</th></tr>"
                    + "".join(rows) + "</table>")

    # ---- market regime ----
    regime_html = "<p>Market regime data unavailable.</p>"
    if regime.get("ok"):
        gate = "ON" if regime["above100"] else "OFF (halted)"
        regime_html = (
            f"<p>As of {regime['asof']}: SPY {_fmt_pct(regime['spy_chg'])} to {regime['spy_close']:.2f}, "
            f"QQQ {_fmt_pct(regime['qqq_chg'])} to {regime.get('qqq_close') or float('nan'):.2f}, "
            f"VIX {regime['vix']:.2f}.<br>"
            f"SPY is {'above' if regime['above200'] else 'below'} its 200-day average; "
            f"Sleeve H momentum gate (SPY&gt;SMA100) is <b>{gate}</b>.</p>"
        )

    # ---- drawdown / circuit breaker posture ----
    if dd is not None:
        if dd <= -20:
            posture = "&#128721; ALL new entries halted (exits continue only)."
        elif dd <= -15:
            posture = "&#9888; Sleeve A entries halted (knife-catcher); Sleeve H entries + all exits continue."
        else:
            posture = "&#9989; No circuit breaker triggered; both sleeves clear to enter."
    else:
        posture = "n/a (equity/HWM comparison unavailable this run)."

    # ---- alerts ----
    alerts_html = "<p>No alerts in the past 7 days.</p>"
    if alerts:
        rows = "".join(
            f"<li>[{a['date']}] {a.get('msg') or a.get('note') or a.get('detail') or a.get('kind')}</li>"
            for a in alerts[:20]
        )
        alerts_html = f"<ul>{rows}</ul>"
        if len(alerts) > 20:
            alerts_html += f"<p><i>...and {len(alerts) - 20} more.</i></p>"

    notes_html = ""
    if data_notes:
        notes_html = "<ul>" + "".join(f"<li>{n}</li>" for n in data_notes) + "</ul>"

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Weekly Portfolio Report - {today}</title>
<style>
body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
h1 {{ font-size: 1.4rem; }}
h2 {{ font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #ddd; padding-bottom: 0.25rem; }}
table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0; }}
td, th {{ border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.92rem; }}
th {{ background: #f5f5f5; }}
.notes {{ background: #fff8e1; border: 1px solid #e0c96a; padding: 0.75rem 1rem; border-radius: 4px; }}
.footer {{ color: #777; font-size: 0.8rem; margin-top: 2rem; }}
</style></head>
<body>
<h1>Weekly Portfolio Report &mdash; {today}</h1>
<p>60/40 A/H ensemble (Sleeve A three-lower-lows mean reversion 60% / Sleeve H 52-week-high momentum 40%). Read-only report; never trades.</p>

{f'<div class="notes">{notes_html}</div>' if notes_html else ''}

<h2>Portfolio manager commentary</h2>
{narrative_html}

<h2>Account &amp; equity</h2>
<table>{acct_html}</table>
{week_html}
<p><b>Drawdown / circuit-breaker posture:</b> {posture}</p>

<h2>Sleeve performance vs backtest benchmark</h2>
{sleeve_table}

<h2>Open positions</h2>
{pos_html}

<h2>Market regime</h2>
{regime_html}

<h2>Alerts (past 7 days)</h2>
{alerts_html}

<div class="footer">Generated by papertrade/report_weekly.py. Data sources: Alpaca (paper account), trades.jsonl, state.json, journal/, yfinance.</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Discord delivery
# ---------------------------------------------------------------------------

def post_to_discord(html_path: Path, summary: str) -> None:
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("DISCORD: no DISCORD_WEBHOOK_URL set - skipping Discord delivery.")
        return
    try:
        import requests

        with html_path.open("rb") as f:
            resp = requests.post(
                webhook,
                data={"payload_json": json.dumps({"content": summary[:1990]})},
                files={"file": (html_path.name, f, "text/html")},
                timeout=30,
            )
        resp.raise_for_status()
        print("DISCORD: posted weekly report to Discord OK.")
    except Exception as e:  # noqa: BLE001
        print(f"DISCORD: upload FAILED: {e}")


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output HTML path")
    ap.add_argument("--narrative-file", help="path to a plain-HTML PM commentary snippet")
    ap.add_argument("--discord", action="store_true", help="post the report to Discord as a file attachment")
    args = ap.parse_args()

    narrative_html = "<p><i>No commentary provided.</i></p>"
    if args.narrative_file:
        p = Path(args.narrative_file)
        if p.exists():
            narrative_html = p.read_text()

    state = load_state()
    trades = load_trades()
    alerts = load_recent_alerts()
    alpaca = fetch_alpaca()
    regime = fetch_market_regime()

    html = build_html(narrative_html=narrative_html, state=state, trades=trades,
                       alerts=alerts, alpaca=alpaca, regime=regime)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    print(f"Wrote {out_path}")

    if not alpaca.get("ok"):
        print(f"NOTE: {alpaca.get('reason')}")
    if not regime.get("ok"):
        print(f"NOTE: {regime.get('reason')}")

    if args.discord:
        summary = f"\U0001F4C8 Weekly Portfolio Report ({dt.date.today().isoformat()}) - see attached."
        post_to_discord(out_path, summary)


if __name__ == "__main__":
    main()
