"""
Experiment runner: load archived data, run harnesses, record results, update the theory registry.
=================================================================================================

``run_all`` is deterministic given the bundles; every result goes to ``state/experiments.jsonl``
and the ledger. Theories mapped to a harness move from ``untested`` to the harness verdict with a
pointer to the result id. Nothing is deleted when a theory is not supported: it is marked and
stays in the registry.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from mandel._io import atomic_write_text
from mandel.archive import Archive
from mandel.experiments import ExperimentLog
from mandel.experiments.markets import bundle_arb_scan, market_calibration, multiscale_edge, price_at_horizons, resolved_outcomes
from mandel.experiments.markov import markov_vs_persistence
from mandel.experiments.msm import msm_vs_rolling
from mandel.experiments.overfit import overfit_report
from mandel.experiments.scaling import hurst_with_interval, multifractal_test
from mandel.experiments.social import attention_vs_abs_return, fear_greed_forward_returns
from mandel.experiments.volatility import implied_move_vs_realised, overlay_backtest, overlay_verdict, price_closes, skew_tail, term_structure_reversion, variance_risk_premium
from mandel.experiments.underlying import ratio_reversion, trend_rules_multi, turn_of_month, weekday_effect, weekend_effect
from mandel.forecasts import ForecastBook
from mandel.ledger import Ledger
from mandel.paths import MANDEL_ROOT

REGISTRY = MANDEL_ROOT / "theories" / "registry.json"


def _series_by_market(price_rows) -> dict[str, np.ndarray]:
    by = {}
    for r in price_rows:
        v = r["value"]
        by.setdefault(v["market_id"], []).append((float(v["t"]), float(v["p"])))
    return {k: np.array([p for _, p in sorted(v)]) for k, v in by.items()}


def harness_market_calibration(archive: Archive) -> tuple[dict, int, str, str]:
    rep = market_calibration(archive.load("polymarket-price-history-daily"), archive.load("polymarket-closed-markets"))
    h = rep["horizons"]
    usable = {k: v for k, v in h.items() if "brier" in v}
    if not usable:
        return rep, 0, "inconclusive", "no horizon had 20+ priced resolved markets"
    worst_skill = min(v["skill_vs_coin"] for v in usable.values())
    n = max(v["n"] for v in usable.values())
    verdict = "supported" if worst_skill > 0 else "not_supported"
    reason = f"market price beats the coin at every horizon (min skill {worst_skill:.2f})" if verdict == "supported" else \
             f"market price fails to beat the coin at some horizon (min skill {worst_skill:.2f})"
    return rep, n, verdict, reason


def harness_multiscale_edge(archive: Archive) -> tuple[dict, int, str, str]:
    rep = multiscale_edge(archive.load("polymarket-price-history-daily"), archive.load("polymarket-closed-markets"))
    n = max((v["n"] for v in rep["horizons"].values()), default=0)
    if rep["n_scales_total"] < 3:
        return rep, n, "inconclusive", "fewer than three horizons had 30+ markets"
    if rep["n_scales_significant"] == 0:
        return rep, n, "not_supported", "no horizon shows a mean error whose interval excludes zero: no structural market bias to be consistent about"
    verdict = "supported" if rep["signs_agree"] else "not_supported"
    return rep, n, verdict, (f"{rep['n_scales_significant']}/{rep['n_scales_total']} horizons significant and signs agree" if rep["signs_agree"]
                              else "significant horizons disagree in sign")


def harness_bundle_arb(archive: Archive) -> tuple[dict, int, str, str]:
    rep = bundle_arb_scan(archive.load("polymarket-books-snapshot"))
    n = rep["markets_scanned"]
    if n < 50:
        return rep, n, "inconclusive", "fewer than 50 markets with both books"
    found = rep["long_after_fees"] + rep["short_after_fees"]
    verdict = "supported" if found > 0 else "not_supported"
    return rep, n, verdict, f"{found} after-fee bundle mispricings in {n} markets (one snapshot)"


def harness_multifractal(archive: Archive, max_markets: int = 40) -> tuple[dict, int, str, str]:
    series = _series_by_market(archive.load("polymarket-price-history-daily"))
    long_enough = [(k, s) for k, s in series.items() if s.size >= 120]
    long_enough.sort(key=lambda kv: -kv[1].size)
    results = []
    for k, s in long_enough[:max_markets]:
        r = multifractal_test(np.log(np.clip(s, 0.01, 0.99) / (1 - np.clip(s, 0.01, 0.99))), n_shuffles=100)
        results.append({"market": k, "n": r.n, "concavity": r.concavity, "null_q95": r.null_concavity_q95, "exceeds": r.exceeds_null})
    n = len(results)
    if n < 10:
        return {"per_market": results}, n, "inconclusive", "fewer than 10 series of 120+ daily points"
    frac = sum(1 for r in results if r["exceeds"]) / n
    verdict = "supported" if frac > 0.25 else "not_supported"
    return {"fraction_exceeding_null": frac, "n_series": n, "per_market": results[:40]}, n, verdict, \
        f"{frac:.0%} of {n} daily logit-price series show concavity beyond the shuffled null (threshold 25%; chance ~5%)"


def harness_hurst(archive: Archive, max_markets: int = 40) -> tuple[dict, int, str, str]:
    series = _series_by_market(archive.load("polymarket-price-history-daily"))
    long_enough = sorted([(k, s) for k, s in series.items() if s.size >= 120], key=lambda kv: -kv[1].size)[:max_markets]
    rows = []
    for k, s in long_enough:
        x = np.log(np.clip(s, 0.01, 0.99) / (1 - np.clip(s, 0.01, 0.99)))
        h = hurst_with_interval(x, n_null=100)
        h["market"] = k
        rows.append(h)
    n = len(rows)
    if n < 10:
        return {"per_market": rows}, n, "inconclusive", "fewer than 10 long series"
    Hs = np.array([r["H"] for r in rows if np.isfinite(r["H"])])
    outside = sum(1 for r in rows if r["outside_null"])
    verdict = "supported" if outside / n > 0.25 else "not_supported"
    return {"median_H": float(np.median(Hs)), "n_series": n, "fraction_outside_null": outside / n, "per_market": rows}, n, verdict, \
        f"median H {np.median(Hs):.2f}; {outside}/{n} series outside their shuffle null (threshold 25%)"


def harness_markov(archive: Archive, max_markets: int = 60) -> tuple[dict, int, str, str]:
    series = _series_by_market(archive.load("polymarket-price-history-daily"))
    long_enough = sorted([(k, s) for k, s in series.items() if s.size >= 100], key=lambda kv: -kv[1].size)[:max_markets]
    gains = []
    for k, s in long_enough:
        r = markov_vs_persistence(s)
        if r.get("n_test", 0) >= 20:
            gains.append(r["improvement_bits"])
    n = len(gains)
    if n < 10:
        return {"gains": gains}, n, "inconclusive", "fewer than 10 usable series"
    g = np.array(gains)
    verdict = "supported" if g.mean() > 0 and np.quantile(g, 0.25) > 0 else "not_supported"
    return {"mean_gain_bits": float(g.mean()), "q25": float(np.quantile(g, 0.25)), "q75": float(np.quantile(g, 0.75)), "n_series": n}, n, verdict, \
        f"first-order price-bucket Markov vs base rate: mean {g.mean():+.4f} bits/step over {n} series"


def harness_msm(archive: Archive, max_markets: int = 12) -> tuple[dict, int, str, str]:
    series = _series_by_market(archive.load("polymarket-price-history-daily"))
    long_enough = sorted([(k, s) for k, s in series.items() if s.size >= 200], key=lambda kv: -kv[1].size)[:max_markets]
    rows = []
    for k, s in long_enough:
        x = np.log(np.clip(s, 0.01, 0.99) / (1 - np.clip(s, 0.01, 0.99)))
        r = msm_vs_rolling(np.diff(x), k=3)
        if r.get("n_test", 0) >= 40:
            rows.append({"market": k, "n_test": r["n_test"], "gain": r["gain_nats_per_obs"], "fit": r["fit"]})
    n = len(rows)
    if n < 5:
        return {"per_market": rows}, n, "inconclusive", "fewer than 5 series of 200+ points"
    g = np.array([r["gain"] for r in rows])
    verdict = "supported" if np.median(g) > 0 else "not_supported"
    return {"median_gain_nats": float(np.median(g)), "n_series": n, "per_market": rows}, n, verdict, \
        f"MSM(k=3) vs 20-day rolling variance, out of sample: median gain {np.median(g):+.3f} nats/obs over {n} series"


def harness_overfit(archive: Archive, max_markets: int = 150) -> tuple[dict, int, str, str]:
    series = _series_by_market(archive.load("polymarket-price-history-daily"))
    prices = [s for _, s in sorted(series.items(), key=lambda kv: -kv[1].size)[:max_markets] if s.size >= 60]
    if len(prices) < 20:
        return {}, len(prices), "inconclusive", "fewer than 20 series"
    rep = overfit_report(prices)
    n = rep["n_periods"]
    # The theory: a declared search of simple rules produces an in-sample winner that does not survive deflation
    verdict = "supported" if rep["dsr_best"] < 0.95 and rep["pbo"] > 0.5 else "not_supported"
    return rep, n, verdict, f"best of {rep['n_variants']} momentum rules: Sharpe {rep['best_sharpe']:.3f}, DSR {rep['dsr_best']:.2f}, PBO {rep['pbo']:.2f}"


def harness_controls(archive: Archive, ledger: Ledger, n_markets: int = 200) -> tuple[dict, int, str, str]:
    """Write coin, oracle and market-price forecasts for resolved markets into the real forecast book and
    check the scoring path end to end: coin ~0.25 Brier, oracle 0, market below coin."""
    outcomes = resolved_outcomes(archive.load("polymarket-closed-markets"))
    byh = price_at_horizons(archive.load("polymarket-price-history-daily"), outcomes, horizons_days=(1,))
    rows = byh.get(1, [])[:n_markets]
    if len(rows) < 30:
        return {}, len(rows), "inconclusive", "fewer than 30 priced resolved markets"
    fb = ForecastBook(ledger=ledger)
    existing = {fc.question_id for fc in fb.forecasts}
    written = 0
    for p, o, mid in rows:
        qid = f"pm:{mid}"
        if qid in existing or qid in fb.resolutions:
            continue
        q = outcomes[mid]["question"][:120]
        fb.record("market:polymarket", qid, q, p, horizon="1d-before-close")
        fb.record("control:coin", qid, q, 0.5)
        fb.record("control:oracle", qid, q, float(o))
        fb.resolve(qid, o, note="Polymarket UMA resolution")
        written += 1
    board = {s.source: s.as_dict() for s in fb.scoreboard()}
    coin = board.get("control:coin", {}).get("brier"); oracle = board.get("control:oracle", {}).get("brier"); mkt = board.get("market:polymarket", {}).get("brier")
    ok = coin is not None and abs(coin - 0.25) < 1e-9 and oracle == 0.0 and mkt is not None and mkt < coin
    return {"written": written, "scoreboard": board}, len(rows), "supported" if ok else "not_supported", \
        f"coin {coin}, oracle {oracle}, market {mkt}: scoring path {'intact' if ok else 'BROKEN'}"


def harness_longshot(archive: Archive, horizon: int = 7, hi_p: float = 0.10, n_boot: int = 2000, seed: int = 0) -> tuple[dict, int, str, str]:
    """T-02: in the under-0.10 bucket at the 7d horizon, mean(outcome - price) < 0 (classic longshot bias:
    cheap YES over-priced). Bootstrap 95% interval; the upper bound must be below zero."""
    outcomes = resolved_outcomes(archive.load("polymarket-closed-markets"))
    rows = price_at_horizons(archive.load("polymarket-price-history-daily"), outcomes, horizons_days=(horizon,))[horizon]
    sel = np.array([o - p for p, o, _ in rows if p < hi_p])
    if sel.size < 100:
        return {"n": int(sel.size)}, int(sel.size), "inconclusive", f"only {sel.size} observations under {hi_p}"
    rng = np.random.default_rng(seed)
    boots = rng.choice(sel, size=(n_boot, sel.size), replace=True).mean(axis=1)
    lo, hi = (float(x) for x in np.quantile(boots, [0.025, 0.975]))
    stat = {"n": int(sel.size), "horizon_days": horizon, "bucket_hi": hi_p, "mean_error": float(sel.mean()), "ci": [lo, hi],
            "yes_events": int(sum(1 for p, o, _ in rows if p < hi_p and o == 1)), "mean_price": float(np.mean([p for p, o, _ in rows if p < hi_p]))}
    verdict = "supported" if hi < 0 else "not_supported"
    return stat, int(sel.size), verdict, f"<{hi_p} bucket at {horizon}d: mean(outcome-price) {sel.mean():+.4f}, 95% [{lo:+.4f}, {hi:+.4f}], {stat['yes_events']} YES events of {sel.size}"


def harness_horizon_monotone(archive: Archive, horizons=(1, 3, 7, 30, 90)) -> tuple[dict, int, str, str]:
    """T-13: Brier skill vs coin is non-increasing as the horizon lengthens (the market learns as time passes).
    Each adjacent pair must satisfy skill(shorter) >= skill(longer) - 0.01 (a 1-point tolerance for noise)."""
    rep = market_calibration(archive.load("polymarket-price-history-daily"), archive.load("polymarket-closed-markets"), horizons_days=horizons)
    skills = {h: rep["horizons"][h]["skill_vs_coin"] for h in horizons if h in rep["horizons"] and rep["horizons"][h].get("n", 0) >= 30}
    hs = sorted(skills)
    n = min((rep["horizons"][h]["n"] for h in hs), default=0)
    if len(hs) < 3:
        return {"skills": skills}, n, "inconclusive", "fewer than 3 horizons with 30+ observations"
    ok = all(skills[hs[i]] >= skills[hs[i + 1]] - 0.01 for i in range(len(hs) - 1))
    return {"skills": {str(h): skills[h] for h in hs}, "monotone": ok}, n, "supported" if ok else "not_supported", \
        "skill by horizon " + ", ".join(f"{h}d {skills[h]:.3f}" for h in hs) + (" (non-increasing)" if ok else " (not monotone)")


def harness_point_in_time(archive: Archive) -> tuple[dict, int, str, str]:
    """T-19: does honouring available_at change a verdict? Runs the Fear & Greed harness with the naive join
    (lag 0) and the honest one (lag 1) and compares verdicts and the sign of the fear-side effect."""
    fng = list(archive.load("crypto-fear-greed-history")); px = list(archive.load("daily-history-BTC-USD"))
    naive = fear_greed_forward_returns(fng, px, lag_days=0, n_boot=500)
    honest = fear_greed_forward_returns(fng, px, lag_days=1, n_boot=500)
    changed = naive["verdict"] != honest["verdict"] or (np.sign(naive.get("d_fear", 0)) != np.sign(honest.get("d_fear", 0)))
    stat = {"naive": {k: naive.get(k) for k in ("verdict", "d_fear", "d_greed", "p_fear", "p_greed")},
            "honest": {k: honest.get(k) for k in ("verdict", "d_fear", "d_greed", "p_fear", "p_greed")}, "changed": bool(changed)}
    return stat, int(honest.get("n", 0)), "supported" if changed else "not_supported", \
        f"naive {naive['verdict']} (d_fear {naive.get('d_fear', float('nan')):+.4f}) vs point-in-time {honest['verdict']} (d_fear {honest.get('d_fear', float('nan')):+.4f}): {'verdict or sign changed' if changed else 'no change on this harness'}"


def _vrp(archive: Archive, index_bundle: str, price_bundle: str, symbol: str, window: int, ppy: int) -> tuple[dict, int, str, str]:
    rep = variance_risk_premium(archive.load(index_bundle), archive.load(price_bundle), window=window, symbol=symbol, periods_per_year=ppy)
    return rep, rep["n"], rep["verdict"], rep["reason"]


def harness_vrp_spx(archive: Archive):
    """T-48: VIX^2 exceeds the realised variance of SPY over the next 21 trading days (model-free VRP)."""
    return _vrp(archive, "cboe-VIX-history", "daily-history-SPY", "SPY", 21, 252)


def harness_vrp_btc(archive: Archive):
    """T-49: DVOL^2 exceeds realised BTC variance over the next 30 calendar days (Deribit DVOL is a 30-day index)."""
    return _vrp(archive, "deribit-dvol-BTC-history", "daily-history-BTC-USD", "BTC-USD", 30, 365)


def harness_vrp_gold(archive: Archive):
    """T-50: GVZ^2 exceeds realised GLD variance over the next 21 days."""
    return _vrp(archive, "cboe-GVZ-history", "daily-history-GLD", "GLD", 21, 252)


def harness_vrp_nasdaq(archive: Archive):
    """T-51: VXN^2 exceeds realised QQQ variance over the next 21 days."""
    return _vrp(archive, "cboe-VXN-history", "daily-history-QQQ", "QQQ", 21, 252)


def harness_vrp_oil(archive: Archive):
    """T-63: OVX^2 exceeds realised USO variance over the next 21 days."""
    return _vrp(archive, "cboe-OVX-history", "daily-history-USO", "USO", 21, 252)


def harness_vrp_bonds(archive: Archive):
    """T-64: VXTLT^2 exceeds realised TLT variance over the next 21 days."""
    return _vrp(archive, "cboe-VXTLT-history", "daily-history-TLT", "TLT", 21, 252)


def harness_vrp_russell(archive: Archive):
    """T-65: RVX^2 exceeds realised IWM variance over the next 21 days."""
    return _vrp(archive, "cboe-RVX-history", "daily-history-IWM", "IWM", 21, 252)


def harness_vrp_eth(archive: Archive):
    """T-67: DVOL(ETH)^2 exceeds realised ETH variance over the next 30 days."""
    return _vrp(archive, "deribit-dvol-ETH-history", "daily-history-ETH-USD", "ETH-USD", 30, 365)


def harness_implied_move(archive: Archive):
    """T-66: the ATM straddle's implied move at ~30 DTE exceeds the realised move to expiry (from the daily surface capture)."""
    syms = ["SPY", "QQQ", "IWM", "TLT", "GLD", "SLV", "USO", "IBIT"]
    px = {s: price_closes(archive.load(f"daily-history-{s}"), s) for s in syms if _bundles_matching(archive, f"daily-history-{s}")}
    rep = implied_move_vs_realised(_load_many(archive, "options-surface-*"), px)
    return rep, rep["n_resolved_captures"], rep["verdict"], rep["reason"]


def harness_skew_tail(archive: Archive):
    rep = skew_tail(archive.load("cboe-SKEW-history"), archive.load("daily-history-SPY"), symbol="SPY")
    return rep, rep["n"], rep["verdict"], rep["reason"]


def harness_term_structure(archive: Archive):
    rep = term_structure_reversion(archive.load("cboe-VIX-history"), archive.load("cboe-VIX3M-history"))
    return rep, rep["n"], rep["verdict"], rep["reason"]


def _sharpe_diff_p(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, block_len: int = 6, seed: int = 0) -> float:
    """One-sided p for H0: Sharpe(a) <= Sharpe(b), circular block bootstrap of paired cycles (percentile)."""
    rng = np.random.default_rng(seed); n = len(a)
    def sr(x): return x.mean() / x.std(ddof=1) if x.std(ddof=1) > 0 else 0.0
    obs = sr(a) - sr(b); null = np.empty(n_boot)
    nb = int(np.ceil(n / block_len))
    for i in range(n_boot):
        idx = (rng.integers(0, n, nb)[:, None] + np.arange(block_len)[None, :]).ravel()[:n] % n
        null[i] = sr(a[idx]) - sr(b[idx]) - obs
    return float((np.sum(null >= obs) + 1) / (n_boot + 1))


# Measured 2026-10-14 against the live SPY chain at 30 DTE: VIX 15.27 vs SPY ATM IV 12.3 (ratio 0.81); a flat VIX
# overstated the 30-delta call premium by 79%, the ATM call by 23%, the ATM put by 17%, the 30-delta put by 8%.
# Until the daily chain capture gives a history of that ratio, model-priced overlays cannot be verdicts.
IV_SCALE_TODAY = 0.81
MODEL_NOTE = "MODEL-PRICED, not a verdict: flat-VIX pricing overstated today's 30-delta call by 79% and ATM by ~20%"


def _overlay(archive: Archive, strategy: str, iv_scale: float = 1.0):
    return overlay_backtest(archive.load("daily-history-SPY"), archive.load("cboe-VIX-history"), archive.load("fred-DTB3"), strategy, symbol="SPY", iv_scale=iv_scale)


def _overlay_pair(archive: Archive, strategy: str, versus: str = "benchmark"):
    """Runs the overlay at VIX and at today's measured ATM/VIX ratio; returns both and a sensitivity reading."""
    a = _overlay(archive, strategy, 1.0); b = _overlay(archive, strategy, IV_SCALE_TODAY)
    va = overlay_verdict(a, versus=versus); vb = overlay_verdict(b, versus=versus)
    va["p_value_sharpe_diff"] = _sharpe_diff_p(a["returns"], a["benchmark"]); vb["p_value_sharpe_diff"] = _sharpe_diff_p(b["returns"], b["benchmark"])
    return {"at_vix": va, "at_iv_scale_0.81": vb, "model_priced": True, "note": MODEL_NOTE}, a, b


def harness_covered_call(archive: Archive):
    """T-54 (model-priced): monthly 30-delta covered calls on SPY vs buy-and-hold. Reported as inconclusive by design."""
    stat, a, b = _overlay_pair(archive, "covered_call")
    return stat, a["n_cycles"], "inconclusive", (f"{MODEL_NOTE}. At VIX: Sharpe {a['sharpe']:.2f} vs B&H {a['benchmark_sharpe']:.2f}, CAGR {a['cagr']*100:.1f}% vs {a['benchmark_cagr']*100:.1f}%; "
                                                   f"at IV x0.81: Sharpe {b['sharpe']:.2f}, CAGR {b['cagr']*100:.1f}%, MDD {b['max_drawdown']*100:.0f}% vs {b['benchmark_max_drawdown']*100:.0f}% ({a['n_cycles']} cycles)")


def harness_csp(archive: Archive):
    """T-55 (model-priced): monthly ATM cash-secured puts on SPY vs buy-and-hold. Inconclusive by design."""
    stat, a, b = _overlay_pair(archive, "cash_secured_put")
    return stat, a["n_cycles"], "inconclusive", (f"{MODEL_NOTE}. At VIX: Sharpe {a['sharpe']:.2f} vs B&H {a['benchmark_sharpe']:.2f}, CAGR {a['cagr']*100:.1f}% vs {a['benchmark_cagr']*100:.1f}%; "
                                                   f"at IV x0.81: Sharpe {b['sharpe']:.2f}, CAGR {b['cagr']*100:.1f}%, MDD {b['max_drawdown']*100:.0f}% vs {b['benchmark_max_drawdown']*100:.0f}%")


def harness_collar(archive: Archive):
    """T-56 (model-priced): monthly 30-delta collar on SPY. Inconclusive by design."""
    stat, a, b = _overlay_pair(archive, "collar")
    return stat, a["n_cycles"], "inconclusive", (f"{MODEL_NOTE}. At VIX: MDD {a['max_drawdown']*100:.0f}% vs {a['benchmark_max_drawdown']*100:.0f}%, Sharpe {a['sharpe']:.2f} vs {a['benchmark_sharpe']:.2f}; "
                                                   f"at IV x0.81: MDD {b['max_drawdown']*100:.0f}%, Sharpe {b['sharpe']:.2f}, CAGR {b['cagr']*100:.1f}% vs {b['benchmark_cagr']*100:.1f}%")


def harness_short_straddle(archive: Archive):
    """T-57 (model-priced): selling the monthly ATM SPY straddle priced at VIX. Inconclusive by design; the sensitivity to the IV scale is the finding."""
    stat, a, b = _overlay_pair(archive, "short_straddle", versus="zero")
    pa = stat["at_vix"].get("p_value_mean_excess", 1.0); pb = stat["at_iv_scale_0.81"].get("p_value_mean_excess", 1.0)
    return stat, a["n_cycles"], "inconclusive", (f"{MODEL_NOTE}. At VIX: mean {a['mean_cycle_return']*100:+.2f}%/month (p={pa:.4f}); "
                                                   f"at IV x0.81: mean {b['mean_cycle_return']*100:+.2f}%/month (p={pb:.4f}), Sharpe {b['sharpe']:.2f}, MDD {b['max_drawdown']*100:.0f}%")


TREND_RULES = [("ma", 50), ("ma", 100), ("ma", 200), ("tsmom", 63), ("tsmom", 126), ("tsmom", 252)]
TREND_ASSETS = {"SPY": 252, "QQQ": 252, "GLD": 252, "SLV": 252, "TLT": 252, "IWM": 252, "BTC-USD": 365, "ETH-USD": 365}


def _closes(archive: Archive, sym: str):
    from mandel.experiments.underlying import _series
    return _series(archive.load(f"daily-history-{sym}"), sym)


def harness_trend_rules(archive: Archive):
    """T-58: a declared grid of six long/flat trend rules beats buy-and-hold on a majority of eight assets after deflation."""
    series = {}
    for sym in TREND_ASSETS:
        try:
            _, c = _closes(archive, sym); series[sym] = c
        except Exception:
            continue
    rep = trend_rules_multi(series, TREND_RULES, cost_bps=5.0, ppy=TREND_ASSETS)
    n = min(o["n_periods"] for o in rep["per_asset"].values()) if rep["per_asset"] else 0
    return rep, n, rep["verdict"], rep["reason"]


def harness_turn_of_month(archive: Archive):
    """T-59: SPY's last four and first three trading days of the month earn more than the other days."""
    days, c = _closes(archive, "SPY"); rep = turn_of_month(days, c)
    return rep, rep["n"], rep["verdict"], rep["reason"]


def harness_weekday(archive: Archive):
    """T-60: some weekday's SPY return differs from the rest (Bonferroni over weekdays, halves agree)."""
    days, c = _closes(archive, "SPY"); rep = weekday_effect(days, c)
    return rep, rep["n"], rep["verdict"], rep["reason"]


def harness_gold_silver_ratio(archive: Archive):
    """T-61: the GLD/SLV log ratio mean-reverts after a 2-sigma deviation from its 250-day mean over the next 21 days."""
    da, a = _closes(archive, "GLD"); db, b = _closes(archive, "SLV"); rep = ratio_reversion(da, a, db, b)
    return rep, rep["n"], rep["verdict"], rep["reason"]


def harness_crypto_weekend(archive: Archive):
    """T-62: BTC weekend (Sat, Sun) close-to-close returns differ from weekday returns."""
    days, c = _closes(archive, "BTC-USD"); rep = weekend_effect(days, c)
    return rep, rep["n"], rep["verdict"], rep["reason"]


def _bundles_matching(archive: Archive, pattern: str) -> list[str]:
    names = sorted(e.name for e in archive.entries())
    return [n for n in names if n.startswith(pattern[:-1])] if pattern.endswith("*") else [n for n in names if n == pattern]


def _load_many(archive: Archive, pattern: str):
    for name in _bundles_matching(archive, pattern):
        yield from archive.load(name)


def harness_social_attention(archive: Archive) -> tuple[dict, int, str, str]:
    """Retail attention (standardised mention count per ticker-day) vs next-day absolute return.
    Inconclusive until 30 distinct collection days exist; the daily capture supplies them."""
    rep = attention_vs_abs_return(_load_many(archive, "social-derived-*"), _load_many(archive, "social-prices-*"))
    return rep, rep["n_ticker_days"], rep["verdict"], rep["reason"]


def harness_fear_greed(archive: Archive) -> tuple[dict, int, str, str]:
    """Crypto Fear & Greed extremes vs forward 7-day BTC log return, point in time, block-shift null, split halves."""
    rep = fear_greed_forward_returns(archive.load("crypto-fear-greed-history"), archive.load("daily-history-BTC-USD"))
    return rep, rep["n"], rep["verdict"], rep["reason"]


HARNESSES: dict[str, Callable] = {
    "market_calibration": harness_market_calibration,
    "multiscale_edge": harness_multiscale_edge,
    "bundle_arb_scan": harness_bundle_arb,
    "multifractal_scaling": harness_multifractal,
    "hurst_ci": harness_hurst,
    "markov_baseline": harness_markov,
    "msm_volatility": harness_msm,
    "dsr_pbo_harness": harness_overfit,
    "controls": harness_controls,
    "social_attention": harness_social_attention,
    "fear_greed_contrarian": harness_fear_greed,
    "longshot_bias": harness_longshot,
    "horizon_monotone": harness_horizon_monotone,
    "point_in_time_check": harness_point_in_time,
    "vrp_spx": harness_vrp_spx, "vrp_btc": harness_vrp_btc, "vrp_gold": harness_vrp_gold, "vrp_nasdaq": harness_vrp_nasdaq,
    "skew_tail": harness_skew_tail, "term_structure_reversion": harness_term_structure,
    "covered_call_overlay": harness_covered_call, "csp_overlay": harness_csp, "collar_overlay": harness_collar, "short_straddle_model": harness_short_straddle,
    "vrp_oil": harness_vrp_oil, "vrp_bonds": harness_vrp_bonds, "vrp_russell": harness_vrp_russell, "vrp_eth": harness_vrp_eth, "implied_move": harness_implied_move,
    "trend_rules": harness_trend_rules, "turn_of_month": harness_turn_of_month, "weekday_effect": harness_weekday,
    "gold_silver_ratio": harness_gold_silver_ratio, "crypto_weekend": harness_crypto_weekend,
}
BUNDLES_NEEDED = {
    "market_calibration": ["polymarket-price-history-daily", "polymarket-closed-markets"],
    "multiscale_edge": ["polymarket-price-history-daily", "polymarket-closed-markets"],
    "bundle_arb_scan": ["polymarket-books-snapshot"],
    "multifractal_scaling": ["polymarket-price-history-daily"], "hurst_ci": ["polymarket-price-history-daily"],
    "markov_baseline": ["polymarket-price-history-daily"], "msm_volatility": ["polymarket-price-history-daily"],
    "dsr_pbo_harness": ["polymarket-price-history-daily"], "controls": ["polymarket-price-history-daily", "polymarket-closed-markets"],
    "social_attention": ["social-derived-*", "social-prices-*"],
    "fear_greed_contrarian": ["crypto-fear-greed-history", "daily-history-BTC-USD"],
    "longshot_bias": ["polymarket-price-history-daily", "polymarket-closed-markets"],
    "horizon_monotone": ["polymarket-price-history-daily", "polymarket-closed-markets"],
    "point_in_time_check": ["crypto-fear-greed-history", "daily-history-BTC-USD"],
    "vrp_spx": ["cboe-VIX-history", "daily-history-SPY"], "vrp_btc": ["deribit-dvol-BTC-history", "daily-history-BTC-USD"],
    "vrp_gold": ["cboe-GVZ-history", "daily-history-GLD"], "vrp_nasdaq": ["cboe-VXN-history", "daily-history-QQQ"],
    "skew_tail": ["cboe-SKEW-history", "daily-history-SPY"], "term_structure_reversion": ["cboe-VIX-history", "cboe-VIX3M-history"],
    "covered_call_overlay": ["daily-history-SPY", "cboe-VIX-history", "fred-DTB3"], "csp_overlay": ["daily-history-SPY", "cboe-VIX-history", "fred-DTB3"],
    "collar_overlay": ["daily-history-SPY", "cboe-VIX-history", "fred-DTB3"], "short_straddle_model": ["daily-history-SPY", "cboe-VIX-history", "fred-DTB3"],
    "vrp_oil": ["cboe-OVX-history", "daily-history-USO"], "vrp_bonds": ["cboe-VXTLT-history", "daily-history-TLT"], "vrp_russell": ["cboe-RVX-history", "daily-history-IWM"],
    "vrp_eth": ["deribit-dvol-ETH-history", "daily-history-ETH-USD"], "implied_move": ["options-surface-*", "daily-history-SPY"],
    "trend_rules": ["daily-history-SPY", "daily-history-BTC-USD"], "turn_of_month": ["daily-history-SPY"], "weekday_effect": ["daily-history-SPY"],
    "gold_silver_ratio": ["daily-history-GLD", "daily-history-SLV"], "crypto_weekend": ["daily-history-BTC-USD"],
}


def load_registry(path: Path = REGISTRY) -> Optional[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_registry(reg: dict, path: Path = REGISTRY) -> None:
    atomic_write_text(path, json.dumps(reg, indent=1, ensure_ascii=False))


def run_all(only: Optional[list[str]] = None, ledger: Optional[Ledger] = None, archive: Optional[Archive] = None,
            log: Optional[ExperimentLog] = None, registry_path: Path = REGISTRY) -> list[dict]:
    ledger = ledger if ledger is not None else Ledger()
    archive = archive if archive is not None else Archive(ledger=ledger)
    log = log if log is not None else ExperimentLog(ledger=ledger)
    reg = load_registry(registry_path)
    theories_by_h: dict[str, list[str]] = {}
    if reg:
        for t in reg["theories"]:
            for h in t.get("experiments", []):
                theories_by_h.setdefault(h, []).append(t["id"])
    out = []
    for name, fn in HARNESSES.items():
        if only and name not in only:
            continue
        t0 = time.time()
        needed = BUNDLES_NEEDED[name]
        missing = [b for b in needed if not _bundles_matching(archive, b)]
        if missing:
            res = log.record(name, theories_by_h.get(name, []), {}, "n/a", 0, "inconclusive", f"missing data bundles {missing}", data_bundles=needed)
            out.append(res.as_dict()); continue
        try:
            stat, n, verdict, reason = fn(archive, ledger) if name == "controls" else fn(archive)
        except Exception as e:  # a crashing harness is a recorded error, not a silent skip
            stat, n, verdict, reason = {"error": repr(e)[:300]}, 0, "error", f"harness raised {type(e).__name__}"
        res = log.record(name, theories_by_h.get(name, []), stat, _null_for(name), n, verdict, reason, data_bundles=needed,
                         cost={"wall_seconds": round(time.time() - t0, 1)})
        out.append(res.as_dict())
        if reg:
            for t in reg["theories"]:
                if name in t.get("experiments", []) and t.get("status") in ("untested", "inconclusive", "supported", "not_supported"):
                    t["status"] = verdict if verdict != "error" else "inconclusive"
                    t.setdefault("results", []).append(res.id)
    if reg:
        save_registry(reg, registry_path)
    return out


def _null_for(name: str) -> str:
    return {
        "market_calibration": "coin (p=0.5) Brier 0.25; skill vs coin must be > 0 at every horizon",
        "multiscale_edge": "mean(outcome - price) = 0 at every horizon (bootstrap 95% interval)",
        "bundle_arb_scan": "no after-fee mispricing in the snapshot",
        "multifractal_scaling": "shuffled increments (same marginal, no clustering): concavity q95",
        "hurst_ci": "shuffled increments: H interval around 0.5",
        "markov_baseline": "base-rate predictor of the next move",
        "msm_volatility": "20-day rolling variance, out-of-sample Gaussian log score",
        "dsr_pbo_harness": "zero-skill best-of-N: DSR < 0.95 and PBO > 0.5 expected",
        "controls": "coin 0.25, oracle 0, market < coin on the same questions",
        "social_attention": "mentions permuted within ticker: Spearman rho with next-day |return| ~ 0",
        "fear_greed_contrarian": "Fear & Greed series circularly shifted against returns: conditional mean difference ~ 0",
        "longshot_bias": "calibrated bucket: mean(outcome - price) = 0 (bootstrap 95% interval)",
        "horizon_monotone": "skill flat across horizons",
        "point_in_time_check": "naive and point-in-time runs give the same verdict and sign",
        "vrp_spx": "implied variance = realised variance (studentized block bootstrap of the daily difference)",
        "vrp_btc": "implied variance = realised variance (block bootstrap)", "vrp_gold": "implied = realised (block bootstrap)", "vrp_nasdaq": "implied = realised (block bootstrap)",
        "skew_tail": "SKEW circularly shifted against returns: equal crash probability in top and bottom quintiles",
        "term_structure_reversion": "VIX/VIX3M ratio circularly shifted against VIX changes",
        "covered_call_overlay": "Sharpe(covered call) <= Sharpe(buy and hold), block bootstrap of paired cycles; model-priced",
        "csp_overlay": "Sharpe(put writing) <= Sharpe(buy and hold); model-priced", "collar_overlay": "descriptive thresholds; model-priced",
        "short_straddle_model": "mean straddle P&L = 0 (block bootstrap); model-priced",
        "vrp_oil": "implied = realised (block bootstrap)", "vrp_bonds": "implied = realised (block bootstrap)", "vrp_russell": "implied = realised (block bootstrap)", "vrp_eth": "implied = realised (block bootstrap)",
        "implied_move": "implied move = realised move (block bootstrap over captures)",
        "trend_rules": "zero-skill best-of-48 (6 rules x 8 assets): DSR and PBO deflation, block bootstrap vs buy-and-hold",
        "turn_of_month": "equal mean return on turn-of-month and other days (block bootstrap, block 21)",
        "weekday_effect": "equal means across weekdays (block bootstrap, Bonferroni over weekdays)",
        "gold_silver_ratio": "z-score series circularly shifted against future ratio changes",
        "crypto_weekend": "equal weekend and weekday means (two-sided block bootstrap)",
    }.get(name, "n/a")
