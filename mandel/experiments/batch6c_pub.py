"""
Batch 6c, group ``pub``: four claims on public and sponsor histories (CFTC COT, Treasury auctions, Sprott trust NAV,
SPDR Gold Trust holdings), fetched by ``mandel.data.public_history``.
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-405  COMEX gold managed-money net position / open interest from the CFTC disaggregated futures-and-options combined
           report (``cftc-cot-disagg-fo-088691``, the library rule's report), z on the trailing 156 weekly reports to t;
           4-week forward GLD return (Monday open after the Friday 15:30 ET release -> the first open 28 calendar days
           later) after z < -2 weeks minus after z > 2 weeks, signal weeks 2006-2026 (min_n 50 extreme weeks of each
           sign): the two-sided 95% CI (8-week blocks) excludes zero on the claimed side AND >= 50 extreme weeks of each
           sign AND the predictive slope of the forward return on z has HAC t <= -2. The trial's park rule ('if either
           tail has < 50 weeks, report insufficient extremes and park') is reported as ``park_condition``.
  * T-442  TLT close of a 10- or 30-year nominal auction day -> close three sessions later, minus the unconditional mean
           3-session return, per ISO-week auction cluster dated at the week's last auction, 2002-2026 (min_n 200
           clusters): excess > 10 bps AND p < 0.05 under both nulls the trial names (daily block bootstrap, block 10, event
           flags held fixed; placement of the clusters in random non-auction weeks), Holm-adjusted over the 6 declared
           variants AND a positive excess in 2002-2013 and in 2014-2026 AND the placebo (clusters moved to non-auction
           weeks) not significant.
  * T-472  long PHYS / short GLD (equal dollars) opened at the next NYSE close after PHYS's Sprott premium/discount is more
           than 1 pp below its trailing 250-observation mean, closed at the next close after it is back at that (rolling)
           mean or 60 sessions after entry; entries 2012-01..2026-09 (min_n 30 trades); 10 bps per leg per trade + 50
           bps/yr GLD borrow: the one-sided 95% lower bound of the mean net return per trade > 0 under both named nulls
           (trades resampled in monthly clusters; block shift of the signal) AND >= 30 trades AND the same sign of the mean
           in 2012-2019 and 2020-2026.
  * T-404  GLD 'Tonnes of Gold' (SPDR archive), 4-week change z-scored on 52 weeks to t, known at the Friday close (t+1
           availability: Thursday's holdings), predicting the next week's GLD return (Monday open -> next Monday open),
           decision weeks 2005-2026 (min_n 1000 weeks): Newey-West HAC t >= 2 over >= 1000 weeks AND a positive slope in
           2005-2015 and in 2016-2026. Failing that the trial parks the claim as 'flows follow price' (``park_condition``);
           the contemporaneous slope and two-way Granger tests are reported alongside, as the trial says.

Conventions
  * Data. Every bundle through ``archive.load``; a row is used only when its ``available_at`` is not after the bundle's
    capture time. ETF prices are Yahoo ``adjclose`` (total return; opens on the same basis, open x adjclose / close) keyed
    by session date. COT rows carry the fetcher's ``available_at`` (Socrata :created_at for the live 2022-07.. rows, the
    CFTC schedule of the era otherwise) and ``pit`` (live / schedule / bound / backcast / not_realtime). Auction rows are
    the fetcher's ``auction-announcement`` rows (available at the end of the announcement day) of held auctions (a
    matching ``auction-result`` row), nominal (``nominal_coupon``: Note/Bond, not TIPS, not FRN) with a 9-/10-/29-/30-Year
    term (reopenings carry x-Year y-Month terms). Sprott and SPDR rows are struck after the close and available at the
    next calendar day 09:30 ET.
  * Point in time (rules 4, 12). T-405: a week enters only when its z is computable from rows public at its own release:
    disaggregated rows dated before 2009-09-01 are backcasts released on 2009-10-20 (pit ``backcast``) and are dropped as
    signal weeks; the reports of 2009-09-01..2009-10-13, whose trailing windows need those backcasts before they were
    public, are dropped too; a report released together with or after a later report (the 2013 shutdown catch-up) is
    superseded by the latest one known at that time (one information set). Every dropped week is counted in the stat, and
    the as-if-live count (backcasts treated as public at their schedule date) is reported. Entry is the first session
    open after the release (the library's 'act at Monday open'). T-442: the cluster date's auction was announced before
    the entry close (checked per cluster; violations reported). T-472: at each NYSE close the latest Sprott value known is
    the one dated strictly before that session (NAV struck after the close, known the next morning); entries and exits
    fill at that close, so a signal on day t trades at the next NYSE close and TSX-only Sprott days are absorbed. T-404:
    the holdings known at the Friday close are the latest trust day available by then (Thursday's: t+1), the trade fills
    at the next session's open (the library's 'evaluated on Friday close, executed Monday open'); the Monday-open
    information set (Friday's holdings) and the Friday-close-to-Friday-close return are reported.
  * Intervals and nulls (rule 6). T-405: studentized circular block bootstrap of the difference of the two tails' means
    on the shared weekly timeline (8-week blocks, the trial's; >= the 4-week overlap), Newey-West slope t with 8 lags.
    T-442: the trial's null bootstrap (daily returns resampled in circular 10-day blocks, event flags fixed, p = share of
    resampled statistics >= the observed) and the placement null (each cluster moved to a random week without a 10- or
    30-year auction, same weekday; 2,000 placements). T-472: studentized bootstrap of trades resampled in entry-month
    clusters (cluster-robust s.e.) and the block-shift null (the position path, which depends only on the signal, shifted
    against the prices by every multiple of 60 sessions). "95% lower bound" is one-sided (the lower end of the two-sided
    90% interval); the two-sided 95% interval is reported. T-404: Newey-West HAC t (lag floor(4 (n/100)^(2/9))). Interval
    ends and p-values are the means over 5 bootstrap seeds with their Monte Carlo s.e. (25 when 5 cannot resolve them).
  * Rule 11. Where a trial names two null constructions (T-442, T-472) a criterion passes only when every one passes.
    Where a claim's wording has two readings, both are judged and both must pass: T-472's '10 bps per leg per trade'
    (10 bps per leg per round trip = 20 bps a trade; 10 bps per leg per side = 40 bps a trade); T-442's 'p < 0.05' with
    the trial's 'Multiple testing: 6 variants Holm' (raw and Holm-adjusted; Holm >= raw).
  * Calendars (rule 10). Every claim names its calendar: T-405 the weekly COT release, T-442 the auction calendar, T-472
    is signal-driven, T-404 the Friday-close / Monday-open week. No grid phase is free.
  * Costs (rule 9) as stated: T-405 GLD 1 bp a side (it cancels in the tail difference; net means reported), T-442 1-2
    bps a round trip (the claim's statistic is gross; net excess reported), T-472 as above, T-404 none enter a slope.
  * Families, declared before any result. T-442: (1) TLT post-auction t -> t+3 (primary), (2) TLT pre-auction t-5 -> t-1
    (expected negative), (3) IEF around 10-year auctions, (4) DGS10 3-session yield change around 10-year auctions
    1990-2026 (bps, sign-flipped), (5) reopening-only vs new-issue clusters (two-sided), (6) the primary without auction
    weeks holding a CPI release or an FOMC decision. T-472: trailing-mean rule (primary), z < -2 entry, fixed -2%/-1%
    levels (control), PSLV/SLV = 4 variants + the disclosed descriptive peek = 5 trials (DSR reported; not in the pass).
    T-405 and T-404: 5 variants each (reported; their passes name no deflation).
  * Below trial.min_n (rule 5): never supported; a failing criterion counts only when it fails decisively (its bound at
    the pass's own confidence wholly on the wrong side, or a count that cannot reach the threshold inside the claim's
    window).

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments.batch6b_bw import _boot_idx, _chunks, _ci_crit, _clean, _decide, all_constructions, mc_escalate, resolve
from mandel.experiments.batch6c_mom import family_dsr, holm_primary
from mandel.experiments.batch6c_rates import nw_lag, ols_nw
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import _hac_var, sharpe_ratio

N_BOOT = 5000                  # bootstrap draws per seed
REPS = 5                       # bootstrap seeds behind every decisive interval end or p-value
SEED = 0
ALPHA = 0.05
NY = ZoneInfo("America/New_York")

GLD_B = "daily-history-GLD"
SLV_B = "daily-history-SLV"
GDX_B = "daily-history-GDX"
TLT_B = "daily-history-TLT"
IEF_B = "daily-history-IEF"
PHYS_B = "daily-history-PHYS"
PSLV_B = "daily-history-PSLV"
DFII10_B = "fred-DFII10"
DGS10_B = "fred-DGS10"
CPI_B = "macro-release-cpi"
FOMC_B = "fomc-meetings"
COT_GOLD = "cftc-cot-disagg-fo-088691"
COT_GOLD_F = "cftc-cot-disagg-f-088691"
COT_SILVER = "cftc-cot-disagg-fo-084691"
AUCT_B = "treasury-auctions"
SPROTT_PHYS = "sprott-phys-nav"
SPROTT_PSLV = "sprott-pslv-nav"
SPDR_GLD = "spdr-gld-archive"


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
        capx = _epoch(cap) if cap else None
        out = []
        for r in archive.load(name):
            av = r.get("available_at")
            if capx is not None and av and _epoch(av) > capx:
                continue
            out.append(r)
        return out
    return _cached(archive, ("rows", name), load)


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _epoch(s) -> float:
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


_ET_MEMO: dict = {}


def et_epoch(day: str, hhmm: str) -> float:
    """POSIX time of ``hhmm`` New York time on ``day``."""
    k = (day, hhmm)
    v = _ET_MEMO.get(k)
    if v is None:
        v = datetime(int(day[:4]), int(day[5:7]), int(day[8:10]), int(hhmm[:2]), int(hhmm[3:5]), tzinfo=NY).timestamp()
        _ET_MEMO[k] = v
    return v


def _daily(archive, name: str) -> dict:
    """{'days', 'close' (split-adjusted), 'adj' (total return), 'open' (adj basis; NaN when missing)} of a Yahoo bundle;
    a bar without adjclose carries the previous adjclose/close ratio."""
    def load():
        by = {}
        for r in _rows(archive, name):
            v = r["value"]
            c = _num(v.get("close"))
            if c is None or c <= 0:
                continue
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
            a, o = _num(v.get("adjclose")), _num(v.get("open"))
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


def _iso_week(day: str) -> tuple:
    y, w, _ = date.fromisoformat(day).isocalendar()
    return (int(y), int(w))


# ================================================================================================= statistics ==

def stud(stat: Callable, cols: Sequence[np.ndarray], block: int, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Studentized (bootstrap-t) circular block bootstrap of a statistic of paired columns (batch6b_bw._stud, with
    resamples whose statistic is undefined dropped). ``stat`` maps row-wise resamples (k, n) to (estimate, s.e.) arrays.
    Returns est, se, the two-sided 95% ``ci`` and 90% ``ci90`` (its lower end = the one-sided 95% lower bound), the
    percentile ``ci_pct``, p (one-sided, H0: est <= 0) and p_lt (H0: est >= 0)."""
    n_boot = N_BOOT if n_boot is None else int(n_boot)
    cols = [np.asarray(c, float) for c in cols]
    n = cols[0].size
    out = {"est": None, "se": None, "ci": [None, None], "ci90": [None, None], "ci_pct": [None, None], "p": None,
           "p_lt": None, "block": None, "n": int(n)}
    if n < 8:
        return out
    bl = max(1, min(int(block), n // 4))
    with np.errstate(all="ignore"):
        d0, se0 = stat(*[c[None, :] for c in cols], bl)
    d0, se0 = float(d0[0]), float(se0[0])
    if not math.isfinite(d0):
        return out
    out.update(est=d0, se=se0 if math.isfinite(se0) else None, block=bl)
    if not (math.isfinite(se0) and se0 > 1e-14):
        out.update(ci=[d0, d0], ci90=[d0, d0], ci_pct=[d0, d0], p=0.0 if d0 > 0 else 1.0, p_lt=0.0 if d0 < 0 else 1.0)
        return out
    rng = np.random.default_rng(seed)
    ts, ds = [], []
    for k in _chunks(n_boot, len(cols) * n):
        idx = _boot_idx(rng, n, bl, k)
        with np.errstate(all="ignore"):
            d, se = stat(*[c[idx] for c in cols], bl)
        ok = np.isfinite(d) & np.isfinite(se) & (se > 1e-14)
        ts.append((d[ok] - d0) / se[ok])
        ds.append(d[np.isfinite(d)])
    t, dd = np.concatenate(ts), np.concatenate(ds)
    if t.size < 20:
        return out
    t_obs = d0 / se0
    q = lambda a: float(np.quantile(t, a))
    out.update(ci=[d0 - q(0.975) * se0, d0 - q(0.025) * se0], ci90=[d0 - q(0.95) * se0, d0 - q(0.05) * se0],
               ci_pct=[float(np.quantile(dd, 0.025)), float(np.quantile(dd, 0.975))],
               p=float((np.sum(t >= t_obs) + 1) / (t.size + 1)), p_lt=float((np.sum(t <= t_obs) + 1) / (t.size + 1)),
               n_valid=int(t.size), n_dropped=int(n_boot - t.size))
    return out


def chi2_sf(x: float, k: int) -> float:
    """P(chi2_k > x) through the regularized upper incomplete gamma Q(k/2, x/2)."""
    if not x > 0:
        return 1.0
    a, z = k / 2.0, x / 2.0
    lg = -z + a * math.log(z) - math.lgamma(a)
    if z < a + 1.0:
        term = s = 1.0 / a
        ap = a
        for _ in range(1000):
            ap += 1.0
            term *= z / ap
            s += term
            if abs(term) < abs(s) * 1e-16:
                break
        return float(min(1.0, max(0.0, 1.0 - s * math.exp(lg))))
    b = z + 1.0 - a
    c, d = 1e300, 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-16:
            break
    return float(min(1.0, max(0.0, math.exp(lg) * h)))


def wald_hc0(y, X, test: Sequence[int]) -> dict:
    """OLS y = X b (X includes the constant) and the White (HC0) Wald test of b[test] = 0: chi2, df, p."""
    y, X = np.asarray(y, float), np.asarray(X, float)
    n, k = X.shape
    if n <= k + 2:
        return {"chi2": None, "df": len(test), "p": None, "n": int(n)}
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ X.T @ y
    e = y - X @ b
    u = X * e[:, None]
    V = XtXi @ (u.T @ u) @ XtXi
    ti = list(test)
    R = b[ti]
    Vr = V[np.ix_(ti, ti)]
    try:
        W = float(R @ np.linalg.solve(Vr, R))
    except np.linalg.LinAlgError:
        return {"chi2": None, "df": len(ti), "p": None, "n": int(n)}
    return {"chi2": W, "df": len(ti), "p": chi2_sf(W, len(ti)), "n": int(n), "coef": [float(v) for v in b[ti]]}


def _lag_matrix(x: np.ndarray, p: int) -> np.ndarray:
    """(n - p, p) of x lagged 1..p, aligned with x[p:]."""
    return np.column_stack([x[p - j:len(x) - j] for j in range(1, p + 1)])


def granger(a, b, p: int = 4) -> dict:
    """Does b help predict a? a_t on a constant, p lags of a and p lags of b; HC0 Wald test of the b lags."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.size <= 3 * p + 5:
        return {"chi2": None, "df": p, "p": None, "n": int(max(0, a.size - p))}
    X = np.column_stack([np.ones(a.size - p), _lag_matrix(a, p), _lag_matrix(b, p)])
    return wald_hc0(a[p:], X, list(range(1 + p, 1 + 2 * p)))


# ----------------------------------------------------------------------------------------------- formatting --

def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


def _bp(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 1e4:+.{nd}f} bps"


def _ci(ci, nd: int = 3, scale: float = 1.0, unit: str = "") -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "CI n/a"
    return f"{lo * scale:+.{nd}f}{unit} to {hi * scale:+.{nd}f}{unit}"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _mean(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(x.mean()) if x.size else None


# ====================================================================================== T-405 gold COT extremes ==

T405_START, T405_END = "2006-01-01", "2026-12-31"
T405_WIN = 156                 # weekly reports in the trailing z window (t included)
T405_THR = 2.0
T405_MIN_N = 50                # extreme weeks of each sign
T405_H_DAYS = 28               # 4-week forward window, calendar days
T405_BLOCK = 8                 # weeks (the trial's)
T405_LAG = 8                   # Newey-West lags (>= the 4-week overlap)
T405_N_VARIANTS = 5
T405_STATUSES = ("backcast", "warmup", "window_not_public", "superseded", "ok")


def cot_weeks(rows: Sequence[dict], win: int = T405_WIN, norm: str = "oi") -> list[dict]:
    """Weekly COT records in report-date order with x = managed-money net / open interest (``norm`` 'oi') or net
    contracts ('raw'), z over the trailing ``win`` reports (t included, sample sd), the release time ``av`` (the row's
    available_at) and a point-in-time status:
      backcast           the row itself was not public at its schedule release (pit 'backcast');
      warmup             fewer than ``win`` reports up to t;
      window_not_public  some row of the trailing window became public only after t's own release;
      superseded         a later report was public no later than t's release (catch-ups: one information set);
      ok                 a valid point-in-time signal week.
    Rows with pit 'not_realtime' are dropped before the windows are built."""
    recs, seen = [], set()
    for r in rows:
        v = r.get("value") or {}
        rd = str(v.get("report_date") or v.get("report_date_as_yyyy_mm_dd") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", rd) or rd in seen or v.get("pit") == "not_realtime":
            continue
        lo, sh, oi = _num(v.get("m_money_positions_long_all")), _num(v.get("m_money_positions_short_all")), _num(v.get("open_interest_all"))
        if lo is None or sh is None or not oi or oi <= 0 or not r.get("available_at"):
            continue
        seen.add(rd)
        net = lo - sh
        rule = v.get("release_rule")
        recs.append({"report_date": rd, "av": _epoch(r["available_at"]), "available_at": r["available_at"], "pit": v.get("pit"),
                     "rule_av": _epoch(rule) if rule else _epoch(r["available_at"]), "net": net, "oi": oi,
                     "x": net / oi if norm == "oi" else net, "created_at": v.get("created_at")})
    recs.sort(key=lambda q: q["report_date"])
    n = len(recs)
    if not n:
        return recs
    av = np.array([q["av"] for q in recs], float)
    x = np.array([q["x"] for q in recs], float)
    suf = np.full(n + 1, np.inf)
    for i in range(n - 1, -1, -1):
        suf[i] = min(suf[i + 1], av[i])
    cs, cs2 = np.concatenate([[0.0], np.cumsum(x)]), np.concatenate([[0.0], np.cumsum(x * x)])
    for i, q in enumerate(recs):
        q["z"] = None
        if i >= win - 1:
            s, s2 = cs[i + 1] - cs[i + 1 - win], cs2[i + 1] - cs2[i + 1 - win]
            mu = s / win
            var = max((s2 - win * mu * mu) / (win - 1), 0.0)
            q["z"] = float((x[i] - mu) / math.sqrt(var)) if var > 0 else None
        if q["pit"] == "backcast":
            q["status"] = "backcast"
        elif i < win - 1:
            q["status"] = "warmup"
        elif float(av[i + 1 - win:i + 1].max()) > av[i]:
            q["status"] = "window_not_public"
        elif suf[i + 1] <= av[i]:
            q["status"] = "superseded"
        else:
            q["status"] = "ok"
    return recs


def fwd_returns(px: dict, ts, horizon_days: int = T405_H_DAYS, at: str = "open") -> dict:
    """Forward returns from decision times ``ts`` (POSIX): ``at`` 'open' enters at the first session open (09:30 ET)
    strictly after t and exits at the open of the first session on or after entry + ``horizon_days`` calendar days;
    'close' enters at the first session close (16:00 ET) at or after t and exits likewise at the close. NaN when the
    exit is beyond the data or a price is missing."""
    days = px["days"]
    ts = np.asarray(ts, float)
    n = len(days)
    ret = np.full(ts.size, np.nan)
    e_idx = np.full(ts.size, -1)
    x_idx = np.full(ts.size, -1)
    if not n or not ts.size:
        return {"ret": ret, "e": e_idx, "x": x_idx}
    hh = "09:30" if at == "open" else "16:00"
    ep = np.array([et_epoch(d, hh) for d in days])
    lv = px["open"] if at == "open" else px["adj"]
    es = np.searchsorted(ep, ts, side="right" if at == "open" else "left")
    for k, e in enumerate(es):
        if e >= n:
            continue
        tgt = (date.fromisoformat(days[e]) + timedelta(days=horizon_days)).isoformat()
        x = bisect.bisect_left(days, tgt)
        if x >= n or not (np.isfinite(lv[e]) and np.isfinite(lv[x])):
            continue
        ret[k], e_idx[k], x_idx[k] = lv[x] / lv[e] - 1.0, e, x
    return {"ret": ret, "e": e_idx, "x": x_idx}


def _tail_diff_stat(X, S, L, bw):
    """Row-wise mean(X | S) - mean(X | L) and its s.e. from the influence function S (x - mS)/pS - L (x - mL)/pL with a
    Bartlett long-run variance (bandwidth ``bw``); undefined (NaN) when a tail is empty."""
    n = X.shape[1]
    nS, nL = S.sum(axis=1), L.sum(axis=1)
    with np.errstate(all="ignore"):
        mS, mL = (X * S).sum(axis=1) / nS, (X * L).sum(axis=1) / nL
        pS, pL = nS / n, nL / n
        z = S * (X - mS[:, None]) / pS[:, None] - L * (X - mL[:, None]) / pL[:, None]
    z = np.where(np.isfinite(z), z, 0.0)
    se = np.sqrt(_hac_var(z, bw) / n)
    d = mS - mL
    bad = (nS < 1) | (nL < 1)
    return np.where(bad, np.nan, d), np.where(bad, np.nan, se)


def cot_study(weeks: Sequence[dict], px: dict, start: str = T405_START, end: str = T405_END, statuses: Sequence[str] = ("ok",),
              decision: str = "av", at: str = "open", horizon_days: int = T405_H_DAYS) -> dict:
    """The signal table: weeks with a status in ``statuses``, a z, a report date in [start, end] and a complete forward
    return from the decision time (``decision`` 'av' = the row's available_at, 'rule' = its schedule release, the
    as-if-live reading of backcast rows)."""
    sel = [q for q in weeks if q["status"] in statuses and q.get("z") is not None and start <= q["report_date"] <= end]
    ts = [q["av"] if decision == "av" else q["rule_av"] for q in sel]
    fw = fwd_returns(px, ts, horizon_days, at)
    ok = np.isfinite(fw["ret"])
    keep = [q for q, o in zip(sel, ok) if o]
    return {"dates": [q["report_date"] for q in keep], "z": np.array([q["z"] for q in keep], float),
            "fwd": fw["ret"][ok], "entry": [px["days"][e] for e in fw["e"][ok]], "n_incomplete": int((~ok).sum()),
            "n_selected": len(sel)}


def _weeks_left(last: Optional[str], end: str) -> int:
    """Weekly reports still possible after ``last`` up to ``end`` (inclusive)."""
    if not last:
        return 0
    return max(0, (date.fromisoformat(end) - date.fromisoformat(last)).days // 7)


def judge_cot(fwd, z, remaining_weeks: int = 0, thr: float = T405_THR, min_n: int = T405_MIN_N, block: int = T405_BLOCK,
              lag: int = T405_LAG, reps: Optional[int] = None) -> dict:
    """T-405 criteria on a signal table (fwd, z)."""
    fwd, z = np.asarray(fwd, float), np.asarray(z, float)
    S, L = (z < -thr).astype(float), (z > thr).astype(float)
    nS, nL = int(S.sum()), int(L.sum())
    n_tail = min(nS, nL)
    if fwd.size >= 8 and nS and nL:
        bt = mc_escalate(lambda seed: stud(_tail_diff_stat, [fwd, S, L], block, N_BOOT, seed),
                         lambda t: _ci_crit(t, "gt", 0.0, "")[1], REPS if reps is None else reps, SEED)
    else:
        bt = {"est": None, "ci": [None, None]}
    reg = ols_nw(fwd, z, lag) if fwd.size > 10 else {"coef": None, "t": None}
    t = (reg.get("t") or [None, None])[1]
    # a week is in at most one tail, so both reach min_n only if the two shortfalls together fit in the weeks left
    short = max(0, min_n - nS) + max(0, min_n - nL)
    dec_count = short > remaining_weeks
    pc = lambda v: _pc(v, 2)
    crit = [_ci_crit(bt, "gt", 0.0, f"mean 4-week GLD return after z < -{thr:g} minus after z > {thr:g} "
                                    f"({pc(bt.get('est'))}): two-sided 95% CI ({block}-week blocks) excludes zero", pc),
            (f">= {min_n} extreme weeks of each sign (z > {thr:g}: {nL}, z < -{thr:g}: {nS}"
             + (f"; the tails need {short} more extreme weeks in all (a week is in at most one tail) and at most "
                f"{remaining_weeks} more weekly reports fit in the claim's window"
                + (f", so both tails cannot reach {min_n}" if dec_count else "") if short else "") + ")",
             n_tail >= min_n, dec_count),
            (f"predictive slope of the 4-week return on z, Newey-West t <= -2 (t {_s(t, 2)}, {lag} lags, {fwd.size} weeks)",
             None if t is None else t <= -2.0, t is not None and t >= 2.0)]
    v, why = _decide(crit, n_tail, min_n, "extreme weeks (the smaller tail)")
    return {"n_short_tail": nS, "n_long_tail": nL, "n_tail": n_tail, "n_weeks": int(fwd.size), "boot": bt, "slope": reg,
            "mean_short_tail": _mean(fwd[S > 0]), "mean_long_tail": _mean(fwd[L > 0]), "park_condition": n_tail < min_n,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _tails_brief(tab: dict, thr: float = T405_THR) -> dict:
    z, f = tab["z"], tab["fwd"]
    S, L = z < -thr, z > thr
    return {"n_weeks": int(z.size), "n_short_tail": int(S.sum()), "n_long_tail": int(L.sum()),
            "mean_short_tail": _mean(f[S]), "mean_long_tail": _mean(f[L]),
            "diff": (_mean(f[S]) - _mean(f[L])) if S.any() and L.any() else None}


def _asof(series: dict):
    ks = sorted(series)
    vs = [series[k] for k in ks]
    def at(day: str, strict: bool = True) -> Optional[float]:
        j = (bisect.bisect_left(ks, day) if strict else bisect.bisect_right(ks, day)) - 1
        return vs[j] if j >= 0 else None
    return at


def b6c_pub_gold_cot_extremes(archive):
    """T-405: 4-week GLD returns after extreme managed-money positioning in COMEX gold (z > 2 vs z < -2)."""
    miss = _missing(archive, [COT_GOLD, GLD_B])
    if miss:
        return miss
    weeks = cot_weeks(_rows(archive, COT_GOLD))
    gld = _daily(archive, GLD_B)
    tab = cot_study(weeks, gld)
    if tab["z"].size == 0:
        v, why = _decide([("signal weeks with a point-in-time z and a complete 4-week GLD return", None)], 0, T405_MIN_N,
                         "extreme weeks (the smaller tail)")
        return _out({"n_weeks": 0}, 0, v, "no point-in-time COT signal week with a complete forward GLD return — " + why)
    last_report = max((q["report_date"] for q in weeks if q["status"] == "ok"), default=None)
    rem = _weeks_left(tab["dates"][-1], T405_END)
    j = judge_cot(tab["fwd"], tab["z"], rem)
    cnt = defaultdict(int)
    for q in weeks:
        if T405_START <= q["report_date"] <= T405_END:
            cnt[q["status"]] += 1
    span = lambda st: [q["report_date"] for q in weeks if q["status"] == st]
    bc, wn, sp = span("backcast"), span("window_not_public"), span("superseded")
    # live-stamped rows whose Socrata creation time is the bundle's bulk history load (not a publication): their
    # available_at is later than their schedule release (conservative); kept as stamped, the schedule reading reported
    bulk = min((q["created_at"] for q in weeks if q.get("created_at")), default=None)
    bulk_rows = [q["report_date"] for q in weeks if q["pit"] == "live" and bulk and q.get("created_at") == bulk]
    # as-if-live (NOT point in time): backcast rows treated as public at their schedule release
    live_like = cot_study(weeks, gld, statuses=("ok", "backcast", "window_not_public", "superseded"), decision="rule")
    sens = {"as_if_live_backcast": _tails_brief(live_like)}
    raw = cot_study(cot_weeks(_rows(archive, COT_GOLD), norm="raw"), gld)
    sens["raw_net_contracts"] = _tails_brief(raw)
    close_tab = cot_study(weeks, gld, at="close")
    sens["release_day_close_entry"] = _tails_brief(close_tab)
    sens["schedule_release_times"] = _tails_brief(cot_study(weeks, gld, statuses=("ok", "superseded"), decision="rule"))
    if _has(archive, COT_GOLD_F):
        sens["futures_only_report"] = _tails_brief(cot_study(cot_weeks(_rows(archive, COT_GOLD_F)), gld))
    if _has(archive, COT_SILVER) and _has(archive, SLV_B):
        sens["silver_084691_slv"] = _tails_brief(cot_study(cot_weeks(_rows(archive, COT_SILVER)), _daily(archive, SLV_B)))
    if _has(archive, GDX_B):
        sens["gold_z_gdx_returns"] = _tails_brief(cot_study(weeks, _daily(archive, GDX_B)))
    ctrl = None
    if _has(archive, DFII10_B):
        rr = _asof(_series(archive, DFII10_B))
        d_rr = []
        for d in tab["entry"]:
            a, b = rr(d), rr((date.fromisoformat(d) - timedelta(days=28)).isoformat())
            d_rr.append(a - b if a is not None and b is not None else np.nan)
        d_rr = np.array(d_rr, float)
        m = np.isfinite(d_rr)
        if m.sum() > 20:
            o = ols_nw(tab["fwd"][m], np.column_stack([tab["z"][m], d_rr[m]]), T405_LAG)
            ctrl = {"n": int(m.sum()), "coef_z": (o.get("coef") or [None, None])[1], "t_z": (o.get("t") or [None, None])[1],
                    "coef_d_dfii10": (o.get("coef") or [None, None, None])[2], "t_d_dfii10": (o.get("t") or [None, None, None])[2]}
    z, f, ds = tab["z"], tab["fwd"], tab["dates"]
    reg_ = lambda a, b: {"short": [float(v) for v, zz, d in zip(f, z, ds) if a <= d <= b and zz < -T405_THR],
                         "long": [float(v) for v, zz, d in zip(f, z, ds) if a <= d <= b and zz > T405_THR]}
    regimes = {k: {"n_short": len(r["short"]), "mean_short": _mean(r["short"]), "n_long": len(r["long"]), "mean_long": _mean(r["long"])}
               for k, r in (("2013", reg_("2013-01-01", "2013-12-31")), ("2020", reg_("2020-01-01", "2020-12-31")))}
    by_year = defaultdict(lambda: [0, 0])
    for zz, d in zip(z, ds):
        if zz > T405_THR:
            by_year[d[:4]][0] += 1
        elif zz < -T405_THR:
            by_year[d[:4]][1] += 1
    bt, sl = j["boot"], j["slope"]
    lt = [d for d, zz in zip(ds, z) if zz > T405_THR]
    park = j["park_condition"]
    reason = (f"CFTC disaggregated F&O combined report, COMEX gold 088691: managed-money net / open interest, z over the trailing "
              f"{T405_WIN} reports; GLD entered at the first open after the release (Friday 15:30 ET or its Socrata/schedule "
              f"time), 4-week forward return to the first open 28 days later. Point in time: {cnt['backcast']} backcast weeks "
              f"({bc[0] if bc else 'n/a'}..{bc[-1] if bc else 'n/a'}, released 2009-10-20) and {cnt['window_not_public']} weeks whose "
              f"156-week window needed them before they were public ({wn[0] if wn else 'n/a'}..{wn[-1] if wn else 'n/a'}) are dropped, "
              f"{cnt['superseded']} reports superseded by a later report released no later ({', '.join(sp) if sp else 'none'}"
              + (f"; {len(bulk_rows)} live-stamped rows {bulk_rows[0]}..{bulk_rows[-1]} carry the Socrata bulk-load time {bulk} as "
                 f"available_at, later than their Friday schedule release: kept as stamped (conservative); on schedule times "
                 f"the tails are {sens['schedule_release_times']['n_long_tail']}/{sens['schedule_release_times']['n_short_tail']}"
                 if bulk_rows else "") + "), "
              f"{cnt['warmup']} warm-up weeks; {j['n_weeks']} signal weeks {ds[0]}..{ds[-1]} ({tab['n_incomplete']} without a "
              f"complete forward window). Tails: z > 2 {j['n_long_tail']} weeks (mean {_pc(j['mean_long_tail'])}; "
              f"{lt[0] if lt else 'n/a'}..{lt[-1] if lt else 'n/a'}), z < -2 {j['n_short_tail']} weeks (mean "
              f"{_pc(j['mean_short_tail'])}); difference {_pc(bt.get('est'))} (95% CI {_ci(bt.get('ci'), 2, 100, '%')}); slope "
              f"{_s((sl.get('coef') or [None, None])[1], 5)} per unit z (NW t {_s((sl.get('t') or [None, None])[1], 2)}). "
              f"PARK CONDITION {'HOLDS' if park else 'does not hold'}: "
              f"{'insufficient extremes (a tail below 50 weeks), the trial parks the claim' if park else 'both tails have >= 50 weeks'}. "
              f"Reported: as-if-live with backcasts (NOT point in time) {sens['as_if_live_backcast']['n_long_tail']}/"
              f"{sens['as_if_live_backcast']['n_short_tail']} weeks z > 2 / z < -2; raw net contracts "
              f"{sens['raw_net_contracts']['n_long_tail']}/{sens['raw_net_contracts']['n_short_tail']}"
              + (f"; futures-only {sens['futures_only_report']['n_long_tail']}/{sens['futures_only_report']['n_short_tail']}"
                 if "futures_only_report" in sens else "")
              + (f"; silver/SLV {sens['silver_084691_slv']['n_long_tail']}/{sens['silver_084691_slv']['n_short_tail']} (difference "
                 f"{_pc(sens['silver_084691_slv']['diff'])})" if "silver_084691_slv" in sens else "")
              + (f"; DFII10-controlled slope t {_s(ctrl['t_z'], 2)}" if ctrl else "; DFII10 control not computed")
              + f"; GLD 1 bp a side cancels in the difference — " + j["why"])
    stat = {"n_weeks": j["n_weeks"], "first_week": ds[0], "last_week": ds[-1], "last_ok_report": last_report,
            "n_long_tail": j["n_long_tail"], "n_short_tail": j["n_short_tail"], "mean_long_tail": j["mean_long_tail"],
            "mean_short_tail": j["mean_short_tail"], "boot": bt, "slope": sl, "park_condition": park,
            "park_rule": "if either tail has < 50 weeks, report 'insufficient extremes' and park",
            "dropped": {k: int(cnt[k]) for k in T405_STATUSES if k != "ok"}, "dropped_backcast_span": [bc[0], bc[-1]] if bc else None,
            "dropped_window_not_public_span": [wn[0], wn[-1]] if wn else None, "superseded_reports": sp,
            "bulk_load_stamped_rows": bulk_rows, "bulk_load_time": bulk if bulk_rows else None,
            "remaining_weeks_in_window": rem, "sensitivities": sens, "dfii10_control": ctrl, "regimes": regimes,
            "tails_by_year": {k: {"z_gt_2": v[0], "z_lt_m2": v[1]} for k, v in sorted(by_year.items())},
            "net_of_costs_note": "1 bp a side on GLD shifts both tail means equally; the difference is unchanged",
            "n_variants_declared": T405_N_VARIANTS, "criteria": j["criteria"], "rule10": "the weekly COT release calendar"}
    return _out(stat, j["n_tail"], j["verdict"], reason)


# ====================================================================================== T-442 Treasury auctions ==

T442_START, T442_END = "2002-01-01", "2026-12-31"
T442_SPLIT = "2014-01-01"
T442_DGS10_START = "1990-01-01"
T442_THR = 0.0010              # 10 bps
T442_MIN_N = 200
T442_BLOCK = 10
T442_BOOT = 2000               # null draws per seed (x REPS seeds)
T442_N_PLACE = 2000            # placements per seed
T442_COSTS = (0.0001, 0.0002)  # 1-2 bps a round trip
T442_VARIANTS = ("V1_tlt_post", "V2_tlt_pre", "V3_ief_10y", "V4_dgs10_10y", "V5_reopen_vs_new", "V6_ex_cpi_fomc")
_TERM = re.compile(r"^(9|10|29|30)-Year")


def nominal_auctions(rows: Sequence[dict]) -> list[dict]:
    """Held nominal 9/10/29/30-Year Note/Bond auctions from the fetcher's announcement rows: {date, term, fam ('10' or
    '30'), reopening, av (announcement available_at, POSIX), cusip}."""
    held = {r.get("key") for r in rows if r.get("kind") == "auction-result"}
    out = []
    for r in rows:
        if r.get("kind") != "auction-announcement":
            continue
        v = r.get("value") or {}
        m = _TERM.match(str(v.get("security_term") or ""))
        ad = str(v.get("auction_date") or "")[:10]
        if not m or not v.get("nominal_coupon") or r.get("key") not in held or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ad):
            continue
        out.append({"date": ad, "term": v.get("security_term"), "fam": "10" if m.group(1) in ("9", "10") else "30",
                    "reopening": str(v.get("reopening")) == "Yes", "av": _epoch(r["available_at"]) if r.get("available_at") else None,
                    "cusip": v.get("cusip")})
    return sorted(out, key=lambda a: (a["date"], a["fam"], str(a["cusip"])))


def auction_clusters(auctions: Sequence[dict], sessions: Sequence[str], fams: Sequence[str] = ("10", "30")) -> dict:
    """ISO-week clusters of the auctions in ``fams``, dated at the week's last auction held on a session in ``sessions``.
    Each: {date, week, n, fams, reopen_only, ann_ok (every auction on the cluster date was announced before its 16:00 ET
    close)}. Also the weeks holding any of these auctions and the weeks dropped (no auction on a session)."""
    ss = set(sessions)
    wk = defaultdict(list)
    for a in auctions:
        if a["fam"] in fams:
            wk[_iso_week(a["date"])].append(a)
    out, dropped = [], []
    lo_d, hi_d = (min(sessions), max(sessions)) if sessions else ("", "")
    for w in sorted(wk):
        al = wk[w]
        held = sorted({a["date"] for a in al if a["date"] in ss})
        if not held:
            if any(lo_d <= a["date"] <= hi_d for a in al):            # inside the series' span: a real gap, reported
                dropped.append(w)
            continue
        d = held[-1]
        on = [a for a in al if a["date"] == d]
        out.append({"date": d, "week": w, "n": len(al), "fams": sorted({a["fam"] for a in al}),
                    "reopen_only": all(a["reopening"] for a in al),
                    "ann_ok": all(a["av"] is not None and a["av"] <= et_epoch(d, "16:00") for a in on)})
    return {"clusters": out, "weeks": set(wk), "dropped_weeks": dropped}


def _null_draws(inc: np.ndarray, W: np.ndarray, span: int, kind: str, block: int, n_boot: int, seed: int) -> np.ndarray:
    """(n_boot, q) weighted statistics R* @ W under the trial's null: the daily increments (log returns, or yield changes)
    resampled in circular blocks with the event weights W (M starts x q) held fixed; R*_s is the ``span``-session return
    (price) or the sign-flipped change in bps (yield) from start s of the resampled path."""
    n_inc = inc.size
    rng = np.random.default_rng(seed)
    out = []
    for k in _chunks(n_boot, n_inc):
        idx = _boot_idx(rng, n_inc, block, k)
        cum = np.concatenate([np.zeros((k, 1)), np.cumsum(inc[idx], axis=1)], axis=1)
        dl = cum[:, span:] - cum[:, :-span]
        R = np.expm1(dl) if kind == "price" else -100.0 * dl
        out.append(R @ W)
    return np.concatenate(out, axis=0)


def event_test(series: dict, clusters: Sequence[dict], lo: int, hi: int, kind: str = "price", start: str = T442_START,
               end: str = T442_END, side: str = "gt", auction_weeks: frozenset = frozenset(), split: Optional[str] = None,
               contrast: Optional[Sequence[bool]] = None, thr: float = 0.0, block: int = T442_BLOCK, n_boot: Optional[int] = None,
               n_place: Optional[int] = None, seed: int = SEED) -> dict:
    """Event-window effect of ``clusters`` on ``series`` ({'days', 'lv'}: price levels or yields in percent) inside
    [start, end]. Window from session e + lo to e + hi (e = the cluster date). Statistic: the mean window return over the
    clusters minus the mean over every start in the sample (``contrast``: the mean over clusters labelled True minus over
    those labelled False). Nulls: the trial's daily block bootstrap with flags fixed (``_null_draws``) and placement
    (each cluster moved to a random week outside ``auction_weeks``, same weekday; for a contrast, the labels permuted).
    Also the pooled placebo (the average of the placements, tested two-sided under the bootstrap), and the halves
    before/after ``split``. ``side`` 'gt' / 'lt' / 'two' sets the p reported as p_boot and p_place."""
    n_boot = T442_BOOT if n_boot is None else int(n_boot)
    n_place = T442_N_PLACE if n_place is None else int(n_place)
    keep = [i for i, d in enumerate(series["days"]) if start <= d <= end]
    days = [series["days"][i] for i in keep]
    lv = np.asarray(series["lv"], float)[keep]
    span = hi - lo
    n = len(days)
    out = {"n_events": 0, "obs": None, "p_boot": None, "p_place": None}
    if n < span + 30:
        return out
    inc = np.diff(np.log(lv)) if kind == "price" else np.diff(lv)
    cum = np.concatenate([[0.0], np.cumsum(inc)])
    dl = cum[span:] - cum[:-span]
    R = np.expm1(dl) if kind == "price" else -100.0 * dl
    M = R.size
    pos = {d: i for i, d in enumerate(days)}
    ev, lab, wd = [], [], []
    for k, c in enumerate(clusters):
        i = pos.get(c["date"])
        if i is None:
            continue
        s = i + lo
        if 0 <= s < M:
            ev.append(s)
            lab.append(bool(contrast[k]) if contrast is not None else True)
            wd.append(date.fromisoformat(c["date"]).weekday())
    ev, lab, wd = np.array(ev, int), np.array(lab, bool), np.array(wd, int)
    K = int(ev.size)
    out["n_events"] = K
    if K < 4 or (contrast is not None and (lab.sum() < 2 or (~lab).sum() < 2)):
        return out
    cols, names = [], []
    if contrast is None:
        w = np.full(M, -1.0 / M)
        np.add.at(w, ev, 1.0 / K)
        out.update(event_mean=float(R[ev].mean()), uncond_mean=float(R.mean()))
    else:
        w = np.zeros(M)
        np.add.at(w, ev[lab], 1.0 / lab.sum())
        np.add.at(w, ev[~lab], -1.0 / (~lab).sum())
        out.update(mean_true=float(R[ev[lab]].mean()), mean_false=float(R[ev[~lab]].mean()), n_true=int(lab.sum()),
                   n_false=int((~lab).sum()))
    cols.append(w)
    names.append("main")
    sdays = np.array(days[:M])
    if split and contrast is None:
        for nm, m_ev, m_u in (("h1", sdays[ev] < split, sdays < split), ("h2", sdays[ev] >= split, sdays >= split)):
            if m_ev.sum() >= 2 and m_u.sum() > span:
                wh = np.where(m_u, -1.0 / m_u.sum(), 0.0)
                np.add.at(wh, ev[m_ev], 1.0 / m_ev.sum())
                cols.append(wh)
                names.append(nm)
    rng = np.random.default_rng(seed + 7919)
    place = None
    if contrast is None:
        byw = defaultdict(dict)
        for i, d in enumerate(days):
            byw[_iso_week(d)][date.fromisoformat(d).weekday()] = i
        pool = []
        for w_, mp in byw.items():
            if w_ in auction_weeks:
                continue
            row = []
            for k in range(5):
                cand = [mp[j] for j in sorted(mp, key=lambda j: (abs(j - k), j))]
                row.append(cand[0] + lo)
            if all(0 <= s < M for s in row):
                pool.append(row)
        P = np.array(pool, int).reshape(-1, 5)
        if P.shape[0] >= 2:
            if P.shape[0] >= K:
                ch = np.argsort(rng.random((n_place, P.shape[0])), axis=1)[:, :K]
            else:
                ch = rng.integers(0, P.shape[0], (n_place, K))
            Sp = P[ch, wd[None, :]]
            stat_k = R[Sp].mean(axis=1) - R.mean()
            cnt = np.bincount(Sp.ravel(), minlength=M) / Sp.size
            cols.append(cnt - 1.0 / M)
            names.append("placebo")
            place = {"stat": stat_k, "pool_weeks": int(P.shape[0])}
    else:
        perm = np.array([rng.permutation(lab) for _ in range(n_place)])
        Rv = R[ev][None, :]
        st = (Rv * perm).sum(axis=1) / perm.sum(axis=1) - (Rv * ~perm).sum(axis=1) / (~perm).sum(axis=1)
        place = {"stat": st, "pool_weeks": None}
    Wm = np.column_stack(cols)
    obs = R @ Wm
    draws = _null_draws(inc, Wm, span, kind, block, n_boot, seed)
    B = draws.shape[0]
    pge = (1 + (draws >= obs[None, :]).sum(axis=0)) / (B + 1)
    ple = (1 + (draws <= obs[None, :]).sum(axis=0)) / (B + 1)
    pick = lambda j: float(pge[j] if side == "gt" else ple[j] if side == "lt" else min(1.0, 2 * min(pge[j], ple[j])))
    o = float(obs[0])
    out.update(obs=o, p_boot=pick(0), p_ge=float(pge[0]), p_le=float(ple[0]),
               p_vs_thr=float((1 + (draws[:, 0] >= o - thr).sum()) / (B + 1)) if thr else None,
               null_q=[float(np.quantile(draws[:, 0], q)) for q in (0.025, 0.5, 0.975)], n_boot=int(B))
    for nm in ("h1", "h2"):
        if nm in names:
            j = names.index(nm)
            out[nm] = {"obs": float(obs[j]), "p_ge": float(pge[j]), "p_le": float(ple[j])}
    if place is not None:
        stt = place["stat"]
        if side == "gt":
            pp = (1 + (stt >= o).sum()) / (stt.size + 1)
        elif side == "lt":
            pp = (1 + (stt <= o).sum()) / (stt.size + 1)
        else:
            pp = (1 + (np.abs(stt) >= abs(o)).sum()) / (stt.size + 1)
        pm = (1 + (stt <= o).sum()) / (stt.size + 1) if side == "gt" else (1 + (stt >= o).sum()) / (stt.size + 1)
        out.update(p_place=float(pp), p_place_mirror=float(pm), place_mean=float(stt.mean()),
                   place_q=[float(np.quantile(stt, q)) for q in (0.025, 0.975)], n_place=int(stt.size), pool_weeks=place["pool_weeks"])
        if "placebo" in names:
            j = names.index("placebo")
            out["placebo"] = {"obs": float(obs[j]), "p_two": float(min(1.0, 2 * min(pge[j], ple[j])))}
    return out


_MC_KEYS = ("obs", "p_boot", "p_ge", "p_le", "p_place", "p_place_mirror", "p_vs_thr")


def event_mc(reps: Optional[int] = None, **kw) -> dict:
    """``event_test`` over ``reps`` seeds: p-values (and the placement and placebo p's) are the seed means, with their
    Monte Carlo s.e. under '<key>_mc_se'."""
    reps = REPS if reps is None else int(reps)
    rs = [event_test(seed=SEED + 101 * k, **kw) for k in range(max(1, reps))]
    out = dict(rs[0])
    r_ = len(rs)
    def avg(get):
        vals = [get(r) for r in rs]
        if any(v is None for v in vals):
            return None, None
        return float(np.mean(vals)), (float(np.std(vals, ddof=1) / math.sqrt(r_)) if r_ > 1 else 0.0)
    for key in _MC_KEYS:
        if key in out:
            out[key], out[key + "_mc_se"] = avg(lambda r: r.get(key))
    for nm in ("h1", "h2"):
        if nm in out:
            out[nm] = dict(out[nm])
            for key in ("p_ge", "p_le"):
                out[nm][key], out[nm][key + "_mc_se"] = avg(lambda r: (r.get(nm) or {}).get(key))
    if "placebo" in out:
        out["placebo"] = dict(out["placebo"])
        out["placebo"]["p_two"], out["placebo"]["p_two_mc_se"] = avg(lambda r: (r.get("placebo") or {}).get("p_two"))
    out["reps"] = r_
    return out


def _holm_crit(fam: dict, se: Optional[float], label: str) -> tuple:
    """(name, ok, decisive) for 'p < 0.05' on the primary: raw p and its Holm-adjusted p over the declared family
    (bounded when some variants are not computable), resolved against Monte Carlo error."""
    p = fam.get(T442_VARIANTS[0])
    h = holm_primary(fam, T442_VARIANTS[0])
    if p is None:
        return f"{label}: p n/a", None, False
    mult = (h["adj"] / p) if (h["adj"] is not None and p > 0) else len(fam)
    ok_raw, note_raw = resolve(p, se, ALPHA, "lt")
    if h["adj"] is not None:
        ok_h, note_h = resolve(h["adj"], (se or 0.0) * mult, ALPHA, "lt")
        htxt = f"Holm-adjusted {h['adj']:.4f} over {h['m']} variants{note_h}"
    elif h["hi"] is not None and h["hi"] < ALPHA:
        ok_h, htxt = True, f"Holm-adjusted <= {h['hi']:.4f} ({h['n_known']}/{h['m']} variants computed)"
    elif h["lo"] is not None and h["lo"] >= ALPHA:
        ok_h, htxt = False, f"Holm-adjusted >= {h['lo']:.4f} ({h['n_known']}/{h['m']} variants computed)"
    else:
        ok_h, htxt = None, f"Holm-adjusted not resolved ({h['n_known']}/{h['m']} variants computed)"
    ok = None if (ok_raw is None or ok_h is None) else (ok_raw and ok_h)
    if ok_raw is False or ok_h is False:
        ok = False
    return f"{label}: p {p:.4f}{note_raw}, {htxt}", ok, False


def judge_auction(prim: dict, fam_boot: dict, fam_place: dict, n: int, min_n: int = T442_MIN_N, thr: float = T442_THR) -> dict:
    """T-442 criteria from the primary ``event_mc`` result and the variant families of p-values."""
    o = prim.get("obs")
    q = prim.get("null_q") or [None, None, None]
    # decisive (below min_n only): the excess's null-based 95% interval obs - q97.5 .. obs - q2.5 wholly below 10 bps
    dec1 = o is not None and q[0] is not None and (o - q[0]) < thr
    c1 = (f"excess > {thr * 1e4:.0f} bps ({_bp(o)} = cluster mean {_bp(prim.get('event_mean'))} - unconditional "
          f"{_bp(prim.get('uncond_mean'))})", None if o is None else o > thr, dec1)
    rb = _holm_crit(fam_boot, prim.get("p_boot_mc_se"), "daily block bootstrap (block 10), event flags fixed")
    rp = _holm_crit(fam_place, prim.get("p_place_mc_se"), f"placement in random non-auction weeks ({prim.get('n_place')} per seed)")
    rb = (rb[0], rb[1], prim.get("p_le") is not None and prim["p_le"] < ALPHA)
    rp = (rp[0], rp[1], prim.get("p_place_mirror") is not None and prim["p_place_mirror"] < ALPHA)
    c2 = all_constructions([rb, rp], "p < 0.05 (raw and Holm over the 6 declared variants) under both named nulls")
    h1, h2 = prim.get("h1") or {}, prim.get("h2") or {}
    ok3 = None if (h1.get("obs") is None or h2.get("obs") is None) else (h1["obs"] > 0 and h2["obs"] > 0)
    dec3 = any(h.get("p_le") is not None and h["p_le"] < ALPHA and h.get("obs", 0) <= 0 for h in (h1, h2))
    c3 = (f"both halves positive (2002-2013 {_bp(h1.get('obs'))}, 2014-2026 {_bp(h2.get('obs'))})", ok3, dec3)
    pl = prim.get("placebo") or {}
    pv, pse = pl.get("p_two"), pl.get("p_two_mc_se")
    okp, notep = (None, " [not available]") if pv is None else resolve(pv, pse, ALPHA, "gt")
    okp = None if pv is None else (okp if okp is not None else None)
    c4 = (f"placebo not significant (clusters moved to non-auction weeks: pooled placebo excess {_bp(pl.get('obs'), 2)}, "
          f"two-sided p {_f(pv, 4)}{notep})", okp, pv is not None and okp is False)
    crit = [c1, c2, c3, c4]
    v, why = _decide(crit, n, min_n, "auction-week clusters")
    return {"criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _event_days(archive) -> dict:
    """{'cpi': set of ISO weeks with a CPI release, 'fomc': set with a scheduled FOMC decision} (None when missing)."""
    out = {"cpi": None, "fomc": None}
    if _has(archive, CPI_B):
        out["cpi"] = {_iso_week(r["value"]["day"]) for r in _rows(archive, CPI_B) if (r.get("value") or {}).get("day")}
    if _has(archive, FOMC_B):
        out["fomc"] = {_iso_week(r["value"]["decision_day"]) for r in _rows(archive, FOMC_B)
                       if (r.get("value") or {}).get("decision_day") and not r["value"].get("future")}
    return out


def t442_study(tlt: dict, auctions: Sequence[dict], ief: Optional[dict] = None, dgs10: Optional[dict] = None,
               cpi_weeks: Optional[set] = None, fomc_weeks: Optional[set] = None, reps: Optional[int] = None) -> dict:
    """The primary test and the 6-variant family on price dicts ({'days', 'adj'}), the auction list and the event weeks."""
    reps = REPS if reps is None else reps
    cl = auction_clusters(auctions, tlt["days"])
    clusters = [c for c in cl["clusters"] if T442_START <= c["date"] <= T442_END]
    aw = frozenset(cl["weeks"])
    ser = {"days": tlt["days"], "lv": tlt["adj"]}
    kw = dict(series=ser, clusters=clusters, kind="price", auction_weeks=aw, reps=reps)
    prim = event_mc(lo=0, hi=3, side="gt", split=T442_SPLIT, thr=T442_THR, **kw)
    var = {T442_VARIANTS[0]: prim}
    var[T442_VARIANTS[1]] = event_mc(lo=-5, hi=-1, side="lt", **kw)
    if ief is not None:
        c10 = [c for c in auction_clusters(auctions, ief["days"], ("10",))["clusters"] if T442_START <= c["date"] <= T442_END]
        var[T442_VARIANTS[2]] = event_mc(series={"days": ief["days"], "lv": ief["adj"]}, clusters=c10, kind="price", lo=0, hi=3,
                                         side="gt", auction_weeks=aw, reps=reps)
    else:
        var[T442_VARIANTS[2]] = None
    if dgs10 is not None:
        yd = sorted(dgs10)
        c10 = [c for c in auction_clusters(auctions, yd, ("10",))["clusters"] if T442_DGS10_START <= c["date"] <= T442_END]
        aw10 = frozenset(auction_clusters(auctions, yd)["weeks"])
        var[T442_VARIANTS[3]] = event_mc(series={"days": yd, "lv": np.array([dgs10[d] for d in yd], float)}, clusters=c10,
                                         kind="yield", lo=0, hi=3, side="gt", start=T442_DGS10_START, auction_weeks=aw10, reps=reps)
    else:
        var[T442_VARIANTS[3]] = None
    var[T442_VARIANTS[4]] = event_mc(lo=0, hi=3, side="two", contrast=[c["reopen_only"] for c in clusters], **kw)
    if cpi_weeks is not None and fomc_weeks is not None:
        ex = [c for c in clusters if c["week"] not in cpi_weeks and c["week"] not in fomc_weeks]
        var[T442_VARIANTS[5]] = event_mc(**{**kw, "clusters": ex}, lo=0, hi=3, side="gt")
    else:
        var[T442_VARIANTS[5]] = None
    fams = lambda: ({k: (v.get("p_boot") if v else None) for k, v in var.items()},
                    {k: (v.get("p_place") if v else None) for k, v in var.items()})
    fam_b, fam_p = fams()
    n = int(prim.get("n_events") or 0)
    j = judge_auction(prim, fam_b, fam_p, n)
    unresolved = any("unresolved" in name for name, _ in j["criteria"])
    if unresolved and REPS_MAX_442 > reps:          # Monte Carlo error cannot decide a p or the placebo: more seeds
        prim = event_mc(lo=0, hi=3, side="gt", split=T442_SPLIT, thr=T442_THR, **{**kw, "reps": REPS_MAX_442})
        var[T442_VARIANTS[0]] = prim
        fam_b, fam_p = fams()
        j = judge_auction(prim, fam_b, fam_p, n)
    return {"clusters": clusters, "cl": cl, "prim": prim, "variants": var, "fam_boot": fam_b, "fam_place": fam_p, "n": n, **j}


REPS_MAX_442 = 25              # seeds when 5 cannot resolve the primary's p-values or placebo against 0.05


def b6c_pub_treasury_auction_cycle(archive):
    """T-442: TLT 3-session return after 10/30-year Treasury auction-week clusters vs its unconditional 3-session mean."""
    miss = _missing(archive, [AUCT_B, TLT_B])
    if miss:
        return miss
    auctions = nominal_auctions(_rows(archive, AUCT_B))
    tlt = _daily(archive, TLT_B)
    ief = _daily(archive, IEF_B) if _has(archive, IEF_B) else None
    dgs10 = _series(archive, DGS10_B) if _has(archive, DGS10_B) else None
    evd = _event_days(archive)
    res = t442_study(tlt, auctions, ief, dgs10, evd["cpi"], evd["fomc"])
    n, prim, cl = res["n"], res["prim"], res["clusters"]
    if n == 0 or prim.get("obs") is None:
        v, why = _decide([("auction clusters inside TLT's history", None)], n, T442_MIN_N, "auction-week clusters")
        return _out({"n_clusters": n}, n, v, f"no testable auction cluster ({len(auctions)} nominal 10/30-year auctions) — {why}")
    ann_bad = [c["date"] for c in cl if not c["ann_ok"]]
    cpi_n = sum(1 for c in cl if evd["cpi"] is not None and c["week"] in evd["cpi"])
    fomc_n = sum(1 for c in cl if evd["fomc"] is not None and c["week"] in evd["fomc"])
    ds = tlt["days"]
    pos = {d: i for i, d in enumerate(ds)}
    a3 = tlt["adj"]
    ret3 = {c["date"]: float(a3[pos[c["date"]] + 3] / a3[pos[c["date"]]] - 1.0) for c in cl if pos[c["date"]] + 3 < len(ds)}
    flag = lambda a, b: [v for d, v in ret3.items() if a <= d <= b]
    flagged = {k: {"n": len(flag(a, b)), "mean": _mean(flag(a, b))} for k, (a, b) in
               {"2008": ("2008-01-01", "2008-12-31"), "2020_03": ("2020-03-01", "2020-03-31"), "2022": ("2022-01-01", "2022-12-31")}.items()}
    vr = res["variants"]
    vtxt = []
    for k in T442_VARIANTS[1:]:
        r = vr.get(k)
        if not r or r.get("obs") is None:
            vtxt.append(f"{k} not computable")
            continue
        unit = (lambda x: f"{x:+.2f} bps") if k == "V4_dgs10_10y" else _bp
        vtxt.append(f"{k} {unit(r['obs'])} over {r.get('n_events')} clusters (p {_f(r.get('p_boot'), 4)} / placement "
                    f"{_f(r.get('p_place'), 4)})")
    o = prim["obs"]
    n_in = sum(1 for a in auctions if tlt["days"][0] <= a["date"] <= tlt["days"][-1])
    reason = (f"{n_in} held nominal 9/10/29/30-Year auctions inside TLT's history ({len(auctions)} since {auctions[0]['date']}; TIPS "
              f"and FRNs out) merged into {len(res['cl']['clusters'])} ISO-week clusters dated at the week's last auction "
              f"({len(res['cl']['dropped_weeks'])} weeks inside TLT's span without an auction on a TLT session dropped; "
              f"{len(ann_bad)} cluster dates not announced before the entry close); {n} clusters {cl[0]['date']}..{cl[-1]['date']} "
              f"inside TLT's history. TLT close of the cluster day -> close 3 sessions later: mean {_bp(prim.get('event_mean'))} vs the "
              f"unconditional 3-session mean {_bp(prim.get('uncond_mean'))}, excess {_bp(o)} (net of 1/2 bps a round trip "
              f"{_bp(o - T442_COSTS[0])}/{_bp(o - T442_COSTS[1])}); flags-fixed bootstrap p {_f(prim.get('p_boot'), 4)} (vs 10 bps "
              f"{_f(prim.get('p_vs_thr'), 4)}), placement p {_f(prim.get('p_place'), 4)} over {prim.get('pool_weeks')} non-auction "
              f"weeks; halves {_bp((prim.get('h1') or {}).get('obs'))} / {_bp((prim.get('h2') or {}).get('obs'))}; variants: "
              + "; ".join(vtxt) + f". Reported: {cpi_n} clusters in CPI weeks, {fomc_n} in FOMC weeks; 2008 "
              f"{_bp(flagged['2008']['mean'])} ({flagged['2008']['n']}), 2020-03 {_bp(flagged['2020_03']['mean'])} "
              f"({flagged['2020_03']['n']}), 2022 {_bp(flagged['2022']['mean'])} ({flagged['2022']['n']}) — " + res["why"])
    slim = lambda r: None if r is None else {k: r.get(k) for k in ("n_events", "obs", "event_mean", "uncond_mean", "mean_true",
                                                                   "mean_false", "n_true", "n_false", "p_boot", "p_boot_mc_se",
                                                                   "p_place", "p_place_mc_se", "reps")}
    stat = {"n_clusters": n, "first_cluster": cl[0]["date"], "last_cluster": cl[-1]["date"], "n_auctions": len(auctions),
            "n_auctions_in_tlt_span": n_in,
            "event_mean": prim.get("event_mean"), "uncond_mean": prim.get("uncond_mean"), "excess": o,
            "excess_bps": o * 1e4, "net_excess_1bp_2bp": [o - T442_COSTS[0], o - T442_COSTS[1]],
            "p_boot": prim.get("p_boot"), "p_boot_mc_se": prim.get("p_boot_mc_se"), "p_vs_10bps": prim.get("p_vs_thr"),
            "p_place": prim.get("p_place"), "p_place_mc_se": prim.get("p_place_mc_se"), "null_q": prim.get("null_q"),
            "place_mean": prim.get("place_mean"), "place_q": prim.get("place_q"), "halves": {"2002_2013": prim.get("h1"),
                                                                                           "2014_2026": prim.get("h2")},
            "placebo": prim.get("placebo"), "family_p_boot": res["fam_boot"], "family_p_place": res["fam_place"],
            "holm_boot": holm_primary(res["fam_boot"], T442_VARIANTS[0]), "holm_place": holm_primary(res["fam_place"], T442_VARIANTS[0]),
            "variants": {k: slim(v) for k, v in vr.items()}, "cpi_week_clusters": cpi_n, "fomc_week_clusters": fomc_n,
            "flagged": flagged, "ann_not_before_entry": ann_bad, "dropped_weeks": len(res["cl"]["dropped_weeks"]),
            "criteria": res["criteria"], "rule10": "the auction calendar (clusters dated at the week's last auction)"}
    return _out(stat, n, res["verdict"], reason)


# ============================================================================== T-472 PHYS discount reversion ==

T472_START, T472_END = "2012-01-01", "2026-09-30"
T472_SPLIT = "2020-01-01"
T472_WIN = 250
T472_GAP = 1.0                 # percentage points below the trailing mean
T472_ZTHR = 2.0
T472_LEVELS = (-2.0, -1.0)     # the original fixed-level control: buy below -2%, sell above -1%
T472_MAX_HOLD = 60
T472_COST_LEG = 0.0010
T472_COSTS = {"20bps_per_trade (10 bps per leg per round trip)": 2 * T472_COST_LEG,
              "40bps_per_trade (10 bps per leg per side)": 4 * T472_COST_LEG}
T472_BORROW = 0.0050           # a year on the GLD short notional
T472_MIN_N = 30
T472_SHIFT = 60
T472_N_TRIALS = 5              # 4 runnable variants + the disclosed descriptive peek


def sprott_series(rows: Sequence[dict]) -> tuple:
    """(days, premium/discount in percent) of a ``sprott-<fund>-nav`` bundle."""
    by = {}
    for r in rows:
        v = r.get("value") or {}
        x = _num(v.get("premium_discount_pct"))
        if x is not None and v.get("day"):
            by[v["day"]] = x
    ds = sorted(by)
    return ds, np.array([by[d] for d in ds], float)


def trailing(x: np.ndarray, win: int = T472_WIN, incl: bool = True) -> tuple:
    """(mean, sd) over the trailing ``win`` observations ending at t (``incl``) or at t-1; NaN before a full window."""
    x = np.asarray(x, float)
    n = x.size
    m, s = np.full(n, np.nan), np.full(n, np.nan)
    cs, cs2 = np.concatenate([[0.0], np.cumsum(x)]), np.concatenate([[0.0], np.cumsum(x * x)])
    off = 0 if incl else 1
    for i in range(win - 1 + off, n):
        a, b = i + 1 - off - win, i + 1 - off
        mu = (cs[b] - cs[a]) / win
        m[i] = mu
        s[i] = math.sqrt(max((cs2[b] - cs2[a] - win * mu * mu) / (win - 1), 0.0))
    return m, s


def discount_trades(sp_days: Sequence[str], d: np.ndarray, pa: dict, pb: dict, rule: str = "mean", win: int = T472_WIN,
                    incl: bool = True, exit_mean: str = "rolling", start: str = T472_START, end: str = T472_END,
                    gap: float = T472_GAP, zthr: float = T472_ZTHR, levels: tuple = T472_LEVELS,
                    max_hold: int = T472_MAX_HOLD) -> dict:
    """Simulate long ``pa`` / short ``pb`` on the sessions where both trade. At each session close the latest premium known
    is the one dated strictly before the session (struck after the close, known the next morning). Flat: enter at that
    close when (rule 'mean') d < trailing mean - gap, ('z') (d - mean)/sd < -zthr, ('fixed') d < levels[0], for sessions in
    [start, end]. In a trade: exit at that close when d >= the trailing mean (rolling, or ``exit_mean`` 'fixed': the mean at
    entry; rule 'fixed': d > levels[1]) or ``max_hold`` sessions after entry. A trade still open at the data end is dropped
    (reported)."""
    d = np.asarray(d, float)
    m, s = trailing(d, win, incl)
    A, Bp = dict(zip(pa["days"], pa["adj"])), dict(zip(pb["days"], pb["adj"]))
    sess = sorted(set(A) & set(Bp))
    Aa = np.array([A[x] for x in sess], float)
    Ba = np.array([Bp[x] for x in sess], float)
    kpos = np.searchsorted(np.array(list(sp_days)), np.array(sess), side="left") - 1 if len(sp_days) and sess else np.zeros(0, int)
    trades, state, e, m_e, k_e = [], False, -1, None, -1
    for j in range(len(sess)):
        k = int(kpos[j])
        if k < 0:
            continue
        dk, mk, sk = d[k], m[k], s[k]
        if state:
            if j - e >= max_hold:
                ex = True
            elif rule == "fixed":
                ex = dk > levels[1]
            else:
                ref = mk if exit_mean == "rolling" else m_e
                ex = bool(np.isfinite(ref) and dk >= ref)
            if ex:
                trades.append((e, j, k_e))
                state = False
            continue
        if not (start <= sess[j] <= end):
            continue
        if rule == "fixed":
            sig = dk < levels[0]
        elif not np.isfinite(mk):
            continue
        elif rule == "z":
            sig = sk > 0 and (dk - mk) / sk < -zthr
        else:
            sig = dk < mk - gap
        if sig:
            state, e, m_e, k_e = True, j, mk, k
    tr = np.array([(a, b) for a, b, _ in trades], int).reshape(-1, 2)
    gross = Aa[tr[:, 1]] / Aa[tr[:, 0]] - Ba[tr[:, 1]] / Ba[tr[:, 0]] if tr.size else np.zeros(0)
    days_h = np.array([(date.fromisoformat(sess[b]) - date.fromisoformat(sess[a])).days for a, b in tr], float) if tr.size else np.zeros(0)
    nets = {k: gross - c - T472_BORROW * days_h / 365.0 for k, c in T472_COSTS.items()}
    y = d - m
    ok = np.isfinite(y)
    yy = y[ok]
    phi = float(np.polyfit(yy[:-1], yy[1:], 1)[0]) if yy.size > 30 else None
    hl = (math.log(0.5) / math.log(phi)) if (phi is not None and 0 < phi < 1) else None
    return {"sess": sess, "A": Aa, "B": Ba, "trades": [(int(a), int(b)) for a, b in tr], "signal_days": [sp_days[k] for *_, k in trades],
            "gross": gross, "days": days_h, "sessions_held": (tr[:, 1] - tr[:, 0]).astype(float) if tr.size else np.zeros(0),
            "net": nets, "entry": [sess[a] for a, _ in tr], "exit": [sess[b] for _, b in tr],
            "open_trade": sess[e] if state else None, "ar1": phi, "half_life": hl}


def cluster_stud(x, labels: Sequence[str], n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Studentized bootstrap of a mean with observations resampled in clusters (``labels``, e.g. the entry month) and a
    cluster-robust s.e.: est, se, two-sided 95% ``ci`` and 90% ``ci90`` (lower end = one-sided 95% lower bound),
    percentile ``ci_pct``, p (H0: mean <= 0) and p_lt."""
    n_boot = N_BOOT if n_boot is None else int(n_boot)
    x = np.asarray(x, float)
    out = {"est": float(x.mean()) if x.size else None, "se": None, "ci": [None, None], "ci90": [None, None],
           "ci_pct": [None, None], "p": None, "p_lt": None, "n": int(x.size), "clusters": 0}
    if x.size < 4:
        return out
    keys = sorted(set(labels))
    ix = {k: i for i, k in enumerate(keys)}
    G = len(keys)
    Sg, Ng = np.zeros(G), np.zeros(G)
    for v, lb in zip(x, labels):
        Sg[ix[lb]] += v
        Ng[ix[lb]] += 1
    out["clusters"] = G
    m0 = float(x.mean())
    se0 = math.sqrt(float(((Sg - Ng * m0) ** 2).sum())) / x.size
    out["se"] = se0
    if G < 4 or not se0 > 1e-14:
        out.update(ci=[m0, m0], ci90=[m0, m0], ci_pct=[m0, m0], p=0.0 if m0 > 0 else 1.0, p_lt=0.0 if m0 < 0 else 1.0)
        return out
    rng = np.random.default_rng(seed)
    ts, ms = [], []
    S2, SN, N2 = Sg * Sg, Sg * Ng, Ng * Ng
    for k in _chunks(n_boot, G):
        idx = rng.integers(0, G, (k, G))
        S, N = Sg[idx].sum(axis=1), Ng[idx].sum(axis=1)
        mm = S / N
        var = S2[idx].sum(axis=1) - 2 * mm * SN[idx].sum(axis=1) + mm * mm * N2[idx].sum(axis=1)
        se = np.sqrt(np.maximum(var, 0.0)) / N
        ok = se > 1e-14
        ts.append((mm[ok] - m0) / se[ok])
        ms.append(mm)
    t, mm = np.concatenate(ts), np.concatenate(ms)
    q = lambda a: float(np.quantile(t, a))
    t_obs = m0 / se0
    out.update(ci=[m0 - q(0.975) * se0, m0 - q(0.025) * se0], ci90=[m0 - q(0.95) * se0, m0 - q(0.05) * se0],
               ci_pct=[float(np.quantile(mm, 0.025)), float(np.quantile(mm, 0.975))],
               p=float((np.sum(t >= t_obs) + 1) / (t.size + 1)), p_lt=float((np.sum(t <= t_obs) + 1) / (t.size + 1)))
    return out


def shift_null(sim: dict, step: int = T472_SHIFT) -> dict:
    """The trial's second null: the position path (a function of the signal alone) shifted against the prices by every
    multiple of ``step`` sessions, circularly with the price path continued past its end; trade lengths, count and costs
    kept, so the comparison is on gross returns. p = (1 + #{shifted mean >= observed}) / (1 + shifts)."""
    A, B = sim["A"], sim["B"]
    N = A.size
    tr = np.array(sim["trades"], int).reshape(-1, 2)
    if not tr.size or N < 2 * step:
        return {"p": None, "n_shifts": 0, "p_mirror": None}
    Ax = np.concatenate([A, A[1:] * (A[-1] / A[0])])
    Bx = np.concatenate([B, B[1:] * (B[-1] / B[0])])
    e, L = tr[:, 0], tr[:, 1] - tr[:, 0]
    obs = float(sim["gross"].mean())
    means = []
    for k in range(1, N // step):
        e2 = (e + k * step) % N
        x2 = e2 + L
        if (x2 >= Ax.size).any():
            continue
        means.append(float((Ax[x2] / Ax[e2] - Bx[x2] / Bx[e2]).mean()))
    means = np.array(means, float)
    if not means.size:
        return {"p": None, "n_shifts": 0, "p_mirror": None}
    return {"p": float((1 + np.sum(means >= obs)) / (1 + means.size)), "p_mirror": float((1 + np.sum(means <= obs)) / (1 + means.size)),
            "n_shifts": int(means.size), "null_mean_gross": float(means.mean()), "null_q95_gross": float(np.quantile(means, 0.95)),
            "obs_gross": obs}


def judge_discount(sim: dict, window_closed: bool, min_n: int = T472_MIN_N, split: str = T472_SPLIT, reps: Optional[int] = None) -> dict:
    """T-472 criteria on a simulation."""
    reps = REPS if reps is None else reps
    n = len(sim["trades"])
    months = [d[:7] for d in sim["entry"]]
    sh = shift_null(sim) if n else {"p": None}
    rows, boots, signs = [], {}, []
    pc3 = lambda v: _pc(v, 3)
    for name, x in sim["net"].items():
        bt = mc_escalate(lambda seed: cluster_stud(x, months, N_BOOT, seed), lambda t: resolve((t.get("ci90") or [None])[0],
                         (t.get("ci90_mc_se") or [0.0])[0], 0.0, "gt")[0], reps, SEED, keys=("ci", "ci90", "ci_pct")) if n >= 4 \
            else {"est": _mean(x), "ci": [None, None], "ci90": [None, None]}
        boots[name] = bt
        lo, hi = (bt.get("ci90") or [None, None])
        se_lo, se_hi = (bt.get("ci90_mc_se") or [0.0, 0.0])
        ok_b, note = resolve(lo, se_lo, 0.0, "gt")
        dec_b = hi is not None and resolve(hi, se_hi, 0.0, "lt")[0] is True
        rows.append((f"[{name}] monthly-cluster studentized bootstrap: mean {pc3(bt.get('est'))}, one-sided 95% lower bound "
                     f"{pc3(lo)}{note} > 0 (two-sided 95% {_ci(bt.get('ci'), 3, 100, '%')})", ok_b, dec_b))
        ok_s = None if sh.get("p") is None else sh["p"] < ALPHA
        rows.append((f"[{name}] block-shift null (every {T472_SHIFT}-session shift of the signal, {sh.get('n_shifts')} shifts): "
                     f"p {_f(sh.get('p'), 3)} < 0.05", ok_s, sh.get("p_mirror") is not None and sh["p_mirror"] < ALPHA))
        x1 = np.array([v for v, d in zip(x, sim["entry"]) if d < split], float)
        x2 = np.array([v for v, d in zip(x, sim["entry"]) if d >= split], float)
        m1, m2 = _mean(x1), _mean(x2)
        ok3 = None if (m1 is None or m2 is None) else bool(np.sign(m1) == np.sign(m2) and m1 != 0)
        dec3 = False
        if ok3 is False:
            b1 = cluster_stud(x1, [d[:7] for d in sim["entry"] if d < split], N_BOOT, SEED)
            b2 = cluster_stud(x2, [d[:7] for d in sim["entry"] if d >= split], N_BOOT, SEED)
            ex = lambda b, sg: b["ci"][0] is not None and ((sg > 0 and b["ci"][0] > 0) or (sg < 0 and b["ci"][1] < 0))
            dec3 = ex(b1, m1) and ex(b2, m2)
        signs.append((f"[{name}] 2012-2019 mean {pc3(m1)} ({x1.size} trades), 2020-2026 mean {pc3(m2)} ({x2.size} trades)", ok3, dec3))
    c1 = all_constructions(rows, "mean net return per trade > 0 (both cost readings, both named nulls)")
    n_open = 1 if sim.get("open_trade") else 0
    dec2 = window_closed and (n + n_open) < min_n
    c2 = (f"at least {min_n} trades ({n} closed" + (f" + 1 still open at the data end" if n_open else "")
          + ("; the entry window has closed, so the count cannot grow" if dec2 else "") + ")", n >= min_n, dec2)
    c3 = all_constructions(signs, "same sign in 2012-2019 and 2020-2026")
    crit = [c1, c2, c3]
    v, why = _decide(crit, n, min_n, "trades")
    return {"n": n, "boot": boots, "shift": sh, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_pub_phys_discount_reversion(archive):
    """T-472: long PHYS / short GLD when PHYS's discount is > 1 pp below its trailing 250-day mean."""
    miss = _missing(archive, [SPROTT_PHYS, PHYS_B, GLD_B])
    if miss:
        return miss
    sd, dv = sprott_series(_rows(archive, SPROTT_PHYS))
    phys, gld = _daily(archive, PHYS_B), _daily(archive, GLD_B)
    sim = discount_trades(sd, dv, phys, gld)
    n = len(sim["trades"])
    window_closed = bool(sim["sess"] and sim["sess"][-1] > T472_END)
    j = judge_discount(sim, window_closed)
    pri = list(T472_COSTS)[0]
    fam = {"mean_rule": sim["net"][pri]}
    var = {}
    for nm, kw in (("z_lt_m2", {"rule": "z"}), ("fixed_m2_m1", {"rule": "fixed"}), ("mean_excl_today", {"incl": False}),
                   ("exit_at_entry_mean", {"exit_mean": "fixed"})):
        s2 = discount_trades(sd, dv, phys, gld, **kw)
        var[nm] = {"n": len(s2["trades"]), "mean_net_20": _mean(s2["net"][pri]), "mean_net_40": _mean(s2["net"][list(T472_COSTS)[1]])}
        if nm in ("z_lt_m2", "fixed_m2_m1"):
            fam[nm] = s2["net"][pri]
    if _has(archive, SPROTT_PSLV) and _has(archive, PSLV_B) and _has(archive, SLV_B):
        ps, pv = sprott_series(_rows(archive, SPROTT_PSLV))
        s3 = discount_trades(ps, pv, _daily(archive, PSLV_B), _daily(archive, SLV_B))
        var["pslv_slv"] = {"n": len(s3["trades"]), "mean_net_20": _mean(s3["net"][pri]), "mean_net_40": _mean(s3["net"][list(T472_COSTS)[1]])}
        fam["pslv_slv"] = s3["net"][pri]
    else:
        var["pslv_slv"] = "not computable: sprott-pslv-nav / daily-history-PSLV / daily-history-SLV not all archived"
    x20 = sim["net"][pri]
    fs = [float(sharpe_ratio(v)) for v in fam.values() if len(v) > 2 and np.std(v) > 0]
    dsr = family_dsr(x20, fs, T472_N_TRIALS) if n > 3 else {"dsr": None}
    sh = j["shift"]
    per_day = float(np.mean(x20 / np.maximum(sim["sessions_held"], 1))) if n else None
    per_cal = float(x20.sum() / sim["days"].sum()) if n and sim["days"].sum() > 0 else None
    b20, b40 = j["boot"][pri], j["boot"][list(T472_COSTS)[1]]
    reason = (f"Sprott PHYS premium/discount ({sd[0]}..{sd[-1]}, {len(sd)} days) vs its trailing {T472_WIN}-observation mean; "
              f"signal known the next morning, long PHYS / short GLD at the next NYSE close, exit at the next close after the "
              f"discount is back at its rolling mean or after {T472_MAX_HOLD} sessions; entries {T472_START}..{T472_END}: {n} trades"
              + (f" {sim['entry'][0]}..{sim['entry'][-1]}" if n else "")
              + (f" (one opened {sim['open_trade']} still open, dropped)" if sim["open_trade"] else "")
              + f", median hold {int(np.median(sim['sessions_held'])) if n else 'n/a'} sessions; gross mean {_pc(_mean(sim['gross']), 3)}; "
              f"net mean {_pc(b20.get('est'), 3)} at 20 bps a trade (one-sided 95% lower bound {_pc((b20.get('ci90') or [None])[0], 3)}), "
              f"{_pc(b40.get('est'), 3)} at 40 bps (lower bound {_pc((b40.get('ci90') or [None])[0], 3)}), 50 bps/yr GLD borrow; "
              f"block-shift p {_f(sh.get('p'), 3)}; per session held {_pc(per_day, 4)}; AR(1) of d minus its trailing mean "
              f"{_f(sim['ar1'], 3)} (half-life {_f(sim['half_life'], 1)} days); DSR at {T472_N_TRIALS} trials {_f(dsr.get('dsr'))} "
              f"(reported, not in the pass). Variants: " + "; ".join(
                  f"{k} {v['n']} trades, mean {_pc(v['mean_net_20'], 3)}" if isinstance(v, dict) else f"{k} {v}" for k, v in var.items())
              + " — " + j["why"])
    stat = {"n_trades": n, "trades": [{"signal": sg, "entry": a, "exit": b, "sessions": int(h), "gross": float(g),
                                       "net_20": float(x), "net_40": float(y)}
                                      for sg, a, b, h, g, x, y in zip(sim["signal_days"], sim["entry"], sim["exit"],
                                                                      sim["sessions_held"], sim["gross"], x20,
                                                                      sim["net"][list(T472_COSTS)[1]])],
            "open_trade_dropped": sim["open_trade"], "mean_gross": _mean(sim["gross"]), "boot": j["boot"], "block_shift": sh,
            "per_session_held": per_day, "per_calendar_day": per_cal, "ar1": sim["ar1"], "half_life_days": sim["half_life"],
            "dsr": dsr, "variants": var, "window_closed": window_closed, "criteria": j["criteria"],
            "cost_readings": T472_COSTS, "borrow": T472_BORROW, "rule10": "signal-driven entries and exits (no grid)",
            "peek_disclosed": "2015-2026 descriptive statistics seen before registration: counted as a trial in the DSR"}
    return _out(stat, n, j["verdict"], reason)


# ================================================================================== T-404 GLD holdings flows ==

T404_START, T404_END = "2005-01-01", "2026-12-31"
T404_SPLIT = "2016-01-01"
T404_FLOW_WEEKS = 4
T404_Z_WEEKS = 52
T404_T_THR = 2.0
T404_MIN_N = 1000
T404_GRANGER_LAGS = 4
T404_N_VARIANTS = 5


def spdr_holdings(rows: Sequence[dict]) -> dict:
    """{'days', 'tonnes', 'av' (POSIX available_at)} of a ``spdr-<product>-archive`` bundle in day order."""
    by = {}
    for r in rows:
        v = r.get("value") or {}
        t = _num(v.get("tonnes"))
        if t is not None and v.get("day") and r.get("available_at"):
            by[v["day"]] = (t, _epoch(r["available_at"]))
    ds = sorted(by)
    return {"days": ds, "tonnes": np.array([by[d][0] for d in ds], float), "av": np.array([by[d][1] for d in ds], float)}


def week_bounds(days: Sequence[str]) -> list:
    """[(iso week, first session index, last session index)] in order."""
    out = []
    for i, d in enumerate(days):
        w = _iso_week(d)
        if out and out[-1][0] == w:
            out[-1][2] = i
        else:
            out.append([w, i, i])
    return [tuple(x) for x in out]


def _zscore(F: np.ndarray, win: int) -> np.ndarray:
    z = np.full(F.size, np.nan)
    for i in range(F.size):
        if i + 1 < win:
            continue
        w = F[i + 1 - win:i + 1]
        if not np.isfinite(w).all():
            continue
        sd = w.std(ddof=1)
        z[i] = (F[i] - w.mean()) / sd if sd > 0 else np.nan
    return z


def flow_panel(h: dict, px: dict, info: str = "close", ret: str = "open", start: str = T404_START, end: str = T404_END,
               flow_weeks: int = T404_FLOW_WEEKS, z_weeks: int = T404_Z_WEEKS) -> dict:
    """Weekly decision panel. Week i decides at its last session's close; the holdings known are the latest trust day
    available by then (``info`` 'close'), or by the next session's 09:30 ET open (``info`` 'open'). F_i = H_i - H_{i-4
    weeks}; z_i over F_{i-51..i}. Next-week return (``ret`` 'open'): first open of week i+1 -> first open of week i+2;
    ('close'): last close of week i -> last close of week i+1. Also the contemporaneous panel (holdings dated by session
    day, the week's own close-to-close return) and the weekly series for the Granger tests."""
    days = px["days"]
    wb = week_bounds(days)
    nW = len(wb)
    H = np.full(nW, np.nan)
    Hd = np.full(nW, np.nan)
    hd = h["days"]
    for i, (w, f, l) in enumerate(wb):
        T = et_epoch(days[l], "16:00") if info == "close" else (et_epoch(days[wb[i + 1][1]], "09:30") if i + 1 < nW else np.inf)
        k = int(np.searchsorted(h["av"], T, side="right")) - 1
        if k >= 0 and np.isfinite(T):
            H[i] = h["tonnes"][k]
        kd = bisect.bisect_right(hd, days[l]) - 1
        if kd >= 0:
            Hd[i] = h["tonnes"][kd]
    F = np.full(nW, np.nan)
    F[flow_weeks:] = H[flow_weeks:] - H[:-flow_weeks]
    z = _zscore(F, z_weeks)
    Fd = np.full(nW, np.nan)
    Fd[flow_weeks:] = Hd[flow_weeks:] - Hd[:-flow_weeks]
    zd = _zscore(Fd, z_weeks)
    O, C = px["open"], px["adj"]
    R = np.full(nW, np.nan)
    for i in range(nW):
        if ret == "open" and i + 2 < nW:
            a, b = O[wb[i + 1][1]], O[wb[i + 2][1]]
            R[i] = b / a - 1.0 if np.isfinite(a) and np.isfinite(b) else np.nan
        elif ret == "close" and i + 1 < nW:
            R[i] = C[wb[i + 1][2]] / C[wb[i][2]] - 1.0
    Rc = np.full(nW, np.nan)
    Rc[1:] = np.array([C[wb[i][2]] / C[wb[i - 1][2]] - 1.0 for i in range(1, nW)])
    dday = [days[l] for _, _, l in wb]
    inw = np.array([start <= d <= end for d in dday], bool)
    m = inw & np.isfinite(z) & np.isfinite(R)
    mc = inw & np.isfinite(zd) & np.isfinite(Rc)
    fl = np.full(nW, np.nan)
    fl[1:] = Hd[1:] - Hd[:-1]
    mg = inw & np.isfinite(fl) & np.isfinite(Rc)
    return {"dates": [d for d, k in zip(dday, m) if k], "z": z[m], "F": F[m], "R": R[m], "zc": zd[mc], "Rc": Rc[mc],
            "g_flow": fl[mg], "g_ret": np.log1p(Rc[mg]), "n_weeks": int(m.sum())}


def _ols1(y, x, lag: Optional[int] = None) -> dict:
    y, x = np.asarray(y, float), np.asarray(x, float)
    if y.size < 12:
        return {"slope": None, "t": None, "n": int(y.size), "lag": None}
    L = nw_lag(y.size) if lag is None else lag
    o = ols_nw(y, x, L)
    return {"slope": (o.get("coef") or [None, None])[1], "t": (o.get("t") or [None, None])[1], "n": int(y.size), "lag": L,
            "r2": o.get("r2")}


def judge_flows(pan: dict, min_n: int = T404_MIN_N, split: str = T404_SPLIT, thr: float = T404_T_THR) -> dict:
    """T-404 criteria on a flow panel."""
    z, R, ds = pan["z"], pan["R"], pan["dates"]
    n = int(z.size)
    full = _ols1(R, z)
    m1 = np.array([d < split for d in ds], bool)
    h1, h2 = _ols1(R[m1], z[m1]), _ols1(R[~m1], z[~m1])
    t = full["t"]
    c1 = (f"predictive slope HAC t >= {thr:g} over >= {min_n} weeks (slope {_s(full['slope'], 5)} per unit z, NW t {_s(t, 2)} with "
          f"{full['lag']} lags, {n} weeks)", None if t is None else t >= thr, t is not None and t <= -thr)
    ok2 = None if (h1["slope"] is None or h2["slope"] is None) else (h1["slope"] > 0 and h2["slope"] > 0)
    dec2 = any(hh["t"] is not None and hh["t"] <= -2.0 for hh in (h1, h2))
    c2 = (f"positive slope in both halves (2005-2015 {_s(h1['slope'], 5)}, t {_s(h1['t'], 2)}, {h1['n']} weeks; 2016-2026 "
          f"{_s(h2['slope'], 5)}, t {_s(h2['t'], 2)}, {h2['n']} weeks)", ok2, dec2)
    crit = [c1, c2]
    v, why = _decide(crit, n, min_n, "weeks")
    return {"n": n, "full": full, "h1": h1, "h2": h2, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why,
            "park_condition": v != "supported"}


def b6c_pub_gld_flows(archive):
    """T-404: the 4-week change in GLD tonnes (52-week z) predicting the next week's GLD return."""
    miss = _missing(archive, [SPDR_GLD, GLD_B])
    if miss:
        return miss
    h = spdr_holdings(_rows(archive, SPDR_GLD))
    gld = _daily(archive, GLD_B)
    pan = flow_panel(h, gld)
    if pan["n_weeks"] < 12:
        v, why = _decide([("weekly flow z and next-week GLD returns", None)], pan["n_weeks"], T404_MIN_N, "weeks")
        return _out({"n_weeks": pan["n_weeks"]}, pan["n_weeks"], v, f"only {pan['n_weeks']} usable weeks — {why}")
    j = judge_flows(pan)
    alt_info = judge_flows(flow_panel(h, gld, info="open"))
    alt_close = judge_flows(flow_panel(h, gld, ret="close"))
    raw = _ols1(pan["R"], pan["F"])
    contemp = _ols1(pan["Rc"], pan["zc"])
    g_fr = granger(pan["g_ret"], pan["g_flow"], T404_GRANGER_LAGS)
    g_rf = granger(pan["g_flow"], pan["g_ret"], T404_GRANGER_LAGS)
    by_year = {}
    for y in sorted({d[:4] for d in pan["dates"]}):
        mk = np.array([d[:4] == y for d in pan["dates"]], bool)
        if mk.sum() >= 20:
            by_year[y] = _ols1(pan["R"][mk], pan["z"][mk], 2)["slope"]
    regimes = {}
    for k, (a, b) in {"2013": ("2013-01-01", "2013-12-31"), "2020": ("2020-01-01", "2020-12-31"), "2022_2026": ("2022-01-01", "2026-12-31")}.items():
        mk = np.array([a <= d <= b for d in pan["dates"]], bool)
        regimes[k] = _ols1(pan["R"][mk], pan["z"][mk], 2) if mk.sum() >= 20 else None
    ctrl = None
    if _has(archive, DFII10_B):
        rr = _asof(_series(archive, DFII10_B))
        drr = []
        for d in pan["dates"]:
            a, b = rr(d), rr((date.fromisoformat(d) - timedelta(days=28)).isoformat())
            drr.append(a - b if a is not None and b is not None else np.nan)
        drr = np.array(drr, float)
        mk = np.isfinite(drr)
        if mk.sum() > 50:
            o = ols_nw(pan["R"][mk], np.column_stack([pan["z"][mk], drr[mk]]), nw_lag(int(mk.sum())))
            ctrl = {"n": int(mk.sum()), "slope_z": (o.get("coef") or [None, None])[1], "t_z": (o.get("t") or [None, None])[1],
                    "coef_d_dfii10": (o.get("coef") or [None, None, None])[2], "t_d_dfii10": (o.get("t") or [None, None, None])[2]}
    pos_years = sum(1 for v in by_year.values() if v is not None and v > 0)
    park = j["park_condition"]
    reason = (f"SPDR GLD archive ({h['days'][0]}..{h['days'][-1]}, {len(h['days'])} trust days): tonnes known at each week's last "
              f"close (available the next morning, so Thursday's for a Friday decision), 4-week change, z on 52 weeks to t; next "
              f"week's GLD return from the first open of the following week to the first open of the week after; {j['n']} decision "
              f"weeks {pan['dates'][0]}..{pan['dates'][-1]}. Full-sample slope {_s(j['full']['slope'], 5)} per unit z (NW t "
              f"{_s(j['full']['t'], 2)}); 2005-2015 {_s(j['h1']['slope'], 5)} (t {_s(j['h1']['t'], 2)}), 2016-2026 "
              f"{_s(j['h2']['slope'], 5)} (t {_s(j['h2']['t'], 2)}). PARK CONDITION {'HOLDS' if park else 'does not hold'}"
              f"{': the trial parks the claim as flows follow price' if park else ''}. Reported: Monday-open information set "
              f"(Friday's holdings) t {_s(alt_info['full']['t'], 2)}; Friday-close-to-Friday-close return t "
              f"{_s(alt_close['full']['t'], 2)}; raw 4-week tonnes change t {_s(raw['t'], 2)}; contemporaneous (same-week return on "
              f"the flow z through that Friday, not point in time) slope {_s(contemp['slope'], 5)}, t {_s(contemp['t'], 2)}; Granger "
              f"(4 weekly lags, HC0 Wald) flows -> returns p {_f(g_fr.get('p'), 4)}, returns -> flows p {_f(g_rf.get('p'), 4)}; "
              f"positive slope in {pos_years} of {len(by_year)} calendar years; "
              + (f"DFII10-controlled z t {_s(ctrl['t_z'], 2)}" if ctrl else "DFII10 control not computed")
              + "; costs (GLD 0.40% fee inside the price, 1 bp spread) do not enter a slope — " + j["why"])
    stat = {"n_weeks": j["n"], "first_week": pan["dates"][0], "last_week": pan["dates"][-1], "slope": j["full"],
            "halves": {"2005_2015": j["h1"], "2016_2026": j["h2"]}, "park_condition": park,
            "park_rule": "otherwise parked as 'flows follow price'",
            "monday_open_info": {"slope": alt_info["full"], "verdict": alt_info["verdict"]},
            "close_to_close": {"slope": alt_close["full"], "verdict": alt_close["verdict"]}, "raw_tonnes_change": raw,
            "contemporaneous": contemp, "granger_flows_to_returns": g_fr, "granger_returns_to_flows": g_rf,
            "slope_by_year": by_year, "regimes": regimes, "dfii10_control": ctrl, "n_variants_declared": T404_N_VARIANTS,
            "criteria": j["criteria"], "rule10": "the Friday-close / Monday-open weekly calendar the library rule names"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_pub_gold_cot_extremes": b6c_pub_gold_cot_extremes,
    "b6c_pub_treasury_auction_cycle": b6c_pub_treasury_auction_cycle,
    "b6c_pub_phys_discount_reversion": b6c_pub_phys_discount_reversion,
    "b6c_pub_gld_flows": b6c_pub_gld_flows,
}

THEORY_MAP = {
    "T-405": "b6c_pub_gold_cot_extremes",
    "T-442": "b6c_pub_treasury_auction_cycle",
    "T-472": "b6c_pub_phys_discount_reversion",
    "T-404": "b6c_pub_gld_flows",
}
