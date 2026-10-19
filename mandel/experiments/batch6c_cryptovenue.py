"""
Batch 6c, group ``cryptovenue``: six crypto-venue, ETF-premium and intraday claims on the bundles fetched by
``mandel.data.crypto_history`` (Coinbase candles, Kraken stablecoin-episode trades, the iShares IBIT page) and on the
Yahoo daily histories of ``mandel.data.market_history`` (IBIT, FBTC, STETH-USD, CBETH-USD, USDT-USD, USDC-USD, ETFs).
=====================================================================================================================

Each claim is tested on its own wording, trial.pass and trial.min_n (house rules, MANDEL.md section 2):
  * T-328  IBIT 2024-04..2026-09: synthetic NAV = Coinbase BTC-USD at the session close (the close of the hourly candle
           ending 16:00 ET; 13:00 ET on the NYSE early-close sessions, when IBIT's own close is struck) x bitcoin per
           share, calibrated to iShares' published Basket Bitcoin Amount / 40,000 and decayed by the 0.25%/yr sponsor fee;
           premium = IBIT close / NAV - 1; z over the trailing 60 sessions including today; |z| > 2 opens a dollar-neutral
           fade (z > 2: short IBIT / long BTC; z < -2: the reverse), closed at the first close with z back at or across
           0 or 3 sessions after the fill; signal days 2024-04-01..2026-09-30 (the launch period before 2024-04 is out of
           the main read); 0.85% a round trip. Pass: one-sided 95% lower bound of the mean net return per trade > 0,
           trades resampled in ISO-week clusters (the trial's 'clustered by week'); min_n 30 trades. Pre-registered park
           rule: otherwise park as 'premium within AP cost band' (reported as ``park_condition``: the pass fails and the
           break-even cost, the mean gross per trade, lies below 0.85% under both fill readings). Reported, not in the
           pass: AR(1) half-life, signal count, gross mean, 0.25% tier, 2025-2026 alone, the official iShares premium
           (lagged only), an hour-average BTC signal (CF BRR NY is an hour-window rate), FBTC, the IBIT/FBTC twin, z
           excluding today, the DSR over the 6 declared variants (CME MBT and GBTC not computable).
  * T-330  USDT and USDC discount episodes on the Yahoo daily closes (the library rule: the first close below 0.995 after
           at least 5 consecutive closes at or above 0.998), signal days 2018-2026; buy at the next close (the close
           after the signal close), sell at the first close at or above 0.999 or 3 days after the entry; re-priced at
           executable venue closes where they exist (the last Kraken USDTZUSD / USDCUSD trade before each 00:00 UTC in the
           archived episode windows; Coinbase USDT-USD daily from 2021-05), else the Yahoo composite; 0.40% a round
           trip. Pass: one-sided 95% lower bound of the pooled mean net return per episode > 0 with at least 10 episodes;
           fewer than 10 is 'inconclusive (too few events)' by the claim's own rule.
  * T-365  stETH/ETH on Yahoo closes (both 00:00 UTC): discount d = 1 - P(stETH)/P(ETH) above 1.5% on two consecutive
           days -> buy stETH at that close, hold 10 days, log return of stETH/ETH net of 30 bp, non-overlapping episodes
           2023-04-12..2026-09-30. Pass: lower end of the two-sided 90% CI > 0 (episode bootstrap, and the trial's
           shuffled-increment null) with at least 15 episodes, DSR over 4 trials; fewer than 15 episodes is 'insufficient
           events' by the claim's own rule. The pre-Shapella regime is reported separately, not pooled.
  * T-366  Coinbase CBETH-ETH daily closes 2023-04-12..2026-09-30: OLS slope of log(ratio) on calendar time (years of
           365 days), Newey-West HAC lag 30. Pass: annualised slope in [1.5%, 3.5%] (as a log rate and compounded: both
           readings must agree) with the HAC 95% CI excluding 0 (lower end > 0); min_n 900 days.
  * T-419  High-volume return premium across the 21 store ETFs + GDX (the library's asset list) + BTC-USD/ETH-USD on
           Coinbase daily candles (the trial's data line), event days 2005-2026: idiosyncratic volume u = x - beta x_SPY
           with x = ln V - ln(mean V over the trailing 50 days) and beta the trailing-50-day slope of x on x_SPY; event = u
           above the 90th percentile of its trailing 50 values and |r| < 2 sigma (trailing 50); entry at the next open,
           exit 10 trading days later; abnormal return = (W - rf) - beta_250 (M - rf) with M the SPY return over the same
           wall-clock span. Pass: >= 800 events AND mean abnormal return >= 50 bps AND block-shift placebo p < 0.01 (2,000
           independent circular shifts of each asset's event dates) AND calendar-time net Sharpe > 0.5 after 5 bps a round
           trip AND the same sign in the ETF and crypto buckets AND DSR >= 0.95 over the declared 36 cells.
  * T-424  Coinbase hourly 2019-2026: point-in-time top-10 alt basket by trailing 30-day Coinbase dollar volume (days
           D-30..D-1 for UTC day D; listed = traded on D-1; BTC, stablecoins and wrapped / liquid-staking tokens excluded by
           a declared list); theta = 1 sd of BTC hourly returns fitted on 2019-2022; follow rule: hold the equal-weight
           basket for the next hour when BTC's last-hour return > theta (flat otherwise); 50 bps a round trip; test
           2023-01..data end. Pass: >= 20,000 out-of-sample hours AND BTC's lagged return positively predicts the basket's
           next-hour return (the claim's first clause; HAC t > 1.645) AND net Sharpe > 0.5 AND stationary-bootstrap
           (24-hour mean blocks) p < 0.05 for a net mean <= 0 AND DSR >= 0.95 over the declared 14 cells.

Conventions
  * Data. Every bundle through ``archive.load``; a row is used only when its ``available_at`` is not after the bundle's
    capture time. Yahoo ETF prices are ``adjclose`` (opens on the same basis); IBIT/FBTC raw closes (no distributions).
    Coinbase rows follow the daily-history convention (bar start, available at bar end). STETH-USD and CBETH-USD Yahoo
    histories ARE archived (fetched by market_history after the crypto group's uncovered list was written), so T-365 and
    T-366's robustness series use them; a harness that needs them still names them in ``_missing``.
  * Point in time (rules 4, 12). T-328: the close and the 16:00 ET candle are stamped at the fill, so both readings run:
    'live' (fill at the signal close) and 'lagged' (decide on the close, fill at the next session's close); the criterion
    needs both. The bitcoin-per-share calibration is a 2026-10 snapshot, but z is exactly invariant to a constant
    bitcoin per share (premium = y / c - 1 is affine in y = close / (fee decay x spot)) and trade P&L does not use it, so
    the snapshot carries no future information into any decision; it only sets the reported premium level. The official
    iShares premium (known 09:30 ET the next session) is a lagged-only robustness reading. T-330: entries at the close
    after the signal close (the claim); venue closes are trades public at execution. T-365: live and lagged fills, as
    T-328. T-419: volume, return and percentile at the event close, entry at the next open. T-424: the hourly candle is
    stamped at its close, which is also the fill (one information set; the one-bar-later fill is reported).
  * Intervals and nulls (rule 6). Per-trade and per-episode means: studentized bootstrap with cluster-robust s.e.
    (``batch6c_pub.cluster_stud``; T-328 ISO-week clusters, T-330/T-365 each episode its own cluster); "95% lower bound" is
    one-sided (the lower end of the two-sided 90% interval). Interval ends are means over 5 bootstrap seeds with their
    Monte Carlo s.e. (25 when 5 cannot resolve them). T-366: HAC normal interval. T-424: studentized stationary bootstrap
    (Bartlett s.e., bandwidth 24). T-419: the trial's placebo.
  * Calendars (rule 10). T-328, T-330, T-365 and T-419 are signal-driven; T-366 is a full-sample slope; T-424 trades every
    hour. No grid phase is free.
  * Costs (rule 9) as stated: T-328 0.85% (0.25% sensitivity), T-330 0.40% (1.2% sensitivity), T-365 30 bp, T-419 5 bps a
    round trip (crypto 50 bps reported), T-424 50 bps (30 bps maker reported).
  * Rule 5: below trial.min_n the verdict is never supported and a failing criterion counts only when it fails
    decisively (its bound at the pass's own confidence wholly on the wrong side). T-330 and T-365 pre-register 'too few
    events' / 'insufficient events' below their counts, so there a shortfall is inconclusive whatever the bound says.

Verdicts use ``underlying2._verdict`` through ``batch6b_bw._decide``: any implemented criterion failing -> not_supported;
any criterion not implemented (None) -> at best inconclusive; supported needs every criterion implemented and passing.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist
from typing import Callable, Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np

from mandel.experiments.batch6b_bw import Bills, _ci, _clean, _decide, _f, _pc, _s, all_constructions, mc_escalate, resolve
from mandel.experiments.batch6c_mom import family_dsr
from mandel.experiments.batch6c_pub import cluster_stud, granger
from mandel.experiments.batch6c_rates import hac_mean, nw_lag, ols_nw
from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying2 import _verdict
from mandel.validation.backtest_eval import _hac_var, sharpe_ratio

N_BOOT = 2000                  # bootstrap draws per seed
REPS = 5                       # bootstrap seeds behind every decisive interval end or p-value
SEED = 0
ALPHA = 0.05
DSR_PASS = 0.95
NY = ZoneInfo("America/New_York")
UTC = timezone.utc
_N = NormalDist()
_EPOCH_ORD = date(1970, 1, 1).toordinal()

DTB3_B = "fred-DTB3"
VIX_B = "cboe-VIX-history"


def dh(sym: str) -> str:
    return "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in sym)


def cbd(pid: str) -> str:
    return f"coinbase-daily-{pid}"


def cbh(pid: str) -> str:
    return f"coinbase-hourly-{pid}"


# ================================================================================================= data access ==

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
    except (KeyError, AttributeError):
        return False


def _missing(archive, names: Sequence[str]):
    miss = [n for n in names if not _has(archive, n)]
    if miss:
        v, why = _verdict([(f"data bundles {miss} archived", None)])
        return ({"missing_bundles": miss}, 0, v,
                f"missing data bundles {miss}: the claim cannot be tested until they are archived — {why}")
    return None


def _epoch(s) -> float:
    d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).timestamp()


def _cap(archive, name: str) -> Optional[str]:
    return getattr(archive.get(name), "created_at", None)


def _visible(av, cap) -> bool:
    """available_at <= capture time (string compare when both are +00:00 ISO stamps, else parsed)."""
    if not cap or not av:
        return True
    if av.endswith("+00:00") and cap.endswith("+00:00"):
        return av <= cap
    return _epoch(av) <= _epoch(cap)


def _stream(archive, name: str):
    """Rows of a bundle that were available when the bundle was captured (streamed, not cached)."""
    cap = _cap(archive, name)
    for r in archive.load(name):
        if _visible(r.get("available_at"), cap):
            yield r


def _num(x) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _dday(ts) -> str:
    return datetime.fromtimestamp(float(ts), tz=UTC).strftime("%Y-%m-%d")


def _ord(d) -> int:
    return (date.fromisoformat(d) if isinstance(d, str) else d).toordinal()


def _bars(archive, name: str) -> dict:
    """{'days', 'open', 'close' (raw), 'adj' (adjclose; close when absent), 'aopen' (open on the adj basis), 'volume'} of a
    Yahoo daily-history or Coinbase daily bundle, keyed by the UTC date of the bar start."""
    def load():
        by = {}
        for r in _stream(archive, name):
            v = r.get("value") or {}
            c = _num(v.get("close"))
            if c is None or c <= 0 or v.get("t") is None:
                continue
            a = _num(v.get("adjclose"))
            o = _num(v.get("open"))
            vol = _num(v.get("volume"))
            by[_dday(v["t"])] = (o if o and o > 0 else float("nan"), c, a if a and a > 0 else float("nan"),
                                  vol if vol is not None else float("nan"))
        days = sorted(by)
        arr = np.array([by[d] for d in days], float).reshape(-1, 4)
        opn, close, adj, vol = arr[:, 0], arr[:, 1], arr[:, 2].copy(), arr[:, 3]
        ratio = 1.0
        for i in range(len(days)):
            if np.isfinite(adj[i]):
                ratio = adj[i] / close[i]
            else:
                adj[i] = close[i] * ratio
        return {"days": days, "open": opn, "close": close, "adj": adj, "aopen": opn * adj / close, "volume": vol}
    return _cached(archive, ("bars", name), load)


def _hourly(archive, name: str) -> tuple:
    """(bar starts as int64 unix seconds, closes) of a Coinbase hourly bundle, sorted, streamed."""
    def load():
        by = {}
        for r in _stream(archive, name):
            v = r.get("value") or {}
            c = _num(v.get("close"))
            if c is not None and c > 0 and v.get("t") is not None:
                by[int(v["t"])] = c
        ks = sorted(by)
        return np.array(ks, np.int64), np.array([by[k] for k in ks], float)
    return _cached(archive, ("hourly", name), load)


def _hourly_mid(archive, name: str) -> tuple:
    """(bar starts, (open + high + low + close) / 4) of a Coinbase hourly bundle: an hour-average proxy."""
    def load():
        by = {}
        for r in _stream(archive, name):
            v = r.get("value") or {}
            xs = [_num(v.get(k)) for k in ("open", "high", "low", "close")]
            if all(x is not None and x > 0 for x in xs) and v.get("t") is not None:
                by[int(v["t"])] = sum(xs) / 4.0
        ks = sorted(by)
        return np.array(ks, np.int64), np.array([by[k] for k in ks], float)
    return _cached(archive, ("hourly_mid", name), load)


def _bills(archive) -> Bills:
    def load():
        out = {}
        for r in _stream(archive, DTB3_B):
            v = r.get("value") or {}
            x = _num(v.get("value", v.get("close")))
            if x is not None and v.get("day"):
                out[v["day"]] = x
        return Bills(out)
    return _cached(archive, ("bills",), load)


def _vix(archive) -> dict:
    def load():
        out = {}
        for r in _stream(archive, VIX_B):
            v = r.get("value") or {}
            c = _num(v.get("close"))
            if c is not None and v.get("day") and not v.get("flag"):
                out[v["day"]] = c
        return out
    return _cached(archive, ("vix",), load)


def _names(archive, prefix: str) -> list:
    try:
        es = archive.entries(kind="data")
    except (AttributeError, TypeError):
        try:
            es = archive.entries()
        except (AttributeError, TypeError):
            return []
    return sorted(e.name for e in es if getattr(e, "name", "").startswith(prefix))


# ================================================================================================== formatting ==

def _bp(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 1e4:+.{nd}f} bp"


def _p3(x) -> str:
    return _pc(x, 3)


def _pu(x, nd: int = 1) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:.{nd}f}%"


def _out(stat: dict, n: int, verdict: str, reason: str):
    return _clean(stat), int(n), verdict, reason


def _mean(x) -> Optional[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean()) if x.size else None


def _sr_ann(x, ppy: float) -> Optional[float]:
    x = np.asarray(x, float)
    if x.size < 3 or not x.std(ddof=1) > 0:
        return None
    return float(sharpe_ratio(x, ppy))


def wilson(k: int, n: int, z: float = 1.959964) -> list:
    if n <= 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0.0, c - h), min(1.0, c + h)]


# ================================================================================================= statistics ==

def boot_mean(x, labels: Sequence[str], thr: float = 0.0, n_boot: Optional[int] = None, reps: Optional[int] = None) -> dict:
    """Cluster studentized bootstrap of a mean (``batch6c_pub.cluster_stud``) over ``reps`` seeds, escalated when the
    seeds cannot resolve the one-sided 95% lower bound (``ci90`` lower end) against ``thr``."""
    x = np.asarray(x, float)
    nb = N_BOOT if n_boot is None else int(n_boot)
    if x.size < 4:
        return {"est": _mean(x), "ci": [None, None], "ci90": [None, None], "n": int(x.size)}
    return mc_escalate(lambda seed: cluster_stud(x, list(labels), nb, seed),
                       lambda t: resolve((t.get("ci90") or [None])[0], (t.get("ci90_mc_se") or [0.0])[0], thr, "gt")[0],
                       REPS if reps is None else reps, SEED, keys=("ci", "ci90", "ci_pct"))


def lb_row(t: dict, label: str, thr: float = 0.0, fmt: Callable = _p3) -> tuple:
    """(name, ok, decisive) for 'one-sided 95% lower bound > thr' on a ``boot_mean`` result; decisive = the one-sided 95%
    upper bound (upper end of the two-sided 90% interval) below thr."""
    lo, hi = (t.get("ci90") or [None, None])[:2]
    se_lo, se_hi = (t.get("ci90_mc_se") or [0.0, 0.0])[:2]
    ok, note = resolve(lo, se_lo, thr, "gt")
    dec = hi is not None and resolve(hi, se_hi, thr, "lt")[0] is True
    return (f"{label}: mean {fmt(t.get('est'))}, one-sided 95% lower bound {fmt(lo)}{note} > {fmt(thr) if thr else 0} "
            f"(two-sided 95% {_ci(t.get('ci'), 3, 100, '%')})", ok, dec)


def _stationary_idx(rng, n: int, mean_block: float, k: int) -> np.ndarray:
    """Politis-Romano stationary bootstrap indices (circular) for k draws, vectorised."""
    p = 1.0 / max(float(mean_block), 1.0)
    new = rng.random((k, n)) < p
    new[:, 0] = True
    starts = rng.integers(0, n, (k, n))
    pos = np.arange(n)
    last = np.maximum.accumulate(np.where(new, pos[None, :], 0), axis=1)
    st = np.take_along_axis(starts, last, axis=1)
    return (st + pos[None, :] - last) % n


def stationary_test(x, mean_block: float = 24.0, n_boot: Optional[int] = None, seed: int = SEED) -> dict:
    """Studentized stationary bootstrap of a mean (Bartlett-HAC s.e., bandwidth = the mean block): est, se, two-sided 95%
    ``ci``, p (H0: mean <= 0)."""
    nb = N_BOOT if n_boot is None else int(n_boot)
    x = np.asarray(x, float)
    n = x.size
    out = {"est": float(x.mean()) if n else None, "se": None, "ci": [None, None], "p": None, "n": int(n)}
    if n < 50:
        return out
    bw = max(1, int(round(mean_block)))
    m0 = float(x.mean())
    se0 = math.sqrt(float(_hac_var(x[None, :], bw)[0]) / n)
    out["se"] = se0
    if not se0 > 1e-14:
        out.update(ci=[m0, m0], p=0.0 if m0 > 0 else 1.0)
        return out
    rng = np.random.default_rng(seed)
    ts = []
    k = max(1, min(nb, 1_000_000 // n))
    done = 0
    while done < nb:
        kk = min(k, nb - done)
        s = x[_stationary_idx(rng, n, mean_block, kk)]
        ts.append((s.mean(axis=1) - m0) / np.sqrt(_hac_var(s, bw) / n))
        done += kk
    t = np.concatenate(ts)
    t_obs = m0 / se0
    out.update(ci=[m0 - float(np.quantile(t, 0.975)) * se0, m0 - float(np.quantile(t, 0.025)) * se0],
               p=float((np.sum(t >= t_obs) + 1) / (t.size + 1)))
    return out


def stationary_mc(x, mean_block: float = 24.0, n_boot: Optional[int] = None, reps: Optional[int] = None) -> dict:
    """``stationary_test`` over seeds; p is the replicate mean with its Monte Carlo s.e. (escalated when unresolved
    against 0.05)."""
    def run(r):
        rs = [stationary_test(x, mean_block, n_boot, SEED + k) for k in range(r)]
        out = dict(rs[0])
        ps = [q["p"] for q in rs if q["p"] is not None]
        if ps:
            out["p"] = float(np.mean(ps))
            out["p_mc_se"] = float(np.std(ps, ddof=1) / math.sqrt(len(ps))) if len(ps) > 1 else 0.0
        cis = np.array([q["ci"] for q in rs if q["ci"][0] is not None], float)
        if cis.size:
            out["ci"] = [float(v) for v in cis.mean(axis=0)]
        out["reps"] = r
        return out
    r0 = REPS if reps is None else int(reps)
    t = run(r0)
    if t.get("p") is not None and resolve(t["p"], t.get("p_mc_se"), ALPHA, "lt")[0] is None and r0 < 25:
        t = run(25)
    return t


def dsr_row(d: dict, label: str) -> tuple:
    """(name, ok, decisive) for 'DSR >= 0.95' on a ``family_dsr`` result; decisive = PSR against a zero Sharpe <= 0.05."""
    if d.get("dsr") is None:
        return f"{label} (n/a)", None, False
    obs = "n/a" if d.get("var_observed") is None else f"{d['var_observed']:.2e}"
    return (f"{label} ({d['dsr']:.3f} at {d['n_trials']} trials; var(trial SR) {d['var_trials_sr']:.2e} = {d['var_used']}; "
            f"observed {obs} over {d['n_family_computed']} computed trials; PSR vs 0 {_f(d.get('psr0'))})",
            d["dsr"] >= DSR_PASS, d.get("psr0") is not None and d["psr0"] <= 1.0 - DSR_PASS)


def ar1(x) -> tuple:
    """(phi, half-life in observations) of an AR(1) fit with intercept; half-life None unless 0 < phi < 1."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size < 20 or not np.std(x[:-1]) > 0:
        return None, None
    phi = float(np.polyfit(x[:-1], x[1:], 1)[0])
    return phi, (math.log(0.5) / math.log(phi) if 0 < phi < 1 else None)


def trailing_z(x, win: int, incl: bool = True) -> np.ndarray:
    """(x_t - mean) / sd over the trailing ``win`` observations ending at t (``incl``) or at t-1; NaN before a full
    window or when the sd is 0."""
    x = np.asarray(x, float)
    n = x.size
    z = np.full(n, np.nan)
    off = 0 if incl else 1
    for t in range(win - 1 + off, n):
        w = x[t - off - win + 1: t - off + 1]
        if not np.isfinite(w).all() or not np.isfinite(x[t]):
            continue
        sd = float(w.std(ddof=1))
        if sd > 0:
            z[t] = (x[t] - float(w.mean())) / sd
    return z


# ======================================================================================== T-328 IBIT premium ==

IBIT_B, FBTC_B = dh("IBIT"), dh("FBTC")
CB_BTC_H = cbh("BTC-USD")
ISH_PREM, ISH_SNAP = "ishares-ibit-premium-discount", "ishares-ibit-snapshots"
T328_START, T328_END = "2024-04-01", "2026-09-30"
T328_SPLIT = "2025-01-01"
T328_WIN, T328_THR, T328_MAX_HOLD = 60, 2.0, 3
T328_COST, T328_COST_HI = 0.0085, 0.0025
T328_TWIN_COST = 0.0010                 # two ETF legs at the claim's 5 bps spread each (twin variant, reported)
T328_FEE = 0.0025
T328_MIN_N = 30
T328_N_TRIALS = 6
T328_TIMINGS = ("live", "lagged")

_ET_MEMO: dict = {}


def et_epoch(day: str, hhmm: str) -> float:
    """POSIX time of ``hhmm`` New York time on ``day``."""
    k = (day, hhmm)
    v = _ET_MEMO.get(k)
    if v is None:
        v = datetime(int(day[:4]), int(day[5:7]), int(day[8:10]), int(hhmm[:2]), int(hhmm[3:5]), tzinfo=NY).timestamp()
        _ET_MEMO[k] = v
    return v


def early_close(day: str) -> bool:
    """NYSE 13:00 ET early closes: July 3 and December 24 when Monday-Thursday, and the day after Thanksgiving."""
    d = date.fromisoformat(day)
    if (d.month, d.day) in ((7, 3), (12, 24)) and d.weekday() <= 3:
        return True
    if d.month == 11 and d.weekday() == 4:
        th = d - timedelta(days=1)
        return 22 <= th.day <= 28
    return False


def close_bar_start(day: str) -> int:
    """Start of the hourly candle that ends at the session close (16:00 ET; 13:00 ET on early-close sessions)."""
    return int(et_epoch(day, "12:00" if early_close(day) else "15:00"))


def spot_at_close(days: Sequence[str], hourly: tuple) -> tuple:
    """(BTC close of the candle ending at each session's close, number of sessions where that candle is missing and the
    latest earlier candle is used instead)."""
    ts, cl = hourly
    out = np.full(len(days), np.nan)
    stale = 0
    for i, d in enumerate(days):
        t0 = close_bar_start(d)
        j = int(np.searchsorted(ts, t0, side="right")) - 1
        if j < 0 or t0 - int(ts[j]) > 6 * 3600:
            continue
        if int(ts[j]) != t0:
            stale += 1
        out[i] = cl[j]
    return out, stale


def fee_factor(days: Sequence[str], ref_day: str, fee: float = T328_FEE) -> np.ndarray:
    """Bitcoin per share on each day relative to the reference day under a constant sponsor fee (act/365)."""
    r = _ord(ref_day)
    return np.exp(fee * (r - np.array([_ord(d) for d in days], float)) / 365.0)


def fade_trades(days: Sequence[str], z: np.ndarray, A: np.ndarray, B: np.ndarray, timing: str, thr: float = T328_THR,
                max_hold: int = T328_MAX_HOLD, start: str = T328_START, end: str = T328_END) -> list:
    """Dollar-neutral fades of A against B. Signal day t in [start, end] with |z_t| > thr: sg = -1 (short A / long B)
    when z > 0, +1 otherwise; 'live' fills at the signal close, 'lagged' at the next close; exit decided at the first later
    close u with sg z_u >= 0 (z back at or across 0) or when the exit fill would be ``max_hold`` sessions after the entry
    fill, filled the same way. One position at a time; a trade still open at the data end is dropped. The exit-decision
    close u is itself re-examined as a signal (the old fade is closed at that close, so a fresh |z| > thr there opens a
    new fade; its entry fill u + lag is the previous exit fill, never before it).
    gross = sg (A_x / A_e - B_x / B_e)."""
    n = len(days)
    lag = 0 if timing == "live" else 1
    out, t = [], 0
    while t < n:
        if not (start <= days[t] <= end) or not np.isfinite(z[t]) or abs(z[t]) <= thr:
            t += 1
            continue
        e = t + lag
        if e >= n:
            break
        sg = -1.0 if z[t] > 0 else 1.0
        x = u = None
        for u in range(t + 1, n):
            if (np.isfinite(z[u]) and sg * z[u] >= 0) or (u + lag) - e >= max_hold:
                x = u + lag
                break
        if x is None or x >= n:
            break
        out.append({"signal": days[t], "entry": days[e], "exit": days[x], "e": e, "x": x, "sg": sg, "z": float(z[t]),
                    "gross": float(sg * (A[x] / A[e] - B[x] / B[e])), "sessions": x - e})
        t = u                    # re-examine the exit-decision day: next entry fill u + lag == this exit fill x
    return out


def _week(day: str) -> str:
    y, w, _ = date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def ibit_fade_test(days: Sequence[str], close: np.ndarray, spot: np.ndarray, bps_ref: float, ref_day: str,
                   start: str = T328_START, end: str = T328_END, cost: float = T328_COST, min_n: int = T328_MIN_N,
                   n_boot: Optional[int] = None, reps: Optional[int] = None) -> dict:
    """T-328 core: synthetic premium, trailing z, both fill readings, week-clustered bootstrap of the net mean per
    trade, the criteria and the park rule."""
    close, spot = np.asarray(close, float), np.asarray(spot, float)
    ok = np.isfinite(close) & np.isfinite(spot) & (spot > 0)
    days = [d for d, k in zip(days, ok) if k]
    close, spot = close[ok], spot[ok]
    bps = bps_ref * fee_factor(days, ref_day)
    prem = close / (bps * spot) - 1.0
    z = trailing_z(prem, T328_WIN)
    runs, tests, rows, gross_t = {}, {}, [], {}
    for tm in T328_TIMINGS:
        tr = fade_trades(days, z, close, spot, tm, start=start, end=end)
        runs[tm] = tr
        g = np.array([q["gross"] for q in tr], float)
        lab = [_week(q["entry"]) for q in tr]
        t = boot_mean(g - cost, lab, 0.0, n_boot, reps)
        tests[tm] = t
        gross_t[tm] = boot_mean(g, lab, cost, n_boot, reps) if g.size >= 4 else {"est": _mean(g), "ci": [None, None],
                                                                                     "ci90": [None, None]}
        rows.append(lb_row(t, f"[{tm}] {len(tr)} trades at {cost * 100:.2f}% a round trip"))
    c1 = all_constructions(rows, "one-sided 95% lower bound of the mean net return per trade > 0 (ISO-week clusters) under "
                                 "both fill readings (rule 12)")
    n = min(len(runs[tm]) for tm in T328_TIMINGS)
    crit = [c1]
    v, why = _decide(crit, n, min_n, "trades")
    win = [i for i, d in enumerate(days) if start <= d <= end]
    phi, hl = ar1(prem[win]) if win else (None, None)
    sig = int(np.sum(np.abs(z[win]) > T328_THR)) if win else 0
    per = {}
    for tm, tr in runs.items():
        g = np.array([q["gross"] for q in tr], float)
        e1 = [q for q in tr if q["entry"] < T328_SPLIT]
        e2 = [q for q in tr if q["entry"] >= T328_SPLIT]
        per[tm] = {"n": len(tr), "mean_gross": _mean(g), "mean_net": _mean(g - cost), "mean_net_hi_tier": _mean(g - T328_COST_HI),
                   "share_positive_net": float(np.mean(g - cost > 0)) if g.size else None,
                   "median_sessions": float(np.median([q["sessions"] for q in tr])) if tr else None,
                   "pre_2025": {"n": len(e1), "mean_net": _mean([q["gross"] - cost for q in e1])},
                   "2025_2026": {"n": len(e2), "mean_net": _mean([q["gross"] - cost for q in e2])},
                   "break_even_cost": _mean(g), "break_even_ci": gross_t[tm].get("ci")}
    hi_tier = {tm: lb_row(boot_mean(np.array([q["gross"] for q in runs[tm]], float) - T328_COST_HI,
                                    [_week(q["entry"]) for q in runs[tm]], 0.0, n_boot, reps),
                          f"[{tm}] at {T328_COST_HI * 100:.2f}%")[:2] for tm in T328_TIMINGS}
    passed = c1[1] is True
    be = [per[tm]["mean_gross"] for tm in T328_TIMINGS]
    park = (not passed) and all(b is not None and b < cost for b in be)
    return {"days": days, "close": close, "spot": spot, "prem": prem, "z": z, "runs": runs, "tests": tests, "gross_tests": gross_t, "per": per, "n": n,
            "ar1": phi, "half_life": hl, "signal_days": sig, "window_sessions": len(win),
            "hi_tier": hi_tier, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why,
            "park_condition": bool(park), "passed": passed}


def _premium_official(archive) -> dict:
    out = {}
    for r in _stream(archive, ISH_PREM):
        v = r.get("value") or {}
        if r.get("kind") == "premium-discount" and v.get("day") and _num(v.get("premium_discount_pct")) is not None:
            out[v["day"]] = float(v["premium_discount_pct"]) / 100.0
    return out


def _snapshot(archive) -> Optional[dict]:
    best = None
    for r in _stream(archive, ISH_SNAP):
        v = r.get("value") or {}
        if _num(v.get("btc_per_share")) and v.get("nav_as_of"):
            if best is None or v["nav_as_of"] > best["nav_as_of"]:
                best = v
    return best


def b6c_cryptovenue_ibit_premium_fade(archive):
    """T-328: fade |z| > 2 of IBIT's 16:00 ET premium to a Coinbase synthetic NAV, 0.85% a round trip."""
    miss = _missing(archive, [IBIT_B, CB_BTC_H, ISH_SNAP])
    if miss:
        return miss
    ib = _bars(archive, IBIT_B)
    hb = _hourly(archive, CB_BTC_H)
    snap = _snapshot(archive)
    if snap is None:
        v, why = _verdict([("published bitcoin per share (ishares-ibit-snapshots btc_per_share)", None)])
        return _out({"missing": "btc_per_share"}, 0, v, "no snapshot row with btc_per_share in ishares-ibit-snapshots — " + why)
    spot, stale = spot_at_close(ib["days"], hb)
    bps_ref, ref_day = float(snap["btc_per_share"]), snap["nav_as_of"]
    j = ibit_fade_test(ib["days"], ib["close"], spot, bps_ref, ref_day)
    days, prem = j["days"], j["prem"]
    ec = [d for d in days if early_close(d) and T328_START <= d <= T328_END]
    # calibration check against the official premium (2025-01-02 ..)
    off = _premium_official(archive) if _has(archive, ISH_PREM) else {}
    pm = dict(zip(days, prem))
    both = [d for d in days if d in off]
    calib = None
    if len(both) > 20:
        a = np.array([pm[d] for d in both]); b = np.array([off[d] for d in both])
        calib = {"days": len(both), "first": both[0], "last": both[-1], "corr": float(np.corrcoef(a, b)[0, 1]),
                 "mean_diff": float((a - b).mean()), "sd_diff": float((a - b).std(ddof=1)),
                 "mean_abs_official": float(np.abs(b).mean()), "p95_abs_official": float(np.quantile(np.abs(b), 0.95)),
                 "share_abs_official_le_25bp": float(np.mean(np.abs(b) <= 0.0025)),
                 "share_abs_official_le_85bp": float(np.mean(np.abs(b) <= 0.0085))}
    # variants (reported; 6 declared): official-premium z (lagged only), FBTC vs spot, IBIT/FBTC twin, z excluding today
    var, fam = {}, {"primary_live": np.array([q["gross"] - T328_COST for q in j["runs"]["live"]], float),
                    "high_tier_live": np.array([q["gross"] - T328_COST_HI for q in j["runs"]["live"]], float)}
    if len(off) > T328_WIN + 5:
        od = sorted(off)
        ix = {d: i for i, d in enumerate(ib["days"])}
        od = [d for d in od if d in ix and np.isfinite(spot[ix[d]])]
        zo = trailing_z(np.array([off[d] for d in od]), T328_WIN)
        tro = fade_trades(od, zo, np.array([ib["close"][ix[d]] for d in od]), np.array([spot[ix[d]] for d in od]), "lagged",
                          start=T328_START, end=T328_END)
        var["official_premium_lagged"] = {"n": len(tro), "first_signal": tro[0]["signal"] if tro else None,
                                          "mean_gross": _mean([q["gross"] for q in tro]),
                                          "mean_net": _mean([q["gross"] - T328_COST for q in tro])}
    else:
        var["official_premium_lagged"] = "not computable: ishares-ibit-premium-discount too short or not archived"
    zx = trailing_z(prem, T328_WIN, incl=False)
    trx = fade_trades(days, zx, j["close"], j["spot"], "live")
    var["z_excluding_today_live"] = {"n": len(trx), "mean_net": _mean([q["gross"] - T328_COST for q in trx])}
    mid, _ = spot_at_close(days, _hourly_mid(archive, CB_BTC_H))   # CF BRR NY is an hour-window median: an OHLC/4 proxy
    okm = np.isfinite(mid)
    if okm.sum() > T328_WIN + 5:
        pmid = j["close"] / (bps_ref * fee_factor(days, ref_day) * np.where(okm, mid, np.nan)) - 1.0
        trm = fade_trades(days, trailing_z(pmid, T328_WIN), j["close"], j["spot"], "live")
        var["brr_hour_average_signal_live"] = {"n": len(trm), "mean_gross": _mean([q["gross"] for q in trm]),
                                               "mean_net": _mean([q["gross"] - T328_COST for q in trm])}
        if off:
            bo = [d for d in days if d in off]
            pmm = dict(zip(days, pmid))
            a2 = np.array([pmm[d] for d in bo]); b2 = np.array([off[d] for d in bo])
            okb = np.isfinite(a2)
            if okb.sum() > 20 and calib:
                calib["corr_hour_average_proxy"] = float(np.corrcoef(a2[okb], b2[okb])[0, 1])
    if _has(archive, FBTC_B):
        fb = _bars(archive, FBTC_B)
        fspot, _ = spot_at_close(fb["days"], hb)
        okf = np.isfinite(fspot)
        fdays = [d for d, k in zip(fb["days"], okf) if k]
        fcl, fsp = fb["close"][okf], fspot[okf]
        fprem = fcl / (fee_factor(fdays, fdays[-1]) * fsp)          # constant scale: z is invariant to it
        fz = trailing_z(fprem, T328_WIN)
        trf = fade_trades(fdays, fz, fcl, fsp, "live")
        var["fbtc_vs_spot_live"] = {"n": len(trf), "mean_gross": _mean([q["gross"] for q in trf]),
                                    "mean_net": _mean([q["gross"] - T328_COST for q in trf])}
        fam["fbtc_live"] = np.array([q["gross"] - T328_COST for q in trf], float)
        common = sorted(set(ib["days"]) & set(fb["days"]))
        im, fm = dict(zip(ib["days"], ib["close"])), dict(zip(fb["days"], fb["close"]))
        ia = np.array([im[d] for d in common])
        fa = np.array([fm[d] for d in common])
        tz = trailing_z(np.log(ia / fa), T328_WIN)
        trt = fade_trades(common, tz, ia, fa, "live")
        var["ibit_fbtc_twin_live"] = {"n": len(trt), "mean_gross": _mean([q["gross"] for q in trt]),
                                      "mean_net_10bp": _mean([q["gross"] - T328_TWIN_COST for q in trt])}
        fam["twin_live"] = np.array([q["gross"] - T328_TWIN_COST for q in trt], float)
    else:
        var["fbtc_vs_spot_live"] = var["ibit_fbtc_twin_live"] = "not computable: daily-history-FBTC not archived"
    var["ibit_vs_cme_mbt"] = "not computable: intraday CME MBT is not archived (BTC=F daily only)"
    var["gbtc_legacy"] = "blocked (catalyst-driven; not in the archive)"
    fs = [float(sharpe_ratio(x)) for x in fam.values() if x.size > 2 and x.std() > 0]
    x0 = fam["primary_live"]
    dsr = family_dsr(x0, fs, T328_N_TRIALS) if x0.size > 3 else {"dsr": None}
    pl, pg = j["per"]["live"], j["per"]["lagged"]
    tl, tg = j["tests"]["live"], j["tests"]["lagged"]
    park_txt = ("PARK CONDITION HOLDS: the pass fails and the break-even cost (mean gross per trade: live "
                f"{_p3(pl['break_even_cost'])}, lagged {_p3(pg['break_even_cost'])}) is inside the {T328_COST * 100:.2f}% cost "
                "band, so the claim parks as 'premium within AP cost band'" if j["park_condition"] else
                "park condition does not hold" + (" (the pass is met)" if j["passed"] else
                                                  " (a break-even cost is not below the cost band)"))
    reason = (f"IBIT sessions {days[0]}..{days[-1]} ({len(days)}), Coinbase BTC-USD hourly close at the session close "
              f"({len(ec)} early-close sessions in the window use the 13:00 ET candle; {stale} sessions with a missing "
              f"candle use the latest earlier one), bitcoin per share {bps_ref:.6f} (iShares basket / 40,000 as of {ref_day}) "
              f"decayed at {T328_FEE * 100:.2f}%/yr; premium in the window mean {_p3(_mean(prem[[i for i, d in enumerate(days) if T328_START <= d <= T328_END]]))}, "
              f"AR(1) {_f(j['ar1'])} (half-life {_f(j['half_life'], 2)} sessions); {j['signal_days']} of "
              f"{j['window_sessions']} window sessions with |z| > 2 (trailing {T328_WIN}). Live: {pl['n']} trades, gross "
              f"{_p3(pl['mean_gross'])}, net {_p3(tl.get('est'))} (one-sided 95% lower bound {_p3((tl.get('ci90') or [None])[0])}); "
              f"lagged: {pg['n']} trades, gross {_p3(pg['mean_gross'])}, net {_p3(tg.get('est'))} (lower bound "
              f"{_p3((tg.get('ci90') or [None])[0])}); at {T328_COST_HI * 100:.2f}%: live {_p3(pl['mean_net_hi_tier'])}, lagged "
              f"{_p3(pg['mean_net_hi_tier'])}; 2025-2026 live {pl['2025_2026']['n']} trades net {_p3(pl['2025_2026']['mean_net'])}. "
              + (f"Synthetic vs official premium {calib['first']}..{calib['last']}: corr {_f(calib['corr'])} (an hour-average "
                 f"BTC proxy for the CF BRR NY window: {_f(calib.get('corr_hour_average_proxy'))}), mean difference "
                 f"{_bp(calib['mean_diff'])}; official |premium| mean {_bp(calib['mean_abs_official'])}, 95th percentile "
                 f"{_bp(calib['p95_abs_official'])}. " if calib else "Official premium not available for a calibration check. ")
              + "Variants: " + "; ".join(f"{k} " + (f"{v_['n']} trades, net {_p3(v_.get('mean_net', v_.get('mean_net_10bp')))}"
                                                     if isinstance(v_, dict) else v_) for k, v_ in var.items())
              + f"; DSR at {T328_N_TRIALS} declared variants {_f(dsr.get('dsr'))} (reported, not in the pass). "
              + park_txt + " — " + j["why"])
    stat = {"n_trades": j["n"], "sessions": len(days), "first": days[0], "last": days[-1], "window": [T328_START, T328_END],
            "btc_per_share_ref": bps_ref, "ref_day": ref_day, "sponsor_fee": T328_FEE, "stale_candles": stale,
            "early_close_sessions_in_window": ec, "ar1_premium": j["ar1"], "half_life_sessions": j["half_life"],
            "signal_days": j["signal_days"], "window_sessions": j["window_sessions"], "per_timing": j["per"],
            "tests": {tm: {"mean": t.get("est"), "ci": t.get("ci"), "ci90": t.get("ci90"), "ci90_mc_se": t.get("ci90_mc_se"),
                           "clusters": t.get("clusters")} for tm, t in j["tests"].items()},
            "high_tier_025": {tm: {"criterion": r[0], "ok": r[1]} for tm, r in j["hi_tier"].items()},
            "trades": {tm: [{k: q[k] for k in ("signal", "entry", "exit", "sg", "z", "gross", "sessions")} for q in tr]
                       for tm, tr in j["runs"].items()},
            "calibration_vs_official": calib, "variants": var, "dsr_variants": dsr, "criteria": j["criteria"],
            "park_condition": j["park_condition"], "park_rule": "else park as 'premium within AP cost band'",
            "z_invariance": "z is exactly invariant to a constant bitcoin-per-share calibration; trade P&L does not use it",
            "not_modelled": "T+1 equity vs immediate crypto settlement (capital on both venues) and IBIT borrow are not costed",
            "rule10": "signal-driven entries and exits: no grid phase", "rule12": "live and lagged fills both required"}
    return _out(stat, j["n"], j["verdict"], reason)


# ============================================================================== T-330 stablecoin peg reversion ==

USDT_Y, USDC_Y = dh("USDT-USD"), dh("USDC-USD")
KR_EP = "kraken-trades-stablecoin-episodes"
CB_USDT = cbd("USDT-USD")
T330_START, T330_END = "2018-01-01", "2026-12-31"
T330_BELOW, T330_ABOVE, T330_RUN = 0.995, 0.998, 5
T330_REPEG, T330_MAX_DAYS = 0.999, 3
T330_COST, T330_COST_HI = 0.004, 0.012
T330_MIN_N = 10
T330_MAX_AGE_H = 24.0


def peg_signals(closes: dict, below: float = T330_BELOW, at_or_above: float = T330_ABOVE, run: int = T330_RUN) -> list:
    """Signal days: the first close below ``below`` after at least ``run`` consecutive closes >= ``at_or_above``."""
    out, streak = [], 0
    for d in sorted(closes):
        x = closes[d]
        if x < below and streak >= run:
            out.append(d)
        streak = streak + 1 if x >= at_or_above else 0
    return out


def _dplus(day: str, k: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=k)).isoformat()


def venue_closes(trades: Sequence[tuple], start_s: float, end_s: float, max_age_h: float = T330_MAX_AGE_H) -> dict:
    """{day: (price, age in hours)}: the close of UTC day ``day`` = the last trade before (day + 1) 00:00 UTC, for every
    midnight inside (start_s, end_s]; a close older than ``max_age_h`` (or before the window start) is left out."""
    tr = sorted((float(t), float(p)) for t, p in trades)
    ts = [t for t, _ in tr]
    out = {}
    m = (math.floor(start_s / 86400) + 1) * 86400
    while m <= end_s + 1e-6:
        j = bisect.bisect_left(ts, m) - 1
        if j >= 0 and ts[j] >= start_s:
            age = (m - ts[j]) / 3600.0
            if age <= max_age_h:
                out[_dday(m - 86400)] = (tr[j][1], age)
        m += 86400
    return out


def peg_trade(signal_day: str, close_of: Callable[[str], Optional[float]], repeg: float = T330_REPEG,
              max_days: int = T330_MAX_DAYS) -> Optional[dict]:
    """Buy at the close of signal day + 1, sell at the first close at or above ``repeg`` among the next ``max_days``
    closes, else at the last of them. None when a needed close is missing."""
    e = _dplus(signal_day, 1)
    pe = close_of(e)
    if pe is None:
        return None
    for k in range(1, max_days + 1):
        x = _dplus(e, k)
        px = close_of(x)
        if px is None:
            return None
        if px >= repeg or k == max_days:
            return {"signal": signal_day, "entry": e, "exit": x, "p_entry": pe, "p_exit": px, "days": k,
                    "repeg": bool(px >= repeg), "gross": px / pe - 1.0}
    return None


def peg_test(episodes: Sequence[dict], min_n: int = T330_MIN_N, cost: float = T330_COST, n_boot: Optional[int] = None,
             reps: Optional[int] = None) -> dict:
    """T-330 core on per-episode trades (each {coin, gross, repeg, ...}): pooled one-sided 95% lower bound > 0, the
    claim's 'fewer than 10 -> inconclusive (too few events)'."""
    g = np.array([e["gross"] for e in episodes], float)
    x = g - cost
    n = int(x.size)
    labels = [f"{e['coin']}:{e['signal']}" for e in episodes]
    t = boot_mean(x, labels, 0.0, n_boot, reps)
    name, ok, dec = lb_row(t, f"pooled USDT+USDC, {n} episodes at {cost * 100:.2f}% a round trip")
    if n < min_n:
        dec = False                     # the claim's own rule: fewer than 10 episodes is 'inconclusive (too few events)'
        name += " [fewer than 10 episodes: 'inconclusive (too few events)' by the claim's own rule]"
    crit = [(name, ok, dec)]
    v, why = _decide(crit, n, min_n, "episodes")
    k = int(sum(1 for e in episodes if e["repeg"]))
    per = {}
    for coin in sorted({e["coin"] for e in episodes}):
        xs = np.array([e["gross"] - cost for e in episodes if e["coin"] == coin], float)
        tc = boot_mean(xs, [l for l, e in zip(labels, episodes) if e["coin"] == coin], 0.0, n_boot, reps)
        per[coin] = {"n": int(xs.size), "mean_net": _mean(xs), "ci90": tc.get("ci90"),
                     "verdict_alone": "inconclusive (too few events)" if xs.size < min_n else
                     ("passes" if lb_row(tc, "")[1] else "fails")}
    return {"n": n, "test": t, "net": x, "gross": g, "repeg": k, "repeg_ci": wilson(k, n), "per_coin": per,
            "worst": float(x.min()) if n else None, "mean_net_hi": _mean(g - T330_COST_HI),
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why, "rule5_decisive": bool(lb_row(t, "")[2])}


def _kraken_windows(archive) -> dict:
    """{coin:signal_day: {'trades': [(time, price)], 'start', 'end', 'complete'}} of the episode bundle (streamed)."""
    def load():
        out = defaultdict(lambda: {"trades": [], "start": None, "end": None, "complete": False})
        for r in _stream(archive, KR_EP):
            v = r.get("value") or {}
            k = f"{v.get('coin')}:{v.get('signal_day')}"
            kind = r.get("kind")
            if kind == "trade":
                p, t = _num(v.get("price")), _num(v.get("time"))
                if p is not None and t is not None:
                    out[k]["trades"].append((t, p))
            elif kind == "episode-window":
                out[k].update(start=_epoch(v["start"]), end=_epoch(v["end"]), complete=bool(v.get("complete")))
        return dict(out)
    return _cached(archive, ("kraken_ep",), load)


def b6c_cryptovenue_stablecoin_peg_reversion(archive):
    """T-330: USDT/USDC discount episodes on Yahoo closes, re-priced at Kraken/Coinbase closes, 0.40% a round trip."""
    miss = _missing(archive, [USDT_Y, USDC_Y, KR_EP])
    if miss:
        return miss
    yc = {}
    for coin, b in (("USDT", USDT_Y), ("USDC", USDC_Y)):
        bars = _bars(archive, b)
        yc[coin] = dict(zip(bars["days"], bars["close"]))
    kw = _kraken_windows(archive)
    cbu = {}
    if _has(archive, CB_USDT):
        cb = _bars(archive, CB_USDT)
        cbu = dict(zip(cb["days"], cb["close"]))
    sig = {coin: peg_signals(c) for coin, c in yc.items()}
    eps = sorted([(d, coin) for coin, ds in sig.items() for d in ds if T330_START <= d <= T330_END])
    pre = sorted([(d, coin) for coin, ds in sig.items() for d in ds if d < T330_START])
    venue_eps, comp_eps, details = [], [], []
    for d, coin in eps:
        y = yc[coin]
        comp = peg_trade(d, lambda x: y.get(x))
        w = kw.get(f"{coin}:{d}")
        tr, src = None, None
        if w and w["complete"] and w["trades"]:
            vc = venue_closes(w["trades"], w["start"], w["end"])
            tr = peg_trade(d, lambda x: vc[x][0] if x in vc else None)
            if tr:
                src = "kraken"
                tr["age_h"] = [vc[tr["entry"]][1], vc[tr["exit"]][1]]
        if tr is None and coin == "USDT" and cbu:
            tr = peg_trade(d, lambda x: cbu.get(x))
            src = "coinbase" if tr else None
        if tr is None and comp is not None:
            tr, src = dict(comp), "yahoo (no venue close)"
        if tr is None:
            details.append({"coin": coin, "signal": d, "status": "dropped: closes missing"})
            continue
        tr.update(coin=coin, venue=src)
        venue_eps.append(tr)
        if comp is not None:
            comp_eps.append({**comp, "coin": coin})
        details.append({"coin": coin, "signal": d, "venue": src, "entry": tr["entry"], "exit": tr["exit"],
                        "p_entry": tr["p_entry"], "p_exit": tr["p_exit"], "repeg": tr["repeg"], "gross": tr["gross"],
                        "net": tr["gross"] - T330_COST, "yahoo_gross": comp["gross"] if comp else None,
                        "kraken_window": bool(w), "close_age_hours": tr.get("age_h")})
    j = peg_test(venue_eps)
    jc = peg_test(comp_eps)
    frozen = sorted(k for k in kw)
    found = sorted(f"{c}:{d}" for d, c in eps + pre)
    t = j["test"]
    reason = (f"Yahoo closes USDT {min(yc['USDT'])}.., USDC {min(yc['USDC'])}..: {len(eps)} episodes with signal days in "
              f"2018-2026 (" + ", ".join(f"{c} {d}" for d, c in eps) + f"; {len(pre)} before 2018 left out); re-priced at "
              + ", ".join(f"{k} {v_}" for k, v_ in sorted(_count([e['venue'] for e in venue_eps]).items()))
              + f" closes; pooled net {_p3(t.get('est'))} per episode at {T330_COST * 100:.2f}% (one-sided 95% lower bound "
              f"{_p3((t.get('ci90') or [None])[0])}, two-sided 95% {_ci(t.get('ci'), 3, 100, '%')}); repeg within 3 days "
              f"{j['repeg']}/{j['n']} (Wilson 95% {_ci(j['repeg_ci'], 2)}); worst episode {_p3(j['worst'])}; at "
              f"{T330_COST_HI * 100:.1f}% {_p3(j['mean_net_hi'])}; per coin " + "; ".join(
                  f"{c} {v_['n']} episodes net {_p3(v_['mean_net'])} ({v_['verdict_alone']})" for c, v_ in j["per_coin"].items())
              + f"; Yahoo composite reading {jc['n']} episodes net {_p3(jc['test'].get('est'))} (lower bound "
              f"{_p3((jc['test'].get('ci90') or [None])[0])}); UST/USDN tail appendix not archived — " + j["why"])
    stat = {"n_episodes": j["n"], "episodes": details, "pre_window_signals": [f"{c}:{d}" for d, c in pre],
            "kraken_windows": frozen, "detected": found, "test": {k: t.get(k) for k in ("est", "ci", "ci90", "ci90_mc_se")},
            "repeg": j["repeg"], "repeg_wilson95": j["repeg_ci"], "worst_net": j["worst"], "mean_net_cost_1_2pct": j["mean_net_hi"],
            "per_coin": j["per_coin"], "composite": {"n": jc["n"], "mean_net": jc["test"].get("est"), "ci90": jc["test"].get("ci90")},
            "criteria": j["criteria"], "rule5_decisive_failure": j["rule5_decisive"],
            "tail_appendix": "UST-USD / USDN-USD not archived (outside the pass rule)",
            "rule10": "signal-driven episodes: no grid phase"}
    return _out(stat, j["n"], j["verdict"], reason)


def _count(xs) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


# ============================================================================== T-365 stETH discount carry ==

STETH_Y, ETH_Y = dh("STETH-USD"), dh("ETH-USD")
T365_START, T365_END = "2023-04-12", "2026-09-30"
T365_PRE = ("2020-12-23", "2023-04-11")
T365_THR = 0.015
T365_THRS = (0.01, 0.015, 0.03)
T365_CONFIRM, T365_HOLD = 2, 10
T365_COST = 0.003
T365_MIN_N = 15
T365_N_TRIALS = 4
T365_N_SHUFFLE = 2000
T365_TIMINGS = ("live", "lagged")


def lst_episodes(days: Sequence[str], ratio: np.ndarray, thr: float = T365_THR, confirm: int = T365_CONFIRM,
                 hold: int = T365_HOLD, start: str = T365_START, end: str = T365_END, timing: str = "live",
                 cost: float = T365_COST) -> list:
    """Non-overlapping episodes on a daily (calendar-day) ratio series: at close t, discount 1 - ratio above ``thr`` on
    ``confirm`` consecutive calendar days (trailing only) -> buy at close t ('live') or t + 1 ('lagged'), sell ``hold``
    calendar days after the entry; net = ln(ratio_x / ratio_e) - cost. The next signal is looked for after the exit."""
    ords = np.array([_ord(d) for d in days], np.int64)
    pos = {int(o): i for i, o in enumerate(ords)}
    disc = 1.0 - np.asarray(ratio, float)
    lag = 0 if timing == "live" else 1
    out, t, n = [], 0, len(days)
    while t < n:
        if not (start <= days[t] <= end) or t < confirm - 1:
            t += 1
            continue
        okc = all(pos.get(int(ords[t]) - k) == t - k and disc[t - k] > thr for k in range(confirm))
        if not okc:
            t += 1
            continue
        e = pos.get(int(ords[t]) + lag)
        x = pos.get(int(ords[t]) + lag + hold) if e is not None else None
        if e is None or x is None:
            t += 1
            continue
        out.append({"signal": days[t], "entry": days[e], "exit": days[x], "disc": float(disc[t]),
                    "net": float(math.log(ratio[x] / ratio[e]) - cost)})
        t = x + 1 - lag
    return out


def shuffle_null(days: Sequence[str], ratio: np.ndarray, obs: Optional[float], n_shuffle: int = T365_N_SHUFFLE,
                 seed: int = SEED, **kw) -> dict:
    """The trial's shuffled-increment null: the daily log increments of the ratio inside the window permuted, the path
    rebuilt from the window's first value, the rule re-run; p = (1 + #{null mean >= observed}) / (1 + shuffles with an
    episode)."""
    start, end = kw.get("start", T365_START), kw.get("end", T365_END)
    idx = [i for i, d in enumerate(days) if start <= d <= end]
    if obs is None or len(idx) < 30:
        return {"p": None, "n_valid": 0}
    i0, i1 = idx[0], idx[-1]
    lr = np.log(np.asarray(ratio, float)[i0: i1 + 1])
    inc = np.diff(lr)
    rng = np.random.default_rng(seed)
    sub = list(days[i0: i1 + 1])
    means = []
    for _ in range(n_shuffle):
        path = np.exp(lr[0] + np.concatenate([[0.0], np.cumsum(rng.permutation(inc))]))
        ep = lst_episodes(sub, path, **kw)
        if ep:
            means.append(float(np.mean([e["net"] for e in ep])))
    if not means:
        return {"p": None, "n_valid": 0}
    m = np.array(means)
    return {"p": float((1 + np.sum(m >= obs)) / (1 + m.size)), "n_valid": int(m.size), "null_mean": float(m.mean())}


def lst_test(days: Sequence[str], ratio: np.ndarray, min_n: int = T365_MIN_N, n_boot: Optional[int] = None,
             reps: Optional[int] = None, n_shuffle: int = T365_N_SHUFFLE) -> dict:
    """T-365 core: episodes under both fill readings, the episode bootstrap and the shuffled-increment null (both named),
    the count (fewer than 15 = insufficient events) and the DSR over the 4 declared trials."""
    runs, rows, tests, nulls = {}, [], {}, {}
    for tm in T365_TIMINGS:
        ep = lst_episodes(days, ratio, timing=tm)
        runs[tm] = ep
        x = np.array([e["net"] for e in ep], float)
        t = boot_mean(x, [e["signal"] for e in ep], 0.0, n_boot, reps)
        tests[tm] = t
        r1 = lb_row(t, f"[{tm}] episode bootstrap, {len(ep)} episodes")
        sh = shuffle_null(days, ratio, _mean(x), n_shuffle, timing=tm) if ep else {"p": None}
        nulls[tm] = sh
        r2 = (f"[{tm}] shuffled-increment null p {_f(sh.get('p'))} < 0.05", None if sh.get("p") is None else sh["p"] < ALPHA, False)
        rows.append(all_constructions([r1, r2], f"[{tm}] both named nulls"))
    n = min(len(runs[tm]) for tm in T365_TIMINGS)
    if max(len(runs[tm]) for tm in T365_TIMINGS) == 0:
        c1 = ("lower end of the two-sided 90% CI of the mean net 10-day log return > 0: no episode under either fill reading "
              "(the discount never exceeded the threshold on two consecutive days), so there is no return to test", None, False)
    else:
        c1 = all_constructions(rows, "lower end of the two-sided 90% CI of the mean net 10-day log return > 0 under both fill "
                                     "readings (rule 12)")
    if n < min_n:
        c1 = (c1[0] + " [fewer than 15 episodes: 'insufficient events' by the claim's own rule]", c1[1], False)
    fam = {}
    for thr in T365_THRS:
        fam[f"thr_{thr:g}"] = np.array([e["net"] for e in lst_episodes(days, ratio, thr=thr)], float)
    fam["pre_shapella_1.5%"] = np.array([e["net"] for e in lst_episodes(days, ratio, start=T365_PRE[0], end=T365_PRE[1])], float)
    x0 = np.array([e["net"] for e in runs["live"]], float)
    fs = [float(sharpe_ratio(v)) for v in fam.values() if v.size > 2 and v.std() > 0]
    dsr = family_dsr(x0, fs, T365_N_TRIALS) if x0.size > 3 else {"dsr": None}
    c3 = dsr_row(dsr, f"DSR >= {DSR_PASS} over {T365_N_TRIALS} trials")
    if n < min_n:
        c3 = (c3[0], c3[1], False)
    crit = [c1, c3]
    v, why = _decide(crit, n, min_n, "non-overlapping post-Shapella episodes")
    return {"n": n, "runs": runs, "tests": tests, "nulls": nulls, "family": {k: {"n": int(v_.size), "mean": _mean(v_)}
                                                                                 for k, v_ in fam.items()},
            "dsr": dsr, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_cryptovenue_steth_discount_carry(archive):
    """T-365: buy stETH after two days of > 1.5% discount to ETH, hold 10 days, 30 bp."""
    miss = _missing(archive, [STETH_Y, ETH_Y])
    if miss:
        return miss
    st, et = _bars(archive, STETH_Y), _bars(archive, ETH_Y)
    sm, em = dict(zip(st["days"], st["close"])), dict(zip(et["days"], et["close"]))
    days = sorted(set(sm) & set(em))
    ratio = np.array([sm[d] / em[d] for d in days], float)
    j = lst_test(days, ratio)
    disc = 1 - ratio
    w = [i for i, d in enumerate(days) if T365_START <= d <= T365_END]
    pw = [i for i, d in enumerate(days) if T365_PRE[0] <= d <= T365_PRE[1]]
    q25 = [i for i, d in enumerate(days) if "2025-07-01" <= d <= "2025-09-30"]
    mx = (float(disc[w].max()), days[w[int(np.argmax(disc[w]))]]) if w else (None, None)
    pre = j["family"]["pre_shapella_1.5%"]
    pre_ep = lst_episodes(days, ratio, start=T365_PRE[0], end=T365_PRE[1])
    pre_t = boot_mean(np.array([e["net"] for e in pre_ep], float), [e["signal"] for e in pre_ep]) if len(pre_ep) >= 4 else {}
    reason = (f"Yahoo STETH-USD / ETH-USD closes {days[0]}..{days[-1]}; post-Shapella window {T365_START}..{T365_END}: "
              f"{len(w)} days, maximum discount {_p3(mx[0])} on {mx[1]}, {int(np.sum(disc[w] > T365_THR))} days above "
              f"{T365_THR * 100:.1f}%, {int(np.sum(disc[w] > 0.01))} above 1%; episodes live {len(j['runs']['live'])}, lagged "
              f"{len(j['runs']['lagged'])} (thresholds 1% / 1.5% / 3%: " + ", ".join(
                  f"{k} {v_['n']}" for k, v_ in j["family"].items() if k.startswith("thr")) + "); 2025-07..09 exit-queue "
              f"window maximum discount {_p3(float(disc[q25].max()) if q25 else None)}. Pre-Shapella regime (reported, not "
              f"pooled): {len(pw)} days, {int(np.sum(disc[pw] > T365_THR))} above 1.5%, {pre['n']} non-overlapping episodes, mean "
              f"net {_p3(pre['mean'])} (one-sided 95% lower bound {_p3((pre_t.get('ci90') or [None])[0])}). cbETH variant "
              f"blocked (no cbETH exchange-rate history) — " + j["why"])
    stat = {"n_episodes": j["n"], "window": [T365_START, T365_END], "window_days": len(w), "max_discount": mx[0],
            "max_discount_day": mx[1], "days_above_threshold": int(np.sum(disc[w] > T365_THR)),
            "episodes": {tm: ep for tm, ep in j["runs"].items()},
            "tests": {tm: {"mean": t.get("est"), "ci90": t.get("ci90")} for tm, t in j["tests"].items()},
            "shuffle_null": j["nulls"], "family": j["family"], "dsr": j["dsr"],
            "pre_shapella": {"days": len(pw), "days_above": int(np.sum(disc[pw] > T365_THR)), "episodes": pre_ep,
                             "ci90": pre_t.get("ci90")},
            "exit_queue_2025_max_discount": float(disc[q25].max()) if q25 else None, "criteria": j["criteria"],
            "cbeth_variant": "blocked: needs the cbETH exchange-rate history (on-chain)", "rule10": "signal-driven episodes"}
    return _out(stat, j["n"], j["verdict"], reason)


# =============================================================================== T-366 cbETH staking drift ==

CB_CBETH_ETH = cbd("CBETH-ETH")
CBETH_Y = dh("CBETH-USD")
T366_START, T366_END = "2023-04-12", "2026-09-30"
T366_LO, T366_HI = 0.015, 0.035
T366_LAG = 30
T366_MIN_N = 900
T366_ROLL = 252
T366_COST_RT = (0.003, 0.005)


def ratio_drift(days: Sequence[str], ratio: np.ndarray, lag: int = T366_LAG) -> dict:
    """OLS of ln(ratio) on calendar time in years (365 days) with Newey-West (Bartlett) s.e., lag ``lag``: slope (a log
    rate per year), s.e., two-sided 95% HAC interval, compounded rate exp(slope) - 1."""
    y = np.log(np.asarray(ratio, float))
    if len(days) < 10:
        return {"slope": None, "se": None, "ci": [None, None], "n": len(days)}
    o0 = _ord(days[0])
    t = np.array([(_ord(d) - o0) / 365.0 for d in days], float)
    o = ols_nw(y, t[:, None], lag)
    b, se = o["coef"][1], o["se"][1]
    z = _N.inv_cdf(0.975)
    return {"slope": b, "se": se, "ci": [b - z * se, b + z * se], "t": b / se if se > 0 else None, "n": len(days),
            "compounded": math.exp(b) - 1.0, "ci_compounded": [math.exp(b - z * se) - 1.0, math.exp(b + z * se) - 1.0],
            "years": float(t[-1]), "lag": lag}


def rolling_share(days: Sequence[str], ratio: np.ndarray, win: int = T366_ROLL) -> dict:
    y = np.log(np.asarray(ratio, float))
    t = np.array([_ord(d) for d in days], float) / 365.0
    sl = []
    for i in range(0, len(days) - win + 1):
        sl.append(float(np.polyfit(t[i:i + win], y[i:i + win], 1)[0]))
    sl = np.array(sl)
    return {"windows": int(sl.size), "share_positive": float(np.mean(sl > 0)) if sl.size else None,
            "min": float(sl.min()) if sl.size else None, "max": float(sl.max()) if sl.size else None}


def drift_test(days: Sequence[str], ratio: np.ndarray, min_n: int = T366_MIN_N, lo: float = T366_LO, hi: float = T366_HI) -> dict:
    """T-366 core: slope in [lo, hi] under both annualisation readings (log rate, compounded) and the HAC 95% CI above 0."""
    d = ratio_drift(days, ratio)
    n = d["n"]
    if d["slope"] is None:
        crit = [("annualised slope in band", None, False), ("HAC 95% CI excludes 0", None, False)]
    else:
        rows = [(f"log rate {_p3(d['slope'])}/yr in [{lo * 100:.1f}%, {hi * 100:.1f}%]", lo <= d["slope"] <= hi, False),
                (f"compounded {_p3(d['compounded'])}/yr in [{lo * 100:.1f}%, {hi * 100:.1f}%]", lo <= d["compounded"] <= hi, False)]
        c1 = all_constructions(rows, "annualised slope of ln(CBETH-ETH) on time in the claimed band (both readings)")
        dec_band = (d["ci"][1] < lo) or (d["ci"][0] > hi)      # rule 5: the whole HAC 95% interval outside the band
        c1 = (c1[0], c1[1], dec_band)
        inside = lo <= d["ci"][0] and d["ci"][1] <= hi
        c2 = (f"HAC (lag {d['lag']}) 95% {_ci(d['ci'], 3, 100, '%')} excludes 0 (lower end > 0)"
              + ("; the whole interval lies inside the band" if inside else ""), d["ci"][0] > 0,
              d["ci"][1] < 0)
        crit = [c1, c2]
    v, why = _decide(crit, n, min_n, "days")
    return {"drift": d, "n": n, "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def b6c_cryptovenue_cbeth_staking_drift(archive):
    """T-366: Coinbase CBETH-ETH log-ratio slope in [1.5%, 3.5%]/yr with a HAC 95% CI above 0."""
    miss = _missing(archive, [CB_CBETH_ETH])
    if miss:
        return miss
    cb = _bars(archive, CB_CBETH_ETH)
    idx = [i for i, d in enumerate(cb["days"]) if T366_START <= d <= T366_END]
    days = [cb["days"][i] for i in idx]
    ratio = cb["close"][idx]
    vol = cb["volume"][idx]
    j = drift_test(days, ratio)
    d = j["drift"]
    roll = rolling_share(days, ratio)
    lags = {L: ratio_drift(days, ratio, L) for L in (nw_lag(len(days)), 90)}
    rob = None
    if _has(archive, CBETH_Y) and _has(archive, ETH_Y):
        c1, e1 = _bars(archive, CBETH_Y), _bars(archive, ETH_Y)
        cm, em = dict(zip(c1["days"], c1["close"])), dict(zip(e1["days"], e1["close"]))
        rd = [x for x in sorted(set(cm) & set(em)) if T366_START <= x <= T366_END]
        if len(rd) > 30:
            rr = ratio_drift(rd, np.array([cm[x] / em[x] for x in rd]))
            rob = {"days": len(rd), "slope": rr["slope"], "ci": rr["ci"]}
    yrs = d.get("years") or 0.0
    net = {f"{c * 1e4:.0f}bp": (d["slope"] - c / yrs) if (d["slope"] is not None and yrs > 0) else None for c in T366_COST_RT}
    thin = float(np.mean(vol < 5.0)) if vol.size else None
    missing_days = (_ord(days[-1]) - _ord(days[0]) + 1 - len(days)) if days else None
    reason = (f"Coinbase CBETH-ETH daily closes {days[0]}..{days[-1]} ({len(days)} days, {missing_days} calendar days "
              f"without a trade; {_pu(thin)} of days under 5 cbETH traded): OLS slope of ln(ratio) on time "
              f"{_p3(d['slope'])}/yr (compounded {_p3(d['compounded'])}), HAC lag {T366_LAG} s.e. {_p3(d['se'])}, 95% "
              f"{_ci(d['ci'], 3, 100, '%')}; other HAC lags " + ", ".join(f"{L}: {_ci(v_['ci'], 3, 100, '%')}" for L, v_ in lags.items())
              + f"; rolling {T366_ROLL}-day windows with a positive slope {_pu(roll['share_positive'])} of {roll['windows']} "
              f"(range {_p3(roll['min'])} to {_p3(roll['max'])}); Yahoo CBETH-USD/ETH-USD robustness "
              + (f"{_p3(rob['slope'])}/yr ({_ci(rob['ci'], 3, 100, '%')}, {rob['days']} days)" if rob else "not available")
              + "; net of one round trip amortised over the window " + ", ".join(f"{k} {_p3(v_)}" for k, v_ in net.items())
              + " (not in the pass); the published net APY path is not archived (comparison only) — " + j["why"])
    stat = {"n_days": len(days), "first": days[0], "last": days[-1], "drift": d, "hac_lag_sensitivity":
            {str(L): {"ci": v_["ci"], "se": v_["se"]} for L, v_ in lags.items()}, "rolling_252": roll, "yahoo_robustness": rob,
            "net_of_round_trip": net, "share_days_under_5_cbeth": thin, "days_without_trade": missing_days,
            "band": [T366_LO, T366_HI], "criteria": j["criteria"], "rule10": "full-sample slope: no grid"}
    return _out(stat, j["n"], j["verdict"], reason)



# ============================================================================ T-419 high-volume return premium ==

T419_ETFS = ("SPY", "QQQ", "IWM", "EFA", "AGG", "TLT", "GLD", "SLV", "USO", "SPHB", "SPLV", "USMV", "XLB", "XLE", "XLF", "XLI",
             "XLK", "XLP", "XLU", "XLV", "XLY")
T419_EXTRA = ("GDX",)                   # declared before any return was seen: the library's asset list names GLD, SLV, GDX
T419_CRYPTO = ("BTC-USD", "ETH-USD")
T419_MKT = "SPY"
T419_START, T419_END = "2005-01-01", "2026-12-31"
T419_PANEL_FIRST = "2002-01-01"
T419_VWIN, T419_BWIN, T419_SIG = 50, 250, 2.0
T419_MIN_VWIN, T419_MIN_BWIN = 30, 200
T419_PCTS = (0.90, 0.95, 0.99)
T419_HS = (5, 10, 20)
T419_VOLS = ("idio", "raw")
T419_BUCKETS = ("etf", "crypto")
T419_PRIMARY = (0.90, 10, "idio")
T419_THR = 0.005
T419_P = 0.01
T419_SR = 0.5
T419_COST = 0.0005
T419_COST_CRYPTO = 0.005
T419_CAP = 0.05
T419_MIN_N = 800
T419_N_TRIALS = 36
T419_N_SHIFT = 2000


def _roll(x: np.ndarray, w: int, incl: bool = False) -> np.ndarray:
    """Rolling sum over x[j-w..j-1] (``incl`` False) or x[j-w+1..j]; NaN where the window is short."""
    x = np.asarray(x, float)
    n = x.size
    c = np.concatenate([[0.0], np.cumsum(x)])
    out = np.full(n, np.nan)
    if incl:
        if n >= w:
            out[w - 1:] = c[w:] - c[:n - w + 1]
    elif n > w:
        out[w:] = c[w:n] - c[:n - w]
    return out


def _trail_q(x: np.ndarray, w: int, q: float, min_obs: int) -> np.ndarray:
    """q-quantile of the finite values among x[j-w..j-1]; NaN with fewer than ``min_obs``."""
    n = x.size
    pad = np.concatenate([np.full(w, np.nan), np.asarray(x, float)])
    W = np.sort(np.lib.stride_tricks.sliding_window_view(pad, w)[:n], axis=1)      # NaN sort last
    cnt = np.isfinite(W).sum(axis=1)
    out = np.full(n, np.nan)
    ok = np.flatnonzero(cnt >= min_obs)
    if ok.size:                                   # numpy's default (linear) quantile on the finite values of each row
        h = (cnt[ok] - 1) * q
        lo = np.floor(h).astype(int)
        hi = np.minimum(lo + 1, cnt[ok] - 1)
        a, b = W[ok, lo], W[ok, hi]
        out[ok] = a + (h - lo) * (b - a)
    return out


def _roll_slope(y: np.ndarray, x: np.ndarray, w: int, min_obs: int, incl: bool) -> np.ndarray:
    """Rolling OLS slope of y on x (with intercept) over pairs where both are finite."""
    m = np.isfinite(y) & np.isfinite(x)
    yy, xx, mm = np.where(m, y, 0.0), np.where(m, x, 0.0), m.astype(float)
    N = _roll(mm, w, incl)
    Sx, Sy = _roll(xx, w, incl), _roll(yy, w, incl)
    Sxy, Sxx = _roll(xx * yy, w, incl), _roll(xx * xx, w, incl)
    with np.errstate(all="ignore"):
        b = (Sxy - Sx * Sy / N) / (Sxx - Sx * Sx / N)
    b[~(N >= min_obs)] = np.nan
    return b


def hvp_asset(bars: dict, kind: str, mkt: dict, bills: Optional[Bills]) -> dict:
    """Per-asset arrays on the asset's own calendar: volume surprise x, market surprise xm (SPY on the same date), the
    idiosyncratic surprise u, the close-to-close return r and its trailing sd, the trailing return beta, forward window
    returns per horizon and the open-to-open interval returns used by the calendar-time portfolio. ``mkt`` = {'x': {date:
    x_SPY}, 'open': {date: adj open}, 'sess': sorted session dates, 'close_arr': adj closes in session order}."""
    days = bars["days"]
    n = len(days)
    O, C, V = bars["aopen"], bars["adj"], bars["volume"]
    with np.errstate(all="ignore"):
        lv = np.where(V > 0, np.log(V), np.nan)
    Vp = np.where(np.isfinite(lv), V, 0.0)
    cnt = _roll(np.isfinite(lv).astype(float), T419_VWIN)
    mv = _roll(Vp, T419_VWIN) / cnt
    with np.errstate(all="ignore"):
        x = lv - np.log(mv)
    x[~(cnt >= T419_MIN_VWIN)] = np.nan
    xm = np.array([mkt["x"].get(d, np.nan) for d in days], float)
    bv = _roll_slope(x, xm, T419_VWIN, T419_MIN_VWIN, incl=False)
    u = x - bv * xm
    r = np.full(n, np.nan)
    r[1:] = C[1:] / C[:-1] - 1.0
    rm_ = np.where(np.isfinite(r), r, 0.0)
    rc = _roll(np.isfinite(r).astype(float), T419_VWIN)
    mu = _roll(rm_, T419_VWIN) / rc
    s2 = (_roll(rm_ * rm_, T419_VWIN) - rc * mu * mu) / (rc - 1)
    sig = np.sqrt(np.maximum(s2, 0.0))
    sig[~(rc >= T419_MIN_VWIN)] = np.nan
    sess, sc = mkt["sess"], mkt["close_arr"]
    if kind == "etf":
        mo = np.array([mkt["open"].get(d, np.nan) for d in days], float)
        mc = np.array([mkt["close"].get(d, np.nan) for d in days], float)
    else:                                      # SPY as of 00:00 UTC of the date (open) and of the next date (close)
        def asof(d):
            j = bisect.bisect_right(sess, d) - 1
            return sc[j] if j >= 0 else np.nan
        mo = np.array([asof(_dplus(d, -1)) for d in days], float)
        mc = np.array([asof(d) for d in days], float)
    rmk = np.full(n, np.nan)
    rmk[1:] = mc[1:] / mc[:-1] - 1.0
    beta = _roll_slope(r, rmk, T419_BWIN, T419_MIN_BWIN, incl=True)
    ords = np.array([_ord(d) for d in days], np.int64)
    if bills is not None:
        cum = np.array([bills._c(int(o)) for o in ords], float)
    else:
        cum = np.zeros(n)
    fwd = {}
    for H in T419_HS:
        W = np.full(n, np.nan); M = np.full(n, np.nan); RF = np.full(n, np.nan)
        if n > H + 1:
            a, b = np.arange(1, n - H), np.arange(1 + H, n)
            W[: n - H - 1] = O[b] / O[a] - 1.0
            M[: n - H - 1] = mo[b] / mo[a] - 1.0
            RF[: n - H - 1] = np.exp(cum[b] - cum[a]) - 1.0
        fwd[H] = {"W": W, "M": M, "RF": RF, "AR": (W - RF) - beta * (M - RF), "AR_plain": W - beta * M}
    R1 = np.full(n, np.nan); M1 = np.full(n, np.nan); RF1 = np.full(n, np.nan)
    R1[:-1] = O[1:] / O[:-1] - 1.0
    M1[:-1] = mo[1:] / mo[:-1] - 1.0
    RF1[:-1] = np.exp(cum[1:] - cum[:-1]) - 1.0
    bprev = np.concatenate([[np.nan], beta[:-1]])
    AR1 = (R1 - RF1) - bprev * (M1 - RF1)
    return {"days": days, "ords": ords, "kind": kind, "x": x, "xm": xm, "u": u, "r": r, "sig": sig, "beta": beta,
            "fwd": fwd, "AR1": AR1, "n": n}


def hvp_flags(a: dict, pct: float, vol: str) -> np.ndarray:
    """Event flags: the surprise (u for 'idio', x for 'raw') above its trailing-50 ``pct`` quantile and |r| < 2 sigma."""
    s = a["u"] if vol == "idio" else a["x"]
    q = _trail_q(s, T419_VWIN, pct, T419_MIN_VWIN)
    with np.errstate(invalid="ignore"):
        return np.isfinite(s) & np.isfinite(q) & (s > q) & np.isfinite(a["sig"]) & (np.abs(a["r"]) < T419_SIG * a["sig"])


def _in_window(a: dict, start: str, end: str) -> np.ndarray:
    return np.array([start <= d <= end for d in a["days"]], bool)


def cal_portfolio(assets: Sequence[dict], flags: Sequence[np.ndarray], H: int, cost: float = T419_COST, cap: float = T419_CAP,
                  start: str = T419_START, end: str = T419_END, crypto_cost: Optional[float] = None) -> dict:
    """Calendar-time portfolio on the calendar-day grid: each event at own-calendar index j holds the asset over the
    open-to-open intervals j+1..j+H (held on every calendar day of those intervals, the interval's abnormal excess return
    AR1 booked on its first day); every held asset weighs min(1 / held assets, cap); turnover pays cost / 2 per unit."""
    o0, o1 = _ord(start), None
    for a in assets:
        if a["n"]:
            o1 = max(o1 or 0, int(a["ords"][-1]))
    if o1 is None or o1 < o0:
        return {"net": np.zeros(0), "gross": np.zeros(0), "n_days": 0}
    T = o1 - o0 + 1
    held = np.zeros((len(assets), T), bool)
    ret = np.zeros((len(assets), T))
    costs = np.full(len(assets), cost, float)
    for i, (a, f) in enumerate(zip(assets, flags)):
        if crypto_cost is not None and a["kind"] == "crypto":
            costs[i] = crypto_cost
        n = a["n"]
        if n < 2:
            continue
        c = np.concatenate([[0], np.cumsum(f.astype(int))])
        k = np.arange(1, n - 1)
        act = (c[k] - c[np.maximum(k - H, 0)]) > 0          # an event in [k - H, k - 1]
        kk = k[act]
        if not kk.size:
            continue
        s = a["ords"][kk] - o0
        e = a["ords"][kk + 1] - o0
        good = (s >= 0) & (s < T)
        s, e, kk = s[good], np.minimum(e[good], T), kk[good]
        d = np.zeros(T + 1)
        np.add.at(d, s, 1)
        np.add.at(d, e, -1)
        held[i] = np.cumsum(d)[:T] > 0
        v = a["AR1"][kk]
        ret[i, s] = np.where(np.isfinite(v), v, 0.0)
    N = held.sum(axis=0)
    w = np.where(N > 0, np.minimum(1.0 / np.maximum(N, 1), cap), 0.0)
    Wt = held * w[None, :]
    gross = (Wt * ret).sum(axis=0)
    turn = np.abs(np.diff(np.concatenate([np.zeros((len(assets), 1)), Wt], axis=1), axis=1))
    cst = (turn * (costs[:, None] / 2.0)).sum(axis=0)
    net = gross - cst
    days_active = int((N > 0).sum())
    first = int(np.argmax(N > 0)) if days_active else 0
    return {"net": net[first:], "gross": gross[first:], "n_days": int(T - first), "days_active": days_active,
            "mean_held": float(N[first:].mean()) if days_active else 0.0, "turnover": float(turn.sum())}


def placebo_p(assets: Sequence[dict], flags: Sequence[np.ndarray], H: int, obs: float, start: str, end: str,
              n_shift: int = T419_N_SHIFT, seed: int = SEED) -> dict:
    """The trial's block-shift placebo: each asset's event-date pattern shifted circularly by an independent random
    offset (at least H + 1 days from zero both ways), the pooled mean abnormal return recomputed; p = (1 + #{placebo mean
    >= observed}) / (1 + shifts). All offsets per asset at once through FFT circular correlations."""
    rng = np.random.default_rng(seed)
    Ss, Cs, ns = [], [], []
    for a, f in zip(assets, flags):
        ar = a["fwd"][H]["AR"]
        v = np.isfinite(ar) & _in_window(a, start, end)
        f = f & v
        n = a["n"]
        if n < 3 * H + 4 or not f.any():
            continue
        F = np.fft.rfft(f.astype(float))
        S = np.fft.irfft(np.conj(F) * np.fft.rfft(np.where(v, ar, 0.0)), n)
        C = np.fft.irfft(np.conj(F) * np.fft.rfft(v.astype(float)), n)
        Ss.append(S); Cs.append(np.rint(C)); ns.append(n)
    if not Ss:
        return {"p": None, "n_shift": 0}
    num = np.zeros(n_shift); den = np.zeros(n_shift)
    for S, C, n in zip(Ss, Cs, ns):
        k = rng.integers(H + 1, n - H, n_shift)
        num += S[k]; den += C[k]
    ok = den > 0
    m = num[ok] / den[ok]
    return {"p": float((1 + np.sum(m >= obs)) / (1 + m.size)), "n_shift": int(m.size), "null_mean": float(m.mean()),
            "null_q99": float(np.quantile(m, 0.99))}


def hvp_test(assets: Sequence[dict], start: str = T419_START, end: str = T419_END, min_n: int = T419_MIN_N,
             n_shift: int = T419_N_SHIFT, vix: Optional[dict] = None, mkt_sym: str = T419_MKT, names: Optional[Sequence[str]] = None) -> dict:
    """T-419 core on prepared assets (``hvp_asset``; the market asset carries no events)."""
    names = list(names) if names is not None else [f"a{i}" for i in range(len(assets))]
    ev_assets = [(nm, a) for nm, a in zip(names, assets) if nm != mkt_sym]
    A = [a for _, a in ev_assets]
    pct0, H0, vol0 = T419_PRIMARY
    fl_cache = {}

    def flags(pct, vol):
        k = (pct, vol)
        if k not in fl_cache:
            fl_cache[k] = [hvp_flags(a, pct, vol) & _in_window(a, start, end) for a in A]
        return fl_cache[k]

    def events(fl, H, bucket=None):
        vals, dates, who = [], [], []
        for (nm, a), f in zip(ev_assets, fl):
            if bucket and a["kind"] != bucket:
                continue
            ar = a["fwd"][H]["AR"]
            idx = np.flatnonzero(f & np.isfinite(ar))
            vals.append(ar[idx]); dates += [a["days"][i] for i in idx]; who += [nm] * idx.size
        return (np.concatenate(vals) if vals else np.zeros(0)), dates, who

    f0 = flags(pct0, vol0)
    f0v = [f & np.isfinite(a["fwd"][H0]["AR"]) for a, f in zip(A, f0)]
    ar0, dts0, who0 = events(f0, H0)
    n = int(ar0.size)
    m0 = _mean(ar0)
    by_b = {b: events(f0, H0, b)[0] for b in T419_BUCKETS}
    mb = {b: _mean(v) for b, v in by_b.items()}
    plc = placebo_p(A, f0v, H0, m0, start, end, n_shift) if n else {"p": None}
    port = cal_portfolio(A, f0v, H0, start=start, end=end)
    sr = _sr_ann(port["net"], 365)
    hac = hac_mean(port["net"]) if port["net"].size > 30 else {"t": None}
    cells, cell_series = {}, []
    for b in T419_BUCKETS:
        Ab = [a for a in A if a["kind"] == b]
        for pct in T419_PCTS:
            for vol in T419_VOLS:
                fl = [f for a, f in zip(A, flags(pct, vol)) if a["kind"] == b]
                for H in T419_HS:
                    flv = [f & np.isfinite(a["fwd"][H]["AR"]) for a, f in zip(Ab, fl)]
                    pc = cal_portfolio(Ab, flv, H, start=start, end=end)
                    ev = np.concatenate([a["fwd"][H]["AR"][f] for a, f in zip(Ab, flv)]) if Ab else np.zeros(0)
                    key = f"{b}|p{int(pct * 100)}|h{H}|{vol}"
                    cells[key] = {"events": int(ev.size), "mean_ar": _mean(ev), "sharpe_net": _sr_ann(pc["net"], 365)}
                    cell_series.append(pc["net"])
    fs = [float(sharpe_ratio(s)) for s in cell_series if s.size > 2 and s.std() > 0]
    dsr = family_dsr(port["net"], fs, T419_N_TRIALS) if port["net"].size > 3 else {"dsr": None}
    L = min((s.size for s in cell_series if s.size), default=0)
    pbo = None
    if L > 400 and len(cell_series) == T419_N_TRIALS:
        M = np.column_stack([s[-L:] for s in cell_series])
        if np.all(M.std(axis=0) > 0):
            pbo = pbo_cscv(M, 8)
    c_mean = (f"mean 10-day abnormal return {_bp(m0)} >= {_bp(T419_THR, 0)} over {n} events", None if m0 is None else m0 >= T419_THR,
              False)
    c_p = (f"block-shift placebo ({plc.get('n_shift')} shifts) p {_f(plc.get('p'), 4)} < {T419_P}",
           None if plc.get("p") is None else plc["p"] < T419_P, False)
    c_sr = (f"calendar-time net Sharpe {_s(sr, 3)} > {T419_SR} after {T419_COST * 1e4:.0f} bps a round trip "
            f"({port['n_days']} calendar days, HAC t of the mean {_f(hac.get('t'), 2)})", None if sr is None else sr > T419_SR, False)
    sg = None if (mb["etf"] is None or mb["crypto"] is None) else bool(np.sign(mb["etf"]) == np.sign(mb["crypto"]) and mb["etf"] != 0)
    c_sg = (f"same sign in the ETF ({_bp(mb['etf'])}, {by_b['etf'].size} events) and crypto ({_bp(mb['crypto'])}, "
            f"{by_b['crypto'].size} events) buckets", sg, False)
    c_d = dsr_row(dsr, f"DSR >= {DSR_PASS} over {T419_N_TRIALS} declared cells")
    crit = [c_mean, c_p, c_sr, c_sg, c_d]
    v, why = _decide(crit, n, min_n, "events")
    halves = None
    if n >= 4:
        # walk forward by DATE halves (the trial's wording): split at the midpoint date of the event span, so no date
        # falls in both halves
        d_arr = np.array(dts0)
        lo_d, hi_d = min(dts0), max(dts0)
        mid = date.fromordinal((_ord(lo_d) + _ord(hi_d)) // 2).isoformat()
        halves = {"basis": "date halves: events dated < split vs >= split (midpoint of the event span)", "split": mid}
        for key, msk in (("first", d_arr < mid), ("second", d_arr >= mid)):
            dd = d_arr[msk].tolist()
            halves[key] = {"from": min(dd) if dd else None, "to": max(dd) if dd else None,
                           "n": int(msk.sum()), "mean": _mean(ar0[msk])}
    vix_rep = None
    if vix:
        hi_ = np.array([vix.get(d, np.nan) > 30 for d in dts0], bool)
        vix_rep = {"events_vix_gt_30": int(hi_.sum()), "mean_ar_vix_gt_30": _mean(ar0[hi_]), "mean_ar_vix_le_30": _mean(ar0[~hi_])}
    pcc = cal_portfolio(A, f0v, H0, start=start, end=end, crypto_cost=T419_COST_CRYPTO)
    plain = np.concatenate([a["fwd"][H0]["AR_plain"][f] for a, f in zip(A, f0v)]) if A else np.zeros(0)
    per_asset = defaultdict(lambda: [0, 0.0])
    for w_, x_ in zip(who0, ar0):
        per_asset[w_][0] += 1
        per_asset[w_][1] += float(x_)
    return {"n": n, "mean_ar": m0, "mean_ar_plain": _mean(plain), "buckets": {b: {"n": int(v_.size), "mean": mb[b]} for b, v_ in by_b.items()},
            "placebo": plc, "sharpe": sr, "hac_t": hac.get("t"), "portfolio": {k: port[k] for k in ("n_days", "days_active", "mean_held", "turnover")},
            "sharpe_crypto_50bp": _sr_ann(pcc["net"], 365), "cells": cells, "dsr": dsr, "pbo": pbo, "halves": halves, "vix": vix_rep,
            "per_asset": {k: {"n": c, "mean": s / c} for k, (c, s) in sorted(per_asset.items())},
            "first_event": min(dts0) if n else None, "last_event": max(dts0) if n else None,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def hvp_market(spy: dict) -> dict:
    """SPY volume surprise x by date plus its adj opens and closes."""
    V = spy["volume"]
    with np.errstate(all="ignore"):
        lv = np.where(V > 0, np.log(V), np.nan)
    cnt = _roll(np.isfinite(lv).astype(float), T419_VWIN)
    mv = _roll(np.where(np.isfinite(lv), V, 0.0), T419_VWIN) / cnt
    with np.errstate(all="ignore"):
        x = lv - np.log(mv)
    x[~(cnt >= T419_MIN_VWIN)] = np.nan
    return {"x": {d: float(v) for d, v in zip(spy["days"], x) if np.isfinite(v)}, "open": dict(zip(spy["days"], spy["aopen"])),
            "close": dict(zip(spy["days"], spy["adj"])), "sess": list(spy["days"]), "close_arr": np.asarray(spy["adj"], float)}


def _clip_bars(b: dict, first: str) -> dict:
    i = bisect.bisect_left(b["days"], first)
    return {k: (v[i:] if k != "days" else v[i:]) for k, v in b.items()}


def b6c_cryptovenue_high_volume_premium(archive):
    """T-419: top-decile idiosyncratic volume without a 2-sigma move -> 10-day beta-adjusted return >= 50 bps."""
    etfs = list(T419_ETFS) + list(T419_EXTRA)
    need = [dh(s) for s in etfs] + [cbd(p) for p in T419_CRYPTO] + [DTB3_B]
    miss = _missing(archive, need)
    if miss:
        return miss
    bills = _bills(archive)
    spy = _clip_bars(_bars(archive, dh(T419_MKT)), T419_PANEL_FIRST)
    mkt = hvp_market(spy)
    names, assets, firsts = [], [], {}
    for s in etfs:
        b = _clip_bars(_bars(archive, dh(s)), T419_PANEL_FIRST)
        names.append(s); assets.append(hvp_asset(b, "etf", mkt, bills)); firsts[s] = b["days"][0] if b["days"] else None
    for p in T419_CRYPTO:
        b = _clip_bars(_bars(archive, cbd(p)), T419_PANEL_FIRST)
        names.append(p); assets.append(hvp_asset(b, "crypto", mkt, bills)); firsts[p] = b["days"][0] if b["days"] else None
    vix = _vix(archive) if _has(archive, VIX_B) else None
    j = hvp_test(assets, vix=vix, names=names)
    no_mkt = {p: int(sum(1 for d in a["days"] if d not in mkt["x"] and d >= T419_START)) for p, a in zip(names, assets) if a["kind"] == "crypto"}
    pl = j["placebo"]
    reason = (f"{len(etfs)} ETFs (21 store ETFs + GDX; SPY is the volume and return market, so it carries no events) and "
              f"BTC-USD/ETH-USD on Coinbase daily candles; events {j['first_event']}..{j['last_event']}: {j['n']} "
              f"(ETF {j['buckets']['etf']['n']}, crypto {j['buckets']['crypto']['n']}; crypto days without an NYSE session have "
              f"no market volume and no idiosyncratic surprise: " + ", ".join(f"{k} {v_}" for k, v_ in no_mkt.items())
              + f"); mean 10-day CAPM abnormal return {_bp(j['mean_ar'])} (plain beta-adjusted {_bp(j['mean_ar_plain'])}); "
              f"ETF {_bp(j['buckets']['etf']['mean'])}, crypto {_bp(j['buckets']['crypto']['mean'])}; placebo p "
              f"{_f(pl.get('p'), 4)} (null mean {_bp(pl.get('null_mean'))}, 99th percentile {_bp(pl.get('null_q99'))}); "
              f"calendar-time net Sharpe {_s(j['sharpe'])} at 5 bps (crypto at 50 bps: {_s(j['sharpe_crypto_50bp'])}), "
              f"mean held assets {_f(j['portfolio']['mean_held'], 2)}; date halves " + (
                  f"(split {j['halves']['split']}) {j['halves']['first']['from']}..{j['halves']['first']['to']} "
                  f"{j['halves']['first']['n']} events {_bp(j['halves']['first']['mean'])} / "
                  f"{j['halves']['second']['from']}..{j['halves']['second']['to']} {j['halves']['second']['n']} events "
                  f"{_bp(j['halves']['second']['mean'])}" if j["halves"] else "n/a")
              + (f"; VIX > 30: {j['vix']['events_vix_gt_30']} events, {_bp(j['vix']['mean_ar_vix_gt_30'])}" if j["vix"] else "")
              + f"; DSR {_f(j['dsr'].get('dsr'))} over {T419_N_TRIALS} cells, PBO {_f((j['pbo'] or {}).get('pbo'))}; dead ETFs: "
              "none (Yahoo drops delisted tickers) — " + j["why"])
    stat = {"n_events": j["n"], "universe": names, "first_bar": firsts, "mean_ar": j["mean_ar"], "mean_ar_plain": j["mean_ar_plain"],
            "buckets": j["buckets"], "placebo": pl, "sharpe_net": j["sharpe"], "hac_t": j["hac_t"], "portfolio": j["portfolio"],
            "sharpe_crypto_50bp": j["sharpe_crypto_50bp"], "cells": j["cells"], "dsr": j["dsr"], "pbo": j["pbo"],
            "halves": j["halves"], "vix": j["vix"], "per_asset": j["per_asset"], "crypto_days_without_session": no_mkt,
            "criteria": j["criteria"], "primary_cell": "pooled|p90|h10|idio", "declared_extra_etfs": list(T419_EXTRA),
            "rule10": "signal-driven events; calendar-time portfolio daily"}
    return _out(stat, j["n"], j["verdict"], reason)


# ================================================================================ T-424 BTC leads altcoins ==

CB_PRODUCTS_PREFIX = "coinbase-products-"
T424_FIT = ("2019-01-01", "2022-12-31")
T424_TEST_START = "2023-01-01"
T424_TOP = 10
T424_RANK_DAYS = 30
T424_THETAS = (1.0, 2.0)
T424_COST, T424_COST_MAKER = 0.005, 0.003
T424_MIN_N = 20000
T424_SR = 0.5
T424_BLOCK = 24
T424_N_TRIALS = 14
T424_HPY = 8760
T424_STABLE = frozenset({"USDT", "USDC", "DAI", "BUSD", "UST", "TUSD", "PAX", "USDP", "GUSD", "PYUSD", "EURC", "GYEN", "MUSD",
                         "USDS", "USD1", "PAXG", "XAUT", "RAI", "LUSD", "FRAX", "SUSD", "USDE", "EUROC", "CUSD", "USDD"})
T424_WRAPPED = frozenset({"BTC", "WBTC", "CBBTC", "TBTC", "LBTC", "CBETH", "LSETH", "WETH", "STETH", "WSTETH", "RETH", "MSOL",
                          "JITOSOL", "BSOL", "CBSOL", "CBXRP", "CBADA", "CBDOGE", "CBLTC", "SWETH", "EZETH", "WEETH", "METH"})


def cb_members(daily: dict, first: str, last: str, exclude: frozenset = T424_STABLE | T424_WRAPPED, top: int = T424_TOP,
               window: int = T424_RANK_DAYS, stable_ids: frozenset = frozenset()) -> dict:
    """{UTC day: [products]} for days in [first, last]: the top ``top`` USD products by dollar volume (close x volume) summed
    over days D-window..D-1, among products that traded on D-1 and are not excluded (base in ``exclude`` or id in
    ``stable_ids``). ``daily``: {product: {day: (close, volume)}}."""
    o0, o1 = _ord(first) - window - 1, _ord(last)
    T = o1 - o0 + 1
    pids = [p for p in sorted(daily) if p.endswith("-USD") and p.split("-")[0] not in exclude and p not in stable_ids and daily[p]]
    M = np.zeros((len(pids), T))
    traded = np.zeros((len(pids), T), bool)
    for i, p in enumerate(pids):
        for d, (c, v) in daily[p].items():
            o = _ord(d) - o0
            if 0 <= o < T and c > 0 and v >= 0:
                M[i, o] = c * v
                traded[i, o] = True
    cs = np.concatenate([np.zeros((len(pids), 1)), np.cumsum(M, axis=1)], axis=1)
    out = {}
    for o in range(_ord(first), o1 + 1):
        k = o - o0                                       # column of day D; window = columns k-window .. k-1
        if k - window < 0:
            continue
        s = cs[:, k] - cs[:, k - window]
        elig = traded[:, k - 1] & (s > 0)
        idx = np.flatnonzero(elig)
        if not idx.size:
            out[date.fromordinal(o).isoformat()] = []
            continue
        order = idx[np.lexsort((np.array([pids[i] for i in idx]), -s[idx]))]
        out[date.fromordinal(o).isoformat()] = [pids[i] for i in order[:top]]
    return out


def hourly_grid_returns(ts: np.ndarray, cl: np.ndarray, t0: int, H: int) -> np.ndarray:
    """Hourly close-to-close returns on the UTC grid t0 + 3600 h (h = 0..H-1): a missing hour had no trade (price
    unchanged, return 0); NaN before the first bar."""
    px = np.full(H, np.nan)
    k = (np.asarray(ts, np.int64) - t0) // 3600
    ok = (k >= 0) & (k < H)
    px[k[ok]] = np.asarray(cl, float)[ok]
    first = int(np.argmax(np.isfinite(px))) if np.isfinite(px).any() else H
    idx = np.where(np.isfinite(px), np.arange(H), 0)
    idx = np.maximum.accumulate(idx)
    ff = px[idx]
    ff[:first] = np.nan
    r = np.full(H, np.nan)
    r[1:] = ff[1:] / ff[:-1] - 1.0
    return r


def follow_rule(r_lead: np.ndarray, r_basket: np.ndarray, rf: np.ndarray, theta: float, cost: float, lag: int = 1) -> dict:
    """Hold the basket over bar h when the leader's return over bar h - lag exceeds ``theta`` (flat otherwise); net excess
    per bar = pos (r - rf) - cost / 2 |pos_h - pos_{h-1}|. Bars where the basket or the signal is undefined are flat."""
    n = r_basket.size
    s = np.full(n, np.nan)
    s[lag:] = r_lead[:-lag]
    pos = (np.isfinite(s) & (s > theta) & np.isfinite(r_basket)).astype(float)
    turn = np.abs(np.diff(np.concatenate([[0.0], pos])))
    ex = np.where(pos > 0, np.nan_to_num(r_basket) - rf, 0.0) - cost / 2.0 * turn
    return {"pos": pos, "net": ex, "signal": s}


def _spells(pos: np.ndarray, r: np.ndarray, cost: float) -> np.ndarray:
    """Net return of each contiguous holding spell: prod(1 + r) - 1 - cost."""
    out, cur = [], None
    for p, x in zip(pos, r):
        if p > 0:
            cur = (1.0 if cur is None else cur) * (1.0 + (0.0 if not np.isfinite(x) else x))
        elif cur is not None:
            out.append(cur - 1.0 - cost)
            cur = None
    if cur is not None:
        out.append(cur - 1.0 - cost)
    return np.array(out, float)


def leadlag_test(r_lead: np.ndarray, r_basket: np.ndarray, rf: np.ndarray, fit: np.ndarray, test: np.ndarray,
                 family_sharpes_hourly: Sequence[float], min_n: int = T424_MIN_N, cost: float = T424_COST,
                 n_boot: Optional[int] = None, reps: Optional[int] = None) -> dict:
    """T-424 core on hourly arrays: theta = 1 sd of the leader's returns on the ``fit`` mask; the follow rule on the
    ``test`` mask; the lagged-coefficient HAC test, net Sharpe, stationary bootstrap and DSR."""
    rl = np.asarray(r_lead, float)
    rb = np.asarray(r_basket, float)
    theta = float(np.nanstd(rl[fit & np.isfinite(rl)], ddof=1))
    fr = follow_rule(rl, rb, rf, theta, cost)
    lagged = np.full(rl.size, np.nan)
    lagged[1:] = rl[:-1]
    oos = test & np.isfinite(rb) & np.isfinite(lagged)
    n = int(oos.sum())
    x = fr["net"][oos]
    sr = _sr_ann(x, T424_HPY)
    reg = ols_nw(rb[oos], lagged[oos][:, None], T424_BLOCK) if n > 50 else {"coef": None, "t": None}
    b = reg["coef"][1] if reg.get("coef") else None
    tb = reg["t"][1] if reg.get("t") else None
    bt = stationary_mc(x, T424_BLOCK, n_boot, reps) if n > 50 else {"p": None}
    fam = [s for s in family_sharpes_hourly if s is not None and math.isfinite(s)]
    dsr = family_dsr(x, fam, T424_N_TRIALS) if n > 3 else {"dsr": None}
    c_b = (f"lagged BTC coefficient {_f(b, 4)} > 0 with HAC (lag {T424_BLOCK}) t {_f(tb, 2)} > 1.645",
           None if tb is None else (b > 0 and tb > _N.inv_cdf(0.95)), False)
    c_sr = (f"net Sharpe {_s(sr)} > {T424_SR} ({T424_HPY} hours a year, excess of bills)", None if sr is None else sr > T424_SR, False)
    pv, pn = resolve(bt.get("p"), bt.get("p_mc_se"), ALPHA, "lt")
    c_p = (f"stationary bootstrap ({T424_BLOCK}-hour mean blocks) p {_f(bt.get('p'), 4)} < {ALPHA} for a net mean <= 0{pn}", pv, False)
    c_d = dsr_row(dsr, f"DSR >= {DSR_PASS} over {T424_N_TRIALS} declared cells")
    crit = [c_b, c_sr, c_p, c_d]
    v, why = _decide(crit, n, min_n, "out-of-sample hourly bars")
    pos = fr["pos"][oos]
    trades = _spells(pos, rb[oos], cost)
    held = pos > 0
    bh = rb[oos] - rf[oos]
    return {"n": n, "theta": theta, "coef": b, "t": tb, "r2": reg.get("r2"), "sharpe": sr, "boot": bt, "dsr": dsr,
            "n_trades": int(trades.size), "mean_net_trade": _mean(trades), "share_in": float(held.mean()) if n else None,
            "mean_net_hour": _mean(x), "cond_mean_basket": _mean(rb[oos][held]), "uncond_mean_basket": _mean(rb[oos]),
            "buy_hold_sharpe": _sr_ann(bh, T424_HPY), "pos": fr["pos"], "net": fr["net"], "oos": oos,
            "criteria": [(c[0], c[1]) for c in crit], "verdict": v, "why": why}


def _daily_rule_sharpe(r_lead: np.ndarray, r_tgt: np.ndarray, rf: np.ndarray, fit: np.ndarray, test: np.ndarray, k: float,
                       cost: float, ppy: int) -> Optional[float]:
    th = k * float(np.nanstd(r_lead[fit & np.isfinite(r_lead)], ddof=1))
    fr = follow_rule(r_lead, r_tgt, rf, th, cost)
    m = test & np.isfinite(r_tgt)
    return _sr_ann(fr["net"][m], ppy)


def _cb_daily_map(archive, pid: str) -> dict:
    out = {}
    for r in _stream(archive, cbd(pid)):
        v = r.get("value") or {}
        c, vol = _num(v.get("close")), _num(v.get("volume"))
        if c is not None and vol is not None and v.get("t") is not None:
            out[_dday(v["t"])] = (c, vol)
    return out


def b6c_cryptovenue_btc_leads_alts(archive):
    """T-424: BTC's lagged hourly return and the theta = 1 sigma follow rule on the point-in-time top-10 alt basket."""
    prods = _names(archive, CB_PRODUCTS_PREFIX)
    need = [cbh("BTC-USD"), cbh("ETH-USD"), cbd("BTC-USD"), cbd("ETH-USD"), DTB3_B]
    miss = _missing(archive, need + ([] if prods else ["coinbase-products-<day>"]))
    if miss:
        return miss
    stable_ids = set()
    for r in _stream(archive, prods[-1]):
        v = r.get("value") or {}
        if v.get("fx_stablecoin") and v.get("id"):
            stable_ids.add(v["id"])
    daily_names = [nm for nm in _names(archive, "coinbase-daily-") if nm.endswith("-USD")]
    daily = {nm[len("coinbase-daily-"):]: _cb_daily_map(archive, nm[len("coinbase-daily-"):]) for nm in daily_names}
    bh = _hourly(archive, cbh("BTC-USD"))
    t0 = int(datetime(2019, 1, 1, tzinfo=UTC).timestamp())
    last_t = int(bh[0][-1])
    H = (last_t - t0) // 3600 + 1
    first_day, last_day = "2019-01-01", _dday(t0 + (H - 1) * 3600)
    mem = cb_members(daily, first_day, last_day, stable_ids=frozenset(stable_ids))
    everm = sorted({p for ms in mem.values() for p in ms})
    rets, missing_h = {}, []
    for p in everm:
        if _has(archive, cbh(p)):
            ts, cl = _hourly(archive, cbh(p))
            rets[p] = hourly_grid_returns(ts, cl, t0, H)
        else:
            missing_h.append(p)
    rb_btc = hourly_grid_returns(bh[0], bh[1], t0, H)
    basket = np.full(H, np.nan)
    gap_days, sizes = 0, []
    for dd, ms in mem.items():
        h0 = (int(datetime.fromisoformat(dd).replace(tzinfo=UTC).timestamp()) - t0) // 3600
        if h0 >= H:
            continue
        h1 = min(H, h0 + 24)
        have = [p for p in ms if p in rets]
        if len(have) < len(ms):
            gap_days += 1
        if not have:
            continue
        S = np.vstack([rets[p][h0:h1] for p in have])
        with np.errstate(all="ignore"):
            cnt = np.isfinite(S).sum(axis=0)
            basket[h0:h1] = np.where(cnt > 0, np.nansum(S, axis=0) / np.maximum(cnt, 1), np.nan)
        sizes.append(len(have))
    bills = _bills(archive)
    hours_day = [_dday(t0 + 3600 * h) for h in range(0, H, 24)]
    rate_d = np.array([bills.rate(d) for d in hours_day], float)
    rf = np.repeat(rate_d, 24)[:H] / T424_HPY
    tday = np.array([_dday(t0 + 3600 * h) for h in range(H)])
    fit = (tday >= T424_FIT[0]) & (tday <= T424_FIT[1])
    test = tday >= T424_TEST_START
    # family (14 declared cells): 1h x theta {1, 2} x {basket, ETH}; 1d likewise; 1m x 4 (not computable); GLD -> SLV, GDX
    re = rets.get("ETH-USD")
    if re is None:
        te, ce = _hourly(archive, cbh("ETH-USD"))
        re = hourly_grid_returns(te, ce, t0, H)
    fam, fam_note = {}, {}
    for nm, tgt in (("basket", basket), ("eth", re)):
        for k in T424_THETAS:
            th = k * float(np.nanstd(rb_btc[fit & np.isfinite(rb_btc)], ddof=1))
            fr = follow_rule(rb_btc, tgt, rf, th, T424_COST)
            msk = test & np.isfinite(tgt)
            fam[f"1h|{nm}|{k:g}sd"] = _sr_ann(fr["net"][msk], T424_HPY)
    dd_days = sorted(d for d in mem if d >= first_day)
    bd = daily.get("BTC-USD", {})
    def dret(m_):
        out = np.full(len(dd_days), np.nan)
        for i in range(1, len(dd_days)):
            a, b = m_.get(dd_days[i - 1]), m_.get(dd_days[i])
            if a and b and a[0] > 0:
                out[i] = b[0] / a[0] - 1.0
        return out
    rd_btc = dret(bd)
    rd_eth = dret(daily.get("ETH-USD", {}))
    rd_bsk = np.full(len(dd_days), np.nan)
    per = {p: dret(daily.get(p, {})) for p in everm}
    for i, d in enumerate(dd_days):
        vals = [per[p][i] for p in mem[d] if p in per and np.isfinite(per[p][i])]
        if vals:
            rd_bsk[i] = float(np.mean(vals))
    rfd = np.array([bills.rate(d) for d in dd_days], float) / 365.0
    dfit = np.array([T424_FIT[0] <= d <= T424_FIT[1] for d in dd_days])
    dtest = np.array([d >= T424_TEST_START for d in dd_days])
    for nm, tgt in (("basket", rd_bsk), ("eth", rd_eth)):
        for k in T424_THETAS:
            s = _daily_rule_sharpe(rd_btc, tgt, rfd, dfit, dtest, k, T424_COST, 365)
            fam[f"1d|{nm}|{k:g}sd"] = s
    for nm in ("basket", "eth"):
        for k in T424_THETAS:
            fam_note[f"1m|{nm}|{k:g}sd"] = "not computable: only coinbase-1m-BTC-USD is archived (no alt or ETH 1-minute bars)"
    for tgt in ("SLV", "GDX"):
        if _has(archive, dh("GLD")) and _has(archive, dh(tgt)):
            g, t_ = _bars(archive, dh("GLD")), _bars(archive, dh(tgt))
            cm = sorted(set(g["days"]) & set(t_["days"]))
            gm, tm_ = dict(zip(g["days"], g["adj"])), dict(zip(t_["days"], t_["adj"]))
            gr = np.array([np.nan] + [gm[cm[i]] / gm[cm[i - 1]] - 1 for i in range(1, len(cm))])
            tr_ = np.array([np.nan] + [tm_[cm[i]] / tm_[cm[i - 1]] - 1 for i in range(1, len(cm))])
            rfg = np.array([bills.rate(d) for d in cm], float) / 252.0
            gf = np.array([T424_FIT[0] <= d <= T424_FIT[1] for d in cm]); gt = np.array([d >= T424_TEST_START for d in cm])
            fam[f"1d|GLD->{tgt}|1sd"] = _daily_rule_sharpe(gr, tr_, rfg, gf, gt, 1.0, T424_COST, 252)
        else:
            fam_note[f"1d|GLD->{tgt}|1sd"] = "not computable: GLD or the target not archived"
    fam_hourly = [v_ / math.sqrt(T424_HPY) for k, v_ in fam.items() if v_ is not None]
    j = leadlag_test(rb_btc, basket, rf, fit, test, fam_hourly)
    # reported: the lagged fill (one bar later), maker costs, regimes, Granger
    fr_lag = follow_rule(rb_btc, basket, rf, j["theta"], T424_COST, lag=2)
    sr_lag = _sr_ann(fr_lag["net"][j["oos"]], T424_HPY)
    fr_mk = follow_rule(rb_btc, basket, rf, j["theta"], T424_COST_MAKER)
    sr_mk = _sr_ann(fr_mk["net"][j["oos"]], T424_HPY)
    reg = {}
    for yr in ("2021", "2022"):
        m_ = np.array([d.startswith(yr) for d in tday]) & np.isfinite(basket)
        reg[yr] = {"hours": int(m_.sum()), "sharpe_net": _sr_ann(j["net"][m_], T424_HPY)}
    oo = j["oos"]
    gr_ = granger(basket[oo], rb_btc[oo], 4) if oo.sum() > 100 else {"p": None}
    reason = (f"Coinbase hourly {first_day}..{last_day} ({H} hours on the UTC grid); basket = top {T424_TOP} USD products by "
              f"trailing {T424_RANK_DAYS}-day Coinbase dollar volume among {len(daily)} daily bundles (BTC, {len(T424_STABLE)} "
              f"stablecoin bases, {len(stable_ids)} fx_stablecoin ids and {len(T424_WRAPPED) - 1} wrapped/staked bases "
              f"excluded), {len(everm)} products ever members, {len(missing_h)} without an hourly bundle"
              + (f" ({', '.join(missing_h[:8])}{'...' if len(missing_h) > 8 else ''})" if missing_h else "")
              + f", {gap_days} days with a member missing, mean "
              f"basket size {_f(float(np.mean(sizes)) if sizes else None, 1)}; theta = {_p3(j['theta'])} (1 sd of BTC hourly "
              f"returns {T424_FIT[0][:4]}-{T424_FIT[1][:4]}); out of sample {T424_TEST_START}..: {j['n']} hours, coefficient on "
              f"lagged BTC {_f(j['coef'], 4)} (HAC t {_f(j['t'], 2)}), Granger(4) p {_f(gr_.get('p'), 4)}; follow rule in the "
              f"basket {_pu(j['share_in'], 2)} of hours, {j['n_trades']} trades, mean net per trade {_p3(j['mean_net_trade'])}, "
              f"net Sharpe {_s(j['sharpe'])} (bootstrap p {_f(j['boot'].get('p'), 4)}); basket mean after a signal "
              f"{_bp(j['cond_mean_basket'], 2)} vs unconditional {_bp(j['uncond_mean_basket'], 2)}, buy-and-hold basket excess "
              f"Sharpe {_s(j['buy_hold_sharpe'])}; one-bar-later fill Sharpe {_s(sr_lag)}, 30 bps maker {_s(sr_mk)}; in-sample "
              f"2021 / 2022 net Sharpe {_s(reg['2021']['sharpe_net'])} / {_s(reg['2022']['sharpe_net'])}; family Sharpes "
              + ", ".join(f"{k} {_s(v_, 2)}" for k, v_ in fam.items()) + f" (4 one-minute cells not computable) — " + j["why"])
    stat = {"n_oos_hours": j["n"], "hours": H, "first_day": first_day, "last_day": last_day, "theta": j["theta"],
            "coef_lagged_btc": j["coef"], "hac_t": j["t"], "r2": j["r2"], "granger4": gr_, "sharpe_net": j["sharpe"],
            "boot": {k: j["boot"].get(k) for k in ("est", "ci", "p", "p_mc_se", "reps")}, "dsr": j["dsr"],
            "n_trades": j["n_trades"], "mean_net_trade": j["mean_net_trade"], "share_in_basket": j["share_in"],
            "cond_mean_basket": j["cond_mean_basket"], "uncond_mean_basket": j["uncond_mean_basket"],
            "buy_hold_sharpe": j["buy_hold_sharpe"], "sharpe_lagged_fill": sr_lag, "sharpe_maker_30bp": sr_mk, "regimes": reg,
            "family_sharpes_annual": fam, "family_not_computable": fam_note, "members_ever": everm,
            "members_without_hourly": missing_h, "days_with_missing_member": gap_days,
            "mean_basket_size": float(np.mean(sizes)) if sizes else None,
            "exclusions": {"stable_bases": sorted(T424_STABLE), "wrapped_or_staked_bases": sorted(T424_WRAPPED),
                           "fx_stablecoin_ids": sorted(stable_ids)},
            "criteria": j["criteria"], "rule10": "every hour traded: no grid phase",
            "rule12": "the hourly candle is stamped at its close, the fill; the one-bar-later fill is reported"}
    return _out(stat, j["n"], j["verdict"], reason)


# ======================================================================================================= maps ==

HARNESSES = {
    "b6c_cryptovenue_ibit_premium_fade": b6c_cryptovenue_ibit_premium_fade,
    "b6c_cryptovenue_stablecoin_peg_reversion": b6c_cryptovenue_stablecoin_peg_reversion,
    "b6c_cryptovenue_steth_discount_carry": b6c_cryptovenue_steth_discount_carry,
    "b6c_cryptovenue_cbeth_staking_drift": b6c_cryptovenue_cbeth_staking_drift,
    "b6c_cryptovenue_high_volume_premium": b6c_cryptovenue_high_volume_premium,
    "b6c_cryptovenue_btc_leads_alts": b6c_cryptovenue_btc_leads_alts,
}

THEORY_MAP = {
    "T-328": "b6c_cryptovenue_ibit_premium_fade",
    "T-330": "b6c_cryptovenue_stablecoin_peg_reversion",
    "T-365": "b6c_cryptovenue_steth_discount_carry",
    "T-366": "b6c_cryptovenue_cbeth_staking_drift",
    "T-419": "b6c_cryptovenue_high_volume_premium",
    "T-424": "b6c_cryptovenue_btc_leads_alts",
}
