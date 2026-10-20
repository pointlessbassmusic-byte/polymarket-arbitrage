"""
Batch 6c, group ``kraken``: four Coinbase / Kraken 1-minute microstructure claims on the bundles fetched by
``mandel.data.crypto_history`` (``coinbase-1m-BTC-USD-<YYYY-MM>``: Coinbase Exchange 1-minute candles, available at bar
start + 60 s; ``kraken-trades-1m-XBTUSD-<YYYY-MM>``: 1-minute bars rebuilt from Kraken public trades with exact
aggressor-side volume and, in the HH:59 minute before each hour mark, every trade as ``ticks``; available at minute end).
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-331  Hourly UTC marks 2022-01..2026-09. On each venue the last trade at or before the mark: Kraken = the close of
           the HH:59 bar (its last trade; the ticks give the same print), Coinbase = the close of the HH:59 candle (the
           candle close is the last trade in the minute, so this is exact at the mark). A venue whose last trade is more
           than 5 minutes old at the mark (outage) makes the mark invalid (counted; the share with no outage rule, the last
           trade up to 60 minutes back, is reported beside it). gap = ln(P_cb / P_kr); excursion =
           |gap| > 0.70%. Pass: lower bound of the 95% Wilson interval of the excursion share >= 0.5%. Null (the trial):
           'share = 0 beyond what a 1-minute price-staleness simulation produces': one venue's mark is shifted by s seconds
           (s uniform in 1..60, one draw per mark, fixed seed; s = 30 and 60 also reported). The shifted venue is Kraken,
           whose HH:59 ticks make the last trade at or before mark - s EXACT. The staleness-only share is the share of
           marks with |ln(P_kr(mark) / P_kr(mark - s))| > 0.70% (what pure staleness of up to 60 s produces when the two
           venues otherwise agree); the criterion is observed share - staleness share > 0, one-sided 95% studentized
           block bootstrap of the paired per-mark indicator difference (24-hour blocks). Shifting Coinbase instead is
           reported as an approximation: a candle gives only the minute close, so the last trade at or before mark - s is
           taken as the close of the last candle that ENDED at or before mark - s, which is up to 60 s staler than the
           true last trade and therefore OVERSTATES the staleness share (conservative against the claim). Stress windows
           2022-11, 2023-03 and 2024-08 are reported separately and excluded in a robustness share. Diagnostics: gap AR(1),
           the single-venue rule (|z| > 2 of the gap over the trailing 168 marks, trade the venue toward the other over the
           next hour, 0.80% maker round trip) and the Sidak-adjusted Wilson bound for the 4 declared variants (ETH,
           USDT-quoted and the single-venue variant are not archived or not share claims: deflation reported, not decided).
  * T-425  Aligned minutes 2023-01..2026-09: gap_t = ln(close_cb / close_kr) of minute t (known at t + 60 s). Trigger
           |gap_t| > theta, theta = all-in cost + 10 bps, all-in cost = the four-leg round trip 2 (f_cb + f_kr) at a tier
           (maker and taker readings). Fills at the NEXT minute's close (the close of minute t + 1, known at t + 120 s):
           sell on the rich venue, buy on the cheap one (inventory-neutral: the BTC book is unchanged). Unwind when
           |gap| < 0.5 sigma (sigma = the trailing 1-day sd of the gap, prior minutes) or 15 minutes after the fill,
           again at the next minute's close. One position at a time. Per-trade net = sign(gap_t) (gap_fill_in -
           gap_fill_out) - 2 (f_cb + f_kr) in fractions of one BTC notional. Period costs: inventory financing = DTB3
           (continuous) on the USD inventory of one notional per venue (2 x notional) every calendar day; a weekly transfer
           (0.0001 BTC) in each week with a trade. Annual net P&L = the sum per calendar year; the test statistic is the
           daily net P&L series (studentized block bootstrap, 7-day blocks, one-sided p for H0: mean <= 0). The user's fee
           tier is NOT recorded anywhere in the repo, so the criterion 'at the user's tier' is None (rule 2 / rule 9 cap: the
           verdict is at best inconclusive) and the P&L is reported for every published tier pair under maker and taker
           fees. A second, implemented criterion is the necessary condition any tier must meet: net P&L > 0 with p < 0.05 at
           the most favourable published pair ($400M+ / Pro 5, maker fees); it fails decisively when that pair's one-sided
           95% upper bound of the daily mean lies below 0 (then no tier can pass). Its gross per trigger is decomposed by leg
           (``leg_decomposition``: the Coinbase leg -s ln(cb_out / cb_in) and the Kraken leg +s ln(kr_out / kr_in), s = the
           trigger gap's sign; the mean signed gap at the trigger, at the entry fill and at the exit; each leg when its entry
           fill is one minute later), so a pass whose gross sits in the Kraken leg while the trigger gap is mostly gone by the
           fill and shrinks under the later fill is read as fee-free Kraken last-print reversion toward Coinbase, not as an
           executable two-venue gap capture (the next-minute-close fill is still followed as worded). Cells: 1-minute (the
           claim) and 5-minute bars (rule 10: the 5 phases pooled, per-phase range
           reported), retail and high-volume tiers (ETH not archived): DSR over the 8 declared cells reported, the family
           variance from cells with at least FAMILY_MIN_N triggers (a cell without trades is only the financing drag). Regime:
           triggers in hours with |trailing 60-minute return| > 3% vs calm. Information share: Hasbrouck bounds (Baillie
           et al. 2002 form, VECM with 5 lags, per calendar year).
  * T-459  Kraken only, 2023-01..2026-09; in-sample 2023-01..2024-12, out of sample 2025-01..2026-09. Imbalance I_t =
           (buy - sell) / (buy + sell) over the last w closed minutes (the library rule's ratio), z-scored against the
           trailing day (prior 1440 minutes, at least 720 valid). The claim's cell: w = 5, horizon 5 minutes, z > 2,
           maker-only. NOTE (measured on the archive): Kraken minutes are thin (median 10 trades, 0.19 BTC), so the ratio is
           bimodal with a trailing-day sd of about 0.64 and z > 2 would need I > 1.28, which a ratio bounded at 1 cannot
           reach; the rule as worded fires in about 0.01% of minutes. The claim's construction stays the ratio; the other
           reading of 'signed-volume imbalance', the raw signed volume (buy - sell, in BTC) z-scored the same way, runs
           through the same pipeline and is REPORTED (``alternative_reading_signed_volume``), not decided. Maker entry: a bid
           at the close of minute t (the last trade) posted at t + 60 s; it fills only when a seller-initiated trade prints
           at or below it in minute t + 1 (the bar's sell_lo <= bid, the fetcher's own convention; the strict reading is
           reported); otherwise the signal lapses. Maker exit: an ask at the close of minute t + h posted at its end; it
           fills when a buyer-initiated trade prints at or above it in minute t + h + 1 (buy_hi >= ask), else the position
           is crossed at that minute's close as a taker. Costs as the claim states: Kraken maker 0.16%, taker 0.26% (the
           base tier the claim names; the 2026 Tier 1 0.40% / 0.80% is a reported sensitivity). One position at a time.
           Pass: >= 20,000 out-of-sample trades AND mean net > 0 with p < 0.01 under the trial's null construction, a
           stationary block bootstrap of the trade sequence with 1-day blocks (Politis-Romano: geometric block lengths whose
           mean is the out-of-sample trades per trading day; centred percentile p), which must agree with a studentized
           bootstrap of the trades resampled in 1-day clusters (rule 11: both pass -> pass, both fail -> fail, otherwise
           undecided) AND DSR >= 0.95 over the 36 declared cells (24 computed: window
           1/5/15 x horizon 5/60 x threshold 2/3 x maker/taker; a cell's per-trade Sharpe enters the family variance only
           with at least FAMILY_MIN_N trades, since a Sharpe from a dozen trades is noise, not a trial estimate). Both
           out-of-sample criteria are decided only from the same minimum evidence (``t459_decide``): MIN_TRADES_DECIDE trades
           spanning MIN_DAYS_DECIDE trade days. Below it the mean-net bootstraps have no p AND the DSR row is None (rule 5:
           the PSR's normal approximation is no bound at 4-6 trades, so a handful of losing trades cannot decide the DSR row
           while its sister criterion is undecidable); the DSR and PSR values are still reported from 4 trades on. The
           in-sample best cell is reported out of sample too.
           Regime: volatility terciles (trailing 60-minute realised vol; the cutpoints are the terciles over the in-sample
           SIGNAL minutes of the claim cell, at least TERCILE_MIN_SIGNALS of them, applied to the out-of-sample trades).
  * T-465  Hourly observations 2023-01..2026-09. VPIN from Kraken signed volume: bucket = ADV / 50 (ADV = the mean daily
           Kraken volume over the previous 30 UTC days, at least 10), buckets filled from the 1-minute buy / sell volumes
           (a minute straddling a boundary is split pro rata); VPIN = mean |buy - sell| / bucket over the last 50 buckets
           whose closing minute ENDED at or before the hour mark (buckets closed before the forecast hour). Realised
           volatility of hour H = the sum of squared 1-minute log close returns of the Coinbase candles in H (at least 30
           returns); volume = the Coinbase base volume of the previous hour. HAR: log RV_H on log RV of the previous hour,
           log of the previous 24-hour mean RV, log of the previous 168-hour mean RV and log volume; the VPIN model adds
           VPIN at H. Pass: >= 20,000 hourly observations AND incremental R^2 >= 2% with Newey-West t > 3 (the full covered
           window) AND Diebold-Mariano p < 0.05 out of sample for the QLIKE loss difference (expanding window, refit every
           24 hours after a 180-day burn-in; forecasts exp(yhat + s^2 / 2)). Cells: bucket 1/50 vs 1/200 of ADV x window
           50 vs 250 buckets x VPIN level vs its trailing-30-day CDF (8 declared, all computed); the Sidak-adjusted DM p is
           reported. Regime: weekends vs weekdays (UTC).

Conventions
  * Data. Months are discovered from the archive's entry names at call time; the dense 1-minute grid spans the stored
    months and every bundle is read through ``archive.load`` (rows with available_at after the bundle's capture time are
    skipped). The aligned arrays are built once per module (``_CACHE`` keyed by the stored month sets) and shared by the
    four harnesses. A month of a claim's window that is not stored on a venue the claim needs is a DATA LIMIT: the
    coverage criterion is None (the verdict is capped at inconclusive) and the missing months are named; it is never an
    error. On a partial window, as below min_n (rule 5), a failing criterion counts only when it fails decisively.
  * Point in time (rules 4, 12). Bars are known at their end; every decision uses closed bars and every fill is a later
    bar's close or a later print through a resting quote; the staleness null uses exact trade times.
  * Intervals (rule 6): studentized block bootstraps (``batch6b_bw._stud``) with replicate seeds and their Monte Carlo
    s.e. (``mc_reps``); Wilson where the claim says Wilson; Newey-West for regression t statistics.
  * Costs as stated (rule 9): T-331 0.70% threshold; T-425 published tier schedules (declared constants, provenance in
    ``COINBASE_TIERS`` / ``KRAKEN_TIERS``); T-459 0.16% / 0.26%; T-465 none.

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not implemented
(None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence

import numpy as np

from mandel.experiments.batch6b_bw import Bills, _chunks, _clean, _closes, _f, _has, _mean_stat, _pc, _s, _stud, mc_reps
from mandel.experiments.batch6c_cryptovenue import ar1, dsr_row, wilson
from mandel.experiments.batch6c_mom import family_dsr
from mandel.experiments.batch6c_pub import cluster_stud
from mandel.experiments.batch6c_rates import hac_mean, nw_lag, ols_nw
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import sharpe_ratio

N_BOOT = 2000                  # bootstrap draws per seed
REPS = 5                       # bootstrap seeds behind every decisive interval end or p-value
SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
UTC = timezone.utc
_N = NormalDist()

KR_PREFIX = "kraken-trades-1m-XBTUSD-"
CB_PREFIX = "coinbase-1m-BTC-USD-"
DTB3_B = "fred-DTB3"

WIN = {"T-331": ("2022-01", "2026-09"), "T-425": ("2023-01", "2026-09"),
       "T-459": ("2023-01", "2026-09"), "T-465": ("2023-01", "2026-09")}
MIN_N = {"T-331": 2000, "T-425": 100_000, "T-459": 20_000, "T-465": 20_000}
T459_OOS_FIRST = "2025-01"     # fit 2023-24, test 2025-26

# T-331
GAP_THR = 0.0070
SHARE_PASS = 0.005
STALE_MAX_S = 60
STALE_OUTAGE_MIN = 5           # a venue whose last trade is older than this at the mark is down: the mark is invalid
STRESS = {"2022-11 (FTX)": "2022-11", "2023-03 (banking)": "2023-03", "2024-08 (carry unwind)": "2024-08"}
T331_VARIANTS = 4
SINGLE_VENUE_RT = 0.0080       # 2 x 0.40% maker, the cheapest retail maker round trip on either venue

# T-425: published spot schedules, maker / taker per leg. Provenance: Kraken Pro tiers 1-3 and Pro 5 re-fetched 2026-10-14
# (mandel/knowledge/VENUES.md; the page's intermediate tiers are elided there and are bracketed by Tier 3 and Pro 5);
# Coinbase Advanced lowest tier verified 2026-10-14 (UNDERLYING-STRATEGIES.md); the other Coinbase tiers are the published
# 30-day-volume schedule as declared here, not re-verified in the repo. The user's own tier is recorded nowhere.
COINBASE_TIERS = [("Intro ($0+)", 0.0040, 0.0060, True), ("$10K+", 0.0025, 0.0040, False), ("$50K+", 0.0015, 0.0025, False),
                  ("$100K+", 0.0010, 0.0020, False), ("$1M+", 0.0008, 0.0018, False), ("$15M+", 0.0006, 0.0016, False),
                  ("$75M+", 0.0003, 0.0012, False), ("$250M+", 0.0000, 0.0008, False), ("$400M+", 0.0000, 0.0005, True)]
KRAKEN_TIERS = [("Tier 1 ($0+)", 0.0040, 0.0080, True), ("Tier 2 ($2.5K+)", 0.0030, 0.0060, True),
                ("Tier 3 ($10K+)", 0.0022, 0.0038, True), ("Pro 5 ($500M+)", 0.0000, 0.0005, True)]
RETAIL_PAIR = ("Intro ($0+)", "Tier 1 ($0+)")
HIGHVOL_PAIR = ("$400M+", "Pro 5 ($500M+)")
EDGE_BPS = 0.0010              # the claim's '+ 10 bps'
HOLD_MIN = 15
EXIT_SIGMA = 0.5
TRANSFER_FEE = 0.0001          # BTC per weekly rebalancing transfer, per BTC notional (declared input)
VOL_SPIKE = 0.03               # |trailing 60-minute return| > 3%
T425_CELLS = 8
IS_LAGS = 5

FAMILY_MIN_N = 30              # trades (T-459) or triggers (T-425) for a cell's Sharpe to enter the DSR family variance

# T-459
T459_MAKER, T459_TAKER = 0.0016, 0.0026
T459_TIER1 = (0.0040, 0.0080)
T459_CELLS = 36
T459_GRID = [(w, h, thr, mk) for w in (1, 5, 15) for h in (5, 60) for thr in (2.0, 3.0) for mk in (True, False)]
T459_CLAIM = (5, 5, 2.0, True)
Z_WINDOW = 1440
Z_MIN = 720
MIN_TRADES_DECIDE = 8          # out-of-sample trades, spanning
MIN_DAYS_DECIDE = 4            # trade days: the minimum evidence for EITHER out-of-sample criterion (mean net, DSR row) to be decided
TERCILE_MIN_SIGNALS = 30       # in-sample claim-cell signal minutes needed for the volatility-tercile cutpoints

# T-465
VPIN_BUCKETS = (50, 200)
VPIN_WINDOWS = (50, 250)
T465_CELLS = 8
ADV_DAYS = 30
ADV_MIN_DAYS = 10
BURN_IN_HOURS = 24 * 180
REFIT_HOURS = 24
RV_MIN_RETURNS = 30
CDF_HOURS = 24 * 30

_CACHE: dict = {}


# ===================================================================================================== helpers ==

def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _month_start_s(m: str) -> int:
    return int(datetime(int(m[:4]), int(m[5:7]), 1, tzinfo=UTC).timestamp())


def _next_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y + (mo == 12):04d}-{(mo % 12) + 1:02d}"


def _months(first: str, last: str) -> list:
    out, m = [], first
    while m <= last:
        out.append(m)
        m = _next_month(m)
    return out


def _months_txt(ms: Sequence[str]) -> str:
    """'2024-06..2026-09, 2022-03' : consecutive months compressed into ranges."""
    ms = sorted(ms)
    if not ms:
        return "none"
    runs, a, b = [], ms[0], ms[0]
    for m in ms[1:]:
        if m == _next_month(b):
            b = m
        else:
            runs.append((a, b)); a = b = m
    runs.append((a, b))
    return ", ".join(x if x == y else f"{x}..{y}" for x, y in runs)


def _entry_names(archive) -> Optional[set]:
    try:
        return {e.name for e in archive.entries()}
    except (AttributeError, TypeError):
        return None


def stored_months(archive, prefix: str, months: Sequence[str]) -> list:
    """The months of ``months`` whose bundle ``prefix + month`` is stored (entry names first, probing as a fallback)."""
    names = _entry_names(archive)
    if names is not None:
        return [m for m in months if prefix + m in names]
    return [m for m in months if _has(archive, prefix + m)]


def _cap(archive, name: str) -> str:
    try:
        return getattr(archive.get(name), "created_at", "") or ""
    except (KeyError, AttributeError):
        return ""


def _load_grid(archive, months_kr: Sequence[str], months_cb: Sequence[str]) -> dict:
    """Dense 1-minute arrays over the stored months (NaN where a venue has no bar) and the Kraken HH:59 ticks per hour."""
    months = sorted(set(months_kr) | set(months_cb))
    if not months:
        return {"N": 0}
    T0, T1 = _month_start_s(months[0]), _month_start_s(_next_month(months[-1]))
    N = (T1 - T0) // 60
    H = N // 60
    g = {"T0": T0, "N": N, "H": H, "months_kr": list(months_kr), "months_cb": list(months_cb), "rows": {"kraken": 0, "coinbase": 0}}
    for k in ("kr_close", "kr_vol", "kr_buy", "kr_sell", "kr_slo", "kr_bhi", "cb_close", "cb_vol"):
        g[k] = np.full(N, np.nan)
    ticks: dict = {}
    for m in months_kr:
        name = KR_PREFIX + m
        cap = _cap(archive, name)
        idx, cols = [], {k: [] for k in ("close", "volume", "buy_vol", "sell_vol", "sell_lo", "buy_hi")}
        for r in archive.load(name):
            if cap and (r.get("available_at") or "") > cap:
                continue
            v = r.get("value") or {}
            try:
                t = int(v["t"]); i = (t - T0) // 60
            except (KeyError, TypeError, ValueError):
                continue
            if not (0 <= i < N):
                continue
            idx.append(i)
            for k in cols:
                x = v.get(k)
                cols[k].append(np.nan if x is None else float(x))
            tk = v.get("ticks")
            if tk:
                ticks[(t + 60 - T0) // 3600] = tk
        if idx:
            ii = np.array(idx, np.int64)
            g["kr_close"][ii] = cols["close"]; g["kr_vol"][ii] = cols["volume"]; g["kr_buy"][ii] = cols["buy_vol"]
            g["kr_sell"][ii] = cols["sell_vol"]; g["kr_slo"][ii] = cols["sell_lo"]; g["kr_bhi"][ii] = cols["buy_hi"]
            g["rows"]["kraken"] += len(idx)
    for m in months_cb:
        name = CB_PREFIX + m
        cap = _cap(archive, name)
        idx, cl, vo = [], [], []
        for r in archive.load(name):
            if cap and (r.get("available_at") or "") > cap:
                continue
            v = r.get("value") or {}
            try:
                t = int(v["t"]); i = (t - T0) // 60
                c = float(v["close"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (0 <= i < N):
                continue
            idx.append(i); cl.append(c)
            x = v.get("volume"); vo.append(np.nan if x is None else float(x))
        if idx:
            ii = np.array(idx, np.int64)
            g["cb_close"][ii] = cl; g["cb_vol"][ii] = vo
            g["rows"]["coinbase"] += len(idx)
    # ticks: flat arrays with per-hour offsets (hour h = mark at T0 + 3600 h; its HH:59 minute's trades)
    off = np.zeros(H + 2, np.int64)
    tt, tp = [], []
    for h in range(H + 1):
        tk = ticks.get(h)
        if tk:
            tk = sorted(tk, key=lambda x: (float(x[0]), x[5] or 0))
            tt.extend(float(x[0]) for x in tk); tp.extend(float(x[1]) for x in tk)
        off[h + 1] = len(tt)
    g["tick_off"], g["tick_t"], g["tick_p"] = off, np.array(tt, float), np.array(tp, float)
    g["marks_with_ticks"] = int(sum(1 for h in ticks if ticks[h]))
    return g


def grid(archive, months_kr: Sequence[str], months_cb: Sequence[str]) -> dict:
    """The aligned arrays, built once per (archive, stored months) and shared by the harnesses."""
    key = (id(archive), tuple(months_kr), tuple(months_cb))
    hit = _CACHE.get("grid")
    if hit is None or hit[0] != key or hit[1] is not archive:
        _CACHE.clear()
        _CACHE["grid"] = (key, archive, _load_grid(archive, months_kr, months_cb))
    return _CACHE["grid"][2]


def _idx_range(g: dict, first: str, last: str) -> tuple:
    """Grid indices [i0, i1) of months first..last (clipped to the grid)."""
    i0 = (_month_start_s(first) - g["T0"]) // 60
    i1 = (_month_start_s(_next_month(last)) - g["T0"]) // 60
    return int(max(0, min(g["N"], i0))), int(max(0, min(g["N"], i1)))


def _day_of(g: dict, i) -> np.ndarray:
    return (g["T0"] + 60 * np.asarray(i, np.int64)) // 86400


def _day_str(ord_day: int) -> str:
    return (date(1970, 1, 1) + timedelta(days=int(ord_day))).isoformat()


def _month_of_idx(g: dict, i: int) -> str:
    return datetime.fromtimestamp(g["T0"] + 60 * int(i), tz=UTC).strftime("%Y-%m")


def _last_before(a: np.ndarray, idx: np.ndarray, back: int) -> tuple:
    """Value of the last finite bar among indices idx-1 .. idx-back (and its age in bars; -1 when none)."""
    out = np.full(idx.size, np.nan)
    age = np.full(idx.size, -1, np.int64)
    n = a.size
    for k in range(1, back + 1):
        j = idx - k
        okj = (j >= 0) & (j < n) & np.isnan(out)
        vals = np.where(okj, a[np.clip(j, 0, max(n - 1, 0))], np.nan)
        take = okj & np.isfinite(vals)
        out[take] = vals[take]; age[take] = k
    return out, age


def _roll_prior(x: np.ndarray, win: int, min_count: int) -> tuple:
    """NaN-aware rolling mean and sd of x over the PRIOR window [t-win, t-1] (NaN below min_count valid values)."""
    n = x.size
    v = np.isfinite(x)
    xz = np.where(v, x, 0.0)
    c1 = np.concatenate([[0.0], np.cumsum(xz)])
    c2 = np.concatenate([[0.0], np.cumsum(xz * xz)])
    cn = np.concatenate([[0.0], np.cumsum(v.astype(float))])
    t = np.arange(n)
    lo = np.maximum(t - win, 0)
    cnt = cn[t] - cn[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = (c1[t] - c1[lo]) / cnt
        var = (c2[t] - c2[lo]) / cnt - mean * mean
    sd = np.sqrt(np.maximum(var, 0.0))
    bad = cnt < min_count
    mean[bad] = np.nan; sd[bad] = np.nan
    return mean, sd


def _roll_sum(x: np.ndarray, win: int) -> np.ndarray:
    """Sum of x (NaN as 0) over [t-win+1, t]."""
    xz = np.where(np.isfinite(x), x, 0.0)
    c = np.concatenate([[0.0], np.cumsum(xz)])
    t = np.arange(x.size) + 1
    return c[t] - c[np.maximum(t - win, 0)]


def _next_finite(x: np.ndarray, maxgap: int) -> np.ndarray:
    """nf[i] = the smallest j >= i with finite x[j] and j - i <= maxgap, else -1."""
    n = x.size
    j = np.where(np.isfinite(x), np.arange(n), n)
    nf = np.minimum.accumulate(j[::-1])[::-1]
    return np.where((nf < n) & (nf - np.arange(n) <= maxgap), nf, -1)


def _prev_finite(x: np.ndarray, maxgap: int) -> np.ndarray:
    n = x.size
    j = np.where(np.isfinite(x), np.arange(n), -1)
    pf = np.maximum.accumulate(j)
    return np.where((pf >= 0) & (np.arange(n) - pf <= maxgap), pf, -1)


def _judge(crit: list, n: int, min_n: int, unit: str, missing: Sequence[str], window: str) -> tuple:
    """crit: [(name, ok, decisive_fail)]. Below min_n OR on a partial window a failing criterion counts only when it fails
    decisively (rule 5 / rule 9); the min_n and the coverage criteria are appended."""
    partial = n < min_n or bool(missing)
    rows = []
    for name, ok, dec in crit:
        if ok is not None and not bool(ok) and partial and not dec:
            why = "below min_n" if n < min_n else "on a partial window"
            rows.append((name + f" [fails, not decisively, {why}]", None))
        else:
            rows.append((name, None if ok is None else bool(ok)))
    rows.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    if missing:
        rows.append((f"window {window} stored ({len(missing)} months not yet archived: {_months_txt(missing)})", None))
    return _verdict(rows)


def _mean_boot(x, block: int, level: float = 0.90, reps: Optional[int] = None) -> dict:
    """Studentized circular block bootstrap of a mean over replicate seeds; ci at ``level`` two-sided (0.90: its ends are
    the one-sided 95% bounds), p (H0: mean <= 0), p_lt (H0: mean >= 0)."""
    x = np.asarray(x, float)
    if x.size < 8:
        return {"est": float(x.mean()) if x.size else None, "ci": [None, None], "p": None, "p_lt": None, "n": int(x.size)}
    return mc_reps(lambda seed: _stud(_mean_stat, [x], block, N_BOOT, seed, level), reps=REPS if reps is None else reps, keys=("ci",))


def _stationary_once(x: np.ndarray, L: float, n_boot: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n = x.size
    m0 = float(x.mean())
    pos = np.arange(n)
    mm = []
    for k in _chunks(n_boot, n):
        new = rng.random((k, n)) < 1.0 / L                      # a new block starts here (geometric lengths, mean L)
        new[:, 0] = True
        starts = rng.integers(0, n, (k, n))                     # the start of the block that begins at each position
        last = np.maximum.accumulate(np.where(new, pos[None, :], 0), axis=1)
        idx = (np.take_along_axis(starts, last, axis=1) + (pos[None, :] - last)) % n
        mm.append(x[idx].mean(axis=1))
    mm = np.concatenate(mm)
    return {"est": m0, "ci": [float(np.quantile(mm, 0.025)), float(np.quantile(mm, 0.975))],
            "p": float((np.sum(mm - m0 >= m0) + 1) / (mm.size + 1)), "p_lt": float((np.sum(mm - m0 <= m0) + 1) / (mm.size + 1)),
            "mean_block": float(L), "n": int(n)}


def stationary_boot_mean(x, mean_block: float, n_boot: Optional[int] = None, reps: Optional[int] = None) -> dict:
    """Politis-Romano stationary (circular) block bootstrap of a mean with geometric block lengths of mean ``mean_block``
    (capped at n / 4), over replicate seeds: est, 95% percentile ci, centred percentile p (H0: mean <= 0: the share of
    resampled means with m* - m0 >= m0) and p_lt (H0: mean >= 0)."""
    x = np.asarray(x, float)
    n = x.size
    if n < 8:
        return {"est": float(x.mean()) if n else None, "ci": [None, None], "p": None, "p_lt": None, "mean_block": None, "n": int(n)}
    L = max(1.0, min(float(mean_block), n / 4.0))
    nb = N_BOOT if n_boot is None else int(n_boot)
    return mc_reps(lambda seed: _stationary_once(x, L, nb, seed), reps=REPS if reps is None else reps, keys=("ci",))


def _agree(pa: Optional[float], pb: Optional[float], alpha: float) -> Optional[bool]:
    """Rule 11: two named constructions of one p-value pass only together; one passing and one failing is undecided."""
    if pa is None or pb is None:
        return None
    a, b = pa < alpha, pb < alpha
    return True if (a and b) else (False if (not a and not b) else None)


def _sidak(p: Optional[float], k: int) -> Optional[float]:
    return None if p is None else 1.0 - (1.0 - min(max(p, 0.0), 1.0)) ** k


def _coverage(archive, tid: str, need_cb: bool) -> dict:
    """Stored months of the claim's window per venue and the months missing on a venue the claim needs."""
    first, last = WIN[tid]
    months = _months(first, last)
    kr = stored_months(archive, KR_PREFIX, months)
    cb = stored_months(archive, CB_PREFIX, months) if need_cb else []
    missing = [m for m in months if m not in kr or (need_cb and m not in cb)]
    return {"window": f"{first}..{last}", "months": months, "kr": kr, "cb": cb, "missing": missing,
            "covered": [m for m in months if m not in missing]}


def _grid_for(archive) -> dict:
    """The shared grid over every stored month of the widest window (so the four harnesses share one load)."""
    all_months = _months(min(w[0] for w in WIN.values()), max(w[1] for w in WIN.values()))
    kr = stored_months(archive, KR_PREFIX, all_months)
    cb = stored_months(archive, CB_PREFIX, all_months)
    cb = [m for m in cb if m in kr]                        # Coinbase months without Kraken serve no claim here
    return grid(archive, kr, cb)


# ======================================================================================================= T-331 ==

def hourly_gaps(g: dict, i0: int, i1: int, thr: float = GAP_THR, seed: int = SEED) -> dict:
    """Per hourly mark in [i0, i1): the last-trade gap, excursions and the staleness simulation."""
    marks = np.arange(((i0 + 59) // 60) * 60, i1, 60, dtype=np.int64)
    marks = marks[marks > 0]
    cb, age_cb = _last_before(g["cb_close"], marks, STALE_OUTAGE_MIN)
    kr, age_kr = _last_before(g["kr_close"], marks, STALE_OUTAGE_MIN)
    valid = np.isfinite(cb) & np.isfinite(kr)
    gap = np.full(marks.size, np.nan)
    gap[valid] = np.log(cb[valid] / kr[valid])
    exc = np.isfinite(gap) & (np.abs(gap) > thr)
    rng = np.random.default_rng(seed)
    s_draw = rng.integers(1, STALE_MAX_S + 1, marks.size)
    kr_prev, _ = _last_before(g["kr_close"], marks - 1, STALE_OUTAGE_MIN)      # last trade at or before mark - 60 by bars
    cb_prev, _ = _last_before(g["cb_close"], marks - 1, STALE_OUTAGE_MIN)      # candle ending at or before mark - 60
    T0, off, tt, tp = g["T0"], g["tick_off"], g["tick_t"], g["tick_p"]
    H = g["H"]

    def kr_shift(s_arr):
        out = kr_prev.copy()
        has_tick = np.zeros(marks.size, bool)
        for q in range(marks.size):
            h = int(marks[q] // 60)
            if h < 0 or h > H:
                continue
            a, b = int(off[h]), int(off[h + 1])
            if b <= a:
                continue
            has_tick[q] = True
            mt = T0 + 60.0 * marks[q] - float(s_arr[q])
            j = np.searchsorted(tt[a:b], mt, side="right") - 1
            if j >= 0:
                out[q] = tp[a + j]
        return out, has_tick

    kr_s, has_tick = kr_shift(s_draw)
    kr_60, _ = kr_shift(np.full(marks.size, STALE_MAX_S))
    kr_30, _ = kr_shift(np.full(marks.size, 30))
    with np.errstate(invalid="ignore", divide="ignore"):
        stale_kr = np.abs(np.log(kr / kr_s))                 # single-venue staleness gap (exact)
        stale_kr60 = np.abs(np.log(kr / kr_60))
        stale_kr30 = np.abs(np.log(kr / kr_30))
        cross_s = np.abs(np.log(cb / kr_s))                  # cross-venue gap with Kraken's mark shifted
        stale_cb = np.abs(np.log(cb / cb_prev))              # Coinbase approximation: candle floor (overstates staleness)
    ok_null = valid & np.isfinite(stale_kr)
    cb_all, _ = _last_before(g["cb_close"], marks, 60)        # no outage rule: the last trade up to 60 minutes back
    kr_all, _ = _last_before(g["kr_close"], marks, 60)
    v_all = np.isfinite(cb_all) & np.isfinite(kr_all)
    with np.errstate(invalid="ignore", divide="ignore"):
        exc_all = v_all & (np.abs(np.log(cb_all / kr_all)) > thr)
    return {"marks": marks, "valid": valid, "gap": gap, "exc": exc, "cb": cb, "kr": kr, "s": s_draw, "has_tick": has_tick,
            "n_all": int(v_all.sum()), "exc_all": int(exc_all.sum()),
            "stale_kr": stale_kr, "stale_kr60": stale_kr60, "stale_kr30": stale_kr30, "cross_s": cross_s, "stale_cb": stale_cb,
            "ok_null": ok_null, "age_cb": age_cb, "age_kr": age_kr, "invalid": int(marks.size - valid.sum())}


def single_venue_rule(gapv: np.ndarray, p_kr: np.ndarray, p_cb: np.ndarray, rt_cost: float = SINGLE_VENUE_RT, lb: int = 168) -> dict:
    """|z| > 2 of the gap over the trailing lb marks -> trade the venue toward the other over the next mark."""
    mu, sd = _roll_prior(gapv, lb, lb // 2)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (gapv - mu) / sd
    sig = np.isfinite(z) & (np.abs(z) > 2.0)
    sig[-1] = False
    out = {}
    for venue, p, sgn in (("kraken", p_kr, 1.0), ("coinbase", p_cb, -1.0)):
        i = np.flatnonzero(sig)
        nxt = i + 1
        okr = np.isfinite(p[i]) & np.isfinite(p[nxt])
        i, nxt = i[okr], nxt[okr]
        r = np.log(p[nxt] / p[i]) * np.sign(gapv[i]) * sgn       # Kraken cheap (gap > 0): buy Kraken; Coinbase rich: sell it
        out[venue] = {"n": int(i.size), "mean_gross": float(r.mean()) if i.size else None,
                      "mean_net": float((r - rt_cost).mean()) if i.size else None}
    out["signals"] = int(sig.sum())
    return out


def b6c_kraken_cross_venue_gap(archive):
    """T-331: last-trade Coinbase-vs-Kraken gap at hourly marks exceeds 0.70% in at least 0.5% of hours (2022-01..2026-09)."""
    tid = "T-331"
    cov = _coverage(archive, tid, need_cb=True)
    if not cov["kr"] or not cov["cb"]:
        need = [KR_PREFIX + cov["months"][0]] if not cov["kr"] else [CB_PREFIX + cov["months"][0]]
        return _missing(archive, need)
    g = _grid_for(archive)
    i0, i1 = _idx_range(g, *WIN[tid])
    r = hourly_gaps(g, i0, i1)
    v = r["valid"]
    n = int(v.sum())
    k = int(r["exc"].sum())
    share = k / n if n else None
    w95 = wilson(k, n) if n else [None, None]
    z_sidak = _N.inv_cdf(1 - (1 - 0.95 ** (1.0 / T331_VARIANTS)) / 2)
    w_sidak = wilson(k, n, z_sidak) if n else [None, None]
    # staleness null: paired per-mark indicator difference, 24-hour blocks
    ok = r["ok_null"]
    stale_exc = ok & (r["stale_kr"] > GAP_THR)
    d = (r["exc"][ok].astype(float) - stale_exc[ok].astype(float))
    ex = _mean_boot(d, 24) if d.size >= 8 else {"est": None, "ci": [None, None], "p": None, "p_lt": None}
    null_share = float(stale_exc.sum() / ok.sum()) if ok.sum() else None
    null60 = float((ok & (r["stale_kr60"] > GAP_THR)).sum() / ok.sum()) if ok.sum() else None
    null30 = float((ok & (r["stale_kr30"] > GAP_THR)).sum() / ok.sum()) if ok.sum() else None
    cross_s = float((ok & (r["cross_s"] > GAP_THR)).sum() / ok.sum()) if ok.sum() else None
    okc = v & np.isfinite(r["stale_cb"])
    null_cb = float((okc & (r["stale_cb"] > GAP_THR)).sum() / okc.sum()) if okc.sum() else None
    # stress windows and the rest
    months = np.array([_month_of_idx(g, int(i)) for i in r["marks"]]) if r["marks"].size else np.array([], str)
    stress = {}
    in_stress = np.zeros(r["marks"].size, bool)
    for label, m in STRESS.items():
        sel = v & (months == m)
        in_stress |= sel
        kk, nn = int(r["exc"][sel].sum()), int(sel.sum())
        stress[label] = {"n": nn, "excursions": kk, "share": kk / nn if nn else None, "wilson95": wilson(kk, nn) if nn else [None, None],
                         "stored": m in cov["covered"]}
    rest = v & ~in_stress
    kr_, nr_ = int(r["exc"][rest].sum()), int(rest.sum())
    phi, hl = ar1(r["gap"][v]) if n > 20 else (None, None)
    sv = single_venue_rule(r["gap"], r["kr"], r["cb"]) if n > 200 else None
    tail = {q: float(np.quantile(np.abs(r["gap"][v]), q)) for q in (0.5, 0.9, 0.99, 0.999)} if n else {}
    crit = [
        (f"lower 95% Wilson bound of the excursion share {_pc(w95[0], 3)} ({k} of {n} marks, share {_pc(share, 3)}, upper {_pc(w95[1], 3)}) >= 0.5%",
         None if w95[0] is None else w95[0] >= SHARE_PASS, w95[1] is not None and w95[1] < SHARE_PASS),
        (f"share exceeds the 60 s staleness null (Kraken shifted by s ~ U(1..60 s) with exact ticks): observed {_pc(share, 3)} vs staleness-only "
         f"{_pc(null_share, 3)}; paired difference {_pc(ex.get('est'), 3)}, one-sided 95% lower bound {_pc((ex.get('ci') or [None])[0], 3)} > 0 "
         f"(24-hour blocks, p {_f(ex.get('p'), 4)})",
         None if (ex.get("ci") or [None])[0] is None else ex["ci"][0] > 0,
         (ex.get("ci") or [None, None])[1] is not None and ex["ci"][1] < 0),
    ]
    verdict, why = _judge(crit, n, MIN_N[tid], "hourly marks", cov["missing"], cov["window"])
    reason = (f"Coinbase/Kraken BTC-USD hourly marks {cov['window']}: covered {_months_txt(cov['covered'])} ({n} valid marks, {r['invalid']} invalid: a venue's "
              f"last trade older than {STALE_OUTAGE_MIN} min; {int(r['has_tick'].sum())} marks with Kraken ticks); |gap| > 0.70% in {k} marks = {_pc(share, 3)}, "
              f"Wilson 95% [{_pc(w95[0], 3)}, {_pc(w95[1], 3)}], Sidak-adjusted for {T331_VARIANTS} variants lower {_pc(w_sidak[0], 3)}; staleness-only share "
              f"{_pc(null_share, 3)} (s = 30 s {_pc(null30, 3)}, s = 60 s {_pc(null60, 3)}; Coinbase candle-floor approximation {_pc(null_cb, 3)}, which "
              f"overstates staleness); cross-venue share with Kraken shifted {_pc(cross_s, 3)}; |gap| median {_pc(tail.get(0.5), 3)}, p99 {_pc(tail.get(0.99), 3)}, "
              f"p99.9 {_pc(tail.get(0.999), 3)}; without the outage rule {r['exc_all']} of {r['n_all']} marks = {_pc(r['exc_all'] / r['n_all'] if r['n_all'] else None, 3)}; "
              f"gap AR(1) {_f(phi)}; stress: " + ", ".join(f"{lab} {_pc(s_['share'], 2)} ({s_['excursions']}/{s_['n']})"
              for lab, s_ in stress.items()) + f"; excluding stress {_pc(kr_ / nr_ if nr_ else None, 3)}; single-venue rule (Kraken toward Coinbase) "
              f"{(sv or {}).get('kraken', {}).get('n', 0)} trades, mean net {_pc(((sv or {}).get('kraken') or {}).get('mean_net'), 3)} — " + why)
    stat = {"window": cov["window"], "covered_months": _months_txt(cov["covered"]), "missing_months": cov["missing"], "n_marks": n, "invalid_marks": r["invalid"],
            "marks_with_ticks": int(r["has_tick"].sum()), "excursions": k, "share": share, "wilson95": w95, "wilson_sidak4": w_sidak, "threshold": GAP_THR,
            "without_outage_rule": {"n_marks": r["n_all"], "excursions": r["exc_all"], "share": r["exc_all"] / r["n_all"] if r["n_all"] else None},
            "staleness": {"share_random_s": null_share, "share_s30": null30, "share_s60": null60, "coinbase_candle_floor_share": null_cb,
                          "cross_venue_share_kraken_shifted": cross_s, "excess": {kq: ex.get(kq) for kq in ("est", "ci", "ci_mc_se", "p", "p_lt", "reps")},
                          "note": "Kraken shifted with exact HH:59 ticks; the Coinbase reading floors the shifted mark to the last closed candle (up to "
                                  "60 s staler than the true last trade) and so overstates the staleness share"},
            "abs_gap_quantiles": tail, "gap_ar1": phi, "gap_half_life_hours": hl, "stress_windows": stress,
            "share_excluding_stress": kr_ / nr_ if nr_ else None, "single_venue_rule": sv, "variants_declared": T331_VARIANTS,
            "criteria": crit, "rule12": "both venues' last trades at or before the mark; the mark is the decision time",
            "rule10": "hourly UTC marks are the claim's named calendar"}
    return _out(stat, n, verdict, reason)


# ======================================================================================================= T-425 ==

def arb_sim(gap: np.ndarray, sigma: np.ndarray, fee_sum: float, hold: int = HOLD_MIN, edge: float = EDGE_BPS) -> dict:
    """Inventory-neutral threshold rule on a bar grid: trigger |gap_t| > 2 fee_sum + edge, fill at bar t+1's close,
    unwind at the close after the first bar u in (t+1, t+1+hold] with |gap_u| < 0.5 sigma_u (or u = t+1+hold); one position
    at a time. Returns per-trade arrays (fractions of notional) with fee_sum = f_cb + f_kr per leg pair."""
    n = gap.size
    thr = 2.0 * fee_sum + edge
    nf = _next_finite(gap, 5)
    cand = np.flatnonzero(np.isfinite(gap) & (np.abs(gap) > thr) & np.isfinite(sigma))
    cand = cand[cand + 1 < n]
    if cand.size == 0:
        return {"entry": np.array([], np.int64), "fill_in": np.array([], np.int64), "exit": np.array([], np.int64), "pnl": np.array([]),
                "gross": np.array([]), "g_in": np.array([]), "candidates": 0, "dropped": 0, "thr": thr}
    fill_in = nf[cand + 1]
    okf = fill_in >= 0
    cand, fill_in = cand[okf], fill_in[okf]
    # first u in (fill, fill + hold] with |gap_u| < 0.5 sigma_u, else fill + hold
    ks = np.arange(1, hold + 1)
    u = fill_in[:, None] + ks[None, :]
    u = np.minimum(u, n - 1)
    with np.errstate(invalid="ignore"):
        cond = np.abs(gap[u]) < EXIT_SIGMA * sigma[u]
    cond = np.where(np.isfinite(gap[u]) & np.isfinite(sigma[u]), cond, False)
    first = np.argmax(cond, axis=1)
    hit = cond[np.arange(cond.shape[0]), first]
    exit_dec = np.where(hit, fill_in + ks[first], fill_in + hold)
    exit_dec = np.minimum(exit_dec, n - 2)
    fill_out = nf[exit_dec + 1]
    oko = fill_out >= 0
    dropped = int((~oko).sum())
    cand, fill_in, fill_out = cand[oko], fill_in[oko], fill_out[oko]
    s = np.sign(gap[cand])
    g_in, g_out = gap[fill_in], gap[fill_out]
    gross_all = s * (g_in - g_out)
    # one position at a time
    keep = np.zeros(cand.size, bool)
    free = -1
    for q in range(cand.size):
        if cand[q] >= free:
            keep[q] = True
            free = fill_out[q] + 1
    pnl = gross_all[keep] - 2.0 * fee_sum
    return {"entry": cand[keep], "fill_in": fill_in[keep], "exit": fill_out[keep], "pnl": pnl, "gross": gross_all[keep],
            "g_in": g_in[keep], "candidates": int(cand.size), "dropped": dropped, "thr": thr}


def leg_decomposition(tr: dict, gap: np.ndarray, cb: np.ndarray, kr: np.ndarray) -> Optional[dict]:
    """Where an ``arb_sim`` cell's gross per trigger comes from (arrays indexed like ``gap``): the Coinbase leg
    -s ln(cb_out / cb_in) and the Kraken leg +s ln(kr_out / kr_in), s = the sign of the trigger gap (sell the rich venue, buy
    the cheap one; the two legs sum to the gross), the mean signed gap s gap at the trigger, at the entry fill and at the exit
    fill, and each leg when its entry fill is one minute later (the close of t + 2). A Kraken leg that carries the gross while
    the trigger gap is mostly gone by the fill and that shrinks under the later fill is venue-level last-print reversion toward
    Coinbase, not a cross-venue gap capture. None without triggers."""
    fi, fo, en = tr.get("fill_in"), tr.get("exit"), tr.get("entry")
    if fi is None or fo is None or en is None or fi.size == 0:
        return None
    s = np.sign(gap[en])
    fi1 = np.minimum(fi + 1, gap.size - 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cb_leg, kr_leg = -s * np.log(cb[fo] / cb[fi]), s * np.log(kr[fo] / kr[fi])
        cb_leg1, kr_leg1 = -s * np.log(cb[fo] / cb[fi1]), s * np.log(kr[fo] / kr[fi1])
    ok = np.isfinite(cb_leg) & np.isfinite(kr_leg)
    ok1 = ok & np.isfinite(cb_leg1) & np.isfinite(kr_leg1)
    if not ok.any():
        return None
    gross = float((cb_leg[ok] + kr_leg[ok]).mean())
    kr_m = float(kr_leg[ok].mean())
    return {"n": int(ok.sum()), "mean_gross": gross, "coinbase_leg": float(cb_leg[ok].mean()), "kraken_leg": kr_m,
            "kraken_leg_share_of_gross": (kr_m / gross) if gross != 0.0 else None,
            "signed_gap_at_trigger": float((s * gap[en])[ok].mean()), "signed_gap_at_fill": float((s * gap[fi])[ok].mean()),
            "signed_gap_at_exit": float((s * gap[fo])[ok].mean()),
            "fill_one_minute_later": {"n": int(ok1.sum()), "coinbase_leg": float(cb_leg1[ok1].mean()) if ok1.any() else None,
                                      "kraken_leg": float(kr_leg1[ok1].mean()) if ok1.any() else None},
            "how_to_read": "a Kraken leg that carries the gross while the signed gap is mostly gone by the fill and that shrinks when its "
                           "fill is one minute later is Kraken last-print reversion toward Coinbase, not a cross-venue gap capture"}


def _legs_txt(L: Optional[dict]) -> str:
    if not L:
        return ""
    later = L["fill_one_minute_later"]
    return (f"its gross by leg: Coinbase {_pc(L['coinbase_leg'], 4)}, Kraken {_pc(L['kraken_leg'], 4)} per trigger ({_pc(L['kraken_leg_share_of_gross'], 0)} of "
            f"the gross); signed gap at trigger {_pc(L['signed_gap_at_trigger'], 3)} -> at fill {_pc(L['signed_gap_at_fill'], 3)} -> at exit "
            f"{_pc(L['signed_gap_at_exit'], 3)}; with the entry fill one minute later the Kraken leg is {_pc(later['kraken_leg'], 4)} (Coinbase "
            f"{_pc(later['coinbase_leg'], 4)}); ")


def _daily_pnl(g: dict, idx_exit: np.ndarray, pnl: np.ndarray, i0: int, i1: int, bills: Optional[Bills], financing: bool = True) -> dict:
    """Daily net P&L over the calendar days of [i0, i1): trade P&L by exit day, minus financing (2 x DTB3 / 365 per day)
    and the weekly transfer fee in weeks with a trade."""
    d0, d1 = int(_day_of(g, i0)), int(_day_of(g, max(i1 - 1, i0)))
    days = np.arange(d0, d1 + 1)
    trade = np.zeros(days.size)
    if idx_exit.size:
        np.add.at(trade, (_day_of(g, idx_exit) - d0).astype(np.int64), pnl)
    fin = np.zeros(days.size)
    if financing and bills is not None:
        fin = -2.0 * np.array([bills.rate(_day_str(d)) for d in days]) / 365.0
    # weekly transfer on Mondays when the previous 7 days had a trade
    had = np.zeros(days.size, bool)
    if idx_exit.size:
        had[(_day_of(g, idx_exit) - d0).astype(np.int64)] = True
    transfer = np.zeros(days.size)
    for q, d in enumerate(days):
        if (d + 3) % 7 == 0 and had[max(0, q - 7):q].any():       # 1970-01-01 was a Thursday: (d + 3) % 7 == 0 -> Monday
            transfer[q] = -TRANSFER_FEE
    net = trade + fin + transfer
    year_of_day = np.array([_day_str(d)[:4] for d in days])
    trig = np.zeros(days.size, np.int64)
    if idx_exit.size:
        np.add.at(trig, (_day_of(g, idx_exit) - d0).astype(np.int64), 1)
    annual = {}
    for y in sorted(set(year_of_day)):
        m = year_of_day == y
        annual[y] = {"net": float(net[m].sum()), "trades_pnl": float(trade[m].sum()), "period_costs": float((fin[m] + transfer[m]).sum()),
                     "triggers": int(trig[m].sum())}
    return {"days": days, "net": net, "trade": trade, "financing": fin, "transfer": transfer, "annual": annual, "year_of_day": year_of_day}


def info_share(p_cb: np.ndarray, p_kr: np.ndarray, lags: int = IS_LAGS) -> Optional[dict]:
    """Hasbrouck information-share bounds for Coinbase from a VECM (beta = (1, -1)) in the Baillie et al. (2002) form:
    IS from the orthogonal complement of alpha and the residual covariance; rows with any missing lag are dropped."""
    P = np.column_stack([p_cb, p_kr])
    dP = np.diff(P, axis=0)
    z = (P[:, 0] - P[:, 1])[:-1]
    n = dP.shape[0]
    if n <= lags + 50:
        return None
    cols = [np.ones(n - lags), z[lags:]]
    for L in range(1, lags + 1):
        cols.append(dP[lags - L:n - L, 0]); cols.append(dP[lags - L:n - L, 1])
    X = np.column_stack(cols)
    Y = dP[lags:]
    ok = np.isfinite(X).all(axis=1) & np.isfinite(Y).all(axis=1)
    X, Y = X[ok], Y[ok]
    if X.shape[0] < 200:
        return None
    B, *_ = np.linalg.lstsq(X, Y, rcond=None)
    E = Y - X @ B
    Om = (E.T @ E) / max(E.shape[0] - X.shape[1], 1)
    a_cb, a_kr = float(B[1, 0]), float(B[1, 1])
    aperp = np.array([a_kr, -a_cb])
    den = float(aperp @ Om @ aperp)
    if not den > 0:
        return None
    out = {}
    for order, name in (((0, 1), "cb_first"), ((1, 0), "kr_first")):
        Pm = np.eye(2)[list(order)]
        F = np.linalg.cholesky(Pm @ Om @ Pm.T)
        a = (Pm @ aperp) @ F
        share = a * a / den
        out[name] = float(share[list(order).index(0)])
    return {"coinbase_upper": max(out.values()), "coinbase_lower": min(out.values()), "alpha_cb": a_cb, "alpha_kr": a_kr, "n": int(X.shape[0])}


def _tier_cells(g: dict, gap: np.ndarray, sigma: np.ndarray, i0: int, i1: int, bills: Optional[Bills]) -> dict:
    """Point estimates for every (Coinbase tier, Kraken tier) pair under maker and taker fees (one simulation per distinct
    fee sum: the rule depends on the tiers only through f_cb + f_kr)."""
    cells, sims = {}, {}
    for cname, cm, ct, _cv in COINBASE_TIERS:
        for kname, km, kt, _kv in KRAKEN_TIERS:
            for reading, fs in (("maker", cm + km), ("taker", ct + kt)):
                fs = round(fs, 8)
                if fs not in sims:
                    r = arb_sim(gap, sigma, fs)
                    ex = r["exit"] + i0
                    dp = _daily_pnl(g, ex, r["pnl"], i0, i1, bills)
                    sims[fs] = {"threshold": r["thr"], "fee_sum_per_leg_pair": fs, "triggers": int(r["pnl"].size), "candidates": r["candidates"],
                                "mean_net_per_trigger": float(r["pnl"].mean()) if r["pnl"].size else None,
                                "mean_gross_per_trigger": float(r["gross"].mean()) if r["gross"].size else None,
                                "total_net": float(dp["net"].sum()), "total_trade_pnl": float(dp["trade"].sum()),
                                "total_period_costs": float(dp["financing"].sum() + dp["transfer"].sum()),
                                "annual": {y: {"net": v["net"], "triggers": v["triggers"]} for y, v in dp["annual"].items()},
                                "_daily": dp["net"], "_trades": r, "_exit_abs": ex}
                cells[f"cb:{cname}|kr:{kname}|{reading}"] = sims[fs]
    return cells


def b6c_kraken_inventory_arb(archive):
    """T-425: the inventory-neutral Coinbase-Kraken rule (threshold = all-in cost + 10 bps, next-minute fills) earns
    positive annual net P&L at the user's fee tier, 2023-2026, 1-minute resolution."""
    tid = "T-425"
    cov = _coverage(archive, tid, need_cb=True)
    need = [DTB3_B] + ([KR_PREFIX + cov["months"][0]] if not cov["kr"] else []) + ([CB_PREFIX + cov["months"][0]] if not cov["cb"] else [])
    miss = _missing(archive, need)
    if miss:
        return miss
    g = _grid_for(archive)
    bills = Bills(_closes(archive, DTB3_B))
    i0, i1 = _idx_range(g, *WIN[tid])
    cb, kr = g["cb_close"][i0:i1], g["kr_close"][i0:i1]
    with np.errstate(invalid="ignore", divide="ignore"):
        gap = np.log(cb / kr)
    aligned = np.isfinite(gap)
    n = int(aligned.sum())
    mu, sigma = _roll_prior(gap, Z_WINDOW, Z_MIN)
    # trailing 60-minute Coinbase return at each minute (regime)
    ret60 = np.full(gap.size, np.nan)
    j60 = np.arange(gap.size) - 60
    okr = (j60 >= 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        ret60[okr] = cb[okr] / cb[np.maximum(j60[okr], 0)] - 1.0
    cells = _tier_cells(g, gap, sigma, i0, i1, bills)
    retail_m, retail_t = f"cb:{RETAIL_PAIR[0]}|kr:{RETAIL_PAIR[1]}|maker", f"cb:{RETAIL_PAIR[0]}|kr:{RETAIL_PAIR[1]}|taker"
    hv_m, hv_t = f"cb:{HIGHVOL_PAIR[0]}|kr:{HIGHVOL_PAIR[1]}|maker", f"cb:{HIGHVOL_PAIR[0]}|kr:{HIGHVOL_PAIR[1]}|taker"
    boot = {}
    for key in (retail_m, retail_t, hv_m, hv_t):
        boot[key] = {kq: vq for kq, vq in _mean_boot(cells[key]["_daily"], 7).items() if kq in ("est", "ci", "ci_mc_se", "p", "p_lt", "reps")}
    legs = {key: leg_decomposition(cells[key]["_trades"], gap, cb, kr) for key in (retail_m, retail_t, hv_m, hv_t)}
    # regime split for the two named maker cells
    regimes = {}
    for key in (retail_m, hv_m):
        tr = cells[key]["_trades"]
        if tr["pnl"].size:
            spike = np.abs(ret60[tr["entry"]]) > VOL_SPIKE
            regimes[key] = {"spike": {"n": int(spike.sum()), "mean_net": float(tr["pnl"][spike].mean()) if spike.any() else None},
                            "calm": {"n": int((~spike).sum()), "mean_net": float(tr["pnl"][~spike].mean()) if (~spike).any() else None}}
        else:
            regimes[key] = {"spike": {"n": 0, "mean_net": None}, "calm": {"n": 0, "mean_net": None}}
    # 5-minute bars (rule 10: the 5 phases pooled)
    five = {}
    for key, pair in (("retail", RETAIL_PAIR), ("highvol", HIGHVOL_PAIR)):
        fs = next(cm for cn, cm, _, _ in COINBASE_TIERS if cn == pair[0]) + next(km for kn, km, _, _ in KRAKEN_TIERS if kn == pair[1])
        per_phase, dailies, triggers = [], [], []
        for ph in range(5):
            idx = np.arange(ph, gap.size, 5)
            gp = gap[idx]
            _, sg = _roll_prior(gp, 288, 144)
            r = arb_sim(gp, sg, fs, hold=3)
            triggers.append(int(r["pnl"].size))
            ex = idx[r["exit"]] + i0 if r["exit"].size else np.array([], np.int64)
            dp = _daily_pnl(g, ex, r["pnl"], i0, i1, bills)
            per_phase.append(float(dp["net"].sum())); dailies.append(dp["net"])
        pooled = np.mean(dailies, axis=0)
        five[key] = {"pooled_total_net": float(pooled.sum()), "per_phase_total_net": per_phase, "range": [min(per_phase), max(per_phase)],
                     "triggers": int(np.mean(triggers)), "_daily": pooled}
    # DSR over the 8 declared cells (4 computed: 1m / 5m x retail / high-volume, maker reading)
    fam = {"1m|retail": cells[retail_m]["_daily"], "1m|highvol": cells[hv_m]["_daily"], "5m|retail": five["retail"]["_daily"], "5m|highvol": five["highvol"]["_daily"]}
    fam_trig = {"1m|retail": cells[retail_m]["triggers"], "1m|highvol": cells[hv_m]["triggers"],
                "5m|retail": five["retail"]["triggers"], "5m|highvol": five["highvol"]["triggers"]}
    fam_sr = {k_: (float(sharpe_ratio(v_)) if v_.size > 2 and v_.std() > 0 and fam_trig[k_] >= FAMILY_MIN_N else None) for k_, v_ in fam.items()}
    dsr = {k_: family_dsr(fam[k_], list(fam_sr.values()), T425_CELLS) for k_ in ("1m|retail", "1m|highvol")}
    # information share per year
    ishare = {}
    days_min = _day_of(g, np.arange(i0, i1))
    udays = np.unique(days_min)
    year_of_day = {int(d): _day_str(int(d))[:4] for d in udays}
    years_min = np.array([year_of_day[int(d)] for d in udays])[np.searchsorted(udays, days_min)]
    for y in sorted(set(years_min)):
        sel = years_min == y
        if sel.sum() < 2000:
            continue
        with np.errstate(invalid="ignore"):
            ishare[y] = info_share(np.log(cb[sel]), np.log(kr[sel]))
    # the user's tier is not recorded: that criterion is None (rule 2 / rule 9 cap); the necessary condition at the most
    # favourable published pair is implemented and can fail decisively (then no tier passes)
    totals = {k_: c_["total_net"] for k_, c_ in cells.items()}
    worst_p = boot[retail_t].get("p")
    best_p = boot[hv_m].get("p")
    best_ci = boot[hv_m].get("ci") or [None, None]
    best_ok = None if best_p is None else bool(best_p < ALPHA and cells[hv_m]["total_net"] > 0)
    best_dec = best_ci[1] is not None and best_ci[1] < 0
    n_pos = sum(1 for t_ in totals.values() if t_ > 0)
    crit = [(f"net P&L > 0 with bootstrap p < 0.05 at the user's tier (the user's Coinbase / Kraken fee tier is not recorded in the repo; "
             f"{n_pos} of {len(totals)} tier pairs x fee readings have a positive total; least favourable pair {RETAIL_PAIR[0]} / {RETAIL_PAIR[1]} taker: "
             f"total {_pc(cells[retail_t]['total_net'])}, p {_f(worst_p, 4)})", None, False),
            (f"necessary for any tier: net P&L > 0 with bootstrap p < 0.05 at the most favourable published pair ({HIGHVOL_PAIR[0]} / {HIGHVOL_PAIR[1]}, maker): "
             f"total {_pc(cells[hv_m]['total_net'])}, daily mean {_pc(boot[hv_m].get('est'), 4)} with one-sided 95% bounds [{_pc(best_ci[0], 4)}, "
             f"{_pc(best_ci[1], 4)}], p {_f(best_p, 4)}", best_ok, best_dec)]
    verdict, why = _judge(crit, n, MIN_N[tid], "aligned minutes", cov["missing"], cov["window"])
    rm, hm = cells[retail_m], cells[hv_m]
    reason = (f"Coinbase/Kraken BTC-USD 1-minute {cov['window']}: covered {_months_txt(cov['covered'])}, {n} aligned minutes; retail pair "
              f"({RETAIL_PAIR[0]} / {RETAIL_PAIR[1]}) maker threshold {_pc(rm['threshold'])}: {rm['triggers']} triggers, mean net per trigger "
              f"{_pc(rm['mean_net_per_trigger'], 3)}, total net {_pc(rm['total_net'])} (trades {_pc(rm['total_trade_pnl'])}, financing + transfers "
              f"{_pc(rm['total_period_costs'])}), p {_f(boot[retail_m].get('p'), 4)}; taker {cells[retail_t]['triggers']} triggers, total "
              f"{_pc(cells[retail_t]['total_net'])}; high-volume pair ({HIGHVOL_PAIR[0]} / {HIGHVOL_PAIR[1]}) maker threshold {_pc(hm['threshold'])}: "
              f"{hm['triggers']} triggers, mean net {_pc(hm['mean_net_per_trigger'], 3)}, total net {_pc(hm['total_net'])}, p {_f(boot[hv_m].get('p'), 4)}; "
              + _legs_txt(legs[hv_m]) + f"annual net (high-volume maker) " + ", ".join(f"{y} {_pc(v_['net'])}" for y, v_ in hm["annual"].items()) + f"; 5-minute pooled total "
              f"{_pc(five['highvol']['pooled_total_net'])} (phases {_pc(five['highvol']['range'][0])}..{_pc(five['highvol']['range'][1])}); spike vs calm mean net "
              f"{_pc(regimes[hv_m]['spike']['mean_net'], 3)} ({regimes[hv_m]['spike']['n']}) vs {_pc(regimes[hv_m]['calm']['mean_net'], 3)} "
              f"({regimes[hv_m]['calm']['n']}); DSR 1m high-volume {_f(dsr['1m|highvol'].get('dsr'))} over {T425_CELLS} cells; Coinbase information share "
              + ", ".join(f"{y} [{_f((v_ or {}).get('coinbase_lower'), 2)}, {_f((v_ or {}).get('coinbase_upper'), 2)}]" for y, v_ in ishare.items()) + " — " + why)
    stat = {"window": cov["window"], "covered_months": _months_txt(cov["covered"]), "missing_months": cov["missing"], "n_aligned_minutes": n,
            "tiers": {"coinbase": [{"tier": a, "maker": b, "taker": c, "verified_in_repo": d} for a, b, c, d in COINBASE_TIERS],
                      "kraken": [{"tier": a, "maker": b, "taker": c, "verified_in_repo": d} for a, b, c, d in KRAKEN_TIERS],
                      "user_tier": None, "note": "the user's Coinbase / Kraken fee tier is not recorded in the repo"},
            "cells": {k_: {q: v_ for q, v_ in c_.items() if not q.startswith("_")} for k_, c_ in cells.items()},
            "bootstrap": boot, "regimes": regimes, "five_minute": {k_: {q: v_ for q, v_ in c_.items() if not q.startswith("_")} for k_, c_ in five.items()},
            "family_sharpes_daily": fam_sr, "family_triggers": fam_trig, "family_min_n": FAMILY_MIN_N,
            "dsr": {k_: {q: v_ for q, v_ in d_.items()} for k_, d_ in dsr.items()},
            "information_share_coinbase": ishare, "costs": {"edge_bps": EDGE_BPS, "hold_minutes": HOLD_MIN, "exit_sigma": EXIT_SIGMA,
                                                           "transfer_fee_btc_per_week": TRANSFER_FEE, "financing": "DTB3 continuous on 2 x notional USD inventory, daily"},
            "criteria": crit, "rule10": "1-minute: every minute is a decision (no phase); 5-minute cell: the 5 phases pooled, range reported",
            "rule12": "trigger on minute t's close (known at t+60 s), fill at minute t+1's close; exits likewise"}
    for k_, L_ in legs.items():                            # where the named cells' gross comes from (venue legs, gap decay)
        stat["cells"][k_]["legs"] = L_
    return _out(stat, n, verdict, reason)


# ======================================================================================================= T-459 ==

def imbalance_z(g: dict, w: int, signed: bool = False) -> np.ndarray:
    """z of the w-minute imbalance against the trailing day (prior 1440 minutes, >= 720 valid): the library's ratio
    (buy - sell) / (buy + sell), or with ``signed`` the raw signed volume buy - sell in BTC (the alternative reading)."""
    b, s = _roll_sum(g["kr_buy"], w), _roll_sum(g["kr_sell"], w)
    tot = b + s
    with np.errstate(invalid="ignore", divide="ignore"):
        I = np.where(tot > 0, (b - s) if signed else (b - s) / np.where(tot > 0, tot, 1.0), np.nan)
    mu, sd = _roll_prior(I, Z_WINDOW, Z_MIN)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (I - mu) / sd
    z[~np.isfinite(z)] = np.nan
    z[~np.isfinite(g["kr_close"])] = np.nan
    return z


def imbalance_trades(g: dict, z: np.ndarray, i0: int, i1: int, h: int, thr: float, maker: bool, fee_m: float = T459_MAKER,
                     fee_t: float = T459_TAKER, strict: bool = False) -> dict:
    """Long trades after z_t > thr in [i0, i1): maker entry (bid at close_t, filled when sell_lo[t+1] <= bid) and maker exit
    (ask at close_{t+h}, filled when buy_hi[t+h+1] >= ask, else taker at close_{t+h+1}); or taker entry at close_{t+1} and
    taker exit at close_{t+h+1}. One position at a time."""
    c, slo, bhi = g["kr_close"], g["kr_slo"], g["kr_bhi"]
    n = c.size
    cand = np.flatnonzero(np.isfinite(z[i0:i1]) & (z[i0:i1] > thr)) + i0
    cand = cand[cand + h + 1 < n]
    nf = _next_finite(c, 5)
    pf = _prev_finite(c, 5)
    out = {"signals": int(cand.size), "entry": np.array([], np.int64), "net": np.array([]), "maker_exit": np.array([], bool), "unfilled": 0}
    if cand.size == 0:
        return out
    keep = np.zeros(cand.size, bool)
    free = -1
    for q in range(cand.size):
        if cand[q] >= free:
            keep[q] = True
            free = cand[q] + h + 2
    cand = cand[keep]
    out["signals_taken"] = int(cand.size)
    if maker:
        bid = c[cand]
        prints = slo[cand + 1]
        filled = np.isfinite(prints) & ((prints < bid) if strict else (prints <= bid))
        out["unfilled"] = int((~filled).sum())
        cand = cand[filled]
        if cand.size == 0:
            return out
        entry_px = c[cand]
        ask_i = pf[cand + h]
        okx = ask_i >= 0
        ask = np.where(okx, c[np.maximum(ask_i, 0)], np.nan)
        hit = np.isfinite(bhi[cand + h + 1]) & (bhi[cand + h + 1] >= ask)
        tk_i = nf[np.minimum(cand + h + 1, n - 1)]
        tk_px = np.where(tk_i >= 0, c[np.maximum(tk_i, 0)], np.nan)
        exit_px = np.where(hit, ask, tk_px)
        fee = fee_m + np.where(hit, fee_m, fee_t)
    else:
        e_i = nf[cand + 1]
        x_i = nf[np.minimum(cand + h + 1, n - 1)]
        ok = (e_i >= 0) & (x_i >= 0)
        cand, e_i, x_i = cand[ok], e_i[ok], x_i[ok]
        entry_px, exit_px = c[e_i], c[x_i]
        hit = np.zeros(cand.size, bool)
        fee = np.full(cand.size, 2.0 * fee_t)
    okp = np.isfinite(entry_px) & np.isfinite(exit_px) & (entry_px > 0) & (exit_px > 0)
    net = np.log(exit_px[okp] / entry_px[okp]) - fee[okp]
    out.update(entry=cand[okp], net=net, maker_exit=hit[okp], gross=net + fee[okp])
    return out


def forward_regression(g: dict, z: np.ndarray, i0: int, i1: int, h: int) -> dict:
    c = g["kr_close"]
    i = np.arange(i0, min(i1, c.size - h))
    with np.errstate(invalid="ignore", divide="ignore"):
        y = np.log(c[i + h] / c[i])
    ok = np.isfinite(y) & np.isfinite(z[i])
    if ok.sum() < 100:
        return {"slope": None, "t": None, "n": int(ok.sum())}
    yy, xx = y[ok], z[i][ok]
    if xx.size > 400_000:                                  # every 2nd minute keeps the regression cheap; overlap handled by the lag
        yy, xx = yy[::2], xx[::2]
    r = ols_nw(yy, xx, max(h, nw_lag(xx.size)))
    return {"slope": r["coef"][1] if r["coef"] else None, "t": r["t"][1] if r["t"] else None, "n": int(xx.size), "r2": r.get("r2")}


def t459_decide(x, labels: Sequence[str], fam: Sequence[Optional[float]]) -> dict:
    """The two out-of-sample criteria of T-459 from the claim cell's trades ``x`` (entry days ``labels``) and the family's
    per-trade Sharpes ``fam``. Both are decided only from the same minimum evidence, MIN_TRADES_DECIDE trades spanning
    MIN_DAYS_DECIDE trade days: below it the bootstraps have no p and the DSR row is None (rule 5: the PSR's normal
    approximation is no bound at 4-6 trades, and a criterion the harness cannot decide for the mean cannot decide its sister
    from the same trades). The DSR and PSR values are still computed from 4 trades on and reported."""
    x = np.asarray(x, float)
    n = int(x.size)
    n_days = len(set(labels))
    enough = n >= MIN_TRADES_DECIDE and n_days >= MIN_DAYS_DECIDE
    empty = {"est": float(x.mean()) if n else None, "ci": [None, None], "p": None, "p_lt": None}
    cs = cluster_stud(x, labels) if enough else {**empty, "clusters": n_days}
    sb = stationary_boot_mean(x, n / max(1, n_days)) if enough else {**empty, "mean_block": None}
    p_ok = _agree(sb.get("p"), cs.get("p"), 0.01)
    p_dec = bool(enough and all(v_ is not None and v_ < 0.01 for v_ in (sb.get("p_lt"), cs.get("p_lt"))))
    dsr = family_dsr(x, fam, T459_CELLS) if n > 3 else {"dsr": None, "psr0": None}
    label = f"DSR >= 0.95 over {T459_CELLS} declared cells (24 computed; family variance from the {len(fam)} cells with >= {FAMILY_MIN_N} trades)"
    if enough:
        dsr_crit = dsr_row(dsr, label)
    else:
        dsr_crit = (f"{label} (n/a: {n} trades on {n_days} days, below the {MIN_TRADES_DECIDE}-trade / {MIN_DAYS_DECIDE}-day minimum the mean-net "
                    f"criterion needs; DSR {_f(dsr.get('dsr'))}, PSR vs 0 {_f(dsr.get('psr0'))} reported, not decided)", None, False)
    return {"cs": cs, "sb": sb, "p_ok": p_ok, "p_dec": p_dec, "dsr": dsr, "dsr_crit": dsr_crit, "n": n, "n_days": n_days, "enough": enough}


def b6c_kraken_flow_imbalance(archive):
    """T-459: a 5-minute signed-volume imbalance above 2 sigma on Kraken BTC-USD predicts a positive 5-minute return large
    enough for the maker-only follow rule to earn a positive mean net return (fit 2023-24, test 2025-26)."""
    tid = "T-459"
    cov = _coverage(archive, tid, need_cb=False)
    if not cov["kr"]:
        return _missing(archive, [KR_PREFIX + cov["months"][0]])
    g = _grid_for(archive)
    first, last = WIN[tid]
    is_last = _months(first, last)[_months(first, last).index(T459_OOS_FIRST) - 1]
    a0, a1 = _idx_range(g, first, is_last)
    b0, b1 = _idx_range(g, T459_OOS_FIRST, last)
    cw, ch, cthr, cmk = T459_CLAIM
    zs = {w: imbalance_z(g, w) for w in sorted({w_ for w_, *_ in T459_GRID} | {cw})}
    # trailing 60-minute realised vol (terciles)
    c = g["kr_close"]
    with np.errstate(invalid="ignore", divide="ignore"):
        r1 = np.log(c[1:] / c[:-1])
    r1 = np.concatenate([[np.nan], r1])
    rv60 = _roll_sum(r1 * r1, 60)
    cells_is, cells_oos = {}, {}
    for w, h, thr, mk in T459_GRID:
        key = f"w{w}|h{h}|z{thr:g}|{'maker' if mk else 'taker'}"
        ti = imbalance_trades(g, zs[w], a0, a1, h, thr, mk)
        to = imbalance_trades(g, zs[w], b0, b1, h, thr, mk)
        cells_is[key] = {"n": int(ti["net"].size), "mean_net": float(ti["net"].mean()) if ti["net"].size else None, "signals": ti["signals"]}
        cells_oos[key] = {"n": int(to["net"].size), "mean_net": float(to["net"].mean()) if to["net"].size else None, "signals": to["signals"],
                          "sharpe_per_trade": float(sharpe_ratio(to["net"])) if to["net"].size > 2 and to["net"].std() > 0 else None, "_t": to}
    best_is = max((k_ for k_, v_ in cells_is.items() if v_["n"] >= 100 and v_["mean_net"] is not None), key=lambda k_: cells_is[k_]["mean_net"], default=None)
    ckey = f"w{cw}|h{ch}|z{cthr:g}|{'maker' if cmk else 'taker'}"
    to = cells_oos[ckey]["_t"]
    x = to["net"]
    n = int(x.size)
    labels = [_day_str(int(d)) for d in _day_of(g, to["entry"])] if n else []
    fam = [v_["sharpe_per_trade"] for v_ in cells_oos.values() if v_["n"] >= FAMILY_MIN_N]
    dec = t459_decide(x, labels, fam)                      # both criteria from the same minimum evidence (rule 5)
    cs, sb, dsr = dec["cs"], dec["sb"], dec["dsr"]
    # the alternative reading of 'signed-volume imbalance': raw buy - sell (BTC) z-scored the same way (reported, not decided)
    z_sv = imbalance_z(g, cw, signed=True)
    alt_is = imbalance_trades(g, z_sv, a0, a1, ch, cthr, cmk)
    alt = imbalance_trades(g, z_sv, b0, b1, ch, cthr, cmk)
    xa = alt["net"]
    la = [_day_str(int(d)) for d in _day_of(g, alt["entry"])] if xa.size else []
    alt_cs = cluster_stud(xa, la) if xa.size >= 8 else {"p": None, "p_lt": None, "ci": [None, None]}
    alt_sb = stationary_boot_mean(xa, xa.size / max(1, len(set(la)))) if xa.size >= 8 else {"p": None, "p_lt": None, "ci": [None, None]}
    alt_out = {"construction": f"z of the {cw}-minute raw signed volume (buy - sell, BTC) against the trailing day; z > {cthr:g}; "
                               f"{'maker-only' if cmk else 'taker'}; same fills and fees",
               "in_sample": {"signals": alt_is["signals"], "n": int(alt_is["net"].size), "mean_net": float(alt_is["net"].mean()) if alt_is["net"].size else None},
               "out_of_sample": {"signals": alt["signals"], "taken": alt.get("signals_taken", 0), "unfilled_bids": alt["unfilled"], "n": int(xa.size),
                                 "mean_net": float(xa.mean()) if xa.size else None, "stationary_p": alt_sb.get("p"), "stationary_p_lt": alt_sb.get("p_lt"),
                                 "cluster_p": alt_cs.get("p"), "cluster_p_lt": alt_cs.get("p_lt"), "ci95": alt_cs.get("ci")}}
    fwd = forward_regression(g, zs[cw], b0, b1, ch) if b1 > b0 else {"slope": None, "t": None, "n": 0}
    fwd_is = forward_regression(g, zs[cw], a0, a1, ch)
    # strict fills, Tier-1 sensitivity, terciles (cutpoints from the in-sample SIGNAL minutes of the claim cell, applied to the OOS trades)
    strict = imbalance_trades(g, zs[cw], b0, b1, ch, cthr, True, strict=True)
    tier1 = imbalance_trades(g, zs[cw], b0, b1, ch, cthr, cmk, fee_m=T459_TIER1[0], fee_t=T459_TIER1[1])
    sig_is = np.flatnonzero(np.isfinite(zs[cw][a0:a1]) & (zs[cw][a0:a1] > cthr)) + a0
    rv_is = rv60[sig_is]
    rv_is = rv_is[np.isfinite(rv_is)]
    terc, cuts = {}, None
    if rv_is.size >= TERCILE_MIN_SIGNALS and n:
        cuts = np.quantile(rv_is, [1 / 3, 2 / 3])
        lab = np.digitize(rv60[to["entry"]], cuts)
        for q, name in enumerate(("low", "mid", "high")):
            sel = lab == q
            terc[name] = {"n": int(sel.sum()), "mean_net": float(x[sel].mean()) if sel.any() else None}
    ev = "" if dec["enough"] else f" [not decided: {n} trades on {dec['n_days']} days, below the {MIN_TRADES_DECIDE}-trade / {MIN_DAYS_DECIDE}-day minimum]"
    crit = [
        (f"out-of-sample mean net per trade {_pc(cs.get('est'), 3)} > 0 with p < 0.01: stationary block bootstrap with 1-day blocks (mean block "
         f"{_f(sb.get('mean_block'), 1)} trades) p {_f(sb.get('p'), 4)}, 95% percentile CI [{_pc((sb.get('ci') or [None])[0], 3)}, "
         f"{_pc((sb.get('ci') or [None, None])[1], 3)}]; the day-cluster studentized bootstrap must agree: p {_f(cs.get('p'), 4)} "
         f"({cs.get('clusters', 0)} days), 95% CI [{_pc((cs.get('ci') or [None])[0], 3)}, {_pc((cs.get('ci') or [None, None])[1], 3)}]" + ev,
         dec["p_ok"], dec["p_dec"]),
        dec["dsr_crit"],
    ]
    verdict, why = _judge(crit, n, MIN_N[tid], "out-of-sample trades", cov["missing"], cov["window"])
    oos_cov = [m for m in cov["covered"] if m >= T459_OOS_FIRST]
    reason = (f"Kraken XBTUSD 1-minute bars {cov['window']} (in-sample {first}..{is_last}, out of sample {T459_OOS_FIRST}..{last}): covered "
              f"{_months_txt(cov['covered'])} (out-of-sample months stored: {_months_txt(oos_cov) if oos_cov else 'none'}); claim cell {ckey} out of "
              f"sample: {to['signals']} signals, {to.get('signals_taken', 0)} taken, {to['unfilled']} unfilled bids, {n} trades on {dec['n_days']} days, "
              f"mean net {_pc(cs.get('est'), 3)} "
              f"(stationary 1-day-block p {_f(sb.get('p'), 4)}, day-cluster p {_f(cs.get('p'), 4)}), "
              f"maker exits {_pc(float(to['maker_exit'].mean()) if n else None, 1)}, strict-fill mean net {_pc(float(strict['net'].mean()) if strict['net'].size else None, 3)} "
              f"({strict['net'].size}), Tier-1 fees {_pc(float(tier1['net'].mean()) if tier1['net'].size else None, 3)}; in-sample claim cell "
              f"{cells_is[ckey]['n']} trades mean net {_pc(cells_is[ckey]['mean_net'], 3)}; in-sample best cell {best_is} "
              f"({_pc(cells_is[best_is]['mean_net'], 3) if best_is else 'n/a'}) out of sample {_pc(cells_oos[best_is]['mean_net'], 3) if best_is else 'n/a'} "
              f"({cells_oos[best_is]['n'] if best_is else 0}); forward 5-minute return on z: slope {_f(fwd['slope'], 6)} (HAC t {_f(fwd['t'], 2)}, n {fwd['n']}) "
              f"out of sample, in-sample t {_f(fwd_is['t'], 2)}; vol terciles (cutpoints from {rv_is.size} in-sample signal minutes) "
              + (", ".join(f"{k_} {_pc(v_['mean_net'], 3)} ({v_['n']})" for k_, v_ in terc.items())
                 or ("n/a (no out-of-sample trades)" if not n else f"n/a (fewer than {TERCILE_MIN_SIGNALS} in-sample signals)"))
              + f"; DSR {_f(dsr.get('dsr'))} (PSR vs 0 {_f(dsr.get('psr0'))}; {len(fam)} cells with >= {FAMILY_MIN_N} trades in the family variance; "
              + (f"decided from {n} trades on {dec['n_days']} days" if dec["enough"] else
                 f"{n} trades on {dec['n_days']} days are below the {MIN_TRADES_DECIDE}-trade / {MIN_DAYS_DECIDE}-day minimum: reported, not decided")
              + f"); alternative reading (raw signed volume z > {cthr:g}): "
              f"in-sample {alt_out['in_sample']['n']} trades mean net {_pc(alt_out['in_sample']['mean_net'], 3)}, out of sample {alt_out['out_of_sample']['n']} trades "
              f"mean net {_pc(alt_out['out_of_sample']['mean_net'], 3)} (stationary p {_f(alt_out['out_of_sample']['stationary_p'], 4)}) — " + why)
    stat = {"window": cov["window"], "in_sample": f"{first}..{is_last}", "out_of_sample": f"{T459_OOS_FIRST}..{last}", "covered_months": _months_txt(cov["covered"]),
            "missing_months": cov["missing"], "oos_months_stored": oos_cov, "n_oos_trades": n, "claim_cell": ckey,
            "oos": {"signals": to["signals"], "taken": to.get("signals_taken", 0), "unfilled_bids": to["unfilled"], "mean_net": cs.get("est"),
                    "stationary_boot": {kq: sb.get(kq) for kq in ("est", "ci", "ci_mc_se", "p", "p_mc_se", "p_lt", "mean_block", "reps")},
                    "cluster_boot": {kq: cs.get(kq) for kq in ("est", "se", "ci", "ci90", "p", "p_lt", "clusters")},
                    "rule11": "the stationary block bootstrap (the trial's null) and the day-cluster studentized bootstrap must agree",
                    "maker_exit_share": float(to["maker_exit"].mean()) if n else None,
                    "strict_fill": {"n": int(strict["net"].size), "mean_net": float(strict["net"].mean()) if strict["net"].size else None},
                    "tier1_fees": {"n": int(tier1["net"].size), "mean_net": float(tier1["net"].mean()) if tier1["net"].size else None},
                    "n_days": dec["n_days"], "minimum_evidence": {"trades": MIN_TRADES_DECIDE, "days": MIN_DAYS_DECIDE, "met": dec["enough"],
                                                                  "note": "both out-of-sample criteria (mean net, DSR row) are decided only above it"}},
            "in_sample_claim_cell": cells_is[ckey], "in_sample_best": best_is, "cells_in_sample": cells_is,
            "cells_out_of_sample": {k_: {q: v_ for q, v_ in c_.items() if not q.startswith("_")} for k_, c_ in cells_oos.items()},
            "forward_regression_oos": fwd, "forward_regression_is": fwd_is, "vol_terciles_oos": terc,
            "vol_terciles_cutpoints": {"rv60": None if cuts is None else [float(c_) for c_ in cuts], "n_in_sample_signals": int(rv_is.size),
                                       "min_signals": TERCILE_MIN_SIGNALS, "source": "in-sample signal minutes of the claim cell"},
            "dsr": dsr, "family_min_n": FAMILY_MIN_N,
            "alternative_reading_signed_volume": alt_out,
            "signal_note": "the library's ratio imbalance on thin Kraken minutes rarely exceeds 2 trailing-day sigmas (bounded at 1, sd about 0.64)",
            "fees": {"maker": T459_MAKER, "taker": T459_TAKER, "sensitivity_tier1": T459_TIER1}, "criteria": crit,
            "rule12": "signal from the closed minute t (known at t+60 s); fills by later prints through the resting quote",
            "rule10": "signal-driven entries: no grid phase"}
    return _out(stat, n, verdict, reason)


# ======================================================================================================= T-465 ==

def vpin_buckets(g: dict, frac: int) -> dict:
    """Volume buckets of ADV / frac from the Kraken 1-minute buy / sell volumes (pro-rata split at boundaries): per bucket
    the imbalance |buy - sell| / bucket and the grid minute index at whose END the bucket is known."""
    vol, buy = g["kr_vol"], g["kr_buy"]
    N = g["N"]
    v = np.where(np.isfinite(vol), vol, 0.0)
    b = np.where(np.isfinite(buy), buy, 0.0)
    cum_v = np.concatenate([[0.0], np.cumsum(v)])          # cum_v[i] = volume before minute i; cum_v[i+1] after it
    cum_b = np.concatenate([[0.0], np.cumsum(b)])
    day_idx = _day_of(g, np.arange(N))
    d0 = int(day_idx[0])
    nd = int(day_idx[-1]) - d0 + 1
    dvol = np.zeros(nd)
    np.add.at(dvol, (day_idx - d0).astype(np.int64), v)
    imb, known = [], []
    x_start, started = 0.0, False
    for d in range(nd):
        lo = max(0, d - ADV_DAYS)
        hist = dvol[lo:d]
        if hist.size < ADV_MIN_DAYS or not hist.mean() > 0:
            continue
        V = hist.mean() / frac
        i_a = int(np.searchsorted(day_idx, d0 + d, side="left"))
        i_b = int(np.searchsorted(day_idx, d0 + d, side="right"))
        x_end = cum_v[i_b]
        if not started:                                        # the first bucket opens with the first eligible day
            x_start, started = float(cum_v[i_a]), True
        kmax = int(math.floor((x_end - x_start) / V))
        if kmax <= 0:
            continue
        bounds = x_start + V * np.arange(1, kmax + 1)
        prev = np.concatenate([[x_start], bounds[:-1]])
        bb = np.interp(bounds, cum_v, cum_b) - np.interp(prev, cum_v, cum_b)
        imb.extend(np.abs(2.0 * bb - V) / V)
        j = np.searchsorted(cum_v, bounds, side="left") - 1      # minute whose end reaches the boundary
        known.extend(np.minimum(np.maximum(j, 0), N - 1))
        x_start = bounds[-1]
    return {"imb": np.array(imb, float), "known_minute": np.array(known, np.int64), "n_buckets": len(imb)}


def vpin_hourly(bk: dict, H: int, window: int) -> np.ndarray:
    """VPIN at each hour mark h (grid hour index): the mean imbalance of the last ``window`` buckets whose closing minute
    ended at or before the mark (minute index <= 60 h - 1)."""
    out = np.full(H + 1, np.nan)
    if bk["n_buckets"] < window:
        return out
    order = np.argsort(bk["known_minute"], kind="stable")
    km = bk["known_minute"][order]
    ci = np.concatenate([[0.0], np.cumsum(bk["imb"][order])])
    marks = 60 * np.arange(H + 1) - 1
    cnt = np.searchsorted(km, marks, side="right")
    ok = cnt >= window
    out[ok] = (ci[cnt[ok]] - ci[cnt[ok] - window]) / window
    return out


def trailing_cdf(x: np.ndarray, win: int = CDF_HOURS) -> np.ndarray:
    """Empirical CDF of x[t] within the prior ``win`` values (NaN until at least win/2 are finite)."""
    n = x.size
    out = np.full(n, np.nan)
    for t in range(1, n):
        if not np.isfinite(x[t]):
            continue
        w = x[max(0, t - win):t]
        w = w[np.isfinite(w)]
        if w.size >= win // 2:
            out[t] = float((w <= x[t]).mean())
    return out


def hourly_rv(g: dict) -> tuple:
    """(RV, volume) per grid hour from the Coinbase candles: sum of squared 1-minute log close returns (>= 30 returns)."""
    c, v = g["cb_close"], g["cb_vol"]
    H = g["H"]
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.log(c[1:] / c[:-1])
    r = np.concatenate([[np.nan], r])
    r2 = np.where(np.isfinite(r), r * r, 0.0)[:60 * H].reshape(H, 60)
    cnt = np.isfinite(r)[:60 * H].reshape(H, 60).sum(axis=1)
    rv = r2.sum(axis=1)
    rv[cnt < RV_MIN_RETURNS] = np.nan
    vol = np.where(np.isfinite(v), v, 0.0)[:60 * H].reshape(H, 60).sum(axis=1)
    vol[cnt < RV_MIN_RETURNS] = np.nan
    return rv, vol


def har_design(rv: np.ndarray, vol: np.ndarray) -> np.ndarray:
    """Columns at hour h: log RV[h-1], log mean RV[h-24..h-1], log mean RV[h-168..h-1], log volume[h-1]."""
    H = rv.size
    lrv = np.log(np.maximum(rv, 1e-14))
    lrv[~np.isfinite(rv)] = np.nan
    m24, _ = _roll_prior(rv, 24, 20)
    m168, _ = _roll_prior(rv, 168, 140)
    lag1 = np.concatenate([[np.nan], lrv[:-1]])
    lvol = np.concatenate([[np.nan], np.log(np.maximum(vol[:-1], 1e-9))])
    lvol[1:][~np.isfinite(vol[:-1])] = np.nan
    with np.errstate(invalid="ignore", divide="ignore"):
        X = np.column_stack([lag1, np.log(m24), np.log(m168), lvol])
    return X


def har_test(y: np.ndarray, X: np.ndarray, extra: np.ndarray, burn_in: Optional[int] = None, refit: int = REFIT_HOURS, weekend: Optional[np.ndarray] = None) -> dict:
    """In-sample incremental R^2 and Newey-West t of ``extra`` in y ~ X + extra, and the expanding-window walk-forward
    QLIKE Diebold-Mariano test (restricted vs full, forecasts exp(yhat + s^2/2), refit every ``refit`` hours)."""
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1) & np.isfinite(extra)
    y, X, e = y[ok], X[ok], extra[ok]
    wk = weekend[ok] if weekend is not None else None
    n = y.size
    out = {"n": int(n), "incr_r2": None, "t": None, "coef": None, "r2_full": None, "r2_restricted": None, "dm": None, "n_oos": 0}
    if n < 400:
        return out
    L = nw_lag(n)
    full = ols_nw(y, np.column_stack([X, e]), L)
    rest = ols_nw(y, X, L)
    out.update(r2_full=full["r2"], r2_restricted=rest["r2"], incr_r2=(full["r2"] - rest["r2"]) if full["r2"] is not None else None,
               t=full["t"][-1] if full["t"] else None, coef=full["coef"][-1] if full["coef"] else None, lag=L)
    # walk-forward
    B = BURN_IN_HOURS if burn_in is None else int(burn_in)
    B = min(B, n // 2)
    if n - B < 200:
        return out
    Zf = np.column_stack([np.ones(n), X, e])
    Zr = Zf[:, :-1]
    fc_f, fc_r = np.full(n, np.nan), np.full(n, np.nan)          # point forecasts of log RV
    s2_f, s2_r = np.full(n, np.nan), np.full(n, np.nan)          # residual variances of the fit in force
    for k0 in range(B, n, refit):
        k1 = min(n, k0 + refit)
        for Z, fc, s2a in ((Zf, fc_f, s2_f), (Zr, fc_r, s2_r)):
            bq, *_ = np.linalg.lstsq(Z[:k0], y[:k0], rcond=None)
            res = y[:k0] - Z[:k0] @ bq
            s2a[k0:k1] = float(res @ res) / max(k0 - Z.shape[1], 1)
            fc[k0:k1] = Z[k0:k1] @ bq
    sel = np.isfinite(fc_f)
    rv = np.exp(y[sel])
    Ff, Fr = np.exp(fc_f[sel] + 0.5 * s2_f[sel]), np.exp(fc_r[sel] + 0.5 * s2_r[sel])
    ql = lambda F: rv / F - np.log(rv / F) - 1.0
    d = ql(Fr) - ql(Ff)
    dm = hac_mean(d)
    yo = y[sel]
    sse_f, sse_r = float(((yo - fc_f[sel]) ** 2).sum()), float(((yo - fc_r[sel]) ** 2).sum())
    out.update(dm={"mean_gain": dm["mean"], "t": dm["t"], "p": dm["p"], "p_lt": (1.0 - dm["p"]) if dm["p"] is not None else None, "lag": dm["lag"]},
               n_oos=int(sel.sum()), oos_r2_gain_log=(1.0 - sse_f / sse_r) if sse_r > 0 else None,
               qlike_full=float(ql(Ff).mean()), qlike_restricted=float(ql(Fr).mean()))
    if wk is not None:
        reg = {}
        for name, m in (("weekend", wk[sel]), ("weekday", ~wk[sel])):
            if m.sum() >= 100:
                dd = hac_mean(d[m])
                reg[name] = {"n_oos": int(m.sum()), "dm_t": dd["t"], "dm_p": dd["p"]}
            else:
                reg[name] = {"n_oos": int(m.sum()), "dm_t": None, "dm_p": None}
        # in-sample incremental R^2 per regime
        for name, m in (("weekend", wk), ("weekday", ~wk)):
            if m.sum() >= 400:
                Lr = nw_lag(int(m.sum()))
                f_, r_ = ols_nw(y[m], np.column_stack([X[m], e[m]]), Lr), ols_nw(y[m], X[m], Lr)
                reg.setdefault(name, {}).update(incr_r2=(f_["r2"] - r_["r2"]) if f_["r2"] is not None else None, t=f_["t"][-1] if f_["t"] else None)
        out["regimes"] = reg
    return out


def b6c_kraken_vpin_volatility(archive):
    """T-465: VPIN from Kraken signed volume adds >= 2% incremental R^2 (t > 3) for next-hour realised volatility over a
    HAR model with lagged RV and volume, with an out-of-sample QLIKE gain (DM p < 0.05), 2023-2026."""
    tid = "T-465"
    cov = _coverage(archive, tid, need_cb=True)
    if not cov["kr"] or not cov["cb"]:
        need = [KR_PREFIX + cov["months"][0]] if not cov["kr"] else [CB_PREFIX + cov["months"][0]]
        return _missing(archive, need)
    g = _grid_for(archive)
    i0, i1 = _idx_range(g, *WIN[tid])
    H = g["H"]
    h0, h1 = i0 // 60, i1 // 60
    rv, vol = hourly_rv(g)
    X = har_design(rv, vol)
    y = np.log(np.maximum(rv, 1e-14)); y[~np.isfinite(rv)] = np.nan
    hours = np.arange(H)
    inwin = (hours >= h0) & (hours < h1)
    wk_day = ((g["T0"] + 3600 * hours) // 86400 + 3) % 7       # 0 = Monday
    weekend = wk_day >= 5
    cells = {}
    bk_cache = {}
    for frac in VPIN_BUCKETS:
        bk_cache[frac] = vpin_buckets(g, frac)
        for win in VPIN_WINDOWS:
            vp = vpin_hourly(bk_cache[frac], H, win)[:H]
            cdf = trailing_cdf(vp) if np.isfinite(vp).sum() > CDF_HOURS // 2 else np.full(H, np.nan)
            for reg_name, ex in (("level", vp), ("cdf", cdf)):
                yy, XX, ee = np.where(inwin, y, np.nan), X, np.where(inwin, ex, np.nan)
                cells[f"bucket1/{frac}|win{win}|{reg_name}"] = har_test(yy, XX, ee, weekend=weekend)
    ckey = f"bucket1/{VPIN_BUCKETS[0]}|win{VPIN_WINDOWS[0]}|level"
    hc = cells[ckey]
    n = int(hc["n"])
    dm = hc.get("dm") or {}
    p_sidak = _sidak(dm.get("p"), T465_CELLS)
    crit = [
        (f"incremental R^2 {_pc(hc.get('incr_r2'), 2)} >= 2% with Newey-West t {_f(hc.get('t'), 2)} > 3 (coefficient {_f(hc.get('coef'), 4)}, lag {hc.get('lag')}, "
         f"HAR + volume R^2 {_pc(hc.get('r2_restricted'), 1)})",
         None if hc.get("incr_r2") is None or hc.get("t") is None else (hc["incr_r2"] >= 0.02 and hc["t"] > 3.0), False),
        (f"Diebold-Mariano p {_f(dm.get('p'), 4)} < 0.05 out of sample (QLIKE gain {_f(dm.get('mean_gain'), 5)}, t {_f(dm.get('t'), 2)}, {hc.get('n_oos', 0)} hours; "
         f"Sidak-adjusted for {T465_CELLS} cells {_f(p_sidak, 4)})",
         None if dm.get("p") is None else dm["p"] < ALPHA, dm.get("p_lt") is not None and dm["p_lt"] < ALPHA),
    ]
    verdict, why = _judge(crit, n, MIN_N[tid], "hourly observations", cov["missing"], cov["window"])
    regs = hc.get("regimes") or {}
    reason = (f"BTC-USD hourly {cov['window']}: covered {_months_txt(cov['covered'])}; {n} hourly observations ({bk_cache[VPIN_BUCKETS[0]]['n_buckets']} "
              f"VPIN buckets of ADV/{VPIN_BUCKETS[0]}); claim cell {ckey}: HAR + volume R^2 {_pc(hc.get('r2_restricted'), 1)}, with VPIN {_pc(hc.get('r2_full'), 1)} "
              f"(incremental {_pc(hc.get('incr_r2'), 2)}, t {_f(hc.get('t'), 2)}); walk-forward {hc.get('n_oos', 0)} hours: QLIKE {_f(hc.get('qlike_restricted'), 4)} -> "
              f"{_f(hc.get('qlike_full'), 4)}, DM t {_f(dm.get('t'), 2)} p {_f(dm.get('p'), 4)} (Sidak x{T465_CELLS} {_f(p_sidak, 4)}), out-of-sample log-RV R^2 gain "
              f"{_pc(hc.get('oos_r2_gain_log'), 2)}; weekend / weekday incremental R^2 {_pc((regs.get('weekend') or {}).get('incr_r2'), 2)} / "
              f"{_pc((regs.get('weekday') or {}).get('incr_r2'), 2)}, DM p {_f((regs.get('weekend') or {}).get('dm_p'), 3)} / {_f((regs.get('weekday') or {}).get('dm_p'), 3)}; "
              f"cells: " + ", ".join(f"{k_} R2+{_pc(v_.get('incr_r2'), 2)} t {_f(v_.get('t'), 1)} DM p {_f((v_.get('dm') or {}).get('p'), 3)}" for k_, v_ in cells.items())
              + " — " + why)
    stat = {"window": cov["window"], "covered_months": _months_txt(cov["covered"]), "missing_months": cov["missing"], "n_hours": n, "n_oos_hours": hc.get("n_oos", 0),
            "claim_cell": ckey, "headline": {k_: v_ for k_, v_ in hc.items()}, "dm_p_sidak8": p_sidak,
            "cells": {k_: {q: v_ for q, v_ in c_.items() if q != "regimes"} for k_, c_ in cells.items()},
            "buckets": {f"1/{f_}": b_["n_buckets"] for f_, b_ in bk_cache.items()}, "burn_in_hours": BURN_IN_HOURS, "refit_hours": REFIT_HOURS,
            "criteria": crit, "rule12": "VPIN from buckets whose closing minute ended at or before the hour mark; RV over the following hour",
            "rule10": "hourly UTC marks: the claim's calendar"}
    return _out(stat, n, verdict, reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_kraken_cross_venue_gap": b6c_kraken_cross_venue_gap,
    "b6c_kraken_inventory_arb": b6c_kraken_inventory_arb,
    "b6c_kraken_flow_imbalance": b6c_kraken_flow_imbalance,
    "b6c_kraken_vpin_volatility": b6c_kraken_vpin_volatility,
}

THEORY_MAP = {
    "T-331": "b6c_kraken_cross_venue_gap",
    "T-425": "b6c_kraken_inventory_arb",
    "T-459": "b6c_kraken_flow_imbalance",
    "T-465": "b6c_kraken_vpin_volatility",
}
