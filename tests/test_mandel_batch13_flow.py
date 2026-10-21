"""Synthetic tests for mandel.experiments.batch13_flow (T-632, T-633, T-639, T-638): every signal or regression input
built at a decision is unchanged when values AFTER the decision are shocked, the statistics' series have the means
they claim, the pinned calendars are as declared, and every harness returns inconclusive (rule 9) on an archive whose
get() raises KeyError. No network, no real archive."""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch6c_events as EV
from mandel.experiments import batch13_flow as M

VERDICTS = {"supported", "not_supported", "inconclusive"}


class EmptyArchive:
    """Stub archive: every bundle is missing."""

    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self, kind=None, tag=None):
        return []


@pytest.mark.parametrize("name", sorted(M.HARNESSES))
def test_missing_bundles_inconclusive(name):
    _stat, n, verdict, reason = M.HARNESSES[name](EmptyArchive())
    assert verdict == "inconclusive"
    assert n == 0
    assert "missing" in reason


def test_theory_map_covers_harnesses():
    assert set(M.THEORY_MAP) == {"T-632", "T-633", "T-639", "T-638"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)


# ===================================================================================================== T-632 ==

def _sessions(first: str, last: str) -> list:
    d, e, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= e:
        if M.CAL.is_nyse_session(d):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def test_t632_expiry_calendar_pinned():
    assert M.is_expiry(date(2014, 3, 7))                       # Friday
    assert not M.is_expiry(date(2016, 2, 24)) and M.is_expiry(date(2016, 3, 2))       # Wednesday switch
    assert not M.is_expiry(date(2016, 8, 15)) and M.is_expiry(date(2016, 8, 22))      # Monday switch
    assert not M.is_expiry(date(2022, 4, 19)) and M.is_expiry(date(2022, 4, 26))      # Tuesday switch
    assert not M.is_expiry(date(2022, 5, 12)) and M.is_expiry(date(2022, 5, 19))      # Thursday switch
    sh = M.holiday_shifted_controls("2014-01-01", "2023-12-31")
    assert "2014-04-17" in sh                                  # Good Friday 2014 -> Thursday (pre-switch)
    assert "2018-12-04" in sh and "2018-12-06" in sh           # 2018-12-05 closure (Wednesday)
    assert "2017-01-17" in sh                                  # MLK Monday 2017 -> Tuesday (Monday expiries live)
    assert "2016-01-19" not in sh                              # MLK 2016: no Monday expiries yet
    assert "2023-04-06" not in sh                              # Good Friday 2023: Thursday already an expiry
    assert M.opex_day(2014, 4) == date(2014, 4, 17)            # third Friday was Good Friday


def _t632_synth(seed=3, first="2015-01-01", last="2017-12-31"):
    days = _sessions("2014-12-20", last)
    rng = np.random.default_rng(seed)
    n = len(days)
    c = 2000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = c * (1 + rng.normal(0, 0.002, n))
    h = np.maximum(o, c) * (1 + rng.uniform(0.001, 0.01, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0.001, 0.01, n))
    vix = {d: float(v) for d, v in zip(days, rng.uniform(12, 25, n))}
    return days, o, h, l, c, vix


def test_t632_row_uses_prior_vix_and_ignores_later_data():
    days, o, h, l, c, vix = _t632_synth()
    ev = {"fomc": set(), "cpi": set(), "nfp": set()}
    R = M.t632_rows(days, o, h, l, c, vix, ev, "2015-01-01", "2017-12-31")
    t = R["days"][100]
    i = days.index(t)
    vix2 = dict(vix)
    for d in days[i:]:                                         # VIX on t itself and after: not used for row t
        vix2[d] = vix[d] * 3.0
    h2, l2, c2, o2 = h.copy(), l.copy(), c.copy(), o.copy()
    h2[i + 1:] *= 1.5; l2[i + 1:] *= 0.5; c2[i + 1:] *= 1.2; o2[i + 1:] *= 0.9
    R2 = M.t632_rows(days, o2, h2, l2, c2, vix2, ev, "2015-01-01", "2017-12-31")
    k = R["days"].index(t)
    k2 = R2["days"].index(t)
    assert R["y"][k] == pytest.approx(R2["y"][k2])
    assert R["pnl"][k] == pytest.approx(R2["pnl"][k2])
    assert R["E"][k] == R2["E"][k2] and R["P"][k] == R2["P"][k2]
    # the expiry and placebo flags are calendar-only: identical whatever the prices
    assert np.array_equal(R["E"][:k + 1], R2["E"][:k2 + 1])
    # y_t is ln(Parkinson / (VIX_{t-1}/100/sqrt 252))
    park = math.log(h[i] / l[i]) / (2 * math.sqrt(math.log(2)))
    assert R["y"][k] == pytest.approx(math.log(park / (vix[days[i - 1]] / 100 / math.sqrt(252))))


def test_t632_exclusions_and_stale_open():
    days, o, h, l, c, vix = _t632_synth()
    i = days.index("2016-06-08")
    o = o.copy(); o[i] = c[i - 1]                              # stale open
    ev = {"fomc": {"2016-06-15"}, "cpi": set(), "nfp": set()}
    R = M.t632_rows(days, o, h, l, c, vix, ev, "2015-01-01", "2017-12-31")
    for d in ("2016-06-08", "2016-06-15", "2016-06-17", "2016-06-30", "2016-11-25"):   # stale, FOMC, opex, month-end, early close
        assert d not in R["days"]
    assert R["drop"]["stale_open"] == 1


def test_t632_cpi_release_days_keep_one_release_per_month():
    raw = ["2014-01-16", "2014-02-18", "2014-02-20", "2014-03-18", "2015-02-20", "2015-02-26", "2015-03-24"]
    keep, dropped = M.cpi_release_days(raw)
    assert dropped == ["2014-02-18", "2015-02-20"]               # seasonal-factor vintages before the January CPI
    assert keep == ["2014-01-16", "2014-02-20", "2014-03-18", "2015-02-26", "2015-03-24"]
    keep2, dropped2 = M.cpi_release_days(["2016-01-20", "2016-02-19", "2016-03-16"])
    assert dropped2 == [] and len(keep2) == 3                    # ordinary monthly gaps are untouched
    # calendar-only: adding a later release never changes which earlier days are kept
    keep3, _ = M.cpi_release_days(raw + ["2015-04-14"])
    assert keep3[:len(keep)] == keep


def test_t632_fe_slope_recovers_beta_and_psi_mean():
    days = _sessions("2015-01-01", "2017-12-31")
    x = np.array([1.0 if M.is_expiry(date.fromisoformat(d)) else 0.0 for d in days])
    rng = np.random.default_rng(0)
    wd = np.array([date.fromisoformat(d).weekday() for d in days])
    y = -0.2 * x + 0.1 * wd + rng.normal(0, 0.05, len(days))
    f = M.fe_slope(y, x, M.fe_design(days))
    assert f["beta"] == pytest.approx(-0.2, abs=0.02)
    assert f["psi"].mean() == pytest.approx(f["beta"])


def test_t632_straddle_premium():
    s = 0.2
    T = 1 / 252
    from statistics import NormalDist
    call = 2 * NormalDist().cdf(s * math.sqrt(T) / 2) - 1
    assert float(M.atm_straddle(s)) == pytest.approx(2 * call)


# ===================================================================================================== T-633 ==

def test_t633_band_and_grid():
    assert M.band_hits([50.0, 50.24, 50.26, 22.5, 22.62, 210.0, 204.0, 24.9]).tolist() == \
        [True, True, False, True, True, True, False, True]
    assert M.band_hits([49.96, 75.1], M.fine_spacing).tolist() == [True, True]
    pairs, skipped = M.t633_pairs("2014-04-01", "2014-04-30")
    assert ("2014-04-17", "2014-04-16", True) in pairs          # Good Friday third Friday: opex Thursday
    assert all(not p[2] for p in pairs if p[0] != "2014-04-17")
    pairs, skipped = M.t633_pairs("2025-06-01", "2025-06-30")
    assert any(s[0] == "2025-06-20" for s in skipped)          # Juneteenth Thursday: no pair


def test_t633_dollar_volume_ignores_later_rows():
    rng = np.random.default_rng(2)
    X = rng.uniform(1, 2, (80, 6))
    X[5:9, 2] = np.nan
    a = M.trailing_mean(X)
    r = 40
    X2 = X.copy(); X2[r + 1:] *= 50.0
    b = M.trailing_mean(X2)
    assert np.allclose(a[:r + 1], b[:r + 1], equal_nan=True)
    assert a[r, 0] == pytest.approx(X[r - 19:r + 1, 0].mean())


def test_t633_raw_close_from_later_splits_only():
    days = ["2020-08-27", "2020-08-28", "2020-08-31", "2020-09-01"]
    f = M.split_factors([("2020-08-31", 4.0)], days)
    assert f.tolist() == [4.0, 4.0, 1.0, 1.0]


def test_t633_ratio_and_month_psi_mean():
    rng = np.random.default_rng(4)
    n = 520
    opex = np.zeros(n, bool); opex[::4] = True
    hf = rng.integers(30, 60, n).astype(float); hb = rng.integers(30, 60, n).astype(float)
    months = np.array([f"{2005 + k // 48:04d}-{(k // 4) % 12 + 1:02d}" for k in range(n)])
    R = M.ratio_R(hf, hb, opex)
    psi = M.month_psi(hf, hb, opex, months)
    assert psi.mean() == pytest.approx(math.log(R) - math.log(M.T633_BAR))
    years = np.array([int(m[:4]) for m in months])
    pg, pl, _ = M.perm_R(hf, hb, opex, years, R, n_perm=500)
    assert 0 < pg <= 1 and 0 < pl <= 1


def test_t633_permutation_tests_the_registered_boundary():
    """H0 is R <= 1.05: the permutation must be inverted at R = 1.05, not run against exchangeable labels (R = 1)."""
    rng = np.random.default_rng(11)
    n = 520
    opex = np.zeros(n, bool); opex[::4] = True
    years = np.repeat(np.arange(2005, 2005 + n // 52 + 1), 52)[:n]
    hf = rng.integers(300, 600, n).astype(float); hb = rng.integers(300, 600, n).astype(float)
    R0 = M.ratio_R(hf, hb, opex)
    p0 = M.perm_R(hf, hb, opex, years, R0, n_perm=2000, bar=1.0)[0]
    hf2 = hf.copy(); hf2[opex] *= M.T633_BAR                        # the same data with exactly the boundary effect added
    R2 = M.ratio_R(hf2, hb, opex)
    assert R2 == pytest.approx(M.T633_BAR * R0)
    pa = M.perm_R(hf2, hb, opex, years, R2, n_perm=2000)[0]          # default: the registered boundary, hits / 1.05
    ps = M.perm_R(hf2, hb, opex, years, R2, n_perm=2000, adjust=False)[0]
    assert pa == pytest.approx(p0, abs=1e-9)                        # adjusted data = the original data
    assert ps == pytest.approx(p0, abs=0.03)                        # draws x 1.05: the same test up to the draw noise
    p_vs_1 = M.perm_R(hf2, hb, opex, years, R2, n_perm=2000, bar=1.0)[0]
    assert p_vs_1 < pa                                              # against R = 1 the boundary effect looks significant


# ===================================================================================================== T-639 ==

def test_t639_percentile_includes_t_and_ignores_later():
    rng = np.random.default_rng(5)
    x = rng.normal(0.45, 0.02, 600)
    f, d = M.pct_flag_incl(x)
    t = 400
    x2 = x.copy(); x2[t + 1:] += 1.0
    f2, d2 = M.pct_flag_incl(x2)
    assert np.array_equal(f[:t + 1], f2[:t + 1]) and np.array_equal(d[:t + 1], d2[:t + 1])
    assert not d[M.T639_WIN - 2] and d[M.T639_WIN - 1]
    w = x[t - M.T639_WIN + 1:t + 1]
    assert f[t] == (x[t] >= np.percentile(w, M.T639_PCT))


def test_t639_crossings_entries_and_exposure_mean():
    flag = np.array([0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1], bool)
    dfd = np.ones(flag.size, bool)
    cr = M.first_crossings(flag, dfd)
    assert np.flatnonzero(cr).tolist() == [1, 4, 7, 11]
    s_idx = np.arange(flag.size) * 10 + 1
    ent = M.rule_entries(cr, s_idx, 35, 1000)
    assert ent.tolist() == [1, 7, 11]                            # s=41 < 11 + 35: blocked while the first is open
    assert M.rule_entries(cr, s_idx, 35, 100).tolist() == [1]    # windows must end inside the data
    rng = np.random.default_rng(6)
    adj = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 800)))
    sa, sb = np.array([10, 200, 400]), np.arange(5, 700, 7)
    x, _ = M.exposure_series(adj, sa, sb, 60, 2e-4)
    R = np.log(adj[np.r_[sa] + 60] / adj[sa]).mean() - 2e-4 - np.log(adj[sb + 60] / adj[sb]).mean()
    assert x.mean() == pytest.approx(R)


def test_t639_entry_is_after_file_day_and_drawdown_uses_past():
    cal = np.arange(100, 400, dtype=np.int64)
    fd = np.array([150, 151, 152], np.int64)
    s = np.searchsorted(cal, fd, side="right")
    assert (cal[s] > fd).all()
    rng = np.random.default_rng(7)
    adj = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, 500)))
    tr = M.drawdown_triggers(adj)
    t = 300
    adj2 = adj.copy(); adj2[t + 1:] *= 0.5
    tr2 = M.drawdown_triggers(adj2)
    assert np.array_equal(tr[:t + 1], tr2[:t + 1])


# ===================================================================================================== T-638 ==

def _trades(rng, days, k=200):
    ts, iv, F, K, put, sg, am, ex = [], [], [], [], [], [], [], []
    for d in days:
        t0 = d * 86400000
        tt = t0 + rng.integers(0, 86400000, k)
        ts += tt.tolist()
        iv += rng.uniform(30, 80, k).tolist()
        F += rng.uniform(60000, 61000, k).tolist()
        K += rng.choice([58000, 60000, 62000], k).tolist()
        put += rng.integers(0, 2, k).astype(bool).tolist()
        sg += rng.choice([-1.0, 1.0], k).tolist()
        am += rng.uniform(0.1, 5, k).tolist()
        ex += (d + rng.integers(1, 8, k)).tolist()
    return [np.array(v) for v in (ts, iv, F, K, put, sg, am, ex)]


def test_t638_daily_flow_uses_only_that_days_trades():
    rng = np.random.default_rng(8)
    days = list(range(EV._ed("2024-03-01"), EV._ed("2024-03-10")))
    cols = _trades(rng, days)
    ud, N, A, _, _, _ = M.flow_aggregate(*cols)
    ts = cols[0]
    later = ts >= (days[5] + 1) * 86400000                      # trades after the end of day 5
    cols2 = [c.copy() for c in cols]
    cols2[5][later] *= -1.0                                    # flip their direction
    cols2[6][later] *= 10.0                                    # and scale their size
    _, N2, A2, _, _, _ = M.flow_aggregate(*cols2)
    j = int(np.flatnonzero(ud == days[5])[0])
    assert N[:j + 1] == pytest.approx(N2[:j + 1]) and A[:j + 1] == pytest.approx(A2[:j + 1])
    assert not np.allclose(N[j + 1:], N2[j + 1:])
    assert (np.abs(N) <= A + 1e-9).all()


def test_t638_black76_delta():
    assert float(M.b76_delta(100.0, 100.0, 1e-6, 0.5, False)) == pytest.approx(0.5, abs=1e-3)
    assert float(M.b76_delta(100.0, 100.0, 1e-6, 0.5, True)) == pytest.approx(-0.5, abs=1e-3)
    assert float(M.b76_delta(150.0, 100.0, 0.02, 0.5, False)) > 0.99


def test_t638_rule_sign_and_z_ignore_later_values():
    rng = np.random.default_rng(9)
    s = rng.normal(0, 1, 300)
    s[10] = np.nan
    sg = M.trailing_median_sign(s)
    t = 200
    s2 = s.copy(); s2[t + 1:] += 5.0
    sg2 = M.trailing_median_sign(s2)
    assert np.array_equal(sg[:t + 1], sg2[:t + 1], equal_nan=True)
    w = s[np.isfinite(s)]
    k = int(np.flatnonzero(np.isfinite(s))[M.T638_WIN - 1])
    assert sg[k] == (1.0 if s[k] > np.median(w[:M.T638_WIN]) else -1.0)
    z = M.SA.trailing_z(s, M.T638_WIN)
    z2 = M.SA.trailing_z(s2, M.T638_WIN)
    assert np.allclose(z[:t + 1], z2[:t + 1], equal_nan=True)
    p3 = M.horizon_position(sg, 3)
    assert p3[t] == pytest.approx(np.mean(sg[t - 2:t + 1]))


def test_t638_rule_net_costs_and_funding():
    pos = np.array([np.nan, 1.0, 1.0, -1.0, -1.0])
    r = np.array([0.01, 0.02, -0.01, 0.03, 0.0])
    f = np.full(5, 1e-4)
    net = M.rule_net(pos, r, f, 5e-4, "s")
    assert np.isnan(net[0])
    assert net[1] == pytest.approx(0.02 - 1e-4 - 5e-4)       # entry from flat: one side
    assert net[2] == pytest.approx(-0.01 - 1e-4)
    assert net[3] == pytest.approx(-0.03 + 1e-4 - 10e-4)     # flip: a round trip; the short receives funding
    netc = M.rule_net(pos, r, f, 5e-4, "c")
    assert netc[3] == pytest.approx(-0.03 - 1e-4 - 10e-4)   # cost-only funding


def test_t638_spearman_hac_is_rank_correlation():
    rng = np.random.default_rng(10)
    x = rng.normal(size=400)
    y = 0.3 * x + rng.normal(size=400)
    from scipy.stats import spearmanr
    d = M.spearman_hac(x, y)
    assert d["ic"] == pytest.approx(spearmanr(x, y)[0], abs=1e-9)
    assert d["t"] > 2
