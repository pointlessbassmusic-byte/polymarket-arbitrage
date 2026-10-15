"""
Batch 5, currency carry and momentum: G10 retail carry, G10 + MXN/ZAR carry, 1-month G10 currency momentum.
===========================================================================================================

Three library claims (T-368, T-431, T-478) tested on the archived FRED H.10 noon spot rates (``fx-spot-g10``, USD
per unit of foreign currency) and OECD 3-month interbank rates (``fx-rates-3m``, monthly averages, percent).

Panel. A month-end spot is the last noon fixing of a month (only complete months); a month-start spot is the first
fixing. Spot rows count only if available when the bundle was captured. OECD rates are monthly averages. The EUR and
GBP series stop at 2026-01 and JPY at 2026-07, so later months are forward-filled from the last print (at most 12
months). Every filled month that a result uses is flagged in the report, together with the Sharpe of the window that
ends before the splice. The archive has no policy-rate series to splice in instead.

Leg excess return. A long-foreign leg held over month H (decided at the end of month M = H-1) earns
    S_c(end H) / S_c(end M) - 1 + (r_c(M) - r_USD(M)) / 1200,
the simple spot return in USD plus one month of the 3-month rate differential. r(M) is the average of the month that
ends on the trade date, the closest available proxy for the forward points locked in at the trade. USD legs earn 0:
USD is the numeraire, so holding it is holding cash.

Carry (T-368, T-431). At the end of month M, rank the universe (USD included) on the month M-1 rate (one-month
lagged OECD average, point in time). Long the top 3, short the bottom 3, hold month H. The signal uses no spot data,
so trading at the month-end fixing has no look-ahead. The trial's walk-forward chooses "weights and filters" on the
training window (2002-05 to 2012-12) and freezes them for the test window (2013-01 to 2026-09). The candidates are
{equal weights (the claim's plain top-3/bottom-3), the rule's inverse 60-day volatility} x {no filter, the declared
VIX > 30 filter (flat for month H when the last VIX close before the decision fixing exceeds 30)}. The candidate with
the highest training Sharpe is frozen; ties keep the simpler book (equal, unfiltered first). The primary test book,
the other-weighting comparison and the regimes all use the frozen filter. Inverse volatility uses daily log returns
that end the day before execution; a USD member keeps its 1/3 share as cash. Without a VIX bundle the filter is not
a candidate, and the reason says so.

Costs. The trade cost is charged on the notional traded, sum_c |w_c(H) - w_c(H-1)| * cost_c: 2 bp for G10 and 5 bp
for MXN/ZAR (T-431, from the library rule). The financing admin is charged on every non-USD position,
sum_c |w_c| * admin_c / 12 a month: 1% a year per leg, 2% for ZAR. USD positions pay neither cost.

Momentum (T-478). The universe is the 9 non-USD G10 currencies vs USD. The rule also lists DKK, which the archive
lacks; DKK is EUR-pegged, so it is a near-duplicate of the EUR leg. At the end of month M, rank on the month-M excess
return: spot return plus (r_c(M-1) - r_USD(M-1))/1200, the differential in force over that month. Long the top
third, short the bottom third (k = n // 3), equal weights. Month-end fixings are published the next business day,
so the position is opened at the first fixing of month H and closed at the first fixing of H+1 (one-day skip). A
currency enters only once its spot and rates exist: CHF rates start in 1999-07 and JPY rates in 2002-04, so before
2002-06 the universe has 6-8 currencies (flagged, and the full-universe sub-sample is reported). Each side costs
5 bp on the notional traded. The permutation null assigns currencies to the legs at random each month, 1,000 times,
and every permuted book pays its own turnover costs.

Statistics. Sharpe ratios are annualised with sqrt(12). The carry Sharpe lower bound is the 2.5% quantile of a
stationary block bootstrap (mean block 12 months, 5,000 draws), the lower end of a two-sided 95% interval. The
momentum mean CI is a two-sided 95% circular block bootstrap (block 12, ``_mean_ci``). DSR uses the declared trial
count. Its trial-Sharpe variance comes from the family members that can be computed, floored at 1/(T-1) (the
zero-skill independent-trial variance), so correlated variants cannot lower the bar.

Verdicts use ``underlying2._verdict``: any implemented criterion failing -> not_supported; any criterion not
implemented -> at best inconclusive; supported only when every criterion is implemented and passes. A missing bundle
-> inconclusive with the reason.

House rule 5 (``_rule5``). Below the trial's min_n (T-368/T-431: 150 test months; T-478: 300 holding months) the unmet
'n >= trial min_n' criterion keeps the verdict from supported, and a failing criterion still counts only when it fails
decisively: its 95% interval lies wholly on the wrong side of the claimed bound. Carry: the Sharpe criterion when the
stationary-bootstrap 95% Sharpe interval lies wholly at or below 0.3, the lower-bound criterion and the DSR when it lies
wholly at or below 0 (the DSR's benchmark, the expected best of the trials' zero-skill Sharpes, is >= 0 at any sample
size). Momentum: the mean and DSR criteria when the mean's 95% block-bootstrap CI lies wholly at or below 0, the
permutation criterion when it lies wholly at or below the permutation 95th percentile. A zero-width interval decides
nothing. Under 48 months (4 blocks of the 12-month bootstrap) no interval is computed, no failure can be decisive and
the verdict is inconclusive. Any other failure below min_n is undecided (None), so the verdict is inconclusive. At or
above min_n every criterion is judged at face value, exactly as before. Below min_n the report's ``criteria`` are the
ones judged and ``rule5`` holds the face-value criteria and the decisive failures.
"""

from __future__ import annotations

import calendar
import math
from bisect import bisect_left
from collections import defaultdict
from datetime import date, timedelta
from typing import Iterable, Optional, Sequence

import numpy as np

from mandel.experiments.underlying2 import _mdd, _mean_ci, _sr, _verdict
from mandel.experiments.volatility import index_closes
from mandel.validation.backtest_eval import deflated_sharpe_ratio, sharpe_ratio

PPY = 12
DSR_PASS = 0.95
G10 = ("USD", "EUR", "GBP", "AUD", "NZD", "JPY", "CHF", "CAD", "NOK", "SEK")
G10_FX = G10[1:]
EM = ("MXN", "ZAR")
SPOT_BUNDLE = "fx-spot-g10"
RATE_BUNDLE = "fx-rates-3m"
VIX_BUNDLE = "cboe-VIX-history"

G10_COST_BPS = 2.0
EM_COST_BPS = 5.0
ADMIN = 0.01
ZAR_ADMIN = 0.02
MOM_COST_BPS = 5.0

CARRY_TRAIN = ("2002-05", "2012-12")
CARRY_TEST = ("2013-01", "2026-09")
MOM_WINDOW = ("1999-01", "2026-09")

G10_REGIMES = {"pre-GFC 2002-2007": ("2002-01", "2007-12"), "GFC 2008": ("2008-01", "2008-12"),
               "ZIRP 2009-2021": ("2009-01", "2021-12"), "hikes 2022-2023": ("2022-01", "2023-12"),
               "yen unwind 2024-07..08": ("2024-07", "2024-08")}
EM_REGIMES = {"taper 2013-05..08": ("2013-05", "2013-08"), "2015": ("2015-01", "2015-12"),
              "covid 2020-02..04": ("2020-02", "2020-04"), "yen unwind 2024-07..08": ("2024-07", "2024-08")}
MOM_REGIMES = {"2008 dollar spike": ("2008-01", "2008-12"), "2022 dollar spike": ("2022-01", "2022-12")}


# ------------------------------------------------------------------------------------------------ months --

def _mi(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def _ms(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def madd(m: str, k: int) -> str:
    """Month ``m`` ('YYYY-MM') shifted by ``k`` months."""
    return _ms(_mi(m) + k)


def mrange(a: str, b: str) -> list[str]:
    """Inclusive list of months a..b."""
    return [_ms(i) for i in range(_mi(a), _mi(b) + 1)]


def _last_weekday(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    d = date(y, mo, calendar.monthrange(y, mo)[1])
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


# ------------------------------------------------------------------------------------------------- panel --

def build_panel(spot_values: Iterable[dict], rate_values: Iterable[dict], fill_to: Optional[str] = None,
                max_fill: int = 12) -> dict:
    """Monthly FX panel from ``fx-spot-g10`` / ``fx-rates-3m`` value dicts (already filtered for availability).

    end[c][m] / end_day[c][m]: last fixing of month m (complete months only); first[c][m]: first fixing of month m;
    daily[c] = (days, values); rates[c][m] in percent. Months after a series' last print (up to ``fill_to``, at most
    ``max_fill``) are forward-filled and listed in filled[c] (the stale-series splice); internal one-off gaps are
    forward-filled and listed in gaps[c]."""
    by: dict[str, dict[str, float]] = defaultdict(dict)
    for v in spot_values:
        x = v.get("usd_per_unit")
        if x is None:
            continue
        x = float(x)
        if not (math.isfinite(x) and x > 0):
            continue
        by[v["ccy"]][v["day"]] = x
    last_day = max((d for s in by.values() for d in s), default=None)
    end, end_day, first, daily = {}, {}, {}, {}
    for c, s in by.items():
        days = sorted(s)
        vals = np.array([s[d] for d in days])
        daily[c] = (days, vals)
        e, ed, f = {}, {}, {}
        for d, x in zip(days, vals):
            m = d[:7]
            f.setdefault(m, float(x))
            e[m], ed[m] = float(x), d
        done = [m for m in e if m < last_day[:7] or last_day >= _last_weekday(m)]
        end[c] = {m: e[m] for m in done}
        end_day[c] = {m: ed[m] for m in done}
        first[c] = f
    rates: dict[str, dict[str, float]] = defaultdict(dict)
    for v in rate_values:
        x = v.get("rate3m")
        if x is None or not math.isfinite(float(x)):
            continue
        rates[v["ccy"]][v["month"]] = float(x)
    filled: dict[str, list[str]] = {}
    gaps: dict[str, list[str]] = {}
    for c, r in rates.items():
        ms = sorted(r)
        lastprint = ms[-1]
        target = max(lastprint, fill_to) if fill_to else lastprint
        last, gap, fl, gl = None, 0, [], []
        for m in mrange(ms[0], target):
            if m in r:
                last, gap = r[m], 0
            else:
                gap += 1
                if gap <= max_fill:
                    r[m] = last
                    (fl if m > lastprint else gl).append(m)
        if fl:
            filled[c] = fl
        if gl:
            gaps[c] = gl
    return {"end": end, "end_day": end_day, "first": first, "daily": daily, "rates": dict(rates),
            "filled": filled, "gaps": gaps, "last_day": last_day}


def _rate(panel: dict, c: str, m: str) -> Optional[float]:
    return panel["rates"].get(c, {}).get(m)


def _leg_ret(panel: dict, c: str, M: str, H: str) -> Optional[float]:
    """Excess return of a long-``c`` position over month H (opened at the end of M)."""
    if c == "USD":
        return 0.0
    e = panel["end"].get(c, {})
    s0, s1, rc, ru = e.get(M), e.get(H), _rate(panel, c, M), _rate(panel, "USD", M)
    if s0 is None or s1 is None or rc is None or ru is None:
        return None
    return s1 / s0 - 1.0 + (rc - ru) / 1200.0


def _vol_before(panel: dict, c: str, day: str, window: int = 60) -> Optional[float]:
    """Std of the ``window`` daily log returns that end strictly before ``day``."""
    days, vals = panel["daily"].get(c, ([], None))
    i = bisect_left(days, day)
    if i < window + 1:
        return None
    s = float(np.diff(np.log(vals[i - window - 1:i])).std(ddof=1))
    return s if s > 0 else None


def _decision_day(panel: dict, universe: Sequence[str], M: str) -> Optional[str]:
    ds = [panel["end_day"].get(c, {}).get(M) for c in universe if c != "USD"]
    ds = [d for d in ds if d]
    return max(ds) if ds else None


def _last_before(days: list[str], vals: dict[str, float], day: str) -> Optional[float]:
    i = bisect_left(days, day)
    return vals[days[i - 1]] if i > 0 else None


# ---------------------------------------------------------------------------------------- carry engine --

def _carry_weights(order: list[str], k: int, scheme: str, vols: dict[str, float], universe: Sequence[str]) -> dict[str, float]:
    w = dict.fromkeys(universe, 0.0)
    n = len(order)
    if scheme == "rank":
        z = {c: (n - i) - (n + 1) / 2.0 for i, c in enumerate(order)}           # best gets n, worst 1, centred
        pos = sum(v for v in z.values() if v > 0)
        neg = -sum(v for v in z.values() if v < 0)
        for c, v in z.items():
            w[c] = v / pos if v > 0 else (v / neg if v < 0 else 0.0)
        return w
    if 2 * k > n:
        raise ValueError(f"top/bottom {k} needs at least {2 * k} currencies, got {n}")
    for leg, sign in ((order[:k], 1.0), (order[-k:], -1.0)):
        if scheme == "equal":
            for c in leg:
                w[c] += sign / k
        elif scheme == "invvol":
            fx = [c for c in leg if c != "USD"]
            share = 1.0 - (len(leg) - len(fx)) / k                             # a USD member keeps 1/k as cash
            inv = np.array([1.0 / vols[c] for c in fx])
            for c, x in zip(fx, inv / inv.sum() if fx else []):
                w[c] += sign * share * float(x)
            if "USD" in leg:
                w["USD"] += sign / k
        else:
            raise ValueError(f"unknown weighting {scheme}")
    return w


def carry_backtest(panel: dict, universe: Sequence[str], months: Sequence[str], k: int = 3, weighting: str = "equal",
                   cost_bps: Optional[dict] = None, admin: Optional[dict] = None, rebalance: str = "monthly",
                   vix: Optional[dict] = None, vix_cut: float = 30.0, blend_mom: bool = False,
                   vol_window: int = 60) -> dict:
    """Cross-sectional carry over holding months ``months``.

    At the end of M = H-1, rank ``universe`` on the month M-1 rate (USD included when listed), long the top ``k``,
    short the bottom ``k`` (or rank weights), hold month H. ``blend_mom`` ranks on the mean of the carry rank and the
    rank of the 12-month spot return to the end of M-1. ``vix`` = {day: close} goes flat when the last close before
    the decision fixing exceeds ``vix_cut``. ``rebalance='annual'`` re-ranks only for January holdings. Costs:
    cost_bps[c] per unit of notional traded, admin[c] (decimal a year) per unit held, USD exempt. A month in which a
    universe member lacks data is dropped and the book restarts flat."""
    cost_bps, admin = cost_bps or {}, admin or {}
    universe = list(universe)
    keys = ("months", "gross", "net", "trade_cost", "fin_cost", "turnover", "spread_pp", "long", "short", "flat")
    out: dict = {k_: [] for k_ in keys}
    out["dropped"] = []
    prev = dict.fromkeys(universe, 0.0)
    vix_days = sorted(vix) if vix else None
    for H in months:
        M, P = madd(H, -1), madd(H, -2)
        sig, ret = {}, {}
        ok = _rate(panel, "USD", P) is not None
        for c in universe:
            s, x = _rate(panel, c, P), _leg_ret(panel, c, M, H)
            if s is None or x is None:
                ok = False
                break
            sig[c], ret[c] = s, x
        mom = {}
        if ok and blend_mom:
            for c in universe:
                if c == "USD":
                    mom[c] = 0.0
                    continue
                e = panel["end"].get(c, {})
                a, b = e.get(madd(M, -13)), e.get(P)
                if a is None or b is None:
                    ok = False
                    break
                mom[c] = b / a - 1.0
        vols = {}
        if ok and weighting == "invvol":
            for c in universe:
                if c == "USD":
                    continue
                d = panel["end_day"].get(c, {}).get(M)
                v = _vol_before(panel, c, d, vol_window) if d else None
                if v is None:
                    ok = False
                    break
                vols[c] = v
        if not ok:
            out["dropped"].append(H)
            prev = dict.fromkeys(universe, 0.0)
            continue
        flat = False
        if rebalance == "monthly" or H.endswith("-01") or not any(prev.values()):
            if blend_mom:
                rk_c = {c: i for i, c in enumerate(sorted(universe, key=lambda c: (sig[c], -universe.index(c))))}
                rk_m = {c: i for i, c in enumerate(sorted(universe, key=lambda c: (mom[c], -universe.index(c))))}
                score = {c: (rk_c[c] + rk_m[c]) / 2.0 for c in universe}
            else:
                score = sig
            order = sorted(universe, key=lambda c: (-score[c], universe.index(c)))
            w = _carry_weights(order, k, weighting, vols, universe)
            if vix_days:
                dd = _decision_day(panel, universe, M)
                v = _last_before(vix_days, vix, dd) if dd else None
                if v is not None and v > vix_cut:
                    w, flat = dict.fromkeys(universe, 0.0), True
        else:
            w = prev
        fx = [c for c in universe if c != "USD"]
        gross = sum(w[c] * ret[c] for c in universe)
        turn = {c: abs(w[c] - prev[c]) for c in fx}
        tc = sum(turn[c] * cost_bps.get(c, 0.0) / 1e4 for c in fx)
        fc = sum(abs(w[c]) * admin.get(c, 0.0) / 12.0 for c in fx)
        out["months"].append(H)
        out["gross"].append(gross)
        out["net"].append(gross - tc - fc)
        out["trade_cost"].append(tc)
        out["fin_cost"].append(fc)
        out["turnover"].append(sum(turn.values()))
        out["spread_pp"].append(sum(w[c] * sig[c] for c in universe))
        out["long"].append([c for c in universe if w[c] > 0])
        out["short"].append([c for c in universe if w[c] < 0])
        out["flat"].append(flat)
        prev = w
    for k_ in ("gross", "net", "trade_cost", "fin_cost", "turnover", "spread_pp"):
        out[k_] = np.array(out[k_], dtype=float)
    return out


def em_timeseries(panel: dict, months: Sequence[str], threshold_pp: float = 3.0, cost_bps: Optional[dict] = None,
                  admin: Optional[dict] = None, ccys: Sequence[str] = EM) -> dict:
    """EM-only time-series carry (T-431 variant): long each of MXN/ZAR with weight 1/len(ccys) when its lagged
    (month M-1) rate exceeds the US rate by more than ``threshold_pp``; flat otherwise."""
    cost_bps, admin = cost_bps or {}, admin or {}
    prev = dict.fromkeys(ccys, 0.0)
    ms, net = [], []
    for H in months:
        M, P = madd(H, -1), madd(H, -2)
        ru = _rate(panel, "USD", P)
        rows = {c: (_rate(panel, c, P), _leg_ret(panel, c, M, H)) for c in ccys}
        if ru is None or any(s is None or x is None for s, x in rows.values()):
            prev = dict.fromkeys(ccys, 0.0)
            continue
        w = {c: (1.0 / len(ccys) if rows[c][0] - ru > threshold_pp else 0.0) for c in ccys}
        g = sum(w[c] * rows[c][1] for c in ccys)
        tc = sum(abs(w[c] - prev[c]) * cost_bps.get(c, 0.0) / 1e4 for c in ccys)
        fc = sum(abs(w[c]) * admin.get(c, 0.0) / 12.0 for c in ccys)
        ms.append(H)
        net.append(g - tc - fc)
        prev = w
    return {"months": ms, "net": np.array(net, dtype=float)}


# ------------------------------------------------------------------------------------- momentum engine --

def momentum_backtest(panel: dict, universe: Sequence[str], months: Sequence[str], formation: int = 1,
                      select="thirds", with_diff: bool = True, cost_bps: float = MOM_COST_BPS,
                      skip_day: bool = True, min_elig: int = 6) -> dict:
    """Cross-sectional currency momentum over holding months ``months``.

    At the end of M = H-1 rank the eligible currencies on the ``formation``-month excess return to the end of M
    (spot return plus the differentials r(M-j) - r_USD(M-j), j = 1..formation, when ``with_diff``). Long the top k,
    short the bottom k (k = n // 3 for 'thirds', else ``select``), equal weights. With ``skip_day`` the book is
    opened at the first fixing of H and closed at the first fixing of H+1, earning (r(M) - r_USD(M))/1200 of carry.
    A currency is eligible only when its spot and rate history cover the formation and holding windows. ``cost_bps``
    is charged per side on the notional traded. ``detail`` keeps (H, eligible, holding returns, k) for the
    permutation null."""
    universe = list(universe)
    out: dict = {"months": [], "gross": [], "net": [], "turnover": [], "n_elig": [], "long": [], "short": [], "dropped": [], "detail": []}
    prev = dict.fromkeys(universe, 0.0)
    for H in months:
        M, B = madd(H, -1), madd(H, -1 - formation)
        elig, sig, hold = [], [], []
        for c in universe:
            e = panel["end"].get(c, {})
            s0, s1 = e.get(B), e.get(M)
            if skip_day:
                f = panel["first"].get(c, {})
                h0, h1 = f.get(H), f.get(madd(H, 1))
            else:
                h0, h1 = s1, e.get(H)
            if s0 is None or s1 is None or h0 is None or h1 is None:
                continue
            cf = ch = 0.0
            if with_diff:
                rs = [(_rate(panel, c, madd(M, -j)), _rate(panel, "USD", madd(M, -j))) for j in range(1, formation + 1)]
                rh = (_rate(panel, c, M), _rate(panel, "USD", M))
                if any(a is None or b is None for a, b in rs) or rh[0] is None or rh[1] is None:
                    continue
                cf = sum(a - b for a, b in rs) / 1200.0
                ch = (rh[0] - rh[1]) / 1200.0
            elig.append(c)
            sig.append(s1 / s0 - 1.0 + cf)
            hold.append(h1 / h0 - 1.0 + ch)
        k = len(elig) // 3 if select == "thirds" else int(select)
        if len(elig) < max(min_elig, 2 * k) or k < 1:
            out["dropped"].append(H)
            out["detail"].append((H, None, None, 0))
            prev = dict.fromkeys(universe, 0.0)
            continue
        order = np.argsort(-np.array(sig), kind="stable")
        w = dict.fromkeys(universe, 0.0)
        longs = [elig[i] for i in order[:k]]
        shorts = [elig[i] for i in order[-k:]]
        for c in longs:
            w[c] = 1.0 / k
        for c in shorts:
            w[c] = -1.0 / k
        x = dict(zip(elig, hold))
        g = sum(w[c] * x[c] for c in elig)
        turn = sum(abs(w[c] - prev[c]) for c in universe)
        out["months"].append(H)
        out["gross"].append(g)
        out["net"].append(g - turn * cost_bps / 1e4)
        out["turnover"].append(turn)
        out["n_elig"].append(len(elig))
        out["long"].append(longs)
        out["short"].append(shorts)
        out["detail"].append((H, elig, np.array(hold), k))
        prev = w
    for k_ in ("gross", "net", "turnover"):
        out[k_] = np.array(out[k_], dtype=float)
    return out


def permutation_null(detail: list, universe: Sequence[str], cost_bps: float = MOM_COST_BPS, n_perm: int = 1000,
                     seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """(net means, gross means) of ``n_perm`` books that put k random eligible currencies long and k short each
    month, with the same eligibility, holding returns and restart-after-gap rule as the tested book, each paying its
    own per-side costs."""
    rng = np.random.default_rng(seed)
    pos = {c: i for i, c in enumerate(universe)}
    rows = np.arange(n_perm)[:, None]
    W_prev = np.zeros((n_perm, len(universe)))
    s_net, s_gross, n = np.zeros(n_perm), np.zeros(n_perm), 0
    for H, elig, x, k in detail:
        if elig is None:
            W_prev = np.zeros_like(W_prev)
            continue
        cols = np.array([pos[c] for c in elig])
        perm = np.argsort(rng.random((n_perm, len(elig))), axis=1)
        W = np.zeros_like(W_prev)
        W[rows, cols[perm[:, :k]]] = 1.0 / k
        W[rows, cols[perm[:, -k:]]] = -1.0 / k
        xv = np.zeros(len(universe))
        xv[cols] = x
        g = W @ xv
        s_gross += g
        s_net += g - np.abs(W - W_prev).sum(axis=1) * cost_bps / 1e4
        n += 1
        W_prev = W
    return s_net / max(n, 1), s_gross / max(n, 1)


# ------------------------------------------------------------------------------------------- statistics --

def stationary_boot_sharpe(x, ppy: int = PPY, mean_block: float = 12.0, n_boot: int = 5000, seed: int = 0) -> np.ndarray:
    """Annualised Sharpe ratios of ``n_boot`` stationary-bootstrap resamples (Politis-Romano, geometric blocks of
    mean length ``mean_block``, circular)."""
    x = np.asarray(x, dtype=float)
    n = x.size
    rng = np.random.default_rng(seed)
    idx = np.empty((n_boot, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, n_boot)
    new = rng.random((n_boot, n)) < 1.0 / mean_block
    starts = rng.integers(0, n, (n_boot, n))
    for t in range(1, n):
        idx[:, t] = np.where(new[:, t], starts[:, t], (idx[:, t - 1] + 1) % n)
    s = x[idx]
    sd = s.std(axis=1, ddof=1)
    mu = s.mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sr = np.where(sd > 0, mu / np.where(sd > 0, sd, 1.0), 0.0)
    return sr * math.sqrt(ppy)


def nw_tstat(x, lags: int = 6) -> float:
    """t-stat of the mean with a Newey-West (Bartlett) long-run variance."""
    x = np.asarray(x, dtype=float)
    n = x.size
    if n < 3:
        return float("nan")
    d = x - x.mean()
    v = float(d @ d) / n
    for k in range(1, lags + 1):
        v += 2.0 * (1.0 - k / (lags + 1)) * float(d[k:] @ d[:-k]) / n
    return float(x.mean() / math.sqrt(v / n)) if v > 0 else float("nan")


def skewness(x) -> float:
    x = np.asarray(x, dtype=float)
    s = x.std()
    return float(((x - x.mean()) ** 3).mean() / s ** 3) if x.size > 2 and s > 0 else float("nan")


def family_dsr(x, family_sharpes: Sequence[float], n_trials: int) -> dict:
    """DSR of ``x`` against the best of ``n_trials`` trials, trial-Sharpe variance from the computable family
    (per-period Sharpes), floored at 1/(T-1)."""
    x = np.asarray(x, dtype=float)
    fs = np.array([s for s in family_sharpes if s is not None and math.isfinite(s)], dtype=float)
    v = float(fs.var(ddof=1)) if fs.size > 1 else 0.0
    floor = 1.0 / max(1, x.size - 1)
    v = max(v, floor)
    return {"dsr": float(deflated_sharpe_ratio(x, n_trials=n_trials, var_trials_sr=v)), "var_trials_sr": v,
            "var_floor": floor, "n_trials": int(n_trials), "n_family_computed": int(fs.size)}


def _perf(net: np.ndarray, gross: Optional[np.ndarray] = None, n_boot: int = 5000, seed: int = 0) -> dict:
    boot = stationary_boot_sharpe(net, PPY, 12.0, n_boot, seed)
    out = {"sharpe": _sr(net, PPY), "boot_lo": float(np.quantile(boot, 0.025)), "boot_hi": float(np.quantile(boot, 0.975)),
           "boot_lo_5pct": float(np.quantile(boot, 0.05)), "mean_pct_month": float(net.mean() * 100),
           "ann_mean_pct": float(net.mean() * 1200), "ann_vol_pct": float(net.std(ddof=1) * math.sqrt(12) * 100),
           "skew": skewness(net), "mdd": _mdd(net), "tstat_nw6": nw_tstat(net, 6)}
    if gross is not None:
        out["gross_sharpe"] = _sr(gross, PPY)
        out["gross_ann_mean_pct"] = float(gross.mean() * 1200)
    return out


# ------------------------------------------------------------------------------------------------ house rule 5 --

BOOT_BLOCK = 12
MIN_RULE5_MONTHS = 4 * BOOT_BLOCK      # under 4 blocks of the 12-month bootstrap no interval decides a failure below min_n


def _ci_below(lo, hi, bound: float) -> bool:
    """The 95% interval [lo, hi] lies wholly at or below ``bound``. False without an interval and for a zero-width one."""
    return lo is not None and hi is not None and math.isfinite(lo) and math.isfinite(hi) and lo < hi and hi <= bound


def _rule5(crit, decisive, n: int, min_n: int, unit: str) -> tuple[str, str, list, dict]:
    """House rule 5 below the trial's min_n (``n`` in the claim's own units; at or above min_n callers judge ``crit`` at
    face value with ``_verdict``, exactly as before). ``crit``: the face-value criteria [(name, ok)]; ``decisive``: one
    flag per criterion, True when its failure stands below min_n (its 95% interval lies wholly on the wrong side of the
    claimed bound). A passing or decisively failing criterion keeps its bool, any other failure becomes None
    (undecided), and the unmet 'n >= trial min_n' criterion (None) keeps the verdict from 'supported'.
    Returns (verdict, why, criteria judged, rule-5 record)."""
    crit = [(name, None if ok is None else bool(ok)) for name, ok in crit]
    judged = [(name, ok) if ok is None or ok else (name + " (fails decisively below min_n)", False) if d
              else (name + " (fails, not decisively, below min_n: undecided)", None) for (name, ok), d in zip(crit, decisive)]
    judged.append((f"n >= trial min_n ({n} {unit}, need {min_n})", None))
    failed = [name for (name, ok), d in zip(crit, decisive) if ok is False and d]
    v, why = _verdict(judged)
    v0, why0 = _verdict(crit)
    why = (f"only {n} {unit}, below the trial's min_n {min_n}, so the verdict cannot be supported and a failing criterion "
           f"counts only when it fails decisively, its 95% interval wholly on the wrong side of the claimed bound (house rule 5). "
           f"Decisive failures: {'; '.join(failed) if failed else 'none'}. {v}: {why} (criteria at face value: {v0}, {why0})")
    return v, why, judged, {"min_n": min_n, "n": n, "unit": unit, "criteria": [[c, ok] for c, ok in judged],
                            "criteria_at_face_value": [[c, ok] for c, ok in crit], "decisive_failures": failed}


def _regimes(months: Sequence[str], net: np.ndarray, regimes: dict) -> dict:
    out = {}
    for name, (a, b) in regimes.items():
        m = np.array([a <= h <= b for h in months], dtype=bool)
        if m.sum() == 0:
            out[name] = None
            continue
        x = net[m]
        out[name] = {"months": int(m.sum()), "cum_net_pct": float((np.prod(1 + x) - 1) * 100),
                     "ann_mean_pct": float(x.mean() * 1200), "sharpe": _sr(x, PPY) if x.size > 2 else None}
    return out


def _filled_used(panel: dict, universe: Sequence[str], first_rate_month: str, last_rate_month: str, kind: str = "filled") -> dict:
    """{ccy: forward-filled rate months inside [first, last]} for ``kind`` 'filled' (stale tail) or 'gaps'."""
    src = panel.get(kind, {})
    out = {}
    for c in list(universe) + ["USD"]:
        ms = [m for m in src.get(c, []) if first_rate_month <= m <= last_rate_month]
        if ms:
            out[c] = ms
    return out


def _fmt_filled(f: dict) -> str:
    if not f:
        return "none"
    return ", ".join(f"{c} {ms[0]}..{ms[-1]} ({len(ms)} mo)" for c, ms in f.items())


# --------------------------------------------------------------------------------------- carry reports --

def g10_costs() -> tuple[dict, dict]:
    return {c: G10_COST_BPS for c in G10_FX}, {c: ADMIN for c in G10_FX}


def em_costs() -> tuple[dict, dict]:
    cb, ad = g10_costs()
    cb.update({c: EM_COST_BPS for c in EM})
    ad.update({"MXN": ADMIN, "ZAR": ZAR_ADMIN})
    return cb, ad


CHOICE_CANDIDATES = (("equal", False), ("invvol", False), ("equal", True), ("invvol", True))   # tie order: simplest first
VIX_FILTER = "vix30"


def choose_weighting(panel: dict, universe: Sequence[str], train: tuple[str, str], cost_bps: dict, admin: dict,
                     min_train: int = 24, vix: Optional[dict] = None) -> dict:
    """Walk-forward choice of weights and filter on the training window: {equal, inverse-60-day-volatility} x {no
    filter, VIX > 30 filter}. The filter is a candidate only when ``vix`` is given. The highest training Sharpe is
    frozen; ties keep the earlier (simpler) candidate. ``train`` is keyed 'equal', 'invvol', 'equal+vix30',
    'invvol+vix30'."""
    ms = mrange(*train)
    res = {}
    for scheme, filt in CHOICE_CANDIDATES:
        if filt and not vix:
            continue
        bt = carry_backtest(panel, universe, ms, weighting=scheme, cost_bps=cost_bps, admin=admin, vix=vix if filt else None)
        res[scheme + ("+" + VIX_FILTER if filt else "")] = {
            "n": int(bt["net"].size), "sharpe": _sr(bt["net"], PPY) if bt["net"].size > 2 else None,
            "first": bt["months"][0] if bt["months"] else None, "last": bt["months"][-1] if bt["months"] else None,
            "flat_months": int(sum(bt["flat"]))}
    eq = res["equal"]
    best = "equal"
    if eq["n"] >= min_train and eq["sharpe"] is not None:
        for name, r in res.items():
            if r["n"] >= min_train and r["sharpe"] is not None and r["sharpe"] > res[best]["sharpe"]:
                best = name
    return {"chosen": best.split("+")[0], "filter": VIX_FILTER if best.endswith("+" + VIX_FILTER) else "none",
            "chosen_book": best, "filter_evaluated": bool(vix), "train": res, "training_ok": eq["n"] >= min_train}


def g10_family(panel: dict, weighting: str, test: Sequence[str], vix: Optional[dict]) -> dict:
    """Declared G10 carry trials (6) on the test months: per-period net returns by name (None = not computable)."""
    cb, ad = g10_costs()
    run = lambda **kw: carry_backtest(panel, kw.pop("u", G10), test, cost_bps=cb, admin=ad, **kw)["net"]
    return {"base": run(weighting=weighting),
            "dollar_neutral_9": run(u=G10_FX, weighting=weighting),
            "rank_weighted_all": run(weighting="rank"),
            "vix30_filter": run(weighting=weighting, vix=vix) if vix else None,
            "carry_plus_12m_momentum": run(weighting=weighting, blend_mom=True),
            "annual_rebalance": run(weighting=weighting, rebalance="annual")}


def em_family(panel: dict, weighting: str, test: Sequence[str], vix: Optional[dict]) -> dict:
    """Declared EM carry trials (4) on the test months; '+KRW' has no archived KRW series."""
    cb, ad = em_costs()
    u = list(G10) + list(EM)
    return {"base_g10_mxn_zar": carry_backtest(panel, u, test, weighting=weighting, cost_bps=cb, admin=ad)["net"],
            "plus_krw_research": None,
            "em_only_timeseries_3pp": em_timeseries(panel, test, 3.0, cb, ad)["net"],
            "vix30_filter": carry_backtest(panel, u, test, weighting=weighting, cost_bps=cb, admin=ad, vix=vix)["net"] if vix else None}


def carry_report(panel: dict, *, universe: Sequence[str], cost_bps: dict, admin: dict, n_trials: int, family: str,
                 vix: Optional[dict] = None, train: tuple[str, str] = CARRY_TRAIN, test: tuple[str, str] = CARRY_TEST,
                 min_n: int = 150, sharpe_bar: float = 0.3, regimes: Optional[dict] = None, label: str = "carry",
                 n_boot: int = 5000, seed: int = 0) -> dict:
    """Walk-forward carry test: weights and the VIX > 30 filter chosen on ``train``, frozen on ``test``. Pass: test Sharpe > ``sharpe_bar``,
    stationary-bootstrap 2.5% lower bound > 0, DSR > 0.95 at ``n_trials``. ``family`` = 'g10' (6 declared trials) or
    'em' (4 EM trials + the G10 entry's 6). Below ``min_n`` test months house rule 5 applies: never supported; the
    Sharpe fails decisively when its stationary-bootstrap 95% interval lies wholly at or below ``sharpe_bar``, the
    lower-bound criterion and the DSR when it lies wholly at or below 0; under 48 months nothing is computed."""
    universe = list(universe)
    sel = choose_weighting(panel, universe, train, cost_bps, admin, vix=vix)
    ws = sel["chosen"]
    vf = vix if sel["filter"] == VIX_FILTER else None                       # the frozen filter
    test_ms = mrange(*test)
    bt = carry_backtest(panel, universe, test_ms, weighting=ws, cost_bps=cost_bps, admin=admin, vix=vf)
    net, n = bt["net"], int(bt["net"].size)
    rep: dict = {"label": label, "universe": universe, "weighting": ws, "filter": sel["filter"], "weight_selection": sel, "n": n,
                 "flat_months": int(sum(bt["flat"])),
                 "test_window": [bt["months"][0], bt["months"][-1]] if n else None, "test_dropped": bt["dropped"],
                 "costs": {"trade_bps": cost_bps, "admin_per_year": admin}}
    if n < min_n and n < MIN_RULE5_MONTHS:
        rep.update(verdict="inconclusive",
                   reason=f"{label}: only {n} test months in {test[0]}..{test[1]} with every currency's spot and lagged rate (need {min_n}); "
                          f"dropped {len(bt['dropped'])} months, fewer than {MIN_RULE5_MONTHS} (4 blocks of the {BOOT_BLOCK}-month "
                          f"bootstrap), so no interval and no decisive failure below min_n (house rule 5) — the archived data cannot "
                          f"support the claim's window")
        return rep
    perf = _perf(net, bt["gross"], n_boot, seed)
    other = "invvol" if ws == "equal" else "equal"
    alt = carry_backtest(panel, universe, test_ms, weighting=other, cost_bps=cost_bps, admin=admin, vix=vf)["net"]
    fam = g10_family(panel, ws if family == "g10" else choose_weighting(panel, G10, train, *g10_costs(), vix=vix)["chosen"], test_ms, vix)
    if family == "em":
        fam = {**{"em:" + k: v for k, v in em_family(panel, ws, test_ms, vix).items()}, **{"g10:" + k: v for k, v in fam.items()}}
    fam_sr = {k: (sharpe_ratio(v) if v is not None and v.size > 2 else None) for k, v in fam.items()}
    d = family_dsr(net, [s for s in fam_sr.values() if s is not None], n_trials)
    filled = _filled_used(panel, universe, madd(bt["months"][0], -2), madd(bt["months"][-1], -1))
    gaps = _filled_used(panel, universe, madd(bt["months"][0], -2), madd(bt["months"][-1], -1), "gaps")
    first_fill = min((ms[0] for ms in filled.values()), default=None)
    pre = None
    if first_fill:
        cut = madd(first_fill, 1)                                           # accrual month M = H-1 first filled
        m = np.array([h < cut for h in bt["months"]], dtype=bool)
        if m.sum() > 2:
            pre = {"through": madd(cut, -1), "months": int(m.sum()), "sharpe": _sr(net[m], PPY)}
    full = carry_backtest(panel, universe, mrange(train[0], test[1]), weighting=ws, cost_bps=cost_bps, admin=admin, vix=vf)
    rep.update(perf)
    rep.update({"alt_weighting": other, "alt_weighting_test_sharpe": _sr(alt, PPY) if alt.size > 2 else None,
                "carry_spread_pp_mean": float(bt["spread_pp"].mean()), "carry_spread_tstat_nw6": nw_tstat(bt["spread_pp"], 6),
                "net_mean_tstat_nw6": perf["tstat_nw6"],
                "costs_pct_year": {"trade": float(bt["trade_cost"].mean() * 1200), "financing": float(bt["fin_cost"].mean() * 1200)},
                "mean_turnover": float(bt["turnover"].mean()), "usd_in_long_pct": float(np.mean(["USD" in l for l in bt["long"]]) * 100),
                "usd_in_short_pct": float(np.mean(["USD" in s for s in bt["short"]]) * 100),
                "family_sharpes_ann": {k: (s * math.sqrt(PPY) if s is not None else None) for k, s in fam_sr.items()},
                "dsr": d["dsr"], "dsr_detail": d, "spliced_rates": filled, "gap_filled_rates": gaps, "sharpe_before_splice": pre,
                "regimes": _regimes(full["months"], full["net"], regimes or {}),
                "last_positions": {"month": bt["months"][-1], "long": bt["long"][-1], "short": bt["short"][-1]}})
    crit = [(f"test-window net Sharpe > {sharpe_bar:g}", perf["sharpe"] > sharpe_bar),
            ("stationary-bootstrap lower bound > 0", perf["boot_lo"] > 0),
            (f"DSR > {DSR_PASS} with n_trials = {n_trials}", d["dsr"] > DSR_PASS)]
    r5 = None
    if n < min_n:
        # rule 5: the Sharpe fails decisively when its stationary-bootstrap 95% interval lies wholly at or below the bar;
        # the lower-bound criterion and the DSR (benchmark >= 0) when it lies wholly at or below 0
        lo_, hi_ = perf["boot_lo"], perf["boot_hi"]
        v, why, judged, r5 = _rule5(crit, [_ci_below(lo_, hi_, sharpe_bar), _ci_below(lo_, hi_, 0.0), _ci_below(lo_, hi_, 0.0)],
                                    n, min_n, "test months")
    else:
        v, why = _verdict(crit)
        judged = crit
    tr = sel["train"]
    eq_s, iv_s = tr["equal"]["sharpe"], tr["invvol"]["sharpe"]
    pre_txt = f"; Sharpe through {pre['through']} (before the splice) {pre['sharpe']:.2f}" if pre else ""
    fv = "+" + VIX_FILTER
    if sel["filter_evaluated"]:
        filt_train = f", with VIX > 30 filter equal {_f(tr['equal' + fv]['sharpe'])} vs inverse-vol {_f(tr['invvol' + fv]['sharpe'])}"
    else:
        filt_train = "; VIX > 30 filter not evaluated (no VIX bundle)"
    book = f"weights {ws} + VIX > 30 filter" if vf else f"weights {ws}, no filter,"
    flat_txt = f"; flat in {rep['flat_months']} of {n} test months" if vf else ""
    reason = (f"{label}, test {rep['test_window'][0]}..{rep['test_window'][1]} ({n} months), {book} chosen on "
              f"{tr['equal']['first']}..{tr['equal']['last']} (train Sharpe equal {_f(eq_s)} vs inverse-vol {_f(iv_s)}{filt_train}; "
              f"test Sharpe of the other weighting with the same filter {_f(rep['alt_weighting_test_sharpe'])}{flat_txt}): net Sharpe {perf['sharpe']:.2f} "
              f"(need > {sharpe_bar:g}); stationary-bootstrap 95% interval [{perf['boot_lo']:+.2f}, {perf['boot_hi']:+.2f}] "
              f"(lower bound need > 0); DSR {d['dsr']:.3f} at {n_trials} trials (need > {DSR_PASS}). "
              f"Gross Sharpe {perf['gross_sharpe']:.2f}, net {perf['ann_mean_pct']:+.2f}%/yr, costs "
              f"{rep['costs_pct_year']['trade']:.2f}% trade + {rep['costs_pct_year']['financing']:.2f}% financing a year, "
              f"skew {perf['skew']:+.2f}, MDD {perf['mdd'] * 100:.1f}%, carry spread {rep['carry_spread_pp_mean']:.2f} pp; "
              f"stale rates spliced by forward fill (flagged): {_fmt_filled(filled)}{pre_txt}; one-month gaps filled: {_fmt_filled(gaps)} — {why}")
    rep.update(verdict=v, reason=reason, criteria=[[c, b] for c, b in judged])
    if r5:
        rep["rule5"] = r5
    return rep


def _f(x) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.2f}"


# ------------------------------------------------------------------------------------ momentum report --

MOM_FAMILY = [(f, s, dd) for f in (1, 3, 6, 12) for s in ("thirds", 2) for dd in (True, False)]


def momentum_report(panel: dict, *, universe: Sequence[str] = G10_FX, window: tuple[str, str] = MOM_WINDOW,
                    cost_bps: float = MOM_COST_BPS, n_trials: int = 16, n_perm: int = 1000, min_n: int = 300,
                    full_universe_from: Optional[str] = None, n_boot: int = 5000, seed: int = 0) -> dict:
    """T-478: 1-month currency momentum, top third minus bottom third, with interest differentials, ``cost_bps``
    per side. Pass: mean net monthly return > 0 with the two-sided 95% block-bootstrap CI (block 12) excluding 0,
    DSR > 0.95 at ``n_trials`` (family: formation 1/3/6/12 x thirds/top-bottom-2 x with/without differentials),
    mean above the 95th percentile of ``n_perm`` random-ranking books. Below ``min_n`` holding months house rule 5
    applies: never supported; the mean and DSR criteria fail decisively when the mean's 95% CI lies wholly at or below
    0, the permutation criterion when it lies wholly at or below the permutation 95th percentile; under 48 months
    nothing is computed."""
    universe = list(universe)
    ms = mrange(*window)
    bt = momentum_backtest(panel, universe, ms, 1, "thirds", True, cost_bps, True)
    net, n = bt["net"], int(bt["net"].size)
    rep: dict = {"universe": universe, "n": n, "window": [bt["months"][0], bt["months"][-1]] if n else None,
                 "dropped": bt["dropped"], "cost_bps_per_side": cost_bps}
    if n < min_n and n < MIN_RULE5_MONTHS:
        rep.update(verdict="inconclusive",
                   reason=f"currency momentum: only {n} holding months in {window[0]}..{window[1]} with >= 6 eligible currencies "
                          f"(need {min_n}), fewer than {MIN_RULE5_MONTHS} (4 blocks of the {BOOT_BLOCK}-month bootstrap), so no "
                          f"interval and no decisive failure below min_n (house rule 5) — the archived data cannot support the claim's window")
        return rep
    lo, hi = _mean_ci(net, 12, n_boot, seed)
    fam = {}
    for f, s, dd in MOM_FAMILY:
        x = momentum_backtest(panel, universe, ms, f, s, dd, cost_bps, True)["net"]
        fam[f"f{f}_{s}_{'diff' if dd else 'spot'}"] = sharpe_ratio(x) if x.size > 2 else None
    d = family_dsr(net, [s for s in fam.values() if s is not None], n_trials)
    pn, pg = permutation_null(bt["detail"], universe, cost_bps, n_perm, seed)
    q95 = float(np.quantile(pn, 0.95))
    q95g = float(np.quantile(pg, 0.95))
    nf = momentum_backtest(panel, universe, ms, 1, "thirds", True, cost_bps, False)["net"]
    ne = np.array(bt["n_elig"])
    full_from = full_universe_from or next((h for h, k in zip(bt["months"], ne) if k == len(universe)), None)
    sub = None
    if full_from:
        m = np.array([h >= full_from for h in bt["months"]], dtype=bool)
        if m.sum() > 24:
            slo, shi = _mean_ci(net[m], 12, n_boot, seed)
            sub = {"from": full_from, "months": int(m.sum()), "mean_bps": float(net[m].mean() * 1e4), "ci_bps": [slo * 1e4, shi * 1e4]}
    filled = _filled_used(panel, universe, madd(bt["months"][0], -2), madd(bt["months"][-1], -1))
    gaps = _filled_used(panel, universe, madd(bt["months"][0], -2), madd(bt["months"][-1], -1), "gaps")
    rep.update({"mean_bps": float(net.mean() * 1e4), "ci_bps": [lo * 1e4, hi * 1e4], "gross_mean_bps": float(bt["gross"].mean() * 1e4),
                "sharpe": _sr(net, PPY), "gross_sharpe": _sr(bt["gross"], PPY), "tstat_nw6": nw_tstat(net, 6),
                "skew": skewness(net), "mdd": _mdd(net), "mean_turnover": float(bt["turnover"].mean()),
                "cost_bps_month": float(bt["turnover"].mean() * cost_bps),
                "dsr": d["dsr"], "dsr_detail": d, "family_sharpes_ann": {k: (s * math.sqrt(PPY) if s is not None else None) for k, s in fam.items()},
                "perm_q95_bps": q95 * 1e4, "perm_pctile": float((pn < net.mean()).mean() * 100),
                "perm_gross_q95_bps": q95g * 1e4, "perm_gross_pctile": float((pg < bt["gross"].mean()).mean() * 100),
                "same_fixing_mean_bps": float(nf.mean() * 1e4) if nf.size else None,
                "months_partial_universe": int((ne < len(universe)).sum()), "min_universe": int(ne.min()),
                "full_universe_subsample": sub, "regimes": _regimes(bt["months"], net, MOM_REGIMES), "spliced_rates": filled,
                "gap_filled_rates": gaps})
    crit = [("mean net monthly excess return > 0 with block-bootstrap 95% CI excluding 0", net.mean() > 0 and lo > 0),
            (f"DSR > {DSR_PASS} with {n_trials} trials", d["dsr"] > DSR_PASS),
            ("mean above the permutation 95th percentile", net.mean() > q95)]
    r5 = None
    if n < min_n:
        # rule 5: the mean and the DSR (benchmark >= 0) fail decisively when the mean's 95% block-bootstrap CI lies wholly
        # at or below 0; the permutation criterion when it lies wholly at or below the permutation 95th percentile
        v, why, judged, r5 = _rule5(crit, [_ci_below(lo, hi, 0.0), _ci_below(lo, hi, 0.0), _ci_below(lo, hi, q95)],
                                    n, min_n, "holding months")
    else:
        v, why = _verdict(crit)
        judged = crit
    sub_txt = (f"; full {len(universe)}-currency sub-sample from {sub['from']} ({sub['months']} months) {sub['mean_bps']:+.1f} bps "
               f"[{sub['ci_bps'][0]:+.1f}, {sub['ci_bps'][1]:+.1f}]") if sub else ""
    reason = (f"currency momentum {rep['window'][0]}..{rep['window'][1]} ({n} months, {len(universe)}-currency universe; "
              f"{rep['months_partial_universe']} early months with {rep['min_universe']}-{len(universe) - 1} currencies while CHF/JPY rates are missing; "
              f"DKK not archived): mean net {rep['mean_bps']:+.1f} bps/month, 95% CI [{lo * 1e4:+.1f}, {hi * 1e4:+.1f}] (need > 0 and CI excluding 0); "
              f"DSR {d['dsr']:.3f} at {n_trials} trials (need > {DSR_PASS}); permutation 95th pct {q95 * 1e4:+.1f} bps, observed at "
              f"pctile {rep['perm_pctile']:.1f} (need above the 95th). Gross {rep['gross_mean_bps']:+.1f} bps, costs "
              f"{rep['cost_bps_month']:.1f} bps/month, net Sharpe {rep['sharpe']:.2f}{sub_txt}; same-fixing (no skip) "
              f"{_f(rep['same_fixing_mean_bps'])} bps; stale rates spliced by forward fill (flagged): {_fmt_filled(filled)}; "
              f"one-month gaps filled: {_fmt_filled(gaps)}; "
              f"ETF cost check not run (FXE/FXY/FXB/FXF/FXC/FXA not archived; reported item, not a pass criterion) — {why}")
    rep.update(verdict=v, reason=reason, criteria=[[c, b] for c, b in judged])
    if r5:
        rep["rule5"] = r5
    return rep


# ----------------------------------------------------------------------------------------- archive I/O --

_CACHE: dict = {}


def _has(archive, name: str) -> bool:
    try:
        archive.get(name)
        return True
    except KeyError:
        return False


def _values(archive, name: str) -> list[dict]:
    entry = archive.get(name)
    cap = getattr(entry, "created_at", None)
    return [r["value"] for r in archive.load(name) if not (cap and r.get("available_at") and r["available_at"] > cap)]


def _panel(archive, fill_to: str) -> dict:
    key = (id(archive), fill_to)
    hit = _CACHE.get(key)
    if hit is None or hit[0] is not archive:
        _CACHE.clear()
        hit = (archive, build_panel(_values(archive, SPOT_BUNDLE), _values(archive, RATE_BUNDLE), fill_to=fill_to))
        _CACHE[key] = hit
    return hit[1]


def _vix(archive) -> Optional[dict]:
    if not _has(archive, VIX_BUNDLE):
        return None
    entry = archive.get(VIX_BUNDLE)
    cap = getattr(entry, "created_at", None)
    rows = (r for r in archive.load(VIX_BUNDLE) if not (cap and r.get("available_at") and r["available_at"] > cap))
    return index_closes(rows) or None


def _missing(archive, names: Sequence[str]):
    miss = [x for x in names if not _has(archive, x)]
    if miss:
        return {"missing_bundles": miss}, 0, "inconclusive", f"missing data bundles {miss}: the claim cannot be tested until they are archived"
    return None


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
    return x


def _wrap(rep: dict):
    rep = _clean(rep)
    return rep, int(rep.get("n") or 0), rep["verdict"], rep["reason"]


# ------------------------------------------------------------------------------------------- harnesses --

def fx_carry_g10(archive):
    """T-368: G10 carry incl. USD, top 3 minus bottom 3 on one-month-lagged OECD 3-month rates, 1%/yr admin per
    leg and 2 bp per trade; 2013-01..2026-09 test Sharpe > 0.3, bootstrap lower bound > 0, DSR > 0.95 (6 trials)."""
    miss = _missing(archive, [SPOT_BUNDLE, RATE_BUNDLE])
    if miss:
        return miss
    panel = _panel(archive, madd(CARRY_TEST[1], -1))
    cb, ad = g10_costs()
    rep = carry_report(panel, universe=G10, cost_bps=cb, admin=ad, n_trials=6, family="g10", vix=_vix(archive),
                       regimes=G10_REGIMES, label="G10 carry (10 incl. USD, top 3 - bottom 3)")
    return _wrap(rep)


def fx_carry_em(archive):
    """T-431: carry over the 10 G10 currencies + MXN + ZAR, top 3 minus bottom 3 on lagged OECD 3-month rates,
    1%/yr admin (2% ZAR), 2 bp per G10 trade and 5 bp per EM trade; test Sharpe > 0.3, bootstrap lower bound > 0,
    DSR > 0.95 with 4 + 6 = 10 trials."""
    miss = _missing(archive, [SPOT_BUNDLE, RATE_BUNDLE])
    if miss:
        return miss
    panel = _panel(archive, madd(CARRY_TEST[1], -1))
    cb, ad = em_costs()
    rep = carry_report(panel, universe=list(G10) + list(EM), cost_bps=cb, admin=ad, n_trials=10, family="em",
                       vix=_vix(archive), regimes=EM_REGIMES, label="G10 + MXN + ZAR carry (top 3 - bottom 3)")
    return _wrap(rep)


def fx_momentum_g10(archive):
    """T-478: 1-month G10 currency momentum with interest differentials, top third minus bottom third, 5 bp per
    side, 1999-2026; mean > 0 with block-bootstrap CI excluding 0, DSR > 0.95 (16 trials), above the permutation
    95th percentile."""
    miss = _missing(archive, [SPOT_BUNDLE, RATE_BUNDLE])
    if miss:
        return miss
    panel = _panel(archive, madd(MOM_WINDOW[1], -1))
    return _wrap(momentum_report(panel))


HARNESSES = {
    "fx_carry_g10": fx_carry_g10,
    "fx_carry_em": fx_carry_em,
    "fx_momentum_g10": fx_momentum_g10,
}

THEORY_MAP = {
    "T-368": "fx_carry_g10",
    "T-431": "fx_carry_em",
    "T-478": "fx_momentum_g10",
}
