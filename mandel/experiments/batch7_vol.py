"""
Batch 7, group ``vol``: three salvage successors pre-registered on 2026-10-20 (mandel/theories/SALVAGE-2026-10-20.md).
=====================================================================================================================

Each claim is tested exactly as worded (its claim, trial.pass and trial.min_n; MANDEL.md section 2, harness rules 1-12).
The parents' in-sample numbers that motivated the successors are not evidence and are not reused as the test sample.

  * T-545  (parent T-237, harness ``batch6_surf.b6_surf_cross_index_vol_spread``) From 2009-09 to 2026-09, after the
           60-day z-score of RVX - VIX falls below -2, (RV_IWM - RV_SPY over the next 21 sessions) - (RVX - VIX at entry)
           is positive on average over non-overlapping events. Pass: mean > 0 with the 95% CI excluding 0, win rate > 0.6,
           both halves positive; min_n 30 events.
  * T-550  (parent T-156) Quote-priced on the DoltHub SPY chains 2019-02..2026-10: a 45-DTE 0.16-delta short strangle on
           each standard monthly expiry, sold at mid - half spread (the bid) and bought back at 50% of the credit or at
           21 DTE (whichever first) at mid + half spread (the ask). Pass: mean P&L per unit of Reg-T margin > 0 with the
           95% CI excluding 0 AND the paired P&L-per-day difference (managed - hold to expiry) > 0 with the 95% CI
           excluding 0; min_n 60 cycles.
  * T-551  (parent T-301, harness ``batch6c_mom.b6c_mom_sma10_drawdown_vs_random``) Over the Cboe PUT index history to
           2026-09, PUT held only in months after SPY (^GSPC before 1993) closed above its 10-month SMA at the prior
           month-end, T-bills otherwise: maximum drawdown reduction >= 30% vs always-PUT with the matched random-timing
           null p < 0.05 AND the excess-return Sharpe difference's 95% lower bound > -0.05; min_n 300 months; the live
           months (after the 2007-06-20 launch) judged separately.

Conventions
  * T-545 reuses T-237's construction (batch6_surf): Cboe closes from ``cboe-RVX-history`` / ``cboe-VIX-history``,
    adjclose of ``daily-history-IWM`` / ``-SPY`` on the sessions all four share; z = ``rolling_z`` of RVX - VIX over the
    trailing 60 sessions (the entry close included: known at that close); RV = ``_fwd_rv`` (annualised zero-mean
    close-to-close log-return volatility, vol points) of returns t -> t+21; ``stud_mean`` / ``two_sided`` (studentized
    circular block bootstrap over events, block 2) for the 95% CI; the parent's win-rate decisiveness rule. The successor
    differs from the parent where its wording does: narrow side only (z < -2, the wide side is not claimed), one-sided
    rule so the statistic is realised minus implied spread (the parent's s = -1 case), an event is the FIRST close with
    z < -2 once the previous event's 21-session hold has ended (no crossing requirement; the parent's crossing rule is a
    reported sensitivity), entries dated 2009-09-01..2026-09-30 with a complete 21-session forward window, 95% two-sided
    (the trial declares no deflation; z-windows 40 and 120 are reported only). Halves = the first and second half of the
    event sequence (T-237's split). Controls (reported): random-entry placebo with the matched count; the unconditional
    realised-minus-implied spread over every day of the window (blocks 2 x 21 sessions). Events sit on data-determined
    dates (rule 10: no grid phase). The VXN/QQQ events of T-237 are not used.
  * T-550 reuses batch6b_dolt's chain parser (``chain_days``: one snapshot per quote day, duplicates dropped, stale-moved
    snapshots kept on their quote day), its strike-by-delta selector (``pick_delta``, vendor |delta| nearest 0.16 within
    0.075, usable = bid > 0 and ask >= bid), its standard monthly expiry calendar (``monthly_expiries``) and settlement
    (intrinsic on SPY's RAW close of the expiry date; early assignment ignored as the parents do). Calendar (rule 10(a)):
    one cycle per standard monthly expiry, entered on the quote day nearest 45 DTE within 38-52 DTE (ties to the longer
    DTE); when that day cannot build the strangle (no usable 0.16-delta leg, put strike not below the call strike) the
    next-nearest day in the window is used (counted). Fills: sell both legs at the bid (= mid - half the quoted spread),
    buy back at the ask (= mid + half the spread) from the same quote rows. Marks (DATA LIMIT): DoltHub lists 3-4
    expiries a day on a strike grid that moves with the spot, so a cycle's expiry is quoted on later days mostly at
    ~25-31 and ~11-15 DTE (rarely at 21) and its exact strikes rarely. A mark is every later quote day before expiry that
    lists the expiry; each leg's ask is the listed ask when its strike is quoted, else interpolated between the nearest
    quoted strikes on either side (at most 6% of S apart, batch6b_dolt.SLOPE_GAP): LINEAR in the ask (above a convex
    price curve, a high buy-back) and LOG-LINEAR (below it in the OTM tails); the two bracket the unquoted ask. Exit at
    the first priceable mark whose buy-back <= 50% of the credit, else the 21-DTE exit read two ways: at the first
    priceable mark at <= 21 DTE, and at the last priceable mark at >= 21 DTE whose next priced listing is below 21 DTE;
    a cycle with no qualifying mark has an unobservable 21-DTE exit and is left out of that reading (never exited at an
    earlier mark nor held to expiry instead). The readings fill unobserved days and do not bound the claim's P&L, so
    they are sensitivities: the criteria are judged on them (all four must agree) only when every cycle's exit is
    observed as worded (a priced mark on every session to the first <= 50% day or to exactly 21 DTE); otherwise both
    criteria are None (rule 9 data limit) and the verdict is capped at inconclusive. Reg-T margin of the
    short strangle (CBOE rule, as batch6b_dolt's naked put): the greater of the two naked requirements (put: premium +
    max(20% S - OTM, 10% K); call: premium + max(20% S - OTM, 10% S)) plus the other leg's premium, premiums at the bid.
    P&L per day in the trade = P&L / entry spot / calendar days held (T-156's unit, bp of spot per day). Intervals:
    studentized circular block bootstrap over the monthly-expiry timeline (``cluster_mean_ci``; months without a cycle
    kept as empty clusters), blocks of 2 and 4 cycles (hold-to-expiry trades overlap the next cycle by at most one
    cycle); a criterion passes only when both blocks pass and fails only when both fail. Point in time: the archive
    stamps every chain row at 22:00Z on its snapshot date, after the 16:15 ET close, so entries and marks use the
    quote day's closing quotes as the live proxy (rule 12: one information set — the same capture decides and fills).
    Commissions are not stated in the claim; $0.65/contract per leg and side is reported. 2020-03 (cycles open across
    it) and 2022 (entries) are reported separately, as are the snapshot-date and entry-day sensitivities.
  * T-551 reuses T-301's construction (batch6c_mom): month-end decision on the signal close, filled at the next
    session's close (``month_grid``), DTB3 accrued calendar day by calendar day (``Bills``/``bill_logcum``, rule 7) when
    out, a proportional cost of 2 bps per switch, maximum drawdown on the monthly compounded equity curve
    (``mdd_from_logwealth``), the matched null that re-places the rule's own out-of-market spells (``spell_paths``,
    count and lengths kept, never merging; p = (1 + #{null MDD <= rule MDD}) / (paths + 1), ties against the rule;
    10,000 paths) and the paired studentized CBB Sharpe difference on excess returns (``sharpe_test``, 12-month blocks,
    5 seeds). The signal is the 10-month SMA of month-end closes: SPY adjclose (T-301's series) once SPY has 10 month-ends
    (from 1993-10), ^GSPC's close before (SPY lists 1993-01-29, so its own SMA is undefined for 1993-01..09). The traded
    series is the Cboe PUT index level on its own sessions; the sample is its continuous daily history (the archived file
    carries only scattered back-test prints before 2007-01, which cannot form monthly returns; named as the data limit).
    Months are hold months (fill to fill), the last ending by 2026-09's final hold. The drawdown-reduction criterion is
    the point estimate (decisive below min_n only when the paired percentile CBB of the reduction, 12-month blocks, has
    its 95% upper end below 30%). Live months = holds starting on or after the 2007-06-20 launch; the same three criteria
    are judged on them (null spells re-placed within the live window). Rule 10(a): the claim names month-end decisions.

Rule 5: below min_n the verdict is never supported and a failing criterion counts only when it fails decisively (its
bound at the pass's own confidence wholly on the wrong side). Rule 9: a missing bundle or too short a window is
inconclusive and names what is missing. Verdicts use ``underlying2._verdict`` through ``batch6_surf._decide``.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections import Counter
from datetime import date, timedelta
from typing import Optional, Sequence

import numpy as np

from mandel.data.dolt_options import is_trading_day
from mandel.experiments import batch6_surf as SURF
from mandel.experiments import batch6b_dolt as DOLT
from mandel.experiments import batch6c_mom as MOM
from mandel.experiments.batch6b_bw import _ci_crit, cboe_index
from mandel.experiments.underlying2 import _verdict

N_BOOT = 2000
SEED = 0

RVX_B = "cboe-RVX-history"
VIX_B = "cboe-VIX-history"
IWM_B = "daily-history-IWM"
SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
PUT_B = "cboe-PUT-history"
DTB3_B = "fred-DTB3"
CHAIN_B = "dolt-chain-SPY"

# T-545
T545_START, T545_END = "2009-09-01", "2026-09-30"
T545_WINDOW, T545_ALT = 60, (40, 120)
T545_THR, T545_HOLD, T545_BLOCK = 2.0, 21, 2
T545_MIN_N, T545_WIN = 30, 0.6
T545_PLACEBO = 2000

# T-550
T550_START, T550_END = "2019-02-01", "2026-10-31"
T550_DTE, T550_TOL, T550_DELTA = 45, 7, 0.16
T550_EXIT_DTE, T550_TARGET = 21, 0.5
T550_MIN_N = 60
T550_BLOCKS = (2, 4)

# T-551
T551_END = "2026-09"
T551_L = 10
T551_COST = 2e-4
T551_RED = 0.30
T551_SHARPE_THR = -0.05
T551_MIN_N = 300
T551_N_NULL = 10000
T551_LAUNCH = "2007-06-20"
T551_MAX_GAP = 10              # calendar days: the continuous daily PUT history starts after the last longer gap

_f, _s = SURF._f, SURF._s


def _ci_txt(ci, nd: int = 2, scale: float = 1.0) -> str:
    lo, hi = (ci or (None, None))[:2]
    if lo is None or hi is None:
        return "95% CI n/a"
    return f"95% CI {lo * scale:+.{nd}f} to {hi * scale:+.{nd}f}"


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


_decide = SURF._decide
_out = SURF._out


# ============================================================================== T-545: RVX - VIX narrow side ==

def narrow_events(days: Sequence[str], iv_a, iv_b, px_a, px_b, window: int = T545_WINDOW, thr: float = T545_THR,
                  hold: int = T545_HOLD, start: str = T545_START, end: str = T545_END, crossing: bool = False) -> dict:
    """x = iv_a - iv_b; z = ``rolling_z`` of x over ``window`` sessions (t included). An event is the first close in
    [start, end] with z < -thr once the previous event's ``hold``-session window has ended (``crossing``: also require
    z_{t-1} >= -thr, T-237's rule). stat_t = (RV_a - RV_b)(returns t -> t+hold) - x_t, vol points; only entries with a
    complete forward window."""
    iv_a, iv_b, px_a, px_b = (np.asarray(v, dtype=float) for v in (iv_a, iv_b, px_a, px_b))
    n = max(len(days) - hold, 0)
    x = iv_a - iv_b
    if n > 0:
        rv_a = 100 * np.sqrt(SURF._fwd_rv(np.diff(np.log(px_a)), n, 1, hold))
        rv_b = 100 * np.sqrt(SURF._fwd_rv(np.diff(np.log(px_b)), n, 1, hold))
        stat_all = (rv_a - rv_b) - x[:n]
    else:
        stat_all = np.zeros(0)
    z = SURF.rolling_z(x, window)
    ev, free = [], 0
    for t in range(max(window - 1, 1), n):
        if t < free or not (start <= days[t] <= end) or not np.isfinite(z[t]):
            continue
        if z[t] < -thr and (not crossing or (np.isfinite(z[t - 1]) and z[t - 1] >= -thr)):
            ev.append(t)
            free = t + hold
    ev = np.array(ev, dtype=int)
    in_win = np.array([start <= days[t] <= end for t in range(n)], dtype=bool) if n else np.zeros(0, bool)
    return {"t": ev, "stat": stat_all[ev] if ev.size else np.zeros(0), "stat_all": stat_all, "in_window": in_win, "z": z}


def rvx_narrow_test(days: Sequence[str], rvx, vix, iwm, spy, *, min_n: int = T545_MIN_N, n_boot: Optional[int] = None,
                    n_placebo: int = T545_PLACEBO, seed: int = SEED) -> dict:
    """T-545 core on aligned daily arrays (RVX, VIX closes; IWM, SPY adjclose). n = events."""
    nb = N_BOOT if n_boot is None else n_boot
    days = list(days)
    ev = narrow_events(days, rvx, vix, iwm, spy)
    x = ev["stat"]
    n = int(x.size)
    bt = SURF.stud_mean(x, T545_BLOCK, nb, seed)
    lo, hi = SURF.two_sided(bt)
    mean = float(x.mean()) if n else None
    wins = int((x > 0).sum())
    wr = wins / n if n else None
    halves = [float(p.mean()) for p in np.array_split(x, 2)] if n >= 2 else [None, None]
    crit = [(f"mean > 0 with the 95% CI excluding zero (mean {_s(mean)}, {_ci_txt((lo, hi))} vol pts)",
             None if lo is None else bool(mean > 0 and lo > 0), hi is not None and hi < 0),
            (f"win rate > {T545_WIN} ({_f(wr)}: {wins} of {n})", None if wr is None else bool(wr > T545_WIN),
             (wins + max(min_n - n, 0)) <= T545_WIN * max(min_n, n)),
            (f"both halves positive ({_s(halves[0])}/{_s(halves[1])})",
             None if None in halves else bool(all(h > 0 for h in halves)), False)]
    verdict, why = _decide(crit, n, min_n, "events")
    # reported: other z-windows, the parent's crossing rule, controls
    alt = {}
    for w in T545_ALT:
        e2 = narrow_events(days, rvx, vix, iwm, spy, window=w)
        s2 = e2["stat"]
        alt[str(w)] = {"n": int(s2.size), "mean": float(s2.mean()) if s2.size else None,
                       "win_rate": float((s2 > 0).mean()) if s2.size else None}
    ec = narrow_events(days, rvx, vix, iwm, spy, crossing=True)
    cross = {"n": int(ec["stat"].size), "mean": float(ec["stat"].mean()) if ec["stat"].size else None}
    sa = ev["stat_all"][ev["in_window"]] if ev["stat_all"].size else np.zeros(0)
    bt_u = SURF.stud_mean(sa, 2 * T545_HOLD, nb, seed) if sa.size >= 8 else None
    ci_u = SURF.two_sided(bt_u) if bt_u else (None, None)
    plc_p = None
    if n >= 2 and sa.size > n:
        rng = np.random.default_rng(seed + 9)
        null = np.array([sa[rng.choice(sa.size, n, replace=False)].mean() for _ in range(n_placebo)])
        plc_p = float((np.sum(null >= x.mean()) + 1) / (n_placebo + 1))
    first = days[ev["t"][0]] if n else None
    last = days[ev["t"][-1]] if n else None
    reason = (f"RVX - VIX narrow side on IWM/SPY: {n} non-overlapping events {first}..{last} (z-window {T545_WINDOW} "
              f"sessions, first close with z < -{T545_THR:g} after the previous {T545_HOLD}-session hold, entries "
              f"{T545_START}..{T545_END}); mean (RV_IWM - RV_SPY next {T545_HOLD} sessions) - (RVX - VIX at entry) "
              f"{_s(mean)} vol pts ({_ci_txt((lo, hi))}, studentized block-{T545_BLOCK} bootstrap over events); win rate "
              f"{_f(wr)}; halves {_s(halves[0])}/{_s(halves[1])}. Reported: z-windows "
              + ", ".join(f"{w} {_s(v['mean'])} (n={v['n']}, win {_f(v['win_rate'])})" for w, v in alt.items())
              + f"; T-237's crossing rule {_s(cross['mean'])} (n={cross['n']}); unconditional realised-minus-implied "
              f"spread {_s(bt_u['est'] if bt_u else None)} vol pts ({_ci_txt(ci_u)}, {2 * T545_HOLD}-session blocks, "
              f"{sa.size} days); random-entry placebo (matched count) p={_f(plc_p, 3)}. Rule 10: event dates are "
              f"data-determined (no grid phase)")
    return {"n": n, "min_n": min_n, "mean": mean, "ci95": [lo, hi], "win_rate": wr, "halves": halves,
            "events": [days[t] for t in ev["t"]], "stats": x.tolist(), "alt_windows": alt, "crossing_rule": cross,
            "unconditional_mean": bt_u["est"] if bt_u else None, "unconditional_ci95": list(ci_u), "placebo_p": plc_p,
            "first_event": first, "last_event": last, "verdict": verdict, "why": why, "reason": reason}


def b7_vol_rvx_narrow_spread(archive):
    """T-545."""
    miss = _missing(archive, [RVX_B, VIX_B, IWM_B, SPY_B])
    if miss:
        return miss
    sd, _, sa = SURF._daily(archive, SPY_B)
    idd, _, ia = SURF._daily(archive, IWM_B)
    rvx, vix = SURF._index(archive, RVX_B), SURF._index(archive, VIX_B)
    spy, iwm = dict(zip(sd, sa)), dict(zip(idd, ia))
    days = SURF._align(spy, iwm, vix, rvx)
    if len(days) < T545_WINDOW + T545_HOLD + 8:
        v, why = _decide([("enough aligned sessions for the 60-day z and a 21-session window", None, False)], 0,
                         T545_MIN_N, "events")
        return _out({"n_sessions": len(days)}, 0, v, f"only {len(days)} sessions shared by RVX, VIX, IWM and SPY — {why}")
    rep = rvx_narrow_test(days, [rvx[d] for d in days], [vix[d] for d in days], [iwm[d] for d in days],
                          [spy[d] for d in days])
    why = rep.pop("why")
    reason = rep.pop("reason")
    rep["sessions"] = [days[0], days[-1], len(days)]
    return _out(rep, rep["n"], rep["verdict"], reason + " — " + why)


# ===================================================================== T-550: SPY short strangle, quoted exits ==

READINGS = tuple((m, tm) for m in ("linear", "loglinear") for tm in ("first<=21", "last>=21"))
PRIMARY_READING = ("linear", "first<=21")


def _rk(r: tuple) -> str:
    return f"{r[0]}/{r[1]}"


def strangle_trade(day: dict, expiry: str) -> tuple:
    """Short 1 call and 1 put at the 0.16-delta strikes (vendor delta, batch6b_dolt.pick_delta) of ``expiry``."""
    if day.get("spot") is None:
        return None, "no SPY close on the quote day"
    e = day["exp"].get(expiry)
    if e is None:
        return None, "monthly expiry not listed"
    c, p = DOLT.pick_delta(e["call"], T550_DELTA), DOLT.pick_delta(e["put"], T550_DELTA)
    if c is None or p is None:
        return None, "no usable 0.16-delta call or put"
    if p["strike"] >= c["strike"]:
        return None, "put strike not below the call strike"
    return DOLT._trade(day, expiry, [DOLT._leg(c, "call", -1), DOLT._leg(p, "put", -1)]), None


def strangle_margin(trade: dict) -> float:
    """Reg-T/CBOE short strangle: the greater naked requirement plus the other leg's premium (premiums at the bid)."""
    S = trade["spot"]
    c = next(l for l in trade["legs"] if l["kind"] == "call")
    p = next(l for l in trade["legs"] if l["kind"] == "put")
    call_req = c["bid"] + max(0.20 * S - max(c["strike"] - S, 0.0), 0.10 * S)
    put_req = DOLT.naked_put_margin(p, S, "exec")
    return call_req + p["bid"] if call_req >= put_req else put_req + c["bid"]


def ask_at(legs: Sequence[dict], k: float, spot: float, mode: str) -> tuple:
    """(ask, exact) at strike ``k`` from one expiry/type's quotes: the listed ask when ``k`` is quoted; else interpolated
    in strike between the nearest quoted strikes on either side (at most SLOPE_GAP x S apart): ``linear`` in the ask
    (above a convex price curve: a conservative, high buy-back) or ``loglinear`` in log ask (below it for OTM tails); the
    two bracket the unquoted ask. (None, False) when no bracket exists."""
    qs = [l for l in legs if l.get("ask") is not None and l["ask"] >= 0 and (l.get("bid") is None or l["ask"] >= l["bid"])]
    for l in qs:
        if abs(l["strike"] - k) < 1e-9:
            return float(l["ask"]), True
    lo = [l for l in qs if l["strike"] < k]
    hi = [l for l in qs if l["strike"] > k]
    if not lo or not hi:
        return None, False
    a, b = max(lo, key=lambda l: l["strike"]), min(hi, key=lambda l: l["strike"])
    if b["strike"] - a["strike"] > DOLT.SLOPE_GAP * spot:
        return None, False
    w = (k - a["strike"]) / (b["strike"] - a["strike"])
    if mode == "loglinear" and a["ask"] > 0 and b["ask"] > 0:
        return float(math.exp((1 - w) * math.log(a["ask"]) + w * math.log(b["ask"]))), False
    return float((1 - w) * a["ask"] + w * b["ask"]), False


def marks(chain: dict, qdays: Sequence[str], trade: dict) -> list:
    """Every later quote day before expiry that lists the expiry: (day, dte, {mode: buy-back cost or None}, exact)."""
    out = []
    S = trade["spot"]
    i = bisect_left(qdays, trade["entry"]) + 1
    while i < len(qdays) and qdays[i] < trade["expiry"]:
        d = qdays[i]
        e = chain[d]["exp"].get(trade["expiry"])
        if e is not None:
            cost, exact = {}, True
            for mode in ("linear", "loglinear"):
                tot = 0.0
                for l in trade["legs"]:
                    px, ex = ask_at(e[l["kind"]], l["strike"], S, mode)
                    if px is None:
                        tot = None
                        break
                    tot += px
                    exact = exact and ex
                cost[mode] = tot
            out.append((d, DOLT.dte(trade["expiry"], d), cost, exact))
        i += 1
    return out


def exit_rule(mk: Sequence[tuple], credit: float, mode: str, timing: str) -> tuple:
    """(kind, day, cost) of the managed exit: the first mark whose buy-back <= 50% of the credit; else the 21-DTE exit
    at the first priceable mark at <= 21 DTE ("first<=21") or at the last priceable mark at >= 21 DTE ("last>=21":
    a mark at >= 21 DTE whose next priceable mark is at < 21 DTE, or a mark at exactly 21 DTE). When no such mark
    exists the 21-DTE exit is unobservable and (None, None, None) is returned: the cycle is never exited at an
    arbitrary earlier mark nor held to expiry in place of the 21-DTE exit."""
    pm = [(d, t, c[mode]) for d, t, c, _ in mk if c[mode] is not None]
    for j, (d, t, c) in enumerate(pm):
        if c <= T550_TARGET * credit:
            return "target", d, c
        if timing == "first<=21":
            if t <= T550_EXIT_DTE:
                return "21dte", d, c
        else:
            if t < T550_EXIT_DTE:                       # no priceable mark at >= 21 DTE preceded it: unobservable
                return None, None, None
            nxt = pm[j + 1][1] if j + 1 < len(pm) else None
            if t == T550_EXIT_DTE or (nxt is not None and nxt < T550_EXIT_DTE):
                return "21dte", d, c
    return None, None, None


def path_observed(mk: Sequence[tuple], mode: str, entry: str, exit_day: str, kind: str, exit_dte: int) -> bool:
    """True when the claim's managed exit is observed as worded: every NYSE session after entry up to the exit day is a
    priceable mark (so the FIRST day the buy-back <= 50% of the credit is seen) and the exit is that target day or a
    mark at exactly 21 DTE."""
    if kind == "target":
        pass
    elif kind != "21dte" or exit_dte != T550_EXIT_DTE:
        return False
    priced = {d for d, _, c, _ in mk if c[mode] is not None}
    x = date.fromisoformat(entry) + timedelta(days=1)
    end = date.fromisoformat(exit_day)
    while x <= end:
        if is_trading_day(x) and x.isoformat() not in priced:
            return False
        x += timedelta(days=1)
    return True


def manage(chain: dict, qdays: Sequence[str], trade: dict, s_t: float) -> dict:
    """Hold-to-expiry outcome and, per reading (interpolation x 21-DTE timing), the managed exit, per share."""
    credit = DOLT.net_credit(trade, "exec")
    pnl_h = credit + DOLT.payoff(trade, s_t)          # short legs: payoff is minus the intrinsic owed
    days_h = max(DOLT._ord(trade["expiry"]) - DOLT._ord(trade["entry"]), 1)
    mk = marks(chain, qdays, trade)
    out = {"credit": credit, "pnl_h": pnl_h, "days_h": days_h, "n_marks": len(mk),
           "n_exact_marks": sum(1 for m in mk if m[3] and m[2]["linear"] is not None), "readings": {}}
    for r in READINGS:
        kind, d, cost = exit_rule(mk, credit, *r)
        if kind is None:                                 # 21-DTE exit unobservable: excluded from this reading
            out["readings"][_rk(r)] = {"exit": "unobservable", "exit_day": None, "exit_dte": None, "pnl": None,
                                       "days": None, "observed": False}
            continue
        pnl = credit - cost
        days = max(DOLT._ord(d) - DOLT._ord(trade["entry"]), 1)
        xd = DOLT.dte(trade["expiry"], d)
        out["readings"][_rk(r)] = {"exit": kind, "exit_day": d, "exit_dte": xd, "pnl": pnl, "days": days,
                                   "observed": path_observed(mk, r[0], trade["entry"], d, kind, xd)}
    return out


def entry_days(chain: dict, expiry: str, start: str = T550_START, end: str = T550_END) -> list:
    """Quote days listing ``expiry`` at 38-52 DTE in [start, end], nearest 45 DTE first (ties to the longer DTE)."""
    out = []
    for q, day in chain.items():
        if not (start <= q <= end) or expiry not in day["exp"]:
            continue
        d = DOLT.dte(expiry, q)
        if abs(d - T550_DTE) <= T550_TOL:
            out.append(((abs(d - T550_DTE), -d), q))
    return [q for _, q in sorted(out)]


def _cycle(chain, qdays, trade, s_t) -> dict:
    m = manage(chain, qdays, trade, s_t)
    mg = strangle_margin(trade)
    S = trade["spot"]
    rd = {}
    for k, v in m["readings"].items():
        if v["pnl"] is None:
            rd[k] = dict(v, ratio=None, ppd=None, ratio_comm=None)
            continue
        rd[k] = dict(v, ratio=v["pnl"] / mg, ppd=v["pnl"] / S / v["days"], ratio_comm=(v["pnl"] - DOLT.COMM * 4) / mg)
    return {**{k: trade[k] for k in ("entry", "expiry", "dte", "spot", "late_stamp")},
            "k_call": trade["legs"][0]["strike"], "k_put": trade["legs"][1]["strike"],
            "delta_call": trade["legs"][0]["delta"], "delta_put": trade["legs"][1]["delta"], "s_t": float(s_t),
            "margin": mg, "credit": m["credit"], "pnl_h": m["pnl_h"], "days_h": m["days_h"], "ratio_h": m["pnl_h"] / mg,
            "ppd_h": m["pnl_h"] / S / m["days_h"], "n_marks": m["n_marks"], "n_exact_marks": m["n_exact_marks"],
            "readings": rd}


def strangle_cycles(chain: dict, close_by: dict, last_day: str, monthly: set) -> tuple:
    """One cycle per standard monthly expiry (entry nearest 45 DTE, next-nearest when that day cannot build the
    strangle). Returns (cycles, skips)."""
    qdays = sorted(chain)
    cycles, skips = [], Counter()
    for e in sorted(monthly):
        cands = entry_days(chain, e)
        if not cands:
            lastq = min(qdays[-1], T550_END) if qdays else ""
            if qdays and DOLT.dte(e, max(qdays[0], T550_START)) >= T550_DTE - T550_TOL \
                    and DOLT.dte(e, lastq) <= T550_DTE + T550_TOL:
                skips["no quote day at 38-52 DTE"] += 1
            continue
        trade, why_first, rank = None, None, 0
        for rank, q in enumerate(cands):
            t, why = strangle_trade(chain[q], e)
            if t is not None:
                trade = t
                break
            why_first = why_first or why
        if trade is None:
            skips[why_first] += 1
            continue
        s_t = close_by.get(e)
        if s_t is None:
            skips["unresolved (expiry after the last archived close)" if e > last_day else "no SPY close on the expiry"] += 1
            continue
        c = _cycle(chain, qdays, trade, float(s_t))
        c["entry_rank"] = rank
        cycles.append(c)
        if rank:
            skips["entered on the next-nearest day (nearest could not build the strangle)"] += 1
    return cycles, skips


def _month_timeline(cycles: Sequence[dict], x) -> tuple:
    """(S, N) per calendar month of expiry from the first to the last cycle; months without a cycle kept empty."""
    if not cycles:
        return np.zeros(0), np.zeros(0)
    mi = [int(c["expiry"][:4]) * 12 + int(c["expiry"][5:7]) - 1 for c in cycles]
    m0 = min(mi)
    S, N = np.zeros(max(mi) - m0 + 1), np.zeros(max(mi) - m0 + 1)
    for k, v in zip(mi, x):
        S[k - m0] += v
        N[k - m0] += 1
    return S, N


def cycle_mean_test(cycles: Sequence[dict], x, blocks: Sequence[int] = T550_BLOCKS, n_boot: Optional[int] = None,
                    seed: int = SEED) -> dict:
    """Mean of x over cycles with the studentized CBB 95% CI at each block (in cycles); ok robust over blocks."""
    nb = N_BOOT if n_boot is None else n_boot
    x = np.asarray(x, dtype=float)
    if not len(cycles):
        rows = [{"block": int(b), "ci": [None, None], "ok": None, "dec": None} for b in blocks]
        return {"mean": None, "n": 0, "by_block": rows, "ok": None, "decisive_fail": False}
    S, N = _month_timeline(cycles, x)
    rows = []
    for b in blocks:
        lo, hi = DOLT.cluster_mean_ci(S, N, b, 0.95, nb, seed)
        rows.append({"block": int(b), "ci": [lo, hi], "ok": None if lo is None else bool(lo > 0),
                     "dec": None if hi is None else bool(hi < 0)})
    return {"mean": float(x.mean()) if x.size else None, "n": int(x.size), "by_block": rows,
            "ok": DOLT._robust([r["ok"] for r in rows]), "decisive_fail": bool(rows) and all(r["dec"] is True for r in rows)}


def strangle_claim(cycles: Sequence[dict], *, min_n: int = T550_MIN_N, n_boot: Optional[int] = None,
                   seed: int = SEED) -> dict:
    """T-550 judge: mean managed P&L / margin > 0 and paired P&L per day (managed - hold) > 0, each with the 95% CI
    excluding 0 robust over blocks of 2 and 4 cycles, judged on every reading (interpolation x 21-DTE timing). The
    readings decide a criterion only when the claim's managed exit is OBSERVED on every cycle under every reading
    (``observed``: a priceable mark on every session up to the exit, which is the first <= 50% day or a mark at exactly
    21 DTE): then a criterion passes only when every reading passes, fails only when every reading fails. Otherwise
    the readings fill unobserved days, do not bracket the true managed P&L, and are reported as sensitivities: both
    criteria are None (rule 9 data limit), capping the verdict at inconclusive. Cycles whose 21-DTE exit is
    unobservable in a reading (ratio None) are left out of that reading's sensitivity. n = cycles."""
    n = len(cycles)
    per = {}
    n_obs = sum(1 for c in cycles if all(c["readings"][_rk(r)].get("observed", False) for r in READINGS))
    for r in READINGS:
        k = _rk(r)
        cs = [c for c in cycles if c["readings"][k]["ratio"] is not None]
        ratio = np.array([c["readings"][k]["ratio"] for c in cs], dtype=float)
        diff = np.array([c["readings"][k]["ppd"] - c["ppd_h"] for c in cs], dtype=float)
        per[k] = {"n": len(cs), "ratio": cycle_mean_test(cs, ratio, n_boot=n_boot, seed=seed),
                  "ppd_diff": cycle_mean_test(cs, diff, n_boot=n_boot, seed=seed)}
    limit = n_obs < n
    limit_txt = (f"DATA LIMIT (rule 9): the claim's exit is observed as worded (a priced mark on every session to the "
                 f"first <= 50% day or to 21 DTE) on {n_obs} of {n} cycles under every reading: the DoltHub chains list a "
                 f"cycle's expiry on only a few days before 21 DTE, so neither the first-day 50% target nor the 21-DTE "
                 f"exit is observable and the four readings are sensitivities, not bounds")

    def crit(key, label, scale, unit, nd):
        oks = [per[_rk(r)][key]["ok"] for r in READINGS]
        ok = None if limit else DOLT._robust(oks)
        dec = False if limit else all(per[_rk(r)][key]["decisive_fail"] for r in READINGS)
        txt = "; ".join(f"{_rk(r)} n={per[_rk(r)]['n']} {_s(None if per[_rk(r)][key]['mean'] is None else per[_rk(r)][key]['mean'] * scale, nd)} ("
                        + ", ".join(f"b{row['block']} {_ci_txt(row['ci'], nd, scale)}" for row in per[_rk(r)][key]["by_block"])
                        + ")" for r in READINGS)
        note = " [the readings disagree: undecided]" if (True in oks and False in oks) else ""
        if limit:
            note = f" [{limit_txt}]"
        return (f"{label} > 0 with the 95% CI excluding 0 under every reading ({unit}: {txt}){note}", ok, dec)

    crits = [crit("ratio", "mean managed P&L per unit Reg-T margin", 1.0, "per cycle", 4),
             crit("ppd_diff", "paired P&L per day (managed - hold to expiry)", 1e4, "bp of spot/day", 3)]
    verdict, why = _decide(crits, n, min_n, "cycles")
    return {"n": n, "n_observed": n_obs, "data_limit": limit, "per_reading": per, "verdict": verdict, "why": why}


def _nmean(xs, scale: float = 1.0):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) * scale if xs else None


def _sub_mean(cycles, key, pred) -> tuple:
    xs = [c[key] for c in cycles if pred(c)]
    return (float(np.mean(xs)) if xs else None), len(xs)


def b7_vol_spy_strangle_quoted_exits(archive):
    """T-550."""
    miss = _missing(archive, [CHAIN_B, SPY_B])
    if miss:
        return miss
    W = DOLT._world(archive)
    monthly = DOLT.monthly_expiries(2019, 2027)
    cycles, skips = strangle_cycles(W["chain"], W["close_by"], W["last"], monthly)
    head = (f"QUOTE-PRICED SPY 45-DTE 0.16-delta short strangle on the standard monthly expiries ({DOLT._data_txt(W)}; "
            f"entry on the quote day nearest {T550_DTE} DTE within +/-{T550_TOL}, sold at the bid = mid - half spread; "
            f"bought back at the ask = mid + half spread at the first mark <= {T550_TARGET:.0%} of the credit, else at "
            f"{T550_EXIT_DTE} DTE; hold-to-expiry settled at intrinsic on SPY's raw close; Reg-T strangle margin = greater "
            f"naked leg + the other leg's premium; {DOLT.LIVE_PROXY_TXT}). DATA LIMIT on the marks: DoltHub lists 3-4 "
            f"expiries a day on a strike grid that moves with the spot, so a cycle's expiry is quoted on later days mostly "
            f"at ~25-31 and ~11-15 DTE, rarely at 21, and its exact strikes rarely; marks are the listed ask when the "
            f"strike is quoted, else the ask interpolated between the bracketing quoted strikes (linear: high; log-linear: "
            f"low), and the 21-DTE exit is read at the first priceable mark at <= 21 DTE and at the last at >= 21 DTE whose "
            f"next priced listing is below 21 DTE (a cycle with no such mark has an unobservable 21-DTE exit and is left "
            f"out of that reading). These readings fill unobserved days and do not bound the claim's P&L, so they decide "
            f"nothing unless the exit is observed as worded on every cycle")
    stat = {"n_cycles": len(cycles), "skips": dict(skips), "data": W["info"], "label": "QUOTE-PRICED (interpolated marks)"}
    if len(cycles) < DOLT.MIN_CLUSTERS:
        v, why = _decide([("enough resolved cycles for an interval", None, False)], len(cycles), T550_MIN_N, "cycles")
        return _out(stat, len(cycles), v, f"{head}: only {len(cycles)} resolved cycles; skips "
                    f"{DOLT._skips_txt(skips, Counter())} — {why}")
    core = strangle_claim(cycles)
    pk = _rk(PRIMARY_READING)
    mean = lambda f: float(np.mean([f(c) for c in cycles]))
    exits = {_rk(r): dict(Counter(c["readings"][_rk(r)]["exit"] for c in cycles)) for r in READINGS}
    exit_dte = {_rk(r): [int(np.min(v)), float(np.median(v)), int(np.max(v))] if v else None
                for r in READINGS for v in [[c["readings"][_rk(r)]["exit_dte"] for c in cycles
                                             if c["readings"][_rk(r)]["exit"] == "21dte"]]}
    n_marks = sum(c["n_marks"] for c in cycles)
    n_exact = sum(c["n_exact_marks"] for c in cycles)
    covid = lambda c: c["entry"] <= "2020-03-31" and c["expiry"] >= "2020-03-01"
    y22 = lambda c: c["entry"][:4] == "2022"
    rest = lambda c: not covid(c) and not y22(c)
    sub = {}
    for lab, p in (("2020-03", covid), ("2022", y22), ("other", rest)):
        cs = [c for c in cycles if p(c)]
        sub[lab] = {"n": len(cs),
                    "ratio_managed": _nmean([c["readings"][pk]["ratio"] for c in cs]),
                    "ratio_hold": float(np.mean([c["ratio_h"] for c in cs])) if cs else None,
                    "ppd_managed_bp": _nmean([c["readings"][pk]["ppd"] for c in cs], 1e4),
                    "ppd_hold_bp": float(np.mean([c["ppd_h"] for c in cs])) * 1e4 if cs else None}
    strict = [c for c in cycles if not c["late_stamp"]]
    qdays = sorted(W["chain"])
    alt = {}
    for lab, longest in (("earliest in the window (longest DTE)", True), ("latest in the window (shortest DTE)", False)):
        rs, ds = [], []
        for c in cycles:
            e_ = c["expiry"]
            cs_ = entry_days(W["chain"], e_)
            q = (max if longest else min)(cs_, key=lambda q_: DOLT.dte(e_, q_))
            t, _ = strangle_trade(W["chain"][q], e_)
            if t is None:
                continue
            cc = _cycle(W["chain"], qdays, t, c["s_t"])
            if cc["readings"][pk]["ratio"] is None:
                continue
            rs.append(cc["readings"][pk]["ratio"])
            ds.append(cc["readings"][pk]["ppd"] - cc["ppd_h"])
        alt[lab] = {"n": len(rs), "ratio_managed": float(np.mean(rs)) if rs else None,
                    "ppd_diff_bp": float(np.mean(ds)) * 1e4 if ds else None}
    per = core["per_reading"]
    parts = [f"{len(cycles)} cycles, entries {cycles[0]['entry']}..{cycles[-1]['entry']} (DTE {min(c['dte'] for c in cycles)}-"
             f"{max(c['dte'] for c in cycles)}; mean call delta {_f(mean(lambda c: c['delta_call']), 3)}, put delta "
             f"{_f(mean(lambda c: c['delta_put']), 3)}); {n_marks} later listings of the cycles' expiries, {n_exact} with "
             f"both strikes quoted exactly",
             "exits by reading: " + "; ".join(f"{k} {v} (21-DTE exits at DTE min/median/max {exit_dte[k]})"
                                              for k, v in exits.items()),
             f"mean credit {_f(mean(lambda c: c['credit']))} ({_f(mean(lambda c: c['credit'] / c['spot']) * 100, 3)}% of S), "
             f"mean margin {_f(mean(lambda c: c['margin'] / c['spot']) * 100)}% of S",
             f"hold to expiry: P&L/margin {_s(mean(lambda c: c['ratio_h']), 4)}, P&L/day {_s(mean(lambda c: c['ppd_h']) * 1e4, 3)} "
             f"bp of spot; managed by reading: " + "; ".join(
                 f"{k} (n={v['n']}) P&L/margin {_s(v['ratio']['mean'], 4)}, P&L/day difference "
                 f"{_s(None if v['ppd_diff']['mean'] is None else v['ppd_diff']['mean'] * 1e4, 3)} bp"
                 for k, v in per.items()),
             f"separately ({pk}): " + "; ".join(
                 f"{lab} (n={v['n']}) P&L/margin managed {_s(v['ratio_managed'], 4)} / hold {_s(v['ratio_hold'], 4)}, "
                 f"P&L/day {_s(v['ppd_managed_bp'], 3)} / {_s(v['ppd_hold_bp'], 3)} bp" for lab, v in sub.items()),
             f"with $0.65/contract per leg and side ({pk}): P&L/margin {_s(_nmean([c['readings'][pk]['ratio_comm'] for c in cycles]), 4)}",
             f"{DOLT.SNAP_SENS} ({pk}; drops {len(cycles) - len(strict)} weekend/holiday/moved-snapshot entries): "
             f"P&L/margin {_s(_nmean([c['readings'][pk]['ratio'] for c in strict]), 4)}, "
             f"P&L/day difference {_s(_nmean([c['readings'][pk]['ppd'] - c['ppd_h'] for c in strict if c['readings'][pk]['ppd'] is not None], 1e4), 3)} bp",
             "entry-day sensitivity within 38-52 DTE (reported; the calendar is the claim's): " + "; ".join(
                 f"{lab} n={v['n']} P&L/margin {_s(v['ratio_managed'], 4)}, P&L/day difference {_s(v['ppd_diff_bp'], 3)} bp"
                 for lab, v in alt.items()),
             f"skips: {DOLT._skips_txt(skips, Counter())}"]
    stat.update({"per_reading": per, "n_exit_observed": core["n_observed"], "exit_data_limit": core["data_limit"],
                 "exits": exits, "exit_dte_21": exit_dte, "n_marks": n_marks,
                 "n_exact_marks": n_exact, "mean_ratio_hold": mean(lambda c: c["ratio_h"]),
                 "mean_ppd_hold_bp": mean(lambda c: c["ppd_h"]) * 1e4, "subperiods": sub, "entry_day_sensitivity": alt,
                 "n_late_stamp": len(cycles) - len(strict),
                 "cycles": [{**{k: c[k] for k in ("entry", "expiry", "k_put", "k_call", "credit", "margin", "pnl_h",
                                                  "ratio_h", "ppd_h")}, "primary": c["readings"][pk]} for c in cycles]})
    return _out(stat, core["n"], core["verdict"], head + ": " + "; ".join(parts) + " — " + core["why"])


# ======================================================================= T-551: PUT with a 10-month SMA filter ==

def sma_signal(series: Sequence[tuple], L: int = T551_L) -> dict:
    """{month: (above, source)} from month-end closes: each (name, days, closes) in priority order; a month uses the
    first series whose L-month SMA is defined at its last session of that month."""
    out = {}
    for name, days, x in reversed(list(series)):
        if not len(days):
            continue
        last = {}
        for i, d in enumerate(days):
            last[d[:7]] = i
        ms = sorted(last)
        xs = np.array([x[last[m]] for m in ms], float)
        st = MOM.ma_state(xs, L, 0.0, "SMA")
        for m, s in zip(ms, st):
            if np.isfinite(s):
                out[m] = (bool(s > 0.5), name)
    return out


def continuous_start(days: Sequence[str], max_gap: int = T551_MAX_GAP) -> int:
    """Index of the first day after the last calendar gap longer than ``max_gap`` days."""
    i0 = 0
    for i in range(1, len(days)):
        if DOLT._ord(days[i]) - DOLT._ord(days[i - 1]) > max_gap:
            i0 = i
    return i0


def _strategy(inm: np.ndarray, R: np.ndarray, rf: np.ndarray, cost: float) -> np.ndarray:
    """(P, n) log returns: the asset when in, bills when out, log(1 - cost) at each switch after the first period."""
    x = np.atleast_2d(inm)
    lr = np.where(x, np.log1p(R)[None, :], np.log1p(rf)[None, :])
    lr[:, 1:] += math.log1p(-cost) * (x[:, 1:] != x[:, :-1])
    return lr


def drawdown_vs_null(inm: np.ndarray, R: np.ndarray, rf: np.ndarray, cost: float = T551_COST,
                     n_null: Optional[int] = None, seed: int = SEED) -> dict:
    """MDD of the filtered rule and of always-in, the reduction, and T-301's matched null (the rule's out spells
    re-placed at random): p = (1 + #{null MDD <= rule MDD}) / (paths + 1)."""
    n_null = T551_N_NULL if n_null is None else n_null
    lr = _strategy(inm, R, rf, cost)
    rule = float(MOM.mdd_from_logwealth(np.cumsum(lr, axis=1))[0])
    always = float(MOM.mdd_depth(R)[0])
    rng = np.random.default_rng(seed)
    nulls, done = [], 0
    while done < n_null:
        k = min(1000, n_null - done)
        paths = ~MOM.spell_paths(~np.asarray(inm, bool), k, rng, with_src=False)[0]
        nulls.append(MOM.mdd_from_logwealth(np.cumsum(_strategy(paths, R, rf, cost), axis=1)))
        done += k
    null = np.concatenate(nulls) if nulls else np.zeros(0)
    return {"mdd_rule": rule, "mdd_always": always, "reduction": 1.0 - rule / always if always > 0 else None,
            "p": MOM._mc_p(null, rule) if null.size else None, "null_median": float(np.median(null)) if null.size else None,
            "null_q05": float(np.quantile(null, 0.05)) if null.size else None, "n_paths": int(null.size),
            "returns": np.expm1(lr[0]), "n_out_spells": len(MOM.runs(~np.asarray(inm, bool)))}


def _judge_block(inm, R, rf, label: str, *, n_null, n_boot, reps, seed) -> tuple:
    dd = drawdown_vs_null(inm, R, rf, n_null=n_null, seed=seed)
    red_b = SURF.mdd_reduction_boot(dd["returns"], R, 12, n_boot or N_BOOT, seed)
    up = (red_b.get("ci95") or [None, None])[1]
    red = dd["reduction"]
    sh = MOM.sharpe_test(dd["returns"] - rf, R - rf, n_boot, seed, reps, thr=T551_SHARPE_THR)
    crit = [(f"{label}: drawdown reduction >= {T551_RED:.0%} ({_f(None if red is None else red * 100, 1)}%: MDD "
             f"{dd['mdd_rule'] * 100:.1f}% vs always {dd['mdd_always'] * 100:.1f}%; paired CBB {_ci_txt(red_b.get('ci95'), 1, 100)}%)",
             None if red is None else bool(red >= T551_RED), up is not None and up < T551_RED),
            (f"{label}: matched random-timing null p < 0.05 (p {_f(dd['p'], 4)} on {dd['n_paths']} paths)",
             None if dd["p"] is None else bool(dd["p"] < 0.05), False),
            _ci_crit(sh, "gt", T551_SHARPE_THR, f"{label}: Sharpe difference (filtered - always, excess returns, "
                                               f"{_s(sh.get('diff'), 3)}) 95% lower bound > {T551_SHARPE_THR}")]
    return crit, dd, sh, red_b


def putwrite_trend_filter(days: Sequence[str], level, backtest, sig: dict, bills, *, launch: str = T551_LAUNCH,
                          end: str = T551_END, min_n: int = T551_MIN_N, n_null: Optional[int] = None,
                          n_boot: Optional[int] = None, reps: Optional[int] = None, seed: int = SEED) -> dict:
    """T-551 core. ``days``/``level``/``backtest``: the PUT index sessions; ``sig``: {month: (above, source)}. Hold k
    runs from the fill after month-end decision k to the next fill; in = the signal at that decision month. n = hold
    months."""
    days = list(days)
    level = np.asarray(level, float)
    g = MOM.month_grid(days)
    me, ex = g["me"], g["ex"]
    C = MOM.bill_logcum(bills, days)
    rows = []
    for k in range(len(me) - 1):
        m = days[me[k]][:7]
        if m >= end or m not in sig:          # the hold after month-end m lies in m + 1, which must be <= ``end``
            continue
        a, b = ex[k], ex[k + 1]
        rows.append((m, a, b, sig[m][0], sig[m][1]))
    n = len(rows)
    out = {"n": n, "min_n": min_n}
    if n < 24:
        v, why = _decide([("enough hold months for the drawdown and Sharpe tests", None, False)], n, min_n, "months")
        out.update(verdict=v, why=why, reason=f"only {n} hold months")
        return out
    a = np.array([r[1] for r in rows])
    b = np.array([r[2] for r in rows])
    inm = np.array([r[3] for r in rows], bool)
    R = level[b] / level[a] - 1.0
    rf = np.exp(C[b] - C[a]) - 1.0
    bt = np.array([bool(backtest[i]) or bool(backtest[j]) for i, j in zip(a, b)])
    crit, dd, sh, red_b = _judge_block(inm, R, rf, "full history", n_null=n_null, n_boot=n_boot, reps=reps, seed=seed)
    live = np.array([days[i] >= launch for i in a])
    live_res = None
    if live.sum() >= 24:
        c2, dd2, sh2, rb2 = _judge_block(inm[live], R[live], rf[live], f"live months (from {launch})", n_null=n_null,
                                         n_boot=n_boot, reps=reps, seed=seed + 1)
        crit += c2
        live_res = {"n": int(live.sum()), "dd": dd2, "sharpe": sh2, "red_boot": rb2}
    else:
        crit.append((f"live months (from {launch}) judged separately ({int(live.sum())} months: too few)", None, False))
    verdict, why = _decide(crit, n, min_n, "months")
    src = Counter(r[4] for r in rows)
    out.update({"verdict": verdict, "why": why, "window": [days[a[0]], days[b[-1]]], "first_month": rows[0][0],
                "last_month": rows[-1][0], "time_in_market": float(inm.mean()), "n_switches": int((inm[1:] != inm[:-1]).sum()),
                "n_backtest_months": int(bt.sum()), "signal_sources": dict(src), "dd": dd, "sharpe": sh, "red_boot": red_b,
                "live": live_res, "ann_mean_always": float(R.mean() * 12), "ann_mean_filtered": float(dd["returns"].mean() * 12)})
    return out


def _dd_txt(dd: dict, sh: dict) -> str:
    return (f"MDD filtered {dd['mdd_rule'] * 100:.1f}% vs always-PUT {dd['mdd_always'] * 100:.1f}% (reduction "
            f"{_f(None if dd['reduction'] is None else dd['reduction'] * 100, 1)}%); matched null median "
            f"{_f(None if dd['null_median'] is None else dd['null_median'] * 100, 1)}%, 5th pct "
            f"{_f(None if dd['null_q05'] is None else dd['null_q05'] * 100, 1)}%, p {_f(dd['p'], 4)} ({dd['n_paths']} paths, "
            f"{dd['n_out_spells']} out spells); excess Sharpe filtered {_s(sh.get('sharpe_a'), 3)} vs always "
            f"{_s(sh.get('sharpe_b'), 3)}, difference {_s(sh.get('diff'), 3)} ({_ci_txt(sh.get('ci'), 3)})")


def b7_vol_putwrite_trend_filter(archive):
    """T-551."""
    miss = _missing(archive, [PUT_B, GSPC_B, SPY_B, DTB3_B])
    if miss:
        return miss
    P = cboe_index(archive, "PUT")
    pdays_all = sorted(P["close"])
    i0 = continuous_start(pdays_all)
    pdays = pdays_all[i0:]
    lvl = [P["close"][d] for d in pdays]
    bt = [P["backtest"].get(d, False) for d in pdays]
    spy, gspc = MOM._daily(archive, SPY_B), MOM._daily(archive, GSPC_B)
    sig = sma_signal([("SPY", spy["days"], spy["adj"]), ("^GSPC", gspc["days"], gspc["close"])])
    sig_g = sma_signal([("^GSPC", gspc["days"], gspc["close"])])
    j = putwrite_trend_filter(pdays, lvl, bt, sig, MOM._bills(archive))
    if "dd" not in j:
        return _out({"n_months": j["n"]}, j["n"], j["verdict"], f"PUT trend filter: {j['reason']} — {j['why']}")
    months = [m for m in sig if j["first_month"] <= m <= j["last_month"]]
    agree = float(np.mean([sig[m][0] == sig_g[m][0] for m in months if m in sig_g])) if months else None
    jg = putwrite_trend_filter(pdays, lvl, bt, sig_g, MOM._bills(archive), n_null=2000, reps=1)
    dropped = pdays_all[:i0]
    head = (f"Cboe PUT index (continuous daily history {pdays[0]}..{pdays[-1]}; the archived file holds only "
            f"{len(dropped)} scattered back-test prints before it ({', '.join(dropped[:3])}{'...' if len(dropped) > 3 else ''}), "
            f"which cannot form monthly returns, so Cboe's pre-{pdays[0][:4]} back-test history is not in the sample) held "
            f"in the month after SPY (^GSPC before SPY's own 10-month SMA exists) closed above its {T551_L}-month SMA at "
            f"month-end, filled at the next session's close, DTB3 (discount-yield converted, rule 7) when out, "
            f"{T551_COST * 1e4:.0f} bps per switch (T-301's construction): {j['n']} hold months after decisions "
            f"{j['first_month']}..{j['last_month']}, {j['time_in_market'] * 100:.0f}% in PUT, {j['n_switches']} switches, "
            f"{j['n_backtest_months']} months touching back-tested values (before the {T551_LAUNCH} launch), signal "
            f"sources {j['signal_sources']}")
    parts = [f"full history: {_dd_txt(j['dd'], j['sharpe'])}"]
    if j["live"]:
        parts.append(f"live months ({j['live']['n']}): {_dd_txt(j['live']['dd'], j['live']['sharpe'])}")
    parts.append(f"reported: ^GSPC-only signal agrees on {_f(None if agree is None else agree * 100, 1)}% of months, its "
                 f"reduction {_f(None if jg.get('dd') is None else (jg['dd']['reduction'] or 0) * 100, 1)}%, Sharpe "
                 f"difference {_s(None if jg.get('sharpe') is None else jg['sharpe'].get('diff'), 3)}; annualised mean "
                 f"return always {_f(j['ann_mean_always'] * 100, 2)}% vs filtered {_f(j['ann_mean_filtered'] * 100, 2)}%")
    stat = {"n_months": j["n"], "window": j["window"], "first_decision": j["first_month"], "last_decision": j["last_month"],
            "time_in_market": j["time_in_market"], "n_switches": j["n_switches"], "n_backtest_months": j["n_backtest_months"],
            "signal_sources": j["signal_sources"], "mdd_filtered": j["dd"]["mdd_rule"], "mdd_always": j["dd"]["mdd_always"],
            "reduction": j["dd"]["reduction"], "reduction_ci95": j["red_boot"].get("ci95"), "null_p": j["dd"]["p"],
            "null_median": j["dd"]["null_median"], "null_q05": j["dd"]["null_q05"], "n_paths": j["dd"]["n_paths"],
            "sharpe_filtered": j["sharpe"].get("sharpe_a"), "sharpe_always": j["sharpe"].get("sharpe_b"),
            "sharpe_diff": j["sharpe"].get("diff"), "sharpe_ci": j["sharpe"].get("ci"),
            "live": None if not j["live"] else {"n": j["live"]["n"], "reduction": j["live"]["dd"]["reduction"],
                                                "mdd_filtered": j["live"]["dd"]["mdd_rule"],
                                                "mdd_always": j["live"]["dd"]["mdd_always"], "null_p": j["live"]["dd"]["p"],
                                                "sharpe_diff": j["live"]["sharpe"].get("diff"),
                                                "sharpe_ci": j["live"]["sharpe"].get("ci")},
            "gspc_signal_agreement": agree, "pre_continuous_prints": dropped,
            "rule10": "calendar: month-end decisions named by the claim (rule 10(a))"}
    return _out(stat, j["n"], j["verdict"], head + ". " + "; ".join(parts) + " — " + j["why"])


HARNESSES = {
    "b7_vol_rvx_narrow_spread": b7_vol_rvx_narrow_spread,
    "b7_vol_spy_strangle_quoted_exits": b7_vol_spy_strangle_quoted_exits,
    "b7_vol_putwrite_trend_filter": b7_vol_putwrite_trend_filter,
}

THEORY_MAP = {
    "T-545": "b7_vol_rvx_narrow_spread",
    "T-550": "b7_vol_spy_strangle_quoted_exits",
    "T-551": "b7_vol_putwrite_trend_filter",
}
