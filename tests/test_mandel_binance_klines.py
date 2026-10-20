"""mandel.data.binance_klines on mocked HTTP only (httpx.MockTransport; no network): resolution times through the harness's
parser, windows and margins (open windows never fetched), the kline row convention (available at the candle's close), window
metadata, chunked resumable storing (skip_stored, refresh, interrupt), dry runs that make no request, Retry-After and
failures never stored, the abort statuses, the licence (in_git False), the .gitignore line, the run lock, the CLI preview,
and the T-337 harness reader consuming the stored rows."""

import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from mandel.archive import Archive
from mandel.data import binance_klines as m
from mandel.data import options_misc as om
from mandel.experiments import batch6c_pmxv as hx
from mandel.ledger import Ledger

UTC = timezone.utc
H = 3600
NOON_ET_2025_03_07 = int(datetime(2025, 3, 7, 17, tzinfo=UTC).timestamp())        # 12:00 EST = 17:00 UTC
FIVE_PM_ET_2026_03_20 = int(datetime(2026, 3, 20, 21, tzinfo=UTC).timestamp())    # 17:00 EDT = 21:00 UTC
NOW = FIVE_PM_ET_2026_03_20 + 7 * 86400


def price(t: int) -> float:
    return 100000.0 + (t // 60) % 97                      # a deterministic path: every minute has its own close


class Fake:
    """The data-api.binance.vision klines endpoint on a synthetic tape. ``calls`` logs every request's params."""

    def __init__(self, **cfg):
        self.cfg = cfg
        self.calls = []
        self.n_429 = cfg.get("n_429", 0)
        self.n_500 = cfg.get("n_500", 0)

    def handler(self, req: httpx.Request) -> httpx.Response:
        if self.cfg.get("forbid"):
            raise AssertionError(f"unexpected request {req.url}")
        q = {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}
        assert req.url.host == "data-api.binance.vision" and req.url.path == "/api/v3/klines", str(req.url)
        self.calls.append(q)
        if self.cfg.get("interrupt_at") is not None and len(self.calls) == self.cfg["interrupt_at"]:
            raise KeyboardInterrupt()
        if self.n_429 > 0:
            self.n_429 -= 1
            return httpx.Response(429, headers={"Retry-After": "3"}, json={"code": -1003, "msg": "Too many requests"})
        if self.n_500 > 0:
            self.n_500 -= 1
            return httpx.Response(500, json={"msg": "boom"})
        if self.cfg.get("status"):
            hdr = {"Retry-After": str(self.cfg["retry_after"])} if self.cfg.get("retry_after") else {}
            return httpx.Response(self.cfg["status"], headers=hdr, json={"code": -1, "msg": "nope"})
        assert q["symbol"] == "BTCUSDT" and q["interval"] == "1m" and int(q["limit"]) <= 1000
        s, e = int(q["startTime"]), int(q["endTime"])
        out = []
        t = s - s % 60000
        while t <= e and len(out) < int(q["limit"]):
            if t // 1000 not in self.cfg.get("gaps", ()):
                p = price(t // 1000)
                out.append([t, f"{p - 1:.8f}", f"{p + 2:.8f}", f"{p - 3:.8f}", f"{p:.8f}", "12.5", t + 59999, "1250000.1", 2100, "6.25", "625000.05", "0"])
            t += 60000
        return httpx.Response(200, json=out)


@pytest.fixture
def fake(monkeypatch):
    def make(**cfg):
        f = Fake(**cfg)
        monkeypatch.setattr(m, "_client", lambda: httpx.Client(transport=httpx.MockTransport(f.handler)))
        monkeypatch.setattr(om, "_sleep", lambda s: None)
        monkeypatch.setattr(m, "_now_s", lambda: NOW)
        return f
    return make


@pytest.fixture
def arc(tmp_path):
    return Archive(root=tmp_path / "archive", ledger=Ledger(tmp_path / "ledger.jsonl"))


def event(slug, end_iso, markets, desc=""):
    return {"source": "polymarket", "kind": "event", "key": slug, "observed_at": end_iso, "available_at": end_iso,
            "value": {"id": slug, "slug": slug, "endDate": end_iso, "description": desc, "markets": markets}}


def market(mid, q, slug, group, desc, end):
    return {"id": str(mid), "question": q, "slug": slug, "endDate": end, "groupItemTitle": group, "description": desc,
            "outcomePrices": '["1", "0"]', "clobTokenIds": json.dumps([f"tok{mid}", f"tok{mid}n"])}


NOON_DESC = ('This market will resolve to "Yes" if the Binance 1 minute candle for BTC/USDT 12:00 in the ET timezone (noon) on the date '
             'specified in the title has a final "Close" price higher than the price specified in the title.')
FIVE_DESC = ('This market will resolve to "Yes" if the "Close" price for the BTC/USDT 1 hour candle that ends on the time and date specified '
             'in the title is higher than the price specified in the title.')


def events_bundle():
    noon = event("bitcoin-above-on-march-7-2025", "2025-03-07T17:00:00Z",
                 [market(1, "Will the price of Bitcoin be above $100,000 on March 7?", "bitcoin-above-on-march-7-2025", "100,000", NOON_DESC, "2025-03-07T17:00:00Z"),
                  market(2, "Will the price of Bitcoin be above $95,000 on March 7?", "bitcoin-above-on-march-7-2025", "95,000", NOON_DESC, "2025-03-07T17:00:00Z")])
    five = event("bitcoin-above-on-march-20-2026-5pm-et", "2026-03-20T21:00:00Z",
                 [market(3, "Will the price of Bitcoin be above $80,000 on March 20 at 5pm ET?", "bitcoin-above-on-march-20-2026-5pm-et", "80,000", FIVE_DESC, "2026-03-20T21:00:00Z")])
    rng = event("bitcoin-between-90000-and-95000-on-march-7", "2025-03-07T17:00:00Z",
                [market(4, "Will Bitcoin be between $90,000 and $95,000?", "bitcoin-between-90000-and-95000-on-march-7", None, "range", "2025-03-07T17:00:00Z")])
    return [noon, five, rng]


# ------------------------------------------------------------------------------------------- resolution times, windows --

def test_resolution_times_through_the_harness_parser(arc):
    arc.store(m.EVENTS_BUNDLE, kind="data", rows=events_bundle(), recipe="fake", tags=["polymarket"], in_git=False)
    tl = m.resolution_times(arc)
    assert [(t["res"], t["variant"], t["markets"]) for t in tl] == [(NOON_ET_2025_03_07, "noon", 2), (FIVE_PM_ET_2026_03_20, "5pm", 1)]
    assert tl[0]["slugs"] == ["bitcoin-above-on-march-7"]                      # the parser's slug (its duplicate-suffix rule strips the year)
    # the same parser the harness uses: identical t_res
    mm = dict(events_bundle()[0]["value"]["markets"][0], _event_slug="bitcoin-above-on-march-7-2025", _event_end="2025-03-07T17:00:00Z", _event_description="")
    assert hx.btc_market_spec(mm)["t_res"] == NOON_ET_2025_03_07
    assert m.resolution_times(Archive(root=arc.root / "empty", ledger=arc.ledger)) == []


def test_windows_margins_open_windows_and_day_filters():
    w = m.windows([NOON_ET_2025_03_07, {"res": FIVE_PM_ET_2026_03_20 + 7, "variant": "5pm", "markets": 3}], now_s=NOW)
    assert [x["res"] for x in w] == [NOON_ET_2025_03_07, FIVE_PM_ET_2026_03_20]                   # minute-aligned
    assert w[0]["start"] == NOON_ET_2025_03_07 - 3600 and w[0]["end"] == NOON_ET_2025_03_07 + 3600 and w[0]["bars"] == 121
    assert w[0]["et"] == "12:00" and w[1]["et"] == "17:00" and w[1]["variant"] == "5pm" and w[1]["markets"] == 3
    # a window whose last bar has not closed is never fetched; margins are parameters; day filters
    assert m.windows([NOW - 30 * 60], now_s=NOW) == [] and m.windows([NOW - 61 * 60 - 60], now_s=NOW)[0]["end"] + 60 <= NOW
    assert m.windows([NOON_ET_2025_03_07], 5, 2, now_s=NOW)[0]["bars"] == 8
    assert [x["res"] for x in m.windows([NOON_ET_2025_03_07, FIVE_PM_ET_2026_03_20], now_s=NOW, first="2026-01-01")] == [FIVE_PM_ET_2026_03_20]
    assert [x["res"] for x in m.windows([NOON_ET_2025_03_07, FIVE_PM_ET_2026_03_20], now_s=NOW, last="2025-12-31")] == [NOON_ET_2025_03_07]


# ------------------------------------------------------------------------------------------------ rows and storing --

def test_fetch_rows_convention_window_metadata_and_store(fake, arc):
    f = fake()
    rep = m.fetch_binance_resolution_klines(arc, times=[NOON_ET_2025_03_07, FIVE_PM_ET_2026_03_20], now_s=NOW, min_interval=0)
    assert rep["_windows"] == 2 and rep["_already_stored"] == 0 and rep["_gitignore"] == [m.GITIGNORE_LINE]
    st = rep[m.BUNDLE]
    assert st["windows"] == 2 and st["calls"] == 2 and st["rows"] == 2 * 122 and st["stored"] == 2 and st["chunks"] == 1 and st["failed"] == []
    assert st["first"].startswith("2025-03-07T17:00:00") and st["last"].startswith("2026-03-20T21:00:00")
    q = f.calls[0]
    assert int(q["startTime"]) == (NOON_ET_2025_03_07 - 3600) * 1000 and int(q["endTime"]) == (NOON_ET_2025_03_07 + 3600) * 1000 + 59999
    rows = list(arc.load(m.BUNDLE))
    e = arc.get(m.BUNDLE)
    assert e.in_git is False and e.rows == 244 and "data-api.binance.vision" in e.recipe and "no redistribution" in e.recipe and "local disk only" in e.recipe
    assert set(e.tags) >= {"binance", "1m", "btc-above"} and e.schema == m.SCHEMA
    wins = [r for r in rows if r["kind"] == "window"]
    bars = [r for r in rows if r["kind"] == "bar1m"]
    assert len(wins) == 2 and len(bars) == 242 and rows[0]["kind"] == "window"            # sorted: window row, then its bars
    w0 = wins[0]["value"]
    assert w0 == {"res": NOON_ET_2025_03_07, "res_iso": m.iso(NOON_ET_2025_03_07), "et": "12:00", "variant": None, "markets": None,
                  "start": NOON_ET_2025_03_07 - 3600, "end": NOON_ET_2025_03_07 + 3600, "bars_expected": 121, "bars": 121, "missing": [],
                  "complete": True, "calls": 1}
    assert wins[0]["available_at"] == m.iso(NOON_ET_2025_03_07 + 3600 + 60) and wins[0]["observed_at"] == m.iso(NOON_ET_2025_03_07)
    b = next(r for r in bars if r["value"]["t"] == NOON_ET_2025_03_07)
    assert b["key"] == f"BTCUSDT:{NOON_ET_2025_03_07}" and b["observed_at"] == m.iso(NOON_ET_2025_03_07)
    assert b["available_at"] == m.iso(NOON_ET_2025_03_07 + 60)                               # the candle is known at its close
    assert b["value"]["close"] == price(NOON_ET_2025_03_07) and b["value"]["open"] == price(NOON_ET_2025_03_07) - 1
    assert b["value"]["close_time"] == NOON_ET_2025_03_07 * 1000 + 59999 and b["value"]["trades"] == 2100 and b["value"]["res"] == NOON_ET_2025_03_07
    assert b["value"]["quote_volume"] == 1250000.1 and b["value"]["taker_buy_volume"] == 6.25 and b["value"]["symbol"] == "BTCUSDT"
    assert all(r["value"]["res"] == FIVE_PM_ET_2026_03_20 for r in bars[121:])
    assert arc.verify(m.BUNDLE)


def test_skip_stored_refresh_and_chunked_resume(fake, arc):
    times = [NOON_ET_2025_03_07, NOON_ET_2025_03_07 + 86400, FIVE_PM_ET_2026_03_20]
    f = fake()
    rep = m.fetch_binance_resolution_klines(arc, times=times, now_s=NOW, min_interval=0, chunk=1, limit=2)
    assert rep[m.BUNDLE]["chunks"] == 2 and rep[m.BUNDLE]["stored"] == 2 and len(f.calls) == 2 and arc.get(m.BUNDLE).rows == 244
    # the second run fetches only the window not yet stored and keeps the stored rows
    f2 = fake()
    rep2 = m.fetch_binance_resolution_klines(arc, times=times, now_s=NOW, min_interval=0)
    assert rep2["_already_stored"] == 2 and len(f2.calls) == 1 and rep2[m.BUNDLE]["windows"] == 1 and arc.get(m.BUNDLE).rows == 366
    assert sorted({r["value"]["res"] for r in arc.load(m.BUNDLE)}) == times
    # nothing to do
    f3 = fake()
    rep3 = m.fetch_binance_resolution_klines(arc, times=times, now_s=NOW, min_interval=0)
    assert len(f3.calls) == 0 and rep3[m.BUNDLE]["windows"] == 0 and rep3["_already_stored"] == 3
    # refresh fetches every window again and replaces, not duplicates, the stored rows
    f4 = fake()
    m.fetch_binance_resolution_klines(arc, times=times, now_s=NOW, min_interval=0, refresh=True)
    assert len(f4.calls) == 3 and arc.get(m.BUNDLE).rows == 366 and arc.verify(m.BUNDLE)
    # a gap on the tape is recorded, the window still complete (skip_stored keeps it)
    f5 = fake(gaps={NOON_ET_2025_03_07 + 120})
    rep5 = m.fetch_binance_resolution_klines(arc, times=times[:1], now_s=NOW, min_interval=0, refresh=True)
    w = next(r for r in arc.load(m.BUNDLE) if r["kind"] == "window" and r["value"]["res"] == NOON_ET_2025_03_07)["value"]
    assert w["bars"] == 120 and w["missing"] == [NOON_ET_2025_03_07 + 120] and w["complete"] is True and rep5[m.BUNDLE]["missing_minutes"] == 1


def test_interrupt_stores_the_complete_windows_so_far(fake, arc):
    times = [NOON_ET_2025_03_07, NOON_ET_2025_03_07 + 86400, FIVE_PM_ET_2026_03_20]
    fake(interrupt_at=3)
    rep = {}
    with pytest.raises(KeyboardInterrupt):
        m.fetch_binance_resolution_klines(arc, times=times, now_s=NOW, min_interval=0, report=rep)
    assert rep[m.BUNDLE]["_interrupted"] is True and rep[m.BUNDLE]["stored"] == 2 and arc.get(m.BUNDLE).rows == 244
    fake()
    rep2 = m.fetch_binance_resolution_klines(arc, times=times, now_s=NOW, min_interval=0)
    assert rep2["_already_stored"] == 2 and arc.get(m.BUNDLE).rows == 366


def test_dry_run_makes_no_request_and_plans(fake, arc):
    fake(forbid=True)
    times = [NOON_ET_2025_03_07 + i * 86400 for i in range(10)]
    rep = m.fetch_binance_resolution_klines(arc, times=times, now_s=NOW, dry_run=True)
    p = rep["_plan"]
    assert p["bundle"] == m.BUNDLE and p["windows"] == 10 and p["calls"] == 10 and p["rows"] == 10 * 122 and p["gz_mb"] == round(1220 * m.ROW_GZ / 1e6, 2)
    assert p["minutes"] > 0 and p["span"] == ["2025-03-07", "2025-03-16"] and p["weight_per_minute"] == 400 and rep["_gitignore"] == [m.GITIGNORE_LINE]
    assert m.BUNDLE not in rep and not (arc.root / "data" / f"{m.BUNDLE}.jsonl.gz").exists()
    # a wider margin needs more calls per window; the plan counts them
    p2 = m.fetch_binance_resolution_klines(arc, times=times[:1], now_s=NOW, dry_run=True, before_min=1000, after_min=500)["_plan"]
    assert p2["calls"] == 2 and p2["rows"] == 1502
    # no store at all: rows go to rows_out only
    fake()
    out = {}
    rep3 = m.fetch_binance_resolution_klines(None, times=times[:2], now_s=NOW, min_interval=0, rows_out=out)
    assert len(out[m.BUNDLE]) == 244 and rep3[m.BUNDLE]["stored"] == 0 and rep3[m.BUNDLE]["windows"] == 2


def test_retry_after_failures_and_aborts_never_stored(fake, arc):
    f = fake(n_429=1)
    rep = m.fetch_binance_resolution_klines(arc, times=[NOON_ET_2025_03_07], now_s=NOW, min_interval=0)
    assert len(f.calls) == 2 and rep[m.BUNDLE]["windows"] == 1 and rep[m.BUNDLE]["calls"] == 1            # retried after Retry-After
    f = fake(n_500=4)                                                                                     # beyond the retries: the window fails
    rep = m.fetch_binance_resolution_klines(arc, times=[FIVE_PM_ET_2026_03_20], now_s=NOW, min_interval=0, retries=4)
    assert rep[m.BUNDLE]["windows"] == 0 and len(rep[m.BUNDLE]["failed"]) == 1 and rep[m.BUNDLE]["failed"][0]["status"] == 500
    assert rep[m.BUNDLE]["failed"][0]["res"] == FIVE_PM_ET_2026_03_20 and "aborted" not in rep[m.BUNDLE]
    assert sorted({r["value"]["res"] for r in arc.load(m.BUNDLE)}) == [NOON_ET_2025_03_07]
    # a long Retry-After, a 451 or a 418 ends the run; later windows are not requested
    for cfg in ({"status": 429, "retry_after": 7200}, {"status": 451}, {"status": 418}):
        f = fake(**cfg)
        rep = m.fetch_binance_resolution_klines(arc, times=[FIVE_PM_ET_2026_03_20, FIVE_PM_ET_2026_03_20 + 86400], now_s=NOW, min_interval=0)
        assert rep[m.BUNDLE]["aborted"]["status"] == cfg["status"] and rep[m.BUNDLE]["windows"] == 0 and len(rep[m.BUNDLE]["failed"]) == 1
        assert len(f.calls) == 1                                        # final at once: no retry, and the second window is never requested
    assert sorted({r["value"]["res"] for r in arc.load(m.BUNDLE)}) == [NOON_ET_2025_03_07]
    # a preview cap cuts a window: never stored
    fake()
    rep = m.fetch_binance_resolution_klines(arc, times=[FIVE_PM_ET_2026_03_20], now_s=NOW, min_interval=0, max_calls=1, before_min=1000, after_min=500)
    assert rep[m.BUNDLE].get("truncated") is True and rep[m.BUNDLE]["windows"] == 0
    assert sorted({r["value"]["res"] for r in arc.load(m.BUNDLE)}) == [NOON_ET_2025_03_07]


def test_licence_gitignore_run_lock_and_recipe(arc):
    assert m.GITIGNORE_LINE == "mandel/archive/data/binance-1m-BTCUSDT-btc-above.jsonl.gz"
    assert m.BINANCE_US not in m.recipe() and "data-api.binance.vision" in m.recipe() and "btc_market_spec" in m.recipe()
    with m.run_lock(arc):
        with pytest.raises(RuntimeError):
            with m.run_lock(arc):
                pass
    with m.run_lock(None) as p:
        assert p is None
    assert m.index_check(arc) == {"ok": True, "bundles": 0}


def test_cli_dry_run_and_preview(fake, arc, tmp_path, monkeypatch, capsys):
    fake(forbid=True)
    monkeypatch.setattr(m, "resolution_times", lambda archive=None, bundle=m.EVENTS_BUNDLE: [{"res": NOON_ET_2025_03_07, "variant": "noon", "markets": 2}])
    import mandel.archive as A
    monkeypatch.setattr(A, "Archive", lambda: arc)
    assert m.main(["--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["_plan"]["windows"] == 1 and out["_plan"]["calls"] == 1 and out["_gitignore"] == [m.GITIGNORE_LINE]
    fake()
    d = tmp_path / "preview"
    assert m.main(["--preview", str(d), "--limit", "1"]) == 0
    assert (d / f"{m.BUNDLE}.preview.jsonl.gz").exists() and json.loads((d / "report.json").read_text())[m.BUNDLE]["windows"] == 1
    assert not (arc.root / "data" / f"{m.BUNDLE}.jsonl.gz").exists()                       # a preview stores nothing
    capsys.readouterr()


# ------------------------------------------------------------------------------------------- the harness reads it --

def test_harness_reader_consumes_the_stored_rows(fake, arc):
    fake()
    m.fetch_binance_resolution_klines(arc, times=[NOON_ET_2025_03_07], now_s=NOW, min_interval=0)
    hx._CACHE.clear()
    mins = hx._binance_minutes(arc)
    assert len(mins) == 121 and mins[NOON_ET_2025_03_07] == price(NOON_ET_2025_03_07) and mins[NOON_ET_2025_03_07 - 3600] == price(NOON_ET_2025_03_07 - 3600)
    # the basis: the latest Deribit trade in the hour before t_res against the Binance close of its minute
    li = {NOON_ET_2025_03_07 // H - 1: (int((NOON_ET_2025_03_07 - 1500) * 1000), 99900.0)}
    b = hx.resolution_basis([NOON_ET_2025_03_07], mins, li)
    t_min = (NOON_ET_2025_03_07 - 1500) // 60 * 60
    assert b == {NOON_ET_2025_03_07: pytest.approx(__import__("math").log(price(t_min) / 99900.0))}
    assert hx.resolution_basis([NOON_ET_2025_03_07], mins, {}) == {}                          # no index observation: no basis
    assert hx.resolution_basis([NOON_ET_2025_03_07], mins, {NOON_ET_2025_03_07 // H - 1: (NOON_ET_2025_03_07 * 1000 + 5, 99900.0)}) == {}   # a trade at t_res is not before it
    hx._CACHE.clear()
