"""
Crypto, metals, oil and bond options claims from the library, tested on archived index histories.
=================================================================================================

Model-free claims compare an implied-vol index (DVOL for BTC/ETH, GVZ for gold, OVX for oil, VXTLT for bonds, VIX for SPX)
with subsequently realised volatility of the matching ETF or coin. Model-priced claims reuse the structure engine with the
index as a flat implied vol (the claims say "flat IV", so no smile). Calendar conventions: equity ETFs use trading days and
252/yr; BTC/ETH use calendar days and 365/yr. Verdicts follow the shared rule in underlying2._verdict.
"""

from __future__ import annotations

import math

import numpy as np

from mandel.experiments.structures import run_structure
from mandel.experiments.underlying2 import _mdd, _mean_ci, _sharpe_diff_lower, _sr, _verdict
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio


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


def multi_asset_short_variance(legs: dict, n: int = 21, block: int = 3):
    """T-245: equal-vega short 21-day variance on SPX, GLD, USO, TLT (pnl_i = (K_i^2 - RV_i^2) / (2 K_i)) vs SPX alone:
    Sharpe difference > 0 with one-sided p < 0.05, positive in both halves. Non-overlapping 21-day cycles on common dates."""
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
    return {"n_cycles": int(len(port)), "sharpe_portfolio": _sr(port, 12), "sharpe_spx": _sr(spx, 12), "diff": obs, "lower": lo, "halves": halves, "verdict": v,
            "reason": f"equal-vega short variance on SPX/GLD/USO/TLT Sharpe {_sr(port,12):.2f} vs SPX alone {_sr(spx,12):.2f} over {len(port)} months since {common[0]} (diff {obs:+.2f}, one-sided lower {lo:+.2f}; halves {halves[0]:+.2f}/{halves[1]:+.2f}) — {why}"}


def ratio_extremes(a_days, a_closes, b_days, b_closes, ia: dict, ib: dict, n: int = 21, ppy: int = 252, window: int = 756, lo_q=0.10, hi_q=0.90, block=3, win_req=0.6, label="GVZ/VIX"):
    """T-247 / T-266 shape: after the implied ratio ia/ib leaves its trailing window's [lo_q, hi_q] band, s*[ln(RV_a/RV_b) - ln(ia/ib)]
    over the next n periods (s = +1 below the band, -1 above). Non-overlapping signals."""
    pa = {d: i for i, d in enumerate(a_days)}; pb = {d: i for i, d in enumerate(b_days)}
    common = [d for d in a_days if d in pb and d in ia and d in ib]
    ratio = np.log(np.array([ia[d] / ib[d] for d in common]))
    x = []
    t = window
    while t < len(common) - n:
        w = ratio[t - window:t]; lo = np.quantile(w, lo_q); hi = np.quantile(w, hi_q) if hi_q is not None else np.inf
        s = 1 if ratio[t] < lo else (-1 if ratio[t] > hi else 0)
        if s:
            d = common[t]; i, j = pa[d], pb[d]
            if i + n < len(a_closes) and j + n < len(b_closes):
                x.append(s * (math.log(_fwd_rv(a_closes, i, n, ppy) / _fwd_rv(b_closes, j, n, ppy)) - ratio[t])); t += n; continue
        t += 1
    x = np.array(x)
    if len(x) < 10:
        return {"n": len(x), "verdict": "inconclusive", "reason": f"{label}: only {len(x)} extreme signals"}
    lo, hi = _mean_ci(x, block); win = float((x > 0).mean())
    crit = [("mean > 0 with CI excluding 0", x.mean() > 0 and lo > 0)] + ([(f"win rate > {win_req}", win > win_req)] if win_req is not None else [])
    v, why = _verdict(crit)
    return {"n": int(len(x)), "mean": float(x.mean()), "ci": [lo, hi], "win_rate": win, "verdict": v,
            "reason": f"{label} extremes: {len(x)} signals, mean {x.mean():+.3f} log units (95% CI {lo:+.3f} to {hi:+.3f}), win rate {win:.2f} — {why}"}


def ratio_mean_reversion_signal(a_days, a_closes, b_days, b_closes, window: int = 1260, q: float = 0.90, horizon: int = 126, start: str = "2011-01-01"):
    """T-274: when GLD/SLV exceeds its trailing 5-year 90th percentile, the 180-calendar-day (~126 trading days) forward log change
    of the ratio is negative at 90% confidence with hit rate > 60%. Non-overlapping signals."""
    pb = {d: i for i, d in enumerate(b_days)}
    common = [d for d in a_days if d in pb]
    pa = {d: i for i, d in enumerate(a_days)}
    lr = np.log(np.array([a_closes[pa[d]] / b_closes[pb[d]] for d in common]))
    x, t = [], window
    while t < len(lr) - horizon:
        if common[t] >= start and lr[t] > np.quantile(lr[t - window:t], q):
            x.append(lr[t + horizon] - lr[t]); t += horizon
        else:
            t += 1
    x = np.array(x)
    if len(x) < 3:
        return {"n": len(x), "verdict": "inconclusive", "reason": f"only {len(x)} independent episodes"}
    rng = np.random.default_rng(0); bs = np.array([rng.choice(x, x.size).mean() for _ in range(4000)])
    upper90 = float(np.quantile(bs, 0.95)); hit = float((x < 0).mean())
    v, why = _verdict([("mean < 0 at 90% confidence", upper90 < 0), ("hit rate > 60%", hit > 0.6)])
    return {"n_signals": int(len(x)), "mean": float(x.mean()), "upper90": upper90, "hit_rate": hit, "verdict": v,
            "reason": f"GLD/SLV above its 5-year 90th percentile: {len(x)} independent episodes, 180-day change {x.mean():+.3f} (one-sided 90% upper {upper90:+.3f}), hit rate {hit:.2f} — {why}"}


def zscore_slope(days, a_idx: dict, b_idx: dict, window: int = 252, horizon: int = 20, start: str = "2010-01-01"):
    """T-514: OLS slope of the 20-day forward change in log(a/b) on its z-score vs the trailing 252-day mean; slope 95% CI < 0 in both
    halves. Non-overlapping 20-day samples."""
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
    return {"n": int(len(z)), "slopes": [s1, s2], "upper": [u1, u2], "verdict": v,
            "reason": f"GVZ/VIX 20-day reversion: slope on z-score {s1:+.4f} (upper {u1:+.4f}) and {s2:+.4f} (upper {u2:+.4f}) in the two halves, {len(z)} samples — {why}"}


# ------------------------------------------------------------ model-priced (flat index IV) --

def _cycles(days, closes, idx, rates, legs, dte, hold, start):
    return run_structure(days, closes, idx, rates, legs, dte, hold, ("flat", 1.0), None, start=start, q=0.0)


def covered_call_vs_hold(days, closes, idx, rates, delta, dte, hold, ppy_cycles, start, label, dsr_variants=(0.15, 0.25, 0.35)):
    """T-253 / T-270: monthly delta-d covered call (priced at the index as flat IV) vs holding: pooled Sharpe-difference 95% CI excludes 0,
    sign holds in both halves, DSR > 0 over the declared delta variants."""
    def run(d):
        res = _cycles(days, closes, idx, rates, [("underlying", "long", 1, None), ("call", "short", 1, ("delta", d))], dte, hold, start)
        return res["pnl"] / res["spot"]
    cc = run(delta)
    hold_res = _cycles(days, closes, idx, rates, [("underlying", "long", 1, None)], dte, hold, start)
    bh = hold_res["pnl"] / hold_res["spot"]
    obs, lo = _sharpe_diff_lower(cc, bh, ppy_cycles, 3, q=0.025); _, hi = _sharpe_diff_lower(cc, bh, ppy_cycles, 3, q=0.975)
    h = len(cc) // 2; halves = [_sr(cc[:h], ppy_cycles) - _sr(bh[:h], ppy_cycles), _sr(cc[h:], ppy_cycles) - _sr(bh[h:], ppy_cycles)]
    dsr = deflated_sharpe_ratio(cc - bh, n_trials=len(dsr_variants), trial_sharpes=[sharpe_ratio(run(d) - bh) for d in dsr_variants])
    v, why = _verdict([("Sharpe diff 95% CI excludes 0", lo > 0 or hi < 0), ("sign holds in both halves", np.sign(halves[0]) == np.sign(halves[1]) == np.sign(obs)), ("DSR > 0", dsr > 0)])
    if v == "supported" and obs < 0:
        v, why = "not_supported", "the CI excludes 0 on the negative side: the covered call has the LOWER Sharpe"
    return {"n_cycles": int(len(cc)), "sharpe_cc": _sr(cc, ppy_cycles), "sharpe_hold": _sr(bh, ppy_cycles), "diff": obs, "ci": [lo, hi], "halves": halves, "dsr": float(dsr), "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: {delta:.2f}-delta covered call Sharpe {_sr(cc,ppy_cycles):.2f} vs hold {_sr(bh,ppy_cycles):.2f} over {len(cc)} cycles (diff {obs:+.2f}, 95% CI {lo:+.2f} to {hi:+.2f}; halves {halves[0]:+.2f}/{halves[1]:+.2f}), DSR {dsr:.2f}, MDD {_mdd(cc)*100:.0f}% vs {_mdd(bh)*100:.0f}% — {why}"}


def short_put_mean(days, closes, idx, rates, delta, dte, hold, start, label):
    """T-254 / T-279: monthly delta-d short put at flat index IV, P&L = (premium - payoff)/K: 95% CI of the mean > 0, positive in both halves."""
    res = _cycles(days, closes, idx, rates, [("put", "short", 1, ("delta", delta))], dte, hold, start)
    K = np.array([k[0] for k in res["strikes"]])
    x = res["pnl"] / K
    lo, hi = _mean_ci(x, 3); h = len(x) // 2
    v, why = _verdict([("95% CI of the mean > 0", lo > 0), ("positive in both halves", x[:h].mean() > 0 and x[h:].mean() > 0)])
    return {"n_cycles": int(len(x)), "mean": float(x.mean()), "ci": [lo, hi], "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: {abs(delta):.2f}-delta short put mean {x.mean()*100:+.2f}% of strike per cycle over {len(x)} cycles (95% CI {lo*100:+.2f} to {hi*100:+.2f}), halves {x[:h].mean()*100:+.2f}/{x[h:].mean()*100:+.2f} — {why}"}


def conditional_straddle(days, closes, idx, rates, dte, hold, start, window, pct, label, report_conditional=True):
    """T-256 / T-272: ATM straddles bought when the index is below its trailing-window pct-percentile vs bought on all days (daily entries,
    hold to expiry): difference in mean return on premium with 95% CI > 0 (block = hold)."""
    d, c, iv = _align(days, closes, idx)
    lr = []
    T = dte / 365.0
    from mandel.options import bs
    rows = []
    for i in range(window, len(c) - hold):
        if d[i] < start:
            continue
        S, V = c[i], iv[i] / 100; r = math.log(1 + rates.get(d[i], rates[max(k for k in rates if k <= d[i])]) / 100)
        prem = float(bs.price(S, S, T, r, V, "call")) + float(bs.price(S, S, T, r, V, "put"))
        ret = (abs(c[i + hold] - S) - prem) / prem
        rows.append((ret, iv[i] < np.quantile(iv[i - window:i], pct)))
    x = np.array([r for r, _ in rows]); m = np.array([f for _, f in rows])
    diff_series = np.where(m, x, 0.0) / max(m.mean(), 1e-9) - x
    lo, hi = _mean_ci(diff_series, hold)
    dmean = float(x[m].mean() - x.mean())
    v, why = _verdict([("difference 95% CI > 0", lo > 0)])
    return {"n_entries": int(len(x)), "n_low": int(m.sum()), "mean_all": float(x.mean()), "mean_low": float(x[m].mean()), "diff": dmean, "ci": [lo, hi], "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: {dte}-day ATM straddles bought with {label} below its trailing {pct:.0%} quantile return {x[m].mean()*100:+.1f}% on premium vs {x.mean()*100:+.1f}% on all days ({int(m.sum())} of {len(x)} daily entries; diff 95% CI {lo*100:+.1f} to {hi*100:+.1f}, overlapping entries, block = holding period) — {why}"}


def protective_put_calmar(days, closes, idx, rates, start, label="DVOL"):
    """T-267: BTC with rolling 10-delta 90-day puts vs buy-and-hold: Calmar (CAGR / |MDD|) difference 95% CI > 0 and positive in >= 2 of 3 windows.
    Cycles of 90 calendar days, bootstrap over cycles (block 2)."""
    res = _cycles(days, closes, idx, rates, [("underlying", "long", 1, None), ("put", "long", 1, ("delta", -0.10))], 90, 90, start)
    hp = _cycles(days, closes, idx, rates, [("underlying", "long", 1, None)], 90, 90, start)
    a = res["pnl"] / (res["spot"] + res["debit"]); b = hp["pnl"] / hp["spot"]
    def calmar(x):
        cagr = np.prod(1 + x) ** (4 / len(x)) - 1; dd = abs(_mdd(x)); return cagr / dd if dd > 0 else float("nan")
    obs = calmar(a) - calmar(b)
    rng = np.random.default_rng(0); n = len(a); bs = []
    for _ in range(2000):
        i = ((rng.integers(0, n, math.ceil(n / 2))[:, None] + np.arange(2)[None, :]).ravel()[:n]) % n; bs.append(calmar(a[i]) - calmar(b[i]))
    lo = float(np.nanquantile(bs, 0.025))
    thirds = [calmar(x) - calmar(y) for x, y in zip(np.array_split(a, 3), np.array_split(b, 3))]
    v, why = _verdict([("Calmar difference 95% CI > 0", lo > 0), ("positive in >= 2 of 3 windows", sum(t > 0 for t in thirds) >= 2)])
    return {"n_cycles": int(n), "calmar_hedged": calmar(a), "calmar_hold": calmar(b), "diff": obs, "lower": lo, "thirds": thirds, "verdict": v,
            "reason": f"MODEL-PRICED at flat {label}: BTC + rolling 10-delta 90-day puts Calmar {calmar(a):.2f} vs hold {calmar(b):.2f} over {n} cycles (diff {obs:+.2f}, 95% lower {lo:+.2f}; thirds " + "/".join(f"{t:+.2f}" for t in thirds) + f") — {why}"}


def inverse_covered_call_btc(days, closes, idx, rates, start):
    """T-176: 25-delta 30-day BTC call written against 1 BTC, P&L in BTC = (premium_usd - payoff_usd)/S_T - 2 x 0.0003 BTC fee: 95% CI of the
    mean > 0. Black-76 at DVOL ~ BS with q = r (forward pricing); spot closes stand in for Deribit delivery prices (stated)."""
    res = _cycles(days, closes, idx, rates, [("call", "short", 1, ("delta", 0.25))], 30, 30, start)
    # payoff and premium are in USD per 1 BTC; convert the cycle P&L to BTC at the settlement price
    settle = np.array([closes[days.index(d) + 30] for d in res["day"]])
    x = res["pnl"] / settle - 0.0006
    lo, hi = _mean_ci(x, 3)
    v, why = _verdict([("95% CI of the mean > 0", lo > 0)])
    return {"n_cycles": int(len(x)), "mean_btc": float(x.mean()), "ci": [lo, hi], "verdict": v,
            "reason": f"MODEL-PRICED at flat DVOL: 25-delta 30-day BTC call against 1 BTC earns {x.mean():+.4f} BTC per cycle on average over {len(x)} cycles (95% CI {lo:+.4f} to {hi:+.4f}); spot closes stand in for Deribit delivery prices — {why}"}
