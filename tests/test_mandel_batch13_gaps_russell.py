"""Batch 13, group gaps_russell (T-736, T-741): the recon calendar, point-in-time signal construction, the permutation
null's exclusions, and missing data."""

from datetime import date, timedelta

import numpy as np
import pytest

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch13_gaps_russell as M


def _sessions(start, end):
    d, out = date.fromisoformat(start), []
    while d <= date.fromisoformat(end):
        if CAL.is_nyse_session(d):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _walk(n, seed, vol=0.01, drift=0.0002):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))


# ============================================================================================ recon calendar ==

def test_recon_table_matches_the_documented_rules_and_sources():
    for y in range(2000, 2027):
        assert M.RECON_JUNE[y][0] == M.documented_rule(y).isoformat()
        assert date.fromisoformat(M.RECON_JUNE[y][0]).month == 6
        assert CAL.is_nyse_session(date.fromisoformat(M.RECON_JUNE[y][0]))
    assert [M.RECON_JUNE[y][0] for y in (2000, 2001, 2002, 2003)] == ["2000-06-30", "2001-06-29", "2002-06-28", "2003-06-30"]
    assert M.RECON_JUNE[2006][0] == "2006-06-30" and M.RECON_JUNE[2020][0] == "2020-06-26"
    assert M.RECON_JUNE[2025][0] == "2025-06-27" and M.RECON_JUNE[2016][0] == "2016-06-24"


def test_fourth_friday_reading_differs_only_in_2006():
    a, b = M.recon_dates("published"), M.recon_dates("fourth_friday")
    assert {y for y in a if a[y] != b[y]} == {2006}
    assert b[2006] == "2006-06-23"
    for y in range(2013, 2027):
        assert a[y] == M.nth_friday(y, 6, 4).isoformat()


def test_calendar_helpers():
    assert M.third_friday(2026, 6) == date(2026, 6, 19) and not CAL.is_nyse_session(date(2026, 6, 19))
    assert M.expiry_session(date(2026, 6, 19)) == date(2026, 6, 18)
    assert M.last_friday(2026, 1) == date(2026, 1, 30) and M.last_friday(2025, 10) == date(2025, 10, 31)
    s = _sessions("2026-06-01", "2026-07-15")
    b = M.band(s, "2026-06-19", 5)                      # a holiday: 5 sessions before and 5 from the next session
    assert len(b) == 10 and "2026-06-19" not in b and b[4] == "2026-06-18" and b[5] == "2026-06-22"
    b2 = M.band(s, "2026-06-26", 2)
    assert b2 == ["2026-06-24", "2026-06-25", "2026-06-26", "2026-06-29", "2026-06-30"]


# ==================================================================================================== T-736 ==

def _pair(start="2009-01-02", end="2014-12-31", seed=1):
    days = _sessions(start, end)
    return days, _walk(len(days), seed), _walk(len(days), seed + 1)


def test_event_return_uses_only_the_entry_and_exit_closes():
    days, a, b = _pair()
    recon = M.recon_dates("published", range(2009, 2015))
    r0 = M.t736_reading(days, a, b, recon, n_perm=200, max_batches=1)
    ev = r0["ev"]
    y = 2011
    i = ev[y]
    j = i + M.T736_HOLD
    a2, b2 = a.copy(), b.copy()
    a2[j + 1:] *= 1.5; b2[j + 1:] *= 0.7                 # after the exit: the event's return must not move
    a2[:i] *= 0.8                                       # before the entry close: nor this
    r1 = M.t736_reading(days, a2, b2, recon, n_perm=200, max_batches=1)
    k = r0["years"].index(y)
    assert r1["net"][k] == pytest.approx(r0["net"][k])
    assert r1["dates"] == r0["dates"] and r1["years"] == r0["years"]     # entries are calendar-only
    expect = (a[j] / a[i] - 1) - (b[j] / b[i] - 1) - 0.0020 - 0.003 * 20 / 252
    assert r0["net"][k] == pytest.approx(expect)
    assert r0["dates"][y] == recon[y] and r0["exits"][y] == days[i + 20]


def test_signal_at_decision_does_not_move_when_prices_after_it_are_shocked():
    days, a, b = _pair()
    recon = M.recon_dates("published", range(2009, 2015))
    ev0, _ = M.event_index(days, recon)
    el0 = M.null_starts(days, recon, sorted(ev0))
    a2 = a.copy(); a2[len(a) // 2:] *= 3.0
    r0 = M.t736_reading(days, a, b, recon, n_perm=200, max_batches=1)
    r1 = M.t736_reading(days, a2, b, recon, n_perm=200, max_batches=1)
    assert r0["ev"] == r1["ev"] == ev0                  # the decision is the published calendar: price-independent
    el1 = M.null_starts(days, recon, sorted(r1["ev"]))
    assert all(np.array_equal(el0[y], el1[y]) for y in el0)
    early = [k for k, y in enumerate(r0["years"]) if r0["ev"][y] + 20 < len(a) // 2]
    assert early and np.allclose(r0["net"][early], r1["net"][early])  # events closed before the shock are unchanged
    pl0 = M.placebo_index(days, range(2009, 2015))
    assert all(days[i][5:7] in ("01", "04", "10") and date.fromisoformat(days[i]).weekday() == 4 for _, i in pl0)


def test_null_windows_avoid_recon_and_quad_witching_bands():
    days = _sessions("2009-01-02", "2014-12-31")
    recon = M.recon_dates("published", range(2009, 2015))
    el = M.null_starts(days, recon, range(2009, 2015))
    pos = {d: i for i, d in enumerate(days)}
    banned = set()
    for d in recon.values():
        k = pos[d]
        banned.update(range(k - 20, k + 21))
    for y in range(2009, 2015):
        for m in (3, 6, 9, 12):
            tf = M.third_friday(y, m).isoformat()
            k = pos[tf]
            banned.update(range(k - 5, k + 6))
    for y, starts in el.items():
        assert starts.size > 20
        for s in starts:
            assert int(days[s][:4]) == y and s + 20 < len(days)
            assert not banned.intersection(range(s, s + 21))
    allowed = set(np.concatenate(list(el.values())).tolist())
    for s in range(len(days) - 20):                     # every clean start in an event year is eligible
        if not banned.intersection(range(s, s + 21)) and 2009 <= int(days[s][:4]) <= 2014:
            assert s in allowed


def test_permutation_detects_a_planted_recon_effect_and_not_its_absence():
    days, a, b = _pair("2000-01-03", "2014-12-31", seed=3)
    recon = M.recon_dates("published", range(2000, 2015))
    base = M.t736_reading(days, a, b, recon, n_perm=2000, max_batches=1)
    a2 = a.copy()
    for i in base["ev"].values():                       # plant +4% on IJR over each post-recon window
        a2[i + 1:i + 21] *= np.linspace(1.002, 1.04, 20)
        a2[i + 21:] *= 1.04
    planted = M.t736_reading(days, a2, b, recon, n_perm=2000, max_batches=1)
    assert planted["mean"] > base["mean"] + 0.03
    assert planted["perm"]["p_greater"] < 0.01
    assert base["perm"]["p_greater"] > 0.01


def test_boot_t_ci_brackets_the_mean():
    x = np.random.default_rng(0).normal(0.01, 0.02, 40)
    r = M.boot_t(x, 4000)
    assert r["ci"][0] < x.mean() < r["ci"][1] and r["lower_one_sided"] > r["ci"][0]


# ==================================================================================================== T-741 ==

def _iwm_rvx(start="2009-06-01", end="2013-12-31", seed=5):
    days = _sessions(start, end)
    adj = _walk(len(days), seed)
    rvx = {d: 20.0 + 5 * np.sin(k / 30.0) for k, d in enumerate(days)}
    return days, adj, rvx


def test_gap_uses_rvx_at_t_and_returns_t_plus_1_to_t_plus_21():
    days, adj, rvx = _iwm_rvx()
    recon = M.recon_dates("published", range(2010, 2014))
    P = M.gap_panel(days, adj, rvx, recon, years=(2010, 2013))
    k = 100
    t = P["day"][k]
    i = days.index(t)
    r = np.log(adj[i + 1:i + 22] / adj[i:i + 21])
    assert P["realised"][k] == pytest.approx(252 / 21 * np.sum(r ** 2))
    assert P["implied"][k] == pytest.approx((rvx[t] / 100) ** 2)
    adj2 = adj.copy(); adj2[i + 22:] *= np.exp(np.random.default_rng(9).normal(0, 0.05, len(adj) - i - 22))
    rvx2 = {d: (v * 2 if d > t else v) for d, v in rvx.items()}
    P2 = M.gap_panel(days, adj2, rvx2, recon, years=(2010, 2013))
    assert P2["g"][k] == pytest.approx(P["g"][k])                       # nothing after t+21 (or RVX after t) moves g_t
    assert P2["implied"][k] == P["implied"][k] and P2["treated"][k] == P["treated"][k]
    assert np.array_equal(P2["treated"], P["treated"]) and np.array_equal(P2["opex"], P["opex"])   # flags: calendar only


def test_treated_flag_is_the_window_t_plus_1_to_t_plus_21():
    days, adj, rvx = _iwm_rvx()
    recon = M.recon_dates("published", range(2010, 2014))
    P = M.gap_panel(days, adj, rvx, recon, years=(2010, 2013))
    for y in range(2010, 2014):
        R = days.index(recon[y])
        tr = [days.index(d) for d, f in zip(P["day"], P["treated"]) if f and d[:4] == str(y)]
        assert tr == list(range(R - 21, R))                             # t+1 <= R <= t+21; day R itself is not
    one = [d for d, o in zip(P["day"], P["opex"]) if o and d[:4] == "2011"]
    qd = days.index("2011-03-18")
    assert days[qd - 21] in one and days[qd] not in one


def test_year_contrasts_and_missing_rvx_days():
    year = np.array([2010] * 4 + [2011] * 4)
    g = np.array([1.0, 2.0, 0.0, 0.0, 3.0, 3.0, 1.0, 2.0])
    tr = np.array([1, 1, 0, 0, 1, 0, 0, 0], bool)
    c = M.year_contrasts(year, g, tr, ~tr)
    assert c[2010] == (pytest.approx(1.5), 2, 2) and c[2011][0] == pytest.approx(1.0)
    days, adj, rvx = _iwm_rvx()
    rvx.pop(days[300])
    P = M.gap_panel(days, adj, rvx, {}, years=(2010, 2013))
    assert days[300] in P["no_rvx"] and days[300] not in set(P["day"])


def test_year_weighted_series_has_mean_d_bar_and_reduces_to_the_house_series_in_one_year():
    rng = np.random.default_rng(4)
    year = np.repeat([2010, 2011, 2012], [250, 252, 248])
    g = rng.normal(0.01, 0.02, year.size)
    tr = np.zeros(year.size, bool)
    for y, s in ((2010, 150), (2011, 140), (2012, 160)):
        k = np.flatnonzero(year == y)[s]
        tr[k:k + 21] = True
    g[tr] += 0.004
    dy = M.year_contrasts(year, g, tr, ~tr)
    z = M.year_weighted_series(year, g, tr)
    assert z.size == year.size
    assert z.mean() == pytest.approx(np.mean([v[0] for v in dy.values()]))
    pooled = CAL.flag_diff_series(g, tr).mean()
    assert pooled == pytest.approx(g[tr].mean() - g[~tr].mean())
    one = year == 2011                                  # a single year: identical to the house flag-difference series
    assert np.allclose(M.year_weighted_series(year[one], g[one], tr[one]), CAL.flag_diff_series(g[one], tr[one]))
    tr2 = tr & (year != 2012)                           # a year without treated entries is left out
    z2 = M.year_weighted_series(year, g, tr2)
    assert z2.size == int((year != 2012).sum())
    assert z2.mean() == pytest.approx(np.mean([v[0] for v in M.year_contrasts(year, g, tr2, ~tr2).values()]))


def test_loo_means():
    r = M.loo_means({2019: 1.0, 2020: 10.0, 2021: 4.0})
    assert r == {2019: pytest.approx(7.0), 2020: pytest.approx(2.5), 2021: pytest.approx(5.5)}
    assert M.loo_means({2020: 1.0}) == {}


# ============================================================================================ wiring / missing ==

class _NoArchive:
    def get(self, name):
        raise KeyError(name)

    def load(self, name):
        raise KeyError(name)

    def entries(self, *a, **k):
        return []


@pytest.mark.parametrize("name", list(M.HARNESSES))
def test_missing_bundles_give_inconclusive(name):
    _stat, n, verdict, reason = M.HARNESSES[name](_NoArchive())
    assert verdict == "inconclusive" and n == 0 and "missing" in reason


def test_theory_map_covers_the_group():
    assert set(M.THEORY_MAP) == {"T-736", "T-741"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    for fn in M.HARNESSES.values():
        assert fn.__doc__ and fn.__doc__.startswith("T-7")
