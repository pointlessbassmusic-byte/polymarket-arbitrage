"""
Batch 11, group ``xasset``: month-end flow effects in Treasuries and FX (T-574, T-575), 2026-10-20.
===================================================================================================

  * T-574  Synthetic 10-year Treasury total return from FRED DGS10, 1990-01..2026-09: r_t = y_{t-1}/100/252 -
           D(y_{t-1}) (y_t - y_{t-1})/100, D the modified duration of a 10-year semi-annual par bond at y_{t-1}. Month-end
           = the last observation of each calendar month. Statistic: mean on month-end days minus mean on other days
           (bps). Pass: >= 1 bp with one-sided p < 0.05 (studentized circular block bootstrap, 21 days, of the paired
           series d_t = r_t (f_t / p - (1 - f_t) / (1 - p)), whose mean is the difference) and both halves positive.
  * T-575  Equal-weight basket of EUR, JPY, GBP, CHF, CAD, AUD, NZD, SEK, NOK vs USD (FRED noon rates), daily log change
           on days every currency prints, 2000-01..2026-09: the last two trading days of each month against other days.
           Pass: >= 2 bp with one-sided p < 0.05 and both halves positive.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Optional

import numpy as np

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6b_bw import _decide

SEED = 0
BLOCK = 21
G10 = ("EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK")


def _missing(archive, names):
    miss = [n for n in names if not B7C._has(archive, n)]
    return _out({"missing": miss}, 0, "inconclusive", f"missing bundles: {', '.join(miss)} (rule 9)") if miss else None


def _series(archive, name: str) -> tuple:
    rows = sorted(((r["value"]["day"], r["value"]["value"]) for r in archive.load(name)
                   if isinstance(r.get("value"), dict) and r["value"].get("value") is not None), key=lambda x: x[0])
    return [d for d, _ in rows], np.array([float(v) for _, v in rows])


def mod_duration(y: float, years: int = 10) -> float:
    """Modified duration of a semi-annual par bond at yield y (percent)."""
    i = max(y, 0.01) / 200
    n = 2 * years
    mac = (1 + i) / i * (1 - (1 + i) ** -n) / 2          # Macaulay duration of a par bond, years
    return mac / (1 + i)


def synth_returns(days, y, start: str, end: str, years: int = 10) -> tuple:
    d_out, r = [], []
    for k in range(1, len(days)):
        if start <= days[k] <= end:
            d_out.append(days[k])
            r.append(y[k - 1] / 100 / 252 - mod_duration(y[k - 1], years) * (y[k] - y[k - 1]) / 100)
    return d_out, np.array(r)


def last_n_flags(days, n: int) -> np.ndarray:
    by = defaultdict(list)
    for i, d in enumerate(days):
        by[d[:7]].append(i)
    f = np.zeros(len(days), bool)
    for idx in by.values():
        f[idx[-n:]] = True
    return f


def flag_test(days, x, flags, bar: float, split: str, min_n: int, unit: str, n_boot: Optional[int] = None) -> dict:
    x, f = np.asarray(x, float), np.asarray(flags, bool)
    p = f.mean()
    diff = float(x[f].mean() - x[~f].mean())
    d = x * np.where(f, 1 / p, -1 / (1 - p)) - bar * 1e-4                   # mean = diff - bar
    pg, pl, dr = CAL.studentized_p_escalated(d, BLOCK, n_boot, SEED, B7C.N_SEEDS)
    halves = []
    for m in (np.array([dd < split for dd in days]), np.array([dd >= split for dd in days])):
        halves.append(float(x[m & f].mean() - x[m & ~f].mean()))
    crit = [(f"flag-day minus other-day mean {diff * 1e4:+.2f} bps >= {bar} bp with one-sided p < 0.05 (p {B7C._mc(pg, dr)})",
             B7C._sig_crit(diff - bar * 1e-4, pg, dr), CAL.decide_p(pl, dr) is True),
            (f"both halves positive (split {split}: {halves[0] * 1e4:+.2f} / {halves[1] * 1e4:+.2f} bps)", all(h > 0 for h in halves), False)]
    n = int(f.sum())
    v, why = _decide(crit, n, min_n, unit)
    return {"n_flag": n, "n_other": int((~f).sum()), "mean_flag_bps": float(x[f].mean() * 1e4),
            "mean_other_bps": float(x[~f].mean() * 1e4), "diff_bps": diff * 1e4, "p": pg, "halves_bps": [h * 1e4 for h in halves],
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b11_xasset_treasury_month_end(archive):
    """T-574."""
    miss = _missing(archive, ["fred-DGS10", "fred-DGS2"])
    if miss:
        return miss
    d10, y10 = _series(archive, "fred-DGS10")
    days, r = synth_returns(d10, y10, "1990-01-01", "2026-09-30")
    j = flag_test(days, r, last_n_flags(days, 1), 1.0, "2008-01-01", 400, "month-ends")
    d2, y2 = _series(archive, "fred-DGS2")
    dd2, r2 = synth_returns(d2, y2, "1990-01-01", "2026-09-30", years=2)
    f2 = last_n_flags(dd2, 1)
    two = float((r2[f2].mean() - r2[~f2].mean()) * 1e4)
    l2 = last_n_flags(days, 2) & ~last_n_flags(days, 1)
    first2 = np.zeros(len(days), bool)
    seen = defaultdict(int)
    for i, dd in enumerate(days):
        seen[dd[:7]] += 1
        first2[i] = seen[dd[:7]] <= 2
    reason = (f"synthetic 10Y total return (FRED DGS10, par-bond duration) {days[0]}..{days[-1]}: month-end "
              f"{j['mean_flag_bps']:+.2f} vs other days {j['mean_other_bps']:+.2f} bps ({j['n_flag']} month-ends), "
              f"difference {j['diff_bps']:+.2f} bps; halves {j['halves_bps'][0]:+.2f} / {j['halves_bps'][1]:+.2f}; "
              f"reported: 2Y note month-end difference {two:+.2f} bps, second-to-last day {r[l2].mean() * 1e4 - r[~l2].mean() * 1e4:+.2f}, "
              f"first two days {r[first2].mean() * 1e4 - r[~first2].mean() * 1e4:+.2f} bps")
    stat = {k: j[k] for k in ("n_flag", "mean_flag_bps", "mean_other_bps", "diff_bps", "p", "halves_bps", "criteria")} | {"two_year_diff_bps": two}
    return _out(stat, j["n_flag"], j["verdict"], reason + " — " + j["why"])


def basket_returns(archive, start: str, end: str) -> tuple:
    by = defaultdict(dict)
    for r in archive.load("fx-spot-g10"):
        v = r.get("value") or {}
        if v.get("ccy") in G10 and v.get("usd_per_unit"):
            by[v["day"]][v["ccy"]] = float(v["usd_per_unit"])
    days = sorted(d for d in by if len(by[d]) == len(G10))
    out_d, x, per = [], [], {c: [] for c in G10}
    for a, b in zip(days[:-1], days[1:]):
        if start <= b <= end:
            ch = {c: math.log(by[b][c] / by[a][c]) for c in G10}
            out_d.append(b); x.append(float(np.mean(list(ch.values()))))
            for c in G10:
                per[c].append(ch[c])
    return out_d, np.array(x), {c: np.array(v) for c, v in per.items()}


def b11_xasset_usd_month_end(archive):
    """T-575."""
    miss = _missing(archive, ["fx-spot-g10"])
    if miss:
        return miss
    days, x, per = basket_returns(archive, "2000-01-01", "2026-09-30")
    f = last_n_flags(days, 2)
    j = flag_test(days, x, f, 2.0, "2013-01-01", 600, "month-end days")
    pc = {c: float((v[f].mean() - v[~f].mean()) * 1e4) for c, v in per.items()}
    reason = (f"equal-weight G10-vs-USD basket {days[0]}..{days[-1]} ({len(days)} days): last two days of the month "
              f"{j['mean_flag_bps']:+.2f} vs other days {j['mean_other_bps']:+.2f} bps, difference {j['diff_bps']:+.2f} bps; "
              f"halves {j['halves_bps'][0]:+.2f} / {j['halves_bps'][1]:+.2f}; per currency "
              + ", ".join(f"{c} {v:+.1f}" for c, v in pc.items()) + f"; {sum(v > 0 for v in pc.values())} of 9 positive")
    stat = {k: j[k] for k in ("n_flag", "mean_flag_bps", "mean_other_bps", "diff_bps", "p", "halves_bps", "criteria")} | {"per_currency_bps": pc}
    return _out(stat, j["n_flag"], j["verdict"], reason + " — " + j["why"])


HARNESSES = {"b11_xasset_treasury_month_end": b11_xasset_treasury_month_end,
             "b11_xasset_usd_month_end": b11_xasset_usd_month_end}
THEORY_MAP = {"T-574": "b11_xasset_treasury_month_end", "T-575": "b11_xasset_usd_month_end"}
