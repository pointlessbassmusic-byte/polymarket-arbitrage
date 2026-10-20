"""
Batch 9, group ``signal``: three tests drawn from the signal map (mandel/viz/graph.json), 2026-10-20.
====================================================================================================

The map's concepts with the most source support and no market test, each turned into a decision a live sleeve makes:

  * T-569  (tension 'discrete Markov regimes (11, 13) versus continuous, scale-dependent multifractal roughness')
           One-day-ahead variance of daily log returns (adjclose) for SPY, QQQ and IWM, 2003-01..2026-09: a k=4 binomial
           Markov-switching multifractal (Calvet-Fisher; mandel.experiments.msm, grid fit) against the two-state Gaussian
           HMM (mandel.experiments.hmm_states), both refitted every January on all prior returns and read one step ahead
           (predicted, never smoothed). Loss QLIKE L = r^2/h + log h; d = L_hmm - L_msm per day; studentized circular
           block bootstrap (20 days) of mean d > 0; Holm over the three ETFs. Pass: all three Holm p < 0.05.
  * T-570  (concepts 'fractal dimension / roughness', 'Hurst') The IBS reversal (IBS < 0.2 at the close, hold to the
           next close) on SPY, QQQ, IWM, 2003-01..2026-09, split by the DFA Hurst exponent of the trailing 250 daily
           log returns through the signal close: trades when H < 0.5 against trades when H >= 0.5, pooled. Pass: the
           pooled mean difference > 0 with date-block bootstrap p < 0.05 and both halves of the sample positive.
  * T-571  (concepts 'Kelly / bet sizing', tension 'edge in bits as Kelly growth versus never full Kelly on an estimated
           edge') The calendar sleeve's three slots as daily return streams (overnight QQQ, IBS SPY, turn-of-month SPY;
           1 bp a side when traded): fixed weights 0.40 / 0.30 / 0.30 against half-Kelly weights 0.5 x inv(Sigma) mu
           estimated each month-end on all prior daily returns (long-only; scaled down to sum 1 when above 1; no
           leverage), 2006-01..2026-09. Pass: mean daily log growth of the Kelly sleeve > the fixed sleeve with paired
           block-bootstrap p < 0.05, both halves positive.

Rule 5: below min_n never supported. Rule 9: a missing bundle is inconclusive.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch4_ohlc as OHLC
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import hmm_states as MK
from mandel.experiments import msm as MSM
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6b_bw import _decide
from mandel.experiments.scaling import hurst_dfa

SEED = 0
START, END = "2003-01-01", "2026-09-30"
ETFS = ("SPY", "QQQ", "IWM")
BLOCK = 20
T569_MIN_N = 5000
T570_MIN_N = 1000
T570_WIN = 250
T570_IBS = 0.2
T571_START = "2006-01-01"
T571_FIXED = (0.40, 0.30, 0.30)
T571_KELLY_FRACTION = 0.5
T571_MIN_N = 4000
COST_SIDE = 1e-4


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not B7C._has(archive, n)]
    if miss:
        return _out({"missing": miss}, 0, "inconclusive", f"missing bundles: {', '.join(miss)} (rule 9)")
    return None


def _p(d, n_boot: Optional[int] = None) -> tuple:
    return CAL.studentized_p_escalated(np.asarray(d, float), BLOCK, n_boot, SEED, B7C.N_SEEDS)


# ------------------------------------------------------------------------------------------------- T-569 --

def forecasts(days: Sequence[str], adj, start: str = START, end: str = END) -> dict:
    """One-step variance forecasts of both models for every return day in [start, end]."""
    days = list(days)
    px = np.asarray(adj, float)
    rd = days[1:]
    r = np.log(px[1:] / px[:-1])
    out_d, rr, h_hmm, h_msm = [], [], [], []
    for y in range(int(start[:4]), int(end[:4]) + 1):
        tr = np.array([d < f"{y}-01-01" for d in rd])
        if tr.sum() < 750:
            continue
        hm = MK.fit(r[tr])
        ms = MSM.fit_msm(r[tr], 4)
        upto = np.array([d <= f"{y}-12-31" for d in rd])
        rr_all = r[upto]
        # HMM: filtered P(high) through t-1, one step ahead -> variance for day t
        p = MK.filter_probs(rr_all, hm)
        _, cv = MSM.filter_loglik(rr_all, 4, ms["m0"], ms["gamma1"], ms["b"], ms["sigma"])   # cv[t] predicted for t
        sel = [i for i, d in enumerate(np.array(rd)[upto]) if d[:4] == str(y) and start <= d <= end and i >= 1]
        for i in sel:
            out_d.append(rd[i]); rr.append(rr_all[i])
            h_hmm.append(MK.one_step_sigma(float(p[i - 1]), hm) ** 2)
            h_msm.append(float(cv[i]))
    return {"days": out_d, "r": np.array(rr), "hmm": np.array(h_hmm), "msm": np.array(h_msm)}


def qlike(r, h) -> np.ndarray:
    h = np.maximum(np.asarray(h, float), 1e-12)
    return np.asarray(r, float) ** 2 / h + np.log(h)


def msm_vs_hmm(per: dict, min_n: int = T569_MIN_N, n_boot: Optional[int] = None) -> dict:
    rep, ps = {}, []
    for s, f in per.items():
        d = qlike(f["r"], f["hmm"]) - qlike(f["r"], f["msm"])
        pg, pl, dr = _p(d, n_boot)
        ps.append(pg)
        rep[s] = {"n": int(d.size), "first": f["days"][0] if f["days"] else None, "last": f["days"][-1] if f["days"] else None,
                  "mean_d": float(d.mean()), "p": pg, "p_less": pl, "draws": dr,
                  "qlike_hmm": float(qlike(f["r"], f["hmm"]).mean()), "qlike_msm": float(qlike(f["r"], f["msm"]).mean())}
    hp = B7C.holm(ps)
    crit = []
    for (s, r), h in zip(rep.items(), hp):
        r["holm_p"] = h
        crit.append((f"{s}: QLIKE(HMM) - QLIKE(MSM) {r['mean_d']:+.4f} > 0 with Holm p < 0.05 (Holm p {B7C._mc(h, r['draws'])})",
                     B7C._sig_crit(r["mean_d"], h, r["draws"]), CAL.decide_p(r["p_less"], r["draws"]) is True))
    n = min((r["n"] for r in rep.values()), default=0)
    v, why = _decide(crit, n, min_n, "days (the shortest ETF)")
    return {"n": n, "per_etf": rep, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b9_signal_msm_vs_hmm(archive):
    """T-569."""
    miss = _missing(archive, [B7C.dh(s) for s in ETFS])
    if miss:
        return miss
    per = {}
    for s in ETFS:
        b = OHLC._bars(archive, s)
        per[s] = forecasts(b.days, b.adj)
    j = msm_vs_hmm(per)
    parts = [f"{s} {r['first']}..{r['last']} ({r['n']} days): QLIKE HMM {r['qlike_hmm']:.4f} vs MSM {r['qlike_msm']:.4f}, "
             f"difference {r['mean_d']:+.4f} (p {B7C._mc(r['p'], r['draws'])}, Holm {B7C._mc(r['holm_p'], r['draws'])})"
             for s, r in j["per_etf"].items()]
    stat = {k: j[k] for k in ("per_etf", "criteria")} | {"loss": "QLIKE r^2/h + log h", "refit": "every January, all prior returns",
                                                          "forecast": "one step ahead (predicted), no smoothing"}
    return _out(stat, j["n"], j["verdict"], "; ".join(parts) + " — " + j["why"])


# ------------------------------------------------------------------------------------------------- T-570 --

def ibs_hurst_trades(b, start: str = START, end: str = END, win: int = T570_WIN) -> list:
    """(signal day, next-day return, H) for every IBS < 0.2 close in [start, end] with a full trailing window."""
    days = list(b.days)
    H, L, C, A = (np.asarray(x, float) for x in (b.high, b.low, b.close, b.adj))
    logp = np.log(A)
    out = []
    for t in range(win, len(days) - 1):
        if not (start <= days[t] <= end) or H[t] <= L[t]:
            continue
        ibs = (C[t] - L[t]) / (H[t] - L[t])
        if ibs >= T570_IBS:
            continue
        h, _, _ = hurst_dfa(logp[t - win:t + 1])
        if not math.isfinite(h):
            continue
        out.append((days[t], float(A[t + 1] / A[t] - 1), h))
    return out


def hurst_split(trades: dict, min_n: int = T570_MIN_N, n_boot: Optional[int] = None) -> dict:
    rows = sorted((d, s, r, h) for s, tr in trades.items() for d, r, h in tr)
    lo = np.array([r for _, _, r, h in rows if h < 0.5]); hi = np.array([r for _, _, r, h in rows if h >= 0.5])
    n = len(rows)
    diff = float(lo.mean() - hi.mean()) if lo.size and hi.size else None
    # bootstrap the difference by resampling months (date blocks): a signed contribution series per trade
    w_lo, w_hi = (1 / lo.size if lo.size else 0), (1 / hi.size if hi.size else 0)
    contrib = np.array([r * (w_lo if h < 0.5 else -w_hi) * n for _, _, r, h in rows])
    pg, pl, dr = _p(contrib, n_boot) if n >= 8 else (None, None, 0)
    mid = rows[n // 2][0] if n else None
    halves = []
    for part in (rows[:n // 2], rows[n // 2:]):
        a = [r for _, _, r, h in part if h < 0.5]; c = [r for _, _, r, h in part if h >= 0.5]
        halves.append(float(np.mean(a) - np.mean(c)) if a and c else None)
    crit = [(f"pooled IBS next-day return, H < 0.5 minus H >= 0.5: {_bp(diff)} > 0 with p < 0.05 (p {B7C._mc(pg, dr)})",
             None if diff is None else B7C._sig_crit(diff, pg, dr), CAL.decide_p(pl, dr) is True),
            (f"both halves positive (split {mid}: {_bp(halves[0])} / {_bp(halves[1])})",
             None if None in halves else all(h > 0 for h in halves), False)]
    v, why = _decide(crit, n, min_n, "IBS trades")
    per = {s: {"n": len(tr), "share_low_H": float(np.mean([h < 0.5 for _, _, h in tr])) if tr else None,
               "mean_low": _m([r for _, r, h in tr if h < 0.5]), "mean_high": _m([r for _, r, h in tr if h >= 0.5])}
           for s, tr in trades.items()}
    return {"n": n, "n_low": int(lo.size), "n_high": int(hi.size), "mean_low": _m(lo), "mean_high": _m(hi), "diff": diff,
            "p": pg, "halves": halves, "per_etf": per, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _m(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(x.mean()) if x.size else None


def _bp(x) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x * 1e4:+.2f} bps"


def b9_signal_ibs_hurst_regime(archive):
    """T-570."""
    miss = _missing(archive, [B7C.dh(s) for s in ETFS])
    if miss:
        return miss
    trades = {s: ibs_hurst_trades(OHLC._bars(archive, s)) for s in ETFS}
    j = hurst_split(trades)
    reason = (f"IBS < {T570_IBS} closes on {', '.join(ETFS)} {START[:4]}..{END[:7]} with a trailing {T570_WIN}-return DFA "
              f"Hurst exponent: {j['n']} trades ({j['n_low']} with H < 0.5, {j['n_high']} with H >= 0.5); next-day return "
              f"{_bp(j['mean_low'])} vs {_bp(j['mean_high'])}, difference {_bp(j['diff'])}; per ETF "
              + "; ".join(f"{s} {r['n']} trades, {r['share_low_H'] * 100:.0f}% low-H, {_bp(r['mean_low'])} vs {_bp(r['mean_high'])}"
                          for s, r in j["per_etf"].items() if r["n"]))
    stat = {k: j[k] for k in ("n_low", "n_high", "mean_low", "mean_high", "diff", "p", "halves", "per_etf", "criteria")}
    return _out(stat, j["n"], j["verdict"], reason + " — " + j["why"])


# ------------------------------------------------------------------------------------------------- T-571 --

def slot_returns(spy, qqq, start: str = T571_START, end: str = END) -> dict:
    """Daily net returns of the three calendar slots on the sessions both ETFs share, dated by the session they end on."""
    sd, qd = list(spy.days), list(qqq.days)
    qpos = {d: i for i, d in enumerate(qd)}
    A, H, L, C = (np.asarray(x, float) for x in (spy.adj, spy.high, spy.low, spy.close))
    qn = B7C.night_day(qqq, qd[1], "9999-12-31")
    night = dict(zip([str(d) for d in qn["ds"]], qn["night"]))
    tom, _ = B7C.tom_flags(sd)
    out_d, R = [], []
    for t in range(1, len(sd)):
        d = sd[t]
        if d not in qpos or d not in night:
            continue
        r_spy = A[t] / A[t - 1] - 1
        ibs_prev = (C[t - 1] - L[t - 1]) / (H[t - 1] - L[t - 1]) if H[t - 1] > L[t - 1] else 1.0
        r_on = night[d] - 2 * COST_SIDE
        r_ibs = (r_spy - 2 * COST_SIDE) if ibs_prev < T570_IBS else 0.0
        r_tom = r_spy if tom[t] else 0.0
        if tom[t] and not tom[t - 1]:
            r_tom -= 2 * COST_SIDE                      # one round trip per window, charged on entry
        out_d.append(d); R.append((r_on, r_ibs, r_tom))
    R = np.array(R)
    m = np.array([start <= d <= end for d in out_d])
    return {"days_all": out_d, "R_all": R, "days": [d for d, k in zip(out_d, m) if k], "R": R[m]}


def kelly_weights(R_hist: np.ndarray, fraction: float = T571_KELLY_FRACTION) -> np.ndarray:
    mu = R_hist.mean(0)
    S = np.cov(R_hist.T) + np.eye(R_hist.shape[1]) * 1e-10
    w = fraction * np.linalg.solve(S, mu)
    w = np.clip(w, 0, None)
    s = w.sum()
    return w / s if s > 1 else w


def kelly_vs_fixed(sr: dict, min_n: int = T571_MIN_N, n_boot: Optional[int] = None) -> dict:
    days_all, R_all = sr["days_all"], sr["R_all"]
    pos = {d: i for i, d in enumerate(days_all)}
    fixed = np.array(T571_FIXED)
    g_k, g_f, W, cur_m, w = [], [], [], None, None
    for d in sr["days"]:
        i = pos[d]
        if d[:7] != cur_m:                              # month-start rebalance on returns strictly before
            cur_m = d[:7]
            w = kelly_weights(R_all[:i])
        W.append(w)
        g_k.append(math.log1p(float(R_all[i] @ w)))
        g_f.append(math.log1p(float(R_all[i] @ fixed)))
    g_k, g_f = np.array(g_k), np.array(g_f)
    d = g_k - g_f
    n = int(d.size)
    pg, pl, dr = _p(d, n_boot)
    h = n // 2
    halves = [float(d[:h].mean()), float(d[h:].mean())]
    ann = lambda g: float(g.mean() * 252)
    shp = lambda g: float(g.mean() / g.std(ddof=1) * math.sqrt(252)) if g.std() > 0 else None
    crit = [(f"mean daily log growth, Kelly - fixed {d.mean() * 1e4:+.3f} bps/day > 0 with p < 0.05 (p {B7C._mc(pg, dr)})",
             B7C._sig_crit(float(d.mean()), pg, dr), CAL.decide_p(pl, dr) is True),
            (f"both halves positive ({halves[0] * 1e4:+.3f} / {halves[1] * 1e4:+.3f} bps/day)", all(x > 0 for x in halves), False)]
    v, why = _decide(crit, n, min_n, "days")
    W = np.array(W)
    return {"n": n, "first": sr["days"][0], "last": sr["days"][-1], "growth_kelly_ann": ann(g_k), "growth_fixed_ann": ann(g_f),
            "sharpe_kelly": shp(g_k), "sharpe_fixed": shp(g_f), "mean_weights": W.mean(0).tolist(),
            "mean_invested": float(W.sum(1).mean()), "halves": halves, "p": pg,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b9_signal_kelly_calendar_weights(archive):
    """T-571."""
    miss = _missing(archive, [B7C.dh("SPY"), B7C.dh("QQQ")])
    if miss:
        return miss
    sr = slot_returns(OHLC._bars(archive, "SPY"), OHLC._bars(archive, "QQQ"))
    j = kelly_vs_fixed(sr)
    mw = j["mean_weights"]
    reason = (f"calendar sleeve slots (overnight QQQ, IBS SPY, turn-of-month SPY; 1 bp a side) {j['first']}..{j['last']} "
              f"({j['n']} days): half-Kelly weights re-estimated monthly on all prior days averaged {mw[0]:.2f} / {mw[1]:.2f} / "
              f"{mw[2]:.2f} (invested {j['mean_invested'] * 100:.0f}%) vs fixed 0.40 / 0.30 / 0.30; annual log growth "
              f"{j['growth_kelly_ann'] * 100:+.2f}% vs {j['growth_fixed_ann'] * 100:+.2f}%, Sharpe {j['sharpe_kelly']:.2f} vs "
              f"{j['sharpe_fixed']:.2f}")
    stat = {k: j[k] for k in ("first", "last", "growth_kelly_ann", "growth_fixed_ann", "sharpe_kelly", "sharpe_fixed",
                              "mean_weights", "mean_invested", "halves", "p", "criteria")}
    return _out(stat, j["n"], j["verdict"], reason + " — " + j["why"])


HARNESSES = {
    "b9_signal_msm_vs_hmm": b9_signal_msm_vs_hmm,
    "b9_signal_ibs_hurst_regime": b9_signal_ibs_hurst_regime,
    "b9_signal_kelly_calendar_weights": b9_signal_kelly_calendar_weights,
}

THEORY_MAP = {
    "T-569": "b9_signal_msm_vs_hmm",
    "T-570": "b9_signal_ibs_hurst_regime",
    "T-571": "b9_signal_kelly_calendar_weights",
}
