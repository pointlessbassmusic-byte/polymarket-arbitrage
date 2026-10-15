"""options_misc: box rates (T-188), OPEC announcement dates (T-518), Deribit option trades around catalysts (T-222) and
Tardis first-of-month box legs (T-260). Parsing, point-in-time dating, target-expiry choice, paging, merging and storage
on mocked transports; no network.

Fixtures: the Känzig rows are recorded from oilSupplyNewsShocks_2025M12.xlsx (CC BY 4.0; Känzig 2021 AER,
doi:10.1257/aer.20190964). The box-rate values, Deribit trades and Tardis messages are synthetic in the sources' exact
formats (the box file is CC BY-NC-ND and Tardis data may not be redistributed, so none of it is copied here)."""

import gzip
import io
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import openpyxl
import pytest

from mandel.archive import Archive
from mandel.data import options_misc as om
from mandel.data.store import ObservationStore
from mandel.ledger import Ledger


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(om, "_sleep", lambda s: None)


def _archive(tmp_path: Path) -> Archive:
    return Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))


def _xlsx(sheets: dict[str, list[tuple]]) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _q(req: httpx.Request) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}


# ================================================================== box rates ==

BOX_HEADER = ("year", "month", "day", "box_6m", "box_12m", "box_18m", "gov_6m", "gov_12m", "gov_18m", None, None)
BOX_XLSX = _xlsx({
    "box_gov_l": [BOX_HEADER,
                  (2004, 1, 2, 1.30, 1.50, 1.90, 1.10, 1.30, 1.60, None, None),
                  (2004, 1, 5, 1.31, 1.51, None, 1.11, 1.31, 1.61, None, None),       # a missing rate is left out
                  (2004, 2, 30, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, None, None),            # invalid date: dropped
                  ("note", None, None, None, None, None, None, None, None, None, None),
                  (2018, 3, 19, 2.40, 2.55, 2.55, 2.00, 2.11, 2.22, None, None),
                  (2004, 1, 5, 1.32, 1.52, 1.92, 1.12, 1.32, 1.62, None, None)],     # duplicate day: the last wins
    "Notes": [("Box rates are SPX implied rates",), ("All yields are continuously compounded and annualized",)]})
# shape of the LBS Research Online landing page (EPrints): <th>Date Deposited:</th><td>23 Nov 2021 13:58</td>
BDG_HTML = ('<li class="list-group-item">Available under License <a href="http://creativecommons.org/licenses/by-nc-nd/4.0/">'
            '<img src="/images/licenses/by-nc-nd.png" /></a></li><table><tr>\n  <th align="right">\n    Date Deposited:</th>\n'
            '  <td valign="top">\n    23 Nov 2021 13:58\n  </td>\n</tr></table>')


def test_parse_box_rates():
    rows = om.parse_box_rates(BOX_XLSX)
    assert [r["day"] for r in rows] == ["2004-01-02", "2004-01-05", "2018-03-19"]
    assert rows[0] == {"day": "2004-01-02", "box_6m": 1.30, "box_12m": 1.50, "box_18m": 1.90, "gov_6m": 1.10, "gov_12m": 1.30, "gov_18m": 1.60}
    assert rows[1]["box_6m"] == 1.32 and rows[1]["box_18m"] == 1.92                    # the later duplicate replaced the earlier
    one = om.parse_box_rates(_xlsx({"box_gov_l": [BOX_HEADER, (2004, 1, 6, 1.3, 1.5, None, 1.1, 1.3, 1.6)]}))
    assert "box_18m" not in one[0] and one[0]["gov_18m"] == 1.6


def test_bdg_page_deposit_date_and_licence():
    meta = om.parse_bdg_page(BDG_HTML)
    assert meta == {"deposited": "2021-11-23T13:58:00+00:00", "licence": "https://creativecommons.org/licenses/by-nc-nd/4.0/"}
    summer = om.parse_bdg_page("<th>Date Deposited:</th><td>5 Jul 2021 10:00</td>")
    assert summer["deposited"] == "2021-07-05T09:00:00+00:00"                          # BST -> UTC
    assert om.parse_bdg_page("<html>nothing</html>") == {}


def _box_client(calls: list, page_status: int = 200):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if req.url.path.endswith(".xlsx"):
            return httpx.Response(200, content=BOX_XLSX)
        return httpx.Response(page_status, text=BDG_HTML if page_status == 200 else "gone")
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_box_rates_one_publication_date_out_of_git(tmp_path):
    a, calls, rep = _archive(tmp_path), [], {}
    rows = om.fetch_box_rates_bdg(a, client=_box_client(calls), min_interval=0, backoff=0, report=rep)
    assert len(calls) == 2 and len(rows) == 3
    assert {r["available_at"] for r in rows} == {"2021-11-23T13:58:00+00:00"}           # publication date for every row
    assert all(r["available_at"] <= r["observed_at"] and r["kind"] == "box-rate" and r["key"] == r["value"]["day"] for r in rows)
    e = a.get("box-rates-bdg")
    assert e.in_git is False and e.rows == 3 and "research-series" in e.tags and "not-point-in-time" in e.tags
    assert "box_gov_07302019.xlsx" in e.recipe and "by-nc-nd" in e.recipe and "2018-03-19" in e.recipe and "deposit" in e.recipe
    assert "available_at = the LBS deposit date" in e.schema
    assert [r["value"] for r in a.load("box-rates-bdg")] == [r["value"] for r in rows]
    assert rep["coverage"]["first"] == "2004-01-02" and rep["coverage"]["licence"].endswith("by-nc-nd/4.0/")


def test_box_rates_page_fallback_limit_and_dry_run(tmp_path):
    a = _archive(tmp_path)
    rows = om.fetch_box_rates_bdg(a, client=_box_client([], page_status=404), min_interval=0, backoff=0, limit=2)
    assert len(rows) == 2 and {r["available_at"] for r in rows} == {om.BDG_DEPOSITED}
    assert a.entries() == []                                                              # a limited preview is never stored
    calls, rep = [], {}
    assert om.fetch_box_rates_bdg(a, dry_run=True, client=_box_client(calls), report=rep) == [] and calls == []
    assert rep["_plan"]["calls"] == 2


# ============================================================ OPEC announcements ==

KZ_HEADER = ("Date/Contract", "Front", "1M", "2M", "3M", "4M", "5M", "6M", "7M", "8M", "9M", "10M", "11M", "12M", "PC")


def _kz_row(day, front, pc):
    return (datetime.fromisoformat(day), front, front, front, front, front, front, front, front, front, front, front, front, front, pc)


# recorded from oilSupplyNewsShocks_2025M12.xlsx (Front and PC columns; the other contracts are set to Front here)
KZ_XLSX = _xlsx({
    "Daily (pre-Covid)": [KZ_HEADER, _kz_row("1983-07-19", -0.25268491019085104, 0.18540973860535853)],
    "Monthly (pre-Covid)": [("Date", "Oil supply surprise series", "Oil supply news shock"), ("1975M01", 0, -0.44017160994746324)],
    "Daily": [KZ_HEADER, _kz_row("1983-07-19", -0.25268491019085104, 0.20094261628094226),
              _kz_row("2025-10-05", 1.321712966811731, 1.3729077319203784),            # Sunday
              ("text", None), _kz_row("2025-11-02", 0.11472589966041369, 0.5918510003004559),   # Sunday
              _kz_row("2025-12-01", 1.3065595803199699, 1.4648009173008574)],
    "Monthly": [("Date", "Oil supply surprise series", "Oil supply news shock"), ("2025M12", 1.4648009173008574, -0.336251677400647)]})


def test_parse_kanzig_and_point_in_time_rows():
    parsed = om.parse_kanzig(KZ_XLSX)
    assert [p["day"] for p in parsed] == ["1983-07-19", "2025-10-05", "2025-11-02", "2025-12-01"]
    first = parsed[0]
    assert first["in_pre_covid_sheet"] and first["pc_pre_covid"] == pytest.approx(0.18540973860535853) and first["surprise"]["PC"] == pytest.approx(0.20094261628094226)
    assert set(first["surprise"]) == set(KZ_HEADER[1:]) and parsed[-1]["pc_pre_covid"] is None and not parsed[-1]["in_pre_covid_sheet"]
    obs, pub = "2026-10-15T12:00:00+00:00", "2026-06-09T23:02:14+00:00"
    rows = om.opec_rows(parsed, "2025M12", obs, pub)
    ev = {r["key"]: r for r in rows if r["kind"] == "opec-announcement"}
    su = {r["value"]["day"]: r for r in rows if r["kind"] == "oil-supply-surprise"}
    assert ev["2025-10-05"]["available_at"] == "2025-10-05T00:00:00+00:00"              # the meeting date itself
    assert ev["2025-10-05"]["value"]["weekday"] == "Sun" and ev["2025-10-05"]["value"]["effective_weekday"] == "2025-10-06"
    assert ev["2025-12-01"]["value"]["effective_weekday"] == "2025-12-01"
    assert all(r["available_at"] == pub for r in su.values())                           # values only once the vintage is published
    assert su["2025-12-01"]["value"]["surprise"]["PC"] == pytest.approx(1.4648009173008574) and su["2025-12-01"]["key"] == "2025-12-01:2025M12"
    late = om.opec_rows(parsed[-1:], "2025M12", obs, "2025-11-01T00:00:00+00:00")       # never before the end of its own day
    assert [r["available_at"] for r in late if r["kind"] == "oil-supply-surprise"] == ["2025-12-01T23:59:59+00:00"]
    assert om.KANZIG_PUBLISHED["2025M12"] == pub and om.KANZIG_PUBLISHED["2024M06"] == "2024-12-03T01:19:04+00:00"


def _kz_client(calls: list, api_status: int = 403):
    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if req.url.host == "raw.githubusercontent.com":
            return httpx.Response(200, content=KZ_XLSX)
        if api_status == 200:
            return httpx.Response(200, json=[{"commit": {"committer": {"date": "2026-06-09T23:02:14Z"}}}])
        return httpx.Response(api_status, json={"message": "blocked"})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_opec_stores_and_uses_commit_time(tmp_path):
    a, calls, rep = _archive(tmp_path), [], {}
    rows = om.fetch_opec_announcements(ObservationStore(a), client=_kz_client(calls, 200), min_interval=0, backoff=0, report=rep)
    assert len(rows) == 8 and rep["coverage"]["published_basis"] == "github-api" and rep["coverage"]["weekend"] == 2
    assert any("oilSupplyNewsShocks_2025M12.xlsx" in u for u in calls) and any("api.github.com" in u for u in calls)
    e = a.get("opec-announcements")
    assert e.in_git and e.rows == 8 and "T-518" in e.tags and "CC BY 4.0" in e.recipe and "00:00 UTC" in e.recipe
    assert {r["available_at"] for r in a.load("opec-announcements") if r["kind"] == "oil-supply-surprise"} == {"2026-06-09T23:02:14+00:00"}


def test_fetch_opec_api_blocked_falls_back_and_limit_not_stored(tmp_path):
    a, rep = _archive(tmp_path), {}
    rows = om.fetch_opec_announcements(a, client=_kz_client([], 403), min_interval=0, backoff=0, report=rep, limit=2)
    assert rep["coverage"]["published_basis"].startswith("git-log constant") and len(rows) == 4
    assert [r["value"]["day"] for r in rows if r["kind"] == "opec-announcement"] == ["2025-11-02", "2025-12-01"]   # most recent N
    assert a.entries() == []
    rows = om.fetch_opec_announcements(a, vintage="2030M06", client=_kz_client([], 403), min_interval=0, backoff=0, report=rep)
    assert rep["coverage"]["published_basis"].startswith("fetch time")                  # unknown vintage: fetch time, never earlier
    assert {r["available_at"] for r in rows if r["kind"] == "oil-supply-surprise"} == {r["observed_at"] for r in rows}


# ========================================================== Deribit catalysts ==

def test_instrument_names():
    assert om.parse_instrument("BTC-26APR24-60000-C") == {"currency": "BTC", "expiry": "2024-04-26", "expiry_code": "26APR24", "strike": 60000.0, "type": "call"}
    assert om.parse_instrument("ETH-6AUG21-2500-P")["expiry"] == "2021-08-06"
    assert om.parse_instrument("XRP-27JUN25-2d5-C")["strike"] == 2.5
    assert om.parse_instrument("BTC-PERPETUAL") is None and om.parse_instrument("BTC-31FEB24-1-C") is None
    assert om.expiry_code(om._ms("2024-04-26T08:00:00+00:00")) == "26APR24" and om.expiry_code(om._ms("2021-08-06T08:00:00Z")) == "6AUG21"


def test_catalyst_calendar_integrity():
    ids = [c["id"] for c in om.CATALYSTS]
    assert len(ids) == len(set(ids)) == 19
    for c in om.CATALYSTS:
        t = datetime.fromisoformat(c["time"])
        assert t.tzinfo is not None and c["time_basis"]
        assert (t.date() - date.fromisoformat(c["date"])).days in (0, 1)              # elections: midnight ET is the next UTC day
        assert set(c["currencies"]) <= {"BTC", "ETH"} and c["category"] in {"fork", "protocol", "halving", "macro", "etf"}
        if c["known_since"]:
            assert c["known_since"] < c["date"] and c["known_since_basis"]
        else:
            assert "unverified" in c["known_since_hint"]
    for cid, epoch in om.BEACON_EPOCHS.items():                                         # epoch-based upgrade times
        c = next(x for x in om.CATALYSTS if x["id"] == cid)
        assert datetime.fromisoformat(c["time"]) == datetime.fromtimestamp(om.BEACON_GENESIS + 384 * epoch, timezone.utc)
    assert len(om.catalyst_windows()) == 21


def _inst(cur, exp, created, strikes=(100.0,), period="week"):
    code = om.expiry_code(om._ms(exp))
    return [{"instrument_name": f"{cur}-{code}-{int(k)}-{cp}", "strike": k, "option_type": "call" if cp == "C" else "put",
             "expiration_timestamp": om._ms(exp), "creation_timestamp": om._ms(created), "settlement_period": period}
            for k in strikes for cp in ("C", "P")]


CAT = {"id": "test-fork", "currencies": ["ETH"], "category": "protocol", "event": "test fork", "date": "2024-03-13",
       "time": "2024-03-13T13:55:35+00:00", "time_basis": "test", "known_since": "2024-02-08", "known_since_basis": "test"}
# entry day 2024-02-21; window [2024-02-20, 2024-03-15)
ETH_INSTRUMENTS = (_inst("ETH", "2024-03-08T08:00:00+00:00", "2024-01-01") +                 # expires before the event
                   _inst("ETH", "2024-03-13T08:00:00+00:00", "2024-02-01", period="day") +   # event day, but before the event time
                   _inst("ETH", "2024-03-14T08:00:00+00:00", "2024-03-11", period="day") +   # after the event, listed after entry
                   _inst("ETH", "2024-03-15T08:00:00+00:00", "2024-02-21T08:00:00+00:00") +  # listed during the entry day: the target
                   _inst("ETH", "2024-03-29T08:00:00+00:00", "2023-03-30", strikes=(100.0, 200.0), period="month"))


def test_window_bounds_and_target_expiry():
    listings = {"ETH": om.expiry_listings(ETH_INSTRUMENTS)}
    assert listings["ETH"][om._ms("2024-03-29T08:00:00+00:00")] == {"listed_at": om._ms("2023-03-30"), "n_instruments": 4, "settlement_period": "month"}
    (w,) = om.catalyst_windows([CAT], listings)
    assert w["start_ms"] == om._ms("2024-02-20") and w["end_ms"] == om._ms("2024-03-15") and w["entry_day"] == "2024-02-21" and w["exit_day"] == "2024-03-12"
    assert [t["expiry_code"] for t in w["targets"]] == ["15MAR24"]
    (w2,) = om.catalyst_windows([CAT], listings, n_expiries=2)
    assert [t["expiry_code"] for t in w2["targets"]] == ["15MAR24", "29MAR24"]
    late = {**CAT, "date": "2024-03-14", "time": "2024-03-14T23:00:00+00:00"}           # entry 2024-02-22 23:59 > listing: still eligible
    assert [t["expiry_code"] for t in om.catalyst_windows([late], listings)[0]["targets"]] == ["15MAR24"]
    assert om.catalyst_windows([CAT], None)[0]["targets"] is None and om.catalyst_windows([CAT], currencies=["BTC"]) == []


def _trade(tid, ts, name, price=0.05):
    return {"trade_seq": tid, "trade_id": str(tid), "timestamp": ts, "tick_direction": 0, "price": price, "mark_price": price,
            "iv": 60.0, "instrument_name": name, "index_price": 3500.0, "direction": "buy", "amount": 1.0}


def _tape():
    """Synthetic tape over the window: every 6 hours one trade in the target and one in another expiry, plus a burst of
    four trades in the same millisecond to exercise the page boundary, and trades just outside the window."""
    t0, t1 = om._ms("2024-02-20"), om._ms("2024-03-15")
    out, tid = [_trade(1, t0 - 1, "ETH-15MAR24-100-C")], 2
    t = t0
    while t < t1:
        out.append(_trade(tid, t, "ETH-15MAR24-100-C")); out.append(_trade(tid + 1, t + 1000, "ETH-29MAR24-200-P")); tid += 2
        t += 6 * 3_600_000
    burst = om._ms("2024-03-01T12:00:00+00:00") + 7
    out += [_trade(tid + i, burst, "ETH-15MAR24-100-P") for i in range(4)]
    out.append(_trade(tid + 10, t1, "ETH-15MAR24-100-C"))                              # end is exclusive
    return sorted(out, key=lambda x: (x["timestamp"], int(x["trade_id"])))


def _deribit_client(calls: list, tape: list, page: int = 5, instruments=None, fail_pages: set | None = None):
    fail_pages = set(fail_pages or ())

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        q = _q(req)
        if req.url.path.endswith("get_instruments"):
            return httpx.Response(200, json={"result": instruments if q.get("expired") == "true" else []})
        n = len([u for u in calls if "get_last_trades" in u])
        if n in fail_pages:
            return httpx.Response(503, text="busy")
        assert q["sorting"] == "asc" and q["kind"] == "option" and q["include_old"] == "true"
        s, e = int(q["start_timestamp"]), int(q["end_timestamp"])
        sel = [x for x in tape if s <= x["timestamp"] <= e]
        return httpx.Response(200, json={"jsonrpc": "2.0", "result": {"trades": sel[:page], "has_more": len(sel) > page}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_trades_paging_dedupes_boundary_and_filters_window():
    tape, calls = _tape(), []
    kept, info = om.trades_in_window("ETH", om._ms("2024-02-20"), om._ms("2024-03-15"), _deribit_client(calls, tape), om.Throttle(0), backoff=0)
    inside = [x for x in tape if om._ms("2024-02-20") <= x["timestamp"] < om._ms("2024-03-15")]
    assert info["complete"] and info["seen"] == len(kept) == len(inside) and len({x["trade_id"] for x in kept}) == len(kept)
    assert sum(1 for x in kept if x["instrument_name"] == "ETH-15MAR24-100-P") == 4             # burst crossing a page boundary
    assert info["pages"] == len(calls) > len(inside) // 5
    kept, info = om.trades_in_window("ETH", om._ms("2024-02-20"), om._ms("2024-03-15"), _deribit_client([], tape), om.Throttle(0), max_pages=2, backoff=0)
    assert not info["complete"] and info["stopped"] == "max_pages" and len(kept) == 9           # page 2 re-reads the boundary ms
    kept, info = om.trades_in_window("ETH", om._ms("2024-02-20"), om._ms("2024-03-15"), _deribit_client([], tape, fail_pages={3, 4, 5}),
                                     om.Throttle(0), retries=3, backoff=0)
    assert not info["complete"] and info["error"]["status"] == 503 and len(kept) == 9


def test_fetch_catalyst_trades_rows_store_and_merge(tmp_path):
    a, tape, calls, rep = _archive(tmp_path), _tape(), [], {}
    rows = om.fetch_deribit_catalyst_trades(a, catalysts=[CAT], client=_deribit_client(calls, tape, instruments=ETH_INSTRUMENTS),
                                            min_interval=0, backoff=0, report=rep)
    assert sum("get_instruments" in u for u in calls) == 2                               # expired + live lists
    trades = [r for r in rows if r["kind"] == "option-trade"]
    (win,) = [r for r in rows if r["kind"] == "catalyst-window"]
    assert trades and {r["value"]["expiry_code"] for r in trades} == {"15MAR24"}           # only the target expiry
    assert all(r["available_at"] == om._iso_ms(r["value"]["timestamp"]) <= r["observed_at"] for r in trades)
    assert trades[0]["value"]["strike"] == 100.0 and trades[0]["value"]["catalyst"] == "test-fork" and trades[0]["key"].startswith("ETH:")
    v = win["value"]
    assert win["available_at"] == "2024-02-08T00:00:00+00:00" and v["complete"] and v["target_expiry"] == "2024-03-15"
    assert v["target_listed_at"] == "2024-02-21T08:00:00.000+00:00" and v["trades_kept"] == len(trades) and v["trades_seen"] > len(trades)
    e = a.get("deribit-option-trades-catalysts")
    assert e.in_git is False and e.rows == len(rows) and "test-fork:ETH" in e.recipe and "sorting=asc" in e.recipe and "T-222" in e.tags
    # a second window merges in; an unverified catalyst's window row is dated at the event itself
    cat2 = {**CAT, "id": "other", "known_since": None, "known_since_hint": "x (unverified)"}
    om.fetch_deribit_catalyst_trades(a, catalysts=[cat2], instruments={"ETH": ETH_INSTRUMENTS}, client=_deribit_client([], tape),
                                     min_interval=0, backoff=0)
    stored = list(a.load("deribit-option-trades-catalysts"))
    wins = {r["key"]: r for r in stored if r["kind"] == "catalyst-window"}
    assert set(wins) == {"test-fork:ETH", "other:ETH"} and wins["other:ETH"]["available_at"] == "2024-03-13T13:55:35.000+00:00"
    assert len(stored) == 2 * len(rows)
    # an incomplete (preview) window never replaces the stored one
    om.fetch_deribit_catalyst_trades(a, catalysts=[CAT], instruments={"ETH": ETH_INSTRUMENTS}, client=_deribit_client([], tape),
                                     max_pages=1, min_interval=0, backoff=0)
    assert len(list(a.load("deribit-option-trades-catalysts"))) == len(stored)


def test_catalyst_interrupt_keeps_complete_windows_and_resume_skips_them(tmp_path):
    a, tape = _archive(tmp_path), _tape()
    pages = []
    om.trades_in_window("ETH", om._ms("2024-02-20"), om._ms("2024-03-15"), _deribit_client(pages, tape), om.Throttle(0), backoff=0)
    calls = []
    inner = _deribit_client(calls, tape)

    def handler(req):
        if len([u for u in calls if "get_last_trades" in u]) >= len(pages):              # the second window is interrupted
            raise RuntimeError("interrupted")
        return inner.get(str(req.url))
    cat2 = {**CAT, "id": "other"}
    with pytest.raises(RuntimeError):
        om.fetch_deribit_catalyst_trades(a, catalysts=[CAT, cat2], instruments={"ETH": ETH_INSTRUMENTS},
                                         client=httpx.Client(transport=httpx.MockTransport(handler)), min_interval=0, backoff=0, retries=1)
    assert {r["key"] for r in a.load("deribit-option-trades-catalysts") if r["kind"] == "catalyst-window"} == {"test-fork:ETH"}
    rep, calls2 = {}, []
    om.fetch_deribit_catalyst_trades(a, catalysts=[CAT, cat2], instruments={"ETH": ETH_INSTRUMENTS}, client=_deribit_client(calls2, tape),
                                     min_interval=0, backoff=0, report=rep, skip_stored=True)
    assert rep["_already_stored"] == ["test-fork:ETH"] and "test-fork:ETH" not in rep and rep["other:ETH"]["complete"]
    assert {r["key"] for r in a.load("deribit-option-trades-catalysts") if r["kind"] == "catalyst-window"} == {"test-fork:ETH", "other:ETH"}


def test_catalyst_dry_run_plan_and_limit():
    calls, rep = [], {}
    assert om.fetch_deribit_catalyst_trades(None, dry_run=True, client=_deribit_client(calls, []), report=rep) == [] and calls == []
    plan = rep["_plan"]
    assert plan["windows"] == 21 and plan["est_calls"] > 1000 and plan["instrument_calls"] == 4          # expired + live, BTC and ETH
    assert {p["window"] for p in plan["per_window"]} >= {"btc-halving-2024:BTC", "eth-merge-2022:ETH", "us-election-2020:ETH"}
    rep = {}
    om.fetch_deribit_catalyst_trades(None, dry_run=True, limit=3, currencies=["ETH"], report=rep)
    assert [p["window"].split(":")[1] for p in rep["_plan"]["per_window"]] == ["ETH"] * 3


def test_missing_instrument_list_skips_window():
    rep = {}
    rows = om.fetch_deribit_catalyst_trades(None, catalysts=[CAT], client=_deribit_client([], _tape(), instruments=[]), min_interval=0, backoff=0, report=rep)
    assert rows == [] and "skipped" in rep["test-fork:ETH"]


# ======================================================================= Tardis ==

DAY = "2024-03-01"
BTC_INSTRUMENTS = (_inst("BTC", "2024-03-29T08:00:00+00:00", "2023-12-28", strikes=(60000.0, 61000.0, 62000.0)) +   # 28 DTE: too near
                   _inst("BTC", "2024-04-26T08:00:00+00:00", "2024-01-18", strikes=(58000.0, 59000.0, 60000.0, 61000.0, 62000.0, 63000.0, 64000.0)) +
                   [x for x in _inst("BTC", "2024-04-26T08:00:00+00:00", "2024-01-18", strikes=(61500.0,)) if x["option_type"] == "call"] +  # call only
                   _inst("BTC", "2024-04-26T08:00:00+00:00", "2024-03-02", strikes=(61200.0,)) +             # listed after the capture
                   _inst("BTC", "2024-05-31T08:00:00+00:00", "2023-11-30", strikes=(50000.0, 70000.0)) +     # 91.3 DTE: too far
                   _inst("BTC", "2024-02-23T08:00:00+00:00", "2024-01-01"))                                   # expired before


def test_select_box_legs():
    legs = om.select_box_legs(BTC_INSTRUMENTS, DAY, spot=61173.0)
    assert len(legs) == 1
    (L,) = legs
    assert L["expiry_code"] == "26APR24" and round(L["dte"], 2) == 56.33 and L["strikes"] == [60000.0, 61000.0, 62000.0, 63000.0]
    assert L["instruments"][:2] == ["BTC-26APR24-60000-C", "BTC-26APR24-60000-P"] and len(L["instruments"]) == 8
    assert om.select_box_legs(BTC_INSTRUMENTS, DAY, spot=61173.0, n_side=1)[0]["strikes"] == [61000.0, 62000.0]
    assert om.select_box_legs(BTC_INSTRUMENTS, DAY, spot=61000.0, n_side=1)[0]["strikes"] == [61000.0, 62000.0]   # at the money counts as below
    assert om.select_box_legs(BTC_INSTRUMENTS, DAY, spot=10.0) == []                                              # nothing below the spot
    assert len(om.box_capture_days("2019-04-01", "2026-10-15")) == 91 and om.box_capture_days("2019-03-30", "2019-05-01") == ["2019-04-01", "2019-05-01"]


def _ticker_line(ts: str, name: str, bid: float, ask: float, stamp_ms: int) -> str:
    data = {"instrument_name": name, "best_bid_price": bid, "best_ask_price": ask, "mark_price": (bid + ask) / 2, "index_price": 61000.0,
            "underlying_price": 62900.0, "underlying_index": "BTC-26APR24", "timestamp": stamp_ms, "greeks": {"delta": 0.5}}
    return ts + " " + json.dumps({"jsonrpc": "2.0", "method": "subscription", "params": {"channel": f"ticker.{name}.raw", "data": data}})


def _feed(symbols, missing=()):
    lines = []
    for i, s in enumerate(symbols):
        if s in missing:
            continue
        lines.append(_ticker_line(f"2024-03-01T00:00:00.{i:03d}1578Z", s, 0.1, 0.11, 1709251199983))
        lines.append(_ticker_line(f"2024-03-01T00:00:3{i % 10}.5000001Z", s, 0.12, 0.13, 1709251230000))
    lines.append('2024-03-01T00:00:59.9Z {"jsonrpc":"2.0","method":"heartbeat"}')
    return "\n".join(lines) + "\n\n"


def test_parse_tardis_and_snapshots():
    lines = om.parse_tardis(_feed(["BTC-26APR24-60000-C", "BTC-26APR24-60000-P"]) + "garbage line\n2024-03-01T00:00:01Z {bad json\n")
    assert lines[0][0] == "2024-03-01T00:00:00.000157+00:00" and len(lines) == 5          # 7-digit fraction truncated to microseconds
    snaps = om.ticker_snapshots(lines)
    s = snaps["BTC-26APR24-60000-C"]
    assert s["n"] == 2 and s["first"][1]["best_bid_price"] == 0.1 and s["last"][1]["best_bid_price"] == 0.12
    assert json.loads(om.tardis_filters(["A", "B"])) == [{"channel": "ticker", "symbols": ["A", "B"]}]
    with pytest.raises(ValueError):
        om.tardis_minute("2024-03-02", ["A"], httpx.Client(), om.Throttle(0))


def _tardis_client(calls: list, missing=(), fail_429=0, deny_days=()):
    state = {"429": fail_429}

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        q = _q(req)
        if req.url.host == "www.deribit.com":                                           # spot hint: 1h bars, the last one ends after the capture
            t = int(q["end_timestamp"])
            ticks = [t - 3 * 3_600_000, t - 2 * 3_600_000, t - 3_600_000, t]
            return httpx.Response(200, json={"result": {"status": "ok", "ticks": ticks, "close": [60000.0, 60500.0, 61173.0, 99999.0]}})
        assert req.url.host == "api.tardis.dev" and q["offset"] == "0"
        if q["from"] in deny_days:
            return httpx.Response(401, json={"code": 10, "message": "For unauthorized requests, only ... first day of each month"})
        if state["429"]:
            state["429"] -= 1
            return httpx.Response(429, headers={"retry-after": "12"}, json={"code": 276})
        syms = json.loads(q["filters"])[0]["symbols"]
        body = gzip.compress(_feed(syms, missing).encode())
        return httpx.Response(200, content=body, headers={"content-encoding": "gzip", "x-name": f"deribit/{q['from'].replace('-', '/')}/00/00"})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_spot_hint_uses_only_bars_ended_by_capture():
    assert om.spot_hint(DAY, _tardis_client([]), om.Throttle(0), backoff=0) == 61173.0


def test_fetch_tardis_rows_store_merge_and_failures(tmp_path):
    a, calls, rep = _archive(tmp_path), [], {}
    rows = om.fetch_tardis_box_monthly(a, days=[DAY], instruments=BTC_INSTRUMENTS, client=_tardis_client(calls, fail_429=1),
                                       min_interval=0, backoff=0, report=rep)
    assert rep[DAY]["status"] == "ok" and rep[DAY]["attempts"] == 2 and rep[DAY]["received"] == 8 and rep[DAY]["x_name"] == "deribit/2024/03/01/00/00"
    tick = [r for r in rows if r["kind"] == "option-ticker"]
    (cap,) = [r for r in rows if r["kind"] == "capture"]
    assert len(tick) == 16 and {r["value"]["snap"] for r in tick} == {"first", "last"}
    first = next(r for r in tick if r["key"] == f"{DAY}:BTC-26APR24-61000-P:first")
    assert first["available_at"] == first["value"]["local_timestamp"] == "2024-03-01T00:00:00.003157+00:00"
    assert first["value"]["ticker"]["best_ask_price"] == 0.11 and first["value"]["type"] == "put" and first["value"]["spot_hint"] == 61173.0
    assert cap["value"]["strikes"] == {"26APR24": [60000.0, 61000.0, 62000.0, 63000.0]} and cap["available_at"] == "2024-03-01T00:01:00+00:00"
    e = a.get("deribit-box-monthly")
    assert e.in_git is False and "Tardis.dev licence" in e.recipe and "no redistribution" in e.recipe and "T-260" in e.tags
    # next month merges in; a 401 day and an empty day are reported and not stored; a partial day is stored as partial
    nxt = "2024-04-01"
    insts = BTC_INSTRUMENTS + _inst("BTC", "2024-05-31T08:00:00+00:00", "2024-01-01", strikes=(60000.0, 62000.0))
    rep2 = {}
    om.fetch_tardis_box_monthly(a, days=[nxt, "2024-05-01"], instruments=insts, spots={nxt: 61000.0, "2024-05-01": 61000.0},
                                client=_tardis_client([], missing={"BTC-31MAY24-62000-C"}, deny_days={"2024-05-01"}), min_interval=0, backoff=0, report=rep2)
    assert rep2[nxt]["status"] == "partial" and rep2["2024-05-01"]["status"] == "empty" and rep2["2024-05-01"]["attempts"] == 1
    stored = list(a.load("deribit-box-monthly"))
    assert sorted({r["value"]["capture_day"] for r in stored}) == [DAY, nxt]
    assert len([r for r in stored if r["value"]["capture_day"] == DAY]) == len(rows)


def test_tardis_skip_stored_fetches_only_new_days(tmp_path):
    a = _archive(tmp_path)
    om.fetch_tardis_box_monthly(a, days=[DAY], instruments=BTC_INSTRUMENTS, spots={DAY: 61173.0}, client=_tardis_client([]), min_interval=0, backoff=0)
    calls, rep = [], {}
    nxt = "2024-04-01"
    om.fetch_tardis_box_monthly(a, days=[DAY, nxt], instruments=BTC_INSTRUMENTS, spots={nxt: 61000.0}, client=_tardis_client(calls),
                                min_interval=0, backoff=0, report=rep, skip_stored=True)
    assert rep["_already_stored"] == [DAY] and DAY not in rep and len(calls) == 1 and "from=2024-04-01" in calls[0]
    assert sorted({r["value"]["capture_day"] for r in a.load("deribit-box-monthly")}) == [DAY, nxt]


def test_tardis_transfer_limit_aborts_without_retrying(tmp_path):
    calls = []

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(429, json={"code": 277, "message": "This account has reached its data transfer limit.", "retryAfterSeconds": 45818})
    a, rep = _archive(tmp_path), {}
    rows = om.fetch_tardis_box_monthly(a, days=[DAY, "2024-04-01"], instruments=BTC_INSTRUMENTS, spots={DAY: 61173.0, "2024-04-01": 61000.0},
                                       client=httpx.Client(transport=httpx.MockTransport(handler)), min_interval=0, backoff=0, report=rep)
    assert rows == [] and len(calls) == 1 and rep[DAY]["attempts"] == 1 and rep[DAY]["retry_after"] == 45818
    assert rep["_aborted"]["day"] == DAY and "2024-04-01" not in rep and a.entries() == []


def test_tardis_dry_run_and_no_legs():
    calls, rep = [], {}
    assert om.fetch_tardis_box_monthly(None, dry_run=True, client=_tardis_client(calls), report=rep) == [] and calls == []
    assert rep["_plan"]["days"] >= 91 and rep["_plan"]["first"] == "2019-04-01" and rep["_plan"]["instrument_mb"] == 77
    rep = {}
    assert om.fetch_tardis_box_monthly(None, days=["2019-04-01"], instruments=BTC_INSTRUMENTS, spots={"2019-04-01": 4100.0},
                                       client=_tardis_client(calls), min_interval=0, backoff=0, report=rep) == []
    assert "skipped" in rep["2019-04-01"] and calls == []


# ===================================================================== helpers ==

def test_get_retries_then_final_status():
    seq = iter([503, 503, 200])
    c = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(next(seq), text="ok")))
    r, info = om._get(c, "https://x.test/a", om.Throttle(0), retries=4, backoff=0)
    assert r is not None and info["attempts"] == 3
    c = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(404, text="nope")))
    r, info = om._get(c, "https://x.test/a", om.Throttle(0), retries=4, backoff=0)
    assert r is None and info["attempts"] == 1 and info["status"] == 404

    c = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(429, headers={"retry-after": "7200"}, text="later")))
    r, info = om._get(c, "https://x.test/a", om.Throttle(0), retries=4, backoff=0)
    assert r is None and info["attempts"] == 1 and info["retry_after"] == 7200.0          # a long block is final, not slept through

    def boom(req):
        raise httpx.ConnectError("down")
    r, info = om._get(httpx.Client(transport=httpx.MockTransport(boom)), "https://x.test/a", om.Throttle(0), retries=2, backoff=0)
    assert r is None and info["attempts"] == 2 and "ConnectError" in info["error"]
