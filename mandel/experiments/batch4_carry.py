"""
Batch 4, crypto carry and funding: perp funding vs dated basis, option-hedged funding carry, funding-filtered trend,
CME basis spikes, CME cash-and-carry, thresholded perp carry, the basis as a crash signal and funding as sentiment.
=====================================================================================================================

Eight library claims (T-198, T-258, T-303, T-329, T-362, T-363, T-364, T-423) tested on archived data, each against
its claim and trial.pass as worded.

Funding. ``deribit-funding-BTC-PERPETUAL`` holds Deribit's hourly records from 2019-05-01. ``interest_1h`` is the
funding accrued over the hour ending at ``timestamp``, as a fraction of position notional. ``interest_8h`` is the
trailing 8-hour sum (the archive confirms it: correlation 0.999 with the rolling 8-hour sum of interest_1h). Deribit
convention (public/get_funding_rate_history and the perpetual contract spec): positive funding means longs pay shorts,
so a SHORT perp receives +interest_1h x notional each hour and pays when it is negative. BTC-PERPETUAL is inverse
(BTC-margined). A short whose USD notional equals the BTC posted as collateral locks the USD value, and a rally
cannot liquidate it at 1x. Funding is therefore treated as a fraction of USD notional. A record is known at its
timestamp.

Spot. The hourly ``index_price`` in the funding records is Deribit's BTC index, a multi-exchange spot composite. It is
the only intraday spot in the archive: coinbase-hourly-BTC-USD is not archived. It starts 2019-05-01 01:00 UTC.
"Synchronous" spot for a CME settle is this index at 15:00 America/Chicago (20:00 UTC under CDT, 21:00 under CST).
The archive confirms the alignment: near expiry the BTC=F close sits within a median 0.066% of that hour's index,
against 0.29-0.42% one or two hours either side. The CME CF BRR, which sets the final settlement, is computed from
trades between 15:00 and 16:00 London. Its proxy here is the mean of the index at 15:00 and 16:00 London. Across 88
expiries that mean is within 0.20% of the final settlement on average (sd 0.26%), while the 16:00 point alone is
0.35% away (sd 0.47%). Before 2019-05 there is no synchronous spot. Claims whose decision window starts earlier carry
a not-implemented coverage criterion: at best inconclusive, and still not_supported if a tested criterion fails. Yahoo
BTC-USD daily closes (00:00 UTC) are used only where a claim asks for daily closes (T-303's trend rule, T-364's
drawdowns).

CME BTC=F (roll handling). Yahoo's continuous front month. Bars are stamped 00:00 New York and the close is the
15:00 CT settle. The archive shows that Yahoo stays on the expiring contract through its last trading day, whose close
is the final settlement (an off-tick print equal to the BRR; 101 of the 106 expiries show it). Yahoo switches to the
next contract on the following trading day. So the front contract on day d is the first CME expiry on or after d. That
expiry is the last Friday of the month, moved to the prior business day for Good Friday, Christmas and New Year. Days to
expiry come from that calendar, not from Yahoo. The expiry-day print is never used as a settle-time basis. Each claim's
roll window is dropped: T-329 drops the 5 trading days before expiry and T-364 drops observations within 3 calendar
days of expiry. T-362 decides on the first session after the previous expiry, far from any roll. Half-day sessions
(bars stamped 08:00/09:00 ET) are dropped because their settle time differs. Per-contract history is not on Yahoo, so roll windows are excluded rather than reconstructed.

Deribit quarterlies. ``deribit-quarterly-futures-btc`` daily bars open at 08:00 UTC (``ts_ms``) and close 24 hours
later; the archive confirms this. The close is compared with the index at that same 08:00 UTC hour. The bar that opens
at expiry is a stale post-expiry bar and is dropped.

Rates. DTB3 is a discount yield. It is converted to a bond-equivalent yield, 365 d / (360 - 91 d). A decision uses the
last value dated before the decision day.

Statistics. "95% CI / interval" means two-sided 95% (the 2.5% and 97.5% quantiles). "95% lower bound" and "bootstrap
lower bound" mean the one-sided 95% lower bound (the 5% quantile). Block, stationary and cluster bootstraps follow each
trial's stated scheme. Crypto annualisation uses 365 days (monthly: 12). Model-priced option legs (T-258) are labelled
MODEL-PRICED.

Verdicts use ``underlying2._verdict``. Any implemented criterion failing gives not_supported. Any criterion that is
not implemented (missing data, too few events) gives at best inconclusive. A claim is supported only when every
criterion is implemented and passes.
"""

from __future__ import annotations

import bisect
import calendar
import math
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments.underlying2 import _mdd, _mean_ci, _sr, _verdict, load_series
from mandel.experiments.volatility import index_closes
from mandel.options import bs
from mandel.validation.backtest_eval import deflated_sharpe_ratio

CRYPTO_PPY = 365
HOUR = 3600
DAY = 86400
FUNDING = "deribit-funding-BTC-PERPETUAL"
QUARTERLIES = "deribit-quarterly-futures-btc"
DELIVERY = "deribit-delivery-prices-btc"
# Joint funding-trial count for T-303's DSR: the sibling funding entries' own trial counts
# (T-198: 1, T-258: 1, T-303: 1, T-363: 12, T-423: 24).
JOINT_FUNDING_TRIALS = 39
# Deribit funding dead band: funding_8h = premium -/+ D outside |premium| <= D. D is 0.025%-0.05% in Deribit's docs;
# the larger value is used so the spread bounds in T-363 are wide (conservative).
DERIBIT_DAMPER = 0.0005

_CHI = ZoneInfo("America/Chicago")
_LON = ZoneInfo("Europe/London")
_NY = ZoneInfo("America/New_York")


# ----------------------------------------------------------------------------------------------- time / calendar --

def _d(x) -> date:
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def _utc_ts(day, hour: int = 0) -> int:
    d = _d(day)
    return int(datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc).timestamp())


def _local_ts(day, hour: int, tz) -> int:
    d = _d(day)
    return int(datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp())


def cme_settle_ts(day) -> int:
    """UTC epoch seconds of the CME BTC daily settle (15:00 America/Chicago) on ``day``."""
    return _local_ts(day, 15, _CHI)


def brr_ts(day) -> int:
    """UTC epoch seconds of the CME CF Bitcoin Reference Rate fix (16:00 Europe/London) on ``day``."""
    return _local_ts(day, 16, _LON)


def _day_of(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")


def _easter(y: int) -> date:
    a = y % 19; b = y // 100; c = y % 100; d = b // 4; e = b % 4; f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30; i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(y, (h + l - 7 * m + 114) // 31, ((h + l - 7 * m + 114) % 31) + 1)


def cme_btc_expiry(y: int, m: int) -> date:
    """Last trading day of the CME BTC contract for month m: the last Friday, moved back past Good Friday, Christmas
    and New Year (the days on which the London/US calendar has closed in the sample)."""
    d = date(y, m, calendar.monthrange(y, m)[1])
    while d.weekday() != 4:
        d -= timedelta(days=1)
    hol = {_easter(y) - timedelta(days=2), date(y, 12, 25), date(y, 1, 1)}
    while d in hol or d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def cme_expiries(y0: int = 2017, y1: int = 2027) -> list[date]:
    return sorted(cme_btc_expiry(y, m) for y in range(y0, y1 + 1) for m in range(1, 13))


def front_expiry(day, expiries: Sequence[date]) -> date:
    """First expiry on or after ``day`` (Yahoo BTC=F holds the expiring contract through its last trading day)."""
    return expiries[bisect.bisect_left(expiries, _d(day))]


# ------------------------------------------------------------------------------------------------- hourly series --

def _hourly(fts, x):
    ts = np.asarray(fts, dtype=np.int64)
    return ts, np.concatenate([[0.0], np.cumsum(np.asarray(x, dtype=float))])


def window_sum(ts: np.ndarray, cs: np.ndarray, a, b):
    """(sum, count) of hourly values with timestamp in (a, b]; vectorised over a, b."""
    i = np.searchsorted(ts, np.asarray(a, dtype=np.int64), side="right")
    j = np.searchsorted(ts, np.asarray(b, dtype=np.int64), side="right")
    return cs[j] - cs[i], j - i


def value_at(ts: np.ndarray, vals: np.ndarray, t) -> np.ndarray:
    """Exact-hour value at t (nan when that hour is missing); vectorised over t."""
    t = np.atleast_1d(np.asarray(t, dtype=np.int64))
    i = np.clip(np.searchsorted(ts, t), 0, len(ts) - 1)
    return np.where(ts[i] == t, np.asarray(vals, dtype=float)[i], np.nan)


# ------------------------------------------------------------------------------------------------------- rates --

def bey(dtb3_pct: float) -> float:
    """Bond-equivalent yield (decimal) of a 91-day bill quoted at discount yield ``dtb3_pct`` (percent)."""
    dr = float(dtb3_pct) / 100.0
    return 365.0 * dr / (360.0 - 91.0 * dr)


class Rates:
    """Point-in-time DTB3: ``before(day)`` is the bond-equivalent yield of the last value dated strictly before day."""

    def __init__(self, dtb3: Optional[dict]):
        dtb3 = dtb3 or {}
        self.days = sorted(dtb3)
        self.vals = [bey(dtb3[d]) for d in self.days]

    def before(self, day) -> float:
        if not self.days:
            return 0.0
        i = bisect.bisect_left(self.days, _d(day).isoformat())
        return self.vals[i - 1] if i > 0 else self.vals[0]


# ------------------------------------------------------------------------------------------------- statistics --

def _lrv(x: np.ndarray, bw: int) -> float:
    """Bartlett long-run variance with bandwidth bw."""
    x = x - x.mean(); n = len(x)
    v = float(x @ x) / n
    for k in range(1, max(1, min(bw, n))):
        v += 2.0 * (1.0 - k / bw) * float(x[k:] @ x[:-k]) / n
    return max(v, 1e-300)


def _cbb_idx(rng, n: int, block: int, size: int) -> np.ndarray:
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(size, nb))
    return ((starts[:, :, None] + np.arange(block)[None, None, :]).reshape(size, -1)[:, :n]) % n


def _stationary_idx(rng, n: int, mean_block: float, size: int) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices (geometric block lengths with mean ``mean_block``), circular."""
    idx = np.empty((size, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, size)
    new = rng.random((size, n)) < 1.0 / mean_block
    jump = rng.integers(0, n, (size, n))
    for t in range(1, n):
        idx[:, t] = np.where(new[:, t], jump[:, t], idx[:, t - 1] + 1)
    return idx % n


def _row_sharpe(X: np.ndarray, ppy: int) -> np.ndarray:
    m = X.mean(axis=1); s = X.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(s > 0, m / s, 0.0)
    return out * math.sqrt(ppy)


def student_mean_ci(x, block: int = 3, n_boot: int = 5000, seed: int = 0) -> dict:
    """Studentized circular-block bootstrap for the mean: two-sided 95% CI and one-sided 95% lower bound.
    t* = (mean* - mean) / se*, se from a Bartlett long-run variance with bandwidth = block."""
    x = np.asarray(x, dtype=float); n = len(x); m = float(x.mean())
    out = {"mean": m, "se": None, "ci95": [None, None], "lb95": None}
    if n < 4:
        return out
    if np.allclose(x, x[0]):
        out.update(se=0.0, ci95=[m, m], lb95=m)
        return out
    se = math.sqrt(_lrv(x, block) / n)
    rng = np.random.default_rng(seed)
    idx = _cbb_idx(rng, n, block, n_boot)
    t = np.empty(n_boot)
    for b in range(n_boot):
        xb = x[idx[b]]
        t[b] = (xb.mean() - m) / math.sqrt(_lrv(xb, block) / n)
    out.update(se=se, ci95=[m - float(np.quantile(t, 0.975)) * se, m - float(np.quantile(t, 0.025)) * se],
               lb95=m - float(np.quantile(t, 0.95)) * se)
    return out


def stationary_sharpe_ci(x, mean_block: float = 14, n_boot: int = 5000, seed: int = 0, ppy: int = CRYPTO_PPY,
                         chunk: int = 500) -> dict:
    """Annualised Sharpe with stationary-bootstrap quantiles: two-sided 95% interval and one-sided 95% lower bound."""
    x = np.asarray(x, dtype=float); n = len(x)
    out = {"sharpe": _sr(x, ppy) if n > 2 else None, "ci95": [None, None], "lb95": None}
    if n < 8:
        return out
    rng = np.random.default_rng(seed); vals = []
    for s in range(0, n_boot, chunk):
        vals.append(_row_sharpe(x[_stationary_idx(rng, n, mean_block, min(chunk, n_boot - s))], ppy))
    v = np.concatenate(vals)
    out.update(ci95=[float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))], lb95=float(np.quantile(v, 0.05)))
    return out


def stationary_mean_p_less(g, mean_block: float = 7, n_boot: int = 5000, seed: int = 0, chunk: int = 500) -> Optional[float]:
    """One-sided p-value for H0: mean(g) >= 0 against mean < 0, by a centred stationary bootstrap."""
    g = np.asarray(g, dtype=float); n = len(g)
    if n < 8:
        return None
    m = float(g.mean()); rng = np.random.default_rng(seed); hits = 0
    for s in range(0, n_boot, chunk):
        mb = g[_stationary_idx(rng, n, mean_block, min(chunk, n_boot - s))].mean(axis=1)
        hits += int(np.sum(mb - m <= m))
    return (1 + hits) / (1 + n_boot)


def paired_sharpe_diff_ci(a, b, ppy: int, block: int, n_boot: int = 5000, seed: int = 0, chunk: int = 500) -> dict:
    """Observed Sharpe(a) - Sharpe(b) with a paired circular-block-bootstrap two-sided 95% interval."""
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float); n = len(a)
    obs = _sr(a, ppy) - _sr(b, ppy)
    rng = np.random.default_rng(seed); vals = []
    for s in range(0, n_boot, chunk):
        idx = _cbb_idx(rng, n, block, min(chunk, n_boot - s))
        vals.append(_row_sharpe(a[idx], ppy) - _row_sharpe(b[idx], ppy))
    v = np.concatenate(vals)
    return {"diff": float(obs), "ci95": [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]}


def cluster_mean_boot(x, clusters, n_boot: int = 5000, seed: int = 0) -> dict:
    """Mean of x with a cluster bootstrap (clusters resampled with replacement): 2.5/5/97.5% quantiles."""
    x = np.asarray(x, dtype=float); cl = np.asarray(clusters)
    keys = sorted(set(cl.tolist()))
    sums = np.array([x[cl == k].sum() for k in keys]); cnts = np.array([(cl == k).sum() for k in keys])
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(keys), size=(n_boot, len(keys)))
    m = sums[pick].sum(axis=1) / cnts[pick].sum(axis=1)
    return {"mean": float(x.mean()), "ci95": [float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))],
            "lb95": float(np.quantile(m, 0.05)), "clusters": len(keys)}


def _dsr(x, n_trials: int) -> Optional[float]:
    x = np.asarray(x, dtype=float)
    if len(x) < 8 or np.std(x) == 0:
        return None
    try:
        v = float(deflated_sharpe_ratio(x, n_trials=n_trials))
    except (ValueError, ZeroDivisionError, FloatingPointError):
        return None
    return v if math.isfinite(v) else None


def _episodes(times: Sequence, min_gap: float) -> int:
    """Greedy count of events separated by at least ``min_gap`` (same units as ``times``)."""
    n, last = 0, None
    for t in sorted(times):
        if last is None or t - last >= min_gap:
            n += 1; last = t
    return n


def _pp(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{100 * x:+.{nd}f}"


def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _months(start: str, end: str) -> list[tuple[int, int]]:
    y, m = int(start[:4]), int(start[5:7]); y1, m1 = int(end[:4]), int(end[5:7]); out = []
    while (y, m) <= (y1, m1):
        out.append((y, m)); m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _next_month(y: int, m: int) -> date:
    return date(y + (m == 12), 1 if m == 12 else m + 1, 1)


# ===================================================================================================================
# T-198: perp funding vs the front Deribit quarterly basis, non-overlapping 90-day windows
# ===================================================================================================================

def _front_quarterly(futures: Sequence[dict], t: int, min_dte_days: float):
    """(expiry_ts, F) of the nearest quarterly expiring at least ``min_dte_days`` after t whose bar closes at t."""
    cands = sorted((f for f in futures if f["expiry_ts"] - t >= min_dte_days * DAY), key=lambda f: f["expiry_ts"])
    if not cands:
        return None
    f = cands[0]
    F = value_at(np.asarray(f["close_ts"], dtype=np.int64), np.asarray(f["close"], dtype=float), t)[0]
    return (int(f["expiry_ts"]), float(F)) if math.isfinite(F) else None


def perp_vs_quarterly_basis(fts, i1, fidx, futures: Sequence[dict], start: str = "2020-01-01", window_days: int = 90,
                            min_dte_days: float = 7.0, block: int = 2, n_boot: int = 5000, seed: int = 0,
                            fee_per_leg: float = 0.0005, min_n: int = 24, min_coverage: float = 0.95) -> dict:
    """T-198. Windows of ``window_days`` from ``start`` 08:00 UTC. funding_90d = sum of interest_1h over (t, t+90d]
    (received by a short perp). basis_90d = (F/S - 1) x 365/dte x 90/365, with F the close at t of the nearest
    quarterly with at least ``min_dte_days`` to expiry (closer ones are in delivery week, where the annualised basis is
    noise) and S the Deribit index at the same 08:00 UTC hour. Pass: share(funding_90d > basis_90d) >= 50% and the
    two-sided 95% block-bootstrap CI of the mean difference above 0."""
    ts, cs = _hourly(fts, i1)
    i1a = np.asarray(i1, dtype=float)
    cap = float(np.quantile(i1a, 0.99))
    _, cs_drop = _hourly(fts, np.where(i1a > cap, 0.0, i1a))
    W = window_days * DAY

    def windows(min_dte: float, csum) -> list[dict]:
        out, t = [], _utc_ts(start, 8)
        while t + W <= ts[-1]:
            fsum, nh = window_sum(ts, csum, t, t + W)
            S = value_at(ts, fidx, t)[0]
            fq = _front_quarterly(futures, t, min_dte)
            if nh >= min_coverage * window_days * 24 and math.isfinite(S) and fq is not None:
                dte = (fq[0] - t) / DAY
                b90 = (fq[1] / S - 1.0) * window_days / dte
                out.append({"start": _day_of(t), "dte": dte, "funding_90d": float(fsum), "basis_90d": float(b90),
                            "diff": float(fsum - b90)})
            t += W
        return out

    def summary(ws: list[dict], cost: float = 0.0) -> dict:
        if not ws:
            return {"n": 0, "share": None, "mean": None, "ci95": [None, None]}
        d = np.array([w["diff"] for w in ws]) - cost
        lo, hi = _mean_ci(d, block, n_boot, seed) if len(d) >= 4 else (None, None)
        return {"n": len(d), "share": float(np.mean(d > 0)), "mean": float(d.mean()), "ci95": [lo, hi]}

    ws = windows(min_dte_days, cs)
    main = summary(ws)
    per_year = {}
    for y in sorted({w["start"][:4] for w in ws}):
        d = np.array([w["diff"] for w in ws if w["start"][:4] == y])
        per_year[y] = {"n": len(d), "share": float(np.mean(d > 0)), "mean": float(d.mean())}
    controls = {"drop_top_1pct_funding_prints": summary(windows(min_dte_days, cs_drop)),
                "taker_fees_4_legs": {**summary(ws, 4 * fee_per_leg), "fee_per_leg": fee_per_leg},
                "front_min_30_dte": summary(windows(30.0, cs)),
                "eth_replication": "not run: deribit-funding-ETH-PERPETUAL and ETH quarterly futures are not archived",
                "top_1pct_cap_interest_1h": cap}
    n = main["n"]
    crit = [(f"windows >= {min_n} (min_n)", True if n >= min_n else None),
            ("share of windows with funding_90d > basis_90d >= 50%", None if main["share"] is None else main["share"] >= 0.5),
            ("mean difference's 95% block-bootstrap CI above 0", None if main["ci95"][0] is None else main["ci95"][0] > 0)]
    v, why = _verdict(crit)
    reason = (f"{n} non-overlapping {window_days}-day windows from {start} (front quarterly with >= {min_dte_days:g} days to "
              f"expiry, F and Deribit index both at 08:00 UTC): funding_90d > basis_90d in "
              f"{sum(w['diff'] > 0 for w in ws)}/{n} = {_f(main['share'] * 100 if main['share'] is not None else None, 0)}% "
              f"(need >= 50%); mean funding_90d {_pp(np.mean([w['funding_90d'] for w in ws]) if ws else None)} pp, mean "
              f"basis_90d {_pp(np.mean([w['basis_90d'] for w in ws]) if ws else None)} pp, mean difference "
              f"{_pp(main['mean'])} pp, 95% block-bootstrap CI [{_pp(main['ci95'][0])}, {_pp(main['ci95'][1])}] pp "
              f"(need lower > 0) — {why}")
    return {"n": n, "share": main["share"], "mean_diff": main["mean"], "ci95": main["ci95"], "windows": ws,
            "per_year": per_year, "controls": controls, "criteria": crit, "verdict": v, "reason": reason,
            "sign_convention": "short perp receives +interest_1h x notional (positive funding: longs pay shorts)"}


# ===================================================================================================================
# T-258: long spot / short perp funding carry, hedged with a model-priced 10-delta 30-DTE call at DVOL
# ===================================================================================================================

def funding_call_hedged(fts, i1, deliv: dict, dvol: dict, dtb3: Optional[dict] = None, start: str = "2021-04",
                        end: str = "2026-09", tenor_days: int = 30, delta: float = 0.10, block: int = 3,
                        n_boot: int = 5000, seed: int = 0, min_n: int = 24, control_bump: float = 5.0,
                        min_coverage: float = 0.95) -> dict:
    """T-258 (MODEL-PRICED). Month m: enter on day 1 at 08:00 UTC at S0 = the Deribit delivery price (the 08:00 index
    TWAP used for option settlement). Funding = sum of interest_1h over (day 1 08:00, next month day 1 08:00]. The
    hedge is a call bought at BS(S0, K, 30/365, r=0, sigma = DVOL/100), with DVOL the previous day's close (known at
    00:00 UTC) and K the 10-delta strike. It pays max(S_T - K, 0) at the delivery price 30 days later. Everything is
    per unit of spot notional. The spot/perp leg is delta-neutral; its perp-index spread is not archived and is taken
    as 0. Pass: studentized block-bootstrap (block 3) two-sided 95% CI of the mean monthly net carry above 0, and an
    annualised Sharpe of monthly net carry in excess of DTB3 above 1."""
    ts, cs = _hourly(fts, i1)
    rates = Rates(dtb3)

    def legs(bump: float):
        rows = []
        for (y, m) in _months(start, end):
            d0 = date(y, m, 1); d1 = _next_month(y, m)
            S0 = deliv.get(d0.isoformat()); ST = deliv.get((d0 + timedelta(days=tenor_days)).isoformat())
            vol = dvol.get((d0 - timedelta(days=1)).isoformat())
            fsum, nh = window_sum(ts, cs, _utc_ts(d0, 8), _utc_ts(d1, 8))
            hours = (d1 - d0).days * 24
            if S0 is None or ST is None or vol is None or nh < min_coverage * hours:
                continue
            sigma = (float(vol) + bump) / 100.0; T = tenor_days / 365.0
            K = bs.strike_for_delta(S0, T, 0.0, sigma, delta, "call")
            prem = float(bs.price(S0, K, T, 0.0, sigma, "call")) / S0
            pay = max(float(ST) - K, 0.0) / S0
            rf = rates.before(d0) * (d1 - d0).days / 365.0
            rows.append({"month": f"{y:04d}-{m:02d}", "funding": float(fsum), "premium": prem, "payoff": pay,
                         "net": float(fsum) - prem + pay, "rf": rf, "strike_over_spot": K / S0, "sigma": sigma})
        return rows

    def summ(vals: np.ndarray, rf: np.ndarray) -> dict:
        ci = student_mean_ci(vals, block, n_boot, seed)
        return {"mean": ci["mean"], "ci95": ci["ci95"], "sharpe_excess": _sr(vals - rf, 12) if len(vals) > 2 else None}

    rows = legs(0.0)
    n = len(rows)
    if n == 0:
        crit = [(f"months >= {min_n} (min_n)", None)]
        v, why = _verdict(crit)
        return {"n": 0, "criteria": crit, "verdict": v, "reason": "MODEL-PRICED. no month has funding, delivery prices and "
                f"DVOL — {why}"}
    net = np.array([r["net"] for r in rows]); fund = np.array([r["funding"] for r in rows]); rf = np.array([r["rf"] for r in rows])
    main = summ(net, rf); unh = summ(fund, rf)
    rows_b = legs(control_bump)
    bump = summ(np.array([r["net"] for r in rows_b]), np.array([r["rf"] for r in rows_b])) if rows_b else None
    h = n // 2
    halves = {"first": {"months": f"{rows[0]['month']}..{rows[h - 1]['month']}", "mean": float(net[:h].mean())},
              "second": {"months": f"{rows[h]['month']}..{rows[-1]['month']}", "mean": float(net[h:].mean())}} if n >= 4 else None
    crit = [(f"months >= {min_n} (min_n)", True if n >= min_n else None),
            ("studentized block-bootstrap 95% CI of mean monthly net carry above 0", None if main["ci95"][0] is None else main["ci95"][0] > 0),
            ("annualised Sharpe of monthly net carry over DTB3 > 1", None if main["sharpe_excess"] is None else main["sharpe_excess"] > 1.0)]
    v, why = _verdict(crit)
    reason = (f"MODEL-PRICED (BS at DVOL, 10-delta 30-DTE call). {n} months {rows[0]['month']}..{rows[-1]['month']}: mean "
              f"funding {_pp(fund.mean())}%/month, mean call premium {_pp(np.mean([r['premium'] for r in rows]))}%, mean "
              f"payoff {_pp(np.mean([r['payoff'] for r in rows]))}%; net carry mean {_pp(main['mean'], 3)}%/month, "
              f"studentized 95% CI [{_pp(main['ci95'][0], 3)}, {_pp(main['ci95'][1], 3)}]% (need lower > 0); Sharpe of "
              f"net over DTB3 {_f(main['sharpe_excess'])} (need > 1); unhedged mean {_pp(unh['mean'], 3)}%, Sharpe "
              f"{_f(unh['sharpe_excess'])}; DVOL+5 hedge mean {_pp(bump['mean'] if bump else None, 3)}% — {why}")
    return {"n": n, "pricing": "MODEL-PRICED: Black-Scholes at DVOL/100, r=0, 30/365 years, 10-delta strike",
            "mean_net": main["mean"], "ci95": main["ci95"], "sharpe_excess": main["sharpe_excess"],
            "unhedged": unh, "dvol_plus_5": bump, "halves": halves, "months": rows, "criteria": crit, "verdict": v,
            "reason": reason}


# ===================================================================================================================
# T-303: 200-day SMA long/flat with the funding crowding state machine
# ===================================================================================================================

def funding_states(trend: np.ndarray, F: np.ndarray, p90: np.ndarray, p97: np.ndarray) -> np.ndarray:
    """State machine per day (nan where the trend is undefined): trend off -> 0; F > P97 on each of the last 3 days ->
    0.5; F <= P90 -> 1; otherwise keep the previous state (a FLAT stays FLAT until F <= P90). Before the funding
    percentiles exist the state is the trend state."""
    n = len(trend); s = np.full(n, np.nan); prev = None
    for i in range(n):
        if not np.isfinite(trend[i]):
            continue
        if trend[i] < 0.5:
            st = 0.0
        elif not np.isfinite(p90[i]):
            st = 1.0
        elif i >= 2 and all(np.isfinite(F[j]) and np.isfinite(p97[j]) and F[j] > p97[j] for j in (i, i - 1, i - 2)):
            st = 0.5
        elif np.isfinite(F[i]) and F[i] <= p90[i]:
            st = 1.0
        else:
            st = prev if prev is not None else 1.0
        s[i] = st; prev = st
    return s


def _trailing_pct(F: np.ndarray, window: int, min_obs: int, qs=(0.90, 0.97)):
    n = len(F); out = [np.full(n, np.nan) for _ in qs]
    for i in range(n):
        w = F[max(0, i - window):i]; w = w[np.isfinite(w)]
        if len(w) >= min_obs:
            for k, q in enumerate(qs):
                out[k][i] = np.quantile(w, q)
    return out


def trend_funding_filter(days: Sequence[str], closes, fts, i8, start: str = "2021-01-01", end: str = "2026-10-31",
                         sma: int = 200, pct_window: int = 365, min_pct_obs: int = 300, cost_side: float = 0.0025,
                         extra_slip: float = 0.0010, block: int = 30, n_boot: int = 5000, seed: int = 0,
                         placebo_lag: int = 30, n_trials: int = JOINT_FUNDING_TRIALS, min_n: int = 2000,
                         min_activations: int = 10, split: str = "2023-01-01") -> dict:
    """T-303. Day i: decision at 00:00 UTC after close_i. Trend = close_i > SMA200. F_i = mean interest_8h over records
    in (decision - 7d, decision]. P90/P97 come from F over the previous 365 days (strictly trailing). Execution is at
    the close one day after the decision, so state_i earns the return from close_{i+1} to close_{i+2}. The unfiltered
    rule gets the same lag. Costs: 25 bp per side on every position change, plus 10 bp on changes that the unfiltered
    rule does not make. Pass: Sharpe difference > 0 with a paired circular-block (30-day) bootstrap 95% interval
    excluding 0; the placebo (F lagged 30 days, percentiles recomputed) interval includes 0; DSR of the daily
    filtered-minus-unfiltered returns > 0.95 at the joint funding-trial count; at least 10 funding-driven activations
    (fewer = inconclusive)."""
    c = np.asarray(closes, dtype=float); n = len(c)
    ts, cs = _hourly(fts, i8)
    dec = np.array([_utc_ts(d) + DAY for d in days], dtype=np.int64)
    s8, cnt = window_sum(ts, cs, dec - 7 * DAY, dec)
    F = np.where(cnt >= 151, s8 / np.maximum(cnt, 1), np.nan)
    trend = np.full(n, np.nan)
    if n >= sma:
        cc = np.concatenate([[0.0], np.cumsum(c)])
        m = (cc[sma:] - cc[:-sma]) / sma
        trend[sma - 1:] = (c[sma - 1:] > m).astype(float)

    def run(Fx: np.ndarray):
        p90, p97 = _trailing_pct(Fx, pct_window, min_pct_obs)
        st = funding_states(trend, Fx, p90, p97)
        pos_f = np.full(n, np.nan); pos_b = np.full(n, np.nan)
        pos_f[2:] = st[:-2]; pos_b[2:] = trend[:-2]
        r = np.full(n, np.nan); r[1:] = c[1:] / c[:-1] - 1
        df = np.abs(np.diff(np.nan_to_num(pos_f), prepend=0.0)); db = np.abs(np.diff(np.nan_to_num(pos_b), prepend=0.0))
        extra = np.where((df > 0) & (db == 0), extra_slip * df, 0.0)
        rf_ = pos_f * r - cost_side * df - extra
        rb_ = pos_b * r - cost_side * db
        return rf_, rb_, pos_f, pos_b

    ds = np.array(days)
    rf_, rb_, pf, pb = run(F)
    ev = (ds >= start) & (ds <= end) & np.isfinite(rf_) & np.isfinite(rb_)
    a, b = rf_[ev], rb_[ev]; N = int(ev.sum())
    if N < 3 * block:
        crit = [(f"days >= {min_n} (min_n)", None)]
        v, why = _verdict(crit)
        return {"n": N, "criteria": crit, "verdict": v, "reason": f"only {N} evaluable days — {why}"}
    main = paired_sharpe_diff_ci(a, b, CRYPTO_PPY, block, n_boot, seed)
    F_lag = np.full(n, np.nan); F_lag[placebo_lag:] = F[:-placebo_lag]
    pa, pbb, _, _ = run(F_lag)
    evp = ev & np.isfinite(pa) & np.isfinite(pbb)
    plc = paired_sharpe_diff_ci(pa[evp], pbb[evp], CRYPTO_PPY, block, n_boot, seed)
    dsr = _dsr(a - b, n_trials)
    diffmask = (pf[ev] != pb[ev]).astype(int)
    acts = int(np.sum(np.diff(np.concatenate([[0], diffmask])) == 1))
    halves = {}
    for nm, msk in (("2021-2022", ds[ev] < split), ("2023-2026", ds[ev] >= split)):
        if msk.sum() > 10:
            halves[nm] = {"sharpe_filtered": _sr(a[msk], CRYPTO_PPY), "sharpe_unfiltered": _sr(b[msk], CRYPTO_PPY),
                          "diff": _sr(a[msk], CRYPTO_PPY) - _sr(b[msk], CRYPTO_PPY)}
    crit = [(f"days >= {min_n} (min_n)", True if N >= min_n else None),
            ("Sharpe difference > 0 with paired block-bootstrap 95% interval excluding 0", main["diff"] > 0 and main["ci95"][0] > 0),
            ("placebo (F lagged 30 days) 95% interval includes 0", plc["ci95"][0] <= 0 <= plc["ci95"][1]),
            (f"DSR of daily filtered-minus-unfiltered returns > 0.95 (n_trials = {n_trials})", dsr is not None and dsr > 0.95),
            (f"at least {min_activations} funding-driven activations", True if acts >= min_activations else None)]
    v, why = _verdict(crit)
    reason = (f"{N} days {ds[ev][0]}..{ds[ev][-1]}: Sharpe filtered {_f(_sr(a, CRYPTO_PPY))} vs unfiltered "
              f"{_f(_sr(b, CRYPTO_PPY))}, difference {_f(main['diff'], 3)} with 95% interval [{_f(main['ci95'][0], 3)}, "
              f"{_f(main['ci95'][1], 3)}] (need > 0 and excluding 0); placebo difference {_f(plc['diff'], 3)} interval "
              f"[{_f(plc['ci95'][0], 3)}, {_f(plc['ci95'][1], 3)}] (need to include 0); DSR {_f(dsr, 3)} (need > 0.95); "
              f"{acts} funding-driven activations (need >= {min_activations}) — {why}")
    return {"n": N, "sharpe_filtered": _sr(a, CRYPTO_PPY), "sharpe_unfiltered": _sr(b, CRYPTO_PPY), "diff": main["diff"],
            "ci95": main["ci95"], "placebo": plc, "dsr": dsr, "dsr_n_trials": n_trials, "activations": acts,
            "days_half": int(np.sum(pf[ev] == 0.5)), "days_flat_by_funding": int(np.sum((pf[ev] == 0) & (pb[ev] == 1))),
            "mdd_filtered": _mdd(a), "mdd_unfiltered": _mdd(b), "halves": halves, "criteria": crit, "verdict": v,
            "reason": reason}


# ===================================================================================================================
# CME BTC=F synchronous basis (shared by T-329, T-362, T-364)
# ===================================================================================================================

def cme_daily_basis(days: Sequence[str], F, S, std_bar, expiries: Sequence[date], roll_trading_days: Optional[int] = None,
                    roll_calendar_days: Optional[int] = None) -> dict:
    """Annualised basis b = (F/S - 1) x 365/dte per BTC=F bar, with dte in calendar days to the front expiry from the
    CME calendar. ok = standard session, finite F and S, not the expiry day, and outside the roll window (trading days
    to expiry > roll_trading_days and/or calendar days to expiry > roll_calendar_days)."""
    F = np.asarray(F, dtype=float); S = np.asarray(S, dtype=float); std = np.asarray(std_bar, dtype=bool); n = len(days)
    exp = [front_expiry(d, expiries) for d in days]
    dte = np.array([(e - _d(d)).days for d, e in zip(days, exp)], dtype=float)
    ntd = np.array([bisect.bisect_left(days, e.isoformat()) - i for i, e in enumerate(exp)], dtype=float)
    ok = std & np.isfinite(F) & np.isfinite(S) & (dte > 0)
    if roll_trading_days is not None:
        ok &= ntd > roll_trading_days
    if roll_calendar_days is not None:
        ok &= dte > roll_calendar_days
    with np.errstate(divide="ignore", invalid="ignore"):
        b = np.where(ok, (F / S - 1.0) * 365.0 / np.maximum(dte, 1.0), np.nan)
    return {"expiry": exp, "dte": dte, "ntd": ntd, "ok": ok, "basis": b}


# ===================================================================================================================
# T-329: 5-day long-spot / short-futures trade after a +2 sd annualised CME basis spike
# ===================================================================================================================

def _basis_trades(days, F, S, ok, exp, sig: np.ndarray, hold: int, cost_rt: float):
    n = len(days); trades = []; last_exit = -1
    for i in np.flatnonzero(sig):
        if i < last_exit:
            continue
        e, x = i + 1, i + 1 + hold
        if x >= n or not (ok[e] and ok[x]) or not (exp[i] == exp[e] == exp[x]):
            continue
        net = ((F[e] - S[e]) - (F[x] - S[x])) / S[e] - cost_rt
        trades.append({"signal": days[i], "entry": days[e], "exit": days[x], "net": float(net),
                       "basis_change": float(((F[x] - S[x]) - (F[e] - S[e])) / S[e]),
                       "decay_implied_change": float((F[e] - S[e]) / S[e] * ((_d(exp[e]) - _d(days[x])).days /
                                                                             max(1, (_d(exp[e]) - _d(days[e])).days) - 1.0)),
                       "hold_days": (_d(days[x]) - _d(days[e])).days})
        last_exit = x
    return trades


def cme_basis_spike(days: Sequence[str], F, S, std_bar, expiries: Sequence[date], dtb3: Optional[dict] = None,
                    start: str = "2018-01-01", end: str = "2026-09-30", z_window: int = 60, z_thr: float = 2.0,
                    hold: int = 5, cost_rt: float = 0.002, roll_trading_days: int = 5, n_boot: int = 5000, seed: int = 0,
                    n_trials: int = 5, split: str = "2024-01-01", min_n: int = 40, shift_block: int = 20,
                    financing_spread: float = 0.015) -> dict:
    """T-329. Signal on settle day i: the annualised basis is more than z_thr sd above the mean of the previous z_window
    valid observations. Entry at the next settle (i+1), exit 5 trading days later. Net per unit spot = (B_entry -
    B_exit)/S_entry - 20 bp, with B = F - S in dollars. Trades never overlap and never span a roll; observations in the
    5 trading days before expiry are dropped. Pass: one-sided 95% lower bound of the mean net return (month-clustered
    bootstrap) > 0, positive means before and after 2024-01, DSR > 0.95 over 5 variants, and the claim window from
    ``start`` covered by synchronous spot."""
    F = np.asarray(F, dtype=float); S = np.asarray(S, dtype=float); ds = list(days); n = len(ds)
    tab = cme_daily_basis(ds, F, S, std_bar, expiries, roll_trading_days=roll_trading_days)
    ok, b, exp = tab["ok"], tab["basis"], tab["expiry"]
    okidx = np.flatnonzero(ok)
    z = np.full(n, np.nan)
    for k in range(z_window, len(okidx)):
        w = b[okidx[k - z_window:k]]; sd = w.std(ddof=1)
        if sd > 0:
            z[okidx[k]] = (b[okidx[k]] - w.mean()) / sd
    dsa = np.array(ds)
    inwin = (dsa >= start) & (dsa <= end)
    sig = np.isfinite(z) & (z > z_thr) & inwin
    trades = _basis_trades(ds, F, S, ok, exp, sig, hold, cost_rt)
    nt = len(trades)
    first_sync = ds[okidx[0]] if len(okidx) else None
    covered = first_sync is not None and first_sync <= (_d(start) + timedelta(days=31)).isoformat()
    if nt == 0:
        crit = [(f"trades >= {min_n} (min_n)", None), ("one-sided 95% lower bound of mean net return > 0", None)]
        v, why = _verdict(crit)
        return {"n": 0, "criteria": crit, "verdict": v, "reason": f"no signal produced a valid trade — {why}"}
    net = np.array([t["net"] for t in trades])
    boot = cluster_mean_boot(net, [t["entry"][:7] for t in trades], n_boot, seed)
    pre = net[np.array([t["entry"] < split for t in trades])]; post = net[np.array([t["entry"] >= split for t in trades])]
    dsr = _dsr(net, n_trials)
    # block-shifted signal null: shift the signal by multiples of 20 trading days (circular) and re-simulate
    shifted = []
    for k in range(1, n // shift_block):
        sg = np.roll(np.isfinite(z) & (z > z_thr), k * shift_block) & inwin
        tr = _basis_trades(ds, F, S, ok, exp, sg, hold, cost_rt)
        if tr:
            shifted.append(np.mean([t["net"] for t in tr]))
    p_shift = (1 + sum(m >= net.mean() for m in shifted)) / (1 + len(shifted)) if shifted else None
    rates = Rates(dtb3)
    fin = np.array([t["net"] - (rates.before(t["entry"]) + financing_spread) * t["hold_days"] / 365.0 for t in trades])
    same_sign = None if len(pre) == 0 or len(post) == 0 else bool(pre.mean() > 0 and post.mean() > 0)
    crit = [(f"trades >= {min_n} (min_n)", True if nt >= min_n else None),
            ("one-sided 95% lower bound of mean net return per trade > 0 (month-clustered bootstrap)", boot["lb95"] > 0),
            ("positive mean before and after 2024-01", same_sign),
            (f"DSR > 0.95 (n_trials = {n_trials})", dsr is not None and dsr > 0.95),
            (f"claim window from {start[:7]} covered by settle-synchronous spot", True if covered else None)]
    v, why = _verdict(crit)
    reason = (f"{nt} trades {trades[0]['entry']}..{trades[-1]['entry']} (synchronous spot from {first_sync}; z > {z_thr:g} "
              f"over the trailing {z_window} settles, enter next settle, hold {hold} trading days, {cost_rt * 1e4:.0f} bp "
              f"round trip): mean net {_pp(net.mean(), 3)}%, one-sided 95% lower bound {_pp(boot['lb95'], 3)}% (need > 0); "
              f"pre-2024 mean {_pp(pre.mean() if len(pre) else None, 3)}% (n={len(pre)}), post {_pp(post.mean() if len(post) else None, 3)}% "
              f"(n={len(post)}) (need both > 0); DSR {_f(dsr, 3)} (need > 0.95); window from {start[:7]} covered: "
              f"{'yes' if covered else 'no, no settle-synchronous spot before ' + str(first_sync)} — {why}")
    return {"n": nt, "mean_net": float(net.mean()), "boot": boot, "pre_2024": {"n": len(pre), "mean": float(pre.mean()) if len(pre) else None},
            "post_2024": {"n": len(post), "mean": float(post.mean()) if len(post) else None}, "dsr": dsr,
            "p_block_shifted_signal": p_shift, "mean_basis_change": float(np.mean([t["basis_change"] for t in trades])),
            "mean_decay_implied_change": float(np.mean([t["decay_implied_change"] for t in trades])),
            "mean_net_after_financing_dtb3_plus_150bp": float(fin.mean()), "first_synchronous_day": first_sync,
            "signals": int(sig.sum()), "trades": trades, "criteria": crit, "verdict": v, "reason": reason}


# ===================================================================================================================
# T-362: hold-to-expiry CME cash-and-carry when the synchronous annualised basis > DTB3 + 3%
# ===================================================================================================================

def cme_contract_table(days: Sequence[str], F, std_bar, spot_at: Callable[[int], float], expiries: Sequence[date],
                       dtb3: Optional[dict] = None, first: str = "2018-01", last: str = "2026-09") -> list[dict]:
    """One row per contract month: decision on the first standard session after the previous expiry; F0 = BTC=F
    settle, S0 = spot at the 15:00 CT settle; F_final = the expiry-day BTC=F print (the final settlement); S_exit =
    the BRR-window proxy, the mean of spot at 15:00 and 16:00 London on expiry day (falls back to 16:00 alone);
    S_exit_16 = spot at 16:00 London (the trial's literal proxy); rf = DTB3 (bond-equivalent) known before the
    decision."""
    F = np.asarray(F, dtype=float); std = np.asarray(std_bar, dtype=bool); rates = Rates(dtb3); out = []
    pos = {d: i for i, d in enumerate(days)}
    for (y, m) in _months(first, last):
        e = cme_btc_expiry(y, m); py, pm = (y - 1, 12) if m == 1 else (y, m - 1); prev = cme_btc_expiry(py, pm)
        j = bisect.bisect_right(days, prev.isoformat())
        while j < len(days) and not std[j]:
            j += 1
        if j >= len(days) or days[j] >= e.isoformat():
            continue
        dday = days[j]
        k = pos.get(e.isoformat())
        s16 = float(spot_at(brr_ts(e))); s15 = float(spot_at(brr_ts(e) - HOUR))
        out.append({"contract": f"{y:04d}-{m:02d}", "expiry": e.isoformat(), "decision": dday, "F0": float(F[j]),
                    "S0": float(spot_at(cme_settle_ts(dday))), "F_final": float(F[k]) if k is not None else float("nan"),
                    "S_exit": 0.5 * (s15 + s16) if math.isfinite(s15) else s16, "S_exit_16": s16, "rf": rates.before(dday)})
    return out


def cme_cash_and_carry(contracts: Sequence[dict], h: float = 0.03, test: tuple = ("2022-01", "2026-09"),
                       fit: tuple = ("2018-01", "2021-12"), margin: float = 0.40, cost_rt: float = 0.002, block: int = 3,
                       n_boot: int = 5000, seed: int = 0, n_trials: int = 10, min_n: int = 50,
                       grid: Sequence[float] = (0.0, 0.03, 0.05, 0.10)) -> dict:
    """T-362. Enter when b = (F0/S0 - 1) x 365/d > rf + h, with d = calendar days from decision to expiry. Buy spot,
    short the same BTC of futures, hold to final settlement. Capital = S0 + 40% x F0, with the margin earning T-bills.
    The P&L is (F0 - S0) - (F_final - S_exit) - 20 bp x S0. The F_final - S_exit term is the settlement slippage of
    the BRR-window proxy (``S_exit``) and is 0 when the expiry print is missing. A control re-runs the test with the
    trial's literal proxy, the 16:00 London point (``S_exit_16``). Excess over DTB3 on all capital = P&L - S0 x rf x d/365
    (margin interest cancels). Annualised: excess / capital x 365/d. Months not entered count as 0. Pass (test
    window): one-sided 95% studentized block-bootstrap (block 3) lower bound of the mean > 0, and DSR > 0.95 with
    n_trials = 10."""

    def run(hh: float, rows: Sequence[dict], exit_key: str = "S_exit"):
        ann, per, entered = [], [], []
        for c in rows:
            d = (_d(c["expiry"]) - _d(c["decision"])).days
            b = (c["F0"] / c["S0"] - 1.0) * 365.0 / d
            sx = c.get(exit_key, float("nan"))
            if b > c["rf"] + hh:
                slip = c["F_final"] - sx if math.isfinite(c["F_final"]) and math.isfinite(sx) else 0.0
                cap = c["S0"] + margin * c["F0"]
                ex = (c["F0"] - c["S0"]) - slip - cost_rt * c["S0"] - c["S0"] * c["rf"] * d / 365.0
                per.append(ex / cap); ann.append(ex / cap * 365.0 / d); entered.append(True)
            else:
                per.append(0.0); ann.append(0.0); entered.append(False)
        return np.array(ann), np.array(per), np.array(entered, dtype=bool)

    cov = [c for c in contracts if math.isfinite(c["S0"]) and math.isfinite(c["F0"]) and c["S0"] > 0]
    tst = [c for c in cov if test[0] <= c["contract"] <= test[1]]
    fitc = [c for c in cov if fit[0] <= c["contract"] <= fit[1]]
    n = len(tst)
    if n < 4:
        crit = [(f"test-window contract-months >= {min_n}", None)]
        v, why = _verdict(crit)
        return {"n": n, "criteria": crit, "verdict": v, "reason": f"only {n} test-window contracts with synchronous prices — {why}"}
    ann, per, ent = run(h, tst)
    ci = student_mean_ci(ann, block, n_boot, seed)
    dsr = _dsr(per, n_trials)
    slips = [(c["F_final"] - c["S_exit"]) / c["S0"] for c in tst if math.isfinite(c["F_final"]) and math.isfinite(c["S_exit"])]
    lit = None
    if any("S_exit_16" in c for c in tst):
        la, lp, _ = run(h, tst, "S_exit_16"); lci = student_mean_ci(la, block, n_boot, seed)
        lsl = [(c["F_final"] - c["S_exit_16"]) / c["S0"] for c in tst
               if math.isfinite(c["F_final"]) and math.isfinite(c.get("S_exit_16", float("nan")))]
        lit = {"mean_ann_excess": float(la.mean()), "lb95": lci["lb95"], "dsr": _dsr(lp, n_trials),
               "mean_slippage": float(np.mean(lsl)) if lsl else None,
               "note": "control: spot sold at the 16:00 London index, the trial's literal BRR proxy"}
    fit_rep = None
    if fitc:
        fa, _, fe = run(h, fitc)
        best = max(grid, key=lambda g: float(run(g, fitc)[0].mean()))
        fit_rep = {"n": len(fitc), "first": fitc[0]["contract"], "mean_ann_excess": float(fa.mean()), "entered": int(fe.sum()),
                   "walk_forward_h": best, "test_mean_at_walk_forward_h": float(run(best, tst)[0].mean())}
    reg = {}
    for nm, lo, hi in (("pre_FTX", "0000", "2022-10"), ("post_FTX", "2022-11", "9999"), ("pre_ETF", "0000", "2023-12"), ("post_ETF", "2024-01", "9999")):
        msk = np.array([lo <= c["contract"] <= hi for c in tst])
        if msk.any():
            reg[nm] = {"n": int(msk.sum()), "mean_ann_excess": float(ann[msk].mean())}
    crit = [(f"test-window contract-months >= {min_n}", True if n >= min_n else None),
            ("one-sided 95% studentized block-bootstrap lower bound of mean annualised excess > 0", ci["lb95"] is not None and ci["lb95"] > 0),
            (f"DSR > 0.95 (n_trials = {n_trials})", dsr is not None and dsr > 0.95)]
    v, why = _verdict(crit)
    reason = (f"{n} test contract-months {tst[0]['contract']}..{tst[-1]['contract']} (h = DTB3 + {h * 100:g}%, entered "
              f"{int(ent.sum())}): mean annualised excess over DTB3 on capital {_pp(ann.mean())}%, one-sided 95% lower bound "
              f"{_pp(ci['lb95'])}% (need > 0); DSR {_f(dsr, 3)} (need > 0.95); mean settlement slippage "
              f"{_pp(np.mean(slips) if slips else None, 3)}% of spot vs the BRR-window proxy (mean index 15:00/16:00 London); "
              f"with the trial's literal 16:00-London exit instead: mean {_pp(lit['mean_ann_excess'] if lit else None)}%, lower "
              f"bound {_pp(lit['lb95'] if lit else None)}%, DSR {_f(lit['dsr'] if lit else None, 3)}; fit window covered from "
              f"{fit_rep['first'] if fit_rep else 'n/a'} (no synchronous spot before 2019-05) with mean "
              f"{_pp(fit_rep['mean_ann_excess'] if fit_rep else None)}% over {fit_rep['n'] if fit_rep else 0} contracts — {why}")
    return {"n": n, "mean_ann_excess": float(ann.mean()), "ci": ci, "dsr": dsr, "entered": int(ent.sum()),
            "fit": fit_rep, "regimes": reg, "mean_slippage": float(np.mean(slips)) if slips else None, "literal_16_london_exit_control": lit,
            "uncovered_contracts": [c["contract"] for c in contracts if c not in cov],
            "contracts": [{**c, "ann_excess": float(a)} for c, a in zip(tst, ann)], "criteria": crit, "verdict": v,
            "reason": reason}


# ===================================================================================================================
# T-363: long BTC / short BTC-PERPETUAL while trailing 7-day annualised funding > DTB3 + 4%
# ===================================================================================================================

def perp_funding_carry(fts, i1, dtb3: Optional[dict] = None, threshold: float = 0.04, test: tuple = ("2023-01-01", "2026-09-30"),
                       fit: tuple = ("2020-01-01", "2022-12-31"), cost_side: float = 0.0010, legs: int = 2,
                       damper: float = DERIBIT_DAMPER, mean_block: float = 14, n_boot: int = 5000, seed: int = 0,
                       n_trials: int = 12, min_days: int = 250, grid: Sequence[float] = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)) -> dict:
    """T-363. Daily check at 00:00 UTC: f7 = sum of interest_1h over the previous 168 hours x 8760/168. Hold (long
    spot, short the perp, 1x, BTC collateral) for the next 24 hours iff f7 > DTB3 + threshold. The daily excess return
    in position is funding over the day - DTB3/365 + perp-spread mark-to-market. Each entry and exit pays 10 bp per
    leg (two legs). Out of position, capital sits in bills, so excess = 0.

    The perp mark/trade history is not archived. The premium p = (perp - index)/index is reconstructed from Deribit's
    funding formula, p = f8 + u with f8 = 8 x interest_1h and |u| <= damper, giving a central path (u = 0; its daily
    changes are the mark-to-market). Pessimistic adds an adverse damper at every entry and exit; optimistic adds a
    favourable one. A Sharpe criterion passes if it passes under the pessimistic bound and fails if it fails under the
    optimistic bound; otherwise it is not decided (None)."""
    ts, cs = _hourly(fts, i1)
    i1a = np.asarray(i1, dtype=float); rates = Rates(dtb3)
    d0 = _d(_day_of(int(ts[0]) + 8 * DAY)); d1 = _d(_day_of(int(ts[-1]) - DAY))
    days = [(d0 + timedelta(days=k)).isoformat() for k in range((d1 - d0).days + 1)]
    t = np.array([_utc_ts(d) for d in days], dtype=np.int64)
    s7, c7 = window_sum(ts, cs, t - 168 * HOUR, t)
    f7 = np.where(c7 >= 160, s7 * 8760.0 / 168.0, np.nan)
    carry, cc = window_sum(ts, cs, t, t + DAY)
    carry = np.where(cc >= 20, carry, np.nan)
    f8 = 8.0 * value_at(ts, i1a, t)
    f8 = np.where(np.isfinite(f8), f8, 0.0)
    f8_next = np.concatenate([f8[1:], [f8[-1]]])
    rf = np.array([rates.before(d) for d in days])

    def series(thr: float, exit_thr: Optional[float] = None, nlegs: int = legs):
        live = np.isfinite(f7) & np.isfinite(carry)
        if exit_thr is None:                                  # the claim: in position only while f7 > DTB3 + thr
            inpos = live & (f7 > rf + thr)
        else:                                                 # library rule: enter > DTB3 + thr, exit < DTB3 + exit_thr
            inpos = np.zeros(len(f7), dtype=bool); held = False
            for k in range(len(f7)):
                if not live[k]:
                    held = False
                elif held:
                    held = f7[k] >= rf[k] + exit_thr
                else:
                    held = f7[k] > rf[k] + thr
                inpos[k] = held
        sw = np.abs(np.diff(inpos.astype(float), prepend=0.0)) > 0
        base = np.where(inpos, np.nan_to_num(carry) - rf / 365.0, 0.0) - sw * nlegs * cost_side
        mtm = np.where(inpos, f8 - f8_next, 0.0)
        cen = base + mtm
        return {"inpos": inpos, "funding_only": base, "central": cen, "pess": cen - sw * damper, "opt": cen + sw * damper,
                "switches": int(sw.sum())}

    da = np.array(days)
    tm = (da >= test[0]) & (da <= test[1]); fm = (da >= fit[0]) & (da <= fit[1])
    S = series(threshold)
    ndays = int(tm.sum()); inpos_days = int(S["inpos"][tm].sum())
    stats = {k: stationary_sharpe_ci(S[k][tm], mean_block, n_boot, seed) for k in ("funding_only", "central", "pess", "opt")}
    dsr = {k: _dsr(S[k][tm], n_trials) for k in ("central", "pess", "opt")}

    def bounded(pess_ok: Optional[bool], opt_ok: Optional[bool]) -> Optional[bool]:
        if pess_ok:
            return True
        if opt_ok is False:
            return False
        return None

    sh_ok = bounded(stats["pess"]["sharpe"] is not None and stats["pess"]["sharpe"] > 1.0,
                    stats["opt"]["sharpe"] is not None and stats["opt"]["sharpe"] > 1.0)
    lb_ok = bounded(stats["pess"]["lb95"] is not None and stats["pess"]["lb95"] > 0.3,
                    stats["opt"]["lb95"] is not None and stats["opt"]["lb95"] > 0.3)
    ds_ok = bounded(dsr["pess"] is not None and dsr["pess"] > 0.95, dsr["opt"] is not None and dsr["opt"] > 0.95)
    wf = {g: _sr(series(g)["central"][fm], CRYPTO_PPY) for g in grid} if fm.sum() > 30 else {}
    best = max(wf, key=wf.get) if wf else None
    years = {}
    for y in sorted({d[:4] for d in days}):
        msk = np.array([d[:4] == y for d in days])
        years[y] = {"sharpe_central": _sr(S["central"][msk], CRYPTO_PPY), "days_in_position": int(S["inpos"][msk].sum())}
    hy = series(threshold, 0.0)
    hysteresis = {"rule": "enter when f7 > DTB3 + threshold, exit when f7 < DTB3 (library rule; control only)",
                  "days_in_position": int(hy["inpos"][tm].sum()), "switches": hy["switches"],
                  "sharpe_central": _sr(hy["central"][tm], CRYPTO_PPY), "sharpe_pessimistic": _sr(hy["pess"][tm], CRYPTO_PPY),
                  "sharpe_funding_only": _sr(hy["funding_only"][tm], CRYPTO_PPY)}
    one = series(threshold, None, 1)
    cost_alt = {"reading": f"{cost_side * 1e4:g} bp per side for the whole position (not per leg)",
                **{k: _sr(one[k][tm], CRYPTO_PPY) for k in ("pess", "central", "opt")}}
    ar1 = float(np.corrcoef(i1a[1:], i1a[:-1])[0, 1]) if len(i1a) > 3 else None
    crit = [(f"in-position test days >= {min_days}", True if inpos_days >= min_days else None),
            ("test Sharpe > 1.0 after costs and perp-spot spread (spread-bounded)", sh_ok),
            ("stationary-bootstrap one-sided 95% lower bound of Sharpe > 0.3 (spread-bounded)", lb_ok),
            (f"DSR > 0.95 with n_trials = {n_trials} (spread-bounded)", ds_ok)]
    v, why = _verdict(crit)
    reason = (f"test {test[0]}..{test[1]}, {ndays} days, {inpos_days} in position, {S['switches']} switches overall "
              f"(threshold DTB3 + {threshold * 100:g}%, 10 bp per side per leg): Sharpe of daily excess, pessimistic / central / "
              f"optimistic spread = {_f(stats['pess']['sharpe'])} / {_f(stats['central']['sharpe'])} / {_f(stats['opt']['sharpe'])} "
              f"(need > 1; funding-only {_f(stats['funding_only']['sharpe'])}); one-sided 95% lower bound "
              f"{_f(stats['pess']['lb95'])} / {_f(stats['central']['lb95'])} / {_f(stats['opt']['lb95'])} (need > 0.3); DSR "
              f"{_f(dsr['pess'], 3)} / {_f(dsr['central'], 3)} / {_f(dsr['opt'], 3)} (need > 0.95); perp mark history not "
              f"archived, spread reconstructed from funding with |u| <= {damper * 100:g}%; cost read as {cost_side * 1e4:g} bp "
              f"per side for the whole position instead of per leg: Sharpe {_f(cost_alt['pess'])} / {_f(cost_alt['central'])} / "
              f"{_f(cost_alt['opt'])}; hysteresis control (exit < DTB3) central Sharpe {_f(hysteresis['sharpe_central'])} — {why}")
    return {"n": ndays, "days_in_position": inpos_days, "sharpe": {k: stats[k]["sharpe"] for k in stats},
            "lb95": {k: stats[k]["lb95"] for k in stats}, "ci95": {k: stats[k]["ci95"] for k in stats}, "dsr": dsr,
            "mdd_central": _mdd(S["central"][tm]) if ndays else None, "ar1_hourly_funding": ar1,
            "mean_daily_excess_central": float(S["central"][tm].mean()) if ndays else None,
            "walk_forward": {"fit_sharpe_by_threshold": wf, "chosen_threshold": best,
                             "test_sharpe_at_chosen": _sr(series(best)["central"][tm], CRYPTO_PPY) if best is not None else None},
            "by_year": years, "hysteresis_control": hysteresis, "cost_reading_control": cost_alt, "criteria": crit,
            "verdict": v, "reason": reason,
            "notes": "Deribit-specific (not US-accessible); Kraken/CDE replication and the ETH variant need bundles not archived"}


# ===================================================================================================================
# T-364: top-decile synchronous basis weeks and the forward 30-day BTC max drawdown
# ===================================================================================================================

def weekly_first(days: Sequence[str], ok) -> list[int]:
    """Index of the first ok day of each ISO week."""
    seen, out = set(), []
    for i, d in enumerate(days):
        if not ok[i]:
            continue
        k = _d(d).isocalendar()[:2]
        if k not in seen:
            seen.add(k); out.append(i)
    return out


def _fwd_mdd(px_pos: dict, px: np.ndarray, day: str, horizon: int) -> Optional[float]:
    i = px_pos.get(day)
    if i is None or i + horizon >= len(px):
        return None
    p = px[i:i + horizon + 1]
    return float((p / np.maximum.accumulate(p) - 1.0).min())


def basis_crash_predictor(obs_days: Sequence[str], obs_basis, px_days: Sequence[str], px_close, dtb3: Optional[dict] = None,
                          start: str = "2018-12-01", end: str = "2026-09-30", trailing: int = 52, horizon: int = 30,
                          block: int = 8, n_perm: int = 5000, seed: int = 0, min_n: int = 350, split: str = "2022-01-01",
                          min_episodes: int = 8, gap_pp: float = 10.0, switch_cost: float = 0.0010, n_trials: int = 4) -> dict:
    """T-364. Weekly basis observations (first valid settle of each ISO week). The state comes from the previous 52
    weekly observations only: top decile if b > their 90th percentile, bottom half if b < their median. Forward
    30-day max drawdown from the daily close on the observation day (the first close after the 15:00 CT signal)
    through 30 days later. Depth = -MDD in percentage points. Pass: mean depth(top) - mean depth(bottom half) >= 10
    pp, block-permutation (8-week blocks) p < 0.05, a positive gap in both halves, >= 8 non-overlapping top-decile
    episodes (fewer = insufficient events), >= 350 weeks, and the claim window from ``start`` covered."""
    ob = np.asarray(obs_basis, dtype=float); px = np.asarray(px_close, dtype=float)
    pos = {d: i for i, d in enumerate(px_days)}
    lab, dep, wk = [], [], []
    for k in range(trailing, len(obs_days)):
        d = obs_days[k]
        if d < start or d > end:
            continue
        prev = ob[k - trailing:k]
        if not np.all(np.isfinite(prev)) or not math.isfinite(ob[k]):
            continue
        m = _fwd_mdd(pos, px, d, horizon)
        if m is None:
            continue
        lab.append(2 if ob[k] > np.quantile(prev, 0.9) else (0 if ob[k] < np.median(prev) else 1))
        dep.append(-100.0 * m); wk.append(d)
    lab = np.array(lab); dep = np.array(dep); n = len(lab)
    covered = bool(wk) and wk[0] <= (_d(start) + timedelta(days=14)).isoformat()

    def gap(L: np.ndarray, D: np.ndarray) -> Optional[float]:
        if (L == 2).sum() == 0 or (L == 0).sum() == 0:
            return None
        return float(D[L == 2].mean() - D[L == 0].mean())

    g = gap(lab, dep) if n else None
    p = None
    if g is not None:
        rng = np.random.default_rng(seed); nb = math.ceil(n / block); hits = 0
        blocks = [lab[i * block:(i + 1) * block] for i in range(nb)]
        for _ in range(n_perm):
            Lp = np.concatenate([blocks[j] for j in rng.permutation(nb)])
            gp = gap(Lp, dep)
            hits += int(gp is not None and gp >= g)
        p = (1 + hits) / (1 + n_perm)
    wka = np.array(wk)
    halves = {}
    for nm, msk in (("first", wka < split), ("second", wka >= split)):
        halves[nm] = {"weeks": int(msk.sum()), "top": int((lab[msk] == 2).sum()) if n else 0,
                      "gap": gap(lab[msk], dep[msk]) if n and msk.any() else None}
    hs = [halves["first"]["gap"], halves["second"]["gap"]]
    same = None if any(x is None for x in hs) else bool(hs[0] > 0 and hs[1] > 0)
    eps = _episodes([_d(w).toordinal() for w, l_ in zip(wk, lab) if l_ == 2], horizon)
    # timing rule: flat (bills) for 30 days after a top-decile week, 10 bp per switch
    timing = None
    if n:
        r = np.full(len(px), np.nan); r[1:] = px[1:] / px[:-1] - 1
        flat = np.zeros(len(px), dtype=bool)
        for w, l_ in zip(wk, lab):
            if l_ == 2:
                i = pos[w]; flat[i + 1:i + 1 + horizon] = True
        rates = Rates(dtb3)
        pdays = np.array(px_days)
        msk = (pdays >= wk[0]) & (pdays <= end) & np.isfinite(r)
        cash = np.array([rates.before(d) / 365.0 for d in pdays[msk]])
        sw = np.abs(np.diff(flat.astype(float), prepend=0.0))[msk]
        rr = np.where(flat[msk], cash, r[msk]) - switch_cost * sw
        timing = {"sharpe": _sr(rr, CRYPTO_PPY), "buy_hold_sharpe": _sr(r[msk], CRYPTO_PPY), "dsr": _dsr(rr, n_trials),
                  "dsr_vs_buy_hold": _dsr(rr - r[msk], n_trials), "mdd": _mdd(rr), "buy_hold_mdd": _mdd(r[msk])}
    crit = [(f"weeks >= {min_n} (min_n)", True if n >= min_n else None),
            (f"claim window from {start[:7]} covered by settle-synchronous basis with a 52-week history", True if covered else None),
            (f"depth gap (top decile - bottom half) >= {gap_pp:g} pp", None if g is None else g >= gap_pp),
            ("block-permutation p < 0.05", None if p is None else p < 0.05),
            ("gap positive in both halves (split 2022-01)", same),
            (f"at least {min_episodes} non-overlapping top-decile episodes (else insufficient events)", True if eps >= min_episodes else None)]
    v, why = _verdict(crit)
    reason = (f"{n} weeks {wk[0] if wk else 'n/a'}..{wk[-1] if wk else 'n/a'} ({int((lab == 2).sum()) if n else 0} top-decile, "
              f"{int((lab == 0).sum()) if n else 0} bottom-half): mean 30-day max drawdown {_f(dep[lab == 2].mean() if n and (lab == 2).any() else None, 1)}% "
              f"vs {_f(dep[lab == 0].mean() if n and (lab == 0).any() else None, 1)}%, gap {_f(g, 1)} pp (need >= {gap_pp:g}); "
              f"permutation p {_f(p, 4)} (need < 0.05); halves {_f(hs[0], 1)} / {_f(hs[1], 1)} pp (need both > 0); "
              f"{eps} non-overlapping episodes (need >= {min_episodes}); weeks need >= {min_n}; window from {start[:7]} "
              f"covered: {'yes' if covered else 'no (settle-synchronous spot starts 2019-05, first labelled week ' + (wk[0] if wk else 'n/a') + ')'} — {why}")
    return {"n": n, "gap_pp": g, "p_perm": p, "halves": halves, "episodes": eps,
            "mean_depth_top": float(dep[lab == 2].mean()) if n and (lab == 2).any() else None,
            "mean_depth_bottom": float(dep[lab == 0].mean()) if n and (lab == 0).any() else None,
            "timing_rule": timing, "first_week": wk[0] if wk else None, "criteria": crit, "verdict": v, "reason": reason}


# ===================================================================================================================
# T-423: top-decile funding z-score and the 7-day forward BTC return
# ===================================================================================================================

def funding_sentiment(fts, i8, fidx, i1=None, start: str = "2019-06-01", end: str = "2026-09-30", oos_start: str = "2023-01-01",
                      z_window: int = 30, min_hist: int = 180, horizon: int = 7, mean_block: float = 7, n_boot: int = 5000,
                      seed: int = 0, n_trials: int = 24, cost_side: float = 0.005, gap: float = -0.02, min_top: int = 200,
                      min_events: int = 30) -> dict:
    """T-423. Day d: m_d = mean interest_8h over records in (d 00:00, d+1 00:00] UTC. z_d uses the previous 30 days.
    Top decile: z_d above the 90th percentile of all earlier z values (expanding window, at least 180 of them, point in
    time). Entry at the next hourly bar (d+1 01:00 UTC). The forward return is index(entry + 7d) / index(entry) - 1 on
    the Deribit BTC index. Difference = mean(top) - mean(all days). Its p-value is from a stationary bootstrap (mean
    block 7) of the estimating series g = diff + f (x - m_top)/p - (x - m_all), with H0: diff >= 0. Pass: >= 200
    top-decile days, >= 30 non-overlapping events (7-day separation), out-of-sample (2023-) diff <= -2 pp with
    p < 0.05, and DSR >= 0.95 (24 cells) of the contrarian rule's daily return net of costs, measured against buy and
    hold. The rule is flat for 7 days after a top-decile day and otherwise long, with 0.5% per side."""
    ts, cs = _hourly(fts, i8); fidx = np.asarray(fidx, dtype=float)
    d0, d1 = _d(start), _d(end)
    days = [(d0 + timedelta(days=k)).isoformat() for k in range((d1 - d0).days + 1)]
    t = np.array([_utc_ts(d) for d in days], dtype=np.int64)
    s, c = window_sum(ts, cs, t, t + DAY)
    m = np.where(c >= 20, s / np.maximum(c, 1), np.nan)
    n = len(days); z = np.full(n, np.nan)
    for i in range(z_window, n):
        w = m[i - z_window:i]
        if np.all(np.isfinite(w)) and np.isfinite(m[i]) and w.std(ddof=1) > 0:
            z[i] = (m[i] - w.mean()) / w.std(ddof=1)
    top = np.zeros(n, dtype=bool); valid = np.zeros(n, dtype=bool); hist: list[float] = []
    for i in range(n):
        if np.isfinite(z[i]):
            if len(hist) >= min_hist:
                valid[i] = True; top[i] = z[i] > np.quantile(hist, 0.9)
            hist.append(float(z[i]))
    te = t + DAY + HOUR
    fwd = value_at(ts, fidx, te + horizon * DAY) / value_at(ts, fidx, te) - 1.0
    use = valid & np.isfinite(fwd)
    da = np.array(days)

    def diff_stats(msk: np.ndarray, with_p: bool) -> dict:
        x = fwd[msk]; f = top[msk]
        if f.sum() < 2 or (~f).sum() < 2:
            return {"n": int(msk.sum()), "n_top": int(f.sum()), "diff": None, "p": None}
        mt, ma = float(x[f].mean()), float(x.mean()); p_ = f.mean(); dif = mt - ma
        g = dif + f * (x - mt) / p_ - (x - ma)
        return {"n": int(msk.sum()), "n_top": int(f.sum()), "mean_top": mt, "mean_all": ma, "diff": dif,
                "p": stationary_mean_p_less(g, mean_block, n_boot, seed) if with_p else None}

    full = diff_stats(use, False)
    oos = diff_stats(use & (da >= oos_start), True)
    ins = diff_stats(use & (da < oos_start), True)
    events = _episodes([_d(d).toordinal() for d in da[use & top]], horizon)
    # contrarian rule on daily index returns (01:00 UTC to 01:00 UTC), flat on days d+1..d+7 after a top day
    p1 = value_at(ts, fidx, te - DAY); p2 = value_at(ts, fidx, te)
    R = p2 / p1 - 1.0                                   # day k: index(k 01:00) -> index(k+1 01:00)
    flat = np.zeros(n, dtype=bool)
    for i in np.flatnonzero(use & top):
        flat[i + 1:i + 1 + horizon] = True
    ev = np.isfinite(R) & (np.cumsum(valid) > 0)
    pos = np.where(flat, 0.0, 1.0)
    sw = np.abs(np.diff(pos, prepend=1.0))
    rule = pos * R - cost_side * sw
    active = rule - R
    dsr = _dsr(active[ev], n_trials)
    carry = None
    if i1 is not None:
        ts1, cs1 = _hourly(fts, i1)
        dcar, cc = window_sum(ts1, cs1, t, t + DAY)
        dcar = np.where(cc >= 20, dcar, np.nan)[ev]
        dcar = dcar[np.isfinite(dcar)]
        carry = {"sharpe": _sr(dcar, CRYPTO_PPY), "mdd": _mdd(dcar), "annualised_mean": float(dcar.mean() * 365)}
    halves = {"2019-2022": ins, "2023-2026": oos}
    crit = [(f"top-decile days >= {min_top}", True if full["n_top"] >= min_top else None),
            (f"non-overlapping events >= {min_events}", True if events >= min_events else None),
            (f"out-of-sample difference <= {gap * 100:g} pp", None if oos["diff"] is None else oos["diff"] <= gap),
            ("out-of-sample stationary-bootstrap p < 0.05 (H0: difference >= 0)", None if oos["p"] is None else oos["p"] < 0.05),
            (f"DSR >= 0.95 of contrarian-minus-buy-and-hold daily returns (n_trials = {n_trials})", dsr is not None and dsr >= 0.95)]
    v, why = _verdict(crit)
    reason = (f"{full['n']} days ({full['n_top']} top-decile, {events} non-overlapping events): full-sample 7-day return top "
              f"{_pp(full.get('mean_top'))}% vs all {_pp(full.get('mean_all'))}%, difference {_pp(full['diff'])} pp; "
              f"out-of-sample {oos_start[:4]}+ difference {_pp(oos['diff'])} pp (need <= {gap * 100:g}) with p {_f(oos['p'], 4)} "
              f"(need < 0.05; {oos['n_top']} top days); in-sample difference {_pp(ins['diff'])} pp; DSR of contrarian vs "
              f"buy-and-hold {_f(dsr, 3)} (need >= 0.95) — {why}")
    return {"n": full["n"], "n_top": full["n_top"], "events": events, "full": full, "oos": oos, "in_sample": ins,
            "halves": halves, "dsr_contrarian_vs_hold": dsr,
            "contrarian_sharpe": _sr(rule[ev], CRYPTO_PPY), "buy_hold_sharpe": _sr(R[ev], CRYPTO_PPY),
            "carry_variant": carry, "criteria": crit, "verdict": v, "reason": reason}


# ===================================================================================================================
# archive access and harnesses
# ===================================================================================================================

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


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return {"missing_bundles": miss}, 0, "inconclusive", f"missing data bundles {miss}: the claim cannot be tested until they are archived"
    return None


def _rows(archive, name: str):
    """Rows of a bundle that were already available when it was captured (drops bars still open at capture)."""
    cap = archive.get(name).created_at
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _funding(archive):
    def load():
        by = {}
        for r in _rows(archive, FUNDING):
            v = r["value"]; by[int(v["timestamp"]) // 1000] = v
        tsl = sorted(by)
        return (np.array(tsl, dtype=np.int64), np.array([by[k]["interest_1h"] for k in tsl], dtype=float),
                np.array([by[k]["interest_8h"] for k in tsl], dtype=float),
                np.array([by[k]["index_price"] for k in tsl], dtype=float))
    return _cached(archive, ("funding",), load)


def _index(archive, name: str) -> dict:
    return _cached(archive, ("index", name), lambda: index_closes(_rows(archive, name)))


def _quarterlies(archive) -> list[dict]:
    def load():
        by: dict = {}
        for r in _rows(archive, QUARTERLIES):
            v = r["value"]; ets = _utc_ts(v["expiry"], 8); o = int(v["ts_ms"]) // 1000
            if o >= ets:
                continue                                  # stale bar opening at/after expiry
            by.setdefault((v["instrument"], ets), {})[o + DAY] = float(v["close"])
        out = []
        for (ins, ets), bars in by.items():
            k = sorted(bars)
            out.append({"instrument": ins, "expiry_ts": ets, "close_ts": np.array(k, dtype=np.int64),
                        "close": np.array([bars[x] for x in k])})
        return out
    return _cached(archive, ("quarterlies",), load)


def _delivery(archive) -> dict:
    return _cached(archive, ("delivery",), lambda: {r["value"]["date"]: float(r["value"]["delivery_price"]) for r in _rows(archive, DELIVERY)})


def _btcf(archive):
    """(days, closes, standard-session flag) of Yahoo BTC=F; standard bars are stamped 00:00 New York."""
    def load():
        by = {}
        for r in _rows(archive, "daily-history-BTC-F"):
            v = r["value"]; dt = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc)
            by[dt.strftime("%Y-%m-%d")] = (float(v["close"]), dt.astimezone(_NY).hour == 0)
        ds = sorted(by)
        return ds, np.array([by[d][0] for d in ds]), np.array([by[d][1] for d in ds], dtype=bool)
    return _cached(archive, ("btcf",), load)


def _spot_fn(archive):
    fts, _, _, fidx = _funding(archive)
    return lambda t: float(value_at(fts, fidx, t)[0])


def _cme_sync(archive):
    days, F, std = _btcf(archive)
    fts, _, _, fidx = _funding(archive)
    S = value_at(fts, fidx, np.array([cme_settle_ts(d) for d in days], dtype=np.int64))
    return days, F, S, std


def _wrap(rep: dict):
    rep = _clean(rep)
    return rep, int(rep.get("n") or 0), rep["verdict"], rep["reason"]


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (np.floating, float)):
        f = float(x)
        return f if math.isfinite(f) else None
    if isinstance(x, date):
        return x.isoformat()
    return x


def carry_perp_funding_vs_quarterly(archive):
    """T-198: 90-day BTC-PERPETUAL funding received by a short vs the front quarterly basis pro-rated to 90 days."""
    miss = _missing(archive, [FUNDING, QUARTERLIES])
    if miss:
        return miss
    fts, i1, _, fidx = _funding(archive)
    return _wrap(perp_vs_quarterly_basis(fts, i1, fidx, _quarterlies(archive)))


def carry_funding_call_hedged(archive):
    """T-258 (MODEL-PRICED): monthly long-spot/short-perp funding net of a rolling 10-delta 30-DTE call at DVOL."""
    miss = _missing(archive, [FUNDING, DELIVERY, "deribit-dvol-BTC-history", "fred-DTB3"])
    if miss:
        return miss
    fts, i1, _, _ = _funding(archive)
    return _wrap(funding_call_hedged(fts, i1, _delivery(archive), _index(archive, "deribit-dvol-BTC-history"),
                                     _index(archive, "fred-DTB3")))


def carry_trend_funding_filter(archive):
    """T-303: BTC 200-day SMA long/flat with vs without the funding crowding state machine."""
    miss = _missing(archive, [FUNDING, "daily-history-BTC-USD"])
    if miss:
        return miss
    days, closes = _cached(archive, ("px", "BTC-USD"), lambda: load_series(archive, "BTC-USD", adjusted=True))
    fts, _, i8, _ = _funding(archive)
    return _wrap(trend_funding_filter(days, closes, fts, i8))


def carry_cme_basis_spike(archive):
    """T-329: 5-day long-spot/short-BTC=F trade after the synchronous annualised basis exceeds +2 sd of its 60-day mean."""
    miss = _missing(archive, [FUNDING, "daily-history-BTC-F", "fred-DTB3"])
    if miss:
        return miss
    days, F, S, std = _cme_sync(archive)
    return _wrap(cme_basis_spike(days, F, S, std, cme_expiries(), dtb3=_index(archive, "fred-DTB3")))


def carry_cme_cash_and_carry(archive):
    """T-362: hold-to-expiry CME cash-and-carry when the synchronous annualised basis > DTB3 + 3%."""
    miss = _missing(archive, [FUNDING, "daily-history-BTC-F", "fred-DTB3"])
    if miss:
        return miss
    days, F, std = _btcf(archive)
    tab = cme_contract_table(days, F, std, _spot_fn(archive), cme_expiries(), _index(archive, "fred-DTB3"))
    return _wrap(cme_cash_and_carry(tab))


def carry_perp_funding_threshold(archive):
    """T-363: long BTC / short BTC-PERPETUAL while 7-day annualised funding > DTB3 + 4%, 2023-01..2026-09."""
    miss = _missing(archive, [FUNDING, "fred-DTB3"])
    if miss:
        return miss
    fts, i1, _, _ = _funding(archive)
    return _wrap(perp_funding_carry(fts, i1, _index(archive, "fred-DTB3")))


def carry_basis_crash_predictor(archive):
    """T-364: forward 30-day BTC-USD max drawdown after top-decile vs bottom-half weekly synchronous BTC=F basis."""
    miss = _missing(archive, [FUNDING, "daily-history-BTC-F", "daily-history-BTC-USD", "fred-DTB3"])
    if miss:
        return miss
    days, F, S, std = _cme_sync(archive)
    tab = cme_daily_basis(days, F, S, std, cme_expiries(), roll_calendar_days=3)
    wk = weekly_first(days, tab["ok"])
    pdays, pclose = _cached(archive, ("px", "BTC-USD"), lambda: load_series(archive, "BTC-USD", adjusted=True))
    return _wrap(basis_crash_predictor([days[i] for i in wk], tab["basis"][wk], pdays, pclose, _index(archive, "fred-DTB3")))


def carry_funding_sentiment(archive):
    """T-423: 7-day forward BTC return after top-decile funding z-score days vs the unconditional mean."""
    miss = _missing(archive, [FUNDING])
    if miss:
        return miss
    fts, i1, i8, fidx = _funding(archive)
    return _wrap(funding_sentiment(fts, i8, fidx, i1=i1))


HARNESSES = {
    "carry_perp_funding_vs_quarterly": carry_perp_funding_vs_quarterly,
    "carry_funding_call_hedged": carry_funding_call_hedged,
    "carry_trend_funding_filter": carry_trend_funding_filter,
    "carry_cme_basis_spike": carry_cme_basis_spike,
    "carry_cme_cash_and_carry": carry_cme_cash_and_carry,
    "carry_perp_funding_threshold": carry_perp_funding_threshold,
    "carry_basis_crash_predictor": carry_basis_crash_predictor,
    "carry_funding_sentiment": carry_funding_sentiment,
}

THEORY_MAP = {
    "T-198": "carry_perp_funding_vs_quarterly",
    "T-258": "carry_funding_call_hedged",
    "T-303": "carry_trend_funding_filter",
    "T-329": "carry_cme_basis_spike",
    "T-362": "carry_cme_cash_and_carry",
    "T-363": "carry_perp_funding_threshold",
    "T-364": "carry_basis_crash_predictor",
    "T-423": "carry_funding_sentiment",
}
