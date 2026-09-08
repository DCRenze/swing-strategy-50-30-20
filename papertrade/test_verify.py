"""Tests for the live-behaviour auditor.

An auditor that cannot fail is worthless, so these tests are mostly the
negative direction: build a journal that contains a known defect and assert
`verify` reports it. Each fixture is a defect that actually happened, or the
defect class the auditor exists to catch.

Run:  python -m papertrade.test_verify
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from papertrade import verify as vf


def journal(day: str, records: list[dict]) -> list[tuple[str, list[dict]]]:
    return [(day, records)]


def run_day(day: str, records: list[dict]) -> vf.Findings:
    fnd = vf.Findings()
    vf.check_day(day, records, fnd)
    return fnd


def codes(fnd: vf.Findings) -> set[str]:
    return {i["check"] for i in fnd.errors}


BASE = [
    {"kind": "run_start", "mode": "morning", "equity": 100_000.0, "hwm": 100_000.0,
     "drawdown": 0.0, "dry_run": False},
    {"kind": "data_asof", "signal_date": "2026-09-03", "trade_date": "2026-09-04"},
    {"kind": "submit_window", "target": "09:30", "waited_s": 500.0},
]


# ------------------------------------------------------------------ anchor ---
def test_clean_day_passes():
    fnd = run_day("2026-09-04", BASE)
    assert not fnd.errors, fnd.errors
    print("ok: a clean session produces no findings")


def test_in_progress_bar_is_caught():
    """The Phase 0 defect: signal_date == trade_date means a live tick was read."""
    recs = [dict(r) for r in BASE]
    recs[1] = {"kind": "data_asof", "signal_date": "2026-09-04",
               "trade_date": "2026-09-04"}
    fnd = run_day("2026-09-04", recs)
    assert "anchor" in codes(fnd), fnd.items
    assert any("in-progress bar" in e["msg"] for e in fnd.errors)
    print("ok: signal_date == trade_date is caught (Phase 0 defect signature)")


def test_stale_feed_is_caught():
    """2026-08-18 really happened: Monday's bar never arrived, so the run
    evaluated every price rule against Friday's close."""
    recs = [dict(r) for r in BASE]
    recs[1] = {"kind": "data_asof", "signal_date": "2026-08-14",
               "trade_date": "2026-08-18"}
    fnd = run_day("2026-08-18", recs)
    assert "anchor" in codes(fnd), fnd.items
    assert any("STALE" in e["msg"] for e in fnd.errors)
    print("ok: a stale feed (2026-08-18 tape) is caught")


def test_weekend_gap_is_not_stale():
    """Monday reading Friday's close is correct, not stale."""
    recs = [dict(r) for r in BASE]
    recs[1] = {"kind": "data_asof", "signal_date": "2026-09-04",
               "trade_date": "2026-09-07"}
    fnd = run_day("2026-09-07", recs)
    assert "anchor" not in codes(fnd), fnd.items
    print("ok: a weekend gap is not mistaken for stale data")


# ------------------------------------------------------------------ timing ---
def test_order_before_the_bell_is_caught():
    recs = BASE + [{"kind": "order_submitted", "ts": "2026-09-04T13:22:10",
                    "sleeve": "A", "ticker": "AAPL", "side": "sell", "qty": 5.0,
                    "order_type": "market"}]
    fnd = run_day("2026-09-04", recs)
    assert "timing" in codes(fnd), fnd.items
    print("ok: an order released before the 13:30Z bell is caught")


def test_missing_submit_window_is_caught():
    recs = [r for r in BASE if r["kind"] != "submit_window"]
    fnd = run_day("2026-09-04", recs)
    assert "timing" in codes(fnd), fnd.items
    print("ok: a run that did not hold orders for the bell is caught")


# -------------------------------------------------------------- exit logic ---
def test_sell_without_reason_is_caught():
    recs = BASE + [{"kind": "order_submitted", "ts": "2026-09-04T13:30:00",
                    "sleeve": "A", "ticker": "AAPL", "side": "sell", "qty": 5.0,
                    "order_type": "market"}]
    fnd = run_day("2026-09-04", recs)
    assert "exit_reason" in codes(fnd), fnd.items
    print("ok: a sell with no recorded reason is caught")


def test_incoherent_up_close_is_caught():
    """'first up-close' whose trigger is not actually above the prior close."""
    recs = BASE + [
        {"kind": "order_submitted", "ts": "2026-09-04T13:30:00", "sleeve": "A",
         "ticker": "AAPL", "side": "sell", "qty": 5.0, "order_type": "market"},
        {"kind": "exit_reason", "ticker": "AAPL", "sleeve": "A", "days_held": 3,
         "signal_date": "2026-09-03", "reason": "first up-close",
         "trigger_close": 100.0, "prior_close": 105.0,
         "trigger_session": "2026-09-03"},
    ]
    fnd = run_day("2026-09-04", recs)
    assert "exit_logic" in codes(fnd), fnd.items
    print("ok: an up-close exit that is not an up-close is caught")


def test_up_close_off_the_completed_bar_is_caught():
    """trigger_session must be the completed session the rules read."""
    recs = BASE + [
        {"kind": "order_submitted", "ts": "2026-09-04T13:30:00", "sleeve": "A",
         "ticker": "AAPL", "side": "sell", "qty": 5.0, "order_type": "market"},
        {"kind": "exit_reason", "ticker": "AAPL", "sleeve": "A", "days_held": 3,
         "signal_date": "2026-09-03", "reason": "first up-close",
         "trigger_close": 106.0, "prior_close": 105.0,
         "trigger_session": "2026-09-04"},
    ]
    fnd = run_day("2026-09-04", recs)
    assert any("did not fire on the completed bar" in e["msg"] for e in fnd.errors)
    print("ok: an exit triggered off an incomplete bar is caught")


def test_early_time_stop_is_caught():
    recs = BASE + [
        {"kind": "order_submitted", "ts": "2026-09-04T13:30:00", "sleeve": "H",
         "ticker": "AAPL", "side": "sell", "qty": 5.0, "order_type": "market"},
        {"kind": "exit_reason", "ticker": "AAPL", "sleeve": "H", "days_held": 4,
         "reason": "15d time stop", "signal_date": "2026-09-03"},
    ]
    fnd = run_day("2026-09-04", recs)
    assert "exit_logic" in codes(fnd), fnd.items
    print("ok: a time stop firing before its day is caught")


def test_stop_above_its_level_is_caught():
    recs = BASE + [
        {"kind": "order_submitted", "ts": "2026-09-04T13:30:00", "sleeve": "H",
         "ticker": "AAPL", "side": "sell", "qty": 5.0, "order_type": "market"},
        {"kind": "exit_reason", "ticker": "AAPL", "sleeve": "H", "days_held": 6,
         "reason": "5% stop", "trigger_close": 99.0, "stop_level": 95.0,
         "trigger_session": "2026-09-03"},
    ]
    fnd = run_day("2026-09-04", recs)
    assert "exit_logic" in codes(fnd), fnd.items
    print("ok: a stop that did not breach its level is caught")


def test_late_exit_is_promoted_to_a_violation():
    recs = BASE + [{"kind": "warning", "ticker": "BROS",
                    "msg": "multiple up-closes since entry - exiting now (overdue)"}]
    fnd = run_day("2026-09-04", recs)
    assert "late_exit" in codes(fnd), fnd.items
    print("ok: an overdue exit is a violation, not a note")


# ----------------------------------------------------------- risk controls ---
def test_entry_during_full_halt_is_caught():
    recs = [dict(r) for r in BASE]
    recs[0] = {"kind": "run_start", "mode": "morning", "equity": 79_000.0,
               "hwm": 100_000.0, "drawdown": -0.21, "dry_run": False}
    recs += [{"kind": "order_submitted", "ts": "2026-09-04T13:30:00", "sleeve": "H",
              "ticker": "AAPL", "side": "buy", "qty": 5.0, "order_type": "market"}]
    fnd = run_day("2026-09-04", recs)
    assert "drawdown_gate" in codes(fnd), fnd.items
    print("ok: an entry below the -20% halt is caught")


def test_sleeve_a_entry_during_a_halt_is_caught():
    recs = [dict(r) for r in BASE]
    recs[0] = {"kind": "run_start", "mode": "morning", "equity": 84_000.0,
               "hwm": 100_000.0, "drawdown": -0.16, "dry_run": False}
    recs += [{"kind": "order_submitted", "ts": "2026-09-04T13:30:00", "sleeve": "A",
              "ticker": "AAPL", "side": "buy", "qty": 5.0, "order_type": "limit",
              "limit_price": 100.0}]
    fnd = run_day("2026-09-04", recs)
    assert "drawdown_gate" in codes(fnd), fnd.items
    print("ok: a Sleeve A entry below the -15% halt is caught")


def test_h_entry_allowed_during_sleeve_a_halt():
    """Between -15% and -20% only Sleeve A stops; H entries and all exits run."""
    recs = [dict(r) for r in BASE]
    recs[0] = {"kind": "run_start", "mode": "morning", "equity": 84_000.0,
               "hwm": 100_000.0, "drawdown": -0.16, "dry_run": False}
    recs += [{"kind": "order_submitted", "ts": "2026-09-04T13:30:00", "sleeve": "H",
              "ticker": "AAPL", "side": "buy", "qty": 5.0, "order_type": "market"}]
    fnd = run_day("2026-09-04", recs)
    assert "drawdown_gate" not in codes(fnd), fnd.items
    print("ok: an H entry inside the Sleeve A halt band is allowed")


def test_position_cap_is_caught():
    state = {"positions": {f"T{i}": {"sleeve": "H"} for i in range(11)}}
    fnd = vf.Findings()
    vf.check_caps(state, fnd)
    assert "position_cap" in codes(fnd), fnd.items
    print("ok: exceeding the 10-position sleeve cap is caught")


def test_dry_run_is_not_audited():
    recs = [dict(r) for r in BASE]
    recs[0] = dict(recs[0], dry_run=True)
    recs[1] = {"kind": "data_asof", "signal_date": "2026-09-04",
               "trade_date": "2026-09-04"}
    fnd = run_day("2026-09-04", recs)
    assert not fnd.errors, fnd.errors
    print("ok: a dry-run preview is not audited as a live decision")


# ------------------------------------------------------------------ ledger ---
def test_ledger_arithmetic_is_checked():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "trades.jsonl"
        path.write_text(json.dumps({
            "ticker": "AAPL", "sleeve": "A", "entry_date": "2026-09-01",
            "exit_date": "2026-09-04", "entry_px": 100.0, "exit_px": 110.0,
            "qty": 5.0, "ret": -0.5, "pnl": 50.0,
        }) + "\n")
        original = vf.TRADES_PATH
        vf.TRADES_PATH = path
        try:
            fnd = vf.Findings()
            vf.check_ledger(None, fnd)
            assert "ledger" in codes(fnd), fnd.items
        finally:
            vf.TRADES_PATH = original
    print("ok: a return that disagrees with its own fill prices is caught")


# --------------------------------------------------------- acknowledgement ---
def test_acknowledgement_does_not_suppress_new_findings():
    """The baseline must match on day+check+text, never blanket-mute a check."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "known.json"
        path.write_text(json.dumps({"acknowledged": [
            {"day": "2026-08-18", "check": "anchor", "match": "STALE",
             "reason": "investigated"}]}))
        original = vf.KNOWN_PATH
        vf.KNOWN_PATH = path
        try:
            fnd = vf.Findings()
            fnd.add("2026-08-18", "anchor", "signal_date 2026-08-14 is STALE ...")
            fnd.add("2026-09-04", "anchor", "signal_date 2026-09-03 is STALE ...")
            vf.apply_known(fnd)
            assert len(fnd.acknowledged) == 1
            assert len(fnd.errors) == 1, "a NEW stale day must still fail"
            assert fnd.errors[0]["day"] == "2026-09-04"
        finally:
            vf.KNOWN_PATH = original
    print("ok: acknowledging one day does not mute the same defect on another")


def test_acknowledged_findings_still_appear():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "known.json"
        path.write_text(json.dumps({"acknowledged": [
            {"day": "2026-08-10", "check": "late_exit", "match": "CF",
             "reason": "transition day"}]}))
        original = vf.KNOWN_PATH
        vf.KNOWN_PATH = path
        try:
            fnd = vf.Findings()
            fnd.add("2026-08-10", "late_exit", "CF: overdue")
            vf.apply_known(fnd)
            assert not fnd.errors
            assert fnd.acknowledged[0]["reason"] == "transition day"
            assert len(fnd.items) == 1, "the finding is recorded, not deleted"
        finally:
            vf.KNOWN_PATH = original
    print("ok: an acknowledged finding is still reported, with its reason")


if __name__ == "__main__":
    test_clean_day_passes()
    test_in_progress_bar_is_caught()
    test_stale_feed_is_caught()
    test_weekend_gap_is_not_stale()
    test_order_before_the_bell_is_caught()
    test_missing_submit_window_is_caught()
    test_sell_without_reason_is_caught()
    test_incoherent_up_close_is_caught()
    test_up_close_off_the_completed_bar_is_caught()
    test_early_time_stop_is_caught()
    test_stop_above_its_level_is_caught()
    test_late_exit_is_promoted_to_a_violation()
    test_entry_during_full_halt_is_caught()
    test_sleeve_a_entry_during_a_halt_is_caught()
    test_h_entry_allowed_during_sleeve_a_halt()
    test_position_cap_is_caught()
    test_dry_run_is_not_audited()
    test_ledger_arithmetic_is_checked()
    test_acknowledgement_does_not_suppress_new_findings()
    test_acknowledged_findings_still_appear()
    print("\nall auditor tests passed")
