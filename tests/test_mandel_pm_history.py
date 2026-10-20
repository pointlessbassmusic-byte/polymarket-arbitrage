"""mandel.data.pm_history on mocked HTTP only (httpx.MockTransport; no network): Gamma keyset day windows (lifetime filter,
inclusive end bound, month complete / partial, resume, failures never stored), the volume- and outcome-blind daily
selection (sampled only once a month is complete), legacy row schemas (market_calibration runs on them), CLOB hourly
windows (14 days, split on 'interval is too long'), data-api end-paging (inclusive boundary de-duplicated, page cap,
complete_from, short histories), hourly taker volume, event listing by keyset windows (BTC tag exclusions, 5 pm ET
windows, macro tags, search page cap, closed filter, resume), the templated FOMC / CPI / BTC / election pair matcher
(listing fields only, point in time, day-suffixed Kalshi events, CPI singles by release date), Kalshi listings
(historical + live, KXBTCD daily events), Retry-After, candle and trade routing around the historical cutoff (capped live
route), pair legs in the hourly candles, candle chunking, the open long-lived markets (T-32), the phased two-thread run
(one consistent INDEX), dry runs that make no request, licences (in_git False) and .gitignore lines."""

import json
from collections import defaultdict
from datetime import datetime, timezone
from fnmatch import fnmatch
from urllib.parse import parse_qs, parse_qsl, urlparse

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
        qm = parse_qs(urlparse(str(req.url)).query)
        host, path = req.url.host, req.url.path
        self.calls.append((host, path, q))
        if host == "gamma-api.polymarket.com":
            return self.gamma(path, q, qm)
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
    def gamma(self, path, q, qm):
        if path == "/markets/keyset" and q.get("closed") == "false":
            rows = [x for x in self.cfg.get("open_markets", []) if float(x["volumeNum"]) >= float(q["volume_num_min"])
                    and ts(x["startDate"]) <= ts(q["start_date_max"])]
            i = int(q.get("after_cursor") or 0)
            return httpx.Response(200, json={"markets": rows[i:i + 2], "next_cursor": str(i + 2) if i + 2 < len(rows) else None})
        if path == "/events/keyset":
            lo, hi = ts(q["end_date_min"]), ts(q["end_date_max"])
            if hi <= lo:
                return httpx.Response(422, json={"error": "invalid time range"})
            if q["end_date_min"] in self.cfg.get("events_fail", ()):
                return httpx.Response(500, json={"error": "boom"})
            excl = set(qm.get("exclude_tag_id", []))
            rows = [e for e in self.cfg.get("events", []) if lo <= ts(e["endDate"]) <= hi and q["tag_slug"] in [t["slug"] for t in e.get("tags", [])]
                    and not excl & {t["id"] for t in e.get("tags", [])}]        # closed=true is not trusted: the module filters
            rows.sort(key=lambda e: int(e["id"]))
            i = int(q.get("after_cursor") or 0)
            return httpx.Response(200, json={"events": rows[i:i + 2], **({"next_cursor": str(i + 2)} if i + 2 < len(rows) else {})})
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
            if p > 100:
                return httpx.Response(422, json={"error": 'query argument "page": must be less than or equal to 100'})
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
            fails = self.cfg.setdefault("k_fail_series", {})
            if fails.get(q.get("series_ticker"), 0) > 0:
                fails[q["series_ticker"]] -= 1
                return httpx.Response(500, json={"error": "boom"})
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

BTC_TAGS = [{"id": "235", "slug": "bitcoin"}, {"id": "1312", "slug": "crypto-prices"}]
H1 = {"id": "102175", "slug": "1h"}
UPDOWN = {"id": "102127", "slug": "up-or-down"}


def _btc_event(eid, slug, end, strikes=(70000, 72000), start=None, tags=None, closed=True):
    ms = [pm_market(f"{eid}{i}", end, start or "2025-03-10T16:00:00Z", q=f"Will the price of Bitcoin be above ${s:,} on March 14?")
          | {"groupItemTitle": f"{s:,}"} for i, s in enumerate(strikes)]
    return {"id": str(eid), "slug": slug, "title": "Bitcoin above ___?", "endDate": end, "startDate": start or "2025-03-10T16:00:00Z",
            "description": "Binance BTC/USDT", "markets": ms, "closed": closed, "tags": tags if tags is not None else BTC_TAGS}


def _btc_world():
    return [_btc_event(1, "bitcoin-above-70000-on-friday", "2024-03-22T07:00:00Z", strikes=(70000,), start="2024-03-17T21:14:27Z"),
            _btc_event(2, "btc-above-70000-next-friday", "2024-03-15T00:00:00Z", strikes=(70000,), start="2024-03-08T22:24:56Z"),
            _btc_event(3, "bitcoin-above-on-september-2-2026", "2026-09-02T16:00:00Z", start="2026-08-26T16:00:00Z"),
            _btc_event(4, "bitcoin-above-on-september-2-2026-5pm-et", "2026-09-02T21:00:00Z", tags=BTC_TAGS + [H1], start="2026-09-01T21:00:00Z"),
            _btc_event(5, "bitcoin-above-on-september-2-2026-9pm-et", "2026-09-03T01:00:00Z", tags=BTC_TAGS + [H1]),   # not 17:00 ET
            _btc_event(6, "bitcoin-up-or-down-on-september-2-2026", "2026-09-02T16:00:00Z", tags=BTC_TAGS + [UPDOWN]),
            _btc_event(7, "bitcoin-above-on-october-14-2026", "2026-10-14T16:00:00Z", closed=False),                     # still open
            {**_btc_event(8, "will-bitcoin-reach-100k", "2026-09-30T00:00:00Z"), "markets": []}]


def test_events_btc_keyset_windows_exclusions_5pm_and_closed_filter(fake, tmp_path):
    """Regression (blocking): public-search refuses page > 100, so 'bitcoin above' could never be stored; the BTC set is
    now listed by keyset windows (tag bitcoin minus 1H / up-or-down per month, plus a 2-second window at 17:00 ET a day)."""
    f = fake(events=_btc_world())
    a = _archive(tmp_path)
    rep = m.fetch_pm_events(a, sets=["btc_above"], btc_first_month="2024-03", hourly_first_day="2026-08-30", **FAST)
    r = rep["polymarket-events-btc-above"]
    kept = {x["value"]["slug"] for x in a.load("polymarket-events-btc-above")}
    assert kept == {"bitcoin-above-70000-on-friday", "btc-above-70000-next-friday", "bitcoin-above-on-september-2-2026",
                    "bitcoin-above-on-september-2-2026-5pm-et"}
    assert r["hourly_et"] == 1 and r["open_dropped"] >= 1 and "complete" in a.get("polymarket-events-btc-above").tags
    g = [q for h, p, q in f.calls if p == "/events/keyset"]
    assert not [1 for h, p, q in f.calls if p == "/public-search"]
    months = [q for q in g if q["end_date_min"].endswith("-01T00:00:00Z") and q["end_date_max"].endswith("-01T00:00:00Z")]
    assert months[0]["end_date_min"] == "2024-03-01T00:00:00Z" and months[0]["end_date_max"] == "2024-04-01T00:00:00Z"
    assert {months[-1]["end_date_min"][:7]} == {"2026-10"} and len(months) == 32
    sep2 = [q for q in g if q["end_date_min"].startswith("2026-09-02T20")]
    assert sep2 and sep2[0]["end_date_min"] == "2026-09-02T20:59:59Z" and sep2[0]["end_date_max"] == "2026-09-02T21:00:01Z"
    assert m.et_hour_ts("2025-12-15", 17) == ts("2025-12-15T22:00:00Z") and m.et_hour_ts("2026-09-02", 17) == ts("2026-09-02T21:00:00Z")
    win = m.event_windows("btc_above", "2026-09-02", hourly_first_day="2026-09-02")
    assert win[0]["params"]["exclude_tag_id"] == ["102175", "102127"]
    log = m._log_load(a, m.PM_LOG)
    assert log["events:btc_above:month:2024-03"]["final"] is True and log["events:btc_above:month:2026-10"]["final"] is False
    n0 = len(f.calls)
    m.fetch_pm_events(a, sets=["btc_above"], btc_first_month="2024-03", hourly_first_day="2026-08-30", **FAST)
    assert len(f.calls) == n0                                                   # complete: skipped until refresh
    t = m.hourly_targets(a, sets=("btc_above",))
    assert {x["market_id"] for M in t for x in t[M].values()} == {"10", "20", "30", "31"}         # 5 pm variant: a pair leg, not here


def test_events_resume_after_failed_window(fake, tmp_path):
    f = fake(events=_btc_world(), events_fail={"2024-06-01T00:00:00Z"})
    a = _archive(tmp_path)
    rep = m.fetch_pm_events(a, sets=["btc_above"], btc_first_month="2024-03", hourly_first_day="2026-10-14", backoff=0.0, **FAST)
    r = rep["polymarket-events-btc-above"]
    assert r["_error"]["window"] == "month:2024-06" and r["stored"] == "partial"
    e = a.get("polymarket-events-btc-above")
    assert "partial" in e.tags and {x["value"]["slug"] for x in a.load("polymarket-events-btc-above")} == {
        "bitcoin-above-70000-on-friday", "btc-above-70000-next-friday"}
    assert m.build_pairs(a)[m.PAIRS]["waiting"]                                 # a partial event set never feeds the frozen table
    f.cfg["events_fail"] = set()
    n0 = len(f.calls)
    m.fetch_pm_events(a, sets=["btc_above"], btc_first_month="2024-03", hourly_first_day="2026-10-14", **FAST)
    again = [q["end_date_min"][:7] for h, p, q in f.calls[n0:] if p == "/events/keyset"]
    assert "2024-03" not in again and "2024-05" not in again and again[0] == "2024-06"        # resumes at the failed window
    assert "complete" in a.get("polymarket-events-btc-above").tags and a.get("polymarket-events-btc-above").rows == 3     # no 5 pm windows asked


def test_events_macro_keyset_union_search_cap_and_closed_filter(fake, tmp_path):
    """Regression (minor): public-search missed january-inflation-us-monthly / february-inflation-us-annual; the macro set
    is the union of keyset tag-months and the searches. A search hitting the 100-page cap is incomplete, not a failure."""
    infl = [{"id": str(60 + i), "slug": s, "endDate": end, "closed": True, "tags": [{"id": "702", "slug": "inflation"}], "markets": []}
            for i, (s, end) in enumerate([("january-inflation-us-monthly", "2026-02-11T12:30:00Z"),
                                          ("february-inflation-us-annual", "2026-03-11T12:30:00Z"),
                                          ("february-inflation-us-monthly-231", "2026-03-11T12:30:00Z"),
                                          ("october-inflation-china-annual", "2026-03-11T12:30:00Z")])]
    fed = {"id": "9", "slug": "fed-decision-in-march", "endDate": "2025-03-19T18:00:00Z", "closed": True, "markets": [],
           "tags": [{"id": "100196", "slug": "fed-rates"}]}
    open_fed = {**fed, "id": "10", "slug": "fed-decision-in-december", "endDate": "2026-12-09T19:00:00Z", "closed": False}
    pres = {"id": "7", "slug": "presidential-election-winner-2024", "endDate": "2024-11-05T00:00:00Z", "closed": True, "markets": []}
    junk = [{"id": str(1000 + i), "slug": f"inflation-junk-{i}", "endDate": "2025-01-01T00:00:00Z", "closed": True, "markets": []} for i in range(205)]
    f = fake(events=infl + [fed], search={"fed decision": [fed, open_fed], "fed interest rates": [], "inflation": junk, "cpi": []},
             events_by_slug=[pres])
    a = _archive(tmp_path)
    rep = m.fetch_pm_events(a, sets=["macro"], macro_first_month="2025-01", **FAST)
    r = rep["polymarket-events-macro"]
    assert {x["value"]["slug"] for x in a.load("polymarket-events-macro")} == {
        "january-inflation-us-monthly", "february-inflation-us-annual", "february-inflation-us-monthly-231", "fed-decision-in-march",
        "presidential-election-winner-2024"}                                  # open and non-US events dropped
    assert r["incomplete"][0]["window"] == "search:inflation" and "page cap 100" in r["incomplete"][0]["note"]
    assert max(int(q["page"]) for h, p, q in f.calls if p == "/public-search") == 100      # page 101 is never asked
    assert "complete" in a.get("polymarket-events-macro").tags
    with m._client() as c:
        got, k, info = m.pm_search(c, m.Throttle(0), "inflation")
    assert got is not None and len(got) == 200 and k == 100 and info["incomplete"]


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
    rep = m.fetch_pm_trades(a, n_markets=68, **FAST)                          # 68 over the 34 months 2024-01..2026-10: 2 a month
    name = "polymarket-volume-hourly-2025-03"
    assert rep[name]["fetched"] == 2 and a.get(name).in_git is False
    log = m._log_load(a, m.PM_LOG)
    ent = [v for v in log.values() if v.get("product") == "trades"]
    assert len(ent) == 2 and all(v["shares"] == 50.0 and v["shares_over_volumeNum"] == 1.0 and v["complete"] for v in ent)
    assert log["trades-sample:2025-03"]["quota"] == 2 and log["trades-sample:2025-03"]["candidates"] == 3
    n0 = f.n("data-api.polymarket.com")
    m.fetch_pm_trades(a, n_markets=68, **FAST)
    assert f.n("data-api.polymarket.com") == n0


def test_pm_trades_short_history_is_not_complete(fake, tmp_path):
    """Regression (minor): a market whose data-api history is partial (taker shares 0.047 x volumeNum, 2023-era) was logged
    complete after one short page; complete now needs |shares / volumeNum - 1| <= 1%."""
    mk = [pm_market(1, "2025-03-20T00:00:00Z", "2025-03-01T00:00:00Z", vol=50.0), pm_market(2, "2025-03-20T00:00:00Z", "2025-03-01T00:00:00Z", vol=1000.0)]
    t0 = ts("2025-03-10T00:00:00Z")
    fake(trades={"0xc1": _trades("0xc1", 25, t0), "0xc2": _trades("0xc2", 25, t0)})              # both sum to 50 shares
    a = _archive(tmp_path)
    _stored_month(a, mk)
    rep = m.fetch_pm_trades(a, n_markets=68, **FAST)
    log = m._log_load(a, m.PM_LOG)
    assert log["trades:1"]["complete"] is True and "history_short" not in log["trades:1"]
    assert log["trades:2"]["complete"] is False and log["trades:2"]["complete_from"] is None and log["trades:2"]["history_short"]
    assert log["trades:2"]["shares_over_volumeNum"] == 0.05 and rep["polymarket-volume-hourly-2025-03"]["history_short"] == 1
    e = a.get("polymarket-volume-hourly-2025-03")
    assert "partial" in e.tags and "history-short" in e.tags


def test_daily_sample_waits_for_a_complete_month(fake, tmp_path):
    """Regression (minor): a partial month was sampled from the markets known so far, and a later run with more markets
    picked a new top set while the earlier picks stayed (6 'sample' markets against a logged rate of 3 / 20)."""
    end = ts("2026-10-03T00:00:00Z")
    mk = [pm_market(i, "2026-10-03T00:00:00Z", "2026-09-20T00:00:00Z") for i in range(1, 21)]
    f = fake(histories={f"tok{i}y": [(end - k * DAY, 0.5) for k in range(5, 0, -1)] for i in range(1, 21)})
    a = _archive(tmp_path)
    rows = [m._pm_market_row(x, "2026-10-15T00:00:00+00:00") for x in mk[:6]]
    a.store("polymarket-closed-markets-2026-10", "data", rows, recipe="t", tags=["partial"], in_git=False)
    m.fetch_pm_daily(a, per_month=3, **FAST)
    log = m._log_load(a, m.PM_LOG)
    assert log["daily-sample:2026-10"]["sampled"] == 0 and log["daily-sample:2026-10"]["sample_deferred"]
    assert not f.n("clob.polymarket.com")                                       # no priority market among the six, no sample yet
    assert m.trade_targets(a, n_markets=68) == {}                              # nor trade targets from a partial month
    a.store("polymarket-closed-markets-2026-10", "data", [m._pm_market_row(x, "2026-10-15T00:00:00+00:00") for x in mk], recipe="t",
            tags=["complete"], in_git=False)
    m.fetch_pm_daily(a, per_month=3, **FAST)
    log = m._log_load(a, m.PM_LOG)
    st = log["daily-sample:2026-10"]
    picked = {v["id"] for v in log.values() if v.get("product") == "daily" and v.get("month") == "2026-10" and v.get("reason") == "sample"}
    assert st["candidates"] == 20 and st["sampled"] == 3 and st["sample_rate"] == 0.15 and len(picked) == 3
    assert {str(r["value"]["market_id"]) for r in a.load("polymarket-price-history-daily-2026-10")} == picked
    want = [x["id"] for x, _ in m.select_daily(mk, per_month=3)[0]]
    assert sorted(picked) == sorted(want)                                       # the prefix of the whole month's hash order
    samples = {}
    t = m.trade_targets(a, n_markets=68, per_month=3, samples_out=samples)
    assert len(t["2026-10"]) == 2 and samples["2026-10"]["quota"] == 2 and samples["2026-10"]["candidates"] == 3
    assert set(t["2026-10"]) <= picked                                          # trade markets are a prefix of the daily sample
    t2 = m.trade_targets(a, n_markets=10, per_month=3, plog={"trades-sample:2026-10": {"quota": 2}})
    assert len(t2["2026-10"]) == 2                                              # a logged quota is kept when n_markets / months shift


def test_open_long_lived_markets_snapshot_and_daily(fake, tmp_path):
    """T-32 (missing coverage): markets still open and alive >= 100 days, one per event, with their daily history."""
    om_ = [pm_market(100 + i, "2027-06-30T00:00:00Z", "2026-03-01T00:00:00Z", ev=f"E{i // 2}") | {"closed": False} for i in range(6)]
    om_.append(pm_market(200, "2027-06-30T00:00:00Z", "2026-09-01T00:00:00Z") | {"closed": False})                 # 44 days: too young
    hist = {f"tok{100 + i}y": [(ts("2026-03-02T00:00:00Z") + k * DAY, 0.5) for k in range(200)] for i in range(6)}
    f = fake(open_markets=om_, histories=hist)
    a = _archive(tmp_path)
    rep = m.fetch_pm_open(a, **FAST)
    assert rep[m.PM_OPEN]["markets"] == 6 and rep[m.PM_OPEN]["events"] == 3
    q = [q for h, p, q in f.calls if p == "/markets/keyset"][0]
    assert q["closed"] == "false" and q["start_date_max"] == "2026-07-07T00:00:00Z" and q["volume_num_min"] == "10000"
    rows = list(a.load(m.PM_OPEN_DAILY))
    assert len({r["value"]["market_id"] for r in rows}) == 3 and a.get(m.PM_OPEN_DAILY).in_git is False   # one per event
    assert "complete" in a.get(m.PM_OPEN_DAILY).tags and rows[0]["available_at"] == rows[0]["observed_at"]
    assert len(m.load_pm_daily(a, legacy=False, include_open=True)) == len(rows) and m.load_pm_daily(a, legacy=False) == []
    n0 = len(f.calls)
    assert m.fetch_pm_open(a, **FAST)[m.PM_OPEN]["skipped"] and len(f.calls) == n0
    assert m.gitignore_line(m.PM_OPEN) and m.gitignore_line(m.PM_OPEN_DAILY) and m._family(m.PM_OPEN_DAILY)[3] == ["T-32"]


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


def _store_events(a, name, evs, complete=True):
    a.store(name, "data", [m._event_row(e, "2026-10-15T00:00:00+00:00") for e in evs], recipe="t", tags=["complete" if complete else "partial"],
            in_git=False)


def test_build_pairs_waits_for_listings_then_freezes(fake, tmp_path):
    a = _archive(tmp_path)
    ev, ks = _fomc_world()
    _store_events(a, "polymarket-events-macro", [ev])
    rep = m.build_pairs(a)
    assert rep[m.PAIRS]["waiting"] and "kalshi-settled-markets-KXFEDDECISION" in rep[m.PAIRS]["waiting"]
    for s in m.PAIR_KALSHI:
        rows = [m._k_market_row(x, "2026-10-15T00:00:00+00:00") for x in ks] if s == "KXFEDDECISION" else []
        a.store(f"kalshi-settled-markets-{s}", "data", rows, recipe="t", tags=["complete"], in_git=False)
    assert m.build_pairs(a)[m.PAIRS]["waiting"] == ["polymarket-events-btc-above"]
    _store_events(a, "polymarket-events-btc-above", [])
    rep = m.build_pairs(a)
    assert rep[m.PAIRS]["pairs"] == 4 and a.get(m.PAIRS).in_git is False and rep[m.PAIRS]["price_bundles_at_freeze"] == 0
    assert "before any price bundle of this module was stored" in a.get(m.PAIRS).recipe
    assert m.build_pairs(a)[m.PAIRS]["skipped"].startswith("stored (frozen)")
    t = m.hourly_targets(a, sets=("pairs",))
    assert {x["market_id"] for x in t["2024-12"].values()} == {"500", "501", "502", "503", "504"}


def test_build_pairs_waits_for_btc_events_and_kxbtcd_months(tmp_path):
    """Regression (blocking): pairs no longer freezes without the BTC family: it waits for a complete
    polymarket-events-btc-above and for the KXBTCD months of its latest 5 pm ET events."""
    a = _archive(tmp_path)
    ev, ks = _fomc_world()
    _store_events(a, "polymarket-events-macro", [ev])
    for s in m.PAIR_KALSHI:
        rows = [m._k_market_row(x, "2026-10-15T00:00:00+00:00") for x in ks] if s == "KXFEDDECISION" else []
        a.store(f"kalshi-settled-markets-{s}", "data", rows, recipe="t", tags=["complete"], in_git=False)
    btc = _btc_event(4, "bitcoin-above-on-september-2-2026-5pm-et", "2026-09-02T21:00:00Z", strikes=(84000, 85000), start="2026-09-01T21:00:00Z")
    _store_events(a, "polymarket-events-btc-above", [btc], complete=False)              # partial: still being listed
    assert m.build_pairs(a)[m.PAIRS]["waiting"] == ["polymarket-events-btc-above"]
    _store_events(a, "polymarket-events-btc-above", [btc])
    assert m.build_pairs(a)[m.PAIRS]["waiting"] == ["kalshi-settled-markets-KXBTCD-2026-09"]
    kb = [k_market("KXBTCD-26SEP0217-T83999.99", "KXBTCD-26SEP0217", "2026-08-26T21:00:00Z", "2026-09-02T21:00:00Z", floor=83999.99)]
    a.store("kalshi-settled-markets-KXBTCD-2026-09", "data", [m._k_market_row(x, "2026-10-15T00:00:00+00:00") for x in kb], recipe="t",
            tags=["complete"], in_git=False)
    rep = m.build_pairs(a)
    assert rep[m.PAIRS]["by_family"] == {"fomc": 4, "btc": 1}
    assert "kalshi-settled-markets-KXBTCD-<2026-09>" in a.get(m.PAIRS).recipe
    assert m.pair_kalshi_tickers(a) >= {"KXBTCD-26SEP0217-T83999.99"}
    b = Archive(root=tmp_path / "other", ledger=Ledger(tmp_path / "l2.jsonl"))       # btc=False: the BTC family is not awaited
    _store_events(b, "polymarket-events-macro", [ev])
    for s in m.PAIR_KALSHI:
        b.store(f"kalshi-settled-markets-{s}", "data", [m._k_market_row(x, "2026-10-15T00:00:00+00:00") for x in ks] if s == "KXFEDDECISION" else [],
                recipe="t", tags=["complete"], in_git=False)
    assert m.build_pairs(b, btc=False)[m.PAIRS]["by_family"] == {"fomc": 4}


def test_event_month_day_suffix_and_nearest_kalshi_event():
    """Regression (data-wrong): FEDDECISION-24JAN31 / -24MAR20 were not parsed, so 2024-03 had no pair and 2024-01 paired
    with the untraded legacy FEDDECISION-24JAN (closed 2024-01-26)."""
    assert m._event_month("FEDDECISION-24JAN31") == (2024, 1) and m._event_month("FEDDECISION-24MAR20") == (2024, 3)
    assert m._event_month("KXCPI-25FEB") == (2025, 2) and m._event_month("KXBTCD-25MAR1417") is None
    def kev(ev, open_t, close_t, vol):
        return [k_market(f"{ev}-{s}", ev, open_t, close_t, vol=vol, sub=sub, strike_type=None)
                for s, sub in [("H0", "Hike 0bps"), ("C25", "Cut 25bps"), ("H25", "Hike 25bps"), ("C26", "Cut >25bps")]]
    ks = (kev("FEDDECISION-24JAN", "2023-12-13T18:00:00Z", "2024-01-26T18:55:00Z", "0.00")
          + kev("FEDDECISION-24JAN31", "2023-12-13T19:05:00Z", "2024-01-31T18:55:00Z", "102686.00")
          + kev("FEDDECISION-24MAR20", "2024-01-31T19:05:00Z", "2024-03-20T17:55:00Z", "133511.00"))
    jan = {"id": "1", "slug": "fed-interest-rates-january-2024", "endDate": "2024-01-31T00:00:00Z", "description": "FOMC",
           "markets": [pm_market(10 + i, "2024-01-31T00:00:00Z", "2023-12-14T00:00:00Z") | {"groupItemTitle": g}
                       for i, g in enumerate(["0 bps increase?", "25 bps decrease?", "25 bps increase?"])]}
    mar = {"id": "2", "slug": "fed-interest-rates-march-2024", "endDate": "2024-03-20T00:00:00Z", "description": "FOMC",
           "markets": [pm_market(20 + i, "2024-03-18T00:00:00Z", "2024-02-01T00:00:00Z") | {"groupItemTitle": g}
                       for i, g in enumerate(["50+ bps decrease", "25 bps decrease", "No change", "25+ bps increase"])]}
    rows = m.match_pairs([jan, mar], ks, frozen_at="2026-10-15T00:00:00+00:00")
    by = defaultdict(set)
    for r in rows:
        by[r["value"]["key"]] |= {l["event_ticker"] for l in r["value"]["kalshi"]}
    assert by == {"2024-01": {"FEDDECISION-24JAN31"}, "2024-03": {"FEDDECISION-24MAR20"}}
    assert all(abs(r["value"]["timing_gap_hours"]) < 24 and not r["value"]["timing_suspect"] for r in rows)
    # listing fields only: zeroing every volume does not change the choice (close_time decides)
    zero = [x | {"volume_fp": "0.00"} for x in ks]
    assert [r["value"]["pair_id"] for r in m.match_pairs([jan, mar], zero, frozen_at="2026-10-15T00:00:00+00:00")] == [r["value"]["pair_id"] for r in rows]


def test_cpi_single_reference_month_from_release_date_and_timing_flag():
    """Regression (minor): 'US inflation >0.1% from Jan to Feb 2024?' resolved on the January print (endDate 2024-02-13);
    it was paired by its text with CPI-24FEB (gap -684 h)."""
    def single(eid, q, end):
        return {"id": eid, "slug": f"us-inflation-{eid}", "endDate": end, "description": "Bureau of Labor Statistics CPI",
                "markets": [pm_market(int(eid), end, "2024-01-20T00:00:00Z", q=q)]}
    evs = [single("31", "US inflation >0.1% from Jan to Feb 2024?", "2024-02-13T00:00:00Z"),
           single("32", "US inflation >0.2% from Nov to Dec 2023?", "2024-01-11T00:00:00Z")]
    ks = [k_market(f"CPI-{e}-T{x}", f"CPI-{e}", "2023-12-01T00:00:00Z", c, floor=x) for e, c in
          [("23DEC", "2024-01-11T13:25:00Z"), ("24JAN", "2024-02-13T13:25:00Z"), ("24FEB", "2024-03-12T12:25:00Z")] for x in (0.1, 0.2)]
    rows = {r["value"]["pm"][0]["market_id"]: r["value"] for r in m.match_pairs(evs, ks, frozen_at="2026-10-15T00:00:00+00:00")}
    assert rows["31"]["kalshi"][0]["ticker"] == "CPI-24JAN-T0.1" and rows["31"]["key"] == "2024-01"
    assert "text names 2024-02" in rows["31"]["basis_note"] and abs(rows["31"]["timing_gap_hours"]) < 24
    assert rows["32"]["kalshi"][0]["ticker"] == "CPI-23DEC-T0.2" and "text names" not in rows["32"]["basis_note"]
    far = m._pair("cpi_mom", "2024-02", "t", [m._pm_leg(evs[0]["markets"][0], 1, "x", evs[0])],
                  [m._k_leg(ks[-1], 1)], 0.0, "", "", "", "2026-10-15T00:00:00+00:00", 1)
    assert far["value"]["timing_suspect"] is True and far["value"]["timing_gap_hours"] < -168


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


def _trs(tk, n, t0, pre="L"):
    return [{"trade_id": f"{tk}-{pre}{i}", "ticker": tk, "created_time": z(t0 - i * 60), "count_fp": "1.00", "yes_price_dollars": "0.40",
             "taker_side": "yes", "taker_outcome_side": "yes"} for i in range(n)]


def test_kalshi_trades_capped_live_route_never_reads_the_older_route(fake, tmp_path):
    """Regression (data-wrong): a market spanning the trades cutoff whose live route hit max_pages also read the historical
    route, and complete_from came from the oldest historical print, hiding the gap between the cutoff and the oldest live
    print fetched."""
    span = k_market("KXFEDDECISION-26SEP-H0", "KXFEDDECISION-26SEP", "2026-07-30T18:00:00Z", "2026-09-16T17:59:00Z", vol="48300000.00")
    live = _trs(span["ticker"], 7, ts("2026-09-16T17:58:59Z"))
    f = fake(k_trades={("live", span["ticker"]): live, ("hist", span["ticker"]): _trs(span["ticker"], 4, ts("2026-08-15T23:54:13Z"), "H")})
    with m._client() as c:
        got, meta = m.kalshi_trades(c, m.Throttle(0), span, ts("2026-08-16T00:00:00Z"), max_pages=3)
    assert not [1 for h, p, q in f.calls if p.endswith("/historical/trades")]
    oldest_live = min(ts(t["created_time"]) for t in live[:6])
    assert meta["complete"] is False and meta["complete_from"] == datetime.fromtimestamp(oldest_live + 1, UTC).isoformat()
    assert meta["routes"] == ["/markets/trades"] and meta["routes_skipped"] == ["/historical/trades"] and len(got) == 6
    assert meta["coverage"][0]["complete"] is False and meta["coverage"][0]["n"] == 6
    with m._client() as c:                                                      # live complete -> historical read; capped there
        got2, meta2 = m.kalshi_trades(c, m.Throttle(0), span, ts("2026-08-16T00:00:00Z"), max_pages=4)
    assert meta2["routes"] == ["/markets/trades", "/historical/trades"] and meta2["complete"] is True and len(got2) == 11
    f.cfg["k_trades"][("hist", span["ticker"])] = _trs(span["ticker"], 9, ts("2026-08-15T23:54:13Z"), "H")
    with m._client() as c:
        got4, meta4 = m.kalshi_trades(c, m.Throttle(0), span, ts("2026-08-16T00:00:00Z"), max_pages=4)
    oldest_hist = min(ts(t["created_time"]) for t in f.cfg["k_trades"][("hist", span["ticker"])][:8])
    assert meta4["complete"] is False and meta4["complete_from"] == datetime.fromtimestamp(oldest_hist + 1, UTC).isoformat()


def test_hourly_candles_add_every_kalshi_pair_leg(fake, tmp_path):
    """Regression (data-wrong): kalshi_select keeps the 4 most traded strikes of a KXBTCD event; the BTC pair legs (on
    Polymarket's grid) got no hourly candles. Pair legs are now added, also by a pass after the table exists."""
    ev = "KXBTCD-26SEP0217"
    ks = [k_market(f"{ev}-T{x - 0.01:.2f}", ev, "2026-08-26T21:00:00Z", "2026-09-02T21:00:00Z", vol=f"{v}.00", floor=x - 0.01)
          for x, v in [(84000, 9000), (84250, 8000), (84500, 7000), (84750, 6000), (85000, 50), (86000, 10)]]
    cs = {("live", k["ticker"]): [{"end_period_ts": ts("2026-09-02T00:00:00Z") + h * 3600, "yes_bid": {"close_dollars": "0.4"}} for h in range(3)]
          for k in ks}
    f = fake(k_candles=cs)
    a = _archive(tmp_path)
    a.store("kalshi-settled-markets-KXBTCD-2026-09", "data", [m._k_market_row(x, "2026-10-15T00:00:00+00:00") for x in ks], recipe="t",
            tags=["complete"], in_git=False)
    m.fetch_kalshi_candles(a, period=60, **FAST)
    name = "kalshi-candles-hourly-KXBTCD-2026-09"
    assert {r["value"]["ticker"] for r in a.load(name)} == {k["ticker"] for k in ks[:4]}
    pairs = [m._pair("btc", "2026-09-02T17ET", "t", [{"market_id": "1", "start": "2026-08-26T21:00:00Z", "end_date": "2026-09-02T21:00:00Z"}],
                     [m._k_leg(ks[i], 1)], 0.0, "", "", "", "2026-10-15T00:00:00+00:00", i) for i in (0, 4, 5)]
    a.store(m.PAIRS, "data", pairs, recipe="t", tags=["complete"], in_git=False)
    n0 = len(f.calls)
    rep = m.fetch_kalshi_candles(a, period=60, **FAST)
    asked = {p.split("/")[-2] for h, p, q in f.calls[n0:] if p.endswith("/candlesticks")}
    assert asked == {ks[4]["ticker"], ks[5]["ticker"]} and rep[name]["pair_legs_added"] == 2
    assert {r["value"]["ticker"] for r in a.load(name)} == {k["ticker"] for k in ks}
    log = m._log_load(a, m.K_LOG)
    assert log[f"candles-60:{ks[5]['ticker']}"]["reason"] == "pair" and log[f"candles-60:{ks[0]['ticker']}"]["reason"] == "select"


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
             "kalshi-candles-hourly-KXBTCD-2025-03", "kalshi-trades-KXCPI", "kalshi-fetch-log", "polymarket-open-markets",
             "polymarket-open-price-history-daily"]
    assert len(m.GITIGNORE_LINES) == 15
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
    phases = [set(n for ns in g.values() for n in ns) for _, g in m.PHASES]
    assert phases[0] == {"pm_markets", "pm_events", "kalshi_markets"} and phases[1] == {"pairs"}
    assert set(m.SOURCES) == set().union(*phases)
    assert m.PM_SOURCES.index("pairs") < m.PM_SOURCES.index("pm_daily")         # listings, then pairs, then prices


def test_stop_event_stops_workers_at_their_next_request():
    th = m._Pace(0.0)
    th.wait()
    m._STOP.set()
    try:
        with pytest.raises(KeyboardInterrupt):
            th.wait()
    finally:
        m._STOP.clear()


def test_dry_run_on_a_partly_filled_archive_plans_unstored_months(fake, tmp_path):
    """Regression (minor): with one closed-markets month stored, the pm_daily plan covered that month only."""
    fake(forbid=True)
    a = _archive(tmp_path)
    _stored_month(a, [pm_market(i, "2025-03-20T00:00:00Z", "2025-01-01T00:00:00Z") for i in range(1, 6)])
    a.store("kalshi-settled-markets-KXCPI", "data", [m._k_market_row(k_market("KXCPI-25JAN-T0.2", "KXCPI-25JAN", "2025-01-01T00:00:00Z",
                                                                             "2025-02-12T13:25:00Z"), "2026-10-15T00:00:00+00:00")],
            recipe="t", tags=["complete"], in_git=False)
    rep = m.fetch_all_pm(a, dry_run=True)
    daily = {i["bundle"]: i for i in rep["pm_daily"]["_plan"]["per_bundle"]}
    assert len(daily) == len(m._months(m.PM_FIRST_DAY, "2026-10-14")) and daily["polymarket-price-history-daily-2025-03"]["calls"] == 5
    assert daily["polymarket-price-history-daily-2026-09"].get("estimate") and daily["polymarket-price-history-daily-2026-09"]["calls"] > 1000
    cand = {i["bundle"] for i in rep["kalshi_candles_hourly"]["_plan"]["per_bundle"]}
    assert "kalshi-candles-hourly-KXCPI" in cand and "kalshi-candles-hourly-KXFEDDECISION" in cand and "kalshi-candles-hourly-<pair legs>" in cand
    assert {i["bundle"] for i in rep["kalshi_trades"]["_plan"]["per_bundle"]} >= {"kalshi-trades-KXCPI", "kalshi-trades-KXFED"}
    t = rep["_total"]
    assert t["wall_minutes_parallel"] < t["minutes"] and set(t["wall_minutes_by_phase"]) == {"listings", "pairs", "prices"}
    assert m.LATENCY["kalshi"] >= 1.34 and m.KALSHI_EST_OTHER >= 9500 and m.pm_month_estimate("2026-09") >= 15000


def _chain_world():
    ev, ks = _fomc_world()
    ev = {**ev, "closed": True, "tags": [{"id": "100196", "slug": "fed-rates"}]}
    mk = [x for x in ev["markets"]]
    hist = {json.loads(x["clobTokenIds"])[0]: [(ts("2024-12-01T00:00:00Z") + h * 3600, 0.3) for h in range(24 * 17)] for x in mk}
    trades = {x["conditionId"]: _trades(x["conditionId"], 6, ts("2024-12-10T00:00:00Z")) for x in mk}
    kc = {("hist", k["ticker"]): [{"end_period_ts": ts("2024-12-01T00:00:00Z") + h * 3600, "yes_bid": {"close": "0.1"}, "yes_ask": {"close": "0.2"}}
                                  for h in range(10)] for k in ks}
    kt = {("hist", k["ticker"]): [{"trade_id": f"{k['ticker']}-{i}", "ticker": k["ticker"], "created_time": z(ts("2024-12-10T00:00:00Z") - i * 60),
                                   "count_fp": "1.00"} for i in range(3)] for k in ks}
    cfg = dict(markets=mk, histories=hist, trades=trades, k_hist=ks, k_candles=kc, k_trades=kt, events=[ev],
               search={"fed decision": [ev], "fed interest rates": [], "inflation": [], "cpi": []}, events_by_slug=[])
    opts = {"pm_markets": {"first": "2024-12-18", "last": "2024-12-18"}, "kalshi_markets": {"series": m.PAIR_KALSHI, "crypto": {}},
            "pm_events": {"btc_first_month": "2026-10", "hourly_first_day": "2026-10-14", "macro_first_month": "2024-12"},
            "pm_hourly": {"sets": ("pairs",)}, "pm_trades": {"n_markets": 2}}
    return cfg, opts


def test_fetch_all_pm_chain_then_rerun_is_cheap_and_every_bundle_local_only(fake, tmp_path):
    cfg, opts = _chain_world()
    f = fake(**cfg)
    a = _archive(tmp_path)
    rep = m.fetch_all_pm(a, options=opts, min_interval=0.0)
    assert rep["pairs"][m.PAIRS]["pairs"] == 4 and rep["pairs"][m.PAIRS]["price_bundles_at_freeze"] == 0
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


def test_parallel_run_one_process_consistent_index_and_phase_order(fake, tmp_path):
    """Regression (minor, problems 9-10): the two-process plan left a stale fetch-log INDEX entry (verify False) and fetched
    pair-leg prices before the pairs table was frozen. One process, two threads, one Archive; listings -> pairs -> prices."""
    cfg, opts = _chain_world()
    fake(**cfg)
    a = _archive(tmp_path)
    m.fetch_all_pm(a, options=opts, min_interval=0.0, parallel=True)
    fresh = Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))
    for e in fresh.entries():
        assert fresh.verify(e.name), e.name
        assert e.rows == sum(1 for _ in fresh.load(e.name)), e.name
    assert {"polymarket-fetch-log", "kalshi-fetch-log"} <= {e.name for e in fresh.entries()}
    frozen = fresh.get(m.PAIRS).created_at
    priced = [e for e in fresh.entries() if any(fnmatch(e.name, p) for p in m.PRICE_BUNDLE_PATTERNS)]
    assert priced and all(e.created_at > frozen for e in priced)
    listings = [e for e in fresh.entries() if e.name.startswith(("polymarket-closed-markets-", "polymarket-events-", "kalshi-settled-markets-"))]
    assert all(e.created_at < frozen for e in listings)




def test_fetch_all_lists_again_before_freezing_when_a_listing_failed(fake, tmp_path):
    """A Kalshi listing that failed past every retry (429 burst, seen live 2026-10-15) is listed again before the pairs
    phase, so the table is not left waiting while the prices run."""
    cfg, opts = _chain_world()
    f = fake(**cfg, k_fail_series={"KXCPI": m.KALSHI_RETRIES})
    a = _archive(tmp_path)
    rep = m.fetch_all_pm(a, options=opts, min_interval=0.0)
    assert rep["_listing_retries"][0]["waiting"] == ["kalshi-settled-markets-KXCPI"]
    assert rep["_listing_retries"][0]["kalshi_markets"]["kalshi-settled-markets-KXCPI"]["stored"] is False
    assert rep["pairs"][m.PAIRS]["pairs"] == 4 and rep["pairs"][m.PAIRS]["price_bundles_at_freeze"] == 0
    assert m.LISTING_RETRY_PAUSE in f.sleeps and a.get("kalshi-candles-hourly-KXFEDDECISION").rows == 50


def test_trade_targets_take_every_closed_btc_above_market(tmp_path):
    """T-337's liquidity rule needs hourly taker volume for the 'Bitcoin above' markets the harness trades, so trade_targets
    adds every closed non-hourly-ET two-token market of polymarket-events-btc-above (reason btc-above) after the pair legs and
    the hash sample, which keep their reasons and accounting; hourly-ET events, future ends and token-less markets are not taken."""
    a = _archive(tmp_path)
    fetched = "2026-10-15T00:00:00+00:00"
    world = [e for e in _btc_world() if e["slug"] != "bitcoin-up-or-down-on-september-2-2026"]   # the fetch drops up-or-down
    world[3]["markets"][0]["clobTokenIds"] = json.dumps(["onlyone"])            # hourly-ET anyway: excluded by the slug
    world[2]["markets"][1]["clobTokenIds"] = json.dumps(["onlyone"])            # one token: no hourly CLOB series to trade
    world[5]["endDate"] = "2099-01-01T00:00:00Z"                                # the open event: its end is still ahead
    for x in world[5]["markets"]:
        x["endDate"] = "2099-01-01T00:00:00Z"
    a.store("polymarket-events-btc-above", "data", [m._event_row(e, fetched) for e in world], recipe="t", tags=["complete"], in_git=False)
    pair_leg = {"market_id": "11", "condition_id": "0xpair", "end": "2024-03-22T07:00:00Z", "start": "2024-03-17T21:14:27Z", "volumeNum": 5.0}
    a.store(m.PAIRS, "data", [m._row("polymarket", "pair", "p1", "2024-03-22T07:00:00Z", fetched, {"pm": [pair_leg]})], recipe="t", in_git=False)
    t = m.trade_targets(a, n_markets=68)
    assert t["2024-03"]["11"]["reason"] == "pair"                               # the pair leg keeps its reason (event 1's market 10 is btc-above)
    assert t["2024-03"]["10"] == {"market_id": "10", "condition_id": "0xc10", "volumeNum": 50000.0, "reason": "btc-above"}
    assert t["2024-03"]["20"]["reason"] == "btc-above"
    assert set(t["2026-09"]) == {"30"}                                          # event 3's second market has one token; events 4-5 hourly-ET
    assert "2099-01" not in t and "2026-10" not in t                            # event 7 ends after yesterday (open), event 8 has no markets
