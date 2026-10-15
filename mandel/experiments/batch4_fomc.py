"""
Batch 4, FOMC event studies: pre-FOMC drift, FOMC-cycle weeks, monetary momentum and FOMC-day option premia.
=============================================================================================================

Seven library claims (T-214, T-215, T-221, T-273, T-341, T-342, T-361) tested on archived daily data. Each test follows
the claim and its trial.pass as worded.

Calendar. Decision days are ``decision_day`` from the ``fomc-meetings`` bundle (federalreserve.gov), scheduled meetings
only. The schedule is published about a year ahead, so flagging a scheduled decision day at the previous close uses no
future information. Meetings after the last price bar are dropped. Unscheduled meetings that a claim leaves out of the
non-FOMC group are mapped to the first trading day on or after their decision day (the 2020-03-15 meeting was a Sunday;
its market reaction is the 2020-03-16 session), plus the statement-release day when it differs (2020-03-02 -> 2020-03-03).

Day-flagged tests. A daily series x_t with event flag f_t is turned into d_t = diff + w_t (x_t - m_g(t)), where
w_t = 1/p on event days and -1/(1-p) on other days (p = share of event days), m_g is the group mean and diff is the
event-minus-other difference in means. mean(d) = diff exactly, and resampling d in circular blocks gives the sampling
spread of the difference with within-group variances, so autocorrelation and volatility clustering are kept.
p-values come from the studentized block bootstrap (``block_bootstrap_pvalue``). CIs are block-bootstrap percentile
intervals (``_mean_ci``), two-sided 95%: "CI excluding 0" means the whole interval is on the claimed side.

Model-priced straddles (T-214, T-221) use Black-Scholes at sigma = index/100 (VIX for SPY, DVOL for BTC), ATM strike at
the previous close, T = 1/252 (SPY) or 1/365 (BTC), r = q = 0 (the rate changes a 1-day ATM straddle by under 0.1 bp).
P&L is in fraction of spot. Every such result is labelled MODEL-PRICED: a flat 30-day index cannot see the event
premium that traded event-expiry options carry.

Costs follow each claim: T-341 charges 2 bps per round trip (the top of its 1-2 bps), T-342 charges 2 bps per
holding block, T-361 charges 2 bps per leg. Equity annualisation uses 252 trading days, crypto 365 calendar days.

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not
implemented -> at best inconclusive; supported only when every criterion is implemented and passes. When the data
cannot support the claim (too few events, missing bundle) the verdict is inconclusive with the reason.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.underlying2 import _mean_ci, _sharpe_diff_lower, _sr, _verdict, load_series
from mandel.experiments.volatility import index_closes
from mandel.options import bs
from mandel.validation.backtest_eval import block_bootstrap_pvalue

EQ_PPY = 252
CRYPTO_PPY = 365
EVEN_WEEKS = (0, 2, 4, 6)
ODD_WEEKS = (1, 3, 5, 7)


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
        archive.get(name)
        return True
    except KeyError:
        return False


def _index(archive, name: str) -> dict[str, float]:
    """{day: close} of an index/FRED/DVOL bundle, keeping only rows available when the bundle was captured."""
    def load():
        cap = archive.get(name).created_at
        rows = (r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap))
        return index_closes(rows)
    return _cached(archive, ("index", name), load)


def _prices(archive, symbol: str, adjusted: bool):
    return _cached(archive, ("px", symbol, adjusted), lambda: load_series(archive, symbol, adjusted=adjusted))


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


# Unscheduled meetings whose statement came out on a later day than the bundle's decision_day: the rate cut decided at
# the 2020-03-02 unscheduled meeting was released 2020-03-03 at 10:00 a.m. EST (federalreserve.gov press release
# monetary20200303a).
UNSCHEDULED_RELEASE_DAYS = {"2020-03-02": "2020-03-03"}


def _fomc_unscheduled(archive) -> list[str]:
    """Unscheduled decision days plus any later statement-release day (calendar dates; the callers align them to the
    trading calendar with ``align_to_trading_days``)."""
    def load():
        rows = list(archive.load("fomc-meetings"))
        un = set(scheduled_decision_days(rows, scheduled_only=False)) - set(scheduled_decision_days(rows))
        return sorted(un | {UNSCHEDULED_RELEASE_DAYS[d] for d in un if d in UNSCHEDULED_RELEASE_DAYS})
    return _cached(archive, ("fomc-unscheduled",), load)


def align_to_trading_days(days: Sequence[str], dates) -> set:
    """First trading day on or after each date (a weekend meeting maps to the next session); dates outside the calendar
    are dropped."""
    arr = np.asarray(days); out = set()
    for d in dates:
        if len(arr) and arr[0] <= d <= arr[-1]:
            out.add(str(arr[int(np.searchsorted(arr, d, side="left"))]))
    return out


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return {"missing_bundles": miss}, 0, "inconclusive", f"missing data bundles {miss}: the claim cannot be tested until they are archived"
    return None


def _clean(x):
    """JSON-safe copy (numpy scalars/arrays to Python)."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (np.bool_,)):
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


# ------------------------------------------------------------------------------------------- statistics core --

def _range_mask(ds: np.ndarray, start: Optional[str], end: Optional[str]) -> np.ndarray:
    m = np.ones(len(ds), dtype=bool)
    if start:
        m &= ds >= start
    if end:
        m &= ds <= end
    return m


def _returns(days: Sequence[str], closes: np.ndarray, start: Optional[str] = None, end: Optional[str] = None):
    """(day array, simple return ending on that day) restricted to [start, end]."""
    c = np.asarray(closes, dtype=float)
    r = c[1:] / c[:-1] - 1
    ds = np.array(days[1:])
    m = _range_mask(ds, start, end)
    return ds[m], r[m]


def flag_diff_series(x: np.ndarray, flag: np.ndarray) -> np.ndarray:
    """Day-flagged series whose mean is mean(x[flag]) - mean(x[~flag]) and whose block-resampled mean has the
    within-group sampling spread of that difference (see the module docstring)."""
    x = np.asarray(x, dtype=float); f = np.asarray(flag, dtype=bool)
    p = f.mean()
    me, mo = x[f].mean(), x[~f].mean()
    w = np.where(f, 1.0 / p, -1.0 / (1.0 - p))
    return (me - mo) + w * (x - np.where(f, me, mo))


def group_diff(x: np.ndarray, flag: np.ndarray, block: int = 10, n_boot: int = 2000, seed: int = 0) -> dict:
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


def _point_diff(x: np.ndarray, f: np.ndarray) -> Optional[float]:
    f = np.asarray(f, dtype=bool)
    if f.sum() == 0 or (~f).sum() == 0:
        return None
    return float(np.asarray(x)[f].mean() - np.asarray(x)[~f].mean())


def _hac_ci(d: np.ndarray, bandwidth: int = 10) -> list[float]:
    """Newey-West (Bartlett) 95% CI for the mean of d."""
    x = d - d.mean(); n = len(x)
    lrv = float(np.sum(x * x) / n)
    for k in range(1, bandwidth):
        lrv += 2.0 * (1.0 - k / bandwidth) * float(np.sum(x[k:] * x[:-k]) / n)
    se = math.sqrt(max(lrv, 1e-300) / n)
    return [float(d.mean() - 1.96 * se), float(d.mean() + 1.96 * se)]


def _holm(ps: dict[str, float]) -> dict[str, float]:
    items = sorted(ps.items(), key=lambda kv: kv[1]); m = len(items); out = {}; run = 0.0
    for k, (name, p) in enumerate(items):
        run = max(run, min(1.0, (m - k) * p)); out[name] = run
    return out


def _binom_tail(k: int, n: int) -> float:
    """P(X >= k) for X ~ Binomial(n, 1/2)."""
    return float(sum(math.comb(n, j) for j in range(k, n + 1)) / 2.0 ** n) if n else 1.0


def _bps(x) -> str:
    return "n/a" if x is None else f"{x * 1e4:+.1f}"


def _ci_bps(ci) -> str:
    return "n/a" if ci[0] is None else f"{ci[0] * 1e4:+.1f} to {ci[1] * 1e4:+.1f}"


# ------------------------------------------------------------------------------- model-priced event straddles --

def short_straddle_pnl(s_prev, s_now, sigma, tau: float, r: float = 0.0):
    """Short ATM straddle (K = s_prev) sold at s_prev with Black-Scholes at sigma, settled at |s_now - K|.
    Returns (P&L in fraction of s_prev, premium in fraction of s_prev, coin-accounted P&L = premium/s_prev - |s_now-K|/s_now)."""
    s0 = np.asarray(s_prev, dtype=float); s1 = np.asarray(s_now, dtype=float); sig = np.asarray(sigma, dtype=float)
    prem = bs.price(s0, s0, tau, r, sig, "call") + bs.price(s0, s0, tau, r, sig, "put")
    pay = np.abs(s1 - s0)
    return (prem - pay) / s0, prem / s0, prem / s0 - pay / s1


def event_straddle_panel(days, closes, iv: dict, event_days, tau: float, ppy: int, start: Optional[str] = None,
                         end: Optional[str] = None, max_gap_days: Optional[int] = None, exclude_days=()) -> dict:
    """One short 1-period ATM straddle per day i: sold at close i-1 with sigma = iv[day i-1]/100, settled at close i.
    ``max_gap_days`` drops windows longer than that many calendar days (data gaps in 24/7 series); ``exclude_days``
    (e.g. unscheduled FOMC days), each mapped to the first trading day on or after it, are left out of both groups."""
    ev = set(event_days); ex = align_to_trading_days(days, exclude_days) - ev; c = np.asarray(closes, dtype=float)
    keep = []
    lr = np.diff(np.log(c))
    for i in range(1, len(days)):
        d, p = days[i], days[i - 1]
        if (start and d < start) or (end and d > end) or d in ex:
            continue
        s = iv.get(p)
        if s is None or not s > 0:
            continue
        if max_gap_days and (date.fromisoformat(d) - date.fromisoformat(p)).days > max_gap_days:
            continue
        keep.append(i)
    idx = np.array(keep, dtype=int)
    ds = np.array([days[i] for i in keep])
    s0, s1 = c[idx - 1], c[idx]
    sig = np.array([iv[days[i - 1]] for i in keep], dtype=float) / 100.0
    pnl, prem, pnl_coin = short_straddle_pnl(s0, s1, sig, tau)
    ret = s1 / s0 - 1
    # trailing 30-return realised daily vol ending at close i-1 (scale check)
    rv = np.array([math.sqrt(np.mean(lr[i - 31:i - 1] ** 2)) if i >= 31 else np.nan for i in keep])
    return {"days": ds, "pnl": pnl, "premium": prem, "pnl_coin": pnl_coin, "ret": ret, "sigma": sig,
            "flag": np.array([d in ev for d in ds], dtype=bool), "ratio": np.abs(ret) / (sig / math.sqrt(ppy)), "rv30_prev": rv}


def _placebo_days(days: Sequence[str], event_days, offset_calendar_days: int = 7) -> set:
    """Trading day on/after event+k and on/before event-k calendar days (the FOMC +/- 7 days placebo)."""
    arr = np.array(days); out = set(); ev = set(event_days)
    for e in event_days:
        de = date.fromisoformat(e)
        a = (de + timedelta(days=offset_calendar_days)).isoformat(); b = (de - timedelta(days=offset_calendar_days)).isoformat()
        ia = int(np.searchsorted(arr, a, side="left")); ib = int(np.searchsorted(arr, b, side="right")) - 1
        if ia < len(arr):
            out.add(arr[ia])
        if ib >= 0:
            out.add(arr[ib])
    return out - ev


def spx_event_straddle(days, closes, vix: dict, fomc_days, start: str = "1994-01-01",
                       halves=(("1994-2010", "1994-01-01", "2010-12-31"), ("2011-2026", "2011-01-01", "2026-12-31")),
                       exclude_days=(), block: int = 10, n_boot: int = 2000, seed: int = 0, min_n: int = 200) -> dict:
    """T-214 (MODEL-PRICED): 1-day ATM SPY straddle, sigma = VIX at the T-1 close, T = 1/252, sold at the T-1 close and
    settled on |SPY_T - SPY_T-1|. Pass: FOMC-minus-non-FOMC mean short P&L < 0 with the 95% CI excluding 0 in both
    1994-2010 and 2011-2026. Controls reported: FOMC +/- 7 calendar-day placebo, excluding September 2008 and March 2020,
    VIX terciles, |r|/(VIX/sqrt 252) by group, |r| over trailing 30-day realised daily vol by group. ``exclude_days``
    (unscheduled FOMC days, mapped to the first trading day on or after each) are dropped from the non-FOMC group."""
    P = event_straddle_panel(days, closes, vix, fomc_days, 1.0 / EQ_PPY, EQ_PPY, start=start, exclude_days=exclude_days)
    if len(P["days"]) == 0:
        return {"n": 0, "verdict": "inconclusive", "reason": "no SPY day has a prior-day VIX close"}
    f = P["flag"]
    full = group_diff(P["pnl"], f, block, n_boot, seed)
    hv = {}
    for lab, lo, hi in halves:
        m = _range_mask(P["days"], lo, hi)
        hv[lab] = group_diff(P["pnl"][m], f[m], block, n_boot, seed)
    plc = _placebo_days(list(P["days"]), [d for d in fomc_days if d >= start], 7)
    pf = np.array([d in plc for d in P["days"]]); m_nf = ~f
    placebo = group_diff(P["pnl"][m_nf], pf[m_nf], block, n_boot, seed)
    excl = np.array([not (d.startswith("2008-09") or d.startswith("2020-03")) for d in P["days"]])
    excl_diff = group_diff(P["pnl"][excl], f[excl], block, n_boot, seed)
    q1, q2 = np.quantile(P["sigma"], [1 / 3, 2 / 3])
    terc = {}
    for lab, m in (("low", P["sigma"] <= q1), ("mid", (P["sigma"] > q1) & (P["sigma"] <= q2)), ("high", P["sigma"] > q2)):
        terc[lab] = {"n_fomc": int((f & m).sum()), "diff": _point_diff(P["pnl"][m], f[m])}
    okrv = np.isfinite(P["rv30_prev"]) & (P["rv30_prev"] > 0)
    scale = np.abs(P["ret"][okrv]) / P["rv30_prev"][okrv]
    rep = {"label": "MODEL-PRICED", "n": full["n_event"], "first_day": str(P["days"][0]), "last_day": str(P["days"][-1]),
           "pricing": "Black-Scholes, sigma = VIX(T-1)/100, T = 1/252, K = SPY(T-1) close, r = q = 0; P&L as a fraction of spot",
           "full": full, "halves": hv, "mean_premium_fomc": float(P["premium"][f].mean()), "mean_premium_other": float(P["premium"][~f].mean()),
           "ratio_abs_r_over_vix_daily": {"fomc": float(P["ratio"][f].mean()), "other": float(P["ratio"][~f].mean())},
           "scale_check_abs_r_over_rv30": {"fomc": float(scale[f[okrv]].mean()), "other": float(scale[~f[okrv]].mean())},
           "placebo_fomc_pm7": placebo, "excluding_2008_09_and_2020_03": excl_diff, "vix_terciles": terc}
    if full["n_event"] < min_n:
        rep.update(verdict="inconclusive", reason=f"MODEL-PRICED: only {full['n_event']} FOMC days with SPY and VIX (min_n {min_n})")
        return rep
    crit = []
    for lab, h in hv.items():
        ok = None if h["diff"] is None else (h["diff"] < 0 and h["ci"][1] < 0)
        crit.append((f"{lab} FOMC-minus-non-FOMC short-straddle P&L < 0 with 95% CI excluding 0", ok))
    v, why = _verdict(crit)
    rep["verdict"] = v
    rep["reason"] = (f"MODEL-PRICED short 1-day ATM SPY straddle (BS, sigma=VIX(T-1), T=1/252): FOMC minus non-FOMC mean P&L "
                     f"{_bps(full['diff'])} bps of spot over {full['n_event']} FOMC / {full['n_other']} other days; "
                     + "; ".join(f"{lab} {_bps(h['diff'])} bps (95% CI {_ci_bps(h['ci'])}, {h['n_event']} FOMC days)" for lab, h in hv.items())
                     + f"; |r|/(VIX/sqrt252) FOMC {rep['ratio_abs_r_over_vix_daily']['fomc']:.2f} vs other {rep['ratio_abs_r_over_vix_daily']['other']:.2f}; "
                     f"placebo +/-7d {_bps(placebo['diff'])} bps; ex Sep-2008/Mar-2020 {_bps(excl_diff['diff'])} bps — {why}")
    return rep


def btc_event_straddle(days, closes, dvol: dict, fomc_days, start: str = "2021-04-01", vix: Optional[dict] = None,
                       block: int = 10, n_boot: int = 2000, seed: int = 0, min_n: int = 40) -> dict:
    """T-221 (MODEL-PRICED): 1-day ATM BTC straddle, sigma = DVOL at 00:00 UTC of day D (the close of the D-1 daily candle),
    T = 1/365, strike and sale at the 00:00 UTC price (BTC-USD close of the D-1 UTC bar), settled at the next 00:00 UTC
    (close of the D bar). Pass: FOMC-minus-non-FOMC mean short P&L < 0 with the 95% CI excluding 0. Controls reported:
    weekday-only non-FOMC days, coin (BTC) accounting sign, VIX-regime split (VIX close of the last US session before D).
    The pooled FOMC+CPI variant needs a CPI release calendar, which is not archived."""
    P = event_straddle_panel(days, closes, dvol, fomc_days, 1.0 / CRYPTO_PPY, CRYPTO_PPY, start=start, max_gap_days=1)
    if len(P["days"]) == 0:
        return {"n": 0, "verdict": "inconclusive", "reason": "no BTC day has a prior-candle DVOL close"}
    f = P["flag"]
    full = group_diff(P["pnl"], f, block, n_boot, seed)
    coin = group_diff(P["pnl_coin"], f, block, n_boot, seed)
    wk = np.array([date.fromisoformat(d).weekday() < 5 for d in P["days"]])
    weekday = group_diff(P["pnl"][wk], f[wk], block, n_boot, seed)
    regime = None
    if vix:
        vk = sorted(vix); va = np.array(vk)
        vlev = np.array([vix[vk[j - 1]] if (j := int(np.searchsorted(va, d, side="left"))) > 0 else np.nan for d in P["days"]])
        ok = np.isfinite(vlev)
        if ok.sum() > 0:
            med = float(np.median(vlev[ok]))
            regime = {"vix_median": med, "diff_low_vix": _point_diff(P["pnl"][ok & (vlev <= med)], f[ok & (vlev <= med)]),
                      "diff_high_vix": _point_diff(P["pnl"][ok & (vlev > med)], f[ok & (vlev > med)])}
    rep = {"label": "MODEL-PRICED", "n": full["n_event"], "first_day": str(P["days"][0]), "last_day": str(P["days"][-1]),
           "pricing": "Black-Scholes, sigma = DVOL(00:00 UTC D)/100, T = 1/365, K = BTC at 00:00 UTC D, r = q = 0; P&L as a fraction of spot",
           "full": full, "coin_accounting": coin, "weekday_only": weekday, "vix_regime": regime,
           "mean_premium_fomc": float(P["premium"][f].mean()), "mean_premium_other": float(P["premium"][~f].mean()),
           "ratio_abs_r_over_dvol_daily": {"fomc": float(P["ratio"][f].mean()), "other": float(P["ratio"][~f].mean())},
           "not_run": ["pooled FOMC+CPI variant: no CPI release calendar archived"]}
    if full["n_event"] < min_n:
        rep.update(verdict="inconclusive", reason=f"MODEL-PRICED: only {full['n_event']} FOMC days with BTC and DVOL since {start} (min_n {min_n})")
        return rep
    ok = None if full["diff"] is None else (full["diff"] < 0 and full["ci"][1] < 0)
    v, why = _verdict([("FOMC-minus-non-FOMC short-straddle P&L < 0 with 95% CI excluding 0", ok)])
    rep["verdict"] = v
    rep["reason"] = (f"MODEL-PRICED short 1-day ATM BTC straddle (BS, sigma=DVOL 00:00 UTC, T=1/365) since {start}: FOMC minus non-FOMC mean P&L "
                     f"{_bps(full['diff'])} bps of spot (95% CI {_ci_bps(full['ci'])}) over {full['n_event']} FOMC / {full['n_other']} other days; "
                     f"|r|/(DVOL/sqrt365) FOMC {rep['ratio_abs_r_over_dvol_daily']['fomc']:.2f} vs other {rep['ratio_abs_r_over_dvol_daily']['other']:.2f}; "
                     f"weekdays only {_bps(weekday['diff'])} bps; coin accounting {_bps(coin['diff'])} bps; CPI-pooled variant not run (no CPI calendar) — {why}")
    return rep


# ------------------------------------------------------------------------------------------- pre-FOMC drift --

def call_spread_overlay(days, closes, vix: dict, event_days, start: str, end: str, width: float = 0.01) -> dict:
    """MODEL-PRICED call spread (long K1 = S(T-1), short K2 = 1.01 S(T-1), expiring the trading day after T): bought at the T-1
    close at sigma = VIX(T-1) with 2/252 left, sold at the T close at sigma = VIX(T) with 1/252 left. P&L in fraction of spot."""
    ev = set(event_days); c = np.asarray(closes, dtype=float); keep = []
    for i in range(1, len(days)):
        d, p = days[i], days[i - 1]
        if start <= d <= end and p in vix and d in vix:
            keep.append(i)
    if not keep:
        return {"n_fomc": 0}
    idx = np.array(keep); s0, s1 = c[idx - 1], c[idx]
    v0 = np.array([vix[days[i - 1]] for i in keep]) / 100; v1 = np.array([vix[days[i]] for i in keep]) / 100
    k1, k2 = s0, s0 * (1 + width)
    debit = bs.price(s0, k1, 2 / EQ_PPY, 0.0, v0, "call") - bs.price(s0, k2, 2 / EQ_PPY, 0.0, v0, "call")
    exitv = bs.price(s1, k1, 1 / EQ_PPY, 0.0, v1, "call") - bs.price(s1, k2, 1 / EQ_PPY, 0.0, v1, "call")
    pnl = (exitv - debit) / s0
    f = np.array([days[i] in ev for i in keep])
    return {"label": "MODEL-PRICED", "n_fomc": int(f.sum()), "mean_pnl_fomc_bps": float(pnl[f].mean() * 1e4) if f.any() else None,
            "mean_pnl_other_bps": float(pnl[~f].mean() * 1e4), "mean_debit_bps": float((debit / s0).mean() * 1e4),
            "fomc_pnl_over_debit": float((pnl[f] / (debit[f] / s0[f])).mean()) if f.any() else None}


def pre_fomc_drift_oos(days, closes, fomc_days, test=("2012-01-01", "2026-12-31"), pre=("1994-01-01", "2011-12-31"),
                       overlay: Optional[tuple] = None, exclude_days=(), block: int = 10, n_boot: int = 2000, n_placebo: int = 2000,
                       seed: int = 0, min_n: int = 100) -> dict:
    """T-215: SPY close(T-1)-to-close(T) return on scheduled FOMC decision days minus the mean return on non-FOMC days,
    2012-2026. Pass: difference > 0 with the 95% CI excluding 0. Reported: Newey-West CI, 1994-2011 split, random-date placebo,
    FOMC mean minus the unconditional mean, MODEL-PRICED 1%-wide call-spread overlay (``overlay`` = (days, unadjusted closes, vix)).
    ``exclude_days`` (unscheduled FOMC days, mapped to the first trading day on or after each) are dropped from the
    non-FOMC group."""
    ev = set(fomc_days); ex = align_to_trading_days(days, exclude_days) - ev
    ds, r = _returns(days, closes, *test)
    keep = np.array([d not in ex for d in ds], dtype=bool); ds, r = ds[keep], r[keep]
    f = np.array([d in ev for d in ds], dtype=bool)
    g = group_diff(r, f, block, n_boot, seed)
    if g["diff"] is None:
        return {"n": int(f.sum()), "verdict": "inconclusive", "reason": f"too few FOMC or non-FOMC days in {test[0]}..{test[1]}"}
    hac = _hac_ci(flag_diff_series(r, f), block)
    dp, rp = _returns(days, closes, *pre); kp = np.array([d not in ex for d in dp], dtype=bool); dp, rp = dp[kp], rp[kp]
    fp = np.array([d in ev for d in dp], dtype=bool)
    pre_g = group_diff(rp, fp, block, n_boot, seed)
    rng = np.random.default_rng(seed); other = np.flatnonzero(~f); ne = int(f.sum()); null = np.empty(n_placebo)
    for b in range(n_placebo):
        pick = rng.choice(other, ne, replace=False); m = np.zeros(len(r), dtype=bool); m[pick] = True
        null[b] = r[pick].mean() - r[~f & ~m].mean()
    p_placebo = float((np.sum(null >= g["diff"]) + 1) / (n_placebo + 1))
    rep = {"n": ne, "window": list(test), "test": g, "hac_ci": hac, "pre_2012": pre_g, "random_date_placebo_p": p_placebo,
           "fomc_minus_unconditional_bps": float((r[f].mean() - r.mean()) * 1e4),
           "note": "close-to-close on T includes the post-statement move; the 13:55 ET exit needs intraday data"}
    if overlay is not None:
        od, oc, vix = overlay
        rep["call_spread_overlay"] = call_spread_overlay(od, oc, vix, fomc_days, *test)
    if ne < min_n:
        rep.update(verdict="inconclusive", reason=f"only {ne} FOMC days in {test[0]}..{test[1]} (min_n {min_n})")
        return rep
    crit = [(f"{test[0][:4]}-{test[1][:4]} FOMC-minus-non-FOMC mean return > 0", g["diff"] > 0),
            ("95% CI excludes 0 (lower bound > 0)", g["ci"][0] > 0)]
    v, why = _verdict(crit)
    rep["verdict"] = v
    ov = rep.get("call_spread_overlay") or {}
    rep["reason"] = (f"SPY FOMC-day close-to-close {g['mean_event']*1e4:+.1f} bps vs non-FOMC {g['mean_other']*1e4:+.1f} bps over {test[0][:4]}-{test[1][:4]} "
                     f"({ne} FOMC days): difference {_bps(g['diff'])} bps, 95% block-bootstrap CI {_ci_bps(g['ci'])} (HAC {_ci_bps(hac)}), "
                     f"random-date placebo p={p_placebo:.3f}; 1994-2011 difference {_bps(pre_g['diff'])} bps"
                     + (f"; MODEL-PRICED 1% call spread FOMC {ov['mean_pnl_fomc_bps']:+.1f} vs other {ov['mean_pnl_other_bps']:+.1f} bps of spot" if ov.get("mean_pnl_fomc_bps") is not None else "")
                     + f" — {why}")
    return rep


def statement_day_effect(days, closes, fomc_days, start: str = "1994-01-01", end: str = "2026-12-31",
                         sub=("2016-01-01", "2026-12-31"), cost_bps: float = 2.0, threshold_bps: float = 15.0,
                         secondary: Optional[dict] = None, block: int = 10, n_boot: int = 2000, seed: int = 0, min_n: int = 200) -> dict:
    """T-341: SPY close-to-close return on scheduled FOMC statement days minus the mean on all other days, net of a
    ``cost_bps`` round trip per statement day. Pass: net difference > 15 bps with studentized block-bootstrap (block 10)
    p < 0.05 (H0: difference <= 0) over 1994-2026 AND a positive 2016-2026 net difference. Secondary assets (QQQ, IWM, TLT,
    GLD, BTC) are reported with Holm-adjusted p-values; the 5 unnamed non-primary variants are not defined and not run."""
    ds, r = _returns(days, closes, start, end)
    ev = set(fomc_days); f = np.array([d in ev for d in ds], dtype=bool)
    net = r - f * cost_bps / 1e4
    g = group_diff(net, f, block, n_boot, seed)
    if g["diff"] is None:
        return {"n": int(f.sum()), "verdict": "inconclusive", "reason": "too few statement days"}
    d = flag_diff_series(net, f)
    p_thr = float(block_bootstrap_pvalue(d - threshold_bps / 1e4, np.zeros_like(d), n_boot=n_boot, block_len=block, seed=seed))
    ms = _range_mask(ds, *sub)
    sub_diff = _point_diff(net[ms], f[ms])
    splits = {}
    for lab, lo, hi in (("pre-2015", "1994-01-01", "2015-12-31"), ("post-2015", "2016-01-01", "2026-12-31"),
                        ("ZLB 2009-2015", "2009-01-01", "2015-12-31")):
        m = _range_mask(ds, lo, hi); splits[lab] = _point_diff(net[m], f[m])
    mz = ~_range_mask(ds, "2009-01-01", "2015-12-31"); splits["excluding ZLB"] = _point_diff(net[mz], f[mz])
    sec = {}
    for sym, (sd, sc) in (secondary or {}).items():
        a, rr = _returns(sd, sc, start, end); fa = np.array([x in ev for x in a], dtype=bool)
        gs = group_diff(rr - fa * cost_bps / 1e4, fa, block, n_boot, seed)
        sec[sym] = {"diff_bps": None if gs["diff"] is None else gs["diff"] * 1e4, "p": gs["p_greater"], "n_fomc": gs["n_event"], "first_day": str(a[0]) if len(a) else None}
    holm = _holm({"SPY": g["p_greater"], **{k: v["p"] for k, v in sec.items() if v["p"] is not None}}) if sec else {}
    rep = {"n": g["n_event"], "n_days": int(len(r)), "cost_bps_round_trip": cost_bps, "net": g, "gross_diff_bps": float(_point_diff(r, f) * 1e4),
           "p_vs_15bps": p_thr, "sub_2016_2026_diff_bps": None if sub_diff is None else sub_diff * 1e4,
           "splits_bps": {k: (None if v is None else v * 1e4) for k, v in splits.items()}, "secondary": sec, "holm_adjusted_p": holm,
           "not_run": ["5 non-primary variants (not specified)", "CPI-overlap flag (no CPI calendar archived)"]}
    if g["n_event"] < min_n:
        rep.update(verdict="inconclusive", reason=f"only {g['n_event']} statement days (min_n {min_n})")
        return rep
    crit = [(f"{start[:4]}-{end[:4]} net difference > {threshold_bps:g} bps", g["diff"] > threshold_bps / 1e4),
            ("block-bootstrap p < 0.05", g["p_greater"] < 0.05),
            (f"{sub[0][:4]}-{sub[1][:4]} net difference > 0", None if sub_diff is None else sub_diff > 0)]
    v, why = _verdict(crit)
    rep["verdict"] = v
    rep["reason"] = (f"SPY statement-day return {g['mean_event']*1e4:+.1f} bps (net of {cost_bps:g} bps) vs other days {g['mean_other']*1e4:+.1f} bps over "
                     f"{g['n_event']} statement days {str(ds[0])}..{str(ds[-1])}: net difference {_bps(g['diff'])} bps (95% CI {_ci_bps(g['ci'])}), "
                     f"p={g['p_greater']:.4f} (H0 diff<=0; p vs 15 bps {p_thr:.3f}); {sub[0][:4]}-{sub[1][:4]} {_bps(sub_diff)} bps"
                     + ("; secondary Holm p " + ", ".join(f"{k} {sec[k]['diff_bps']:+.1f} bps p_holm={holm.get(k, float('nan')):.3f}" for k in sec if sec[k]['diff_bps'] is not None) if sec else "")
                     + f" — {why}")
    return rep


# -------------------------------------------------------------------------------------------- FOMC-cycle weeks --

def weeks_from_origins(n: int, origins) -> np.ndarray:
    """FOMC-cycle week of each of n trading days given origin (day-0) indices: week 0 = days -1..+3, then 5-day weeks,
    each cycle running until the next origin's day -2. -1 = before the first cycle."""
    o = np.unique(np.asarray(origins, dtype=int))
    i = np.arange(n)
    j = np.searchsorted(o - 1, i, side="right") - 1
    w = np.full(n, -1, dtype=int)
    ok = j >= 0
    w[ok] = (i[ok] - o[j[ok]] + 1) // 5
    return w


def _origins(days: Sequence[str], statement_days) -> np.ndarray:
    arr = np.array(days)
    return np.array(sorted({int(np.searchsorted(arr, s, side="left")) for s in statement_days if days[0] <= s <= days[-1]}), dtype=int)


def fomc_cycle_weeks(days: Sequence[str], statement_days) -> np.ndarray:
    """Cieslak-Morse-Vissing-Jorgensen / Cucinelli-Lucca-Moench cycle week of every day in ``days``."""
    return weeks_from_origins(len(days), _origins(days, statement_days))


def _even_odd_diff(r: np.ndarray, w: np.ndarray) -> Optional[float]:
    e = np.isin(w, EVEN_WEEKS); o = np.isin(w, ODD_WEEKS)
    if e.sum() == 0 or o.sum() == 0:
        return None
    return float(r[e].mean() - r[o].mean())


def even_week_effect(days, closes, statement_days, start: str = "1994-01-01", end: str = "2026-12-31",
                     halves=(("1994-2009", "1994-01-01", "2009-12-31"), ("2010-2026", "2010-01-01", "2026-12-31")),
                     sub=("2017-01-01", "2026-12-31"), cost_bps: float = 2.0, threshold_bps: float = 5.0, block: int = 5,
                     n_boot: int = 2000, n_placebo: int = 1000, seed: int = 0, min_n: int = 1500, secondary: Optional[dict] = None) -> dict:
    """T-342: SPY mean daily return in even FOMC-cycle weeks (0, 2, 4, 6) minus odd weeks (1, 3, 5, 7); weeks >= 8 are rare
    long-gap days and are left out of both groups. Week 0 = trading days -1..+3 around the scheduled statement day, then
    5-trading-day weeks until the next meeting's day -2. A ``cost_bps`` round trip is charged on the first day of every
    even-week holding block. Pass: net difference > 5 bps/day with studentized block-bootstrap (block 5) p < 0.05; positive
    net difference in 1994-2009, 2010-2026 and 2017-2026; random-offset placebo p < 0.05 (1,000 calendars, every cycle
    origin shifted by an independent uniform 1-30 trading days)."""
    c = np.asarray(closes, dtype=float)
    origins = _origins(days, statement_days)
    w_all = weeks_from_origins(len(days), origins)
    r_all = c[1:] / c[:-1] - 1; d_all = np.array(days[1:])
    rm = _range_mask(d_all, start, end)
    r, ds, w = r_all[rm], d_all[rm], w_all[1:][rm]
    even = np.isin(w, EVEN_WEEKS); odd = np.isin(w, ODD_WEEKS); incl = even | odd
    entries = even & ~np.concatenate([[False], even[:-1]])
    net = r - entries * cost_bps / 1e4
    x, fe = net[incl], even[incl]
    g = group_diff(x, fe, block, n_boot, seed)
    if g["diff"] is None:
        return {"n": int(incl.sum()), "verdict": "inconclusive", "reason": "no even or no odd FOMC-cycle days in range"}
    parts = {}
    for lab, lo, hi in tuple(halves) + ((f"{sub[0][:4]}-{sub[1][:4]}", sub[0], sub[1]),):
        m = _range_mask(ds, lo, hi) & incl
        parts[lab] = _point_diff(net[m], even[m])
    gross = _even_odd_diff(r, w)
    rng = np.random.default_rng(seed); null = np.empty(n_placebo)
    for b in range(n_placebo):
        sh = origins + rng.integers(1, 31, size=len(origins))
        wb = weeks_from_origins(len(days), sh)[1:][rm]
        null[b] = _even_odd_diff(r, wb)
    p_placebo = float((np.sum(null >= gross) + 1) / (n_placebo + 1))
    flips = {f"shift_{k}_trading_days": _even_odd_diff(r, weeks_from_origins(len(days), origins + k)[1:][rm]) for k in (5, 15)}
    years = max((date.fromisoformat(str(ds[-1])) - date.fromisoformat(str(ds[0]))).days / 365.25, 1e-9)
    sec = {}
    for sym, (sd, sc) in (secondary or {}).items():
        sc = np.asarray(sc, dtype=float); ws = fomc_cycle_weeks(sd, statement_days)[1:]; rs = sc[1:] / sc[:-1] - 1
        ms = _range_mask(np.array(sd[1:]), start, end)
        sec[sym] = {"gross_diff_bps": None if (z := _even_odd_diff(rs[ms], ws[ms])) is None else z * 1e4, "first_day": sd[1] if len(sd) > 1 else None}
    rep = {"n": int(incl.sum()), "week_definition": "week 0 = trading days -1..+3 around the scheduled statement day (day 0), then 5-trading-day weeks until the next meeting's day -2; even = 0,2,4,6, odd = 1,3,5,7, weeks >= 8 excluded",
           "n_even_days": int(even.sum()), "n_odd_days": int(odd.sum()), "n_excluded_week8plus": int((w >= 8).sum()),
           "round_trips_per_year": float(entries.sum() / years), "cost_bps_round_trip": cost_bps, "net": g, "gross_diff_bps": gross * 1e4,
           "parts_net_bps": {k: (None if v is None else v * 1e4) for k, v in parts.items()}, "placebo_p": p_placebo,
           "placebo_mean_bps": float(null.mean() * 1e4), "placebo_q95_bps": float(np.quantile(null, 0.95) * 1e4),
           "parity_flip_shifts_bps": {k: (None if v is None else v * 1e4) for k, v in flips.items()}, "secondary": sec,
           "not_run": ["BTC-USD variant (calendar-day series; trading-day week index undefined)", "Holm over the 4 unnamed variants"]}
    if rep["n"] < min_n:
        rep.update(verdict="inconclusive", reason=f"only {rep['n']} cycle days (min_n {min_n})")
        return rep
    crit = [(f"net difference > {threshold_bps:g} bps/day", g["diff"] > threshold_bps / 1e4), ("block-bootstrap p < 0.05", g["p_greater"] < 0.05)]
    for lab, v in parts.items():
        crit.append((f"{lab} net difference > 0", None if v is None else v > 0))
    crit.append(("random-offset placebo p < 0.05", p_placebo < 0.05))
    v, why = _verdict(crit)
    rep["verdict"] = v
    rep["reason"] = (f"SPY even FOMC-cycle weeks {g['mean_event']*1e4:+.2f} bps/day (net of {cost_bps:g} bps per block, {rep['round_trips_per_year']:.0f} blocks/yr) "
                     f"vs odd {g['mean_other']*1e4:+.2f} bps/day over {rep['n_even_days']}+{rep['n_odd_days']} days {str(ds[0])}..{str(ds[-1])}: net difference "
                     f"{_bps(g['diff'])} bps/day (95% CI {_ci_bps(g['ci'])}), p={g['p_greater']:.4f}; "
                     + ", ".join(f"{k} {_bps(v)}" for k, v in parts.items())
                     + f"; random-offset placebo p={p_placebo:.3f} (gross {gross*1e4:+.2f} vs placebo 95th pct {rep['placebo_q95_bps']:+.2f}); "
                     f"week 0 = days -1..+3 then 5-day weeks — {why}")
    return rep


# -------------------------------------------------------------------------------------------- monetary momentum --

def monetary_momentum(days, closes, dgs2: dict, statement_days, start: str = "1994-01-01", end: str = "2026-12-31",
                      rf: Optional[dict] = None, threshold_bps: float = 5.0, entry_lag: int = 2, horizon: int = 15,
                      cost_bps_leg: float = 2.0, gap_pp: float = 1.0,
                      halves=(("1994-2009", "1994-01-01", "2009-12-31"), ("2010-2026", "2010-01-01", "2026-12-31")),
                      n_perm: int = 10000, n_boot: int = 2000, seed: int = 0, min_n: int = 120) -> dict:
    """T-361: classify each scheduled statement day t by the DGS2 change from the previous DGS2 observation to t
    (expansionary < -5 bps, contractionary > +5 bps). Entry at the SPY close of t+2 (after H.15 publishes DGS2), hold
    15 trading days. Net gap = mean expansionary return - mean contractionary return - 2 x (2 legs x ``cost_bps_leg``)
    (each arm pays its entry and exit legs). Pass: net gap > 1 pp, label-permutation p < 0.05 (labels shuffled across all
    classified meetings, 10,000 draws), both halves positive, and the long-only expansionary arm's Sharpe (daily excess
    returns over T-bills, cash otherwise, sqrt(252)) above buy-and-hold's over the same calendar span. The DGS2 change is
    taken in exact basis points (DGS2 is quoted to 0.01 pp), so an exact 5 bp move is neutral. min_n counts the
    expansionary + contractionary meetings, the ones that enter the gap; fewer -> inconclusive, criteria still reported."""
    c = np.asarray(closes, dtype=float); pos = {d: i for i, d in enumerate(days)}
    gk = sorted(dgs2); ga = np.array(gk)
    ev = []
    skipped = {"no_dgs2": 0, "window_incomplete": 0, "not_trading_day": 0}
    for t in statement_days:
        if not (start <= t <= end) or t > days[-1]:
            continue
        if t not in pos:
            skipped["not_trading_day"] += 1; continue
        j = int(np.searchsorted(ga, t, side="left"))
        if j >= len(gk) or gk[j] != t or j == 0:
            skipped["no_dgs2"] += 1; continue
        i = pos[t]
        if i + entry_lag + horizon >= len(days):
            skipped["window_incomplete"] += 1; continue
        chg = round((dgs2[t] - dgs2[gk[j - 1]]) * 100, 6)              # exact bps: 5.65 -> 5.60 is -5, not -5.00000000000007
        lab = "exp" if chg < -threshold_bps else ("con" if chg > threshold_bps else "neu")
        ev.append((t, chg, lab, c[i + entry_lag + horizon] / c[i + entry_lag] - 1, i + entry_lag))
    if not ev:
        return {"n": 0, "verdict": "inconclusive", "reason": "no scheduled meeting with DGS2 and a complete 15-day window", "skipped": skipped}
    labs = np.array([e[2] for e in ev]); ret = np.array([e[3] for e in ev]); tds = np.array([e[0] for e in ev])
    cost_arm = 2 * cost_bps_leg / 1e4

    def gap(lb, rr):
        a, b = rr[lb == "exp"], rr[lb == "con"]
        return None if (len(a) == 0 or len(b) == 0) else float(a.mean() - b.mean())

    g_gross = gap(labs, ret)
    n_exp, n_con = int((labs == "exp").sum()), int((labs == "con").sum())
    rep = {"n": n_exp + n_con, "n_classified": len(ev), "n_expansionary": n_exp, "n_contractionary": n_con,
           "n_neutral": int((labs == "neu").sum()), "skipped": skipped,
           "definition": f"DGS2 change from the previous DGS2 day to t; +/-{threshold_bps:g} bps; entry close t+{entry_lag}, exit {horizon} trading days later",
           "cost": f"{cost_bps_leg:g} bps per leg; each arm pays 2 legs"}
    if g_gross is None:
        rep.update(verdict="inconclusive", reason="no expansionary or no contractionary meetings"); return rep
    g_net = g_gross - 2 * cost_arm
    rng = np.random.default_rng(seed)
    exp_m, con_m = labs == "exp", labs == "con"
    keys = rng.random((n_perm, len(labs))).argsort(axis=1)
    pe, pc = exp_m[keys], con_m[keys]
    perm = (pe * ret).sum(1) / n_exp - (pc * ret).sum(1) / n_con
    p_perm = float((np.sum(perm >= g_gross) + 1) / (n_perm + 1))
    a, b = ret[exp_m], ret[con_m]
    boot = np.array([rng.choice(a, a.size).mean() - rng.choice(b, b.size).mean() for _ in range(n_boot)]) - 2 * cost_arm
    ci = [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]
    hv = {}
    for lab, lo, hi in halves:
        m = _range_mask(tds, lo, hi); gg = gap(labs[m], ret[m])
        hv[lab] = {"gap_net_pp": None if gg is None else (gg - 2 * cost_arm) * 100, "n_exp": int((labs[m] == "exp").sum()), "n_con": int((labs[m] == "con").sum())}
    mz = _range_mask(tds, "2009-01-01", "2015-12-31"); gz = gap(labs[mz], ret[mz])
    zlb = {"gap_net_pp": None if gz is None else (gz - 2 * cost_arm) * 100, "n_exp": int((labs[mz] == "exp").sum()), "n_con": int((labs[mz] == "con").sum())}
    # long-only expansionary arm vs buy-and-hold over the same span (daily excess returns)
    r_d = c[1:] / c[:-1] - 1; d_d = np.array(days[1:])
    first = int(np.searchsorted(d_d, start, side="left")); last = max(e[4] for e in ev) + horizon      # index into r_d is day index - 1
    span = slice(first, last)
    posn = np.zeros(len(r_d)); costs = np.zeros(len(r_d))
    for t, _, lab, _, ie in ev:
        if lab == "exp":
            posn[ie:ie + horizon] = 1.0                       # returns ending on days ie+1 .. ie+horizon
            costs[ie] += cost_bps_leg / 1e4; costs[ie + horizon - 1] += cost_bps_leg / 1e4
    if rf:
        rk = sorted(rf); ra = np.array(rk)
        rfd = np.array([rf[rk[k - 1]] / 100 / EQ_PPY if (k := int(np.searchsorted(ra, d, side="left"))) > 0 else 0.0 for d in d_d])
    else:
        rfd = np.zeros(len(r_d))
    arm = (posn * (r_d - rfd) - costs)[span]; bh = (r_d - rfd)[span]
    sr_arm, sr_bh = _sr(arm, EQ_PPY), _sr(bh, EQ_PPY)
    sd_obs, sd_lo = _sharpe_diff_lower(arm, bh, EQ_PPY, block=21, n_boot=500, seed=seed)
    rep.update(gap_gross_pp=g_gross * 100, gap_net_pp=g_net * 100, gap_ci_net_pp=[x * 100 for x in ci], permutation_p=p_perm,
               mean_exp_pp=float(a.mean() * 100), mean_con_pp=float(b.mean() * 100), halves=hv, zlb_2009_2015=zlb,
               arm_sharpe=sr_arm, buy_hold_sharpe=sr_bh, sharpe_diff_lower_95=sd_lo, span=[str(d_d[first]), str(d_d[last - 1])],
               arm_days_in_market_share=float(posn[span].mean()), not_run=["^FVX same-day variant", "Polymarket/Kalshi variants", "Holm over the 6 variants"])
    crit = [(f"net gap > {gap_pp:g} pp", g_net * 100 > gap_pp), ("permutation p < 0.05", p_perm < 0.05)]
    for lab, h in hv.items():
        crit.append((f"{lab} net gap > 0", None if h["gap_net_pp"] is None else h["gap_net_pp"] > 0))
    crit.append(("long-only expansionary arm Sharpe > buy-and-hold Sharpe", sr_arm > sr_bh))
    v, why = _verdict(crit)
    rep["criteria"] = {name: ok for name, ok in crit}
    body = (f"SPY 15 trading days from the t+2 close: after {n_exp} expansionary (DGS2 < -{threshold_bps:g} bps) {a.mean()*100:+.2f}% vs "
                     f"{n_con} contractionary {b.mean()*100:+.2f}% of {len(ev)} classified meetings: net gap {g_net*100:+.2f} pp (95% CI {ci[0]*100:+.2f} to {ci[1]*100:+.2f}), "
                     f"permutation p={p_perm:.4f}; " + ", ".join(f"{k} {('n/a' if h['gap_net_pp'] is None else format(h['gap_net_pp'], '+.2f'))} pp" for k, h in hv.items())
                     + f"; ZLB 2009-2015 {('n/a' if zlb['gap_net_pp'] is None else format(zlb['gap_net_pp'], '+.2f'))} pp; long-only arm Sharpe {sr_arm:.2f} vs buy-and-hold {sr_bh:.2f} "
                     f"({rep['span'][0]}..{rep['span'][1]}, excess over T-bills)")
    if n_exp + n_con < min_n:
        rep.update(verdict="inconclusive", criteria_verdict_if_min_n_ignored=v,
                   reason=f"only {n_exp + n_con} expansionary+contractionary meetings (min_n {min_n}); {body} — inconclusive: only "
                          f"{n_exp + n_con} of {len(ev)} classified meetings enter the gap (min_n {min_n}); criteria on this sample, "
                          f"not used for the verdict: {why}")
        return rep
    rep["verdict"] = v
    rep["reason"] = f"{body} — {why}"
    return rep


# ---------------------------------------------------------------------------------------------- GVZ around FOMC --

def index_event_change(idx: dict, event_days, start: str, end: str, n_boot: int = 4000, seed: int = 0) -> dict:
    """Change in an index from the close before each event day to the close after it (index observations strictly
    before and after the event day), with an iid bootstrap CI over events, sign test, and a weekday-matched non-event
    control (same 2-close window around non-event days whose window contains no event day)."""
    ks = sorted(idx); ka = np.array(ks); kpos = {k: i for i, k in enumerate(ks)}
    evs = sorted(e for e in event_days if start <= e <= end)
    ev_set = set(evs); rows = []
    for e in evs:
        j0 = int(np.searchsorted(ka, e, side="left")) - 1; j1 = int(np.searchsorted(ka, e, side="right"))
        if j0 < 0 or j1 >= len(ks):
            continue
        if (date.fromisoformat(ks[j1]) - date.fromisoformat(ks[j0])).days > 7:
            continue
        rows.append((e, idx[ks[j1]] - idx[ks[j0]], math.log(idx[ks[j1]] / idx[ks[j0]]), date.fromisoformat(e).weekday()))
    if not rows:
        return {"n": 0, "mean": None, "ci": [None, None]}
    x = np.array([r[1] for r in rows]); lx = np.array([r[2] for r in rows])
    lo, hi = _mean_ci(x, 1, n_boot, seed)
    k_dec = int((x < 0).sum())
    # weekday-matched control
    ctrl = {}
    for k in ks:
        if not (start <= k <= end) or k in ev_set:
            continue
        i = kpos[k]
        if i == 0 or i + 1 >= len(ks):
            continue
        if any(ks[m] in ev_set for m in (i - 1, i + 1)):
            continue
        if (date.fromisoformat(ks[i + 1]) - date.fromisoformat(ks[i - 1])).days > 7:
            continue
        ctrl.setdefault(date.fromisoformat(k).weekday(), []).append(idx[ks[i + 1]] - idx[ks[i - 1]])
    wd = [r[3] for r in rows]
    ctrl_mean = float(np.mean([np.mean(ctrl[w]) for w in wd if w in ctrl])) if any(w in ctrl for w in wd) else None
    return {"n": len(rows), "first_event": rows[0][0], "last_event": rows[-1][0], "mean": float(x.mean()), "ci": [lo, hi], "median": float(np.median(x)),
            "mean_log_change": float(lx.mean()), "share_declining": float(k_dec / len(x)), "sign_test_p": _binom_tail(k_dec, len(x)),
            "matched_control_mean": ctrl_mean, "event_minus_control": None if ctrl_mean is None else float(x.mean() - ctrl_mean),
            "n_control_days": int(sum(len(v) for v in ctrl.values()))}


def gvz_fomc_change(gvz: dict, fomc_days, vix: Optional[dict] = None, start: str = "2009-10-01", end: str = "2026-09-30",
                    n_boot: int = 4000, seed: int = 0, min_n: int = 100) -> dict:
    """T-273: mean change in GVZ from the close before each scheduled FOMC decision day to the close after it,
    2009-10..2026-09. Pass: mean < 0 with the 95% CI excluding 0. Reported: share declining and sign test, weekday-matched
    non-event control, the same test on VIX (positive control). 30-day VIX-method indices drop mechanically when an event
    leaves their window, so a fall is expected even with no event premium. CPI dates are not archived (CPI repeat not run)."""
    g = index_event_change(gvz, fomc_days, start, end, n_boot, seed)
    rep = {"n": g["n"], "gvz": g, "vix_positive_control": index_event_change(vix, fomc_days, start, end, n_boot, seed) if vix else None,
           "not_run": ["CPI-date repeat (no CPI calendar archived)"]}
    if g["n"] < min_n:
        rep.update(verdict="inconclusive", reason=f"only {g['n']} FOMC decision days with GVZ closes either side in {start}..{end} (min_n {min_n})")
        return rep
    v, why = _verdict([("mean GVZ change < 0 with 95% CI excluding 0", g["mean"] < 0 and g["ci"][1] < 0)])
    rep["verdict"] = v
    vc = rep["vix_positive_control"]
    rep["reason"] = (f"GVZ change from the close before to the close after {g['n']} scheduled FOMC decision days ({g['first_event']}..{g['last_event']}): "
                     f"mean {g['mean']:+.3f} vol pts (95% CI {g['ci'][0]:+.3f} to {g['ci'][1]:+.3f}), {g['share_declining']*100:.0f}% declining (sign-test p={g['sign_test_p']:.4f}); "
                     f"weekday-matched non-event 2-day change {('n/a' if g['matched_control_mean'] is None else format(g['matched_control_mean'], '+.3f'))}"
                     + (f"; VIX positive control {vc['mean']:+.3f} pts (95% CI {vc['ci'][0]:+.3f} to {vc['ci'][1]:+.3f})" if vc and vc.get("mean") is not None else "")
                     + f" — {why}")
    return rep


# ---------------------------------------------------------------------------------------------------- harnesses --

def fomc_spx_event_straddle(archive):
    """T-214: MODEL-PRICED 1-day ATM SPY straddle on FOMC vs non-FOMC days (VIX as IV)."""
    miss = _missing(archive, ["daily-history-SPY", "cboe-VIX-history", "fomc-meetings"])
    if miss:
        return miss
    days, closes = _prices(archive, "SPY", adjusted=False)
    return _wrap(spx_event_straddle(days, closes, _index(archive, "cboe-VIX-history"), _fomc(archive), exclude_days=_fomc_unscheduled(archive)))


def fomc_pre_drift_oos(archive):
    """T-215: SPY FOMC-day close-to-close return minus non-FOMC mean, 2012-2026."""
    miss = _missing(archive, ["daily-history-SPY", "cboe-VIX-history", "fomc-meetings"])
    if miss:
        return miss
    days, closes = _prices(archive, "SPY", adjusted=True)
    du, cu = _prices(archive, "SPY", adjusted=False)
    return _wrap(pre_fomc_drift_oos(days, closes, _fomc(archive), overlay=(du, cu, _index(archive, "cboe-VIX-history")),
                                    exclude_days=_fomc_unscheduled(archive)))


def fomc_btc_event_straddle(archive):
    """T-221: MODEL-PRICED 1-day ATM BTC straddle on FOMC vs non-FOMC days (DVOL as IV), since April 2021."""
    miss = _missing(archive, ["daily-history-BTC-USD", "deribit-dvol-BTC-history", "fomc-meetings"])
    if miss:
        return miss
    days, closes = _prices(archive, "BTC-USD", adjusted=False)
    vix = _index(archive, "cboe-VIX-history") if _has(archive, "cboe-VIX-history") else None
    return _wrap(btc_event_straddle(days, closes, _index(archive, "deribit-dvol-BTC-history"), _fomc(archive), vix=vix))


def fomc_gvz_event_change(archive):
    """T-273: GVZ change from the close before to the close after FOMC decision days, 2009-10..2026-09."""
    miss = _missing(archive, ["cboe-GVZ-history", "fomc-meetings"])
    if miss:
        return miss
    vix = _index(archive, "cboe-VIX-history") if _has(archive, "cboe-VIX-history") else None
    return _wrap(gvz_fomc_change(_index(archive, "cboe-GVZ-history"), _fomc(archive), vix=vix))


def fomc_statement_day_drift(archive):
    """T-341: SPY statement-day return minus other days >= 15 bps (1994-2026), positive 2016-2026."""
    miss = _missing(archive, ["daily-history-SPY", "fomc-meetings"])
    if miss:
        return miss
    days, closes = _prices(archive, "SPY", adjusted=True)
    sec = {s: _prices(archive, s, adjusted=True) for s in ("QQQ", "IWM", "TLT", "GLD", "BTC-USD") if _has(archive, "daily-history-" + s)}
    return _wrap(statement_day_effect(days, closes, _fomc(archive), secondary=sec))


def fomc_cycle_even_weeks(archive):
    """T-342: SPY even-minus-odd FOMC-cycle week daily return >= 5 bps, halves and 2017-2026 positive, placebo p < 0.05."""
    miss = _missing(archive, ["daily-history-SPY", "fomc-meetings"])
    if miss:
        return miss
    days, closes = _prices(archive, "SPY", adjusted=True)
    sec = {"EFA": _prices(archive, "EFA", adjusted=True)} if _has(archive, "daily-history-EFA") else None
    return _wrap(even_week_effect(days, closes, _fomc(archive), secondary=sec))


def fomc_monetary_momentum(archive):
    """T-361: 15-day SPY return from the t+2 close after expansionary vs contractionary DGS2 surprises."""
    miss = _missing(archive, ["daily-history-SPY", "fred-DGS2", "fomc-meetings"])
    if miss:
        return miss
    days, closes = _prices(archive, "SPY", adjusted=True)
    rf = _index(archive, "fred-DTB3") if _has(archive, "fred-DTB3") else None
    return _wrap(monetary_momentum(days, closes, _index(archive, "fred-DGS2"), _fomc(archive), rf=rf))


HARNESSES = {
    "fomc_spx_event_straddle": fomc_spx_event_straddle,
    "fomc_pre_drift_oos": fomc_pre_drift_oos,
    "fomc_btc_event_straddle": fomc_btc_event_straddle,
    "fomc_gvz_event_change": fomc_gvz_event_change,
    "fomc_statement_day_drift": fomc_statement_day_drift,
    "fomc_cycle_even_weeks": fomc_cycle_even_weeks,
    "fomc_monetary_momentum": fomc_monetary_momentum,
}

THEORY_MAP = {
    "T-214": "fomc_spx_event_straddle",
    "T-215": "fomc_pre_drift_oos",
    "T-221": "fomc_btc_event_straddle",
    "T-273": "fomc_gvz_event_change",
    "T-341": "fomc_statement_day_drift",
    "T-342": "fomc_cycle_even_weeks",
    "T-361": "fomc_monetary_momentum",
}
