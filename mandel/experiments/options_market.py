"""
Options-library harnesses: term structure, vol-of-vol, VIX forwards, boxes, parity, pinning, BTC weekend variance.
================================================================================================================

Each function tests one library claim exactly as stated (theory ids in the docstrings). Where a claim has a
data part and a strategy-simulation part and only the data part is implemented, the harness can return
``not_supported`` (the data part fails, so the claim fails) but never ``supported``: a passing data part
returns ``inconclusive`` with the reason. Market-priced harnesses read the raw daily CBOE chain bundles,
which live on the capturing machine's disk; elsewhere they report the missing bundles.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

import numpy as np

from mandel.experiments.underlying2 import _verdict
from mandel.experiments.volatility import index_closes, price_closes
from mandel.validation.backtest_eval import block_bootstrap_pvalue


# ----------------------------------------------------------------------- helpers --

def _binom_two_sided_ci(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Clopper-Pearson interval by bisection on the exact binomial tails (no scipy)."""
    def cdf(x, p):            # P(X <= x)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, x + 1))
    def solve(f, lo=0.0, hi=1.0):
        for _ in range(60):
            mid = (lo + hi) / 2
            if f(mid):
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: 1 - cdf(k - 1, p) >= alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: cdf(k, p) <= alpha / 2)
    return lower, upper


def _sign_test_p(k: int, n: int) -> float:
    """One-sided P(X >= k) under p=0.5."""
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n if n else 1.0


def _one_sided_p_mean_positive(x: np.ndarray, block_len: int, seed: int = 0) -> float:
    return block_bootstrap_pvalue(x, np.zeros_like(x), n_boot=2000, block_len=block_len, seed=seed)


def _aligned_index_and_price(index_rows_list: list[Iterable[dict]], price_rows: Iterable[dict], symbol: str):
    idx = [index_closes(r) for r in index_rows_list]
    px = price_closes(price_rows, symbol)
    days = sorted(d for d in px if all(d in i for i in idx))
    return days, [np.array([i[d] for d in days]) for i in idx], np.array([px[d] for d in days])


def _rv_annual(r: np.ndarray, start: int, end: int, ppy: int = 252) -> float:
    """Annualised realised variance of returns r[start:end]."""
    seg = r[start:end]
    return float(np.sum(seg ** 2) * ppy / len(seg))


# ------------------------------------------------------------------ FRED rates --

def _bill_obs(series: dict, day: str) -> tuple[str, float]:
    """Latest FRED observation dated strictly BEFORE the capture day. A FRED row for day D is published about 20:00 UTC on D, while the
    chain captures (07:00-11:30 UTC) carry the previous session's quotes, so a same-day row would be look-ahead and would make a re-run
    differ from the recorded day-one statistic."""
    prior = [d for d in series if d < day]
    if not prior:
        raise ValueError(f"no FRED observation dated before capture day {day}")
    d = max(prior)
    return d, float(series[d])


def _dtb3_cont(pct: float) -> float:
    """FRED DTB3 is a discount-basis yield on a 91-day bill: price = 1 - d*91/360, continuous rate = -ln(price) / (91/365)."""
    return -math.log(1 - pct / 100 * 91 / 360) / (91 / 365)


def _semiannual_cont(pct: float) -> float:
    """FRED DGS2 is a bond-equivalent (semiannually compounded) yield: continuous rate = 2 ln(1 + y/2)."""
    return 2 * math.log(1 + pct / 200)


def _bill_used(dtb3: dict, day: str) -> dict:
    """The 3-month bill a capture day is compared with, recorded in each day's output so a re-run reproduces it."""
    d, v = _bill_obs(dtb3, day)
    return {"bill_day": d, "dtb3_discount_pct": v, "bill_cont_bp": _dtb3_cont(v) * 1e4}


# ------------------------------------------------------------- forward variance --

def forward_variance_premium(vix_rows, vix3m_rows, spy_rows) -> dict:
    """T-148: FV = (93*VIX3M^2 - 30*VIX^2)/63 exceeds realised SPY variance over trading days 21..63 after entry;
    pass: mean gap > 1 vol point, block-bootstrap CI excludes 0 in both halves, sign test p < 0.05 on non-overlapping windows."""
    days, (vix, v3), S = _aligned_index_and_price([vix_rows, vix3m_rows], spy_rows, "SPY")
    r = np.diff(np.log(S))
    n = len(r) - 63
    fv = (93 * (v3 / 100) ** 2 - 30 * (vix / 100) ** 2) / 63
    gaps = []
    for t in range(n):
        if fv[t] <= 0:
            continue
        rv = _rv_annual(r, t + 21, t + 63)
        gaps.append((t, math.sqrt(fv[t]) * 100 - math.sqrt(rv) * 100))
    idx = np.array([g[0] for g in gaps]); g = np.array([g[1] for g in gaps])
    half = len(g) // 2
    p1 = _one_sided_p_mean_positive(g[:half], 63); p2 = _one_sided_p_mean_positive(g[half:], 63, 1)
    non = g[::63]; k = int((non > 0).sum()); p_sign = _sign_test_p(k, len(non))
    ok = g.mean() > 1.0 and p1 < 0.025 and p2 < 0.025 and p_sign < 0.05
    return {"n": int(len(g)), "first_day": days[0], "mean_gap_vol_pts": float(g.mean()), "share_positive": float((g > 0).mean()),
            "halves": [float(g[:half].mean()), float(g[half:].mean())], "p_halves": [p1, p2], "nonoverlap_n": len(non), "nonoverlap_positive": k, "p_sign": p_sign,
            "verdict": "supported" if ok else "not_supported",
            "reason": f"forward vol (VIX/VIX3M, days 21-63) exceeds realised by {g.mean():+.2f} vol pts on average ({(g > 0).mean()*100:.0f}% of {len(g)} days since {days[0]}); halves {g[:half].mean():+.2f}/{g[half:].mean():+.2f} (p {p1:.3f}/{p2:.3f}); sign test {k}/{len(non)} p={p_sign:.4f}"}


T231_MIN_CYCLES = 70        # T-231 trial.min_n, in non-overlapping 63-day cycles


def _significantly_negative(x: np.ndarray) -> bool:
    """Mean of x below 0 with the 95% CI wholly below 0: the mirror one-sided test (H0: mean >= 0) rejects at 2.5%, by the same studentized
    block bootstrap as the pass-side test. Under 8 points no bootstrap runs, so nothing can be shown and the answer is False."""
    return len(x) >= 8 and float(x.mean()) < 0 and block_bootstrap_pvalue(-x, np.zeros_like(x), n_boot=2000, block_len=2) < 0.025


def term_vs_spot_premium(vix_rows, vix3m_rows, spy_rows) -> dict:
    """T-231: (F^2 - RV[22..63]) - (VIX^2 - RV[1..21]) > 0 with F^2 = (3*VIX3M^2 - VIX^2)/2; conditional forward premium
    (VIX3M/VIX > 1.10) positive in both halves. Non-overlapping 63-day cycles.
    Below trial.min_n (70 cycles) the verdict cannot be supported, and a failing criterion decides only when it fails decisively: the main
    premium's 95% CI lies wholly at or below 0, or a conditional half's mean is significantly negative. A non-significant shortfall there,
    or a sample under 8 cycles (no bootstrap), is inconclusive."""
    days, (vix, v3), S = _aligned_index_and_price([vix_rows, vix3m_rows], spy_rows, "SPY")
    r = np.diff(np.log(S))
    d, cond, ts = [], [], []
    for t in range(0, len(r) - 63, 63):
        f2 = (3 * (v3[t] / 100) ** 2 - (vix[t] / 100) ** 2) / 2
        fwd = f2 - _rv_annual(r, t + 21, t + 63); spot = (vix[t] / 100) ** 2 - _rv_annual(r, t, t + 21)
        d.append(fwd - spot); ts.append(t)
        if v3[t] / vix[t] > 1.10:
            cond.append(fwd)
    d = np.array(d, dtype=float); cond = np.array(cond, dtype=float)
    mean = float(d.mean()) if len(d) else float("nan")
    p = block_bootstrap_pvalue(d, np.zeros_like(d), n_boot=2000, block_len=2) if len(d) >= 8 else None   # under 8 cycles: no test, never a decision
    h = len(cond) // 2
    parts = [cond[:h], cond[h:]]
    halves = [float(x.mean()) if len(x) else float("nan") for x in parts]
    full = len(d) >= T231_MIN_CYCLES
    # (name, passes, fails decisively: the failure stands below trial.min_n because its interval lies wholly on the wrong side)
    rows = [("forward premium > spot premium, 95% CI excluding 0", p is not None and mean > 0 and p < 0.025, _significantly_negative(d)),
            ("conditional (VIX3M/VIX > 1.10) forward premium positive in both halves", all(x > 0 for x in halves), any(_significantly_negative(x) for x in parts))]
    criteria = [(name, bool(ok)) if (full or ok or decisive) else (name + " (fails, not decisively, below min_n: undecided)", None)
                for name, ok, decisive in rows]
    criteria.append((f"sample reaches trial min_n {T231_MIN_CYCLES} cycles ({len(d)} so far)", True if full else None))
    verdict, why = _verdict(criteria)
    return {"n_cycles": int(len(d)), "min_n": T231_MIN_CYCLES, "mean_term_minus_spot_var": mean, "p_value": p, "n_conditional": int(len(cond)),
            "conditional_forward_premium_halves": halves, "criteria": [[c, ok] for c, ok in criteria], "verdict": verdict,
            "reason": f"forward premium minus spot premium {mean:+.4f} (variance units) over {len(d)} non-overlapping 63d cycles, "
                      + (f"p={p:.3f}" if p is not None else "p n/a (under 8 cycles)")
                      + f"; conditional (VIX3M/VIX>1.10, n={len(cond)}) forward premium halves {halves[0]:+.4f}/{halves[1]:+.4f}; verdict: {why}"}



# ------------------------------------------------------------------- vol of vol --

def vvix_premium(vvix_rows, vix_rows) -> dict:
    """T-243 (data part): VVIX - realised vol of VIX over the next 21 days > 10 pts with 99% CI excluding 0, quartile
    means increasing in VVIX. The strangle simulation is not implemented, so a pass is reported inconclusive."""
    vv = index_closes(vvix_rows); vx = index_closes(vix_rows)
    days = sorted(d for d in vv if d in vx)
    VV = np.array([vv[d] for d in days]); VX = np.array([vx[d] for d in days])
    lr = np.diff(np.log(VX))
    gaps, lvl = [], []
    for t in range(len(lr) - 21):
        rv = float(np.std(lr[t:t + 21], ddof=1) * math.sqrt(252) * 100)
        gaps.append(VV[t] - rv); lvl.append(VV[t])
    g = np.array(gaps); L = np.array(lvl)
    p = _one_sided_p_mean_positive(g - 10.0, 42)
    qs = np.quantile(L, [0.25, 0.5, 0.75]); qi = np.searchsorted(qs, L)
    qmeans = [float(g[qi == i].mean()) for i in range(4)]
    mono = all(qmeans[i] < qmeans[i + 1] for i in range(3))
    data_ok = g.mean() > 10 and p < 0.005 and mono
    return {"n": int(len(g)), "first_day": days[0], "mean_gap": float(g.mean()), "p_gap_above_10": p, "quartile_means": qmeans, "monotone": mono,
            "verdict": "inconclusive" if data_ok else "not_supported",
            "reason": (f"VVIX exceeds realised VIX vol by {g.mean():.1f} pts on average over {len(g)} days (p for gap > 10: {p:.4f}); quartile gaps " + "/".join(f"{x:.1f}" for x in qmeans)
                       + (" increasing" if mono else " NOT monotone") + ("; data part passes, strangle simulation not implemented" if data_ok else "")
                       + "; note: VVIX is the implied vol of VIX futures, which move less than spot VIX, so comparing it with spot-VIX realised vol (as the claim does) understates any vol-of-vol premium")}


def short_horizon_conditional(vix9d_rows, spy_rows) -> dict:
    """T-232 (data part): when VIX9D < trailing 10-day realised SPY vol, next-9-day RV^2 - VIX9D^2 > 0 with CI excluding 0.
    Non-overlapping 9-day cycles. Simulation part not implemented (pass -> inconclusive)."""
    days, (v9,), S = _aligned_index_and_price([vix9d_rows], spy_rows, "SPY")
    r = np.diff(np.log(S))
    d = []
    t = 10
    while t + 9 <= len(r):
        trailing = math.sqrt(_rv_annual(r, t - 10, t)) * 100
        if v9[t] < trailing:
            d.append(_rv_annual(r, t, t + 9) - (v9[t] / 100) ** 2); t += 9
        else:
            t += 1
    d = np.array(d)
    if len(d) < 30:
        return {"n": len(d), "verdict": "inconclusive", "reason": f"only {len(d)} signal cycles"}
    p = block_bootstrap_pvalue(d, np.zeros_like(d), n_boot=2000, block_len=2)
    data_ok = d.mean() > 0 and p < 0.025
    return {"n_signals": int(len(d)), "mean_rv2_minus_iv2": float(d.mean()), "win_rate": float((d > 0).mean()), "p_value": p,
            "verdict": "inconclusive" if data_ok else "not_supported",
            "reason": f"{len(d)} signals (VIX9D below trailing 10d realised): next-9d RV^2 - VIX9D^2 mean {d.mean():+.4f}, realised wins {(d > 0).mean()*100:.0f}%, p={p:.3f}" + ("; data part passes, swap simulation not implemented" if data_ok else "")}


# ------------------------------------------------------------------ VIX forwards --

def _vix_forward(vix, v3):
    f2 = (3 * v3 ** 2 - vix ** 2) / 2
    return np.sqrt(np.maximum(f2, 1e-9))


def vix_forward_contango(vix_rows, vix3m_rows) -> dict:
    """T-238 (data part): when VIX3M/VIX > 1.10, P(VIX_{t+21} < F) > 0.60 with 95% CI above 0.5 and mean F - VIX_{t+21} > 0 (p < 0.05).
    Non-overlapping 21-day cycles. Call-spread simulation not implemented (pass -> inconclusive)."""
    vx = index_closes(vix_rows); v3 = index_closes(vix3m_rows)
    days = sorted(d for d in vx if d in v3)
    VX = np.array([vx[d] for d in days]); V3 = np.array([v3[d] for d in days]); F = _vix_forward(VX, V3)
    hits, gaps = [], []
    t = 0
    while t + 21 < len(VX):
        if V3[t] / VX[t] > 1.10:
            hits.append(VX[t + 21] < F[t]); gaps.append(F[t] - VX[t + 21]); t += 21
        else:
            t += 1
    n = len(hits); k = int(sum(hits)); g = np.array(gaps)
    lo, hi = _binom_two_sided_ci(k, n)
    p = block_bootstrap_pvalue(g, np.zeros_like(g), n_boot=2000, block_len=2) if n >= 8 else 1.0
    data_ok = k / n > 0.60 and lo > 0.5 and g.mean() > 0 and p < 0.05
    return {"n": n, "freq_below_forward": k / n, "ci95": [lo, hi], "mean_F_minus_vix21": float(g.mean()), "p_value": p,
            "verdict": "inconclusive" if data_ok else "not_supported",
            "reason": f"in contango (VIX3M/VIX>1.10), VIX 21 days later is below the forward {k}/{n} = {k/n:.0%} (95% CI {lo:.2f}-{hi:.2f}); mean F - VIX(t+21) {g.mean():+.2f} pts, p={p:.4f}" + ("; data part passes, call-spread simulation not implemented" if data_ok else "")}


T241_MIN_EVENTS = 25        # T-241 trial.min_n, in spike events


def vix_spike_forward(vix_rows, vix3m_rows) -> dict:
    """T-241, tested as its claim sentence is worded: after VIX > 30 and VIX > VIX3M, VIX_{t+21} is below the forward F in FEWER than 50%
    of events and the excess reversion beyond F is not significant (the exact 95% CI does not lie above 0.5), while VIX_{t+21} is below spot
    VIX in MORE than 75% of events; the put-spread P&L part (priced with VVIX) is not implemented, so the verdict is at best inconclusive.
    The strategy-side reading (P(<F) > 0.5 with the CI above 0.5) refutes this claim; it is T-535's wording (spike_forward_v2).
    Below trial.min_n (25 events) only a decisive failure (an exact CI on the wrong side of the claimed bound) can decide.
    Non-overlapping 21-day event entries."""
    vx = index_closes(vix_rows); v3 = index_closes(vix3m_rows)
    days = sorted(d for d in vx if d in v3)
    VX = np.array([vx[d] for d in days]); V3 = np.array([v3[d] for d in days]); F = _vix_forward(VX, V3)
    below_f, below_spot = [], []
    t = 0
    while t + 21 < len(VX):
        if VX[t] > 30 and VX[t] > V3[t]:
            below_f.append(VX[t + 21] < F[t]); below_spot.append(VX[t + 21] < VX[t]); t += 21
        else:
            t += 1
    n = len(below_f)
    if n < 10:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} spike events"}
    kf, ks = int(sum(below_f)), int(sum(below_spot))
    lf, hf = _binom_two_sided_ci(kf, n); ls, hs = _binom_two_sided_ci(ks, n)
    full = n >= T241_MIN_EVENTS
    # (name, passes on the point frequency / test, fails decisively: the exact 95% CI lies on the wrong side of the claimed bound)
    rows = [("P(VIX_t+21 < F) < 0.5", kf / n < 0.5, lf >= 0.5),
            ("excess reversion beyond F not significant (exact 95% CI not above 0.5)", not lf > 0.5, lf > 0.5),
            ("P(VIX_t+21 < spot VIX) > 0.75", ks / n > 0.75, hs <= 0.75)]
    criteria = [(name, bool(ok) if (full or ok or decisive) else None) for name, ok, decisive in rows]
    criteria += [("put spread struck at F vs at spot: positive expectancy only when struck at spot (VVIX-priced P&L simulation)", None),
                 (f"sample reaches trial min_n {T241_MIN_EVENTS} events ({n} so far)", True if full else None)]
    verdict, why = _verdict(criteria)
    strategy_passes = kf / n > 0.5 and lf > 0.5
    return {"n_events": n, "min_n": T241_MIN_EVENTS, "p_below_forward": kf / n, "ci_forward": [lf, hf], "p_below_spot": ks / n, "ci_spot": [ls, hs],
            "criteria": [[c, ok] for c, ok in criteria], "verdict": verdict,
            "reason": f"{n} spike events (VIX>30, backwardation): VIX 21 days later below the forward in {kf}/{n} ({lf:.2f}-{hf:.2f}), below spot in {ks}/{n} ({ls:.2f}-{hs:.2f})"
                      + ("; the curve UNDER-prices the reversion (the strategy-side pass rule is met), which refutes the claim sentence that the curve already prices the decline (that reading is T-535)"
                         if strategy_passes else "; finding: the forward is fair after spikes")
                      + f"; verdict: {why}"}


# ------------------------------------------------------------- chains: boxes, parity --

def _chain_by_expiry(rows: Iterable[dict]) -> dict:
    by = defaultdict(lambda: {"call": {}, "put": {}})
    for r in rows:
        v = r["value"]
        if v.get("bid") is None or v.get("ask") is None:
            continue
        by[v["expiry"]][v["type"]][float(v["strike"])] = (float(v["bid"]), float(v["ask"]))
    return by


def _bill_curve(dtb3: dict, dgs2: dict, day: str):
    """Continuous rate at maturity T (years), linear between the 3-month bill (DTB3, discount basis) and the 2-year note (DGS2,
    semiannual bond-equivalent); flat outside. Both from the latest rows dated before the capture day."""
    y3 = _dtb3_cont(_bill_obs(dtb3, day)[1]); y2 = _semiannual_cont(_bill_obs(dgs2, day)[1])
    def at(T):
        if T <= 0.25:
            return y3
        if T >= 2.0:
            return y2
        return y3 + (y2 - y3) * (T - 0.25) / 1.75
    return at


def box_rates(chain_rows, spot: float, capture_day: str, dtb3_rows, dgs2_rows, dte_range=(90, 365), moneyness: float = 0.15, min_width_frac: float = 0.10) -> list[dict]:
    """All boxes on strikes that are multiples of 100 within +/- moneyness of spot, width >= min_width_frac*spot.
    Lending (long box) pays asks on bought legs and bids on sold legs; borrowing (short box) the reverse."""
    by = _chain_by_expiry(chain_rows)
    curve = _bill_curve(index_closes(dtb3_rows), index_closes(dgs2_rows), capture_day)
    cap = datetime.strptime(capture_day, "%Y-%m-%d")
    out = []
    for exp, legs in by.items():
        dte = (datetime.strptime(exp, "%Y-%m-%d") - cap).days
        if not (dte_range[0] <= dte <= dte_range[1]):
            continue
        T = dte / 365.0
        ks = sorted(k for k in legs["call"] if k in legs["put"] and abs(k / spot - 1) <= moneyness and k % 100 == 0
                    and legs["call"][k][0] > 0 and legs["put"][k][0] > 0)
        for i, k1 in enumerate(ks):
            for k2 in ks[i + 1:]:
                if k2 - k1 < min_width_frac * spot:
                    continue
                (c1b, c1a), (c2b, c2a) = legs["call"][k1], legs["call"][k2]
                (p1b, p1a), (p2b, p2a) = legs["put"][k1], legs["put"][k2]
                lend_cost = c1a - c2b - p1b + p2a
                borrow_cash = c1b - c2a - p1a + p2b
                mid = (c1b + c1a) / 2 - (c2b + c2a) / 2 - (p1b + p1a) / 2 + (p2b + p2a) / 2
                W = k2 - k1
                rec = {"expiry": exp, "dte": dte, "k1": k1, "k2": k2, "bill": curve(T)}
                rec["r_lend"] = math.log(W / lend_cost) / T if lend_cost > 0 else None
                rec["r_borrow"] = math.log(W / borrow_cash) / T if borrow_cash > 0 else None
                rec["r_mid"] = math.log(W / mid) / T if mid > 0 else None
                out.append(rec)
    return out


T186_MIN_DAYS = 20          # T-186 pass: "maintained over 20 captured days" (= trial.min_n)
T187_MIN_DAYS = 10          # T-187 trial.min_n; its pass names no 20-day requirement


def box_lending(captures: list[tuple[str, float, list]], dtb3_rows, dgs2_rows) -> dict:
    """T-186: per capture day, median (r_lend - r_bill) over 90-365 DTE boxes in [15, 80] bp with >= 80% of boxes positive.
    Day one is a criterion of its own (a failed day one is not_supported); then maintained on >= 80% of >= 20 captured days."""
    dtb3, dgs2 = list(dtb3_rows), list(dgs2_rows)
    d3, d2 = index_closes(dtb3), index_closes(dgs2)
    days = []
    for day, spot, rows in captures:
        bx = [b for b in box_rates(rows, spot, day, dtb3, dgs2, (90, 365)) if b["r_lend"] is not None]
        if not bx:
            continue
        sp = np.array([(b["r_lend"] - b["bill"]) * 1e4 for b in bx]); mid = np.array([(b["r_mid"] - b["bill"]) * 1e4 for b in bx if b["r_mid"] is not None])
        dgs2_day, dgs2_pct = _bill_obs(d2, day)
        days.append({"day": day, "n_boxes": len(bx), "median_spread_bp": float(np.median(sp)), "share_positive": float((sp > 0).mean()),
                     "median_mid_spread_bp": float(np.median(mid)) if len(mid) else None,
                     "pass": bool(15 <= np.median(sp) <= 80 and (sp > 0).mean() >= 0.8),
                     "bill": {**_bill_used(d3, day), "dgs2_day": dgs2_day, "dgs2_pct": dgs2_pct, "dgs2_cont_bp": _semiannual_cont(dgs2_pct) * 1e4}})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX chain captures with 90-365 DTE boxes on this machine"}
    d0 = days[0]; share = sum(d["pass"] for d in days) / len(days)
    verdict, why = _verdict([(f"day one ({d0['day']}): median executable spread in [15, 80] bp with >= 80% of boxes positive", d0["pass"]),
                             (f"maintained on >= 80% of >= {T186_MIN_DAYS} captured days ({len(days)} so far)",
                              None if len(days) < T186_MIN_DAYS else share >= 0.8)])
    last = days[-1]
    return {"n_days": len(days), "days": days, "share_days_passing": share, "verdict": verdict,
            "reason": f"{len(days)} capture day(s); day one {d0['day']}: executable spread median {d0['median_spread_bp']:+.0f} bp ({'pass' if d0['pass'] else 'fail'}); latest {last['day']}: {last['n_boxes']} boxes, executable lending spread over bills median {last['median_spread_bp']:+.0f} bp (mid {last['median_mid_spread_bp']:+.0f} bp), {last['share_positive']*100:.0f}% positive; claim needs [15, 80] bp and 80% positive on day one and on 80% of 20+ days; verdict: {why}"}


def box_borrowing(captures: list[tuple[str, float, list]], dtb3_rows, dgs2_rows) -> dict:
    """T-187: executable short-box borrowing rate (180-730 DTE) at least 100 bp below (3-month bill + 150 bp): median advantage > 100 bp
    on day one (a failed day one is not_supported) and on >= 80% of captured days, with at least trial.min_n (10) days to confirm."""
    dtb3, dgs2 = list(dtb3_rows), list(dgs2_rows)
    d3 = index_closes(dtb3)
    days = []
    for day, spot, rows in captures:
        bx = [b for b in box_rates(rows, spot, day, dtb3, dgs2, (180, 730)) if b["r_borrow"] is not None]
        if not bx:
            continue
        bill = _bill_used(d3, day)
        bench = bill["bill_cont_bp"] / 1e4 + 0.015
        adv = np.array([(bench - b["r_borrow"]) * 1e4 for b in bx])
        days.append({"day": day, "n_boxes": len(bx), "median_advantage_bp": float(np.median(adv)), "pass": bool(np.median(adv) > 100), "bill": bill})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX chain captures with 180-730 DTE boxes on this machine"}
    d0 = days[0]; share = sum(d["pass"] for d in days) / len(days); last = days[-1]
    verdict, why = _verdict([(f"day one ({d0['day']}): median advantage over bill + 150 bp > 100 bp", d0["pass"]),
                             (f"advantage > 100 bp on >= 80% of >= {T187_MIN_DAYS} captured days ({len(days)} so far)",
                              None if len(days) < T187_MIN_DAYS else share >= 0.8)])
    return {"n_days": len(days), "days": days, "share_days_passing": share, "verdict": verdict,
            "reason": f"{len(days)} capture day(s); day one {d0['day']}: median advantage {d0['median_advantage_bp']:+.0f} bp; latest {last['day']}: {last['n_boxes']} boxes, borrowing via short box beats bill+150 bp by a median {last['median_advantage_bp']:+.0f} bp (claim: > 100 bp on day one and on 80% of days, {T187_MIN_DAYS}+ days to confirm); verdict: {why}"}


def parity_check(captures: list[tuple[str, str, float, list]], dtb3_rows, n_side: int = 5) -> dict:
    """T-181: implied rate r = -ln(-slope)/T from regressing (C_mid - P_mid) on K over the n_side strikes either side of spot, for
    expiries >= 30 DTE; claim: |median r_impl - r_bill| < 50 bp on day one (each symbol's first capture day; a failure there is
    not_supported) and on every one of the first 20 captured days ("stable"; any failure among them is not_supported).
    The claim's violation statistic compares F_impl with F_theo = S e^{rT} - FV(D), which needs a dividend schedule the inputs do not
    carry: it is not implemented (None), so the verdict is at best inconclusive. ``violation_rate`` is a diagnostic only: residuals
    from a free-intercept fit, which absorbs any level error of the forward and so measures cross-strike consistency (T-505's question)."""
    d3 = index_closes(dtb3_rows)
    per_day = []
    for day, sym, spot, rows in captures:
        by = _chain_by_expiry(rows)
        cap = datetime.strptime(day, "%Y-%m-%d")
        bill_rec = _bill_used(d3, day); bill = bill_rec["bill_cont_bp"] / 1e4
        pairs = viol = 0; rates = []
        for exp, legs in by.items():
            dte = (datetime.strptime(exp, "%Y-%m-%d") - cap).days
            if dte < 1:
                continue
            ks = sorted(k for k in legs["call"] if k in legs["put"] and legs["call"][k][0] > 0 and legs["put"][k][0] > 0)
            if len(ks) < 2 * n_side:
                continue
            ks = sorted(ks, key=lambda k: abs(k - spot))[:2 * n_side]
            K = np.array(ks); y = np.array([(sum(legs["call"][k]) - sum(legs["put"][k])) / 2 for k in ks])
            spr = np.array([(legs["call"][k][1] - legs["call"][k][0]) + (legs["put"][k][1] - legs["put"][k][0]) for k in ks])
            A = np.column_stack([np.ones_like(K), K]); coef, *_ = np.linalg.lstsq(A, y, rcond=None)
            res = y - A @ coef
            pairs += len(ks); viol += int((np.abs(res) > 0.5 * spr).sum())
            if dte >= 30 and coef[1] < 0:
                T = dte / 365.0
                rates.append(-math.log(-coef[1]) / T)
        if pairs:
            gap = float((np.median(rates) - bill) * 1e4) if rates else None
            per_day.append({"day": day, "symbol": sym, "pairs": pairs, "violation_rate": viol / pairs, "violation_rate_basis": "free-intercept regression residual (diagnostic)",
                            "median_rate_gap_bp": gap, "n_rate_expiries": len(rates), "rate_ok": None if gap is None else bool(abs(gap) < 50), "bill": bill_rec})
    if not per_day:
        return {"n": 0, "verdict": "inconclusive", "reason": "no SPY/SPX chain captures on this machine"}

    def _all(vals):            # False if any False; None if any not evaluable; else True
        return False if any(v is False for v in vals) else (None if any(v is None for v in vals) else True)

    by_sym = defaultdict(list)
    for d in sorted(per_day, key=lambda d: d["day"]):
        by_sym[d["symbol"]].append(d)
    day_one = _all([v[0]["rate_ok"] for v in by_sym.values()])
    first20 = [d["rate_ok"] for v in by_sym.values() for d in v[:20]]
    stable = False if any(x is False for x in first20) else (_all(first20) if all(len(v) >= 20 for v in by_sym.values()) else None)
    n_days = len({d["day"] for d in per_day})
    verdict, why = _verdict([("day one: |median r_impl - r_bill| < 50 bp for every symbol (" + ", ".join(f"{s} {v[0]['day']}" for s, v in sorted(by_sym.items())) + ")", day_one),
                             ("stable over the first 20 captured days: rate gap within 50 bp on every one of them", stable),
                             ("violation fraction |F_impl - F_theo| > half-spread < 2%, F_theo = S e^{rT} - FV(D) (needs a dividend schedule the inputs do not carry)", None)])
    txt = "; ".join(f"{d['symbol']} {d['day']}: implied rate {d['median_rate_gap_bp']:+.0f} bp vs bill, {d['violation_rate']*100:.1f}% of {d['pairs']} pairs off a free cross-strike fit by more than the half-spread" for d in per_day[-4:] if d["median_rate_gap_bp"] is not None)
    return {"n_days": n_days, "per_day": per_day, "verdict": verdict,
            "reason": txt + " (claim: within 50 bp and < 2% violations against F_theo on day one, stable over 20 days); the free-fit violation rate is a diagnostic, not the claim's F_theo statistic; the implied rate from ten strikes is noise-dominated for SPY's $1 strikes; verdict: " + why}


# ---------------------------------------------------------------- pinning, weekend --

def _third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


_SPY_MW_WEEKLIES = "2016-01-01"     # T-502: "pre-2016 non-Fridays" carry no SPY expiration; Monday/Wednesday SPY weeklies from 2016
_SPY_DAILY_EXPIRIES = "2022-11-14"  # Tuesday/Thursday SPY expirations from mid-November 2022 ("late 2022"): every weekday expires
T502_MIN_OPEX = 200                 # T-502 trial.min_n, in monthly expiration days


def _expiry_on_or_before(trading: list[str], iso: str) -> Optional[str]:
    """The trading day an expiry scheduled for ``iso`` falls on: iso itself, or the preceding trading day when iso is a holiday."""
    j = bisect.bisect_right(trading, iso) - 1
    return trading[j] if j >= 0 else None


def _monthly_expiries(trading: list[str]) -> set[str]:
    """Monthly (third-Friday) SPY expirations within the data; a holiday third Friday expires on the preceding trading day."""
    out = set()
    if not trading:
        return out
    for y in range(int(trading[0][:4]), int(trading[-1][:4]) + 1):
        for m in range(1, 13):
            tf = _third_friday(y, m).isoformat()
            if trading[0] <= tf <= trading[-1]:
                out.add(_expiry_on_or_before(trading, tf))
    return out


def _spy_expiry_days(trading: list[str]) -> set[str]:
    """Every day with a SPY expiration by the deterministic calendar: Fridays throughout (monthlies, weeklies), Mondays and Wednesdays from
    2016, every weekday from late 2022; a scheduled expiry on a market holiday expires on the preceding trading day."""
    out = set()
    if not trading:
        return out
    d, end = date.fromisoformat(trading[0]), date.fromisoformat(trading[-1])
    while d <= end:
        iso = d.isoformat()
        sched = (4,) if iso < _SPY_MW_WEEKLIES else ((0, 2, 4) if iso < _SPY_DAILY_EXPIRIES else (0, 1, 2, 3, 4))
        if d.weekday() in sched:
            e = _expiry_on_or_before(trading, iso)
            if e:
                out.add(e)
        d += timedelta(days=1)
    return out


def expiry_pinning(spy_rows, start: str = "2005-01-01", n_boot: int = 4000, seed: int = 0) -> dict:
    """T-502: mean |close - nearest $1| on monthly (third-Friday) expiration days at least 10% below non-expiration days. Treatment: third
    Fridays, or the preceding trading day when the Friday is a holiday. Control: days with NO SPY expiration by the calendar (before 2016
    Mon-Thu; 2016 to Nov 2022 Tue/Thu), over 2005 to Nov 2022. From Nov 2022 every weekday expires, so that regime (monthly vs non-monthly
    days) is reported separately and does not enter the verdict. Null: ratio of means >= 0.90; p = P(bootstrap ratio >= 0.90).
    Pass: ratio < 0.90, p < 0.05, opex mean lower in a majority of years, and at least trial.min_n (200) opex days."""
    px = price_closes(spy_rows, "SPY")
    days = sorted(d for d in px if d >= start)
    monthly = _monthly_expiries(days); expiring = _spy_expiry_days(days) | monthly
    dist = {d: abs(px[d] - round(px[d])) for d in days}
    prim = [d for d in days if d < _SPY_DAILY_EXPIRIES]
    A = np.array([dist[d] for d in prim if d in monthly]); B = np.array([dist[d] for d in prim if d not in expiring])
    rng = np.random.default_rng(seed)
    ab = np.array([(rng.choice(A, A.size).mean(), rng.choice(B, B.size).mean()) for _ in range(n_boot)])
    p = float((np.sum(ab[:, 0] / ab[:, 1] >= 0.90) + 1) / (n_boot + 1))          # T-502 null: ratio >= 0.90
    p_diff = float((np.sum(ab[:, 0] - ab[:, 1] >= 0) + 1) / (n_boot + 1))         # no-difference null (T-192's), reported only
    years = sorted({d[:4] for d in prim}); wins = wins10 = counted = 0
    for y in years:
        a = [dist[d] for d in prim if d.startswith(y) and d in monthly]; b = [dist[d] for d in prim if d.startswith(y) and d not in expiring]
        if len(a) >= 6 and b:
            counted += 1; wins += bool(np.mean(a) < np.mean(b)); wins10 += bool(np.mean(a) < 0.9 * np.mean(b))
    ratio = float(A.mean() / B.mean())

    def _regime(lo, hi, control_excludes):
        sel = [d for d in days if lo <= d < hi]
        a = [dist[d] for d in sel if d in monthly]; b = [dist[d] for d in sel if d not in control_excludes]
        return {"n_opex": len(a), "n_control": len(b), "mean_opex": float(np.mean(a)) if a else None, "mean_control": float(np.mean(b)) if b else None,
                "ratio": float(np.mean(a) / np.mean(b)) if a and b else None}
    regimes = {"2005-2015 (control Mon-Thu)": _regime(start, _SPY_MW_WEEKLIES, expiring),
               "2016-Nov 2022 (control Tue/Thu)": _regime(_SPY_MW_WEEKLIES, _SPY_DAILY_EXPIRIES, expiring),
               "Nov 2022 on (daily expiries; control non-monthly days)": _regime(_SPY_DAILY_EXPIRIES, "9999", monthly)}
    verdict, why = _verdict([("ratio of means < 0.90", ratio < 0.90), ("bootstrap p < 0.05 against ratio >= 0.90", p < 0.05),
                             ("opex mean lower in a majority of years", wins > counted / 2),
                             (f"sample reaches trial min_n {T502_MIN_OPEX} opex days ({A.size})", True if A.size >= T502_MIN_OPEX else None)])
    return {"n_opex": int(A.size), "n_other": int(B.size), "mean_opex": float(A.mean()), "mean_other": float(B.mean()), "ratio": ratio, "p_value": p, "p_diff": p_diff,
            "years_lower": int(wins), "years_ratio_below_090": int(wins10), "years": counted, "regimes": regimes, "verdict": verdict,
            "reason": f"SPY close's distance to the nearest $1 on {A.size} monthly expiration days {A.mean():.3f} vs {B.mean():.3f} on {B.size} days with no SPY expiration, 2005 to Nov 2022 "
                      f"(ratio {ratio:.3f}, need < 0.90; P(boot ratio >= 0.90) = {p:.3f}; difference p {p_diff:.3f}); lower in {wins}/{counted} years ({wins10} at least 10% lower); "
                      "regimes (reported, the last outside the verdict): " + ", ".join(f"{k} {v['ratio']:.3f}" for k, v in regimes.items() if v["ratio"] is not None) + f"; verdict: {why}"}


def btc_weekend_variance(btc_rows, start_year: int = 2017, n_boot: int = 2000, seed: int = 0) -> dict:
    """T-264: Friday-close to Monday-close variance < 3x mean single-weekday (Tue-Fri) variance; per-year bootstrap CI of the
    ratio entirely below 0.9 in at least 70% of years."""
    px = price_closes(btc_rows, "BTC-USD")
    days = sorted(px)
    rng = np.random.default_rng(seed)
    by_year: dict[int, dict] = defaultdict(lambda: {"we": [], "wd": []})
    for i in range(1, len(days)):
        d = datetime.strptime(days[i], "%Y-%m-%d").date()
        r = math.log(px[days[i]] / px[days[i - 1]])
        if d.year < start_year:
            continue
        if d.weekday() in (1, 2, 3, 4):
            by_year[d.year]["wd"].append(r)
        if d.weekday() == 0:   # Monday: Fri close -> Mon close spans Sat, Sun, Mon bars
            prev_fri = (d - timedelta(days=3)).isoformat()
            if prev_fri in px:
                by_year[d.year]["we"].append(math.log(px[days[i]] / px[prev_fri]))
    out, passing = {}, 0
    for y, v in sorted(by_year.items()):
        we, wd = np.array(v["we"]), np.array(v["wd"])
        if len(we) < 30 or len(wd) < 100:
            continue
        ratio = float(np.mean(we ** 2) / (3 * np.mean(wd ** 2)))
        bs = [np.mean(rng.choice(we, we.size) ** 2) / (3 * np.mean(rng.choice(wd, wd.size) ** 2)) for _ in range(n_boot)]
        lo, hi = np.quantile(bs, [0.025, 0.975])
        out[y] = {"ratio": ratio, "ci": [float(lo), float(hi)], "pass": bool(hi < 0.9)}
        passing += hi < 0.9
    share = passing / len(out) if out else 0.0
    return {"by_year": out, "years_passing": passing, "years": len(out), "verdict": "supported" if share >= 0.7 else "not_supported",
            "reason": f"weekend (Fri->Mon) variance / 3x weekday variance: CI below 0.9 in {passing}/{len(out)} years (need 70%); ratios " + ", ".join(f"{y}:{v['ratio']:.2f}" for y, v in out.items())}


# ===================================================== verifier-corrected restatements =====

import re as _re

_ROOT = _re.compile(r"^([A-Z]+)")


def _chain_by_root_expiry(rows) -> dict:
    by = defaultdict(lambda: {"call": {}, "put": {}})
    for r in rows:
        v = r["value"]
        if v.get("bid") is None or v.get("ask") is None:
            continue
        m = _ROOT.match(v.get("sym", "")); root = m.group(1) if m else "?"
        by[(root, v["expiry"])][v["type"]][float(v["strike"])] = (float(v["bid"]), float(v["ask"]))
    return by


def _bill_cont(dtb3: dict, day: str) -> float:
    """Continuously compounded 3-month bill from DTB3 (discount basis), latest row dated before the capture day."""
    return _dtb3_cont(_bill_obs(dtb3, day)[1])


def _boxes_v2(rows, spot, day, dte_range, moneyness=0.15, min_width_frac=0.05, step=None):
    cap = datetime.strptime(day, "%Y-%m-%d"); out = []
    for (root, exp), legs in _chain_by_root_expiry(rows).items():
        dte = (datetime.strptime(exp, "%Y-%m-%d") - cap).days
        if not (dte_range[0] <= dte <= dte_range[1]):
            continue
        T = dte / 365.0
        ks = sorted(k for k in legs["call"] if k in legs["put"] and abs(k / spot - 1) <= moneyness and legs["call"][k][0] > 0 and legs["put"][k][0] > 0 and (step is None or k % step == 0))
        for i, k1 in enumerate(ks):
            for k2 in ks[i + 1:]:
                if k2 - k1 < min_width_frac * spot:
                    continue
                (c1b, c1a), (c2b, c2a) = legs["call"][k1], legs["call"][k2]; (p1b, p1a), (p2b, p2a) = legs["put"][k1], legs["put"][k2]
                W = k2 - k1
                mid = (c1b + c1a) / 2 - (c2b + c2a) / 2 - (p1b + p1a) / 2 + (p2b + p2a) / 2
                borrow = c1b - c2a - p1a + p2b
                out.append({"root": root, "expiry": exp, "T": T, "k1": k1, "k2": k2, "r_mid": math.log(W / mid) / T if mid > 0 else None,
                            "r_borrow": math.log(W / borrow) / T if borrow > 0 else None})
    return out


def box_mid_v2(captures, dtb3_rows, n_boot: int = 2000, seed: int = 0) -> dict:
    """T-503: median mid box lending rate over ALL strike pairs with both legs bid > 0 (60-120 DTE, |K/S-1| <= 15%, no strike-grid or
    width filter, as the procedure states) minus the continuously compounded 3-month bill in [15, 80] bp with the 95% bootstrap CI inside
    [0, 120] bp on day one; persistence over 20 captured days with no stated tolerance: every one of the first 20 days must pass, so any
    failing day among them is decisive. The $25-grid / width >= 5% subset is reported as a robustness row only."""
    d3 = index_closes(dtb3_rows); rng = np.random.default_rng(seed); days = []
    for day, spot, rows in captures:
        bx = [b for b in _boxes_v2(rows, spot, day, (60, 120), min_width_frac=0.0, step=None) if b["r_mid"] is not None]
        if not bx:
            continue
        bill = _bill_used(d3, day); b0 = bill["bill_cont_bp"] / 1e4
        sp = np.array([(b["r_mid"] - b0) * 1e4 for b in bx])
        bs = np.array([np.median(rng.choice(sp, sp.size)) for _ in range(n_boot)]); lo, hi = np.quantile(bs, [0.025, 0.975])
        sub = np.array([(b["r_mid"] - b0) * 1e4 for b in bx if b["k1"] % 25 == 0 and b["k2"] % 25 == 0 and b["k2"] - b["k1"] >= 0.05 * spot])
        days.append({"day": day, "n_boxes": len(bx), "median_bp": float(np.median(sp)), "ci_bp": [float(lo), float(hi)], "pass": bool(15 <= np.median(sp) <= 80 and lo >= 0 and hi <= 120),
                     "robustness_step25_wide": {"n_boxes": int(sub.size), "median_bp": float(np.median(sub)) if sub.size else None}, "bill": bill})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX captures with 60-120 DTE boxes on this machine"}
    d0 = days[0]
    persist = False if not all(d["pass"] for d in days[:20]) else (True if len(days) >= 20 else None)
    verdict, why = _verdict([(f"day one ({d0['day']}): median in [15, 80] bp with the 95% CI inside [0, 120] bp", d0["pass"]),
                             (f"persistence: in range on every one of the first 20 captured days ({min(len(days), 20)} so far)", persist)])
    rb = d0["robustness_step25_wide"]
    return {"n_days": len(days), "days": days, "verdict": verdict,
            "reason": f"day one {d0['day']}: {d0['n_boxes']} boxes (SPX and SPXW, 60-120 DTE, all strike pairs), mid box rate minus bill median {d0['median_bp']:+.0f} bp (95% CI {d0['ci_bp'][0]:+.0f} to {d0['ci_bp'][1]:+.0f}); needs [15, 80] with CI in [0, 120]"
                      + (f" (robustness, $25 grid and width >= 5% of spot: {rb['median_bp']:+.0f} bp over {rb['n_boxes']} boxes)" if rb["median_bp"] is not None else "")
                      + ("; later days: " + ", ".join(f"{d['day']} {d['median_bp']:+.0f} bp ({'in' if d['pass'] else 'out of'} range)" for d in days[1:]) if len(days) > 1 else "")
                      + ("" if persist is not None else f"; persistence needs 20 capture days ({len(days)} so far)") + f"; the CI resamples boxes that share strikes, so it understates uncertainty; verdict: {why}"}


def box_borrow_v2(captures, dtb3_rows) -> dict:
    """T-506: median OVER EXPIRIES (per (root, expiry) median, then the median of those) of the executable short-box borrowing rate
    (180-730 DTE, wide boxes) minus the bill < 50 bp on day one and on >= 80% of capture days. The pooled box median is reported."""
    d3 = index_closes(dtb3_rows); days = []
    for day, spot, rows in captures:
        bx = [b for b in _boxes_v2(rows, spot, day, (180, 730), step=25) if b["r_borrow"] is not None]
        if bx:
            bill = _bill_used(d3, day); b0 = bill["bill_cont_bp"] / 1e4
            groups = defaultdict(list)
            for b in bx:
                groups[(b["root"], b["expiry"])].append((b["r_borrow"] - b0) * 1e4)
            per = {f"{r} {e}": float(np.median(v)) for (r, e), v in sorted(groups.items())}
            m = float(np.median(list(per.values())))
            days.append({"day": day, "n_boxes": len(bx), "n_expiries": len(per), "median_bp": m, "pass": m < 50, "per_expiry_median_bp": per,
                         "pooled_median_bp": float(np.median([x for v in groups.values() for x in v])), "bill": bill})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX captures with 180-730 DTE boxes on this machine"}
    d0 = days[0]; share = sum(d["pass"] for d in days) / len(days)
    verdict = "not_supported" if not d0["pass"] else ("supported" if len(days) >= 20 and share >= 0.8 else "inconclusive")
    return {"n_days": len(days), "days": days, "verdict": verdict,
            "reason": f"day one {d0['day']}: executable short-box borrowing rate is bill {d0['median_bp']:+.0f} bp, median over {d0['n_expiries']} expiries ({d0['n_boxes']} boxes; pooled box median {d0['pooled_median_bp']:+.0f} bp) (needs < +50 bp)" + ("; later days: " + ", ".join(f"{d['day']} {d['median_bp']:+.0f} bp" for d in days[1:]) if len(days) > 1 else "")}


def parity_v2(captures, dtb3_rows, n_side: int = 5, n_boot: int = 2000, seed: int = 0) -> dict:
    """T-505: SPX chain split by root (SPX, SPXW); per (root, expiry) the 2*n_side strikes nearest spot; F_impl = K + (C_mid - P_mid) e^{rT};
    exceedance when |F_impl - median F_impl| > 0.5 e^{rT} (spread_c + spread_p). Day-one share < 2% with a one-sided 95% bootstrap bound
    < 2%; still < 2% on >= 16 of the first 20 capture days."""
    d3 = index_closes(dtb3_rows); rng = np.random.default_rng(seed); days = []
    for day, spot, rows in captures:
        bill = _bill_used(d3, day); r = bill["bill_cont_bp"] / 1e4; cap = datetime.strptime(day, "%Y-%m-%d"); flags = []
        for (root, exp), legs in _chain_by_root_expiry(rows).items():
            dte = (datetime.strptime(exp, "%Y-%m-%d") - cap).days
            if dte < 1:
                continue
            T = dte / 365.0; g = math.exp(r * T)
            ks = sorted((k for k in legs["call"] if k in legs["put"] and legs["call"][k][0] > 0 and legs["put"][k][0] > 0), key=lambda k: abs(k - spot))[:2 * n_side]
            if len(ks) < 4:
                continue
            F = np.array([k + ((sum(legs["call"][k]) - sum(legs["put"][k])) / 2) * g for k in ks]); med = np.median(F)
            band = np.array([0.5 * g * ((legs["call"][k][1] - legs["call"][k][0]) + (legs["put"][k][1] - legs["put"][k][0])) for k in ks])
            flags += list(np.abs(F - med) > band)
        if flags:
            f = np.array(flags, float); bs = np.array([rng.choice(f, f.size).mean() for _ in range(n_boot)])
            days.append({"day": day, "pairs": int(f.size), "share": float(f.mean()), "upper95": float(np.quantile(bs, 0.95)), "pass": bool(f.mean() < 0.02 and np.quantile(bs, 0.95) < 0.02), "bill": bill})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX captures on this machine"}
    d0 = days[0]
    verdict = "not_supported" if not d0["pass"] else ("inconclusive" if len(days) < 20 else ("supported" if sum(d["share"] < 0.02 for d in days[:20]) >= 16 else "not_supported"))
    return {"n_days": len(days), "days": days, "verdict": verdict,
            "reason": f"day one {d0['day']}: {d0['share']*100:.1f}% of {d0['pairs']} SPX/SPXW (K,T) pairs have an implied forward outside the half-spread band around the expiry median (one-sided 95% bound {d0['upper95']*100:.1f}%; needs < 2%)"
                      + (f"; later days: " + ", ".join(f"{d['day']} {d['share']*100:.1f}%" for d in days[1:]) + " (the claim makes day one decisive)" if len(days) > 1 else "")}


def btc_weekend_ratio_v2(btc_rows, start_year: int = 2017, n_boot: int = 2000, seed: int = 0) -> dict:
    """T-515: mean squared Sat+Sun daily return < 0.9 x mean squared Mon-Fri daily return: pooled 95% CI (block 4 weeks) entirely < 0.9, and
    ratio < 1 in >= 70% of years."""
    px = price_closes(btc_rows, "BTC-USD"); days = sorted(px)
    r, wd, yr = [], [], []
    for i in range(1, len(days)):
        d = date.fromisoformat(days[i])
        if d.year >= start_year:
            r.append(math.log(px[days[i]] / px[days[i - 1]])); wd.append(d.weekday() >= 5); yr.append(d.year)
    r, wd, yr = np.array(r) ** 2, np.array(wd), np.array(yr)
    ratio = float(r[wd].mean() / r[~wd].mean())
    rng = np.random.default_rng(seed); n = len(r); B = 28; nb = math.ceil(n / B); bs = []
    for _ in range(n_boot):
        idx = ((rng.integers(0, n, nb)[:, None] + np.arange(B)[None, :]).ravel()[:n]) % n
        bs.append(r[idx][wd[idx]].mean() / r[idx][~wd[idx]].mean())
    lo, hi = np.quantile(bs, [0.025, 0.975])
    per = {int(y): float(r[(yr == y) & wd].mean() / r[(yr == y) & ~wd].mean()) for y in sorted(set(yr)) if ((yr == y) & wd).sum() > 20}
    share = sum(v < 1 for v in per.values()) / len(per)
    ok = hi < 0.9 and share >= 0.7
    return {"n": int(n), "ratio": ratio, "ci": [float(lo), float(hi)], "per_year": per, "share_years_below_1": share, "verdict": "supported" if ok else "not_supported",
            "reason": f"BTC weekend/weekday squared-return ratio {ratio:.2f} (95% CI {lo:.2f}-{hi:.2f}, needs entirely < 0.9); below 1 in {share*100:.0f}% of years (needs 70%)"}


def conditional_forward_v2(vix_rows, vix3m_rows, spy_rows) -> dict:
    """T-530: conditional on VIX3M/VIX > 1.10, F^2 = (93*VIX3M^2 - 30*VIX^2)/63 minus SPY variance over trading days 22-63 > 0 with the 95% CI
    excluding zero, positive in both halves (non-overlapping 63-day entries)."""
    days, (vix, v3), S = _aligned_index_and_price([vix_rows, vix3m_rows], spy_rows, "SPY")
    r = np.diff(np.log(S)); x = []
    t = 0
    while t + 63 <= len(r):
        if v3[t] / vix[t] > 1.10:
            f2 = (93 * (v3[t] / 100) ** 2 - 30 * (vix[t] / 100) ** 2) / 63
            x.append(f2 - _rv_annual(r, t + 21, t + 63)); t += 63
        else:
            t += 1
    x = np.array(x)
    p = block_bootstrap_pvalue(x, np.zeros_like(x), n_boot=2000, block_len=2)
    h = len(x) // 2; halves = [float(x[:h].mean()), float(x[h:].mean())]
    ok = x.mean() > 0 and p < 0.025 and all(z > 0 for z in halves)
    return {"n": int(len(x)), "mean_var": float(x.mean()), "p": p, "halves": halves, "verdict": "supported" if ok else "not_supported",
            "reason": f"{len(x)} contango entries: forward variance minus realised (days 22-63) {x.mean():+.4f} (p={p:.4f}), halves {halves[0]:+.4f}/{halves[1]:+.4f}"}


def vix9d_v2(vix9d_rows, spy_rows) -> dict:
    """T-533: conditional on VIX9D < trailing 10-day realised SPY vol, SPY variance realised over the next 9 calendar days exceeds VIX9D^2
    on average (95% CI excluding zero). Non-overlapping signals."""
    days, (v9,), S = _aligned_index_and_price([vix9d_rows], spy_rows, "SPY")
    r = np.diff(np.log(S)); dts = [date.fromisoformat(d) for d in days]; x = []
    t = 10
    while t < len(r) - 8:
        end = t
        while end + 1 < len(dts) and (dts[end + 1] - dts[t]).days <= 9:
            end += 1
        trailing = math.sqrt(_rv_annual(r, t - 10, t)) * 100
        if v9[t] < trailing and end > t:
            x.append(_rv_annual(r, t, end) - (v9[t] / 100) ** 2); t = end + 1
        else:
            t += 1
    x = np.array(x)
    p = block_bootstrap_pvalue(x, np.zeros_like(x), n_boot=2000, block_len=2)
    ok = x.mean() > 0 and p < 0.025
    return {"n_signals": int(len(x)), "mean": float(x.mean()), "p": p, "verdict": "supported" if ok else "not_supported",
            "reason": f"{len(x)} signals: next-9-calendar-day RV^2 - VIX9D^2 mean {x.mean():+.4f} (realised larger in {(x > 0).mean()*100:.0f}%), p={p:.3f}"}


def _f93(vix, v3):
    return np.sqrt(np.maximum((93 * v3 ** 2 - 30 * vix ** 2) / 63, 1e-9))


def contango_forward_v2(vix_rows, vix3m_rows, vvix_rows) -> dict:
    """T-534: when VIX3M/VIX > 1.10, VIX(t+21) < F_adj in > 60% of non-overlapping months: the exact lower 95% bound of the frequency > 0.60
    on F_adj = F exp(-(VVIX/100)^2 T/2), T = 1/12, and mean F_adj - VIX(t+21) > 0 at p < 0.05. F (unadjusted) reported."""
    vx, v3, vv = index_closes(vix_rows), index_closes(vix3m_rows), index_closes(vvix_rows)
    days = sorted(d for d in vx if d in v3 and d in vv)
    VX = np.array([vx[d] for d in days]); V3 = np.array([v3[d] for d in days]); VV = np.array([vv[d] for d in days])
    F = _f93(VX, V3); Fa = F * np.exp(-((VV / 100) ** 2) * (1 / 12) / 2)
    hit, hitF, gap = [], [], []
    t = 0
    while t + 21 < len(VX):
        if V3[t] / VX[t] > 1.10:
            hit.append(VX[t + 21] < Fa[t]); hitF.append(VX[t + 21] < F[t]); gap.append(Fa[t] - VX[t + 21]); t += 21
        else:
            t += 1
    n, k = len(hit), int(sum(hit)); lo, hi = _binom_two_sided_ci(k, n); g = np.array(gap)
    p = block_bootstrap_pvalue(g, np.zeros_like(g), n_boot=2000, block_len=2)
    ok = lo > 0.60 and g.mean() > 0 and p < 0.05
    return {"n": n, "freq_adj": k / n, "ci": [lo, hi], "freq_unadj": float(np.mean(hitF)), "mean_gap": float(g.mean()), "p": p, "verdict": "supported" if ok else "not_supported",
            "reason": f"contango months: VIX 21 days later below F_adj in {k}/{n} = {k/n:.0%} (95% CI {lo:.2f}-{hi:.2f}, needs lower > 0.60), below unadjusted F in {np.mean(hitF):.0%}; mean F_adj - VIX(t+21) {g.mean():+.2f}, p={p:.4f}"}


def spike_forward_v2(vix_rows, vix3m_rows, vvix_rows) -> dict:
    """T-535: after VIX > 30 and VIX > VIX3M, P(VIX(t+21) < F_adj) > 0.5 with the exact 95% CI excluding 0.5; otherwise 'the forward is fair'."""
    vx, v3, vv = index_closes(vix_rows), index_closes(vix3m_rows), index_closes(vvix_rows)
    days = sorted(d for d in vx if d in v3 and d in vv)
    VX = np.array([vx[d] for d in days]); V3 = np.array([v3[d] for d in days]); VV = np.array([vv[d] for d in days])
    F = _f93(VX, V3); Fa = F * np.exp(-((VV / 100) ** 2) * (1 / 12) / 2)
    a, b, s = [], [], []
    t = 0
    while t + 21 < len(VX):
        if VX[t] > 30 and VX[t] > V3[t]:
            a.append(VX[t + 21] < Fa[t]); b.append(VX[t + 21] < F[t]); s.append(VX[t + 21] < VX[t]); t += 21
        else:
            t += 1
    n, k = len(a), int(sum(a)); lo, hi = _binom_two_sided_ci(k, n)
    ok = k / n > 0.5 and lo > 0.5
    return {"n_events": n, "p_adj": k / n, "ci": [lo, hi], "p_unadj": float(np.mean(b)), "p_spot": float(np.mean(s)), "verdict": "supported" if ok else "not_supported",
            "reason": f"{n} spike events since {days[0]}: VIX 21 days later below F_adj in {k}/{n} ({lo:.2f}-{hi:.2f}), below unadjusted F in {np.mean(b):.0%}, below spot in {np.mean(s):.0%}" + ("" if ok else "; finding: the forward is fair after spikes")}


def vvix_v2(vvix_rows, vix_rows, start: str = "2006-01-01") -> dict:
    """T-536: non-overlapping months since 2006: VVIX minus realised 21-day vol of daily log changes in spot VIX, lower 99% bound of the
    mean gap > 10 vol points."""
    vv = index_closes(vvix_rows); vx = index_closes(vix_rows)
    days = sorted(d for d in vv if d in vx and d >= start)
    VV = np.array([vv[d] for d in days]); lr = np.diff(np.log(np.array([vx[d] for d in days])))
    g = np.array([VV[t] - np.std(lr[t:t + 21], ddof=1) * math.sqrt(252) * 100 for t in range(0, len(lr) - 21, 21)])
    se = g.std(ddof=1) / math.sqrt(len(g)); lo99 = g.mean() - 2.576 * se
    return {"n_months": int(len(g)), "mean_gap": float(g.mean()), "lower99": float(lo99), "verdict": "supported" if lo99 > 10 else "not_supported",
            "reason": f"{len(g)} non-overlapping months: VVIX minus realised spot-VIX vol {g.mean():+.1f} pts (lower 99% {lo99:+.1f}, needs > 10); VVIX prices VIX futures, which move less than spot"}
