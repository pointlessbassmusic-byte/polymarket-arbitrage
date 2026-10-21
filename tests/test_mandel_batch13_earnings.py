"""Synthetic tests for mandel.experiments.batch13_earnings (T-627, T-628, T-629): every signal built at a decision is
unchanged when values AFTER the decision are shocked (CNMS file days after k-5, prices after the month-end close, SEC
shares accepted after the entry open; factor months after the regression row; dividend rows and prices after an
ex-date; returns after a calendar-time month), the book and survivorship helpers do what they claim, and every
harness returns inconclusive (rule 9) on an archive whose get() raises KeyError. No network, no real archive."""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import batch13_earnings as M
from mandel.experiments import batch13_short_b as SB
from mandel.experiments import batch6c_events as EV
from mandel.experiments import batch6c_stockxs as SX


class EmptyArchive:
    """Stub archive: every bundle is missing."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self, kind=None, tag=None):
        return []


def _bdays(start: str, n: int) -> list:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _epoch(day: str, hh: int = 12) -> float:
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hh, tzinfo=timezone.utc).timestamp()


# ================================================================================================= T-627 ==

def _t627_world(S: int = 30, D: int = 320):
    days = _bdays("2018-06-01", D)
    cal = SX.Cal(days)
    rng = np.random.default_rng(3)
    syms = [f"S{k:02d}" for k in range(S)]
    C = rng.uniform(20, 80, (D, S))
    A = np.cumprod(1 + rng.normal(0, 0.01, (D, S)), axis=0)
    pr = {"cal": cal, "days": np.array(days), "C": C, "F": np.ones((D, S)), "real": np.isfinite(C), "Af": A,
          "splits": {}, "col": {s: k for k, s in enumerate(syms)}, "syms": syms}
    Cn = {"days": np.array([EV._ed(d) for d in days], np.int64), "iso": days, "SV": rng.uniform(2e5, 6e5, (D, S)),
          "TV": rng.uniform(5e5, 2e6, (D, S)), "syms": syms, "backfilled": np.zeros(D, bool), "missing_months": []}
    Bc = {"C": Cn, "pj": np.arange(S), "idok": np.ones(S, bool), "ident": {s: "ok" for s in syms}}
    ser = {1000 + k: [(_epoch(days[0]), days[0], 1e8 * (1 + k))] for k in range(S)}
    B = {"pr": pr, "Bc": Bc, "snaps": [(EV._ed("2018-01-01"), frozenset(syms))], "ser": ser,
         "cl": {"cls": {1000 + k: [("m", k)] for k in range(S)}, "XC": np.zeros((D, 0)), "XF": np.ones((D, 0))},
         "ci": np.arange(D), "ysyms": syms, "cik": np.array([1000 + k for k in range(S)], np.int64),
         "sector": np.array(["XLK"] * (S // 2) + ["XLF"] * (S - S // 2), object)}
    return B


def test_t627_window_is_file_days_k64_to_k5():
    rng = np.random.default_rng(5)
    D, S = 200, 20
    SV = rng.uniform(2e5, 6e5, (D, S)); TV = np.full((D, S), 1e6)
    i0 = 150
    sig, cnt = SB.window_svr(SV, TV, i0, M.T627_LO, M.T627_HI, M.T627_MIN_PRESENT)
    assert np.allclose(sig, (SV[i0 - 64:i0 - 4] / TV[i0 - 64:i0 - 4]).mean(axis=0)) and (cnt == 60).all()
    SV2 = SV.copy(); SV2[i0 - 4:] *= 3.0; SV2[:i0 - 64] *= 0.1          # after k-5 and before k-64
    assert np.allclose(sig, SB.window_svr(SV2, TV, i0, M.T627_LO, M.T627_HI, M.T627_MIN_PRESENT)[0])
    SV3 = SV.copy(); SV3[i0 - 5] *= 3.0                                 # k-5 itself is in the window
    assert not np.allclose(sig, SB.window_svr(SV3, TV, i0, M.T627_LO, M.T627_HI, M.T627_MIN_PRESENT)[0])


def test_t627_formation_ignores_everything_after_the_decision():
    B = _t627_world()
    days = B["pr"]["cal"].days
    m = SB.month_ends(days)[5]
    f = M.t627_formation(B, m)
    assert f["e"] == m + 1 and f["x"] == m + 21 and f["U"] == 30 and f["k"] == 6
    i0 = int(np.searchsorted(B["Bc"]["C"]["days"], EV._ed(days[m]), side="right")) - 1
    B2 = copy.deepcopy(B)
    B2["Bc"]["C"]["SV"][i0 - 4:] *= 2.5
    B2["Bc"]["C"]["TV"][i0 - 4:] *= 0.2
    B2["pr"]["C"][m + 1:] *= 3.0
    B2["pr"]["Af"][m + 2:] *= np.linspace(0.5, 2.0, 30)
    for c in B2["ser"]:                       # a cover count accepted after the entry open must not enter
        B2["ser"][c] = B2["ser"][c] + [(float(B["pr"]["cal"].open[m + 1]) + 60.0, days[m + 1], 9e9)]
    f2 = M.t627_formation(B2, m)
    for key in ("fl", "fs", "tl", "ts", "sl", "ss"):
        assert np.allclose(f[key], f2[key]), key
    assert np.allclose(f["cap"], f2["cap"], equal_nan=True)
    assert not np.allclose(f["r"], f2["r"])                          # the outcome moves, the decision does not


def test_t627_quintiles_include_unpriced_members_and_count_their_leg_share():
    B = _t627_world()
    m = SB.month_ends(B["pr"]["cal"].days)[5]
    f = M.t627_formation(B, m)
    j = int(np.flatnonzero(f["fl"] > 0)[0])                           # a long-leg name loses its price
    B3 = copy.deepcopy(B); B3["Bc"]["idok"][j] = False
    f3 = M.t627_formation(B3, m)
    assert np.allclose(f["fl"], f3["fl"]) and np.allclose(f["fs"], f3["fs"])      # the sort is over every member
    assert f3["absent"] == 1 and f3["wl_abs"] == pytest.approx(f["fl"][j] / f["fl"].sum()) and f3["ws_abs"] == 0.0
    c = M.t627_ls(f3)
    assert c["net"] == pytest.approx(c["gross"] - 2 * M.T627_COST_RT - M.T627_BORROW * f3["cdays"] / 365.0)
    assert c["gross"] == pytest.approx(c["RL"] - c["RS"])


def test_t627_class_split_and_price_ratio_rule():
    B = _t627_world()
    B["cl"]["cls"][1000] = [("m", 0), ("m", 1)]
    q = 100
    B["pr"]["C"][q, 0], B["pr"]["C"][q, 1] = 100.0, 150.0
    assert M.class_split(B, 1000, q, 0) == 2
    B["pr"]["C"][q, 1] = 300.0                                       # classes more than 2x apart: no cap
    assert M.class_split(B, 1000, q, 0) is None


def test_t627_survivorship_semantics():
    rng = np.random.default_rng(2)
    x = 0.02 + rng.normal(0, 0.01, 120)
    small = M.t627_survivorship(x, np.full(120, 0.01), True)
    assert small["ok"] is True
    big = M.t627_survivorship(x, np.full(120, 0.6), True)              # 5% x 0.6 = 3% per month: flips the bound
    assert big["ok"] is None and big["tipping_delta"] is not None and big["tipping_delta"] < 0
    assert big["tipping_kind"] == "adverse"
    assert M.t627_survivorship(x, np.full(120, 0.01), None)["ok"] is None
    xf = -0.005 + rng.normal(0, 0.01, 120)                             # failing bound that a favourable shift flips
    f = M.t627_survivorship(xf, np.full(120, 0.6), False)
    assert f["ok"] is False and f["tipping_kind"] == "favourable" and f["tipping_delta"] > 0


def test_t629_both_judges_on_R_only():
    assert M._both(False, True) is False and M._both(None, True) is None
    assert M._both(True, False) is None and M._both(True, True) is True and M._both(False, False) is False


# ================================================================================================= T-628 ==

def _months(n: int, start: str = "2010-01") -> list:
    y, m = int(start[:4]), int(start[5:7])
    out = []
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _fm(n: int, seed: int = 1, alpha: float = 0.0) -> dict:
    rng = np.random.default_rng(seed)
    fm = {c: rng.normal(0, 0.04, n) for c in ("Mkt-RF", "HML", "RMW", "CMA", "UMD", "RF")}
    fm["SMB"] = alpha + 0.2 * fm["Mkt-RF"] - 0.4 * fm["RMW"] + rng.normal(0, 0.01, n)
    return fm


def test_t628_design_uses_only_the_month_and_its_previous_month():
    ms = _months(60)
    fm = _fm(60)
    d, y, X = M.t628_design(ms, fm, "2011-01", "2013-12")
    assert d[0] == "2011-01" and d[-1] == "2013-12" and len(d) == 36
    i = ms.index("2012-05")
    k = d.index("2012-05")
    assert X[k, 0] == fm["Mkt-RF"][i] and X[k, 1] == fm["Mkt-RF"][i - 1] and y[k] == fm["SMB"][i]
    fm2 = copy.deepcopy(fm)
    for c in fm2:
        fm2[c][ms.index("2014-01"):] *= 5.0                          # months after the sample end
    _d2, y2, X2 = M.t628_design(ms, fm2, "2011-01", "2013-12")
    assert np.allclose(y, y2) and np.allclose(X, X2)
    gap = ms[:20] + ms[21:]                                          # a month whose previous month is missing is skipped
    fmg = {c: np.delete(v, 20) for c, v in fm.items()}
    dg, _yg, _Xg = M.t628_design(gap, fmg, "2010-01", "2014-12")
    assert ms[21] not in dg and ms[22] in dg


def test_t628_bootstrap_intercept_direction():
    ms = _months(160)
    pos = _fm(160, 3, alpha=0.01)
    _d, y, X = M.t628_design(ms, pos, ms[1], ms[-1])
    pg, pl, ci = M.boot_intercept(y, X, 12, 6, 300, 0)
    assert pg < 0.02 and pl > 0.9 and ci[0] > 0
    neg = _fm(160, 3, alpha=-0.01)
    _d, y, X = M.t628_design(ms, neg, ms[1], ms[-1])
    pg, pl, ci = M.boot_intercept(y, X, 12, 6, 300, 0)
    assert pl < 0.02 and ci[1] < 0


def test_t628_hedge_book_is_point_in_time_and_charges_resets():
    days = _bdays("2020-01-01", 80)
    rng = np.random.default_rng(4)
    rets = {k: rng.normal(0, 0.01, 80) for k in ("IJR", "QUAL", "SPY")}
    w = {"IJR": 1.0, "QUAL": 0.4, "SPY": -1.4}
    p = M.hedge_book(days, rets, w, 5e-4, 0.003)
    i = 30
    r2 = {k: v.copy() for k, v in rets.items()}
    for v in r2.values():
        v[i + 1:] *= 4.0
    p2 = M.hedge_book(days, r2, w, 5e-4, 0.003)
    assert np.allclose(p[:i + 1], p2[:i + 1]) and not np.allclose(p[i + 1:], p2[i + 1:])
    zero = {k: np.zeros(80) for k in rets}
    pz = M.hedge_book(days, zero, w, 5e-4, 0.0)
    starts = [k for k in range(80) if k == 0 or days[k][:7] != days[k - 1][:7]]
    assert np.allclose(pz[starts], -5e-4) and np.allclose(np.delete(pz, starts), 0.0)


# ================================================================================================= T-629 ==

def test_t629_split_day_dividend_is_a_reclassification():
    rows = [{"kind": "dividend", "value": {"ex_date": "2007-11-27", "amount": 33.03}},
            {"kind": "split", "value": {"ex_date": "2007-11-27", "numerator": 6996.0, "denominator": 10000.0}},
            {"kind": "dividend", "value": {"ex_date": "2011-05-18", "amount": 0.79}},
            {"kind": "dividend", "value": {"ex_date": "2011-05-18", "amount": 0.01}},
            {"kind": "dividend", "value": {"ex_date": "2012-02-22", "amount": 0.0}}]
    divs, rc = M.cash_dividends(rows)
    assert rc == [("2007-11-27", 33.03)]
    assert divs == [(EV._ed("2011-05-18"), pytest.approx(0.80))]


def _t629_world():
    days = _bdays("2001-01-01", 3200)
    D = len(days)
    eds = np.array([EV._ed(d) for d in days], np.int64)
    rng = np.random.default_rng(6)
    A = np.cumprod(1 + rng.normal(0.0003, 0.015, (D, 2)), axis=0)
    spy = np.cumprod(1 + rng.normal(0.0003, 0.01, D))
    init = "2008-06-02"
    later = [EV._ed(d) for d in ("2008-09-02", "2008-12-01", "2009-03-02")]
    B = {"series": ["S1", "S2"], "col": {"S1": 0, "S2": 1},
         "spells": {"S1": [(EV._ed("1996-01-01"), EV._ed("2030-01-01"))], "S2": [(EV._ed("1996-01-01"), EV._ed("2030-01-01"))]},
         "first": {"S1": EV._ed(days[0]), "S2": EV._ed(days[0])}, "A": A.copy(), "Af": A.copy(),
         "traded": np.ones((D, 2), bool), "last": np.array([D - 1, D - 1]), "spy": spy, "days": days, "eds": eds,
         "divs": {"S1": [(EV._ed("2003-03-03"), 0.1), (EV._ed(init), 0.2)] + [(e, 0.2) for e in later],
                  "S2": [(EV._ed(d), 0.3) for d in ("2005-03-01", "2005-06-01", "2005-09-01")]},
         "cik": {"S1": 11, "S2": 22}}
    return B, init


def test_t629_detection_rules_and_point_in_time():
    B, init = _t629_world()
    ev, _cnt = M.detect_events(B, "2005-01-01", "2010-12-31")
    assert [v["day"] for v in ev if v["sym"] == "S1"] == [init]
    # rows and prices after the ex-date do not move the event
    B2 = copy.deepcopy(B)
    B2["divs"]["S1"] = B2["divs"]["S1"] + [(EV._ed("2009-06-01"), 5.0)]
    e = ev[0]["e"]
    B2["A"][e + 1:, 0] *= 3.0; B2["Af"][e + 1:, 0] *= 3.0
    ev2, _ = M.detect_events(B2, "2005-01-01", "2010-12-31")
    assert [(v["sym"], v["day"]) for v in ev2] == [(v["sym"], v["day"]) for v in ev]
    # a dividend inside the 730 days before removes it; so do short history and non-membership
    B3 = copy.deepcopy(B)
    B3["divs"]["S1"] = sorted(B3["divs"]["S1"] + [(EV._ed(init) - 400, 0.1)])
    assert not [v for v in M.detect_events(B3, "2005-01-01", "2010-12-31")[0] if v["sym"] == "S1" and v["day"] == init]
    B4 = copy.deepcopy(B); B4["first"]["S1"] = EV._ed(init) - 700
    assert not [v for v in M.detect_events(B4, "2005-01-01", "2010-12-31")[0] if v["sym"] == "S1"]
    B5 = copy.deepcopy(B); B5["spells"]["S1"] = [(EV._ed("1996-01-01"), EV._ed(init))]
    assert not [v for v in M.detect_events(B5, "2005-01-01", "2010-12-31")[0] if v["sym"] == "S1"]
    # reading M: an excluded row is treated as absent
    B6 = copy.deepcopy(B)
    ev6, _ = M.detect_events(B6, "2005-01-01", "2010-12-31", excl={("S1", init)})
    assert [v["day"] for v in ev6 if v["sym"] == "S1"] == ["2008-09-02"]       # the next row becomes the initiation


def test_t629_bhar_and_spy_after_the_last_bar():
    B, _init = _t629_world()
    Af, spy = B["Af"][:, 0], B["spy"]
    e = 1000
    r = M.bhar(Af, spy, len(spy) - 1, e)
    assert r == pytest.approx(Af[e + 252] / Af[e] - spy[e + 252] / spy[e])
    Af2 = Af.copy(); Af2[e + 253:] *= 7.0                            # after the exit
    assert M.bhar(Af2, spy, len(spy) - 1, e) == pytest.approx(r)
    last = e + 100                                                   # the series ends inside the window
    rl = M.bhar(Af, spy, last, e)
    assert rl == pytest.approx(Af[last] / Af[e] * spy[e + 252] / spy[last] - spy[e + 252] / spy[e])
    assert M.bhar(Af, spy, len(spy) - 1, len(spy) - 100) is None


def test_t629_merge_share_classes():
    evs = [{"sym": "GOOG", "ed": 100, "cik": 7, "e": 1}, {"sym": "GOOGL", "ed": 101, "cik": 7, "e": 1},
           {"sym": "X", "ed": 100, "cik": 8, "e": 1}, {"sym": "GOOGL", "ed": 300, "cik": 7, "e": 5}]
    out = M.merge_classes(evs)
    assert sorted(len(v["classes"]) for v in out) == [1, 1, 2]


def test_t629_calendar_time_month_ignores_later_returns():
    B, _init = _t629_world()
    ev, _ = M.detect_events(B, "2005-01-01", "2010-12-31")
    evs = M.merge_classes(ev)
    ms = sorted({d[:7] for d in B["days"]})
    rng = np.random.default_rng(9)
    fm = {c: rng.normal(0, 0.03, len(ms)) for c in ("Mkt-RF", "SMB", "HML", "RMW", "CMA", "UMD")}
    fm["RF"] = np.full(len(ms), 0.001)
    ct = M.calendar_time(B, evs, ms, fm)
    assert ct["months"] >= 6
    B2 = copy.deepcopy(B)
    cut = B["days"].index("2009-01-02")
    B2["Af"][cut:, 0] *= np.linspace(1.0, 2.0, len(B["days"]) - cut)
    ct2 = M.calendar_time(B2, evs, ms, fm)
    s1, s2 = ct["series"], ct2["series"]
    assert s1["months"] == s2["months"]
    before = [k for k, m in enumerate(s1["months"]) if m < "2009-01"]
    after = [k for k, m in enumerate(s1["months"]) if m >= "2009-01"]
    assert before and after
    assert np.allclose([s1["excess"][k] for k in before], [s2["excess"][k] for k in before])
    assert not np.allclose([s1["excess"][k] for k in after], [s2["excess"][k] for k in after])


def test_t629_resolve_series_follows_renames_before_the_rename_date():
    own = {"NEW": "NEW"}
    succ = {"OLD": [(EV._ed("2015-01-01"), "NEW")]}
    assert M.resolve_series("OLD", EV._ed("2012-01-01"), own, succ) == "NEW"
    assert M.resolve_series("OLD", EV._ed("2016-01-01"), own, succ) is None
    assert M.resolve_series("NEW", EV._ed("2012-01-01"), own, succ) == "NEW"


def test_t629_survivorship_uses_the_extreme_included_value():
    rng = np.random.default_rng(1)
    x = 0.08 + rng.normal(0, 0.1, 80)                                # positive mean, negative tail
    assert x.min() < 0
    g = np.array([f"2010-{(k % 12) + 1:02d}" if k < 40 else f"2015-{(k % 12) + 1:02d}" for k in range(80)])
    s = M.t629_survivorship(x, g, True, 4)
    assert s["worst"] == pytest.approx(x.min()) and s["ok"] is True
    s2 = M.t629_survivorship(x, g, True, 400)                        # many unseen events at the worst value flip it
    assert s2["ok"] is None


# ================================================================================================= contract ==

@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_harness_inconclusive_when_bundles_missing(name):
    stat, n, verdict, reason = M.HARNESSES[name](EmptyArchive())
    assert verdict == "inconclusive" and n == 0
    assert "missing" in reason
    assert stat.get("missing_bundles")


def test_theory_map_names_harnesses():
    assert set(M.THEORY_MAP) == {"T-627", "T-628", "T-629"}
    for tid, h in M.THEORY_MAP.items():
        assert h in M.HARNESSES and M.HARNESSES[h].__doc__.strip().rstrip(".") == tid
