"""
Batch 6, time / term-structure structures on SPY: long and short calendars, the long diagonal, the double calendar and
double diagonal, the vega-weighted ratio calendar, the poor man's covered call, the LEAPS collar, the calendarised
butterfly and the roll of a tested short put.
=====================================================================================================================

Ten options-library claims (T-143, T-144, T-145, T-146, T-147, T-149, T-150, T-151, T-152, T-155), each tested on its own
claim, trial.pass and trial.min_n. Every result is MODEL-PRICED: legs are Black-Scholes prices at the IV proxy the claim
names, never traded quotes. The archive holds two captured chain days, enough to calibrate costs and one-day
sensitivities but not a traded test; every reason says so.

IV term structure (the claims' model).
  * Front IV = VIX/100. A tenor T (calendar days) between 30 and 93 days is priced at the total-variance interpolation
    w(T) = w(30) + (w(93) - w(30)) * (T - 30) / (93 - 30), w = IV^2 * T, from VIX (30d) and VIX3M (93d); between 93 and
    182 days from VIX3M and VIX6M the same way (flat VIX3M vol when VIX6M is missing); flat vol below 30 days (VIX) and
    beyond 182 days (VIX6M). The PMCC and LEAPS collar claims name VIX3M itself as the 12-month IV and use it as named.
  * Held legs are re-priced at each revaluation date with that day's VIX/VIX3M(/VIX6M) for their remaining life.
  * Claim window: the trials ask for 2007-12-04 onward (FRED VXVCLS). The archive's VIX3M starts on 2009-09-18, so the
    tests run from the first archived VIX3M print; using VIX for VIX3M before then would make the term structure flat and,
    for T-143/T-144, put every pre-2009 day in one regime, so it is not done. A WINDOW SENSITIVITY (never a criterion)
    reruns the headline statistic from 2008-01-02 (first VIX6M print) with a VIX3M proxy interpolated in total variance
    between VIX and VIX6M before 2009-09-18; its error against the real VIX3M on the overlap is reported. 2007-12 itself
    is not covered by any archived term index.
    T-152 is the exception: its CLAIM names the window ("top-decile months of VIX increase since 2007-12") and has no
    term-structure regime, so the house data guidance applies: VIX stands in for VIX3M before its first print (the
    back-leg IV is then VIX), entries run from 2007-12-04, and the reason labels the proxy and gives its error against
    the real VIX3M. The real-VIX3M-only run (2009-09-18 on) and the VIX/VIX6M proxy are report-only sensitivities.

Conventions (house rules).
  * Prices: SPY RAW closes (``close``) for strikes and settlement. Cash dividends come from the step in the adjclose/close
    ratio on each ex-date: D = close(day before) * (1 - ratio(day before) / ratio(day)). An option whose life holds an
    ex-date (after the valuation close, on or before expiry) is priced on the escrowed-dividend forward S - PV(D) with
    q = 0. Realised amounts are used as known (SPY's schedule is fixed); ex-dates after the last archived day are
    projected by repeating the last year's dividends 364 and 728 days later. Holding SPY (covered call, collars) is total
    return (adjclose).
  * Rates: FRED DTB3 is a discount yield published the next day, so a decision on day d uses the latest print dated
    before d, converted to a continuous rate r = -ln(1 - d/100 * 91/360) / (91/365).
  * Index closes (VIX, VIX3M, VIX6M, SKEW) are known at their close and used at that close; a missing print carries the
    last one.
  * Cycles: a "30-DTE" front leg expires at the close 21 sessions after entry; T = calendar days / 365. Calendar back
    legs expire 30 calendar days after the front (so a 30/60 calendar's back leg has exactly 30 days left at the front
    expiry); 90-DTE and 12-month legs bought on a monthly grid are replaced when 30 / 90 days remain.
  * Costs: half the bid-ask spread per contract fill, from the archived SPY chains (median half-spread / spot of OTM
    quotes by DTE and moneyness bucket, pooled over the capture days). An ITM leg is charged the same-strike OTM
    option's half-spread (put-call parity): the pre-open captures quote ITM SPY options 15-30 bp wide, which is staleness,
    not the market. Fill counts follow each claim (stated in every reason). Today's spreads are applied to all history.
  * SKEW tilt (sensitivity, and a criterion where T-147's pass asks for it): IV(m) = IV_flat + (r(m) - r(1)) * VIX *
    (SKEW_t - 100) / (SKEW_ref - 100), where r is the captured SPY smile (IV / VIX by moneyness, ``spy-smile-*``) and
    SKEW_ref the SKEW close on the smile's quote days: the captured smile's shape, scaled by the SKEW index.

Statistics. CIs are 95% two-sided unless the pass says otherwise; percentile circular block bootstraps (2000 resamples,
seed 0) of the statistic the claim names, studentized (bootstrap-t, Bartlett long-run s.e., bandwidth = block) where the
trial names it (T-143, T-144). Overlapping daily holds use blocks of 21 entries (>= the overlap); monthly cycles use 6;
weekly entries 4 weeks, as T-149 states. Differences are bootstrapped PAIRED on one timeline. Deflation for the
thresholds a trial lists is Bonferroni (k thresholds -> alpha / k).

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented
-> at best inconclusive; supported only when every criterion is implemented and passes. Below trial.min_n (in the claim's
own units) the verdict is never supported, and a failing criterion counts only when it fails decisively (its interval
lies wholly on the wrong side).
"""

from __future__ import annotations

import bisect
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.structures import Smile
from mandel.experiments.underlying2 import _mdd, _verdict
from mandel.experiments.volatility import index_closes
from mandel.options import bs
from mandel.validation.backtest_eval import _hac_var, deflated_sharpe_ratio, sharpe_ratio

MONTH = 21                     # sessions per monthly cycle ("30 DTE")
WEEK = 5
YEAR = 252
GAP = 30                       # calendar days between the front and back expiries of a 30/60 structure
N_BOOT = 2000
BLOCK_M = 6                    # bootstrap block for monthly cycles
BLOCK_D = 21                   # bootstrap block for overlapping daily entries (>= the 21-session hold)
BLOCK_W = 4                    # weeks (T-149)
MODEL = "MODEL-PRICED"
SCALES = (0.81, 0.90)          # IV-scale sensitivities (never criteria): the captured SPY ATM IV / VIX ratio was about 0.81

SPY_BASE = ["daily-history-SPY", "cboe-VIX-history", "fred-DTB3"]
TERM_BASE = SPY_BASE + ["cboe-VIX3M-history"]
CHAIN = "options-chain-SPY-"
SURFACE = "options-surface-"
SMILE = "spy-smile-"
VIX6M = "cboe-VIX6M-history"
SKEW = "cboe-SKEW-history"


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


def _names(archive, prefix: str) -> list:
    """Dated bundles ``<prefix><YYYY-MM-DD>`` in the archive index."""
    try:
        ents = archive.entries()
    except Exception:
        return []
    out = []
    for e in ents:
        nm = getattr(e, "name", None) or (e.get("name") if isinstance(e, dict) else None)
        if nm and nm.startswith(prefix) and nm[len(prefix):][:4].isdigit():
            out.append(nm)
    return sorted(set(out))


def _missing(archive, names: Sequence[str], dated: Sequence[str] = ()):
    """Inconclusive naming the missing bundles: fixed names, plus one ``<prefix>*`` per dated family with no bundle."""
    miss = [n for n in names if not _has(archive, n)] + [p + "<date>" for p in dated if not _names(archive, p)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived")
    return None


def _rows(archive, name: str):
    """Rows of a bundle that were available when the bundle was captured."""
    e = archive.get(name)
    cap = getattr(e, "created_at", None) if e is not None else None
    return (r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap))


def _index(archive, name: str) -> dict:
    return _cached(archive, ("index", name), lambda: index_closes(_rows(archive, name)))


def _prices(archive, symbol: str = "SPY"):
    """(days, raw closes, adjcloses) of daily-history-<symbol>; a missing adjclose carries the previous adj/close ratio."""
    def load():
        name = "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in symbol)
        by = {}
        for r in _rows(archive, name):
            v = r["value"]
            c = v.get("close")
            if c is None or not float(c) > 0:
                continue
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
            a = v.get("adjclose")
            by[d] = (float(c), float(a) if a is not None and float(a) > 0 else float("nan"))
        days = sorted(by)
        close = np.array([by[d][0] for d in days], float)
        adj = np.array([by[d][1] for d in days], float)
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return days, close, adj
    return _cached(archive, ("px", symbol), load)


# --------------------------------------------------------------------------------------------- market panel --

def cont_rate(discount_pct: float) -> float:
    """Continuous rate from a 3-month bill discount yield in percent (FRED DTB3)."""
    return -math.log(1.0 - discount_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


def dividends_from_adj(close, adj, tol: float = 1e-4, cap: float = 0.05) -> np.ndarray:
    """Cash dividend D[i] going ex on day i, from the adjclose/close ratio step: D = close[i-1] * (1 - ratio[i-1]/ratio[i]).
    Steps under ``tol`` are rounding and steps over ``cap`` are data errors."""
    close = np.asarray(close, float); ratio = np.asarray(adj, float) / close
    out = np.zeros(close.size)
    for i in range(1, close.size):
        if np.isfinite(ratio[i]) and np.isfinite(ratio[i - 1]) and ratio[i] > 0:
            y = 1.0 - ratio[i - 1] / ratio[i]
            if tol < y < cap:
                out[i] = close[i - 1] * y
    return out


@dataclass
class Market:
    days: list
    close: np.ndarray          # raw closes
    adj: np.ndarray            # total-return closes
    div: np.ndarray            # cash dividend going ex on day i (0 otherwise)
    cal: np.ndarray            # calendar-day ordinal
    rate: np.ndarray           # continuous bill rate known at day i's close (latest DTB3 print dated before day i)
    ex_cal: np.ndarray         # ex-dividend ordinals, realised then projected past the last day
    ex_amt: np.ndarray
    n_projected: int = 0

    def pv_div(self, i, end_cal) -> np.ndarray:
        """PV at day i (discounted at rate[i]) of the dividends going ex in (cal[i], end_cal]."""
        i = np.atleast_1d(np.asarray(i, int))
        end = np.broadcast_to(np.asarray(end_cal, float), i.shape)
        c0 = self.cal[i]; r = self.rate[i]; out = np.zeros(i.shape)
        if not self.ex_cal.size or not i.size:
            return out
        lo = np.searchsorted(self.ex_cal, c0, "right"); hi = np.searchsorted(self.ex_cal, end, "right")
        for k in range(int(np.max(hi - lo, initial=0))):
            j = lo + k; ok = j < hi; jj = np.where(ok, j, 0)
            out += np.where(ok, self.ex_amt[jj] * np.exp(-r * (self.ex_cal[jj] - c0) / 365.0), 0.0)
        return out


def make_market(days: Sequence[str], close, adj, bills: dict) -> Market:
    """``bills`` = {day: DTB3 discount yield in percent}."""
    days = list(days); close = np.asarray(close, float); adj = np.asarray(adj, float)
    div = dividends_from_adj(close, adj)
    cal = np.array([date.fromisoformat(d).toordinal() for d in days], float)
    bd = sorted(bills); bv = [cont_rate(float(bills[d])) for d in bd]
    rate = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        j = bisect.bisect_left(bd, d) - 1                          # latest print dated strictly before d
        if j >= 0:
            rate[i] = bv[j]
    ex = np.nonzero(div > 0)[0]
    ex_cal = [float(cal[k]) for k in ex]; ex_amt = [float(div[k]) for k in ex]; n_proj = 0
    if len(days):
        last = float(cal[-1]); recent = [(c, x) for c, x in zip(ex_cal, ex_amt) if c > last - 365]
        for shift in (364.0, 728.0):
            for c, x in recent:
                if c + shift > last:
                    ex_cal.append(c + shift); ex_amt.append(x); n_proj += 1
    o = np.argsort(ex_cal, kind="stable")
    return Market(days, close, adj, div, cal, rate, np.array(ex_cal, float)[o], np.array(ex_amt, float)[o], n_proj)


def carried(days: Sequence[str], series: dict, scale: float = 100.0) -> np.ndarray:
    """{day: close} -> close/scale per day, carrying the last print (dated on or before the day); NaN before the first."""
    keys = sorted(series); out = np.full(len(days), np.nan); last = float("nan"); j = 0
    for i, d in enumerate(days):
        while j < len(keys) and keys[j] <= d:
            last = float(series[keys[j]]) / scale; j += 1
        out[i] = last
    return out


@dataclass
class Term:
    v30: np.ndarray            # VIX / 100
    v93: np.ndarray            # VIX3M / 100 (NaN before its first print unless proxied)
    v182: np.ndarray           # VIX6M / 100 (NaN before its first print)
    proxy: np.ndarray          # True where v93 is a proxy (named by proxy_label)
    first93: Optional[str] = None
    proxy_label: str = "VIX/VIX6M VIX3M proxy"


def make_term(days: Sequence[str], vix: dict, vix3m: dict, vix6m: Optional[dict] = None, proxy_before: bool = False) -> Term:
    """Term panel aligned to ``days``. ``proxy_before`` fills VIX3M before its first print with the total-variance
    interpolation between VIX (30d) and VIX6M (182d) at 93 days (window sensitivity only)."""
    v30 = carried(days, vix); v93 = carried(days, vix3m) if vix3m else np.full(len(days), np.nan)
    v182 = carried(days, vix6m) if vix6m else np.full(len(days), np.nan)
    proxy = np.zeros(len(days), bool); first = min(vix3m) if vix3m else None
    if proxy_before:
        before = np.array([first is None or d < first for d in days]) & np.isfinite(v30) & np.isfinite(v182)
        w = v30 ** 2 * 30 + (v182 ** 2 * 182 - v30 ** 2 * 30) * (93 - 30) / (182 - 30)
        v93 = np.where(before, np.sqrt(np.maximum(w, 1e-10) / 93), v93); proxy = before
    return Term(v30, v93, v182, proxy, first)


def scaled_term(term: Term, s: float) -> Term:
    """Every IV of the panel multiplied by s (the IV-scale sensitivity; ratios between tenors are unchanged)."""
    return Term(term.v30 * s, term.v93 * s, term.v182 * s, term.proxy, term.first93, term.proxy_label)


def vix_for_vix3m(term: Term, label: str = "VIX-for-VIX3M proxy") -> Term:
    """House data guidance (T-152): VIX stands in for VIX3M where VIX3M has no print (before its first one), so the
    30-to-93-day term is flat and a back leg inside 93 days is priced at VIX. Filled days are marked as proxy (OR-ed with
    any proxy already in ``term``)."""
    fill = ~np.isfinite(term.v93) & np.isfinite(term.v30)
    return Term(term.v30, np.where(fill, term.v30, term.v93), term.v182, term.proxy | fill, term.first93, label)


def vix_for_vix3m_fit(term: Term, T: float = 60.0) -> dict:
    """Error of VIX standing in for VIX3M against the real VIX3M where both print (``term`` = the real panel), in vol
    points: on VIX3M itself and on the T-day back-leg IV the structure prices (total-variance interpolation)."""
    ok = np.flatnonzero(np.isfinite(term.v30) & np.isfinite(term.v93) & ~term.proxy)
    if ok.size < 20:
        return {"n": int(ok.size), "mean_err_3m": None, "mae_3m": None, "mean_err_back": None, "mae_back": None}
    e3 = (term.v30[ok] - term.v93[ok]) * 100
    eb = (term.v30[ok] - term_iv(term, ok, T)) * 100
    return {"n": int(ok.size), "mean_err_3m": float(e3.mean()), "mae_3m": float(np.abs(e3).mean()),
            "mean_err_back": float(eb.mean()), "mae_back": float(np.abs(eb).mean())}


def term_iv(term: Term, i, T_days) -> np.ndarray:
    """IV for a tenor of T_days calendar days at day i (total-variance interpolation, flat-vol extrapolation)."""
    i = np.atleast_1d(np.asarray(i, int))
    T = np.maximum(np.broadcast_to(np.asarray(T_days, float), i.shape), 1e-9)
    s30, s93, s182 = term.v30[i], term.v93[i], term.v182[i]
    w30, w93 = s30 ** 2 * 30, s93 ** 2 * 93
    has6 = np.isfinite(s182); w182 = np.where(has6, s182 ** 2 * 182, np.nan)
    w_mid = w30 + (w93 - w30) * (T - 30) / 63.0
    w_long = np.where(has6, w93 + (w182 - w93) * (T - 93) / 89.0, s93 ** 2 * T)
    w_far = np.where(has6, s182 ** 2 * T, s93 ** 2 * T)
    w = np.where(T <= 30, s30 ** 2 * T, np.where(T <= 93, w_mid, np.where(T <= 182, w_long, w_far)))
    return np.sqrt(np.maximum(w, 1e-10) / T)


# -------------------------------------------------------------------------------------------- pricing helpers --

def intrinsic(S, K, kind: str) -> np.ndarray:
    S = np.asarray(S, float); K = np.asarray(K, float)
    return np.maximum(S - K, 0.0) if kind == "call" else np.maximum(K - S, 0.0)


def px(m: Market, i, end_cal, K, kind: str, sig) -> np.ndarray:
    """Black-Scholes value at day i's close of an option expiring at ordinal end_cal, on the dividend forward."""
    i = np.atleast_1d(np.asarray(i, int)); end = np.broadcast_to(np.asarray(end_cal, float), i.shape)
    T = np.maximum((end - m.cal[i]) / 365.0, 0.0)
    F = m.close[i] - m.pv_div(i, end)
    return np.asarray(bs.price(F, np.broadcast_to(np.asarray(K, float), i.shape), T, m.rate[i],
                               np.broadcast_to(np.asarray(sig, float), i.shape), kind, 0.0), float)


def greeks_at(m: Market, i, end_cal, K, kind: str, sig) -> dict:
    i = np.atleast_1d(np.asarray(i, int)); end = np.broadcast_to(np.asarray(end_cal, float), i.shape)
    T = np.maximum((end - m.cal[i]) / 365.0, 1e-9)
    F = m.close[i] - m.pv_div(i, end)
    return bs.greeks(F, np.broadcast_to(np.asarray(K, float), i.shape), T, m.rate[i], np.broadcast_to(np.asarray(sig, float), i.shape), kind, 0.0)


def k_delta(m: Market, i, end_cal, sig, delta: float, kind: str) -> np.ndarray:
    """Strikes whose Black-Scholes delta (on the dividend forward, q = 0) equals ``delta``."""
    i = np.atleast_1d(np.asarray(i, int)); end = np.broadcast_to(np.asarray(end_cal, float), i.shape)
    sig = np.broadcast_to(np.asarray(sig, float), i.shape)
    F = m.close[i] - m.pv_div(i, end); T = (end - m.cal[i]) / 365.0
    return np.array([bs.strike_for_delta(f, t, r, s, delta, kind, 0.0) for f, t, r, s in zip(F, T, m.rate[i], sig)], float)


# ------------------------------------------------------------------------------------------------ chain costs --

DTE_EDGES = np.array([7, 21, 45, 75, 120, 250, 420], float)
M_STEP, M_MAX = 0.025, 8


def _dte_bucket(dte):
    return np.searchsorted(DTE_EDGES, np.asarray(dte, float), side="left")


def _m_bucket(mny):
    return np.minimum(np.rint(np.abs(np.log(np.asarray(mny, float))) / M_STEP), M_MAX).astype(int)


def _parity_spot(vals: list, q0: date) -> Optional[float]:
    """Spot from put-call parity at the shortest expiry >= 5 days with two-sided call and put quotes."""
    by = defaultdict(dict)
    for v in vals:
        try:
            dte = (date.fromisoformat(v["expiry"]) - q0).days
        except Exception:
            continue
        if dte >= 5 and v.get("bid") and v.get("ask") and v["bid"] > 0 and v["ask"] >= v["bid"]:
            by[(dte, v["expiry"])].setdefault(float(v["strike"]), {})[v.get("type")] = (v["bid"] + v["ask"]) / 2
    for key in sorted(by):
        both = [(K, d["call"], d["put"]) for K, d in by[key].items() if "call" in d and "put" in d]
        if len(both) >= 5:
            K, c, p = min(both, key=lambda x: abs(x[1] - x[2]))
            return float(K + c - p)
    return None


@dataclass
class Spreads:
    """Half bid-ask spread per contract fill as a fraction of spot, by DTE and |log moneyness| bucket (OTM quotes)."""
    table: np.ndarray
    quote_days: list = field(default_factory=list)
    n_quotes: int = 0

    @classmethod
    def zero(cls) -> "Spreads":
        return cls(np.zeros((DTE_EDGES.size + 1, M_MAX + 1)), [], 0)

    @classmethod
    def from_chains(cls, chains: Sequence[Sequence[dict]]) -> "Spreads":
        cells = defaultdict(list); qdays = []; nq = 0
        for rows in chains:
            vals = [r["value"] for r in rows if isinstance(r.get("value"), dict)]
            lt = Counter((v.get("last_time") or "")[:10] for v in vals if v.get("last_time"))
            if not lt:
                continue
            qd = lt.most_common(1)[0][0]; q0 = date.fromisoformat(qd)          # the session the quotes belong to
            S = _parity_spot(vals, q0)
            if not S:
                continue
            qdays.append(qd)
            for v in vals:
                bid, ask, K = v.get("bid"), v.get("ask"), v.get("strike")
                if not (bid and ask and K) or not (bid > 0 and ask > bid):
                    continue
                mny = float(K) / S; kind = v.get("type")
                if (kind == "call" and mny < 1) or (kind == "put" and mny > 1):
                    continue                                                   # OTM quotes only (ITM by parity)
                dte = (date.fromisoformat(v["expiry"]) - q0).days
                if dte < 0:
                    continue
                cells[(int(_dte_bucket(dte)), int(_m_bucket(mny)))].append((ask - bid) / 2 / S); nq += 1
        t = np.full((DTE_EDGES.size + 1, M_MAX + 1), np.nan)
        for (i, j), xs in cells.items():
            t[i, j] = float(np.median(xs))
        for i in range(t.shape[0]):                                            # fill gaps: nearest moneyness bucket
            ok = np.flatnonzero(np.isfinite(t[i]))
            if ok.size:
                for j in range(t.shape[1]):
                    if not np.isfinite(t[i, j]):
                        t[i, j] = t[i, ok[np.argmin(np.abs(ok - j))]]
        rows_ok = np.flatnonzero(np.isfinite(t[:, 0]))
        if not rows_ok.size:
            return cls.zero()
        for i in range(t.shape[0]):                                            # then nearest DTE bucket
            if not np.isfinite(t[i, 0]):
                t[i] = t[rows_ok[np.argmin(np.abs(rows_ok - i))]]
        return cls(t, sorted(set(qdays)), nq)

    def frac(self, dte, mny) -> np.ndarray:
        return self.table[_dte_bucket(dte), _m_bucket(mny)]

    def cost(self, dte, K, S) -> np.ndarray:
        """Half-spread in price units for one contract fill (per unit of underlying)."""
        S = np.asarray(S, float)
        return np.asarray(self.frac(dte, np.asarray(K, float) / S), float) * S

    def describe(self) -> str:
        if not self.n_quotes:
            return "no chain costs"
        return (f"half-spread per fill from {self.n_quotes} OTM SPY quotes on {', '.join(self.quote_days)} (30-DTE ATM "
                f"{self.frac(30, 1.0) * 1e4:.2f} bp of spot, 60-DTE 5% OTM {self.frac(60, 1.05) * 1e4:.2f} bp, 365-DTE 15% "
                f"from spot {self.frac(365, 0.85) * 1e4:.2f} bp)")


# --------------------------------------------------------------------------------------------- SKEW smile tilt --

class Tilt:
    """IV(m) = base + (r(m) - r(1)) * VIX_t * (SKEW_t - 100) / (SKEW_ref - 100): the captured SPY smile's shape (IV/VIX by
    moneyness, nearest of its 30/45-day curves) scaled by the SKEW index relative to its level on the smile quote days."""

    def __init__(self, smile_rows: list, skew_by_day: np.ndarray, v30: np.ndarray, skew_ref: float):
        self.smile = Smile(smile_rows); self.skew = np.asarray(skew_by_day, float); self.v30 = v30
        self.ref = float(skew_ref); self.n_days = self.smile.n_days

    @classmethod
    def build(cls, smile_rows: list, days: Sequence[str], skew: dict, v30: np.ndarray) -> Optional["Tilt"]:
        if not smile_rows or not skew:
            return None
        qd = sorted({r["value"]["quote_date"] for r in smile_rows})
        ref = [float(skew[q]) for q in qd if q in skew]
        if not ref or not np.mean(ref) > 100.5:
            return None
        return cls(smile_rows, carried(days, skew, 1.0), v30, float(np.mean(ref)))

    def ratio(self, mny, dte) -> np.ndarray:
        mny = np.asarray(mny, float); dte = np.broadcast_to(np.asarray(dte, float), mny.shape)
        keys = np.array(sorted(self.smile.curves), float); out = np.empty(mny.shape)
        pick = keys[np.abs(dte[..., None] - keys).argmin(axis=-1)]
        for k in keys:
            ks, rs = self.smile.curves[k]; sel = pick == k
            out[sel] = np.interp(mny[sel], ks, rs)
        return out

    def sig(self, base, i, K, S, dte) -> np.ndarray:
        i = np.atleast_1d(np.asarray(i, int)); K = np.broadcast_to(np.asarray(K, float), i.shape)
        S = np.broadcast_to(np.asarray(S, float), i.shape); dte = np.broadcast_to(np.asarray(dte, float), i.shape)
        dev = self.ratio(K / S, dte) - self.ratio(np.ones(i.shape), dte)
        f = (self.skew[i] - 100.0) / (self.ref - 100.0)
        return np.maximum(np.asarray(base, float) + dev * self.v30[i] * np.where(np.isfinite(f), f, 0.0), 0.01)


# ------------------------------------------------------------------------------------------------ statistics --

def _bidx(rng, n: int, block: int, rows: int) -> np.ndarray:
    nb = math.ceil(n / block)
    st = rng.integers(0, n, (rows, nb))
    return ((st[:, :, None] + np.arange(block)[None, None, :]).reshape(rows, -1)[:, :n]) % n


def _chunks(n_boot: int, chunk: int = 250):
    b = 0
    while b < n_boot:
        yield min(chunk, n_boot - b); b += chunk


def _blk(block: int, n: int) -> int:
    return max(1, min(int(block), max(1, n // 4)))


def boot_dist(n: int, fn: Callable[[np.ndarray], np.ndarray], block: int, n_boot: int = N_BOOT, seed: int = 0) -> np.ndarray:
    """Percentile circular block bootstrap: fn(idx rows) -> one statistic per resample row."""
    rng = np.random.default_rng(seed); block = _blk(block, n); out = []
    for rows in _chunks(n_boot):
        out.append(np.asarray(fn(_bidx(rng, n, block, rows)), float))
    return np.concatenate(out) if out else np.array([])


def _q(x, p):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    return float(np.quantile(x, p)) if x.size else float("nan")


def boot_mean_t(x, block: int, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """Studentized circular block bootstrap of a mean: {'est', 's', 't'} (t = resample t-statistics)."""
    x = np.asarray(x, float); n = x.size
    if n < 3:
        return {"est": float(x.mean()) if n else float("nan"), "s": float("nan"), "t": np.array([])}
    block = _blk(block, n); m0 = float(x.mean()); s0 = math.sqrt(float(_hac_var(x[None, :], block)[0]) / n)
    rng = np.random.default_rng(seed); ts = []
    for rows in _chunks(n_boot):
        xb = x[_bidx(rng, n, block, rows)]
        ts.append((xb.mean(axis=1) - m0) / np.sqrt(_hac_var(xb, block) / n))
    return {"est": m0, "s": s0, "t": np.concatenate(ts)}


def boot_group_diff_t(x, g1, g2, block: int, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    """Studentized circular block bootstrap of mean(x | g1) - mean(x | g2) on one timeline: whole periods are resampled
    with their labels and each resample is studentized by the Bartlett long-run s.e. of its influence series."""
    x = np.asarray(x, float); g1 = np.asarray(g1, bool); g2 = np.asarray(g2, bool); n = x.size
    block = _blk(block, n)
    def est(X, A, B):
        n1, n2 = A.sum(axis=1), B.sum(axis=1)
        m1 = np.where(n1 > 0, (X * A).sum(axis=1) / np.maximum(n1, 1), np.nan)
        m2 = np.where(n2 > 0, (X * B).sum(axis=1) / np.maximum(n2, 1), np.nan)
        p1, p2 = np.maximum(n1, 1) / n, np.maximum(n2, 1) / n
        infl = np.where(A, (X - m1[:, None]) / p1[:, None], 0.0) - np.where(B, (X - m2[:, None]) / p2[:, None], 0.0)
        s = np.sqrt(_hac_var(np.nan_to_num(infl), block) / n)
        ok = (n1 >= 2) & (n2 >= 2)
        return np.where(ok, m1 - m2, np.nan), np.where(ok, s, np.nan)
    d0, s0 = (float(v[0]) for v in est(x[None, :], g1[None, :], g2[None, :]))
    if not np.isfinite(d0):
        return {"est": d0, "s": float("nan"), "t": np.array([])}
    rng = np.random.default_rng(seed); ts = []
    for rows in _chunks(n_boot):
        idx = _bidx(rng, n, block, rows)
        d, s = est(x[idx], g1[idx], g2[idx])
        ts.append((d - d0) / s)
    t = np.concatenate(ts)
    return {"est": d0, "s": s0, "t": t[np.isfinite(t)]}


def t_bounds(res: dict, alpha: float, two_sided: bool = True) -> tuple:
    """(lower, upper) of a bootstrap-t interval: two-sided at 1 - alpha, or the two one-sided bounds at 1 - alpha."""
    est, s, t = res["est"], res["s"], res["t"]
    if not (np.isfinite(est) and np.isfinite(s)) or t.size < 10:
        return float("nan"), float("nan")
    if s <= 1e-15:
        return est, est
    a = alpha / 2 if two_sided else alpha
    return est - _q(t, 1 - a) * s, est - _q(t, a) * s


def t_pvalue(res: dict) -> float:
    """One-sided bootstrap-t p-value for H0: statistic <= 0."""
    est, s, t = res["est"], res["s"], res["t"]
    if not (np.isfinite(est) and np.isfinite(s)) or t.size < 10:
        return float("nan")
    if s <= 1e-15:
        return 0.0 if est > 0 else 1.0
    return float((np.sum(t >= est / s) + 1) / (t.size + 1))


def boot_mean_ci(x, block: int, n_boot: int = N_BOOT, seed: int = 0, alpha: float = 0.05) -> tuple:
    x = np.asarray(x, float)
    if x.size < 2:
        return float("nan"), float("nan")
    d = boot_dist(x.size, lambda idx: x[idx].mean(axis=1), block, n_boot, seed)
    return _q(d, alpha / 2), _q(d, 1 - alpha / 2)


def _sr_rows(X: np.ndarray, ppy: float) -> np.ndarray:
    m = X.mean(axis=-1); s = X.std(axis=-1, ddof=1)
    return np.where(s > 0, m / np.where(s > 0, s, 1.0), 0.0) * math.sqrt(ppy)


def sharpe_diff_ci(a, b, ppy: float, block: int = BLOCK_M, n_boot: int = N_BOOT, seed: int = 0) -> tuple:
    """(Sharpe(a) - Sharpe(b), 95% lower, 95% upper): paired circular block bootstrap (percentile)."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.size < 4:
        return float("nan"), float("nan"), float("nan")
    obs = float(_sr_rows(a[None, :], ppy)[0] - _sr_rows(b[None, :], ppy)[0])
    d = boot_dist(a.size, lambda idx: _sr_rows(a[idx], ppy) - _sr_rows(b[idx], ppy), block, n_boot, seed)
    return obs, _q(d, 0.025), _q(d, 0.975)


def swap_perm_p(a, b, ppy: float, n_perm: int = N_BOOT, seed: int = 0) -> float:
    """One-sided p of Sharpe(a) - Sharpe(b) under the null that each month's pair is exchangeable (swapped at random)."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.size < 4:
        return float("nan")
    obs = float(_sr_rows(a[None, :], ppy)[0] - _sr_rows(b[None, :], ppy)[0])
    sw = np.random.default_rng(seed).random((n_perm, a.size)) < 0.5
    A = np.where(sw, b, a); B = np.where(sw, a, b)
    null = _sr_rows(A, ppy) - _sr_rows(B, ppy)
    return float((np.sum(null >= obs) + 1) / (n_perm + 1))


def rank_avg(x) -> np.ndarray:
    """Ranks with ties averaged (0-based)."""
    x = np.asarray(x, float); n = x.size
    o = np.argsort(x, kind="mergesort"); xs = x[o]
    new = np.concatenate([[True], xs[1:] != xs[:-1]]) if n else np.array([], bool)
    grp = np.cumsum(new) - 1; starts = np.flatnonzero(new); cnt = np.bincount(grp) if n else np.array([], int)
    r = np.empty(n); r[o] = (starts + (cnt - 1) / 2.0)[grp]
    return r


def spearman(a, b) -> float:
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.size < 3:
        return float("nan")
    ra, rb = rank_avg(a), rank_avg(b)
    ra -= ra.mean(); rb -= rb.mean(); den = math.sqrt(float(ra @ ra) * float(rb @ rb))
    return float(ra @ rb / den) if den > 0 else 0.0


def spearman_ci(a, b, block: int, n_boot: int = N_BOOT, seed: int = 0) -> tuple:
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.size < 8:
        return spearman(a, b), float("nan"), float("nan")
    d = boot_dist(a.size, lambda idx: np.array([spearman(a[r], b[r]) for r in idx]), block, n_boot, seed)
    return spearman(a, b), _q(d, 0.025), _q(d, 0.975)


def shift_null(stat: Callable[[int], float], n: int, min_shift: int, n_boot: int = N_BOOT, seed: int = 0) -> np.ndarray:
    """Circular block-shift null: stat(k) for random shifts k in [min_shift, n - min_shift)."""
    if n <= 2 * min_shift + 1:
        return np.array([])
    ks = np.random.default_rng(seed).integers(min_shift, n - min_shift, n_boot)
    out = np.array([stat(int(k)) for k in ks], float)
    return out[np.isfinite(out)]


class Criteria:
    """Criteria with the min_n rule: below min_n a failing criterion stands only when it fails decisively."""

    def __init__(self):
        self.items, self.decisive = [], []

    def add(self, name: str, ok, decisive: bool = False):
        self.items.append((name, None if ok is None else bool(ok))); self.decisive.append(bool(decisive))

    def finish(self, n: int, min_n: int, unit: str) -> tuple:
        crit = list(self.items)
        if n < min_n:
            crit = [(nm, None if (ok is not None and not ok and not dec) else ok) for (nm, ok), dec in zip(crit, self.decisive)]
        crit.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
        return _verdict(crit)


def _ok(lo, hi, side: str, thr: float = 0.0):
    """CI criterion: (ok, decisive). side 'gt': pass if lo > thr (decisive failure if hi < thr); 'lt': pass if hi < thr
    (decisive failure if lo > thr); 'not_above': pass unless lo > thr (decisive failure = lo > thr)."""
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return None, False
    if side == "gt":
        return lo > thr, hi < thr
    if side == "lt":
        return hi < thr, lo > thr
    return not lo > thr, lo > thr


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _wrap(rep: dict):
    rep = _clean(rep)
    return rep, int(rep.get("n") or 0), rep["verdict"], rep["reason"]


def _p(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:+.{nd}f}%"


def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _pv(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.4f}"


def _ci_txt(lo, hi, fmt=_p, level: str = "95%") -> str:
    return f"{level} CI {fmt(lo)} to {fmt(hi)}"


def _mean(x) -> float:
    x = np.asarray(x, float)
    return float(x.mean()) if x.size else float("nan")


def _halves_idx(n: int) -> tuple:
    h = n // 2
    return np.arange(0, h), np.arange(h, n)


def _start_index(m: Market, term: Term, start: str, need93: bool = True) -> int:
    i = bisect.bisect_left(m.days, start)
    while i < len(m.days):
        ok = np.isfinite(term.v30[i]) and term.v30[i] > 0 and np.isfinite(m.rate[i])
        if need93:
            ok = ok and np.isfinite(term.v93[i])
        if ok:
            return i
        i += 1
    return len(m.days)


def daily_entries(m: Market, term: Term, start: str, hold: int = MONTH, need93: bool = True) -> np.ndarray:
    i0 = _start_index(m, term, start, need93)
    return np.arange(i0, max(i0, len(m.days) - hold))


def grid(m: Market, term: Term, start: str, step: int, need93: bool = True) -> np.ndarray:
    """Grid of entry indices every ``step`` sessions from the first usable day (the last point may lack a full cycle)."""
    i0 = _start_index(m, term, start, need93)
    return np.arange(i0, len(m.days), step)


# --------------------------------------------------------------------------------------- two-expiry engine --

def two_expiry(m: Market, term: Term, a, legs: list, spreads: Spreads, hold: int = MONTH, gap: float = GAP,
               tilt: Optional[Tilt] = None, back_shift: float = 0.0, close_front: bool = True) -> dict:
    """Enter at the close of a; front legs expire at the close hold sessions later (b) and settle at intrinsic on the raw
    close; back legs expire ``gap`` calendar days after the front and are re-priced at b with the then-current term IV
    for their remaining ``gap`` days. legs: (kind, side, qty, K array, 'front'|'back'). Front IV = VIX; back IV at entry =
    term_iv(a, days to back expiry) + back_shift. Costs: half-spread per contract on every open, every back-leg close and
    (close_front) every front-leg close at b. Returns per-entry arrays (debit > 0 = paid)."""
    a = np.asarray(a, int); b = a + hold
    E1 = m.cal[b]; E2 = E1 + gap; S0 = m.close[a]; S1 = m.close[b]
    vf = term.v30[a]; vb0 = term_iv(term, a, E2 - m.cal[a]) + back_shift; vb1 = term_iv(term, b, np.full(a.size, float(gap)))
    debit = np.zeros(a.size); val1 = np.zeros(a.size); cost = np.zeros(a.size); prem, sigs = [], []
    for kind, side, qty, K, tenor in legs:
        sgn = 1.0 if side == "long" else -1.0; K = np.broadcast_to(np.asarray(K, float), a.shape)
        if tenor == "front":
            s0 = vf if tilt is None else tilt.sig(vf, a, K, S0, E1 - m.cal[a])
            p0 = px(m, a, E1, K, kind, s0); v1 = intrinsic(S1, K, kind)
            c = spreads.cost(E1 - m.cal[a], K, S0) + (spreads.cost(0.0, K, S1) if close_front else 0.0)
        else:
            s0 = vb0 if tilt is None else tilt.sig(vb0, a, K, S0, E2 - m.cal[a])
            s1 = vb1 if tilt is None else tilt.sig(vb1, b, K, S1, np.full(a.size, float(gap)))
            p0 = px(m, a, E2, K, kind, s0); v1 = px(m, b, E2, K, kind, s1)
            c = spreads.cost(E2 - m.cal[a], K, S0) + spreads.cost(float(gap), K, S1)
        debit += sgn * qty * p0; val1 += sgn * qty * v1; cost += qty * c; prem.append(p0); sigs.append(s0)
    return {"a": a, "b": b, "E1": E1, "E2": E2, "S0": S0, "S1": S1, "debit": debit, "val1": val1, "cost": cost,
            "pnl": val1 - debit - cost, "prem": prem, "sig": sigs, "vf": vf, "vb0": vb0, "vb1": vb1}


def _window_note(term: Term, m: Market, a) -> str:
    a = np.asarray(a, int)
    if not a.size:
        return "no entries"
    prox = int(term.proxy[a].sum())
    return (f"{m.days[int(a[0])]} to {m.days[int(a[-1])]}" + (f" ({prox} entries on the {term.proxy_label})" if prox else ""))


def _proxy_fit(term_real: Term, term_proxy_full: Term) -> str:
    """Error of the VIX/VIX6M VIX3M proxy against the real VIX3M where both exist."""
    v6, v3, v1 = term_proxy_full.v182, term_real.v93, term_real.v30
    ok = np.isfinite(v6) & np.isfinite(v3) & np.isfinite(v1)
    if ok.sum() < 20:
        return "proxy fit n/a"
    w = v1[ok] ** 2 * 30 + (v6[ok] ** 2 * 182 - v1[ok] ** 2 * 30) * 63 / 152; pr = np.sqrt(np.maximum(w, 1e-10) / 93)
    err = (pr - v3[ok]) * 100
    return f"proxy vs real VIX3M on {int(ok.sum())} overlap days: mean error {err.mean():+.2f} vol pts, mean |error| {np.abs(err).mean():.2f}"


# ------------------------------------------------------------------------------------ T-143 long calendar --

def judge_regime(x, ratio, x_sens=None, min_n: int = 30, n_boot: int = N_BOOT, hi_thr: float = 1.0, lo_thr: float = 0.9,
                 k_thr: int = 3, block: int = BLOCK_D, monthly_step: int = MONTH, need_sens: bool = True) -> dict:
    """T-143 statistics on daily entries: diff = mean(x | ratio >= hi_thr) - mean(x | ratio <= lo_thr).
    Criteria: diff > 0 with block-shift p x k_thr < 0.05; studentized block bootstrap deflated one-sided lower bound > 0;
    diff > 0 in both walk-forward halves; diff > 0 in the sensitivity rerun ``x_sens`` (not implemented when it is None
    and ``need_sens``)."""
    x = np.asarray(x, float); ratio = np.asarray(ratio, float); n = x.size
    hi = ratio >= hi_thr; lo = ratio <= lo_thr
    d0 = _mean(x[hi]) - _mean(x[lo]) if hi.any() and lo.any() else float("nan")
    lab_hi, lab_lo = hi.copy(), lo.copy()
    def stat(k):
        h, l = np.roll(lab_hi, k), np.roll(lab_lo, k)
        return _mean(x[h]) - _mean(x[l]) if h.any() and l.any() else float("nan")
    null = shift_null(stat, n, block, n_boot)
    p_up = float((np.sum(null >= d0) + 1) / (null.size + 1)) if null.size and np.isfinite(d0) else float("nan")
    p_dn = float((np.sum(null <= d0) + 1) / (null.size + 1)) if null.size and np.isfinite(d0) else float("nan")
    bt = boot_group_diff_t(x, hi, lo, block, n_boot)
    lo_d, _ = t_bounds(bt, 0.05 / k_thr, two_sided=False)
    _, hi_d = t_bounds(bt, 0.05 / k_thr, two_sided=False)
    p_t = t_pvalue(bt)
    i1, i2 = _halves_idx(n)
    halves = [(_mean(x[ii][hi[ii]]) - _mean(x[ii][lo[ii]])) if hi[ii].any() and lo[ii].any() else float("nan") for ii in (i1, i2)]
    mo = np.arange(0, n, monthly_step); xm, him, lom = x[mo], hi[mo], lo[mo]
    dm = boot_dist(mo.size, lambda idx: np.array([_mean(xm[r][him[r]]) - _mean(xm[r][lom[r]]) if him[r].any() and lom[r].any() else np.nan for r in idx]), 1, n_boot)
    d_sens = None
    if x_sens is not None:
        xs = np.asarray(x_sens, float); d_sens = _mean(xs[hi]) - _mean(xs[lo]) if hi.any() and lo.any() else float("nan")
    c = Criteria()
    ok1 = (d0 > 0 and min(1.0, k_thr * p_up) < 0.05) if np.isfinite(p_up) else None
    c.add(f"difference > 0 with block-shift p x{k_thr} < 0.05", ok1, bool(np.isfinite(p_dn) and k_thr * p_dn < 0.05))
    ok2, dec2 = _ok(lo_d, hi_d, "gt")
    c.add(f"studentized block-{block} bootstrap: one-sided {100 - 5 / k_thr:.2f}% lower bound > 0", ok2, dec2)
    hv = all(np.isfinite(h) for h in halves)
    c.add("difference > 0 in both walk-forward halves", (all(h > 0 for h in halves)) if hv else None)
    if x_sens is not None or need_sens:
        c.add("sensitivity rerun at the captured 30/60-DTE ATM IV spread: difference > 0"
              + ("" if x_sens is not None else " (no SPY surface capture on a day with VIX and VIX3M)"),
              (d_sens > 0) if d_sens is not None and np.isfinite(d_sens) else None)
    n_small = int(min(hi.sum(), lo.sum()))
    v, why = c.finish(n_small, min_n, "daily entries in the smaller regime")
    return {"verdict": v, "why": why, "n": n_small, "n_days": n, "n_high": int(hi.sum()), "n_low": int(lo.sum()),
            "mean_high": _mean(x[hi]), "mean_low": _mean(x[lo]), "difference": d0, "p_shift": p_up,
            "p_shift_deflated": min(1.0, k_thr * p_up) if np.isfinite(p_up) else None, "p_studentized": p_t,
            "p_studentized_deflated": min(1.0, k_thr * p_t) if np.isfinite(p_t) else None, "lower_deflated": lo_d,
            "upper_deflated": hi_d, "halves": halves, "monthly": {"n": int(mo.size), "n_high": int(him.sum()), "n_low": int(lom.sum()),
            "difference": (_mean(xm[him]) - _mean(xm[lom])) if him.any() and lom.any() else None, "ci": [_q(dm, 0.025), _q(dm, 0.975)]},
            "difference_sensitivity": d_sens, "min_n": min_n}


def long_calendar(m: Market, term: Term, a, spreads: Spreads, back_shift: float = 0.0, tilt: Optional[Tilt] = None) -> dict:
    """30/60-DTE ATM call calendar: short the front, long the back at the same strike (K = entry close)."""
    K = m.close[np.asarray(a, int)]
    r = two_expiry(m, term, a, [("call", "short", 1, K, "front"), ("call", "long", 1, K, "back")], spreads, tilt=tilt, back_shift=back_shift)
    r["x"] = r["pnl"] / r["debit"]
    return r


def eval_long_calendar(m: Market, term: Term, spreads: Spreads, start: str, spread_shift: Optional[float] = None,
                       shift_note: str = "", min_n: int = 30, n_boot: int = N_BOOT, headline_only: bool = False) -> dict:
    a = daily_entries(m, term, start)
    res = long_calendar(m, term, a, spreads); x = res["x"]; ratio = term.v30[a] / term.v93[a]
    hi, lo = ratio >= 1.0, ratio <= 0.9
    head = _mean(x[hi]) - _mean(x[lo]) if hi.any() and lo.any() else float("nan")
    if headline_only:
        return {"headline": head, "n_high": int(hi.sum()), "n_low": int(lo.sum()), "window": _window_note(term, m, a)}
    x_sens = long_calendar(m, term, a, spreads, back_shift=spread_shift)["x"] if spread_shift is not None else None
    j = judge_regime(x, ratio, x_sens, min_n, n_boot)
    yrs = {}
    for y in ("2008", "2011", "2020", "2022"):
        keep = np.array([not m.days[int(i)].startswith(y) for i in a], bool)
        if not (~keep).any():
            yrs[y] = "no entries in window"
        else:
            yrs[y] = (_mean(x[keep & hi]) - _mean(x[keep & lo])) if (keep & hi).any() and (keep & lo).any() else None
    reason = (f"{MODEL} (model-only until >= 120 daily chain captures confirm the front/back ATM IV spread; 2 archived) "
              f"30/60-DTE ATM SPY call calendar, front IV = VIX, back IV = VIX/VIX3M total-variance interpolation, held to the "
              f"front expiry (21 sessions) and the back leg re-priced at that day's VIX for its last 30 days; costs = "
              f"{spreads.describe()} on 4 fills (open both legs, close both at T1); daily entries "
              f"{_window_note(term, m, a)}. P&L/debit: "
              f"VIX/VIX3M >= 1.0 mean {_p(j['mean_high'])} on {j['n_high']} days vs <= 0.9 mean {_p(j['mean_low'])} on "
              f"{j['n_low']} days, difference {_p(j['difference'])}; block-shift p = {_pv(j['p_shift'])} (x3 thresholds = "
              f"{_pv(j['p_shift_deflated'])}); studentized block-21 bootstrap one-sided 98.33% bounds {_p(j['lower_deflated'])} / "
              f"{_p(j['upper_deflated'])} (p x3 = {_pv(j['p_studentized_deflated'])}); walk-forward halves {_p(j['halves'][0])} / "
              f"{_p(j['halves'][1])}; sensitivity rerun with the back IV shifted {_f(spread_shift * 100 if spread_shift is not None else None)} "
              f"vol pts to the captured spread{shift_note}: difference {_p(j['difference_sensitivity'])}; non-overlapping monthly "
              f"entries (plain bootstrap, report only): {j['monthly']['n_high']} high vs {j['monthly']['n_low']} low, difference "
              f"{_p(j['monthly']['difference'])} ({_ci_txt(*j['monthly']['ci'])}); leave-one-year-out differences: "
              + ", ".join(f"ex-{y} {(_p(v) if not isinstance(v, str) else v)}" for y, v in yrs.items()))
    out = dict(j); out.update({"leave_year_out": yrs, "spread_shift": spread_shift, "model_priced": True, "reason_core": reason,
                               "window": _window_note(term, m, a), "headline": head})
    return out


# ------------------------------------------------------------------------------------ T-144 short calendar --

def spike_months(days: Sequence[str], vix: np.ndarray, top: int = 5, lo_day: str = "", hi_day: str = "9999") -> list:
    """Calendar months with the largest VIX spike: max VIX close in the month minus the prior month's last close."""
    last, mx = {}, {}
    for d, v in zip(days, vix):
        if not np.isfinite(v):
            continue
        mo = d[:7]; last[mo] = v; mx[mo] = max(mx.get(mo, -np.inf), v)
    ms = sorted(last); sp = []
    for k in range(1, len(ms)):
        if lo_day[:7] <= ms[k] <= hi_day[:7]:
            sp.append((mx[ms[k]] - last[ms[k - 1]], ms[k]))
    return [mo for _, mo in sorted(sp, reverse=True)[:top]]


def judge_conditional_mean(x, keep_ex=None, min_n: int = 60, n_boot: int = N_BOOT, k_thr: int = 3, block: int = BLOCK_D) -> dict:
    """T-144: conditional mean > 0 with the deflated (Bonferroni over k_thr thresholds) studentized CI excluding 0 in both
    walk-forward halves, all entries and with ``keep_ex`` (entries outside the spike months)."""
    x = np.asarray(x, float); n = x.size; alpha = 0.05 / k_thr
    keep_ex = np.ones(n, bool) if keep_ex is None else np.asarray(keep_ex, bool)
    c = Criteria(); rows = {}
    for label, xx in (("all", x), ("ex-spikes", x[keep_ex])):
        i1, i2 = _halves_idx(xx.size)
        for hname, ii in (("first half", i1), ("second half", i2)):
            res = boot_mean_t(xx[ii], block, n_boot); lo, hi = t_bounds(res, alpha)
            ok, dec = _ok(lo, hi, "gt")
            c.add(f"{label} {hname}: mean > 0 with the {100 * (1 - alpha):.2f}% studentized CI excluding 0", ok, dec)
            rows[f"{label} {hname}"] = {"n": int(ii.size), "mean": _mean(xx[ii]), "ci": [lo, hi]}
    v, why = c.finish(n, min_n, "conditional entries")
    return {"verdict": v, "why": why, "n": n, "mean": _mean(x), "halves": rows, "min_n": min_n}


def short_calendar(m: Market, term: Term, a, spreads: Spreads) -> dict:
    """Short 30/60 ATM call calendar (long the front, short the back); x = P&L / back-leg premium."""
    K = m.close[np.asarray(a, int)]
    r = two_expiry(m, term, a, [("call", "long", 1, K, "front"), ("call", "short", 1, K, "back")], spreads)
    r["x"] = r["pnl"] / r["prem"][1]
    return r


def eval_short_calendar(m: Market, term: Term, spreads: Spreads, start: str, gate: float = 1.15, min_n: int = 60,
                        n_boot: int = N_BOOT, headline_only: bool = False) -> dict:
    a = daily_entries(m, term, start)
    res = short_calendar(m, term, a, spreads); x = res["x"]; slope = term.v93[a] / term.v30[a]
    g = slope >= gate; xc = x[g]; ac = a[g]
    if headline_only:
        return {"headline": _mean(xc), "n": int(g.sum()), "window": _window_note(term, m, a)}
    sp = spike_months(m.days, term.v30 * 100, 5, m.days[int(a[0])] if a.size else "", m.days[int(a[-1] + MONTH)] if a.size else "")
    keep = np.array([m.days[int(i)][:7] not in sp and m.days[int(i + MONTH)][:7] not in sp for i in ac], bool)
    j = judge_conditional_mean(xc, keep, min_n, n_boot)
    def placebo(k):
        gg = np.roll(g, k)
        return _mean(x[gg]) if gg.any() else float("nan")
    null = shift_null(placebo, x.size, BLOCK_D, n_boot)
    p_pl = float((np.sum(null >= _mean(xc)) + 1) / (null.size + 1)) if null.size and xc.size else float("nan")
    q1, q2 = (np.quantile(term.v30[a], [1 / 3, 2 / 3]) if a.size else (np.nan, np.nan))
    terc = {}
    for nm, msk in (("low", term.v30[ac] <= q1), ("mid", (term.v30[ac] > q1) & (term.v30[ac] <= q2)), ("high", term.v30[ac] > q2)):
        terc[nm] = {"n": int(msk.sum()), "mean": _mean(xc[msk]) if msk.any() else None}
    unc = boot_mean_t(x, BLOCK_D, n_boot); ulo, uhi = t_bounds(unc, 0.05)
    other = {f"{t:.2f}": {"n": int((slope >= t).sum()), "mean": _mean(x[slope >= t]) if (slope >= t).any() else None} for t in (1.10, 1.20)}
    hv = j["halves"]
    reason = (f"{MODEL} short 30/60-DTE ATM SPY call calendar (long the 30-DTE front at VIX, short the back at the VIX/VIX3M "
              f"interpolation), closed at the front expiry with the back re-priced at that day's VIX; P&L per unit of the back "
              f"leg's premium after {spreads.describe()} on 4 fills; daily entries {_window_note(term, m, a)} on days with "
              f"VIX3M/VIX >= {gate:.2f}: {j['n']} conditional entries, mean {_p(j['mean'])}; deflated (x3 thresholds) "
              f"studentized block-21 98.33% CIs: "
              + "; ".join(f"{k} {_p(r['mean'])} (n {r['n']}, {_ci_txt(*r['ci'], level='98.33%')})" for k, r in hv.items())
              + f"; spike months removed: {', '.join(sp) if sp else 'none'} ({int((~keep).sum())} entries); placebo (gate block-shifted) "
              f"p = {_pv(p_pl)}; unconditional mean {_p(_mean(x))} on {x.size} days ({_ci_txt(ulo, uhi)}); other gates (report "
              f"only): " + ", ".join(f">= {k} n {v['n']} mean {_p(v['mean'])}" for k, v in other.items())
              + "; VIX-tercile control of the conditional mean: " + ", ".join(f"{k} {_p(v['mean'])} (n {v['n']})" for k, v in terc.items()))
    out = dict(j); out.update({"spike_months": sp, "n_ex_spikes": int(keep.sum()), "placebo_p": p_pl, "unconditional": {"n": int(x.size),
               "mean": _mean(x), "ci": [ulo, uhi]}, "other_gates": other, "vix_terciles": terc, "model_priced": True,
               "reason_core": reason, "headline": _mean(xc), "window": _window_note(term, m, a)})
    return out


# ------------------------------------------------------------------------------- rolling (monthly) engines --

def long_schedule(m: Market, g: np.ndarray, L: int, extra: float, kind: str, delta: float, iv_fn: Callable, spreads: Spreads,
                  tilt: Optional[Tilt] = None) -> dict:
    """A long option bought at grid point j*L with expiry at grid point (j+1)*L plus ``extra`` days (so ``extra`` days remain
    at replacement), strike at ``delta`` (solved at the flat IV), marked at every grid point with iv_fn(i, days left).
    Per cycle k (g[k] -> g[k+1]): v0, v1 (value at both ends), cost (open fill at purchase, close fill at replacement)."""
    N = len(g) - 1
    K = np.full(N, np.nan); E = np.full(N, np.nan); cost = np.zeros(N); first = np.zeros(N, bool)
    for j in range(0, N, L):
        a = int(g[j])
        Ej = float(m.cal[g[j + L]] + extra) if j + L < len(g) else float(m.cal[a] + L * MONTH * 365.0 / YEAR + extra)
        T = Ej - m.cal[a]; s = iv_fn(np.array([a]), np.array([T]))
        Kj = float(k_delta(m, [a], Ej, s, delta, kind)[0])
        K[j:min(j + L, N)] = Kj; E[j:min(j + L, N)] = Ej; first[j] = True
        cost[j] += float(spreads.cost(T, Kj, m.close[a]))
        if j + L <= N:
            b = int(g[j + L]); cost[j + L - 1] += float(spreads.cost(Ej - m.cal[b], Kj, m.close[b]))
    i0, i1 = g[:N], g[1:N + 1]
    s0 = iv_fn(i0, E - m.cal[i0]); s1 = iv_fn(i1, E - m.cal[i1])
    if tilt is not None:
        s0 = tilt.sig(s0, i0, K, m.close[i0], E - m.cal[i0]); s1 = tilt.sig(s1, i1, K, m.close[i1], E - m.cal[i1])
    return {"K": K, "E": E, "v0": px(m, i0, E, K, kind, s0), "v1": px(m, i1, E, K, kind, s1), "cost": cost, "first": first}


def monthly_leg(m: Market, g: np.ndarray, kind: str, delta: float, iv_fn: Callable, spreads: Spreads, tilt: Optional[Tilt] = None) -> dict:
    """A 30-DTE option opened at each grid point at ``delta`` and settled at intrinsic at the next (open + close fills)."""
    i0, i1 = g[:-1], g[1:]; E = m.cal[i1]; T = E - m.cal[i0]
    s = iv_fn(i0, T); K = k_delta(m, i0, E, s, delta, kind)
    sp = tilt.sig(s, i0, K, m.close[i0], T) if tilt is not None else s
    return {"K": K, "prem": px(m, i0, E, K, kind, sp), "pay": intrinsic(m.close[i1], K, kind),
            "cost": spreads.cost(T, K, m.close[i0]) + spreads.cost(0.0, K, m.close[i1]), "T": T}


def bill_growth(m: Market, g: np.ndarray) -> np.ndarray:
    """Bill return over each cycle at the rate known at its start."""
    i0, i1 = g[:-1], g[1:]
    return np.exp(m.rate[i0] * (m.cal[i1] - m.cal[i0]) / 365.0) - 1.0


# ------------------------------------------------------------------------------- T-145 diagonal vs vertical --

def diagonal_vs_vertical(m: Market, term: Term, g: np.ndarray, spreads: Spreads, tilt: Optional[Tilt] = None) -> dict:
    """0.70-delta 90-DTE long call replaced at 30 DTE (every 2 cycles) + monthly 0.30-delta 30-DTE short call, vs the 30-DTE
    vertical on the same strikes (long K1 = the diagonal's current long strike, short K2) rolled monthly. Excess P&L per
    unit of spot: P&L - debit x bill return, / S."""
    iv_term = lambda i, T: term_iv(term, i, T)
    lg = long_schedule(m, g, 2, 30.0, "call", 0.70, iv_term, spreads, tilt)
    sh = monthly_leg(m, g, "call", 0.30, lambda i, T: term.v30[np.asarray(i, int)], spreads, tilt)
    i0, i1 = g[:-1], g[1:]; S0 = m.close[i0]; E = m.cal[i1]; T = E - m.cal[i0]; bill = bill_growth(m, g)
    pnl_d = (lg["v1"] - lg["v0"]) + (sh["prem"] - sh["pay"]) - lg["cost"] - sh["cost"]
    debit_d = lg["v0"] - sh["prem"]
    sv = term.v30[i0] if tilt is None else tilt.sig(term.v30[i0], i0, lg["K"], S0, T)
    c1 = px(m, i0, E, lg["K"], "call", sv); c2 = sh["prem"]
    pnl_v = (intrinsic(m.close[i1], lg["K"], "call") - sh["pay"]) - (c1 - c2) - (spreads.cost(T, lg["K"], S0) + spreads.cost(0.0, lg["K"], m.close[i1])) - sh["cost"]
    debit_v = c1 - c2
    xd = (pnl_d - debit_d * bill) / S0; xv = (pnl_v - debit_v * bill) / S0
    tasty = (debit_d < (sh["K"] - lg["K"]))[lg["first"]]
    return {"xd": xd, "xv": xv, "K1": lg["K"], "K2": sh["K"], "debit_d": debit_d, "debit_v": debit_v, "n_inverted": int((sh["K"] <= lg["K"]).sum()),
            "tasty_share": _mean(tasty.astype(float)), "n_long_entries": int(lg["first"].sum())}


def judge_sharpe_halves(a, b, ppy: float, side: str, min_n: int, unit: str, n_boot: int = N_BOOT, block: int = BLOCK_M,
                        extra: Sequence = ()) -> dict:
    """Sharpe(a) - Sharpe(b) per walk-forward half (paired block bootstrap, 95% CI). side 'gt': lower > 0 in both halves;
    'not_above': the CI includes 0 or lies below it (lower <= 0) in both halves. ``extra``: (name, ok, decisive) criteria."""
    a = np.asarray(a, float); b = np.asarray(b, float); n = a.size
    full = sharpe_diff_ci(a, b, ppy, block, n_boot)
    c = Criteria(); hv = []
    for nm, ii in zip(("first half", "second half"), _halves_idx(n)):
        r = sharpe_diff_ci(a[ii], b[ii], ppy, block, n_boot); hv.append(r)
        ok, dec = _ok(r[1], r[2], side)
        c.add(f"{nm}: Sharpe difference " + ("95% CI lower > 0" if side == "gt" else "95% CI includes 0 or lies below it"), ok, dec)
    for nm, ok, dec in extra:
        c.add(nm, ok, dec)
    v, why = c.finish(n, min_n, unit)
    return {"verdict": v, "why": why, "n": n, "full": full, "halves": hv, "sharpe_a": float(_sr_rows(a[None, :], ppy)[0]) if n > 1 else None,
            "sharpe_b": float(_sr_rows(b[None, :], ppy)[0]) if n > 1 else None, "min_n": min_n}


def _sd_txt(r) -> str:
    return f"{_f(r[0])} ({_ci_txt(r[1], r[2], _f)})"


def eval_diagonal(m: Market, term: Term, spreads: Spreads, start: str, tilt: Optional[Tilt] = None, min_n: int = 150,
                  n_boot: int = N_BOOT, headline_only: bool = False) -> dict:
    g = grid(m, term, start, MONTH); ppy = YEAR / MONTH
    res = diagonal_vs_vertical(m, term, g, spreads); xd, xv = res["xd"], res["xv"]
    head = float(_sr_rows(xd[None, :], ppy)[0] - _sr_rows(xv[None, :], ppy)[0]) if xd.size > 1 else float("nan")
    if headline_only:
        return {"headline": head, "n": int(xd.size), "window": _window_note(term, m, g[:-1])}
    pbo = pbo_cscv(np.column_stack([xd, xv]), 8) if xd.size >= 16 else {"pbo": float("nan")}
    j = judge_sharpe_halves(xd, xv, ppy, "gt", min_n, "months", n_boot,
                            extra=[("PBO < 0.5 (CSCV, 8 partitions, diagonal vs vertical)", (pbo["pbo"] < 0.5) if np.isfinite(pbo["pbo"]) else None, False)])
    p_swap = swap_perm_p(xd, xv, ppy, n_boot)
    sr_d, sr_v = sharpe_ratio(xd), sharpe_ratio(xv)
    dsr = deflated_sharpe_ratio(xd, 2, trial_sharpes=[sr_d, sr_v]) if xd.size > 2 else float("nan")
    tl = None
    if tilt is not None:
        rt = diagonal_vs_vertical(m, term, g, spreads, tilt)
        tl = sharpe_diff_ci(rt["xd"], rt["xv"], ppy, BLOCK_M, n_boot)
    reason = (f"{MODEL} SPY diagonal: 0.70-delta call bought at 90 DTE (VIX/VIX3M interpolated IV, VIX6M past 93 days) and "
              f"sold at 30 DTE, plus a 0.30-delta 30-DTE short call (VIX) rolled monthly, vs the 30-DTE vertical on the same "
              f"strikes (both at VIX) rolled monthly; marked to model at each monthly roll (the statistic is monthly P&L); monthly "
              f"excess P&L per unit of spot (P&L minus the debit's bill return); "
              f"costs {spreads.describe()} on every open and close; {j['n']} months {_window_note(term, m, g[:-1])}. "
              f"Annualised Sharpe diagonal {_f(j['sharpe_a'])} vs vertical {_f(j['sharpe_b'])}: difference {_sd_txt(j['full'])}; "
              f"halves {_sd_txt(j['halves'][0])} / {_sd_txt(j['halves'][1])}; paired-swap permutation p (trial null, report only) "
              f"{_pv(p_swap)}; PBO {_pv(pbo['pbo'])}; deflated Sharpe of the diagonal "
              f"(2 trials) {_pv(dsr)}; SKEW-tilt rerun (report only): "
              + (f"difference {_sd_txt(tl)}" if tl else "not available (no spy-smile/SKEW)")
              + f"; tastylive setup (net debit < strike width) met on {res['tasty_share'] * 100:.0f}% of {res['n_long_entries']} long entries; "
              f"{res['n_inverted']} months with the short strike at or below the long strike")
    out = dict(j); out.update({"pbo": pbo.get("pbo"), "dsr": dsr, "p_swap": p_swap, "skew_tilt": tl, "tasty_share": res["tasty_share"], "n_inverted": res["n_inverted"],
                               "model_priced": True, "reason_core": reason, "headline": head, "window": _window_note(term, m, g[:-1])})
    return out


# ---------------------------------------------------------------------------------- T-146 double calendar --

def double_vs_single(m: Market, term: Term, a, spreads: Spreads, tilt: Optional[Tilt] = None) -> dict:
    a = np.asarray(a, int); S = m.close[a]
    s = two_expiry(m, term, a, [("call", "short", 1, S, "front"), ("call", "long", 1, S, "back")], spreads, tilt=tilt)
    d = two_expiry(m, term, a, [("put", "short", 1, 0.95 * S, "front"), ("put", "long", 1, 0.95 * S, "back"),
                                ("call", "short", 1, 1.05 * S, "front"), ("call", "long", 1, 1.05 * S, "back")], spreads, tilt=tilt)
    return {"xs": s["pnl"] / s["debit"], "xd": d["pnl"] / d["debit"], "ms": s["pnl"] / (s["debit"] + s["cost"]),
            "md": d["pnl"] / (d["debit"] + d["cost"]), "debit_s": s["debit"] / S, "debit_d": d["debit"] / S}


def _std_ratio_rows(xd, xs):
    return lambda idx: xd[idx].std(axis=1, ddof=1) / np.maximum(xs[idx].std(axis=1, ddof=1), 1e-300)


def judge_std_ratio(xd, xs, min_n: int = 150, n_boot: int = N_BOOT, block: int = BLOCK_M, thr: float = 0.9) -> dict:
    """T-146 on non-overlapping monthly entries: per half, std(xd)/std(xs) < thr and the paired-bootstrap 95% CI < 1."""
    xd = np.asarray(xd, float); xs = np.asarray(xs, float); n = xd.size
    def ratio_ci(ii):
        if ii.size < 4:
            return float("nan"), float("nan"), float("nan")
        r0 = float(xd[ii].std(ddof=1) / xs[ii].std(ddof=1)) if xs[ii].std(ddof=1) > 0 else float("nan")
        dist = boot_dist(ii.size, _std_ratio_rows(xd[ii], xs[ii]), block, n_boot)
        return r0, _q(dist, 0.025), _q(dist, 0.975)
    full = ratio_ci(np.arange(n)); c = Criteria(); hv = []
    for nm, ii in zip(("first half", "second half"), _halves_idx(n)):
        r = ratio_ci(ii); hv.append(r)
        c.add(f"{nm}: std ratio < {thr}", (r[0] < thr) if np.isfinite(r[0]) else None, bool(np.isfinite(r[1]) and r[1] > thr))
        ok, dec = _ok(r[1], r[2], "lt", 1.0)
        c.add(f"{nm}: 95% CI of the ratio excludes 1 (upper < 1)", ok, dec)
    v, why = c.finish(n, min_n, "non-overlapping monthly entries")
    return {"verdict": v, "why": why, "n": n, "full": full, "halves": hv, "min_n": min_n}


def eval_double_calendar(m: Market, term: Term, spreads: Spreads, start: str, tilt: Optional[Tilt] = None, min_n: int = 150,
                         n_boot: int = N_BOOT, headline_only: bool = False) -> dict:
    a = daily_entries(m, term, start); mo = a[::MONTH]
    res = double_vs_single(m, term, mo, spreads)
    head = float(res["xd"].std(ddof=1) / res["xs"].std(ddof=1)) if mo.size > 2 else float("nan")
    if headline_only:
        return {"headline": head, "n": int(mo.size), "window": _window_note(term, m, mo)}
    j = judge_std_ratio(res["xd"], res["xs"], min_n, n_boot)
    daily = double_vs_single(m, term, a, spreads)
    r_daily = float(daily["xd"].std(ddof=1) / daily["xs"].std(ddof=1)) if a.size > 2 else float("nan")
    r_ml = float(res["md"].std(ddof=1) / res["ms"].std(ddof=1)) if mo.size > 2 else float("nan")
    tl = None
    if tilt is not None:
        rt = double_vs_single(m, term, mo, spreads, tilt); tl = float(rt["xd"].std(ddof=1) / rt["xs"].std(ddof=1))
    f3 = lambda r: f"{_f(r[0], 3)} ({_ci_txt(r[1], r[2], lambda v: _f(v, 3))})"
    reason = (f"{MODEL} SPY +/-5% double calendar (0.95 S put calendar + 1.05 S call calendar, 30/60 DTE, flat IV per expiry) vs "
              f"the ATM call calendar, entered on the same days, held to the front expiry (back legs re-priced at that day's VIX "
              f"for 30 days); P&L / debit after {spreads.describe()} on 8 vs 4 fills (open and close at T1; no commission amount is stated, so none beyond the half-spread); {j['n']} "
              f"non-overlapping monthly entries {_window_note(term, m, mo)}; mean debit {_p(_mean(res['debit_d']))} vs "
              f"{_p(_mean(res['debit_s']))} of spot. Std ratio (double / single) {f3(j['full'])}; halves {f3(j['halves'][0])} / "
              f"{f3(j['halves'][1])} (paired block-6 percentile bootstrap); all daily entries (report only) {_f(r_daily, 3)}; per "
              f"unit of max loss (debit + costs: a long calendar is never worth less than 0 at T1) {_f(r_ml, 3)}; SKEW-tilt rerun "
              f"(report only) " + (_f(tl, 3) if tl is not None else "not available"))
    out = dict(j); out.update({"ratio_daily": r_daily, "ratio_per_max_loss": r_ml, "skew_tilt_ratio": tl, "model_priced": True,
                               "reason_core": reason, "headline": head, "window": _window_note(term, m, mo)})
    return out


# ---------------------------------------------------------------------------------- T-147 double diagonal --

def double_diagonal_vs_condor(m: Market, term: Term, a, spreads: Spreads, tilt: Optional[Tilt] = None, grid_n: int = 401) -> dict:
    """Double diagonal: short 0.16-delta 30-DTE strangle (VIX), long 0.10-delta 60-DTE wings (VIX/VIX3M), valued at T1 with
    the wings re-priced at T1's VIX for 30 days; max loss = debit + costs - min over S of the T1 value (wings at T1's IV).
    Iron condor: the same four strikes, all 30 DTE at VIX, held to expiry; max loss = wider wing - credit + costs."""
    a = np.asarray(a, int); b = a + MONTH; E1 = m.cal[b]; E2 = E1 + GAP
    vf = term.v30[a]; vb = term_iv(term, a, E2 - m.cal[a])
    K2 = k_delta(m, a, E1, vf, -0.16, "put"); K3 = k_delta(m, a, E1, vf, 0.16, "call")
    K1 = k_delta(m, a, E2, vb, -0.10, "put"); K4 = k_delta(m, a, E2, vb, 0.10, "call")
    dd = two_expiry(m, term, a, [("put", "long", 1, K1, "back"), ("put", "short", 1, K2, "front"), ("call", "short", 1, K3, "front"),
                                 ("call", "long", 1, K4, "back")], spreads, tilt=tilt)
    ic = two_expiry(m, term, a, [("put", "long", 1, K1, "front"), ("put", "short", 1, K2, "front"), ("call", "short", 1, K3, "front"),
                                 ("call", "long", 1, K4, "front")], spreads, tilt=tilt, close_front=False)
    ml_dd = np.empty(a.size)
    pvd = m.pv_div(b, E2); T = GAP / 365.0
    for k in range(a.size):
        Sg = m.close[a[k]] * np.linspace(0.5, 1.5, grid_n); F = Sg - pvd[k]; bb = np.full(grid_n, int(b[k]))
        s1 = np.full(grid_n, float(dd["vb1"][k]))
        sp = tilt.sig(s1, bb, K1[k], Sg, np.full(grid_n, float(GAP))) if tilt is not None else s1
        sc = tilt.sig(s1, bb, K4[k], Sg, np.full(grid_n, float(GAP))) if tilt is not None else s1
        wings = np.asarray(bs.price(F, K1[k], T, m.rate[b[k]], sp, "put"), float) + np.asarray(bs.price(F, K4[k], T, m.rate[b[k]], sc, "call"), float)
        val = wings - intrinsic(Sg, K2[k], "put") - intrinsic(Sg, K3[k], "call")
        ml_dd[k] = dd["debit"][k] + dd["cost"][k] - float(val.min())
    ml_ic = np.maximum(K2 - K1, K4 - K3) + ic["debit"] + ic["cost"]
    S = m.close[a]
    ml_dd = np.maximum(ml_dd, 1e-6 * S); ml_ic = np.maximum(ml_ic, 1e-6 * S)
    return {"x_dd": dd["pnl"] / ml_dd, "x_ic": ic["pnl"] / ml_ic, "ml_dd": ml_dd / S, "ml_ic": ml_ic / S, "debit_dd": dd["debit"] / S,
            "credit_ic": -ic["debit"] / S, "K": np.column_stack([K1, K2, K3, K4]) / S[:, None]}


def judge_paired_halves(d_sets: dict, min_n: int, unit: str, n_boot: int = N_BOOT, block: int = BLOCK_M) -> dict:
    """Per named difference series: mean > 0 with the paired block-bootstrap 95% CI excluding 0 in both halves. A series
    given as None is a criterion that cannot be implemented (its two half criteria are None)."""
    c = Criteria(); rows = {}; n = None
    for name, d in d_sets.items():
        if d is None:
            for hn in ("first half", "second half"):
                c.add(f"{name}, {hn}: difference > 0 with the 95% CI excluding 0", None)
            continue
        d = np.asarray(d, float); n = d.size if n is None else n
        full = (_mean(d),) + boot_mean_ci(d, block, n_boot); hv = []
        for hn, ii in zip(("first half", "second half"), _halves_idx(d.size)):
            r = (_mean(d[ii]),) + boot_mean_ci(d[ii], block, n_boot); hv.append(r)
            ok, dec = _ok(r[1], r[2], "gt")
            c.add(f"{name}, {hn}: difference > 0 with the 95% CI excluding 0", ok, dec)
        rows[name] = {"full": full, "halves": hv}
    v, why = c.finish(int(n or 0), min_n, unit)
    return {"verdict": v, "why": why, "n": int(n or 0), "rows": rows, "min_n": min_n}


def eval_double_diagonal(m: Market, term: Term, spreads: Spreads, start: str, tilt: Optional[Tilt] = None, min_n: int = 80,
                         n_boot: int = N_BOOT, headline_only: bool = False) -> dict:
    g = grid(m, term, start, MONTH); g = g[g + MONTH < len(m.days)]
    med = np.array([np.median(term.v30[max(0, i - YEAR):i]) if i >= YEAR else np.nan for i in g])
    low = term.v30[g] < med; a = g[low]
    res = double_diagonal_vs_condor(m, term, a, spreads); d = res["x_dd"] - res["x_ic"]
    if headline_only:
        return {"headline": _mean(d), "n": int(a.size), "window": _window_note(term, m, a)}
    sets = {"flat IV": d, "SKEW tilt" + ("" if tilt is not None else " (no spy-smile / SKEW data)"): None}
    if tilt is not None:
        rt = double_diagonal_vs_condor(m, term, a, spreads, tilt); sets["SKEW tilt"] = rt["x_dd"] - rt["x_ic"]
    j = judge_paired_halves(sets, min_n, "low-VIX monthly entries", n_boot)
    rng = np.random.default_rng(0)
    perm = np.array([_mean(d * rng.choice([-1.0, 1.0], d.size)) for _ in range(n_boot)]) if d.size else np.array([])
    p_perm = float((np.sum(perm >= _mean(d)) + 1) / (perm.size + 1)) if perm.size else float("nan")
    fx = lambda r: f"{_p(r[0])} ({_ci_txt(r[1], r[2])})"
    reason = (f"{MODEL} SPY double diagonal (short 0.16-delta 30-DTE strangle at VIX, long 0.10-delta 60-DTE wings at the "
              f"VIX/VIX3M interpolation, closed at the front expiry with the wings re-priced at that day's VIX) vs the 30-DTE iron "
              f"condor on the same strikes (VIX, held to expiry); entries on the monthly grid {_window_note(term, m, a)} when VIX < "
              f"its trailing 252-session median ({j['n']} of {g.size} months); costs {spreads.describe()} on 8 vs 4 fills; max loss "
              f"of the diagonal = debit + costs - the lowest T1 value over spot (wings at T1's realised IV), of the condor = wider "
              f"wing - credit + costs. Mean P&L / max loss {_p(_mean(res['x_dd']))} vs {_p(_mean(res['x_ic']))}; difference "
              + "; ".join(f"[{k}] full {fx(r['full'])}, halves {fx(r['halves'][0])} / {fx(r['halves'][1])}" for k, r in j["rows"].items())
              + f"; sign-flip permutation p (report only) {_pv(p_perm)}; median strikes (K/S) "
              + "/".join(f"{v:.3f}" for v in (np.median(res["K"], axis=0) if a.size else [np.nan] * 4)))
    out = dict(j); out.update({"n_months_total": int(g.size), "mean_dd": _mean(res["x_dd"]), "mean_ic": _mean(res["x_ic"]), "p_perm": p_perm,
                               "model_priced": True, "reason_core": reason, "headline": _mean(d), "window": _window_note(term, m, a)})
    return out


# ------------------------------------------------------------------------------------ T-149 ratio calendar --

def ratio_calendar(m: Market, term: Term, a, spreads: Spreads, hold: int = WEEK) -> dict:
    """Long 1 x 90-DTE ATM call (VIX/VIX3M interpolation), short n x 30-DTE ATM call (VIX) with n = back vega / front vega at
    entry; revalued after ``hold`` sessions with that day's interpolated IVs. P&L per unit of entry spot; costs on 1 + n
    contract fills (the claim's 2.7) per week. Also the 1:1 calendar and the delta-hedged ratio P&L."""
    a = np.asarray(a, int); c = a + hold; S0 = m.close[a]; K = S0
    E1 = m.cal[a] + 30.0; E2 = m.cal[a] + 90.0
    s1a = term.v30[a]; s2a = term_iv(term, a, np.full(a.size, 90.0))
    s1c = term_iv(term, c, E1 - m.cal[c]); s2c = term_iv(term, c, E2 - m.cal[c])
    g1 = greeks_at(m, a, E1, K, "call", s1a); g2 = greeks_at(m, a, E2, K, "call", s2a)
    n = np.asarray(g2["vega"], float) / np.asarray(g1["vega"], float)
    f0, f1 = px(m, a, E1, K, "call", s1a), px(m, c, E1, K, "call", s1c)
    b0, b1 = px(m, a, E2, K, "call", s2a), px(m, c, E2, K, "call", s2c)
    hs_f = spreads.cost(30.0, K, S0); hs_b = spreads.cost(90.0, K, S0)
    pnl_r = (b1 - b0) - n * (f1 - f0) - (hs_b + n * hs_f)
    pnl_1 = (b1 - b0) - (f1 - f0) - (hs_b + hs_f)
    delta = np.asarray(g2["delta"], float) - n * np.asarray(g1["delta"], float)
    dS = m.close[c] - S0 + np.array([m.div[i + 1:j + 1].sum() for i, j in zip(a, c)])
    return {"x": pnl_r / S0, "x1": pnl_1 / S0, "xh": (pnl_r - delta * dS) / S0, "dvix": (term.v30[c] - term.v30[a]) * 100, "n_ratio": n}


def judge_spearman(x, dv, min_n: int = 300, n_boot: int = N_BOOT, block: int = BLOCK_W, thr: float = 0.3) -> dict:
    """T-149: per half, the upper bound of the 95% CI of |rho| (max(|lo|, |hi|) of the rho CI) < thr."""
    x = np.asarray(x, float); dv = np.asarray(dv, float); n = x.size
    full = spearman_ci(x, dv, block, n_boot); c = Criteria(); hv = []
    for nm, ii in zip(("first half", "second half"), _halves_idx(n)):
        r = spearman_ci(x[ii], dv[ii], block, n_boot); hv.append(r)
        if np.isfinite(r[1]) and np.isfinite(r[2]):
            up = max(abs(r[1]), abs(r[2])); lo_abs = 0.0 if r[1] <= 0 <= r[2] else min(abs(r[1]), abs(r[2]))
            c.add(f"{nm}: upper bound of the 95% CI of |rho| < {thr}", up < thr, lo_abs >= thr)
        else:
            c.add(f"{nm}: upper bound of the 95% CI of |rho| < {thr}", None)
    v, why = c.finish(n, min_n, "weeks")
    return {"verdict": v, "why": why, "n": n, "full": full, "halves": hv, "min_n": min_n}


def eval_ratio_calendar(m: Market, term: Term, spreads: Spreads, start: str, min_n: int = 300, n_boot: int = N_BOOT,
                        headline_only: bool = False) -> dict:
    g = grid(m, term, start, WEEK); g = g[g + WEEK < len(m.days)]
    res = ratio_calendar(m, term, g, spreads)
    if headline_only:
        return {"headline": spearman(res["x"], res["dvix"]), "n": int(g.size), "window": _window_note(term, m, g)}
    j = judge_spearman(res["x"], res["dvix"], min_n, n_boot)
    r1 = spearman_ci(res["x1"], res["dvix"], BLOCK_W, n_boot); rh = spearman_ci(res["xh"], res["dvix"], BLOCK_W, n_boot)
    top = res["dvix"] >= np.quantile(res["dvix"], 0.9) if g.size else np.zeros(0, bool)
    r_ex = spearman(res["x"][~top], res["dvix"][~top]) if g.size else float("nan")
    abs_up = lambda r: max(abs(r[1]), abs(r[2])) if np.isfinite(r[1]) and np.isfinite(r[2]) else float("nan")
    fr = lambda r: f"{_f(r[0], 3)} ({_ci_txt(r[1], r[2], lambda v: _f(v, 3))}, |rho| upper {abs(abs_up(r)):.3f})"
    reason = (f"{MODEL} SPY 30/90-DTE ATM ratio call calendar re-sized vega-neutral each week (short n x 30-DTE at VIX per long "
              f"90-DTE at the VIX/VIX3M interpolation; median n {float(np.median(res['n_ratio'])) if g.size else float('nan'):.2f}), held "
              f"5 sessions and re-priced with that day's interpolated IVs; weekly P&L per unit of spot after {spreads.describe()} on "
              f"1 + n contract fills; {j['n']} weeks {_window_note(term, m, g)}. Spearman(P&L, delta-VIX) {fr(j['full'])}; halves "
              f"{fr(j['halves'][0])} / {fr(j['halves'][1])} (block-4-week percentile bootstrap); 1:1 calendar {fr(r1)}; delta-hedged "
              f"ratio P&L {fr(rh)}; without the top-decile VIX-spike weeks {_f(r_ex, 3)}")
    out = dict(j); out.update({"one_to_one": r1, "delta_hedged": rh, "ex_top_decile": r_ex, "median_n_ratio": float(np.median(res["n_ratio"])) if g.size else None,
                               "model_priced": True, "reason_core": reason, "headline": j["full"][0], "window": _window_note(term, m, g)})
    return out


# ---------------------------------------------------------------------------------- T-150 PMCC vs covered call --

def pmcc_vs_cc(m: Market, term: Term, g: np.ndarray, spreads: Spreads, leaps_shift: float = 0.0, leaps_scale: float = 1.0) -> dict:
    """PMCC: 0.80-delta 12-month LEAPS call at VIX3M (x scale + shift) replaced at 90 DTE (every 9 cycles) + monthly 0.30-delta
    30-DTE short call at VIX. Covered call: SPY (total return) + the same short call. Monthly excess return on capital
    deployed (PMCC: LEAPS value - short premium; CC: S - premium) over the bill."""
    iv_l = lambda i, T: np.maximum(term.v93[np.asarray(i, int)] * leaps_scale + leaps_shift, 0.01)
    lg = long_schedule(m, g, 9, 90.0, "call", 0.80, iv_l, spreads)
    sh = monthly_leg(m, g, "call", 0.30, lambda i, T: term.v30[np.asarray(i, int)], spreads)
    i0, i1 = g[:-1], g[1:]; S0 = m.close[i0]; bill = bill_growth(m, g)
    pnl_p = (lg["v1"] - lg["v0"]) + (sh["prem"] - sh["pay"]) - lg["cost"] - sh["cost"]
    cap_p = lg["v0"] - sh["prem"]
    pnl_c = S0 * (m.adj[i1] / m.adj[i0] - 1.0) + (sh["prem"] - sh["pay"]) - sh["cost"]
    cap_c = S0 - sh["prem"]
    rp, rc = pnl_p / cap_p, pnl_c / cap_c
    return {"xp": rp - bill, "xc": rc - bill, "rp": rp, "rc": rc, "cap_p": cap_p / S0, "K_leaps": lg["K"] / S0}


def eval_pmcc(m: Market, term: Term, spreads: Spreads, start: str, chain_ratio: Optional[float] = None, chain_note: str = "",
              min_n: int = 150, n_boot: int = N_BOOT, headline_only: bool = False) -> dict:
    g = grid(m, term, start, MONTH); ppy = YEAR / MONTH
    res = pmcc_vs_cc(m, term, g, spreads)
    head = float(_sr_rows(res["xp"][None, :], ppy)[0] - _sr_rows(res["xc"][None, :], ppy)[0]) if res["xp"].size > 1 else float("nan")
    if headline_only:
        return {"headline": head, "n": int(res["xp"].size), "window": _window_note(term, m, g[:-1])}
    j = judge_sharpe_halves(res["xp"], res["xc"], ppy, "not_above", min_n, "months", n_boot)
    sens = {}
    for nm, kw in (("VIX3M - 3 vol pts", {"leaps_shift": -0.03}), ("VIX3M + 3 vol pts", {"leaps_shift": 0.03})) + (
            ((f"chain 12-month ATM IV / VIX3M = {chain_ratio:.3f}", {"leaps_scale": chain_ratio}),) if chain_ratio else ()):
        r = pmcc_vs_cc(m, term, g, spreads, **kw); sens[nm] = sharpe_diff_ci(r["xp"], r["xc"], ppy, BLOCK_M, n_boot)
    ann = lambda r: float(np.prod(1 + r) ** (ppy / r.size) - 1) if r.size else float("nan")
    reason = (f"{MODEL} SPY poor man's covered call (0.80-delta 12-month LEAPS call at VIX3M IV, replaced at 90 DTE; monthly "
              f"0.30-delta 30-DTE short call at VIX; no dividends) vs the covered call (SPY total return + the same short call), "
              f"marked to model at each monthly roll; "
              f"monthly returns on capital deployed (PMCC: LEAPS value - short premium, median {_p(float(np.median(res['cap_p'])) if res['cap_p'].size else float('nan'), 1)} "
              f"of spot; CC: spot - premium) in excess of the bill; costs {spreads.describe()} on the monthly short-call fills and "
              f"the LEAPS rolls; {j['n']} months {_window_note(term, m, g[:-1])}. Annualised Sharpe PMCC {_f(j['sharpe_a'])} vs CC "
              f"{_f(j['sharpe_b'])}: difference {_sd_txt(j['full'])}; halves {_sd_txt(j['halves'][0])} / {_sd_txt(j['halves'][1])} "
              f"(the claim survives a half unless its CI lies entirely above 0); return on capital {_p(ann(res['rp']), 1)} vs "
              f"{_p(ann(res['rc']), 1)} a year, max drawdown {_p(_mdd(res['rp']), 1)} vs {_p(_mdd(res['rc']), 1)}; LEAPS-IV "
              f"sensitivity (report only): " + "; ".join(f"{k}: {_sd_txt(v)}" for k, v in sens.items()) + (chain_note or ""))
    out = dict(j); out.update({"sensitivity": sens, "ann_return": [ann(res["rp"]), ann(res["rc"])], "mdd": [_mdd(res["rp"]), _mdd(res["rc"])],
                               "model_priced": True, "reason_core": reason, "headline": head, "window": _window_note(term, m, g[:-1])})
    return out


# ------------------------------------------------------------------------------------ T-151 LEAPS collar --

def leaps_vs_standard_collar(m: Market, term: Term, g: np.ndarray, spreads: Spreads, put_shift: float = 0.0, put_scale: float = 1.0,
                             tilt: Optional[Tilt] = None) -> dict:
    """LEAPS collar: SPY (total return) + 12-month -0.25-delta put at VIX3M (x scale + shift) replaced at 90 DTE + monthly
    0.30-delta 30-DTE short call at VIX. Standard collar: SPY + 30-DTE -0.25-delta put + 0.30-delta call, both at VIX, rolled
    monthly. Monthly excess return on the net outlay (S + put - call premium) over the bill."""
    v30 = lambda i, T: term.v30[np.asarray(i, int)]
    iv_p = lambda i, T: np.maximum(term.v93[np.asarray(i, int)] * put_scale + put_shift, 0.01)
    lp = long_schedule(m, g, 9, 90.0, "put", -0.25, iv_p, spreads, tilt)
    ca = monthly_leg(m, g, "call", 0.30, v30, spreads, tilt)
    sp = monthly_leg(m, g, "put", -0.25, v30, spreads, tilt)
    i0, i1 = g[:-1], g[1:]; S0 = m.close[i0]; bill = bill_growth(m, g); stock = S0 * (m.adj[i1] / m.adj[i0] - 1.0)
    pnl_l = stock + (lp["v1"] - lp["v0"]) + (ca["prem"] - ca["pay"]) - lp["cost"] - ca["cost"]
    cap_l = S0 + lp["v0"] - ca["prem"]
    pnl_s = stock + (sp["pay"] - sp["prem"]) + (ca["prem"] - ca["pay"]) - sp["cost"] - ca["cost"]
    cap_s = S0 + sp["prem"] - ca["prem"]
    rl, rs = pnl_l / cap_l, pnl_s / cap_s
    starts = np.flatnonzero(lp["first"])                       # LEAPS purchases; resales at the cycle before the next one
    resale = float(lp["v1"][starts[1:] - 1].sum() + (lp["v1"][-1] if lp["v1"].size else 0.0))   # + the last put's final mark
    net_put = float(lp["v0"][starts].sum()) - resale
    cov_l = float(ca["prem"].sum() / net_put) if ca["prem"].size and net_put > 0 else float("nan")
    cov_s = float(ca["prem"].sum() / sp["prem"].sum()) if sp["prem"].size and sp["prem"].sum() > 0 else float("nan")
    return {"xl": rl - bill, "xs": rs - bill, "rl": rl, "rs": rs, "coverage": [cov_l, cov_s]}


def eval_leaps_collar(m: Market, term: Term, spreads: Spreads, start: str, tilt: Optional[Tilt] = None, chain_ratio: Optional[float] = None,
                      chain_note: str = "", min_n: int = 150, n_boot: int = N_BOOT, headline_only: bool = False) -> dict:
    g = grid(m, term, start, MONTH); ppy = YEAR / MONTH
    res = leaps_vs_standard_collar(m, term, g, spreads)
    head = float(_sr_rows(res["xl"][None, :], ppy)[0] - _sr_rows(res["xs"][None, :], ppy)[0]) if res["xl"].size > 1 else float("nan")
    if headline_only:
        return {"headline": head, "n": int(res["xl"].size), "window": _window_note(term, m, g[:-1])}
    j = judge_sharpe_halves(res["xl"], res["xs"], ppy, "gt", min_n, "months", n_boot)
    p_swap = swap_perm_p(res["xl"], res["xs"], ppy, n_boot)
    sens = {}
    runs = [("VIX3M - 3 vol pts", {"put_shift": -0.03}), ("VIX3M + 3 vol pts", {"put_shift": 0.03})]
    if chain_ratio:
        runs.append((f"chain 12-month 25-delta put IV / VIX3M = {chain_ratio:.3f}", {"put_scale": chain_ratio}))
    if tilt is not None:
        runs.append(("SKEW tilt (45-day smile shape)", {"tilt": tilt}))
    for nm, kw in runs:
        r = leaps_vs_standard_collar(m, term, g, spreads, **kw); sens[nm] = sharpe_diff_ci(r["xl"], r["xs"], ppy, BLOCK_M, n_boot)
    reason = (f"{MODEL} SPY LEAPS collar (SPY + 12-month -0.25-delta put at VIX3M IV replaced at 90 DTE + monthly 0.30-delta "
              f"30-DTE short call at VIX) vs the standard collar (SPY + 30-DTE -0.25-delta put and 0.30-delta call, both at VIX, "
              f"rolled monthly), marked to model at each monthly roll; dividends credited to SPY in both; monthly excess return on "
              f"the net outlay; costs "
              f"{spreads.describe()} on every option fill; {j['n']} months {_window_note(term, m, g[:-1])}. Annualised Sharpe "
              f"LEAPS collar {_f(j['sharpe_a'])} vs standard {_f(j['sharpe_b'])}: difference {_sd_txt(j['full'])}; halves "
              f"{_sd_txt(j['halves'][0])} / {_sd_txt(j['halves'][1])}; paired-swap permutation p (trial null, report only) "
              f"{_pv(p_swap)}; max drawdown {_p(_mdd(res['rl']), 1)} vs {_p(_mdd(res['rs']), 1)}; "
              f"credit coverage (call premium / net put cost) {res['coverage'][0]:.2f} vs {res['coverage'][1]:.2f}; sensitivities "
              f"(report only): " + "; ".join(f"{k}: {_sd_txt(v)}" for k, v in sens.items()) + (chain_note or ""))
    out = dict(j); out.update({"sensitivity": sens, "mdd": [_mdd(res["rl"]), _mdd(res["rs"])], "coverage": res["coverage"], "p_swap": p_swap,
                               "model_priced": True, "reason_core": reason, "headline": head, "window": _window_note(term, m, g[:-1])})
    return out


# ------------------------------------------------------------------------------ T-152 calendarised butterfly --

T152_START = "2007-12-04"      # the claim's "since 2007-12": the first VIX3M (VXV) close, the trial's anchor

def time_vs_plain_fly(m: Market, term: Term, a, spreads: Spreads, w: float = 0.03) -> dict:
    """Calendarised fly: long 60-DTE calls at (1 -/+ w) S (VIX/VIX3M), short 2 x 30-DTE ATM (VIX); plain fly: all three strikes
    at 30 DTE (VIX). Both valued at the front expiry; P&L / debit after half-spread costs on 6 vs 4 contracts (the time fly's
    wings are closed at T1; expiring legs settle without a fill)."""
    a = np.asarray(a, int); S = m.close[a]
    tf = two_expiry(m, term, a, [("call", "long", 1, (1 - w) * S, "back"), ("call", "short", 2, S, "front"), ("call", "long", 1, (1 + w) * S, "back")],
                    spreads, close_front=False)
    pf = two_expiry(m, term, a, [("call", "long", 1, (1 - w) * S, "front"), ("call", "short", 2, S, "front"), ("call", "long", 1, (1 + w) * S, "front")],
                    spreads, close_front=False)
    return {"xt": tf["pnl"] / tf["debit"], "xp": pf["pnl"] / pf["debit"], "dvix": (term.v30[a + MONTH] - term.v30[a]) * 100,
            "debit_t": tf["debit"] / S, "debit_p": pf["debit"] / S}


def judge_spike_decile(xt, xp, dvix, min_n: int = 15, n_boot: int = N_BOOT, extra: Sequence = ()) -> dict:
    """Top-decile delta-VIX holding periods: mean paired (time - plain) P&L/debit > 0 with the paired bootstrap 95% CI
    excluding 0 (percentile; spike months are not contiguous, so resampled individually). ``extra``: (name, ok, decisive)."""
    xt = np.asarray(xt, float); xp = np.asarray(xp, float); dv = np.asarray(dvix, float)
    top = dv >= np.quantile(dv, 0.9) if dv.size else np.zeros(0, bool)
    d = (xt - xp)[top]; lo, hi = boot_mean_ci(d, 1, n_boot)
    c = Criteria(); ok, dec = _ok(lo, hi, "gt")
    c.add("spike decile: difference > 0 with the 95% CI excluding 0", ok, dec)
    for nm, okx, decx in extra:
        c.add(nm, okx, decx)
    v, why = c.finish(int(d.size), min_n, "spike-decile months")
    return {"verdict": v, "why": why, "n": int(d.size), "diff": _mean(d), "ci": [lo, hi], "top": top, "min_n": min_n}


def eval_time_fly(m: Market, term: Term, spreads: Spreads, start: str, min_n: int = 15, n_boot: int = N_BOOT, headline_only: bool = False,
                  window_gap: Optional[str] = None) -> dict:
    """``window_gap``: set only when the inputs cannot reach the claim's own window (top-decile months since 2007-12) even
    with VIX standing in for VIX3M; it then becomes a criterion that is not implemented."""
    g = grid(m, term, start, MONTH); g = g[g + MONTH < len(m.days)]
    res = time_vs_plain_fly(m, term, g, spreads)
    extra = [(f"the claim's window, top-decile months since 2007-12 ({window_gap})", None, False)] if window_gap else []
    j = judge_spike_decile(res["xt"], res["xp"], res["dvix"], min_n, n_boot, extra)
    if headline_only:
        return {"headline": j["diff"], "n": j["n"], "window": _window_note(term, m, g)}
    top = j.pop("top"); d_all = res["xt"] - res["xp"]
    hv = [_mean(d_all[ii][top[ii]]) if top[ii].any() else float("nan") for ii in _halves_idx(g.size)]
    reason = (f"{MODEL} SPY calendarised butterfly (long 60-DTE calls at 0.97 S and 1.03 S at the VIX/VIX3M interpolation, short "
              f"2 x 30-DTE ATM at VIX; wings re-priced at the front expiry at that day's VIX) vs the 30-DTE butterfly on the same "
              f"strikes (VIX); P&L / debit at the front expiry after {spreads.describe()} on 6 vs 4 contracts; {g.size} monthly "
              f"entries {_window_note(term, m, g)}, top delta-VIX decile over the hold = {j['n']} months (delta-VIX >= "
              f"{_f(float(np.quantile(res['dvix'], 0.9)) if g.size else float('nan'))} pts). Spike-decile mean P&L/debit time fly "
              f"{_p(_mean(res['xt'][top]))} vs plain {_p(_mean(res['xp'][top]))}: paired difference {_p(j['diff'])} "
              f"({_ci_txt(*j['ci'])}, paired percentile bootstrap); walk-forward halves (report only) {_p(hv[0])} / {_p(hv[1])}; "
              f"all months (not the claim) {_p(_mean(d_all))}; mean debit {_p(_mean(res['debit_t']))} vs {_p(_mean(res['debit_p']))} of spot")
    out = dict(j); out.update({"halves": hv, "mean_all": _mean(d_all), "model_priced": True, "reason_core": reason, "headline": j["diff"],
                               "window": _window_note(term, m, g), "first_entry": m.days[int(g[0])] if g.size else None,
                               "spike_days": [m.days[int(i)] for i in g[top]], "proxy_entries": int(term.proxy[g].sum()),
                               "proxy_spike_days": [m.days[int(i)] for i in g[top] if term.proxy[int(i)]]})
    return out


# ------------------------------------------------------------------------------ T-155 roll vs reset --

def roll_vs_reset(m: Market, v30: np.ndarray, a, spreads: Spreads, tilt: Optional[Tilt] = None, dte0: float = 45.0, check: float = 21.0,
                  roll_out: float = 28.0, delta0: float = -0.16, tested: float = -0.30) -> dict:
    """Short a ``delta0`` put at ``dte0`` days (IV = VIX). At the first close with <= ``check`` days left, the put is tested
    if its delta (at that day's VIX) is below ``tested``. Roll: buy it back, sell the same strike at the next monthly
    (``roll_out`` days later) and exit at its 21-DTE close. Reset: buy it back, sell a fresh ``delta0`` put at ``dte0`` days
    and exit at its 21-DTE close. P&L per day held from the decision, per unit of spot at the decision, after half-spread
    costs on 3 fills per path (close the tested put, open, close) and margin-time at the bill rate (Reg-T broad-based:
    premium + max(15% S - OTM, 10% K))."""
    a = np.asarray(a, int); n = len(m.days)
    sig = lambda i, K, T: v30[i] if tilt is None else tilt.sig(v30[i], i, K, m.close[i], T)
    E0 = m.cal[a] + dte0; K = k_delta(m, a, E0, v30[a], delta0, "put")
    c = np.searchsorted(m.cal, E0 - check, "left")
    ok = c < n
    a, E0, K, c = a[ok], E0[ok], K[ok], c[ok]
    Er = E0 + roll_out; er = np.searchsorted(m.cal, Er - check, "left")
    Es = m.cal[c] + dte0; es = np.searchsorted(m.cal, Es - check, "left")
    ok = (er < n) & (es < n) & np.isfinite(v30[c]) & np.isfinite(m.rate[c])
    a, E0, K, c, Er, er, Es, es = (x[ok] for x in (a, E0, K, c, Er, er, Es, es))
    Tc = E0 - m.cal[c]
    dl = np.asarray(greeks_at(m, c, E0, K, "put", sig(c, K, Tc))["delta"], float)
    test = dl < tested
    p_entry = px(m, a, E0, K, "put", sig(a, K, np.full(a.size, dte0)))
    p_close = px(m, c, E0, K, "put", sig(c, K, Tc))
    Sc = m.close[c]; rc = m.rate[c]
    Ks = k_delta(m, c, Es, v30[c], delta0, "put")
    pr0 = px(m, c, Er, K, "put", sig(c, K, Er - m.cal[c])); pr1 = px(m, er, Er, K, "put", sig(er, K, Er - m.cal[er]))
    ps0 = px(m, c, Es, Ks, "put", sig(c, Ks, Es - m.cal[c])); ps1 = px(m, es, Es, Ks, "put", sig(es, Ks, Es - m.cal[es]))
    close_cost = spreads.cost(Tc, K, Sc)
    def path(p0, p1, Kn, E, e):
        days = m.cal[e] - m.cal[c]
        margin = p0 + np.maximum(0.15 * Sc - np.maximum(Sc - Kn, 0.0), 0.10 * Kn)
        cost = close_cost + spreads.cost(E - m.cal[c], Kn, Sc) + spreads.cost(E - m.cal[e], Kn, m.close[e])
        pnl = p0 - p1 - cost - rc * margin * days / 365.0
        return pnl, days
    pnl_r, dr = path(pr0, pr1, K, Er, er); pnl_s, ds = path(ps0, ps1, Ks, Es, es)
    orig = p_entry - p_close
    return {"a": a, "tested": test, "roll": pnl_r / dr / Sc, "reset": pnl_s / ds / Sc, "days_roll": dr, "days_reset": ds,
            "life_roll": (orig + pnl_r) / (m.cal[er] - m.cal[a]) / Sc, "life_reset": (orig + pnl_s) / (m.cal[es] - m.cal[a]) / Sc,
            "delta_check": dl}


def judge_roll(roll, reset, min_n: int = 200, n_boot: int = N_BOOT, block: int = BLOCK_D) -> dict:
    """T-155: the claim survives a half when the paired block-bootstrap 95% CI of mean(roll - reset) includes 0 or lies
    below it."""
    d = np.asarray(roll, float) - np.asarray(reset, float); n = d.size
    full = (_mean(d),) + boot_mean_ci(d, block, n_boot); c = Criteria(); hv = []
    for nm, ii in zip(("first half", "second half"), _halves_idx(n)):
        r = (_mean(d[ii]),) + boot_mean_ci(d[ii], block, n_boot); hv.append(r)
        ok, dec = _ok(r[1], r[2], "not_above")
        c.add(f"{nm}: 95% CI of (roll - reset) P&L/day includes 0 or lies below it", ok, dec)
    v, why = c.finish(n, min_n, "tested entries")
    vr = float(np.var(roll, ddof=1) / np.var(reset, ddof=1)) if n > 2 and np.var(reset) > 0 else float("nan")
    return {"verdict": v, "why": why, "n": n, "full": full, "halves": hv, "var_ratio": vr, "min_n": min_n}


def eval_roll(m: Market, v30: np.ndarray, spreads: Spreads, start: str = "1993-01-29", tilt: Optional[Tilt] = None, min_n: int = 200,
              n_boot: int = N_BOOT, headline_only: bool = False) -> dict:
    i0 = bisect.bisect_left(m.days, start)
    a = np.array([i for i in range(i0, len(m.days)) if np.isfinite(v30[i]) and v30[i] > 0 and np.isfinite(m.rate[i])], int)
    res = roll_vs_reset(m, v30, a, spreads)
    t = res["tested"]
    if headline_only:
        d = res["roll"][t] - res["reset"][t]
        return {"headline": _mean(d), "n": int(t.sum()), "ci": boot_mean_ci(d, BLOCK_D, n_boot)}
    j = judge_roll(res["roll"][t], res["reset"][t], min_n, n_boot)
    life = (_mean(res["life_roll"][t] - res["life_reset"][t]),) + boot_mean_ci(res["life_roll"][t] - res["life_reset"][t], BLOCK_D, n_boot)
    tl = None
    if tilt is not None:
        rt = roll_vs_reset(m, v30, a, spreads, tilt); tt = rt["tested"]
        dd = rt["roll"][tt] - rt["reset"][tt]; tl = (_mean(dd),) + boot_mean_ci(dd, BLOCK_D, n_boot) + (int(tt.sum()),)
    bp = lambda x: "n/a" if x is None or not np.isfinite(x) else f"{x * 1e4:+.3f} bp"
    fr = lambda r: f"{bp(r[0])} (95% CI {bp(r[1])} to {bp(r[2])})"
    ad = res["a"][t]
    reason = (f"{MODEL} SPY 0.16-delta 45-DTE short put (VIX as IV), entered every session "
              f"{m.days[int(res['a'][0])] if res['a'].size else ''} to {m.days[int(res['a'][-1])] if res['a'].size else ''}; tested "
              f"(delta < -0.30 at 21 DTE) on {j['n']} of {res['a'].size} entries "
              f"({m.days[int(ad[0])] if ad.size else ''} to {m.days[int(ad[-1])] if ad.size else ''}); roll = same strike to the "
              f"next monthly (+28 days), reset = fresh 0.16-delta 45-DTE put, both exited at their 21-DTE close; P&L per day held "
              f"from the decision per unit of spot, after {spreads.describe()} on 3 fills per path and margin-time at the bill "
              f"rate. Roll - reset: {fr(j['full'])}; halves {fr(j['halves'][0])} / {fr(j['halves'][1])} (paired block-21 percentile "
              f"bootstrap; the claim survives a half unless its CI lies entirely above 0); mean roll {bp(_mean(res['roll'][t]))} vs reset "
              f"{bp(_mean(res['reset'][t]))} per day; variance ratio (roll / reset) {j['var_ratio']:.3f}; whole-life variant "
              f"(report only) {fr(life)}; SKEW-tilt rerun (report only) " + (f"{fr(tl)} on {tl[3]} tested entries" if tl else "not available"))
    out = dict(j); out.update({"n_entries": int(res["a"].size), "life_variant": life, "skew_tilt": tl, "model_priced": True, "reason_core": reason})
    return out


# ------------------------------------------------------------------------------------------- archive wiring --

def _market(archive) -> Market:
    def build():
        days, close, adj = _prices(archive, "SPY")
        return make_market(days, close, adj, _index(archive, "fred-DTB3"))
    return _cached(archive, ("market",), build)


def _term(archive, proxy: bool = False) -> Term:
    def build():
        m = _market(archive)
        v6 = _index(archive, VIX6M) if _has(archive, VIX6M) else None
        return make_term(m.days, _index(archive, "cboe-VIX-history"), _index(archive, "cboe-VIX3M-history"), v6, proxy_before=proxy)
    return _cached(archive, ("term", proxy), build)


def _spreads(archive) -> Spreads:
    return _cached(archive, ("spreads",), lambda: Spreads.from_chains([list(_rows(archive, n)) for n in _names(archive, CHAIN)]))


def _tilt(archive) -> Optional[Tilt]:
    def build():
        names = _names(archive, SMILE)
        if not names or not _has(archive, SKEW):
            return None
        rows = [r for n in names for r in _rows(archive, n)]
        m = _market(archive)
        return Tilt.build(rows, m.days, _index(archive, SKEW), _term(archive).v30)
    return _cached(archive, ("tilt",), build)


def _first93(archive) -> str:
    v3 = _index(archive, "cboe-VIX3M-history")
    return min(v3) if v3 else "9999-12-31"


def _quote_day(archive, capture: str, observed: str) -> str:
    """The session a capture's quotes belong to: the modal last-trade date of the same day's SPY chain capture; without
    one, the previous weekday when captured before the US open (13:30 UTC), else the capture date."""
    chain = CHAIN + capture
    if _has(archive, chain):
        lt = Counter((r["value"].get("last_time") or "")[:10] for r in _rows(archive, chain) if r["value"].get("last_time"))
        if lt:
            return lt.most_common(1)[0][0]
    if observed[11:16] < "13:30":
        d = date.fromisoformat(capture).toordinal() - 1
        while date.fromordinal(d).weekday() > 4:
            d -= 1
        return date.fromordinal(d).isoformat()
    return capture


def _surface(archive) -> list:
    """[(quote_date, {dte: (atm_iv, iv_put25d)})] for SPY from every options-surface capture (dte from the quote date)."""
    def build():
        out = []
        for nm in _names(archive, SURFACE):
            pts = {}; qd = None
            for r in _rows(archive, nm):
                v = r["value"]
                if v.get("symbol") != "SPY" or not v.get("atm_iv"):
                    continue
                if qd is None:
                    obs = str(r.get("observed_at", ""))[:19].replace("T", " ")
                    qd = _quote_day(archive, nm[len(SURFACE):], obs)
                dte = (date.fromisoformat(v["expiry"]) - date.fromisoformat(qd)).days
                if dte > 0:
                    pts[dte] = (float(v["atm_iv"]), float(v.get("iv_put25d") or "nan"))
            if qd and pts:
                out.append((qd, pts))
        return sorted(out, key=lambda t: t[0])
    return _cached(archive, ("surface",), build)


def _interp_tv(pts: dict, T: float, col: int) -> float:
    """Total-variance interpolation of a surface column at T days (flat vol beyond the ends)."""
    ks = sorted(k for k in pts if np.isfinite(pts[k][col]))
    if not ks:
        return float("nan")
    if T <= ks[0]:
        return pts[ks[0]][col]
    if T >= ks[-1]:
        return pts[ks[-1]][col]
    j = bisect.bisect_left(ks, T); t0, t1 = ks[j - 1], ks[j]
    w0, w1 = pts[t0][col] ** 2 * t0, pts[t1][col] ** 2 * t1
    return math.sqrt(max((w0 + (w1 - w0) * (T - t0) / (t1 - t0)) / T, 1e-10))


def _model_back(vix: float, vix3m: float, T: float) -> float:
    w30, w93 = (vix / 100) ** 2 * 30, (vix3m / 100) ** 2 * 93
    return math.sqrt(max((w30 + (w93 - w30) * (T - 30) / 63) / T, 1e-10))


def _window_sensitivity(archive, fn, label: str, fmt=_p) -> str:
    """The headline statistic rerun from the first VIX6M print with the VIX/VIX6M proxy before the first VIX3M print."""
    if not _has(archive, VIX6M):
        return f"; window sensitivity: no VIX6M bundle, the pre-{_first93(archive)} window is not covered"
    tp = _term(archive, proxy=True); v6 = _index(archive, VIX6M)
    try:
        r = fn(tp, min(v6))
    except Exception as e:                                   # pragma: no cover - reported, never raised
        return f"; window sensitivity failed ({type(e).__name__})"
    return (f"; the trial's 2007-12 start predates the archive's VIX3M (first print {_first93(archive)}), so the test runs from "
            f"that print; window sensitivity (report only, VIX3M proxied from VIX/VIX6M from the first VIX6M print {min(v6)}; "
            f"2007-12 has no archived term index; {_proxy_fit(_term(archive), tp)}): {label} {fmt(r['headline'])} over {r['window']}")


def _scale_sensitivity(fn, label: str, fmt=_p, whole: bool = False) -> str:
    """The headline statistic with every IV multiplied by each of SCALES (report only); ``whole`` formats the result dict."""
    parts = []
    for s in SCALES:
        try:
            r = fn(s)
            parts.append(f"s={s:.2f} {fmt(r) if whole else fmt(r['headline'])}")
        except Exception as e:                               # pragma: no cover - reported, never raised
            parts.append(f"s={s:.2f} failed ({type(e).__name__})")
    return (f"; IV-scale sensitivity (report only; every IV x s, s = 0.81 is the captured SPY ATM IV / VIX ratio; the traded "
            f"version needs chain history, 2 capture days archived): {label} " + ", ".join(parts))


def _finish(rep: dict, extra: str = "") -> tuple:
    rep = dict(rep)
    rep["reason"] = rep.pop("reason_core") + extra + " — " + rep.pop("why")
    return _wrap(rep)


def b6_term_long_calendar(archive):
    """T-143: MODEL-PRICED 30/60 ATM SPY call calendar; mean P&L/debit higher when VIX/VIX3M >= 1.0 than when <= 0.9."""
    miss = _missing(archive, TERM_BASE, [CHAIN, SURFACE])
    if miss:
        return miss
    m, term, sp = _market(archive), _term(archive), _spreads(archive)
    shift, note = None, ""
    surf = _surface(archive); vix, v3 = _index(archive, "cboe-VIX-history"), _index(archive, "cboe-VIX3M-history")
    meas = []
    for qd, pts in surf:
        if qd in vix and qd in v3:
            chain = _interp_tv(pts, 60, 0) - _interp_tv(pts, 30, 0); model = _model_back(vix[qd], v3[qd], 60) - vix[qd] / 100
            meas.append((qd, chain, model))
    if meas:
        qd, chain, model = meas[-1]; shift = chain - model
        skipped = [q for q, _ in surf if q not in vix or q not in v3]
        note = (f" (latest capture whose quote day has VIX and VIX3M closes, {qd}: chain 60-30 ATM IV spread {chain * 100:+.2f} vs "
                f"model {model * 100:+.2f} vol pts" + "".join(f"; {q}: {c * 100:+.2f} vs {mm * 100:+.2f}" for q, c, mm in meas[:-1])
                + (f"; quote day {', '.join(skipped)} skipped: its index closes post-date the index capture" if skipped else "") + ")")
    rep = eval_long_calendar(m, term, sp, _first93(archive), shift, note)
    ext = _window_sensitivity(archive, lambda tp, s: eval_long_calendar(m, tp, sp, s, headline_only=True), "regime difference")
    ext += _scale_sensitivity(lambda k: eval_long_calendar(m, scaled_term(term, k), sp, _first93(archive), headline_only=True), "regime difference")
    return _finish(rep, ext)


def b6_term_short_calendar(archive):
    """T-144: MODEL-PRICED short 30/60 ATM SPY call calendar entered at VIX3M/VIX >= 1.15: mean P&L / back premium > 0."""
    miss = _missing(archive, TERM_BASE, [CHAIN])
    if miss:
        return miss
    m, term, sp = _market(archive), _term(archive), _spreads(archive)
    rep = eval_short_calendar(m, term, sp, _first93(archive))
    ext = _window_sensitivity(archive, lambda tp, s: eval_short_calendar(m, tp, sp, s, headline_only=True), "conditional mean")
    ext += _scale_sensitivity(lambda k: eval_short_calendar(m, scaled_term(term, k), sp, _first93(archive), headline_only=True), "conditional mean")
    return _finish(rep, ext)


def b6_term_long_diagonal(archive):
    """T-145: MODEL-PRICED SPY 0.70/90 vs 0.30/30 call diagonal vs the 30-DTE vertical: higher Sharpe in both halves, PBO < 0.5."""
    miss = _missing(archive, TERM_BASE, [CHAIN])
    if miss:
        return miss
    m, term, sp = _market(archive), _term(archive), _spreads(archive)
    rep = eval_diagonal(m, term, sp, _first93(archive), _tilt(archive))
    ext = _window_sensitivity(archive, lambda tp, s: eval_diagonal(m, tp, sp, s, headline_only=True), "Sharpe difference", _f)
    ext += _scale_sensitivity(lambda k: eval_diagonal(m, scaled_term(term, k), sp, _first93(archive), headline_only=True), "Sharpe difference", _f)
    return _finish(rep, ext)


def b6_term_double_calendar(archive):
    """T-146: MODEL-PRICED +/-5% double calendar vs ATM calendar: std of P&L/debit ratio < 0.9, CI < 1 in both halves."""
    miss = _missing(archive, TERM_BASE, [CHAIN])
    if miss:
        return miss
    m, term, sp = _market(archive), _term(archive), _spreads(archive)
    rep = eval_double_calendar(m, term, sp, _first93(archive), _tilt(archive))
    ext = _window_sensitivity(archive, lambda tp, s: eval_double_calendar(m, tp, sp, s, headline_only=True), "std ratio", lambda v: _f(v, 3))
    ext += _scale_sensitivity(lambda k: eval_double_calendar(m, scaled_term(term, k), sp, _first93(archive), headline_only=True), "std ratio", lambda v: _f(v, 3))
    return _finish(rep, ext)


def b6_term_double_diagonal(archive):
    """T-147: MODEL-PRICED double diagonal vs iron condor on low-VIX months: P&L / max loss difference > 0 in both halves,
    with and without the SKEW tilt."""
    miss = _missing(archive, TERM_BASE + [SKEW], [CHAIN, SMILE])
    if miss:
        return miss
    m, term, sp = _market(archive), _term(archive), _spreads(archive)
    rep = eval_double_diagonal(m, term, sp, _first93(archive), _tilt(archive))
    ext = _window_sensitivity(archive, lambda tp, s: eval_double_diagonal(m, tp, sp, s, headline_only=True), "flat-IV difference")
    ext += _scale_sensitivity(lambda k: eval_double_diagonal(m, scaled_term(term, k), sp, _first93(archive), headline_only=True), "flat-IV difference")
    return _finish(rep, ext)


def b6_term_ratio_calendar(archive):
    """T-149: MODEL-PRICED vega-neutral 30/90 ratio calendar: |Spearman(weekly P&L, delta-VIX)| CI upper < 0.3 in both halves."""
    miss = _missing(archive, TERM_BASE, [CHAIN])
    if miss:
        return miss
    m, term, sp = _market(archive), _term(archive), _spreads(archive)
    rep = eval_ratio_calendar(m, term, sp, _first93(archive))
    ext = _window_sensitivity(archive, lambda tp, s: eval_ratio_calendar(m, tp, sp, s, headline_only=True), "Spearman rho", lambda v: _f(v, 3))
    ext += _scale_sensitivity(lambda k: eval_ratio_calendar(m, scaled_term(term, k), sp, _first93(archive), headline_only=True), "Spearman rho", lambda v: _f(v, 3))
    return _finish(rep, ext)


def _chain_ratio(archive, col: int, T: float = 365.0) -> tuple:
    surf = _surface(archive); v3 = _index(archive, "cboe-VIX3M-history"); out = []
    for qd, pts in surf:
        if qd in v3:
            iv = _interp_tv(pts, T, col)
            if np.isfinite(iv):
                out.append((qd, iv, iv / (v3[qd] / 100)))
    if not out:
        return None, ""
    qd, iv, r = out[-1]
    return r, f" (chain capture, quote day {qd}: 12-month {'ATM' if col == 0 else '25-delta put'} IV {iv * 100:.2f} vs VIX3M {v3[qd]:.2f})"


def b6_term_pmcc(archive):
    """T-150: MODEL-PRICED PMCC vs covered call: Sharpe difference CI not entirely above 0 in either half (the claim survives)."""
    miss = _missing(archive, TERM_BASE, [CHAIN])
    if miss:
        return miss
    m, term, sp = _market(archive), _term(archive), _spreads(archive)
    r, note = _chain_ratio(archive, 0)
    rep = eval_pmcc(m, term, sp, _first93(archive), r, note)
    ext = _window_sensitivity(archive, lambda tp, s: eval_pmcc(m, tp, sp, s, headline_only=True), "Sharpe difference", _f)
    ext += _scale_sensitivity(lambda k: eval_pmcc(m, scaled_term(term, k), sp, _first93(archive), headline_only=True), "Sharpe difference", _f)
    return _finish(rep, ext)


def b6_term_leaps_collar(archive):
    """T-151: MODEL-PRICED LEAPS collar vs standard collar: Sharpe difference > 0 (95% CI) in both halves."""
    miss = _missing(archive, TERM_BASE, [CHAIN])
    if miss:
        return miss
    m, term, sp = _market(archive), _term(archive), _spreads(archive)
    r, note = _chain_ratio(archive, 1)
    rep = eval_leaps_collar(m, term, sp, _first93(archive), _tilt(archive), r, note)
    ext = _window_sensitivity(archive, lambda tp, s: eval_leaps_collar(m, tp, sp, s, headline_only=True), "Sharpe difference", _f)
    ext += _scale_sensitivity(lambda k: eval_leaps_collar(m, scaled_term(term, k), sp, _first93(archive), headline_only=True), "Sharpe difference", _f)
    return _finish(rep, ext)


def b6_term_calendarised_fly(archive):
    """T-152: MODEL-PRICED calendarised vs plain ATM butterfly in the top delta-VIX decile: paired difference > 0 (95% CI)."""
    miss = _missing(archive, TERM_BASE, [CHAIN])
    if miss:
        return miss
    m, term, sp = _market(archive), _term(archive), _spreads(archive)
    f93 = _first93(archive)
    tw = vix_for_vix3m(term)                    # the claim's window: VIX stands in for VIX3M before its first print
    i0 = _start_index(m, tw, T152_START)
    first = m.days[i0] if i0 < len(m.days) else "none"
    gap = None
    if first[:7] > T152_START[:7]:
        gap = (f"the first entry SPY, VIX and the bill can price is {first}, so 2007-12 is not covered even with VIX for VIX3M; "
               f"it needs SPY, VIX and DTB3 history from 2007-12-04")
    rep = eval_time_fly(m, tw, sp, T152_START, window_gap=gap)
    fit = vix_for_vix3m_fit(term); rep["proxy_fit"] = fit
    if rep["proxy_entries"]:
        ext = (f"; claim window: monthly entries from {T152_START} (the claim's 'since 2007-12'); the archived VIX3M starts "
               f"{f93}, so before it VIX stands in for VIX3M (house data guidance; the back legs are then priced at VIX), a "
               f"PROXY on {rep['proxy_entries']} entries and {len(rep['proxy_spike_days'])} of {rep['n']} spike-decile months ("
               + (", ".join(d[:7] for d in rep["proxy_spike_days"]) or "none") + f"); proxy error against the real VIX3M on "
               f"{fit['n']} overlap days: VIX - VIX3M mean {_f(fit['mean_err_3m'])} vol pts (mean |error| "
               f"{_f(fit['mae_3m']).lstrip('+')}), on the 60-DTE back-leg IV mean {_f(fit['mean_err_back'])} vol pts (mean "
               f"|error| {_f(fit['mae_back']).lstrip('+')})")
    else:
        ext = f"; claim window: monthly entries from {T152_START}, real VIX3M throughout"
    sens = {}
    real = eval_time_fly(m, term, sp, f93)
    sens["real_vix3m_only"] = {"diff": real["diff"], "ci": real["ci"], "n": real["n"], "window": real["window"]}
    ext += (f"; sensitivities (report only): real VIX3M only, from its first print {f93}: spike-decile difference "
            f"{_p(real['diff'])} ({_ci_txt(*real['ci'])}, {real['n']} spike-decile months, {real['window']})")
    if _has(archive, VIX6M):
        tc = vix_for_vix3m(_term(archive, proxy=True), "VIX/VIX6M VIX3M proxy (VIX before the first VIX6M print)")
        r6 = eval_time_fly(m, tc, sp, T152_START)
        sens["vix6m_proxy"] = {"diff": r6["diff"], "ci": r6["ci"], "n": r6["n"], "window": r6["window"]}
        ext += (f"; VIX3M proxied from VIX/VIX6M in total variance from the first VIX6M print {min(_index(archive, VIX6M))} "
                f"(VIX before it; {_proxy_fit(term, _term(archive, proxy=True))}): {_p(r6['diff'])} ({_ci_txt(*r6['ci'])}, "
                f"{r6['n']} spike-decile months)")
    else:
        ext += "; VIX/VIX6M proxy sensitivity: no VIX6M bundle"
    rep["sensitivities"] = sens
    ext += _scale_sensitivity(lambda k: eval_time_fly(m, scaled_term(tw, k), sp, T152_START, headline_only=True), "spike-decile difference")
    return _finish(rep, ext)


def b6_term_roll_tested_put(archive):
    """T-155: MODEL-PRICED tested 0.16-delta short put: roll out vs reset, P&L/day; the claim survives unless the CI of
    (roll - reset) lies entirely above 0 in a half."""
    miss = _missing(archive, SPY_BASE, [CHAIN])
    if miss:
        return miss
    m, sp = _market(archive), _spreads(archive)
    v30 = carried(m.days, _index(archive, "cboe-VIX-history"))
    tilt = None
    if _names(archive, SMILE) and _has(archive, SKEW):                 # the tilt is a sensitivity only: built on VIX alone
        rows = [r for n in _names(archive, SMILE) for r in _rows(archive, n)]
        tilt = Tilt.build(rows, m.days, _index(archive, SKEW), v30)
    bp = lambda x: "n/a" if x is None or not np.isfinite(x) else f"{x * 1e4:+.3f} bp"
    fr = lambda r: f"{bp(r['headline'])}/day (95% CI {bp(r['ci'][0])} to {bp(r['ci'][1])}, {r['n']} tested)"
    ext = _scale_sensitivity(lambda k: eval_roll(m, v30 * k, sp, headline_only=True), "roll - reset", fr, whole=True)
    return _finish(eval_roll(m, v30, sp, tilt=tilt), ext)


HARNESSES = {
    "b6_term_long_calendar": b6_term_long_calendar,
    "b6_term_short_calendar": b6_term_short_calendar,
    "b6_term_long_diagonal": b6_term_long_diagonal,
    "b6_term_double_calendar": b6_term_double_calendar,
    "b6_term_double_diagonal": b6_term_double_diagonal,
    "b6_term_ratio_calendar": b6_term_ratio_calendar,
    "b6_term_pmcc": b6_term_pmcc,
    "b6_term_leaps_collar": b6_term_leaps_collar,
    "b6_term_calendarised_fly": b6_term_calendarised_fly,
    "b6_term_roll_tested_put": b6_term_roll_tested_put,
}

THEORY_MAP = {
    "T-143": "b6_term_long_calendar",
    "T-144": "b6_term_short_calendar",
    "T-145": "b6_term_long_diagonal",
    "T-146": "b6_term_double_calendar",
    "T-147": "b6_term_double_diagonal",
    "T-149": "b6_term_ratio_calendar",
    "T-150": "b6_term_pmcc",
    "T-151": "b6_term_leaps_collar",
    "T-152": "b6_term_calendarised_fly",
    "T-155": "b6_term_roll_tested_put",
}

# Bundles each harness loads (for the runner's declared-vs-loaded check). "<prefix>*" stands for every dated bundle of that
# family in the archive index; cboe-VIX6M-history, spy-smile-* and cboe-SKEW-history are optional where marked in the
# harness (term tenors past 93 days and the window sensitivity; the SKEW tilt) and loaded when present.
_TERM_LOADS = ["daily-history-SPY", "fred-DTB3", "cboe-VIX-history", "cboe-VIX3M-history", VIX6M, CHAIN + "*"]
_TILT_LOADS = [SMILE + "*", SKEW]
BUNDLES = {
    "b6_term_long_calendar": _TERM_LOADS + [SURFACE + "*"],
    "b6_term_short_calendar": list(_TERM_LOADS),
    "b6_term_long_diagonal": _TERM_LOADS + _TILT_LOADS,
    "b6_term_double_calendar": _TERM_LOADS + _TILT_LOADS,
    "b6_term_double_diagonal": _TERM_LOADS + _TILT_LOADS,
    "b6_term_ratio_calendar": list(_TERM_LOADS),
    "b6_term_pmcc": _TERM_LOADS + [SURFACE + "*"],
    "b6_term_leaps_collar": _TERM_LOADS + _TILT_LOADS + [SURFACE + "*"],
    "b6_term_calendarised_fly": list(_TERM_LOADS),
    "b6_term_roll_tested_put": ["daily-history-SPY", "fred-DTB3", "cboe-VIX-history", CHAIN + "*"] + _TILT_LOADS,
}
