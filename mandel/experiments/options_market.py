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

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

import numpy as np

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


def term_vs_spot_premium(vix_rows, vix3m_rows, spy_rows) -> dict:
    """T-231: (F^2 - RV[22..63]) - (VIX^2 - RV[1..21]) > 0 with F^2 = (3*VIX3M^2 - VIX^2)/2; conditional forward premium
    (VIX3M/VIX > 1.10) positive in both halves. Non-overlapping 63-day cycles."""
    days, (vix, v3), S = _aligned_index_and_price([vix_rows, vix3m_rows], spy_rows, "SPY")
    r = np.diff(np.log(S))
    d, cond, ts = [], [], []
    for t in range(0, len(r) - 63, 63):
        f2 = (3 * (v3[t] / 100) ** 2 - (vix[t] / 100) ** 2) / 2
        fwd = f2 - _rv_annual(r, t + 21, t + 63); spot = (vix[t] / 100) ** 2 - _rv_annual(r, t, t + 21)
        d.append(fwd - spot); ts.append(t)
        if v3[t] / vix[t] > 1.10:
            cond.append(fwd)
    d = np.array(d); cond = np.array(cond)
    p = block_bootstrap_pvalue(d, np.zeros_like(d), n_boot=2000, block_len=2) if len(d) >= 8 else 1.0
    h = len(cond) // 2
    halves = [float(cond[:h].mean()) if h else float("nan"), float(cond[h:].mean()) if len(cond) - h else float("nan")]
    ok = d.mean() > 0 and p < 0.025 and all(x > 0 for x in halves)
    return {"n_cycles": int(len(d)), "mean_term_minus_spot_var": float(d.mean()), "p_value": p, "n_conditional": int(len(cond)),
            "conditional_forward_premium_halves": halves, "verdict": "supported" if ok else "not_supported",
            "reason": f"forward premium minus spot premium {d.mean():+.4f} (variance units) over {len(d)} non-overlapping 63d cycles, p={p:.3f}; conditional (VIX3M/VIX>1.10, n={len(cond)}) forward premium halves {halves[0]:+.4f}/{halves[1]:+.4f}"}


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


def vix_spike_forward(vix_rows, vix3m_rows) -> dict:
    """T-241: after VIX > 30 and VIX > VIX3M, P(VIX_{t+21} < F) > 0.5 with 95% CI excluding 0.5 for the strategy to pass;
    otherwise the finding is 'the forward is fair'. Non-overlapping 21-day event entries."""
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
    ok = kf / n > 0.5 and lf > 0.5
    return {"n_events": n, "p_below_forward": kf / n, "ci_forward": [lf, hf], "p_below_spot": ks / n, "ci_spot": [ls, hs],
            "verdict": "supported" if ok else "not_supported",
            "reason": f"{n} spike events (VIX>30, backwardation): VIX 21 days later below the forward in {kf}/{n} ({lf:.2f}-{hf:.2f}), below spot in {ks}/{n} ({ls:.2f}-{hs:.2f})"
                      + ("; the pass rule (strategy passes) is met, which REFUTES the claim sentence that the curve already prices the decline" if ok else "; finding: the forward is fair after spikes")}


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
    """Continuous rate at maturity T (years), linear between the 3-month bill and the 2-year note; flat outside."""
    d3 = max((d for d in dtb3 if d <= day), default=None); d2 = max((d for d in dgs2 if d <= day), default=None)
    y3 = math.log(1 + dtb3[d3] / 100); y2 = math.log(1 + dgs2[d2] / 100)
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


def box_lending(captures: list[tuple[str, float, list]], dtb3_rows, dgs2_rows) -> dict:
    """T-186: per capture day, median (r_lend - r_bill) over 90-365 DTE boxes in [15, 80] bp with >= 80% of boxes positive;
    maintained on >= 80% of >= 20 captured days. One day can falsify, not confirm."""
    dtb3, dgs2 = list(dtb3_rows), list(dgs2_rows)
    days = []
    for day, spot, rows in captures:
        bx = [b for b in box_rates(rows, spot, day, dtb3, dgs2, (90, 365)) if b["r_lend"] is not None]
        if not bx:
            continue
        sp = np.array([(b["r_lend"] - b["bill"]) * 1e4 for b in bx]); mid = np.array([(b["r_mid"] - b["bill"]) * 1e4 for b in bx if b["r_mid"] is not None])
        days.append({"day": day, "n_boxes": len(bx), "median_spread_bp": float(np.median(sp)), "share_positive": float((sp > 0).mean()),
                     "median_mid_spread_bp": float(np.median(mid)) if len(mid) else None,
                     "pass": bool(15 <= np.median(sp) <= 80 and (sp > 0).mean() >= 0.8)})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX chain captures with 90-365 DTE boxes on this machine"}
    share = sum(d["pass"] for d in days) / len(days)
    if len(days) < 20:
        verdict = "not_supported" if share < 0.8 and len(days) >= 1 and not any(d["pass"] for d in days) else "inconclusive"
    else:
        verdict = "supported" if share >= 0.8 else "not_supported"
    last = days[-1]
    return {"n_days": len(days), "days": days, "share_days_passing": share, "verdict": verdict,
            "reason": f"{len(days)} capture day(s); latest {last['day']}: {last['n_boxes']} boxes, executable lending spread over bills median {last['median_spread_bp']:+.0f} bp (mid {last['median_mid_spread_bp']:+.0f} bp), {last['share_positive']*100:.0f}% positive; claim needs [15, 80] bp and 80% positive on 80% of 20+ days"}


def box_borrowing(captures: list[tuple[str, float, list]], dtb3_rows, dgs2_rows) -> dict:
    """T-187: executable short-box borrowing rate (180-730 DTE) at least 100 bp below (3-month bill + 150 bp) on >= 80% of days."""
    dtb3, dgs2 = list(dtb3_rows), list(dgs2_rows)
    d3 = index_closes(dtb3)
    days = []
    for day, spot, rows in captures:
        bx = [b for b in box_rates(rows, spot, day, dtb3, dgs2, (180, 730)) if b["r_borrow"] is not None]
        if not bx:
            continue
        bench = math.log(1 + d3[max(d for d in d3 if d <= day)] / 100) + 0.015
        adv = np.array([(bench - b["r_borrow"]) * 1e4 for b in bx])
        days.append({"day": day, "n_boxes": len(bx), "median_advantage_bp": float(np.median(adv)), "pass": bool(np.median(adv) > 100)})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX chain captures with 180-730 DTE boxes on this machine"}
    share = sum(d["pass"] for d in days) / len(days); last = days[-1]
    verdict = ("supported" if share >= 0.8 else "not_supported") if len(days) >= 20 else ("not_supported" if not any(d["pass"] for d in days) else "inconclusive")
    return {"n_days": len(days), "days": days, "share_days_passing": share, "verdict": verdict,
            "reason": f"{len(days)} capture day(s); latest {last['day']}: {last['n_boxes']} boxes, borrowing via short box beats bill+150 bp by a median {last['median_advantage_bp']:+.0f} bp (claim: > 100 bp on 80% of 20+ days)"}


def parity_check(captures: list[tuple[str, str, float, list]], dtb3_rows, n_side: int = 5) -> dict:
    """T-181: per expiry, regress (C_mid - P_mid) on K over the n_side strikes either side of spot. Violations: |residual| >
    half the combined call+put spread; claim: < 2% of (K,T) pairs. Implied rate r = -ln(-slope)/T for expiries >= 30 DTE;
    claim: |median r_impl - r_bill| < 50 bp. Stable over 20 days to confirm; one day can falsify."""
    d3 = index_closes(dtb3_rows)
    per_day = []
    for day, sym, spot, rows in captures:
        by = _chain_by_expiry(rows)
        cap = datetime.strptime(day, "%Y-%m-%d")
        bill = math.log(1 + d3[max(d for d in d3 if d <= day)] / 100)
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
            per_day.append({"day": day, "symbol": sym, "pairs": pairs, "violation_rate": viol / pairs,
                            "median_rate_gap_bp": float((np.median(rates) - bill) * 1e4) if rates else None, "n_rate_expiries": len(rates)})
    if not per_day:
        return {"n": 0, "verdict": "inconclusive", "reason": "no SPY/SPX chain captures on this machine"}
    ok_day = [d["violation_rate"] < 0.02 and d["median_rate_gap_bp"] is not None and abs(d["median_rate_gap_bp"]) < 50 for d in per_day]
    n_days = len({d["day"] for d in per_day})
    verdict = ("supported" if all(ok_day) else "not_supported") if n_days >= 20 else ("not_supported" if not any(ok_day) else "inconclusive")
    txt = "; ".join(f"{d['symbol']} {d['day']}: {d['violation_rate']*100:.1f}% of {d['pairs']} pairs outside half-spread, implied rate {d['median_rate_gap_bp']:+.0f} bp vs bill" for d in per_day[-4:] if d["median_rate_gap_bp"] is not None)
    return {"n_days": n_days, "per_day": per_day, "verdict": verdict, "reason": txt + " (claim: < 2% and within 50 bp, stable over 20 days); the implied rate from ten strikes is noise-dominated for SPY's $1 strikes, so the violation rate is the reliable half"}


# ---------------------------------------------------------------- pinning, weekend --

def _third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def expiry_pinning(spy_rows, start: str = "2005-01-01", n_boot: int = 4000, seed: int = 0) -> dict:
    """T-192 (monthly opex only): mean |close - nearest integer| on third Fridays at least 10% below other days, bootstrap
    p < 0.05, and lower in a majority of years. Weeklies are not separated: since 2022 SPY expires every trading day."""
    px = price_closes(spy_rows, "SPY")
    days = sorted(d for d in px if d >= start)
    opex = {_third_friday(y, m).isoformat() for y in range(int(start[:4]), 2027) for m in range(1, 13)}
    dist = {d: abs(px[d] - round(px[d])) for d in days}
    A = np.array([dist[d] for d in days if d in opex]); B = np.array([dist[d] for d in days if d not in opex])
    rng = np.random.default_rng(seed)
    boots = np.array([rng.choice(A, A.size).mean() - rng.choice(B, B.size).mean() for _ in range(n_boot)])
    p = float((np.sum(boots >= 0) + 1) / (n_boot + 1))
    years = sorted({d[:4] for d in days}); wins = 0; counted = 0
    for y in years:
        a = [dist[d] for d in days if d.startswith(y) and d in opex]; b = [dist[d] for d in days if d.startswith(y) and d not in opex]
        if len(a) >= 6:
            counted += 1; wins += np.mean(a) < np.mean(b)
    ratio = float(A.mean() / B.mean())
    ok = ratio <= 0.9 and p < 0.05 and wins > counted / 2
    return {"n_opex": int(A.size), "n_other": int(B.size), "mean_opex": float(A.mean()), "mean_other": float(B.mean()), "ratio": ratio, "p_value": p,
            "years_lower": wins, "years": counted, "verdict": "supported" if ok else "not_supported",
            "reason": f"SPY close's distance to the nearest $1 on {A.size} monthly opex days {A.mean():.3f} vs {B.mean():.3f} on other days (ratio {ratio:.2f}, need <= 0.90; p={p:.3f}); lower in {wins}/{counted} years"}


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
    return math.log(1 + dtb3[max(d for d in dtb3 if d <= day)] / 100)


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
                out.append({"root": root, "expiry": exp, "T": T, "r_mid": math.log(W / mid) / T if mid > 0 else None,
                            "r_borrow": math.log(W / borrow) / T if borrow > 0 else None})
    return out


def box_mid_v2(captures, dtb3_rows, n_boot: int = 2000, seed: int = 0) -> dict:
    """T-503: median mid box lending rate (60-120 DTE, |K/S-1| <= 15%) minus the 3-month bill in [15, 80] bp with the 95% bootstrap CI
    inside [0, 120] bp on day one; persistence over 20 capture days (until then the verdict can only be not_supported or inconclusive)."""
    d3 = index_closes(dtb3_rows); rng = np.random.default_rng(seed); days = []
    for day, spot, rows in captures:
        bx = [b for b in _boxes_v2(rows, spot, day, (60, 120), step=25) if b["r_mid"] is not None]
        if not bx:
            continue
        sp = np.array([(b["r_mid"] - _bill_cont(d3, day)) * 1e4 for b in bx])
        bs = np.array([np.median(rng.choice(sp, sp.size)) for _ in range(n_boot)]); lo, hi = np.quantile(bs, [0.025, 0.975])
        days.append({"day": day, "n_boxes": len(bx), "median_bp": float(np.median(sp)), "ci_bp": [float(lo), float(hi)], "pass": bool(15 <= np.median(sp) <= 80 and lo >= 0 and hi <= 120)})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX captures with 60-120 DTE boxes on this machine"}
    d0 = days[0]; persist = (sum(d["pass"] for d in days) / len(days) >= 0.8) if len(days) >= 20 else None
    verdict = "not_supported" if not d0["pass"] else ("inconclusive" if persist is None else ("supported" if persist else "not_supported"))
    return {"n_days": len(days), "days": days, "verdict": verdict,
            "reason": f"day one {d0['day']}: {d0['n_boxes']} boxes (SPX and SPXW, 60-120 DTE), mid box rate minus bill median {d0['median_bp']:+.0f} bp (95% CI {d0['ci_bp'][0]:+.0f} to {d0['ci_bp'][1]:+.0f}); needs [15, 80] with CI in [0, 120]" + ("" if persist is not None else f"; persistence needs 20 capture days ({len(days)} so far)") + "; the CI resamples boxes that share strikes, so it understates uncertainty"}


def box_borrow_v2(captures, dtb3_rows) -> dict:
    """T-506: median executable short-box borrowing rate (180-730 DTE) minus the bill < 50 bp on day one and on >= 80% of capture days."""
    d3 = index_closes(dtb3_rows); days = []
    for day, spot, rows in captures:
        bx = [b for b in _boxes_v2(rows, spot, day, (180, 730), step=25) if b["r_borrow"] is not None]
        if bx:
            m = float(np.median([(b["r_borrow"] - _bill_cont(d3, day)) * 1e4 for b in bx])); days.append({"day": day, "n_boxes": len(bx), "median_bp": m, "pass": m < 50})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX captures with 180-730 DTE boxes on this machine"}
    d0 = days[0]; share = sum(d["pass"] for d in days) / len(days)
    verdict = "not_supported" if not d0["pass"] else ("supported" if len(days) >= 20 and share >= 0.8 else "inconclusive")
    return {"n_days": len(days), "days": days, "verdict": verdict,
            "reason": f"day one {d0['day']}: executable short-box borrowing rate is bill {d0['median_bp']:+.0f} bp over {d0['n_boxes']} boxes (needs < +50 bp)"}


def parity_v2(captures, dtb3_rows, n_side: int = 5, n_boot: int = 2000, seed: int = 0) -> dict:
    """T-505: SPX chain split by root (SPX, SPXW); per (root, expiry) the 2*n_side strikes nearest spot; F_impl = K + (C_mid - P_mid) e^{rT};
    exceedance when |F_impl - median F_impl| > 0.5 e^{rT} (spread_c + spread_p). Day-one share < 2% with a one-sided 95% bootstrap bound
    < 2%; still < 2% on >= 16 of the first 20 capture days."""
    d3 = index_closes(dtb3_rows); rng = np.random.default_rng(seed); days = []
    for day, spot, rows in captures:
        r = _bill_cont(d3, day); cap = datetime.strptime(day, "%Y-%m-%d"); flags = []
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
            days.append({"day": day, "pairs": int(f.size), "share": float(f.mean()), "upper95": float(np.quantile(bs, 0.95)), "pass": bool(f.mean() < 0.02 and np.quantile(bs, 0.95) < 0.02)})
    if not days:
        return {"n_days": 0, "verdict": "inconclusive", "reason": "no SPX captures on this machine"}
    d0 = days[0]
    verdict = "not_supported" if not d0["pass"] else ("inconclusive" if len(days) < 20 else ("supported" if sum(d["share"] < 0.02 for d in days[:20]) >= 16 else "not_supported"))
    return {"n_days": len(days), "days": days, "verdict": verdict,
            "reason": f"day one {d0['day']}: {d0['share']*100:.1f}% of {d0['pairs']} SPX/SPXW (K,T) pairs have an implied forward outside the half-spread band around the expiry median (one-sided 95% bound {d0['upper95']*100:.1f}%; needs < 2%)"}


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
