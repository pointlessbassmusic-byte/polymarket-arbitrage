"""
Batch 7, group ``cal``: five salvage successors pre-registered on 2026-10-20 (mandel/theories/SALVAGE-2026-10-20.md):
calendar effects on an independent international ETF panel, two replication families of executable daily rules, and a
realised-return check of the gold carry inversion.
=====================================================================================================================

Each claim is tested exactly as worded (its claim, trial.pass and trial.min_n; MANDEL.md section 2, harness rules 1-12).
The parents' in-sample numbers that motivated the successors are not evidence and are not reused as the test sample:
every successor here names a universe or symbols its parent did not use (the 21 country ETFs; QQQ/IWM; QQQ/IWM/DIA;
realised futures returns instead of an implied rate).

  * T-547  (parent T-344, T-59's window and cost convention: ``underlying.turn_of_month`` / ``underlying2.tom_replication``)
           Pooled over the 21 iShares country ETFs (``batch6c_xs.COUNTRY21``), 2000-01..2026-09: mean daily return in the
           turn-of-month window (the last 4 and first 3 sessions of each month, on the NYSE sessions the ETFs trade)
           minus the mean on other days, net of 2 bps per monthly round trip (T-344's convention: the round trip spread
           over the 7 window days, 2/7 bp per window day), >= 3 bps with one-sided p < 0.05 (H0: net difference <= 3 bps),
           both halves positive (net), and at least 60% of the 21 ETFs (13) with a positive net difference. min_n 200
           months (one window per month).
  * T-548  (parent T-441, T-352's season-year construction ``underlying2.sell_in_may``) Same panel, month-end adjclose
           returns 2000-01..2026-09: pooled mean monthly return Nov-Apr minus May-Oct > 0 with one-sided p < 0.05, both
           halves positive, at least 60% of the ETFs positive. min_n 200 months.
  * T-549  (parent T-348, harness ``batch4_ohlc.ohlc_overnight_vs_intraday``) QQQ (1999-03 on) and IWM (2000-05 on) to
           2026-09: T-348's construction unchanged (``overnight_intraday``: r_night = open_t / close_{t-1} - 1 + D_t /
           close_{t-1}, r_day = close_t / open_t - 1, D recovered from close / adjclose by ``ex_dividends``). Pass, for both
           ETFs after Holm over the two: gap > 0 with p < 0.05, both halves positive, and the overnight-only holding's mean
           net of 1 bp per side (2 bps a day) > 0 with p < 0.05. min_n 2500 trading days. Yahoo-open quality check against
           the first hourly bar (hourly-QQQ / hourly-IWM, report only).
  * T-558  (parent T-332, harness ``batch4_ohlc.ohlc_ibs_reversal``) QQQ, IWM, DIA, inception..2026-09: T-332's
           construction unchanged (``ibs``: (close - low) / (high - low) of day t on the raw bar, next-day close-to-close
           adjclose return). Statistic: mean next-day return after IBS < 0.2 minus the unconditional mean. Pass: at least
           two of three ETFs with Holm-adjusted p < 0.05 against the claim's 2 bps (H0: difference <= 2 bps), and every ETF
           positive in both halves; the claim sentence also puts "> 2 bps" on each of the three ETFs (rule 1: an asset the
           claim names is a criterion; the pass's two-of-three significance count does not override it). min_n 1000
           trading days per ETF. Rule 12: daily-history rows are available the next session, so each criterion is
           scored under the entry-close live proxy (gate and fill at close t) and the previous-close reading (gate of
           day t, entry close t+1, exit close t+2), Holm per reading, combined by ``batch6c_xs._rule12``.
  * T-555  (parent T-370, harness ``batch6c_misc.b6c_misc_metals_basis``) 2005-01..2026-09: daily return of a fully
           collateralised long GC=F position (Yahoo continuous front, F_t / F_{t-1} - 1) plus the DTB3 accrual on the
           collateral, minus GLD's total return (adjclose), on the sessions outside T-370's roll mask (``roll_flags``:
           +-2 sessions around the last session before each active month's first notice day, ``first_notice_day``,
           GC_MONTHS Feb/Apr/Jun/Aug/Oct/Dec). Pass: annualised mean difference (x 252) >= 0.5%/yr, HAC (Newey-West lag 21)
           two-sided 95% lower bound > 0, both halves positive. min_n 3000 unmasked sessions.

Conventions
  * Data. Bundles are read through ``archive.load`` (via the parents' loaders: ``batch6c_misc._daily`` for adjclose /
    close, ``batch4_ohlc._bars`` for OHLC bars); a row is used only if its ``available_at`` is not after the bundle's
    capture. Calendar claims take no data-dependent decision (rule 4 / 12 do not bind beyond the calendar).
  * Rule 10. T-547 uses the month calendar the claim names (the -4..+3 window of every month) and T-548 the month-end
    calendar it names; T-549 and T-558 use every trading day; T-555 every unmasked session: there is no grid phase.
  * Panels (T-547, T-548). The equal-weight panel return on a session (month) is the mean over the ETFs with a return
    then (each ETF's return between consecutive sessions of the union calendar of the 21 ETFs; a return spanning a
    missing bar is dropped). The flagged-series device ``batch6c_cal.flag_diff_series`` turns the difference of means
    into a mean. Intervals: studentized cluster bootstrap (bootstrap-t on the cluster-linearised ratio-mean s.e.):
    T-547 clusters by turn-of-month window (the month m with its last 4 sessions and the first 3 of m+1; the trial's
    "date-clustered (month)"), T-548 by season year May-April (the trial's "block bootstrap by year", T-352's season
    year), clusters drawn i.i.d.; a 12-cluster circular block is reported as a sensitivity. Halves: the season-year
    boundary nearest the window's midpoint (2013-05), each half's net difference by point estimate.
  * Holm (T-549, T-558) over the ETFs of each family, on studentized circular block-bootstrap p's (block 10 for T-549 as
    its trial states; block 20 for T-558, T-332's mean block). Monte-Carlo precision (``batch6c_cal.escalate_p``): each
    p is the mean over 5 seeds of 2000 resamples, escalated one seed at a time while its MC band straddles 0.05, and a
    Holm-adjusted p decides only when its band clears 0.05 (else the criterion is undecided, None).
  * T-555. DTB3 accrual is the ``batch6b_bw.Bills`` convention (rule 7: discount yield -> continuous, the print dated
    strictly before each calendar day, accrued calendar day by calendar day from the previous session's close). The
    masked sessions' own drift (same difference on the masked sessions), the all-session reading, unmasked jumps in the
    difference beyond 5 robust s.d. (Yahoo rolls off the schedule are the leading artefact), the micro-gold (MGC=F)
    reading when archived, and T-370's implied-financing reading (``implied_financing`` on the same days: mean(i -
    DTB3), whose negative implies futures + bills beat spot by about -mean plus GLD's 0.40% fee) are reported side by
    side so a measurement artefact is visible. Report only; the claim's statistic decides.
  * Rule 5: below min_n the verdict is never supported and a failing criterion counts only when it fails decisively
    (``batch6_surf._decide``). Rule 9: a missing bundle or too short a window is inconclusive and names what is missing.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from statistics import NormalDist
from typing import Optional, Sequence

import numpy as np

from mandel.experiments import batch4_ohlc as OHLC
from mandel.experiments import batch6c_cal as CAL
from mandel.experiments import batch6c_misc as MISC
from mandel.experiments.batch5_hourly import ny_bars
from mandel.experiments.batch6_surf import _decide, _out
from mandel.experiments.batch6c_xs import COUNTRY21, _rule12
from mandel.experiments.underlying2 import _verdict, monthly

N_BOOT = 2000
N_SEEDS = 5
SEED = 0
ALPHA = 0.05
Z95 = NormalDist().inv_cdf(0.975)

DTB3_B = "fred-DTB3"
SPLIT_MONTH = "2013-05"            # season-year boundary nearest the 2000-01..2026-09 midpoint

# T-547
T547_START, T547_END = "2000-01-01", "2026-09-30"
T547_BEFORE, T547_AFTER = 4, 3
T547_COST_RT = 2e-4
T547_BAR = 3e-4
T547_MIN_N = 200
T547_SHARE = 0.6
# T-548
T548_START, T548_END = "2000-01", "2026-09"
T548_MIN_N = 200
T548_SHARE = 0.6
# T-549
T549_STARTS = {"QQQ": "1999-03-01", "IWM": "2000-05-01"}
T549_END = "2026-09-30"
T549_COST_SIDE = 1e-4
T549_BLOCK = 10
T549_MIN_N = 2500
# T-558
T558_SYMS = ("QQQ", "IWM", "DIA")
T558_END = "2026-09-30"
T558_THR = 0.2
T558_BAR = 2e-4
T558_BLOCK = 20
T558_MIN_N = 1000
# T-555
T555_START, T555_END = "2005-01-01", "2026-09-30"
T555_BAR = 0.005
T555_LAG = 21
T555_WINDOW = 2
T555_MIN_N = 3000
T555_JUMP_K = 5.0
GLD_FEE = 0.004


def dh(sym: str) -> str:
    return "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


def hourly(sym: str) -> str:
    return "hourly-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


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


def _bp(x, nd: int = 2) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x * 1e4:+.{nd}f} bps"


def _pc(x, nd: int = 2) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x * 100:+.{nd}f}%"


def _mc(p, draws) -> str:
    return CAL._mc(p, draws)


# ================================================================================================ statistics ==

def cluster_boot(x, groups, n_boot: int = N_BOOT, seed: int = SEED, block: int = 1) -> tuple:
    """Studentized cluster bootstrap of the (ratio) mean of ``x`` with clusters ``groups`` (drawn i.i.d. when block = 1,
    else in circular blocks of ``block`` consecutive clusters): (p_greater, p_less, [2.5%, 97.5%] percentile CI of the
    mean). p_greater tests H0 mean <= 0, p_less H0 mean >= 0; (None, None, [None, None]) below 8 clusters."""
    x = np.asarray(x, float)
    _, inv = np.unique(np.asarray(groups), return_inverse=True)
    S = np.bincount(inv, weights=x)
    N = np.bincount(inv).astype(float)
    G = S.size
    if G < 8:
        return None, None, [None, None]
    m = S.sum() / N.sum()

    def se(Sm, Nm, mm):
        e = Sm - mm[:, None] * Nm
        return np.sqrt(G / (G - 1) * (e ** 2).sum(axis=1)) / Nm.sum(axis=1)

    s0 = float(se(S[None], N[None], np.array([m]))[0])
    rng = np.random.default_rng(seed)
    idx = CAL._boot_idx(rng, G, block, n_boot)
    Sb, Nb = S[idx], N[idx]
    mb = Sb.sum(axis=1) / Nb.sum(axis=1)
    sb = se(Sb, Nb, mb)
    ok = sb > 0
    if s0 <= 0 or not ok.any():
        return None, None, [float(np.quantile(mb, 0.025)), float(np.quantile(mb, 0.975))]
    t0 = m / s0
    tb = (mb[ok] - m) / sb[ok]
    k = tb.size
    return (float((np.sum(tb >= t0) + 1) / (k + 1)), float((np.sum(tb <= t0) + 1) / (k + 1)),
            [float(np.quantile(mb, 0.025)), float(np.quantile(mb, 0.975))])


def cluster_p(x, groups, n_boot: int = N_BOOT, seed: int = SEED, n_seeds: int = N_SEEDS, block: int = 1,
              max_seeds: Optional[int] = None) -> tuple:
    """(p_greater, p_less, draws) of ``cluster_boot`` pooled over seeds and escalated while undecided
    (``batch6c_cal.escalate_p``)."""
    def batch(k):
        pg, pl, _ = cluster_boot(x, groups, n_boot, seed + k, block)
        return pg, pl
    return CAL.escalate_p(batch, n_boot, n_seeds, CAL.MAX_SEEDS if max_seeds is None else max_seeds)


def holm(ps: Sequence[Optional[float]]) -> list:
    """Holm step-down adjusted p-values (None entries are treated as p = 1 and stay None)."""
    q = [1.0 if p is None or not math.isfinite(p) else float(p) for p in ps]
    m = len(q)
    order = sorted(range(m), key=lambda i: q[i])
    adj = [1.0] * m
    run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (m - r) * q[i]))
        adj[i] = run
    return [None if ps[i] is None else adj[i] for i in range(m)]


def _count_crit(decisions: Sequence[Optional[bool]], need: int) -> Optional[bool]:
    t = sum(1 for d in decisions if d is True)
    u = sum(1 for d in decisions if d is None)
    if t >= need:
        return True
    if t + u < need:
        return False
    return None


# ===================================================================================== panels (T-547, T-548) ==

def union_returns(series: dict) -> tuple:
    """(union calendar U, {sym: returns on U}) from {sym: (days, adjclose)}; the return on U[i] is close U[i] / close
    U[i-1] - 1 when the ETF has both bars, NaN otherwise (a return spanning a missing bar is dropped)."""
    U = sorted(set().union(*(set(d) for d, _ in series.values()))) if series else []
    at = {d: i for i, d in enumerate(U)}
    R = {}
    for s, (days, c) in series.items():
        px = np.full(len(U), np.nan)
        px[[at[d] for d in days]] = np.asarray(c, float)
        r = np.full(len(U), np.nan)
        if len(U) > 1:
            with np.errstate(invalid="ignore", divide="ignore"):
                r[1:] = px[1:] / px[:-1] - 1.0
        R[s] = r
    return U, R


def tom_flags(days: Sequence[str], before: int = T547_BEFORE, after: int = T547_AFTER) -> tuple:
    """(flags, anchors): T-59's window on the session calendar ``days`` (a session's return ends on it): the first
    ``after`` and last ``before`` sessions of each month; anchor = the month whose turn the session belongs to (the
    first ``after`` sessions of month m+1 belong to month m's window)."""
    pos = defaultdict(list)
    for i, d in enumerate(days):
        pos[d[:7]].append(i)
    fl = np.zeros(len(days), bool)
    anc = np.array([d[:7] for d in days], dtype=object)
    months = sorted(pos)
    for j, m in enumerate(months):
        idx = pos[m]
        fl[idx[:after]] = True
        fl[idx[-before:]] = True
        if j > 0:
            for k in idx[:after]:
                anc[k] = months[j - 1]
    return fl, anc


def _halves_mask(anchor_months, split: str = SPLIT_MONTH):
    a = np.asarray(anchor_months, dtype=object)
    return np.array([x < split for x in a], bool)


def tom_panel(series: dict, start: str = T547_START, end: str = T547_END, before: int = T547_BEFORE, after: int = T547_AFTER,
              cost_rt: float = T547_COST_RT, bar: float = T547_BAR, min_n: int = T547_MIN_N, share: float = T547_SHARE,
              n_expected: int = len(COUNTRY21), split: str = SPLIT_MONTH, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """T-547 core. ``series``: {sym: (days, adjclose)}. Returns the stat dict with verdict, why and reason."""
    U, R = union_returns(series)
    fl, anc = tom_flags(U, before, after)
    Ua = np.array(U, dtype=object)
    w = np.array([start <= d <= end for d in U], bool)
    M = np.vstack([R[s] for s in series]) if series else np.zeros((0, len(U)))
    cnt = np.sum(np.isfinite(M), axis=0)
    with np.errstate(invalid="ignore"):
        panel = np.where(cnt > 0, np.nansum(M, axis=0) / np.maximum(cnt, 1), np.nan)
    keep = w & np.isfinite(panel)
    x, f, g = panel[keep], fl[keep], anc[keep]
    days = Ua[keep]
    n_months = len({str(d)[:7] for d in days})       # calendar months with sessions in the window (one window each)
    adj = cost_rt / (before + after)
    rep = {"n_months": n_months, "n_sessions": int(keep.sum()), "first": days[0] if days.size else None,
           "last": days[-1] if days.size else None, "n_etfs": len(series), "cost_per_window_day_bps": adj * 1e4}
    if f.sum() < 8 or (~f).sum() < 8 or n_months < 8:
        v, why = _decide([("enough sessions for the window comparison", None, False)], n_months, min_n, "months")
        rep.update(verdict=v, why=why, reason=f"{n_months} months, {int(keep.sum())} panel sessions: too few — {why}")
        return rep
    d = CAL.flag_diff_series(x, f)
    gross = float(d.mean())
    net = gross - adj
    pg, pl, draws = cluster_p(d - (bar + adj), g, n_boot, seed)
    _, _, ci = cluster_boot(d, g, n_boot, seed)
    ci_net = [None if c is None else c - adj for c in ci]
    pg12, _, _ = cluster_boot(d - (bar + adj), g, n_boot, seed, block=12)
    pg0, _, d0 = cluster_p(d - adj, g, n_boot, seed, max_seeds=N_SEEDS)
    early = _halves_mask(g, split)
    halves, hci = [], []
    for h in (early, ~early):
        if (h & f).sum() >= 2 and (h & ~f).sum() >= 2:
            dh_ = CAL.flag_diff_series(x[h], f[h])
            halves.append(float(dh_.mean()) - adj)
            hci.append([None if c is None else c - adj for c in cluster_boot(dh_, g[h], n_boot, seed)[2]])
        else:
            halves.append(float("nan")); hci.append([None, None])
    per = {}
    for s in series:
        r = R[s][w]
        ok = np.isfinite(r)
        ff = fl[w][ok]
        rr = r[ok]
        if ff.sum() >= 2 and (~ff).sum() >= 2:
            dg = float(rr[ff].mean() - rr[~ff].mean())
            per[s] = {"gross_bps": dg * 1e4, "net_bps": (dg - adj) * 1e4, "n_sessions": int(ok.sum())}
        else:
            per[s] = {"gross_bps": None, "net_bps": None, "n_sessions": int(ok.sum())}
    n_pos = sum(1 for v_ in per.values() if v_["net_bps"] is not None and v_["net_bps"] > 0)
    n_pos_gross = sum(1 for v_ in per.values() if v_["gross_bps"] is not None and v_["gross_bps"] > 0)
    need = math.ceil(share * n_expected - 1e-9)
    p_ok = CAL.decide_p(pg, draws)
    p_dec = CAL.decide_p(pl, draws) is True
    crit = [(f"pooled net difference >= {bar * 1e4:.0f} bps ({_bp(net)})", net >= bar,
             ci_net[1] is not None and ci_net[1] < bar),
            (f"one-sided p < 0.05 vs net difference <= {bar * 1e4:.0f} bps (p {_mc(pg, draws)})", p_ok, p_dec),
            (f"both halves positive net (<{split} {_bp(halves[0])}, >={split} {_bp(halves[1])})",
             all(math.isfinite(h) and h > 0 for h in halves),
             any(c[1] is not None and c[1] <= 0 for c in hci)),
            (f"at least {need} of {n_expected} ETFs ({share:.0%}) with a positive net difference ({n_pos} of {len(per)})",
             n_pos >= need, False)]
    v, why = _decide(crit, n_months, min_n, "months")
    rep.update(gross_diff_bps=gross * 1e4, net_diff_bps=net * 1e4, ci95_net_bps=[None if c is None else c * 1e4 for c in ci_net],
               p_vs_bar=pg, p_vs_bar_draws=draws, p_vs_bar_block12=pg12, p_net_gt0=pg0, p_net_gt0_draws=d0,
               mean_tom_bps=float(x[f].mean() * 1e4), mean_other_bps=float(x[~f].mean() * 1e4), n_tom_sessions=int(f.sum()),
               halves_net_bps=[h * 1e4 for h in halves], halves_ci95_net_bps=[[None if c is None else c * 1e4 for c in h] for h in hci],
               split=split, per_etf=per, n_positive_net=n_pos, n_positive_gross=n_pos_gross, need_positive=need,
               criteria=[[c[0], c[1]] for c in crit], verdict=v, why=why)
    rep["reason"] = (f"Equal-weight panel of {len(series)} country ETFs, {rep['first']}..{rep['last']} ({int(keep.sum())} sessions, "
                     f"{n_months} months): window (-{before}..+{after}) {x[f].mean() * 1e4:+.2f} vs other days "
                     f"{x[~f].mean() * 1e4:+.2f} bps/day, gross difference {gross * 1e4:+.2f}, net of {cost_rt * 1e4:.0f} bps per "
                     f"monthly round trip ({adj * 1e4:.2f} bp per window day) {net * 1e4:+.2f} bps (window-clustered 95% CI "
                     f"{ci_net[0] * 1e4:+.2f}..{ci_net[1] * 1e4:+.2f}; needs >= {bar * 1e4:.0f}); studentized p vs <= "
                     f"{bar * 1e4:.0f} bps {_mc(pg, draws)} (12-window block sensitivity {CAL._mc(pg12, n_boot)}; p vs <= 0 "
                     f"{_mc(pg0, d0)}); halves net <{split} {_bp(halves[0])} / >={split} {_bp(halves[1])}; ETFs with a positive net "
                     f"difference {n_pos} of {len(per)} (gross {n_pos_gross}; need {need}): "
                     + ", ".join(f"{s} {v_['net_bps']:+.1f}" for s, v_ in per.items() if v_["net_bps"] is not None))
    return rep


def month_returns(days: Sequence[str], c) -> dict:
    """{month: month-end to month-end return} over consecutive calendar months (``underlying2.monthly``)."""
    ms, mc = monthly(list(days), np.asarray(c, float))
    out = {}
    for i in range(1, len(ms)):
        y, m = int(ms[i - 1][:4]), int(ms[i - 1][5:7])
        nxt = f"{y + (m == 12):04d}-{m % 12 + 1:02d}"
        if ms[i] == nxt:
            out[ms[i]] = float(mc[i] / mc[i - 1] - 1.0)
    return out


def season_year(month: str) -> int:
    y, m = int(month[:4]), int(month[5:7])
    return y if m >= 5 else y - 1


def halloween_panel(series: dict, start: str = T548_START, end: str = T548_END, min_n: int = T548_MIN_N,
                    share: float = T548_SHARE, n_expected: int = len(COUNTRY21), split: str = SPLIT_MONTH,
                    n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """T-548 core. ``series``: {sym: (days, adjclose)}."""
    per_m = {s: month_returns(d, c) for s, (d, c) in series.items()}
    months = sorted({m for v_ in per_m.values() for m in v_ if start <= m <= end})
    panel = np.array([np.mean([v_[m] for v_ in per_m.values() if m in v_]) for m in months], float)
    win = np.array([int(m[5:7]) in (11, 12, 1, 2, 3, 4) for m in months], bool)
    g = np.array([season_year(m) for m in months])
    n = len(months)
    rep = {"n_months": n, "first": months[0] if n else None, "last": months[-1] if n else None, "n_etfs": len(series)}
    if win.sum() < 8 or (~win).sum() < 8:
        v, why = _decide([("enough months for the comparison", None, False)], n, min_n, "months")
        rep.update(verdict=v, why=why, reason=f"{n} panel months: too few — {why}")
        return rep
    d = CAL.flag_diff_series(panel, win)
    diff = float(d.mean())
    pg, pl, draws = cluster_p(d, g, n_boot, seed)
    _, _, ci = cluster_boot(d, g, n_boot, seed)
    pg_b, _, _ = cluster_boot(d, g, n_boot, seed, block=3)
    early = np.array([m < split for m in months], bool)
    halves, hci = [], []
    for h in (early, ~early):
        if (h & win).sum() >= 2 and (h & ~win).sum() >= 2:
            dh_ = CAL.flag_diff_series(panel[h], win[h])
            halves.append(float(dh_.mean()))
            hci.append(cluster_boot(dh_, g[h], n_boot, seed)[2])
        else:
            halves.append(float("nan")); hci.append([None, None])
    per = {}
    for s, v_ in per_m.items():
        ks = [m for m in v_ if start <= m <= end]
        a = [v_[m] for m in ks if int(m[5:7]) in (11, 12, 1, 2, 3, 4)]
        b = [v_[m] for m in ks if int(m[5:7]) not in (11, 12, 1, 2, 3, 4)]
        per[s] = {"diff_bps": float(np.mean(a) - np.mean(b)) * 1e4 if a and b else None, "n_months": len(ks)}
    n_pos = sum(1 for x in per.values() if x["diff_bps"] is not None and x["diff_bps"] > 0)
    need = math.ceil(share * n_expected - 1e-9)
    crit = [(f"pooled difference > 0 ({_bp(diff, 1)}/month)", diff > 0, ci[1] is not None and ci[1] <= 0),
            (f"one-sided p < 0.05 (p {_mc(pg, draws)})", CAL.decide_p(pg, draws), CAL.decide_p(pl, draws) is True),
            (f"both halves positive (<{split} {_bp(halves[0], 1)}, >={split} {_bp(halves[1], 1)})",
             all(math.isfinite(h) and h > 0 for h in halves), any(c[1] is not None and c[1] <= 0 for c in hci)),
            (f"at least {need} of {n_expected} ETFs ({share:.0%}) positive ({n_pos} of {len(per)})", n_pos >= need, False)]
    v, why = _decide(crit, n, min_n, "months")
    rep.update(diff_bps_month=diff * 1e4, ci95_bps=[None if c is None else c * 1e4 for c in ci], p=pg, p_draws=draws,
               p_block3_seasons=pg_b, mean_nov_apr_bps=float(panel[win].mean() * 1e4), mean_may_oct_bps=float(panel[~win].mean() * 1e4),
               halves_bps=[h * 1e4 for h in halves], halves_ci95_bps=[[None if c is None else c * 1e4 for c in h] for h in hci],
               split=split, n_season_years=len(set(g.tolist())), per_etf=per, n_positive=n_pos, need_positive=need,
               criteria=[[c[0], c[1]] for c in crit], verdict=v, why=why)
    rep["reason"] = (f"Equal-weight panel of {len(series)} country ETFs, month-end adjclose returns {rep['first']}..{rep['last']} "
                     f"({n} months, {rep['n_season_years']} season years): Nov-Apr {panel[win].mean() * 1e4:+.1f} vs May-Oct "
                     f"{panel[~win].mean() * 1e4:+.1f} bps/month, difference {diff * 1e4:+.1f} (season-year-clustered 95% CI "
                     f"{ci[0] * 1e4:+.1f}..{ci[1] * 1e4:+.1f}), studentized one-sided p {_mc(pg, draws)} (3-season block "
                     f"sensitivity {CAL._mc(pg_b, n_boot)}); halves <{split} {_bp(halves[0], 1)} / >={split} {_bp(halves[1], 1)}; "
                     f"ETFs positive {n_pos} of {len(per)} (need {need}): "
                     + ", ".join(f"{s} {x['diff_bps']:+.0f}" for s, x in per.items() if x["diff_bps"] is not None))
    return rep


# ================================================================================ T-549 overnight vs intraday ==

def night_day(b, start: str, end: str) -> dict:
    """T-348's construction on bars ``b`` (batch4_ohlc.Bars): night, day, ds within [start, end], and the dividends."""
    D = OHLC.ex_dividends(b.close, b.adj)
    O, C = np.asarray(b.open, float), np.asarray(b.close, float)
    ds = np.array(b.days[1:])
    night = O[1:] / C[:-1] - 1 + D[1:] / C[:-1]
    dayr = C[1:] / O[1:] - 1
    m = (ds >= start) & (ds <= end)
    return {"ds": ds[m], "night": night[m], "day": dayr[m], "divs": D, "n_div": int(np.sum(D[1:][m] > 0))}


def open_quality(b, hourly_values) -> Optional[dict]:
    """Yahoo daily open vs the open of the first (09:30 ET) hourly bar on the days both exist, and the gap recomputed with
    the hourly open on those days. Report only."""
    if not hourly_values:
        return None
    nb = ny_bars(hourly_values)
    at = {d: i for i, d in enumerate(b.days)}
    D = OHLC.ex_dividends(b.close, b.adj)
    diffs, g_y, g_h, days = [], [], [], []
    for d, bars in nb.items():
        i = at.get(d)
        first = bars.get("09:30")
        if i is None or i == 0 or first is None:
            continue
        ho = float(first.get("open") or float("nan"))
        if not (ho > 0):
            continue
        yo, c0, c1 = float(b.open[i]), float(b.close[i - 1]), float(b.close[i])
        diffs.append(yo / ho - 1.0)
        g_y.append((yo / c0 - 1 + D[i] / c0) - (c1 / yo - 1))
        g_h.append((ho / c0 - 1 + D[i] / c0) - (c1 / ho - 1))
        days.append(d)
    if not diffs:
        return {"n_days": 0}
    x = np.abs(np.array(diffs))
    return {"n_days": len(diffs), "first": min(days), "last": max(days), "median_abs_diff_bps": float(np.median(x) * 1e4),
            "share_abs_diff_gt_5bps": float(np.mean(x > 5e-4)), "share_abs_diff_gt_20bps": float(np.mean(x > 2e-3)),
            "gap_yahoo_open_bps": float(np.mean(g_y) * 1e4), "gap_hourly_open_bps": float(np.mean(g_h) * 1e4)}


def overnight_family(bars: dict, starts: dict, end: str = T549_END, cost_side: float = T549_COST_SIDE,
                     block: int = T549_BLOCK, min_n: int = T549_MIN_N, n_boot: int = N_BOOT, seed: int = SEED,
                     hourly_values: Optional[dict] = None) -> dict:
    """T-549 core. ``bars``: {sym: Bars}; ``starts``: {sym: first day}."""
    syms = list(bars)
    per, pg_gap, pg_net, draws_g, draws_n = {}, [], [], [], []
    for s in syms:
        b = bars[s]
        x = night_day(b, starts[s], end)
        n = int(x["ds"].size)
        rec = {"n": n, "first": x["ds"][0] if n else None, "last": x["ds"][-1] if n else None, "n_ex_dividend_nights": x["n_div"]}
        if n < 8:
            per[s] = rec; pg_gap.append(None); pg_net.append(None); draws_g.append(0); draws_n.append(0)
            continue
        split = str(x["ds"][n // 2])
        par = OHLC.overnight_intraday(b.days, b.open, b.close, x["divs"], adj=b.adj, start=starts[s], end=end, split=split,
                                      min_gap=0.0, block=block, n_boot=n_boot, min_n=min_n, cost_rt=2 * cost_side, seed=seed)
        gap = x["night"] - x["day"]
        net = x["night"] - 2 * cost_side
        pg, pl, dg = CAL.studentized_p_escalated(gap, block, n_boot, seed, N_SEEDS)
        qg, ql, dn = CAL.studentized_p_escalated(net, block, n_boot, seed, N_SEEDS)
        rec.update(mean_night_bps=float(x["night"].mean() * 1e4), mean_day_bps=float(x["day"].mean() * 1e4),
                   gap_bps=float(gap.mean() * 1e4), gap_ci95_bps=par.get("gap_ci_bps"), p_gap=pg, p_gap_less=pl, p_gap_draws=dg,
                   halves_gap_bps=par.get("halves_gap_bps"), halves_n=par.get("halves_n"), split=split,
                   net_overnight_bps=float(net.mean() * 1e4), net_overnight_ci95_bps=[c * 1e4 for c in CAL.mean_ci(net, block, n_boot, seed)],
                   p_net=qg, p_net_less=ql, p_net_draws=dn,
                   net_overnight_2bp_side_bps=float((x["night"] - 4 * cost_side).mean() * 1e4),
                   sharpe_overnight_net=par.get("sharpe_overnight_net_1bp"), sharpe_intraday=par.get("sharpe_intraday"),
                   sharpe_buy_hold=par.get("sharpe_buy_hold"), open_equals_close_share=par.get("open_equals_close_share"))
        if hourly_values and hourly_values.get(s):
            rec["open_quality"] = open_quality(b, hourly_values[s])
        per[s] = rec
        pg_gap.append(pg); pg_net.append(qg); draws_g.append(dg); draws_n.append(dn)
    hg, hn = holm(pg_gap), holm(pg_net)
    crit = []
    for i, s in enumerate(syms):
        r = per[s]
        per[s]["holm_p_gap"], per[s]["holm_p_net"] = hg[i], hn[i]
        if "gap_bps" not in r:
            crit += [(f"{s}: enough days", None, False)]
            continue
        hv = r["halves_gap_bps"] or [float("nan"), float("nan")]
        gap_ok = _sig_crit(r["gap_bps"], hg[i], draws_g[i])
        net_ok = _sig_crit(r["net_overnight_bps"], hn[i], draws_n[i])
        crit += [(f"{s}: gap > 0 with Holm p < 0.05 ({r['gap_bps']:+.2f} bps, Holm p {_mc(hg[i], draws_g[i])})", gap_ok,
                  CAL.decide_p(r["p_gap_less"], draws_g[i]) is True),
                 (f"{s}: gap positive in both halves ({_s2(hv[0])} / {_s2(hv[1])} bps)",
                  all(h is not None and math.isfinite(h) and h > 0 for h in hv), False),
                 (f"{s}: net overnight-only mean > 0 with Holm p < 0.05 ({r['net_overnight_bps']:+.2f} bps/day net of "
                  f"{cost_side * 1e4:.0f} bp per side, Holm p {_mc(hn[i], draws_n[i])})", net_ok,
                  CAL.decide_p(r["p_net_less"], draws_n[i]) is True)]
    n = min((per[s]["n"] for s in syms), default=0)
    v, why = _decide(crit, n, min_n, "trading days (the smaller ETF)")
    parts = []
    for s in syms:
        r = per[s]
        if "gap_bps" not in r:
            parts.append(f"{s}: {r['n']} days, too few"); continue
        oq = r.get("open_quality")
        oq_txt = ("" if not oq or not oq.get("n_days") else
                  f"; Yahoo open vs first hourly bar on {oq['n_days']} days {oq['first']}..{oq['last']}: median |diff| "
                  f"{oq['median_abs_diff_bps']:.1f} bps, > 5 bps on {oq['share_abs_diff_gt_5bps'] * 100:.0f}%, gap there "
                  f"{oq['gap_yahoo_open_bps']:+.2f} (Yahoo open) vs {oq['gap_hourly_open_bps']:+.2f} bps (hourly open)")
        parts.append(f"{s} {r['first']}..{r['last']} ({r['n']} days, {r['n_ex_dividend_nights']} ex-dividend nights): overnight "
                     f"{r['mean_night_bps']:+.2f} vs intraday {r['mean_day_bps']:+.2f} bps/day, gap {r['gap_bps']:+.2f} (95% CI "
                     f"{r['gap_ci95_bps'][0]:+.2f}..{r['gap_ci95_bps'][1]:+.2f}; p {_mc(r['p_gap'], r['p_gap_draws'])}, Holm "
                     f"{_mc(r['holm_p_gap'], r['p_gap_draws'])}), halves split {r['split']} {_s2(r['halves_gap_bps'][0])} / "
                     f"{_s2(r['halves_gap_bps'][1])}; overnight-only net of 1 bp per side {r['net_overnight_bps']:+.2f} bps/day "
                     f"(p {_mc(r['p_net'], r['p_net_draws'])}, Holm {_mc(r['holm_p_net'], r['p_net_draws'])}; 2 bp per side "
                     f"{r['net_overnight_2bp_side_bps']:+.2f}); Sharpe overnight net {r['sharpe_overnight_net']:.2f} vs buy-hold "
                     f"{r['sharpe_buy_hold']:.2f}; open==close on {r['open_equals_close_share'] * 100:.1f}% of days" + oq_txt)
    return {"n": n, "per_etf": per, "criteria": [[c[0], c[1]] for c in crit], "verdict": v, "why": why,
            "reason": "; ".join(parts)}


def _sig_crit(point, p_adj, draws) -> Optional[bool]:
    """'point > 0 with (adjusted) p < 0.05': False when the point is not positive, else the MC-banded p decision."""
    if point is None or not point > 0:
        return False
    return None if p_adj is None else CAL.decide_p(p_adj, draws)


def _s2(x) -> str:
    return "n/a" if x is None or not math.isfinite(x) else f"{x:+.2f}"


# ===================================================================================== T-558 IBS replication ==

T558_READINGS = (("entry_close", "entry-close live proxy (IBS of day t, fill at close t, exit close t+1)"),
                 ("prev_close", "previous-close reading (IBS of day t known next session, entry close t+1, exit close t+2)"))


def _ibs_reading(rw, f, days, bar: float, block: int, n_boot: int, seed: int) -> dict:
    """One information-set reading: paired series s = (1 - share) x flag_diff (mean exactly mean(r | flag) - mean(r)),
    studentized circular block-bootstrap p vs ``bar``, block CI and median-date halves."""
    n = int(rw.size)
    rec = {"n": n, "first": days[0] if n else None, "last": days[-1] if n else None, "n_signal": int(f.sum())}
    if f.sum() < 8 or (~f).sum() < 8:
        return rec
    sh = float(f.mean())
    s = (1.0 - sh) * CAL.flag_diff_series(rw, f)
    diff = float(rw[f].mean() - rw.mean())
    pg, pl, dr = CAL.studentized_p_escalated(s - bar, block, n_boot, seed, N_SEEDS)
    split = str(days[n // 2])
    early = days < split
    halves = [float(rw[g & f].mean() - rw[g].mean()) if (g & f).any() else float("nan") for g in (early, ~early)]
    since2000 = days >= "2000-01-01"
    d2000 = float(rw[since2000 & f].mean() - rw[since2000].mean()) if (since2000 & f).any() else None
    rec.update(diff_bps=diff * 1e4, p=pg, p_less=pl, p_draws=dr, ci95_bps=[c * 1e4 for c in CAL.mean_ci(s, block, n_boot, seed)],
               halves_bps=[h * 1e4 for h in halves], split=split, mean_after_signal_bps=float(rw[f].mean() * 1e4),
               mean_unconditional_bps=float(rw.mean() * 1e4), diff_since_2000_bps=None if d2000 is None else d2000 * 1e4)
    return rec


def ibs_one(b, end: str = T558_END, thr: float = T558_THR, bar: float = T558_BAR, block: int = T558_BLOCK,
            n_boot: int = N_BOOT, seed: int = SEED, min_n: int = T558_MIN_N, parent: bool = True) -> dict:
    """One ETF: T-332's construction from inception to ``end`` under both information-set readings (rule 12). The
    top-level keys are the entry-close live-proxy reading (IBS_t gate, r = A[t+1]/A[t] - 1); ``prev_close`` holds the
    previous-close reading (IBS_t gate known next session, r = A[t+2]/A[t+1] - 1, exit dates <= ``end``)."""
    H, L, C, A = (np.asarray(x, float) for x in (b.high, b.low, b.close, b.adj))
    x = OHLC.ibs(H, L, C)
    days_all = np.array(b.days)
    sd, nd = days_all[:-1], days_all[1:]
    r = A[1:] / A[:-1] - 1
    idx = np.where((nd <= end) & np.isfinite(x[:-1]))[0]
    rec = _ibs_reading(r[idx], x[idx] < thr, sd[idx], bar, block, n_boot, seed)
    r2 = A[2:] / A[1:-1] - 1
    idx2 = np.where((days_all[2:] <= end) & np.isfinite(x[:-2]))[0]
    rec["prev_close"] = _ibs_reading(r2[idx2], x[:-2][idx2] < thr, days_all[:-2][idx2], bar, block, n_boot, seed)
    if "diff_bps" in rec and parent:
        par = OHLC.ibs_reversal(b.days, H, L, C, A, opens=b.open, start=b.days[0], end=end, thr=thr, split=rec["split"],
                                min_gap=bar, n_boot=n_boot, seed=seed, min_n=min_n, grid_sharpes=None)
        rec.update(parent_stationary_ci95_bps=par.get("ci_bps"), parent_block_shift_p=par.get("p_block_shift"),
                   rule_sharpe_net=par.get("rule_sharpe_net"), execution=par.get("execution"))
    return rec


def _ibs_criteria(per: dict, syms: Sequence[str], thr: float, bar: float, need: int, tag: str) -> list:
    """The three T-558 criteria (name, ok, decisive) for one reading; ``per``: {sym: reading record}; Holm within it."""
    hp = holm([per[s].get("p") for s in syms])
    dec = []
    for i, s in enumerate(syms):
        per[s]["holm_p"] = hp[i]
        dec.append(None if hp[i] is None else CAL.decide_p(hp[i], per[s]["p_draws"]))
    have = [s for s in syms if "diff_bps" in per[s]]
    ok_count = _count_crit([d if "diff_bps" in per[s] else None for d, s in zip(dec, syms)], need)
    n_dec_fail = sum(1 for s in have if CAL.decide_p(per[s]["p_less"], per[s]["p_draws"]) is True)
    return [(f"{tag} (" + ", ".join(f"{s} {_mc(per[s]['holm_p'], per[s]['p_draws'])}" for s in have) + ")", ok_count,
             len(syms) - n_dec_fail < need),
            (f"{tag} (" + ", ".join(f"{s} {per[s]['diff_bps']:+.2f}" for s in have) + ")",
             None if len(have) < len(syms) else all(per[s]["diff_bps"] > bar * 1e4 for s in syms),
             any(per[s]["ci95_bps"][1] is not None and per[s]["ci95_bps"][1] <= bar * 1e4 for s in have)),
            (f"{tag} (" + ", ".join(f"{s} {_s2(per[s]['halves_bps'][0])}/{_s2(per[s]['halves_bps'][1])}" for s in have) + ")",
             None if len(have) < len(syms) else all(all(math.isfinite(h) and h > 0 for h in per[s]["halves_bps"]) for s in syms),
             False)]


def ibs_family(bars: dict, end: str = T558_END, thr: float = T558_THR, bar: float = T558_BAR, block: int = T558_BLOCK,
               min_n: int = T558_MIN_N, n_boot: int = N_BOOT, seed: int = SEED, need: int = 2, parent: bool = True) -> dict:
    """T-558 core. ``bars``: {sym: Bars}. Rule 12: every criterion is scored under the entry-close live-proxy reading and
    the previous-close reading (Holm applied separately per reading) and combined with batch6c_xs._rule12: it passes only
    when both pass, fails only when both fail, undecided otherwise."""
    syms = list(bars)
    per = {s: ibs_one(bars[s], end, thr, bar, block, n_boot, seed, min_n, parent) for s in syms}
    views = {"entry_close": {s: per[s] for s in syms}, "prev_close": {s: per[s]["prev_close"] for s in syms}}
    crit = [(f"{s}: enough IBS < {thr} days and other days ({lab})", None, False)
            for key, lab in T558_READINGS for s in syms if "diff_bps" not in views[key][s]]
    by = {key: _ibs_criteria(views[key], syms, thr, bar, need, lab.split(" (")[0]) for key, lab in T558_READINGS}
    labels = (f"at least {need} of {len(syms)} ETFs with Holm-adjusted p < 0.05 vs difference <= {bar * 1e4:.0f} bps",
              f"every ETF difference > {bar * 1e4:.0f} bps (the claim's bound on QQQ, IWM and DIA)",
              "every ETF positive in both halves")
    for j, lab in enumerate(labels):
        crit.append(_rule12([by[key][j] for key, _ in T558_READINGS], lab))
    n = min((min(per[s]["n"], per[s]["prev_close"]["n"]) for s in syms), default=0)
    v, why = _decide(crit, n, min_n, "trading days (the smallest ETF)")
    parts = []
    for s in syms:
        r, q = per[s], per[s]["prev_close"]
        if "diff_bps" not in r:
            parts.append(f"{s}: {r['n']} days, {r['n_signal']} signals, too few"); continue
        ex = r.get("execution") or {}
        parts.append(f"{s} {r['first']}..{r['last']} ({r['n']} days, {r['n_signal']} IBS<{thr} signals): entry-close reading "
                     f"next-day {r['mean_after_signal_bps']:+.2f} vs unconditional {r['mean_unconditional_bps']:+.2f} bps, difference "
                     f"{r['diff_bps']:+.2f} (block-{block} 95% CI {r['ci95_bps'][0]:+.2f}..{r['ci95_bps'][1]:+.2f}"
                     + (f"; T-332 stationary CI {r['parent_stationary_ci95_bps'][0]:+.2f}..{r['parent_stationary_ci95_bps'][1]:+.2f}"
                        if r.get("parent_stationary_ci95_bps") else "")
                     + f"), p vs <= {bar * 1e4:.0f} bps {_mc(r['p'], r['p_draws'])}, Holm {_mc(r['holm_p'], r['p_draws'])}; halves "
                     f"split {r['split']} {_s2(r['halves_bps'][0])} / {_s2(r['halves_bps'][1])}; since 2000 {_s2(r['diff_since_2000_bps'])}"
                     + (f"; previous-close reading (entry close t+1) difference {q['diff_bps']:+.2f} (CI {q['ci95_bps'][0]:+.2f}.."
                        f"{q['ci95_bps'][1]:+.2f}), p {_mc(q['p'], q['p_draws'])}, Holm {_mc(q['holm_p'], q['p_draws'])}, halves "
                        f"{_s2(q['halves_bps'][0])} / {_s2(q['halves_bps'][1])}" if "diff_bps" in q else
                        f"; previous-close reading: {q['n_signal']} signals, too few")
                     + (f"; execution next-open-to-close {_s2(ex.get('next_open_to_close_diff_bps'))}" if ex else ""))
    return {"n": n, "per_etf": per, "criteria": [[c[0], c[1]] for c in crit], "verdict": v, "why": why, "reason": "; ".join(parts)}


# ======================================================================== T-555 gold futures + bills vs GLD ==

def gold_carry(days: Sequence[str], F, gld_adj, bills, start: str = T555_START, end: str = T555_END,
               months: Sequence[int] = MISC.GC_MONTHS, window: int = T555_WINDOW, lag: int = T555_LAG,
               bar: float = T555_BAR, min_n: int = T555_MIN_N, ppy: int = 252, jump_k: float = T555_JUMP_K,
               bad_print: Optional[float] = None) -> dict:
    """T-555 core on aligned sessions: daily (F_t / F_{t-1} - 1) + bill growth (prev session -> session) - 1 - (GLD
    adjclose return), on sessions in [start, end] outside the roll mask. ``bills``: object with growth(d0, d1)."""
    F, A = np.asarray(F, float), np.asarray(gld_adj, float)
    days = list(days)
    n_all = len(days)
    rep = {"n": 0}
    if n_all < 3:
        v, why = _decide([("aligned GC=F / GLD sessions", None, False)], 0, min_n, "unmasked sessions")
        rep.update(verdict=v, why=why, reason=f"{n_all} aligned sessions — {why}")
        return rep
    rfut = F[1:] / F[:-1] - 1.0
    acc = np.array([bills.growth(days[i - 1], days[i]) - 1.0 for i in range(1, n_all)])
    rg = A[1:] / A[:-1] - 1.0
    diff = rfut + acc - rg
    ds = np.array(days[1:])
    fl = MISC.roll_flags(days, months, window)[1:]
    inw = (ds >= start) & (ds <= end)
    bad = np.zeros(diff.size, bool)
    if bad_print is not None:                        # report-only readings: drop impossible daily prints, counted
        bad = (np.abs(rfut) > bad_print) | (np.abs(rg) > bad_print)
        inw = inw & ~bad
    prof = roll_profile(days, diff, months, start, end)
    keep = inw & ~fl
    msk = inw & fl
    x = diff[keep]; kd = ds[keep]
    n = int(x.size)
    rep.update(n=n, n_masked=int(msk.sum()), first=kd[0] if n else None, last=kd[-1] if n else None)
    if n < 8:
        v, why = _decide([("unmasked sessions for the HAC mean", None, False)], n, min_n, "unmasked sessions")
        rep.update(verdict=v, why=why, reason=f"{n} unmasked sessions — {why}")
        return rep
    h = MISC.hac_mean(x, lag)
    ann = h["mean"] * ppy
    lo = (h["mean"] - Z95 * h["se"]) * ppy if h["se"] is not None else None
    hi = (h["mean"] + Z95 * h["se"]) * ppy if h["se"] is not None else None
    split = str(kd[n // 2])
    halves, hci = [], []
    for g in (kd < split, kd >= split):
        hh = MISC.hac_mean(x[g], lag)
        halves.append(hh["mean"] * ppy if hh["mean"] is not None else float("nan"))
        hci.append(None if hh["se"] is None else (hh["mean"] + Z95 * hh["se"]) * ppy)
    years = (date.fromisoformat(str(ds[inw][-1])) - date.fromisoformat(str(ds[inw][0]))).days / 365.25 if inw.any() else float("nan")
    masked = diff[msk]
    med = float(np.median(x)); rsd = 1.4826 * float(np.median(np.abs(x - med)))
    jumps = np.abs(x - med) > jump_k * max(rsd, 1e-4)
    xj = x[~jumps]
    alls = diff[inw]
    rep.update(ann_diff=ann, hac_ci95=[lo, hi], daily_mean=h["mean"], daily_se=h["se"], halves_ann=halves, split=split,
               fut_leg_ann=float(rfut[keep].mean() * ppy), bills_ann=float(acc[keep].mean() * ppy), gld_ann=float(rg[keep].mean() * ppy),
               masked_mean_ann=float(masked.mean() * ppy) if masked.size else None,
               masked_contribution_per_year=float(masked.sum() / years) if masked.size and years > 0 else None,
               all_sessions_ann=float(alls.mean() * ppy), all_sessions_per_year=float(alls.sum() / years) if years > 0 else None,
               unmasked_jumps=int(jumps.sum()), unmasked_jump_sum=float(x[jumps].sum()),
               ann_diff_ex_jumps=float(xj.mean() * ppy) if xj.size else None, years=years, roll_profile=prof,
               n_bad_prints=int(bad.sum()))
    crit = [(f"annualised difference >= {bar * 100:.1f}%/yr ({_pc(ann)})", ann >= bar, hi is not None and hi < bar),
            (f"HAC (lag {lag}) 95% lower bound > 0 ({_pc(lo)})", None if lo is None else lo > 0, hi is not None and hi <= 0),
            (f"both halves positive (<{split} {_pc(halves[0])}, >={split} {_pc(halves[1])})",
             all(math.isfinite(v_) and v_ > 0 for v_ in halves), any(c is not None and c <= 0 for c in hci))]
    v, why = _decide(crit, n, min_n, "unmasked sessions")
    rep.update(criteria=[[c[0], c[1]] for c in crit], verdict=v, why=why)
    return rep


def roll_profile(days: Sequence[str], diff, months: Sequence[int] = MISC.GC_MONTHS, start: str = T555_START,
                 end: str = T555_END, span: int = 5) -> dict:
    """Mean daily difference by session offset k = -span..+span from each scheduled roll session j (the last session
    before first notice; ``diff[i - 1]`` is the return ending at session i), pooled over the rolls in [start, end]:
    where the continuous series actually rolls shows as the offsets carrying the contango jump. Report only."""
    import bisect
    days = list(days)
    diff = np.asarray(diff, float)
    by = {k: [] for k in range(-span, span + 1)}
    if len(days) < 2 * span + 3:
        return {"n_rolls": 0, "mean_by_offset": {}}
    for y in range(int(days[0][:4]), int(days[-1][:4]) + 1):
        for m in months:
            f = MISC.first_notice_day(y, m).isoformat()
            j = bisect.bisect_left(days, f) - 1
            if j - span < 1 or j + span >= len(days) or not (start <= days[j] <= end):
                continue
            for k in by:
                by[k].append(diff[j + k - 1])
    nr = len(by[0])
    mean = {str(k): (float(np.mean(v)) if v else None) for k, v in by.items()}
    se = {str(k): (float(np.std(v, ddof=1) / math.sqrt(len(v))) if len(v) > 1 else None) for k, v in by.items()}
    inside = [mean[str(k)] for k in range(-T555_WINDOW, T555_WINDOW + 1) if mean[str(k)] is not None]
    outside = [mean[str(k)] for k in by if abs(k) > T555_WINDOW and mean[str(k)] is not None]
    return {"n_rolls": nr, "mean_by_offset": mean, "se_by_offset": se,
            "per_roll_inside_mask": float(np.sum(inside)) if inside else None,
            "max_outside_mask": float(max(outside)) if outside else None,
            "argmax_offset": max(mean, key=lambda k: -1e9 if mean[k] is None else mean[k]) if nr else None}


def b7_cal_tom_country_etfs(archive):
    """T-547."""
    names = [dh(s) for s in COUNTRY21]
    miss = _missing(archive, names)
    if miss:
        return miss
    series = {}
    for s in COUNTRY21:
        x = MISC._daily(archive, dh(s))
        series[s] = (x["days"], x["adj"])
    rep = tom_panel(series)
    why, reason = rep.pop("why"), rep.pop("reason")
    stat = {**rep, "rule10": "calendar named by the claim (the -4..+3 window of every month)"}
    return _out(stat, rep["n_months"], rep["verdict"], reason + " — " + why)


def b7_cal_halloween_country_etfs(archive):
    """T-548."""
    names = [dh(s) for s in COUNTRY21]
    miss = _missing(archive, names)
    if miss:
        return miss
    series = {}
    for s in COUNTRY21:
        x = MISC._daily(archive, dh(s))
        series[s] = (x["days"], x["adj"])
    rep = halloween_panel(series)
    why, reason = rep.pop("why"), rep.pop("reason")
    stat = {**rep, "rule10": "month-end calendar named by the claim"}
    return _out(stat, rep["n_months"], rep["verdict"], reason + " — " + why)


def b7_cal_overnight_qqq_iwm(archive):
    """T-549."""
    miss = _missing(archive, [dh("QQQ"), dh("IWM")])
    if miss:
        return miss
    bars = {s: OHLC._bars(archive, s) for s in ("QQQ", "IWM")}
    hv, absent = {}, []
    for s in bars:                                  # optional: the report-only open-quality check
        if _has(archive, hourly(s)):
            hv[s] = [r["value"] for r in archive.load(hourly(s))]
        else:
            absent.append(hourly(s))
    rep = overnight_family(bars, T549_STARTS, hourly_values=hv)
    reason = rep.pop("reason") + (f"; open-quality check not run for {absent} (not archived; report only)" if absent else "")
    why = rep.pop("why")
    stat = {**rep, "rule10": "every trading day (no grid phase)"}
    return _out(stat, rep["n"], rep["verdict"], reason + " — " + why)


def b7_cal_ibs_qqq_iwm_dia(archive):
    """T-558."""
    miss = _missing(archive, [dh(s) for s in T558_SYMS])
    if miss:
        return miss
    bars = {s: OHLC._bars(archive, s) for s in T558_SYMS}
    rep = ibs_family(bars)
    reason, why = rep.pop("reason"), rep.pop("why")
    stat = {**rep, "rule10": "every trading day (no grid phase)",
            "rule12": "criteria scored under the entry-close and previous-close readings; undecided when they disagree"}
    return _out(stat, rep["n"], rep["verdict"], reason + " — " + why)


def _gold_pair(archive, fut: str):
    gf, ge = MISC._daily(archive, dh(fut)), MISC._daily(archive, dh("GLD"))
    days, (F, A, E) = MISC._align((gf["days"], gf["close"]), (ge["days"], ge["adj"]), (ge["days"], ge["close"]))
    return days, F, A, E


def b7_cal_gold_futures_bills_vs_gld(archive):
    """T-555."""
    miss = _missing(archive, [dh("GC=F"), dh("GLD"), DTB3_B])
    if miss:
        return miss
    bills = MISC._bills(archive)
    days, F, A, E = _gold_pair(archive, "GC=F")
    rep = gold_carry(days, F, A, bills)
    if not rep.get("n") or "ann_diff" not in rep:
        why, reason = rep.pop("why"), rep.pop("reason")
        return _out(rep, rep.get("n", 0), rep["verdict"], reason)
    # T-370's implied-financing reading on the same sessions, side by side (report only)
    imp = None
    try:
        sr = MISC.SameDayRate(MISC._fred(archive, DTB3_B))
        G = MISC.implied_financing(days, F, E, lambda d: MISC.ounces_per_share(d, MISC.GLD_OZ0, MISC.GLD_FEE, MISC.GLD_LAUNCH),
                                   MISC.GC_MONTHS, sr.rates, start=T555_START, end=T555_END)
        hm = MISC.hac_mean(G["dev"], T555_LAG)
        imp = {"mean_i_minus_dtb3": hm["mean"], "ci95": [hm["mean"] - Z95 * hm["se"], hm["mean"] + Z95 * hm["se"]] if hm["se"] else None,
               "n": int(G["dev"].size), "decay": G["decay"],
               "implied_realised_diff": (-hm["mean"] + GLD_FEE) if hm["mean"] is not None else None}
    except (ValueError, ZeroDivisionError, KeyError) as exc:
        imp = {"error": str(exc)}
    mgc = None
    if _has(archive, dh("MGC=F")):                  # optional: the US retail micro contract
        md, MF, MA, _ = _gold_pair(archive, "MGC=F")
        m = gold_carry(md, MF, MA, bills, min_n=1, bad_print=0.25)
        mgc = {k: m.get(k) for k in ("n", "first", "last", "ann_diff", "hac_ci95", "masked_contribution_per_year", "n_bad_prints")}
    rep.update(implied_financing=imp, micro_gold=mgc)
    why = rep.pop("why")
    prof = rep["roll_profile"]
    imp_txt = ("n/a" if not imp or imp.get("mean_i_minus_dtb3") is None else
               f"mean(i - DTB3) {_bp(imp['mean_i_minus_dtb3'], 0)} (95% CI {_bp(imp['ci95'][0], 0)}..{_bp(imp['ci95'][1], 0)}, "
               f"{imp['n']} days), which read as a carry implies futures + bills - GLD of about {_pc(imp['implied_realised_diff'])}/yr "
               f"(-(i - DTB3) + the 0.40% fee)"
               + (f"; level-free decay reading {_bp(imp['decay']['dev'], 0)}" if imp.get("decay") else ""))
    reason = (f"GC=F (Yahoo continuous front) + DTB3 accrual minus GLD total return, {rep['first']}..{rep['last']}, {rep['n']} "
              f"sessions outside T-370's roll mask (+-{T555_WINDOW} sessions around the last session before each first notice "
              f"day; {rep['n_masked']} masked): annualised difference {_pc(rep['ann_diff'])} (HAC lag {T555_LAG} 95% CI "
              f"{_pc(rep['hac_ci95'][0])}..{_pc(rep['hac_ci95'][1])}; needs >= {T555_BAR * 100:.1f}% and lower > 0), legs futures "
              f"{_pc(rep['fut_leg_ann'])} + bills {_pc(rep['bills_ann'])} vs GLD {_pc(rep['gld_ann'])}; halves split {rep['split']} "
              f"{_pc(rep['halves_ann'][0])} / {_pc(rep['halves_ann'][1])}. Artefact readings side by side (report only): masked "
              f"sessions' drift {_pc(rep['masked_mean_ann'])} annualised per masked session, {_pc(rep['masked_contribution_per_year'])}"
              f" a year in total; all sessions (continuous series, roll jumps included) {_pc(rep['all_sessions_per_year'])} a year; "
              f"{rep['unmasked_jumps']} unmasked sessions beyond {T555_JUMP_K:g} robust s.d. summing {_pc(rep['unmasked_jump_sum'])} "
              f"(ex-jumps {_pc(rep['ann_diff_ex_jumps'])}); roll profile over {prof['n_rolls']} scheduled rolls (mean difference by "
              f"session offset from the last session before first notice, bps): "
              + ", ".join(f"{k} {_s2(None if v_ is None else v_ * 1e4)}" for k, v_ in prof["mean_by_offset"].items())
              + f" (inside the mask {_bp(prof['per_roll_inside_mask'], 1)} per roll; largest outside {_bp(prof['max_outside_mask'], 1)}); "
              f"T-370 implied financing on the same pair: {imp_txt}"
              + (f"; MGC=F (micro, {mgc['first']}..{mgc['last']}, {mgc['n']} sessions, {mgc['n_bad_prints']} impossible prints "
                 f"(|daily return| > 25%) dropped) {_pc(mgc['ann_diff'])} (HAC 95% CI {_pc(mgc['hac_ci95'][0])}.."
                 f"{_pc(mgc['hac_ci95'][1])})" if mgc and mgc.get("ann_diff") is not None else "")
              + ". Measurement limits (rule 9): Yahoo's continuous contract identity and roll days are undocumented, the COMEX "
              "settle (13:30 ET) and GLD close (16:00 ET) are asynchronous")
    stat = {**rep, "rule10": "every unmasked session (no grid phase)"}
    return _out(stat, rep["n"], rep["verdict"], reason + " — " + why)


HARNESSES = {
    "b7_cal_tom_country_etfs": b7_cal_tom_country_etfs,
    "b7_cal_halloween_country_etfs": b7_cal_halloween_country_etfs,
    "b7_cal_overnight_qqq_iwm": b7_cal_overnight_qqq_iwm,
    "b7_cal_ibs_qqq_iwm_dia": b7_cal_ibs_qqq_iwm_dia,
    "b7_cal_gold_futures_bills_vs_gld": b7_cal_gold_futures_bills_vs_gld,
}

THEORY_MAP = {
    "T-547": "b7_cal_tom_country_etfs",
    "T-548": "b7_cal_halloween_country_etfs",
    "T-549": "b7_cal_overnight_qqq_iwm",
    "T-558": "b7_cal_ibs_qqq_iwm_dia",
    "T-555": "b7_cal_gold_futures_bills_vs_gld",
}
