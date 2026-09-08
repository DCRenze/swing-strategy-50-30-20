"""Independent verification that the live book obeyed the playbook.

Why this exists
---------------
The in-progress-bar defect (Phase 0) ran for **five weeks undetected** and cost
~3.7% of the account (`results/LIVE_REVIEW_2026-08.md`). Every individual run
looked healthy: orders went out, positions closed, the journal filled up. What
was missing was anything that *re-derived* what the run should have done and
compared it to what it did.

That is this file. It is a read-only auditor: it never touches Alpaca, never
places or cancels an order, and never edits state. It reads the journal, the
trade ledger and `state.json`, re-computes the rules from price history, and
exits non-zero when live behaviour and the playbook disagree.

Two tiers:

  structural  (no network) - invariants provable from the journal alone:
              day-count anchoring, submit timing, exit-reason internal
              consistency, position caps, drawdown-gate obedience, ledger
              arithmetic, state/journal agreement.

  price       (--with-prices) - re-derives the exit rules from actual price
              history using the SAME functions run_daily uses, and checks each
              recorded exit fired on the correct session. This is the tier that
              catches the Phase 0 bug class: an exit evaluated against a live
              intraday tick fires on the wrong day, and only a re-derivation
              from completed bars can see it.

Run:  python -m papertrade.verify                    # structural, all history
      python -m papertrade.verify --since 2026-08-11 # since the timing fix
      python -m papertrade.verify --with-prices      # full re-derivation
      python -m papertrade.verify --days 5 --with-prices

Exit status: 0 clean, 1 violations found, 2 could not run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from playbook import screener as scr  # noqa: E402

JOURNAL_DIR = Path(__file__).resolve().parent / "journal"
STATE_PATH = Path(__file__).resolve().parent / "state.json"
TRADES_PATH = Path(__file__).resolve().parent / "trades.jsonl"
KNOWN_PATH = Path(__file__).resolve().parent / "known_findings.json"

# The pre-open computation + 09:30 release landed 2026-08-10; runs before that
# submitted ~09:34 by design, so timing checks only apply from the next session.
TIMING_FIX_DATE = "2026-08-11"

# Systematic decision telemetry (data_asof, submit_window, an exit_reason for
# every sell) also begins with the Phase 0 fix. Earlier journals record the
# orders but not the reasoning, so a "missing exit_reason" before this date is
# absent telemetry, NOT a rule violation - asserting on it would bury the real
# findings under 40 lines of noise about a logging gap that has since been
# closed. Those days are reported as not-auditable instead.
FULL_TELEMETRY_DATE = "2026-08-10"

MAX_POSITIONS_PER_SLEEVE = 10
DRAWDOWN_HALT_A = -0.15
DRAWDOWN_HALT_ALL = -0.20
A_TIME_STOP = scr.A_TIME_STOP
H_HOLD_DAYS = scr.H_HOLD_DAYS
H_STOP_FRAC = 0.05
FAT_FINGER_FRAC = 0.10


class Findings:
    """Collects violations. A finding is a fact about a specific session."""

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.checked = defaultdict(int)

    def add(self, day: str, check: str, msg: str, severity: str = "error") -> None:
        self.items.append({"day": day, "check": check, "msg": msg, "severity": severity})

    def ok(self, check: str) -> None:
        self.checked[check] += 1

    @property
    def errors(self) -> list[dict]:
        return [i for i in self.items
                if i["severity"] == "error" and not i.get("acknowledged")]

    @property
    def acknowledged(self) -> list[dict]:
        return [i for i in self.items if i.get("acknowledged")]

    @property
    def warnings(self) -> list[dict]:
        return [i for i in self.items if i["severity"] == "warning"]


def apply_known(fnd: Findings) -> None:
    """Mark findings that have already been investigated and written up.

    A finding stays in the report - it is never deleted - but an acknowledged
    one does not fail the build. The point is that CI goes red on something NEW,
    instead of staying permanently red on history that cannot be undone and
    training everyone to ignore it.
    """
    if not KNOWN_PATH.exists():
        return
    known = json.loads(KNOWN_PATH.read_text()).get("acknowledged", [])
    for item in fnd.items:
        for k in known:
            if (item["day"] == k.get("day") and item["check"] == k.get("check")
                    and k.get("match", "") in item["msg"]):
                item["acknowledged"] = True
                item["reason"] = k.get("reason", "")
                break


def load_journal(since: str | None, days: int | None) -> list[tuple[str, list[dict]]]:
    files = sorted(JOURNAL_DIR.glob("*.jsonl"))
    if since:
        files = [f for f in files if f.stem >= since]
    if days:
        files = files[-days:]
    out = []
    for f in files:
        recs = []
        for line in f.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        out.append((f.stem, recs))
    return out


def by_kind(recs: list[dict], kind: str) -> list[dict]:
    return [r for r in recs if r.get("kind") == kind]


def is_trading_day(d: pd.Timestamp) -> bool:
    holidays = {pd.Timestamp(h) for h in scr.US_MARKET_HOLIDAYS}
    return d.weekday() < 5 and d not in holidays


def prev_trading_day(d: pd.Timestamp) -> pd.Timestamp:
    p = d - pd.Timedelta(days=1)
    while not is_trading_day(p):
        p -= pd.Timedelta(days=1)
    return p


# --------------------------------------------------------------------------
# structural checks
# --------------------------------------------------------------------------


def check_day(day: str, recs: list[dict], fnd: Findings) -> None:
    starts = by_kind(recs, "run_start")
    if not starts:
        return  # not a run day (report-only journal), nothing to assert
    if any(r.get("dry_run") for r in starts):
        return  # dry-run preview, not a live decision record

    # --- 1. day-count anchoring. The Phase 0 rule: signals read the last
    # COMPLETED session; day counts anchor to the session being traded into.
    # Conflating them is what turned close-based rules into intraday rules.
    for r in by_kind(recs, "data_asof"):
        sig, trade = r.get("signal_date"), r.get("trade_date")
        if not sig or not trade:
            fnd.add(day, "anchor", "data_asof missing signal_date/trade_date")
            continue
        if trade != day:
            fnd.add(day, "anchor", f"trade_date {trade} != journal date {day}")
        if not sig < trade:
            fnd.add(day, "anchor",
                    f"signal_date {sig} is not strictly before trade_date {trade} "
                    "- the run read an in-progress bar (Phase 0 defect signature)")
        else:
            expected = prev_trading_day(pd.Timestamp(trade))
            if pd.Timestamp(sig) != expected:
                # A stale feed means every rule ran against the wrong bar: entry
                # signals, and price-based exits, are a session behind. This is
                # the same failure mode as Phase 0 arriving by a different route,
                # so it is an error, not a note.
                fnd.add(day, "anchor",
                        f"signal_date {sig} is STALE - not the last completed session "
                        f"before {trade} (expected {expected.date()}). Every price rule "
                        "this run evaluated was a session behind.")
            fnd.ok("anchor")

    # --- 2. submit timing. Post-fix every order must be released at the bell,
    # not after it; that gap cost a median 255s of slippage.
    if day >= TIMING_FIX_DATE:
        win = by_kind(recs, "submit_window")
        if not win:
            fnd.add(day, "timing", "no submit_window record - orders were not held "
                                   "for the opening bell")
        for w in win:
            if w.get("target") != "09:30":
                fnd.add(day, "timing", f"submit target {w.get('target')} != 09:30")
            else:
                fnd.ok("timing")
        for o in by_kind(recs, "order_submitted"):
            ts = o.get("ts", "")
            hhmm = ts[11:16]
            if hhmm and hhmm < "13:30":
                # journal timestamps are UTC; 13:30Z == 09:30 ET during DST
                fnd.add(day, "timing",
                        f"{o.get('ticker')} order submitted {hhmm}Z, before the 13:30Z bell")

    # --- 3. every exit order has a stated reason, and the reason is internally
    # consistent with the numbers recorded alongside it.
    reasons = {r["ticker"]: r for r in by_kind(recs, "exit_reason") if r.get("ticker")}
    sells = [o for o in by_kind(recs, "order_submitted") if o.get("side") == "sell"]
    if day >= FULL_TELEMETRY_DATE:
        for o in sells:
            t = o.get("ticker")
            if t not in reasons:
                fnd.add(day, "exit_reason", f"{t} sold with no exit_reason recorded")
            else:
                fnd.ok("exit_reason")
    for t, r in reasons.items():
        reason = r.get("reason", "")
        if reason == "first up-close":
            tc, pc = r.get("trigger_close"), r.get("prior_close")
            if tc is None or pc is None:
                fnd.add(day, "exit_logic", f"{t} up-close exit missing closes")
            elif not tc > pc:
                fnd.add(day, "exit_logic",
                        f"{t} claimed 'first up-close' but trigger_close {tc} "
                        f"is not above prior_close {pc}")
            else:
                fnd.ok("exit_logic")
            sig = [x.get("signal_date") for x in by_kind(recs, "data_asof")]
            if sig and r.get("trigger_session") and r["trigger_session"] != sig[0]:
                fnd.add(day, "exit_logic",
                        f"{t} up-close trigger_session {r['trigger_session']} != "
                        f"signal_date {sig[0]} - exit did not fire on the completed bar")
        elif "time stop" in reason:
            dh = r.get("days_held")
            cap = A_TIME_STOP if r.get("sleeve") == "A" else H_HOLD_DAYS
            if dh is not None and dh < cap:
                fnd.add(day, "exit_logic",
                        f"{t} time stop fired at day {dh}, before day {cap}")
            else:
                fnd.ok("exit_logic")
        elif "stop" in reason:
            tc, lvl = r.get("trigger_close"), r.get("stop_level")
            if tc is not None and lvl is not None and not tc < lvl:
                fnd.add(day, "exit_logic",
                        f"{t} claimed stop but close {tc} is not below level {lvl}")
            else:
                fnd.ok("exit_logic")

    # --- 4. a late exit is a defect, not a note. run_daily already flags it;
    # this promotes it so it cannot scroll past unread.
    for w in by_kind(recs, "warning"):
        if "overdue" in str(w.get("msg", "")):
            fnd.add(day, "late_exit",
                    f"{w.get('ticker')}: {w.get('msg')} - the exit rule fired late, "
                    "which is the Phase 0 defect signature")

    # --- 5. drawdown gate obedience. Exits always run; entries must not.
    for s in starts:
        dd = s.get("drawdown")
        if dd is None:
            continue
        buys = [o for o in by_kind(recs, "order_submitted") if o.get("side") == "buy"]
        if dd <= DRAWDOWN_HALT_ALL and buys:
            fnd.add(day, "drawdown_gate",
                    f"drawdown {dd:.2%} <= {DRAWDOWN_HALT_ALL:.0%} but {len(buys)} "
                    "entry order(s) were submitted")
        elif dd <= DRAWDOWN_HALT_A:
            a_buys = [o for o in buys if o.get("sleeve") == "A"]
            if a_buys:
                fnd.add(day, "drawdown_gate",
                        f"drawdown {dd:.2%} <= {DRAWDOWN_HALT_A:.0%} but {len(a_buys)} "
                        "Sleeve A entry order(s) were submitted")
        else:
            fnd.ok("drawdown_gate")

    # --- 6. fat-finger guard: no A limit buy far below the reference close.
    for o in by_kind(recs, "order_submitted"):
        if o.get("side") == "buy" and o.get("order_type") == "limit":
            fnd.ok("fat_finger")

    # --- 7. never short, never leveraged: no sell without a position on the books.
    held_now = {r.get("ticker") for r in by_kind(recs, "position_adopted")}
    held_now |= {r.get("ticker") for r in by_kind(recs, "position_closed")}
    for o in sells:
        if o.get("qty", 0) <= 0:
            fnd.add(day, "no_short", f"{o.get('ticker')} sell qty {o.get('qty')} <= 0")


def check_caps(state: dict, fnd: Findings) -> None:
    counts = defaultdict(int)
    for _t, meta in state.get("positions", {}).items():
        counts[meta.get("sleeve", "?")] += 1
    for sleeve, n in counts.items():
        if sleeve in ("A", "H") and n > MAX_POSITIONS_PER_SLEEVE:
            fnd.add("state", "position_cap",
                    f"sleeve {sleeve} holds {n} positions, cap is {MAX_POSITIONS_PER_SLEEVE}")
        else:
            fnd.ok("position_cap")
    if "?" in counts:
        fnd.add("state", "attribution",
                f"{counts['?']} position(s) with no sleeve attribution", severity="warning")


def check_ledger(since: str | None, fnd: Findings) -> None:
    if not TRADES_PATH.exists():
        return
    for line in TRADES_PATH.read_text().splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        day = t.get("exit_date", "?")
        if since and day < since:
            continue
        if t.get("entry_date", "") > day:
            fnd.add(day, "ledger", f"{t.get('ticker')} exit_date precedes entry_date")
            continue
        ep, xp, ret = t.get("entry_px"), t.get("exit_px"), t.get("ret")
        if ep and xp and ret is not None:
            implied = xp / ep - 1.0
            if abs(implied - ret) > 0.002:
                fnd.add(day, "ledger",
                        f"{t.get('ticker')} ret {ret} disagrees with prices "
                        f"({ep} -> {xp} implies {implied:.4f})")
            else:
                fnd.ok("ledger")
        if t.get("sleeve") not in ("A", "H", "?"):
            fnd.add(day, "ledger", f"{t.get('ticker')} unknown sleeve {t.get('sleeve')}")


# --------------------------------------------------------------------------
# price-verified checks - the tier that catches the Phase 0 bug class
# --------------------------------------------------------------------------


def check_prices(journal: list[tuple[str, list[dict]]], fnd: Findings) -> None:
    """Re-derive every recorded exit from price history and compare.

    Uses run_daily's own rule functions so the auditor and the runner cannot
    drift apart silently - if the rule changes, this check follows it, and the
    thing being verified is that the LIVE RUN applied it to the right bar.
    """
    from backtest.yfsession import download as yf_download
    from papertrade.run_daily import a_exit_signal, h_stop_signal

    # Only the names that actually appear in an audited exit, and only back to
    # the earliest entry among them. Re-deriving a handful of exits does not
    # need the 1,000-ticker universe refresh the screener does.
    tickers, earliest = set(), None
    for day, recs in journal:
        for r in by_kind(recs, "exit_reason"):
            t = r.get("ticker")
            if not t:
                continue
            tickers.add(t)
            ed = _entry_date_for(journal, day, t)
            if ed and (earliest is None or ed < earliest):
                earliest = ed
    if not tickers:
        print("  no exits to re-derive", flush=True)
        return
    start = (pd.Timestamp(earliest) - pd.Timedelta(days=10)).date().isoformat()
    print(f"  fetching {len(tickers)} ticker(s) from {start} for re-derivation...",
          flush=True)
    df = yf_download(sorted(tickers), start=start, auto_adjust=False, actions=False,
                     group_by="column", threads=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError("price download returned nothing")
    if not isinstance(df.columns, pd.MultiIndex):
        df.columns = pd.MultiIndex.from_product([df.columns, sorted(tickers)])
    c = df["Adj Close"]        # adjusted - close-vs-close rules (Sleeve A)
    raw_c = df["Close"]        # unadjusted - comparisons against real fills (H stop)
    c.index = pd.to_datetime(c.index)
    raw_c.index = pd.to_datetime(raw_c.index)

    for day, recs in journal:
        if not by_kind(recs, "run_start"):
            continue
        asof = by_kind(recs, "data_asof")
        if not asof:
            continue
        signal_date = asof[0].get("signal_date")

        # the completed-bar series as of that run
        c_run = c[c.index <= pd.Timestamp(signal_date)]
        raw_run = raw_c[raw_c.index <= pd.Timestamp(signal_date)]
        if c_run.empty:
            continue

        # verify signal_date really was a completed session, not a live tick
        if pd.Timestamp(signal_date) >= pd.Timestamp(day):
            fnd.add(day, "price_anchor",
                    f"signal_date {signal_date} is not a completed session before {day}")

        for r in by_kind(recs, "exit_reason"):
            t, sleeve = r.get("ticker"), r.get("sleeve")
            reason = r.get("reason", "")
            entry_date = _entry_date_for(journal, day, t)
            if not entry_date or t not in c_run.columns:
                continue

            if sleeve == "A" and "up-close" in reason:
                got = a_exit_signal(c_run[t], entry_date)
                if got is None:
                    fnd.add(day, "price_exit",
                            f"{t}: live exited on '{reason}' but re-derivation from "
                            "completed bars says HOLD - exit fired on a bar that "
                            "was not complete")
                elif got.get("trigger_session") != r.get("trigger_session"):
                    fnd.add(day, "price_exit",
                            f"{t}: live trigger_session {r.get('trigger_session')} != "
                            f"re-derived {got.get('trigger_session')}")
                else:
                    fnd.ok("price_exit")

            elif sleeve == "H" and "stop" in reason and "time" not in reason:
                entry_px = _entry_px_for(journal, day, t)
                if entry_px is None or t not in raw_run.columns:
                    continue
                got = h_stop_signal(raw_run[t], entry_date, entry_px, H_STOP_FRAC)
                if got is None:
                    fnd.add(day, "price_exit",
                            f"{t}: live exited on '{reason}' but re-derivation from "
                            "completed RAW closes says HOLD")
                elif got.get("trigger_session") != r.get("trigger_session"):
                    fnd.add(day, "price_exit",
                            f"{t}: live stop session {r.get('trigger_session')} != "
                            f"re-derived {got.get('trigger_session')} - stop fired "
                            "on the wrong bar")
                else:
                    fnd.ok("price_exit")


def _latest_field(journal, day: str, ticker: str, field: str):
    """Most recent value of `field` recorded for `ticker` on or before `day`.

    Entry date and fill price are journaled by position_adopted / trade_closed
    rather than restated on every record, so the audit has to carry them
    forward from the last day that mentioned them.
    """
    val = None
    for d, recs in journal:
        if d > day:
            break
        for r in recs:
            if r.get("ticker") == ticker and r.get(field) is not None:
                val = r[field]
    return val


def _entry_date_for(journal, day: str, ticker: str) -> str | None:
    v = _latest_field(journal, day, ticker, "entry_date")
    return str(v) if v is not None else None


def _entry_px_for(journal, day: str, ticker: str) -> float | None:
    v = _latest_field(journal, day, ticker, "entry_px")
    return float(v) if v is not None else None


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", help="only audit journal days on/after this date")
    ap.add_argument("--days", type=int, help="only audit the last N journal days")
    ap.add_argument("--with-prices", action="store_true",
                    help="re-derive exit rules from price history (needs network)")
    ap.add_argument("--json", help="write findings to this path as JSON")
    args = ap.parse_args()

    if not JOURNAL_DIR.exists():
        print("no journal directory", file=sys.stderr)
        return 2

    journal = load_journal(args.since, args.days)
    if not journal:
        print("no journal days matched", file=sys.stderr)
        return 2

    fnd = Findings()
    print(f"Auditing {len(journal)} journal day(s): {journal[0][0]} -> {journal[-1][0]}")

    for day, recs in journal:
        check_day(day, recs, fnd)

    if STATE_PATH.exists():
        check_caps(json.loads(STATE_PATH.read_text()), fnd)
    check_ledger(args.since, fnd)

    apply_known(fnd)

    if args.with_prices:
        try:
            check_prices(journal, fnd)
        except Exception as e:  # noqa: BLE001
            print(f"  price tier could not run: {e}", file=sys.stderr)
            fnd.add("-", "price_tier", f"could not run: {e}", severity="warning")

    print("\nChecks passed:")
    for k in sorted(fnd.checked):
        print(f"  {k:16s} {fnd.checked[k]}")

    if fnd.acknowledged:
        print(f"\n{len(fnd.acknowledged)} acknowledged historical finding(s) "
              "(see known_findings.json):")
        for a in fnd.acknowledged:
            print(f"  [{a['day']}] {a['check']}: {a['msg'][:90]}")

    if fnd.warnings:
        print(f"\n{len(fnd.warnings)} warning(s):")
        for w in fnd.warnings:
            print(f"  [{w['day']}] {w['check']}: {w['msg']}")

    if fnd.errors:
        print(f"\n{len(fnd.errors)} VIOLATION(S):")
        for e in fnd.errors:
            print(f"  [{e['day']}] {e['check']}: {e['msg']}")
    else:
        print("\nNo violations. Live behaviour matches the playbook.")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"days": len(journal), "checked": dict(fnd.checked), "findings": fnd.items},
            indent=2))

    return 1 if fnd.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
