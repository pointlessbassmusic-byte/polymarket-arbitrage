import asyncio
import datetime as dt
import math
import pickle
from types import SimpleNamespace

import httpx

from cryptobot import hype_scanner as HS
from cryptobot import hype_study as H


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat().replace("+00:00", "Z")


def test_message_rate():
    t0 = 1_790_000_000
    msgs = [{"created_at": _iso(t0 + 60 * k), "entities": {"sentiment": {"basic": "Bullish" if k % 3 else "Bearish"}}} for k in range(31)]
    r = HS.message_rate(msgs)
    assert abs(r["rate_per_h"] - 60.0) < 1e-6
    assert r["bull"] == 20 and r["bear"] == 11


def test_snapshot_and_froth(tmp_path):
    clock = {"t": 1_790_000_000.0}
    rate = {"DOGE": 60}

    def handler(req: httpx.Request):
        u = str(req.url)
        if "trending" in u:
            return httpx.Response(200, json={"coins": [{"item": {"symbol": "doge", "market_cap_rank": 9}}]})
        if "coins/markets" in u:
            return httpx.Response(200, json=[{"symbol": "doge", "current_price": 0.2, "total_volume": 1e9 * rate["DOGE"] / 60,
                                              "price_change_percentage_24h": 5, "market_cap": 3e10}])
        if "stocktwits" in u:
            gap = 3600 / rate["DOGE"]
            return httpx.Response(200, json={"messages": [{"created_at": _iso(clock["t"] - gap * k)} for k in range(30)]})
        if "alternative" in u:
            return httpx.Response(200, json={"data": [{"value": "30"}]})
        return httpx.Response(404)

    async def go():
        async def nosleep(_):
            return None
        c = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        s = HS.HypeScanner(tmp_path, tracked={"DOGE": ("DOGE.X", "doge")}, client=c, now=lambda: clock["t"], sleep=nosleep)
        for _ in range(10):
            await s.snapshot()
            clock["t"] += 3600
        rate["DOGE"] = 240
        row = await s.snapshot()
        await c.aclose()
        return row
    row = asyncio.run(go())
    assert not row["errors"] and row["fng"] == 30
    f = HS.froth(HS.rows(tmp_path), tracked={"DOGE": ("DOGE.X", "doge")})["DOGE"]
    assert abs(f["rate_ratio"] - math.log(4)) < 0.05
    assert abs(f["vol_ratio"] - math.log(4)) < 1e-6
    assert f["trending_rank"] == 1 and f["score"] > 2.5
    st = HS.status(tmp_path)
    assert st["rows"] == 11 and HS.render(st)


def test_froth_study_on_synthetic(tmp_path):
    rng = __import__("random").Random(5)
    t0 = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc).timestamp()
    d = {}
    for k in range(40):
        p, cs = 1.0, []
        for i in range(300):
            o = p
            p *= math.exp(rng.gauss(0, 0.04))
            v = 1e6 * math.exp(rng.gauss(0, 0.3))
            cs.append(SimpleNamespace(ts=t0 + 86400 * i, open=o, high=max(o, p) * 1.01, low=min(o, p) * 0.99, close=p, volume_usd=v))
        d[f"C{k}" if k else "DOGE"] = (SimpleNamespace(symbol="x"), cs)
    pickle.dump(d, open(tmp_path / "hl_all_daily.pkl", "wb"))
    res = H.run(tmp_path)
    assert res["coins"] == 40
    assert res["trials"]["froth 7d all"]["n"] > 10
    assert abs(res["trials"]["froth 7d all"]["t"]) < 4
    assert H.render(res)
