"""
Underlying-strategy harnesses on daily closes: declared rule searches with deflation, calendar effects,
ratio reversion and the crypto weekend effect.
=======================================================================================================

Every search is declared up front (the variant grid is the trial count), scored by the deflated Sharpe of
the best variant and the probability of backtest overfitting (CSCV) over the whole grid, so "best of N"
cannot pass by luck. Calendar and conditional-mean effects use block bootstraps or block shifts.
Costs: a round-trip cost in basis points is charged on every position change.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

import numpy as np

from mandel.experiments.overfit import pbo_cscv
from mandel.validation.backtest_eval import block_bootstrap_pvalue, deflated_sharpe_ratio, sharpe_ratio


def _ts(s) -> Optional[datetime]:
    try:
        t = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _series(rows: Iterable[dict], symbol: Optional[str] = None, cap: Optional[str] = None):
    """(days, closes) on the dividend-adjusted ``adjclose`` when a bar carries it (else ``close``), point in time: a bar
    is used only if its ``available_at`` is at or before the capture time ``cap`` (the bundle's created_at). Without
    ``cap`` (run._closes passes only the rows) the latest ``observed_at`` in the bundle stands in for it: the capture
    cannot precede the newest observation, so every kept bar was available at capture (at worst one bar that was in
    fact available is dropped)."""
    rows = list(rows)
    bound = _ts(cap) if cap is not None else max((t for t in (_ts(r.get("observed_at")) for r in rows if r.get("observed_at")) if t), default=None)
    d = {}
    for r in rows:
        v = r["value"]
        if symbol and v.get("symbol") != symbol:
            continue
        av = _ts(r.get("available_at")) if r.get("available_at") else None
        if bound is not None and av is not None and av > bound:
            continue
        c = v.get("adjclose") if v.get("adjclose") is not None else v["close"]
        d[datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")] = float(c)
    days = sorted(d)
    return days, np.array([d[k] for k in days])


def ma_rule_returns(closes: np.ndarray, lookback: int, cost_bps: float = 5.0) -> np.ndarray:
    """Long when close > its lookback-day moving average, else flat (cash earns 0 here). Daily simple returns,
    position decided at close t applied to t+1, costs on position changes."""
    r = closes[1:] / closes[:-1] - 1
    ma = np.convolve(closes, np.ones(lookback) / lookback, mode="valid")        # ma[i] = mean(closes[i..i+lb-1])
    pos = np.zeros(len(closes))
    pos[lookback - 1:] = (closes[lookback - 1:] > ma).astype(float)
    pos_prev = pos[:-1]                                                        # position held during day t+1 decided at t
    strat = pos_prev * r
    changes = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    return strat - changes * cost_bps / 1e4


def tsmom_returns(closes: np.ndarray, lookback: int, cost_bps: float = 5.0) -> np.ndarray:
    """Long when the trailing lookback-day return is positive, else flat."""
    r = closes[1:] / closes[:-1] - 1
    pos = np.zeros(len(closes))
    pos[lookback:] = (closes[lookback:] > closes[:-lookback]).astype(float)
    pos_prev = pos[:-1]
    changes = np.abs(np.diff(np.concatenate([[0.0], pos_prev])))
    return pos_prev * r - changes * cost_bps / 1e4


def _rule_matrix(closes: np.ndarray, rules: Sequence[tuple[str, int]], cost_bps: float):
    """(R: periods x variants after the longest warm-up, buy-and-hold returns on the same periods, variant names)."""
    r = closes[1:] / closes[:-1] - 1
    cols, names = [], []
    for kind, lb in rules:
        cols.append(ma_rule_returns(closes, lb, cost_bps) if kind == "ma" else tsmom_returns(closes, lb, cost_bps)); names.append(f"{kind}{lb}")
    warm = max(lb for _, lb in rules)
    return np.column_stack(cols)[warm:], r[warm:], names


def _sharpe_diff_test(a: np.ndarray, b: np.ndarray, ppy: int, block: int = 21, n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """Paired circular block bootstrap of the annualised Sharpe difference a - b (same resampling as
    underlying2._sharpe_diff_lower). Returns (observed difference, one-sided 5% lower bound, one-sided p), with
    p = share of resampled differences <= 0; p < 0.05 is the same decision as lower bound > 0."""
    rng = np.random.default_rng(seed); n = len(a); nb = math.ceil(n / block)
    obs = sharpe_ratio(a, ppy) - sharpe_ratio(b, ppy); out = np.empty(n_boot)
    for i in range(n_boot):
        idx = ((rng.integers(0, n, nb)[:, None] + np.arange(block)[None, :]).ravel()[:n]) % n
        out[i] = sharpe_ratio(a[idx], ppy) - sharpe_ratio(b[idx], ppy)
    return float(obs), float(np.quantile(out, 0.05)), float((np.sum(out <= 0) + 1) / (n_boot + 1))


def rule_search(closes: np.ndarray, rules: Sequence[tuple[str, int]], cost_bps: float = 5.0, periods_per_year: int = 252,
                n_trials: Optional[int] = None, trial_sharpes: Optional[Sequence[float]] = None, n_boot: int = 2000, block: int = 21) -> dict:
    """Declared grid of (kind, lookback) rules on one series. Reports every variant's Sharpe, the best variant's
    deflated Sharpe, PBO by CSCV, and the best variant's Sharpe vs buy-and-hold by a paired block bootstrap of the
    Sharpe difference (``p_best_vs_bh``). The DSR deflates by ``n_trials`` / ``trial_sharpes`` (per-period Sharpes) when
    given (trend_rules_multi passes the whole variants x assets grid), else by this series' grid alone."""
    R, bh, names = _rule_matrix(closes, rules, cost_bps)
    srs = np.array([sharpe_ratio(R[:, j], periods_per_year) for j in range(R.shape[1])])
    best = int(np.argmax(srs))
    if n_trials is None:
        n_trials, trial_sharpes = R.shape[1], [sharpe_ratio(R[:, j]) for j in range(R.shape[1])]
    dsr = deflated_sharpe_ratio(R[:, best], n_trials=n_trials, trial_sharpes=trial_sharpes)
    pbo = pbo_cscv(R, n_partitions=8)
    sd, sd_lo, p_vs_bh = _sharpe_diff_test(R[:, best], bh, periods_per_year, block, n_boot)
    return {"n_periods": int(R.shape[0]), "n_variants": int(R.shape[1]), "variants": dict(zip(names, [float(x) for x in srs])),
            "best": names[best], "best_sharpe": float(srs[best]), "buy_and_hold_sharpe": float(sharpe_ratio(bh, periods_per_year)),
            "best_cagr": float(np.prod(1 + R[:, best]) ** (periods_per_year / R.shape[0]) - 1), "bh_cagr": float(np.prod(1 + bh) ** (periods_per_year / len(bh)) - 1),
            "dsr_best": float(dsr), "dsr_n_trials": int(n_trials), "pbo": pbo["pbo"],
            "sharpe_diff_best_minus_bh": sd, "sharpe_diff_lower_5pct": sd_lo, "p_best_vs_bh": float(p_vs_bh),
            "p_best_vs_bh_test": f"one-sided paired circular block bootstrap (block {block}) of the annualised Sharpe difference"}


def trend_rules_multi(series: dict[str, np.ndarray], rules: Sequence[tuple[str, int]], cost_bps: float = 5.0, ppy: dict | None = None) -> dict:
    """Same declared grid on several assets; the trial count is variants x assets. Verdict (T-58): supported if, on a
    MAJORITY of assets, the best variant's Sharpe exceeds buy-and-hold's with a block-bootstrap p < 0.05 on the Sharpe
    difference and its deflated Sharpe > 0.95, deflated against the zero-skill best of all variants x assets trials
    (the variance of the trial Sharpes is taken over every per-period trial Sharpe in the grid). PBO is reported."""
    all_sr = [sharpe_ratio(R[:, j]) for R in (_rule_matrix(c, rules, cost_bps)[0] for c in series.values()) for j in range(R.shape[1])]
    n_trials = len(rules) * len(series)
    out, wins, dsrs, pbos = {}, 0, [], []
    for sym, closes in series.items():
        rep = rule_search(closes, rules, cost_bps, (ppy or {}).get(sym, 252), n_trials=n_trials, trial_sharpes=all_sr)
        out[sym] = rep
        wins += int(rep["best_sharpe"] > rep["buy_and_hold_sharpe"] and rep["p_best_vs_bh"] < 0.05 and rep["dsr_best"] > 0.95)
        dsrs.append(rep["dsr_best"]); pbos.append(rep["pbo"])
    n = len(series)
    return {"per_asset": out, "assets": n, "assets_where_best_beats_bh_after_deflation": wins, "median_dsr": float(np.median(dsrs)), "median_pbo": float(np.median(pbos)),
            "n_trials_total": n_trials, "verdict": "supported" if wins > n / 2 else "not_supported",
            "reason": f"{wins}/{n} assets where the best of {len(rules)} trend rules beats buy-and-hold on Sharpe (block-bootstrap p < 0.05) with DSR > 0.95 over {n_trials} trials (median DSR {np.median(dsrs):.2f}, median PBO {np.median(pbos):.2f}); "
                      + "; ".join(f"{s}: best {o['best']} SR {o['best_sharpe']:.2f} vs B&H {o['buy_and_hold_sharpe']:.2f} (p={o['p_best_vs_bh']:.3f}), DSR {o['dsr_best']:.2f}, PBO {o['pbo']:.2f}" for s, o in out.items())}


# ---------------------------------------------------------------- calendar effects --

def turn_of_month(days: list[str], closes: np.ndarray, before: int = 4, after: int = 3, n_boot: int = 2000) -> dict:
    """Mean daily return over the last `before` and first `after` trading days of each month vs all other days."""
    r = closes[1:] / closes[:-1] - 1
    months = [d[:7] for d in days[1:]]
    idx_in_month = {}
    for i, m in enumerate(months):
        idx_in_month.setdefault(m, []).append(i)
    tom = np.zeros(len(r), dtype=bool)
    for m, idxs in idx_in_month.items():
        for k in idxs[:after]:
            tom[k] = True
        for k in idxs[-before:]:
            tom[k] = True
    a, b = r[tom], r[~tom]
    if len(a) < 200 or len(b) < 200:
        return {"n": len(r), "verdict": "inconclusive", "reason": "too few days"}
    # paired test: strategy long only on TOM days vs long only on other days, scaled to equal day counts -> use mean difference bootstrap on daily series
    strat = np.where(tom, r, 0.0); other = np.where(~tom, r, 0.0) * (len(a) / len(b))
    p = block_bootstrap_pvalue(strat, other, n_boot=n_boot, block_len=21)
    half = len(r) // 2
    halves = [float(r[:half][tom[:half]].mean() - r[:half][~tom[:half]].mean()), float(r[half:][tom[half:]].mean() - r[half:][~tom[half:]].mean())]
    d = float(a.mean() - b.mean())
    ok = p < 0.05 and d > 0 and all(h > 0 for h in halves)
    return {"n": int(len(r)), "n_tom_days": int(tom.sum()), "mean_tom_bps": float(a.mean() * 1e4), "mean_other_bps": float(b.mean() * 1e4), "difference_bps": d * 1e4, "p_value": float(p), "halves_bps": [h * 1e4 for h in halves],
            "verdict": "supported" if ok else "not_supported",
            "reason": f"turn-of-month days {a.mean()*1e4:+.1f} bps/day vs others {b.mean()*1e4:+.1f} (diff {d*1e4:+.1f} bps, block-bootstrap p={p:.4f}, halves {halves[0]*1e4:+.1f}/{halves[1]*1e4:+.1f})"}


def weekday_effect(days: list[str], closes: np.ndarray, n_boot: int = 2000) -> dict:
    """Mean return by weekday (close-to-close ending on that weekday). Verdict: is any weekday's mean different
    from the rest at p < 0.05 after a Bonferroni correction over 7 (or 5) weekdays, with both halves agreeing."""
    r = closes[1:] / closes[:-1] - 1
    wd = np.array([datetime.strptime(d, "%Y-%m-%d").weekday() for d in days[1:]])
    present = sorted(set(wd.tolist()))
    res, best = {}, None
    half = len(r) // 2
    for w in present:
        m = wd == w
        if m.sum() < 100:
            continue
        strat = np.where(m, r, 0.0); other = np.where(~m, r, 0.0) * (m.sum() / (~m).sum())
        p_hi = block_bootstrap_pvalue(strat, other, n_boot=n_boot, block_len=10); p_lo = block_bootstrap_pvalue(other, strat, n_boot=n_boot, block_len=10, seed=1)
        d = float(r[m].mean() - r[~m].mean())
        hv = [float(r[:half][m[:half]].mean() - r[:half][~m[:half]].mean()), float(r[half:][m[half:]].mean() - r[half:][~m[half:]].mean())]
        res[w] = {"mean_bps": float(r[m].mean() * 1e4), "diff_bps": d * 1e4, "p_two_sided_bonf": float(min(1.0, 2 * min(p_hi, p_lo) * len(present))), "halves_agree": bool(np.sign(hv[0]) == np.sign(hv[1]) == np.sign(d)), "n": int(m.sum())}
        if best is None or res[w]["p_two_sided_bonf"] < res[best]["p_two_sided_bonf"]:
            best = w
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    ok = best is not None and res[best]["p_two_sided_bonf"] < 0.05 and res[best]["halves_agree"]
    return {"n": int(len(r)), "by_weekday": {names[w]: v for w, v in res.items()}, "strongest": names[best] if best is not None else None,
            "verdict": "supported" if ok else "not_supported",
            "reason": (f"strongest weekday {names[best]}: {res[best]['diff_bps']:+.1f} bps vs rest (Bonferroni p={res[best]['p_two_sided_bonf']:.3f}, halves agree {res[best]['halves_agree']})" if best is not None else "no weekday with 100+ observations")}


def ratio_reversion(days_a: list[str], a: np.ndarray, days_b: list[str], b: np.ndarray, lookback: int = 250, z_entry: float = 2.0, horizon: int = 21, n_boot: int = 2000, seed: int = 0) -> dict:
    """Log ratio a/b; z-score against its trailing lookback mean/sd; when |z| > z_entry, does the ratio move back
    toward the mean over `horizon` days? Statistic: mean of -sign(z) * (future change in log ratio) on signal
    days; null: z series circularly shifted against the future changes."""
    common = sorted(set(days_a) & set(days_b))
    ia = {d: i for i, d in enumerate(days_a)}; ib = {d: i for i, d in enumerate(days_b)}
    lr = np.array([math.log(a[ia[d]] / b[ib[d]]) for d in common])
    n = len(lr)
    if n < lookback + horizon + 500:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} common days"}
    z = np.full(n, np.nan)
    for i in range(lookback, n):
        w = lr[i - lookback:i]; sd = w.std()
        z[i] = (lr[i] - w.mean()) / sd if sd > 0 else 0.0
    fwd = np.full(n, np.nan); fwd[:-horizon] = lr[horizon:] - lr[:-horizon]
    valid = ~np.isnan(z) & ~np.isnan(fwd)
    zz, ff = z[valid], fwd[valid]
    def stat(zs):
        sig = np.abs(zs) > z_entry
        return float(np.mean(-np.sign(zs[sig]) * ff[sig])) if sig.sum() >= 30 else 0.0
    d = stat(zz)
    rng = np.random.default_rng(seed); null = np.empty(n_boot)
    for i in range(n_boot):
        null[i] = stat(np.roll(zz, int(rng.integers(horizon + 1, len(zz) - horizon - 1))))
    p = float((np.sum(null >= d) + 1) / (n_boot + 1))
    nsig = int((np.abs(zz) > z_entry).sum())
    half = len(zz) // 2
    def stat_on(lo, hi):
        zs, f = zz[lo:hi], ff[lo:hi]; sig = np.abs(zs) > z_entry
        return float(np.mean(-np.sign(zs[sig]) * f[sig])) if sig.sum() >= 15 else float("nan")
    halves = [stat_on(0, half), stat_on(half, len(zz))]
    # T-61 pass: mean > 0, p < 0.05, both halves > 0, >= 30 signals. A half with < 15 signals is not testable, so that
    # criterion is unimplemented (None) and the verdict caps at inconclusive instead of passing on the other half alone.
    from mandel.experiments.underlying2 import _verdict          # lazy: underlying2 imports this module
    untestable = any(math.isnan(h) for h in halves)
    if nsig < 30:
        verdict, why = "inconclusive", f"only {nsig} signals (< 30)"
    else:
        verdict, why = _verdict([("mean > 0", d > 0), ("block-shift p < 0.05", p < 0.05),
                                 ("both halves > 0" + (" (a half has < 15 signals)" if untestable else ""), None if untestable else all(h > 0 for h in halves)),
                                 (">= 30 signals", True)])
    return {"n": int(len(zz)), "n_signals": nsig, "lookback": lookback, "z_entry": z_entry, "horizon": horizon, "mean_reversion_log": d, "p_value": p, "halves": halves,
            "halves_testable": not untestable, "verdict": verdict,
            "reason": f"{nsig} signal days (|z|>{z_entry}); mean {horizon}d move back toward the mean {d:+.4f} log units (block-shift p={p:.3f}, halves {halves[0]:+.4f}/{halves[1]:+.4f}); {why}"}


def weekend_effect(days: list[str], closes: np.ndarray, n_boot: int = 2000) -> dict:
    """Crypto trades every day: are Saturday+Sunday close-to-close returns different from weekday returns?"""
    r = closes[1:] / closes[:-1] - 1
    wd = np.array([datetime.strptime(d, "%Y-%m-%d").weekday() for d in days[1:]])
    we = wd >= 5
    if we.sum() < 200:
        return {"n": len(r), "verdict": "inconclusive", "reason": "too few weekend days (not a 7-day series?)"}
    strat = np.where(we, r, 0.0); other = np.where(~we, r, 0.0) * (we.sum() / (~we).sum())
    p_hi = block_bootstrap_pvalue(strat, other, n_boot=n_boot, block_len=14); p_lo = block_bootstrap_pvalue(other, strat, n_boot=n_boot, block_len=14, seed=1)
    d = float(r[we].mean() - r[~we].mean()); p = float(min(1.0, 2 * min(p_hi, p_lo)))
    half = len(r) // 2
    halves = [float(r[:half][we[:half]].mean() - r[:half][~we[:half]].mean()), float(r[half:][we[half:]].mean() - r[half:][~we[half:]].mean())]
    vol_ratio = float(r[we].std() / r[~we].std())
    ok = p < 0.05 and np.sign(halves[0]) == np.sign(halves[1]) == np.sign(d)
    return {"n": int(len(r)), "n_weekend": int(we.sum()), "mean_weekend_bps": float(r[we].mean() * 1e4), "mean_weekday_bps": float(r[~we].mean() * 1e4), "diff_bps": d * 1e4, "p_two_sided": p, "halves_bps": [h * 1e4 for h in halves], "weekend_vol_ratio": vol_ratio,
            "verdict": "supported" if ok else "not_supported",
            "reason": f"weekend {r[we].mean()*1e4:+.1f} bps/day vs weekday {r[~we].mean()*1e4:+.1f} (diff {d*1e4:+.1f}, two-sided block-bootstrap p={p:.3f}, halves {halves[0]*1e4:+.1f}/{halves[1]*1e4:+.1f}); weekend vol is {vol_ratio:.2f}x weekday vol"}
