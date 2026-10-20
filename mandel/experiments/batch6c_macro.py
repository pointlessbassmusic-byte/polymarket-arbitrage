"""
Batch 6c, group ``macro``: six predictive-regression and tactical/trend claims on ALFRED vintages and Yahoo bundles.
===================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-398  the 4-quarter sum of mutual funds' net equity purchases (Z.1 BOGZ1FA653064100Q) scaled by US equity market
           value (BOGZ1LM893064105Q), as an expanding-window z-score known at each Z.1 release, predicts the next-4-quarter
           US market excess return (Ken French Mkt-RF + RF) negatively over 1952-2026 (min_n 250 quarters): slope t <= -2
           under every overlapping-return correction the trial names (Hansen-Hodrick, Newey-West, 8-quarter block
           bootstrap: rule 11) AND a negative slope in 1952-1989 and in 1990-2026.
  * T-458  a top-tercile orthogonalised Michigan sentiment reading (UMCSENT on the 12-month changes in unemployment, CPI
           inflation and the T-bill rate, fitted in the expanding window) predicts a negative 3-month ^RUT-minus-^GSPC
           return from 1990 (min_n 400 months): at least 400 monthly out-of-sample observations; the mean 3-month spread
           after top-tercile readings < 0; Campbell-Thompson OOS R^2 > 0 with Clark-West p < 0.05 after deflation over the
           12 declared cells (Holm); net Sharpe of the tercile long-short > 0.3.
  * T-479  DAA (13612W breadth momentum, canary VWO + BND, top 6 of 12 risky, SHY/IEF/LQD cash) vs the same top-6
           rotation without the canary, hold months 2008-05..2026-09 (min_n 200): paired Sharpe-difference 95% CI > 0,
           DSR > 0.95, PBO < 0.5 over the 4-trial x breadth-threshold matrix.
  * T-483  2x SPY above its 200-day SMA (T-bills below), after costs and financing at DTB3 + 50 bp, vs SPY buy-and-hold,
           1994-2026 (min_n 8,000 days): mean daily log-return difference > 0 with the 60-day circular block bootstrap
           95% CI excluding 0, DSR > 0.95 over 6 trials + T-58's 6 SPY trials, SSO 2006-2026 point estimate same sign.
  * T-325  short equal dollars of TQQQ and SQQQ, reset monthly, 2010-03..2026-09 (min_n 150 months), 3%/yr borrow per leg,
           DTB3 on the short proceeds: one-sided 95% lower bound of the mean monthly net return on gross short notional > 0
           (6-month blocks) AND DSR > 0.95 over the 8 trials (4 pairs x monthly / 20%-drift reset).
  * T-467  |z| > 2 last-hour parity fade pooled over the 10 declared NYSE/TSX pairs on Yahoo 60-minute bars (min_n 200
           trades), 3 bps per leg per trade plus 2 bps FX: one-sided 95% lower bound of the pooled mean net return per
           trade (bootstrap clustered by date) > 0 AND DSR > 0.95 over the 4 declared variants.

Conventions
  * Data. Yahoo ``daily-history-<SYM>`` adjclose (split and dividend adjusted; indices are price-only) and
    ``hourly-<SYM>`` bars (bar start + 1 h availability; bars are keyed by their New York start time), FRED DTB3,
    Ken French daily factors and ``alfred-<SID>`` real-time vintages, all through ``archive.load``; a row is used only when
    its ``available_at`` is not after the bundle's capture time.
  * Point in time (rules 4, 12). ALFRED: a value counts from its period's ``available_at`` (realtime_start at the release
    time of day). Periods that start on the series' first ALFRED vintage count from the fetcher's ``lag_rule_at`` (the
    period end + LAG_RULE_DAYS: Z.1 84 days, Michigan/BLS 35 days) when it set one: the true first release is unknown, a
    stated look-ahead approximation (T-398 before 2019-03-07: the 2019 vintage values, so pre-2019 Z.1 revisions are NOT
    removed; T-458's UMCSENT before 1998-07-31). Forecasting signals use only values in force (T-398: the vintage in force
    at each release, whose z uses that vintage's whole history) or first-release values (T-458: each observation's
    first print; a 12-month change is taken inside the first-release vintage, so CPI's 1988 rebasing never mixes bases).
    FRED daily series (DTB3) are used from the day after their date (batch6b_bw.Bills).
  * Bills and Sharpe (rule 7). DTB3 is a 91-day discount yield, converted to the continuous rate
    -ln(1 - d 91/360)/(91/365) and accrued calendar day by calendar day (batch6b_bw.Bills). Funded strategies are judged
    on excess returns; zero-investment books (T-458, T-467) and short books whose proceeds earn bills (T-325: the return on
    gross notional with proceeds interest is the excess return of a fully margined account) are excess by construction.
  * Intervals (rule 6). Studentized circular block bootstrap (Bartlett-HAC s.e., bandwidth = block; batch6b_bw._stud),
    5,000 resamples per seed, interval ends averaged over 5 seeds with their Monte Carlo s.e. (25 when 5 cannot resolve a
    bound). Blocks: T-398 8 quarters (the trial's), T-458 12 months, T-479 12 months (the trial's), T-483 60 days (the
    trial's), T-325 6 months (the trial's), T-467 5 sessions (holds last at most 3 sessions). Sidedness as the pass states:
    an 'X% lower bound > 0' pass (T-325, T-467) is one-sided, judged on the (1 - X) end, i.e. the lower end of the
    two-sided 1 - 2(1 - X) interval from the same draws (95% -> _stud level 0.90); the two-sided 95% CI is reported.
  * Calendars (rule 10). T-398 decides at each Z.1 release (the library's 'rebalance on each Z.1 release date') and holds
    release to release; T-458 decides at the close of the first trading day of each month (the claim's availability rule:
    a month's sentiment is known on the first day of the next month) and its long-short book holds overlapping 3-month
    cohorts (the pooled all-start estimate; the per-phase range is reported); T-479 decides at month-end closes and fills
    at the next close (its rule); T-483 is daily; T-325 resets at month-end closes (its rule); T-467 is signal-driven.
  * Families (multiple testing), declared before any result: T-398 horizons 1 and 4 quarters (2 trials; the pass names
    no deflation, the 1-quarter trial is reported); T-458 the 12 cells raw/orthogonalised x 1/3/12 months x RUT-GSPC/
    SPHB-SPLV (Holm on the Clark-West p's); T-479 top 6/top 3 x canary VWO+BND/SPY+BND x breadth 2/1 = 8 configurations
    (DSR count and PBO matrix); T-483 leverage 1.25/2/3 x SMA 100/200 = 6 computed, + T-58's 6 SPY rules = 12; T-325 4
    pairs x monthly/20%-drift = 8; T-467 4 variants, of which the 10 large caps at |z| > 2 and |z| > 3 are computable
    (gold miners and TSM/2330.TW are not archived and enter the count only). DSR trial-Sharpe variance: the computed
    family's observed variance floored at the zero-skill 1/(T-1) (batch6c_mom.family_dsr). Where a DSR could mean the
    strategy's own series or the claim's difference series (T-479), or per-trade and daily series (T-467), every reading
    is computed and the criterion needs all (rule 11 spirit).
  * Below trial.min_n (rule 5): never supported; a failing criterion counts only when it fails decisively.

Claim-specific choices (declared before any result)
  * T-398: x_q = (sum of the 4 quarterly SAAR flows q-3..q / 4) / the equity market value at q; the quarterly flow history
    starts in the first year with four quarterly prints (1952; earlier rows are annual Q4 values); z_q is the expanding
    z of x over 1952Q4..q in the vintage in force at q's release, from 8 quarters of history. The fill is the close of
    the release day (Z.1 posts at 12:00 ET) or of the next session (lag-rule days); h-quarter returns run fill(q) ->
    fill(q + h). HH: rectangular kernel, h - 1 lags; NW: Bartlett, max(2(h - 1), floor(4 (n/100)^(2/9))) lags;
    bootstrap: pairs circular blocks of 8 quarters, t = slope / bootstrap s.e. The halves split on the flow quarter.
    Stambaugh bias (not named by the trial) is reported for the 1-quarter regression.
  * T-458: availability of UMCSENT under BOTH constructions the claim names (rule 11): 'next-month' (available on the first
    day of the next month) and 'alfred' (realtime_start; the 35-day lag rule before 1998-07-31). Macro regressors are the
    latest first releases known at the decision; the orthogonalisation and the forecasting regression are re-fitted at
    every decision on everything known then (orthogonalisation rows from 1978-02; forecasting rows need 24 complete
    outcomes, from ^RUT's 1987-09 start), and terciles are the in-sample residual terciles at that decision. The claim's
    'top-tercile reading predicts' fixes no regressor, so the forecast uses both the continuous residual and the tercile
    signal (+1/0/-1) and the R^2/Clark-West criterion needs both (rule 11 spirit). Clark-West HAC lag max(h - 1,
    floor(4 (n/100)^(2/9))). Long-short: top tercile = short ^RUT / long ^GSPC for 3 months, bottom the reverse,
    overlapping monthly cohorts (1/3 each), equal notional legs, 5 bps per leg on every change in exposure; ^RUT and
    ^GSPC are price indices (the dividend-yield gap is ignored, as the claim's data does).
  * T-479: score = (12 r1 + 4 r3 + 2 r6 + r12)/4 on month-end adjclose; b = canaries with score <= 0, cash fraction
    min(1, b/B); the risky part goes equally to the top ceil(T (1 - CF)) risky assets (T = 6, CF = 0.5: the library's top
    3), the cash part to the best of SHY/IEF/LQD; 5 bps per side on drift-adjusted turnover. PBO (CSCV, 8 partitions)
    and DSR on both the DAA excess returns and the DAA-minus-rotation differences.
  * T-483: signal at close t (adjclose > SMA200), position from close t+1 (one-bar delay); 2x day = 2 r_SPY - financing of
    the borrowed 1x at DTB3 + 50 bp - 0.9%/yr expense, accrued over calendar days; switches cost 2 bps per unit of SPY
    notional traded (4 bps of equity per 0 <-> 2x switch; the literal 2 bps per switch is reported); SSO cross-check:
    actual SSO adjclose with the same SPY signal, 5 bps per switch, vs SPY over the same days.
  * T-325: daily simulation on adjclose; at each reset 0.5 of gross short notional per leg; borrow accrues on each leg's
    current value (act/365), DTB3 on the gross short value (marked-to-market cash collateral); margin-call stop: when
    the FINRA-style requirement sum(min(1, 0.3 max(1, |L|)) x value) reaches 2x its value at the last reset, both legs
    are covered at that close and re-opened at the next month-end; UVXY 2x -> 1.5x and SVXY -1x -> -0.5x from 2018-02-28
    (the requirement and the reported pre/post split); the drift variant resets to equal dollars (gross 1) when the
    larger leg exceeds the smaller by more than 20% at a close. Monthly return = month P&L / gross at the month start.
  * T-467: d = ln P_US - ln(P_TSX / USDCAD) at the 16:00 ET closes (the 15:30 equity bar and the 15:00 CAD=X bar, which
    must not be flat); sessions where either venue or the FX bar is missing (holidays, early closes) are skipped; z over
    the trailing 20 valid sessions including today; |z| > 2 opens long the cheap / short the rich listing (one position
    per pair), exit at the first close with z on the other side of 0 (or 0) or after 2 sessions. Rule 12: the 16:00 bar
    close is the signal and, in Yahoo's layout, also the closing-auction proxy, so both readings are run: 'live' (fill at
    the signal close) and 'lagged' (decide on the close, fill at the next session's close); costs under both readings of
    '3 bps per leg per trade plus 2 bps FX' (per round trip 2 x 3 + 2 = 8 bps; per side 4 x 3 + 2 x 2 = 16 bps). The
    criterion needs every reading (rules 11, 12). Placebo: the FX bar one hour earlier (reported).

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.data.market_history import CANADA, TSX
from mandel.experiments.batch6b_bw import (Bills, _boot_idx, _chunks, _ci_crit, _clean, _decide, _mean_stat, _stud,
                                           all_constructions, mc_escalate, resolve, sharpe_diff_test)
from mandel.experiments.batch6c_mom import bill_logcum, drift_turnover, dsr_row, family_dsr, holm_primary, month_grid
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import _hac_var, deflated_sharpe_ratio, sharpe_ratio

N_BOOT = 5000                  # the trials' 5,000 bootstrap draws
REPS = 5                       # bootstrap seeds behind every decisive interval end
SEED = 0
DSR_PASS = 0.95
ALPHA = 0.05
_N = NormalDist()
NY = ZoneInfo("America/New_York")
CLOSE_UTC = "T20:00:00+00:00"  # a New York close is at 20:00 or 21:00 UTC: a value known by 20:00 UTC is known at the close

DTB3_B = "fred-DTB3"
FF3_B = "french-ff3-daily"
FA_SID, LM_SID = "BOGZ1FA653064100Q", "BOGZ1LM893064105Q"
UMC_SID, UNR_SID, CPI_SID = "UMCSENT", "UNRATE", "CPIAUCSL"
CAD_SYM = "CAD=X"


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in s)


def dh(sym: str) -> str:
    return "daily-history-" + _safe(sym)


def hr(sym: str) -> str:
    return "hourly-" + _safe(sym)


def al(sid: str) -> str:
    return "alfred-" + sid


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# ================================================================================================= data access ==

_CACHE: dict = {}


def _cached(archive, key, fn):
    slot = _CACHE.get(id(archive))
    if slot is None or slot[0] is not archive:
        _CACHE.clear()
        slot = (archive, {})
        _CACHE[id(archive)] = slot
    if key not in slot[1]:
        slot[1][key] = fn()
    return slot[1][key]


def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _rows(archive, name: str) -> list:
    """Rows of a bundle that were available when the bundle was captured."""
    def load():
        cap = getattr(archive.get(name), "created_at", None)
        cap = str(cap) if cap else None
        return [r for r in archive.load(name) if not (cap and r.get("available_at") and str(r["available_at"]) > cap)]
    return _cached(archive, ("rows", name), load)


def _daily(archive, name: str) -> dict:
    """{'days', 'close', 'adj'} of a Yahoo daily bundle (session dates); a bar without adjclose carries the previous
    adjclose/close ratio."""
    def load():
        by = {}
        for r in _rows(archive, name):
            v = r["value"]
            c = _num(v.get("close"))
            if c is None or c <= 0:
                continue
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
            a = _num(v.get("adjclose"))
            by[d] = (c, a if a is not None and a > 0 else float("nan"))
        days = sorted(by)
        arr = np.array([by[d] for d in days], float).reshape(-1, 2)
        close, adj = arr[:, 0], arr[:, 1].copy()
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return {"days": days, "close": close, "adj": adj}
    return _cached(archive, ("daily", name), load)


def _series(archive, name: str) -> dict:
    """{day: value} of a FRED series bundle; non-numeric prints are skipped."""
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            x = _num(v.get("value"))
            if x is not None and v.get("day"):
                out[v["day"]] = x
        return out
    return _cached(archive, ("series", name), load)


def _bills(archive) -> Bills:
    return _cached(archive, ("bills",), lambda: Bills(_series(archive, DTB3_B)))


def _ff3(archive) -> dict:
    """Ken French daily market factor: {'days', 'mkt' (total market return = Mkt-RF + RF), 'rf'} as decimals."""
    def load():
        by = {}
        for r in _rows(archive, FF3_B):
            v = r["value"]
            m, f = _num(v.get("Mkt-RF")), _num(v.get("RF"))
            if m is not None and f is not None and v.get("day"):
                by[v["day"]] = ((m + f) / 100.0, f / 100.0)
        days = sorted(by)
        return {"days": days, "mkt": np.array([by[d][0] for d in days]), "rf": np.array([by[d][1] for d in days])}
    return _cached(archive, ("ff3",), load)


def _hourly(archive, name: str) -> dict:
    """{(New York date, 'HH:MM' bar start): (open, high, low, close)} of an hourly bundle."""
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            px = [_num(v.get(k)) for k in ("open", "high", "low", "close")]
            t = _num(v.get("t"))
            if t is None or any(p is None or p <= 0 for p in px):
                continue
            et = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(NY)
            out[(et.strftime("%Y-%m-%d"), et.strftime("%H:%M"))] = tuple(px)
        return out
    return _cached(archive, ("hourly", name), load)


class Alfred:
    """Every real-time period of one ALFRED series. ``periods``: {observation day: [(start, value), ...]} where start is
    the ISO UTC time the period's value became public. A period on the series' first ALFRED vintage starts at the
    fetcher's ``lag_rule_at`` when one is set (stated look-ahead approximation); each period runs until the next starts
    (a later blank period withdraws the value)."""

    def __init__(self, periods: dict):
        self.obs = {}
        for k, rows in periods.items():
            rs = sorted(rows, key=lambda r: r[0])
            self.obs[k] = ([r[0] for r in rs], [r[1] for r in rs])

    @classmethod
    def from_rows(cls, rows) -> "Alfred":
        per = defaultdict(list)
        for r in rows:
            v = r.get("value") or {}
            day = v.get("day")
            if not day:
                continue
            start = str(r.get("available_at") or (str(v.get("realtime_start")) + "T23:59:59+00:00"))
            lag = v.get("lag_rule_at")
            if v.get("first_vintage") and lag and str(lag) < start:
                start = str(lag)
            per[day].append((start, _num(v.get("value"))))
        return cls(per)

    def at(self, day: str, T: str) -> Optional[float]:
        """The value of observation ``day`` in force at time T (ISO UTC), or None."""
        s = self.obs.get(day)
        if not s:
            return None
        i = bisect.bisect_right(s[0], T) - 1
        return s[1][i] if i >= 0 else None

    def first(self, day: str) -> tuple:
        """(value, start) of the observation's first non-blank print, or (None, None)."""
        s = self.obs.get(day)
        if not s:
            return None, None
        for st, v in zip(*s):
            if v is not None:
                return v, st
        return None, None


def _alfred(archive, sid: str) -> Alfred:
    return _cached(archive, ("alfred", sid), lambda: Alfred.from_rows(_rows(archive, al(sid))))


# ================================================================================================== statistics ==

def _nw_lag(n: int) -> int:
    return max(1, int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))


def hac_mean(x, lag: int) -> dict:
    """Mean with a Newey-West (Bartlett, ``lag`` lags) s.e.: t, one-sided p (H0: mean <= 0) and the normal 95% CI."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return {"mean": float(x.mean()) if n else None, "se": None, "t": None, "p": None, "ci": [None, None], "lag": lag, "n": int(n)}
    u = x - x.mean()
    s = float(u @ u) / n
    for l in range(1, min(int(lag), n - 1) + 1):
        s += 2.0 * (1.0 - l / (lag + 1.0)) * float(u[l:] @ u[:-l]) / n
    se = math.sqrt(max(s, 1e-300) / n)
    m = float(x.mean())
    return {"mean": m, "se": se, "t": m / se, "p": 1.0 - _N.cdf(m / se), "ci": [m - 1.959964 * se, m + 1.959964 * se],
            "lag": int(lag), "n": int(n)}


ONE_SIDED_LEVEL = 1.0 - 2.0 * ALPHA   # a one-sided 95% bound is an end of the two-sided 90% interval


def _stud_os(stat, cols, block: int, nb: int, seed: int, one_sided: bool) -> dict:
    """``_stud`` (two-sided 95% CI under 'ci'); with ``one_sided`` also the one-sided 95% lower / upper bounds under 'ci1'
    (the two-sided ONE_SIDED_LEVEL interval from the same seed, hence the same resamples)."""
    r = _stud(stat, cols, block, nb, seed)
    if one_sided:
        r["ci1"] = _stud(stat, cols, block, nb, seed, level=ONE_SIDED_LEVEL)["ci"]
    return r


def _lb_crit(t: dict, label: str, fmt=None) -> tuple:
    """'95% lower bound > 0' judged as the pass states it, one-sided (rule 6): the one-sided 95% lower bound ('ci1'[0]) must
    exceed 0 beyond its Monte Carlo error; decisive failure when the one-sided 95% upper bound lies below 0. The two-sided
    95% lower end is reported beside it. Returns (name, ok, decisive) like _ci_crit."""
    fmt = fmt or (lambda v: _s(v))
    lo, hi = t.get("ci1") or (None, None)
    se_lo, se_hi = t.get("ci1_mc_se") or (0.0, 0.0)
    ok, note = resolve(lo, se_lo, 0.0, "gt")
    dec = hi is not None and resolve(hi, se_hi, 0.0, "lt")[0] is True
    lo2 = (t.get("ci") or [None, None])[0]
    return f"{label} (one-sided 95% lower {fmt(lo)}; two-sided 95% lower {fmt(lo2)}){note}", ok, dec


def mean_test(x, block: int, n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED,
              one_sided: bool = False) -> dict:
    """Studentized circular block bootstrap of a mean: est, two-sided 95% CI (interval ends averaged over ``reps`` seeds,
    with their Monte Carlo s.e.; escalated when they cannot resolve against 0), p (H0: mean <= 0). ``one_sided``: also the
    one-sided 95% bounds ('ci1'), and the escalation resolves the one-sided lower bound instead."""
    nb = N_BOOT if n_boot is None else n_boot
    x = np.asarray(x, float)
    chk = (lambda t: _lb_crit(t, "")[1]) if one_sided else (lambda t: _ci_crit(t, "gt", 0.0, "")[1])
    return mc_escalate(lambda seed: _stud_os(_mean_stat, [x], block, nb, seed, one_sided), chk,
                       REPS if reps is None else reps, seed, keys=("ci", "ci_pct", "ci1"))


def _sr_one_stat(X, bw):
    """Row-wise per-period Sharpe (population moments) and its delta-method Bartlett-HAC s.e."""
    n = X.shape[1]
    m = X.mean(axis=1)
    g = (X * X).mean(axis=1)
    v = np.maximum(g - m ** 2, 1e-300)
    z = (g / v ** 1.5)[:, None] * (X - m[:, None]) - (m / (2 * v ** 1.5))[:, None] * (X * X - g[:, None])
    return m / np.sqrt(v), np.sqrt(_hac_var(z, bw) / n)


def sharpe_one_test(x, ppy: float, block: int, n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED,
                    thr: Optional[float] = None) -> dict:
    """Annualised Sharpe (ddof 1) of one series with its studentized CBB 95% CI (seeds averaged; escalated when ``thr`` is
    given and the CI's upper end cannot be resolved against it)."""
    nb = N_BOOT if n_boot is None else n_boot
    x = np.asarray(x, float)
    n = x.size
    c = math.sqrt(ppy) * math.sqrt((n - 1) / n) if n > 1 else 0.0

    def one(seed):
        r = _stud(_sr_one_stat, [x], block, nb, seed)
        sc = lambda v: [None if a is None else a * c for a in v]
        return {"est": None if r["est"] is None else r["est"] * c, "ci": sc(r["ci"]), "ci_pct": sc(r.get("ci_pct", [None, None])),
                "p": r["p"], "p_lt": r["p_lt"], "block": r["block"], "n": int(n)}

    def check(t):
        if thr is None:
            return True
        hi = (t.get("ci") or [None, None])[1]
        return resolve(hi, (t.get("ci_mc_se") or [0.0, 0.0])[1], thr, "lt")[0] if hi is not None else True

    out = mc_escalate(one, check, REPS if reps is None else reps, seed)
    out["sharpe"] = float(sharpe_ratio(x, ppy)) if n > 1 else None
    return out


def _ratio_stat(S, N, bw):
    """Row-wise ratio of means sum(S)/sum(N) and its delta-method Bartlett-HAC s.e. (clustered per period)."""
    n = S.shape[1]
    mn = np.maximum(N.mean(axis=1), 1e-300)
    R = S.mean(axis=1) / mn
    z = (S - R[:, None] * N) / mn[:, None]
    return R, np.sqrt(_hac_var(z, bw) / n)


def ratio_test(S, N, block: int, n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED,
               one_sided: bool = False) -> dict:
    """Pooled mean per trade sum(S)/sum(N) with a studentized circular block bootstrap over the date calendar (each date's
    trades resampled together: clustered by date). ``one_sided``: as in ``mean_test``."""
    nb = N_BOOT if n_boot is None else n_boot
    S, N = np.asarray(S, float), np.asarray(N, float)
    chk = (lambda t: _lb_crit(t, "")[1]) if one_sided else (lambda t: _ci_crit(t, "gt", 0.0, "")[1])
    return mc_escalate(lambda seed: _stud_os(_ratio_stat, [S, N], block, nb, seed, one_sided), chk,
                       REPS if reps is None else reps, seed, keys=("ci", "ci_pct", "ci1"))


def ols_hac(y, x, lag: int, kernel: str = "bartlett") -> dict:
    """OLS y = a + b x with a HAC s.e. of b: kernel 'bartlett' (Newey-West) or 'rect' (Hansen-Hodrick). A non-positive
    HAC variance (possible with the rectangular kernel) gives se None."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    n = y.size
    out = {"n": int(n), "a": None, "b": None, "se": None, "t": None, "lag": int(lag), "kernel": kernel, "r2": None}
    if n < 5 or not np.std(x) > 0:
        return out
    X = np.column_stack([np.ones(n), x])
    XtXi = np.linalg.inv(X.T @ X)
    coef = XtXi @ X.T @ y
    e = y - X @ coef
    u = X * e[:, None]
    S = u.T @ u
    for l in range(1, min(int(lag), n - 1) + 1):
        w = 1.0 if kernel == "rect" else 1.0 - l / (lag + 1.0)
        G = u[l:].T @ u[:-l]
        S = S + w * (G + G.T)
    V = XtXi @ S @ XtXi
    vb = float(V[1, 1])
    tss = float(((y - y.mean()) ** 2).sum())
    out.update(a=float(coef[0]), b=float(coef[1]), r2=1.0 - float(e @ e) / tss if tss > 0 else None)
    if vb > 0:
        out.update(se=math.sqrt(vb), t=float(coef[1]) / math.sqrt(vb))
    return out


def _slope_boot_once(y, x, block: int, n_boot: int, seed: int) -> dict:
    n = y.size
    rng = np.random.default_rng(seed)
    bl = max(1, min(int(block), n // 4))
    draws = []
    for k in _chunks(n_boot, 2 * n):
        idx = _boot_idx(rng, n, bl, k)
        X, Y = x[idx], y[idx]
        xm, ym = X.mean(axis=1), Y.mean(axis=1)
        vx = ((X - xm[:, None]) ** 2).sum(axis=1)
        ok = vx > 1e-300
        b = ((X - xm[:, None]) * (Y - ym[:, None])).sum(axis=1)[ok] / vx[ok]
        draws.append(b)
    d = np.concatenate(draws)
    xc = x - x.mean()
    b0 = float(xc @ (y - y.mean()) / (xc @ xc))
    se = float(d.std(ddof=1))
    return {"b": b0, "se": se, "t": b0 / se if se > 0 else None, "ci_pct": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))],
            "share_ge0": float(np.mean(d >= 0)), "block": bl}


def slope_boot(y, x, block: int, thr: float = -2.0, n_boot: Optional[int] = None, reps: Optional[int] = None,
               seed: int = SEED) -> dict:
    """Pairs circular block bootstrap of the OLS slope: t = slope / bootstrap s.e., averaged over ``reps`` seeds with its
    Monte Carlo s.e. (escalated to REPS_MAX seeds when that cannot resolve t against ``thr``)."""
    from mandel.experiments import batch6b_bw as _bw
    nb = N_BOOT if n_boot is None else n_boot
    y, x = np.asarray(y, float), np.asarray(x, float)
    if y.size < 8 or not np.std(x) > 0:
        return {"b": None, "se": None, "t": None, "t_mc_se": None, "ci_pct": [None, None], "reps": 0}

    def run(r):
        rs = [_slope_boot_once(y, x, block, nb, seed + k) for k in range(r)]
        ts = np.array([q["t"] for q in rs if q["t"] is not None], float)
        out = dict(rs[0])
        out["t"] = float(ts.mean()) if ts.size else None
        out["t_mc_se"] = float(ts.std(ddof=1) / math.sqrt(ts.size)) if ts.size > 1 else 0.0
        out["se"] = float(np.mean([q["se"] for q in rs]))
        out["ci_pct"] = [float(np.mean([q["ci_pct"][0] for q in rs])), float(np.mean([q["ci_pct"][1] for q in rs]))]
        out["reps"] = len(rs)
        return out

    r0 = REPS if reps is None else reps
    out = run(r0)
    if out["t"] is not None and resolve(out["t"], out["t_mc_se"], thr, "lt")[0] is None and _bw.REPS_MAX > r0:
        out = run(_bw.REPS_MAX)
    return out


def _sr_pp(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 else None


def _sr_ann(x, ppy: float) -> Optional[float]:
    s = _sr_pp(x)
    return None if s is None else s * math.sqrt(ppy)


def _mdd_simple(r) -> Optional[float]:
    r = np.asarray(r, float)
    if not r.size:
        return None
    c = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    return float((c / np.maximum.accumulate(c) - 1.0).min())


def _mdd_log(lr) -> Optional[float]:
    lr = np.asarray(lr, float)
    if not lr.size:
        return None
    c = np.concatenate([[0.0], np.cumsum(lr)])
    return float(np.exp(c - np.maximum.accumulate(c)).min() - 1.0)


# ================================================================================================= formatting ==

def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _pu(x, nd: int = 0) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:.{nd}f}%"


def _bpu(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 1e4:.{nd}f} bp"


def _bp(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 1e4:+.{nd}f} bp"


def _ci(ci, nd: int = 3, scale: float = 1.0, unit: str = "") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"95% CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _dsr_txt(d: dict) -> str:
    if d.get("dsr") is None:
        return "n/a"
    s = f"{d['dsr']:.3f}"
    if d.get("floor_binds"):
        s += f" (1/(T-1) floor binds; observed variance gives {_f(d.get('dsr_observed'))})"
    return s


def _month_add(m: str, k: int) -> str:
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    return f"{y + mo // 12:04d}-{mo % 12 + 1:02d}"


def _ord(d: str) -> int:
    return date.fromisoformat(d[:10]).toordinal()


# ==================================================================================== T-398 fund-flow timing ==

T398_MIN_N = 250
T398_H = 4
T398_H_ALT = 1
T398_BLOCK = 8                 # quarters (the trial's)
T398_MIN_HIST = 8              # quarters of x before the first z
T398_SPLIT = "1990-01-01"
T398_TCRIT = -2.0
T398_CRISIS_YEARS = ("1987", "2008", "2020")


def _qadd(q: str, k: int) -> str:
    y, m = int(q[:4]), int(q[5:7])
    i = y * 4 + (m - 1) // 3 + k
    return f"{i // 4:04d}-{(i % 4) * 3 + 1:02d}-01"


def _qstart(alf: Alfred) -> Optional[str]:
    """First quarter of the quarterly history: Q1 of the first year with four quarterly prints (Z.1 flows before 1952 are
    annual values stored at Q4)."""
    per_year = defaultdict(set)
    for k, (_, vals) in alf.obs.items():
        if any(v is not None for v in vals):
            per_year[k[:4]].add(k[5:7])
    years = sorted(y for y, ms in per_year.items() if {"01", "04", "07", "10"} <= ms)
    return f"{years[0]}-01-01" if years else None


def flow_panel(fa: Alfred, lm: Alfred, min_hist: int = T398_MIN_HIST) -> dict:
    """Point-in-time flow signal at each quarter's Z.1 release: R (release time: the later of the two series' first
    prints), x (4-quarter flow / market value) and z (expanding z of x over the vintage in force at R)."""
    q0 = max(filter(None, (_qstart(fa), _qstart(lm))), default=None)
    if q0 is None:
        return {"quarters": [], "R": {}, "x": {}, "z": {}, "n_hist": {}, "q0": None}
    qs = sorted(q for q in set(fa.obs) & set(lm.obs) if q >= q0)
    R = {}
    for q in qs:
        a, b = fa.first(q)[1], lm.first(q)[1]
        if a and b:
            R[q] = max(a, b)
    xs, zs, nh = {}, {}, {}
    rq = [q for q in qs if q in R]
    for q in rq:
        T = R[q]
        hist = []
        for j in qs:
            if j > q:
                break
            if _qadd(j, -3) < q0:
                continue
            f = [fa.at(_qadd(j, -k), T) for k in range(4)]
            m = lm.at(j, T)
            if any(v is None for v in f) or m is None or m <= 0:
                continue
            hist.append((j, sum(f) / 4.0 / m))
        if not hist or hist[-1][0] != q:
            continue
        xs[q] = hist[-1][1]
        if len(hist) >= min_hist:
            v = np.array([h[1] for h in hist])
            sd = float(v.std(ddof=1))
            if sd > 0:
                zs[q] = (hist[-1][1] - float(v.mean())) / sd
                nh[q] = len(hist)
    return {"quarters": rq, "R": R, "x": xs, "z": zs, "n_hist": nh, "q0": q0}


def _fill_index(close_times: Sequence[str], T: str) -> int:
    """Index of the first session whose close (20:00 UTC) is at or after T."""
    return bisect.bisect_left(close_times, T)


def _ff_excess(ff: dict) -> tuple:
    lm_ = np.concatenate([[0.0], np.cumsum(np.log1p(ff["mkt"]))])
    lf_ = np.concatenate([[0.0], np.cumsum(np.log1p(ff["rf"]))])
    ct = [d + CLOSE_UTC for d in ff["days"]]
    return lm_, lf_, ct


def flow_outcomes(panel: dict, ff: dict, h: int) -> dict:
    """{q: next-h-quarter market excess return from the close at q's release to the close at q+h's release}."""
    lm_, lf_, ct = _ff_excess(ff)
    nd = len(ff["days"])
    out = {}
    for q in panel["z"]:
        q2 = _qadd(q, h)
        if q2 not in panel["R"]:
            continue
        f0, f1 = _fill_index(ct, panel["R"][q]), _fill_index(ct, panel["R"][q2])
        if f0 >= nd or f1 >= nd or f1 <= f0:
            continue
        # cumulative arrays are offset by one: day i's return is index i + 1
        rm = math.exp(lm_[f1 + 1] - lm_[f0 + 1]) - 1.0
        rf = math.exp(lf_[f1 + 1] - lf_[f0 + 1]) - 1.0
        out[q] = rm - rf
    return out


def _flow_reg(qs: Sequence[str], y: np.ndarray, z: np.ndarray, h: int, n_boot=None, reps=None, seed=SEED, boot: bool = True) -> dict:
    n = len(qs)
    L_nw = max(2 * (h - 1), _nw_lag(n))
    hh = ols_hac(y, z, max(h - 1, 0), "rect") if h > 1 else ols_hac(y, z, 0, "rect")
    nw = ols_hac(y, z, L_nw, "bartlett")
    bb = slope_boot(y, z, T398_BLOCK, T398_TCRIT, n_boot, reps, seed) if boot else None
    return {"n": n, "hh": hh, "nw": nw, "bb": bb, "slope": nw["b"]}


def fund_flow_test(fa: Alfred, lm: Alfred, ff: dict, spy: Optional[tuple] = None, bills: Optional[Bills] = None,
                   min_n: int = T398_MIN_N, n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-398 core."""
    P = flow_panel(fa, lm)
    first_true = None
    res = {}
    for h in (T398_H, T398_H_ALT):
        Y = flow_outcomes(P, ff, h)
        qs = [q for q in sorted(P["z"]) if q in Y]
        y = np.array([Y[q] for q in qs], float)
        z = np.array([P["z"][q] for q in qs], float)
        res[h] = {"qs": qs, "y": y, "z": z, "reg": _flow_reg(qs, y, z, h, n_boot, reps, seed, boot=(h == T398_H))}
    m = res[T398_H]
    qs, y, z = m["qs"], m["y"], m["z"]
    n = len(qs)
    reg = m["reg"]
    halves = {}
    for nm, sel in (("1952-1989", [q < T398_SPLIT for q in qs]), ("1990-2026", [q >= T398_SPLIT for q in qs])):
        ii = np.array(sel, bool)
        halves[nm] = {"n": int(ii.sum()), "first": qs[int(np.argmax(ii))] if ii.any() else None,
                      "nw": ols_hac(y[ii], z[ii], max(2 * (T398_H - 1), _nw_lag(int(ii.sum()))), "bartlett") if ii.sum() >= 5 else ols_hac([], [], 0)}
    # secondary and diagnostics
    quint = None
    if n >= 20:
        top, bot = [], []
        for k, q in enumerate(qs):
            past = np.array([P["z"][j] for j in sorted(P["z"]) if j <= q])
            if past.size < 10:
                continue
            if z[k] >= np.quantile(past, 0.8):
                top.append(y[k])
            elif z[k] <= np.quantile(past, 0.2):
                bot.append(y[k])
        if top and bot:
            quint = {"top": float(np.mean(top)), "bottom": float(np.mean(bot)), "diff": float(np.mean(top) - np.mean(bot)),
                     "n_top": len(top), "n_bottom": len(bot)}
    exc = np.array([q[:4] not in T398_CRISIS_YEARS for q in qs], bool)
    ex_crisis = ols_hac(y[exc], z[exc], max(2 * (T398_H - 1), _nw_lag(int(exc.sum()))), "bartlett") if exc.sum() >= 5 else None
    # Stambaugh (1999) bias of the 1-quarter regression (reported only; the trial names no correction)
    st = None
    a1 = res[T398_H_ALT]
    if len(a1["qs"]) >= 20:
        zz = np.array([P["z"][q] for q in sorted(P["z"])])
        if zz.size > 10:
            z0, z1 = zz[:-1], zz[1:]
            rho = float(np.polyfit(z0, z1, 1)[0])
            v = z1 - np.polyval(np.polyfit(z0, z1, 1), z0)
            r1 = a1["reg"]["nw"]
            if r1["b"] is not None:
                idx = {q: k for k, q in enumerate(sorted(P["z"]))}
                e_pairs = []
                for k, q in enumerate(a1["qs"]):
                    j = idx[q]
                    if j < len(v):
                        e_pairs.append((a1["y"][k] - r1["a"] - r1["b"] * a1["z"][k], v[j]))
                if len(e_pairs) > 10:
                    e_, v_ = np.array(e_pairs).T
                    gam = float(np.cov(e_, v_)[0, 1] / np.var(v_, ddof=1))
                    bias = -gam * (1 + 3 * rho) / len(a1["qs"])
                    st = {"rho": rho, "gamma": gam, "bias": bias, "slope": r1["b"], "slope_adjusted": r1["b"] - bias}
    spy_chk = None
    if spy is not None and bills is not None:
        sd_, sa_ = spy
        ct = [d + CLOSE_UTC for d in sd_]
        ys, zs_ = [], []
        for q in qs:
            q2 = _qadd(q, T398_H)
            if P["R"][q][:10] < sd_[0]:
                continue
            f0, f1 = _fill_index(ct, P["R"][q]), _fill_index(ct, P["R"][q2])
            if f1 >= len(sd_) or f1 <= f0:
                continue
            ys.append(sa_[f1] / sa_[f0] - 1.0 - (bills.growth(sd_[f0], sd_[f1]) - 1.0))
            zs_.append(P["z"][q])
        if len(ys) >= 20:
            spy_chk = ols_hac(np.array(ys), np.array(zs_), max(2 * (T398_H - 1), _nw_lag(len(ys))), "bartlett")
    vint_note = sum(1 for q in qs if P["R"][q] >= "2019-03-07")

    def trow(name, t):
        if t is None:
            return f"{name} t n/a", None, False
        return f"{name} t {t:+.2f}", t <= T398_TCRIT, t >= -T398_TCRIT

    bb = reg["bb"] or {}
    if bb.get("t") is None:
        bb_row = ("8-quarter block bootstrap t n/a", None, False)
    else:
        ok, note = resolve(bb["t"], bb.get("t_mc_se"), T398_TCRIT, "lt")
        bb_row = (f"8-quarter pairs block bootstrap t {bb['t']:+.2f} (slope / bootstrap s.e., {bb['reps']} seeds){note}", ok,
                  bb["t"] >= -T398_TCRIT)
    crit = [all_constructions([trow(f"Hansen-Hodrick ({reg['hh']['lag']} lags)", reg["hh"]["t"]),
                               trow(f"Newey-West ({reg['nw']['lag']} lags)", reg["nw"]["t"]), bb_row],
                              f"next-4-quarter slope {_s(reg['slope'], 4)} per z: t <= -2 under every overlapping-return "
                              f"correction the trial names (rule 11)")]
    for nm, hv in halves.items():
        b = hv["nw"]["b"]
        crit.append((f"{nm} slope < 0 ({_s(b, 4)}, NW t {_s(hv['nw']['t'], 2)}, {hv['n']} quarters)", None if b is None else b < 0,
                     hv["nw"]["t"] is not None and hv["nw"]["t"] >= -T398_TCRIT))
    v, why = _decide(crit, n, min_n, "quarters")
    alt = res[T398_H_ALT]["reg"]
    return {"n": n, "window": [qs[0], qs[-1]] if qs else None, "reg": reg, "halves": halves, "quintile": quint, "ex_crisis": ex_crisis,
            "stambaugh_h1": st, "spy": spy_chk, "h1": {"n": alt["n"], "slope": alt["slope"], "hh_t": alt["hh"]["t"], "nw_t": alt["nw"]["t"]},
            "n_vintage_decisions": vint_note, "q0": P["q0"], "mean_y": float(y.mean()) if n else None,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_macro_fund_flow_dumb_money(archive):
    """T-398."""
    need = [al(FA_SID), al(LM_SID), FF3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    fa, lm, ff = _alfred(archive, FA_SID), _alfred(archive, LM_SID), _ff3(archive)
    spy = bills = None
    if _has(archive, dh("SPY")) and _has(archive, DTB3_B):
        d = _daily(archive, dh("SPY"))
        spy, bills = (d["days"], d["adj"]), _bills(archive)
    j = fund_flow_test(fa, lm, ff, spy, bills)
    r, hv = j["reg"], j["halves"]
    bb = r["bb"] or {}
    q = j["quintile"]
    sp = j["spy"]
    st = j["stambaugh_h1"]
    reason = (f"Signal: Z.1 mutual-fund net equity purchases (4-quarter sum of SAAR/4) over corporate-equity market value, "
              f"quarterly flows from {j['q0'][:7] if j['q0'] else 'n/a'}, expanding z (from 8 quarters of history) in the vintage in "
              f"force at each quarter's Z.1 release "
              f"(ALFRED vintages from 2019-03-07: {j['n_vintage_decisions']} decisions; earlier ones use the 2019 vintage counted "
              f"from quarter end + 84 days (the fetcher's lag_rule_at; true pre-2019 release dates unknown), so pre-2019 "
              f"revisions are a stated look-ahead limitation); outcome: Ken French Mkt-RF + RF "
              f"compounded from the close at the release to the close at the release 4 quarters later (excess over RF). "
              f"Flow quarters {j['window'][0][:7] if j['window'] else 'n/a'}..{j['window'][1][:7] if j['window'] else 'n/a'} "
              f"({j['n']} quarters, min_n {T398_MIN_N}); slope {_s(r['slope'], 4)} per unit z (R^2 {_f(r['nw']['r2'])}): Hansen-"
              f"Hodrick t {_s(r['hh']['t'], 2)}, Newey-West t {_s(r['nw']['t'], 2)}, block-bootstrap t {_s(bb.get('t'), 2)} "
              f"(percentile {_ci(bb.get('ci_pct'), 4)}); halves 1952-1989 {_s(hv['1952-1989']['nw']['b'], 4)} "
              f"({hv['1952-1989']['n']} q), 1990-2026 {_s(hv['1990-2026']['nw']['b'], 4)} ({hv['1990-2026']['n']} q). "
              f"1-quarter trial: slope {_s(j['h1']['slope'], 4)}, NW t {_s(j['h1']['nw_t'], 2)} ({j['h1']['n']} q). "
              + (f"Top-minus-bottom expanding-quintile 4-quarter excess return {_pc(q['diff'])} ({q['n_top']}/{q['n_bottom']} q). " if q else "")
              + (f"Ex-1987/2008/2020 slope {_s(j['ex_crisis']['b'], 4)} (NW t {_s(j['ex_crisis']['t'], 2)}). " if j["ex_crisis"] else "")
              + (f"SPY cross-check (1993-): slope {_s(sp['b'], 4)}, NW t {_s(sp['t'], 2)} ({sp['n']} q). " if sp else "")
              + (f"Stambaugh bias of the 1-quarter slope (rho {st['rho']:.2f}): adjusted {_s(st['slope_adjusted'], 4)} "
                 f"(reported only) " if st else "")
              + "— " + j["why"])
    stat = {"n_quarters": j["n"], "window": j["window"], "slope": r["slope"], "r2": r["nw"]["r2"], "hh_t": r["hh"]["t"],
            "nw_t": r["nw"]["t"], "nw_lag": r["nw"]["lag"], "boot_t": bb.get("t"), "boot_t_mc_se": bb.get("t_mc_se"),
            "boot_ci_pct": bb.get("ci_pct"), "halves": {k: {"n": v["n"], "slope": v["nw"]["b"], "nw_t": v["nw"]["t"]} for k, v in hv.items()},
            "h1": j["h1"], "quintile": q, "ex_crisis": None if not j["ex_crisis"] else {"slope": j["ex_crisis"]["b"], "nw_t": j["ex_crisis"]["t"]},
            "spy": None if not sp else {"slope": sp["b"], "nw_t": sp["t"], "n": sp["n"]}, "stambaugh_h1": st,
            "n_vintage_decisions": j["n_vintage_decisions"], "criteria": j["criteria"],
            "rule10": "calendar: Z.1 release dates (the library's rebalance-on-release rule)"}
    return _out(stat, j["n"], j["verdict"], reason)


# ============================================================================= T-458 sentiment and the size spread ==

T458_START = "1990-01"
T458_ORTH_FROM = "1978-02"
T458_MIN_N = 400
T458_MIN_TRAIN = 24
T458_COST = 5e-4               # per leg on every change in exposure
T458_SHARPE_THR = 0.3
T458_HORIZONS = (1, 3, 12)
T458_SPREADS = ("RUT-GSPC", "SPHB-SPLV")
T458_SIGNALS = ("orth", "raw")
T458_PRIMARY = ("orth", 3, "RUT-GSPC")
T458_AVAIL = ("next-month", "alfred")
T458_FORECASTS = ("continuous", "tercile")
T458_BLOCK = 12
T458_HOLD = 3


def _mkey(m: str) -> str:
    return m + "-01"


def _next_month_start(day: str) -> str:
    return _month_add(day[:7], 1) + "-01T05:00:00+00:00"        # 00:00 New York


class Released:
    """A monthly ALFRED series as first published: for each observation month, the time of its first print and a feature
    computed inside that first-release vintage ('level', 'diff12' = x(m) - x(m-12), 'log12' = 100 ln(x(m)/x(m-12)))."""

    def __init__(self, alf: Alfred, kind: str, avail: str = "alfred"):
        self.R, self.val = {}, {}
        for k in alf.obs:
            v, st = alf.first(k)
            if v is None:
                continue
            if avail == "next-month":
                st = _next_month_start(k)
            if kind == "level":
                f = v
            else:
                prev = alf.at(_mkey(_month_add(k[:7], -12)), alf.first(k)[1])
                if prev is None or (kind == "log12" and (prev <= 0 or v <= 0)):
                    continue
                f = v - prev if kind == "diff12" else 100.0 * math.log(v / prev)
            self.R[k[:7]], self.val[k[:7]] = st, f

    def latest(self, T: str, back: int = 8) -> tuple:
        """(observation month, feature) of the latest month whose first print is public at T."""
        m0 = T[:7]
        for k in range(0, back + 1):
            m = _month_add(m0, -k)
            st = self.R.get(m)
            if st is not None and st <= T:
                return m, self.val[m]
        return None, None


def _holm_ok(hp: dict) -> tuple:
    """(passes Holm at ALPHA: True/False/None, text) from batch6c_mom.holm_primary's exact value or bounds."""
    if hp.get("adj") is not None:
        return hp["adj"] < ALPHA, f"{hp['adj']:.4f}"
    if hp.get("hi") is not None and hp["hi"] < ALPHA:
        return True, f"<= {hp['hi']:.4f} ({hp['n_known']}/{hp['m']} cells computed)"
    if hp.get("lo") is not None and hp["lo"] >= ALPHA:
        return False, f">= {hp['lo']:.4f} ({hp['n_known']}/{hp['m']} cells computed)"
    return None, f"unresolved ({hp.get('n_known')}/{hp.get('m')} cells computed)"


def _decision_days(days: Sequence[str], start: str) -> list:
    """First session of each month from ``start`` (YYYY-MM)."""
    out, seen = [], set()
    for d in days:
        if d[:7] >= start and d[:7] not in seen:
            seen.add(d[:7])
            out.append(d)
    return out


def _price_at(days: Sequence[str], px: np.ndarray) -> dict:
    return {d: float(p) for d, p in zip(days, px)}


def sentiment_rows(umc: Released, unr: Released, cpi: Released, dtb3: dict, dec_days: Sequence[str]) -> dict:
    """One row per decision day: S (sentiment as known), X (dU12, pi12, dr12), the observation months used."""
    bd = sorted(dtb3)
    bv = [dtb3[k] for k in bd]

    def bill_before(d):
        i = bisect.bisect_left(bd, d) - 1
        return bv[i] if i >= 0 else None

    K = len(dec_days)
    S = np.full(K, np.nan)
    X = np.full((K, 3), np.nan)
    obs = []
    for k, d in enumerate(dec_days):
        T = d + CLOSE_UTC
        ms, s = umc.latest(T)
        mu, u = unr.latest(T)
        mc, c = cpi.latest(T)
        r1 = bill_before(d)
        r0 = bill_before(dec_days[k - 12]) if k >= 12 else None
        obs.append((ms, mu, mc))
        if s is None or u is None or c is None or r1 is None or r0 is None:
            continue
        S[k] = s
        X[k] = (u, c, r1 - r0)
    return {"days": list(dec_days), "S": S, "X": X, "obs": obs}


def spread_outcomes(dec_days: Sequence[str], a: dict, b: dict, h: int) -> np.ndarray:
    """y[k] = simple return of A minus that of B from decision day k to decision day k + h (NaN when unavailable)."""
    K = len(dec_days)
    y = np.full(K, np.nan)
    for k in range(K - h):
        d0, d1 = dec_days[k], dec_days[k + h]
        if d0 in a and d1 in a and d0 in b and d1 in b:
            y[k] = (a[d1] / a[d0] - 1.0) - (b[d1] / b[d0] - 1.0)
    return y


def _ols_fit(y: np.ndarray, x: np.ndarray) -> tuple:
    xm = x.mean()
    vx = float(((x - xm) ** 2).sum())
    if vx <= 1e-300:
        return float(y.mean()), 0.0
    b = float(((x - xm) * (y - y.mean())).sum() / vx)
    return float(y.mean() - b * xm), b


def sentiment_oos(rows: dict, Y: dict, signal: str, start: str = T458_START, min_train: int = T458_MIN_TRAIN,
                  orth_from: str = T458_ORTH_FROM) -> dict:
    """Expanding-window engine for one signal ('orth' | 'raw'). Y: {(h, spread): y array}. Returns per cell the OOS
    records (t, y, bench, continuous forecast, tercile forecast) and per decision the residual tercile signal."""
    days, S, X = rows["days"], rows["S"], rows["X"]
    K = len(days)
    valid = np.isfinite(S) & np.isfinite(X).all(axis=1) & np.array([d[:7] >= orth_from for d in days])
    recs = {key: [] for key in Y}
    terc = np.zeros(K)
    resid = np.full(K, np.nan)
    tdec = [k for k in range(K) if days[k][:7] >= start]
    for t in tdec:
        if not valid[t]:
            continue
        idx = np.where(valid[: t + 1])[0]
        if idx.size < 24:
            continue
        if signal == "orth":
            A = np.column_stack([np.ones(idx.size), X[idx]])
            coef, *_ = np.linalg.lstsq(A, S[idx], rcond=None)
            e = S[idx] - A @ coef
        else:
            e = S[idx].copy()
        q1, q2 = np.quantile(e, [1.0 / 3.0, 2.0 / 3.0])
        D = np.where(e > q2, 1.0, np.where(e < q1, -1.0, 0.0))
        resid[t], terc[t] = e[-1], D[-1]
        for (h, sp), y in Y.items():
            if not np.isfinite(y[t]):
                continue
            ii = np.where((idx <= t - h) & np.isfinite(y[idx]))[0]
            if ii.size < min_train:
                continue
            yt = y[idx[ii]]
            bench = float(yt.mean())
            a1, b1 = _ols_fit(yt, e[ii])
            a2, b2 = _ols_fit(yt, D[ii])
            recs[(h, sp)].append((t, float(y[t]), bench, a1 + b1 * e[-1], a2 + b2 * D[-1], b1))
    return {"recs": recs, "terc": terc, "resid": resid, "tdec": tdec}


def clark_west(rec: Sequence[tuple], h: int, which: int) -> dict:
    """Campbell-Thompson OOS R^2 and the Clark-West MSPE-adjusted test of a forecast (``which`` = 3 continuous, 4 tercile)
    against the expanding historical mean; HAC lag max(h - 1, NW automatic)."""
    if len(rec) < 10:
        return {"n": len(rec), "r2": None, "cw_t": None, "p": None}
    arr = np.array([(r[1], r[2], r[which]) for r in rec], float)
    y, fb, fm = arr[:, 0], arr[:, 1], arr[:, 2]
    e1, e2 = y - fb, y - fm
    f = e1 ** 2 - (e2 ** 2 - (fb - fm) ** 2)
    hm = hac_mean(f, max(h - 1, _nw_lag(f.size)))
    return {"n": int(y.size), "r2": 1.0 - float(e2 @ e2) / float(e1 @ e1) if float(e1 @ e1) > 0 else None,
            "cw_t": hm["t"], "p": hm["p"], "lag": hm["lag"]}


def ls_book(terc: np.ndarray, m1: np.ndarray, tdec: Sequence[int], hold: int = T458_HOLD, cost: float = T458_COST,
            phase: Optional[int] = None) -> dict:
    """Tercile long-short on the spread A - B: exposure s = -1 after a top-tercile reading (short A / long B), +1 after a
    bottom-tercile reading. phase None: overlapping monthly cohorts held ``hold`` months (1/hold each); phase p: a
    non-overlapping grid that decides only at offsets p mod hold. Monthly net return = P x m1 - 2 legs x cost x |dP|."""
    t0 = tdec[0] if tdec else 0
    s = -np.asarray(terc, float)
    rets, labels = [], []
    prev = 0.0
    cur = 0.0
    for t in tdec:
        if not np.isfinite(m1[t]):
            continue
        if phase is None:
            P = sum(s[t - k] for k in range(hold) if t - k >= t0) / hold
        else:
            if (t - t0) % hold == phase:
                cur = s[t]
            P = cur
        rets.append(P * m1[t] - 2.0 * cost * abs(P - prev))
        labels.append(t)
        prev = P
    return {"r": np.array(rets, float), "t": labels}


def sentiment_test(umc_alf: Alfred, unr_alf: Alfred, cpi_alf: Alfred, dtb3: dict, gspc: tuple, rut: tuple, sphb: tuple, splv: tuple,
                   min_n: int = T458_MIN_N, n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-458 core. gspc/rut/sphb/splv: (days, levels)."""
    gd = gspc[0]
    dec = _decision_days(gd, _month_add(T458_ORTH_FROM, -13))        # 12 months of bill history before the first row
    A = {"RUT-GSPC": (_price_at(*rut), _price_at(*gspc)), "SPHB-SPLV": (_price_at(*sphb), _price_at(*splv))}
    Y = {(h, sp): spread_outcomes(dec, a, b, h) for h in T458_HORIZONS for sp, (a, b) in A.items()}
    m1 = Y[(1, "RUT-GSPC")]
    unr = Released(unr_alf, "diff12")
    cpi = Released(cpi_alf, "log12")
    cells = [(sg, h, sp) for sg in T458_SIGNALS for h in T458_HORIZONS for sp in T458_SPREADS]
    out = {}
    for av in T458_AVAIL:
        rows = sentiment_rows(Released(umc_alf, "level", av), unr, cpi, dtb3, dec)
        eng = {sg: sentiment_oos(rows, Y, sg) for sg in T458_SIGNALS}
        cw = {fc: {c: clark_west(eng[c[0]]["recs"][(c[1], c[2])], c[1], 3 if fc == "continuous" else 4) for c in cells}
              for fc in T458_FORECASTS}
        holm = {fc: holm_primary({c: cw[fc][c]["p"] for c in cells}, T458_PRIMARY) for fc in T458_FORECASTS}
        prim = eng["orth"]
        rec = prim["recs"][(3, "RUT-GSPC")]
        top = [r[1] for r in rec if prim["terc"][r[0]] > 0]
        topm = hac_mean(top, T458_HOLD - 1) if len(top) >= 3 else {"mean": None, "ci": [None, None], "n": len(top)}
        book = ls_book(prim["terc"], m1, prim["tdec"])
        tb = [t for t in prim["tdec"] if np.isfinite(rows["S"][t])]
        shp = sharpe_one_test(book["r"], 12, T458_BLOCK, n_boot, reps, seed, thr=T458_SHARPE_THR) if book["r"].size > 8 else {"sharpe": None, "ci": [None, None]}
        phases = [_sr_ann(ls_book(prim["terc"], m1, prim["tdec"], phase=p)["r"], 12) for p in range(T458_HOLD)]
        stale = [(_ord(rows["days"][t]) - _ord(rows["obs"][t][0] + "-01")) / 30.44 for t in tb if rows["obs"][t][0]]
        # restricted Campbell-Thompson R^2 (continuous forecast replaced by the mean when the slope is positive)
        rr = None
        if rec:
            arr = np.array([(r[1], r[2], r[3] if r[5] <= 0 else r[2]) for r in rec])
            e1, e2 = arr[:, 0] - arr[:, 1], arr[:, 0] - arr[:, 2]
            rr = 1.0 - float(e2 @ e2) / float(e1 @ e1) if float(e1 @ e1) > 0 else None
        halves = {}
        if rec:
            mid = rows["days"][rec[len(rec) // 2][0]][:7]
            for nm, sel in (("first", [r for r in rec if rows["days"][r[0]][:7] < mid]), ("second", [r for r in rec if rows["days"][r[0]][:7] >= mid])):
                c_ = clark_west(sel, 3, 3)
                halves[nm] = {"from": rows["days"][sel[0][0]][:7] if sel else None, "n": c_["n"], "r2": c_["r2"]}
        out[av] = {"cw": cw, "holm": holm, "n": len(rec), "top": topm, "n_top": len(top), "book": book, "sharpe": shp,
                   "phase_sharpes": phases, "stale_months_mean": float(np.mean(stale)) if stale else None,
                   "r2_restricted": rr, "halves": halves,
                   "first_oos": rows["days"][rec[0][0]] if rec else None, "last_oos": rows["days"][rec[-1][0]] if rec else None,
                   "share_top": float(np.mean(prim["terc"][tb] > 0)) if tb else None,
                   "share_bottom": float(np.mean(prim["terc"][tb] < 0)) if tb else None}
    n = min(out[av]["n"] for av in T458_AVAIL)
    crit = [(f"at least {T458_MIN_N} monthly out-of-sample observations ({' / '.join(f'{av} {out[av]['n']}' for av in T458_AVAIL)})",
             n >= T458_MIN_N, True)]
    rows_top = []
    for av in T458_AVAIL:
        tm = out[av]["top"]
        rows_top.append((f"{av}: {_pc(tm.get('mean'))} over {out[av]['n_top']} top-tercile months ({_ci(tm.get('ci'), 4)}, NW)",
                         None if tm.get("mean") is None else tm["mean"] < 0,
                         tm.get("ci", [None])[0] is not None and tm["ci"][0] > 0))
    crit.append(all_constructions(rows_top, "mean 3-month ^RUT-minus-^GSPC return after a top-tercile orthogonalised reading < 0 "
                                            "under both availability rules the claim names"))
    rows_cw = []
    for av in T458_AVAIL:
        for fc in T458_FORECASTS:
            c = out[av]["cw"][fc][T458_PRIMARY]
            hp = out[av]["holm"][fc]
            h_ok, h_txt = _holm_ok(hp)
            ok = None if c["r2"] is None or h_ok is None else (c["r2"] > 0 and h_ok)
            if c["r2"] is not None and c["r2"] <= 0:
                ok = False
            dec = c["r2"] is not None and c["cw_t"] is not None and c["cw_t"] < -1.645
            rows_cw.append((f"{av}/{fc}: R^2_OS {_pc(c['r2'])}, CW t {_s(c['cw_t'], 2)}, p {_f(c['p'], 4)}, Holm over 12 cells "
                            f"{h_txt}", ok, dec))
    crit.append(all_constructions(rows_cw, "OOS R^2 > 0 with Clark-West p < 0.05 after Holm deflation over the 12 cells (both "
                                           "availability rules x continuous/tercile forecasts)"))
    rows_sh = []
    for av in T458_AVAIL:
        sh = out[av]["sharpe"]
        hi = (sh.get("ci") or [None, None])[1]
        dec = hi is not None and resolve(hi, (sh.get("ci_mc_se") or [0.0, 0.0])[1], T458_SHARPE_THR, "lt")[0] is True
        rows_sh.append((f"{av}: {_s(sh.get('sharpe'))} ({_ci(sh.get('ci'))})", None if sh.get("sharpe") is None else sh["sharpe"] > T458_SHARPE_THR, dec))
    crit.append(all_constructions(rows_sh, f"net Sharpe of the tercile long-short > {T458_SHARPE_THR} (point estimate; 5 bps per leg)"))
    v, why = _decide(crit, n, min_n, "months")
    return {"n": n, "by_avail": out, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_macro_sentiment_size_premium(archive):
    """T-458."""
    need = [al(UMC_SID), al(UNR_SID), al(CPI_SID), DTB3_B, dh("^GSPC"), dh("^RUT"), dh("SPHB"), dh("SPLV")]
    miss = _missing(archive, need)
    if miss:
        return miss
    px = {s: _daily(archive, dh(s)) for s in ("^GSPC", "^RUT", "SPHB", "SPLV")}
    j = sentiment_test(_alfred(archive, UMC_SID), _alfred(archive, UNR_SID), _alfred(archive, CPI_SID), _series(archive, DTB3_B),
                       (px["^GSPC"]["days"], px["^GSPC"]["close"]), (px["^RUT"]["days"], px["^RUT"]["close"]),
                       (px["SPHB"]["days"], px["SPHB"]["adj"]), (px["SPLV"]["days"], px["SPLV"]["adj"]))
    parts = []
    for av, o in j["by_avail"].items():
        c, ct = o["cw"]["continuous"][T458_PRIMARY], o["cw"]["tercile"][T458_PRIMARY]
        others = ", ".join(f"{sg}/{h}m/{sp} {_pc(o['cw']['continuous'][(sg, h, sp)]['r2'], 1)}" for sg in T458_SIGNALS
                           for h in T458_HORIZONS for sp in T458_SPREADS if (sg, h, sp) != T458_PRIMARY)
        sh = o["sharpe"]
        ph = [x for x in o["phase_sharpes"] if x is not None]
        parts.append(f"[{av} availability: OOS decisions {(o['first_oos'] or 'n/a')[:7]}..{(o['last_oos'] or 'n/a')[:7]} ({o['n']}), "
                     f"sentiment on average {_f(o['stale_months_mean'], 1)} months old at the decision; R^2_OS continuous "
                     f"{_pc(c['r2'])} (CW t {_s(c['cw_t'], 2)}, Holm p {_f(o['holm']['continuous']['adj'], 4)}), tercile "
                     f"{_pc(ct['r2'])} (CW t {_s(ct['cw_t'], 2)}, Holm p {_f(o['holm']['tercile']['adj'], 4)}); restricted "
                     f"(slope <= 0) {_pc(o['r2_restricted'])}; halves "
                     + ", ".join(f"from {hv['from']} {_pc(hv['r2'])}" for hv in o["halves"].values())
                     + f"; top-tercile mean 3-month spread {_pc(o['top'].get('mean'))} ({o['n_top']} months; top/bottom shares "
                     f"{_pu(o['share_top'])}/{_pu(o['share_bottom'])}); long-short net Sharpe {_s(sh.get('sharpe'))} "
                     f"({_ci(sh.get('ci'))}), per-phase non-overlapping range {_s(min(ph, default=None))}.."
                     f"{_s(max(ph, default=None))}; other cells' continuous R^2_OS: {others}]")
    reason = ("UMCSENT orthogonalised in the expanding window on the latest first-release 12-month changes in UNRATE, CPI "
              "inflation (both taken inside their first-release vintages) and DTB3, decided at the close of each month's first "
              "session; 3-month ^RUT - ^GSPC price-return spread from that close; Campbell-Thompson OOS R^2 against the "
              "expanding mean, Clark-West (HAC) one-sided, Holm over the 12 declared cells; long-short in overlapping 3-month "
              "cohorts, 5 bps per leg. " + " ".join(parts) + " — " + j["why"])
    stat = {"n_months": j["n"], "criteria": j["criteria"], "by_avail": {}}
    for av, o in j["by_avail"].items():
        stat["by_avail"][av] = {
            "n": o["n"], "first_oos": o["first_oos"], "last_oos": o["last_oos"],
            "cells": {f"{sg}|{h}|{sp}|{fc}": o["cw"][fc][(sg, h, sp)] for fc in T458_FORECASTS for sg in T458_SIGNALS
                      for h in T458_HORIZONS for sp in T458_SPREADS},
            "holm": o["holm"], "top_mean": o["top"].get("mean"), "top_ci": o["top"].get("ci"), "n_top": o["n_top"],
            "sharpe": o["sharpe"].get("sharpe"), "sharpe_ci": o["sharpe"].get("ci"), "phase_sharpes": o["phase_sharpes"],
            "r2_restricted": o["r2_restricted"], "halves": o["halves"], "stale_months_mean": o["stale_months_mean"]}
    stat["rule10"] = "calendar: first session of each month (the claim's availability rule); book = overlapping 3-month cohorts (pooled all-start), per-phase range reported"
    return _out(stat, j["n"], j["verdict"], reason)


# =============================================================================== T-479 DAA canary vs rotation ==

T479_RISKY = ("SPY", "IWM", "QQQ", "VGK", "EWJ", "VWO", "VNQ", "DBC", "GLD", "TLT", "HYG", "LQD")
T479_CASH = ("SHY", "IEF", "LQD")
T479_CANARIES = {"VWO+BND": ("VWO", "BND"), "SPY+BND": ("SPY", "BND")}
T479_ALL = tuple(sorted(set(T479_RISKY) | set(T479_CASH) | {"BND"}))
T479_START, T479_END = "2008-05", "2026-09"
T479_COST = 5e-4
T479_MIN_N = 200
T479_BLOCK = 12
T479_FAMILY = tuple((T, cn, B) for T in (6, 3) for cn in ("VWO+BND", "SPY+BND") for B in (2, 1))
T479_PRIMARY = (6, "VWO+BND", 2)
T479_PBO_PARTS = 8
T479_YEARS = ("2008", "2020", "2022")


def score_13612w(P: np.ndarray, t: int) -> np.ndarray:
    """(12 r1 + 4 r3 + 2 r6 + r12) / 4 at month-end t from month-end levels P (months x assets)."""
    r = lambda k: P[t] / P[t - k] - 1.0
    return (12.0 * r(1) + 4.0 * r(3) + 2.0 * r(6) + r(12)) / 4.0


def daa_weights(sc: dict, T: int, canary: Sequence[str], B: int, cols: Sequence[str]) -> np.ndarray:
    w = np.zeros(len(cols))
    ci = {s: i for i, s in enumerate(cols)}
    bad = sum(1 for c in canary if sc[c] <= 0)
    cf = min(1.0, bad / B) if B > 0 else 0.0
    if cf < 1.0:
        k = int(math.ceil(T * (1.0 - cf) - 1e-12))
        top = sorted(T479_RISKY, key=lambda s: (-sc[s], s))[:k]
        for s in top:
            w[ci[s]] += (1.0 - cf) / k
    if cf > 0:
        best = sorted(T479_CASH, key=lambda s: (-sc[s], s))[0]
        w[ci[best]] += cf
    return w


def rotation_weights(sc: dict, T: int, cols: Sequence[str]) -> np.ndarray:
    w = np.zeros(len(cols))
    ci = {s: i for i, s in enumerate(cols)}
    for s in sorted(T479_RISKY, key=lambda s: (-sc[s], s))[:T]:
        w[ci[s]] = 1.0 / T
    return w


def daa_panel(series: dict, bills: Bills) -> dict:
    """Common calendar of all 15 ETFs; month-end decisions, next-session fills; hold returns, bills, labels."""
    cols = list(T479_ALL)
    common = None
    for s in cols:
        common = set(series[s][0]) if common is None else common & set(series[s][0])
    days = sorted(common or ())
    maps = {s: dict(zip(series[s][0], series[s][1])) for s in cols}
    lv = np.column_stack([np.array([maps[s][d] for d in days], float) for s in cols]) if days else np.zeros((0, len(cols)))
    g = month_grid(days)
    me, ex = g["me"], g["ex"]
    C = bill_logcum(bills, days) if days else np.zeros(0)
    P = lv[me]
    nT = len(me) - 1
    R = lv[ex[1:]] / lv[ex[:-1]] - 1.0
    rf = np.exp(C[ex[1:]] - C[ex[:-1]]) - 1.0
    labels = [days[i][:7] for i in ex[:-1]]
    return {"cols": cols, "P": P, "R": R, "rf": rf, "labels": labels, "n": nT, "days": days}


def daa_run(panel: dict, cfg: tuple, start: str = T479_START, end: str = T479_END, cost: float = T479_COST) -> dict:
    T, cn, B = cfg
    cols, P, R, rf, labels = panel["cols"], panel["P"], panel["R"], panel["rf"], panel["labels"]
    ts = [t for t in range(panel["n"]) if t >= 12 and start <= labels[t] <= end]
    if not ts:
        return {"labels": [], "daa": np.zeros(0), "rot": np.zeros(0), "to_daa": np.zeros(0), "to_rot": np.zeros(0), "cash_share": None}
    Wd, Wr = [], []
    cash = []
    for t in ts:
        s = score_13612w(P, t)
        sc = dict(zip(cols, s))
        wd = daa_weights(sc, T, T479_CANARIES[cn], B, cols)
        Wd.append(wd)
        Wr.append(rotation_weights(sc, T, cols))
        bad = sum(1 for c in T479_CANARIES[cn] if sc[c] <= 0)
        cash.append(min(1.0, bad / B))
    Wd, Wr = np.array(Wd), np.array(Wr)
    Rt, rft = R[ts], rf[ts]
    out = {"labels": [labels[t] for t in ts]}
    for nm, W in (("daa", Wd), ("rot", Wr)):
        pre = (W * Rt).sum(axis=1)
        to = drift_turnover(W, Rt, pre)
        out[nm] = pre - cost * to - rft
        out["to_" + nm] = to
    out["cash_share"] = float(np.mean(cash))
    return out


def daa_test(series: dict, bills: Bills, min_n: int = T479_MIN_N, family: Optional[Sequence[tuple]] = None,
             n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-479 core. series: {sym: (days, adjclose)}."""
    family = T479_FAMILY if family is None else tuple(family)
    panel = daa_panel(series, bills)
    res = {cfg: daa_run(panel, cfg) for cfg in family}
    pk = T479_PRIMARY if T479_PRIMARY in res else family[0]
    pv = res[pk]
    n = len(pv["labels"])
    nb = N_BOOT if n_boot is None else n_boot
    sh = mc_escalate(lambda seed: sharpe_diff_test(pv["daa"], pv["rot"], 12, T479_BLOCK, nb, seed),
                     lambda t: _ci_crit(t, "gt", 0.0, "")[1], REPS if reps is None else reps, seed) if n >= 8 else {"diff": None, "ci": [None, None]}
    d_strat = family_dsr(pv["daa"], [_sr_pp(r["daa"]) for r in res.values()], len(family))
    d_diff = family_dsr(pv["daa"] - pv["rot"], [_sr_pp(r["daa"] - r["rot"]) for r in res.values()], len(family))
    L = min(len(r["labels"]) for r in res.values())
    pbo_s = pbo_cscv(np.column_stack([r["daa"][-L:] for r in res.values()]), T479_PBO_PARTS) if L >= 2 * T479_PBO_PARTS and len(res) > 1 else None
    pbo_d = pbo_cscv(np.column_stack([(r["daa"] - r["rot"])[-L:] for r in res.values()]), T479_PBO_PARTS) if L >= 2 * T479_PBO_PARTS and len(res) > 1 else None
    pbo_rows = [(f"{nm} {_f(p['pbo'])} ({p['n_combinations']} CSCV splits)" if p else f"{nm} n/a",
                 None if p is None else p["pbo"] < 0.5, False) for nm, p in (("DAA excess returns", pbo_s), ("DAA - rotation", pbo_d))]
    crit = [_ci_crit(sh, "gt", 0.0, "Sharpe(DAA) - Sharpe(no-canary top-6 rotation) > 0 with the paired block-bootstrap 95% "
                                    "interval excluding 0"),
            all_constructions([dsr_row(d_strat, "DAA excess-return series"), dsr_row(d_diff, "DAA-minus-rotation series")],
                              f"DSR > {DSR_PASS} over the {len(family)} configurations under both readings"),
            all_constructions(pbo_rows, f"PBO < 0.5 over the {len(family)}-configuration matrix under both readings")]
    v, why = _decide(crit, n, min_n, "months")
    labs = pv["labels"]
    post = np.array([l >= "2018-01" for l in labs], bool)
    sub = {"post-2018": {"n": int(post.sum()), "diff": (_sr_ann(pv["daa"][post], 12) or 0) - (_sr_ann(pv["rot"][post], 12) or 0)} if post.sum() > 12 else None}
    years = {}
    for y in T479_YEARS:
        m = np.array([l[:4] == y for l in labs], bool)
        if m.any():
            years[y] = {"daa": float(np.prod(1 + pv["daa"][m]) - 1), "rot": float(np.prod(1 + pv["rot"][m]) - 1)}
    return {"n": n, "window": [labs[0], labs[-1]] if labs else None, "sharpe": sh, "dsr_strategy": d_strat, "dsr_diff": d_diff,
            "pbo_strategy": pbo_s, "pbo_diff": pbo_d, "subsample": sub, "years": years,
            "turnover": {"daa": float(pv["to_daa"].mean() * 12) if n else None, "rot": float(pv["to_rot"].mean() * 12) if n else None},
            "cash_share": pv["cash_share"],
            "family": {"|".join(map(str, k)): {"n": len(r["labels"]), "sharpe_daa": _sr_ann(r["daa"], 12), "sharpe_rot": _sr_ann(r["rot"], 12)}
                       for k, r in res.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_macro_daa_canary(archive):
    """T-479."""
    need = [dh(s) for s in T479_ALL] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    series = {}
    for s in T479_ALL:
        d = _daily(archive, dh(s))
        series[s] = (d["days"], d["adj"])
    j = daa_test(series, _bills(archive))
    sh = j["sharpe"]
    sub = j["subsample"]["post-2018"]
    reason = (f"DAA at month-end closes (13612W on adjclose; canary VWO+BND, breadth 2: one bad canary = 50% in the top 3 of "
              f"the 12 risky ETFs + 50% in the best of SHY/IEF/LQD, both bad = 100% cash ETF; cash part on average "
              f"{_pu(j['cash_share'])}) vs the same top-6 rotation without the canary, filled at the next session's close, "
              f"5 bps per side on drift-adjusted turnover (annual turnover DAA {_f(j['turnover']['daa'], 2)}, rotation "
              f"{_f(j['turnover']['rot'], 2)}); hold months {j['window'][0] if j['window'] else 'n/a'}..{j['window'][1] if j['window'] else 'n/a'} "
              f"({j['n']}). Excess Sharpe DAA {_s(sh.get('sharpe_a'))} vs rotation {_s(sh.get('sharpe_b'))}: difference "
              f"{_s(sh.get('diff'))} ({_ci(sh.get('ci'))}, paired studentized CBB, 12-month blocks, {N_BOOT:,} draws x {REPS} seeds); "
              f"DSR over the 8 configurations: DAA series {_dsr_txt(j['dsr_strategy'])}, difference series {_dsr_txt(j['dsr_diff'])}; "
              f"PBO (CSCV, {T479_PBO_PARTS} partitions): DAA {_f((j['pbo_strategy'] or {}).get('pbo'))}, difference "
              f"{_f((j['pbo_diff'] or {}).get('pbo'))}. Post-2018 Sharpe difference {_s(sub['diff'] if sub else None)}; "
              + ", ".join(f"{y}: DAA {_pc(v['daa'], 1)} vs rotation {_pc(v['rot'], 1)}" for y, v in j["years"].items())
              + " — " + j["why"])
    stat = {"n_months": j["n"], "window": j["window"], "sharpe_daa": sh.get("sharpe_a"), "sharpe_rot": sh.get("sharpe_b"),
            "diff": sh.get("diff"), "ci": sh.get("ci"), "ci_mc_se": sh.get("ci_mc_se"), "dsr_strategy": j["dsr_strategy"],
            "dsr_diff": j["dsr_diff"], "pbo_strategy": (j["pbo_strategy"] or {}).get("pbo"), "pbo_diff": (j["pbo_diff"] or {}).get("pbo"),
            "subsample": j["subsample"], "years": j["years"], "turnover": j["turnover"], "cash_share": j["cash_share"],
            "family": j["family"], "criteria": j["criteria"], "rule10": "calendar: month-end decisions named by the rule (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ============================================================================== T-483 leverage for the long run ==

T483_START = "1994-01-01"
T483_MIN_N = 8000
T483_BLOCK = 60
T483_SPREAD = 0.005
T483_EXPENSE = 0.009
T483_COST_SPY = 2e-4            # per unit of SPY notional traded
T483_COST_SSO = 5e-4            # per switch (SSO notional = equity)
T483_LEV, T483_SMA = 2.0, 200
T483_DELAY = 2                  # signal at close t, position from close t+1: earns the return of day t+2
T483_FAMILY = ((1.25, 100), (1.25, 200), (2.0, 100), (2.0, 200), (3.0, 100), (3.0, 200))
T483_T58 = 6
T483_REGIMES = (("2018-10-01", "2018-12-31", "2018-Q4"), ("2020-03-01", "2020-03-31", "2020-03"), ("2022-01-01", "2022-12-31", "2022"))


def sma_signal(adj: np.ndarray, L: int) -> np.ndarray:
    """1.0 where adjclose > its L-day SMA, 0.0 below, NaN before L bars."""
    n = adj.size
    s = np.full(n, np.nan)
    if n >= L:
        c = np.concatenate([[0.0], np.cumsum(adj)])
        sma = (c[L:] - c[:-L]) / L
        s[L - 1:] = (adj[L - 1:] > sma).astype(float)
    return s


def lev_rule(days: Sequence[str], adj: np.ndarray, sig: np.ndarray, bills: Bills, lev: float, delay: int = T483_DELAY,
             inst: Optional[np.ndarray] = None, cost_unit: float = T483_COST_SPY, expense: float = T483_EXPENSE,
             spread: float = T483_SPREAD, cost_per_switch: Optional[float] = None) -> dict:
    """Daily rule returns for return days i = 1..n-1 (close i-1 -> close i): position = sig[i - delay]. Leveraged day:
    lev r - (lev - 1) x financing (bill growth x e^(spread dt/365) - 1) - expense dt/365, or the instrument's own return
    (``inst``); flat day: the bill growth. Switch cost: cost_unit x |change in notional| (or cost_per_switch)."""
    n = len(days)
    C = bill_logcum(bills, days)
    o = np.array([_ord(d) for d in days], float)
    dt = np.diff(o)
    g = np.exp(np.diff(C)) - 1.0
    r = adj[1:] / adj[:-1] - 1.0
    if inst is None:
        lr = lev * r - (lev - 1.0) * ((1.0 + g) * np.exp(spread * dt / 365.0) - 1.0) - expense * dt / 365.0
        notional = lev
    else:
        lr = inst[1:] / inst[:-1] - 1.0
        notional = 1.0
    pos = np.full(n - 1, np.nan)
    for i in range(1, n):
        j = i - delay
        if j >= 0:
            pos[i - 1] = sig[j]
    ok = np.isfinite(pos)
    p = np.where(ok, pos, 0.0)
    prev = np.concatenate([[np.nan], p[:-1]])
    sw = ok & np.isfinite(prev) & (p != prev)
    cost = np.where(sw, cost_per_switch if cost_per_switch is not None else cost_unit * notional, 0.0)
    rule = p * lr + (1 - p) * g - cost
    return {"rule": rule, "spy": r, "pos": p, "ok": ok, "switch": sw, "days": list(days[1:]), "bill": g}


def leverage_test(spy: tuple, bills: Bills, sso: Optional[tuple] = None, start: str = T483_START, min_n: int = T483_MIN_N,
                  family: Optional[Sequence[tuple]] = None, n_boot: Optional[int] = None, reps: Optional[int] = None,
                  seed: int = SEED) -> dict:
    """T-483 core. spy/sso: (days, adjclose)."""
    family = T483_FAMILY if family is None else tuple(family)
    days, adj = list(spy[0]), np.asarray(spy[1], float)
    sigs = {L: sma_signal(adj, L) for L in sorted({L for _, L in family} | {T483_SMA})}

    def run(lev, L, **kw):
        x = lev_rule(days, adj, sigs[L], bills, lev, **kw)
        m = x["ok"] & np.array([d >= start for d in x["days"]])
        d = np.log1p(x["rule"][m]) - np.log1p(x["spy"][m])
        return {**x, "m": m, "d": d}

    res = {cfg: run(*cfg) for cfg in family}
    pk = (T483_LEV, T483_SMA)
    pv = res[pk] if pk in res else run(*pk)
    d = pv["d"]
    n = int(d.size)
    mt = mean_test(d, T483_BLOCK, n_boot, reps, seed) if n >= 8 else {"est": None, "ci": [None, None]}
    fam_sr = [_sr_pp(r["d"]) for r in res.values()]
    dsr = family_dsr(d, fam_sr, len(family) + T483_T58)
    rd = [x for x, k in zip(pv["days"], pv["m"]) if k]
    yrs = (_ord(rd[-1]) - _ord(rd[0]) + 1) / 365.25 if rd else None
    rule_lr, spy_lr = np.log1p(pv["rule"][pv["m"]]), np.log1p(pv["spy"][pv["m"]])
    cagr = {"rule": math.exp(rule_lr.sum() / yrs) - 1 if yrs else None, "spy": math.exp(spy_lr.sum() / yrs) - 1 if yrs else None}
    lit = lev_rule(days, adj, sigs[T483_SMA], bills, T483_LEV, cost_per_switch=T483_COST_SPY)
    lit_d = np.log1p(lit["rule"][pv["m"]]) - np.log1p(lit["spy"][pv["m"]])
    one = lev_rule(days, adj, sigs[T483_SMA], bills, T483_LEV, delay=1)
    one_d = np.log1p(one["rule"][pv["m"]]) - np.log1p(one["spy"][pv["m"]])
    sso_out = None
    if sso is not None:
        sm = dict(zip(sso[0], sso[1]))
        ad = dict(zip(days, adj))
        sgd = dict(zip(days, sigs[T483_SMA]))
        cd = [x for x in days if x in sm and x >= sso[0][0]]
        if len(cd) > 300:
            sg = np.array([sgd[x] for x in cd])
            xs = lev_rule(cd, np.array([ad[x] for x in cd]), sg, bills, 1.0, inst=np.array([sm[x] for x in cd]), cost_per_switch=T483_COST_SSO)
            ms = xs["ok"]
            ds = np.log1p(xs["rule"][ms]) - np.log1p(xs["spy"][ms])
            syn = lev_rule(cd, np.array([ad[x] for x in cd]), sg, bills, T483_LEV)
            dsyn = np.log1p(syn["rule"][ms]) - np.log1p(syn["spy"][ms])
            lev_days = ms & (xs["pos"] > 0)
            te = None
            if lev_days.sum() > 50:
                a_, b_ = syn["rule"][lev_days], xs["rule"][lev_days]
                te = {"corr": float(np.corrcoef(a_, b_)[0, 1]), "gap_ann": float((a_ - b_).mean() * 252)}
            sso_out = {"n": int(ds.size), "from": [x for x, k in zip(xs["days"], ms) if k][0], "mean": float(ds.mean()),
                       "ann": float(ds.mean() * 252), "synthetic_same_days_ann": float(dsyn.mean() * 252), "tracking": te}
    regimes = {}
    for a, b, nm in T483_REGIMES:
        k = np.array([a <= x <= b for x in rd], bool)
        if k.any():
            sw = pv["switch"][pv["m"]][k]
            regimes[nm] = {"diff_log": float(d[k].sum()), "switches": int(sw.sum())}
    crit = [_ci_crit(mt, "gt", 0.0, "mean daily log-return difference (rule - SPY) > 0 with the 60-day block-bootstrap 95% CI "
                                    "excluding 0", fmt=lambda v: _bp(v, 2)),
            dsr_row(dsr, f"DSR of the difference series > {DSR_PASS} over {len(family)} trials + T-58's {T483_T58} SPY trials")]
    if sso_out is None:
        crit.append(("SSO 2006-2026 point estimate same sign (daily-history-SSO not archived)", None, False))
    else:
        same = (sso_out["mean"] > 0) == ((mt.get("est") or 0) > 0)
        crit.append((f"SSO {sso_out['from'][:4]}-2026 mean log difference {_bp(sso_out['mean'], 2)}/day same sign as the synthetic "
                     f"{_bp(mt.get('est'), 2)}/day", same, False))
    v, why = _decide(crit, n, min_n, "days")
    return {"n": n, "window": [rd[0], rd[-1]] if rd else None, "mean": mt, "dsr": dsr, "cagr": cagr, "sso": sso_out,
            "regimes": regimes, "switches_per_year": float(pv["switch"][pv["m"]].sum() / yrs) if yrs else None,
            "share_levered": float(pv["pos"][pv["m"]].mean()) if n else None,
            "mdd": {"rule": _mdd_log(rule_lr), "spy": _mdd_log(spy_lr)},
            "literal_cost_ann": float(lit_d.mean() * 252) if lit_d.size else None, "one_bar_ann": float(one_d.mean() * 252) if one_d.size else None,
            "family": {f"{l}x/SMA{L}": {"ann_diff": float(r["d"].mean() * 252) if r["d"].size else None, "sharpe_d": _sr_ann(r["d"], 252)}
                       for (l, L), r in res.items()},
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_macro_leverage_sma200(archive):
    """T-483."""
    need = [dh("SPY"), DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    sp = _daily(archive, dh("SPY"))
    sso = None
    if _has(archive, dh("SSO")):
        s = _daily(archive, dh("SSO"))
        sso = (s["days"], s["adj"])
    j = leverage_test((sp["days"], sp["adj"]), _bills(archive), sso)
    mt, so = j["mean"], j["sso"]
    reason = (f"Synthetic 2x SPY (2 r - financing of the borrowed 1x at DTB3 continuous + 50 bp - 0.9%/yr expense, calendar-day "
              f"accrual) when SPY adjclose > SMA200 at close t, from close t+1; else DTB3 bills; 2 bps per unit of SPY notional "
              f"per switch ({_f(j['switches_per_year'], 1)} switches/yr, levered {_pu(j['share_levered'])} of days); vs SPY "
              f"buy-and-hold, {j['window'][0] if j['window'] else 'n/a'}..{j['window'][1] if j['window'] else 'n/a'} ({j['n']} days). "
              f"CAGR rule {_pc(j['cagr']['rule'])} vs SPY {_pc(j['cagr']['spy'])}; mean daily log difference {_bp(mt.get('est'), 2)} "
              f"({_ci(mt.get('ci'), 2, 1e4, ' bp')}, studentized circular blocks of {T483_BLOCK} days, {N_BOOT:,} draws x "
              f"{REPS} seeds; annualised {_pc((mt.get('est') or 0) * 252)}); DSR of the difference over {len(T483_FAMILY)} + "
              f"{T483_T58} trials {_dsr_txt(j['dsr'])}; "
              + (f"SSO from {so['from']} ({so['n']} days): {_pc(so['ann'])}/yr vs SPY (synthetic on the same days "
                 f"{_pc(so['synthetic_same_days_ann'])}/yr" + (f", levered-day correlation {so['tracking']['corr']:.3f}, gap "
                                                               f"{_pc(so['tracking']['gap_ann'])}/yr" if so.get("tracking") else "") + "); "
                 if so else "SSO not archived; ")
              + f"max drawdown rule {_pc(j['mdd']['rule'], 1)} vs SPY {_pc(j['mdd']['spy'], 1)}; whipsaws "
              + ", ".join(f"{k}: {_pc(v['diff_log'], 1)} log, {v['switches']} switches" for k, v in j["regimes"].items())
              + f"; sensitivities (reported): literal 2 bps per switch {_pc(j['literal_cost_ann'])}/yr, signal applied to the next "
              f"day's return (no extra bar) {_pc(j['one_bar_ann'])}/yr; family "
              + ", ".join(f"{k} {_pc(v['ann_diff'], 1)}/yr" for k, v in j["family"].items()) + " — " + j["why"])
    stat = {"n_days": j["n"], "window": j["window"], "mean_log_diff": mt.get("est"), "ci": mt.get("ci"), "ci_mc_se": mt.get("ci_mc_se"),
            "cagr": j["cagr"], "dsr": j["dsr"], "sso": so, "regimes": j["regimes"], "switches_per_year": j["switches_per_year"],
            "share_levered": j["share_levered"], "mdd": j["mdd"], "literal_cost_ann": j["literal_cost_ann"],
            "one_bar_ann": j["one_bar_ann"], "family": j["family"], "criteria": j["criteria"],
            "rule10": "daily rule: no grid phase"}
    return _out(stat, j["n"], j["verdict"], reason)


# =============================================================================== T-325 leveraged ETF pair decay ==

T325_PAIRS = (("TQQQ", "SQQQ"), ("SSO", "SDS"), ("UPRO", "SPXU"), ("UVXY", "SVXY"))
T325_LEV = {"TQQQ": 3.0, "SQQQ": -3.0, "SSO": 2.0, "SDS": -2.0, "UPRO": 3.0, "SPXU": -3.0}
T325_VIX_BREAK = "2018-02-28"
T325_VIX_LEV = {"UVXY": (2.0, 1.5), "SVXY": (-1.0, -0.5)}
T325_FEE = 0.03
T325_FEE_GRID = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08)
T325_START, T325_END = "2010-03", "2026-09"
T325_MIN_N = 150
T325_BLOCK = 6
T325_DRIFT = 0.20
T325_STOP = 2.0
T325_MODES = ("monthly", "drift")
T325_N_TRIALS = 8
T325_LATE_BLOCK = 5


def _lev(sym: str, day: str) -> float:
    if sym in T325_VIX_LEV:
        a, b = T325_VIX_LEV[sym]
        return a if day < T325_VIX_BREAK else b
    return T325_LEV.get(sym, 1.0)


def _req(sym: str, day: str) -> float:
    """FINRA-style short maintenance for a leveraged ETF: 30% x leverage, at least 30%, at most 100%."""
    return min(1.0, 0.3 * max(1.0, abs(_lev(sym, day))))


def sim_pair(days: Sequence[str], a: np.ndarray, b: np.ndarray, C: np.ndarray, sym_a: str, sym_b: str, mode: str = "monthly",
             stop: float = T325_STOP, drift: float = T325_DRIFT) -> dict:
    """Daily short-pair simulation; monthly records of price P&L + interest (``pnl``), the borrow base sum(value x dt/365)
    (``fee_base``) and the gross at the month start (``g0``). Net return at fee f = (pnl - f fee_base) / g0."""
    n = len(days)
    last = {}
    for i, d in enumerate(days):
        last[d[:7]] = i
    me = sorted(last.values())
    if len(me) < 2:
        return {"labels": [], "pnl": np.zeros(0), "fee_base": np.zeros(0), "g0": np.zeros(0), "stops": 0, "resets": 0, "stopped": []}
    me_set = set(me)
    o = np.array([_ord(d) for d in days], float)
    i0 = me[0]

    def reset(i):
        na, nb = 0.5 / a[i], 0.5 / b[i]
        return na, nb, _req(sym_a, days[i]) * 0.5 + _req(sym_b, days[i]) * 0.5

    na, nb, M0 = reset(i0)
    active, g0 = True, 1.0
    pnl = fb = 0.0
    labels, P, F, G, stopped = [], [], [], [], []
    stops = resets = 0
    hit = False
    for i in range(i0 + 1, n):
        if active:
            va, vb = na * a[i - 1], nb * b[i - 1]
            gross = va + vb
            pnl -= na * (a[i] - a[i - 1]) + nb * (b[i] - b[i - 1])
            pnl += gross * (math.exp(C[i] - C[i - 1]) - 1.0)
            fb += gross * (o[i] - o[i - 1]) / 365.0
            va, vb = na * a[i], nb * b[i]
            if _req(sym_a, days[i]) * va + _req(sym_b, days[i]) * vb >= stop * M0:
                active, hit = False, True
                stops += 1
            elif mode == "drift" and max(va, vb) > (1.0 + drift) * min(va, vb):
                na, nb, M0 = reset(i)
                resets += 1
        if i in me_set:
            labels.append(days[i][:7])
            P.append(pnl)
            F.append(fb)
            G.append(g0)
            stopped.append(hit)
            pnl = fb = 0.0
            hit = False
            if mode == "monthly" or not active:
                na, nb, M0 = reset(i)
                active, g0 = True, 1.0
            else:
                g0 = na * a[i] + nb * b[i]
    return {"labels": labels, "pnl": np.array(P), "fee_base": np.array(F), "g0": np.array(G), "stops": stops, "resets": resets,
            "stopped": stopped}


def _pair_net(sim: dict, fee: float, start: str, end: str) -> tuple:
    m = np.array([start <= l <= end for l in sim["labels"]], bool)
    if not m.any():
        return [], np.zeros(0)
    r = (sim["pnl"][m] - fee * sim["fee_base"][m]) / sim["g0"][m]
    return [l for l, k in zip(sim["labels"], m) if k], r


def late_day(bars: dict) -> dict:
    """Late-day LETF flow reversal (reported only): at 15:30 ET (the start of Yahoo's last :30-aligned bar) take the
    opposite of the day's direction so far (15:30 price vs the previous session's last close), cover at the next
    session's open; gross return per session."""
    sessions = sorted({d for d, _ in bars})
    out = []
    for i in range(1, len(sessions) - 1):
        d0, d, d1 = sessions[i - 1], sessions[i], sessions[i + 1]
        pc, p, nx = bars.get((d0, "15:30")), bars.get((d, "14:30")), bars.get((d1, "09:30"))
        if not (pc and p and nx and bars.get((d, "15:30"))):
            continue
        entry = p[3]
        dirn = np.sign(entry / pc[3] - 1.0)
        if dirn == 0:
            continue
        out.append((d, -dirn * (nx[0] / entry - 1.0)))
    return {"sessions": [x[0] for x in out], "r": np.array([x[1] for x in out], float)}


def letf_test(pairs: dict, bills: Bills, qqq: Optional[tuple] = None, hourly: Optional[dict] = None, start: str = T325_START,
              end: str = T325_END, min_n: int = T325_MIN_N, n_boot: Optional[int] = None, reps: Optional[int] = None,
              seed: int = SEED) -> dict:
    """T-325 core. pairs: {(A, B): (days, adj A, adj B)} on each pair's common calendar; the first is the primary."""
    keys = list(pairs)
    sims = {}
    for k in keys:
        d, a, b = pairs[k]
        C = bill_logcum(bills, d)
        for md in T325_MODES:
            sims[(k, md)] = sim_pair(d, np.asarray(a, float), np.asarray(b, float), C, k[0], k[1], md)
    pk = (keys[0], "monthly")
    labs, r = _pair_net(sims[pk], T325_FEE, start, end)
    n = len(labs)
    mt = mean_test(r, T325_BLOCK, n_boot, reps, seed, one_sided=True) if n >= 8 else {"est": None, "ci": [None, None], "ci1": [None, None]}
    fam = {}
    for key, s in sims.items():
        lb, rr = _pair_net(s, T325_FEE, "0000", end)
        fam[key] = {"n": len(lb), "first": lb[0] if lb else None, "mean": float(rr.mean()) if rr.size else None, "sr": _sr_pp(rr),
                    "stops": s["stops"], "resets": s["resets"]}
    dsr = family_dsr(r, [v["sr"] for v in fam.values()], T325_N_TRIALS)
    # the same DSR at the zero-skill variance 1/(T-1) alone (reported: shows whether the outcome rests on the dispersion
    # of the trial Sharpes)
    dsr_floor_only = float(deflated_sharpe_ratio(r, n_trials=T325_N_TRIALS, var_trials_sr=1.0 / max(1, n - 1))) if n > 3 else None
    s0 = sims[pk]
    m = np.array([start <= l <= end for l in s0["labels"]], bool)
    gross_mean = float((s0["pnl"][m] / s0["g0"][m]).mean()) if m.any() else None
    fee_unit = float((s0["fee_base"][m] / s0["g0"][m]).mean()) if m.any() else None
    breakeven = gross_mean / fee_unit if fee_unit else None
    grid = {f"{f * 100:.0f}%": float(_pair_net(s0, f, start, end)[1].mean()) if n else None for f in T325_FEE_GRID}
    regimes = {}
    for nm, (a_, b_) in (("2010-2019", ("2010-01", "2019-12")), ("2020-2026", ("2020-01", "2026-12")), ("2022", ("2022-01", "2022-12"))):
        k = np.array([a_ <= l <= b_ for l in labs], bool)
        if k.any():
            regimes[nm] = {"n": int(k.sum()), "mean": float(r[k].mean())}
    rv_reg = None
    if qqq is not None and n > 24:
        qd, qa = qqq
        lr = np.diff(np.log(np.asarray(qa, float)))
        rv = defaultdict(float)
        for d_, x in zip(qd[1:], lr):
            rv[d_[:7]] += x * x
        k = [i for i, l in enumerate(labs) if l in rv]
        if len(k) > 24:
            rv_reg = ols_hac(r[k], np.array([rv[labs[i]] for i in k]), 3, "bartlett")
    vix = None
    vk = next((key for key in keys if key[0] == "UVXY"), None)
    if vk is not None:
        lb, rr = _pair_net(sims[(vk, "monthly")], T325_FEE, "0000", end)
        pre = np.array([l < T325_VIX_BREAK[:7] for l in lb], bool)
        vix = {"pre_n": int(pre.sum()), "pre_mean": float(rr[pre].mean()) if pre.any() else None,
               "post_n": int((~pre).sum()), "post_mean": float(rr[~pre].mean()) if (~pre).any() else None}
    late = {}
    for sym, bars in (hourly or {}).items():
        ld = late_day(bars)
        if ld["r"].size >= 20:
            t = mean_test(ld["r"], T325_LATE_BLOCK, n_boot, reps, seed)
            late[sym] = {"n": int(ld["r"].size), "first": ld["sessions"][0], "last": ld["sessions"][-1], "mean": t.get("est"), "ci": t.get("ci")}
    crit = [_lb_crit(mt, f"one-sided 95% lower bound of the mean monthly net return on gross short notional > 0 at "
                         f"{T325_FEE * 100:.0f}%/yr borrow per leg (studentized CBB, {T325_BLOCK}-month blocks)",
                     fmt=lambda v: _pc(v, 3)),
            dsr_row(dsr, f"DSR > {DSR_PASS} over the {T325_N_TRIALS} trials (4 pairs x monthly / 20%-drift reset)")]
    v, why = _decide(crit, n, min_n, "months")
    return {"n": n, "window": [labs[0], labs[-1]] if labs else None, "mean": mt, "dsr": dsr, "dsr_floor_only": dsr_floor_only,
            "sharpe_ann": _sr_ann(r, 12), "family": fam, "gross_mean": gross_mean, "fee_unit": fee_unit, "breakeven": breakeven, "grid": grid, "regimes": regimes,
            "mdd": _mdd_simple(r), "rv_reg": rv_reg, "vix_break": vix, "late_day": late,
            "stops": s0["stops"], "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_macro_letf_pair_decay(archive):
    """T-325."""
    need = [dh(s) for p in T325_PAIRS for s in p] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    pairs = {}
    for a, b in T325_PAIRS:
        da, db = _daily(archive, dh(a)), _daily(archive, dh(b))
        ma, mb = dict(zip(da["days"], da["adj"])), dict(zip(db["days"], db["adj"]))
        cd = sorted(set(ma) & set(mb))
        pairs[(a, b)] = (cd, np.array([ma[d] for d in cd]), np.array([mb[d] for d in cd]))
    qqq = None
    if _has(archive, dh("QQQ")):
        q = _daily(archive, dh("QQQ"))
        qqq = (q["days"], q["adj"])
    hourly = {s: _hourly(archive, hr(s)) for s in ("TQQQ", "SQQQ") if _has(archive, hr(s))}
    j = letf_test(pairs, _bills(archive), qqq, hourly)
    mt = j["mean"]
    fam = j["family"]
    rv = j["rv_reg"]
    vx = j["vix_break"]
    reason = (f"Short 0.5 TQQQ + 0.5 SQQQ of gross notional at each month-end close (adjclose, daily simulation), "
              f"{T325_FEE * 100:.0f}%/yr borrow on each leg's value, DTB3 (continuous) on the marked-to-market proceeds, margin-call "
              f"stop at 2x the reset requirement ({j['stops']} stops); months {j['window'][0] if j['window'] else 'n/a'}.."
              f"{j['window'][1] if j['window'] else 'n/a'} ({j['n']}). Mean monthly net return {_pc(mt.get('est'), 3)} "
              f"(one-sided 95% lower bound {_pc((mt.get('ci1') or [None])[0], 3)}; two-sided {_ci(mt.get('ci'), 3, 100, '%')}; "
              f"studentized CBB, {T325_BLOCK}-month blocks, {N_BOOT:,} draws x {REPS} seeds); "
              f"annualised Sharpe {_s(j['sharpe_ann'], 2)}; DSR over the 8 trials {_dsr_txt(j['dsr'])}, "
              f"{_f(j['dsr_floor_only'])} at the zero-skill variance 1/(T-1) alone (trial means/month at 3%: "
              + ", ".join(f"{k[0][0]}/{k[0][1]} {k[1]} {_pc(v['mean'], 2)} from {v['first']}" for k, v in fam.items())
              + f"). Borrow break-even {_pc(j['breakeven'], 2)}/yr per leg (gross of borrow {_pc(j['gross_mean'], 3)}/month); "
              f"fee grid 0-8%: " + ", ".join(f"{k} {_pc(v, 2)}" for k, v in j["grid"].items())
              + f"; max drawdown on gross notional {_pc(j['mdd'], 1)}; regimes "
              + ", ".join(f"{k} {_pc(v['mean'], 2)} ({v['n']} m)" for k, v in j["regimes"].items())
              + (f"; monthly P&L on QQQ realized variance: slope {_s(rv['b'], 3)}, NW t {_s(rv['t'], 2)}" if rv else "")
              + (f"; UVXY/SVXY before the 2018-02-28 leverage change {_pc(vx['pre_mean'], 2)} ({vx['pre_n']} m), after "
                 f"{_pc(vx['post_mean'], 2)} ({vx['post_n']} m)" if vx else "")
              + "; late-day hourly variant (reported only; Yahoo 60-minute bars reach only about 730 sessions, so it covers "
              + (", ".join(f"{s} {v['first']}..{v['last']}: {v['n']} sessions, {_bp(v['mean'], 2)} gross per session "
                           f"({_ci(v['ci'], 1, 1e4, ' bp')})" for s, v in j["late_day"].items()) or "nothing archived")
              + ") — " + j["why"])
    stat = {"n_months": j["n"], "window": j["window"], "mean": mt.get("est"), "ci": mt.get("ci"), "ci_mc_se": mt.get("ci_mc_se"),
            "lower_one_sided95": (mt.get("ci1") or [None])[0], "ci1": mt.get("ci1"), "ci1_mc_se": mt.get("ci1_mc_se"),
            "dsr": j["dsr"], "dsr_floor_only": j["dsr_floor_only"], "sharpe_ann": j["sharpe_ann"],
            "family": {f"{k[0][0]}/{k[0][1]}|{k[1]}": v for k, v in fam.items()}, "gross_mean": j["gross_mean"],
            "breakeven_fee": j["breakeven"], "fee_grid": j["grid"], "regimes": j["regimes"], "mdd": j["mdd"],
            "rv_regression": None if not rv else {"slope": rv["b"], "nw_t": rv["t"], "n": rv["n"]}, "vix_break": vx,
            "late_day": j["late_day"], "stops": j["stops"], "criteria": j["criteria"],
            "rule10": "calendar: month-end resets named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================== T-467 Canadian interlisted parity fade ==

T467_THR, T467_THR_ALT = 2.0, 3.0
T467_WIN = 20
T467_MAX_HOLD = 2
T467_COSTS = {"per-trade": 2 * 3e-4 + 2e-4, "per-side": 4 * 3e-4 + 2 * 2e-4}
T467_TIMINGS = ("live", "lagged")
T467_BLOCK = 5
T467_MIN_N = 200
T467_N_TRIALS = 4
T467_EQ_BAR, T467_FX_BAR, T467_FX_LAG_BAR = "15:30", "15:00", "14:00"


def parity_series(us: dict, ca: dict, fx: dict, fx_bar: str = T467_FX_BAR) -> dict:
    """d = ln P_US - ln(P_TSX / USDCAD) at the 16:00 ET closes, on sessions where both last equity bars and a non-flat FX
    bar exist."""
    days = sorted({d for d, hm in us if hm == T467_EQ_BAR} & {d for d, hm in ca if hm == T467_EQ_BAR})
    out_d, out_v, flat, nofx = [], [], 0, 0
    for d in days:
        f = fx.get((d, fx_bar))
        if f is None:
            nofx += 1
            continue
        if not f[1] > f[2]:
            flat += 1
            continue
        out_d.append(d)
        out_v.append(math.log(us[(d, T467_EQ_BAR)][3]) - math.log(ca[(d, T467_EQ_BAR)][3] / f[3]))
    return {"days": out_d, "d": np.array(out_v, float), "flat_fx": flat, "no_fx": nofx}


def zscores(d: np.ndarray, win: int = T467_WIN) -> np.ndarray:
    z = np.full(d.size, np.nan)
    for t in range(win - 1, d.size):
        w = d[t - win + 1: t + 1]
        sd = float(w.std(ddof=1))
        if sd > 0:
            z[t] = (d[t] - float(w.mean())) / sd
    return z


def fade_trades(d: np.ndarray, z: np.ndarray, thr: float, timing: str, max_hold: int = T467_MAX_HOLD) -> list:
    """Trades (entry index, exit index, sigma, gross): sigma = -sign(z) at the signal; 'live' fills at the signal close,
    'lagged' at the next session's close; exit when z reaches 0 or crosses it, or after ``max_hold`` sessions, filled the
    same way. One position at a time; incomplete trades at the end are dropped."""
    n = d.size
    lag = 0 if timing == "live" else 1
    out = []
    t = 0
    last_exit = -1
    while t < n:
        if not np.isfinite(z[t]) or abs(z[t]) <= thr:
            t += 1
            continue
        e = t + lag
        if e >= n or e <= last_exit:
            t += 1
            continue
        sg = -1.0 if z[t] > 0 else 1.0
        x = None
        for u in range(e if lag else e + 1, n):
            if (np.isfinite(z[u]) and sg * z[u] >= 0) or (u + lag) - e >= max_hold:
                x = u + lag
                break
        if x is None or x >= n:
            break
        out.append((e, x, sg, sg * (d[x] - d[e])))
        last_exit = x
        t = x - lag + 1 if lag else x + 1
    return out


def _pooled(parity: dict, thr: float, timing: str, cost: float, n_pairs: int) -> dict:
    """Pooled trades over the pairs: per-trade net returns, per-entry-date sums/counts on the union calendar, and the
    daily book (sum of the pairs' marked P&L / number of pairs; cost half at entry, half at exit)."""
    cal = sorted({d for p in parity.values() for d in p["days"]})
    ci = {d: i for i, d in enumerate(cal)}
    S, N, book = np.zeros(len(cal)), np.zeros(len(cal)), np.zeros(len(cal))
    trades = []
    for name, p in parity.items():
        days, d = p["days"], p["d"]
        for e, x, sg, g in fade_trades(d, p["z"], thr, timing):
            net = g - cost
            trades.append((days[e], name, sg, g, net, x - e))
            S[ci[days[e]]] += net
            N[ci[days[e]]] += 1
            book[ci[days[e]]] -= cost / 2.0
            book[ci[days[x]]] -= cost / 2.0
            for k in range(e + 1, x + 1):
                book[ci[days[k]]] += sg * (d[k] - d[k - 1])
    trades.sort()
    return {"cal": cal, "S": S, "N": N, "book": book / max(1, n_pairs), "trades": trades,
            "net": np.array([t[4] for t in trades], float), "gross": np.array([t[3] for t in trades], float)}


def parity_test(legs: dict, fx: dict, min_n: int = T467_MIN_N, n_boot: Optional[int] = None, reps: Optional[int] = None,
                seed: int = SEED) -> dict:
    """T-467 core. legs: {US symbol: (US bars, TSX bars)}; fx: CAD=X bars."""
    par, plc = {}, {}
    for us, (ub, cb) in legs.items():
        p = parity_series(ub, cb, fx)
        p["z"] = zscores(p["d"])
        par[us] = p
        q = parity_series(ub, cb, fx, T467_FX_LAG_BAR)
        q["z"] = zscores(q["d"])
        plc[us] = q
    npairs = len(legs)
    runs = {}
    for tm in T467_TIMINGS:
        for ck, cv in T467_COSTS.items():
            for thr in (T467_THR, T467_THR_ALT):
                runs[(tm, ck, thr)] = _pooled(par, thr, tm, cv, npairs)
    rows_m, rows_d, tests = [], [], {}
    for tm in T467_TIMINGS:
        for ck in T467_COSTS:
            r = runs[(tm, ck, T467_THR)]
            ra = runs[(tm, ck, T467_THR_ALT)]
            t = (ratio_test(r["S"], r["N"], T467_BLOCK, n_boot, reps, seed, one_sided=True) if r["N"].sum() >= 8
                 else {"est": None, "ci": [None, None], "ci1": [None, None]})
            tests[(tm, ck)] = t
            rows_m.append(_lb_crit(t, f"{tm}/{ck} {_bp(t.get('est'), 2)} per trade over {int(r['N'].sum())} trades",
                                   fmt=lambda v: _bp(v, 2)))
            dt_ = family_dsr(r["net"], [_sr_pp(r["net"]), _sr_pp(ra["net"])], T467_N_TRIALS)
            dd_ = family_dsr(r["book"], [_sr_pp(r["book"]), _sr_pp(ra["book"])], T467_N_TRIALS)
            rows_d.append(dsr_row(dt_, f"{tm}/{ck} per-trade"))
            rows_d.append(dsr_row(dd_, f"{tm}/{ck} daily book"))
    n = min(int(runs[(tm, "per-trade", T467_THR)]["N"].sum()) for tm in T467_TIMINGS)
    crit = [all_constructions(rows_m, "one-sided 95% lower bound of the pooled mean net return per trade > 0 (studentized block bootstrap "
                                      "over dates, trades clustered by entry date) under both fill readings (rule 12) and both "
                                      "cost readings"),
            all_constructions(rows_d, f"DSR > {DSR_PASS} over the {T467_N_TRIALS} declared variants (per-trade and daily-book "
                                      f"series, every fill and cost reading)")]
    v, why = _decide(crit, n, min_n, "trades")
    pl = _pooled(plc, T467_THR, "live", T467_COSTS["per-trade"], npairs)
    pr = runs[("live", "per-trade", T467_THR)]
    per_pair = defaultdict(lambda: [0, 0.0])
    for tr in pr["trades"]:
        per_pair[tr[1]][0] += 1
        per_pair[tr[1]][1] += tr[3]
    allz = np.concatenate([p["d"] for p in par.values()]) if par else np.zeros(0)
    dd = np.concatenate([np.diff(p["d"]) for p in par.values() if p["d"].size > 1]) if par else np.zeros(0)
    first = min((p["days"][0] for p in par.values() if p["days"]), default=None)
    last = max((p["days"][-1] for p in par.values() if p["days"]), default=None)
    return {"n": n, "window": [first, last], "tests": tests, "runs_summary": {
                f"{k[0]}|{k[1]}|{k[2]:g}": {"trades": int(r["N"].sum()), "mean_net": float(r["net"].mean()) if r["net"].size else None,
                                            "mean_gross": float(r["gross"].mean()) if r["gross"].size else None,
                                            "sr_trade": _sr_pp(r["net"]), "sr_book_ann": _sr_ann(r["book"], 252)} for k, r in runs.items()},
            "placebo": {"trades": int(pl["N"].sum()), "mean_net": float(pl["net"].mean()) if pl["net"].size else None,
                        "mean_gross": float(pl["gross"].mean()) if pl["gross"].size else None},
            "per_pair": {k: {"trades": v_[0], "mean_gross": v_[1] / v_[0] if v_[0] else None} for k, v_ in per_pair.items()},
            "sessions": {k: len(p["days"]) for k, p in par.items()}, "flat_fx": sum(p["flat_fx"] for p in par.values()),
            "d_sd": float(allz.std()) if allz.size else None, "dd_sd": float(dd.std()) if dd.size else None,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_macro_interlisted_parity(archive):
    """T-467."""
    need = [hr(s) for s in CANADA] + [hr(TSX[s]) for s in CANADA] + [hr(CAD_SYM)]
    miss = _missing(archive, need)
    if miss:
        return miss
    legs = {s: (_hourly(archive, hr(s)), _hourly(archive, hr(TSX[s]))) for s in CANADA}
    fx = _hourly(archive, hr(CAD_SYM))
    j = parity_test(legs, fx)
    ts = j["tests"]
    rs = j["runs_summary"]
    fx_first = min((d for d, _ in fx), default=None)
    reason = (f"10 pairs (" + ", ".join(f"{s}/{TSX[s]}" for s in CANADA) + f"); d = ln P_US - ln(P_TSX / USDCAD) at the 16:00 ET "
              f"closes (15:30 equity bars, 15:00 CAD=X bar; {j['flat_fx']} flat-FX sessions dropped); sessions "
              f"{j['window'][0]}..{j['window'][1]} (CAD=X 60-minute bars start {fx_first}: the claim's 2023-11 start is not "
              f"reachable from Yahoo; per-pair sessions {min(j['sessions'].values()) if j['sessions'] else 0}-"
              f"{max(j['sessions'].values()) if j['sessions'] else 0}); d sd {_bpu(j['d_sd'])}, daily change sd {_bpu(j['dd_sd'])}. "
              f"|z| > 2 on 20-session z, exit at z = 0 or after 2 sessions. Pooled mean net per trade: "
              + "; ".join(f"{k[0]}/{k[1]} {_bp(v.get('est'), 2)} (one-sided 95% lower bound {_bp((v.get('ci1') or [None])[0], 3)}, "
                          f"two-sided {_ci(v.get('ci'), 1, 1e4, ' bp')}, "
                          f"{rs[f'{k[0]}|{k[1]}|2']['trades']} trades, gross {_bp(rs[f'{k[0]}|{k[1]}|2']['mean_gross'], 2)})"
                          for k, v in ts.items())
              + f"; |z| > 3 variant (live/per-trade) {_bp(rs['live|per-trade|3']['mean_net'], 2)} over {rs['live|per-trade|3']['trades']} trades; "
              f"FX 1-bar-lag placebo {_bp(j['placebo']['mean_net'], 2)} net / {_bp(j['placebo']['mean_gross'], 2)} gross over "
              f"{j['placebo']['trades']} trades; DSR over 4 variants (gold miners and TSM/2330.TW not archived: count only), "
              f"daily-book Sharpe (live/per-trade) {_s(rs['live|per-trade|2']['sr_book_ann'], 2)} — " + j["why"])
    stat = {"n_trades": j["n"], "window": j["window"], "fx_first": fx_first,
            "tests": {f"{k[0]}|{k[1]}": {"mean": v.get("est"), "ci": v.get("ci"), "ci_mc_se": v.get("ci_mc_se"),
                                         "lower_one_sided95": (v.get("ci1") or [None])[0], "ci1": v.get("ci1"),
                                         "ci1_mc_se": v.get("ci1_mc_se")} for k, v in ts.items()},
            "runs": rs, "placebo": j["placebo"], "per_pair": j["per_pair"], "sessions": j["sessions"], "flat_fx": j["flat_fx"],
            "d_sd": j["d_sd"], "dd_sd": j["dd_sd"], "criteria": j["criteria"], "rule10": "signal-driven entries and exits: no grid phase"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_macro_fund_flow_dumb_money": b6c_macro_fund_flow_dumb_money,
    "b6c_macro_sentiment_size_premium": b6c_macro_sentiment_size_premium,
    "b6c_macro_daa_canary": b6c_macro_daa_canary,
    "b6c_macro_leverage_sma200": b6c_macro_leverage_sma200,
    "b6c_macro_letf_pair_decay": b6c_macro_letf_pair_decay,
    "b6c_macro_interlisted_parity": b6c_macro_interlisted_parity,
}

THEORY_MAP = {
    "T-398": "b6c_macro_fund_flow_dumb_money",
    "T-458": "b6c_macro_sentiment_size_premium",
    "T-479": "b6c_macro_daa_canary",
    "T-483": "b6c_macro_leverage_sma200",
    "T-325": "b6c_macro_letf_pair_decay",
    "T-467": "b6c_macro_interlisted_parity",
}
