"""
Batch 6c, group ``rates``: seven carry, curve and bill claims on Treasury, credit, country-ETF and OECD yield data.
=================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-373  TLT held only when 20-year carry + roll-down (DGS20, DGS10, DTB3) is positive, else cash, hold months
           2002-08..2026-09 (min_n 280 months): Sharpe(timed) > Sharpe(buy-and-hold) over the claim's window (the claim's
           "earns a higher Sharpe"), test-window (2014-01..2026-09) Sharpe(timed) - Sharpe(buy-and-hold) on monthly excess
           returns > 0.15 with paired block-bootstrap p < 0.05, and DSR > 0.95 at 4 trials.
  * T-377  SGOV monthly total return minus the DTB3 investment-yield accrual, 2020-07..2026-09 (min_n 70 months):
           |annualised mean| < 10 bp, its HAC 95% CI inside +/-15 bp, annualised SD < 20 bp.
  * T-381  equal-risk composite of the FX, global-bond, equity-country and credit carry sleeves with trailing 36-month
           volatility weights, 2013-01..2026-09 (min_n 150 months): Sharpe > 0.6, bootstrap 95% lower bound > 0.2,
           DSR > 0.95 at 3 + every sleeve trial.
  * T-430  LQD minus duration-matched IEF held when BAA10Y is above its trailing 60-month median, else SGOV/BIL, hold
           months 2003-01..2026-09 (min_n 250): positive mean excess and Sharpe > 0.3 over the claim's window, Sharpe >
           0.3 with bootstrap lower bound > 0 in 2013-2026, DSR > 0.95 at 4 trials.
  * T-433  long top-3 / short bottom-3 10-year-minus-3-month carry among 10 developed bond markets on the yield-based
           FX-hedged excess return, 2010-01..2026-09 (min_n 150): Sharpe > 0.3, bootstrap lower bound > 0, the US leg's
           synthetic return correlated > 0.9 with IEF's actual excess return, DSR > 0.95 at 3 trials.
  * T-432  long top-4 / short bottom-4 country ETFs on trailing dividend yield minus the lagged local 3-month rate,
           2011-01..2026-09 (min_n 150): Sharpe > 0.3, bootstrap lower bound > 0, DSR > 0.95 at 4 trials.
  * T-474  duration-neutral SHY/IEI/IEF butterfly on |z| > 2 of the FRED 2s5s10s fly, entries 2008-01..2026-09 (min_n
           30 trades): 95% lower bound of the mean net return per trade > 0 (and the trial's 60-day block-shift null),
           at least 30 trades, DSR > 0.95 at 4 variants.

Conventions
  * Data. ``daily-history-<SYM>`` bundles through ``archive.load``; a row is used only when its ``available_at`` is not
    after the bundle's capture time. Prices are Yahoo ``adjclose`` (split and dividend adjusted: total return, so each
    ETF's expense ratio is already in it); opens are put on the same basis (open x adjclose / close). Dividends are
    ``daily-events-<SYM>`` (ex-date, per share, split adjusted); SPY has no events bundle, so its cash dividends are read
    from its adjclose/close ratio steps (``batch6b_bw.spy_dividends``). FRED daily H.15 series (DGS*, DTB3, BAA10Y) are
    not revised; a print dated d is used from the session after d (FRED posts a day late) unless a claim states its own
    timing. OECD 10-year yields (IRLTLT01, revised monthly averages) are read point in time from ``alfred-<SID>``: the
    value of observation month m known at day D is the vintage in force at D; before ALFRED's first vintage (2013-06-03)
    the first-vintage value counts from its ``lag_rule_at`` (period end + 45 days), the fetcher's stated look-ahead
    approximation. Outcomes (realised synthetic returns) may use the latest vintage (``fred-<SID>``, else the latest
    ALFRED vintage available at capture). OECD 3-month rates are ``fx-rates-3m`` (IR3TIB01 monthly averages; no vintages
    archived, so the claims' one-month lag is the only availability rule; EUR and GBP end 2026-01 and JPY 2026-07: later
    months forward-fill the last print for at most 12 months, flagged in every reason).
  * Bills and Sharpe (rule 7). DTB3 is a 91-day discount yield. Excess returns subtract the bill growth over the same
    calendar days at the continuous rate -ln(1 - d 91/360)/(91/365), the print dated strictly before each day
    (batch6b_bw.Bills). T-377 names its own construction (the investment yield i = 365 d / (360 - 91 d), accrued daily
    actual/365) and is judged under it AND the rule-7 continuous rate (rule 11 spirit: both readings must pass); the raw
    discount reading is reported. T-373's carry compares the bill with DGS20, a bond-equivalent par yield, so the
    rule-7 reading converts the bill to its bond-equivalent yield; the claim writes DTB3 itself, so the raw-discount
    reading is judged too and every T-373 criterion needs both (rule 11 spirit). Sharpe ratios are on
    monthly excess returns x sqrt(12) (T-474's sleeve: daily x sqrt(252)). Zero-investment books (T-432, T-433, T-474,
    the duration-hedged T-430 position) are excess returns by construction.
  * Calendars (rule 10(a)). Every claim names month-end decisions or a signal rule: T-373 decides on the last session's
    close and fills at the next session's open (its procedure: "trade next open"); T-430 reads the month-end BAA10Y,
    published a day later, and fills at the next session's close; T-432 forms on month-end closes and fills at the next
    close; holds run fill to fill and are labelled by the fill month. T-377 is month-end close to month-end close.
    T-433's synthetic return of month t is the claim's (y10(t-1) - r3m(t-1))/12 - 8 (y10(t) - y10(t-1)) on monthly
    averages, so its yield change is spread over months t-1 and t: rule 4 puts the decision at the end of month t-2,
    before that window opens, using the OECD prints released by then (the as-worded one-month lag, which decides after
    the window has opened, is reported). T-474's entries and exits are signal-driven (no grid). T-381 stacks the sleeves'
    calendar months.
  * Point in time (rules 4, 12). One information set per decision: T-373's three yields are the month-end prints (known
    20:00 UTC, before the next open); T-430's BAA10Y print dated on the month-end day is known the next day and trades
    at that session's close; T-432's dividend yield, rate and 60-day volatility use data through the month-end close;
    T-474's z uses yields dated before the entry session and trades at its close; T-381's volatility weights use only
    the 36 sleeve months before each month, and for the bond sleeve (whose T-433 x(t) opens at the start of t-1, as
    above) the 36 months ending t-2, with its drawdown halving also decided at the end of t-2.
  * Costs (rule 9) as each claim states: T-373 2 bps per switch (TLT <-> cash; 1 bp per side of each unit traded in the
    cross-maturity variant); T-430 5 bps per switch; T-432 10 bps per side on drift-adjusted turnover + 50 bps/yr borrow
    on the short notional; T-433 5 bps per unit of notional traded; T-474 3 bps per leg at entry and at exit + 30 bps/yr
    borrow on the short legs; T-381 the sleeves' own costs. The first month's position of every strategy is entered free.
  * Intervals (rule 6). Studentized circular block bootstrap (Bartlett-HAC s.e., bandwidth = block; batch6b_bw._stud)
    with 12-month blocks, 5,000 resamples per seed, interval ends and p-values averaged over 5 seeds with their Monte
    Carlo s.e. (25 seeds when 5 cannot resolve a bound). A single Sharpe is studentized through its delta-method
    influence function; T-373's difference is paired (batch6b_bw.sharpe_diff_test; the Ledoit-Wolf test is reported).
    The timed and buy-and-hold series differ only in cash and switch months (2 of 137 in 2002-2013), so every resample
    that draws none of them has zero s.e. and _stud drops it, which inflates the studentized upper end; each T-373
    difference therefore reports how many months differ, and when that is under two blocks' worth or more than 1% of the
    resamples have zero s.e., the percentile CBB on the same resamples (interval and p = P*(d* <= 0)) is judged instead,
    with the studentized numbers kept as '*_stud' (sharpe_pair).
    "Lower bound" is the lower end of the two-sided 95% interval. T-377 names a HAC CI: Newey-West (Bartlett, lag
    floor(4 (n/100)^(2/9))), normal 95%. T-474's trades do not overlap: per-trade means use a studentized bootstrap of
    trades (block 1), and the trial's null is a block shift of the position path against the returns by every multiple
    of 60 sessions (both must reject: rule 11).
  * Families (multiple testing), declared before any result. T-373: TLT long/flat (base), IEF long/flat on DGS10/DGS7,
    duration-neutral cross-maturity (SHY/IEI/IEF/TLT on DGS1..DGS20), base + 12-month momentum filter = 4. T-430: LQD vs
    IEF (base), HYG vs IEI, continuous sizing clip(z/2, -1, 1) on the trailing 60-month BAA10Y z-score, long-only LQD vs
    IEF switch = 4. T-433: top 3 (base), top 2, 10y + roll-down on the 10y-2y slope (not computable: OECD MEI has no
    2-year yields) = 3. T-432: D/P - r_local (base), D/P - r_USD (unhedged total carry), FX-hedged base (synthetic
    forwards from fx-spot-g10 and fx-rates-3m), top 3 = 4. T-474: 2s5s10s (base), 5s10s30s on IEF/TLH/TLT (not
    computable: DGS30 is not archived), PCA curvature factor, base skipping FOMC weeks = 4. T-381: 3 composite variants
    + every sleeve trial (T-368 6, T-431 4, T-433 3, T-432 4, T-430 4, T-362 10) = 34. DSR (batch6c_mom.family_dsr):
    trial-Sharpe variance = the computed family's observed variance floored at the zero-skill 1/(T-1); when the trial's
    "DSR" could mean the strategy's own series or the claim's difference series (T-373), or two windows (T-430), or
    per-trade and daily series (T-474), every reading is computed and the criterion needs all (rule 11 spirit).
  * Below trial.min_n (rule 5): never supported; a failing criterion counts only when it fails decisively (its 95%
    interval wholly on the wrong side, the PSR against zero <= 0.05 for a DSR, or a count that cannot grow).

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments import batch5_fx as fxm
from mandel.experiments import batch6b_bw as _bw
from mandel.experiments.batch6b_bw import (Bills, _boot_idx, _chunks, _ci_crit, _clean, _decide, _mean_stat,
                                           _sr_diff_stat, _stud, all_constructions, lw_test, mc_escalate, mc_reps, resolve,
                                           sharpe_diff_test, spy_dividends)
from mandel.experiments.batch6c_mom import dsr_row, family_dsr, month_grid
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import _hac_var, sharpe_ratio

N_BOOT = 5000                  # the trials' 5,000 bootstrap draws
REPS = 5                       # bootstrap seeds behind every decisive interval end
SEED = 0
BLOCK = 12                     # months
PPY = 12
DSR_PASS = 0.95
ALPHA = 0.05
_N = NormalDist()

DTB3_B = "fred-DTB3"
RATES_B = "fx-rates-3m"
SPOT_B = "fx-spot-g10"
VIX_B = "cboe-VIX-history"
USREC_B = "fred-USREC"
FOMC_B = "fomc-meetings"
DBC_B = "daily-history-DBC"


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in s)


def dh(sym: str) -> str:
    return "daily-history-" + _safe(sym)


def de(sym: str) -> str:
    return "daily-events-" + _safe(sym)


def fr(sid: str) -> str:
    return "fred-" + sid


def al(sid: str) -> str:
    return "alfred-" + sid


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
        return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]
    return _cached(archive, ("rows", name), load)


def _capture_day(archive, name: str) -> str:
    cap = getattr(archive.get(name), "created_at", None)
    return str(cap)[:10] if cap else "9999-12-31"


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _daily(archive, name: str) -> dict:
    """{'days', 'close' (split-adjusted), 'adj' (total return), 'open' (on the adj basis; NaN when missing)} of a Yahoo
    daily bundle; a bar without adjclose carries the previous adjclose/close ratio."""
    def load():
        by = {}
        for r in _rows(archive, name):
            v = r["value"]
            c = _num(v.get("close"))
            if c is None or c <= 0:
                continue
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
            a = _num(v.get("adjclose"))
            o = _num(v.get("open"))
            by[d] = (c, a if a and a > 0 else float("nan"), o if o and o > 0 else float("nan"))
        days = sorted(by)
        arr = np.array([by[d] for d in days], float).reshape(-1, 3)
        close, adj, opn = arr[:, 0], arr[:, 1].copy(), arr[:, 2]
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return {"days": days, "close": close, "adj": adj, "open": opn * adj / close}
    return _cached(archive, ("daily", name), load)


def _series(archive, name: str) -> dict:
    """{day: value} of a FRED bundle; blank prints are skipped."""
    def load():
        out = {}
        for r in _rows(archive, name):
            v = r["value"]
            x = _num(v.get("value", v.get("close")))
            if x is not None and v.get("day"):
                out[v["day"]] = x
        return out
    return _cached(archive, ("series", name), load)


def _monthly_series(archive, name: str) -> dict:
    """{'YYYY-MM': value} of a monthly FRED bundle (observation dated the first of the month)."""
    return _cached(archive, ("mseries", name), lambda: {d[:7]: x for d, x in _series(archive, name).items()})


def _bills(archive) -> Bills:
    return _cached(archive, ("bills",), lambda: Bills(_series(archive, DTB3_B)))


def _divs(archive, sym: str) -> dict:
    """{ex_date: cash dividend per share} from ``daily-events-<SYM>``."""
    def load():
        out = {}
        for r in _rows(archive, de(sym)):
            v = r["value"]
            if (v.get("type") or r.get("kind")) != "dividend":
                continue
            amt, d = _num(v.get("amount")), v.get("ex_date")
            if amt and amt > 0 and d:
                out[d] = out.get(d, 0.0) + amt
        return out
    return _cached(archive, ("divs", sym), load)


def _alfred(archive, sid: str) -> dict:
    """{'YYYY-MM': [(realtime_start, realtime_end, value, first_vintage, lag_rule_day)]} of an ALFRED bundle."""
    def load():
        obs: dict = {}
        for r in _rows(archive, al(sid)):
            v = r["value"]
            day, rs = v.get("day"), v.get("realtime_start")
            if not day or not rs:
                continue
            lag = v.get("lag_rule_at")
            obs.setdefault(day[:7], []).append((rs, v.get("realtime_end") or "9999-12-31", _num(v.get("value")),
                                                bool(v.get("first_vintage")), str(lag)[:10] if lag else None))
        for m in obs:
            obs[m].sort()
        return obs
    return _cached(archive, ("alfred", sid), load)


def _rates3m(archive) -> dict:
    """{ccy: {'YYYY-MM': rate3m percent}} of ``fx-rates-3m``."""
    def load():
        out: dict = {}
        for r in _rows(archive, RATES_B):
            v = r["value"]
            x = _num(v.get("rate3m"))
            if x is not None and v.get("ccy") and v.get("month"):
                out.setdefault(v["ccy"], {})[v["month"]] = x
        return out
    return _cached(archive, ("rates3m",), load)


def _spot(archive) -> dict:
    """{ccy: {day: USD per unit}} of ``fx-spot-g10``."""
    def load():
        out: dict = {}
        for r in _rows(archive, SPOT_B):
            v = r["value"]
            x = _num(v.get("usd_per_unit"))
            if x and x > 0 and v.get("ccy") and v.get("day"):
                out.setdefault(v["ccy"], {})[v["day"]] = x
        return out
    return _cached(archive, ("spot",), load)


# =============================================================================================== small helpers ==

def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def _month_add(m: str, k: int) -> str:
    y, mo = int(m[:4]), int(m[5:7]) - 1 + k
    return f"{y + mo // 12:04d}-{mo % 12 + 1:02d}"


def _months(a: str, b: str) -> list:
    out, m = [], a
    while m <= b:
        out.append(m)
        m = _month_add(m, 1)
    return out


def _month_last_day(m: str) -> str:
    return (date.fromisoformat(_month_add(m, 1) + "-01") - timedelta(days=1)).isoformat()


class Asof:
    """Latest value of a dated series on or before a day (``strict``: strictly before), at most ``max_age`` calendar days
    old (None = no limit)."""

    def __init__(self, series: dict, max_age: Optional[int] = None):
        self.k = sorted(series)
        self.v = [series[x] for x in self.k]
        self.o = [_ord(x) for x in self.k]
        self.max_age = max_age

    def at(self, day: str, strict: bool = False) -> Optional[float]:
        j = (bisect.bisect_left(self.k, day) if strict else bisect.bisect_right(self.k, day)) - 1
        if j < 0:
            return None
        if self.max_age is not None and _ord(day) - self.o[j] > self.max_age:
            return None
        return float(self.v[j])


def bey(d_pct: float) -> float:
    """Bond-equivalent (investment) yield, percent, of a 91-day bill quoted at discount yield ``d_pct`` percent."""
    d = d_pct / 100.0
    return 100.0 * 365.0 * d / (360.0 - 91.0 * d)


class Accrual:
    """DTB3 accrued calendar day by calendar day at the print dated strictly before each day (FRED posts a day late), under
    a stated conversion of the discount yield d: 'cont' (rule 7: r = -ln(1 - d 91/360)/(91/365), growth exp(sum r/365):
    identical to batch6b_bw.Bills), 'bey' (the investment yield i = 365 d/(360 - 91 d), compounded daily at i/365,
    actual/365), 'disc' (the raw discount yield compounded daily: the reading rule 7 forbids, reported only)."""

    def __init__(self, dtb3: dict, conv: str = "cont"):
        ks = sorted(dtb3)
        if not ks:
            raise ValueError("no DTB3 prints")
        self.p = np.array([_ord(k) for k in ks], np.int64)
        d = np.array([float(dtb3[k]) for k in ks], float) / 100.0
        if conv == "cont":
            lr = -np.log(1.0 - d * 91.0 / 360.0) / (91.0 / 365.0) / 365.0
        elif conv == "bey":
            lr = np.log1p(365.0 * d / (360.0 - 91.0 * d) / 365.0)
        elif conv == "disc":
            lr = np.log1p(d / 365.0)
        else:
            raise ValueError(conv)
        self.lr = lr
        self.lo, self.hi = int(self.p[0]), int(self.p[-1]) + 1
        o = np.arange(self.lo, self.hi + 1)
        rate = lr[np.maximum(np.searchsorted(self.p, o, side="left") - 1, 0)]
        self.cum = np.concatenate([[0.0], np.cumsum(rate)])

    def _c(self, o: int) -> float:
        if o <= self.lo:
            return (o - self.lo) * float(self.lr[0])
        if o > self.hi:
            return float(self.cum[self.hi - self.lo]) + (o - self.hi) * float(self.lr[-1])
        return float(self.cum[o - self.lo])

    def growth(self, d0: str, d1: str) -> float:
        return math.exp(self._c(_ord(d1)) - self._c(_ord(d0)))


def _rate_at(rates: dict, ccy: str, m: str, max_fill: int = 12) -> tuple:
    """(rate for month m or the latest earlier print within ``max_fill`` months, months filled; -1 = none)."""
    s = rates.get(ccy, {})
    for k in range(max_fill + 1):
        mm = _month_add(m, -k)
        if mm in s:
            return s[mm], k
    return None, -1


# ================================================================================================== statistics ==

def _sr_stat(X, bw):
    """Row-wise per-period Sharpe (population moments) and its s.e. from the delta-method influence function with a
    fixed-bandwidth Bartlett long-run variance (the single-series half of batch6b_bw._sr_diff_stat)."""
    n = X.shape[1]
    m = X.mean(axis=1)
    g = (X * X).mean(axis=1)
    v = np.maximum(g - m ** 2, 1e-300)
    z = (g / v ** 1.5)[:, None] * (X - m[:, None]) - (m / (2 * v ** 1.5))[:, None] * (X * X - g[:, None])
    return m / np.sqrt(v), np.sqrt(_hac_var(z, bw) / n)


def nw_lag(n: int) -> int:
    """Newey-West lag floor(4 (n/100)^(2/9)), at least 1."""
    return max(1, int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))


def hac_mean(x, lag: Optional[int] = None) -> dict:
    """Mean with a Newey-West (Bartlett) s.e.; t and one-sided p (H0: mean <= 0)."""
    x = np.asarray(x, float)
    n = x.size
    if n < 3:
        return {"mean": float(x.mean()) if n else None, "se": None, "t": None, "p": None, "lag": None, "n": int(n)}
    L = nw_lag(n) if lag is None else int(lag)
    u = x - x.mean()
    s = float(u @ u) / n
    for l in range(1, min(L, n - 1) + 1):
        s += 2.0 * (1.0 - l / (L + 1.0)) * float(u[l:] @ u[:-l]) / n
    se = math.sqrt(max(s, 1e-300) / n)
    t = float(x.mean() / se)
    return {"mean": float(x.mean()), "se": se, "t": t, "p": 1.0 - _N.cdf(t), "lag": L, "n": int(n)}


def rank_weights(score: np.ndarray, elig: np.ndarray, k: int) -> np.ndarray:
    """One month's long/short weights: +1/k on the k highest scores, -1/k on the k lowest among eligible names (stable
    order on ties); zeros when fewer than 2k names are eligible."""
    w = np.zeros(score.size)
    idx = np.flatnonzero(elig & np.isfinite(score))
    if k < 1 or idx.size < 2 * k:
        return w
    o = idx[np.argsort(-score[idx], kind="stable")]
    w[o[:k]] = 1.0 / k
    w[o[-k:]] = -1.0 / k
    return w


def book(W, R, cost, borrow=None, hold_days=None) -> dict:
    """Net returns of a zero-investment book (one unit long, one short) with target weights W (T, N) on hold returns R
    (T, N): gross = sum W R; borrow (N,) a year on the short notional over ``hold_days`` (T,) calendar days; turnover
    against the previous weights drifted over their hold; net = (1 - cost x turnover)(1 + gross - borrow) - 1, ``cost``
    (N,) per side per unit traded."""
    W = np.asarray(W, float)
    R = np.asarray(R, float)
    if ((W != 0) & ~np.isfinite(R)).any():
        raise ValueError("a held name has no hold return")
    R0 = np.where(np.isfinite(R), R, 0.0)
    T = W.shape[0]
    gross = (W * R0).sum(axis=1)
    bor = np.zeros(T)
    if borrow is not None:
        bor = (np.maximum(-W, 0.0) * np.asarray(borrow, float)[None, :]).sum(axis=1) * np.asarray(hold_days, float) / 365.0
    pre = gross - bor
    prev = np.zeros_like(W)
    if T > 1:
        den = 1.0 + pre[:-1]
        den = np.where(np.abs(den) < 1e-12, 1e-12, den)
        prev[1:] = W[:-1] * (1.0 + R0[:-1]) / den[:, None]
    to = np.abs(W - prev)
    c = (to * np.asarray(cost, float)[None, :]).sum(axis=1)
    return {"net": (1.0 - c) * (1.0 + pre) - 1.0, "gross": gross, "borrow": bor, "cost": c, "turnover": to.sum(axis=1)}


def _sr_pp(x) -> Optional[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(sharpe_ratio(x)) if x.size > 2 and x.std() > 0 else None


def _sr_ann(x, ppy: float = PPY) -> Optional[float]:
    s = _sr_pp(x)
    return None if s is None else s * math.sqrt(ppy)


def sharpe_one(x, ppy: float = PPY, block: int = BLOCK, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Annualised Sharpe (ddof 1) with a studentized circular block bootstrap: two-sided 95% CI, p (H0: Sharpe <= 0)."""
    x = np.asarray(x, float)
    n = x.size
    out = {"n": int(n), "sharpe": _sr_ann(x, ppy), "ci": [None, None], "p": None, "p_lt": None, "block": None, "se": None}
    if n < 8:
        return out
    c = math.sqrt(ppy) * math.sqrt((n - 1) / n)
    r = _stud(_sr_stat, [x], block, N_BOOT if n_boot is None else n_boot, seed)
    sc = lambda v: [None if y is None else y * c for y in v]
    out.update(ci=sc(r["ci"]), ci_pct=sc(r.get("ci_pct", [None, None])), p=r["p"], p_lt=r["p_lt"], block=r["block"],
               se=None if r["se"] is None else r["se"] * c)
    return out


def sharpe_ci(x, thr: float = 0.0, ppy: float = PPY, block: int = BLOCK, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """``sharpe_one`` over ``reps`` seeds (escalated when the lower end cannot be resolved against ``thr``)."""
    x = np.asarray(x, float)
    return mc_escalate(lambda seed: sharpe_one(x, ppy, block, None, seed), lambda t: _ci_crit(t, "gt", thr, "")[1],
                       REPS if reps is None else reps, seed)


def mean_ci(x, block: int = BLOCK, reps: Optional[int] = None, seed: int = SEED, thr: float = 0.0) -> dict:
    """Studentized circular block bootstrap of a mean: est, two-sided 95% CI over ``reps`` seeds, p (H0: mean <= 0)."""
    x = np.asarray(x, float)
    return mc_escalate(lambda seed: _stud(_mean_stat, [x], block, N_BOOT, seed), lambda t: _ci_crit(t, "gt", thr, "")[1],
                       REPS if reps is None else reps, seed)


PAIR_MIN_DIFF_BLOCKS = 2       # the paired series must differ in at least two blocks' worth of months ...
PAIR_MAX_ZERO_SE = 0.01        # ... and at most this share of resamples may have zero s.e., else the studentized CBB is degenerate


def _pair_once(a, b, block: int, seed: int) -> dict:
    """``sharpe_diff_test`` for one seed plus, on the very same resamples (batch6b_bw._stud's index stream: same seed,
    chunks and blocks), the share of resamples with zero s.e. (none of the months where the two series differ was drawn:
    _stud drops them) and the percentile p-values P*(d* <= 0) (H0: diff <= 0) and P*(d* >= 0) (H0: diff >= 0), stored as
    one-element lists so ``mc_reps`` averages them over seeds."""
    t = sharpe_diff_test(a, b, PPY, block, N_BOOT, seed)
    n, bl = a.size, t.get("block")
    nz = nle = nge = tot = 0
    if bl is not None:
        rng = np.random.default_rng(seed)
        for k in _chunks(N_BOOT, 2 * n):
            idx = _boot_idx(rng, n, bl, k)
            d, se = _sr_diff_stat(a[idx], b[idx], bl)
            nz, nle, nge, tot = nz + int(np.sum(se <= 1e-14)), nle + int(np.sum(d <= 0)), nge + int(np.sum(d >= 0)), tot + d.size
    t["zero_se_share"] = [nz / tot if tot else None]
    t["p_pct"] = [(nle + 1) / (tot + 1) if tot else None]
    t["p_lt_pct"] = [(nge + 1) / (tot + 1) if tot else None]
    return t


def _pair_construction(t: dict, n_diff: int) -> dict:
    """Pick the paired construction. The studentized CBB is degenerate when the two series differ in fewer than
    PAIR_MIN_DIFF_BLOCKS blocks' worth of months or more than PAIR_MAX_ZERO_SE of its resamples have zero s.e. (they are
    dropped, which inflates its upper end: T-373's 2002-2013 window differs in 2 of 137 months). Then the interval and the
    p-values judged are the percentile CBB's on the same resamples; the studentized ones are kept under '*_stud'."""
    n, bl = t.get("n"), t.get("block") or BLOCK
    zs = (t.get("zero_se_share") or [None])[0]
    t["n_differ"] = int(n_diff)
    why = []
    if n_diff < PAIR_MIN_DIFF_BLOCKS * bl:
        why.append(f"the series differ in {n_diff} of {n} months, fewer than {PAIR_MIN_DIFF_BLOCKS} x {bl}")
    if zs is not None and zs > PAIR_MAX_ZERO_SE:
        why.append(f"{zs:.1%} of resamples have zero s.e. (> {PAIR_MAX_ZERO_SE:.0%})")
    pct = t.get("ci_pct") or [None, None]
    p_pct, p_lt_pct = (t.get("p_pct") or [None])[0], (t.get("p_lt_pct") or [None])[0]
    if not why or n_diff == 0 or None in pct or p_pct is None:
        # n_diff == 0: identical series, difference exactly 0 (the studentized early return, ci [0, 0], p 1) stands
        t["construction"], t["degenerate"] = "studentized CBB", ("; ".join(why) if why else None)
        return t
    t.update(ci_stud=t.get("ci"), ci_stud_mc_se=t.get("ci_mc_se"), p_stud=t.get("p"), p_stud_mc_se=t.get("p_mc_se"),
             p_lt_stud=t.get("p_lt"))
    t.update(ci=list(pct), ci_mc_se=t.get("ci_pct_mc_se"), p=p_pct, p_mc_se=(t.get("p_pct_mc_se") or [0.0])[0], p_lt=p_lt_pct,
             construction="percentile CBB", degenerate="; ".join(why))
    return t


def sharpe_pair(a, b, check: Optional[Callable] = None, block: int = BLOCK, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """Paired CBB of Sharpe(a) - Sharpe(b) over ``reps`` seeds (escalated to REPS_MAX when ``check`` is unresolved): the
    studentized CBB (batch6b_bw.sharpe_diff_test), or the percentile CBB on the same resamples when the studentized one
    is degenerate (``_pair_construction``). Reports 'n_differ', the months in which the two series differ."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n_diff = int(np.sum(np.abs(a - b) > 1e-12)) if a.size == b.size else 0
    if a.size < 8:
        t = sharpe_diff_test(a, b, PPY, block, N_BOOT, seed)
        t.update(n_differ=n_diff, construction="n/a (fewer than 8 months)", degenerate=None)
        return t
    check = check or (lambda t: _ci_crit(t, "gt", 0.0, "")[1])
    keys = ("ci", "ci_pct", "zero_se_share", "p_pct", "p_lt_pct")
    r = REPS if reps is None else reps
    t = _pair_construction(mc_reps(lambda seed: _pair_once(a, b, block, seed), r, seed, keys), n_diff)
    if check(t) is None and _bw.REPS_MAX > r:
        t = _pair_construction(mc_reps(lambda seed: _pair_once(a, b, block, seed), _bw.REPS_MAX, seed, keys), n_diff)
    return t


def _pair_txt(t: dict, ci_name: bool = True) -> str:
    """'k of n months differ; <construction> CI lo to hi' (+ why the studentized CBB was replaced)."""
    t = t or {}
    deg = f" (studentized CBB degenerate: {t['degenerate']})" if t.get("construction") == "percentile CBB" else ""
    con = (t.get("construction") or "CBB") + " " if ci_name else ""
    return f"{t.get('n_differ', 'n/a')} of {t.get('n', 'n/a')} months differ; {con}{_ci(t.get('ci'))}{deg}"


def ols_nw(y, X, lag: int) -> dict:
    """OLS y = a + X b with Newey-West (Bartlett) standard errors; X is (n, k)."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(len(y), -1)
    n = y.size
    Z = np.column_stack([np.ones(n), X])
    if n <= Z.shape[1] + 1:
        return {"coef": None, "se": None, "t": None, "r2": None, "n": int(n)}
    ZtZi = np.linalg.pinv(Z.T @ Z)
    b = ZtZi @ Z.T @ y
    e = y - Z @ b
    u = Z * e[:, None]
    S = u.T @ u
    for l in range(1, min(lag, n - 1) + 1):
        G = u[l:].T @ u[:-l]
        S += (1.0 - l / (lag + 1.0)) * (G + G.T)
    se = np.sqrt(np.maximum(np.diag(ZtZi @ S @ ZtZi), 0.0))
    ss = float(((y - y.mean()) ** 2).sum())
    return {"coef": [float(v) for v in b], "se": [float(v) for v in se],
            "t": [float(c / s) if s > 0 else None for c, s in zip(b, se)], "r2": 1.0 - float(e @ e) / ss if ss > 0 else None,
            "n": int(n)}


def corr_ci(a, b, level: float = 0.95) -> dict:
    """Pearson correlation with a Fisher-z interval."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = int(a.size)
    if n < 4 or a.std() == 0 or b.std() == 0:
        return {"r": None, "ci": [None, None], "n": n}
    r = float(np.corrcoef(a, b)[0, 1])
    z, s = math.atanh(max(min(r, 0.999999), -0.999999)), 1.0 / math.sqrt(n - 3)
    q = _N.inv_cdf(0.5 + level / 2)
    return {"r": r, "ci": [math.tanh(z - q * s), math.tanh(z + q * s)], "n": n}


def _pt_row(label: str, value: Optional[float], thr: float, ci, fmt: Callable = None, side: str = "gt") -> tuple:
    """(name, ok, decisive) for a point criterion 'value > thr' ('lt': value < thr); decisive when the 95% interval lies
    wholly on the wrong side of ``thr``."""
    fmt = fmt or _s
    lo, hi = (ci or (None, None))[:2]
    if value is None:
        return f"{label} (n/a)", None, False
    if side == "gt":
        return f"{label} ({fmt(value)}; {_ci(ci)})", bool(value > thr), hi is not None and hi < thr
    return f"{label} ({fmt(value)}; {_ci(ci)})", bool(value < thr), lo is not None and lo > thr


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _bp(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f} bp"


def _ci(ci, nd: int = 3, scale: float = 1.0, unit: str = "") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"CI {lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _window(labels: Sequence[str], a: str, b: str) -> np.ndarray:
    return np.array([a <= l <= b for l in labels], bool)


def _fam(rows: Sequence) -> list:
    return [_sr_pp(r) for r in rows if r is not None and np.asarray(r).size > 2]


def _dsr_pair(rows: Sequence[tuple], label: str) -> tuple:
    """Rule 11 over DSR readings: each row = (dsr dict, reading label)."""
    return all_constructions([dsr_row(d, nm) for d, nm in rows], label)


# ============================================================================= T-373 Treasury carry + roll-down ==

T373_START, T373_END, T373_TEST = "2002-08", "2026-09", "2014-01"
T373_MIN_N = 280
T373_DIFF_THR = 0.15
T373_N_TRIALS = 4
T373_SWITCH = 0.0002           # 2 bps per switch = 1 bp per side of each unit traded
T373_D = {"SHY": 1.9, "IEI": 4.4, "IEF": 7.5, "TLT": 17.0}
# Cross-maturity points: (ETF, yield, local-slope partner, gap in years): roll-down = D x (y - y_partner) / gap / 12.
T373_POINTS = (("SHY", "DGS2", "DGS1", 1.0), ("IEI", "DGS5", "DGS3", 2.0), ("IEF", "DGS10", "DGS7", 3.0),
               ("TLT", "DGS20", "DGS10", 10.0))
T373_YIELDS = ("DGS1", "DGS2", "DGS3", "DGS5", "DGS7", "DGS10", "DGS20", "DTB3")
CASH_ETFS = ("SGOV", "BIL")


def _fill_prices(p: dict, fill: str) -> dict:
    arr = p["open"] if fill == "open" else p["adj"]
    return {d: (float(x) if np.isfinite(x) and x > 0 else float(a)) for d, x, a in zip(p["days"], arr, p["adj"])}


def _cash(P: dict, f0: str, f1: str, rf: float) -> tuple:
    """Cash-leg return between fills: SGOV when it has both fills, else BIL, else the DTB3 accrual."""
    for s in CASH_ETFS:
        q = P.get(s)
        if q is not None and f0 in q and f1 in q:
            return q[f1] / q[f0] - 1.0, s
    return rf, "DTB3"


def curve_carry(px: dict, ylds: dict, bills: Bills, start: str = T373_START, end: str = T373_END, fill: str = "open",
                cash_etfs: bool = True) -> dict:
    """T-373 engine on TLT's session calendar. Decision = the month's last session close (yields: the latest prints dated
    on or before it, at most 10 days old); fill = the next session's open (``fill='adj'``: its close); a hold runs fill to
    fill and is labelled by the fill month. Signal = (DGS20 - BEY(DTB3))/12 + 17 (DGS20 - DGS10)/10/12 > 0 -> TLT, else
    cash (SGOV, BIL, or the DTB3 accrual before they list; ``cash_etfs=False``: always the accrual). Variants on the same
    holds: IEF on (DGS10 - BEY)/12 + 7.5 (DGS10 - DGS7)/3/12; duration-neutral cross-maturity (long the point with the
    highest (carry + roll-down)/duration, short the lowest, DV01-matched); the base with a 12-month TLT excess-momentum
    filter. Excess returns subtract the bill growth over the hold."""
    days = px["TLT"]["days"]
    g = month_grid(days)
    P = {s: _fill_prices(p, fill) for s, p in px.items()}
    C = {s: dict(zip(p["days"], p["adj"])) for s, p in px.items()}
    Y = {sid: Asof(v, max_age=10) for sid, v in ylds.items()}
    me, ex, ms = g["me"], g["ex"], g["months"]
    rec = {k: [] for k in ("labels", "dec", "f0", "f1", "rf", "tlt", "cash", "cash_src", "sig", "sig_disc", "ief", "sig_ief",
                           "cross_ex", "cross_pos", "mom")}
    skipped = []
    for k in range(len(ms) - 1):
        d, f0, f1 = days[me[k]], days[ex[k]], days[ex[k + 1]]
        lab = f0[:7]
        if lab < start or lab > end:
            continue
        y = {sid: (Y[sid].at(d) if sid in Y else None) for sid in T373_YIELDS}
        if y["DGS20"] is None or y["DGS10"] is None or y["DTB3"] is None:
            skipped.append(lab)
            continue
        rb = bey(y["DTB3"])
        roll = T373_D["TLT"] * (y["DGS20"] - y["DGS10"]) / 10.0 / 12.0
        rf = bills.growth(f0, f1) - 1.0
        cash, src = _cash(P, f0, f1, rf) if cash_etfs else (rf, "DTB3")
        rec["labels"].append(lab)
        rec["dec"].append(d)
        rec["f0"].append(f0)
        rec["f1"].append(f1)
        rec["rf"].append(rf)
        rec["tlt"].append(P["TLT"][f1] / P["TLT"][f0] - 1.0)
        rec["cash"].append(cash)
        rec["cash_src"].append(src)
        rec["sig"].append((y["DGS20"] - rb) / 12.0 + roll)
        rec["sig_disc"].append((y["DGS20"] - y["DTB3"]) / 12.0 + roll)
        q = P.get("IEF")
        if q is not None and f0 in q and f1 in q and y["DGS7"] is not None:
            rec["ief"].append(q[f1] / q[f0] - 1.0)
            rec["sig_ief"].append((y["DGS10"] - rb) / 12.0 + T373_D["IEF"] * (y["DGS10"] - y["DGS7"]) / 3.0 / 12.0)
        else:
            rec["ief"].append(np.nan)
            rec["sig_ief"].append(np.nan)
        # cross-maturity
        ok = all(s in P and f0 in P[s] and f1 in P[s] for s, *_ in T373_POINTS) and all(y[a] is not None and y[b] is not None
                                                                                       for _, a, b, _g in T373_POINTS)
        if ok:
            e = {}
            for s, a, b, gap in T373_POINTS:
                D = T373_D[s]
                e[s] = ((y[a] - rb) / 12.0 + D * (y[a] - y[b]) / gap / 12.0) / D
            order = sorted(e, key=lambda s: (-e[s], [p[0] for p in T373_POINTS].index(s)))
            L, S = order[0], order[-1]
            hS = T373_D[L] / T373_D[S]
            rL, rS = P[L][f1] / P[L][f0] - 1.0, P[S][f1] / P[S][f0] - 1.0
            rec["cross_ex"].append((rL - rf) - hS * (rS - rf))
            rec["cross_pos"].append({L: 1.0, S: -hS})
        else:
            rec["cross_ex"].append(np.nan)
            rec["cross_pos"].append(None)
        if k >= 12 and days[me[k - 12]] in C["TLT"]:
            d12 = days[me[k - 12]]
            rec["mom"].append(C["TLT"][d] / C["TLT"][d12] - 1.0 - (bills.growth(d12, d) - 1.0))
        else:
            rec["mom"].append(np.nan)
    out = {k: (np.array(v, float) if k not in ("labels", "dec", "f0", "f1", "cash_src", "cross_pos") else v) for k, v in rec.items()}
    out["skipped"] = skipped

    def timed(pos, risky):
        pos = np.asarray(pos, float)
        sw = np.r_[0.0, np.abs(np.diff(pos))]
        return pos * risky + (1.0 - pos) * out["cash"] - T373_SWITCH * sw, int(sw.sum())

    rf = out["rf"]
    pos = (out["sig"] > 0).astype(float)
    tb, nsw = timed(pos, out["tlt"])
    out.update(pos=pos, timed=tb, n_switch=nsw, ex_timed=tb - rf, ex_bh=out["tlt"] - rf)
    pos_d = (out["sig_disc"] > 0).astype(float)
    out["ex_timed_disc"] = timed(pos_d, out["tlt"])[0] - rf
    out["signal_disagree"] = int(np.sum(pos != pos_d))
    # IEF variant (rows where it exists)
    iv = np.isfinite(out["ief"])
    ex_ief_t, ex_ief_b = np.full(len(rf), np.nan), np.full(len(rf), np.nan)
    if iv.any():
        p_i = (out["sig_ief"][iv] > 0).astype(float)
        sw = np.r_[0.0, np.abs(np.diff(p_i))]
        ex_ief_t[iv] = p_i * out["ief"][iv] + (1 - p_i) * out["cash"][iv] - T373_SWITCH * sw - rf[iv]
        ex_ief_b[iv] = out["ief"][iv] - rf[iv]
    out["ex_ief_timed"], out["ex_ief_bh"] = ex_ief_t, ex_ief_b
    # cross-maturity: 1 bp per side on every unit traded when the legs change
    cx = out["cross_ex"].copy()
    prev = None
    for i, w in enumerate(out["cross_pos"]):
        if w is None:
            prev = None
            continue
        if prev is not None:
            names = set(w) | set(prev)
            cx[i] -= (T373_SWITCH / 2.0) * sum(abs(w.get(s, 0.0) - prev.get(s, 0.0)) for s in names)
        prev = w
    out["ex_cross"] = cx
    # momentum-filtered base
    mv = np.isfinite(out["mom"])
    ex_m = np.full(len(rf), np.nan)
    if mv.any():
        p_m = ((out["sig"][mv] > 0) & (out["mom"][mv] > 0)).astype(float)
        sw = np.r_[0.0, np.abs(np.diff(p_m))]
        ex_m[mv] = p_m * out["tlt"][mv] + (1 - p_m) * out["cash"][mv] - T373_SWITCH * sw - rf[mv]
    out["ex_mom"] = ex_m
    return out


T373_READINGS = (("ex_timed", "BEY reading"), ("ex_timed_disc", "raw-DTB3 reading"))


def judge_curve_carry(res: dict, min_n: int = T373_MIN_N, test_from: str = T373_TEST, full: tuple = (T373_START, T373_END)) -> dict:
    """Criteria (rule 1: the claim's full-window 'higher Sharpe', the pass's test-window difference > 0.15, p < 0.05 and
    DSR > 0.95 at 4 trials), each judged under both signal readings (rule 7 / rule 11): the carry term with the bill's
    bond-equivalent yield (BEY(DTB3), comparable with the par yield DGS20) and the as-worded raw discount DTB3. A
    criterion passes only when both readings pass and is undecided when they disagree."""
    lab = res["labels"]
    fw = _window(lab, *full)
    n = int(fw.sum())
    te = fw & np.array([l >= test_from for l in lab], bool)
    xb, xb_f = res["ex_bh"][te], res["ex_bh"][fw]
    chk = lambda t: resolve(t.get("p"), t.get("p_mc_se"), ALPHA, "lt")[0]
    t0 = lab[np.flatnonzero(te)[0]] if te.any() else "n/a"
    full_rows, diff_rows, p_rows, dsr_rows, tests, fulls = [], [], [], [], {}, {}
    fam_other_s = [res["ex_ief_timed"][te], res["ex_cross"][te], res["ex_mom"][te]]
    fam_other_d = [res["ex_ief_timed"][te] - res["ex_ief_bh"][te], res["ex_cross"][te], res["ex_mom"][te] - xb]
    for key, nm in T373_READINGS:
        xa = res[key][te]
        sh = sharpe_pair(xa, xb, check=chk)
        fa = sharpe_pair(res[key][fw], xb_f, check=lambda t: True, reps=1)
        tests[key], fulls[key] = sh, fa
        full_rows.append(_pt_row(f"{nm} {_s(fa.get('diff'))} (Sharpe {_f(fa.get('sharpe_a'))} vs {_f(fa.get('sharpe_b'))}; "
                                 f"{fa.get('n_differ')} of {fa.get('n')} months differ; {fa.get('construction')})",
                                 fa.get("diff"), 0.0, fa.get("ci")))
        diff_rows.append(_pt_row(f"{nm} (Sharpe {_f(sh.get('sharpe_a'))} vs {_f(sh.get('sharpe_b'))}; {sh.get('n_differ')} of "
                                 f"{sh.get('n')} months differ; {sh.get('construction')})", sh.get("diff"),
                                 T373_DIFF_THR, sh.get("ci")))
        ok_p, note = resolve(sh.get("p"), sh.get("p_mc_se"), ALPHA, "lt")
        deg = f", studentized degenerate: {sh['degenerate']}" if sh.get("construction") == "percentile CBB" else ""
        p_rows.append((f"{nm} p {_f(sh.get('p'), 4)} ({sh.get('construction')}{deg}){note}", ok_p,
                       sh.get("p_lt") is not None and sh["p_lt"] < ALPHA))
        fs = [x[np.isfinite(x)] for x in [xa] + fam_other_s]
        fd = [x[np.isfinite(x)] for x in [xa - xb] + fam_other_d]
        dsr_rows.append((family_dsr(xa, _fam(fs), T373_N_TRIALS), f"{nm}, timed excess returns"))
        dsr_rows.append((family_dsr(xa - xb, _fam(fd), T373_N_TRIALS), f"{nm}, timed-minus-buy-and-hold differences"))
    crit = [all_constructions(full_rows, f"{full[0]}..{full[1]} ({n} months): Sharpe(timed) - Sharpe(buy-and-hold) > 0"),
            all_constructions(diff_rows, f"test window {t0}.. ({int(te.sum())} months): Sharpe(timed) - Sharpe(buy-and-hold) "
                                         f"> {T373_DIFF_THR}"),
            all_constructions(p_rows, "paired block-bootstrap p < 0.05 (H0: difference <= 0)"),
            _dsr_pair(dsr_rows, f"DSR > {DSR_PASS} at {T373_N_TRIALS} trials on the test window, every reading")]
    v, why = _decide(crit, n, min_n, "months")
    isw = fw & ~te
    ins = sharpe_pair(res["ex_timed"][isw], res["ex_bh"][isw], check=lambda t: True, reps=1) if isw.sum() >= 8 else None
    xa = res["ex_timed"][te]
    lw = lw_test(xa, xb, PPY, BLOCK, N_BOOT, SEED) if xa.size >= 8 else None
    fam_s = [x[np.isfinite(x)] for x in [xa] + fam_other_s]
    return {"n": n, "n_test": int(te.sum()), "test": tests["ex_timed"], "test_disc": tests["ex_timed_disc"],
            "full": fulls["ex_timed"], "full_disc": fulls["ex_timed_disc"], "dsr": {nm: d for d, nm in dsr_rows},
            "dsr_strategy": dsr_rows[0][0], "dsr_difference": dsr_rows[1][0], "in_sample": ins, "lw": lw,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why,
            "family_sharpe_ann": {"tlt_base": _sr_ann(fam_s[0]), "ief": _sr_ann(fam_s[1]), "cross_maturity": _sr_ann(fam_s[2]),
                                  "momentum_filter": _sr_ann(fam_s[3])}}


def b6c_rates_treasury_carry_rolldown(archive):
    """T-373: TLT only when 20-year carry + roll-down is positive vs buy-and-hold TLT; test 2014-2026."""
    need = [dh("TLT"), fr("DGS20"), fr("DGS10"), DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    px = {"TLT": _daily(archive, dh("TLT"))}
    for s in ("IEF", "IEI", "SHY") + CASH_ETFS:
        if _has(archive, dh(s)):
            px[s] = _daily(archive, dh(s))
    ylds = {sid: _series(archive, fr(sid)) for sid in T373_YIELDS if sid != "DTB3" and _has(archive, fr(sid))}
    ylds["DTB3"] = _series(archive, DTB3_B)
    bills = _bills(archive)
    res = curve_carry(px, ylds, bills)
    if len(res["labels"]) < 8:
        v, why = _decide([("enough hold months to test", None)], len(res["labels"]), T373_MIN_N, "months")
        return _out({"n": len(res["labels"])}, len(res["labels"]), v, f"only {len(res['labels'])} hold months — {why}")
    j = judge_curve_carry(res)
    te = _window(res["labels"], T373_TEST, T373_END)
    sens = {}
    for nm, kw in (("next_close", {"fill": "adj"}), ("dtb3_cash", {"cash_etfs": False})):
        r2 = curve_carry(px, ylds, bills, **kw)
        t2 = _window(r2["labels"], T373_TEST, T373_END)
        sens[nm] = _sr_ann(r2["ex_timed"][t2]) - _sr_ann(r2["ex_bh"][t2]) if t2.sum() > 2 else None
    t, td, ins = j["test"], j["test_disc"], j["in_sample"]
    fu, fd = j["full"], j["full_disc"]
    lab = res["labels"]
    srcs = {s: int(sum(1 for x in res["cash_src"] if x == s)) for s in ("SGOV", "BIL", "DTB3")}
    cash_m = int((res["pos"] == 0).sum())
    cash_te = int((res["pos"][te] == 0).sum())
    missing_v = [nm for nm, k in (("IEF (DGS7)", "ex_ief_timed"), ("cross-maturity", "ex_cross"), ("momentum", "ex_mom"))
                 if not np.isfinite(res[k][te]).any()]
    dsr_txt = "; ".join(f"{nm} {_f(d.get('dsr'))}" for nm, d in j["dsr"].items())
    reason = (f"TLT long/flat on (DGS20 - DTB3)/12 + 17 (DGS20 - DGS10)/10/12 > 0 at the month-end close (DTB3 read two "
              f"ways, both judged: as its bond-equivalent yield BEY(DTB3), rule 7, and as the raw discount yield the claim "
              f"writes; {res['signal_disagree']} months differ), filled at the next open, cash = SGOV/BIL/DTB3 accrual, 2 bps per "
              f"switch ({res['n_switch']} switches; in cash {cash_m} of {len(lab)} months, {cash_te} of {j['n_test']} test months), "
              f"hold months {lab[0]}..{lab[-1]} ({j['n']}). Paired intervals are the studentized CBB unless it is degenerate "
              f"(the two series differ in fewer than {PAIR_MIN_DIFF_BLOCKS} blocks' worth of months, or more than "
              f"{PAIR_MAX_ZERO_SE:.0%} of resamples have zero s.e. and would be dropped): then the percentile CBB on the same "
              f"resamples, interval and p. Full window: Sharpe difference {_s(fu.get('diff'))} (BEY; timed "
              f"{_f(fu.get('sharpe_a'))} vs buy-and-hold {_f(fu.get('sharpe_b'))}; {_pair_txt(fu)}) and {_s(fd.get('diff'))} "
              f"(raw; {_pair_txt(fd)}), need > 0. Test "
              f"{T373_TEST}..: Sharpe timed {_f(t.get('sharpe_a'))} vs buy-and-hold {_f(t.get('sharpe_b'))}, difference "
              f"{_s(t.get('diff'))} (BEY; {_pair_txt(t)}; p {_f(t.get('p'), 4)}) and {_s(td.get('diff'))} (raw; "
              f"{_pair_txt(td)}; p {_f(td.get('p'), 4)}), need > {T373_DIFF_THR} with p < 0.05 (Ledoit-Wolf, reported, BEY: "
              f"{_ci((j['lw'] or {}).get('ci'))}, p {_f((j['lw'] or {}).get('p'), 3)}); DSR at {T373_N_TRIALS} trials: {dsr_txt}. "
              f"In-sample {lab[0]}..2013-12 difference {_s((ins or {}).get('diff'))} ({_pair_txt(ins)}). "
              f"Sensitivities (BEY): next-close fills {_s(sens['next_close'])}; DTB3-accrual cash {_s(sens['dtb3_cash'])}. Cash "
              f"legs used: {srcs}. Variant Sharpes (test, annualised): "
              + ", ".join(f"{k} {_f(v, 2)}" for k, v in j["family_sharpe_ann"].items())
              + (f"; variants not computable: {missing_v}" if missing_v else "") + " — " + j["why"])
    stat = {"n_months": j["n"], "n_test_months": j["n_test"], "window": [lab[0], lab[-1]], "test": t, "test_raw_dtb3": td,
            "full": fu, "full_raw_dtb3": fd, "in_sample": ins, "ledoit_wolf": j["lw"], "dsr": j["dsr"],
            "family_sharpe_ann": j["family_sharpe_ann"], "n_switch": res["n_switch"], "months_in_cash": cash_m,
            "cash_sources": srcs, "sens_next_close_diff": sens["next_close"], "sens_dtb3_cash_diff": sens["dtb3_cash"],
            "signal_disagree_months": res["signal_disagree"],
            "skipped_months": res["skipped"], "criteria": j["criteria"], "durations": T373_D,
            "last_signal": {"decision": res["dec"][-1], "signal_pct_per_month": float(res["sig"][-1]), "in_tlt": bool(res["pos"][-1])},
            "rule10": "month-end calendar named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# =================================================================================== T-377 SGOV vs DTB3 accrual ==

T377_START, T377_END = "2020-07", "2026-09"
T377_MIN_N = 70
T377_FEE = 0.0009
T377_MEAN_BP, T377_CI_BP, T377_SD_BP = 10.0, 15.0, 20.0


def month_end_periods(days: Sequence[str], adj, start: str, end: str) -> dict:
    """Month-end close to month-end close returns for months start..end; a month counts only when its own and the
    previous month's last bars exist and a later bar shows the month complete."""
    adj = np.asarray(adj, float)
    last = {}
    for i, d in enumerate(days):
        last[d[:7]] = i
    lab, d0, d1, r = [], [], [], []
    for m in _months(start, end):
        p = _month_add(m, -1)
        if m not in last or p not in last or last[m] + 1 >= len(days):
            continue
        i0, i1 = last[p], last[m]
        lab.append(m)
        d0.append(days[i0])
        d1.append(days[i1])
        r.append(adj[i1] / adj[i0] - 1.0)
    return {"labels": lab, "d0": d0, "d1": d1, "r": np.array(r, float)}


def tracking_difference(etf: dict, dtb3: dict, start: str = T377_START, end: str = T377_END, fee: float = 0.0) -> dict:
    """Monthly (ETF total return + fee/12 - DTB3 accrual) under each conversion; annualised mean (12 x mean, bp), its
    Newey-West 95% CI, annualised SD (sd x sqrt 12, bp)."""
    per = month_end_periods(etf["days"], etf["adj"], start, end)
    out = {"labels": per["labels"], "n": len(per["labels"]), "r": per["r"]}
    for conv in ("bey", "cont", "disc"):
        acc = Accrual(dtb3, conv)
        g = np.array([acc.growth(a, b) - 1.0 for a, b in zip(per["d0"], per["d1"])], float)
        d = per["r"] + fee / 12.0 - g
        n = d.size
        h = hac_mean(d, nw_lag(n)) if n >= 3 else {"mean": None, "se": None, "lag": None}
        m = None if h.get("mean") is None else 12e4 * h["mean"]
        se = None if h.get("se") is None else 12e4 * h["se"]
        q = _N.inv_cdf(0.975)
        out[conv] = {"diff": d, "accrual": g, "mean_bp": m, "se_bp": se, "lag": h.get("lag"),
                     "ci_bp": [m - q * se, m + q * se] if m is not None and se is not None else [None, None],
                     "sd_bp": float(d.std(ddof=1) * math.sqrt(12) * 1e4) if n > 1 else None}
    return out


def judge_tracking(t: dict, min_n: int = T377_MIN_N) -> dict:
    def rows(c):
        x = t[c]
        m, (lo, hi), sd = x["mean_bp"], x["ci_bp"], x["sd_bp"]
        nm = {"bey": "the claim's investment yield accrued actual/365", "cont": "rule 7's continuous rate"}[c]
        r1 = (f"{nm}: |mean| < {T377_MEAN_BP:g} bp ({_bp(m)}/yr)", None if m is None else abs(m) < T377_MEAN_BP,
              lo is not None and (lo > T377_MEAN_BP or hi < -T377_MEAN_BP))
        r2 = (f"{nm}: HAC 95% CI inside +/-{T377_CI_BP:g} bp ({_bp(lo)} to {_bp(hi)}, NW lag {x['lag']})",
              None if lo is None else (lo > -T377_CI_BP and hi < T377_CI_BP),
              lo is not None and (lo > T377_CI_BP or hi < -T377_CI_BP))
        r3 = (f"{nm}: SD < {T377_SD_BP:g} bp ({_f(sd, 1)} bp/yr)", None if sd is None else sd < T377_SD_BP, False)
        return r1, r2, r3
    b, c = rows("bey"), rows("cont")
    crit = [all_constructions([b[i], c[i]], lbl) for i, lbl in enumerate(
        (f"|annualised mean tracking difference| < {T377_MEAN_BP:g} bp", f"HAC 95% CI inside +/-{T377_CI_BP:g} bp",
         f"annualised tracking-difference SD < {T377_SD_BP:g} bp"))]
    v, why = _decide(crit, t["n"], min_n, "months")
    return {"criteria": [(x[0], x[1]) for x in crit], "verdict": v, "why": why}


def b6c_rates_tbill_ladder_sgov(archive):
    """T-377: SGOV's monthly total return tracks the compounded DTB3 investment yield (mean within 10 bp, CI inside
    +/-15 bp, SD < 20 bp), 2020-07..2026-09."""
    miss = _missing(archive, [dh("SGOV"), DTB3_B])
    if miss:
        return miss
    sg = _daily(archive, dh("SGOV"))
    dtb3 = _series(archive, DTB3_B)
    t = tracking_difference(sg, dtb3)
    if t["n"] < 8:
        v, why = _decide([("enough months to test", None)], t["n"], T377_MIN_N, "months")
        return _out({"n": t["n"]}, t["n"], v, f"only {t['n']} SGOV months — {why}")
    j = judge_tracking(t)
    fee = tracking_difference(sg, dtb3, fee=T377_FEE)
    partial = tracking_difference(sg, dtb3, start="2020-06")
    if partial["n"] and partial["labels"][0] != "2020-06":
        # SGOV's first bar is 2020-06-01: June 2020 runs from that close (a partial month) to the June close
        days, adj = sg["days"], sg["adj"]
        jun = [i for i, d in enumerate(days) if d[:7] == "2020-06"]
        if jun:
            acc = Accrual(dtb3, "bey")
            d_jun = adj[jun[-1]] / adj[jun[0]] - 1.0 - (acc.growth(days[jun[0]], days[jun[-1]]) - 1.0)
            dd = np.r_[d_jun, partial["bey"]["diff"]]
            partial = {"labels": ["2020-06(partial)"] + partial["labels"], "mean_bp": float(12e4 * dd.mean()), "n": int(dd.size)}
    bil = None
    if _has(archive, dh("BIL")):
        bd = _daily(archive, dh("BIL"))
        b1 = tracking_difference(bd, dtb3)
        b2 = tracking_difference(bd, dtb3, start="2007-07")
        bil = {"same_window_mean_bp": b1["bey"]["mean_bp"], "same_window_sd_bp": b1["bey"]["sd_bp"], "n_same": b1["n"],
               "full_mean_bp": b2["bey"]["mean_bp"], "full_sd_bp": b2["bey"]["sd_bp"], "full_window": [b2["labels"][0], b2["labels"][-1]] if b2["n"] else None}
    slope = None
    if _has(archive, fr("DFF")):
        dff = Asof(_series(archive, fr("DFF")), max_age=7)
        dt = Asof(dtb3, max_age=7)
        diffs = []
        for m in t["labels"]:
            for day in (m + "-15",):
                a, b = dff.at(day), dt.at(day)
                if a is not None and b is not None:
                    diffs.append(a - bey(b))
        slope = float(np.mean(diffs) * 100) if diffs else None
    b, c = t["bey"], t["cont"]
    reason = (f"SGOV month-end adjclose returns {t['labels'][0]}..{t['labels'][-1]} ({t['n']} full months; SGOV's first bar is "
              f"2020-06-01, so June 2020 is partial and left out) minus the DTB3 accrual (print dated before each day): "
              f"investment-yield accrual (the claim's) mean {_bp(b['mean_bp'])}/yr (need |.| < {T377_MEAN_BP:g}), HAC 95% CI "
              f"{_bp(b['ci_bp'][0])} to {_bp(b['ci_bp'][1])} (need inside +/-{T377_CI_BP:g}), SD {_f(b['sd_bp'], 1)} bp/yr (need < "
              f"{T377_SD_BP:g}); rule-7 continuous accrual mean {_bp(c['mean_bp'])}, CI {_bp(c['ci_bp'][0])} to "
              f"{_bp(c['ci_bp'][1])}, SD {_f(c['sd_bp'], 1)}; raw-discount accrual (reported) mean {_bp(t['disc']['mean_bp'])}. "
              f"Reported: with the 9 bp fee added back {_bp(fee['bey']['mean_bp'])}/yr; including partial June 2020 "
              f"{_bp(partial.get('mean_bp') if isinstance(partial, dict) and 'mean_bp' in partial else None)}; BIL over the same "
              f"window {_bp((bil or {}).get('same_window_mean_bp'))} (SD {_f((bil or {}).get('same_window_sd_bp'), 1)}), BIL "
              f"2007-07.. {_bp((bil or {}).get('full_mean_bp'))}; 0-3-month vs 3-month curve: no 1-month bill series is "
              f"archived, the mid-month DFF - BEY(DTB3) proxy averages {_bp(slope)} — " + j["why"])
    stat = {"n_months": t["n"], "window": [t["labels"][0], t["labels"][-1]],
            "bey": {k: b[k] for k in ("mean_bp", "se_bp", "ci_bp", "sd_bp", "lag")},
            "cont": {k: c[k] for k in ("mean_bp", "se_bp", "ci_bp", "sd_bp", "lag")},
            "disc": {k: t["disc"][k] for k in ("mean_bp", "ci_bp", "sd_bp")},
            "fee_added_back_mean_bp": fee["bey"]["mean_bp"], "bil": bil, "dff_minus_bey_bp": slope,
            "monthly_diff_bp": [float(x * 1e4) for x in b["diff"]], "criteria": j["criteria"],
            "rule10": "calendar months named by the claim (rule 10(a))"}
    return _out(stat, t["n"], j["verdict"], reason)


# ============================================================================== T-430 credit carry spread timing ==

T430_START, T430_END, T430_TEST = "2003-01", "2026-09", "2013-01"
T430_MIN_N = 250
T430_SHARPE_THR = 0.3
T430_N_TRIALS = 4
T430_SWITCH = 0.0005
T430_LB = 60
T430_DUR = {"LQD": 8.5, "IEF": 7.5, "HYG": 3.8, "IEI": 4.4}


def credit_timing(px: dict, baa: dict, bills: Bills, start: str = T430_START, end: str = T430_END) -> dict:
    """T-430 engine on LQD's session calendar. Decision month k: BAA10Y = the latest print dated on or before the month's
    last session (published a day later, so it trades at the close of the next session, the fill); on = that print above
    the median of the 60 month-end prints ending with it. Hold fill to fill, labelled by the fill month.
    Base: on -> (LQD - rf) - 8.5/7.5 (IEF - rf), off -> cash - rf (SGOV, BIL, DTB3 accrual); 5 bps per switch.
    Variants: HYG vs 3.8/4.4 IEI; w = clip(z/2, -1, 1) on the 60-month z-score (w x spread + (1 - |w|) cash, 5 bps per
    unit of |dw|); long-only LQD (on) vs IEF (off)."""
    days = px["LQD"]["days"]
    g = month_grid(days)
    P = {s: dict(zip(p["days"], p["adj"])) for s, p in px.items()}
    A = Asof(baa, max_age=10)
    mend = {}
    for d in sorted(baa):
        mend[d[:7]] = baa[d]
    me, ex, ms = g["me"], g["ex"], g["months"]
    rec = {k: [] for k in ("labels", "dec", "f0", "f1", "s", "med", "z", "rf", "cash", "cash_src", "lqd", "ief", "hyg", "iei")}
    for k in range(len(ms) - 1):
        d, f0, f1 = days[me[k]], days[ex[k]], days[ex[k + 1]]
        lab = f0[:7]
        if lab < start or lab > end:
            continue
        s = A.at(d)
        hist = [mend.get(_month_add(d[:7], -j)) for j in range(1, T430_LB)]
        if s is None or any(h is None for h in hist) or "IEF" not in P or f0 not in P["IEF"] or f1 not in P["IEF"]:
            continue
        w60 = np.array(hist + [s], float)
        rf = bills.growth(f0, f1) - 1.0
        cash, src = _cash(P, f0, f1, rf)
        rec["labels"].append(lab)
        rec["dec"].append(d)
        rec["f0"].append(f0)
        rec["f1"].append(f1)
        rec["s"].append(s)
        rec["med"].append(float(np.median(w60)))
        rec["z"].append(float((s - w60.mean()) / w60.std(ddof=1)) if w60.std() > 0 else 0.0)
        rec["rf"].append(rf)
        rec["cash"].append(cash)
        rec["cash_src"].append(src)
        for nm in ("LQD", "IEF", "HYG", "IEI"):
            q = P.get(nm)
            rec[nm.lower()].append(q[f1] / q[f0] - 1.0 if q is not None and f0 in q and f1 in q else np.nan)
    out = {k: (np.array(v, float) if k not in ("labels", "dec", "f0", "f1", "cash_src") else v) for k, v in rec.items()}
    rf, cash_ex = out["rf"], out["cash"] - out["rf"]
    on = (out["s"] > out["med"]).astype(float)
    sw = np.r_[0.0, np.abs(np.diff(on))]
    spread = (out["lqd"] - rf) - T430_DUR["LQD"] / T430_DUR["IEF"] * (out["ief"] - rf)
    base = np.where(on > 0, spread, cash_ex) - T430_SWITCH * sw
    out.update(on=on, spread=spread, ex_base=base, n_switch=int(sw.sum()))
    hy = np.isfinite(out["hyg"]) & np.isfinite(out["iei"])
    ex_hy = np.full(rf.size, np.nan)
    if hy.any():
        sp_h = (out["hyg"][hy] - rf[hy]) - T430_DUR["HYG"] / T430_DUR["IEI"] * (out["iei"][hy] - rf[hy])
        o_h = on[hy]
        ex_hy[hy] = np.where(o_h > 0, sp_h, cash_ex[hy]) - T430_SWITCH * np.r_[0.0, np.abs(np.diff(o_h))]
    out["ex_hyg"] = ex_hy
    w = np.clip(out["z"] / 2.0, -1.0, 1.0)
    out["ex_z"] = w * spread + (1.0 - np.abs(w)) * cash_ex - T430_SWITCH * np.r_[0.0, np.abs(np.diff(w))]
    out["ex_longonly"] = np.where(on > 0, out["lqd"] - rf, out["ief"] - rf) - T430_SWITCH * sw
    return out


def judge_credit_timing(res: dict, min_n: int = T430_MIN_N) -> dict:
    lab = res["labels"]
    fw = _window(lab, T430_START, T430_END)
    tw = _window(lab, T430_TEST, T430_END)
    xf, xt = res["ex_base"][fw], res["ex_base"][tw]
    n = int(fw.sum())
    mf = mean_ci(xf)
    sf = sharpe_ci(xf, T430_SHARPE_THR)
    st = sharpe_ci(xt, 0.0)
    ann = lambda v: None if v is None else 12 * v
    crit = [_pt_row(f"{T430_START}..{T430_END} ({n} months): annualised mean excess return > 0", ann(mf.get("est")), 0.0,
                    [ann(x) if x is not None else None for x in mf.get("ci", [None, None])], _pc),
            _pt_row(f"{T430_START}..{T430_END}: Sharpe > {T430_SHARPE_THR}", sf.get("sharpe"), T430_SHARPE_THR, sf.get("ci")),
            _pt_row(f"{T430_TEST}..{T430_END} ({int(tw.sum())} months): Sharpe > {T430_SHARPE_THR}", st.get("sharpe"),
                    T430_SHARPE_THR, st.get("ci")),
            _ci_crit(st, "gt", 0.0, f"{T430_TEST}..{T430_END}: bootstrap 95% lower bound of the Sharpe > 0")]
    rows = []
    for nm, m in (("test window 2013-2026", tw), ("claim window 2003-2026", fw)):
        fam = [res[k][m] for k in ("ex_base", "ex_hyg", "ex_z", "ex_longonly")]
        fam = [x[np.isfinite(x)] for x in fam]
        rows.append((family_dsr(res["ex_base"][m], _fam(fam), T430_N_TRIALS), f"DSR on the {nm}"))
    crit.append(_dsr_pair(rows, f"DSR > {DSR_PASS} at {T430_N_TRIALS} trials, both windows"))
    v, why = _decide(crit, n, min_n, "months")
    early = _window(lab, T430_START, "2012-12")
    fam_ann = {k: _sr_ann(res[k][tw][np.isfinite(res[k][tw])]) for k in ("ex_base", "ex_hyg", "ex_z", "ex_longonly")}
    return {"n": n, "n_test": int(tw.sum()), "full_mean": mf, "full_sharpe": sf, "test_sharpe": st,
            "dsr_test": rows[0][0], "dsr_full": rows[1][0], "early_sharpe": _sr_ann(res["ex_base"][early]),
            "family_sharpe_ann_test": fam_ann, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _regimes(lab: Sequence[str], x: np.ndarray, spans: dict) -> dict:
    out = {}
    for nm, (a, b) in spans.items():
        m = _window(lab, a, b)
        out[nm] = {"months": int(m.sum()), "total": float(np.prod(1 + x[m]) - 1) if m.any() else None}
    return out


def _t430_inputs(archive) -> tuple:
    px = {s: _daily(archive, dh(s)) for s in ("LQD", "IEF") + tuple(x for x in ("HYG", "IEI") + CASH_ETFS if _has(archive, dh(x)))}
    return px, _series(archive, fr("BAA10Y")), _bills(archive)


def b6c_rates_credit_spread_timing(archive):
    """T-430: LQD minus duration-matched IEF when BAA10Y is above its trailing 60-month median, else cash."""
    miss = _missing(archive, [dh("LQD"), dh("IEF"), fr("BAA10Y"), DTB3_B])
    if miss:
        return miss
    px, baa, bills = _t430_inputs(archive)
    res = credit_timing(px, baa, bills)
    if len(res["labels"]) < 8:
        v, why = _decide([("enough hold months to test", None)], len(res["labels"]), T430_MIN_N, "months")
        return _out({"n": len(res["labels"])}, len(res["labels"]), v, f"only {len(res['labels'])} hold months — {why}")
    j = judge_credit_timing(res)
    lab = res["labels"]
    reg = _regimes(lab, res["ex_base"], {"2008": ("2008-01", "2008-12"), "2020-03": ("2020-03", "2020-03"),
                                         "2022": ("2022-01", "2022-12")})
    on_share = float(res["on"].mean())
    fm, fs, ts = j["full_mean"], j["full_sharpe"], j["test_sharpe"]
    reason = (f"LQD - (8.5/7.5) IEF when the month-end BAA10Y (traded at the next session's close, its publication day) is "
              f"above the median of its last 60 month-end prints, else SGOV/BIL/DTB3 cash; 5 bps per switch "
              f"({res['n_switch']} switches, on in {on_share * 100:.0f}% of months), hold months {lab[0]}..{lab[-1]} "
              f"({j['n']}). Claim window: mean excess {_pc(12 * fm['est'] if fm.get('est') is not None else None)}/yr "
              f"(need > 0; {_ci([12 * x for x in fm['ci']] if fm.get('ci') and None not in fm['ci'] else None, 2, 100, '%')}), "
              f"Sharpe {_f(fs.get('sharpe'))} (need > {T430_SHARPE_THR}; {_ci(fs.get('ci'))}). {T430_TEST}..{T430_END} "
              f"({j['n_test']} months): Sharpe {_f(ts.get('sharpe'))} (need > {T430_SHARPE_THR}), 95% {_ci(ts.get('ci'))} "
              f"(lower bound need > 0). DSR at {T430_N_TRIALS} trials {_f(j['dsr_test']['dsr'])} (2013-2026), "
              f"{_f(j['dsr_full']['dsr'])} (2003-2026). Reported: 2003-2012 Sharpe {_f(j['early_sharpe'])}; test-window variant "
              f"Sharpes " + ", ".join(f"{k[3:]} {_f(v, 2)}" for k, v in j["family_sharpe_ann_test"].items())
              + f"; regimes " + ", ".join(f"{k} {_pc(v['total'])}" for k, v in reg.items()) + " — " + j["why"])
    stat = {"n_months": j["n"], "n_test_months": j["n_test"], "window": [lab[0], lab[-1]], "full_mean_monthly": fm,
            "full_sharpe": fs, "test_sharpe": ts, "dsr_test": j["dsr_test"], "dsr_full": j["dsr_full"],
            "early_sharpe": j["early_sharpe"], "family_sharpe_ann_test": j["family_sharpe_ann_test"], "regimes": reg,
            "on_share": on_share, "n_switch": res["n_switch"], "durations": T430_DUR, "criteria": j["criteria"],
            "last": {"decision": res["dec"][-1], "baa10y": float(res["s"][-1]), "median60": float(res["med"][-1]), "on": bool(res["on"][-1])},
            "rule10": "month-end calendar named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ========================================================================= T-433 global government bond carry ==

T433_CC = ("US", "DE", "GB", "JP", "CA", "AU", "CH", "SE", "NO", "NZ")
T433_CCY = {"US": "USD", "DE": "EUR", "GB": "GBP", "JP": "JPY", "CA": "CAD", "AU": "AUD", "CH": "CHF", "SE": "SEK",
            "NO": "NOK", "NZ": "NZD"}
T433_SID = {cc: f"IRLTLT01{cc}M156N" for cc in T433_CC}
T433_D = 8.0
T433_K = 3
T433_COST = 0.0005
T433_FIT = ("1990-01", "2009-12")
T433_TEST = ("2010-01", "2026-09")
T433_MIN_N = 150
T433_N_TRIALS = 3
T433_CORR_THR = 0.9
T433_SHARPE_THR = 0.3


class Vintages:
    """Real-time values of one monthly ALFRED series: the value of observation month m known at day D is the vintage in
    force at D (realtime_start <= D <= realtime_end); before the series' first vintage a first-vintage value counts from
    its lag_rule_at day (the fetcher's stated look-ahead approximation)."""

    def __init__(self, obs: dict):
        self.obs = obs
        self.first = min((r[0] for rows in obs.values() for r in rows), default="9999-12-31")

    def known(self, m: str, D: str) -> Optional[float]:
        for rs, re, v, fv, lag in self.obs.get(m, ()):
            if v is None:
                continue
            if rs <= D <= re:
                return v
            if fv and D < rs and lag is not None and lag <= D:
                return v
        return None

    def latest(self, D: str, back: int = 13) -> tuple:
        """(observation month, value) of the most recent month known at D (searching ``back`` months before D's month: ALFRED
        recorded no OECD vintage between 2014-02-03 and 2014-11-03, so for decisions in that gap the latest known print is
        up to ten months old; the staleness is reported)."""
        for k in range(1, back + 1):
            m = _month_add(D[:7], -k)
            v = self.known(m, D)
            if v is not None:
                return m, v
        return None, None

    def latest_vintage(self, m: str) -> Optional[float]:
        rows = [r for r in self.obs.get(m, ()) if r[2] is not None]
        return rows[-1][2] if rows else None


def bond_carry(vint: dict, y_out: dict, r3m: dict, months: Sequence[str], k: int = T433_K, timing: str = "pit",
               cost: float = T433_COST, D: float = T433_D) -> dict:
    """T-433 engine. For return month t the synthetic FX-hedged excess return of market i is
    x_i(t) = (y_i(t-1) - r_i(t-1))/1200 - D (y_i(t) - y_i(t-1))/100 on monthly averages (outcomes: ``y_out``, the latest
    vintage; r from ``r3m`` with at most 12 months of forward fill). timing 'pit' (rule 4): the decision is the last day of
    month t-2 and the carry y - r uses each market's latest observation month released by then (``vint``: Vintages);
    'worded': decision at the end of t-1 on month t-2 averages (latest vintage), as the claim's one-month lag reads.
    Long the k highest carry, short the k lowest (equal notional = equal DV01 at a common D), cost per unit traded."""
    labels, gross, net, turn, longs, shorts, stale, obs_lag = [], [], [], [], [], [], [], []
    prev = {}
    xs_us = {}
    for t in months:
        p1, p2 = _month_add(t, -1), _month_add(t, -2)
        car, x = {}, {}
        for cc in T433_CC:
            ccy = T433_CCY[cc]
            yo = y_out.get(cc, {})
            y1, y0 = yo.get(t), yo.get(p1)
            r1, f1 = _rate_at(r3m, ccy, p1)
            if y1 is None or y0 is None or r1 is None:
                continue
            x[cc] = (y0 - r1) / 1200.0 - D * (y1 - y0) / 100.0
            if f1 > 0:
                stale.append((t, cc, f1))
            if timing == "pit":
                Dd = _month_last_day(p2)
                m_star, yv = vint[cc].latest(Dd) if cc in vint else (None, None)
            else:
                m_star, yv = p2, yo.get(p2)
            if m_star is None or yv is None:
                continue
            rr, fk = _rate_at(r3m, ccy, m_star)
            if rr is None:
                continue
            if fk > 0:
                stale.append((t, cc, fk))
            car[cc] = yv - rr
            obs_lag.append((int(t[:4]) * 12 + int(t[5:7])) - (int(m_star[:4]) * 12 + int(m_star[5:7])))
        if "US" in x:
            xs_us[t] = x["US"]
        names = [cc for cc in T433_CC if cc in car and cc in x]
        if len(names) < 2 * k:
            prev = {}
            continue
        order = sorted(names, key=lambda c: (-car[c], T433_CC.index(c)))
        w = {c: 0.0 for c in names}
        for c in order[:k]:
            w[c] = 1.0 / k
        for c in order[-k:]:
            w[c] = -1.0 / k
        tv = sum(abs(w.get(c, 0.0) - prev.get(c, 0.0)) for c in set(w) | set(prev)) if prev else 0.0
        gr = sum(w[c] * x[c] for c in names)
        labels.append(t)
        gross.append(gr)
        net.append(gr - cost * tv)
        turn.append(tv)
        longs.append(order[:k])
        shorts.append(order[-k:])
        prev = w
    return {"labels": labels, "gross": np.array(gross, float), "net": np.array(net, float), "turnover": np.array(turn, float),
            "long": longs, "short": shorts, "stale": stale, "x_us": xs_us,
            "obs_lag_months": {"mean": float(np.mean(obs_lag)) if obs_lag else None,
                               "max": int(max(obs_lag)) if obs_lag else None}}


def ief_monthly_excess(ief: dict, bills: Bills) -> tuple:
    """({month: IEF month-end to month-end excess return}, {month: excess return on monthly-average prices})."""
    days, adj = ief["days"], np.asarray(ief["adj"], float)
    last, avg = {}, {}
    for i, d in enumerate(days):
        last[d[:7]] = i
        avg.setdefault(d[:7], []).append(adj[i])
    me, av = {}, {}
    ms = sorted(last)
    for a, b in zip(ms[:-1], ms[1:]):
        i0, i1 = last[a], last[b]
        if i1 + 1 >= len(days):
            continue
        g = bills.growth(days[i0], days[i1]) - 1.0
        me[b] = adj[i1] / adj[i0] - 1.0 - g
        av[b] = float(np.mean(avg[b]) / np.mean(avg[a]) - 1.0 - g)
    return me, av


def ief_midmonth_excess(ief: dict, bills: Bills) -> dict:
    """{month t: IEF excess return from the last session on or before the 15th of t-1 to that of t} (reported only: the
    window centred where the averaged synthetic return of month t puts its weight)."""
    days, adj = ief["days"], np.asarray(ief["adj"], float)
    mids = {}
    for i, d in enumerate(days):
        if int(d[8:10]) <= 15:
            mids[d[:7]] = i
    out = {}
    ms = sorted(mids)
    for a, b in zip(ms[:-1], ms[1:]):
        if _month_add(a, 1) != b:
            continue
        i0, i1 = mids[a], mids[b]
        out[b] = adj[i1] / adj[i0] - 1.0 - (bills.growth(days[i0], days[i1]) - 1.0)
    return out


def _t433_inputs(archive) -> tuple:
    vint, y_out = {}, {}
    for cc, sid in T433_SID.items():
        v = Vintages(_alfred(archive, sid))
        vint[cc] = v
        yo = dict(_monthly_series(archive, fr(sid)))
        for m in v.obs:                      # outcomes: latest vintage; the ALFRED vintage when FRED's row is not yet available
            if m not in yo:
                lv = v.latest_vintage(m)
                if lv is not None:
                    yo[m] = lv
        y_out[cc] = yo
    return vint, y_out, _rates3m(archive)


def judge_bond_carry(res: dict, corr: dict, fam: dict, min_n: int = T433_MIN_N) -> dict:
    lab = res["labels"]
    tw = _window(lab, *T433_TEST)
    x = res["net"][tw]
    n = int(tw.sum())
    st = sharpe_ci(x, 0.0)
    crit = [_pt_row(f"test {T433_TEST[0]}.. ({n} months): Sharpe > {T433_SHARPE_THR}", st.get("sharpe"), T433_SHARPE_THR, st.get("ci")),
            _ci_crit(st, "gt", 0.0, "bootstrap 95% lower bound of the Sharpe > 0"),
            _pt_row(f"US synthetic vs IEF actual monthly excess return: correlation > {T433_CORR_THR} ({corr.get('n')} months)",
                    corr.get("r"), T433_CORR_THR, corr.get("ci"))]
    d = family_dsr(x, _fam(fam.values()), T433_N_TRIALS)
    crit.append(dsr_row(d, f"DSR > {DSR_PASS} at {T433_N_TRIALS} trials"))
    v, why = _decide(crit, n, min_n, "months")
    return {"n": n, "test": st, "dsr": d, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_rates_global_bond_carry(archive):
    """T-433: 10-market 10y-minus-3m bond carry, long top 3 / short bottom 3 on the approximate FX-hedged excess return."""
    need = [al(s) for s in T433_SID.values()] + [fr(s) for s in T433_SID.values()] + [RATES_B, dh("IEF"), DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    vint, y_out, r3m = _t433_inputs(archive)
    months = _months("1990-01", T433_TEST[1])
    res = bond_carry(vint, y_out, r3m, months)
    worded = bond_carry(vint, y_out, r3m, months, timing="worded")
    top2 = bond_carry(vint, y_out, r3m, months, k=2)
    tw = _window(res["labels"], *T433_TEST)
    if tw.sum() < 8:
        v, why = _decide([("enough test months", None)], int(tw.sum()), T433_MIN_N, "months")
        return _out({"n": int(tw.sum())}, int(tw.sum()), v, f"only {int(tw.sum())} test months with >= 6 markets — {why}")
    me, av = ief_monthly_excess(_daily(archive, dh("IEF")), _bills(archive))
    tm = [m for m in res["x_us"] if T433_TEST[0] <= m <= T433_TEST[1] and m in me]
    corr = corr_ci([res["x_us"][m] for m in tm], [me[m] for m in tm])
    corr_avg = corr_ci([res["x_us"][m] for m in tm if m in av], [av[m] for m in tm if m in av])
    mid = ief_midmonth_excess(_daily(archive, dh("IEF")), _bills(archive))
    corr_mid = corr_ci([res["x_us"][m] for m in tm if m in mid], [mid[m] for m in tm if m in mid])
    t2 = _window(top2["labels"], *T433_TEST)
    fam = {"top3": res["net"][tw], "top2": top2["net"][t2]}
    j = judge_bond_carry(res, corr, fam)
    fw = _window(res["labels"], *T433_FIT)
    ww = _window(worded["labels"], *T433_TEST)
    wst = sharpe_one(worded["net"][ww]) if ww.sum() >= 8 else {}
    reg = _regimes(res["labels"], res["net"], {"negative rates 2014-2021": ("2014-01", "2021-12"), "2022": ("2022-01", "2022-12")})
    stale_t = {}
    for (tt, cc, f) in res["stale"]:
        if T433_TEST[0] <= tt:
            a_, b_, f_ = stale_t.get(cc, (tt, tt, 0))
            stale_t[cc] = (min(a_, tt), max(b_, tt), max(f_, f))
    stale_txt = ", ".join(f"{cc} in {a_}..{b_} (up to {f_} months)" for cc, (a_, b_, f_) in sorted(stale_t.items())) or "none"
    lab = [l for l, m in zip(res["labels"], tw) if m]
    t = j["test"]
    end_note = ""
    if lab[-1] < T433_TEST[1]:
        cap = str(getattr(archive.get(fr(T433_SID["US"])), "created_at", "") or "")[:16]
        end_note = (f"; the window ends {lab[-1]}, not {T433_TEST[1]}: the later OECD monthly values are stamped available "
                    f"(ALFRED realtime_start, end of day) after the bundles' capture ({cap} UTC), so the house filter leaves "
                    f"them out")
    reason = (f"Synthetic FX-hedged excess return (y10(t-1) - r3m(t-1))/12 - 8 (y10(t) - y10(t-1)) on OECD monthly averages, "
              f"long top 3 / short bottom 3 of 10 markets on 10y - 3m carry, 5 bps per unit traded; decision at the end of month "
              f"t-2 on the OECD prints released by then (ALFRED; mean observation lag {_f(res['obs_lag_months']['mean'], 1)} "
              f"months before the return month, at most {res['obs_lag_months']['max']}; pre-2013-06 by the 45-day lag rule). Test {lab[0]}..{lab[-1]} ({j['n']} months): "
              f"Sharpe {_f(t.get('sharpe'))} (need > {T433_SHARPE_THR}), 95% {_ci(t.get('ci'))} (lower need > 0); US synthetic "
              f"vs IEF month-end excess return correlation {_f(corr.get('r'))} over {corr.get('n')} months (Fisher {_ci(corr.get('ci'))}; "
              f"need > {T433_CORR_THR}; reported: against IEF's monthly-average-price return {_f(corr_avg.get('r'))}, its "
              f"mid-month to mid-month return {_f(corr_mid.get('r'))}); DSR at "
              f"{T433_N_TRIALS} trials {_f(j['dsr']['dsr'])} (family top 3, top 2; the 10y-2y roll-down variant is not "
              f"computable: OECD MEI has no 2-year yields). Reported: as-worded timing (decision at the end of t-1 on t-2 "
              f"averages) Sharpe {_f(wst.get('sharpe'))}; top 2 {_f(_sr_ann(top2['net'][t2]))}; 1990-2009 in-sample "
              f"{_f(_sr_ann(res['net'][fw]))} ({int(fw.sum())} months); " + ", ".join(f"{k} {_pc(v['total'])}" for k, v in reg.items())
              + f"; stale 3-month rates forward-filled (EUR/GBP end 2026-01, JPY 2026-07): {stale_txt}" + end_note + " — " + j["why"])
    stat = {"n_months": j["n"], "window": [lab[0], lab[-1]], "test": t, "dsr": j["dsr"], "corr_us_ief": corr,
            "corr_us_ief_avgprice": corr_avg, "worded_timing_sharpe": wst.get("sharpe"), "top2_sharpe": _sr_ann(top2["net"][t2]),
            "fit_window_sharpe": _sr_ann(res["net"][fw]), "fit_window_months": int(fw.sum()), "regimes": reg,
            "obs_lag_months": res["obs_lag_months"], "stale_rates_test": {k: list(v) for k, v in stale_t.items()},
            "corr_us_ief_midmonth": corr_mid,
            "last_book": {"month": res["labels"][-1], "long": res["long"][-1], "short": res["short"][-1]},
            "duration": T433_D, "criteria": j["criteria"],
            "rule10": "calendar months named by the claim; rule 4 sets the decision before the averaging window"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================== T-432 equity-country dividend carry ==

T432_ETFS = {"SPY": "USD", "EWA": "AUD", "EWC": "CAD", "EWD": "SEK", "EWG": "EUR", "EWI": "EUR", "EWJ": "JPY",
             "EWK": "EUR", "EWL": "CHF", "EWN": "EUR", "EWO": "EUR", "EWP": "EUR", "EWQ": "EUR", "EWU": "GBP"}
T432_DROPPED = {"EWH": "Hong Kong", "EWS": "Singapore", "EWM": "Malaysia"}
T432_K = 4
T432_COST = 0.0010
T432_BORROW = 0.0050
T432_FIT = ("1997-01", "2010-12")
T432_TEST = ("2011-01", "2026-09")
T432_MIN_N = 150
T432_N_TRIALS = 4
T432_SHARPE_THR = 0.3
T432_VOL_N = 60


def country_panel(series: dict, divs: dict, rates: dict, ccys: dict, start: str, end: str, lag: int = 1,
                  spot: Optional[dict] = None) -> dict:
    """Monthly panel on the union session calendar. Decision k = the month's last session close; fill = the next session
    close; hold fill to fill (labelled by the fill month). Per ETF: dividend yield = cash dividends with ex-date in the
    365 days to the decision / the decision close (split-adjusted close and dividends), once the ETF has a year of
    history; local rate = the 3-month rate of the month ``lag`` months before the decision month (<= 12 months of fill);
    60-session volatility of daily log adjclose returns through the decision; the hold return. ``spot`` (fx-spot-g10)
    adds FX-hedged hold returns (minus the spot return and the lagged rate differential over the hold days)."""
    syms = list(series)
    master = sorted(set().union(*[set(series[s]["days"]) for s in syms]))
    idx = {d: i for i, d in enumerate(master)}
    Dn, N = len(master), len(syms)
    A, Cl = np.full((Dn, N), np.nan), np.full((Dn, N), np.nan)
    for i, s in enumerate(syms):
        p = series[s]
        for d, a, c in zip(p["days"], p["adj"], p["close"]):
            A[idx[d], i], Cl[idx[d], i] = a, c
    L = np.log(A)
    first = [(_ord(series[s]["days"][0]) if series[s]["days"] else 10 ** 9) for s in syms]
    dv = {s: (sorted(divs.get(s, {})), np.cumsum([0.0] + [divs[s][x] for x in sorted(divs.get(s, {}))])) for s in syms}
    sp = {c: Asof(v, max_age=7) for c, v in (spot or {}).items()}
    g = month_grid(master)
    me, ex, ms = g["me"], g["ex"], g["months"]
    rows = []
    stale = set()
    for k in range(len(ms) - 1):
        f0, f1 = master[ex[k]], master[ex[k + 1]]
        lab = f0[:7]
        if lab < start or lab > end:
            continue
        d = master[me[k]]
        od = _ord(d)
        rm = _month_add(d[:7], -lag)
        ru, _fu = _rate_at(rates, "USD", rm)
        car, tcar, vol, R, RH, dy = (np.full(N, np.nan) for _ in range(6))
        for i, s in enumerate(syms):
            c = Cl[me[k], i]
            a0, a1 = A[ex[k], i], A[ex[k + 1], i]
            if not (np.isfinite(c) and np.isfinite(a0) and np.isfinite(a1)) or first[i] > od - 365:
                continue
            keys, cum = dv[s]
            lo = bisect.bisect_right(keys, (date.fromordinal(od - 365)).isoformat())
            hi = bisect.bisect_right(keys, d)
            y = float(cum[hi] - cum[lo]) / c
            ccy = ccys[s]
            r, fk = _rate_at(rates, ccy, rm)
            w = L[me[k] - T432_VOL_N:me[k] + 1, i] if me[k] >= T432_VOL_N else np.array([np.nan])
            if r is None or ru is None or not np.isfinite(w).all():
                continue
            if fk > 0:
                stale.add((ccy, rm, fk))
            dy[i] = y
            car[i] = y - r / 100.0
            tcar[i] = y - ru / 100.0
            vol[i] = float(np.diff(w).std(ddof=1))
            R[i] = a1 / a0 - 1.0
            if ccy == "USD":
                RH[i] = R[i]
            elif ccy in sp:
                s0, s1 = sp[ccy].at(f0), sp[ccy].at(f1)
                if s0 and s1:
                    RH[i] = R[i] - (s1 / s0 - 1.0 + (r - ru) / 100.0 * (_ord(f1) - _ord(f0)) / 365.0)
        rows.append((lab, d, f0, f1, car, tcar, vol, R, RH, dy))
    T = len(rows)
    pick = lambda j: np.array([r[j] for r in rows], float).reshape(T, N)
    return {"syms": syms, "labels": [r[0] for r in rows], "dec": [r[1] for r in rows], "f0": [r[2] for r in rows],
            "f1": [r[3] for r in rows], "carry": pick(4), "tcarry": pick(5), "vol": pick(6), "R": pick(7), "R_hedged": pick(8),
            "dy": pick(9), "hold_days": np.array([_ord(r[3]) - _ord(r[2]) for r in rows], float), "stale": sorted(stale)}


def country_book(P: dict, score: str = "carry", k: int = T432_K, weighting: str = "equal", ret: str = "R",
                 cost: float = T432_COST, borrow: float = T432_BORROW) -> dict:
    """Long the k highest scores, short the k lowest among eligible ETFs (finite score, volatility and hold return):
    equal 1/k per leg or inverse-volatility within each leg; a zero-investment book with ``cost`` per side on drift-adjusted
    turnover and ``borrow`` a year on the short notional (``book``). Months with fewer than 2k names hold nothing."""
    S, R, V = P[score], P[ret], P["vol"]
    T, N = S.shape
    W = np.zeros((T, N))
    has = np.zeros(T, bool)
    for t in range(T):
        elig = np.isfinite(S[t]) & np.isfinite(R[t]) & np.isfinite(V[t]) & (V[t] > 0)
        w = rank_weights(S[t], elig, k)
        if not w.any():
            continue
        if weighting == "invvol":
            for sg in (1.0, -1.0):
                m = w * sg > 0
                iv = 1.0 / V[t, m]
                w[m] = sg * iv / iv.sum()
        W[t] = w
        has[t] = True
    b = book(W, R, np.full(N, cost), borrow=np.full(N, borrow), hold_days=P["hold_days"])
    lab = [l for l, h in zip(P["labels"], has) if h]
    return {"labels": lab, "net": b["net"][has], "gross": b["gross"][has], "cost": b["cost"][has], "borrow": b["borrow"][has],
            "turnover": b["turnover"][has], "W": W[has], "n_names": (np.isfinite(S) & np.isfinite(R)).sum(axis=1)[has]}


def choose_weighting(P: dict, fit: tuple = T432_FIT) -> dict:
    """Walk-forward choice of the leg weighting on the fit window by net Sharpe (ties keep equal weights)."""
    out = {}
    for wt in ("equal", "invvol"):
        b = country_book(P, weighting=wt)
        m = _window(b["labels"], *fit)
        out[wt] = {"sharpe": _sr_ann(b["net"][m]), "months": int(m.sum())}
    best = "invvol" if (out["invvol"]["sharpe"] is not None and out["equal"]["sharpe"] is not None
                        and out["invvol"]["sharpe"] > out["equal"]["sharpe"]) else "equal"
    return {"chosen": best, "fit": out}


def judge_country_carry(base: dict, fam: dict, min_n: int = T432_MIN_N, test: tuple = T432_TEST) -> dict:
    tw = _window(base["labels"], *test)
    x = base["net"][tw]
    n = int(tw.sum())
    st = sharpe_ci(x, 0.0)
    crit = [_pt_row(f"test {test[0]}.. ({n} months): net Sharpe > {T432_SHARPE_THR}", st.get("sharpe"), T432_SHARPE_THR, st.get("ci")),
            _ci_crit(st, "gt", 0.0, "bootstrap 95% lower bound of the Sharpe > 0")]
    d = family_dsr(x, _fam(fam.values()), T432_N_TRIALS)
    crit.append(dsr_row(d, f"DSR > {DSR_PASS} at {T432_N_TRIALS} trials"))
    v, why = _decide(crit, n, min_n, "months")
    return {"n": n, "test": st, "dsr": d, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _t432_inputs(archive) -> tuple:
    series = {s: _daily(archive, dh(s)) for s in T432_ETFS}
    divs = {}
    for s in T432_ETFS:
        if s == "SPY" and not _has(archive, de("SPY")):
            p = series["SPY"]
            D = spy_dividends(p["close"], p["adj"])
            divs[s] = {d: float(x) for d, x in zip(p["days"], D) if x > 0}
        else:
            divs[s] = _divs(archive, s)
    spot = _spot(archive) if _has(archive, SPOT_B) else None
    return series, divs, _rates3m(archive), spot


def b6c_rates_equity_country_carry(archive):
    """T-432: long top-4 / short bottom-4 country ETFs on trailing dividend yield minus the lagged local 3-month rate."""
    need = [dh(s) for s in T432_ETFS] + [de(s) for s in T432_ETFS if s != "SPY"] + [RATES_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    series, divs, rates, spot = _t432_inputs(archive)
    P = country_panel(series, divs, rates, T432_ETFS, T432_FIT[0], T432_TEST[1], spot=spot)
    sel = choose_weighting(P)
    wt = sel["chosen"]
    base = country_book(P, weighting=wt)
    tw = _window(base["labels"], *T432_TEST)
    if tw.sum() < 8:
        v, why = _decide([("enough test months", None)], int(tw.sum()), T432_MIN_N, "months")
        return _out({"n": int(tw.sum())}, int(tw.sum()), v, f"only {int(tw.sum())} test months with >= 8 ETFs — {why}")
    tot = country_book(P, score="tcarry", weighting=wt)
    top3 = country_book(P, k=3, weighting=wt)
    hed = country_book(P, weighting=wt, ret="R_hedged") if spot is not None else None
    win = lambda b: b["net"][_window(b["labels"], *T432_TEST)]
    fam = {"base": win(base), "total_carry_usd": win(tot), "top3": win(top3), "fx_hedged": win(hed) if hed else None}
    fam = {k: v for k, v in fam.items() if v is not None}
    j = judge_country_carry(base, fam)
    lag2 = country_book(country_panel(series, divs, rates, T432_ETFS, T432_TEST[0], T432_TEST[1], lag=2), weighting=wt)
    eq = country_book(P, weighting="equal" if wt == "invvol" else "invvol")
    lab = [l for l, m in zip(base["labels"], tw) if m]
    reg = _regimes(base["labels"], base["net"], {"2008": ("2008-01", "2008-12"), "euro crisis 2011-12": ("2011-01", "2012-12"),
                                                 "2020": ("2020-01", "2020-12")})
    stale_t = [s for s in P["stale"] if s[1] >= T432_TEST[0]]
    sg = {}
    for c, m_, f_ in stale_t:
        a_, b_, ff = sg.get(c, (m_, m_, 0))
        sg[c] = (min(a_, m_), max(b_, m_), max(ff, f_))
    stale_txt = ", ".join(f"{c} rate months {a_}..{b_} (up to {ff} months)" for c, (a_, b_, ff) in sorted(sg.items())) or "none"
    dbc = None
    if _has(archive, DBC_B):
        dp = _daily(archive, DBC_B)
        q = dict(zip(dp["days"], dp["adj"]))
        mp = {l: (q[b] / q[a] - 1.0 if a in q and b in q else np.nan) for l, a, b in zip(P["labels"], P["f0"], P["f1"])}
        dbc = corr_ci(base["net"][tw], [mp.get(l, np.nan) for l in lab])
    t = j["test"]
    reason = (f"{len(T432_ETFS)} ETFs (SPY + 13 country ETFs; {', '.join(f'{k} ({v})' for k, v in T432_DROPPED.items())} dropped: "
              f"no OECD 3-month rate on FRED, as the claim allows), carry = trailing-12-month dividends / month-end close - "
              f"the local 3-month rate one month earlier (EZ for the euro members), long top 4 / short bottom 4, filled at the "
              f"next close, 10 bps per side + 50 bps/yr borrow; leg weighting chosen on {T432_FIT[0]}..{T432_FIT[1]}: {wt} "
              f"(fit Sharpe equal {_f(sel['fit']['equal']['sharpe'])} vs inverse-60-day-vol {_f(sel['fit']['invvol']['sharpe'])}). "
              f"Test {lab[0]}..{lab[-1]} ({j['n']} months): net Sharpe {_f(t.get('sharpe'))} (need > {T432_SHARPE_THR}), 95% "
              f"{_ci(t.get('ci'))} (lower need > 0), DSR {_f(j['dsr']['dsr'])} at {T432_N_TRIALS} trials. Reported: variant "
              f"Sharpes " + ", ".join(f"{k} {_f(_sr_ann(v), 2)}" for k, v in fam.items())
              + f"; other weighting {_f(_sr_ann(win(eq)))}; two-month rate lag {_f(_sr_ann(lag2['net']))}; mean turnover "
                f"{_f(float(base['turnover'][tw].mean()), 2)}/month, costs {_pc(float((base['cost'][tw] + base['borrow'][tw]).mean() * 12))}/yr; "
              + ", ".join(f"{k} {_pc(v['total'])}" for k, v in reg.items())
              + f"; correlation with DBC {_f((dbc or {}).get('r'))}; SPY dividends read from its adjclose/close steps (no "
                f"daily-events-SPY); stale rates forward-filled: {stale_txt} — " + j["why"])
    stat = {"n_months": j["n"], "window": [lab[0], lab[-1]], "test": t, "dsr": j["dsr"], "weighting": sel,
            "family_sharpe_ann": {k: _sr_ann(v) for k, v in fam.items()}, "other_weighting_sharpe": _sr_ann(win(eq)),
            "rate_lag2_sharpe": _sr_ann(lag2["net"]), "regimes": reg, "corr_dbc": dbc, "universe": T432_ETFS,
            "dropped": T432_DROPPED, "stale_rates": [list(s) for s in stale_t], "criteria": j["criteria"],
            "last_book": {"month": base["labels"][-1], "long": [P["syms"][i] for i in np.flatnonzero(base["W"][-1] > 0)],
                          "short": [P["syms"][i] for i in np.flatnonzero(base["W"][-1] < 0)]},
            "rule10": "month-end calendar named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], reason)


# ========================================================================= T-474 Treasury butterfly reversion ==

T474_START, T474_END = "2008-01-01", "2026-09-30"
T474_WIN = 250
T474_ENTRY = 2.0
T474_MAX_HOLD = 60
T474_DUR = {"SHY": 1.9, "IEI": 4.4, "IEF": 7.3}
T474_COST = 0.0003             # per leg per fill
T474_BORROW = 0.0030
T474_MIN_N = 30
T474_N_TRIALS = 4
T474_SHIFT = 60
T474_LEGS = {"IEI": 1.0, "SHY": -(T474_DUR["IEI"] / 2.0) / T474_DUR["SHY"], "IEF": -(T474_DUR["IEI"] / 2.0) / T474_DUR["IEF"]}


def fly_series(ylds: dict, kind: str = "fixed", win: int = T474_WIN, incl: bool = True) -> tuple:
    """(dates, z) of the 2s5s10s signal on the days all three yields print. 'fixed': fly = 2 DGS5 - DGS2 - DGS10, z over
    the trailing ``win`` observations including the current (``incl=False``: the ``win`` before it, a reported
    sensitivity); 'pca': the third principal component (curvature, positive 5-year loading) of the trailing ``win``
    yield levels, its current score over the window's score sd."""
    ds = sorted(set(ylds["DGS2"]) & set(ylds["DGS5"]) & set(ylds["DGS10"]))
    Y = np.array([[ylds["DGS2"][d], ylds["DGS5"][d], ylds["DGS10"][d]] for d in ds], float).reshape(-1, 3)
    z = np.full(len(ds), np.nan)
    if kind == "fixed":
        f = 2 * Y[:, 1] - Y[:, 0] - Y[:, 2]
        c1, c2 = np.r_[0.0, np.cumsum(f)], np.r_[0.0, np.cumsum(f * f)]
        sh = 0 if incl else 1
        for t in range(win - 1 + sh, len(ds)):
            hi = t + 1 - sh
            s1, s2 = c1[hi] - c1[hi - win], c2[hi] - c2[hi - win]
            m = s1 / win
            v = (s2 - win * m * m) / (win - 1)
            z[t] = (f[t] - m) / math.sqrt(v) if v > 1e-12 else np.nan
    else:
        for t in range(win - 1, len(ds)):
            X = Y[t - win + 1:t + 1]
            Xc = X - X.mean(axis=0)
            _, vecs = np.linalg.eigh(Xc.T @ Xc / (win - 1))
            v3 = vecs[:, 0]
            if v3[1] < 0:
                v3 = -v3
            sc = Xc @ v3
            sd = sc.std(ddof=1)
            z[t] = sc[-1] / sd if sd > 1e-12 else np.nan
    return ds, z


def fly_trades(px: dict, zd: Sequence[str], zv: np.ndarray, bills: Bills, start: str = T474_START, end: str = T474_END,
               skip: Optional[set] = None, entry: float = T474_ENTRY, max_hold: int = T474_MAX_HOLD) -> dict:
    """T-474 simulation on the sessions where SHY, IEI and IEF all trade. The z known at session s is the latest print dated
    strictly before s (FRED posts the H.15 curve a day late). Flat and |z| > 2 at s (s within [start, end], not in
    ``skip``): enter at the close of s, long the belly (z > 2) or the wings (z < -2), DV01-neutral with a 50/50 split
    (T474_LEGS). Exit at the close of the first later session where z has crossed 0 or 60 sessions after entry; re-entry
    from the next session. Net per trade (per unit of belly notional) = sum of leg excess returns - 3 bps per leg at entry
    and at exit - 30 bps/yr on the short notional. A trade still open at the data's end is dropped (reported)."""
    P = {s: dict(zip(px[s]["days"], px[s]["adj"])) for s in T474_LEGS}
    sess = sorted(set(P["SHY"]) & set(P["IEI"]) & set(P["IEF"]))
    N = len(sess)
    A = {s: np.array([P[s][d] for d in sess], float) for s in T474_LEGS}
    o = np.array([_ord(d) for d in sess], np.int64)
    Bc = np.array([math.log(bills.growth(sess[0], d)) for d in sess], float) if N else np.zeros(0)
    zpos = [bisect.bisect_left(zd, s) - 1 for s in sess]
    trades, state, e = [], 0, -1
    for j, s in enumerate(sess):
        zj = zv[zpos[j]] if zpos[j] >= 0 else np.nan
        if state != 0:
            if (state > 0 and zj <= 0) or (state < 0 and zj >= 0) or (j - e >= max_hold):
                trades.append((e, j, state))
                state = 0
            continue
        if s < start or s > end or not np.isfinite(zj) or (skip and s in skip):
            continue
        if zj > entry:
            state, e = 1, j
        elif zj < -entry:
            state, e = -1, j
    open_trade = (sess[e], state) if state != 0 else None
    out = {"sess": sess, "A": A, "o": o, "Bc": Bc, "trades": trades, "open_trade": open_trade}
    out.update(_trade_pnl(out, trades))
    return out


def _trade_pnl(sim: dict, trades: Sequence[tuple], shift: int = 0) -> dict:
    """Per-trade net returns of ``trades`` (entry, exit, sign) on the simulation's prices, shifted ``shift`` sessions
    against the returns (circularly, with a zero-return wrap) for the block-shift null; the daily sleeve when unshifted."""
    A, Bc, o = sim["A"], sim["Bc"], sim["o"]
    N = len(o)
    gross_cost = 2.0 * T474_COST * sum(abs(w) for w in T474_LEGS.values())
    if shift:
        Ax = {s: np.concatenate([a, a * (a[-1] / a[0])]) for s, a in A.items()}
        Bx = np.concatenate([Bc, Bc + (Bc[-1] - Bc[0])])
    else:
        Ax, Bx = A, Bc
    net, gross, days = [], [], []
    for e, x, sg in trades:
        e2, x2 = (e + shift) % N if shift else e, ((e + shift) % N + (x - e)) if shift else x
        g = math.exp(Bx[x2] - Bx[e2]) - 1.0
        gr = sum(sg * w * (Ax[s][x2] / Ax[s][e2] - 1.0 - g) for s, w in T474_LEGS.items())
        shortn = sum(max(-sg * w, 0.0) for w in T474_LEGS.values())
        nd = int(o[x] - o[e])
        net.append(gr - gross_cost - T474_BORROW * shortn * nd / 365.0)
        gross.append(gr)
        days.append(nd)
    res = {"net": np.array(net, float), "gross": np.array(gross, float), "days": np.array(days, float)}
    if shift == 0:
        daily = np.zeros(N)
        for e, x, sg in trades:
            shortn = sum(max(-sg * w, 0.0) for w in T474_LEGS.values())
            ge = np.exp(Bc[e:x + 1] - Bc[e]) - 1.0
            val = sum(sg * w * (A[s][e:x + 1] / A[s][e] - 1.0 - ge) for s, w in T474_LEGS.items())
            daily[e + 1:x + 1] += np.diff(val) - T474_BORROW * shortn * np.diff(o[e:x + 1]) / 365.0
            daily[e] -= gross_cost / 2.0
            daily[x] -= gross_cost / 2.0
        res["daily"] = daily
    return res


def block_shift_null(sim: dict, step: int = T474_SHIFT) -> dict:
    """The trial's null: the position path shifted against the returns by every multiple of ``step`` sessions (trade
    count, lengths, signs and costs kept); p = (1 + #{shifted mean >= observed}) / (1 + shifts)."""
    N = len(sim["o"])
    obs = float(sim["net"].mean()) if sim["net"].size else None
    means = []
    for k in range(1, max(1, N // step)):
        r = _trade_pnl(sim, sim["trades"], shift=k * step)
        if r["net"].size:
            means.append(float(r["net"].mean()))
    means = np.array(means, float)
    p = float((1 + np.sum(means >= obs)) / (1 + means.size)) if obs is not None and means.size else None
    return {"obs": obs, "p": p, "n_shifts": int(means.size), "null_mean": float(means.mean()) if means.size else None,
            "null_q95": float(np.quantile(means, 0.95)) if means.size else None}


def judge_butterfly(sim: dict, fam_trade: dict, fam_daily: dict, full_window: bool, min_n: int = T474_MIN_N) -> dict:
    x = sim["net"]
    n = int(x.size)
    bt = mc_escalate(lambda seed: _stud(_mean_stat, [x], 1, N_BOOT, seed), lambda t: _ci_crit(t, "gt", 0.0, "")[1], REPS, SEED) \
        if n >= 8 else {"est": float(x.mean()) if n else None, "ci": [None, None]}
    bs = block_shift_null(sim) if n else {"p": None}
    ok_bs = None if bs.get("p") is None else bs["p"] < ALPHA
    pc_ = lambda v: _pc(v, 3)
    crit = [all_constructions([_ci_crit(bt, "gt", 0.0, "studentized bootstrap of trades: 95% lower bound > 0", pc_),
                               (f"60-session block-shift null p < 0.05 (p {_f(bs.get('p'), 3)} over {bs.get('n_shifts')} shifts; "
                                f"null 95th pct {_pc(bs.get('null_q95'), 3)})", ok_bs, bs.get("p") is not None and bs["p"] >= 0.95)],
                              f"mean net return per trade > 0 ({_pc(bt.get('est'), 3)})"),
            (f"at least {min_n} trades ({n})", n >= min_n, full_window)]
    d_t = family_dsr(x, _fam(fam_trade.values()), T474_N_TRIALS)
    d_d = family_dsr(sim["daily"], _fam(fam_daily.values()), T474_N_TRIALS)
    crit.append(_dsr_pair([(d_t, "DSR of the per-trade net returns"), (d_d, "DSR of the daily sleeve")],
                          f"DSR > {DSR_PASS} at {T474_N_TRIALS} variants, both readings"))
    v, why = _decide(crit, n, min_n, "trades")
    return {"n": n, "boot": bt, "block_shift": bs, "dsr_trade": d_t, "dsr_daily": d_d,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _fomc_weeks(archive) -> Optional[set]:
    if not _has(archive, FOMC_B):
        return None
    wk = set()
    for r in _rows(archive, FOMC_B):
        d = r["value"].get("decision_day")
        if d:
            y, w, _ = date.fromisoformat(d).isocalendar()
            wk.add((y, w))
    return wk


def b6c_rates_treasury_butterfly(archive):
    """T-474: SHY/IEI/IEF DV01-neutral butterfly on |z| > 2 of the FRED 2s5s10s fly."""
    need = [dh("SHY"), dh("IEI"), dh("IEF"), fr("DGS2"), fr("DGS5"), fr("DGS10"), DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    px = {s: _daily(archive, dh(s)) for s in T474_LEGS}
    ylds = {sid: _series(archive, fr(sid)) for sid in ("DGS2", "DGS5", "DGS10")}
    bills = _bills(archive)
    zd, zv = fly_series(ylds, "fixed")
    sim = fly_trades(px, zd, zv, bills)
    if sim["net"].size == 0:
        v, why = _decide([("trades to test", None)], 0, T474_MIN_N, "trades")
        return _out({"n": 0}, 0, v, f"no butterfly trades in {T474_START}..{T474_END} — {why}")
    pd_, pz = fly_series(ylds, "pca")
    pca = fly_trades(px, pd_, pz, bills)
    xd, xz = fly_series(ylds, "fixed", incl=False)
    excl = fly_trades(px, xd, xz, bills)
    wk = _fomc_weeks(archive)
    fomc = None
    if wk is not None:
        skip = {s for s in sim["sess"] if tuple(date.fromisoformat(s).isocalendar()[:2]) in wk}
        fomc = fly_trades(px, zd, zv, bills, skip=skip)
    fam_t = {"fixed_2s5s10s": sim["net"], "pca": pca["net"], "skip_fomc": fomc["net"] if fomc else None}
    fam_d = {"fixed_2s5s10s": sim["daily"], "pca": pca["daily"], "skip_fomc": fomc["daily"] if fomc else None}
    fam_t = {k: v for k, v in fam_t.items() if v is not None}
    fam_d = {k: v for k, v in fam_d.items() if v is not None}
    sess = sim["sess"]
    full_window = bool(sess and sess[0] <= T474_START and sess[-1] >= T474_END and zd and zd[0] < "2007-01-01")
    j = judge_butterfly(sim, fam_t, fam_d, full_window)
    tr = sim["trades"]
    ent = [sess[e] for e, _, _ in tr]
    per = lambda a, b: [v for v, d in zip(sim["net"], ent) if a <= d <= b]
    zlb, post = per("2009-01-01", "2015-12-31"), per("2022-03-01", "9999")
    inc = 0 < (sim["daily"] != 0).sum()
    # residual exposure: daily sleeve on the change in the yield level and the 10s-2s slope (in-trade sessions)
    Yl = {sid: Asof(v, max_age=7) for sid, v in ylds.items()}
    lev = np.array([np.mean([Yl[s].at(d) or np.nan for s in ("DGS2", "DGS5", "DGS10")]) for d in sess], float)
    slo = np.array([(Yl["DGS10"].at(d) or np.nan) - (Yl["DGS2"].at(d) or np.nan) for d in sess], float)
    intr = np.zeros(len(sess), bool)
    for e, x, _ in tr:
        intr[e + 1:x + 1] = True
    dl, ds_ = np.r_[np.nan, np.diff(lev)], np.r_[np.nan, np.diff(slo)]
    m = intr & np.isfinite(dl) & np.isfinite(ds_)
    reg = ols_nw(sim["daily"][m], np.column_stack([dl[m], ds_[m]]), 5) if m.sum() > 10 else {"coef": None}
    hold = [x - e for e, x, _ in tr]
    long_belly = sum(1 for *_, sg in tr if sg > 0)
    bt, bs = j["boot"], j["block_shift"]
    reason = (f"fly = 2 DGS5 - DGS2 - DGS10, z over its trailing 250 prints, known the session after each print; |z| > 2 -> "
              f"long IEI / short SHY and IEF (z > 2) or the reverse, DV01-neutral 50/50 (SHY 1.9, IEI 4.4, IEF 7.3), enter "
              f"at the close, exit at the z zero-cross or after 60 sessions; 3 bps per leg at entry and exit + 30 bps/yr "
              f"borrow. {j['n']} trades {ent[0]}..{ent[-1]} ({long_belly} long belly; median hold {int(np.median(hold))} "
              f"sessions{'; the trade opened ' + sim['open_trade'][0] + ' is still open at the data end and is dropped' if sim['open_trade'] else ''}): mean net "
              f"{_pc(bt.get('est'), 3)} per trade (95% {_ci(bt.get('ci'), 4, 100, '%')}; block-shift p {_f(bs.get('p'), 3)}); "
              f"DSR at {T474_N_TRIALS} variants {_f(j['dsr_trade']['dsr'])} (per trade), {_f(j['dsr_daily']['dsr'])} (daily "
              f"sleeve, annualised Sharpe {_f(_sr_ann(sim['daily'], 252), 2)}); variants: PCA {pca['net'].size} trades mean "
              f"{_pc(float(pca['net'].mean()) if pca['net'].size else None, 3)}, skip-FOMC "
              f"{(fomc['net'].size if fomc else 'n/a')} trades mean {_pc(float(fomc['net'].mean()) if fomc and fomc['net'].size else None, 3)}, "
              f"5s10s30s not computable (DGS30 not archived). Reported: z window excluding the current print "
              f"{excl['net'].size} trades mean {_pc(float(excl['net'].mean()) if excl['net'].size else None, 3)}; ZLB 2009-2015 {len(zlb)} trades mean "
              f"{_pc(float(np.mean(zlb)) if zlb else None, 3)}, post-2022 {len(post)} trades mean "
              f"{_pc(float(np.mean(post)) if post else None, 3)}; residual exposure per 1 pp (level, slope) "
              f"{', '.join(_s(c, 4) for c in (reg.get('coef') or [None, None, None])[1:])} (NW t "
              f"{', '.join(_s(c, 2) for c in (reg.get('t') or [None, None, None])[1:])}) — " + j["why"])
    stat = {"n_trades": j["n"], "first_entry": ent[0], "last_entry": ent[-1], "boot": bt, "block_shift": bs,
            "dsr_trade": j["dsr_trade"], "dsr_daily": j["dsr_daily"], "daily_sharpe_ann": _sr_ann(sim["daily"], 252),
            "trades": [{"entry": sess[e], "exit": sess[x], "sign": int(sg), "net": float(v)} for (e, x, sg), v in zip(tr, sim["net"])],
            "variants": {"pca": {"n": int(pca["net"].size), "mean": float(pca["net"].mean()) if pca["net"].size else None},
                         "skip_fomc": {"n": int(fomc["net"].size), "mean": float(fomc["net"].mean()) if fomc["net"].size else None} if fomc else None,
                         "5s10s30s": "not computable: fred-DGS30 not archived",
                         "z_excluding_current": {"n": int(excl["net"].size),
                                                 "mean": float(excl["net"].mean()) if excl["net"].size else None}},
            "zlb_2009_2015": {"n": len(zlb), "mean": float(np.mean(zlb)) if zlb else None},
            "post_2022": {"n": len(post), "mean": float(np.mean(post)) if post else None}, "exposure": reg,
            "open_trade_dropped": sim["open_trade"], "legs": T474_LEGS, "criteria": j["criteria"],
            "rule10": "signal-driven entries and exits (no grid)", "any_activity": bool(inc)}
    return _out(stat, j["n"], j["verdict"], reason)


# ========================================================================== T-381 cross-asset carry composite ==

T381_TEST = ("2013-01", "2026-09")
T381_MIN_N = 150
T381_TARGET = 0.05
T381_LB = 36
T381_DD = 0.10
T381_SHARPE_THR = 0.6
T381_LB_THR = 0.2
T381_SLEEVE_TRIALS = {"T-368 fx-carry-g10-retail": 6, "T-431 em-fx-carry": 4, "T-433 global-government-bond-carry": 3,
                      "T-432 equity-country-dividend-carry": 4, "T-430 credit-carry-spread-timing": 4,
                      "T-362 crypto-cme-cash-and-carry": 10}
T381_N_TRIALS = 3 + sum(T381_SLEEVE_TRIALS.values())                          # 34
T381_N_TRIALS_EX_CRYPTO = T381_N_TRIALS - T381_SLEEVE_TRIALS["T-362 crypto-cme-cash-and-carry"]   # 24


T381_BONDS = "global bonds (T-433)"
T381_LAG = {T381_BONDS: 1}     # T-433's x(t) is built on monthly averages: its window opens at the start of t-1 (rule 4)


def carry_composite(sleeves: dict, start: str = T381_TEST[0], end: str = T381_TEST[1], target: float = T381_TARGET,
                    lb: int = T381_LB, derisk: bool = False, dd: float = T381_DD, lag: Optional[dict] = None) -> dict:
    """Equal-risk composite of monthly sleeve excess returns ({name: {month: return}}): each sleeve scaled to ``target``
    annualised volatility with the sd of its ``lb`` months before the month (trailing only), summed. A month counts only
    when every sleeve has it and its full trailing window. ``derisk``: exposure halved in a month when the composite's
    drawdown over its trailing 3 months exceeds ``dd``.

    ``lag`` ({sleeve: L}, rule 4): a sleeve whose month-t return window opens L months before month t is decided at the
    end of month t-1-L, so its weight uses the sd of the ``lb`` months ending t-1-L and its de-risking the composite's
    drawdown on the composite months through t-1-L. 'halved' lists the months the unlagged sleeves were halved,
    'halved_lag' those a lagged sleeve was."""
    names = list(sleeves)
    lag = {s: int(v) for s, v in (lag or {}).items() if s in sleeves and int(v) > 0}
    lab, ret, wts, dropped, halved, halved_lag = [], [], [], [], [], []
    path = [(None, 1.0)]                       # (composite month, wealth after it)

    def in_drawdown(t: str, L: int) -> bool:
        cut = _month_add(t, -1 - L)
        w = [v for mo, v in path if mo is None or mo <= cut]
        return len(w) >= 2 and w[-1] / max(w[-4:]) - 1.0 < -dd

    for t in _months(start, end):
        ws, ok = {}, True
        for s in names:
            ser, L = sleeves[s], lag.get(s, 0)
            past = [ser.get(_month_add(t, -j)) for j in range(1 + L, lb + 1 + L)]
            if ser.get(t) is None or any(p is None for p in past):
                ok = False
                break
            sd = float(np.std(past, ddof=1)) * math.sqrt(PPY)
            ws[s] = target / sd if sd > 0 else 0.0
        if not ok:
            dropped.append(t)
            continue
        h = {L: (derisk and in_drawdown(t, L)) for L in {0, *lag.values()}}
        r = sum((0.5 if h[lag.get(s, 0)] else 1.0) * ws[s] * sleeves[s][t] for s in names)
        if h[0]:
            halved.append(t)
        if any(h[L] for L in lag.values()):
            halved_lag.append(t)
        path.append((t, path[-1][1] * (1.0 + r)))
        lab.append(t)
        ret.append(r)
        wts.append(ws)
    return {"labels": lab, "ret": np.array(ret, float), "weights": wts, "dropped": dropped, "halved": halved,
            "halved_lag": halved_lag, "lag": lag}


def judge_composite(comp: dict, comp_dr: dict, fam: dict, min_n: int = T381_MIN_N) -> dict:
    n = int(comp["ret"].size)
    rows, tests = [], {}
    for nm, c in (("equal-risk composite (the claim)", comp), ("with the rule's drawdown de-risking", comp_dr)):
        t = sharpe_ci(c["ret"], T381_LB_THR)
        tests[nm] = t
        rows.append((_pt_row(f"{nm}: Sharpe > {T381_SHARPE_THR}", t.get("sharpe"), T381_SHARPE_THR, t.get("ci")),
                     _ci_crit(t, "gt", T381_LB_THR, f"{nm}: bootstrap 95% lower bound > {T381_LB_THR}")))
    crit = [all_constructions([rows[0][0], rows[1][0]], f"point Sharpe > {T381_SHARPE_THR}, both books"),
            all_constructions([rows[0][1], rows[1][1]], f"bootstrap lower bound > {T381_LB_THR}, both books")]
    fs = _fam(fam.values())
    d = family_dsr(comp["ret"], fs, T381_N_TRIALS)
    d24 = family_dsr(comp["ret"], fs, T381_N_TRIALS_EX_CRYPTO)
    crit.append(_dsr_pair([(d, f"DSR at {T381_N_TRIALS} trials (3 + every sleeve trial incl. the crypto basis)"),
                           (d24, f"DSR at {T381_N_TRIALS_EX_CRYPTO} trials (without the crypto sleeve's)")],
                          f"DSR > {DSR_PASS} at 3 + every sleeve trial"))
    v, why = _decide(crit, n, min_n, "months")
    return {"n": n, "tests": tests, "dsr": d, "dsr_ex_crypto": d24, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _fx_books(archive, months: Sequence[str]) -> dict:
    """The T-368 and T-431 sleeve books (batch5_fx, walk-forward weights and filter frozen on 2002-05..2012-12) over
    ``months``: {name: {month: net}}."""
    panel = fxm.build_panel(fxm._values(archive, fxm.SPOT_BUNDLE), fxm._values(archive, fxm.RATE_BUNDLE), fill_to=months[-1])
    vix = fxm._vix(archive) if _has(archive, VIX_B) else None
    out = {}
    for nm, uni, (cb, ad) in (("fx_g10", fxm.G10, fxm.g10_costs()), ("fx_em", list(fxm.G10) + list(fxm.EM), fxm.em_costs())):
        sel = fxm.choose_weighting(panel, uni, fxm.CARRY_TRAIN, cb, ad, vix=vix)
        vf = vix if sel["filter"] == fxm.VIX_FILTER else None
        bt = fxm.carry_backtest(panel, uni, months, weighting=sel["chosen"], cost_bps=cb, admin=ad, vix=vf)
        out[nm] = {"series": dict(zip(bt["months"], [float(x) for x in bt["net"]])), "book": sel["chosen_book"]}
    return out


def b6c_rates_cross_asset_carry(archive):
    """T-381: equal-risk composite of the FX, global-bond, equity-country and credit carry sleeves, 2013-01..2026-09.
    Rule 4: the bond sleeve's month-t return (T-433's synthetic x(t) on OECD monthly averages) opens at the start of t-1,
    so its volatility weight (trailing 36 months ending t-2) and its drawdown halving are set at the end of t-2
    (T381_LAG); the other sleeves' windows open at their month-end fills and are weighted at the end of t-1."""
    need = ([SPOT_B, RATES_B, DTB3_B, dh("IEF"), dh("LQD"), fr("BAA10Y")] + [al(s) for s in T433_SID.values()]
            + [fr(s) for s in T433_SID.values()] + [dh(s) for s in T432_ETFS] + [de(s) for s in T432_ETFS if s != "SPY"])
    miss = _missing(archive, need)
    if miss:
        return miss
    warm = _month_add(T381_TEST[0], -T381_LB)
    fx = _fx_books(archive, _months(warm, T381_TEST[1]))
    vint, y_out, r3m = _t433_inputs(archive)
    bonds = bond_carry(vint, y_out, r3m, _months(_month_add(warm, -max(T381_LAG.values())), T381_TEST[1]))
    series, divs, rates, spot = _t432_inputs(archive)
    P = country_panel(series, divs, rates, T432_ETFS, T432_FIT[0], T381_TEST[1])
    wt = choose_weighting(P)["chosen"]
    eq = country_book(P, weighting=wt)
    px, baa, bills = _t430_inputs(archive)
    cr = credit_timing(px, baa, bills, start=warm, end=T381_TEST[1])
    fxs = {}
    for m in set(fx["fx_g10"]["series"]) & set(fx["fx_em"]["series"]):
        fxs[m] = 0.5 * (fx["fx_g10"]["series"][m] + fx["fx_em"]["series"][m])
    sleeves = {"FX (mean of the T-368 and T-431 books)": fxs,
               T381_BONDS: dict(zip(bonds["labels"], [float(x) for x in bonds["net"]])),
               "equity-country (T-432)": dict(zip(eq["labels"], [float(x) for x in eq["net"]])),
               "credit (T-430)": dict(zip(cr["labels"], [float(x) for x in cr["ex_base"]]))}
    comp = carry_composite(sleeves, lag=T381_LAG)
    comp_dr = carry_composite(sleeves, derisk=True, lag=T381_LAG)
    if comp["ret"].size < 8:
        v, why = _decide([("enough composite months", None)], int(comp["ret"].size), T381_MIN_N, "months")
        return _out({"n": int(comp["ret"].size), "dropped": comp["dropped"]}, int(comp["ret"].size), v,
                    f"only {comp['ret'].size} composite months with every sleeve and 36 trailing months — {why}")
    lab = comp["labels"]
    sl_test = {k: np.array([v[m] for m in lab], float) for k, v in sleeves.items()}
    fam = {"composite": comp["ret"], "composite_derisk": comp_dr["ret"],
           **{"sleeve " + k: v for k, v in sl_test.items()},
           "fx_g10": np.array([fx["fx_g10"]["series"].get(m, np.nan) for m in lab]),
           "fx_em": np.array([fx["fx_em"]["series"].get(m, np.nan) for m in lab])}
    fam = {k: v[np.isfinite(v)] for k, v in fam.items()}
    j = judge_composite(comp, comp_dr, fam)
    sl_sr = {k: _sr_ann(v) for k, v in sl_test.items()}
    div_gain = (j["tests"]["equal-risk composite (the claim)"].get("sharpe") or 0.0) - float(np.mean([v for v in sl_sr.values() if v is not None]))
    alts = {}
    for nm, sub in (("FX = G10 only", {"FX": fx["fx_g10"]["series"]}), ("FX = G10+EM book only", {"FX": fx["fx_em"]["series"]}),
                    ("G10 and EM as two sleeves", {"G10": fx["fx_g10"]["series"], "EM": fx["fx_em"]["series"]})):
        s2 = {k: v for k, v in sleeves.items() if not k.startswith("FX")}
        s2.update(sub)
        alts[nm] = _sr_ann(carry_composite(s2, lag=T381_LAG)["ret"])
    rec = None
    if _has(archive, USREC_B):
        us = _monthly_series(archive, USREC_B)
        rm = [i for i, m in enumerate(lab) if us.get(m) == 1.0]
        rec = {"months": [lab[i] for i in rm], "composite_total": float(np.prod(1 + comp["ret"][rm]) - 1) if rm else None}
    maxw = {k.split(" (")[0]: float(max(w[k] for w in comp["weights"])) for k in sleeves}
    worst = int(np.argmin(comp["ret"]))
    sr_wo_worst = _sr_ann(np.delete(comp["ret"], worst))
    corr = np.corrcoef(np.array(list(sl_test.values())))
    names = list(sl_test)
    mean_corr = float(np.mean([corr[a, b] for a in range(len(names)) for b in range(a + 1, len(names))]))
    t0, t1 = j["tests"]["equal-risk composite (the claim)"], j["tests"]["with the rule's drawdown de-risking"]
    reason = (f"Composite of 4 carry sleeves (FX = mean of the T-368 G10 and T-431 G10+MXN+ZAR books with their frozen "
              f"walk-forward weights; T-433 bonds; T-432 country ETFs ({wt} weights); T-430 credit), each scaled to 5% a year "
              f"by its trailing 36-month sd, summed (rule 4: the bond sleeve's x(t) is built on monthly averages, so its "
              f"weight uses the 36 months ending t-2 and its halving the drawdown at the end of t-2; the other sleeves' "
              f"weights use the 36 months ending t-1); {lab[0]}..{lab[-1]} ({j['n']} months{', dropped ' + str(len(comp['dropped'])) if comp['dropped'] else ''}): "
              f"Sharpe {_f(t0.get('sharpe'))} (need > {T381_SHARPE_THR}), 95% {_ci(t0.get('ci'))} (lower need > {T381_LB_THR}); "
              f"with the rule's 3-month 10% drawdown halving ({len(comp_dr['halved'])} months halved, the bond sleeve "
              f"{len(comp_dr['halved_lag'])}) Sharpe "
              f"{_f(t1.get('sharpe'))}, {_ci(t1.get('ci'))}; DSR {_f(j['dsr']['dsr'])} at {T381_N_TRIALS} trials "
              f"({_f(j['dsr_ex_crypto']['dsr'])} at {T381_N_TRIALS_EX_CRYPTO} without the crypto sleeve's 10). Reported: sleeve "
              f"Sharpes " + ", ".join(f"{k.split(' (')[0]} {_f(v, 2)}" for k, v in sl_sr.items())
              + f"; diversification gain over the average sleeve {_s(div_gain, 2)}; mean pairwise sleeve correlation "
                f"{_f(mean_corr, 2)}; FX-sleeve alternatives " + ", ".join(f"{k} {_f(v, 2)}" for k, v in alts.items())
              + f"; largest trailing-volatility weight per sleeve " + ", ".join(f"{k} {v:.2f}" for k, v in maxw.items())
              + f" (a timing sleeve that sat in cash has a small trailing sd and a large weight); worst month {lab[worst]} "
                f"{_pc(float(comp['ret'][worst]))}, Sharpe without it {_f(sr_wo_worst)}"
              + f"; NBER recession months in the window {len((rec or {}).get('months', []))} (composite "
                f"{_pc((rec or {}).get('composite_total'))}); the crypto basis sleeve (T-362, from 2018) is not in the claim's "
                f"composite and is not computed; FX weights were chosen on 2002-05..2012-12, which overlaps the 2010-2012 "
                f"volatility warm-up only — " + j["why"])
    stat = {"n_months": j["n"], "window": [lab[0], lab[-1]], "tests": j["tests"], "dsr": j["dsr"],
            "dsr_ex_crypto": j["dsr_ex_crypto"], "n_trials": T381_N_TRIALS, "sleeve_trials": T381_SLEEVE_TRIALS,
            "sleeve_sharpe_ann": sl_sr, "diversification_gain": div_gain, "mean_sleeve_corr": mean_corr,
            "fx_alternatives_sharpe": alts, "fx_books": {k: v["book"] for k, v in fx.items()}, "equity_weighting": wt,
            "halved_months": comp_dr["halved"], "halved_months_bond_sleeve": comp_dr["halved_lag"],
            "sleeve_decision_lag_months": comp["lag"], "dropped_months": comp["dropped"], "nber": rec, "max_weight": maxw,
            "worst_month": {"month": lab[worst], "ret": float(comp["ret"][worst]), "sharpe_without": sr_wo_worst},
            "last_weights": comp["weights"][-1], "criteria": j["criteria"],
            "rule10": "calendar months of the sleeves (each sleeve's calendar is named by its claim)"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_rates_treasury_carry_rolldown": b6c_rates_treasury_carry_rolldown,
    "b6c_rates_tbill_ladder_sgov": b6c_rates_tbill_ladder_sgov,
    "b6c_rates_cross_asset_carry": b6c_rates_cross_asset_carry,
    "b6c_rates_credit_spread_timing": b6c_rates_credit_spread_timing,
    "b6c_rates_global_bond_carry": b6c_rates_global_bond_carry,
    "b6c_rates_treasury_butterfly": b6c_rates_treasury_butterfly,
    "b6c_rates_equity_country_carry": b6c_rates_equity_country_carry,
}

THEORY_MAP = {
    "T-373": "b6c_rates_treasury_carry_rolldown",
    "T-377": "b6c_rates_tbill_ladder_sgov",
    "T-381": "b6c_rates_cross_asset_carry",
    "T-430": "b6c_rates_credit_spread_timing",
    "T-433": "b6c_rates_global_bond_carry",
    "T-474": "b6c_rates_treasury_butterfly",
    "T-432": "b6c_rates_equity_country_carry",
}
