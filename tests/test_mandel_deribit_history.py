"""deribit_history: the declared batch-6b Deribit bundles for T-263 (FOMC windows), T-268 (BTC DVOL futures) and
T-257 / T-262 (daily 07:00-09:00 UTC option-trade samples). Window bounds, target expiries, paging, settlement
fallback, point-in-time dating, streamed chunked storing, interrupt and resume, and the batch6b_drb readers run on
the rows. Mocked transports and a temporary archive only; no network.

Fixtures are synthetic in Deribit's exact formats (Deribit states no data licence, so no recorded tape is copied here)."""

import gzip
import json
import math
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from mandel.archive import Archive
from mandel.data import deribit_history as dh
from mandel.data import options_misc as om
from mandel.experiments import batch6b_drb as h
from mandel.ledger import Ledger

NOW = om._ms("2026-10-15T12:00:00+00:00")
H = 3_600_000


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(om, "_sleep", lambda s: None)
    h._CACHE.clear()


def _archive(tmp_path: Path) -> Archive:
    return Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))


def _q(req: httpx.Request) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}


def _code(day: str) -> str:
    return om.expiry_code(om._ms(day + "T08:00:00+00:00"))


def _opt(day: str, strike: float, cp: str, cur: str = "BTC") -> str:
    return f"{cur}-{_code(day)}-{int(strike)}-{cp}"


def _trade(tid, ts, name, price=0.05, iv=60.0, index=60100.0, mark=None, direction="buy", amount=1.0):
    return {"trade_seq": tid, "trade_id": str(tid), "timestamp": ts, "tick_direction": 0, "price": price,
            "mark_price": price if mark is None else mark, "iv": iv, "instrument_name": name, "index_price": index,
            "direction": direction, "amount": amount, "contracts": amount * 10}


def _inst(cur, exp_day, created, strikes=(60000.0,), kind="option", name=None, period="day"):
    e = om._ms(exp_day + "T08:00:00+00:00")
    if kind == "future":
        return [{"instrument_name": name, "kind": "future", "expiration_timestamp": e, "creation_timestamp": om._ms(created),
                 "settlement_period": period, "price_index": "btcdvol_usdc"}]
    return [{"instrument_name": f"{cur}-{om.expiry_code(e)}-{int(k)}-{cp}", "strike": k, "option_type": "call" if cp == "C" else "put",
             "expiration_timestamp": e, "creation_timestamp": om._ms(created), "settlement_period": period}
            for k in strikes for cp in ("C", "P")]


def _deribit(calls: list, tape=(), page: int = 5, instruments=None, usdc=None, deliveries=None, settlements=None, fail=None):
    """Mock of history.deribit.com (trades, instruments) and www.deribit.com (delivery prices, settlements)."""
    tape = sorted(tape, key=lambda x: (x["timestamp"], int(x["trade_id"].split("-")[-1])))

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        q, path, host = _q(req), req.url.path, req.url.host
        if fail is not None:
            r = fail(req, q)
            if r is not None:
                return r
        if path.endswith("get_instruments"):
            assert host == "history.deribit.com" and q["expired"] in ("true", "false")
            if q["currency"] == "USDC":
                assert q["kind"] == "future" and q["expired"] == "true"
                return httpx.Response(200, json={"result": usdc or []})
            assert q["kind"] == "option"
            return httpx.Response(200, json={"result": (instruments or []) if q["expired"] == "true" else []})
        if path.endswith("get_last_trades_by_currency_and_time") or path.endswith("get_last_trades_by_instrument_and_time"):
            assert host == "history.deribit.com"
            assert q["sorting"] == "asc" and q["include_old"] == "true" and q["count"] == "1000"
            s, e = int(q["start_timestamp"]), int(q["end_timestamp"])
            if path.endswith("currency_and_time"):
                assert q["kind"] == "option"
                sel = [x for x in tape if s <= x["timestamp"] <= e and x["instrument_name"].startswith(q["currency"] + "-")]
            else:
                sel = [x for x in tape if s <= x["timestamp"] <= e and x["instrument_name"] == q["instrument_name"]]
            return httpx.Response(200, json={"jsonrpc": "2.0", "result": {"trades": sel[:page], "has_more": len(sel) > page}})
        if path.endswith("get_delivery_prices"):
            assert host == "www.deribit.com" and q["index_name"] == "btcdvol_usdc"
            off, cnt = int(q["offset"]), int(q["count"])
            data = list(deliveries or [])
            return httpx.Response(200, json={"result": {"data": data[off:off + cnt], "records_total": len(data)}})
        if path.endswith("get_last_settlements_by_currency"):
            assert host == "www.deribit.com" and q["type"] == "delivery"
            return httpx.Response(200, json={"result": {"settlements": settlements or [], "continuation": "none"}})
        if path.endswith("get_last_settlements_by_instrument"):
            return httpx.Response(400, json={"error": {"code": -32602, "data": {"reason": "instrument is not active"}}})
        raise AssertionError(f"unexpected request {req.url}")
    return httpx.Client(transport=httpx.MockTransport(handler))


# ========================================================================================= declared names ==

def test_bundle_names_and_windows_match_the_harness():
    assert dh.FOMC_BUNDLE == h.FOMC_TRADES_B and dh.DVOLF_BUNDLE == h.DVOLF_B and dh.daily_bundle("BTC") == h.DAILY_TRADES_B
    assert set(h.REQUESTS) >= {dh.FOMC_BUNDLE, dh.DVOLF_BUNDLE, dh.daily_bundle()}
    assert h.daily_smiles.__defaults__[0] == dh.DAILY_HOURS == (7, 9)            # the window the smiles sample
    assert dh.DAILY_DTE_DAYS == (1, int(h.daily_smiles.__defaults__[1]))          # daily_smiles: 1/365 <= T <= 400/365
    req = h.REQUESTS[dh.daily_bundle()]
    assert "07:00 UTC" in req and "09:00 UTC ms - 1" in req and dh.DAILY_FIRST in req and dh.DAILY_LAST in req
    assert "decision_ms - 86400000" in h.REQUESTS[dh.FOMC_BUNDLE] and "14:00 America/New_York" in h.REQUESTS[dh.FOMC_BUNDLE]
    assert "expiry_ms - 8*86400000" in h.REQUESTS[dh.DVOLF_BUNDLE] and dh.DVOLF_LEAD_DAYS == 8


# ============================================================================================== FOMC ==

DEC = "2024-09-18"                       # 14:00 EDT = 18:00 UTC
DEC2 = "2024-11-07"                      # 14:00 EST = 19:00 UTC (after the clocks changed)
MEETINGS = [
    {"start": "2024-09-17", "decision_day": DEC, "scheduled": True, "label": "September 17-18*", "available_at": "2024-09-17T00:00:00+00:00"},
    {"start": "2024-11-06", "decision_day": DEC2, "scheduled": True, "label": "November 6-7", "available_at": "2024-11-06T00:00:00+00:00"},
    {"start": "2024-08-05", "decision_day": "2024-08-05", "scheduled": False, "label": "unscheduled", "available_at": "2024-08-05T00:00:00+00:00"},
    {"start": "2021-12-14", "decision_day": "2021-12-15", "scheduled": True, "label": "before 2022", "available_at": "2021-12-14T00:00:00+00:00"},
    {"start": "2026-12-08", "decision_day": "2026-12-09", "scheduled": True, "label": "future", "available_at": "2026-12-08T00:00:00+00:00"},
]
FOMC_INSTRUMENTS = (_inst("BTC", "2024-09-18", "2024-09-15", strikes=(60000.0,)) +                    # expires before the decision
                    _inst("BTC", "2024-09-19", "2024-09-16T08:00:10+00:00", strikes=(59000.0, 60000.0, 61000.0)) +   # the target
                    _inst("BTC", "2024-09-27", "2024-08-01", strikes=(60000.0,), period="week") +
                    _inst("BTC", "2024-11-07", "2024-11-04", strikes=(70000.0,)) +                     # 08:00 on the decision day: before it
                    _inst("BTC", "2024-11-08", "2024-11-07T20:00:00+00:00", strikes=(70000.0,)) +      # listed after the decision: not eligible
                    _inst("BTC", "2024-11-09", "2024-11-06T08:00:00+00:00", strikes=(70000.0,)))       # the target of DEC2


def _fomc_tape():
    d1, d2 = dh.fomc_decision_ms(DEC), dh.fomc_decision_ms(DEC2)
    out, tid = [], 1
    for d, tgt, other, idx, ks in ((d1, "2024-09-19", "2024-09-27", 60100.0, (59000.0, 60000.0, 61000.0)),
                                   (d2, "2024-11-09", "2024-11-07", 70100.0, (70000.0,))):
        out.append(_trade(tid, d - 24 * H - 1, _opt(tgt, ks[0], "C"), index=idx)); tid += 1         # just before the window
        t = d - 24 * H
        while t < d:
            for k in ks:
                for cp in ("C", "P"):
                    out.append(_trade(tid, t, _opt(tgt, k, cp), price=0.01, mark=0.011, index=idx)); tid += 1
            out.append(_trade(tid, t + 1000, _opt(other, ks[0], "P"), index=idx)); tid += 1
            t += 3 * H
        out += [_trade(tid + i, d - 5000, _opt(tgt, ks[0], "P"), index=idx) for i in range(6)]      # burst across a page boundary
        tid += 10
        out.append(_trade(tid, d, _opt(tgt, ks[0], "C"), index=idx)); tid += 1                      # at the decision: excluded
    return out


def test_fomc_decision_time_and_windows():
    assert om._iso_ms(dh.fomc_decision_ms("2022-01-26")) == "2022-01-26T19:00:00.000+00:00"        # EST
    assert om._iso_ms(dh.fomc_decision_ms(DEC)) == "2024-09-18T18:00:00.000+00:00"                 # EDT
    listings = om.expiry_listings(FOMC_INSTRUMENTS)
    ws = dh.fomc_windows(MEETINGS, listings, now_ms=NOW)
    assert [w["decision_day"] for w in ws] == [DEC, DEC2]          # unscheduled, pre-2022 and future decisions are left out
    w1, w2 = ws
    assert w1["end_ms"] == dh.fomc_decision_ms(DEC) and w1["start_ms"] == w1["end_ms"] - 86_400_000
    assert w1["target"]["expiry_code"] == "19SEP24" and w1["target"]["listed_at"] == "2024-09-16T08:00:10.000+00:00"
    assert w2["target"]["expiry_code"] == "9NOV24"                 # 8NOV24 was listed only after the decision
    assert dh.fomc_windows(MEETINGS, None, now_ms=NOW)[0]["target"] is None
    assert dh.fomc_windows(MEETINGS, listings, now_ms=dh.fomc_decision_ms(DEC2) - 1)[-1]["decision_day"] == DEC   # not yet decided


def test_fetch_fomc_rows_store_merge_and_harness(tmp_path):
    a, calls, rep = _archive(tmp_path), [], {}
    tape = _fomc_tape()
    rows = dh.fetch_deribit_fomc_trades(a, meetings=MEETINGS[:1], client=_deribit(calls, tape, page=8, instruments=FOMC_INSTRUMENTS),
                                        min_interval=0, backoff=0, report=rep, now_ms=NOW)
    assert sum("get_instruments" in u for u in calls) == 2                                    # expired + live option lists
    first = _q(httpx.Request("GET", next(u for u in calls if "get_last_trades" in u)))
    d1 = dh.fomc_decision_ms(DEC)
    assert (first["currency"], int(first["start_timestamp"]), int(first["end_timestamp"])) == ("BTC", d1 - 86_400_000, d1 - 1)
    trades = [r for r in rows if r["kind"] == "option-trade"]
    (win,) = [r for r in rows if r["kind"] == "fomc-window"]
    inside = [x for x in tape if d1 - 86_400_000 <= x["timestamp"] < d1]
    assert {r["value"]["expiry_code"] for r in trades} == {"19SEP24"}
    assert len(trades) == sum(1 for x in inside if "19SEP24" in x["instrument_name"]) and len({r["key"] for r in trades}) == len(trades)
    assert all(r["available_at"] == om._iso_ms(r["value"]["timestamp"]) <= r["observed_at"] for r in trades)
    v = trades[0]["value"]
    assert {"decision_day", "currency", "expiry", "expiry_code", "strike", "type", "trade_id", "timestamp", "instrument_name", "price",
            "mark_price", "iv", "index_price", "amount", "direction", "trade_seq", "tick_direction"} <= set(v)       # the raw trade + parsed
    w = win["value"]
    assert {"decision_day", "decision_time", "currency", "target_expiry", "target_expiry_code", "target_listed_at", "window_start",
            "window_end", "complete"} <= set(w)
    assert (w["decision_time"], w["target_expiry"], w["window_start"], w["window_end"]) == (
        "2024-09-18T18:00:00.000+00:00", "2024-09-19", "2024-09-17T18:00:00.000+00:00", "2024-09-18T18:00:00.000+00:00")
    assert w["complete"] and w["trades_seen"] == len(inside) and w["trades_kept"] == len(trades)
    assert win["available_at"] == "2024-09-17T00:00:00+00:00"           # the meeting was known before the target's listing
    e = a.get(dh.FOMC_BUNDLE)
    assert e.in_git is False and e.rows == len(rows) and "sorting=asc" in e.recipe and "T-263" in e.tags and f"{DEC}:BTC" in e.recipe
    # the harness reads it: the straddle at the strike nearest the index (60100) with both legs printed
    settle = {"2024-09-19": 61000.0}
    wins, tr = h.fomc_inputs(list(a.load(dh.FOMC_BUNDLE)))
    m = h.fomc_move(wins[f"{DEC}:BTC"], tr[f"{DEC}:BTC"], settle)
    assert m["strike"] == 60000.0 and m["expiry"] == "2024-09-19" and m["implied"] == pytest.approx(2 * 0.011 * 60100 / 60100)
    # a second decision merges in; its window row is dated at the target's listing (after the meeting start)
    dh.fetch_deribit_fomc_trades(a, meetings=MEETINGS, instruments=FOMC_INSTRUMENTS, client=_deribit([], tape), min_interval=0, backoff=0,
                                 now_ms=NOW, first="2024-11-01")
    stored = list(a.load(dh.FOMC_BUNDLE))
    wins = {r["key"]: r for r in stored if r["kind"] == "fomc-window"}
    assert set(wins) == {f"{DEC}:BTC", f"{DEC2}:BTC"} and wins[f"{DEC2}:BTC"]["available_at"] == "2024-11-06T08:00:00.000+00:00"
    assert wins[f"{DEC2}:BTC"]["value"]["decision_time"] == "2024-11-07T19:00:00.000+00:00"
    assert stored == sorted(stored, key=dh._fomc_sort) and len([r for r in stored if r["value"]["decision_day"] == DEC]) == len(rows)
    # a preview (max_pages) is never stored and never replaces the stored window
    n = len(stored)
    dh.fetch_deribit_fomc_trades(a, meetings=MEETINGS[:1], instruments=FOMC_INSTRUMENTS, client=_deribit([], tape), max_pages=1,
                                 min_interval=0, backoff=0, now_ms=NOW)
    assert len(list(a.load(dh.FOMC_BUNDLE))) == n
    # end to end through the harness entry point (delivery prices archived alongside)
    a.store(h.DELIV_B, kind="data", rows=[{"value": {"date": "2024-09-19", "delivery_price": 61000.0}, "available_at": "2024-09-19T08:00:00+00:00"},
                                         {"value": {"date": "2024-11-09", "delivery_price": 70500.0}, "available_at": "2024-11-09T08:00:00+00:00"}],
            recipe="test")
    stat, n_dec, verdict, reason = h.b6b_drb_fomc_event_straddle(a)
    assert "missing_bundles" not in stat and n_dec == 2 and len(stat["moves"]) == 2


def test_fomc_interrupt_resume_and_dry_run(tmp_path):
    a, tape = _archive(tmp_path), _fomc_tape()
    inner = _deribit([], tape)
    d2 = dh.fomc_decision_ms(DEC2)

    def fail(req, q):
        if "get_last_trades" in req.url.path and int(q["start_timestamp"]) >= d2 - 86_400_000:
            raise RuntimeError("interrupted")                                  # the second window dies mid-run
        return None
    with pytest.raises(RuntimeError):
        dh.fetch_deribit_fomc_trades(a, meetings=MEETINGS, instruments=FOMC_INSTRUMENTS, client=_deribit([], tape, fail=fail),
                                     min_interval=0, backoff=0, retries=1, now_ms=NOW)
    assert {r["key"] for r in a.load(dh.FOMC_BUNDLE) if r["kind"] == "fomc-window"} == {f"{DEC}:BTC"}
    calls, rep = [], {}
    dh.fetch_deribit_fomc_trades(a, meetings=MEETINGS, instruments=FOMC_INSTRUMENTS, client=_deribit(calls, tape), min_interval=0,
                                 backoff=0, report=rep, skip_stored=True, now_ms=NOW)
    assert rep["_already_stored"] == [f"{DEC}:BTC"] and f"{DEC}:BTC" not in rep and rep[f"{DEC2}:BTC"]["complete"]
    calls2 = []                                                                  # all stored: no request at all
    assert dh.fetch_deribit_fomc_trades(a, meetings=MEETINGS, client=_deribit(calls2, tape), skip_stored=True, now_ms=NOW) == [] and calls2 == []
    assert all(int(_q(httpx.Request("GET", u))["start_timestamp"]) >= d2 - 86_400_000 for u in calls)
    assert {r["key"] for r in a.load(dh.FOMC_BUNDLE) if r["kind"] == "fomc-window"} == {f"{DEC}:BTC", f"{DEC2}:BTC"}
    # dry run: no request; 8 scheduled decisions a year 2022-2026
    mts, calls, rep = [], [], {}
    for y in range(2022, 2027):
        for k in range(8):
            d = date(y, 1 + k, 15).isoformat()
            mts.append({"start": d, "decision_day": d, "scheduled": True})
    dh.fetch_deribit_fomc_trades(None, meetings=mts, dry_run=True, client=_deribit(calls), report=rep, now_ms=NOW)
    plan = rep["_plan"]
    assert calls == [] and plan["windows"] == 40 and plan["instrument_calls"] == 2
    assert plan["est_calls"] == sum(max(1, math.ceil(dh.FOMC_WINDOW_TRADES[int(w["decision_day"][:4])] / 1000)) for w in plan["per_window"])
    assert plan["est_rows"] == int(plan["est_trades_seen"] * dh.FOMC_KEEP_SHARE) + 40


def test_load_fomc_meetings_from_archive(tmp_path):
    a = _archive(tmp_path)
    assert dh.load_fomc_meetings(a) == []
    a.store("fomc-meetings", kind="data", recipe="test",
            rows=[{"key": m["decision_day"], "available_at": m["available_at"], "value": {k: v for k, v in m.items() if k != "available_at"}}
                  for m in MEETINGS])
    got = dh.load_fomc_meetings(a)
    assert [m["decision_day"] for m in got] == [m["decision_day"] for m in MEETINGS] and got[0]["available_at"] == MEETINGS[0]["available_at"]


# ========================================================================================== DVOL futures ==

E1, E2, E3 = "2023-04-26", "2023-05-31", "2023-06-28"
USDC = (_inst("USDC", E1, "2023-03-23T10:07:30+00:00", kind="future", name="BTCDVOL_USDC-26APR23", period="month") +
        _inst("USDC", E2, "2023-04-19T08:01:11+00:00", kind="future", name="BTCDVOL_USDC-31MAY23", period="month") +
        _inst("USDC", E3, "2023-05-24T08:00:53+00:00", kind="future", name="BTCDVOL_USDC-28JUN23", period="month") +
        _inst("USDC", E1, "2023-03-23", kind="future", name="ETHDVOL_USDC-26APR23") +            # not BTC DVOL
        _inst("USDC", "2026-11-25", "2026-10-01", kind="future", name="BTCDVOL_USDC-25NOV26"))   # not expired yet


def _dvol_tape():
    out, tid = [], 1
    for name, day, gap in (("BTCDVOL_USDC-26APR23", E1, False), ("BTCDVOL_USDC-31MAY23", E2, True), ("BTCDVOL_USDC-28JUN23", E3, False)):
        e = om._ms(day + "T08:00:00+00:00")
        t = e - 10 * 86_400_000 + H                                                 # the grid never lands on T-7d itself
        while t <= e:
            if not (gap and e - 8 * 86_400_000 <= t <= e - 6 * 86_400_000):           # 31MAY23: no trade near T-7d
                out.append(_trade(f"USDC-{tid}", t, name, price=55.0, mark=55.2, index=54.0)); tid += 1
            t += 6 * H
        out += [_trade(f"USDC-{tid + i}", e - 7 * 86_400_000 + 5, name, price=56.0, mark=56.1, index=54.5) for i in range(7) if not gap]
        tid += 10
        out.append(_trade(f"USDC-{tid}", e, name, price=50.0, mark=50.5, index=50.0)); tid += 1          # at expiry: included
        out.append(_trade(f"USDC-{tid}", e + 1, name)); tid += 1                                          # after expiry: excluded
    return out


DELIVERIES = ([{"date": (date(2023, 7, 1) - timedelta(days=i)).isoformat(), "delivery_price": 50.0 + i / 10} for i in range(250)
               if (date(2023, 7, 1) - timedelta(days=i)).isoformat() not in (E2, E3)]
              + [{"date": E3, "delivery_price": 47.25}])
SETTLEMENTS = [{"type": "delivery", "timestamp": om._ms(E2 + "T08:00:00+00:00") + 1166, "instrument_name": "BTCDVOL_USDC-31MAY23",
                "mark_price": 48.5, "index_price": 48.5, "position": 1, "profit_loss": 0.0, "session_profit_loss": 0.0}]


def test_instrument_paging_and_delivery_prices():
    tape, calls = _dvol_tape(), []
    e = om._ms(E1 + "T08:00:00+00:00")
    got, info = dh.instrument_trades("BTCDVOL_USDC-26APR23", e - 8 * 86_400_000, e + 1, _deribit(calls, tape, page=8), om.Throttle(0), backoff=0)
    want = [x for x in tape if x["instrument_name"] == "BTCDVOL_USDC-26APR23" and e - 8 * 86_400_000 <= x["timestamp"] <= e]
    assert info["complete"] and sorted(t["trade_id"] for t in got) == sorted(x["trade_id"] for x in want)
    assert max(t["timestamp"] for t in got) == e and info["pages"] == len(calls) > len(want) // 8
    got, info = dh.instrument_trades("BTCDVOL_USDC-26APR23", e - 8 * 86_400_000, e + 1, _deribit([], tape, page=8), om.Throttle(0), max_pages=2, backoff=0)
    assert not info["complete"] and info["stopped"] == "max_pages"
    calls = []
    prices, info = dh.delivery_prices("btcdvol_usdc", _deribit(calls, deliveries=DELIVERIES), om.Throttle(0), backoff=0)
    assert info["complete"] and info["pages"] == 3 == len(calls) and len(prices) == len(DELIVERIES) and prices[E3] == 47.25
    assert all("offset=" in u for u in calls) and E2 not in prices
    px = dh.currency_settlement("BTCDVOL_USDC-31MAY23", om._ms(E2 + "T08:00:00+00:00"), _deribit([], settlements=SETTLEMENTS), om.Throttle(0), backoff=0)
    assert px == 48.5
    assert dh.currency_settlement("BTCDVOL_USDC-28JUN23", om._ms(E3 + "T08:00:00+00:00"), _deribit([], settlements=SETTLEMENTS), om.Throttle(0), backoff=0) is None


def test_fetch_dvol_futures_rows_store_resume_and_harness(tmp_path):
    a, calls, rep = _archive(tmp_path), [], {}
    tape = _dvol_tape()
    rows = dh.fetch_deribit_dvol_futures(a, client=_deribit(calls, tape, page=8, usdc=USDC, deliveries=DELIVERIES, settlements=SETTLEMENTS),
                                         min_interval=0, backoff=0, report=rep, now_ms=NOW)
    assert sum("get_instruments" in u for u in calls) == 1 and not any("settlements_by_instrument" in u for u in calls)
    assert rep["_instruments"] == 3 and rep["_delivery_prices"]["complete"]
    trades = [r for r in rows if r["kind"] == "future-trade"]
    sets = {r["key"]: r for r in rows if r["kind"] == "future-settlement"}
    wins = {r["key"]: r for r in rows if r["kind"] == "future-window"}
    assert {r["value"]["instrument_name"] for r in trades} == set(sets) == set(wins) == {"BTCDVOL_USDC-26APR23", "BTCDVOL_USDC-31MAY23", "BTCDVOL_USDC-28JUN23"}
    assert all(set(r["value"]) == {"instrument_name", "expiry", "timestamp", "price", "mark_price", "index_price", "amount", "direction"} for r in trades)
    assert all(r["available_at"] == om._iso_ms(r["value"]["timestamp"]) for r in trades)
    for name, day in (("BTCDVOL_USDC-26APR23", E1), ("BTCDVOL_USDC-28JUN23", E3)):
        e = om._ms(day + "T08:00:00+00:00")
        mine = [r["value"]["timestamp"] for r in trades if r["value"]["instrument_name"] == name]
        assert min(mine) >= e - 8 * 86_400_000 and max(mine) == e
        assert len(mine) == sum(1 for x in tape if x["instrument_name"] == name and e - 8 * 86_400_000 <= x["timestamp"] <= e)
    s1 = sets["BTCDVOL_USDC-26APR23"]
    assert s1["value"] == {"instrument_name": "BTCDVOL_USDC-26APR23", "expiry": "2023-04-26T08:00:00.000+00:00", "delivery_price": 50.0 + 66 / 10}
    assert s1["available_at"] == "2023-04-26T08:00:00.000+00:00" and s1["source"] == "deribit-delivery-prices"
    assert sets["BTCDVOL_USDC-31MAY23"]["value"]["delivery_price"] == 48.5 and sets["BTCDVOL_USDC-31MAY23"]["source"] == "deribit-settlements"
    assert wins["BTCDVOL_USDC-26APR23"]["value"]["window_start"] == "2023-04-18T08:00:00.000+00:00" and wins["BTCDVOL_USDC-26APR23"]["value"]["complete"]
    e = a.get(dh.DVOLF_BUNDLE)
    assert e.in_git is False and e.rows == len(rows) and "T-268" in e.tags and "get_delivery_prices" in e.recipe
    stored = list(a.load(dh.DVOLF_BUNDLE))
    assert stored == sorted(stored, key=dh._dvol_sort)
    # the harness reads it: 26APR23 and 28JUN23 have a trade near T-7d, 31MAY23 does not
    tr, st = h.dvolf_inputs(stored)
    pts, drop = h.dvolf_points(tr, st)
    assert [p["instrument"] for p in pts] == ["BTCDVOL_USDC-26APR23", "BTCDVOL_USDC-28JUN23"] and drop == [("BTCDVOL_USDC-31MAY23", "no trade within 24 h of T-7d")]
    assert pts[0]["F_T7"] == 56.1 and pts[0]["settle"] == 56.6 and pts[1]["settle"] == 47.25 and pts[0]["settle_how"] == "delivery price"
    stat, n, verdict, reason = h.b6b_drb_dvol_futures_basis(a)
    assert "missing_bundles" not in stat and n == 2
    # resume: everything is stored complete with a settlement, so only the instrument list and the delivery prices are read
    calls, rep = [], {}
    dh.fetch_deribit_dvol_futures(a, client=_deribit(calls, tape, usdc=USDC, deliveries=DELIVERIES), min_interval=0, backoff=0, report=rep,
                                  skip_stored=True, now_ms=NOW)
    assert rep["_instruments"] == 0 and len(rep["_already_stored"]) == 3 and [urlparse(u).path.rsplit("/", 1)[1] for u in calls] == ["get_instruments"]
    assert len(list(a.load(dh.DVOLF_BUNDLE))) == len(stored)
    rep = {}
    dh.fetch_deribit_dvol_futures(a, dry_run=True, report=rep, skip_stored=True)
    assert rep["_plan"]["instruments"] == dh.DVOLF_EXPIRED - 3 and rep["_plan"]["est_calls"] == 1 + dh.DVOLF_EXPIRED - 3 + 10


# ============================================================================================ daily samples ==

DAYS = ["2024-03-01", "2024-03-02", "2024-03-03", "2024-03-04", "2024-03-05"]
STRIKES = (80000.0, 90000.0, 100000.0, 110000.0, 120000.0)


def _daily_tape(days=DAYS):
    """Per day: prints in the 2024-03-29 expiry at five strikes inside [07:00, 09:00), the same-day expiry and a
    2025 expiry more than 400 days out (both dropped), and prints just outside the window."""
    out, tid = [], 1
    for d in days:
        t0 = om._ms(d + "T07:00:00+00:00")
        for i, k in enumerate(STRIKES):
            for j, cp in enumerate(("C", "P")):
                iv = 60.0 + abs(k - 100000.0) / 2000.0
                out.append(_trade(tid, t0 + (i * 2 + j) * 11 * 60_000, _opt("2024-03-29", k, cp), iv=iv, index=100000.0)); tid += 1
        out.append(_trade(tid, t0, _opt(d, 100000.0, "C"), index=100000.0)); tid += 1                  # same-day expiry, at 07:00
        out.append(_trade(tid, t0 + H, _opt("2025-06-27", 100000.0, "C"), index=100000.0)); tid += 1    # 450+ days out
        out.append(_trade(tid, t0 - 1, _opt("2024-03-29", 100000.0, "C"), index=100000.0)); tid += 1    # 06:59:59.999
        out.append(_trade(tid, t0 + 2 * H, _opt("2024-03-29", 100000.0, "C"), index=100000.0)); tid += 1  # 09:00: excluded
        out.append(_trade(tid, t0 + 2 * H - 1, _opt("2024-03-29", 100000.0, "P"), iv=60.0, index=100000.0)); tid += 1  # 08:59:59.999
    return out


def test_sample_days_window_and_expiry_filter():
    assert dh.daily_window("2024-03-01") == (om._ms("2024-03-01T07:00:00+00:00"), om._ms("2024-03-01T09:00:00+00:00"))
    assert dh.sample_days("2024-02-28", "2024-03-02", now_ms=om._ms("2024-03-02T09:59:59+00:00")) == ["2024-02-28", "2024-02-29", "2024-03-01"]
    assert dh.sample_days("2024-03-02", "2024-03-02", now_ms=om._ms("2024-03-02T10:00:00+00:00")) == ["2024-03-02"]   # an hour after 09:00
    assert dh.fetch_deribit_daily_trades(None, days=["2024-03-02"], dry_run=True, report=(rep := {}), now_ms=om._ms("2024-03-02T09:30:00+00:00")) == []
    assert rep["_plan"]["days"] == 0                                            # explicit days obey the same rule
    assert len(dh.sample_days()) == 1779 and dh.sample_days()[0] == "2021-12-01" and dh.sample_days()[-1] == "2026-10-14"
    keep = dh._dte_keep("2024-03-01", dh.DAILY_DTE_DAYS)
    assert not keep({"instrument_name": _opt("2024-03-01", 1, "C")}) and keep({"instrument_name": _opt("2024-03-02", 1, "C")})
    assert keep({"instrument_name": _opt("2025-04-05", 1, "P")}) and not keep({"instrument_name": _opt("2025-04-06", 1, "P")})   # 400 / 401 days
    assert keep({"instrument_name": "BTC-5APR25-1d5-P"}) and not keep({"instrument_name": "BTC-PERPETUAL"})
    assert dh._dte_keep("2024-03-01", None)({"instrument_name": _opt("2024-03-01", 1, "C")})


def _stored_keys(a):
    return sorted(r["key"] for r in a.load(dh.daily_bundle()))


def test_fetch_daily_chunked_store_and_harness(tmp_path):
    a, calls, rep = _archive(tmp_path), [], {}
    tape = _daily_tape()
    out = dh.fetch_deribit_daily_trades(a, days=DAYS, client=_deribit(calls, tape, page=4), min_interval=0, backoff=0, report=rep,
                                        chunk_days=2, tmp_dir=str(tmp_path))
    assert out == [] and rep["_totals"]["complete"] == 5 and rep["_incomplete"] == {}
    assert len(a.ledger.events("archive.stored")) == 3                         # chunks of 2 + 2 + 1 days, each merged in
    stored = list(a.load(dh.daily_bundle()))
    assert stored == sorted(stored, key=dh._daily_sort)
    samples = [r for r in stored if r["kind"] == "sample-day"]
    trades = [r for r in stored if r["kind"] == "option-trade"]
    assert [r["value"]["day"] for r in samples] == DAYS and all(r["value"]["complete"] for r in samples)
    assert len(trades) == 11 * 5 and {r["value"]["expiry"] for r in trades} == {"2024-03-29"}
    assert samples[0]["value"]["trades_seen"] == 13 and samples[0]["value"]["trades_kept"] == 11
    assert samples[0]["available_at"] == "2024-03-01T09:00:00.000+00:00" and samples[0]["value"]["window_end"] == samples[0]["available_at"]
    v = trades[0]["value"]
    assert list(v) == ["trade_id", "timestamp", "instrument_name", "price", "mark_price", "iv", "index_price", "amount", "direction",
                       "currency", "expiry", "expiry_code", "strike", "type"]
    assert all(om._ms(r["value"]["expiry"]) > 0 and r["available_at"] == om._iso_ms(r["value"]["timestamp"]) for r in trades)
    assert all(7 * H <= r["value"]["timestamp"] % 86_400_000 < 9 * H for r in trades)
    e = a.get(dh.daily_bundle())
    assert e.in_git is False and {"T-257", "T-262"} <= set(e.tags) and "sorting=asc" in e.recipe
    assert "Days stored: 2024-03-01..2024-03-05 (5 days" in e.recipe and "07:00" in e.recipe and not list(tmp_path.glob("deribit-*.jsonl.gz"))
    # the harness rebuilds a smile per day from the stored prints
    sm = h._daily_inputs(a)
    assert sorted(sm) == DAYS and all(list(s["fits"]) == ["2024-03-29"] and s["S"] == 100000.0 for s in sm.values())
    assert sm["2024-03-01"]["fits"]["2024-03-29"]["strikes"] == list(STRIKES)
    # a re-fetch of stored days replaces them without duplicates; skip_stored fetches nothing
    dh.fetch_deribit_daily_trades(a, days=DAYS[1:3], client=_deribit([], tape, page=4), min_interval=0, backoff=0, chunk_days=1)
    assert len(list(a.load(dh.daily_bundle()))) == len(stored) and _stored_keys(a) == sorted(r["key"] for r in stored)
    calls, rep = [], {}
    dh.fetch_deribit_daily_trades(a, days=DAYS, client=_deribit(calls, tape), min_interval=0, backoff=0, report=rep, skip_stored=True)
    assert calls == [] and rep["_already_stored"] == 5 and rep["_totals"]["days"] == 0


def test_daily_interrupt_failures_and_resume(tmp_path):
    a, tape = _archive(tmp_path), _daily_tape()
    clean = _archive(tmp_path / "clean")
    dh.fetch_deribit_daily_trades(clean, days=DAYS, client=_deribit([], tape, page=4), min_interval=0, backoff=0, chunk_days=10)
    d4 = om._ms(DAYS[3] + "T07:00:00+00:00")

    def interrupt(req, q):
        if int(q.get("start_timestamp", 0)) >= d4:
            raise KeyboardInterrupt
        return None
    with pytest.raises(KeyboardInterrupt):
        dh.fetch_deribit_daily_trades(a, days=DAYS, client=_deribit([], tape, page=4, fail=interrupt), min_interval=0, backoff=0,
                                      chunk_days=2, retries=1, tmp_dir=str(tmp_path))
    assert [r["value"]["day"] for r in a.load(dh.daily_bundle()) if r["kind"] == "sample-day"] == DAYS[:3]   # day 3 stored by the finally
    assert not list(tmp_path.glob("deribit-*.jsonl.gz"))                                                    # no spill or snapshot left
    calls, rep = [], {}
    dh.fetch_deribit_daily_trades(a, days=DAYS, client=_deribit(calls, tape, page=4), min_interval=0, backoff=0, report=rep, skip_stored=True)
    assert rep["_already_stored"] == 3 and rep["_totals"]["days"] == 2
    assert all(int(_q(httpx.Request("GET", u))["start_timestamp"]) >= d4 for u in calls)
    assert _stored_keys(a) == _stored_keys(clean)
    # a day whose pages keep failing is reported, not stored; a long Retry-After stops the run, earlier days are stored
    b = _archive(tmp_path / "b")
    d2, d3 = om._ms(DAYS[1] + "T07:00:00+00:00"), om._ms(DAYS[2] + "T07:00:00+00:00")

    def flaky(req, q):
        s = int(q.get("start_timestamp", 0))
        if d2 <= s < d3:
            return httpx.Response(503, text="busy")
        if s >= d4:
            return httpx.Response(429, headers={"retry-after": "7200"}, text="later")
        return None
    rep = {}
    dh.fetch_deribit_daily_trades(b, days=DAYS, client=_deribit([], tape, page=4, fail=flaky), min_interval=0, backoff=0, retries=2,
                                  report=rep, chunk_days=10)
    assert set(rep["_incomplete"]) == {DAYS[1], DAYS[3]} and rep["_incomplete"][DAYS[1]]["error"]["status"] == 503
    assert rep["_aborted"]["day"] == DAYS[3] and rep["_aborted"]["retry_after_s"] == 7200.0 and rep["_totals"]["days"] == 4
    assert [r["value"]["day"] for r in b.load(dh.daily_bundle()) if r["kind"] == "sample-day"] == [DAYS[0], DAYS[2]]


def test_daily_preview_returns_rows_without_storing_and_dry_run(tmp_path):
    tape = _daily_tape()
    rows = dh.fetch_deribit_daily_trades(None, days=DAYS[:2], client=_deribit([], tape, page=4), min_interval=0, backoff=0)
    assert len(rows) == 2 * 12 and rows == sorted(rows, key=dh._daily_sort)
    a, rep = _archive(tmp_path), {}
    rows = dh.fetch_deribit_daily_trades(a, days=DAYS[:2], client=_deribit([], tape, page=4), max_pages=1, min_interval=0, backoff=0,
                                         report=rep, keep_rows=True)
    assert rows and set(rep["_incomplete"]) == set(DAYS[:2]) and "stored" not in rep
    with pytest.raises(KeyError):
        a.get(dh.daily_bundle())
    calls, rep = [], {}
    dh.fetch_deribit_daily_trades(None, dry_run=True, client=_deribit(calls), report=rep, now_ms=NOW)
    p = rep["_plan"]
    assert calls == [] and p["days"] == 1779 and p["merges"] == math.ceil(1779 / dh.DAILY_CHUNK_DAYS)
    assert p["est_calls"] == sum(y["est_calls"] for y in p["by_year"].values()) and 3000 < p["est_calls"] < 6000
    assert 2_000_000 < p["est_rows"] < 4_000_000 and 60 < p["est_gz_mb"] < 150 and 20 < p["est_minutes"] < 120
    rep = {}
    dh.fetch_deribit_daily_trades(None, dry_run=True, report=rep, first="2019-01-01", last="2019-01-31", now_ms=NOW)
    assert rep["_plan"]["est_calls"] == 31                                     # one page a day when the tape is thin


# ===================================================================================== merge safety, CLI ==

def test_merge_failure_keeps_the_previous_bundle(tmp_path):
    a, tape = _archive(tmp_path), _daily_tape()
    dh.fetch_deribit_daily_trades(a, days=DAYS[:2], client=_deribit([], tape, page=4), min_interval=0, backoff=0)
    before = list(a.load(dh.daily_bundle()))
    sha = a.get(dh.daily_bundle()).sha256

    def boom():
        yield from (r for r in before if r["kind"] == "sample-day")
        raise RuntimeError("disk full")
    with pytest.raises(RuntimeError):
        dh._merge_store(a, dh.daily_bundle(), boom(), {om._ms(DAYS[2]) // om.DAY_MS}, dh._daily_idx, dh._daily_sort, recipe="x", tags=[],
                        schema="", tmp_dir=str(tmp_path))
    assert a.get(dh.daily_bundle()).sha256 == sha and a.verify(dh.daily_bundle()) and list(a.load(dh.daily_bundle())) == before
    assert not list(tmp_path.glob("deribit-*.jsonl.gz"))


def test_cli_preview_and_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dh, "_client", lambda timeout=300: _deribit([], _dvol_tape(), usdc=USDC, deliveries=DELIVERIES, settlements=SETTLEMENTS))
    assert dh.main(["dvol", "--preview", str(tmp_path), "--min-interval", "0"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["bundle"] == dh.DVOLF_BUNDLE and out["_instruments"] == 3 and out["rows_returned"] > 0
    rows = [json.loads(line) for line in gzip.open(tmp_path / f"{dh.DVOLF_BUNDLE}.preview.jsonl.gz", "rt")]
    assert len(rows) == out["rows_returned"] and (tmp_path / f"{dh.DVOLF_BUNDLE}.report.json").exists()
    assert dh.main(["daily", "--dry-run", "--preview", str(tmp_path / "dry"), "--first", "2024-03-01", "--last", "2024-03-10"]) == 0
    plan = json.loads(capsys.readouterr().out)["_plan"]
    assert plan["days"] == 10 and plan["est_calls"] == 30 and not (tmp_path / "dry").exists()
