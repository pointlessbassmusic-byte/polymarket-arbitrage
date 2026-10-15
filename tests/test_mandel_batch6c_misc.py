"""Batch-6c misc harnesses (T-318 TA-rule reality check, T-326 gold/silver ratio rule, T-370 metals implied financing,
T-372 ES implied financing, T-416 Fear & Greed first crossings, T-484 long-history bond TSMOM) on synthetic data only:
for every core judge a planted effect passes and a null does not; the rule universe, SPA, CSCV, calendars, dividend
accrual and event logic are checked directly; every harness runs on a fake archive (JSON-safe, missing bundles ->
inconclusive). No archive, no network."""

import json
import math
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from mandel.experiments import batch6c_misc as m
from mandel.experiments.batch6b_bw import Bills
from mandel.experiments.overfit import pbo_cscv


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(m, "N_BOOT", 200)
    monkeypatch.setattr(m, "SPA_BOOT", 300)
    monkeypatch.setattr(m, "T416_BOOT", 300)
    monkeypatch.setattr(m, "T484_BOOT", 300)
    monkeypatch.setattr(m, "REPS", 2)
    monkeypatch.setattr(m, "REPS_MAX", 2)
    m._CACHE.clear()
    yield
    m._CACHE.clear()


# ---------------------------------------------------------------------------------------------- fake archive --

class FakeArchive:
    def __init__(self, bundles, created="2030-01-01T00:00:00+00:00"):
        self.bundles, self.created = bundles, created

    def get(self, name):
        if name not in self.bundles:
            raise KeyError(name)
        return SimpleNamespace(created_at=self.created)

    def load(self, name):
        return iter(self.bundles[name])


def _yahoo(days, close, adj=None, hour="14:30"):
    adj = close if adj is None else adj
    return [{"available_at": d + "T23:00:00+00:00",
             "value": {"t": datetime.fromisoformat(f"{d}T{hour}:00+00:00").timestamp(), "close": float(c), "adjclose": float(a)}}
            for d, c, a in zip(days, close, adj)]


def _fred_rows(days, vals):
    return [{"available_at": d + "T20:00:00+00:00", "value": {"day": d, "value": float(x)}} for d, x in zip(days, vals)]


def _fng_rows(days, vals):
    return [{"observed_at": d + "T00:00:00+00:00",
             "available_at": (date.fromisoformat(d) + timedelta(days=1)).isoformat() + "T00:00:00+00:00",
             "value": {"value": float(v), "label": "x"}} for d, v in zip(days, vals)]


def wdays(first, last):
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def cdays(first, last):
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _last_wd(month):
    y, mo = int(month[:4]), int(month[5:7])
    d = date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1)
    while d.weekday() > 4:
        d -= timedelta(days=1)
    return d.isoformat()


def _json_ok(stat):
    json.dumps(stat, allow_nan=False)


# ============================================================================================ T-318 =====

def test_rule_universe_is_the_frozen_88():
    rules = m.rule_universe()
    assert len(rules) == 88
    fam = [r[0] for r in rules]
    assert (fam.count("sma"), fam.count("cross"), fam.count("donchian"), fam.count("filter")) == (24, 29, 25, 10)
    assert ("cross", 50, 50) not in rules and ("cross", 50, 100) in rules
    assert m.rule_name(("donchian", 30)) == "Donchian30/15"


def test_rule_signals_logic_and_one_bar_delay():
    c = np.r_[np.full(30, 100.0), np.linspace(100, 130, 30), np.linspace(130, 90, 40)]
    sig = m.rule_signals(c, [("sma", 20), ("donchian", 10), ("filter", 5)])
    assert sig[:19, 0].sum() == 0                            # undefined before 20 closes
    assert sig[35, 0] == 1 and sig[95, 0] == 0
    first_break = int(np.argmax(sig[:, 1]))
    assert c[first_break] > c[first_break - 10:first_break].max()
    exit_ = first_break + int(np.argmax(sig[first_break:, 1] == 0))
    assert c[exit_] < c[exit_ - 5:exit_].min()
    entry_f = int(np.argmax(sig[:, 2]))
    assert c[entry_f] >= 100 * 1.05 and c[entry_f - 1] < 100 * 1.05
    rr = m.rule_returns(c, np.zeros(c.size), 0.0002, [("sma", 20)])
    assert np.array_equal(rr["pos"][2:, 0], sig[:-2, 0])     # signal at close t earns the return over (t+1, t+2]
    k = int(np.argmax(rr["pos"][:, 0]))
    assert rr["ex"][k, 0] == pytest.approx(rr["xr"][k] - 0.0002)


def test_pbo_fast_matches_pbo_cscv():
    rng = np.random.default_rng(3)
    R = rng.normal(0, 0.01, (403, 9)) + rng.normal(0, 0.002, 9)
    a, b = m.pbo_fast(R, 8), pbo_cscv(R, 8)
    assert a["pbo"] == pytest.approx(b["pbo"]) and a["median_logit"] == pytest.approx(b["median_logit"])
    assert a["n_combinations"] == b["n_combinations"] == 70


def test_hansen_spa_planted_rejects_and_null_does_not():
    rng = np.random.default_rng(5)
    n = 2000
    null = rng.normal(-0.0005, 0.01, (n, 6))
    t0 = m.hansen_spa(null, 20, 400, 0)
    assert t0["p_c"] > 0.05 and t0["p_l"] <= t0["p_c"] <= t0["p_u"]
    planted = null.copy()
    planted[:, 2] = rng.normal(0.002, 0.01, n)
    t1 = m.hansen_spa(planted, 20, 400, 0)
    assert t1["p_c"] < 0.05 and t1["best"] == 2


def test_stationary_bootstrap_means_are_unbiased():
    x = np.random.default_rng(1).normal(0.3, 1.0, 500)
    b = m.sb_means(x, 20, 400, 0)
    assert b.shape == (400,) and abs(b.mean() - x.mean()) < 0.05 and 0.02 < b.std() < 0.2


def _control_world(edge: bool):
    days = wdays("1994-01-03", "2013-12-31")
    n = len(days)
    rng = np.random.default_rng(11)
    xr = rng.normal(0.0003, 0.01, n)
    favored_a = np.array([((int(d[:4]) - 1994) // 5) % 2 == 0 for d in days])   # A wins on 5-year spells, B on the others
    K = 10
    ex = np.empty((n, K))
    for k in range(K):
        sgn = 1.0 if k % 2 == 0 else -1.0
        ex[:, k] = xr + sgn * 0.0006 * np.where(favored_a, 1.0, -1.0) - 0.0001 + rng.normal(0, 0.002, n)
    if edge:
        ex[:, 0] = xr + 0.0008 + rng.normal(0, 0.002, n)
    return ex, xr, days


def test_reality_check_planted_control_confirmed():
    ex, xr, days = _control_world(edge=False)
    j = m.reality_check(ex, xr, days, 0.0, None, min_n=1000, n_phases=3, spa_boot=300)
    assert j["spa"]["p_c"] > 0.05
    assert j["pbo"]["pbo"] > 0.5
    assert j["wf"]["calendar"]["diff"] < 0 and [c[1] for c in j["criteria"]] == [True, True, True]
    assert j["verdict"] == "supported" and not j["surprise"]


def test_reality_check_null_edge_is_not_a_control():
    ex, xr, days = _control_world(edge=True)
    j = m.reality_check(ex, xr, days, 0.0, None, min_n=1000, n_phases=3, spa_boot=300)
    assert j["spa"]["p_c"] < 0.05 and j["criteria"][0][1] is False
    assert j["verdict"] == "not_supported" and j["surprise"]


def test_walk_forward_calendar_is_the_claims():
    ex, xr, days = _control_world(edge=False)
    W = m.walk_forward(ex, xr, days, 0.0)
    assert [s["month"] for s in W["selections"]] == ["1998-12", "2003-12", "2008-12"]
    assert days[W["first"]].startswith("1999-01")
    assert m.walk_forward(ex, xr, days, 0.0, phase=7)["selections"][0]["month"] == "1999-07"


def test_walk_forward_selects_on_bars_before_the_switch():
    """Regression (T-318): the switch is made at re-selection close e, so the ranking may use returns through close e - 1
    only (one-bar delay); the bar ending at close e must not enter it."""
    days = wdays("1994-01-03", "2003-12-31")
    n = len(days)
    e = max(i for i, d in enumerate(days) if d[:7] == "1998-12")
    xr = np.zeros(n)
    ex = np.zeros((n, 2))
    ex[:, 0] = 1e-5 + 1e-3 * np.sin(np.arange(n))           # per-day Sharpe about 0.014
    ex[e, 1] = 0.01                                        # rule 1: one gain on the re-selection bar (Sharpe about 0.028)
    W = m.walk_forward(ex, xr, days, 0.0)
    s0 = W["selections"][0]
    assert s0["month"] == "1998-12" and s0["is_days"] == e and s0["rule"] == 0
    assert W["first"] == e + 1 and W["wf"][e + 1] == ex[e + 1, 0]
    ex[e, 1], ex[e - 1, 1] = 0.0, 0.01                     # the same gain one bar earlier is known at the switch
    assert m.walk_forward(ex, xr, days, 0.0)["selections"][0]["rule"] == 1


# ============================================================================================ T-326 =====

def _metals_pair(kind: str, n: int = 3600, seed: int = 2):
    rng = np.random.default_rng(seed)
    days = wdays("2006-04-28", "2030-01-01")[:n]
    A = 60 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = (0.96 * x[t - 1] + 0.02 * rng.normal()) if kind == "ou" else x[t - 1] + 0.01 * rng.normal()
    B = A * np.exp(-(x + 1.5))
    return days, A, B


def test_trailing_z_matches_direct():
    x = np.random.default_rng(0).normal(0, 1, 120).cumsum()
    z = m.trailing_z(x, 30)
    w = x[60:90]
    assert z[89] == pytest.approx((x[89] - w.mean()) / w.std(ddof=1))
    assert np.isnan(z[28]) and np.isfinite(z[29])


def test_ratio_rule_fills_at_the_next_close():
    days, A, B = _metals_pair("ou", 1500)
    P = m.ratio_rule(days, A, B, anchor=50, end="2030-01-01")
    z = m.trailing_z(np.log(A / B), 50)
    ix = {d: i for i, d in enumerate(days)}
    assert len(P["trades"]) >= 5
    for tr in P["trades"]:
        e = ix[tr["entry"]]
        assert (z[e - 1] > 2) if tr["side"] == "long B/short A" else (z[e - 1] < -2)
        if tr["exit"] is not None:
            x_ = ix[tr["exit"]]
            zz = z[x_ - 1]
            if tr["side"] == "long B/short A":
                assert zz <= 0 or zz >= 3.5 or tr["days_held"] >= 120
            else:
                assert zz >= 0 or zz <= -3.5 or tr["days_held"] >= 120
    k = ix[P["trades"][0]["entry"]] - ix[P["days"][0]]
    assert P["net"][k] == pytest.approx(-0.004)              # 20 bps x 2 legs on the fill day, no P&L yet


def test_ratio_reversion_planted_passes():
    days, A, B = _metals_pair("ou")
    j = m.ratio_reversion((days, A), (days, B), min_n=500, end="2030-01-01")
    oks = [c[1] for c in j["criteria"]]
    assert oks[0] is True and oks[1] is True and oks[2] is None
    assert j["verdict"] == "inconclusive" and j["n_trades"] >= 5


def test_ratio_reversion_null_does_not_pass():
    days, A, B = _metals_pair("rw", seed=4)
    j = m.ratio_reversion((days, A), (days, B), min_n=500, end="2030-01-01")
    assert j["criteria"][0][1] is not True and j["verdict"] != "supported"


def test_variance_ratio_detects_mean_reversion():
    rng = np.random.default_rng(9)
    iid = np.cumsum(rng.normal(0, 1, 3000))
    v = m.variance_ratio(iid, 20)
    assert abs(v["vr"] - 1) < 0.25 and abs(v["z"]) < 3
    ou = np.zeros(3000)
    for t in range(1, 3000):
        ou[t] = 0.9 * ou[t - 1] + rng.normal()
    w = m.variance_ratio(ou, 60)
    assert w["vr"] < 0.5 and w["z"] < -3


def test_roll_adjusted_index_replaces_roll_window_returns():
    days = wdays("2010-01-04", "2010-12-31")
    F = 100 * np.exp(np.cumsum(np.full(len(days), 0.001)))
    etf = {d: 50.0 for d in days}                           # flat ETF: roll-window returns become 0
    adj = m.roll_adjusted_index(days, F, m.GC_MONTHS, etf)
    fl = m.roll_flags(days, m.GC_MONTHS)
    r = np.r_[0, adj[1:] / adj[:-1] - 1]
    assert fl.sum() >= 25 and np.allclose(r[fl & (np.arange(len(days)) > 0)], 0.0)
    assert np.allclose(r[~fl][1:], math.exp(0.001) - 1)


# ============================================================================================ T-370 =====

def test_cme_metals_calendar():
    assert m.last_trade_day(2025, 12) == date(2025, 12, 29)
    assert m.first_notice_day(2025, 12) == date(2025, 11, 28)
    assert m.front_contract(date(2025, 11, 26), m.GC_MONTHS) == (2025, 12)
    assert m.front_contract(date(2025, 11, 28), m.GC_MONTHS) == (2026, 2)
    assert m.front_contract(date(2025, 12, 15), m.SI_MONTHS) == (2026, 3)


def _gold_world(carry: float, r: float = 0.02, seed: int = 0, noise: float = 0.0003, silver: bool = False):
    days = wdays("2006-05-01" if silver else "2005-01-03", "2016-12-30")
    rng = np.random.default_rng(seed)
    spot = 400 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
    oz0, fee, launch, months = ((m.SLV_OZ0, m.SLV_FEE, m.SLV_LAUNCH, m.SI_MONTHS) if silver else
                                (m.GLD_OZ0, m.GLD_FEE, m.GLD_LAUNCH, m.GC_MONTHS))
    gld = spot * np.array([m.ounces_per_share(d, oz0, fee, launch) for d in days])
    dd = np.array([(m.last_trade_day(*m.front_contract(date.fromisoformat(d), months)) - date.fromisoformat(d)).days
                   for d in days], float)
    F = spot * np.exp((r + carry) * dd / 365.0 + rng.normal(0, noise, len(days)))
    return days, F, gld, (lambda ds: np.full(len(ds), r))


def test_band_test_planted_inside_and_null_outside():
    days, F, gld, rate = _gold_world(0.0)
    G = m.implied_financing(days, F, gld, lambda d: m.ounces_per_share(d, m.GLD_OZ0, m.GLD_FEE, m.GLD_LAUNCH), m.GC_MONTHS, rate,
                            end="2030-01-01")
    t = m.band_test(G["dev"])
    assert t["ok"] is True and abs(t["mean"]) < 0.002 and abs(G["decay"]["dev"]) < 0.003
    days, F, gld, rate = _gold_world(0.02)
    G = m.implied_financing(days, F, gld, lambda d: m.ounces_per_share(d, m.GLD_OZ0, m.GLD_FEE, m.GLD_LAUNCH), m.GC_MONTHS, rate,
                            end="2030-01-01")
    t = m.band_test(G["dev"])
    assert t["ok"] is False and t["decisive"] is True and t["mean"] == pytest.approx(0.02, abs=0.003)


def test_metals_basis_planted_passes_and_null_fails_on_gold_alone():
    """Regression (T-370): the GLD-NAV 'Robustness: ... instead of the GLD close' item is report-only (module convention),
    so the rule's close construction decides; it no longer caps the verdict at inconclusive."""
    days, F, gld, rate = _gold_world(0.0)
    j = m.metals_basis((days, F, gld), None, rate, min_n=500)
    assert len(j["criteria"]) == 1 and j["criteria"][0][1] is True and j["verdict"] == "supported"
    assert "not archived" in j["robustness_nav"]
    days, F, gld, rate = _gold_world(0.02)
    j = m.metals_basis((days, F, gld), None, rate, min_n=500)
    assert j["criteria"][0][1] is False and j["gold"]["decisive_bonf6"] is True and j["verdict"] == "not_supported"
    j = m.metals_basis((days[:400], F[:400], gld[:400]), None, rate, min_n=500)   # below min_n: decisive failure counts
    assert j["n"] < 500 and j["verdict"] == "not_supported"


def test_metals_basis_other_metals_are_separate_trials():
    """Regression (T-370): the claim is gold-only; a failing silver trial and the unarchived PL/PA/HG trials are reported,
    not criteria, so they neither override nor cap the gold result."""
    days, F, gld, rate = _gold_world(0.0)
    sd, SF, SE, _ = _gold_world(0.03, seed=4, silver=True)
    j = m.metals_basis((days, F, gld), (sd, SF, SE), rate, min_n=500)
    assert j["silver"]["ok_bonf6"] is False and j["separate_trials"]["silver"]["decisive"] is True
    assert set(j["separate_trials"]) == {"silver", "platinum", "palladium", "copper"}
    assert "not archived" in j["separate_trials"]["copper"]
    assert len(j["criteria"]) == 1 and j["criteria"][0][0].startswith("gold") and j["verdict"] == "supported"


def test_metals_basis_judges_the_six_trial_bonferroni_interval():
    """Regression (T-370): '6 trials counted' -> the band test uses the HAC interval at 1 - 0.05/6; a mean whose
    unadjusted 95% CI is inside the band but whose Bonferroni CI crosses +50 bp fails (not decisively)."""
    days, F, gld, rate = _gold_world(0.0037, noise=0.003)
    j = m.metals_basis((days, F, gld), None, rate, min_n=500)
    g = j["gold"]
    assert g["ci"][1] < 0.005 < g["ci_bonf6"][1] and g["ok"] is True
    assert j["criteria"][0][1] is False and g["decisive_bonf6"] is False and j["verdict"] == "not_supported"
    assert "99.17% CI" in j["criteria"][0][0]


# ============================================================================================ T-372 =====

def _es_world(spread: float, r: float = 0.02, seed: int = 1, first: str = "2008-06-02"):
    days = wdays(first, "2013-12-31")
    rng = np.random.default_rng(seed)
    I = 1000 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
    exps = m.quarterly_expiries(days, int(first[:4]), 2014)
    spy_c = I / 10.0
    f = np.ones(len(days))
    exset = set(exps)
    for i in range(1, len(days)):
        f[i] = f[i - 1] / (1 - 1.5 / spy_c[i - 1]) if days[i] in exset else f[i - 1]
    spy_a = spy_c * f
    F = np.empty(len(days))
    for i, d in enumerate(days):
        Tc = next(T for T in exps if T >= d)
        Tp = max(T for T in exps if T < Tc) if any(T < Tc for T in exps) else (date.fromisoformat(Tc) - timedelta(days=91)).isoformat()
        dd = (date.fromisoformat(Tc) - date.fromisoformat(d)).days
        D = 15.0 * dd / (date.fromisoformat(Tc) - date.fromisoformat(Tp)).days
        F[i] = (I[i] - D) * math.exp((r + spread) * dd / 365.0)
    return (days, F), (days, I), (days, spy_c, spy_a), (lambda ds: np.full(len(ds), r))


def test_quarterly_expiries_holiday_and_dividend_accrual():
    s = [d for d in wdays("2026-06-01", "2026-06-30") if d != "2026-06-19"]
    assert m.quarterly_expiries(s, 2026, 2026)[1] == "2026-06-18"
    acc = m.dividend_accrual(["2024-03-15", "2024-06-21"], [1.0, 2.0])
    assert acc("2024-03-15", "2024-06-21") == pytest.approx(2.0)
    assert acc("2024-05-03", "2024-06-21") == pytest.approx(2.0 * 49 / 98)
    assert acc("2024-05-03", "2024-06-21", known_before="2024-06-21") == 0.0


def test_es_financing_planted_passes():
    es, gs, spy, rate = _es_world(0.006)
    j = m.es_financing(es, gs, spy, rate, min_n=500)
    assert j["mean"] == pytest.approx(0.006, abs=0.001)
    assert [c[1] for c in j["criteria"]] == [True, True] and j["verdict"] == "supported"
    assert j["n_quarters"] >= 15


def test_es_financing_null_fails():
    es, gs, spy, rate = _es_world(0.0)
    j = m.es_financing(es, gs, spy, rate, min_n=500)
    assert abs(j["mean"]) < 0.001 and j["verdict"] == "not_supported"


def test_es_financing_counts_the_five_trials():
    """T-372 under the module's trial-count convention: '5 trials counted' -> one-sided bounds at 1 - 0.05/5. An HAC
    lower bound above 20 bp unadjusted but below it at the Bonferroni level fails; realized dividends stay report-only."""
    es, gs, spy, rate = _es_world(0.0036)
    j = m.es_financing(es, gs, spy, rate, min_n=500)
    assert j["level_one_sided"] == pytest.approx(0.99)
    assert j["hac_lower"] == pytest.approx(j["mean"] - 2.3263479 * j["hac_se"], rel=1e-6)
    assert j["hac_lower95"] > m.T372_THR > j["hac_lower"] and j["criteria"][0][1] is False
    assert len(j["criteria"]) == 2 and j["verdict"] == "not_supported"


# ============================================================================================ T-416 =====

def _fng_world(effect: float, seed: int = 3, last: str = "2025-06-30", spacing: int = 75):
    rng = np.random.default_rng(seed)
    fd = cdays("2018-02-01", last)
    F = 50 + 10 * np.sin(np.arange(len(fd)) / 9.0) + rng.uniform(-5, 5, len(fd))
    dips = list(range(20, len(fd) - 40, spacing))
    for k in dips:
        F[k] = 15.0
    fng = {d: (float(v), None) for d, v in zip(fd, F)}
    bd = cdays("2017-11-01", (date.fromisoformat(last) + timedelta(days=120)).isoformat())
    lr = rng.normal(0, 0.003, len(bd))
    ix = {d: i for i, d in enumerate(bd)}
    for k in dips:
        e = ix[(date.fromisoformat(fd[k]) + timedelta(days=1)).isoformat()]
        lr[e + 1:e + 31] += effect / 30.0
    px = dict(zip(bd, 100 * np.exp(np.cumsum(lr))))
    return px, fng, [fd[k] for k in dips]


def test_fng_events_crossing_refractory_and_level():
    days = cdays("2020-01-01", "2020-03-31")
    F = np.full(len(days), 40.0)
    F[[5, 9, 30, 31, 32, 60]] = [18, 19, 15, 14, 25, 10]      # day 9 is inside day 5's 10-day refractory window
    fng = {d: (v, None) for d, v in zip(days, F)}
    E = m.fng_events(fng, "first", 20, 30)
    assert E["all"] == [days[5], days[30], days[60]]
    assert E["kept"] == [days[5], days[60]]                  # day 30 is within 30 days of day 5
    L = m.fng_events(fng, "level", 20, 1)
    assert L["all"] == [days[i] for i in (5, 9, 30, 31, 60)]


def test_fear_greed_planted_passes():
    px, fng, dips = _fng_world(0.25)
    j = m.fear_greed_study(px, None, fng, grid=False)
    assert j["n_events"] >= 30 and j["coef"] > m.T416_EFFECT   # overlapping non-event windows carry part of the drift
    assert [c[1] for c in j["criteria"]] == [True, True, True]
    assert j["verdict"] == "supported"


def test_fear_greed_null_does_not_pass():
    px, fng, dips = _fng_world(0.0)
    j = m.fear_greed_study(px, None, fng, grid=False)
    assert j["criteria"][0][1] is not True and j["verdict"] != "supported"


def test_coef_test_uses_percentile_bounds_and_p():
    """Regression (T-416): rule 6 allows studentized or percentile intervals, so the one-sided bounds are the 5% / 95%
    quantiles of the bootstrap coefficients b* and p = P(b* <= 0), not the basic (reverse-percentile) b - q(b* - b)."""
    rng = np.random.default_rng(8)
    n = 900
    I = np.zeros(n)
    I[rng.choice(n, 25, replace=False)] = 1.0
    x = rng.normal(0, 0.1, n)
    y = 0.03 * I + 0.2 * x + rng.exponential(0.05, n) * (1 + 3 * I) - 0.05
    t = m.coef_test(y, I, x, 30, n_boot=400, seed=3)
    bs = m._boot_coef(y, I, x, 30, 400, 3)
    assert t["ci"] == pytest.approx([np.quantile(bs, 0.05), np.quantile(bs, 0.95)])
    assert t["p"] == pytest.approx((np.sum(bs <= 0) + 1) / (bs.size + 1))
    basic_up = t["coef"] - np.quantile(bs - t["coef"], 0.05)
    assert abs(basic_up - t["ci"][1]) > 1e-3                 # the skewed draws separate the two constructions


def test_fear_greed_grid_has_72_cells():
    px, fng, _ = _fng_world(0.1, last="2021-12-31", spacing=60)
    j = m.fear_greed_study(px, px, fng, grid=True)
    assert len(j["cells"]) == 72 and j["dsr"]["n_trials"] == 72


# ============================================================================================ T-484 =====

def test_par_bond_duration_convexity_and_carry():
    D, C = m.par_bond_dc(5.0)
    assert D == pytest.approx((1 - 1.025 ** -20) / 0.05, rel=1e-9) and 60 < C < 90
    r = m.synthetic_returns([6.0, 6.0, 6.5])
    assert np.isnan(r[0]) and r[1] == pytest.approx(0.005) and r[2] < 0


def _bond_world(kind: str, seed: int = 7):
    rng = np.random.default_rng(seed)
    months = []
    mm = "1962-01"
    while mm <= "2026-09":
        months.append(mm)
        mm = m._month_add(mm, 1)
    me = [_last_wd(x) for x in months]
    y = np.empty(len(months))
    y[0] = 6.0
    for t in range(1, len(months)):
        if kind == "trend":
            y[t] = y[t - 1] + (0.12 if (t // 36) % 2 == 0 else -0.12) + rng.normal(0, 0.03)
        else:
            y[t] = min(15.0, max(1.0, y[t - 1] + rng.normal(0, 0.25)))
    fred10 = {d: (float(v), d + "T20:00:00+00:00") for d, v in zip(me, y)}
    bills = Bills({d: 3.0 for d in me})
    S = m.bond_series(fred10, bills)
    i0 = months.index("2002-07")
    r = m.synthetic_returns(y)
    adj = 50 * np.cumprod(1 + np.r_[0.0, r[i0 + 1:]])
    ief = (me[i0:], adj)
    return S, ief, bills


def test_bond_tsmom_planted_passes():
    S, ief, bills = _bond_world("trend")
    j = m.bond_tsmom(S, ief, bills)
    assert j["n"] >= 700 and j["validation"]["corr"] > 0.999
    assert [c[1] for c in j["criteria"]] == [True, True, True, True] and j["verdict"] == "supported"


def test_bond_tsmom_null_does_not_pass():
    S, ief, bills = _bond_world("rw")
    j = m.bond_tsmom(S, ief, bills)
    assert j["verdict"] != "supported"


def test_tsmom_window_skips_the_latest_month():
    x = np.zeros(30)
    x[11] = -0.5                                            # only the most recent month at decision t = 11 is negative
    months = [f"2000-{k:02d}" for k in range(1, 13)] + [f"2001-{k:02d}" for k in range(1, 13)] + [f"2002-{k:02d}" for k in range(1, 7)]
    x[:11] = 0.01
    P = m.tsmom_vs_hist(x, months, "LS", 12, cost=0.0, start="", end="9999")
    assert P["labels"][0] == months[12] and P["w_t"][0] == 1.0   # months 1..11 positive -> long despite month 12


# ======================================================================================= harnesses (fake) =====

def _fake_bundles():
    rng = np.random.default_rng(21)
    b = {}
    # SPY / ^GSPC / ES=F with quarterly dividends and a synthetic basis
    es, gs, spy, _ = _es_world(0.004, seed=5, first="2003-01-02")
    sd = spy[0]
    b["daily-history-SPY"] = _yahoo(sd, spy[1], spy[2])
    b["daily-history--GSPC"] = _yahoo(gs[0], gs[1])
    b["daily-history-ES-F"] = _yahoo(es[0], es[1], hour="04:00")
    # GLD / SLV / GC=F / SI=F
    gd2 = wdays("2004-11-18", "2014-12-31")
    sp2 = 400 * np.exp(np.cumsum(rng.normal(0, 0.01, len(gd2))))
    dd = np.array([(m.last_trade_day(*m.front_contract(date.fromisoformat(d), m.GC_MONTHS)) - date.fromisoformat(d)).days for d in gd2])
    b["daily-history-GC-F"] = _yahoo(gd2, sp2 * np.exp(0.02 * dd / 365), hour="04:00")
    gld_px = sp2 * np.array([m.ounces_per_share(d, m.GLD_OZ0, m.GLD_FEE, m.GLD_LAUNCH) for d in gd2])
    b["daily-history-GLD"] = _yahoo(gd2, gld_px)
    slv_ix = [i for i, d in enumerate(gd2) if d >= "2006-04-28"]
    b["daily-history-SLV"] = _yahoo([gd2[i] for i in slv_ix], [gld_px[i] / 60 * math.exp(0.1 * math.sin(i / 50)) for i in slv_ix])
    b["daily-history-SI-F"] = _yahoo(gd2, sp2 / 60, hour="04:00")
    # crypto + fear & greed
    px, fng, _ = _fng_world(0.05, last="2022-03-31", spacing=45)
    bd = sorted(px)
    b["daily-history-BTC-USD"] = _yahoo(bd, [px[d] for d in bd], hour="00:00")
    b["daily-history-ETH-USD"] = _yahoo(bd, [px[d] * 0.05 for d in bd], hour="00:00")
    fk = sorted(fng)
    b["crypto-fear-greed-history"] = _fng_rows(fk, [fng[d][0] for d in fk])
    # FRED + IEF
    S, ief, _ = _bond_world("rw")
    months = S["months"]
    me = [_last_wd(x) for x in months]
    b["fred-DGS10"] = _fred_rows(me, S[10]["y"])
    b["fred-DGS2"] = _fred_rows([d for d in me if d >= "1976-06-01"], [3.0 + 0.001 * k for k, d in enumerate(me) if d >= "1976-06-01"])
    wk = wdays("1960-01-04", "2026-10-09")[::5]
    b["fred-DTB3"] = _fred_rows(wk, [2.0] * len(wk))
    b["daily-history-IEF"] = _yahoo(ief[0], ief[1])
    return b


@pytest.fixture(scope="module")
def fake_bundles():
    return _fake_bundles()


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_harness_runs_on_fake_archive(fake_bundles, name):
    a = FakeArchive(fake_bundles)
    stat, n, verdict, reason = m.HARNESSES[name](a)
    _json_ok(stat)
    assert verdict in ("supported", "not_supported", "inconclusive")
    assert isinstance(n, int) and " — " in reason
    assert reason.split(" — ")[-1].startswith(("failed", "implemented", "all criteria"))


@pytest.mark.parametrize("name", sorted(m.HARNESSES))
def test_harness_missing_bundles_inconclusive(name):
    stat, n, verdict, reason = m.HARNESSES[name](FakeArchive({}))
    assert verdict == "inconclusive" and n == 0 and stat["missing_bundles"]
    _json_ok(stat)


def test_theory_map_covers_the_six():
    assert set(m.THEORY_MAP) == {"T-318", "T-326", "T-372", "T-416", "T-484", "T-370"}
    assert set(m.THEORY_MAP.values()) == set(m.HARNESSES)
    assert all(k.startswith("b6c_misc_") and k == k.lower() for k in m.HARNESSES)


def test_t318_fake_below_min_n_never_supported(fake_bundles):
    stat, n, verdict, reason = m.HARNESSES["b6c_misc_ta_reality_check"](FakeArchive(fake_bundles))
    assert n < m.T318_MIN_N and verdict != "supported" and "88 long/flat rules" in reason
