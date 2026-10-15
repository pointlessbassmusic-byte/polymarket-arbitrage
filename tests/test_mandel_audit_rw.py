"""Regression tests for the runner audit fixes (group rw: mandel/experiments/run.py). Synthetic data and in-memory archives only."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

import mandel.experiments.cross_asset as xa
import mandel.experiments.run as run
import mandel.experiments.underlying2 as u2
from mandel.archive import BundleEntry


# ----------------------------------------------------------------------------------------------- fixtures --

class FakeArchive:
    """Dict-backed stand-in for Archive: INDEX entries, files on disk (marker files under root) and rows. ``absent`` names are listed
    in the INDEX but have no file on this machine, like the off-git option chains on a fresh checkout."""

    def __init__(self, root: Path, bundles: dict, absent=()):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self._rows, self._entries, self.loaded = dict(bundles), {}, []
        for name in list(bundles) + list(absent):
            path = self.root / f"{name}.jsonl.gz"
            if name not in absent:
                path.write_bytes(b"")
            self._entries[name] = BundleEntry(name=name, kind="data", path=str(path), created_at="2099-01-01T00:00:00+00:00", rows=0, bytes=0, sha256="")

    def entries(self, kind=None, tag=None):
        return sorted(self._entries.values(), key=lambda e: e.name)

    def get(self, name):
        return self._entries[name]

    def _abs(self, rel):
        return Path(rel)

    def load(self, name):
        entry = self._entries[name]
        self.loaded.append(name)
        if not Path(entry.path).exists():
            raise FileNotFoundError(f"bundle {name} is not on this machine; rebuild with recipe: test")
        return iter(self._rows[name])


class TraceArchive:
    """Serves any bundle name with a short synthetic daily series and records every name loaded."""

    def __init__(self, n_days: int = 40):
        self.loaded = set(); self.n_days = n_days

    def entries(self, kind=None, tag=None):
        return []

    def get(self, name):
        return BundleEntry(name=name, kind="data", path=name, created_at="2099-01-01T00:00:00+00:00", rows=0, bytes=0, sha256="")

    def load(self, name):
        self.loaded.add(name)
        sym = name[len("daily-history-"):] if name.startswith("daily-history-") else name
        return iter(_daily_rows(sym, [100.0 + i for i in range(self.n_days)]))


T0 = datetime(2010, 12, 1, tzinfo=timezone.utc)


def _days(n, start=T0):
    return [(start + timedelta(days=i)) for i in range(n)]


def _daily_rows(sym, closes, start=T0):
    return [{"value": {"t": d.timestamp(), "close": float(c), "day": d.strftime("%Y-%m-%d"), "symbol": sym}} for d, c in zip(_days(len(closes), start), closes)]


def _h(n, skill):
    """One market_calibration horizon entry: scored when n >= 20, otherwise 'too few' as markets.market_calibration reports it."""
    return {"n": n, "brier": 0.25 * (1 - skill), "skill_vs_coin": skill} if n >= 20 else {"n": n, "note": "too few"}


@pytest.fixture
def pm_archive(tmp_path):
    return FakeArchive(tmp_path / "pm", {"polymarket-price-history-daily": [], "polymarket-closed-markets": []})


def _stub_calibration(monkeypatch, horizons: dict):
    monkeypatch.setattr(run, "market_calibration", lambda *a, **k: {"n_resolved_markets": 999, "horizons": dict(horizons)})


# ------------------------------------------------------------------- OM-1 (T-01, T-13, T-02): min_n per horizon --

def test_om1_market_calibration_binding_horizon_below_min_n_is_inconclusive(pm_archive, monkeypatch):
    # real-data shape: every skill > 0, 90d scored on 265 markets < min_n 300. Before: supported with n = max = 393.
    _stub_calibration(monkeypatch, {1: _h(393, .86), 3: _h(387, .85), 7: _h(373, .78), 30: _h(348, .72), 90: _h(265, .70)})
    stat, n, verdict, reason = run.harness_market_calibration(pm_archive)
    assert (verdict, n) == ("inconclusive", 265) and "90d n 265" in reason
    _stub_calibration(monkeypatch, {h: _h(400, .8) for h in (1, 3, 7, 30, 90)})
    assert run.harness_market_calibration(pm_archive)[1:3] == (400, "supported")


def test_om1_horizon_monotone_binding_horizon_below_min_n_is_inconclusive(pm_archive, monkeypatch):
    # strictly ordered skills but 90d n 265 < 300: was supported with n 265
    _stub_calibration(monkeypatch, {1: _h(393, .858), 3: _h(387, .855), 7: _h(373, .778), 30: _h(348, .719), 90: _h(265, .701)})
    stat, n, verdict, reason = run.harness_horizon_monotone(pm_archive)
    assert (verdict, n) == ("inconclusive", 265)
    _stub_calibration(monkeypatch, {1: _h(400, .858), 3: _h(400, .855), 7: _h(400, .778), 30: _h(400, .719), 90: _h(400, .701)})
    assert run.harness_horizon_monotone(pm_archive)[2] == "supported"


def _pm_markets(spec, p=0.05, close=datetime(2026, 1, 1, tzinfo=timezone.utc)):
    """spec: list of (market_id, event_id or None, outcome). Daily prices at p for the 10 days before close."""
    markets, prices = [], []
    for mid, eid, o in spec:
        m = {"id": mid, "umaResolutionStatus": "resolved", "outcomePrices": json.dumps([str(float(o)), str(float(1 - o))]),
             "outcomes": json.dumps(["Yes", "No"]), "closedTime": close.isoformat(), "question": mid}
        if eid is not None:
            m["events"] = [{"id": eid}]
        markets.append({"value": m})
        prices += [{"value": {"market_id": mid, "t": (close - timedelta(days=d)).timestamp(), "p": p}} for d in range(10, 0, -1)]
    return {"polymarket-closed-markets": markets, "polymarket-price-history-daily": prices}


def test_om1_longshot_below_min_n_cannot_support_but_can_falsify(tmp_path):
    # 284 cheap markets that all resolve NO: the bound is below zero, but 284 < min_n 300 -> inconclusive (was supported)
    a = FakeArchive(tmp_path / "a", _pm_markets([(f"m{i}", None, 0) for i in range(284)]))
    stat, n, verdict, reason = run.harness_longshot(a)
    assert (verdict, n) == ("inconclusive", 284) and stat["ci"][1] < 0
    # 284 markets with a positive mean error: the implemented criterion fails -> not_supported even below min_n
    b = FakeArchive(tmp_path / "b", _pm_markets([(f"m{i}", None, int(i < 40)) for i in range(284)]))
    assert run.harness_longshot(b)[2] == "not_supported"
    c = FakeArchive(tmp_path / "c", _pm_markets([(f"m{i}", None, 0) for i in range(300)]))
    assert run.harness_longshot(c)[2] == "supported"


# --------------------------------------------------------------------- OM-8 / OM-10 (T-01): every horizon --

def test_om8_market_calibration_unscored_horizon_is_inconclusive(pm_archive, monkeypatch):
    # 90d has 15 priced markets ('too few'); the others beat the coin. Was: supported 'at every horizon'.
    _stub_calibration(monkeypatch, {1: _h(400, .95), 3: _h(400, .95), 7: _h(400, .95), 30: _h(400, .95), 90: _h(15, 0)})
    stat, n, verdict, reason = run.harness_market_calibration(pm_archive)
    assert verdict == "inconclusive" and n == 15 and "90d unscored" in reason
    # a scored horizon with skill <= 0 falsifies 'every horizon' even when another horizon is unscored (rule 2 ordering)
    _stub_calibration(monkeypatch, {1: _h(400, .95), 3: _h(400, .95), 7: _h(400, -.1), 30: _h(400, .95), 90: _h(15, 0)})
    assert run.harness_market_calibration(pm_archive)[2] == "not_supported"


def test_om10_market_calibration_90d_at_19_markets_is_not_silently_dropped(pm_archive, monkeypatch):
    # verifier's stub: 90d n = 19 (no Brier); the other four horizons have min skill 0.72. Was: supported.
    _stub_calibration(monkeypatch, {1: _h(393, .86), 3: _h(387, .85), 7: _h(373, .78), 30: _h(348, .72), 90: _h(19, -.5)})
    stat, n, verdict, reason = run.harness_market_calibration(pm_archive)
    assert verdict == "inconclusive" and n == 19 and "90d" in reason


# ------------------------------------------------------------------------ OM-9 (T-13): strict chain --

def test_om9_horizon_monotone_is_strict_without_tolerance(pm_archive, monkeypatch):
    # 30d 0.700 < 90d 0.709 violates skill(30d) > skill(90d); the old 0.01 tolerance called it 'non-increasing'
    _stub_calibration(monkeypatch, {1: _h(400, .86), 3: _h(400, .85), 7: _h(400, .78), 30: _h(400, .700), 90: _h(400, .709)})
    stat, n, verdict, reason = run.harness_horizon_monotone(pm_archive)
    assert verdict == "not_supported" and not stat["monotone"] and "skill(30d) <= skill(90d)" in reason


def test_om9_horizon_monotone_needs_every_named_horizon_and_ignores_3d(pm_archive, monkeypatch):
    # 90d below 20 rows is unscored: was 'supported' on 1/3/7/30; now inconclusive
    _stub_calibration(monkeypatch, {1: _h(400, .86), 3: _h(400, .85), 7: _h(400, .78), 30: _h(400, .70), 90: _h(15, 0)})
    assert run.harness_horizon_monotone(pm_archive)[2] == "inconclusive"
    # 3d is not in the registered chain: 1d < 3d does not falsify 1d > 7d > 30d > 90d (the old adjacent check said not_supported)
    _stub_calibration(monkeypatch, {1: _h(400, .80), 3: _h(400, .85), 7: _h(400, .78), 30: _h(400, .70), 90: _h(400, .65)})
    stat, n, verdict, reason = run.harness_horizon_monotone(pm_archive)
    assert verdict == "supported" and stat["skills"]["3"] == .85


# ----------------------------------------------------------------------------- OM-14a (T-04): long side only --

def test_om14_bundle_arb_counts_only_long_bundles(tmp_path, monkeypatch):
    a = FakeArchive(tmp_path, {"polymarket-books-snapshot": [], "polymarket-books-2026-10-15": []})
    rep = {"markets_scanned": 250, "long_after_fees": 0, "short_after_fees": 5, "gross_long_candidates": 0, "median_round_trip_spread": .02,
           "examples_long": [], "examples_short": [{"market": "stale 1-share bid", "net_edge": .05}]}
    monkeypatch.setattr(run, "bundle_arb_scan", lambda rows: dict(rep))
    stat, n, verdict, reason = run.harness_bundle_arb(a)          # was supported: 5 short-side crosses per 250 markets in both snapshots
    assert verdict == "not_supported" and all(s["found"] == 0 and s["short_after_fees_reported_only"] == 5 for s in stat["snapshots"])
    monkeypatch.setattr(run, "bundle_arb_scan", lambda rows: {**rep, "long_after_fees": 3, "short_after_fees": 0})
    assert run.harness_bundle_arb(a)[2] == "supported"
    monkeypatch.setattr(run, "bundle_arb_scan", lambda rows: {**rep, "markets_scanned": 100, "long_after_fees": 3})
    assert run.harness_bundle_arb(a)[2] == "inconclusive"         # snapshots below the trial's min_n of 200 markets cannot confirm


# --------------------------------------------------------------------- OM-15 (T-02): event-clustered interval --

def test_om15_longshot_interval_resamples_events_not_markets(tmp_path):
    # 300 cheap markets in 20 events of 15. Event 0 resolves 6 YES together; the rest all NO. Mean error -0.03.
    spec = [(f"m{e}_{j}", f"ev{e}", int(e == 0 and j < 6)) for e in range(20) for j in range(15)]
    a = FakeArchive(tmp_path, _pm_markets(spec))
    stat, n, verdict, reason = run.harness_longshot(a)
    e = np.array([o - 0.05 for _, _, o in spec])
    iid_hi = np.quantile(np.random.default_rng(0).choice(e, size=(2000, e.size)).mean(axis=1), 0.975)
    assert iid_hi < 0                                              # the iid interval (old code) excludes zero -> was 'supported'
    assert verdict == "not_supported" and stat["ci"][1] >= 0 and stat["n_events"] == 20 and n == 300
    # with no event ids every market is its own cluster (falls back to the market id)
    assert run._event_keys([{"value": {"id": "x", "negRiskMarketID": "0xab"}}, {"value": {"id": "y"}}]) == {"x": "negrisk:0xab", "y": "market:y"}


# ------------------------------------------------------------- OM-1 (chains): listed is not on this machine --

def test_om1_chain_captures_listed_but_not_on_disk_are_missing_not_skipped(tmp_path):
    rows = [{"value": {"symbol": "SPX", "underlying": 5000.0}}]
    a = FakeArchive(tmp_path, {"options-chain-SPX-2026-10-15": [{"value": {}}], "options-surface-2026-10-15": rows, "options-surface-2026-10-14": rows,
                               "fred-DTB3": []}, absent=["options-chain-SPX-2026-10-14"])
    with pytest.raises(run.MissingData) as e:                        # was: 10-14 silently dropped, so 'day one' became 10-15
        run._chain_captures(a, "SPX")
    assert e.value.names == ["options-chain-SPX-2026-10-14"]
    assert run._missing_bundles(a, ["options-chain-SPX-*", "fred-DTB3"]) == []
    b = FakeArchive(tmp_path / "b", {"fred-DTB3": []}, absent=["options-chain-SPX-2026-10-14", "options-chain-SPX-2026-10-15"])
    assert run._bundles_matching(b, "options-chain-SPX-*") and run._missing_bundles(b, ["options-chain-SPX-*", "fred-DTB3"]) == ["options-chain-SPX-*"]
    stat, n, verdict, reason, no_data = run._execute("parity_v2", run.HARNESSES["parity_v2"], a, None)
    assert (verdict, n, no_data) == ("inconclusive", 0, True) and "options-chain-SPX-2026-10-14" in reason
    reg = {"theories": [{"id": "T-505", "status": "not_supported", "results": ["X-old"], "experiments": ["parity_v2"]}]}
    run._apply_result(reg, ["T-505"], "X-new", verdict, no_data)
    assert reg["theories"][0]["status"] == "not_supported" and reg["theories"][0]["results"] == ["X-old"]
    # a harness that itself reports nothing on this machine (n = 0) is also a no-data result
    _, _, v, _, nd = run._execute("x", lambda arc: ({}, 0, "inconclusive", "no SPX captures on this machine"), a, None)
    assert (v, nd) == ("inconclusive", True)


# ------------------------------------------------------------------------- OM-4 / OM-14b (T-07, T-06) --

def _long_series_archive(tmp_path, n_series=40, length=130):
    rows = [{"value": {"market_id": f"m{k}", "t": float(i), "p": 0.5}} for k in range(n_series) for i in range(length)]
    return FakeArchive(tmp_path, {"polymarket-price-history-daily": rows})


def test_om4_hurst_persistent_series_never_support_anti_persistence(tmp_path, monkeypatch):
    a = _long_series_archive(tmp_path)
    persistent = {"H": 0.69, "r2": 1, "n_scales": 8, "n": 130, "null_lo": 0.40, "null_hi": 0.60, "outside_null": True}
    monkeypatch.setattr(run, "hurst_with_interval", lambda x, n_null=200, seed=0: dict(persistent))
    stat, n, verdict, reason = run.harness_hurst(a)               # was supported: 40/40 'outside the null' (all above it)
    assert verdict == "not_supported" and stat["n_persistent_outside_null"] == 40 and stat["n_anti_persistent_outside_null"] == 0
    rows = iter([{"H": 0.38, "null_lo": 0.42, "null_hi": 0.58}] * 12 + [{"H": 0.47, "null_lo": 0.42, "null_hi": 0.58}] * 20 + [{"H": 0.55, "null_lo": 0.42, "null_hi": 0.58}] * 8)
    monkeypatch.setattr(run, "hurst_with_interval", lambda x, n_null=200, seed=0: {**next(rows), "r2": 1, "n_scales": 8, "n": 130, "outside_null": False})
    stat, n, verdict, reason = run.harness_hurst(a)               # 32/40 below 0.5 and 12/40 (30%) significantly anti-persistent
    assert verdict == "supported" and stat["share_H_below_half"] == 0.8 and stat["n_anti_persistent_outside_null"] == 12


def test_om4_hurst_below_min_n_series_cannot_support(tmp_path, monkeypatch):
    a = _long_series_archive(tmp_path, n_series=20)
    monkeypatch.setattr(run, "hurst_with_interval", lambda x, n_null=200, seed=0: {"H": 0.38, "null_lo": 0.42, "null_hi": 0.58, "outside_null": True})
    assert run.harness_hurst(a)[2] == "inconclusive"


def test_om14_shuffle_counts_follow_the_trials(tmp_path, monkeypatch):
    a = _long_series_archive(tmp_path)
    seen = {}

    class R:
        n, concavity, null_concavity_q95, exceeds_null = 130, 0.1, 0.05, True

    def mf(x, n_shuffles=999, **k):
        seen["n_shuffles"] = n_shuffles; return R()

    def hu(x, n_null=999, seed=0):
        seen["n_null"] = n_null; return {"H": 0.4, "null_lo": 0.42, "null_hi": 0.58, "outside_null": True}

    monkeypatch.setattr(run, "multifractal_test", mf); monkeypatch.setattr(run, "hurst_with_interval", hu)
    run.harness_multifractal(a); run.harness_hurst(a)
    assert seen == {"n_shuffles": 200, "n_null": 200}             # was 100 and 100; T-06 and T-07 specify 200


# ------------------------------------------------------------------------------------- OM-5 (T-36) --

def _pm_price_series_archive(tmp_path, n_series):
    rows = [{"value": {"market_id": f"m{k}", "t": float(i), "p": 0.5 + 0.001 * i}} for k in range(n_series) for i in range(61)]
    return FakeArchive(tmp_path, {"polymarket-price-history-daily": rows})


def test_om5_t36_is_scored_by_holdout_sharpe_of_the_is_best_rule(tmp_path, monkeypatch):
    a = _pm_price_series_archive(tmp_path, 120)
    rng = np.random.default_rng(0)
    R = rng.normal(0, 0.01, size=(400, 21))
    R[:200, 3] += 0.02                                             # in-sample winner: rule 3
    R[200:, 3] += 0.005                                            # ... still positive out of sample -> T-36 fails
    monkeypatch.setattr(run, "momentum_variants", lambda prices: (R, [f"r{j}" for j in range(21)]))
    stat, n, verdict, reason = run.harness_holdout_sharpe(a)
    assert stat["is_best_variant"] == "r3" and stat["holdout_sharpe"] > 0 and verdict == "not_supported" and n == 200
    R2 = R.copy(); R2[200:, 3] -= 0.02
    monkeypatch.setattr(run, "momentum_variants", lambda prices: (R2, [f"r{j}" for j in range(21)]))
    assert run.harness_holdout_sharpe(a)[2] == "supported"
    monkeypatch.setattr(run, "momentum_variants", lambda prices: (R2[125:275], [f"r{j}" for j in range(21)]))
    stat, n, verdict, reason = run.harness_holdout_sharpe(a)
    assert stat["holdout_sharpe"] <= 0 and (n, verdict) == (75, "inconclusive")     # 75 holdout periods < min_n 100
    reg = {"theories": [{"id": "T-10", "experiments": ["dsr_pbo_harness"]}, {"id": "T-36", "experiments": ["dsr_pbo_harness"]}]}
    by_h = run._scored_theories(reg)
    assert by_h["dsr_pbo_harness"] == ["T-10"] and by_h["holdout_sharpe"] == ["T-36"] and "holdout_sharpe" in run.HARNESSES


# ------------------------------------------------------------------------------- OM-6: superseded theories --

def test_om6_superseded_theory_is_not_rescored_by_its_successors_harness():
    reg = {"theories": [
        {"id": "T-192", "status": "not_supported", "experiments": ["opex_pinning"], "results": ["X-a"]},
        {"id": "T-502", "status": "not_supported", "experiments": ["opex_pinning"], "supersedes": "T-192", "results": ["X-a"]},
        {"id": "T-181", "status": "not_supported", "experiments": ["spx_box_lending"]},
        {"id": "T-505", "status": "not_supported", "experiments": ["parity_v2"], "supersedes": "T-181"}]}
    by_h = run._scored_theories(reg)
    assert by_h["opex_pinning"] == ["T-502"]                        # was ['T-192', 'T-502']: one harness overwrote both wordings
    assert by_h["spx_box_lending"] == ["T-181"]                     # its own harness still tests the old wording
    run._apply_result(reg, by_h["opex_pinning"], "X-b", "supported", False)
    t = {x["id"]: x for x in reg["theories"]}
    assert t["T-192"]["status"] == "not_supported" and t["T-192"]["results"] == ["X-a"] and t["T-502"]["status"] == "supported"


# ---------------------------------------------------------------------------------- OM-7: true inputs, errors --

def test_om7_error_never_overwrites_a_computed_verdict():
    reg = {"theories": [{"id": "T-266", "status": "supported", "results": ["X-1"]}, {"id": "T-999", "status": "untested"}]}
    stat, n, verdict, reason, no_data = run._execute("eth_btc_dvol_ratio", lambda a: (_ for _ in ()).throw(ValueError("boom")), None, None)
    assert (verdict, no_data) == ("error", False)
    run._apply_result(reg, ["T-266", "T-999"], "X-2", verdict, no_data)
    t = {x["id"]: x for x in reg["theories"]}
    assert t["T-266"]["status"] == "supported" and t["T-999"]["status"] == "inconclusive"   # was: supported -> inconclusive
    # an undeclared input absent on this machine surfaces as missing data, not as a status change
    _, _, v, _, nd = run._execute("x", lambda a: (_ for _ in ()).throw(FileNotFoundError("bundle cboe-OVX-history is not on this machine")), None, None)
    assert (v, nd) == ("inconclusive", True)


XA_STUBS = ["gap_test", "multi_asset_short_variance", "ratio_extremes", "ratio_mean_reversion_signal", "zscore_slope", "covered_call_vs_hold",
            "short_put_mean", "conditional_straddle", "protective_put_calmar", "inverse_covered_call_btc"]
U2_STUBS = ["tom_replication", "quarter_end_reversal", "santa_rally", "january_small_cap", "sell_in_may", "opex_week", "btc_monday", "gold_autumn",
            "golden_cross", "metals_tsmom", "crypto_weekly_tsmom", "btc_reversal", "gem", "sector_rotation", "svxy_regime", "low_vol_tilt", "santa_v2",
            "sell_in_may_v2", "btc_monday_v2", "gold_autumn_v2", "opex_week_v2", "tom_replication_v2", "low_vol_v2", "btc_reversal_v2",
            "sector_rotation_v2", "gem_v2", "golden_cross_v2", "crypto_weekly_v2", "metals_v2", "svxy_v2"]


def _stub(*a, **k):
    return {"verdict": "inconclusive", "reason": "stub", "n": 1}


def test_xa9_om7_declared_bundles_equal_the_bundles_each_harness_loads(monkeypatch):
    for name in XA_STUBS:
        monkeypatch.setattr(xa, name, _stub)
    for name in U2_STUBS:
        monkeypatch.setattr(u2, name, _stub)
    for name in list(run.XA_HARNESSES) + list(run.U2_HARNESSES) + ["trend_rules"]:
        arc = TraceArchive()
        try:
            run.HARNESSES[name](arc)
        except Exception:
            pass                                                   # trend_rules runs its real maths on 40 synthetic days
        assert arc.loaded == set(run.BUNDLES_NEEDED[name]), name   # was GLD/GVZ/DVOL-BTC/DTB3 for every XA harness
    assert run.BUNDLES_NEEDED["eth_btc_dvol_ratio"] == ["daily-history-ETH-USD", "daily-history-BTC-USD", "deribit-dvol-ETH-history", "deribit-dvol-BTC-history"]
    assert all(run._null_for(k) != "n/a" for k in run.XA_HARNESSES)


# ------------------------------------------------------------------------------------- OM-8b (T-58) --

def test_om8_trend_rules_denominator_stays_eight(tmp_path):
    syms = list(run.TREND_ASSETS)
    full = {f"daily-history-{s}": _daily_rows(s, 100 + np.arange(300.0)) for s in syms}
    assert run.BUNDLES_NEEDED["trend_rules"] == [f"daily-history-{s}" for s in syms]        # was SPY and BTC only
    a = FakeArchive(tmp_path / "a", {k: v for k, v in full.items() if "SLV" not in k and "TLT" not in k})
    with pytest.raises(run.MissingData) as e:                      # was: a majority over the 6 loaded assets
        run.harness_trend_rules(a)
    assert e.value.names == ["daily-history-SLV", "daily-history-TLT"]
    b = FakeArchive(tmp_path / "b", {k: v for k, v in full.items() if "IWM" not in k}, absent=["daily-history-IWM"])
    assert run._execute("trend_rules", run.harness_trend_rules, b, None)[2:] == ("inconclusive", "missing data: not on this machine: daily-history-IWM", True)


# ------------------------------------------------------------------------------------- OM-11 (T-19) --

def test_om11_point_in_time_needs_a_verdict_change(tmp_path, monkeypatch):
    a = FakeArchive(tmp_path, {"crypto-fear-greed-history": [], "daily-history-BTC-USD": []})

    def fg(d_naive, d_honest, v_naive="not_supported", v_honest="not_supported"):
        return lambda fng, px, lag_days=1, n_boot=500: {"verdict": v_naive if lag_days == 0 else v_honest, "d_fear": d_naive if lag_days == 0 else d_honest, "n": 900}

    monkeypatch.setattr(run, "fear_greed_forward_returns", fg(+0.0001, -0.0001))
    stat, n, verdict, reason = run.harness_point_in_time(a)        # was supported on the sign flip alone
    assert verdict == "not_supported" and stat["d_fear_sign_flip_reported_only"]
    monkeypatch.setattr(run, "fear_greed_forward_returns", fg(float("nan"), 0.0003))
    stat, n, verdict, reason = run.harness_point_in_time(a)        # was supported: sign(nan) != sign(x)
    assert verdict == "not_supported" and not stat["d_fear_sign_flip_reported_only"]
    monkeypatch.setattr(run, "fear_greed_forward_returns", fg(0.0003, 0.0001, "supported", "not_supported"))
    assert run.harness_point_in_time(a)[2] == "supported"


# ------------------------------------------------------------------------------------- OM-12: U2 n --

def test_om12_u2_harnesses_report_the_observations_they_rest_on(tmp_path, monkeypatch):
    syms = ["QQQ", "IWM", "TLT", "GLD", "GC=F", "USMV", "SPY", "SPLV", "SPHB"]
    bundles = {run._dh(s)[0]: _daily_rows(s, 100 + np.arange(400.0)) for s in syms}
    bundles.update({run._dh(s)[0]: _daily_rows(s, 100 + np.arange(2000.0)) for s in ("BTC-USD", "ETH-USD")})   # 2010-12 .. 2016-05
    a = FakeArchive(tmp_path, bundles)
    for name in ["tom_replication", "btc_monday", "gold_autumn", "golden_cross", "low_vol_tilt", "gold_autumn_v2", "tom_replication_v2", "golden_cross_v2"]:
        monkeypatch.setattr(u2, name, lambda *x, **k: {"verdict": "not_supported", "reason": "stub"})
    days = [d.strftime("%Y-%m-%d") for d in _days(400)]
    crypto_days = [d.strftime("%Y-%m-%d") for d in _days(2000)]
    expect = {"tom_replication": 399, "tom_replication_v2": 399, "btc_monday": 1999, "gold_autumn": 399, "low_vol_tilt": 399,
              "golden_cross_crypto": 1999 - 300, "gold_autumn_v2": sum(d >= "2010-12-31" for d in days) - 1,
              "golden_cross_v2": sum(1 for i, d in enumerate(crypto_days[1:]) if i >= 300 and d >= "2015-04-01")}
    for h, n_expected in expect.items():
        assert run.HARNESSES[h](a)[1] == n_expected, h               # all eight were recorded with n = 0
    assert expect["gold_autumn_v2"] == 369 and 0 < expect["golden_cross_v2"] < 1999 - 300
    monkeypatch.setattr(u2, "btc_monday", lambda *x, **k: {"verdict": "not_supported", "reason": "stub", "n": 7, "n_days": 99})
    assert run.HARNESSES["btc_monday"](a)[1] == 7                    # a function's own n is read first


# ------------------------------------------------------------------------------------- OM-13 (T-448, T-435) --

def test_om13_excess_index_subtracts_the_prior_day_bill():
    days = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"]
    e_days, e = run._excess_index((days, np.array([100.0, 101.0, 101.0, 101.0])), (["2020-01-01", "2020-01-03"], [2.52, 5.04]))
    r = e[1:] / e[:-1] - 1
    # day 2 uses the 01-01 print (1 bp/day); day 3 still the 01-01 print (prior day 01-02); day 4 the 01-03 print (2 bp/day)
    assert e_days == days and np.allclose(r, [0.01 - 0.0001, 0.0 - 0.0001, 0.0 - 0.0002])
    late_d, late = run._excess_index((days, np.array([1.0, 1.0, 1.0, 1.0])), (["2020-01-02"], [2.52]))
    assert late_d == days[1:]                                       # no bill print yet on 01-01: that day is dropped


def test_om13_low_vol_and_svxy_wrappers_use_excess_returns(tmp_path, monkeypatch):
    flat = 100 * np.ones(30)
    a = FakeArchive(tmp_path, {"daily-history-USMV": _daily_rows("USMV", flat), "daily-history-SPY": _daily_rows("SPY", flat),
                               "daily-history-SVXY": _daily_rows("SVXY", flat), "fred-DTB3": _daily_rows("DTB3", 2.52 * np.ones(30)),
                               "cboe-VIX-history": _daily_rows("VIX", 15 * np.ones(30)), "cboe-VIX3M-history": _daily_rows("VIX3M", 17 * np.ones(30))})
    seen = {}

    def lv(usmv, spy):
        seen["lv"] = (usmv, spy); return {"verdict": "not_supported", "reason": "stub", "n_days": 29}

    def sv(svxy, vix, vix3m):
        seen["sv"] = svxy; return {"verdict": "not_supported", "reason": "stub", "n_test_days": 29}

    monkeypatch.setattr(u2, "low_vol_v2", lv); monkeypatch.setattr(u2, "svxy_v2", sv)
    run.HARNESSES["low_vol_v2"](a); run.HARNESSES["svxy_v2"](a)
    for _, c in (seen["lv"][0], seen["lv"][1], seen["sv"]):         # flat prices: every excess return is -rf = -1 bp/day (was 0)
        assert np.allclose(c[1:] / c[:-1] - 1, -0.0001)
    # if underlying2 takes the bill series itself, raw prices and the bills are passed instead (never subtracted twice)
    monkeypatch.setattr(u2, "low_vol_v2", lambda usmv, spy, bill_days=None, bill_vals=None: seen.update(raw=(usmv, bill_vals)) or {"verdict": "x", "reason": "y"})
    run.HARNESSES["low_vol_v2"](a)
    assert np.allclose(seen["raw"][0][1], flat) and seen["raw"][1][0] == 2.52
