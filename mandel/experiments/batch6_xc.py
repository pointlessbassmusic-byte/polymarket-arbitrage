"""
Batch 6a, group ``xc``: crypto model-priced hedging claims and captured-chain arbitrage claims.
==============================================================================================

Five options-library claims, each tested against its claim, trial.pass and trial.min_n as worded.

MODEL-PRICED on BTC (Black-Scholes at sigma = DVOL/100, r = q = 0, the Black-76 price on a forward that carries no basis;
every result is labelled MODEL-PRICED):
  * T-255 a short 30-day ATM BTC straddle, delta-hedged at every daily close with the BS delta at that day's DVOL;
    mean P&L per non-overlapping 30-day cycle / premium, studentized block-bootstrap CI, halves, Sharpe after fees;
  * T-261 a short 15-delta inverse BTC strangle (premium booked in coin): variance of the 30-day USD P&L when hedged with
    the coin-corrected delta (BS delta minus the coin premium held) over the variance with the naive BS delta.

Captured CBOE chains (two capture days so far, 2026-10-14 and 2026-10-15; each pre-open capture carries the previous
session's closing quotes, so its quote day is the prior trading day and spot is that day's RAW close):
  * T-194 SPY parity-implied financing rate ln(F_spy / SPY) / T + 0.0945% vs the SPXW box rate at the nearest expiry,
    for SPY expiries 30-64 DTE before the 2026-12-18 ex-date. The claim counts EXPIRIES (min_n 10) and its pass needs
    "day one and >= 80% of 20 captured days", so two capture days cannot confirm it;
  * T-199 GLD option-implied financing rate (ATM +/- 3 strikes, 90-365 DTE) within 50 bp of the 3-month bill - 0.40%:
    the claim counts STRIKE/EXPIRY PAIRS on the capture day (min_n 30), so day one can decide it;
  * T-137 near-ATM parity deviations (3 strikes nearest spot, every expiry) on SPX (European, parity forward) and SPY /
    GLD / IBIT (American no-arbitrage bounds): the claim counts PAIRS (min_n 500, met), but its pass also needs a
    day-clustered CI, which needs at least 5 capture days (the registry's own blocked_on note). Reported beside it: the
    quote-synchronous spot the 1-10 DTE parity implies per day and symbol, and the shares re-judged at that spot.

Conventions:
  * Point in time. BTC closes (Yahoo daily bar, 00:00-24:00 UTC) and DVOL (Deribit daily candle keyed by its open) are
    keyed by the same day, so the DVOL close used on day d is the value at 24:00 UTC of d, simultaneous with the BTC
    close. The 3-month bill is FRED DTB3, a discount yield published the next day: each capture uses the latest print
    dated strictly before the quote day, converted to a continuous rate r = -ln(1 - d/100 * 91/360) / (91/365).
    T-199 names FRED DGS3MO (a bond-equivalent yield, continuous r = ln(1 + y/100 * 91/365) / (91/365)), which sits
    7-9 bp above DTB3 on the capture days: it uses the archived fred-DGS3MO when present and, until that bundle is
    archived, the two FRED prints in DGS3MO_REF, with the DTB3 result reported next to it.
  * Chains. Crossed (ask < bid) and zero-bid quotes are excluded; mids are (bid + ask) / 2. SPX and SPXW roots are kept
    apart (AM-settled SPX monthlies never stand in for a PM SPXW expiry). T = calendar days from the quote day / 365.
  * SPY dividends come from the adjclose/close ratio step (D = close[i-1] (1 - f[i-1]/f[i]), f = adjclose/close); the
    next ones are forecast as the last dividend paid, going ex on the third Friday of Mar/Jun/Sep/Dec (the Thursday
    before when Juneteenth closes that Friday).
  * Intervals. Studentized (bootstrap-t) circular block bootstrap of a mean (Bartlett long-run s.e., bandwidth = block);
    percentile paired block bootstrap of a variance ratio; a day-clustered bootstrap for a share of pairs.
  * min_n in the claim's own units. Below min_n a claim cannot be supported, and a failing criterion counts only when
    it fails decisively (its interval wholly on the wrong side, or the failure would persist at min_n); otherwise it is
    reported as not decisive (None) and the verdict is inconclusive.

Verdicts use ``underlying2._verdict``: any implemented criterion failing gives not_supported; any criterion not
implemented gives at best inconclusive; supported only when every criterion is implemented and passes.
"""

from __future__ import annotations

import math
import re
from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

import numpy as np

from mandel.experiments.underlying2 import _verdict
from mandel.experiments.volatility import _quote_day, index_closes
from mandel.options import bs
from mandel.validation.backtest_eval import _hac_var, deflated_sharpe_ratio, sharpe_ratio

CRYPTO_PPY = 365
HOLD = 30
BTC_B = "daily-history-BTC-USD"
DVOL_B = "deribit-dvol-BTC-history"
DTB3_B = "fred-DTB3"
DGS3MO_B = "fred-DGS3MO"
DGS2_B = "fred-DGS2"
# T-199's named bill. fred-DGS3MO is not archived yet; these FRED DGS3MO prints (percent, bond-equivalent; read once,
# read-only, from fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO on 2026-10-15, where the same file's DTB3 column
# matches the archived fred-DTB3: 4.06 and 4.09) stand in for it only until it is archived, and only for a quote day
# whose latest FRED print day is one of these keys.
DGS3MO_REF = {"2026-10-09": 4.25, "2026-10-13": 4.26}
SPY_B = "daily-history-SPY"
GSPC_B = "daily-history--GSPC"
VIX_B = "cboe-VIX-history"
HIST_B = {"SPX": GSPC_B, "SPY": SPY_B, "GLD": "daily-history-GLD", "IBIT": "daily-history-IBIT", "SLV": "daily-history-SLV"}
CHAIN_P = "options-chain-"
DSURF_P = "deribit-surface-BTC-"
MP = "MODEL-PRICED"
SPY_FEE = 0.000945               # SPY expense ratio, as the T-194 claim states it
GLD_FEE = 0.0040                 # GLD sponsor fee (T-199)
SLV_FEE = 0.0050                 # SLV sponsor fee (reported alongside T-199)
DERIBIT_OPT_FEE = 0.0003         # Deribit option fee: 0.03% of the underlying per leg, capped at 12.5% of the option price
DERIBIT_PERP_FEE = 0.0005        # Deribit perpetual taker fee on the hedge's traded notional
FUNDING_BP_DAY = 1.0             # T-255 control: 1 bp/day funding on the hedge notional
MIN_DAYS_SHARE = 5               # fewest capture days that can resolve an "80% of captured days" share or a day-clustered CI

T255_MIN_N = 36                  # trial.min_n, non-overlapping 30-day cycles
T261_MIN_N = 36                  # trial.min_n, non-overlapping 30-day cycles
T194_MIN_N = 10                  # trial.min_n, matched expiries
T194_DAYS = 20                   # pass: ">= 80% of 20 captured days"
T199_MIN_N = 30                  # trial.min_n, strike/expiry pairs
T137_MIN_N = 500                 # trial.min_n, near-ATM strike/expiry pairs


# =================================================================================================== statistics ==

def _boot_idx(rng, n: int, block: int, k: int) -> np.ndarray:
    nb = math.ceil(n / block)
    starts = rng.integers(0, n, size=(k, nb))
    return (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(k, -1)[:, :n] % n


def stud_ci(x, block: int, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> tuple:
    """Two-sided studentized circular block-bootstrap CI of the mean at ``level``: (lo, hi), or (None, None) below 8
    observations. Each resample's mean is studentized by its own Bartlett long-run s.e. (bandwidth = block)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 8:
        return None, None
    block = max(1, min(int(block), n // 4))
    m = float(x.mean())
    v0 = float(_hac_var(x[None, :], block)[0])
    if v0 <= 1e-30:
        return m, m
    se = math.sqrt(v0 / n)
    rng = np.random.default_rng(seed)
    xb = x[_boot_idx(rng, n, block, n_boot)]
    t = (xb.mean(axis=1) - m) / np.sqrt(_hac_var(xb, block) / n)
    a = (1.0 - level) / 2.0
    return m - float(np.quantile(t, 1.0 - a)) * se, m - float(np.quantile(t, a)) * se


def var_ratio_ci(num, den, block: int, level: float = 0.95, n_boot: int = 2000, seed: int = 0) -> dict:
    """var(num) / var(den) for two series on one timeline, with a percentile circular block-bootstrap CI that resamples
    the SAME blocks for both (paired). Fewer than 8 points: no interval."""
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    n = num.size
    vd = float(den.var(ddof=1)) if n > 1 else 0.0
    ratio = float(num.var(ddof=1) / vd) if n > 1 and vd > 0 else None
    if n < 8 or ratio is None:
        return {"ratio": ratio, "lo": None, "hi": None}
    block = max(1, min(int(block), n // 4))
    rng = np.random.default_rng(seed)
    idx = _boot_idx(rng, n, block, n_boot)
    vn = num[idx].var(axis=1, ddof=1)
    vdd = den[idx].var(axis=1, ddof=1)
    r = vn[vdd > 0] / vdd[vdd > 0]
    a = (1.0 - level) / 2.0
    return {"ratio": ratio, "lo": float(np.quantile(r, a)), "hi": float(np.quantile(r, 1.0 - a))}


def day_cluster_share_ci(flags_by_day: Sequence[Sequence[bool]], level: float = 0.95, n_boot: int = 4000, seed: int = 0) -> tuple:
    """Pooled share of flagged pairs with a percentile cluster bootstrap over capture days (whole days resampled with
    replacement, share = total flags / total pairs). Fewer than MIN_DAYS_SHARE days: (None, None)."""
    days = [np.asarray(f, dtype=float) for f in flags_by_day if len(f)]
    if len(days) < MIN_DAYS_SHARE:
        return None, None
    k = np.array([d.sum() for d in days])
    m = np.array([d.size for d in days], dtype=float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(days), size=(n_boot, len(days)))
    s = k[pick].sum(axis=1) / m[pick].sum(axis=1)
    a = (1.0 - level) / 2.0
    return float(np.quantile(s, a)), float(np.quantile(s, 1.0 - a))


def _share_fails_at_min_n(hits: int, n: int, min_n: int, need: float) -> bool:
    """A 'share >= need' criterion fails at min_n even if every missing observation were a hit."""
    return n < min_n and (hits + (min_n - n)) / min_n < need


def _days_share(passes: Sequence[Optional[bool]], need: float, min_days: int) -> Optional[bool]:
    """'Passes on >= need of the captured days', judged over ALL the captured days passed in once at least ``min_days``
    exist (a claim that names a day count, like T-194's '20 captured days', slices the list itself). A None entry is a
    day that cannot be judged (an input missing): True only if the share holds even if every such day failed, False only
    if it fails even if every such day passed, else None. Fewer than ``min_days`` days: False only when the share would
    stay below ``need`` even if every missing or unjudged day passed (decisive), else None."""
    p = list(passes)
    k = sum(1 for v in p if v is not None and bool(v))
    u = sum(1 for v in p if v is None)
    if len(p) >= min_days:
        if k / len(p) >= need:
            return True
        return False if (k + u) / len(p) < need else None
    if (k + u + (min_days - len(p))) / min_days < need:
        return False
    return None


def _decide(rows: list, n: int, min_n: int, unit: str) -> tuple:
    """rows: [(name, ok, decisive_fail)]. Below min_n a failing criterion counts only when it fails decisively; otherwise
    it is reported as not decisive (None). Appends the min_n criterion."""
    crit = []
    for name, ok, dec in rows:
        if ok is not None and not bool(ok) and n < min_n and not dec:
            crit.append((name + " [fails, not decisively, below min_n]", None))
        else:
            crit.append((name, None if ok is None else bool(ok)))
    crit.append((f"n >= trial min_n ({n} of {min_n} {unit})", True if n >= min_n else None))
    return _verdict(crit)


def _halves(x) -> list:
    x = np.asarray(x, dtype=float)
    h = x.size // 2
    return [float(x[:h].mean()) if h else None, float(x[h:].mean()) if x.size - h else None]


def _f(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{nd}f}"


def _s(x, nd: int = 2) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:+.{nd}f}"


def _pct(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:+.{nd}f}%"


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


# ======================================================================================================= rates ==

def dtb3_continuous(d_pct: float) -> float:
    """Continuous rate from a 91-day discount yield in percent."""
    return -math.log(1.0 - d_pct / 100.0 * 91.0 / 360.0) / (91.0 / 365.0)


def bey_continuous(y_pct: float) -> float:
    """Continuous rate from a 91-day bond-equivalent yield in percent (FRED DGS3MO)."""
    return math.log(1.0 + y_pct / 100.0 * 91.0 / 365.0) / (91.0 / 365.0)


def prior_print(series: dict, day: str) -> Optional[tuple]:
    """(print day, value) of the latest observation dated strictly before ``day`` (FRED publishes a day late)."""
    ks = sorted(series)
    j = bisect_left(ks, day) - 1
    return (ks[j], float(series[ks[j]])) if j >= 0 else None


# ============================================================================================ archive plumbing ==

def _has(archive, name: str) -> bool:
    """Bundle indexed AND loadable on this machine (large chain bundles are kept off git)."""
    try:
        archive.get(name)
    except (KeyError, AttributeError):
        return False
    try:
        it = iter(archive.load(name))
        next(it, None)
        close = getattr(it, "close", None)
        if close:
            close()
        return True
    except (FileNotFoundError, OSError, KeyError):
        return False


def _names(archive, prefix: str) -> list:
    try:
        ents = archive.entries()
    except (AttributeError, TypeError):
        return []
    return sorted(e.name for e in ents if getattr(e, "name", "").startswith(prefix))


def _capture_names(archive, sym: str) -> list:
    """options-chain-<SYM>-<YYYY-MM-DD> bundles that are loadable, oldest first."""
    pat = re.compile(rf"^{re.escape(CHAIN_P + sym)}-(\d{{4}}-\d{{2}}-\d{{2}})$")
    return [n for n in _names(archive, CHAIN_P + sym + "-") if pat.match(n) and _has(archive, n)]


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        return ({"missing_bundles": miss}, 0, "inconclusive",
                f"missing data bundles {miss}: the claim cannot be tested until they are archived")
    return None


def _rows(archive, name: str, filtered: bool = True) -> list:
    """Rows of a bundle; with ``filtered`` drops rows not yet available when the bundle was captured (a bar still open)."""
    cap = getattr(archive.get(name), "created_at", None) if filtered else None
    return [r for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _daily_from_rows(rows) -> tuple:
    by = {}
    for r in rows:
        v = r["value"]
        c = v.get("close")
        if c is None or not float(c) > 0:
            continue
        d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        a = v.get("adjclose")
        by[d] = (float(c), float(a) if a is not None and float(a) > 0 else float(c))
    days = sorted(by)
    return days, np.array([by[d][0] for d in days], dtype=float), np.array([by[d][1] for d in days], dtype=float)


def _daily(archive, name: str) -> tuple:
    """(days, RAW close, adjclose) of a daily-history bundle, bars not yet available at capture dropped."""
    return _daily_from_rows(_rows(archive, name))


def _series(archive, name: str) -> dict:
    """{day: value} of a FRED series, missing prints skipped."""
    out = {}
    for r in _rows(archive, name):
        v = r["value"]
        try:
            x = float(v.get("value", v.get("close")))
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            out[v["day"]] = x
    return out


# ================================================================================================ chain parsing ==

_ROOT = re.compile(r"^([A-Z]+)")


def _ok(q) -> bool:
    """Usable two-sided quote: bid > 0 and not crossed."""
    return q is not None and q[0] > 0 and q[1] >= q[0]


def _mid(q) -> float:
    return 0.5 * (q[0] + q[1])


def _hs(q) -> float:
    return 0.5 * (q[1] - q[0])


def chain_by_root(values) -> dict:
    """{(root, expiry): {'call': {K: (bid, ask)}, 'put': {...}}} from compact CBOE option rows (row['value'] dicts)."""
    by = defaultdict(lambda: {"call": {}, "put": {}})
    for v in values:
        if v.get("bid") is None or v.get("ask") is None or v.get("type") not in ("call", "put"):
            continue
        m = _ROOT.match(v.get("sym") or "")
        root = m.group(1) if m else "?"
        by[(root, v["expiry"])][v["type"]][float(v["strike"])] = (float(v["bid"]), float(v["ask"]))
    return by


def valid_strikes(legs: dict) -> list:
    return sorted(k for k in legs["call"] if k in legs["put"] and _ok(legs["call"][k]) and _ok(legs["put"][k]))


def atm_pm(legs: dict, spot: float, n_side: int = 3) -> list:
    """The ATM strike (nearest to spot among strikes with both legs quoted) and the n_side quoted strikes either side."""
    ks = valid_strikes(legs)
    if not ks:
        return []
    i0 = min(range(len(ks)), key=lambda i: abs(ks[i] - spot))
    return ks[max(0, i0 - n_side): i0 + n_side + 1]


def nearest_strikes(legs: dict, spot: float, n: int = 3) -> list:
    return sorted(sorted(valid_strikes(legs), key=lambda k: (abs(k - spot), k))[:n])


def _dte(expiry: str, quote_day: str) -> int:
    return (date.fromisoformat(expiry) - date.fromisoformat(quote_day)).days


def regression_forward(legs: dict, ks: Sequence[float]) -> Optional[dict]:
    """OLS of C_mid - P_mid = a + b K over the strikes ks: discount factor DF = -b, forward F = -a / b (European parity
    C - P = DF (F - K)). None without a negative slope or with fewer than 2 strikes."""
    if len(ks) < 2:
        return None
    K = np.array(ks, dtype=float)
    y = np.array([_mid(legs["call"][k]) - _mid(legs["put"][k]) for k in ks])
    b, a = np.polyfit(K, y, 1)
    if not b < 0:
        return None
    return {"a": float(a), "b": float(b), "DF": float(-b), "F": float(-a / b), "K": K, "y": y}


def box_rate(legs: dict, spot: float, T: float, grid: float = 25.0, moneyness: float = 0.10, min_width: float = 0.05) -> tuple:
    """Median mid-price box rate ln(W / box_mid) / T over 'wide' boxes: strike pairs on the ``grid`` within +/- moneyness of
    spot, width >= min_width * spot, every leg quoted. Returns (rate or None, number of boxes)."""
    ks = [k for k in valid_strikes(legs) if abs(k / spot - 1) <= moneyness and abs(k / grid - round(k / grid)) < 1e-9]
    rates = []
    for i, k1 in enumerate(ks):
        for k2 in ks[i + 1:]:
            if k2 - k1 < min_width * spot:
                continue
            mid = (_mid(legs["call"][k1]) - _mid(legs["call"][k2]) - _mid(legs["put"][k1]) + _mid(legs["put"][k2]))
            if mid > 0:
                rates.append(math.log((k2 - k1) / mid) / T)
    return (float(np.median(rates)) if rates else None), len(rates)


# =============================================================================================== SPY dividends ==

def dividends(close, adj) -> np.ndarray:
    """Cash dividend going ex on each day (0 otherwise) from the adjclose/close ratio step: D = close[i-1](1 - f[i-1]/f[i])."""
    close = np.asarray(close, dtype=float)
    f = np.asarray(adj, dtype=float) / close
    out = np.zeros(close.size)
    for i in range(1, close.size):
        if f[i] > f[i - 1] * (1 + 1e-5):
            d = close[i - 1] * (1.0 - f[i - 1] / f[i])
            if 0 < d < 0.05 * close[i - 1]:
                out[i] = d
    return out


def _third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return d + timedelta(days=14)


def spy_ex_date(y: int, m: int) -> date:
    """Projected SPY ex-date: the third Friday of the quarter-end month, or the Thursday before when Juneteenth (observed)
    closes the market that Friday."""
    tf = _third_friday(y, m)
    if m == 6:
        j = date(y, 6, 19)
        observed = j if j.weekday() < 5 else (j - timedelta(days=1) if j.weekday() == 5 else j + timedelta(days=1))
        if observed == tf:
            return tf - timedelta(days=1)
    return tf


def pv_dividends(quote_day: str, expiry: str, amount: float, r: float) -> float:
    """PV at the quote-day close of the forecast dividends going ex in (quote_day, expiry]."""
    q, e = date.fromisoformat(quote_day), date.fromisoformat(expiry)
    pv = 0.0
    for y in range(q.year, e.year + 1):
        for m in (3, 6, 9, 12):
            x = spy_ex_date(y, m)
            if q < x <= e:
                pv += amount * math.exp(-r * (x - q).days / 365.0)
    return pv


def last_dividend(days, close, adj, before: str) -> Optional[float]:
    div = dividends(close, adj)
    amt = [float(div[i]) for i, d in enumerate(days) if div[i] > 0 and d <= before]
    return amt[-1] if amt else None


# ====================================================================================== T-255: hedged straddle ==

def _cycle_starts(days: Sequence[str], hold: int, start: str, end: str) -> np.ndarray:
    """Non-overlapping cycle entries every ``hold`` days from the first day >= start; the expiry close must be <= end and
    the cycle must span consecutive calendar days (no data gap)."""
    ords = np.array([date.fromisoformat(d).toordinal() for d in days], dtype=np.int64)
    i = bisect_left(list(days), start)
    out = []
    while i + hold < len(days) and days[i + hold] <= end:
        if ords[i + hold] - ords[i] == hold:
            out.append(i)
        i += hold
    return np.array(out, dtype=np.int64)


def _ivs(iv, I, scale: float) -> np.ndarray:
    return np.maximum(scale * np.asarray(iv, dtype=float)[I] / 100.0, 0.01)


def hedged_straddle(days, close, iv, start: str = "2021-04-01", end: str = "2026-09-30", hold: int = HOLD, scale: float = 1.0,
                    hedge_vol: str = "current", opt_fee: float = DERIBIT_OPT_FEE, hedge_fee: float = DERIBIT_PERP_FEE,
                    funding_bp: float = FUNDING_BP_DAY) -> dict:
    """Short ATM straddle (K = entry close) on a 24/7 asset priced by BS at sigma = scale * iv / 100 with r = q = 0, held
    ``hold`` calendar days to expiry and delta-hedged at every daily close with the BS straddle delta (at that day's iv,
    or the entry iv with hedge_vol='entry'); settled on the raw close. gross = premium - |S_T - K| + sum h_j (S_j+1 - S_j).
    Fees: the option fee per leg at entry (opt_fee x S, capped at 12.5% of the leg price), the hedge's taker fee on every
    traded notional (open, daily rebalances, unwind) and funding_bp per day on the hedge notional. Also returns the
    entry implied variance minus the cycle's realised variance (365 / hold x sum of squared log returns)."""
    days = list(days)
    close = np.asarray(close, dtype=float)
    starts = _cycle_starts(days, hold, start, end)
    keys = ("gross", "net", "prem", "x_gross", "x_net", "var_gap", "fees", "spot", "sig0")
    if starts.size == 0:
        return {k: np.zeros(0) for k in keys} | {"day": [], "start": starts}
    I = starts[:, None] + np.arange(hold + 1)[None, :]
    S = close[I]
    sig = _ivs(iv, I, scale)
    K = S[:, 0]
    T0 = hold / 365.0
    c0 = bs.price(K, K, T0, 0.0, sig[:, 0], "call")
    p0 = bs.price(K, K, T0, 0.0, sig[:, 0], "put")
    prem = c0 + p0
    Tj = (hold - np.arange(hold)) / 365.0
    hs = sig[:, :hold] if hedge_vol == "current" else np.repeat(sig[:, :1], hold, axis=1)
    h = 2.0 * bs.greeks(S[:, :hold], K[:, None], Tj[None, :], 0.0, hs, "call")["delta"] - 1.0   # long hedge of the short straddle
    dS = np.diff(S, axis=1)
    hedge_pnl = np.sum(h * dS, axis=1)
    payoff = np.abs(S[:, -1] - K)
    gross = prem - payoff + hedge_pnl
    leg_fee = np.minimum(opt_fee * K, 0.125 * c0) + np.minimum(opt_fee * K, 0.125 * p0)
    trades = np.concatenate([np.abs(h[:, :1]) * S[:, :1], np.abs(np.diff(h, axis=1)) * S[:, 1:hold], np.abs(h[:, -1:]) * S[:, -1:]], axis=1)
    fees = leg_fee + hedge_fee * trades.sum(axis=1) + funding_bp / 1e4 * np.sum(np.abs(h) * S[:, :hold], axis=1)
    net = gross - fees
    rv2 = (365.0 / hold) * np.sum(np.log(S[:, 1:] / S[:, :-1]) ** 2, axis=1)
    return {"start": starts, "day": [days[a] for a in starts], "gross": gross, "net": net, "prem": prem,
            "x_gross": gross / prem, "x_net": net / prem, "var_gap": sig[:, 0] ** 2 - rv2, "fees": fees, "spot": K, "sig0": sig[:, 0]}


def trailing_rv(close, idx, window: int = HOLD, ppy: int = CRYPTO_PPY) -> np.ndarray:
    """Annualised realised vol (vol points) of the ``window`` log returns ending at each close in idx (known at that close)."""
    c = np.asarray(close, dtype=float)
    out = np.full(len(idx), np.nan)
    for i, a in enumerate(idx):
        if a - window >= 0:
            r = np.log(c[a - window + 1:a + 1] / c[a - window:a])
            out[i] = math.sqrt(ppy / window * float(np.sum(r ** 2))) * 100
    return out


def btc_vrp_straddle(days, close, iv, start: str = "2021-04-01", end: str = "2026-09-30", hold: int = HOLD, block: int = 3,
                     n_boot: int = 2000, seed: int = 0, min_n: int = T255_MIN_N, sharpe_bound: float = 0.5,
                     measured_scale: Optional[float] = None, measured_note: str = "", spy_control: Optional[dict] = None) -> dict:
    """T-255: delta-hedged short 30-day ATM straddle at DVOL. Pass: the pooled studentized block-bootstrap 95% CI of the
    mean P&L / premium lies above 0, the mean is positive in both walk-forward halves, and the annualised Sharpe of the
    P&L after fees (365/30 cycles a year) exceeds 0.5. min_n 36 cycles. The 'positive mean P&L' criteria use the gross
    hedged P&L (the claim names no costs there); the Sharpe uses the P&L net of option fees, hedge fees and 1 bp/day funding."""
    base = hedged_straddle(days, close, iv, start, end, hold)
    n = int(base["x_gross"].size)
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"{MP}: only {n} non-overlapping {hold}-day cycles between {start} and {end}",
                "stat": {"model_priced": True, "n_cycles": n}}
    xg, xn = base["x_gross"], base["x_net"]
    lo, hi = stud_ci(xg, block, 0.95, n_boot, seed)
    lo_n, hi_n = stud_ci(xn, block, 0.95, n_boot, seed)
    hv = _halves(xg)
    ppy_c = CRYPTO_PPY / hold
    sr_net = sharpe_ratio(xn, ppy_c)
    sr_gross = sharpe_ratio(xg, ppy_c)
    h = n // 2
    rows = [("mean hedged P&L / premium > 0 with the studentized block-bootstrap 95% CI above 0 (pooled)",
             lo is not None and lo > 0, hi is not None and hi <= 0),
            ("mean > 0 in both walk-forward halves", all(v is not None and v > 0 for v in hv),
             min_n // 2 <= n < min_n and not xg[:min_n // 2].mean() > 0),
            (f"annualised Sharpe of hedged P&L after fees > {sharpe_bound}", sr_net > sharpe_bound, False)]
    verdict, why = _decide(rows, n, min_n, "cycles")
    # controls and sensitivities (reported, outside the verdict)
    scales = sorted(set([0.85, 0.90, 0.95, 1.0] + ([round(measured_scale, 4)] if measured_scale else [])))
    sens = {}
    for s in scales:
        r = hedged_straddle(days, close, iv, start, end, hold, scale=s)
        sens[f"{s:.4f}"] = {"mean_gross": float(r["x_gross"].mean()), "mean_net": float(r["x_net"].mean()),
                            "sharpe_net": sharpe_ratio(r["x_net"], ppy_c)}
    entry = hedged_straddle(days, close, iv, start, end, hold, hedge_vol="entry")
    rng = np.random.default_rng(seed)
    iv_arr = np.asarray(iv, dtype=float)
    shuf = hedged_straddle(days, close, iv_arr[rng.permutation(iv_arr.size)], start, end, hold)
    rv_entry = trailing_rv(close, base["start"], hold)
    gap_entry = base["sig0"] * 100 - rv_entry
    variants = {"all": np.ones(n, bool)}
    for thr in (0, 5, 10, 15):
        variants[f"DVOL-RV30>{thr}"] = gap_entry > thr
    trial_sr = [sharpe_ratio(xn[m]) if m.sum() >= 3 else 0.0 for m in variants.values()]
    dsr = float(deflated_sharpe_ratio(xn, len(variants), trial_sharpes=trial_sr))
    var_gap = base["var_gap"]
    stat = {"model_priced": True, "pricing": "Black-Scholes at sigma = DVOL/100, r = q = 0, K = entry close, T = 30/365; daily delta hedge on closes",
            "n_cycles": n, "first_entry": base["day"][0], "last_entry": base["day"][-1],
            "mean_gross": float(xg.mean()), "ci_gross": [lo, hi], "halves_gross": hv, "mean_net": float(xn.mean()), "ci_net": [lo_n, hi_n],
            "sharpe_net_annual": sr_net, "sharpe_gross_annual": sr_gross, "sharpe_net_per_cycle": sharpe_ratio(xn),
            "mean_fees_over_premium": float(np.mean(base["fees"] / base["prem"])),
            "mean_dvol2_minus_rv2": float(var_gap.mean()), "share_dvol2_above_rv2": float((var_gap > 0).mean()),
            "iv_scale_sensitivity": sens, "measured_atm_over_dvol": measured_scale,
            "entry_vol_hedge_mean_gross": float(entry["x_gross"].mean()), "shuffled_dvol_placebo_mean_gross": float(shuf["x_gross"].mean()),
            "dsr_over_threshold_variants": dsr, "variant_sharpes_per_cycle": dict(zip(variants, trial_sr)),
            "spy_vix_positive_control": spy_control, "verdict": verdict}
    sens_txt = ", ".join(f"s={float(k):.3f}{' (measured)' if measured_scale and abs(float(k) - measured_scale) < 1e-4 else ''} "
                         f"{v['mean_gross'] * 100:+.1f}%" for k, v in sens.items())
    meas_txt = ""
    if measured_scale:
        rm = hedged_straddle(days, close, iv, start, end, hold, scale=measured_scale)
        ml, mh = stud_ci(rm["x_gross"], block, 0.95, n_boot, seed)
        stat["measured_scale_ci_gross"] = [ml, mh]
        meas_txt = (f"; at the measured ATM/DVOL scale {measured_scale:.3f}: mean {rm['x_gross'].mean() * 100:+.1f}% (CI {_pct(ml)} to {_pct(mh)}), "
                    f"after fees Sharpe {sharpe_ratio(rm['x_net'], ppy_c):.2f}")
    ctl = (f"; SPY/VIX hedged short straddle (positive control) {spy_control['mean'] * 100:+.1f}% of premium over {spy_control['n']} cycles"
           if spy_control and spy_control.get("mean") is not None else "; SPY/VIX positive control not run (bundles missing)")
    reason = (f"{MP} (BS at DVOL, r = q = 0, daily delta hedge on daily closes; self-financed at r = 0, so the P&L is an excess P&L): "
              f"short 30-day ATM BTC straddle, {n} non-overlapping "
              f"cycles {base['day'][0]}..{base['day'][-1]}: mean hedged P&L {xg.mean() * 100:+.1f}% of premium (studentized 95% CI "
              f"{_pct(lo)} to {_pct(hi)}), halves {_pct(hv[0])}/{_pct(hv[1])}; after fees (0.03% option fee per leg, 0.05% perp taker on "
              f"hedge trades, 1 bp/day funding) mean {xn.mean() * 100:+.1f}% (CI {_pct(lo_n)} to {_pct(hi_n)}), annualised Sharpe "
              f"{sr_net:.2f} (needs > {sharpe_bound}); mean DVOL^2 - RV^2(30d) {var_gap.mean():+.4f} (positive in {(var_gap > 0).mean() * 100:.0f}% "
              f"of cycles){measured_note}; IV-scale sensitivity (gross mean) {sens_txt}{meas_txt}; entry-vol hedge {entry['x_gross'].mean() * 100:+.1f}%, "
              f"shuffled-DVOL placebo {shuf['x_gross'].mean() * 100:+.1f}%, DSR over {len(variants)} DVOL-RV30 threshold variants {dsr:.2f}{ctl}; "
              f"DVOL is a variance-swap level that sits above ATM IV, so pricing the ATM straddle at DVOL overstates the premium: the edge "
              f"hinges on the IV level and the traded version needs Deribit option-trade history (2 book captures archived) — {why}")
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ================================================================================== T-261: inverse strangle ==

def deribit_im_btc(S: np.ndarray, Kc: np.ndarray, Kp: np.ndarray, c_btc: np.ndarray, p_btc: np.ndarray) -> np.ndarray:
    """Deribit standard initial margin of a short call plus a short put, in BTC per contract:
    max(0.15 - OTM amount / S, 0.10) + mark (BTC), per leg."""
    otm_c = np.maximum(Kc - S, 0.0) / S
    otm_p = np.maximum(S - Kp, 0.0) / S
    return np.maximum(0.15 - otm_c, 0.10) + c_btc + np.maximum(0.15 - otm_p, 0.10) + p_btc


def inverse_strangle(days, close, iv, start: str = "2021-04-01", end: str = "2026-09-30", hold: int = HOLD, delta: float = 0.15,
                     scale: float = 1.0) -> dict:
    """Short delta-d strangle (BS at sigma = scale * iv / 100, r = q = 0, strikes at +/- d delta on the entry close), held
    ``hold`` days and hedged at each daily close. USD P&L per 1-BTC contract under:
      inverse, premium booked in coin (pc = USD premium / S0 BTC, held):
        naive      = premium_usd - payoff_usd + pc (S_T - S0) + sum D_j dS_j          (D_j = BS call + put delta)
        corrected  = naive - pc (S_T - S0)        (hedge D_j - pc: the coin premium's delta neutralised)
      inverse with the Deribit initial margin m (BTC) also held as coin collateral:
        naive_coll = naive + m (S_T - S0),  corrected_coll = naive_coll - (pc + m)(S_T - S0)
      USDC-linear (premium in USD): naive_lin = premium_usd - payoff_usd + sum D_j dS_j; the correct rule hedges the same
        way (ratio 1 by construction); misapplied = naive_lin - pc (S_T - S0) (the coin correction applied where no coin is held).
    The USD value of an inverse option equals its BS value, so the option legs are identical across the variants."""
    days = list(days)
    close = np.asarray(close, dtype=float)
    starts = _cycle_starts(days, hold, start, end)
    if starts.size == 0:
        z = np.zeros(0)
        return {"start": starts, "day": [], "naive": z, "corrected": z, "naive_coll": z, "corrected_coll": z, "naive_lin": z,
                "misapplied_lin": z, "spot": z, "prem_btc": z, "im_btc": z}
    I = starts[:, None] + np.arange(hold + 1)[None, :]
    S = close[I]
    sig = _ivs(iv, I, scale)
    S0 = S[:, 0]
    T0 = hold / 365.0
    Kc = np.array([bs.strike_for_delta(s, T0, 0.0, v, delta, "call") for s, v in zip(S0, sig[:, 0])])
    Kp = np.array([bs.strike_for_delta(s, T0, 0.0, v, -delta, "put") for s, v in zip(S0, sig[:, 0])])
    c0 = bs.price(S0, Kc, T0, 0.0, sig[:, 0], "call")
    p0 = bs.price(S0, Kp, T0, 0.0, sig[:, 0], "put")
    prem = c0 + p0
    pc = prem / S0
    Tj = (hold - np.arange(hold)) / 365.0
    D = (bs.greeks(S[:, :hold], Kc[:, None], Tj[None, :], 0.0, sig[:, :hold], "call")["delta"]
         + bs.greeks(S[:, :hold], Kp[:, None], Tj[None, :], 0.0, sig[:, :hold], "put")["delta"])
    hedge = np.sum(D * np.diff(S, axis=1), axis=1)
    ST = S[:, -1]
    payoff = np.maximum(ST - Kc, 0.0) + np.maximum(Kp - ST, 0.0)
    move = ST - S0
    im = deribit_im_btc(S0, Kc, Kp, c0 / S0, p0 / S0)
    naive = prem - payoff + pc * move + hedge
    naive_coll = naive + im * move
    naive_lin = prem - payoff + hedge
    return {"start": starts, "day": [days[a] for a in starts], "naive": naive, "corrected": naive - pc * move,
            "naive_coll": naive_coll, "corrected_coll": naive_coll - (pc + im) * move, "naive_lin": naive_lin,
            "misapplied_lin": naive_lin - pc * move, "spot": S0, "prem_btc": pc, "im_btc": im, "Kc": Kc, "Kp": Kp}


def inverse_hedge_ratio(days, close, iv, start: str = "2021-04-01", end: str = "2026-09-30", hold: int = HOLD, delta: float = 0.15,
                        bound: float = 0.8, block: int = 3, n_boot: int = 2000, seed: int = 0, min_n: int = T261_MIN_N) -> dict:
    """T-261: ratio var(USD P&L, coin-corrected hedge) / var(USD P&L, naive BS-delta hedge) for the short 15-delta inverse
    strangle (premium in coin), with a paired percentile block-bootstrap 95% CI. Pass: upper end of the CI < 0.8.
    min_n 36 cycles. The claimed statistic is on USD P&L per contract; the same ratio on P&L / entry spot and the
    collateral and USDC-linear controls are reported."""
    res = inverse_strangle(days, close, iv, start, end, hold, delta)
    n = int(res["naive"].size)
    if n < 8:
        return {"verdict": "inconclusive", "n": n, "reason": f"{MP}: only {n} non-overlapping {hold}-day cycles between {start} and {end}",
                "stat": {"model_priced": True, "n_cycles": n}}
    main = var_ratio_ci(res["corrected"], res["naive"], block, 0.95, n_boot, seed)
    per_spot = var_ratio_ci(res["corrected"] / res["spot"], res["naive"] / res["spot"], block, 0.95, n_boot, seed)
    coll = var_ratio_ci(res["corrected_coll"], res["naive_coll"], block, 0.95, n_boot, seed)
    lin = var_ratio_ci(res["naive_lin"], res["naive_lin"], block, 0.95, n_boot, seed)
    mis = var_ratio_ci(res["misapplied_lin"], res["naive_lin"], block, 0.95, n_boot, seed)
    rows = [(f"upper end of the 95% CI of var(corrected) / var(naive) < {bound}",
             main["hi"] is not None and main["hi"] < bound, main["lo"] is not None and main["lo"] >= bound)]
    verdict, why = _decide(rows, n, min_n, "cycles")
    stat = {"model_priced": True, "pricing": "Black-Scholes at sigma = DVOL/100, r = q = 0, 15-delta strikes on the entry close, T = 30/365; daily hedge on closes",
            "n_cycles": n, "first_entry": res["day"][0], "last_entry": res["day"][-1],
            "var_ratio_usd": main, "var_ratio_per_spot": per_spot, "var_ratio_premium_plus_collateral": coll,
            "usdc_linear_correct_rule": lin, "usdc_linear_coin_correction_misapplied": mis,
            "mean_premium_btc": float(res["prem_btc"].mean()), "mean_im_btc": float(res["im_btc"].mean()),
            "sd_usd_naive": float(res["naive"].std(ddof=1)), "sd_usd_corrected": float(res["corrected"].std(ddof=1)), "verdict": verdict}
    reason = (f"{MP} (BS at DVOL, r = q = 0, daily hedge on closes): short 15-delta inverse BTC strangle, premium booked in coin "
              f"(mean {res['prem_btc'].mean():.4f} BTC), {n} non-overlapping 30-day cycles {res['day'][0]}..{res['day'][-1]}: "
              f"var(USD P&L) corrected / naive = {_f(main['ratio'], 3)} (paired block-bootstrap 95% CI {_f(main['lo'], 3)} to "
              f"{_f(main['hi'], 3)}; needs upper < {bound}); per unit of entry spot {_f(per_spot['ratio'], 3)} (CI {_f(per_spot['lo'], 3)} "
              f"to {_f(per_spot['hi'], 3)}); with the Deribit initial margin (mean {res['im_btc'].mean():.3f} BTC) also held in coin "
              f"{_f(coll['ratio'], 3)} (CI {_f(coll['lo'], 3)} to {_f(coll['hi'], 3)}); USDC-linear control: the correct rule hedges "
              f"identically (ratio {_f(lin['ratio'], 3)}), the coin correction misapplied gives {_f(mis['ratio'], 3)} — {why}")
    return {"verdict": verdict, "n": n, "reason": reason, "stat": stat}


# ========================================================================== T-194: SPY vs SPX implied financing ==

def spy_spx_financing(captures: Sequence[dict], ex_date: str = "2026-12-18", dte_range=(30, 64), fee: float = SPY_FEE,
                      tol_bp: float = 25.0, need: float = 0.90, days_need: float = 0.80, n_days: int = T194_DAYS,
                      min_n: int = T194_MIN_N) -> dict:
    """T-194. captures: [{'quote_day', 'spy_spot', 'spx_spot', 'spy': [values], 'spx': [values]}], oldest first.
    For each SPY expiry with dte in dte_range and expiry < ex_date: F_spy from an OLS of C_mid - P_mid on K over the ATM
    +/- 3 strikes (F = -a/b, no bill input), r_spy = ln(F / SPY) / T + fee; r_box = median mid box rate over wide SPXW
    boxes ($25 grid, +/- 10% of spot, width >= 5% of spot) at the nearest SPXW expiry (AM-settled SPX monthlies excluded).
    Pass: >= 90% of matched expiries within 25 bp on day one, and on >= 80% of 20 captured days. min_n 10 matched
    expiries (counted on day one)."""
    per_day = []
    for cap in captures:
        qd, S, X = cap["quote_day"], float(cap["spy_spot"]), float(cap["spx_spot"])
        spy = chain_by_root(cap["spy"])
        spx = {e: legs for (root, e), legs in chain_by_root(cap["spx"]).items() if root == "SPXW"}
        spx_exp = sorted(spx)
        rows = []
        for (root, e), legs in sorted(spy.items()):
            dte = _dte(e, qd)
            if not (dte_range[0] <= dte <= dte_range[1] and e < ex_date) or not spx_exp:
                continue
            T = dte / 365.0
            ks = atm_pm(legs, S, 3)
            fw = regression_forward(legs, ks)
            if fw is None or len(ks) < 4:
                continue
            m = min(spx_exp, key=lambda x: (abs(_dte(x, e)), x))
            rb, nbox = box_rate(spx[m], X, _dte(m, qd) / 365.0)
            if rb is None:
                continue
            r_spy = math.log(fw["F"] / S) / T + fee
            Fk = fw["K"] + fw["y"] * math.exp(rb * T)                      # strike-by-strike forwards at the box discount
            d_bp = (r_spy - rb) * 1e4
            rows.append({"expiry": e, "dte": dte, "spxw_expiry": m, "gap_days": _dte(m, e), "strikes": [float(k) for k in ks],
                         "F_spy": fw["F"], "r_spy_bp": r_spy * 1e4, "r_spy_ex_fee_bp": (r_spy - fee) * 1e4, "r_box_bp": rb * 1e4,
                         "n_boxes": nbox, "diff_bp": d_bp, "within": abs(d_bp) <= tol_bp,
                         "F_strike_sd_bp": float(np.std(Fk, ddof=1) / S * 1e4) if Fk.size > 1 else None,
                         "spot_reconciling": float(fw["F"] * math.exp(-(rb - fee) * T))})
        if rows:
            k = sum(r["within"] for r in rows)
            off = [r["spot_reconciling"] - S for r in rows]
            per_day.append({"quote_day": qd, "spy_spot": S, "n_expiries": len(rows), "n_within": k, "share_within": k / len(rows),
                            "pass": k / len(rows) >= need, "median_spot_offset": float(np.median(off)), "expiries": rows,
                            "bill_used": cap.get("bill")})
    if not per_day:
        return {"verdict": "inconclusive", "n": 0, "stat": {"n_days": 0},
                "reason": f"no capture day has a SPY expiry with {dte_range[0]}-{dte_range[1]} DTE before {ex_date} matched to a SPXW box"}
    d0 = per_day[0]
    n1, k1 = d0["n_expiries"], d0["n_within"]
    days_ok = _days_share([d["pass"] for d in per_day][:n_days], days_need, n_days)      # the pass names 20 captured days
    rows = [(f"day one ({d0['quote_day']} quotes): >= {need:.0%} of matched expiries within {tol_bp:.0f} bp ({k1}/{n1})",
             k1 / n1 >= need, _share_fails_at_min_n(k1, n1, min_n, need)),
            (f">= {days_need:.0%} of {n_days} captured days pass ({sum(d['pass'] for d in per_day)}/{len(per_day)} so far)", days_ok, days_ok is False)]
    verdict, why = _decide(rows, n1, min_n, "matched expiries on day one")
    txt = []
    for d in per_day:
        txt.append(f"{d['quote_day']} (SPY {d['spy_spot']:.2f}): " + ", ".join(
            f"{r['expiry']} {r['r_spy_bp']:.0f} vs box {r['r_box_bp']:.0f} ({r['diff_bp']:+.0f})" for r in d["expiries"])
            + f" -> {d['n_within']}/{d['n_expiries']} within; spot that reconciles the two rates is {d['median_spot_offset']:+.2f} from the close")
    reason = (f"SPY ATM +/- 3 OLS forward vs SPXW wide-box mid rate, SPY expiries {dte_range[0]}-{dte_range[1]} DTE before {ex_date}, "
              f"r_spy = ln(F/SPY)/T + {fee * 100:.4f}% (bp/yr): " + "; ".join(txt)
              + f". SPY options quote to 16:15 ET but the SPY close prints at 16:00, so a 15-minute move of the spot shifts r_spy by "
              f"(dS/S)/T (about 10 bp/yr per 1 bp of spot at 37 DTE); the XSP box (second reference) is not captured — {why}")
    stat = {"n_days": len(per_day), "day_one": d0["quote_day"], "n_matched_day_one": n1, "n_within_day_one": k1,
            "n_matched_total": sum(d["n_expiries"] for d in per_day), "per_day": per_day, "days_criterion": days_ok, "verdict": verdict}
    return {"verdict": verdict, "n": n1, "reason": reason, "stat": stat}


# ================================================================================== T-199: GLD implied carry ==

def implied_carry_pairs(values, spot: float, quote_day: str, r_bill: float, fee: float, dte_range=(90, 365), n_side: int = 3,
                        tol_bp: float = 50.0) -> list:
    """Per (expiry, strike) over the ATM +/- n_side strikes of expiries in dte_range: r_impl from C_mid - P_mid = S - K e^{-r T},
    r_impl = -ln((S - (C - P)) / K) / T, residual against the target r_bill - fee. The executable band uses
    C_bid - P_ask and C_ask - P_bid."""
    out = []
    target = r_bill - fee
    for (root, e), legs in sorted(chain_by_root(values).items()):
        dte = _dte(e, quote_day)
        if not (dte_range[0] <= dte <= dte_range[1]):
            continue
        T = dte / 365.0
        for k in atm_pm(legs, spot, n_side):
            c, p = legs["call"][k], legs["put"][k]
            cp = _mid(c) - _mid(p)
            if spot - cp <= 0:
                continue
            r = -math.log((spot - cp) / k) / T
            lo_cp, hi_cp = c[0] - p[1], c[1] - p[0]
            r_lo = -math.log((spot - lo_cp) / k) / T if spot - lo_cp > 0 else None
            r_hi = -math.log((spot - hi_cp) / k) / T if spot - hi_cp > 0 else None
            resid = (r - target) * 1e4
            out.append({"expiry": e, "dte": dte, "K": float(k), "r_impl_bp": r * 1e4, "resid_bp": resid, "within": abs(resid) <= tol_bp,
                        "exec_band_bp": [None if r_lo is None else (r_lo - target) * 1e4, None if r_hi is None else (r_hi - target) * 1e4]})
    return out


def gld_carry(captures: Sequence[dict], fee: float = GLD_FEE, tol_bp: float = 50.0, need: float = 0.90, days_need: float = 0.80,
              min_n: int = T199_MIN_N, min_days: int = MIN_DAYS_SHARE, slv: Optional[Sequence[dict]] = None, basis: Optional[dict] = None) -> dict:
    """T-199. captures: [{'quote_day', 'spot', 'values', 'bill', 'bill_day'} + optional 'bill_src', 'proxy', 'proxy_day'],
    oldest first. 'bill' is the trial's 3-month bill (FRED DGS3MO, continuous; None when no print is available for that
    quote day) and 'proxy' the DTB3 stand-in (continuous), evaluated next to it. Share of GLD strike/expiry pairs (ATM
    +/- 3, 90-365 DTE) with |r_impl - (bill - 0.40%)| <= 50 bp. Pass: share >= 90% on day one and on >= 80% of captured
    days. min_n 30 pairs (counted on day one). The '80% of captured days' share is judged over all captured days once
    MIN_DAYS_SHARE (5) exist (the fewest that can tell 80% from 100%); before that only a decisive failure counts. A day
    without the named bill is reported under the proxy and left unjudged (pass None).
    slv: the same captures for SLV (reported separately, fee 0.50%). basis: {quote_day: {expiry: SPXW box - bill (bp)}}."""
    per_day = []
    for cap in captures:
        named, proxy = cap.get("bill"), cap.get("proxy")
        r0 = named if named is not None else proxy
        if r0 is None:
            continue
        pairs = implied_carry_pairs(cap["values"], cap["spot"], cap["quote_day"], r0, fee, tol_bp=tol_bp)
        if not pairs:
            continue
        k = sum(p["within"] for p in pairs)
        need_k = math.ceil(need * len(pairs) - 1e-9)
        out_gap = [abs(p["resid_bp"]) - tol_bp for p in pairs if not p["within"]]
        in_gap = [tol_bp - abs(p["resid_bp"]) for p in pairs if p["within"]]
        prox = None
        if named is not None and proxy is not None:
            pp = implied_carry_pairs(cap["values"], cap["spot"], cap["quote_day"], proxy, fee, tol_bp=tol_bp)
            kp = sum(p["within"] for p in pp)
            prox = {"rate_cont_bp": proxy * 1e4, "print_day": cap.get("proxy_day"), "n_pairs": len(pp), "n_within": kp,
                    "share": kp / len(pp) if pp else None, "pass": (kp / len(pp) >= need) if pp else None,
                    "bill_minus_proxy_bp": (named - proxy) * 1e4}
        res = np.array([p["resid_bp"] for p in pairs])
        K = np.array([p["K"] for p in pairs]) / cap["spot"] - 1
        slope = float(np.polyfit(K, res, 1)[0] / 100) if len(set(K.round(6))) > 1 else None   # bp per 1% of moneyness
        exec_ok = [p for p in pairs if None not in p["exec_band_bp"]]
        exec_share = (sum(p["exec_band_bp"][0] <= tol_bp and p["exec_band_bp"][1] >= -tol_bp for p in exec_ok) / len(exec_ok)) if exec_ok else None
        b = (basis or {}).get(cap["quote_day"]) or {}
        net = [p["resid_bp"] - b[p["expiry"]] for p in pairs if b.get(p["expiry"]) is not None]
        sens = {f"{sh:+d}bp": sum(abs(p["resid_bp"] - sh) <= tol_bp for p in pairs) / len(pairs) for sh in (-10, 10)}
        per_day.append({"quote_day": cap["quote_day"], "spot": cap["spot"], "as_worded": named is not None,
                        "bill_src": cap.get("bill_src") if named is not None else "DTB3 proxy only (no DGS3MO print)",
                        "bill_day": cap.get("bill_day") if named is not None else cap.get("proxy_day"), "bill_cont_bp": r0 * 1e4,
                        "n_pairs": len(pairs), "n_within": k, "share": k / len(pairs),
                        "pass": (k / len(pairs) >= need) if named is not None else None,
                        "pairs_short_of_need": max(0, need_k - k), "pairs_to_spare": max(0, k - need_k),
                        "nearest_outside_beyond_band_bp": min(out_gap) if out_gap else None,
                        "nearest_inside_from_edge_bp": min(in_gap) if in_gap else None, "dtb3_proxy": prox,
                        "median_resid_bp": float(np.median(res)), "resid_slope_bp_per_1pct_moneyness": slope,
                        "exec_band_overlap_share": exec_share, "bill_shift_share": sens,
                        "median_resid_net_of_spx_box_basis_bp": float(np.median(net)) if net else None,
                        "spx_box_minus_bill_bp": b or None, "pairs": pairs})
    if not per_day:
        return {"verdict": "inconclusive", "n": 0, "stat": {"n_days": 0}, "reason": "no GLD capture has ATM +/- 3 pairs at 90-365 DTE"}
    d0 = per_day[0]
    n1, k1 = d0["n_pairs"], d0["n_within"]
    days_ok = _days_share([d["pass"] for d in per_day], days_need, min_days)
    unjudged = sum(d["pass"] is None for d in per_day)
    rows = [(f"day one ({d0['quote_day']} quotes): share of pairs within {tol_bp:.0f} bp of bill - {fee * 100:.2f}% >= {need:.0%} ({k1}/{n1} = {k1 / n1:.1%}"
             + ("" if d0["as_worded"] else "; no DGS3MO print for day one, DTB3 proxy only") + ")",
             (k1 / n1 >= need) if d0["as_worded"] else None, d0["as_worded"] and _share_fails_at_min_n(k1, n1, min_n, need)),
            (f"share >= {need:.0%} on >= {days_need:.0%} of captured days ({sum(bool(d['pass']) for d in per_day)}/{len(per_day)} days so far"
             + (f", {unjudged} without a DGS3MO print" if unjudged else "") + f"; judged over all captured days from {min_days} days)",
             days_ok, days_ok is False)]
    verdict, why = _decide(rows, n1, min_n, "pairs on day one")
    slv_txt, slv_days = "", []
    for cap in slv or []:
        r_s = cap.get("bill") if cap.get("bill") is not None else cap.get("proxy")
        pairs = implied_carry_pairs(cap["values"], cap["spot"], cap["quote_day"], r_s, SLV_FEE, tol_bp=tol_bp) if r_s is not None else []
        if pairs:
            k = sum(p["within"] for p in pairs)
            slv_days.append({"quote_day": cap["quote_day"], "n_pairs": len(pairs), "share": k / len(pairs),
                             "median_resid_bp": float(np.median([p["resid_bp"] for p in pairs]))})
    if slv_days:
        slv_txt = "; SLV (reported separately, bill - 0.50%): " + ", ".join(
            f"{d['quote_day']} {d['share']:.0%} of {d['n_pairs']} within (median residual {d['median_resid_bp']:+.0f} bp)" for d in slv_days)
    def _pl(m: int) -> str:
        return f"{m} pair" + ("" if m == 1 else "s")

    def _margin(d) -> str:
        if d["share"] >= need:
            return f" ({_pl(d['pairs_to_spare'])} to spare)"
        near = d["nearest_outside_beyond_band_bp"]
        return (f" ({_pl(d['pairs_short_of_need'])} short of {need:.0%}" +
                (f"; the nearest pair outside the band misses it by {near:.1f} bp" if near is not None else "") + ")")

    def _proxy(d) -> str:
        p = d["dtb3_proxy"]
        if not p:
            return ""
        return (f"; next to it, the DTB3 proxy {p['rate_cont_bp']:.1f} bp cont. ({p['print_day']} print, {-p['bill_minus_proxy_bp']:+.1f} bp vs "
                f"DGS3MO) gives {p['n_within']}/{p['n_pairs']} = {p['share']:.1%}")

    day_txt = "; ".join(
        f"{d['quote_day']} (GLD {d['spot']:.2f}, bill {d['bill_cont_bp']:.1f} bp cont. from the {d['bill_day']} print, {d['bill_src'] or 'bill as given'}): "
        f"{d['n_within']}/{d['n_pairs']} = {d['share']:.1%} within{_margin(d)}{_proxy(d)}, median residual {d['median_resid_bp']:+.0f} bp, "
        f"residual slope {_s(d['resid_slope_bp_per_1pct_moneyness'], 1)} bp per 1% "
        f"of moneyness (American puts carry an early-exercise premium at high strikes), executable band overlaps the target in "
        f"{_pct(d['exec_band_overlap_share'], 0).lstrip('+')} of pairs, share with the bill shifted -10/+10 bp "
        f"{d['bill_shift_share']['-10bp']:.0%}/{d['bill_shift_share']['+10bp']:.0%}"
        + (f", median residual net of the SPXW box-bill basis {d['median_resid_net_of_spx_box_basis_bp']:+.0f} bp"
           if d["median_resid_net_of_spx_box_basis_bp"] is not None else "")
        for d in per_day)
    gaps = [d["dtb3_proxy"]["bill_minus_proxy_bp"] for d in per_day if d["dtb3_proxy"]]
    src_txt = ""
    if any((d["bill_src"] or "").startswith("DGS3MO_REF") for d in per_day):
        src_txt += ("; fred-DGS3MO is not archived yet, so its prints come from DGS3MO_REF (FRED fredgraph.csv, read once on "
                    "2026-10-15) until the bundle is archived")
    if unjudged:
        src_txt += f"; {unjudged} day(s) with no DGS3MO print are shown under the DTB3 proxy and left unjudged"
    if gaps:
        pdays = [d["dtb3_proxy"] for d in per_day if d["dtb3_proxy"]]
        src_txt += (f"; DGS3MO sits {min(gaps):.1f} to {max(gaps):.1f} bp above the DTB3 proxy (both continuous), which would give day one "
                    f"{pdays[0]['n_within']}/{pdays[0]['n_pairs']} and pass on {sum(bool(p['pass']) for p in pdays)}/{len(pdays)} days")
    reason = (f"GLD option-implied financing rate from ATM +/- 3 mids at 90-365 DTE vs the trial's 3-month bill, FRED DGS3MO - 0.40% "
              f"(bond-equivalent print dated before the quote day, continuous ln(1 + y 91/365) / (91/365){src_txt}; day one with the bill "
              f"10 bp higher or lower: {d0['bill_shift_share']['+10bp']:.0%} / {d0['bill_shift_share']['-10bp']:.0%} within): "
              + day_txt + slv_txt + f" — {why}")
    stat = {"n_days": len(per_day), "day_one": d0["quote_day"], "n_pairs_day_one": n1, "share_day_one": k1 / n1,
            "bill_series": sorted({d["bill_src"] or "bill as given" for d in per_day}), "dgs3mo_minus_dtb3_bp": gaps,
            "per_day": per_day, "days_criterion": days_ok, "slv": slv_days, "verdict": verdict}
    return {"verdict": verdict, "n": n1, "reason": reason, "stat": stat}


def box_bill_basis(spx_values, spx_spot: float, quote_day: str, r_bill: float, expiries: Sequence[str]) -> dict:
    """{expiry: (median wide SPXW box rate at the nearest SPXW expiry - bill) in bp} for the given expiries."""
    spx = {e: legs for (root, e), legs in chain_by_root(spx_values).items() if root == "SPXW"}
    out = {}
    for e in expiries:
        if not spx:
            break
        m = min(spx, key=lambda x: (abs(_dte(x, e)), x))
        dte = _dte(m, quote_day)
        if dte <= 0:
            continue
        rb, nb = box_rate(spx[m], spx_spot, dte / 365.0)
        if rb is not None:
            out[e] = (rb - r_bill) * 1e4
    return out


# =========================================================================== T-137: parity deviation scan ==

def european_pairs(values, spot: float, quote_day: str, r: float, n_near: int = 3, reg_moneyness: float = 0.10, min_reg: int = 5,
                   r_curve=None) -> list:
    """SPX (European). Per (root, expiry): OLS of C_mid - P_mid on K over the strikes within +/- reg_moneyness of spot,
    intercept a = S e^{-qT} gives the implied q; parity forward F = S e^{(r - q)T} = a e^{rT} with r the bill. Each of the
    n_near strikes nearest spot is flagged when |K + (C_mid - P_mid) e^{rT} - F| > (hs_C + hs_P) e^{rT} + 0.001 S.
    Variants: 'literal' (the claim's K + C - P, undiscounted), 'box' (F and carry at the regression's own discount rate:
    cross-strike consistency only) and 'curve' (r from r_curve(T), a bill-to-2-year interpolation)."""
    out = []
    for (root, e), legs in sorted(chain_by_root(values).items()):
        dte = _dte(e, quote_day)
        if dte < 1:
            continue
        T = dte / 365.0
        reg = [k for k in valid_strikes(legs) if abs(k / spot - 1) <= reg_moneyness]
        fw = regression_forward(legs, reg) if len(reg) >= min_reg else None
        if fw is None:
            continue
        a, DF = fw["a"], fw["DF"]
        g = math.exp(r * T)
        F = a * g
        rc = r_curve(T) if r_curve else None
        for k in nearest_strikes(legs, spot, n_near):
            c, p = legs["call"][k], legs["put"][k]
            cp, hs = _mid(c) - _mid(p), _hs(c) + _hs(p)
            dev = k + cp * g - F
            tol = hs * g + 0.001 * spot
            rec = {"symbol": "SPX", "root": root, "expiry": e, "dte": dte, "K": float(k), "dev": dev, "tol": tol, "flag": abs(dev) > tol,
                   "flag_literal": abs(k + cp - F) > hs + 0.001 * spot,
                   "flag_box": abs(k + cp / DF - a / DF) > hs / DF + 0.001 * spot,
                   "r_box_bp": -math.log(DF) / T * 1e4, "q_bp": -math.log(a / spot) / T * 1e4 if a > 0 else None}
            if rc is not None:
                gc = math.exp(rc * T)
                rec["flag_curve"] = abs(k + cp * gc - a * gc) > hs * gc + 0.001 * spot
            out.append(rec)
    return out


def american_pairs(values, spot: float, quote_day: str, r: float, symbol: str, div_amount: Optional[float] = None, n_near: int = 3,
                   r_curve=None) -> list:
    """SPY / GLD / IBIT (American). Each of the n_near strikes nearest spot is flagged when C_mid - P_mid lies outside the
    no-arbitrage bounds S - PV(D) - K <= C - P <= S - K e^{-rT} by more than hs_C + hs_P + 0.001 S. PV(D) from the
    forecast quarterly dividend (SPY), 0 for GLD and IBIT."""
    out = []
    for (root, e), legs in sorted(chain_by_root(values).items()):
        dte = _dte(e, quote_day)
        if dte < 1:
            continue
        T = dte / 365.0
        pvd = pv_dividends(quote_day, e, div_amount, r) if div_amount else 0.0
        rc = r_curve(T) if r_curve else None
        for k in nearest_strikes(legs, spot, n_near):
            c, p = legs["call"][k], legs["put"][k]
            cp = _mid(c) - _mid(p)
            tol = _hs(c) + _hs(p) + 0.001 * spot
            lo, hi = spot - pvd - k, spot - k * math.exp(-r * T)
            below, above = lo - tol - cp, cp - hi - tol
            rec = {"symbol": symbol, "root": root, "expiry": e, "dte": dte, "K": float(k), "pv_div": pvd, "tol": tol,
                   "excess": max(below, above), "flag": below > 0 or above > 0, "side": "lower" if below > 0 else ("upper" if above > 0 else None)}
            if rc is not None:
                hi_c = spot - k * math.exp(-rc * T)
                lo_c = spot - pv_dividends(quote_day, e, div_amount, rc) - k if div_amount else lo
                rec["flag_curve"] = cp < lo_c - tol or cp > hi_c + tol
            out.append(rec)
    return out


def parity_scan(days_pairs: Sequence[tuple], symbols=("SPX", "SPY", "GLD", "IBIT"), bound: float = 0.01, min_n: int = T137_MIN_N,
                min_days: int = MIN_DAYS_SHARE, n_boot: int = 4000, seed: int = 0) -> dict:
    """T-137. days_pairs: [(quote_day, [pair dicts from european_pairs / american_pairs])], one entry per capture (quote)
    day. Pass: pooled share of flagged near-ATM pairs < 1% with a day-clustered 95% CI entirely below 1% (needs at
    least min_days capture days). min_n 500 pairs. Every named chain must contribute pairs."""
    allp = [p for _, ps in days_pairs for p in ps]
    n = len(allp)
    if n == 0:
        return {"verdict": "inconclusive", "n": 0, "stat": {"n_pairs": 0}, "reason": "no near-ATM pairs in the captured chains"}
    flags = sum(bool(p["flag"]) for p in allp)
    share = flags / n
    by_day = defaultdict(list)
    for qd, ps in days_pairs:
        by_day[qd] += [bool(p["flag"]) for p in ps]
    lo, hi = day_cluster_share_ci(list(by_day.values()), 0.95, n_boot, seed)
    present = sorted({p["symbol"] for p in allp})
    absent = [s for s in symbols if s not in present]
    by_sym = {}
    for s in present:
        ps = [p for p in allp if p["symbol"] == s]
        bucket = defaultdict(list)
        for p in ps:
            bucket["<=30" if p["dte"] <= 30 else "31-90" if p["dte"] <= 90 else "91-365" if p["dte"] <= 365 else ">365"].append(bool(p["flag"]))
        per_day = defaultdict(list)
        for qd, pp in days_pairs:
            per_day[qd] += [bool(p["flag"]) for p in pp if p["symbol"] == s]
        rec = {"n": len(ps), "share": sum(p["flag"] for p in ps) / len(ps),
               "share_by_dte": {k: {"n": len(v), "share": sum(v) / len(v)} for k, v in bucket.items()},
               "share_by_day": {qd: sum(v) / len(v) for qd, v in per_day.items() if v}}
        for var in ("flag_literal", "flag_box", "flag_curve"):
            v = [p[var] for p in ps if var in p]
            if v:
                rec["share_" + var[5:]] = sum(v) / len(v)
        by_sym[s] = rec
    rows = [(f"pooled share of near-ATM pairs outside parity +/- (half-spreads + 10 bp of spot) < {bound:.0%} ({flags}/{n} = {share:.2%})",
             share < bound, flags / max(min_n, n) >= bound),
            (f"day-clustered 95% CI entirely below {bound:.0%} ({len(by_day)} capture days; needs >= {min_days})",
             None if hi is None else hi < bound, lo is not None and lo >= bound),
            ("every named chain captured (" + ", ".join(symbols) + ")" + (f"; missing {absent}" if absent else ""), True if not absent else None, False)]
    verdict, why = _decide(rows, n, min_n, "pairs")
    alt = sum(bool(p.get("flag_box", p["flag"])) for p in allp)        # SPX judged at its own box rate, the rest unchanged
    stat = {"n_pairs": n, "n_flagged": flags, "share": share, "day_cluster_ci": [lo, hi], "n_days": len(by_day), "by_symbol": by_sym,
            "absent_symbols": absent, "share_spx_at_box_rate": alt / n, "verdict": verdict}
    return {"verdict": verdict, "n": n, "reason": why, "stat": stat}


def parity_implied_spot(values, spot: float, quote_day: str, r: float, div_amount: Optional[float] = None, dte_range=(1, 10),
                        n_near: int = 4) -> Optional[dict]:
    """Quote-synchronous spot from the short-dated parity: median of K e^{-rT} + C_mid - P_mid + PV(D) over the n_near
    strikes nearest the close of every expiry with dte in dte_range (European parity; the early-exercise premium of
    near-ATM options a few days out is small). For SPX it is S e^{-qT}, so it carries up to ~10 days of dividend yield.
    None without such pairs. offset_bp is the implied spot against the close."""
    xs = []
    for (root, e), legs in chain_by_root(values).items():
        dte = _dte(e, quote_day)
        if not dte_range[0] <= dte <= dte_range[1]:
            continue
        T = dte / 365.0
        pvd = pv_dividends(quote_day, e, div_amount, r) if div_amount else 0.0
        for k in nearest_strikes(legs, spot, n_near):
            xs.append(k * math.exp(-r * T) + _mid(legs["call"][k]) - _mid(legs["put"][k]) + pvd)
    if not xs:
        return None
    s = float(np.median(xs))
    return {"spot": s, "close": float(spot), "offset_bp": (s / spot - 1.0) * 1e4, "n": len(xs)}


def spot_timing(days_pairs: Sequence[tuple], sync_days_pairs: Sequence[tuple], offsets: dict) -> dict:
    """T-137 spot-timing diagnostic. days_pairs: [(quote_day, pairs)] judged at the quote-day close; sync_days_pairs: the
    same chains with the American bounds re-judged at the quote-synchronous spot (parity_implied_spot; SPX pairs are
    passed unchanged, its check runs on its own regression forward). offsets: {(quote_day, symbol): parity_implied_spot}.
    Returns per (day, symbol) flags at the close and at the synchronous spot (flags that vanish are spot-timing
    artefacts) and the pooled shares under the main and the lenient (SPX at its own box rate) readings, at both spots."""
    def pooled(dp):
        ps = [p for _, pp in dp for p in pp]
        n = len(ps)
        main = sum(bool(p["flag"]) for p in ps)
        lenient = sum(bool(p.get("flag_box", p["flag"])) for p in ps)
        return n, main, lenient

    def per(dp):
        out = defaultdict(lambda: {"n": 0, "flags": 0, "upper": 0, "lower": 0})
        for qd, pp in dp:
            for p in pp:
                c = out[(qd, p["symbol"])]
                c["n"] += 1
                c["flags"] += bool(p["flag"])
                if p.get("side") in ("upper", "lower"):
                    c[p["side"]] += 1
        return out

    n0, m0, l0 = pooled(days_pairs)
    n1, m1, l1 = pooled(sync_days_pairs)
    a, b = per(days_pairs), per(sync_days_pairs)
    rows = []
    for key in sorted(set(a) | set(b)):
        ca, cb, off = a.get(key, {}), b.get(key, {}), offsets.get(key) or {}
        rows.append({"quote_day": key[0], "symbol": key[1], "close": off.get("close"), "implied_spot": off.get("spot"),
                     "offset_bp": off.get("offset_bp"), "n_short_dated": off.get("n"), "n": ca.get("n", 0),
                     "flags_at_close": ca.get("flags", 0), "upper_at_close": ca.get("upper", 0), "lower_at_close": ca.get("lower", 0),
                     "flags_at_implied_spot": cb.get("flags", 0),
                     "spot_timing_artefacts": max(0, ca.get("flags", 0) - cb.get("flags", 0))})
    return {"n_close": n0, "n_sync": n1, "share_close": m0 / n0 if n0 else None, "share_sync": m1 / n1 if n1 else None,
            "lenient_close": l0 / n0 if n0 else None, "lenient_sync": l1 / n1 if n1 else None,
            "flags_close": m0, "flags_sync": m1, "lenient_flags_close": l0, "lenient_flags_sync": l1, "by_day_symbol": rows}


# =================================================================================================== harnesses ==

def _btc_inputs(archive) -> tuple:
    days, close, _ = _daily(archive, BTC_B)
    dv = index_closes(_rows(archive, DVOL_B))
    keep = [i for i, d in enumerate(days) if d in dv]
    d2 = [days[i] for i in keep]
    return d2, close[keep], np.array([dv[d] for d in d2], dtype=float)


def _deribit_expiry(code: str) -> Optional[datetime]:
    try:
        return datetime.strptime(code, "%d%b%y").replace(hour=8, tzinfo=timezone.utc)
    except ValueError:
        return None


def _dvol_points(dvol_rows) -> dict:
    """{day: (close, available_at)} from deribit-dvol rows; the close of the candle keyed d is the value at 24:00 UTC of d."""
    out = {}
    for r in dvol_rows:
        v = r["value"]
        if v.get("ts_ms") is None or v.get("close") is None:
            continue
        d = datetime.fromtimestamp(v["ts_ms"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        out[d] = (float(v["close"]), str(r.get("available_at") or ""))
    return out


def measured_atm_over_dvol(surface_rows_by_name: dict, dvol: dict, target_days: float = 30.0) -> tuple:
    """Mean over captures of the 30-day ATM mark IV (total-variance interpolation between the Deribit expiries bracketing
    30 days) over DVOL at the capture's prior 00:00 UTC close (the candle keyed the day before the capture). dvol:
    {day: close} or {day: (close, available_at)}; with availability, a candle not yet available at the capture is skipped."""
    ratios = []
    for name, rows in sorted(surface_rows_by_name.items()):
        if not rows:
            continue
        obs = rows[0].get("observed_at") or rows[0].get("available_at")
        try:
            t0 = datetime.fromisoformat(str(obs).replace(" ", "T"))
        except ValueError:
            continue
        if t0.tzinfo is None:
            t0 = t0.replace(tzinfo=timezone.utc)
        pts = []
        for r in rows:
            v = r["value"]
            ex = _deribit_expiry(str(v.get("expiry", "")))
            if ex is None or v.get("atm_mark_iv") is None:
                continue
            dd = (ex - t0).total_seconds() / 86400.0
            if dd > 0:
                pts.append((dd, float(v["atm_mark_iv"]) / 100.0))
        pts.sort()
        below = [p for p in pts if p[0] <= target_days]
        above = [p for p in pts if p[0] > target_days]
        if not below or not above:
            continue
        (d1, v1), (d2, v2) = below[-1], above[0]
        w = (d2 - target_days) / (d2 - d1)
        var = (v1 ** 2 * d1 * w + v2 ** 2 * d2 * (1 - w)) / target_days
        key = (t0.date() - timedelta(days=1)).isoformat()
        pt = dvol.get(key)
        if isinstance(pt, tuple):
            ok = bool(pt[1]) and pt[1].replace(" ", "T") <= t0.isoformat()
            pt = pt[0] if ok else None
        if pt is not None and pt > 0:
            ratios.append(math.sqrt(var) * 100 / pt)
    return (float(np.mean(ratios)), len(ratios)) if ratios else (None, 0)


def _spy_vix_control(archive) -> Optional[dict]:
    """SPY/VIX MODEL-PRICED hedged short 30-DTE straddle (batch6_var engine: dividend forward, raw closes, bill rate)
    over the same window, as T-255's positive control. None when its bundles are missing."""
    if not all(_has(archive, b) for b in (SPY_B, VIX_B, DTB3_B)):
        return None
    try:
        from mandel.experiments.batch6_var import _spy_frame, straddle_cycles
        fr = _spy_frame(archive)
        first = bisect_left(fr["days"], "2021-04-01")
        r = straddle_cycles(fr, 1.0, side=-1, hedge=True, first=first)
        keep = [i for i, d in enumerate(r["day"]) if d <= "2026-09-30"]
        x = (r["pnl"] / r["prem"])[keep]
        return {"n": int(x.size), "mean": float(x.mean()) if x.size else None}
    except Exception as exc:                     # a control must never break the harness
        return {"n": 0, "mean": None, "error": f"{type(exc).__name__}: {exc}"}


def b6_xc_btc_hedged_straddle(archive):
    """T-255: MODEL-PRICED delta-hedged short 30-day ATM BTC straddle at DVOL, 2021-04 to 2026-09."""
    miss = _missing(archive, [BTC_B, DVOL_B])
    if miss:
        return miss
    days, close, dv = _btc_inputs(archive)
    surf = {nm: _rows(archive, nm, filtered=False) for nm in _names(archive, DSURF_P) if _has(archive, nm)}
    ms, k = measured_atm_over_dvol(surf, _dvol_points(_rows(archive, DVOL_B, filtered=False)))
    note = (f"; measured 30-day ATM mark IV / DVOL = {ms:.3f} on {k} Deribit book capture(s)" if ms else
            "; no Deribit surface capture to measure the ATM IV / DVOL gap")
    rep = btc_vrp_straddle(days, close, dv, measured_scale=ms, measured_note=note, spy_control=_spy_vix_control(archive))
    return _out(rep["stat"], rep["n"], rep["verdict"], rep["reason"])


def b6_xc_inverse_strangle_hedge(archive):
    """T-261: MODEL-PRICED short 15-delta inverse BTC strangle, coin-corrected vs naive delta hedge, 2021-04 to 2026-09."""
    miss = _missing(archive, [BTC_B, DVOL_B])
    if miss:
        return miss
    days, close, dv = _btc_inputs(archive)
    rep = inverse_hedge_ratio(days, close, dv)
    return _out(rep["stat"], rep["n"], rep["verdict"], rep["reason"])


def _capture_meta(rows: list, trading_days: list) -> tuple:
    """(quote_day, note): the session the capture's quotes belong to, None for an intraday capture (13:30-21:15 UTC), whose
    quotes are not synchronous with a close."""
    if not rows:
        return None, "empty capture"
    obs = str(rows[0].get("observed_at") or rows[0].get("available_at") or "")
    hhmm = obs[11:16]
    if "13:30" <= hhmm < "21:15":
        return None, f"intraday capture at {obs} UTC (quotes not synchronous with a close)"
    return _quote_day(obs, trading_days), ""


def _spot_history(archive, name: str) -> tuple:
    """(days, RAW close, adjclose, bundle created_at) of a daily-history bundle, unfiltered: a quote-day close is used only
    when the bundle was captured after that session closed (see _load_captures), so no bar that was still open enters."""
    return _daily_from_rows(_rows(archive, name, filtered=False)) + (str(getattr(archive.get(name), "created_at", "") or ""),)


def _close_final(created_at: str, quote_day: str) -> bool:
    """The daily bundle was captured after the quote day's 16:00 ET close (21:15 UTC covers EST and EDT)."""
    return bool(created_at) and created_at[:16].replace(" ", "T") >= f"{quote_day}T21:15"


def _load_captures(archive, sym: str, notes: list, hist: Optional[tuple] = None) -> list:
    """[(quote_day, spot RAW close, [values], capture name)] for each loadable options-chain-<sym>-<date> bundle, one per
    quote day (a later capture of the same session's quotes is skipped). Spot is the RAW close of the quote day."""
    days, close, _, created = hist if hist is not None else _spot_history(archive, HIST_B[sym])
    px = dict(zip(days, close))
    out, seen = [], set()
    for nm in _capture_names(archive, sym):
        rows = list(archive.load(nm))
        qd, why = _capture_meta(rows, days)
        if qd is None or qd not in px or not _close_final(created, qd):
            notes.append(f"{nm} skipped: {why or 'no final close on its quote day ' + str(qd)}")
            continue
        if qd in seen:
            notes.append(f"{nm} skipped: a capture of the {qd} quotes is already used")
            continue
        seen.add(qd)
        out.append((qd, float(px[qd]), [r["value"] for r in rows], nm))
    return out


def _bill(dtb3: dict, quote_day: str) -> tuple:
    pp = prior_print(dtb3, quote_day)
    return (dtb3_continuous(pp[1]), pp[0]) if pp else (None, None)


def _bill_dgs3mo(dgs3mo: dict, dtb3: dict, quote_day: str) -> tuple:
    """(continuous rate, print day, source) of T-199's 3-month bill, FRED DGS3MO: the archived print dated strictly before
    the quote day. With fred-DGS3MO not archived (dgs3mo empty), the DGS3MO_REF print, used only when it carries the
    same date as the latest DTB3 print before the quote day (so it is the latest FRED print, not a stale one); else
    (None, None, None)."""
    if dgs3mo:
        pp = prior_print(dgs3mo, quote_day)
        return (bey_continuous(pp[1]), pp[0], DGS3MO_B) if pp else (None, None, None)
    pp, pd = prior_print(DGS3MO_REF, quote_day), prior_print(dtb3, quote_day)
    if pp and pd and pp[0] == pd[0]:
        return bey_continuous(pp[1]), pp[0], "DGS3MO_REF (fred-DGS3MO not archived)"
    return None, None, None


def _bill_curve(dtb3: dict, dgs2: dict, quote_day: str):
    """Continuous rate at maturity T: the 3-month bill up to 0.25y, the 2-year note (semiannual BEY) from 2y, linear between."""
    b, _ = _bill(dtb3, quote_day)
    p2 = prior_print(dgs2, quote_day) if dgs2 else None
    if b is None or p2 is None:
        return None
    y2 = 2 * math.log(1 + p2[1] / 200)
    return lambda T: b if T <= 0.25 else (y2 if T >= 2.0 else b + (y2 - b) * (T - 0.25) / 1.75)


def b6_xc_spy_spx_financing(archive):
    """T-194: SPY parity-implied financing (+ fee) vs SPXW box rate, 30-64 DTE SPY expiries before the 2026-12-18 ex-date."""
    caps_spy, caps_spx = _capture_names(archive, "SPY"), _capture_names(archive, "SPX")
    miss = _missing(archive, [SPY_B, GSPC_B] + ([] if caps_spy else ["options-chain-SPY-<date>"]) + ([] if caps_spx else ["options-chain-SPX-<date>"]))
    if miss:
        return miss
    notes = []
    spy = _load_captures(archive, "SPY", notes)
    spx = {qd: (s, v) for qd, s, v, _ in _load_captures(archive, "SPX", notes)}
    captures = [{"quote_day": qd, "spy_spot": s, "spx_spot": spx[qd][0], "spy": v, "spx": spx[qd][1]} for qd, s, v, _ in spy if qd in spx]
    rep = spy_spx_financing(sorted(captures, key=lambda c: c["quote_day"]))
    stat = dict(rep["stat"], skipped=notes, capture_quote_days=[c["quote_day"] for c in captures])
    return _out(stat, rep["n"], rep["verdict"], rep["reason"] + (f" [skipped: {'; '.join(notes)}]" if notes else ""))


def b6_xc_gld_implied_carry(archive):
    """T-199: GLD option-implied financing rate (ATM +/- 3, 90-365 DTE) vs 3-month bill - 0.40%."""
    caps = _capture_names(archive, "GLD")
    has_dgs = _has(archive, DGS3MO_B)
    miss = _missing(archive, [HIST_B["GLD"]] + ([] if has_dgs else [DTB3_B]) + ([] if caps else ["options-chain-GLD-<date>"]))
    if miss:
        return miss
    dgs3mo = _series(archive, DGS3MO_B) if has_dgs else {}
    dtb3 = _series(archive, DTB3_B) if _has(archive, DTB3_B) else {}
    notes = []

    def prep(sym):
        out = []
        for qd, s, v, nm in _load_captures(archive, sym, notes):
            b, bd, src = _bill_dgs3mo(dgs3mo, dtb3, qd)
            p, pdy = _bill(dtb3, qd)
            if b is None and p is None:
                notes.append(f"{nm} skipped: no DGS3MO or DTB3 print before {qd}")
                continue
            out.append({"quote_day": qd, "spot": s, "values": v, "bill": b, "bill_day": bd, "bill_src": src, "proxy": p, "proxy_day": pdy})
        return sorted(out, key=lambda c: c["quote_day"])
    gld = prep("GLD")
    slv = prep("SLV") if _has(archive, HIST_B["SLV"]) and _capture_names(archive, "SLV") else []
    basis = {}
    if _has(archive, GSPC_B) and _capture_names(archive, "SPX"):
        spx = {qd: (s, v) for qd, s, v, _ in _load_captures(archive, "SPX", notes)}
        for c in gld:
            rb = c["bill"] if c["bill"] is not None else c["proxy"]
            if c["quote_day"] in spx:
                exps = sorted({p["expiry"] for p in implied_carry_pairs(c["values"], c["spot"], c["quote_day"], rb, GLD_FEE)})
                basis[c["quote_day"]] = box_bill_basis(spx[c["quote_day"]][1], spx[c["quote_day"]][0], c["quote_day"], rb, exps)
    rep = gld_carry(gld, slv=slv, basis=basis)
    stat = dict(rep["stat"], skipped=notes)
    return _out(stat, rep["n"], rep["verdict"], rep["reason"] + (f" [skipped: {'; '.join(notes)}]" if notes else ""))


def b6_xc_parity_deviation_scan(archive):
    """T-137: near-ATM parity deviations on captured SPX (European) and SPY / GLD / IBIT (American bounds) chains."""
    syms = ("SPX", "SPY", "GLD", "IBIT")
    caps = {s: _capture_names(archive, s) for s in syms}
    miss = _missing(archive, [DTB3_B] + [HIST_B[s] for s in syms] + [f"options-chain-{s}-<date>" for s in syms if not caps[s]])
    if miss:
        return miss
    dtb3 = _series(archive, DTB3_B)
    dgs2 = _series(archive, DGS2_B) if _has(archive, DGS2_B) else {}
    notes, by_day, t181 = [], defaultdict(list), []
    sync_by_day, offsets = defaultdict(list), {}
    spy_hist = None
    for s in syms:
        hist = _spot_history(archive, HIST_B[s])
        if s == "SPY":
            spy_hist = hist[:3]
        for qd, spot, vals, nm in _load_captures(archive, s, notes, hist):
            r, _ = _bill(dtb3, qd)
            if r is None:
                notes.append(f"{nm} skipped: no DTB3 print before {qd}")
                continue
            curve = _bill_curve(dtb3, dgs2, qd)
            div = last_dividend(*spy_hist, before=qd) if s == "SPY" else None
            si = parity_implied_spot(vals, spot, qd, r, div)
            if si:
                offsets[(qd, s)] = si
            if s == "SPX":
                ps = european_pairs(vals, spot, qd, r, r_curve=curve)
                by_day[qd] += ps
                sync_by_day[qd] += ps                    # judged on its own regression forward: the close enters only the tolerance
            else:
                ps = american_pairs(vals, spot, qd, r, s, div, r_curve=curve)
                by_day[qd] += ps
                sync_by_day[qd] += american_pairs(vals, si["spot"], qd, r, s, div) if si else ps
            if s in ("SPX", "SPY"):
                t181.append((qd, s, spot, [{"value": v} for v in vals]))
    rep = parity_scan(sorted(by_day.items()), syms)
    st = rep["stat"]
    t181_txt, t181_out = "", None
    if t181:
        try:
            from mandel.experiments.options_market import parity_check
            pc = parity_check(t181, [{"value": {"day": d, "value": v}} for d, v in dtb3.items()])
            t181_out = [{k: d.get(k) for k in ("day", "symbol", "pairs", "median_rate_gap_bp", "violation_rate")} for d in pc.get("per_day", [])]
            t181_txt = "; T-181 parity_check (C - P regressed on K, 10 strikes, >= 30 DTE): implied rate minus bill " + ", ".join(
                f"{d['symbol']} {d['day']} {_s(d['median_rate_gap_bp'], 0)} bp" for d in t181_out) + " (its slope rate is noise-dominated for SPY's $1 strikes)"
        except Exception as exc:                 # the companion check is a control; it must not break the harness
            t181_txt = f"; T-181 parity_check not run ({type(exc).__name__})"
    sym_txt = "; ".join(
        f"{s} {v['share']:.1%} of {v['n']}"
        + (f" (by DTE " + ", ".join(f"{k} {b['share']:.0%}/{b['n']}" for k, b in sorted(v['share_by_dte'].items())) + ")")
        + (f", literal K + C - P {v['share_literal']:.1%}" if "share_literal" in v else "")
        + (f", at its own box rate {v['share_box']:.1%}" if "share_box" in v else "")
        + (f", bill-to-2y curve {v['share_curve']:.1%}" if "share_curve" in v else "")
        for s, v in st["by_symbol"].items())
    lo, hi = st["day_cluster_ci"]
    tim = spot_timing(sorted(by_day.items()), sorted(sync_by_day.items()), offsets)
    off_txt = ", ".join(f"{r_['symbol']} {r_['quote_day']} {_s(r_['offset_bp'], 1)} bp" for r_ in tim["by_day_symbol"])
    art = [r_ for r_ in tim["by_day_symbol"] if r_["spot_timing_artefacts"]]
    art_txt = "; ".join(
        f"{r_['symbol']} {r_['quote_day']}: {r_['flags_at_close']}/{r_['n']} flagged at the close ({r_['upper_at_close']} upper, "
        f"{r_['lower_at_close']} lower) vs {r_['flags_at_implied_spot']} at the implied spot ({_f(r_['close'], 3)} -> {_f(r_['implied_spot'], 3)}, "
        f"{_s(r_['offset_bp'], 1)} bp), so {r_['spot_timing_artefacts']} are spot-timing artefacts (the close print is not synchronous "
        f"with the captured option quotes), not a conversion/reversal edge" for r_ in art)
    ln_c, ln_s = tim["lenient_close"], tim["lenient_sync"]
    if ln_c is not None and ln_s is not None and ln_c >= 0.01 > ln_s:
        ln_txt = ("the lenient reading clears 1% once the stale close is replaced, so the failure rests on the bill-financed SPX "
                  "parity forward alone")
    elif ln_s is not None and ln_s >= 0.01:
        ln_txt = "the lenient reading still fails at the quote-synchronous spot"
    else:
        ln_txt = "the lenient reading passes at either spot, so the failure rests on the bill-financed SPX parity forward alone"
    tim_txt = (f". Spot timing: the short-dated parity (median K e^(-rT) + C - P + PV(D) over the 4 strikes nearest the close at 1-10 "
               f"DTE) puts the quote-synchronous spot at {off_txt} from the quote-day close (SPX's is S e^(-qT), within about 4 bp of S, and "
               f"is reported only: SPX is judged on its own regression forward, where the close enters only the tolerance)"
               + (f"; {art_txt}" if art_txt else "")
               + f". With the American bounds judged at that spot the pooled share is {_pct(tim['share_sync'], 2).lstrip('+')} "
               f"({tim['flags_sync']}/{tim['n_sync']}). With SPX judged at its own box rate (the most lenient reading) it is "
               f"{_pct(ln_c, 2).lstrip('+')} ({tim['lenient_flags_close']}/{tim['n_close']}) at the close and {_pct(ln_s, 2).lstrip('+')} "
               f"({tim['lenient_flags_sync']}/{tim['n_sync']}) at the quote-synchronous spot: {ln_txt}")
    reason = (f"{st['n_pairs']} near-ATM pairs (3 strikes nearest the quote-day close, every expiry) over {st['n_days']} quote day(s) "
              f"{sorted(by_day)}: {st['n_flagged']} outside parity +/- (half-spreads + 10 bp of spot) = {st['share']:.2%} (needs < 1%); "
              f"day-clustered CI " + ("n/a: " + f"{st['n_days']} capture days, needs >= {MIN_DAYS_SHARE}" if hi is None else f"{lo:.2%} to {hi:.2%}")
              + f". By chain: {sym_txt}{tim_txt}. SPX parity forward F = S e^(r - q)T with r the 3-month bill (DTB3) and q from the intercept of the "
              f"C - P on K regression; SPX options discount at their box rate, above the 3-month bill and rising with maturity, so long-dated "
              f"SPX pairs sit outside a bill-financed parity forward while the cross-strike fit at the box rate is tight; American SPY/GLD/IBIT "
              f"checked against S - PV(D) - K <= C - P <= S - K e^(-rT){t181_txt} — {rep['reason']}")
    stat = dict(st, skipped=notes, t181_parity_check=t181_out, spot_timing=tim)
    return _out(stat, rep["n"], rep["verdict"], reason + (f" [skipped: {'; '.join(notes)}]" if notes else ""))


HARNESSES = {
    "b6_xc_btc_hedged_straddle": b6_xc_btc_hedged_straddle,
    "b6_xc_inverse_strangle_hedge": b6_xc_inverse_strangle_hedge,
    "b6_xc_spy_spx_financing": b6_xc_spy_spx_financing,
    "b6_xc_gld_implied_carry": b6_xc_gld_implied_carry,
    "b6_xc_parity_deviation_scan": b6_xc_parity_deviation_scan,
}

THEORY_MAP = {
    "T-255": "b6_xc_btc_hedged_straddle",
    "T-261": "b6_xc_inverse_strangle_hedge",
    "T-194": "b6_xc_spy_spx_financing",
    "T-199": "b6_xc_gld_implied_carry",
    "T-137": "b6_xc_parity_deviation_scan",
}
