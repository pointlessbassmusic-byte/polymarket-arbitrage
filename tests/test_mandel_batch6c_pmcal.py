"""Synthetic tests for mandel.experiments.batch6c_pmcal: a planted effect that passes and a null that does not, per core
function, plus the harness contract (missing bundles, JSON-safe stat, verdict set) on a fake archive. No network, no real
archive."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import numpy as np
import pytest

from mandel.experiments import batch6c_pmcal as M

DAY = 86_400.0
T0 = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _market(mid: str, end_ts: float, outcome: int, event: str, start_ts: float, fees: bool = False, closed_ts: float = None) -> dict:
    return {"id": mid, "umaResolutionStatus": "resolved", "outcomePrices": json.dumps(["1", "0"] if outcome else ["0", "1"]),
            "outcomes": json.dumps(["Yes", "No"]), "closedTime": _iso(closed_ts if closed_ts is not None else end_ts + 3600), "endDate": _iso(end_ts),
            "startDate": _iso(start_ts), "volumeNum": 50_000.0, "events": [{"id": event}], "feesEnabled": fees, "feeType": "politics_fees" if fees else None,
            "umaEndDate": _iso(end_ts), "question": f"Q {mid}", "negRisk": False}


def _rate(_ts: float) -> float:
    return 0.04


# ---------------------------------------------------------------------------------------------------- T-12 ---

def _quartile_data(planted: bool, n: int = 800, seed: int = 0):
    rng = np.random.default_rng(seed)
    vol = rng.lognormal(10, 1.5, n)
    truth = rng.uniform(0.05, 0.95, n)
    o = (rng.random(n) < truth).astype(int)
    rank = np.argsort(np.argsort(vol)) / n
    noise = (0.45 * (1 - rank) if planted else 0.25) * rng.normal(size=n)
    p = np.clip(truth + noise, 0.01, 0.99)
    keys = [f"e{i // 2}" for i in range(n)]
    return p, o, vol, keys


def test_volume_quartile_skill_planted_rises_and_gap_positive():
    p, o, vol, keys = _quartile_data(True)
    r = M.volume_quartile_skill(p, o, vol, keys, n_boot=300)
    assert r["monotone"] is True
    assert r["gap_ci"][0] > 0
    assert sum(r["n_per_quartile"]) == 800


def test_volume_quartile_skill_null_no_gap():
    p, o, vol, keys = _quartile_data(False)
    r = M.volume_quartile_skill(p, o, vol, keys, n_boot=300)
    assert not (r["monotone"] and r["gap_ci"][0] > 0)
    assert r["gap_ci"][0] <= 0 <= r["gap_ci"][1]


def _sharp_price(rng, planted: bool, rank: float) -> tuple[float, int]:
    """(price, outcome) of a market whose truth is extreme (Beta(0.3, 0.3)): a planted market's price is the truth shrunk towards
    0.5 by a factor that grows with its volume rank (sharper prices at higher volume: resolution), a null market's by a flat 0.6."""
    truth = rng.beta(0.3, 0.3) * 0.98 + 0.01
    o = int(rng.random() < truth)
    s = 0.1 + 0.9 * rank ** 2 if planted else 0.6
    return float(np.clip(0.5 + (truth - 0.5) * s + 0.03 * rng.normal(), 0.01, 0.99)), o


def _quartile_data_sharp(planted: bool, n: int = 2000, seed: int = 0):
    rng = np.random.default_rng(seed)
    vol = rng.lognormal(10, 1.5, n); rank = np.argsort(np.argsort(vol)) / n
    po = [_sharp_price(rng, planted, rank[i]) for i in range(n)]
    return np.array([x[0] for x in po]), np.array([x[1] for x in po]), vol, [f"e{i // 2}" for i in range(n)]


def test_volume_quartile_skill_reports_per_quartile_and_increment_intervals():
    p, o, vol, keys = _quartile_data_sharp(True)
    r = M.volume_quartile_skill(p, o, vol, keys, n_boot=300, age=np.linspace(1, 40, 2000))
    assert len(r["skill_ci"]) == 4 and all(c[0] <= s <= c[1] for s, c in zip(r["skill"], r["skill_ci"]))
    assert len(r["increment"]) == 3 and all(abs(r["increment"][k] - (r["skill"][k + 1] - r["skill"][k])) < 1e-12 for k in range(3))
    assert all(c[0] <= d <= c[1] for d, c in zip(r["increment"], r["increment_ci"]))
    assert all(c[0] > 0 for c in r["increment_ci"])               # every planted adjacent rise is resolved
    assert r["monotone"] and r["gap_ci"][0] > 0 and abs(sum(r["increment"]) - r["gap"]) < 1e-12
    assert len(r["median_age_days_per_quartile"]) == 4 and r["corr_log_volume_log_age"] is not None
    p, o, vol, keys = _quartile_data_sharp(False)
    r0 = M.volume_quartile_skill(p, o, vol, keys, n_boot=300)
    assert all(c[0] <= 0 <= c[1] for c in r0["increment_ci"])    # null: every adjacent increment includes 0
    assert not (r0["monotone"] and r0["gap_ci"][0] > 0)


def _volume_archive(n_sample: int, n_family: int, planted_sample: bool, planted_family: bool, n_young: int = 0, log_reasons: bool = True, seed: int = 9):
    """Fake archive for the T-12 harness: markets with a daily price at close - 7 d (and other days), one hourly volume row per
    market before the decision, and fetch-log rows giving each market's selection reason ('sample' or 'family:cpi') and a
    complete trade history. A planted set has price noise shrinking with the volume rank; a null set has flat noise."""
    rng = np.random.default_rng(seed)
    markets, daily, volume, log = [], [], [], []
    specs = [("sample", planted_sample)] * n_sample + [("family:cpi", planted_family)] * n_family
    vols = {}
    for grp in ("sample", "family:cpi"):
        idx = [i for i, (g, _) in enumerate(specs) if g == grp]
        v = rng.lognormal(10, 1.5, len(idx)); rank = np.argsort(np.argsort(v)) / max(len(idx), 1)
        for j, i in enumerate(idx):
            vols[i] = (float(v[j]), float(rank[j]))
    for i, (grp, planted) in enumerate(specs):
        mid = f"m{i}"; end = T0 + (30 + i // 3) * DAY; v, rank = vols[i]
        p, o = _sharp_price(rng, planted, rank)
        start = end - (9 * DAY if i < n_young else 30 * DAY)        # a 'young' market is 2 d old at the decision (close - 7 d)
        markets.append({"value": _market(mid, end, o, f"e{i // 2}", start)})
        for k in range(20, 0, -1):
            daily.append({"value": {"market_id": mid, "token": "t", "p": p, "t": float(end - k * DAY)}, "available_at": _iso(end - k * DAY)})
        hour = float(((end - 10 * DAY) // 3600) * 3600)
        volume.append({"value": {"market_id": mid, "t": hour, "shares": v}, "available_at": _iso(hour + 3600)})
        if log_reasons:
            log.append({"value": {"product": "daily", "id": mid, "reason": grp}})
        log.append({"value": {"product": "trades", "id": mid, "complete": True}})
    return FakeArchive({"polymarket-closed-markets": markets, "polymarket-price-history-daily": daily, "polymarket-fetch-log": log,
                        "polymarket-volume-hourly-2025-02": volume})


def test_volume_harness_scores_the_hash_sample_not_the_family_mixture():
    # the family markets carry the planted volume-skill relation, the hash sample does not: the criteria must be scored on the sample
    stat, n, verdict, reason = M.b6c_pmcal_volume_calibration(_volume_archive(420, 300, planted_sample=False, planted_family=True), n_boot=60)
    assert n == 420 and stat["n_primary"] == 420 and stat["n_with_pit_volume"] == 720
    assert stat["pit_volume_quartiles"]["n"] == 420 and stat["family_inclusive_mixture_sensitivity"]["n"] == 720
    assert stat["selection_reasons_pit"] == {"family:cpi": 300, "sample": 420}
    assert verdict != "supported" and "hash sample" in reason and "family-inclusive mixture" in reason and "quote skill" in reason
    json.dumps(stat)


def test_volume_harness_planted_sample_passes_and_reports_age_sensitivity():
    stat, n, verdict, reason = M.b6c_pmcal_volume_calibration(_volume_archive(480, 40, planted_sample=True, planted_family=False, n_young=60), n_boot=60)
    assert n == 480 and verdict == "supported" and reason.endswith("all criteria pass")
    res = stat["pit_volume_quartiles"]
    assert res["monotone"] is True and res["gap_ci"][0] > 0 and len(res["skill_ci"]) == 4 and len(res["increment_ci"]) == 3
    assert stat["age_at_least_7d_sensitivity"]["n"] == 420                # the 60 markets listed 2 d before the decision are excluded
    assert "age confound" in reason and "adjacent increments" in reason
    json.dumps(stat)


def test_volume_harness_without_sample_reasons_is_inconclusive_and_names_it():
    stat, n, verdict, reason = M.b6c_pmcal_volume_calibration(_volume_archive(60, 0, planted_sample=True, planted_family=False, log_reasons=False), n_boot=30)
    assert verdict == "inconclusive" and n == 0 and "sample" in stat["missing"] and "polymarket-fetch-log" in stat["missing"]
    assert stat["family_inclusive_mixture_sensitivity"]["n"] == 60 and "reported only" in reason
    json.dumps(stat)


def test_pit_volume_routes():
    hours = np.array([0.0, 3600.0, 7200.0]); cum = np.cumsum([10.0, 20.0, 30.0])
    assert M.pit_volume(hours, cum, 7203.0, {"complete": True}) == 30.0        # the 7200 hour has not ended at 7203
    assert M.pit_volume(hours, cum, 10800.0, {"complete": True}) == 60.0
    assert M.pit_volume(hours, cum, 3600.0, {"complete": True}) == 10.0
    assert M.pit_volume(hours, cum, 3600.0, {"complete": False, "complete_from_hour": 3600.0, "volumeNum": 100.0}) == 50.0
    assert M.pit_volume(hours, cum, 7203.0, {"complete": False, "complete_from_hour": 3600.0, "volumeNum": 100.0}) == 70.0
    assert M.pit_volume(hours, cum, 3600.0, {"complete": False, "complete_from_hour": 7200.0, "volumeNum": 100.0}) is None
    assert M.pit_volume(hours, cum, 3600.0, None) is None


# --------------------------------------------------------------------------------------------------- T-378 ---

def _carry_world(calibrated: bool, n: int = 600, seed: int = 1):
    rng = np.random.default_rng(seed)
    outcomes, series, meta = {}, {}, {}
    for i in range(n):
        mid = f"m{i}"; end = T0 + (30 + i) * DAY; q = 0.96
        win = (rng.random() < q) if calibrated else True
        yes_fav = i % 2 == 0
        outcome = int(win) if yes_fav else int(not win)
        days_pts = np.arange(40, 0, -1)
        ts = end - days_pts * DAY
        p_fav = np.where(days_pts > 3 + (i % 7), 0.80, q)       # enters the bin 4-10 days out
        ps = p_fav if yes_fav else 1 - p_fav
        series[mid] = (ts, ps.astype(float))
        m = _market(mid, end, outcome, f"ev{i}", end - 60 * DAY)
        meta[mid] = M._slim(m)
    outcomes = M.resolved_outcomes([{"value": s} for s in meta.values()])
    return outcomes, series, meta


def test_carry_planted_favorites_clear_hurdle():
    outs, series, meta = _carry_world(calibrated=False)
    obs = M.carry_observations_pm(outs, series, meta, _rate)
    assert len({o["mid"] for o in obs}) == 600 and all(o["win"] == 1 for o in obs)
    assert all(len({o["bucket"] for o in obs if o["mid"] == m}) == len([o for o in obs if o["mid"] == m]) for m in ("m0", "m6"))
    st = M.carry_stats(obs, n_boot=300)
    assert st["by_event"]["ci"][0] > 0 and st["by_resolution_day"]["ci"][0] > 0
    assert st["largest_cluster_profit_share"] < 0.5


def test_carry_null_calibrated_fails():
    outs, series, meta = _carry_world(calibrated=True)
    obs = M.carry_observations_pm(outs, series, meta, _rate)
    st = M.carry_stats(obs, n_boot=300)
    assert st["by_event"]["ci"][0] <= 0
    assert st["mean_excess"] < 0


def test_carry_eligibility_and_bucket_use_the_scheduled_end_not_the_realized_close():
    # A: scheduled end 200 d out, resolved early at day 20; price 0.96 at day 10 = 190 d to the scheduled end (not eligible), 10 d to the realized close
    # B: scheduled end 40 d out, resolved early at day 15; price 0.96 at day 12 = 28 d scheduled (bucket 8-30), 3 d realized (bucket 1-7)
    mA = _market("A", T0 + 200 * DAY, 1, "eA", T0, closed_ts=T0 + 20 * DAY)
    mB = _market("B", T0 + 40 * DAY, 1, "eB", T0, closed_ts=T0 + 15 * DAY)
    meta = {"A": M._slim(mA), "B": M._slim(mB)}
    series = {"A": (np.array([T0 + 10 * DAY]), np.array([0.96])), "B": (np.array([T0 + 12 * DAY]), np.array([0.96]))}
    outs = M.resolved_outcomes([{"value": s} for s in meta.values()])
    sched = M.carry_observations_pm(outs, series, meta, _rate)
    real = M.carry_observations_pm(outs, series, meta, _rate, days_basis="realized")
    assert [o["mid"] for o in sched] == ["B"] and sched[0]["bucket"] == 1 and sched[0]["days"] == pytest.approx(28) and sched[0]["hold"] == pytest.approx(3)
    assert sched[0]["days_to_realized_close"] == pytest.approx(3) and sched[0]["days_basis"] == "scheduled"
    assert sorted(o["mid"] for o in real) == ["A", "B"] and {o["mid"]: o["bucket"] for o in real} == {"A": 1, "B": 0}
    # a market without a scheduled end date cannot be taken under the rule (skipped); the realized construction admits it
    mC = _market("C", T0 + 30 * DAY, 1, "eC", T0, closed_ts=T0 + 30 * DAY); mC["endDate"] = None
    meta["C"] = M._slim(mC); series["C"] = (np.array([T0 + 20 * DAY]), np.array([0.97]))
    outs = M.resolved_outcomes([{"value": s} for s in meta.values()])
    assert "C" not in {o["mid"] for o in M.carry_observations_pm(outs, series, meta, _rate)}
    assert "C" in {o["mid"] for o in M.carry_observations_pm(outs, series, meta, _rate, days_basis="realized")}
    with pytest.raises(ValueError):
        M.carry_observations_pm(outs, series, meta, _rate, days_basis="whatever")


def test_carry_stats_reports_short_hold_weight():
    obs = []
    for i in range(50):
        hold = 1.0 if i < 5 else 20.0; ex = 5.0 if hold <= 2 else 0.1
        obs.append({"venue": "polymarket", "mid": f"m{i}", "cluster": f"e{i}", "res_day": "2025-01-01", "t": T0 + i, "q": 0.96, "side": 1, "win": 1, "fee": 0.0,
                    "days": hold, "hold": hold, "bucket": 0, "rf": 0.04, "r_ann": ex, "excess": ex, "excess_single_rf": ex, "profit": 0.04, "year": 2025})
    st = M.carry_stats(obs, n_boot=50)
    sh = st["short_hold"]
    assert sh["n_obs"] == 5 and sh["share_of_obs"] == pytest.approx(0.1) and sh["mean_excess"] == pytest.approx(5.0)
    assert sh["contribution_to_pooled_mean"] == pytest.approx(25.0 / 50) and sh["pooled_mean"] == pytest.approx(st["mean_excess"])
    assert sh["mean_excess_longer_holds"] == pytest.approx(0.1)
    assert M.short_hold_contribution([]) is None


def test_carry_harness_reports_scheduled_basis_and_realized_sensitivity():
    fa = _fake_archive(True)
    fa.b["fred-DTB3"] = [{"value": {"value": 4.0}, "available_at": _iso(T0 - DAY)}]
    stat, n, verdict, reason = M.b6c_pmcal_near_certain_carry(fa, n_boot=50)
    assert n > 0 and stat["days_basis"].startswith("scheduled") and "scheduled endDate" in reason
    sr = stat["realized_close_sensitivity"]
    assert sr is not None and sr["n_obs"] == stat["pooled"]["n_obs"]       # closedTime = endDate + 1 h in the fake world: the constructions coincide
    assert stat["pooled"]["short_hold"]["n_obs"] >= 0 and "hold <= 2 d" in reason and "realized-close construction" in reason
    json.dumps(stat)


def test_carry_kalshi_observations_use_ask_and_fee():
    t = T0 + np.arange(10) * DAY
    kal = {"markets": {"K-1": {"result": 1, "close_ts": T0 + 12 * DAY, "settle_ts": T0 + 12 * DAY + 3600, "event": "E", "open_ts": T0, "series": "KXCPI"}},
           "candles": {"K-1": (t, np.full(10, 0.95), np.full(10, 0.97), np.full(10, 0.96))}}
    obs = M.carry_observations_kalshi(kal, _rate)
    assert len(obs) == 2 and {o["bucket"] for o in obs} == {0, 1}          # 12 days to close: one entry in the 8-30 and one in the 1-7 bucket
    assert all(o["q"] == 0.97 and o["side"] == 1 and o["win"] == 1 for o in obs)
    assert obs[0]["fee"] == pytest.approx(0.07 * 0.97 * 0.03)
    kal["candles"]["K-1"] = (t, np.full(10, 0.02), np.full(10, 0.04), np.full(10, 0.03))
    kal["markets"]["K-1"]["result"] = 0
    obs = M.carry_observations_kalshi(kal, _rate)
    assert len(obs) == 2 and all(o["side"] == 0 and o["q"] == pytest.approx(0.98) and o["win"] == 1 for o in obs)


# ---------------------------------------------------------------------------------------------------- T-31 ---

def _wf_data(nonlinear: bool, n: int = 2400, seed: int = 2):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 3))
    z = 3.0 * X[:, 0] * X[:, 1] if nonlinear else 1.5 * X[:, 0] + 0.5 * X[:, 1]
    y = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(float)
    market = [f"m{i}" for i in range(n)]
    close = T0 + np.arange(n) * DAY / 4
    return X, y, market, close, market


def test_logit_vs_mlp_planted_nonlinearity_wins():
    X, y, mk, close, keys = _wf_data(True)
    r = M.logit_vs_mlp(X, y, mk, close, keys, n_boot=300)
    assert r["n_markets_tested"] > 1000
    assert r["diff_mean"] < 0 and r["diff_ci"][1] < 0


def test_logit_vs_mlp_null_linear_does_not_win():
    X, y, mk, close, keys = _wf_data(False)
    r = M.logit_vs_mlp(X, y, mk, close, keys, n_boot=300)
    assert not (r["diff_mean"] < 0 and r["diff_ci"][1] < 0)


def test_logit_vs_mlp_embargo_training_before_test_close():
    X, y, mk, close, keys = _wf_data(False, n=600)
    r = M.logit_vs_mlp(X, y, mk, close, keys, n_boot=50, n_folds=2)
    for f in r["folds"]:
        assert f["n_train"] > 0 and f["n_test"] > 0


# ---------------------------------------------------------------------------------------------------- T-32 ---

def _rank_world(one_factor: bool, n_units: int = 90, days: int = 400, seed: int = 3):
    rng = np.random.default_rng(seed)
    f = rng.normal(size=days)
    out = {}
    for i in range(n_units):
        e = rng.normal(size=days)
        dx = (f + 0.15 * e) if one_factor else e
        p = np.clip(0.5 + 0.01 * np.cumsum(dx), 0.02, 0.98)
        out[f"u{i}"] = (np.arange(days) + 20000, p, None)
    return out


def test_low_rank_planted_one_factor():
    r = M.low_rank_windows(_rank_world(True), 20000, 20400, T=120, step=60, cap=60, min_markets=50)
    assert r["n_windows_scored"] >= 3
    assert r["pooled_ratio"] < 0.1 and r["pooled_lam1_over_plus"] > 1


def test_low_rank_null_independent_noise():
    r = M.low_rank_windows(_rank_world(False), 20000, 20400, T=120, step=60, cap=60, min_markets=50)
    assert r["n_windows_scored"] >= 3
    assert r["pooled_ratio"] > 0.5 and r["pooled_lam1_over_plus"] < 1.3


def test_low_rank_skips_thin_windows():
    r = M.low_rank_windows(_rank_world(True, n_units=20), 20000, 20400, T=120, step=60, cap=60, min_markets=50)
    assert r["n_windows_scored"] == 0 and r["n_max_candidates"] == 20


# --------------------------------------------------------------------------------------------------- T-359 ---

def _late_world(planted: bool, n: int = 700, seed: int = 4):
    rng = np.random.default_rng(seed)
    series, meta = {}, {}
    for i in range(n):
        mid = f"m{i}"; end = T0 + (20 + i // 2) * DAY
        yes_fav = i % 2 == 0
        q_final, q14 = 0.92, 0.96
        win = True if planted else bool(rng.random() < q_final)
        outcome = int(win) if yes_fav else int(not win)
        days_pts = np.arange(20, 0, -1)
        ts = end - days_pts * DAY + 5
        fav = np.where(days_pts >= 10, q14, q_final)
        ps = fav if yes_fav else 1 - fav
        series[mid] = (ts, ps.astype(float))
        meta[mid] = M._slim(_market(mid, end, outcome, f"e{i // 3}", end - 30 * DAY))
    outs = M.resolved_outcomes([{"value": s} for s in meta.values()])
    return outs, series, meta


def test_late_favorite_planted_passes_every_criterion():
    outs, series, meta = _late_world(True)
    r = M.late_favorite(outs, series, meta, n_boot=300)
    assert r["n_entries"] == 700 and r["entries_by_day"]["3"] == 700
    assert r["mean_net_return"] > 0 and r["p_cluster"] < 0.05 and r["p_parametric_bernoulli"] < 0.05
    assert r["calibration_slope"]["slope"] > 1
    assert all(h["mean"] > 0 for h in r["halves"])
    assert r["day14"]["diff"] > 0 and r["day14"]["n_day14"] == 700 and r["day14"]["n_final3"] == 700
    assert r["day14_paired_sensitivity"]["paired_diff"] > 0


def _late_world_crash(n_each: int = 60, seed: int = 11):
    """Set A: leading side 0.95 at day 14, 0.97 in the final 3 days, wins. Set B: 0.95 at day 14, crashes to 0.50 by the final
    3 days (never qualifies there) and loses. The unconditional day-14 rule holds A and B; the both-horizons pairing sees A only."""
    series, meta = {}, {}
    for i in range(2 * n_each):
        mid = f"m{i}"; end = T0 + (20 + i // 2) * DAY; crash = i >= n_each
        yes_fav = i % 2 == 0
        win = not crash
        outcome = int(win) if yes_fav else int(not win)
        days_pts = np.arange(20, 0, -1)
        ts = end - days_pts * DAY + 5
        fav = np.where(days_pts >= 10, 0.95, 0.50 if crash else 0.97)
        ps = fav if yes_fav else 1 - fav
        series[mid] = (ts, ps.astype(float))
        meta[mid] = M._slim(_market(mid, end, outcome, f"e{i // 3}", end - 30 * DAY))
    outs = M.resolved_outcomes([{"value": s} for s in meta.values()])
    return outs, series, meta


def test_late_favorite_day14_contrast_is_unconditional_not_paired_on_staying_in_the_bin():
    outs, series, meta = _late_world_crash()
    r = M.late_favorite(outs, series, meta, n_boot=300)
    d14 = r["day14"]; pr = r["day14_paired_sensitivity"]
    assert r["n_entries"] == 60                                   # only set A qualifies in the final 3 days
    assert d14["n_day14"] == 120 and d14["n_day14_also_final3"] == 60 and d14["n_day14_not_final3"] == 60
    assert d14["mean_day14_not_final3"] < -0.9 and d14["mean_net_return_day14"] < 0   # the crashes belong to the day-14 rule
    assert d14["diff"] > 0 and d14["diff_ci"][0] > 0                                     # final-3 beats the day-14 rule as executed
    assert pr["n"] == 60 and pr["paired_diff"] < 0                                       # the conditioned pairing says the opposite
    assert "conditioned" in pr["note"]


def test_cluster_mean_diff_shares_cluster_draws():
    a = np.array([1.0, 1.0, 1.0, 1.0]); b = np.array([1.0, 1.0, 1.0, 1.0])
    r = M.cluster_mean_diff(a, ["c0", "c1", "c2", "c3"], b, ["c0", "c1", "c2", "c3"], n_boot=100)
    assert r["diff"] == 0 and r["ci"] == [0.0, 0.0] and r["n_clusters"] == 4
    rng = np.random.default_rng(0)
    a = rng.normal(0.5, 1, 400); b = rng.normal(0.0, 1, 400)
    r = M.cluster_mean_diff(a, [f"a{i // 4}" for i in range(400)], b, [f"b{i // 4}" for i in range(400)], n_boot=300)
    assert r["ci"][0] > 0 and r["ci"][0] <= r["diff"] <= r["ci"][1]


def test_late_favorite_null_calibrated_fails():
    outs, series, meta = _late_world(False)
    r = M.late_favorite(outs, series, meta, n_boot=300)
    assert r["mean_net_return"] < 0 or r["p_cluster"] >= 0.05
    assert r["p_parametric_bernoulli"] >= 0.05


def test_late_favorite_skips_post_outcome_prices():
    outs, series, meta = _late_world(True, n=10)
    mid = "m0"; s = dict(meta[mid]); end = M._ts(s["endDate"])
    s["closedTime"] = _iso(end - 10 * DAY)                      # resolved ten days before the scheduled end
    meta[mid] = s
    outs = M.resolved_outcomes([{"value": x} for x in meta.values()])
    r = M.late_favorite(outs, series, meta, n_boot=50)
    assert r["n_entries"] == 9


# --------------------------------------------------------------------------------------------------- T-316 ---

def _shock_world(continuation: bool, n: int = 150, days: int = 120, seed: int = 5):
    rng = np.random.default_rng(seed)
    series, info = {}, {}
    for i in range(n):
        x = np.zeros(days); x[0] = rng.normal(0, 0.3)
        shocks = set(rng.choice(np.arange(45, days - 10), size=2, replace=False))
        drift = 0.0; left = 0
        for t in range(1, days):
            step = rng.normal(0, 0.08)
            if t in shocks:
                sgn = rng.choice([-1.0, 1.0]); step = sgn * 0.6; drift = sgn * 0.2 if continuation else 0.0; left = 4
            elif left > 0:
                step += drift; left -= 1
            x[t] = x[t - 1] + step
        p = 1 / (1 + np.exp(-x)); ts = T0 + np.arange(days) * DAY + 3
        series[f"m{i}"] = (ts, p)
        info[f"m{i}"] = {"close_ts": ts[-1] + DAY, "end_ts": ts[-1] + DAY, "outcome": int(p[-1] > 0.5), "cluster": f"market:m{i}"}
    return series, info


def test_shock_planted_continuation_positive():
    series, info = _shock_world(True)
    ev, cells = M.shock_events(series, info)
    st = M.shock_stats(ev, cells, n_boot=300)
    assert st["n_events"] >= 100
    assert st["mean_net"] > 0.02 and st["ci"][0] > 0
    assert st["matched_controls"]["mean_diff"] > 0


def test_shock_null_random_walk_fails():
    series, info = _shock_world(False)
    ev, cells = M.shock_events(series, info)
    st = M.shock_stats(ev, cells, n_boot=300)
    assert st["n_events"] >= 100
    assert not (st["mean_net"] > 0.02 and st["ci"][0] > 0)
    assert st["mean_net"] < 0.02


def test_shock_events_do_not_overlap_within_a_market():
    series, info = _shock_world(True)
    ev, _ = M.shock_events(series, info)
    by = {}
    for e in ev:
        by.setdefault(e["mid"], []).append(e)
    for es in by.values():
        es.sort(key=lambda d: d["t"])
        for a, b in zip(es, es[1:]):
            assert b["t"] >= a["t"] + 4 * DAY - 10


# ---------------------------------------------------------------------------------------- harness contract ---

class _Entry:
    def __init__(self, name):
        self.name = name; self.created_at = "2026-10-16T00:00:00+00:00"


class FakeArchive:
    def __init__(self, bundles: dict):
        self.b = bundles

    def entries(self, kind=None, tag=None):
        return [_Entry(n) for n in self.b]

    def get(self, name):
        if name not in self.b:
            raise KeyError(name)
        return _Entry(name)

    def load(self, name):
        return iter(self.b[name])


def _fake_archive(planted: bool = True):
    outs, series, meta = _late_world(planted, n=460)
    markets = [{"value": _market(mid, M._ts(s["endDate"]), int(json.loads(s["outcomePrices"])[0] == "1"), s["event_id"], M._ts(s["startDate"]))} for mid, s in meta.items()]
    daily = [{"value": {"market_id": mid, "token": "t", "p": float(p), "t": float(t)}, "available_at": _iso(t)} for mid, (ts, ps) in series.items() for t, p in zip(ts, ps)]
    return FakeArchive({"polymarket-closed-markets": markets, "polymarket-price-history-daily": daily, "polymarket-fetch-log": []})


def test_missing_bundles_are_inconclusive_and_named():
    stat, n, verdict, reason = M.b6c_pmcal_late_favorite(FakeArchive({}))
    assert verdict == "inconclusive" and n == 0 and "polymarket-closed-markets" in reason and " — " in reason
    json.dumps(stat)


def test_harness_contract_on_fake_archive():
    stat, n, verdict, reason = M.b6c_pmcal_late_favorite(_fake_archive(True), n_boot=200)
    assert verdict in ("supported", "not_supported", "inconclusive") and n == 460
    assert verdict == "supported"
    json.dumps(stat)
    assert reason.endswith("all criteria pass")
    stat2, n2, verdict2, _ = M.b6c_pmcal_late_favorite(_fake_archive(False), n_boot=200)
    assert verdict2 == "not_supported" and n2 == 460
    json.dumps(stat2)


def test_volume_harness_without_trade_bundles_names_them():
    stat, n, verdict, reason = M.b6c_pmcal_volume_calibration(_fake_archive(True), n_boot=50)
    assert verdict == "inconclusive" and n == 0 and "polymarket-volume-hourly-<YYYY-MM>" in reason
    json.dumps(stat)


def test_harness_map_complete():
    assert set(M.THEORY_MAP) == {"T-12", "T-378", "T-31", "T-32", "T-359", "T-316"}
    assert set(M.THEORY_MAP.values()) == set(M.HARNESSES)
    assert all(k.startswith("b6c_pmcal_") for k in M.HARNESSES)
