"""
Batch 6b, group ``volh``: T-250, the implied-minus-realised cross-sector correlation premium of SPY and the nine original
SPDR sector ETFs, on the DoltHub volatility history (2019-2026).
=====================================================================================================================

Claim (T-250, options library ``sector_correlation_trade``): implied cross-sector correlation computed from SPY and the
nine original SPDR sector ETFs' (XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY) 30-day ATM IVs exceeds the subsequently
realised 21-day correlation of the same ETFs (same formula on realised vols, SPY sector weights) by more than 0.05 on
average. Pass: "Lower 95% bound of the mean > 0.05 over at least 36 cycles; positive in > 65% of non-crisis months
(reported)"; min_n 36 cycles (non-overlapping 21-session cycles).

Data
  * ``dolt-volhistory`` (``mandel.data.dolt_options``; post-no-preference via DoltHub, CC BY-SA 4.0): per snapshot and
    symbol the vendor's ``iv_current`` and ``hv_current``. Snapshots are weekly in 2019 (Saturdays quoting Friday),
    Mon/Wed/Fri 2020-2023 (some Tue/Thu from mid-2024) and daily from 2025. A row is used only when its ``available_at``
    is not after the bundle's capture time. One snapshot per quote session (the data module's ``quote_date``): the one
    taken on the quote day and not flagged stale is kept, else the earliest. A snapshot is used only when all ten symbols
    have a positive ``iv_current`` and the same ``quote_date`` (a stale-moved symbol beside unmoved ones would mix
    sessions; such snapshots are dropped and counted).
  * ``iv_current`` is taken as the vendor's 30-calendar-day ATM implied vol. The data module does not document its tenor,
    so the harness measures it: on every snapshot with an archived SPY chain (``dolt-chain-SPY``, optional) it builds the
    ATM IV of each listed expiry (vendor per-strike IVs, call/put average, linear in strike between the two strikes that
    bracket SPY's raw close) and interpolates total variance to each tenor of 14-45 calendar days; the tenor whose
    interpolated ATM IV is nearest SPY's ``iv_current`` (median absolute difference) is reported, with SPY ``iv_current``
    against VIX/100 (VIX is a 30-day variance-swap rate and sits above ATM IV by the skew). Measured 2026-10-15: best at
    29-30 days, median |difference| 0.13 vol points at 30 days (91% within 0.5 points), against 0.35 points at 21 days and
    0.52 at 45; SPY iv_current correlates 0.986 with VIX/100 and sits 3.2 points below it on average. The sector rows are
    the same vendor field (no sector chains are archived to check them separately).
  * ``hv_current`` is the 30-session close-to-close vol (verified by the data module); the harness re-checks it against
    the archived raw closes as an alignment check of the closes it uses (reported).
  * Realised side: ``daily-history-<SYM>`` for the same ten ETFs. Realised vol over the 21 sessions after the snapshot's
    quote session t (log returns of sessions t+1..t+21 from the dividend-adjusted ``adjclose``, so ex-dividend drops are
    not counted as moves; zero-mean, x sqrt(252), the delta-hedged-P&L convention of the trade). The sample standard
    deviation (demeaned) and raw-close returns are reported sensitivities. Windows that end after the last common close
    are unresolved and left out.
  * Controls: ``cboe-VIX-history`` (crisis months, VIX terciles; optional) and ``cboe-COR1M-history`` (Cboe 1-month
    implied correlation of the 50 largest S&P 500 stocks: a single-stock, not a sector, implied correlation, so it is an
    external level/co-movement check only; optional).

Formula. rho(sigma_SPY, sigma_i, w) = (sigma_SPY^2 - sum_i w_i^2 sigma_i^2) / (sum_{i != j} w_i w_j sigma_i sigma_j), the
library entry's breakeven; the same weights w(t), fixed at the snapshot, enter the implied (IVs) and the realised
(21-session realised vols) side. Values outside [-1, 1] are kept and counted.

Weights (a data limit, rule 9). Historical SPY (S&P 500 GICS) sector weights are NOT archived; only approximate weights
can be built, and none is a point-in-time record of the published weights:
  * anchor schemes: approximate year-end S&P 500 sector weights typed into this module (``ANCHORS``, rounded values of
    S&P's published year-end sector breakdowns, NOT archived and not verified against a primary source in this run) at
    2019-12-31 and 2024-12-31, drifted to each snapshot by each sector ETF's raw-close price relative (market caps move
    with price; index changes, reclassifications and share-count changes are ignored) and normalised over the nine
    sectors (Communication Services and Real Estate, about 12-13% of SPY, are outside the claim's nine-ETF basket).
    ``anchor_nearest`` (the headline) uses the nearer anchor, ``anchor_2019`` and ``anchor_2024`` one anchor throughout
    (drifted backward before it: a measurement proxy for weights that were public at t, not a trading signal). Checked
    on the archived closes: the 2019 anchor drifted to 2024-12-31 lands within 2.0 points of the 2024 anchor on every
    sector (normalised: XLF 13.3 vs 15.3, XLK 38.4 vs 36.7, the rest within 1.4).
  * ``regression_pit``: strictly point in time: non-negative least squares of SPY's daily log returns on the nine
    sectors' over the 252 sessions ending at t, normalised to sum to one (an effective, not a published, weighting: it
    loads the omitted Communication Services exposure on correlated sectors, e.g. XLY).
  The mean criterion is decided only when every scheme agrees (pass under all, fail under all; otherwise undecided), and
  the weights themselves are a criterion that is not implemented (None): no point-in-time published weights exist in the
  archive, so the verdict is at best inconclusive. Equal weights and un-normalised anchor weights (the nine sectors' own
  share, about 0.87) are reported sensitivities.

Statistics and house rule 10. The claim names no entry calendar (non-overlapping 21-day cycles with an arbitrary phase), so
the primary statistic is the POOLED all-start estimate over every snapshot quote session with a resolved window. Because
the snapshot cadence changes (1/week in 2019, 3/week 2020-2023, 5/week from 2025), each calendar week with entries counts
once (the mean of weekly means), which is what a non-overlapping 21-session grid averages in expectation; the
entry-weighted mean is reported. The interval is a studentized circular block bootstrap over calendar weeks (empty weeks
kept; each resample studentized by its Bartlett long-run s.e. at bandwidth = block) with blocks of 2x and 4x the hold in
weeks (the 21-session window spans up to ``hold_weeks`` calendar weeks); "Lower 95% bound" is read as the ONE-SIDED 95%
bound (the test of the stated null at 5%); the two-sided 95% interval is reported. A block or scheme disagreement is
undecided (None). The per-start range is reported: from each snapshot session in the first 21 sessions, a chain of
non-overlapping cycles (each next entry the first snapshot session on or after the previous window's end), with its mean,
one-sided lower bound (studentized, blocks of 2 cycles) and how many starts pass. n is counted in cycles: the fewest
cycles in any per-start chain.

Reported (not judged): "positive in > 65% of non-crisis months" (the pass marks it reported): the calendar months of the
entries, monthly mean of rho_imp - rho_real > 0, crisis month = any VIX close > 30 in it; crisis months separately;
VIX terciles of the entry-day close; COR1M; the walk-forward reading after the first 2 years (the procedure's
"walk-forward after 2 years": the statistic has no fitted parameter, so this is the out-of-burn-in subsample); by year;
a strict point-in-time sensitivity that drops entries whose rows became available after the quote close's evening
(weekend and holiday snapshots); the direct weighted average of pairwise realised sector correlations against the
formula's realised correlation.

Rule 5: below min_n the verdict is never supported and a failing criterion counts only when decisive (its one-sided 95%
upper bound at or below 0.05 under every scheme and block). Rule 9: a missing bundle or too few entries is inconclusive and
names what is missing.

Verdicts use ``underlying2._verdict``: any implemented criterion failing gives not_supported; any criterion not implemented
gives at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import _hac_var

VOL_B = "dolt-volhistory"
CHAIN_B = "dolt-chain-SPY"           # optional: the iv_current tenor check
VIX_B = "cboe-VIX-history"           # optional control
COR1M_B = "cboe-COR1M-history"       # optional control
INDEX = "SPY"
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
SYMS = (INDEX,) + SECTORS
CLOSE_B = {s: f"daily-history-{s}" for s in SYMS}

HOLD = 21                            # sessions in a realised window (the claim's 21-day correlation)
MIN_N = 36                           # trial min_n: cycles
MARGIN = 0.05                        # the claim's premium threshold
CONF = 0.95                          # one-sided confidence of "Lower 95% bound"
BLOCK_HOLDS = (2, 4)                 # pooled blocks in multiples of the hold (rule 10: >= 2x)
CHAIN_BLOCK = 2                      # per-start non-overlapping chains: block of cycles
REG_WINDOW = 252                     # regression weights: trailing sessions
CRISIS_VIX = 30.0                    # crisis month: any VIX close above this
MONTH_POS_SHARE = 0.65               # reported: share of non-crisis months with a positive premium
WALK_YEARS = 2                       # walk-forward burn-in
HV_N = 30                            # hv_current: 30-session close-to-close vol
HV_TOL = 0.00006                     # 4-decimal rounding plus close-price precision (the data module's tolerance)
TENORS = tuple(range(14, 46))        # tenor check, calendar days
MIN_CLUSTERS = 8
N_BOOT = 2000
SEED = 0
PPY = 252
HEADLINE = "anchor_nearest"

# Approximate S&P 500 GICS sector weights (percent) at the year-end, rounded; typed in, NOT archived (see the docstring).
# XLC = Communication Services and XLRE = Real Estate are outside the claim's nine-ETF basket.
ANCHORS = {
    "2019-12-31": {"XLK": 23.2, "XLV": 14.2, "XLF": 13.0, "XLY": 9.8, "XLI": 9.1, "XLP": 7.2, "XLE": 4.3, "XLU": 3.3,
                   "XLB": 2.7, "XLC": 10.4, "XLRE": 2.9},
    "2024-12-31": {"XLK": 32.5, "XLF": 13.6, "XLY": 11.3, "XLV": 10.1, "XLI": 8.2, "XLP": 5.5, "XLE": 3.2, "XLU": 2.3,
                   "XLB": 1.9, "XLC": 9.4, "XLRE": 2.1},
}


# ===================================================================================================== formatting ==

def _f(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pct(x, nd: int = 0) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{100 * x:.{nd}f}%"


def _rng(xs, nd: int = 3) -> str:
    xs = [x for x in xs if x is not None and math.isfinite(x)]
    return "n/a" if not xs else f"{min(xs):+.{nd}f}..{max(xs):+.{nd}f}"


def _ok_txt(ok) -> str:
    return "PASS" if ok is True else "FAIL" if ok is False else "UNDECIDED"


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        f = float(x)
        return f if math.isfinite(f) else None
    return x


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _corr(a, b) -> Optional[float]:
    """Pearson correlation; None when either side is constant or there are fewer than 3 points."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size < 3 or a.size != b.size or float(np.std(a)) <= 0 or float(np.std(b)) <= 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def _num(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


# ===================================================================================================== statistics ==

def stud_bounds(S, N, block: int, n_boot: Optional[int] = None, seed: int = SEED, conf: float = CONF) -> Optional[dict]:
    """Studentized circular block bootstrap of the ratio-of-sums mean sum(S)/sum(N) over time-ordered clusters (empty
    clusters stay in the timeline). Each resample is studentized by its own Bartlett long-run s.e. (bandwidth = block) of
    the influence function psi_c = (S_c - m N_c) / Nbar. Returns {mean, se, block, lower, upper (one-sided at ``conf``),
    ci95 (two-sided)}; None with fewer than MIN_CLUSTERS non-empty clusters."""
    S = np.asarray(S, dtype=float)
    N = np.asarray(N, dtype=float)
    W = S.size
    if W == 0 or int((N > 0).sum()) < MIN_CLUSTERS:
        return None
    n_boot = N_BOOT if n_boot is None else n_boot
    block = max(1, min(int(block), W // 4))
    tot = float(N.sum())
    m = float(S.sum() / tot)
    psi = (S - m * N) / (tot / W)
    se = math.sqrt(float(_hac_var(psi[None, :], block)[0]) / W)
    out = {"mean": m, "se": se, "block": int(block), "lower": m, "upper": m, "ci95": [m, m]}
    if se <= 1e-15:
        return out
    rng = np.random.default_rng(seed)
    nb = math.ceil(W / block)
    ts = []
    done = 0
    step = max(1, min(n_boot, 4_000_000 // max(W, 1)))
    while done < n_boot:
        k = min(step, n_boot - done)
        done += k
        starts = rng.integers(0, W, size=(k, nb))
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :W] % W
        Sb, Nb = S[idx], N[idx]
        tb = Nb.sum(axis=1)
        ok = tb > 0
        if not ok.any():
            continue
        Sb, Nb, tb = Sb[ok], Nb[ok], tb[ok]
        mb = Sb.sum(axis=1) / tb
        pb = (Sb - mb[:, None] * Nb) / (tb / W)[:, None]
        sb = np.sqrt(_hac_var(pb, block) / W)
        good = sb > 1e-15
        ts.append((mb[good] - m) / sb[good])
    t = np.concatenate(ts) if ts else np.zeros(0)
    if t.size < 10:
        return out
    a = 1.0 - conf
    out.update(lower=m - float(np.quantile(t, 1.0 - a)) * se, upper=m - float(np.quantile(t, a)) * se,
               ci95=[m - float(np.quantile(t, 0.975)) * se, m - float(np.quantile(t, 0.025)) * se])
    return out


def _robust(oks: Sequence[Optional[bool]]) -> Optional[bool]:
    """True when every variant passes, False when every variant fails, None when any is undecided or they disagree."""
    if not oks or any(o is None for o in oks):
        return None
    if all(oks):
        return True
    if not any(oks):
        return False
    return None


def week_index(days: Sequence[str]) -> np.ndarray:
    o = np.array([date.fromisoformat(d).toordinal() for d in days], dtype=np.int64)
    if not o.size:
        return o
    first = int(o.min())
    mon = first - date.fromordinal(first).weekday()
    return (o - mon) // 7


def week_clusters(days: Sequence[str], x, weighting: str = "week") -> tuple:
    """(S, N) per Monday-anchored calendar week from the first to the last entry (empty weeks kept). 'week': each week
    with entries counts once (S = its mean, N = 1); 'entry': S = the week's sum, N = its count."""
    x = np.asarray(x, dtype=float)
    if not len(days):
        return np.zeros(0), np.zeros(0)
    w = week_index(days)
    W = int(w.max()) + 1
    S, N = np.zeros(W), np.zeros(W)
    np.add.at(S, w, x)
    np.add.at(N, w, 1.0)
    if weighting == "week":
        has = N > 0
        S = np.where(has, S / np.maximum(N, 1.0), 0.0)
        N = has.astype(float)
    return S, N


def pooled_test(days: Sequence[str], x, hold_weeks: int, margin: float = MARGIN, weighting: str = "week",
                holds: Sequence[int] = BLOCK_HOLDS, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Rule-10 pooled all-start mean over every entry (weekly clusters), one-sided 95% bounds at blocks of h x
    ``hold_weeks`` weeks for each h. ok: lower > margin; decisive fail: upper <= margin; both robust over the blocks."""
    S, N = week_clusters(days, x, weighting)
    rows = []
    for h in holds:
        bw = int(h * hold_weeks)
        b = stud_bounds(S, N, bw, n_boot, seed)
        if b is None:
            rows.append({"holds": int(h), "block_weeks": bw, "lower": None, "upper": None, "ci95": [None, None],
                         "ok": None, "decisive_fail": None})
            continue
        rows.append({"holds": int(h), "block_weeks": bw, "block_used": b["block"], "lower": b["lower"], "upper": b["upper"],
                     "ci95": b["ci95"], "se": b["se"], "ok": bool(b["lower"] > margin),
                     "decisive_fail": bool(b["upper"] <= margin)})
    mean = float(S.sum() / N.sum()) if N.sum() > 0 else None
    return {"mean": mean, "weighting": weighting, "n_entries": int(np.asarray(x).size), "n_weeks": int(S.size),
            "n_weeks_with_entries": int((N > 0).sum()), "by_block": rows, "ok": _robust([r["ok"] for r in rows]),
            "decisive_fail": bool(rows) and all(r["decisive_fail"] is True for r in rows)}


def _decide(crit: list, n: int, min_n: int, unit: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n a failing criterion counts only when it fails decisively (rule 5);
    otherwise it is reported as not decisive (None). Appends the min_n criterion."""
    rows = []
    for name, ok, dec in crit:
        if ok is not None and not bool(ok) and n < min_n and not dec:
            rows.append((name + " [fails, not decisively, below min_n]", None))
        else:
            rows.append((name, None if ok is None else bool(ok)))
    rows.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    return _verdict(rows)


# ======================================================================================== correlation and weights ==

def implied_corr(sig_index, sig_sec, w) -> np.ndarray:
    """rho = (s_I^2 - sum w_i^2 s_i^2) / (sum_{i != j} w_i w_j s_i s_j), row-wise. sig_index (E,), sig_sec and w (E, 9);
    NaN where the denominator is not positive or an input is missing."""
    si = np.atleast_1d(np.asarray(sig_index, dtype=float))
    ss = np.atleast_2d(np.asarray(sig_sec, dtype=float))
    ww = np.atleast_2d(np.asarray(w, dtype=float))
    ws = ww * ss
    own = np.sum(ws * ws, axis=1)
    den = np.sum(ws, axis=1) ** 2 - own
    with np.errstate(invalid="ignore", divide="ignore"):
        rho = (si * si - own) / den
    return np.where(np.isfinite(rho) & (den > 0), rho, np.nan)


def nnls(X, y, max_iter: int = 200) -> np.ndarray:
    """Lawson-Hanson non-negative least squares: argmin ||X b - y|| subject to b >= 0 (no scipy)."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n = X.shape[1]
    P = np.zeros(n, dtype=bool)
    b = np.zeros(n)
    w = X.T @ (y - X @ b)
    tol = 1e-12 * max(1.0, float(np.abs(X).max()) ** 2 * X.shape[0])
    it = 0
    while (~P).any() and float(np.max(np.where(~P, w, -np.inf))) > tol and it < max_iter:
        it += 1
        P[int(np.argmax(np.where(~P, w, -np.inf)))] = True
        while True:
            z = np.zeros(n)
            z[P] = np.linalg.lstsq(X[:, P], y, rcond=None)[0]
            if (z[P] > 0).all():
                b = z
                break
            neg = P & (z <= 0)
            alpha = float(np.min(b[neg] / (b[neg] - z[neg])))
            b = b + alpha * (z - b)
            P &= b > 1e-15
            b[~P] = 0.0
            if not P.any():
                break
        w = X.T @ (y - X @ b)
    return b


def regression_weights(r_index, r_sec) -> Optional[np.ndarray]:
    """NNLS weights of the index's returns on the sectors' (T, 9), normalised to sum one; None if all zero or too few."""
    r_index = np.asarray(r_index, dtype=float)
    r_sec = np.asarray(r_sec, dtype=float)
    ok = np.isfinite(r_index) & np.isfinite(r_sec).all(axis=1)
    if ok.sum() < 2 * r_sec.shape[1]:
        return None
    b = nnls(r_sec[ok], r_index[ok])
    return b / b.sum() if b.sum() > 0 else None


def anchor_vector(anchor: dict, sectors: Sequence[str] = SECTORS) -> tuple:
    """(normalised nine-sector weights, the nine's share of the index) from an anchor table in percent."""
    v = np.array([float(anchor[s]) for s in sectors])
    return v / v.sum(), float(v.sum() / sum(float(x) for x in anchor.values()))


def drift_weights(w_anchor, px_anchor, px_t) -> np.ndarray:
    """Anchor weights drifted by price relatives: w_i(t) proportional to w_i(a) P_i(t) / P_i(a), normalised. px_* (..., 9)."""
    w = np.asarray(w_anchor, dtype=float) * np.asarray(px_t, dtype=float) / np.asarray(px_anchor, dtype=float)
    return w / w.sum(axis=-1, keepdims=True)


def weight_schemes(days: Sequence[str], close, adj, sess, anchors: Optional[dict] = None,
                   reg_window: int = REG_WINDOW) -> tuple:
    """({judged scheme: (E, 9)}, {reported scheme: (E, 9)}, info) for entries at session indices ``sess`` of ``days``.
    close/adj (T, 10) with the index first. Judged: anchor_nearest, anchor_<year> per anchor, regression_pit; reported:
    equal weights and the nearest anchor un-normalised (times the nine's share of the index)."""
    anchors = ANCHORS if anchors is None else anchors
    close = np.asarray(close, dtype=float)
    adj = np.asarray(adj, dtype=float)
    sess = np.asarray(sess, dtype=np.int64)
    E = sess.size
    judged, info = {}, {"anchors": {}}
    an_w, an_share, an_idx = {}, {}, {}
    for ad, tab in sorted(anchors.items()):
        i = bisect_right(list(days), ad) - 1
        if i < 0:
            continue
        w0, share = anchor_vector(tab)
        an_w[ad], an_share[ad], an_idx[ad] = w0, share, i
        judged[f"anchor_{ad[:4]}"] = drift_weights(w0, close[i, 1:], close[sess, 1:]) if E else np.zeros((0, 9))
        info["anchors"][ad] = {"session": days[i], "nine_sector_share": share,
                               "weights": {s: float(x) for s, x in zip(SECTORS, w0)}}
    if an_w:
        ords = {ad: date.fromisoformat(ad).toordinal() for ad in an_w}
        near = np.empty((E, 9))
        share = np.empty(E)
        for k, i in enumerate(sess):
            o = date.fromisoformat(days[int(i)]).toordinal()
            ad = min(ords, key=lambda a: (abs(ords[a] - o), a))
            near[k] = judged[f"anchor_{ad[:4]}"][k]
            share[k] = an_share[ad]
        judged = {"anchor_nearest": near, **judged}
    else:
        share = np.full(E, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        lr = np.diff(np.log(adj), axis=0)
    reg = np.full((E, 9), np.nan)
    for k, i in enumerate(sess):
        i = int(i)
        if i < reg_window:
            continue
        wv = regression_weights(lr[i - reg_window:i, 0], lr[i - reg_window:i, 1:])
        if wv is not None:
            reg[k] = wv
    judged["regression_pit"] = reg
    reported = {"equal": np.full((E, 9), 1.0 / 9.0)}
    if "anchor_nearest" in judged:
        reported["anchor_nearest_unnormalised"] = judged["anchor_nearest"] * share[:, None]
    return judged, reported, info


# ============================================================================================= realised volatility ==

def realised_vols(logret, sess, hold: int = HOLD, demean: bool = False) -> np.ndarray:
    """(E, K) annualised vols of returns logret[i : i + hold] (sessions i+1..i+hold after the entry at session i).
    Zero-mean sqrt(252 mean r^2) by default; the sample standard deviation x sqrt(252) when ``demean``."""
    lr = np.asarray(logret, dtype=float)
    z = np.zeros((1, lr.shape[1]))
    c1 = np.vstack([z, np.cumsum(lr, axis=0)])
    c2 = np.vstack([z, np.cumsum(lr * lr, axis=0)])
    sess = np.asarray(sess, dtype=np.int64)
    s1 = c1[sess + hold] - c1[sess]
    s2 = c2[sess + hold] - c2[sess]
    if demean:
        var = (s2 - s1 * s1 / hold) / (hold - 1)
    else:
        var = s2 / hold
    return np.sqrt(np.maximum(var, 0.0) * PPY)


def pairwise_realised(logret, sess, w, hold: int = HOLD) -> np.ndarray:
    """Direct check: the weighted average of the sectors' pairwise realised correlations over each window, weights
    w_i w_j sigma_i sigma_j over i != j (columns 1.. of logret are the sectors)."""
    lr = np.asarray(logret, dtype=float)
    out = np.full(len(sess), np.nan)
    for k, i in enumerate(sess):
        X = lr[int(i):int(i) + hold, 1:]
        if not np.isfinite(X).all() or not np.isfinite(w[k]).all():
            continue
        if (np.std(X, axis=0) <= 0).any():
            continue
        C = np.corrcoef(X.T)
        sd = np.sqrt(np.mean(X * X, axis=0))
        a = w[k] * sd
        M = np.outer(a, a)
        np.fill_diagonal(M, 0.0)
        if M.sum() > 0:
            out[k] = float((M * C).sum() / M.sum())
    return out


# =================================================================================================== chains (rule 10) ==

def grid_chains(sess, hold: int = HOLD) -> list:
    """Per-start non-overlapping chains over sorted entry session indices: one chain from each entry in the first
    ``hold`` sessions; each next entry is the first one at or after the previous window's end (session + hold).
    Returns lists of positions into ``sess``."""
    s = [int(x) for x in sess]
    if not s:
        return []
    chains = []
    for p0 in range(len(s)):
        if s[p0] >= s[0] + hold:
            break
        ch, p = [p0], p0
        while True:
            q = bisect_left(s, s[p] + hold)
            if q >= len(s):
                break
            ch.append(q)
            p = q
        chains.append(ch)
    return chains


def chain_scan(sess, x, hold: int = HOLD, margin: float = MARGIN, block: int = CHAIN_BLOCK,
               n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Every per-start chain's mean and one-sided 95% lower bound (studentized circular blocks of ``block`` cycles)."""
    x = np.asarray(x, dtype=float)
    rows = []
    for ch in grid_chains(sess, hold):
        v = x[ch]
        v = v[np.isfinite(v)]
        b = stud_bounds(v, np.ones(v.size), block, n_boot, seed) if v.size else None
        rows.append({"start_session": int(sess[ch[0]]), "n": int(v.size), "mean": float(v.mean()) if v.size else None,
                     "lower": None if b is None else b["lower"],
                     "pass": None if b is None else bool(b["lower"] > margin)})
    return {"chains": rows, "n_starts": len(rows), "n_min": min((r["n"] for r in rows), default=0),
            "n_max": max((r["n"] for r in rows), default=0), "n_pass": sum(1 for r in rows if r["pass"] is True)}


# ================================================================================================ the core test ==

def premium_test(days: Sequence[str], adj, close, entries: Sequence[dict], weights: dict, sens_weights: Optional[dict] = None,
                 weights_pit: bool = False, weights_note: str = "", vix: Optional[dict] = None,
                 cor1m: Optional[dict] = None, hold: int = HOLD, margin: float = MARGIN, min_n: int = MIN_N,
                 n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """T-250 on aligned data. days (T sessions); adj, close (T, 10), index first; entries: [{quote_date, snapshot_date,
    available_at, iv: (10,)}] whose quote_date is a session in ``days``, sorted, aligned with the rows of every weights
    array {scheme: (E, 9)} (the judged schemes; the first is the headline). ``weights_pit`` says whether the weights are
    point-in-time published weights (else that criterion is not implemented). vix / cor1m: {day: close}."""
    days = list(days)
    adj = np.asarray(adj, dtype=float)
    close = np.asarray(close, dtype=float)
    sens_weights = sens_weights or {}
    vix = vix or {}
    cor1m = cor1m or {}
    T = len(days)
    pos = {d: i for i, d in enumerate(days)}
    sess = np.array([pos[e["quote_date"]] for e in entries], dtype=np.int64)
    iv = np.array([np.asarray(e["iv"], dtype=float) for e in entries]).reshape(len(entries), len(SYMS))
    resolved = sess + hold <= T - 1
    E_all = len(entries)
    with np.errstate(invalid="ignore", divide="ignore"):
        lr = np.diff(np.log(adj), axis=0)
        lr_raw = np.diff(np.log(close), axis=0)
    keep = resolved.copy()
    if keep.any():
        idx = np.where(keep)[0]
        fin = np.array([np.isfinite(lr[int(sess[k]):int(sess[k]) + hold]).all() for k in idx])
        keep[idx[~fin]] = False
    sel = np.where(keep)[0]
    s_sel = sess[sel]
    ent = [entries[k] for k in sel]
    edays = [e["quote_date"] for e in ent]
    unit = f"non-overlapping {hold}-session cycles"
    base = {"n_entries_given": E_all, "n_unresolved": int((~resolved).sum()), "n_entries": int(sel.size),
            "first": edays[0] if edays else None, "last": edays[-1] if edays else None}
    names = list(weights)
    if sel.size < 2 * MIN_CLUSTERS or not names:
        chains = grid_chains(s_sel, hold)
        n = min((len(c) for c in chains), default=0)
        crit = [(f"POOLED mean of rho_imp - rho_real one-sided 95% lower bound > {margin}", None, False),
                ("point-in-time SPY sector weights", True if weights_pit else None, False)]
        verdict, why = _decide(crit, n, min_n, unit)
        body = (f"only {sel.size} snapshot sessions with a resolved {hold}-session window (of {E_all}; "
                f"{int((~resolved).sum())} end after the last close): too few to test")
        return {**base, "n": n, "verdict": verdict, "why": why, "reason_core": body, "reason": body + " — " + why}
    rv = realised_vols(lr, s_sel, hold)
    rv_dm = realised_vols(lr, s_sel, hold, demean=True)
    rv_raw = realised_vols(lr_raw, s_sel, hold)
    ivs = iv[sel]
    end_days = [days[int(i) + hold] for i in s_sel]
    span = max(date.fromisoformat(b).toordinal() - date.fromisoformat(a).toordinal() for a, b in zip(edays, end_days))
    hold_weeks = int(math.ceil((span + 1) / 7.0))

    def series(w, vols=rv):
        ri = implied_corr(ivs[:, 0], ivs[:, 1:], w)
        rr = implied_corr(vols[:, 0], vols[:, 1:], w)
        return ri, rr, ri - rr

    per = {}
    for nm in names:
        w = np.asarray(weights[nm], dtype=float)[sel]
        ri, rr, d = series(w)
        ok = np.isfinite(d)
        dd = [edays[k] for k in np.where(ok)[0]]
        pt = pooled_test(dd, d[ok], hold_weeks, margin, "week", n_boot=n_boot, seed=seed)
        pe = pooled_test(dd, d[ok], hold_weeks, margin, "entry", holds=(BLOCK_HOLDS[0],), n_boot=n_boot, seed=seed)
        cs = chain_scan(s_sel[ok], d[ok], hold, margin, n_boot=n_boot, seed=seed)
        per[nm] = {"pooled": pt, "entry_weighted": pe, "chains": cs,
                   "mean_rho_implied": float(ri[np.isfinite(ri)].mean()) if np.isfinite(ri).any() else None,
                   "mean_rho_realised": float(rr[np.isfinite(rr)].mean()) if np.isfinite(rr).any() else None,
                   "n_valid": int(ok.sum()),
                   "rho_implied_outside_pm1": int(np.sum(np.abs(ri[np.isfinite(ri)]) > 1)),
                   "rho_realised_outside_pm1": int(np.sum(np.abs(rr[np.isfinite(rr)]) > 1)),
                   "mean_weights": {s: (float(np.mean(w[np.isfinite(w).all(axis=1), j])) if np.isfinite(w).all(axis=1).any()
                                        else None) for j, s in enumerate(SECTORS)}}
    head = names[0]
    wH = np.asarray(weights[head], dtype=float)[sel]
    riH, rrH, dH = series(wH)
    okH = np.isfinite(dH)
    hd = [edays[k] for k in np.where(okH)[0]]
    xH = dH[okH]
    sH = s_sel[okH]
    n = per[head]["chains"]["n_min"]
    n_pool = len({int(i) // hold for i in sH}) if sH.size else 0
    # --- criteria
    oks = [per[nm]["pooled"]["ok"] for nm in names]
    decs = [per[nm]["pooled"]["decisive_fail"] for nm in names]
    ok_mean = _robust(oks)
    dec_mean = bool(decs) and all(decs)
    mean_txt = "; ".join(
        f"{nm} {_s(per[nm]['pooled']['mean'])} (lower " + "/".join(_s(r['lower']) for r in per[nm]['pooled']['by_block'])
        + f" at {'/'.join(str(r['block_weeks']) for r in per[nm]['pooled']['by_block'])}-week blocks: "
        + _ok_txt(per[nm]['pooled']['ok']) + ")" for nm in names)
    crit = [(f"POOLED week-weighted mean of rho_imp - rho_real: one-sided 95% lower bound > {margin} under every weight "
             f"scheme and block ({mean_txt})", ok_mean, dec_mean),
            ("point-in-time SPY sector weights" + (f" ({weights_note})" if weights_note else ""),
             True if weights_pit else None, False)]
    verdict, why = _decide(crit, n, min_n, unit)
    # --- reported controls (headline scheme)
    months = defaultdict(list)
    for dday, x in zip(hd, xH):
        months[dday[:7]].append(x)
    vmax = defaultdict(float)
    for dday, v in vix.items():
        if v is not None:
            vmax[dday[:7]] = max(vmax[dday[:7]], float(v))
    mon_mean = {m: float(np.mean(v)) for m, v in months.items()}
    if vix:
        crisis = {m for m in mon_mean if vmax.get(m, 0.0) > CRISIS_VIX}
        nonc = [m for m in mon_mean if m not in crisis]
        share_pos = (sum(1 for m in nonc if mon_mean[m] > 0) / len(nonc)) if nonc else None
        cris_x = [x for dday, x in zip(hd, xH) if dday[:7] in crisis]
        nonc_x = [x for dday, x in zip(hd, xH) if dday[:7] not in crisis]
    else:
        crisis, nonc, share_pos, cris_x, nonc_x = set(), list(mon_mean), None, [], list(xH)
    month_rep = {"n_months": len(mon_mean), "n_crisis_months": len(crisis), "n_noncrisis_months": len(nonc),
                 "share_noncrisis_positive": share_pos,
                 "above_065": None if share_pos is None else bool(share_pos > MONTH_POS_SHARE),
                 "crisis_months": sorted(crisis), "mean_crisis_entries": float(np.mean(cris_x)) if cris_x else None,
                 "n_crisis_entries": len(cris_x), "mean_noncrisis_entries": float(np.mean(nonc_x)) if nonc_x else None}
    vix_e = np.array([_num(vix.get(dday)) if vix.get(dday) is not None else np.nan for dday in hd], dtype=float)
    terc = None
    if np.isfinite(vix_e).sum() >= 9:
        q1, q2 = np.nanquantile(vix_e, [1 / 3, 2 / 3])
        terc = []
        for lo, hi, lab in ((-np.inf, q1, "low"), (q1, q2, "mid"), (q2, np.inf, "high")):
            m = np.isfinite(vix_e) & (vix_e > lo) & (vix_e <= hi)
            terc.append({"tercile": lab, "vix_range": [None if not math.isfinite(lo) else float(lo),
                                                       None if not math.isfinite(hi) else float(hi)],
                         "n": int(m.sum()), "mean": float(xH[m].mean()) if m.any() else None})
    c_e = np.array([_num(cor1m.get(dday)) if cor1m.get(dday) is not None else np.nan for dday in hd], dtype=float)
    riHk = riH[okH]
    cm = np.isfinite(c_e) & np.isfinite(riHk)
    cor_rep = None
    if cm.sum() >= 10:
        a, b = riHk[cm], c_e[cm] / 100.0
        da, db = np.diff(a), np.diff(b)
        cor_rep = {"n": int(cm.sum()), "mean_cor1m": float(b.mean()), "mean_rho_implied": float(a.mean()),
                   "corr_levels": _corr(a, b), "corr_changes": _corr(da, db)}
    # walk-forward after WALK_YEARS years, by year
    first_o = date.fromisoformat(hd[0] if hd else edays[0])
    cut = date(first_o.year + WALK_YEARS, first_o.month, min(first_o.day, 28)).isoformat()
    wf_m = np.array([dday >= cut for dday in hd], dtype=bool)
    wf = pooled_test([dday for dday, m in zip(hd, wf_m) if m], xH[wf_m], hold_weeks, margin, "week",
                     holds=(BLOCK_HOLDS[0],), n_boot=n_boot, seed=seed) if wf_m.sum() >= 2 * MIN_CLUSTERS else None
    by_year = {}
    for dday, x in zip(hd, xH):
        by_year.setdefault(dday[:4], []).append(x)
    by_year = {y: {"n": len(v), "mean": float(np.mean(v))} for y, v in sorted(by_year.items())}
    # strict point in time: drop entries whose rows became available after the quote day's evening
    ent_ok = [ent[k] for k in np.where(okH)[0]]
    strict_m = np.array([(e.get("available_at") or "")[:10] <= e["quote_date"] for e in ent_ok], dtype=bool)
    strict = pooled_test([dday for dday, m in zip(hd, strict_m) if m], xH[strict_m], hold_weeks, margin, "week",
                         holds=(BLOCK_HOLDS[0],), n_boot=n_boot, seed=seed) if strict_m.sum() >= 2 * MIN_CLUSTERS else None
    # realised-vol conventions and weight sensitivities (headline weights unless named)
    sens = {}
    for lab, vols in (("demeaned", rv_dm), ("raw_close", rv_raw)):
        _, _, d2 = series(wH, vols)
        m2 = np.isfinite(d2)
        sens[lab] = pooled_test([edays[k] for k in np.where(m2)[0]], d2[m2], hold_weeks, margin, "week",
                                holds=(BLOCK_HOLDS[0],), n_boot=n_boot, seed=seed)
    for lab, w in sens_weights.items():
        _, _, d2 = series(np.asarray(w, dtype=float)[sel])
        m2 = np.isfinite(d2)
        sens[lab] = pooled_test([edays[k] for k in np.where(m2)[0]], d2[m2], hold_weeks, margin, "week",
                                holds=(BLOCK_HOLDS[0],), n_boot=n_boot, seed=seed)
    pw = pairwise_realised(lr, s_sel, wH, hold)
    pm = np.isfinite(pw) & np.isfinite(rrH)
    pair_rep = {"n": int(pm.sum()), "mean_pairwise": float(pw[pm].mean()) if pm.any() else None,
                "mean_formula": float(rrH[pm].mean()) if pm.any() else None,
                "corr": _corr(pw[pm], rrH[pm])}
    # --- reason
    pH = per[head]
    cs = pH["chains"]
    body = (
        f"{sel.size} snapshot sessions {edays[0]}..{edays[-1]} with a resolved {hold}-session window "
        f"({base['n_unresolved']} unresolved at the end); window spans up to {span} calendar days, so blocks are "
        f"{BLOCK_HOLDS[0]}x/{BLOCK_HOLDS[1]}x {hold_weeks} weeks. Headline weights {head}: implied correlation averages "
        f"{_f(pH['mean_rho_implied'])}, realised {_f(pH['mean_rho_realised'])}; POOLED week-weighted mean of rho_imp - "
        f"rho_real {_s(pH['pooled']['mean'])} (two-sided 95% CI " + "/".join(
            f"{_s(r['ci95'][0])}..{_s(r['ci95'][1])}" for r in pH['pooled']['by_block']) + "), entry-weighted "
        f"{_s(pH['entry_weighted']['mean'])} (one-sided lower {_s(pH['entry_weighted']['by_block'][0]['lower'])}, reported). "
        f"Criterion vs {margin}: " + _ok_txt(ok_mean)
        + f" (one-sided upper bound <= {margin} under every scheme and block, the rule-5 decisive reading: "
        + ("yes" if dec_mean else "no") + f"). n = {n} cycles "
        f"(fewest in the {cs['n_starts']} per-start non-overlapping chains, {cs['n_min']}-{cs['n_max']}, one from each "
        f"snapshot session in the first {hold} sessions; the entries span "
        f"{n_pool} distinct {hold}-session holds) vs min_n {min_n}. Per-start chains ({head}): mean "
        f"{_rng([r['mean'] for r in cs['chains']])}, one-sided lower {_rng([r['lower'] for r in cs['chains']])}, "
        f"{cs['n_pass']}/{cs['n_starts']} clear {margin}; other schemes pass "
        + ", ".join(f"{nm} {per[nm]['chains']['n_pass']}/{per[nm]['chains']['n_starts']}" for nm in names[1:])
        + f". Reported: non-crisis months positive {_pct(share_pos)} of {len(nonc)} (> 65%: "
        + ("n/a" if share_pos is None else "yes" if share_pos > MONTH_POS_SHARE else "no")
        + f"; reported, not judged); crisis months (VIX > {CRISIS_VIX:.0f}) {len(crisis)}, mean "
        f"{_s(month_rep['mean_crisis_entries'])} over {len(cris_x)} entries vs non-crisis {_s(month_rep['mean_noncrisis_entries'])}; "
        f"VIX terciles " + ("n/a" if terc is None else ", ".join(f"{t['tercile']} {_s(t['mean'])}" for t in terc))
        + "; COR1M " + ("n/a" if cor_rep is None else
                        f"mean {_f(cor_rep['mean_cor1m'])} vs sector implied {_f(cor_rep['mean_rho_implied'])}, corr levels "
                        f"{_f(cor_rep['corr_levels'], 2)}, changes {_f(cor_rep['corr_changes'], 2)}")
        + f"; walk-forward after {WALK_YEARS} years (from {cut}) " + ("n/a" if wf is None else
                                                               f"{_s(wf['mean'])} (lower {_s(wf['by_block'][0]['lower'])})")
        + "; by year " + ", ".join(f"{y} {_s(v['mean'], 2)}" for y, v in by_year.items())
        + "; strict point in time (drop weekend/holiday snapshots) " + ("n/a" if strict is None else
                                                                        f"{_s(strict['mean'])} (lower {_s(strict['by_block'][0]['lower'])}, "
                                                                        f"{strict['n_entries']} entries)")
        + "; " + ", ".join(f"{k} {_s(v['mean'])} (lower {_s(v['by_block'][0]['lower'])})" for k, v in sens.items())
        + f"; direct weighted pairwise realised sector correlation {_f(pair_rep['mean_pairwise'])} vs the formula's "
        f"{_f(pair_rep['mean_formula'])} (corr {_f(pair_rep['corr'], 2)}); |rho| > 1: implied "
        f"{pH['rho_implied_outside_pm1']}, realised {pH['rho_realised_outside_pm1']}")
    return {**base, "n": n, "n_pooled_holds": n_pool, "hold_weeks": hold_weeks, "span_days": span, "headline": head,
            "schemes": per, "criterion_mean_ok": ok_mean, "criterion_mean_decisive_fail": dec_mean,
            "months": month_rep, "vix_terciles": terc, "cor1m": cor_rep, "walk_forward": wf, "walk_forward_from": cut,
            "by_year": by_year, "strict_pit": strict, "sensitivities": sens, "pairwise_check": pair_rep,
            "verdict": verdict, "why": why, "reason_core": body, "reason": body + " — " + why}


# ============================================================================================ archive plumbing ==

def _has(archive, name: str) -> bool:
    try:
        return archive.get(name) is not None
    except (KeyError, AttributeError):
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — "
                "not implemented: every criterion (no data)")
    return None


def _created(archive, name: str) -> str:
    try:
        return getattr(archive.get(name), "created_at", "") or ""
    except (KeyError, AttributeError):
        return ""


def closes_from_rows(rows, created: str = "") -> dict:
    """{day: (raw close, adjclose)} from daily-history rows (``value.t`` = bar time, UTC). A bar dated on or after the
    bundle's capture day is dropped unless the capture came after 21:00 UTC."""
    by = {}
    for r in rows:
        v = r.get("value") or {}
        c = _num(v.get("close"))
        if c is None or c <= 0:
            continue
        if v.get("t") is not None:
            d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        elif v.get("day"):
            d = str(v["day"])[:10]
        else:
            continue
        if created and (d > created[:10] or (d == created[:10] and created[11:16] < "21:00")):
            continue
        a = _num(v.get("adjclose"))
        by[d] = (c, a if a is not None and a > 0 else c)
    return by


def index_closes(rows) -> dict:
    out = {}
    for r in rows:
        v = r.get("value") or {}
        c = _num(v.get("close"))
        d = v.get("day")
        if c is not None and d:
            out[str(d)[:10]] = c
    return out


def snapshots(rows, created: str = "", syms: Sequence[str] = SYMS) -> tuple:
    """({quote_date: entry}, info) from dolt-volhistory rows. One snapshot per quote session (not stale and taken on the
    quote day first, else the earliest); entry = {quote_date, snapshot_date, available_at (latest of the rows), stale,
    iv (10,), hv (10,)}. A snapshot needs every symbol with a positive iv_current and one common quote_date."""
    by = defaultdict(dict)
    late = 0
    for r in rows:
        v = r.get("value") or {}
        s, sd = v.get("symbol"), v.get("snapshot_date")
        if s not in syms or not sd:
            continue
        if created and (r.get("available_at") or "") > created:
            late += 1
            continue
        by[sd][s] = (v, r.get("available_at") or "")
    info = Counter()
    info["snapshot_dates"] = len(by)
    info["rows_after_capture"] = late
    best = {}
    for sd, m in by.items():
        if any(s not in m for s in syms):
            info["missing_symbol"] += 1
            continue
        ivs = [_num(m[s][0].get("iv_current")) for s in syms]
        if any(x is None or x <= 0 for x in ivs):
            info["missing_iv"] += 1
            continue
        qs = {m[s][0].get("quote_date") or sd for s in syms}
        if len(qs) != 1:
            info["mixed_quote_dates"] += 1
            continue
        q = qs.pop()
        stale = any(m[s][0].get("stale") is True for s in syms)
        key = (stale, sd != q, sd)
        e = {"quote_date": q, "snapshot_date": sd, "available_at": max(m[s][1] for s in syms), "stale": stale,
             "iv": np.array(ivs, dtype=float),
             "hv": np.array([_num(m[s][0].get("hv_current")) if _num(m[s][0].get("hv_current")) is not None else np.nan
                             for s in syms], dtype=float)}
        if q in best:
            info["duplicate_quote_day_dropped"] += 1
            if key >= best[q][0]:
                continue
        best[q] = (key, e)
    out = {q: e for q, (k, e) in best.items()}
    info["used"] = len(out)
    info["stale_moved_kept"] = sum(1 for e in out.values() if e["stale"])
    return out, dict(info)


def hv_check(close_col, days: Sequence[str], hv_by_day: dict, n: int = HV_N, tol: float = HV_TOL) -> dict:
    """Share of snapshot hv_current values equal (within ``tol``) to the n-session sample stdev of log close-to-close
    returns x sqrt(252) ending on the quote session, from the closes used here (an alignment check)."""
    pos = {d: i for i, d in enumerate(days)}
    c = np.asarray(close_col, dtype=float)
    hit = tot = 0
    for d, h in hv_by_day.items():
        i = pos.get(d)
        if i is None or i < n or h is None or not math.isfinite(h):
            continue
        r = np.diff(np.log(c[i - n:i + 1]))
        if not np.isfinite(r).all():
            continue
        tot += 1
        hit += abs(float(np.std(r, ddof=1)) * math.sqrt(PPY) - h) <= tol
    return {"n": tot, "match": hit, "share": hit / tot if tot else None}


def atm_term(legs: Sequence[tuple], spot: float, quote_date: str) -> list:
    """[(calendar days, ATM IV)] per expiry from (expiry, strike, iv) legs: the vendor IVs averaged per strike (calls and
    puts), linear in strike between the two strikes that bracket the spot."""
    by = defaultdict(lambda: defaultdict(list))
    for e, k, v in legs:
        if v is not None and v > 0:
            by[e][float(k)].append(float(v))
    q = date.fromisoformat(quote_date).toordinal()
    out = []
    for e, ks in by.items():
        t = date.fromisoformat(e).toordinal() - q
        if t <= 0:
            continue
        strikes = sorted(ks)
        i = bisect_left(strikes, spot)
        if i < len(strikes) and strikes[i] == spot:
            out.append((t, float(np.mean(ks[spot]))))
            continue
        if i == 0 or i >= len(strikes):
            continue
        k0, k1 = strikes[i - 1], strikes[i]
        v0, v1 = float(np.mean(ks[k0])), float(np.mean(ks[k1]))
        out.append((t, v0 + (v1 - v0) * (spot - k0) / (k1 - k0)))
    return sorted(out)


def interp_tenor(term: Sequence[tuple], tau: float) -> Optional[float]:
    """ATM IV at ``tau`` days by linear interpolation of total variance between bracketing expiries (no extrapolation)."""
    for (t0, v0), (t1, v1) in zip(term, term[1:]):
        if t0 <= tau <= t1 and t1 > t0:
            w = v0 * v0 * t0 + (v1 * v1 * t1 - v0 * v0 * t0) * (tau - t0) / (t1 - t0)
            return math.sqrt(w / tau) if w > 0 else None
    return None


def iv_tenor_check(chain_rows, iv_by_snap: dict, spot_by_day: dict, tenors: Sequence[int] = TENORS) -> dict:
    """Which constant tenor of the chain's ATM term structure best matches the vendor's iv_current. chain_rows: archive
    rows of one symbol (value.snapshot_date, quote_date, expiry, strike, iv); iv_by_snap {snapshot_date: iv_current};
    spot_by_day {quote_date: raw close}. Per tenor: n, median |difference|, median difference, share within 0.5 points."""
    legs = defaultdict(list)
    qd = {}
    for r in chain_rows:
        v = r.get("value") or {}
        sd = v.get("snapshot_date")
        if sd not in iv_by_snap or v.get("expiry") is None:
            continue
        legs[sd].append((v["expiry"], _num(v.get("strike")), _num(v.get("iv"))))
        qd[sd] = v.get("quote_date") or sd
    diffs = {t: [] for t in tenors}
    for sd, lg in legs.items():
        s = spot_by_day.get(qd[sd])
        if s is None:
            continue
        term = atm_term([x for x in lg if x[1] is not None], s, qd[sd])
        if len(term) < 2:
            continue
        for t in tenors:
            v = interp_tenor(term, t)
            if v is not None:
                diffs[t].append(iv_by_snap[sd] - v)
    res = {}
    for t, d in diffs.items():
        if d:
            a = np.asarray(d)
            res[t] = {"n": int(a.size), "median_abs": float(np.median(np.abs(a))), "median": float(np.median(a)),
                      "within_0005": float(np.mean(np.abs(a) < 0.005))}
    if not res:
        return {"by_tenor": {}, "best": None, "n_days": 0}
    nmax = max(r["n"] for r in res.values())
    cand = {t: r for t, r in res.items() if r["n"] >= 0.8 * nmax}
    best = min(cand, key=lambda t: (cand[t]["median_abs"], t))
    return {"by_tenor": res, "best": int(best), "n_days": nmax}


# ====================================================================================================== harness ==

def b6b_volh_sector_corr_premium(archive):
    """T-250: implied minus subsequently realised cross-sector correlation (SPY and the nine original SPDR sectors) above
    0.05 on average; see the module docstring."""
    need = [VOL_B] + [CLOSE_B[s] for s in SYMS]
    miss = _missing(archive, need)
    if miss:
        return miss
    created = _created(archive, VOL_B)
    snaps, sinfo = snapshots(archive.load(VOL_B), created)
    cl = {s: closes_from_rows(archive.load(CLOSE_B[s]), _created(archive, CLOSE_B[s])) for s in SYMS}
    days = sorted(set.intersection(*[set(c) for c in cl.values()]))
    if len(days) < REG_WINDOW + HOLD + 10:
        return _out({"sessions": len(days)}, 0, "inconclusive",
                    f"only {len(days)} common sessions across {', '.join(CLOSE_B[s] for s in SYMS)} — "
                    "not implemented: every criterion (closes too short)")
    close = np.array([[cl[s][d][0] for s in SYMS] for d in days])
    adj = np.array([[cl[s][d][1] for s in SYMS] for d in days])
    dset = set(days)
    no_close = sorted(q for q in snaps if q not in dset)
    entries = [snaps[q] for q in sorted(snaps) if q in dset]
    vix = index_closes(archive.load(VIX_B)) if _has(archive, VIX_B) else {}
    cor = index_closes(archive.load(COR1M_B)) if _has(archive, COR1M_B) else {}
    if not entries:
        return _out({"snapshots": sinfo}, 0, "inconclusive",
                    f"no usable {VOL_B} snapshot (all ten symbols with iv_current on a common quote session with closes): "
                    f"{sinfo} — not implemented: every criterion (no snapshots)")
    pos = {d: i for i, d in enumerate(days)}
    sess = np.array([pos[e["quote_date"]] for e in entries], dtype=np.int64)
    judged, reported, winfo = weight_schemes(days, close, adj, sess)
    note = ("not archived: year-end anchors (approximate, typed in) drifted by price, and a trailing NNLS regression; "
            "data limit, rule 9")
    res = premium_test(days, adj, close, entries, judged, reported, weights_pit=False, weights_note=note, vix=vix,
                       cor1m=cor)
    # --- data diagnostics: iv_current tenor and hv alignment
    spy_iv = {e["snapshot_date"]: float(e["iv"][0]) for e in entries}
    spy_iv_q = {e["quote_date"]: float(e["iv"][0]) for e in entries}
    vx = [(spy_iv_q[q], vix[q] / 100.0) for q in spy_iv_q if q in vix and vix[q]]
    vix_cmp = None
    if len(vx) >= 10:
        a = np.array(vx)
        vix_cmp = {"n": len(vx), "corr": _corr(a[:, 0], a[:, 1]),
                   "mean_vix_minus_iv": float((a[:, 1] - a[:, 0]).mean()),
                   "share_iv_below_vix": float(np.mean(a[:, 0] < a[:, 1]))}
    tenor = None
    if _has(archive, CHAIN_B):
        spot = {d: cl[INDEX][d][0] for d in cl[INDEX]}
        tenor = iv_tenor_check(archive.load(CHAIN_B), spy_iv, spot)
    hvc = {}
    for j, s in enumerate(SYMS):
        hvc[s] = hv_check(close[:, j], days, {e["quote_date"]: float(e["hv"][j]) for e in entries})
    hv_share = [v["share"] for v in hvc.values() if v["share"] is not None]
    t30 = (tenor or {}).get("by_tenor", {}).get(30)
    t21 = (tenor or {}).get("by_tenor", {}).get(21)
    t45 = (tenor or {}).get("by_tenor", {}).get(45)
    wmean = res.get("schemes", {})
    wtxt = "; ".join(
        f"{nm} mean " + ", ".join(f"{s} {_f(None if x is None else 100 * x, 1)}" for s, x in v["mean_weights"].items()) + "%"
        for nm, v in wmean.items() if nm in (HEADLINE, "regression_pit"))
    data_txt = (
        f"T-250 on {VOL_B} (vendor iv_current; {sinfo.get('snapshot_dates', 0)} snapshot dates, {sinfo.get('used', 0)} quote "
        f"sessions with all ten IVs on one quote session; dropped: {sinfo.get('missing_iv', 0)} missing an IV, "
        f"{sinfo.get('missing_symbol', 0)} missing a symbol, {sinfo.get('mixed_quote_dates', 0)} with mixed quote dates, "
        f"{sinfo.get('duplicate_quote_day_dropped', 0)} duplicate quote sessions; {len(no_close)} without closes) and "
        f"daily-history adjclose for SPY and {', '.join(SECTORS)}. iv_current tenor evidence: "
        + ("no dolt-chain-SPY" if not tenor or tenor.get("best") is None else
           f"SPY chain ATM IV interpolated in total variance matches iv_current best at {tenor['best']} days over "
           f"{tenor['n_days']} snapshots (median |diff| at 30d {_f(t30['median_abs'] * 100 if t30 else None, 2)} vol pts, "
           f"{_pct(t30['within_0005'] if t30 else None)} within 0.5 pts; 21d {_f(t21['median_abs'] * 100 if t21 else None, 2)}, "
           f"45d {_f(t45['median_abs'] * 100 if t45 else None, 2)})")
        + ("" if vix_cmp is None else
           f"; SPY iv_current vs VIX/100: corr {_f(vix_cmp['corr'], 3)}, VIX above it by {vix_cmp['mean_vix_minus_iv'] * 100:.1f} "
           f"pts on average and on {_pct(vix_cmp['share_iv_below_vix'])} of days, as a 30-day ATM IV sits below the "
           f"variance-swap VIX")
        + f"; sector rows assumed the same field. hv_current re-computed from the closes used: {_rng(hv_share, 3).replace('+', '')} "
        f"share matching per symbol. WEIGHTS (data limit, rule 9): no point-in-time SPY sector weights are archived; "
        f"judged schemes {', '.join(judged)} (anchors {', '.join(winfo['anchors'])} approximate year-end S&P 500 sector "
        f"weights typed in, drifted by raw-close price relatives, normalised over the nine; regression_pit = trailing "
        f"{REG_WINDOW}-session NNLS, strictly point in time): {wtxt}. Realised: zero-mean {HOLD}-session vol of adjclose "
        f"log returns after the quote close. ")
    reason = data_txt + res["reason_core"] + " — " + res["why"]
    stat = {k: v for k, v in res.items() if k not in ("reason", "reason_core", "why")}
    stat.update({"snapshot_info": sinfo, "snapshots_without_closes": no_close, "weights_info": winfo,
                 "weights_point_in_time": False, "iv_tenor_check": tenor, "spy_iv_vs_vix": vix_cmp, "hv_check": hvc,
                 "controls_available": {"VIX": bool(vix), "COR1M": bool(cor)}, "claim_margin": MARGIN, "min_n": MIN_N})
    return _out(stat, res["n"], res["verdict"], reason)


HARNESSES = {
    "b6b_volh_sector_corr_premium": b6b_volh_sector_corr_premium,
}

THEORY_MAP = {
    "T-250": "b6b_volh_sector_corr_premium",
}
