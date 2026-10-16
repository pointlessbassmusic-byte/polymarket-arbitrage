"""Batch-6c macro harnesses (T-398 Z.1 fund flows, T-458 Michigan sentiment and the size spread, T-479 DAA canary, T-483
2x SPY above SMA200, T-325 leveraged-ETF short pairs, T-467 Canadian interlisted parity) on synthetic data only: for every
core function a planted effect passes and a null does not; the ALFRED point-in-time reader (lag rule, later vintages,
first-release vintages across a rebasing), the Z.1 panel, the HAC and bootstrap pieces, the DAA weights, the SMA rule's
one-bar delay and costs, the short-pair simulator and the fade's two fill readings are checked directly; every harness runs
JSON-safe on a fake archive, and missing bundles give inconclusive. No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pytest

import mandel.experiments.batch6b_bw as bw
from mandel.experiments import batch6c_macro as m

NY = ZoneInfo("America/New_York")


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(bw, "REPS_MAX", 3)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- generators --

def bdays(start, end="2026-10-14"):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def month_add(mo, k):
    y, x = int(mo[:4]), int(mo[5:7]) - 1 + k
    return f"{y + x // 12:04d}-{x % 12 + 1:02d}"


def month_end(mo):
    return (date.fromisoformat(month_add(mo, 1) + "-01") - timedelta(days=1)).isoformat()


def ar1(rng, n, rho):
    x = np.zeros(n)
    x[0] = rng.normal()
    for i in range(1, n):
        x[i] = rho * x[i - 1] + math.sqrt(1 - rho * rho) * rng.normal()
    return x


def alfred_row(day, value, avail, first_release=True, first_vintage=False, lag=None, rs=None):
    return {"available_at": avail, "value": {"day": day, "value": value, "realtime_start": rs or avail[:10], "realtime_end": None,
                                             "first_release": first_release, "first_vintage": first_vintage, "lag_rule_at": lag}}


# --- T-398 ---------------------------------------------------------------------------------------------------

def quarters(a="1952-01-01", b="2026-04-01"):
    out, q = [], a
    while q <= b:
        out.append(q)
        q = m._qadd(q, 1)
    return out


def z1_rows(qs, vals):
    rows = []
    for q, v in zip(qs, vals):
        qe = date.fromisoformat(m._qadd(q, 1)) - timedelta(days=1)
        if q < "2019-01-01":
            lag = (qe + timedelta(days=84)).isoformat() + "T23:59:59+00:00"
            rows.append(alfred_row(q, float(v), "2019-03-07T17:00:00+00:00", True, True, lag if lag < "2019-03-07" else None))
        else:
            rows.append(alfred_row(q, float(v), (qe + timedelta(days=70)).isoformat() + "T16:00:00+00:00"))
    return rows


def z1_world(effect=True, seed=0):
    rng = np.random.default_rng(seed)
    qs = quarters()
    w = 1.0 + 0.5 * ar1(rng, len(qs), 0.85)
    fa = m.Alfred.from_rows(z1_rows(qs, 1e5 * w))
    lm = m.Alfred.from_rows(z1_rows(qs, [1e7] * len(qs)))
    P = m.flow_panel(fa, lm)
    days = bdays("1952-01-02", "2026-08-31")
    ex = rng.normal(0.0002, 0.004, len(days))
    if effect:
        ct = [d + m.CLOSE_UTC for d in days]
        for q in sorted(P["z"]):
            q2 = m._qadd(q, 1)
            if q2 not in P["R"]:
                continue
            f0, f1 = m._fill_index(ct, P["R"][q]), m._fill_index(ct, P["R"][q2])
            if f1 > f0 + 1 and f1 < len(days):
                ex[f0 + 1: f1 + 1] += -0.03 * P["z"][q] / (f1 - f0)
    rf = np.full(len(days), 1e-4)
    return fa, lm, {"days": days, "mkt": ex + rf, "rf": rf}, P


# --- T-458 ---------------------------------------------------------------------------------------------------

def sentiment_world(effect=True, seed=1):
    rng = np.random.default_rng(seed)
    obs = [f"{y:04d}-{mo:02d}" for y in range(1976, 2027) for mo in range(1, 13) if f"{y:04d}-{mo:02d}" <= "2026-09"]
    n = len(obs)
    u = ar1(rng, n, 0.95)
    U = 6.0 + np.cumsum(rng.normal(0, 0.1, n))
    cpi = 100.0 * np.exp(np.cumsum(0.003 + rng.normal(0, 0.002, n)))
    dU = np.array([U[i] - U[i - 12] if i >= 12 else 0.0 for i in range(n)])
    S = 85.0 + 8.0 * u + 3.0 * dU + rng.normal(0, 1.0, n)
    umc, unr, cp = [], [], []
    for i, mo in enumerate(obs):
        day = mo + "-01"
        if mo >= "1978-01":
            if mo < "1998-07":
                lag = (date.fromisoformat(month_end(mo)) + timedelta(days=35)).isoformat() + "T23:59:59+00:00"
                umc.append(alfred_row(day, float(S[i]), "1998-07-31T14:00:00+00:00", True, True, lag))
            else:
                umc.append(alfred_row(day, float(S[i]), mo + "-28T14:00:00+00:00"))
        unr.append(alfred_row(day, float(U[i]), month_add(mo, 1) + "-05T12:30:00+00:00"))
        cp.append(alfred_row(day, float(cpi[i]), month_add(mo, 1) + "-15T12:30:00+00:00"))
    gd = bdays("1976-01-02")
    g = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.008, len(gd))))
    first = {}
    for i, d in enumerate(gd):
        first.setdefault(d[:7], i)
    ui = {mo: i for i, mo in enumerate(obs)}
    spread_lvl = np.zeros(len(gd))
    starts = sorted(first.values())
    lvl = 0.0
    for a, b in zip(starts, starts[1:] + [len(gd)]):
        mo = gd[a][:7]
        prev = month_add(mo, -1)
        s = rng.normal(0, 0.01) + (-0.02 * u[ui[prev]] if (effect and prev in ui) else 0.0)
        for k in range(a, b):
            spread_lvl[k] = lvl + s * (k - a) / max(1, b - a)
        lvl += s
    rut = g * np.exp(spread_lvl)
    ri = [i for i, d in enumerate(gd) if d >= "1987-09-10"]
    hi = [i for i, d in enumerate(gd) if d >= "2011-05-05"]
    dtb3 = {d: 4.0 + math.sin(i / 500.0) for i, d in enumerate(bdays("1975-01-02"))}
    return {"umc": umc, "unr": unr, "cpi": cp, "dtb3": dtb3, "gspc": (gd, g), "rut": ([gd[i] for i in ri], rut[ri]),
            "sphb": ([gd[i] for i in hi], rut[hi] * 0.5), "splv": ([gd[i] for i in hi], g[hi] * 0.4)}


def run_sentiment(w):
    return m.sentiment_test(m.Alfred.from_rows(w["umc"]), m.Alfred.from_rows(w["unr"]), m.Alfred.from_rows(w["cpi"]), w["dtb3"],
                            w["gspc"], w["rut"], w["sphb"], w["splv"])


# --- T-479 ---------------------------------------------------------------------------------------------------

def daa_world(effect=True, seed=2):
    """Planted: in the month before a crash the canaries VWO and BND fall 8% and rebound 8% in the crash month, while the
    other ten risky ETFs (SPY included) fall 8%; cash ETFs earn 0.3% a month. With the VWO+BND canary both are bad before
    a crash (all cash); with SPY+BND at breadth 2 only BND is (half cash). Null: no crashes, no warnings."""
    rng = np.random.default_rng(seed)
    days = bdays("2007-04-11")
    months = sorted({d[:7] for d in days})
    crash = {}
    for i, mo in enumerate(months):
        recent = any(crash.get(months[j]) for j in range(max(0, i - 2), i))
        crash[mo] = bool(effect and not recent and mo > "2007-06" and rng.random() < 0.15)
    pre = {month_add(mo, -1) for mo, c in crash.items() if c}
    idx = {}
    for i, d in enumerate(days):
        idx.setdefault(d[:7], []).append(i)
    lv = {}
    for s in m.T479_ALL:
        x, arr = 100.0, np.empty(len(days))
        for mo in months:
            if s in ("SHY", "IEF", "LQD"):
                r = 0.003 + rng.normal(0, 0.001)
            elif s in ("VWO", "BND") and mo in pre:
                r = -0.08
            elif s in ("VWO", "BND") and crash[mo]:
                r = 0.08
            elif crash[mo]:
                r = -0.08 + rng.normal(0, 0.01)
            elif s == "BND":
                r = 0.003 + rng.normal(0, 0.001)
            else:
                r = 0.02 + rng.normal(0, 0.02)
            ii = idx[mo]
            k = ii[1] if len(ii) > 1 else ii[0]                                  # the month's move lands on its 2nd session
            arr[ii[0]:k] = x
            x *= 1 + r
            arr[k:ii[-1] + 1] = x
        lv[s] = arr
    return {s: (days, lv[s]) for s in m.T479_ALL}


DAA_TEST_FAMILY = (m.T479_PRIMARY, (6, "SPY+BND", 2), (3, "VWO+BND", 2), (3, "SPY+BND", 2))


# --- T-483 ---------------------------------------------------------------------------------------------------

def spy_world(effect=True, seed=3):
    rng = np.random.default_rng(seed)
    days = bdays("1993-01-29")
    n = len(days)
    r = np.empty(n)
    if effect:
        bull, left = True, 300
        for i in range(n):
            if left == 0:
                bull = not bull
                left = int(rng.integers(250, 500)) if bull else int(rng.integers(100, 200))
            r[i] = rng.normal(0.001, 0.006) if bull else rng.normal(-0.004, 0.02)
            left -= 1
    else:
        r = rng.normal(0.0, 0.012, n)
    spy = 100.0 * np.cumprod(1 + r)
    si = [i for i, d in enumerate(days) if d >= "2006-06-21"]
    sso = 50.0 * np.cumprod(1 + 2 * r[si] - 0.009 / 252 - 0.025 / 252)
    return (days, spy), ([days[i] for i in si], sso), m.Bills({"1990-01-02": 2.0})


# --- T-325 ---------------------------------------------------------------------------------------------------

def letf_world(effect=True, seed=4):
    rng = np.random.default_rng(seed)
    out = {}
    for (a, b), L, start in zip(m.T325_PAIRS, (3.0, 2.0, 3.0, 2.0), ("2010-02-11", "2006-07-13", "2009-06-25", "2011-10-04")):
        days = bdays(start)
        n = len(days)
        if effect:
            e = rng.normal(0, 0.02, n)
            r = e - 0.4 * np.r_[0.0, e[:-1]]                                    # mean-reverting daily index returns
            ra = L * r - 0.01 / 252                                             # fund drag (expenses, financing)
            rb = -(L if b != "SVXY" else 1.0) * r - 0.01 / 252
        else:
            ra, rb = rng.normal(0, 0.01, n), rng.normal(0, 0.01, n)
        ra[0] = rb[0] = 0.0
        out[(a, b)] = (days, 50.0 * np.cumprod(1 + ra), 50.0 * np.cumprod(1 + rb))
    qd = bdays("2006-01-03")
    q = 100.0 * np.cumprod(1 + rng.normal(0, 0.015, len(qd)))
    return out, (qd, q)


# --- T-467 ---------------------------------------------------------------------------------------------------

def parity_world(effect=True, seed=5):
    rng = np.random.default_rng(seed)
    days = bdays("2024-01-02", "2026-10-15")
    fxc = 1.35 + np.cumsum(rng.normal(0, 0.002, len(days)))
    fx = {}
    for d, c in zip(days, fxc):
        fx[(d, "15:00")] = (c, c * 1.0005, c * 0.9995, c)
        fx[(d, "14:00")] = (c, c * 1.0005, c * 0.9995, c * (1 + rng.normal(0, 0.0002)))
    legs = {}
    for s in m.CANADA:
        dd = np.zeros(len(days))
        for i in range(1, len(days)):
            dd[i] = (0.6 * dd[i - 1] + rng.normal(0, 0.01)) if effect else rng.normal(0, 0.0002)
        ca_c = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
        us_c = ca_c / fxc * np.exp(dd)
        ub = {(d, "15:30"): (x, x, x, x) for d, x in zip(days, us_c)}
        cb = {(d, "15:30"): (x, x, x, x) for d, x in zip(days, ca_c)}
        legs[s] = (ub, cb)
    return legs, fx


# ======================================================================================== small pieces ==

def test_alfred_lag_rule_later_vintage_and_withdrawal():
    rows = [alfred_row("2010-01-01", 1.0, "2019-03-07T17:00:00+00:00", True, True, "2010-06-24T23:59:59+00:00"),
            alfred_row("2010-01-01", 1.5, "2020-01-10T17:00:00+00:00", False, False),
            alfred_row("2010-01-01", None, "2021-01-10T17:00:00+00:00", False, False)]
    a = m.Alfred.from_rows(rows)
    assert a.at("2010-01-01", "2010-06-01T00:00:00+00:00") is None            # before the lag-rule day
    assert a.at("2010-01-01", "2010-06-25T00:00:00+00:00") == 1.0             # first-vintage value from lag_rule_at
    assert a.at("2010-01-01", "2020-01-10T16:59:59+00:00") == 1.0             # the revision is not yet public
    assert a.at("2010-01-01", "2020-01-10T17:00:00+00:00") == 1.5
    assert a.at("2010-01-01", "2022-01-01T00:00:00+00:00") is None            # withdrawn by a blank period
    assert a.first("2010-01-01") == (1.0, "2010-06-24T23:59:59+00:00")
    # a first-vintage row without a lag rule counts from its own available_at
    b = m.Alfred.from_rows([alfred_row("2018-10-01", 2.0, "2019-03-07T17:00:00+00:00", True, True, None)])
    assert b.first("2018-10-01")[1] == "2019-03-07T17:00:00+00:00"


def test_released_first_release_vintage_survives_rebasing():
    # month 1988-01's first print is on a new base (x 0.5) together with the restated 1987-01; the old 1987-01 print was
    # on the old base. The 12-month change must be taken inside the first-release vintage.
    rows = [alfred_row("1987-01-01", 200.0, "1987-02-20T13:30:00+00:00"),
            alfred_row("1987-01-01", 100.0, "1988-02-20T13:30:00+00:00", False),
            alfred_row("1988-01-01", 104.0, "1988-02-20T13:30:00+00:00")]
    r = m.Released(m.Alfred.from_rows(rows), "log12")
    assert r.val["1988-01"] == pytest.approx(100 * math.log(1.04))
    assert r.latest("1988-02-20T13:29:00+00:00") == (None, None)
    assert r.latest("1988-03-01T20:00:00+00:00")[0] == "1988-01"
    nm = m.Released(m.Alfred.from_rows(rows), "level", "next-month")
    assert nm.R["1988-01"] == "1988-02-01T05:00:00+00:00"


def test_hac_mean_and_ols_hac_known_values():
    rng = np.random.default_rng(0)
    x = rng.normal(0.5, 1.0, 400)
    h = m.hac_mean(x, 4)
    assert h["mean"] == pytest.approx(x.mean())
    assert h["t"] > 5 and h["ci"][0] < 0.5 < h["ci"][1]
    z = rng.normal(size=300)
    y = -0.5 * z + rng.normal(0, 0.5, 300)
    for k in ("bartlett", "rect"):
        o = m.ols_hac(y, z, 3, k)
        assert o["b"] == pytest.approx(-0.5, abs=0.1) and o["t"] < -8
    sb = m.slope_boot(y, z, 8)
    assert sb["t"] < -8 and sb["ci_pct"][1] < 0


def test_ratio_and_sharpe_one_tests():
    rng = np.random.default_rng(1)
    N = rng.integers(0, 3, 500).astype(float)
    S = N * 0.002 + rng.normal(0, 0.001, 500) * N
    t = m.ratio_test(S, N, 5)
    assert t["est"] == pytest.approx(S.sum() / N.sum()) and t["ci"][0] > 0
    t0 = m.ratio_test(N * rng.normal(0, 0.001, 500), N, 5)
    assert t0["ci"][0] < 0 < t0["ci"][1]
    x = rng.normal(0.01, 0.02, 300)
    sh = m.sharpe_one_test(x, 12, 12)
    assert sh["sharpe"] == pytest.approx(m.sharpe_ratio(x, 12)) and sh["est"] == pytest.approx(sh["sharpe"], rel=1e-9)
    assert sh["ci"][0] < sh["sharpe"] < sh["ci"][1] and sh["ci"][0] > 0


def test_one_sided_bounds_come_from_the_same_draws_at_level_090():
    # rule 6 regression (T-467 / T-325): a '95% lower bound' pass is one-sided, the 5% end = the lower end of the two-sided
    # 90% interval from the same resamples; the two-sided 95% CI is still returned under 'ci'
    rng = np.random.default_rng(2)
    x = rng.normal(0.004, 0.02, 240)
    t = m.mean_test(x, 6, one_sided=True)
    exp = [bw._stud(m._mean_stat, [x], 6, m.N_BOOT, m.SEED + k, level=0.90)["ci"] for k in range(m.REPS)]
    assert t["ci1"][0] == pytest.approx(np.mean([e[0] for e in exp])) and t["ci1"][1] == pytest.approx(np.mean([e[1] for e in exp]))
    assert t["ci"][0] < t["ci1"][0] < t["est"] < t["ci1"][1] < t["ci"][1] and len(t["ci1_mc_se"]) == 2
    assert "ci1" not in m.mean_test(x, 6)                                       # two-sided callers (T-483) unchanged
    N = rng.integers(0, 3, 400).astype(float)
    S = N * 0.001 + rng.normal(0, 0.002, 400) * N
    tr = m.ratio_test(S, N, 5, one_sided=True)
    expr = [bw._stud(m._ratio_stat, [S, N], 5, m.N_BOOT, m.SEED + k, level=0.90)["ci"][0] for k in range(m.REPS)]
    assert tr["ci1"][0] == pytest.approx(np.mean(expr)) and tr["ci"][0] < tr["ci1"][0]


def test_lb_crit_judges_the_one_sided_bound():
    # two-sided 95% lower end below 0, one-sided 95% lower bound above 0: the pass's own (one-sided) bound passes
    t = {"est": 6e-5, "ci": [-1e-5, 1.4e-4], "ci1": [2e-6, 1.2e-4], "ci_mc_se": [0.0, 0.0], "ci1_mc_se": [1e-7, 1e-7]}
    assert m._ci_crit(t, "gt", 0.0, "x")[1] is False
    nm, ok, dec = m._lb_crit(t, "x", fmt=lambda v: m._bp(v, 3))
    assert ok is True and not dec and "one-sided 95% lower +0.020 bp" in nm and "two-sided 95% lower -0.100 bp" in nm
    assert m._lb_crit(dict(t, ci1_mc_se=[2e-6, 0.0]), "x")[1] is None          # within 2 Monte Carlo s.e.: unresolved
    assert m._lb_crit({"ci": [-3.0, -1.0], "ci1": [-2.8, -1.2]}, "x")[1:] == (False, True)   # decisive: upper bound < 0


def test_flow_panel_point_in_time_and_quarterly_start():
    qs = quarters("1950-10-01", "2020-01-01")
    vals = [1e5 * (1 + 0.1 * math.sin(i)) for i in range(len(qs))]
    rows_fa = [r for r in z1_rows(qs, vals) if r["value"]["day"] >= "1952-01-01" or r["value"]["day"][5:7] == "10"]
    rows_fa.append(alfred_row("2019-10-01", 9e5, "2020-12-01T16:00:00+00:00", False, False))      # a later revision
    fa = m.Alfred.from_rows(rows_fa)
    lm = m.Alfred.from_rows(z1_rows(qs, [1e7] * len(qs)))
    P = m.flow_panel(fa, lm)
    assert P["q0"] == "1952-01-01"                                             # 1950-51 Q4-only rows are annual
    assert min(P["x"]) == "1952-10-01"                                         # the first 4-quarter sum
    assert P["R"]["2000-01-01"] == "2000-06-23T23:59:59+00:00"                 # lag rule: quarter end + 84 days
    # the 2019Q4 x at its own release uses the first print, not the 2020-12 revision
    qe = date(2019, 12, 31) + timedelta(days=70)
    assert P["R"]["2019-10-01"] == qe.isoformat() + "T16:00:00+00:00"
    exp = sum(vals[qs.index(m._qadd("2019-10-01", -k))] for k in range(4)) / 4 / 1e7
    assert P["x"]["2019-10-01"] == pytest.approx(exp)


def test_daa_weights_cases():
    cols = list(m.T479_ALL)
    sc = {s: 0.1 + 0.01 * i for i, s in enumerate(cols)}
    w = m.daa_weights(sc, 6, ("VWO", "BND"), 2, cols)
    assert w.sum() == pytest.approx(1.0) and (w > 0).sum() == 6
    sc1 = dict(sc, VWO=-0.1)
    w1 = m.daa_weights(sc1, 6, ("VWO", "BND"), 2, cols)
    assert len([s for s in m.T479_RISKY if w1[cols.index(s)] > 0]) == 3       # top 3 risky with one bad canary
    best_cash = max(m.T479_CASH, key=lambda s: sc1[s])
    assert w1[cols.index(best_cash)] >= 0.5 - 1e-12 and w1.sum() == pytest.approx(1.0)
    w2 = m.daa_weights(dict(sc1, BND=-0.2), 6, ("VWO", "BND"), 2, cols)
    assert w2[cols.index(best_cash)] == pytest.approx(1.0)
    assert m.daa_weights(sc1, 6, ("VWO", "BND"), 1, cols)[cols.index(best_cash)] == pytest.approx(1.0)
    P = np.vstack([np.full(3, 100.0 * 1.01 ** k) for k in range(13)])
    assert m.score_13612w(P, 12)[0] == pytest.approx((12 * 0.01 + 4 * (1.01 ** 3 - 1) + 2 * (1.01 ** 6 - 1) + (1.01 ** 12 - 1)) / 4)


def test_sma_rule_delay_costs_and_financing():
    days = bdays("2020-01-01", "2020-03-31")
    adj = np.linspace(100, 110, len(days))
    adj[30:] = adj[30:] - 30.0                                                  # a drop that flips the signal
    sig = m.sma_signal(adj, 5)
    assert np.isnan(sig[3]) and sig[10] == 1.0
    bills = m.Bills({"2019-12-31": 2.0})
    x = m.lev_rule(days, adj, sig, bills, 2.0)
    i = 30                                                                      # sig at close 30 is 0; position from close 31
    assert sig[30] == 0.0 and x["pos"][30] == 1.0 and x["pos"][31] == 0.0      # return index k-1 covers close k-1 -> k
    assert x["switch"][31] and x["rule"][31] == pytest.approx(x["bill"][31] - 2 * 2e-4)
    r = adj[20] / adj[19] - 1
    dt = (date.fromisoformat(days[20]) - date.fromisoformat(days[19])).days
    fin = (1 + x["bill"][19]) * math.exp(0.005 * dt / 365) - 1
    assert x["rule"][19] == pytest.approx(2 * r - fin - 0.009 * dt / 365)


def test_sim_pair_decay_and_stop():
    days = bdays("2020-01-01", "2020-12-31")
    n = len(days)
    rng = np.random.default_rng(3)
    r = rng.normal(0, 0.03, n)
    r[0] = 0
    a, b = 10 * np.cumprod(1 + 3 * r), 10 * np.cumprod(1 - 3 * r)
    C = np.zeros(n)
    s = m.sim_pair(days, a, b, C, "TQQQ", "SQQQ")
    assert len(s["labels"]) == 11 and (s["g0"] == 1.0).all()
    assert s["pnl"].mean() > 0                                                  # both legs decay
    up = 10 * np.cumprod(np.r_[1.0, np.full(n - 1, 1.05)])
    st = m.sim_pair(days, up, 10 * np.ones(n), C, "TQQQ", "SQQQ")
    assert st["stops"] > 0 and any(st["stopped"])
    assert m._req("UVXY", "2018-01-02") == pytest.approx(0.6) and m._req("UVXY", "2018-03-01") == pytest.approx(0.45)
    assert m._req("SVXY", "2018-03-01") == pytest.approx(0.3) and m._req("TQQQ", "2020-01-02") == pytest.approx(0.9)


def test_fade_trades_live_and_lagged():
    d = np.array([0.0] * 20 + [0.01, 0.005, -0.001, 0.0, 0.0, 0.0])
    z = np.array([np.nan] * 20 + [3.0, -0.2, -0.5, 0.0, 0.0, 0.0])               # z crosses 0 at index 21
    live = m.fade_trades(d, z, 2.0, "live")
    assert live[0][:3] == (20, 21, -1.0) and live[0][3] == pytest.approx(-(0.005 - 0.01))
    lag = m.fade_trades(d, z, 2.0, "lagged")
    assert lag[0][:3] == (21, 22, -1.0) and lag[0][3] == pytest.approx(-(-0.001 - 0.005))
    z2 = np.array([np.nan] * 20 + [3.0, 2.5, 2.4, 2.3, 0.1, 0.1])
    assert m.fade_trades(d, z2, 2.0, "live")[0][1] == 22                       # max hold 2 sessions
    assert m.fade_trades(d, z2, 2.0, "lagged")[0][:2] == (21, 23)


def test_parity_series_needs_both_bars_and_live_fx():
    d1, d2, d3 = "2024-03-04", "2024-03-05", "2024-03-06"
    us = {(d1, "15:30"): (1, 1, 1, 74.0), (d2, "15:30"): (1, 1, 1, 74.0), (d3, "15:30"): (1, 1, 1, 74.0)}
    ca = {(d1, "15:30"): (1, 1, 1, 100.0), (d2, "15:30"): (1, 1, 1, 100.0)}
    fx = {(d1, "15:00"): (1.35, 1.36, 1.34, 1.35), (d2, "15:00"): (1.35, 1.35, 1.35, 1.35)}
    p = m.parity_series(us, ca, fx)
    assert p["days"] == [d1] and p["flat_fx"] == 1
    assert p["d"][0] == pytest.approx(math.log(74.0) - math.log(100.0 / 1.35))


# ================================================================================ planted effects and nulls ==

def test_fund_flow_planted_and_null():
    fa, lm, ff, _ = z1_world(True)
    j = m.fund_flow_test(fa, lm, ff)
    assert j["n"] >= 250 and j["reg"]["nw"]["t"] < -2 and j["reg"]["hh"]["t"] < -2 and j["reg"]["bb"]["t"] < -2
    assert all(h["nw"]["b"] < 0 for h in j["halves"].values())
    assert j["verdict"] == "supported", j["why"]
    fa0, lm0, ff0, _ = z1_world(False, seed=7)
    j0 = m.fund_flow_test(fa0, lm0, ff0)
    assert j0["verdict"] != "supported"


def test_sentiment_planted_and_null():
    j = run_sentiment(sentiment_world(True))
    for av in m.T458_AVAIL:
        o = j["by_avail"][av]
        assert o["n"] >= 400 and o["top"]["mean"] < 0 and o["sharpe"]["sharpe"] > 0.3
        assert o["cw"]["continuous"][m.T458_PRIMARY]["r2"] > 0 and o["holm"]["continuous"]["adj"] < 0.05
    assert j["verdict"] == "supported", j["why"]
    j0 = run_sentiment(sentiment_world(False, seed=8))
    assert j0["verdict"] != "supported"


def test_daa_planted_and_null():
    bills = m.Bills({"2007-01-02": 0.0})
    w = daa_world(True)
    # a declared family whose ordering is structural (VWO+BND hedges fully, SPY+BND at breadth 2 by half), so the CSCV
    # ranking is stable under both PBO readings; near-identical configurations make any PBO a coin flip
    j = m.daa_test(w, bills, family=DAA_TEST_FAMILY)
    assert j["n"] >= 200 and j["window"] == ["2008-05", "2026-09"]
    assert j["sharpe"]["ci"][0] > 0 and j["pbo_strategy"]["pbo"] < 0.5 and j["pbo_diff"]["pbo"] < 0.5
    assert j["verdict"] == "supported", j["why"]
    jd = m.daa_test(w, bills)                                                  # the declared 8-configuration matrix
    assert jd["sharpe"]["ci"][0] > 0 and jd["criteria"][0][1] is True
    j0 = m.daa_test(daa_world(False, seed=9), bills)
    assert j0["verdict"] != "supported"


def test_leverage_planted_and_null():
    spy, sso, bills = spy_world(True)
    j = m.leverage_test(spy, bills, sso)
    assert j["n"] >= 8000 and j["mean"]["ci"][0] > 0 and j["sso"]["mean"] > 0
    assert j["verdict"] == "supported", j["why"]
    spy0, sso0, bills0 = spy_world(False, seed=10)
    j0 = m.leverage_test(spy0, bills0, sso0)
    assert j0["verdict"] != "supported"
    j1 = m.leverage_test(spy, bills, None)
    assert j1["verdict"] == "inconclusive"                                      # SSO missing: criterion not implemented


def test_letf_planted_and_null():
    pairs, qqq = letf_world(True)
    bills = m.Bills({"2006-01-02": 1.0})
    j = m.letf_test(pairs, bills, qqq)
    assert j["window"] == ["2010-03", "2026-09"] and j["n"] == 199
    assert j["mean"]["ci"][0] > 0 and j["breakeven"] > 0.03
    assert j["verdict"] == "supported", j["why"]
    p0, q0 = letf_world(False, seed=11)
    j0 = m.letf_test(p0, bills, q0)
    assert j0["verdict"] != "supported"


def test_parity_planted_and_null():
    legs, fx = parity_world(True)
    j = m.parity_test(legs, fx)
    assert j["n"] >= 200
    assert all(t["ci"][0] > 0 for t in j["tests"].values())
    assert j["verdict"] == "supported", j["why"]
    legs0, fx0 = parity_world(False, seed=12)
    j0 = m.parity_test(legs0, fx0)
    assert j0["verdict"] != "supported"


def _canned(ci, ci1):
    return {"est": 0.5 * (ci[0] + ci[1]), "ci": list(ci), "ci1": list(ci1), "ci_mc_se": [0.0, 0.0], "ci1_mc_se": [0.0, 0.0],
            "p": None, "p_lt": None}


def test_parity_criterion_uses_the_one_sided_bound(monkeypatch):
    # T-467 regression: live/per-trade has a two-sided 95% lower end below 0 but a one-sided 95% lower bound above 0 (the
    # reproduced +0.616 bp, -0.090 bp / +0.015 bp case); the other three readings fail decisively. The criterion is then
    # undecided under rules 11/12 (one construction passes, three fail), not failed.
    calls = []

    def fake(S, N, block, n_boot=None, reps=None, seed=0, one_sided=False):
        assert one_sided is True
        calls.append(1)
        return _canned([-0.9e-5, 1.4e-4], [1.5e-6, 1.2e-4]) if len(calls) == 1 else _canned([-8.1e-4, -6.5e-4], [-8e-4, -6.6e-4])

    monkeypatch.setattr(m, "ratio_test", fake)
    legs, fx = parity_world(True)
    j = m.parity_test(legs, fx)
    name, ok = j["criteria"][0]
    assert len(calls) == 4 and ok is None and "undecided under rule 11" in name
    assert name.startswith("one-sided 95% lower bound") and "live/per-trade" in name and "one-sided 95% lower +0.02 bp" in name
    calls.clear()
    monkeypatch.setattr(m, "ratio_test", lambda *a, **k: _canned([-0.9e-5, 1.4e-4], [1.5e-6, 1.2e-4]))
    assert m.parity_test(legs, fx)["criteria"][0][1] is True                   # every reading passes its one-sided bound


def test_letf_criterion_uses_the_one_sided_bound(monkeypatch):
    # T-325 regression: the criterion is the one-sided 95% lower bound, not the 2.5% end of the two-sided CI
    pairs, qqq = letf_world(True)
    bills = m.Bills({"2006-01-02": 1.0})
    seen = {}

    def fake(x, block, n_boot=None, reps=None, seed=0, one_sided=False):
        seen["one_sided"] = one_sided
        return _canned([-1e-4, 6e-3], [2e-4, 5e-3])

    monkeypatch.setattr(m, "mean_test", fake)
    j = m.letf_test(pairs, bills, qqq)
    name, ok = j["criteria"][0]
    assert seen["one_sided"] is True and ok is True
    assert name.startswith("one-sided 95% lower bound") and "one-sided 95% lower +0.020%" in name and "two-sided 95% lower -0.010%" in name


# ===================================================================================== harnesses (fake archive) ==

class FakeArchive:
    def __init__(self, bundles, created="2026-10-16T08:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


_EPOCH = date(1970, 1, 1).toordinal()


def _yahoo(days, px):
    rows = []
    for d, c in zip(days, px):
        od = date.fromisoformat(d).toordinal()
        rows.append({"available_at": date.fromordinal(od + 1).isoformat() + "T14:30:00+00:00",
                     "value": {"t": (od - _EPOCH) * 86400 + 14.5 * 3600, "open": float(c), "high": float(c), "low": float(c),
                               "close": float(c), "adjclose": float(c)}})
    return rows


def _fred(series):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": float(v)}} for d, v in sorted(series.items())]


def _hourly_rows(bars):
    rows = []
    for (d, hm), (o, h, l, c) in sorted(bars.items()):
        y, mo, dd = (int(x) for x in d.split("-"))
        t = datetime(y, mo, dd, int(hm[:2]), int(hm[3:]), tzinfo=NY).timestamp()
        rows.append({"available_at": datetime.fromtimestamp(t + 3600, tz=timezone.utc).isoformat(),
                     "value": {"t": t, "open": o, "high": h, "low": l, "close": c, "volume": 1}})
    return rows


def _ff_rows(ff):
    return [{"available_at": d + "T21:00:00+00:00", "value": {"day": d, "Mkt-RF": float((mk - rf) * 100), "RF": float(rf * 100)}}
            for d, mk, rf in zip(ff["days"], ff["mkt"], ff["rf"])]


def _check(out, verdicts=("supported", "not_supported", "inconclusive")):
    stat, n, v, why = out
    json.dumps(stat)
    assert isinstance(n, int) and v in verdicts and " — " in why
    return stat, n, v, why


def test_harness_fund_flow_fake_archive():
    qs = quarters()
    rng = np.random.default_rng(0)
    w = 1.0 + 0.5 * ar1(rng, len(qs), 0.85)
    _, _, ff, _ = z1_world(False)
    bundles = {m.al(m.FA_SID): z1_rows(qs, 1e5 * w), m.al(m.LM_SID): z1_rows(qs, [1e7] * len(qs)), m.FF3_B: _ff_rows(ff)}
    _check(m.b6c_macro_fund_flow_dumb_money(FakeArchive(bundles)))
    days = bdays("1993-01-29", "2026-08-31")
    bundles[m.dh("SPY")] = _yahoo(days, 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(days))))
    bundles[m.DTB3_B] = _fred({d: 3.0 for d in bdays("1990-01-02")})
    m._CACHE.clear()
    stat, *_ = _check(m.b6c_macro_fund_flow_dumb_money(FakeArchive(bundles)))
    assert stat["spy"] is not None


def test_harness_fund_flow_reason_states_the_quarter_end_lag_rule():
    # T-398 regression: pre-2019 decisions use the fetcher's lag_rule_at = quarter END + 84 days (true release dates
    # unknown), and the reason must say so rather than 'release + 84 days'
    qs = quarters()
    rng = np.random.default_rng(0)
    w = 1.0 + 0.5 * ar1(rng, len(qs), 0.85)
    _, _, ff, _ = z1_world(False)
    bundles = {m.al(m.FA_SID): z1_rows(qs, 1e5 * w), m.al(m.LM_SID): z1_rows(qs, [1e7] * len(qs)), m.FF3_B: _ff_rows(ff)}
    *_, why = _check(m.b6c_macro_fund_flow_dumb_money(FakeArchive(bundles)))
    assert "counted from quarter end + 84 days (the fetcher's lag_rule_at; true pre-2019 release dates unknown)" in why
    assert "release + 84" not in why
    P = m.flow_panel(m.Alfred.from_rows(bundles[m.al(m.FA_SID)]), m.Alfred.from_rows(bundles[m.al(m.LM_SID)]))
    assert P["R"]["1990-01-01"] == (date(1990, 3, 31) + timedelta(days=84)).isoformat() + "T23:59:59+00:00"


def test_harness_sentiment_fake_archive():
    w = sentiment_world(True)
    bundles = {m.al(m.UMC_SID): w["umc"], m.al(m.UNR_SID): w["unr"], m.al(m.CPI_SID): w["cpi"], m.DTB3_B: _fred(w["dtb3"]),
               m.dh("^GSPC"): _yahoo(*w["gspc"]), m.dh("^RUT"): _yahoo(*w["rut"]), m.dh("SPHB"): _yahoo(*w["sphb"]),
               m.dh("SPLV"): _yahoo(*w["splv"])}
    stat, n, v, _ = _check(m.b6c_macro_sentiment_size_premium(FakeArchive(bundles)))
    assert n >= 400 and v == "supported"


def test_harness_daa_fake_archive():
    w = daa_world(True)
    bundles = {m.dh(s): _yahoo(*w[s]) for s in m.T479_ALL}
    bundles[m.DTB3_B] = _fred({d: 0.0 for d in bdays("2007-01-02")})
    _check(m.b6c_macro_daa_canary(FakeArchive(bundles)))


def test_harness_leverage_fake_archive():
    spy, sso, _ = spy_world(True)
    bundles = {m.dh("SPY"): _yahoo(*spy), m.dh("SSO"): _yahoo(*sso), m.DTB3_B: _fred({d: 2.0 for d in bdays("1990-01-02")})}
    _check(m.b6c_macro_leverage_sma200(FakeArchive(bundles)))
    del bundles[m.dh("SSO")]
    m._CACHE.clear()
    _, _, v, why = _check(m.b6c_macro_leverage_sma200(FakeArchive(bundles)))
    assert v != "supported" and "SSO" in why


def test_harness_letf_fake_archive():
    pairs, qqq = letf_world(True)
    bundles = {m.DTB3_B: _fred({d: 1.0 for d in bdays("2006-01-02")}), m.dh("QQQ"): _yahoo(*qqq)}
    for (a, b), (d, pa, pb) in pairs.items():
        bundles[m.dh(a)], bundles[m.dh(b)] = _yahoo(d, pa), _yahoo(d, pb)
    hb = {}
    for i, d in enumerate(bdays("2024-01-02", "2024-06-28")):
        for hm in ("09:30", "14:30", "15:30"):
            x = 50 + math.sin(1.7 * i + 0.3 * int(hm[:2]))
            hb[(d, hm)] = (x, x, x, x)
    bundles[m.hr("TQQQ")] = _hourly_rows(hb)
    stat, n, v, why = _check(m.b6c_macro_letf_pair_decay(FakeArchive(bundles)))
    assert "TQQQ" in stat["late_day"] and "730 sessions" in why
    assert stat["lower_one_sided95"] > stat["ci"][0] and "(one-sided 95% lower bound " in why and "two-sided 95% CI" in why


def test_harness_parity_fake_archive():
    legs, fx = parity_world(True)
    bundles = {m.hr(m.CAD_SYM): _hourly_rows(fx)}
    for s, (ub, cb) in legs.items():
        bundles[m.hr(s)], bundles[m.hr(m.TSX[s])] = _hourly_rows(ub), _hourly_rows(cb)
    assert m.hr(m.TSX["CNI"]) == "hourly-CNR.TO"
    stat, n, v, why = _check(m.b6c_macro_interlisted_parity(FakeArchive(bundles)))
    assert n >= 200 and stat["fx_first"] == "2024-01-02"
    assert all(t["lower_one_sided95"] > t["ci"][0] for t in stat["tests"].values()) and "one-sided 95% lower bound" in why


def test_missing_bundles_inconclusive_and_maps():
    empty = FakeArchive({})
    for name, fn in m.HARNESSES.items():
        stat, n, v, why = fn(empty)
        assert v == "inconclusive" and n == 0 and stat["missing_bundles"] and "missing data bundles" in why
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert all(k.startswith("b6c_macro_") for k in m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-398", "T-458", "T-479", "T-483", "T-325", "T-467"}
