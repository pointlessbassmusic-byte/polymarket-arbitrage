"""
Batch 10, group ``calib``: per-model calibration (T-572), 2026-10-20.
=====================================================================

  * T-572  For SPY, QQQ and IWM daily log returns (adjclose) 2003-01..2026-09: the two-state Gaussian HMM refitted
           EVERY DAY on all returns before the day (EM warm-started from the previous day's fit) against the same model
           refitted every January, on the QLIKE loss (r^2/h + log h) of the one-day-ahead variance forecast. Both
           forecasts use returns through the previous close only. d = QLIKE(yearly) - QLIKE(daily); studentized circular
           block bootstrap (20 days); Holm over the three ETFs. Pass: all three Holm p < 0.05.
           Reported: how far the daily parameters drift from the January fit within each year (daily vol of each state,
           stay probabilities) and the T-562 scaled-overnight Sharpe of QQQ under each refit.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from mandel.experiments import batch4_ohlc as OHLC
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch7_cal as B7C
from mandel.experiments import batch9_signal as B9
from mandel.experiments import hmm_states as MK
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6b_bw import _decide

START, END = "2003-01-01", "2026-09-30"
ETFS = ("SPY", "QQQ", "IWM")
MIN_N = 5000


def _forward_var(x: np.ndarray, h: MK.HMM2) -> float:
    """One-step-ahead variance after filtering over all of ``x``."""
    p = MK.filter_probs(x, h)[-1] if len(x) else h.pi[1]
    return MK.one_step_sigma(float(p), h) ** 2


def refit_forecasts(days, adj, start: str = START, end: str = END) -> dict:
    days = list(days)
    px = np.asarray(adj, float)
    rd = days[1:]
    r = np.log(px[1:] / px[:-1])
    idx = [i for i, d in enumerate(rd) if start <= d <= end]
    yearly: dict = {}
    daily_fit = None
    out = {"days": [], "r": [], "yearly": [], "daily": [], "drift": []}
    for i in idx:
        y = int(rd[i][:4])
        if y not in yearly:
            m = np.array([d < f"{y}-01-01" for d in rd])
            if m.sum() < 750:
                continue
            yearly[y] = MK.fit(r[m])
        hist = r[:i]
        daily_fit = MK.fit(hist, max_iter=50, init=daily_fit or yearly[y])
        hy = yearly[y]
        # yearly forecast: filter with the January fit over all returns before day i (the batch-8 convention)
        out["days"].append(rd[i]); out["r"].append(r[i])
        out["yearly"].append(_forward_var(hist, hy))
        out["daily"].append(_forward_var(hist, daily_fit))
        out["drift"].append([math.sqrt(daily_fit.var[0]) - math.sqrt(hy.var[0]), math.sqrt(daily_fit.var[1]) - math.sqrt(hy.var[1]),
                             daily_fit.P[1][1] - hy.P[1][1]])
    return {k: (np.array(v) if k != "days" else v) for k, v in out.items()}


def daily_vs_yearly(per: dict, min_n: int = MIN_N, n_boot: Optional[int] = None) -> dict:
    rep, ps = {}, []
    for s, f in per.items():
        d = B9.qlike(f["r"], f["yearly"]) - B9.qlike(f["r"], f["daily"])
        pg, pl, dr = CAL.studentized_p_escalated(d, B9.BLOCK, n_boot, B9.SEED, B7C.N_SEEDS)
        ps.append(pg)
        dr_abs = np.abs(f["drift"])
        rep[s] = {"n": int(d.size), "first": f["days"][0], "last": f["days"][-1], "mean_d": float(d.mean()), "p": pg,
                  "p_less": pl, "draws": dr, "qlike_yearly": float(B9.qlike(f["r"], f["yearly"]).mean()),
                  "qlike_daily": float(B9.qlike(f["r"], f["daily"]).mean()),
                  "median_abs_drift": {"vol_low": float(np.median(dr_abs[:, 0])), "vol_high": float(np.median(dr_abs[:, 1])),
                                       "stay_high": float(np.median(dr_abs[:, 2]))},
                  "p95_abs_drift_vol_high": float(np.percentile(dr_abs[:, 1], 95))}
    hp = B7C.holm(ps)
    crit = []
    for (s, r), h in zip(rep.items(), hp):
        r["holm_p"] = h
        crit.append((f"{s}: QLIKE(yearly) - QLIKE(daily) {r['mean_d']:+.5f} > 0 with Holm p < 0.05 (Holm p {B7C._mc(h, r['draws'])})",
                     B7C._sig_crit(r["mean_d"], h, r["draws"]), CAL.decide_p(r["p_less"], r["draws"]) is True))
    n = min((r["n"] for r in rep.values()), default=0)
    v, why = _decide(crit, n, min_n, "days (the shortest ETF)")
    return {"n": n, "per_etf": rep, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b10_calib_hmm_daily_vs_yearly(archive):
    """T-572."""
    miss = B9._missing(archive, [B7C.dh(s) for s in ETFS])
    if miss:
        return miss
    per = {}
    for s in ETFS:
        b = OHLC._bars(archive, s)
        per[s] = refit_forecasts(b.days, b.adj)
    j = daily_vs_yearly(per)
    parts = [f"{s} {r['first']}..{r['last']} ({r['n']} days): QLIKE yearly {r['qlike_yearly']:.5f} vs daily {r['qlike_daily']:.5f}, "
             f"difference {r['mean_d']:+.5f} (p {B7C._mc(r['p'], r['draws'])}, Holm {B7C._mc(r['holm_p'], r['draws'])}); daily "
             f"parameters drift from the January fit by a median {r['median_abs_drift']['vol_high'] * 100:.3f} pts of daily "
             f"high-state vol (95th pct {r['p95_abs_drift_vol_high'] * 100:.3f}), {r['median_abs_drift']['stay_high']:.4f} in "
             f"the high-state stay probability" for s, r in j["per_etf"].items()]
    stat = {k: j[k] for k in ("per_etf", "criteria")} | {"loss": "QLIKE", "forecast": "one step ahead, returns through the previous close"}
    return _out(stat, j["n"], j["verdict"], "; ".join(parts) + " — " + j["why"])


HARNESSES = {"b10_calib_hmm_daily_vs_yearly": b10_calib_hmm_daily_vs_yearly}
THEORY_MAP = {"T-572": "b10_calib_hmm_daily_vs_yearly"}
