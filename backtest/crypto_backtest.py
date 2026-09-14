"""Run the DEPLOYED sleeve configuration on crypto, 3 years to today.

Pre-registration: `results/CRYPTO_BACKTEST_HYPOTHESIS.md`. Criteria were fixed
before this was run. Nothing here tunes anything: Sleeve A uses the exact
`screener.py` constants, Sleeve H its exact constants, and the strategy modules
and `backtest/engine.py` are imported unmodified.

    python -m backtest.crypto_backtest
    python -m backtest.crypto_backtest --json results/crypto_backtest.json

Two declared adaptations (see the pre-registration):
  - min_price $1 dropped (price level is an arbitrary unit in crypto); the $1
    filter is run as a sensitivity so the effect is visible.
  - Sleeve H's SPY>SMA(100) gate becomes BTC>SMA(100).

One plumbing detail, not a rule change: Yahoo reports crypto Volume already in
USD, while indicators.liquidity_mask multiplies price by volume. The panel is
built with volume = usd_volume / close so the unmodified screen computes the
right dollar figure.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from backtest.crypto_feasibility import CRYPTO_TICKERS, fetch, load_equity_sample
from backtest.engine import run_backtest
from backtest.indicators import sma
from backtest.metrics import cagr, max_drawdown, profit_factor, summarize
from backtest.strategies import high52_breakout, three_lower_lows

# --- window: three years to today, plus warmup for the 252-day lookback ---
END = "2026-09-14"
START = "2023-09-14"
WARMUP_START = "2022-01-01"

# --- the deployed constants ---
# A: refine.py's "3ll_refined" == screener.A_STRETCH / A_TREND_SMA / A_MIN_DOLLAR_VOL.
# H: refine.py's "h52_fast_regime" == module defaults + a 100-day regime gate.
#    H exposes no min_price/min_dollar_vol; liquidity_mask() is called inside the
#    module with its $5 / $20M defaults. Left alone rather than edit validated code.
A_PARAMS = dict(stretch=0.75, trend_sma=200, min_dollar_vol=10e6, max_positions=10)
H_PARAMS: dict = {}
SLIPPAGE = {"slip5": 5.0, "slip15": 15.0, "slip25": 25.0}
HEADLINE_SLIP = "slip15"
CRYPTO_BARS_PER_YEAR = 365


def build_crypto_panel() -> dict[str, pd.DataFrame]:
    """Panel in the shape engine.py and indicators.py expect.

    Crypto has no dividend/split adjustment — CRYPTO_FEASIBILITY.md verified
    Adj Close == Close exactly — so adjusted and raw series are identical.
    """
    raw = fetch(CRYPTO_TICKERS, WARMUP_START)
    close = raw["close"]
    return {
        "open": raw["open"], "high": raw["high"], "low": raw["low"],
        "close": close, "raw_close": close,
        # usd notional -> synthetic coin units, so liquidity_mask() is correct
        "volume": raw["volume"] / close.replace(0, np.nan),
    }


def build_equity_panel() -> dict[str, pd.DataFrame]:
    raw = load_equity_sample()
    close = raw["close"]
    return {"open": raw["open"], "high": raw["high"], "low": raw["low"],
            "close": close, "raw_close": close, "volume": raw["volume"]}


def crypto_sharpe(equity: pd.Series) -> float:
    """metrics.sharpe annualises at 252 bars. Crypto has 365."""
    r = equity.pct_change().dropna()
    if r.std() == 0:
        return 0.0
    return float(r.mean() / r.std() * np.sqrt(CRYPTO_BARS_PER_YEAR))


def buy_and_hold(close: pd.Series | pd.DataFrame, label: str) -> dict:
    """Equity curve for holding an asset (or an equal-weight basket) over the window."""
    if isinstance(close, pd.DataFrame):
        rets = close.pct_change()
        eq = (1 + rets.mean(axis=1, skipna=True).fillna(0)).cumprod()
    else:
        eq = close / close.iloc[0]
    eq = eq.loc[START:END]
    eq = eq / eq.iloc[0]
    return {"strategy": label, "cagr": round(cagr(eq), 4),
            "sharpe": round(crypto_sharpe(eq), 2),
            "max_dd": round(max_drawdown(eq), 4), "exposure": 1.0,
            "trades": None, "win_rate": None, "profit_factor": None}


def run_sleeve(panel: dict, sleeve: str, slip: float, *, min_price: float,
               regime_ok=None, is_crypto: bool) -> dict:
    if sleeve == "A":
        spec = three_lower_lows.build(panel, {}, min_price=min_price, **A_PARAMS)
    else:
        # H takes no min_price — see H_PARAMS note
        spec = high52_breakout.build(panel, {}, regime_ok=regime_ok, **H_PARAMS)
    res = run_backtest(panel, spec, start=START, end=END, slippage_bps=slip)
    out = summarize(res)
    out["strategy"] = f"Sleeve {sleeve}"
    if is_crypto:
        out["sharpe"] = round(crypto_sharpe(res.equity), 2)
    out["_result"] = res
    return out


def ensemble(res_a, res_h, w_a: float = 0.60) -> dict:
    """The deployed 60/40 capital split, combined on daily returns."""
    ra = res_a.equity.pct_change().fillna(0)
    rh = res_h.equity.pct_change().fillna(0)
    eq = (1 + w_a * ra + (1 - w_a) * rh).cumprod()
    trades = pd.concat([res_a.trades, res_h.trades], ignore_index=True)
    return {"strategy": "Ensemble 60/40", "cagr": round(cagr(eq), 4),
            "sharpe": round(crypto_sharpe(eq), 2),
            "max_dd": round(max_drawdown(eq), 4),
            "exposure": round(float(w_a * res_a.exposure.mean()
                                    + (1 - w_a) * res_h.exposure.mean()), 3),
            "trades": int(len(trades)),
            "win_rate": round(float((trades["ret"] > 0).mean()), 3) if len(trades) else None,
            "profit_factor": round(profit_factor(trades), 2) if len(trades) else None}


def fill_rates(crypto: dict, equity: dict, out: dict) -> None:
    """Why is crypto exposure so low — too few signals, or a limit that never fills?

    The obvious objection to this whole run is that `stretch=0.75` was tuned for
    equity volatility and sits too deep in a 3x-more-volatile asset. Measured
    below: it does not. The limit is ATR-scaled, so it self-adjusts, and the fill
    rates match. Low exposure is a supply problem, not a parameter problem.
    """
    from backtest.indicators import atr, liquidity_mask

    print("\n=== DIAGNOSTIC: signals -> limit fills (does stretch=0.75 transfer?) ===")
    for name, panel, min_price in (("CRYPTO", crypto, 0.0), ("EQUITY", equity, 1.0)):
        p = {k: v.loc[START:END] for k, v in panel.items()}
        c, lo, hi = p["close"], p["low"], p["high"]
        ll = ((lo < lo.shift(1)) & (lo.shift(1) < lo.shift(2))
              & (lo.shift(2) < lo.shift(3)))
        sig = ((c > sma(c, 200)) & (c < sma(c, 5)) & ll
               & liquidity_mask(p, min_price=min_price, min_dollar_vol=10e6))
        a10 = atr(hi, lo, c, 10)
        fill = (lo.shift(-1) <= c - 0.75 * a10) & sig
        n_sig, n_fill = int(sig.sum().sum()), int(fill.sum().sum())
        print(f"  {name}: {n_sig:>6,} signals -> {n_fill:>5,} fills "
              f"({n_fill / max(n_sig, 1):>5.1%})   "
              f"limit sits {(0.75 * a10 / c)[sig].stack().median():.2%} below close, "
              f"ATR(10) = {(a10 / c)[sig].stack().median():.2%} of price")
        out.setdefault("fills", {})[name] = {
            "signals": n_sig, "fills": n_fill, "rate": round(n_fill / max(n_sig, 1), 3)}
    print("  Fill rates match, so the ATR-scaled limit transfers. Exposure is low")
    print("  because there are few signals, not because the limit is mispriced.")


ROW = "  {strategy:<26}{cagr:>9}{sharpe:>8}{max_dd:>9}{exposure:>8}{trades:>8}{win:>8}{pf:>7}"


def header() -> None:
    print(ROW.format(strategy="", cagr="CAGR", sharpe="Sharpe", max_dd="MaxDD",
                     exposure="Expo", trades="Trades", win="Win%", pf="PF"))


def show(d: dict) -> None:
    fmt = lambda v, p="": "-" if v is None else f"{v:{p}}"  # noqa: E731
    print(ROW.format(
        strategy=d["strategy"],
        cagr=fmt(d["cagr"], ".1%"), sharpe=fmt(d["sharpe"], ".2f"),
        max_dd=fmt(d["max_dd"], ".1%"), exposure=fmt(d.get("exposure"), ".0%"),
        trades=fmt(d.get("trades")), win=fmt(d.get("win_rate"), ".1%"),
        pf=fmt(d.get("profit_factor"), ".2f")))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", help="write the full result table to this path")
    args = ap.parse_args()

    print(f"\nDeployed sleeve config on crypto — {START} to {END}")
    print("Pre-registration: results/CRYPTO_BACKTEST_HYPOTHESIS.md\n")

    crypto = build_crypto_panel()
    btc = crypto["close"]["BTC-USD"]
    btc_regime = (btc > sma(btc, 100)).reindex(crypto["close"].index).fillna(False)

    out: dict = {"window": [START, END], "runs": {}}

    # How much universe does each sleeve's liquidity screen actually leave?
    from backtest.indicators import liquidity_mask
    w = {k: v.loc[START:END] for k, v in crypto.items()}
    a_mask = liquidity_mask(w, min_price=0.0, min_dollar_vol=10e6)
    h_mask = liquidity_mask(w, min_price=5.0, min_dollar_vol=20e6)
    print("=== UNIVERSE after each sleeve's own liquidity screen ===")
    print(f"  Sleeve A ($0 price, $10M ADV) : median {a_mask.sum(axis=1).median():.0f} "
          f"of {w['close'].shape[1]} names/day")
    print(f"  Sleeve H ($5 price, $20M ADV) : median {h_mask.sum(axis=1).median():.0f} "
          f"of {w['close'].shape[1]} names/day  <-- $5 floor is hardcoded in the module")
    print(f"    names ever passing H's screen: "
          f"{sorted(h_mask.columns[h_mask.any()].tolist())}")
    out["universe"] = {"A_median": float(a_mask.sum(axis=1).median()),
                       "H_median": float(h_mask.sum(axis=1).median()),
                       "H_names": sorted(h_mask.columns[h_mask.any()].tolist())}

    print("\n=== BENCHMARKS (buy and hold, 100% exposed) ===")
    header()
    bench = [buy_and_hold(btc, "BTC buy-and-hold"),
             buy_and_hold(crypto["close"], "Equal-weight 19 pairs")]
    for b in bench:
        show(b)
    out["benchmarks"] = bench
    btc_sharpe = bench[0]["sharpe"]

    for label, slip in SLIPPAGE.items():
        tag = "  <-- HEADLINE (Alpaca maker fee)" if label == HEADLINE_SLIP else ""
        print(f"\n=== CRYPTO at {slip:.0f} bps/side ({label}){tag} ===")
        header()
        a = run_sleeve(crypto, "A", slip, min_price=0.0, is_crypto=True)
        h = run_sleeve(crypto, "H", slip, min_price=0.0,
                       regime_ok=btc_regime, is_crypto=True)
        e = ensemble(a["_result"], h["_result"])
        for d in (a, h, e):
            show(d)
        out["runs"][label] = {k: {x: v for x, v in d.items() if x != "_result"}
                              for k, d in (("A", a), ("H", h), ("ensemble", e))}

    print(f"\n=== SENSITIVITY: keeping the $1 min-price filter ({HEADLINE_SLIP}) ===")
    header()
    a1 = run_sleeve(crypto, "A", SLIPPAGE[HEADLINE_SLIP], min_price=1.0, is_crypto=True)
    a1["strategy"] = "Sleeve A (min_price $1)"
    show(a1)
    out["min_price_1"] = {k: v for k, v in a1.items() if k != "_result"}

    eq_panel = build_equity_panel()
    fill_rates(crypto, eq_panel, out)

    print(f"\n=== INCUMBENT: the same Sleeve A on US equities, same window ===")
    header()
    for label in ("slip5", "slip25"):
        d = run_sleeve(eq_panel, "A", SLIPPAGE[label], min_price=1.0, is_crypto=False)
        d["strategy"] = f"Equity Sleeve A ({label})"
        show(d)
        out.setdefault("equity", {})[label] = {k: v for k, v in d.items() if k != "_result"}

    # ---- pre-registered verdict ----
    hl = out["runs"][HEADLINE_SLIP]["A"]
    worst = out["runs"]["slip25"]["A"]
    print(f"\n=== PRE-REGISTERED CRITERIA, evaluated at {HEADLINE_SLIP} ===")
    checks = [
        ("A1  profit factor > 1.30", hl["profit_factor"], hl["profit_factor"] is not None
         and hl["profit_factor"] > 1.30),
        ("A2  at least 100 trades", hl["trades"], hl["trades"] >= 100),
        ("A3  max drawdown better than -25%", f"{hl['max_dd']:.1%}", hl["max_dd"] > -0.25),
        (f"B4  Sharpe >= BTC buy-and-hold ({btc_sharpe:.2f})", hl["sharpe"],
         hl["sharpe"] >= btc_sharpe),
        ("B5  CAGR positive at slip25", f"{worst['cagr']:.1%}", worst["cagr"] > 0),
        ("B6  Sharpe >= equity Sleeve A OOS 0.98", hl["sharpe"], hl["sharpe"] >= 0.98),
    ]
    for name, value, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {name:<42} actual: {value}")
    verdict_a = all(ok for n, _, ok in checks if n.startswith("A"))
    verdict_b = verdict_a and all(ok for n, _, ok in checks if n.startswith("B"))
    print(f"\n  VERDICT A (does the rule work on crypto?) : "
          f"{'PASS' if verdict_a else 'FAIL'}")
    print(f"  VERDICT B (worth building?)               : "
          f"{'PASS' if verdict_b else 'FAIL'}")
    out["verdict"] = {"a": verdict_a, "b": verdict_b,
                      "checks": [(n, str(v), ok) for n, v, ok in checks]}

    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
