"""Generate a self-contained weekly portfolio HTML report (no LLM) and, optionally,
post it to Discord as a file attachment.

A professional-PM analyst dashboard for the 60/40 A/H ensemble: a KPI hero row,
equity curve + underwater drawdown, an allocation donut, per-sleeve ("per-strategy")
cards with win-rate bars and profit-factor gauges vs the backtest benchmark, a
cumulative realized-P/L-by-sleeve chart, the week's activity, open positions, and the
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

Output is a single HTML file with inline CSS, matplotlib charts embedded as base64
data URIs, and inline SVG - no external assets, so it opens anywhere (incl. Discord).

Palette: validated dark categorical hues (sleeve A = blue, H = orange) on surface
#1a1a19, plus reserved good/critical status colors for P/L - see the dataviz skill.

Env: ALPACA_API_KEY, ALPACA_SECRET_KEY (optional), DISCORD_WEBHOOK_URL (for --discord).
Usage:
  python -m papertrade.report_weekly                        # write reports/weekly/<date>.html
  python -m papertrade.report_weekly --out /tmp/wk.html     # custom path
  python -m papertrade.report_weekly --narrative-file c.html  # inject PM commentary from a file
  python -m papertrade.report_weekly --discord              # also post the file to Discord
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

# Validated dark palette (dataviz skill, surface #1a1a19). A/H are categorical slots
# with ΔE 97.3 separation; pos/neg are reserved status colors, never used as a series.
C = {
    "surface": "#181a1f", "panel": "#1f232b", "page": "#0c0e12",
    "ink": "#f4f6f8", "sec": "#c3c2b7", "muted": "#8a8f98",
    "grid": "#262a32", "axis": "#3a3f48",
    "A": "#3987e5", "H": "#d95926", "total": "#c3c2b7", "cash": "#3a3f48",
    "pos": "#3fb950", "neg": "#f0503c", "warn": "#e3b341", "serious": "#ec835a",
}


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
                    "pf": None, "expectancy": 0.0, "wins": 0, "losses": 0}
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
            "wins": len(wins), "losses": len(losses),
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
    close = market["close"]
    try:
        spy = close["SPY"].dropna()
        qqq = close["QQQ"].dropna()
        vix = close["^VIX"].dropna()
    except Exception:  # noqa: BLE001
        return {}
    if len(spy) < 200:
        return {}
    return {
        "asof": close.index[-1].date(),
        "spy_wk": _wk_return(spy),
        "qqq_wk": _wk_return(qqq),
        "vix": float(vix.iloc[-1]) if len(vix) else None,
        "above200": bool(spy.iloc[-1] > spy.rolling(200).mean().iloc[-1]),
        "gate_on": bool(spy.iloc[-1] > spy.rolling(100).mean().iloc[-1]),
        "spy_series": spy,
    }


def _wk_return(s) -> float | None:
    """Return over the last 5 sessions, in percent."""
    s = s.dropna()
    if len(s) < 6:
        return None
    return (s.iloc[-1] / s.iloc[-6] - 1) * 100


# ------------------------------------------------------------------------ charts

def _new_fig(w, h):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(w, h), facecolor=C["surface"])
    return fig, plt


def _fig_to_data_uri(fig) -> str:
    import matplotlib.pyplot as plt

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=C["surface"])
    buf.seek(0)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()


def _style_axes(ax) -> None:
    ax.set_facecolor(C["surface"])
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(C["axis"])
    ax.tick_params(colors=C["muted"], labelsize=8)
    ax.grid(axis="y", color=C["grid"], lw=0.7)


def equity_underwater_chart(series, spy) -> str | None:
    """Equity vs SPY (top) with a filled underwater-drawdown panel (bottom)."""
    if series is None or len(series) < 2:
        return None
    fig, plt = _new_fig(9.2, 4.3)
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1.15], hspace=0.12)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    port = series / series.iloc[0] * 100
    ax1.plot(port.index, port.values, color=C["A"], lw=2.4, label="Portfolio")
    if spy is not None and len(spy):
        try:
            b = spy.reindex(series.index, method="ffill").dropna()
            if len(b) >= 2:
                b = b / b.iloc[0] * 100
                ax1.plot(b.index, b.values, color=C["sec"], lw=1.6, ls="--", label="SPY")
        except Exception:  # noqa: BLE001
            pass
    ax1.axhline(100, color=C["axis"], lw=0.8)
    ax1.legend(loc="upper left", frameon=False, labelcolor=C["sec"], fontsize=9)
    _style_axes(ax1)
    ax1.set_ylabel("Indexed to 100", color=C["muted"], fontsize=9)
    plt.setp(ax1.get_xticklabels(), visible=False)

    dd = (series / series.cummax() - 1.0) * 100
    ax2.fill_between(dd.index, dd.values, 0, color=C["neg"], alpha=0.28)
    ax2.plot(dd.index, dd.values, color=C["neg"], lw=1.4)
    ax2.axhline(0, color=C["axis"], lw=0.8)
    _style_axes(ax2)
    ax2.set_ylabel("Drawdown %", color=C["muted"], fontsize=9)
    if dd.min() < 0:
        ax2.set_ylim(min(dd.min() * 1.25, -0.1), 0.5)
    for lbl in ax2.get_xticklabels():
        lbl.set_rotation(0)
    return _fig_to_data_uri(fig)


def cumulative_pl_chart(trades: list[dict]) -> str | None:
    """Cumulative realized P/L over time, per sleeve + total (from the ledger)."""
    if not trades:
        return None
    import pandas as pd

    df = pd.DataFrame(trades)
    if "exit_date" not in df or "pnl" not in df:
        return None
    df = df.dropna(subset=["exit_date"]).copy()
    if df.empty:
        return None
    df["exit_date"] = pd.to_datetime(df["exit_date"])
    df = df.sort_values("exit_date")

    fig, plt = _new_fig(9.2, 3.2)
    ax = fig.add_subplot(111)
    plotted = False
    for sk in ("A", "H"):
        sub = df[df["sleeve"] == sk]
        if len(sub):
            cum = sub["pnl"].cumsum().values
            ax.plot(sub["exit_date"], cum, color=C[sk], lw=2.2, marker="o", ms=4,
                    label=f"Sleeve {sk}")
            ax.annotate(f"${cum[-1]:+,.0f}", (sub["exit_date"].iloc[-1], cum[-1]),
                        textcoords="offset points", xytext=(6, 0), va="center",
                        color=C[sk], fontsize=8.5, fontweight="bold")
            plotted = True
    tot = df["pnl"].cumsum().values
    ax.plot(df["exit_date"], tot, color=C["total"], lw=1.5, ls="--", label="Total")
    ax.axhline(0, color=C["axis"], lw=0.9)
    _style_axes(ax)
    if plotted:
        ax.legend(loc="upper left", frameon=False, labelcolor=C["sec"], fontsize=9, ncol=3)
    ax.set_ylabel("Cumulative realized P/L ($)", color=C["muted"], fontsize=9)
    fig.autofmt_xdate(rotation=0)
    return _fig_to_data_uri(fig)


def allocation_donut(sleeve_cap_pct: dict, invested_pct: float | None) -> str | None:
    """Donut of live capital A/H/cash; falls back to the 60/40 target when no
    live positions are available."""
    fig, plt = _new_fig(3.5, 3.2)
    ax = fig.add_subplot(111)
    if sleeve_cap_pct and invested_pct is not None:
        a = max(sleeve_cap_pct.get("A", 0.0), 0.0)
        h = max(sleeve_cap_pct.get("H", 0.0), 0.0)
        cash = max(100.0 - a - h, 0.0)
        vals = [a, h, cash]
        cols = [C["A"], C["H"], C["cash"]]
        labels = [f"A {a:.0f}%", f"H {h:.0f}%", f"Cash {cash:.0f}%"]
        center = f"{invested_pct:.0f}%\ninvested"
    else:
        vals = [60, 40]
        cols = [C["A"], C["H"]]
        labels = ["A 60%", "H 40%"]
        center = "target\n60 / 40"
    wedges, _ = ax.pie(vals, colors=cols, startangle=90,
                       wedgeprops=dict(width=0.42, edgecolor=C["surface"], linewidth=2))
    ax.text(0, 0, center, ha="center", va="center", color=C["ink"],
            fontsize=12, fontweight="bold", linespacing=1.3)
    ax.legend(wedges, labels, loc="center", bbox_to_anchor=(0.5, -0.08),
              ncol=3, frameon=False, labelcolor=C["sec"], fontsize=8.5,
              handlelength=1, columnspacing=1.1)
    ax.set(aspect="equal")
    return _fig_to_data_uri(fig)


def sparkline_svg(series, w=132, h=34) -> str:
    """Inline SVG sparkline of the equity series (crisp, no raster)."""
    if series is None or len(series) < 2:
        return ""
    ys = [float(v) for v in series.values]
    lo, hi = min(ys), max(ys)
    rng = (hi - lo) or 1.0
    n = len(ys)
    pad = 3
    pts = []
    for i, y in enumerate(ys):
        x = pad + i * (w - 2 * pad) / (n - 1)
        yy = pad + (h - 2 * pad) * (1 - (y - lo) / rng)
        pts.append(f"{x:.1f},{yy:.1f}")
    up = ys[-1] >= ys[0]
    col = C["pos"] if up else C["neg"]
    last = pts[-1].split(",")
    return (f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'preserveAspectRatio="none" aria-hidden="true">'
            f'<polyline fill="none" stroke="{col}" stroke-width="1.8" '
            f'stroke-linejoin="round" stroke-linecap="round" points="{" ".join(pts)}"/>'
            f'<circle cx="{last[0]}" cy="{last[1]}" r="2.4" fill="{col}"/></svg>')


# -------------------------------------------------------------------------- HTML

def _cls(v) -> str:
    if v is None:
        return "muted"
    return "pos" if v >= 0 else "neg"


def _arrow(v) -> str:
    if v is None:
        return ""
    return "▲" if v >= 0 else "▼"


def _money(v, signed=False) -> str:
    if v is None:
        return "—"
    return f"{'+' if signed and v >= 0 else ''}${v:,.2f}"


def _money0(v, signed=False) -> str:
    if v is None:
        return "—"
    return f"{'+' if signed and v >= 0 else ''}${v:,.0f}"


def _pct(v, signed=True) -> str:
    if v is None:
        return "—"
    return f"{'+' if signed and v >= 0 else ''}{v:.2f}%"


def _pf_bucket(sk: str, pf) -> tuple[str, str, float]:
    """(status_class, label, benchmark) for a sleeve's realized profit factor."""
    bench = PF_BENCHMARK[sk].get("oos") or PF_BENCHMARK[sk].get("full")
    if pf is None:
        return "muted", "n/a", bench
    if pf >= bench:
        return "ok", f"{pf:.2f} — at/above {bench:.2f} benchmark", bench
    if pf >= 1.0:
        return "warn", f"{pf:.2f} — below {bench:.2f} benchmark", bench
    return "bad", f"{pf:.2f} — below 1.0 · decay watch", bench


def kpi(label, value, sub="", cls="", arrow="", extra="") -> str:
    arrow_html = f'<span class="kpi-arrow {cls}">{arrow}</span>' if arrow else ""
    sub_html = f'<div class="kpi-sub {cls}">{sub}</div>' if sub else ""
    return (f'<div class="kpi"><div class="kpi-label">{escape(label)}</div>'
            f'<div class="kpi-val {cls}">{value}{arrow_html}</div>{sub_html}{extra}</div>')


def bar(pct, color, track=None) -> str:
    track = track or "var(--grid)"
    pct = max(0.0, min(100.0, pct))
    return (f'<div class="track" style="background:{track}">'
            f'<div class="fill" style="width:{pct:.1f}%;background:{color}"></div></div>')


def pf_gauge(sk, pf) -> str:
    """A horizontal gauge: fill to PF on a 0..2 scale, benchmark tick, status color."""
    status, _, bench = _pf_bucket(sk, pf)
    color = {"ok": C["pos"], "warn": C["warn"], "bad": C["neg"], "muted": C["muted"]}[status]
    scale = 2.0
    fill = 0.0 if pf is None else min(pf, scale) / scale * 100
    tick = min(bench, scale) / scale * 100
    pf_txt = "—" if pf is None else f"{pf:.2f}"
    return (
        f'<div class="gauge-row"><span class="gauge-cap">Profit factor</span>'
        f'<b class="{status}">{pf_txt}</b><span class="gauge-bench">bench {bench:.2f}</span></div>'
        f'<div class="gauge"><div class="gauge-fill" style="width:{fill:.1f}%;background:{color}"></div>'
        f'<div class="gauge-tick" style="left:{tick:.1f}%"></div></div>')


def sleeve_card(sk, data, cap_pct, upl) -> str:
    a = data["all"]
    w = data["week"]
    tgt = TARGET_WEIGHTS[sk] * 100
    drift = (cap_pct - tgt) if cap_pct is not None else None
    cap_txt = (f"{cap_pct:.0f}% <span class='fine'>vs {tgt:.0f}% target "
               f"({drift:+.0f})</span>" if cap_pct is not None
               else f"<span class='fine'>target {tgt:.0f}%</span>")
    wr_color = C["pos"] if a["wr"] >= 50 else C["warn"]
    # avg win / avg loss mini-bars (scaled to the larger magnitude)
    mag = max(a["avg_w"], -a["avg_l"] if a["avg_l"] else 0, 1)
    return (
        f'<div class="scard" style="border-top:3px solid {C[sk]}">'
        f'<div class="scard-head"><span class="dot" style="background:{C[sk]}"></span>'
        f'<b>{escape(SLEEVE_NAMES[sk])}</b></div>'
        f'<div class="scard-cap">Capital: {cap_txt}</div>'
        f'<div class="scard-net {_cls(a["net"])}">{_money(a["net"], signed=True)}'
        f'<span class="scard-net-lbl">realized · all-time</span></div>'
        f'<div class="scard-grid">'
        f'<div><span>Trades</span><b>{a["n"]}</b></div>'
        f'<div><span>Win rate</span><b>{a["wr"]:.0f}%</b></div>'
        f'<div><span>This week</span><b class="{_cls(w["net"])}">{_money0(w["net"], signed=True)} '
        f'<span class="fine">({w["n"]})</span></b></div>'
        f'<div><span>Open P/L</span><b class="{_cls(upl)}">{_money0(upl, signed=True)}</b></div>'
        f'</div>'
        f'<div class="scard-barlbl">Win rate {a["wr"]:.0f}% '
        f'<span class="fine">({a["wins"]}W / {a["losses"]}L)</span></div>'
        f'{bar(a["wr"], wr_color)}'
        f'{pf_gauge(sk, a["pf"])}'
        f'<div class="scard-avg"><div class="avgcol">'
        f'<span class="fine">Avg win</span>{bar(a["avg_w"] / mag * 100, C["pos"])}'
        f'<b class="pos">{_money0(a["avg_w"])}</b></div>'
        f'<div class="avgcol"><span class="fine">Avg loss</span>'
        f'{bar(-a["avg_l"] / mag * 100 if a["avg_l"] else 0, C["neg"])}'
        f'<b class="neg">{_money0(a["avg_l"])}</b></div></div>'
        f'</div>')


def chip(text, kind="") -> str:
    return f'<span class="chip {kind}">{text}</span>'


def build_html(ctx: dict) -> str:
    eq = ctx["equity"]
    rm = ctx["risk"]
    sl = ctx["sleeves"]
    reg = ctx["regime"]
    week_start, as_of = ctx["week_start"], ctx["as_of"]

    # ---- KPI hero row
    kpis = []
    if not eq.get("empty"):
        spark = sparkline_svg(eq["series"])
        kpis.append(kpi("Equity", _money0(eq["equity"]), f"as of {eq['asof']}", "",
                        extra=f'<div class="kpi-spark">{spark}</div>'))
        kpis.append(kpi("Week P/L", _money0(eq["week_pl"], signed=True),
                        _pct(eq["week_pct"]), _cls(eq["week_pl"]), _arrow(eq["week_pl"])))
        kpis.append(kpi("Since inception", _money0(eq["incep_pl"], signed=True),
                        _pct(eq["incep_pct"]), _cls(eq["incep_pl"]), _arrow(eq["incep_pl"])))
    if rm:
        kpis.append(kpi("Max drawdown", f"{rm['maxdd']:.1f}%",
                        f"current {rm['curdd']:.1f}%", "neg"))
        kpis.append(kpi("Sharpe (ann.)", f"{rm['sharpe']:.2f}",
                        f"Sortino {rm['sortino']:.2f}", _cls(rm["sharpe"])))
    elif ctx["dd"] is not None:
        kpis.append(kpi("Drawdown vs HWM", _pct(ctx["dd"] * 100, signed=False), "", "neg"))

    # ---- charts
    equity_html = (f'<img src="{ctx["equity_chart"]}" alt="Equity curve and drawdown"/>'
                   if ctx["equity_chart"] else
                   "<p class='muted'>Not enough equity history yet for the curve.</p>")
    donut_html = (f'<img src="{ctx["donut"]}" alt="Capital allocation"/>'
                  if ctx["donut"] else "")
    cum_html = (f'<img src="{ctx["cum_chart"]}" alt="Cumulative P/L by sleeve"/>'
                if ctx["cum_chart"] else
                "<p class='muted'>No closed trades to chart yet.</p>")

    # ---- risk strip
    risk_html = ""
    if rm:
        risk_html = '<div class="metrics">' + "".join(
            f'<div class="metric"><span>{lbl}</span><b class="{cls}">{val}</b></div>'
            for lbl, val, cls in [
                ("Volatility (ann.)", f"{rm['vol']:.1f}%", ""),
                ("Best day", f"{rm['best']:+.2f}%", "pos"),
                ("Worst day", f"{rm['worst']:+.2f}%", "neg"),
                ("Up days", f"{rm['pct_up']:.0f}%", ""),
                ("Return obs.", f"{rm['days']}", "muted"),
            ]) + "</div>"

    # ---- sleeve cards
    cards = "".join(sleeve_card(sk, sl[sk], ctx["sleeve_cap_pct"].get(sk),
                                ctx["sleeve_upl"].get(sk)) for sk in ("A", "H"))

    # ---- activity
    act = ctx["activity"]
    exit_chips = "".join(chip(f"{escape(k)} ×{v}", "neg") for k, v in act["exits"].items()) \
        or "<span class='muted'>none</span>"
    entry_chips = "".join(chip(f"{escape(e['sym'])} · {e.get('sleeve', '?')}", "acc")
                          for e in act["entries"]) or "<span class='muted'>none</span>"
    closed_rows = "".join(
        f"<tr><td>{escape(t['ticker'])}</td><td>{t.get('sleeve', '?')}</td>"
        f"<td>{t.get('entry_date', '')}</td><td>{t.get('exit_date', '')}</td>"
        f"<td class='{_cls(t['pnl'])} num'>{_money(t['pnl'], signed=True)}</td>"
        f"<td class='{_cls(t['ret'])} num'>{t['ret'] * 100:+.1f}%</td></tr>"
        for t in sorted(act["closed"], key=lambda t: t["pnl"], reverse=True))
    closed_html = (f"<div class='tbl-wrap'><table class='grid'><thead><tr><th>Ticker</th>"
                   f"<th>Sleeve</th><th>Entry</th><th>Exit</th><th class='num'>P/L</th>"
                   f"<th class='num'>Return</th></tr></thead><tbody>{closed_rows}</tbody></table></div>"
                   if closed_rows else "<p class='muted'>No positions closed this week.</p>")

    # ---- open positions (with inline P/L bar)
    max_upl = max((abs(r["uplpc"]) for r in ctx["positions"] if r["uplpc"] is not None),
                  default=1.0) or 1.0
    pos_rows = ""
    for r in ctx["positions"]:
        warn = " ⏳" if r["near"] else ""
        if r["uplpc"] is not None:
            w = min(abs(r["uplpc"]) / max_upl * 100, 100)
            col = C["pos"] if r["uplpc"] >= 0 else C["neg"]
            side = "left:50%" if r["uplpc"] >= 0 else f"right:50%"
            plbar = (f"<div class='plbar'><div class='plfill' style='width:{w / 2:.1f}%;"
                     f"{side};background:{col}'></div></div>")
        else:
            plbar = ""
        pos_rows += (
            f"<tr><td>{escape(r['sym'])}{warn}</td><td>{r['sleeve']}</td>"
            f"<td>{r['entry'] or '—'}</td>"
            f"<td class='num'>{r['held'] if r['held'] is not None else '—'}</td>"
            f"<td class='num'>{('%.4g' % r['qty']) if r['qty'] is not None else '—'}</td>"
            f"<td class='num'>{_money0(r['mv'])}</td>"
            f"<td class='{_cls(r['upl'])} num'>{_money0(r['upl'], signed=True)}</td>"
            f"<td class='{_cls(r['uplpc'])} num'>{_pct(r['uplpc'])}</td>"
            f"<td class='plcell'>{plbar}</td></tr>"
        )
    pos_html = (f"<div class='tbl-wrap'><table class='grid'><thead><tr><th>Symbol</th>"
                f"<th>Sleeve</th><th>Entry</th><th class='num'>Days</th><th class='num'>Qty</th>"
                f"<th class='num'>Mkt value</th><th class='num'>Unreal. P/L</th>"
                f"<th class='num'>%</th><th></th></tr></thead><tbody>{pos_rows}</tbody></table></div>"
                if pos_rows else "<p class='muted'>No open positions.</p>")

    # ---- regime chips
    if reg:
        gate = ("on" if reg["gate_on"] else "off")
        chips = [
            chip(f"Momentum gate {gate.upper()}", "ok" if reg["gate_on"] else "off"),
            chip(f"SPY {'above' if reg['above200'] else 'below'} 200-day",
                 "ok" if reg["above200"] else "warn"),
            chip(f"VIX {reg['vix']:.1f}") if reg.get("vix") is not None else "",
            chip(f"SPY wk {_pct(reg.get('spy_wk'))}", _cls(reg.get("spy_wk")).replace("pos", "ok").replace("neg", "off")),
        ]
        regime_html = '<div class="chips">' + "".join(chips) + "</div>"
    else:
        regime_html = "<p class='muted'>Market data unavailable (no network) — regime n/a.</p>"

    # drawdown circuit-breaker chip
    if ctx["dd"] is not None:
        if ctx["dd"] <= DD_HALT_ALL:
            cb = chip(f"Circuit breaker: ALL entries halted ({ctx['dd'] * 100:.1f}%)", "bad")
        elif ctx["dd"] <= DD_HALT_A:
            cb = chip(f"Circuit breaker: Sleeve A halted ({ctx['dd'] * 100:.1f}%)", "warn")
        else:
            cb = chip(f"Circuit breaker: normal (dd {ctx['dd'] * 100:.1f}%)", "ok")
        regime_html += f'<div class="chips" style="margin-top:8px">{cb}</div>'

    alerts_html = ("".join(f"<li>{escape(a)}</li>" for a in ctx["alerts"])
                   if ctx["alerts"] else "<li class='muted'>none this week</li>")

    narrative = ctx.get("narrative") or (
        "<em>Portfolio-manager commentary is added here by the weekly Claude routine.</em>")

    return _PAGE.format(
        title=f"Weekly Portfolio Report — {as_of}",
        week=f"{week_start:%b %d} – {as_of:%b %d, %Y}",
        generated=ctx["generated"],
        kpis="".join(kpis) or "<p class='muted'>No data available.</p>",
        equity_chart=equity_html,
        donut=donut_html,
        narrative=narrative,
        sleeve_cards=cards,
        cum_chart=cum_html,
        risk=risk_html,
        exit_chips=exit_chips,
        entry_chips=entry_chips,
        closed=closed_html,
        positions=pos_html,
        regime=regime_html,
        alerts=alerts_html,
    )


_PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
:root{{color-scheme:dark;--surface:#181a1f;--panel:#1f232b;--page:#0c0e12;
--ink:#f4f6f8;--sec:#c3c2b7;--muted:#8a8f98;--grid:#262a32;--axis:#3a3f48;
--A:#3987e5;--H:#d95926;--pos:#3fb950;--neg:#f0503c;--warn:#e3b341;--acc:#3987e5}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--page);color:var(--sec);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:26px 20px 64px}}
h1{{font-size:23px;margin:0;color:var(--ink);letter-spacing:-.01em}}
.sub{{color:var(--muted);font-size:13px;margin:2px 0 0}}
h2{{font-size:13px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);
margin:30px 0 12px;font-weight:600}}
.num{{font-variant-numeric:tabular-nums}}
.pos{{color:var(--pos)}}.neg{{color:var(--neg)}}.muted{{color:var(--muted)}}
.fine{{color:var(--muted);font-size:12px;font-weight:400}}
/* KPI hero */
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-top:16px}}
.kpi{{background:linear-gradient(160deg,var(--panel),var(--surface));border:1px solid var(--grid);
border-radius:12px;padding:15px 16px;position:relative;overflow:hidden}}
.kpi-label{{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
.kpi-val{{font-size:25px;font-weight:650;margin-top:5px;color:var(--ink);
font-variant-numeric:tabular-nums;display:flex;align-items:baseline;gap:6px}}
.kpi-val.pos{{color:var(--pos)}}.kpi-val.neg{{color:var(--neg)}}
.kpi-arrow{{font-size:14px}}
.kpi-sub{{font-size:12.5px;color:var(--muted);margin-top:2px}}
.kpi-sub.pos{{color:var(--pos)}}.kpi-sub.neg{{color:var(--neg)}}
.kpi-spark{{position:absolute;right:12px;bottom:10px;opacity:.9}}
.spark{{display:block}}
/* panels */
.panel{{background:var(--surface);border:1px solid var(--grid);border-radius:12px;padding:14px 16px}}
.two{{display:grid;grid-template-columns:1.9fr 1fr;gap:16px;align-items:stretch}}
.panel img,.tile-img img{{max-width:100%;display:block;margin:0 auto;border-radius:6px}}
.panel-cap{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:0 0 6px}}
.narrative{{background:var(--surface);border:1px solid var(--grid);border-left:3px solid var(--acc);
border-radius:10px;padding:15px 18px;line-height:1.6}}
.narrative p{{margin:0 0 8px}}.narrative p:last-child{{margin:0}}
/* sleeve cards */
.cards{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.scard{{background:var(--surface);border:1px solid var(--grid);border-radius:12px;
padding:16px 18px;border-top-width:3px}}
.scard-head{{display:flex;align-items:center;gap:8px;color:var(--ink);font-size:15px}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block}}
.scard-cap{{font-size:12.5px;color:var(--muted);margin:3px 0 10px}}
.scard-net{{font-size:30px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1}}
.scard-net-lbl{{display:block;font-size:11px;color:var(--muted);font-weight:400;
text-transform:uppercase;letter-spacing:.05em;margin-top:3px}}
.scard-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px 14px;margin:14px 0 4px}}
.scard-grid div{{display:flex;justify-content:space-between;align-items:baseline;
border-bottom:1px solid var(--grid);padding-bottom:4px}}
.scard-grid span{{color:var(--muted);font-size:12.5px}}
.scard-grid b{{color:var(--ink);font-variant-numeric:tabular-nums}}
.scard-barlbl{{font-size:12.5px;color:var(--sec);margin:12px 0 5px}}
.track{{height:7px;border-radius:6px;overflow:hidden}}
.fill{{height:100%;border-radius:6px}}
.gauge-row{{display:flex;align-items:baseline;gap:8px;margin:14px 0 5px;font-size:12.5px}}
.gauge-cap{{color:var(--sec)}}.gauge-row b{{font-size:15px;font-variant-numeric:tabular-nums}}
.gauge-bench{{color:var(--muted);margin-left:auto;font-size:11.5px}}
.gauge{{position:relative;height:8px;background:var(--grid);border-radius:6px;overflow:hidden}}
.gauge-fill{{height:100%;border-radius:6px}}
.gauge-tick{{position:absolute;top:-2px;width:2px;height:12px;background:var(--ink);opacity:.7}}
.scard-avg{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}}
.avgcol span{{display:block;margin-bottom:4px}}
.avgcol .track{{margin-bottom:4px}}
.avgcol b{{font-size:13.5px;font-variant-numeric:tabular-nums}}
.ok{{color:var(--pos)}}.warn{{color:var(--warn)}}.bad{{color:var(--neg)}}
/* metrics strip */
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}}
.metric{{background:var(--surface);border:1px solid var(--grid);border-radius:9px;
padding:10px 13px;display:flex;justify-content:space-between;align-items:baseline}}
.metric span{{color:var(--muted);font-size:12.5px}}
.metric b{{font-size:16px;color:var(--ink);font-variant-numeric:tabular-nums}}
/* chips */
.chips{{display:flex;flex-wrap:wrap;gap:8px}}
.chip{{font-size:12.5px;padding:4px 11px;border-radius:20px;background:var(--panel);
border:1px solid var(--grid);color:var(--sec)}}
.chip.ok{{background:#12341c;border-color:#1c5027;color:var(--pos)}}
.chip.warn{{background:#3a300f;border-color:#5c4a12;color:var(--warn)}}
.chip.bad,.chip.off{{background:#3a1614;border-color:#5c2320;color:var(--neg)}}
.chip.neg{{background:#3a1614;border-color:#5c2320;color:var(--neg)}}
.chip.acc{{background:#0f2540;border-color:#1c447a;color:var(--A)}}
/* tables */
.act{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:14px}}
.act h3{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:0 0 8px}}
.tbl-wrap{{overflow-x:auto}}
table.grid{{width:100%;border-collapse:collapse;font-size:13.5px}}
table.grid th{{text-align:left;color:var(--muted);font-weight:600;font-size:11.5px;
text-transform:uppercase;letter-spacing:.03em;padding:8px 10px;border-bottom:1px solid var(--grid)}}
table.grid th.num,table.grid td.num{{text-align:right;font-variant-numeric:tabular-nums}}
table.grid td{{padding:8px 10px;border-bottom:1px solid var(--grid);white-space:nowrap;color:var(--sec)}}
table.grid tbody tr:hover{{background:var(--panel)}}
.plcell{{width:90px}}
.plbar{{position:relative;height:8px;background:var(--grid);border-radius:5px;width:80px}}
.plbar::before{{content:"";position:absolute;left:50%;top:-1px;height:10px;width:1px;background:var(--axis)}}
.plfill{{position:absolute;height:100%;border-radius:5px}}
ul.plain{{margin:6px 0;padding-left:18px}}ul.plain li{{margin:3px 0}}
footer{{margin-top:40px;color:var(--muted);font-size:12px;border-top:1px solid var(--grid);padding-top:14px}}
@media(max-width:760px){{.two,.cards,.act{{grid-template-columns:1fr}}}}
</style></head>
<body><div class="wrap">
<header>
<h1>📊 Weekly Portfolio Report</h1>
<p class="sub">60/40 A/H swing ensemble · trading week {week} · generated {generated}</p>
</header>
<div class="kpis">{kpis}</div>

<div class="two" style="margin-top:22px">
<div class="panel"><p class="panel-cap">Equity vs SPY & drawdown</p>{equity_chart}</div>
<div class="panel"><p class="panel-cap">Capital allocation</p>{donut}</div>
</div>

<h2>Portfolio-manager commentary</h2>
<div class="narrative">{narrative}</div>

<h2>Per-strategy performance (sleeves)</h2>
<div class="cards">{sleeve_cards}</div>

<h2>Cumulative realized P/L by sleeve</h2>
<div class="panel">{cum_chart}</div>

<h2>Risk metrics</h2>
{risk}

<h2>This week's activity</h2>
<div class="act">
<div><h3>Exits triggered</h3><div class="chips">{exit_chips}</div></div>
<div><h3>New entries</h3><div class="chips">{entry_chips}</div></div>
</div>
<h3 style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:0 0 6px">Closed trades</h3>
{closed}

<h2>Open positions</h2>
{positions}

<h2>Market regime & guardrails</h2>
{regime}
<h3 style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin:16px 0 6px">Alerts this week</h3>
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
    as_of = series.index[-1].date() if len(series) else dt.date.today()
    week_start, as_of = week_window(as_of)

    eq = equity_stats(series, week_start, live_equity)
    rm = risk_metrics(eq["series"]) if not eq.get("empty") else {}

    hwm = float(state.get("hwm", 0.0) or 0.0)
    cur_eq = live_equity if live_equity is not None else (eq["equity"] if not eq.get("empty") else None)
    dd = (cur_eq / hwm - 1.0) if (hwm > 0 and cur_eq) else None

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

    close = market.get("close")
    spy_series = None
    if close is not None and len(close):
        try:
            spy_series = close["SPY"].dropna()
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
        "equity_chart": equity_underwater_chart(eq.get("series"), spy_series),
        "donut": allocation_donut(sleeve_cap_pct, invested_pct),
        "cum_chart": cumulative_pl_chart(trades),
    }
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


def post_file_to_discord(webhook: str, filepath: Path, message: str) -> int:
    """Upload the HTML file to a Discord webhook as an attachment (multipart).

    Returns the HTTP status code. `?wait=true` makes Discord return the created
    message (and a proper error body) instead of a bare 204, which aids diagnosis.
    """
    import requests

    url = webhook + ("&" if "?" in webhook else "?") + "wait=true"
    with open(filepath, "rb") as fh:
        files = {"files[0]": (filepath.name, fh, "text/html")}
        data = {"payload_json": json.dumps({"content": message[:1990]})}
        resp = requests.post(url, data=data, files=files, timeout=30)
    resp.raise_for_status()
    return resp.status_code


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Weekly portfolio HTML report")
    ap.add_argument("--out", type=Path, default=None, help="output HTML path")
    ap.add_argument("--discord", action="store_true", help="also post the file to Discord")
    ap.add_argument("--narrative", type=str, default=None,
                    help="PM commentary (HTML) to inject")
    ap.add_argument("--narrative-file", type=Path, default=None,
                    help="path to a file with PM commentary HTML (avoids shell-quoting issues)")
    args = ap.parse_args()

    narrative = args.narrative
    if args.narrative_file is not None:
        try:
            narrative = args.narrative_file.read_text(encoding="utf-8").strip()
        except OSError as e:
            print(f"Could not read --narrative-file ({e}); continuing without commentary.")

    html, ctx = generate(narrative=narrative)

    out = args.out
    if out is None:
        DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = DEFAULT_OUT_DIR / f"{ctx['as_of'].isoformat()}.html"
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out}  ({len(html):,} bytes)")

    if args.discord:
        webhook = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()
        if not webhook:
            print("DISCORD: no DISCORD_WEBHOOK_URL set in the environment - NOT posted. "
                  "Add it to the environment to enable delivery.")
            return
        try:
            code = post_file_to_discord(webhook, out, summary_line(ctx))
            print(f"DISCORD: posted weekly report to Discord OK (HTTP {code}).")
        except Exception as e:  # noqa: BLE001 - a report failure must never break a pipeline
            body = ""
            resp = getattr(e, "response", None)
            if resp is not None:
                body = f" [HTTP {resp.status_code}] {resp.text[:300]}"
            print(f"DISCORD: upload FAILED (report still written): {e}{body}")


if __name__ == "__main__":
    main()
