"""Batch-6b volh harness (T-250, implied minus realised cross-sector correlation of SPY and the nine SPDR sectors) on
synthetic data only. The core judge passes a planted correlation premium and fails a null; the formula, NNLS weights,
anchor drift, realised vols, snapshot dedupe, rule-10 chains, the studentized bounds, the iv tenor check, the hv
alignment check, rule 5 and the weights data limit are checked directly; the harness runs on a fake archive (JSON-safe
stat, reason ending with the verdict explanation, missing bundles -> inconclusive). No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.data.dolt_options import is_trading_day
from mandel.experiments import batch6b_volh as v

NB = 200                                # bootstrap resamples in tests


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(v, "N_BOOT", NB)
    yield


class FakeArchive:
    def __init__(self, bundles, created="2030-01-01T00:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


def _sessions(start: str, n: int) -> list:
    out, x = [], date.fromisoformat(start)
    while len(out) < n:
        if is_trading_day(x):
            out.append(x.isoformat())
        x += timedelta(days=1)
    return out


W_TRUE, _ = v.anchor_vector(v.ANCHORS["2019-12-31"])
SIG = np.linspace(0.14, 0.32, 9)


def _market(T, rho=0.5, seed=0, start="2018-01-02", w=W_TRUE):
    """Nine sectors with constant pairwise correlation ``rho`` and vols SIG; the index = sum w_i r_i every day."""
    days = _sessions(start, T)
    rng = np.random.default_rng(seed)
    C = rho * np.ones((9, 9)) + (1 - rho) * np.eye(9)
    z = rng.standard_normal((T - 1, 9)) @ np.linalg.cholesky(C).T
    r = z * SIG / math.sqrt(252)
    lr = np.column_stack([r @ w, r])
    px = 100.0 * np.exp(np.vstack([np.zeros(10), np.cumsum(lr, axis=0)]))
    return days, px


def _index_iv(rho, w=W_TRUE, sig=SIG):
    ws = w * sig
    own = float(np.sum(ws * ws))
    return math.sqrt(own + rho * (float(np.sum(ws)) ** 2 - own))


def _entries(days, first, last, premium, rho=0.5, step=1):
    iv = np.concatenate([[_index_iv(rho + premium)], SIG])
    return [{"quote_date": d, "snapshot_date": d, "available_at": d + "T22:00:00+00:00", "iv": iv.copy()}
            for d in days[first:last:step]]


# ---------------------------------------------------------------------------------------------- formula and weights --

def test_implied_corr_recovers_planted_rho_and_rejects_bad_denominator():
    for rho in (0.2, 0.5, 0.9):
        got = v.implied_corr(_index_iv(rho), SIG[None, :], W_TRUE[None, :])
        assert got[0] == pytest.approx(rho, abs=1e-12)
    # null: a single non-zero weight leaves no cross term -> NaN, never a number
    w = np.zeros(9)
    w[0] = 1.0
    assert np.isnan(v.implied_corr(0.2, SIG[None, :], w[None, :])[0])


def test_nnls_recovers_nonnegative_weights_and_clips_a_negative_one():
    rng = np.random.default_rng(1)
    X = rng.standard_normal((300, 5))
    b = np.array([0.4, 0.0, 0.3, 0.2, 0.1])
    got = v.nnls(X, X @ b + 1e-4 * rng.standard_normal(300))
    assert np.allclose(got, b, atol=1e-3) and (got >= 0).all()
    b2 = np.array([0.5, -0.3, 0.2, 0.0, 0.0])
    got2 = v.nnls(X, X @ b2)
    assert (got2 >= 0).all() and got2[1] == 0.0
    assert not np.allclose(got2, b2, atol=1e-2)


def test_regression_weights_recover_planted_index_weights_and_not_equal_weights():
    days, px = _market(400, seed=2)
    lr = np.diff(np.log(px), axis=0)
    w = v.regression_weights(lr[-252:, 0], lr[-252:, 1:])
    assert w.sum() == pytest.approx(1.0) and np.allclose(w, W_TRUE, atol=1e-8)
    assert not np.allclose(w, np.full(9, 1 / 9), atol=0.02)


def test_drift_weights_follow_price_relatives():
    w0 = np.full(9, 1 / 9)
    p0 = np.ones(9)
    p1 = np.ones(9)
    p1[0] = 2.0
    w1 = v.drift_weights(w0, p0, p1)
    assert w1[0] == pytest.approx(2 / 10) and w1.sum() == pytest.approx(1.0)
    assert np.allclose(v.drift_weights(w0, p0, p0), w0)          # null: no price move, no drift


def test_weight_schemes_judged_and_reported_sets():
    days, px = _market(700, seed=3)
    sess = np.arange(300, 650, 10)
    judged, reported, info = v.weight_schemes(days, px, px, sess)
    assert list(judged)[0] == "anchor_nearest" and {"anchor_2019", "anchor_2024", "regression_pit"} <= set(judged)
    assert np.allclose(judged["regression_pit"], W_TRUE[None, :], atol=1e-6)
    assert np.allclose(judged["anchor_2019"].sum(axis=1), 1.0)
    assert np.allclose(reported["anchor_nearest_unnormalised"].sum(axis=1), info["anchors"]["2019-12-31"]["nine_sector_share"])
    # the 2019 anchor is exact at its own session
    i = days.index("2019-12-31")
    w_at = v.weight_schemes(days, px, px, np.array([i]))[0]["anchor_2019"][0]
    assert np.allclose(w_at, W_TRUE)


def test_realised_vols_zero_mean_and_demeaned():
    lr = np.zeros((40, 2))
    lr[:, 0] = 0.01
    lr[::2, 1] = 0.02
    lr[1::2, 1] = -0.02
    z = v.realised_vols(lr, np.array([0]), hold=20)
    d = v.realised_vols(lr, np.array([0]), hold=20, demean=True)
    assert z[0, 0] == pytest.approx(0.01 * math.sqrt(252)) and d[0, 0] == pytest.approx(0.0, abs=1e-12)
    assert z[0, 1] == pytest.approx(0.02 * math.sqrt(252))
    assert d[0, 1] == pytest.approx(math.sqrt(20 * 0.0004 / 19 * 252))


def test_pairwise_realised_matches_planted_correlation():
    days, px = _market(2000, rho=0.6, seed=4)
    lr = np.diff(np.log(px), axis=0)
    got = v.pairwise_realised(lr, np.array([0]), np.array([W_TRUE]), hold=1990)
    assert got[0] == pytest.approx(0.6, abs=0.04)
    days0, px0 = _market(2000, rho=0.0, seed=4)
    got0 = v.pairwise_realised(np.diff(np.log(px0), axis=0), np.array([0]), np.array([W_TRUE]), hold=1990)
    assert abs(got0[0]) < 0.05


# ----------------------------------------------------------------------------------------------------- statistics --

def test_stud_bounds_planted_mean_clears_margin_and_null_does_not():
    rng = np.random.default_rng(5)
    x = 0.12 + 0.05 * rng.standard_normal(200)
    b = v.stud_bounds(x, np.ones(200), 4, n_boot=NB)
    assert b["lower"] > 0.05 and b["lower"] < b["mean"] < b["upper"]
    assert b["ci95"][0] < b["lower"]
    x0 = 0.05 * rng.standard_normal(200)
    b0 = v.stud_bounds(x0, np.ones(200), 4, n_boot=NB)
    assert b0["lower"] < 0.05 and b0["upper"] < 0.05
    assert v.stud_bounds(x0[:5], np.ones(5), 2) is None


def test_week_clusters_count_each_week_once():
    days = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-15"]
    S, N = v.week_clusters(days, [1.0, 2.0, 3.0, 10.0], "week")
    assert list(N) == [1.0, 0.0, 1.0] and list(S) == [2.0, 0.0, 10.0]
    S2, N2 = v.week_clusters(days, [1.0, 2.0, 3.0, 10.0], "entry")
    assert list(N2) == [3.0, 0.0, 1.0] and list(S2) == [6.0, 0.0, 10.0]


def test_grid_chains_are_non_overlapping_one_per_start():
    sess = [0, 2, 5, 9, 21, 23, 30, 42, 44, 63, 70]
    chains = v.grid_chains(sess, hold=21)
    assert len(chains) == 4                                         # entries at sessions 0, 2, 5, 9
    for ch in chains:
        s = [sess[p] for p in ch]
        assert all(b - a >= 21 for a, b in zip(s, s[1:]))
    assert [sess[p] for p in chains[0]] == [0, 21, 42, 63]
    assert [sess[p] for p in chains[3]] == [9, 30, 63]


def test_decide_rule5_below_min_n_only_decisive_failures_count():
    verdict, _ = v._decide([("mean", False, False)], 10, 36, "cycles")
    assert verdict == "inconclusive"
    verdict, _ = v._decide([("mean", False, True)], 10, 36, "cycles")
    assert verdict == "not_supported"
    verdict, _ = v._decide([("mean", True, False)], 10, 36, "cycles")
    assert verdict == "inconclusive"
    verdict, _ = v._decide([("mean", True, False), ("weights", None, False)], 40, 36, "cycles")
    assert verdict == "inconclusive"


# ---------------------------------------------------------------------------------------------------- the core test --

def _core(premium, T=1200, seed=6, weights_pit=True, first=260, step=1, w=W_TRUE, **kw):
    days, px = _market(T, seed=seed)
    ent = _entries(days, first, T, premium, step=step)
    E = len(ent)
    weights = {"true": np.tile(w, (E, 1)), "true_copy": np.tile(w, (E, 1))}
    return v.premium_test(days, px, px, ent, weights, {"equal": np.full((E, 9), 1 / 9)}, weights_pit=weights_pit, **kw)


def test_premium_test_planted_premium_supported():
    r = _core(0.15)
    assert r["n"] >= v.MIN_N
    assert r["schemes"]["true"]["pooled"]["mean"] == pytest.approx(0.15, abs=0.04)
    assert r["criterion_mean_ok"] is True
    assert r["verdict"] == "supported", r["reason"]
    assert r["reason"].endswith(" — " + r["why"])
    json.dumps(v._clean(r))


def test_premium_test_null_premium_not_supported():
    r = _core(0.0)
    assert r["n"] >= v.MIN_N
    assert abs(r["schemes"]["true"]["pooled"]["mean"]) < 0.04
    assert r["criterion_mean_ok"] is False
    assert r["verdict"] == "not_supported", r["reason"]


def test_premium_test_weights_data_limit_caps_a_planted_premium():
    r = _core(0.15, weights_pit=False, weights_note="approximate weights")
    assert r["criterion_mean_ok"] is True
    assert r["verdict"] == "inconclusive" and "point-in-time SPY sector weights" in r["why"]


def test_premium_test_schemes_must_agree():
    days, px = _market(1200, seed=7)
    ent = _entries(days, 260, 1200, 0.15)
    E = len(ent)
    # the second scheme has one weight on a single sector: the cross term vanishes -> no valid entries -> undecided
    w_bad = np.zeros((E, 9))
    w_bad[:, 0] = 1.0
    r = v.premium_test(days, px, px, ent, {"true": np.tile(W_TRUE, (E, 1)), "bad": w_bad}, weights_pit=True)
    assert r["criterion_mean_ok"] is None and r["verdict"] == "inconclusive"


def test_robust_needs_every_variant():
    assert v._robust([True, True]) is True and v._robust([False, False]) is False
    assert v._robust([True, False]) is None and v._robust([True, None]) is None and v._robust([]) is None


def test_premium_test_below_min_n_is_never_supported():
    r = _core(0.15, T=600)
    assert r["n"] < v.MIN_N and r["verdict"] == "inconclusive"
    r0 = _core(0.04, T=600)
    assert r0["verdict"] in ("inconclusive", "not_supported") and r0["verdict"] != "supported"


def test_premium_test_reports_controls():
    days, px = _market(1200, seed=8)
    vix = {d: (35.0 if d.startswith("2020-03") else 15.0 + (i % 7)) for i, d in enumerate(days)}
    cor = {d: 30.0 + (i % 11) for i, d in enumerate(days)}
    ent = _entries(days, 260, 1200, 0.1)
    E = len(ent)
    r = v.premium_test(days, px, px, ent, {"true": np.tile(W_TRUE, (E, 1))}, weights_pit=True, vix=vix, cor1m=cor)
    assert "2020-03" in r["months"]["crisis_months"] and r["months"]["share_noncrisis_positive"] is not None
    assert r["vix_terciles"] and len(r["vix_terciles"]) == 3
    assert r["cor1m"]["n"] > 100 and r["walk_forward"] is not None
    assert r["strict_pit"]["n_entries"] == r["schemes"]["true"]["n_valid"]       # no weekend snapshots here
    assert set(r["sensitivities"]) == {"demeaned", "raw_close"}


# ---------------------------------------------------------------------------------------- snapshots and diagnostics --

def _vol_row(sym, sd, q, iv, hv=0.2, stale=False, avail=None):
    return {"available_at": avail or (max(sd, q) + "T22:00:00+00:00"),
            "value": {"symbol": sym, "snapshot_date": sd, "quote_date": q, "iv_current": iv, "hv_current": hv,
                      "stale": stale}}


def test_snapshots_dedupe_and_drop_rules():
    rows = []
    for s in v.SYMS:
        rows.append(_vol_row(s, "2024-03-01", "2024-03-01", 0.2))           # Friday, kept
        rows.append(_vol_row(s, "2024-03-02", "2024-03-01", 0.3))           # Saturday quoting Friday: duplicate
        rows.append(_vol_row(s, "2024-03-04", "2024-03-04", None if s == "XLU" else 0.2))   # missing IV
        rows.append(_vol_row(s, "2024-03-05", "2024-03-04" if s == "XLB" else "2024-03-05", 0.2,
                             stale=(s == "XLB")))                          # mixed quote dates
        rows.append(_vol_row(s, "2024-03-06", "2024-03-06", 0.2, avail="2031-01-01T00:00:00+00:00"))  # after capture
    snaps, info = v.snapshots(rows, created="2030-01-01T00:00:00+00:00")
    assert list(snaps) == ["2024-03-01"] and snaps["2024-03-01"]["iv"][0] == 0.2
    assert info["duplicate_quote_day_dropped"] == 1 and info["missing_iv"] == 1 and info["mixed_quote_dates"] == 1
    assert info["rows_after_capture"] == 10


BASE_IV = np.array([0.12, 0.20, 0.30, 0.18, 0.16, 0.17, 0.11, 0.14, 0.13, 0.19])      # SPY first, then the nine


def _iv_rows(levels):
    """dolt-volhistory rows for consecutive sessions from {offset: (10,) iv vector}."""
    days = _sessions("2024-03-04", len(levels))
    rows = []
    for d, iv in zip(days, levels):
        for j, s in enumerate(v.SYMS):
            rows.append(_vol_row(s, d, d, float(iv[j])))
    return days, rows


def test_iv_screen_drops_one_symbol_glitches_and_keeps_market_wide_moves():
    # regression (T-250 review): XLK 2021-11-03 iv_current 1.2518 between 0.165 and 0.1885 was kept in the judged sample
    k, xv = v.SYMS.index("XLK"), v.SYMS.index("XLV")
    lv = [BASE_IV * (1 + 0.03 * (i % 3)) for i in range(10)]
    lv[4] = lv[4].copy()
    lv[4][k] *= 7.5                                              # planted one-symbol spike that reverts next snapshot
    for i in (6, 7, 8, 9):
        lv[i] = lv[i] * 2.5                                      # market-wide jump (a Covid-like onset): genuine
    lv[8] = lv[8].copy()
    lv[8][xv] *= 0.3                                             # planted one-symbol collapse
    days, rows = _iv_rows(lv)
    snaps, info = v.snapshots(rows)
    assert days[4] not in snaps and days[8] not in snaps
    assert all(d in snaps for d in days[:4] + days[5:8] + days[9:])         # the reversion and the market jump stay
    assert info["iv_glitch_dropped"] == 2 and info["used"] == 8
    assert [(g["quote_date"], g["symbol"]) for g in info["iv_glitches"]] == [(days[4], "XLK"), (days[8], "XLV")]
    g = info["iv_glitches"][0]
    assert g["relative_move"] > 7 and g["ref"] == pytest.approx(BASE_IV[k] * 1.03)
    raw, info_raw = v.snapshots(rows, screen=False)               # the as-is sensitivity keeps them
    assert len(raw) == 10 and info_raw["iv_glitch_kept"] == 2 and info_raw["iv_glitches"] == info["iv_glitches"]


def test_iv_screen_null_keeps_moves_below_the_threshold():
    rng = np.random.default_rng(12)
    lv = [BASE_IV * np.exp(0.05 * rng.standard_normal(10)) for _ in range(30)]
    lv[10] = lv[10].copy()
    lv[10][3] = 1.7 * np.median(np.array(lv[7:10]), axis=0)[3]   # a 1.7x one-symbol move is not a glitch
    for i in range(20, 30):
        lv[i] = lv[i] * 3.0                                       # a 3x market-wide jump is not a glitch
    days, rows = _iv_rows(lv)
    snaps, info = v.snapshots(rows)
    assert len(snaps) == 30 and info["iv_glitch_dropped"] == 0 and info["iv_glitches"] == []
    largest = info["iv_screen_largest_kept"]
    assert largest["quote_date"] == days[10] and largest["symbol"] == v.SYMS[3] and 1.6 < largest["relative_move"] < 2


def test_iv_screen_level_shift_is_flagged_only_until_it_persists():
    e = v.SYMS.index("XLE")
    lv = [BASE_IV.copy() for _ in range(12)]
    for i in range(5, 12):
        lv[i] = lv[i].copy()
        lv[i][e] *= 3.0                                           # a persistent 3x shift of one symbol
    days, rows = _iv_rows(lv)
    snaps, info = v.snapshots(rows)
    assert [g["quote_date"] for g in info["iv_glitches"]] == days[5:5 + v.IV_SCREEN_PREV]
    assert all(d in snaps for d in days[5 + v.IV_SCREEN_PREV:])   # then it is the symbol's reference level


def test_iv_screen_is_point_in_time():
    k = v.SYMS.index("XLK")
    lv = [BASE_IV.copy() for _ in range(8)]
    lv[7] = lv[7].copy()
    lv[7][k] *= 6.0                                               # a spike on the LAST snapshot needs no later data
    days, rows = _iv_rows(lv)
    snaps, info = v.snapshots(rows)
    assert days[7] not in snaps and info["iv_glitch_dropped"] == 1
    # earlier flags do not depend on later snapshots
    lv2 = [x.copy() for x in lv]
    lv2[3][k] *= 5.0
    days2, rows2 = _iv_rows(lv2)
    full = [(g["quote_date"], g["symbol"]) for g in v.snapshots(rows2)[1]["iv_glitches"]]
    cut = [(g["quote_date"], g["symbol"]) for g in v.snapshots([r for r in rows2 if r["value"]["snapshot_date"] <= days2[3]])[1]["iv_glitches"]]
    assert cut == [(days2[3], "XLK")] and full[:1] == cut


def _chain_rows(sd, spot, term_fn, expiries):
    out = []
    for e in expiries:
        t = (date.fromisoformat(e) - date.fromisoformat(sd)).days
        for k in (spot - 5, spot, spot + 5):
            for typ in ("call", "put"):
                out.append({"value": {"snapshot_date": sd, "quote_date": sd, "expiry": e, "strike": k, "type": typ,
                                      "iv": term_fn(t)}})
    return out


def test_iv_tenor_check_finds_the_planted_tenor_and_not_another():
    term = lambda t: 0.10 + 0.002 * t                                   # upward term structure
    rows, iv30, iv45, spot = [], {}, {}, {}
    for k, sd in enumerate(_sessions("2024-01-02", 30)):
        exps = [(date.fromisoformat(sd) + timedelta(days=d)).isoformat() for d in (12, 26, 40, 61)]
        rows += _chain_rows(sd, 100.0, term, exps)
        spot[sd] = 100.0
        tl = v.atm_term([(e, 100.0, term((date.fromisoformat(e) - date.fromisoformat(sd)).days)) for e in exps], 100.0, sd)
        iv30[sd] = v.interp_tenor(tl, 30)
        iv45[sd] = v.interp_tenor(tl, 45)
    got = v.iv_tenor_check(rows, iv30, spot)
    assert got["best"] == 30 and got["by_tenor"][30]["median_abs"] < 1e-9
    got45 = v.iv_tenor_check(rows, iv45, spot)
    assert got45["best"] == 45 and got45["best"] != 30


def test_hv_check_matches_planted_and_rejects_wrong_values():
    days, px = _market(100, seed=9)
    c = px[:, 0]
    good, bad = {}, {}
    for i in range(40, 100, 5):
        h = float(np.std(np.diff(np.log(c[i - 30:i + 1])), ddof=1) * math.sqrt(252))
        good[days[i]] = round(h, 4)
        bad[days[i]] = round(h * 1.1, 4)
    assert v.hv_check(c, days, good)["share"] == 1.0
    assert v.hv_check(c, days, bad)["share"] == 0.0


# ------------------------------------------------------------------------------------------------------- harness --

def _bundles(premium, T=1250, seed=10, with_vix=True, mwf=True, glitch=None):
    """glitch: (session index, symbol, factor) planted on that snapshot's iv_current."""
    days, px = _market(T, seed=seed)
    b = {}
    for j, s in enumerate(v.SYMS):
        rows = []
        for i, d in enumerate(days):
            t = datetime.fromisoformat(d + "T14:30:00+00:00").timestamp()
            rows.append({"value": {"symbol": s, "t": t, "close": float(px[i, j]), "adjclose": float(px[i, j])}})
        b[v.CLOSE_B[s]] = rows
    iv = np.concatenate([[_index_iv(0.5 + premium)], SIG])
    vol = []
    for i, d in enumerate(days[260:], start=260):
        if mwf and date.fromisoformat(d).weekday() not in (0, 2, 4):
            continue
        for j, s in enumerate(v.SYMS):
            h = float(np.std(np.diff(np.log(px[i - 30:i + 1, j])), ddof=1) * math.sqrt(252))
            f = glitch[2] if glitch and glitch[0] == i and glitch[1] == s else 1.0
            vol.append(_vol_row(s, d, d, float(iv[j]) * f, hv=round(h, 4)))
    b[v.VOL_B] = vol
    if with_vix:
        b[v.VIX_B] = [{"value": {"day": d, "close": 18.0 + (i % 5)}} for i, d in enumerate(days)]
    return b


def test_harness_missing_bundles_inconclusive():
    stat, n, verdict, reason = v.b6b_volh_sector_corr_premium(FakeArchive({}))
    assert verdict == "inconclusive" and n == 0 and v.VOL_B in stat["missing_bundles"]
    assert reason.endswith("not implemented: every criterion (no data)")


def test_harness_planted_premium_capped_by_the_weights_data_limit():
    arc = FakeArchive(_bundles(0.15))
    stat, n, verdict, reason = v.b6b_volh_sector_corr_premium(arc)
    json.dumps(stat)
    assert n >= v.MIN_N
    assert stat["criterion_mean_ok"] is True
    assert verdict == "inconclusive" and "point-in-time SPY sector weights" in reason
    assert " — implemented criteria pass; not implemented: point-in-time SPY sector weights" in reason
    assert stat["hv_check"]["SPY"]["share"] == 1.0 and stat["weights_point_in_time"] is False
    assert stat["controls_available"] == {"VIX": True, "COR1M": False}


def test_harness_drops_a_planted_iv_glitch_and_reports_the_as_is_sensitivity():
    # regression (T-250 review): a one-symbol vendor IV spike must not enter the judged sample unnamed
    days = _sessions("2018-01-02", 1250)
    i = next(k for k in range(700, 720) if date.fromisoformat(days[k]).weekday() == 2)      # a Wednesday snapshot
    stat, n, verdict, reason = v.b6b_volh_sector_corr_premium(FakeArchive(_bundles(0.15, glitch=(i, "XLK", 12.0))))
    json.dumps(stat)
    si = stat["snapshot_info"]
    assert si["iv_glitch_dropped"] == 1 and [(g["quote_date"], g["symbol"]) for g in si["iv_glitches"]] == [(days[i], "XLK")]
    assert f"XLK {days[i]} iv_current" in reason and "as-is with the glitches kept (reported)" in reason
    asis = stat["as_is_before_iv_screen"]
    assert asis["n_entries"] == stat["n_entries"] + 1
    assert asis["rho_implied_outside_pm1"] >= 1 and stat["schemes"]["anchor_nearest"]["rho_implied_outside_pm1"] == 0
    assert asis["schemes"]["anchor_nearest"]["mean"] < stat["schemes"]["anchor_nearest"]["pooled"]["mean"]
    assert verdict == "inconclusive" and stat["criterion_mean_ok"] is True
    # null: without a glitch nothing is dropped and no as-is run is needed
    stat0, _, _, reason0 = v.b6b_volh_sector_corr_premium(FakeArchive(_bundles(0.15)))
    assert stat0["snapshot_info"]["iv_glitch_dropped"] == 0 and stat0["as_is_before_iv_screen"] is None
    assert "dropped 0 snapshot(s) with a vendor IV glitch" in reason0


def test_harness_null_premium_not_supported():
    arc = FakeArchive(_bundles(0.0, with_vix=False))
    stat, n, verdict, reason = v.b6b_volh_sector_corr_premium(arc)
    json.dumps(stat)
    assert n >= v.MIN_N and stat["criterion_mean_ok"] is False
    assert verdict == "not_supported" and reason.split(" — ")[-1].startswith("failed:")


def test_registry_maps():
    assert v.THEORY_MAP == {"T-250": "b6b_volh_sector_corr_premium"}
    assert set(v.HARNESSES) == set(v.THEORY_MAP.values())
    assert all(k.startswith("b6b_volh_") and k == k.lower() for k in v.HARNESSES)
