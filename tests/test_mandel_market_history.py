"""Yahoo/FRED/ALFRED market-history fetchers: row parity with the archived conventions (collect_history, fetch_hourly,
fred-DTB3), events, skip-stored and rebuild, 404/429 handling and the query2 fallback, in-progress bars, FRED licences,
ALFRED real-time periods and release times, dry-run plans and .gitignore lines. Mocked HTTP only, no network."""

import io
import json
import time
import zipfile
from urllib.parse import parse_qs

import httpx
import pytest

from mandel.archive import ARCHIVE_ROOT, Archive
from mandel.data import market_history as m
from mandel.data import options as options_mod
from mandel.data import options_misc
from mandel.data import social, unlocks
from mandel.data.store import ObservationStore
from mandel.ledger import Ledger
from mandel.paths import MANDEL_ROOT

DAY = 86400
T0 = 1_600_000_000 - (1_600_000_000 % DAY) + 48600          # 2020-09-13 13:30 UTC: a session-start bar time


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    waits = []
    monkeypatch.setattr(options_misc, "_sleep", lambda s: waits.append(s))
    monkeypatch.setattr(m, "_sleep", lambda s: waits.append(s))
    return waits


def _arch(tmp_path, sub="a") -> Archive:
    return Archive(root=tmp_path / sub, ledger=Ledger(tmp_path / sub / "ledger.jsonl"))


def chart(sym, ts, closes=None, adj=True, events=None, gran="1d", first=None):
    n = len(ts)
    closes = closes if closes is not None else [100.0 + i for i in range(n)]
    q = {"open": [c - 0.5 if c is not None else None for c in closes], "high": [c + 1 if c is not None else None for c in closes],
         "low": [c - 1 if c is not None else None for c in closes], "close": closes, "volume": [1000 + i for i in range(n)]}
    ind = {"quote": [q]}
    if adj:
        ind["adjclose"] = [{"adjclose": [c * 0.9 if c is not None else None for c in closes]}]
    res = {"meta": {"symbol": sym, "currency": "USD", "exchangeName": "PCX", "instrumentType": "ETF", "firstTradeDate": first or (ts[0] if ts else 0),
                    "exchangeTimezoneName": "America/New_York", "dataGranularity": gran}, "timestamp": ts, "indicators": ind}
    if events:
        res["events"] = events
    return {"chart": {"result": [res], "error": None}}


class FakeNet:
    """Routes Yahoo (query1/query2), FRED and ALFRED requests to canned answers and records every request."""

    def __init__(self):
        self.calls = []
        self.yahoo = {}            # (host, sym) or sym -> list of responses (last one repeats) or a callable(request)
        self.fred_csv = {}
        self.fred_page = {}
        self.alfred_page = {}
        self.alfred_zip = {}
        self.posts = []
        self.other = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        host, path = request.url.host, request.url.path
        if host.endswith("finance.yahoo.com"):
            sym = path.rsplit("/", 1)[-1]
            seq = self.yahoo.get((host, sym), self.yahoo.get(sym))
            if seq is None:
                return httpx.Response(404, json={"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found, symbol may be delisted"}}})
            if callable(seq):
                return seq(request)
            return seq.pop(0) if len(seq) > 1 else seq[0]
        if host == "fred.stlouisfed.org" and path == "/graph/fredgraph.csv":
            sid = request.url.params["id"]
            return httpx.Response(200, text=self.fred_csv[sid]) if sid in self.fred_csv else httpx.Response(404, text="<html>no</html>")
        if host == "fred.stlouisfed.org" and path.startswith("/series/"):
            sid = path.rsplit("/", 1)[-1]
            v = self.fred_page.get(sid)
            return v if isinstance(v, httpx.Response) else httpx.Response(200, text=v) if v else httpx.Response(404, text="")
        if host == "alfred.stlouisfed.org":
            sid = request.url.params["seid"]
            if request.method == "POST":
                self.posts.append(parse_qs(request.content.decode()))
                return httpx.Response(200, content=self.alfred_zip[sid], headers={"content-type": "application/zip"})
            return httpx.Response(200, text=self.alfred_page[sid])
        if host == "api.alternative.me":
            return httpx.Response(200, json={"data": []})
        raise AssertionError(f"unexpected request {request.url}")

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def ok(js):
    return httpx.Response(200, json=js)


# ----------------------------------------------------------------------------------------- naming, licences --

def test_names_and_gitignore_lines_follow_the_archive_path_pattern(tmp_path):
    assert m.history_bundle("^GSPC") == "daily-history--GSPC" and m.history_bundle("GC=F") == "daily-history-GC-F"
    assert m.hourly_bundle("CAD=X") == "hourly-CAD-X" and m.events_bundle("BRK-B") == "daily-events-BRK-B"
    assert m.ARCHIVE_DATA_PREFIX == str(ARCHIVE_ROOT.relative_to(MANDEL_ROOT.parent)) + "/data/"
    assert m.gitignore_line("daily-history-BZ=F") == "mandel/archive/data/daily-history-BZ-F.jsonl.gz"
    a = _arch(tmp_path)
    e = a.store("daily-history-EEM", "data", [{"x": 1}], recipe="r", in_git=False)
    assert ("mandel/archive/" + e.path).endswith(m.gitignore_line("daily-history-EEM")[len("mandel/archive/"):])
    gi = (MANDEL_ROOT.parent / ".gitignore").read_text()
    assert m.gitignore_line("cboe-BXM-history") in gi                  # same pattern as the existing local-only lines


def test_symbol_spelling_and_symbol_files(tmp_path):
    assert m.yahoo_symbol("brk.b") == "BRK-B" and m.yahoo_symbol("BF.B") == "BF-B"
    assert m.yahoo_symbol("RY.TO") == "RY.TO" and m.yahoo_symbol("CAD=X") == "CAD=X" and m.yahoo_symbol("^VIX") == "^VIX"
    f = tmp_path / "s.csv"
    f.write_text("Symbol,Name\nBRK.B,Berkshire\nAAPL,Apple\nAAPL,dup\n\n")
    assert m.read_symbols(str(f)) == ["BRK-B", "AAPL"]


def test_symbols_from_another_groups_bundle(tmp_path):
    a = _arch(tmp_path)
    a.store("sp500-constituents", "data", [{"key": "BRK.B", "value": {"symbol": "BRK.B"}}, {"key": "AAPL", "value": {"symbol": "AAPL"}},
                                           {"key": "AAPL", "value": {"symbol": "AAPL"}}, {"key": "", "value": {}}], recipe="r")
    assert m.symbols_from_bundle(a, "sp500-constituents", "symbol") == ["BRK-B", "AAPL"]
    assert m.symbols_from_bundle(a, "sp500-constituents") == ["BRK-B", "AAPL"]
    assert m.symbols_from_bundle(a, "absent") == [] and m.symbols_from_bundle(None, "absent") == []


def test_theory_needs_cover_the_group_and_hold_the_triage_symbols():
    group = {"T-309", "T-325", "T-370", "T-405", "T-432", "T-458", "T-468", "T-476", "T-381", "T-398", "T-419", "T-433", "T-470", "T-479",
             "T-319", "T-328", "T-373", "T-420", "T-462", "T-471", "T-313", "T-321", "T-330", "T-365", "T-374", "T-472", "T-482", "T-322",
             "T-366", "T-375", "T-393", "T-414", "T-451", "T-473", "T-483", "T-323", "T-334", "T-377", "T-394", "T-404", "T-415", "T-430",
             "T-467", "T-474"}
    assert group <= set(m.THEORY_NEEDS)
    for s in ["EEM", "SSO", "UVXY", "PL=F", "BZ=F", "DBA", "EZA", "SGOV", "STETH-USD", "CBETH-USD", "USDT-USD", "PHYS", "TLH", "LBRDK", "IWN"]:
        assert s in m.DAILY_SYMBOLS
    for s in ["RY.TO", "CAD=X", "IBIT", "SOL-USD", "XLK"]:
        assert s in m.HOURLY_SYMBOLS
    for s in ["DGS20", "DGS5", "DFII10", "BAA10Y", "USREC", "UMCSENT", "BOGZ1FA653064100Q"] + m.IRLTLT01:
        assert s in m.FRED_SERIES
    assert len(set(m.ETF60_EXTRA)) + 26 >= 60                        # T-420/T-462: declared list of at least 60 ETFs
    assert not set(m.DAILY_SYMBOLS) & {"SPY", "QQQ", "GLD", "TLT", "XLB", "DBC", "BTC-USD"}     # archived already


# ------------------------------------------------------------------------------------------- daily parity --

def test_parse_daily_matches_social_yahoo_history():
    net = FakeNet()
    ts = [T0 + i * DAY for i in range(6)]
    js = chart("SPY", ts, closes=[1.0, None, 3.0, 4.0, 5.0, 6.0])
    js["chart"]["result"][0]["indicators"]["adjclose"][0]["adjclose"][3] = None      # a bar without adjclose
    net.yahoo["SPY"] = [ok(js)]
    with net.client() as c:
        theirs = social.yahoo_history("SPY", c, m.Throttle(0))
    assert m.parse_daily(js["chart"]["result"][0]) == theirs and len(theirs) == 5 and "adjclose" not in theirs[2]


def test_history_rows_tags_and_schema_match_collect_history(tmp_path, monkeypatch):
    ts = [T0 + i * DAY for i in range(8)]
    net = FakeNet()
    net.yahoo["SPY"] = [ok(chart("SPY", ts, events={"dividends": {str(ts[2]): {"amount": 0.5, "date": ts[2]}}}))]
    old = _arch(tmp_path, "old")
    real = httpx.Client
    with monkeypatch.context() as mp:                        # collect_history builds its own httpx.Client()
        mp.setattr(social.httpx, "Client", lambda *a, **k: real(transport=httpx.MockTransport(net)))
        social.collect_history(ObservationStore(old), symbols=("SPY",))
    new = _arch(tmp_path, "new")
    with net.client() as c:
        rep = m.fetch_daily_histories(new, ["SPY"], min_interval=0, client=c)
    assert rep["daily-history-SPY"]["stored"]["in_git"] is False
    assert list(new.load("daily-history-SPY")) == list(old.load("daily-history-SPY"))
    eo, en = old.get("daily-history-SPY"), new.get("daily-history-SPY")
    assert en.tags == eo.tags and en.schema == eo.schema and en.schema == m.HISTORY_SCHEMA
    assert en.recipe.startswith(eo.recipe.split(" (available_at")[0])     # same endpoint and window, plus &events=div|split
    assert "events=div|split" in net.calls[-1].url.query.decode().replace("%7C", "|")


def test_events_bundle_rows(tmp_path):
    ts = [T0 + i * DAY for i in range(10)]
    ev = {"dividends": {str(ts[5]): {"amount": 0.25, "date": ts[5]}, str(ts[1]): {"amount": 0.2, "date": ts[1]}},
          "splits": {str(ts[3]): {"date": ts[3], "numerator": 1.0, "denominator": 6.0, "splitRatio": "1:6"}}}
    net = FakeNet()
    net.yahoo["UVXY"] = [ok(chart("UVXY", ts, events=ev))]
    a = _arch(tmp_path)
    with net.client() as c:
        rep = m.fetch_daily_histories(a, ["UVXY"], min_interval=0, client=c)
    assert rep["daily-events-UVXY"]["dividends"] == 2 and rep["daily-events-UVXY"]["splits"] == 1
    rows = list(a.load("daily-events-UVXY"))
    assert [r["kind"] for r in rows] == ["dividend", "split", "dividend"]
    assert rows[0]["available_at"] == rows[0]["observed_at"] == m.iso(ts[1]) and rows[0]["value"]["amount"] == 0.2
    assert rows[1]["value"]["ratio"] == "1:6" and rows[1]["value"]["ex_date"] == m.iso(ts[3])[:10]
    assert a.get("daily-events-UVXY").in_git is False and len(net.calls) == 1        # one call for bars and events


def test_events_bundle_written_even_without_events(tmp_path):
    net = FakeNet()
    net.yahoo["BZ=F"] = [ok(chart("BZ=F", [T0 + i * DAY for i in range(6)]))]
    a = _arch(tmp_path)
    with net.client() as c:
        m.fetch_daily_histories(a, ["BZ=F"], min_interval=0, client=c)
    assert a.get("daily-events-BZ-F").rows == 0 and a.get("daily-history-BZ-F").rows == 6


def test_in_progress_bar_is_not_stored(tmp_path):
    now = int(time.time())
    ts = [T0 + i * DAY for i in range(6)] + [now - 3600]            # today's bar: available_at = t + 24h is in the future
    net = FakeNet()
    net.yahoo["EEM"] = [ok(chart("EEM", ts))]
    a = _arch(tmp_path)
    with net.client() as c:
        m.fetch_daily_histories(a, ["EEM"], min_interval=0, client=c)
    rows = list(a.load("daily-history-EEM"))
    assert len(rows) == 6 and all(r["value"]["t"] < now - DAY for r in rows)


# ------------------------------------------------------------------------------ resumability and failures --

def test_skip_stored_and_rebuild_missing_local_file(tmp_path):
    net = FakeNet()
    net.yahoo["DBA"] = [ok(chart("DBA", [T0 + i * DAY for i in range(6)]))]
    a = _arch(tmp_path)
    with net.client() as c:
        m.fetch_daily_histories(a, ["DBA"], min_interval=0, client=c)
        n = len(net.calls)
        rep = m.fetch_daily_histories(a, ["DBA"], min_interval=0, client=c)
        assert len(net.calls) == n and rep["daily-history-DBA"] == {"skipped": "stored"}
        assert m.fetch_daily_histories(a, ["DBA"], dry_run=True)["_plan"] == []
        (a.root / "data" / "daily-history-DBA.jsonl.gz").unlink()             # INDEX entry kept, file gone (fresh clone)
        rep = m.fetch_daily_histories(a, ["DBA"], min_interval=0, client=c)
    assert len(net.calls) == n + 1 and rep["daily-history-DBA"]["stored"]["rows"] == 6


def test_delisted_404_is_final_and_not_stored(tmp_path):
    net = FakeNet()
    a = _arch(tmp_path)
    with net.client() as c:
        rep = m.fetch_daily_histories(a, ["CELG"], min_interval=0, client=c)
    assert "delisted" in rep["daily-history-CELG"]["error"] and len(net.calls) == 1    # no retry, no query2
    with pytest.raises(KeyError):
        a.get("daily-history-CELG")


def test_429_honours_retry_after_then_falls_back_to_query2(tmp_path, no_sleep):
    net = FakeNet()
    net.yahoo[("query1.finance.yahoo.com", "EWA")] = [httpx.Response(429, headers={"retry-after": "7"}, text="Too Many Requests")]
    net.yahoo[("query2.finance.yahoo.com", "EWA")] = [ok(chart("EWA", [T0 + i * DAY for i in range(6)]))]
    a = _arch(tmp_path)
    with net.client() as c:
        rep = m.fetch_daily_histories(a, ["EWA"], min_interval=0, client=c, retries=3, backoff=1.0)
    hosts = [r.url.host for r in net.calls]
    assert hosts == ["query1.finance.yahoo.com"] * 3 + ["query2.finance.yahoo.com"]
    assert sum(1 for w in no_sleep if w >= 7) == 3 and rep["daily-history-EWA"]["host"].endswith("query2.finance.yahoo.com")
    assert a.get("daily-history-EWA").rows == 6


def test_non_daily_or_too_short_answers_are_not_stored(tmp_path):
    net = FakeNet()
    net.yahoo["VYM"] = [ok(chart("VYM", [T0 + i * 30 * DAY for i in range(12)], gran="1mo"))]
    net.yahoo["LBRDK"] = [ok(chart("LBRDK", [T0]))]
    net.yahoo["XOP"] = [httpx.Response(200, text="<html>consent</html>", headers={"content-type": "text/html"})]
    a = _arch(tmp_path)
    with net.client() as c:
        rep = m.fetch_daily_histories(a, ["VYM", "LBRDK", "XOP"], min_interval=0, client=c)
    assert "not stored" in rep["daily-history-VYM"]["error"] and "1 daily bars" in rep["daily-history-LBRDK"]["error"]
    assert rep["daily-history-XOP"]["error"] == "answer is not JSON"
    assert [e.name for e in a.entries()] == []


def test_refresh_keeps_stored_history_when_the_new_one_is_much_shorter(tmp_path):
    net = FakeNet()
    net.yahoo["GDX"] = [ok(chart("GDX", [T0 + i * DAY for i in range(20)])), ok(chart("GDX", [T0 + i * DAY for i in range(6)]))]
    a = _arch(tmp_path)
    with net.client() as c:
        m.fetch_daily_histories(a, ["GDX"], min_interval=0, client=c)
        rep = m.fetch_daily_histories(a, ["GDX"], min_interval=0, client=c, refresh=True)
    assert "kept the stored bundle" in rep["daily-history-GDX"]["kept_stored"] and a.get("daily-history-GDX").rows == 20


def test_no_store_returns_rows():
    net = FakeNet()
    net.yahoo["IAU"] = [ok(chart("IAU", [T0 + i * DAY for i in range(6)]))]
    with net.client() as c:
        rep = m.fetch_daily_histories(None, ["IAU"], min_interval=0, client=c)
    assert len(rep["daily-history-IAU"]["rows"]) == 6 and rep["daily-events-IAU"]["rows"] == []


# ------------------------------------------------------------------------------------------------- hourly --

def hourly_chart(sym, ts):
    return chart(sym, ts, adj=False, gran="1h")


def test_hourly_rows_match_fetch_hourly_and_merge(tmp_path, monkeypatch):
    ts = [T0 + i * 3600 for i in range(7)]
    net = FakeNet()
    net.yahoo["RY.TO"] = [ok(hourly_chart("RY.TO", ts))]
    monkeypatch.setattr(unlocks, "_client", lambda: net.client())
    old = _arch(tmp_path, "old")
    unlocks.fetch_hourly(ObservationStore(old), symbols=["RY.TO"])
    new = _arch(tmp_path, "new")
    with net.client() as c:
        m.fetch_hourly_histories(new, ["RY.TO"], min_interval=0, client=c)
    assert list(new.load("hourly-RY.TO")) == list(old.load("hourly-RY.TO"))
    eo, en = old.get("hourly-RY.TO"), new.get("hourly-RY.TO")
    assert en.tags == eo.tags and en.schema == eo.schema and en.in_git is False
    assert net.calls[-1].url.params["range"] == "730d" and net.calls[-1].url.params["interval"] == "1h"
    assert en.recipe.startswith(eo.recipe) and '"currency": "USD"' in en.recipe
    # a later window overlapping the stored one: merged, the stored bars kept, a bar still in progress dropped
    later = [T0 + i * 3600 for i in range(5, 10)] + [int(time.time()) - 600]
    net.yahoo["RY.TO"] = [ok(hourly_chart("RY.TO", later))]
    with net.client() as c:
        rep = m.fetch_hourly_histories(new, ["RY.TO"], min_interval=0, client=c, refresh=True)
    rows = list(new.load("hourly-RY.TO"))
    assert len(rows) == 10 and rep["hourly-RY.TO"]["fresh_bars"] == 5 and rows[0]["available_at"] == m.iso(T0 + 3600)


def test_hourly_skip_stored(tmp_path):
    net = FakeNet()
    net.yahoo["CAD=X"] = [ok(hourly_chart("CAD=X", [T0 + i * 3600 for i in range(3)]))]
    a = _arch(tmp_path)
    with net.client() as c:
        m.fetch_hourly_histories(a, ["CAD=X"], min_interval=0, client=c)
        n = len(net.calls)
        rep = m.fetch_hourly_histories(a, ["CAD=X"], min_interval=0, client=c)
    assert len(net.calls) == n and rep["hourly-CAD-X"] == {"skipped": "stored"}


# --------------------------------------------------------------------------------------------- FRED/ALFRED --

def fred_page(lic, source, freq, extra=""):
    return (f'<script type="application/ld+json">{{"@context": "http://schema.org", "@type": "Dataset", "license": "https://fred.stlouisfed.org/legal/{lic}",'
            f' "name": "A series"}}</script><p><strong>Source:</strong>\n <a class="note-source" href="x">{source}\n <i class="fas"></i></a>&nbsp;</p>'
            f'<p><strong>Release:</strong> <a href="y">Some Release <i></i></a></p><span class="series-meta-value-frequency">\n {freq} </span>{extra}')


def alfred_page(vintages, start, end):
    opts = "".join(f'<option value="{v}">{v}</option>' for v in vintages)
    return (f'<form name="form" method="post"><input type="text" id="form_obs_start_date" name="form[obs_start_date]" required="required" '
            f'maxlength="10" value="{start}"> to <input type="text" id="form_obs_end_date" name="form[obs_end_date]" required="required" '
            f'maxlength="10" value="{end}"><select id="form_selected_vintage_dates" name="form[selected_vintage_dates][]" multiple="multiple">{opts}</select></form>')


def alfred_zip(sid, lines):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("README.txt", "Output Format: Observations by Real-Time Period")
        z.writestr("obs._by_real-time_period.csv", f"period_start_date,{sid},realtime_start_date,realtime_end_date\n" + "\n".join(lines) + "\n")
    return b.getvalue()


def test_fred_daily_rows_match_the_fred_dtb3_convention(tmp_path, monkeypatch):
    net = FakeNet()
    net.fred_csv["DGS20"] = "observation_date,DGS20\n1993-10-01,6.12\n1993-10-04,.\n1993-10-05,6.10\n1993-10-06,6.08\n"
    net.fred_page["DGS20"] = fred_page("#copyright-public-domain", "Board of Governors of the Federal Reserve System (US)", "Daily")
    monkeypatch.setattr(options_mod, "_client", lambda: net.client())
    old = _arch(tmp_path, "old")
    options_mod.collect_options_history(ObservationStore(old), indices=(), fred=("DGS20",), currencies=())
    new = _arch(tmp_path, "new")
    with net.client() as c:
        rep = m.fetch_fred_series(new, ["DGS20"], min_interval=0, client=c)
    assert list(new.load("fred-DGS20")) == list(old.load("fred-DGS20"))
    e = new.get("fred-DGS20")
    assert e.in_git is True and e.tags == old.get("fred-DGS20").tags and e.schema == old.get("fred-DGS20").schema
    assert rep["fred-DGS20"]["daily"] is True and "alfred-DGS20" not in rep and "copyright-public-domain" in e.recipe


def test_fred_copyrighted_or_unreadable_pages_stay_out_of_git(tmp_path):
    net = FakeNet()
    net.fred_csv["BAA10Y"] = "observation_date,BAA10Y\n2026-10-07,1.71\n2026-10-08,1.70\n2026-10-09,1.69\n"
    net.fred_page["BAA10Y"] = fred_page("#copyright-citation-required", "Federal Reserve Bank of St. Louis", "Daily")
    net.fred_csv["DFII10"] = "observation_date,DFII10\n2026-10-08,1.71\n2026-10-09,1.69\n2026-10-13,1.70\n"
    net.fred_page["DFII10"] = httpx.Response(500, text="err")
    a = _arch(tmp_path)
    with net.client() as c:
        rep = m.fetch_fred_series(a, ["BAA10Y", "DFII10"], min_interval=0, client=c, retries=2)
    assert a.get("fred-BAA10Y").in_git is False and "never in git" in a.get("fred-BAA10Y").recipe
    assert a.get("fred-DFII10").in_git is False and "licence not read" in a.get("fred-DFII10").recipe
    assert rep["fred-DFII10"]["meta_error"]
    assert m.fred_in_git({"license": "https://fred.stlouisfed.org/legal/#copyright-public-domain", "source": "Federal Reserve Bank of St. Louis"}) is False


UNRATE_VINTAGES = ["1960-03-15", "1966-02-08", "2026-01-09", "2026-02-06", "2026-10-02"]
UNRATE_RTP = ["1948-01-01,3.5,1960-03-15,1966-02-07", "1948-01-01,3.4,1966-02-08,", "2025-12-01,4.4,2026-01-09,2026-02-05",
              "2025-12-01,4.5,2026-02-06,", "2026-09-01,4.2,2026-10-02,"]


def _unrate_net():
    net = FakeNet()
    net.fred_csv["UNRATE"] = "observation_date,UNRATE\n1948-01-01,3.4\n2025-12-01,4.5\n2026-08-01,4.1\n2026-09-01,4.2\n"
    net.fred_page["UNRATE"] = fred_page("#copyright-public-domain", "U.S. Bureau of Labor Statistics", "Monthly")
    net.alfred_page["UNRATE"] = alfred_page(UNRATE_VINTAGES, "1948-01-01", "2026-09-01")
    net.alfred_zip["UNRATE"] = alfred_zip("UNRATE", UNRATE_RTP)
    return net


def test_alfred_real_time_periods_and_release_times(tmp_path):
    net = _unrate_net()
    a = _arch(tmp_path)
    with net.client() as c:
        rep = m.fetch_fred_series(a, ["UNRATE"], min_interval=0, client=c)
    form = net.posts[0]
    assert form["form[file_type]"] == ["1"] and form["form[file_format]"] == ["csv"]
    assert form["form[selected_vintage_dates][]"] == UNRATE_VINTAGES and form["form[obs_start_date]"] == ["1948-01-01"]
    rows = {r["key"]: r for r in a.load("alfred-UNRATE")}
    first = rows["UNRATE:1948-01-01:1960-03-15"]
    assert first["value"]["first_release"] and first["value"]["first_vintage"] and first["value"]["lag_rule_at"] == "1948-03-06T23:59:59+00:00"
    assert first["available_at"] == "1960-03-15T13:30:00+00:00"                 # 08:30 EST
    rev = rows["UNRATE:1948-01-01:1966-02-08"]
    assert not rev["value"]["first_release"] and not rev["value"]["first_vintage"] and rev["value"]["realtime_end"] is None
    assert rows["UNRATE:2025-12-01:2026-01-09"]["value"]["first_release"] and rows["UNRATE:2025-12-01:2026-01-09"]["value"]["lag_rule_at"] is None
    assert rows["UNRATE:2026-09-01:2026-10-02"]["available_at"] == "2026-10-02T12:30:00+00:00"       # 08:30 EDT
    assert a.get("alfred-UNRATE").in_git is True and rep["alfred-UNRATE"]["vintages"] == 5
    fred = {r["value"]["day"]: r for r in a.load("fred-UNRATE")}
    assert fred["1948-01-01"]["available_at"] == "1966-02-08T13:30:00+00:00" and fred["1948-01-01"]["value"]["available_basis"] == "alfred-current-vintage"
    assert fred["2025-12-01"]["available_at"] == "2026-02-06T13:30:00+00:00"
    assert fred["2026-08-01"]["value"]["available_basis"] == "capture" and fred["2026-08-01"]["available_at"] > "2026-10-02"
    assert fred["2026-09-01"]["observed_at"] == "2026-09-01T00:00:00+00:00" and "revised" in a.get("fred-UNRATE").tags
    assert rep["fred-UNRATE"]["capture_stamped"] == 1


def test_non_daily_series_resume_needs_both_bundles(tmp_path):
    net = _unrate_net()
    a = _arch(tmp_path)
    with net.client() as c:
        m.fetch_fred_series(a, ["UNRATE"], min_interval=0, client=c)
        n = len(net.calls)
        assert m.fetch_fred_series(a, ["UNRATE"], min_interval=0, client=c)["fred-UNRATE"] == {"skipped": "stored"} and len(net.calls) == n
        (a.root / "data" / "alfred-UNRATE.jsonl.gz").unlink()
        m.fetch_fred_series(a, ["UNRATE"], min_interval=0, client=c)
    assert len(net.calls) == n + 4                                  # page, csv, ALFRED GET, ALFRED POST


def test_release_times_and_lag_rule():
    assert m.parse_fred_page(fred_page("#copyright-public-domain", "Board of Governors of the Federal Reserve System (US)", "Quarterly,"))["frequency"] == "Quarterly"
    assert m.release_at("UMCSENT", "2026-08-28") == "2026-08-28T14:00:00+00:00"
    assert m.release_at("BOGZ1FA653064100Q", "2019-03-07") == "2019-03-07T17:00:00+00:00"
    assert m.release_at("IRLTLT01USM156N", "2026-09-15") == "2026-09-15T23:59:59+00:00"
    assert m.lag_rule_at("BOGZ1FA653064100Q", "1990-01-01", 3) == "1990-06-23T23:59:59+00:00"     # Q1 end + 84 days
    assert m.lag_rule_at("USREC", "2020-02-01", 1) is None


# ------------------------------------------------------------------------------------------ plans, entry --

class Refuse:
    def __call__(self, request):
        raise AssertionError(f"dry run made a request: {request.url}")


def test_dry_run_makes_no_request_and_plans_every_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "_client", lambda timeout=0: httpx.Client(transport=httpx.MockTransport(Refuse())))
    a = _arch(tmp_path)
    rep = m.fetch_all_yahoo_fred(a, dry_run=True)
    plan = rep["_plan"]
    names = {p["name"] for p in plan}
    assert {"daily-history-EEM", "daily-events-EEM", "hourly-RY.TO", "fred-DGS20", "fred-UNRATE", "alfred-UNRATE", "alfred-BOGZ1FA653064100Q"} <= names
    assert "alfred-DGS20" not in names
    for p in plan:
        assert p["in_git"] or p["gitignore_line"] == m.gitignore_line(p["name"])
        assert p["calls"] >= 0 and p["rows"] >= 0 and p["gz_mb"] >= 0 and p["minutes"] >= 0 and p["available_at_rule"]
    byname = {p["name"]: p for p in plan}
    assert byname["fred-DGS20"]["in_git"] and not byname["fred-UMCSENT"]["in_git"] and not byname["alfred-IRLTLT01USM156N"]["in_git"]
    assert byname["daily-events-EEM"]["calls"] == 0 and byname["daily-history-EEM"]["calls"] == 1
    assert rep["_totals"]["bundles"] == len(plan) and rep["_totals"]["calls"] == len(m.DAILY_SYMBOLS) + len(m.HOURLY_SYMBOLS) + sum(
        p["calls"] for p in plan if p["function"] == "fetch_fred_series")
    assert m.gitignore_block(plan).count("\n") + 1 == sum(1 for p in plan if not p["in_git"])
    assert a.entries() == []


def test_fetch_all_with_limit_fetches_one_bundle_per_source(tmp_path, monkeypatch):
    net = _unrate_net()
    first_daily, first_hourly, first_fred = m.DAILY_SYMBOLS[0], m.HOURLY_SYMBOLS[0], m.FRED_SERIES[0]
    net.yahoo[first_daily] = [ok(chart(first_daily, [T0 + i * DAY for i in range(6)]))]
    net.yahoo[first_hourly] = [ok(hourly_chart(first_hourly, [T0 + i * 3600 for i in range(4)]))]
    net.fred_csv[first_fred] = f"observation_date,{first_fred}\n2026-10-08,1.71\n2026-10-09,1.69\n2026-10-13,1.70\n"
    net.fred_page[first_fred] = fred_page("#copyright-public-domain", "Board of Governors of the Federal Reserve System (US)", "Daily")
    monkeypatch.setattr(m, "_client", lambda timeout=0: net.client())
    a = _arch(tmp_path)
    rep = m.fetch_all_yahoo_fred(a, limit=1, yahoo_interval=0, fred_interval=0)
    stored = {e.name for e in a.entries()}
    assert stored == {m.history_bundle(first_daily), m.events_bundle(first_daily), m.hourly_bundle(first_hourly), m.fred_bundle(first_fred)}
    assert rep["_totals"]["bundles"] == 4
    rep2 = m.fetch_all_yahoo_fred(a, dry_run=True, limit=1)
    assert m.history_bundle(first_daily) not in {p["name"] for p in rep2["_plan"]}       # resumes past what is stored


def test_command_line_preview_writes_a_scratch_archive(tmp_path, monkeypatch, capsys):
    net = FakeNet()
    net.yahoo["EEM"] = [ok(chart("EEM", [T0 + i * DAY for i in range(6)]))]
    monkeypatch.setattr(m, "_client", lambda timeout=0: net.client())
    assert m.main(["daily", "--symbols", "EEM", "--preview", str(tmp_path / "pv"), "--yahoo-interval", "0"]) == 0
    a = Archive(root=tmp_path / "pv" / "archive", ledger=Ledger(tmp_path / "pv" / "ledger.jsonl"))
    assert a.get("daily-history-EEM").rows == 6 and (tmp_path / "pv" / "daily.report.json").exists()
    out = json.loads(capsys.readouterr().out)
    assert out["plan_bundles"] == 2 and out["results"]["daily-history-EEM"]["stored"]["rows"] == 6
    assert json.loads((tmp_path / "pv" / "daily.report.json").read_text())["_plan"][0]["name"] == "daily-history-EEM"
