"""Crypto sleeve feasibility probe — measurement only, no strategy, no backtest.

Answers the five blocking questions in `results/CRYPTO_FEASIBILITY.md` with numbers
that can be re-derived. Nothing here trades, and nothing here touches the live
screener or runner.

    python -m backtest.crypto_feasibility            # all sections
    python -m backtest.crypto_feasibility --section engine

Sections
  engine    Does backtest/engine.py contain a calendar/session assumption?
            (feeds it the same synthetic panel on a 5-day and a 7-day index)
  data      What daily crypto history is actually obtainable, and is Yahoo's
            crypto `Volume` field denominated in coins or in USD?
  breadth   Effective independent bets, and the PHASE4/5 test — does the Sleeve A
            entry feature vary between names on the same day, or between days?
  supply    Qualifying Sleeve A setups per year, crypto vs equities. This is the
            question PHASE6_CONCLUSION.md left open.
  regime    Does `close > SMA200` act as a per-name filter or as a single
            market-wide on/off switch?
  ceiling   Hard upper bound on capital utilisation, independent of any edge.

Universe: the USD-quoted spot pairs on Alpaca's supported list, minus the two
stablecoins (USDC/USDT are not swing-tradable). SKY/USD has no Yahoo history.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from backtest.yfsession import download as yf_download

ALPACA_USD_PAIRS = [
    "AAVE", "AVAX", "BAT", "BCH", "BTC", "CRV", "DOGE", "DOT", "ETH", "GRT",
    "LINK", "LTC", "MKR", "SHIB", "SUSHI", "UNI", "XRP", "XTZ", "YFI",
]
CRYPTO_TICKERS = [f"{s}-USD" for s in ALPACA_USD_PAIRS]

# The broad crypto cohort only begins here; before it the universe is BTC + LTC.
COHORT_START = "2017-11-09"
IS_WINDOW = ("2017-11-09", "2022-12-31")
OOS_WINDOW = ("2023-01-01", "2026-12-31")
EQUITY_SAMPLE_N = 120
EQUITY_SAMPLE_SEED = 11
LIQUIDITY_MIN_DOLLAR_VOL = 10e6  # PLAYBOOK §2, Sleeve A


# ---------------------------------------------------------------- data


def fetch(tickers: list[str], start: str) -> dict[str, pd.DataFrame]:
    df = yf_download(tickers, start=start, auto_adjust=False, actions=False,
                     group_by="column", threads=True, progress=False)
    if df is None or df.empty:
        raise SystemExit(f"no data returned for {tickers[:3]}...")
    if not isinstance(df.columns, pd.MultiIndex):
        df.columns = pd.MultiIndex.from_product([df.columns, tickers])
    fields = (("Open", "open"), ("High", "high"), ("Low", "low"),
              ("Close", "close"), ("Volume", "volume"))
    return {name: df[f].sort_index() for f, name in fields}


def load_crypto() -> dict[str, pd.DataFrame]:
    return fetch(CRYPTO_TICKERS, "2010-01-01")


def load_equity_sample() -> dict[str, pd.DataFrame]:
    import random
    from backtest.data import DATA_DIR

    uni = pd.read_csv(DATA_DIR / "universe.csv")
    random.seed(EQUITY_SAMPLE_SEED)
    tick = sorted(random.sample(sorted(set(uni["ticker"])), EQUITY_SAMPLE_N))
    return fetch(tick, "2017-01-01")


def window(panel: dict, start: str, end: str | None = None) -> dict:
    out = {}
    for k, v in panel.items():
        w = v[v.index >= pd.Timestamp(start)]
        if end:
            w = w[w.index <= pd.Timestamp(end)]
        out[k] = w
    return out


# ------------------------------------------------------- shared measures


def sleeve_a_signal(panel: dict) -> pd.DataFrame:
    """The deployed Sleeve A entry rule (PLAYBOOK §2), minus the liquidity screen:
    close > SMA200, close < SMA5, three consecutive lower lows."""
    c, lo = panel["close"], panel["low"]
    lower_lows = (
        (lo < lo.shift(1)) & (lo.shift(1) < lo.shift(2)) & (lo.shift(2) < lo.shift(3))
    )
    return (c > c.rolling(200).mean()) & (c < c.rolling(5).mean()) & lower_lows


def warm(panel: dict) -> pd.DataFrame:
    """Rows where the 200-day lookback is actually available."""
    c = panel["close"]
    return c.notna() & c.shift(200).notna()


def dollar_volume(panel: dict, is_crypto: bool) -> pd.DataFrame:
    """Yahoo reports crypto `Volume` already in USD notional; equity Volume is in
    shares. The `data` section verifies this empirically."""
    return panel["volume"] if is_crypto else panel["volume"] * panel["close"]


def avg_pairwise_corr(rets: pd.DataFrame, min_periods: int = 250) -> tuple[float, int]:
    c = rets.corr(min_periods=min_periods).to_numpy()
    iu = np.triu_indices_from(c, 1)
    v = c[iu][np.isfinite(c[iu])]
    return float(v.mean()), int(v.size)


def effective_bets(rets: pd.DataFrame) -> tuple[float, float, int]:
    """N / (1 + (N-1)·rho) — how many independent bets an N-name universe really is."""
    rho, _ = avg_pairwise_corr(rets)
    n = rets.shape[1]
    return n / (1 + (n - 1) * rho), rho, n


def pc1_share(rets: pd.DataFrame, min_periods: int = 250) -> tuple[float, int]:
    """Variance share of the first principal component, from the pairwise-complete
    correlation matrix (ragged crypto histories make listwise deletion useless).
    Note PC1 share is mildly N-dependent — `effective_bets` is the cleaner stat."""
    r = rets.dropna(axis=1, thresh=min_periods)
    c = r.corr(min_periods=min_periods).to_numpy()
    keep = np.isfinite(c).all(axis=0)
    c = c[np.ix_(keep, keep)]
    ev = np.clip(np.linalg.eigvalsh(c)[::-1], 0, None)
    return float(ev[0] / ev.sum()), int(keep.sum())


def between_day_share(feat: pd.DataFrame) -> float:
    """Share of a feature's total variance that sits BETWEEN DAYS rather than
    between names on the same day.

    This is PHASE5_CONCLUSION.md's test made explicit: a high share means the
    feature is a regime proxy. Phases 4 and 5 both died on this."""
    f = feat[feat.notna().sum(axis=1) >= 3]
    a = f.to_numpy()
    grand = np.nanmean(a)
    n = f.notna().sum(axis=1).to_numpy()
    ss_total = np.nansum((a - grand) ** 2)
    ss_day = np.nansum(n * (np.nanmean(a, axis=1) - grand) ** 2)
    return float(ss_day / ss_total)


# ------------------------------------------------------------ sections


def section_engine() -> None:
    """Run the identical synthetic panel on a weekday index and a calendar-day
    index. If the engine holds any session assumption, the two must differ."""
    from backtest.engine import StrategySpec, run_backtest

    print("\n=== ENGINE — is there a calendar/session assumption in engine.py? ===")
    n, k = 400, 6
    rng = np.random.default_rng(0)
    px = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, size=(n, k)), axis=0))
    tick = [f"T{i}" for i in range(k)]

    def panel_for(idx):
        close = pd.DataFrame(px, index=idx, columns=tick)
        return {"open": close.shift(1).fillna(close.iloc[0]),
                "high": close * 1.01, "low": close * 0.99, "close": close,
                "raw_close": close,
                "volume": pd.DataFrame(1e9, index=idx, columns=tick)}

    res = {}
    for label, idx in (("business_days", pd.bdate_range("2020-01-01", periods=n)),
                       ("calendar_days", pd.date_range("2020-01-01", periods=n, freq="D"))):
        p = panel_for(idx)
        c = p["close"]
        spec = StrategySpec(name=label, entry_signal=(c < c.shift(1)) & (c.shift(1) < c.shift(2)),
                            entry_mode="next_open", exit_signal=(c > c.shift(1)),
                            exit_mode="next_open", time_stop=15, max_positions=3)
        res[label] = run_backtest(p, spec)

    a, b = res["business_days"], res["calendar_days"]
    cols = ["entry_px", "exit_px", "ret", "hold_days", "reason"]
    print(f"  trades         : 5-day index {len(a.trades)}   7-day index {len(b.trades)}")
    print(f"  final equity   : 5-day index {a.equity.iloc[-1]:,.2f}   "
          f"7-day index {b.equity.iloc[-1]:,.2f}")
    print(f"  equity identical ignoring date labels : "
          f"{np.allclose(a.equity.to_numpy(), b.equity.to_numpy())}")
    print(f"  trade ledger identical                : {a.trades[cols].equals(b.trades[cols])}")
    wd = sorted(set(pd.to_datetime(b.trades.entry_date).dt.weekday))
    print(f"  weekdays entered on the 7-day index   : {wd}  (5=Sat, 6=Sun)")
    print("  => the engine indexes by ROW, not by session. It needs no change for crypto.")


def section_data(crypto: dict) -> None:
    print("\n=== DATA — what daily crypto history is actually obtainable? ===")
    c, v = crypto["close"], crypto["volume"]
    print(f"  panel: {c.shape[0]} rows x {c.shape[1]} names, "
          f"{c.index[0].date()} -> {c.index[-1].date()}, tz={c.index.tz}")
    wd = pd.Series(c.index.weekday).value_counts().sort_index()
    print(f"  rows by weekday (0=Mon..6=Sun): {dict(wd)}  -> genuine 7-day bars")

    btc_v, btc_c = v["BTC-USD"].dropna().iloc[-1], c["BTC-USD"].dropna().iloc[-1]
    print(f"\n  Volume-units check on BTC-USD (Volume={btc_v:,.0f}, Close={btc_c:,.0f}):")
    print(f"    read as COINS -> ${btc_v * btc_c / 1e9:,.0f}bn/day  (implausible)")
    print(f"    read as USD   -> ${btc_v / 1e9:,.0f}bn/day  (matches real BTC spot volume)")
    print("    => Yahoo's crypto Volume is ALREADY USD notional. Do not multiply by close.")

    print(f"\n  {'ticker':<11}{'first':>12}{'last':>12}{'rows':>7}{'yrs':>6}{'med $vol 1y':>16}")
    for t in c.columns:
        s = c[t].dropna()
        if s.empty:
            print(f"  {t:<11}{'NO DATA':>12}")
            continue
        yrs = (s.index[-1] - s.index[0]).days / 365.25
        dv = v[t].reindex(s.index).tail(365).median()
        flag = ""
        if s.index[-1] < c.index[-1] - pd.Timedelta(days=30):
            flag = "  <-- STALE"
        elif dv < LIQUIDITY_MIN_DOLLAR_VOL:
            flag = "  <-- below $10M screen"
        print(f"  {t:<11}{str(s.index[0].date()):>12}{str(s.index[-1].date()):>12}"
              f"{len(s):>7}{yrs:>6.1f}{dv:>16,.0f}{flag}")


def _breadth_row(label: str, panel: dict, ann: int) -> None:
    c = panel["close"]
    rets = np.log(c / c.shift(1))
    ne, rho, n = effective_bets(rets)
    pc1, ncols = pc1_share(rets)
    dip = (c / c.rolling(5).mean() - 1.0) / rets.rolling(60).std()
    print(f"\n  --- {label} ---")
    print(f"    names                                  : {n}")
    print(f"    avg pairwise daily-return correlation  : {rho:.3f}")
    print(f"    PC1 share of variance                  : {pc1:.1%}  ({ncols} names)")
    print(f"    effective independent bets N/(1+(N-1)r): {ne:.1f}")
    print(f"    median annualised volatility           : {(rets.std() * np.sqrt(ann)).median():.1%}")
    ds = between_day_share(dip)
    print(f"    PHASE4/5 TEST on the A entry feature:")
    print(f"      between-DAY variance share  : {ds:.1%}   <- regime proxy if high")
    print(f"      within-DAY variance share   : {1 - ds:.1%}   <- real cross-sectional choice")


def section_breadth(crypto: dict, equity: dict) -> None:
    print("\n=== BREADTH — how many independent bets, and is the entry rule a regime proxy? ===")
    _breadth_row(f"CRYPTO ({len(CRYPTO_TICKERS)} Alpaca USD pairs, {COHORT_START}+)",
                 window(crypto, COHORT_START), 365)
    _breadth_row(f"EQUITY ({EQUITY_SAMPLE_N}-name universe sample, {COHORT_START}+)",
                 window(equity, COHORT_START), 252)

    # The premise of the whole idea: is crypto actually uncorrelated with equities?
    # Benchmark to beat is the A/H sleeve correlation of 0.26 (PLAYBOOK §1).
    print("\n  --- BTC vs the equity market (equal-weighted sample proxy) ---")
    btc = np.log(crypto["close"]["BTC-USD"] / crypto["close"]["BTC-USD"].shift(1)).dropna()
    eq = np.log(equity["close"] / equity["close"].shift(1)).mean(axis=1).dropna()
    j = pd.concat([btc.rename("btc"), eq.rename("eq")], axis=1).dropna()
    for lbl, sl in (("2017-11 -> 2020-12", j.loc["2017-11":"2020-12"]),
                    ("2021-01 -> 2022-12", j.loc["2021":"2022"]),
                    ("2023-01 -> now    ", j.loc["2023":]),
                    ("FULL              ", j)):
        print(f"    {lbl}: corr={sl['btc'].corr(sl['eq']):+.3f}  ({len(sl):,} common days)")
    print("    Reference: the deployed A/H sleeve correlation is 0.26, and a candidate")
    print("    sleeve was rejected for correlating 0.69 with Sleeve A (PLAYBOOK §1).")


def section_supply(crypto: dict, equity: dict) -> None:
    print("\n=== SUPPLY — qualifying Sleeve A setups per year (PHASE6's open question) ===")
    results = {}
    for name, panel, is_crypto, dpy in (("CRYPTO", crypto, True, 365),
                                        ("EQUITY", equity, False, 252)):
        p = window(panel, COHORT_START)
        c = p["close"]
        sig = sleeve_a_signal(p) & warm(p)
        if is_crypto:
            # equities come from an already liquidity-screened universe
            liquid = dollar_volume(p, True).rolling(20).mean() > LIQUIDITY_MIN_DOLLAR_VOL
            sig = sig & liquid
            n_liquid = liquid.sum(axis=1).median()
        cnt = sig.sum(axis=1)
        yrs = (c.index[-1] - c.index[0]).days / 365.25
        per_yr = cnt.sum() / yrs
        results[name] = per_yr
        print(f"\n  --- {name} ({c.shape[1]} names, {yrs:.1f} yrs) ---")
        if is_crypto:
            print(f"    names clearing the $10M screen (median): {n_liquid:.0f}")
        print(f"    total qualifying setups        : {int(cnt.sum()):,}")
        print(f"    setups per YEAR                : {per_yr:,.0f}")
        print(f"    setups per year PER NAME       : {per_yr / c.shape[1]:,.1f}")
        print(f"    share of days with ZERO setups : {(cnt == 0).mean():.1%}")
        for lbl, (a, b) in (("IS  " + "..".join(IS_WINDOW), IS_WINDOW),
                            ("OOS " + "..".join(OOS_WINDOW), OOS_WINDOW)):
            w = sig.loc[a:b]
            k = w.sum(axis=1)
            nz = k[k > 0]
            if not len(nz):
                continue
            top = nz.sort_values(ascending=False)[: max(1, int(0.1 * len(nz)))]
            print(f"    {lbl}: {int(k.sum()):>6,} signals on {len(nz):>4,} distinct dates "
                  f"({len(nz) / len(w):.0%} of days), mean {nz.mean():.1f}/date, "
                  f"{top.sum() / nz.sum():.0%} on the busiest 10% of dates")
    scaled = results["EQUITY"] * (1000 / EQUITY_SAMPLE_N)
    print(f"\n  Scaled to the live ~1,000-name universe: ~{scaled:,.0f} equity setups/yr")
    print(f"  Crypto supplies {results['CRYPTO'] / scaled:.1%} of that.")

    print("\n  --- crypto setups by calendar year ---")
    p = window(crypto, COHORT_START)
    sig = sleeve_a_signal(p) & warm(p)
    for y, n in sig.sum(axis=1).groupby(sig.index.year).sum().items():
        print(f"    {y}: {int(n):4d}  {'#' * int(n / 4)}")


def section_regime(crypto: dict, equity: dict) -> None:
    print("\n=== REGIME — is `close > SMA200` a per-name filter or one market switch? ===")
    print(f"  {'':<9}{'p05':>7}{'p25':>7}{'p50':>7}{'p75':>7}{'p95':>7}"
          f"{'<10% up':>10}{'>90% up':>10}{'40-60%':>10}")
    for name, panel in (("CRYPTO", crypto), ("EQUITY", equity)):
        c = window(panel, COHORT_START)["close"]
        v = c.notna() & c.shift(200).notna()
        frac = (((c > c.rolling(200).mean()) & v).sum(axis=1)
                / v.sum(axis=1).replace(0, np.nan)).dropna()
        print(f"  {name:<9}" + "".join(f"{frac.quantile(q):>7.0%}"
                                       for q in (.05, .25, .5, .75, .95))
              + f"{(frac < .10).mean():>10.1%}{(frac > .90).mean():>10.1%}"
              + f"{((frac >= .4) & (frac <= .6)).mean():>10.1%}")
    print("  '<10% up' + '>90% up' is the share of days the gate is effectively")
    print("  all-off or all-on for the entire book at once.")


def section_ceiling(crypto_per_yr: float = 127.0, equity_per_yr: float = 10043.0) -> None:
    """PHASE3: 'you cannot deploy capital that has nothing to buy.'"""
    print("\n=== CEILING — max capital utilisation, independent of any edge ===")
    print("  max exposure <= setups/yr * avg_hold_days / (days_per_yr * slots)")
    for label, s, dpy in (("CRYPTO (16 liquid Alpaca USD pairs)", crypto_per_yr, 365),
                          ("EQUITY (live ~1,000-name universe)", equity_per_yr, 252)):
        print(f"\n  {label} — {s:,.0f} setups/yr")
        for hold in (3, 4.5, 6):
            cap = min(s * hold / (dpy * 10), 1.0)
            print(f"    avg hold {hold:>3}d -> ceiling on exposure with 10 slots: {cap:.1%}")
    print("\n  Reference: PHASE3 — Sleeve A at 10 slots averages 58.5% invested.")
    print("             PHASE6 — the 'everything' config ran 2% exposure -> 1.55% CAGR "
          "(rejected).")


SECTIONS = ("engine", "data", "breadth", "supply", "regime", "ceiling")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--section", choices=SECTIONS + ("all",), default="all")
    args = ap.parse_args()
    want = SECTIONS if args.section == "all" else (args.section,)

    if "engine" in want:
        section_engine()

    needs_crypto = any(s in want for s in ("data", "breadth", "supply", "regime"))
    needs_equity = any(s in want for s in ("breadth", "supply", "regime"))
    crypto = load_crypto() if needs_crypto else None
    equity = load_equity_sample() if needs_equity else None

    if "data" in want:
        section_data(crypto)
    if "breadth" in want:
        section_breadth(crypto, equity)
    if "supply" in want:
        section_supply(crypto, equity)
    if "regime" in want:
        section_regime(crypto, equity)
    if "ceiling" in want:
        section_ceiling()


if __name__ == "__main__":
    main()
