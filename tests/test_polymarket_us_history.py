import base64
import json

import httpx
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from cryptobot import polymarket_us_history as U


def _trade(slug, price, qty, cost=None, pnl=None, aggressor=True, ts="2026-09-01T12:00:00Z"):
    return {"type": "ACTIVITY_TYPE_TRADE", "trade": {"id": f"{slug}-{qty}-{pnl}", "marketSlug": slug, "state": "TRADE_STATE_CLEARED",
            "createTime": ts, "price": {"value": str(price), "currency": "USD"}, "qtyDecimal": str(qty), "isAggressor": aggressor,
            "costBasis": {"value": str(cost), "currency": "USD"} if cost is not None else None,
            "realizedPnl": {"value": str(pnl), "currency": "USD"} if pnl is not None else None}}


def _resolution(slug, realized_before, realized_after, side="POSITION_RESOLUTION_SIDE_LONG"):
    return {"type": "ACTIVITY_TYPE_POSITION_RESOLUTION", "positionResolution": {"marketSlug": slug, "side": side,
            "beforePosition": {"realized": {"value": str(realized_before), "currency": "USD"}, "marketMetadata": {"title": "Bitcoin Up or Down"}},
            "afterPosition": {"realized": {"value": str(realized_after), "currency": "USD"}}}}


def test_markets_from_trades_and_settlements():
    acts = []
    for i in range(30):
        slug = f"btc-updown-15m-{i}"
        acts.append(_trade(slug, 0.15, 100, cost=15.0, aggressor=True))
        won = i % 10 == 0
        acts.append(_resolution(slug, 0.0, 85.0 if won else -15.0))
    for i in range(5):
        slug = f"nba-lakers-celtics-{i}"
        acts.append(_trade(slug, 0.60, 50, cost=30.0, aggressor=False))
        acts.append(_trade(slug, 0.70, 50, pnl=5.0, aggressor=True))     # sold early at a profit
    rows = U.markets({"activities": acts, "positions": []})
    assert len(rows) == 35
    btc = [r for r in rows if r["slug"].startswith("btc")]
    assert all(abs(r["entry"] - 0.15) < 1e-9 for r in btc)
    assert sum(r["pnl"] for r in btc) == 3 * 85 - 27 * 15
    nba = [r for r in rows if r["slug"].startswith("nba")]
    assert all(r["pnl"] == 5.0 and r["maker_share"] == 0.5 for r in nba)
    res = U.analyse({"activities": acts, "positions": []})
    assert res["by_category"]["crypto up/down"]["pnl"] < 0
    assert res["rules"] and res["rules"][0]["cell"].startswith("crypto up/down")
    assert "maker" in U.render(res)


def test_client_signs_and_pages():
    sk = ed25519.Ed25519PrivateKey.generate()
    raw = sk.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    secret = base64.b64encode(raw + sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    seen = []

    def handler(req: httpx.Request):
        h = req.headers
        msg = f"{h['X-PM-Timestamp']}GET{req.url.path}".encode()
        sk.public_key().verify(base64.b64decode(h["X-PM-Signature"]), msg)      # raises if the signature is wrong
        seen.append(req.url.params.get("cursor"))
        if req.url.path.endswith("activities"):
            if not req.url.params.get("cursor"):
                return httpx.Response(200, json={"activities": [_trade("a", 0.5, 1, cost=0.5)], "nextCursor": "c2", "eof": False})
            return httpx.Response(200, json={"activities": [_trade("b", 0.5, 1, cost=0.5)], "nextCursor": "", "eof": True})
        return httpx.Response(200, json={"positions": [], "eof": True})

    c = U.Client("kid", secret, client=httpx.Client(transport=httpx.MockTransport(handler)))
    raw = c.fetch()
    assert len(raw["activities"]) == 2 and "c2" in seen
