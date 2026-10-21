"""Synthetic tests for mandel.experiments.batch13_short_a (T-673, T-674, T-672): every signal built at a decision is
unchanged when values AFTER the decision are shocked, the statistics' series have the means they claim, and every
harness returns inconclusive (rule 9) on an archive whose get() raises KeyError. No network, no real archive."""

from __future__ import annotations

import math

import numpy as np
import pytest

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch13_short_a as M

VERDICTS = {"supported", "not_supported", "inconclusive"}


class EmptyArchive:
    """Stub archive: every bundle is missing."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self, kind=None, tag=None):
        return []


def _panel(rng, D=400, S=520):
    SV = rng.uniform(0.3, 0.6, (D, S)) * 1e6
    TV = np.full((D, S), 1e6) * rng.uniform(0.8, 1.2, (D, S))
    Mm = np.ones((D, S), bool)
    return SV, TV, Mm


# ================================================================================================ T-673 signal ==

def test_t673_ew_ratio_and_z_ignore_values_after_t():
    rng = np.random.default_rng(1)
    SV, TV, Mm = _panel(rng)
    x, cnt = M.ew_ratio(SV, TV, Mm)
    z = M.trailing_z(x, M.T673_WIN)
    t = 250
    SV2, TV2 = SV.copy(), TV.copy()
    SV2[t + 1:] *= 3.0
    TV2[t + 1:] *= 0.1
    x2, _ = M.ew_ratio(SV2, TV2, Mm)
    z2 = M.trailing_z(x2, M.T673_WIN)
    assert np.allclose(x[:t + 1], x2[:t + 1])
    assert np.allclose(z[:t + 1], z2[:t + 1], equal_nan=True)
    assert not np.allclose(x[t + 1:], x2[t + 1:])
    # z includes day t itself: shocking day t moves z_t
    SV3 = SV.copy(); SV3[t] *= 1.5
    x3, _ = M.ew_ratio(SV3, TV, Mm)
    assert M.trailing_z(x3, M.T673_WIN)[t] != pytest.approx(z[t])


def test_t673_member_floor_skips_day():
    rng = np.random.default_rng(2)
    SV, TV, Mm = _panel(rng, D=10, S=500)
    Mm[3, 60:] = False                    # 60 members only on day 3
    x, cnt = M.ew_ratio(SV, TV, Mm)
    assert cnt[3] == 60 and np.isnan(x[3]) and np.isfinite(x[2])


def test_t673_forward_target_starts_at_next_open():
    cal = np.arange(100, dtype=np.int64) + 18000
    opn = np.linspace(100, 120, 100)
    bills = CAL.Bills({"1990-01-01": 0.0})
    days = cal[:50]
    y, e0, e1, i = M.fwd_open_excess(days, cal, opn, bills, 10)
    assert e0[5] == 6 and e1[5] == 16
    assert y[5] == pytest.approx(opn[16] / opn[6] - 1.0)
    opn2 = opn.copy(); opn2[:6] = 1.0     # prices up to and including day t's own open do not enter
    y2, *_ = M.fwd_open_excess(days, cal, opn2, bills, 10)
    assert y2[5] == pytest.approx(y[5])


def test_slope_influence_series_mean_is_the_ols_slope():
    rng = np.random.default_rng(3)
    z = rng.normal(size=500); c = rng.normal(size=500)
    y = -0.3 * z + 0.2 * c + rng.normal(size=500)
    s = M.slope_psi(y, z, c)
    X = np.column_stack([np.ones(500), c, z])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    assert s["slope"] == pytest.approx(b[-1])
    assert s["psi"].mean() == pytest.approx(b[-1])
    t = M.slope_test(y, z, None, block=5, n_boot=300, escalate=False)
    assert t["slope"] < 0 and t["p_less"] < 0.05 and t["p_greater"] > 0.5


def test_stud_p_matches_house_bootstrap():
    from mandel.validation.backtest_eval import block_bootstrap_pvalue
    rng = np.random.default_rng(4)
    d = rng.normal(0.1, 1.0, 300)
    pg, pl = M.stud_p(d, 10, 1000, seed=7)
    ref = block_bootstrap_pvalue(d, np.zeros_like(d), n_boot=1000, block_len=10, seed=7)
    assert abs(pg - ref) < 0.03
    assert pg + pl == pytest.approx(1.0, abs=0.01)


# ================================================================================================ T-674 signal ==

def test_t674_dix_rank_and_dip_ignore_values_after_t():
    rng = np.random.default_rng(5)
    SV, TV, Mm = _panel(rng, D=600, S=50)
    P = rng.uniform(10, 200, (600, 50))
    x, share, npr = M.dw_ratio(SV, TV, Mm, P)
    f, dfd, rk = M.prior_pct_flag(x, M.T674_RANK_WIN, M.T674_PCT, upper=True)
    t = 400
    SV2, P2 = SV.copy(), P.copy()
    SV2[t + 1:] *= 2.0
    P2[t + 1:] *= rng.uniform(0.1, 10, (600 - t - 1, 50))
    x2, _, _ = M.dw_ratio(SV2, TV, Mm, P2)
    f2, dfd2, rk2 = M.prior_pct_flag(x2, M.T674_RANK_WIN, M.T674_PCT, upper=True)
    assert np.allclose(x[:t + 1], x2[:t + 1])
    assert (f[:t + 1] == f2[:t + 1]).all() and np.allclose(rk[:t + 1], rk2[:t + 1], equal_nan=True)
    assert not dfd[M.T674_RANK_WIN - 1] and dfd[M.T674_RANK_WIN]
    # the breakpoints exclude day t: x_t equal to the window max flags, the window is t-252..t-1
    w = x[t - M.T674_RANK_WIN:t]
    assert f[t] == (x[t] >= np.percentile(w, M.T674_PCT))
    # dip: SPY 5-day ratio vs the 252 sessions before t
    close = np.cumprod(1 + rng.normal(0, 0.01, 700))
    q = np.full(700, np.nan); q[5:] = close[5:] / close[:-5]
    d1, _, _ = M.prior_pct_flag(q, 252, 20.0, upper=False)
    c2 = close.copy(); c2[t + 1:] *= 0.5
    q2 = np.full(700, np.nan); q2[5:] = c2[5:] / c2[:-5]
    d2, _, _ = M.prior_pct_flag(q2, 252, 20.0, upper=False)
    assert (d1[:t + 1] == d2[:t + 1]).all()


def test_t674_unpriced_members_dropped_and_share_reported():
    SV = np.array([[50.0, 40.0]]); TV = np.array([[100.0, 100.0]]); Mm = np.ones((1, 2), bool)
    P = np.array([[10.0, np.nan]])
    x, share, npr = M.dw_ratio(SV, TV, Mm, P)
    assert x[0] == pytest.approx(0.5) and share[0] == pytest.approx(0.5) and npr[0] == 1


def test_t674_difference_series_have_the_differences_as_means():
    rng = np.random.default_rng(6)
    y = rng.normal(size=1000); s = rng.random(1000) < 0.2; d = rng.random(1000) < 0.2
    assert M.diff_all_series(y, s).mean() == pytest.approx(y[s].mean() - y.mean())
    assert M.diff_overlap_series(y, s, d).mean() == pytest.approx(y[s].mean() - y[d].mean())


def test_t674_as_traded_close_is_known_at_t_whatever_splits_follow():
    # Yahoo's split-adjusted close embeds every later split; close x factor-after-day must give back the price that
    # traded on the day, and a split announced after t (ex-date after t) must not move day t's as-traded price.
    iso = ["2020-01-02", "2020-06-01", "2021-01-04", "2022-01-03"]
    raw = np.array([100.0, 120.0, 50.0, 60.0])           # a 2:1 split with ex-date 2020-12-01
    splits = [("2020-12-01", 2.0)]
    adj = raw / M.after_split_factor(iso, splits)
    assert np.allclose(adj * M.after_split_factor(iso, splits), raw)
    late = splits + [("2021-06-01", 4.0)]                 # a later split rescales Yahoo's history again
    adj2 = raw / M.after_split_factor(iso, late)
    assert np.allclose(adj2 * M.after_split_factor(iso, late), raw)
    assert M.after_split_factor(iso, late)[:2].tolist() == [8.0, 8.0]
    # the DIX numerator/denominator at t then use only day-t prices and volumes
    SV = np.array([[50.0, 40.0]] * 4); TV = np.array([[100.0, 100.0]] * 4); Mm = np.ones((4, 2), bool)
    P = np.column_stack([raw, np.full(4, 30.0)])
    x, _, _ = M.dw_ratio(SV, TV, Mm, P)
    P2 = P.copy(); P2[2:, 0] *= 7.0
    x2, _, _ = M.dw_ratio(SV, TV, Mm, P2)
    assert np.allclose(x[:2], x2[:2]) and not np.allclose(x[2:], x2[2:])


def test_touches_window():
    cal = np.array([M.EV._ed(d) for d in ("2020-01-02", "2020-01-30", "2020-02-03", "2020-07-01", "2020-07-02")], np.int64)
    t = M.touches(np.array([0, 3, 0]), np.array([1, 4, 2]), cal, "2020-02-01", "2020-06-30")
    assert t.tolist() == [False, False, True]


# ================================================================================================ T-672 signal ==

def test_t672_detrended_index_at_r_ignores_later_releases():
    rng = np.random.default_rng(7)
    x = np.cumsum(rng.normal(size=150)) * 0.01 + np.linspace(0, 1, 150)
    r = 90
    x2 = x.copy(); x2[r + 1:] += 5.0
    zA, zA2 = M.detrend_z(x[:r + 1]), M.detrend_z(x2[:r + 1])
    assert np.allclose(zA, zA2)
    zB, zB2 = M.realtime_z(x), M.realtime_z(x2)
    assert np.allclose(zB[:r + 1], zB2[:r + 1], equal_nan=True)
    assert not np.allclose(zB[r + 1:], zB2[r + 1:])
    # the real-time value at s is the last element of the detrend over 1..s
    assert zB[r] == pytest.approx(M.detrend_z(x[:r + 1])[-1])


def test_t672_oos_uses_only_pairs_realised_before_the_decision():
    rng = np.random.default_rng(8)
    R = 120
    x = rng.normal(size=R); v = rng.normal(size=R); y = rng.normal(size=R) * 0.01
    av = np.arange(R, dtype=float) * 10.0
    real = av + 15.0                               # y_j realised 1.5 releases after its decision
    o = M.si_oos(x, v, y, av, real, "A", start=80)
    k0 = o["rec"][0]
    # shocking y at the origin and at the release whose y is not yet realised leaves the forecast unchanged
    y2 = y.copy(); y2[80] += 1.0; y2[79] += 1.0
    o2 = M.si_oos(x, v, y2, av, real, "A", start=80)
    assert o2["rec"][0][2:6] == pytest.approx(k0[2:6])
    y3 = y.copy(); y3[78] += 1.0                  # realised at 795 < av[80] = 800: it does enter
    o3 = M.si_oos(x, v, y3, av, real, "A", start=80)
    assert o3["rec"][0][2] != pytest.approx(k0[2])
    # x after the origin does not move the origin's forecast
    x4 = x.copy(); x4[81:] += 3.0
    o4 = M.si_oos(x4, v, y, av, real, "A", start=80)
    assert o4["rec"][0][2:6] == pytest.approx(k0[2:6])


def test_t672_regex_excludes_declared_classes():
    for nm in ("SPDR S&P 500 ETF Trust", "Vanguard Total Stock Mkt Fund", "Foo Acquisition Corp II", "Bar ADR",
               "Baz Corp Warrants", "Qux Units", "Rights to buy", "Big Bank Preferred", "Senior Notes 2030",
               "American Depositary Shs"):
        assert M.SI_EXCLUDE.search(nm), nm
    for nm in ("Agilent Technologies Inc.", "Alcoa Corporation", "Apple Inc."):
        assert not M.SI_EXCLUDE.search(nm), nm


class _Ent:
    def __init__(self, name):
        self.name, self.created_at, self.recipe = name, None, ""


class RowsArchive:
    """Stub archive serving in-memory rows per bundle."""

    def __init__(self, bundles):
        self.b = bundles

    def entries(self, kind=None, tag=None):
        return [_Ent(n) for n in self.b]

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Ent(name)

    def load(self, name):
        return iter(self.b[name])


def _si_row(sym, name, cls, si, adv, av="2026-10-12T23:59:59+00:00", rev=None):
    return {"kind": "short-interest", "available_at": av,
            "value": {"symbolCode": sym, "issueName": name, "marketClassCode": cls, "currentShortPositionQuantity": si,
                      "averageDailyVolumeQuantity": adv, "daysToCoverQuantity": 1.0, "revisionFlag": rev}}


def test_t672_universes_raw_fields_and_release_time():
    rows = [_si_row("AAA", "Alpha Corp", "NYSE", 50_000, 200_000),            # raw SI/ADV 0.25 (FINRA floors DTC at 1)
            _si_row("BBB", "Beta Inc", "NNM", 600_000, 200_000, rev="R"),
            _si_row("IBX", "iShares iBoxx $ Investment Gra", "ARCA", 900_000, 300_000),   # truncated fund name
            _si_row("SPY", "SPDR S&P 500 ETF Trust", "ARCA", 1e8, 5e7),        # regex removes it in both universes
            _si_row("TINY", "Tiny Corp", "NYSE", 10_000, 50_000),              # ADV below 100k
            _si_row("LATE", "Late Corp", "NYSE", 1.0, 200_000, av="2026-10-13T23:59:59+00:00")]
    M.CAL._CACHE.clear()
    recs = M.si_releases(RowsArchive({"finra-short-interest-2026-09-30": rows}))
    r = recs[0]
    assert r["n_all"] == 4 and r["n_company"] == 3 and r["n_norev"] == 3
    exp_company = np.mean([math.log1p(0.25), math.log1p(3.0), math.log1p(1.0 / 200_000)])
    assert r["x_company"] == pytest.approx(exp_company)
    assert r["x_all"] == pytest.approx(np.mean([math.log1p(0.25), math.log1p(3.0), math.log1p(3.0), math.log1p(5e-6)]))
    assert r["v_company"] == pytest.approx(math.log(200_000))
    # the decision time is the latest available_at in the release (never earlier than any row it uses)
    assert r["av"] == M.SX._ts("2026-10-13T23:59:59+00:00")
    M.CAL._CACHE.clear()


def test_clark_west_detects_planted_predictability():
    rng = np.random.default_rng(9)
    n = 600
    x = rng.normal(size=n)
    y = 0.5 * x + rng.normal(size=n)
    known = np.arange(n) + 1
    cw = M.expanding_oos(x, y, known, 100, 2)
    assert cw["r2"] > 0 and cw["cw_t"] > 3
    ci = M.r2_ci(rng.normal(size=200), rng.normal(size=200) * 0.5, 6, n_boot=300)
    assert ci[0] < ci[1]


# ================================================================================================ harness contract ==

@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_harness_inconclusive_when_bundles_missing(name):
    stat, n, verdict, reason = M.HARNESSES[name](EmptyArchive())
    assert verdict == "inconclusive" and n == 0
    assert "missing" in reason
    assert stat.get("missing_bundles")


def test_theory_map_names_harnesses():
    assert set(M.THEORY_MAP) == {"T-673", "T-674", "T-672"}
    for h in M.THEORY_MAP.values():
        assert h in M.HARNESSES and M.HARNESSES[h].__doc__.strip().rstrip(".") in M.THEORY_MAP


def test_sig_rule():
    assert M.sig(-0.1, 0.001, 10000, 0.0125, "neg") is True
    assert M.sig(0.1, 0.001, 10000, 0.0125, "neg") is False
    assert M.sig(-0.1, 0.3, 10000, 0.0125, "neg") is False
    assert M.sig(None, 0.3, 10000, 0.0125, "neg") is None
    assert math.isclose(M.ALPHA_CELL, 0.05 / 4)
