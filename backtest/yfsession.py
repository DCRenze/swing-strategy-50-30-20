"""yfinance transport shim.

yfinance drives curl_cffi with `impersonate="chrome"`, which sends a spoofed
Chrome TLS fingerprint. A TLS-inspecting proxy resets that handshake, so every
download dies with

    curl: (35) Recv failure: Connection reset by peer

while the Yahoo hosts are perfectly reachable and plain curl gets a normal
response. The failure looks exactly like a blocked domain and is not one.

So: try the impersonations in order and keep the first that actually returns
data. "chrome" stays first, so on a normal network (GitHub Actions, a laptop)
nothing changes; the alternates only come into play where Chrome's fingerprint
is being reset.

Override with YF_IMPERSONATE=safari to skip the probe.
"""

from __future__ import annotations

import os

import pandas as pd

IMPERSONATIONS = ("chrome", "safari", "edge99", "chrome110")

_session = None
_resolved: str | None = None


def _make(impersonate: str):
    from curl_cffi import requests as cr

    return cr.Session(impersonate=impersonate)


def download(tickers, **kwargs) -> pd.DataFrame:
    """yf.download, retried across TLS impersonations until one works."""
    import yfinance as yf

    global _session, _resolved

    if _session is not None:
        return yf.download(tickers, session=_session, **kwargs)

    forced = os.getenv("YF_IMPERSONATE")
    candidates = (forced,) if forced else IMPERSONATIONS

    last_err: Exception | None = None
    for imp in candidates:
        try:
            session = _make(imp)
            df = yf.download(tickers, session=session, **kwargs)
            if df is not None and not df.empty:
                _session, _resolved = session, imp
                if imp != IMPERSONATIONS[0]:
                    print(f"NOTE: yfinance TLS impersonation '{imp}' "
                          f"(default '{IMPERSONATIONS[0]}' was reset by the network)",
                          flush=True)
                return df
        except Exception as e:  # noqa: BLE001 - probing transports
            last_err = e
            continue

    if last_err is not None:
        print(f"yfinance download failed on every impersonation "
              f"({', '.join(candidates)}): {last_err}", flush=True)
    return pd.DataFrame()


def resolved() -> str | None:
    """Which impersonation is in use, once one has been established."""
    return _resolved
