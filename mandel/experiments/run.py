"""
Experiment runner: load archived data, run harnesses, record results, update the theory registry.
=================================================================================================

``run_all`` is deterministic given the bundles; every result goes to ``state/experiments.jsonl``
and the ledger. Theories mapped to a harness move from ``untested`` to the harness verdict with a
pointer to the result id. Nothing is deleted when a theory is not supported: it is marked and
stays in the registry.
"""

from __future__ import annotations

import bisect
import inspect
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
from mandel.experiments.overfit import momentum_variants, overfit_report
from mandel.validation.backtest_eval import sharpe_ratio
from mandel.experiments.scaling import hurst_with_interval, multifractal_test
from mandel.experiments.social import attention_vs_abs_return, fear_greed_forward_returns
from mandel.experiments.volatility import implied_move_vs_realised, index_closes, overlay_backtest, overlay_verdict, price_closes, skew_tail, term_structure_reversion, variance_risk_premium
from mandel.experiments.underlying import ratio_reversion, trend_rules_multi, turn_of_month, weekday_effect, weekend_effect
from mandel.experiments import options_market as om
from mandel.experiments import batch4_carry, batch4_fact, batch4_fomc, batch4_ohlc, batch4_vx, batch5_fx, batch5_hourly, batch5_macro
from mandel.experiments import batch6_dir, batch6_surf, batch6_term, batch6_var, batch6_xc
from mandel.experiments import batch6b_bw, batch6b_chain, batch6b_dolt, batch6b_drb, batch6b_hedge, batch6b_misc, batch6b_volh
from mandel.experiments import batch6c_cal, batch6c_misc, batch6c_mom
from mandel.experiments import batch6c_macro, batch6c_pairs, batch6c_rates, batch6c_xs
from mandel.experiments import batch6c_pub
from mandel.experiments import batch6c_events
from mandel.experiments import underlying2 as u2
from mandel.forecasts import ForecastBook
from mandel.ledger import Ledger
from mandel.paths import MANDEL_ROOT

REGISTRY = MANDEL_ROOT / "theories" / "registry.json"


class MissingData(Exception):
    """An input the harness needs (listed in the INDEX or declared) cannot be read on this machine. run_all records the result as
    inconclusive and leaves theory status and results untouched, exactly as for a declared bundle that is absent."""

    def __init__(self, names):
        self.names = sorted(set(names))
        super().__init__(f"not on this machine: {', '.join(self.names)}")


def _series_by_market(price_rows) -> dict[str, np.ndarray]:
    by = {}
    for r in price_rows:
        v = r["value"]
        by.setdefault(v["market_id"], []).append((float(v["t"]), float(v["p"])))
    return {k: np.array([p for _, p in sorted(v)]) for k, v in by.items()}


def harness_market_calibration(archive: Archive, horizons=(1, 3, 7, 30, 90), min_n: int = 300) -> tuple[dict, int, str, str]:
    """T-01: Brier skill vs coin > 0 at EVERY registered horizon (1, 3, 7, 30, 90 days). A horizon scored on >= min_n markets (the
    trial's min_n, per horizon) with skill <= 0 falsifies 'every horizon'. A thin horizon (n < min_n) with skill <= 0 falsifies only
    when the failure would persist at min_n even if every missing market were forecast perfectly (n * Brier >= min_n * 0.25);
    otherwise it, like an unscored or thin horizon, makes the result inconclusive. n is the binding (smallest) per-horizon count."""
    rep = market_calibration(archive.load("polymarket-price-history-daily"), archive.load("polymarket-closed-markets"), horizons_days=horizons)
    h = rep["horizons"]
    ns = {k: int(h.get(k, {}).get("n", 0)) for k in horizons}
    n = min(ns.values())
    usable = {k: h[k]["skill_vs_coin"] for k in horizons if "brier" in h.get(k, {}) and h[k].get("skill_vs_coin") is not None}
    rep["n_by_horizon"] = {str(k): v for k, v in ns.items()}
    failing = {k: s for k, s in usable.items() if s <= 0 and (ns[k] >= min_n or ns[k] * h[k]["brier"] >= min_n * 0.25)}
    if failing:
        return rep, n, "not_supported", "market price fails to beat the coin at " + ", ".join(f"{k}d (skill {s:.2f}, n {ns[k]})" for k, s in failing.items())
    missing = [k for k in horizons if k not in usable]
    thin = [k for k in horizons if k in usable and ns[k] < min_n]
    if missing or thin:
        return rep, n, "inconclusive", (f"skill > 0 at every horizon scored on n >= {min_n}, but the claim needs every horizon with n >= {min_n}: "
                                        + ", ".join([f"{k}d unscored (n {ns[k]})" for k in missing]
                                                    + [f"{k}d n {ns[k]}" + (f", skill {usable[k]:.2f} <= 0 on n < min_n" if usable[k] <= 0 else "") for k in thin]))
    worst_skill = min(usable.values())
    return rep, n, "supported", f"market price beats the coin at every horizon (min skill {worst_skill:.2f}; smallest horizon n {n})"


def harness_multiscale_edge(archive: Archive, horizons=(1, 3, 7, 30, 90), min_n: int = 300) -> tuple[dict, int, str, str]:
    """T-03: some horizon's interval excludes zero AND the raw sign of mean(outcome - price) agrees across every registered horizon.
    markets.multiscale_edge gives signs_agree False (scored horizons disagree in sign), None (scored ones agree, a registered horizon is
    unscored) or True. Checked in that order: raw signs disagree -> not_supported; no horizon significant -> not_supported; an unscored
    horizon or any horizon below min_n (the trial's, per horizon) -> inconclusive; else supported. A failure counts only when decisive:
    the disagreement is between horizons with n >= min_n (or between intervals wholly on opposite sides of zero), and 'none
    significant' needs every registered horizon scored on n >= min_n; otherwise inconclusive. n is the binding per-horizon count."""
    rep = multiscale_edge(archive.load("polymarket-price-history-daily"), archive.load("polymarket-closed-markets"), horizons_days=horizons)
    H = rep["horizons"]
    ns = {h: int(H.get(h, {}).get("n", 0)) for h in horizons}
    n = min(ns.values())
    rep["n_by_horizon"] = {str(h): v for h, v in ns.items()}
    signs = {h: int(np.sign(H[h]["mean_error"])) for h in horizons if h in H}
    adequate = {s for h, s in signs.items() if ns[h] >= min_n}
    ci_sides = {(1 if H[h]["ci"][0] > 0 else -1) for h in signs if H[h]["ci"][0] > 0 or H[h]["ci"][1] < 0}
    disagree_decisive = 0 in adequate or len(adequate) > 1 or len(ci_sides) > 1
    thin = [f"{h}d unscored (n {ns[h]})" if h not in H else f"{h}d n {ns[h]}" for h in horizons if ns[h] < min_n or h not in H]
    txt = "raw sign of mean(outcome - price) by horizon " + ", ".join(f"{h}d {H[h]['mean_error']:+.4f} (n {ns[h]})" for h in horizons if h in H) + \
        f"; {rep['n_scales_significant']}/{rep['n_scales_total']} scored horizons with an interval excluding zero"
    if rep["signs_agree"] is False and disagree_decisive:
        return rep, n, "not_supported", txt + "; raw signs disagree across horizons"
    if rep["n_scales_significant"] == 0 and not thin:
        return rep, n, "not_supported", txt + "; no horizon's interval excludes zero: no structural market bias to be consistent about"
    if rep["signs_agree"] is not True or rep["n_scales_significant"] == 0 or thin:
        why = ("raw signs disagree only where n < min_n" if rep["signs_agree"] is False else "no horizon significant yet" if rep["n_scales_significant"] == 0
               else "signs agree where scored")
        return rep, n, "inconclusive", txt + f"; {why}, but the claim needs every horizon with n >= {min_n}" + (": " + ", ".join(thin) if thin else "")
    return rep, n, "supported", txt + "; raw signs agree at every horizon"


def harness_bundle_arb(archive: Archive, min_n: int = 200) -> tuple[dict, int, str, str]:
    """T-04: >= 1 after-fee LONG bundle mispricing (best-ask YES + best-ask NO + fee + gas < 1, depth >= 5 USD) per 100 markets in every
    snapshot, across >= 2 snapshots. One snapshot can falsify persistence (a snapshot below the rate) but cannot confirm it. Short-side
    crosses (bids summing above 1) are outside the claim and reported only. A snapshot of fewer than min_n markets can neither confirm
    nor falsify: only snapshots of >= min_n markets count against the claim; a thin one below the rate leaves it inconclusive."""
    names = ["polymarket-books-snapshot"] * bool(_bundles_matching(archive, "polymarket-books-snapshot")) + [n for n in _bundles_matching(archive, "polymarket-books-2*")]
    snaps = []
    for name in names:
        rep = bundle_arb_scan(archive.load(name))
        if rep["markets_scanned"] >= 50:
            found = rep["long_after_fees"]
            snaps.append({"bundle": name, "markets": rep["markets_scanned"], "found": found, "rate_per_100": 100 * found / rep["markets_scanned"],
                          "short_after_fees_reported_only": rep["short_after_fees"],
                          "gross_long_candidates": rep["gross_long_candidates"], "median_spread": rep["median_round_trip_spread"], "examples": rep["examples_long"][:3],
                          "examples_short_reported_only": rep["examples_short"][:3]})
    if not snaps:
        return {"snapshots": []}, 0, "inconclusive", "no snapshot with 50+ markets"
    ok = [s["rate_per_100"] >= 1 for s in snaps]
    falsifying = [s for s in snaps if s["rate_per_100"] < 1 and s["markets"] >= min_n]
    verdict = "not_supported" if falsifying else ("supported" if all(ok) and len(snaps) >= 2 and all(s["markets"] >= min_n for s in snaps) else "inconclusive")
    txt = "; ".join(f"{s['bundle'].replace('polymarket-books-', '')}: {s['found']} after-fee long bundles in {s['markets']} markets ({s['gross_long_candidates']} with YES+NO asks below 1 before fees; "
                    f"{s['short_after_fees_reported_only']} short-side, not counted), median round-trip spread {s['median_spread']:.3f}" for s in snaps)
    return {"snapshots": snaps}, sum(s["markets"] for s in snaps), verdict, f"{len(snaps)} snapshot(s): {txt}" + \
        (f"; a snapshot needs >= {min_n} markets to count" if verdict == "inconclusive" and any(s["markets"] < min_n for s in snaps) else "")


def harness_multifractal(archive: Archive, max_markets: int = 40, n_shuffles: int = 200, min_n: int = 40) -> tuple[dict, int, str, str]:
    """T-06: > 25% of series with tau(q) concavity beyond the 95th percentile of 200 shuffles per series (the trial's count).
    Fewer than min_n series cannot support the claim, and falsify it only when the share would stay <= 25% at min_n even if every
    missing series exceeded the null; otherwise inconclusive."""
    series = _series_by_market(archive.load("polymarket-price-history-daily"))
    long_enough = [(k, s) for k, s in series.items() if s.size >= 120]
    long_enough.sort(key=lambda kv: -kv[1].size)
    results = []
    for k, s in long_enough[:max_markets]:
        r = multifractal_test(np.log(np.clip(s, 0.01, 0.99) / (1 - np.clip(s, 0.01, 0.99))), n_shuffles=n_shuffles)
        results.append({"market": k, "n": r.n, "concavity": r.concavity, "null_q95": r.null_concavity_q95, "exceeds": r.exceeds_null})
    n = len(results)
    if n < 10:
        return {"per_market": results}, n, "inconclusive", "fewer than 10 series of 120+ daily points"
    n_exceed = sum(1 for r in results if r["exceeds"]); frac = n_exceed / n
    verdict = "supported" if frac > 0.25 else "not_supported"
    if n < min_n and (verdict == "supported" or (n_exceed + min_n - n) / min_n > 0.25):
        verdict = "inconclusive"
    return {"fraction_exceeding_null": frac, "n_series": n, "n_shuffles": n_shuffles, "per_market": results[:40]}, n, verdict, \
        f"{frac:.0%} of {n} daily logit-price series show concavity beyond the shuffled null ({n_shuffles} shuffles; threshold 25%; chance ~5%)" + \
        (f"; fewer than the {min_n} series the trial requires" + ("; fails even if every missing series counted for the claim" if verdict == "not_supported" else "") if n < min_n else "")


def harness_hurst(archive: Archive, max_markets: int = 40, n_null: int = 200, min_n: int = 40) -> tuple[dict, int, str, str]:
    """T-07: anti-persistence in a majority of markets, outside the shuffle null. Two criteria: share of series with H < 0.5 > 50%,
    and share significantly ANTI-persistent (H below its own 200-shuffle 2.5% quantile) > 25%. Series above the null (persistent)
    count against the claim, never for it. Fewer than min_n series cannot support the claim, and falsify it only when a criterion
    would still fail at min_n even if every missing series were significantly anti-persistent; otherwise inconclusive."""
    series = _series_by_market(archive.load("polymarket-price-history-daily"))
    long_enough = sorted([(k, s) for k, s in series.items() if s.size >= 120], key=lambda kv: -kv[1].size)[:max_markets]
    rows = []
    for k, s in long_enough:
        x = np.log(np.clip(s, 0.01, 0.99) / (1 - np.clip(s, 0.01, 0.99)))
        h = hurst_with_interval(x, n_null=n_null)
        h["market"] = k
        rows.append(h)
    n = len(rows)
    if n < 10:
        return {"per_market": rows}, n, "inconclusive", "fewer than 10 long series"
    fin = [r for r in rows if np.isfinite(r["H"])]
    Hs = np.array([r["H"] for r in fin])
    below = sum(1 for r in fin if r["H"] < 0.5) / n
    anti = sum(1 for r in fin if np.isfinite(r["null_lo"]) and r["H"] < r["null_lo"])
    persistent = sum(1 for r in fin if np.isfinite(r["null_hi"]) and r["H"] > r["null_hi"])
    verdict = "supported" if below > 0.5 and anti / n > 0.25 else "not_supported"
    n_below, pad = sum(1 for r in fin if r["H"] < 0.5), max(min_n - n, 0)
    if n < min_n and (verdict == "supported" or ((n_below + pad) / min_n > 0.5 and (anti + pad) / min_n > 0.25)):
        verdict = "inconclusive"
    med = float(np.median(Hs)) if Hs.size else float("nan")
    return {"median_H": med, "n_series": n, "n_null": n_null, "share_H_below_half": below, "n_anti_persistent_outside_null": anti,
            "share_anti_persistent_outside_null": anti / n, "n_persistent_outside_null": persistent, "per_market": rows}, n, verdict, \
        (f"median H {med:.2f}; {below:.0%} of {n} series with H < 0.5 (need > 50%); {anti}/{n} significantly anti-persistent, below their "
         f"{n_null}-shuffle null (need > 25%); {persistent} significantly persistent (count against)" + (f"; fewer than the {min_n} series the trial requires" + ("; fails even if every missing series counted for the claim" if verdict == "not_supported" else "") if n < min_n else ""))


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


_MOM_GRID = {k: p.default for k, p in inspect.signature(momentum_variants).parameters.items() if k in ("lookbacks", "holds")}


def _momentum_pnl_by_time(series_t: list[tuple[np.ndarray, np.ndarray]], lookbacks=_MOM_GRID["lookbacks"], holds=_MOM_GRID["holds"]) -> list[tuple]:
    """T-10's declared momentum rules with momentum_variants' own lb/hd construction, kept per rule with each return's end time and
    market: [(name, pnl, t_end, market index)]. series_t: [(t, price)] per market, sorted by t. pnl[j] = sign(p[j+lb] - p[j]) *
    r[j+lb] ends at t[j+lb+1]; hd > 1 keeps every hd-th return, as momentum_variants does. Nothing is truncated or aligned by row."""
    out = []
    for lb in lookbacks:
        for hd in holds:
            P, Te, M = [], [], []
            for m, (t, s) in enumerate(series_t):
                if lb + 1 >= s.size:
                    continue
                r = np.diff(s) / np.maximum(s[:-1], 1e-6)
                sig = np.sign(s[lb:-1] - s[:-lb - 1])
                pnl = sig[:len(r) - lb] * r[lb:lb + len(sig)]
                te = np.asarray(t, dtype=float)[lb + 1:lb + 1 + pnl.size]
                P.append(pnl[::hd]); Te.append(te[::hd]); M.append(np.full(len(pnl[::hd]), m))
            if P:
                out.append((f"mom_lb{lb}_h{hd}", np.concatenate(P), np.concatenate(Te), np.concatenate(M)))
    return out


def harness_holdout_sharpe(archive: Archive, max_markets: int = 150, min_n: int = 100) -> tuple[dict, int, str, str]:
    """T-36: the in-sample best of the declared momentum rules (T-10's search) has holdout Sharpe <= 0. One calendar split, the same
    for every rule: the cutoff is the median end time of all the rules' pooled returns; returns ending at or before it are in-sample,
    later ones holdout (a bot tuned on a backtest faces a later period). Each rule's returns are rebuilt per market with their end times
    (T-10's construction), so every rule is ranked on the same markets and dates. Fewer than min_n holdout periods or series: inconclusive
    whatever the sign (no interval to call a failure decisive)."""
    rows = {}
    for r in archive.load("polymarket-price-history-daily"):
        v = r["value"]
        rows.setdefault(v["market_id"], []).append((float(v["t"]), float(v["p"])))
    series = {k: sorted(v) for k, v in rows.items()}
    picked = [v for _, v in sorted(series.items(), key=lambda kv: -len(kv[1]))[:max_markets] if len(v) >= 60]
    if len(picked) < 20:
        return {}, len(picked), "inconclusive", "fewer than 20 series"
    rules = _momentum_pnl_by_time([(np.array([t for t, _ in v]), np.array([p for _, p in v])) for v in picked])
    cutoff = float(np.median(np.concatenate([te for _, _, te, _ in rules])))
    split = [(name, pnl[te <= cutoff], pnl[te > cutoff], m[te <= cutoff], m[te > cutoff]) for name, pnl, te, m in rules]
    is_sr = np.array([sharpe_ratio(x) for _, x, _, _, _ in split])
    best = int(np.argmax(is_sr))
    name, x_is, x_ho, m_is, m_ho = split[best]
    ho = float(sharpe_ratio(x_ho))
    n = int(x_ho.size)
    stat = {"n_variants": len(rules), "n_series": len(picked), "split": "one calendar cutoff for every rule: median end time of the pooled returns",
            "cutoff_t": cutoff, "cutoff_utc": time.strftime("%Y-%m-%d %H:%M", time.gmtime(cutoff)),
            "n_is_periods": int(x_is.size), "n_holdout_periods": n, "n_is_markets": int(np.unique(m_is).size), "n_holdout_markets": int(np.unique(m_ho).size),
            "per_rule_is_holdout_periods": {nm: [int(a.size), int(b.size)] for nm, a, b, _, _ in split},
            "is_best_variant": name, "is_best_sharpe": float(is_sr[best]), "holdout_sharpe": ho}
    if n < min_n or len(picked) < min_n:
        verdict = "inconclusive"
    elif ho > 0:
        verdict = "not_supported"
    else:
        verdict = "supported"
    return stat, n, verdict, (f"in-sample best of {len(rules)} momentum rules {name} (IS Sharpe {is_sr[best]:+.4f} over {x_is.size} periods to {stat['cutoff_utc']} UTC) "
                              f"has holdout Sharpe {ho:+.4f} over {n} later periods from {len(picked)} series (pass: <= 0)"
                              + (f"; below min_n {min_n}" if verdict == "inconclusive" else ""))


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


def _event_keys(market_rows) -> dict[str, str]:
    """market id -> dependence cluster: events[0].id, else negRiskMarketID, else the market itself. Markets of one negRisk event are
    mutually exclusive and resolve together, so they are one unit for resampling."""
    out = {}
    for r in market_rows:
        m = r.get("value", {})
        mid = str(m.get("id"))
        ev = m.get("events")
        if isinstance(ev, str):
            try:
                ev = json.loads(ev)
            except ValueError:
                ev = None
        eid = ev[0].get("id") if isinstance(ev, list) and ev and isinstance(ev[0], dict) else None
        out[mid] = f"event:{eid}" if eid is not None else (f"negrisk:{m['negRiskMarketID']}" if m.get("negRiskMarketID") else f"market:{mid}")
    return out


def _cluster_mean_ci(e: np.ndarray, keys: list, n_boot: int, seed: int, q=(0.025, 0.975)) -> tuple[float, float, int]:
    """Percentile CI of the pooled mean sum(e)/count with whole clusters resampled (ratio estimator)."""
    _, inv = np.unique(np.asarray(keys, dtype=object).astype(str), return_inverse=True)
    S = np.bincount(inv, weights=e); C = np.bincount(inv).astype(float); G = S.size
    idx = np.random.default_rng(seed).integers(0, G, size=(n_boot, G))
    boots = S[idx].sum(axis=1) / C[idx].sum(axis=1)
    lo, hi = (float(x) for x in np.quantile(boots, list(q)))
    return lo, hi, int(G)


def harness_longshot(archive: Archive, horizon: int = 7, hi_p: float = 0.10, n_boot: int = 2000, seed: int = 0, min_n: int = 300) -> tuple[dict, int, str, str]:
    """T-02: in the under-0.10 bucket at the 7d horizon, mean(outcome - price) < 0 (classic longshot bias:
    cheap YES over-priced). Event-clustered bootstrap 95% interval (markets of one event resampled together); the upper bound must be
    below zero. Below the trial's min_n markets a passing bound is only inconclusive, and a failing one falsifies only when the whole
    interval lies above zero (decisive); an interval straddling zero on thin data is inconclusive."""
    market_rows = list(archive.load("polymarket-closed-markets"))
    outcomes = resolved_outcomes(market_rows)
    rows = price_at_horizons(archive.load("polymarket-price-history-daily"), outcomes, horizons_days=(horizon,))[horizon]
    picked = [(p, o, mid) for p, o, mid in rows if p < hi_p]
    sel = np.array([o - p for p, o, _ in picked])
    if sel.size < 100:
        return {"n": int(sel.size)}, int(sel.size), "inconclusive", f"only {sel.size} observations under {hi_p}"
    cluster = _event_keys(market_rows)
    lo, hi, n_events = _cluster_mean_ci(sel, [cluster.get(mid, f"market:{mid}") for _, _, mid in picked], n_boot, seed)
    stat = {"n": int(sel.size), "n_events": n_events, "horizon_days": horizon, "bucket_hi": hi_p, "mean_error": float(sel.mean()), "ci": [lo, hi],
            "ci_method": "event-clustered percentile bootstrap (events[0].id, else negRiskMarketID, else market)",
            "yes_events": int(sum(1 for p, o, _ in picked if o == 1)), "mean_price": float(np.mean([p for p, _, _ in picked]))}
    if hi >= 0:
        verdict = "not_supported" if sel.size >= min_n or lo > 0 else "inconclusive"
    elif sel.size < min_n:
        verdict = "inconclusive"
    else:
        verdict = "supported"
    return stat, int(sel.size), verdict, (f"<{hi_p} bucket at {horizon}d: mean(outcome-price) {sel.mean():+.4f}, event-clustered 95% [{lo:+.4f}, {hi:+.4f}], "
                                          f"{stat['yes_events']} YES events of {sel.size} markets in {n_events} events" + (f"; below min_n {min_n}" if verdict == "inconclusive" else ""))


def harness_horizon_monotone(archive: Archive, horizons=(1, 3, 7, 30, 90), required=(1, 3, 7, 30, 90), min_n: int = 300) -> tuple[dict, int, str, str]:
    """T-13: skill increases monotonically as the horizon shortens (90d -> 1d) over the claim's data (T-01's horizons, 3d included):
    skill(1d) > skill(3d) > skill(7d) > skill(30d) > skill(90d), strictly, no tolerance. A strict-order violation between two horizons
    both scored on >= min_n markets (the trial's min_n, per horizon) falsifies the chain; a violation involving a thinner horizon, an
    unscored horizon or a thin one leaves it inconclusive. n is the binding per-horizon minimum."""
    rep = market_calibration(archive.load("polymarket-price-history-daily"), archive.load("polymarket-closed-markets"), horizons_days=horizons)
    H = rep["horizons"]
    skills = {h: H[h]["skill_vs_coin"] for h in horizons if "brier" in H.get(h, {}) and H[h].get("skill_vs_coin") is not None}
    ns = {h: int(H.get(h, {}).get("n", 0)) for h in horizons}
    n = min(ns[h] for h in required)
    avail = [h for h in required if h in skills]
    violations = [(a, b) for i, a in enumerate(avail) for b in avail[i + 1:] if not skills[a] > skills[b]]
    decisive = [(a, b) for a, b in violations if ns[a] >= min_n and ns[b] >= min_n]
    missing = [h for h in required if h not in skills]
    thin = [h for h in required if h in skills and ns[h] < min_n]
    stat = {"skills": {str(h): skills[h] for h in horizons if h in skills}, "n_by_horizon": {str(h): ns[h] for h in horizons},
            "required": list(required), "monotone": not violations and not missing}
    txt = "skill by horizon " + ", ".join(f"{h}d {skills[h]:.3f}" for h in horizons if h in skills)
    if decisive:
        return stat, n, "not_supported", txt + f"; strict order fails on n >= {min_n}: " + ", ".join(f"skill({a}d) <= skill({b}d)" for a, b in decisive)
    if violations or missing or thin:
        return stat, n, "inconclusive", txt + "".join(f"; skill({a}d) <= skill({b}d) with n < {min_n}" for a, b in violations) + \
            f"; the chain needs every one of {', '.join(f'{h}d' for h in required)} with n >= {min_n}: " + \
            ", ".join([f"{h}d unscored (n {ns[h]})" for h in missing] + [f"{h}d n {ns[h]}" for h in thin])
    return stat, n, "supported", txt + " (strictly decreasing " + " > ".join(f"{h}d" for h in required) + ")"


def harness_point_in_time(archive: Archive) -> tuple[dict, int, str, str]:
    """T-19: does honouring available_at change a verdict? Runs the Fear & Greed harness with the naive join on observed_at
    (lag -1: the forward window starts at close(d-1), before day d's index was published) and the point-in-time one (lag 0: the
    first close at or after available_at = observed_at + 24 h). Pass: the verdicts differ. The sign of the fear-side effect is
    reported only."""
    fng = list(archive.load("crypto-fear-greed-history")); px = list(archive.load("daily-history-BTC-USD"))
    naive = fear_greed_forward_returns(fng, px, lag_days=-1, n_boot=500)
    honest = fear_greed_forward_returns(fng, px, lag_days=0, n_boot=500)
    changed = naive["verdict"] != honest["verdict"]
    dn, dh = naive.get("d_fear", float("nan")), honest.get("d_fear", float("nan"))
    sign_flip = bool(dn is not None and dh is not None and np.isfinite(dn) and np.isfinite(dh) and np.sign(dn) != np.sign(dh))
    stat = {"naive": {k: naive.get(k) for k in ("verdict", "d_fear", "d_greed", "p_fear", "p_greed")},
            "honest": {k: honest.get(k) for k in ("verdict", "d_fear", "d_greed", "p_fear", "p_greed")}, "changed": bool(changed),
            "d_fear_sign_flip_reported_only": sign_flip}
    return stat, int(honest.get("n", 0)), "supported" if changed else "not_supported", \
        f"naive {naive['verdict']} (d_fear {naive.get('d_fear', float('nan')):+.4f}) vs point-in-time {honest['verdict']} (d_fear {honest.get('d_fear', float('nan')):+.4f}): " \
        f"{'verdict changed' if changed else 'no verdict change on this harness'}" + ("; d_fear sign flips (reported only)" if sign_flip else "")


def _vrp(archive: Archive, index_bundle: str, price_bundle: str, symbol: str, window: int, ppy: int, min_n: int = 2000) -> tuple[dict, int, str, str]:
    """min_n: the trial's own, in daily windows (2000; 1000 for T-49 and T-67)."""
    rep = variance_risk_premium(archive.load(index_bundle), archive.load(price_bundle), window=window, symbol=symbol, periods_per_year=ppy, min_n=min_n)
    return rep, rep["n"], rep["verdict"], rep["reason"]


def harness_vrp_spx(archive: Archive):
    """T-48: VIX^2 exceeds the realised variance of SPY over the next 21 trading days (model-free VRP)."""
    return _vrp(archive, "cboe-VIX-history", "daily-history-SPY", "SPY", 21, 252)


def harness_vrp_btc(archive: Archive):
    """T-49: DVOL^2 exceeds realised BTC variance over the next 30 calendar days (Deribit DVOL is a 30-day index)."""
    return _vrp(archive, "deribit-dvol-BTC-history", "daily-history-BTC-USD", "BTC-USD", 30, 365, min_n=1000)


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
    return _vrp(archive, "deribit-dvol-ETH-history", "daily-history-ETH-USD", "ETH-USD", 30, 365, min_n=1000)


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
    for v, rep in ((va, a), (vb, b)):
        v["p_value_sharpe_diff"] = _sharpe_diff_p(*_sharpe_basis(rep))
        v["p_value_sharpe_diff_basis"] = rep.get("sharpe_basis", "raw")
    return {"at_vix": va, "at_iv_scale_0.81": vb, "model_priced": True, "note": MODEL_NOTE}, a, b


def _sharpe_basis(rep: dict) -> tuple[np.ndarray, np.ndarray]:
    """(strategy, benchmark) per-cycle returns on the basis of the Sharpes overlay_backtest reports: funded positions (stock legs,
    cash-secured put) and the buy-and-hold benchmark in excess of the per-cycle bill; an unfunded straddle raw (already an excess return)."""
    bill = np.asarray(rep["bill_returns"], dtype=float)
    funded = rep.get("strategy") not in ("short_straddle", "long_straddle")
    s = np.asarray(rep["returns"], dtype=float)
    return (s - bill if funded else s), np.asarray(rep["benchmark"], dtype=float) - bill


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
    """T-58: a declared grid of six long/flat trend rules beats buy-and-hold on a majority of eight assets after deflation.
    The denominator is always the eight named assets: an asset that cannot be loaded makes the run a missing-data result, never a
    smaller majority."""
    series, absent = {}, []
    for sym in TREND_ASSETS:
        try:
            _, c = _closes(archive, sym); series[sym] = c
        except (KeyError, FileNotFoundError):
            absent.append(f"daily-history-{sym}")
    if absent:
        raise MissingData(absent)
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


def _chain_captures(archive: Archive, sym: str) -> list[tuple[str, float, list]]:
    """(day, spot, rows) for every raw chain capture of sym listed in the INDEX; spot from that day's surface bundle. The raw chains are
    kept off git (in_git=False), so a checkout can list captures it does not hold: any listed capture (or its surface) that is not on
    this machine raises MissingData instead of being skipped, so 'day one' never shifts silently."""
    out, unreadable = [], []
    for name in _bundles_matching(archive, f"options-chain-{sym}-*"):
        day = name.rsplit("-", 3)[-3:]; day = "-".join(day)
        try:
            rows = list(archive.load(name))
        except FileNotFoundError:
            unreadable.append(name); continue
        spot = None
        if _bundles_matching(archive, f"options-surface-{day}"):
            try:
                spot = next((r["value"]["underlying"] for r in archive.load(f"options-surface-{day}") if r["value"]["symbol"] == sym), None)
            except FileNotFoundError:
                unreadable.append(f"options-surface-{day}"); continue
        if rows and spot:
            out.append((day, float(spot), rows))
    if unreadable:
        raise MissingData(unreadable)
    return out


def harness_forward_variance(archive):
    rep = om.forward_variance_premium(archive.load("cboe-VIX-history"), archive.load("cboe-VIX3M-history"), archive.load("daily-history-SPY")); return rep, rep["n"], rep["verdict"], rep["reason"]


def harness_term_vs_spot(archive):
    rep = om.term_vs_spot_premium(archive.load("cboe-VIX-history"), archive.load("cboe-VIX3M-history"), archive.load("daily-history-SPY")); return rep, rep["n_cycles"], rep["verdict"], rep["reason"]


def harness_vvix(archive):
    rep = om.vvix_premium(archive.load("cboe-VVIX-history"), archive.load("cboe-VIX-history")); return rep, rep["n"], rep["verdict"], rep["reason"]


def harness_vix9d(archive):
    rep = om.short_horizon_conditional(archive.load("cboe-VIX9D-history"), archive.load("daily-history-SPY")); return rep, rep.get("n_signals", rep.get("n", 0)), rep["verdict"], rep["reason"]


def harness_vix_forward_contango(archive):
    rep = om.vix_forward_contango(archive.load("cboe-VIX-history"), archive.load("cboe-VIX3M-history")); return rep, rep["n"], rep["verdict"], rep["reason"]


def harness_vix_spike(archive):
    rep = om.vix_spike_forward(archive.load("cboe-VIX-history"), archive.load("cboe-VIX3M-history")); return rep, rep.get("n_events", rep.get("n", 0)), rep["verdict"], rep["reason"]


def harness_box_lend(archive):
    rep = om.box_lending(_chain_captures(archive, "SPX"), archive.load("fred-DTB3"), archive.load("fred-DGS2")); return rep, rep["n_days"], rep["verdict"], rep["reason"]


def harness_box_borrow(archive):
    rep = om.box_borrowing(_chain_captures(archive, "SPX"), archive.load("fred-DTB3"), archive.load("fred-DGS2")); return rep, rep["n_days"], rep["verdict"], rep["reason"]


def harness_parity(archive):
    caps = [(d, sym, sp, rows) for sym in ("SPY", "SPX") for d, sp, rows in _chain_captures(archive, sym)]
    rep = om.parity_check(caps, archive.load("fred-DTB3")); return rep, rep.get("n_days", 0), rep["verdict"], rep["reason"]


def harness_pinning(archive):
    rep = om.expiry_pinning(archive.load("daily-history-SPY")); return rep, rep["n_opex"], rep["verdict"], rep["reason"]


def harness_btc_weekend_var(archive):
    rep = om.btc_weekend_variance(archive.load("daily-history-BTC-USD")); return rep, rep["years"], rep["verdict"], rep["reason"]


def _ls(archive, sym):
    return u2.load_series(archive, sym)


def _bill(archive):
    d = index_closes(archive.load("fred-DTB3")); ks = sorted(d); return ks, [d[k] for k in ks]


def _u2(fn):
    def h(archive):
        rep = fn(archive)
        n = int(rep["n"]) if rep.get("n") is not None else \
            next((int(rep[k]) for k in ("n_years", "n_months", "n_weeks", "n_quarters", "n_signals", "n_test_days", "n_opex_weeks", "n_days") if rep.get(k)), 0)
        return rep, n, rep["verdict"], rep["reason"]
    h.__doc__ = fn.__doc__
    return h


def _with_n(rep: dict, n: int) -> dict:
    """Attach the number of daily observations the verdict rests on, unless the function already reports its own 'n'."""
    rep.setdefault("n", int(n))
    return rep


def _n_returns(*series, burn: int = 0, since: Optional[str] = None) -> int:
    """Smallest count of daily returns across (days, closes) series, after a burn-in of `burn` returns, ending on or after `since`."""
    return min((sum(1 for d in days[1:][burn:] if since is None or d >= since) for days, _ in series), default=0)


def _excess_index(series: tuple, bill: tuple) -> tuple[list, np.ndarray]:
    """(days, index) of the series in excess of T-bills: E_i = E_{i-1} * (P_i / P_{i-1} - rf_i), rf_i = the latest DTB3 print on or
    before day i-1 (percent) / 100 / 252, i.e. the bill rate known when the day's holding period starts. Days before the first bill
    print are dropped. Feeding this index to a Sharpe or switch rule makes every return an excess return, and a flat (cash) day earns
    the bill: sig * (r - rf) is the excess return of sig * r + (1 - sig) * rf."""
    days, c = series; bdays, bvals = bill
    i0 = next((i for i, d in enumerate(days) if bisect.bisect_right(bdays, d) > 0), None)
    if i0 is None:
        raise MissingData(["fred-DTB3 (no bill print before the series)"])
    out = [float(c[i0])]
    for i in range(i0 + 1, len(days)):
        rf = bvals[bisect.bisect_right(bdays, days[i - 1]) - 1] / 100 / 252
        out.append(out[-1] * (c[i] / c[i - 1] - rf))
    return list(days[i0:]), np.array(out)


TOM_ASSETS, TOM_COST_BPS = ("QQQ", "IWM", "TLT", "GLD", "BTC-USD"), {"QQQ": 2, "IWM": 2, "TLT": 2, "GLD": 3, "BTC-USD": 40}


def _u2_tom(a, fn_name: str):
    s = {sym: _ls(a, sym) for sym in TOM_ASSETS}
    return _with_n(getattr(u2, fn_name)(s, TOM_COST_BPS), _n_returns(*s.values()))


def _accepts_bills(fn) -> bool:
    try:
        return "bill_days" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _u2_low_vol_v2(a):
    """T-448's statistic is on daily excess returns over T-bills. If underlying2.low_vol_v2 takes the bill series it subtracts the bill
    itself; otherwise both legs are passed as excess-return indexes (never both, so the bill is never subtracted twice)."""
    b = _bill(a)
    if _accepts_bills(u2.low_vol_v2):
        return u2.low_vol_v2(_ls(a, "USMV"), _ls(a, "SPY"), bill_days=b[0], bill_vals=b[1])
    rep = u2.low_vol_v2(_excess_index(_ls(a, "USMV"), b), _excess_index(_ls(a, "SPY"), b))
    rep["returns"] = "excess over fred-DTB3 (prior-day print / 100 / 252)"; rep["reason"] = "excess over T-bills: " + rep["reason"]
    return rep


def _u2_svxy_v2(a):
    """T-435 holds SGOV (bills) when out of SVXY. If underlying2.svxy_v2 takes the bill series it credits cash days itself; otherwise the
    SVXY leg is an excess-return index, so off days earn the bill and the Sharpe difference is on excess returns."""
    b = _bill(a); vix, vix3m = index_closes(a.load("cboe-VIX-history")), index_closes(a.load("cboe-VIX3M-history"))
    if _accepts_bills(u2.svxy_v2):
        return u2.svxy_v2(_ls(a, "SVXY"), vix, vix3m, bill_days=b[0], bill_vals=b[1])
    rep = u2.svxy_v2(_excess_index(_ls(a, "SVXY"), b), vix, vix3m)
    rep["returns"] = "excess over fred-DTB3 (prior-day print / 100 / 252); cash days earn the bill"; rep["reason"] = "excess over T-bills, cash earns the bill: " + rep["reason"]
    return rep


def _u2_gold_autumn_v2(a):
    g = _ls(a, "GLD")
    return _with_n(u2.gold_autumn_v2(g), max(sum(1 for d in g[0] if d >= "2010-12-31") - 1, 0))


def _u2_low_vol_tilt(a):
    """T-384's Sharpe difference is on daily excess returns over T-bills: underlying2.low_vol_tilt subtracts the bill known at t-1."""
    usmv, spy = _ls(a, "USMV"), _ls(a, "SPY"); b = _bill(a)
    return _with_n(u2.low_vol_tilt(usmv, spy, _ls(a, "SPLV"), _ls(a, "SPHB"), bill_days=b[0], bill_vals=b[1]), max(len(set(usmv[0]) & set(spy[0])) - 1, 0))


def _u2_golden_cross(a, v2: bool):
    btc, eth = _ls(a, "BTC-USD"), _ls(a, "ETH-USD")
    if v2:   # golden_cross_v2 tests BTC returns from 2015-04 after a 300-day burn-in
        return _with_n(u2.golden_cross_v2(btc, eth), _n_returns(btc, burn=300, since="2015-04-01"))
    return _with_n(u2.golden_cross(btc, eth), _n_returns(btc, eth, burn=300))


U2_HARNESSES = {
    "tom_replication": _u2(lambda a: _u2_tom(a, "tom_replication")),
    "quarter_end_reversal": _u2(lambda a: u2.quarter_end_reversal(*_ls(a, "IWM"))),
    "santa_rally": _u2(lambda a: u2.santa_rally(_ls(a, "^GSPC"), _ls(a, "SPY"))),
    "january_small_cap": _u2(lambda a: u2.january_small_cap(_ls(a, "IWM"), _ls(a, "SPY"), _ls(a, "^RUT"), _ls(a, "^GSPC"))),
    "sell_in_may": _u2(lambda a: u2.sell_in_may(_ls(a, "^GSPC"), _ls(a, "SPY"))),
    "opex_week": _u2(lambda a: u2.opex_week(*_ls(a, "SPY"))),
    "btc_monday": _u2(lambda a: (lambda s: _with_n(u2.btc_monday(*s), _n_returns(s)))(_ls(a, "BTC-USD"))),
    "gold_autumn": _u2(lambda a: (lambda g: _with_n(u2.gold_autumn(g, _ls(a, "GC=F")), _n_returns(g)))(_ls(a, "GLD"))),
    "golden_cross_crypto": _u2(lambda a: _u2_golden_cross(a, v2=False)),
    "metals_tsmom": _u2(lambda a: (lambda b: u2.metals_tsmom(_ls(a, "GLD"), _ls(a, "SLV"), _ls(a, "GC=F"), _ls(a, "SI=F"), bill_days=b[0], bill_vals=b[1]))(_bill(a))),
    "crypto_weekly_tsmom": _u2(lambda a: u2.crypto_weekly_tsmom(_ls(a, "BTC-USD"), _ls(a, "ETH-USD"))),
    "btc_reversal": _u2(lambda a: u2.btc_reversal(*_ls(a, "BTC-USD"))),
    "gem_dual_momentum": _u2(lambda a: u2.gem(_ls(a, "SPY"), _ls(a, "EFA"), _ls(a, "AGG"), *_bill(a))),
    "sector_rotation": _u2(lambda a: u2.sector_rotation({s: _ls(a, s) for s in u2.SECTORS}, _ls(a, "SPY"), *_bill(a))),
    "svxy_regime": _u2(lambda a: u2.svxy_regime(_ls(a, "SVXY"), index_closes(a.load("cboe-VIX-history")), index_closes(a.load("cboe-VIX3M-history")))),
    "low_vol_tilt": _u2(_u2_low_vol_tilt),
    "santa_v2": _u2(lambda a: u2.santa_v2(_ls(a, "^GSPC"))),
    "sell_in_may_v2": _u2(lambda a: u2.sell_in_may_v2(_ls(a, "^GSPC"))),
    "btc_monday_v2": _u2(lambda a: u2.btc_monday_v2(*_ls(a, "BTC-USD"))),
    "gold_autumn_v2": _u2(_u2_gold_autumn_v2),
    "opex_week_v2": _u2(lambda a: u2.opex_week_v2(*_ls(a, "SPY"))),
    "tom_replication_v2": _u2(lambda a: _u2_tom(a, "tom_replication_v2")),
    "low_vol_v2": _u2(_u2_low_vol_v2),
    "btc_reversal_v2": _u2(lambda a: u2.btc_reversal_v2(*_ls(a, "BTC-USD"))),
    "sector_rotation_v2": _u2(lambda a: u2.sector_rotation_v2({s: _ls(a, s) for s in u2.SECTORS}, _ls(a, "SPY"), *_bill(a))),
    "gem_v2": _u2(lambda a: u2.gem_v2(_ls(a, "SPY"), _ls(a, "EFA"), _ls(a, "AGG"), *_bill(a))),
    "golden_cross_v2": _u2(lambda a: _u2_golden_cross(a, v2=True)),
    "crypto_weekly_v2": _u2(lambda a: u2.crypto_weekly_v2(_ls(a, "BTC-USD"), _ls(a, "ETH-USD"))),
    "metals_v2": _u2(lambda a: u2.metals_v2(_ls(a, "GLD"), _ls(a, "SLV"), _ls(a, "GC=F"), _ls(a, "SI=F"), *_bill(a))),
    "svxy_v2": _u2(_u2_svxy_v2),
}


def _dh(*syms: str) -> list[str]:
    """Bundle names of daily-history symbols, sanitised exactly as u2.load_series names them (^GSPC -> daily-history--GSPC)."""
    return ["daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in s) for s in syms]


# Every bundle each U2 harness actually loads (asserted against a load trace in tests/test_mandel_audit_rw.py).
U2_BUNDLES = {"tom_replication": _dh(*TOM_ASSETS), "quarter_end_reversal": _dh("IWM"), "santa_rally": _dh("^GSPC", "SPY"),
              "january_small_cap": _dh("IWM", "SPY", "^RUT", "^GSPC"), "sell_in_may": _dh("^GSPC", "SPY"), "opex_week": _dh("SPY"), "btc_monday": _dh("BTC-USD"),
              "gold_autumn": _dh("GLD", "GC=F"), "golden_cross_crypto": _dh("BTC-USD", "ETH-USD"), "metals_tsmom": _dh("GLD", "SLV", "GC=F", "SI=F") + ["fred-DTB3"],
              "crypto_weekly_tsmom": _dh("BTC-USD", "ETH-USD"), "btc_reversal": _dh("BTC-USD"), "gem_dual_momentum": _dh("SPY", "EFA", "AGG") + ["fred-DTB3"],
              "sector_rotation": _dh(*u2.SECTORS, "SPY") + ["fred-DTB3"], "svxy_regime": _dh("SVXY") + ["cboe-VIX-history", "cboe-VIX3M-history"],
              "low_vol_tilt": _dh("USMV", "SPY", "SPLV", "SPHB") + ["fred-DTB3"],
              "santa_v2": _dh("^GSPC"), "sell_in_may_v2": _dh("^GSPC"), "btc_monday_v2": _dh("BTC-USD"), "gold_autumn_v2": _dh("GLD"),
              "opex_week_v2": _dh("SPY"), "tom_replication_v2": _dh(*TOM_ASSETS), "low_vol_v2": _dh("USMV", "SPY") + ["fred-DTB3"], "btc_reversal_v2": _dh("BTC-USD"),
              "sector_rotation_v2": _dh(*u2.SECTORS, "SPY") + ["fred-DTB3"], "gem_v2": _dh("SPY", "EFA", "AGG") + ["fred-DTB3"], "golden_cross_v2": _dh("BTC-USD", "ETH-USD"),
              "crypto_weekly_v2": _dh("BTC-USD", "ETH-USD"), "metals_v2": _dh("GLD", "SLV", "GC=F", "SI=F") + ["fred-DTB3"],
              "svxy_v2": _dh("SVXY") + ["cboe-VIX-history", "cboe-VIX3M-history", "fred-DTB3"]}


def _om(fn, nkey):
    def h(archive):
        rep = fn(archive); return rep, int(rep.get(nkey) or 0), rep["verdict"], rep["reason"]
    return h


OM2_HARNESSES = {
    "box_mid_v2": _om(lambda a: om.box_mid_v2(_chain_captures(a, "SPX"), a.load("fred-DTB3")), "n_days"),
    "box_borrow_v2": _om(lambda a: om.box_borrow_v2(_chain_captures(a, "SPX"), a.load("fred-DTB3")), "n_days"),
    "parity_v2": _om(lambda a: om.parity_v2(_chain_captures(a, "SPX"), a.load("fred-DTB3")), "n_days"),
    "btc_weekend_ratio_v2": _om(lambda a: om.btc_weekend_ratio_v2(a.load("daily-history-BTC-USD")), "n"),
    "conditional_forward_v2": _om(lambda a: om.conditional_forward_v2(a.load("cboe-VIX-history"), a.load("cboe-VIX3M-history"), a.load("daily-history-SPY")), "n"),
    "vix9d_v2": _om(lambda a: om.vix9d_v2(a.load("cboe-VIX9D-history"), a.load("daily-history-SPY")), "n_signals"),
    "contango_forward_v2": _om(lambda a: om.contango_forward_v2(a.load("cboe-VIX-history"), a.load("cboe-VIX3M-history"), a.load("cboe-VVIX-history")), "n"),
    "spike_forward_v2": _om(lambda a: om.spike_forward_v2(a.load("cboe-VIX-history"), a.load("cboe-VIX3M-history"), a.load("cboe-VVIX-history")), "n_events"),
    "vvix_v2": _om(lambda a: om.vvix_v2(a.load("cboe-VVIX-history"), a.load("cboe-VIX-history")), "n_months"),
}
OM2_BUNDLES = {"box_mid_v2": ["options-chain-SPX-*", "fred-DTB3"], "box_borrow_v2": ["options-chain-SPX-*", "fred-DTB3"], "parity_v2": ["options-chain-SPX-*", "fred-DTB3"],
               "btc_weekend_ratio_v2": ["daily-history-BTC-USD"], "conditional_forward_v2": ["cboe-VIX3M-history", "daily-history-SPY"], "vix9d_v2": ["cboe-VIX9D-history"],
               "contango_forward_v2": ["cboe-VVIX-history", "cboe-VIX3M-history"], "spike_forward_v2": ["cboe-VVIX-history", "cboe-VIX3M-history"], "vvix_v2": ["cboe-VVIX-history"]}


_SC = {}


def _structure_ctx(archive):
    """One shared context per run (closes, VIX, bills, captured smile)."""
    from mandel.experiments.structure_claims import Ctx
    key = id(archive)
    if key not in _SC:
        days, closes = u2.load_series(archive, "SPY", adjusted=False)
        _SC.clear(); _SC[key] = Ctx(days, closes, index_closes(archive.load("cboe-VIX-history")), index_closes(archive.load("fred-DTB3")), list(_load_many(archive, "spy-smile-*")))
    return _SC[key]


# The model-priced structure claims evaluated by structure_claims.evaluate, one harness each (structure_t_100 ... structure_t_517).
STRUCTURE_IDS = ["T-100", "T-102", "T-104", "T-105", "T-106", "T-107", "T-109", "T-110", "T-114", "T-115", "T-116", "T-124", "T-125", "T-126", "T-127", "T-129", "T-130", "T-131", "T-132", "T-134", "T-517"]
STRUCTURE_THEORY = {f"structure_{c.replace('-', '_').lower()}": c for c in STRUCTURE_IDS}


def _structure_harness(cid):
    def h(archive):
        from mandel.experiments.structure_claims import evaluate
        rep = evaluate(cid, _structure_ctx(archive)); return rep, rep["n_cycles"], rep["verdict"], rep["reason"]
    return h


def _xa():
    from mandel.experiments import cross_asset as xa
    return xa


def _ix(a, name):
    return index_closes(a.load(name))


def _px(a, sym):
    return u2.load_series(a, sym, adjusted=False)


def _xh(fn, nkey="n"):
    def h(archive):
        rep = fn(archive); return rep, int(rep.get(nkey) or rep.get("n_cycles") or rep.get("n_entries") or rep.get("n_signals") or 0), rep["verdict"], rep["reason"]
    return h


XA_HARNESSES = {
    "dvol_gap_5pts": _xh(lambda a: _xa().gap_test(*_px(a, "BTC-USD"), _ix(a, "deribit-dvol-BTC-history"), 30, 365, 5.0, "vol", 30, label="BTC DVOL")),
    "gvz_gap_2pts": _xh(lambda a: _xa().gap_test(*_px(a, "GLD"), _ix(a, "cboe-GVZ-history"), 21, 252, 2.0, "vol", 21, label="GVZ/GLD")),
    "gvz_var_premium_thirds": _xh(lambda a: _xa().gap_test(*_px(a, "GLD"), _ix(a, "cboe-GVZ-history"), 21, 252, 0.0, "var", 21, thirds=True, label="GVZ^2 vs GLD")),
    "dvol_var_premium": _xh(lambda a: _xa().gap_test(*_px(a, "BTC-USD"), _ix(a, "deribit-dvol-BTC-history"), 30, 365, 0.0, "var", 30, label="DVOL^2 vs BTC")),
    "gvz_var_premium_halves": _xh(lambda a: _xa().gap_test(*_px(a, "GLD"), _ix(a, "cboe-GVZ-history"), 21, 252, 0.0, "var", 21, start="2009-10-01", label="GVZ^2 vs GLD")),
    "ovx_var_premium": _xh(lambda a: _xa().gap_test(*_px(a, "USO"), _ix(a, "cboe-OVX-history"), 21, 252, 0.0, "var", 21, start="2009-10-01", label="OVX^2 vs USO")),
    "multi_asset_short_var": _xh(lambda a: _xa().multi_asset_short_variance({"SPX": (*_px(a, "SPY"), _ix(a, "cboe-VIX-history")), "GLD": (*_px(a, "GLD"), _ix(a, "cboe-GVZ-history")),
                                                                            "USO": (*_px(a, "USO"), _ix(a, "cboe-OVX-history")), "TLT": (*_px(a, "TLT"), _ix(a, "cboe-VXTLT-history"))}), "n_cycles"),
    "gvz_vix_extremes": _xh(lambda a: _xa().ratio_extremes(*_px(a, "GLD"), *_px(a, "SPY"), _ix(a, "cboe-GVZ-history"), _ix(a, "cboe-VIX-history"))),
    "eth_btc_dvol_ratio": _xh(lambda a: _xa().ratio_extremes(*_px(a, "ETH-USD"), *_px(a, "BTC-USD"), _ix(a, "deribit-dvol-ETH-history"), _ix(a, "deribit-dvol-BTC-history"),
                                                             n=30, ppy=365, window=365, lo_q=0.20, hi_q=None, block=2, win_req=None, label="ETH/BTC DVOL")),
    "gold_silver_ratio_extreme": _xh(lambda a: _xa().ratio_mean_reversion_signal(*_px(a, "GLD"), *_px(a, "SLV")), "n_signals"),
    "gvz_vix_zscore_slope": _xh(lambda a: _xa().zscore_slope(None, _ix(a, "cboe-GVZ-history"), _ix(a, "cboe-VIX-history"))),
    "btc_covered_call": _xh(lambda a: _xa().covered_call_vs_hold(*_px(a, "BTC-USD"), _ix(a, "deribit-dvol-BTC-history"), _ix(a, "fred-DTB3"), 0.25, 30, 30, 12, "2021-04-01", "DVOL"), "n_cycles"),
    "btc_short_put": _xh(lambda a: _xa().short_put_mean(*_px(a, "BTC-USD"), _ix(a, "deribit-dvol-BTC-history"), _ix(a, "fred-DTB3"), -0.25, 30, 30, "2021-04-01", "DVOL"), "n_cycles"),
    "btc_low_dvol_straddle": _xh(lambda a: _xa().conditional_straddle(*_px(a, "BTC-USD"), _ix(a, "deribit-dvol-BTC-history"), _ix(a, "fred-DTB3"), 60, 60, "2022-01-01", 365, 0.20, "DVOL"), "n_entries"),
    "btc_protective_put": _xh(lambda a: _xa().protective_put_calmar(*_px(a, "BTC-USD"), _ix(a, "deribit-dvol-BTC-history"), _ix(a, "fred-DTB3"), "2021-04-01"), "n_cycles"),
    "btc_inverse_covered_call": _xh(lambda a: _xa().inverse_covered_call_btc(*_px(a, "BTC-USD"), _ix(a, "deribit-dvol-BTC-history"), _ix(a, "fred-DTB3"), "2021-04-01",
                                                                             delivery=_xa().delivery_prices(a.load("deribit-delivery-prices-btc"))), "n_cycles"),
    "gld_covered_call": _xh(lambda a: _xa().covered_call_vs_hold(*_px(a, "GLD"), _ix(a, "cboe-GVZ-history"), _ix(a, "fred-DTB3"), 0.30, 30, 21, 12, "2009-10-01", "GVZ", (0.20, 0.30, 0.40)), "n_cycles"),
    "gld_put_write": _xh(lambda a: _xa().short_put_mean(*_px(a, "GLD"), _ix(a, "cboe-GVZ-history"), _ix(a, "fred-DTB3"), -0.25, 30, 21, "2009-10-01", "GVZ"), "n_cycles"),
    "gld_low_gvz_straddle": _xh(lambda a: _xa().conditional_straddle(*_px(a, "GLD"), _ix(a, "cboe-GVZ-history"), _ix(a, "fred-DTB3"), 90, 63, "2010-01-01", 252, 0.20, "GVZ"), "n_entries"),
}
XA_MAP = {"T-175": "dvol_gap_5pts", "T-177": "gvz_gap_2pts", "T-244": "gvz_var_premium_thirds", "T-246": "dvol_var_premium", "T-271": "gvz_var_premium_halves", "T-512": "ovx_var_premium",
          "T-245": "multi_asset_short_var", "T-247": "gvz_vix_extremes", "T-266": "eth_btc_dvol_ratio", "T-274": "gold_silver_ratio_extreme", "T-514": "gvz_vix_zscore_slope",
          "T-253": "btc_covered_call", "T-254": "btc_short_put", "T-256": "btc_low_dvol_straddle", "T-267": "btc_protective_put", "T-176": "btc_inverse_covered_call",
          "T-270": "gld_covered_call", "T-279": "gld_put_write", "T-272": "gld_low_gvz_straddle"}
_BTC_OPT = _dh("BTC-USD") + ["deribit-dvol-BTC-history", "fred-DTB3"]
_GLD_OPT = _dh("GLD") + ["cboe-GVZ-history", "fred-DTB3"]
# Every bundle each XA harness actually loads (asserted against a load trace in tests/test_mandel_audit_rw.py).
XA_BUNDLES = {
    "dvol_gap_5pts": _dh("BTC-USD") + ["deribit-dvol-BTC-history"], "gvz_gap_2pts": _dh("GLD") + ["cboe-GVZ-history"],
    "gvz_var_premium_thirds": _dh("GLD") + ["cboe-GVZ-history"], "dvol_var_premium": _dh("BTC-USD") + ["deribit-dvol-BTC-history"],
    "gvz_var_premium_halves": _dh("GLD") + ["cboe-GVZ-history"], "ovx_var_premium": _dh("USO") + ["cboe-OVX-history"],
    "multi_asset_short_var": _dh("SPY", "GLD", "USO", "TLT") + ["cboe-VIX-history", "cboe-GVZ-history", "cboe-OVX-history", "cboe-VXTLT-history"],
    "gvz_vix_extremes": _dh("GLD", "SPY") + ["cboe-GVZ-history", "cboe-VIX-history"],
    "eth_btc_dvol_ratio": _dh("ETH-USD", "BTC-USD") + ["deribit-dvol-ETH-history", "deribit-dvol-BTC-history"],
    "gold_silver_ratio_extreme": _dh("GLD", "SLV"), "gvz_vix_zscore_slope": ["cboe-GVZ-history", "cboe-VIX-history"],
    "btc_covered_call": _BTC_OPT, "btc_short_put": _BTC_OPT, "btc_low_dvol_straddle": _BTC_OPT, "btc_protective_put": _BTC_OPT, "btc_inverse_covered_call": _BTC_OPT + ["deribit-delivery-prices-btc"],
    "gld_covered_call": _GLD_OPT, "gld_put_write": _GLD_OPT, "gld_low_gvz_straddle": _GLD_OPT,
}
# The registered null of the theory each XA harness tests (XA_MAP), recorded with every result.
XA_NULLS = {
    "dvol_gap_5pts": "mean(DVOL - forward 30-day realised BTC vol) <= 5 vol points (block-bootstrap CI)",
    "gvz_gap_2pts": "mean(GVZ - forward 21-day realised GLD vol) < 2 vol points (block-bootstrap CI)",
    "gvz_var_premium_thirds": "mean(GVZ^2 - forward realised GLD variance) <= 0 (block-bootstrap CI)",
    "dvol_var_premium": "mean(DVOL^2 - forward realised BTC variance) <= 0 (block-bootstrap CI)",
    "gvz_var_premium_halves": "mean GVZ^2 - realised GLD variance <= 0 (block-bootstrap CI)",
    "ovx_var_premium": "mean OVX^2 - realised USO variance <= 0 (block-bootstrap CI)",
    "multi_asset_short_var": "Sharpe(equal-vega SPX/GLD/USO/TLT short variance) - Sharpe(SPX alone) <= 0 (block bootstrap)",
    "gvz_vix_extremes": "mean of s*[ln(RV_GLD/RV_SPY) - ln(GVZ/VIX)] after band exits <= 0 (block-bootstrap CI)",
    "eth_btc_dvol_ratio": "mean of [RV_ETH/RV_BTC - DVOL_ETH/DVOL_BTC] after signals below the trailing 365-day 20th percentile <= 0 (block-bootstrap CI)",
    "gold_silver_ratio_extreme": "mean 180-day forward log change of GLD/SLV after a 5-year 90th-percentile exceedance >= 0 (bootstrap)",
    "gvz_vix_zscore_slope": "OLS slope of the 20-day forward change in log(GVZ/VIX) on its z-score >= 0 (bootstrap, per half)",
    "btc_covered_call": "Sharpe(covered call) - Sharpe(hold) <= 0; model-priced at flat DVOL", "btc_short_put": "mean short-put P&L <= 0; model-priced at flat DVOL",
    "btc_low_dvol_straddle": "mean straddle return (low DVOL) - mean (all days) <= 0; model-priced", "btc_protective_put": "Calmar(hedged) - Calmar(hold) <= 0; model-priced",
    "btc_inverse_covered_call": "mean BTC-denominated covered-call P&L <= 0; model-priced", "gld_covered_call": "Sharpe(covered call) - Sharpe(hold) <= 0; model-priced at flat GVZ",
    "gld_put_write": "mean short-put P&L <= 0; model-priced at flat GVZ", "gld_low_gvz_straddle": "mean straddle return (low GVZ) - mean (all days) <= 0; model-priced",
}


# Batch modules, one per data unlock: FOMC calendar, Fama-French/AQR factors, Deribit carry, OHLC, VX futures (batch 4); macro release
# dates, FX spot and 3-month rates, hourly bars (batch 5); options-library claims on archived data (batch 6a) and on the stored Cboe strategy indices, DoltHub chains/vol history and
# Deribit trades (batch 6b); underlying-library claims on archived data (batch 6c). Each exports HARNESSES
# {name: fn(archive) -> (stat, n, verdict, reason)} and THEORY_MAP {theory id: harness}; each harness checks its own inputs.
# BATCH_BUNDLES lists the bundles each one loads, traced on the archive (dated daily captures as name-* patterns).
BATCH_MODULES = (batch4_fomc, batch4_fact, batch4_carry, batch4_ohlc, batch4_vx, batch5_macro, batch5_fx,
                 batch5_hourly, batch6_var, batch6_dir, batch6_term, batch6_surf, batch6_xc, batch6b_bw,
                 batch6b_hedge, batch6b_chain, batch6b_misc, batch6b_dolt, batch6b_volh, batch6b_drb, batch6c_cal,
                 batch6c_mom, batch6c_misc, batch6c_xs, batch6c_pairs, batch6c_rates, batch6c_macro, batch6c_pub,
                 batch6c_events)
BATCH_HARNESSES = {h: fn for m in BATCH_MODULES for h, fn in m.HARNESSES.items()}
BATCH_THEORY = {h: tid for m in BATCH_MODULES for tid, h in m.THEORY_MAP.items()}
BATCH_BUNDLES = {
    "fomc_btc_event_straddle": ["cboe-VIX-history", "daily-history-BTC-USD", "deribit-dvol-BTC-history", "fomc-meetings", "macro-release-cpi"],
    "fomc_cycle_even_weeks": ["daily-history-EFA", "daily-history-SPY", "fomc-meetings"],
    "fomc_gvz_event_change": ["cboe-GVZ-history", "cboe-VIX-history", "fomc-meetings", "macro-release-cpi"],
    "fomc_monetary_momentum": ["daily-history-SPY", "fomc-meetings", "fred-DGS2", "fred-DTB3"],
    "fomc_pre_drift_oos": ["cboe-VIX-history", "daily-history-SPY", "fomc-meetings"],
    "fomc_spx_event_straddle": ["cboe-VIX-history", "daily-history-SPY", "fomc-meetings"],
    "fomc_statement_day_drift": ["daily-history-BTC-USD", "daily-history-GLD", "daily-history-IWM", "daily-history-QQQ", "daily-history-SPY", "daily-history-TLT", "fomc-meetings", "macro-release-cpi"],
    "fact_accruals": ["french-accruals-monthly", "french-ff5-daily", "french-momentum-daily"],
    "fact_bab_etf": ["aqr-bab-daily", "daily-history-COWZ", "daily-history-IJR", "daily-history-IWD", "daily-history-IWF", "daily-history-IWM", "daily-history-QUAL", "daily-history-SPHB", "daily-history-SPLV", "daily-history-SPY", "daily-history-USMV", "fred-DTB3", "french-ff3-daily", "french-ff5-daily", "french-momentum-daily"],
    "fact_contrarian_timing": ["french-ff5-daily", "french-momentum-daily"],
    "fact_factor_momentum": ["aqr-bab-daily", "french-ff5-daily", "french-momentum-daily"],
    "fact_investment_cma": ["aqr-bab-daily", "daily-history-COWZ", "daily-history-IJR", "daily-history-IWD", "daily-history-IWF", "daily-history-IWM", "daily-history-QUAL", "daily-history-SPHB", "daily-history-SPLV", "daily-history-SPY", "daily-history-USMV", "fred-DTB3", "french-ff3-daily", "french-ff5-daily", "french-momentum-daily"],
    "fact_momentum_umd": ["aqr-bab-daily", "daily-history-COWZ", "daily-history-IJR", "daily-history-IWD", "daily-history-IWF", "daily-history-IWM", "daily-history-QUAL", "daily-history-SPHB", "daily-history-SPLV", "daily-history-SPY", "daily-history-USMV", "fred-DTB3", "french-ff3-daily", "french-ff5-daily", "french-momentum-daily"],
    "fact_net_issuance": ["daily-history-PKW", "daily-history-SPY", "french-ff5-daily", "french-momentum-daily", "french-net-issuance-monthly"],
    "fact_profitability_rmw": ["aqr-bab-daily", "daily-history-COWZ", "daily-history-IJR", "daily-history-IWD", "daily-history-IWF", "daily-history-IWM", "daily-history-QUAL", "daily-history-SPHB", "daily-history-SPLV", "daily-history-SPY", "daily-history-USMV", "daily-history-XLE", "daily-history-XLK", "fred-DTB3", "french-ff3-daily", "french-ff5-daily", "french-momentum-daily"],
    "fact_quality_qual": ["aqr-bab-daily", "daily-history-COWZ", "daily-history-IJR", "daily-history-IWD", "daily-history-IWF", "daily-history-IWM", "daily-history-QUAL", "daily-history-SPHB", "daily-history-SPLV", "daily-history-SPY", "daily-history-USMV", "fred-DTB3", "french-ff3-daily", "french-ff5-daily", "french-momentum-daily"],
    "fact_sin_alpha": ["french-ff5-daily", "french-industry49-daily", "french-momentum-daily"],
    "fact_size_ijr_iwm": ["aqr-bab-daily", "daily-history-COWZ", "daily-history-IJR", "daily-history-IWD", "daily-history-IWF", "daily-history-IWM", "daily-history-QUAL", "daily-history-SPHB", "daily-history-SPLV", "daily-history-SPY", "daily-history-USMV", "fred-DTB3", "french-ff3-daily", "french-ff5-daily", "french-momentum-daily"],
    "fact_value_hml": ["aqr-bab-daily", "daily-history-COWZ", "daily-history-IJR", "daily-history-IWD", "daily-history-IWF", "daily-history-IWM", "daily-history-QUAL", "daily-history-SPHB", "daily-history-SPLV", "daily-history-SPY", "daily-history-USMV", "fred-DTB3", "french-ff3-daily", "french-ff5-daily", "french-momentum-daily"],
    "carry_basis_crash_predictor": ["daily-history-BTC-F", "daily-history-BTC-USD", "deribit-funding-BTC-PERPETUAL", "fred-DTB3"],
    "carry_cme_basis_spike": ["daily-history-BTC-F", "deribit-funding-BTC-PERPETUAL", "fred-DTB3"],
    "carry_cme_cash_and_carry": ["daily-history-BTC-F", "deribit-funding-BTC-PERPETUAL", "fred-DTB3"],
    "carry_funding_call_hedged": ["deribit-delivery-prices-btc", "deribit-dvol-BTC-history", "deribit-funding-BTC-PERPETUAL", "fred-DTB3"],
    "carry_funding_sentiment": ["deribit-funding-BTC-PERPETUAL"],
    "carry_perp_funding_threshold": ["deribit-funding-BTC-PERPETUAL", "fred-DTB3"],
    "carry_perp_funding_vs_quarterly": ["deribit-funding-BTC-PERPETUAL", "deribit-quarterly-futures-btc"],
    "carry_trend_funding_filter": ["daily-history-BTC-USD", "deribit-funding-BTC-PERPETUAL"],
    "ohlc_cs_spread_shock": ["cboe-VIX-history", "daily-history-SPY"],
    "ohlc_donchian_atr_breakout": ["cboe-VIX-history", "daily-history-BTC-USD", "daily-history-ETH-USD", "daily-history-GLD", "daily-history-QQQ", "daily-history-SLV", "daily-history-SPY", "daily-history-XLE", "daily-history-XLK"],
    "ohlc_gap_fade": ["daily-history-IBIT", "daily-history-QQQ", "daily-history-SPY"],
    "ohlc_ibs_reversal": ["daily-history-QQQ", "daily-history-SPY"],
    "ohlc_opex_pin_straddle": ["cboe-VIX-history", "daily-history-SPY", "fomc-meetings", "macro-release-cpi"],
    "ohlc_overnight_vs_intraday": ["daily-history-SPY"],
    "ohlc_spy_ivv_twin": ["daily-history-IVV", "daily-history-SPY"],
    "vx_calendar_gated": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-vx-futures"],
    "vx_vxx_contango_decay": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VVIX-history", "daily-history-SVXY", "daily-history-VXX", "fred-DTB3"],
    "macro_announcement_day_premium": ["daily-history-SPY", "daily-history-TLT", "fomc-meetings", "macro-release-cpi", "macro-release-employment-situation"],
    "macro_fomc_im_hm_filter": ["cboe-VIX-history", "daily-history-SPY", "fomc-meetings"],
    "macro_gld_event_straddle": ["cboe-GVZ-history", "cboe-VIX-history", "daily-history-GLD", "daily-history-SPY", "fomc-meetings", "macro-release-cpi", "macro-release-employment-situation"],
    "macro_triple_witching_straddle": ["cboe-VIX-history", "daily-history-SPY", "fomc-meetings"],
    "fx_carry_em": ["cboe-VIX-history", "fx-rates-3m", "fx-spot-g10"],
    "fx_carry_g10": ["cboe-VIX-history", "fx-rates-3m", "fx-spot-g10"],
    "fx_momentum_g10": ["fx-rates-3m", "fx-spot-g10"],
    "hourly_closing_reversal": ["daily-history-GLD", "daily-history-IWM", "daily-history-QQQ", "daily-history-SPY", "hourly-GLD", "hourly-IWM", "hourly-QQQ", "hourly-SPY"],
    "hourly_half_hour_momentum": ["daily-history-IWM", "daily-history-QQQ", "daily-history-SPY", "fomc-meetings", "hourly-IWM", "hourly-QQQ", "hourly-SPY", "macro-release-cpi"],
    "b6_var_gamma_scalp_long_straddle": ["cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3"],
    "b6_var_iv_rv_spread_scaled": ["cboe-VIX-history", "daily-history--GSPC"],
    "b6_var_short_straddle_tercile": ["cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3"],
    "b6_var_theta_harvest_45dte": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3", "spy-smile-*"],
    "b6_var_theta_ladder": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3"],
    "b6_var_variance_strip_win_rate": ["cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*", "spy-smile-*"],
    "b6_var_variance_swap_units": ["cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "hourly-SPY"],
    "b6_var_vix1d_premium": ["cboe-VIX-history", "cboe-VIX1D-history", "daily-history--GSPC", "fomc-meetings", "macro-release-cpi", "macro-release-employment-situation"],
    "b6_var_vrp_short_straddle_hedged": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3", "spy-smile-*"],
    "b6_dir_christmas_tree": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3"],
    "b6_dir_deep_itm_call": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3"],
    "b6_dir_digital_put": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3"],
    "b6_dir_jade_lizard": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3"],
    "b6_dir_leaps_replacement": ["cboe-VIX-history", "cboe-VIX3M-history", "daily-history-SPY", "fred-DTB3"],
    "b6_dir_ratio_1x2": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3"],
    "b6_dir_risk_reversal_skew": ["cboe-SKEW-history", "cboe-VIX-history", "daily-history-SPY", "fred-DTB3"],
    "b6_dir_stock_repair": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VXN-history", "daily-history-QQQ", "daily-history-SPY", "fred-DTB3"],
    "b6_dir_zebra": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3"],
    "b6_term_calendarised_fly": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VIX6M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*"],
    "b6_term_double_calendar": ["cboe-SKEW-history", "cboe-VIX-history", "cboe-VIX3M-history", "cboe-VIX6M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*", "spy-smile-*"],
    "b6_term_double_diagonal": ["cboe-SKEW-history", "cboe-VIX-history", "cboe-VIX3M-history", "cboe-VIX6M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*", "spy-smile-*"],
    "b6_term_leaps_collar": ["cboe-SKEW-history", "cboe-VIX-history", "cboe-VIX3M-history", "cboe-VIX6M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*", "options-surface-*", "spy-smile-*"],
    "b6_term_long_calendar": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VIX6M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*", "options-surface-*"],
    "b6_term_long_diagonal": ["cboe-SKEW-history", "cboe-VIX-history", "cboe-VIX3M-history", "cboe-VIX6M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*", "spy-smile-*"],
    "b6_term_pmcc": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VIX6M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*", "options-surface-*"],
    "b6_term_ratio_calendar": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VIX6M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*"],
    "b6_term_roll_tested_put": ["cboe-SKEW-history", "cboe-VIX-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*", "spy-smile-*"],
    "b6_term_short_calendar": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VIX6M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPY-*"],
    "b6_surf_cross_index_vol_spread": ["cboe-RVX-history", "cboe-VIX-history", "cboe-VXN-history", "daily-history-IWM", "daily-history-QQQ", "daily-history-SPY"],
    "b6_surf_forward_variance_premium": ["cboe-VIX-history", "cboe-VIX3M-history", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*"],
    "b6_surf_implied_correlation": ["cboe-COR1M-history", "daily-history-XLB", "daily-history-XLC", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLRE", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY"],
    "b6_surf_skew_cheap_put_spread": ["cboe-SKEW-history", "cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*"],
    "b6_surf_skew_implied_tail_gap": ["cboe-SKEW-history", "cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY"],
    "b6_surf_skew_tail_frequency": ["cboe-SKEW-history", "cboe-VIX-history", "daily-history--GSPC"],
    "b6_surf_vix_call_hedge": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VVIX-history", "daily-history-SPY", "fred-DTB3", "spy-smile-*"],
    "b6_surf_vrp_term_regime": ["cboe-VIX-history", "cboe-VIX3M-history", "daily-history-SPY", "fred-DTB3"],
    "b6_surf_vvix_vs_realised": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VVIX-history", "daily-history--GSPC", "fred-DTB3"],
    "b6_surf_weekend_variance": ["daily-history-SPY"],
    "b6_xc_btc_hedged_straddle": ["cboe-VIX-history", "daily-history-BTC-USD", "daily-history-SPY", "deribit-dvol-BTC-history", "deribit-funding-BTC-PERPETUAL", "deribit-surface-BTC-*", "fred-DTB3"],
    "b6_xc_gld_implied_carry": ["daily-history--GSPC", "daily-history-GLD", "daily-history-SLV", "fred-DTB3", "options-chain-GLD-*", "options-chain-SLV-*", "options-chain-SPX-*"],
    "b6_xc_inverse_strangle_hedge": ["daily-history-BTC-USD", "deribit-dvol-BTC-history"],
    "b6_xc_parity_deviation_scan": ["daily-history--GSPC", "daily-history-GLD", "daily-history-IBIT", "daily-history-SPY", "fred-DGS2", "fred-DTB3", "options-chain-GLD-*", "options-chain-IBIT-*", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6_xc_spy_spx_financing": ["daily-history--GSPC", "daily-history-SPY", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6b_bw_bxm_alpha": ["cboe-BXM-history", "cboe-BXMC-history", "cboe-BXMD-history", "cboe-BXMH-history", "cboe-BXMW-history", "cboe-BXY-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3"],
    "b6b_bw_bxmd_vs_bxm": ["cboe-BXM-history", "cboe-BXMC-history", "cboe-BXMD-history", "cboe-BXY-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3"],
    "b6b_bw_bxmh_vs_bxm": ["cboe-BXM-history", "cboe-BXMC-history", "cboe-BXMH-history", "daily-history-SPY", "fred-DTB3"],
    "b6b_bw_bxmw_vs_bxm": ["cboe-BXM-history", "cboe-BXMW-history", "daily-history-SPY", "fred-DTB3"],
    "b6b_bw_call_spread_overwrite": ["cboe-BXM-history", "cboe-SKEW-history", "cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*"],
    "b6b_bw_cmbo_vs_bxy": ["cboe-BXY-history", "cboe-CMBO-history", "cboe-PUTY-history", "daily-history-SPY", "fred-DTB3"],
    "b6b_bw_covered_put": ["cboe-BXM-history", "cboe-PUT-history", "cboe-SKEW-history", "cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3"],
    "b6b_bw_put_bxm_return_gap": ["cboe-BXM-history", "cboe-BXMD-history", "cboe-PUT-history", "fred-DTB3"],
    "b6b_bw_put_vs_bxm": ["cboe-BXM-history", "cboe-BXY-history", "cboe-PUT-history", "cboe-PUTD-history", "cboe-PUTY-history", "cboe-WPUT-history", "fred-DTB3"],
    "b6b_bw_putwrite_vs_spy": ["cboe-PUT-history", "cboe-VIX-history", "daily-history-SPY", "fred-DTB3"],
    "b6b_bw_wheel_basis": ["cboe-BXM-history", "cboe-PUT-history", "cboe-SKEW-history", "cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*"],
    "b6b_hedge_bfly_vs_cndr_sharpe": ["cboe-BFLY-history", "cboe-CNDR-history", "daily-history--GSPC", "fred-DTB3"],
    "b6b_hedge_bs_replication": ["cboe-BXM-history", "cboe-BXMD-history", "cboe-CNDR-history", "cboe-PUT-history", "cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3"],
    "b6b_hedge_cllz_sharpe": ["cboe-CLL-history", "cboe-CLLZ-history", "cboe-PPUT-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3"],
    "b6b_hedge_cndr_vrp_gap": ["cboe-CNDR-history", "cboe-VIX-history", "daily-history--GSPC", "fred-DFF", "fred-DTB3"],
    "b6b_hedge_collar_cll_vs_blend": ["cboe-CLL-history", "cboe-CLLZ-history", "cboe-PPUT-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3"],
    "b6b_hedge_pput_vs_blend": ["cboe-PPUT-history", "cboe-PPUT3M-history", "cboe-VIX-history", "daily-history--GSPC", "daily-history-SPY", "fred-DTB3"],
    "b6b_hedge_vix_soq_credit_spread": ["cboe-VIX-history", "cboe-VIX3M-history", "cboe-VRO-history", "cboe-VVIX-history", "cboe-vx-futures", "fred-DTB3", "options-chain-VIX-*"],
    "b6b_hedge_vxth_drawdown": ["cboe-PPUT-history", "cboe-PPUT3M-history", "cboe-VXTH-history", "daily-history--GSPC", "daily-history-SPY"],
    "b6b_chain_butterfly_arb": ["daily-history--GSPC", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6b_chain_calendar_arb": ["daily-history--GSPC", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6b_chain_conversion": ["daily-history--GSPC", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6b_chain_itm_put_exercise": ["daily-history--GSPC", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6b_chain_jelly_roll": ["daily-history--GSPC", "daily-history-SPY", "fred-DTB3", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6b_chain_strangle_vs_straddle": ["cboe-SKEW-history", "cboe-VIX-history", "daily-history-SPY", "fred-DTB3", "spy-smile-*"],
    "b6b_chain_synthetic_call": ["daily-history--GSPC", "daily-history-GLD", "daily-history-IBIT", "daily-history-SPY", "fred-DTB3", "options-chain-GLD-*", "options-chain-IBIT-*", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6b_chain_synthetic_long": ["daily-history-GLD", "daily-history-IBIT", "daily-history-SPY", "fred-DTB3", "options-chain-GLD-*", "options-chain-IBIT-*", "options-chain-SPY-*"],
    "b6b_chain_synthetic_short": ["daily-history--GSPC", "daily-history-GLD", "daily-history-IBIT", "daily-history-SPY", "fred-DTB3", "options-chain-GLD-*", "options-chain-IBIT-*", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6b_chain_vertical_bounds": ["daily-history--GSPC", "daily-history-GLD", "daily-history-IBIT", "daily-history-QQQ", "daily-history-SPY", "fred-DTB3", "options-chain-GLD-*", "options-chain-IBIT-*", "options-chain-QQQ-*", "options-chain-SPX-*", "options-chain-SPY-*"],
    "b6b_misc_box_bill_vix_corr": ["box-rates-bdg", "cboe-VIX-history", "fomc-meetings", "fred-DTB3"],
    "b6b_misc_election_spy_move": ["cboe-VIX-history", "daily-history-SPY", "fred-DTB3", "kalshi-settled-markets", "polymarket-closed-markets", "polymarket-price-history-daily"],
    "b6b_misc_opec_uso_straddle": ["cboe-OVX-history", "daily-history-USO", "fred-DTB3", "opec-announcements"],
    "b6b_misc_slv_call_backspread": ["daily-history-GLD", "daily-history-SLV", "fred-DTB3", "options-chain-SLV-*"],
    "b6b_dolt_backspread": ["daily-history-SPY", "dolt-chain-SPY"],
    "b6b_dolt_put_front_ratio": ["cboe-VIX-history", "daily-history-SPY", "dolt-chain-SPY"],
    "b6b_dolt_put_ladder": ["cboe-VIX-history", "daily-history-SPY", "dolt-chain-SPY"],
    "b6b_dolt_ratio_overlay_skew": ["daily-history-SPY", "dolt-chain-SPY"],
    "b6b_volh_sector_corr_premium": ["cboe-COR1M-history", "cboe-VIX-history", "daily-history-SPY", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY", "dolt-chain-SPY", "dolt-volhistory"],
    "b6b_drb_box_rate_capture_days": ["deribit-book-BTC-*", "deribit-funding-BTC-PERPETUAL", "deribit-quarterly-futures-btc", "fred-DTB3"],
    "b6b_drb_calendar_inversion": ["deribit-delivery-prices-btc", "deribit-option-trades-daily-BTC"],
    "b6b_drb_catalyst_strangle": ["deribit-dvol-BTC-history", "deribit-dvol-ETH-history", "deribit-option-trades-catalysts"],
    "b6b_drb_cme_ibit_tax": ["deribit-delivery-prices-btc", "deribit-dvol-BTC-history", "deribit-funding-BTC-PERPETUAL", "deribit-quarterly-futures-btc", "fred-DTB3"],
    "b6b_drb_dvol_futures_basis": ["cboe-vx-futures", "deribit-dvol-futures-trades"],
    "b6b_drb_expiry_friday_straddle": ["deribit-delivery-prices-btc", "deribit-dvol-BTC-history", "deribit-dvol-ETH-history", "deribit-funding-BTC-PERPETUAL", "fomc-meetings", "fred-DTB3", "hourly-BTC-USD", "hourly-ETH-USD", "macro-release-cpi"],
    "b6b_drb_fomc_event_straddle": ["deribit-delivery-prices-btc", "deribit-dvol-BTC-history", "deribit-option-trades-fomc", "fomc-meetings"],
    "b6b_drb_parity_violations": ["deribit-book-BTC-*", "deribit-funding-BTC-PERPETUAL", "deribit-quarterly-futures-btc"],
    "b6b_drb_quarterly_basis": ["daily-history-BTC-USD", "deribit-funding-BTC-PERPETUAL", "deribit-quarterly-futures-btc", "fred-DTB3"],
    "b6b_drb_quarterly_box_rate": ["deribit-book-BTC-*", "deribit-funding-BTC-PERPETUAL", "fred-DTB3"],
    "b6b_drb_rr_skew_harvest": ["deribit-delivery-prices-btc", "deribit-option-trades-daily-BTC"],
    "b6c_cal_month_end_rebalancing": ["daily-history-BTC-USD", "daily-history-GLD", "daily-history-SPY", "daily-history-TLT"],
    "b6c_cal_pension_rebalancing": ["daily-history-AGG", "daily-history-SPY", "daily-history-TLT", "fred-DGS10", "fred-DTB3", "french-ff3-daily"],
    "b6c_cal_pre_holiday": ["daily-history--RUT", "daily-history-BTC-USD", "daily-history-IWM", "daily-history-SPY"],
    "b6c_cal_presidential_year3": ["daily-history--GSPC"],
    "b6c_cal_weekday_speculative_spread": ["cboe-VIX-history", "daily-history-GLD", "daily-history-IWN", "daily-history-SLV", "daily-history-SPHB", "daily-history-SPLV", "daily-history-USMV"],
    "b6c_mom_crash_filter_vs_random": ["daily-history-SPY", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY", "fred-DTB3"],
    "b6c_mom_cross_asset_tsmom": ["daily-history-IEF", "daily-history-SPY", "daily-history-TLT", "fred-DGS10", "fred-DTB3"],
    "b6c_mom_residual_vs_total_momentum": ["daily-history-SPY", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY", "fred-DTB3"],
    "b6c_mom_sma10_drawdown_vs_random": ["daily-history-DBC", "daily-history-EFA", "daily-history-IEF", "daily-history-SPY", "daily-history-VNQ", "fred-DTB3"],
    "b6c_mom_trend_crisis_smile": ["daily-history-BTC-USD", "daily-history-DBC", "daily-history-EFA", "daily-history-GLD", "daily-history-IEF", "daily-history-QQQ", "daily-history-SLV", "daily-history-SPY", "daily-history-TLT", "fred-DTB3"],
    "b6c_mom_tsmom_vs_hist_mean": ["cboe-VIX-history", "daily-history-AGG", "daily-history-BTC-USD", "daily-history-DBC", "daily-history-EFA", "daily-history-ETH-USD", "daily-history-GLD", "daily-history-QQQ", "daily-history-SLV", "daily-history-SPY", "daily-history-TLT", "fred-DTB3"],
    "b6c_mom_vol_scaled_trend_did": ["daily-history-BTC-USD", "daily-history-EFA", "daily-history-ETH-USD", "daily-history-GLD", "daily-history-QQQ", "daily-history-SLV", "daily-history-SPY", "daily-history-TLT", "deribit-dvol-BTC-history", "fred-DTB3"],
    "b6c_misc_bond_tsmom_fred": ["daily-history-IEF", "fred-DGS10", "fred-DGS2", "fred-DTB3"],
    "b6c_misc_es_basis": ["daily-history--GSPC", "daily-history-ES-F", "daily-history-SPY", "fred-DTB3"],
    "b6c_misc_fear_greed_extremes": ["crypto-fear-greed-history", "daily-history-BTC-USD", "daily-history-ETH-USD", "fred-DTB3"],
    "b6c_misc_gold_silver_ratio": ["daily-history-GC-F", "daily-history-GLD", "daily-history-SI-F", "daily-history-SLV"],
    "b6c_misc_metals_basis": ["daily-history-GC-F", "daily-history-GLD", "daily-history-SI-F", "daily-history-SLV", "fred-DTB3"],
    "b6c_misc_ta_reality_check": ["daily-history-BTC-USD", "daily-history-GLD", "daily-history-QQQ", "daily-history-SPY", "fred-DTB3"],
    "b6c_xs_commodity_etf_momentum": ["daily-history-CORN", "daily-history-CPER", "daily-history-DBA", "daily-history-DBB", "daily-history-DBC", "daily-history-DBE", "daily-history-GLD", "daily-history-PALL", "daily-history-PPLT", "daily-history-SLV", "daily-history-SOYB", "daily-history-UNG", "daily-history-USO", "daily-history-WEAT", "fred-DTB3"],
    "b6c_xs_country_long_reversal": ["daily-history-EWA", "daily-history-EWC", "daily-history-EWD", "daily-history-EWG", "daily-history-EWH", "daily-history-EWI", "daily-history-EWJ", "daily-history-EWK", "daily-history-EWL", "daily-history-EWM", "daily-history-EWN", "daily-history-EWO", "daily-history-EWP", "daily-history-EWQ", "daily-history-EWS", "daily-history-EWT", "daily-history-EWU", "daily-history-EWW", "daily-history-EWY", "daily-history-EWZ", "daily-history-EZA"],
    "b6c_xs_fifty_two_week_high": ["daily-history-DBC", "daily-history-EEM", "daily-history-EFA", "daily-history-GLD", "daily-history-IEF", "daily-history-IWM", "daily-history-QQQ", "daily-history-SPY", "daily-history-TLT", "daily-history-VNQ", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY", "fred-DTB3"],
    "b6c_xs_frog_in_the_pan": ["daily-history-BTC-USD", "daily-history-DBC", "daily-history-EEM", "daily-history-EFA", "daily-history-ETH-USD", "daily-history-GLD", "daily-history-IEF", "daily-history-IWM", "daily-history-QQQ", "daily-history-SPY", "daily-history-TLT", "daily-history-VNQ", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY"],
    "b6c_xs_return_seasonality": ["daily-history-DBA", "daily-history-GLD", "daily-history-SLV", "daily-history-TLT", "daily-history-USO", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY", "fred-DTB3"],
    "b6c_xs_reversal_vix_liquidity": ["cboe-VIX-history", "daily-history-AGG", "daily-history-DBC", "daily-history-DIA", "daily-history-EEM", "daily-history-EFA", "daily-history-EWA", "daily-history-EWC", "daily-history-EWD", "daily-history-EWG", "daily-history-EWH", "daily-history-EWI", "daily-history-EWJ", "daily-history-EWK", "daily-history-EWL", "daily-history-EWM", "daily-history-EWN", "daily-history-EWO", "daily-history-EWP", "daily-history-EWQ", "daily-history-EWS", "daily-history-EWT", "daily-history-EWU", "daily-history-EWW", "daily-history-EWY", "daily-history-EWZ", "daily-history-EZA", "daily-history-GDX", "daily-history-GLD", "daily-history-IDU", "daily-history-IEF", "daily-history-IJH", "daily-history-IJR", "daily-history-IVV", "daily-history-IWD", "daily-history-IWF", "daily-history-IWM", "daily-history-IYC", "daily-history-IYE", "daily-history-IYF", "daily-history-IYH", "daily-history-IYJ", "daily-history-IYK", "daily-history-IYM", "daily-history-IYR", "daily-history-IYT", "daily-history-IYW", "daily-history-IYZ", "daily-history-LQD", "daily-history-MDY", "daily-history-PKW", "daily-history-PPLT", "daily-history-QQQ", "daily-history-SHY", "daily-history-SLV", "daily-history-SPY", "daily-history-TIP", "daily-history-TLT", "daily-history-USO", "daily-history-VNQ", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY"],
    "b6c_xs_weekly_etf_reversal": ["cboe-VIX-history", "daily-history-EWA", "daily-history-EWC", "daily-history-EWD", "daily-history-EWG", "daily-history-EWH", "daily-history-EWI", "daily-history-EWJ", "daily-history-EWK", "daily-history-EWL", "daily-history-EWM", "daily-history-EWN", "daily-history-EWO", "daily-history-EWP", "daily-history-EWQ", "daily-history-EWS", "daily-history-EWT", "daily-history-EWU", "daily-history-EWW", "daily-history-EWY", "daily-history-EWZ", "daily-history-EZA", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY"],
    "b6c_pairs_brent_wti": ["daily-history-BNO", "daily-history-BZ-F", "daily-history-CL-F", "daily-history-UGA", "daily-history-USO"],
    "b6c_pairs_cointegration": ["daily-events-DIA", "daily-events-EEM", "daily-events-EWA", "daily-events-EWC", "daily-events-EWD", "daily-events-EWG", "daily-events-EWH", "daily-events-EWI", "daily-events-EWJ", "daily-events-EWK", "daily-events-EWL", "daily-events-EWM", "daily-events-EWN", "daily-events-EWO", "daily-events-EWP", "daily-events-EWQ", "daily-events-EWS", "daily-events-EWT", "daily-events-EWU", "daily-events-EWW", "daily-events-EWY", "daily-events-EWZ", "daily-events-EZA", "daily-events-GDX", "daily-events-GLD", "daily-events-HYG", "daily-events-IYR", "daily-events-KRE", "daily-events-LQD", "daily-events-MDY", "daily-events-SHY", "daily-events-VWO", "daily-events-XHB", "daily-events-XOP", "daily-history-BTC-USD", "daily-history-DIA", "daily-history-EEM", "daily-history-EFA", "daily-history-ETH-USD", "daily-history-EWA", "daily-history-EWC", "daily-history-EWD", "daily-history-EWG", "daily-history-EWH", "daily-history-EWI", "daily-history-EWJ", "daily-history-EWK", "daily-history-EWL", "daily-history-EWM", "daily-history-EWN", "daily-history-EWO", "daily-history-EWP", "daily-history-EWQ", "daily-history-EWS", "daily-history-EWT", "daily-history-EWU", "daily-history-EWW", "daily-history-EWY", "daily-history-EWZ", "daily-history-EZA", "daily-history-GDX", "daily-history-GLD", "daily-history-HYG", "daily-history-IEF", "daily-history-IWM", "daily-history-IYR", "daily-history-KRE", "daily-history-LQD", "daily-history-MDY", "daily-history-QQQ", "daily-history-SHY", "daily-history-SLV", "daily-history-SPY", "daily-history-TLT", "daily-history-VNQ", "daily-history-VWO", "daily-history-XHB", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY", "daily-history-XOP"],
    "b6c_pairs_distance": ["daily-history-DIA", "daily-history-EEM", "daily-history-EFA", "daily-history-EWA", "daily-history-EWC", "daily-history-EWD", "daily-history-EWG", "daily-history-EWH", "daily-history-EWI", "daily-history-EWJ", "daily-history-EWK", "daily-history-EWL", "daily-history-EWM", "daily-history-EWN", "daily-history-EWO", "daily-history-EWP", "daily-history-EWQ", "daily-history-EWS", "daily-history-EWT", "daily-history-EWU", "daily-history-EWW", "daily-history-EWY", "daily-history-EWZ", "daily-history-EZA", "daily-history-GDX", "daily-history-GLD", "daily-history-HYG", "daily-history-IEF", "daily-history-IWM", "daily-history-IYR", "daily-history-KRE", "daily-history-LQD", "daily-history-MDY", "daily-history-QQQ", "daily-history-SHY", "daily-history-SLV", "daily-history-SPY", "daily-history-TLT", "daily-history-VNQ", "daily-history-VWO", "daily-history-XHB", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY", "daily-history-XOP"],
    "b6c_pairs_dual_class": ["daily-events-BF-A", "daily-events-BF-B", "daily-events-BRK-A", "daily-events-BRK-B", "daily-events-FOX", "daily-events-FOXA", "daily-events-GOOG", "daily-events-GOOGL", "daily-events-HEI", "daily-events-HEI-A", "daily-events-LEN", "daily-events-LEN-B", "daily-events-NWS", "daily-events-NWSA", "daily-events-UA", "daily-events-UAA", "daily-events-Z", "daily-events-ZG", "daily-history-BF-A", "daily-history-BF-B", "daily-history-BRK-A", "daily-history-BRK-B", "daily-history-FOX", "daily-history-FOXA", "daily-history-GOOG", "daily-history-GOOGL", "daily-history-HEI", "daily-history-HEI-A", "daily-history-LEN", "daily-history-LEN-B", "daily-history-NWS", "daily-history-NWSA", "daily-history-UA", "daily-history-UAA", "daily-history-Z", "daily-history-ZG"],
    "b6c_pairs_kalman": ["daily-events-DIA", "daily-events-EEM", "daily-events-EWA", "daily-events-EWC", "daily-events-EWD", "daily-events-EWG", "daily-events-EWH", "daily-events-EWI", "daily-events-EWJ", "daily-events-EWK", "daily-events-EWL", "daily-events-EWM", "daily-events-EWN", "daily-events-EWO", "daily-events-EWP", "daily-events-EWQ", "daily-events-EWS", "daily-events-EWT", "daily-events-EWU", "daily-events-EWW", "daily-events-EWY", "daily-events-EWZ", "daily-events-EZA", "daily-events-GDX", "daily-events-GLD", "daily-events-HYG", "daily-events-IYR", "daily-events-KRE", "daily-events-LQD", "daily-events-MDY", "daily-events-SHY", "daily-events-VWO", "daily-events-XHB", "daily-events-XOP", "daily-history-BTC-USD", "daily-history-DIA", "daily-history-EEM", "daily-history-EFA", "daily-history-ETH-USD", "daily-history-EWA", "daily-history-EWC", "daily-history-EWD", "daily-history-EWG", "daily-history-EWH", "daily-history-EWI", "daily-history-EWJ", "daily-history-EWK", "daily-history-EWL", "daily-history-EWM", "daily-history-EWN", "daily-history-EWO", "daily-history-EWP", "daily-history-EWQ", "daily-history-EWS", "daily-history-EWT", "daily-history-EWU", "daily-history-EWW", "daily-history-EWY", "daily-history-EWZ", "daily-history-EZA", "daily-history-GDX", "daily-history-GLD", "daily-history-HYG", "daily-history-IEF", "daily-history-IWM", "daily-history-IYR", "daily-history-KRE", "daily-history-LQD", "daily-history-MDY", "daily-history-QQQ", "daily-history-SHY", "daily-history-SLV", "daily-history-SPY", "daily-history-TLT", "daily-history-VNQ", "daily-history-VWO", "daily-history-XHB", "daily-history-XLB", "daily-history-XLE", "daily-history-XLF", "daily-history-XLI", "daily-history-XLK", "daily-history-XLP", "daily-history-XLU", "daily-history-XLV", "daily-history-XLY", "daily-history-XOP"],
    "b6c_rates_credit_spread_timing": ["daily-history-BIL", "daily-history-HYG", "daily-history-IEF", "daily-history-IEI", "daily-history-LQD", "daily-history-SGOV", "fred-BAA10Y", "fred-DTB3"],
    "b6c_rates_cross_asset_carry": ["alfred-IRLTLT01AUM156N", "alfred-IRLTLT01CAM156N", "alfred-IRLTLT01CHM156N", "alfred-IRLTLT01DEM156N", "alfred-IRLTLT01GBM156N", "alfred-IRLTLT01JPM156N", "alfred-IRLTLT01NOM156N", "alfred-IRLTLT01NZM156N", "alfred-IRLTLT01SEM156N", "alfred-IRLTLT01USM156N", "cboe-VIX-history", "daily-events-EWA", "daily-events-EWC", "daily-events-EWD", "daily-events-EWG", "daily-events-EWI", "daily-events-EWJ", "daily-events-EWK", "daily-events-EWL", "daily-events-EWN", "daily-events-EWO", "daily-events-EWP", "daily-events-EWQ", "daily-events-EWU", "daily-history-BIL", "daily-history-EWA", "daily-history-EWC", "daily-history-EWD", "daily-history-EWG", "daily-history-EWI", "daily-history-EWJ", "daily-history-EWK", "daily-history-EWL", "daily-history-EWN", "daily-history-EWO", "daily-history-EWP", "daily-history-EWQ", "daily-history-EWU", "daily-history-HYG", "daily-history-IEF", "daily-history-IEI", "daily-history-LQD", "daily-history-SGOV", "daily-history-SPY", "fred-BAA10Y", "fred-DTB3", "fred-IRLTLT01AUM156N", "fred-IRLTLT01CAM156N", "fred-IRLTLT01CHM156N", "fred-IRLTLT01DEM156N", "fred-IRLTLT01GBM156N", "fred-IRLTLT01JPM156N", "fred-IRLTLT01NOM156N", "fred-IRLTLT01NZM156N", "fred-IRLTLT01SEM156N", "fred-IRLTLT01USM156N", "fred-USREC", "fx-rates-3m", "fx-spot-g10"],
    "b6c_rates_equity_country_carry": ["daily-events-EWA", "daily-events-EWC", "daily-events-EWD", "daily-events-EWG", "daily-events-EWI", "daily-events-EWJ", "daily-events-EWK", "daily-events-EWL", "daily-events-EWN", "daily-events-EWO", "daily-events-EWP", "daily-events-EWQ", "daily-events-EWU", "daily-history-DBC", "daily-history-EWA", "daily-history-EWC", "daily-history-EWD", "daily-history-EWG", "daily-history-EWI", "daily-history-EWJ", "daily-history-EWK", "daily-history-EWL", "daily-history-EWN", "daily-history-EWO", "daily-history-EWP", "daily-history-EWQ", "daily-history-EWU", "daily-history-SPY", "fx-rates-3m", "fx-spot-g10"],
    "b6c_rates_global_bond_carry": ["alfred-IRLTLT01AUM156N", "alfred-IRLTLT01CAM156N", "alfred-IRLTLT01CHM156N", "alfred-IRLTLT01DEM156N", "alfred-IRLTLT01GBM156N", "alfred-IRLTLT01JPM156N", "alfred-IRLTLT01NOM156N", "alfred-IRLTLT01NZM156N", "alfred-IRLTLT01SEM156N", "alfred-IRLTLT01USM156N", "daily-history-IEF", "fred-DTB3", "fred-IRLTLT01AUM156N", "fred-IRLTLT01CAM156N", "fred-IRLTLT01CHM156N", "fred-IRLTLT01DEM156N", "fred-IRLTLT01GBM156N", "fred-IRLTLT01JPM156N", "fred-IRLTLT01NOM156N", "fred-IRLTLT01NZM156N", "fred-IRLTLT01SEM156N", "fred-IRLTLT01USM156N", "fx-rates-3m"],
    "b6c_rates_tbill_ladder_sgov": ["daily-history-BIL", "daily-history-SGOV", "fred-DFF", "fred-DTB3"],
    "b6c_rates_treasury_butterfly": ["daily-history-IEF", "daily-history-IEI", "daily-history-SHY", "fomc-meetings", "fred-DGS10", "fred-DGS2", "fred-DGS5", "fred-DTB3"],
    "b6c_rates_treasury_carry_rolldown": ["daily-history-BIL", "daily-history-IEF", "daily-history-IEI", "daily-history-SGOV", "daily-history-SHY", "daily-history-TLT", "fred-DGS1", "fred-DGS10", "fred-DGS2", "fred-DGS20", "fred-DGS3", "fred-DGS5", "fred-DGS7", "fred-DTB3"],
    "b6c_macro_daa_canary": ["daily-history-BND", "daily-history-DBC", "daily-history-EWJ", "daily-history-GLD", "daily-history-HYG", "daily-history-IEF", "daily-history-IWM", "daily-history-LQD", "daily-history-QQQ", "daily-history-SHY", "daily-history-SPY", "daily-history-TLT", "daily-history-VGK", "daily-history-VNQ", "daily-history-VWO", "fred-DTB3"],
    "b6c_macro_fund_flow_dumb_money": ["alfred-BOGZ1FA653064100Q", "alfred-BOGZ1LM893064105Q", "daily-history-SPY", "fred-DTB3", "french-ff3-daily"],
    "b6c_macro_interlisted_parity": ["hourly-BMO", "hourly-BMO.TO", "hourly-BNS", "hourly-BNS.TO", "hourly-CAD-X", "hourly-CNI", "hourly-CNQ", "hourly-CNQ.TO", "hourly-CNR.TO", "hourly-CP", "hourly-CP.TO", "hourly-ENB", "hourly-ENB.TO", "hourly-RY", "hourly-RY.TO", "hourly-SHOP", "hourly-SHOP.TO", "hourly-SU", "hourly-SU.TO", "hourly-TD", "hourly-TD.TO"],
    "b6c_macro_letf_pair_decay": ["daily-history-QQQ", "daily-history-SDS", "daily-history-SPXU", "daily-history-SQQQ", "daily-history-SSO", "daily-history-SVXY", "daily-history-TQQQ", "daily-history-UPRO", "daily-history-UVXY", "fred-DTB3", "hourly-SQQQ", "hourly-TQQQ"],
    "b6c_macro_leverage_sma200": ["daily-history-SPY", "daily-history-SSO", "fred-DTB3"],
    "b6c_macro_sentiment_size_premium": ["alfred-CPIAUCSL", "alfred-UMCSENT", "alfred-UNRATE", "daily-history--GSPC", "daily-history--RUT", "daily-history-SPHB", "daily-history-SPLV", "fred-DTB3"],
    "b6c_pub_gld_flows": ["daily-history-GLD", "fred-DFII10", "spdr-gld-archive"],
    "b6c_pub_gold_cot_extremes": ["cftc-cot-disagg-f-088691", "cftc-cot-disagg-fo-084691", "cftc-cot-disagg-fo-088691", "daily-history-GDX", "daily-history-GLD", "daily-history-SLV", "fred-DFII10"],
    "b6c_pub_phys_discount_reversion": ["daily-history-GLD", "daily-history-PHYS", "daily-history-PSLV", "daily-history-SLV", "sprott-phys-nav", "sprott-pslv-nav"],
    "b6c_pub_treasury_auction_cycle": ["daily-history-IEF", "daily-history-TLT", "fomc-meetings", "fred-DGS10", "macro-release-cpi", "treasury-auctions"],
    "b6c_events_dividend_month": ["daily-events-A", "daily-events-AAPL", "daily-events-ABBV", "daily-events-ABNB", "daily-events-ABT", "daily-events-ACGL", "daily-events-ACN", "daily-events-ADBE", "daily-events-ADI", "daily-events-ADM", "daily-events-ADP", "daily-events-ADSK", "daily-events-AEE", "daily-events-AEP", "daily-events-AES", "daily-events-AFL", "daily-events-AIG", "daily-events-AIZ", "daily-events-AJG", "daily-events-AKAM", "daily-events-ALB", "daily-events-ALGN", "daily-events-ALL", "daily-events-ALLE", "daily-events-AMAT", "daily-events-AMCR", "daily-events-AMD", "daily-events-AME", "daily-events-AMGN", "daily-events-AMP", "daily-events-AMT", "daily-events-AMZN", "daily-events-ANET", "daily-events-AON", "daily-events-AOS", "daily-events-APA", "daily-events-APD", "daily-events-APH", "daily-events-APO", "daily-events-APP", "daily-events-APTV", "daily-events-ARE", "daily-events-ARES", "daily-events-ATO", "daily-events-AVGO", "daily-events-AVY", "daily-events-AWK", "daily-events-AXON", "daily-events-AXP", "daily-events-AZO", "daily-events-BA", "daily-events-BAC", "daily-events-BALL", "daily-events-BAX", "daily-events-BBY", "daily-events-BDX", "daily-events-BEN", "daily-events-BF-B", "daily-events-BG", "daily-events-BIIB", "daily-events-BKNG", "daily-events-BKR", "daily-events-BLK", "daily-events-BMY", "daily-events-BNY", "daily-events-BR", "daily-events-BRK-B", "daily-events-BRO", "daily-events-BSX", "daily-events-BX", "daily-events-BXP", "daily-events-C", "daily-events-CAH", "daily-events-CARR", "daily-events-CASY", "daily-events-CAT", "daily-events-CB", "daily-events-CBOE", "daily-events-CBRE", "daily-events-CCI", "daily-events-CCL", "daily-events-CDNS", "daily-events-CDW", "daily-events-CEG", "daily-events-CF", "daily-events-CFG", "daily-events-CHD", "daily-events-CHRW", "daily-events-CHTR", "daily-events-CI", "daily-events-CIEN", "daily-events-CINF", "daily-events-CL", "daily-events-CLX", "daily-events-CMCSA", "daily-events-CME", "daily-events-CMG", "daily-events-CMI", "daily-events-CMS", "daily-events-CNC", "daily-events-CNP", "daily-events-COF", "daily-events-COHR", "daily-events-COIN", "daily-events-COO", "daily-events-COP", "daily-events-COR", "daily-events-COST", "daily-events-CPAY", "daily-events-CPRT", "daily-events-CPT", "daily-events-CRH", "daily-events-CRL", "daily-events-CRM", "daily-events-CRWD", "daily-events-CSCO", "daily-events-CSGP", "daily-events-CSX", "daily-events-CTAS", "daily-events-CTSH", "daily-events-CVNA", "daily-events-CVS", "daily-events-CVX", "daily-events-D", "daily-events-DAL", "daily-events-DASH", "daily-events-DD", "daily-events-DDOG", "daily-events-DE", "daily-events-DECK", "daily-events-DELL", "daily-events-DG", "daily-events-DGX", "daily-events-DHI", "daily-events-DHR", "daily-events-DIS", "daily-events-DLR", "daily-events-DLTR", "daily-events-DOC", "daily-events-DOV", "daily-events-DOW", "daily-events-DPZ", "daily-events-DRI", "daily-events-DTE", "daily-events-DUK", "daily-events-DVA", "daily-events-DVN", "daily-events-DVY", "daily-events-DXCM", "daily-events-EBAY", "daily-events-ECHO", "daily-events-ECL", "daily-events-ED", "daily-events-EFX", "daily-events-EG", "daily-events-EIX", "daily-events-EL", "daily-events-ELV", "daily-events-EME", "daily-events-EMR", "daily-events-EOG", "daily-events-EQIX", "daily-events-EQT", "daily-events-ERIE", "daily-events-ES", "daily-events-ESS", "daily-events-ETN", "daily-events-ETR", "daily-events-EVRG", "daily-events-EW", "daily-events-EXC", "daily-events-EXE", "daily-events-EXPD", "daily-events-EXPE", "daily-events-EXR", "daily-events-F", "daily-events-FANG", "daily-events-FAST", "daily-events-FCX", "daily-events-FDS", "daily-events-FDX", "daily-events-FDXF", "daily-events-FE", "daily-events-FERG", "daily-events-FFIV", "daily-events-FICO", "daily-events-FIS", "daily-events-FISV", "daily-events-FITB", "daily-events-FIX", "daily-events-FLEX", "daily-events-FOX", "daily-events-FOXA", "daily-events-FRT", "daily-events-FSLR", "daily-events-FTNT", "daily-events-FTV", "daily-events-GD", "daily-events-GDDY", "daily-events-GE", "daily-events-GEHC", "daily-events-GEN", "daily-events-GEV", "daily-events-GILD", "daily-events-GIS", "daily-events-GL", "daily-events-GLW", "daily-events-GM", "daily-events-GNRC", "daily-events-GOOG", "daily-events-GOOGL", "daily-events-GPC", "daily-events-GPN", "daily-events-GRMN", "daily-events-GS", "daily-events-GWW", "daily-events-HAL", "daily-events-HAS", "daily-events-HBAN", "daily-events-HCA", "daily-events-HD", "daily-events-HIG", "daily-events-HII", "daily-events-HLT", "daily-events-HON", "daily-events-HONA", "daily-events-HOOD", "daily-events-HPE", "daily-events-HPQ", "daily-events-HRL", "daily-events-HSIC", "daily-events-HST", "daily-events-HSY", "daily-events-HUBB", "daily-events-HUM", "daily-events-HWM", "daily-events-IBKR", "daily-events-IBM", "daily-events-ICE", "daily-events-IDXX", "daily-events-IEX", "daily-events-IFF", "daily-events-ILMN", "daily-events-INCY", "daily-events-INTC", "daily-events-INTU", "daily-events-INVH", "daily-events-IP", "daily-events-IQV", "daily-events-IR", "daily-events-IRM", "daily-events-ISRG", "daily-events-IT", "daily-events-ITW", "daily-events-IVZ", "daily-events-J", "daily-events-JBHT", "daily-events-JBL", "daily-events-JCI", "daily-events-JKHY", "daily-events-JNJ", "daily-events-JPM", "daily-events-KDP", "daily-events-KEY", "daily-events-KEYS", "daily-events-KHC", "daily-events-KIM", "daily-events-KKR", "daily-events-KLAC", "daily-events-KMB", "daily-events-KMI", "daily-events-KO", "daily-events-KR", "daily-events-KVUE", "daily-events-L", "daily-events-LDOS", "daily-events-LEN", "daily-events-LH", "daily-events-LHX", "daily-events-LII", "daily-events-LIN", "daily-events-LITE", "daily-events-LLY", "daily-events-LMT", "daily-events-LNT", "daily-events-LOW", "daily-events-LRCX", "daily-events-LULU", "daily-events-LUV", "daily-events-LVS", "daily-events-LYB", "daily-events-LYV", "daily-events-MA", "daily-events-MAA", "daily-events-MAR", "daily-events-MAS", "daily-events-MCD", "daily-events-MCHP", "daily-events-MCK", "daily-events-MCO", "daily-events-MDLZ", "daily-events-MDT", "daily-events-MET", "daily-events-META", "daily-events-MGM", "daily-events-MKC", "daily-events-MLM", "daily-events-MMM", "daily-events-MNST", "daily-events-MO", "daily-events-MOS", "daily-events-MPC", "daily-events-MPWR", "daily-events-MRK", "daily-events-MRNA", "daily-events-MRSH", "daily-events-MRVL", "daily-events-MS", "daily-events-MSCI", "daily-events-MSFT", "daily-events-MSI", "daily-events-MTB", "daily-events-MTD", "daily-events-MU", "daily-events-NCLH", "daily-events-NDAQ", "daily-events-NDSN", "daily-events-NEE", "daily-events-NEM", "daily-events-NFLX", "daily-events-NI", "daily-events-NKE", "daily-events-NOC", "daily-events-NOW", "daily-events-NRG", "daily-events-NSC", "daily-events-NTAP", "daily-events-NTRS", "daily-events-NUE", "daily-events-NVDA", "daily-events-NVR", "daily-events-NWS", "daily-events-NWSA", "daily-events-NXPI", "daily-events-O", "daily-events-ODFL", "daily-events-OKE", "daily-events-OMC", "daily-events-ON", "daily-events-ORCL", "daily-events-ORLY", "daily-events-OTIS", "daily-events-OXY", "daily-events-PANW", "daily-events-PAYX", "daily-events-PCAR", "daily-events-PCG", "daily-events-PEG", "daily-events-PEP", "daily-events-PFE", "daily-events-PFG", "daily-events-PG", "daily-events-PGR", "daily-events-PH", "daily-events-PHM", "daily-events-PKG", "daily-events-PLD", "daily-events-PLTR", "daily-events-PM", "daily-events-PNC", "daily-events-PNR", "daily-events-PNW", "daily-events-PODD", "daily-events-PPG", "daily-events-PPL", "daily-events-PRU", "daily-events-PSA", "daily-events-PSX", "daily-events-PTC", "daily-events-PWR", "daily-events-PYPL", "daily-events-Q", "daily-events-QCOM", "daily-events-RCL", "daily-events-RDDT", "daily-events-REG", "daily-events-REGN", "daily-events-RF", "daily-events-RJF", "daily-events-RL", "daily-events-RMD", "daily-events-ROK", "daily-events-ROL", "daily-events-ROP", "daily-events-ROST", "daily-events-RSG", "daily-events-RTX", "daily-events-RVTY", "daily-events-SBAC", "daily-events-SBUX", "daily-events-SCHD", "daily-events-SCHW", "daily-events-SDY", "daily-events-SHW", "daily-events-SJM", "daily-events-SLB", "daily-events-SMCI", "daily-events-SNA", "daily-events-SNDK", "daily-events-SNPS", "daily-events-SO", "daily-events-SOLV", "daily-events-SPG", "daily-events-SPGI", "daily-events-SRE", "daily-events-STE", "daily-events-STLD", "daily-events-STT", "daily-events-STX", "daily-events-STZ", "daily-events-SW", "daily-events-SWK", "daily-events-SWKS", "daily-events-SYF", "daily-events-SYK", "daily-events-SYY", "daily-events-T", "daily-events-TDG", "daily-events-TDY", "daily-events-TECH", "daily-events-TEL", "daily-events-TER", "daily-events-TFC", "daily-events-TGT", "daily-events-TJX", "daily-events-TKO", "daily-events-TMO", "daily-events-TMUS", "daily-events-TPL", "daily-events-TPR", "daily-events-TRGP", "daily-events-TRMB", "daily-events-TROW", "daily-events-TRV", "daily-events-TSCO", "daily-events-TSLA", "daily-events-TSN", "daily-events-TT", "daily-events-TTWO", "daily-events-TXN", "daily-events-TXT", "daily-events-TYL", "daily-events-UAL", "daily-events-UBER", "daily-events-UDR", "daily-events-UHS", "daily-events-ULTA", "daily-events-UNH", "daily-events-UNP", "daily-events-UPS", "daily-events-URI", "daily-events-USB", "daily-events-V", "daily-events-VEEV", "daily-events-VICI", "daily-events-VLO", "daily-events-VLTO", "daily-events-VMC", "daily-events-VMRK", "daily-events-VRSK", "daily-events-VRSN", "daily-events-VRT", "daily-events-VRTX", "daily-events-VST", "daily-events-VTR", "daily-events-VTRS", "daily-events-VYM", "daily-events-VZ", "daily-events-WAB", "daily-events-WAT", "daily-events-WDAY", "daily-events-WDC", "daily-events-WEC", "daily-events-WELL", "daily-events-WFC", "daily-events-WM", "daily-events-WMB", "daily-events-WMT", "daily-events-WRB", "daily-events-WSM", "daily-events-WST", "daily-events-WTW", "daily-events-WY", "daily-events-WYNN", "daily-events-XEL", "daily-events-XOM", "daily-events-XYL", "daily-events-XYZ", "daily-events-YUM", "daily-events-ZBH", "daily-events-ZBRA", "daily-events-ZTS", "daily-history-A", "daily-history-AAPL", "daily-history-ABBV", "daily-history-ABNB", "daily-history-ABT", "daily-history-ACGL", "daily-history-ACN", "daily-history-ADBE", "daily-history-ADI", "daily-history-ADM", "daily-history-ADP", "daily-history-ADSK", "daily-history-AEE", "daily-history-AEP", "daily-history-AES", "daily-history-AFL", "daily-history-AIG", "daily-history-AIZ", "daily-history-AJG", "daily-history-AKAM", "daily-history-ALB", "daily-history-ALGN", "daily-history-ALL", "daily-history-ALLE", "daily-history-AMAT", "daily-history-AMCR", "daily-history-AMD", "daily-history-AME", "daily-history-AMGN", "daily-history-AMP", "daily-history-AMT", "daily-history-AMZN", "daily-history-ANET", "daily-history-AON", "daily-history-AOS", "daily-history-APA", "daily-history-APD", "daily-history-APH", "daily-history-APO", "daily-history-APP", "daily-history-APTV", "daily-history-ARE", "daily-history-ARES", "daily-history-ATO", "daily-history-AVGO", "daily-history-AVY", "daily-history-AWK", "daily-history-AXON", "daily-history-AXP", "daily-history-AZO", "daily-history-BA", "daily-history-BAC", "daily-history-BALL", "daily-history-BAX", "daily-history-BBY", "daily-history-BDX", "daily-history-BEN", "daily-history-BF-B", "daily-history-BG", "daily-history-BIIB", "daily-history-BKNG", "daily-history-BKR", "daily-history-BLK", "daily-history-BMY", "daily-history-BNY", "daily-history-BR", "daily-history-BRK-B", "daily-history-BRO", "daily-history-BSX", "daily-history-BX", "daily-history-BXP", "daily-history-C", "daily-history-CAH", "daily-history-CARR", "daily-history-CASY", "daily-history-CAT", "daily-history-CB", "daily-history-CBOE", "daily-history-CBRE", "daily-history-CCI", "daily-history-CCL", "daily-history-CDNS", "daily-history-CDW", "daily-history-CEG", "daily-history-CF", "daily-history-CFG", "daily-history-CHD", "daily-history-CHRW", "daily-history-CHTR", "daily-history-CI", "daily-history-CIEN", "daily-history-CINF", "daily-history-CL", "daily-history-CLX", "daily-history-CMCSA", "daily-history-CME", "daily-history-CMG", "daily-history-CMI", "daily-history-CMS", "daily-history-CNC", "daily-history-CNP", "daily-history-COF", "daily-history-COHR", "daily-history-COIN", "daily-history-COO", "daily-history-COP", "daily-history-COR", "daily-history-COST", "daily-history-CPAY", "daily-history-CPRT", "daily-history-CPT", "daily-history-CRH", "daily-history-CRL", "daily-history-CRM", "daily-history-CRWD", "daily-history-CSCO", "daily-history-CSGP", "daily-history-CSX", "daily-history-CTAS", "daily-history-CTSH", "daily-history-CVNA", "daily-history-CVS", "daily-history-CVX", "daily-history-D", "daily-history-DAL", "daily-history-DASH", "daily-history-DD", "daily-history-DDOG", "daily-history-DE", "daily-history-DECK", "daily-history-DELL", "daily-history-DG", "daily-history-DGX", "daily-history-DHI", "daily-history-DHR", "daily-history-DIS", "daily-history-DLR", "daily-history-DLTR", "daily-history-DOC", "daily-history-DOV", "daily-history-DOW", "daily-history-DPZ", "daily-history-DRI", "daily-history-DTE", "daily-history-DUK", "daily-history-DVA", "daily-history-DVN", "daily-history-DVY", "daily-history-DXCM", "daily-history-EBAY", "daily-history-ECHO", "daily-history-ECL", "daily-history-ED", "daily-history-EFX", "daily-history-EG", "daily-history-EIX", "daily-history-EL", "daily-history-ELV", "daily-history-EME", "daily-history-EMR", "daily-history-EOG", "daily-history-EQIX", "daily-history-EQT", "daily-history-ERIE", "daily-history-ES", "daily-history-ESS", "daily-history-ETN", "daily-history-ETR", "daily-history-EVRG", "daily-history-EW", "daily-history-EXC", "daily-history-EXE", "daily-history-EXPD", "daily-history-EXPE", "daily-history-EXR", "daily-history-F", "daily-history-FANG", "daily-history-FAST", "daily-history-FCX", "daily-history-FDS", "daily-history-FDX", "daily-history-FDXF", "daily-history-FE", "daily-history-FERG", "daily-history-FFIV", "daily-history-FICO", "daily-history-FIS", "daily-history-FISV", "daily-history-FITB", "daily-history-FIX", "daily-history-FLEX", "daily-history-FOX", "daily-history-FOXA", "daily-history-FRT", "daily-history-FSLR", "daily-history-FTNT", "daily-history-FTV", "daily-history-GD", "daily-history-GDDY", "daily-history-GE", "daily-history-GEHC", "daily-history-GEN", "daily-history-GEV", "daily-history-GILD", "daily-history-GIS", "daily-history-GL", "daily-history-GLW", "daily-history-GM", "daily-history-GNRC", "daily-history-GOOG", "daily-history-GOOGL", "daily-history-GPC", "daily-history-GPN", "daily-history-GRMN", "daily-history-GS", "daily-history-GWW", "daily-history-HAL", "daily-history-HAS", "daily-history-HBAN", "daily-history-HCA", "daily-history-HD", "daily-history-HIG", "daily-history-HII", "daily-history-HLT", "daily-history-HON", "daily-history-HONA", "daily-history-HOOD", "daily-history-HPE", "daily-history-HPQ", "daily-history-HRL", "daily-history-HSIC", "daily-history-HST", "daily-history-HSY", "daily-history-HUBB", "daily-history-HUM", "daily-history-HWM", "daily-history-IBKR", "daily-history-IBM", "daily-history-ICE", "daily-history-IDXX", "daily-history-IEX", "daily-history-IFF", "daily-history-ILMN", "daily-history-INCY", "daily-history-INTC", "daily-history-INTU", "daily-history-INVH", "daily-history-IP", "daily-history-IQV", "daily-history-IR", "daily-history-IRM", "daily-history-ISRG", "daily-history-IT", "daily-history-ITW", "daily-history-IVZ", "daily-history-J", "daily-history-JBHT", "daily-history-JBL", "daily-history-JCI", "daily-history-JKHY", "daily-history-JNJ", "daily-history-JPM", "daily-history-KDP", "daily-history-KEY", "daily-history-KEYS", "daily-history-KHC", "daily-history-KIM", "daily-history-KKR", "daily-history-KLAC", "daily-history-KMB", "daily-history-KMI", "daily-history-KO", "daily-history-KR", "daily-history-KVUE", "daily-history-L", "daily-history-LDOS", "daily-history-LEN", "daily-history-LH", "daily-history-LHX", "daily-history-LII", "daily-history-LIN", "daily-history-LITE", "daily-history-LLY", "daily-history-LMT", "daily-history-LNT", "daily-history-LOW", "daily-history-LRCX", "daily-history-LULU", "daily-history-LUV", "daily-history-LVS", "daily-history-LYB", "daily-history-LYV", "daily-history-MA", "daily-history-MAA", "daily-history-MAR", "daily-history-MAS", "daily-history-MCD", "daily-history-MCHP", "daily-history-MCK", "daily-history-MCO", "daily-history-MDLZ", "daily-history-MDT", "daily-history-MET", "daily-history-META", "daily-history-MGM", "daily-history-MKC", "daily-history-MLM", "daily-history-MMM", "daily-history-MNST", "daily-history-MO", "daily-history-MOS", "daily-history-MPC", "daily-history-MPWR", "daily-history-MRK", "daily-history-MRNA", "daily-history-MRSH", "daily-history-MRVL", "daily-history-MS", "daily-history-MSCI", "daily-history-MSFT", "daily-history-MSI", "daily-history-MTB", "daily-history-MTD", "daily-history-MU", "daily-history-NCLH", "daily-history-NDAQ", "daily-history-NDSN", "daily-history-NEE", "daily-history-NEM", "daily-history-NFLX", "daily-history-NI", "daily-history-NKE", "daily-history-NOC", "daily-history-NOW", "daily-history-NRG", "daily-history-NSC", "daily-history-NTAP", "daily-history-NTRS", "daily-history-NUE", "daily-history-NVDA", "daily-history-NVR", "daily-history-NWS", "daily-history-NWSA", "daily-history-NXPI", "daily-history-O", "daily-history-ODFL", "daily-history-OKE", "daily-history-OMC", "daily-history-ON", "daily-history-ORCL", "daily-history-ORLY", "daily-history-OTIS", "daily-history-OXY", "daily-history-PANW", "daily-history-PAYX", "daily-history-PCAR", "daily-history-PCG", "daily-history-PEG", "daily-history-PEP", "daily-history-PFE", "daily-history-PFG", "daily-history-PG", "daily-history-PGR", "daily-history-PH", "daily-history-PHM", "daily-history-PKG", "daily-history-PLD", "daily-history-PLTR", "daily-history-PM", "daily-history-PNC", "daily-history-PNR", "daily-history-PNW", "daily-history-PODD", "daily-history-PPG", "daily-history-PPL", "daily-history-PRU", "daily-history-PSA", "daily-history-PSX", "daily-history-PTC", "daily-history-PWR", "daily-history-PYPL", "daily-history-Q", "daily-history-QCOM", "daily-history-RCL", "daily-history-RDDT", "daily-history-REG", "daily-history-REGN", "daily-history-RF", "daily-history-RJF", "daily-history-RL", "daily-history-RMD", "daily-history-ROK", "daily-history-ROL", "daily-history-ROP", "daily-history-ROST", "daily-history-RSG", "daily-history-RTX", "daily-history-RVTY", "daily-history-SBAC", "daily-history-SBUX", "daily-history-SCHD", "daily-history-SCHW", "daily-history-SDY", "daily-history-SHW", "daily-history-SJM", "daily-history-SLB", "daily-history-SMCI", "daily-history-SNA", "daily-history-SNDK", "daily-history-SNPS", "daily-history-SO", "daily-history-SOLV", "daily-history-SPG", "daily-history-SPGI", "daily-history-SPY", "daily-history-SRE", "daily-history-STE", "daily-history-STLD", "daily-history-STT", "daily-history-STX", "daily-history-STZ", "daily-history-SW", "daily-history-SWK", "daily-history-SWKS", "daily-history-SYF", "daily-history-SYK", "daily-history-SYY", "daily-history-T", "daily-history-TDG", "daily-history-TDY", "daily-history-TECH", "daily-history-TEL", "daily-history-TER", "daily-history-TFC", "daily-history-TGT", "daily-history-TJX", "daily-history-TKO", "daily-history-TMO", "daily-history-TMUS", "daily-history-TPL", "daily-history-TPR", "daily-history-TRGP", "daily-history-TRMB", "daily-history-TROW", "daily-history-TRV", "daily-history-TSCO", "daily-history-TSLA", "daily-history-TSN", "daily-history-TT", "daily-history-TTWO", "daily-history-TXN", "daily-history-TXT", "daily-history-TYL", "daily-history-UAL", "daily-history-UBER", "daily-history-UDR", "daily-history-UHS", "daily-history-ULTA", "daily-history-UNH", "daily-history-UNP", "daily-history-UPS", "daily-history-URI", "daily-history-USB", "daily-history-V", "daily-history-VEEV", "daily-history-VICI", "daily-history-VLO", "daily-history-VLTO", "daily-history-VMC", "daily-history-VMRK", "daily-history-VRSK", "daily-history-VRSN", "daily-history-VRT", "daily-history-VRTX", "daily-history-VST", "daily-history-VTR", "daily-history-VTRS", "daily-history-VYM", "daily-history-VZ", "daily-history-WAB", "daily-history-WAT", "daily-history-WDAY", "daily-history-WDC", "daily-history-WEC", "daily-history-WELL", "daily-history-WFC", "daily-history-WM", "daily-history-WMB", "daily-history-WMT", "daily-history-WRB", "daily-history-WSM", "daily-history-WST", "daily-history-WTW", "daily-history-WY", "daily-history-WYNN", "daily-history-XEL", "daily-history-XOM", "daily-history-XYL", "daily-history-XYZ", "daily-history-YUM", "daily-history-ZBH", "daily-history-ZBRA", "daily-history-ZTS", "ssga-spy-holdings-*", "wikipedia-sp500-constituents"],
    "b6c_events_index_addition_reversal": ["daily-history-A", "daily-history-AAL", "daily-history-AAP", "daily-history-AAPL", "daily-history-ABBV", "daily-history-ABNB", "daily-history-ABT", "daily-history-ACGL", "daily-history-ACN", "daily-history-ADBE", "daily-history-ADI", "daily-history-ADM", "daily-history-ADP", "daily-history-ADSK", "daily-history-ADT", "daily-history-AEE", "daily-history-AEP", "daily-history-AES", "daily-history-AFL", "daily-history-AIG", "daily-history-AIV", "daily-history-AIZ", "daily-history-AJG", "daily-history-AKAM", "daily-history-ALB", "daily-history-ALGN", "daily-history-ALK", "daily-history-ALL", "daily-history-ALLE", "daily-history-AMAT", "daily-history-AMCR", "daily-history-AMD", "daily-history-AME", "daily-history-AMG", "daily-history-AMGN", "daily-history-AMP", "daily-history-AMT", "daily-history-AMTM", "daily-history-AMZN", "daily-history-AN", "daily-history-ANET", "daily-history-ANF", "daily-history-AON", "daily-history-AOS", "daily-history-APA", "daily-history-APC", "daily-history-APD", "daily-history-APH", "daily-history-APO", "daily-history-APP", "daily-history-APTV", "daily-history-ARE", "daily-history-ARES", "daily-history-ATI", "daily-history-ATO", "daily-history-AVGO", "daily-history-AVY", "daily-history-AWK", "daily-history-AXON", "daily-history-AXP", "daily-history-AYI", "daily-history-AZO", "daily-history-BA", "daily-history-BAC", "daily-history-BALL", "daily-history-BAX", "daily-history-BBBY", "daily-history-BBT", "daily-history-BBWI", "daily-history-BBY", "daily-history-BDX", "daily-history-BEAM", "daily-history-BEN", "daily-history-BF-B", "daily-history-BG", "daily-history-BHF", "daily-history-BIIB", "daily-history-BIO", "daily-history-BKNG", "daily-history-BKR", "daily-history-BLDR", "daily-history-BLK", "daily-history-BMY", "daily-history-BNY", "daily-history-BR", "daily-history-BRK-B", "daily-history-BRO", "daily-history-BSX", "daily-history-BWA", "daily-history-BX", "daily-history-BXP", "daily-history-C", "daily-history-CAG", "daily-history-CAH", "daily-history-CAM", "daily-history-CARR", "daily-history-CASY", "daily-history-CAT", "daily-history-CB", "daily-history-CBOE", "daily-history-CBRE", "daily-history-CCEP", "daily-history-CCI", "daily-history-CCL", "daily-history-CDNS", "daily-history-CDW", "daily-history-CE", "daily-history-CEG", "daily-history-CF", "daily-history-CFG", "daily-history-CHD", "daily-history-CHRW", "daily-history-CHTR", "daily-history-CI", "daily-history-CIEN", "daily-history-CINF", "daily-history-CL", "daily-history-CLF", "daily-history-CLX", "daily-history-CMCSA", "daily-history-CME", "daily-history-CMG", "daily-history-CMI", "daily-history-CMS", "daily-history-CNC", "daily-history-CNP", "daily-history-CNX", "daily-history-COF", "daily-history-COHR", "daily-history-COIN", "daily-history-COO", "daily-history-COP", "daily-history-COR", "daily-history-COST", "daily-history-COTY", "daily-history-CPAY", "daily-history-CPB", "daily-history-CPRI", "daily-history-CPRT", "daily-history-CPT", "daily-history-CPWR", "daily-history-CRH", "daily-history-CRL", "daily-history-CRM", "daily-history-CRWD", "daily-history-CSCO", "daily-history-CSGP", "daily-history-CSRA", "daily-history-CSX", "daily-history-CTAS", "daily-history-CTSH", "daily-history-CTVA", "daily-history-CVNA", "daily-history-CVS", "daily-history-CVX", "daily-history-CZR", "daily-history-D", "daily-history-DAL", "daily-history-DASH", "daily-history-DD", "daily-history-DDOG", "daily-history-DE", "daily-history-DECK", "daily-history-DELL", "daily-history-DG", "daily-history-DGX", "daily-history-DHI", "daily-history-DHR", "daily-history-DIS", "daily-history-DLR", "daily-history-DLTR", "daily-history-DOC", "daily-history-DOV", "daily-history-DOW", "daily-history-DPZ", "daily-history-DRI", "daily-history-DTE", "daily-history-DUK", "daily-history-DVA", "daily-history-DVN", "daily-history-DXC", "daily-history-DXCM", "daily-history-EBAY", "daily-history-ECHO", "daily-history-ECL", "daily-history-ED", "daily-history-EFX", "daily-history-EG", "daily-history-EIX", "daily-history-EL", "daily-history-ELV", "daily-history-EMC", "daily-history-EME", "daily-history-EMN", "daily-history-EMR", "daily-history-ENPH", "daily-history-EOG", "daily-history-EP", "daily-history-EPAM", "daily-history-EQIX", "daily-history-EQT", "daily-history-ERIE", "daily-history-ES", "daily-history-ESS", "daily-history-ETN", "daily-history-ETR", "daily-history-ETSY", "daily-history-EVRG", "daily-history-EW", "daily-history-EXC", "daily-history-EXE", "daily-history-EXPD", "daily-history-EXPE", "daily-history-EXR", "daily-history-F", "daily-history-FANG", "daily-history-FAST", "daily-history-FB", "daily-history-FCPT", "daily-history-FCX", "daily-history-FDS", "daily-history-FDX", "daily-history-FDXF", "daily-history-FE", "daily-history-FERG", "daily-history-FFIV", "daily-history-FHN", "daily-history-FICO", "daily-history-FIS", "daily-history-FISV", "daily-history-FITB", "daily-history-FIX", "daily-history-FLEX", "daily-history-FLR", "daily-history-FLS", "daily-history-FMC", "daily-history-FOSL", "daily-history-FOX", "daily-history-FOXA", "daily-history-FRT", "daily-history-FSLR", "daily-history-FTI", "daily-history-FTNT", "daily-history-FTV", "daily-history-GD", "daily-history-GDDY", "daily-history-GE", "daily-history-GEHC", "daily-history-GEN", "daily-history-GENZ", "daily-history-GEV", "daily-history-GHC", "daily-history-GILD", "daily-history-GIS", "daily-history-GL", "daily-history-GLW", "daily-history-GM", "daily-history-GME", "daily-history-GNRC", "daily-history-GNW", "daily-history-GOOG", "daily-history-GOOGL", "daily-history-GPC", "daily-history-GPN", "daily-history-GRMN", "daily-history-GS", "daily-history-GT", "daily-history-GWW", "daily-history-HAL", "daily-history-HAS", "daily-history-HBAN", "daily-history-HCA", "daily-history-HD", "daily-history-HIG", "daily-history-HII", "daily-history-HLT", "daily-history-HOG", "daily-history-HON", "daily-history-HONA", "daily-history-HOOD", "daily-history-HP", "daily-history-HPE", "daily-history-HPQ", "daily-history-HRB", "daily-history-HRL", "daily-history-HSIC", "daily-history-HST", "daily-history-HSY", "daily-history-HUBB", "daily-history-HUM", "daily-history-HWM", "daily-history-IBKR", "daily-history-IBM", "daily-history-ICE", "daily-history-IDXX", "daily-history-IEX", "daily-history-IFF", "daily-history-ILMN", "daily-history-INCY", "daily-history-INFO", "daily-history-INTC", "daily-history-INTU", "daily-history-INVH", "daily-history-IP", "daily-history-IPGP", "daily-history-IQV", "daily-history-IR", "daily-history-IRM", "daily-history-ISRG", "daily-history-IT", "daily-history-ITT", "daily-history-ITW", "daily-history-IVZ", "daily-history-J", "daily-history-JBHT", "daily-history-JBL", "daily-history-JCI", "daily-history-JEF", "daily-history-JKHY", "daily-history-JNJ", "daily-history-JPM", "daily-history-KDP", "daily-history-KEY", "daily-history-KEYS", "daily-history-KG", "daily-history-KHC", "daily-history-KIM", "daily-history-KKR", "daily-history-KLAC", "daily-history-KMB", "daily-history-KMI", "daily-history-KMX", "daily-history-KO", "daily-history-KR", "daily-history-KSS", "daily-history-KVUE", "daily-history-L", "daily-history-LB", "daily-history-LDOS", "daily-history-LEN", "daily-history-LH", "daily-history-LHX", "daily-history-LIFE", "daily-history-LII", "daily-history-LIN", "daily-history-LITE", "daily-history-LKQ", "daily-history-LLY", "daily-history-LMT", "daily-history-LNC", "daily-history-LNT", "daily-history-LOW", "daily-history-LRCX", "daily-history-LULU", "daily-history-LUMN", "daily-history-LUV", "daily-history-LVS", "daily-history-LW", "daily-history-LYB", "daily-history-LYV", "daily-history-M", "daily-history-MA", "daily-history-MAA", "daily-history-MAC", "daily-history-MAR", "daily-history-MAS", "daily-history-MAT", "daily-history-MCD", "daily-history-MCHP", "daily-history-MCK", "daily-history-MCO", "daily-history-MDLZ", "daily-history-MDT", "daily-history-MET", "daily-history-META", "daily-history-MGM", "daily-history-MHK", "daily-history-MI", "daily-history-MKC", "daily-history-MKTX", "daily-history-MLM", "daily-history-MMI", "daily-history-MMM", "daily-history-MNST", "daily-history-MO", "daily-history-MOH", "daily-history-MOS", "daily-history-MPC", "daily-history-MPWR", "daily-history-MRK", "daily-history-MRNA", "daily-history-MRSH", "daily-history-MRVL", "daily-history-MS", "daily-history-MSCI", "daily-history-MSFT", "daily-history-MSI", "daily-history-MTB", "daily-history-MTCH", "daily-history-MTD", "daily-history-MU", "daily-history-MUR", "daily-history-NAVI", "daily-history-NBR", "daily-history-NCLH", "daily-history-NDAQ", "daily-history-NDSN", "daily-history-NE", "daily-history-NEE", "daily-history-NEM", "daily-history-NFLX", "daily-history-NFX", "daily-history-NI", "daily-history-NKE", "daily-history-NKTR", "daily-history-NOC", "daily-history-NOV", "daily-history-NOW", "daily-history-NRG", "daily-history-NSC", "daily-history-NTAP", "daily-history-NTRS", "daily-history-NUE", "daily-history-NVDA", "daily-history-NVR", "daily-history-NWL", "daily-history-NWS", "daily-history-NWSA", "daily-history-NXPI", "daily-history-NYT", "daily-history-O", "daily-history-ODFL", "daily-history-OGN", "daily-history-OI", "daily-history-OKE", "daily-history-OMC", "daily-history-ON", "daily-history-ORCL", "daily-history-ORLY", "daily-history-OTIS", "daily-history-OXY", "daily-history-PANW", "daily-history-PARA", "daily-history-PAYC", "daily-history-PAYX", "daily-history-PBI", "daily-history-PCAR", "daily-history-PCG", "daily-history-PCL", "daily-history-PEG", "daily-history-PENN", "daily-history-PEP", "daily-history-PFE", "daily-history-PFG", "daily-history-PG", "daily-history-PGR", "daily-history-PH", "daily-history-PHM", "daily-history-PKG", "daily-history-PLD", "daily-history-PLTR", "daily-history-PM", "daily-history-PNC", "daily-history-PNR", "daily-history-PNW", "daily-history-PODD", "daily-history-POM", "daily-history-POOL", "daily-history-PPG", "daily-history-PPL", "daily-history-PRGO", "daily-history-PRU", "daily-history-PSA", "daily-history-PSKY", "daily-history-PSX", "daily-history-PTC", "daily-history-PVH", "daily-history-PWR", "daily-history-PYPL", "daily-history-Q", "daily-history-QCOM", "daily-history-R", "daily-history-RCL", "daily-history-RDDT", "daily-history-REG", "daily-history-REGN", "daily-history-RF", "daily-history-RHI", "daily-history-RIG", "daily-history-RJF", "daily-history-RL", "daily-history-RMD", "daily-history-ROK", "daily-history-ROL", "daily-history-ROP", "daily-history-ROST", "daily-history-RRC", "daily-history-RSG", "daily-history-RTX", "daily-history-RVTY", "daily-history-S", "daily-history-SBAC", "daily-history-SBNY", "daily-history-SBUX", "daily-history-SCHW", "daily-history-SE", "daily-history-SEDG", "daily-history-SHLD", "daily-history-SHW", "daily-history-SIG", "daily-history-SII", "daily-history-SJM", "daily-history-SLB", "daily-history-SLG", "daily-history-SLM", "daily-history-SMCI", "daily-history-SNA", "daily-history-SNDK", "daily-history-SNPS", "daily-history-SO", "daily-history-SOLS", "daily-history-SOLV", "daily-history-SPG", "daily-history-SPGI", "daily-history-SPLS", "daily-history-SPY", "daily-history-SRE", "daily-history-STE", "daily-history-STI", "daily-history-STLD", "daily-history-STT", "daily-history-STX", "daily-history-STZ", "daily-history-SUN", "daily-history-SW", "daily-history-SWK", "daily-history-SWKS", "daily-history-SYF", "daily-history-SYK", "daily-history-SYY", "daily-history-T", "daily-history-TAP", "daily-history-TDC", "daily-history-TDG", "daily-history-TDY", "daily-history-TE", "daily-history-TECH", "daily-history-TEL", "daily-history-TER", "daily-history-TFC", "daily-history-TFX", "daily-history-TGT", "daily-history-THC", "daily-history-TJX", "daily-history-TKO", "daily-history-TMO", "daily-history-TMUS", "daily-history-TPL", "daily-history-TPR", "daily-history-TRGP", "daily-history-TRIP", "daily-history-TRMB", "daily-history-TROW", "daily-history-TRV", "daily-history-TSCO", "daily-history-TSLA", "daily-history-TSN", "daily-history-TT", "daily-history-TTD", "daily-history-TTWO", "daily-history-TXN", "daily-history-TXT", "daily-history-TYL", "daily-history-UA", "daily-history-UAA", "daily-history-UAL", "daily-history-UBER", "daily-history-UDR", "daily-history-UHS", "daily-history-ULTA", "daily-history-UNH", "daily-history-UNM", "daily-history-UNP", "daily-history-UPS", "daily-history-URBN", "daily-history-URI", "daily-history-USB", "daily-history-V", "daily-history-VEEV", "daily-history-VFC", "daily-history-VIAV", "daily-history-VICI", "daily-history-VLO", "daily-history-VLTO", "daily-history-VMC", "daily-history-VMRK", "daily-history-VNO", "daily-history-VNT", "daily-history-VRSK", "daily-history-VRSN", "daily-history-VRT", "daily-history-VRTX", "daily-history-VST", "daily-history-VTR", "daily-history-VTRS", "daily-history-VZ", "daily-history-WAB", "daily-history-WAT", "daily-history-WDAY", "daily-history-WDC", "daily-history-WEC", "daily-history-WELL", "daily-history-WFC", "daily-history-WHR", "daily-history-WM", "daily-history-WMB", "daily-history-WMT", "daily-history-WRB", "daily-history-WSM", "daily-history-WST", "daily-history-WTW", "daily-history-WU", "daily-history-WY", "daily-history-WYNN", "daily-history-XEL", "daily-history-XOM", "daily-history-XRAY", "daily-history-XRX", "daily-history-XYL", "daily-history-XYZ", "daily-history-YUM", "daily-history-ZBH", "daily-history-ZBRA", "daily-history-ZION", "daily-history-ZTS", "fja-sp500-components", "wikipedia-sp500-changes", "wikipedia-sp500-constituents"],
    "b6c_events_short_volume_ratio": ["daily-events-A", "daily-events-AAL", "daily-events-AAP", "daily-events-AAPL", "daily-events-ABBV", "daily-events-ABNB", "daily-events-ABT", "daily-events-ACGL", "daily-events-ACN", "daily-events-ADBE", "daily-events-ADI", "daily-events-ADM", "daily-events-ADP", "daily-events-ADSK", "daily-events-AEE", "daily-events-AEP", "daily-events-AES", "daily-events-AFL", "daily-events-AIG", "daily-events-AIV", "daily-events-AIZ", "daily-events-AJG", "daily-events-AKAM", "daily-events-ALB", "daily-events-ALGN", "daily-events-ALK", "daily-events-ALL", "daily-events-ALLE", "daily-events-AMAT", "daily-events-AMCR", "daily-events-AMD", "daily-events-AME", "daily-events-AMG", "daily-events-AMGN", "daily-events-AMP", "daily-events-AMT", "daily-events-AMTM", "daily-events-AMZN", "daily-events-ANET", "daily-events-AON", "daily-events-AOS", "daily-events-APA", "daily-events-APC", "daily-events-APD", "daily-events-APH", "daily-events-APO", "daily-events-APP", "daily-events-APTV", "daily-events-ARE", "daily-events-ARES", "daily-events-ATO", "daily-events-AVGO", "daily-events-AVY", "daily-events-AWK", "daily-events-AXON", "daily-events-AXP", "daily-events-AZO", "daily-events-BA", "daily-events-BAC", "daily-events-BALL", "daily-events-BAX", "daily-events-BBT", "daily-events-BBWI", "daily-events-BBY", "daily-events-BDX", "daily-events-BEN", "daily-events-BF-B", "daily-events-BG", "daily-events-BHF", "daily-events-BIIB", "daily-events-BIO", "daily-events-BKNG", "daily-events-BKR", "daily-events-BLDR", "daily-events-BLK", "daily-events-BMY", "daily-events-BNY", "daily-events-BR", "daily-events-BRK-B", "daily-events-BRO", "daily-events-BSX", "daily-events-BWA", "daily-events-BX", "daily-events-BXP", "daily-events-C", "daily-events-CAG", "daily-events-CAH", "daily-events-CARR", "daily-events-CASY", "daily-events-CAT", "daily-events-CB", "daily-events-CBOE", "daily-events-CBRE", "daily-events-CCI", "daily-events-CCL", "daily-events-CDNS", "daily-events-CDW", "daily-events-CE", "daily-events-CEG", "daily-events-CF", "daily-events-CFG", "daily-events-CHD", "daily-events-CHRW", "daily-events-CHTR", "daily-events-CI", "daily-events-CIEN", "daily-events-CINF", "daily-events-CL", "daily-events-CLX", "daily-events-CMCSA", "daily-events-CME", "daily-events-CMG", "daily-events-CMI", "daily-events-CMS", "daily-events-CNC", "daily-events-CNP", "daily-events-COF", "daily-events-COHR", "daily-events-COIN", "daily-events-COO", "daily-events-COP", "daily-events-COR", "daily-events-COST", "daily-events-COTY", "daily-events-CPAY", "daily-events-CPB", "daily-events-CPRI", "daily-events-CPRT", "daily-events-CPT", "daily-events-CRH", "daily-events-CRL", "daily-events-CRM", "daily-events-CRWD", "daily-events-CSCO", "daily-events-CSGP", "daily-events-CSX", "daily-events-CTAS", "daily-events-CTSH", "daily-events-CTVA", "daily-events-CVNA", "daily-events-CVS", "daily-events-CVX", "daily-events-CZR", "daily-events-D", "daily-events-DAL", "daily-events-DASH", "daily-events-DD", "daily-events-DDOG", "daily-events-DE", "daily-events-DECK", "daily-events-DELL", "daily-events-DG", "daily-events-DGX", "daily-events-DHI", "daily-events-DHR", "daily-events-DIS", "daily-events-DLR", "daily-events-DLTR", "daily-events-DOC", "daily-events-DOV", "daily-events-DOW", "daily-events-DPZ", "daily-events-DRI", "daily-events-DTE", "daily-events-DUK", "daily-events-DVA", "daily-events-DVN", "daily-events-DXC", "daily-events-DXCM", "daily-events-EBAY", "daily-events-ECHO", "daily-events-ECL", "daily-events-ED", "daily-events-EFX", "daily-events-EG", "daily-events-EIX", "daily-events-EL", "daily-events-ELV", "daily-events-EME", "daily-events-EMN", "daily-events-EMR", "daily-events-ENPH", "daily-events-EOG", "daily-events-EPAM", "daily-events-EQIX", "daily-events-EQT", "daily-events-ERIE", "daily-events-ES", "daily-events-ESS", "daily-events-ETN", "daily-events-ETR", "daily-events-ETSY", "daily-events-EVRG", "daily-events-EW", "daily-events-EXC", "daily-events-EXE", "daily-events-EXPD", "daily-events-EXPE", "daily-events-EXR", "daily-events-F", "daily-events-FANG", "daily-events-FAST", "daily-events-FB", "daily-events-FCX", "daily-events-FDS", "daily-events-FDX", "daily-events-FDXF", "daily-events-FE", "daily-events-FERG", "daily-events-FFIV", "daily-events-FICO", "daily-events-FIS", "daily-events-FISV", "daily-events-FITB", "daily-events-FIX", "daily-events-FLEX", "daily-events-FLR", "daily-events-FLS", "daily-events-FMC", "daily-events-FOX", "daily-events-FOXA", "daily-events-FRT", "daily-events-FSLR", "daily-events-FTI", "daily-events-FTNT", "daily-events-FTV", "daily-events-GD", "daily-events-GDDY", "daily-events-GE", "daily-events-GEHC", "daily-events-GEN", "daily-events-GEV", "daily-events-GILD", "daily-events-GIS", "daily-events-GL", "daily-events-GLW", "daily-events-GM", "daily-events-GNRC", "daily-events-GOOG", "daily-events-GOOGL", "daily-events-GPC", "daily-events-GPN", "daily-events-GRMN", "daily-events-GS", "daily-events-GT", "daily-events-GWW", "daily-events-HAL", "daily-events-HAS", "daily-events-HBAN", "daily-events-HCA", "daily-events-HD", "daily-events-HIG", "daily-events-HII", "daily-events-HLT", "daily-events-HOG", "daily-events-HON", "daily-events-HONA", "daily-events-HOOD", "daily-events-HP", "daily-events-HPE", "daily-events-HPQ", "daily-events-HRB", "daily-events-HRL", "daily-events-HSIC", "daily-events-HST", "daily-events-HSY", "daily-events-HUBB", "daily-events-HUM", "daily-events-HWM", "daily-events-IBKR", "daily-events-IBM", "daily-events-ICE", "daily-events-IDXX", "daily-events-IEX", "daily-events-IFF", "daily-events-ILMN", "daily-events-INCY", "daily-events-INFO", "daily-events-INTC", "daily-events-INTU", "daily-events-INVH", "daily-events-IP", "daily-events-IPGP", "daily-events-IQV", "daily-events-IR", "daily-events-IRM", "daily-events-ISRG", "daily-events-IT", "daily-events-ITW", "daily-events-IVZ", "daily-events-J", "daily-events-JBHT", "daily-events-JBL", "daily-events-JCI", "daily-events-JEF", "daily-events-JKHY", "daily-events-JNJ", "daily-events-JPM", "daily-events-KDP", "daily-events-KEY", "daily-events-KEYS", "daily-events-KHC", "daily-events-KIM", "daily-events-KKR", "daily-events-KLAC", "daily-events-KMB", "daily-events-KMI", "daily-events-KMX", "daily-events-KO", "daily-events-KR", "daily-events-KSS", "daily-events-KVUE", "daily-events-L", "daily-events-LB", "daily-events-LDOS", "daily-events-LEN", "daily-events-LH", "daily-events-LHX", "daily-events-LII", "daily-events-LIN", "daily-events-LITE", "daily-events-LKQ", "daily-events-LLY", "daily-events-LMT", "daily-events-LNC", "daily-events-LNT", "daily-events-LOW", "daily-events-LRCX", "daily-events-LULU", "daily-events-LUMN", "daily-events-LUV", "daily-events-LVS", "daily-events-LW", "daily-events-LYB", "daily-events-LYV", "daily-events-M", "daily-events-MA", "daily-events-MAA", "daily-events-MAC", "daily-events-MAR", "daily-events-MAS", "daily-events-MAT", "daily-events-MCD", "daily-events-MCHP", "daily-events-MCK", "daily-events-MCO", "daily-events-MDLZ", "daily-events-MDT", "daily-events-MET", "daily-events-META", "daily-events-MGM", "daily-events-MHK", "daily-events-MKC", "daily-events-MKTX", "daily-events-MLM", "daily-events-MMM", "daily-events-MNST", "daily-events-MO", "daily-events-MOH", "daily-events-MOS", "daily-events-MPC", "daily-events-MPWR", "daily-events-MRK", "daily-events-MRNA", "daily-events-MRSH", "daily-events-MRVL", "daily-events-MS", "daily-events-MSCI", "daily-events-MSFT", "daily-events-MSI", "daily-events-MTB", "daily-events-MTCH", "daily-events-MTD", "daily-events-MU", "daily-events-NCLH", "daily-events-NDAQ", "daily-events-NDSN", "daily-events-NEE", "daily-events-NEM", "daily-events-NFLX", "daily-events-NFX", "daily-events-NI", "daily-events-NKE", "daily-events-NKTR", "daily-events-NOC", "daily-events-NOV", "daily-events-NOW", "daily-events-NRG", "daily-events-NSC", "daily-events-NTAP", "daily-events-NTRS", "daily-events-NUE", "daily-events-NVDA", "daily-events-NVR", "daily-events-NWL", "daily-events-NWS", "daily-events-NWSA", "daily-events-NXPI", "daily-events-O", "daily-events-ODFL", "daily-events-OGN", "daily-events-OKE", "daily-events-OMC", "daily-events-ON", "daily-events-ORCL", "daily-events-ORLY", "daily-events-OTIS", "daily-events-OXY", "daily-events-PANW", "daily-events-PARA", "daily-events-PAYC", "daily-events-PAYX", "daily-events-PCAR", "daily-events-PCG", "daily-events-PEG", "daily-events-PENN", "daily-events-PEP", "daily-events-PFE", "daily-events-PFG", "daily-events-PG", "daily-events-PGR", "daily-events-PH", "daily-events-PHM", "daily-events-PKG", "daily-events-PLD", "daily-events-PLTR", "daily-events-PM", "daily-events-PNC", "daily-events-PNR", "daily-events-PNW", "daily-events-PODD", "daily-events-POOL", "daily-events-PPG", "daily-events-PPL", "daily-events-PRGO", "daily-events-PRU", "daily-events-PSA", "daily-events-PSKY", "daily-events-PSX", "daily-events-PTC", "daily-events-PVH", "daily-events-PWR", "daily-events-PYPL", "daily-events-Q", "daily-events-QCOM", "daily-events-RCL", "daily-events-RDDT", "daily-events-REG", "daily-events-REGN", "daily-events-RF", "daily-events-RHI", "daily-events-RJF", "daily-events-RL", "daily-events-RMD", "daily-events-ROK", "daily-events-ROL", "daily-events-ROP", "daily-events-ROST", "daily-events-RSG", "daily-events-RTX", "daily-events-RVTY", "daily-events-SBAC", "daily-events-SBNY", "daily-events-SBUX", "daily-events-SCHW", "daily-events-SEDG", "daily-events-SHW", "daily-events-SJM", "daily-events-SLB", "daily-events-SLG", "daily-events-SMCI", "daily-events-SNA", "daily-events-SNDK", "daily-events-SNPS", "daily-events-SO", "daily-events-SOLS", "daily-events-SOLV", "daily-events-SPG", "daily-events-SPGI", "daily-events-SRE", "daily-events-STE", "daily-events-STI", "daily-events-STLD", "daily-events-STT", "daily-events-STX", "daily-events-STZ", "daily-events-SW", "daily-events-SWK", "daily-events-SWKS", "daily-events-SYF", "daily-events-SYK", "daily-events-SYY", "daily-events-T", "daily-events-TAP", "daily-events-TDG", "daily-events-TDY", "daily-events-TECH", "daily-events-TEL", "daily-events-TER", "daily-events-TFC", "daily-events-TFX", "daily-events-TGT", "daily-events-TJX", "daily-events-TKO", "daily-events-TMO", "daily-events-TMUS", "daily-events-TPL", "daily-events-TPR", "daily-events-TRGP", "daily-events-TRIP", "daily-events-TRMB", "daily-events-TROW", "daily-events-TRV", "daily-events-TSCO", "daily-events-TSLA", "daily-events-TSN", "daily-events-TT", "daily-events-TTD", "daily-events-TTWO", "daily-events-TXN", "daily-events-TXT", "daily-events-TYL", "daily-events-UA", "daily-events-UAA", "daily-events-UAL", "daily-events-UBER", "daily-events-UDR", "daily-events-UHS", "daily-events-ULTA", "daily-events-UNH", "daily-events-UNM", "daily-events-UNP", "daily-events-UPS", "daily-events-URI", "daily-events-USB", "daily-events-V", "daily-events-VEEV", "daily-events-VFC", "daily-events-VICI", "daily-events-VLO", "daily-events-VLTO", "daily-events-VMC", "daily-events-VMRK", "daily-events-VNO", "daily-events-VNT", "daily-events-VRSK", "daily-events-VRSN", "daily-events-VRT", "daily-events-VRTX", "daily-events-VST", "daily-events-VTR", "daily-events-VTRS", "daily-events-VZ", "daily-events-WAB", "daily-events-WAT", "daily-events-WDAY", "daily-events-WDC", "daily-events-WEC", "daily-events-WELL", "daily-events-WFC", "daily-events-WHR", "daily-events-WM", "daily-events-WMB", "daily-events-WMT", "daily-events-WRB", "daily-events-WSM", "daily-events-WST", "daily-events-WTW", "daily-events-WU", "daily-events-WY", "daily-events-WYNN", "daily-events-XEL", "daily-events-XOM", "daily-events-XRAY", "daily-events-XRX", "daily-events-XYL", "daily-events-XYZ", "daily-events-YUM", "daily-events-ZBH", "daily-events-ZBRA", "daily-events-ZION", "daily-events-ZTS", "daily-history-A", "daily-history-AAL", "daily-history-AAP", "daily-history-AAPL", "daily-history-ABBV", "daily-history-ABNB", "daily-history-ABT", "daily-history-ACGL", "daily-history-ACN", "daily-history-ADBE", "daily-history-ADI", "daily-history-ADM", "daily-history-ADP", "daily-history-ADSK", "daily-history-AEE", "daily-history-AEP", "daily-history-AES", "daily-history-AFL", "daily-history-AIG", "daily-history-AIV", "daily-history-AIZ", "daily-history-AJG", "daily-history-AKAM", "daily-history-ALB", "daily-history-ALGN", "daily-history-ALK", "daily-history-ALL", "daily-history-ALLE", "daily-history-AMAT", "daily-history-AMCR", "daily-history-AMD", "daily-history-AME", "daily-history-AMG", "daily-history-AMGN", "daily-history-AMP", "daily-history-AMT", "daily-history-AMTM", "daily-history-AMZN", "daily-history-ANET", "daily-history-AON", "daily-history-AOS", "daily-history-APA", "daily-history-APC", "daily-history-APD", "daily-history-APH", "daily-history-APO", "daily-history-APP", "daily-history-APTV", "daily-history-ARE", "daily-history-ARES", "daily-history-ATO", "daily-history-AVGO", "daily-history-AVY", "daily-history-AWK", "daily-history-AXON", "daily-history-AXP", "daily-history-AZO", "daily-history-BA", "daily-history-BAC", "daily-history-BALL", "daily-history-BAX", "daily-history-BBT", "daily-history-BBWI", "daily-history-BBY", "daily-history-BDX", "daily-history-BEN", "daily-history-BF-B", "daily-history-BG", "daily-history-BHF", "daily-history-BIIB", "daily-history-BIO", "daily-history-BKNG", "daily-history-BKR", "daily-history-BLDR", "daily-history-BLK", "daily-history-BMY", "daily-history-BNY", "daily-history-BR", "daily-history-BRK-B", "daily-history-BRO", "daily-history-BSX", "daily-history-BWA", "daily-history-BX", "daily-history-BXP", "daily-history-C", "daily-history-CAG", "daily-history-CAH", "daily-history-CARR", "daily-history-CASY", "daily-history-CAT", "daily-history-CB", "daily-history-CBOE", "daily-history-CBRE", "daily-history-CCEP", "daily-history-CCI", "daily-history-CCL", "daily-history-CDNS", "daily-history-CDW", "daily-history-CE", "daily-history-CEG", "daily-history-CF", "daily-history-CFG", "daily-history-CHD", "daily-history-CHRW", "daily-history-CHTR", "daily-history-CI", "daily-history-CIEN", "daily-history-CINF", "daily-history-CL", "daily-history-CLX", "daily-history-CMCSA", "daily-history-CME", "daily-history-CMG", "daily-history-CMI", "daily-history-CMS", "daily-history-CNC", "daily-history-CNP", "daily-history-COF", "daily-history-COHR", "daily-history-COIN", "daily-history-COO", "daily-history-COP", "daily-history-COR", "daily-history-COST", "daily-history-COTY", "daily-history-CPAY", "daily-history-CPB", "daily-history-CPRI", "daily-history-CPRT", "daily-history-CPT", "daily-history-CRH", "daily-history-CRL", "daily-history-CRM", "daily-history-CRWD", "daily-history-CSCO", "daily-history-CSGP", "daily-history-CSX", "daily-history-CTAS", "daily-history-CTSH", "daily-history-CTVA", "daily-history-CVNA", "daily-history-CVS", "daily-history-CVX", "daily-history-CZR", "daily-history-D", "daily-history-DAL", "daily-history-DASH", "daily-history-DD", "daily-history-DDOG", "daily-history-DE", "daily-history-DECK", "daily-history-DELL", "daily-history-DG", "daily-history-DGX", "daily-history-DHI", "daily-history-DHR", "daily-history-DIS", "daily-history-DLR", "daily-history-DLTR", "daily-history-DOC", "daily-history-DOV", "daily-history-DOW", "daily-history-DPZ", "daily-history-DRI", "daily-history-DTE", "daily-history-DUK", "daily-history-DVA", "daily-history-DVN", "daily-history-DXC", "daily-history-DXCM", "daily-history-EBAY", "daily-history-ECHO", "daily-history-ECL", "daily-history-ED", "daily-history-EFX", "daily-history-EG", "daily-history-EIX", "daily-history-EL", "daily-history-ELV", "daily-history-EME", "daily-history-EMN", "daily-history-EMR", "daily-history-ENPH", "daily-history-EOG", "daily-history-EPAM", "daily-history-EQIX", "daily-history-EQT", "daily-history-ERIE", "daily-history-ES", "daily-history-ESS", "daily-history-ETN", "daily-history-ETR", "daily-history-ETSY", "daily-history-EVRG", "daily-history-EW", "daily-history-EXC", "daily-history-EXE", "daily-history-EXPD", "daily-history-EXPE", "daily-history-EXR", "daily-history-F", "daily-history-FANG", "daily-history-FAST", "daily-history-FB", "daily-history-FCPT", "daily-history-FCX", "daily-history-FDS", "daily-history-FDX", "daily-history-FDXF", "daily-history-FE", "daily-history-FERG", "daily-history-FFIV", "daily-history-FICO", "daily-history-FIS", "daily-history-FISV", "daily-history-FITB", "daily-history-FIX", "daily-history-FLEX", "daily-history-FLR", "daily-history-FLS", "daily-history-FMC", "daily-history-FOSL", "daily-history-FOX", "daily-history-FOXA", "daily-history-FRT", "daily-history-FSLR", "daily-history-FTI", "daily-history-FTNT", "daily-history-FTV", "daily-history-GD", "daily-history-GDDY", "daily-history-GE", "daily-history-GEHC", "daily-history-GEN", "daily-history-GEV", "daily-history-GILD", "daily-history-GIS", "daily-history-GL", "daily-history-GLW", "daily-history-GM", "daily-history-GNRC", "daily-history-GOOG", "daily-history-GOOGL", "daily-history-GPC", "daily-history-GPN", "daily-history-GRMN", "daily-history-GS", "daily-history-GT", "daily-history-GWW", "daily-history-HAL", "daily-history-HAS", "daily-history-HBAN", "daily-history-HCA", "daily-history-HD", "daily-history-HIG", "daily-history-HII", "daily-history-HLT", "daily-history-HOG", "daily-history-HON", "daily-history-HONA", "daily-history-HOOD", "daily-history-HP", "daily-history-HPE", "daily-history-HPQ", "daily-history-HRB", "daily-history-HRL", "daily-history-HSIC", "daily-history-HST", "daily-history-HSY", "daily-history-HUBB", "daily-history-HUM", "daily-history-HWM", "daily-history-IBKR", "daily-history-IBM", "daily-history-ICE", "daily-history-IDXX", "daily-history-IEX", "daily-history-IFF", "daily-history-ILMN", "daily-history-INCY", "daily-history-INFO", "daily-history-INTC", "daily-history-INTU", "daily-history-INVH", "daily-history-IP", "daily-history-IPGP", "daily-history-IQV", "daily-history-IR", "daily-history-IRM", "daily-history-ISRG", "daily-history-IT", "daily-history-ITW", "daily-history-IVZ", "daily-history-J", "daily-history-JBHT", "daily-history-JBL", "daily-history-JCI", "daily-history-JEF", "daily-history-JKHY", "daily-history-JNJ", "daily-history-JPM", "daily-history-KDP", "daily-history-KEY", "daily-history-KEYS", "daily-history-KHC", "daily-history-KIM", "daily-history-KKR", "daily-history-KLAC", "daily-history-KMB", "daily-history-KMI", "daily-history-KMX", "daily-history-KO", "daily-history-KR", "daily-history-KSS", "daily-history-KVUE", "daily-history-L", "daily-history-LB", "daily-history-LDOS", "daily-history-LEN", "daily-history-LH", "daily-history-LHX", "daily-history-LII", "daily-history-LIN", "daily-history-LITE", "daily-history-LKQ", "daily-history-LLY", "daily-history-LMT", "daily-history-LNC", "daily-history-LNT", "daily-history-LOW", "daily-history-LRCX", "daily-history-LULU", "daily-history-LUMN", "daily-history-LUV", "daily-history-LVS", "daily-history-LW", "daily-history-LYB", "daily-history-LYV", "daily-history-M", "daily-history-MA", "daily-history-MAA", "daily-history-MAC", "daily-history-MAR", "daily-history-MAS", "daily-history-MAT", "daily-history-MCD", "daily-history-MCHP", "daily-history-MCK", "daily-history-MCO", "daily-history-MDLZ", "daily-history-MDT", "daily-history-MET", "daily-history-META", "daily-history-MGM", "daily-history-MHK", "daily-history-MKC", "daily-history-MKTX", "daily-history-MLM", "daily-history-MMM", "daily-history-MNST", "daily-history-MO", "daily-history-MOH", "daily-history-MOS", "daily-history-MPC", "daily-history-MPWR", "daily-history-MRK", "daily-history-MRNA", "daily-history-MRSH", "daily-history-MRVL", "daily-history-MS", "daily-history-MSCI", "daily-history-MSFT", "daily-history-MSI", "daily-history-MTB", "daily-history-MTCH", "daily-history-MTD", "daily-history-MU", "daily-history-NAVI", "daily-history-NCLH", "daily-history-NDAQ", "daily-history-NDSN", "daily-history-NE", "daily-history-NEE", "daily-history-NEM", "daily-history-NFLX", "daily-history-NFX", "daily-history-NI", "daily-history-NKE", "daily-history-NKTR", "daily-history-NOC", "daily-history-NOV", "daily-history-NOW", "daily-history-NRG", "daily-history-NSC", "daily-history-NTAP", "daily-history-NTRS", "daily-history-NUE", "daily-history-NVDA", "daily-history-NVR", "daily-history-NWL", "daily-history-NWS", "daily-history-NWSA", "daily-history-NXPI", "daily-history-O", "daily-history-ODFL", "daily-history-OGN", "daily-history-OKE", "daily-history-OMC", "daily-history-ON", "daily-history-ORCL", "daily-history-ORLY", "daily-history-OTIS", "daily-history-OXY", "daily-history-PANW", "daily-history-PARA", "daily-history-PAYC", "daily-history-PAYX", "daily-history-PCAR", "daily-history-PCG", "daily-history-PEG", "daily-history-PENN", "daily-history-PEP", "daily-history-PFE", "daily-history-PFG", "daily-history-PG", "daily-history-PGR", "daily-history-PH", "daily-history-PHM", "daily-history-PKG", "daily-history-PLD", "daily-history-PLTR", "daily-history-PM", "daily-history-PNC", "daily-history-PNR", "daily-history-PNW", "daily-history-PODD", "daily-history-POOL", "daily-history-PPG", "daily-history-PPL", "daily-history-PRGO", "daily-history-PRU", "daily-history-PSA", "daily-history-PSKY", "daily-history-PSX", "daily-history-PTC", "daily-history-PVH", "daily-history-PWR", "daily-history-PYPL", "daily-history-Q", "daily-history-QCOM", "daily-history-RCL", "daily-history-RDDT", "daily-history-REG", "daily-history-REGN", "daily-history-RF", "daily-history-RHI", "daily-history-RJF", "daily-history-RL", "daily-history-RMD", "daily-history-ROK", "daily-history-ROL", "daily-history-ROP", "daily-history-ROST", "daily-history-RSG", "daily-history-RTX", "daily-history-RVTY", "daily-history-SBAC", "daily-history-SBNY", "daily-history-SBUX", "daily-history-SCHW", "daily-history-SEDG", "daily-history-SHW", "daily-history-SJM", "daily-history-SLB", "daily-history-SLG", "daily-history-SMCI", "daily-history-SNA", "daily-history-SNDK", "daily-history-SNPS", "daily-history-SO", "daily-history-SOLS", "daily-history-SOLV", "daily-history-SPG", "daily-history-SPGI", "daily-history-SPY", "daily-history-SRE", "daily-history-STE", "daily-history-STI", "daily-history-STLD", "daily-history-STT", "daily-history-STX", "daily-history-STZ", "daily-history-SW", "daily-history-SWK", "daily-history-SWKS", "daily-history-SYF", "daily-history-SYK", "daily-history-SYY", "daily-history-T", "daily-history-TAP", "daily-history-TDG", "daily-history-TDY", "daily-history-TECH", "daily-history-TEL", "daily-history-TER", "daily-history-TFC", "daily-history-TFX", "daily-history-TGT", "daily-history-TJX", "daily-history-TKO", "daily-history-TMO", "daily-history-TMUS", "daily-history-TPL", "daily-history-TPR", "daily-history-TRGP", "daily-history-TRIP", "daily-history-TRMB", "daily-history-TROW", "daily-history-TRV", "daily-history-TSCO", "daily-history-TSLA", "daily-history-TSN", "daily-history-TT", "daily-history-TTD", "daily-history-TTWO", "daily-history-TXN", "daily-history-TXT", "daily-history-TYL", "daily-history-UA", "daily-history-UAA", "daily-history-UAL", "daily-history-UBER", "daily-history-UDR", "daily-history-UHS", "daily-history-ULTA", "daily-history-UNH", "daily-history-UNM", "daily-history-UNP", "daily-history-UPS", "daily-history-URI", "daily-history-USB", "daily-history-V", "daily-history-VEEV", "daily-history-VFC", "daily-history-VIAV", "daily-history-VICI", "daily-history-VLO", "daily-history-VLTO", "daily-history-VMC", "daily-history-VMRK", "daily-history-VNO", "daily-history-VNT", "daily-history-VRSK", "daily-history-VRSN", "daily-history-VRT", "daily-history-VRTX", "daily-history-VST", "daily-history-VTR", "daily-history-VTRS", "daily-history-VZ", "daily-history-WAB", "daily-history-WAT", "daily-history-WDAY", "daily-history-WDC", "daily-history-WEC", "daily-history-WELL", "daily-history-WFC", "daily-history-WHR", "daily-history-WM", "daily-history-WMB", "daily-history-WMT", "daily-history-WRB", "daily-history-WSM", "daily-history-WST", "daily-history-WTW", "daily-history-WU", "daily-history-WY", "daily-history-WYNN", "daily-history-XEL", "daily-history-XOM", "daily-history-XRAY", "daily-history-XRX", "daily-history-XYL", "daily-history-XYZ", "daily-history-YUM", "daily-history-ZBH", "daily-history-ZBRA", "daily-history-ZION", "daily-history-ZTS", "finra-regsho-cnms-2018-08", "finra-regsho-cnms-2018-09", "finra-regsho-cnms-2018-10", "finra-regsho-cnms-2018-11", "finra-regsho-cnms-2018-12", "finra-regsho-cnms-2019-01", "finra-regsho-cnms-2019-02", "finra-regsho-cnms-2019-03", "finra-regsho-cnms-2019-04", "finra-regsho-cnms-2019-05", "finra-regsho-cnms-2019-06", "finra-regsho-cnms-2019-07", "finra-regsho-cnms-2019-08", "finra-regsho-cnms-2019-09", "finra-regsho-cnms-2019-10", "finra-regsho-cnms-2019-11", "finra-regsho-cnms-2019-12", "finra-regsho-cnms-2020-01", "finra-regsho-cnms-2020-02", "finra-regsho-cnms-2020-03", "finra-regsho-cnms-2020-04", "finra-regsho-cnms-2020-05", "finra-regsho-cnms-2020-06", "finra-regsho-cnms-2020-07", "finra-regsho-cnms-2020-08", "finra-regsho-cnms-2020-09", "finra-regsho-cnms-2020-10", "finra-regsho-cnms-2020-11", "finra-regsho-cnms-2020-12", "finra-regsho-cnms-2021-01", "finra-regsho-cnms-2021-02", "finra-regsho-cnms-2021-03", "finra-regsho-cnms-2021-04", "finra-regsho-cnms-2021-05", "finra-regsho-cnms-2021-06", "finra-regsho-cnms-2021-07", "finra-regsho-cnms-2021-08", "finra-regsho-cnms-2021-09", "finra-regsho-cnms-2021-10", "finra-regsho-cnms-2021-11", "finra-regsho-cnms-2021-12", "finra-regsho-cnms-2022-01", "finra-regsho-cnms-2022-02", "finra-regsho-cnms-2022-03", "finra-regsho-cnms-2022-04", "finra-regsho-cnms-2022-05", "finra-regsho-cnms-2022-06", "finra-regsho-cnms-2022-07", "finra-regsho-cnms-2022-08", "finra-regsho-cnms-2022-09", "finra-regsho-cnms-2022-10", "finra-regsho-cnms-2022-11", "finra-regsho-cnms-2022-12", "finra-regsho-cnms-2023-01", "finra-regsho-cnms-2023-02", "finra-regsho-cnms-2023-03", "finra-regsho-cnms-2023-04", "finra-regsho-cnms-2023-05", "finra-regsho-cnms-2023-06", "finra-regsho-cnms-2023-07", "finra-regsho-cnms-2023-08", "finra-regsho-cnms-2023-09", "finra-regsho-cnms-2023-10", "finra-regsho-cnms-2023-11", "finra-regsho-cnms-2023-12", "finra-regsho-cnms-2024-01", "finra-regsho-cnms-2024-02", "finra-regsho-cnms-2024-03", "finra-regsho-cnms-2024-04", "finra-regsho-cnms-2024-05", "finra-regsho-cnms-2024-06", "finra-regsho-cnms-2024-07", "finra-regsho-cnms-2024-08", "finra-regsho-cnms-2024-09", "finra-regsho-cnms-2024-10", "finra-regsho-cnms-2024-11", "finra-regsho-cnms-2024-12", "finra-regsho-cnms-2025-01", "finra-regsho-cnms-2025-02", "finra-regsho-cnms-2025-03", "finra-regsho-cnms-2025-04", "finra-regsho-cnms-2025-05", "finra-regsho-cnms-2025-06", "finra-regsho-cnms-2025-07", "finra-regsho-cnms-2025-08", "finra-regsho-cnms-2025-09", "finra-regsho-cnms-2025-10", "finra-regsho-cnms-2025-11", "finra-regsho-cnms-2025-12", "finra-regsho-cnms-2026-01", "finra-regsho-cnms-2026-02", "finra-regsho-cnms-2026-03", "finra-regsho-cnms-2026-04", "finra-regsho-cnms-2026-05", "finra-regsho-cnms-2026-06", "finra-regsho-cnms-2026-07", "finra-regsho-cnms-2026-08", "finra-regsho-cnms-2026-09", "finra-regsho-cnms-2026-10", "fja-sp500-components", "wikipedia-sp500-changes", "wikipedia-sp500-constituents"],
}


def _batch_null(name: str) -> str:
    """The null of the theory a batch or structure harness tests, as registered in its trial."""
    tid = BATCH_THEORY.get(name) or STRUCTURE_THEORY.get(name)
    reg = load_registry() if tid else None
    t = next((t for t in reg["theories"] if t["id"] == tid), None) if reg else None
    if t:
        return f"{tid}: {t['trial']['null']}" + ("; model-priced" if name in STRUCTURE_THEORY else "")
    return f"{tid}: mean P&L = 0 at the stated pricing; model-priced" if name in STRUCTURE_THEORY else "see the harness docstring"

def _bundles_matching(archive: Archive, pattern: str) -> list[str]:
    """INDEX entries matching the pattern. Listing is not availability: bundles kept off git have INDEX entries on every checkout."""
    names = sorted(e.name for e in archive.entries())
    return [n for n in names if n.startswith(pattern[:-1])] if pattern.endswith("*") else [n for n in names if n == pattern]


def _present(archive: Archive, pattern: str) -> list[str]:
    """INDEX entries matching the pattern whose file is on this machine."""
    return [n for n in _bundles_matching(archive, pattern) if archive._abs(archive.get(n).path).exists()]


def _missing_bundles(archive: Archive, needed: list[str]) -> list[str]:
    return [b for b in needed if not _present(archive, b)]


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
    "holdout_sharpe": harness_holdout_sharpe,
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
    "forward_variance_premium": harness_forward_variance, "term_vs_spot_premium": harness_term_vs_spot, "vvix_premium": harness_vvix,
    "vix9d_conditional": harness_vix9d, "vix_forward_contango": harness_vix_forward_contango, "vix_spike_forward": harness_vix_spike,
    "spx_box_lending": harness_box_lend, "spx_box_borrowing": harness_box_borrow, "parity_forward": harness_parity,
    "opex_pinning": harness_pinning, "btc_weekend_variance": harness_btc_weekend_var,
    **U2_HARNESSES,
    **OM2_HARNESSES,
    **XA_HARNESSES,
    **BATCH_HARNESSES,
    **{f"structure_{c.replace('-', '_').lower()}": _structure_harness(c) for c in STRUCTURE_IDS},
}
BUNDLES_NEEDED = {
    "market_calibration": ["polymarket-price-history-daily", "polymarket-closed-markets"],
    "multiscale_edge": ["polymarket-price-history-daily", "polymarket-closed-markets"],
    "bundle_arb_scan": ["polymarket-books-snapshot"],
    "multifractal_scaling": ["polymarket-price-history-daily"], "hurst_ci": ["polymarket-price-history-daily"],
    "markov_baseline": ["polymarket-price-history-daily"], "msm_volatility": ["polymarket-price-history-daily"],
    "dsr_pbo_harness": ["polymarket-price-history-daily"], "holdout_sharpe": ["polymarket-price-history-daily"], "controls": ["polymarket-price-history-daily", "polymarket-closed-markets"],
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
    "trend_rules": _dh(*TREND_ASSETS), "turn_of_month": ["daily-history-SPY"], "weekday_effect": ["daily-history-SPY"],
    "gold_silver_ratio": ["daily-history-GLD", "daily-history-SLV"], "crypto_weekend": ["daily-history-BTC-USD"],
    "forward_variance_premium": ["cboe-VIX-history", "cboe-VIX3M-history", "daily-history-SPY"], "term_vs_spot_premium": ["cboe-VIX-history", "cboe-VIX3M-history", "daily-history-SPY"],
    "vvix_premium": ["cboe-VVIX-history", "cboe-VIX-history"], "vix9d_conditional": ["cboe-VIX9D-history", "daily-history-SPY"],
    "vix_forward_contango": ["cboe-VIX-history", "cboe-VIX3M-history"], "vix_spike_forward": ["cboe-VIX-history", "cboe-VIX3M-history"],
    "spx_box_lending": ["options-chain-SPX-*", "fred-DTB3", "fred-DGS2"], "spx_box_borrowing": ["options-chain-SPX-*", "fred-DTB3", "fred-DGS2"],
    "parity_forward": ["options-chain-SPY-*", "fred-DTB3"], "opex_pinning": ["daily-history-SPY"], "btc_weekend_variance": ["daily-history-BTC-USD"],
    **U2_BUNDLES,
    **OM2_BUNDLES,
    **XA_BUNDLES,
    **BATCH_BUNDLES,
    **{f"structure_{c.replace('-', '_').lower()}": ["daily-history-SPY", "cboe-VIX-history", "fred-DTB3", "spy-smile-*"] for c in STRUCTURE_IDS},
}


def load_registry(path: Path = REGISTRY) -> Optional[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_registry(reg: dict, path: Path = REGISTRY) -> None:
    atomic_write_text(path, json.dumps(reg, indent=1, ensure_ascii=False))


# A theory whose registry `experiments` still names a harness that does not test its wording is scored by the harness that does.
# T-36's pass rule is the holdout Sharpe of the in-sample best rule, which dsr_pbo_harness (T-10's DSR/PBO rule) never computes.
# A no-op once registry.json maps T-36 to holdout_sharpe.
HARNESS_REMAP = {("T-36", "dsr_pbo_harness"): "holdout_sharpe"}
UPDATABLE = ("untested", "inconclusive", "supported", "not_supported")


def _experiments_of(t: dict) -> list[str]:
    return [HARNESS_REMAP.get((t["id"], h), h) for h in t.get("experiments", [])]


def _scored_theories(reg: Optional[dict]) -> dict[str, list[str]]:
    """harness -> ids of the theories its verdict scores. A superseded theory is not scored by a harness that is also mapped to its
    successor: that harness tests the restated wording, and the earlier wording's verdict stands. A superseded theory with a harness
    of its own (testing its own wording) is still scored by it."""
    if not reg:
        return {}
    exps = {t["id"]: _experiments_of(t) for t in reg["theories"]}
    successors: dict[str, list[str]] = {}
    for t in reg["theories"]:
        if t.get("supersedes"):
            successors.setdefault(t["supersedes"], []).append(t["id"])
    out: dict[str, list[str]] = {}
    for t in reg["theories"]:
        shared = {h for s in successors.get(t["id"], []) for h in exps.get(s, [])}
        for h in exps[t["id"]]:
            if h not in shared:
                out.setdefault(h, []).append(t["id"])
    return out


def _execute(name: str, fn: Callable, archive: Archive, ledger: Ledger) -> tuple[dict, int, str, str, bool]:
    """Run one harness: (stat, n, verdict, reason, no_data). no_data marks a result that must not move theory status: an input listed
    in the INDEX but not on this machine, or a harness reporting it has nothing on this machine to test."""
    try:
        stat, n, verdict, reason = fn(archive, ledger) if name == "controls" else fn(archive)
    except (MissingData, FileNotFoundError) as e:
        return {"missing": getattr(e, "names", [str(e)[:300]])}, 0, "inconclusive", f"missing data: {e}"[:500], True
    except Exception as e:  # a crashing harness is a recorded error, not a silent skip
        return {"error": repr(e)[:300]}, 0, "error", f"harness raised {type(e).__name__}", False
    return stat, n, verdict, reason, verdict == "inconclusive" and "on this machine" in str(reason)


def _apply_result(reg: Optional[dict], ids: list[str], res_id: str, verdict: str, no_data: bool) -> None:
    """Move the status of the scored theories to the verdict. A no-data result moves nothing (as for a missing bundle). An error never
    overwrites a verdict computed earlier; an untested theory becomes inconclusive."""
    if not reg or no_data:
        return
    ids = set(ids)
    for t in reg["theories"]:
        if t["id"] in ids and t.get("status") in UPDATABLE:
            if verdict != "error":
                t["status"] = verdict
            elif t["status"] == "untested":
                t["status"] = "inconclusive"
            t.setdefault("results", []).append(res_id)


def run_all(only: Optional[list[str]] = None, ledger: Optional[Ledger] = None, archive: Optional[Archive] = None,
            log: Optional[ExperimentLog] = None, registry_path: Path = REGISTRY) -> list[dict]:
    ledger = ledger if ledger is not None else Ledger()
    archive = archive if archive is not None else Archive(ledger=ledger)
    log = log if log is not None else ExperimentLog(ledger=ledger)
    reg = load_registry(registry_path)
    theories_by_h = _scored_theories(reg)
    out = []
    for name, fn in HARNESSES.items():
        if only and name not in only:
            continue
        t0 = time.time()
        needed = BUNDLES_NEEDED[name]
        missing = _missing_bundles(archive, needed)       # on disk, not merely listed in the INDEX
        if missing:
            res = log.record(name, theories_by_h.get(name, []), {}, _null_for(name), 0, "inconclusive", f"missing data bundles {missing}", data_bundles=needed)
            out.append(res.as_dict()); continue
        stat, n, verdict, reason, no_data = _execute(name, fn, archive, ledger)
        res = log.record(name, theories_by_h.get(name, []), stat, _null_for(name), n, verdict, reason, data_bundles=needed,
                         cost={"wall_seconds": round(time.time() - t0, 1)})
        out.append(res.as_dict())
        _apply_result(reg, theories_by_h.get(name, []), res.id, verdict, no_data)
    if reg:
        save_registry(reg, registry_path)
    return out


def _null_for(name: str) -> str:
    return {
        "market_calibration": "coin (p=0.5) Brier 0.25; skill vs coin must be > 0 at every horizon",
        "multiscale_edge": "mean(outcome - price) = 0 at every horizon (bootstrap 95% interval)",
        "bundle_arb_scan": "no after-fee long-bundle (YES ask + NO ask) mispricing in the snapshot; short side reported only",
        "multifractal_scaling": "shuffled increments (same marginal, no clustering): concavity q95 over 200 shuffles per series",
        "hurst_ci": "shuffled increments: H interval around 0.5 (200 shuffles per series); claim needs majority H < 0.5 and > 25% below the null",
        "markov_baseline": "base-rate predictor of the next move",
        "msm_volatility": "20-day rolling variance, out-of-sample Gaussian log score",
        "dsr_pbo_harness": "zero-skill best-of-N: DSR < 0.95 and PBO > 0.5 expected",
        "holdout_sharpe": "holdout Sharpe of the in-sample best rule = 0 (pass: <= 0)",
        "controls": "coin 0.25, oracle 0, market < coin on the same questions",
        "social_attention": "mentions permuted within ticker: Spearman rho with next-day |return| ~ 0",
        "fear_greed_contrarian": "Fear & Greed series circularly shifted against returns: conditional mean difference ~ 0",
        "longshot_bias": "calibrated bucket: mean(outcome - price) = 0 (event-clustered bootstrap 95% interval)",
        "horizon_monotone": "skill flat across horizons",
        "point_in_time_check": "naive and point-in-time runs give the same verdict (d_fear sign reported only)",
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
        "forward_variance_premium": "zero mean forward premium (block bootstrap per half, sign test)", "term_vs_spot_premium": "forward premium <= spot premium",
        "vvix_premium": "VVIX - realised VIX vol <= 10 or not increasing by quartile", "vix9d_conditional": "conditional near-term VRP >= 0",
        "vix_forward_contango": "VIX(t+21) >= F on average", "vix_spike_forward": "P(VIX(t+21) < F) = 0.5 after spikes",
        "spx_box_lending": "box lending spread over bills <= 0", "spx_box_borrowing": "short-box rate >= bill + 50 bp",
        "parity_forward": "parity deviations within the half-spread; implied rate = bill", "opex_pinning": "distance to nearest $1 uniform on opex and other days",
        "btc_weekend_variance": "weekend variance >= 3x weekday variance",
        **XA_NULLS,
    }.get(name, "see the harness docstring in mandel/experiments/underlying2.py (null stated per criterion)" if name in U2_HARNESSES
          else _batch_null(name) if name in BATCH_HARNESSES or name in STRUCTURE_THEORY else "n/a")
