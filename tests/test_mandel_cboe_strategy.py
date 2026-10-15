"""Cboe strategy benchmark indices: CSV parsing, point-in-time dating (evening ET, launch date for back-tested rows),
defect flags, VRO carried rows, the fetch loop (307 redirect, 403, 429 retry, storage) on a mocked transport, and the
index -> theory map against the registry. Fixtures are rows recorded from the live files on 2026-10-15; no network."""

import json
from pathlib import Path

import httpx
import pytest

import mandel
from mandel.archive import Archive
from mandel.data import cboe_strategy as cs
from mandel.data.store import ObservationStore
from mandel.ledger import Ledger

# recorded from https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv on 2026-10-15
BXM_CSV = "DATE,BXM\n03/22/2002,584.300000\n03/25/2002,578.480000\n10/13/2026,2578.630000\n10/14/2026,2576.300000\n"
BXY_CSV = ("DATE,BXY\n03/07/2013,1255.470000\n03/08/2013,1260.260000\n03/11/2013,937.940000\n03/12/2013,1262.110000\n"
           "03/13/2013,1264.520000\n")
BXMD_CRASH = "DATE,BXMD\n10/16/1987,100.0\n10/19/1987,79.9\n10/20/1987,82.0\n10/21/1987,86.0\n"   # crash shape: no reversion
SPAI_CSV = "DATE,OPEN,HIGH,LOW,CLOSE\n11/04/2021,574.1,575.2,572.9,574.5\n11/05/2021,,,,573.930000\n"
CLL_CSV = "DATE,CLL\n10/14/2009,591.130000\n10/15/2009,592.600000\n10/16/2009,475.170000\n10/19/2009,478.530000\n"
VRO_CSV = ("DATE,VRO\n01/02/2018,10.310000\n01/03/2018,9.730000\n01/04/2018,9.730000\n01/08/2018,9.730000\n"
           "01/09/2018,9.730000\n01/10/2018,10.290000\n01/06/2016,21.890000\n01/13/2016,21.890000\n")
S3_403 = '<?xml version="1.0" encoding="UTF-8"?><Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>'


# ------------------------------------------------------------------ parsing --

def test_parse_single_column_and_ohlc():
    rows = cs.parse_history("﻿" + BXM_CSV + "bad,row\n13/45/2020,1\n10/14/2026,2576.31\n", "BXM")
    assert [r["day"] for r in rows] == ["2002-03-22", "2002-03-25", "2026-10-13", "2026-10-14"]
    assert rows[-1] == {"day": "2026-10-14", "close": 2576.31}                       # duplicate day: the last wins
    o = cs.parse_history(SPAI_CSV, "SPAI")
    assert o[0] == {"day": "2021-11-04", "open": 574.1, "high": 575.2, "low": 572.9, "close": 574.5}
    assert o[1] == {"day": "2021-11-05", "close": 573.93}                             # blank O/H/L left out, row kept


# -------------------------------------------------------------- point in time --

def test_available_at_evening_et_launch_and_cap():
    assert cs.available_at("2026-10-14") == "2026-10-14T23:00:00+00:00"              # EDT: 19:00 ET = 23:00 UTC
    assert cs.available_at("2026-01-15") == "2026-01-16T00:00:00+00:00"              # EST: 19:00 ET = 00:00 UTC next day
    assert cs.available_at("1990-03-01", launch="2015-08-03") == "2015-08-03T23:00:00+00:00"
    assert cs.available_at("2026-10-14", observed_at="2026-10-14T21:00:00+00:00") == "2026-10-14T21:00:00+00:00"


def test_archive_rows_backtest_dating_and_never_after_observed():
    obs = "2026-10-15T11:30:00+00:00"
    rows = cs.to_archive_rows("BXM", cs.parse_history(BXM_CSV, "BXM"), obs)
    first, last = rows[0], rows[-1]
    assert first["value"]["backtest"] is True and first["available_at"] == "2002-04-30T23:00:00+00:00"   # before BXM launch
    assert last["value"]["backtest"] is False and last["available_at"] == "2026-10-14T23:00:00+00:00"
    assert all(r["available_at"] <= r["observed_at"] == obs for r in rows)
    assert {r["key"] for r in rows} == {"BXM"} and rows[0]["source"] == "cboe"
    cll = cs.to_archive_rows("CLL", cs.parse_history(CLL_CSV, "CLL"), obs)       # launch not stated: no back-test claim
    assert {r["value"]["backtest"] for r in cll} == {None}


# ------------------------------------------------------------------- defects --

def test_flags_spike_known_splice_and_crash_not_flagged():
    bxy = cs.annotate("BXY", cs.parse_history(BXY_CSV, "BXY"))
    assert [r["day"] for r in bxy if r.get("flag")] == ["2013-03-11"]
    cll = cs.annotate("CLL", cs.parse_history(CLL_CSV, "CLL"))
    assert [r["day"] for r in cll if r.get("flag")] == ["2009-10-16"]
    assert cs.spikes(cs.parse_history(BXMD_CRASH, "BXMD")) == set()
    assert cs.coverage(bxy)["flagged"] == {"2013-03-11": cs.KNOWN_ISSUES["BXY"]["2013-03-11"]}


def test_vro_carried_rows_and_no_backtest():
    v = cs.annotate("VRO", cs.parse_history(VRO_CSV, "VRO"))
    by = {r["day"]: r for r in v}
    assert [d for d, r in by.items() if r["carried"]] == ["2018-01-04", "2018-01-08", "2018-01-09"]
    assert by["2016-01-13"]["carried"] is False                                       # equal value a week later is a new print
    assert all(r["backtest"] is False and "flag" not in r for r in v)


# -------------------------------------------------------------------- fetching --

def _mock(calls: list, fail_first: dict | None = None):
    fail_first = dict(fail_first or {})
    bodies = {"BXM": BXM_CSV, "VRO": VRO_CSV, "SPAI": SPAI_CSV}

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        sym = req.url.path.rsplit("/", 1)[-1].replace("_History.csv", "")
        if req.url.host == "cdn.cboe.com":
            return httpx.Response(307, headers={"location": str(req.url).replace("cdn.cboe.com", "cdn-api.cboe.com")})
        if fail_first.get(sym):
            fail_first[sym] -= 1
            return httpx.Response(429, text="slow down")
        if sym in bodies:
            return httpx.Response(200, text=bodies[sym], headers={"content-type": "text/csv", "last-modified": "Wed, 14 Oct 2026 22:31:04 GMT"})
        return httpx.Response(403, text=S3_403)
    return httpx.Client(transport=httpx.MockTransport(handler))


def _archive(tmp_path: Path) -> Archive:
    return Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))


def test_fetch_follows_redirect_retries_429_and_stores(tmp_path):
    calls, rep = [], {}
    a = _archive(tmp_path)
    out = cs.fetch_cboe_strategy(a, symbols=["BXM", "PUTW", "VRO"], client=_mock(calls, {"BXM": 1}), min_interval=0, backoff=0, report=rep)
    assert set(out) == {"cboe-BXM-history", "cboe-PUTW-history", "cboe-VRO-history"}
    assert len(out["cboe-BXM-history"]) == 4 and out["cboe-PUTW-history"] == []
    assert rep["BXM"]["attempts"] == 2 and rep["BXM"]["final_url"].startswith("https://cdn-api.cboe.com/")
    assert rep["PUTW"]["status"] == 403 and rep["PUTW"]["attempts"] == 1               # no file: no retry
    assert rep["BXM"]["coverage"]["first"] == "2002-03-22" and rep["BXM"]["last_modified"].endswith("GMT")
    names = {e.name: e for e in a.entries()}
    assert set(names) == {"cboe-BXM-history", "cboe-VRO-history"}                    # empty fetch is not stored
    e = names["cboe-BXM-history"]
    assert e.in_git and e.kind == "data" and e.rows == 4 and "strategy-index" in e.tags and "buywrite" in e.tags
    assert "BXM_History.csv" in e.recipe and "Cboe_BuyWrite_Indices_Methodology.pdf" in e.recipe
    assert "available_at = 19:00 America/New_York" in e.recipe and "2002-04-30" in e.recipe and "backtest" in e.schema
    back = list(a.load("cboe-BXM-history"))
    assert back[-1]["value"] == {"day": "2026-10-14", "close": 2576.3, "backtest": False}
    assert all(r["available_at"] <= r["observed_at"] for r in back)


def test_failed_refetch_keeps_stored_bundle_and_observation_store_passthrough(tmp_path):
    a = _archive(tmp_path)
    cs.fetch_cboe_strategy(ObservationStore(a), symbols=["BXM"], client=_mock([]), min_interval=0, backoff=0)
    assert [e.name for e in a.entries()] == ["cboe-BXM-history"]

    def down(req):
        return httpx.Response(503, text="unavailable")
    out = cs.fetch_cboe_strategy(a, symbols=["BXM"], client=httpx.Client(transport=httpx.MockTransport(down)), min_interval=0, backoff=0, retries=2)
    assert out["cboe-BXM-history"] == [] and len(list(a.load("cboe-BXM-history"))) == 4


def test_dry_run_and_limit(tmp_path):
    calls, rep = [], {}
    out = cs.fetch_cboe_strategy(None, dry_run=True, client=_mock(calls), report=rep)
    assert calls == [] and len(out) == len(cs.STRATEGY_INDICES) and all(v == [] for v in out.values())
    assert rep["_plan"]["calls"] == len(cs.STRATEGY_INDICES)
    out = cs.fetch_cboe_strategy(None, symbols=["BXM", "VRO", "SPAI"], limit=2, client=_mock(calls), min_interval=0, backoff=0)
    assert list(out) == ["cboe-BXM-history", "cboe-VRO-history"] and len(calls) == 4      # 2 indices x (307 + 200)


# ------------------------------------------------------------- index -> theory --

def test_index_list_and_theory_map_match_registry():
    required = ["BXM", "BXMD", "BXY", "BXMC", "PUT", "PUTY", "PUTR", "WPUT", "CLL", "CLLZ", "CMBO", "CNDR", "BFLY",
                "PPUT", "VXTH", "RXM", "BXN", "BXR", "VRO"]
    assert set(required) <= set(cs.STRATEGY_INDICES) and "PUTW" not in cs.STRATEGY_INDICES   # PUTW answers 403
    reg = json.loads((Path(mandel.__file__).parent / "theories" / "registry.json").read_text())["theories"]
    ids = {t["id"] for t in (reg.values() if isinstance(reg, dict) else reg)}
    mapped = {t for m in cs.INDEX_META.values() for t in m["theories"]}
    assert mapped <= ids and set(cs.THEORY_NOTES) == mapped
    assert {"PUT", "BXM"} <= set(cs.indices_for("T-202")) and cs.indices_for("T-220") == ["VRO"]
    assert "BXMD" in cs.indices_for("T-54") and "CNDR" in cs.indices_for("T-109") and "BFLY" in cs.indices_for("T-106")
    for s, m in cs.INDEX_META.items():
        assert m["history"] == cs.history_url(s) and m["dashboard"].startswith("https://www.cboe.com/us/indices/dashboard/")
        assert m["methodology"] is None or m["methodology"].startswith("https://cdn-api.cboe.com/api/global/us_indices/governance/")
        assert m["launch"] is None or len(m["launch"]) == 10
