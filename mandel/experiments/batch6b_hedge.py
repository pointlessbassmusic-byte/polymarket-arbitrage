"""
Batch 6b, group ``hedge``: Cboe hedged-overlay benchmark indices (collars, protective puts, iron butterfly / condor,
VIX tail hedge), the Black-Scholes replication of BXM and PUT, and the VIX call credit spread settled at the SOQ.
=====================================================================================================================

Eight options-library claims, each tested against its claim, trial.pass and trial.min_n as worded:
  * T-166 CLL 95-110 collar CAGR vs a beta-matched SPY-TR / T-bill blend, 2008-08..2026-10 (95% CI < 0);
  * T-168 CLLZ zero-cost put-spread collar monthly Sharpe vs SPY TR, 1993-02..2026-10 (point <= 0, CI upper <= 0.05);
  * T-169 PPUT 5% protective put CAGR vs a beta-matched SPY-TR / T-bill blend, 1993-02..2026-10 (95% CI < -1%/yr);
  * T-178 BFLY minus CNDR monthly Sharpe, 1986-06..2026-10 (95% CI < 0, same sign pre/post 2008);
  * T-179 CNDR roll-to-roll excess return on (VIX - trailing 21-day SPX RV) at the 3rd-Friday roll, 1990-2026 (CI > 0,
    same sign in both halves);
  * T-180 MODEL-PRICED Black-Scholes overlay (VIX as IV, DTB3) reproducing BXM (2002-) and PUT (2007-) monthly returns
    (R^2 > 0.95 and TE < 2%/yr for both; BXMD and CNDR shortfalls documented);
  * T-528 VXTH vs SPY TR (and PPUT3M) daily maximum drawdowns on the common 2006-03 onward sample (90% CI > 10 points);
  * T-220 MODEL-PRICED VIX call credit spread (short front VX future + 2, long + 5) sold 3 trading days before the
    monthly SOQ when VIX3M/VIX > 1.1, settled at VRO, return on max loss net of half-spreads (95% CI > 0).

Data (all loaded through ``archive.load``; a bar is used only if its ``available_at`` precedes the bundle's capture):
  * ``cboe-<SYM>-history`` (mandel.data.cboe_strategy): published index levels. Flags are applied as the module says: a
    row on a market-closed day or a one-day bad print is dropped; a known level step ("splice", CLL 2009-10-16: -19.8%
    while SPX fell 0.8%) is a BREAK: the one return ending on that day is excluded from EVERY leg of the paired panel
    (strategy, benchmark and bill), so nothing is compounded across it. The as-published compounding is reported.
  * BACK-TESTED HISTORY. Every Cboe index here launched after the start of its claim's window (INDEX_META, section 5 of
    each methodology): CLL 2008-09-30, VXTH 2011-07-29, CLLZ / PPUT / BFLY / CNDR / BXMD 2015-08-03, PPUT3M 2021-08-02,
    BXM 2002-04-30, PUT 2007-06-20. Rows before launch are Cboe's back-test (``backtest: true``), dated as published on
    the launch day. None of these claims is about what a trader could have known (they compare index histories), so
    back-tested rows are used and each reason states the share of the window that is back-tested.
  * SPY total return = Yahoo ``adjclose``; ^GSPC raw closes (and opens for the SOQ-settlement sensitivity) for SPX.
  * T-bills: FRED DTB3, a 91-day discount yield published a day late: the print dated strictly before a day is the rate
    known at that day's close, converted to a continuous rate r = -ln(1 - d/100 * 91/360) / (91/365); a period earns
    exp(r * calendar days / 365) - 1 with r known at its start. T-179 names the 1-month bill, which FRED does not carry
    before 2001 (DTB4WK); DTB3 is the stated proxy and fed funds (DFF, act/360) and a zero rate are reported; the slope
    criterion is decided only when every rate choice agrees.
  * VIX, VIX3M, VVIX closes (cboe-*-history); VX futures daily settlements (cboe-vx-futures, monthly contracts, usable
    settles from 2013-05-20); VRO (VIX SOQ) rows with ``expiry`` set, not ``carried`` and no ``flag``; captured VIX option
    chains (options-chain-VIX-<date>, pre-open captures carrying the previous session's quotes) for half-spreads.

Conventions:
  * Calendars (house rule 10). Every claim names its calendar, so no grid phase is chosen: calendar month-ends (T-166,
    T-168, T-169, T-178: the trials say month-end returns; T-166's CSV has gaps, so a month's return compounds the daily
    returns between common days, which equals the month-end-to-month-end return), the 3rd-Friday SPX roll (T-179; T-180's
    simulated roll), the daily series (T-528) and the VIX monthly settlement Wednesdays (T-220).
  * Monthly panels are paired on a shared timeline: the days on which every leg has a close.
  * CAGR = growth^(1 / years) - 1 with years = calendar span / 365.25. A beta-matched blend is beta * SPY TR + (1 -
    beta) * bill rebalanced monthly; beta is the OLS slope of the strategy's monthly excess return on SPY's over the
    claim's own window (stated in the reason with the claim's approximate value). The CAGR-difference interval is a
    two-sided percentile circular block bootstrap of paired months (block 6; 12 reported) that re-estimates beta in every
    resample. The trial's out-of-sample variant (beta from the first half applied to the second) is reported.
  * Sharpe differences use excess returns over the bill and a studentized circular block bootstrap of the paired months
    with a delta-method Bartlett HAC s.e. (bandwidth = block = 6 months). "Monthly Sharpe ratio" is read as the Sharpe
    ratio of monthly returns, not annualised (T-168's 0.05 margin is on that scale; the annualised reading is reported).
  * T-179's slope interval is a studentized pairs block bootstrap (block 6 rolls) with a Bartlett HAC s.e.
  * T-528 resamples paired daily returns with the stationary bootstrap (mean block 63 days, as the trial says) and takes
    the percentile 90% CI of the maximum-drawdown difference in percentage points.
  * T-180 (MODEL-PRICED): BXM holds SPX total return and is short a 1-month call struck at the first 5-point strike at or
    above the roll close; PUT holds bill collateral equal to the strike and is short the put struck at the 5-point strike
    at or below the roll close; options are written at the 3rd-Friday close at Black-Scholes with sigma = VIX/100, r =
    DTB3 (continuous), q = trailing 12-month SPY dividends / SPY close (point in time), and settle on the RAW ^GSPC close
    of the next roll (house rule 8; settlement at the ^GSPC open, a proxy for the SOQ, is a sensitivity). The index is
    chained daily (BXM_t = BXM_{t-1} (S_t + Div_t - C_t) / (S_{t-1} - C_{t-1}), C marked at the day's VIX). SPX
    dividends are SPY's (adjclose/close steps) spread evenly over the SPX sessions since the previous SPY ex-date (SPY
    accrues its holdings' dividends and pays them quarterly); the lumped ex-date version and price-only SPX are reported.
    R^2 (squared correlation) and TE (sd of the monthly difference x sqrt 12) are computed on both monthly calendars a
    reader could mean: roll-to-roll periods and calendar month-ends. A criterion passes when both pass, fails when both
    fail, and is undecided (None) when they disagree. IV-scale sensitivity: 0.9 and 1.1 x VIX.
  * T-220 (MODEL-PRICED): entry at the close 3 trading days before each monthly VIX settlement (the VX futures expiry
    dates), F = the expiring VX future's settlement that day, K1 = F + 2 rounded to the nearest 1-point strike, K2 = K1 +
    5, Black-76 with sigma = VVIX/100 and T = (calendar days - 0.28) / 365 (16:15 ET to the 09:30 ET SOQ); the credit is
    reduced by one half-spread per leg measured on the captured VIX chains at the same strikes relative to F (today's
    spreads applied to history: an assumption); payoff min(max(VRO - K1, 0), 5); return = P&L / (5 - net credit). The gate
    uses the entry day's VIX3M and VIX closes (16:15 ET, the VIX options close; the prior-day gate is reported). IV
    scales 0.8 / 1.2 / 1.5, a chain-skew pricing (per-leg IV / VVIX measured on the captures), doubled half-spreads,
    unrounded strikes and the trial's controls are reported.
  * Seed and block robustness: no claim fixes a block length, so every CI-decided criterion is evaluated on several
    bootstrap variants (blocks 6 and 12 months x seeds 0-2; T-179 the same in rolls; T-528 seeds 0-2 at its named mean
    block of 63 days; T-220 blocks 3 and 6 trades x seeds 0-2). It passes only when every variant passes, fails when none
    does, and is MARGINAL (None, so at best inconclusive) when they disagree.
  * Live-only check: every index claim also reports its statistic on the months (rolls, days) after the index's launch,
    where no back-tested level enters. It is reported, not a criterion: the claims are worded over their full windows.
  * min_n is counted in the claim's own units (months, rolls, days, trades). Below min_n a claim is never supported and a
    failing criterion counts only when it fails decisively at the pass's own confidence (house rule 5).

Verdicts use ``underlying2._verdict``: any implemented criterion failing gives not_supported; any criterion not
implemented gives at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.underlying2 import _verdict
from mandel.options import bs
from mandel.validation.backtest_eval import _hac_var

PPY_M = 12
PPY_D = 252
SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
DTB3_B = "fred-DTB3"
DFF_B = "fred-DFF"
VIX_B = "cboe-VIX-history"
VIX3M_B = "cboe-VIX3M-history"
VVIX_B = "cboe-VVIX-history"
VX_B = "cboe-vx-futures"
VIX_CHAIN_P = "options-chain-VIX-"
MP = "MODEL-PRICED"
BLOCK_M = 6                      # monthly paired bootstrap block (months); 12 reported
N_BOOT = 4000

# Launch dates (mandel.data.cboe_strategy.INDEX_META, section 5 of each methodology), restated for the reasons.
LAUNCH = {"CLL": "2008-09-30", "CLLZ": "2015-08-03", "PPUT": "2015-08-03", "PPUT3M": "2021-08-02", "BFLY": "2015-08-03",
          "CNDR": "2015-08-03", "VXTH": "2011-07-29", "BXM": "2002-04-30", "PUT": "2007-06-20", "BXMD": "2015-08-03"}


def CB(sym: str) -> str:
    return f"cboe-{sym}-history"


# ================================================================================================= formatting ==

def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{100 * x:+.{nd}f}%"


def _pu(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{100 * x:.{nd}f}%"


def _ci_s(ci, nd: int = 2, scale: float = 1.0, unit: str = "") -> str:
    lo, hi = (list(ci) + [None, None])[:2] if ci is not None else (None, None)
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _wrap(rep: dict):
    return _out(rep.get("stat", {"verdict": rep["verdict"]}), rep.get("n", 0), rep["verdict"], rep["reason"])


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n a failing criterion counts only when it fails decisively (its
    bound at the pass's own confidence wholly on the wrong side); otherwise it is reported as not decisive (None).
    Appends the min_n criterion."""
    rows = []
    for name, ok, dec in crit:
        if ok is not None and not bool(ok) and n < min_n and not dec:
            rows.append((name + " [fails, not decisively, below min_n]", None))
        else:
            rows.append((name, None if ok is None else bool(ok)))
    rows.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    return _verdict(rows)


VARIANTS = ((BLOCK_M, 0), (BLOCK_M, 1), (BLOCK_M, 2), (12, 0), (12, 1), (12, 2))


def robust_decision(ci_fn, passes, fails_decisively, variants=VARIANTS) -> dict:
    """Decide a CI criterion so that neither the bootstrap seed nor the (undeclared) block length decides it: ``ci_fn(block,
    seed)`` -> (lo, hi) is evaluated on every variant; ok = True when every variant passes, False when none does, None
    (MARGINAL) when they disagree. ``decisive``: every variant fails decisively (rule 5)."""
    cis = [tuple(ci_fn(b, sd)) for b, sd in variants]
    oks = [None if lo is None or hi is None else bool(passes(lo, hi)) for lo, hi in cis]
    if any(o is None for o in oks):
        ok = None
    elif all(oks):
        ok = True
    elif not any(oks):
        ok = False
    else:
        ok = None
    dec = all(lo is not None and hi is not None and bool(fails_decisively(lo, hi)) for lo, hi in cis)
    return {"ok": ok, "decisive": dec, "n_pass": int(sum(bool(o) for o in oks)), "n_variants": len(variants),
            "variants": [list(v) for v in variants], "cis": [list(c) for c in cis]}


def _rob_txt(rd: dict) -> str:
    tag = "" if rd["ok"] is not None else ", MARGINAL: the bootstrap variants disagree"
    blocks = sorted({v[0] for v in rd["variants"]})
    what = "block length x seed" if len(blocks) > 1 else "seeds"
    return f"{rd['n_pass']}/{rd['n_variants']} bootstrap variants ({what}) pass{tag}"


def _live_month(sym: str) -> Optional[str]:
    """First calendar month wholly after the index's launch day ('YYYY-MM'), or None."""
    lau = LAUNCH.get(sym)
    if not lau:
        return None
    y, m = int(lau[:4]), int(lau[5:7])
    return f"{y + (m == 12):04d}-{m % 12 + 1:02d}"


def _bt_note(sym: str, first: str, last: str) -> str:
    """'SYM launched L: back-tested for x of y years of the window' (or 'all live')."""
    lau = LAUNCH.get(sym)
    if not lau or not first or not last:
        return ""
    a, b, c = (date.fromisoformat(d) for d in (first, min(max(lau, first), last), last))
    tot = max((c - a).days, 1)
    bt = (b - a).days
    if bt <= 0:
        return f"{sym} is live (launched {lau}) for the whole window"
    return (f"{sym} launched {lau}: its rows before then are Cboe's back-test, {bt / 365.25:.1f} of the window's "
            f"{tot / 365.25:.1f} years ({100 * bt / tot:.0f}%)")


# ================================================================================================= statistics ==

def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def _chunks(n_boot: int, n: int):
    k = max(1, min(n_boot, 2_000_000 // max(n, 1)))
    done = 0
    while done < n_boot:
        yield min(k, n_boot - done)
        done += k


def stud_ci(x, block: int, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> tuple:
    """Two-sided studentized circular block-bootstrap CI of the mean: (lo, hi), or (None, None) below 8 observations."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return None, None
    block = max(1, min(int(block), n // 4))
    m = float(x.mean())
    v0 = float(_hac_var(x[None, :], block)[0])
    if v0 <= 1e-30:
        return m, m
    se = math.sqrt(v0 / n)
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, n):
        xb = x[_boot_idx(rng, n, block, k)]
        ts.append((xb.mean(axis=1) - m) / np.sqrt(_hac_var(xb, block) / n))
    t = np.concatenate(ts)
    a = (1.0 - level) / 2.0
    return m - float(np.quantile(t, 1.0 - a)) * se, m - float(np.quantile(t, a)) * se


def _sr_diff_and_se(a: np.ndarray, b: np.ndarray, bw: int):
    """Row-wise per-period Sharpe(a) - Sharpe(b) and its delta-method HAC s.e. (Ledoit and Wolf 2008)."""
    n = a.shape[1]
    mu_a, mu_b = a.mean(axis=1), b.mean(axis=1)
    g_a, g_b = (a * a).mean(axis=1), (b * b).mean(axis=1)
    va, vb = np.maximum(g_a - mu_a ** 2, 1e-300), np.maximum(g_b - mu_b ** 2, 1e-300)
    d = mu_a / np.sqrt(va) - mu_b / np.sqrt(vb)
    grad = (1.0 / np.sqrt(va) + mu_a ** 2 / va ** 1.5, -(1.0 / np.sqrt(vb) + mu_b ** 2 / vb ** 1.5),
            -mu_a / (2 * va ** 1.5), mu_b / (2 * vb ** 1.5))
    z = (grad[0][:, None] * (a - mu_a[:, None]) + grad[1][:, None] * (b - mu_b[:, None])
         + grad[2][:, None] * (a * a - g_a[:, None]) + grad[3][:, None] * (b * b - g_b[:, None]))
    return d, np.sqrt(_hac_var(z, bw) / n)


def sharpe_diff_test(a, b, block: int = BLOCK_M, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> dict:
    """Per-period Sharpe(a) - Sharpe(b) on paired periods (population sd) with a two-sided studentized circular
    block-bootstrap CI at ``level`` and the one-sided p-value of H0: difference <= 0."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = a.size
    out = {"n": int(n), "diff": None, "se": None, "p_gt0": None, "ci": [None, None], "sr_a": None, "sr_b": None}
    if n < 8 or b.size != n:
        return out
    out["sr_a"] = float(a.mean() / a.std()) if a.std() > 0 else None
    out["sr_b"] = float(b.mean() / b.std()) if b.std() > 0 else None
    block = max(1, min(int(block), n // 4))
    d0, se0 = _sr_diff_and_se(a[None, :], b[None, :], block)
    d0, se0 = float(d0[0]), float(se0[0])
    out.update(diff=d0, se=se0)
    if not se0 > 1e-150:
        out.update(ci=[d0, d0], p_gt0=0.0 if d0 > 0 else 1.0)
        return out
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, 2 * n):
        idx = _boot_idx(rng, n, block, k)
        d, se = _sr_diff_and_se(a[idx], b[idx], block)
        ok = se > 1e-150
        ts.append((d[ok] - d0) / se[ok])
    t = np.concatenate(ts)
    al = (1.0 - level) / 2.0
    out["ci"] = [d0 - float(np.quantile(t, 1.0 - al)) * se0, d0 - float(np.quantile(t, al)) * se0]
    out["p_gt0"] = float((np.sum(t >= d0 / se0) + 1) / (t.size + 1))        # one-sided p of H0: difference <= 0
    return out


def _ols_slope_rows(X: np.ndarray, Y: np.ndarray, bw: int):
    """Row-wise OLS slope of Y on X (with intercept) and its Bartlett HAC s.e. (influence function x_c e / s_xx)."""
    n = X.shape[1]
    xc = X - X.mean(axis=1, keepdims=True)
    yc = Y - Y.mean(axis=1, keepdims=True)
    sxx = np.maximum((xc * xc).mean(axis=1), 1e-300)
    b = (xc * yc).mean(axis=1) / sxx
    e = yc - b[:, None] * xc
    psi = xc * e / sxx[:, None]
    return b, np.sqrt(_hac_var(psi, bw) / n)


def slope_ci(x, y, block: int = BLOCK_M, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> dict:
    """OLS slope of y on x with a two-sided studentized pairs circular block-bootstrap CI and the HAC t-statistic."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = x.size
    out = {"n": int(n), "slope": None, "se": None, "t_hac": None, "ci": [None, None]}
    if n < 8 or y.size != n or not np.std(x) > 0:
        return out
    block = max(1, min(int(block), n // 4))
    b0, se0 = _ols_slope_rows(x[None, :], y[None, :], block)
    b0, se0 = float(b0[0]), float(se0[0])
    out.update(slope=b0, se=se0, t_hac=b0 / se0 if se0 > 0 else None)
    if not se0 > 1e-150:
        out["ci"] = [b0, b0]
        return out
    rng = np.random.default_rng(seed)
    ts = []
    for k in _chunks(n_boot, 2 * n):
        idx = _boot_idx(rng, n, block, k)
        xb = x[idx]
        ok = xb.std(axis=1) > 0
        b, se = _ols_slope_rows(xb[ok], y[idx][ok], block)
        good = se > 1e-150
        ts.append((b[good] - b0) / se[good])
    t = np.concatenate(ts)
    al = (1.0 - level) / 2.0
    out["ci"] = [b0 - float(np.quantile(t, 1.0 - al)) * se0, b0 - float(np.quantile(t, al)) * se0]
    return out


def ols_hac(y, X, bw: int = BLOCK_M) -> dict:
    """OLS of y on [1, X] with Bartlett HAC (Newey-West) standard errors: {coef, se, t} (intercept first)."""
    y = np.asarray(y, dtype=float)
    X = np.column_stack([np.ones(y.size), np.asarray(X, dtype=float).reshape(y.size, -1)])
    n, k = X.shape
    if n <= k + 2:
        return {"coef": [None] * k, "se": [None] * k, "t": [None] * k}
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    g = X * e[:, None]
    S = g.T @ g / n
    for lag in range(1, max(1, bw)):
        w = 1.0 - lag / bw
        G = g[lag:].T @ g[:-lag] / n
        S += w * (G + G.T)
    V = n * XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(V), 0))
    return {"coef": beta.tolist(), "se": se.tolist(), "t": [float(b / s) if s > 0 else None for b, s in zip(beta, se)]}


def cagr(r, years: float) -> Optional[float]:
    r = np.asarray(r, dtype=float)
    g = float(np.prod(1.0 + r))
    if not years > 0 or not g > 0:
        return None
    return g ** (1.0 / years) - 1.0


def ols_beta(ra, rs, rb) -> float:
    """OLS slope of the strategy's excess return on the benchmark's (both over the bill), with intercept."""
    x = np.asarray(rs, dtype=float) - np.asarray(rb, dtype=float)
    y = np.asarray(ra, dtype=float) - np.asarray(rb, dtype=float)
    xc = x - x.mean()
    return float((xc * (y - y.mean())).sum() / max((xc * xc).sum(), 1e-300))


def cagr_vs_blend(ra, rs, rb, span_days, beta: Optional[float] = None, block: int = BLOCK_M, level: float = 0.95,
                  n_boot: int = 2000, seed: int = 0) -> dict:
    """CAGR(strategy) - CAGR(beta * benchmark + (1 - beta) * bill, rebalanced each period). ``beta`` None: the OLS beta
    on the same periods, re-estimated in every resample. Two-sided percentile circular block-bootstrap CI of paired
    periods; each resample's calendar span is the sum of its periods' spans."""
    ra, rs, rb, sp = (np.asarray(v, dtype=float) for v in (ra, rs, rb, span_days))
    n = ra.size
    out = {"n": int(n), "beta": None, "beta_fixed": beta is not None, "cagr_a": None, "cagr_blend": None, "diff": None,
           "ci": [None, None], "years": None}
    if n < 8:
        return out
    years = float(sp.sum()) / 365.25
    b0 = ols_beta(ra, rs, rb) if beta is None else float(beta)
    bl = b0 * rs + (1.0 - b0) * rb
    ca, cb = cagr(ra, years), cagr(bl, years)
    out.update(beta=b0, cagr_a=ca, cagr_blend=cb, diff=None if ca is None or cb is None else ca - cb, years=years)
    block = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    ds = []
    for k in _chunks(n_boot, 4 * n):
        idx = _boot_idx(rng, n, block, k)
        A, S, Bi = ra[idx], rs[idx], rb[idx]
        yrs = sp[idx].sum(axis=1) / 365.25
        if beta is None:
            x = S - Bi
            y = A - Bi
            xc = x - x.mean(axis=1, keepdims=True)
            bb = (xc * (y - y.mean(axis=1, keepdims=True))).sum(axis=1) / np.maximum((xc * xc).sum(axis=1), 1e-300)
        else:
            bb = np.full(k, float(beta))
        BL = bb[:, None] * S + (1.0 - bb[:, None]) * Bi
        with np.errstate(invalid="ignore", divide="ignore"):
            ga = np.exp(np.log(np.maximum(1.0 + A, 1e-12)).sum(axis=1) / yrs) - 1.0
            gb = np.exp(np.log(np.maximum(1.0 + BL, 1e-12)).sum(axis=1) / yrs) - 1.0
        ds.append(ga - gb)
    d = np.concatenate(ds)
    d = d[np.isfinite(d)]
    al = (1.0 - level) / 2.0
    out["ci"] = [float(np.quantile(d, al)), float(np.quantile(d, 1.0 - al))]
    return out


def _stationary_idx(rng, n: int, mean_block: float, k: int) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices (k x n): geometric block lengths with mean ``mean_block``, circular."""
    p = 1.0 / max(float(mean_block), 1.0)
    new = rng.random((k, n)) < p
    new[:, 0] = True
    starts = rng.integers(0, n, size=(k, n))
    pos = np.arange(n)
    last = np.maximum.accumulate(np.where(new, pos[None, :], 0), axis=1)
    sv = np.take_along_axis(starts, last, axis=1)
    return (sv + pos[None, :] - last) % n


def max_drawdown(r) -> np.ndarray:
    """Maximum drawdown depth (>= 0, fraction of the peak) of compounded returns, row-wise; the path starts at 1."""
    r = np.atleast_2d(np.asarray(r, dtype=float))
    eq = np.concatenate([np.ones((r.shape[0], 1)), np.cumprod(1.0 + r, axis=1)], axis=1)
    return (1.0 - eq / np.maximum.accumulate(eq, axis=1)).max(axis=1)


def drawdown_gap(r_hedge, r_ref, mean_block: float = 63, level: float = 0.90, n_boot: int = 2000, seed: int = 0) -> dict:
    """maxDD(ref) - maxDD(hedge) in percentage points (depths, so positive = the hedge is shallower) with a two-sided
    percentile CI at ``level`` from the stationary bootstrap of the PAIRED daily returns."""
    a = np.asarray(r_hedge, dtype=float)
    b = np.asarray(r_ref, dtype=float)
    n = a.size
    ma, mb = float(max_drawdown(a)[0]), float(max_drawdown(b)[0])
    out = {"n_days": int(n), "mdd_hedge_pct": 100 * ma, "mdd_ref_pct": 100 * mb, "gap_pts": 100 * (mb - ma),
           "ci": [None, None], "mean_block": float(mean_block), "level": level}
    if n < 8 or b.size != n:
        return out
    rng = np.random.default_rng(seed)
    gs = []
    for k in _chunks(n_boot, 6 * n):
        idx = _stationary_idx(rng, n, mean_block, k)
        gs.append(100 * (max_drawdown(b[idx]) - max_drawdown(a[idx])))
    g = np.concatenate(gs)
    al = (1.0 - level) / 2.0
    out["ci"] = [float(np.quantile(g, al)), float(np.quantile(g, 1.0 - al))]
    return out


# ============================================================================================ archive plumbing ==

def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _names(archive, prefix: str) -> list:
    try:
        ents = archive.entries()
    except (AttributeError, TypeError):
        return []
    return sorted(e.name for e in ents if getattr(e, "name", "").startswith(prefix))


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived")
    return None


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    e = archive.get(name)
    cap = getattr(e, "created_at", None) if e is not None else None
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _day_of(v) -> Optional[str]:
    if "day" in v and v["day"]:
        return str(v["day"])[:10]
    if "t" in v:
        return datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
    return None


def daily_from_rows(rows) -> dict:
    """{days, close (raw), adj (adjclose or close), open (raw, NaN when absent)} of a daily-history bundle."""
    by = {}
    for r in rows:
        v = r["value"]
        c = v.get("close")
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        if not c > 0:
            continue
        d = _day_of(v)
        a = v.get("adjclose")
        o = v.get("open")
        try:
            o = float(o) if o is not None else float("nan")
        except (TypeError, ValueError):
            o = float("nan")
        by[d] = (c, float(a) if a is not None and float(a) > 0 else c, o if o > 0 else float("nan"))
    days = sorted(by)
    return {"days": days, "close": np.array([by[d][0] for d in days]), "adj": np.array([by[d][1] for d in days]),
            "open": np.array([by[d][2] for d in days])}


def index_series(rows) -> dict:
    """{day: close} of a cboe-*-history / fred-* bundle (close, else value), positive finite values only."""
    out = {}
    for r in rows:
        v = r["value"]
        x = v.get("close", v.get("value"))
        try:
            x = float(x)
        except (TypeError, ValueError):
            continue
        d = _day_of(v)
        if d and math.isfinite(x):
            out[d] = x
    return out


def strategy_series(rows) -> dict:
    """A Cboe strategy index with its flags applied: {close: {day: level}, breaks: set of days whose return must not be
    compounded (a known level step / splice), dropped: {day: flag} (market-closed rows, bad prints, other flags),
    backtest: set of back-tested days}."""
    close, breaks, dropped, bt = {}, set(), {}, set()
    for r in rows:
        v = r["value"]
        d = v.get("day")
        try:
            c = float(v.get("close"))
        except (TypeError, ValueError):
            continue
        if not d or not c > 0:
            continue
        fl = v.get("flag")
        if fl:
            low = str(fl).lower()
            if "splice" in low or "level step" in low:
                breaks.add(d)
            else:
                dropped[d] = str(fl)
                continue
        close[d] = c
        if v.get("backtest"):
            bt.add(d)
    return {"close": close, "breaks": breaks, "dropped": dropped, "backtest": bt}


def dtb3_continuous(d_pct: float) -> float:
    """Continuous rate from a 91-day discount yield in percent."""
    return -math.log(1.0 - d_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


def rate_known(days: Sequence[str], series: dict, conv=dtb3_continuous) -> np.ndarray:
    """Continuous rate known at each day's close: the print dated strictly before the day (published a day late);
    before the first print, the first print."""
    ks = sorted(series)
    if not ks:
        return np.zeros(len(days))
    vals = [conv(series[k]) for k in ks]
    return np.array([vals[max(bisect_left(ks, d) - 1, 0)] for d in days], dtype=float)


def dff_continuous(pct: float) -> float:
    return pct / 100.0 * 365.0 / 360.0


def _ords(days) -> np.ndarray:
    return np.array([date.fromisoformat(d).toordinal() for d in days], dtype=np.int64)


# ============================================================================================== monthly panels ==

def monthly_panel(series: dict, rates: dict, start: str = "", end: str = "9999-12", breaks=(), conv=dtb3_continuous) -> dict:
    """Paired calendar-month returns of every series on their common days. ``series``: {name: {day: level}}; ``rates``:
    the bill series {day: pct} (``conv`` makes it continuous); ``start``/``end``: 'YYYY-MM' months of the first and last
    return; ``breaks``: days whose (one) return is excluded from every leg and the bill. Returns months, per-series
    returns, bill returns, each month's calendar span (days), the base and last day, and the excluded returns."""
    common = sorted(set.intersection(*[set(s) for s in series.values()])) if series else []
    common = [d for d in common if d[:7] <= end]
    i0 = next((i for i, d in enumerate(common) if d[:7] >= start), None)
    out = {"months": [], "ret": {k: np.zeros(0) for k in series}, "bill": np.zeros(0), "span": np.zeros(0),
           "first": None, "last": None, "excluded": []}
    if i0 is None or len(common) < 3:
        return out
    sub = common[max(i0 - 1, 0):]
    if len(sub) < 2:
        return out
    o = _ords(sub)
    rk = rate_known(sub, rates, conv) if rates else np.zeros(len(sub))
    bill_d = np.exp(rk[:-1] * (o[1:] - o[:-1]) / 365.0) - 1.0
    excl = np.array([d in breaks for d in sub[1:]], dtype=bool)
    lr = {k: np.array([s[d] for d in sub]) for k, s in series.items()}
    rd = {k: c[1:] / c[:-1] - 1.0 for k, c in lr.items()}
    mon = [d[:7] for d in sub[1:]]
    order, grp = [], defaultdict(list)
    for i, m in enumerate(mon):
        if m not in grp:
            order.append(m)
        grp[m].append(i)
    keep = [m for m in order if m >= start]
    last_in = {m: grp[m][-1] for m in keep}
    span, prev = [], o[0]
    for m in keep:
        j = last_in[m] + 1                          # index into sub of the month's last day
        span.append(int(o[j] - prev))
        prev = o[j]
    def agg(x):
        return np.array([float(np.prod(1.0 + x[[i for i in grp[m] if not excl[i]]])) - 1.0 for m in keep])
    out.update(months=keep, ret={k: agg(v) for k, v in rd.items()}, bill=agg(bill_d), span=np.array(span, dtype=float),
               first=sub[0], last=sub[-1], excluded=[sub[i + 1] for i in np.where(excl)[0]])
    return out


def _sub(panel: dict, mask) -> dict:
    mask = np.asarray(mask, dtype=bool)
    return {"months": [m for m, k in zip(panel["months"], mask) if k], "ret": {k: v[mask] for k, v in panel["ret"].items()},
            "bill": panel["bill"][mask], "span": panel["span"][mask], "first": panel["first"], "last": panel["last"],
            "excluded": panel["excluded"]}


# ================================================================================ T-166 / T-169 beta-matched CAGR ==

def beta_blend_claim(panel: dict, strat: str, bench: str, bound: float, min_n: int, claim_beta: float,
                     raw_panel: Optional[dict] = None, controls: Optional[dict] = None, n_boot: int = N_BOOT,
                     seed: int = 0, block: int = BLOCK_M, exclude_years: Sequence[str] = (), sym_note: str = "",
                     live_from: Optional[str] = None) -> dict:
    """CAGR(strat) - CAGR(beta * bench + (1 - beta) * bill), monthly rebalanced, beta = OLS on the window (re-estimated in
    every resample). Pass: the two-sided 95% CI lies wholly below ``bound`` (0 for T-166, -0.01 for T-169).
    ``raw_panel``: the same panel compounded across breaks (as published). ``controls``: {label: panel with a 'strat'
    series} reported only. ``exclude_years``: each calendar year dropped in turn (reported)."""
    ra, rs, rb, sp = panel["ret"].get(strat), panel["ret"].get(bench), panel["bill"], panel["span"]
    n = 0 if ra is None else int(ra.size)
    if n < 8:
        return {"n": n, "verdict": "inconclusive", "stat": {"n_months": n},
                "reason": f"only {n} paired months of {strat} and {bench}: too few to test — "
                          + _decide([("CAGR difference CI below bound", None, False)], n, min_n, "months")[1]}
    main = cagr_vs_blend(ra, rs, rb, sp, None, block, 0.95, n_boot, seed)
    alt = cagr_vs_blend(ra, rs, rb, sp, None, 12, 0.95, n_boot, seed + 1)
    h = n // 2
    b_first = ols_beta(ra[:h], rs[:h], rb[:h])
    oos = cagr_vs_blend(ra[h:], rs[h:], rb[h:], sp[h:], b_first, block, 0.95, n_boot, seed + 2)
    ins2 = cagr_vs_blend(ra[h:], rs[h:], rb[h:], sp[h:], None, block, 0.95, n_boot, seed + 3)
    lo, hi = main["ci"]
    rd = robust_decision(lambda bl, sd: cagr_vs_blend(ra, rs, rb, sp, None, bl, 0.95, n_boot, seed + sd)["ci"],
                         lambda l, u: u < bound, lambda l, u: l >= bound)
    ok, decisive = rd["ok"], rd["decisive"]
    at_claim = cagr_vs_blend(ra, rs, rb, sp, claim_beta, block, 0.95, n_boot, seed)
    stat = {"strategy": strat, "window": [panel["months"][0], panel["months"][-1]], "base_day": panel["first"],
            "last_day": panel["last"], "n_months": n, "years": main["years"], "beta_ols": main["beta"],
            "beta_claim": claim_beta, "cagr_strategy": main["cagr_a"], "cagr_blend": main["cagr_blend"],
            "cagr_spy_tr": cagr(rs, main["years"]), "cagr_bill": cagr(rb, main["years"]),
            "diff": main["diff"], "ci95": main["ci"], "ci95_block12": alt["ci"], "bound": bound,
            "beta_raw_returns": float(np.polyfit(rs, ra, 1)[0]),
            "oos_second_half": {"beta_first_half": b_first, "months": [panel["months"][h], panel["months"][-1]],
                                "diff": oos["diff"], "ci95": oos["ci"], "in_sample_beta": ins2["beta"],
                                "in_sample_diff": ins2["diff"]},
            "excluded_returns": panel["excluded"], "robustness": rd,
            "at_claim_beta": {"beta": claim_beta, "cagr_blend": at_claim["cagr_blend"], "diff": at_claim["diff"], "ci95": at_claim["ci"]}}
    extra = []
    if raw_panel is not None and raw_panel["ret"].get(strat) is not None and raw_panel["ret"][strat].size == n:
        rr = raw_panel["ret"]
        raw = cagr_vs_blend(rr[strat], rr[bench], raw_panel["bill"], raw_panel["span"], None, block, 0.95, n_boot, seed)
        stat["as_published"] = {"cagr_strategy": raw["cagr_a"], "diff": raw["diff"], "ci95": raw["ci"], "beta": raw["beta"]}
        extra.append(f"compounded across the excluded return(s) {panel['excluded']} as published: CAGR {_pc(raw['cagr_a'])}, "
                     f"diff {_pc(raw['diff'])} ({_ci_s(raw['ci'], 2, 100, '%')})")
    ex = {}
    for y in exclude_years:
        m = np.array([not mm.startswith(y) for mm in panel["months"]])
        p2 = _sub(panel, m)
        r2 = cagr_vs_blend(p2["ret"][strat], p2["ret"][bench], p2["bill"], p2["span"], None, block, 0.95, n_boot, seed)
        ex[y] = {"diff": r2["diff"], "ci95": r2["ci"], "beta": r2["beta"], "n": r2["n"]}
    if ex:
        stat["exclude_year"] = ex
        extra.append("excluding " + "; ".join(f"{y}: diff {_pc(v['diff'])} ({_ci_s(v['ci95'], 2, 100, '%')})" for y, v in ex.items()))
    if live_from:
        lm = np.array([mm >= live_from for mm in panel["months"]])
        if lm.sum() >= 8:
            pl = _sub(panel, lm)
            lv = cagr_vs_blend(pl["ret"][strat], pl["ret"][bench], pl["bill"], pl["span"], None, block, 0.95, n_boot, seed)
            stat["live_only"] = {"from": live_from, "n": lv["n"], "beta": lv["beta"], "cagr": lv["cagr_a"],
                                 "cagr_blend": lv["cagr_blend"], "diff": lv["diff"], "ci95": lv["ci"]}
            extra.append(f"live (post-launch) months only, {live_from}.. ({lv['n']}): beta {_f(lv['beta'])}, diff {_pc(lv['diff'])} "
                         f"({_ci_s(lv['ci'], 2, 100, '%')})")
    ctl = {}
    for lab, p in (controls or {}).items():
        if p is None or p["ret"].get("strat") is None or p["ret"]["strat"].size < 8:
            ctl[lab] = None
            continue
        c = cagr_vs_blend(p["ret"]["strat"], p["ret"]["bench"], p["bill"], p["span"], None, block, 0.95, n_boot, seed)
        ctl[lab] = {"window": [p["months"][0], p["months"][-1]], "n": c["n"], "beta": c["beta"], "cagr": c["cagr_a"],
                    "cagr_blend": c["cagr_blend"], "diff": c["diff"], "ci95": c["ci"]}
    if ctl:
        stat["controls"] = ctl
        extra.append("controls: " + "; ".join(
            f"{k} not available" if v is None else
            f"{k} {v['window'][0]}..{v['window'][1]} beta {_f(v['beta'])}, CAGR {_pc(v['cagr'])} vs blend {_pc(v['cagr_blend'])}, "
            f"diff {_pc(v['diff'])} ({_ci_s(v['ci95'], 2, 100, '%')})" for k, v in ctl.items()))
    bname = "0" if bound == 0 else f"{100 * bound:+.0f}%/yr"
    crit = [(f"95% CI of CAGR({strat}) - CAGR(blend) entirely below {bname} (upper {_pc(hi)}; {_rob_txt(rd)})", ok, decisive)]
    v, why = _decide(crit, n, min_n, "months")
    reason = (f"{strat} vs beta-matched SPY-TR/T-bill blend (monthly rebalanced) over {panel['months'][0]}..{panel['months'][-1]} "
              f"({n} months, base {panel['first']}, last {panel['last']}): OLS beta {_f(main['beta'])} on the window "
              f"(claim ~{claim_beta:.2f}); CAGR {strat} {_pc(main['cagr_a'])} vs blend {_pc(main['cagr_blend'])} (SPY TR "
              f"{_pc(stat['cagr_spy_tr'])}, bill {_pc(stat['cagr_bill'])}): difference {_pc(main['diff'])}, 95% "
              f"{_ci_s(main['ci'], 2, 100, '%')} (block 6 months, beta re-estimated per resample; block 12: "
              f"{_ci_s(alt['ci'], 2, 100, '%')}); out of sample (beta {_f(b_first)} from the first half, second half "
              f"{panel['months'][h]}..): diff {_pc(oos['diff'])} ({_ci_s(oos['ci'], 2, 100, '%')}); at the claim's beta {claim_beta:.2f}: "
              f"blend {_pc(at_claim['cagr_blend'])}, diff {_pc(at_claim['diff'])} ({_ci_s(at_claim['ci'], 2, 100, '%')}) (reported)"
              + (f"; return(s) ending {panel['excluded']} excluded from every leg (flagged level step)" if panel["excluded"] else "")
              + ("; " + "; ".join(extra) if extra else "") + (f"; {sym_note}" if sym_note else "") + f" — {why}")
    return {"n": n, "verdict": v, "reason": reason, "stat": stat}


# ============================================================================= T-168 / T-178 Sharpe differences ==

def _excess(panel: dict, name: str) -> np.ndarray:
    return panel["ret"][name] - panel["bill"]


def sharpe_noworse_claim(panel: dict, strat: str, bench: str, margin: float = 0.05, min_n: int = 380,
                         crash: Optional[np.ndarray] = None, controls: Optional[dict] = None, n_boot: int = N_BOOT,
                         seed: int = 0, sym_note: str = "", live_from: Optional[str] = None) -> dict:
    """T-168: Sharpe(strat) - Sharpe(bench) on monthly excess returns (per-month Sharpe, not annualised). Pass: point
    estimate <= 0 and the two-sided 95% CI upper bound <= ``margin``. ``crash``: bench-index month returns used to report
    the mean return difference in months with SPX < -5%."""
    a, b = _excess(panel, strat), _excess(panel, bench)
    n = int(a.size)
    t = sharpe_diff_test(a, b, BLOCK_M, 0.95, n_boot, seed)
    t12 = sharpe_diff_test(a, b, 12, 0.95, n_boot, seed + 1)
    if t["diff"] is None:
        return {"n": n, "verdict": "inconclusive", "stat": {"n_months": n},
                "reason": f"only {n} paired months: too few — " + _decide([("Sharpe test", None, False)], n, min_n, "months")[1]}
    d, (lo, hi) = t["diff"], t["ci"]
    h = n // 2
    halves = [sharpe_diff_test(a[:h], b[:h], BLOCK_M, 0.95, 400, seed)["diff"], sharpe_diff_test(a[h:], b[h:], BLOCK_M, 0.95, 400, seed)["diff"]]
    stat = {"window": [panel["months"][0], panel["months"][-1]], "n_months": n, "sharpe_strategy_monthly": t["sr_a"],
            "sharpe_bench_monthly": t["sr_b"], "diff_monthly": d, "ci95_monthly": t["ci"], "ci95_block12": t12["ci"],
            "diff_annualised": d * math.sqrt(PPY_M), "ci95_annualised": [lo * math.sqrt(PPY_M), hi * math.sqrt(PPY_M)],
            "margin": margin, "halves_diff_monthly": halves, "halves_split": panel["months"][h]}
    extra = [f"halves (walk-forward, split {panel['months'][h]}): {_s(halves[0], 3)} / {_s(halves[1], 3)}"]
    if live_from:
        lm = np.array([mm >= live_from for mm in panel["months"]])
        if lm.sum() >= 8:
            lv = sharpe_diff_test(a[lm], b[lm], BLOCK_M, 0.95, n_boot, seed)
            stat["live_only"] = {"from": live_from, "n": lv["n"], "diff_monthly": lv["diff"], "ci95": lv["ci"]}
            extra.append(f"live (post-launch) months only, {live_from}.. ({lv['n']}): {_s(lv['diff'], 4)} ({_ci_s(lv['ci'], 4)})")
    if crash is not None and crash.size == n:
        m = crash < -0.05
        dd = panel["ret"][strat][m] - panel["ret"][bench][m]
        stat["crash_months"] = {"n": int(m.sum()), "mean_diff": float(dd.mean()) if dd.size else None,
                                "mean_strategy": float(panel["ret"][strat][m].mean()) if dd.size else None,
                                "mean_bench": float(panel["ret"][bench][m].mean()) if dd.size else None}
        extra.append(f"in the {int(m.sum())} months with SPX < -5%: {strat} {_pc(stat['crash_months']['mean_strategy'])} vs "
                     f"{bench} {_pc(stat['crash_months']['mean_bench'])} (difference {_pc(stat['crash_months']['mean_diff'])})")
    ctl = {}
    for lab, p in (controls or {}).items():
        if p is None:
            ctl[lab] = None
            continue
        c = sharpe_diff_test(_excess(p, "strat"), _excess(p, "bench"), BLOCK_M, 0.95, n_boot, seed)
        ctl[lab] = {"window": [p["months"][0], p["months"][-1]], "n": c["n"], "diff_monthly": c["diff"], "ci95": c["ci"]}
    if ctl:
        stat["controls"] = ctl
        extra.append("controls: " + "; ".join(f"{k} n/a" if v is None else
                                               f"{k} {v['window'][0]}.. diff {_s(v['diff_monthly'], 3)} ({_ci_s(v['ci95'], 3)})"
                                               for k, v in ctl.items()))
    ann_ok = hi * math.sqrt(PPY_M) <= margin
    rd = robust_decision(lambda bl, sd: sharpe_diff_test(a, b, bl, 0.95, n_boot, seed + sd)["ci"],
                         lambda l, u: u <= margin, lambda l, u: l > margin)
    stat["robustness"] = rd
    crit = [(f"Sharpe difference point estimate <= 0 ({_s(d, 4)} per month)", d <= 0, lo > 0),
            (f"95% CI upper bound <= {margin} (monthly-Sharpe units: {_s(hi, 4)}; {_rob_txt(rd)})", rd["ok"], rd["decisive"])]
    v, why = _decide(crit, n, min_n, "months")
    reason = (f"{strat} vs {bench} monthly excess returns over 3m T-bill (DTB3), {panel['months'][0]}..{panel['months'][-1]} "
              f"({n} months): monthly Sharpe {_f(t['sr_a'], 4)} vs {_f(t['sr_b'], 4)}, difference {_s(d, 4)} (95% "
              f"{_ci_s(t['ci'], 4)}, studentized block bootstrap, block 6; block 12 {_ci_s(t12['ci'], 4)}); annualised "
              f"reading {_s(d * math.sqrt(PPY_M), 3)} ({_ci_s(stat['ci95_annualised'], 3)}), upper "
              f"{'<=' if ann_ok else '>'} {margin} on that scale (reported); " + "; ".join(extra)
              + (f"; {sym_note}" if sym_note else "") + f" — {why}")
    return {"n": n, "verdict": v, "reason": reason, "stat": stat}


def sharpe_lower_claim(panel: dict, a_name: str, b_name: str, split: str = "2008-01", min_n: int = 400,
                       n_boot: int = N_BOOT, seed: int = 0, sym_note: str = "", live_from: Optional[str] = None) -> dict:
    """T-178: Sharpe(a) - Sharpe(b) on monthly excess returns; pass: two-sided 95% CI upper < 0 and the point estimate
    negative both before and from ``split`` (the trial's pre/post-2008 halves; equal-count halves reported)."""
    a, b = _excess(panel, a_name), _excess(panel, b_name)
    n = int(a.size)
    t = sharpe_diff_test(a, b, BLOCK_M, 0.95, n_boot, seed)
    if t["diff"] is None:
        return {"n": n, "verdict": "inconclusive", "stat": {"n_months": n},
                "reason": f"only {n} paired months: too few — " + _decide([("Sharpe test", None, False)], n, min_n, "months")[1]}
    t12 = sharpe_diff_test(a, b, 12, 0.95, n_boot, seed + 1)
    pre = np.array([m < split for m in panel["months"]])
    tp = sharpe_diff_test(a[pre], b[pre], BLOCK_M, 0.95, n_boot, seed)
    tq = sharpe_diff_test(a[~pre], b[~pre], BLOCK_M, 0.95, n_boot, seed)
    h = n // 2
    e1 = sharpe_diff_test(a[:h], b[:h], BLOCK_M, 0.95, 400, seed)["diff"]
    e2 = sharpe_diff_test(a[h:], b[h:], BLOCK_M, 0.95, 400, seed)["diff"]
    d, (lo, hi) = t["diff"], t["ci"]
    halves_ok = None if tp["diff"] is None or tq["diff"] is None else bool(tp["diff"] < 0 and tq["diff"] < 0)
    halves_dec = halves_ok is False and n >= min_n
    stat = {"window": [panel["months"][0], panel["months"][-1]], "n_months": n, "sharpe_a_monthly": t["sr_a"],
            "sharpe_b_monthly": t["sr_b"], "diff_monthly": d, "ci95": t["ci"], "ci95_block12": t12["ci"],
            "diff_annualised": d * math.sqrt(PPY_M),
            "pre_split": {"split": split, "n": tp["n"], "diff": tp["diff"], "ci95": tp["ci"]},
            "post_split": {"n": tq["n"], "diff": tq["diff"], "ci95": tq["ci"]},
            "equal_halves": {"split": panel["months"][h], "diff": [e1, e2]}}
    rd = robust_decision(lambda bl, sd: sharpe_diff_test(a, b, bl, 0.95, n_boot, seed + sd)["ci"],
                         lambda l, u: u < 0, lambda l, u: l >= 0)
    stat["robustness"] = rd
    live = ""
    if live_from:
        lm = np.array([mm >= live_from for mm in panel["months"]])
        if lm.sum() >= 8:
            lv = sharpe_diff_test(a[lm], b[lm], BLOCK_M, 0.95, n_boot, seed)
            stat["live_only"] = {"from": live_from, "n": lv["n"], "diff_monthly": lv["diff"], "ci95": lv["ci"]}
            live = f"; live (post-launch) months only, {live_from}.. ({lv['n']}): {_s(lv['diff'], 4)} ({_ci_s(lv['ci'], 4)})"
    crit = [(f"95% CI of Sharpe({a_name}) - Sharpe({b_name}) < 0 (upper {_s(hi, 4)}; upper across variants "
             f"{min(c[1] for c in rd['cis']):+.4f} to {max(c[1] for c in rd['cis']):+.4f}; {_rob_txt(rd)})", rd["ok"], rd["decisive"]),
            (f"same (negative) sign before and from {split} ({_s(tp['diff'], 4)} / {_s(tq['diff'], 4)})", halves_ok, halves_dec)]
    v, why = _decide(crit, n, min_n, "months")
    reason = (f"{a_name} vs {b_name} monthly excess returns over DTB3, {panel['months'][0]}..{panel['months'][-1]} ({n} months): "
              f"monthly Sharpe {_f(t['sr_a'], 4)} vs {_f(t['sr_b'], 4)}, difference {_s(d, 4)} (annualised "
              f"{_s(d * math.sqrt(PPY_M), 3)}), 95% {_ci_s(t['ci'], 4)} (studentized block bootstrap, block 6; block 12 "
              f"{_ci_s(t12['ci'], 4)}); pre-{split[:4]} ({tp['n']} months) {_s(tp['diff'], 4)} ({_ci_s(tp['ci'], 4)}), "
              f"from {split[:4]} ({tq['n']}) {_s(tq['diff'], 4)} ({_ci_s(tq['ci'], 4)}); equal halves (split "
              f"{panel['months'][h]}) {_s(e1, 4)} / {_s(e2, 4)} (reported){live}" + (f"; {sym_note}" if sym_note else "") + f" — {why}")
    return {"n": n, "verdict": v, "reason": reason, "stat": stat}


# ================================================================================= T-179 CNDR on the VRP gap ==

def _third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def roll_sessions(days: Sequence[str], start: str = "", end: str = "9999") -> np.ndarray:
    """Session index of each monthly SPX expiry / Cboe benchmark roll: the third Friday, or the prior session when it is
    a holiday (no session within 4 days before: skipped)."""
    if not len(days):
        return np.zeros(0, dtype=np.int64)
    o = _ords(days)
    y0, y1 = int(days[0][:4]), int(days[-1][:4])
    out = []
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            t = _third_friday(y, m)
            ts = t.isoformat()
            if ts < start or ts > end or t.toordinal() < o[0] or t.toordinal() > o[-1]:
                continue
            j = int(np.searchsorted(o, t.toordinal(), side="right") - 1)
            if j >= 0 and t.toordinal() - o[j] <= 4:
                out.append(j)
    return np.array(sorted(set(out)), dtype=np.int64)


def trailing_rv(close, idx, window: int = 21) -> np.ndarray:
    """Annualised realised vol (vol points) of the ``window`` close-to-close log returns ending at each index (no mean
    removed); NaN without a full window."""
    c = np.asarray(close, dtype=float)
    lr2 = np.zeros(c.size)
    lr2[1:] = np.log(c[1:] / c[:-1]) ** 2
    cs = np.concatenate([[0.0], np.cumsum(lr2)])
    idx = np.asarray(idx, dtype=np.int64)
    out = np.full(idx.size, np.nan)
    ok = idx >= window
    a = idx[ok]
    out[ok] = 100.0 * np.sqrt(PPY_D / window * (cs[a + 1] - cs[a + 1 - window]))
    return out


def roll_panel(days, spx, roll_idx, strat: dict, vix: dict, rates: dict, conv=dtb3_continuous) -> dict:
    """Roll-to-roll observations: the strategy's return from roll a to the next roll b (both closes present), the bill
    accrued over a..b at the rate known at a, VIX at a, trailing 21-day SPX RV at a and the SPX price return a..b."""
    o = _ords(days)
    rv = trailing_rv(spx, roll_idx)
    rk = rate_known([days[i] for i in roll_idx], rates, conv) if rates else np.zeros(len(roll_idx))
    rows = []
    for j in range(len(roll_idx) - 1):
        a, b = int(roll_idx[j]), int(roll_idx[j + 1])
        da, db = days[a], days[b]
        if da not in strat or db not in strat or da not in vix or not np.isfinite(rv[j]):
            continue
        bill = math.exp(rk[j] * (o[b] - o[a]) / 365.0) - 1.0
        rows.append((da, db, strat[db] / strat[da] - 1.0, bill, vix[da], rv[j], spx[b] / spx[a] - 1.0))
    if not rows:
        return {"day": [], "end": [], "ret": np.zeros(0), "bill": np.zeros(0), "vix": np.zeros(0), "rv": np.zeros(0), "spx": np.zeros(0)}
    c = list(zip(*rows))
    return {"day": list(c[0]), "end": list(c[1]), "ret": np.array(c[2]), "bill": np.array(c[3]), "vix": np.array(c[4]),
            "rv": np.array(c[5]), "spx": np.array(c[6])}


def gap_slope_claim(rp: dict, alt_bills: Optional[dict] = None, min_n: int = 400, n_boot: int = N_BOOT, seed: int = 0,
                    sym_note: str = "", live_from: Optional[str] = None) -> dict:
    """T-179: OLS slope of the roll-to-roll excess return on (VIX - trailing RV21) at the roll. Pass: two-sided 95% CI >
    0 and a positive slope in both halves. ``alt_bills``: {label: bill returns} for the rate-proxy check (the criterion
    is decided only when every rate choice agrees)."""
    x = rp["vix"] - rp["rv"]
    y = rp["ret"] - rp["bill"]
    n = int(x.size)
    m = slope_ci(x, y, BLOCK_M, 0.95, n_boot, seed)
    if m["slope"] is None:
        return {"n": n, "verdict": "inconclusive", "stat": {"n_rolls": n},
                "reason": f"only {n} roll-to-roll months: too few — " + _decide([("slope CI", None, False)], n, min_n, "rolls")[1]}
    h = n // 2
    s1 = slope_ci(x[:h], y[:h], BLOCK_M, 0.95, 400, seed)["slope"]
    s2 = slope_ci(x[h:], y[h:], BLOCK_M, 0.95, 400, seed)["slope"]
    lo, hi = m["ci"]
    alts = {}
    for lab, bill in (alt_bills or {}).items():
        r = slope_ci(x, rp["ret"] - bill, BLOCK_M, 0.95, n_boot, seed)
        alts[lab] = {"slope": r["slope"], "ci95": r["ci"], "pass": bool(r["ci"][0] is not None and r["ci"][0] > 0)}
    rd = robust_decision(lambda bl, sd: slope_ci(x, y, bl, 0.95, n_boot, seed + sd)["ci"], lambda l, u: l > 0, lambda l, u: u <= 0)
    passes = [rd["ok"]] + [v["pass"] for v in alts.values()]
    ok = None if passes[0] is None else (True if all(passes) else (False if not any(passes) else None))
    dec = rd["decisive"] and all(a["ci95"][1] is not None and a["ci95"][1] <= 0 for a in alts.values())
    halves_ok = None if s1 is None or s2 is None else bool(s1 > 0 and s2 > 0)
    live = ""
    lv = None
    if live_from:
        lm = np.array([d >= live_from for d in rp["day"]])
        if lm.sum() >= 8:
            lv = slope_ci(x[lm], y[lm], BLOCK_M, 0.95, n_boot, seed)
            live = f"; live (post-launch) rolls only, {live_from}.. ({lv['n']}): {_s(lv['slope'], 5)} ({_ci_s(lv['ci'], 5)})"
    multi = ols_hac(y, np.column_stack([x, rp["spx"]]), BLOCK_M)
    beta = ols_hac(y, rp["spx"], BLOCK_M)
    stat = {"window": [rp["day"][0], rp["end"][-1]], "n_rolls": n, "slope": m["slope"], "ci95": m["ci"], "t_hac": m["t_hac"],
            "slope_units": "excess return per vol point", "mean_gap": float(x.mean()), "sd_gap": float(x.std()),
            "mean_excess": float(y.mean()), "halves": {"split": rp["day"][h], "slopes": [s1, s2]},
            "rate_proxies": alts, "with_spx_return": {"coef_gap": multi["coef"][1], "t_gap": multi["t"][1],
                                                       "coef_spx": multi["coef"][2], "t_spx": multi["t"][2]},
            "beta_to_spx": beta["coef"][1],
            "live_only": None if lv is None else {"from": live_from, "n": lv["n"], "slope": lv["slope"], "ci95": lv["ci"]}}
    stat["robustness"] = rd
    ptxt = "" if rd["ok"] is None or not alts else (", every bill proxy agrees" if ok is not None else ", the bill proxies disagree: data limit")
    crit = [(f"95% CI of the slope > 0 ({_ci_s(m['ci'], 5)}; {_rob_txt(rd)}{ptxt})", ok, dec),
            (f"same (positive) sign in both halves ({_s(s1, 5)} / {_s(s2, 5)})", halves_ok, halves_ok is False and n >= min_n)]
    v, why = _decide(crit, n, min_n, "roll-to-roll months")
    reason = (f"CNDR roll-to-roll excess return (3rd-Friday closes, {rp['day'][0]}..{rp['end'][-1]}, {n} rolls) on VIX - "
              f"trailing 21-day ^GSPC RV at the roll (mean gap {_f(x.mean())} vol pts): slope {_s(m['slope'], 5)} per vol pt "
              f"(HAC t {_f(m['t_hac'])}), 95% {_ci_s(m['ci'], 5)} (studentized pairs block bootstrap, block 6); bill = DTB3 "
              f"as the 1-month proxy" + ("; " + "; ".join(f"{k}: {_s(v2['slope'], 5)} ({_ci_s(v2['ci95'], 5)})" for k, v2 in alts.items()) if alts else "")
              + f"; halves (split {rp['day'][h]}) {_s(s1, 5)} / {_s(s2, 5)}; with the SPX roll-to-roll return as a second "
              f"regressor the gap coefficient is {_s(multi['coef'][1], 5)} (HAC t {_f(multi['t'][1])}), SPX beta "
              f"{_f(beta['coef'][1], 3)} (reported){live}" + (f"; {sym_note}" if sym_note else "") + f" — {why}")
    return {"n": n, "verdict": v, "reason": reason, "stat": stat}


# =================================================================================== T-528 VXTH drawdowns ==

def daily_paired(series: dict, start: str = "", breaks=()) -> dict:
    """Paired daily returns of every series on their common days from ``start``; a return ending on a break day is
    dropped from every leg."""
    common = sorted(set.intersection(*[set(s) for s in series.values()]))
    common = [d for d in common if d >= start]
    if len(common) < 3:
        return {"days": common, "end_days": [], "ret": {k: np.zeros(0) for k in series}}
    keep = np.array([d not in breaks for d in common[1:]], dtype=bool)
    ret = {}
    for k, s in series.items():
        c = np.array([s[d] for d in common])
        ret[k] = (c[1:] / c[:-1] - 1.0)[keep]
    return {"days": common, "end_days": [d for d, k in zip(common[1:], keep) if k], "ret": ret}


def tail_hedge_claim(dp: dict, hedge: str = "VXTH", ref: str = "SPY", rival: str = "PPUT3M", gap_bound: float = 10.0,
                     min_n: int = 2500, controls: Sequence[str] = ("PPUT",), mean_block: float = 63, n_boot: int = 2000,
                     seed: int = 0, sym_note: str = "", live_from: Optional[str] = None) -> dict:
    """T-528: maxDD(ref) - maxDD(hedge) > ``gap_bound`` points (90% CI lower bound, stationary bootstrap of paired daily
    returns, mean block 63) and the claim's first clause maxDD(hedge) < maxDD(rival) (90% CI of maxDD(rival) -
    maxDD(hedge) > 0), on one common daily sample."""
    r = dp["ret"]
    n = int(r[hedge].size)
    if n < 8:
        return {"n": n, "verdict": "inconclusive", "stat": {"n_days": n},
                "reason": f"only {n} common days: too few — " + _decide([("drawdown CI", None, False)], n, min_n, "days")[1]}
    g = drawdown_gap(r[hedge], r[ref], mean_block, 0.90, n_boot, seed)
    gr = drawdown_gap(r[hedge], r[rival], mean_block, 0.90, n_boot, seed + 1) if rival in r else None
    yrs = (date.fromisoformat(dp["days"][-1]) - date.fromisoformat(dp["days"][0])).days / 365.25
    cg = {k: cagr(v, yrs) for k, v in r.items()}
    ctl = {}
    for k in controls:
        if k in r:
            c = drawdown_gap(r[k], r[ref], mean_block, 0.90, max(400, n_boot // 4), seed + 2)
            ctl[k] = {"mdd_pct": c["mdd_hedge_pct"], "gap_vs_ref_pts": c["gap_pts"], "ci90": c["ci"]}
    lo, hi = g["ci"]
    sv = tuple((mean_block, k) for k in range(3))
    rd1 = robust_decision(lambda mb, sd: drawdown_gap(r[hedge], r[ref], mb, 0.90, n_boot, seed + sd)["ci"],
                          lambda l, u: l > gap_bound, lambda l, u: u <= gap_bound, sv)
    crit = [(f"90% CI of maxDD({ref} TR) - maxDD({hedge}) > {gap_bound:g} points (lower {_f(lo)}; {_rob_txt(rd1)})", rd1["ok"], rd1["decisive"])]
    rd2 = None
    if gr is not None:
        lo2, hi2 = gr["ci"]
        rd2 = robust_decision(lambda mb, sd: drawdown_gap(r[hedge], r[rival], mb, 0.90, n_boot, seed + 1 + sd)["ci"],
                              lambda l, u: l > 0, lambda l, u: u <= 0, sv)
        crit.append((f"maxDD({hedge}) smaller than maxDD({rival}) (claim's first clause; 90% CI of the difference > 0, "
                     f"lower {_f(lo2)}; {_rob_txt(rd2)})", rd2["ok"], rd2["decisive"]))
    else:
        crit.append((f"maxDD({hedge}) smaller than maxDD({rival}): {rival} not archived", None, False))
    v, why = _decide(crit, n, min_n, "days")
    live = ""
    lv = None
    if live_from and dp.get("end_days"):
        lm = np.array([d >= live_from for d in dp["end_days"]])
        if lm.sum() >= 8:
            lv = {k: 100 * float(max_drawdown(rr[lm])[0]) for k, rr in r.items()}
            live = (f"; live (post-launch) days only, {live_from}..: maxDD " + ", ".join(f"{k} {_f(x2, 1)}%" for k, x2 in lv.items()))
    stat = {"window": [dp["days"][0], dp["days"][-1]], "n_days": n, "live_only_mdd_pct": lv, "mdd_pct": {hedge: g["mdd_hedge_pct"], ref: g["mdd_ref_pct"]},
            "gap_vs_ref_pts": g["gap_pts"], "ci90_vs_ref": g["ci"], "gap_bound": gap_bound,
            "vs_rival": None if gr is None else {"rival": rival, "mdd_rival_pct": gr["mdd_ref_pct"], "gap_pts": gr["gap_pts"], "ci90": gr["ci"]},
            "cagr": cg, "controls": ctl, "mean_block": mean_block, "robustness": {"vs_ref": rd1, "vs_rival": rd2}}
    reason = (f"daily common sample {dp['days'][0]}..{dp['days'][-1]} ({n} paired returns): maxDD {ref} TR "
              f"{_f(g['mdd_ref_pct'], 1)}% vs {hedge} {_f(g['mdd_hedge_pct'], 1)}%: gap {_s(g['gap_pts'], 1)} pts, 90% "
              f"{_ci_s(g['ci'], 1)} pts (stationary bootstrap, mean block {mean_block:g} days)"
              + ("" if gr is None else f"; {rival} maxDD {_f(gr['mdd_ref_pct'], 1)}%: {rival} - {hedge} {_s(gr['gap_pts'], 1)} pts "
                                       f"(90% {_ci_s(gr['ci'], 1)})")
              + "; CAGR cost: " + ", ".join(f"{k} {_pc(c)}" for k, c in cg.items())
              + ("; controls: " + ", ".join(f"{k} maxDD {_f(c['mdd_pct'], 1)}% (gap vs {ref} {_s(c['gap_vs_ref_pts'], 1)})" for k, c in ctl.items()) if ctl else "")
              + live
              + (f"; {sym_note}" if sym_note else "") + f" — {why}")
    return {"n": n, "verdict": v, "reason": reason, "stat": stat}


# ========================================================================= T-180 Black-Scholes replication ==

def dividends(close, adj) -> np.ndarray:
    """Cash dividend going ex on each day (0 otherwise) from the adjclose/close ratio step: D = close[i-1](1 - f[i-1]/f[i])."""
    close = np.asarray(close, dtype=float)
    f = np.asarray(adj, dtype=float) / close
    out = np.zeros(close.size)
    for i in range(1, close.size):
        if f[i] > f[i - 1] * (1 + 1e-5):
            d = close[i - 1] * (1.0 - f[i - 1] / f[i])
            if 0 < d < 0.05 * close[i - 1]:
                out[i] = d
    return out


def spx_frame(g: dict, spy: dict, vix: dict, dtb3: dict, start: str = "") -> dict:
    """Aligned daily SPX arrays for the overlay engine: days, ordinals, raw close and open, the SPX dividend yield per
    session (smoothed: each SPY dividend yield spread evenly over the SPX sessions since the previous SPY ex-date, the
    last one carried forward; lumped: on SPY's ex-date), the point-in-time trailing 12-month SPY yield q, VIX (forward
    filled) and the continuous DTB3 rate known at each close."""
    keep = [i for i, d in enumerate(g["days"]) if d >= start]
    days = [g["days"][i] for i in keep]
    S = g["close"][keep]
    O = g["open"][keep]
    sd, sc, sa = spy["days"], spy["close"], spy["adj"]
    dv = dividends(sc, sa)
    ex = [(sd[i], dv[i] / sc[i - 1], dv[i]) for i in range(1, len(sd)) if dv[i] > 0]
    n = len(days)
    lump = np.zeros(n)
    smooth = np.zeros(n)
    prev_j = -1
    last_rate = 0.0
    for d, y, _ in ex:
        if not days or d < days[0]:
            continue
        j = bisect_left(days, d)
        if j >= n:
            break
        lump[j] += y
        a = prev_j + 1
        if j >= a:
            smooth[a:j + 1] = y / (j - a + 1)
            last_rate = y / (j - a + 1)
        prev_j = j
    if prev_j + 1 < n:
        smooth[prev_j + 1:] = last_rate
    # trailing 12-month SPY yield known at each close
    spy_close = dict(zip(sd, sc))
    ex_days = [e[0] for e in ex]
    ex_amt = np.cumsum([0.0] + [e[2] for e in ex])
    q = np.zeros(n)
    last_spy = None
    for i, d in enumerate(days):
        last_spy = spy_close.get(d, last_spy)
        hi = bisect_right(ex_days, d)
        lo = bisect_right(ex_days, (date.fromisoformat(d) - timedelta(days=365)).isoformat())
        q[i] = (ex_amt[hi] - ex_amt[lo]) / last_spy if last_spy else 0.0
    vv = np.array([vix.get(d, np.nan) for d in days], dtype=float)
    has = np.isfinite(vv)
    if has.any():
        idx = np.maximum.accumulate(np.where(has, np.arange(n), -1))
        idx = np.where(idx < 0, int(np.argmax(has)), idx)
        vv = vv[idx]
    return {"days": days, "ords": _ords(days), "S": S, "O": O, "divy_smooth": smooth, "divy_lump": lump, "q": q,
            "vix": vv, "rate": rate_known(days, dtb3)}


def _strike(S: float, kind: str, step: float = 5.0) -> float:
    """5-point SPX strike: the first at or above S for a call, at or below S for a put."""
    return math.ceil(S / step - 1e-9) * step if kind == "call" else math.floor(S / step + 1e-9) * step


def overlay_index(fr: dict, rolls, kind: str, iv_scale: float = 1.0, delta: Optional[float] = None, div: str = "smooth",
                  settle: str = "close") -> np.ndarray:
    """Daily level (100 at the first roll; NaN outside the rolls) of a MODEL-PRICED monthly overlay written at each roll's
    close and settled at the next roll: kind 'call' = buy-write on SPX total return (BXM: BXM_t = BXM_{t-1} (S_t + Div_t -
    C_t) / (S_{t-1} - C_{t-1})); kind 'put' = put-write on bill collateral equal to the strike (PUT: V_t / V_roll = (1 +
    P_0/K) e^{r tau} - P_t/K). Strikes: 5-point ATM rule, or the BS ``delta`` strike (BXMD 0.30). Marks: BS at iv_scale x
    VIX, the day's rate and q. ``div``: 'smooth', 'lump' or 'none' (price-only). ``settle``: 'close' (raw close, house
    rule) or 'open' (^GSPC open of the roll day, the SOQ proxy)."""
    S, O, o = fr["S"], fr["O"], fr["ords"]
    dv = np.zeros(S.size) if div == "none" else fr["divy_" + div]
    out = np.full(S.size, np.nan)
    rolls = np.asarray(rolls, dtype=np.int64)
    if rolls.size < 2:
        return out
    level = 100.0
    out[rolls[0]] = level
    for a, b in zip(rolls[:-1], rolls[1:]):
        seg = np.arange(a, b + 1)
        T = (o[b] - o[seg]) / 365.0
        sig = np.maximum(iv_scale * fr["vix"][seg] / 100.0, 1e-4)
        r, q = fr["rate"][seg], fr["q"][seg]
        if delta is not None:
            Kx = bs.strike_for_delta(S[a], T[0], r[0], sig[0], delta, kind, q[0])
            K = round(Kx / 5.0) * 5.0
        else:
            K = _strike(S[a], kind)
        V = np.asarray(bs.price(S[seg], K, T, r, sig, kind, q), dtype=float)
        if settle == "open" and np.isfinite(O[b]):
            V[-1] = max(O[b] - K, 0.0) if kind == "call" else max(K - O[b], 0.0)
        if kind == "call":
            num = S[seg[1:]] + S[seg[:-1]] * dv[seg[1:]] - V[1:]
            den = S[seg[:-1]] - V[:-1]
            out[seg[1:]] = level * np.cumprod(num / den)
        else:
            tau = (o[seg] - o[a]) / 365.0
            out[seg] = level * ((1.0 + V[0] / K) * np.exp(fr["rate"][a] * tau) - V / K)
        level = out[b]
    return out


def condor_periods(fr: dict, rolls, iv_scale: float = 1.0, short_d: float = 0.20, long_d: float = 0.05) -> np.ndarray:
    """Per roll period: the MODEL-PRICED iron condor's P&L per unit of SPX (credit - payoff at the next roll close) / S."""
    S, o = fr["S"], fr["ords"]
    out = []
    for a, b in zip(rolls[:-1], rolls[1:]):
        T = (o[b] - o[a]) / 365.0
        sig, r, q = max(iv_scale * fr["vix"][a] / 100.0, 1e-4), fr["rate"][a], fr["q"][a]
        ks = {}
        for lab, d, kind in (("c20", short_d, "call"), ("c5", long_d, "call"), ("p20", -short_d, "put"), ("p5", -long_d, "put")):
            ks[lab] = round(bs.strike_for_delta(S[a], T, r, sig, d, kind, q) / 5.0) * 5.0
        pr = {k: float(bs.price(S[a], K, T, r, sig, "call" if k[0] == "c" else "put", q)) for k, K in ks.items()}
        cr = pr["c20"] + pr["p20"] - pr["c5"] - pr["p5"]
        sT = S[b]
        pay = (max(sT - ks["c20"], 0) - max(sT - ks["c5"], 0) + max(ks["p20"] - sT, 0) - max(ks["p5"] - sT, 0))
        out.append((cr - pay) / S[a])
    return np.array(out)


def fit_stats(a, s) -> dict:
    """R^2 (squared correlation), the 1:1 R^2, TE = sd(a - s) x sqrt 12 and RMS TE of monthly returns."""
    a = np.asarray(a, dtype=float)
    s = np.asarray(s, dtype=float)
    n = a.size
    if n < 3 or not a.std() > 0 or not s.std() > 0:
        return {"n": int(n), "r2": None, "r2_1to1": None, "te": None, "te_rms": None, "mean_diff_ann": None}
    d = a - s
    return {"n": int(n), "r2": float(np.corrcoef(a, s)[0, 1] ** 2),
            "r2_1to1": float(1.0 - (d * d).sum() / ((a - a.mean()) ** 2).sum()),
            "te": float(d.std(ddof=1) * math.sqrt(PPY_M)), "te_rms": float(math.sqrt((d * d).mean()) * math.sqrt(PPY_M)),
            "mean_diff_ann": float(d.mean() * PPY_M), "slope": float(np.polyfit(s, a, 1)[0])}


def _period_returns(points, days, actual: dict, sim: np.ndarray, max_days: int = 40) -> tuple:
    """Returns between consecutive points (session indices) where the actual index has a close and the simulation is
    finite; a step longer than ``max_days`` calendar days (a missing roll or month) is dropped."""
    a, s, ends = [], [], []
    pts = [int(p) for p in points]
    for p, q in zip(pts[:-1], pts[1:]):
        dp, dq = days[p], days[q]
        if (date.fromisoformat(dq) - date.fromisoformat(dp)).days > max_days:
            continue
        if dp in actual and dq in actual and np.isfinite(sim[p]) and np.isfinite(sim[q]):
            a.append(actual[dq] / actual[dp] - 1.0)
            s.append(sim[q] / sim[p] - 1.0)
            ends.append(dq)
    return np.array(a), np.array(s), ends


def month_end_points(days, lo: int, hi: int, actual: dict) -> list:
    """Last session of each calendar month within [lo, hi] on which the actual index has a close; a month with no such
    session breaks the chain (both neighbouring returns are dropped by ``_period_returns``)."""
    last = {}
    for i in range(lo, hi + 1):
        if days[i] in actual:
            last[days[i][:7]] = i
    return [last[m] for m in sorted(last)]


def replicate(fr: dict, actual: dict, kind: str, start: str, iv_scale: float = 1.0, delta: Optional[float] = None,
              div: str = "smooth", settle: str = "close") -> dict:
    """R^2 / TE of the simulated overlay against the actual index on both monthly calendars (roll-to-roll and calendar
    month-ends), from the first roll on or after ``start`` (and on or after the actual index's first close)."""
    days = fr["days"]
    first_actual = min(actual) if actual else "9999"
    rolls = roll_sessions(days, max(start, first_actual))
    if rolls.size < 3:
        return {"roll": fit_stats([], []), "month": fit_stats([], []), "n": 0}
    sim = overlay_index(fr, rolls, kind, iv_scale, delta, div, settle)
    ar, sr_, er = _period_returns(rolls, days, actual, sim)
    me = month_end_points(days, int(rolls[0]), int(rolls[-1]), actual)
    am, sm, em = _period_returns(me, days, actual, sim)
    fr_r, fr_m = fit_stats(ar, sr_), fit_stats(am, sm)
    h = ar.size // 2
    return {"roll": fr_r, "month": fr_m, "n": int(min(ar.size, am.size)), "window": [days[rolls[0]], days[rolls[-1]]],
            "roll_halves": [fit_stats(ar[:h], sr_[:h]), fit_stats(ar[h:], sr_[h:])],
            "sim_cagr": cagr(sm, (date.fromisoformat(days[me[-1]]) - date.fromisoformat(days[me[0]])).days / 365.25) if sm.size else None,
            "actual_cagr": cagr(am, (date.fromisoformat(days[me[-1]]) - date.fromisoformat(days[me[0]])).days / 365.25) if am.size else None}


def _both(a: Optional[bool], b: Optional[bool]) -> Optional[bool]:
    if a is None or b is None:
        return None
    return a if a == b else None


def replication_claim(fr: dict, actual: dict, starts: dict, condor: Optional[dict] = None, min_n: int = 220,
                      r2_min: float = 0.95, te_max: float = 0.02, sym_note: str = "") -> dict:
    """T-180: R^2 > 0.95 and TE < 2%/yr for both BXM and PUT (each criterion decided when the roll-to-roll and calendar
    month-end bases agree); BXMD (0.30-delta) and CNDR (scale-free R^2 only) documented; IV-scale, dividend and
    settlement sensitivities reported. ``actual``: {sym: {day: level}}; ``starts``: {sym: 'YYYY-MM-DD'}."""
    res, crit, parts, ns = {}, [], [], []
    for sym, kind in (("BXM", "call"), ("PUT", "put")):
        if sym not in actual:
            crit.append((f"{sym} R^2 > {r2_min}", None, False))
            crit.append((f"{sym} TE < {100 * te_max:.0f}%/yr", None, False))
            parts.append(f"{sym} not archived")
            continue
        rep = replicate(fr, actual[sym], kind, starts[sym])
        sens = {}
        for lab, kw in (("iv x0.9", {"iv_scale": 0.9}), ("iv x1.1", {"iv_scale": 1.1}), ("dividends lumped on SPY ex-dates", {"div": "lump"}),
                        ("price-only SPX", {"div": "none"}), ("settle at the ^GSPC open (SOQ proxy)", {"settle": "open"})):
            if kind == "put" and kw.get("div") in ("lump", "none"):
                continue                                        # PUT holds bills, not SPX: dividends do not enter
            r2 = replicate(fr, actual[sym], kind, starts[sym], **kw)
            sens[lab] = {"roll": {k: r2["roll"][k] for k in ("r2", "te")}, "month": {k: r2["month"][k] for k in ("r2", "te")}}
        rep["sensitivity"] = sens
        res[sym] = rep
        ns.append(rep["n"])
        rr, mm = rep["roll"], rep["month"]
        r2ok = _both(None if rr["r2"] is None else rr["r2"] > r2_min, None if mm["r2"] is None else mm["r2"] > r2_min)
        teok = _both(None if rr["te"] is None else rr["te"] < te_max, None if mm["te"] is None else mm["te"] < te_max)
        crit.append((f"{sym} R^2 > {r2_min} (roll-to-roll {_f(rr['r2'], 3)}, month-end {_f(mm['r2'], 3)}"
                     + (", the bases disagree" if r2ok is None and rr["r2"] is not None and mm["r2"] is not None else "") + ")", r2ok, False))
        crit.append((f"{sym} TE < {100 * te_max:.0f}%/yr (roll-to-roll {_pu(rr['te'])}, month-end {_pu(mm['te'])}"
                     + (", the bases disagree" if teok is None and rr["te"] is not None and mm["te"] is not None else "") + ")", teok, False))
        parts.append(f"{sym} {rep['window'][0]}..{rep['window'][1]}: roll-to-roll ({rr['n']}) R^2 {_f(rr['r2'], 3)} (1:1 "
                     f"{_f(rr['r2_1to1'], 3)}), TE {_pu(rr['te'])}, mean actual - sim {_pc(rr['mean_diff_ann'])}/yr; month-end "
                     f"({mm['n']}) R^2 {_f(mm['r2'], 3)}, TE {_pu(mm['te'])}; halves R^2 "
                     f"{'/'.join(_f(h['r2'], 3) for h in rep['roll_halves'])}; sensitivities (roll R^2 / TE): "
                     + ", ".join(f"{k} {_f(v['roll']['r2'], 3)} / {_pu(v['roll']['te'])}" for k, v in sens.items()))
    doc = {}
    if "BXMD" in actual:
        rd = replicate(fr, actual["BXMD"], "call", starts.get("BXMD", "2002-04-01"), delta=0.30)
        doc["BXMD"] = {"roll": rd["roll"], "month": rd["month"], "window": rd.get("window")}
        parts.append(f"BXMD (0.30-delta call at VIX, documented): roll R^2 {_f(rd['roll']['r2'], 3)}, TE {_pu(rd['roll']['te'])}; "
                     f"month-end R^2 {_f(rd['month']['r2'], 3)}, TE {_pu(rd['month']['te'])}")
    if condor is not None:
        doc["CNDR"] = condor
        parts.append(f"CNDR (20/5-delta condor at VIX, documented; collateral rule not modelled, so TE is not computed): "
                     f"R^2 {_f(condor.get('r2'), 3)} over {condor.get('n')} rolls, implied notional slope {_f(condor.get('slope'), 2)}")
    n = min(ns) if ns else 0
    v, why = _decide(crit, n, min_n, "months")
    stat = {"label": MP, "bxm": res.get("BXM"), "put": res.get("PUT"), "documented": doc, "r2_min": r2_min, "te_max": te_max}
    reason = (f"{MP}: Black-Scholes overlay on ^GSPC (sigma = VIX, DTB3, q = trailing SPY yield, 3rd-Friday close rolls, "
              f"raw-close settlement, SPY dividends spread over each quarter for the total-return leg): " + "; ".join(parts)
              + "; VWAP-vs-close fill not testable (no intraday option prices archived)"
              + (f"; {sym_note}" if sym_note else "") + f" — {why}")
    return {"n": n, "verdict": v, "reason": reason, "stat": stat}


def condor_doc(fr: dict, cndr: dict, start: str = "2002-04-01") -> dict:
    """CNDR shortfall documentation: squared correlation of the actual roll-to-roll return with the simulated condor P&L
    per unit of SPX (scale-free) and the implied notional (OLS slope)."""
    days = fr["days"]
    rolls = roll_sessions(days, max(start, min(cndr) if cndr else "9999"))
    rolls = np.array([r for r in rolls if days[r] in cndr], dtype=np.int64)
    if rolls.size < 4:
        return {"n": 0, "r2": None}
    sim = condor_periods(fr, rolls)
    o = fr["ords"]
    act = np.array([cndr[days[b]] / cndr[days[a]] - 1.0 - (math.exp(fr["rate"][a] * (o[b] - o[a]) / 365.0) - 1.0)
                    for a, b in zip(rolls[:-1], rolls[1:])])
    # keep consecutive rolls only (one month apart)
    ok = np.array([(o[b] - o[a]) <= 40 for a, b in zip(rolls[:-1], rolls[1:])])
    act, sim = act[ok], sim[ok]
    if act.size < 3 or not sim.std() > 0:
        return {"n": int(act.size), "r2": None}
    return {"n": int(act.size), "r2": float(np.corrcoef(act, sim)[0, 1] ** 2), "slope": float(np.polyfit(sim, act, 1)[0])}


# =================================================================================== T-220 VIX SOQ credit spread ==

def vx_curve(rows) -> dict:
    """{day: {expiry: settle}} from cboe-vx-futures rows; missing or non-positive settles (the 2013 files carry 0) and
    rows dated after their expiry are dropped."""
    curve = defaultdict(dict)
    for r in rows:
        v = r["value"]
        try:
            s = float(v.get("settle"))
        except (TypeError, ValueError):
            continue
        if not (s > 0 and math.isfinite(s)):
            continue
        d, e = str(v["day"])[:10], str(v["expiry"])[:10]
        if d > e:
            continue
        curve[d][e] = s
    return dict(curve)


def vx_expiries(rows) -> list:
    return sorted({str(r["value"]["expiry"])[:10] for r in rows})


def vro_clean(rows) -> dict:
    """{day: SOQ} of VRO rows that are VIX expiries, not carried, with no flag (cboe_strategy.annotate)."""
    out = {}
    for r in rows:
        v = r["value"]
        if v.get("expiry") and not v.get("carried") and not v.get("flag"):
            try:
                out[v["day"]] = float(v["close"])
            except (TypeError, ValueError, KeyError):
                continue
    return out


def b76_call(F, K, T, r, sigma):
    """Black-76 call on a future: e^{-rT} [F N(d1) - K N(d2)]."""
    return np.exp(-np.asarray(r, dtype=float) * np.asarray(T, dtype=float)) * np.asarray(bs.price(F, K, T, 0.0, sigma, "call", 0.0), dtype=float)


def b76_iv(price: float, F: float, K: float, T: float, r: float) -> Optional[float]:
    """Black-76 implied vol by bisection (None when the price is outside the bounds)."""
    target = price * math.exp(r * T)
    if not target > max(F - K, 0.0) or target >= F:
        return None
    lo, hi = 1e-3, 10.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if float(bs.price(F, K, T, 0.0, mid, "call", 0.0)) > target:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def _strike_round(x: float, step: float = 1.0) -> float:
    return math.floor(x / step + 0.5) * step


def chain_calibration(chains: list, curve: dict, vvix: dict, rates: dict, tdays: list, otm: float = 2.0, width: float = 5.0) -> dict:
    """From captured VIX chains: for each capture, the quote day (pre-open captures carry the previous session), the near
    monthly expiry, F, the claim's strikes, each leg's bid/ask half-spread, the market mid credit, the Black-76 credit at
    VVIX, and each leg's Black-76 IV / VVIX. Returns per-capture rows and the mean half-spreads and IV ratios."""
    from mandel.experiments.volatility import _quote_day
    rows_out = []
    for rows in chains:
        if not rows:
            continue
        qd = _quote_day(rows[0].get("available_at") or "", tdays)
        if qd is None or qd not in curve:
            continue
        exps = sorted(e for e in curve[qd] if e > qd)
        if not exps:
            continue
        e = exps[0]
        F = curve[qd][e]
        K1 = _strike_round(F + otm)
        K2 = K1 + width
        calls = {}
        for r in rows:
            v = r["value"]
            if v.get("expiry") == e and v.get("type") == "call" and str(v.get("sym", "")).startswith("VIX") and not str(v.get("sym", "")).startswith("VIXW"):
                try:
                    calls[float(v["strike"])] = (float(v["bid"]), float(v["ask"]))
                except (TypeError, ValueError, KeyError):
                    continue
        if K1 not in calls or K2 not in calls:
            continue
        (b1, a1), (b2, a2) = calls[K1], calls[K2]
        if not (a1 > b1 >= 0 and a2 > b2 >= 0):
            continue
        T = (date.fromisoformat(e).toordinal() - date.fromisoformat(qd).toordinal() - 0.28) / 365.0
        r0 = float(rate_known([qd], rates)[0]) if rates else 0.0
        m1, m2 = (a1 + b1) / 2, (a2 + b2) / 2
        iv1, iv2 = b76_iv(m1, F, K1, T, r0), b76_iv(m2, F, K2, T, r0)
        sig = vvix[qd] / 100.0 if qd in vvix else None          # VVIX of the quote day (None: not yet archived)
        model = None if sig is None else float(b76_call(F, K1, T, r0, sig) - b76_call(F, K2, T, r0, sig))
        rows_out.append({"quote_day": qd, "expiry": e, "F": F, "K1": K1, "K2": K2, "half_spread_K1": (a1 - b1) / 2,
                         "half_spread_K2": (a2 - b2) / 2, "market_mid_credit": m1 - m2, "model_credit": model,
                         "vvix": None if sig is None else vvix[qd], "iv_K1": iv1, "iv_K2": iv2,
                         "iv_ratio_K1": None if iv1 is None or sig is None else iv1 / sig,
                         "iv_ratio_K2": None if iv2 is None or sig is None else iv2 / sig})
    if not rows_out:
        return {"captures": [], "hs1": None, "hs2": None, "ratio1": None, "ratio2": None}
    def mean(key):
        xs = [r[key] for r in rows_out if r[key] is not None]
        return float(np.mean(xs)) if xs else None
    return {"captures": rows_out, "hs1": mean("half_spread_K1"), "hs2": mean("half_spread_K2"),
            "ratio1": mean("iv_ratio_K1"), "ratio2": mean("iv_ratio_K2")}


def soq_spread_trades(tdays: list, expiries: list, curve: dict, vix: dict, vix3m: dict, vvix: dict, vro: dict, rates: dict,
                      hs1: float, hs2: float, entry_lag: int = 3, gate: float = 1.10, otm: float = 2.0, width: float = 5.0,
                      iv_scale: float = 1.0, iv_legs: Optional[tuple] = None, round_strikes: bool = True,
                      gate_lag: int = 0, gate_side: str = "above") -> dict:
    """One call credit spread per monthly VIX settlement E (in ``expiries``): entry at the close ``entry_lag`` sessions
    before E, gate VIX3M/VIX (``gate_lag`` sessions before entry) above ``gate`` (or below 1 for gate_side 'below'),
    strikes from the expiring future's settlement, Black-76 credit at VVIX x iv_scale (or per-leg IV ratios ``iv_legs``)
    minus the half-spreads, settled at the clean VRO print on E. Returns the trades and the skipped expiries by reason."""
    pos = {d: i for i, d in enumerate(tdays)}
    trades, skipped = [], defaultdict(list)
    for e in expiries:
        if e not in pos:
            if e <= tdays[-1]:
                skipped["settlement day not a session"].append(e)
            continue
        i = pos[e] - entry_lag
        if i < gate_lag:
            continue
        d = tdays[i]
        g = tdays[i - gate_lag]
        F = curve.get(d, {}).get(e)
        if F is None:
            skipped["no VX settlement for the expiring future at entry"].append(e)
            continue
        if g not in vix or g not in vix3m or d not in vvix:
            skipped["no VIX / VIX3M / VVIX close at entry"].append(e)
            continue
        ratio = vix3m[g] / vix[g]
        if (gate_side == "above" and not ratio > gate) or (gate_side == "below" and not ratio < 1.0):
            continue
        if e not in vro:
            skipped["no clean VRO settlement"].append(e)
            continue
        K1 = _strike_round(F + otm) if round_strikes else F + otm
        K2 = K1 + width
        T = (date.fromisoformat(e).toordinal() - date.fromisoformat(d).toordinal() - 0.28) / 365.0
        r0 = float(rate_known([d], rates)[0]) if rates else 0.0
        s1 = vvix[d] / 100.0 * (iv_legs[0] if iv_legs else iv_scale)
        s2 = vvix[d] / 100.0 * (iv_legs[1] if iv_legs else iv_scale)
        mid = float(b76_call(F, K1, T, r0, s1) - b76_call(F, K2, T, r0, s2))
        net = mid - hs1 - hs2
        soq = vro[e]
        pay = min(max(soq - K1, 0.0), width)
        ml = width - net
        trades.append({"expiry": e, "entry": d, "ratio": ratio, "F": F, "K1": K1, "vvix": vvix[d], "mid_credit": mid,
                       "net_credit": net, "soq": soq, "payoff": pay, "pnl": net - pay, "ret": (net - pay) / ml})
    return {"trades": trades, "skipped": {k: v for k, v in skipped.items()}}


def soq_spread_claim(main: dict, variants: dict, prelim: Optional[dict] = None, calib: Optional[dict] = None, min_n: int = 60,
                     n_boot: int = N_BOOT, seed: int = 0, block: int = 3, costs_measured: bool = True) -> dict:
    """T-220: mean return on max loss > 0 with a two-sided 95% CI excluding 0 (studentized block bootstrap, block 3
    trades). ``variants``: {label: trades dict} reported (IV scales, chain skew, costs, strikes, gate lag, controls)."""
    tr = main["trades"]
    x = np.array([t["ret"] for t in tr])
    n = int(x.size)
    lo, hi = stud_ci(x, block, 0.95, n_boot, seed) if n >= 8 else (None, None)
    mean = float(x.mean()) if n else None
    rd = robust_decision(lambda bl, sd: stud_ci(x, bl, 0.95, n_boot, seed + sd) if n >= 8 else (None, None),
                         lambda l, u: l > 0, lambda l, u: u <= 0, tuple((b, k) for b in (block, 2 * block) for k in range(3)))
    if not costs_measured:
        ok, dec = None, False
        cname = "mean return on max loss > 0 with 95% CI excluding 0 NET OF HALF-SPREADS (no VIX chain captured: half-spreads not measurable)"
    else:
        ok, dec = rd["ok"], rd["decisive"]
        cname = f"mean return on max loss > 0 with 95% CI excluding 0 ({_ci_s((lo, hi), 2, 100, '%')}; {_rob_txt(rd)})"
    v, why = _decide([(cname, ok, dec)], n, min_n, "trades")
    rep_v = {}
    for lab, t in variants.items():
        xv = np.array([q["ret"] for q in t["trades"]])
        lv, hv = stud_ci(xv, block, 0.95, max(1000, n_boot // 4), seed) if xv.size >= 8 else (None, None)
        rep_v[lab] = {"n": int(xv.size), "mean": float(xv.mean()) if xv.size else None, "ci95": [lv, hv]}
    wins = float(np.mean([t["payoff"] == 0 for t in tr])) if tr else None
    stat = {"label": MP, "n_trades": n, "mean_ret_on_max_loss": mean, "ci95": [lo, hi], "win_rate": wins,
            "mean_net_credit": float(np.mean([t["net_credit"] for t in tr])) if tr else None,
            "mean_mid_credit": float(np.mean([t["mid_credit"] for t in tr])) if tr else None,
            "max_losses": int(sum(1 for t in tr if t["payoff"] >= 5.0 - 1e-9)),
            "worst": sorted(({"expiry": t["expiry"], "ret": t["ret"], "soq": t["soq"], "K1": t["K1"]} for t in tr), key=lambda z: z["ret"])[:5],
            "skipped": {k: len(v2) for k, v2 in main["skipped"].items()}, "variants": rep_v,
            "calibration": calib, "preliminary_soq": prelim, "robustness": rd, "trades": tr}
    window = f"{tr[0]['expiry']}..{tr[-1]['expiry']}" if tr else "no trades"
    cal = ""
    if calib and calib.get("captures"):
        cal = ("; captured chains: " + ", ".join(
            f"{c['quote_day']} F {c['F']:.2f} K {c['K1']:g}/{c['K2']:g}: market mid credit {c['market_mid_credit']:.3f} vs model "
            f"{_f(c['model_credit'], 3)}, half-spreads {c['half_spread_K1']:.3f}/{c['half_spread_K2']:.3f}, Black-76 IV "
            f"{_f(c['iv_K1'])}/{_f(c['iv_K2'])}" + ("" if c["vvix"] is None else f" = {_f(c['iv_ratio_K1'])}/{_f(c['iv_ratio_K2'])} x VVIX")
            for c in calib["captures"]))
    pre = ""
    if prelim:
        pre = (f"; preliminary SOQ check ({prelim['n_settle']} monthly settlements from {prelim['first']}): mean VRO - prior VIX "
               f"close {_s(prelim['mean_settle'])} vs mean daily VIX change on {prelim['n_other']} other Wednesdays "
               f"{_s(prelim['mean_other'])} (difference {_s(prelim['diff'])}, {_ci_s(prelim['ci95'])})")
    reason = (f"{MP} (Black-76 at VVIX on the expiring VX future): {n} gated trades ({window}; VIX3M/VIX > 1.1 at the entry "
              f"close 3 sessions before the monthly SOQ), mean net credit {_f(stat['mean_net_credit'], 3)} (mid "
              f"{_f(stat['mean_mid_credit'], 3)}, half-spreads {_f(main.get('hs1'), 3)} + {_f(main.get('hs2'), 3)} per spread "
              f"from the captured chains), win rate {_pu(wins, 1)}, {stat['max_losses']} max losses; mean return on max loss "
              f"{_pc(mean)} (95% {_ci_s((lo, hi), 2, 100, '%')}, studentized block bootstrap, block 3)"
              + (f"; skipped: " + ", ".join(f"{k} {len(v2)}" for k, v2 in main["skipped"].items()) if main["skipped"] else "")
              + "; sensitivities: " + ", ".join(f"{k}: n {r['n']}, mean {_pc(r['mean'])} ({_ci_s(r['ci95'], 2, 100, '%')})" for k, r in rep_v.items())
              + cal + pre + f" — {why}")
    return {"n": n, "verdict": v, "reason": reason, "stat": stat}


def soq_preliminary(vro: dict, vix: dict, tdays: list, monthly: set, n_boot: int = 2000, seed: int = 0) -> Optional[dict]:
    """Mean (VRO - prior-session VIX close) on monthly settlement days vs mean daily VIX change on other Wednesdays,
    with a percentile bootstrap CI of the difference (independent resampling of the two groups)."""
    pos = {d: i for i, d in enumerate(tdays)}
    a, b = [], []
    first = None
    for d in sorted(vro):
        if d in monthly and d in pos and pos[d] > 0 and tdays[pos[d] - 1] in vix:
            a.append(vro[d] - vix[tdays[pos[d] - 1]])
            first = first or d
    lo_day = first or "9999"
    for i, d in enumerate(tdays):
        if d < lo_day or i == 0 or date.fromisoformat(d).weekday() != 2 or d in monthly:
            continue
        if d in vix and tdays[i - 1] in vix:
            b.append(vix[d] - vix[tdays[i - 1]])
    if len(a) < 8 or len(b) < 8:
        return None
    a, b = np.array(a), np.array(b)
    rng = np.random.default_rng(seed)
    ds = rng.choice(a, (n_boot, a.size)).mean(axis=1) - rng.choice(b, (n_boot, b.size)).mean(axis=1)
    return {"n_settle": int(a.size), "n_other": int(b.size), "first": first, "mean_settle": float(a.mean()),
            "mean_other": float(b.mean()), "diff": float(a.mean() - b.mean()),
            "ci95": [float(np.quantile(ds, 0.025)), float(np.quantile(ds, 0.975))]}


# ===================================================================================================== harnesses ==

def _spy_tr(archive) -> dict:
    d = daily_from_rows(_rows(archive, SPY_B))
    return dict(zip(d["days"], d["adj"]))


def _gspc(archive) -> dict:
    return daily_from_rows(_rows(archive, GSPC_B))


def _strat(archive, sym: str) -> dict:
    return strategy_series(_rows(archive, CB(sym)))


def _panel_pair(archive, strat_sym: str, bench: dict, dtb3: dict, start: str, end: str = "9999-12", breaks: bool = True) -> Optional[dict]:
    if not _has(archive, CB(strat_sym)):
        return None
    s = _strat(archive, strat_sym)
    return monthly_panel({"strat": s["close"], "bench": bench}, dtb3, start, end, s["breaks"] if breaks else ())


def b6b_hedge_collar_cll_vs_blend(archive):
    """T-166: CLL 95-110 collar CAGR below a beta-matched SPY-TR / T-bill blend, 2008-08..2026-10."""
    miss = _missing(archive, [CB("CLL"), SPY_B, DTB3_B])
    if miss:
        return miss
    spy = _spy_tr(archive)
    dtb3 = index_series(_rows(archive, DTB3_B))
    cll = _strat(archive, "CLL")
    panel = monthly_panel({"CLL": cll["close"], "SPY": spy}, dtb3, "2008-08", "2026-10", cll["breaks"])
    raw = monthly_panel({"CLL": cll["close"], "SPY": spy}, dtb3, "2008-08", "2026-10", ())
    ctl = {}
    for sym in ("PPUT", "CLLZ"):
        ctl[f"{sym} (same window)"] = _panel_pair(archive, sym, spy, dtb3, "2008-08", "2026-10")
    for sym in ("CLL1M", "CLL3M"):
        if _has(archive, CB(sym)):
            ctl[f"{sym} (same window)"] = _panel_pair(archive, sym, spy, dtb3, "2008-08", "2026-10")
    note = _bt_note("CLL", panel["first"], panel["last"]) + "; CLL1M and CLL3M are not archived (controls not run)"
    rep = beta_blend_claim(panel, "CLL", "SPY", 0.0, 200, 0.63, raw_panel=raw, controls=ctl, sym_note=note,
                           live_from=_live_month("CLL"))
    return _wrap(rep)


def b6b_hedge_cllz_sharpe(archive):
    """T-168: CLLZ monthly Sharpe (excess over DTB3) no higher than SPY TR, 1993-02..2026-10."""
    miss = _missing(archive, [CB("CLLZ"), SPY_B, DTB3_B, GSPC_B])
    if miss:
        return miss
    spy = _spy_tr(archive)
    g = _gspc(archive)
    gp = dict(zip(g["days"], g["close"]))
    dtb3 = index_series(_rows(archive, DTB3_B))
    cz = _strat(archive, "CLLZ")
    panel = monthly_panel({"CLLZ": cz["close"], "SPY": spy, "SPX": gp}, dtb3, "1993-02", "2026-10", cz["breaks"])
    ctl = {"CLL (2008-)": _panel_pair(archive, "CLL", spy, dtb3, "1993-02"),
           "PPUT": _panel_pair(archive, "PPUT", spy, dtb3, "1993-02"),
           "CLLZ vs price-only SPX": monthly_panel({"strat": cz["close"], "bench": gp}, dtb3, "1993-02", "2026-10", cz["breaks"])}
    rep = sharpe_noworse_claim(panel, "CLLZ", "SPY", 0.05, 380, crash=panel["ret"]["SPX"], controls=ctl,
                               sym_note=_bt_note("CLLZ", panel["first"], panel["last"]), live_from=_live_month("CLLZ"))
    return _wrap(rep)


def b6b_hedge_pput_vs_blend(archive):
    """T-169: PPUT CAGR more than 1%/yr below a beta-matched SPY-TR / T-bill blend, 1993-02..2026-10."""
    miss = _missing(archive, [CB("PPUT"), SPY_B, DTB3_B])
    if miss:
        return miss
    spy = _spy_tr(archive)
    dtb3 = index_series(_rows(archive, DTB3_B))
    pp = _strat(archive, "PPUT")
    panel = monthly_panel({"PPUT": pp["close"], "SPY": spy}, dtb3, "1993-02", "2026-10", pp["breaks"])
    ctl = {"PPUT3M (2004-)": _panel_pair(archive, "PPUT3M", spy, dtb3, "1993-02")}
    note = _bt_note("PPUT", panel["first"], panel["last"])
    if _has(archive, GSPC_B) and _has(archive, VIX_B):
        g = _gspc(archive)
        vix = index_series(_rows(archive, VIX_B))
        i0 = bisect_left(g["days"], "1990-01-01")
        idx = np.array([i for i in range(i0, len(g["days"]) - 21) if g["days"][i] in vix], dtype=np.int64)
        fwd = trailing_rv(g["close"], idx + 21)
        gap = np.array([vix[g["days"][i]] for i in idx]) - fwd
        gap = gap[np.isfinite(gap)]
        lo, hi = stud_ci(gap, 42, 0.95, 1000, 0)
        note += (f"; VRP cross-check: VIX minus forward 21-day ^GSPC RV since 1990 averages {_s(float(gap.mean()))} vol pts "
                 f"({_ci_s((lo, hi))}, block 42 days, {gap.size} days)")
    rep = beta_blend_claim(panel, "PPUT", "SPY", -0.01, 380, 0.73, controls=ctl, exclude_years=("2008", "2020"), sym_note=note,
                           live_from=_live_month("PPUT"))
    return _wrap(rep)


def b6b_hedge_bfly_vs_cndr_sharpe(archive):
    """T-178: BFLY monthly Sharpe below CNDR's, 1986-06..2026-10, same sign pre/post 2008."""
    miss = _missing(archive, [CB("BFLY"), CB("CNDR"), DTB3_B])
    if miss:
        return miss
    dtb3 = index_series(_rows(archive, DTB3_B))
    bf, cn = _strat(archive, "BFLY"), _strat(archive, "CNDR")
    panel = monthly_panel({"BFLY": bf["close"], "CNDR": cn["close"]}, dtb3, "1986-06", "2026-10", bf["breaks"] | cn["breaks"])
    rep = sharpe_lower_claim(panel, "BFLY", "CNDR", "2008-01", 400,
                             sym_note=_bt_note("BFLY", panel["first"], panel["last"]) + " (CNDR the same)", live_from=_live_month("BFLY"))
    return _wrap(rep)


def b6b_hedge_cndr_vrp_gap(archive):
    """T-179: CNDR roll-to-roll excess return rises with VIX - trailing 21-day SPX RV at the roll, 1990-2026."""
    miss = _missing(archive, [CB("CNDR"), VIX_B, GSPC_B, DTB3_B])
    if miss:
        return miss
    g = _gspc(archive)
    vix = index_series(_rows(archive, VIX_B))
    dtb3 = index_series(_rows(archive, DTB3_B))
    cn = _strat(archive, "CNDR")
    rolls = roll_sessions(g["days"], "1990-01-01")
    rp = roll_panel(g["days"], g["close"], rolls, cn["close"], vix, dtb3)
    alts = {}
    if _has(archive, DFF_B):
        dff = index_series(_rows(archive, DFF_B))
        rk = roll_panel(g["days"], g["close"], rolls, cn["close"], vix, dff, dff_continuous)
        if len(rk["day"]) == len(rp["day"]):
            alts["fed funds (DFF)"] = rk["bill"]
    alts["zero rate"] = np.zeros(len(rp["day"]))
    rep = gap_slope_claim(rp, alts, 400, sym_note=_bt_note("CNDR", rp["day"][0] if rp["day"] else "", rp["end"][-1] if rp["end"] else ""),
                          live_from=LAUNCH["CNDR"])
    return _wrap(rep)


def b6b_hedge_bs_replication(archive):
    """T-180: MODEL-PRICED BS overlay (VIX as IV, DTB3) reproduces BXM (2002-) and PUT (2007-) monthly returns."""
    miss = _missing(archive, [CB("BXM"), CB("PUT"), GSPC_B, SPY_B, VIX_B, DTB3_B])
    if miss:
        return miss
    g = _gspc(archive)
    spy = daily_from_rows(_rows(archive, SPY_B))
    vix = index_series(_rows(archive, VIX_B))
    dtb3 = index_series(_rows(archive, DTB3_B))
    fr = spx_frame(g, spy, vix, dtb3, "2001-01-01")
    actual = {s: _strat(archive, s)["close"] for s in ("BXM", "PUT", "BXMD") if _has(archive, CB(s))}
    cond = condor_doc(fr, _strat(archive, "CNDR")["close"]) if _has(archive, CB("CNDR")) else None
    note = "; ".join(x for x in (_bt_note("BXM", "2002-04-19", fr["days"][-1]), _bt_note("PUT", "2007-01-19", fr["days"][-1])) if x)
    rep = replication_claim(fr, actual, {"BXM": "2002-01-01", "PUT": "2007-01-01", "BXMD": "2002-01-01"}, cond, 220, sym_note=note)
    return _wrap(rep)


def b6b_hedge_vxth_drawdown(archive):
    """T-528: VXTH maxDD at least 10 points shallower than SPY TR's (and shallower than PPUT3M's), 2006-03 onward, daily."""
    miss = _missing(archive, [CB("VXTH"), SPY_B])
    if miss:
        return miss
    ser = {"VXTH": _strat(archive, "VXTH")}
    for sym in ("PPUT3M", "PPUT"):
        if _has(archive, CB(sym)):
            ser[sym] = _strat(archive, sym)
    closes = {k: v["close"] for k, v in ser.items()}
    closes["SPY"] = _spy_tr(archive)
    brk = set().union(*[v["breaks"] for v in ser.values()])
    dp = daily_paired(closes, "2006-03-01", brk)
    if len(dp["days"]) < 3:
        return _wrap(tail_hedge_claim(dp, "VXTH", "SPY", "PPUT3M", 10.0, 2500, ()))
    note = "; ".join(_bt_note(k, dp["days"][0], dp["days"][-1]) for k in ("VXTH", "PPUT3M") if k in closes)
    if dp["ret"]["VXTH"].size:
        eq = np.cumprod(1 + dp["ret"]["VXTH"])
        trough = int(np.argmax(1 - eq / np.maximum.accumulate(eq)))
        note += f"; VXTH's deepest drawdown bottoms on {dp['end_days'][trough]}" + (" (back-tested)" if dp["end_days"][trough] < LAUNCH["VXTH"] else "")
    rep = tail_hedge_claim(dp, "VXTH", "SPY", "PPUT3M", 10.0, 2500, ("PPUT",) if "PPUT" in closes else (), sym_note=note,
                           live_from=LAUNCH["VXTH"])
    return _wrap(rep)


def b6b_hedge_vix_soq_credit_spread(archive):
    """T-220: MODEL-PRICED VIX call credit spread sold 3 sessions before the monthly SOQ when VIX3M/VIX > 1.1."""
    miss = _missing(archive, [VX_B, CB("VRO"), VIX_B, VIX3M_B, VVIX_B, DTB3_B])
    if miss:
        return miss
    vxr = _rows(archive, VX_B)
    curve = vx_curve(vxr)
    exps = vx_expiries(vxr)
    vix = index_series(_rows(archive, VIX_B))
    vix3m = index_series(_rows(archive, VIX3M_B))
    vvix = index_series(_rows(archive, VVIX_B))
    vro = vro_clean(_rows(archive, CB("VRO")))
    dtb3 = index_series(_rows(archive, DTB3_B))
    tdays = sorted(vix)
    chains = [_rows(archive, nm) for nm in _names(archive, VIX_CHAIN_P)]
    calib = chain_calibration(chains, curve, vvix, dtb3, sorted(set(vix) | set(curve)))
    measured = calib["hs1"] is not None
    hs1, hs2 = (calib["hs1"], calib["hs2"]) if measured else (0.0, 0.0)
    kw = dict(tdays=tdays, expiries=exps, curve=curve, vix=vix, vix3m=vix3m, vvix=vvix, vro=vro, rates=dtb3)
    main = soq_spread_trades(hs1=hs1, hs2=hs2, **kw)
    main.update(hs1=hs1 if measured else None, hs2=hs2 if measured else None)
    var = {}
    for s in (0.8, 1.2, 1.5):
        var[f"IV x{s}"] = soq_spread_trades(hs1=hs1, hs2=hs2, iv_scale=s, **kw)
    if calib.get("ratio1") and calib.get("ratio2"):
        var[f"chain-skew IV (K1 x{calib['ratio1']:.2f}, K2 x{calib['ratio2']:.2f} VVIX)"] = soq_spread_trades(
            hs1=hs1, hs2=hs2, iv_legs=(calib["ratio1"], calib["ratio2"]), **kw)
    var["half-spreads x2"] = soq_spread_trades(hs1=2 * hs1, hs2=2 * hs2, **kw)
    var["unrounded strikes (F+2, F+7)"] = soq_spread_trades(hs1=hs1, hs2=hs2, round_strikes=False, **kw)
    var["gate at the prior close"] = soq_spread_trades(hs1=hs1, hs2=hs2, gate_lag=1, **kw)
    var["backwardation control (VIX3M/VIX < 1)"] = soq_spread_trades(hs1=hs1, hs2=hs2, gate_side="below", **kw)
    ex = {"trades": [t for t in main["trades"] if not (t["expiry"].startswith("2008") or t["expiry"][:7] in ("2018-02", "2020-03"))],
          "skipped": {}}
    dropped = len(main["trades"]) - len(ex["trades"])
    var[f"excluding 2008, 2018-02, 2020-03 ({dropped} gated trades fall in them; 2008 predates the VX file)"] = ex
    prelim = soq_preliminary(vro, vix, tdays, set(exps) | _monthly_vix_expiries(min(vro) if vro else "2008-01-01", tdays[-1]))
    rep = soq_spread_claim(main, var, prelim, calib, 60, costs_measured=measured)
    return _wrap(rep)


def _monthly_vix_expiries(first: str, last: str) -> set:
    """Monthly VIX settlement days before the VX futures file starts (the Wednesday 30 days before the next month's third
    Friday, the prior session on a holiday), from mandel.data.cboe_strategy's calendar."""
    from mandel.data.cboe_strategy import is_trading_day
    out = set()
    y, m = int(first[:4]), int(first[5:7])
    while f"{y:04d}-{m:02d}" <= last[:7]:
        ny, nm = y + (m == 12), m % 12 + 1
        w = _third_friday(ny, nm) - timedelta(days=30)
        d = w
        if not (is_trading_day(w) and is_trading_day(w + timedelta(days=30))):
            d = w - timedelta(days=1)
            while not is_trading_day(d):
                d -= timedelta(days=1)
        if first <= d.isoformat() <= last:
            out.add(d.isoformat())
        y, m = ny, nm
    return out


HARNESSES = {
    "b6b_hedge_collar_cll_vs_blend": b6b_hedge_collar_cll_vs_blend,
    "b6b_hedge_cllz_sharpe": b6b_hedge_cllz_sharpe,
    "b6b_hedge_pput_vs_blend": b6b_hedge_pput_vs_blend,
    "b6b_hedge_bfly_vs_cndr_sharpe": b6b_hedge_bfly_vs_cndr_sharpe,
    "b6b_hedge_cndr_vrp_gap": b6b_hedge_cndr_vrp_gap,
    "b6b_hedge_bs_replication": b6b_hedge_bs_replication,
    "b6b_hedge_vxth_drawdown": b6b_hedge_vxth_drawdown,
    "b6b_hedge_vix_soq_credit_spread": b6b_hedge_vix_soq_credit_spread,
}

THEORY_MAP = {
    "T-166": "b6b_hedge_collar_cll_vs_blend",
    "T-168": "b6b_hedge_cllz_sharpe",
    "T-169": "b6b_hedge_pput_vs_blend",
    "T-178": "b6b_hedge_bfly_vs_cndr_sharpe",
    "T-179": "b6b_hedge_cndr_vrp_gap",
    "T-180": "b6b_hedge_bs_replication",
    "T-528": "b6b_hedge_vxth_drawdown",
    "T-220": "b6b_hedge_vix_soq_credit_spread",
}
