"""
Crypto, metals, oil and bond options claims from the library, tested on archived index histories.
=================================================================================================

Model-free claims compare an implied-vol index (DVOL for BTC/ETH, GVZ for gold, OVX for oil, VXTLT for bonds, VIX for SPX)
with subsequently realised volatility of the matching ETF or coin. Model-priced claims reuse the structure engine with the
index as a flat implied vol (the claims say "flat IV", so no smile). Calendar conventions: equity ETFs use trading days and
252/yr; BTC/ETH use calendar days and 365/yr. Verdicts follow the shared rule in underlying2._verdict. Below the trial's
min_n (in the claim's own units: non-overlapping signals, entries, episodes or cycles) a verdict is capped at inconclusive,
as in batch4_fomc.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from typing import Optional

import numpy as np

from mandel.experiments.structures import run_structure
from mandel.experiments.underlying2 import _mdd, _mean_ci, _sharpe_diff_lower, _sr, _verdict
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

# Per-trial settings for functions that run.py wires to two theories, keyed by (function, label). The values are the registry's
# min_n in each claim's own units (and T-266's level statistic). An explicit argument always wins over this table.
_TRIAL = {
    ("ratio_extremes", "GVZ/VIX"): {"min_n": 40, "statistic": "log"},          # T-247: non-overlapping 21-day signals
    ("ratio_extremes", "ETH/BTC DVOL"): {"min_n": 25, "statistic": "level"},   # T-266: mean of RV_ETH/RV_BTC - DVOL_ETH/DVOL_BTC
    ("conditional_straddle", "DVOL"): {"min_n": 25},                           # T-256: non-overlapping low-DVOL entries
    ("conditional_straddle", "GVZ"): {"min_n": 20},                            # T-272: non-overlapping low-GVZ entries
    ("covered_call_vs_hold", "DVOL"): {"min_n": 60},                           # T-253: monthly cycles
    ("covered_call_vs_hold", "GVZ"): {"min_n": 100},                           # T-270
    ("short_put_mean", "DVOL"): {"min_n": 60},                                 # T-254
    ("short_put_mean", "GVZ"): {"min_n": 100},                                 # T-279
}


def _trial(fn: str, label: str, key: str, given, default):
    return given if given is not None else _TRIAL.get((fn, label), {}).get(key, default)


def _cap_min_n(v: str, why: str, n: int, min_n: Optional[int], unit: str) -> tuple[str, str]:
    """Below the trial's min_n the verdict cannot be 'supported' or decided either way: inconclusive (batch4_fomc convention)."""
    if min_n and n < min_n:
        return "inconclusive", f"only {n} {unit}, below the trial's min_n {min_n}, so the verdict is capped at inconclusive (criteria: {v}, {why})"
    return v, why


def _asof(series: dict):
    """Point-in-time lookup: the value on day d, else the last value before d."""
    keys = sorted(series)
    def get(d):
        if d in series:
            return series[d]
        k = bisect_right(keys, d)
        if k == 0:
            raise KeyError(f"no value on or before {d}")
        return series[keys[k - 1]]
    return get


def _block_mean_draws(x: np.ndarray, block: int, n_boot: int = 2000, seed: int = 0) -> np.ndarray:
    """Circular block-bootstrap draws of the mean of x."""
    rng = np.random.default_rng(seed); n = len(x); b = max(1, min(int(block), n)); nb = math.ceil(n / b); m = np.empty(n_boot)
    for i in range(n_boot):
        m[i] = x[((rng.integers(0, n, nb)[:, None] + np.arange(b)[None, :]).ravel()[:n]) % n].mean()
    return m


def _align(days, closes, idx: dict):
    keep = [i for i, d in enumerate(days) if d in idx]
    return [days[i] for i in keep], closes[keep], np.array([idx[days[i]] for i in keep])


def _fwd_rv(closes, i, n, ppy):
    r = np.diff(np.log(closes[i:i + n + 1])); return float(np.sqrt(np.sum(r ** 2) * ppy / n))


def iv_minus_rv(days, closes, idx, n, ppy, units="vol", start=None):
    """Daily series of IV - forward realised over n periods; units 'vol' (vol points) or 'var' (annualised variance)."""
    d, c, iv = _align(days, closes, idx)
    out, ds = [], []
    for i in range(len(c) - n):
        if start and d[i] < start:
            continue
        rv = _fwd_rv(c, i, n, ppy)
        out.append((iv[i] - rv * 100) if units == "vol" else ((iv[i] / 100) ** 2 - rv ** 2)); ds.append(d[i])
    return ds, np.array(out)


def gap_test(days, closes, idx, n, ppy, threshold, units, block, thirds=False, start=None, label=""):
    ds, x = iv_minus_rv(days, closes, idx, n, ppy, units, start)
    lo, hi = _mean_ci(x, block)
    h = len(x) // 2; halves = [float(x[:h].mean()), float(x[h:].mean())]
    crit = [(f"lower 95% CI > {threshold}", lo > threshold)]
    if thirds:
        t3 = [float(z.mean()) for z in np.array_split(x, 3)]
        crit.append(("positive in >= 2 of 3 thirds", sum(z > 0 for z in t3) >= 2)); extra = f", thirds " + "/".join(f"{z:+.4f}" for z in t3)
    else:
        crit.append(("same sign in both halves", np.sign(halves[0]) == np.sign(halves[1]) == np.sign(x.mean()))); extra = f", halves {halves[0]:+.4f}/{halves[1]:+.4f}"
    v, why = _verdict(crit)
    unit = "vol pts" if units == "vol" else "variance"
    return {"n": int(len(x)), "first_day": ds[0], "mean": float(x.mean()), "ci": [lo, hi], "verdict": v,
            "reason": f"{label} implied minus realised over {n} periods: {x.mean():+.4f} {unit} since {ds[0]} (95% CI {lo:+.4f} to {hi:+.4f}){extra} — {why}"}


def multi_asset_short_variance(legs: dict, n: int = 21, block: int = 3, min_n: int = 180):
    """T-245: equal-vega short 21-day variance on SPX, GLD, USO, TLT (pnl_i = (K_i^2 - RV_i^2) / (2 K_i)) vs SPX alone:
    Sharpe difference > 0 with one-sided p < 0.05, positive in both halves. Non-overlapping 21-day cycles on common dates;
    fewer than min_n cycles caps the verdict at inconclusive."""
    common = sorted(set.intersection(*(set(d for d in v[0] if d in v[2]) for v in legs.values())))
    series = {}
    for k, (days, closes, idx) in legs.items():
        pos = {d: i for i, d in enumerate(days)}
        series[k] = (pos, closes, idx)
    port, spx = [], []
    for j in range(0, len(common) - n, n):
        d0 = common[j]; vals = {}
        ok = True
        for k, (pos, closes, idx) in series.items():
            i = pos[d0]
            if i + n >= len(closes):
                ok = False; break
            K = idx[d0] / 100; rv = _fwd_rv(closes, i, n, 252)
            vals[k] = (K ** 2 - rv ** 2) / (2 * K)
        if ok:
            port.append(np.mean(list(vals.values()))); spx.append(vals["SPX"])
    port, spx = np.array(port), np.array(spx)
    obs, lo = _sharpe_diff_lower(port, spx, 12, block, q=0.05)
    h = len(port) // 2
    halves = [_sr(port[:h], 12) - _sr(spx[:h], 12), _sr(port[h:], 12) - _sr(spx[h:], 12)]
    v, why = _verdict([("Sharpe diff > 0 with one-sided p < 0.05", obs > 0 and lo > 0), ("positive in both halves", all(x > 0 for x in halves))])
    v, why = _cap_min_n(v, why, len(port), min_n, "non-overlapping 21-day cycles")
    return {"n_cycles": int(len(port)), "sharpe_portfolio": _sr(port, 12), "sharpe_spx": _sr(spx, 12), "diff": obs, "lower": lo, "halves": halves, "verdict": v,
            "reason": f"equal-vega short variance on SPX/GLD/USO/TLT Sharpe {_sr(port,12):.2f} vs SPX alone {_sr(spx,12):.2f} over {len(port)} months since {common[0]} (diff {obs:+.2f}, one-sided lower {lo:+.2f}; halves {halves[0]:+.2f}/{halves[1]:+.2f}) — {why}"}


def ratio_extremes(a_days, a_closes, b_days, b_closes, ia: dict, ib: dict, n: int = 21, ppy: int = 252, window: int = 756, lo_q=0.10, hi_q=0.90, block=3, win_req=0.6, label="GVZ/VIX",
                   statistic: Optional[str] = None, min_n: Optional[int] = None):
    """T-247 / T-266 shape: after the implied ratio ia/ib leaves its trailing window's [lo_q, hi_q] band (s = +1 below the band, -1 above),
    the signed gap between the realised vol ratio over the next n periods and the entry implied ratio. statistic 'log' (T-247):
    s*[ln(RV_a/RV_b) - ln(ia/ib)]; 'level' (T-266): s*[RV_a/RV_b - ia/ib]. Non-overlapping signals. The unconditional mean of the same
    unsigned statistic over every post-warm-up day is reported for comparison. Fewer than min_n signals caps the verdict at inconclusive.
    statistic and min_n default to the _TRIAL entry for the label (else 'log' and 10)."""
    statistic = _trial("ratio_extremes", label, "statistic", statistic, "log")
    min_n = _trial("ratio_extremes", label, "min_n", min_n, 10)
    if statistic not in ("log", "level"):
        raise ValueError(f"statistic must be 'log' or 'level', got {statistic!r}")
    pa = {d: i for i, d in enumerate(a_days)}; pb = {d: i for i, d in enumerate(b_days)}
    common = [d for d in a_days if d in pb and d in ia and d in ib]
    ratio = np.log(np.array([ia[d] / ib[d] for d in common]))

    def gap(t):                                   # unsigned statistic at entry t, or None without a full forward window
        d = common[t]; i, j = pa[d], pb[d]
        if i + n >= len(a_closes) or j + n >= len(b_closes):
            return None
        rv = _fwd_rv(a_closes, i, n, ppy) / _fwd_rv(b_closes, j, n, ppy)
        return math.log(rv) - ratio[t] if statistic == "log" else rv - math.exp(ratio[t])

    x, sig_days = [], []
    t = window
    while t < len(common) - n:
        w = ratio[t - window:t]; lo = np.quantile(w, lo_q); hi = np.quantile(w, hi_q) if hi_q is not None else np.inf
        s = 1 if ratio[t] < lo else (-1 if ratio[t] > hi else 0)
        if s:
            g = gap(t)
            if g is not None:
                x.append(s * g); sig_days.append(common[t]); t += n; continue
        t += 1
    x = np.array(x)
    unc = [g for g in (gap(t) for t in range(window, len(common) - n)) if g is not None]
    unc_mean = float(np.mean(unc)) if unc else float("nan")
    units = "log units" if statistic == "log" else "ratio points"
    unc_txt = f"unconditional mean over all {len(unc)} post-warm-up days {unc_mean:+.3f}"
    if len(x) < 2:
        return {"n": len(x), "statistic": statistic, "min_n": min_n, "unconditional_mean": unc_mean, "signal_days": sig_days, "verdict": "inconclusive",
                "reason": f"{label}: only {len(x)} non-overlapping extreme signals (min_n {min_n}); {unc_txt}"}
    lo, hi = _mean_ci(x, block); win = float((x > 0).mean())
    crit = [("mean > 0 with CI excluding 0", x.mean() > 0 and lo > 0)] + ([(f"win rate > {win_req}", win > win_req)] if win_req is not None else [])
    v, why = _verdict(crit)
    v, why = _cap_min_n(v, why, len(x), min_n, "non-overlapping signals")
    return {"n": int(len(x)), "statistic": statistic, "min_n": min_n, "mean": float(x.mean()), "ci": [lo, hi], "win_rate": win, "unconditional_mean": unc_mean,
            "signal_days": sig_days, "verdict": v,
            "reason": f"{label} extremes: {len(x)} non-overlapping signals, mean {x.mean():+.3f} {units} (95% CI {lo:+.3f} to {hi:+.3f}), win rate {win:.2f}; {unc_txt} — {why}"}


def ratio_mean_reversion_signal(a_days, a_closes, b_days, b_closes, window: int = 1260, q: float = 0.90, horizon_days: int = 180, start: str = "2011-01-01",
                                min_n: int = 15):
    """T-274: when GLD/SLV exceeds its trailing 5-year (1260 trading days) 90th percentile, the 180-day forward log change of the ratio
    (to the first common trading day at or after entry + 180 calendar days) is negative at 90% confidence, judged one-sided by the
    bootstrap 0.90 quantile of the mean being < 0, with hit rate > 60%. Non-overlapping episodes; fewer than min_n caps at inconclusive."""
    pb = {d: i for i, d in enumerate(b_days)}
    common = [d for d in a_days if d in pb]
    pa = {d: i for i, d in enumerate(a_days)}
    lr = np.log(np.array([a_closes[pa[d]] / b_closes[pb[d]] for d in common]))
    x, eps, t = [], [], window
    while t < len(lr):
        if common[t] >= start and lr[t] > np.quantile(lr[t - window:t], q):
            j = bisect_left(common, (date.fromisoformat(common[t]) + timedelta(days=horizon_days)).isoformat())
            if j >= len(lr):
                break                                 # no full horizon left for this or any later signal
            x.append(lr[j] - lr[t]); eps.append((common[t], common[j])); t = j
        else:
            t += 1
    x = np.array(x)
    if len(x) < 3:
        return {"n": len(x), "n_signals": len(x), "episodes": eps, "verdict": "inconclusive", "reason": f"only {len(x)} independent episodes (min_n {min_n})"}
    rng = np.random.default_rng(0); bs = np.array([rng.choice(x, x.size).mean() for _ in range(4000)])
    upper90 = float(np.quantile(bs, 0.90)); hit = float((x < 0).mean())      # one-sided 90% upper bound of the mean
    v, why = _verdict([("mean < 0 at 90% confidence (one-sided)", upper90 < 0), ("hit rate > 60%", hit > 0.6)])
    v, why = _cap_min_n(v, why, len(x), min_n, "independent episodes")
    return {"n_signals": int(len(x)), "mean": float(x.mean()), "upper90": upper90, "hit_rate": hit, "changes": x.tolist(), "episodes": eps, "verdict": v,
            "reason": f"GLD/SLV above its 5-year 90th percentile: {len(x)} independent episodes, {horizon_days}-calendar-day change {x.mean():+.3f} (one-sided 90% upper {upper90:+.3f}), hit rate {hit:.2f} — {why}"}


def zscore_slope(days, a_idx: dict, b_idx: dict, window: int = 252, horizon: int = 20, start: str = "2010-01-01", min_n: int = 150):
    """T-514: OLS slope of the 20-day forward change in log(a/b) on its z-score vs the trailing 252-day mean; slope 95% CI < 0 in both
    halves. Non-overlapping 20-day samples; fewer than min_n samples caps the verdict at inconclusive."""
    common = [d for d in sorted(set(a_idx) & set(b_idx))]
    lr = np.log(np.array([a_idx[d] / b_idx[d] for d in common]))
    z, f, ds = [], [], []
    for t in range(window, len(lr) - horizon, horizon):
        if common[t] < start:
            continue
        w = lr[t - window:t]; sd = w.std()
        if sd > 0:
            z.append((lr[t] - w.mean()) / sd); f.append(lr[t + horizon] - lr[t]); ds.append(common[t])
    z, f = np.array(z), np.array(f)
    def slope_ci(zz, ff, seed=0):
        rng = np.random.default_rng(seed); n = len(zz); bs = []
        for _ in range(2000):
            i = rng.integers(0, n, n); bs.append(np.polyfit(zz[i], ff[i], 1)[0])
        return float(np.polyfit(zz, ff, 1)[0]), float(np.quantile(bs, 0.975))
    h = len(z) // 2
    s1, u1 = slope_ci(z[:h], f[:h]); s2, u2 = slope_ci(z[h:], f[h:], 1)
    v, why = _verdict([("first-half slope CI < 0", u1 < 0), ("second-half slope CI < 0", u2 < 0)])
    v, why = _cap_min_n(v, why, len(z), min_n, "non-overlapping 20-day samples")
    return {"n": int(len(z)), "slopes": [s1, s2], "upper": [u1, u2], "verdict": v,
            "reason": f"GVZ/VIX 20-day reversion: slope on z-score {s1:+.4f} (upper {u1:+.4f}) and {s2:+.4f} (upper {u2:+.4f}) in the two halves, {len(z)} samples — {why}"}


# ------------------------------------------------------------ model-priced (flat index IV) --

def _cycles(days, closes, idx, rates, legs, dte, hold, start):
    return run_structure(days, closes, idx, rates, legs, dte, hold, ("flat", 1.0), None, start=start, q=0.0)


def covered_call_vs_hold(days, closes, idx, rates, delta, dte, hold, ppy_cycles, start, label, dsr_variants=(0.15, 0.25, 0.35), min_n: Optional[int] = None):
    """T-253 / T-270: monthly delta-d covered call (priced at the index as flat IV) vs holding: pooled Sharpe-difference 95% CI excludes 0,
    sign holds in both halves, deflated Sharpe > 0 over the declared delta variants. deflated_sharpe_ratio returns a probability
    (PSR against the expected best-of-N zero-skill Sharpe SR*), so 'deflated Sharpe > 0' (SR_hat > SR*) is DSR probability > 0.5.
    Fewer than min_n cycles (default: the _TRIAL entry for the label) caps the verdict at inconclusive."""
    min_n = _trial("covered_call_vs_hold", label, "min_n", min_n, 0)
    def run(d):
        res = _cycles(days, closes, idx, rates, [("underlying", "long", 1, None), ("call", "short", 1, ("delta", d))], dte, hold, start)
        return res["pnl"] / res["spot"]
    cc = run(delta)
    hold_res = _cycles(days, closes, idx, rates, [("underlying", "long", 1, None)], dte, hold, start)
    bh = hold_res["pnl"] / hold_res["spot"]
    obs, lo = _sharpe_diff_lower(cc, bh, ppy_cycles, 3, q=0.025); _, hi = _sharpe_diff_lower(cc, bh, ppy_cycles, 3, q=0.975)
    h = len(cc) // 2; halves = [_sr(cc[:h], ppy_cycles) - _sr(bh[:h], ppy_cycles), _sr(cc[h:], ppy_cycles) - _sr(bh[h:], ppy_cycles)]
    dsr = deflated_sharpe_ratio(cc - bh, n_trials=len(dsr_variants), trial_sharpes=[sharpe_ratio(run(d) - bh) for d in dsr_variants])
    v, why = _verdict([("Sharpe diff 95% CI excludes 0", lo > 0 or hi < 0), ("sign holds in both halves", np.sign(halves[0]) == np.sign(halves[1]) == np.sign(obs)),
                       ("deflated Sharpe > 0 (DSR probability > 0.5)", dsr > 0.5)])
    if v == "supported" and obs < 0:
        v, why = "not_supported", "the CI excludes 0 on the negative side: the covered call has the LOWER Sharpe"
    v, why = _cap_min_n(v, why, len(cc), min_n, "cycles")
    return {"n_cycles": int(len(cc)), "sharpe_cc": _sr(cc, ppy_cycles), "sharpe_hold": _sr(bh, ppy_cycles), "diff": obs, "ci": [lo, hi], "halves": halves, "dsr": float(dsr), "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: {delta:.2f}-delta covered call Sharpe {_sr(cc,ppy_cycles):.2f} vs hold {_sr(bh,ppy_cycles):.2f} over {len(cc)} cycles (diff {obs:+.2f}, 95% CI {lo:+.2f} to {hi:+.2f}; halves {halves[0]:+.2f}/{halves[1]:+.2f}), DSR probability {dsr:.2f} (deflated Sharpe > 0 needs > 0.5), MDD {_mdd(cc)*100:.0f}% vs {_mdd(bh)*100:.0f}% — {why}"}


def short_put_mean(days, closes, idx, rates, delta, dte, hold, start, label, min_n: Optional[int] = None):
    """T-254 / T-279: monthly delta-d short put at flat index IV, P&L = (premium - payoff)/K: 95% CI of the mean > 0, positive in both halves.
    Fewer than min_n cycles (default: the _TRIAL entry for the label) caps the verdict at inconclusive."""
    min_n = _trial("short_put_mean", label, "min_n", min_n, 0)
    res = _cycles(days, closes, idx, rates, [("put", "short", 1, ("delta", delta))], dte, hold, start)
    K = np.array([k[0] for k in res["strikes"]])
    x = res["pnl"] / K
    lo, hi = _mean_ci(x, 3); h = len(x) // 2
    v, why = _verdict([("95% CI of the mean > 0", lo > 0), ("positive in both halves", x[:h].mean() > 0 and x[h:].mean() > 0)])
    v, why = _cap_min_n(v, why, len(x), min_n, "cycles")
    return {"n_cycles": int(len(x)), "mean": float(x.mean()), "ci": [lo, hi], "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: {abs(delta):.2f}-delta short put mean {x.mean()*100:+.2f}% of strike per cycle over {len(x)} cycles (95% CI {lo*100:+.2f} to {hi*100:+.2f}), halves {x[:h].mean()*100:+.2f}/{x[h:].mean()*100:+.2f} — {why}"}


def conditional_straddle(days, closes, idx, rates, dte, hold, start, window, pct, label, report_conditional=True, min_n: Optional[int] = None, block: int = 2):
    """T-256 / T-272: ATM straddles (BS at the index as flat IV, held `hold` periods to expiry) bought when the index is below its
    trailing-window pct-percentile vs bought on all days: conditional minus unconditional mean return on premium, 95% CI > 0.
    The conditional set is non-overlapping, as both trials specify: after a low-index entry the next `hold` days are skipped. The
    unconditional mean is over every daily entry. CI: paired circular block bootstrap of the difference on the daily timeline (blocks of
    `block` x `hold` rows, about `block` conditional entries each) of z = 1[entry] x / p - x, p = share of rows that are entries, whose
    mean is exactly mean_low - mean_all; both means move together in every draw, so their positive covariance is kept.
    n_entries counts the non-overlapping conditional entries (the trials' unit); fewer than min_n (default: the _TRIAL entry for the
    label) caps the verdict at inconclusive."""
    min_n = _trial("conditional_straddle", label, "min_n", min_n, 0)
    d, c, iv = _align(days, closes, idx)
    T = dte / 365.0
    from mandel.options import bs
    rate = _asof(rates)
    rows = []
    for i in range(window, len(c) - hold):
        if d[i] < start:
            continue
        S, V = c[i], iv[i] / 100; r = math.log(1 + rate(d[i]) / 100)
        prem = float(bs.price(S, S, T, r, V, "call")) + float(bs.price(S, S, T, r, V, "put"))
        ret = (abs(c[i + hold] - S) - prem) / prem
        rows.append((d[i], ret, bool(iv[i] < np.quantile(iv[i - window:i], pct))))
    x = np.array([r for _, r, _ in rows]); m = np.array([f for _, _, f in rows], dtype=bool)
    cond, k = [], 0
    while k < len(rows):                                  # greedy non-overlapping conditional entries
        if rows[k][2]:
            cond.append(k); k += hold
        else:
            k += 1
    nc = len(cond); entry_days = [rows[k][0] for k in cond]
    if nc < 2:
        return {"n_entries": nc, "n_days": int(len(x)), "n_low_days": int(m.sum()), "entry_days": entry_days, "min_n": min_n, "verdict": "inconclusive",
                "reason": f"MODEL-PRICED at flat {label}: only {nc} non-overlapping low-{label} entries (min_n {min_n})"}
    xc = x[cond]
    flag = np.zeros(len(x), bool); flag[cond] = True
    z = np.where(flag, x, 0.0) / flag.mean() - x                  # paired difference series: mean(z) == xc.mean() - x.mean()
    draws = _block_mean_draws(z, block * hold, seed=0)
    lo, hi = float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))
    dmean = float(xc.mean() - x.mean())
    v, why = _verdict([("difference 95% CI > 0", lo > 0)])
    v, why = _cap_min_n(v, why, nc, min_n, "non-overlapping conditional entries")
    return {"n_entries": nc, "n_days": int(len(x)), "n_low_days": int(m.sum()), "entry_days": entry_days, "mean_all": float(x.mean()), "mean_low": float(xc.mean()),
            "conditional_mean_positive": bool(xc.mean() > 0), "diff": dmean, "ci": [lo, hi], "min_n": min_n, "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: {dte}-day ATM straddles bought with {label} below its trailing {pct:.0%} quantile return {xc.mean()*100:+.1f}% on premium "
                      f"over {nc} non-overlapping entries (conditional mean {'>' if xc.mean() > 0 else '<='} 0) vs {x.mean()*100:+.1f}% on all {len(x)} daily entries "
                      f"(diff {dmean*100:+.1f}, 95% CI {lo*100:+.1f} to {hi*100:+.1f}; {int(m.sum())} low-{label} days in all) — {why}"}


def protective_put_calmar(days, closes, idx, rates, start, label="DVOL", dte: int = 90, roll: int = 30, delta: float = -0.10, block: int = 6,
                          ppy: int = 365, min_n: int = 20):
    """T-267: 1 BTC plus one 10-delta 90-DTE put (BS at the index as flat IV, q = 0), rolled monthly as the trial's procedure states: every
    `roll` days the held put (then dte - roll days to expiry) is sold at its BS mark and a new 90-DTE 10-delta put is bought; vs buy-and-hold.
    Both arms are marked daily (spot plus the put at BS with that day's index and bill rate), and Calmar = CAGR / |max drawdown of the daily
    path|. Pass: bootstrap 95% lower bound of the Calmar difference > 0 (circular blocks of `block` roll periods, each keeping its daily
    path) and positive in >= 2 of 3 windows. Fewer than min_n roll periods caps the verdict at inconclusive."""
    from mandel.options import bs
    vol, rate = _asof(idx), _asof(rates)
    i = next((k for k, d in enumerate(days) if d >= start and d in idx), len(days))
    GH, GB, cost, first = [], [], [], None
    while i + roll < len(days):
        d0 = days[i]; S0 = float(closes[i]); V0 = vol(d0) / 100; r0 = math.log(1 + rate(d0) / 100); first = first or d0
        K = bs.strike_for_delta(S0, dte / 365.0, r0, V0, delta, "put", 0.0); P0 = float(bs.price(S0, K, dte / 365.0, r0, V0, "put", 0.0))
        dk = days[i + 1:i + roll + 1]; Sk = np.asarray(closes[i + 1:i + roll + 1], dtype=float)
        tau = np.array([(dte - (date.fromisoformat(x) - date.fromisoformat(d0)).days) / 365.0 for x in dk])
        Pk = bs.price(Sk, K, tau, np.array([math.log(1 + rate(x) / 100) for x in dk]), np.array([vol(x) / 100 for x in dk]), "put", 0.0)
        GH.append((Sk + Pk) / (S0 + P0)); GB.append(Sk / S0); cost.append(P0 / S0); i += roll
    n = len(GH)
    if n < 3:
        return {"n_cycles": n, "verdict": "inconclusive", "reason": f"MODEL-PRICED at flat {label}: only {n} monthly roll periods (min_n {min_n})"}
    GH, GB = np.array(GH), np.array(GB)

    def path(G):                                      # daily equity path from per-period cumulative growth
        starts = np.concatenate([[1.0], np.cumprod(G[:, -1])[:-1]])
        return np.concatenate([[1.0], (starts[:, None] * G).ravel()])

    def mdd(G):
        e = path(G); return float((e / np.maximum.accumulate(e) - 1).min())

    def calmar(G):
        cagr = path(G)[-1] ** (ppy / (len(G) * roll)) - 1; dd = abs(mdd(G)); return cagr / dd if dd > 0 else float("nan")

    obs = calmar(GH) - calmar(GB)
    rng = np.random.default_rng(0); b = max(1, min(block, n)); draws = []
    for _ in range(2000):
        j = ((rng.integers(0, n, math.ceil(n / b))[:, None] + np.arange(b)[None, :]).ravel()[:n]) % n; draws.append(calmar(GH[j]) - calmar(GB[j]))
    lo = float(np.nanquantile(draws, 0.025))
    thirds = [calmar(GH[s]) - calmar(GB[s]) for s in np.array_split(np.arange(n), 3)]
    v, why = _verdict([("Calmar difference 95% CI > 0", lo > 0), ("positive in >= 2 of 3 windows", sum(t > 0 for t in thirds) >= 2)])
    v, why = _cap_min_n(v, why, n, min_n, "monthly roll periods")
    mh, mb = mdd(GH), mdd(GB); annual_cost = float(np.mean(cost) * ppy / roll)
    return {"n_cycles": int(n), "first_day": first, "calmar_hedged": calmar(GH), "calmar_hold": calmar(GB), "diff": obs, "lower": lo, "thirds": thirds,
            "mdd_hedged": mh, "mdd_hold": mb, "annual_premium": annual_cost, "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: BTC + 10-delta {dte}-DTE puts rolled every {roll} days Calmar {calmar(GH):.2f} vs hold {calmar(GB):.2f} over {n} roll periods "
                      f"since {first} (daily-path MDD {mh*100:.0f}% vs {mb*100:.0f}%, gross premium {annual_cost*100:.1f}% of spot a year; diff {obs:+.2f}, 95% lower {lo:+.2f}; thirds "
                      + "/".join(f"{t:+.2f}" for t in thirds) + f") — {why}"}


def delivery_prices(rows) -> dict:
    """{ISO date: Deribit 08:00 UTC delivery price} from deribit-delivery-prices-btc rows ({'value': {'date', 'delivery_price'}})."""
    out = {}
    for r in rows:
        v = r.get("value", r)
        if v.get("delivery_price"):
            out[v["date"]] = float(v["delivery_price"])
    return out


def inverse_covered_call_btc(days, closes, idx, rates, start, delivery: Optional[dict] = None, settle_offset_days: int = 31, min_n: int = 60):
    """T-176: 25-delta 30-day BTC call written against 1 BTC, the registry statistic in BTC: c - max(S_T - K, 0)/S_T - 2 x 0.0003 BTC fee,
    with c = USD premium / S_0 (the BTC received at inception). Pass: 95% CI of the mean > 0. Black-76 at DVOL on the forward
    F = S e^{rT} equals BS with q = 0, which _cycles uses. Settlement: `delivery` ({date: Deribit delivery price}, see delivery_prices)
    on entry date + settle_offset_days. The entry is the daily close (24:00 UTC), so the 30-day expiry falls at 00:00 UTC of day +31
    and the first 08:00 UTC delivery at or after it is on day +31. Cycles without a delivery price are dropped. Without `delivery`,
    spot closes on day +30 stand in and the claim's 'settlement at Deribit delivery prices' criterion is not implemented (None), so
    the verdict is at best inconclusive. Fewer than min_n cycles caps the verdict at inconclusive."""
    res = _cycles(days, closes, idx, rates, [("call", "short", 1, ("delta", 0.25))], 30, 30, start)
    K = np.array([s[0] for s in res["strikes"]])
    premium_btc = -res["debit"] / res["spot"]                     # c: BTC received at inception (debit < 0 for a short call)
    if delivery is not None:
        settle = np.array([delivery.get((date.fromisoformat(d) + timedelta(days=settle_offset_days)).isoformat(), np.nan) for d in res["day"]])
        src = f"Deribit delivery prices on day +{settle_offset_days}"
    else:
        settle = np.array([closes[days.index(d) + 30] for d in res["day"]], dtype=float)
        src = "spot closes on day +30 stand in for Deribit delivery prices"
    ok = np.isfinite(settle); dropped = int((~ok).sum())
    x = premium_btc[ok] - np.maximum(settle[ok] - K[ok], 0) / settle[ok] - 0.0006
    if len(x) < 2:
        return {"n_cycles": int(len(x)), "dropped": dropped, "verdict": "inconclusive", "reason": f"MODEL-PRICED at flat DVOL: only {len(x)} cycles settle on {src} (min_n {min_n})"}
    lo, hi = _mean_ci(x, 3)
    v, why = _verdict([("95% CI of the mean > 0", lo > 0), ("settled at Deribit delivery prices", True if delivery is not None else None)])
    v, why = _cap_min_n(v, why, len(x), min_n, "monthly cycles")
    return {"n_cycles": int(len(x)), "dropped": dropped, "mean_btc": float(x.mean()), "mean_premium_btc": float(premium_btc[ok].mean()), "ci": [lo, hi], "verdict": v,
            "reason": f"MODEL-PRICED at flat DVOL: 25-delta 30-day BTC call against 1 BTC earns {x.mean():+.4f} BTC per cycle on average (premium {premium_btc[ok].mean():.4f} BTC at S_0) "
                      f"over {len(x)} cycles (95% CI {lo:+.4f} to {hi:+.4f}); {src}" + (f", {dropped} cycles without one dropped" if dropped else "") + f" — {why}"}
