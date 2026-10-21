"""Synthetic tests for mandel.experiments.batch13_short_b (T-675, T-676, T-677): every signal built at a decision is
unchanged when values AFTER the decision are shocked (prices after the previous close, SEC facts accepted after the entry
open, splits after settlement, CNMS file days after -6, later FINRA releases), the split restatement defuses the
filing-vs-split trap, the books and tipping helpers do what they claim, and every harness returns inconclusive (rule 9)
on an archive whose get() raises KeyError. No network, no real archive."""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from mandel.experiments import batch6c_events as EV
from mandel.experiments import batch6c_stockxs as SX
from mandel.experiments import batch13_short_b as M


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


def _epoch(day: str, hh: int = 23, mm: int = 59) -> float:
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc).timestamp()


# ============================================================================================= SI building blocks ==

def test_finra_symbol_spelling():
    assert M.finra_sym("BRK.B") == "BRKB" and M.finra_sym("BF.B") == "BFB" and M.finra_sym("AAPL") == "AAPL"


def test_split_restatement_defuses_the_filing_vs_split_trap():
    # NVDA 2024: cover 2.46bn shares on 2024-05-24, 10:1 split ex 2024-06-10, settlement 2024-06-14, SI 315m post-split
    splits = [("2021-07-20", 4.0), ("2024-06-10", 10.0)]
    sir = M.si_ratio(315_033_985.0, 2.46e9, "2024-05-24", "2024-06-14", splits)
    assert sir == pytest.approx(315_033_985.0 / 24.6e9)
    # a split after settlement does not enter (it cannot be in the settlement-date SI)
    later = splits + [("2024-06-20", 2.0)]
    assert M.si_ratio(315_033_985.0, 2.46e9, "2024-05-24", "2024-06-14", later) == pytest.approx(sir)
    # a cover date after settlement is divided back across a split between them
    assert M.split_adj(splits, "2024-06-12", "2024-06-05") == pytest.approx(0.1)
    assert M.split_adj(splits, "2024-05-24", "2024-06-14") == pytest.approx(10.0)


def _fact(val, end, accn, av, tax="dei", tag="EntityCommonStockSharesOutstanding"):
    return (tax, tag, "shares", None, end, float(val), accn, "10-Q", float(av))


def test_shares_known_point_in_time_and_dei_first():
    facts = [_fact(100.0, "2024-01-20", "a1", 1000.0), _fact(20.0, "2024-01-20", "a1", 1000.0),      # two classes summed
             _fact(130.0, "2024-04-20", "a2", 2000.0),
             _fact(90.0, "2023-12-31", "a1", 1000.0, "us-gaap", "CommonStockSharesOutstanding")]
    ser = M.share_series(facts)
    assert M.shares_known(ser, 1500.0) == (120.0, "2024-01-20", "dei")
    assert M.shares_known(ser, 2500.0) == (130.0, "2024-04-20", "dei")
    assert M.shares_known(ser, 999.0) is None
    # a later accession accepted after the decision does not move the shares at the decision
    ser2 = M.share_series(facts + [_fact(999.0, "2024-07-20", "a3", 3000.0)])
    assert M.shares_known(ser2, 2500.0) == M.shares_known(ser, 2500.0)
    # us-gaap only when no dei value has been accepted
    g = M.share_series([_fact(90.0, "2023-12-31", "g1", 500.0, "us-gaap", "CommonStockSharesOutstanding")])
    assert M.shares_known(g, 600.0) == (90.0, "1970-01-01", "gaap")   # us-gaap basis = acceptance date


def _ep(d):
    from datetime import datetime, timezone
    return datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp()


def test_spin_off_pseudo_split_does_not_move_sir():
    # EXC 2022-02-02 Constellation spin-off stored as a 1.402 'split': FINRA SI is unchanged, so is the SIR
    sp = [("2022-02-02", 1.402)]
    assert not M.true_split(1.402) and not M.true_split(1.973) and not M.true_split(2.39)
    assert M.true_split(20.0) and M.true_split(1.5) and M.true_split(0.1) and M.true_split(4 / 3)
    assert M.si_ratio(1e7, 1e9, "2022-01-31", "2022-02-15", sp) == pytest.approx(0.01)


def test_googl_2022_gaap_count_not_split_twice():
    # Q2-2022 10-Q: balance-sheet date 2022-06-30, accepted 2022-07-26 after the 2022-07-18 20:1 split -> post-split count
    sp = [("2022-07-18", 20.0)]
    g = M.share_series([_fact(13e9, "2022-06-30", "q2", _ep("2022-07-26"), "us-gaap", "CommonStockSharesOutstanding")])
    sh = M.shares_known(g, _ep("2022-08-01"), "2022-07-29")
    assert sh == (13e9, "2022-07-26", "gaap")
    assert M.si_ratio(6.5e7, sh[0], sh[1], "2022-07-29", sp) == pytest.approx(0.005)


def test_fresher_gaap_beats_stale_dei_and_age_cap():
    facts = [_fact(100.0, "2014-01-20", "d1", _ep("2014-02-01")),
             _fact(300.0, "2024-03-31", "g1", _ep("2024-04-25"), "us-gaap", "CommonStockSharesOutstanding")]
    ser = M.share_series(facts)
    assert M.shares_known(ser, _ep("2024-05-01"), "2024-05-15")[0] == 300.0
    assert M.shares_known(ser, _ep("2015-06-01"), "2015-06-15") is None        # only the 2014 dei: > 456 days old


def test_identity_rejects_generic_token_and_fund_rows():
    assert not M.ident_ok("BlackRock New York Municipal Income Trust", ["The Bank of New York Mellon Corporation"], "BNY")
    assert not M.ident_ok("ARKO Petroleum Corp", ["Anadarko Petroleum Corporation"], "APC")
    sec = {"ciks": {1}, "cik_names": {1: ["Meta Platforms, Inc.", "Facebook Inc"]}}
    rel = {"rows": {"META": ("Roundhill Ball Metaverse ETF", "NMS", 1e5, 1e4, 0.0, False, False, 1)}}
    assert M.issuer_si(rel, sec, {"META"}) == {}


def test_dollar_volume_uses_only_the_window_ending_at_the_decision_row():
    rng = np.random.default_rng(1)
    C = rng.uniform(10, 50, (200, 6)); V = rng.uniform(1e5, 1e6, (200, 6))
    i = 120
    dv = M.dollar_volume(C, V, i)
    C2, V2 = C.copy(), V.copy()
    C2[i + 1:] *= 5.0; V2[i + 1:] *= 0.1
    assert np.allclose(dv, M.dollar_volume(C2, V2, i))
    assert np.allclose(dv, np.median(C[i - 59:i + 1] * V[i - 59:i + 1], axis=0))
    C3 = C.copy(); C3[: i - 59] *= 100.0
    assert np.allclose(dv, M.dollar_volume(C3, V, i))
    V4 = V.copy(); V4[i - 40:, 0] = np.nan                   # 19 bars left in the window: below the 30-bar minimum
    assert np.isnan(M.dollar_volume(C, V4, i)[0])


def test_identity_rule():
    assert M.ident_ok("A.O. Smith Corporation", ["A. O. Smith Corporation", "SMITH A O CORP"], "AOS")
    assert M.ident_ok("The J.M. Smucker Company", ["The J. M. Smucker Company"], "SJM")
    assert not M.ident_ok("BB&T Corporation", ["Beacon Financial Corporation", "Beacon Financial Corp"], "BBT")
    assert M.ident_ok("Apple Inc. Common Stock", ["Apple Inc."], "AAPL")


def _si_world(n_days: int = 160):
    """A synthetic world: three member stocks, monthly FINRA releases, SEC dei shares, splits, prices."""
    days = _bdays("2024-01-02", n_days)
    cal = SX.Cal(days)
    rng = np.random.default_rng(3)
    S = 3
    C = rng.uniform(20, 80, (n_days, S)); V = rng.uniform(1e5, 1e6, (n_days, S))
    A = np.cumprod(1 + rng.normal(0, 0.01, (n_days, S)), axis=0) * 50
    pr = {"cal": cal, "col": {"AAA": 0, "BBB": 1, "CCC": 2}, "C": C, "V": V, "real": np.isfinite(C), "Af": A,
          "splits": {"AAA": [("2024-03-11", 2.0)], "BBB": [], "CCC": []}}
    names = {"AAA": "Aaa Corp", "BBB": "Bbb Inc", "CCC": "Ccc Co"}
    facts = {1: [_fact(1e8, "2024-01-15", "x1", _epoch("2024-01-20"))],
             2: [_fact(5e8, "2024-01-15", "y1", _epoch("2024-01-20"))],
             3: [_fact(2e8, "2024-01-15", "z1", _epoch("2024-01-20"))]}
    sec = {"tick": {"AAA": (1, names["AAA"]), "BBB": (2, names["BBB"]), "CCC": (3, names["CCC"])}, "ciks": {1, 2, 3},
           "ser": {k: M.share_series(v) for k, v in facts.items()},
           "sym_names": {s: [names[s]] for s in names}, "cik_names": {1: [names["AAA"]], 2: [names["BBB"]], 3: [names["CCC"]]},
           "cik_sym": {1: "AAA", 2: "BBB", 3: "CCC"}}
    rels = []
    for k, settle in enumerate(["2024-02-15", "2024-02-29", "2024-03-15", "2024-03-28", "2024-04-15", "2024-04-30"]):
        av = _epoch(_bdays(settle, 10)[8])
        rows = {s: (names[s], "NYSE", float(1e6 * (j + 1) * (2.0 if (s == "AAA" and settle >= "2024-03-11") else 1.0)
                                          * (1 + 0.1 * k)), 5e5, 3.0, False, False, j + 1)
                for j, s in enumerate(("AAA", "BBB", "CCC"))}
        rels.append({"settle": settle, "av": av, "rows": rows})
    snaps = [(EV._ed("2023-06-01"), frozenset({"AAA", "BBB", "CCC"}))]
    return pr, sec, facts, rels, snaps


def test_t675_member_signal_ignores_everything_after_the_decision():
    pr, sec, facts, rels, snaps = _si_world()
    mem_f = {"AAA", "BBB", "CCC"}
    B = M.build_sir(pr, sec, copy.deepcopy(rels), mem_f)
    r = 3                                                    # the 2024-03-28 release (after AAA's 2:1 split)
    f = M.member_rows(B, r, snaps)
    e, q = f["e"], f["q"]
    assert f["cnt"]["covered"] == 3 and e == pr["cal"].entry_after(rels[r]["av"])
    # AAA: SI doubled by the split, cover shares restated by it: the SIR does not jump
    assert f["sir"][0] == pytest.approx(B["SIR"][1, B["kc"][1]] * (1.3 / 1.1), rel=1e-9)
    # (1) prices and volumes after the previous close q
    pr2 = copy.deepcopy(pr)
    pr2["C"][q + 1:] *= 4.0; pr2["V"][q + 1:] *= 0.2
    f2 = M.member_rows(M.build_sir(pr2, sec, copy.deepcopy(rels), mem_f), r, snaps)
    for k in ("sir", "dtc", "mcap", "dv"):
        assert np.allclose(f[k], f2[k]), k
    # (2) SEC facts accepted after the entry open
    tau = float(pr["cal"].open[e])
    sec3 = copy.deepcopy(sec)
    sec3["ser"][1] = M.share_series(facts[1] + [_fact(9e9, "2024-04-01", "x9", tau + 60.0)])
    f3 = M.member_rows(M.build_sir(pr, sec3, copy.deepcopy(rels), mem_f), r, snaps)
    assert np.allclose(f["sir"], f3["sir"]) and np.allclose(f["mcap"], f3["mcap"])
    sec3b = copy.deepcopy(sec)
    sec3b["ser"][1] = M.share_series(facts[1] + [_fact(9e9, "2024-03-25", "x8", tau - 3600.0)])
    assert not np.allclose(f["sir"], M.member_rows(M.build_sir(pr, sec3b, copy.deepcopy(rels), mem_f), r, snaps)["sir"])
    # (3) a split after the settlement date
    pr4 = copy.deepcopy(pr)
    pr4["splits"]["BBB"] = [("2024-04-02", 3.0)]
    f4 = M.member_rows(M.build_sir(pr4, sec, copy.deepcopy(rels), mem_f), r, snaps)
    assert np.allclose(f["sir"], f4["sir"])
    # (4) later releases
    rels5 = copy.deepcopy(rels)
    for rr in rels5[r + 1:]:
        rr["rows"] = {s: (v[0], v[1], v[2] * 50.0, *v[3:]) for s, v in rr["rows"].items()}
    B5 = M.build_sir(pr, sec, rels5, mem_f)
    assert np.allclose(f["sir"], M.member_rows(B5, r, snaps)["sir"])
    assert np.allclose(M.susi_at(B["SIR"], r, look=3, min_hist=3), M.susi_at(B5["SIR"], r, look=3, min_hist=3),
                       equal_nan=True)


def test_t675_member_with_a_foreign_yahoo_series_is_absent():
    pr, sec, facts, rels, snaps = _si_world()
    rels = copy.deepcopy(rels)
    for rr in rels:
        v = rr["rows"]["CCC"]
        rr["rows"]["CCC"] = ("Zzyzx Mining Ltd", *v[1:])
    B = M.build_sir(pr, sec, rels, {"AAA", "BBB", "CCC"})
    f = M.member_rows(B, 3, snaps)
    assert f["cnt"]["absent"] == 1 and f["absent"] == ["CCC"] and f["cnt"]["covered"] == 2


def test_top_half_and_quintile():
    dv = np.array([5.0, 1.0, 4.0, 3.0, 2.0, np.nan])
    th = M.top_half(dv, np.ones(6, bool))
    assert th.tolist() == [True, False, True, False, False, False]


# ================================================================================================= books ==

def test_leg_track_returns_turnover_and_drift():
    Af = np.array([[1.0, 1.0], [1.1, 1.0], [1.21, 0.5], [1.21, 0.5]])
    periods = [(0, 2), (2, 3)]
    legs = [(np.array([0, 1]), np.array([0.5, 0.5])), (np.array([0]), np.array([1.0]))]
    t = M.leg_track(periods, legs, Af, daily=True)
    assert t["R"][0] == pytest.approx(0.5 * 0.21 + 0.5 * (-0.5))
    assert t["TO"][0] == pytest.approx(1.0)
    w0 = 0.5 * 1.21 / (1 + t["R"][0])
    assert t["TO"][1] == pytest.approx(abs(1.0 - w0) + (1 - w0))
    assert t["exit"] == pytest.approx(1.0)
    assert np.allclose(np.prod(1 + t["daily"][0]) - 1, t["R"][0])
    # values after the exit do not move the period return
    Af2 = Af.copy(); Af2[3] *= 7.0
    assert M.leg_track([(0, 2)], legs[:1], Af2)["R"][0] == pytest.approx(t["R"][0])


def test_absent_weight_readings_and_tipping():
    w = M.ls_absent_weights([100, 100], [10, 0], [90, 100], 10)
    assert w["P"].tolist() == pytest.approx([0.1, 0.0])
    assert w["W"].tolist() == pytest.approx([1.0, 0.0])     # 10 absent fill the whole 10-name decile at worst
    rng = np.random.default_rng(5)
    x = rng.normal(0.01, 0.01, 200)
    ww = np.full(200, 0.2)
    r = M.tipping_value(lambda rr: (1 - ww) * x + ww * rr, 6)
    assert M.hac_lb((1 - ww) * x + ww * r, 6) == pytest.approx(0.0, abs=1e-6)
    assert r < 0


# ================================================================================================= T-676 ==

def test_t676_window_ignores_file_days_after_minus_6():
    rng = np.random.default_rng(7)
    D, S = 200, 30
    SV = rng.uniform(2e5, 6e5, (D, S)); TV = np.full((D, S), 1e6)
    i0 = 150
    sig, cnt = M.window_svr(SV, TV, i0)
    assert np.allclose(sig, (SV[i0 - 65:i0 - 5] / TV[i0 - 65:i0 - 5]).mean(axis=0)) and (cnt == 60).all()
    SV2 = SV.copy(); SV2[i0 - 5:] *= 1.5; SV2[: i0 - 65] *= 0.1
    assert np.allclose(sig, M.window_svr(SV2, TV, i0)[0])
    SV3 = SV.copy(); SV3[i0 - 6] *= 1.5
    assert not np.allclose(sig, M.window_svr(SV3, TV, i0)[0])
    TV4 = TV.copy(); TV4[i0 - 65:i0 - 44, 0] = 0.0           # 21 days absent: 39 present < 40
    assert np.isnan(M.window_svr(SV, TV4, i0)[0][0]) and np.isfinite(M.window_svr(SV, TV4, i0)[0][1])


def test_resid_on_is_orthogonal_to_size():
    rng = np.random.default_rng(8)
    z = rng.normal(size=300); x = 0.3 * z + rng.normal(size=300)
    m = np.ones(300, bool); m[:10] = False
    e = M.resid_on(x, z, m)
    assert np.isnan(e[:10]).all()
    assert abs(np.corrcoef(e[m], z[m])[0, 1]) < 1e-10 and abs(e[m].mean()) < 1e-10


def _svr_world():
    days = _bdays("2018-06-01", 400)
    cal = SX.Cal(days)
    rng = np.random.default_rng(9)
    S = 25
    C = rng.uniform(20, 80, (len(days), S)); V = rng.uniform(1e5, 1e6, (len(days), S))
    A = np.cumprod(1 + rng.normal(0, 0.01, (len(days), S)), axis=0)
    pr = {"cal": cal, "C": C, "V": V, "real": np.isfinite(C), "Af": A}
    fd = np.array([EV._ed(d) for d in days], np.int64)
    syms = [f"S{k:02d}" for k in range(S)]
    Cn = {"days": fd, "SV": rng.uniform(2e5, 6e5, (len(days), S)), "TV": np.full((len(days), S), 1e6), "syms": syms,
          "backfilled": np.zeros(len(days), bool)}
    Bc = {"C": Cn, "pj": np.arange(S), "idok": np.ones(S, bool)}
    snaps = [(EV._ed("2018-01-01"), frozenset(syms))]
    return pr, Bc, snaps


def test_t676_formation_legs_ignore_everything_after_the_month_end_close():
    pr, Bc, snaps = _svr_world()
    m = M.month_ends(pr["cal"].days)[5]
    f = M.svr_formation(Bc, pr, snaps, m)
    assert f["n"] == 25 and f["k"] == 5 and f["e"] == m + 1 and f["x"] == m + 22
    i0 = int(np.searchsorted(Bc["C"]["days"], EV._ed(pr["cal"].days[m]), side="right")) - 1
    Bc2 = copy.deepcopy(Bc); pr2 = copy.deepcopy(pr)
    Bc2["C"]["SV"][i0 - 5:] *= 2.0
    pr2["C"][m + 1:] *= 3.0; pr2["V"][m + 1:] *= 0.3; pr2["Af"][m + 2:] *= np.linspace(0.5, 2.0, 25)
    f2 = M.svr_formation(Bc2, pr2, snaps, m)
    assert np.allclose(f["fl"], f2["fl"]) and np.allclose(f["fs"], f2["fs"]) and np.allclose(f["dv"], f2["dv"], equal_nan=True)
    assert not np.allclose(f["r"], f2["r"])                  # the outcome moves, the decision does not
    # a member without a usable price is counted absent, not dropped silently
    Bc3 = copy.deepcopy(Bc); Bc3["idok"][0] = False
    f3 = M.svr_formation(Bc3, pr, snaps, m)
    assert f3["absent"] == 1 and f3["n"] == 24
    c = M.ls_cohort(f)
    assert c["gross"] == pytest.approx(c["RL"] - c["RS"])


def test_month_ends():
    assert M.month_ends(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-29", "2024-03-01"]) == [1, 3]


# ================================================================================================= T-677 ==

def test_t677_susi_ignores_later_releases_and_needs_20_of_24():
    rng = np.random.default_rng(11)
    S = rng.uniform(0.01, 0.05, (60, 40))
    t = 40
    z = M.susi_at(S, t)
    H = S[t - 24:t]
    assert np.allclose(z, (S[t] - H.mean(axis=0)) / H.std(axis=0, ddof=1))
    S2 = S.copy(); S2[t + 1:] *= 10.0
    assert np.allclose(z, M.susi_at(S2, t))
    S3 = S.copy(); S3[t, 0] *= 3.0
    assert M.susi_at(S3, t)[0] != pytest.approx(z[0])
    S4 = S.copy(); S4[t - 24:t - 19, 0] = np.nan             # 19 of the prior 24 present
    S4[t - 24:t - 20, 1] = np.nan                            # 20 present
    z4 = M.susi_at(S4, t)
    assert np.isnan(z4[0]) and np.isfinite(z4[1])


# ================================================================================================= contract ==

@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_harness_inconclusive_when_bundles_missing(name):
    stat, n, verdict, reason = M.HARNESSES[name](EmptyArchive())
    assert verdict == "inconclusive" and n == 0
    assert "missing" in reason
    assert stat.get("missing_bundles")


def test_theory_map_names_harnesses():
    assert set(M.THEORY_MAP) == {"T-675", "T-676", "T-677"}
    for tid, h in M.THEORY_MAP.items():
        assert h in M.HARNESSES and M.HARNESSES[h].__doc__.strip().rstrip(".") == tid


def test_implausible_sir_is_a_missing_cover_value():
    pr, sec, facts, rels, snaps = _si_world()
    rels = copy.deepcopy(rels)
    v = rels[3]["rows"]["BBB"]
    rels[3]["rows"]["BBB"] = (v[0], v[1], 0.0, *v[3:])                 # a zero FINRA position on a member
    sec = copy.deepcopy(sec)
    sec["ser"][3] = M.share_series([_fact(1e3, "2024-01-15", "z1", _epoch("2024-01-20"))])   # cover count 1,000: SIR >> 1
    B = M.build_sir(pr, sec, rels, {"AAA", "BBB", "CCC"})
    f = M.member_rows(B, 3, snaps)
    assert f["cnt"]["bad_sir"] == 2 and f["sym"].tolist() == ["AAA"]
    assert np.isnan(B["SIR"][3, B["kc"][2]]) and np.isnan(B["SIR"][0, B["kc"][3]])
