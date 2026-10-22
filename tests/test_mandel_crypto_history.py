"""mandel.data.crypto_history on mocked HTTP only (httpx.MockTransport; no network): Coinbase candle windows and the
daily-history row convention, open bars never stored, month chunks and resume, failures never stored, the point-in-time
hourly candidate ranking, Kraken since-paging with rate-error retries and 1-minute signed-volume bars, stablecoin episode
windows, CMC snapshot merging and resume, CoinMetrics paging and the 403 fallback, blockchain.info, DefiLlama, the iShares
page parser and merge, Retry-After, dry runs that make no request, licences (in_git False) and .gitignore lines."""

import html
import json
from datetime import date, datetime, timedelta, timezone
from fnmatch import fnmatch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from mandel.archive import Archive
from mandel.data import crypto_history as m
from mandel.data import options_misc as om
from mandel.ledger import Ledger

UTC = timezone.utc
NOW = m._ts("2026-10-15") + 12 * 3600          # 2026-10-15 12:00 UTC


def _iso(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


# ------------------------------------------------------------------------------------------------ fake venue --

class Fake:
    """One handler for every host the module calls. ``calls`` logs (host, path, params)."""

    def __init__(self, **cfg):
        self.cfg = cfg
        self.calls = []
        self.kraken_errors = list(cfg.get("kraken_errors", []))
        self.cb_429 = cfg.get("cb_429", 0)

    def handler(self, req: httpx.Request) -> httpx.Response:
        if self.cfg.get("forbid"):
            raise AssertionError(f"unexpected request {req.url}")
        q = {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}
        host, path = req.url.host, req.url.path
        self.calls.append((host, path, q))
        if host == "api.exchange.coinbase.com":
            return self.coinbase(path, q)
        if host == "api.kraken.com":
            return self.kraken(path, q)
        if host == "api.coinmarketcap.com":
            return self.cmc(path, q)
        if host == "community-api.coinmetrics.io":
            return self.coinmetrics(q)
        if host == "api.blockchain.info":
            return httpx.Response(200, json={"status": "ok", "unit": "Hash Rate TH/s", "values": [
                {"x": m._ts("2009-01-03") + i * 86400, "y": float(i) * 1.5} for i in range(10)]})
        if host == "yields.llama.fi":
            return self.llama(path)
        if host == "www.ishares.com":
            return httpx.Response(200, text=self.cfg.get("ishares_page", ""), headers={"content-type": "text/html"})
        return httpx.Response(404, json={"message": "NotFound"})

    # -- Coinbase
    def coinbase(self, path, q):
        if self.cb_429:
            self.cb_429 -= 1
            return httpx.Response(429, headers={"Retry-After": "7"}, json={"message": "slow down"})
        if path == "/products":
            return httpx.Response(200, json=self.cfg.get("products", []))
        parts = path.strip("/").split("/")
        pid = parts[1]
        if parts[-1] == "trades":
            return self.cb_trades(q)
        if pid in self.cfg.get("cb_missing", ()):
            return httpx.Response(404, json={"message": "NotFound"})
        if pid in self.cfg.get("cb_broken", ()):
            return httpx.Response(500, json={"message": "boom"})
        g = int(q["granularity"])
        s, e = _iso(q["start"]), _iso(q["end"])
        n = (e - s) // g + 1
        if n > 300 or s % g or e % g:
            return httpx.Response(400, json={"message": "granularity too small for the requested time range"})
        lo, hi = self.cfg.get("listed", {}).get(pid, (0, 10**11))
        bars = []
        for t in range(s, e + 1, g):
            if lo <= t <= hi and (t // g) % 13 != 5:               # every 13th bucket has no trade
                p = 100.0 + (t // g) % 50 + self.cfg.get("level", {}).get(pid, 0.0)
                bars.append([t, p - 1, p + 1, p - 0.5, p + 0.5, self.cfg.get("vol", {}).get(pid, 10.0)])
        return httpx.Response(200, json=list(reversed(bars)))

    def cb_trades(self, q):
        n, t0 = self.cfg["cb_trades_n"], self.cfg["cb_trades_t0"]
        top = int(q["after"]) - 1 if "after" in q else n
        ids = range(min(top, n), max(0, min(top, n) - int(q["limit"])), -1)
        return httpx.Response(200, json=[{"trade_id": i, "side": "buy" if i % 2 == 0 else "sell", "size": "0.1",
                                          "price": str(100 + i % 7),
                                          "time": datetime.fromtimestamp(t0 + i * 0.5, UTC).isoformat().replace("+00:00", "Z")} for i in ids])

    # -- Kraken
    def kraken(self, path, q):
        if self.kraken_errors:
            return httpx.Response(200, json={"error": [self.kraken_errors.pop(0)], "result": {}})
        pair = q["pair"]
        if pair in self.cfg.get("kraken_bad_pairs", ()):
            return httpx.Response(200, json={"error": ["EQuery:Unknown asset pair"], "result": {}})
        t0, dt, n = self.cfg["kraken_t0"], self.cfg["kraken_dt"], self.cfg["kraken_n"]
        since = int(q["since"])
        cap = self.cfg.get("kraken_page", 100)
        out = []
        i = max(0, (since - t0 * 10**9) // int(dt * 10**9) - 1)
        while i < n and len(out) < cap:
            ts = t0 + i * dt
            if int(round(ts * 1e9)) > since:
                out.append([f"{100 + i % 11:.5f}", f"{0.01 * (1 + i % 3):.8f}", ts, "b" if i % 3 else "s", "m" if i % 5 == 0 else "l", "", 1000 + i])
            i += 1
        last = int(round(out[-1][2] * 1e9)) if out else since
        return httpx.Response(200, json={"error": [], "result": {"X" + pair: out, "last": str(last)}})

    # -- CoinMarketCap
    def cmc(self, path, q):
        if self.cfg.get("cmc_down"):
            return httpx.Response(200, json={"status": {"error_code": "500", "error_message": "down"}, "data": None})
        if path.endswith("/listings/historical"):
            day, lim = q["date"], int(q["limit"])
            coins = []
            hot = self.cfg.get("cmc_hot", {})                              # {rank: volume24h}: high-volume small caps
            untagged = day < self.cfg.get("cmc_untagged_before", "")       # early snapshots carry no tags
            for i in range(1, min(lim, self.cfg.get("cmc_n", 8)) + 1):
                coins.append({"id": i, "name": f"Coin{i}", "symbol": f"C{i}", "slug": f"coin{i}", "cmcRank": i,
                              "circulatingSupply": 1000.0 * i, "totalSupply": 2000.0 * i, "maxSupply": None,
                              "lastUpdated": f"{day}T00:00:00.000Z", "dateAdded": "2013-04-28T00:00:00.000Z",
                              "tags": None if untagged else (["stablecoin", "usd-stablecoin", "mineable"] if i == 2 else ["mineable", "pow"]),
                              "platform": {"name": "Ethereum", "symbol": "ETH"} if i == 3 else None,
                              "quotes": [{"name": "2781", "price": 1.5 * i, "volume24h": hot.get(i, 1000.0 / i), "marketCap": 1e6 / i,
                                          "percentChange24h": 0.1, "percentChange7d": -0.2}]})
            return httpx.Response(200, json={"status": {"error_code": "0", "error_message": "SUCCESS"}, "data": coins})
        cid, s, e = int(q["id"]), int(q["timeStart"]), int(q["timeEnd"])
        days = [d for d in range(s // 86400, e // 86400 + 1) if d * 86400 >= self.cfg.get("cmc_coin_first", 0)][-400:]
        quotes = [{"timeOpen": datetime.fromtimestamp(d * 86400, UTC).isoformat().replace("+00:00", ".000Z"),
                   "quote": {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0, "marketCap": 5.0}} for d in days]
        return httpx.Response(200, json={"status": {"error_code": "0"}, "data": {"id": cid, "name": "Bitcoin", "symbol": "BTC", "quotes": quotes}})

    # -- CoinMetrics
    def coinmetrics(self, q):
        metrics = q["metrics"].split(",")
        if "SOPR" in metrics:
            return httpx.Response(403, json={"error": {"type": "forbidden", "message": "not available"}})
        assert q.get("paging_from") == "start" and q.get("frequency") == "1d"
        start = m._ts(q["start_time"])
        n_days = self.cfg.get("cm_days", 25)
        k = int(q.get("next_page_token", 0))
        rows = []
        for d in range(k, min(k + 10, n_days)):
            row = {"asset": q["assets"], "time": datetime.fromtimestamp(start + d * 86400, UTC).strftime("%Y-%m-%dT00:00:00.000000000Z")}
            for mm in metrics:
                if not (mm == "PriceUSD" and d < 3):              # the price starts later than the other metrics
                    row[mm] = str(1.25 * (d + 1))
            rows.append(row)
        body = {"data": rows}
        if k + 10 < n_days:
            body["next_page_url"] = (f"{m.CM}?assets={q['assets']}&metrics={q['metrics']}&frequency=1d&start_time={q['start_time']}"
                                     f"&page_size=10000&paging_from=start&ignore_unsupported_errors=true&next_page_token={k + 10}")
        return httpx.Response(200, json=body)

    # -- DefiLlama
    def llama(self, path):
        pools = [{"pool": p, "project": "aave-v3", "chain": "Ethereum", "symbol": "USDC", "tvlUsd": 1e6, "apyBase": 3.0} for p in m.LLAMA_POOLS]
        pools.append({"pool": "other", "project": "x", "chain": "Base", "symbol": "ETH", "tvlUsd": 5.0, "apyBase": 9.0})
        if path == "/pools":
            return httpx.Response(200, json={"status": "success", "data": pools})
        return httpx.Response(200, json={"status": "success", "data": [
            {"timestamp": f"2023-02-0{i + 6}T23:01:24.670Z", "tvlUsd": 100 + i, "apy": 1.8 + i, "apyBase": 1.8 + i, "apyReward": None,
             "il7d": None, "apyBase7d": None, "pricePerShare": None} for i in range(3)]})


@pytest.fixture
def fake(monkeypatch):
    def install(**cfg):
        f = Fake(**cfg)
        monkeypatch.setattr(m, "_client", lambda: httpx.Client(transport=httpx.MockTransport(f.handler)))
        return f
    sleeps = []
    monkeypatch.setattr(om, "_sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(m, "_sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(m, "_now_s", lambda: NOW)
    # the archive stamps created_at from the wall clock, and the hourly fetch reads a daily bundle's created_at to
    # decide whether a product was still trading when fetched (within 7 days of its last bar): freeze it to NOW too,
    # or the test goes stale once the real date passes NOW + 7 days (it did on 2026-10-22)
    import mandel.archive as _arc
    monkeypatch.setattr(_arc, "utcnow_iso", lambda: datetime.fromtimestamp(NOW, timezone.utc).isoformat())
    install.sleeps = sleeps
    return install


def _archive(tmp_path):
    return Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))


def _rows(arc, name):
    return list(arc.load(name))


def _assert_local_only(arc):
    for e in arc.entries():
        assert e.in_git is False, e.name
        assert m.gitignore_line(e.name) is not None, e.name
        assert fnmatch(f"mandel/archive/data/{e.name}.jsonl.gz", m.gitignore_line(e.name))
        assert e.path.endswith(f"data/{e.name}.jsonl.gz")


# ============================================================================================== Coinbase ==

def test_coinbase_daily_windows_and_daily_history_convention(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(m, "CB_FIRST_DAY", "2025-01-01")             # the family default first, so the bundle is complete
    f = fake()
    arc = _archive(tmp_path)
    rep = m.fetch_coinbase_daily(arc, products=["BTC-USD"], first="2025-01-01", min_interval=0)
    reqs = [q for h, p, q in f.calls if p.endswith("/candles")]
    assert len(reqs) == 3                                             # 652 days: 300 + 300 + 52
    spans = [(_iso(q["start"]), _iso(q["end"])) for q in reqs]
    assert spans[0][0] == m._ts("2025-01-01") and spans[-1][1] == m._ts("2026-10-14")   # the open 2026-10-15 bar is never asked for
    assert all((e - s) // 86400 + 1 <= 300 for s, e in spans)
    assert all(spans[i + 1][0] == spans[i][1] + 86400 for i in range(len(spans) - 1))
    rows = _rows(arc, "coinbase-daily-BTC-USD")
    assert rows == sorted(rows, key=lambda r: r["value"]["t"]) and len({r["value"]["t"] for r in rows}) == len(rows)
    r0 = rows[0]
    assert set(r0["value"]) == {"symbol", "t", "open", "high", "low", "close", "volume"}          # daily-history-<SYM> keys
    assert r0["kind"] == "price" and r0["source"] == "coinbase" and r0["key"] == "BTC-USD"
    t = r0["value"]["t"]
    assert r0["observed_at"] == datetime.fromtimestamp(t, UTC).isoformat()
    assert r0["available_at"] == datetime.fromtimestamp(t + 86400, UTC).isoformat()               # bar time + 24 h
    assert r0["value"]["low"] < r0["value"]["open"] < r0["value"]["close"] < r0["value"]["high"]  # [time, low, high, open, close, volume]
    assert rows[-1]["value"]["t"] <= m._ts("2026-10-14")
    e = arc.get("coinbase-daily-BTC-USD")
    assert "complete" in e.tags and e.in_git is False and rep["coinbase-daily-BTC-USD"]["stored"]["in_git"] is False
    n = len(f.calls)
    m.fetch_coinbase_daily(arc, products=["BTC-USD"], first="2025-01-01", min_interval=0)
    assert len(f.calls) == n                                          # resumable: stored complete -> no request
    m.fetch_coinbase_daily(arc, products=["BTC-USD"], first="2025-01-01", min_interval=0, refresh=True)
    assert len(f.calls) == n + 3
    _assert_local_only(arc)


def test_coinbase_failures_are_never_stored_but_unknown_products_are(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(m, "CB_FIRST_DAY", "2026-01-01")
    f = fake(cb_broken=("BAD-USD",), cb_missing=("GONE-USD",))
    arc = _archive(tmp_path)
    rep = m.fetch_coinbase_daily(arc, products=["BAD-USD", "GONE-USD"], first="2026-01-01", min_interval=0)
    assert rep["coinbase-daily-BAD-USD"]["failed"] and "not_stored" in rep["coinbase-daily-BAD-USD"]
    with pytest.raises(KeyError):
        arc.get("coinbase-daily-BAD-USD")
    gone = arc.get("coinbase-daily-GONE-USD")
    assert gone.rows == 0 and "complete" in gone.tags and "404" in gone.recipe
    n = len(f.calls)
    m.fetch_coinbase_daily(arc, products=["BAD-USD", "GONE-USD"], first="2026-01-01", min_interval=0)
    assert all("BAD-USD" in p for h, p, q in f.calls[n:])            # only the failed product is fetched again


def test_retry_after_is_honoured(fake, tmp_path):
    f = fake(cb_429=1)
    rows = {}
    m.fetch_coinbase_daily(None, products=["BTC-USD"], first="2026-10-01", min_interval=0, rows_out=rows)
    assert max(fake.sleeps) >= 7                                       # waited at least Retry-After
    assert len(rows["coinbase-daily-BTC-USD"]) > 0


def test_coinbase_1m_month_chunks_and_open_month(fake, tmp_path, monkeypatch):
    now = m._ts("2026-10-01") + 2 * 3600 + 30                        # 2026-10-01 02:00:30
    monkeypatch.setattr(m, "_now_s", lambda: now)
    f = fake()
    arc = _archive(tmp_path)
    m.fetch_coinbase_1m(arc, first="2026-09-01", min_interval=0)
    sep, octo = arc.get("coinbase-1m-BTC-USD-2026-09"), arc.get("coinbase-1m-BTC-USD-2026-10")
    assert "complete" in sep.tags and "partial" in octo.tags
    o = _rows(arc, "coinbase-1m-BTC-USD-2026-10")
    assert o[-1]["value"]["t"] == m._ts("2026-10-01") + 2 * 3600 - 60  # the 02:00 minute is still open
    assert o[0]["available_at"] == datetime.fromtimestamp(o[0]["value"]["t"] + 60, UTC).isoformat()
    s = _rows(arc, "coinbase-1m-BTC-USD-2026-09")
    assert s[0]["value"]["t"] == m._ts("2026-09-01") and s[-1]["value"]["t"] <= m._ts("2026-10-01") - 60
    assert "span:2026-09-01..2026-09-30" in sep.tags
    n = len(f.calls)
    m.fetch_coinbase_1m(arc, first="2026-09-01", min_interval=0)
    assert f.calls[n:] and all(_iso(q["start"]) >= m._ts("2026-10-01") for h, p, q in f.calls[n:])   # only the open month again
    _assert_local_only(arc)


def test_hourly_candidates_rank_point_in_time():
    days = [(date(2019, 1, 1) + timedelta(days=i)).isoformat() for i in range(120)]
    daily = {
        "BTC-USD": {d: (100.0, 1000.0) for d in days},
        "USDT-USD": {d: (1.0, 1e9) for d in days},                    # stablecoin: huge volume, never a candidate
        "AAA-USD": {d: (10.0, 100.0) for d in days},
        "BBB-USD": {d: (10.0, 1.0 if d < "2019-03-01" else 500.0) for d in days},   # becomes big in March
        "CCC-USD": {d: (10.0, 50.0) for d in days},
        "LATE-USD": {d: (10.0, 1e6) for d in days if d > "2019-04-10"},  # big only after the selection window
        "STB-USD": {d: (1.0, 1e8) for d in days},                     # flagged fx_stablecoin by Coinbase
        "X-EUR": {d: (1.0, 1e9) for d in days},                       # not USD-quoted
    }
    c = m.hourly_candidates(daily, "2019-01-02", "2019-04-01", top_k=2, stable_ids={"STB-USD"})
    assert set(c) == {"BTC-USD", "AAA-USD", "BBB-USD"}
    assert c["BBB-USD"]["first_top"] > "2019-03-01"                   # trailing 30-day sums: no look-ahead
    assert c["AAA-USD"]["last_top"] < "2019-04-01"                    # pushed out once BBB's trailing volume overtakes it
    assert c["BTC-USD"]["best_rank"] == 1


def test_coinbase_hourly_selects_from_stored_daily_bundles(fake, tmp_path):
    lo = m._ts("2026-09-20")
    f = fake(listed={"ALT-USD": (lo, 10**11)}, vol={"ALT-USD": 1e6, "USDT-USD": 1e9, "MID-USD": 1.0, "LOW-USD": 0.001})
    arc = _archive(tmp_path)
    m.fetch_coinbase_daily(arc, products=["ALT-USD", "USDT-USD", "MID-USD", "LOW-USD"], first="2026-09-01", min_interval=0)
    n = len(f.calls)
    rep = m.fetch_coinbase_hourly(arc, first="2026-09-01", top_k=1, min_interval=0)
    pids = {p.split("/")[2] for h, p, q in f.calls[n:]}
    assert pids == set(m.CB_ALWAYS_HOURLY) | {"ALT-USD", "MID-USD"}    # MID tops the ranking until ALT lists; LOW never ranks;
    alt = [q for h, p, q in f.calls[n:] if "ALT-USD" in p]             # USDT-USD is a stablecoin
    assert _iso(alt[0]["start"]) == lo                                 # starts at the product's first daily bar
    assert rep["_candidates"]["n"] == 2
    r = _rows(arc, "coinbase-hourly-ALT-USD")
    assert r[-1]["value"]["t"] == NOW - NOW % 3600 - 3600 and r[0]["kind"] == "bar1h"
    assert r[0]["available_at"] == datetime.fromtimestamp(r[0]["value"]["t"] + 3600, UTC).isoformat()


def test_coinbase_hourly_stops_at_a_delisted_products_last_day(fake, tmp_path):
    dead = m._ts("2026-09-25")
    f = fake(listed={"DEAD-USD": (0, dead)}, vol={"DEAD-USD": 1e6})
    arc = _archive(tmp_path)
    m.fetch_coinbase_daily(arc, products=["DEAD-USD"], first="2026-09-01", min_interval=0)
    last_daily = max(r["value"]["t"] for r in _rows(arc, "coinbase-daily-DEAD-USD"))
    m.fetch_coinbase_hourly(arc, products=None, first="2026-09-01", top_k=1, min_interval=0)
    q = [q for h, p, q in f.calls if "DEAD-USD" in p and q["granularity"] == "3600"]
    assert _iso(q[-1]["end"]) == last_daily + 86400 - 3600            # not to now: the product stopped trading
    assert max(r["value"]["t"] for r in _rows(arc, "coinbase-hourly-DEAD-USD")) <= dead + 86400 - 3600


def test_fetch_all_passes_the_product_universe_to_the_daily_fetch(fake, tmp_path):
    prods = [{"id": "BTC-USD", "quote_currency": "USD", "status": "online"},
             {"id": "MATIC-USD", "quote_currency": "USD", "status": "delisted"},
             {"id": "BTC-EUR", "quote_currency": "EUR", "status": "online"},
             {"id": "CBETH-ETH", "quote_currency": "ETH", "status": "online"}]
    f = fake(products=prods)
    arc = _archive(tmp_path)
    rep = m.fetch_all_crypto(arc, sources=["coinbase_products", "coinbase_daily"], min_interval=0)
    assert arc.get("coinbase-products-2026-10-15").rows == 4
    daily = sorted(e.name for e in arc.entries() if e.name.startswith("coinbase-daily-"))
    assert daily == ["coinbase-daily-BTC-USD", "coinbase-daily-CBETH-ETH", "coinbase-daily-MATIC-USD"]   # USD (delisted too) + CBETH-ETH
    assert rep["coinbase_daily"]["_already_stored"] == 0
    n = len(f.calls)
    rep = m.fetch_all_crypto(arc, sources=["coinbase_products", "coinbase_daily"], min_interval=0)
    assert len(f.calls) == n and rep["coinbase_daily"]["_already_stored"] == 3
    plan = m.fetch_all_crypto(arc, sources=["coinbase_daily"], dry_run=True, refresh=True)["coinbase_daily"]["_plan"]
    assert plan["bundles"] == 3                                        # the stored snapshot names the bundles in a dry run


def test_coinbase_trades_bisect_window_and_aggressor_side(fake, tmp_path):
    t0 = m._ts("2025-01-31") + 86400 - 60                             # trade i at t0 + 0.5 i: 2025-01-31 23:59 .. 2025-02-01
    f = fake(cb_trades_n=400, cb_trades_t0=t0)
    arc = _archive(tmp_path)
    rows = {}
    rep = m.fetch_coinbase_trades_1m(arc, first="2025-01-31", last="2025-01-31", min_interval=0, rows_out=rows)
    name = "coinbase-trades-1m-BTC-USD-2025-01"
    v = rows[name][0]["value"]
    assert len(rows[name]) == 1 and v["t"] == t0                       # only trades before 2025-02-01 00:00
    assert v["n"] == 119                                               # ids 1..119 (id 120 is at 00:00:00)
    assert v["buy_vol"] == pytest.approx(0.1 * 60) and v["sell_vol"] == pytest.approx(0.1 * 59)   # maker 'sell' = aggressor buy
    assert v["ticks"] and v["mkt_vol"] is None
    assert "partial" in arc.get(name).tags and not rep[name]["complete"]   # one day of January, not the whole month


# ========================================================================================= 1-minute bars ==

def test_minute_agg_ohlc_side_extremes_and_mark_ticks():
    a = m.MinuteAgg("XBTUSD")
    base = m._ts("2024-01-01") + 59 * 60                               # 00:59, the mark minute before 01:00
    a.add(base + 30, 101.0, 2.0, "s", "l", 12)
    a.add(base + 1, 100.0, 1.0, "b", "m", 10)                          # out of order: still the open
    a.add(base + 59.5, 99.0, 1.0, "b", "l", 13)
    a.add(base + 1, 100.5, 1.0, "s", "l", 11)                          # same second, later id
    a.add(base + 70, 105.0, 1.0, "b", "l", 14)                         # next minute (01:00): no ticks
    r = a.rows("kraken")
    v, w = r[0]["value"], r[1]["value"]
    assert (v["open"], v["high"], v["low"], v["close"]) == (100.0, 101.0, 99.0, 99.0)
    assert v["volume"] == 5.0 and v["n"] == 4 and v["buy_vol"] == 2.0 and v["sell_vol"] == 3.0 and v["n_buy"] == 2
    assert (v["buy_hi"], v["buy_lo"], v["sell_hi"], v["sell_lo"]) == (100.0, 99.0, 101.0, 100.5)
    assert v["vwap"] == pytest.approx((100 + 202 + 99 + 100.5) / 5) and v["mkt_vol"] == 1.0 and v["last_id"] == 13
    assert [x[5] for x in v["ticks"]] == [10, 11, 12, 13]              # every trade of the mark minute, in time/id order
    assert "ticks" not in w and r[0]["available_at"] == datetime.fromtimestamp(base + 60, UTC).isoformat()


# ================================================================================================ Kraken ==

def test_kraken_month_paging_since_cursor_and_rate_retry(fake, tmp_path, monkeypatch):
    now = m._ts("2026-10-03")
    monkeypatch.setattr(m, "_now_s", lambda: now)
    t0, dt = m._ts("2026-09-29"), 61.7
    n = int((now - 3600 - t0) / dt)                                    # the tape ends an hour before now
    f = fake(kraken_t0=t0, kraken_dt=dt, kraken_n=n, kraken_errors=["EGeneral:Too many requests"])
    arc = _archive(tmp_path)
    rep = m.fetch_kraken_trades_1m(arc, first="2026-09-01", min_interval=0)
    kr = [q for h, p, q in f.calls if h == "api.kraken.com"]
    assert int(kr[0]["since"]) == m._ts("2026-09-01") * 10**9 - 1 and kr[1]["since"] == kr[0]["since"]   # retried after the rate error
    sep, octo = "kraken-trades-1m-XBTUSD-2026-09", "kraken-trades-1m-XBTUSD-2026-10"
    assert "complete" in arc.get(sep).tags and "partial" in arc.get(octo).tags
    trades = [(t0 + i * dt, i) for i in range(n)]
    want = sum(1 for ts, _ in trades if m._ts("2026-09-01") <= ts < m._ts("2026-10-01"))
    s = _rows(arc, sep)
    assert sum(r["value"]["n"] for r in s) == want and rep[sep]["trades"] == want
    assert all(m._ts("2026-09-01") <= r["value"]["t"] < m._ts("2026-10-01") for r in s)
    one = next(r["value"] for r in s if r["value"]["n"] == 1)
    i = next(i for ts, i in trades if int(ts // 60) * 60 == one["t"])
    assert one["close"] == 100 + i % 11 and (one["buy_vol"] > 0) == bool(i % 3) and one["last_id"] == 1000 + i
    assert sum(r["value"]["n"] for r in _rows(arc, octo)) == sum(1 for ts, _ in trades if ts >= m._ts("2026-10-01"))
    k = len(f.calls)
    m.fetch_kraken_trades_1m(arc, first="2026-09-01", min_interval=0)
    assert all(int(q["since"]) >= m._ts("2026-10-01") * 10**9 - 1 for h, p, q in f.calls[k:])   # only the open month again
    _assert_local_only(arc)


def test_kraken_episode_windows_merge_and_resume(fake, tmp_path):
    f = fake(kraken_t0=m._ts("2020-03-01"), kraken_dt=900.0, kraken_n=8000, kraken_bad_pairs=("USDTZUSD",))
    arc = _archive(tmp_path)
    eps = [("USDC", "USDCUSD", "2020-03-17"), ("USDT", "USDTZUSD", "2020-04-06")]
    rep = m.fetch_kraken_stablecoin_episodes(arc, episodes=eps, min_interval=0)
    assert rep["USDC:2020-03-17"]["complete"] and not rep["USDT:2020-04-06"]["complete"]
    rows = _rows(arc, m.EPISODE_BUNDLE)
    win = [r for r in rows if r["kind"] == "episode-window"]
    assert [w["key"] for w in win] == ["USDC:2020-03-17"]              # the failed window is not stored
    assert win[0]["available_at"] == win[0]["observed_at"] == "2020-03-24T00:00:00+00:00"   # counts: known at the window end
    sig = [r for r in rows if r["kind"] == "episode-signal"]
    assert [r["available_at"] for r in sig] == ["2020-03-18T00:00:00+00:00"]               # the signal close: the next day
    tr = [r for r in rows if r["kind"] == "trade"]
    assert tr and all(m._ts("2020-03-16") <= r["value"]["time"] < m._ts("2020-03-24") for r in tr)
    assert all(r["available_at"] == r["observed_at"] for r in tr)
    k = len(f.calls)
    f.cfg["kraken_bad_pairs"] = ()
    m.fetch_kraken_stablecoin_episodes(arc, episodes=eps, min_interval=0)
    assert {q["pair"] for h, p, q in f.calls[k:]} == {"USDTZUSD"}      # resume: only the missing window
    keys = [r["key"] for r in _rows(arc, m.EPISODE_BUNDLE) if r["kind"] == "episode-window"]
    assert keys == ["USDC:2020-03-17", "USDT:2020-04-06"]


def test_peg_episode_rule():
    closes = {f"2020-01-{d:02d}": x for d, x in enumerate([1.0, 0.999, 0.998, 1.0, 0.9985, 0.994, 0.99, 0.999, 0.998, 0.9990,
                                                            0.9995, 0.9981, 0.9949, 0.9999], 1)}
    assert m.peg_episodes(closes) == ["2020-01-06", "2020-01-13"]


# ========================================================================================= CoinMarketCap ==

def test_cmc_weekly_rows_merge_and_resume(fake, tmp_path):
    f = fake()
    arc = _archive(tmp_path)
    assert m.weekly_days("2017-12-01", "2017-12-12") == ["2017-12-03", "2017-12-04", "2017-12-10", "2017-12-11"]
    m.fetch_cmc_weekly_listings(arc, first="2017-12-01", last="2017-12-12", limit=2, min_interval=0)
    assert [q["date"] for h, p, q in f.calls] == ["2017-12-03", "2017-12-04"] and f.calls[0][2]["limit"] == "500"
    m.fetch_cmc_weekly_listings(arc, first="2017-12-01", last="2017-12-12", min_interval=0)
    assert [q["date"] for h, p, q in f.calls[2:]] == ["2017-12-10", "2017-12-11"]   # stored dates skipped
    rows = _rows(arc, m.CMC_WEEKLY_BUNDLE)
    assert [r["key"] for r in rows if r["kind"] == "snapshot"] == ["2017-12-03", "2017-12-04", "2017-12-10", "2017-12-11"]
    assert len({r["key"] for r in rows}) == len(rows) == 4 * 9
    c2 = next(r for r in rows if r["key"] == "2017-12-04:2")
    assert c2["observed_at"] == "2017-12-04T23:59:59+00:00" and c2["available_at"] == "2017-12-05T00:00:00+00:00"
    assert c2["value"]["flags"] == ["stablecoin", "usd-stablecoin"] and c2["value"]["price"] == 3.0
    assert next(r for r in rows if r["key"] == "2017-12-04:3")["value"]["platform"] == "Ethereum"
    assert len(f.calls) == 4
    m.fetch_cmc_weekly_listings(arc, first="2017-12-01", last="2017-12-12", min_interval=0)
    assert len(f.calls) == 4
    _assert_local_only(arc)


def test_cmc_daily_year_bundles_and_abort(fake, tmp_path):
    f = fake()
    arc = _archive(tmp_path)
    m.fetch_cmc_daily_listings(arc, first="2025-12-30", last="2026-01-02", min_interval=0)
    assert all(q["limit"] == "500" for h, p, q in f.calls) and len(f.calls) == 4
    assert [r["key"] for r in _rows(arc, "cmc-daily-listings-2025") if r["kind"] == "snapshot"] == ["2025-12-30", "2025-12-31"]
    assert [r["key"] for r in _rows(arc, "cmc-daily-listings-2026") if r["kind"] == "snapshot"] == ["2026-01-01", "2026-01-02"]
    f2 = fake(cmc_down=True)
    arc2 = _archive(tmp_path / "b")
    rep = m.fetch_cmc_daily_listings(arc2, first="2026-01-01", last="2026-01-31", min_interval=0)
    assert len(f2.calls) == 5 and rep["cmc-daily-listings-2026"]["aborted"]
    with pytest.raises(KeyError):
        arc2.get("cmc-daily-listings-2026")


def test_cmc_coin_history_pages_backward_400_days(fake, tmp_path):
    f = fake(cmc_coin_first=m._ts("2024-06-01"))
    arc = _archive(tmp_path)
    m.fetch_cmc_coin_history(arc, ids=[1], first="2023-01-01", min_interval=0)
    rows = _rows(arc, "cmc-coin-daily-1")
    assert len(f.calls) == 3 and rows[0]["value"]["day"] == "2024-06-01" and rows[-1]["value"]["day"] == "2026-10-14"   # 400 + 400 + 66
    assert len(rows) == len({r["key"] for r in rows}) == (m._ts("2026-10-14") - m._ts("2024-06-01")) // 86400 + 1
    assert rows[0]["available_at"] == "2024-06-02T00:00:00+00:00"


# =========================================================================== CoinMetrics, blockchain, Llama ==

def test_coinmetrics_paging_and_forbidden_fallback(fake, tmp_path):
    f = fake(cm_days=25)
    arc = _archive(tmp_path)
    rep = m.fetch_coinmetrics(arc, assets={"btc": ["PriceUSD", "CapMVRVCur"], "eth": ["PriceUSD", "SOPR"]}, min_interval=0)
    btc = _rows(arc, "coinmetrics-btc-daily")
    assert len(btc) == 25 and sum(1 for h, p, q in f.calls if q["assets"] == "btc") == 3    # pages of 10 via next_page_url
    assert btc[0]["value"] == {"asset": "btc", "day": "2010-07-01", "CapMVRVCur": 1.25}     # PriceUSD starts later
    assert btc[5]["value"]["PriceUSD"] == pytest.approx(7.5) and btc[5]["available_at"] == "2010-07-07T00:00:00+00:00"
    assert rep["coinmetrics-eth-daily"]["forbidden"] == ["SOPR"] and rep["coinmetrics-eth-daily"]["metrics"] == ["PriceUSD"]
    assert "SOPR" in arc.get("coinmetrics-eth-daily").schema and "cc-by-nc-4.0" in arc.get("coinmetrics-eth-daily").tags
    n = len(f.calls)
    m.fetch_coinmetrics(arc, assets={"btc": ["PriceUSD", "CapMVRVCur"], "eth": ["PriceUSD", "SOPR"]}, min_interval=0)
    assert len(f.calls) == n
    _assert_local_only(arc)


def test_blockchain_hashrate_and_defillama(fake, tmp_path):
    f = fake()
    arc = _archive(tmp_path)
    m.fetch_btc_hashrate(arc, min_interval=0)
    h = _rows(arc, "btc-hashrate-daily")
    assert len(h) == 10 and h[0]["value"]["day"] == "2009-01-03" and h[0]["available_at"] == "2009-01-04T00:00:00+00:00"
    rep = m.fetch_defillama_yields(arc, min_interval=0)
    snap = _rows(arc, "defillama-yields-pools-2026-10-15")
    assert len(snap) == len(m.LLAMA_POOLS) + 1
    ch = _rows(arc, "defillama-yields")
    charts = [r for r in ch if r["kind"] == "chart"]
    assert len(charts) == 3 * len(m.LLAMA_POOLS) and {r["kind"] for r in ch} == {"chart", "pool"}
    assert charts[0]["available_at"] == charts[0]["observed_at"] == "2023-02-06T23:01:24.670000+00:00"
    assert rep["defillama-yields"]["complete"]
    n = len(f.calls)
    m.fetch_defillama_yields(arc, min_interval=0)
    m.fetch_btc_hashrate(arc, min_interval=0)
    assert len(f.calls) == n
    _assert_local_only(arc)


# =============================================================================================== iShares ==

def _ishares_page(days, values, nav_as_of=20250703, nav=55.5):
    obj = {"perf": {"dataPointsByNameMap": {"premiumDiscountChartData": {"name": "premiumDiscountChartData", "asOfDate": days,
                                                                         "value": [str(v) for v in values]}}},
           "hdr": {"navAmount": {"name": "navAmount", "asOfDate": nav_as_of, "value": nav}},
           "facts": {"basketAmt": {"visible": True, "label": "Basket Bitcoin Amount", "formattedValue": "22.64", "formattedAsOfDate": "Jul 03, 2025"},
                     "BasketBitcoinAmount": {"visible": True, "label": "Basket Amount", "formattedValue": "$1,849,077.84",
                                             "infoBubble": "multiplying the NAV by the number of shares in each Basket (40,000).",
                                             "formattedAsOfDate": "Jul 03, 2025"},
                     "sharesOutstanding": {"visible": True, "label": "Shares Outstanding", "formattedValue": "1,422,080,000",
                                           "formattedAsOfDate": "Jul 03, 2025"},
                     "closingPrice": {"visible": True, "label": "Closing Price", "formattedValue": "55.52", "formattedAsOfDate": "Jul 03, 2025"}},
           "g": {"performanceData": {"name": "performanceData", "asOfDate": [20231231, 20240131, 20240229],
                                     "value": ["10000.0", "10000.0", "14484.2"]},
                 "benchmarkData": {"name": "benchmarkData", "asOfDate": [20231231, 20240131, 20240229],
                                   "value": ["10000.0", "10000.0", "14501.0"]}}}
    return f'<html><body><div componentprops="{html.escape(json.dumps(obj), quote=True)}"></div></body></html>'


def test_ishares_parse_available_at_and_accumulating_merge(fake, tmp_path, monkeypatch):
    page = _ishares_page([20250702, 20250703], [-0.12, 0.25])
    assert "&quot;" in page
    p = m.parse_ishares(page)
    assert p["premium"] == [("2025-07-02", -0.12), ("2025-07-03", 0.25)]
    s = p["snapshot"]
    assert s["nav"] == 55.5 and s["nav_as_of"] == "2025-07-03" and s["shares_outstanding"] == 1422080000.0
    assert s["btc_per_share"] == pytest.approx(22.64 / 40000) and s["basket_shares"] == 40000
    assert p["growth"] == [("2023-12-31", 10000.0, 10000.0), ("2024-01-31", 10000.0, 10000.0), ("2024-02-29", 14484.2, 14501.0)]
    f = fake(ishares_page=page)
    arc = _archive(tmp_path)
    m.fetch_ishares_ibit(arc, min_interval=0)
    rows = {r["key"]: r for r in _rows(arc, m.ISH_PREMIUM) if r["kind"] == "premium-discount"}
    assert rows["2025-07-03"]["available_at"] == "2025-07-07T13:30:00+00:00"   # Jul 4 holiday + weekend: Monday 09:30 EDT
    assert rows["2025-07-02"]["available_at"] == "2025-07-03T13:30:00+00:00"
    assert rows["2025-07-03"]["observed_at"] == "2025-07-03T20:00:00+00:00"    # 16:00 EDT
    snap = _rows(arc, m.ISH_SNAP)[0]
    assert snap["available_at"] == "2025-07-07T13:30:00+00:00" and snap["value"]["fetched_day"] == "2026-10-15"
    n = len(f.calls)
    m.fetch_ishares_ibit(arc, min_interval=0)
    assert len(f.calls) == n                                            # today's fetch is stored
    monkeypatch.setattr(m, "_now_s", lambda: NOW + 86400)
    f.cfg["ishares_page"] = _ishares_page([20250703, 20250707], [0.3, 0.5], nav_as_of=20250707, nav=56.0)
    m.fetch_ishares_ibit(arc, min_interval=0)
    prem = {r["key"]: r["value"]["premium_discount_pct"] for r in _rows(arc, m.ISH_PREMIUM) if r["kind"] == "premium-discount"}
    assert prem == {"2025-07-02": -0.12, "2025-07-03": 0.3, "2025-07-07": 0.5}   # old days kept, re-published days replaced
    assert [r["key"] for r in _rows(arc, m.ISH_SNAP)] == ["2025-07-03", "2025-07-07"]
    _assert_local_only(arc)


# ======================================================================================== plans, fetch_all ==

def test_dry_run_makes_no_request_and_plans_every_source(fake, tmp_path):
    fake(forbid=True)
    arc = _archive(tmp_path)
    rep = m.fetch_all_crypto(arc, dry_run=True, include_optional=True)
    for src in list(m.DEFAULT_SOURCES) + list(m.OPTIONAL_SOURCES):
        plan = rep[src]["_plan"]
        assert plan["bundles"] >= 1 and plan["calls"] >= 1, src
        assert all({"bundle", "calls", "rows", "gz_mb", "minutes"} <= set(i) for i in plan["per_bundle"])
    assert rep["kraken_1m"]["_plan"]["calls"] > 60000 and rep["coinbase_1m"]["_plan"]["bundles"] == 58
    assert rep["_total"]["calls"] == sum(rep[s]["_plan"]["calls"] for s in list(m.DEFAULT_SOURCES) + list(m.OPTIONAL_SOURCES))
    assert rep["_gitignore"] == m.GITIGNORE_LINES
    fams = m.family_table(rep)
    assert {f["family"] for f in fams} == {p for p, *_ in m.FAMILIES}
    assert all(f["in_git"] is False and f["gitignore_line"] in m.GITIGNORE_LINES for f in fams)
    assert arc.entries() == []


def test_fetch_all_without_store_returns_rows_and_stores_nothing(fake, tmp_path):
    fake(ishares_page=_ishares_page([20250702], [0.1]))
    rows = {}
    rep = m.fetch_all_crypto(None, sources=["btc_hashrate", "ishares"], rows_out=rows, min_interval=0)
    assert len(rows["btc-hashrate-daily"]) == 10 and len(rows[m.ISH_PREMIUM]) == 3
    assert "stored" not in rep["btc_hashrate"]["btc-hashrate-daily"]
    with pytest.raises(ValueError):
        m.fetch_all_crypto(None, sources=["nope"])


def test_gitignore_lines_cover_every_family_and_licences():
    names = ["coinbase-products-2026-10-15", "coinbase-daily-BTC-USD", "coinbase-hourly-ETH-USD", "coinbase-1m-BTC-USD-2022-01",
             "coinbase-trades-1m-BTC-USD-2025-01", "kraken-trades-1m-XBTUSD-2023-05", "kraken-trades-stablecoin-episodes",
             "cmc-historical-listings", "cmc-daily-listings-2019", "cmc-coin-daily-1027", "coinmetrics-usdt-daily",
             "btc-hashrate-daily", "defillama-yields", "defillama-yields-pools-2026-10-15", "ishares-ibit-premium-discount",
             "ishares-ibit-snapshots"]
    lines = {m.gitignore_line(n) for n in names}
    assert lines == set(m.GITIGNORE_LINES)
    assert m.gitignore_line("coinbase-trades-1m-BTC-USD-2025-01") == "mandel/archive/data/coinbase-trades-1m-*.jsonl.gz"
    assert m.gitignore_line("defillama-yields") == "mandel/archive/data/defillama-yields.jsonl.gz"
    assert m.gitignore_line("daily-history-BTC-USD") is None
    assert "CC BY-NC 4.0" in m.LICENCE["coinmetrics"] and all(m.LICENCE[f[1]] for f in m.FAMILIES)


# ======================================================================== regressions (batch-6c checker) ==

def _top_by_volume(rows, n):
    vol = {}
    for r in rows:
        if r["kind"] == "listing":
            vol[r["value"]["id"]] = vol.get(r["value"]["id"], 0.0) + (r["value"]["volume24h"] or 0.0)
    return [i for i, _ in sorted(vol.items(), key=lambda kv: -kv[1])[:n]]


def test_cmc_daily_depth_500_keeps_high_volume_small_caps_and_refetches_shallow_dates(fake, tmp_path):
    # problem 1: at depth 200 a coin ranked 310 by market cap but #1 by volume never appeared in the volume ranking
    assert m.CMC_DAILY_LIMIT == 500 == m.CMC_WEEKLY_LIMIT
    f = fake(cmc_n=600, cmc_hot={310: 5e9, 254: 4e9})
    arc = _archive(tmp_path)
    m.fetch_cmc_daily_listings(arc, first="2026-10-10", last="2026-10-11", depth=200, min_interval=0)   # the old depth
    assert 310 not in _top_by_volume(_rows(arc, "cmc-daily-listings-2026"), 20)
    n = len(f.calls)
    rep = m.fetch_cmc_daily_listings(arc, first="2026-10-10", last="2026-10-11", min_interval=0)          # the default
    assert [q["limit"] for h, p, q in f.calls[n:]] == ["500", "500"]   # dates stored at depth 200 are fetched again
    rows = _rows(arc, "cmc-daily-listings-2026")
    assert _top_by_volume(rows, 2) == [310, 254]
    assert [r["value"]["limit"] for r in rows if r["kind"] == "snapshot"] == [500, 500]
    assert len(rows) == len({r["key"] for r in rows}) == 2 * 501       # the merge replaced the shallow dates, no duplicates
    assert rep["cmc-daily-listings-2026"]["dates"] == 2
    k = len(f.calls)
    m.fetch_cmc_daily_listings(arc, first="2026-10-10", last="2026-10-11", min_interval=0)
    assert len(f.calls) == k                                            # depth-500 dates are stored: no request
    plan = m.fetch_cmc_daily_listings(_archive(tmp_path / "p"), first="2017-11-01", last="2026-10-14", dry_run=True)["_plan"]
    assert plan["calls"] == 3270 and plan["rows"] == 3270 * 501 and 160 < plan["gz_mb"] < 170
    assert "MARKET CAP" in m.CMC_SCHEMA and "wash-traded" in m.CMC_SCHEMA


def test_a_second_storing_run_on_one_archive_is_refused(fake, tmp_path):
    # problem 2: two writer processes leave stale INDEX entries, so the module refuses a concurrent second run
    fake()
    arc = _archive(tmp_path)
    assert "ONE WRITER AT A TIME" in m.__doc__ and "next to the rest" not in m.__doc__
    with m.run_lock(arc) as path:
        assert path.name == m.RUN_LOCK and fnmatch(f"mandel/archive/{path.name}", "mandel/*/*.lock")   # gitignored lock
        other = _archive(tmp_path)                                      # another process on the same archive root
        with pytest.raises(RuntimeError, match="one process at a time"):
            m.fetch_all_crypto(other, sources=["btc_hashrate"], min_interval=0)
        assert other.entries() == []
        m.fetch_all_crypto(other, sources=["btc_hashrate"], dry_run=True)   # a dry run writes nothing and needs no lock
    rep = m.fetch_all_crypto(arc, sources=["btc_hashrate"], min_interval=0)
    assert rep["_index_check"] == {"ok": True, "bundles": 1}


def test_index_check_reports_an_entry_a_concurrent_writer_reverted(fake, tmp_path, monkeypatch):
    # problem 2 reproduction: B has seen the first merge of cmc-historical-listings and writes it back after A's second
    monkeypatch.setattr(m, "CMC_CHUNK", 1)
    fake()
    arc = _archive(tmp_path)
    b = {}

    def log(msg):
        if msg.startswith(m.CMC_WEEKLY_BUNDLE):
            if "arc" not in b:
                b["arc"] = Archive(root=arc.root, ledger=arc.ledger)
            else:
                b["arc"].store("kraken-trades-1m-XBTUSD-2022-01", "data", [], recipe="process B", in_git=False)
    rep = m.fetch_all_crypto(arc, sources=["cmc_weekly"], limit=2, min_interval=0, log=log)   # two dates, one merge each
    # Archive._reload_index now lets the INDEX on disk win under the store lock, so B's late write no longer reverts A's
    # entry: the reproduction is the regression test, and the INDEX agrees with the file
    assert rep["_index_check"]["ok"] is True, rep["_index_check"]
    fresh = Archive(root=arc.root, ledger=arc.ledger)
    assert fresh.verify(m.CMC_WEEKLY_BUNDLE) is True
    import json as _json                                                # a stale entry written by hand is still caught
    ip = arc.root / "INDEX.json"
    idx = _json.loads(ip.read_text())["bundles"]
    idx[m.CMC_WEEKLY_BUNDLE]["rows"] -= 1
    ip.write_text(_json.dumps({"bundles": idx}))
    chk = m.index_check(arc, {})
    assert chk["ok"] is False and [x["bundle"] for x in chk["mismatched"]] == [m.CMC_WEEKLY_BUNDLE]
    assert chk["mismatched"][0]["index_rows"] < chk["mismatched"][0]["stored_rows"]


def test_narrow_spans_are_partial_and_the_default_run_fetches_them_again(fake, tmp_path):
    # problem 3: a narrower first/last stored 'complete' and every later default run skipped the truncated bundle
    f = fake()
    arc = _archive(tmp_path)
    m.fetch_coinbase_1m(arc, first="2023-03-30", last="2023-03-31", min_interval=0)
    e = arc.get("coinbase-1m-BTC-USD-2023-03")
    assert "partial" in e.tags and "complete" not in e.tags and "span:2023-03-30..2023-03-31" in e.tags
    n = len(f.calls)
    rep = m.fetch_coinbase_1m(arc, first="2023-03-01", last="2023-03-31", min_interval=0)
    assert rep["_already_stored"] == 0 and len(f.calls) - n == 31 * 1440 // 300 + 1
    e = arc.get("coinbase-1m-BTC-USD-2023-03")
    want = sum(1 for t in range(m._ts("2023-03-01"), m._ts("2023-04-01"), 60) if (t // 60) % 13 != 5)
    assert "complete" in e.tags and e.rows == want
    n = len(f.calls)
    assert m.fetch_coinbase_1m(arc, first="2023-03-30", last="2023-03-31", min_interval=0)["_already_stored"] == 1
    assert len(f.calls) == n                                            # a narrower request is covered by the whole month

    m.fetch_coinbase_daily(arc, products=["CBETH-ETH"], first="2026-09-01", min_interval=0)
    assert "partial" in arc.get("coinbase-daily-CBETH-ETH").tags
    n = len(f.calls)
    rep = m.fetch_coinbase_daily(arc, products=["CBETH-ETH"], min_interval=0)          # the default first, 2015-07-20
    assert rep["_already_stored"] == 0 and len(f.calls) - n == 14
    rows = _rows(arc, "coinbase-daily-CBETH-ETH")
    assert "complete" in arc.get("coinbase-daily-CBETH-ETH").tags and rows[0]["value"]["t"] < m._ts("2015-08-01")
    n = len(f.calls)
    m.fetch_coinbase_daily(arc, products=["CBETH-ETH"], first="2026-09-01", min_interval=0)
    assert len(f.calls) == n                                            # covered: skipped
    rep = m.fetch_coinbase_daily(arc, products=["CBETH-ETH"], first="2014-01-01", dry_run=True)
    assert rep["_already_stored"] == 0                                  # a wider request than the stored span is fetched again
    m.fetch_coinbase_daily(arc, products=["BTC-USD"], last="2026-10-01", first="2026-09-20", min_interval=0)
    assert "partial" in arc.get("coinbase-daily-BTC-USD").tags          # a narrower last too

    m.fetch_coinbase_hourly(arc, products=["ETH-USD"], first="2026-10-05", min_interval=0)
    assert "partial" in arc.get("coinbase-hourly-ETH-USD").tags
    assert m.fetch_coinbase_hourly(arc, products=["ETH-USD"], dry_run=True)["_already_stored"] == 0


def test_narrow_kraken_coin_metric_pool_and_window_requests_do_not_hide_the_default(fake, tmp_path, monkeypatch):
    now = m._ts("2026-10-03")
    monkeypatch.setattr(m, "_now_s", lambda: now)
    f = fake(kraken_t0=m._ts("2026-09-01"), kraken_dt=600.0, kraken_n=4000, cmc_coin_first=m._ts("2026-01-01"), cm_days=12)
    arc = _archive(tmp_path)
    m.fetch_kraken_trades_1m(arc, first="2026-09-15", last="2026-09-30", min_interval=0)
    assert "partial" in arc.get("kraken-trades-1m-XBTUSD-2026-09").tags
    rep = m.fetch_kraken_trades_1m(arc, first="2026-09-01", last="2026-09-30", min_interval=0)
    assert rep["_already_stored"] == 0 and "complete" in arc.get("kraken-trades-1m-XBTUSD-2026-09").tags
    assert _rows(arc, "kraken-trades-1m-XBTUSD-2026-09")[0]["value"]["t"] == m._ts("2026-09-01")

    m.fetch_cmc_coin_history(arc, ids=[1], first="2026-06-01", min_interval=0)
    assert "partial" in arc.get("cmc-coin-daily-1").tags
    assert m.fetch_cmc_coin_history(arc, ids=[1], dry_run=True)["_plan"]["bundles"] == 1   # the default run fetches it again

    m.fetch_coinmetrics(arc, assets={"btc": ["PriceUSD"]}, min_interval=0)
    e = arc.get("coinmetrics-btc-daily")
    assert "complete" in e.tags and "has:PriceUSD" in e.tags
    n = len(f.calls)
    m.fetch_coinmetrics(arc, assets={"btc": ["PriceUSD", "CapMVRVCur"]}, min_interval=0)  # more metrics than stored
    assert len(f.calls) > n and "has:CapMVRVCur" in arc.get("coinmetrics-btc-daily").tags
    m.fetch_coinmetrics(arc, assets={"eth": ["PriceUSD"]}, first="2020-01-01", min_interval=0)
    assert "partial" in arc.get("coinmetrics-eth-daily").tags          # a later first than CM_FIRST

    one = dict(list(m.LLAMA_POOLS.items())[:1])
    m.fetch_defillama_yields(arc, pools=one, min_interval=0)
    assert "partial" in arc.get("defillama-yields").tags
    n = len(f.calls)
    m.fetch_defillama_yields(arc, min_interval=0)
    assert sum(1 for h, p, q in f.calls[n:] if p.startswith("/chart/")) == len(m.LLAMA_POOLS)
    assert "complete" in arc.get("defillama-yields").tags and all(f"has:{p}" in arc.get("defillama-yields").tags for p in m.LLAMA_POOLS)

    f2 = fake(kraken_t0=m._ts("2020-03-01"), kraken_dt=900.0, kraken_n=8000)
    eps = [("USDC", "USDCUSD", "2020-03-17")]
    m.fetch_kraken_stablecoin_episodes(arc, episodes=eps, after_days=2, min_interval=0)
    rep = m.fetch_kraken_stablecoin_episodes(arc, episodes=eps, min_interval=0)       # the default window is wider
    assert rep["_already_stored"] == 0 and rep["USDC:2020-03-17"]["complete"]
    win = [r for r in _rows(arc, m.EPISODE_BUNDLE) if r["kind"] == "episode-window"]
    assert len(win) == 1 and win[0]["value"]["end"] == "2020-03-24T00:00:00+00:00"
    k = len(f2.calls)
    assert m.fetch_kraken_stablecoin_episodes(arc, episodes=eps, after_days=2, min_interval=0)["_already_stored"] == 1
    assert len(f2.calls) == k


def test_episode_rows_never_precede_their_observation_and_hide_window_counts(fake, tmp_path):
    # problem 4: the window row (counts through signal + 7 d) was available at signal + 1 d, before its observed_at
    fake(kraken_t0=m._ts("2019-08-15"), kraken_dt=600.0, kraken_n=3000)
    arc = _archive(tmp_path)
    m.fetch_kraken_stablecoin_episodes(arc, episodes=[("USDT", "USDTZUSD", "2019-08-21")], min_interval=0)
    rows = _rows(arc, m.EPISODE_BUNDLE)
    assert all(datetime.fromisoformat(r["available_at"]) >= datetime.fromisoformat(r["observed_at"]) for r in rows)
    sig = next(r for r in rows if r["kind"] == "episode-signal")
    win = next(r for r in rows if r["kind"] == "episode-window")
    assert (sig["observed_at"], sig["available_at"]) == ("2019-08-21T00:00:00+00:00", "2019-08-22T00:00:00+00:00")
    assert "trades" not in sig["value"] and sig["value"]["end"] == "2019-08-28T00:00:00+00:00"
    assert win["available_at"] == win["observed_at"] == win["value"]["end"] and win["value"]["trades"] > 0
    pit = [r for r in rows if r["available_at"] <= "2019-08-22T00:00:00+00:00"]
    assert pit and not any("trades" in r["value"] or "complete" in r["value"] for r in pit)   # no look-ahead at signal + 1 d
    assert max(r["value"]["time"] for r in pit if r["kind"] == "trade") <= m._ts("2019-08-22")


def test_ishares_growth_is_based_at_2024_01_31_without_the_placeholder(fake, tmp_path):
    # problem 5: the 2023-12-31 point (10,000 before the 2024-01-11 launch) was stored and the schema claimed that base
    arc = _archive(tmp_path)
    legacy = {"source": "ishares", "kind": "growth-10k", "key": "2023-12-31", "observed_at": "2024-01-01T05:00:00+00:00",
              "available_at": "2024-01-15T14:30:00+00:00", "value": {"month_end": "2023-12-31", "growth_10k_nav": 10000.0}}
    arc.store(m.ISH_PREMIUM, "data", [legacy], recipe="an earlier run", in_git=False)
    fake(ishares_page=_ishares_page([20250702], [0.1]))
    rep = m.fetch_ishares_ibit(arc, min_interval=0)
    g = [r for r in _rows(arc, m.ISH_PREMIUM) if r["kind"] == "growth-10k"]
    assert [r["key"] for r in g] == ["2024-01-31", "2024-02-29"]       # the stored placeholder is gone too
    assert g[0]["value"]["growth_10k_nav"] == 10000.0 and all(r["value"]["base_month_end"] == "2024-01-31" for r in g)
    assert g[1]["value"]["growth_10k_nav"] / g[0]["value"]["growth_10k_nav"] == pytest.approx(1.44842)
    assert rep[m.ISH_PREMIUM]["growth_base"] == "2024-01-31" and rep[m.ISH_PREMIUM]["growth_placeholders_dropped"] == ["2023-12-31"]
    sch = arc.get(m.ISH_PREMIUM).schema
    assert "BASED AT 2024-01-31" in sch and "since 2023-12-31" not in sch and "m0 >= base_month_end" in sch


def test_cmc_flags_are_snapshot_dated_and_flags_latest_is_labelled(fake, tmp_path):
    # problem 6: early snapshots carry no tags, so flags cannot drive exclusions; the latest tags only draft a declared list
    fake(cmc_untagged_before="2018-01-01")
    arc = _archive(tmp_path)
    m.fetch_cmc_weekly_listings(arc, first="2017-12-03", last="2017-12-03", min_interval=0)
    m.fetch_cmc_weekly_listings(arc, first="2026-10-11", last="2026-10-11", min_interval=0)
    rows = {r["key"]: r["value"] for r in _rows(arc, m.CMC_WEEKLY_BUNDLE)}
    assert rows["2017-12-03:2"]["flags"] == [] and rows["2026-10-11:2"]["flags"] == ["stablecoin", "usd-stablecoin"]
    latest = m.cmc_flags_latest(arc)
    assert latest[2] == {"symbol": "C2", "name": "Coin2", "flags": ["stablecoin", "usd-stablecoin"], "date": "2026-10-11"}
    assert "SNAPSHOT-DATED" in m.CMC_SCHEMA and "declared list of CMC ids" in m.CMC_SCHEMA
    assert "NOT point in time" in m.cmc_flags_latest.__doc__
