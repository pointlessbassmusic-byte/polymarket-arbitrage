"""Batch-6c events harnesses (T-374 dividend-month premium, T-334 S&P 500 addition reversal, T-394 FINRA short-volume
ratio) on synthetic data only: for every core function a planted effect passes and a null does not; the dividend-month
spans and listing rule, the two-way cluster bootstrap, the absent-member sensitivity, the membership snapshots, rename
edges (unexplained pairs, Wikipedia ticker changes, ambiguous groups through date-added), the price book's identity and
volume-continuity checks, the addition confirmation, the trailing z, the next-open alignment, the FINRA volume identity
check and the survivorship gate are checked directly; every harness runs JSON-safe on a fake archive, and missing bundles
give inconclusive. Regression tests for the audited defects: renames judged on the tickers, not on the reason text
(AAL / WLTW / EVRG are additions, Howmet and Dayforce are not), other-spelling and pre-2010-06 confirmations, rename
edges only with same-company evidence (no FOSL -> WLTW, NAVI -> EVRG, QLGC -> NE), the later-listing and unpaired-
successor edges (IR -> TT, KORS -> CPRI), the volume check overruling a wrong Yahoo longName (VMRK), refused spans
refilled by the successor (BBT -> TFC), FINRA identity per spell (Yahoo's IR), and T-374's absent-member gate under
every cost reading and for the DSR. No archive, no network."""

import json
import math
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6c_events as m


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(m, "REPS_MAX", 3)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- generators --

EPOCH = date(1970, 1, 1).toordinal()


def bdays(start, end="2026-10-14"):
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def eds(days):
    return np.array([date.fromisoformat(d).toordinal() - EPOCH for d in days], np.int64)


class FakeArchive:
    def __init__(self, bundles, recipes=None, created="2026-10-15T23:30:00+00:00"):
        self.bundles = bundles
        self.recipes = recipes or {}
        self.created = created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created, recipe=self.recipes.get(name, ""))

    def load(self, name):
        return iter(self.bundles[name])


def yahoo_rows(days, close, vol=None):
    rows = []
    for k, (d, c) in enumerate(zip(days, close)):
        od = date.fromisoformat(d).toordinal()
        v = {"t": (od - EPOCH) * 86400 + 14.5 * 3600, "open": float(c), "high": float(c), "low": float(c),
             "close": float(c), "adjclose": float(c)}
        if vol is not None:
            v["volume"] = float(vol[k])
        rows.append({"kind": "price", "available_at": date.fromordinal(od + 1).isoformat() + "T14:30:00+00:00", "value": v})
    return rows


def recipe(name):
    return 'yahoo /v8/finance/chart/X; meta {"currency": "USD", "longName": "%s"}. Yahoo terms' % name


def div_rows(ex_days):
    return [{"kind": "dividend", "available_at": d + "T13:30:00+00:00", "value": {"type": "dividend", "ex_date": d, "amount": 0.5}}
            for d in ex_days]


def quarterly(months, day=15, y0=2008, y1=2026):
    return [date(y, mo, day).isoformat() for y in range(y0, y1 + 1) for mo in months if date(y, mo, day).isoformat() <= "2026-10-14"]


# ======================================================================================= T-374 pieces ==

def _div_world(drift, n_firms=30, seed=0, etf_drift=None):
    """Calendar, SPY and firms whose total return beats SPY by ``drift`` a session from each dividend month's start
    to the session before its ex-date (day 15; the same every year, so the prior-year prediction is exact)."""
    rng = np.random.default_rng(seed)
    days = bdays("2008-01-02")
    cal = eds(days)
    n = cal.size
    spy = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, n))
    rs = spy[1:] / spy[:-1] - 1
    mo = np.array([int(d[5:7]) for d in days])
    dom = np.array([int(d[8:10]) for d in days])

    def firm(months, sd, dr, sd_seed):
        r = np.zeros(n)
        r[1:] = rs + np.random.default_rng(sd_seed).normal(0, sd, n - 1)
        inspan = np.isin(mo, months) & (dom < 15)
        r[inspan] += dr
        px = 100 * np.cumprod(1 + r)
        exd = np.array(sorted(m._ed(x) for x in quarterly(months)), np.int64)
        return {"adj": px, "exd": exd, "first": int(cal[0])}
    groups = ([1, 4, 7, 10], [2, 5, 8, 11], [3, 6, 9, 12])
    firms = {f"F{i:02d}": firm(groups[i % 3], 0.01, drift, seed * 100 + i) for i in range(n_firms)}
    ed_ = drift if etf_drift is None else etf_drift
    etfs = {s: firm([3, 6, 9, 12], 0.003, ed_, seed * 100 + 90 + k) for k, s in enumerate(m.T374_ETFS)}
    return cal, spy, firms, etfs


def _judge_world(drift, min_n=1000, seed=0):
    cal, spy, firms, etfs = _div_world(drift, seed=seed)
    P = m.divmonth_panel(cal, spy, firms)
    E = m.divmonth_panel(cal, spy, etfs, same_firms=False)
    x = m.monthly_diff(P)
    fam = {"1": m._sr(x), "2": m._sr(m.monthly_diff(m.divmonth_panel(cal, spy, firms, mode="through"))),
           "3": (m._sr(m.monthly_diff(E, per=3)) or 0.0) / math.sqrt(3), "4": m._sr(m.exday_capture(cal, spy, firms))}
    return m.judge_divmonth(P, E, fam, x, min_n=min_n), P


def test_divmonth_spans_kinds_and_listing():
    days = bdays("2008-01-02", "2011-12-30")
    cal = eds(days)
    spy = np.full(cal.size, 100.0)
    adj = 100.0 * (1.001 ** np.arange(cal.size))                     # +0.1% every session
    exd = np.array([m._ed("2009-03-10"), m._ed("2009-06-10"), m._ed("2010-03-10")], np.int64)
    mi = m._month_index(cal)
    r = m.divmonth_obs(cal, mi, spy, adj, exd, int(cal[0]), m._mk_of("2010-01"), m._mk_of("2010-12"))["obs"]
    kind, v = r[m._mk_of("2010-03")]
    assert kind == "D"
    i0 = int(np.searchsorted(cal, m._ed("2010-02-26")))              # previous month's last close
    i1 = int(np.searchsorted(cal, m._ed("2010-03-09")))              # the close before the predicted 2010-03-10
    assert v == pytest.approx(adj[i1] / adj[i0] - 1.0)
    assert r[m._mk_of("2010-06")][0] == "D"
    assert r[m._mk_of("2010-04")][0] == "N"                          # a payer in the year before, no ex-date a year ago
    i1n = int(np.searchsorted(cal, m._ed("2010-04-09")))             # day 10 of the latest ex-date (2010-03-10)
    i0n = int(np.searchsorted(cal, m._ed("2010-03-31")))
    assert r[m._mk_of("2010-04")][1] == pytest.approx(adj[i1n] / adj[i0n] - 1.0)
    assert m._mk_of("2010-01") not in r or r[m._mk_of("2010-01")][0] == "N"
    # 2011-07..: no ex-date in the 12 months before -> not a payer, not in the sample
    r2 = m.divmonth_obs(cal, mi, spy, adj, exd, int(cal[0]), m._mk_of("2011-04"), m._mk_of("2011-12"))["obs"]
    assert not r2
    # listing rule: a firm whose first bar is after the month a year earlier is not in that month
    r3 = m.divmonth_obs(cal, mi, spy, adj, exd, m._ed("2009-05-01"), m._mk_of("2010-03"), m._mk_of("2010-06"))["obs"]
    assert m._mk_of("2010-03") not in r3 and m._mk_of("2010-06") in r3


def test_divmonth_through_mode_includes_the_ex_day():
    days = bdays("2008-01-02", "2010-12-31")
    cal = eds(days)
    spy = np.full(cal.size, 100.0)
    adj = 100.0 * (1.001 ** np.arange(cal.size))
    exd = np.array([m._ed("2009-03-10"), m._ed("2010-03-10")], np.int64)
    mi = m._month_index(cal)
    a = m.divmonth_obs(cal, mi, spy, adj, exd, int(cal[0]), m._mk_of("2010-03"), m._mk_of("2010-03"), "runup")["obs"]
    b = m.divmonth_obs(cal, mi, spy, adj, exd, int(cal[0]), m._mk_of("2010-03"), m._mk_of("2010-03"), "through")["obs"]
    k = m._mk_of("2010-03")
    assert b[k][1] == pytest.approx((1 + a[k][1]) * 1.001 - 1.0)


def test_panel_same_firms_and_twoway_point_estimate():
    cal, spy, firms, _ = _div_world(0.0005, n_firms=9)
    firms["MONTHLY"] = dict(firms["F00"], exd=np.array(sorted(m._ed(d) for d in quarterly(range(1, 13)))), first=int(cal[0]))
    P = m.divmonth_panel(cal, spy, firms)
    assert "MONTHLY" not in P["syms"] and P["one_kind_firms"] == ["MONTHLY"]
    b = m.twoway_boot(P, m._scope_masks(P["months"]), {"gross": 0.0, "net": 0.0005}, "two-way", 200, 1)
    d = m._diff(P["XD"], P["CD"], P["XN"], P["CN"], 0.0)
    assert b["full"]["gross"]["est"] == pytest.approx(d)
    assert b["full"]["net"]["est"] == pytest.approx(d - 0.0005)
    assert b["full"]["gross"]["p"] < 0.05


def test_twoway_null_is_not_significant():
    cal, spy, firms, _ = _div_world(0.0, n_firms=12, seed=3)
    P = m.divmonth_panel(cal, spy, firms)
    full = {"full": np.ones(len(P["months"]), bool)}
    for how in m.T374_HOWS + ("two-way",):
        b = m.twoway_boot(P, full, {"g": 0.0}, how, 400, 2)
        assert b["full"]["g"]["p"] > 0.01
    assert m.cgm_twoway(P, full, {"g": 0.0})["full"]["g"]["p"] > 0.01


def test_cgm_matches_firm_clustering_without_month_correlation():
    cal, spy, firms, _ = _div_world(0.0012, n_firms=30, seed=5)
    P = m.divmonth_panel(cal, spy, firms)
    full = {"full": np.ones(len(P["months"]), bool)}
    c = m.cgm_twoway(P, full, {"g": 0.0})["full"]["g"]
    b = m.twoway_boot(P, full, {"g": 0.0}, "firm", 2000, 3)["full"]["g"]
    se_boot = (b["ci"][1] - b["ci"][0]) / 3.92
    assert c["est"] == pytest.approx(b["est"]) and 0.6 < c["se"] / se_boot < 1.6
    assert c["p"] < 0.001


def test_t374_planted_passes():
    j, P = _judge_world(0.0012)
    assert j["verdict"] == "supported", j["why"]
    assert j["n"] >= 1000 and j["dsr"]["dsr"] > 0.95


def test_t374_null_fails():
    j, P = _judge_world(0.0, seed=1)
    assert j["verdict"] == "not_supported"


def test_t374_etf_robustness_can_fail_alone():
    cal, spy, firms, etfs = _div_world(0.0012, etf_drift=0.0)
    P = m.divmonth_panel(cal, spy, firms)
    E = m.divmonth_panel(cal, spy, etfs, same_firms=False)
    x = m.monthly_diff(P)
    j = m.judge_divmonth(P, E, {"1": m._sr(x), "2": 0.0, "3": 0.0, "4": 0.0}, x, min_n=1000)
    assert j["verdict"] == "not_supported"
    assert [c[1] for c in j["criteria"]][:3] == [True, True, True]
    assert j["criteria"][3][1] is False


def test_t374_absent_members_gate():
    j, P = _judge_world(0.0, seed=1)
    full = np.ones(len(P["months"]), bool)
    b = j["boot"][m.TWO]["full"]["net"]
    s = m.absent_sensitivity(P, full, 2, b["est"], b["ci"])
    assert s["need_up"] > s["firm_max"]                     # two absent firms cannot lift a null to 20 bp
    s_many = m.absent_sensitivity(P, full, 300, b["est"], b["ci"])
    assert s_many["need_up"] < s["need_up"]
    cal, spy, firms, etfs = _div_world(0.0, seed=1)
    E = m.divmonth_panel(cal, spy, etfs, same_firms=False)
    x = m.monthly_diff(P)
    j2 = m.judge_divmonth(P, E, {"1": 0.0}, x, min_n=1000, n_absent=2)
    assert j2["criteria"][0][1] is False and "the failure stands" in j2["criteria"][0][0]
    j3 = m.judge_divmonth(P, E, {"1": 0.0}, x, min_n=1000, n_absent=10000)
    assert j3["criteria"][0][1] is None and "undecided by the absent data" in j3["criteria"][0][0]


def test_t374_absent_gate_judges_every_cost_reading():
    """Regression (T-374 absent_sensitivity): the stock criterion conjoins gross and net, so a failure stands only when
    it stands under both readings. Six absent firms could lift the gross reading to the pass bound (need below the
    largest included firm's gross difference) but not the net one: the old net-only gate kept False; now None."""
    j0, P = _judge_world(0.0, seed=1)
    full = np.ones(len(P["months"]), bool)
    c = j0["boot"][m.TWO]["full"]
    g = m.absent_sensitivity(P, full, 6, c["gross"]["est"], c["gross"]["ci"], cost=0.0)
    t = m.absent_sensitivity(P, full, 6, c["net"]["est"], c["net"]["ci"], cost=m.T374_COST)
    assert g["need_up"] <= g["firm_max"] and t["need_up"] > t["firm_max"]       # gross could flip, net stands
    assert t["firm_max"] == pytest.approx(g["firm_max"] - m.T374_COST)          # firm-level differences per reading
    cal, spy, firms, etfs = _div_world(0.0, seed=1)
    E = m.divmonth_panel(cal, spy, etfs, same_firms=False)
    x = m.monthly_diff(P)
    j = m.judge_divmonth(P, E, {"1": m._sr(x), "2": 0.0, "3": 0.0, "4": 0.0}, x, min_n=1000, n_absent=6)
    name, ok = j["criteria"][0]
    assert ok is None and "(could flip)" in name and "a reading's failure does not stand" in name
    assert set(j["absent_sensitivity"]["full"]) == {"gross", "net"}
    j2 = m.judge_divmonth(P, E, {"1": m._sr(x), "2": 0.0, "3": 0.0, "4": 0.0}, x, min_n=1000, n_absent=2)
    assert j2["criteria"][0][1] is False and "the failure stands under every reading" in j2["criteria"][0][0]


def test_t374_dsr_absent_sensitivity():
    """Regression (T-374): the DSR is computed on the stock panel, so it involves the absent members too."""
    rng = np.random.default_rng(4)
    x = rng.normal(0.0, 0.01, 200)
    fam = {"1": m._sr(x), "2": 0.0, "3": 0.0, "4": 0.0}
    row = ("DSR", False, True)
    small = m.dsr_absent(row, x, fam, {"w": 0.001, "firm_max": 0.02, "firm_min": -0.02}, 1)
    assert small[0][1] is False and "the failure stands" in small[0][0]
    big = m.dsr_absent(row, x, fam, {"w": 0.3, "firm_max": 0.02, "firm_min": -0.02}, 50)
    assert big[0][1] is None and "undecided by the absent data" in big[0][0]


def test_monthly_diff_quarterly_grouping():
    cal, spy, _, etfs = _div_world(0.0006)
    E = m.divmonth_panel(cal, spy, etfs, same_firms=False)
    assert m.monthly_diff(E).size == 0                      # every fund goes ex in the same months
    q = m.monthly_diff(E, per=3)
    assert q.size > 60 and q.mean() > 0.003


# ======================================================================================= membership pieces ==

def _snaps(pairs):
    return [(m._ed(d), frozenset(s)) for d, s in pairs]


def test_membership_snapshots_apply_post_fja_changes():
    fja = [{"value": {"date": "2020-01-02", "tickers": ["A", "B", "BRK.B"]}}]
    chg = [{"effective_date": "2020-03-02", "added_ticker": "C", "removed_ticker": "A"},
           {"effective_date": "2019-06-01", "added_ticker": "X", "removed_ticker": "Y"}]
    s = m.membership_snapshots(fja, chg)
    assert len(s) == 2 and s[1][1] == frozenset({"B", "BRK.B", "C"})
    assert m.members_at(s, m._ed("2020-02-28")) == frozenset({"A", "B", "BRK.B"})
    assert m.members_at(s, m._ed("2019-01-01")) == frozenset()


def test_rename_edges_pair_wikipedia_and_ambiguous():
    snaps = _snaps([("2010-01-04", {"A", "B", "C", "H", "S"}),
                    ("2012-05-01", {"A", "B", "D", "H", "S"}),            # C -> D, unexplained: a rename
                    ("2013-05-01", {"A", "E", "D", "H", "S"}),            # B -> E with a Wikipedia ticker-change row
                    ("2014-05-01", {"A", "E", "D", "H", "S", "Z"}),       # Z added, Wikipedia-confirmed: no edge
                    ("2019-11-05", {"A", "E", "D", "NL", "PK", "Z"}),     # H, S -> NL, PK: ambiguous
                    ("2022-11-08", {"A", "E", "D", "GN", "PK", "Z"}),     # NL -> GN
                    ("2024-03-04", {"A", "E", "D", "GN", "DC", "Z"})])    # PK -> DC
    chg = [{"effective_date": "2013-05-01", "added_ticker": "E", "removed_ticker": "B", "reason": "B changed its ticker symbol to E."},
           {"effective_date": "2014-05-01", "added_ticker": "Z", "removed_ticker": None, "reason": "Market capitalization."}]
    current = {"GN": {"date_added": "2003-03-25"}, "DC": {"date_added": "2008-03-31"}}
    # the ambiguous pair: H joined 2008-03-31, S joined 2003-03-25 (spell starts from an earlier snapshot)
    snaps = _snaps([("2003-03-25", {"A", "B", "C", "S"}), ("2008-03-31", {"A", "B", "C", "H", "S"})]) + snaps[1:]
    refs = {"C": ["Charlie Co"], "D": ["Charlie Holdings"], "NL": ["Nlock Software"], "GN": ["Nlock Gen Digital"],
            "PK": ["Peakco Health"], "DC": ["Peakco Doc Properties"]}
    e = {(x, y): how for _, x, y, how in m.rename_edges(snaps, chg, current, start="2010-06-01", refs=refs)}
    assert e[("C", "D")].startswith("unexplained leave/join pair (names match")
    assert e[("B", "E")] == "wikipedia ticker change"
    assert ("H", "PK") in e and ("S", "NL") in e and "date added" in e[("H", "PK")]
    assert e[("NL", "GN")] and e[("PK", "DC")]
    assert not any(y == "Z" for _, y in e)


def test_name_match_rules():
    assert m.name_match("Meta Platforms, Inc.", "Meta Platforms")
    assert m.name_match("Super Micro Computer, Inc.", "Supermicro")
    assert m.name_match("International Business Machines Corporation", "IBM", "IBM")
    assert m.name_match("Westinghouse Air Brake Technologies Corporation", "Wabtec", "WAB")
    assert m.name_match("SLB N.V.", "Schlumberger", "SLB")
    assert not m.name_match("Banzai International, Inc.", "Paramount Global", "PARA")
    assert not m.name_match("AvalonBay Communities, Inc.", "Vivmark Residential", "VMRK")


def _book_world(pre_vol=1e6):
    days = bdays("2008-01-02", "2014-12-31")
    n = len(days)
    spy = 100 * np.cumprod(np.full(n, 1.0002))
    meta = 50 * np.cumprod(np.full(n, 1.0005))
    vol = np.full(n, 1e6)
    cut = days.index("2012-06-01")
    vol[:cut] = pre_vol
    b = {m.SPY_B: yahoo_rows(days, spy, np.full(n, 1e8)),
         "daily-history-NEW": yahoo_rows(days, meta, vol),
         "daily-history-OLD": yahoo_rows(days[-20:], np.full(20, 10.0), np.full(20, 1e5))}    # a reused ticker
    rec = {"daily-history-NEW": recipe("Newco Holdings, Inc."), "daily-history-OLD": recipe("Some Daily ETF")}
    return FakeArchive(b, rec), days


def test_price_book_rename_fill_identity_and_continuity():
    arch, days = _book_world()
    edges = [(m._ed("2012-06-01"), "OLD", "NEW", "pair")]
    refs = {"NEW": ["Newco"], "OLD": ["Oldco Inc"]}
    bk = m.PriceBook(arch, edges, refs, check_own=True)
    r = bk.resolved("OLD")
    cal = m._spy(arch)["cal"]
    i_before, i_after = int(np.searchsorted(cal, m._ed("2011-06-01"))), int(np.searchsorted(cal, m._ed("2014-12-01")))
    assert np.isfinite(r["adj"][i_before]) and r["names"][r["src"][i_before]] == "NEW"
    assert not np.isfinite(r["adj"][i_after])                  # the reused ticker's own bars are refused on identity
    assert "OLD" in bk.rejected
    m._CACHE.clear()
    arch2, _ = _book_world(pre_vol=300.0)                      # pre-rename prints of a few hundred shares
    bk2 = m.PriceBook(arch2, edges, refs, check_own=True)
    r2 = bk2.resolved("OLD")
    assert r2 is None and "OLD->NEW" in bk2.rejected
    m._CACHE.clear()
    bk3 = m.PriceBook(arch, edges, {"OLD": ["Oldco Inc"]}, check_own=True)   # the successor is named nowhere
    assert bk3.resolved("OLD") is None
    m._CACHE.clear()
    bk4 = m.PriceBook(arch, edges, {"OLD": ["Oldco Inc"]}, check_own=False, unknown_ok=True)
    assert np.isfinite(bk4.resolved("OLD")["adj"][i_before])


def test_later_listing_and_unpaired_successor_edges():
    """Regression (T-334 / T-394 PriceBook.resolved, rename_edges): IR -> TT (Wikipedia adds Gardner Denver as IR while
    Ingersoll-Rand plc continues as TT, and Yahoo's IR starts in 2017) and KORS -> CPRI (fja lists Michael Kors under
    both tickers from 2016, Yahoo has no KORS) become edges, so those events are priced from the same company's history:
    IR before 2020-03-02 from TT, never from Yahoo's own later IR listing."""
    snaps = _snaps([("2009-01-02", {"A", "X"}), ("2010-11-17", {"A", "X", "IR"}), ("2013-11-13", {"A", "X", "IR", "KORS"}),
                    ("2016-01-04", {"A", "X", "IR", "KORS", "CPRI"}), ("2018-09-19", {"A", "X", "IR", "CPRI"}),
                    ("2020-03-02", {"A", "IR", "CPRI", "TT"})])
    chg = [{"effective_date": "2010-11-17", "added_ticker": "IR", "added_security": "Ingersoll-Rand", "removed_ticker": None},
           {"effective_date": "2013-11-13", "added_ticker": "KORS", "added_security": "Michael Kors", "removed_ticker": None},
           {"effective_date": "2020-03-03", "added_ticker": "IR", "added_security": "Ingersoll Rand", "removed_ticker": "X",
            "removed_security": "Xco", "reason": "Gardner Denver merged with Ingersoll-Rand's industrial unit and was renamed."}]
    current = {"TT": {"symbol": "TT", "security": "Trane Technologies", "date_added": "2010-11-17"},
               "CPRI": {"symbol": "CPRI", "security": "Capri Holdings", "date_added": "2013-11-13"},
               "IR": {"symbol": "IR", "security": "Ingersoll Rand", "date_added": "2020-03-03"}}
    refs = dict(m._ref_names(list(current.values()), chg))
    arch = _facts_world({"IR": ("Ingersoll Rand Inc.", "2017-05-12", None), "TT": ("Trane Technologies plc", "2008-01-02", None),
                         "CPRI": ("Capri Holdings Limited", "2011-12-15", None)})
    facts = m.YahooFacts(arch, refs)
    edges = m.rename_edges(snaps, chg, current, start="2010-06-01", facts=facts, refs=refs)
    e = {(x, y): how for _, x, y, how in edges}
    assert e[("IR", "TT")].startswith("ticker reused") and e[("KORS", "CPRI")].startswith("unexplained leave paired")
    bk = m.PriceBook(arch, edges, refs, joins=m.spell_joins(snaps))
    cal = m._spy(arch)["cal"]
    ir = bk.resolved("IR")
    at = lambda r, d: r["names"][r["src"][int(np.searchsorted(cal, m._ed(d)))]]
    assert at(ir, "2010-11-17") == "TT" and at(ir, "2019-06-03") == "TT" and at(ir, "2021-06-01") == "IR"
    assert any(k.startswith("IR<") for k in bk.rejected)
    assert at(bk.resolved("KORS"), "2013-11-13") == "CPRI"
    A = m.addition_events(snaps, chg, None, start="2010-01-01", facts=facts, refs=refs)
    out = {r["ticker"]: r for r in m.event_excess(A["events"], cal, m._spy(arch)["adj"], bk.resolved)}
    assert out["IR"]["status"] == "ok" and out["IR"]["via"] == "TT" and out["KORS"]["via"] == "CPRI"


def test_price_book_volume_identity_overrules_a_wrong_longname_and_refused_spans_refill():
    """Regression (T-394: VMRK, BBT): with names_veto off (FINRA volume decides), a successor whose Yahoo longName
    disagrees (VMRK reads 'AvalonBay' but carries Equity Residential's bars) is used and recorded; with it on (T-334) it
    is refused. A refused own span (BBT's re-issued ticker) is refilled from the successor (TFC) for those dates."""
    arch, days = _book_world()
    edges = [(m._ed("2012-06-01"), "OLD", "NEW", "pair")]
    refs = {"NEW": ["Vivmark Residential"], "OLD": ["Oldco Inc"]}
    cal = m._spy(arch)["cal"]
    i = int(np.searchsorted(cal, m._ed("2011-06-01")))
    on = m.PriceBook(arch, edges, refs, check_own=False, unknown_ok=True, names_veto=False)
    r = on.resolved("OLD")
    assert r["names"][r["src"][i]] == "NEW" and "NEW" in on.name_overruled
    off = m.PriceBook(arch, edges, refs, check_own=True, names_veto=True)
    assert off.resolved("OLD") is None and "NEW" in off.rejected
    m._CACHE.clear()
    days = bdays("2008-01-02", "2014-12-31")
    n = len(days)
    b = {m.SPY_B: yahoo_rows(days, 100 * np.cumprod(np.full(n, 1.0002)), np.full(n, 1e8)),
         "daily-history-BBT": yahoo_rows(days, 10 * np.cumprod(np.full(n, 1.0001)), np.full(n, 1e5)),
         "daily-history-TFC": yahoo_rows(days, 40 * np.cumprod(np.full(n, 1.0004)), np.full(n, 5e6))}
    arch2 = FakeArchive(b, {"daily-history-BBT": recipe("Beacon Financial"), "daily-history-TFC": recipe("Truist Financial")})
    bk = m.PriceBook(arch2, [(m._ed("2012-06-01"), "BBT", "TFC", "pair")], {}, check_own=False, unknown_ok=True,
                     joins={"BBT": [m._ed("2008-01-02")]}, names_veto=False)
    cal2 = m._spy(arch2)["cal"]
    j = int(np.searchsorted(cal2, m._ed("2010-06-01")))
    assert bk.resolved("BBT")["names"][bk.resolved("BBT")["src"][j]] == "BBT"
    rf = bk.resolved("BBT", refuse=(("BBT", m._ed("2008-01-02"), m._ed("2012-06-01")),))
    assert rf["names"][rf["src"][j]] == "TFC"


def test_addition_events_confirm_and_exclude():
    snaps = _snaps([("2009-12-01", {"A", "B", "Q"}), ("2012-03-19", {"A", "N1", "Q"}), ("2013-05-01", {"A", "N1", "RN"}),
                    ("2014-02-03", {"A", "N1", "RN", "UN"}), ("2026-09-21", {"A", "N1", "RN", "UN", "LATE"})])
    chg = [{"effective_date": "2012-03-16", "added_ticker": "N1", "removed_ticker": "B", "announced": "2012-03-06",
            "added_security": "Newone"},
           {"effective_date": "2013-05-01", "added_ticker": "RN", "removed_ticker": "Q", "reason": "Q renamed RN."},
           {"effective_date": "2026-09-21", "added_ticker": "LATE", "removed_ticker": None, "reason": "Market cap."}]
    A = m.addition_events(snaps, chg, m._ed("2026-08-18"))
    t = {e["ticker"]: e for e in A["events"]}
    assert set(t) == {"N1", "LATE"} and t["N1"]["announced"] == "2012-03-06" and t["LATE"]["after_fja"]
    assert [u["ticker"] for u in A["unconfirmed"]] == ["UN"]
    assert [r["ticker"] for r in A["rename_rows"]] == ["RN"]


def _facts_world(specs, start="2008-01-02", end="2021-12-31"):
    """A fake archive with SPY and the given Yahoo histories {ticker: (longName, first day, last day or None)}."""
    days = bdays(start, end)
    n = len(days)
    rng = np.random.default_rng(7)
    b = {m.SPY_B: yahoo_rows(days, 100 * np.cumprod(np.full(n, 1.0002)), np.full(n, 1e8))}
    rec = {m.SPY_B: recipe("SPDR S&P 500 ETF Trust")}
    for k, (t, (nm, a, z)) in enumerate(specs.items()):
        dd = [d for d in days if d >= a and (z is None or d <= z)]
        px = (20 + 10 * k) * np.cumprod(1 + rng.normal(0.0003, 0.01, len(dd)))
        b[f"daily-history-{t}"] = yahoo_rows(dd, px, np.full(len(dd), 1e6))
        rec[f"daily-history-{t}"] = recipe(nm)
    return FakeArchive(b, rec)


def _rename_world():
    """Evergy replaces Navient (which trades on as itself), Willis Towers Watson replaces Fossil (likewise), American
    Airlines replaces Allergan (which is not an fja leaver on that change), Arconic -> Howmet 'remained in the index',
    Ceridian -> Dayforce a ticker change (no Yahoo history for either), QLogic / Noble an unexplained pair with no
    evidence, OLDT -> NEWT an unexplained pair whose Yahoo history is continuous."""
    snaps = _snaps([("2011-01-03", {"A", "NAVI", "FOSL", "AVP", "ARNC", "CDAY", "QLGC", "OLDT"}),
                    ("2015-03-23", {"A", "NAVI", "FOSL", "AAL", "ARNC", "CDAY", "QLGC", "OLDT"}),
                    ("2016-01-05", {"A", "NAVI", "WLTW", "AAL", "ARNC", "CDAY", "QLGC", "OLDT"}),
                    ("2017-01-18", {"A", "NAVI", "WLTW", "AAL", "ARNC", "CDAY", "NE", "OLDT"}),
                    ("2018-06-05", {"A", "EVRG", "WLTW", "AAL", "ARNC", "CDAY", "NE", "OLDT"}),
                    ("2019-05-01", {"A", "EVRG", "WLTW", "AAL", "ARNC", "CDAY", "NE", "NEWT"}),
                    ("2020-04-06", {"A", "EVRG", "WLTW", "AAL", "HWM", "CDAY", "NE", "NEWT"}),
                    ("2021-02-01", {"A", "EVRG", "WLTW", "AAL", "HWM", "DAY", "NE", "NEWT"})])
    chg = [{"effective_date": "2015-03-23", "added_ticker": "AAL", "added_security": "American Airlines Group",
            "removed_ticker": "AGN", "removed_security": "Allergan",
            "reason": "Allergan was acquired by Actavis (and changed its name to Allergan)."},
           {"effective_date": "2015-03-23", "added_ticker": None, "removed_ticker": "AVP", "reason": "Market cap."},
           {"effective_date": "2016-01-05", "added_ticker": "WLTW", "added_security": "Willis Towers Watson",
            "removed_ticker": "FOSL", "removed_security": "Fossil Group",
            "reason": "Willis Holdings merged with Towers Watson and was renamed Willis Towers Watson."},
           {"effective_date": "2018-06-05", "added_ticker": "EVRG", "added_security": "Evergy", "removed_ticker": "NAVI",
            "removed_security": "Navient", "reason": "Westar Energy acquired Great Plains Energy and changed name to Evergy."},
           {"effective_date": "2020-04-01", "added_ticker": "HWM", "added_security": "Howmet Aerospace", "removed_ticker": "ARNC",
            "removed_security": "Arconic", "reason": "Arconic separated into 2 companies - Howmet remained in the index."},
           {"effective_date": "2021-02-01", "added_ticker": "DAY", "added_security": "Dayforce", "removed_ticker": "CDAY",
            "removed_security": "Ceridian", "reason": "Ceridian changed its ticker symbol from CDAY to DAY."}]
    refs = dict(m._ref_names([], chg))
    refs.update({"QLGC": ["QLogic"], "NE": ["Noble Corporation"], "OLDT": ["Oldtown Corp"], "NEWT": ["Brandnew Inc"]})
    arch = _facts_world({"NAVI": ("Navient Corporation", "2008-01-02", None), "FOSL": ("Fossil Group, Inc.", "2008-01-02", None),
                         "EVRG": ("Evergy, Inc.", "2008-01-02", None), "WLTW": ("Some Daily ETF", "2020-01-02", None),
                         "AAL": ("American Airlines Group Inc.", "2008-01-02", None),
                         "HWM": ("Howmet Aerospace Inc.", "2008-01-02", None), "NE": ("Noble Corporation plc", "2021-02-08", None),
                         "NEWT": ("Brandnew Inc", "2008-01-02", None)})
    return snaps, chg, refs, arch


def test_addition_events_judge_renames_on_the_tickers():
    """Regression (T-334 addition_events): the reason text describes the company that LEFT. AAL, WLTW and EVRG are
    additions (the leaver is not on the change, or trades on as itself); Howmet 'remained in the index'; CDAY -> DAY,
    the change's only leave/join with no Yahoo history trading on, is a ticker change. The old reason regex dropped the
    first three and counted Howmet; a positional slip in same_company kept DAY."""
    snaps, chg, refs, arch = _rename_world()
    facts = m.YahooFacts(arch, refs)
    A = m.addition_events(snaps, chg, None, start="2010-01-01", facts=facts, refs=refs, edge_start="2010-06-01")
    ev = {e["ticker"] for e in A["events"]}
    assert {"AAL", "WLTW", "EVRG"} <= ev and not ({"HWM", "DAY"} & ev)
    rr = {r["ticker"]: r["why"] for r in A["rename_rows"]}
    assert rr["HWM"] == "remained in the index" and "only unexplained leave/join" in rr["DAY"]
    kept = {r["ticker"]: r["why"] for r in A["rename_candidates_kept"]}
    assert "trades on across" in kept["EVRG"] and "trades on across" in kept["WLTW"] and "not the only" in kept["AAL"]
    assert "NE" in {u["ticker"] for u in A["unconfirmed"]}                  # no Wikipedia row, after 2010-06


def test_rename_edges_need_same_company_evidence():
    """Regression (T-334 rename_edges): no FOSL -> WLTW or NAVI -> EVRG edge from the reason text, no QLGC -> NE edge from
    a bare leave/join pair; CDAY -> DAY and ARNC -> HWM (one company), OLDT -> NEWT (Yahoo history continuous) are."""
    snaps, chg, refs, arch = _rename_world()
    facts = m.YahooFacts(arch, refs)
    e = {(x, y): how for _, x, y, how in m.rename_edges(snaps, chg, {}, start="2010-06-01", facts=facts, refs=refs)}
    assert ("FOSL", "WLTW") not in e and ("NAVI", "EVRG") not in e and ("QLGC", "NE") not in e
    assert e[("CDAY", "DAY")] == "wikipedia ticker change" and e[("ARNC", "HWM")] == "wikipedia ticker change"
    assert "Yahoo's NEWT history covers" in e[("OLDT", "NEWT")]
    bk = m.PriceBook(arch, sorted((m._ed("2020-01-01"), x, y, h) for (x, y), h in e.items()), refs)
    cal = m._spy(arch)["cal"]
    nv = bk.resolved("NAVI")
    i = int(np.searchsorted(cal, m._ed("2013-01-02")))
    assert nv["names"][nv["src"][i]] == "NAVI"                              # Navient's own bars, never Evergy's


def test_addition_events_other_spellings_and_early_joins():
    """Regression (T-334): fja's later tickers are confirmed by the Wikipedia add under the old spelling (names match:
    UA = UAA; the same leaver on the change: DLPH = APTV; a leave and a join split over two fja snapshots: Q = IQV);
    an orphan add replacing a leaver of ANOTHER change (Bemis for Mattel) does not confirm a rename (L3Harris); joins
    before 2010-06 are accepted unconfirmed."""
    snaps = _snaps([("2009-12-01", {"A", "TIE", "WFM", "HRS", "MAT", "BX"}),
                    ("2010-02-16", {"A", "TIE", "WFM", "HRS", "MAT", "BX", "BRK.B"}),
                    ("2012-12-24", {"A", "APTV", "WFM", "HRS", "MAT", "BX", "BRK.B"}),
                    ("2014-05-01", {"A", "APTV", "WFM", "HRS", "MAT", "BX", "BRK.B", "UAA"}),
                    ("2017-08-28", {"A", "APTV", "HRS", "MAT", "BX", "BRK.B", "UAA"}),
                    ("2017-08-29", {"A", "APTV", "HRS", "MAT", "BX", "BRK.B", "UAA", "IQV"}),
                    ("2019-06-01", {"A", "APTV", "LHX", "MAT", "BX", "BRK.B", "UAA", "IQV"}),
                    ("2019-06-07", {"A", "APTV", "LHX", "AMCR", "BX", "BRK.B", "UAA", "IQV"})])
    chg = [{"effective_date": "2012-12-21", "added_ticker": "DLPH", "added_security": "Delphi Automotive", "removed_ticker": "TIE"},
           {"effective_date": "2014-05-01", "added_ticker": "UA", "added_security": "Under Armour", "removed_ticker": None},
           {"effective_date": "2017-08-29", "added_ticker": "Q", "added_security": "QuintilesIMS", "removed_ticker": "WFM"},
           {"effective_date": "2019-06-07", "added_ticker": "BMS", "added_security": "Bemis", "removed_ticker": "MAT"},
           {"effective_date": "2019-06-11", "added_ticker": "AMCR", "added_security": "Amcor", "removed_ticker": "BMS"}]
    refs = {"APTV": ["Aptiv"], "UAA": ["Under Armour (Class A)"], "IQV": ["IQVIA"], "LHX": ["L3Harris"]}
    sp = m.spelling_pairs(snaps, chg, refs, "2010-06-01")
    got = {t: (ntk, how) for (t, _), (w, how) in sp.items() for ntk in [w["added_ticker"]]}
    assert got == {"APTV": ("DLPH", "replaces the same leaver"), "UAA": ("UA", "names match"),
                   "IQV": ("Q", "replaces the same leaver")}
    A = m.addition_events(snaps, chg, None, start="2010-01-01", spelled=sp, refs=refs)
    ev = {e["ticker"]: e["confirmed"] for e in A["events"]}
    assert {"APTV", "UAA", "IQV", "BRK.B", "AMCR"} == set(ev) and ev["BRK.B"].startswith("accepted unconfirmed")
    assert [u["ticker"] for u in A["unconfirmed"]] == ["LHX"]


def test_event_excess_entry_exit_and_status():
    days = bdays("2015-01-02", "2015-12-31")
    cal = eds(days)
    spy = 100 * np.cumprod(np.full(cal.size, 1.001))
    stock = 100 * np.cumprod(np.full(cal.size, 1.0005))
    ser = {"S": {"adj": stock, "dv": np.full(cal.size, 1e7), "src": np.zeros(cal.size, np.int8), "names": ["S"]}}
    evs = [{"ticker": "S", "ed": m._ed("2015-03-14")}, {"ticker": "X", "ed": m._ed("2015-03-16")},
           {"ticker": "S", "ed": m._ed("2015-12-20")}]
    out = m.event_excess(evs, cal, spy, lambda t: ser.get(t))
    assert out[0]["status"] == "ok" and m._iso(cal[out[0]["i0"]]) == "2015-03-16"      # Saturday -> Monday
    assert out[0]["ex"] == pytest.approx(1.0005 ** 20 - 1.001 ** 20)
    assert out[1]["status"] == "no_history" and out[2]["status"] == "window_open"


def _addition_sample(mu, n=200, seed=0, placebo_mu=0.0):
    rng = np.random.default_rng(seed)
    ok = []
    for k in range(n):
        i0 = 30 + 12 * k
        ok.append({"ex": float(rng.normal(mu, 0.03)), "date": m._iso(16000 + (k // 2) * 15), "i0": i0})
    pe = rng.normal(placebo_mu, 0.03, n)
    draws = rng.normal(placebo_mu, 0.03 / math.sqrt(n), 1000)
    return ok, {"per_event": pe, "draw_means": draws, "n_events": n, "keep": list(range(n))}


def test_t334_planted_passes():
    ok, pl = _addition_sample(-0.012)
    j = m.judge_additions(ok, complete=True, placebo=pl, size_ok=True)
    assert j["verdict"] == "supported", j["why"]


def test_t334_null_fails():
    ok, pl = _addition_sample(0.0, seed=1)
    j = m.judge_additions(ok, complete=True, placebo=pl, size_ok=True)
    assert j["verdict"] == "not_supported"


def test_t334_placebo_off_zero_fails_and_survivor_gate():
    ok, pl = _addition_sample(-0.012, placebo_mu=-0.02)
    j = m.judge_additions(ok, complete=True, placebo=pl, size_ok=True)
    assert j["verdict"] == "not_supported" and j["criteria"][2][1] is False
    j2 = m.judge_additions(ok, complete=False, placebo=pl, size_ok=False, survivor_note=": 9 absent")
    assert j2["verdict"] == "inconclusive" and all(c[1] is None for c in j2["criteria"][:3])
    assert "NOT IMPLEMENTED" in j2["criteria"][0][0] and j2["raw"][0][1] is True


def test_absent_needed_arithmetic():
    assert m.absent_needed(90, 10, 0.01, 0.0) == pytest.approx(-0.09)
    assert m.absent_needed(90, 10, 0.01, 0.0, gap=0.005) == pytest.approx((-0.005 * 100 - 0.9) / 10)
    assert m.absent_needed(90, 0, 0.01, 0.0) is None


def test_placebo_draws_match_nearest_size():
    cal = np.arange(100, dtype=np.int64)
    spy = np.full(100, 100.0)
    ev = {"i0": 70, "dv": 1e7}
    near = {"adj": np.linspace(100, 110, 100), "dv": np.full(100, 1.1e7)}
    far = {"adj": np.linspace(100, 50, 100), "dv": np.full(100, 1e4)}
    pl = m.placebo_draws([ev], lambda e: [("N", near), ("F", far)], cal, spy, hold=20, k=1, draws=50)
    assert pl["n_events"] == 1 and np.allclose(pl["draw_means"], near["adj"][90] / near["adj"][70] - 1)


# ======================================================================================= T-394 pieces ==

def test_svr_z_matches_brute_force():
    rng = np.random.default_rng(0)
    X = rng.uniform(0.3, 0.6, (150, 3))
    X[10, 1] = np.nan
    Z = m.svr_z(X, win=60, min_obs=55)
    t, j = 100, 0
    w = X[t - 59:t + 1, j]
    assert Z[t, j] == pytest.approx((X[t, j] - w.mean()) / w.std(ddof=1))
    assert np.isnan(Z[50, 0]) and np.isnan(Z[10, 1])
    w1 = X[61:121, 1]
    assert Z[120, 1] == pytest.approx((X[120, 1] - np.nanmean(w1)) / np.nanstd(w1, ddof=1))


def test_svr_returns_next_open_to_open_five_later():
    days = bdays("2019-01-02", "2019-03-29")
    cal = eds(days)
    spy_o = np.full(cal.size, 100.0)
    O = np.arange(cal.size, dtype=float)[:, None] + 100.0
    fd = cal[[0, 5, cal.size - 3]]
    R = m.svr_returns(fd, cal, spy_o, O, hold=5)
    assert R[0, 0] == pytest.approx(O[6, 0] / O[1, 0] - 1)
    assert R[1, 0] == pytest.approx(O[11, 0] / O[6, 0] - 1)
    assert np.isnan(R[2, 0])                                       # the exit open lies past the data


def test_finra_identity_thresholds():
    rng = np.random.default_rng(1)
    yv = np.exp(rng.normal(15, 0.5, 300))
    good = 0.35 * yv * np.exp(rng.normal(0, 0.2, 300))
    mem = np.ones(300, bool)
    assert m.finra_identity(good, yv, mem)["ok"] is True
    other = np.exp(rng.normal(12, 0.5, 300))                       # a different, smaller company's volume
    assert m.finra_identity(good, other, mem)["ok"] is False
    assert m.finra_identity(good, yv, np.zeros(300, bool))["ok"] is None


def test_finra_identity_is_judged_per_spell():
    """Regression (T-394 identity loop): a Yahoo history that is another company's for part of the span (Yahoo's IR is
    Gardner Denver before the 2020-03-02 rename) passes the whole-segment check but fails on its own spell; the spell
    pieces split at the root ticker's rename and join dates."""
    rng = np.random.default_rng(5)
    n, cut = 800, 200
    yv = np.exp(rng.normal(15, 0.6, n))
    tv = 0.3 * yv * np.exp(rng.normal(0, 0.15, n))
    tv[:cut] = 0.3 * np.exp(rng.normal(15, 0.6, cut))            # FINRA's symbol was another company before the cut
    mem = np.ones(n, bool)
    assert m.finra_identity(tv, yv, mem)["ok"] is True             # the old whole-segment check passes
    cal = np.arange(10000, 10000 + n, dtype=np.int64)
    pieces = m.spell_pieces(np.zeros(n, np.int8), cal, [int(cal[cut])])
    assert pieces == [(0, 0, cut), (0, cut, n)]
    res = [m.finra_identity(tv[a:b], yv[a:b], mem[a:b])["ok"] for _, a, b in pieces]
    assert res == [False, True]
    src = np.where(np.arange(n) < cut, 1, 0).astype(np.int8)      # a successor chain already split at the rename
    assert m.spell_pieces(src, cal, []) == [(0, cut, n), (1, 0, cut)]


def test_fama_macbeth_recovers_a_slope():
    rng = np.random.default_rng(2)
    Z = rng.normal(0, 1, (300, 80))
    R = -0.001 * Z + rng.normal(0, 0.01, Z.shape)
    fm = m.fama_macbeth(Z, R, np.ones(Z.shape, bool))
    assert fm["slope"] == pytest.approx(-0.001, abs=2e-4) and fm["t"] < -5


def test_fama_macbeth_null_has_no_slope():
    rng = np.random.default_rng(3)
    Z = rng.normal(0, 1, (300, 80))
    fm = m.fama_macbeth(Z, rng.normal(0, 0.01, Z.shape), np.ones(Z.shape, bool))
    assert abs(fm["t"]) < 3


def _svr_sample(mu, n=6000, seed=0):
    rng = np.random.default_rng(seed)
    ar = rng.normal(mu, 0.03, n)
    d0 = m._ed("2019-01-02")
    sess = np.sort(rng.integers(0, 1900, n))
    sig = [m._iso(d0 + int(s * 365 / 252)) for s in sess]
    return ar, sig, sess


def test_t394_planted_passes():
    ar, sig, sess = _svr_sample(-0.006)
    j = m.judge_svr(ar, sig, sess, complete=True)
    assert j["verdict"] == "supported", j["why"]


def test_t394_null_fails():
    ar, sig, sess = _svr_sample(0.0, seed=1)
    j = m.judge_svr(ar, sig, sess, complete=True)
    assert j["verdict"] == "not_supported"


def test_t394_survivor_gate_and_below_min_n():
    ar, sig, sess = _svr_sample(-0.006)
    j = m.judge_svr(ar, sig, sess, complete=False, survivor_note=": 5 absent")
    assert j["verdict"] == "inconclusive" and all(c[1] is None for c in j["criteria"])
    assert j["raw"][0][1] is True
    ar2, sig2, sess2 = _svr_sample(0.004, n=1500, seed=4)       # below min_n, a clearly wrong-signed mean
    j2 = m.judge_svr(ar2, sig2, sess2, complete=True)
    assert j2["verdict"] == "not_supported"


# ============================================================================================ fake archive ==

STOCKS = {"AAA": "Alpha Industries Inc.", "BBB": "Bravo Foods Corp", "CCC": "Charlie Energy plc", "DDD": "Delta Robotics",
          "EEE": "Echo Banking Co", "FFF": "Foxtrot Health", "GGG": "Golf Mining Ltd", "HHH": "Hotel Realty Inc",
          "NEWA": "Newa Software Inc.", "NEWB": "Newb Devices"}
PAYERS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]


def _full_archive():
    rng = np.random.default_rng(12)
    days = bdays("2008-01-02")
    n = len(days)
    spy = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, n))
    b, rec = {m.SPY_B: yahoo_rows(days, spy, np.full(n, 8e7))}, {m.SPY_B: recipe("SPDR S&P 500 ETF Trust")}
    vols = {}
    groups = ([1, 4, 7, 10], [2, 5, 8, 11], [3, 6, 9, 12])
    for k, (s, nm) in enumerate(STOCKS.items()):
        start = {"NEWA": "2010-05-03", "NEWB": "2013-01-02"}.get(s, "2008-01-02")
        dd = [d for d in days if d >= start]
        px = 50 * np.cumprod(1 + rng.normal(0.0003, 0.015, len(dd)))
        vol = np.exp(rng.normal(14.5, 0.4, len(dd)))
        vols[s] = dict(zip(dd, vol))
        b[f"daily-history-{s}"] = yahoo_rows(dd, px, vol)
        rec[f"daily-history-{s}"] = recipe(nm)
        b[f"daily-events-{s}"] = div_rows(quarterly(groups[k % 3])) if s in PAYERS else []
    for k, s in enumerate(m.T374_ETFS):
        px = 60 * np.cumprod(1 + rng.normal(0.0003, 0.008, n))
        b[f"daily-history-{s}"] = yahoo_rows(days, px, np.full(n, 1e6))
        rec[f"daily-history-{s}"] = recipe(f"{s} Dividend ETF")
        b[f"daily-events-{s}"] = div_rows(quarterly([3, 6, 9, 12], 18))
    base = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "OLD1", "OLD2"]
    snaps = [("2008-01-02", base),
             ("2012-03-19", [t for t in base if t != "OLD1"] + ["NEWA"]),
             ("2015-06-22", [t for t in base if t not in ("OLD1", "OLD2")] + ["NEWA", "NEWB"]),
             ("2016-03-21", [t for t in base if t not in ("OLD1", "OLD2")] + ["NEWA", "NEWB", "GONE"]),
             ("2019-05-01", [t for t in base if t not in ("OLD1", "OLD2")] + ["NEWA", "NEWB", "ZZZ"])]
    b[m.FJA_B] = [{"kind": "sp500-members", "available_at": d + "T13:30:00+00:00", "value": {"date": d, "tickers": t, "n": len(t)}}
                  for d, t in snaps]
    chg = [("2012-03-19", "NEWA", "Newa Software", "OLD1", "2012-03-09"), ("2015-06-22", "NEWB", "Newb Devices", "OLD2", None),
           ("2016-03-21", "GONE", "Gone Corp", None, "2016-03-11"), ("2019-05-01", "ZZZ", "Zulu Zinc", "GONE", "2019-04-22")]
    b[m.CHG_B] = [{"kind": "index-change", "available_at": d + "T13:30:00+00:00",
                   "value": {"effective_date": d, "added_ticker": a, "added_security": sec, "removed_ticker": r,
                             "removed_security": None, "reason": "Market capitalization changes.", "announced": an}}
                  for d, a, sec, r, an in chg]
    cur = snaps[-1][1]
    b[m.CONS_B] = [{"kind": "constituent", "available_at": "2026-10-14T03:35:00+00:00",
                    "value": {"symbol": s, "security": (STOCKS.get(s) or "Zulu Zinc").split(" Inc")[0], "date_added": "2001-01-01",
                              "revision_time": "2026-10-14T03:35:00+00:00"}} for s in cur]
    members = {d: set(t) for d, t in snaps}
    sdays = sorted(members)
    for mo in m._months("2018-08", "2019-12"):
        rows = []
        for d in days:
            if not d.startswith(mo):
                continue
            mem = members[[x for x in sdays if x <= d][-1]]
            rows.append({"kind": "file-day", "available_at": d + "T23:59:59+00:00", "value": {"day": d, "status": "ok"}})
            for s in sorted(mem):
                yv = vols.get(s, {}).get(d, 3e6)
                tv = 0.35 * yv * math.exp(rng.normal(0, 0.15))
                svr = min(0.95, max(0.05, rng.normal(0.45, 0.05)))
                rows.append({"kind": "short-volume", "available_at": d + "T23:59:59+00:00",
                             "value": {"day": d, "symbol": s, "short_volume": svr * tv, "short_exempt_volume": 0.0,
                                       "total_volume": tv, "market": "Q,N"}})
        b[m.CNMS_FMT.format(mo)] = rows
    return FakeArchive(b, rec)


@pytest.fixture(scope="module")
def fake():
    return _full_archive()


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_every_harness_runs_json_safe(fake, name):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES[name](fake)
    json.dumps(stat, allow_nan=False)
    assert verdict in ("supported", "not_supported", "inconclusive")
    assert isinstance(n, int) and n > 0
    assert " — " in reason


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = m.HARNESSES[name](FakeArchive({}))
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]
    assert "missing data bundles" in reason and " — " in reason


def test_optional_bundles_are_optional(fake):
    b = dict(fake.bundles)
    for k in ("daily-history-GGG", "daily-events-GGG", "daily-history-NEWB", m.CNMS_FMT.format("2018-08")):
        b.pop(k, None)
    arch = FakeArchive(b, fake.recipes)
    for name in m.HARNESSES:
        m._CACHE.clear()
        stat, n, verdict, reason = m.HARNESSES[name](arch)
        assert "missing_bundles" not in stat and n > 0


def test_t374_harness_universe_and_absent(fake):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES["b6c_events_dividend_month"](fake)
    u = stat["universe"]
    assert u["absent"] == ["ZZZ"] and u["current_payers"] == 8 and u["non_payers"] == 2
    assert n == stat["n_dividend_firm_months"] and n < m.T374_MIN_N
    assert stat["etf"]["funds"] == sorted(m.T374_ETFS)


def test_t334_harness_survivorship(fake):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES["b6c_events_index_addition_reversal"](fake)
    assert stat["events_confirmed"] == 4 and n == 2 and stat["n_measurable"] == 4
    assert {u["ticker"] for u in stat["unpriced"]} == {"GONE", "ZZZ"} and not stat["complete_universe"]
    assert verdict == "inconclusive" and "SURVIVORSHIP" in reason
    assert stat["unpriced_yahoo_404"] == 2 and stat["unpriced_own_ticker_reissued"] == []        # each absence named
    assert "2 with no Yahoo history under the ticker or any successor" in reason
    assert stat["announcement_runup"]["events_with_cited_announcement"] == 3


def test_t394_harness_counts_absent_events(fake):
    m._CACHE.clear()
    stat, n, verdict, reason = m.HARNESSES["b6c_events_short_volume_ratio"](fake)
    assert stat["events_point_in_time"] >= stat["events_measurable"] >= stat["events_priced"] == n
    assert "ZZZ" in stat["symbols_no_history"] and stat["complete_universe"] is False
    assert verdict == "inconclusive" and "PARK CONDITION" in reason and stat["park_condition"] is None
    assert not stat["identity_rejected"]


def test_maps_consistent():
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert set(m.THEORY_MAP) == {"T-374", "T-334", "T-394"}
    assert all(k.startswith("b6c_events_") and k == k.lower() for k in m.HARNESSES)
