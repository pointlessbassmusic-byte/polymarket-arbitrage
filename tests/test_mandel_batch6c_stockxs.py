"""Batch-6c single-stock cross-sectional harnesses (T-375 FINRA days-to-cover deciles against the lender's fee, T-393
top-1000 days-to-cover long-short, T-451 Piotroski F-score within value, T-473 Avellaneda-Lee sector-ETF s-score) on
synthetic data only: for every core function a planted effect passes and a null does not; the split-adjusted raw
prices and market caps, point-in-time shares, tie-sharing deciles, name identity checks (reused tickers), the F-score
signals and the filing's own accession, the Newey-West and stationary-bootstrap tools, the Avellaneda-Lee OU fit and
its next-close execution (no look-ahead) are checked directly; every harness runs JSON-safe on a fake archive, missing
bundles and unpriced universes give inconclusive. No archive, no network."""

import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import numpy as np
import pytest

import mandel.experiments.batch6b_bw as bw
from mandel.data.public_history import finra_si_available
from mandel.experiments import batch6c_stockxs as m

UTC = timezone.utc
CAP = "2026-10-15T23:00:00+00:00"


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(bw, "REPS_MAX", 3)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- generators --

def bdays(start, end):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def ser(sym, days, adj, close=None, vol=None, splits=(), typ="EQUITY", name=None):
    adj = np.asarray(adj, float)
    close = adj if close is None else np.asarray(close, float)
    return {"sym": sym, "days": list(days), "close": close, "adj": adj,
            "vol": np.full(len(days), 1e6) if vol is None else np.asarray(vol, float),
            "F": np.array([m.split_factor(list(splits), d) for d in days]), "splits": list(splits),
            "meta": {"instrumentType": typ, "longName": name or f"{sym} Industries Inc."}}


def paths(R, start=100.0):
    return start * np.cumprod(1.0 + R, axis=0)


class FakeArchive:
    def __init__(self):
        self.b = {}

    def add(self, name, rows, recipe="", created_at=CAP):
        self.b[name] = SimpleNamespace(name=name, rows=list(rows), recipe=recipe, created_at=created_at)

    def get(self, name):
        return self.b[name]

    def load(self, name):
        yield from self.b[name].rows

    def entries(self, kind=None, tag=None):
        return list(self.b.values())


def _t(day, hh=14, mm=30):
    y, mo, d = map(int, day.split("-"))
    return datetime(y, mo, d, hh, mm, tzinfo=UTC).timestamp()


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def add_stock(fa, sym, days, adj, close=None, vol=None, typ="EQUITY", name=None, splits=()):
    close = adj if close is None else close
    rows = []
    for k, d in enumerate(days):
        t = _t(d)
        rows.append({"source": "yahoo", "kind": "price", "key": sym, "observed_at": _iso(t), "available_at": _iso(t + 86400),
                     "value": {"symbol": sym, "t": t, "open": float(close[k]), "high": float(close[k]), "low": float(close[k]),
                               "close": float(close[k]), "volume": float(1e6 if vol is None else vol[k]),
                               "adjclose": float(adj[k])}})
    meta = json.dumps({"currency": "USD", "instrumentType": typ, "longName": name or f"{sym} Industries Inc."})
    fa.add(m.dh(sym), rows, recipe=f"yahoo /v8/finance/chart/{sym}; meta {meta}. Yahoo terms")
    ev = []
    for ex, ratio in splits:
        t = _t(ex)
        ev.append({"kind": "split", "available_at": _iso(t), "value": {"type": "split", "t": t, "ex_date": ex,
                                                                       "numerator": ratio, "denominator": 1.0}})
    fa.add(m.de(sym), ev)


def add_daily_value(fa, name, days, vals, field="value", hh=20):
    fa.add(name, [{"available_at": _iso(_t(d, hh, 0)), "value": {"day": d, field: float(v)}} for d, v in zip(days, vals)])


def add_ff5(fa, days, rng):
    rows = []
    for d in days:
        v = {"day": d, **{c: float(rng.normal(0, 0.5)) for c in m.FF5_COLS}, "RF": 0.01}
        rows.append({"available_at": _iso(_t(d, 21, 0)), "value": v})
    fa.add(m.FF5_B, rows)


# ================================================================================================= helpers ==

def test_names_match_rejects_reused_tickers_and_keeps_renames():
    assert m.names_match("Physicians Realty Trust", "Healthpeak Properties, Inc.") is False
    assert m.names_match("American Airlines Group Inc. C", "American Airlines Group Inc.") is True
    assert m.names_match("American Express Company", "American Airlines Group Inc.") is False     # generic first word
    assert m.names_match("BERKSHIRE HATHAWAY Class B", "Berkshire Hathaway Inc.") is True
    assert m.names_match("Advanced Accelerator Applicati", "Advanced Accelerator Applications S.A.") is True
    assert m.names_match("Compuware", "Ocean Thermal Energy Corporation") is False
    assert m.names_match("", "Apple Inc.") is None
    assert m.names_match("VF Corporation", "V.F. Corporation") is True                   # dotted initials
    assert m.names_match("J.B. Hunt", "J.B. Hunt Transport Services, Inc.") is True
    assert m.names_ok("Cliffs Natural Resources", ["Cleveland-Cliffs Inc.", "CLIFFS NATURAL RESOURCES INC."]) is True
    assert m.names_ok("El Paso Corporation", ["Empire Petroleum Corporation"]) is False


def test_split_factor_raw_price_and_market_cap():
    days = bdays("2020-03-02", "2020-08-31")
    adj = np.full(len(days), 50.0)                                 # Yahoo's split-adjusted close: 50 throughout
    s = ser("XYZ", days, adj, splits=[("2020-06-01", 2.0)])        # 2:1 split: raw 100 before, 50 after
    cal = m.Cal(days)
    P = m.Panel(cal, [s])
    i_pre, i_post = cal.pos["2020-05-01"], cal.pos["2020-07-01"]
    assert P.RAW[i_pre, 0] == pytest.approx(100.0) and P.RAW[i_post, 0] == pytest.approx(50.0)
    # 10 shares reported as of 2020-03-31 (pre-split basis), 20 as of 2020-06-30 (post-split): market cap 1,000 both
    assert P.mcap(0, i_pre, 10.0, "2020-03-31") == pytest.approx(1000.0)
    assert P.mcap(0, i_post, 20.0, "2020-06-30") == pytest.approx(1000.0)
    # the pre-split cover count used after the split is still converted correctly
    assert P.mcap(0, i_post, 10.0, "2020-03-31") == pytest.approx(1000.0)


def test_shares_series_sums_classes_and_goes_stale():
    facts = [("dei", "EntityCommonStockSharesOutstanding", "shares", None, "2020-01-15", 70.0, "a1", "10-K", _t("2020-02-01")),
             ("dei", "EntityCommonStockSharesOutstanding", "shares", None, "2020-01-15", 30.0, "a1", "10-K", _t("2020-02-01")),
             ("us-gaap", "CommonStockSharesOutstanding", "shares", None, "2020-03-31", 90.0, "a2", "10-Q", _t("2020-05-01"))]
    s = m.shares_series(facts)
    assert [x[2] for x in s] == [100.0, 90.0]
    assert m.shares_at(s, _t("2020-03-01"), "2020-03-01") == (100.0, "2020-01-15")
    assert m.shares_at(s, _t("2020-01-01"), "2020-01-01") is None                   # nothing known yet
    assert m.shares_at(s, _t("2022-01-01"), "2022-01-01") is None                   # stale (> 15 months)


def test_tail_fractions_share_tied_boundary_slots():
    sc = np.array([1.0, 1.0, 1.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    el = np.ones(10, bool)
    lo = m.tail_fractions(sc, el, 2, high=False)
    assert lo.sum() == pytest.approx(2.0) and np.allclose(lo[:4], 0.5) and np.allclose(lo[4:], 0.0)
    hi = m.tail_fractions(sc, el, 2, high=True)
    assert np.allclose(hi[-2:], 1.0) and hi.sum() == pytest.approx(2.0)
    assert m.tail_fractions(sc, np.zeros(10, bool), 1, True).sum() == 0.0


def test_nw_mean_and_ols_nw_planted_and_null():
    rng = np.random.default_rng(1)
    x = rng.normal(0.01, 0.02, 300)
    assert m.nw_mean(x, 4)["p"] < 0.01
    assert m.nw_mean(rng.normal(0.0, 0.02, 300) - 0.004, 4)["p"] > 0.5
    F = rng.normal(0, 0.03, (300, 5))
    y = 0.004 + F @ np.array([1.0, 0.2, -0.3, 0.0, 0.1]) + rng.normal(0, 0.005, 300)
    r = m.ols_nw(y, F, 6)
    assert r["alpha"] == pytest.approx(0.004, abs=0.0015) and r["t"] > 4
    r0 = m.ols_nw(y - 0.004, F, 6)
    assert abs(r0["t"]) < 3


def test_stationary_bootstrap_sharpe_planted_and_null():
    rng = np.random.default_rng(2)
    idx = m._stat_idx(rng, 50, 10.0, 4)
    assert idx.shape == (4, 50) and idx.min() >= 0 and idx.max() < 50
    good = rng.normal(0.001, 0.01, 2500)
    sb = m.sharpe_boot(good, 20.0, 400, 0)
    assert sb["est"] > 1.0 and sb["ci"][0] > 0
    null = rng.normal(0.0, 0.01, 2500)
    sb0 = m.sharpe_boot(null, 20.0, 400, 0)
    assert sb0["ci"][0] < 0 < sb0["ci"][1]


def test_win_valid():
    X = np.ones((6, 2))
    X[2, 1] = np.nan
    v = m._win_valid(X, 3)
    assert v[:, 0].tolist() == [False, False, True, True, True, True]
    assert v[:, 1].tolist() == [False, False, False, False, False, True]


# ================================================================================ T-375 / T-393 worlds ==

def dtc_world(start, planted, drift=-0.0015, N=100, seed=0, step=10, end="2026-10-14", dtc_scale=0.1):
    """N names with a persistent DTC rank (name i: 1 + i x dtc_scale); planted: the top-decile names drift by
    ``drift`` a day. Formations every ``step`` sessions from ``start``."""
    rng = np.random.default_rng(seed)
    days = bdays("2017-11-01", end)
    D = len(days)
    R = rng.normal(0.0002, 0.01, (D, N))
    top = np.arange(N) >= int(N * 0.9)
    if planted:
        R[:, top] += drift
    A = paths(R)
    cal = m.Cal(days)
    P = m.Panel(cal, [ser(f"S{i:03d}", days, A[:, i]) for i in range(N)])
    forms = []
    e = cal.on_or_after(start)
    while e < D - 30:
        dtc = 1.0 + np.arange(N) * dtc_scale + rng.normal(0, 0.01, N)
        forms.append({"label": days[e], "e": e, "q": e - 1, "cols": np.arange(N), "dtc": dtc,
                      "chg": rng.normal(0, 10, N), "price": np.full(N, 50.0), "adv_usd": np.full(N, 1e8),
                      "mcap": rng.uniform(1e9, 1e11, N)})
        e += step
    for k, f in enumerate(forms):
        f["e_next"] = forms[k + 1]["e"] if k + 1 < len(forms) else None
    return P, forms


def _t375(P, forms, covered=True):
    core = m.t375_periods(P, forms)
    fam = {"dtc_1m": core, "dtc_to_next": m.t375_periods(P, forms, hold="next"), "chg_1m": m.t375_periods(P, forms, sort="chg")}
    n = len(core["label"])
    rows, tests = m.t375_judge(core, fam, covered, "x% unpriced", n)
    return bw._decide(rows, n, m.T375_MIN_N, "formation dates"), core, tests, rows


def test_t375_planted_underperformance_is_supported():
    P, forms = dtc_world("2020-05-04", planted=True)
    forms = [f for f in forms if f["label"] <= "2026-09-30"]
    (v, why), core, tests, _ = _t375(P, forms)
    assert len(core["label"]) >= m.T375_MIN_N
    assert tests["ew"]["nw"]["est"] > 0.005 and tests["vw"]["nw"]["est"] > 0.005
    assert tests["years"]["ew"]["positive"] == 7
    assert v == "supported", why


def test_t375_null_is_not_supported_and_costs_count():
    P, forms = dtc_world("2020-05-04", planted=False)
    forms = [f for f in forms if f["label"] <= "2026-09-30"]
    (v, why), core, tests, _ = _t375(P, forms)
    assert v == "not_supported", why
    # net = gross - 4 x 10 bp per cohort; x = net - 0.83%
    assert np.allclose(core["net_ew"], core["gross_ew"] - 0.004)
    assert np.allclose(core["x_ew"], core["net_ew"] - 0.0083)


def test_t375_uncovered_universe_is_not_judged():
    P, forms = dtc_world("2020-05-04", planted=True)
    (v, why), _, _, rows = _t375(P, forms, covered=False)
    assert v == "inconclusive" and all(r[1] is None for r in rows) and "NOT JUDGED" in rows[0][0]


def test_t375_month_hold_drops_holds_past_the_data():
    P, forms = dtc_world("2026-08-03", planted=False, end="2026-10-14", step=5)
    core = m.t375_periods(P, forms)
    assert all(d <= "2026-09-14" for d in core["label"])           # a one-month hold must end by 2026-10-14


def _t393(P, forms, covered=True, rng=None):
    rng = rng or np.random.default_rng(5)
    book = m.t393_book(P, forms)
    F = rng.normal(0, 0.01, (len(book["label"]), 5))
    n = len(book["label"])
    rows, tests = m.t393_judge(book, F, covered, "unpriced", n)
    return bw._decide(rows, n, m.T393_MIN_N, "release dates"), book, tests


def test_t393_planted_low_dtc_outperformance_is_supported():
    P, forms = dtc_world("2018-01-11", planted=True, drift=-0.002, dtc_scale=0.08)
    (v, why), book, tests = _t393(P, forms)
    assert len(book["label"]) >= m.T393_MIN_N and tests["mean"]["est"] > 0.005
    assert v == "supported", why


def test_t393_null_after_costs_is_not_supported():
    P, forms = dtc_world("2018-01-11", planted=False, dtc_scale=0.08)
    (v, why), book, tests = _t393(P, forms)
    assert v == "not_supported", why
    assert np.all(book["borrow"] > 0) and np.all(book["cost"] > 0)


def test_t393_universe_is_top_n_by_cap_and_dtc_cap():
    P, forms = dtc_world("2018-01-11", planted=False, N=60, dtc_scale=0.3)       # DTC 1 .. 18.7
    f = dict(forms[0])
    f["mcap"] = np.arange(60, 0, -1) * 1e9                                         # name 0 largest
    f["dtc"] = 1.0 + np.arange(60) * 0.3
    b = m.t393_book(P, [f, forms[1]], top_n=40)
    # top 40 by cap = names 0..39 (DTC 1..12.7); DTC <= 10 keeps names 0..30 -> 31 names, deciles of 3
    assert int(b["n"][0]) == 31 and int(b["k"][0]) == 3


# ======================================================================================= T-451 F-score ==

GOOD_CUR = dict(ni=12.0, cfo=20.0, assets=110.0, ltd=10.0, ca=60.0, cl=30.0, rev=200.0, gp=90.0, iss=False)
GOOD_PREV = dict(ni=8.0, cfo=10.0, assets=100.0, ltd=12.0, ca=50.0, cl=30.0, rev=170.0, gp=70.0)
BAD_CUR = dict(ni=-5.0, cfo=-10.0, assets=100.0, ltd=30.0, ca=40.0, cl=40.0, rev=150.0, gp=40.0, iss=True)
BAD_PREV = dict(ni=5.0, cfo=8.0, assets=100.0, ltd=10.0, ca=60.0, cl=30.0, rev=170.0, gp=70.0)


def test_fscore_nine_signals_and_missing_data():
    g = m.fscore(GOOD_CUR, GOOD_PREV, 95.0)
    assert g["score"] == 9 and all(g["signals"].values())
    b = m.fscore(BAD_CUR, BAD_PREV, 100.0)
    assert b["score"] == 0
    assert m.fscore({**GOOD_CUR, "cl": 0.0}, GOOD_PREV, 95.0) is None             # no current ratio (a bank)
    assert m.fscore(GOOD_CUR, GOOD_PREV, None) is None                             # no t-2 assets


def tenk(accn, av, E, E1, cur, prev, form="10-K", shares=None):
    rows = []

    def dur(tag, end, val):
        start = (date.fromisoformat(end) - timedelta(days=364)).isoformat()
        rows.append(("us-gaap", tag, "USD", start, end, float(val), accn, form, av))

    def inst(tag, end, val):
        rows.append(("us-gaap", tag, "USD", None, end, float(val), accn, form, av))

    for d, end in ((cur, E), (prev, E1)):
        dur("NetIncomeLoss", end, d["ni"])
        dur("NetCashProvidedByUsedInOperatingActivities", end, d["cfo"])
        dur("Revenues", end, d["rev"])
        dur("GrossProfit", end, d["gp"])
        for tag, k in (("Assets", "assets"), ("AssetsCurrent", "ca"), ("LiabilitiesCurrent", "cl"),
                       ("LongTermDebtNoncurrent", "ltd")):
            inst(tag, end, d[k])
        inst("StockholdersEquity", end, d.get("eq", 50.0))
    if cur.get("iss"):
        dur("ProceedsFromIssuanceOfCommonStock", E, 5.0)
    if shares:
        rows.append(("dei", "EntityCommonStockSharesOutstanding", "shares", None, shares[1], float(shares[0]), accn, form, av))
    return rows


def test_tenk_events_use_the_filings_own_accession_and_earlier_t2_assets():
    f = []
    f += tenk("a2011", _t("2012-02-20"), "2011-12-31", "2010-12-31", {**GOOD_PREV, "assets": 100.0}, {**GOOD_PREV, "assets": 95.0})
    f += tenk("a2012", _t("2013-02-20"), "2012-12-31", "2011-12-31", GOOD_CUR, GOOD_PREV, shares=(10.0, "2013-02-01"))
    # a later amendment restates 2011 net income downwards: the 2012 10-K's F-score must not see it
    f += [("us-gaap", "NetIncomeLoss", "USD", "2011-01-01", "2011-12-31", -50.0, "a2012A", "10-K/A", _t("2013-09-01"))]
    ev = {e["accn"]: e for e in m.tenk_events(f)}
    assert ev["a2012"]["fscore"]["score"] == 9
    assert ev["a2012"]["book"] == pytest.approx(50.0) and ev["a2012"]["shares"] == 10.0
    assert ev["a2011"]["fscore"] is None                                           # no earlier filing with 2009 assets
    assert "a2012A" not in ev                                                      # amendments are not entry events


def ls_world(planted, seed=3, N=40):
    rng = np.random.default_rng(seed)
    days = bdays("2010-06-01", "2026-10-14")
    D = len(days)
    R = rng.normal(0.0002, 0.01, (D, N))
    if planted:
        R[:, :N // 2] += 0.0008
        R[:, N // 2:] -= 0.0008
    A = paths(R)
    cal = m.Cal(days)
    P = m.Panel(cal, [ser(f"S{i:03d}", days, A[:, i]) for i in range(N)])
    pos = []
    for j in range(N):
        leg = 1 if j < N // 2 else -1
        e = cal.on_or_after("2010-07-01") + 3 * (j % (N // 2))
        while e < D - 1:
            x = min(cal.on_or_before(m._add_months(days[e], 12)), D - 1)
            pos.append((j, e, x, leg))
            e = x + 5                                     # a gap: each new 10-K is a fresh entry (costs are paid)
    return P, pos


def _t451(P, pos, rng=None):
    rng = rng or np.random.default_rng(7)
    months = m._months(m.T451_START, m.T451_END)
    runs = {c: m.calendar_ls(P, pos, months, c) for c in m.T451_COSTS}
    Fm = {c: rng.normal(0, 0.03, (len(runs[c]["months"]), 5)) for c in m.T451_COSTS}
    n = len(runs[m.T451_COSTS[0]]["months"])
    rows, tests = m.t451_judge(runs, Fm, True, "", n)
    return bw._decide(rows, n, m.T451_MIN_N, "months"), runs, tests


def test_t451_planted_calendar_time_spread_is_supported():
    P, pos = ls_world(True)
    (v, why), runs, tests = _t451(P, pos)
    r = runs[m.T451_COSTS[0]]
    assert len(r["months"]) == 189 and r["ls"].mean() > 0.02
    # the higher cost end earns less
    assert runs[m.T451_COSTS[1]]["ls"].mean() < r["ls"].mean()
    assert v == "supported", why


def test_t451_null_is_not_supported():
    P, pos = ls_world(False)
    (v, why), runs, tests = _t451(P, pos)
    assert v == "not_supported", why


def test_calendar_ls_continuing_firm_pays_no_round_trip():
    days = bdays("2015-01-01", "2016-12-31")
    cal = m.Cal(days)
    P = m.Panel(cal, [ser("A", days, np.full(len(days), 10.0)), ser("B", days, np.full(len(days), 10.0))])
    e1, x1 = cal.on_or_after("2015-02-02"), cal.on_or_after("2015-08-03")
    x2 = cal.on_or_after("2016-02-01")
    pos = [(0, e1, x1, 1), (0, x1, x2, 1), (1, e1, x2, -1)]
    r = m.calendar_ls(P, pos, m._months("2015-03", "2015-12"), 0.001)
    # flat prices: only costs; the long leg pays entry (Feb, outside) and exit (2016) -> zero in Mar-Dec 2015
    assert np.allclose(r["long"], 0.0) and np.allclose(r["short"], 0.0)


def test_t451_positions_value_quintile_and_legs():
    days = bdays("2014-01-01", "2016-12-31")
    cal = m.Cal(days)
    N = 10
    P = m.Panel(cal, [ser(f"S{i}", days, np.full(len(days), 20.0)) for i in range(N)])
    colmap = {1000 + i: i for i in range(N)}
    av = _t("2015-03-10", 20)
    events, shares = {}, {}
    for i in range(N):
        book = 100.0 if i in (0, 1, 2) else 10.0                                   # firms 0-2: high B/M
        sc = {0: 9, 1: 1, 2: 5}.get(i, 9)
        events[1000 + i] = [{"av": _t("2014-03-10", 20), "fscore": {"score": 5}, "book": book},
                            {"av": av, "fscore": {"score": sc}, "book": book}]
        shares[1000 + i] = [(_t("2014-02-01"), "2014-01-31", 10.0)] + [(_t("2015-02-01"), "2015-01-31", 10.0)]
    pos, info, bps = m.t451_positions(P, events, colmap, shares)
    legs = {(j, leg) for j, e, x, leg in pos if days[e] >= "2015-03-01"}
    assert (0, 1) in legs and (1, -1) in legs
    assert not any(j == 2 for j, _ in legs) and not any(j >= 3 for j, _ in legs)


# ================================================================================= T-473 Avellaneda-Lee ==

def al_world(planted, D=650, N=40, seed=11, t0=150):
    rng = np.random.default_rng(seed)
    S = 2
    E = rng.normal(0.0003, 0.01, (D, S))
    sec = np.arange(N) % S
    beta = rng.uniform(0.6, 1.4, N)
    if planted:
        X = np.zeros((D, N))
        for t in range(1, D):
            X[t] = 0.7 * X[t - 1] + rng.normal(0, 0.012, N)
        eps = np.diff(X, axis=0, prepend=np.zeros((1, N)))
    else:
        eps = rng.normal(0, 0.012, (D, N))
    R = beta * E[:, sec] + eps
    R[0] = np.nan
    E[0] = np.nan
    vix = np.zeros(D, bool)
    vix[::2] = True
    return {"R": R, "RP": np.nan_to_num(R), "E": E, "EP": np.nan_to_num(E), "member": np.ones((D, N), bool),
            "etf_p": sec, "etf_f": sec, "V": np.full((D, N), 1e6), "vix_ok": vix, "rf": np.full(D, 0.0001),
            "hd": np.ones(D), "t0": t0, "t1": D - 1}


AL_KW = dict(win=60, pca_win=120, n_pc=2)


def test_ou_scores_fast_reversion_passes_kappa():
    rng = np.random.default_rng(0)
    X = np.zeros((60, 200))
    for t in range(1, 60):
        X[t] = 0.6 * X[t - 1] + rng.normal(0, 0.01, 200)
    ou = m.ou_scores(np.diff(X, axis=0, prepend=np.zeros((1, 200))))
    assert ou["ok"].mean() > 0.95 and ou["kappa_ok"].mean() > 0.9
    beta, eps = m.etf_resid(2.0 * X[:, :3] + 0.001, X[:, :3])
    assert np.allclose(beta, 2.0) and np.allclose(eps, 0.0, atol=1e-12)


def test_al_backtest_planted_mean_reversion_vs_null():
    res = m.al_backtest(al_world(True), **AL_KW)
    x = res["etf"]["net"]
    sb = m.sharpe_boot(x, 20.0, 400, 0)
    assert sb["ci"][0] > 0, sb
    assert res["etf"]["n_open"].mean() > 2 and res["etf"]["cost"].sum() > 0 and res["etf"]["borrow"].sum() > 0
    assert m.sharpe_boot(res["pca15"]["net"], 20.0, 400, 0)["est"] > 0
    res0 = m.al_backtest(al_world(False), **AL_KW)
    sb0 = m.sharpe_boot(res0["etf"]["net"], 20.0, 400, 0)
    assert sb0["ci"][0] <= 0, sb0


def test_al_backtest_no_lookahead_and_gross_cap():
    inp = al_world(True, D=400)
    res = m.al_backtest(inp, **AL_KW)
    T = 300
    inp2 = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in inp.items()}
    rng = np.random.default_rng(99)
    for k in ("R", "RP"):
        inp2[k][T + 1:] = rng.normal(0, 0.05, inp2[k][T + 1:].shape)
    for k in ("E", "EP"):
        inp2[k][T + 1:] = rng.normal(0, 0.05, inp2[k][T + 1:].shape)
    res2 = m.al_backtest(inp2, **AL_KW)
    k = T - inp["t0"]
    for v in m.T473_VARIANTS:
        nm = v["name"]
        # returns through day T may not depend on anything after day T (signals at T-1 execute at close T)
        assert np.allclose(res[nm]["net"][:k + 1], res2[nm]["net"][:k + 1]), nm
    # the stock legs never exceed 2x: with 40 names at 2% each the cap does not bind, and gross stays bounded
    assert res["etf"]["gross_exposure"].max() < 2.0 * 2.5


def test_al_backtest_vix_gate_blocks_entries():
    inp = al_world(True)
    inp["vix_ok"] = np.zeros_like(inp["vix_ok"])
    res = m.al_backtest(inp, variants=[v for v in m.T473_VARIANTS if v["name"] == "etf_vix"], **AL_KW)
    assert res["etf_vix"]["n_open"].max() == 0 and np.allclose(res["etf_vix"]["net"], 0.0)


def _family(primary_mean, n=2100, seed=4):
    rng = np.random.default_rng(seed)
    base = rng.normal(primary_mean, 0.01, n)
    fam = {"etf": base}
    for k, nm in enumerate(["pca15", "etf_volume", "etf_1.0/0.25/0.25", "etf_vix"]):
        fam[nm] = base - 0.0004 * (k + 1) + rng.normal(0, 0.001, n)
    return fam


def test_t473_judge_planted_supported_null_not():
    fam = _family(0.0012)
    rows, tests = m.t473_judge({"drift": fam, "target": _family(0.0013, seed=5)}, "etf", 2100)
    v, why = bw._decide(rows, 2100, m.T473_MIN_N, "trading days")
    assert v == "supported", why
    assert tests["drift"]["pbo"]["pbo"] < 0.5 and tests["drift"]["dsr"]["dsr"] > 0.95
    rows0, _ = m.t473_judge({"drift": _family(0.0), "target": _family(0.0, seed=5)}, "etf", 2100)
    v0, why0 = bw._decide(rows0, 2100, m.T473_MIN_N, "trading days")
    assert v0 == "not_supported", why0


def test_t473_judge_accountings_must_agree():
    rows, _ = m.t473_judge({"drift": _family(-0.0006), "target": _family(0.0012, seed=5)}, "etf", 2100)
    v, why = bw._decide(rows, 2100, m.T473_MIN_N, "trading days")
    assert rows[0][1] is None and "disagree" in rows[0][0]
    assert v != "supported"


def test_al_backtest_target_accounting_charges_no_drift():
    res = m.al_backtest(al_world(True), **AL_KW)
    r = res["etf"]
    assert r["cost_target"].sum() < r["cost"].sum()
    assert np.allclose(r["net"] + r["cost"], r["net_target"] + r["cost_target"])


def test_sector_maps():
    assert m.gics_etf("Real Estate") == ("XLRE", "XLF")
    assert m.gics_etf("Communication Services", "Interactive Media & Services") == ("XLC", "XLK")
    assert m.gics_etf("Communication Services", "Movies & Entertainment") == ("XLC", "XLY")
    assert m.sic_etf(2834) == ("XLV", "XLV") and m.sic_etf(1311) == ("XLE", "XLE") and m.sic_etf(6022) == ("XLF", "XLF")
    assert m.sic_etf(4813) == ("XLC", "XLK") and m.sic_etf(4841) == ("XLC", "XLY") and m.sic_etf("9999") is None


# =============================================================================== harnesses (fake archive) ==

def _json_ok(out):
    stat, n, v, reason = out
    json.dumps(stat)
    assert isinstance(n, int) and v in ("supported", "not_supported", "inconclusive") and isinstance(reason, str)
    assert " — " in reason
    return stat, n, v, reason


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, v, reason = _json_ok(m.HARNESSES[name](FakeArchive()))
    assert v == "inconclusive" and "missing" in reason
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)


def finra_fake(monkeypatch, unpriced=0, N=30, seed=0):
    """A fake archive for T-375/T-393 over 2024 with N priced FINRA stocks (+ ``unpriced`` names without prices)."""
    monkeypatch.setattr(m, "T375_START", "2024-01-01")
    monkeypatch.setattr(m, "T375_END", "2024-12-31")
    monkeypatch.setattr(m, "T393_START", "2024-01-01")
    monkeypatch.setattr(m, "T393_END", "2024-12-31")
    monkeypatch.setattr(m, "FINRA_ALL", ("2024-01-01", "2024-12-31"))
    monkeypatch.setattr(m, "T375_MIN_N", 5)
    monkeypatch.setattr(m, "T393_MIN_N", 5)
    rng = np.random.default_rng(seed)
    fa = FakeArchive()
    days = bdays("2023-06-01", "2025-06-30")
    add_stock(fa, "SPY", days, paths(rng.normal(0, 0.01, len(days))), typ="ETF", name="SPDR S&P 500 ETF Trust")
    R = rng.normal(0.0002, 0.01, (len(days), N))
    A = paths(R)
    tick, facts = [], []
    for i in range(N):
        sym = "".join(chr(65 + int(c)) for c in f"{i:03d}")             # AAA, AAB, ...
        add_stock(fa, sym, days, A[:, i], name=f"{sym} Industries Inc.")
        tick.append({"available_at": CAP, "value": {"cik": 100 + i, "name": f"{sym} INDUSTRIES INC", "ticker": sym,
                                                    "exchange": "NYSE"}})
        for q in ("2023-06-30", "2023-12-31", "2024-06-30", "2024-12-31"):
            av = _iso(_t(q) + 30 * 86400)
            facts.append({"kind": "fact", "available_at": av, "value": {
                "cik": 100 + i, "taxonomy": "dei", "tag": "EntityCommonStockSharesOutstanding", "unit": "shares", "start": None,
                "end": q, "val": float(1e7 * (i + 1)), "accn": f"{i}-{q}", "fy": 2024, "fp": "Q", "form": "10-Q",
                "filed": q, "frame": None}})
    fa.add(m.SEC_TICK_B, tick)
    fa.add(m.FACTS_PREFIX + "b000", facts)
    add_ff5(fa, days, rng)
    for d in m.finra_expected("2023-11-01", "2024-12-31"):
        rows = []
        for i in range(N + unpriced):
            sym = "".join(chr(65 + int(c)) for c in f"{i:03d}")
            name = f"{sym} Industries Inc." if i < N else f"Gone{i} Corp"
            sym = sym if i < N else f"ZZ{i}"
            rows.append({"kind": "short-interest", "available_at": finra_si_available(d), "value": {
                "symbolCode": sym, "issueName": name, "marketClassCode": "NYSE",
                "currentShortPositionQuantity": float(rng.uniform(1e5, 5e6)), "averageDailyVolumeQuantity": 1e6,
                "changePercent": float(rng.normal(0, 10)), "settlementDate": d}})
        fa.add(m.finra_name(d), rows)
    return fa


def test_t375_harness_fake_archive_unpriced_names_make_it_inconclusive(monkeypatch):
    fa = finra_fake(monkeypatch, unpriced=3)
    stat, n, v, reason = _json_ok(m.b6c_stockxs_lending_dtc_deciles(fa))
    assert v == "inconclusive" and "NOT JUDGED" in reason and n >= 15
    assert stat["coverage"]["missing_share_mean"] == pytest.approx(3 / 33)
    assert stat["covered"] is False


def test_t375_harness_fake_archive_fully_priced_is_judged(monkeypatch):
    fa = finra_fake(monkeypatch, unpriced=0)
    stat, n, v, reason = _json_ok(m.b6c_stockxs_lending_dtc_deciles(fa))
    assert stat["covered"] is True and "NOT JUDGED" not in " ".join(c[0] for c in stat["criteria"])
    assert v == "not_supported"                                    # random DTC cannot beat the 0.83% fee + costs


def test_t393_harness_fake_archive(monkeypatch):
    fa = finra_fake(monkeypatch, unpriced=2)
    stat, n, v, reason = _json_ok(m.b6c_stockxs_short_interest_dtc(fa))
    assert v == "inconclusive" and "NOT JUDGED" in reason and n >= 15
    fa2 = finra_fake(monkeypatch, unpriced=0)
    m._CACHE.clear()
    stat2, n2, v2, _ = _json_ok(m.b6c_stockxs_short_interest_dtc(fa2))
    assert stat2["covered"] is True and v2 in ("not_supported", "inconclusive", "supported")


def test_finra_reused_ticker_is_unpriced(monkeypatch):
    fa = finra_fake(monkeypatch, unpriced=0, N=12)
    d = m.finra_expected("2024-01-01", "2024-12-31")[3]
    rows = fa.b[m.finra_name(d)].rows
    rows[0]["value"]["issueName"] = "Totally Different Holdings"       # AAA is now another company in FINRA's file
    panel = m._equity_panel(fa)
    forms, cover = m.finra_formations(fa, panel, [d])
    assert cover[0]["why"]["name"] == 1 and cover[0]["priced"] == 11


def _fake_tenk_rows(cik, year, good, shares_val):
    E, E1 = f"{year}-12-31", f"{year - 1}-12-31"
    av = _iso(_t(f"{year + 1}-02-20", 15))
    cur, prev = (GOOD_CUR, GOOD_PREV) if good else (BAD_CUR, BAD_PREV)
    out = []
    for tax, tag, unit, start, end, val, accn, form, _ in tenk(f"{cik}-{year}", 0, E, E1, cur, prev,
                                                                shares=(shares_val, f"{year + 1}-01-31")):
        out.append({"kind": "fact", "available_at": av, "value": {"cik": cik, "taxonomy": tax, "tag": tag, "unit": unit,
                                                                  "start": start, "end": end, "val": val, "accn": accn,
                                                                  "fy": year, "fp": "FY", "form": form, "filed": av[:10],
                                                                  "frame": None}})
    return out


def test_t451_harness_fake_archive(monkeypatch):
    monkeypatch.setattr(m, "T451_START", "2013-01")
    monkeypatch.setattr(m, "T451_END", "2016-12")
    monkeypatch.setattr(m, "T451_MIN_N", 5)
    rng = np.random.default_rng(3)
    fa = FakeArchive()
    days = bdays("2011-01-03", "2017-06-30")
    add_stock(fa, "SPY", days, paths(rng.normal(0, 0.01, len(days))), typ="ETF")
    tick, facts = [], []
    N = 12
    A = paths(rng.normal(0.0002, 0.01, (len(days), N)))
    for i in range(N):
        sym = f"F{chr(65 + i)}"
        add_stock(fa, sym, days, A[:, i])
        tick.append({"available_at": CAP, "value": {"cik": 200 + i, "name": f"{sym} INDUSTRIES", "ticker": sym, "exchange": "NYSE"}})
        for y in range(2011, 2017):
            facts += _fake_tenk_rows(200 + i, y, good=(i % 2 == 0), shares_val=1.0 if i < 4 else 1e3)
    facts += _fake_tenk_rows(999, 2014, good=True, shares_val=5.0)                  # a 10-K filer without a price
    fa.add(m.SEC_TICK_B, tick)
    fa.add(m.FACTS_PREFIX + "b000", facts)
    add_ff5(fa, days, rng)
    stat, n, v, reason = _json_ok(m.b6c_stockxs_piotroski_value(fa))
    assert stat["events"]["fscored"] > 0 and stat["events"]["long"] > 0 and stat["events"]["short"] > 0
    assert stat["missing_share"] > 0 and v == "inconclusive" and "NOT JUDGED" in reason


def test_t473_harness_fake_archive(monkeypatch):
    monkeypatch.setattr(m, "T473_START", "2021-01-01")
    monkeypatch.setattr(m, "T473_PCA_WIN", 80)
    monkeypatch.setattr(m, "T473_NPC", 2)
    monkeypatch.setattr(m, "T473_MIN_N", 100)
    monkeypatch.setattr(m, "T473_PBO_PARTS", 4)
    rng = np.random.default_rng(8)
    fa = FakeArchive()
    days = bdays("2020-06-01", "2022-06-30")
    D = len(days)
    add_stock(fa, "SPY", days, paths(rng.normal(0, 0.01, D)), typ="ETF")
    E = {}
    for s in m.SECTOR_ETFS[:9]:
        E[s] = rng.normal(0.0003, 0.01, D)
        add_stock(fa, s, days, paths(E[s]), typ="ETF", name=f"{s} Select Sector SPDR")
    N = 24
    tickers = [f"T{chr(65 + i)}" for i in range(N)]
    wiki = []
    X = np.zeros((D, N))
    for t in range(1, D):
        X[t] = 0.7 * X[t - 1] + rng.normal(0, 0.012, N)
    eps = np.diff(X, axis=0, prepend=np.zeros((1, N)))
    secs = ["Information Technology", "Financials"]
    for i, tk in enumerate(tickers):
        etf = "XLK" if i % 2 == 0 else "XLF"
        r = 1.0 * E[etf] + eps[:, i]
        add_stock(fa, tk, days, paths(r), name=f"{tk} Industries Inc.")
        if i < N - 2:
            wiki.append({"available_at": CAP, "value": {"symbol": tk, "security": f"{tk} Industries",
                                                        "gics_sector": secs[i % 2], "gics_sub_industry": "x"}})
    # three problem members: an ETF under a reused ticker, a removed member whose ticker now names another company,
    # and a member without any series
    add_stock(fa, "OLDE", days, paths(rng.normal(0, 0.01, D)), typ="ETF", name="Some Buffer ETF")
    add_stock(fa, "REUS", days, paths(rng.normal(0, 0.01, D)), name="Ocean Thermal Energy Corporation")
    members = tickers + ["OLDE", "REUS", "GONE"]
    fa.add(m.FJA_B, [{"available_at": _iso(_t("2020-06-01", 13)), "value": {"date": "2020-06-01", "tickers": members}}])
    fa.add(m.WIKI_B, wiki)
    fa.add(m.WIKI_CH_B, [{"available_at": CAP, "value": {"effective_date": "2019-01-02", "removed_ticker": "REUS",
                                                         "removed_security": "Compuware", "added_ticker": None}}])
    add_daily_value(fa, m.DTB3_B, days, np.full(D, 1.5))
    add_daily_value(fa, m.VIX_B, days, 15 + 5 * rng.random(D), field="close", hh=21)
    stat, n, v, reason = _json_ok(m.b6c_stockxs_avellaneda_lee(fa))
    u = stat["universe"]
    assert stat["not_equity"] == ["OLDE"] and stat["name_mismatch"] == ["REUS"] and u["no_series"] == 1
    # TW and TX (the last two) have no Wikipedia sector and no SEC SIC: they drop out
    assert set(stat["no_sector"]) == {tickers[-1], tickers[-2]} and u["used"] == N - 2
    assert n == len([d for d in days if d >= "2021-01-01"])
    for a in m.ACCOUNTINGS:
        assert set(stat["tests"][a]["family_sharpe_ann"]) == {v_["name"] for v_ in m.T473_VARIANTS}
    assert stat["cost_ann"]["target"] <= stat["cost_ann"]["drift"]
