"""
Batch 13, group ``gaps_russell``: two June Russell reconstitution claims from the 2026-10-20 web sweep (cluster
"russellrecon"), pre-registered before any run, 2026-10-21.
=====================================================================================================================

  * T-736  Dollar-neutral long IJR / short IWM entered at the June recon-day close and closed at the close 20 NYSE
           sessions later, one event per year 2000-2026 (Yahoo adjclose, so the short leg pays dividends). Per event:
           (IJR[R+20]/IJR[R] - 1) - (IWM[R+20]/IWM[R] - 1) - 0.0020 - 0.003 x 20/252. Pass (min_n 25 events): mean
           net > 0 with a one-sided within-year permutation p < 0.05 (each draw takes, for every event year, one
           20-session window starting at a uniformly random session of that year whose whole span avoids recon-20..
           recon+20 sessions, the third Friday of Mar/Jun/Sep/Dec +/-5 sessions and every session after 2026-10-14;
           10,000 draws), both halves' net means > 0 (2000-2014, 2015-2026), and the pooled placebo (the identical rule
           anchored on the last Friday of January, April and October) with a 95% CI covering 0. Reported, not
           criteria: the studentized bootstrap 95% CI over events, recon-20 -> recon (expected < 0), the calendar-July
           spread, an IWM-vs-^RUT cross-check, the DSR in T-385's IJR-IWM family, and the December 2026 forward arm.
  * T-741  g_t = (RVX_t/100)^2 - (252/21) x sum of squared IWM daily log returns over sessions t+1..t+21, every
           trading day of 2010-2026 an entry (no grid phase), windows ending after 2026-10-14 dropped. Treated = the
           window t+1..t+21 contains that year's June recon day; untreated = the same year's entry days whose window
           contains no recon day. d_y = mean g (treated) - mean g (untreated) in year y. Pass (min_n 15 years):
           one-sided 95% lower bound of mean d_y > 0 (studentized bootstrap over years, 10,000 draws), both halves
           (2010-2017, 2018-2026) > 0, the opex-matched contrast (treated minus untreated days whose window holds the
           third Friday of Mar/Sep/Dec and no recon) mean > 0, and the circular 42-day block bootstrap of the daily
           treated-minus-untreated contrast agreeing (rule 11). Leave-one-year-out range reported. A statistic, not a
           trade: no costs.

Conventions
  * Recon calendar (shared by both trials, compiled from FTSE Russell's published rules and dated notices, never from
    the data). ``RECON_JUNE`` holds one date per year with its source:
      - 2000-2003: FTSE Russell, "Four decades of Russell US index reconstitution": "2004 - Reconstitution date changed
        to last Friday in June (previously June 30th)"; membership "takes effect July 1" (PlanSponsor's notices of 11
        June 2001 and 10 June 2002; Madhavan 2003). The recon close is the last session on or before 30 June:
        2000-06-30 (Fri), 2001-06-29 (Fri; the 30th a Saturday), 2002-06-28 (Fri; the 30th a Sunday), 2003-06-30
        (Mon). No year is unsourceable, so none is excluded.
      - 2004-2006: the last Friday of June (FTSE Russell, "Russell US Equity Index Series: history of Ground Rule
        updates", June 2007 entry: "Previously, the reconstitution date fell on the last Friday of June"): 2004-06-25,
        2005-06-24, 2006-06-30 (PlanSponsor, 19 June 2006: Russell "would reconstitute ... on June 30").
      - 2007-2012: the last Friday unless it falls on the 28th-30th, then the Friday before (same June 2007 entry).
      - 2013-2026: the last Friday unless it falls on the 29th or 30th, i.e. the fourth Friday (four-decades note;
        ground-rule history 2016/2020 entries; 26 June 2020 confirmed there).
    The registration's procedure abbreviates 2004-2026 as "the fourth Friday of June". That agrees with the published
    dates in every year except 2006 (fourth Friday 2006-06-23, published 2006-06-30). Decided before any run (the
    conservative reading, rule 11/12 style): T-736 is computed on both calendars, the published one (primary) and the
    literal fourth-Friday rule, and every criterion passes only when both readings pass, fails only when both fail and
    is undecided otherwise. T-741 (2010-2026) is unaffected: the two calendars coincide there. The December 2026 recon
    (2026-12-11) is a forward arm and is not pooled; its +20-session exit lies after the data end, so it is not run.
  * Data. ``batch6c_cal._daily`` (rows available at capture: the 2026-10-14 Yahoo bar is stamped available
    2026-10-15 13:30 UTC, after the bundles' capture, so the Yahoo series end 2026-10-13) and ``_series`` for RVX
    (closes at 16:15 ET, archived available 21:30 UTC). IJR/IWM/^RUT bars match the NYSE rule calendar exactly
    (``calendar_check``: no unexplained gaps, no bars on closed days), so "20 NYSE sessions later" is 20 bars later.
    RVX has no print on 5 IWM sessions (2018-05-01, 2018-12-03, 2019-02-20, 2019-07-05, 2020-10-16): those days are
    not entries (their returns still enter other days' realised windows).
  * Point in time. Both trials take no data-dependent decision: the recon, quad-witching and placebo calendars are
    published in advance; T-736 fills at the official closes (MOC) on calendar dates; T-741's treated flag is calendar
    only, and RVX_t is the 16:15 ET close, 15 minutes after IWM's close: a small look-ahead if read as a tradable entry
    IV, harmless for this statistic (it is not a trade). The realised window t+1..t+21 excludes day t's return.
  * Inference. T-736: permutation p = (#{draw mean >= observed} + 1) / (draws + 1) (house convention; the registered
    raw share is reported too), 10,000 draws escalated one 10,000 batch at a time while the Monte-Carlo band straddles
    0.05 (``batch6c_cal.escalate_p``, cap 100,000); the event CI is a bootstrap-t (i.i.d. events, 10,000 draws); the
    placebo CI is the same bootstrap-t over the pooled placebo events. T-741: ``studentized_p_escalated`` with block 1
    (i.i.d. years; 5 seeds x 2,000 = the registered 10,000, escalated while undecided), whose p < 0.05 is the
    one-sided 95% lower bound > 0 (the bootstrap-t bound itself is reported); the alternative is
    ``batch6c_cal.group_test`` on the pooled daily entries (flag-difference series, circular 42-day blocks), fixed
    before any run. Its estimand is the pooled treated-minus-untreated mean, not mean d_y, so the year-weighted
    analogue (``year_weighted_series``: a daily series whose mean is exactly mean d_y, same 42-day studentized
    bootstrap) is reported next to it after review. Reported only, never a criterion: the decision stays on the
    pre-run reading. The opex-matched contrast's leave-one-year-out range is reported too (its criterion stays
    registered as mean > 0).
  * Rule 10: T-736's entries are the calendar the claim names (rule 10(a)), so there is no grid phase; its null draws
    every eligible start uniformly. T-741 uses every trading day as an entry.
  * Survivorship: none at ETF / index level (IJR, IWM, ^RUT and RVX exist throughout their samples).
"""

from __future__ import annotations

import bisect
import math
from datetime import date, timedelta
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out

SEED = 0
IJR_B = "daily-history-IJR"
IWM_B = "daily-history-IWM"
RUT_B = "daily-history--RUT"
RVX_B = "cboe-RVX-history"
DATA_END = "2026-10-14"            # windows ending after this session are dropped (both trials)
DEC_2026_RECON = "2026-12-11"      # forward arm (T-736), never pooled

SRC_FOUR_DECADES = "https://www.lseg.com/content/dam/ftse-russell/en_us/documents/research/four-decades-russell-reconstitution.pdf"
SRC_GROUND_RULES = ("https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/"
                    "russell-us-equity-indexes-history-of-ground-rule-updates.pdf")
SRC_PS_2001 = "https://www.plansponsor.com/russell-posts-preliminary-reconstitution-results/"
SRC_PS_2002 = "https://www.plansponsor.com/?p=30049"
SRC_PS_2003 = "https://www.plansponsor.com/russell-wraps-up-2003-reconstitution/"
SRC_PS_2006 = "https://www.plansponsor.com/?p=69118"

# One published June recon date per year (the close at which the index changes are implemented) and its source.
RECON_JUNE: dict = {
    2000: ("2000-06-30", "pre-2004 rule 'June 30th' (FTSE Russell four decades); a Friday session"),
    2001: ("2001-06-29", "pre-2004 'June 30th'; membership effective 1 July (PlanSponsor 2001-06-11); the 30th a Saturday"),
    2002: ("2002-06-28", "pre-2004 'June 30th'; 'final index membership will go into effect July 1' (PlanSponsor 2002-06-10)"),
    2003: ("2003-06-30", "pre-2004 'June 30th' (FTSE Russell four decades); 'at the end of June' (PlanSponsor 2003-06-16)"),
    2004: ("2004-06-25", "last Friday of June (2004-2006 rule, FTSE Russell ground-rule history)"),
    2005: ("2005-06-24", "last Friday of June (2004-2006 rule)"),
    2006: ("2006-06-30", "last Friday of June (2004-2006 rule); 'on June 30' (PlanSponsor 2006-06-19)"),
}                                  # 2007-2026 are added below from the documented Friday rules (``documented_rule``)


def last_friday(y: int, m: int) -> date:
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - 4) % 7)


def nth_friday(y: int, m: int, n: int) -> date:
    d = date(y, m, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7 + 7 * (n - 1))


def third_friday(y: int, m: int) -> date:
    return nth_friday(y, m, 3)


def documented_rule(y: int) -> date:
    """The June recon date by FTSE Russell's documented rule of each era (see the module docstring)."""
    if y < 2004:
        d = date(y, 6, 30)
        while not CAL.is_nyse_session(d):
            d -= timedelta(days=1)
        return d
    lf = last_friday(y, 6)
    if y < 2007:
        return lf
    if y < 2013:
        return lf - timedelta(days=7) if lf.day >= 28 else lf
    return lf - timedelta(days=7) if lf.day >= 29 else lf


for _y in range(2007, 2027):
    RECON_JUNE[_y] = (documented_rule(_y).isoformat(),
                      "last Friday unless the 28th-30th, then the Friday before (2007-2012 rule)" if _y < 2013 else
                      "last Friday unless the 29th or 30th, i.e. the fourth Friday (2013- rule)")
del _y


def recon_dates(reading: str = "published", years: Sequence[int] = range(2000, 2027)) -> dict:
    """{year: ISO date}: 'published' = ``RECON_JUNE``; 'fourth_friday' = the registration's literal rule (the fourth
    Friday of June from 2004, the published pre-2004 dates before)."""
    out = {}
    for y in years:
        if reading == "fourth_friday" and y >= 2004:
            out[y] = nth_friday(y, 6, 4).isoformat()
        else:
            out[y] = RECON_JUNE[y][0]
    return out


# ============================================================================================ session calendar ==

def rule_sessions(first: str, last: str) -> list:
    """NYSE rule-calendar sessions in [first, last] (``batch6c_cal.is_nyse_session``)."""
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        if CAL.is_nyse_session(d):
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def band(sessions: Sequence[str], d: str, k: int) -> list:
    """Sessions within k sessions of date d: d itself and k on each side when d is a session; otherwise the k sessions
    before it and the k from the first session after it (a holiday third Friday, e.g. Juneteenth 2026-06-19)."""
    j = bisect.bisect_left(sessions, d)
    if j < len(sessions) and sessions[j] == d:
        return list(sessions[max(0, j - k):j + k + 1])
    return list(sessions[max(0, j - k):j + k])


def expiry_session(d: date) -> date:
    """The options-expiry session of a third Friday: the Friday, or the session before when it is a holiday."""
    while not CAL.is_nyse_session(d):
        d -= timedelta(days=1)
    return d


def _f(x, fmt: str = "+.2f") -> str:
    return "n/a" if x is None or not np.isfinite(x) else format(float(x), fmt)


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:+.{nd}f}%"


def boot_t(x, n_boot: int = 10000, seed: int = SEED, level: float = 0.95) -> dict:
    """Bootstrap-t (studentized, i.i.d.) for the mean of x: two-sided ``level`` CI and the one-sided lower bound."""
    x = np.asarray(x, float)
    n = x.size
    out = {"n": int(n), "mean": float(x.mean()) if n else None, "ci": [None, None], "lower_one_sided": None}
    if n < 8:
        return out
    m, se = float(x.mean()), float(x.std(ddof=1)) / math.sqrt(n)
    if se <= 0:
        out.update(ci=[m, m], lower_one_sided=m)
        return out
    rng = np.random.default_rng(seed)
    xb = x[rng.integers(0, n, size=(n_boot, n))]
    sb = xb.std(axis=1, ddof=1)
    ok = sb > 0
    t = (xb.mean(axis=1)[ok] - m) / (sb[ok] / math.sqrt(n))
    a = (1 - level) / 2
    out.update(ci=[m - float(np.quantile(t, 1 - a)) * se, m - float(np.quantile(t, a)) * se],
               lower_one_sided=m - float(np.quantile(t, level)) * se, se=se)
    return out


# =============================================================================================== T-736 events ==

T736_HOLD = 20
T736_COST = 0.0020                 # 5 bp per leg per side
T736_BORROW = 0.003                # IWM borrow per year, pro rata
T736_SPLIT = 2015                  # halves 2000-2014 / 2015-2026
T736_MIN_N = 25
T736_EXCL_RECON = 20
T736_EXCL_QW = 5
T736_N_PERM = 10000
T736_N_BOOT = 10000
T736_DSR_TRIALS = 36               # T-385's 34 + T-628 (joined the family) + this one: the conservative count
T736_PLACEBO_MONTHS = (1, 4, 10)


def spread_windows(a, b, hold: int = T736_HOLD, cost: float = T736_COST, borrow: float = T736_BORROW) -> tuple:
    """(gross, net) arrays: entry at the close of session i, exit at the close of i + hold (NaN where i + hold is past
    the data). net = gross - cost - borrow x hold / 252."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = a.size
    g = np.full(n, np.nan)
    if n > hold:
        g[:n - hold] = a[hold:] / a[:-hold] - b[hold:] / b[:-hold]
    return g, g - cost - borrow * hold / 252.0


def event_index(days: Sequence[str], recon: dict, hold: int = T736_HOLD) -> tuple:
    """({year: entry index}, {year: why missing}): the recon close must be a bar with a bar ``hold`` sessions later."""
    pos = {d: i for i, d in enumerate(days)}
    ev, miss = {}, {}
    for y, d in sorted(recon.items()):
        i = pos.get(d)
        if i is None:
            miss[y] = f"{d} not a bar in the sample"
        elif i + hold >= len(days):
            miss[y] = f"{d}: no close {hold} sessions later by {days[-1]}"
        else:
            ev[y] = i
    return ev, miss


def null_starts(days: Sequence[str], recon: dict, years: Sequence[int], hold: int = T736_HOLD,
                excl_recon: int = T736_EXCL_RECON, excl_qw: int = T736_EXCL_QW) -> dict:
    """{year: eligible start indices}: starts in that calendar year whose whole span (sessions i..i+hold) avoids every
    recon-20..recon+20 band, every third Friday of Mar/Jun/Sep/Dec +/-5 sessions and the end of the data (``days``
    already stops at the data end). Bands are taken on the NYSE rule calendar, so they are right at the sample edges."""
    days = list(days)
    if not days:
        return {y: np.array([], int) for y in years}
    y0, y1 = int(days[0][:4]), int(days[-1][:4])
    rv = sorted(recon.values())
    lo = min([date(y0, 1, 1)] + [date.fromisoformat(rv[0])] * bool(rv)) - timedelta(days=60)
    hi = max([date(y1, 12, 31)] + [date.fromisoformat(rv[-1])] * bool(rv)) + timedelta(days=60)
    rs = rule_sessions(lo.isoformat(), hi.isoformat())        # every banned date lies inside, so no band is clipped
    banned = set()
    for d in recon.values():
        banned.update(band(rs, d, excl_recon))
    for y in range(y0, y1 + 1):
        for m in (3, 6, 9, 12):
            banned.update(band(rs, third_friday(y, m).isoformat(), excl_qw))
    bad = np.array([d in banned for d in days], int)
    n = len(days)
    cb = np.concatenate([[0], np.cumsum(bad)])
    ok = np.zeros(n, bool)
    if n > hold:
        i = np.arange(n - hold)
        ok[i] = (cb[i + hold + 1] - cb[i]) == 0
    yr = np.array([int(d[:4]) for d in days])
    return {y: np.flatnonzero(ok & (yr == y)) for y in years}


def perm_test(W, eligible: dict, years: Sequence[int], obs: float, n_perm: int = T736_N_PERM, seed: int = SEED,
              max_batches: Optional[int] = None) -> dict:
    """Within-year permutation null of the mean over event years: each draw takes one eligible window per event year.
    (p_greater, p_less) by ``_perm_p`` ((k + 1) / (n + 1)), escalated while undecided; the raw registered share
    #{draw >= observed} / draws and the null mean from the first batch."""
    W = np.asarray(W, float)
    E = [np.asarray(eligible.get(y, []), int) for y in years]
    empty = [y for y, e in zip(years, E) if e.size == 0]
    if empty or not years:
        return {"p_greater": None, "p_less": None, "draws": 0, "raw_share": None, "null_mean": None, "years_without_null": empty}

    def draws(j):
        rng = np.random.default_rng(seed + j)
        s = np.zeros(n_perm)
        for e in E:
            s += W[e[rng.integers(0, e.size, n_perm)]]
        return s / len(E)

    pg, pl, nd = CAL.escalate_p(lambda j: CAL._perm_p(obs, draws(j)), n_perm, 1,
                                CAL.MAX_PERM_BATCHES if max_batches is None else max_batches)
    d0 = draws(0)
    return {"p_greater": pg, "p_less": pl, "draws": nd, "raw_share": float(np.mean(d0 >= obs)),
            "null_mean": float(d0.mean()), "null_sd": float(d0.std()), "eligible_per_year": {y: int(e.size) for y, e in zip(years, E)},
            "years_without_null": []}


def placebo_index(days: Sequence[str], years: Sequence[int], months: Sequence[int] = T736_PLACEBO_MONTHS,
                  hold: int = T736_HOLD) -> list:
    """[(label, entry index)]: the last Friday of each placebo month (the session before it when closed) with a close
    ``hold`` sessions later inside the data."""
    out = []
    if not days:
        return out
    for y in years:
        for m in months:
            d = last_friday(y, m)
            while not CAL.is_nyse_session(d):
                d -= timedelta(days=1)
            iso = d.isoformat()
            if iso < days[0]:
                continue
            i = bisect.bisect_left(days, iso)
            if i < len(days) and days[i] == iso and i + hold < len(days):
                out.append((f"{y}-{m:02d}", i))
    return out


def t736_reading(days, ijr, iwm, recon: dict, n_perm: int = T736_N_PERM, max_batches: Optional[int] = None) -> dict:
    """One calendar reading of T-736: events, the net mean, the within-year permutation p and the halves."""
    G, W = spread_windows(ijr, iwm)
    ev, miss = event_index(days, recon)
    years = sorted(ev)
    x = np.array([W[ev[y]] for y in years])
    obs = float(x.mean()) if x.size else float("nan")
    elig = null_starts(days, recon, years)
    pt = perm_test(W, elig, years, obs, n_perm, SEED, max_batches) if x.size else {"p_greater": None, "p_less": None, "draws": 0}
    h1 = np.array([W[ev[y]] for y in years if y < T736_SPLIT])
    h2 = np.array([W[ev[y]] for y in years if y >= T736_SPLIT])
    return {"years": years, "dates": {y: days[ev[y]] for y in years}, "exits": {y: days[ev[y] + T736_HOLD] for y in years},
            "net": x, "gross": np.array([G[ev[y]] for y in years]), "mean": obs, "perm": pt, "missing": miss,
            "halves": [float(h1.mean()) if h1.size else None, float(h2.mean()) if h2.size else None],
            "n_halves": [int(h1.size), int(h2.size)], "ev": ev}


def _sig_ok(mean: float, pg, draws) -> Optional[bool]:
    """'mean > 0 with one-sided p < 0.05': False when the mean is not positive or p decides >= 0.05, None while p is
    undecided."""
    if mean is None or not np.isfinite(mean) or pg is None:
        return None
    if not mean > 0:
        return False
    return CAL.decide_p(pg, draws)


def b13_gaps_russell_ijr_iwm_post_recon(archive):
    """T-736: long IJR / short IWM from the June recon close to +20 sessions, net of costs and borrow."""
    miss = B7C._missing(archive, [IJR_B, IWM_B])
    if miss:
        return miss
    days, (ijr, iwm) = CAL._align(CAL._daily(archive, IJR_B, "adjclose"), CAL._daily(archive, IWM_B, "adjclose"))
    keep = [i for i, d in enumerate(days) if d <= DATA_END]
    days, ijr, iwm = [days[i] for i in keep], ijr[keep], iwm[keep]
    cal = CAL.calendar_check(days)
    readings = {"published": t736_reading(days, ijr, iwm, recon_dates("published")),
                "fourth_friday": t736_reading(days, ijr, iwm, recon_dates("fourth_friday"))}
    differ = {y: (recon_dates("published")[y], recon_dates("fourth_friday")[y]) for y in range(2000, 2027)
              if recon_dates("published")[y] != recon_dates("fourth_friday")[y]}
    P = readings["published"]
    n = int(P["net"].size)
    ci = boot_t(P["net"], T736_N_BOOT)

    # ---- placebo (independent of the recon reading)
    _G, W = spread_windows(ijr, iwm)
    pl_idx = placebo_index(days, range(2000, 2027))
    pl_x = np.array([W[i] for _, i in pl_idx])
    pl_ci = boot_t(pl_x, T736_N_BOOT)
    pl_by_m = {m: float(np.mean([W[i] for lab, i in pl_idx if lab.endswith(f"-{m:02d}")])) for m in T736_PLACEBO_MONTHS}
    pl_ok = None if pl_ci["ci"][0] is None else bool(pl_ci["ci"][0] <= 0.0 <= pl_ci["ci"][1])

    # ---- criteria, each read on both calendars (rule 11/12: pass when both pass, fail when both fail)
    sig = {k: _sig_ok(r["mean"], r["perm"]["p_greater"], r["perm"]["draws"]) for k, r in readings.items()}
    sig_dec = all(CAL.decide_p(r["perm"]["p_less"], r["perm"]["draws"]) is True for r in readings.values())
    halves_ok = {k: (None if any(h is None for h in r["halves"]) else all(h > 0 for h in r["halves"])) for k, r in readings.items()}

    def rd(k):
        r = readings[k]
        return (f"{k} calendar: mean {_pc(r['mean'], 3)} over {r['net'].size} events, permutation p "
                f"{CAL._mc(r['perm']['p_greater'], r['perm']['draws'])} (raw share {_f(r['perm'].get('raw_share'), '.4f')}; "
                f"null mean {_pc(r['perm'].get('null_mean'), 3)})")

    rows = [(f"primary-window net mean > 0 with one-sided within-year permutation p < 0.05 [{rd('published')}; "
             f"{rd('fourth_friday')}]", CAL._agree(sig.values()), sig_dec),
            (f"both halves' net means > 0 (published: 2000-2014 {_pc(P['halves'][0], 3)} over {P['n_halves'][0]}, "
             f"2015-2026 {_pc(P['halves'][1], 3)} over {P['n_halves'][1]}; fourth-Friday: "
             f"{_pc(readings['fourth_friday']['halves'][0], 3)} / {_pc(readings['fourth_friday']['halves'][1], 3)})",
             CAL._agree(halves_ok.values()), False),
            (f"placebo (last Friday of Jan/Apr/Oct, same rule) pooled mean {_pc(pl_ci['mean'], 3)} over {pl_x.size} "
             f"windows with 95% CI [{_pc(pl_ci['ci'][0], 3)}, {_pc(pl_ci['ci'][1], 3)}] covering 0", pl_ok, False)]
    rows = CAL._undecided(rows)
    verdict, why, crit = CAL._judge(rows, n, T736_MIN_N, "recon events")

    # ---- reported only
    ev = P["ev"]
    G, _W = spread_windows(ijr, iwm)
    pre = np.array([G[ev[y] - T736_HOLD] for y in P["years"] if ev[y] - T736_HOLD >= 0])
    pre_net = pre - T736_COST - T736_BORROW * T736_HOLD / 252
    july = []
    for y in range(2000, 2027):
        jun = [i for i, d in enumerate(days) if d[:7] == f"{y}-06"]
        jul = [i for i, d in enumerate(days) if d[:7] == f"{y}-07"]
        if jun and jul and days[jul[-1]] <= DATA_END and (y < 2026 or days[-1] >= f"{y}-07-31"):
            a, b = jun[-1], jul[-1]
            july.append(ijr[b] / ijr[a] - iwm[b] / iwm[a])
    july = np.array(july)
    rut = None
    if B7C._has(archive, RUT_B):
        rd_, rc = CAL._daily(archive, RUT_B, "close")
        rp = {d: v for d, v in zip(rd_, rc)}
        td = []
        legs = []
        for y in P["years"]:
            i, j = ev[y], ev[y] + T736_HOLD
            if days[i] in rp and days[j] in rp:
                iw = iwm[j] / iwm[i] - 1
                ru = rp[days[j]] / rp[days[i]] - 1
                td.append(iw - ru); legs.append((iw, ru))
        if td:
            lg = np.array(legs)
            rut = {"events": len(td), "mean_iwm_minus_rut": float(np.mean(td)), "max_abs_diff": float(np.max(np.abs(td))),
                   "corr": float(np.corrcoef(lg[:, 0], lg[:, 1])[0, 1]) if len(td) > 2 else None}
    dsr = None
    try:
        from mandel.experiments import batch4_fact as FACT
        from mandel.experiments.batch6c_mom import _dsr_brief, family_dsr
        from mandel.validation.backtest_eval import sharpe_ratio
        fam = FACT.family_sharpes(archive)
        own = float(sharpe_ratio(P["net"]))
        scaled = [float(v) * math.sqrt(T736_HOLD) for v in fam.values() if v is not None and math.isfinite(v)]
        d = family_dsr(P["net"], [own] + scaled, T736_DSR_TRIALS)
        d35 = family_dsr(P["net"], [own] + scaled, T736_DSR_TRIALS - 1)
        dsr = {"at_36": d, "at_35": d35, "brief": _dsr_brief(d), "event_sharpe": own, "family_daily_sharpes": fam}
    except (KeyError, FileNotFoundError, ValueError, IndexError, TypeError, ZeroDivisionError, ImportError) as e:  # reported only
        dsr = {"error": f"{type(e).__name__}: {e}"}

    reason = (f"IJR-IWM dollar-neutral, recon close -> +{T736_HOLD} sessions, net of {T736_COST * 1e4:.0f} bp round trip and "
              f"{T736_BORROW:.1%}/yr IWM borrow, {n} June recons {P['years'][0]}-{P['years'][-1]} (Yahoo adjclose to "
              f"{days[-1]}): mean net {_pc(P['mean'], 3)} (gross {_pc(float(P['gross'].mean()), 3)}), bootstrap-t 95% CI "
              f"[{_pc(ci['ci'][0], 3)}, {_pc(ci['ci'][1], 3)}], {int((P['net'] > 0).sum())} of {n} positive; "
              f"within-year permutation p {CAL._mc(P['perm']['p_greater'], P['perm']['draws'])}; halves "
              f"{_pc(P['halves'][0], 3)} / {_pc(P['halves'][1], 3)}; placebo {_pc(pl_ci['mean'], 3)} CI "
              f"[{_pc(pl_ci['ci'][0], 3)}, {_pc(pl_ci['ci'][1], 3)}]; calendars differ only in "
              + (", ".join(f"{y} ({a} published vs {b} fourth Friday)" for y, (a, b) in differ.items()) or "no year")
              + f"; reported: recon-20 -> recon net {_pc(float(pre_net.mean()) if pre_net.size else None, 3)} (expected < 0), "
              f"calendar July gross {_pc(float(july.mean()) if july.size else None, 3)} over {july.size} Julys"
              + (f", IWM minus ^RUT over the windows {_pc(rut['mean_iwm_minus_rut'], 3)} (max |diff| {_pc(rut['max_abs_diff'], 2)})" if rut else "")
              + (f", DSR at {T736_DSR_TRIALS} trials {dsr['brief']}" if dsr and "brief" in dsr else "")
              + f"; December 2026 forward arm ({DEC_2026_RECON}) not run: its exit is after the data end. "
              f"Recon dates are FTSE Russell's published calendar (pre-2004 June 30 rule, 2004-2006 last Friday, then the "
              f"documented Friday rules), never data-detected — {why}")
    stat = {"n_events": n, "mean_net": P["mean"], "mean_gross": float(P["gross"].mean()), "ci_bootstrap_t": ci["ci"],
            "events": [{"year": y, "entry": P["dates"][y], "exit": P["exits"][y], "net": float(P["net"][k]),
                        "gross": float(P["gross"][k])} for k, y in enumerate(P["years"])],
            "readings": {k: {"mean": r["mean"], "perm": r["perm"], "halves": r["halves"], "n": int(r["net"].size),
                             "missing": r["missing"]} for k, r in readings.items()},
            "calendar_differences": differ, "placebo": {"n": int(pl_x.size), "mean": pl_ci["mean"], "ci": pl_ci["ci"],
                                                        "by_month": pl_by_m},
            "pre_window_gross_mean": float(pre.mean()) if pre.size else None,
            "pre_window_net_mean": float(pre_net.mean()) if pre_net.size else None,
            "july_gross_mean": float(july.mean()) if july.size else None, "july_n": int(july.size),
            "rut_cross_check": rut, "dsr": dsr, "calendar_check": {k: (v if isinstance(v, int) else len(v)) for k, v in cal.items()},
            "forward_arm": {"date": DEC_2026_RECON, "status": "not run: exit after the data end; never pooled"},
            "recon_calendar": {y: RECON_JUNE[y] for y in range(2000, 2027)},
            "sources": [SRC_FOUR_DECADES, SRC_GROUND_RULES, SRC_PS_2001, SRC_PS_2002, SRC_PS_2003, SRC_PS_2006],
            "criteria": crit}
    return _out(stat, n, verdict, reason)


# ================================================================================================ T-741 panel ==

T741_WIN = 21
T741_YEARS = (2010, 2026)
T741_SPLIT = 2018                  # halves 2010-2017 / 2018-2026
T741_MIN_N = 15
T741_BLOCK = 42
T741_N_BOOT = 2000                 # x 5 seeds = the registered 10,000, escalated while undecided
T741_N_SEEDS = 5


def gap_panel(days: Sequence[str], adj, rvx: dict, recon: dict, years: tuple = T741_YEARS, win: int = T741_WIN) -> dict:
    """Every entry day t (a bar with an RVX close that day and ``win`` bars after it inside ``days``): implied
    (RVX_t/100)^2, realised (252/win) x sum of squared log returns over bars t+1..t+win, g = implied - realised, and
    calendar flags: treated (a recon session in t+1..t+win) and opex (a Mar/Sep/Dec expiry session in t+1..t+win)."""
    days = list(days)
    adj = np.asarray(adj, float)
    n = len(days)
    r2 = np.zeros(n)
    if n > 1:
        r2[1:] = np.log(adj[1:] / adj[:-1]) ** 2
    c = np.cumsum(r2)
    pos = {d: i for i, d in enumerate(days)}
    mark_r, mark_o = np.zeros(n), np.zeros(n)
    for d in recon.values():
        if d in pos:
            mark_r[pos[d]] = 1
    if days:
        for y in range(int(days[0][:4]), int(days[-1][:4]) + 1):
            for m in (3, 9, 12):
                e = expiry_session(third_friday(y, m)).isoformat()
                if e in pos:
                    mark_o[pos[e]] = 1
    cr, co = np.cumsum(mark_r), np.cumsum(mark_o)
    out = {k: [] for k in ("day", "year", "implied", "realised", "g", "treated", "opex")}
    no_rvx = []
    for i in range(max(0, n - win)):
        y = int(days[i][:4])
        if not years[0] <= y <= years[1]:
            continue
        iv = rvx.get(days[i])
        if iv is None:
            no_rvx.append(days[i])
            continue
        imp = (float(iv) / 100.0) ** 2
        rv = 252.0 / win * float(c[i + win] - c[i])
        out["day"].append(days[i]); out["year"].append(y); out["implied"].append(imp); out["realised"].append(rv)
        out["g"].append(imp - rv)
        out["treated"].append(bool(cr[i + win] - cr[i] > 0)); out["opex"].append(bool(co[i + win] - co[i] > 0))
    P = {k: np.array(v) for k, v in out.items()}
    P["treated"] = P["treated"].astype(bool) if P["treated"].size else np.zeros(0, bool)
    P["opex"] = P["opex"].astype(bool) if P["opex"].size else np.zeros(0, bool)
    P["year"] = P["year"].astype(int) if P["year"].size else np.zeros(0, int)
    P["no_rvx"] = no_rvx
    return P


def year_contrasts(year, g, treated, control) -> dict:
    """{year: (mean g treated - mean g control, n treated, n control)} for years with both groups."""
    year, g = np.asarray(year, int), np.asarray(g, float)
    treated, control = np.asarray(treated, bool), np.asarray(control, bool)
    out = {}
    for y in sorted(set(year.tolist())):
        m = year == y
        a, b = g[m & treated], g[m & control]
        if a.size and b.size:
            out[y] = (float(a.mean() - b.mean()), int(a.size), int(b.size))
    return out


def year_weighted_series(year, g, treated) -> np.ndarray:
    """Year-weighted analogue of ``batch6c_cal.flag_diff_series``. It returns a daily series, in entry order, whose mean
    is exactly mean over years of (mean g treated - mean g untreated), i.e. the registered mean d_y. Per entry:
    D + (N/Y)/nT_y x (g - cT) when treated and D - (N/Y)/nU_y x (g - cU) otherwise, with cT and cU the means over years
    of the year means. Only years holding both groups enter; Y is their count and N the count of their entries.
    Reported only (the rule-11 decision uses the pre-run pooled ``group_test``)."""
    year, g, treated = np.asarray(year, int), np.asarray(g, float), np.asarray(treated, bool)
    yrs = [y for y in sorted(set(year.tolist())) if (treated & (year == y)).any() and (~treated & (year == y)).any()]
    keep = np.isin(year, yrs)
    year, g, treated = year[keep], g[keep], treated[keep]
    if not yrs:
        return np.zeros(0)
    mT = {y: g[(year == y) & treated].mean() for y in yrs}
    mU = {y: g[(year == y) & ~treated].mean() for y in yrs}
    nT = {y: int(((year == y) & treated).sum()) for y in yrs}
    nU = {y: int(((year == y) & ~treated).sum()) for y in yrs}
    Y, N = len(yrs), g.size
    D = float(np.mean([mT[y] - mU[y] for y in yrs]))
    cT, cU = float(np.mean([mT[y] for y in yrs])), float(np.mean([mU[y] for y in yrs]))
    wT = np.array([N / Y / nT[y] for y in year.tolist()])
    wU = np.array([N / Y / nU[y] for y in year.tolist()])
    return D + np.where(treated, wT * (g - cT), -wU * (g - cU))


def loo_means(vals: dict) -> dict:
    """{key: mean of the other values}: the leave-one-out means of a {year: value} table."""
    ks = sorted(vals)
    v = np.array([vals[k] for k in ks], float)
    return {k: float(np.delete(v, j).mean()) for j, k in enumerate(ks)} if v.size > 1 else {}


def b13_gaps_russell_rvx_vrp_recon(archive):
    """T-741: RVX-minus-realised IWM variance gap, recon windows minus the same year's other windows."""
    miss = B7C._missing(archive, [RVX_B, IWM_B])
    if miss:
        return miss
    days, adj = CAL._daily(archive, IWM_B, "adjclose")
    keep = [i for i, d in enumerate(days) if d <= DATA_END]
    days, adj = [days[i] for i in keep], adj[keep]
    rvx = CAL._series(archive, RVX_B)
    recon = recon_dates("published", range(T741_YEARS[0], T741_YEARS[1] + 1))
    same = recon == recon_dates("fourth_friday", range(T741_YEARS[0], T741_YEARS[1] + 1))
    P = gap_panel(days, adj, rvx, recon)
    dy = year_contrasts(P["year"], P["g"], P["treated"], ~P["treated"])
    ey = year_contrasts(P["year"], P["g"], P["treated"], ~P["treated"] & P["opex"])
    yrs = sorted(dy)
    d = np.array([dy[y][0] for y in yrs])
    n = int(d.size)
    if n < 8:
        return _out({"years": yrs}, n, "inconclusive", f"only {n} years with treated and untreated entry days (rule 9)")
    pg, pl, draws = CAL.studentized_p_escalated(d, 1, T741_N_BOOT, SEED, T741_N_SEEDS)
    bt = boot_t(d, T741_N_BOOT * T741_N_SEEDS)
    # rule-11 alternative: the pooled daily treated-minus-untreated contrast, circular 42-day blocks
    alt = CAL.group_test(P["g"], P["treated"], T741_BLOCK, T741_N_BOOT, SEED, T741_N_SEEDS, max_seeds=CAL.MAX_SEEDS)
    # reported only (added after review, never a criterion): the same bootstrap on the year-weighted series (mean = d-bar)
    yw = year_weighted_series(P["year"], P["g"], P["treated"])
    yw_pg, yw_pl, yw_draws = CAL.studentized_p_escalated(yw, T741_BLOCK, T741_N_BOOT, SEED, T741_N_SEEDS, CAL.MAX_SEEDS)
    alt_yw = {"mean": float(yw.mean()) if yw.size else None, "p_greater": yw_pg, "p_less": yw_pl, "draws": yw_draws,
              "decide_p_greater_lt_005": CAL.decide_p(yw_pg, yw_draws), "n": int(yw.size),
              "role": "reported only: year-weighted analogue of the pooled group_test series (mean = mean d_y); the "
                      "rule-11 decision uses the pre-run pooled reading"}
    prim_ok = None if pg is None else (False if not d.mean() > 0 else CAL.decide_p(pg, draws))
    alt_ok = None if alt["p_greater"] is None else (False if not alt["diff"] > 0 else CAL.decide_p(alt["p_greater"], alt["draws"]))
    dec = CAL.decide_p(pl, draws) is True and CAL.decide_p(alt["p_less"], alt["draws"]) is True
    h1 = np.array([dy[y][0] for y in yrs if y < T741_SPLIT])
    h2 = np.array([dy[y][0] for y in yrs if y >= T741_SPLIT])
    e = np.array([ey[y][0] for y in sorted(ey)])
    loo = {y: float(np.delete(d, k).mean()) for k, y in enumerate(yrs)}
    lo_y, hi_y = min(loo, key=loo.get), max(loo, key=loo.get)
    e_loo = loo_means({y: ey[y][0] for y in ey})                # reported only (the criterion stays mean > 0)
    e_lo_y = min(e_loo, key=e_loo.get) if e_loo else None
    e_hi_y = max(e_loo, key=e_loo.get) if e_loo else None
    e_no2020 = e_loo.get(2020)
    vp = 1e4                                                     # variance in vol-points squared
    rows = [(f"one-sided 95% lower bound of mean d_y > 0 (studentized bootstrap over {n} years: mean "
             f"{d.mean() * vp:+.1f} vol-pt^2, bootstrap-t one-sided lower bound {_f(bt['lower_one_sided'] * vp if bt['lower_one_sided'] is not None else None, '+.1f')}, "
             f"p {CAL._mc(pg, draws)}) with the circular {T741_BLOCK}-day block bootstrap of the daily treated-minus-"
             f"untreated contrast agreeing (pooled difference {alt['diff'] * vp:+.1f} vol-pt^2, p "
             f"{CAL._mc(alt['p_greater'], alt['draws'])}; rule 11: both must pass)", CAL._agree([prim_ok, alt_ok]), dec),
            (f"both halves' mean d_y > 0 (2010-2017 {h1.mean() * vp:+.1f} over {h1.size} years, 2018-2026 "
             f"{h2.mean() * vp:+.1f} over {h2.size})", bool(h1.size and h2.size and h1.mean() > 0 and h2.mean() > 0), False),
            (f"opex-matched contrast (treated minus untreated windows holding the Mar/Sep/Dec third Friday) mean > 0 "
             f"({e.mean() * vp:+.1f} vol-pt^2 over {e.size} years)", bool(e.size and e.mean() > 0), False)]
    rows = CAL._undecided(rows)
    verdict, why, crit = CAL._judge(rows, n, T741_MIN_N, "years")
    tr = P["treated"]
    reason = (f"RVX^2 minus 21-session realised IWM variance (sessions t+1..t+21, adjclose log returns), every entry day "
              f"{P['day'][0]}..{P['day'][-1]} ({P['g'].size} entries, {int(tr.sum())} treated), {n} years: treated "
              f"mean g {P['g'][tr].mean() * vp:+.1f} vs untreated {P['g'][~tr].mean() * vp:+.1f} vol-pt^2 (all days "
              f"{P['g'].mean() * vp:+.1f}, the T-65 baseline); mean d_y {d.mean() * vp:+.1f} (bootstrap-t 95% CI "
              f"[{bt['ci'][0] * vp:+.1f}, {bt['ci'][1] * vp:+.1f}]), {int((d > 0).sum())} of {n} years positive, "
              f"one-sided p {CAL._mc(pg, draws)} (p_less {CAL._mc(pl, draws)}); halves {h1.mean() * vp:+.1f} / "
              f"{h2.mean() * vp:+.1f}; opex-matched {e.mean() * vp:+.1f} ({int((e > 0).sum())} of {e.size} years "
              f"positive; leave-one-year-out {_f(e_loo[e_lo_y] * vp if e_lo_y is not None else None, '+.1f')} (without "
              f"{e_lo_y}) to {_f(e_loo[e_hi_y] * vp if e_hi_y is not None else None, '+.1f')} (without {e_hi_y})"
              + ("" if e_no2020 is None or 2020 in (e_lo_y, e_hi_y) else f", without 2020 {e_no2020 * vp:+.1f}")
              + f"; the criterion is the registered point mean > 0); 42-day block alternative p "
              f"{CAL._mc(alt['p_greater'], alt['draws'])} on the pre-run pooled reading (decisive), year-weighted reading "
              f"(mean = mean d_y {_f(alt_yw['mean'] * vp if alt_yw['mean'] is not None else None, '+.1f')}, reported "
              f"only) p {CAL._mc(yw_pg, yw_draws)}, "
              + {True: "decided < 0.05", False: "decided >= 0.05", None: "undecided"}[alt_yw["decide_p_greater_lt_005"]]
              + f"; leave-one-year-out mean d_y {loo[lo_y] * vp:+.1f} (without "
              f"{lo_y}) to {loo[hi_y] * vp:+.1f} (without {hi_y}); 2016 d {dy.get(2016, (float('nan'),))[0] * vp:+.1f}, "
              f"2020 d {dy.get(2020, (float('nan'),))[0] * vp:+.1f}. Recon dates = FTSE Russell's published calendar "
              f"(identical to the fourth Friday in 2010-2026: {same}); RVX closes at 16:15 ET, 15 minutes after IWM, a "
              f"small look-ahead only if read as a tradable entry IV; a statistic, not a trade (no costs); "
              f"{len(P['no_rvx'])} IWM sessions without an RVX print are not entries — {why}")
    stat = {"n_years": n, "mean_d": float(d.mean()), "d_by_year": {y: dy[y][0] for y in yrs},
            "n_treated_by_year": {y: dy[y][1] for y in yrs}, "n_untreated_by_year": {y: dy[y][2] for y in yrs},
            "p_greater": pg, "p_less": pl, "draws": draws, "bootstrap_t": bt,
            "block_alternative": dict(alt, year_weighted_reported_only=alt_yw),
            "halves": [float(h1.mean()), float(h2.mean())], "opex_matched_by_year": {y: ey[y][0] for y in sorted(ey)},
            "opex_matched_mean": float(e.mean()) if e.size else None, "opex_matched_positive_years": int((e > 0).sum()),
            "opex_matched_leave_one_out": e_loo, "opex_matched_mean_without_2020": e_no2020, "leave_one_out": loo,
            "mean_g_treated": float(P["g"][tr].mean()), "mean_g_untreated": float(P["g"][~tr].mean()),
            "mean_g_all": float(P["g"].mean()), "n_entries": int(P["g"].size), "no_rvx_days": P["no_rvx"],
            "recon_dates": recon, "calendars_identical": same, "units": "variance (x 1e4 = vol-points squared)",
            "criteria": crit}
    return _out(stat, n, verdict, reason)


HARNESSES = {"b13_gaps_russell_ijr_iwm_post_recon": b13_gaps_russell_ijr_iwm_post_recon,
             "b13_gaps_russell_rvx_vrp_recon": b13_gaps_russell_rvx_vrp_recon}
THEORY_MAP = {"T-736": "b13_gaps_russell_ijr_iwm_post_recon", "T-741": "b13_gaps_russell_rvx_vrp_recon"}
