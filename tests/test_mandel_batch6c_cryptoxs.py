"""Batch-6c crypto cross-section, on-chain and DeFi harnesses (T-314 weekly crypto momentum, T-420 volume-conditioned
momentum, T-400 MVRV regime, T-402 stablecoin supply growth, T-403 hash ribbons, T-367 DeFi lending carry) on synthetic
data only: for every core function a planted effect passes and a null does not; the helpers (episode spells, kernel HAC,
long-book arithmetic, sequential and independent sorts, same-coin supply growth, the 7-day APY, the bill conversions,
the declared exclusions, the CMC panel's last-price marks and peg screen, the MVRV rule's minimum hold, the hash-ribbon
cancellation) are checked directly; every harness runs JSON-safe on a fake archive, and missing bundles give
inconclusive. No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

import mandel.experiments.batch6b_bw as bw
from mandel.experiments import batch6c_cryptoxs as m


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(m, "N_PERM", 200)
    monkeypatch.setattr(bw, "REPS_MAX", 3)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


BILLS = m.Bills({"1990-01-02": 2.0})
_EPOCH = date(1970, 1, 1).toordinal()


def cdays(start, end="2026-10-14"):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def bdays(start, end="2026-10-14"):
    return [d for d in cdays(start, end) if date.fromisoformat(d).weekday() < 5]


def nxt(d, k=1):
    return (date.fromisoformat(d) + timedelta(days=k)).isoformat()


# ------------------------------------------------------------------------------------------------- generators --

def cmc_rows(n_weeks=470, n_coins=60, drift=0.0, seed=0, stable=True):
    """Weekly CMC-style listings (Sunday and Monday) from 2017-12-03. Coin 1 is the benchmark (no drift). Each coin has a
    regime (+1 / -1) redrawn every 12 weeks; its weekly log return is drift x regime + noise, so past returns reveal the
    regime when drift > 0. Coin 999 (optional) is a 1-USD peg with the largest market cap (the peg screen must drop it)."""
    rng = np.random.default_rng(seed)
    start = date(2017, 12, 3)
    supply = rng.uniform(1e6, 1e8, n_coins)
    logp = np.log(rng.uniform(1, 100, n_coins))
    logp[0], supply[0] = math.log(10000.0), 1e7
    regime = rng.choice([-1.0, 1.0], n_coins)
    rows = []
    for w in range(n_weeks):
        sun = start + timedelta(days=7 * w)
        if w % 12 == 0:
            regime = rng.choice([-1.0, 1.0], n_coins)
        for d, lp in ((sun, logp), (sun + timedelta(days=1), logp + rng.normal(0, 0.002, n_coins))):
            px = np.exp(lp)
            mc = px * supply
            ids = list(range(1, n_coins + 1))
            pxs, mcs = list(px), list(mc)
            if stable:
                ids.append(999)
                pxs.append(1.0 + rng.normal(0, 0.001))
                mcs.append(1e13)
            order = np.argsort(-np.array(mcs))
            rank = np.empty(len(ids), int)
            rank[order] = np.arange(1, len(ids) + 1)
            ds = d.isoformat()
            rows.append({"kind": "snapshot", "available_at": nxt(ds) + "T00:00:00+00:00", "value": {"date": ds, "n": len(ids), "limit": 500}})
            for j, cid in enumerate(ids):
                rows.append({"kind": "listing", "available_at": nxt(ds) + "T00:00:00+00:00",
                             "value": {"date": ds, "id": cid, "symbol": f"C{cid}", "slug": f"coin-{cid}", "name": f"Coin {cid}",
                                       "cmcRank": int(rank[j]), "price": float(pxs[j]), "volume24h": 1e6, "marketCap": float(mcs[j])}})
        step = rng.normal(0, 0.03, n_coins) + drift * regime
        step[0] = rng.normal(0, 0.03)
        logp = logp + step
    return rows


def sim_month_panel(labels, N, a, seed, J=6, noise=0.02, depth=False):
    """Monthly panel; with a != 0 the J-month low-turnover winners (high-turnover losers) chosen at decision t earn +a (-a)
    in each of the next three hold months (the K = 3 overlap)."""
    rng = np.random.default_rng(seed)
    T = len(labels)
    P, R = np.full((N, T), np.nan), np.full((N, T), np.nan)
    TURN = rng.uniform(0.5, 1.5, (N, T))
    ELIG = np.ones((N, T), bool)
    eff = np.zeros((N, T + 3))
    P[:, 0] = 100.0
    for t in range(T):
        if t >= 1:
            P[:, t] = P[:, t - 1] * (1 + R[:, t - 1])
        if a and t - 1 - J >= 0:
            mom = P[:, t - 1] / P[:, t - 1 - J] - 1
            w = m.cohort_weights(mom, TURN[:, t], ELIG[:, t], "ls", "LS")
            for k in range(3):
                eff[w > 0, t + k] += a
                eff[w < 0, t + k] -= a
        R[:, t] = rng.normal(0.005, noise, N) + eff[:, t]
    out = {"labels": labels, "syms": [f"A{i}" for i in range(N)], "P": P, "R": R, "TURN": TURN, "ELIG": ELIG, "rf": np.full(T, 0.002),
           "n_universe_months": T, "depth": {"months_checked": T, "months_binding": 3 if depth else 0, "binding_examples": [],
                                             "max_member_rank_median": 100.0, "max_member_rank_max": 450 if depth else 300}}
    return out


def months(a, b):
    return m._mrange(a, b)


def sim_mvrv(planted, seed=0, start="2010-07-18", end="2026-10-14"):
    rng = np.random.default_rng(seed)
    days = cdays(start, end)
    k = np.arange(len(days))
    ph = 2 * math.pi * k / 1460.0
    mv = np.exp(0.4 + 1.3 * np.sin(ph))
    drift = (-0.004 * np.sin(ph)) if planted else np.full(len(days), 0.0008)
    lp = np.log(100.0) + np.cumsum(drift + rng.normal(0, 0.02, len(days)))
    return dict(zip(days, mv)), dict(zip(days, np.exp(lp)))


def sim_supply(planted, seed=0, start="2017-01-01", end="2026-10-14"):
    rng = np.random.default_rng(seed)
    days = cdays(start, end)
    n = len(days)
    u = np.zeros(n)
    for t in range(1, n):
        u[t] = 0.98 * u[t - 1] + rng.normal(0, 0.0005)
    S = 1e9 * np.exp(np.cumsum(0.001 + u))
    usdt = dict(zip(days, S))
    usdc = {d: 1e8 * (1 + 0.001 * i) for i, d in enumerate(days) if d >= "2018-10-01"}
    g = np.full(n, np.nan)
    tot = np.array([usdt[d] + usdc.get(d, 0.0) for d in days])
    for t in range(31, n):
        d1, d0 = days[t - 1], days[t - 31]
        s1 = usdt[d1] + (usdc[d1] if (d1 in usdc and d0 in usdc) else 0.0)
        s0 = usdt[d0] + (usdc[d0] if (d1 in usdc and d0 in usdc) else 0.0)
        g[t] = s1 / s0 - 1
    b = 3.0 if planted else 0.0
    r = np.where(np.isfinite(g), b / 30.0 * g, 0.0) + rng.normal(0, 0.03, n)
    price = dict(zip(days, 1000.0 * np.exp(np.cumsum(r))))
    return {"usdt": usdt, "usdc": usdc}, price


def sim_hash(planted, seed=0, start="2009-01-03", end="2026-10-14"):
    rng = np.random.default_rng(seed)
    days = cdays(start, end)
    n = len(days)
    k = np.arange(n)
    lh = 0.001 * k
    for c in range(200, n, 270):                                      # an 80-day dip of up to 30% every 270 days
        w = np.arange(n) - c
        lh += np.where((w >= 0) & (w < 80), -0.30 * np.sin(np.pi * np.clip(w, 0, 80) / 80), 0.0)
    H = np.exp(lh + rng.normal(0, 0.003, n))
    rec = m.ribbon_signals(H, np.full(n, 100.0), "live")[1]
    drift = np.zeros(n)
    if planted:
        for r_ in rec:
            drift[r_ + 1:r_ + 121] += 0.006
    lp = np.log(100.0) + np.cumsum(drift + rng.normal(0, 0.025, n))
    hb = dict(zip(days, H))
    hc = {d: v * (1 + rng.normal(0, 0.002)) for d, v in hb.items() if d >= "2010-07-01"}
    return {"a": hb, "b": hc}, dict(zip(days, np.exp(lp)))


def sim_pools(apy_level, seed=0):
    rng = np.random.default_rng(seed)
    out = {}
    spans = {m.AAVE: ("2023-02-06", 2e8), m.MAPLE: ("2025-07-28", 2.8e9), m.SPARK_SAV: ("2025-12-22", 3e8),
             m.SPARKLEND: ("2023-08-11", 5e6)}
    for p, (a, tvl) in spans.items():
        pts = {}
        for d in cdays(a, "2026-10-16"):
            pts[d] = (float(apy_level + rng.normal(0, 0.3)), float(tvl * (1 + rng.normal(0, 0.01))), d + "T23:01:00+00:00")
        out[p] = pts
    return out


# --------------------------------------------------------------------------------------------------- helpers --

def test_spells_merge_gaps():
    mask = np.array([1, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1], bool)
    assert m.spells(mask, 0) == [(0, 1), (4, 4), (9, 10)]
    assert m.spells(mask, 2) == [(0, 4), (9, 10)]
    assert m.spells(mask, 4) == [(0, 10)]
    assert m.spells(np.zeros(5, bool), 3) == []


def test_ols_kernel_bartlett_matches_ols_hac_and_uniform_differs():
    rng = np.random.default_rng(1)
    x = rng.normal(size=400)
    y = 0.5 * x + rng.normal(size=400)
    a = m.ols_kernel(y, x, 12, "bartlett")
    b = bw.ols_hac(y, x, 12)
    assert a["beta"] == pytest.approx(b["beta"])
    assert a["se"] == pytest.approx(b["se_beta"])
    u = m.ols_kernel(y, x, 12, "uniform")
    assert u["beta"] == pytest.approx(a["beta"]) and u["se"] != pytest.approx(a["se"])


def test_long_book_turnover_drift_and_costs():
    W = [{1: 0.5, 2: 0.5}, {1: 0.5, 2: 0.5}, {3: 1.0}]
    R = [{1: 0.10, 2: -0.10}, {1: 0.0, 2: 0.0}, {3: 0.0}]
    b = m.long_book(W, R, 0.01)
    assert b["turnover"][0] == pytest.approx(1.0)                 # entry from cash
    assert b["gross"][0] == pytest.approx(0.0)
    # after week 1 the drifted weights are 0.55 / 0.45: rebalancing to 0.5 / 0.5 trades 0.1
    assert b["turnover"][1] == pytest.approx(0.1)
    assert b["turnover"][2] == pytest.approx(2.0)
    assert b["net"][1] == pytest.approx((1 - 0.001) * 1.0 - 1)


def test_cohort_weights_sequential_sorts():
    mom = np.arange(18, dtype=float)                               # 17 is the best
    turn = np.array([5, 4, 3, 2, 1, 0] * 3, float)
    el = np.ones(18, bool)
    u = m.cohort_weights(mom, turn, el, None, "LS")
    assert (u > 0).sum() == 6 and (u < 0).sum() == 6 and u.sum() == pytest.approx(0)
    c = m.cohort_weights(mom, turn, el, "ls", "LS")
    winners = np.argsort(-mom)[:6]
    lg = np.flatnonzero(c > 0)
    assert set(lg) <= set(winners) and len(lg) == 2
    assert set(lg) == set(winners[np.argsort(turn[winners], kind="stable")[:2]])
    sh = np.flatnonzero(c < 0)
    losers = np.argsort(mom)[:6]
    assert set(sh) <= set(losers) and set(sh) == set(losers[np.argsort(-turn[losers], kind="stable")[:2]])
    lo = m.cohort_weights(mom, turn, el, "conf", "LO")
    assert (lo < 0).sum() == 0 and lo.sum() == pytest.approx(1.0)
    assert m.cohort_weights(mom[:8], turn[:8], el[:8], "ls", "LS").sum() == 0      # k = 2 < 3: no conditioned book
    ind = m.cohort_weights_indep(mom, turn, el, "ls", "LS")
    assert ind.sum() == pytest.approx(0) or (ind == 0).all()


def test_supply_growth_same_coin_and_lag():
    s = {"a": {"2020-01-01": 100.0, "2020-01-31": 110.0}, "b": {"2020-01-31": 50.0}}
    # day 2020-02-01 reads 2020-01-31 vs 2020-01-01; coin b exists only on the later day: its appearance is not growth
    assert m.supply_growth(s, "2020-02-01") == pytest.approx(0.10)
    assert m.supply_growth(s, "2020-02-02") is None


def test_apy7_bills_conversions_and_exclusions():
    pts = {nxt("2024-01-01", k): float(k) for k in range(7)}
    assert m.apy7(pts, "2024-01-07") == pytest.approx(3.0)
    assert m.apy7({"2024-01-07": 1.0}, "2024-01-07") is None
    assert m.bey(5.0) == pytest.approx(100 * 365 * 0.05 / (360 - 91 * 0.05))
    assert m.eff_annual(5.0) > m.bey(5.0) > 5.0
    assert m.declared_excluded(825, "tether") and m.declared_excluded(123456, "wrapped-foo")
    assert m.declared_excluded(123456, "venus-bnb") and not m.declared_excluded(8000, "lido-dao")
    assert not m.declared_excluded(5692, "compound") and not m.declared_excluded(7278, "aave")


def test_cmc_panel_last_price_and_peg_screen():
    rows = []
    for k, d in enumerate(cdays("2024-01-01", "2024-01-10")):
        for cid, px in ((1, 40000.0 + 100 * k), (2, 1.0 + 0.001 * (k % 2)), (3, 40000.0 + 100 * k + 5), (4, 5.0 + k)):
            if cid == 4 and k >= 5:
                continue                                           # coin 4 vanishes after 2024-01-05
            rows.append({"kind": "listing", "value": {"date": d, "id": cid, "symbol": f"C{cid}", "slug": f"c{cid}", "cmcRank": cid,
                                                      "price": px, "volume24h": 1.0, "marketCap": 1.0}})
    P = m.CmcPanel([rows])
    assert P.price(4, 4) == pytest.approx(9.0) and P.price(4, 6) is None
    assert P.last_price(4, 8) == (pytest.approx(9.0), 4)
    assert P.last_price(4, 8, lo=4) == (None, None)
    peg = P.pegged([2, 3, 4], list(range(4, 10)), 5)
    assert peg == {2, 3}                                           # 2 pegs 1 USD, 3 tracks BTC (id 1)


def _daily_rows(days, n_coins=60, seed=0, drop=None, swap=None):
    """Daily CMC-style listings: coin 1 is BTC-like; ``drop`` {day: ids absent}, ``swap`` {day: keep-ids}: on that day
    every other id is replaced by a fresh id (+3000), as in the corrupt 2020-11-30 snapshot."""
    rng = np.random.default_rng(seed)
    lp = np.log(rng.uniform(5, 500, n_coins))
    lp[0] = math.log(10000.0)
    supply = rng.uniform(1e6, 1e8, n_coins)
    vol = rng.uniform(1e6, 1e9, n_coins)
    rows = []
    for d in days:
        px = np.exp(lp)
        mc = px * supply
        rank = np.empty(n_coins, int)
        rank[np.argsort(-mc)] = np.arange(1, n_coins + 1)
        for j in range(n_coins):
            cid = j + 1
            if drop and cid in drop.get(d, ()):
                continue
            if swap and d in swap and cid not in swap[d]:
                cid += 3000
            rows.append({"kind": "listing", "available_at": nxt(d) + "T00:00:00+00:00",
                         "value": {"date": d, "id": cid, "symbol": f"C{cid}", "slug": f"coin-{cid}", "name": f"Coin {cid}",
                                   "cmcRank": int(rank[j]), "price": float(px[j]), "volume24h": float(vol[j] * rng.uniform(0.8, 1.2)),
                                   "marketCap": float(mc[j])}})
        lp = lp + rng.normal(0, 0.02, n_coins)
    return rows


def test_snapshot_screen_flags_corrupt_days_and_treats_them_as_missing():
    days = cdays("2024-01-01", "2024-01-12")
    rows = _daily_rows(days, swap={"2024-01-05": {1}}, drop={"2024-01-07": {7}, "2024-01-09": set(range(2, 32))})
    P = m.CmcPanel([rows])
    # 01-05 shares 1 of 60 ids with both neighbours (which share all): corrupt; 01-09 lacks 30 of the neighbours' common top
    # 50 (the 2021-09-28 short-snapshot case); one coin missing on 01-07 is not a corrupt day
    assert set(P.flagged) == {"2024-01-05", "2024-01-09"}
    assert P.flagged["2024-01-05"]["overlap_prev"] < 0.8 and P.flagged["2024-01-09"]["top50_missing"] >= 3
    k5 = P.dpos["2024-01-05"]                                       # the date stays in the index (calendars stay aligned)
    assert P.price(1, k5) is None and P.price(3003, k5) is None and P.day(k5)[0].size == 0
    assert P.last_price(3, k5) == (pytest.approx(P.price(3, k5 - 1)), k5 - 1)      # marks skip the flagged day
    assert P.seen_after(7, P.dpos["2024-01-07"]) and not P.seen_after(3003, 0)
    U = m.CmcPanel([rows], screen=False)                            # without the screen the corrupt day is used as data
    assert U.flagged == {} and U.price(3003, k5) is not None


def test_hold_return_stress_marks_only_coins_that_never_return():
    days = cdays("2024-01-01", "2024-01-12")
    drop = {d: {4} for d in days if d > "2024-01-05"}
    drop["2024-01-07"] = {4, 5}
    rows = _daily_rows(days, n_coins=8, drop=drop)
    P = m.CmcPanel([rows], screen=False)
    k = P.dpos
    # coin 5 is below the depth on 01-07 only and comes back: last-price mark (entry price, 0 return) in both cases
    assert m.hold_return(P, 5, k["2024-01-06"], k["2024-01-07"]) == pytest.approx(0.0)
    assert m.hold_return(P, 5, k["2024-01-06"], k["2024-01-07"], stress=True) == pytest.approx(0.0)
    # coin 4 vanishes for good after 01-05: the stress marks its last price down 50%
    assert m.hold_return(P, 4, k["2024-01-05"], k["2024-01-06"]) == pytest.approx(0.0)
    assert m.hold_return(P, 4, k["2024-01-05"], k["2024-01-06"], stress=True) == pytest.approx(-0.5)
    p0, p1 = P.price(2, k["2024-01-03"]), P.price(2, k["2024-01-04"])
    assert m.hold_return(P, 2, k["2024-01-03"], k["2024-01-04"], stress=True) == pytest.approx(p1 / p0 - 1)


def test_mvrv_rule_min_hold_and_drift():
    sig = np.array([2.0, 0.5, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0])
    r = np.full(10, 0.01)
    b = np.zeros(10)
    out, tg = m.mvrv_rule(sig, r, b, 1.0, 3.0, 0.0, min_hold=7)
    assert list(tg[:8]) == [0.5] * 7 + [0.5]
    assert tg[1] == 0.5                                            # the switch to 1.0 waits for the 7-day minimum hold
    out2, tg2 = m.mvrv_rule(np.array([0.5] * 10), r, b, 1.0, 3.0, 0.001)
    assert (tg2 == 1.0).all() and out2[0] == pytest.approx((1 - 0.001) * 1.01 - 1)


def test_ribbon_signals_cancel_on_new_capitulation():
    n = 400
    H = np.ones(n)
    H[100:160] = 0.7                                               # a dip
    P = np.full(n, 100.0)                                          # flat price: momentum never confirms
    sig, rec = m.ribbon_signals(H, P, "live")
    assert rec and not sig
    P2 = 100.0 * np.exp(np.concatenate([np.zeros(200), 0.01 * np.arange(1, n - 199)]))
    sig2, rec2 = m.ribbon_signals(H, P2, "live")
    assert sig2 and sig2[0] >= rec2[0]
    sig3, _ = m.ribbon_signals(H, P2, "prev")
    assert sig3[0] >= sig2[0]


# ------------------------------------------------------------------------------------------------ core: T-314 --

def test_t314_planted_momentum_passes():
    P = m.CmcPanel([cmc_rows(drift=0.04, seed=1)])
    j = m.xs_momentum_weekly(P)
    assert j["n"] >= 400
    assert j["verdict"] == "supported", j["criteria"]
    assert "C999" in j["excluded"]                                 # the 1-USD peg is screened out
    assert j["mean_test"]["est"] > 0


def test_t314_null_fails():
    P = m.CmcPanel([cmc_rows(drift=0.0, seed=2)])
    j = m.xs_momentum_weekly(P)
    assert j["verdict"] != "supported"


def test_t314_weekday_light_mode():
    P = m.CmcPanel([cmc_rows(drift=0.04, seed=1)])
    o = m.xs_momentum_weekly(P, weekday=6, light=True)
    assert set(o) == {"n", "mean", "first", "last", "flag_dropped"} and o["mean"] > 0 and o["flag_dropped"] == []
    assert m.xs_momentum_weekly(P, weekday=2, light=True).get("too_short")     # no Wednesday snapshots


def _corrupt_monday(rows, day="2020-11-30"):
    """The 2020-11-30 defect: every id but BTC's replaced on one Monday snapshot."""
    out = []
    for r in rows:
        v = r["value"]
        if r["kind"] == "listing" and v["date"] == day and v["id"] != 1:
            v = dict(v, id=v["id"] + 5000, symbol=f"X{v['id']}", slug=f"old-{v['id']}")
            r = dict(r, value=v)
        out.append(r)
    return out


def test_t314_corrupt_snapshot_drops_the_weeks_that_need_it():
    clean = cmc_rows(drift=0.04, seed=1)
    j0 = m.xs_momentum_weekly(m.CmcPanel([clean]))
    rows = _corrupt_monday(clean)
    P = m.CmcPanel([rows])
    assert set(P.flagged) == {"2020-11-30"}
    j = m.xs_momentum_weekly(P)
    assert j["flag_dropped_weeks"] == ["2020-11-23", "2020-11-30"]          # the week exiting and the week entering on it
    assert j["n"] == j0["n"] - 2 and "2020-11-30" not in j["labels"] and "2020-11-23" not in j["labels"]
    assert j["n_vanished"] == 0 and j["stress_mean"] == pytest.approx(j["mean_test"]["est"])
    assert j["verdict"] == "supported" and j["n_long"]["min"] == 10
    # without the screen the corrupt Monday is used: held coins look vanished and the entry week is cut short
    ju = m.xs_momentum_weekly(m.CmcPanel([rows], screen=False))
    assert ju["n"] == j0["n"] and ju["n_vanished"] > 0 and ju["n_long"]["min"] < 10
    # ... but every one of them comes back, so the vanished-coin stress no longer marks them down
    assert ju["n_vanished_returned"] == ju["n_vanished"] and ju["n_vanished_gone"] == 0
    assert ju["stress_mean"] == pytest.approx(ju["mean_test"]["est"])


def test_t314_book_size_follows_the_eligible_count():
    rows = cmc_rows(drift=0.04, seed=1)
    d200 = (date(2017, 12, 3) + timedelta(days=7 * 200)).isoformat()
    top = sorted((r["value"]["cmcRank"], r["value"]["id"]) for r in rows
                 if r["kind"] == "listing" and r["value"]["date"] == d200 and r["value"]["id"] not in (1, 999))
    new = top[0][1]                                                 # a top-30 coin first listed on week 200
    rows = [r for r in rows if not (r["kind"] == "listing" and r["value"]["id"] == new and r["value"]["date"] < d200)]
    j = m.xs_momentum_weekly(m.CmcPanel([rows]))
    # weeks 200-202 have no price 3 weeks earlier for it: 29 eligible, floor(29/3) = 9 names
    assert j["dropped_coin_weeks"] == {"formation": 3, "entry": 0}
    assert j["n_long"]["min"] == 9 and j["n_long"]["max"] == 10 and j["n_long"]["weeks_by_size"]["9"] == 3
    assert sum(j["n_long"]["weeks_by_size"].values()) == j["n"]


# ------------------------------------------------------------------------------------------------ core: T-420 --

def test_t420_planted_conditioning_passes():
    etf = sim_month_panel(months("2005-01", "2026-09"), 60, 0.02, seed=3)
    cr = sim_month_panel(months("2017-11", "2026-09"), 40, 0.0, seed=4)
    j = m.volume_momentum(etf, cr)
    assert j["n"] == 237
    assert j["verdict"] == "supported", j["criteria"]


def test_t420_null_fails():
    etf = sim_month_panel(months("2005-01", "2026-09"), 60, 0.0, seed=5)
    cr = sim_month_panel(months("2017-11", "2026-09"), 40, 0.0, seed=6)
    j = m.volume_momentum(etf, cr)
    assert j["verdict"] == "not_supported"


def test_t420_depth_binding_and_missing_crypto_cap_the_family_criteria():
    etf = sim_month_panel(months("2005-01", "2026-09"), 60, 0.02, seed=3)
    cr = sim_month_panel(months("2017-11", "2026-09"), 40, 0.0, seed=4, depth=True)
    j = m.volume_momentum(etf, cr)
    assert j["depth_binds"] and j["verdict"] != "supported"
    j2 = m.volume_momentum(etf, None)
    assert not j2["have_crypto"] and j2["verdict"] != "supported"


def test_t420_crypto_panel_flagged_month_end_uses_last_intact_day():
    days = cdays("2019-01-01", "2019-05-31")
    rows = _daily_rows(days, n_coins=40, seed=21, swap={"2019-03-31": {1}})
    C = m.CmcPanel([rows])
    assert set(C.flagged) == {"2019-03-31"}
    out = m.crypto_panel(C, None, first="2019-01", last="2019-05")
    assert out["substituted_month_ends"] == {"2019-03": {"stored_last_day": "2019-03-31", "month_end_used": "2019-03-30"}}
    t = out["labels"].index("2019-03")
    assert out["ELIG"][:, t].sum() == 20                            # the March universe is built from 03-30
    k30 = C.dpos["2019-03-30"]
    P = out["P"][:, t]
    assert np.isfinite(P).all()
    for i, sym in enumerate(out["syms"]):                           # month-end price = the 03-30 close
        assert P[i] == pytest.approx(C.price(int(sym[1:]), k30))
    # without the screen the corrupt snapshot is the month-end: no universe, and no month-end price for 39 of 40 coins
    U = m.CmcPanel([rows], screen=False)
    ou = m.crypto_panel(U, None, first="2019-01", last="2019-05")
    assert ou["ELIG"][:, t].sum() == 0 and ou["substituted_month_ends"] == {}


# ------------------------------------------------------------------------------------------------ core: T-400 --

def test_t400_planted_regime_passes_when_point_in_time():
    mv, px = sim_mvrv(True, seed=7)
    j = m.mvrv_regime(mv, px, BILLS, pit=True)
    assert j["n"] >= 4 and not j["park_triggered"]
    assert j["est"] > 0
    assert j["verdict"] == "supported", j["criteria"]


def test_t400_current_vintage_caps_at_inconclusive():
    mv, px = sim_mvrv(True, seed=7)
    j = m.mvrv_regime(mv, px, BILLS, pit=False)
    assert j["verdict"] == "inconclusive"
    assert any("point in time" in c[0] and c[1] is None for c in j["criteria"])


def test_t400_null_fails():
    mv, px = sim_mvrv(False, seed=8)
    j = m.mvrv_regime(mv, px, BILLS, pit=True)
    assert j["verdict"] != "supported"


def test_t400_park_rule_below_four_episodes():
    mv, px = sim_mvrv(True, seed=7, start="2019-01-01")
    j = m.mvrv_regime(mv, px, BILLS, start="2020-01-01", pit=True, variants=False)
    assert j["park_triggered"] and j["verdict"] != "supported"


# ------------------------------------------------------------------------------------------------ core: T-402 --

def test_t402_planted_slope_passes():
    s, p = sim_supply(True, seed=9)
    j = m.stablecoin_predict(s, p)
    assert j["n"] >= 400
    assert j["verdict"] == "supported", j["criteria"]


def test_t402_null_fails():
    s, p = sim_supply(False, seed=10)
    j = m.stablecoin_predict(s, p)
    assert j["verdict"] == "not_supported"


# ------------------------------------------------------------------------------------------------ core: T-403 --

def test_t403_planted_signal_passes():
    h, p = sim_hash(True, seed=11)
    j = m.hash_ribbons(h, p)
    assert j["n"] >= 15
    assert j["verdict"] == "supported", j["criteria"]


def test_t403_null_fails():
    h, p = sim_hash(False, seed=12)
    j = m.hash_ribbons(h, p)
    assert j["verdict"] != "supported"


# ------------------------------------------------------------------------------------------------ core: T-367 --

def _bill(ts):
    return 4.5


def test_t367_no_carry_planted_supported():
    j = m.defi_carry(sim_pools(4.8, seed=13), _bill)
    assert j["n"] >= 900
    assert j["verdict"] == "supported", j["criteria"]


def test_t367_carry_null_fails():
    j = m.defi_carry(sim_pools(8.0, seed=14), _bill)
    assert j["verdict"] == "not_supported"
    assert any(v["venue_carry"] for v in j["venues"].values())


# ------------------------------------------------------------------------------------------------- harnesses --

class FakeArchive:
    def __init__(self, bundles, created="2026-10-16T08:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        b = self.bundles[name]
        return iter(b() if callable(b) else b)


def _yahoo_rows(px: dict, vol=1e6):
    rows = []
    for d, c in sorted(px.items()):
        od = date.fromisoformat(d).toordinal()
        rows.append({"available_at": nxt(d) + "T00:00:00+00:00",
                     "value": {"t": (od - _EPOCH) * 86400, "open": c, "high": c, "low": c, "close": c, "adjclose": c, "volume": vol}})
    return rows


def _fred_rows(days, v=4.5):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": v}} for d in days]


def _cm_rows(asset, series: dict):
    out = []
    days = sorted({d for s in series.values() for d in s})
    for d in days:
        v = {"asset": asset, "day": d}
        for k, s in series.items():
            if d in s:
                v[k] = float(s[d])
        out.append({"available_at": nxt(d) + "T00:00:00+00:00", "value": v})
    return out


def _check(out, allowed=("supported", "not_supported", "inconclusive")):
    stat, n, v, reason = out
    json.dumps(stat)
    assert v in allowed and isinstance(n, int)
    assert " — " in reason
    return stat, n, v, reason


def test_harness_t367_fake_archive():
    pools = sim_pools(4.8, seed=13)
    rows = [{"kind": "chart", "available_at": ts, "value": {"pool": p, "timestamp": ts, "apyBase": a, "tvlUsd": tv}}
            for p, pts in pools.items() for d, (a, tv, ts) in pts.items() if d <= "2026-10-15"]
    A = FakeArchive({m.LLAMA_B: rows, m.DTB3_B: _fred_rows(bdays("2022-01-03"))})
    stat, n, v, reason = _check(m.b6c_cryptoxs_defi_yield_carry(A))
    assert v == "supported" and n >= 900


def test_harness_t402_fake_archive():
    s, p = sim_supply(True, seed=9)
    b = {m.cm_b(a): _cm_rows(a, {"SplyCur": s.get(a, {})}) for a in m.STABLES if a in s}
    for a in m.STABLES:
        b.setdefault(m.cm_b(a), [])
    b[m.BTC_Y] = _yahoo_rows(p)
    stat, n, v, reason = _check(m.b6c_cryptoxs_stablecoin_supply_growth(FakeArchive(b)))
    assert v == "supported"


def test_harness_t403_fake_archive():
    h, p = sim_hash(True, seed=11)
    hr = [{"available_at": nxt(d) + "T00:00:00+00:00", "value": {"day": d, "hash_rate_ths": x}} for d, x in sorted(h["a"].items())]
    b = {m.HASH_B: hr, m.cm_b("btc"): _cm_rows("btc", {"HashRate": h["b"], "PriceUSD": p}),
         m.BTC_Y: _yahoo_rows({d: x for d, x in p.items() if d >= "2014-09-17"})}
    stat, n, v, reason = _check(m.b6c_cryptoxs_hash_ribbons(FakeArchive(b)))
    assert v == "supported" and n >= 15
    # the cost label: 40 bps per switch is an 80 bps round trip; the 10 bps-per-switch end is reported too
    assert "a round trip at 40 bps per switch (80 bps) costs -0.0080" in reason and "10 bps per switch (20 bps) -0.0020" in reason
    assert "a 40 bps round trip" not in reason
    assert stat["round_trip_cost_log_10"] == pytest.approx(2 * math.log(1 - 0.001))
    assert "10-40 bps round trip" not in m.__doc__ and "10-40 bps per switch" in m.__doc__


def test_harness_t400_fake_archive_is_capped_by_vintage():
    mv, px = sim_mvrv(True, seed=7)
    b = {m.cm_b("btc"): _cm_rows("btc", {"CapMVRVCur": mv, "PriceUSD": px}),
         m.BTC_Y: _yahoo_rows({d: x for d, x in px.items() if d >= "2014-09-17"}), m.DTB3_B: _fred_rows(bdays("2009-01-05"), 2.0)}
    stat, n, v, reason = _check(m.b6c_cryptoxs_mvrv_regime(FakeArchive(b)))
    assert v == "inconclusive" and "park rule" in reason
    assert stat["park_rule"].endswith("not triggered")


def test_harness_t314_fake_archive():
    A = FakeArchive({m.CMC_W: cmc_rows(drift=0.04, seed=1)})
    stat, n, v, reason = _check(m.b6c_cryptoxs_xs_momentum_weekly(A))
    assert v == "supported" and n >= 400 and stat["by_formation_weekday"] is None
    assert "long 10 coins" not in reason and "book size mean 10.00 names, min 10, max 10" in reason
    assert "Data limit" not in reason and stat["flagged_snapshots"] == {}


def test_harness_t314_names_the_corrupt_snapshot_as_a_data_limit():
    A = FakeArchive({m.CMC_W: _corrupt_monday(cmc_rows(drift=0.04, seed=1))})
    stat, n, v, reason = _check(m.b6c_cryptoxs_xs_momentum_weekly(A))
    assert "Data limit: the weekly snapshots 2020-11-30" in reason and "entries 2020-11-23, 2020-11-30" in reason
    assert stat["flag_dropped_weeks"] == ["2020-11-23", "2020-11-30"] and "2020-11-30" in stat["flagged_snapshots"]
    assert "0 never seen again" in reason and v == "supported"


def test_harness_t420_fake_archive_without_crypto(monkeypatch):
    syms = tuple(f"E{i}" for i in range(15))
    monkeypatch.setattr(m, "U68", syms)
    rng = np.random.default_rng(15)
    b = {}
    days = bdays("2004-06-01")
    for s in syms:
        px = 50.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(days))))
        b[m.dh(s)] = _yahoo_rows(dict(zip(days, px)), vol=float(rng.uniform(1e5, 1e6)))
    b[m.DTB3_B] = _fred_rows(bdays("2004-01-02"), 2.0)
    stat, n, v, reason = _check(m.b6c_cryptoxs_volume_conditioned_momentum(FakeArchive(b)))
    assert v != "supported" and n == 237 and not stat["have_crypto"]


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, v, reason = m.HARNESSES[name](FakeArchive({}))
    assert v == "inconclusive" and n == 0 and "missing data bundles" in reason
    json.dumps(stat)


def test_maps_are_consistent():
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-314", "T-420", "T-400", "T-402", "T-403", "T-367"}
    assert all(k.startswith("b6c_cryptoxs_") and k == k.lower() for k in m.HARNESSES)
