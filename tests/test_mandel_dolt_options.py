"""DoltHub options fetcher: NYSE calendar and quote-date rule, row shaping, window walking under the 1000-row cap and
query deadlines, commit-log parsing, bundle merge, and the parity check on recorded SPY rows. No network."""

import re
from datetime import date, timedelta

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
    assert r["key"] == "SPY:2019-02-09:2019-02-22:C270.50" and v["dolt_commit_at"] is None
    assert m.chain_row(_raw(REC_2019_02_09[2]), "x", {"2021-05-03": "t"})["value"]["dolt_commit_at"] == m.BULK_IMPORT_AT
    nulls = _raw(REC_2019_02_09[3]); nulls["bid"] = None
    assert m.chain_row(nulls, "x")["value"]["bid"] is None
    vr = m.vol_row(VOL_REC, "x", {"2025-01-03": "2025-01-04T06:35:00+00:00"})
    assert vr["value"]["iv_current"] == 0.1513 and vr["value"]["hv_year_high_date"] == "2024-08-05"
    assert vr["value"]["quote_date"] == "2025-01-03" and vr["value"]["dolt_commit_at"] == "2025-01-04T06:35:00+00:00"


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
           {"date": "2021-10-07 06:55:57.800", "message": "option_chain 2021-10-06 update"},
           {"date": "2021-10-07 06:46:54.630", "message": "option_chain 2021-10-06 update"},       # re-run: keep the first
           {"date": "2022-06-01 07:22:37.395", "message": "get rid of bad memorial day data"},
           {"date": "2021-04-20 23:20:48.218", "message": "option_chain 2019-04-01 update"},
           {"date": "2021-04-20 23:18:54.935", "message": "Initialize data repository"}]
    fake(FakeDolt(log=log))
    with m._client() as c:
        oc = m.dolt_commit_times(c, m.Throttle(0), "option_chain", page=3)
        vh = m.dolt_commit_times(c, m.Throttle(0), "volatility_history", page=3)   # served from the one-pass cache
    assert oc == {"2026-10-14": "2026-10-15T06:34:53+00:00", "2021-10-06": "2021-10-07T06:46:54+00:00", "2019-04-01": "2021-04-20T23:20:48+00:00"}
    assert vh == {"2026-10-14": "2026-10-15T06:35:00+00:00"}
    assert m.commit_time_for("2020-03-02", oc) == m.BULK_IMPORT_AT and m.commit_time_for("2023-01-04", oc) is None


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


def test_parity_check_on_recorded_saturday_snapshot():
    rows = [m.chain_row(_raw(t), "x") for t in REC_2019_02_09]
    S = m.parity_spot(rows, "2019-02-09", rate=0.024)
    assert abs(S - 270.47) < 0.15                                     # Friday 2019-02-08 close
    res = m.parity_check(rows, CLOSES_2019, rate=0.024)
    assert len(res) == 1 and res[0]["best"] == "prev" and res[0]["matched_day"] == "2019-02-08" and res[0]["agrees_with_rule"]
