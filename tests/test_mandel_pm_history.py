"""mandel.data.pm_history on mocked HTTP only (httpx.MockTransport; no network): Gamma keyset day windows (lifetime filter,
inclusive end bound, month complete / partial, resume, failures never stored), the volume- and outcome-blind daily
selection, legacy row schemas (market_calibration runs on them), CLOB hourly windows (14 days, split on 'interval is too
long'), data-api end-paging (inclusive boundary de-duplicated, page cap, complete_from) and hourly taker volume, event
search paging, the templated FOMC / CPI / BTC / election pair matcher (listing fields only, point in time), Kalshi
listings (historical + live, KXBTCD daily events), Retry-After, candle and trade routing around the historical cutoff,
candle chunking, dry runs that make no request, licences (in_git False) and .gitignore lines."""

import json
from datetime import datetime, timezone
from fnmatch import fnmatch
from urllib.parse import parse_qsl, urlparse

import httpx
import pytest

from mandel.archive import Archive
from mandel.data import options_misc as om
from mandel.data import pm_history as m
from mandel.experiments.markets import market_calibration
from mandel.ledger import Ledger

UTC = timezone.utc
DAY = 86400
NOW = int(datetime(2026, 10, 15, 12, tzinfo=UTC).timestamp())


def ts(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def z(t: int) -> str:
    return datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def pm_market(mid, end, start, vol=50_000.0, q=None, toks=None, outcome="1", closed=None, cond=None, slug=None, ev=None, title=None):
    toks = toks or [f"tok{mid}y", f"tok{mid}n"]
    return {"id": str(mid), "question": q or f"Will thing {mid} happen?", "slug": slug or f"thing-{mid}", "conditionId": cond or f"0xc{mid}",
            "endDate": end, "startDate": start, "closedTime": closed or end.replace("T", " ").replace("Z", "+00"),
            "volumeNum": vol, "clobTokenIds": json.dumps(toks), "outcomes": json.dumps(["Yes", "No"]),
            "outcomePrices": json.dumps([outcome, "0" if outcome == "1" else "1"]), "umaResolutionStatus": "resolved",
            "events": [{"id": ev or f"e{mid}", "slug": f"ev-{mid}", "title": title or ""}], "description": "desc"}


def k_market(ticker, event, open_t, close_t, vol="5000.00", sub=None, floor=None, strike_type="greater", settle=None, rules="rules"):
    return {"ticker": ticker, "event_ticker": event, "open_time": open_t, "close_time": close_t, "settlement_ts": settle or close_t,
            "volume_fp": vol, "yes_sub_title": sub, "floor_strike": floor, "strike_type": strike_type, "rules_primary": rules,
            "status": "finalized", "result": "yes"}


# ------------------------------------------------------------------------------------------------ fake venues --

class Fake:
    """One handler for the four hosts. ``calls`` logs (host, path, params)."""

    def __init__(self, **cfg):
        self.cfg = cfg
        self.calls = []
        self.k429 = cfg.get("k_429", 0)

    def handler(self, req: httpx.Request) -> httpx.Response:
        if self.cfg.get("forbid"):
            raise AssertionError(f"unexpected request {req.url}")
        q = dict(parse_qsl(urlparse(str(req.url)).query))
        host, path = req.url.host, req.url.path
        self.calls.append((host, path, q))
        if host == "gamma-api.polymarket.com":
            return self.gamma(path, q)
        if host == "clob.polymarket.com":
            return self.clob(q)
        if host == "data-api.polymarket.com":
            return self.data(q)
        if host == "api.elections.kalshi.com":
            return self.kalshi(path, q)
        return httpx.Response(404, json={})

    def n(self, host, path=None):
        return sum(1 for h, p, _ in self.calls if h == host and (path is None or p == path))

    # -- Gamma
    def gamma(self, path, q):
        if path == "/markets/keyset":
            lo, hi = ts(q["end_date_min"]), ts(q["end_date_max"])
            if self.cfg.get("gamma_fail_day") == q["end_date_min"][:10]:
                return httpx.Response(500, json={"error": "boom"})
            rows = [x for x in self.cfg.get("markets", []) if lo <= ts(x["endDate"]) <= hi and float(x["volumeNum"]) >= float(q["volume_num_min"])
                    and ("start_date_max" not in q or ts(x["startDate"]) <= ts(q["start_date_max"]))]
            rows.sort(key=lambda x: int(x["id"]))
            i = int(q.get("after_cursor") or 0)
            page = rows[i:i + 2]                               # tiny pages: exercises the cursor
            nxt = str(i + 2) if i + 2 < len(rows) else None
            return httpx.Response(200, json={"markets": page, "next_cursor": nxt})
        if path == "/public-search":
            evs = [e for e in self.cfg.get("search", {}).get(q["q"], [])]
            per, p = int(q["limit_per_type"]), int(q["page"])
            chunk = evs[(p - 1) * 2:(p - 1) * 2 + 2]          # 2 per page
            return httpx.Response(200, json={"events": chunk, "pagination": {"hasMore": (p * 2) < len(evs), "totalResults": len(evs)}})
        if path == "/events":
            return httpx.Response(200, json=[e for e in self.cfg.get("events_by_slug", []) if e["slug"] == q.get("slug")])
        return httpx.Response(404, json={})

    # -- CLOB
    def clob(self, q):
        tok = q["market"]
        if tok in self.cfg.get("clob_fail", ()):
            return httpx.Response(500, json={"error": "boom"})
        hist = self.cfg.get("histories", {}).get(tok, [])
        if "interval" in q:
            return httpx.Response(200, json={"history": [{"t": t, "p": p} for t, p in hist]})
        s, e = int(q["startTs"]), int(q["endTs"])
        if e - s > self.cfg.get("clob_max_span", 14 * DAY):
            return httpx.Response(400, json={"error": "invalid filters: 'startTs' and 'endTs' interval is too long"})
        return httpx.Response(200, json={"history": [{"t": t, "p": p} for t, p in hist if s <= t <= e]})

    # -- data-api
    def data(self, q):
        assert q.get("takerOnly") == "true"
        trades = sorted(self.cfg.get("trades", {}).get(q["market"], []), key=lambda t: -t["timestamp"])
        if "end" in q:
            trades = [t for t in trades if t["timestamp"] <= int(q["end"])]
        return httpx.Response(200, json=trades[:int(q["limit"])])

    # -- Kalshi
    def kalshi(self, path, q):
        if self.k429:
            self.k429 -= 1
            return httpx.Response(429, headers={"Retry-After": "3"}, json={"error": {"code": "too_many_requests"}})
        if path == "/trade-api/v2/historical/cutoff":
            return httpx.Response(200, json={"market_settled_ts": "2026-08-16T00:00:00Z", "trades_created_ts": "2026-08-16T00:00:00Z"})
        if path in ("/trade-api/v2/historical/markets", "/trade-api/v2/markets"):
            src = self.cfg.get("k_hist" if "historical" in path else "k_live", [])
            if "series_ticker" in q:
                rows = [x for x in src if x["event_ticker"].split("-")[0] in (q["series_ticker"], q["series_ticker"].replace("KX", "", 1))
                        or x.get("_series") == q["series_ticker"]]
            else:
                rows = [x for x in src if x["event_ticker"] == q.get("event_ticker")]
            i = int(q.get("cursor") or 0)
            return httpx.Response(200, json={"markets": rows[i:i + 2], "cursor": str(i + 2) if i + 2 < len(rows) else ""})
        if path.endswith("/candlesticks"):
            t = path.split("/")[-2]
            route = "hist" if "/historical/" in path else "live"
            s, e, per = int(q["start_ts"]), int(q["end_ts"]), int(q["period_interval"])
            if (e - s) / (per * 60) > 5000:
                return httpx.Response(400, json={"error": {"details": "max candlesticks: 5000"}})
            cs = [c for c in self.cfg.get("k_candles", {}).get((route, t), []) if s <= c["end_period_ts"] <= e]
            return httpx.Response(200, json={"candlesticks": cs, "ticker": t})
        if path in ("/trade-api/v2/historical/trades", "/trade-api/v2/markets/trades"):
            route = "hist" if "historical" in path else "live"
            rows = self.cfg.get("k_trades", {}).get((route, q["ticker"]), [])
            i = int(q.get("cursor") or 0)
            return httpx.Response(200, json={"trades": rows[i:i + 2], "cursor": str(i + 2) if i + 2 < len(rows) else ""})
        return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def fake(monkeypatch):
    sleeps = []

    def make(**cfg):
        f = Fake(**cfg)
        monkeypatch.setattr(m, "_client", lambda: httpx.Client(transport=httpx.MockTransport(f.handler)))
        f.sleeps = sleeps
        return f
    monkeypatch.setattr(om, "_sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(m, "_sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(m, "_now_s", lambda: NOW)
    return make


def _archive(tmp_path):
    return Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))


FAST = {"min_interval": 0.0}


# ============================================================================================ Gamma markets ==

def test_gamma_day_window_lifetime_filter_and_inclusive_end(fake):
    mk = [pm_market(1, "2025-03-02T12:00:00Z", "2025-02-01T00:00:00Z"),
          pm_market(2, "2025-03-03T00:00:00Z", "2025-02-01T00:00:00Z"),            # exactly the next midnight: belongs to 03-03
          pm_market(3, "2025-03-02T18:00:00Z", "2025-03-01T00:00:00Z"),            # lived 1.75 days: excluded by start_date_max
          pm_market(4, "2025-03-02T20:00:00Z", "2025-02-01T00:00:00Z", vol=9_000), # below the volume floor
          pm_market(5, "2025-03-02T23:00:00Z", "2025-02-20T00:00:00Z"),
          pm_market(6, "2025-03-02T01:00:00Z", "2025-02-25T00:00:00Z")]
    f = fake(markets=mk)
    with m._client() as c:
        rows, calls, _ = m.gamma_day(c, m.Throttle(0), "2025-03-02")
    assert sorted(r["id"] for r in rows) == ["1", "5", "6"]
    assert calls == 2                                                           # two pages of 2 (ids 1, 2 | 5, 6) via after_cursor
    q = f.calls[0][2]
    assert q["start_date_max"] == "2025-02-27T00:00:00Z" and q["volume_num_min"] == "10000" and q["limit"] == "100"
    assert q["end_date_min"] == "2025-03-02T00:00:00Z" and q["end_date_max"] == "2025-03-03T00:00:00Z"
    assert "after_cursor" in f.calls[1][2]


def test_pm_markets_month_complete_partial_schema_and_resume(fake, tmp_path):
    mk = [pm_market(10, "2025-03-05T12:00:00Z", "2025-01-01T00:00:00Z"), pm_market(11, "2025-03-31T23:00:00Z", "2025-03-01T00:00:00Z"),
          pm_market(12, "2026-10-02T12:00:00Z", "2026-09-01T00:00:00Z")]
    f = fake(markets=mk)
    a = _archive(tmp_path)
    rep = m.fetch_pm_markets(a, first="2025-03-01", last="2025-03-31", **FAST)
    e = a.get("polymarket-closed-markets-2025-03")
    assert e.in_git is False and "complete" in e.tags and rep["polymarket-closed-markets-2025-03"]["rows"] == 2
    rows = list(a.load("polymarket-closed-markets-2025-03"))
    legacy_keys = {"source", "kind", "key", "observed_at", "available_at", "value"}
    assert all(set(r) == legacy_keys and r["source"] == "polymarket" and r["kind"] == "market" for r in rows)
    assert rows[0]["value"] == mk[0]                                            # raw Gamma row, lossless
    assert rows[0]["observed_at"] == "2025-03-05T12:00:00+00:00"                # closedTime normalised to ISO UTC
    assert rows[0]["available_at"] >= "2026-"                                   # fetch time (end-of-life snapshot)
    n0 = f.n("gamma-api.polymarket.com")
    m.fetch_pm_markets(a, first="2025-03-01", last="2025-03-31", **FAST)        # complete month: skipped
    assert f.n("gamma-api.polymarket.com") == n0
    m.fetch_pm_markets(a, first="2026-10-01", last="2026-10-14", **FAST)        # the open month: partial, fetched again next run
    e2 = a.get("polymarket-closed-markets-2026-10")
    assert "partial" in e2.tags and e2.rows == 1
    n1 = f.n("gamma-api.polymarket.com")
    m.fetch_pm_markets(a, first="2026-10-01", last="2026-10-14", **FAST)
    assert f.n("gamma-api.polymarket.com") == n1 + 14


def test_pm_markets_failure_and_max_calls_never_stored(fake, tmp_path):
    fake(markets=[pm_market(1, "2025-03-05T12:00:00Z", "2025-01-01T00:00:00Z")], gamma_fail_day="2025-03-03")
    a = _archive(tmp_path)
    rep = m.fetch_pm_markets(a, first="2025-03-01", last="2025-03-31", backoff=0.0, **FAST)
    assert rep["polymarket-closed-markets-2025-03"]["stored"] is False and rep["polymarket-closed-markets-2025-03"]["_error"]["day"] == "2025-03-03"
    with pytest.raises(KeyError):
        a.get("polymarket-closed-markets-2025-03")
    out = {}
    rep = m.fetch_pm_markets(a, first="2025-02-01", last="2025-02-28", max_calls=3, rows_out=out, **FAST)
    assert rep["polymarket-closed-markets-2025-02"]["stored"] is False and "polymarket-closed-markets-2025-02" in out
    with pytest.raises(KeyError):
        a.get("polymarket-closed-markets-2025-02")


# ============================================================================================ daily prices ==

def test_select_daily_priorities_and_volume_outcome_blind_sample():
    ms = [pm_market(i, "2025-03-10T00:00:00Z", "2025-03-01T00:00:00Z", vol=10_000 + i) for i in range(1, 41)]
    ms.append(pm_market(100, "2025-03-10T00:00:00Z", "2024-10-01T00:00:00Z"))                          # long-lived
    ms.append(pm_market(101, "2025-03-19T18:00:00Z", "2025-03-01T00:00:00Z", q="Fed decision in March?", slug="fed-decision-in-march"))
    ms.append(pm_market(102, "2025-03-12T12:00:00Z", "2025-03-01T00:00:00Z", q="February inflation US - monthly"))
    ms.append({**pm_market(103, "2025-03-10T00:00:00Z", "2025-03-01T00:00:00Z"), "clobTokenIds": json.dumps(["a", "b", "c"])})  # not binary
    sel, st = m.select_daily(ms, per_month=10)
    why = {x["id"]: r for x, r in sel}
    assert why["100"] == "long-lived" and why["101"] == "family:fomc" and why["102"] == "family:cpi" and "103" not in why
    assert sum(1 for r in why.values() if r == "sample") == 10 and st["candidates"] == 40 and st["sample_rate"] == 0.25
    flipped = [{**x, "volumeNum": 1e9 - float(x["volumeNum"]), "outcomePrices": json.dumps(["0", "1"])} for x in ms]
    sel2, _ = m.select_daily(flipped, per_month=10)
    assert [x["id"] for x, _ in sel2] == [x["id"] for x, _ in sel]               # never uses volume, price or outcome


def _stored_month(a, mk, month="2025-03"):
    rows = [m._pm_market_row(x, "2026-10-15T00:00:00+00:00") for x in mk]
    a.store(f"polymarket-closed-markets-{month}", "data", rows, recipe="test", tags=["complete"], in_git=False)


def test_pm_daily_legacy_schema_resume_failures_and_calibration(fake, tmp_path):
    end = ts("2025-03-20T00:00:00Z")
    mk = [pm_market(i, "2025-03-20T00:00:00Z", "2025-01-01T00:00:00Z", outcome="1" if i % 2 else "0") for i in range(1, 6)]
    hist = {f"tok{i}y": [(end - k * DAY, (0.8 if i % 2 else 0.2)) for k in range(30, 0, -1)] for i in range(1, 5)}
    hist["tok5y"] = []                                                          # empty history: logged, never asked again
    f = fake(histories=hist, clob_fail={"tok4y"})
    a = _archive(tmp_path)
    _stored_month(a, mk)
    rep = m.fetch_pm_daily(a, per_month=10, backoff=0.0, **FAST)
    r = rep["polymarket-price-history-daily-2025-03"]
    assert r["n_failed"] == 1 and r["fetched"] == 4 and not r["complete"]
    e = a.get("polymarket-price-history-daily-2025-03")
    assert "partial" in e.tags and e.in_git is False
    rows = list(a.load("polymarket-price-history-daily-2025-03"))
    v = rows[0]
    assert set(v) == {"source", "kind", "key", "observed_at", "available_at", "value"} and set(v["value"]) == {"market_id", "token", "p", "t"}
    assert v["kind"] == "price" and v["observed_at"] == v["available_at"] == datetime.fromtimestamp(v["value"]["t"], UTC).isoformat()
    assert {q["fidelity"] for h, p, q in f.calls if h == "clob.polymarket.com"} == {"1440"}
    f.cfg["clob_fail"] = set()
    n0 = f.n("clob.polymarket.com")
    m.fetch_pm_daily(a, per_month=10, **FAST)                                   # resume: only the failed market is asked again
    assert f.n("clob.polymarket.com") == n0 + 1 and "complete" in a.get("polymarket-price-history-daily-2025-03").tags
    n1 = f.n("clob.polymarket.com")
    m.fetch_pm_daily(a, per_month=10, **FAST)
    assert f.n("clob.polymarket.com") == n1                                     # complete bundle skipped
    log = m._log_load(a, m.PM_LOG)
    assert log["daily:5"]["points"] == 0 and log["daily-sample:2025-03"]["sampled"] == 5
    rep = market_calibration(m.load_pm_daily(a, legacy=False), m.load_pm_markets(a, legacy=False), horizons_days=(1, 7))
    assert rep["n_resolved_markets"] == 5 and rep["horizons"][7]["n"] == 4 and rep["horizons"][1]["n"] == 4


# ============================================================================================ events, hourly ==

def _btc_event(eid, slug, end, strikes=(70000, 72000), start=None):
    ms = [pm_market(f"{eid}{i}", end, start or "2025-03-10T16:00:00Z", q=f"Will the price of Bitcoin be above ${s:,} on March 14?")
          | {"groupItemTitle": f"{s:,}"} for i, s in enumerate(strikes)]
    return {"id": str(eid), "slug": slug, "title": "Bitcoin above ___?", "endDate": end, "startDate": start or "2025-03-10T16:00:00Z",
            "description": "Binance BTC/USDT", "markets": ms}


def test_events_search_paging_filters_and_hourly_et(fake, tmp_path):
    btc = [_btc_event(1, "bitcoin-above-on-march-14", "2025-03-14T16:00:00Z"), _btc_event(2, "bitcoin-above-on-march-14-2025-5pm-et", "2025-03-14T21:00:00Z"),
           _btc_event(5, "bitcoin-above-on-march-14-2025-9pm-et", "2025-03-15T01:00:00Z"),                # hourly-ET, not 17:00: dropped
           {"id": "3", "slug": "will-bitcoin-reach-100k", "endDate": "2025-03-31T00:00:00Z", "markets": []},
           _btc_event(4, "bitcoin-above-on-march-15", "2025-03-15T16:00:00Z")]
    fed = {"id": "9", "slug": "fed-decision-in-march", "endDate": "2025-03-19T18:00:00Z", "markets": []}
    other = {"id": "8", "slug": "october-inflation-china-annual", "endDate": "2026-11-09T00:00:00Z", "markets": []}
    pres = {"id": "7", "slug": "presidential-election-winner-2024", "endDate": "2024-11-05T00:00:00Z", "markets": []}
    f = fake(search={"bitcoin above": btc, "fed decision": [fed, other], "fed interest rates": [], "inflation": [other], "cpi": []},
             events_by_slug=[pres])
    a = _archive(tmp_path)
    rep = m.fetch_pm_events(a, **FAST)
    assert rep["polymarket-events-btc-above"]["events"] == 3 and rep["polymarket-events-btc-above"]["hourly_et"] == 1
    assert {r["value"]["slug"] for r in a.load("polymarket-events-macro")} == {"fed-decision-in-march", "presidential-election-winner-2024"}
    assert [q.get("page") for h, p, q in f.calls if q.get("q") == "bitcoin above"] == ["1", "2", "3"]
    assert m.is_hourly_et("bitcoin-above-on-april-6-2026-9pm-et") and not m.is_hourly_et("bitcoin-above-on-april-8")
    assert m.hourly_et_hour("bitcoin-above-on-april-6-2026-9pm-et") == 21 and m.hourly_et_hour("x-12am-et") == 0
    n0 = len(f.calls)
    m.fetch_pm_events(a, **FAST)
    assert len(f.calls) == n0                                                   # stored: skipped until refresh


def test_pm_hourly_14_day_windows_split_and_resume(fake, tmp_path):
    ev = _btc_event(1, "bitcoin-above-on-march-14", "2025-03-14T16:00:00Z", strikes=(70000,), start="2025-02-01T16:00:00Z")
    tok = json.loads(ev["markets"][0]["clobTokenIds"])[0]
    s = ts("2025-02-01T16:00:00Z")
    hist = {tok: [(s + h * 3600, 0.5) for h in range(0, 41 * 24)]}
    f = fake(histories=hist, clob_max_span=10 * DAY)                            # the fake refuses > 10 days: windows of 14 are split
    a = _archive(tmp_path)
    a.store("polymarket-events-btc-above", "data", [m._event_row(ev, "2026-10-15T00:00:00+00:00")], recipe="t", tags=["complete"], in_git=False)
    rep = m.fetch_pm_hourly(a, sets=("btc_above",), backoff=0.0, **FAST)
    name = "polymarket-price-history-hourly-2025-03"
    assert rep[name]["rows"] == len({t for t, _ in hist[tok] if t <= ts("2025-03-14T16:00:00Z") + 2 * DAY})
    spans = [int(q["endTs"]) - int(q["startTs"]) for h, p, q in f.calls if h == "clob.polymarket.com"]
    assert max(spans) <= 14 * DAY and all(q["fidelity"] == "60" for h, p, q in f.calls if h == "clob.polymarket.com")
    assert any(sp > 10 * DAY for sp in spans) and sum(1 for sp in spans if sp <= 10 * DAY) >= 2   # 400 'too long' -> halves
    rows = list(a.load(name))
    assert rows[0]["available_at"] == rows[0]["observed_at"] and a.get(name).in_git is False
    n0 = len(f.calls)
    m.fetch_pm_hourly(a, sets=("btc_above",), **FAST)
    assert len(f.calls) == n0                                                   # every target stored


# ============================================================================================ trades / volume ==

def _trades(cond, n, t0, step=10, size=2.0):
    return [{"proxyWallet": f"w{i % 3}", "side": "BUY" if i % 3 else "SELL", "asset": "a0" if i % 4 else "a1", "conditionId": cond,
             "size": size, "price": 0.4, "timestamp": t0 + (i // 2) * step, "outcomeIndex": 0 if i % 4 else 1,
             "transactionHash": f"0x{i}", "name": "someone", "pseudonym": "x", "bio": "b"} for i in range(n)]


def test_pm_trades_end_paging_dedup_cap_and_hourly_volume(fake, tmp_path, monkeypatch):
    t0 = ts("2025-03-01T00:00:00Z")
    tr = _trades("0xc1", 25, t0)                                                # pairs of trades share a second: page boundaries split seconds
    fake(trades={"0xc1": tr})
    monkeypatch.setattr(m, "PM_TRADE_PAGE", 4)
    with m._client() as c:
        got, meta = m.pm_trades(c, m.Throttle(0), "0xc1", max_pages=50, page=4)
    assert meta["complete"] and len(got) == 25 and sum(x["size"] for x in got) == 50.0
    assert set(got[0]) == {"ts", "side", "oi", "size", "price"}                 # wallet, name, bio are not kept
    with m._client() as c:
        capped, meta2 = m.pm_trades(c, m.Throttle(0), "0xc1", max_pages=2, page=4)
    assert not meta2["complete"] and meta2["complete_from"] == min(x["ts"] for x in capped) + 1
    rows = m.hourly_volume(got, "1", "0xc1")
    v = rows[0]["value"]
    assert rows[0]["available_at"] == datetime.fromtimestamp(v["t"] + 3600, UTC).isoformat() and rows[0]["observed_at"] == datetime.fromtimestamp(v["t"], UTC).isoformat()
    assert v["n"] == 25 and abs(v["shares"] - 50.0) < 1e-9 and abs(v["usd"] - 20.0) < 1e-9
    assert v["o0"]["n_buy"] + v["o0"]["n_sell"] + v["o1"]["n_buy"] + v["o1"]["n_sell"] == 25
    assert m.hourly_volume(got, "1", "0xc1", from_ts=t0 + 3600) == []


def test_fetch_pm_trades_targets_log_and_resume(fake, tmp_path):
    mk = [pm_market(i, "2025-03-20T00:00:00Z", "2025-03-01T00:00:00Z", vol=50.0) for i in range(1, 4)]
    t0 = ts("2025-03-10T00:00:00Z")
    f = fake(trades={f"0xc{i}": _trades(f"0xc{i}", 25, t0 + i * 7200) for i in range(1, 4)})
    a = _archive(tmp_path)
    _stored_month(a, mk)
    rep = m.fetch_pm_trades(a, n_markets=2, **FAST)
    name = "polymarket-volume-hourly-2025-03"
    assert rep[name]["fetched"] == 2 and a.get(name).in_git is False
    log = m._log_load(a, m.PM_LOG)
    ent = [v for v in log.values() if v.get("product") == "trades"]
    assert len(ent) == 2 and all(v["shares"] == 50.0 and v["shares_over_volumeNum"] == 1.0 and v["complete"] for v in ent)
    n0 = f.n("data-api.polymarket.com")
    m.fetch_pm_trades(a, n_markets=2, **FAST)
    assert f.n("data-api.polymarket.com") == n0


# ================================================================================================== pairs ==

def _fomc_world():
    ev = {"id": "50", "slug": "fed-interest-rates-december-2024", "endDate": "2024-12-18T12:00:00Z", "description": "FOMC statement",
          "markets": [pm_market(500 + i, "2024-12-18T12:00:00Z", "2024-08-06T16:00:00Z") | {"groupItemTitle": g}
                      for i, g in enumerate(["75+ bps decrease", "50 bps decrease", "25 bps decrease", "No Change", "25+ bps increase", "Other"])]}
    ks = [k_market(f"KXFEDDECISION-24DEC-{s}", "KXFEDDECISION-24DEC", "2024-09-01T14:00:00Z", "2024-12-18T18:59:00Z", sub=sub, floor=None, strike_type=None)
          for s, sub in [("H0", "Fed maintains rate"), ("C25", "Cut 25bps"), ("C26", "Cut >25bps"), ("H25", "Hike 25bps"), ("H26", "Hike >25bps")]]
    return ev, ks


def test_fomc_atoms_labels():
    assert m.fomc_atoms("No Change") == {0} and m.fomc_atoms("Hike 0bps") == {0} and m.fomc_atoms("No cut/hike") == {0}
    assert m.fomc_atoms("50+ bps decrease") == m.fomc_atoms("Cut >25bps") == {-50, -75, -100}
    assert m.fomc_atoms("25+ bps increase") == {25, 50, 75, 100} and m.fomc_atoms("Hike >50bps") == {75, 100}
    assert m.fomc_atoms("50 bps decrease") == {-50} and m.fomc_atoms("Other") is None


def test_match_pairs_fomc_components_and_point_in_time():
    ev, ks = _fomc_world()
    rows = m.match_pairs([ev], ks, frozen_at="2026-10-15T00:00:00+00:00")
    got = {tuple(sorted(l["label"] for l in r["value"]["pm"])): tuple(sorted(l["ticker"].split("-")[-1] for l in r["value"]["kalshi"])) for r in rows}
    assert got == {("50 bps decrease", "75+ bps decrease"): ("C26",), ("25 bps decrease",): ("C25",), ("No Change",): ("H0",),
                   ("25+ bps increase",): ("H25", "H26")}
    r = rows[0]
    assert r["available_at"] == "2024-09-01T14:00:00+00:00"                     # the later listing (Kalshi open_time) of the legs
    assert r["observed_at"] == "2026-10-15T00:00:00+00:00" and r["value"]["audited"] is False and r["value"]["family"] == "fomc"
    # listing fields only: outcomes, prices and volumes do not change the table
    ev2 = {**ev, "markets": [x | {"outcomePrices": json.dumps(["0.3", "0.7"]), "volumeNum": 1.0} for x in ev["markets"]]}
    ks2 = [x | {"result": "no", "volume_fp": "1.00", "last_price_dollars": "0.99"} for x in ks]
    strip = lambda rs: [(x["value"]["pair_id"], [l["market_id"] for l in x["value"]["pm"]], [l["ticker"] for l in x["value"]["kalshi"]]) for x in rs]
    assert strip(m.match_pairs([ev2], ks2, frozen_at="2026-10-15T00:00:00+00:00")) == strip(rows)


def test_match_pairs_cpi_bucket_algebra_btc_and_election():
    ev = {"id": "60", "slug": "february-inflation-us-monthly", "endDate": "2025-03-12T12:30:00Z", "description": "Bureau of Labor Statistics CPI",
          "markets": [pm_market(600 + i, "2025-03-12T12:30:00Z", "2025-02-20T00:00:00Z") | {"groupItemTitle": g}
                      for i, g in enumerate(["≤0.1%", "0.2%", "0.3%", "≥0.5%", "2.0-2.4%"])]}
    ks = [k_market(f"KXCPI-25FEB-T{x}", "KXCPI-25FEB", "2025-02-21T00:00:00Z", "2025-03-12T12:25:00Z", floor=x) for x in (0.0, 0.1, 0.2, 0.4)]
    china = {**ev, "id": "61", "slug": "february-inflation-china-annual"}
    no_bls = {**ev, "id": "62", "slug": "march-inflation-us-monthly", "description": "some index"}
    btc = {"id": "70", "slug": "bitcoin-above-on-march-14-2025-5pm-et", "endDate": "2025-03-14T21:00:00Z", "description": "Binance",
           "markets": [pm_market(700, "2025-03-14T21:00:00Z", "2025-03-13T21:00:00Z") | {"groupItemTitle": "84,000"},
                       pm_market(701, "2025-03-14T21:00:00Z", "2025-03-13T21:00:00Z") | {"groupItemTitle": "85,000"}]}
    kb = [k_market("KXBTCD-25MAR1417-T83999.99", "KXBTCD-25MAR1417", "2025-03-07T21:00:00Z", "2025-03-14T21:00:00Z", floor=83999.99)]
    pres = {"id": "80", "slug": "presidential-election-winner-2024", "endDate": "2024-11-05T00:00:00Z",
            "markets": [pm_market(800, "2024-11-05T00:00:00Z", "2024-01-04T00:00:00Z") | {"groupItemTitle": "Donald Trump"},
                        pm_market(801, "2024-11-05T00:00:00Z", "2024-01-04T00:00:00Z") | {"groupItemTitle": "Joe Biden"}]}
    kp = [k_market("PRES-2024-DJT", "PRES-2024", "2024-10-04T00:00:00Z", "2025-01-20T00:00:00Z", sub="Donald Trump", strike_type=None)]
    rows = m.match_pairs([ev, china, no_bls, pres], ks + kb + kp, btc_events=[btc], frozen_at="2026-10-15T00:00:00+00:00")
    cpi = {r["value"]["pm"][0]["label"]: r["value"] for r in rows if r["value"]["family"] == "cpi_mom"}
    assert set(cpi) == {"≤0.1%", "0.2%", "≥0.5%"}                               # 0.3% needs K(above 0.3): absent, no pair
    assert cpi["≤0.1%"]["const"] == 1.0 and [(l["ticker"], l["sign"]) for l in cpi["≤0.1%"]["kalshi"]] == [("KXCPI-25FEB-T0.1", -1)]
    assert [(l["ticker"], l["sign"]) for l in cpi["0.2%"]["kalshi"]] == [("KXCPI-25FEB-T0.1", 1), ("KXCPI-25FEB-T0.2", -1)]
    assert [(l["ticker"], l["sign"]) for l in cpi["≥0.5%"]["kalshi"]] == [("KXCPI-25FEB-T0.4", 1)] and cpi["≥0.5%"]["key"] == "2025-02"
    b = [r["value"] for r in rows if r["value"]["family"] == "btc"]
    assert len(b) == 1 and b[0]["pm"][0]["label"] == "84,000" and b[0]["kalshi"][0]["ticker"] == "KXBTCD-25MAR1417-T83999.99"
    assert "BRTI" in b[0]["basis_note"] and b[0]["timing_gap_hours"] == 0.0
    el = [r for r in rows if r["value"]["family"] == "election"]
    assert len(el) == 1 and el[0]["value"]["kalshi"][0]["ticker"] == "PRES-2024-DJT" and el[0]["available_at"] == "2024-10-04T00:00:00+00:00"


def test_cpi_bucket_and_ref_month():
    assert m.cpi_bucket("≤0.1%") == ("le", 0.1) and m.cpi_bucket("<2.5%") == ("le", 2.4) and m.cpi_bucket("0.3%") == ("eq", 0.3)
    assert m.cpi_bucket("≥0.8%") == ("ge", 0.8) and m.cpi_bucket("0.5%+") == ("ge", 0.5) and m.cpi_bucket("2.0-2.4%") is None
    assert m._pm_ref_month("december-inflation-us-monthly", "2026-01-13T13:30:00Z", "december") == (2025, 12)
    assert m._pm_ref_month("core-cpi-mom-july-2026-20260705181328287", "2026-08-12T12:30:00Z", "july") == (2026, 7)


def test_build_pairs_waits_for_listings_then_freezes(fake, tmp_path):
    a = _archive(tmp_path)
    ev, ks = _fomc_world()
    a.store("polymarket-events-macro", "data", [m._event_row(ev, "2026-10-15T00:00:00+00:00")], recipe="t", tags=["complete"], in_git=False)
    rep = m.build_pairs(a)
    assert rep[m.PAIRS]["waiting"] and "kalshi-settled-markets-KXFEDDECISION" in rep[m.PAIRS]["waiting"]
    for s in m.PAIR_KALSHI:
        rows = [m._k_market_row(x, "2026-10-15T00:00:00+00:00") for x in ks] if s == "KXFEDDECISION" else []
        a.store(f"kalshi-settled-markets-{s}", "data", rows, recipe="t", tags=["complete"], in_git=False)
    rep = m.build_pairs(a)
    assert rep[m.PAIRS]["pairs"] == 4 and a.get(m.PAIRS).in_git is False
    assert m.build_pairs(a)[m.PAIRS]["skipped"].startswith("stored (frozen)")
    t = m.hourly_targets(a, sets=("pairs",))
    assert {x["market_id"] for x in t["2024-12"].values()} == {"500", "501", "502", "503", "504"}


# ================================================================================================== Kalshi ==

def test_kalshi_markets_hist_live_dedup_btc_events_and_retry_after(fake, tmp_path):
    hist = [k_market("KXCPI-25JAN-T0.2", "KXCPI-25JAN", "2025-01-01T00:00:00Z", "2025-02-12T13:25:00Z"),
            k_market("CPI-21JUN-T0.6", "CPI-21JUN", "2021-06-30T00:00:00Z", "2021-07-12T23:00:00Z") | {"_series": "KXCPI"},
            k_market("KXCPI-26JUL-T0.1", "KXCPI-26JUL", "2026-06-16T00:00:00Z", "2026-08-12T12:25:00Z"),
            k_market("KXBTCD-25MAR1417-T83999.99", "KXBTCD-25MAR1417", "2025-03-07T21:00:00Z", "2025-03-14T21:00:00Z"),
            k_market("KXBTCD-25MAR1417-T90999.99", "KXBTCD-25MAR1417", "2025-03-07T21:00:00Z", "2025-03-14T21:00:00Z", vol="0.00")]
    live = [k_market("KXCPI-26JUL-T0.1", "KXCPI-26JUL", "2026-06-16T00:00:00Z", "2026-08-12T12:25:00Z", vol="9.00"),
            k_market("KXCPI-26SEP-T0.9", "KXCPI-26SEP", "2026-09-17T00:00:00Z", "2026-10-14T12:29:00Z")]
    f = fake(k_hist=hist, k_live=live, k_429=1)
    a = _archive(tmp_path)
    rep = m.fetch_kalshi_markets(a, series=("KXCPI",), crypto={"KXBTCD": 17}, crypto_first="2025-03-14", last="2025-03-15", **FAST)
    assert 3.0 in f.sleeps                                                      # 429 Retry-After honoured
    rows = list(a.load("kalshi-settled-markets-KXCPI"))
    assert sorted(r["key"] for r in rows) == ["CPI-21JUN-T0.6", "KXCPI-25JAN-T0.2", "KXCPI-26JUL-T0.1", "KXCPI-26SEP-T0.9"]
    assert next(r for r in rows if r["key"] == "KXCPI-26JUL-T0.1")["value"]["volume_fp"] == "9.00"        # live row wins
    assert rows[0]["kind"] == "market" and rows[0]["observed_at"].endswith("+00:00")
    btc = list(a.load("kalshi-settled-markets-KXBTCD-2025-03"))
    assert [r["key"] for r in btc] == ["KXBTCD-25MAR1417-T83999.99"]                                   # untraded strikes dropped
    assert {q.get("event_ticker") for h, p, q in f.calls if "event_ticker" in q} == {"KXBTCD-25MAR1417", "KXBTCD-25MAR1517"}
    assert a.get("kalshi-settled-markets-KXCPI").in_git is False
    assert m.kxbtcd_event("2025-03-14", 17) == "KXBTCD-25MAR1417"


def test_kalshi_candles_routes_fallback_chunking_and_resume(fake, tmp_path):
    early = k_market("KXFED-25JAN-T4.25", "KXFED-25JAN", "2024-01-01T00:00:00Z", "2025-01-29T19:00:00Z")      # 394 days: 2 hourly windows
    late = k_market("KXFED-26SEP-T3.50", "KXFED-26SEP", "2026-08-01T00:00:00Z", "2026-09-16T18:00:00Z")
    empty_hist = k_market("KXFED-25MAR-T4.00", "KXFED-25MAR", "2025-02-01T00:00:00Z", "2025-03-19T18:00:00Z")
    def cs(a, b, step):
        return [{"end_period_ts": t, "yes_bid": {"close": "0.40"}, "yes_ask": {"close": "0.45"}} for t in range(a, b, step)]
    f = fake(k_candles={("hist", early["ticker"]): cs(ts("2024-01-01T01:00:00Z"), ts("2025-01-29T19:00:00Z"), 7 * 3600),
                        ("live", late["ticker"]): cs(ts("2026-08-01T01:00:00Z"), ts("2026-09-16T18:00:00Z"), 5 * 3600),
                        ("live", empty_hist["ticker"]): cs(ts("2025-02-01T01:00:00Z"), ts("2025-02-03T00:00:00Z"), 3600)})
    a = _archive(tmp_path)
    a.store("kalshi-settled-markets-KXFED", "data", [m._k_market_row(x, "2026-10-15T00:00:00+00:00") for x in (early, late, empty_hist)],
            recipe="t", tags=["complete"], in_git=False)
    rep = m.fetch_kalshi_candles(a, period=60, **FAST)
    name = "kalshi-candles-hourly-KXFED"
    assert rep[name]["fetched"] == 3 and "complete" in a.get(name).tags
    paths = [(p, q) for h, p, q in f.calls if p.endswith("/candlesticks")]
    assert all((int(q["end_ts"]) - int(q["start_ts"])) / 3600 <= m.CANDLES_PER_CALL for p, q in paths)
    assert sum(1 for p, q in paths if early["ticker"] in p) == 2 and all("/historical/" in p for p, q in paths if early["ticker"] in p)
    assert all("/series/KXFED/markets/" in p for p, q in paths if late["ticker"] in p)
    assert [("/historical/" in p) for p, q in paths if empty_hist["ticker"] in p] == [True, False]       # empty historical -> live route
    rows = list(a.load(name))
    r = rows[0]
    assert set(r["value"]) == {"ticker", "period", "candle"} and r["observed_at"] == r["available_at"]
    assert r["available_at"] == datetime.fromtimestamp(r["value"]["candle"]["end_period_ts"], UTC).isoformat()
    n0 = len(f.calls)
    rep2 = m.fetch_kalshi_candles(a, period=60, **FAST)
    assert rep2[name]["skipped"] and len(f.calls) == n0 + 1                     # only the cutoff call
    m.fetch_kalshi_candles(a, period=1440, **FAST)
    assert a.get("kalshi-candles-daily-KXFED").rows > 0


def test_candle_fields_reads_both_route_conventions():
    hist = {"end_period_ts": 1, "price": {"close": "0.25", "mean": "0.27"}, "volume": "1331.00", "open_interest": "1893.00",
            "yes_ask": {"close": "0.29", "open": "0.31"}, "yes_bid": {"close": "0.23"}}
    live = {"end_period_ts": 2, "price": {"close_dollars": "0.82", "mean_dollars": "0.85"}, "volume_fp": "4.09", "open_interest_fp": "4.09",
            "yes_ask": {"close_dollars": "0.83"}, "yes_bid": {"close_dollars": "0.80"}}
    a, b = m.candle_fields(hist), m.candle_fields(live)
    assert (a["price_close"], a["yes_ask_close"], a["yes_bid_close"], a["volume"], a["open_interest"]) == (0.25, 0.29, 0.23, 1331.0, 1893.0)
    assert (b["price_close"], b["yes_ask_close"], b["yes_bid_close"], b["volume"], b["price_mean"]) == (0.82, 0.83, 0.80, 4.09, 0.85)
    assert a["yes_bid_open"] is None


def test_kalshi_trades_routes_cap_and_complete_from(fake, tmp_path, monkeypatch):
    span = k_market("KXCPI-26JUL-T0.1", "KXCPI-26JUL", "2026-06-16T00:00:00Z", "2026-08-20T12:25:00Z", vol="5000.00")   # spans the cutoff
    old = k_market("KXCPI-25JAN-T0.2", "KXCPI-25JAN", "2025-01-01T00:00:00Z", "2025-02-12T13:25:00Z", vol="5000.00")
    def trs(tk, n, t0, pre="L"):
        return [{"trade_id": f"{tk}-{pre}{i}", "ticker": tk, "created_time": z(t0 - i * 60), "count_fp": "1.00", "yes_price_dollars": "0.40",
                 "taker_side": "yes", "taker_outcome_side": "yes"} for i in range(n)]
    f = fake(k_trades={("live", span["ticker"]): trs(span["ticker"], 3, ts("2026-08-18T00:00:00Z")),
                       ("hist", span["ticker"]): trs(span["ticker"], 2, ts("2026-08-10T00:00:00Z"), "H") + trs(span["ticker"], 1, ts("2026-08-18T00:00:00Z")),
                       ("hist", old["ticker"]): trs(old["ticker"], 9, ts("2025-02-12T00:00:00Z"))})
    a = _archive(tmp_path)
    a.store("kalshi-settled-markets-KXCPI", "data", [m._k_market_row(x, "2026-10-15T00:00:00+00:00") for x in (span, old)], recipe="t",
            tags=["complete"], in_git=False)
    rep = m.fetch_kalshi_trades(a, max_pages=3, **FAST)
    rows = list(a.load("kalshi-trades-KXCPI"))
    by = {}
    for r in rows:
        by.setdefault(r["value"]["ticker"], []).append(r)
    assert len(by[span["ticker"]]) == 5                                         # both stores, de-duplicated by trade_id
    assert len(by[old["ticker"]]) == 6                                          # 3 pages of 2: capped
    log = m._log_load(a, m.K_LOG)
    assert log[f"trades:{old['ticker']}"]["complete"] is False and log[f"trades:{old['ticker']}"]["complete_from"]
    assert log[f"trades:{span['ticker']}"]["complete"] is True and set(log[f"trades:{span['ticker']}"]["routes"]) == {"/markets/trades", "/historical/trades"}
    assert all(r["observed_at"] == r["available_at"] for r in rows) and a.get("kalshi-trades-KXCPI").in_git is False
    assert rep["kalshi-trades-KXCPI"]["fetched"] == 2


# ============================================================================================ plans, licences ==

def test_dry_run_makes_no_request_and_plans_every_source(fake, tmp_path):
    fake(forbid=True)
    a = _archive(tmp_path)
    rep = m.fetch_all_pm(a, dry_run=True)
    assert set(rep) >= set(m.SOURCES) | {"_total", "_gitignore"}
    for n in m.SOURCES:
        p = rep[n]["_plan"]
        assert {"calls", "rows", "gz_mb", "minutes", "per_bundle"} <= set(p)
    assert rep["_total"]["calls"] > 10_000 and rep["_total"]["minutes_by_host_group"]["kalshi"] > 0
    fam = m.family_table(rep)
    assert all(x["in_git"] is False and x["gitignore_line"].startswith("mandel/archive/data/") for x in fam)


def test_gitignore_lines_cover_every_bundle_name_and_spare_legacy():
    names = ["polymarket-closed-markets-2025-03", "polymarket-price-history-daily-2025-03", "polymarket-price-history-hourly-2025-03",
             "polymarket-volume-hourly-2025-03", "polymarket-events-btc-above", "polymarket-events-macro", "polymarket-fetch-log",
             "pm-kalshi-pairs", "kalshi-settled-markets-KXCPI", "kalshi-settled-markets-KXBTCD-2025-03", "kalshi-candles-daily-KXCPI",
             "kalshi-candles-hourly-KXBTCD-2025-03", "kalshi-trades-KXCPI", "kalshi-fetch-log"]
    for n in names:
        line = m.gitignore_line(n)
        assert line and fnmatch(f"mandel/archive/data/{n}.jsonl.gz", line), n
    for legacy in ("polymarket-closed-markets", "polymarket-price-history-daily", "kalshi-settled-markets", "kalshi-candles", "polymarket-books-snapshot"):
        assert not any(fnmatch(f"mandel/archive/data/{legacy}.jsonl.gz", g) for g in m.GITIGNORE_LINES), legacy


def test_fetch_all_rejects_unknown_sources_and_orders_dependencies():
    with pytest.raises(ValueError):
        m.fetch_all_pm(None, sources=["nope"])
    order = list(m.SOURCES)
    assert order.index("kalshi_markets") < order.index("pairs") < order.index("pm_hourly") < order.index("pm_trades")
    assert order.index("pm_markets") < order.index("pm_daily")


def test_fetch_all_pm_chain_then_rerun_is_cheap_and_every_bundle_local_only(fake, tmp_path):
    ev, ks = _fomc_world()
    mk = [x for x in ev["markets"]]
    hist = {json.loads(x["clobTokenIds"])[0]: [(ts("2024-12-01T00:00:00Z") + h * 3600, 0.3) for h in range(24 * 17)] for x in mk}
    trades = {x["conditionId"]: _trades(x["conditionId"], 6, ts("2024-12-10T00:00:00Z")) for x in mk}
    kc = {("hist", k["ticker"]): [{"end_period_ts": ts("2024-12-01T00:00:00Z") + h * 3600, "yes_bid": {"close": "0.1"}, "yes_ask": {"close": "0.2"}}
                                  for h in range(10)] for k in ks}
    kt = {("hist", k["ticker"]): [{"trade_id": f"{k['ticker']}-{i}", "ticker": k["ticker"], "created_time": z(ts("2024-12-10T00:00:00Z") - i * 60),
                                   "count_fp": "1.00"} for i in range(3)] for k in ks}
    f = fake(markets=mk, histories=hist, trades=trades, k_hist=ks, k_candles=kc, k_trades=kt,
             search={"fed decision": [ev], "fed interest rates": [], "inflation": [], "cpi": [], "bitcoin above": []}, events_by_slug=[])
    a = _archive(tmp_path)
    opts = {"pm_markets": {"first": "2024-12-18", "last": "2024-12-18"}, "kalshi_markets": {"series": m.PAIR_KALSHI, "crypto": {}},
            "pm_hourly": {"sets": ("pairs",)}, "pm_trades": {"n_markets": 2}}
    rep = m.fetch_all_pm(a, options=opts, min_interval=0.0)
    assert rep["pairs"][m.PAIRS]["pairs"] == 4
    assert a.get("polymarket-price-history-daily-2024-12").rows == 6 * 24 * 17                 # all six markets (long-lived: priority)
    assert a.get("polymarket-price-history-hourly-2024-12").rows == 5 * 24 * 17                # five pair legs, windows de-duplicated
    assert a.get("polymarket-volume-hourly-2024-12").rows > 0 and a.get("kalshi-candles-hourly-KXFEDDECISION").rows == 50
    assert a.get("kalshi-candles-daily-KXFEDDECISION").rows == 50 and a.get("kalshi-trades-KXFEDDECISION").rows == 15
    n0 = len(f.calls)
    m.fetch_all_pm(a, options=opts, min_interval=0.0)
    again = f.calls[n0:]
    assert not [c for c in again if c[0] in ("clob.polymarket.com", "data-api.polymarket.com")]
    assert all(p == "/trade-api/v2/historical/cutoff" for h, p, q in again if h == "api.elections.kalshi.com")
    g = [(p, q) for h, p, q in again if h == "gamma-api.polymarket.com"]
    assert g and all(p == "/markets/keyset" and q["end_date_min"].startswith("2024-12-18") for p, q in g)   # the open (partial) month only
    for e in a.entries():
        assert e.in_git is False and m.gitignore_line(e.name), e.name
