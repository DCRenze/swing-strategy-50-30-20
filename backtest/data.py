"""Download and cache daily OHLCV for the universe + benchmarks.

Storage: per-field wide parquet (index=date, columns=ticker) in data/:
  raw_open, raw_high, raw_low, raw_close, adj_close, volume

Adjusted OHLC for backtesting is derived at load time:
  factor = adj_close / raw_close;  adj O/H/L = raw O/H/L * factor

Usage:
  python backtest/data.py            # download everything (skips if fresh)
  from backtest.data import load_panel, load_benchmarks
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
START = "2005-01-01"
BENCHMARKS = ["SPY", "QQQ", "^VIX"]
FIELDS = {
    "Open": "raw_open",
    "High": "raw_high",
    "Low": "raw_low",
    "Close": "raw_close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}
BATCH = 50


def _download_batch(tickers: list[str]) -> pd.DataFrame:
    for attempt in range(3):
        try:
            df = yf.download(
                tickers,
                start=START,
                auto_adjust=False,
                actions=False,
                group_by="column",
                threads=True,
                progress=False,
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:  # noqa: BLE001
            print(f"  batch error (attempt {attempt + 1}): {e}", flush=True)
        time.sleep(5 * (attempt + 1))
    return pd.DataFrame()


def download_universe() -> None:
    uni = pd.read_csv(DATA_DIR / "universe.csv")
    tickers = sorted(set(uni["ticker"]) | set(BENCHMARKS))
    print(f"Downloading {len(tickers)} tickers from {START}...", flush=True)

    field_parts: dict[str, list[pd.DataFrame]] = {f: [] for f in FIELDS}
    for i in range(0, len(tickers), BATCH):
        batch = tickers[i : i + BATCH]
        df = _download_batch(batch)
        if df.empty:
            print(f"  SKIPPED batch {i // BATCH + 1} ({batch[0]}..{batch[-1]})", flush=True)
            continue
        # single-ticker batches come back without a column MultiIndex
        if not isinstance(df.columns, pd.MultiIndex):
            df.columns = pd.MultiIndex.from_product([df.columns, batch])
        for field in FIELDS:
            if field in df.columns.get_level_values(0):
                field_parts[field].append(df[field])
        print(
            f"  batch {i // BATCH + 1}/{-(-len(tickers) // BATCH)} done ({batch[0]}..{batch[-1]})",
            flush=True,
        )

    DATA_DIR.mkdir(exist_ok=True)
    for field, fname in FIELDS.items():
        parts = field_parts[field]
        if not parts:
            print(f"WARNING: no data for field {field}")
            continue
        wide = pd.concat(parts, axis=1)
        wide = wide.loc[:, ~wide.columns.duplicated()].sort_index()
        wide.index = pd.to_datetime(wide.index)
        # drop all-NaN tickers (failed symbols)
        wide = wide.dropna(axis=1, how="all")
        wide.to_parquet(DATA_DIR / f"{fname}.parquet")
        print(f"{fname}: {wide.shape[0]} days x {wide.shape[1]} tickers", flush=True)


def load_panel() -> dict[str, pd.DataFrame]:
    """Load adjusted OHLC + raw close/volume panel for backtesting."""
    raw = {name: pd.read_parquet(DATA_DIR / f"{name}.parquet") for name in FIELDS.values()}
    factor = raw["adj_close"] / raw["raw_close"]
    panel = {
        "open": raw["raw_open"] * factor,
        "high": raw["raw_high"] * factor,
        "low": raw["raw_low"] * factor,
        "close": raw["adj_close"],
        "raw_close": raw["raw_close"],
        "volume": raw["volume"],
    }
    return panel


def load_benchmarks() -> dict[str, pd.Series]:
    panel = load_panel()
    return {
        "spy": panel["close"]["SPY"].dropna(),
        "qqq": panel["close"]["QQQ"].dropna(),
        "vix": panel["raw_close"]["^VIX"].dropna(),
    }


if __name__ == "__main__":
    download_universe()
    sys.exit(0)
