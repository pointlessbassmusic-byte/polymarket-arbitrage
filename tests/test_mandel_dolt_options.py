"""DoltHub options fetcher: NYSE calendar and quote-date rule, row shaping, window walking under the 1000-row cap and
query deadlines, commit-log parsing, bundle merge, and the parity check on recorded SPY rows. No network."""

import math
import re
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from mandel.archive import Archive
from mandel.data import dolt_options as m
from mandel.ledger import Ledger

COLS = ["date", "act_symbol", "expiration", "strike", "call_put", "bid", "ask", "vol", "delta", "gamma", "theta", "vega", "rho"]

# Recorded 2026-10-15 from the DoltHub API: near-ATM SPY rows of two snapshots.
REC_2019_02_09 = [   # a Saturday snapshot (2019 is weekly, Saturdays)
    ("2019-02-09", "SPY", "2019-02-22", "265.00", "Call", "6.60", "6.66", "0.1475", "0.7683", "0.0390", "-0.0948", "0.1613", "0.0771"),
    ("2019-02-09", "SPY", "2019-02-22", "265.00", "Put", "1.05", "1.08", "0.1472", "-0.2313", "0.0394", "-0.0822", "0.1668", "-0.0220"),
    ("2019-02-09", "SPY", "2019-02-22", "270.50", "Call", "2.62", "2.67", "0.1237", "0.5088", "0.0609", "-0.0999", "0.2111", "0.0517"),
    ("2019-02-09", "SPY", "2019-02-22", "270.50", "Put", "2.56", "2.60", "0.1231", "-0.4940", "0.0620", "-0.0874", "0.2110", "-0.0433"),
    ("2019-02-09", "SPY", "2019-03-08", "265.00", "Call", "7.94", "8.00", "0.1520", "0.7038", "0.0304", "-0.0804", "0.2587", "0.1399"),
    ("2019-02-09", "SPY", "2019-03-08", "265.00", "Put", "2.15", "2.18", "0.1511", "-0.2967", "0.0309", "-0.0659", "0.2629", "-0.0553"),
    ("2019-02-09", "SPY", "2019-03-08", "270.00", "Call", "4.43", "4.48", "0.1355", "0.5390", "0.0391", "-0.0798", "0.2972", "0.1084"),
    ("2019-02-09", "SPY", "2019-03-08", "270.00", "Put", "3.63", "3.67", "0.1344", "-0.4651", "0.0402", "-0.0654", "0.2973", "-0.0813"),
]
CLOSES_2019 = {"2019-02-07": 270.14, "2019-02-08": 270.47, "2019-02-11": 270.62}       # Yahoo SPY closes (archive daily-history-SPY)
REC_2022_08_19 = [   # a Friday with large moves either side: Thursday 427.89, Friday 422.14, Monday 413.35
    ("2022-08-19", "SPY", "2022-09-02", "414.00", "Call", "11.44", "11.49", "0.1937", "0.7106", "0.0213", "-0.2126", "0.2827", "0.1107"),
    ("2022-08-19", "SPY", "2022-09-02", "414.00", "Put", "2.94", "2.97", "0.1931", "-0.2896", "0.0216", "-0.1891", "0.2854", "-0.0431"),
    ("2022-08-19", "SPY", "2022-09-02", "422.00", "Call", "6.11", "6.14", "0.1780", "0.5208", "0.0271", "-0.2220", "0.3294", "0.0820"),
    ("2022-08-19", "SPY", "2022-09-02", "422.00", "Put", "5.60", "5.64", "0.1774", "-0.4815", "0.0275", "-0.1989", "0.3293", "-0.0677"),
    ("2022-08-19", "SPY", "2022-09-16", "414.00", "Call", "13.88", "14.05", "0.2062", "0.6390", "0.0155", "-0.1539", "0.4363", "0.1962"),
    ("2022-08-19", "SPY", "2022-09-16", "414.00", "Put", "5.84", "5.86", "0.2008", "-0.3556", "0.0159", "-0.1594", "0.4355", "-0.1153"),
    ("2022-08-19", "SPY", "2022-09-16", "422.00", "Call", "8.70", "8.72", "0.1882", "0.5075", "0.0181", "-0.1512", "0.4653", "0.1577"),
    ("2022-08-19", "SPY", "2022-09-16", "422.00", "Put", "8.78", "8.82", "0.1880", "-0.4902", "0.0182", "-0.1609", "0.4653", "-0.1582"),
]
CLOSES_2022 = {"2022-08-18": 427.89, "2022-08-19": 422.14, "2022-08-22": 413.35}
CLOSES_2022_WIDE = {"2022-08-16": 429.70, "2022-08-17": 426.65, "2022-08-18": 427.89, "2022-08-19": 422.14, "2022-08-22": 413.35,
                    "2022-08-23": 412.35, "2022-08-24": 413.67}             # archive daily-history-SPY closes
DTB3_2022 = {"2022-08-17": 0.0259, "2022-08-18": 0.0261, "2022-08-19": 0.0264, "2022-08-22": 0.0274}   # archive fred-DTB3 / 100

VOL_REC = {"date": "2025-01-03", "act_symbol": "SPY", "hv_current": "0.1105", "hv_week_ago": "0.1301", "hv_month_ago": "0.0890",
           "hv_year_high": "0.2251", "hv_year_high_date": "2024-08-05", "hv_year_low": "0.0675", "hv_year_low_date": "2024-01-31",
           "iv_current": "0.1513", "iv_week_ago": "0.1450", "iv_month_ago": "0.1290", "iv_year_high": "0.3050",
           "iv_year_high_date": "2024-08-05", "iv_year_low": "0.0960", "iv_year_low_date": "2024-05-20"}


def _raw(t):
    return dict(zip(COLS, t))


# ------------------------------------------------------------------ fake DoltHub --

class FakeDolt:
    """Serves option_chain / volatility_history / dolt_log from memory, parsing the fetcher's SQL shapes, with the real
    API's 1000-row cap and optional 'context deadline exceeded' failures for chosen calls."""

    def __init__(self, chain=(), vol=(), log=(), fail_calls=(), deadline_if_days_over=None):
        self.tables = {"option_chain": list(chain), "volatility_history": list(vol)}
        self.log = list(log)
        self.calls: list[str] = []
        self.fail_calls = set(fail_calls)
        self.deadline_if_days_over = deadline_if_days_over

    @staticmethod
    def _resp(status, rows, msg=""):
        return httpx.Response(200, json={"query_execution_status": status, "query_execution_message": msg, "rows": rows})

    def handler(self, request: httpx.Request) -> httpx.Response:
        sql = request.url.params["q"]
        self.calls.append(sql)
        if len(self.calls) in self.fail_calls:
            return self._resp("Error", [], "query error: context deadline exceeded")
        if "FROM dolt_log" in sql:
            lim = int(re.search(r"LIMIT (\d+)", sql).group(1)); off = int(re.search(r"OFFSET (\d+)", sql).group(1))
            return self._resp("Success", self.log[off:off + lim])
        table = "option_chain" if "FROM option_chain" in sql else "volatility_history"
        sm = re.search(r"act_symbol IN \(([^)]*)\)", sql) or re.search(r"act_symbol = ('[^']*')", sql)
        dm = re.search(r"date IN \(([^)]*)\)", sql) or re.search(r"date = ('[^']*')", sql)
        syms = set(re.findall(r"'([^']*)'", sm.group(1)))
        days = set(re.findall(r"'([^']*)'", dm.group(1)))
        if self.deadline_if_days_over and len(days) > self.deadline_if_days_over:
            return self._resp("Error", [{"partial": True}], "query error: context deadline exceeded")
        rows = [r for r in self.tables[table] if r["act_symbol"] in syms and r["date"] in days]
        lm = re.search(r"LIMIT (\d+) OFFSET (\d+)", sql)
        if lm:
            rows = sorted(rows, key=lambda r: (r["expiration"], float(r["strike"]), r["call_put"]))
            rows = rows[int(lm.group(2)):int(lm.group(2)) + int(lm.group(1))]
        if len(rows) > m.ROW_CAP:
            return self._resp("RowLimit", rows[:m.ROW_CAP])
        return self._resp("Success", rows)


def synthetic_chain(start, end, per_day, symbol="SPY", weekdays=(0, 1, 2, 3, 4)):
    """per_day rows on each trading day in [start, end] whose weekday is in ``weekdays``."""
    out, d = [], date.fromisoformat(start)
    while d <= date.fromisoformat(end):
        if m.is_trading_day(d) and d.weekday() in weekdays:
            for i in range(per_day):
                k = 400 + (i // 2)
                out.append({"date": d.isoformat(), "act_symbol": symbol, "expiration": (d + timedelta(days=14)).isoformat(), "strike": f"{k}.00",
                            "call_put": "Call" if i % 2 == 0 else "Put", "bid": "1.00", "ask": "1.10", "vol": "0.2000", "delta": "0.5000",
                            "gamma": "0.0100", "theta": "-0.1000", "vega": "0.3000", "rho": "0.0500"})
        d += timedelta(days=1)
    return out


@pytest.fixture
def fake(monkeypatch):
    holder = {}

    def install(f):
        holder["f"] = f
        monkeypatch.setattr(m, "_client", lambda: httpx.Client(transport=httpx.MockTransport(f.handler)))
        return f

    monkeypatch.setattr(m, "_sleep", lambda s: None)
    monkeypatch.setattr(m, "_COMMIT_CACHE", {})
    return install


def _archive(tmp_path):
    return Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))


# ----------------------------------------------------------------------- tests --

def test_nyse_calendar_and_quote_date_rule():
    hol = {d.isoformat() for y in (2019, 2020, 2021, 2022, 2025, 2026) for d in m.nyse_holidays(y)}
    for d in ["2020-04-10", "2021-12-24", "2022-06-20", "2025-01-09", "2026-07-03", "2019-01-21", "2022-01-17"]:
        assert d in hol, d
    assert "2022-12-31" not in hol and "2021-12-31" not in hol          # New Year's on a Saturday is not moved to Friday
    assert m.quote_date_for("2019-02-09") == "2019-02-08"              # Saturday snapshot quotes Friday's close
    assert m.quote_date_for("2020-04-10") == "2020-04-09"              # Good Friday quotes Thursday
    assert m.quote_date_for("2024-06-05") == "2024-06-05"              # weekday quotes the same session
    assert m.quote_date_for("2025-01-09") == "2025-01-08"              # unscheduled closure (Carter funeral)
    assert m.available_at_for("2019-02-09") == "2019-02-09T22:00:00+00:00"
    assert m.available_at_for("2024-06-05") == "2024-06-05T22:00:00+00:00"
    assert m.available_at_for("2024-06-05", "2024-06-06") == "2024-06-06T22:00:00+00:00"   # never before the quote date's evening


def test_chain_and_vol_row_shapes():
    r = m.chain_row(_raw(REC_2019_02_09[2]), "2026-10-15T12:00:00+00:00", {})
    v = r["value"]
    assert v["snapshot_date"] == "2019-02-09" and v["quote_date"] == "2019-02-08" and v["type"] == "call"
    assert v["strike"] == 270.5 and v["bid"] == 2.62 and v["iv"] == 0.1237 and v["rho"] == 0.0517 and v["expiry"] == "2019-02-22"
    assert r["observed_at"] == "2026-10-15T12:00:00+00:00" and r["available_at"] == "2019-02-09T22:00:00+00:00"
    assert r["key"] == "SPY:2019-02-09:2019-02-22:C270.50" and v["dolt_commit_at"] is None and v["backfilled"] is None
    assert v["stale"] is None and v["stale_basis"] is None                # not checked until the fetcher runs the stale check
    bulk = m.chain_row(_raw(REC_2019_02_09[2]), "x", {"2021-05-03": "t", "2019-04-01": "2021-04-20T23:20:48+00:00"})["value"]
    assert bulk["dolt_commit_at"] == m.BULK_IMPORT_AT == "2021-04-21T01:13:00+00:00" and bulk["backfilled"] is False
    nulls = _raw(REC_2019_02_09[3]); nulls["bid"] = None
    assert m.chain_row(nulls, "x")["value"]["bid"] is None
    vr = m.vol_row(VOL_REC, "x", {"2025-01-03": "2025-01-04T06:35:00+00:00"})
    assert vr["value"]["iv_current"] == 0.1513 and vr["value"]["hv_year_high_date"] == "2024-08-05"
    assert vr["value"]["quote_date"] == "2025-01-03" and vr["value"]["dolt_commit_at"] == "2025-01-04T06:35:00+00:00"
    assert vr["value"]["backfilled"] is False and vr["value"]["stale"] is None


def test_symbol_validation_blocks_sql():
    with pytest.raises(ValueError):
        m.fetch_dolt_chains(None, "SPY' OR '1'='1")
    with pytest.raises(ValueError):
        m.fetch_dolt_volhistory(None, ["SPY", "X;DROP"])


def test_dolt_sql_retries_deadline_but_not_syntax_errors(fake):
    f = fake(FakeDolt(chain=[_raw(t) for t in REC_2019_02_09], fail_calls={1, 2}))
    with m._client() as c:
        res = m.dolt_sql("SELECT * FROM option_chain WHERE act_symbol = 'SPY' AND date IN ('2019-02-09')", c, m.Throttle(0))
    assert res["status"] == "Success" and len(res["rows"]) == 8 and len(f.calls) == 3

    def bad(request):
        bad.n += 1
        return httpx.Response(200, json={"query_execution_status": "Error", "query_execution_message": "syntax error at position 7", "rows": []})
    bad.n = 0
    with httpx.Client(transport=httpx.MockTransport(bad)) as c:
        assert m.dolt_sql("SELEC", c, m.Throttle(0))["status"] == "Error" and bad.n == 1


def test_walk_windows_respects_row_cap_and_deadlines(fake):
    chain = synthetic_chain("2025-01-01", "2025-04-30", 150)          # dense: 150 rows on every trading day
    f = fake(FakeDolt(chain=chain, deadline_if_days_over=20))         # empty December grows the window to 31 days: deadline
    st = {}
    rows = m.fetch_dolt_chains(None, "SPY", start="2024-11-01", end="2025-04-30", pace=0, with_commits=False, stats=st)
    assert len(rows) == len(chain)                                   # every row exactly once, partial Error rows discarded
    assert len({r["key"] for r in rows}) == len(chain)
    n_days = [len(re.findall(r"'\d{4}-\d{2}-\d{2}'", q)) for q in f.calls]
    assert max(n_days) > 20 and st["splits"] >= 2 and not st["failed_days"]
    assert st["windows"] < len(n_days) <= st["windows"] + st["splits"]
    # a single day above the cap is paged with ORDER BY ... LIMIT/OFFSET
    big = synthetic_chain("2025-02-03", "2025-02-03", 2300)
    f2 = fake(FakeDolt(chain=big))
    rows2 = m.fetch_dolt_chains(None, "SPY", start="2025-02-03", end="2025-02-03", pace=0, with_commits=False)
    assert len(rows2) == 2300 and any("OFFSET 2000" in q for q in f2.calls)


def test_limit_days_and_sparse_history(fake):
    sat = []                                                         # 2019 is Saturdays only
    d = date(2019, 2, 9)
    while d <= date(2019, 6, 30):
        sat += [dict(r, date=d.isoformat()) for r in synthetic_chain("2019-02-11", "2019-02-11", 66)]
        d += timedelta(days=7)
    fake(FakeDolt(chain=sat))
    st = {}
    rows = m.fetch_dolt_chains(None, "SPY", start="2019-02-01", end="2019-06-30", limit_days=3, pace=0, with_commits=False, stats=st)
    snaps = sorted({r["value"]["snapshot_date"] for r in rows})
    assert snaps == ["2019-02-09", "2019-02-16", "2019-02-23"] and len(rows) == 3 * 66
    assert all(r["value"]["quote_date"] == (date.fromisoformat(r["value"]["snapshot_date"]) - timedelta(days=1)).isoformat() for r in rows)
    assert st["last_day"] == "2019-02-23"


def test_commit_log_parsing_and_bulk_fallback(fake):
    log = [{"date": "2026-10-15 06:35:00.543", "message": "volatility_history 2026-10-14 update"},
           {"date": "2026-10-15 06:34:53.747", "message": "option_chain 2026-10-14 update"},
           {"date": "2021-10-07 06:55:57.800", "message": "option_chain 2021-10-06 update"},       # re-run: keep the LAST
           {"date": "2021-10-07 06:46:54.630", "message": "option_chain 2021-10-06 update"},
           {"date": "2022-06-01 07:22:37.395", "message": "get rid of bad memorial day data"},
           {"date": "2021-04-20 23:20:48.218", "message": "option_chain 2019-04-01 update"},
           {"date": "2021-04-20 23:18:54.935", "message": "Initialize data repository"}]
    fake(FakeDolt(log=log))
    st1, st2 = {}, {}
    with m._client() as c:
        oc = m.dolt_commit_times(c, m.Throttle(0), "option_chain", page=3, stats=st1)
        vh = m.dolt_commit_times(c, m.Throttle(0), "volatility_history", page=3, stats=st2)   # served from the one-pass cache
    assert oc == {"2026-10-14": "2026-10-15T06:34:53+00:00", "2021-10-06": "2021-10-07T06:55:57+00:00", "2019-04-01": "2021-04-20T23:20:48+00:00"}
    assert vh == {"2026-10-14": "2026-10-15T06:35:00+00:00"}
    assert st1["commit_log_complete"] is True and st1["commit_log_cached"] is False and st1["calls"] == 3
    assert st2["commit_log_complete"] is True and st2["commit_log_cached"] is True and "calls" not in st2
    # every bulk-era date gets BULK_IMPORT_AT, even the one a bulk commit happens to name
    assert m.commit_time_for("2020-03-02", oc) == m.BULK_IMPORT_AT and m.commit_time_for("2019-04-01", oc) == m.BULK_IMPORT_AT
    assert m.commit_time_for("2023-01-04", oc) is None and m.commit_time_for("2020-03-02", {}) is None


def test_incomplete_commit_log_is_not_cached(fake):
    log = [{"date": f"2026-10-{d:02d} 06:35:00.000", "message": f"option_chain 2026-10-{d - 1:02d} update"} for d in range(14, 2, -1)]
    fake(FakeDolt(log=log, fail_calls={2, 3, 4, 5}))                    # the second page fails on every retry
    st = {}
    with m._client() as c:
        oc = m.dolt_commit_times(c, m.Throttle(0), "option_chain", page=3, stats=st)
    assert st["commit_log_complete"] is False and st["calls"] == 2 and "log" not in m._COMMIT_CACHE
    assert sorted(oc) == ["2026-10-11", "2026-10-12", "2026-10-13"]               # the first page only


def test_fetch_stores_merges_and_dry_run(fake, tmp_path):
    arc = _archive(tmp_path)
    chain = synthetic_chain("2024-01-02", "2024-02-29", 20)
    fake(FakeDolt(chain=chain))
    assert m.fetch_dolt_chains(arc, "SPY", start="2024-01-01", end="2024-02-29", pace=0, with_commits=False, dry_run=True)
    assert "dolt-chain-SPY" not in {e.name for e in arc.entries()}
    rows = m.fetch_dolt_chains(arc, "SPY", start="2024-01-01", end="2024-02-29", pace=0, with_commits=False)
    e = arc.get("dolt-chain-SPY")
    assert e.rows == len(chain) == len(rows) and "dolthub" in e.tags and "date IN" in e.recipe and "quote_date" in e.schema
    # an incremental fetch of February keeps January
    fake(FakeDolt(chain=synthetic_chain("2024-02-01", "2024-03-15", 20)))
    m.fetch_dolt_chains(arc, "SPY", start="2024-02-01", end="2024-03-15", pace=0, with_commits=False)
    stored = list(arc.load("dolt-chain-SPY"))
    assert len(stored) == len(synthetic_chain("2024-01-02", "2024-03-15", 20)) and len({r["key"] for r in stored}) == len(stored)
    assert [r["value"]["snapshot_date"] for r in stored] == sorted(r["value"]["snapshot_date"] for r in stored)
    # a refetch whose query for 2024-02-05 keeps failing must not drop that day's stored rows
    class FailOneDay(FakeDolt):
        def handler(self, request):
            if "'2024-02-05'" in request.url.params["q"]:
                self.calls.append(request.url.params["q"])
                return self._resp("Error", [], "query error: context deadline exceeded")
            return super().handler(request)
    fake(FailOneDay(chain=synthetic_chain("2024-02-01", "2024-02-09", 20)))
    st = {}
    m.fetch_dolt_chains(arc, "SPY", start="2024-02-01", end="2024-02-09", pace=0, with_commits=False, stats=st)
    assert st["failed_days"] == ["2024-02-05"]
    again = list(arc.load("dolt-chain-SPY"))
    assert len(again) == len(stored) and sum(r["value"]["snapshot_date"] == "2024-02-05" for r in again) == 20


def test_volhistory_reports_missing_symbols(fake, tmp_path):
    vol = []
    for d in ["2025-01-02", "2025-01-03", "2025-01-06"]:
        for s in ["SPY", "XLE", "DIA"]:
            vol.append(dict(VOL_REC, date=d, act_symbol=s))
    fake(FakeDolt(vol=vol))
    arc = _archive(tmp_path)
    st = {}
    rows = m.fetch_dolt_volhistory(arc, ["SPY", "XLE", "QQQ"], start="2025-01-01", end="2025-01-10", pace=0, with_commits=False, stats=st)
    assert len(rows) == 6 and st["missing"] == ["QQQ"] and st["rows_by_symbol"]["SPY"] == 3
    assert arc.get("dolt-volhistory").rows == 6


def test_backfill_is_provenance_only(fake):
    """Publication lag is provenance: backfilled and dolt_commit_at are recorded, available_at stays on the snapshot evening."""
    commits = {"2022-12-12": "2022-12-15T17:53:55+00:00", "2024-06-03": "2024-06-04T06:34:51+00:00", "2021-09-28": "2021-09-28T20:58:07+00:00"}
    raw = dict(_raw(REC_2019_02_09[0]), date="2022-12-12")
    r = m.chain_row(raw, "x", commits)
    assert r["value"]["backfilled"] is True and r["value"]["dolt_commit_at"] == "2022-12-15T17:53:55+00:00"
    assert r["available_at"] == "2022-12-12T22:00:00+00:00" and r["value"]["quote_date"] == "2022-12-12"
    r = m.chain_row(dict(raw, date="2024-06-03"), "x", commits)          # published 06:34 UTC next morning: normal
    assert r["value"]["backfilled"] is False and r["available_at"] == "2024-06-03T22:00:00+00:00"
    r = m.chain_row(dict(raw, date="2021-09-28"), "x", commits)          # published the same evening
    assert r["value"]["backfilled"] is False and r["available_at"] == "2021-09-28T22:00:00+00:00"
    r = m.chain_row(dict(raw, date="2025-10-08"), "x", commits)          # live era, no commit names it: unknown, never False
    assert r["value"]["dolt_commit_at"] is None and r["value"]["backfilled"] is None and r["available_at"] == "2025-10-08T22:00:00+00:00"
    assert m.is_backfill("2020-03-02", m.BULK_IMPORT_AT) is False        # the bulk import is not a backfill
    assert m.is_backfill("2025-10-10", "2025-10-13T13:31:00+00:00") and m.is_backfill("2025-10-10", "2025-10-13T13:29:00+00:00") is False
    assert m.is_backfill("2025-10-10", None) is None
    v = m.vol_row(dict(VOL_REC, date="2022-12-12"), "x", commits)
    assert v["value"]["backfilled"] is True and v["available_at"] == "2022-12-12T22:00:00+00:00"
    # SPY 2021-07-09: the on-time commit carried no SPY rows, the re-run five days later loaded them; the LAST commit counts
    log = [{"date": "2021-07-14 21:47:50.703", "message": "option_chain 2021-07-09 update"},
           {"date": "2021-07-10 06:45:04.646", "message": "option_chain 2021-07-09 update"}]
    fake(FakeDolt(log=log))
    with m._client() as c:
        oc = m.dolt_commit_times(c, m.Throttle(0), "option_chain")
    r = m.chain_row(dict(raw, date="2021-07-09"), "x", oc)
    assert r["value"]["dolt_commit_at"] == "2021-07-14T21:47:50+00:00" and r["value"]["backfilled"] is True
    assert r["available_at"] == "2021-07-09T22:00:00+00:00"


def test_parity_check_on_recorded_weekday_snapshot():
    rows = [m.chain_row(_raw(t), "x") for t in REC_2022_08_19]
    res = m.parity_check(rows, CLOSES_2022, rate=0.026)
    assert res[0]["best"] == "same" and res[0]["clear"] and res[0]["agrees_with_rule"] and res[0]["err"] < 0.002


def test_parity_check_on_recorded_saturday_snapshot():
    rows = [m.chain_row(_raw(t), "x") for t in REC_2019_02_09]
    S = m.parity_spot(rows, "2019-02-09", rate=0.024)
    assert abs(S - 270.47) < 0.15                                     # Friday 2019-02-08 close
    res = m.parity_check(rows, CLOSES_2019, rate=0.024)
    assert len(res) == 1 and res[0]["best"] == "prev" and res[0]["matched_day"] == "2019-02-08" and res[0]["agrees_with_rule"]


# ------------------------------------------------------------------ stale check --

def _parity_chain(snap, spot, rate=0.03, div_yield=m.SPY_DIV_YIELD, dtes=(14, 28), symbol="SPY"):
    """Archive rows whose call/put mids satisfy put-call parity exactly for ``spot``: C - P = (S e^{(r-q)T} - K) e^{-rT}."""
    d0 = date.fromisoformat(snap)
    out = []
    for dte in dtes:
        T = dte / 365.0
        F = spot * math.exp((rate - div_yield) * T)
        exp = (d0 + timedelta(days=dte)).isoformat()
        for k in range(-3, 4):
            K = round(spot) + k
            put = 2.0 + max(K - F, 0.0)
            call = put + (F - K) * math.exp(-rate * T)
            for typ, mid in (("Call", call), ("Put", put)):
                out.append(m.chain_row({"date": snap, "act_symbol": symbol, "expiration": exp, "strike": f"{K:.2f}", "call_put": typ,
                                        "bid": f"{mid - 0.01:.10f}", "ask": f"{mid + 0.01:.10f}", "vol": "0.2"}, "x"))
    return out


def test_stale_check_chain_decision_rule():
    snap, rates = "2024-06-05", {"2024-06-05": 0.03}                   # Wednesday: prev 06-04, rule 06-05, next 06-06
    assert m.parity_spot(_parity_chain(snap, 100.15), snap, rate=0.03) == pytest.approx(100.15, abs=1e-6)

    def verdict(spot, closes):
        return m.stale_check_chain(_parity_chain(snap, spot), closes, rates)[snap]

    base = {"2024-06-04": 100.0, "2024-06-05": 100.6, "2024-06-06": 101.5}
    v = verdict(100.6, base)
    assert v["decision"] == "rule" and v["stale"] is False and v["quote_date"] == snap
    v = verdict(100.15, base)                                          # 0.15% off the prev close, gap 0.6%: decisive
    assert v["decision"] == "moved" and v["stale"] is True and v["quote_date"] == "2024-06-04" and "2024-06-04 close" in v["basis"]
    v = verdict(100.25, base)                                          # 0.25% off: noise above a third of the 0.6% gap
    assert v["decision"] == "undecidable" and v["stale"] is False and v["quote_date"] == snap
    v = verdict(100.0, dict(base, **{"2024-06-06": 100.1}))            # prev and next closes only 0.1% apart
    assert v["decision"] == "undecidable" and v["quote_date"] == snap
    v = verdict(100.0, {"2024-06-04": 100.0, "2024-06-05": 100.6})     # next close missing: cannot rule it out
    assert v["decision"] == "undecidable" and "no close for 2024-06-06" in v["basis"]
    v = verdict(100.0, {"2024-06-04": 100.0, "2024-06-06": 100.6})     # rule close missing
    assert v["decision"] == "unchecked" and v["stale"] is None
    assert verdict(100.0, {})["stale"] is None


def test_stale_check_chain_on_recorded_quotes():
    """The recorded Friday 2022-08-19 chain matches its own session; relabelled as a Monday snapshot it is a stale copy of
    Friday (moved back, available_at unchanged); relabelled as a Thursday snapshot it quotes the next session (moved
    forward, available_at waits for that session's evening)."""
    def rows_as(snap):
        return [m.chain_row(dict(_raw(t), date=snap), "x") for t in REC_2022_08_19]

    v = m.stale_check_chain(rows_as("2022-08-19"), CLOSES_2022_WIDE, DTB3_2022)["2022-08-19"]
    assert v["decision"] == "rule" and v["errs"]["rule"] < 0.002
    rows = rows_as("2022-08-22")
    v = m.stale_check_chain(rows, CLOSES_2022_WIDE, DTB3_2022)["2022-08-22"]
    assert v["decision"] == "moved" and v["quote_date"] == "2022-08-19" and v["gap"] > 0.02
    r = m.apply_stale(rows[0], v)
    assert r["value"]["quote_date"] == "2022-08-19" and r["value"]["stale"] is True and "2022-08-19 close 422.14" in r["value"]["stale_basis"]
    assert r["available_at"] == "2022-08-22T22:00:00+00:00"
    rows = rows_as("2022-08-18")
    v = m.stale_check_chain(rows, CLOSES_2022_WIDE, DTB3_2022)["2022-08-18"]
    assert v["decision"] == "moved" and v["quote_date"] == "2022-08-19"
    assert m.apply_stale(rows[0], v)["available_at"] == "2022-08-19T22:00:00+00:00"
    # the Saturday 2019 snapshot: neighbouring closes within 0.2%, nothing to move
    v = m.stale_check_chain([m.chain_row(_raw(t), "x") for t in REC_2019_02_09], dict(CLOSES_2019, **{"2019-02-12": 274.10}),
                            {"2019-02-08": 0.0238})["2019-02-09"]
    assert v["stale"] is False and v["quote_date"] == "2019-02-08"


def _synthetic_closes(start="2024-01-02", n=50):
    out, d, i = {}, date.fromisoformat(start), 0
    while len(out) < n:
        if m.is_trading_day(d):
            out[d.isoformat()] = 100 * math.exp(0.02 * math.sin(1.7 * i) + 0.013 * math.cos(0.45 * i * i) + 0.001 * i)
            i += 1
        d += timedelta(days=1)
    return out


def test_stale_check_vol_uses_exact_hv_match():
    closes = _synthetic_closes()
    snap = "2024-02-24"                                                # Saturday: prev 02-22, rule 02-23, next 02-26
    hv = {d: round(m.hv_close_to_close(closes, d), 4) for d in ("2024-02-22", "2024-02-23", "2024-02-26")}
    assert len(set(hv.values())) == 3

    def row(h, sym="SPY"):
        return m.vol_row(dict(VOL_REC, date=snap, act_symbol=sym, hv_current=None if h is None else f"{h:.4f}"), "x")

    rows = [row(hv["2024-02-23"]), row(hv["2024-02-22"], "XLE"), row(hv["2024-02-26"], "XLF"), row(9.9, "XLK"), row(0.1, "XLU"), row(None, "XLV")]
    cl = {"SPY": closes, "XLE": closes, "XLF": closes, "XLK": closes, "XLV": closes}
    V = m.stale_check_vol(rows, cl)
    assert V[("SPY", snap)]["decision"] == "rule" and V[("SPY", snap)]["quote_date"] == "2024-02-23"
    assert V[("XLE", snap)]["decision"] == "moved" and V[("XLE", snap)]["quote_date"] == "2024-02-22"
    assert V[("XLF", snap)]["decision"] == "moved" and V[("XLF", snap)]["quote_date"] == "2024-02-26"
    assert V[("XLK", snap)]["decision"] == "undecidable" and V[("XLK", snap)]["stale"] is False
    assert V[("XLU", snap)]["decision"] == "unchecked" and V[("XLV", snap)]["decision"] == "unchecked"
    for r in rows:
        m.apply_stale(r, V[(r["value"]["symbol"], snap)])
    by = {r["value"]["symbol"]: r for r in rows}
    assert by["XLE"]["value"]["stale"] is True and by["XLE"]["available_at"] == "2024-02-24T22:00:00+00:00"
    assert "equals the 30-session close-to-close vol ending 2024-02-22" in by["XLE"]["value"]["stale_basis"]
    assert by["XLF"]["value"]["quote_date"] == "2024-02-26" and by["XLF"]["available_at"] == "2024-02-26T22:00:00+00:00"
    assert by["SPY"]["value"]["stale"] is False and by["SPY"]["value"]["stale_basis"] is None and by["XLU"]["value"]["stale"] is None


def _daily_rows(sym, closes):
    return [{"source": "yahoo", "kind": "price", "key": sym, "observed_at": f"{d}T13:30:00+00:00", "available_at": f"{d}T21:00:00+00:00",
             "value": {"symbol": sym, "t": int(datetime.fromisoformat(f"{d}T13:30:00+00:00").timestamp()), "close": c}}
            for d, c in sorted(closes.items())]


def test_fetch_chain_applies_stale_check_and_licence(fake, tmp_path):
    arc = _archive(tmp_path)
    arc.store("daily-history-SPY", "data", _daily_rows("SPY", CLOSES_2022_WIDE), recipe="test fixture")
    arc.store("fred-DTB3", "data", [{"value": {"day": d, "value": x * 100}} for d, x in DTB3_2022.items()], recipe="test fixture")
    chain = [_raw(t) for t in REC_2022_08_19] + [dict(_raw(t), date="2022-08-22") for t in REC_2022_08_19]
    fake(FakeDolt(chain=chain))
    st = {}
    rows = m.fetch_dolt_chains(arc, "SPY", start="2022-08-19", end="2022-08-22", pace=0, with_commits=False, in_git=True, stats=st)
    by = {}
    for r in rows:
        by.setdefault(r["value"]["snapshot_date"], set()).add((r["value"]["quote_date"], r["value"]["stale"], r["available_at"]))
    assert by == {"2022-08-19": {("2022-08-19", False, "2022-08-19T22:00:00+00:00")},
                  "2022-08-22": {("2022-08-19", True, "2022-08-22T22:00:00+00:00")}}
    assert st["stale"]["moved"] == 1 and st["stale"]["rule"] == 1 and st["stale"]["moved_dates"] == ["2022-08-22->2022-08-19"]
    e = arc.get("dolt-chain-SPY")
    assert e.in_git and "cc-by-sa-4.0" in e.tags
    for text in ("CC BY-SA 4.0", "post-no-preference via DoltHub", "ShareAlike", "vol renamed iv", "stale_basis"):
        assert text in e.recipe, text
    assert "stale" in e.schema and "provenance" in e.schema
    stored = list(arc.load("dolt-chain-SPY"))
    assert sum(r["value"]["stale"] is True for r in stored) == len(REC_2022_08_19)
    # closes passed in, no store; and no closes at all: rows stay unchecked
    fake(FakeDolt(chain=chain))
    rows = m.fetch_dolt_chains(None, "SPY", start="2022-08-22", end="2022-08-22", pace=0, with_commits=False,
                               closes=CLOSES_2022_WIDE, rates=DTB3_2022)
    assert {r["value"]["quote_date"] for r in rows} == {"2022-08-19"}
    fake(FakeDolt(chain=chain))
    st = {}
    rows = m.fetch_dolt_chains(None, "SPY", start="2022-08-22", end="2022-08-22", pace=0, with_commits=False, stats=st)
    assert {r["value"]["stale"] for r in rows} == {None} and st["stale"]["unchecked"] == 1
    fake(FakeDolt(chain=chain))
    rows = m.fetch_dolt_chains(arc, "SPY", start="2022-08-22", end="2022-08-22", pace=0, with_commits=False, stale_check=False, dry_run=True)
    assert {r["value"]["stale"] for r in rows} == {None}


def test_fetch_volhistory_in_git_licence_and_stale(fake, tmp_path):
    closes = _synthetic_closes()
    arc = _archive(tmp_path)
    arc.store("daily-history-XLE", "data", _daily_rows("XLE", closes), recipe="test fixture")
    h_prev = round(m.hv_close_to_close(closes, "2024-02-22"), 4)
    h_rule = round(m.hv_close_to_close(closes, "2024-02-23"), 4)
    vol = [dict(VOL_REC, date="2024-02-24", act_symbol="XLE", hv_current=f"{h_prev:.4f}"),
           dict(VOL_REC, date="2024-02-23", act_symbol="XLE", hv_current=f"{h_rule:.4f}"),
           dict(VOL_REC, date="2024-02-23", act_symbol="SPY")]
    fake(FakeDolt(vol=vol))
    st = {}
    rows = m.fetch_dolt_volhistory(arc, ["SPY", "XLE"], start="2024-02-20", end="2024-02-25", pace=0, with_commits=False, in_git=False, stats=st)
    got = {(r["value"]["symbol"], r["value"]["snapshot_date"]): (r["value"]["quote_date"], r["value"]["stale"]) for r in rows}
    assert got == {("XLE", "2024-02-24"): ("2024-02-22", True), ("XLE", "2024-02-23"): ("2024-02-23", False),
                   ("SPY", "2024-02-23"): ("2024-02-23", None)}                          # no daily-history-SPY in this archive
    assert st["stale"]["closes_symbols"] == ["XLE"] and st["stale"]["moved"] == 1
    e = arc.get("dolt-volhistory")
    assert e.in_git is False and "cc-by-sa-4.0" in e.tags and "CC BY-SA 4.0" in e.recipe and "ShareAlike" in e.recipe
