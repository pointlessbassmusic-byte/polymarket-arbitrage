"""
Batch 5, macro announcement days: release-day premium, the FOMC implied/realised move filter, GLD event straddles and
the triple-witching straddle.
======================================================================================================================

Four library claims (T-343, T-208, T-224, T-219) tested on archived daily data. Each test follows the claim and its
trial.pass as worded.

Calendars.
  * FOMC: ``decision_day`` of the scheduled meetings in ``fomc-meetings`` (federalreserve.gov). The schedule is published
    about a year ahead, so flagging a scheduled decision day at the previous close uses no future information.
  * CPI and Employment Situation: ALFRED vintage dates of CPIAUCSL and PAYEMS (``macro-release-cpi``,
    ``macro-release-employment-situation``; 08:30 ET releases). A few vintages are not releases. BLS publishes revised
    CPI seasonal factors a few days before the January CPI, so when two CPI vintages fall in February at most 7 days
    apart the earlier one is dropped. Any other vintage that comes less than 14 days after the previous kept vintage is
    a correction and is dropped (2000-09-28 CPI; 2002-12-09, 2003-10-10, 2020-05-11 Employment Situation). Releases
    that BLS delayed (1996, October 2013, autumn 2025 shutdowns) keep the actual release day and are flagged: a kept
    release more than 40 or fewer than 20 days after the previous one, or one in October-November 2013 or
    October-December 2025. Release schedules are published a year ahead; a delayed date was announced before it
    happened.
  * A release on a day SPY/GLD did not trade (an Employment Situation on Good Friday) is assigned to the next session,
    whose close-to-close return is the first to contain it. The count is reported.
  * Triple witching = third Friday of March, June, September and December. A witching Friday that is not a trading day
    (2008-03-21, Good Friday) or whose Thursday is not the previous trading day is skipped and counted.

Day-flagged tests (T-343, T-224, T-219). A series x_t with event flag f_t is turned into d_t = diff + w_t (x_t - m_g(t)),
w_t = 1/p on event days and -1/(1-p) otherwise (p = share of event days, m_g the group mean). mean(d) is the
event-minus-other difference exactly, and resampling d in circular blocks gives the sampling spread of the difference
while keeping autocorrelation and volatility clustering. p-values come from the studentized block bootstrap
(``block_bootstrap_pvalue``); CIs are block-bootstrap percentile intervals (``_mean_ci``), two-sided 95%. "CI excluding 0"
means the whole interval lies on the claimed side.

Model-priced straddles (T-208, T-224, T-219): Black-Scholes, ATM strike = the T-1 close, sigma = index(T-1)/100 (VIX for
SPY, GVZ for GLD), T = 1/252, r = q = 0 (the rate moves a 1-day ATM straddle by under 0.1 bp; T-219 adds the ex-date
dividend, below). Settlement is |S_T - S_T-1|. P&L is in fraction of the T-1 spot. Every such result is labelled
MODEL-PRICED: a 30-day index cannot see the event premium that traded event-expiry options carry.

Dividends (T-219). SPY goes ex-dividend on the quarterly triple-witching Friday itself, so the raw Thursday-to-Friday
move on those Fridays contains a known, pre-announced drop (about 44 bps). The T-219 straddle keeps K = S_Thu and the
settlement |S_Fri - S_Thu| on raw closes, but is priced on the dividend forward F = S_Thu (1 - D/S_Thu) (escrowed-dividend
Black-Scholes), so the known drop is in the premium as well as the payoff. D/S_Thu is read from the step in the
adjclose/close ratio on the ex-date (Yahoo multiplies every earlier close by 1 - D/S_Thu). SPY's ex-dates are fixed in
the trust's distribution schedule and the amount passes through dividends the constituents have already declared, so
it is treated as known at Thursday's close; the previous ex-date's yield as the forecast is reported as a sensitivity.
The |r|/(VIX/sqrt252) control uses the dividend-neutral move |S_Fri - F|/S_Thu.

Costs follow each claim: T-343 charges 2 bps (the top of its 1-2 bps) per round trip, one per run of consecutive
release days. The straddle claims state no cost. Equity annualisation uses 252 trading days; T-343's Sharpe by day type
annualises each type by the square root of its own days per year (about 31 release days, 221 other days), and the
release-only strategy (flat otherwise) by sqrt(252).

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not
implemented -> at best inconclusive; supported only when every criterion is implemented and passes. When the data
cannot support the claim (no events, missing bundle) the verdict is inconclusive with the reason.

House rule 5 (``_rule5``). Below the trial's min_n, counted in the claim's own units (T-343 release days, T-208 FOMC
events with IM and HM, T-224 FOMC/CPI days, T-219 witching Fridays), the unmet 'n >= trial min_n' criterion keeps the
verdict from supported, and a failing criterion still counts only when it fails decisively: its 95% interval lies
wholly on the wrong side of the claimed bound (a block-bootstrap CI of the event-minus-other difference, the bootstrap
CI of T-208's Q1-Q5 difference, or a Fisher-z interval of T-208's Spearman rho). A one-sided p < 0.05 criterion is
mirrored at the same level, not by a two-sided 95% interval (a one-sided 97.5% bound): it decides when the same test
run in the opposite direction on the same draws gives p < 0.05 (T-343 the studentized block-bootstrap p for H0
diff >= 0; T-208 the permutation p for H0 rho <= 0; T-219 the label-permutation p for H0 witching >= other); those
mirrored p-values are reported in ``rule5`` and the reason. An interval or test from fewer than 4 events (per group
for T-208's quintiles), from fewer than 4 blocks of days, or an interval of zero width decides nothing. Any other
failure there is undecided (None), so the verdict is inconclusive. At or above min_n every criterion is judged at face
value, exactly as before. Below min_n the report's ``rule5`` holds the face-value and judged criteria and the decisive
failures.

House rule 10 (no arbitrary grid phase). No harness here rests on a non-overlapping cycle grid. T-343 and T-224 are
daily series (every trading day, flagged on scheduled FOMC / CPI / Employment Situation dates); T-208 is an event study
on the scheduled FOMC decision days; T-219 compares calendar-named days (quarterly third Fridays against all other
Fridays). Every date is fixed by a published or computed calendar, so there is no start offset to choose.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.underlying2 import _mean_ci, _verdict, load_series
from mandel.experiments.volatility import index_closes
from mandel.options import bs
from mandel.validation.backtest_eval import block_bootstrap_pvalue

EQ_PPY = 252
TAU_1D = 1.0 / EQ_PPY
MEDIAN_MOVE_FACTOR = 0.845          # median |N(0,s)| / mean |N(0,s)| = 0.6745 / 0.7979
WITCHING_MONTHS = (3, 6, 9, 12)
SHUTDOWN_WINDOWS = (("2013-10-01", "2013-11-30"), ("2025-10-01", "2025-12-31"))


# ------------------------------------------------------------------------------------------------ data access --

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
    except KeyError:
        return False


def _capture(archive, name: str):
    e = archive.get(name)
    return getattr(e, "created_at", None) if e is not None else None


def _available(archive, name: str):
    cap = _capture(archive, name)
    return (r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap))


def _index(archive, name: str) -> dict[str, float]:
    """{day: close} of an index bundle, keeping only rows available when the bundle was captured."""
    return _cached(archive, ("index", name), lambda: index_closes(_available(archive, name)))


def _prices(archive, symbol: str, adjusted: bool):
    return _cached(archive, ("px", symbol, adjusted), lambda: load_series(archive, symbol, adjusted=adjusted))


def _opens(archive, symbol: str) -> dict[str, float]:
    """{day: open} from the daily OHLC bundle (split-adjusted, like ``close``)."""
    from datetime import datetime, timezone

    def load():
        out = {}
        for r in _available(archive, "daily-history-" + symbol):
            v = r["value"]
            if v.get("open") is not None:
                out[datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")] = float(v["open"])
        return out
    return _cached(archive, ("open", symbol), load)


def scheduled_decision_days(rows, scheduled_only: bool = True) -> list[str]:
    """Sorted FOMC decision days from ``fomc-meetings`` rows (or bare value dicts)."""
    out = set()
    for r in rows:
        v = r.get("value", r)
        if scheduled_only and not v.get("scheduled"):
            continue
        out.add(v["decision_day"])
    return sorted(out)


def _fomc(archive) -> list[str]:
    return _cached(archive, ("fomc",), lambda: scheduled_decision_days(archive.load("fomc-meetings")))


def _fomc_unscheduled(archive) -> list[str]:
    def load():
        rows = list(archive.load("fomc-meetings"))
        return sorted(set(scheduled_decision_days(rows, scheduled_only=False)) - set(scheduled_decision_days(rows)))
    return _cached(archive, ("fomc-unscheduled",), load)


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return {"missing_bundles": miss}, 0, "inconclusive", f"missing data bundles {miss}: the claim cannot be tested until they are archived"
    return None


def _clean(x):
    """JSON-safe copy (numpy scalars/arrays to Python)."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_clean(v) for v in (sorted(x) if isinstance(x, set) else x)]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _wrap(rep: dict, nkey: str = "n"):
    rep = _clean(rep)
    return rep, int(rep.get(nkey) or 0), rep["verdict"], rep["reason"]


# ------------------------------------------------------------------------------------------------- calendars --

def _d(s: str) -> date:
    return date.fromisoformat(s)


def clean_release_days(days: Sequence[str], kind: str, min_gap: int = 14, feb_gap: int = 7) -> tuple[list[str], list[str]]:
    """(kept release days, dropped vintages) from sorted ALFRED vintage dates. A CPI vintage followed by another within
    ``feb_gap`` days in February is the seasonal-factor revision and is dropped in favour of the later (the January CPI
    release). Any other vintage less than ``min_gap`` days after the previous kept one is a correction and is dropped."""
    keep: list[str] = []; dropped: list[str] = []
    for d in sorted(set(days)):
        if keep:
            gap = (_d(d) - _d(keep[-1])).days
            if gap < min_gap:
                if kind == "cpi" and gap <= feb_gap and d[5:7] == "02" and keep[-1][5:7] == "02":
                    dropped.append(keep[-1]); keep[-1] = d
                else:
                    dropped.append(d)
                continue
        keep.append(d)
    return keep, dropped


def delayed_release_flags(release_days: Sequence[str], windows=SHUTDOWN_WINDOWS, lo: int = 20, hi: int = 40) -> list[str]:
    """Kept releases with irregular spacing (fewer than ``lo`` or more than ``hi`` days after the previous release) or
    inside a named shutdown window: delayed or catch-up releases, flagged."""
    ds = sorted(release_days); out = []
    for i, d in enumerate(ds):
        gap = (_d(d) - _d(ds[i - 1])).days if i else None
        if (gap is not None and (gap < lo or gap > hi)) or any(a <= d <= b for a, b in windows):
            out.append(d)
    return out


def release_days_from_rows(rows, kind: str) -> tuple[list[str], list[str]]:
    """Kept release days and dropped vintages from ``macro-release-*`` rows (or bare value dicts)."""
    return clean_release_days([r.get("value", r)["day"] for r in rows], kind)


def to_sessions(event_days: Sequence[str], trading_days: Sequence[str]) -> tuple[list[str], int]:
    """Map each event day to the first trading day on or after it (the first close-to-close return containing an 08:30
    ET release). Events after the last trading day are dropped. Returns (sorted sessions, number of events moved)."""
    arr = np.asarray(trading_days); out = set(); moved = 0
    if len(arr) == 0:
        return [], 0
    for e in event_days:
        if e < arr[0] or e > arr[-1]:
            continue
        j = int(np.searchsorted(arr, e, side="left"))
        out.add(str(arr[j])); moved += int(arr[j] != e)
    return sorted(out), moved


def third_friday(year: int, month: int) -> str:
    d = date(year, month, 1)
    return (d + timedelta(days=(4 - d.weekday()) % 7 + 14)).isoformat()


def third_fridays(first_year: int, last_year: int, months=tuple(range(1, 13))) -> list[str]:
    return [third_friday(y, m) for y in range(first_year, last_year + 1) for m in months]


# ------------------------------------------------------------------------------------------- statistics core --

def _range_mask(ds: np.ndarray, start: Optional[str], end: Optional[str]) -> np.ndarray:
    m = np.ones(len(ds), dtype=bool)
    if start:
        m &= ds >= start
    if end:
        m &= ds <= end
    return m


def _returns(days: Sequence[str], closes, start: Optional[str] = None, end: Optional[str] = None):
    """(day array, simple return ending on that day) restricted to [start, end]."""
    c = np.asarray(closes, dtype=float)
    r = c[1:] / c[:-1] - 1
    ds = np.array(days[1:])
    m = _range_mask(ds, start, end)
    return ds[m], r[m]


def flag_diff_series(x, flag) -> np.ndarray:
    """Day-flagged series whose mean is mean(x[flag]) - mean(x[~flag]) and whose block-resampled mean has the
    within-group sampling spread of that difference (see the module docstring)."""
    x = np.asarray(x, dtype=float); f = np.asarray(flag, dtype=bool)
    p = f.mean()
    me, mo = x[f].mean(), x[~f].mean()
    w = np.where(f, 1.0 / p, -1.0 / (1.0 - p))
    return (me - mo) + w * (x - np.where(f, me, mo))


def group_diff(x, flag, block: int = 10, n_boot: int = 2000, seed: int = 0) -> dict:
    """Event-minus-other difference in means with a two-sided 95% block-bootstrap CI and studentized one-sided p-values
    (p_greater: H0 diff <= 0; p_less: H0 diff >= 0)."""
    x = np.asarray(x, dtype=float); f = np.asarray(flag, dtype=bool)
    ne, no = int(f.sum()), int((~f).sum())
    out = {"n_event": ne, "n_other": no, "mean_event": float(x[f].mean()) if ne else None, "mean_other": float(x[~f].mean()) if no else None,
           "diff": None, "ci": [None, None], "p_greater": None, "p_less": None}
    if ne < 2 or no < 2 or len(x) < 8:
        return out
    d = flag_diff_series(x, f)
    lo, hi = _mean_ci(d, block, n_boot, seed)
    z = np.zeros_like(d)
    out.update(diff=float(d.mean()), ci=[lo, hi],
               p_greater=float(block_bootstrap_pvalue(d, z, n_boot=n_boot, block_len=block, seed=seed)),
               p_less=float(block_bootstrap_pvalue(-d, z, n_boot=n_boot, block_len=block, seed=seed)))
    return out


def _point_diff(x, f) -> Optional[float]:
    x = np.asarray(x, dtype=float); f = np.asarray(f, dtype=bool)
    if f.sum() == 0 or (~f).sum() == 0:
        return None
    return float(x[f].mean() - x[~f].mean())


def _holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1]); m = len(items); out = {}; run = 0.0
    for k, (name, p) in enumerate(items):
        run = max(run, min(1.0, (m - k) * p)); out[name] = run
    return out


def _bps(x) -> str:
    return "n/a" if x is None else f"{x * 1e4:+.1f}"


def _ci_bps(ci) -> str:
    return "n/a" if ci[0] is None else f"{ci[0] * 1e4:+.1f} to {ci[1] * 1e4:+.1f}"


def _f(x, fmt: str = "+.3f") -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, fmt)


def rankdata(x) -> np.ndarray:
    """Ranks 1..n with ties given their average rank."""
    x = np.asarray(x, dtype=float); n = len(x)
    order = np.argsort(x, kind="mergesort"); xs = x[order]
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[j + 1] == xs[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def _pearson(a, b) -> Optional[float]:
    a = np.asarray(a, dtype=float) - np.mean(a); b = np.asarray(b, dtype=float) - np.mean(b)
    den = math.sqrt(float(a @ a) * float(b @ b))
    return None if den == 0 else float(a @ b / den)


def spearman(x, y) -> Optional[float]:
    if len(x) < 3:
        return None
    return _pearson(rankdata(x), rankdata(y))


def spearman_perm_p(x, y, n_perm: int = 10000, seed: int = 0, alternative: str = "less") -> Optional[float]:
    """One-sided permutation p-value for Spearman rho: 'less' tests H0 rho >= 0 (small p = significantly negative)."""
    if len(x) < 3:
        return None
    rx = rankdata(x); ry = rankdata(y)
    rx = rx - rx.mean(); ry = ry - ry.mean()
    den = math.sqrt(float(rx @ rx) * float(ry @ ry))
    if den == 0:
        return None
    obs = float(rx @ ry) / den
    rng = np.random.default_rng(seed)
    perm = rng.permuted(np.tile(ry, (n_perm, 1)), axis=1)
    null = perm @ rx / den
    hits = np.sum(null <= obs + 1e-12) if alternative == "less" else np.sum(null >= obs - 1e-12)
    return float((hits + 1) / (n_perm + 1))


def spearman_ci(rho: Optional[float], n: int, z: float = 1.959964) -> list:
    """Two-sided 95% interval of a Spearman rho from ``n`` pairs: Fisher z with the Bonett-Wright (2000) variance
    (1 + rho^2/2) / (n - 3). [None, None] without rho or under 4 pairs."""
    if rho is None or n < 4:
        return [None, None]
    r = min(max(float(rho), -0.999999), 0.999999)
    se = math.sqrt((1.0 + r * r / 2.0) / (n - 3))
    zr = math.atanh(r)
    return [math.tanh(zr - z * se), math.tanh(zr + z * se)]


def partial_spearman(x, y, z) -> Optional[float]:
    """Spearman correlation of x and y after removing the rank-linear effect of z from both."""
    if len(x) < 4:
        return None
    rx, ry, rz = rankdata(x), rankdata(y), rankdata(z)
    Z = np.column_stack([np.ones(len(rz)), rz])
    ex = rx - Z @ np.linalg.lstsq(Z, rx, rcond=None)[0]
    ey = ry - Z @ np.linalg.lstsq(Z, ry, rcond=None)[0]
    return _pearson(ex, ey)


# ------------------------------------------------------------------------------- model-priced 1-day straddles --

def straddle_premium(sigma, tau: float = TAU_1D, fwd=1.0):
    """Black-Scholes straddle struck at the T-1 spot (K = 1 per unit spot), r = 0, as a fraction of spot, on the forward
    ``fwd`` per unit spot: 1 - D/S when a known dividend D goes ex before expiry (escrowed-dividend model), else 1 (ATM)."""
    s = np.asarray(sigma, dtype=float); F = np.asarray(fwd, dtype=float)
    return bs.price(F, 1.0, tau, 0.0, s, "call") + bs.price(F, 1.0, tau, 0.0, s, "put")


def ex_dividend_yields(days: Sequence[str], raw_closes, adj_closes, tol: float = 1e-4, cap: float = 0.05) -> dict[str, float]:
    """{ex-dividend day: D / close(day before)} from the steps in the adjclose/close ratio: Yahoo multiplies every close
    before an ex-date by 1 - D/S(day before), so ratio(i-1)/ratio(i) = 1 - y on ex-day i. Steps under ``tol`` are rounding;
    steps over ``cap`` (a missing adjclose) are not dividends."""
    ratio = np.asarray(adj_closes, dtype=float) / np.asarray(raw_closes, dtype=float)
    out = {}
    for i in range(1, len(days)):
        if np.isfinite(ratio[i]) and np.isfinite(ratio[i - 1]) and ratio[i] > 0:
            y = 1.0 - ratio[i - 1] / ratio[i]
            if tol < y < cap:
                out[str(days[i])] = float(y)
    return out


def straddle_panel(days: Sequence[str], closes, iv: dict, tau: float = TAU_1D, start: Optional[str] = None,
                   end: Optional[str] = None, div_yield: Optional[dict] = None) -> dict:
    """One 1-day straddle per day i: K = close(i-1), sigma = iv[day i-1]/100, settled at |close(i) - K|.
    ``long`` = (|S_i - S_i-1| - premium) / S_i-1; the short P&L is its negative. ``div_yield`` = {ex-dividend day i:
    D / S_i-1}: that day's straddle is priced on the dividend forward F = S_i-1 (1 - y) (``div`` = y; K and the
    settlement are unchanged) and ``move_fwd`` = |S_i - F| / S_i-1 is the dividend-neutral move. Without it y = 0 (ATM)."""
    c = np.asarray(closes, dtype=float)
    keep = [i for i in range(1, len(days))
            if (not start or days[i] >= start) and (not end or days[i] <= end) and (iv.get(days[i - 1]) or 0) > 0]
    idx = np.array(keep, dtype=int)
    if len(idx) == 0:
        return {k: np.array([], dtype=str) if k in ("days", "prev") else np.array([])
                for k in ("days", "prev", "s0", "s1", "sigma", "div", "premium", "ret", "move", "move_fwd", "long")}
    s0, s1 = c[idx - 1], c[idx]
    sig = np.array([iv[days[i - 1]] for i in keep], dtype=float) / 100.0
    y = np.array([float((div_yield or {}).get(days[i], 0.0)) for i in keep], dtype=float)
    prem = straddle_premium(sig, tau, 1.0 - y)
    ret = s1 / s0 - 1
    return {"days": np.array([days[i] for i in keep]), "prev": np.array([days[i - 1] for i in keep]), "s0": s0, "s1": s1,
            "sigma": sig, "div": y, "premium": prem, "ret": ret, "move": np.abs(ret), "move_fwd": np.abs(ret + y),
            "long": np.abs(ret) - prem}


def _subset(P: dict, m: np.ndarray) -> dict:
    return {k: v[m] for k, v in P.items()}


# ----------------------------------------------------------------------------------------------- house rule 5 --

MIN_DECISIVE_EVENTS = 4     # an interval from fewer events (or fewer than 4 blocks of days) never decides below min_n


def _ci_below(ci, bound: float) -> bool:
    """The 95% interval lies wholly at or below ``bound``. False without an interval and for a zero-width one."""
    lo, hi = ci
    return lo is not None and hi is not None and lo < hi and hi <= bound


def _ci_above(ci, bound: float) -> bool:
    """The 95% interval lies wholly at or above ``bound``. False without an interval and for a zero-width one."""
    lo, hi = ci
    return lo is not None and hi is not None and lo < hi and lo >= bound


def _decides(g: dict, block: int) -> bool:
    """A ``group_diff`` interval may decide a failure below min_n: at least 4 events and 4 blocks of days."""
    return g["n_event"] >= MIN_DECISIVE_EVENTS and g["n_event"] + g["n_other"] >= 4 * block


def _rule5(crit, decisive, n: int, min_n: int, unit: str) -> tuple[str, str, dict]:
    """House rule 5 below the trial's min_n (``n`` in the claim's own units; at or above min_n callers judge ``crit`` at
    face value with ``_verdict``, exactly as before). ``crit``: the face-value criteria [(name, ok)], ok True / False /
    None (not implemented); ``decisive``: one flag per criterion, True when its failure stands below min_n (its 95%
    interval lies wholly on the wrong side of the claimed bound). A passing or decisively failing criterion keeps its
    bool, any other failure becomes None (undecided), and the unmet 'n >= trial min_n' criterion (None) keeps the
    verdict from 'supported'. Returns (verdict, why, rule-5 record)."""
    crit = [(name, None if ok is None else bool(ok)) for name, ok in crit]
    judged = [(name, ok) if ok is None or ok else (name + " (fails decisively below min_n)", False) if d
              else (name + " (fails, not decisively, below min_n: undecided)", None) for (name, ok), d in zip(crit, decisive)]
    judged.append((f"n >= trial min_n ({n} {unit}, need {min_n})", None))
    failed = [name for (name, ok), d in zip(crit, decisive) if ok is False and d]
    v, why = _verdict(judged)
    v0, why0 = _verdict(crit)
    why = (f"only {n} {unit}, below the trial's min_n {min_n}, so the verdict cannot be supported and a failing criterion "
           f"counts only when it fails decisively, its 95% interval wholly on the wrong side of the claimed bound (house rule 5). "
           f"Decisive failures: {'; '.join(failed) if failed else 'none'}. {v}: {why} (criteria at face value: {v0}, {why0})")
    return v, why, {"min_n": min_n, "n": n, "unit": unit, "criteria": [[c, ok] for c, ok in judged],
                    "criteria_at_face_value": [[c, ok] for c, ok in crit], "decisive_failures": failed}


def _below_min_n(rep: dict, crit, decisive, n: int, min_n: int, unit: str, body: str) -> dict:
    """Sets the rule-5 verdict, reason (``body`` — explanation) and record on ``rep`` and returns it."""
    v, why, r5 = _rule5(crit, decisive, n, min_n, unit)
    rep.update(verdict=v, reason=f"{body} — {why}", rule5=r5)
    return rep


def _placebo_days(days: Sequence[str], event_days, offset_calendar_days: int = 7) -> set:
    """Trading day on/after event+k and on/before event-k calendar days, minus the events themselves."""
    arr = np.array(days); out = set(); ev = set(event_days)
    for e in event_days:
        de = _d(e)
        a = (de + timedelta(days=offset_calendar_days)).isoformat(); b = (de - timedelta(days=offset_calendar_days)).isoformat()
        ia = int(np.searchsorted(arr, a, side="left")); ib = int(np.searchsorted(arr, b, side="right")) - 1
        if ia < len(arr):
            out.add(str(arr[ia]))
        if ib >= 0:
            out.add(str(arr[ib]))
    return out - ev


# -------------------------------------------------------------------------- T-343 announcement-day premium --

def _net_of_blocks(r: np.ndarray, flag: np.ndarray, cost_bps: float) -> tuple[np.ndarray, np.ndarray]:
    """Returns net of one ``cost_bps`` round trip per run of consecutive flagged days (charged on the run's first day)."""
    entries = flag & ~np.concatenate([[False], flag[:-1]])
    return r - entries * cost_bps / 1e4, entries


def announcement_day_premium(days: Sequence[str], closes, cpi_days, es_days, fomc_days, start: str = "1993-01-01",
                             end: str = "2026-12-31",
                             halves=(("1993-2009", "1993-01-01", "2009-12-31"), ("2010-2026", "2010-01-01", "2026-12-31")),
                             cost_bps: float = 2.0, threshold_bps: float = 5.0, flagged_days=(), tlt: Optional[tuple] = None,
                             block: int = 10, n_boot: int = 2000, seed: int = 0, min_n: int = 600) -> dict:
    """T-343: SPY close-to-close return on scheduled CPI, Employment Situation and FOMC statement days minus the mean on all
    other days, net of a ``cost_bps`` round trip per run of consecutive release days. Pass: net difference > 5 bps/day
    with studentized block-bootstrap (block 10) p < 0.05 (H0: difference <= 0) and a positive net difference in
    1993-2009 and in 2010-2026. Reported: per-type breakdown (each type vs non-release days, Holm over 3), the
    FOMC-excluded sensitivity, the runnable non-primary variants (CPI 2021-2026, jobs only, TLT) with Holm, day-type
    Sharpe (each type annualised by sqrt of its own days per year) and the release-only strategy Sharpe (flat otherwise,
    sqrt(252)), ex-2008/2020, ex shutdown-delayed releases, overlaps. ``tlt`` = (days, closes). Below ``min_n`` release
    days house rule 5 applies: never supported; the difference and each half fail decisively only when their 95%
    block-bootstrap CI lies wholly at or below the bound (5 bps for the difference, 0 for each half), and the p criterion
    only when the opposite one-sided studentized p (H0: difference >= 0, the same test) is < 0.05."""
    ds, r = _returns(days, closes, start, end)
    if len(ds) == 0:
        return {"n": 0, "verdict": "inconclusive", "reason": f"no SPY returns in {start}..{end}"}
    dlist = list(days)
    types = {}
    moved = {}
    for lab, evs in (("CPI", cpi_days), ("Employment Situation", es_days), ("FOMC", fomc_days)):
        s, mv = to_sessions([e for e in evs if start <= e <= end], dlist)
        types[lab] = np.isin(ds, s); moved[lab] = mv
    flag = types["CPI"] | types["Employment Situation"] | types["FOMC"]
    net, entries = _net_of_blocks(r, flag, cost_bps)
    g = group_diff(net, flag, block, n_boot, seed)
    if g["diff"] is None:
        return {"n": int(flag.sum()), "verdict": "inconclusive", "reason": "too few release or non-release days"}
    d = flag_diff_series(net, flag)
    p_thr = float(block_bootstrap_pvalue(d - threshold_bps / 1e4, np.zeros_like(d), n_boot=n_boot, block_len=block, seed=seed))
    hv = {}
    for lab, lo, hi in halves:
        m = _range_mask(ds, lo, hi)
        hv[lab] = group_diff(net[m], flag[m], block, n_boot, seed)
    # per type: each type's days vs non-release days (other types' days left out)
    per_type = {}
    for lab, tf in types.items():
        m = tf | ~flag
        per_type[lab] = group_diff(net[m], tf[m], block, n_boot, seed)
    holm_types = _holm({k: v["p_greater"] for k, v in per_type.items() if v["p_greater"] is not None})
    # FOMC-excluded sensitivity: FOMC days that are not CPI/jobs days leave the sample; costs re-counted
    cj = types["CPI"] | types["Employment Situation"]
    keep_fx = ~(types["FOMC"] & ~cj)
    net_cj, _ = _net_of_blocks(r, cj, cost_bps)
    fomc_excl = group_diff(net_cj[keep_fx], cj[keep_fx], block, n_boot, seed)
    # variants
    m21 = _range_mask(ds, "2021-01-01", end)
    net_c, _ = _net_of_blocks(r, types["CPI"], cost_bps)
    cpi21 = group_diff(net_c[m21], types["CPI"][m21], block, n_boot, seed)
    net_j, _ = _net_of_blocks(r, types["Employment Situation"], cost_bps)
    jobs = group_diff(net_j, types["Employment Situation"], block, n_boot, seed)
    tlt_g = None
    if tlt is not None:
        td, tc = tlt
        tds, tr = _returns(td, tc, start, end)
        if len(tds):
            tflag = np.zeros(len(tds), dtype=bool)
            for evs in (cpi_days, es_days, fomc_days):
                tflag |= np.isin(tds, to_sessions([e for e in evs if start <= e <= end], list(td))[0])
            tnet, _ = _net_of_blocks(tr, tflag, cost_bps)
            tlt_g = group_diff(tnet, tflag, block, n_boot, seed)
            tlt_g["first_day"] = str(tds[0])
    var_p = {"primary (pooled SPY)": g["p_greater"], "CPI only 2021-2026": cpi21["p_greater"], "jobs only": jobs["p_greater"],
             "FOMC excluded": fomc_excl["p_greater"]}
    if tlt_g is not None:
        var_p["TLT pooled"] = tlt_g["p_greater"]
    holm_var = _holm({k: v for k, v in var_p.items() if v is not None})
    # Sharpe by day type (net daily returns): each type annualised by sqrt(its own days per year), so neither type is
    # credited with days it does not hold; the release-only strategy (flat otherwise) is annualised by sqrt(252)
    def _sh(x, per_year):
        sd = float(x.std(ddof=1)) if len(x) > 2 else 0.0
        return float(x.mean() / sd * math.sqrt(per_year)) if sd > 0 else None
    td_years = len(r) / EQ_PPY
    per_year = {"release": float(flag.sum() / td_years), "other": float((~flag).sum() / td_years)}
    sharpe = {"release": _sh(net[flag], per_year["release"]), "other": _sh(net[~flag], per_year["other"])}
    sharpe_release_only = _sh(np.where(flag, net, 0.0), EQ_PPY)
    yr = np.array([s[:4] for s in ds])
    m_ex = ~np.isin(yr, ["2008", "2020"])
    ex0820 = _point_diff(net[m_ex], flag[m_ex])
    fl_s = set(to_sessions([x for x in flagged_days if start <= x <= end], dlist)[0])
    m_fl = ~np.isin(ds, list(fl_s))
    ex_flagged = _point_diff(net[m_fl], flag[m_fl])
    years = max((_d(str(ds[-1])) - _d(str(ds[0]))).days / 365.25, 1e-9)
    gross = _point_diff(r, flag)
    pre_fomc = set()
    pos = {x: i for i, x in enumerate(dlist)}
    for f_ in fomc_days:
        if f_ in pos and pos[f_] > 0:
            pre_fomc.add(dlist[pos[f_] - 1])
    rep = {"n": int(flag.sum()), "n_days": int(len(r)), "first_day": str(ds[0]), "last_day": str(ds[-1]),
           "n_by_type": {k: int(v.sum()) for k, v in types.items()}, "moved_to_next_session": moved,
           "overlaps": {"CPI&FOMC": int((types["CPI"] & types["FOMC"]).sum()), "jobs&FOMC": int((types["Employment Situation"] & types["FOMC"]).sum()),
                        "CPI&jobs": int((types["CPI"] & types["Employment Situation"]).sum()),
                        "CPI/jobs on the session before an FOMC decision": int((cj & np.isin(ds, list(pre_fomc))).sum()),
                        "FOMC statement days in the pooled set (shared with the pre-FOMC entry)": int(types["FOMC"].sum())},
           "cost_bps_round_trip": cost_bps, "round_trips_per_year": float(entries.sum() / years), "net": g, "gross_diff_bps": gross * 1e4,
           "p_vs_threshold": p_thr, "threshold_bps": threshold_bps, "halves": hv, "per_type": per_type, "per_type_holm_p": holm_types,
           "fomc_excluded": fomc_excl, "variants": {"CPI only 2021-2026": cpi21, "jobs only": jobs, "TLT pooled": tlt_g},
           "variants_holm_p": holm_var,
           "sharpe_by_day_type": sharpe, "days_per_year_by_type": per_year,
           "sharpe_annualisation": "each day type by sqrt(its days per year); release-only strategy (flat otherwise) by sqrt(252)",
           "sharpe_release_only_strategy": sharpe_release_only,
           "excluding_2008_2020_diff_bps": None if ex0820 is None else ex0820 * 1e4,
           "flagged_delayed_sessions": sorted(fl_s), "excluding_flagged_diff_bps": None if ex_flagged is None else ex_flagged * 1e4,
           "not_run": ["Kalshi outcome-entropy variant (no KXCPI/KXPAYROLLS candles archived)"],
           "calendar_note": "CPI/jobs: ALFRED vintage dates with seasonal-revision and correction vintages removed; FOMC: scheduled decision days"}
    crit = [(f"net difference > {threshold_bps:g} bps/day", g["diff"] > threshold_bps / 1e4),
            ("studentized block-bootstrap p < 0.05", g["p_greater"] < 0.05)]
    for lab, h in hv.items():
        crit.append((f"{lab} net difference > 0", None if h["diff"] is None else h["diff"] > 0))
    body = (f"SPY release-day close-to-close {g['mean_event']*1e4:+.2f} bps (net of {cost_bps:g} bps per round trip, "
            f"{rep['round_trips_per_year']:.0f}/yr) vs other days {g['mean_other']*1e4:+.2f} bps over {g['n_event']} release days "
            f"(CPI {rep['n_by_type']['CPI']}, jobs {rep['n_by_type']['Employment Situation']}, FOMC {rep['n_by_type']['FOMC']}) "
            f"{rep['first_day']}..{rep['last_day']}: net difference {g['diff']*1e4:+.2f} bps/day (gross {gross*1e4:+.2f}; 95% CI {_ci_bps(g['ci'])}), "
            f"p={g['p_greater']:.4f} (H0 diff<=0; p vs {threshold_bps:g} bps {p_thr:.3f}); "
            + ", ".join(f"{k} {_bps(h['diff'])} bps" for k, h in hv.items())
            + "; per type " + ", ".join(f"{k} {_bps(v_['diff'])} (Holm p {_f(holm_types.get(k), '.3f')})" for k, v_ in per_type.items())
            + f"; FOMC-excluded {_bps(fomc_excl['diff'])} bps (p={_f(fomc_excl['p_greater'], '.3f')}); net Sharpe, each day type "
            f"annualised by sqrt of its days/yr ({per_year['release']:.0f} release, {per_year['other']:.0f} other): release "
            f"{_f(sharpe['release'], '.2f')} vs other {_f(sharpe['other'], '.2f')} (release-only strategy, flat otherwise, "
            f"{_f(sharpe_release_only, '.2f')}); primary Holm p over "
            f"{len(holm_var)} variants {_f(holm_var.get('primary (pooled SPY)'), '.3f')}")
    if rep["n"] < min_n:
        # rule 5: the difference fails decisively when its 95% CI lies wholly at or below 5 bps, and a half when that
        # half's CI lies wholly at or below 0. The one-sided p < 0.05 criterion is mirrored at its own level by the same
        # studentized block-bootstrap test in the opposite direction: p_less (H0: diff >= 0) < 0.05
        dec = [_decides(g, block) and _ci_below(g["ci"], threshold_bps / 1e4),
               _decides(g, block) and g["p_less"] is not None and g["p_less"] < 0.05]
        dec += [_decides(h, block) and _ci_below(h["ci"], 0.0) for h in hv.values()]
        body += ("; halves 95% CI " + ", ".join(f"{k} {_ci_bps(h['ci'])} bps" for k, h in hv.items())
                 + f"; opposite one-sided studentized p (H0 diff >= 0) {_f(g['p_less'], '.4f')}")
        rep_ = _below_min_n(rep, crit, dec, rep["n"], min_n, "release days", body)
        rep_["rule5"]["p_opposite_studentized"] = g["p_less"]
        return rep_
    v, why = _verdict(crit)
    rep["verdict"] = v
    rep["reason"] = f"{body} — {why}"
    return rep


# -------------------------------------------------------------------------------- T-208 IM/HM rank filter --

def event_move_table(days: Sequence[str], closes, iv: dict, event_days, n_hm: int = 8, tau: float = TAU_1D,
                     opens: Optional[dict] = None) -> dict:
    """Per event day T (a trading day): premium = BS ATM straddle/S at sigma = iv(T-1)/100; IM = 0.845 x premium;
    move = |S_T/S_T-1 - 1|; HM = median move over the previous ``n_hm`` events; ratio = IM/HM;
    long = move - premium (long-straddle P&L in fraction of S_T-1); ret_on_debit = move/premium - 1.
    Rows without HM (first ``n_hm`` events) or without iv(T-1) are dropped after HM is computed."""
    c = np.asarray(closes, dtype=float); pos = {d: i for i, d in enumerate(days)}
    idx = np.array(sorted({pos[e] for e in event_days if e in pos and pos[e] > 0}), dtype=int)
    empty = {k: np.array([]) for k in ("days", "sigma", "premium", "im", "hm", "ratio", "move", "long", "ret_on_debit", "long_open")}
    if len(idx) == 0:
        return empty
    move = np.abs(c[idx] / c[idx - 1] - 1)
    hm = np.full(len(idx), np.nan)
    for k in range(n_hm, len(idx)):
        hm[k] = np.median(move[k - n_hm:k])
    sig = np.array([iv.get(days[i - 1], np.nan) for i in idx], dtype=float) / 100.0
    ok = np.isfinite(hm) & (hm > 0) & np.isfinite(sig) & (sig > 0)
    idx, move, hm, sig = idx[ok], move[ok], hm[ok], sig[ok]
    if len(idx) == 0:
        return empty
    prem = straddle_premium(sig, tau)
    im = MEDIAN_MOVE_FACTOR * prem
    out = {"days": np.array([days[i] for i in idx]), "sigma": sig, "premium": prem, "im": im, "hm": hm, "ratio": im / hm,
           "move": move, "long": move - prem, "ret_on_debit": move / prem - 1}
    if opens is not None:
        out["long_open"] = np.array([abs(opens[days[i]] / c[i - 1] - 1) - p if days[i] in opens else np.nan for i, p in zip(idx, prem)])
    else:
        out["long_open"] = np.full(len(idx), np.nan)
    return out


def _q_bootstrap_ci(a: np.ndarray, b: np.ndarray, n_boot: int, seed: int) -> list:
    if len(a) < 2 or len(b) < 2:
        return [None, None]
    rng = np.random.default_rng(seed)
    bs_ = np.array([rng.choice(a, a.size).mean() - rng.choice(b, b.size).mean() for _ in range(n_boot)])
    return [float(np.quantile(bs_, 0.025)), float(np.quantile(bs_, 0.975))]


def im_hm_filter(days: Sequence[str], closes, vix: dict, fomc_days, opens: Optional[dict] = None, start: str = "1994-01-01",
                 is_end: str = "2009-12-31", oos_start: str = "2010-01-01", end: Optional[str] = None, n_hm: int = 8,
                 rho_threshold: float = -0.1, n_perm: int = 10000, n_boot: int = 4000, n_placebo: int = 200,
                 seed: int = 0, min_n: int = 200) -> dict:
    """T-208 (MODEL-PRICED): for each scheduled FOMC day since 1994, IM/HM with IM = 0.845 x BS 1-day ATM straddle/S at
    sigma = VIX(T-1), T = 1/252, and HM = median |SPY return| over the previous 8 FOMC days; long-straddle P&L =
    |S_T - S_T-1|/S_T-1 - straddle/S_T-1. Quintile cutoffs of IM/HM come from 1994-2009 events only and are applied to
    2010-2026. Pass (out of sample, 2010-2026): Spearman rho(IM/HM, long P&L) < -0.1 with a one-sided permutation
    p < 0.05 (H0 rho >= 0), and Q1-minus-Q5 mean long P&L > 0 with the 95% bootstrap CI excluding 0. Reported: in-sample
    and full rho, return-on-debit rho, rho partialling out the VIX level, a random non-event-day placebo, and the
    close-to-open realised definition (the 14:00 statement is after the open, so that one is a non-event control).
    ``min_n`` applies to the full event table. Below it house rule 5 applies: never supported, and a criterion fails
    decisively only when it fails at the confidence of its pass (the OOS rho's two-sided 95% Fisher-z interval at or
    above -0.1 for the rho criterion; the opposite one-sided permutation p, H0 rho <= 0 from the same draws, < 0.05 for
    the permutation criterion; the Q1-Q5 bootstrap CI at or below 0 for both quintile criteria, with at least 4 events in
    Q1 and in Q5)."""
    ev = sorted(e for e in fomc_days if e >= start and (end is None or e <= end))
    T = event_move_table(days, closes, vix, ev, n_hm=n_hm, opens=opens)
    n = int(len(T["days"]))
    if n == 0:
        return {"n": 0, "verdict": "inconclusive", "reason": "no FOMC day with SPY, a prior-day VIX close and 8 earlier FOMC moves"}
    is_m = T["days"] <= is_end; oos_m = T["days"] >= oos_start
    n_is, n_oos = int(is_m.sum()), int(oos_m.sum())
    rep = {"label": "MODEL-PRICED", "n": n, "n_in_sample": n_is, "n_oos": n_oos, "first_event": str(T["days"][0]), "last_event": str(T["days"][-1]),
           "pricing": "Black-Scholes, sigma = VIX(T-1)/100, T = 1/252, K = SPY(T-1) close, r = q = 0; P&L as a fraction of spot",
           "definition": f"IM = {MEDIAN_MOVE_FACTOR} x straddle/S; HM = median |r| over the previous {n_hm} scheduled FOMC days; long P&L = |r_T| - straddle/S"}
    if n_is < 5 or n_oos < 5:
        rep.update(verdict="inconclusive", reason=f"MODEL-PRICED: {n_is} in-sample and {n_oos} out-of-sample FOMC events: too few to set cutoffs or test")
        return rep
    cut = np.quantile(T["ratio"][is_m], [0.2, 0.4, 0.6, 0.8])
    q = np.searchsorted(cut, T["ratio"], side="right")           # 0..4 = Q1..Q5
    x, y = T["ratio"][oos_m], T["long"][oos_m]
    rho = spearman(x, y); p_rho = spearman_perm_p(x, y, n_perm, seed, "less")
    qo = q[oos_m]
    a, b = y[qo == 0], y[qo == 4]
    q15 = float(a.mean() - b.mean()) if len(a) and len(b) else None
    ci = _q_bootstrap_ci(a, b, n_boot, seed)
    q_means = {f"Q{k + 1}": {"n": int((qo == k).sum()), "mean_long_pnl_bps": float(y[qo == k].mean() * 1e4) if (qo == k).any() else None} for k in range(5)}
    # controls
    rho_is = spearman(T["ratio"][is_m], T["long"][is_m]); rho_full = spearman(T["ratio"], T["long"])
    rho_debit = spearman(x, T["ret_on_debit"][oos_m])
    rho_partial = partial_spearman(x, y, T["sigma"][oos_m])
    lo_ok = np.isfinite(T["long_open"][oos_m])
    rho_open = spearman(x[lo_ok], T["long_open"][oos_m][lo_ok]) if lo_ok.sum() >= 3 else None
    # placebo: random non-FOMC days (same count as the FOMC days used), HM from the previous 8 placebo days
    rng = np.random.default_rng(seed + 1)
    evset = set(ev)
    pool = [days[i] for i in range(1, len(days)) if days[i] >= start and (end is None or days[i] <= end)
            and days[i] not in evset and (vix.get(days[i - 1]) or 0) > 0]
    n_draw = len([e for e in ev if e in set(days)])
    prho = []
    if len(pool) > n_draw > n_hm:
        for _ in range(n_placebo):
            pick = sorted(rng.choice(pool, n_draw, replace=False).tolist())
            Pt = event_move_table(days, closes, vix, pick, n_hm=n_hm)
            mo = Pt["days"] >= oos_start
            r_ = spearman(Pt["ratio"][mo], Pt["long"][mo]) if mo.sum() >= 3 else None
            if r_ is not None:
                prho.append(r_)
    prho = np.array(prho)
    placebo = {"n_draws": int(len(prho)), "mean_rho": float(prho.mean()) if len(prho) else None,
               "share_at_or_below_observed": float((prho <= rho).mean()) if len(prho) and rho is not None else None}
    rep.update(in_sample_cutoffs=cut, oos_spearman_rho=rho, oos_perm_p=p_rho, oos_q1_minus_q5=q15, oos_q1_minus_q5_ci=ci,
               oos_quintiles=q_means, in_sample_rho=rho_is, full_rho=rho_full, oos_rho_return_on_debit=rho_debit,
               oos_rho_partial_vix=rho_partial, oos_rho_close_to_open=rho_open, placebo_random_days=placebo,
               mean_long_pnl_oos_bps=float(y.mean() * 1e4), mean_ratio_oos=float(x.mean()))
    crit = [(f"OOS Spearman rho < {rho_threshold:g}", None if rho is None else rho < rho_threshold),
            ("OOS one-sided permutation p < 0.05", None if p_rho is None else p_rho < 0.05),
            ("OOS Q1-Q5 mean long P&L > 0", None if q15 is None else q15 > 0),
            ("OOS Q1-Q5 95% CI excludes 0", None if ci[0] is None else ci[0] > 0)]
    body = (f"MODEL-PRICED long 1-day ATM SPY straddle (BS, sigma=VIX(T-1), T=1/252) on {n} scheduled FOMC days "
            f"{rep['first_event']}..{rep['last_event']}; OOS 2010+ ({n_oos} events): Spearman rho(IM/HM, long P&L) {_f(rho)} "
            f"(permutation p={_f(p_rho, '.4f')}); Q1-Q5 with 1994-2009 cutoffs {_bps(q15)} bps of spot (95% CI {_ci_bps(ci)}; "
            f"Q1 n={q_means['Q1']['n']}, Q5 n={q_means['Q5']['n']}); in-sample rho {_f(rho_is)}, VIX-partialled OOS rho {_f(rho_partial)}, "
            f"return-on-debit OOS rho {_f(rho_debit)}, close-to-open OOS rho {_f(rho_open)}, random-day placebo mean rho "
            f"{_f(placebo['mean_rho'])}")
    if n < min_n:
        # rule 5: rho fails decisively when its 95% interval (Fisher z) lies wholly at or above -0.1; the one-sided
        # permutation p < 0.05 criterion is mirrored at its own level by the opposite one-sided permutation test from the
        # same draws (H0 rho <= 0): p_greater < 0.05; the Q1-Q5 criteria when the Q1-Q5 CI lies wholly at or below 0 (>= 4
        # events in each of Q1 and Q5)
        rho_ci = spearman_ci(rho, n_oos)
        p_rho_greater = spearman_perm_p(x, y, n_perm, seed, "greater") if n_oos >= MIN_DECISIVE_EVENTS else None
        q_ok = len(a) >= MIN_DECISIVE_EVENTS and len(b) >= MIN_DECISIVE_EVENTS
        dec = [_ci_above(rho_ci, rho_threshold), p_rho_greater is not None and p_rho_greater < 0.05,
               q_ok and _ci_below(ci, 0.0), q_ok and _ci_below(ci, 0.0)]
        rep["oos_spearman_rho_ci"] = rho_ci
        rep["oos_perm_p_greater"] = p_rho_greater
        body += (f"; OOS rho 95% interval (Fisher z, Bonett-Wright) [{_f(rho_ci[0])}, {_f(rho_ci[1])}]; opposite one-sided "
                 f"permutation p (H0 rho <= 0) {_f(p_rho_greater, '.4f')}")
        rep_ = _below_min_n(rep, crit, dec, n, min_n, "FOMC events with IM and HM", body)
        rep_["rule5"]["p_opposite_permutation"] = p_rho_greater
        return rep_
    v, why = _verdict(crit)
    rep["verdict"] = v
    rep["reason"] = f"{body} — {why}"
    return rep


# ----------------------------------------------------------------------------- T-224 GLD event short straddle --

def event_straddle_diff(P: dict, event_sessions: set, exclude_sessions: set = frozenset(), side: str = "short",
                        block: int = 10, n_boot: int = 2000, seed: int = 0) -> tuple[dict, dict, np.ndarray]:
    """Event-minus-non-event mean straddle P&L (``side`` short or long) on a panel from ``straddle_panel``, after leaving
    ``exclude_sessions`` out of both groups. Returns (group_diff, panel subset, flag)."""
    keep = ~np.isin(P["days"], sorted(set(exclude_sessions) - set(event_sessions)))
    Q = _subset(P, keep)
    f = np.isin(Q["days"], sorted(event_sessions))
    x = -Q["long"] if side == "short" else Q["long"]
    return group_diff(x, f, block, n_boot, seed), Q, f


def gld_event_straddle(days: Sequence[str], closes, gvz: dict, fomc_days, cpi_days, es_days=(), exclude_days=(),
                       start: str = "2009-09-01", end: Optional[str] = None, spx: Optional[tuple] = None, block: int = 10,
                       n_boot: int = 2000, seed: int = 0, min_n: int = 150) -> dict:
    """T-224 (MODEL-PRICED): 1-day ATM GLD straddle, sigma = GVZ at the T-1 close, T = 1/252, sold at the T-1 close and
    settled at |GLD_T - GLD_T-1|, on scheduled FOMC decision days and CPI release days since 2009-09 vs all other days.
    Pass: event-minus-non-event mean short P&L < 0 with the 95% block-bootstrap CI excluding 0. Reported: |r|/(GVZ/sqrt252)
    by group, per type (FOMC, CPI), +/-7 calendar-day placebo, ex March 2020, GVZ terciles, non-event days without
    Employment Situation days, and the same test on SPY with VIX (``spx`` = (days, closes, vix)). ``exclude_days``
    (unscheduled FOMC days) leave both groups. The real-rate regime split is not run (no real-yield series archived).
    Below ``min_n`` event days house rule 5 applies: never supported, and both criteria fail decisively only when the
    difference's 95% block-bootstrap CI lies wholly at or above 0."""
    P = straddle_panel(days, closes, gvz, TAU_1D, start=start, end=end)
    if len(P["days"]) == 0:
        return {"n": 0, "verdict": "inconclusive", "reason": f"no GLD day since {start} has a prior-day GVZ close"}
    dl = list(days)
    in_rng = lambda evs: [e for e in evs if e >= start and (end is None or e <= end)]
    fomc_s, mv_f = to_sessions(in_rng(fomc_days), dl); cpi_s, mv_c = to_sessions(in_rng(cpi_days), dl)
    es_s, _ = to_sessions(in_rng(es_days), dl); ex_s, _ = to_sessions(in_rng(exclude_days), dl)
    ev = set(fomc_s) | set(cpi_s)
    full, Q, f = event_straddle_diff(P, ev, set(ex_s), "short", block, n_boot, seed)
    short = -Q["long"]
    ratio = Q["move"] / (Q["sigma"] / math.sqrt(EQ_PPY))
    per_type = {}
    for lab, s in (("FOMC", set(fomc_s)), ("CPI", set(cpi_s))):
        g_, _, _ = event_straddle_diff(P, s, set(ex_s) | (ev - s), "short", block, n_boot, seed)
        per_type[lab] = g_
    plc = _placebo_days(list(Q["days"]), sorted(ev), 7)
    m_nf = ~f
    placebo = group_diff(short[m_nf], np.isin(Q["days"][m_nf], sorted(plc)), block, n_boot, seed)
    ex20 = np.array([not d_.startswith("2020-03") for d_ in Q["days"]])
    excl = group_diff(short[ex20], f[ex20], block, n_boot, seed)
    no_es = ~(np.isin(Q["days"], es_s) & ~f)
    without_es = _point_diff(short[no_es], f[no_es])
    q1, q2 = np.quantile(Q["sigma"], [1 / 3, 2 / 3])
    terc = {}
    for lab, m in (("low", Q["sigma"] <= q1), ("mid", (Q["sigma"] > q1) & (Q["sigma"] <= q2)), ("high", Q["sigma"] > q2)):
        dd = _point_diff(short[m], f[m])
        terc[lab] = {"n_event": int((f & m).sum()), "diff_bps": None if dd is None else dd * 1e4}
    spx_rep = None
    if spx is not None:
        sd, sc, vix = spx
        Ps = straddle_panel(sd, sc, vix, TAU_1D, start=str(Q["days"][0]), end=str(Q["days"][-1]))
        if len(Ps["days"]):
            ev_s = set(to_sessions(in_rng(fomc_days), list(sd))[0]) | set(to_sessions(in_rng(cpi_days), list(sd))[0])
            gs, _, _ = event_straddle_diff(Ps, ev_s, set(to_sessions(in_rng(exclude_days), list(sd))[0]), "short", block, n_boot, seed)
            spx_rep = {"diff_bps": None if gs["diff"] is None else gs["diff"] * 1e4, "ci_bps": [None if c_ is None else c_ * 1e4 for c_ in gs["ci"]],
                       "n_event": gs["n_event"]}
    rep = {"label": "MODEL-PRICED", "n": full["n_event"], "first_day": str(Q["days"][0]), "last_day": str(Q["days"][-1]),
           "pricing": "Black-Scholes, sigma = GVZ(T-1)/100, T = 1/252, K = GLD(T-1) close, r = q = 0; short P&L as a fraction of spot",
           "n_fomc": int(np.isin(Q["days"], fomc_s).sum()), "n_cpi": int(np.isin(Q["days"], cpi_s).sum()),
           "moved_to_next_session": {"FOMC": mv_f, "CPI": mv_c}, "full": full,
           "mean_premium_event_bps": float(Q["premium"][f].mean() * 1e4) if f.any() else None,
           "mean_premium_other_bps": float(Q["premium"][~f].mean() * 1e4),
           "abs_r_over_gvz_daily": {"event": float(ratio[f].mean()) if f.any() else None, "other": float(ratio[~f].mean())},
           "per_type": per_type, "placebo_pm7": placebo, "excluding_2020_03": excl,
           "non_event_without_jobs_days_diff_bps": None if without_es is None else without_es * 1e4, "gvz_terciles": terc,
           "spx_comparison_model_priced": spx_rep, "not_run": ["real-rate regime split (no real-yield series such as DFII10 archived)"]}
    crit = [("event-minus-non-event short-straddle P&L < 0", None if full["diff"] is None else full["diff"] < 0),
            ("95% CI excludes 0 (upper bound < 0)", None if full["ci"][1] is None else full["ci"][1] < 0)]
    ra = rep["abs_r_over_gvz_daily"]
    body = (f"MODEL-PRICED short 1-day ATM GLD straddle (BS, sigma=GVZ(T-1), T=1/252) {rep['first_day']}..{rep['last_day']}: "
            f"event mean {_bps(full['mean_event'])} vs non-event {_bps(full['mean_other'])} bps of spot; difference {_bps(full['diff'])} bps "
            f"(95% CI {_ci_bps(full['ci'])}, one-sided p={_f(full['p_less'], '.4f')}) over {full['n_event']} event days (FOMC {rep['n_fomc']}, CPI {rep['n_cpi']}) / {full['n_other']} other; "
            f"|r|/(GVZ/sqrt252) event {_f(ra['event'], '.2f')} vs other {_f(ra['other'], '.2f')}; FOMC {_bps(per_type['FOMC']['diff'])}, "
            f"CPI {_bps(per_type['CPI']['diff'])} bps; placebo +/-7d {_bps(placebo['diff'])} bps; ex Mar-2020 {_bps(excl['diff'])} bps"
            + (f"; SPY/VIX same events {_f(spx_rep['diff_bps'], '+.1f')} bps" if spx_rep else ""))
    if full["n_event"] < min_n:
        # rule 5: both criteria fail decisively when the difference's 95% CI lies wholly at or above 0
        up = _decides(full, block) and _ci_above(full["ci"], 0.0)
        return _below_min_n(rep, crit, [up, up], full["n_event"], min_n, f"FOMC/CPI days with GLD and GVZ since {start}", body)
    v, why = _verdict(crit)
    rep["verdict"] = v
    rep["reason"] = f"{body} — {why}"
    return rep


# ---------------------------------------------------------------------------- T-219 triple-witching straddle --

def friday_panel(days: Sequence[str], closes, iv: dict, start: Optional[str] = None, end: Optional[str] = None,
                 div_yield: Optional[dict] = None) -> dict:
    """Straddle panel restricted to Fridays whose previous trading day is the Thursday before (Thursday close to Friday close)."""
    P = straddle_panel(days, closes, iv, TAU_1D, start=start, end=end, div_yield=div_yield)
    if len(P["days"]) == 0:
        return P
    m = np.array([_d(d).weekday() == 4 and (_d(d) - _d(p)).days == 1 for d, p in zip(P["days"], P["prev"])], dtype=bool)
    return _subset(P, m)


def witching_straddle(days: Sequence[str], closes, vix: dict, fomc_days=(), start: str = "1993-01-01", end: Optional[str] = None,
                      split: str = "2010-01-01", block: int = 4, n_boot: int = 2000, n_perm: int = 10000, seed: int = 0,
                      min_n: int = 100, div_yield: Optional[dict] = None) -> dict:
    """T-219 (MODEL-PRICED): long 1-day ATM SPY straddle bought at Thursday's close (sigma = VIX at Thursday's close,
    T = 1/252) and settled at |SPY_Fri - SPY_Thu| on quarterly triple-witching Fridays (third Friday of Mar/Jun/Sep/Dec)
    vs all other Fridays. ``closes`` are raw (split-adjusted, not dividend-adjusted) closes and ``div_yield`` =
    {ex-dividend day: D / close(day before)}: a straddle over an ex-date is priced on the dividend forward
    F = S_Thu (1 - D/S_Thu), K = S_Thu, so the known ex-date drop (SPY goes ex on the witching Friday) enters the premium
    as well as the payoff. Pass: witching-minus-other mean long P&L > 0 with the 95% block-bootstrap CI (block 4 weeks)
    excluding 0 and a one-sided label-permutation p < 0.05. Reported: |r|/(VIX/sqrt252) on the dividend-neutral move,
    monthly (non-quarterly) opex Fridays as a separate control, witching Fridays in FOMC weeks excluded, pre/post-2010
    split, witching Fridays skipped (holiday or no Thursday session), and the dividend treatment sensitivity (ignored;
    previous ex-date yield as the forecast; dividend-adjusted closes). The 15:00-16:00 ET version is not run (needs a
    15:00 ET price; hourly SPY bars start on the half hour). Below ``min_n`` witching Fridays house rule 5 applies: never
    supported; the difference and CI criteria fail decisively only when the difference's 95% CI lies wholly at or below
    0, the permutation criterion only when the opposite one-sided permutation p (H0: witching >= other, from the same
    label draws) is < 0.05."""
    P = friday_panel(days, closes, vix, start=start, end=end, div_yield=div_yield)
    if len(P["days"]) == 0:
        return {"n": 0, "verdict": "inconclusive", "reason": "no Friday with a Thursday SPY close and VIX"}
    y0, y1 = int(str(P["days"][0])[:4]), int(str(P["days"][-1])[:4])
    witch_all = [d for d in third_fridays(y0, y1, WITCHING_MONTHS) if str(P["days"][0]) <= d <= str(P["days"][-1])]
    opex_m = [d for d in third_fridays(y0, y1, tuple(m for m in range(1, 13) if m not in WITCHING_MONTHS))]
    w = np.isin(P["days"], witch_all); mo = np.isin(P["days"], opex_m)
    x = P["long"]
    g = group_diff(x, w, block, n_boot, seed)
    has_div = bool(div_yield)
    div_txt = ("priced on the dividend forward F = S_Thu(1 - D/S_Thu) on ex-dividend Fridays, K = S_Thu, settled on raw closes"
               if has_div else "K = S_Thu, q = 0 (no dividends supplied)")
    rep = {"label": "MODEL-PRICED", "n": int(w.sum()), "n_other_fridays": int((~w).sum()), "first_day": str(P["days"][0]), "last_day": str(P["days"][-1]),
           "pricing": f"Black-Scholes, sigma = VIX(Thu)/100, T = 1/252, r = 0, {div_txt}; long P&L as a fraction of spot",
           "dividend_treatment": div_txt}
    if g["diff"] is None:
        rep.update(verdict="inconclusive", reason="too few witching or other Fridays"); return rep
    rng = np.random.default_rng(seed); nw = int(w.sum())
    keys = rng.random((n_perm, len(x))).argsort(axis=1)[:, :nw]
    sw = x[keys].sum(1); tot = x.sum()
    perm = sw / nw - (tot - sw) / (len(x) - nw)
    p_perm = float((np.sum(perm >= g["diff"] - 1e-15) + 1) / (n_perm + 1))
    vs_opex = _point_diff(x[w | mo], w[w | mo])
    opex_vs_plain = _point_diff(x[~w], mo[~w])
    no_opex = ~mo
    vs_plain = _point_diff(x[no_opex], w[no_opex])
    fomc_weeks = set()
    for fd in fomc_days:
        dd = _d(fd); mon = dd - timedelta(days=dd.weekday())
        fomc_weeks.add((mon + timedelta(days=4)).isoformat())
    w_fomc = w & np.isin(P["days"], sorted(fomc_weeks))
    ex_fomc = _point_diff(x[~w_fomc], w[~w_fomc])
    split_d = {}
    for lab, m in ((f"pre-{split[:4]}", P["days"] < split), (f"{split[:4]}+", P["days"] >= split)):
        dd = _point_diff(x[m], w[m]); split_d[lab] = {"n_witching": int((w & m).sum()), "diff_bps": None if dd is None else dd * 1e4}
    # dividend: counts and the treatment sensitivity (ignored = ATM premium on the raw move; previous ex-date yield as the
    # point-in-time forecast; dividend-adjusted closes = |S_Fri - F| / F against the ATM premium)
    exd = P["div"] > 0
    div_sens = {}
    if has_div:
        atm = straddle_premium(P["sigma"])
        exs = sorted(div_yield)
        prev_y = {d_: div_yield[exs[k - 1] if k else d_] for k, d_ in enumerate(exs)}       # first ex-date: its own yield
        P_pit = friday_panel(days, closes, vix, start=start, end=end, div_yield=prev_y)
        for lab, xs in (("ignored (q = 0, raw move)", P["move"] - atm), ("previous ex-date yield as forecast", P_pit["long"]),
                        ("dividend-adjusted closes", P["move_fwd"] / (1.0 - P["div"]) - atm)):
            dd = _point_diff(xs, w); div_sens[lab] = None if dd is None else dd * 1e4
    nrm = P["sigma"] / math.sqrt(EQ_PPY)
    rep.update(n_witching_skipped=len(witch_all) - nw, witching_skipped=sorted(set(witch_all) - set(P["days"].tolist())), full=g,
               permutation_p=p_perm, mean_premium_witching_bps=float(P["premium"][w].mean() * 1e4),
               mean_premium_other_bps=float(P["premium"][~w].mean() * 1e4),
               n_ex_dividend_witching=int((w & exd).sum()), n_ex_dividend_other=int((~w & exd).sum()),
               mean_dividend_yield_ex_witching_bps=float(P["div"][w & exd].mean() * 1e4) if (w & exd).any() else None,
               dividend_treatment_sensitivity_diff_bps=div_sens,
               abs_r_over_vix_daily={"witching": float((P["move_fwd"][w] / nrm[w]).mean()), "other": float((P["move_fwd"][~w] / nrm[~w]).mean()),
                                     "move": "dividend-neutral |S_Fri - F| / S_Thu"},
               witching_minus_monthly_opex_bps=None if vs_opex is None else vs_opex * 1e4,
               monthly_opex_minus_non_opex_bps=None if opex_vs_plain is None else opex_vs_plain * 1e4,
               witching_minus_non_opex_bps=None if vs_plain is None else vs_plain * 1e4,
               n_witching_in_fomc_weeks=int(w_fomc.sum()), excluding_fomc_week_witching_bps=None if ex_fomc is None else ex_fomc * 1e4,
               split=split_d, not_run=["15:00-16:00 ET straddle (no 15:00 ET SPY price; hourly bars start 09:30, 10:30, ..., 15:30)"])
    crit = [("witching-minus-other mean long P&L > 0", g["diff"] > 0), ("95% CI excludes 0 (lower bound > 0)", g["ci"][0] > 0),
            ("permutation p < 0.05", p_perm < 0.05)]
    div_reason = (f"dividend: {div_txt} (ex-dividend on {rep['n_ex_dividend_witching']} of {g['n_event']} witching and "
                  f"{rep['n_ex_dividend_other']} other Fridays, mean D/S {_f(rep['mean_dividend_yield_ex_witching_bps'], '.1f')} bps)"
                  if has_div else f"dividend: {div_txt}")
    body = (f"MODEL-PRICED long 1-day ATM SPY straddle Thursday close to Friday close (BS, sigma=VIX(Thu), T=1/252) "
            f"{rep['first_day']}..{rep['last_day']}; {div_reason}: witching Fridays {_bps(g['mean_event'])} vs other Fridays {_bps(g['mean_other'])} bps of spot; "
            f"difference {_bps(g['diff'])} bps (95% CI {_ci_bps(g['ci'])}) over {g['n_event']} witching / {g['n_other']} other Fridays, "
            f"permutation p={p_perm:.4f}; dividend-neutral |r|/(VIX/sqrt252) witching {rep['abs_r_over_vix_daily']['witching']:.2f} vs other "
            f"{rep['abs_r_over_vix_daily']['other']:.2f}; vs monthly opex {_f(rep['witching_minus_monthly_opex_bps'], '+.1f')} bps; "
            f"ex FOMC weeks {_f(rep['excluding_fomc_week_witching_bps'], '+.1f')} bps; "
            + ", ".join(f"{k} {_f(v_['diff_bps'], '+.1f')} bps" for k, v_ in split_d.items())
            + ("; difference with the dividend " + ", ".join(f"{k} {_f(v_, '+.1f')}" for k, v_ in div_sens.items()) + " bps" if div_sens else ""))
    if rep["n"] < min_n:
        # rule 5: the difference and the CI criteria fail decisively when the difference's 95% CI (block 4 weeks) lies
        # wholly at or below 0; the one-sided permutation p < 0.05 criterion is mirrored at its own level by the opposite
        # one-sided permutation test from the same label draws (H0: witching >= other): p_less < 0.05
        down = _decides(g, block) and _ci_below(g["ci"], 0.0)
        p_perm_less = float((np.sum(perm <= g["diff"] + 1e-15) + 1) / (n_perm + 1))
        rep["permutation_p_less"] = p_perm_less
        body += f"; opposite one-sided permutation p (H0 witching >= other) {p_perm_less:.4f}"
        rep_ = _below_min_n(rep, crit, [down, down, _decides(g, block) and p_perm_less < 0.05], rep["n"], min_n,
                            "witching Fridays with SPY and VIX", body)
        rep_["rule5"]["p_opposite_permutation"] = p_perm_less
        return rep_
    v, why = _verdict(crit)
    rep["verdict"] = v
    rep["reason"] = f"{body} — {why}"
    return rep


# ---------------------------------------------------------------------------------------------------- harnesses --

def _releases(archive, name: str, kind: str) -> tuple[list[str], list[str]]:
    return _cached(archive, ("rel", name), lambda: release_days_from_rows(list(_available(archive, name)), kind))


def macro_announcement_day_premium(archive):
    """T-343: SPY release-day (CPI, jobs, FOMC) mean return minus other days > 5 bps/day net, p < 0.05, both halves positive."""
    miss = _missing(archive, ["daily-history-SPY", "fomc-meetings", "macro-release-cpi", "macro-release-employment-situation"])
    if miss:
        return miss
    days, closes = _prices(archive, "SPY", adjusted=True)
    cpi, cpi_drop = _releases(archive, "macro-release-cpi", "cpi")
    es, es_drop = _releases(archive, "macro-release-employment-situation", "es")
    flagged = delayed_release_flags(cpi) + delayed_release_flags(es)
    tlt = _prices(archive, "TLT", adjusted=True) if _has(archive, "daily-history-TLT") else None
    rep = announcement_day_premium(days, closes, cpi, es, _fomc(archive), flagged_days=flagged, tlt=tlt)
    rep["dropped_vintages"] = {"CPI": [d for d in cpi_drop if d >= "1993"], "Employment Situation": [d for d in es_drop if d >= "1993"]}
    return _wrap(rep)


def macro_fomc_im_hm_filter(archive):
    """T-208: MODEL-PRICED IM/HM vs long-straddle P&L on scheduled FOMC days, walk-forward 1994-2009 / 2010-2026."""
    miss = _missing(archive, ["daily-history-SPY", "cboe-VIX-history", "fomc-meetings"])
    if miss:
        return miss
    days, closes = _prices(archive, "SPY", adjusted=False)
    return _wrap(im_hm_filter(days, closes, _index(archive, "cboe-VIX-history"), _fomc(archive), opens=_opens(archive, "SPY")))


def macro_gld_event_straddle(archive):
    """T-224: MODEL-PRICED short GLD straddle (GVZ as IV) on FOMC and CPI days vs other days since 2009-09."""
    miss = _missing(archive, ["daily-history-GLD", "cboe-GVZ-history", "fomc-meetings", "macro-release-cpi"])
    if miss:
        return miss
    days, closes = _prices(archive, "GLD", adjusted=False)
    cpi, _ = _releases(archive, "macro-release-cpi", "cpi")
    es = _releases(archive, "macro-release-employment-situation", "es")[0] if _has(archive, "macro-release-employment-situation") else ()
    spx = None
    if _has(archive, "daily-history-SPY") and _has(archive, "cboe-VIX-history"):
        sd, sc = _prices(archive, "SPY", adjusted=False)
        spx = (sd, sc, _index(archive, "cboe-VIX-history"))
    return _wrap(gld_event_straddle(days, closes, _index(archive, "cboe-GVZ-history"), _fomc(archive), cpi, es_days=es,
                                    exclude_days=_fomc_unscheduled(archive), spx=spx))


def macro_triple_witching_straddle(archive):
    """T-219: MODEL-PRICED long SPY straddle Thursday close to Friday close, witching vs other Fridays since 1993, priced on
    the dividend forward on ex-dividend Fridays (raw closes for K and settlement; dividend yields from adjclose/close)."""
    miss = _missing(archive, ["daily-history-SPY", "cboe-VIX-history"])
    if miss:
        return miss
    days, closes = _prices(archive, "SPY", adjusted=False)
    adays, adj = _prices(archive, "SPY", adjusted=True)
    adj_by = dict(zip(adays, adj))
    divs = ex_dividend_yields(days, closes, [adj_by.get(d, float("nan")) for d in days])     # SPY ex-dates: witching Fridays
    fomc = _fomc(archive) if _has(archive, "fomc-meetings") else ()
    return _wrap(witching_straddle(days, closes, _index(archive, "cboe-VIX-history"), fomc_days=fomc, div_yield=divs))


HARNESSES = {
    "macro_announcement_day_premium": macro_announcement_day_premium,
    "macro_fomc_im_hm_filter": macro_fomc_im_hm_filter,
    "macro_gld_event_straddle": macro_gld_event_straddle,
    "macro_triple_witching_straddle": macro_triple_witching_straddle,
}

THEORY_MAP = {
    "T-343": "macro_announcement_day_premium",
    "T-208": "macro_fomc_im_hm_filter",
    "T-224": "macro_gld_event_straddle",
    "T-219": "macro_triple_witching_straddle",
}
