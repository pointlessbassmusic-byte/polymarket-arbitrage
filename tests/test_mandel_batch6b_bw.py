"""Batch-6b buy-write / put-write harnesses on synthetic series only: for every core judge a planted effect passes and a
null does not; the MODEL-PRICED engines, the calibration gate, the bill and calendar conventions are checked directly;
and every harness runs on a fake archive (JSON-safe, labelled, missing bundles -> inconclusive). No archive, no network."""

import json
import math
from datetime import date, datetime
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.data.cboe_strategy import trading_days
from mandel.experiments import batch6b_bw as bw
from mandel.validation.backtest_eval import sharpe_ratio

NB = 300                                # bootstrap resamples in tests


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(bw, "N_BOOT", NB)
    monkeypatch.setattr(bw, "REPS", 2)
    monkeypatch.setattr(bw, "REPS_MAX", 3)
    bw._CACHE.clear()
    yield
    bw._CACHE.clear()


def _labels(n, y=2000, m=1):
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


# ------------------------------------------------------------------------------------------- bills and calendar --

def test_dtb3_conversion_and_prior_print():
    assert bw.dtb3_cont(4.0) == pytest.approx(-math.log(1 - 0.04 * 91 / 360) / (91 / 365))
    b = bw.Bills({"2020-01-02": 4.0, "2020-01-03": 8.0})
    assert b.rate("2020-01-03") == pytest.approx(bw.dtb3_cont(4.0))          # the 01-03 print is not known on 01-03
    assert b.rate("2020-01-04") == pytest.approx(bw.dtb3_cont(8.0))
    c = bw.Bills({"2019-12-30": 4.0})
    assert c.growth("2020-01-01", "2021-01-01") == pytest.approx(math.exp(bw.dtb3_cont(4.0) * 366 / 365))


def test_month_end_days_common_calendar_and_incomplete_final_month():
    days = trading_days("2020-01-02", "2020-03-13")
    a = {d: 100 + i for i, d in enumerate(days)}
    b = {d: 50 + i for i, d in enumerate(days) if d != "2020-01-31"}
    me = bw.month_end_days({"a": a, "b": b})
    assert me == ["2020-01-30", "2020-02-28"]                                  # March incomplete; Jan 31 missing in b
    assert bw.roll_days({"a": a}) == ["2020-01-17", "2020-02-21"]
    P = bw.panel({"a": a}, bw.Bills({"2019-12-30": 0.0}), me)
    assert P["n"] == 1 and P["months"] == ["2020-02"] and P["ret"]["a"][0] == pytest.approx(a["2020-02-28"] / a["2020-01-30"] - 1)


def test_monthly_expiries_third_friday_and_holiday():
    days = trading_days("2025-03-01", "2025-05-31")
    ex = [days[i] for i in bw.monthly_expiries(days)]
    assert ex == ["2025-03-21", "2025-04-17", "2025-05-16"]                   # 2025-04-18 is Good Friday


# -------------------------------------------------------------------------------------------------- statistics --

def test_sharpe_diff_and_cagr_diff_identities():
    rng = np.random.default_rng(1)
    a, b = rng.normal(0.008, 0.03, 240), rng.normal(0.004, 0.04, 240)
    t = bw.sharpe_diff_test(a, b, n_boot=NB)
    assert t["diff"] == pytest.approx(sharpe_ratio(a, 12) - sharpe_ratio(b, 12))
    assert t["ci"][0] < t["diff"] < t["ci"][1] and 0 < t["p"] < 1
    c = bw.cagr_diff_test(a, b, n_boot=NB)
    cg = lambda x: np.prod(1 + x) ** (12 / x.size) - 1
    assert c["diff"] == pytest.approx(cg(a) - cg(b))


def test_alpha_test_recovers_alpha_and_beta():
    rng = np.random.default_rng(2)
    x = rng.normal(0.006, 0.04, 300)
    y = 0.002 + 0.6 * x + rng.normal(0, 0.003, 300)
    t = bw.alpha_test(y, x, n_boot=NB)
    assert t["alpha_ann"] == pytest.approx(0.024, abs=0.005) and t["beta"] == pytest.approx(0.6, abs=0.02)
    assert t["ci"][0] < 0.024 < t["ci"][1] and t["ci"][0] > 0


def test_resolve_against_monte_carlo_error():
    assert bw.resolve(0.01, 0.001, 0.0, "gt")[0] is True
    assert bw.resolve(0.001, 0.001, 0.0, "gt")[0] is None
    assert bw.resolve(-0.01, 0.001, 0.0, "gt")[0] is False
    assert bw.resolve(0.03, 0.002, 0.05, "lt")[0] is True
    t = bw.mc_reps(lambda seed: bw.sharpe_diff_test(np.arange(30.) % 7, np.arange(30.) % 5, n_boot=NB, seed=seed), 3)
    assert t["reps"] == 3 and len(t["ci_mc_se"]) == 2


# ---------------------------------------------------------------------------------------- judges: planted vs null --

def _pair(n, edge, seed=0, noise=0.004):
    rng = np.random.default_rng(seed)
    m = rng.normal(0.004, 0.03, n)
    return 0.7 * m + edge + rng.normal(0, noise, n), 0.7 * m + rng.normal(0, noise, n)


def test_judge_sharpe_planted_supported():
    a, b = _pair(300, 0.004)
    j = bw.judge_sharpe(a, b, _labels(300), 280, ("A", "B"), n_boot=NB)
    assert j["verdict"] == "supported" and j["full"]["ci"][0] > 0


def test_judge_sharpe_null_not_supported():
    a, b = _pair(300, 0.0, seed=3)
    j = bw.judge_sharpe(a, b, _labels(300), 280, ("A", "B"), n_boot=NB)
    assert j["verdict"] == "not_supported"


def test_judge_sharpe_named_split_and_rule5():
    a, b = _pair(171, 0.004, seed=4)
    lab = _labels(171, 2012, 7)
    j = bw.judge_sharpe(a, b, lab, 160, ("A", "B"), split="2020-01", n_boot=NB)
    assert j["part_names"] == ["pre-2020", "2020-"] and j["part_n"] == [90, 81] and j["verdict"] == "supported"
    a0, b0 = _pair(100, 0.0, seed=5)                                        # below min_n, not decisive -> inconclusive
    assert bw.judge_sharpe(a0, b0, _labels(100), 280, n_boot=NB)["verdict"] == "inconclusive"
    a1, b1 = _pair(100, -0.01, seed=6)                                      # decisive failure counts below min_n
    assert bw.judge_sharpe(a1, b1, _labels(100), 280, n_boot=NB)["verdict"] == "not_supported"


def test_judge_alpha_planted_and_null():
    rng = np.random.default_rng(7)
    x = rng.normal(0.006, 0.04, 294)
    y = 0.003 + 0.63 * x + rng.normal(0, 0.004, 294)
    assert bw.judge_alpha(y, x, _labels(294), 280, n_boot=NB)["verdict"] == "supported"
    y0 = 0.63 * x + rng.normal(0, 0.012, 294)
    assert bw.judge_alpha(y0, x, _labels(294), 280, n_boot=NB)["verdict"] == "not_supported"


def test_judge_band_planted_and_null():
    rng = np.random.default_rng(8)
    b = rng.normal(0.005, 0.03, 236)
    a = b + 0.0075 / 12 + rng.normal(0, 0.0008, 236)                        # +0.75 pp/yr, tight
    assert bw.judge_band(a, b, 200, n_boot=NB)["verdict"] == "supported"
    a0 = b + rng.normal(0, 0.0008, 236)                                     # no gap
    assert bw.judge_band(a0, b, 200, n_boot=NB)["verdict"] == "not_supported"
    a3 = b + 0.03 / 12 + rng.normal(0, 0.0008, 236)                         # gap above 1.5 pp
    assert bw.judge_band(a3, b, 200, n_boot=NB)["verdict"] == "not_supported"


def test_judge_gate_and_sharpe_lt_and_gt():
    a, b = _pair(440, -0.004, seed=9)                                       # T-171: constrained worse
    assert bw.judge_gate_and_sharpe(a, b, True, "gate", 400, "lt", n_boot=NB)["verdict"] == "supported"
    assert bw.judge_gate_and_sharpe(a, b, False, "gate", 400, "lt", n_boot=NB)["verdict"] == "not_supported"
    a0, b0 = _pair(440, 0.0, seed=10)
    assert bw.judge_gate_and_sharpe(a0, b0, True, "gate", 400, "lt", n_boot=NB)["verdict"] == "not_supported"
    a2, b2 = _pair(440, 0.004, seed=11)                                     # T-527: spread better in both halves
    j = bw.judge_gate_and_sharpe(a2, b2, True, "gate", 400, "gt", halves=True, n_boot=NB)
    assert j["verdict"] == "supported" and len(j["halves"]) == 2
    assert bw.judge_gate_and_sharpe(a0, b0, True, "gate", 400, "gt", halves=True, n_boot=NB)["verdict"] == "not_supported"


def test_judge_window_share_planted_null_and_rule5():
    rng = np.random.default_rng(12)
    neg = -0.01 + rng.normal(0, 0.02, 440)
    assert bw.judge_window_share(neg, True, "gate", 300)["verdict"] == "supported"
    assert bw.judge_window_share(neg, False, "gate", 300)["verdict"] == "not_supported"
    pos = 0.006 + rng.normal(0, 0.02, 440)
    assert bw.judge_window_share(pos, True, "gate", 300)["verdict"] == "not_supported"
    short = 0.006 + rng.normal(0, 0.02, 169)                                # 50 windows, all positive: decisive
    j = bw.judge_window_share(short, True, "gate", 300)
    assert j["n"] == 50 and j["verdict"] == "not_supported"
    half = np.where(np.arange(169) < 85, 0.03, -0.03)                       # about half negative: not decisive
    assert bw.judge_window_share(half, True, "gate", 300)["verdict"] == "inconclusive"


def test_judge_putwrite_planted_and_null():
    rng = np.random.default_rng(13)
    s = rng.normal(0.0, 0.04, 400)
    p = 0.35 * s + 0.006 + rng.normal(0, 0.004, 400)
    assert bw.judge_putwrite({1.0: (p, s), 0.9: (p - 0.001, s)}, 300, n_boot=NB)["verdict"] == "supported"
    p0 = s + rng.normal(0, 0.004, 400)
    assert bw.judge_putwrite({1.0: (p0, s), 0.9: (p0, s)}, 300, n_boot=NB)["verdict"] == "not_supported"


def test_calibration_gate_planted_and_null():
    rng = np.random.default_rng(14)
    act = rng.normal(0.005, 0.03, 240)
    g = bw.calibration_gate({"BXM": (act + rng.normal(0, 0.001, 240), act)})
    assert g["ok"] and g["indices"]["BXM"]["te"] < 0.01
    g2 = bw.calibration_gate({"BXM": (act + rng.normal(0, 0.01, 240), act), "PUT": (act, act)})
    assert not g2["ok"] and g2["indices"]["BXM"]["te"] > 0.02 and g2["indices"]["PUT"]["ok"]


# ------------------------------------------------------------------------------------------ MODEL-PRICED engines --

def _C(S0, ST, vix=20.0, T=28 / 365, r=0.0, q=0.0, g=1.0, D=0.0, skew=120.0):
    n = len(S0)
    f = lambda v: np.full(n, float(v))
    return {"S0": np.asarray(S0, float), "ST": np.asarray(ST, float), "T": f(T), "r": f(r), "q": f(q), "vix": f(vix),
            "skew": f(skew), "g": f(g), "D": f(D), "n": n, "trf": np.asarray(ST, float) / np.asarray(S0, float)}


def test_put_and_bxm_models_match_their_payoffs():
    C = _C([1000.0, 1000.0], [950.0, 1100.0], g=1.001)
    R = bw.put_model(C)
    P = bw.bs_px(C["S0"], np.array([1000.0, 1000.0]), C["T"], 0.0, 0.0, 0.2, "put")
    assert R == pytest.approx((1 + P / 1000) * 1.001 - np.array([50.0, 0.0]) / 1000 - 1)
    Rb = bw.bxm_model(C)
    c = bw.bs_px(C["S0"], np.array([1000.0, 1000.0]), C["T"], 0.0, 0.0, 0.2, "call")
    assert Rb == pytest.approx((np.array([950.0, 1000.0])) / (1000 - c) - 1)    # capped at K = 1000


def test_covered_put_is_short_call_plus_interest():
    C = _C([1000.0, 1000.0], [900.0, 1080.0], g=1.002, D=1.5)
    r = bw.covered_put_model(C)
    p = bw.bs_px(C["S0"], np.array([1000.0, 1000.0]), C["T"], 0.0, 0.0, 0.2, "put")
    exp = (1000 - np.maximum(C["ST"], 1000) - 1.5 + p * 1.002 + 1000 * 0.002) / 1000
    assert r == pytest.approx(exp)
    assert bw.covered_put_model(C, collateral=True) == pytest.approx(exp + 0.002)


def test_call_spread_wing_adds_upside():
    C = _C([1000.0, 1000.0], [1000.0, 1200.0])
    m = bw.call_spread_model(C, slip=0.0)
    assert m["cs"][1] > m["cc"][1] and m["cs"][0] < m["cc"][0]               # wing pays in the rally, costs otherwise
    assert np.all(m["c2"] < m["c1"])


def test_wheel_assignment_and_basis_floor():
    S0 = [1000.0, 900.0, 905.0, 960.0]
    ST = [900.0, 905.0, 960.0, 1000.0]                                       # assigned in cycle 0, then a slow rebound
    C = _C(S0, ST)
    wc, wu = bw.wheel_model(C, True, slip=0.0), bw.wheel_model(C, False, slip=0.0)
    assert wc["assigned"] == 1 and list(wc["stock"]) == [False, True, True, True]
    k_put = wc["K"][0]
    assert np.all(wc["K"][1:4] >= k_put - wc["premiums"][:4].sum())        # call strikes floored at the cost basis
    assert wu["K"][1] < wc["K"][1]                                          # the 30-delta call sits below the basis
    assert wc["basis_floor_binds"] >= 1


def test_spy_putwrite_planted_premium_beats_spy_and_null_does_not():
    days = trading_days("1993-01-04", "2024-12-31")
    rng = np.random.default_rng(15)
    cal = np.array([date.fromisoformat(d).toordinal() for d in days], float)
    dt = np.diff(cal) / 365.0

    def run(vol, iv, drift):
        lr = (drift - 0.5 * vol ** 2) * dt + vol * np.sqrt(dt) * rng.standard_normal(dt.size)
        c = 100 * np.exp(np.concatenate([[0.0], np.cumsum(lr)]))
        bills = bw.Bills({"1992-12-31": 0.0})
        fr = bw.spy_frame(days, c, c, {d: iv for d in days}, bills)
        C = bw.cycles(fr, bills)
        runs = {}
        for sc in (1.0, 0.9):
            pw = bw.spy_putwrite(C, sc)
            runs[sc] = (pw["R"] - (C["g"] - 1), pw["R_spy"] - (C["g"] - 1))
        return C["n"], bw.judge_putwrite(runs, 300, n_boot=NB)

    n, j = run(0.10, 30.0, 0.0)                                             # rich premium, flat market
    assert n >= 300 and j["verdict"] == "supported"
    _, j0 = run(0.20, 8.0, 0.10)                                            # cheap premium, rising market
    assert j0["verdict"] == "not_supported"


def test_spx_frame_dividends_and_assumed_yield():
    gdays = trading_days("1992-01-02", "1995-12-29")
    g = np.full(len(gdays), 400.0)
    sdays = [d for d in gdays if d >= "1993-01-29"]
    close = np.full(len(sdays), 40.0)
    f = np.ones(len(sdays))
    for i, d in enumerate(sdays):                                           # 0.5% dividend on each quarterly third Friday
        dd = date.fromisoformat(d)
        if i and dd.month in (3, 6, 9, 12) and 15 <= dd.day <= 21 and dd.weekday() == 4:
            f[i:] /= 1 - 0.005
    fr = bw.spx_frame(gdays, g, {d: 20.0 for d in gdays}, None, bw.Bills({"1991-12-31": 3.0}), (sdays, close, close * f))
    i92 = fr.days.index("1992-06-01")
    assert fr.q_assumed[i92] and fr.q[i92] == pytest.approx(bw.PRE_YIELD) and fr.divpts[i92] > 0
    i95 = fr.days.index("1995-06-01")
    assert not fr.q_assumed[i95] and fr.q[i95] == pytest.approx(0.02, rel=0.02)
    y95 = [i for i, d in enumerate(fr.days) if "1995-01-01" <= d <= "1995-12-31"]
    assert sum(fr.divpts[i] for i in y95) / 400 == pytest.approx(0.02, rel=0.05)   # SPY's 2%/yr, accrued over the year
    assert fr.tr[-1] > fr.tr[0]                                              # flat price, positive total return


def _quarterly_lump_frame():
    """Flat ^GSPC at 400, SPY at 40 paying 0.5% on each quarterly third Friday (2%/yr), from 1993-01-29."""
    gdays = trading_days("1992-01-02", "1997-12-31")
    g = np.full(len(gdays), 400.0)
    sdays = [d for d in gdays if d >= "1993-01-29"]
    close = np.full(len(sdays), 40.0)
    f = np.ones(len(sdays))
    for i, d in enumerate(sdays):
        dd = date.fromisoformat(d)
        if i and dd.month in (3, 6, 9, 12) and 15 <= dd.day <= 21 and dd.weekday() == 4:
            f[i:] /= 1 - 0.005
    bills = bw.Bills({"1991-12-31": 3.0})
    return bw.spx_frame(gdays, g, {d: 20.0 for d in gdays}, None, bills, (sdays, close, close * f)), bills


def test_spx_dividends_accrue_daily_not_in_spy_quarterly_lumps():
    # regression (T-527/T-171/T-174 gate): SPY's quarterly ex-date lumps used to land a quarter's dividends (0.5% here)
    # on the Mar/Jun/Sep/Dec expiry session, so one cycle in three carried D and the rest none; BXM accrues daily
    fr, bills = _quarterly_lump_frame()
    dt = np.diff(fr.ords)
    want = fr.close[:-1] * (np.exp(fr.q[:-1] * dt / 365.0) - 1.0)
    assert np.allclose(fr.divpts[1:], want, rtol=1e-12, atol=0)             # every session, at the prior close's q
    assert (fr.divpts[1:] > 0).all() and fr.divpts.max() < 0.001 * 400       # no session carries a quarter's lump
    C = bw.cycles(fr, bills, start="1994-03-01")
    ratio = C["D"] / C["S0"] / C["T"]                                        # dividend yield earned in each cycle
    assert C["n"] >= 40 and (C["D"] > 0).all()
    assert ratio.min() > 0.017 and ratio.max() < 0.027                       # ~2%/yr in every cycle (lumps: 0 or ~6%)
    off = [k for k, d in enumerate(C["day1"]) if int(d[5:7]) not in (3, 6, 9, 12)]
    assert len(off) >= 25 and (C["D"][off] > 0).all()                        # cycles holding no SPY ex-date still earn D


# ---------------------------------------------------------------------------------------------- harness plumbing --

class FakeArchive:
    def __init__(self, bundles, created="2030-01-01T00:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


def _yahoo(days, close, adj, sym):
    return [{"available_at": d + "T21:00:00+00:00",
             "value": {"symbol": sym, "t": datetime.fromisoformat(d + "T14:30:00+00:00").timestamp(), "close": float(c), "adjclose": float(a)}}
            for d, c, a in zip(days, close, adj)]


def _cboe(days, level):
    return [{"available_at": d + "T23:00:00+00:00", "value": {"day": d, "close": float(x), "backtest": False}} for d, x in zip(days, level)]


def _fake_archive(edge_bxmd=0.0, seed=21):
    rng = np.random.default_rng(seed)
    days = trading_days("1988-06-01", "2026-10-14")
    n = len(days)
    m = rng.normal(0.0003, 0.010, n)                                       # market daily log return
    g = 300 * np.exp(np.cumsum(m))
    idx = lambda beta, extra, noise, s: 100 * np.exp(np.cumsum(beta * m + extra / 252 + rng.normal(0, noise, n)))
    b = {"daily-history--GSPC": _yahoo([d for d in days if d >= "1990-01-01"], g[-sum(d >= "1990-01-01" for d in days):],
                                       g[-sum(d >= "1990-01-01" for d in days):], "^GSPC")}
    sd = [d for d in days if d >= "1993-01-29"]
    sc = g[-len(sd):] / 10
    b["daily-history-SPY"] = _yahoo(sd, sc, sc * np.linspace(1.0, 2.0, len(sd)), "SPY")
    b["cboe-VIX-history"] = [{"available_at": d + "T21:30:00+00:00", "value": {"day": d, "close": 18.0 + 4 * math.sin(i / 50)}}
                             for i, d in enumerate(days) if d >= "1990-01-02"]
    b["cboe-SKEW-history"] = [{"available_at": r["available_at"], "value": {"day": r["value"]["day"], "close": 125.0}} for r in b["cboe-VIX-history"]]
    b["fred-DTB3"] = [{"available_at": "1988-01-04T20:00:00+00:00", "value": {"day": "1988-01-04", "value": 2.0}}]
    base = idx(0.6, 0.0, 0.002, 1)
    for sym, start in (("BXM", "2002-03-22"), ("BXY", "1988-06-01"), ("BXMW", "2012-06-29"), ("BXMH", "1990-01-31"),
                       ("BXMC", "1990-01-31"), ("PUT", "2007-01-03"), ("PUTY", "1988-06-01"), ("WPUT", "2006-01-31"),
                       ("PUTD", "2006-01-03"), ("CMBO", "1988-06-01")):
        lv = base * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
        keep = [i for i, d in enumerate(days) if d >= start]
        b[f"cboe-{sym}-history"] = _cboe([days[i] for i in keep], lv[keep])
    bxm = {r["value"]["day"]: r["value"]["close"] for r in b["cboe-BXM-history"]}
    lr = np.diff(np.log([bxm[d] for d in sorted(bxm)]))
    bd = sorted(bxm)
    lv = 100 * np.exp(np.concatenate([[0.0], np.cumsum(lr + edge_bxmd / 252 + rng.normal(0, 0.0005, lr.size))]))
    b["cboe-BXMD-history"] = _cboe(bd, lv)
    return FakeArchive(b)


def test_harnesses_run_on_fake_archive_and_are_json_safe():
    fa = _fake_archive()
    assert set(bw.THEORY_MAP.values()) == set(bw.HARNESSES) and len(bw.THEORY_MAP) == 11
    assert all(h.startswith("b6b_bw_") for h in bw.HARNESSES)
    for tid, h in bw.THEORY_MAP.items():
        stat, n, verdict, reason = bw.HARNESSES[h](fa)
        json.dumps(stat, allow_nan=False)
        assert verdict in ("supported", "not_supported", "inconclusive") and isinstance(n, int) and n > 0, tid
        assert " — " in reason, tid
        if tid in ("T-128", "T-171", "T-174", "T-527"):
            assert "MODEL-PRICED" in reason and stat["label"] == "MODEL-PRICED" and "rule 10(a)" in reason
        else:
            assert "month-end" in reason or "monthly sampling" in reason or "month ends" in reason, tid
    stat, n, verdict, reason = bw.b6b_bw_bxm_alpha(fa)
    assert n == 294 and stat["months"] == ["2002-04", "2026-09"]             # complete months only (Oct 2026 dropped)
    stat, n, _, reason = bw.b6b_bw_bxmw_vs_bxm(fa)
    assert [p["name"] for p in stat["parts"]] == ["pre-2020", "2020-"]


def test_harness_planted_and_null_bxmd_vs_bxm():
    stat, n, verdict, reason = bw.b6b_bw_bxmd_vs_bxm(_fake_archive(edge_bxmd=0.04))
    assert verdict == "supported" and n == 294 and stat["diff"] > 0
    stat, n, verdict, reason = bw.b6b_bw_bxmd_vs_bxm(_fake_archive(edge_bxmd=0.0, seed=24))
    assert verdict != "supported"


def test_missing_bundles_inconclusive():
    fa = _fake_archive()
    del fa.bundles["fred-DTB3"]
    for h in bw.HARNESSES.values():
        stat, n, verdict, reason = h(fa)
        assert verdict == "inconclusive" and n == 0 and "fred-DTB3" in stat["missing_bundles"] and " — " in reason
