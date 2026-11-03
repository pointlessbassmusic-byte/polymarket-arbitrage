"""Dashboard dataset files: derived from the journals, the box's run log, the registry and the ledger; totals agree with
the tracker's accounting."""

import json

from mandel.live import dashboard_export as X
from mandel.live import tracker as T


def _fill(cid, side, qty, px, at, status="filled"):
    return {"kind": "order.fill", "client_order_id": cid, "symbol": cid.split("-")[2], "side": side, "qty": str(qty),
            "filled_qty": str(qty), "filled_avg_price": px, "status": status, "filled_at": at}


def _journal():
    return [
        {"kind": "close.decision", "day": "2026-10-22", "equity": 1000.0, "snapshot_splg": {"high": 10, "low": 9, "last": 9.1},
         "reasons": {"overnight": "hold QQQM", "ibs": "IBS 0.1 < 0.2: hold SPYM to the next close", "tom": "not a turn-of-month day"},
         "targets": {"QQQM": 400.0, "SPYM": 300.0}},
        _fill("m-cls-QQQM-2026-10-22-aa", "buy", 4, 100.0, "2026-10-22T19:44:01Z"),
        _fill("m-cls-SPYM-2026-10-22-ab", "buy", 10, 50.0, "2026-10-22T19:44:02Z"),
        _fill("m-opg-QQQM-2026-10-23-ac", "sell", 4, 101.0, "2026-10-23T13:33:01Z"),
        {"kind": "close.decision", "day": "2026-10-23", "equity": 1004.0, "snapshot_splg": {"high": 10, "low": 9, "last": 9.9},
         "reasons": {"overnight": "hold QQQM", "ibs": "IBS 0.9: no", "tom": "not"}, "targets": {"QQQM": 400.0}},
        _fill("m-cls-SPYM-2026-10-23-ad", "sell", 10, 49.0, "2026-10-23T19:44:01Z"),
        {"kind": "print.official", "symbol": "QQQM", "day": "2026-10-22", "close": 100.2, "open": 99.0},
        {"kind": "print.official", "symbol": "QQQM", "day": "2026-10-23", "close": 102.0, "open": 100.8},
    ]


def test_round_trips_match_the_tracker_and_mark_the_official_prints():
    j = _journal()
    trips = X.round_trips(j)
    assert [t["symbol"] for t in trips] == ["QQQM", "SPYM"]
    assert trips[0]["pnl_usd"] == 4.0 and trips[0]["shadow_pnl_usd"] == round(4 * (100.8 - 100.2), 2)
    assert trips[1]["pnl_usd"] == -10.0 and trips[1]["shadow_pnl_usd"] is None and trips[1]["rule"] == "IBS SPYM"
    prog = T.calendar_progress(j)
    assert round(sum(t["pnl_usd"] for t in trips), 2) == prog["pnl_usd"]
    assert round(sum(t["shadow_pnl_usd"] for t in trips if t["shadow_pnl_usd"] is not None), 2) == prog["shadow_pnl_usd"]


def test_sessions_carry_ibs_rules_and_the_running_total():
    s = X.paper_sessions(_journal())
    assert [r["day"] for r in s] == ["2026-10-22", "2026-10-23"]
    assert s[0]["ibs_15_45"] == 0.1 and s[0]["ibs_fired"] and not s[0]["tom_window"] and s[0]["target_spym_usd"] == 300.0
    assert s[0]["realised_pnl_to_date_usd"] == 0.0 and s[1]["realised_pnl_to_date_usd"] == -6.0 and s[1]["round_trips_closed"] == 2


def test_fills_carry_the_official_print_gap():
    f = X.paper_fills(_journal())
    buy = next(r for r in f if r["symbol"] == "QQQM" and r["side"] == "buy")
    assert buy["official_print"] == 100.2 and buy["gap_bp"] == round(abs(100 - 100.2) / 100.2 * 1e4, 2) and buy["phase"] == "close"
    assert next(r for r in f if r["symbol"] == "SPYM" and r["side"] == "sell")["rule"] == "IBS SPYM"


def test_wide_orders_parse_both_id_shapes():
    w = [{"kind": "order.fill", "client_order_id": "w-USO-open-2026-10-20", "qty": "1", "filled_avg_price": "-0.55", "status": "filled"},
         {"kind": "order.fill", "client_order_id": "w-cls-IEF-2026-10-30-56e9bc", "side": "sell", "qty": "16", "filled_avg_price": "91.65", "status": "filled"},
         {"kind": "order.fill", "client_order_id": "w-TLT-open-2026-10-20", "qty": "1", "filled_avg_price": None, "status": "expired"}]
    rows = {r["order"]: r for r in X.wide_orders(w)}
    assert rows["w-cls-IEF-2026-10-30-56e9bc"]["underlying"] == "IEF" and rows["w-cls-IEF-2026-10-30-56e9bc"]["kind"] == "stock"
    assert rows["w-USO-open-2026-10-20"]["side"] == "open spread" and rows["w-USO-open-2026-10-20"]["price"] == -0.55
    assert rows["w-TLT-open-2026-10-20"]["price"] is None and rows["w-TLT-open-2026-10-20"]["status"] == "expired"


def test_capture_health_and_registry_timeline():
    runs = [{"ts": "2026-10-20T22:30:00+00:00", "steps": [{"step": "a", "rc": 0}, {"step": "b", "rc": 0}]},
            {"ts": "2026-10-21T22:30:00+00:00", "steps": [{"step": "a", "rc": 1, "tail": ["x", "ModuleNotFoundError: pandas"]}, {"step": "b", "rc": 0}]}]
    h = X.capture_health(runs)
    assert h[0]["ok"] and h[1] == {"day": "2026-10-21", "steps": 2, "failed": 1, "ok": False, "first_error": "ModuleNotFoundError: pandas"}
    led = [{"ts": "2026-10-14T01:00:00", "kind": "theory.preregistered"},
           {"ts": "2026-10-14T02:00:00", "kind": "experiment.recorded", "payload": {"verdict": "supported"}},
           {"ts": "2026-10-15T02:00:00", "kind": "experiment.recorded", "payload": {"verdict": "not_supported"}},
           {"ts": "2026-10-15T03:00:00", "kind": "archive.stored"}]
    tl = X.registry_timeline(led)
    assert tl[-1] == {"day": "2026-10-15", "preregistered_cum": 1, "experiments_cum": 2, "supported_cum": 1,
                      "not_supported_cum": 1, "inconclusive_cum": 0, "experiments_today": 1}


def test_build_writes_every_dataset(tmp_path):
    counts = X.build(tmp_path)
    assert set(counts) >= {"paper_sessions", "paper_round_trips", "registry_status", "capture_health", "alerts"}
    assert json.loads((tmp_path / "registry_status.json").read_text())
