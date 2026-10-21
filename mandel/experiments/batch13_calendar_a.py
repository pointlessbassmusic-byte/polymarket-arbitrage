"""
Batch 13, group ``calendar_a``: five calendar / event claims from the 2026-10-20 web sweep (cluster "calendar"), 2026-10-21.
=========================================================================================================================

  * T-589  Treasury pre-auction concession on the weeks T-442 never examined (Lou-Yan-Zhang, RFS 2013). Clusters = ISO
           weeks 2014-01..2026-10 with a held nominal fixed-coupon 2-, 5-, 7- or 20-year auction and no 10- or 30-year
           auction; t = the week's first nominal coupon auction. Per auctioned tenor n: the synthetic total return of a
           DGSn par bond (T-574's r = y(t-1)/252 - D dy), DV01-scaled to the 10-year (x D10/Dn), summed over the four
           sessions close t-5 -> close t-1 with T-574's month-end sessions excluded; cluster value = the mean over its
           tenors of that window minus the tenor's unconditional mean 4-session window. Pass: the mean excess, net of
           the 2 bps round trip of the short that trades it, < -2 bps with one-sided p < 0.05 under BOTH the flags-fixed
           studentized circular block bootstrap (block 10) and the placement null (clusters moved to random weeks with
           no coupon auction, same weekday); both halves (2014-2019 / 2020-2026) negative; the ex-CPI version (clusters
           whose window holds a CPI release dropped) negative with p < 0.1 under both nulls; the 10/30-year-week
           secondary (seen in T-442) the same sign; the size slope (concession from the announcement to t-1 on the
           offering-amount z-score) negative with Holm-adjusted p < 0.05 over the 2 secondaries. min_n 150 clusters.
  * T-592  Put-write weekend decay. Cboe PUT live marks 2007-06-20..2026-10, intervals between consecutive Cboe closes:
           residual = index return - DTB3 bill accrual over the interval's calendar days - beta x the ^GSPC excess return,
           beta the OLS slope over the index's prior 60 live intervals. D = mean Fri->Mon residual - 1.5 x mean single-
           weekday residual (Mon-Tue .. Thu-Fri). Excluded: both intervals next to each monthly roll session (the one
           ending on it, the Thu-Fri into the roll, and the one starting on it, the roll day; read so at review, after
           the builder's run, because under the reading 'ending on it only' the registered roll clause removes nothing
           for PUT: every such interval is also < 10 days to expiry; WPUT keeps its Fri->Mon, the registered 'first
           weekend of each weekly put', under an explicit WPUT-only waiver as for the DTE rule; the end-only reading is
           reported as a sensitivity and the verdict depends on it), intervals whose held put has < 10 calendar days to
           expiry at the interval's end, intervals next to (or spanning) an exchange closure. Pass: D > 0 with one-sided
           p < 0.05 (studentized circular block bootstrap of ISO-week clusters, 4-week blocks, 5 seeds) after Holm over
           PUT and WPUT, both halves (2007-06..2016-12 / 2017-01..2026-10) positive, and D > 0 on WPUT's live marks
           (2015-08-03 on). min_n 500 weekend intervals.
  * T-582  HVIX next-session premium (Hu et al., NBER w25817). Spike day t: VIX close(t) - EWMA(t-1) >= 3.0 points,
           EWMA(t-1) = 0.7 sum_k 0.3^k VIX(t-1-k) from 1990. Trade: SPY t+1 official open -> t+1 close, 2 bps a round
           trip. Control: non-spike days in the same decile of the day-t SPY close-to-close return (cutoffs expanding
           from 1993, past returns only). Holdout 2018-06..2026-10. Pass: net matched difference > 2 bps with one-sided
           p < 0.05 (studentized bootstrap of calendar-month clusters, 5 seeds), both holdout halves (2018-06..2022-08 /
           2022-09..2026-10) positive, the raw net HVIX mean above the unconditional open-to-close mean, QQQ and IWM
           positive with Holm-adjusted p < 0.05 over the 2. Fewer than 40 holdout events: inconclusive.
  * T-581  VIX build-up before FOMC statement days (Hu et al.). z = (VIX close t-2 - VIX close t-5) / sd of 3-session VIX
           changes over the 250 sessions ending at t-2. OLS over every session 2010-01..2026-10 of SPY's close t-1 ->
           close t return on z, D (scheduled FOMC statement day), z x D, r(close t-5 -> close t-2) and 1{IBS(t-1) < 0.2},
           Newey-West lag 5. Pass: b3 > 0 with one-sided p < 0.05 under HAC and a studentized circular block bootstrap of
           the rows (21 sessions, 5 seeds), Holm over the 2 arms (FOMC primary, Employment Situation secondary: z6 over 6
           sessions, window close t-1 -> open t) and deflated jointly with T-341/T-215/T-343; b3 > 0 in 2010-2017, 2018-
           2026 and 2018-06..2026-10; the top-minus-bottom expanding-tercile FOMC event return net of costs > 0. min_n
           120 FOMC events.
  * T-583  FOMC-window short-dollar carry (Mueller-Tahbaz-Salehi-Vedolin, JF 2017). Equal-weight basket long the three
           highest-yielding of the 9 non-USD G10 currencies (re-ranked at each month end on month m-1 OECD 3-month rates
           available then), log return noon(t-1) -> noon(t+1) around each scheduled FOMC statement day t (FRED H.10),
           2011-01..2026-10. Statistic: mean net window return - 2 x the mean noon-to-noon daily basket return outside
           every FOMC window. Pass: > 3 bps with one-sided p < 0.05 under both a same-position-in-month date permutation
           (10,000 draws) and a studentized circular block bootstrap (21 days), Holm over the primary and DOL; both halves
           (2011-2018 / 2019-2026) positive; DOL (the 9-currency basket) positive after Holm. min_n 120 FOMC windows.

Conventions (and every reading taken before any run; the harness reasons repeat the binding ones)
  * Data. Bundles via ``archive.load`` / ``batch6c_cal`` loaders (a row is used only when available at capture). Yahoo
    bars through ``batch4_ohlc._bars`` (raw open/high/low/close, adjclose = total return); Cboe strategy indices through
    ``batch6b_bw.cboe_index`` (flagged prints out, back-test labels kept); DTB3 bills through ``batch6b_bw.Bills``
    (calendar-day accrual at the print dated strictly before each day: the indices' calendar-day rule).
  * Costs, the conservative reading wherever a trial lists a cost next to a bar: the cost is charged on the traded
    window AND the bar applies to the net figure (T-589: excess + 2 bps < -2 bps; T-582: matched difference - 2 bps
    > 2 bps; T-583: window return net of its basket's round trip; T-581: the tercile spread pays 2 bps on each leg).
    Sign criteria (halves, secondaries) are judged net as well. Gross readings are reported.
  * Inference. Every resampled p is pooled over seeds and escalated while its Monte-Carlo band straddles the criterion's
    alpha (``_escalate``, ``batch6c_cal.decide_p``), so a seed never decides a criterion. Where a criterion names two
    nulls or two readings it passes only when both pass and fails only when both fail (``batch6c_cal._agree``).
  * Point in time. Daily bars are known at their close; the VIX close (16:15 ET) is never used for a same-day 16:00
    SPY entry (T-581's z ends at t-2 for a t-1 close entry; T-582 enters at the t+1 open); auction, FOMC, CPI and
    payroll dates are scheduled in advance; T-589's offering amounts enter only from their announcement row's
    available_at (end of the announcement day), so the size window starts at the next session's close (the registered
    announcement-day-close window is reported); T-583's ranks use month m-1 rates whose available_at precedes the
    month-m rank date, taking a print as published at the later of its stamp and the 15th of the following month (the
    archive stamps every print on the 28th of its own month); a currency whose m-1 print fails that gate carries its
    earlier print and is flagged (EUR/GBP after the OECD series end in 2026-01); T-592's betas use
    prior live intervals only and back-tested index rows never enter.
  * Rule 10: no claim holds on a free grid phase: every window is anchored on a dated event (auctions, FOMC, payrolls,
    VIX spikes) or on the weekday calendar the claim names (T-592).
"""

from __future__ import annotations

import bisect
import math
import re
from collections import defaultdict
from datetime import date, timedelta
from statistics import NormalDist
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments import batch4_ohlc as OHLC
from mandel.experiments import batch6b_bw as BW
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch11_xasset import mod_duration
from mandel.experiments.batch5_macro import release_days_from_rows, to_sessions
from mandel.experiments.batch6_surf import _out

SEED = 0
N_BOOT = 2000                    # resamples per seed (5 seeds -> 10,000 draws)
N_SEEDS = 5
MAX_SEEDS = 50
ALPHA = 0.05
_NORM = NormalDist()

AUCT_B, CPI_B, FOMC_B, NFP_B = "treasury-auctions", "macro-release-cpi", "fomc-meetings", "macro-release-employment-situation"
IEF_B, SHY_B, TLT_B = "daily-history-IEF", "daily-history-SHY", "daily-history-TLT"
SPY_B, QQQ_B, IWM_B, GSPC_B = "daily-history-SPY", "daily-history-QQQ", "daily-history-IWM", "daily-history--GSPC"
VIX_B, VXTLT_B = "cboe-VIX-history", "cboe-VXTLT-history"
PUT_B, WPUT_B, PUTY_B = "cboe-PUT-history", "cboe-WPUT-history", "cboe-PUTY-history"
DTB3_B, DFF_B = "fred-DTB3", "fred-DFF"
FX_B, RATES_B = "fx-spot-g10", "fx-rates-3m"

# T-589
T589_START, T589_END = "2014-01-01", "2026-10-31"
T589_SPLIT = "2020-01-01"                     # halves 2014-2019 / 2020-2026
T589_SPAN = 4                                 # close t-5 -> close t-1: four sessions
T589_BAR = 2e-4                               # excess < -2 bps
T589_COST = 2e-4                              # 2 bps a round trip
T589_BLOCK = 10
T589_MIN_N = 150
T589_ALT_ALPHA = 0.10                         # ex-CPI version: p < 0.1
T589_UNSEEN = (2, 5, 7, 20)
T589_SEEN = (10, 30)
T589_TENORS = (2, 5, 7, 10, 20, 30)
T589_YIELD = {2: "fred-DGS2", 5: "fred-DGS5", 7: "fred-DGS7", 10: "fred-DGS10", 20: "fred-DGS20", 30: "fred-DGS20"}
T589_STD = (2, 3, 5, 7, 10, 20, 30)           # standard coupon tenors (a reopening's remaining term maps to the nearest)
T589_Z_LOOKBACK = 365                         # trailing 12 months (calendar days) of same-tenor auctions
T589_Z_MIN = 6                                # at least 6 prior same-tenor auctions for a z-score
T589_FLAGS = {"2020-03": ("2020-03-01", "2020-03-31"), "2022": ("2022-01-01", "2022-12-31")}
# T-592
T592_START, T592_END = "2007-06-20", "2026-10-31"
T592_SPLIT = "2017-01-01"
T592_LIVE = {"PUT": "2007-06-20", "WPUT": "2015-08-03", "PUTY": "2019-02-15"}
T592_MULT = 1.5
T592_BETA_WIN = 60
T592_MIN_DTE = 10
T592_BLOCK = 4                                # 4-week blocks of ISO-week clusters
T592_MIN_N = 500
# T-582
T582_HOLD = ("2018-06-01", "2026-10-31")
T582_HALVES = (("2018-06-01", "2022-08-31"), ("2022-09-01", "2026-10-31"))
T582_PAPER = ("2000-01-01", "2018-05-31")
T582_DECAY = 0.3
T582_THR = 3.0
T582_BAR = 2e-4
T582_COST = 2e-4
T582_DEC_FROM = "1993-01-01"
T582_DEC_MIN = 250                            # prior returns before an expanding decile is assigned
T582_DECLUSTER = 5
T582_MEAN_BLOCK = 3.0                         # stationary bootstrap of month clusters: mean block 3 months (review)
T582_IBS = 0.2
T582_MIN_N = 40
# T-581
T581_START, T581_END = "2010-01-01", "2026-10-31"
T581_SPLIT = "2018-01-01"
T581_POST = "2018-06-01"
T581_PAPER = ("1994-01-01", "2009-12-31")
T581_SD_WIN = 250
T581_LAG = 5
T581_BLOCK = 21
T581_COST = 2e-4                              # per leg of the tercile spread
T581_IBS = 0.2
T581_TERC_MIN = 9                             # prior FOMC events before an expanding tercile is assigned
T581_JOINT = 5                                # joint deflation family: T-581 FOMC + NFP arms, T-341, T-215, T-343
T581_MIN_N = 120
T581_ZLB = (("2010-01-01", "2015-12-16"), ("2020-03-15", "2022-03-16"))
# T-583
T583_START, T583_END = "2011-01-01", "2026-10-31"
T583_SPLIT = "2019-01-01"
T583_ZLB = ("2011-01-01", "2015-12-31")
G10 = ("EUR", "JPY", "GBP", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK")
T583_TOP = 3
T583_BAR = 3e-4
T583_COST_SIDE = {"NOK": 4e-4, "SEK": 4e-4}   # others 1.5 bps a side
T583_COST_MAJOR = 1.5e-4
T583_BLOCK = 21
T583_N_PERM = 10000
T583_MIN_N = 120
T583_PUB_DAY = 15                             # an OECD month-m rate counts as published from the 15th of month m+1 (review)
T583_EASE = -0.20                             # DFF 30-day mean down more than 20 bps over the prior 6 months
T583_FX60 = {"EUR": ("EURUSD=X", False), "GBP": ("GBPUSD=X", False), "AUD": ("AUDUSD=X", False),
             "NZD": ("NZDUSD=X", False), "JPY": ("USDJPY=X", True), "CAD": ("USDCAD=X", True), "CHF": ("USDCHF=X", True)}


# ================================================================================================ shared helpers ==

def _missing(archive, names):
    return B7C._missing(archive, names)


def _has(archive, name: str) -> bool:
    return B7C._has(archive, name)


def _bp(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 1e4:+.{nd}f}"


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _p(x) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.4f}"


def _mc(p, draws) -> str:
    return CAL._mc(p, draws)


def _d(s: str) -> date:
    return date.fromisoformat(s)


def iso_week(day: str) -> tuple:
    return tuple(_d(day).isocalendar()[:2])


def _decide(p, draws, alpha: float = ALPHA) -> Optional[bool]:
    return CAL.decide_p(p, draws, alpha)


def _escalate(batch: Callable[[int], tuple], draws: int, k0: int = N_SEEDS, k_max: int = MAX_SEEDS,
              alpha: float = ALPHA) -> tuple:
    """``batch6c_cal.escalate_p`` with the Monte-Carlo decision taken at ``alpha``: (p_greater, p_less, draws)."""
    ps = [batch(k) for k in range(max(1, int(k0)))]
    while True:
        if any(p is None for p in ps[0]):
            return None, None, draws * len(ps)
        pg, pl = float(np.mean([p[0] for p in ps])), float(np.mean([p[1] for p in ps]))
        nd = draws * len(ps)
        if len(ps) >= k_max or (_decide(pg, nd, alpha) is not None and _decide(pl, nd, alpha) is not None):
            return pg, pl, nd
        ps.append(batch(len(ps)))


def _sig(point, p, draws, side: str = "less", alpha: float = ALPHA) -> Optional[bool]:
    """'point < 0 (side less) / > 0 (greater) with one-sided p < alpha': False when the point has the wrong sign, else
    the Monte-Carlo-banded decision of p."""
    if point is None or not np.isfinite(point):
        return None
    if (point >= 0) if side == "less" else (point <= 0):
        return False
    return _decide(p, draws, alpha)


def _hac_ok(point, p, side: str = "less", alpha: float = ALPHA) -> Optional[bool]:
    if point is None or p is None or not np.isfinite(point):
        return None
    if (point >= 0) if side == "less" else (point <= 0):
        return False
    return bool(p < alpha)


def holm2(p_a: Optional[float], p_b: Optional[float]) -> tuple:
    """Holm-adjusted (p_a, p_b) over a family of two (a missing p counts as 1 and stays None)."""
    adj = B7C.holm([p_a, p_b])
    return adj[0], adj[1]


def ols_hac(y, X, lag: int) -> dict:
    """OLS of y on [1, X] with Newey-West (Bartlett, ``lag``) standard errors: coef / se / t lists (intercept first)."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(len(y), -1)
    n = y.size
    Z = np.column_stack([np.ones(n), X])
    if n <= Z.shape[1] + 1:
        return {"coef": None, "se": None, "t": None, "n": int(n), "lag": int(lag)}
    A = np.linalg.pinv(Z.T @ Z)
    b = A @ Z.T @ y
    e = y - Z @ b
    u = Z * e[:, None]
    S = u.T @ u
    for l in range(1, min(lag, n - 1) + 1):
        G = u[l:].T @ u[:-l]
        S += (1.0 - l / (lag + 1.0)) * (G + G.T)
    se = np.sqrt(np.maximum(np.diag(A @ S @ A), 0.0))
    return {"coef": [float(v) for v in b], "se": [float(v) for v in se],
            "t": [float(c / s) if s > 0 else float("nan") for c, s in zip(b, se)], "n": int(n), "lag": int(lag)}


def boot_coef_circ(y, X, j: int, lag: int, block: int, n_boot: int, seed: int, chunk: int = 100) -> tuple:
    """(p_greater, p_less) of coefficient ``j`` of X (0-based, intercept excluded): studentized (bootstrap-t) circular
    block bootstrap of the (y, X) rows (``block`` consecutive rows; block 1 = i.i.d. rows), t* = (b* - b) / se*_HAC
    on every resample, p_greater = share of t* >= t (with the +1 correction), p_less = share of t* <= t."""
    y = np.asarray(y, float)
    X = np.asarray(X, float).reshape(len(y), -1)
    n = y.size
    Z = np.column_stack([np.ones(n), X])
    q = j + 1
    full = ols_hac(y, X, lag)
    if full["coef"] is None or not full["se"][q] > 0:
        return None, None
    b0, t0 = full["coef"][q], full["t"][q]
    rng = np.random.default_rng(seed)
    ts, done = [], 0
    while done < n_boot:
        k = min(chunk, n_boot - done)
        idx = CAL._boot_idx(rng, n, block, k)
        Zb, yb = Z[idx], y[idx]
        Zt = np.transpose(Zb, (0, 2, 1))
        A = np.linalg.pinv(Zt @ Zb)
        B = (A @ (Zt @ yb[:, :, None]))[:, :, 0]
        e = yb - (Zb @ B[:, :, None])[:, :, 0]
        U = Zb * e[:, :, None]
        Ut = np.transpose(U, (0, 2, 1))
        S = Ut @ U
        for l in range(1, min(lag, n - 1) + 1):
            G = Ut[:, :, l:] @ U[:, :-l]
            S += (1.0 - l / (lag + 1.0)) * (G + np.transpose(G, (0, 2, 1)))
        V = A @ S @ A
        se = np.sqrt(np.maximum(V[:, q, q], 0.0))
        ok = se > 0
        ts.append((B[ok, q] - b0) / se[ok])
        done += k
    t = np.concatenate(ts)
    m = t.size
    return float((np.sum(t >= t0) + 1) / (m + 1)), float((np.sum(t <= t0) + 1) / (m + 1))


def coef_test(y, X, j: int, lag: int, block: int, n_boot: int = N_BOOT, seed: int = SEED, alpha: float = ALPHA,
              boot: bool = True) -> dict:
    """Coefficient ``j``: point, HAC t, HAC normal one-sided p's and the escalated studentized circular-block p's."""
    full = ols_hac(y, X, lag)
    if full["coef"] is None:
        return {"coef": None, "t": None, "n": full["n"]}
    q = j + 1
    t = full["t"][q]
    out = {"coef": full["coef"][q], "se": full["se"][q], "t": t, "n": full["n"], "lag": lag,
           "hac_p_less": float(_NORM.cdf(t)) if np.isfinite(t) else None,
           "hac_p_greater": float(1 - _NORM.cdf(t)) if np.isfinite(t) else None,
           "boot_p_greater": None, "boot_p_less": None, "boot_draws": 0}
    if boot:
        pg, pl, dr = _escalate(lambda k: boot_coef_circ(y, X, j, lag, block, n_boot, seed + k), n_boot, alpha=alpha)
        out.update(boot_p_greater=pg, boot_p_less=pl, boot_draws=dr)
    return out


def _closed_weekday(d: date) -> bool:
    return d.weekday() < 5 and not CAL.is_nyse_session(d)


def holiday_adjacent(day: str) -> bool:
    """A session next to an exchange closure: the previous or the next weekday was closed (rule calendar plus the
    known unscheduled closures: the realised calendar)."""
    d = _d(day)
    p = d - timedelta(days=3 if d.weekday() == 0 else 1)
    nx = d + timedelta(days=3 if d.weekday() == 4 else 1)
    return _closed_weekday(p) or _closed_weekday(nx)


def _rows(archive, name: str) -> list:
    return CAL._rows(archive, name)


def _fomc_days(archive) -> list:
    """Scheduled FOMC statement days (decision_day of scheduled, non-future rows; unscheduled meetings excluded)."""
    return sorted({(r["value"] or {}).get("decision_day") for r in _rows(archive, FOMC_B)
                   if (r.get("value") or {}).get("scheduled") and not r["value"].get("future") and r["value"].get("decision_day")})


def _release_days(archive, name: str, kind: str) -> list:
    return release_days_from_rows(_rows(archive, name), kind)[0]


def _in(day: str, span: tuple) -> bool:
    return span[0] <= day <= span[1]


# ================================================================================ T-589 Treasury auctions ==

_TERM = re.compile(r"^(\d+)-Year(?: (\d+)-Month)?")


def auction_tenor(term: str) -> Optional[int]:
    """The standard coupon tenor an auctioned security term maps to ('9-Year 11-Month' -> 10, '19-Year 10-Month' ->
    20, '2-Year' reopening an old 5-year -> 2): the nearest of 2/3/5/7/10/20/30 years to the remaining term."""
    m = _TERM.match(str(term or ""))
    if not m:
        return None
    y = int(m.group(1)) + int(m.group(2) or 0) / 12.0
    return min(T589_STD, key=lambda t: (abs(t - y), t))


def t589_auctions(rows: Sequence[dict]) -> tuple:
    """(nominal, coupon_weeks): one dict per held nominal fixed-coupon Note/Bond auction from the announcement rows
    (deduplicated by CUSIP + auction date; FRNs and TIPS dropped; reopenings kept and labelled): {date, tenor, term,
    reopening, amt, ann_day, av (announcement available_at ISO), cusip}; and the set of ISO weeks holding ANY Note/Bond
    auction (FRN and TIPS included: the placement pool is weeks with no coupon auction at all)."""
    held = {r.get("key") for r in rows if r.get("kind") == "auction-result"}
    seen, out, weeks = set(), [], set()
    for r in rows:
        if r.get("kind") != "auction-announcement":
            continue
        v = r.get("value") or {}
        ad = str(v.get("auction_date") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ad) or v.get("security_type") not in ("Note", "Bond"):
            continue
        weeks.add(iso_week(ad))
        key = (v.get("cusip"), ad)
        if key in seen or r.get("key") not in held:
            continue
        if str(v.get("floating_rate")) == "Yes" or str(v.get("inflation_index_security")) == "Yes" or not v.get("nominal_coupon"):
            continue
        ten = auction_tenor(v.get("security_term"))
        if ten is None:
            continue
        seen.add(key)
        try:
            amt = float(v.get("offering_amt"))
        except (TypeError, ValueError):
            amt = float("nan")
        out.append({"date": ad, "tenor": ten, "term": v.get("security_term"), "reopening": str(v.get("reopening")) == "Yes",
                    "amt": amt, "ann_day": str(v.get("announcemt_date") or "")[:10], "av": r.get("available_at"),
                    "cusip": v.get("cusip")})
    return sorted(out, key=lambda a: (a["date"], a["tenor"], str(a["cusip"]))), weeks


def month_end_mask(days: Sequence[str]) -> np.ndarray:
    """T-574's month-end sessions: the last observation of each calendar month; the data's final month only when a
    later month is present (an incomplete month has no month-end session yet)."""
    n = len(days)
    m = np.zeros(n, bool)
    for i in range(n - 1):
        if days[i][:7] != days[i + 1][:7]:
            m[i] = True
    return m


def synth_panel(yields: dict, tenors: Sequence[int] = T589_TENORS, start: str = T589_START, end: str = T589_END) -> dict:
    """DV01-scaled synthetic daily total returns per tenor on the common days of the yield series: r_n(t) = y(t-1)/100/252
    - D_n(y(t-1)) (y(t) - y(t-1))/100 (T-574; D the modified duration of an n-year semi-annual par bond; the 30-year
    tenor prices DGS20 at a 30-year duration), scaled by D_10(y10(t-1)) / D_n(yn(t-1)) (a 10-year-DV01-equivalent
    position rebalanced at each close). Return days in [start, end]. V = scaled returns, U = V with month-end sessions
    zeroed (T-574's sessions are excluded from every window), me = the month-end mask."""
    keys = None
    for t in tenors:
        s = set(yields[t])
        keys = s if keys is None else keys & s
    allk = sorted(keys)
    j0 = max(bisect.bisect_left(allk, start), 1)
    days = [d for d in allk[j0:] if d <= end]
    prev = allk[j0 - 1:j0 - 1 + len(days)]
    me_full = month_end_mask(allk)
    me = me_full[j0:j0 + len(days)]
    V = np.zeros((len(tenors), len(days)))
    y10p = np.array([yields[10][d] for d in prev], float)
    d10 = np.array([mod_duration(y, 10) for y in y10p])
    for k, t in enumerate(tenors):
        yp = np.array([yields[t][d] for d in prev], float)
        yc = np.array([yields[t][d] for d in days], float)
        dn = np.array([mod_duration(y, t) for y in yp])
        r = yp / 100.0 / 252.0 - dn * (yc - yp) / 100.0
        V[k] = r * d10 / dn
    U = V * (~me)[None, :]
    return {"days": days, "tenors": tuple(tenors), "V": V, "U": U, "me": me}


def windows(U: np.ndarray, span: int = T589_SPAN) -> np.ndarray:
    """W[..., a] = sum of U[..., a+1 .. a+span]: the window from the close of day a to the close of day a+span."""
    pad = np.zeros(U.shape[:-1] + (1,))
    cum = np.concatenate([pad, np.cumsum(U, axis=-1)], axis=-1)
    return cum[..., span + 1:] - cum[..., 1:-span]


def t589_clusters(auctions: Sequence[dict], days: Sequence[str], fams: Sequence[int], exclude: Sequence[int] = (),
                  tenors: Sequence[int] = T589_TENORS, start: str = T589_START, end: str = T589_END,
                  span: int = T589_SPAN) -> list:
    """ISO-week clusters with an auction in ``fams`` and none in ``exclude``, t = the week's first nominal coupon auction
    (any tenor) in [start, end]. Window start a = (index of the first series day >= t) - 5, i.e. the close of t-5, ending
    at the close of t-1. Each: {week, t, a, tenors (the auctioned tenors with a registered yield series), auctions,
    reopen_any, reopen_all, ann_last (latest announcement day), av_last}."""
    wk = defaultdict(list)
    for x in auctions:
        if start <= x["date"] <= end:
            wk[iso_week(x["date"])].append(x)
    out = []
    for w in sorted(wk):
        al = wk[w]
        ts = {x["tenor"] for x in al}
        if not (ts & set(fams)) or (ts & set(exclude)):
            continue
        t = min(x["date"] for x in al)
        i = bisect.bisect_left(days, t)
        a = i - (span + 1)
        if a < 0 or i > len(days) - 1:              # t itself must be inside the series, so t-1 is its previous day
            continue
        use = [x for x in al if x["tenor"] in tenors]
        ten = sorted({x["tenor"] for x in use})
        if not ten:
            continue
        out.append({"week": w, "t": t, "a": a, "i_t": i, "tenors": ten, "auctions": use, "all_tenors": sorted(ts),
                    "reopen_any": any(x["reopening"] for x in use), "reopen_all": all(x["reopening"] for x in use),
                    "ann_last": max((x["ann_day"] for x in use if x["ann_day"]), default=None),
                    "av_last": max((x["av"] for x in use if x["av"]), default=None)})
    return out


def _weights(clusters: Sequence[dict], tenors: Sequence[int]) -> np.ndarray:
    """(K, T) equal weights over each cluster's tenors."""
    A = np.zeros((len(clusters), len(tenors)))
    pos = {t: k for k, t in enumerate(tenors)}
    for c, cl in enumerate(clusters):
        for t in cl["tenors"]:
            A[c, pos[t]] = 1.0 / len(cl["tenors"])
    return A


def cluster_values(W: np.ndarray, A: np.ndarray, starts: np.ndarray, seg: Optional[np.ndarray] = None) -> np.ndarray:
    """Per-cluster excess: sum_n A[c, n] (W[n, a_c] - mean_a W[n, a]) (W: (T, S) windows). ``seg`` (an integer segment
    id per window start, e.g. the half): each cluster is demeaned by its own segment's unconditional mean instead."""
    if seg is None:
        Wb = W.mean(axis=-1)
        return np.einsum("ct,tc->c", A, W[:, starts] - Wb[:, None])
    return np.einsum("ct,tc->c", A, W[:, starts] - _seg_means(W, seg)[..., seg[starts]])


def _seg_means(W: np.ndarray, seg: np.ndarray) -> np.ndarray:
    """(..., T, n_seg) means of the windows ``W`` (..., T, S) over the starts of each segment."""
    return np.stack([W[..., seg == s].mean(axis=-1) for s in range(int(seg.max()) + 1)], axis=-1)


def window_segments(days: Sequence[str], S: int, split: str = T589_SPLIT, span: int = T589_SPAN) -> np.ndarray:
    """Half of each window start a (0 before ``split``, 1 from it), by the window's last day (the close of t-1 for a
    cluster)."""
    return np.array([1 if days[a + span] >= split else 0 for a in range(S)], int)


def _flags_fixed_batch(V, me, A, starts, shift: float, block: int, n_boot: int, seed: int, span: int = T589_SPAN,
                       chunk: int = 200, seg: Optional[np.ndarray] = None) -> tuple:
    """One seed of the flags-fixed studentized circular block bootstrap: the non-month-end daily returns (all tenors on
    the same resampled days) are resampled in circular ``block``-day blocks into the non-month-end positions (month-end
    positions stay zero, the event flags and windows stay fixed), every cluster value recomputed; t* = mean / se
    (se = sd of the cluster values / sqrt K) against t = (observed mean + shift) / se. (p_greater, p_less). ``seg``:
    cluster values demeaned by their own segment's mean (observed and resampled alike)."""
    keep = np.where(~me)[0]
    pool = V[:, keep]
    Mk = keep.size
    K = len(starts)
    U0 = V * (~me)[None, :]
    obs = cluster_values(windows(U0, span), A, starts, seg)
    se0 = obs.std(ddof=1) / math.sqrt(K)
    if not se0 > 0:
        return None, None
    t0 = (obs.mean() + shift) / se0
    rng = np.random.default_rng(seed)
    ts, done = [], 0
    T, M = V.shape
    while done < n_boot:
        k = min(chunk, n_boot - done)
        idx = CAL._boot_idx(rng, Mk, block, k)
        Ub = np.zeros((k, T, M))
        Ub[:, :, keep] = np.transpose(pool[:, idx], (1, 0, 2))
        Wb = windows(Ub, span)
        if seg is None:
            G = Wb[:, :, starts] - Wb.mean(axis=-1)[:, :, None]
        else:
            G = Wb[:, :, starts] - _seg_means(Wb, seg)[:, :, seg[starts]]
        vals = np.einsum("ktc,ct->kc", G, A)
        se = vals.std(axis=1, ddof=1) / math.sqrt(K)
        ok = se > 0
        ts.append(vals.mean(axis=1)[ok] / se[ok])
        done += k
    t = np.concatenate(ts)
    return float((np.sum(t >= t0) + 1) / (t.size + 1)), float((np.sum(t <= t0) + 1) / (t.size + 1))


def placement_pool(days: Sequence[str], coupon_weeks: set, span: int = T589_SPAN) -> np.ndarray:
    """(P, 5) window starts a' of ISO weeks inside the series with no coupon auction: for each weekday 0..4 the series
    day of that week nearest to it (T-442's construction), minus span + 1. Rows with any start outside [0, S) dropped."""
    S = len(days) - span
    byw = defaultdict(dict)
    for i, d in enumerate(days):
        byw[iso_week(d)][_d(d).weekday()] = i
    rows = []
    for w, mp in sorted(byw.items()):
        if w in coupon_weeks or len(mp) < 1:
            continue
        row = []
        for k in range(5):
            j = min(mp, key=lambda x: (abs(x - k), x))
            row.append(mp[j] - (span + 1))
        if all(0 <= s < S for s in row):
            rows.append(row)
    return np.array(rows, int).reshape(-1, 5)


def _placement_batch(W, A, wd, pool, obs_shifted: float, n_place: int, seed: int) -> tuple:
    """One seed of the placement null: each cluster moved to a random no-coupon-auction week (same weekday, distinct
    weeks when the pool allows), the mean excess recomputed; (p_greater, p_less) of the shifted observed mean."""
    K = A.shape[0]
    P = pool.shape[0]
    if P < 2:
        return None, None
    rng = np.random.default_rng(seed + 7919)
    WW = W - W.mean(axis=-1)[:, None]
    stats, done = [], 0
    while done < n_place:
        k = min(1000, n_place - done)
        ch = np.argsort(rng.random((k, P)), axis=1)[:, :K] if P >= K else rng.integers(0, P, (k, K))
        Sp = pool[ch, wd[None, :]]
        vals = np.einsum("tkc,ct->kc", WW[:, Sp], A)
        stats.append(vals.mean(axis=1))
        done += k
    st = np.concatenate(stats)
    return float((np.sum(st >= obs_shifted) + 1) / (st.size + 1)), float((np.sum(st <= obs_shifted) + 1) / (st.size + 1))


def pool_years(days: Sequence[str], pool: np.ndarray, span: int = T589_SPAN) -> np.ndarray:
    """Calendar year of each placement-pool week (its mid-week series day)."""
    return np.array([int(days[r[2] + span + 1][:4]) for r in pool], int)


def _placement_strat_batch(W, A, wd, pool, pyear, cyear, seg, obs_shifted: float, n_place: int, seed: int) -> tuple:
    """One seed of the year-stratified placement null for the period-demeaned statistic: each cluster moved to a random
    no-coupon-auction week of its own calendar year (same weekday, drawn with replacement; a year without pool weeks
    draws from the whole pool), every window demeaned by its own half's mean; (p_greater, p_less)."""
    K = A.shape[0]
    if pool.shape[0] < 2:
        return None, None
    rng = np.random.default_rng(seed + 15485863)
    WW = W - _seg_means(W, seg)[:, seg]
    cand = {y: np.where(pyear == y)[0] for y in set(cyear.tolist())}
    allr = np.arange(pool.shape[0])
    stats, done = [], 0
    while done < n_place:
        k = min(1000, n_place - done)
        ch = np.empty((k, K), int)
        for y, cs in cand.items():
            cols = np.where(cyear == y)[0]
            src = cs if cs.size else allr
            ch[:, cols] = src[rng.integers(0, src.size, (k, cols.size))]
        Sp = pool[ch, wd[None, :]]
        stats.append(np.einsum("tkc,ct->kc", WW[:, Sp], A).mean(axis=1))
        done += k
    st = np.concatenate(stats)
    return float((np.sum(st >= obs_shifted) + 1) / (st.size + 1)), float((np.sum(st <= obs_shifted) + 1) / (st.size + 1))


def period_demeaned_test(panel: dict, clusters: Sequence[dict], pool: np.ndarray, shift: float, alpha: float = ALPHA,
                         n_boot: int = N_BOOT, seed: int = SEED, split: str = T589_SPLIT, span: int = T589_SPAN) -> dict:
    """Report only (the reviewer's period check): the cluster excess with each cluster demeaned by its own half's
    unconditional window mean (``window_segments``), under the flags-fixed CBB (half-demeaned in every resample) and the
    year-stratified placement null, at the shifted statistic (H0 excess + shift >= 0 tested by p_less)."""
    W = windows(panel["U"], span)
    S = W.shape[1]
    cl = [c for c in clusters if 0 <= c["a"] < S]
    if len(cl) < 4:
        return {"n": len(cl)}
    seg = window_segments(panel["days"], S, split, span)
    A = _weights(cl, panel["tenors"])
    starts = np.array([c["a"] for c in cl], int)
    vals = cluster_values(W, A, starts, seg)
    wd = np.array([_d(c["t"]).weekday() for c in cl], int)
    cyear = np.array([int(c["t"][:4]) for c in cl], int)
    pyear = pool_years(panel["days"], pool, span)
    obs = float(vals.mean())
    pg, pl, dr = _escalate(lambda k: _flags_fixed_batch(panel["V"], panel["me"], A, starts, shift, T589_BLOCK, n_boot, seed + k,
                                                        span, seg=seg), n_boot, alpha=alpha)
    pg2, pl2, dr2 = _escalate(lambda k: _placement_strat_batch(W, A, wd, pool, pyear, cyear, seg, obs + shift, n_boot, seed + k),
                              n_boot, alpha=alpha)
    return {"n": len(cl), "excess": obs, "n_by_half": [int((seg[starts] == 0).sum()), int((seg[starts] == 1).sum())],
            "boot_p_less": pl, "boot_draws": dr, "place_p_less": pl2, "place_draws": dr2,
            "pool_weeks_by_year": {int(y): int((pyear == y).sum()) for y in sorted(set(pyear.tolist()))}}


def concession_test(panel: dict, clusters: Sequence[dict], pool: np.ndarray, shift: float, alpha: float = ALPHA,
                    n_boot: int = N_BOOT, seed: int = SEED, split: Optional[str] = T589_SPLIT,
                    span: int = T589_SPAN, pvals: bool = True) -> dict:
    """The cluster excess (mean over clusters of the tenor-averaged window minus each tenor's unconditional window
    mean), its two nulls at the shifted statistic (excess + shift; H0 excess + shift >= 0 tested by p_less) and the
    halves (each half's excess against its own unconditional mean, by cluster date t)."""
    tenors = panel["tenors"]
    W = windows(panel["U"], span)
    S = W.shape[1]
    cl = [c for c in clusters if 0 <= c["a"] < S]
    out = {"n": len(cl)}
    if len(cl) < 4:
        return out
    A = _weights(cl, tenors)
    starts = np.array([c["a"] for c in cl], int)
    vals = cluster_values(W, A, starts)
    ev_mean = float(np.einsum("ct,tc->c", A, W[:, starts]).mean())
    out.update(excess=float(vals.mean()), event_mean=ev_mean, uncond_mean=float(ev_mean - vals.mean()),
               se=float(vals.std(ddof=1) / math.sqrt(len(cl))), values=vals, t_dates=[c["t"] for c in cl])
    if split:
        dd = np.array(panel["days"][:S])
        td = np.array([c["t"] for c in cl])
        hv = []
        for m_ev, m_u in ((td < split, dd < split), (td >= split, dd >= split)):
            if m_ev.sum() >= 2 and m_u.sum() > span:
                Wb = W[:, m_u].mean(axis=1)
                hv.append(float(np.einsum("ct,tc->c", A[m_ev], W[:, starts[m_ev]] - Wb[:, None]).mean()))
            else:
                hv.append(None)
        out["halves"] = hv
        out["halves_n"] = [int((td < split).sum()), int((td >= split).sum())]
    if not pvals:
        return out
    wd = np.array([_d(c["t"]).weekday() for c in cl], int)
    pg, pl, dr = _escalate(lambda k: _flags_fixed_batch(panel["V"], panel["me"], A, starts, shift, T589_BLOCK, n_boot,
                                                        seed + k, span), n_boot, alpha=alpha)
    out.update(boot_p_greater=pg, boot_p_less=pl, boot_draws=dr)
    pg2, pl2, dr2 = _escalate(lambda k: _placement_batch(W, A, wd, pool, float(vals.mean()) + shift, n_boot, seed + k),
                              n_boot, alpha=alpha)
    out.update(place_p_greater=pg2, place_p_less=pl2, place_draws=dr2, pool_weeks=int(pool.shape[0]))
    return out


def _both_nulls(res: dict, point: float, alpha: float = ALPHA) -> Optional[bool]:
    return CAL._agree([_sig(point, res.get("boot_p_less"), res.get("boot_draws", 0), "less", alpha),
                       _sig(point, res.get("place_p_less"), res.get("place_draws", 0), "less", alpha)])


def auction_z(auctions: Sequence[dict], lookback: int = T589_Z_LOOKBACK, min_prior: int = T589_Z_MIN) -> dict:
    """{(cusip, date): z} of each auction's offering amount against the same tenor's auctions dated in the prior
    ``lookback`` calendar days (at least ``min_prior`` of them; their amounts were announced before): (amt - mean) / sd
    (ddof 1); sd = 0 with amt = mean gives z = 0, sd = 0 with a change is undefined (left out)."""
    by = defaultdict(list)
    for x in sorted(auctions, key=lambda a: a["date"]):
        by[x["tenor"]].append(x)
    out = {}
    for ten, al in by.items():
        for i, x in enumerate(al):
            lo = (_d(x["date"]) - timedelta(days=lookback)).isoformat()
            prior = [p["amt"] for p in al[:i] if lo <= p["date"] < x["date"] and np.isfinite(p["amt"])]
            if len(prior) < min_prior or not np.isfinite(x["amt"]):
                continue
            m, s = float(np.mean(prior)), float(np.std(prior, ddof=1))
            if s > 0:
                out[(x["cusip"], x["date"])] = (x["amt"] - m) / s
            elif x["amt"] == m:
                out[(x["cusip"], x["date"])] = 0.0
    return out


def size_rows(panel: dict, clusters: Sequence[dict], zmap: dict, conservative: bool = True) -> list:
    """Per cluster: (z, excess, L) for the size secondary. Window from the close of the announcement day (registered;
    ``conservative``: the first series day AFTER the latest announcement day of the cluster's auctions, because the
    announcement row's available_at is the end of that day, after the close) to the close of t-1; excess = the
    tenor-averaged window minus L x each tenor's mean non-month-end daily return (L = the window's non-month-end
    sessions). Clusters without a z, or with an empty window, are left out."""
    days = panel["days"]
    U, me = panel["U"], panel["me"]
    pos = {t: k for k, t in enumerate(panel["tenors"])}
    ubar = np.array([U[k, ~me].mean() for k in range(U.shape[0])])
    cum = np.concatenate([np.zeros((U.shape[0], 1)), np.cumsum(U, axis=1)], axis=1)
    cnt = np.concatenate([[0], np.cumsum(~me)])
    out = []
    for c in clusters:
        zs = [zmap.get((x["cusip"], x["date"])) for x in c["auctions"]]
        zs = [z for z in zs if z is not None]
        if not zs or not c["ann_last"]:
            continue
        if conservative:
            s0 = bisect.bisect_right(days, c["ann_last"]) - 1 + 1          # first series day after the announcement day
        else:
            s0 = bisect.bisect_right(days, c["ann_last"]) - 1               # the announcement day's close
        e = c["i_t"] - 1
        if s0 < 0 or e <= s0 or e >= len(days):
            continue
        L = int(cnt[e + 1] - cnt[s0 + 1])
        if L < 1:
            continue
        ks = [pos[t] for t in c["tenors"]]
        w = float(np.mean([cum[k, e + 1] - cum[k, s0 + 1] - L * ubar[k] for k in ks]))
        out.append((float(np.mean(zs)), w, L, c["t"]))
    return out


def _flag_mean(vals, dates, span: tuple) -> dict:
    m = [v for v, d in zip(vals, dates) if span[0] <= d <= span[1]]
    return {"n": len(m), "mean_bps": float(np.mean(m) * 1e4) if m else None}


def etf_window_excess(days: Sequence[str], adj, clusters: Sequence[dict], start: str = T589_START, end: str = T589_END,
                      span: int = T589_SPAN) -> dict:
    """Tradeable check: the ETF's total return close t-5 -> close t-1 (its own NYSE sessions; every session, month ends
    included) minus its unconditional 4-session mean over [start, end]."""
    keep = [i for i, d in enumerate(days) if start <= d <= end]
    if len(keep) < 50:
        return {"n": 0}
    ds = [days[i] for i in keep]
    lv = np.asarray(adj, float)[keep]
    R = lv[span:] / lv[:-span] - 1.0
    ev = []
    for c in clusters:
        i = bisect.bisect_left(ds, c["t"])
        a = i - (span + 1)                       # the close of t-5 on this calendar; the window ends at the close of t-1
        if 0 <= a and i < len(ds):
            ev.append(float(lv[a + span] / lv[a] - 1.0))
    if not ev:
        return {"n": 0}
    return {"n": len(ev), "excess": float(np.mean(ev) - R.mean()), "event_mean": float(np.mean(ev)), "uncond": float(R.mean()),
            "t": float((np.mean(ev) - R.mean()) / (np.std(ev, ddof=1) / math.sqrt(len(ev)))) if len(ev) > 2 else None}


def b13_calendar_a_pre_auction_concession(archive):
    """T-589: Treasury pre-auction concession on unseen 2/5/7/20-year auction weeks."""
    need = [AUCT_B, CPI_B] + sorted(set(T589_YIELD.values()))
    miss = _missing(archive, need)
    if miss:
        return miss
    yields = {t: CAL._series(archive, b) for t, b in T589_YIELD.items()}
    panel = synth_panel(yields)
    days = panel["days"]
    auctions, coupon_weeks = t589_auctions(_rows(archive, AUCT_B))
    unseen = t589_clusters(auctions, days, T589_UNSEEN, T589_SEEN)
    seen = t589_clusters(auctions, days, T589_SEEN)
    pool = placement_pool(days, coupon_weeks)
    shift = T589_COST + T589_BAR                       # H0: excess + cost >= -bar  <=>  excess + cost + bar >= 0
    prim = concession_test(panel, unseen, pool, shift)
    n = prim.get("n", 0)
    if n < 4 or prim.get("excess") is None:
        v, why, crit = CAL._judge([("testable auction clusters", None, False)], n, T589_MIN_N, "auction-week clusters")
        return _out({"n_clusters": n}, n, v, f"too few testable clusters ({n}) — {why}")
    ex = prim["excess"]
    net = ex + T589_COST
    # ex-CPI: drop clusters whose window (sessions t-4 .. t-1) holds a CPI release (08:30 ET, inside the window)
    cpi = sorted(_release_days(archive, CPI_B, "cpi"))
    def has_cpi(c):
        lo, hi = days[c["a"]], days[c["i_t"] - 1]
        j = bisect.bisect_right(cpi, lo)
        return j < len(cpi) and cpi[j] <= hi
    ucl = [c for c in unseen if 0 <= c["a"] < len(days) - T589_SPAN]
    excpi = [c for c in ucl if not has_cpi(c)]
    rx = concession_test(panel, excpi, pool, T589_COST, alpha=T589_ALT_ALPHA, split=None)
    rs = concession_test(panel, seen, pool, T589_COST, split=None)
    # size secondary
    zmap = auction_z(auctions)
    srows = size_rows(panel, ucl, zmap, conservative=True)
    srows_reg = size_rows(panel, ucl, zmap, conservative=False)
    size = {"n": len(srows)}
    if len(srows) >= 10:
        z = np.array([r[0] for r in srows]); w = np.array([r[1] for r in srows])
        size = {"n": len(srows), **coef_test(w, z, 0, CAL.nw_lags(len(srows)), 1)}
    size_reg = {"n": len(srows_reg)}
    if len(srows_reg) >= 10:
        z2 = np.array([r[0] for r in srows_reg]); w2 = np.array([r[1] for r in srows_reg])
        size_reg = {"n": len(srows_reg), **coef_test(w2, z2, 0, CAL.nw_lags(len(srows_reg)), 1)}
    hb_size, hb_seen = holm2(size.get("boot_p_less"), rs.get("boot_p_less"))
    hh_size, _ = holm2(size.get("hac_p_less"), rs.get("boot_p_less"))
    hb_size_r, _ = holm2(size_reg.get("boot_p_less"), rs.get("boot_p_less"))
    hh_size_r, _ = holm2(size_reg.get("hac_p_less"), rs.get("boot_p_less"))
    # reported next to the pre-declared net readings: the literal gross bar (excess < -2 bps, no cost) and the
    # period-demeaned excess (each cluster against its own half's unconditional mean; year-stratified placement)
    prim_g = concession_test(panel, unseen, pool, T589_BAR, split=None)
    pdm = period_demeaned_test(panel, unseen, pool, shift)
    # criteria
    c1_ok = _both_nulls(prim, net + T589_BAR)
    c1_dec = (prim.get("boot_p_greater") is not None and _decide(prim["boot_p_greater"], prim["boot_draws"]) is True)
    h = prim.get("halves") or [None, None]
    hn = [None if x is None else x + T589_COST for x in h]
    c2_ok = None if any(x is None for x in hn) else all(x < 0 for x in hn)
    rx_net = None if rx.get("excess") is None else rx["excess"] + T589_COST
    c3_ok = None if rx_net is None else _both_nulls(rx, rx_net, T589_ALT_ALPHA)
    rs_net = None if rs.get("excess") is None else rs["excess"] + T589_COST
    c4_ok = None if rs_net is None else rs_net < 0
    sc, sc_r = size.get("coef"), size_reg.get("coef")
    c5_ok = (None if sc is None or sc_r is None else
             CAL._agree([_hac_ok(sc, hh_size), _sig(sc, hb_size, size.get("boot_draws", 0)),
                         _hac_ok(sc_r, hh_size_r), _sig(sc_r, hb_size_r, size_reg.get("boot_draws", 0))]))
    g_ok = _both_nulls(prim_g, ex + T589_BAR) if prim_g.get("excess") is not None else None
    rows = [
        (f"unseen-week net excess (excess {_bp(ex)} + 2 bps cost = {_bp(net)} bps) < -2 bps with one-sided p < 0.05 under "
         f"both nulls: flags-fixed studentized CBB (block 10) p {_mc(prim.get('boot_p_less'), prim.get('boot_draws', 0))}, "
         f"placement in {prim.get('pool_weeks')} no-coupon-auction weeks p {_mc(prim.get('place_p_less'), prim.get('place_draws', 0))} "
         f"[literal gross reading, reported: excess {_bp(ex)} < -2 bps: CBB p {_mc(prim_g.get('boot_p_less'), prim_g.get('boot_draws', 0))}, "
         f"placement p {_mc(prim_g.get('place_p_less'), prim_g.get('place_draws', 0))}: "
         f"{'passes' if g_ok else 'fails' if g_ok is False else 'undecided'}]",
         c1_ok, c1_dec),
        (f"both halves negative net (2014-2019 {_bp(hn[0])}, 2020-2026 {_bp(hn[1])} bps; n {prim.get('halves_n')}) [gross, "
         f"reported: {_bp(h[0])} / {_bp(h[1])}]", c2_ok, False),
        (f"ex-CPI net excess {_bp(rx_net)} bps negative with p < 0.1 under both nulls ({rx.get('n')} clusters; CBB p "
         f"{_mc(rx.get('boot_p_less'), rx.get('boot_draws', 0))}, placement p {_mc(rx.get('place_p_less'), rx.get('place_draws', 0))})",
         c3_ok, False),
        (f"10/30-year-week secondary (seen in T-442) the same sign: net excess {_bp(rs_net)} bps over {rs.get('n')} clusters", c4_ok, False),
        (f"size slope (concession to t-1 on the offering z-score) negative with Holm-adjusted p < 0.05 over the 2 secondaries, "
         f"on both windows (they must agree): registered window from the announcement-day close {_bp(sc_r)} bps per z over "
         f"{size_reg.get('n')} clusters, HAC t {_f(size_reg.get('t'), 2)}, Holm p HAC {_p(hh_size_r)} / bootstrap {_p(hb_size_r)}; "
         f"archive-stamp window from the next session's close {_bp(sc)} bps per z over {size.get('n')} clusters, HAC t "
         f"{_f(size.get('t'), 2)}, Holm p HAC {_p(hh_size)} / bootstrap {_p(hb_size)}", c5_ok, False),
    ]
    v, why, crit = CAL._judge(CAL._undecided(rows), n, T589_MIN_N, "unseen auction-week clusters")
    # reported
    vals, td = prim["values"], prim["t_dates"]
    fomc = set(_fomc_days(archive)) if _has(archive, FOMC_B) else None
    in_ucl = [c for c in ucl]
    fomc_flag = None
    if fomc is not None:
        fl = np.array([any(days[c["a"]] < d <= days[c["i_t"] - 1] or iso_week(d) == c["week"] for d in fomc) for c in in_ucl])
        fomc_flag = {"n": int(fl.sum()), "net_fomc_bps": float((vals[fl].mean() + T589_COST) * 1e4) if fl.any() else None,
                     "net_other_bps": float((vals[~fl].mean() + T589_COST) * 1e4) if (~fl).any() else None}
    flags = {k: _flag_mean(vals + T589_COST, td, sp) for k, sp in T589_FLAGS.items()}
    reo = np.array([c["reopen_any"] for c in in_ucl])
    reopen = {"n_reopening": int(reo.sum()), "net_reopening_bps": float((vals[reo].mean() + T589_COST) * 1e4) if reo.any() else None,
              "net_new_only_bps": float((vals[~reo].mean() + T589_COST) * 1e4) if (~reo).any() else None}
    comp = defaultdict(list)
    for c, x in zip(in_ucl, vals):
        comp["/".join(map(str, c["tenors"]))].append(x)
    comp = {k: {"n": len(x), "net": float(np.mean(x) + T589_COST)} for k, x in comp.items()}
    etf = {}
    for b in (IEF_B, SHY_B, TLT_B):
        if _has(archive, b):
            dd, adj = CAL._daily(archive, b, "adjclose")
            etf[b[len("daily-history-"):]] = etf_window_excess(dd, adj, in_ucl)
    n3y = sum(1 for c in seen if 3 in c["all_tenors"])
    reason = (f"{len(auctions)} held nominal fixed-coupon auctions (FRNs and TIPS out, reopenings kept); {n} unseen ISO-week "
              f"clusters {td[0]}..{td[-1]} (2/5/7 or 20-year, no 10/30; t = the week's first nominal auction; compositions "
              + ", ".join(f"{k} {v_['n']}" for k, v_ in sorted(comp.items())) + "). 10Y-DV01-scaled synthetic window close t-5 -> "
              f"close t-1 (month-end sessions excluded): cluster mean {_bp(prim.get('event_mean'))} vs unconditional "
              f"{_bp(prim.get('uncond_mean'))}, excess {_bp(ex)} bps gross / {_bp(net)} net of the 2 bps round trip; halves "
              f"net {_bp(hn[0])} / {_bp(hn[1])}; ex-CPI ({rx.get('n')} clusters) net {_bp(rx_net)}; 10/30-year weeks "
              f"({rs.get('n')} clusters, tenors 10 and 30 via DGS20; the week's 3-year auction ({n3y} weeks) has no registered "
              f"series and only sets t) net {_bp(rs_net)}; size slope on the registered announcement-close window "
              f"{_bp(sc_r)} bps per z (n {size_reg.get('n')}) and on the archive-stamp next-session window {_bp(sc)} (n "
              f"{size.get('n')}), decided on both. Literal gross reading (no cost on top of the -2 bps bar; reported): excess "
              f"{_bp(ex)} bps, CBB p {_p(prim_g.get('boot_p_less'))}, placement p {_p(prim_g.get('place_p_less'))}, halves gross "
              f"{_bp(h[0])} / {_bp(h[1])}. Period-demeaned primary (reported; each cluster against its own half's unconditional "
              f"window mean, because {pdm.get('n_by_half', [None, None])[1]} of {pdm.get('n')} clusters fall in 2020-2026): excess "
              f"{_bp(pdm.get('excess'))} gross / {_bp(None if pdm.get('excess') is None else pdm['excess'] + T589_COST)} net, CBB "
              f"(half-demeaned resamples) p {_p(pdm.get('boot_p_less'))}, year-stratified placement p "
              f"{_p(pdm.get('place_p_less'))} (both at the net -2 bps bar). Tradeable checks (gross excess, every session): "
              + ", ".join(f"{k} {_bp(e_.get('excess'))} bps (n {e_.get('n')})" for k, e_ in etf.items())
              + f". Flagged (net bps): clusters with an FOMC decision in the window or week {fomc_flag}; 2020-03 {flags['2020-03']}; "
              f"2022 {flags['2022']}; reopening clusters {reopen}. Unconditional means use every 4-session window 2014-01..2026-10")
    stat = {"n_clusters": n, "excess_bps": ex * 1e4, "net_excess_bps": net * 1e4, "event_mean_bps": prim["event_mean"] * 1e4,
            "uncond_mean_bps": prim["uncond_mean"] * 1e4,
            "boot_p_less": prim.get("boot_p_less"), "boot_draws": prim.get("boot_draws"), "place_p_less": prim.get("place_p_less"),
            "place_draws": prim.get("place_draws"), "pool_weeks": prim.get("pool_weeks"),
            "halves_net_bps": [None if x is None else x * 1e4 for x in hn],
            "ex_cpi": {"n": rx.get("n"), "net_bps": None if rx_net is None else rx_net * 1e4, "boot_p_less": rx.get("boot_p_less"),
                       "place_p_less": rx.get("place_p_less")},
            "seen_10_30": {"n": rs.get("n"), "net_bps": None if rs_net is None else rs_net * 1e4, "boot_p_less": rs.get("boot_p_less"),
                           "place_p_less": rs.get("place_p_less")},
            "size": {k: size.get(k) for k in ("n", "coef", "t", "hac_p_less", "boot_p_less", "boot_draws")} | {"holm_hac": hh_size, "holm_boot": hb_size},
            "size_registered_window": {k: size_reg.get(k) for k in ("n", "coef", "t", "hac_p_less", "boot_p_less", "boot_draws")}
            | {"holm_hac": hh_size_r, "holm_boot": hb_size_r},
            "gross_reading": {"excess_bps": ex * 1e4, "boot_p_less": prim_g.get("boot_p_less"), "place_p_less": prim_g.get("place_p_less"),
                              "draws": [prim_g.get("boot_draws"), prim_g.get("place_draws")], "halves_gross_bps": [None if x is None else x * 1e4 for x in h],
                              "primary_ok": g_ok},
            "period_demeaned": {k: (pdm.get(k) * 1e4 if k == "excess" and pdm.get(k) is not None else pdm.get(k))
                                for k in ("n", "excess", "n_by_half", "boot_p_less", "boot_draws", "place_p_less", "place_draws", "pool_weeks_by_year")},
            "compositions": comp, "etf_checks": etf, "fomc_flag": fomc_flag, "flags": flags, "reopening": reopen,
            "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ================================================================================ T-592 put-write weekend decay ==

def roll_sessions(first: str, last: str, weekly: bool) -> list:
    """Roll sessions of a put-write index: monthly (PUT, PUTY) each month's third Friday, weekly (WPUT) every Friday; when
    the exchange is closed that day, the last session before it (the realised calendar)."""
    a, b = _d(first) - timedelta(days=40), _d(last) + timedelta(days=40)
    out = set()
    if weekly:
        d = a - timedelta(days=(a.weekday() - 4) % 7)
        while d <= b:
            s = d
            while not CAL.is_nyse_session(s):
                s -= timedelta(days=1)
            out.add(s.isoformat())
            d += timedelta(days=7)
    else:
        y, m = a.year, a.month
        while date(y, m, 1) <= b:
            s = BW.third_friday(y, m)
            while not CAL.is_nyse_session(s):
                s -= timedelta(days=1)
            out.add(s.isoformat())
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return sorted(out)


def rolling_beta(ex: np.ndarray, gx: np.ndarray, win: int = T592_BETA_WIN) -> np.ndarray:
    """beta[i] = OLS slope (with intercept) of ex on gx over intervals i-win .. i-1 (prior intervals only); NaN for the
    first ``win`` intervals."""
    n = ex.size
    out = np.full(n, np.nan)
    if n <= win:
        return out
    c = lambda x: np.concatenate([[0.0], np.cumsum(x)])
    Sx, Sy, Sxx, Sxy = c(gx), c(ex), c(gx * gx), c(gx * ex)
    i = np.arange(win, n)
    sx, sy = Sx[i] - Sx[i - win], Sy[i] - Sy[i - win]
    sxx, sxy = Sxx[i] - Sxx[i - win], Sxy[i] - Sxy[i - win]
    den = win * sxx - sx * sx
    out[win:] = np.where(den > 0, (win * sxy - sx * sy) / np.where(den > 0, den, 1.0), np.nan)
    return out


def put_intervals(idx: dict, gspc: dict, bills, live_from: str, weekly: bool, beta_win: int = T592_BETA_WIN,
                  min_dte: int = T592_MIN_DTE) -> dict:
    """Intervals between consecutive LIVE closes of a put-write index (back-tested rows never enter, not even in the
    betas): residual = index return - bill accrual over the interval's calendar days (``batch6b_bw.Bills``) - beta x
    (^GSPC return - the same accrual), beta from the prior ``beta_win`` intervals. Labels: weekend (Fri -> Mon, 3 calendar
    days), weekday (Mon-Tue .. Thu-Fri, 1 calendar day), holiday-spanning (a closed weekday inside); exclusions
    (``excluded``, the primary reading): ends on a roll session (the Thu-Fri into the roll), starts on a roll session
    (the roll day; monthly indices only: WPUT's registered 'first weekend of each weekly put' is the Fri -> Mon starting
    on its roll, so it is waived there), held put under ``min_dte`` calendar days to expiry at the interval's end
    (monthly indices only: a weekly put always is), next to a closure. ``excluded_end_only`` is the pre-review reading
    (only the interval ending on the roll session), reported as a sensitivity."""
    close, bt = idx["close"], idx["backtest"]
    days = sorted(d for d in close if d >= live_from and not bt.get(d, True))
    rows = []
    for d0, d1 in zip(days[:-1], days[1:]):
        if d0 not in gspc or d1 not in gspc:
            continue
        g = bills.growth(d0, d1) - 1.0
        rows.append((d0, d1, close[d1] / close[d0] - 1.0 - g, gspc[d1] / gspc[d0] - 1.0 - g))
    out = {"n": len(rows)}
    if not rows:
        return out
    d0 = [r[0] for r in rows]; d1 = [r[1] for r in rows]
    ex = np.array([r[2] for r in rows]); gx = np.array([r[3] for r in rows])
    beta = rolling_beta(ex, gx, beta_win)
    rolls = roll_sessions(d0[0], d1[-1], weekly)
    rset = set(rolls)
    cal = np.array([(_d(b) - _d(a)).days for a, b in zip(d0, d1)])
    wd0 = np.array([_d(a).weekday() for a in d0])
    weekend = (wd0 == 4) & (cal == 3)
    weekday = (cal == 1) & (wd0 <= 3)
    spans = np.array([any(_closed_weekday(_d(a) + timedelta(days=k)) for k in range(1, c)) for a, c in zip(d0, cal)])
    roll_end = np.array([b in rset for b in d1])
    roll_start = np.array([a in rset for a in d0])
    roll_start_x = np.zeros(len(rows), bool) if weekly else roll_start      # WPUT waiver: its Fri -> Mon starts on every roll
    if weekly:
        dte = np.full(len(rows), 99)
    else:
        dte = np.array([(_d(rolls[bisect.bisect_right(rolls, a)]) - _d(b)).days if bisect.bisect_right(rolls, a) < len(rolls) else 99
                        for a, b in zip(d0, d1)])
    short = dte < min_dte
    hol = np.array([holiday_adjacent(a) or holiday_adjacent(b) for a, b in zip(d0, d1)])
    out.update(d0=d0, d1=d1, ex=ex, gx=gx, beta=beta, resid=ex - beta * gx, weekend=weekend, weekday=weekday, spans=spans,
               roll_end=roll_end, roll_start=roll_start, roll_start_excluded=roll_start_x, short_dte=short, hol_adj=hol,
               excluded=roll_end | roll_start_x | short | hol, excluded_end_only=roll_end | short | hol, dte=dte)
    return out


def weekend_test(iv: dict, start: str, end: str, split: Optional[str] = T592_SPLIT, mult: float = T592_MULT,
                 block: int = T592_BLOCK, pvals: bool = True, n_boot: int = N_BOOT, seed: int = SEED,
                 excl: str = "excluded") -> dict:
    """D = mean weekend residual - mult x mean weekday residual over the kept intervals in [start, end] (by the interval's
    start day; ``excl`` names the exclusion mask: the primary reading or ``excluded_end_only``), its studentized
    circular block bootstrap of ISO-week clusters (``block`` weeks; the linearised series whose mean is D) and the
    halves. Exclusion counts overlap (an interval can meet several rules)."""
    if not iv.get("n"):
        return {"n_weekend": 0}
    d0 = np.array(iv["d0"])
    inr = (d0 >= start) & (d0 <= end) & np.isfinite(iv["beta"])
    keep = inr & ~iv[excl]
    wk, wdy = keep & iv["weekend"], keep & iv["weekday"]
    typed = inr & (iv["weekend"] | iv["weekday"])
    rs = iv["roll_start_excluded"] if excl == "excluded" else np.zeros(d0.size, bool)
    out = {"n_weekend": int(wk.sum()), "n_weekday": int(wdy.sum()),
           "n_excluded": {"roll_end": int((typed & iv["roll_end"]).sum()), "roll_start": int((typed & rs).sum()),
                          "roll_start_only": int((typed & rs & ~iv["excluded_end_only"]).sum()),
                          "short_dte": int((typed & iv["short_dte"]).sum()),
                          "holiday_adjacent": int((typed & iv["hol_adj"]).sum()),
                          "roll_end_not_short_dte": int((typed & iv["roll_end"] & ~iv["short_dte"]).sum())}}
    if wk.sum() < 2 or wdy.sum() < 2:
        return out
    r = iv["resid"]
    mw, md = float(r[wk].mean()), float(r[wdy].mean())
    D = mw - mult * md
    out.update(mean_weekend=mw, mean_weekday=md, D=D, ratio=(mw / md) if md != 0 else None,
               mean_weekend_raw_ex=float(iv["ex"][wk].mean()), mean_weekday_raw_ex=float(iv["ex"][wdy].mean()))
    sel = wk | wdy
    x, f = r[sel], wk[sel]
    pw = f.mean()
    z = D + np.where(f, (x - mw) / pw, -mult * (x - md) / (1.0 - pw))
    groups = np.array([iso_week(d)[0] * 100 + iso_week(d)[1] for d in d0[sel]])
    if pvals:
        pg, pl, dr = B7C.cluster_p(z, groups, n_boot, seed, N_SEEDS, block)
        out.update(p_greater=pg, p_less=pl, draws=dr)
    if split:
        hv = []
        for m in (d0 < split, d0 >= split):
            a, b = wk & m, wdy & m
            hv.append(float(r[a].mean() - mult * r[b].mean()) if a.sum() >= 2 and b.sum() >= 2 else None)
        out["halves"] = hv
    return out


def b13_calendar_a_putwrite_weekend(archive):
    """T-592: Cboe PUT weekend residual decay vs 1.5 x the single-weekday residual."""
    miss = _missing(archive, [PUT_B, WPUT_B, GSPC_B, DTB3_B])
    if miss:
        return miss
    bills = BW.Bills(CAL._series(archive, DTB3_B))
    gd, gc = CAL._daily(archive, GSPC_B, "close")
    gspc = dict(zip(gd, (float(x) for x in gc)))
    res = {}
    for sym, b in (("PUT", PUT_B), ("WPUT", WPUT_B), ("PUTY", PUTY_B)):
        if not _has(archive, b):
            continue
        iv = put_intervals(BW.cboe_index(archive, sym), gspc, bills, T592_LIVE[sym], weekly=(sym == "WPUT"))
        res[sym] = (iv, weekend_test(iv, T592_LIVE[sym], T592_END, T592_SPLIT if sym == "PUT" else None, pvals=(sym != "PUTY")))
    iv, P = res["PUT"]
    W = res["WPUT"][1]
    n = P.get("n_weekend", 0)
    if P.get("D") is None or W.get("D") is None:
        v, why, crit = CAL._judge([("PUT and WPUT weekend and weekday intervals", None, False)], n, T592_MIN_N, "PUT weekend intervals")
        return _out({"n_weekend": n}, n, v, f"too few kept intervals — {why}")

    def t592_rows(Pr):
        hp_, hw_ = holm2(Pr.get("p_greater"), W.get("p_greater"))
        h_ = Pr.get("halves") or [None, None]
        rows_ = [
            (f"PUT D = weekend {_bp(Pr['mean_weekend'])} - 1.5 x weekday {_bp(Pr['mean_weekday'])} = {_bp(Pr['D'])} bps > 0 with "
             f"one-sided p < 0.05 after Holm over PUT and WPUT (raw p {_mc(Pr.get('p_greater'), Pr.get('draws', 0))}, Holm "
             f"{_p(hp_)}; studentized CBB of ISO weeks, 4-week blocks)", _sig(Pr["D"], hp_, Pr.get("draws", 0), "greater"),
             Pr.get("p_less") is not None and _decide(Pr["p_less"], Pr["draws"]) is True),
            (f"PUT both halves positive (2007-06..2016-12 {_bp(h_[0])}, 2017-01..2026-10 {_bp(h_[1])} bps)",
             None if any(x is None for x in h_) else all(x > 0 for x in h_), False),
            (f"WPUT live (2015-08-03 on) D the same sign: {_bp(W['D'])} bps (weekend {_bp(W['mean_weekend'])}, weekday "
             f"{_bp(W['mean_weekday'])}; {W['n_weekend']} weekends; raw p {_p(W.get('p_greater'))}, Holm {_p(hw_)})", W["D"] > 0, False),
        ]
        return rows_, hp_, hw_, h_

    rows, hp, hw, h = t592_rows(P)
    v, why, crit = CAL._judge(CAL._undecided(rows), n, T592_MIN_N, "PUT weekend intervals")
    # sensitivity: the pre-review reading (only the interval ending on the roll session excluded; for PUT every such
    # interval is also under 10 days to expiry, so the roll clause removes nothing under it)
    PE = weekend_test(iv, T592_LIVE["PUT"], T592_END, T592_SPLIT, excl="excluded_end_only")
    sens = {"n_weekend": PE.get("n_weekend", 0)}
    if PE.get("D") is not None:
        rows_e, hp_e, _, h_e = t592_rows(PE)
        v_e, why_e, _ = CAL._judge(CAL._undecided(rows_e), PE["n_weekend"], T592_MIN_N, "PUT weekend intervals")
        sens.update(D=PE["D"], p_greater=PE.get("p_greater"), draws=PE.get("draws"), holm=hp_e, halves=h_e, verdict=v_e,
                    n_weekday=PE.get("n_weekday"), n_excluded=PE.get("n_excluded"))
    # reported
    Y = res.get("PUTY", (None, {}))[1]
    YE = (weekend_test(res["PUTY"][0], T592_LIVE["PUTY"], T592_END, None, pvals=False, excl="excluded_end_only")
          if "PUTY" in res else {})
    d0 = np.array(iv["d0"]); r = iv["resid"]
    inr = (d0 >= T592_START) & np.isfinite(iv["beta"])
    holi = inr & iv["spans"] & ~iv["roll_end"] & ~iv["roll_start_excluded"] & ~iv["short_dte"]
    hol_mean = float(r[holi].mean()) if holi.any() else None
    nfp = set(_release_days(archive, NFP_B, "employment")) if _has(archive, NFP_B) else set()
    keep = inr & ~iv["excluded"] & iv["weekend"]
    mon = np.array([b in nfp for b in iv["d1"]]) & keep
    ne = P["n_excluded"]
    reason = (f"PUT live marks {iv['d0'][0]}..{iv['d1'][-1]} ({iv['n']} intervals between consecutive Cboe closes; the first "
              f"{T592_BETA_WIN} live intervals only seed the beta): kept {P['n_weekend']} Fri->Mon and {P['n_weekday']} single-weekday "
              f"intervals. Roll exclusion read (at review, after the builder's run) as BOTH intervals next to each third-Friday "
              f"roll session for PUT/PUTY: the one ending on it (the Thu-Fri into the roll) and the one starting on it (the roll "
              f"day); WPUT keeps its Fri->Mon (its registered 'first weekend of each weekly put') under an explicit WPUT-only "
              f"waiver, as for the DTE rule. Excluded (overlapping) {ne}: every interval ending on a PUT roll is also under 10 "
              f"days to expiry ({ne['roll_end_not_short_dte']} are not), so only the roll-day clause removes anything "
              f"({ne['roll_start_only']} weekends). Residual = return - DTB3 calendar-day accrual - trailing-60 beta x ^GSPC "
              f"excess. Mean weekend residual {_bp(P['mean_weekend'])} bps, weekday {_bp(P['mean_weekday'])} bps (ratio "
              f"{_f(P.get('ratio'), 2)}; raw excess {_bp(P['mean_weekend_raw_ex'])} / {_bp(P['mean_weekday_raw_ex'])}), D "
              f"{_bp(P['D'])} bps, p {_p(P.get('p_greater'))} (p_less {_p(P.get('p_less'))}); halves {_bp(h[0])} / {_bp(h[1])}. "
              f"THE VERDICT DEPENDS ON THE ROLL READING: under the pre-review reading (only the interval ending on the roll "
              f"session excluded, which is vacuous for PUT) {sens.get('n_weekend')} weekends, D {_bp(sens.get('D'))} bps, p "
              f"{_p(sens.get('p_greater'))} (Holm {_p(sens.get('holm'))}), halves {_bp((sens.get('halves') or [None])[0])} / "
              f"{_bp((sens.get('halves') or [None, None])[1])}: {sens.get('verdict')} (sensitivity, not the verdict). WPUT (live, "
              f"weekly roll every Friday; the < 10-day rule cannot apply to a one-week put, theta-acceleration caveat) D "
              f"{_bp(W['D'])} bps over {W['n_weekend']} weekends / {W['n_weekday']} weekdays. Reported: PUTY live (2019-02-15 on) D "
              f"{_bp(Y.get('D'))} bps ({Y.get('n_weekend')} weekends, weekend {_bp(Y.get('mean_weekend'))} / weekday "
              f"{_bp(Y.get('mean_weekday'))}; pre-review reading {_bp(YE.get('D'))} over {YE.get('n_weekend')}); PUT "
              f"pre-holiday-to-post-holiday intervals {int(holi.sum())}, mean residual {_bp(hol_mean)} bps; kept weekends ending "
              f"on an Employment Situation Monday {int(mon.sum())} (mean {_bp(float(r[mon].mean()) if mon.any() else None)}). "
              f"Index marks carry no costs: a pass would be a premium estimate, not a net trade")
    slim = lambda d: {k: d.get(k) for k in ("n_weekend", "n_weekday", "n_excluded", "mean_weekend", "mean_weekday", "D", "ratio",
                                            "p_greater", "p_less", "draws", "halves")}
    stat = {"PUT": slim(P), "WPUT": slim(W), "PUTY": slim(Y), "holm_put": hp, "holm_wput": hw,
            "roll_reading": "both intervals next to each monthly roll session excluded (PUT/PUTY); WPUT Fri->Mon waived",
            "sensitivity_end_only_reading": sens, "PUTY_end_only": slim(YE),
            "holiday_intervals": {"n": int(holi.sum()), "mean": hol_mean}, "nfp_monday_weekends": int(mon.sum()), "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ================================================================================ T-582 HVIX next-session premium ==

def vix_spikes(vix: dict, decay: float = T582_DECAY, thr: float = T582_THR) -> dict:
    """{day: (spike, excess)}: excess(t) = VIX(t) - mu(t-1), mu(t-1) = (1 - decay) sum_k decay^k VIX(t-1-k) over the VIX
    history (eq. 7; the sum truncated at the first print), spike = excess >= thr. Uses closes through t only."""
    ds = sorted(vix)
    v = np.array([vix[d] for d in ds], float)
    out = {}
    m = 0.0                                  # mu through the previous print; the empty sum before the first
    for i, d in enumerate(ds):
        if i > 0:
            e = float(v[i] - m)
            out[d] = (bool(e >= thr), e)
        m = (1.0 - decay) * v[i] + decay * m
    return out


def expanding_deciles(r, min_hist: int = T582_DEC_MIN) -> np.ndarray:
    """d[i] in 0..9: the decile of r[i] against cutoffs (linear-interpolation quantiles 0.1 .. 0.9) of r[0 .. i-1] (past
    returns only); -1 with fewer than ``min_hist`` finite prior returns or a non-finite r[i]."""
    r = np.asarray(r, float)
    out = np.full(r.size, -1, int)
    srt: list = []
    qs = np.arange(1, 10) / 10.0
    for i, x in enumerate(r):
        m = len(srt)
        if m >= min_hist and np.isfinite(x):
            pos = qs * (m - 1)
            lo = np.floor(pos).astype(int)
            hi = np.minimum(lo + 1, m - 1)
            fr = pos - lo
            cut = [srt[a] * (1 - f) + srt[b] * f for a, b, f in zip(lo, hi, fr)]
            out[i] = int(np.searchsorted(cut, x, side="right"))
        if np.isfinite(x):
            bisect.insort(srt, float(x))
    return out


def hvix_frame(bars, spikes: dict, dec_from: str = T582_DEC_FROM, dec_min: int = T582_DEC_MIN) -> dict:
    """Per session t of the ETF (rows with a VIX print on t and a next session t+1): the spike flag and VIX excess of t,
    the expanding decile of the day-t close-to-close total return (cutoffs from returns dated from ``dec_from`` through
    t-1), IBS(t), and the outcomes of t+1: open -> close (o2c) and close(t) -> open(t+1) with the ex-dividend cash."""
    days = list(bars.days)
    n = len(days)
    adj, op, cl, hi, lo = bars.adj, bars.open, bars.close, bars.high, bars.low
    c2c = np.full(n, np.nan); c2c[1:] = adj[1:] / adj[:-1] - 1.0
    c2c_d = np.where(np.array(days) >= dec_from, c2c, np.nan)
    dec = expanding_deciles(c2c_d, dec_min)
    div = OHLC.ex_dividends(cl, adj)
    rng_ = hi - lo
    ibs = np.where(rng_ > 0, (cl - lo) / np.where(rng_ > 0, rng_, 1.0), np.nan)
    rows = {"day": [], "spike": [], "vex": [], "dec": [], "ibs": [], "y": [], "on": [], "c2c": [], "i": []}
    for i in range(n - 1):
        s = spikes.get(days[i])
        if s is None:
            continue
        rows["day"].append(days[i]); rows["spike"].append(s[0]); rows["vex"].append(s[1]); rows["dec"].append(int(dec[i]))
        rows["ibs"].append(float(ibs[i])); rows["c2c"].append(float(c2c[i])); rows["i"].append(i)
        rows["y"].append(float(cl[i + 1] / op[i + 1] - 1.0))
        rows["on"].append(float(op[i + 1] / cl[i] - 1.0 + div[i + 1] / cl[i]))
    out = {k: np.array(v) for k, v in rows.items()}
    out["day"] = np.array(rows["day"], dtype=object).astype(str)
    return out


def matched_diff(y, ev, dec) -> dict:
    """Decile-matched difference: mean over events of (y_e - mean y of the non-event days in e's decile), its linearised
    per-day series z (mean z = the difference; events weigh (y - c_d) N / K, controls -(K_d / K)(y - c_d) N / N_d) and
    the counts. Events whose decile has no control are dropped."""
    y = np.asarray(y, float); ev = np.asarray(ev, bool); dec = np.asarray(dec, int)
    ok = (dec >= 0) & np.isfinite(y)
    c, nk = {}, {}
    for k in range(10):
        m = ok & ~ev & (dec == k)
        if m.any():
            c[k] = float(y[m].mean()); nk[k] = int(m.sum())
    use = ok & (~ev | np.isin(dec, list(c)))
    e = use & ev
    K, N = int(e.sum()), int(use.sum())
    if K == 0:
        return {"K": 0}
    cd = np.array([c.get(int(k), np.nan) for k in dec])
    diff = float((y[e] - cd[e]).mean())
    z = np.zeros(y.size)
    z[e] = (y[e] - cd[e]) * N / K
    for k in c:
        m = use & ~ev & (dec == k)
        kk = int((e & (dec == k)).sum())
        z[m] = -(kk / K) * (y[m] - c[k]) * N / nk[k]
    return {"K": K, "N": N, "diff": diff, "z": z[use], "use": use, "event_mean": float(y[e].mean()),
            "control_mean": float(cd[e].mean()), "uncond_mean": float(y[use].mean()), "dropped": int((ok & ev).sum() - K)}


def stationary_idx(rng, n: int, mean_block: float, k: int) -> np.ndarray:
    """(k, n) Politis-Romano stationary-bootstrap indices: circular runs of consecutive units with geometric lengths of
    mean ``mean_block`` (``batch4_carry._stationary_idx``, vectorised over draws)."""
    idx = np.empty((k, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, k)
    new = rng.random((k, n)) < 1.0 / max(float(mean_block), 1.0)
    jump = rng.integers(0, n, (k, n))
    for t in range(1, n):
        idx[:, t] = np.where(new[:, t], jump[:, t], idx[:, t - 1] + 1)
    return idx % n


def stationary_cluster_boot(x, groups, n_boot: int, seed: int, mean_block: float) -> tuple:
    """``batch7_cal.cluster_boot`` with the clusters (sorted, i.e. chronological for 'YYYY-MM' labels) drawn as a
    stationary bootstrap of consecutive clusters (geometric run lengths, mean ``mean_block``) instead of i.i.d.:
    studentized (p_greater, p_less) of the ratio mean of x; (None, None) below 8 clusters."""
    x = np.asarray(x, float)
    _, inv = np.unique(np.asarray(groups), return_inverse=True)
    S = np.bincount(inv, weights=x)
    N = np.bincount(inv).astype(float)
    G = S.size
    if G < 8:
        return None, None
    m = S.sum() / N.sum()

    def se(Sm, Nm, mm):
        e = Sm - mm[:, None] * Nm
        return np.sqrt(G / (G - 1) * (e ** 2).sum(axis=1)) / Nm.sum(axis=1)

    s0 = float(se(S[None], N[None], np.array([m]))[0])
    if not s0 > 0:
        return None, None
    idx = stationary_idx(np.random.default_rng(seed), G, mean_block, n_boot)
    Sb, Nb = S[idx], N[idx]
    mb = Sb.sum(axis=1) / Nb.sum(axis=1)
    sb = se(Sb, Nb, mb)
    ok = sb > 0
    tb = (mb[ok] - m) / sb[ok]
    t0 = m / s0
    return float((np.sum(tb >= t0) + 1) / (tb.size + 1)), float((np.sum(tb <= t0) + 1) / (tb.size + 1))


def hvix_test(fr: dict, span: tuple, shift: float, pvals: bool = True, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """``matched_diff`` on the rows with t in ``span``; p of H0 mean(z) - shift <= 0 by two studentized bootstraps of
    calendar-month clusters: drawn i.i.d. (``batch7_cal.cluster_p``; p_greater / p_less) and as the registered
    stationary bootstrap of consecutive months (mean block ``T582_MEAN_BLOCK`` months; st_p_greater / st_p_less)."""
    m = (fr["day"] >= span[0]) & (fr["day"] <= span[1])
    md = matched_diff(fr["y"][m], fr["spike"][m], fr["dec"][m])
    if md.get("K", 0) == 0:
        return md
    if pvals:
        months = np.array([d[:7] for d in fr["day"][m][md["use"]]])
        zs = md["z"] - shift
        pg, pl, dr = B7C.cluster_p(zs, months, n_boot, seed, N_SEEDS, 1)
        md.update(p_greater=pg, p_less=pl, draws=dr)
        sg, sl, sdr = _escalate(lambda k: stationary_cluster_boot(zs, months, n_boot, seed + k, T582_MEAN_BLOCK), n_boot)
        md.update(st_p_greater=sg, st_p_less=sl, st_draws=sdr)
    return md


def declustered(fr: dict, gap: int = T582_DECLUSTER) -> np.ndarray:
    """Spike flags with every event that follows any earlier event within ``gap`` sessions removed (past events only)."""
    sp = fr["spike"].astype(bool)
    idx = fr["i"]
    out = sp.copy()
    last = -10 ** 9
    for k in range(sp.size):
        if sp[k]:
            if idx[k] - last <= gap:
                out[k] = False
            last = idx[k]
    return out


def b13_calendar_a_hvix_next_session(archive):
    """T-582: SPY t+1 open-to-close after VIX-over-EWMA spike days vs decile-matched controls."""
    miss = _missing(archive, [VIX_B, SPY_B, QQQ_B, IWM_B])
    if miss:
        return miss
    spikes = vix_spikes(CAL._series(archive, VIX_B))
    frames = {s: hvix_frame(OHLC._bars(archive, s), spikes) for s in ("SPY", "QQQ", "IWM")}
    F = frames["SPY"]
    shift = T582_COST + T582_BAR
    P = hvix_test(F, T582_HOLD, shift)
    n = P.get("K", 0)
    if n == 0:
        return _out({"n_events": 0}, 0, "inconclusive", "no HVIX event in the holdout")
    net = P["diff"] - T582_COST
    halves = [hvix_test(F, sp, 0.0, pvals=False) for sp in T582_HALVES]
    hn = [None if h.get("K", 0) == 0 else h["diff"] - T582_COST for h in halves]
    raw = P["event_mean"] - T582_COST - P["uncond_mean"]
    sec = {s: hvix_test(frames[s], T582_HOLD, T582_COST) for s in ("QQQ", "IWM")}
    hq, hi_ = holm2(sec["QQQ"].get("p_greater"), sec["IWM"].get("p_greater"))
    hq_s, hi_s = holm2(sec["QQQ"].get("st_p_greater"), sec["IWM"].get("st_p_greater"))
    sec_net = {s: sec[s].get("diff", np.nan) - T582_COST for s in ("QQQ", "IWM")}
    oks = [CAL._agree([_sig(sec_net[s], hp, sec[s].get("draws", 0), "greater"),
                       _sig(sec_net[s], hs, sec[s].get("st_draws", 0), "greater")])
           for s, hp, hs in (("QQQ", hq, hq_s), ("IWM", hi_, hi_s))]
    sign_only = all(np.isfinite(sec_net[s]) and sec_net[s] > 0 for s in ("QQQ", "IWM"))
    prim_ok = CAL._agree([_sig(net - T582_BAR, P.get("p_greater"), P.get("draws", 0), "greater"),
                          _sig(net - T582_BAR, P.get("st_p_greater"), P.get("st_draws", 0), "greater")])
    prim_dec = (P.get("p_less") is not None and P.get("st_p_less") is not None and _decide(P["p_less"], P["draws"]) is True
                and _decide(P["st_p_less"], P["st_draws"]) is True)
    rows = [
        (f"holdout net matched difference ({_bp(P['diff'])} - 2 bps cost = {_bp(net)} bps) > 2 bps with one-sided p < 0.05 "
         f"under both month-cluster studentized bootstraps (they must agree): stationary blocks of months (mean "
         f"{T582_MEAN_BLOCK:g}) p {_mc(P.get('st_p_greater'), P.get('st_draws', 0))}, i.i.d. months p "
         f"{_mc(P.get('p_greater'), P.get('draws', 0))}", prim_ok, prim_dec),
        (f"both holdout halves positive net (2018-06..2022-08 {_bp(hn[0])} bps over {halves[0].get('K')} events, "
         f"2022-09..2026-10 {_bp(hn[1])} over {halves[1].get('K')})", None if any(x is None for x in hn) else all(x > 0 for x in hn), False),
        (f"raw net HVIX mean above the unconditional open-to-close mean ({_bp(P['event_mean'])} - 2 bps vs {_bp(P['uncond_mean'])}: "
         f"{_bp(raw)} bps)", raw > 0, False),
        (f"QQQ and IWM the same sign after Holm over 2, read as both positive with Holm-adjusted p < 0.05 under both "
         f"bootstraps (net {_bp(sec_net['QQQ'])} / {_bp(sec_net['IWM'])} bps; Holm p i.i.d. months {_p(hq)} / {_p(hi_)}, "
         f"stationary {_p(hq_s)} / {_p(hi_s)}) [sign-only reading, reported: both net positive "
         f"{'yes' if sign_only else 'no'}; 'after Holm' has content only under the significance reading]",
         B7C._count_crit(oks, 2), False),
    ]
    rows = CAL._undecided(rows)
    if n < T582_MIN_N:
        v, why, crit = "inconclusive", (f"only {n} holdout events, below the registered 40: inconclusive by registration"), [(r[0], r[1]) for r in rows]
    else:
        v, why, crit = CAL._judge(rows, n, T582_MIN_N, "holdout HVIX events")
    # reported
    m = (F["day"] >= T582_HOLD[0]) & (F["day"] <= T582_HOLD[1])
    dc = declustered(F)
    Fd = dict(F); Fd["spike"] = dc
    D = hvix_test(Fd, T582_HOLD, T582_COST, pvals=False)
    on = matched_diff(F["on"][m], F["spike"][m], F["dec"][m])
    ev = F["spike"].astype(bool) & m
    lowibs = (F["ibs"] < T582_IBS) & m
    ibs_sec = (float(F["y"][ev & lowibs].mean() - F["y"][lowibs & ~F["spike"].astype(bool)].mean())
               if (ev & lowibs).any() and (lowibs & ~F["spike"].astype(bool)).any() else None)
    paper = hvix_test(F, T582_PAPER, 0.0, pvals=False)
    flags = {}
    for k, sp in (("2020-03", ("2020-03-01", "2020-03-31")), ("2022", ("2022-01-01", "2022-12-31"))):
        mm = ev & (F["day"] >= sp[0]) & (F["day"] <= sp[1])
        flags[k] = {"n": int(mm.sum()), "net_mean_bps": float((F["y"][mm].mean() - T582_COST) * 1e4) if mm.any() else None}
    tr = {s: frames[s]["y"][frames[s]["spike"].astype(bool) & (frames[s]["day"] >= T582_HOLD[0]) & (frames[s]["day"] <= T582_HOLD[1])]
          - T582_COST for s in frames}
    srs = [float(x.mean() / x.std(ddof=1)) for x in tr.values() if x.size > 2 and x.std(ddof=1) > 0]
    dsr = OHLC._dsr(tr["SPY"], 3, srs) if tr["SPY"].size > 2 else None
    reason = (f"VIX close minus its EWMA through t-1 (decay 0.3, from 1990) >= 3.0 points: {int(ev.sum())} SPY holdout events "
              f"(2018-06..2026-10; {P.get('dropped', 0)} without a control decile). SPY t+1 open->close: events "
              f"{_bp(P['event_mean'])} bps vs their decile-matched controls {_bp(P['control_mean'])} (expanding deciles of the day-t "
              f"close-to-close return from 1993, past returns only): difference {_bp(P['diff'])} gross / {_bp(net)} net of 2 bps; "
              f"halves net {_bp(hn[0])} / {_bp(hn[1])}; raw net minus unconditional {_bp(raw)}; QQQ net "
              f"{_bp(sec['QQQ'].get('diff', np.nan) - T582_COST)} ({sec['QQQ'].get('K')} events), IWM "
              f"{_bp(sec['IWM'].get('diff', np.nan) - T582_COST)} ({sec['IWM'].get('K')}). Reported: de-clustered "
              f"(events within 5 sessions after a prior event dropped) {D.get('K')} events, net {_bp(D.get('diff', np.nan) - T582_COST)} "
              f"bps; HVIX & IBS<0.2 minus IBS<0.2 alone {_bp(ibs_sec)} bps ({int((ev & lowibs).sum())} of {int(ev.sum())} events "
              f"have IBS<0.2: the T-332 overlap); close(t)->open(t+1) leg (not tradeable) matched {_bp(on.get('diff'))} bps; "
              f"in-paper 2000-01..2018-05 matched {_bp(paper.get('diff'))} bps gross over {paper.get('K')} events; flagged "
              f"{flags}; DSR of the SPY event trade over 3 tickers {_f(dsr, 3)}")
    stat = {"n_events": n, "diff_bps": P["diff"] * 1e4, "net_bps": net * 1e4, "event_mean_bps": P["event_mean"] * 1e4,
            "control_mean_bps": P["control_mean"] * 1e4, "uncond_mean_bps": P["uncond_mean"] * 1e4, "p_greater": P.get("p_greater"),
            "draws": P.get("draws"), "stationary_p_greater": P.get("st_p_greater"), "stationary_draws": P.get("st_draws"),
            "stationary_mean_block_months": T582_MEAN_BLOCK,
            "halves_net_bps": [None if x is None else x * 1e4 for x in hn], "raw_net_minus_uncond_bps": raw * 1e4,
            "QQQ": {"K": sec["QQQ"].get("K"), "net_bps": sec_net["QQQ"] * 1e4, "p": sec["QQQ"].get("p_greater"), "holm": hq,
                    "stationary_p": sec["QQQ"].get("st_p_greater"), "stationary_holm": hq_s},
            "IWM": {"K": sec["IWM"].get("K"), "net_bps": sec_net["IWM"] * 1e4, "p": sec["IWM"].get("p_greater"), "holm": hi_,
                    "stationary_p": sec["IWM"].get("st_p_greater"), "stationary_holm": hi_s},
            "qqq_iwm_sign_only_reading": sign_only,
            "declustered": {"K": D.get("K"), "net_bps": (D.get("diff", np.nan) - T582_COST) * 1e4},
            "ibs_secondary_bps": None if ibs_sec is None else ibs_sec * 1e4, "overnight_matched_bps": None if on.get("diff") is None else on["diff"] * 1e4,
            "in_paper": {"K": paper.get("K"), "diff_bps": None if paper.get("diff") is None else paper["diff"] * 1e4},
            "flags": flags, "dsr": dsr, "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ================================================================================ T-581 VIX build-up before FOMC ==

def _lagged(x: np.ndarray, k: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    if k < x.size:
        out[k:] = x[:-k] if k > 0 else x
    return out


def _rolling_sd(x: np.ndarray, win: int) -> np.ndarray:
    """sd (ddof 1) of x[j-win+1 .. j] at each j; NaN when the window is incomplete or holds a NaN."""
    out = np.full(x.size, np.nan)
    if x.size < win:
        return out
    w = np.lib.stride_tricks.sliding_window_view(x, win)
    out[win - 1:] = w.std(axis=1, ddof=1)
    return out


def buildup_z(vix_s: np.ndarray, k: int, sd_win: int = T581_SD_WIN) -> np.ndarray:
    """z[t] = (VIX(t-2) - VIX(t-2-k)) / sd of the k-session changes over the ``sd_win`` sessions ending at t-2 (closes
    through t-2 only: known before the t-1 close, after which the 16:15 ET VIX close of t-1 would be a look-ahead)."""
    ch = vix_s - _lagged(vix_s, k)
    sd = _rolling_sd(ch, sd_win)
    z = np.where(sd > 0, ch / np.where(sd > 0, sd, 1.0), np.nan)
    return _lagged(z, 2)


def buildup_frame(bars, vix: dict, fomc: set, nfp: set) -> dict:
    """Per SPY session t: the close t-1 -> close t total return (cc), the close t-1 -> open t return with the ex-dividend
    cash (on), z3 / z6 (``buildup_z``), the price controls r(close t-5 -> close t-2) and 1{IBS(t-1) < 0.2}, and the event
    dummies (scheduled FOMC statement day; Employment Situation session)."""
    days = list(bars.days)
    n = len(days)
    adj, op, cl, hi, lo = bars.adj, bars.open, bars.close, bars.high, bars.low
    v = np.array([vix.get(d, np.nan) for d in days], float)
    div = OHLC.ex_dividends(cl, adj)
    cc = np.full(n, np.nan); cc[1:] = adj[1:] / adj[:-1] - 1.0
    on = np.full(n, np.nan); on[1:] = op[1:] / cl[:-1] - 1.0 + div[1:] / cl[:-1]
    c1 = np.full(n, np.nan); c1[5:] = adj[3:-2] / adj[:-5] - 1.0
    rng_ = hi - lo
    ibs = np.where(rng_ > 0, (cl - lo) / np.where(rng_ > 0, rng_, 1.0), np.nan)
    ibs1 = _lagged(ibs, 1)
    c2 = np.where(np.isfinite(ibs1), (ibs1 < T581_IBS).astype(float), np.nan)
    return {"day": np.array(days), "cc": cc, "on": on, "z3": buildup_z(v, 3), "z6": buildup_z(v, 6), "c1": c1, "c2": c2,
            "fomc": np.array([d in fomc for d in days], float), "nfp": np.array([d in nfp for d in days], float)}


def arm_design(fr: dict, y: str, z: str, dmy: str, span: tuple) -> tuple:
    """(y, X = [z, D, z D, r(t-5 -> t-2), 1{IBS(t-1) < 0.2}], days) over the sessions in ``span`` with every term finite."""
    X = np.column_stack([fr[z], fr[dmy], fr[z] * fr[dmy], fr["c1"], fr["c2"]])
    m = (fr["day"] >= span[0]) & (fr["day"] <= span[1]) & np.isfinite(fr[y]) & np.isfinite(X).all(axis=1)
    return fr[y][m], X[m], fr["day"][m]


def tercile_spread(fr: dict, span: tuple, cost: float = T581_COST, min_prior: int = T581_TERC_MIN) -> dict:
    """FOMC statement-day returns (close t-1 -> close t) by expanding terciles of z3: cutoffs from the z3 of every
    EARLIER scheduled statement day (from 1994), top = z above the 2/3 cutoff, bottom = at or below the 1/3 cutoff.
    Spread = mean top - mean bottom - 2 x cost (a long top / short bottom pair pays a round trip on each leg)."""
    ev = (fr["fomc"] > 0) & np.isfinite(fr["z3"]) & np.isfinite(fr["cc"])
    idx = np.where(ev)[0]
    top, bot = [], []
    for k, i in enumerate(idx):
        if not (span[0] <= fr["day"][i] <= span[1]) or k < min_prior:
            continue
        q1, q2 = np.quantile(fr["z3"][idx[:k]], [1 / 3, 2 / 3])
        z = fr["z3"][i]
        if z > q2:
            top.append(fr["cc"][i])
        elif z <= q1:
            bot.append(fr["cc"][i])
    if not top or not bot:
        return {"n_top": len(top), "n_bottom": len(bot)}
    return {"n_top": len(top), "n_bottom": len(bot), "mean_top": float(np.mean(top)), "mean_bottom": float(np.mean(bot)),
            "spread_net": float(np.mean(top) - np.mean(bot) - 2 * cost)}


def b13_calendar_a_vix_buildup_fomc(archive):
    """T-581: lagged VIX build-up x FOMC statement day interaction on SPY's close t-1 -> close t return."""
    miss = _missing(archive, [VIX_B, FOMC_B, SPY_B, NFP_B])
    if miss:
        return miss
    bars = OHLC._bars(archive, "SPY")
    fomc = set(_fomc_days(archive))
    nfp_days = _release_days(archive, NFP_B, "employment")
    nfp, moved = to_sessions([d for d in nfp_days if d >= bars.days[0]], bars.days)
    fr = buildup_frame(bars, CAL._series(archive, VIX_B), fomc, set(nfp))
    span = (T581_START, T581_END)
    y, X, dd = arm_design(fr, "cc", "z3", "fomc", span)
    n = int(X[:, 1].sum())
    F = coef_test(y, X, 2, T581_LAG, T581_BLOCK)
    yn, Xn, _ = arm_design(fr, "on", "z6", "nfp", span)
    Nf = coef_test(yn, Xn, 2, T581_LAG, T581_BLOCK)
    hh, hhn = holm2(F.get("hac_p_greater"), Nf.get("hac_p_greater"))
    hb, hbn = holm2(F.get("boot_p_greater"), Nf.get("boot_p_greater"))
    b3 = F.get("coef")
    sub = {}
    for k, sp in (("2010-2017", (T581_START, "2017-12-31")), ("2018-2026", (T581_SPLIT, T581_END)), ("2018-06..2026-10", (T581_POST, T581_END)),
                  ("in_paper_1994-2009", T581_PAPER)):
        ys, Xs, _ = arm_design(fr, "cc", "z3", "fomc", sp)
        r = ols_hac(ys, Xs, T581_LAG)
        sub[k] = {"b3": r["coef"][3] if r["coef"] else None, "t": r["t"][3] if r["coef"] else None, "n_events": int(Xs[:, 1].sum())}
    terc = tercile_spread(fr, span)
    b1 = ols_hac(y, X, T581_LAG)["coef"][1]
    joint = lambda p: None if p is None else min(1.0, T581_JOINT * p)
    boot_dr = F.get("boot_draws", 0)
    rows = [
        (f"b3 > 0 with one-sided p < 0.05 under HAC and the circular block bootstrap (b3 {_f(b3 * 1e4 if b3 is not None else None, 2)} "
         f"bps per z on FOMC days, HAC t {_f(F.get('t'), 2)}, p HAC {_p(F.get('hac_p_greater'))} / bootstrap "
         f"{_mc(F.get('boot_p_greater'), boot_dr)})",
         CAL._agree([_hac_ok(b3, F.get("hac_p_greater"), "greater"), _sig(b3, F.get("boot_p_greater"), boot_dr, "greater")]),
         F.get("hac_p_less") is not None and F["hac_p_less"] < ALPHA and _decide(F.get("boot_p_less"), boot_dr) is True),
        (f"Holm over the 2 arms (FOMC primary, Employment Situation secondary): Holm p HAC {_p(hh)} / bootstrap {_p(hb)}",
         CAL._agree([_hac_ok(b3, hh, "greater"), _sig(b3, hb, boot_dr, "greater")]), False),
        (f"deflated jointly with T-341/T-215/T-343 (Bonferroni over the {T581_JOINT}-member family): p HAC "
         f"{_p(joint(F.get('hac_p_greater')))} / bootstrap {_p(joint(F.get('boot_p_greater')))}",
         CAL._agree([_hac_ok(b3, joint(F.get("hac_p_greater")), "greater"), _sig(b3, joint(F.get("boot_p_greater")), boot_dr, "greater")]), False),
        ("b3 > 0 in 2010-2017, 2018-2026 and 2018-06..2026-10 (" + ", ".join(f"{k} {_f(None if sub[k]['b3'] is None else sub[k]['b3'] * 1e4, 2)}"
                                                                         for k in ("2010-2017", "2018-2026", "2018-06..2026-10")) + " bps per z)",
         None if any(sub[k]["b3"] is None for k in ("2010-2017", "2018-2026", "2018-06..2026-10"))
         else all(sub[k]["b3"] > 0 for k in ("2010-2017", "2018-2026", "2018-06..2026-10")), False),
        (f"top-minus-bottom expanding-tercile FOMC return net of 2 bps a leg > 0 ({_bp(terc.get('spread_net'))} bps; top "
         f"{_bp(terc.get('mean_top'))} over {terc.get('n_top')}, bottom {_bp(terc.get('mean_bottom'))} over {terc.get('n_bottom')})",
         None if terc.get("spread_net") is None else terc["spread_net"] > 0, False),
    ]
    v, why, crit = CAL._judge(CAL._undecided(rows), n, T581_MIN_N, "FOMC statement days")
    # reported
    ev = (X[:, 1] > 0)
    cpi = set(_release_days(archive, CPI_B, "cpi")) if _has(archive, CPI_B) else set()
    share = sum(1 for d in dd[ev] if d in cpi or d in set(nfp))
    zlb = sum(1 for d in dd[ev] if any(_in(d, s) for s in T581_ZLB))
    m2003 = sum(1 for d in dd[ev] if "2020-03-01" <= d <= "2020-03-31")
    reason = (f"SPY sessions {dd[0]}..{dd[-1]} ({y.size} rows, {n} scheduled FOMC statement days; unscheduled meetings out); z = "
              f"(VIX t-2 - VIX t-5) / sd of 3-session changes over the 250 sessions ending t-2. OLS (NW lag 5): b1 (non-event "
              f"placebo slope) {_f(b1 * 1e4, 2)} bps per z, b3 {_f(b3 * 1e4 if b3 is not None else None, 2)} "
              f"(HAC t {_f(F.get('t'), 2)}); subsamples " + ", ".join(f"{k} b3 {_f(None if s_['b3'] is None else s_['b3'] * 1e4, 2)} "
                                                                 f"(t {_f(s_['t'], 2)}, {s_['n_events']} events)" for k, s_ in sub.items())
              + f". Employment Situation arm (z6, close t-1 -> open t; {int(Xn[:, 1].sum())} release sessions, {moved} releases "
              f"moved to the next session): b3 {_f(None if Nf.get('coef') is None else Nf['coef'] * 1e4, 2)} bps per z (HAC t "
              f"{_f(Nf.get('t'), 2)}, Holm p HAC {_p(hhn)} / bootstrap {_p(hbn)}). Tercile spread net {_bp(terc.get('spread_net'))} bps. "
              f"Flagged: {share} statement days share a session with a CPI or payroll release; {zlb} in the ZLB years; {m2003} in 2020-03")
    stat = {"n_events": n, "rows": int(y.size), "fomc": {k: F.get(k) for k in ("coef", "se", "t", "hac_p_greater", "boot_p_greater", "boot_draws")},
            "nfp": {k: Nf.get(k) for k in ("coef", "se", "t", "hac_p_greater", "boot_p_greater", "boot_draws")},
            "holm": {"hac": [hh, hhn], "boot": [hb, hbn]}, "joint_deflated": {"hac": joint(F.get("hac_p_greater")), "boot": joint(F.get("boot_p_greater"))},
            "subsamples": sub, "tercile": terc, "b1_placebo": b1, "flags": {"cpi_or_nfp_share": share, "zlb": zlb, "2020_03": m2003},
            "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


# ============================================================================ T-583 FOMC-window short-dollar carry ==

def fx_noon(rows: Sequence[dict], ccys: Sequence[str] = G10) -> tuple:
    """(days, {ccy: array of USD per unit aligned to days, NaN where the currency did not print}) of the FRED H.10 noon
    rates; days = the dates on which any of ``ccys`` prints (the H.10 calendar)."""
    by = defaultdict(dict)
    for r in rows:
        v = r.get("value") or {}
        c, d, x = v.get("ccy"), v.get("day"), v.get("usd_per_unit")
        if c in ccys and d and x:
            try:
                x = float(x)
            except (TypeError, ValueError):
                continue
            if x > 0 and math.isfinite(x):
                by[d][c] = x
    days = sorted(by)
    return days, {c: np.array([by[d].get(c, np.nan) for d in days]) for c in ccys}


def rate_book(rows: Sequence[dict]) -> dict:
    """{ccy: sorted [(month, rate3m, available_at)]} of the OECD 3-month rates."""
    out = defaultdict(list)
    for r in rows:
        v = r.get("value") or {}
        try:
            x = float(v.get("rate3m"))
        except (TypeError, ValueError):
            continue
        if v.get("ccy") and v.get("month") and math.isfinite(x):
            out[v["ccy"]].append((v["month"], x, r.get("available_at") or ""))
    return {c: sorted(l) for c, l in out.items()}


def _prev_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def _next_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y + 1}-01" if mo == 12 else f"{y}-{mo + 1:02d}"


def rate_available(month: str, av: str, pub_day: int = T583_PUB_DAY) -> str:
    """The day a month's OECD rate is taken as published: the later of the row's available_at date and day ``pub_day``
    of the following month (the archive stamps each print on the 28th of its own month, before that month's average is
    complete, so the stamp alone is not a publication time)."""
    return max(str(av or "")[:10], f"{_next_month(month)}-{pub_day:02d}")


def rank_schedule(days: Sequence[str], book: dict, ccys: Sequence[str] = G10, top: int = T583_TOP) -> list:
    """[(rank_day, basket, stale ccys)]: at the last H.10 day of each month m (complete months only), the ``top``
    currencies by the month m-1 OECD 3-month rate (the latest month <= m-1 published, per ``rate_available``, on or
    before the rank day; a currency whose m-1 print is not yet out carries its latest earlier print and is listed as
    stale)."""
    last = {}
    for i, d in enumerate(days[:-1]):
        if d[:7] != days[i + 1][:7]:
            last[d[:7]] = d
    out = []
    for m in sorted(last):
        rd = last[m]
        target = _prev_month(m)
        lv, stale = {}, []
        for c in ccys:
            ok = [(mm, x) for mm, x, av in book.get(c, []) if mm <= target and rate_available(mm, av) <= rd]
            if not ok:
                continue
            mm, x = ok[-1]
            lv[c] = x
            if mm < target:
                stale.append(c)
        if len(lv) >= top:
            basket = tuple(sorted(sorted(lv, key=lambda c: (-lv[c], c))[:top]))
            out.append((rd, basket, tuple(sorted(stale))))
    return out


def _basket_for(sched: list, day: str):
    j = bisect.bisect_right([s[0] for s in sched], day) - 1
    return sched[j] if j >= 0 else None


def round_trip(basket: Sequence[str]) -> float:
    """Round-trip cost of an equal-weight basket: 2 x the mean per-side cost (4 bps NOK/SEK, 1.5 bps the others)."""
    return 2.0 * float(np.mean([T583_COST_SIDE.get(c, T583_COST_MAJOR) for c in basket]))


def carry_series(days: Sequence[str], px: dict, sched: Optional[list], fomc: Sequence[str], start: str = T583_START,
                 end: str = T583_END, dol: bool = False) -> dict:
    """Daily noon-to-noon basket log returns on the H.10 calendar (interval p -> d, the basket fixed at the latest rank
    day <= p; ``dol``: all 9) and the FOMC windows noon(t-1) -> noon(t+1) (t = a scheduled statement day on the calendar;
    the basket fixed at noon t-1, every basket currency printing at t-1, t and t+1). Window days (t and t+1) carry the
    window basket's returns net of half its round trip each; other days are the baseline. Returns the per-day arrays
    (x, window flag, day), the windows and the return days of every FOMC window (usable or not)."""
    pos = {d: i for i, d in enumerate(days)}
    n = len(days)
    lp = {c: np.log(v) for c, v in px.items()}

    def bk(p):
        if dol:
            return tuple(G10), (), round_trip(G10)
        s = _basket_for(sched, p)
        return (s[1], s[2], round_trip(s[1])) if s else (None, None, None)

    def ret(b, i0, i1):
        vals = [lp[c][i1] - lp[c][i0] for c in b]
        return float(np.mean(vals)) if all(np.isfinite(vals)) else None

    wdays, wins = set(), []
    for t in fomc:
        i = pos.get(t)
        if i is None or i < 1 or i + 1 >= n:
            continue
        wdays.update((days[i], days[i + 1]))
        if not (start <= t <= end):
            continue
        b, stale, cost = bk(days[i - 1])
        if b is None:
            continue
        r1, r2 = ret(b, i - 1, i), ret(b, i, i + 1)
        if r1 is None or r2 is None:
            continue
        wins.append({"t": t, "p": days[i - 1], "q": days[i + 1], "basket": b, "stale": stale, "cost": cost, "r1": r1, "r2": r2,
                     "gross": r1 + r2, "net": r1 + r2 - cost})
    xs, fl, dd = [], [], []
    for w in wins:
        xs += [w["r1"] - w["cost"] / 2, w["r2"] - w["cost"] / 2]; fl += [True, True]; dd += [w["t"], w["q"]]
    for i in range(1, n):
        d = days[i]
        if not (start <= d <= end) or d in wdays:
            continue
        b, _, _ = bk(days[i - 1])
        if b is None:
            continue
        r = ret(b, i - 1, i)
        if r is not None:
            xs.append(r); fl.append(False); dd.append(d)
    o = np.argsort(np.array(dd), kind="stable")
    return {"x": np.array(xs)[o], "f": np.array(fl)[o], "day": np.array(dd)[o], "windows": wins, "window_days": wdays}


def carry_stat(cs: dict, span: tuple = ("0000", "9999")) -> Optional[dict]:
    m = (cs["day"] >= span[0]) & (cs["day"] <= span[1])
    x, f = cs["x"][m], cs["f"][m]
    w = [w for w in cs["windows"] if span[0] <= w["t"] <= span[1]]
    if f.sum() < 4 or (~f).sum() < 10:
        return None
    base = float(x[~f].mean())
    return {"n": len(w), "mean_net": float(np.mean([v["net"] for v in w])), "mean_gross": float(np.mean([v["gross"] for v in w])),
            "base_daily": base, "diff_net": float(np.mean([v["net"] for v in w]) - 2 * base),
            "diff_gross": float(np.mean([v["gross"] for v in w]) - 2 * base)}


def carry_boot(cs: dict, bar: float, alpha: float = ALPHA, n_boot: int = N_BOOT, seed: int = SEED) -> tuple:
    """Studentized circular block bootstrap (21 days) of the day-flagged series d = 2 x flag_diff(x_net, window) - bar,
    whose mean is the net difference minus the bar: (p_greater, p_less, draws)."""
    d = 2.0 * CAL.flag_diff_series(cs["x"], cs["f"]) - bar
    return _escalate(lambda k: CAL.studentized_p(d, T583_BLOCK, n_boot, seed + k, 1), n_boot, alpha=alpha)


def placebo_pool(days: Sequence[str], px: dict, sched: Optional[list], fomc: Sequence[str], window_days: set,
                 start: str = T583_START, end: str = T583_END, dol: bool = False) -> dict:
    """{(weekday, week-of-month): [net placebo window returns]} of every H.10 day d in [start, end] whose ISO week holds no
    scheduled FOMC statement day and whose window (d-1, d, d+1) touches no FOMC window day; basket and cost as for a
    real window (fixed at noon d-1)."""
    fweeks = {iso_week(t) for t in fomc}
    pos_days = list(days)
    lp = {c: np.log(v) for c, v in px.items()}
    out = defaultdict(list)
    for i in range(1, len(pos_days) - 1):
        d = pos_days[i]
        if not (start <= d <= end) or iso_week(d) in fweeks:
            continue
        if {pos_days[i - 1], d, pos_days[i + 1]} & window_days:
            continue
        if dol:
            b = G10
        else:
            s = _basket_for(sched, pos_days[i - 1])
            if s is None:
                continue
            b = s[1]
        vals = [lp[c][i + 1] - lp[c][i - 1] for c in b]
        mid = [lp[c][i] for c in b]
        if not (all(np.isfinite(vals)) and all(np.isfinite(mid))):
            continue
        out[(_d(d).weekday(), (_d(d).day - 1) // 7)].append(float(np.mean(vals)) - round_trip(b))
    return {k: np.array(v) for k, v in out.items()}


def _perm_batch(windows: list, pool: dict, base: float, obs: float, bar: float, n_draws: int, seed: int) -> tuple:
    """One batch of the same-position-in-month date permutation: every FOMC window replaced by a random non-FOMC window
    with the same weekday and week-of-month (falling back to the same weekday when that bucket is empty);
    (p_greater, p_less) of obs against placebo statistic + bar."""
    rng = np.random.default_rng(seed + 104729)
    cols = []
    for w in windows:
        key = (_d(w["t"]).weekday(), (_d(w["t"]).day - 1) // 7)
        arr = pool.get(key)
        if arr is None or arr.size == 0:
            arr = np.concatenate([v for (wd, _), v in pool.items() if wd == key[0]])
        cols.append(arr[rng.integers(0, arr.size, n_draws)])
    st = np.mean(np.column_stack(cols), axis=1) - 2 * base + bar
    return float((np.sum(st >= obs) + 1) / (st.size + 1)), float((np.sum(st <= obs) + 1) / (st.size + 1))


def carry_perm(cs: dict, pool: dict, bar: float, alpha: float = ALPHA, n_draws: int = T583_N_PERM, seed: int = SEED) -> tuple:
    s = carry_stat(cs)
    return _escalate(lambda k: _perm_batch(cs["windows"], pool, s["base_daily"], s["diff_net"], bar, n_draws, seed + k),
                     n_draws, k0=1, k_max=10, alpha=alpha)


def fx_timing_legs(windows: list, start: str = "2024-01-01") -> dict:
    """Report only: per FOMC window from ``start``, the basket's 16:00 ET (t-1) -> 14:00 ET (t) and 14:00 -> 16:00 ET (t)
    log returns from local 60m Yahoo bars (stamped by bar OPEN: the price at hh:00 is the close of the bar opened an
    hour earlier); NOK and SEK have no local bars and drop out of the basket."""
    try:
        from mandel.ml.features import load_bars
    except Exception:  # pragma: no cover - optional local data
        return {"n": 0, "note": "local bars unavailable"}
    import pandas as pd
    px = {}
    for c, (sym, inv) in T583_FX60.items():
        df = load_bars("60m", sym)
        if df is None or df.empty:
            continue
        s = df["c"].astype(float)
        s.index = (s.index + pd.Timedelta(hours=1)).tz_convert("America/New_York")
        px[c] = (1.0 / s) if inv else s
    if not px:
        return {"n": 0, "note": "no local 60m FX bars"}

    def at(c, day, hh):
        s = px[c]
        ts = pd.Timestamp(f"{day} {hh:02d}:00", tz="America/New_York")
        if ts not in s.index:
            return None
        return float(s.loc[ts])

    a_, b_ = [], []
    for w in windows:
        if w["t"] < start:
            continue
        cs = [c for c in w["basket"] if c in px]
        l1, l2 = [], []
        for c in cs:
            x0, x1, x2 = at(c, w["p"], 16), at(c, w["t"], 14), at(c, w["t"], 16)
            if None not in (x0, x1, x2):
                l1.append(math.log(x1 / x0)); l2.append(math.log(x2 / x1))
        if l1:
            a_.append(float(np.mean(l1))); b_.append(float(np.mean(l2)))
    return {"n": len(a_), "pre_bps": float(np.mean(a_) * 1e4) if a_ else None, "post_bps": float(np.mean(b_) * 1e4) if b_ else None}


def b13_calendar_a_fomc_carry(archive):
    """T-583: top-3 carry basket vs USD over noon(t-1) -> noon(t+1) FOMC windows minus twice its non-FOMC daily mean."""
    miss = _missing(archive, [FX_B, RATES_B, FOMC_B])
    if miss:
        return miss
    days, px = fx_noon(_rows(archive, FX_B))
    book = rate_book(_rows(archive, RATES_B))
    sched = rank_schedule(days, book)
    fomc = _fomc_days(archive)
    cs = carry_series(days, px, sched, fomc)
    dl = carry_series(days, px, None, fomc, dol=True)
    S, SD = carry_stat(cs), carry_stat(dl)
    n = S["n"] if S else 0
    if S is None or SD is None:
        v, why, crit = CAL._judge([("FOMC windows with every basket currency printing", None, False)], n, T583_MIN_N, "FOMC windows")
        return _out({"n_windows": n}, n, v, f"too few usable windows — {why}")
    pool = placebo_pool(days, px, sched, fomc, cs["window_days"])
    pool_d = placebo_pool(days, px, None, fomc, dl["window_days"], dol=True)
    bg, bl, bdr = carry_boot(cs, T583_BAR)
    pg, pl, pdr = carry_perm(cs, pool, T583_BAR)
    dbg, dbl, dbdr = carry_boot(dl, 0.0)
    dpg, dpl, dpdr = carry_perm(dl, pool_d, 0.0)
    hb, hbd = holm2(bg, dbg)
    hp, hpd = holm2(pg, dpg)
    halves = [carry_stat(cs, (T583_START, "2018-12-31")), carry_stat(cs, (T583_SPLIT, T583_END))]
    hn = [None if h is None else h["diff_net"] for h in halves]
    D_, Dd = S["diff_net"], SD["diff_net"]
    rows = [
        (f"net difference {_bp(D_)} bps (window net {_bp(S['mean_net'])} - 2 x daily {_bp(S['base_daily'])}) > 3 bps with one-sided "
         f"p < 0.05 under both nulls after Holm over the primary and DOL: CBB (21 days) p {_mc(bg, bdr)} (Holm {_p(hb)}), "
         f"same-position permutation p {_mc(pg, pdr)} (Holm {_p(hp)})",
         CAL._agree([_sig(D_ - T583_BAR, hb, bdr, "greater"), _sig(D_ - T583_BAR, hp, pdr, "greater")]),
         _decide(bl, bdr) is True and _decide(pl, pdr) is True),
        (f"both halves positive net (2011-2018 {_bp(hn[0])}, 2019-2026 {_bp(hn[1])} bps)",
         None if any(x is None for x in hn) else all(x > 0 for x in hn), False),
        (f"DOL (9-currency basket) the same sign after Holm over 2: net {_bp(Dd)} bps, Holm p CBB {_p(hbd)} / permutation {_p(hpd)}",
         CAL._agree([_sig(Dd, hbd, dbdr, "greater"), _sig(Dd, hpd, dpdr, "greater")]), False),
    ]
    v, why, crit = CAL._judge(CAL._undecided(rows), n, T583_MIN_N, "FOMC windows")
    # reported: dummies, ZLB, interactions, timing
    W = cs["windows"]
    last2 = set()
    for i in range(len(days) - 1):
        if days[i][:7] != days[i + 1][:7]:
            last2.update((days[i], days[i - 1]) if i >= 1 else (days[i],))
    cpi = set(_release_days(archive, CPI_B, "cpi")) if _has(archive, CPI_B) else set()
    me_flag = np.array([bool({w["p"], w["t"], w["q"]} & last2) for w in W])
    cpi_flag = np.array([w["t"] in cpi or w["q"] in cpi for w in W])
    nets = np.array([w["net"] for w in W])
    clean = ~me_flag & ~cpi_flag
    zlb = np.array([_in(w["t"], T583_ZLB) for w in W])
    stale = sum(1 for w in W if w["stale"])
    stale_ccys = sorted({c for w in W for c in w["stale"]})
    inter = {}
    if _has(archive, DFF_B) and _has(archive, VXTLT_B):
        dff = CAL._series(archive, DFF_B)
        kd = sorted(dff)
        def mean30(end_day):
            a = (_d(end_day) - timedelta(days=29)).isoformat()
            vals = [dff[k] for k in kd[bisect.bisect_left(kd, a):bisect.bisect_right(kd, end_day)]]
            return float(np.mean(vals)) if vals else None
        vx = CAL._series(archive, VXTLT_B)
        kv = sorted(vx)
        ease, lvl, yv = [], [], []
        for w in W:
            known = (_d(w["p"]) - timedelta(days=1)).isoformat()          # prints dated before noon t-1 (DFF / VXTLT closes)
            a, b = mean30(known), mean30((_d(known) - timedelta(days=182)).isoformat())
            j = bisect.bisect_right(kv, known) - 1
            if a is None or b is None or j < 0:
                continue
            ease.append(float(a - b < T583_EASE)); lvl.append(vx[kv[j]]); yv.append(w["net"])
        if len(yv) > 20:
            e = np.array(ease); lv = np.array(lvl); yy = np.array(yv)
            r1 = ols_hac(yy, e, 1); r2 = ols_hac(yy, (lv - lv.mean()) / lv.std(ddof=1), 1)
            p1 = 1 - _NORM.cdf(r1["t"][1]) if r1["coef"] and np.isfinite(r1["t"][1]) else None
            p2 = 1 - _NORM.cdf(r2["t"][1]) if r2["coef"] and np.isfinite(r2["t"][1]) else None
            h1, h2 = holm2(p1, p2)
            inter = {"n": len(yv), "n_easing": int(e.sum()), "easing_slope_bps": r1["coef"][1] * 1e4 if r1["coef"] else None,
                     "easing_p": p1, "easing_holm": h1, "vxtlt_slope_bps_per_sd": r2["coef"][1] * 1e4 if r2["coef"] else None,
                     "vxtlt_p": p2, "vxtlt_holm": h2}
    timing = fx_timing_legs(W)
    comp = defaultdict(int)
    for w in W:
        comp["/".join(w["basket"])] += 1
    reason = (f"{n} scheduled FOMC windows {W[0]['t']}..{W[-1]['t']} (noon t-1 -> noon t+1, H.10; every basket currency printing); "
              f"top-3 basket by month m-1 OECD 3-month rate ranked at each month end (" + ", ".join(f"{k} {v_}" for k, v_ in
              sorted(comp.items(), key=lambda kv: -kv[1])[:6]) + f"; ranks gate each OECD print on its publication, the later of its stamp and the {T583_PUB_DAY}th of the next "
              f"month: {stale} windows rank with an m-1 print not yet published, carried from an earlier month "
              f"({'/'.join(stale_ccys) or 'none'})): window "
              f"gross {_bp(S['mean_gross'])} / net {_bp(S['mean_net'])} bps vs 2 x the non-FOMC daily {_bp(S['base_daily'])}: "
              f"difference {_bp(S['diff_gross'])} gross / {_bp(D_)} net; halves net {_bp(hn[0])} / {_bp(hn[1])}; DOL net {_bp(Dd)} "
              f"(gross {_bp(SD['diff_gross'])}). Permutation pool {sum(v_.size for v_ in pool.values())} non-FOMC windows. Reported: "
              f"windows on the last two days of a month {int(me_flag.sum())}, holding a CPI release {int(cpi_flag.sum())}; net window "
              f"mean without them {_bp(float(nets[clean].mean()) if clean.any() else None)} bps ({int(clean.sum())}); ZLB 2011-2015 "
              f"{_bp(float(nets[zlb].mean()) if zlb.any() else None)} ({int(zlb.sum())}) vs later {_bp(float(nets[~zlb].mean()) if (~zlb).any() else None)}; "
              f"interactions (Holm over 2, report only) {inter}; 60m timing check 2024-2026 (no NOK/SEK bars) {timing}. "
              f"Costs 1.5 bps a side per major and 4 bps NOK/SEK, charged on every window")
    stat = {"n_windows": n, "diff_net_bps": D_ * 1e4, "diff_gross_bps": S["diff_gross"] * 1e4, "window_net_bps": S["mean_net"] * 1e4,
            "base_daily_bps": S["base_daily"] * 1e4, "boot": {"p_greater": bg, "draws": bdr, "holm": hb},
            "perm": {"p_greater": pg, "draws": pdr, "holm": hp}, "halves_net_bps": [None if x is None else x * 1e4 for x in hn],
            "dol": {"diff_net_bps": Dd * 1e4, "boot_p": dbg, "perm_p": dpg, "holm_boot": hbd, "holm_perm": hpd},
            "month_end_windows": int(me_flag.sum()), "cpi_windows": int(cpi_flag.sum()), "stale_rank_windows": stale, "stale_ccys": stale_ccys, "rate_publication_day": T583_PUB_DAY,
            "interactions": inter, "timing_60m": timing, "baskets": dict(comp), "criteria": crit}
    return _out(stat, n, v, reason + " — " + why)


HARNESSES = {"b13_calendar_a_pre_auction_concession": b13_calendar_a_pre_auction_concession,
             "b13_calendar_a_putwrite_weekend": b13_calendar_a_putwrite_weekend,
             "b13_calendar_a_hvix_next_session": b13_calendar_a_hvix_next_session,
             "b13_calendar_a_vix_buildup_fomc": b13_calendar_a_vix_buildup_fomc,
             "b13_calendar_a_fomc_carry": b13_calendar_a_fomc_carry}
THEORY_MAP = {"T-589": "b13_calendar_a_pre_auction_concession", "T-592": "b13_calendar_a_putwrite_weekend",
              "T-582": "b13_calendar_a_hvix_next_session", "T-581": "b13_calendar_a_vix_buildup_fomc",
              "T-583": "b13_calendar_a_fomc_carry"}
