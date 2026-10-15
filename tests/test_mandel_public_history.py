"""mandel.data.public_history on mocked HTTP only (httpx.MockTransport / a patched urlopen; no network): the COT release
rule and Socrata creation times, Treasury announcement vs result rows, the Cleveland Fed label years and release-day
actuals, the SPDR / SSGA workbooks and Sprott Highcharts parsers, the Wikipedia tables (rowspans, announcement dates from
index-announcement citations only, CC BY-SA attribution), the fja join/leave events, FINRA short-interest paging and the
publication lag, CNMS universe filtering and month completeness, SEC buckets (acceptance bound, concept filter, coverage
and resume), the StockTwits anchor search and windows, Deribit near-expiry days, dry runs that make no request, skip-stored
and refresh, and the licence / .gitignore decisions."""

import io
import json
import math
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import pytest

from mandel.archive import Archive
from mandel.data import options_misc as om
from mandel.data import public_history as ph
from mandel.ledger import Ledger

UTC = timezone.utc
NOW = datetime(2026, 10, 16, 15, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(om, "_sleep", lambda s: None)
    monkeypatch.setattr(ph, "_sleep", lambda s: None)
    monkeypatch.setattr(ph, "_now", lambda: NOW)


@pytest.fixture
def archive(tmp_path):
    return Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))


def _rows(archive, name):
    return list(archive.load(name))


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _forbid(req):
    raise AssertionError(f"unexpected request {req.url}")


# ================================================================================================ COT rule ==

@pytest.mark.parametrize("report,release", [
    ("2026-01-13", "2026-01-16T20:30:00+00:00"),      # MLK is the next Monday: no shift (EST: 15:30 ET = 20:30 UTC)
    ("2026-07-14", "2026-07-17T19:30:00+00:00"),      # EDT
    ("2025-12-30", "2026-01-05T20:30:00+00:00"),      # New Year's Day Thursday -> Monday (CFTC 2026 schedule 'January 05*')
    ("2026-06-16", "2026-06-22T19:30:00+00:00"),      # Juneteenth Friday -> Monday ('June 22*')
    ("2026-06-30", "2026-07-06T19:30:00+00:00"),      # July 4 observed Friday July 3 -> Monday ('July 06*')
    ("2026-11-10", "2026-11-16T20:30:00+00:00"),      # Veterans Day Wednesday -> Monday ('November 16*')
    ("2026-11-24", "2026-11-30T20:30:00+00:00"),      # Thanksgiving -> Monday ('November 30*')
    ("2026-12-22", "2026-12-28T20:30:00+00:00"),      # Christmas Friday -> Monday ('December 28*')
    ("2014-12-23", "2014-12-30T20:30:00+00:00"),      # Dec 25 + Dec 26 (executive order) -> Tuesday (CFTC notice 2014-12-19)
    ("2015-06-30", "2015-07-06T19:30:00+00:00"),      # July 3 2015 -> Monday July 6 (CFTC notice)
    ("2018-12-04", "2018-12-10T20:30:00+00:00"),      # national day of mourning Wed Dec 5 2018
    ("2018-12-24", "2019-02-01T20:30:00+00:00"),      # 2019 shutdown catch-up (press release 7864-19)
    ("2019-02-26", "2019-03-05T20:30:00+00:00"),
])
def test_cot_release_rule(report, release):
    assert ph.cot_release_rule(report)[0] == release


def test_cot_shutdown_catchups_and_federal_calendar():
    # 2013 (regression: was a 2013-11-29 bound): CFTC 6745-13 first delayed report 10-25; notice 11-06 'week of October 29
    # ... now available'; the 11-05 report on its normal Friday 11-08 (notice of that day)
    assert ph.cot_release_rule("2013-10-01")[:3:2] == ("2013-10-25T23:59:59+00:00", "schedule")
    for d in ("2013-10-08", "2013-10-15", "2013-10-22", "2013-10-29"):
        assert ph.cot_release_rule(d)[0] == "2013-11-06T23:59:59+00:00"
    assert ph.cot_release_rule("2013-11-05")[0] == "2013-11-08T20:30:00+00:00"
    assert ph.cot_release_rule("2013-11-19")[0] == "2013-11-22T20:30:00+00:00"
    rel, basis, pit = ph.cot_release_rule("1995-12-05")                                # 1995-96: conservative bound kept
    assert rel == "1996-02-29T23:59:59+00:00" and basis.startswith("conservative bound") and pit == "bound"
    hol = ph.federal_closures(2021)
    assert datetime(2021, 12, 31).date() in hol          # New Year 2022 is a Saturday: observed Friday Dec 31, 2021
    assert datetime(2021, 6, 18).date() in hol and datetime(2020, 6, 19).date() not in ph.federal_closures(2020)


def test_cot_available_at_live_and_bulk():
    av, basis, rule, pit = ph.cot_available_at("2026-10-06", "2026-10-09T19:30:07.543Z")
    assert (av, basis, pit) == ("2026-10-09T19:30:08+00:00", "Socrata :created_at (live publication)", "live")
    assert rule == "2026-10-09T19:30:00+00:00"
    # created before the Friday 15:30 ET release: never earlier than the release
    assert ph.cot_available_at("2026-10-06", "2026-10-09T15:39:00Z")[0] == "2026-10-09T19:30:00+00:00"
    # a 2022 bulk-load creation time far after an old report: the rule
    av, basis, _, pit = ph.cot_available_at("2012-03-13", "2022-08-01T18:54:48.615Z")
    assert av == "2012-03-16T19:30:00+00:00" and basis.startswith("rule") and pit == "schedule"
    # a delayed live publication (2025 shutdown) keeps the real time
    assert ph.cot_available_at("2025-10-14", "2025-11-25T20:30:48Z")[0] == "2025-11-25T20:30:48+00:00"


BULK = "2022-09-13T14:25:38.412Z"


@pytest.mark.parametrize("asof,available,pit", [
    # checker's case (regression): 1990-03-30 was released at 15:30 ET that day, before its own observed_at; the 1990
    # switch month to the 6th-business-day schedule is not stated, so 1990 keeps the later monthly schedule
    ("1990-03-30", "1990-04-12T23:59:59+00:00", "bound"),
    ("1987-03-13", "1987-04-13T23:59:59+00:00", "not_realtime"),   # pre-1990 mid-month: no real-time publication (12th = Sunday)
    ("1987-03-31", "1987-04-13T23:59:59+00:00", "bound"),          # pre-1990 month-end: the monthly publication
    ("1991-03-29", "1991-04-08T23:59:59+00:00", "schedule"),       # 1991-92: 6th federal business day
    ("1992-09-30", "1992-10-08T23:59:59+00:00", "schedule"),
    ("1996-06-04", "1996-06-14T23:59:59+00:00", "bound"),          # 1992-10..2000 biweekly: the following week's release day
    ("2000-12-26", "2001-01-05T23:59:59+00:00", "bound"),          # all of 2000 keeps the biweekly bound
    ("2001-12-21", "2001-12-28T20:30:00+00:00", "schedule"),       # Friday as-of (regression): the next week's Friday
    ("2003-02-14", "2003-02-21T20:30:00+00:00", "schedule"),
    ("2010-12-23", "2011-01-03T20:30:00+00:00", "schedule"),       # Thursday as-of; Friday Dec 31 closed -> Monday
    ("2007-01-03", "2007-01-08T20:30:00+00:00", "schedule"),       # Wednesday as-of: 3rd federal business day minimum
])
def test_cot_release_eras_and_holiday_weeks(asof, available, pit):
    av, basis, rule, p = ph.cot_available_at(asof, BULK, "legacy-f", "088691")
    assert (av, p) == (available, pit) and rule == available
    assert ph._parse_iso(av) > ph._parse_iso(ph._et(asof, "17:00"))     # strictly after the positions' own close


def test_cot_backcasts_disaggregated_and_tff():
    # regression: disaggregated rows before 2009-09 were released as history on 2009-10-20, not on the weekly rule
    av, basis, rule, pit = ph.cot_available_at("2006-06-13", BULK, "disagg-fo", "088691")
    assert (av, pit, rule) == ("2009-10-20T23:59:59+00:00", "backcast", "2006-06-16T19:30:00+00:00")
    assert basis.startswith("CFTC historical disaggregated release 2009-10-20 (backcast")
    assert ph.cot_available_at("2009-08-25", BULK, "disagg-f", "084691")[0] == "2009-10-20T23:59:59+00:00"
    # gold and silver were in the first disaggregated report (as of 2009-09-01, published 2009-09-04)
    assert ph.cot_available_at("2009-09-01", BULK, "disagg-f", "084691")[::3] == ("2009-09-04T19:30:00+00:00", "schedule")
    # a market not known to be among the first 22 (platinum) counts from its 2009-12-04 addition
    assert ph.cot_available_at("2009-09-01", BULK, "disagg-fo", "076651")[::3] == ("2009-12-04T23:59:59+00:00", "backcast")
    assert ph.cot_available_at("2009-12-01", BULK, "disagg-fo", "076651")[::3] == ("2009-12-04T20:30:00+00:00", "schedule")
    # the legacy report of the same date is not a backcast
    assert ph.cot_available_at("2006-06-13", BULK, "legacy-fo", "088691")[3] == "schedule"
    # TFF: first report as of 2010-07-20; earlier rows from the December 2010 history release; CME bitcoin is live
    assert ph.cot_available_at("2010-07-13", BULK, "tff-f", "13874A")[::3] == ("2010-12-07T23:59:59+00:00", "backcast")
    assert ph.cot_available_at("2018-04-10", BULK, "tff-f", "133741")[::3] == ("2018-04-13T19:30:00+00:00", "schedule")


def test_parse_cot_rows_pit_and_observed_guard(monkeypatch):
    raw = [_cot_row(d, BULK) for d in ("1987-03-13", "1990-03-30", "2001-12-21", "2001-12-28", "2012-03-13")]
    stats = {}
    rows = ph.parse_cot_rows(raw, "legacy-f", "088691", "2026-10-15T00:00:00+00:00", stats)
    assert all(ph._parse_iso(r["available_at"]) > ph._parse_iso(r["observed_at"]) for r in rows)
    assert [r["value"]["pit"] for r in rows] == ["not_realtime", "bound", "schedule", "schedule", "schedule"]
    assert stats == {"not_realtime": 1, "bound": 1, "schedule": 3}
    # the guard: an availability before the positions' close is raised to observed_at and counted
    monkeypatch.setattr(ph, "cot_available_at", lambda rd, ca, rp=None, cd=None: (ph._et(rd, "15:30"), "test", ph._et(rd, "15:30"), "schedule"))
    stats = {}
    rows = ph.parse_cot_rows(raw[2:3], "legacy-f", "088691", "2026-10-15T00:00:00+00:00", stats)
    assert rows[0]["available_at"] == rows[0]["observed_at"] == "2001-12-21T22:00:00+00:00"
    assert stats["raised_to_observed"] == 1 and rows[0]["value"]["available_basis"].endswith("raised to observed_at (guard)")


def _cot_row(day, created=None, code="088691"):
    r = {"id": f"{day}{code}", "report_date_as_yyyy_mm_dd": day + "T00:00:00.000", "cftc_contract_market_code": code,
         "m_money_positions_long_all": "100", "m_money_positions_short_all": "50", "open_interest_all": "1000"}
    if created:
        r[":created_at"] = created
    return r


def test_fetch_cftc_cot_pages_stores_in_git_and_skips(archive, monkeypatch):
    monkeypatch.setattr(ph, "COT_PAGE", 2)
    calls = []
    days = ["2012-03-13", "2012-03-20", "2026-09-29", "2026-10-06"]
    created = {"2026-09-29": "2026-10-02T19:30:09.762Z", "2026-10-06": "2026-10-09T19:30:07.543Z"}

    def handler(req):
        q = {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}
        calls.append(q)
        assert req.url.path == "/resource/kh3c-gbw2.json" and q["cftc_contract_market_code"] == "088691"
        assert q["$select"] == "*,:created_at,:updated_at"
        off, lim = int(q["$offset"]), int(q["$limit"])
        return httpx.Response(200, json=[_cot_row(d, created.get(d)) for d in days[off:off + lim]])

    rep = ph.fetch_cftc_cot(archive, series=[("disagg-fo", "088691")], client=_client(handler), min_interval=0)
    name = "cftc-cot-disagg-fo-088691"
    assert rep[name]["stored"]["in_git"] is True and len(calls) == 3                # 2 + 2 + empty page
    rows = _rows(archive, name)
    assert [r["value"]["report_date"] for r in rows] == days
    assert rows[0]["available_at"] == "2012-03-16T19:30:00+00:00" and rows[0]["observed_at"] == "2012-03-13T21:00:00+00:00"
    assert rows[-1]["available_at"] == "2026-10-09T19:30:08+00:00" and rows[-1]["value"]["m_money_positions_long_all"] == "100"
    assert "complete" in archive.get(name).tags and "public domain" in archive.get(name).recipe
    assert ph.gitignore_line(name) is None
    rep2 = ph.fetch_cftc_cot(archive, series=[("disagg-fo", "088691")], client=_client(_forbid), min_interval=0)
    assert rep2[name] == {"skipped": "stored"}
    ph.fetch_cftc_cot(archive, series=[("disagg-fo", "088691")], client=_client(handler), min_interval=0, refresh=True)
    assert len(calls) == 6


def test_fetch_cftc_failure_never_stores(archive):
    rep = ph.fetch_cftc_cot(archive, series=[("disagg-f", "084691")], client=_client(lambda r: httpx.Response(500, text="boom")),
                            min_interval=0, retries=2)
    assert "error" in rep["cftc-cot-disagg-f-084691"]
    with pytest.raises(KeyError):
        archive.get("cftc-cot-disagg-f-084691")


# ============================================================================================ Treasury auctions ==

def _auction(cusip, ad, ann, term="10-Year", typ="Note", tips="No", frn="No", result=True, close="01:00 PM"):
    return {"cusip": cusip, "security_type": typ, "security_term": term, "original_security_term": term, "auction_date": ad,
            "issue_date": ad, "maturity_date": "2036-01-01", "announcemt_date": ann, "offering_amt": "42000000000", "reopening": "No",
            "inflation_index_security": tips, "floating_rate": frn, "closing_time_comp": close, "closing_time_noncomp": "12:00 PM",
            "high_yield": "4.100" if result else "null", "bid_to_cover_ratio": "2.5" if result else "null", "int_rate": "null"}


def test_treasury_auction_rows_and_fetch(archive):
    data = [_auction("A1", "2026-10-08", "2026-10-01", term="29-Year 10-Month", typ="Bond"),
            _auction("A2", "2026-10-22", "2026-10-15", term="5-Year", tips="Yes", result=False),
            _auction("A3", "1979-10-31", "1979-10-24", close="null")]
    pages = [data[:2], data[2:]]
    seen = []

    def handler(req):
        q = {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}
        seen.append(q)
        assert q["filter"] == "security_type:in:(Note,Bond),auction_date:gte:1979-01-01"
        k = int(q["page[number]"])
        return httpx.Response(200, json={"data": pages[k - 1], "meta": {"total-pages": 2, "total-count": 3}})

    rep = ph.fetch_treasury_auctions(archive, client=_client(handler), min_interval=0)
    assert rep["treasury-auctions"]["stored"]["in_git"] is True and len(seen) == 2
    rows = {(r["kind"], r["value"]["cusip"]): r for r in _rows(archive, "treasury-auctions")}
    a1 = rows[("auction-announcement", "A1")]
    assert a1["available_at"] == "2026-10-01T23:59:59+00:00" and a1["value"]["nominal_coupon"] is True
    assert "high_yield" not in a1["value"]                                            # results never in the schedule row
    r1 = rows[("auction-result", "A1")]
    assert r1["observed_at"] == "2026-10-08T17:00:00+00:00" and r1["available_at"] == "2026-10-08T17:30:00+00:00"
    assert r1["value"]["high_yield"] == "4.100" and r1["value"]["int_rate"] is None    # 'null' -> None
    assert ("auction-result", "A2") not in rows                                        # announced, not yet held
    a2 = rows[("auction-announcement", "A2")]
    assert a2["value"]["nominal_coupon"] is False and a2["available_at"] == "2026-10-15T23:59:59+00:00"   # TIPS; announced
    r3 = rows[("auction-result", "A3")]
    assert r3["available_at"] == "1979-10-31T23:59:59+00:00"                           # no closing time: end of day


# ====================================================================================== Cleveland Fed nowcasts ==

def _nowcast_el(target, labels, series):
    cats = [{"label": l, "vline": "true"} if l.startswith("CPI ") else {"label": l} for l in labels]
    return {"chart": {"subcaption": target, "_comment": "2026-10-15 00:00"}, "categories": [{"category": cats}],
            "dataset": [{"seriesname": n, "data": [{"value": v} for v in vals]} for n, vals in series.items()]}


def test_clevelandfed_parse_years_vlines_and_times():
    el = _nowcast_el("2025-12", ["12/30", "01/12", "01/13", "CPI Dec", "01/14"],
                     {"CPI Inflation": ["0.25", "0.27", "", ""], "Actual CPI Inflation": ["", "", "0.3073", ""]})
    rows = ph.parse_nowcast([el], "month", "mom", NOW.isoformat())
    by = {(r["kind"], r["value"]["label_date"]): r for r in rows}
    assert set(by) == {("nowcast", "2025-12-30"), ("nowcast", "2026-01-12"), ("actual", "2026-01-13")}
    assert by[("nowcast", "2026-01-12")]["available_at"] == "2026-01-12T17:00:00+00:00"      # 12:00 EST
    assert by[("actual", "2026-01-13")]["available_at"] == "2026-01-13T13:30:00+00:00"       # 08:30 EST release day
    assert all(r["value"]["target"] == "2025-12" and r["value"]["vintage_verified"] is False for r in rows)
    q = ph.parse_nowcast([_nowcast_el("2026:Q1", ["12/31", "01/02"], {"PCE Inflation": ["3.1", "3.2"]})], "quarter", "qoq-saar",
                         NOW.isoformat())
    assert [r["value"]["label_date"] for r in q] == ["2025-12-31", "2026-01-02"]
    assert ph.parse_nowcast([_nowcast_el("2013-7", ["08/20"], {"CPI Inflation": ["0.1"]})], "month", "mom", NOW.isoformat())[0]["value"]["target"] == "2013-07"


def test_clevelandfed_fetch_and_snapshot(archive):
    month = [_nowcast_el(f"2026-{m}", [f"{m:02d}/02"], {"CPI Inflation": ["0.2"]}) for m in range(5, 10)]
    quarter = [_nowcast_el("2026:Q3", ["09/02"], {"CPI Inflation": ["3.0"]})]

    def handler(req):
        return httpx.Response(200, content=json.dumps(month if "month" in req.url.path else quarter).encode())

    rep = ph.fetch_clevelandfed_nowcast(archive, client=_client(handler), min_interval=0)
    assert rep["clevelandfed-inflation-nowcast"]["stored"]["in_git"] is False
    assert len(_rows(archive, "clevelandfed-inflation-nowcast")) == 6
    rep = ph.fetch_clevelandfed_snapshot(archive, client=_client(handler), min_interval=0, targets=2)
    name = "clevelandfed-nowcast-snapshot-2026-10-16"
    snap = _rows(archive, name)
    assert {r["value"]["target"] for r in snap} == {"2026-08", "2026-09", "2026:Q3"}
    assert all(r["available_at"] == NOW.isoformat() for r in snap)
    assert ph.gitignore_line(name) == "mandel/archive/data/clevelandfed-nowcast-snapshot-*.jsonl.gz"


# ======================================================================== SPDR, Sprott, SSGA sponsor files ==

def _xlsx(sheets: dict) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


SPDR_HEADER = ("Date", "Closing Price", "Ounces of Gold per Share", "NAV/Share at 10:30am NYT", "Indicative Price per Share at 4:15pm NYT",
               "Mid point of bid/ask spread at 4:15pm NYT", "Premium/Discount of GLD Mid Point vs Indicative Value of GLD at 4:15pm NYT",
               "Daily Share Volume", "Total Ounces of Gold in the Trust", "Tonnes of Gold", "Total Net Asset Value in the Trust")


def test_spdr_archive(archive):
    content = _xlsx({"Disclaimer": [("Reproduction or redistribution ... expressly prohibited",)],
                     "US GLD Historical Archive": [SPDR_HEADER,
                                                   ("13-Oct-2026", 381.67, 0.0916, 382.19, 381.56, 381.63, 0.0173, 5711673, 33893447.76, 1054.2, 1.4e11),
                                                   ("14-Oct-2026",) + ("US Holiday",) * 10,
                                                   ("15-Oct-2026", 375.99, 0.0916, 374.83, 376.08, 375.97, -0.0314, 10311133, 33893447.76, 1054.2, 1.38e11)]})
    ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def handler(req):
        assert req.url.params["product"] == "gld"
        return httpx.Response(200, content=content, headers={"content-type": ctype, "last-modified": "Fri, 16 Oct 2026 02:10:38 GMT"})

    rep = ph.fetch_spdr_archive(archive, products=["gld"], client=_client(handler), min_interval=0)
    assert rep["spdr-gld-archive"]["holidays_dropped"] == 1
    rows = _rows(archive, "spdr-gld-archive")
    assert [r["value"]["day"] for r in rows] == ["2026-10-13", "2026-10-15"]
    assert rows[0]["value"]["tonnes"] == 1054.2 and rows[0]["value"]["premium_discount_415pm"] == 0.0173
    assert rows[0]["available_at"] == "2026-10-14T13:30:00+00:00" and rows[0]["observed_at"] == "2026-10-13T20:00:00+00:00"
    assert rows[1]["available_at"] == "2026-10-16T13:30:00+00:00"
    assert archive.get("spdr-gld-archive").in_git is False
    bad = ph.fetch_spdr_archive(archive, products=["gldm"], client=_client(lambda r: httpx.Response(200, text="%PDF-1.4",
                                headers={"content-type": "application/pdf"})), min_interval=0)
    assert "not an xlsx" in bad["spdr-gldm-archive"]["error"]


SPROTT_PAGE = """<script>
 series: [{ name: 'Share Price', color: '#8c7838', data: [[Date.UTC(2010,1,25),10.00],[Date.UTC(2010,1,26),9.62]] }]
 series: [{ name: 'Net Asset Value', data: [[Date.UTC(2010,1,25),10.00],[Date.UTC(2010,1,26),9.50]] }]
 series: [{ name: 'Premium/Discount to Net Asset Value', marker: { radius: 2 }, data: [[Date.UTC(2010,1,25),0.00],[Date.UTC(2010,1,26),1.34],[Date.UTC(2010,11,31),null]] }]
 <td>PHYS (NAV)</td> name: 'Benchmark: Spot Gold Price'
</script>"""


def test_sprott_highcharts(archive):
    s = ph.parse_highcharts(SPROTT_PAGE)
    assert s["Premium/Discount to Net Asset Value"] == {"2010-02-25": 0.0, "2010-02-26": 1.34}      # month is 0-based; null dropped
    rep = ph.fetch_sprott_trusts(archive, funds=["phys"], client=_client(lambda r: httpx.Response(200, text=SPROTT_PAGE)), min_interval=0)
    rows = _rows(archive, "sprott-phys-nav")
    assert rows[1]["value"] == {"fund": "PHYS", "day": "2010-02-26", "share_price": 9.62, "nav": 9.5, "premium_discount_pct": 1.34}
    assert rows[1]["available_at"] == "2010-02-27T14:30:00+00:00"
    miss = ph.fetch_sprott_trusts(archive, funds=["pslv"], client=_client(lambda r: httpx.Response(200, text="<html></html>")), min_interval=0)
    assert "missing" in miss["sprott-pslv-nav"]["error"]


def test_ssga_holdings_snapshot(archive):
    content = _xlsx({"holdings": [("Fund Name:", "SPDR S&P 500 ETF Trust"), ("Ticker Symbol:", "SPY"), ("Holdings:", "As of 14-Oct-2026"), (),
                                  ("Name", "Ticker", "Identifier", "SEDOL", "Weight", "Sector", "Shares Held", "Local Currency"),
                                  ("NVIDIA CORP", "NVDA", "67066G104", "2379504", 8.05, "-", 298491438.0, "USD"),
                                  ("APPLE INC", "AAPL", "037833100", "2046251", 7.52, "-", 180010285.0, "USD"), (), ("Before investing ...",)]})
    ctype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    h = lambda r: httpx.Response(200, content=content, headers={"content-type": ctype, "last-modified": "Thu, 15 Oct 2026 13:00:51 GMT"})
    rep = ph.fetch_ssga_holdings(archive, client=_client(h), min_interval=0)
    name = "ssga-spy-holdings-2026-10-14"
    rows = _rows(archive, name)
    assert [r["value"]["ticker"] for r in rows] == ["NVDA", "AAPL"] and rows[0]["value"]["weight"] == 8.05
    assert rows[0]["available_at"] == "2026-10-15T13:00:51+00:00" and rows[0]["observed_at"] == "2026-10-14T20:00:00+00:00"
    assert ph.fetch_ssga_holdings(archive, client=_client(h), min_interval=0)[name] == {"skipped": "stored"}


# ============================================================================================ Wikipedia tables ==

WIKI_CONST = """<html><script>"wgRevisionId":1380159481,</script>
<table class="wikitable sortable" id="constituents"><tbody>
<tr><th><a href="x">Symbol</a></th><th>Security</th><th>GICS Sector</th><th>GICS Sub-Industry</th><th>Headquarters Location</th><th>Date added</th><th>CIK</th><th>Founded</th></tr>
<tr><td><a href="https://www.nyse.com/quote/XNYS:MMM">MMM</a></td><td><a href="/wiki/3M">3M</a></td><td>Industrials</td><td>Industrial Conglomerates</td><td>Saint Paul, Minnesota</td><td>1957-03-04</td><td>0000066740</td><td>1902</td></tr>
<tr><td>BRK.B</td><td>Berkshire Hathaway</td><td>Financials</td><td>Multi-Sector Holdings</td><td>Omaha, Nebraska</td><td>2010-02-16</td><td>0001067983</td><td>1839</td></tr>
</tbody></table>
<li id="footer-info-lastmod"> This page was last edited on 14 October 2026, at 03:35</li></html>"""

WIKI_CHANGES = """<html><script>"wgRevisionId":1379179365,</script>
<table class="wikitable sortable" id="changes"><tbody>
<tr><th rowspan="2">Effective Date</th><th colspan="2">Added</th><th colspan="2">Removed</th><th rowspan="2">Reason</th><th rowspan="2">Refs</th></tr>
<tr><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th></tr>
<tr><td rowspan="2">September 21, 2026</td><td>BE</td><td><a href="/wiki/Bloom">Bloom Energy</a></td><td>TAP</td><td>Molson Coors</td><td>Market capitalization changes.</td><td><sup><a href="#cite_note-a-1">[1]</a></sup></td></tr>
<tr><td>ILMN</td><td>Illumina, Inc.</td><td>BLDR</td><td>Builders FirstSource</td><td>Market capitalization changes.</td><td><sup><a href="#cite_note-a-1">[1]</a></sup></td></tr>
<tr><td>October 6, 2026</td><td>TWLO</td><td>Twilio</td><td>WBD</td><td>Warner Bros. Discovery</td><td>Paramount Skydance acquired Warner Bros. Discovery<sup><a href="#cite_note-m-2">[2]</a></sup></td><td><sup><a href="#cite_note-n-3">[3]</a></sup></td></tr>
</tbody></table>
<ol class="references">
<li id="cite_note-a-1"><span>"Bloom Energy, Illumina, and Everpure Set to Join S&amp;P 500" (PDF). S&amp;P Dow Jones Indices. September 4, 2026. Retrieved September 21, 2026.</span></li>
<li id="cite_note-m-2"><span>"Paramount Skydance agrees to acquire Warner Bros. Discovery". Reuters. September 12, 2026. Retrieved October 1, 2026.</span></li>
<li id="cite_note-n-3"><span>"Twilio Set to Join S&amp;P 500". News Release Archive. Retrieved October 8, 2026.</span></li>
</ol>
<li id="footer-info-lastmod"> This page was last edited on 8 October 2026, at 11:11</li></html>"""


def test_wikipedia_tables(archive):
    def handler(req):
        return httpx.Response(200, text=WIKI_CONST if "List_of" in str(req.url) else WIKI_CHANGES)

    rep = ph.fetch_wikipedia_sp500(archive, client=_client(handler), min_interval=0)
    const = _rows(archive, "wikipedia-sp500-constituents")
    assert [r["value"]["symbol"] for r in const] == ["MMM", "BRK.B"]
    assert const[0]["value"]["gics_sector"] == "Industrials" and const[0]["value"]["cik"] == "0000066740"
    assert const[0]["available_at"] == "2026-10-14T03:35:00+00:00" and const[0]["value"]["revid"] == 1380159481
    ch = {r["value"]["added_ticker"]: r for r in _rows(archive, "wikipedia-sp500-changes")}
    assert ch["ILMN"]["value"]["effective_date"] == "2026-09-21"                         # rowspan expanded
    assert ch["BE"]["value"]["announced"] == "2026-09-04" and ch["BE"]["available_at"] == "2026-09-04T23:59:59+00:00"
    # the merger article (dated before the index announcement) is not an announcement; the index note has no date
    tw = ch["TWLO"]
    assert tw["value"]["announced"] is None and tw["available_at"] == "2026-10-06T13:30:00+00:00"
    assert tw["value"]["reason"] == "Paramount Skydance acquired Warner Bros. Discovery"
    e = archive.get("wikipedia-sp500-changes")
    assert e.in_git is True and "cc-by-sa-4.0" in e.tags and "oldid=1379179365" in e.recipe and "CC BY-SA 4.0" in e.recipe
    assert ph.gitignore_line("wikipedia-sp500-changes") is None


def test_wiki_get_urllib_retries(monkeypatch):
    import urllib.error
    import urllib.request
    seen = []

    class Resp(io.BytesIO):
        status = 200
        headers = {"last-modified": "Wed, 14 Oct 2026 03:35:16 GMT"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=None):
        seen.append(req.get_header("User-agent"))
        if len(seen) == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "Too many", {"retry-after": "1"}, io.BytesIO(b"slow"))
        return Resp(b"<html>ok</html>")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    r, info = ph._wiki_get("https://en.wikipedia.org/wiki/X", ph.Throttle(0))
    assert r.text == "<html>ok</html>" and info["attempts"] == 2 and "mandel-research@example.org" in seen[0]


# ================================================================================================= fja05680 ==

def test_fja_components_spells_and_fallback(archive):
    comp = 'date,tickers\n2019-01-02,"AAPL,BRK.B,CELG"\n2019-11-21,"AAPL,BRK.B"\n'
    spells = "ticker,start_date,end_date\nCELG,2001-01-01,2019-11-21\nAAPL,1982-11-30,\n"

    def handler(req):
        if req.url.host == "cdn.jsdelivr.net" and "Components" in unquote(req.url.path):
            return httpx.Response(404, text="not found")                       # jsDelivr miss -> raw.githubusercontent
        return httpx.Response(200, text=comp if "Components" in unquote(req.url.path) else spells)

    rep = ph.fetch_fja_sp500(archive, client=_client(handler), min_interval=0)
    assert rep["fja-sp500-components"]["via"] == "raw.githubusercontent.com"
    c = _rows(archive, "fja-sp500-components")
    assert c[1]["value"] == {"date": "2019-11-21", "tickers": ["AAPL", "BRK.B"], "n": 2} and c[1]["available_at"] == "2019-11-21T14:30:00+00:00"
    s = _rows(archive, "fja-sp500-ticker-spells")
    joins = [r for r in s if r["kind"] == "sp500-join"]
    leaves = [r for r in s if r["kind"] == "sp500-leave"]
    assert all("end_date" not in r["value"] for r in joins)                           # a join row never carries its end
    assert [(r["value"]["ticker"], r["value"]["date"]) for r in leaves] == [("CELG", "2019-11-21")]
    assert archive.get("fja-sp500-components").in_git is False
    assert ph.gitignore_line("fja-sp500-components") == "mandel/archive/data/fja-sp500-components.jsonl.gz"


# ========================================================================================= FINRA short interest ==

def _si(sym, mcc, sd="2026-09-30"):
    return {"symbolCode": sym, "marketClassCode": mcc, "settlementDate": sd, "accountingYearMonthNumber": 20260930,
            "currentShortPositionQuantity": 100, "daysToCoverQuantity": 1.5, "issueName": f"{sym} Inc"}


def test_finra_short_interest(archive, monkeypatch):
    monkeypatch.setattr(ph, "FINRA_PAGE", 2)
    listed = [_si("A", "NYSE"), _si("AA", "NYSE"), _si("AAPL", "NNM")]
    otc = [_si("ZZZZF", "OTC")]
    bodies = []

    def handler(req):
        b = json.loads(req.content)
        bodies.append(b)
        filt = {f["fieldName"]: f["fieldValue"] for f in b.get("compareFilters", [])}
        if filt.get("symbolCode"):
            return httpx.Response(200, json=[{"settlementDate": "2026-09-30"}, {"settlementDate": "2017-12-15"}])
        dom = (b.get("domainFilters") or [{}])[0].get("values")
        pool = listed + otc if dom is None else [x for x in listed + otc if x["marketClassCode"] in dom]
        page = pool[b["offset"]: b["offset"] + b["limit"]]
        return httpx.Response(200, json=page, headers={"record-total": str(len(pool))})

    rep = ph.fetch_finra_short_interest(archive, client=_client(handler), min_interval=0)
    name = "finra-short-interest-2026-09-30"
    assert rep[name]["mode"] == "listed" and rep[name]["total"] == 4 and rep[name]["otc"] == 1
    assert "finra-short-interest-2017-12-15" not in rep                               # before FINRA's first date
    rows = _rows(archive, name)
    assert [r["value"]["symbolCode"] for r in rows] == ["A", "AA", "AAPL"]
    assert "accountingYearMonthNumber" not in rows[0]["value"]
    assert rows[0]["available_at"] == "2026-10-12T23:59:59+00:00"                    # 8th NYSE business day after 09-30
    assert archive.get(name).in_git is False
    # an unknown market class makes listed + OTC != total: page everything and drop OTC client-side
    listed.append(_si("NEWX", "XNEW"))
    rep = ph.fetch_finra_short_interest(archive, dates=["2026-09-30"], client=_client(handler), min_interval=0, refresh=True)
    assert rep[name]["mode"].startswith("all") and "XNEW" in rep[name]["classes"] and "OTC" not in rep[name]["classes"]


def test_finra_business_days():
    assert ph.nth_business_day("2017-12-29", 8) == "2018-01-11"
    assert ph.finra_si_available("2025-12-31") == "2026-01-13T23:59:59+00:00"        # Jan 1 skipped


# ============================================================================================== FINRA CNMS ==

def test_cnms_universe_filter_and_month(archive):
    archive.store("fja-sp500-components", "data", [{"key": "2026-08-18", "value": {"date": "2026-08-18", "tickers": ["AAPL", "BRK.B"]}}],
                  recipe="t")
    archive.store("wikipedia-sp500-changes", "data", [{"key": "x", "value": {"effective_date": "2026-09-21", "added_ticker": "BE",
                                                                          "removed_ticker": "TAP"}}], recipe="t")
    uni = ph.cnms_universe(archive, "2026-09-01")
    assert uni == {"AAPL", "BRK/B", "BE", "TAP"}
    text = "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n{d}|AAPL|10.5|1|30|B,Q,N\n{d}|BRK/B|5|0|9|Q\n{d}|ZZZ|1|0|2|Q\n"

    def handler(req):
        ymd = re.search(r"CNMSshvol(\d{8})", req.url.path).group(1)
        if ymd == "20260930":
            return httpx.Response(403, text="AccessDenied")
        return httpx.Response(200, text=text.format(d=ymd), headers={"last-modified": "Wed, 30 Sep 2026 21:18:34 GMT"})

    rep = ph.fetch_finra_cnms(archive, first="2026-09-01", last="2026-09-30", client=_client(handler), min_interval=0)
    name = "finra-regsho-cnms-2026-09"
    assert rep[name]["absent"] == ["2026-09-30"] and rep[name]["failed"] == []
    rows = _rows(archive, name)
    sv = [r for r in rows if r["kind"] == "short-volume"]
    assert {r["value"]["symbol"] for r in sv} == {"AAPL", "BRK/B"}
    assert sv[0]["available_at"] == "2026-09-01T23:59:59+00:00" and sv[0]["value"]["short_volume"] == 10.5
    fd = [r for r in rows if r["kind"] == "file-day"]
    assert fd[0]["value"]["backfilled"] is True and fd[-1]["value"]["status"] == "absent"   # LM 09-30 is > 2 days after 09-01
    assert "complete" in archive.get(name).tags                                        # absent day is 16 days old: settled
    rep2 = ph.fetch_finra_cnms(archive, first="2026-09-01", last="2026-09-30", client=_client(_forbid), min_interval=0)
    assert rep2[name] == {"skipped": "stored"}


def test_cnms_requires_universe(archive):
    rep = ph.fetch_finra_cnms(archive, first="2026-09-01", last="2026-09-02", client=_client(_forbid), min_interval=0)
    assert "no universe" in rep["_error"]


# ===================================================================================================== SEC ==

SUB_AAPL = {"cik": "0000320193", "name": "Apple Inc.", "sic": "3571", "sicDescription": "Electronic Computers", "tickers": ["AAPL"],
            "exchanges": ["Nasdaq"], "formerNames": [], "filings": {
                "recent": {"accessionNumber": ["0000320193-25-000079", "0000320193-25-000080"], "filingDate": ["2025-10-31", "2025-11-01"],
                           "reportDate": ["2025-09-27", ""], "acceptanceDateTime": ["2025-10-31T14:01:26.000Z", "2025-11-01T10:00:00.000Z"],
                           "form": ["10-K", "4"], "isXBRL": [1, 0], "isInlineXBRL": [1, 0], "primaryDocument": ["a.htm", "b.xml"]},
                "files": [{"name": "CIK0000320193-submissions-001.json", "filingFrom": "1994-01-26", "filingTo": "2015-09-15"}]}}
SUB_PAGE = {"accessionNumber": ["0001193125-10-238044"], "filingDate": ["2010-10-27"], "reportDate": ["2010-09-25"],
            "acceptanceDateTime": ["2010-10-27T16:47:00.000Z"], "form": ["10-K"], "isXBRL": [1], "isInlineXBRL": [0], "primaryDocument": ["d.htm"]}
FACTS_AAPL = {"facts": {
    "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2025-10-17", "val": 14776353000, "accn": "0000320193-25-000079", "fy": 2025, "fp": "FY", "form": "10-K", "filed": "2025-10-31"},
        {"end": "2025-07-18", "val": 14840390000, "accn": "0000320193-25-000073", "fy": 2025, "fp": "Q3", "form": "10-Q", "filed": "2025-08-01"}]}}},
    "us-gaap": {"Assets": {"units": {"USD": [
        {"end": "2025-09-27", "val": 359241000000, "accn": "0000320193-25-000079", "fy": 2025, "fp": "FY", "form": "10-K", "filed": "2025-10-31"},
        {"end": "2025-06-28", "val": 331495000000, "accn": "0000320193-25-000073", "fy": 2025, "fp": "Q3", "form": "10-Q", "filed": "2025-08-01"}]}},
                "AccountsPayableCurrent": {"units": {"USD": [{"end": "2025-09-27", "val": 1, "accn": "x", "form": "10-K", "filed": "2025-10-31"}]}}}}}


def test_sec_buckets_acceptance_and_resume(archive):
    calls = []

    def handler(req):
        calls.append(req.url.path)
        assert req.headers["user-agent"] == "Mandel research mandel-research@example.org"
        p = req.url.path
        if p.endswith("CIK0000320193-submissions-001.json"):
            return httpx.Response(200, json=SUB_PAGE)
        if p.endswith("submissions/CIK0000320193.json"):
            return httpx.Response(200, json=SUB_AAPL)
        if p.endswith("companyfacts/CIK0000320193.json"):
            return httpx.Response(200, json=FACTS_AAPL)
        if "0000320194" in p:
            return httpx.Response(404, json={"error": "not found"})
        if "0000320195" in p:
            return httpx.Response(500, text="boom")
        return httpx.Response(404)

    rep = ph.fetch_sec_submissions(archive, ciks=[320193, 320194, 320195], client=_client(handler), min_interval=0, retries=1)
    name = "sec-submissions-b006"
    rows = _rows(archive, name)
    fil = {r["value"]["accn"]: r for r in rows if r["kind"] == "filing"}
    assert set(fil) == {"0000320193-25-000079", "0001193125-10-238044"}                # XBRL only; older page read
    # JSON acceptance 14:01Z is before the filing-date bound (22:00 ET = 02:00Z next day): it is kept
    assert fil["0000320193-25-000079"]["available_at"] == "2025-10-31T14:01:26+00:00"
    comp = [r for r in rows if r["kind"] == "company"][0]
    assert comp["value"]["sicDescription"] == "Electronic Computers"
    cov = [r for r in rows if r["kind"] == "coverage"][0]["value"]["status"]
    assert cov == {"320193": "ok", "320194": "404", "320195": None}
    assert "partial" in archive.get(name).tags                                         # the 500 CIK is retried next run
    calls.clear()
    ph.fetch_sec_submissions(archive, ciks=[320193, 320194, 320195], client=_client(handler), min_interval=0, retries=1)
    assert calls == ["/submissions/CIK0000320195.json"]
    ph.fetch_sec_companyfacts(archive, ciks=[320193], client=_client(handler), min_interval=0)
    facts = [r for r in _rows(archive, "sec-companyfacts-b006") if r["kind"] == "fact"]
    got = {(r["value"]["tag"], r["value"]["form"]) for r in facts}
    assert got == {("EntityCommonStockSharesOutstanding", "10-K"), ("EntityCommonStockSharesOutstanding", "10-Q"), ("Assets", "10-K")}
    k = [r for r in facts if r["value"]["tag"] == "Assets"][0]
    assert k["available_at"] == "2025-10-31T14:01:26+00:00"                           # the accession's acceptance from submissions
    q = [r for r in facts if r["value"]["form"] == "10-Q"][0]
    assert q["available_at"] == "2025-08-02T02:00:00+00:00"                           # accession unknown: filed 22:00 ET


def test_sec_tickers_lookup_and_universe(archive):
    tick = {"fields": ["cik", "name", "ticker", "exchange"], "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"], [9, "OTC Co", "OTCX", "OTC"]]}
    lookup = "CELGENE CORP /DE/:0000816284:\nAPPLE INC:0000320193:\nbad line\n"

    def handler(req):
        return httpx.Response(200, json=tick, headers={"last-modified": "Thu, 15 Oct 2026 13:39:20 GMT"}) if "tickers" in req.url.path \
            else httpx.Response(200, text=lookup)

    ph.fetch_sec_company_tickers(archive, client=_client(handler), min_interval=0)
    ph.fetch_sec_cik_lookup(archive, client=_client(handler), min_interval=0)
    assert archive.get("sec-company-tickers").in_git is True and archive.get("sec-cik-lookup").in_git is False
    assert [r["value"]["cik"] for r in _rows(archive, "sec-cik-lookup")] == [816284, 320193]
    archive.store("wikipedia-sp500-changes", "data", [{"key": "x", "value": {"removed_security": "Celgene Corporation"}}], recipe="t")
    ciks, prov = ph.sec_universe(archive)
    assert ciks == [320193, 816284] and prov["delisted_matched_ciks"] == 1
    assert ph.normalize_company_name("Celgene Corp /DE/") == ph.normalize_company_name("CELGENE CORPORATION") == "CELGENE"


# ============================================================================================== StockTwits ==

class Stream:
    """Global message ids rising with time: SPY every 5 minutes, BTC.X every 20 minutes, from T0."""

    def __init__(self, t0, hours=40):
        self.msgs = []
        mid = 700_000_000
        t = t0
        while t < t0 + timedelta(hours=hours):
            mid += 7
            syms = ["SPY"] + (["BTC.X"] if t.minute % 20 == 0 else [])
            self.msgs.append({"id": mid, "created_at": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "symbols": [{"symbol": s} for s in syms],
                              "entities": {"sentiment": {"basic": "Bullish" if mid % 2 else None}}, "user": {"id": 1, "followers": 3},
                              "body": "hi", "likes": {"total": 0}})
            t += timedelta(minutes=5)
        self.calls = 0
        self.fail_429 = 0

    def handler(self, req):
        self.calls += 1
        if self.fail_429:
            self.fail_429 -= 1
            return httpx.Response(429, headers={"retry-after": "2"}, json={"errors": "rate"})
        sym = req.url.path.split("/")[-1][:-5]
        mx = int(req.url.params.get("max", 10 ** 12))
        pool = [m for m in reversed(self.msgs) if m["id"] < mx and any(s["symbol"] == sym for s in m["symbols"])]
        page = pool[:30]
        return httpx.Response(200, json={"messages": page, "cursor": {"more": len(pool) > 30, "max": page[-1]["id"] if page else None}})


def test_find_anchor_and_window(monkeypatch):
    monkeypatch.setattr(ph, "ST_SEED", ())
    st = Stream(datetime(2026, 10, 13, 12, 0, tzinfo=UTC))
    c, th = _client(st.handler), ph.Throttle(0)
    known = [(700_000_000, "2026-10-13T11:59:00+00:00")]
    target = "2026-10-14T13:00:00+00:00"
    aid, info = ph.find_anchor(target, c, th, known)
    first_after = min(m["id"] for m in st.msgs if m["created_at"] >= "2026-10-14T13:00:00Z")
    assert aid == first_after and info["calls"] <= 8
    msgs, winfo = ph.st_window("BTC.X", "2026-10-13T20:00:00+00:00", aid, c, th, end=target)
    want = [m for m in st.msgs if "2026-10-13T20:00:00Z" <= m["created_at"] < "2026-10-14T13:00:00Z" and len(m["symbols"]) == 2]
    assert winfo["complete"] and sorted(m["id"] for m in msgs) == sorted(m["id"] for m in want)


def test_stocktwits_preopen_and_intensity(archive, monkeypatch):
    monkeypatch.setattr(ph, "ST_SEED", ())
    st = Stream(datetime(2026, 10, 13, 12, 0, tzinfo=UTC))
    st.fail_429 = 1                                                                   # first call is rate limited, then retried
    rep = ph.fetch_stocktwits_preopen(archive, symbols=["SPY", "BTC.X"], first="2026-10-14", last="2026-10-14",
                                      client=_client(st.handler), min_interval=0)
    name = "stocktwits-preopen-2026-W42"
    rows = _rows(archive, name)
    win = {r["value"]["stream"]: r for r in rows if r["kind"] == "window"}
    assert win["SPY"]["value"]["window_start"] == "2026-10-13T20:00:00+00:00" and win["SPY"]["value"]["window_end"] == "2026-10-14T13:00:00+00:00"
    assert win["SPY"]["value"]["messages"] == 17 * 12 and win["SPY"]["value"]["complete"] is True
    assert win["BTC.X"]["value"]["messages"] == 17 * 3
    msg = [r for r in rows if r["kind"] == "message"][0]
    assert msg["available_at"] == msg["observed_at"] and "body" not in msg["value"] and msg["value"]["body_len"] == 2
    assert "partial" in archive.get(name).tags                                        # the week is not over
    assert any(r["kind"] == "anchor" for r in _rows(archive, "stocktwits-anchors"))
    n = st.calls
    rep = ph.fetch_stocktwits_preopen(archive, symbols=["SPY", "BTC.X"], first="2026-10-14", last="2026-10-14",
                                      client=_client(st.handler), min_interval=0)
    assert st.calls == n                                                              # day stored complete: nothing refetched
    ph.fetch_stocktwits_intensity(archive, symbols=["SPY"], times=["10:00"], first="2026-10-14", last="2026-10-14",
                                  client=_client(st.handler), min_interval=0)
    s = _rows(archive, "stocktwits-intensity-2026-W42")
    assert len(s) == 1 and s[0]["available_at"] == "2026-10-14T14:00:00+00:00"
    v = s[0]["value"]
    assert v["n"] == 30 and all(t < "2026-10-14T14:00:00Z" for t in v["created_at"]) and abs(v["per_hour"] - 12.4) < 0.5


# ================================================================================================ Deribit ==

def test_deribit_near_trades(archive, monkeypatch):
    monkeypatch.setattr(ph, "_now", lambda: datetime(2024, 3, 3, 12, 0, tzinfo=UTC))
    base = int(datetime(2024, 3, 1, tzinfo=UTC).timestamp() * 1000)
    trades = []
    for i in range(30):
        ts = base + i * 3_000_000                                                    # 50 minutes apart over ~25 hours
        inst = "BTC-2MAR24-60000-C" if i % 3 else "BTC-29MAR24-60000-C"              # 29MAR24 is > 8 days out
        trades.append({"trade_id": str(i), "timestamp": ts, "instrument_name": inst, "price": 0.01, "mark_price": 0.01, "iv": 60,
                       "index_price": 61000, "amount": 1, "direction": "buy"})

    def handler(req):
        q = req.url.params
        s, e = int(q["start_timestamp"]), int(q["end_timestamp"])
        page = [t for t in trades if s <= t["timestamp"] <= e][: int(q["count"])]
        return httpx.Response(200, json={"result": {"trades": page, "has_more": False}})

    rep = ph.fetch_deribit_near_trades(archive, first="2024-03-01", last="2024-03-02", client=_client(handler), min_interval=0)
    name = "deribit-option-trades-near-BTC-2024-03"
    rows = _rows(archive, name)
    kept = [r for r in rows if r["kind"] == "option-trade"]
    assert kept and all(r["value"]["expiry"] == "2024-03-02" for r in kept)
    days = [r["value"]["day"] for r in rows if r["kind"] == "sample-day"]
    assert days == ["2024-03-01", "2024-03-02"] and "partial" in archive.get(name).tags
    assert archive.get(name).in_git is False
    assert ph.gitignore_line(name) == "mandel/archive/data/deribit-option-trades-near-*.jsonl.gz"


# ============================================================================================ plan, licences ==

def test_dry_run_makes_no_request(archive, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a dry run opened a client")
    monkeypatch.setattr(httpx, "Client", boom)
    rep = ph.fetch_all_misc(archive, dry_run=True)
    assert rep["_totals"]["bundles"] > 200 and rep["_totals"]["calls"] > 10_000
    for p in rep["_plan"]:
        assert set(p) >= {"name", "function", "theories", "in_git", "licence", "gitignore_line", "calls", "rows", "gz_mb", "minutes",
                          "available_at_rule"}
        assert (p["gitignore_line"] == "") == p["in_git"]
        if not p["in_git"]:
            assert p["gitignore_line"].startswith("mandel/archive/data/") and p["gitignore_line"].endswith(".jsonl.gz")
    assert not any(s.get("_error") for s in rep.values() if isinstance(s, dict))


def test_licence_decisions_and_gitignore_lines():
    in_git = {f[0] for f in ph.FAMILIES.values() if f[3]}
    assert in_git == {"cftc-cot-*", "treasury-auctions", "wikipedia-sp500-constituents", "wikipedia-sp500-changes", "sec-company-tickers"}
    lines = ph.gitignore_lines()
    assert "mandel/archive/data/stocktwits-preopen-*.jsonl.gz" in lines and "mandel/archive/data/spdr-*-archive.jsonl.gz" in lines
    assert ph.gitignore_line("finra-short-interest-2026-09-30") == "mandel/archive/data/finra-short-interest-*.jsonl.gz"
    assert ph.gitignore_line("sec-companyfacts-b006") == "mandel/archive/data/sec-companyfacts-*.jsonl.gz"
    assert ph.gitignore_line("cftc-cot-disagg-fo-088691") is None and ph.gitignore_line("unrelated") is None


def test_main_dry_run(capsys, tmp_path, monkeypatch):
    assert ph.main(["cftc", "--dry-run", "--preview", str(tmp_path / "p")]) == 0
    out = capsys.readouterr().out
    assert "cftc-cot-disagg-fo-088691" in out and "mandel/archive/data/stocktwits-preopen-*.jsonl.gz" in out


def test_cnms_recent_absent_day_is_partial(archive):
    archive.store("fja-sp500-components", "data", [{"key": "d", "value": {"date": "2026-08-18", "tickers": ["AAPL"]}}], recipe="t")
    text = "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n{d}|AAPL|1|0|2|Q\n"

    def handler(req):
        ymd = re.search(r"CNMSshvol(\d{8})", req.url.path).group(1)
        return httpx.Response(403) if ymd == "20261015" else httpx.Response(200, text=text.format(d=ymd))

    rep = ph.fetch_finra_cnms(archive, first="2026-10-01", last="2026-10-15", client=_client(handler), min_interval=0)
    assert rep["finra-regsho-cnms-2026-10"]["absent"] == ["2026-10-15"]
    assert "partial" in archive.get("finra-regsho-cnms-2026-10").tags                 # month not over, absent day is fresh


def test_sec_universe_skips_funds_and_otc(archive):
    archive.store("sec-company-tickers", "data", [{"key": "1", "value": {"cik": 1, "ticker": "AAA", "exchange": "NYSE"}}], recipe="t")
    archive.store("sec-cik-lookup", "data", [{"key": "a", "value": {"name": "OLDCO INC", "cik": 5}},
                                             {"key": "b", "value": {"name": "BIG INDEX ETF", "cik": 6}},
                                             {"key": "c", "value": {"name": "OTCONLY CORP", "cik": 7}}], recipe="t")
    archive.store("finra-short-interest-2020-01-15", "data", [
        {"key": "x", "value": {"symbolCode": "OLD", "issueName": "OldCo, Inc. Common Stock", "marketClassCode": "NNM"}},
        {"key": "y", "value": {"symbolCode": "BIX", "issueName": "Big Index ETF", "marketClassCode": "NYSE"}},
        {"key": "z", "value": {"symbolCode": "OTCO", "issueName": "OTConly Corp", "marketClassCode": "OTC"}},
        {"key": "w", "value": {"symbolCode": "AAA", "issueName": "Current Co", "marketClassCode": "NYSE"}}],
        recipe="t", tags=["short-interest"])
    ciks, prov = ph.sec_universe(archive)
    assert ciks == [1, 5] and prov["delisted_names"] == 1


def test_main_sources_option(capsys, tmp_path):
    assert ph.main(["all", "--dry-run", "--sources", "treasury,cftc", "--preview", str(tmp_path / "p")]) == 0
    out = capsys.readouterr().out
    assert "treasury-auctions" in out and "stocktwits-preopen" not in out.split("mandel/archive/data/")[0]
    with pytest.raises(SystemExit):
        ph.main(["all", "--dry-run", "--sources", "nope"])


# ================================================================ checker fixes (COT store, writers, plans) ==

def test_fetch_cftc_disagg_backcast_stored(archive):
    days = ["2006-06-13", "2009-08-25", "2009-09-01"]

    def handler(req):
        q = {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}
        return httpx.Response(200, json=[_cot_row(d, BULK) for d in days] if q["$offset"] == "0" else [])

    rep = ph.fetch_cftc_cot(archive, series=[("disagg-fo", "088691")], client=_client(handler), min_interval=0)
    name = "cftc-cot-disagg-fo-088691"
    assert rep[name]["pit"] == {"schedule": 1, "backcast": 2} and rep[name]["raised_to_observed"] == 0
    rows = _rows(archive, name)
    assert [r["available_at"] for r in rows] == ["2009-10-20T23:59:59+00:00", "2009-10-20T23:59:59+00:00", "2009-09-04T19:30:00+00:00"]
    assert rows[0]["value"]["release_rule"] == "2006-06-16T19:30:00+00:00" and rows[0]["value"]["pit"] == "backcast"
    rec = archive.get(name).recipe
    assert "2009-10-20" in rec and "backcast 2" in rec and "never before observed_at" in rec


def _hold_lock(root, name):
    import fcntl
    root.mkdir(parents=True, exist_ok=True)
    fh = open(root / name, "a+")
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fh


def test_run_lock_refuses_a_second_writer(archive, tmp_path):
    with ph.run_lock(archive) as paths:
        assert [p.name for p in paths] == ["public_history.run.lock", "crypto_history.run.lock"]
        other = Archive(root=archive.root, ledger=archive.ledger)
        with pytest.raises(RuntimeError, match="another writer"):
            with ph.run_lock(other):
                pass
        with pytest.raises(RuntimeError):                                             # fetch_all_misc storing run refused
            ph.fetch_all_misc(other, sources=["treasury"])
    with ph.run_lock(archive):                                                        # released on exit
        pass
    # a crypto_history run holding its own lock also blocks this module (and the lock is released after the refusal)
    fh = _hold_lock(archive.root, "crypto_history.run.lock")
    try:
        with pytest.raises(RuntimeError, match="crypto_history.run.lock"):
            ph.fetch_all_misc(archive, sources=["treasury"])
    finally:
        fh.close()
    with ph.run_lock(archive):
        pass
    assert ph.fetch_all_misc(archive, dry_run=True, sources=["treasury"])["_totals"]["bundles"] == 1     # dry runs take no lock


def test_index_check_reports_a_stale_concurrent_writer(tmp_path):
    root = tmp_path / "a"
    st = Archive(root=root, ledger=Ledger(tmp_path / "l.jsonl"))                     # the checker's reproduction
    before = {e.name: e.sha256 for e in st.entries()}
    st.store("stocktwits-preopen-2025-W44", "data", [{"value": {"day": "2025-10-27"}}], recipe="r", tags=["partial"], in_git=False)
    other = Archive(root=root, ledger=Ledger(tmp_path / "l.jsonl"))
    other.store("finra-short-interest-2017-12-29", "data", [{"v": 1}], recipe="r", tags=["complete"], in_git=False)
    st.store("stocktwits-preopen-2025-W44", "data", [{"value": {"day": d}} for d in ("2025-10-27", "2025-10-28")], recipe="r",
             tags=["partial"], in_git=False)
    other.store("finra-short-interest-2018-01-12", "data", [{"v": 2}], recipe="r", tags=["complete"], in_git=False)
    chk = ph.index_check(st, before)
    # Archive._reload_index now lets the INDEX on disk win under the store lock, so the interleaving that used to write back
    # the stale 1-row entry leaves the INDEX in agreement with the files (the checker's reproduction is the regression test)
    assert chk["ok"] is True, chk
    import json as _json
    idx = _json.loads((root / "INDEX.json").read_text())["bundles"]
    idx["stocktwits-preopen-2025-W44"]["rows"] = 1                                # a stale entry written by hand is still caught
    (root / "INDEX.json").write_text(_json.dumps({"bundles": idx}))
    chk = ph.index_check(st, before)                                             # this process's view vs the INDEX on disk
    assert chk["ok"] is False and chk["mismatched"][0]["bundle"] == "stocktwits-preopen-2025-W44"
    assert chk["mismatched"][0]["index_rows"] == 1 and chk["mismatched"][0]["stored_rows"] == 2
    idx["stocktwits-preopen-2025-W44"]["rows"] = 2
    (root / "INDEX.json").write_text(_json.dumps({"bundles": idx}))
    fresh = Archive(root=root, ledger=Ledger(tmp_path / "l.jsonl"))
    assert ph.index_check(fresh, {}) == {"ok": True, "bundles": 3}                   # a fresh view (all 3 bundles) agrees with disk


def test_fetch_all_misc_reports_index_check(archive):
    rep = ph.fetch_all_misc(archive, sources=["treasury"], limit=0)                    # limit 0: no request, no store
    assert rep["_index_check"] == {"ok": True, "bundles": 0}


def test_main_single_source_takes_the_lock(tmp_path, capsys):
    root = tmp_path / "run"
    store = ph._root_archive(root)
    fh = _hold_lock(store.root, "public_history.run.lock")
    try:
        assert ph.main(["treasury", "--root", str(root)]) == 2                      # refused before any request
        assert ph.main(["all", "--sources", "cftc", "--root", str(root)]) == 2
        assert ph.main(["treasury", "--dry-run", "--root", str(root)]) == 0         # a plan needs no lock
    finally:
        fh.close()
    assert "refused: another writer holds" in capsys.readouterr().err


def test_merge_archive_from_a_separate_root(tmp_path, archive):
    src = ph._root_archive(tmp_path / "st")
    week = [{"key": f"SPY:{i}", "value": {"day": "2025-10-27", "stream": "SPY"}} for i in range(3)]
    src.store("stocktwits-preopen-2025-W44", "data", week, recipe="st recipe", tags=["complete", "T-414"], schema="s", in_git=False)
    src.store("stocktwits-anchors", "data", [{"value": {"target": "2025-10-27T13:00:00+00:00", "id": 5}}], recipe="a", in_git=False)
    archive.store("stocktwits-anchors", "data", [{"value": {"target": "2025-10-20T13:00:00+00:00", "id": 3}}], recipe="a", in_git=False)
    src.store("unrelated-bundle", "data", [{"v": 1}], recipe="x")
    rep = ph.merge_archive(tmp_path / "st", archive)
    e = archive.get("stocktwits-preopen-2025-W44")
    assert e.rows == 3 and e.recipe == "st recipe" and e.in_git is False and e.tags == ["T-414", "complete"] and archive.verify(e.name)
    assert [r["value"]["id"] for r in _rows(archive, "stocktwits-anchors")] == [3, 5]               # union by target
    assert "unrelated-bundle" not in rep and rep["_index_check"]["ok"]
    rep = ph.merge_archive(tmp_path / "st", archive)
    assert rep["stocktwits-preopen-2025-W44"] == {"skipped": "identical"}
    archive.store("stocktwits-preopen-2025-W44", "data", week + week[:1], recipe="newer", tags=["complete"], in_git=False)
    rep = ph.merge_archive(tmp_path / "st", archive)
    assert "conflict" in rep["stocktwits-preopen-2025-W44"] and archive.get("stocktwits-preopen-2025-W44").rows == 4
    with pytest.raises(FileNotFoundError):
        ph.merge_archive(tmp_path / "nothing-here", archive)


def test_finra_calendar_and_dry_run_counts_stored_dates(archive, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a dry run opened a client")
    monkeypatch.setattr(httpx, "Client", boom)
    assert ph.finra_si_calendar(today="2018-03-01") == ["2017-12-29", "2018-01-12", "2018-01-31", "2018-02-15"]   # MLK -> 01-12
    cal = ph.finra_si_calendar(today="2026-10-15")
    assert len(cal) == 211 and cal[-1] == "2026-09-30" and "2026-03-13" in cal                  # 2026-03-15 is a Sunday
    for d in ("2017-12-29", "2018-01-12", "2026-09-30"):                                         # regression: stored dates count
        archive.store(f"finra-short-interest-{d}", "data", [{"v": 1}], recipe="t", tags=["complete", "short-interest"], in_git=False)
    rep = ph.fetch_finra_short_interest(archive, dry_run=True)
    assert rep["_dry_run"] == {"dates": 211, "already_stored": 3, "to_fetch": 208}
    stored = [p for p in rep["_plan"] if p["already_stored"]]
    assert {p["name"] for p in stored} == {f"finra-short-interest-{d}" for d in ("2017-12-29", "2018-01-12", "2026-09-30")}
    assert all(p["calls"] == 0 for p in stored) and sum(p["calls"] for p in rep["_plan"]) < 211 * 5
    assert rep["finra-short-interest-2018-01-12"] == {"skipped": "stored"}
    assert len([p for p in ph.fetch_finra_short_interest(archive, dry_run=True, limit=1)["_plan"] if not p["already_stored"]]) == 1


def test_stocktwits_plan_uses_the_remeasured_estimates(archive):
    rep = ph.fetch_stocktwits_preopen(archive, first="2026-10-13", last="2026-10-13", dry_run=True)       # a Tuesday
    p = rep["_plan"][0]
    assert sum(ph.ST_PAGES_EST.values()) == 167 and ph.ST_ANCHOR_CALLS == 9
    assert p["calls"] == 167 + 9 and p["minutes"] == round(176 * 1.95 / 60, 2)
    mon = ph.fetch_stocktwits_preopen(archive, first="2026-10-12", last="2026-10-12", dry_run=True)["_plan"][0]
    assert mon["calls"] == math.ceil(167 * ph.ST_MONDAY_FACTOR + 9)
    full = ph.fetch_stocktwits_preopen(archive, dry_run=True)["_plan"]
    assert 50_000 < sum(x["calls"] for x in full) < 65_000 and 1_650 < sum(x["minutes"] for x in full) < 2_100   # ~30 h
