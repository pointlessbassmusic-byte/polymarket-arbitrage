"""Cboe strategy benchmark indices: CSV parsing, point-in-time dating (evening ET; next morning for daily-closing-value
indices; launch date for back-tested rows), defect flags and market-closed-day rows, the VRO expiry / carried
classification, the fetch loop (307 redirect, 403, 429 retry, local-only storage) on a mocked transport, and the
index -> theory map against the registry. Fixtures are rows copied from the live files on 2026-10-15 (the 1987 crash
shape is synthetic); no network."""

import json
from pathlib import Path

import httpx
import pytest

import mandel
from mandel.archive import Archive
from mandel.data import cboe_strategy as cs
from mandel.data.store import ObservationStore
from mandel.ledger import Ledger

# rows from https://cdn.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv on 2026-10-15
BXM_CSV = "DATE,BXM\n03/22/2002,584.300000\n03/25/2002,578.480000\n10/13/2026,2578.630000\n10/14/2026,2576.300000\n"
BXY_CSV = ("DATE,BXY\n03/07/2013,1255.470000\n03/08/2013,1260.260000\n03/11/2013,937.940000\n03/12/2013,1262.110000\n"
           "03/13/2013,1264.520000\n")
BXMD_CRASH = "DATE,BXMD\n10/16/1987,100.0\n10/19/1987,79.9\n10/20/1987,82.0\n10/21/1987,86.0\n"   # crash shape: no reversion
SPAI_CSV = ("DATE,OPEN,HIGH,LOW,CLOSE\n02/03/2006,100.000000,100.000000,100.000000,100.000000\n"
            "12/29/2006,116.260000,116.260000,116.260000,116.260000\n01/02/2007,116.260000,116.260000,116.260000,116.260000\n"
            "01/03/2007,116.710000,116.710000,116.710000,116.710000\n08/14/2017,319.790000,319.790000,319.790000,319.790000\n"
            "08/15/2017,318.960000,318.960000,318.960000,318.960000\n11/04/2021,574.1,575.2,572.9,574.5\n11/05/2021,,,,573.930000\n")
CLL_CSV = ("DATE,CLL\n08/26/2008,597.670000\n08/27/2008,600.680000\n09/29/2008,521.940000\n09/30/2008,536.620000\n"
           "10/14/2009,591.130000\n10/15/2009,592.600000\n10/16/2009,475.170000\n10/19/2009,478.530000\n"
           "11/21/2018,805.180000\n11/22/2018,805.180000\n11/23/2018,804.660000\n")
SVRPO_CSV = "DATE,SVRPO\n12/30/2005,100.000000\n01/04/2010,207.780000\n10/13/2026,963.620000\n10/14/2026,965.080000\n"
VPD_CSV = "DATE,VPD\n11/16/2007,153.880000\n10/14/2026,1067.990000\n"
VRO_CSV = "DATE,VRO\n" + "".join(f"{d},{v}\n" for d, v in [
    ("09/17/2008", 31.54), ("10/17/2008", 31.54), ("10/22/2008", 63.04),                  # stale Friday repeat
    ("09/28/2016", 13.05), ("10/03/2016", 13.05), ("10/05/2016", 12.97),                  # stale Monday repeat (5 days)
    ("11/21/2018", 22.07), ("11/22/2018", 22.07), ("11/23/2018", 22.07), ("11/28/2018", 18.77), ("12/03/2018", 18.77),
    ("12/04/2018", 18.77), ("12/06/2018", 24.60),                                          # 2018-12-05 closure: SOQ on 12-06
    ("01/02/2019", 28.09), ("01/03/2019", 28.09), ("01/04/2019", 28.09), ("01/07/2019", 28.09), ("01/08/2019", 28.09),
    ("01/09/2019", 28.09), ("01/10/2019", 28.09), ("01/11/2019", 20.09), ("01/14/2019", 20.09), ("01/15/2019", 20.09),
    ("01/16/2019", 20.09),
    ("07/03/2019", 13.01), ("07/10/2019", 13.64), ("07/17/2019", 12.69), ("07/23/2019", 12.69), ("07/24/2019", 13.01),
    ("12/18/2019", 11.99), ("12/19/2019", 11.99), ("12/20/2019", 11.99), ("12/23/2019", 11.99), ("12/24/2019", 12.59),
    ("12/25/2019", 12.59), ("12/26/2019", 12.59), ("12/27/2019", 12.59), ("12/30/2019", 12.59), ("12/31/2019", 15.41),
    ("01/02/2020", 15.41), ("01/03/2020", 15.41), ("01/06/2020", 12.59), ("01/07/2020", 12.59), ("01/08/2020", 13.95)])
S3_403 = '<?xml version="1.0" encoding="UTF-8"?><Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>'


# ------------------------------------------------------------------ parsing --

def test_parse_single_column_and_ohlc():
    rows = cs.parse_history("﻿" + BXM_CSV + "bad,row\n13/45/2020,1\n10/14/2026,2576.31\n", "BXM")
    assert [r["day"] for r in rows] == ["2002-03-22", "2002-03-25", "2026-10-13", "2026-10-14"]
    assert rows[-1] == {"day": "2026-10-14", "close": 2576.31}                       # duplicate day: the last wins
    o = cs.parse_history(SPAI_CSV, "SPAI")
    assert o[-2] == {"day": "2021-11-04", "open": 574.1, "high": 575.2, "low": 572.9, "close": 574.5}
    assert o[-1] == {"day": "2021-11-05", "close": 573.93}                            # blank O/H/L left out, row kept


# -------------------------------------------------------------- point in time --

def test_available_at_evening_et_next_morning_eod_launch_and_cap():
    assert cs.available_at("2026-10-14") == "2026-10-14T23:00:00+00:00"              # EDT: 19:00 ET = 23:00 UTC
    assert cs.available_at("2026-01-15") == "2026-01-16T00:00:00+00:00"              # EST: 19:00 ET = 00:00 UTC next day
    assert cs.available_at("2026-10-14", eod=True) == "2026-10-15T13:00:00+00:00"    # 09:00 ET next calendar day
    assert cs.available_at("2026-01-16", eod=True) == "2026-01-17T14:00:00+00:00"    # Friday close -> Saturday 09:00 EST
    assert cs.available_at("1990-03-01", launch="2015-08-03") == "2015-08-03T23:00:00+00:00"
    assert cs.available_at("2010-01-04", launch="2018-05-29", eod=True) == "2018-05-30T13:00:00+00:00"
    assert cs.available_at("2026-10-14", observed_at="2026-10-14T21:00:00+00:00") == "2026-10-14T21:00:00+00:00"


def test_archive_rows_backtest_dating_and_never_after_observed():
    obs = "2026-10-15T11:30:00+00:00"
    rows = cs.to_archive_rows("BXM", cs.parse_history(BXM_CSV, "BXM"), obs)
    first, last = rows[0], rows[-1]
    assert first["value"]["backtest"] is True and first["available_at"] == "2002-04-30T23:00:00+00:00"   # before BXM launch
    assert last["value"]["backtest"] is False and last["available_at"] == "2026-10-14T23:00:00+00:00"
    assert all(r["available_at"] <= r["observed_at"] == obs for r in rows)
    assert {r["key"] for r in rows} == {"BXM"} and rows[0]["source"] == "cboe"
    cll = {r["value"]["day"]: r for r in cs.to_archive_rows("CLL", cs.parse_history(CLL_CSV, "CLL"), obs)}
    for d in ("2008-08-26", "2008-08-27", "2008-09-29"):                              # before the 2008-09 launch: back-tested
        assert cll[d]["value"]["backtest"] is True and cll[d]["available_at"] == "2008-09-30T23:00:00+00:00"
    assert cll["2008-09-30"]["value"]["backtest"] is False and cll["2009-10-16"]["value"]["backtest"] is False


def test_spai_launch_dating_and_market_closed_row():
    obs = "2026-10-15T11:30:00+00:00"
    assert cs.INDEX_META["SPAI"]["launch"] == "2017-08-15"
    assert cs.INDEX_META["SPAI"]["methodology"] == cs.INDEX_META["SPATI"]["methodology"] == cs.GOV + "SPATI_Methodology.pdf"
    spai = {r["value"]["day"]: r for r in cs.to_archive_rows("SPAI", cs.parse_history(SPAI_CSV, "SPAI"), obs)}
    base = spai["2006-02-03"]
    assert base["value"]["backtest"] is True and base["available_at"] == "2017-08-15T23:00:00+00:00"
    assert spai["2017-08-14"]["value"]["backtest"] is True and spai["2017-08-15"]["value"]["backtest"] is False
    assert spai["2017-08-15"]["available_at"] == "2017-08-15T23:00:00+00:00"
    assert "Ford" in spai["2007-01-02"]["value"]["flag"] and "repeats the previous close" in spai["2007-01-02"]["value"]["flag"]
    assert [d for d, r in spai.items() if r["value"].get("flag")] == ["2007-01-02"]


def test_eod_only_indices_dated_next_morning():
    assert cs.EOD_ONLY == {"SVRPO", "VPD", "VPN"} and all(cs.INDEX_META[s]["eod_only"] for s in cs.EOD_ONLY)
    assert cs.INDEX_META["SVRPO"]["launch"] == "2018-05-29" and cs.INDEX_META["SVRPO"]["methodology"].endswith("SVRPO_Methodology.pdf")
    late = "2026-10-15T14:00:00+00:00"
    sv = {r["value"]["day"]: r for r in cs.to_archive_rows("SVRPO", cs.parse_history(SVRPO_CSV, "SVRPO"), late)}
    for d in ("2005-12-30", "2010-01-04"):                                            # back-tested, published the morning after launch
        assert sv[d]["value"]["backtest"] is True and sv[d]["available_at"] == "2018-05-30T13:00:00+00:00"
    assert sv["2026-10-14"]["value"]["backtest"] is False and sv["2026-10-14"]["available_at"] == "2026-10-15T13:00:00+00:00"
    assert sv["2026-10-13"]["available_at"] == "2026-10-14T13:00:00+00:00"
    early = cs.to_archive_rows("SVRPO", cs.parse_history(SVRPO_CSV, "SVRPO"), "2026-10-15T11:30:00+00:00")
    assert early[-1]["available_at"] == "2026-10-15T11:30:00+00:00"                   # capped at the fetch time
    vpd = cs.to_archive_rows("VPD", cs.parse_history(VPD_CSV, "VPD"), late)
    assert [r["available_at"] for r in vpd] == ["2007-11-17T14:00:00+00:00", "2026-10-15T13:00:00+00:00"]
    assert all(r["value"]["backtest"] is False for r in vpd)
    rec = cs._recipe("SVRPO", 0.7, 4)
    assert "09:00 America/New_York on the calendar day after" in rec and "daily closing value only" in rec
    assert "19:00 America/New_York" in cs._recipe("BXM", 0.7, 4) and "calendar day after" not in cs._recipe("BXM", 0.7, 4)


# ------------------------------------------------------------------- defects --

def test_flags_spike_known_splice_crash_and_closed_days():
    bxy = cs.annotate("BXY", cs.parse_history(BXY_CSV, "BXY"))
    assert [r["day"] for r in bxy if r.get("flag")] == ["2013-03-11"]
    cll = cs.annotate("CLL", cs.parse_history(CLL_CSV, "CLL"))
    flagged = {r["day"]: r["flag"] for r in cll if r.get("flag")}
    assert set(flagged) == {"2009-10-16", "2018-11-22"}
    assert flagged["2018-11-22"] == "row on a market-closed day (Thanksgiving); repeats the previous close"
    assert cs.spikes(cs.parse_history(BXMD_CRASH, "BXMD")) == set()
    cov = cs.coverage(bxy, "BXY")
    assert cov["flagged"] == {"2013-03-11": cs.KNOWN_ISSUES["BXY"]["2013-03-11"]}
    assert cov["closed_day_rows"] == [] and cov["missing_trading_days"] == 0
    c = cs.coverage(cs.to_archive_rows("CLL", cs.parse_history(CLL_CSV, "CLL"), "2026-10-15T11:30:00+00:00"))
    assert c["closed_day_rows"] == ["2018-11-22"] and c["backtest_rows"] == 3
    assert c["missing_trading_days"] > 2000 and c["missing_latest"][-1] == "2018-11-20"    # the fixture is sparse


def test_trading_calendar():
    closed = {"2007-01-02": "President Ford's funeral", "2018-12-05": "President George H. W. Bush's funeral",
              "1998-01-19": "Martin Luther King Jr. Day", "1993-12-24": "Christmas", "2022-06-20": "Juneteenth",
              "2015-04-03": "Good Friday", "2026-07-03": "Independence Day", "1994-04-27": "President Nixon's funeral",
              "2026-10-17": "weekend"}
    for d, why in closed.items():
        assert cs.closed_reason(d) == why and not cs.is_trading_day(d)
    for d in ("1997-01-20", "2010-12-31", "2021-12-31", "2019-07-05", "2018-12-03", "2020-10-16", "2026-10-14"):
        assert cs.is_trading_day(d)                                                   # MLK before 1998; Saturday New Year
    assert cs.trading_days("2026-10-09", "2026-10-14") == ["2026-10-09", "2026-10-12", "2026-10-13", "2026-10-14"]


def test_vix_expiries_holiday_shifts():
    assert cs.vix_expiries("2008-07-01", "2008-10-31") == ["2008-07-16", "2008-08-20", "2008-09-17", "2008-10-22"]
    assert cs.vix_expiries("2014-03-01", "2014-03-31") == ["2014-03-18"]              # Good Friday 30 days later
    assert cs.vix_expiries("2015-07-01", "2015-08-12") == ["2015-07-22", "2015-08-05", "2015-08-12"]   # weekly from 2015-08-05
    assert cs.vix_expiries("2018-12-01", "2018-12-10") == ["2018-12-06"]              # unscheduled closure, SOQ next day
    assert cs.vix_expiries("2019-12-16", "2020-01-10") == ["2019-12-18", "2019-12-24", "2019-12-31", "2020-01-08"]
    assert "2024-06-18" in cs.vix_expiries("2024-06-01", "2024-06-30")                # Wednesday Juneteenth


def test_vro_expiry_carried_and_known_issues():
    v = cs.annotate("VRO", cs.parse_history(VRO_CSV, "VRO"))
    by = {r["day"]: r for r in v}
    assert all(r["backtest"] is False for r in v)
    settlements = [d for d, r in by.items() if r["expiry"] and not r["carried"] and "flag" not in r]
    assert settlements == ["2008-09-17", "2008-10-22", "2016-09-28", "2016-10-05", "2018-11-21", "2018-11-28", "2018-12-06",
                           "2019-01-02", "2019-07-03", "2019-07-10", "2019-07-17", "2019-07-24", "2019-12-18", "2019-12-24",
                           "2019-12-31", "2020-01-08"]
    for d in ("2008-10-17", "2016-10-03", "2019-01-09", "2019-01-16", "2020-01-06", "2020-01-07", "2019-07-23", "2018-12-04"):
        assert by[d]["carried"] is True, d
    assert by["2019-07-24"]["carried"] is False                                       # a real settlement equal to 2019-07-03's
    assert by["2019-01-11"]["carried"] is False and by["2019-01-11"]["expiry"] is False   # late print, off calendar
    assert by["2019-01-09"]["expiry"] and by["2019-01-16"]["expiry"]
    for d in cs.KNOWN_ISSUES["VRO"]:
        if d in by:
            assert by[d]["flag"] == cs.KNOWN_ISSUES["VRO"][d]
    assert "Christmas" in by["2019-12-25"]["flag"] and "Thanksgiving" in by["2018-11-22"]["flag"]
    cov = cs.coverage(v, "VRO")
    assert cov["stale_expiries"] == ["2019-01-09", "2019-01-16"] and cov["settlements"] == len(settlements)
    assert "missing_trading_days" not in cov
    gap = cs.annotate("VRO", cs.parse_history("DATE,VRO\n04/17/2013,15.46\n06/19/2013,17.22\n", "VRO"))
    assert cs.coverage(gap, "VRO")["missing_expiries"] == ["2013-05-22"]


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


def test_fetch_follows_redirect_retries_429_and_stores_local_only(tmp_path):
    calls, rep = [], {}
    a = _archive(tmp_path)
    out = cs.fetch_cboe_strategy(a, symbols=["BXM", "PUTW", "VRO"], client=_mock(calls, {"BXM": 1}), min_interval=0, backoff=0, report=rep)
    assert set(out) == {"cboe-BXM-history", "cboe-PUTW-history", "cboe-VRO-history"}
    assert len(out["cboe-BXM-history"]) == 4 and out["cboe-PUTW-history"] == []
    assert rep["BXM"]["attempts"] == 2 and rep["BXM"]["final_url"].startswith("https://cdn-api.cboe.com/")
    assert rep["PUTW"]["status"] == 403 and rep["PUTW"]["attempts"] == 1               # no file: no retry
    assert rep["BXM"]["coverage"]["first"] == "2002-03-22" and rep["BXM"]["last_modified"].endswith("GMT")
    assert rep["BXM"]["stored"]["in_git"] is False and rep["VRO"]["coverage"]["stale_expiries"] == ["2019-01-09", "2019-01-16"]
    names = {e.name: e for e in a.entries()}
    assert set(names) == {"cboe-BXM-history", "cboe-VRO-history"}                    # empty fetch is not stored
    assert not any(e.in_git for e in names.values())                                  # Cboe terms: never republished
    e = names["cboe-BXM-history"]
    assert e.kind == "data" and e.rows == 4 and "strategy-index" in e.tags and "buywrite" in e.tags
    assert "BXM_History.csv" in e.recipe and "Cboe_BuyWrite_Indices_Methodology.pdf" in e.recipe
    assert "available_at = 19:00 America/New_York" in e.recipe and "2002-04-30" in e.recipe and "backtest" in e.schema
    assert "https://www.cboe.com/terms/" in e.recipe and "personal non-commercial use" in e.recipe and "in_git=False" in e.recipe
    back = list(a.load("cboe-BXM-history"))
    assert back[-1]["value"] == {"day": "2026-10-14", "close": 2576.3, "backtest": False}
    assert all(r["available_at"] <= r["observed_at"] for r in back)
    vro = list(a.load("cboe-VRO-history"))
    assert {"expiry", "carried"} <= set(vro[0]["value"]) and "expiry" in names["cboe-VRO-history"].schema


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
    assert rep["_plan"]["calls"] == len(cs.STRATEGY_INDICES) and rep["_plan"]["in_git"] is False
    assert rep["_plan"]["est_raw_mb"] == pytest.approx(len(cs.STRATEGY_INDICES) * 0.145, abs=0.1)
    out = cs.fetch_cboe_strategy(None, symbols=["BXM", "VRO", "SPAI"], limit=2, client=_mock(calls), min_interval=0, backoff=0)
    assert list(out) == ["cboe-BXM-history", "cboe-VRO-history"] and len(calls) == 4      # 2 indices x (307 + 200)


# ------------------------------------------------------------- index -> theory --

def test_index_list_launch_dates_and_theory_map_match_registry():
    required = ["BXM", "BXMD", "BXY", "BXMC", "PUT", "PUTY", "PUTR", "WPUT", "CLL", "CLLZ", "CMBO", "CNDR", "BFLY",
                "PPUT", "VXTH", "RXM", "BXN", "BXR", "VRO"]
    assert set(required) <= set(cs.STRATEGY_INDICES) and "PUTW" not in cs.STRATEGY_INDICES   # PUTW answers 403
    assert len(cs.STRATEGY_INDICES) == 59
    reg = json.loads((Path(mandel.__file__).parent / "theories" / "registry.json").read_text())["theories"]
    ids = {t["id"] for t in (reg.values() if isinstance(reg, dict) else reg)}
    mapped = {t for m in cs.INDEX_META.values() for t in m["theories"]}
    assert mapped <= ids and set(cs.THEORY_NOTES) == mapped
    assert {"PUT", "BXM"} <= set(cs.indices_for("T-202")) and cs.indices_for("T-220") == ["VRO"]
    assert "BXMD" in cs.indices_for("T-54") and "CNDR" in cs.indices_for("T-109") and "BFLY" in cs.indices_for("T-106")
    assert cs.INDEX_META["CLL"]["launch"] == "2008-09-30"
    for s, m in cs.INDEX_META.items():
        assert m["history"] == cs.history_url(s) and m["dashboard"].startswith("https://www.cboe.com/us/indices/dashboard/")
        if s == "VRO":
            assert m["launch"] is None and m["family"] == "settlement"
            continue
        assert len(m["launch"]) == 10 and m["methodology"].startswith(cs.GOV), s       # every index: launch + methodology
