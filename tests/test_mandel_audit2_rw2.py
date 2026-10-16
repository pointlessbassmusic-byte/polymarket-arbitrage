"""Round-2 regression tests for the runner (group rw2: mandel/experiments/run.py). Synthetic data and in-memory archives only.

Items: OM-1 (house rule 5: a failure below min_n counts only when decisive), OM-9 (T-13's chain includes 3d), OM-5 (T-36 calendar split),
OM-13 (T-bills into low_vol_tilt / metals_tsmom), XA-9 / XA-7 (T-266 null names the level statistic), vs OM-11 (T-19 arms),
vs OM-16 (overlay Sharpe-difference p on the reported excess basis), XA-6 (T-176 settles at Deribit delivery prices),
st OM-5 (structure_* nulls), vs OM-6 (T-03 three-valued signs_agree)."""

import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

import mandel.experiments.cross_asset as xa
import mandel.experiments.run as run
import mandel.experiments.underlying2 as u2
from mandel.archive import BundleEntry
from mandel.experiments.overfit import momentum_variants

REG = json.loads(Path(run.REGISTRY).read_text(encoding="utf-8"))
THEORY = {t["id"]: t for t in REG["theories"]}


class MemArchive:
    """Dict-backed stand-in for Archive: every bundle listed and on this machine; records the names loaded."""

    def __init__(self, bundles: dict):
        self._rows = dict(bundles); self.loaded = []

    def entries(self, kind=None, tag=None):
        return [BundleEntry(name=n, kind="data", path=n, created_at="2099-01-01T00:00:00+00:00", rows=0, bytes=0, sha256="") for n in sorted(self._rows)]

    def get(self, name):
        return BundleEntry(name=name, kind="data", path=name, created_at="2099-01-01T00:00:00+00:00", rows=0, bytes=0, sha256="")

    def load(self, name):
        self.loaded.append(name)
        return iter(self._rows[name])


def _daily_rows(sym, closes, start=datetime(2011, 10, 3, tzinfo=timezone.utc)):
    return [{"value": {"t": (start + timedelta(days=i)).timestamp(), "close": float(c), "day": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "symbol": sym}}
            for i, c in enumerate(closes)]


def _h(n, skill):
    """A market_calibration horizon entry (scored when n >= 20, as markets.market_calibration reports it)."""
    return {"n": n, "brier": 0.25 * (1 - skill), "skill_vs_coin": skill} if n >= 20 else {"n": n, "note": "too few"}


@pytest.fixture
def pm():
    return MemArchive({"polymarket-price-history-daily": [], "polymarket-closed-markets": []})


def _calib(monkeypatch, horizons):
    monkeypatch.setattr(run, "market_calibration", lambda *a, **k: {"n_resolved_markets": 999, "horizons": dict(horizons)})


# ----------------------------------------------------------- OM-1: rule 5, failures below min_n must be decisive --

def test_om1_market_calibration_thin_horizon_with_skill_below_zero_is_inconclusive(pm, monkeypatch):
    # the checker's case: 1/3/7/30d at n 400 with skill 0.8, 90d on 25 markets with skill -0.05. Was not_supported.
    _calib(monkeypatch, {1: _h(400, .8), 3: _h(400, .8), 7: _h(400, .8), 30: _h(400, .8), 90: _h(25, -.05)})
    stat, n, verdict, reason = run.harness_market_calibration(pm)
    assert (verdict, n) == ("inconclusive", 25) and "skill -0.05 <= 0 on n < min_n" in reason
    # on adequate data the same skill falsifies 'every horizon'
    _calib(monkeypatch, {1: _h(400, .8), 3: _h(400, .8), 7: _h(400, .8), 30: _h(400, .8), 90: _h(300, -.05)})
    assert run.harness_market_calibration(pm)[2] == "not_supported"
    # below min_n it is decisive only if it would fail at min_n even with every missing market forecast perfectly: n * Brier >= 300 * 0.25
    _calib(monkeypatch, {1: _h(400, .8), 3: _h(400, .8), 7: _h(400, .8), 30: _h(400, .8), 90: _h(290, -.5)})    # 290 * 0.375 = 108.75 >= 75
    assert run.harness_market_calibration(pm)[2] == "not_supported"


def test_om1_horizon_monotone_violation_on_a_thin_horizon_is_inconclusive(pm, monkeypatch):
    # skill(30d) <= skill(90d), but 90d has 250 markets: was not_supported
    _calib(monkeypatch, {1: _h(400, .80), 3: _h(400, .79), 7: _h(400, .75), 30: _h(400, .70), 90: _h(250, .72)})
    stat, n, verdict, reason = run.harness_horizon_monotone(pm)
    assert (verdict, n) == ("inconclusive", 250) and "skill(30d) <= skill(90d) with n < 300" in reason and not stat["monotone"]
    # a violation between two adequate horizons is decisive even when another horizon is thin
    _calib(monkeypatch, {1: _h(400, .70), 3: _h(400, .79), 7: _h(400, .75), 30: _h(400, .74), 90: _h(250, .60)})
    assert run.harness_horizon_monotone(pm)[2] == "not_supported"


def _pm_markets(spec, p=0.05, close=datetime(2026, 1, 1, tzinfo=timezone.utc)):
    """spec: list of (market_id, outcome); daily price p for the 10 days before close; no event ids (each market its own cluster)."""
    markets, prices = [], []
    for mid, o in spec:
        markets.append({"value": {"id": mid, "umaResolutionStatus": "resolved", "outcomePrices": json.dumps([str(float(o)), str(float(1 - o))]),
                                  "outcomes": json.dumps(["Yes", "No"]), "closedTime": close.isoformat(), "question": mid}})
        prices += [{"value": {"market_id": mid, "t": (close - timedelta(days=d)).timestamp(), "p": p}} for d in range(10, 0, -1)]
    return MemArchive({"polymarket-closed-markets": markets, "polymarket-price-history-daily": prices})


def test_om1_longshot_straddling_interval_below_min_n_is_inconclusive():
    # 150 cheap markets, 8 YES: mean error +0.003 with an interval straddling zero. Was not_supported (low power, not a failure).
    stat, n, verdict, reason = run.harness_longshot(_pm_markets([(f"m{i}", int(i < 8)) for i in range(150)]))
    assert stat["ci"][0] < 0 <= stat["ci"][1] and (verdict, n) == ("inconclusive", 150)
    # the whole interval above zero is decisive below min_n
    stat, n, verdict, reason = run.harness_longshot(_pm_markets([(f"m{i}", int(i < 40)) for i in range(150)]))
    assert stat["ci"][0] > 0 and verdict == "not_supported"


def test_om1_bundle_arb_thin_snapshots_cannot_falsify(monkeypatch):
    a = MemArchive({"polymarket-books-snapshot": [], "polymarket-books-2026-10-15": []})
    rep = {"markets_scanned": 150, "long_after_fees": 0, "short_after_fees": 0, "gross_long_candidates": 0, "median_round_trip_spread": .02,
           "examples_long": [], "examples_short": []}
    monkeypatch.setattr(run, "bundle_arb_scan", lambda rows: dict(rep))
    stat, n, verdict, reason = run.harness_bundle_arb(a)          # was not_supported on two snapshots of 150 < min_n 200 markets
    assert verdict == "inconclusive" and "needs >= 200 markets" in reason
    monkeypatch.setattr(run, "bundle_arb_scan", lambda rows: {**rep, "markets_scanned": 250})
    assert run.harness_bundle_arb(a)[2] == "not_supported"


def _series_archive(n_series, length=130):
    return MemArchive({"polymarket-price-history-daily": [{"value": {"market_id": f"m{k}", "t": float(i), "p": 0.5}} for k in range(n_series) for i in range(length)]})


def test_om1_hurst_below_min_n_falsifies_only_when_decisive(monkeypatch):
    # 20 series, all H < 0.5, none below the null: the share criterion fails on 20, but 20 more anti-persistent series could pass it
    monkeypatch.setattr(run, "hurst_with_interval", lambda x, n_null=200, seed=0: {"H": 0.45, "null_lo": 0.42, "null_hi": 0.58})
    assert run.harness_hurst(_series_archive(20))[2] == "inconclusive"          # was not_supported
    # 20 series all persistent (H 0.55): even 20 more anti-persistent ones leave H < 0.5 at 20/40, not > 50% -> decisive
    monkeypatch.setattr(run, "hurst_with_interval", lambda x, n_null=200, seed=0: {"H": 0.55, "null_lo": 0.42, "null_hi": 0.58})
    stat, n, verdict, reason = run.harness_hurst(_series_archive(20))
    assert verdict == "not_supported" and "fails even if every missing series counted" in reason


def test_om1_multifractal_below_min_n_falsifies_only_when_decisive(monkeypatch):
    class R:
        n, concavity, null_concavity_q95, exceeds_null = 130, 0.0, 0.05, False

    monkeypatch.setattr(run, "multifractal_test", lambda x, n_shuffles=200, **k: R())
    assert run.harness_multifractal(_series_archive(20))[2] == "inconclusive"   # 0/20; (0 + 20)/40 = 50% could pass: was not_supported
    assert run.harness_multifractal(_series_archive(35))[2] == "not_supported"  # 0/35; (0 + 5)/40 = 12.5% fails at min_n whatever comes


def test_om1_holdout_sharpe_below_min_n_is_inconclusive_whatever_the_sign(monkeypatch):
    a = _series_archive(120, length=61)
    t = np.arange(150, dtype=float)
    M = np.random.default_rng(1).normal(0, 0.01, size=(150, 21)); M[:, 0] += 0.01   # rule 0 wins in sample and stays positive
    monkeypatch.setattr(run, "_momentum_pnl_by_time", lambda s: [(f"r{j}", M[:, j], t, np.zeros(150, int)) for j in range(21)])
    stat, n, verdict, reason = run.harness_holdout_sharpe(a)
    assert stat["holdout_sharpe"] > 0 and n == 75 and verdict == "inconclusive"   # 75 < min_n 100; was not_supported


# ------------------------------------------------------------------------------- OM-9: T-13 includes 3d --

def test_om9_t13_chain_includes_3d_real_data_shape(pm, monkeypatch):
    # the measured skills (1d 0.780 < 3d 0.795 on n 389 / 382; 90d n 260): was inconclusive (3d dropped, 90d thin); the claim's data is
    # T-01's horizons, so 1d <= 3d on adequate data contradicts 'increases monotonically as the horizon shortens'
    _calib(monkeypatch, {1: _h(389, .780), 3: _h(382, .795), 7: _h(368, .743), 30: _h(337, .735), 90: _h(260, .689)})
    stat, n, verdict, reason = run.harness_horizon_monotone(pm)
    assert verdict == "not_supported" and stat["required"] == [1, 3, 7, 30, 90] and "skill(1d) <= skill(3d)" in reason
    _calib(monkeypatch, {1: _h(400, .80), 3: _h(400, .79), 7: _h(400, .75), 30: _h(400, .70), 90: _h(400, .65)})
    assert run.harness_horizon_monotone(pm)[2] == "supported"


# ---------------------------------------------------------------------------- OM-5: T-36 calendar split --

def _calendar_series(n_markets, rng, phi_before=0.5, phi_after=-0.5, cut_day=90):
    """Markets that all span the same calendar (start days 0..9, 150..190 days long). Daily price changes are AR(1) with phi_before
    before cut_day and phi_after from it: trending, then reverting, in calendar time for every market."""
    day, out = 86400.0, []
    for m in range(n_markets):
        start, L = m % 10, 150 + (m * 7) % 41
        t = 1.7e9 + day * (start + np.arange(L))
        d = np.zeros(L)
        for i in range(1, L):
            phi = phi_before if start + i < cut_day else phi_after
            d[i] = phi * d[i - 1] + rng.normal(0, 0.004)
        out.append((t, np.clip(0.5 + np.cumsum(d), 0.02, 0.98)))
    return out


def test_om5_every_rule_is_split_on_one_calendar_cutoff():
    rng = np.random.default_rng(7)
    series_t = _calendar_series(30, rng)
    rules = run._momentum_pnl_by_time(series_t, lookbacks=(1, 3, 21), holds=(1, 2, 3))
    # the construction is momentum_variants' own: concatenated per market, each rule's returns equal T-10's matrix column
    R, names = momentum_variants([p for _, p in series_t], lookbacks=(1, 3, 21), holds=(1, 2, 3))
    assert [r[0] for r in rules] == names and all(np.allclose(r[1][:R.shape[0]], R[:, j]) for j, r in enumerate(rules))
    cutoff = float(np.median(np.concatenate([te for _, _, te, _ in rules])))
    is_sets, ho_sets = set(), set()
    for name, pnl, te, m in rules:
        assert te.size == pnl.size == m.size
        is_sets.add(frozenset(m[te <= cutoff].tolist())); ho_sets.add(frozenset(m[te > cutoff].tolist()))
    assert is_sets == ho_sets == {frozenset(range(30))}             # every rule: the same 30 markets on both sides of one date
    # the old row split (first half of momentum_variants' truncated rows) put different markets in-sample for each rule
    order = sorted(range(30), key=lambda k: -series_t[k][1].size)
    old_is = []
    for lb, hd in ((1, 1), (3, 3), (21, 3)):
        per_market = [len(range(0, series_t[k][1].size - 1 - lb, hd)) for k in order]
        old_is.append(int(np.searchsorted(np.cumsum(per_market), R.shape[0] // 2, side="right")) + 1)
    assert len(set(old_is)) > 1


def test_om5_holdout_is_the_later_period_for_every_rule():
    rng = np.random.default_rng(11)

    def archive(series_t):
        return MemArchive({"polymarket-price-history-daily": [{"value": {"market_id": f"m{k}", "t": float(t), "p": float(p)}}
                                                              for k, (ts, ps) in enumerate(series_t) for t, p in zip(ts, ps)]})

    series_t = _calendar_series(120, rng)                           # momentum pays in sample, then reverses
    stat, n, verdict, reason = run.harness_holdout_sharpe(archive(series_t))
    rules = run._momentum_pnl_by_time(series_t)
    cutoff = float(np.median(np.concatenate([te for _, _, te, _ in rules])))
    assert stat["cutoff_t"] == cutoff and stat["n_variants"] == 21 and stat["n_is_markets"] == stat["n_holdout_markets"] == 120
    assert all(a + b == r[1].size for (a, b), r in zip(stat["per_rule_is_holdout_periods"].values(), rules))
    assert stat["is_best_sharpe"] > 0 and stat["holdout_sharpe"] < 0 and n >= 100 and verdict == "supported"
    stat, n, verdict, reason = run.harness_holdout_sharpe(archive(_calendar_series(120, np.random.default_rng(11), phi_after=0.5)))
    assert stat["holdout_sharpe"] > 0 and verdict == "not_supported"   # momentum keeps paying after the cutoff: T-36 fails


# -------------------------------------------------------------------- OM-13: T-bills into the u2 wrappers --

def _u2_archive(n_days=300):
    rng = np.random.default_rng(2)
    b = {run._dh(s)[0]: _daily_rows(s, 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n_days)))) for s in ("USMV", "SPY", "SPLV", "SPHB", "GLD", "SLV", "GC=F", "SI=F")}
    b["fred-DTB3"] = _daily_rows("DTB3", 5.04 * np.ones(n_days))
    return MemArchive(b)


def test_om13_low_vol_tilt_and_metals_tsmom_get_the_bills(monkeypatch):
    seen = {}
    monkeypatch.setattr(u2, "low_vol_tilt", lambda *x, **k: seen.update(lvt=k) or {"verdict": "inconclusive", "reason": "stub"})
    monkeypatch.setattr(u2, "metals_tsmom", lambda *x, **k: seen.update(mt=k) or {"verdict": "inconclusive", "reason": "stub", "n": 1})
    a = _u2_archive()
    run.HARNESSES["low_vol_tilt"](a); run.HARNESSES["metals_tsmom"](a)
    for key in ("lvt", "mt"):                                      # was: no bills, so the excess-over-bills criterion stayed None
        assert len(seen[key]["bill_days"]) == 300 and set(seen[key]["bill_vals"]) == {5.04}
    assert "fred-DTB3" in run.BUNDLES_NEEDED["low_vol_tilt"] and "fred-DTB3" in run.BUNDLES_NEEDED["metals_tsmom"]


def test_om13_low_vol_tilt_scores_excess_returns_end_to_end():
    stat, n, verdict, reason = run.HARNESSES["low_vol_tilt"](_u2_archive())
    assert stat["excess_over_bills"] and "excess Sharpe" in reason and "not supplied" not in reason


# underlying2.svxy_v2 is fixed by the u2 group (round 2, U2-1): until its Sharpe difference is taken on s - rf and b - rf, this run-path
# test is an expected failure; once the source changes it must pass.
_SVXY_TOTAL_RETURN_BASIS = "_sharpe_diff_lower(s, b," in inspect.getsource(u2.svxy_v2)


@pytest.mark.xfail(_SVXY_TOTAL_RETURN_BASIS, reason="underlying2.svxy_v2 still takes the Sharpe difference on total returns (u2 group, U2-1)", strict=True)
def test_om13_svxy_v2_run_path_scores_the_sharpe_difference_on_excess_returns():
    # svxy_v2 is not stubbed: SVXY prices plus a constant bill through the runner (raw prices + bills) must give the Sharpe difference of
    # the excess-index path, where every return is already net of the bill and cash days earn exactly the bill
    rng, n, start = np.random.default_rng(3), 3000, datetime(2016, 1, 4, tzinfo=timezone.utc)
    vix = 15 + 5 * np.abs(np.sin(np.arange(n) / 40))
    a = MemArchive({"daily-history-SVXY": _daily_rows("SVXY", 50 * np.exp(np.cumsum(rng.normal(0.0004, 0.03, n))), start),
                    "cboe-VIX-history": _daily_rows("VIX", vix, start), "cboe-VIX3M-history": _daily_rows("VIX3M", vix * (1 + 0.1 * np.sin(np.arange(n) / 17)), start),
                    "fred-DTB3": _daily_rows("DTB3", 5.04 * np.ones(n), start)})
    stat, _, _, _ = run.HARNESSES["svxy_v2"](a)
    ex = u2.svxy_v2(run._excess_index(run._ls(a, "SVXY"), run._bill(a)), run.index_closes(a.load("cboe-VIX-history")), run.index_closes(a.load("cboe-VIX3M-history")))
    assert stat["cash_leg"] == "T-bill" and stat["sharpe_diff"] == pytest.approx(ex["sharpe_diff"], abs=1e-9)


# ------------------------------------------------------------------ XA-9 / XA-7: T-266's null is the level form --

def test_xa7_eth_btc_null_names_the_level_statistic_of_t266():
    null = run._null_for("eth_btc_dvol_ratio")
    assert "RV_ETH/RV_BTC - DVOL_ETH/DVOL_BTC" in null and "ln(" not in null and "20th percentile" in null
    assert "RV_ETH/RV_BTC - DVOL_ETH/DVOL_BTC" in THEORY["T-266"]["trial"]["statistic"]
    for tid, h in run.XA_MAP.items():                              # log form in the null exactly when the registered statistic is in logs
        assert ("ln(" in run.XA_NULLS[h]) == ("ln(" in THEORY[tid]["trial"]["statistic"]), tid


# ------------------------------------------------------------------------ vs OM-11: T-19 naive vs honest arms --

def test_om11_point_in_time_compares_the_observed_at_join_with_the_available_at_join(monkeypatch):
    a = MemArchive({"crypto-fear-greed-history": [], "daily-history-BTC-USD": []})
    lags = []

    def fg(fng, px, lag_days=1, n_boot=500):
        lags.append(lag_days)
        return {"verdict": "supported" if lag_days < 0 else "not_supported", "d_fear": 0.01 if lag_days < 0 else 0.0, "n": 900}

    monkeypatch.setattr(run, "fear_greed_forward_returns", fg)
    stat, n, verdict, reason = run.harness_point_in_time(a)
    assert lags == [-1, 0] and verdict == "supported" and stat["naive"]["verdict"] == "supported"   # was lags 0 and 1: no look-ahead arm


def test_om11_naive_arm_sees_look_ahead_on_synthetic_data():
    # the index for day d is set by day d's own return (close(d-1) -> close(d)) and published at close(d): 'fear' after up-days.
    # The naive join (window from close(d-1)) contains that return, so it 'finds' the contrarian effect; the honest join does not.
    rng = np.random.default_rng(4)
    n, t0 = 1200, datetime(2018, 2, 1, tzinfo=timezone.utc)
    r = rng.normal(0, 0.03, n)
    closes = 100 * np.exp(np.cumsum(r))
    fng = [{"observed_at": (t0 + timedelta(days=i)).isoformat(), "value": {"value": 10 if r[i] > 0.02 else 90 if r[i] < -0.02 else 50}} for i in range(1, n)]
    px = [{"value": {"symbol": "BTC-USD", "t": (t0 + timedelta(days=i)).timestamp(), "close": float(c)}} for i, c in enumerate(closes)]
    stat, n_out, verdict, reason = run.harness_point_in_time(MemArchive({"crypto-fear-greed-history": fng, "daily-history-BTC-USD": px}))
    assert stat["naive"]["verdict"] == "supported" and stat["honest"]["verdict"] == "not_supported" and verdict == "supported"


# ------------------------------------------------------------- vs OM-16: overlay p on the reported excess basis --

def test_om16_overlay_sharpe_diff_p_uses_the_reported_basis(monkeypatch):
    rng = np.random.default_rng(5)
    bill = 0.004 + 0.003 * np.sin(np.arange(120) / 6)              # a moving bill: raw and excess Sharpes differ
    rets, bh = bill + rng.normal(0.002, 0.01, 120), rng.normal(0.006, 0.04, 120)
    calls = []

    def ov(archive, strategy, iv_scale=1.0):
        return {"strategy": strategy, "returns": rets, "benchmark": bh, "bill_returns": bill, "n_cycles": 120, "sharpe_basis": "x"}

    monkeypatch.setattr(run, "_overlay", ov)
    monkeypatch.setattr(run, "overlay_verdict", lambda rep, versus="benchmark": {})
    monkeypatch.setattr(run, "_sharpe_diff_p", lambda a, b: calls.append((a, b)) or 0.5)
    run._overlay_pair(None, "cash_secured_put")
    assert all(np.allclose(a, rets - bill) and np.allclose(b, bh - bill) for a, b in calls) and len(calls) == 2   # was raw rets, bh
    calls.clear(); run._overlay_pair(None, "short_straddle", versus="zero")
    assert all(np.allclose(a, rets) and np.allclose(b, bh - bill) for a, b in calls)                              # unfunded: strategy raw


# ------------------------------------------------------------------------ XA-6: T-176 at Deribit delivery prices --

def test_xa6_inverse_covered_call_settles_at_deribit_delivery_prices(monkeypatch):
    seen = {}
    monkeypatch.setattr(xa, "inverse_covered_call_btc", lambda *a, **k: seen.update(k) or {"verdict": "inconclusive", "reason": "stub", "n_cycles": 1})
    rows = [{"value": {"date": "2024-01-26", "delivery_price": 40000.0}}, {"value": {"date": "2024-02-23", "delivery_price": 51000.0}}]
    a = MemArchive({"daily-history-BTC-USD": _daily_rows("BTC-USD", 100 + np.arange(30.0)), "deribit-dvol-BTC-history": [], "fred-DTB3": [],
                    "deribit-delivery-prices-btc": rows})
    run.HARNESSES["btc_inverse_covered_call"](a)
    assert seen["delivery"] == {"2024-01-26": 40000.0, "2024-02-23": 51000.0}           # was: no delivery, Yahoo closes stood in
    assert set(a.loaded) == set(run.BUNDLES_NEEDED["btc_inverse_covered_call"]) and "deribit-delivery-prices-btc" in a.loaded


# ------------------------------------------------------------------------------ st OM-5: structure_* nulls --

def test_st_om5_structure_harnesses_record_their_registered_null():
    names = [h for h in run.HARNESSES if h.startswith("structure_")]
    assert len(names) == len(run.STRUCTURE_IDS) == 21
    for h in names:                                                # was 'n/a' for every one
        tid = run.STRUCTURE_THEORY[h]
        assert run._null_for(h) == f"{tid}: {THEORY[tid]['trial']['null']}; model-priced"


# ------------------------------------------------------------------- vs OM-6: T-03 three-valued signs_agree --

def _ms(errs, ns=None, cis=None, signs_agree=None):
    """multiscale_edge stub output: errs {h: mean error or None (unscored)}; significance from the CI."""
    ns = ns or {}; cis = cis or {}
    H = {h: {"n": ns.get(h, 400), "mean_error": e, "ci": list(cis.get(h, (e - 0.03, e + 0.03)))} for h, e in errs.items() if e is not None}
    sig = sum(1 for v in H.values() if v["ci"][0] > 0 or v["ci"][1] < 0)
    return {"horizons": H, "n_scales_significant": sig, "n_scales_total": len(H), "signs_agree": signs_agree}


@pytest.mark.parametrize("rep, expected", [
    # the markets.py checker's case: +0.02 at 1/3/7d, +0.12 (significant) at 30d, 90d unscored -> None. Was not_supported 'disagree'.
    (_ms({1: .02, 3: .02, 7: .02, 30: .12, 90: None}, signs_agree=None), "inconclusive"),
    (_ms({1: -.01, 3: .02, 7: .02, 30: .12, 90: .02}, signs_agree=False), "not_supported"),                      # adequate horizons disagree
    (_ms({1: .01, 3: .02, 7: .02, 30: .12, 90: -.01}, ns={90: 120}, signs_agree=False), "inconclusive"),         # only thin 90d disagrees
    (_ms({1: .01, 3: .02, 7: .02, 30: .12, 90: -.08}, ns={90: 120}, signs_agree=False), "not_supported"),        # intervals on opposite sides
    (_ms({1: .01, 3: .02, 7: .02, 30: .12, 90: .02}, signs_agree=True), "supported"),
    (_ms({1: .01, 3: .02, 7: .02, 30: .12, 90: .02}, ns={90: 260}, signs_agree=True), "inconclusive"),           # 90d below min_n 300
    (_ms({1: .01, 3: .02, 7: .02, 30: .02, 90: .02}, signs_agree=True), "not_supported"),                        # none significant, all adequate
    (_ms({1: .01, 3: .02, 7: .02, 30: .02, 90: .02}, ns={90: 260}, signs_agree=True), "inconclusive"),           # none significant yet, 90d thin
])
def test_om6_multiscale_edge_follows_the_three_valued_interface(pm, monkeypatch, rep, expected):
    seen = {}
    monkeypatch.setattr(run, "multiscale_edge", lambda p, m, horizons_days=None: seen.update(h=horizons_days) or rep)
    stat, n, verdict, reason = run.harness_multiscale_edge(pm)
    assert verdict == expected and seen["h"] == (1, 3, 7, 30, 90)
    assert n == min(rep["horizons"].get(h, {"n": 0})["n"] for h in (1, 3, 7, 30, 90))   # binding per-horizon n (was the largest)
