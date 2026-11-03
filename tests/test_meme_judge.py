import asyncio
import json

import httpx

from cryptobot import meme_judge as M

T0 = 1_800_000_000.0


def _pool(addr, price, liq, buyers=40, sellers=20, m5=(10, 4), created=T0 - 60, tok="Tok1"):
    return {"attributes": {"address": addr, "name": "X / SOL", "base_token_price_usd": str(price), "reserve_in_usd": str(liq),
                           "fdv_usd": "100000", "pool_created_at": "2027-01-15T08:00:00Z",
                           "transactions": {"m5": {"buys": m5[0], "sells": m5[1]}, "m15": {"buys": m5[0] + 5, "sells": m5[1] + 5},
                                            "h1": {"buyers": buyers, "sellers": sellers}}},
            "relationships": {"base_token": {"data": {"id": f"solana_{tok}"}}}}


def test_rules():
    first = M.parse_pool(_pool("P", 1.0, 50_000), "solana", T0)
    now = M.parse_pool(_pool("P", 1.5, 50_000), "solana", T0 + 1800)
    sec = M.parse_goplus("solana", {"mintable": {"status": "0"}, "freezable": {"status": "0"}})
    d = M.dossier(first, now, sec)
    assert d["buys_prev5"] == 5 and abs(d["move_since_first"] - 0.5) < 1e-12
    assert M.risk(d) is None and M.judge(d)["action"] == "buy"
    assert M.risk(dict(d, security=M.parse_goplus("solana", {"mintable": {"status": "1"}, "freezable": {"status": "0"}}))) == "mint authority live"
    assert M.risk(dict(d, security=M.parse_goplus("solana", None))) == "security unchecked"
    assert M.risk(dict(d, liq=9_000)) == "liquidity < $10k"
    late = M.dossier(first, M.parse_pool(_pool("P", 4.5, 50_000), "solana", T0 + 1800), sec)
    assert M.judge(late)["late"] and M.judge(late)["action"] == "pass"
    thin = M.dossier(first, M.parse_pool(_pool("P", 1.1, 15_000), "solana", T0 + 1800), sec)
    assert M.judge(thin)["exit_risk"] == 4 and M.judge(thin)["action"] == "watch"
    assert M.judge(M.dossier(first, M.parse_pool(_pool("P", 1.1, 50_000, buyers=10), "solana", T0 + 1800), sec))["why"] == "not organic"
    assert M.net_return(1.0, 2.0, 50_000, 50_000) < 1.0
    assert M.net_return(1.0, 2.0, 500, 50_000) == -1.0                    # pool drained: -100%


def test_lifecycle_first_sight_judge_and_outcomes(tmp_path):
    clock = {"t": T0}
    price = {"v": 1.0}

    def handler(req: httpx.Request):
        u = str(req.url)
        if "new_pools" in u:
            return httpx.Response(200, json={"data": [_pool("P1", price["v"], 50_000), _pool("P2", 1.0, 2_000, tok="Tok2")]
                                             if "solana" in u else []})
        if "pools/multi" in u:
            return httpx.Response(200, json={"data": [_pool("P1", price["v"], 50_000), _pool("P2", 1.0, 2_000, tok="Tok2")]})
        if "gopluslabs" in u:
            assert "," not in req.url.params["contract_addresses"]          # one address per call
            assert req.url.params["contract_addresses"] == "Tok1"           # only liquid pools are checked
            return httpx.Response(200, json={"result": {"Tok1": {"mintable": {"status": "0"}, "freezable": {"status": "0"}}}})
        return httpx.Response(404)

    async def sleep(_s):
        return None

    async def run():
        c = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        j = M.MemeJudge(tmp_path, client=c, now=lambda: clock["t"], sleep=sleep)
        await j.discover()
        assert len(j.pools) == 2
        clock["t"] += 1801
        assert await j.process() == 2
        for dt_, px in ((3600, 1.2), (14400, 1.4), (86400, 0.5)):
            clock["t"] = T0 + 1801 + dt_
            price["v"] = px
            await j.process()
        await c.aclose()
    asyncio.run(run())
    rows = [json.loads(l) for l in (tmp_path / "meme" / "verdicts.jsonl").read_text().splitlines()]
    acts = sorted((r["stage"], r["action"]) for r in rows)
    assert acts == [("judge", "buy"), ("outcome", "buy"), ("risk", "pass")]
    out = next(r for r in rows if r["stage"] == "outcome")["out"]
    assert out["4h"] > 0.3 and out["24h"] < -0.4
    rep = M.report(tmp_path)
    assert rep["buy"] == 1 and rep["kills"] == {"liquidity < $10k": 1} and rep["buys"]["n"] == 1
    assert "collecting" in M.render(rep)
