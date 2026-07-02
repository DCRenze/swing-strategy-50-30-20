"""Build the stock universe list.

Sources (free, current-constituent — survivorship bias documented in README):
  - S&P 500: Wikipedia constituents table
  - Russell 1000: Wikipedia components table

Output: data/universe.csv with columns ticker, name, source.
Tickers are normalized to Yahoo Finance format (BRK.B -> BRK-B).
"""

import io
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

WIKI_SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
WIKI_R1000 = "https://en.wikipedia.org/wiki/Russell_1000_Index"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-script"}


def normalize(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def fetch_sp500() -> pd.DataFrame:
    resp = requests.get(WIKI_SP500, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]
    out = pd.DataFrame(
        {"ticker": df["Symbol"].map(normalize), "name": df["Security"], "source": "sp500"}
    )
    return out


def fetch_russell1000() -> pd.DataFrame:
    resp = requests.get(WIKI_R1000, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    comp = next(t for t in tables if "Symbol" in t.columns or "Ticker" in t.columns)
    sym_col = "Symbol" if "Symbol" in comp.columns else "Ticker"
    name_col = next((c for c in ("Company", "Security", "Name") if c in comp.columns), sym_col)
    out = pd.DataFrame(
        {
            "ticker": comp[sym_col].astype(str).map(normalize),
            "name": comp[name_col],
            "source": "russell1000",
        }
    )
    out = out[out["ticker"].str.match(r"^[A-Z]{1,5}(-[A-Z])?$", na=False)]
    return out


def build() -> pd.DataFrame:
    frames = []
    try:
        frames.append(fetch_sp500())
        print(f"S&P 500: {len(frames[-1])} tickers")
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: S&P 500 fetch failed: {e}")
    try:
        frames.append(fetch_russell1000())
        print(f"Russell 1000 (Wikipedia): {len(frames[-1])} tickers")
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: Russell 1000 fetch failed: {e}")
    if not frames:
        raise SystemExit("No universe source available")
    uni = pd.concat(frames).drop_duplicates(subset="ticker").sort_values("ticker")
    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "universe.csv"
    # Guard: if one source failed, the rebuilt list can be far smaller than usual,
    # silently dropping names we may hold. Don't clobber a healthy existing list
    # with a degraded one - keep the old universe until a full rebuild succeeds.
    if out_path.exists():
        try:
            prev = pd.read_csv(out_path)
        except Exception:  # noqa: BLE001
            prev = None
        if prev is not None and len(uni) < 0.9 * len(prev):
            print(f"WARNING: rebuilt universe ({len(uni)}) is <90% of the existing "
                  f"list ({len(prev)}) - a source likely failed. Keeping existing universe.csv.")
            return prev
    uni.to_csv(out_path, index=False)
    print(f"Universe: {len(uni)} unique tickers -> {out_path}")
    return uni


if __name__ == "__main__":
    build()
