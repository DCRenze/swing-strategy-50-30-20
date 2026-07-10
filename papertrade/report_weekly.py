"""Generate a self-contained weekly portfolio HTML report (no LLM) and, optionally,
post it to Discord as a file attachment.

A professional-PM wrap-up of the 60/40 A/H ensemble for the trading week: headline
scorecard, equity curve vs SPY, risk metrics, per-sleeve ("per-strategy") realized
performance with backtest-decay flags, the week's activity, open positions, and the
market regime / drawdown-circuit-breaker status. READ-ONLY - never trades.

Data sources, in preference order (degrades gracefully if a source is absent):
  - Alpaca (account/positions) for the live equity + open-position P/L snapshot;
  - papertrade/journal/*.jsonl `run_start` records for the daily equity curve;
  - papertrade/trades.jsonl for the realized closed-trade ledger;
  - papertrade/state.json for open positions + high-water mark;
  - yfinance (SPY/QQQ/^VIX) for benchmarks + regime.
With no Alpaca keys the report still builds from committed repo data (it then reflects
the last committed morning run, not Friday's close). With no network, benchmark/regime
sections show "n/a" but the report still renders.

Output is a single HTML file with inline CSS and matplotlib charts embedded as base64
data URIs - no external assets, so it opens anywhere.

Env: ALPACA_API_KEY, ALPACA_SECRET_KEY (optional), DISCORD_WEBHOOK_URL (for --discord).
Usage:
  python -m papertrade.report_weekly                     # write reports/weekly/<date>.html
  python -m papertrade.report_weekly --out /tmp/wk.html  # custom path
  python -m papertrade.report_weekly --discord           # also post the file to Discord
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
import json
import os
import sys
from collections import defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

# Reuse the daily reporter's pure helpers so the two reports stay consistent.
from papertrade.report_discord import (  # noqa: E402
    NEAR_STOP,
    SLEEVE_NAMES,
    TIME_STOP,
    load_state,
    trading_days_since,
)

HERE = Path(__file__).resolve().parent
JOURNAL_DIR = HERE / "journal"
TRADES_PATH = HERE / "trades.jsonl"
DEFAULT_OUT_DIR = ROOT / "reports" / "weekly"

MAX_POSITIONS = 20
TARGET_WEIGHTS = {"A": 0.60, "H": 0.40}
# Backtest profit-factor benchmarks for the decay watch (PLAYBOOK §8 / REFINEMENT.md).
PF_BENCHMARK = {"A": {"full": 1.30, "oos": 1.19}, "H": {"oos": 1.37}}
DD_HALT_A, DD_HALT_ALL = -0.15, -0.20
TRADING_DAYS = 252


# --------------------------------------------------------------------------- data

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


def load_equity_series():
    """Reconstruct a daily equity curve from journal `run_start` records.

    Returns a pandas Series indexed by date (one non-dry-run point per session,
    the latest snapshot of the day). Empty Series if nothing is available.
    """
    import pandas as pd

    by_date: dict[dt.date, tuple[str, float]] = {}
    for path in sorted(JOURNAL_DIR.glob("*.jsonl")):
        try:
            d = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        for ln in path.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("kind") != "run_start" or r.get("dry_run"):
                continue
            eq = r.get("equity")
            ts = r.get("ts", "")
            if eq is None:
                continue
            # keep the latest snapshot (max ts) for each date
            if d not in by_date or ts >= by_date[d][0]:
                by_date[d] = (ts, float(eq))
    if not by_date:
        return pd.Series(dtype=float)
    idx = sorted(by_date)
    return pd.Series([by_date[d][1] for d in idx],
                     index=pd.to_datetime(idx)).sort_index()


def alpaca_snapshot():
    """Return (account, positions) from Alpaca, or (None, None) without keys/network."""
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        return None, None
    try:
        from alpaca.trading.client import TradingClient

        client = TradingClient(key, secret, paper=True)
        return client.get_account(), list(client.get_all_positions())
    except Exception:  # noqa: BLE001 - report must never fail on a data hiccup
        return None, None


def fetch_market():
    """SPY/QQQ/^VIX close history via yfinance; {} if the network is unavailable."""
    try:
        import yfinance as yf

        raw = yf.download(["SPY", "QQQ", "^VIX"], period="400d",
                          auto_adjust=True, progress=False)
        close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
        return {"close": close}
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------- computing

def week_window(as_of: dt.date) -> tuple[dt.date, dt.date]:
    """Monday .. as_of for the ISO week containing as_of."""
    monday = as_of - dt.timedelta(days=as_of.weekday())
    return monday, as_of


def equity_stats(series, week_start: dt.date, live_equity: float | None) -> dict:
    import pandas as pd

    s = series.copy()
    if live_equity is not None and len(s):
        # freshen the last point with the live account equity
        s.iloc[-1] = live_equity
    elif live_equity is not None:
        s = pd.Series([live_equity], index=[pd.Timestamp(dt.date.today())])
    if not len(s):
        return {"empty": True}
    cur = float(s.iloc[-1])
    incep = float(s.iloc[0])
    ws = pd.Timestamp(week_start)
    prior = s[s.index < ws]
    base = float(prior.iloc[-1]) if len(prior) else float(s[s.index >= ws].iloc[0])
    return {
        "empty": False,
        "series": s,
        "equity": cur,
        "week_pl": cur - base,
        "week_pct": (cur / base - 1) * 100 if base else 0.0,
        "incep_pl": cur - incep,
        "incep_pct": (cur / incep - 1) * 100 if incep else 0.0,
        "incep_base": incep,
        "asof": s.index[-1].date(),
    }


def risk_metrics(series) -> dict:
    if series is None or len(series) < 3:
        return {}
    rets = series.pct_change().dropna()
    if not len(rets):
        return {}
    import numpy as np

    mu, sd = rets.mean(), rets.std(ddof=1)
    downside = rets[rets < 0].std(ddof=1)
    sharpe = (mu / sd * np.sqrt(TRADING_DAYS)) if sd else 0.0
    sortino = (mu / downside * np.sqrt(TRADING_DAYS)) if downside else 0.0
    roll_max = series.cummax()
    dd = series / roll_max - 1.0
    return {
        "sharpe": sharpe,
        "sortino": sortino,
        "vol": sd * np.sqrt(TRADING_DAYS) * 100,
        "maxdd": dd.min() * 100,
        "curdd": dd.iloc[-1] * 100,
        "best": rets.max() * 100,
        "worst": rets.min() * 100,
        "pct_up": (rets > 0).mean() * 100,
        "days": len(rets),
    }


def sleeve_realized(trades: list[dict], week_start: dt.date) -> dict:
    """Per-sleeve realized stats, all-time and this-week."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        groups[t.get("sleeve", "?")].append(t)

    def summarize(ts: list[dict]) -> dict:
        if not ts:
            return {"n": 0, "net": 0.0, "wr": 0.0, "avg_w": 0.0, "avg_l": 0.0,
                    "pf": None, "expectancy": 0.0}
        wins = [t for t in ts if t["pnl"] > 0]
        losses = [t for t in ts if t["pnl"] < 0]
        gross_w = sum(t["pnl"] for t in wins)
        gross_l = -sum(t["pnl"] for t in losses)
        net = sum(t["pnl"] for t in ts)
        return {
            "n": len(ts),
            "net": net,
            "wr": len(wins) / len(ts) * 100,
            "avg_w": (gross_w / len(wins)) if wins else 0.0,
            "avg_l": (-gross_l / len(losses)) if losses else 0.0,
            "pf": (gross_w / gross_l) if gross_l > 0 else None,
            "expectancy": net / len(ts),
        }

    ws = week_start.isoformat()
    out = {}
    for sk in ("A", "H"):
        ts = groups.get(sk, [])
        wk = [t for t in ts if (t.get("exit_date") or "") >= ws]
        out[sk] = {"all": summarize(ts), "week": summarize(wk)}
    return out


def open_position_rows(positions, state: dict) -> list[dict]:
    """Rows for the open-positions table. Uses live Alpaca P/L when available,
    otherwise falls back to state.json (no live market value)."""
    meta = state.get("positions", {})
    rows = []
    if positions:
        for p in positions:
            m = meta.get(p.symbol, {})
            entry = m.get("entry_date")
            held = trading_days_since(entry) if entry else None
            rows.append({
                "sym": p.symbol, "sleeve": m.get("sleeve", "?"),
                "entry": entry, "held": held,
                "qty": float(p.qty), "mv": float(p.market_value),
                "upl": float(p.unrealized_pl), "uplpc": float(p.unrealized_plpc) * 100,
                "near": held is not None and held >= NEAR_STOP,
            })
    else:  # committed-data fallback
        for sym, m in meta.items():
            entry = m.get("entry_date")
            held = trading_days_since(entry) if entry else None
            rows.append({
                "sym": sym, "sleeve": m.get("sleeve", "?"), "entry": entry, "held": held,
                "qty": None, "mv": None, "upl": None, "uplpc": None,
                "near": held is not None and held >= NEAR_STOP,
            })
    return sorted(rows, key=lambda r: (r["sleeve"], -(r["mv"] or 0)))


def week_activity(trades: list[dict], state: dict, week_start: dt.date, as_of: dt.date) -> dict:
    ws, we = week_start.isoformat(), as_of.isoformat()
    closed = [t for t in trades if ws <= (t.get("exit_date") or "") <= we]
    entries = [{"sym": s, **m} for s, m in state.get("positions", {}).items()
               if ws <= (m.get("entry_date") or "") <= we]
    exits_by_reason: dict[str, int] = defaultdict(int)
    for path in sorted(JOURNAL_DIR.glob("*.jsonl")):
        try:
            d = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if not (week_start <= d <= as_of):
            continue
        for ln in path.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("kind") == "exit_reason":
                exits_by_reason[f"{r.get('sleeve', '?')} · {r.get('reason', '?')}"] += 1
    return {"closed": closed, "entries": entries, "exits": dict(exits_by_reason)}


def regime_info(market: dict) -> dict:
    if not market:
        return {}
    import pandas as pd

    close = market["close"]
    try:
        spy = close["SPY"].dropna()
        qqq = close["QQQ"].dropna()
        vix = close["^VIX"].dropna()
    except Exception:  # noqa: BLE001
        return {}
    if len(spy) < 200:
        return {}
    info = {
        "asof": close.index[-1].date(),
        "spy_wk": _wk_return(spy),
        "qqq_wk": _wk_return(qqq),
        "vix": float(vix.iloc[-1]) if len(vix) else None,
        "above200": bool(spy.iloc[-1] > spy.rolling(200).mean().iloc[-1]),
        "gate_on": bool(spy.iloc[-1] > spy.rolling(100).mean().iloc[-1]),
        "spy_series": spy,
    }
    return info


def _wk_return(s) -> float | None:
    """Return over the last 5 sessions, in percent."""
    s = s.dropna()
    if len(s) < 6:
        return None
    return (s.iloc[-1] / s.iloc[-6] - 1) * 100


# ------------------------------------------------------------------------ charts

def _fig_to_data_uri(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    import matplotlib.pyplot as plt

    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()


def equity_chart(series, spy) -> str | None:
    if series is None or len(series) < 2:
        return None
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 3.4), facecolor="#12161d")
    ax.set_facecolor("#12161d")
    port = series / series.iloc[0] * 100
    ax.plot(port.index, port.values, color="#4f9dff", lw=2.2, label="Portfolio")
    if spy is not None and len(spy):
        try:
            b = spy.reindex(series.index, method="ffill").dropna()
            if len(b) >= 2:
                b = b / b.iloc[0] * 100
                ax.plot(b.index, b.values, color="#9aa4b2", lw=1.6, ls="--", label="SPY")
        except Exception:  # noqa: BLE001
            pass
    ax.axhline(100, color="#3a424e", lw=0.8)
    ax.legend(loc="upper left", frameon=False, labelcolor="#c7d0db", fontsize=9)
    _style_axes(ax)
    ax.set_ylabel("Indexed to 100", color="#9aa4b2", fontsize=9)
    return _fig_to_data_uri(fig)


def sleeve_bar(sleeves: dict) -> str | None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels, vals = [], []
    for sk in ("A", "H"):
        labels.append(f"Sleeve {sk}")
        vals.append(sleeves[sk]["all"]["net"])
    if not any(vals):
        return None
    fig, ax = plt.subplots(figsize=(4.2, 3.0), facecolor="#12161d")
    ax.set_facecolor("#12161d")
    colors = ["#3fb950" if v >= 0 else "#f85149" for v in vals]
    ax.bar(labels, vals, color=colors, width=0.55)
    ax.axhline(0, color="#3a424e", lw=0.8)
    _style_axes(ax)
    ax.set_ylabel("Realized net P/L ($)", color="#9aa4b2", fontsize=9)
    for i, v in enumerate(vals):
        ax.text(i, v, f"${v:,.0f}", ha="center",
                va="bottom" if v >= 0 else "top", color="#c7d0db", fontsize=9)
    return _fig_to_data_uri(fig)


def _style_axes(ax) -> None:
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#3a424e")
    ax.tick_params(colors="#9aa4b2", labelsize=8)
    ax.grid(axis="y", color="#20262e", lw=0.7)


# -------------------------------------------------------------------------- HTML

def _cls(v) -> str:
    if v is None:
        return "muted"
    return "pos" if v >= 0 else "neg"


def _money(v, signed=False) -> str:
    if v is None:
        return "—"
    return f"{'+' if signed and v >= 0 else ''}${v:,.2f}"


def _pct(v, signed=True) -> str:
    if v is None:
        return "—"
    return f"{'+' if signed and v >= 0 else ''}{v:.2f}%"


def _pf_flag(sk: str, pf) -> str:
    """Decay flag: compare realized PF to the backtest benchmark."""
    if pf is None:
        return '<span class="muted">n/a</span>'
    bench = PF_BENCHMARK[sk].get("oos") or PF_BENCHMARK[sk].get("full")
    if pf >= bench:
        return f'<span class="pf ok">{pf:.2f} ✓ ≥ {bench:.2f} bench</span>'
    if pf >= 1.0:
        return f'<span class="pf warn">{pf:.2f} ⚠ &lt; {bench:.2f} bench</span>'
    return f'<span class="pf bad">{pf:.2f} ✗ &lt; 1.0 — decay watch</span>'


def tile(label: str, value: str, sub: str = "", cls: str = "") -> str:
    sub_html = f'<div class="tile-sub {cls}">{sub}</div>' if sub else ""
    return (f'<div class="tile"><div class="tile-label">{escape(label)}</div>'
            f'<div class="tile-val {cls}">{value}</div>{sub_html}</div>')


def build_html(ctx: dict) -> str:
    eq = ctx["equity"]
    rm = ctx["risk"]
    sl = ctx["sleeves"]
    reg = ctx["regime"]
    week_start, as_of = ctx["week_start"], ctx["as_of"]

    # ---- scorecard tiles
    tiles = []
    if not eq.get("empty"):
        tiles.append(tile("Equity", _money(eq["equity"]),
                          f"as of {eq['asof']}"))
        tiles.append(tile("Week P/L", _money(eq["week_pl"], signed=True),
                          _pct(eq["week_pct"]), _cls(eq["week_pl"])))
        tiles.append(tile("Since inception", _money(eq["incep_pl"], signed=True),
                          _pct(eq["incep_pct"]) + f" · base ${eq['incep_base']:,.0f}",
                          _cls(eq["incep_pl"])))
    if ctx["dd"] is not None:
        halt = ("ALL entries halted" if ctx["dd"] <= DD_HALT_ALL
                else "Sleeve A halted" if ctx["dd"] <= DD_HALT_A else "normal")
        tiles.append(tile("Drawdown vs HWM", _pct(ctx["dd"] * 100, signed=False),
                          f"circuit breaker: {halt}",
                          "neg" if ctx["dd"] <= DD_HALT_A else ""))
    if ctx["invested_pct"] is not None:
        tiles.append(tile("Invested", f"{ctx['invested_pct']:.0f}%",
                          f"cash {100 - ctx['invested_pct']:.0f}%"))
    if reg:
        alpha = None
        if not eq.get("empty") and reg.get("spy_wk") is not None:
            alpha = eq["week_pct"] - reg["spy_wk"]
        tiles.append(tile("Week vs SPY",
                          _pct(reg["spy_wk"]) if reg.get("spy_wk") is not None else "—",
                          (f"alpha {_pct(alpha)}" if alpha is not None else
                           f"QQQ {_pct(reg.get('qqq_wk'))}"),
                          _cls(alpha) if alpha is not None else ""))

    # ---- risk metrics row
    risk_html = '<p class="muted">Not enough equity history yet for risk metrics.</p>'
    if rm:
        risk_html = '<div class="metrics">' + "".join(
            f'<div class="metric"><span>{lbl}</span><b class="{cls}">{val}</b></div>'
            for lbl, val, cls in [
                ("Sharpe (ann.)", f"{rm['sharpe']:.2f}", _cls(rm['sharpe'])),
                ("Sortino (ann.)", f"{rm['sortino']:.2f}", _cls(rm['sortino'])),
                ("Volatility (ann.)", f"{rm['vol']:.1f}%", ""),
                ("Max drawdown", f"{rm['maxdd']:.1f}%", "neg"),
                ("Current drawdown", f"{rm['curdd']:.1f}%", _cls(rm['curdd'])),
                ("Best day", f"{rm['best']:+.2f}%", "pos"),
                ("Worst day", f"{rm['worst']:+.2f}%", "neg"),
                ("Up days", f"{rm['pct_up']:.0f}%", ""),
            ]) + f'</div><p class="fine">Computed from {rm["days"]} daily returns.</p>'

    # ---- per-sleeve table
    sleeve_rows = ""
    for sk in ("A", "H"):
        a, w = sl[sk]["all"], sl[sk]["week"]
        cap = ctx["sleeve_cap_pct"].get(sk)
        tgt = TARGET_WEIGHTS[sk] * 100
        drift = (cap - tgt) if cap is not None else None
        cap_cell = (f"{cap:.0f}% <span class='fine'>/ {tgt:.0f}% tgt "
                    f"({drift:+.0f})</span>" if cap is not None else f"— / {tgt:.0f}% tgt")
        upl = ctx["sleeve_upl"].get(sk)
        sleeve_rows += (
            f"<tr><td><b>{escape(SLEEVE_NAMES[sk])}</b></td>"
            f"<td class='{_cls(a['net'])}'>{_money(a['net'], signed=True)}</td>"
            f"<td>{a['n']}</td><td>{a['wr']:.0f}%</td>"
            f"<td class='pos'>{_money(a['avg_w'])}</td>"
            f"<td class='neg'>{_money(a['avg_l'])}</td>"
            f"<td class='{_cls(a['expectancy'])}'>{_money(a['expectancy'], signed=True)}</td>"
            f"<td>{_pf_flag(sk, a['pf'])}</td>"
            f"<td class='{_cls(w['net'])}'>{_money(w['net'], signed=True)} "
            f"<span class='fine'>({w['n']})</span></td>"
            f"<td>{cap_cell}</td>"
            f"<td class='{_cls(upl)}'>{_money(upl, signed=True)}</td></tr>"
        )

    # ---- activity
    act = ctx["activity"]
    exits_html = ("".join(f"<li>{escape(k)} ×{v}</li>" for k, v in act["exits"].items())
                  or "<li class='muted'>none</li>")
    closed_rows = "".join(
        f"<tr><td>{escape(t['ticker'])}</td><td>{t.get('sleeve', '?')}</td>"
        f"<td>{t.get('entry_date', '')}</td><td>{t.get('exit_date', '')}</td>"
        f"<td class='{_cls(t['pnl'])}'>{_money(t['pnl'], signed=True)}</td>"
        f"<td class='{_cls(t['ret'])}'>{t['ret'] * 100:+.1f}%</td></tr>"
        for t in sorted(act["closed"], key=lambda t: t["pnl"], reverse=True))
    closed_html = (f"<table class='grid'><thead><tr><th>Ticker</th><th>Sleeve</th>"
                   f"<th>Entry</th><th>Exit</th><th>P/L</th><th>Return</th></tr></thead>"
                   f"<tbody>{closed_rows}</tbody></table>" if closed_rows
                   else "<p class='muted'>No positions closed this week.</p>")

    # ---- open positions
    pos_rows = ""
    for r in ctx["positions"]:
        warn = " ⏳" if r["near"] else ""
        pos_rows += (
            f"<tr><td>{escape(r['sym'])}{warn}</td><td>{r['sleeve']}</td>"
            f"<td>{r['entry'] or '—'}</td>"
            f"<td>{r['held'] if r['held'] is not None else '—'}</td>"
            f"<td>{('%.4g' % r['qty']) if r['qty'] is not None else '—'}</td>"
            f"<td>{_money(r['mv'])}</td>"
            f"<td class='{_cls(r['upl'])}'>{_money(r['upl'], signed=True)}</td>"
            f"<td class='{_cls(r['uplpc'])}'>{_pct(r['uplpc'])}</td></tr>"
        )
    pos_html = (f"<table class='grid'><thead><tr><th>Symbol</th><th>Sleeve</th>"
                f"<th>Entry</th><th>Days</th><th>Qty</th><th>Mkt value</th>"
                f"<th>Unreal. P/L</th><th>%</th></tr></thead><tbody>{pos_rows}</tbody></table>"
                if pos_rows else "<p class='muted'>No open positions.</p>")

    # ---- regime
    if reg:
        gate = "ON" if reg["gate_on"] else "OFF"
        regime_html = (
            f"<ul class='plain'>"
            f"<li>SPY {'above' if reg['above200'] else 'below'} its 200-day average — "
            f"trend {'healthy' if reg['above200'] else 'weak'}</li>"
            f"<li>Momentum gate (SPY &gt; SMA100): <b>{gate}</b> — Sleeve H entries "
            f"{'permitted' if reg['gate_on'] else 'stood down'}</li>"
            f"<li>VIX: {reg['vix']:.1f}</li>"
            f"<li>Week: SPY {_pct(reg.get('spy_wk'))} · QQQ {_pct(reg.get('qqq_wk'))}</li>"
            f"</ul>")
    else:
        regime_html = "<p class='muted'>Market data unavailable (no network) — regime n/a.</p>"

    alerts_html = ("".join(f"<li>{escape(a)}</li>" for a in ctx["alerts"])
                   if ctx["alerts"] else "<li class='muted'>none this week</li>")

    charts = ""
    if ctx["equity_chart"]:
        charts += f'<img src="{ctx["equity_chart"]}" alt="Equity curve"/>'
    sb = ""
    if ctx["sleeve_chart"]:
        sb = f'<img class="half" src="{ctx["sleeve_chart"]}" alt="Sleeve P/L"/>'

    narrative = ctx.get("narrative") or (
        "<em>Portfolio-manager commentary is added here by the weekly Claude routine.</em>")

    return _PAGE.format(
        title=f"Weekly Portfolio Report — {as_of}",
        week=f"{week_start:%b %d} – {as_of:%b %d, %Y}",
        generated=ctx["generated"],
        tiles="".join(tiles) or "<p class='muted'>No data available.</p>",
        equity_chart=charts,
        risk=risk_html,
        sleeve_rows=sleeve_rows,
        sleeve_chart=sb,
        exits=exits_html,
        closed=closed_html,
        positions=pos_html,
        regime=regime_html,
        alerts=alerts_html,
        narrative=narrative,
    )


_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:#0d1014;color:#c7d0db;font:15px/1.5 -apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:960px;margin:0 auto;padding:28px 20px 60px}}
h1{{font-size:24px;margin:0 0 2px}}
h2{{font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:#8b96a5;
margin:34px 0 12px;border-bottom:1px solid #232a33;padding-bottom:6px}}
.sub{{color:#8b96a5;font-size:13px;margin:0 0 4px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:18px}}
.tile{{background:#12161d;border:1px solid #232a33;border-radius:10px;padding:14px 16px}}
.tile-label{{font-size:12px;color:#8b96a5;text-transform:uppercase;letter-spacing:.04em}}
.tile-val{{font-size:22px;font-weight:600;margin-top:4px}}
.tile-sub{{font-size:12px;color:#8b96a5;margin-top:2px}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.metric{{background:#12161d;border:1px solid #232a33;border-radius:8px;padding:10px 12px;
display:flex;justify-content:space-between;align-items:baseline}}
.metric span{{color:#8b96a5;font-size:13px}}
.metric b{{font-size:16px}}
table.grid{{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:8px;
display:block;overflow-x:auto}}
table.grid th{{text-align:left;color:#8b96a5;font-weight:600;font-size:12px;
text-transform:uppercase;letter-spacing:.03em;padding:8px 10px;border-bottom:1px solid #232a33}}
table.grid td{{padding:8px 10px;border-bottom:1px solid #1a2029;white-space:nowrap}}
table.grid tbody tr:hover{{background:#12161d}}
img{{max-width:100%;border-radius:10px;margin-top:8px;background:#12161d}}
img.half{{max-width:360px}}
.pos{{color:#3fb950}}.neg{{color:#f85149}}.muted{{color:#6b7684}}
.fine{{color:#6b7684;font-size:12px}}
.pf{{font-size:12.5px;padding:1px 7px;border-radius:20px}}
.pf.ok{{background:#12341c;color:#3fb950}}.pf.warn{{background:#3a300f;color:#e3b341}}
.pf.bad{{background:#3a1414;color:#f85149}}
ul.plain,ul.cols{{margin:6px 0;padding-left:18px}}ul.plain li{{margin:3px 0}}
.narrative{{background:#12161d;border:1px solid #232a33;border-left:3px solid #4f9dff;
border-radius:8px;padding:14px 18px;margin-top:10px}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
@media(max-width:640px){{.two{{grid-template-columns:1fr}}}}
footer{{margin-top:40px;color:#6b7684;font-size:12px;border-top:1px solid #232a33;padding-top:14px}}
</style></head>
<body><div class="wrap">
<h1>📊 Weekly Portfolio Report</h1>
<p class="sub">60/40 A/H swing ensemble · trading week {week}</p>
<p class="sub">Generated {generated}</p>
<div class="tiles">{tiles}</div>

<h2>Portfolio-manager commentary</h2>
<div class="narrative">{narrative}</div>

<h2>Equity curve</h2>
{equity_chart}

<h2>Risk metrics</h2>
{risk}

<h2>Per-strategy performance (sleeves)</h2>
<table class="grid"><thead><tr>
<th>Sleeve</th><th>Net P/L (all-time)</th><th>Trades</th><th>Win %</th>
<th>Avg win</th><th>Avg loss</th><th>Expectancy</th><th>Profit factor vs backtest</th>
<th>Net P/L (week)</th><th>Capital</th><th>Open P/L</th></tr></thead>
<tbody>{sleeve_rows}</tbody></table>
{sleeve_chart}

<h2>This week's activity</h2>
<h3 style="color:#8b96a5;font-size:13px;margin:0 0 4px">Exits triggered</h3>
<ul class="plain">{exits}</ul>
<h3 style="color:#8b96a5;font-size:13px;margin:16px 0 4px">Closed trades</h3>
{closed}

<h2>Open positions</h2>
{positions}

<h2>Market regime &amp; guardrails</h2>
{regime}
<h3 style="color:#8b96a5;font-size:13px;margin-top:14px">Alerts this week</h3>
<ul class="plain">{alerts}</ul>

<footer>
Paper trading on Alpaca. Long-only 60/40 A/H ensemble (see <code>playbook/PLAYBOOK.md</code>).
Backtest carries survivorship bias; past performance does not guarantee future results.
This is an automated internal report, not investment advice.
</footer>
</div></body></html>"""


# ------------------------------------------------------------------- orchestration

def collect_alerts(week_start: dt.date, as_of: dt.date) -> list[str]:
    alerts = []
    for path in sorted(JOURNAL_DIR.glob("*.jsonl")):
        try:
            d = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if not (week_start <= d <= as_of):
            continue
        for ln in path.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("kind") in ("action_needed", "unattributed_position"):
                alerts.append(r.get("msg") or r.get("note") or "")
    return [a for a in alerts if a][:8]


def generate(narrative: str | None = None) -> tuple[str, dict]:
    """Build the report HTML. Returns (html, summary_ctx)."""
    state = load_state()
    trades = load_trades()
    series = load_equity_series()
    account, positions = alpaca_snapshot()
    market = fetch_market()

    live_equity = float(account.equity) if account is not None else None
    as_of = (series.index[-1].date() if len(series)
             else (dt.date.today()))
    week_start, as_of = week_window(as_of)

    eq = equity_stats(series, week_start, live_equity)
    rm = risk_metrics(eq["series"]) if not eq.get("empty") else {}

    # drawdown vs HWM
    hwm = float(state.get("hwm", 0.0) or 0.0)
    cur_eq = live_equity if live_equity is not None else (eq["equity"] if not eq.get("empty") else None)
    dd = (cur_eq / hwm - 1.0) if (hwm > 0 and cur_eq) else None

    # invested % + per-sleeve capital & unrealized P/L (needs live positions)
    invested_pct = None
    sleeve_cap_pct: dict[str, float] = {}
    sleeve_upl: dict[str, float] = {}
    if account is not None and positions is not None:
        equity = float(account.equity)
        mv = sum(float(p.market_value) for p in positions)
        invested_pct = (mv / equity * 100) if equity else None
        meta = state.get("positions", {})
        by_cap, by_upl = defaultdict(float), defaultdict(float)
        for p in positions:
            sk = meta.get(p.symbol, {}).get("sleeve", "?")
            by_cap[sk] += float(p.market_value)
            by_upl[sk] += float(p.unrealized_pl)
        for sk in ("A", "H"):
            sleeve_cap_pct[sk] = (by_cap[sk] / equity * 100) if equity else 0.0
            sleeve_upl[sk] = by_upl[sk]

    spy = market.get("close", {})
    spy_series = None
    if len(spy) if hasattr(spy, "__len__") else False:
        try:
            spy_series = spy["SPY"].dropna()
        except Exception:  # noqa: BLE001
            spy_series = None

    ctx = {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "week_start": week_start, "as_of": as_of,
        "equity": eq, "risk": rm, "dd": dd, "invested_pct": invested_pct,
        "sleeves": sleeve_realized(trades, week_start),
        "sleeve_cap_pct": sleeve_cap_pct, "sleeve_upl": sleeve_upl,
        "positions": open_position_rows(positions, state),
        "activity": week_activity(trades, state, week_start, as_of),
        "regime": regime_info(market),
        "alerts": collect_alerts(week_start, as_of),
        "narrative": narrative,
        "equity_chart": equity_chart(eq.get("series"), spy_series),
        "sleeve_chart": None,
    }
    ctx["sleeve_chart"] = sleeve_bar(ctx["sleeves"])
    return build_html(ctx), ctx


def summary_line(ctx: dict) -> str:
    eq = ctx["equity"]
    parts = [f"📊 Weekly report — week ending {ctx['as_of']}"]
    if not eq.get("empty"):
        parts.append(f"Equity ${eq['equity']:,.0f} (week {eq['week_pct']:+.2f}%, "
                     f"since inception {eq['incep_pct']:+.2f}%)")
    a, h = ctx["sleeves"]["A"]["all"], ctx["sleeves"]["H"]["all"]
    parts.append(f"Realized net — A ${a['net']:+,.0f} / H ${h['net']:+,.0f}")
    return " · ".join(parts)


def post_file_to_discord(webhook: str, filepath: Path, message: str) -> None:
    """Upload the HTML file to a Discord webhook as an attachment (multipart)."""
    import requests

    with open(filepath, "rb") as fh:
        files = {"files[0]": (filepath.name, fh, "text/html")}
        data = {"payload_json": json.dumps({"content": message[:1990]})}
        resp = requests.post(webhook, data=data, files=files, timeout=30)
        resp.raise_for_status()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Weekly portfolio HTML report")
    ap.add_argument("--out", type=Path, default=None, help="output HTML path")
    ap.add_argument("--discord", action="store_true", help="also post the file to Discord")
    ap.add_argument("--narrative", type=str, default=None,
                    help="optional PM commentary (HTML) to inject; or set via routine")
    args = ap.parse_args()

    html, ctx = generate(narrative=args.narrative)

    out = args.out
    if out is None:
        DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = DEFAULT_OUT_DIR / f"{ctx['as_of'].isoformat()}.html"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}  ({len(html):,} bytes)")

    if args.discord:
        webhook = os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook:
            print("No DISCORD_WEBHOOK_URL set - skipping Discord upload.")
            return
        try:
            post_file_to_discord(webhook, out, summary_line(ctx))
            print("Posted weekly report to Discord.")
        except Exception as e:  # noqa: BLE001 - a report failure must never break a pipeline
            print(f"Discord upload failed (ignored): {e}")


if __name__ == "__main__":
    main()
