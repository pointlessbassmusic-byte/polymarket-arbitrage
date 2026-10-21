"""
Batch 13, group ``cryptoderiv_a``: four claims from the 2026-10-20 web sweep (cluster "cryptoderiv"), pre-registered
before any run (T-608, T-613, T-612, T-614).
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (MANDEL.md section 2, house rules 1-12):

  * T-608  Point-in-time top 30 Coinbase USD products by trailing 30-day dollar volume, rebuilt every Monday 00:00 UTC
           with T-424's construction (``batch6c_cryptovenue.cb_members``' rule, re-expressed on arrays: dollar volume
           close x volume summed over days M-30..M-1, listed = traded on M-1), T-424's declared stablecoin and
           wrapped / staked base lists (BTC itself is NOT excluded: T-424 dropped it as the leader, this claim names
           "coins"), and the ``fx_stablecoin`` ids of coinbase-products-2026-10-15. Signal = close of the bar starting
           Sunday (ending Monday 00:00) / close 14 days earlier - 1. Eligible = member with a 14-day signal and a Monday
           bar to enter on; weeks with < 15 eligible are dropped and counted. Losers = the floor(n/3) lowest. Books: EW
           of all eligible and EW ex-losers, entered at the Monday open, exited at the next Monday open, reset weekly,
           each charged 50 bp per side on its own drift-adjusted turnover. A name with no bar at the exit Monday is
           marked at its last close, minus 50% when it never trades again (delisted). Statistic: mean weekly net
           EW(ex-losers) - EW(all), entries 2019-01..2026-09. Pass: one-sided 95% lower bound > 0 (studentized 8-week
           circular block bootstrap, 5,000 draws per seed, escalated), both halves (split 2022-11-17) positive, above the
           95th percentile of 1,000 within-week random-tercile placebos, DSR > 0.95 at 28 trials (T-314's 24, T-546 and
           the 3 arms here). min_n 300 weeks. The placebo criterion charges each random draw the primary's own mean cost
           difference (T-314's convention; random exclusions turn over more than the loser tercile, so this is the
           stricter reading, fixed before the run); the null with each random book's own turnover is reported. Reported
           arms: gross EW(rest) - EW(losers); the 21-day lookback; on the Kalshi-listed subset (the coins the archive's
           records name as Kalshi perps: ETH, SOL, BNB, DOGE, SHIB, PEPE; hindsight universe) long BTC x the mean
           trailing-60-day beta of hourly Coinbase log returns (bars ending by Monday 00:00; daily for a coin without an
           hourly bundle) minus the EW Kalshi-listed losers, 18 bp round trip per leg, funding 0 / +-10%/yr; CMC flags
           (cmc-historical-listings matched by symbol, T-314's declared classification) and a peg screen as
           cross-checks; per year; the BTC 200-day trend regime; the six other weekday phases (rule 10).
  * T-613  Coinbase BTC log return from the close of the hourly bar ending at the NYSE close of the last session
           before a weekend (13:00 ET on early closes) to the close of the bar ending 30 minutes before the next
           session's 09:30 ET open (holiday Mondays roll), flagged when in the bottom tercile of all prior weekends
           from 2019-01 (expanding, >= 52). Target: Yahoo open-to-close of that session. Per ETF (SPY, QQQ, IWM),
           2020-01..2026-09: contrast = mean after flagged weekends minus after the others. Pass (for at least one ETF):
           contrast < 0 with Bonferroni (x3) one-sided p < 0.05 (studentized circular block bootstrap, 4-weekend
           ~monthly blocks, 5,000 draws per seed, escalated against 0.05/3), negative in both halves (split 2022-05-09),
           and the flat-on-signal rule's net mean (2 bp round trip) above always-long Monday. min_n 300 weekends.
  * T-612  CME Bitcoin (133741) futures-only TFF report: LF = (lev_money long - short) / open_interest_all,
           dLF = LF - LF of the previous report, known at the row's stored available_at (a report whose successor was
           public no later than it is superseded: one information set). Entry at the open of the first Coinbase hourly
           bar starting at or after available_at (daily bar before 2019), exit at the open of the first bar 7 x 24 h
           later; y = log return. Controls: annualised CME basis ln(BTC=F close / Coinbase close of the bar ending
           16:00 ET) x 365 / days to the front (last-Friday) expiry on the as-of Tuesday, its change, and the 7-day
           BTC return to the entry. Pass (post-publication, report dates 2022-05..2026-09): Newey-West (lag 4) t of the
           dLF slope >= 2, the slope positive in 2022-05..2023-12 and in 2024-01..2026-09, and the long/flat rule
           (long when dLF > 0, 10 bp per switch, bills when flat) with a weekly Sharpe above buy-and-hold under an
           8-week block-permutation p < 0.05 (2,000 draws per batch, escalated). min_n 200 reports.
  * T-614  Coinbase BTC-USD hourly marks by bar end: 00:00 = close of the bar starting 23:00 (previous day), 08:00 =
           close of the bar starting 07:00, 16:00 = close of the bar starting 15:00; r1 = ln(P08 / P00), r2 =
           ln(P16 / P08), 2019-05-01..2026-10-15. OLS slope of r2 on r1 on Deribit monthly / quarterly expiry Fridays
           (last Friday of the month, the rule calendar) minus the slope on Monday-Thursday. Fade trade on expiry
           Fridays: at the open of the bar starting 08:00, the side opposite sign(r1), out at the close of the bar
           starting 15:00, 10 bp round trip. Pass: slope difference < 0 with one-sided p < 0.05 (4-week circular block
           bootstrap of the calendar, 5,000 draws per seed, escalated; p = share of draws >= 0), negative in both halves
           (split 2023-01-01), and the net mean fade trade with a one-sided 95% lower bound > 0 (studentized bootstrap,
           block 1: one expiry per 4-week block). min_n 80 expiry Fridays.

Conventions
  * Data: bundles through ``archive.load`` with rows available after the bundle's capture dropped
    (``batch6c_cryptovenue._stream``; ``batch6c_cal._rows``). A missing bundle the pass depends on is inconclusive and
    named (rule 9); a bundle only a reported arm needs is reported as not archived.
  * Point in time (rules 4, 12): Coinbase bars are start-stamped; a close is used only from its bar's end. T-608 decides
    at Monday 00:00 UTC from bars ending by then and enters at the Monday open; T-613 decides 30 minutes before the
    open from bars ending by then and enters at the official open (Yahoo's open print); T-612 enters at the first bar
    starting at or after the stored available_at (never the report date); T-614 decides at 08:00 from bars ending by
    then and enters at the open of the bar starting 08:00. Expanding terciles (T-613) use prior weekends only.
  * Rule 5: below min_n never supported; a failing criterion counts only when it fails decisively (``batch6c_cal._judge``).
  * Rule 10: T-608 is a fixed Monday grid named by the claim; the other six weekday phases' primary statistic is
    reported as the per-start range (not judged). T-613, T-612 and T-614 are event-driven (weekends, releases, expiry
    days): no free phase.
  * Monte Carlo (rule 11): resampled p's decide only when their 95% MC band clears the threshold, escalated one seed or
    batch at a time up to ``batch6c_cal.MAX_SEEDS`` (``escalate_p``).
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_cryptovenue as CV
from mandel.experiments import batch7_cal as B7C
from mandel.experiments.batch6_surf import _out
from mandel.experiments.batch6c_mom import dsr_row, family_dsr
from mandel.validation.backtest_eval import block_bootstrap_pvalue, sharpe_ratio

UTC = timezone.utc
NY = CV.NY
H = 3600
DAY = 86400
SEED = 0
ALPHA = 0.05


# =========================================================================================================== shared ==

def _missing(archive, names: Sequence[str]):
    return B7C._missing(archive, names)


def _utc0(day: str) -> int:
    """POSIX seconds of 00:00 UTC on ``day``."""
    return int(datetime(int(day[:4]), int(day[5:7]), int(day[8:10]), tzinfo=UTC).timestamp())


def _iso(o: int) -> str:
    return date.fromordinal(int(o)).isoformat()


def _ord(d: str) -> int:
    return date.fromisoformat(d).toordinal()


def _hourly_oc(archive, name: str) -> tuple:
    """(bar starts int64, open, close) of a Coinbase hourly bundle (rows available at capture), sorted."""
    def load():
        by = {}
        for r in CV._stream(archive, name):
            v = r.get("value") or {}
            o, c = CV._num(v.get("open")), CV._num(v.get("close"))
            if c is not None and c > 0 and o is not None and o > 0 and v.get("t") is not None:
                by[int(v["t"])] = (o, c)
        ks = sorted(by)
        return (np.array(ks, np.int64), np.array([by[k][0] for k in ks], float),
                np.array([by[k][1] for k in ks], float))
    return CAL._cached(archive, ("b13cda_hourly", name), load)


def _exact(ts: np.ndarray, t) -> tuple:
    """(index, found) of bar starts exactly equal to ``t`` (scalar or array)."""
    t = np.asarray(t, np.int64)
    if ts.size == 0:
        return np.zeros(t.shape, int), np.zeros(t.shape, bool)
    j = np.minimum(np.searchsorted(ts, t), ts.size - 1)
    return j, ts[j] == t


def mark_at(ts: np.ndarray, cl: np.ndarray, t_end, max_age: int = 6 * H) -> tuple:
    """Price known at ``t_end``: the close of the hourly bar ending at t_end, or of the latest earlier bar (a no-trade
    hour) within ``max_age``; (price array, stale flags). NaN when none."""
    t_end = np.atleast_1d(np.asarray(t_end, np.int64))
    if ts.size == 0:
        return np.full(t_end.shape, np.nan), np.zeros(t_end.shape, bool)
    start = t_end - H
    j = np.searchsorted(ts, start, side="right") - 1        # the latest bar starting at or before t_end - 1 h
    jj = np.maximum(j, 0)
    ok = (j >= 0) & ((start - ts[jj]) <= max_age)
    return np.where(ok, cl[jj], np.nan), ok & (ts[jj] != start)


def _esc_stud(d, block: int, n_boot: int, alpha: float = ALPHA, max_seeds: Optional[int] = None) -> tuple:
    """(p_greater, p_less, draws): studentized circular block-bootstrap one-sided p's of mean(d) (``block_bootstrap_
    pvalue``), one seed of ``n_boot`` resamples at a time while either p's MC band straddles ``alpha``."""
    d = np.asarray(d, float)
    if d.size < 8 or not np.isfinite(d).all():
        return None, None, 0
    z = np.zeros_like(d)
    cap = CAL.MAX_SEEDS if max_seeds is None else max_seeds
    ps = []
    while True:
        k = len(ps)
        ps.append((block_bootstrap_pvalue(d, z, n_boot=n_boot, block_len=block, seed=SEED + k),
                   block_bootstrap_pvalue(-d, z, n_boot=n_boot, block_len=block, seed=SEED + k)))
        pg, pl = float(np.mean([p[0] for p in ps])), float(np.mean([p[1] for p in ps]))
        nd = n_boot * len(ps)
        if len(ps) >= cap or (CAL.decide_p(pg, nd, alpha) is not None and CAL.decide_p(pl, nd, alpha) is not None):
            return pg, pl, nd


def _bp(x, nd: int = 2) -> str:
    return B7C._bp(x, nd)


def _pc(x, nd: int = 2) -> str:
    return B7C._pc(x, nd)


def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:+.{nd}f}"


def _mean(x) -> Optional[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else None


def _sr(x) -> Optional[float]:
    x = np.asarray(x, float)
    return float(sharpe_ratio(x)) if x.size > 2 and x.std(ddof=1) > 0 else None


def _fomc_cpi_days(archive) -> set:
    """FOMC decision days and the day after (scheduled; usable ahead) and CPI release days, when archived."""
    out = set()
    if B7C._has(archive, "fomc-meetings"):
        for r in CAL._rows(archive, "fomc-meetings"):
            v = r.get("value") or {}
            if v.get("decision_day") and not v.get("future"):
                d = v["decision_day"]
                out.update({d, (date.fromisoformat(d) + timedelta(days=1)).isoformat()})
    if B7C._has(archive, "macro-release-cpi"):
        out.update((r.get("value") or {}).get("day") for r in CAL._rows(archive, "macro-release-cpi"))
    out.discard(None)
    return out


# ============================================================================== T-614 Deribit expiry-Friday reversal ==

T614_B = "coinbase-hourly-BTC-USD"
T614_DELIV = "deribit-delivery-prices-btc"
T614_FUND = "deribit-funding-BTC-PERPETUAL"
T614_START, T614_END = "2019-05-01", "2026-10-31"
T614_SPLIT = "2023-01-01"
T614_BLOCK = 28                      # 4-week circular blocks over the calendar (days)
T614_NBOOT = 5000
T614_COST = 0.0010                   # 10 bp round trip
T614_STRESS = 0.0120                 # Coinbase Intro taker 0.60% per side (batch6c_kraken.COINBASE_TIERS)
T614_MIN_N = 80


def last_friday(y: int, m: int) -> date:
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d


def is_expiry_friday(day: str) -> bool:
    d = date.fromisoformat(day)
    return d.weekday() == 4 and d == last_friday(d.year, d.month)


def day_marks(ts: np.ndarray, op: np.ndarray, cl: np.ndarray, days: Sequence[str]) -> dict:
    """Per UTC day: r1 = ln(P08 / P00) and r2 = ln(P16 / P08) from bar-end marks (00:00 = close of the bar starting
    23:00 the day before, 08:00 = close of the bar starting 07:00, 16:00 = close of the bar starting 15:00), the fade
    side -sign(r1) decided at 08:00, and the trade's gross return from the open of the bar starting 08:00 to the close of
    the bar starting 15:00. Every bar must exist exactly (else ``ok`` False)."""
    t0 = np.array([_utc0(d) for d in days], np.int64)
    j00, k00 = _exact(ts, t0 - H)
    j08, k08 = _exact(ts, t0 + 7 * H)
    jo, ko = _exact(ts, t0 + 8 * H)
    j16, k16 = _exact(ts, t0 + 15 * H)
    ok = k00 & k08 & ko & k16
    p00, p08, o08, p16 = cl[j00], cl[j08], op[jo], cl[j16]
    with np.errstate(divide="ignore", invalid="ignore"):
        r1 = np.where(ok, np.log(p08 / p00), np.nan)
        r2 = np.where(ok, np.log(p16 / p08), np.nan)
        side = -np.sign(r1)
        gross = np.where(ok, side * (p16 / o08 - 1.0), np.nan)
    ok &= np.isfinite(r1) & np.isfinite(r2) & np.isfinite(gross)
    return {"ok": ok, "r1": r1, "r2": r2, "side": side, "gross": gross, "p08": np.where(ok, p08, np.nan)}


def _grp_slope(X: np.ndarray, Y: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Row-wise OLS slope (with intercept) of Y on X over the entries flagged by M."""
    m = M.astype(float)
    n = m.sum(axis=1)
    sx, sy = (X * m).sum(axis=1), (Y * m).sum(axis=1)
    sxx, sxy = (X * X * m).sum(axis=1), (X * Y * m).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        vx = sxx - sx * sx / n
        b = (sxy - sx * sy / n) / vx
    return np.where((n > 2) & (vx > 0), b, np.nan)


def slope(x, y, m) -> Optional[float]:
    b = _grp_slope(np.asarray(x, float)[None], np.asarray(y, float)[None], np.asarray(m, bool)[None])[0]
    return float(b) if np.isfinite(b) else None


def slope_diff_draws(x, y, ga, gb, block: int, n_boot: int, seed: int) -> np.ndarray:
    """Circular-block (calendar) bootstrap draws of slope(ga) - slope(gb); x, y on the full calendar (0 off-group)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ga, gb = np.asarray(ga, bool), np.asarray(gb, bool)
    rng = np.random.default_rng(seed)
    out, done = [], 0
    while done < n_boot:
        k = min(250, n_boot - done)
        idx = CAL._boot_idx(rng, x.size, block, k)
        X, Y = x[idx], y[idx]
        out.append(_grp_slope(X, Y, ga[idx]) - _grp_slope(X, Y, gb[idx]))
        done += k
    d = np.concatenate(out)
    return d[np.isfinite(d)]


def slope_diff_test(x, y, ga, gb, block: int = T614_BLOCK, n_boot: int = T614_NBOOT) -> dict:
    """Point slope difference, percentile 95% CI and the one-sided bootstrap p's (p_less = share of draws >= 0 for
    H0 diff >= 0; p_greater = share <= 0), escalated by ``escalate_p``."""
    x0 = np.where(ga | gb, np.nan_to_num(x), 0.0)
    y0 = np.where(ga | gb, np.nan_to_num(y), 0.0)
    pa, pb = slope(x0, y0, ga), slope(x0, y0, gb)
    diff = None if pa is None or pb is None else pa - pb
    first = {}

    def batch(k):
        d = slope_diff_draws(x0, y0, ga, gb, block, n_boot, SEED + k)
        if k == 0:
            first["ci"] = [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))] if d.size else [None, None]
        if not d.size:
            return None, None
        return float((np.sum(d <= 0) + 1) / (d.size + 1)), float((np.sum(d >= 0) + 1) / (d.size + 1))

    pg, pl, nd = CAL.escalate_p(batch, n_boot, 1, CAL.MAX_SEEDS) if diff is not None else (None, None, 0)
    return {"slope_a": pa, "slope_b": pb, "diff": diff, "ci": first.get("ci", [None, None]), "p_greater": pg, "p_less": pl,
            "draws": nd, "n_a": int(np.sum(ga)), "n_b": int(np.sum(gb))}


def expiry_reversal(days: Sequence[str], mk: dict, events: set = frozenset(), split: str = T614_SPLIT,
                    cost: float = T614_COST, min_n: int = T614_MIN_N, n_boot: int = T614_NBOOT) -> dict:
    """T-614 criteria on the day marks of a full UTC calendar ``days``."""
    days = list(days)
    ok = mk["ok"]
    wd = np.array([date.fromisoformat(d).weekday() for d in days])
    exp = np.array([is_expiry_friday(d) for d in days]) & ok
    quarterly = exp & np.array([int(d[5:7]) in (3, 6, 9, 12) for d in days])
    ofri = (wd == 4) & ~exp & ok
    mt = (wd <= 3) & ok
    x, y = mk["r1"], mk["r2"]
    main = slope_diff_test(x, y, exp, mt, n_boot=n_boot)
    first = np.array([d < split for d in days])
    halves = [slope(np.nan_to_num(x), np.nan_to_num(y), exp & h) for h in (first, ~first)]
    halves_mt = [slope(np.nan_to_num(x), np.nan_to_num(y), mt & h) for h in (first, ~first)]
    hd = [None if a is None or b is None else a - b for a, b in zip(halves, halves_mt)]
    trade = mk["gross"]
    sel = exp & (mk["side"] != 0)
    net = trade[sel] - cost
    pg, pl, dr = _esc_stud(net, 1, n_boot)
    m_net = _mean(net)
    tci = CAL.mean_ci(net, 1, n_boot) if net.size > 2 else [None, None]
    n = int(exp.sum())
    d = main["diff"]
    rows = [(f"slope difference expiry Fridays minus Mon-Thu {_f(d)} < 0 with one-sided p < 0.05 (p {CAL._mc(main['p_less'], main['draws'])}, "
             f"95% CI {_f(main['ci'][0])} to {_f(main['ci'][1])})",
             (False if d is None or not d < 0 else CAL.decide_p(main["p_less"], main["draws"])),
             CAL.decide_p(main["p_greater"], main["draws"]) is True),
            (f"slope difference negative in both halves (split {split}: {_f(hd[0])} / {_f(hd[1])})",
             None if any(h is None for h in hd) else all(h < 0 for h in hd), False),
            (f"net mean fade trade on expiry Fridays {_bp(m_net)} at a {cost * 1e4:.0f} bp round trip with a one-sided 95% "
             f"lower bound > 0 (p {CAL._mc(pg, dr)})", B7C._sig_crit(m_net, pg, dr), CAL.decide_p(pl, dr) is True)]
    v, why, crit = CAL._judge(rows, n, min_n, "expiry Fridays")
    # reported
    other = slope_diff_test(x, y, ofri, mt, n_boot=n_boot)
    q_nq = slope_diff_test(x, y, quarterly, exp & ~quarterly, n_boot=n_boot)
    keep = exp & ~np.array([dd in events for dd in days])
    rob = {"n_dropped": int((exp & ~keep).sum()),
           "slope_diff": (None if slope(np.nan_to_num(x), np.nan_to_num(y), keep) is None or main["slope_b"] is None
                          else slope(np.nan_to_num(x), np.nan_to_num(y), keep) - main["slope_b"]),
           "trade_net": _mean(trade[keep & (mk["side"] != 0)] - cost)}
    mt_trade = _mean(trade[mt & (mk["side"] != 0)] - cost)
    th = [_mean(trade[sel & h] - cost) for h in (first, ~first)]
    by_year = defaultdict(list)
    for dd, t in zip(np.array(days)[sel], trade[sel]):
        by_year[dd[:4]].append(t - cost)
    return {"verdict": v, "why": why, "criteria": crit, "n": n, "main": main, "halves_slope_diff": hd,
            "halves_slope_expiry": halves, "trade_mean_net": m_net, "trade_mean_gross": _mean(trade[sel]), "trade_ci": tci,
            "trade_p": pg, "trade_draws": dr, "trade_stress_net": _mean(trade[sel] - T614_STRESS), "trade_halves": th,
            "n_trades": int(sel.sum()), "other_fridays": other, "quarterly_vs_monthly": q_nq, "fomc_cpi_dropped": rob,
            "mon_thu_fade_net": mt_trade, "n_quarterly": int(quarterly.sum()), "n_other_fridays": int(ofri.sum()),
            "n_mon_thu": int(mt.sum()), "trade_by_year": {k: float(np.mean(v_)) for k, v_ in sorted(by_year.items())}}


def _deribit_vs_coinbase(archive, days, mk) -> dict:
    """Reported: Deribit's 08:00 delivery TWAP and the funding bundle's 08:00 index print vs Coinbase's 08:00 mark on
    expiry Fridays (mean |log difference| and mean signed, bp)."""
    deliv = {}
    for r in (CV._stream(archive, T614_DELIV) if B7C._has(archive, T614_DELIV) else ()):
        v = r.get("value") or {}
        p = CV._num(v.get("delivery_price"))
        if p and v.get("date"):
            deliv[v["date"]] = p
    idx08 = {}
    for r in (CV._stream(archive, T614_FUND) if B7C._has(archive, T614_FUND) else ()):
        v = r.get("value") or {}
        t = v.get("timestamp")
        p = CV._num(v.get("index_price"))
        if t is not None and p and int(t) % (DAY * 1000) == 8 * H * 1000:
            idx08[CV._dday(int(t) / 1000)] = p
    out = {}
    for nm, src in (("delivery_twap", deliv), ("index_0800", idx08)):
        dv = [math.log(src[d] / p) for d, p, ok in zip(days, mk["p08"], mk["ok"]) if ok and is_expiry_friday(d) and d in src]
        out[nm] = {"n": len(dv), "mean_abs_bp": float(np.mean(np.abs(dv)) * 1e4) if dv else None,
                   "mean_bp": float(np.mean(dv) * 1e4) if dv else None}
    return out


def b13_cryptoderiv_a_expiry_reversal(archive):
    """T-614: 08-16 UTC on 00-08 UTC slope on Deribit monthly-expiry Fridays vs Mon-Thu, and the fade trade."""
    miss = _missing(archive, [T614_B])            # the Deribit bundles feed a reported row only
    if miss:
        return miss
    ts, op, cl = _hourly_oc(archive, T614_B)
    last = CV._dday(int(ts[-1])) if ts.size else T614_START
    o0, o1 = _ord(T614_START), min(_ord(T614_END), _ord(last))
    days = [_iso(o) for o in range(o0, o1 + 1)]
    mk = day_marks(ts, op, cl, days)
    j = expiry_reversal(days, mk, _fomc_cpi_days(archive))
    dc = _deribit_vs_coinbase(archive, days, mk)
    m, o, q = j["main"], j["other_fridays"], j["quarterly_vs_monthly"]
    p223 = None if m["p_less"] is None else min(1.0, 2 * m["p_less"])
    reason = (f"Coinbase BTC-USD hourly marks by bar end, {days[0]}..{days[-1]}: {j['n']} monthly/quarterly expiry Fridays "
              f"(last Friday, rule calendar; {j['n_quarterly']} quarterly), {j['n_other_fridays']} other Fridays, {j['n_mon_thu']} "
              f"Mon-Thu days with all four bars. Slope of r(08-16) on r(00-08): expiry {_f(m['slope_a'])} vs Mon-Thu "
              f"{_f(m['slope_b'])}, difference {_f(m['diff'])} (4-week calendar blocks, one-sided p {CAL._mc(m['p_less'], m['draws'])}; "
              f"95% CI {_f(m['ci'][0])} to {_f(m['ci'][1])}); halves {_f(j['halves_slope_diff'][0])} / {_f(j['halves_slope_diff'][1])}. "
              f"Fade trade on expiry Fridays ({j['n_trades']}): gross {_bp(j['trade_mean_gross'])}, net {_bp(j['trade_mean_net'])} at 10 bp "
              f"(p {CAL._mc(j['trade_p'], j['trade_draws'])}; halves {_bp(j['trade_halves'][0])} / {_bp(j['trade_halves'][1])}), "
              f"{_bp(j['trade_stress_net'])} at the 120 bp Coinbase retail-taker stress; the same fade on Mon-Thu nets "
              f"{_bp(j['mon_thu_fade_net'])}. Reported: other Fridays minus Mon-Thu slope {_f(o['diff'])} (p {_f(o['p_less'], 4)}); "
              f"quarterly minus non-quarterly monthly {_f(q['diff'])} (p {_f(q['p_less'], 4)}); FOMC/CPI-coincident expiries "
              f"dropped ({j['fomc_cpi_dropped']['n_dropped']}): slope difference {_f(j['fomc_cpi_dropped']['slope_diff'])}, trade net "
              f"{_bp(j['fomc_cpi_dropped']['trade_net'])}; Deribit 08:00 delivery TWAP vs Coinbase 08:00 mark mean |diff| "
              f"{_f(dc['delivery_twap']['mean_abs_bp'], 1)} bp (n {dc['delivery_twap']['n']}), 08:00 index print "
              f"{_f(dc['index_0800']['mean_abs_bp'], 1)} bp; T-223 counted as a prior trial on this window (2-trial Bonferroni "
              f"slope p {_f(p223, 4)}, context only); stage 2 (sign of GEX) is forward only and not part of this verdict — " + j["why"])
    stat = {k: j[k] for k in ("n", "main", "halves_slope_diff", "halves_slope_expiry", "trade_mean_net", "trade_mean_gross",
                              "trade_ci", "trade_p", "trade_draws", "trade_stress_net", "trade_halves", "n_trades",
                              "other_fridays", "quarterly_vs_monthly", "fomc_cpi_dropped", "mon_thu_fade_net", "n_quarterly",
                              "n_other_fridays", "n_mon_thu", "trade_by_year", "criteria")}
    stat.update(deribit_vs_coinbase=dc, window=[days[0], days[-1]], cost_round_trip=T614_COST, stress_round_trip=T614_STRESS,
                bonferroni_with_t223=p223, rule10="calendar events (expiry Fridays): no grid phase")
    return _out(stat, j["n"], j["verdict"], reason)


# ============================================================================ T-613 BTC weekend -> Monday ETF session ==

T613_BTC = "coinbase-hourly-BTC-USD"
T613_ETFS = ("SPY", "QQQ", "IWM")
T613_START, T613_END = "2020-01-01", "2026-09-30"
T613_HIST = "2019-01-01"
T613_MIN_PRIOR = 52
T613_SPLIT = "2022-05-09"
T613_COST = 0.0002
T613_BLOCK = 4                       # weekends per ~monthly block
T613_NBOOT = 5000
T613_MIN_N = 300


def gap_events(sessions: Sequence[str], kind: str = "weekend") -> list:
    """(previous session, next session) pairs: ``weekend`` = a Saturday lies between them (holiday Mondays roll to the
    first session after; a Friday holiday starts the weekend at Thursday's close); ``wednesday`` = a Tuesday session
    followed directly by a Wednesday session (the placebo)."""
    out = []
    for a, b in zip(sessions[:-1], sessions[1:]):
        da, db = date.fromisoformat(a), date.fromisoformat(b)
        if kind == "weekend":
            if any((da + timedelta(days=k)).weekday() == 5 for k in range(1, (db - da).days)):
                out.append((a, b))
        elif da.weekday() == 1 and (db - da).days == 1:
            out.append((a, b))
    return out


def btc_window_returns(events: Sequence[tuple], ts: np.ndarray, cl: np.ndarray, end_hhmm: str = "09:00") -> dict:
    """BTC log return from the close of the hourly bar ending at the previous session's close (16:00 ET; 13:00 ET on an
    early close) to the close of the bar ending at ``end_hhmm`` ET on the next session's date (30 minutes before the
    09:30 open), with the stale counts."""
    t_a = np.array([CV.close_bar_start(a) + H for a, _ in events], np.int64)
    t_b = np.array([int(CV.et_epoch(b, end_hhmm)) for _, b in events], np.int64)
    pa, sa = mark_at(ts, cl, t_a)
    pb, sb = mark_at(ts, cl, t_b)
    with np.errstate(divide="ignore", invalid="ignore"):
        x = np.log(pb / pa)
    return {"x": x, "stale": int(sa.sum() + sb.sum()), "t_a": t_a, "t_b": t_b}


def expanding_tercile_flags(x, eligible=None, min_prior: int = T613_MIN_PRIOR) -> tuple:
    """(flag, valid): x[k] at or below the 1/3 quantile of the finite x of every earlier eligible observation, valid when
    at least ``min_prior`` exist. Uses prior observations only."""
    x = np.asarray(x, float)
    el = np.isfinite(x) if eligible is None else (np.asarray(eligible, bool) & np.isfinite(x))
    flag, valid = np.zeros(x.size, bool), np.zeros(x.size, bool)
    hist = []
    for k in range(x.size):
        if len(hist) >= min_prior and np.isfinite(x[k]):
            valid[k] = True
            flag[k] = x[k] <= float(np.quantile(np.array(hist), 1.0 / 3.0))
        if el[k]:
            hist.append(float(x[k]))
    return flag, valid


def residual_flags(x, g, eligible, min_prior: int = T613_MIN_PRIOR) -> tuple:
    """Gap-residualised arm: at k, OLS of x on the SPY gap g over the prior eligible weekends (>= min_prior), the
    residual of k under that fit, flagged when at or below the 1/3 quantile of the prior residuals under the same fit."""
    x, g = np.asarray(x, float), np.asarray(g, float)
    el = np.asarray(eligible, bool) & np.isfinite(x) & np.isfinite(g)
    flag, valid = np.zeros(x.size, bool), np.zeros(x.size, bool)
    for k in range(x.size):
        idx = np.flatnonzero(el[:k])
        if idx.size >= min_prior and np.isfinite(x[k]) and np.isfinite(g[k]):
            X = np.column_stack([np.ones(idx.size), g[idx]])
            beta, *_ = np.linalg.lstsq(X, x[idx], rcond=None)
            res = x[idx] - X @ beta
            flag[k] = (x[k] - beta[0] - beta[1] * g[k]) <= float(np.quantile(res, 1.0 / 3.0))
            valid[k] = True
    return flag, valid


def session_oc(bars: dict, days: Sequence[str]) -> np.ndarray:
    """Open-to-close return (raw close / raw open - 1) of each session in ``days`` (NaN when absent)."""
    pos = {d: i for i, d in enumerate(bars["days"])}
    out = np.full(len(days), np.nan)
    for k, d in enumerate(days):
        i = pos.get(d)
        if i is not None and bars["open"][i] > 0:
            out[k] = bars["close"][i] / bars["open"][i] - 1.0
    return out


def session_gap(bars: dict, events: Sequence[tuple]) -> np.ndarray:
    """Close-to-open gap of the next session (dividend-adjusted: adjusted open / previous adjclose - 1)."""
    pos = {d: i for i, d in enumerate(bars["days"])}
    out = np.full(len(events), np.nan)
    for k, (a, b) in enumerate(events):
        i, j = pos.get(a), pos.get(b)
        if i is not None and j is not None:
            out[k] = bars["aopen"][j] / bars["adj"][i] - 1.0
    return out


def contrast_eval(oc, flag, mask, days_next: Sequence[str], split: str = T613_SPLIT, cost: float = T613_COST,
                  alpha: float = ALPHA, n_boot: int = T613_NBOOT, pvals: bool = True) -> dict:
    """Contrast (flagged minus other) of ``oc`` over ``mask``, its studentized p's (block T613_BLOCK, escalated against
    ``alpha``), halves and the flat-on-signal rule vs always-long net of ``cost``."""
    oc, f, m = np.asarray(oc, float), np.asarray(flag, bool), np.asarray(mask, bool) & np.isfinite(oc)
    x, ff = oc[m], f[m]
    dn = np.array(days_next)[m]
    out = {"n": int(m.sum()), "n_flag": int(ff.sum()), "contrast": None, "p_less": None, "p_greater": None, "draws": 0,
           "halves": [None, None], "rule_net": None, "always_net": None, "rule_minus_always": None}
    if ff.sum() < 2 or (~ff).sum() < 2:
        return out
    d = CAL.flag_diff_series(x, ff)
    out["contrast"] = float(d.mean())
    out["mean_flag"], out["mean_other"] = float(x[ff].mean()), float(x[~ff].mean())
    if pvals:
        out["p_greater"], out["p_less"], out["draws"] = _esc_stud(d, T613_BLOCK, n_boot, alpha)
        out["ci"] = CAL.mean_ci(d, T613_BLOCK, n_boot)
    hv = []
    for h in (dn < split, dn >= split):
        hv.append(CAL._point_diff(x[h], ff[h]) if (ff[h].sum() and (~ff[h]).sum()) else None)
    out["halves"] = hv
    out["rule_net"] = float(np.mean(np.where(ff, 0.0, x - cost)))
    out["always_net"] = float(np.mean(x - cost))
    out["rule_minus_always"] = out["rule_net"] - out["always_net"]
    return out


def etf_criteria(per: dict, m_tests: int = 3, alpha: float = ALPHA) -> tuple:
    """(ok, text) of 'for at least one ETF: contrast < 0 with Bonferroni one-sided p < alpha, negative in both halves,
    rule net above always-long': True if any ETF passes all three, False if every ETF fails one, else None."""
    oks, parts = [], []
    for s, e in per.items():
        c = e["contrast"]
        sig = (False if c is None or not c < 0 else CAL.decide_p(e["p_less"], e["draws"], alpha / m_tests))
        hv = None if any(h is None for h in e["halves"]) else all(h < 0 for h in e["halves"])
        rl = None if e["rule_minus_always"] is None else e["rule_minus_always"] > 0
        sub = [sig, hv, rl]
        ok = False if any(o is False for o in sub) else (True if all(o is True for o in sub) else None)
        oks.append(ok)
        padj = None if e["p_less"] is None else min(1.0, m_tests * e["p_less"])
        parts.append(f"{s}: contrast {_bp(c)} (Bonferroni p {_f(padj, 4)}, raw {CAL._mc(e['p_less'], e['draws'])}) -> {sig}, "
                     f"halves {_bp(e['halves'][0])} / {_bp(e['halves'][1])} -> {hv}, rule minus always-long "
                     f"{_bp(e['rule_minus_always'])} -> {rl}")
    if any(o is True for o in oks):
        ok = True
    elif all(o is False for o in oks):
        ok = False
    else:
        ok = None
    return ok, "; ".join(parts)


def _local_es(events: Sequence[tuple]) -> Optional[dict]:
    """ES_F 60m local bars (start-stamped): Sunday 18:00 ET reopen open and the close of the bar starting 15:00 ET on
    the next session (when that is the Monday right after the weekend)."""
    try:
        from mandel.ml.features import load_bars
        df = load_bars("60m", "ES_F")
    except Exception:  # noqa: BLE001 - optional local data
        return None
    if df is None or df.empty:
        return None
    ts = np.array([int(t.timestamp()) for t in df.index], np.int64)   # POSIX seconds whatever the index unit
    o, c = df["o"].to_numpy(float), df["c"].to_numpy(float)
    pos = {int(t): i for i, t in enumerate(ts)}
    out = {"ret": np.full(len(events), np.nan), "t_sun": np.zeros(len(events), np.int64)}
    for k, (a, b) in enumerate(events):
        db = date.fromisoformat(b)
        if db.weekday() != 0:
            continue
        sun = (db - timedelta(days=1)).isoformat()
        t_sun = int(CV.et_epoch(sun, "18:00"))
        out["t_sun"][k] = t_sun
        i, j = pos.get(t_sun), pos.get(int(CV.et_epoch(b, "15:00")))
        if i is not None and j is not None and o[i] > 0:
            out["ret"][k] = c[j] / o[i] - 1.0
    out["first"] = CV._dday(int(ts[0]))
    return out


def b13_cryptoderiv_a_btc_weekend_monday(archive):
    """T-613: bottom-tercile Coinbase BTC weekend return -> lower first-session open-to-close in SPY / QQQ / IWM."""
    need = [T613_BTC] + [CV.dh(s) for s in T613_ETFS]
    miss = _missing(archive, need)
    if miss:
        return miss
    ts, _, cl = _hourly_oc(archive, T613_BTC)
    bars = {s: CV._bars(archive, CV.dh(s)) for s in T613_ETFS}
    sessions = [d for d in bars["SPY"]["days"] if d >= "2018-12-01"]
    ev = gap_events(sessions, "weekend")
    ev = [e for e in ev if e[1] >= T613_HIST]
    w = btc_window_returns(ev, ts, cl)
    x = w["x"]
    nxt = [b for _, b in ev]
    flag, valid = expanding_tercile_flags(x)
    win = valid & np.array([T613_START <= b <= T613_END for b in nxt])
    per = {s: contrast_eval(session_oc(bars[s], nxt), flag, win, nxt, alpha=ALPHA / len(T613_ETFS)) for s in T613_ETFS}
    ok, txt = etf_criteria(per)
    n = int(win.sum())
    rows = [(f"for at least one ETF: contrast < 0 with Bonferroni-adjusted (x3) one-sided p < 0.05, negative in both halves "
             f"(split {T613_SPLIT}) and the flat-on-signal rule's net mean above always-long after a 2 bp round trip [{txt}]", ok, False)]
    v, why, crit = CAL._judge(rows, n, T613_MIN_N, "weekends")
    # ------------------------------------------------------------------ reported arms
    rep = {}
    spy_gap = session_gap(bars["SPY"], ev)
    rep["gap_contrast"] = {s: contrast_eval(session_gap(bars[s], ev), flag, win, nxt, pvals=False)["contrast"] for s in T613_ETFS}
    rf, rv = residual_flags(x, spy_gap, np.isfinite(x))
    winr = rv & np.array([T613_START <= b <= T613_END for b in nxt])
    rep["gap_residualised"] = {s: {k: contrast_eval(session_oc(bars[s], nxt), rf, winr, nxt, pvals=False)[k]
                                   for k in ("n", "contrast", "halves", "rule_minus_always")} for s in T613_ETFS}
    if B7C._has(archive, CV.dh("COIN")):
        cb = CV._bars(archive, CV.dh("COIN"))
        c = contrast_eval(session_oc(cb, nxt), flag, win, nxt)
        rep["COIN"] = {k: c[k] for k in ("n", "contrast", "p_less", "halves", "rule_minus_always")}
    else:
        rep["COIN"] = "daily-history-COIN not archived"
    es = _local_es(ev)
    if es is not None:
        t_sun = np.where(es["t_sun"] > 0, es["t_sun"], w["t_a"])
        p_fri, _ = mark_at(ts, cl, w["t_a"])
        p_sun, _ = mark_at(ts, cl, t_sun)
        with np.errstate(divide="ignore", invalid="ignore"):
            xs = np.where(es["t_sun"] > 0, np.log(p_sun / p_fri), np.nan)
        fs, vs = expanding_tercile_flags(xs)
        wes = vs & np.isfinite(es["ret"]) & np.array([b <= T613_END for b in nxt])
        c = contrast_eval(es["ret"], fs, wes, nxt, pvals=False)
        rep["ES_sunday_reopen_to_monday_close"] = {"n": c["n"], "n_flag": c["n_flag"], "contrast": c["contrast"],
                                                   "local_bars_from": es["first"],
                                                   "signal": "BTC Friday NYSE close -> Sunday 18:00 ET (the reopen)"}
    else:
        rep["ES_sunday_reopen_to_monday_close"] = "local 60m ES_F bars not available"
    wev = [e for e in gap_events(sessions, "wednesday") if e[1] >= T613_HIST]
    ww = btc_window_returns(wev, ts, cl)
    wf, wv = expanding_tercile_flags(ww["x"])
    wnext = [b for _, b in wev]
    wwin = wv & np.array([T613_START <= b <= T613_END for b in wnext])
    rep["wednesday_placebo"] = {s: {k: c_[k] for k in ("n", "contrast", "p_less", "halves")}
                                for s in T613_ETFS for c_ in [contrast_eval(session_oc(bars[s], wnext), wf, wwin, wnext,
                                                                            n_boot=2000)]}
    evd = _fomc_cpi_days(archive)
    fc = np.array([b in evd for b in nxt])
    rep["fomc_cpi_sessions"] = {"n": int((fc & win).sum()),
                                "contrast_excluding": {s: contrast_eval(session_oc(bars[s], nxt), flag, win & ~fc, nxt,
                                                                        pvals=False)["contrast"] for s in T613_ETFS}}
    rep["weekend_gap_mean_t549_context"] = {s: _mean(session_gap(bars[s], ev)[win]) for s in T613_ETFS}
    by_year = {}
    for yv in sorted({b[:4] for b, m in zip(nxt, win) if m}):
        my = win & np.array([b[:4] == yv for b in nxt])
        by_year[yv] = {s: CAL._point_diff(session_oc(bars[s], nxt)[my], flag[my]) for s in T613_ETFS}
    rep["by_year"] = by_year
    xs_w = x[win]
    reason = (f"{len(ev)} weekends from {T613_HIST} (Coinbase BTC hourly, Friday NYSE-close bar -> bar ending 09:00 ET of "
              f"the next session; {w['stale']} stale marks), {n} in {T613_START}..{T613_END} with >= {T613_MIN_PRIOR} prior "
              f"weekends, {int(flag[win].sum())} flagged (expanding bottom tercile; flagged mean BTC {_pc(_mean(xs_w[flag[win]]))} vs "
              f"{_pc(_mean(xs_w[~flag[win]]))}). Open-to-close contrasts: "
              + "; ".join(f"{s} {_bp(per[s]['contrast'])} (p {CAL._mc(per[s]['p_less'], per[s]['draws'])}, halves "
                          f"{_bp(per[s]['halves'][0])} / {_bp(per[s]['halves'][1])}, rule minus always-long "
                          f"{_bp(per[s]['rule_minus_always'])})" for s in T613_ETFS)
              + ". Reported: gap (not traded) contrasts " + ", ".join(f"{s} {_bp(v_)}" for s, v_ in rep["gap_contrast"].items())
              + "; gap-residualised " + ", ".join(f"{s} {_bp(v_['contrast'])}" for s, v_ in rep["gap_residualised"].items())
              + f"; COIN {_bp(rep['COIN']['contrast']) if isinstance(rep['COIN'], dict) else rep['COIN']}"
              + "; ES arm " + (f"{_bp(rep['ES_sunday_reopen_to_monday_close']['contrast'])} over "
                               f"{rep['ES_sunday_reopen_to_monday_close']['n']}" if isinstance(rep['ES_sunday_reopen_to_monday_close'], dict)
                               else rep['ES_sunday_reopen_to_monday_close'])
              + "; Wednesday placebo " + ", ".join(f"{s} {_bp(v_['contrast'])} (p {_f(v_['p_less'], 3)})"
                                                   for s, v_ in rep["wednesday_placebo"].items())
              + f"; {rep['fomc_cpi_sessions']['n']} FOMC/CPI target sessions — " + why)
    stat = {"per_etf": per, "n_weekends": n, "n_flagged": int(flag[win].sum()), "n_events_all": len(ev), "stale_marks": w["stale"],
            "criteria": crit, "reported": rep, "split": T613_SPLIT, "cost_round_trip": T613_COST, "block_weekends": T613_BLOCK,
            "rule10": "weekend events: no grid phase"}
    return _out(stat, n, v, reason)


# ========================================================================= T-612 CME bitcoin leveraged-funds change ==

T612_F = "cftc-cot-tff-f-133741"
T612_FO = "cftc-cot-tff-fo-133741"
T612_H = "coinbase-hourly-BTC-USD"
T612_D = "coinbase-daily-BTC-USD"
T612_FUT = "daily-history-BTC-F"
T612_IBIT = "daily-history-IBIT"
T612_DTB3 = "fred-DTB3"
T612_POST = ("2022-05-01", "2026-09-30")
T612_SUBS = (("2022-05-01", "2023-12-31"), ("2024-01-01", "2026-09-30"))
T612_PRE = ("2018-04-01", "2022-04-30")
T612_LAG = 4
T612_T = 2.0
T612_COST = 0.0010
T612_STRESS = 0.0050
T612_BLOCK = 8
T612_NPERM = 2000
T612_MIN_N = 200
T612_ZWIN = 52
T612_TRIALS = 3                      # the 2 arms here and T-405


def cot_records(rows: Sequence[dict], use: str = "av") -> list:
    """Weekly CME bitcoin TFF records in report-date order: LF, AM (net / OI), their changes against the previous report,
    the decision time ``t`` (stored available_at, or the schedule release when ``use`` = 'rule'), superseded flag (a later
    report public no later than this one). Rows with pit 'not_realtime' are dropped."""
    recs, seen = [], set()
    for r in rows:
        v = r.get("value") or {}
        rd = str(v.get("report_date") or v.get("report_date_as_yyyy_mm_dd") or "")[:10]
        if len(rd) != 10 or rd in seen or v.get("pit") == "not_realtime" or not r.get("available_at"):
            continue
        lo, sh = CV._num(v.get("lev_money_positions_long")), CV._num(v.get("lev_money_positions_short"))
        al, ash = CV._num(v.get("asset_mgr_positions_long")), CV._num(v.get("asset_mgr_positions_short"))
        oi = CV._num(v.get("open_interest_all"))
        if lo is None or sh is None or not oi or oi <= 0:
            continue
        seen.add(rd)
        av = CV._epoch(r["available_at"])
        rule = CV._epoch(v["release_rule"]) if v.get("release_rule") else av
        recs.append({"report_date": rd, "t": av if use == "av" else rule, "av": av, "rule": rule, "pit": v.get("pit"),
                     "lf": (lo - sh) / oi, "am": (al - ash) / oi if al is not None and ash is not None else float("nan"),
                     "oi": oi})
    recs.sort(key=lambda q: q["report_date"])
    for i, q in enumerate(recs):
        q["dlf"] = q["lf"] - recs[i - 1]["lf"] if i else float("nan")
        q["dam"] = q["am"] - recs[i - 1]["am"] if i else float("nan")
        past = np.array([p["lf"] for p in recs[max(0, i - T612_ZWIN + 1): i + 1]])
        q["z"] = float((q["lf"] - past.mean()) / past.std(ddof=1)) if past.size == T612_ZWIN and past.std(ddof=1) > 0 else float("nan")
        q["superseded"] = any(p["t"] <= q["t"] for p in recs[i + 1:])
    return recs


def entry_exit(t_dec: float, hourly: tuple, daily: dict, hold: int = 7 * DAY) -> Optional[dict]:
    """Entry at the open of the first Coinbase hourly bar starting at or after ``t_dec`` (the first daily bar when that
    precedes the hourly bundle), exit at the open of the first bar starting at or after entry + ``hold``, and the prior
    7-day return to the entry (open of the first bar starting at or after entry - 7 days)."""
    ts, op, _ = hourly
    if ts.size and t_dec >= ts[0]:
        j = int(np.searchsorted(ts, int(math.ceil(t_dec))))
        if j >= ts.size:
            return None
        te = int(ts[j])
        k = int(np.searchsorted(ts, te + hold))
        if k >= ts.size:
            return None
        p0 = int(np.searchsorted(ts, te - 7 * DAY))
        prior = math.log(op[j] / op[p0]) if te - 7 * DAY >= ts[0] else None
        if prior is None:
            return None
        return {"te": te, "tx": int(ts[k]), "pe": float(op[j]), "px": float(op[k]), "prior": prior, "bar": "hourly"}
    dts = daily["t"]
    j = int(np.searchsorted(dts, int(math.ceil(t_dec))))
    if j >= dts.size:
        return None
    te = int(dts[j])
    k = int(np.searchsorted(dts, te + hold))
    p0 = int(np.searchsorted(dts, te - 7 * DAY))
    if k >= dts.size or te - 7 * DAY < dts[0]:
        return None
    return {"te": te, "tx": int(dts[k]), "pe": float(daily["open"][j]), "px": float(daily["open"][k]),
            "prior": math.log(daily["open"][j] / daily["open"][p0]), "bar": "daily"}


def front_expiry_days(rd: str) -> int:
    d = date.fromisoformat(rd)
    e = last_friday(d.year, d.month)
    if e < d:
        y, m = (d.year + (d.month == 12), d.month % 12 + 1)
        e = last_friday(y, m)
    return (e - d).days


def basis_on(rd: str, fut: dict, hourly: tuple, daily: dict) -> Optional[float]:
    """Annualised CME basis on the as-of Tuesday: ln(BTC=F daily close / Coinbase close of the hourly bar ending 16:00 ET
    (CME's daily settlement time; the Coinbase daily close of that UTC day before the hourly bundle)) x 365 / days to
    the front last-Friday expiry."""
    F = fut.get(rd)
    if not F:
        return None
    ts, _, cl = hourly
    t_end = int(CV.et_epoch(rd, "16:00"))
    if ts.size and t_end - H >= ts[0]:
        px, _ = mark_at(ts, cl, t_end, max_age=3 * H)
        S = float(px[0])
    else:
        S = daily["close_by_day"].get(rd)
    if not S or not np.isfinite(S):
        return None
    return math.log(F / S) * 365.0 / max(1, front_expiry_days(rd))


def cot_table(recs: Sequence[dict], hourly: tuple, daily: dict, fut: dict, bills) -> list:
    """One row per non-superseded report with a complete 7-day forward window and every control."""
    basis = {q["report_date"]: basis_on(q["report_date"], fut, hourly, daily) for q in recs}
    out = []
    for i, q in enumerate(recs):
        b = basis[q["report_date"]]
        bprev = basis[recs[i - 1]["report_date"]] if i else None
        if q["superseded"] or not np.isfinite(q["dlf"]) or b is None or bprev is None:
            continue
        ee = entry_exit(q["t"], hourly, daily)
        if ee is None:
            continue
        de, dx = CV._dday(ee["te"]), CV._dday(ee["tx"])
        out.append({"report_date": q["report_date"], "entry_day": de, "exit_day": dx, "y": math.log(ee["px"] / ee["pe"]),
                    "dlf": q["dlf"], "dam": q["dam"], "z": q["z"], "basis": b, "dbasis": b - bprev, "prior": ee["prior"],
                    "rf": bills.growth(de, dx) if bills is not None else 0.0, "bar": ee["bar"], "te": ee["te"], "t": q["t"]})
    return out


def cot_reg(tab: Sequence[dict], lo: str, hi: str, extra: Sequence[str] = (), lead: str = "dlf") -> dict:
    sel = [q for q in tab if lo <= q["report_date"] <= hi]
    cols = [lead, "basis", "dbasis", "prior"] + list(extra)
    sel = [q for q in sel if all(np.isfinite(q[c]) for c in cols)]
    if len(sel) < 12:
        return {"n": len(sel), "slope": None, "t": None}
    y = np.array([q["y"] for q in sel])
    X = np.array([[q[c] for c in cols] for q in sel])
    o = CAL.ols_nw(y, X, T612_LAG)
    res = {"n": len(sel), "slope": o["slope"], "t": o["t"], "se": o["se"]}
    if extra:
        Xc = np.column_stack([np.ones(len(sel)), X])
        beta = np.linalg.lstsq(Xc, y, rcond=None)[0]
        res["coef_extra"] = float(beta[-1])
        o2 = CAL.ols_nw(y, np.column_stack([X[:, -1], X[:, :-1]]), T612_LAG)
        res["t_extra"] = o2["t"]
    return res


def rule_series(pos: np.ndarray, r: np.ndarray, rf: np.ndarray, cost: float) -> np.ndarray:
    """Weekly excess return of the long/flat rule: pos x (r - rf) - cost x |pos - previous pos| (starts flat)."""
    prev = np.concatenate([[0.0], pos[:-1]])
    return pos * (r - rf) - cost * np.abs(pos - prev)


def rule_perm_test(pos, r, rf, cost: float = T612_COST, block: int = T612_BLOCK, n_perm: int = T612_NPERM) -> dict:
    """Weekly Sharpe(rule) - Sharpe(buy-and-hold) and its block-permutation p (8-week blocks of the position series
    permuted in order against fixed returns, switching costs recomputed), escalated by batches of ``n_perm``."""
    pos, r, rf = np.asarray(pos, float), np.asarray(r, float), np.asarray(rf, float)
    bh = r - rf
    sr_bh = _sr(bh)
    rule = rule_series(pos, r, rf, cost)
    obs = None if _sr(rule) is None or sr_bh is None else _sr(rule) - sr_bh
    n = pos.size
    blocks = [np.arange(s, min(n, s + block)) for s in range(0, n, block)]

    def batch(k):
        rng = np.random.default_rng(SEED + k)
        dr = np.empty(n_perm)
        for b in range(n_perm):
            p = pos[np.concatenate([blocks[i] for i in rng.permutation(len(blocks))])]
            s = _sr(rule_series(p, r, rf, cost))
            dr[b] = (s if s is not None else 0.0) - sr_bh
        return CAL._perm_p(obs, dr)

    if obs is None:
        return {"diff": None, "p_greater": None, "p_less": None, "draws": 0}
    pg, pl, nd = CAL.escalate_p(batch, n_perm, 1, CAL.MAX_PERM_BATCHES)
    return {"diff": obs, "sr_rule": _sr(rule), "sr_bh": sr_bh, "p_greater": pg, "p_less": pl, "draws": nd,
            "share_long": float(pos.mean()), "switches": int(np.abs(np.diff(np.concatenate([[0.0], pos]))).sum()),
            "rule_excess": rule}


def cot_test(tab: Sequence[dict]) -> dict:
    lo, hi = T612_POST
    post = [q for q in tab if lo <= q["report_date"] <= hi]
    main = cot_reg(tab, lo, hi)
    subs = [cot_reg(tab, a, b) for a, b in T612_SUBS]
    pos = np.array([1.0 if q["dlf"] > 0 else 0.0 for q in post])
    r = np.array([math.exp(q["y"]) - 1.0 for q in post])
    rf = np.array([q["rf"] for q in post])
    rp = rule_perm_test(pos, r, rf)
    t = main["t"]
    rows = [(f"post-publication slope on dLF/OI {_f(main['slope'], 4)} > 0 with Newey-West (lag {T612_LAG}) t >= {T612_T} after "
             f"the basis, basis-change and prior-week controls (t {_f(t, 2)}, n {main['n']})",
             None if t is None else bool(t >= T612_T), t is not None and t <= -T612_T),
            (f"slope positive in both post-publication sub-periods (2022-05..2023-12 {_f(subs[0]['slope'], 4)}, t {_f(subs[0]['t'], 2)}; "
             f"2024-01..2026-09 {_f(subs[1]['slope'], 4)}, t {_f(subs[1]['t'], 2)})",
             None if any(s["slope"] is None for s in subs) else all(s["slope"] > 0 for s in subs), False),
            (f"long/flat rule (10 bp per switch) weekly Sharpe minus buy-and-hold {_f(rp['diff'], 4)} > 0 with 8-week "
             f"block-permutation p < 0.05 (p {CAL._mc(rp['p_greater'], rp['draws'])})",
             B7C._sig_crit(rp["diff"], rp["p_greater"], rp["draws"]), CAL.decide_p(rp["p_less"], rp["draws"]) is True)]
    v, why, crit = CAL._judge(rows, main["n"], T612_MIN_N, "post-publication reports")
    return {"verdict": v, "why": why, "criteria": crit, "main": main, "subs": subs, "rule": rp, "n": main["n"], "post": post,
            "pos": pos, "r": r, "rf": rf}


def b13_cryptoderiv_a_cme_lev_funds(archive):
    """T-612: weekly change in CME bitcoin leveraged-funds net / OI -> 7-day BTC return after release, basis-controlled."""
    miss = _missing(archive, [T612_F, T612_H, T612_D, T612_FUT, T612_DTB3])
    if miss:
        return miss
    hourly = _hourly_oc(archive, T612_H)
    cbd = CV._bars(archive, T612_D)
    daily = {"t": np.array([_utc0(d) for d in cbd["days"]], np.int64), "open": np.asarray(cbd["open"], float),
             "close_by_day": dict(zip(cbd["days"], (float(c) for c in cbd["close"])))}
    fb = CV._bars(archive, T612_FUT)
    fut = dict(zip(fb["days"], (float(c) for c in fb["close"])))
    bills = CAL.Bills(CAL._series(archive, T612_DTB3))
    recs = cot_records(CAL._rows(archive, T612_F))
    tab = cot_table(recs, hourly, daily, fut, bills)
    j = cot_test(tab)
    rp, m, s = j["rule"], j["main"], j["subs"]
    # ------------------------------------------------------------------ reported
    rep = {}
    rep["in_sample_replication_2018_04_2022_04"] = cot_reg(tab, *T612_PRE)
    rep["asset_manager_competing"] = cot_reg(tab, *T612_POST, extra=("dam",))
    rep["lf_level_z52_arm"] = cot_reg(tab, *T612_POST, lead="z")
    zpost = [q for q in j["post"] if np.isfinite(q["z"])]
    if len(zpost) > 10:
        zr = rule_series(np.array([1.0 if q["z"] > 0 else 0.0 for q in zpost]), np.array([math.exp(q["y"]) - 1 for q in zpost]),
                         np.array([q["rf"] for q in zpost]), T612_COST)
        rep["lf_level_z52_rule_sr_minus_bh"] = (_sr(zr) or 0.0) - (_sr(np.array([math.exp(q["y"]) - 1 - q["rf"] for q in zpost])) or 0.0)
    else:
        zr = None
    stress = rule_series(j["pos"], j["r"], j["rf"], T612_STRESS)
    rep["rule_50bp_stress_sr_minus_bh"] = None if rp.get("sr_bh") is None or _sr(stress) is None else _sr(stress) - rp["sr_bh"]
    if B7C._has(archive, T612_FO):
        tfo = cot_table(cot_records(CAL._rows(archive, T612_FO)), hourly, daily, fut, bills)
        rep["futures_and_options_report"] = {"post": cot_reg(tfo, *T612_POST), "subs": [cot_reg(tfo, a, b) for a, b in T612_SUBS]}
    else:
        rep["futures_and_options_report"] = "cftc-cot-tff-fo-133741 not archived"
    rtab = cot_table(cot_records(CAL._rows(archive, T612_F), use="rule"), hourly, daily, fut, bills)
    rep["schedule_release_reading"] = {"post": cot_reg(rtab, *T612_POST), "subs": [cot_reg(rtab, a, b) for a, b in T612_SUBS]}
    if rp.get("rule_excess") is not None:
        fam = [_sr(rp["rule_excess"])] + ([_sr(zr)] if zr is not None else [])
        dsr = family_dsr(rp["rule_excess"], fam, T612_TRIALS)
        rep["dsr_rule"] = {k: dsr[k] for k in ("dsr", "psr0", "var_used", "n_trials")}
        rep["dsr_row"] = dsr_row(dsr, "DSR of the rule's weekly net excess (reported, not in the pass)")[0]
    rep["ibit_first_bar"] = (CV._bars(archive, T612_IBIT)["days"][0] if B7C._has(archive, T612_IBIT) else "not archived")
    n_sup = sum(1 for q in recs if q["superseded"])
    n_late = sum(1 for q in recs if q["av"] - q["rule"] > DAY)
    post_rows = [q for q in tab if T612_POST[0] <= q["report_date"] <= T612_POST[1]]
    by_regime = {k: _mean([q["y"] for q in post_rows if lo_ <= q["report_date"] <= hi_ and (q["dlf"] > 0) == pos_])
                 for (lo_, hi_), lab in zip(T612_SUBS, ("pre_etf", "etf_era")) for pos_, k in
                 ((True, f"{lab}_dlf_pos_mean_y"), (False, f"{lab}_dlf_neg_mean_y"))}
    rep["regimes"] = by_regime
    ins, am, zz = rep["in_sample_replication_2018_04_2022_04"], rep["asset_manager_competing"], rep["lf_level_z52_arm"]
    fo = rep["futures_and_options_report"]
    sr_ = rep["schedule_release_reading"]
    reason = (f"CME bitcoin futures-only TFF ({len(recs)} reports {recs[0]['report_date'] if recs else 'n/a'}..{recs[-1]['report_date'] if recs else 'n/a'}; "
              f"{n_sup} superseded at their stored available_at, {n_late} stamped > 1 day after the schedule release); entry at the open "
              f"of the first Coinbase bar starting at or after available_at, 7 x 24 h hold. Post-publication ({T612_POST[0][:7]}..{T612_POST[1][:7]}, "
              f"n {m['n']}): dLF/OI slope {_f(m['slope'], 4)}, NW t {_f(m['t'], 2)} with basis, basis-change and prior-week controls; "
              f"2022-05..2023-12 {_f(s[0]['slope'], 4)} (t {_f(s[0]['t'], 2)}, n {s[0]['n']}), 2024-01..2026-09 {_f(s[1]['slope'], 4)} "
              f"(t {_f(s[1]['t'], 2)}, n {s[1]['n']}). Long/flat rule: long {_pc(rp.get('share_long'), 0)} of weeks, {rp.get('switches')} switches, "
              f"weekly Sharpe {_f(rp.get('sr_rule'), 3)} vs buy-and-hold {_f(rp.get('sr_bh'), 3)} (difference {_f(rp['diff'], 3)}, block-permutation "
              f"p {CAL._mc(rp['p_greater'], rp['draws'])}); 50 bp stress difference {_f(rep['rule_50bp_stress_sr_minus_bh'], 3)}. Reported: "
              f"in-sample 2018-04..2022-04 slope {_f(ins['slope'], 4)} (t {_f(ins['t'], 2)}, n {ins['n']}); with the asset-manager change "
              f"dLF t {_f(am['t'], 2)}, dAM t {_f(am.get('t_extra'), 2)}; LF level z(52) arm slope {_f(zz['slope'], 4)} (t {_f(zz['t'], 2)}); "
              + (f"F&O report post t {_f(fo['post']['t'], 2)}; " if isinstance(fo, dict) else f"{fo}; ")
              + f"schedule-release timing post t {_f(sr_['post']['t'], 2)} (n {sr_['post']['n']}); "
              + f"{rep.get('dsr_row', 'DSR n/a')}; IBIT first bar {rep['ibit_first_bar']} — " + j["why"])
    rp_stat = {k: v_ for k, v_ in rp.items() if k != "rule_excess"}
    stat = {"n": m["n"], "main": m, "subs": s, "rule": rp_stat, "criteria": j["criteria"], "reported": rep, "n_reports": len(recs),
            "n_superseded": n_sup, "n_late_stamped": n_late, "cost_per_switch": T612_COST,
            "rule10": "release-driven weekly entries: no grid phase"}
    return _out(stat, m["n"], j["verdict"], reason)


# ============================================================================ T-608 crypto two-week losers exclusion ==

T608_PRODUCTS = "coinbase-products-2026-10-15"
T608_BTC = "coinbase-daily-BTC-USD"
T608_CMC = "cmc-historical-listings"
T608_TOP = 30
T608_WIN = 30
T608_LOOK = 14
T608_LOOK_ROB = 21
T608_MIN_ELIG = 15
T608_COST = 0.0050                   # per side, on each book's own turnover
T608_DELIST_HAIRCUT = 0.50
T608_START, T608_END = "2019-01-01", "2026-09-30"
T608_SPLIT = "2022-11-17"
T608_BLOCK = 8
T608_NBOOT = 5000
T608_NPLACEBO = 1000
T608_TRIALS = 24 + 1 + 3             # T-314's 24, T-546, the 3 arms here
T608_MIN_N = 300
T608_MAX_STALE = 7                   # days: a 14-day base close may be the latest within a week before M-15
# Kalshi crypto perps the archive's own records name (hindsight set, 2026 knowledge): ETH, SOL, BNB in
# knowledge/venues/US-LEVERAGE-VENUES-2026-10-20.md ("BTC plus ~17 alts"), DOGE, SHIB, PEPE in Hurst's reports. The
# other alts are not named anywhere in the archive, so they are left out rather than guessed.
T608_KALSHI = ("ETH", "SOL", "BNB", "DOGE", "SHIB", "PEPE")
T608_KALSHI_RT = 0.0018
# Cross-check only (reported, not the primary): a base that is a wrapped token by its Coinbase asset name ("Wrapped LUNA
# Token") but is absent from T-424's declared lists and unmatched on CMC. The primary keeps T-424's construction as
# registered; this variant drops it from the universe.
T608_XCHECK_WRAPPED = frozenset({"WLUNA"})
T608_BETA_MIN_SHARE = 0.5            # an hourly beta needs >= half of the 1,440 trailing hours with both closes
T608_FUNDING = (-0.10, 0.0, 0.10)
T608_BETA_WIN = 60
T608_EXCLUDE = (CV.T424_STABLE | CV.T424_WRAPPED) - {"BTC"}
_CMC_EXCL_SYMS = None


def _cmc_excluded_symbols() -> set:
    from mandel.experiments.batch6c_cryptoxs import EXCLUDE_IDS
    return {s.upper() for s in EXCLUDE_IDS.values()}


def build_panel(daily: dict, first: str, last: str) -> dict:
    """Arrays over the UTC day grid [first, last]: open / close / dollar volume (NaN / 0 where no bar), traded flags,
    the forward-filled close with its age, and for every (product, day) whether the product trades on any later day.
    ``daily``: {product id: {day: (open, close, volume)}}."""
    o0, o1 = _ord(first), _ord(last)
    T = o1 - o0 + 1
    pids = sorted(p for p in daily if daily[p])
    P = len(pids)
    O, C = np.full((P, T), np.nan), np.full((P, T), np.nan)
    DV = np.zeros((P, T))
    for i, p in enumerate(pids):
        for d, (o, c, v) in daily[p].items():
            k = _ord(d) - o0
            if 0 <= k < T and c and c > 0:
                C[i, k] = c
                O[i, k] = o if o and o > 0 else np.nan
                DV[i, k] = c * v if v is not None and v >= 0 else 0.0
    traded = np.isfinite(C)
    idx = np.where(traded, np.arange(T)[None, :], -1)
    last_idx = np.maximum.accumulate(idx, axis=1)
    Cf = np.where(last_idx >= 0, np.take_along_axis(np.nan_to_num(C), np.maximum(last_idx, 0), axis=1), np.nan)
    age = np.where(last_idx >= 0, np.arange(T)[None, :] - last_idx, 10 ** 6)
    later = np.zeros((P, T), bool)                        # trades on some day strictly after column k
    later[:, :-1] = np.flip(np.logical_or.accumulate(np.flip(traded[:, 1:], axis=1), axis=1), axis=1)
    cs = np.concatenate([np.zeros((P, 1)), np.cumsum(DV, axis=1)], axis=1)
    return {"pids": pids, "base": [p.split("-")[0] for p in pids], "o0": o0, "days": [_iso(o0 + k) for k in range(T)],
            "O": O, "C": C, "Cf": Cf, "age": age, "traded": traded, "later": later, "cs": cs, "T": T}


def universe_at(pan: dict, k: int, top: int = T608_TOP, window: int = T608_WIN, drop: frozenset = frozenset()) -> np.ndarray:
    """Row indexes of the top ``top`` products by dollar volume summed over columns k-window..k-1, among products
    traded on k-1 (T-424's cb_members rule; ties by product id); rows in ``drop`` are not eligible (reported variant)."""
    if k - window < 0:
        return np.array([], int)
    s = pan["cs"][:, k] - pan["cs"][:, k - window]
    elig = pan["traded"][:, k - 1] & (s > 0)
    if drop:
        elig[list(drop)] = False
    idx = np.flatnonzero(elig)
    if not idx.size:
        return idx
    order = idx[np.lexsort((np.array([pan["pids"][i] for i in idx]), -s[idx]))]
    return order[:top]


def week_signal(pan: dict, k: int, members: np.ndarray, look: int = T608_LOOK) -> np.ndarray:
    """close(k-1) / close(k-1-look) - 1 for each member (the base close may be the latest within T608_MAX_STALE days
    before k-1-look); NaN when the coin has no such close. Uses closes of bars ending by column k's 00:00 only."""
    j = k - 1 - look
    if j < 0:
        return np.full(members.size, np.nan)
    c1 = pan["C"][members, k - 1]
    c0 = pan["Cf"][members, j]
    ok = pan["age"][members, j] <= T608_MAX_STALE
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(ok, c1 / c0 - 1.0, np.nan)


def loser_mask(sig: np.ndarray, pids: Sequence[str]) -> np.ndarray:
    """The floor(n/3) lowest signals (ties by product id)."""
    n = sig.size
    k = n // 3
    order = np.lexsort((np.array(pids), sig))
    m = np.zeros(n, bool)
    m[order[:k]] = True
    return m


def week_returns(pan: dict, k: int, rows: np.ndarray, hold: int = 7) -> tuple:
    """(return, delisted flags) from the open at column k to the open at k + hold; a name without a bar there is marked
    at its last close before it, minus T608_DELIST_HAIRCUT when it never trades again."""
    e = pan["O"][rows, k]
    x = k + hold
    ox = pan["O"][rows, x]
    last_c = pan["Cf"][rows, x - 1]
    gone = ~pan["traded"][rows, x] & ~pan["later"][rows, x]
    ex = np.where(np.isfinite(ox), ox, np.where(gone, last_c * (1 - T608_DELIST_HAIRCUT), last_c))
    return ex / e - 1.0, gone & ~np.isfinite(ox)


def weekly_books(pan: dict, cols: Sequence[int], look: int = T608_LOOK, kalshi: bool = False, btc_row: Optional[int] = None,
                 drop: frozenset = frozenset()) -> dict:
    """The two books (all eligible, ex-losers) on every rebalance column in ``cols``: gross, turnover, net, the gross
    rest-minus-losers spread, and (``kalshi``) the BTC-minus-Kalshi-listed-losers arm."""
    rec = []
    prev = {"all": None, "ex": None}
    prev_k = None
    dropped = 0
    for k in cols:
        if k + 7 >= pan["T"]:
            break
        mem = universe_at(pan, k, drop=drop)
        sig = week_signal(pan, k, mem, look)
        ok = np.isfinite(sig) & np.isfinite(pan["O"][mem, k])
        rows, sig = mem[ok], sig[ok]
        if rows.size < T608_MIN_ELIG:
            dropped += 1
            prev = {"all": None, "ex": None}
            prev_k = None
            continue
        r, gone = week_returns(pan, k, rows)
        lm = loser_mask(sig, [pan["pids"][i] for i in rows])
        consecutive = prev_k is not None and k - prev_k == 7
        q = {"k": k, "day": pan["days"][k], "rows": rows, "r": r, "losers": lm, "n": rows.size, "n_delisted": int(gone.sum())}
        for book, sel in (("all", np.ones(rows.size, bool)), ("ex", ~lm)):
            w = np.zeros(rows.size)
            w[sel] = 1.0 / sel.sum()
            gross = float(np.dot(w, r))
            tw = dict(zip(rows.tolist(), w.tolist()))
            pw = prev[book] if consecutive else None
            if pw is None:
                to = 1.0
            else:
                keys = set(tw) | set(pw)
                to = float(sum(abs(tw.get(i, 0.0) - pw.get(i, 0.0)) for i in keys))
            q[f"gross_{book}"], q[f"to_{book}"] = gross, to
            drift = {i: wi * (1 + ri) / (1 + gross) for i, wi, ri in zip(rows.tolist(), w.tolist(), r.tolist()) if wi > 0}
            prev[book] = drift
        q["rl_gross"] = float(r[~lm].mean() - r[lm].mean()) if lm.any() else float("nan")
        if kalshi and btc_row is not None:
            q.update(_kalshi_leg(pan, k, rows, r, lm, btc_row))
        rec.append(q)
        prev_k = k
    for i, q in enumerate(rec):                       # liquidation before a dropped week / data gap costs a full turn
        nxt_ok = i + 1 < len(rec) and rec[i + 1]["k"] - q["k"] == 7
        last = i + 1 == len(rec)
        for book in ("all", "ex"):
            q[f"cost_{book}"] = T608_COST * (q[f"to_{book}"] + (0.0 if (nxt_ok or last) else 1.0))
            q[f"net_{book}"] = q[f"gross_{book}"] - q[f"cost_{book}"]
        q["d"] = q["net_ex"] - q["net_all"]
    return {"weeks": rec, "dropped": dropped}


def hourly_grid(series: dict) -> tuple:
    """{base: (bar starts, closes)} -> (g0, {base: closes on the common UTC hourly grid from g0, NaN where no bar})."""
    if not series:
        return 0, {}
    g0 = min(int(ts[0]) for ts, _ in series.values() if ts.size)
    g1 = max(int(ts[-1]) for ts, _ in series.values() if ts.size)
    n = (g1 - g0) // H + 1
    out = {}
    for b, (ts, cl) in series.items():
        a = np.full(n, np.nan)
        a[(np.asarray(ts, np.int64) - g0) // H] = cl
        out[b] = a
    return g0, out


def hourly_beta(grid: dict, g0: int, base: str, t_dec: int, days: int = T608_BETA_WIN,
                min_share: float = T608_BETA_MIN_SHARE) -> Optional[float]:
    """Trailing ``days``-day beta of ``base``'s hourly log returns on BTC's, over the bars ending by ``t_dec`` (bar starts
    t_dec - days x 24 h .. t_dec - 1 h; each return against the previous bar's close), hours with both closes only;
    None below ``min_share`` of the window's hours."""
    c, b = grid.get(base), grid.get("BTC")
    if c is None or b is None:
        return None
    hi = (int(t_dec) - H - g0) // H                       # the bar starting t_dec - 1 h (it ends at t_dec)
    lo = hi - days * 24 + 1
    if lo < 1 or hi >= c.size:
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        x = np.log(c[lo:hi + 1] / c[lo - 1:hi])
        y = np.log(b[lo:hi + 1] / b[lo - 1:hi])
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < min_share * days * 24 or np.var(y[m]) <= 0:
        return None
    return float(np.cov(x[m], y[m])[0, 1] / np.var(y[m], ddof=1))


def _daily_beta(pan: dict, k: int, row: int, btc_row: int) -> Optional[float]:
    """Fallback for a coin with no hourly bundle (or too few hours): trailing-60-day beta of daily close-to-close log
    returns through the bar ending at column k's 00:00, >= 40 days with both closes."""
    lo = k - T608_BETA_WIN - 1
    if lo < 0:
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        a, b = np.diff(np.log(pan["C"][row, lo:k])), np.diff(np.log(pan["C"][btc_row, lo:k]))
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 40 or np.var(b[m]) <= 0:
        return None
    return float(np.cov(a[m], b[m])[0, 1] / np.var(b[m], ddof=1))


def _kalshi_leg(pan: dict, k: int, rows: np.ndarray, r: np.ndarray, lm: np.ndarray, btc_row: int) -> dict:
    """Reported Kalshi arm: long BTC x mean trailing-60-day beta (hourly Coinbase returns, ``pan['hgrid']``; daily for a
    coin without an hourly bundle), short the EW Kalshi-listed losers, 18 bp round trip on each leg's notional; funding
    on the short at -10 / 0 / +10 %/yr."""
    sel = [j for j in np.flatnonzero(lm) if pan["base"][rows[j]] in T608_KALSHI]
    if not sel:
        return {"kalshi": None}
    if btc_row in rows.tolist():
        rb = float(r[rows.tolist().index(btc_row)])
    else:
        e, x = pan["O"][btc_row, k], pan["O"][btc_row, k + 7]
        if not (np.isfinite(e) and np.isfinite(x)):
            return {"kalshi": None}
        rb = float(x / e - 1)
    g0, grid = pan.get("hgrid", (0, {}))
    t_dec = _utc0(pan["days"][k])
    betas, src = [], []
    for j in sel:
        bs = pan["base"][rows[j]]
        bh = hourly_beta(grid, g0, bs, t_dec) if bs in grid else None
        if bh is not None:
            betas.append(bh)
            src.append("hourly")
            continue
        bd = _daily_beta(pan, k, rows[j], btc_row)
        if bd is not None:
            betas.append(bd)
            src.append("daily")
    if not betas:
        return {"kalshi": None}
    beta = float(np.mean(betas))
    base = beta * rb - float(np.mean(r[sel])) - T608_KALSHI_RT * (1 + abs(beta))
    return {"kalshi": {f: base + f / 52.0 for f in T608_FUNDING}, "kalshi_names": [pan["base"][rows[j]] for j in sel],
            "kalshi_beta": beta, "kalshi_beta_src": src}


def placebo_null(weeks: Sequence[dict], cost_diff: float, n: int = T608_NPLACEBO, seed: int = SEED) -> np.ndarray:
    """Random-tercile placebo: in every week floor(n/3) eligible names drawn at random as 'losers'; statistic = mean over
    weeks of gross EW(ex-random) - gross EW(all), minus the primary's own mean cost difference (T-314's convention)."""
    rng = np.random.default_rng(seed)
    tot = np.zeros(n)
    for q in weeks:
        r = q["r"]
        m = r.size
        k = m // 3
        pick = np.argsort(rng.random((n, m)), axis=1)[:, :k]
        s_l = r[pick].sum(axis=1)
        tot += (r.sum() - s_l) / (m - k) - r.mean()
    return tot / max(1, len(weeks)) - cost_diff


def placebo_null_own_cost(weeks: Sequence[dict], n_rows: int, n: int = T608_NPLACEBO, seed: int = SEED) -> np.ndarray:
    """Reported reading of the placebo: the same random within-week terciles, but each random ex-book charged its OWN
    drift-adjusted turnover at T608_COST per side exactly as ``weekly_books`` charges the primary (full entry after a
    gap, a full liquidation before one), minus the EW(all) book's own net. Random exclusions turn over more than the
    loser tercile, so this null sits below ``placebo_null`` (which is the stricter criterion)."""
    rng = np.random.default_rng(seed)
    tot = np.zeros(n)
    prev = None
    ar = np.arange(n)[:, None]
    for i, q in enumerate(weeks):
        rows, r = q["rows"], q["r"]
        m = r.size
        k = m // 3
        pick = np.argsort(rng.random((n, m)), axis=1)[:, :k]
        keep = np.ones((n, m), bool)
        keep[ar, pick] = False
        w = keep / float(m - k)
        gross = (w * r[None, :]).sum(axis=1)
        consecutive = i > 0 and q["k"] - weeks[i - 1]["k"] == 7
        if consecutive and prev is not None:
            Wt = np.zeros((n, n_rows))
            Wt[:, rows] = w
            to = np.abs(Wt - prev).sum(axis=1)
        else:
            to = np.ones(n)
        nxt_ok = i + 1 < len(weeks) and weeks[i + 1]["k"] - q["k"] == 7
        last = i + 1 == len(weeks)
        net_ex = gross - T608_COST * (to + (0.0 if (nxt_ok or last) else 1.0))
        tot += net_ex - q["net_all"]
        prev = np.zeros((n, n_rows))
        prev[:, rows] = w * (1.0 + r[None, :]) / (1.0 + gross[:, None])
    return tot / max(1, len(weeks))


def _load_daily_ohlv(archive, pid: str) -> dict:
    out = {}
    for r in CV._stream(archive, f"coinbase-daily-{pid}"):
        v = r.get("value") or {}
        c, o, vol = CV._num(v.get("close")), CV._num(v.get("open")), CV._num(v.get("volume"))
        if c is not None and v.get("t") is not None:
            out[CV._dday(v["t"])] = (o, c, vol if vol is not None else 0.0)
    return out


def _t608_panel(archive) -> tuple:
    def load():
        prods = CV._names(archive, CV.CB_PRODUCTS_PREFIX)
        snap = T608_PRODUCTS if T608_PRODUCTS in prods else prods[-1]
        stable_ids, status = set(), {}
        for r in CV._stream(archive, snap):
            v = r.get("value") or {}
            if v.get("id"):
                status[v["id"]] = v.get("status")
                if v.get("fx_stablecoin"):
                    stable_ids.add(v["id"])
        names = [nm for nm in CV._names(archive, "coinbase-daily-") if nm.endswith("-USD")]
        daily, excluded = {}, []
        for nm in names:
            pid = nm[len("coinbase-daily-"):]
            if pid.split("-")[0] in T608_EXCLUDE or pid in stable_ids:
                excluded.append(pid)
                continue
            daily[pid] = _load_daily_ohlv(archive, pid)
        last = max((max(m) for m in daily.values() if m), default="2019-01-01")
        pan = build_panel(daily, "2018-09-01", last)
        return pan, {"snapshot": snap, "n_bundles": len(names), "excluded": sorted(excluded), "fx_stablecoin_ids": sorted(stable_ids),
                     "status": status}
    return CAL._cached(archive, ("b13cda_t608_panel",), load)


def _peg_flags(pan: dict, k: int, rows: np.ndarray, refs: Sequence[int] = ()) -> int:
    """Cross-check: members whose every close over the 14 days before column k lies within 2% of 1 USD, or of a
    reference coin's close on the same days (BTC / ETH / SOL rows ``refs``: a wrapped or staked copy the declared lists
    missed); at least 10 closes. Uses closes of bars ending by column k's 00:00 only."""
    c = pan["C"][rows, max(0, k - 14):k]
    with np.errstate(invalid="ignore", divide="ignore"):
        fin = np.isfinite(c)
        peg = np.all(np.abs(c - 1.0) <= 0.02, axis=1, where=fin) & (fin.sum(axis=1) >= 10)
        for ref in refs:
            rc = pan["C"][ref, max(0, k - 14):k][None, :]
            ok = fin & np.isfinite(rc)
            near = np.all(np.abs(c / rc - 1.0) <= 0.02, axis=1, where=ok) & (ok.sum(axis=1) >= 10) & (rows != ref)
            peg |= near
    return int(peg.sum())


def _cmc_cross_check(archive, bases: set) -> dict:
    """CMC flags as a cross-check (reported, nothing is excluded by it): every base that was ever a member, matched by
    symbol to the CMC id with the largest market cap among cmc-historical-listings rows (rows available at capture),
    flagged when T-314's declared CMC classification (``batch6c_cryptoxs.declared_excluded``: stablecoin, gold token,
    wrapped / bridged / staked copy, by id or slug) marks that id."""
    from mandel.experiments.batch6c_cryptoxs import declared_excluded
    if not B7C._has(archive, T608_CMC):
        return {"archived": False}
    best = {}
    for r in CV._stream(archive, T608_CMC):
        v = r.get("value") or {}
        s = str(v.get("symbol") or "").upper()
        if s not in bases or v.get("id") is None:
            continue
        mc = CV._num(v.get("marketCap")) or 0.0
        if s not in best or mc > best[s][2]:
            best[s] = (int(v["id"]), v.get("slug"), mc)
    flagged = sorted(s for s, (cid, slug, _) in best.items() if declared_excluded(cid, slug))
    return {"archived": True, "n_bases": len(bases), "matched": len(best), "unmatched": sorted(bases - set(best)),
            "flagged": flagged, "flagged_slugs": {s: best[s][1] for s in flagged}}


def two_week_losers(pan: dict, info: dict, weekday: int = 0, full: bool = True) -> dict:
    """T-608 on the rebalance weekday ``weekday`` (0 = Monday, the claim). ``full`` adds the criteria, placebo, DSR and
    the reported arms; otherwise only the primary mean (rule 10's per-start range)."""
    o0 = pan["o0"]
    cols = [k for k in range(pan["T"]) if date.fromordinal(o0 + k).weekday() == weekday
            and T608_START <= pan["days"][k] <= T608_END]
    btc_row = pan["pids"].index("BTC-USD") if "BTC-USD" in pan["pids"] else None
    res = weekly_books(pan, cols, kalshi=full, btc_row=btc_row)
    W = res["weeks"]
    d = np.array([q["d"] for q in W])
    out = {"n": len(W), "dropped": res["dropped"], "mean": _mean(d)}
    if not full:
        return out
    days = [q["day"] for q in W]
    pg, pl, dr = CAL.studentized_p_escalated(d, T608_BLOCK, T608_NBOOT, SEED, 1)
    ci = CAL.mean_ci(d, T608_BLOCK, T608_NBOOT)
    first = np.array([dd < T608_SPLIT for dd in days])
    halves = [_mean(d[first]), _mean(d[~first])]
    cost_diff = float(np.mean([q["cost_ex"] - q["cost_all"] for q in W])) if W else 0.0
    pl_null = placebo_null(W, cost_diff) if W else np.array([])
    q95 = float(np.quantile(pl_null, 0.95)) if pl_null.size else None
    own = placebo_null_own_cost(W, len(pan["pids"])) if W else np.array([])
    q95_own = float(np.quantile(own, 0.95)) if own.size else None
    rl = np.array([q["rl_gross"] for q in W])
    kal = [q for q in W if q.get("kalshi")]
    kser = np.array([q["kalshi"][0.0] for q in kal]) if kal else np.array([])
    rob = weekly_books(pan, cols, look=T608_LOOK_ROB)
    d21 = np.array([q["d"] for q in rob["weeks"]])
    xw_rows = frozenset(i for i, b in enumerate(pan["base"]) if b in T608_XCHECK_WRAPPED)
    xw = weekly_books(pan, cols, drop=xw_rows) if xw_rows else None
    if xw is not None:
        dx = np.array([q["d"] for q in xw["weeks"]])
        fx = np.array([q["day"] < T608_SPLIT for q in xw["weeks"]])
        pgx, _, drx = CAL.studentized_p_escalated(dx, T608_BLOCK, T608_NBOOT, SEED, 1)
        xw_out = {"bases": sorted(T608_XCHECK_WRAPPED), "n": int(dx.size), "dropped": xw["dropped"], "mean": _mean(dx),
                  "p": pgx, "draws": drx, "halves": [_mean(dx[fx]), _mean(dx[~fx])]}
    else:
        xw_out = {"bases": sorted(T608_XCHECK_WRAPPED), "n": 0, "note": "not in the panel"}
    fam = [_sr(d), _sr(rl[np.isfinite(rl)]), _sr(kser) if kser.size > 2 else None]
    dsr = family_dsr(d, fam, T608_TRIALS) if d.size > 3 else {"dsr": None}
    m = _mean(d)
    rows_ = [(f"primary mean weekly net EW(ex-losers) - EW(all) {_bp(m)} with a one-sided 95% lower bound > 0 (8-week blocks, "
              f"p {CAL._mc(pg, dr)}; 95% CI {_bp(ci[0])} to {_bp(ci[1])})", B7C._sig_crit(m, pg, dr), CAL.decide_p(pl, dr) is True),
             (f"both halves positive (split {T608_SPLIT}: {_bp(halves[0])} / {_bp(halves[1])})",
              None if any(h is None for h in halves) else all(h > 0 for h in halves), False),
             (f"above the random-tercile placebo's 95th percentile ({_bp(q95)}, {T608_NPLACEBO} within-week draws, the primary's "
              f"own mean cost difference {_bp(cost_diff)} charged)", None if q95 is None or m is None else bool(m > q95), False),
             dsr_row(dsr, f"DSR > 0.95 at {T608_TRIALS} trials (T-314's 24, T-546, the 3 arms here)")
             if dsr.get("dsr") is not None else ("DSR > 0.95 (n/a)", None, False)]
    v, why, crit = CAL._judge(rows_, len(W), T608_MIN_N, "weeks")
    by_reg = {}
    if btc_row is not None:
        Cf = pan["Cf"][btc_row]
        reg = []
        for q in W:
            k = q["k"]
            sma = np.nanmean(pan["C"][btc_row, max(0, k - 200):k])
            reg.append(bool(Cf[k - 1] > sma))
        reg = np.array(reg)
        by_reg = {"btc_above_200d_sma": {"n": int(reg.sum()), "mean": _mean(d[reg])},
                  "btc_below_200d_sma": {"n": int((~reg).sum()), "mean": _mean(d[~reg])}}
    by_year = defaultdict(list)
    for q in W:
        by_year[q["day"][:4]].append(q["d"])
    excl_syms = _cmc_excluded_symbols()
    cmc_hits = sorted({pan["base"][i] for q in W for i in q["rows"] if pan["base"][i].upper() in excl_syms})
    refs = [pan["pids"].index(p) for p in ("BTC-USD", "ETH-USD", "SOL-USD") if p in pan["pids"]]
    peg_hits = sum(_peg_flags(pan, q["k"], q["rows"], refs) for q in W)
    src = [s for q in kal for s in q.get("kalshi_beta_src", [])]
    out.update(verdict=v, why=why, criteria=crit, p=pg, draws=dr, ci=ci, halves=halves, placebo_q95=q95,
               placebo_mean=float(pl_null.mean()) if pl_null.size else None, cost_diff=cost_diff, dsr=dsr,
               placebo_own_cost_q95=q95_own, placebo_own_cost_mean=float(own.mean()) if own.size else None,
               ever_member_bases=sorted({pan["base"][i] for q in W for i in q["rows"]}),
               gross_rest_minus_losers=_mean(rl), mean_gross_ex=_mean([q["gross_ex"] for q in W]),
               mean_gross_all=_mean([q["gross_all"] for q in W]), mean_to_ex=_mean([q["to_ex"] for q in W]),
               mean_to_all=_mean([q["to_all"] for q in W]), mean_n=_mean([q["n"] for q in W]),
               n_delisted=int(sum(q["n_delisted"] for q in W)), first_week=days[0] if days else None,
               last_week=days[-1] if days else None,
               robust_21d={"n": len(rob["weeks"]), "mean": _mean(d21), "dropped": rob["dropped"]},
               cross_check_wrapped_excluded=xw_out,
               kalshi_arm={"n_active_weeks": len(kal), "mean_by_funding": {str(f): _mean([q["kalshi"][f] for q in kal]) for f in T608_FUNDING},
                           "mean_beta": _mean([q["kalshi_beta"] for q in kal]), "set": list(T608_KALSHI),
                           "beta_source_counts": {s: src.count(s) for s in ("hourly", "daily")},
                           "per_year_funding0": {yv: _mean([q["kalshi"][0.0] for q in kal if q["day"][:4] == yv])
                                                 for yv in sorted({q["day"][:4] for q in kal})}},
               by_year={y: float(np.mean(v_)) for y, v_ in sorted(by_year.items())}, btc_trend=by_reg,
               cmc_cross_check={"excluded_symbol_members": cmc_hits, "peg_screen_member_weeks": peg_hits})
    return out


def b13_cryptoderiv_a_two_week_losers(archive):
    """T-608: EW point-in-time top-30 Coinbase coins ex 14-day losers minus EW top-30, weekly, net of 50 bp per side."""
    prods = CV._names(archive, CV.CB_PRODUCTS_PREFIX)
    daily_names = [nm for nm in CV._names(archive, "coinbase-daily-") if nm.endswith("-USD")]
    need = [T608_BTC] + ([] if T608_PRODUCTS in prods else [T608_PRODUCTS]) + ([] if daily_names else ["coinbase-daily-<SYM>-USD"])
    miss = _missing(archive, need)
    if miss:
        return miss
    pan, info = _t608_panel(archive)
    hb = {b: _hourly_oc(archive, CV.cbh(f"{b}-USD")) for b in ("BTC",) + T608_KALSHI if B7C._has(archive, CV.cbh(f"{b}-USD"))}
    pan["hgrid"] = hourly_grid({b: (ts, cl) for b, (ts, _, cl) in hb.items()}) if "BTC" in hb else (0, {})
    j = two_week_losers(pan, info, 0, True)
    cmc = _cmc_cross_check(archive, set(j["ever_member_bases"]))
    phases = {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][wd]: two_week_losers(pan, info, wd, False)["mean"] for wd in range(1, 7)}
    phases["Mon"] = j["mean"]
    pv = [v_ for v_ in phases.values() if v_ is not None]
    ka = j["kalshi_arm"]
    cmc_note = (f"cmc-historical-listings: {cmc['matched']} of {cmc['n_bases']} ever-member bases matched by symbol, "
                f"flagged by T-314's declared CMC classification {cmc['flagged']}" if cmc.get("archived")
                else "cmc-historical-listings not archived")
    j["cmc_cross_check"]["cmc_bundle"] = cmc
    reason = (f"{info['n_bundles']} coinbase-daily USD bundles ({len(info['excluded'])} excluded: T-424's stablecoin and wrapped/staked "
              f"bases (BTC kept) and {len(info['fx_stablecoin_ids'])} fx_stablecoin ids of {info['snapshot']}); point-in-time top {T608_TOP} "
              f"by trailing {T608_WIN}-day dollar volume each Monday 00:00 UTC, {j['first_week']}..{j['last_week']}: {j['n']} weeks kept, "
              f"{j['dropped']} dropped (< {T608_MIN_ELIG} eligible), mean {_f(j['mean_n'], 1)} eligible, {j['n_delisted']} delisted exits at "
              f"last price -50%. Mean weekly net EW(ex-losers) - EW(all) {_bp(j['mean'])} (p {CAL._mc(j['p'], j['draws'])}, 95% CI "
              f"{_bp(j['ci'][0])} to {_bp(j['ci'][1])}); gross ex {_pc(j['mean_gross_ex'], 3)} vs all {_pc(j['mean_gross_all'], 3)}; "
              f"turnover ex {_f(j['mean_to_ex'], 3)} vs all {_f(j['mean_to_all'], 3)} a week (cost difference {_bp(j['cost_diff'])}); halves "
              f"{_bp(j['halves'][0])} / {_bp(j['halves'][1])}; placebo 95th pct {_bp(j['placebo_q95'])} (mean {_bp(j['placebo_mean'])}; "
              f"the primary's cost difference charged, the stricter reading; with each random book's own turnover the 95th pct is "
              f"{_bp(j['placebo_own_cost_q95'])}); DSR {_f(j['dsr'].get('dsr'), 3)}. Reported: gross EW(rest) - EW(losers) "
              f"{_bp(j['gross_rest_minus_losers'])}; 21-day lookback "
              f"{_bp(j['robust_21d']['mean'])} ({j['robust_21d']['n']} weeks); Kalshi-listed subset {list(T608_KALSHI)} (hindsight universe) "
              f"BTC x beta minus losers {ka['n_active_weeks']} active weeks (betas: {ka['beta_source_counts']['hourly']} hourly, "
              f"{ka['beta_source_counts']['daily']} daily), mean {_bp(ka['mean_by_funding']['0.0'])} at funding 0 "
              f"({_bp(ka['mean_by_funding']['-0.1'])} / {_bp(ka['mean_by_funding']['0.1'])} at -/+10%/yr); BTC trend "
              + ", ".join(f"{k} {_bp(v_['mean'])} ({v_['n']})" for k, v_ in j["btc_trend"].items())
              + "; by year " + ", ".join(f"{y} {_bp(v_)}" for y, v_ in j["by_year"].items())
              + f"; rule 10 per-start range over the 7 weekday phases {_bp(min(pv)) if pv else 'n/a'} to {_bp(max(pv)) if pv else 'n/a'}"
              f"; CMC cross-check: members matching CMC-declared stable/wrapped symbols {j['cmc_cross_check']['excluded_symbol_members']}, "
              f"peg-screen member-weeks (2% of 1 USD, BTC, ETH or SOL over 14 days) {j['cmc_cross_check']['peg_screen_member_weeks']}; "
              f"{cmc_note}; with {j['cross_check_wrapped_excluded']['bases']} (wrapped by name, missing from T-424's lists) "
              f"dropped from the universe the primary reads {_bp(j['cross_check_wrapped_excluded'].get('mean'))} (p "
              f"{_f(j['cross_check_wrapped_excluded'].get('p'), 4)}, halves {_bp((j['cross_check_wrapped_excluded'].get('halves') or [None, None])[0])} / "
              f"{_bp((j['cross_check_wrapped_excluded'].get('halves') or [None, None])[1])}; reported, the primary keeps T-424's construction). "
              f"Survivorship: the panel is "
              f"today's Coinbase product list (online and delisted USD products), so products dropped from the API entirely are "
              f"absent; the -50% delisting mark is the registered haircut — " + j["why"])
    stat = {k: j[k] for k in ("n", "dropped", "mean", "p", "draws", "ci", "halves", "placebo_q95", "placebo_mean", "cost_diff",
                              "placebo_own_cost_q95", "placebo_own_cost_mean",
                              "gross_rest_minus_losers", "mean_gross_ex", "mean_gross_all", "mean_to_ex", "mean_to_all", "mean_n",
                              "n_delisted", "first_week", "last_week", "robust_21d", "kalshi_arm", "by_year", "btc_trend",
                              "cross_check_wrapped_excluded",
                              "cmc_cross_check", "criteria")}
    stat.update(dsr={k: j["dsr"].get(k) for k in ("dsr", "psr0", "var_used", "n_trials")}, phases=phases,
                excluded_products=info["excluded"], snapshot=info["snapshot"],
                rule10="claim names Monday 00:00 UTC; the other six weekday phases are reported (per-start range), not judged")
    return _out(stat, j["n"], j["verdict"], reason)


HARNESSES = {"b13_cryptoderiv_a_two_week_losers": b13_cryptoderiv_a_two_week_losers,
             "b13_cryptoderiv_a_btc_weekend_monday": b13_cryptoderiv_a_btc_weekend_monday,
             "b13_cryptoderiv_a_cme_lev_funds": b13_cryptoderiv_a_cme_lev_funds,
             "b13_cryptoderiv_a_expiry_reversal": b13_cryptoderiv_a_expiry_reversal}
THEORY_MAP = {"T-608": "b13_cryptoderiv_a_two_week_losers", "T-613": "b13_cryptoderiv_a_btc_weekend_monday",
              "T-612": "b13_cryptoderiv_a_cme_lev_funds", "T-614": "b13_cryptoderiv_a_expiry_reversal"}
