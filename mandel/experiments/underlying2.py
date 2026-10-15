"""
Underlying-library harnesses, batch 2: calendar effects, crypto and metals trend, ETF rotation and factor tilts.
==============================================================================================================

One function per library claim (theory id in the docstring), testing every pass criterion the claim states that
the archived data supports. ``_verdict`` enforces the rule: any implemented criterion failing -> not_supported;
all implemented criteria passing but some criterion not implemented -> inconclusive; supported only when every
stated criterion is implemented and passes. Prices are split- and dividend-adjusted closes when available
(``adjclose``), and a bar is used only if its ``available_at`` precedes the bundle's capture time.
"""

from __future__ import annotations

import bisect
import calendar
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

import numpy as np

from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying import turn_of_month, weekday_effect
from mandel.validation.backtest_eval import block_bootstrap_pvalue, deflated_sharpe_ratio, sharpe_ratio


# ------------------------------------------------------------------------ loading --

class PriceSeries(tuple):
    """``(days, closes)`` from ``load_series``; unpacks exactly like a plain pair. ``opens`` holds the opens on the same
    adjustment basis as the closes (open * adjclose / close), aligned with ``days``, or None when any bar lacks an open."""

    def __new__(cls, days, closes, opens=None):
        obj = super().__new__(cls, (days, closes))
        obj.opens = opens
        return obj


def load_series(archive, symbol: str, adjusted: bool = True):
    """(days, closes) with closes = adjclose when present; drops bars not yet available at capture. The returned pair
    also carries ``.opens`` (see PriceSeries) for harnesses that fill at the next open."""
    name = "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in symbol)
    entry = archive.get(name)
    cap = entry.created_at if entry else None
    by, op = {}, {}
    for r in archive.load(name):
        if cap and r.get("available_at") and r["available_at"] > cap:
            continue
        v = r["value"]
        d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        c = v.get("adjclose") if adjusted and v.get("adjclose") is not None else v["close"]
        by[d] = float(c)
        o, raw = v.get("open"), v.get("close")
        if o is not None and raw and float(o) > 0:
            op[d] = float(o) * float(c) / float(raw)
        else:
            op.pop(d, None)
    days = sorted(by)
    opens = np.array([op[d] for d in days]) if days and all(d in op for d in days) else None
    return PriceSeries(days, np.array([by[d] for d in days]), opens)


def monthly(days, closes):
    """Month-end closes: (months 'YYYY-MM', closes)."""
    last = {}
    for d, c in zip(days, closes):
        last[d[:7]] = c
    ms = sorted(last)
    return ms, np.array([last[m] for m in ms])


def weekly(days, closes, weekday: int = 6):
    """Closes on the last available day of each ISO week (crypto: Sunday)."""
    last = {}
    for d, c in zip(days, closes):
        y, w, _ = date.fromisoformat(d).isocalendar()
        last[(y, w)] = (d, c)
    ks = sorted(last)
    return [last[k][0] for k in ks], np.array([last[k][1] for k in ks])


# ------------------------------------------------------------------------ helpers --

def _mdd(r: np.ndarray) -> float:
    c = np.cumprod(1 + r); return float((c / np.maximum.accumulate(c) - 1).min())


def _sr(r: np.ndarray, ppy: int) -> float:
    return float(sharpe_ratio(r, ppy))


def _sharpe_diff_lower(a: np.ndarray, b: np.ndarray, ppy: int, block: int, n_boot: int = 2000, seed: int = 0, q: float = 0.025) -> tuple[float, float]:
    """(observed annualised Sharpe difference, lower q-quantile) by circular block bootstrap of paired periods."""
    rng = np.random.default_rng(seed); n = len(a); nb = math.ceil(n / block)
    obs = _sr(a, ppy) - _sr(b, ppy); out = np.empty(n_boot)
    for i in range(n_boot):
        idx = ((rng.integers(0, n, nb)[:, None] + np.arange(block)[None, :]).ravel()[:n]) % n
        out[i] = _sr(a[idx], ppy) - _sr(b[idx], ppy)
    return obs, float(np.quantile(out, q))


def _mean_ci(x: np.ndarray, block: int, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed); n = len(x); nb = math.ceil(n / block); m = np.empty(n_boot)
    for i in range(n_boot):
        idx = ((rng.integers(0, n, nb)[:, None] + np.arange(block)[None, :]).ravel()[:n]) % n
        m[i] = x[idx].mean()
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def _verdict(criteria: list[tuple[str, Optional[bool]]]) -> tuple[str, str]:
    """criteria: (name, True/False/None=not implemented)."""
    failed = [n for n, ok in criteria if ok is not None and not bool(ok)]      # numpy bools are not the False singleton
    missing = [n for n, ok in criteria if ok is None]
    if failed:
        return "not_supported", "failed: " + "; ".join(failed) + (f" (not implemented: {'; '.join(missing)})" if missing else "")
    if missing:
        return "inconclusive", "implemented criteria pass; not implemented: " + "; ".join(missing)
    return "supported", "all criteria pass"


def _halves(x: np.ndarray) -> list[float]:
    h = len(x) // 2
    return [float(x[:h].mean()), float(x[h:].mean())]


def _rf_per_period(start_days, bill_days, bill_vals, ppy: int) -> np.ndarray:
    """T-bill return per period known at the start of each period: the latest bill observation (annual %, e.g. FRED
    DTB3) dated on or before the period's start day, / 100 / ppy. Periods before the first observation use the first."""
    bd = list(bill_days); bv = [float(v) for v in bill_vals]
    out = np.empty(len(start_days))
    for i, d in enumerate(start_days):
        j = bisect.bisect_right(bd, d) - 1
        out[i] = bv[max(j, 0)] / 100 / ppy
    return out


def _last_weekday(month: str) -> str:
    """Last Monday-Friday of a 'YYYY-MM' month (ISO date)."""
    y, m = int(month[:4]), int(month[5:7])
    d = date(y, m, calendar.monthrange(y, m)[1])
    while d.weekday() > 4:
        d -= timedelta(days=1)
    return d.isoformat()


def _hac_t(d: np.ndarray, bw: int) -> float:
    """Mean / sqrt(Bartlett long-run variance / n): the studentization block_bootstrap_pvalue uses (bandwidth = block)."""
    n = d.size; x = d - d.mean()
    lrv = float(x @ x) / n
    for k in range(1, min(max(1, bw), n)):
        lrv += 2 * (1 - k / bw) * float(x[k:] @ x[:-k]) / n
    return float(d.mean() / math.sqrt(lrv / n)) if lrv > 0 else 0.0


# ----------------------------------------------------------------- calendar effects --

def tom_replication(series: dict[str, tuple[list, np.ndarray]], cost_bps: dict[str, float]) -> dict:
    """T-344: turn-of-month (-4..+3) on QQQ, IWM, TLT, GLD, BTC-USD; >= 3 of 5 with diff > 0, p < 0.05, both halves > 0,
    after charging one round trip per month spread over the 7 window days."""
    per, wins = {}, 0
    for sym, (days, c) in series.items():
        r = c[1:] / c[:-1] - 1
        rep = turn_of_month(days, c)
        adj = cost_bps.get(sym, 2.0) / 7.0
        ok = rep["verdict"] == "supported" and rep["difference_bps"] - adj > 0
        per[sym] = {"difference_bps": rep.get("difference_bps"), "net_of_cost_bps": (rep.get("difference_bps") or 0) - adj, "p": rep.get("p_value"), "halves_bps": rep.get("halves_bps"), "pass": bool(ok)}
        wins += ok
    v, why = _verdict([("at least 3 of 5 assets pass", wins >= 3)])
    return {"per_asset": per, "assets_passing": wins, "verdict": v,
            "reason": f"turn-of-month replicates on {wins}/5 assets (need 3): " + "; ".join(f"{s} {p['net_of_cost_bps']:+.1f} bps net, p={p['p']:.3f}" for s, p in per.items() if p['p'] is not None) + f" — {why}"}


def quarter_end_reversal(days, c, start: str = "2000-01-01", n_boot: int = 4000, seed: int = 0, rt_cost: float = 0.0002) -> dict:
    """T-346/T-439: IWM last trading day of quarter minus first trading day of next quarter, net of the controls' costs
    (8 round trips a year = 2 per quarter end, at the 1-3 bps midpoint ``rt_cost``), > 20 bps, bootstrap p < 0.05, both
    halves (2000-2012 / 2013-) positive, and the gross placebo (non-quarter month ends) not significant: two-sided p > 0.1."""
    r = {days[i]: c[i] / c[i - 1] - 1 for i in range(1, len(days)) if days[i] >= start}
    ds = sorted(r)
    by_month = defaultdict(list)
    for d in ds:
        by_month[d[:7]].append(d)
    ms = sorted(by_month)
    q, plc = [], []
    for a, b in zip(ms[:-1], ms[1:]):
        diff = r[by_month[a][-1]] - r[by_month[b][0]]
        (q if int(a[5:7]) in (3, 6, 9, 12) else plc).append((a, diff))
    cost = 2 * rt_cost
    qd = np.array([x[1] for x in q]) - cost; pd_ = np.array([x[1] for x in plc])
    rng = np.random.default_rng(seed)
    def boot(x):
        return np.array([rng.choice(x, x.size).mean() for _ in range(n_boot)])
    bq = boot(qd); p = float((np.sum(bq <= 0) + 1) / (n_boot + 1))
    bp = boot(pd_)
    pp = float(min(1.0, 2 * min((np.sum(bp <= 0) + 1) / (n_boot + 1), (np.sum(bp >= 0) + 1) / (n_boot + 1))))
    h1 = np.array([x[1] for x in q if x[0] < "2013"]) - cost; h2 = np.array([x[1] for x in q if x[0] >= "2013"]) - cost
    crit = [("mean > 20 bps net of costs", qd.mean() > 0.002), ("bootstrap p < 0.05", p < 0.05), ("both halves positive", h1.mean() > 0 and h2.mean() > 0), ("placebo not significant (two-sided p > 0.1)", pp > 0.1)]
    v, why = _verdict(crit)
    return {"n_quarters": int(qd.size), "mean_bps": float(qd.mean() * 1e4), "cost_bps_per_quarter": cost * 1e4, "p": p, "halves_bps": [float(h1.mean() * 1e4), float(h2.mean() * 1e4)], "placebo_mean_bps": float(pd_.mean() * 1e4), "placebo_p": pp,
            "verdict": v, "reason": f"IWM quarter-end minus next-day {qd.mean()*1e4:+.1f} bps net of {cost*1e4:.0f} bps costs over {qd.size} quarters (p={p:.3f}), halves {h1.mean()*1e4:+.1f}/{h2.mean()*1e4:+.1f}; placebo month ends {pd_.mean()*1e4:+.1f} bps (two-sided p={pp:.3f}) — {why}"}


def _trading_days_by_year_month(days):
    out = defaultdict(list)
    for i, d in enumerate(days):
        out[(int(d[:4]), int(d[5:7]))].append(i)
    return out


def santa_rally(gspc: tuple, spy: tuple, n_place: int = 2000, seed: int = 0) -> dict:
    """T-350: last 5 trading days of Dec + first 2 of Jan vs the average 7-trading-day window: excess > 1 pp with
    placement-bootstrap p < 0.05 on ^GSPC (1928-), both halves positive; the claim's subject SPY (1993-) also at least
    1 pp with both halves positive (the claim sentence puts the 1 pp bar on SPY; the pass's weaker 'positive on SPY'
    does not override it). The barometer clause concerns variants not run here and does not gate the window claim."""
    def per_year(days, c):
        ym = _trading_days_by_year_month(days); out = []
        lr = np.log(c)
        for y in range(int(days[0][:4]), int(days[-1][:4])):
            dec, jan = ym.get((y, 12)), ym.get((y + 1, 1))
            if not dec or not jan or len(dec) < 5 or len(jan) < 2:
                continue
            a, b = dec[-5] - 1, jan[1]
            if a < 0:
                continue
            out.append((y, lr[b] - lr[a]))
        return out
    def excess(days, c):
        py = per_year(days, c); lr = np.log(c)
        all7 = (lr[7:] - lr[:-7]).mean()
        return py, np.array([x[1] for x in py]) - all7, lr
    py, ex, lr = excess(*gspc)
    rng = np.random.default_rng(seed)
    obs = ex.mean(); n = len(lr) - 7
    null = np.array([np.mean([lr[k + 7] - lr[k] for k in rng.integers(0, n, len(py))]) - (lr[7:] - lr[:-7]).mean() for _ in range(n_place)])
    p = float((np.sum(null >= obs) + 1) / (n_place + 1))
    py_spy, ex_spy, _ = excess(spy[0], spy[1])
    h = _halves(ex); hs = _halves(ex_spy)
    crit = [("^GSPC excess > 1 pp", obs > 0.01), ("placement p < 0.05", p < 0.05), ("halves agree (positive)", h[0] > 0 and h[1] > 0),
            ("SPY excess >= 1 pp (1993-)", ex_spy.mean() >= 0.01), ("SPY halves positive", hs[0] > 0 and hs[1] > 0)]
    v, why = _verdict(crit)
    return {"n_years": len(py), "excess_pp": float(obs * 100), "p": p, "spy_n_years": len(py_spy), "spy_excess_pp": float(ex_spy.mean() * 100), "spy_halves_pp": [x * 100 for x in hs], "halves_pp": [x * 100 for x in h], "verdict": v,
            "reason": f"Santa window excess over the average 7-day window {obs*100:+.2f} pp on ^GSPC over {len(py)} years (placement p={p:.3f}), halves {h[0]*100:+.2f}/{h[1]*100:+.2f}; SPY {ex_spy.mean()*100:+.2f} pp over {len(py_spy)} years, halves {hs[0]*100:+.2f}/{hs[1]*100:+.2f} — {why}"}


def january_small_cap(iwm: tuple, spy: tuple, rut: tuple, gspc: tuple, n_place: int = 2000, seed: int = 0) -> dict:
    """T-351: small-minus-large from the close of the 6th-to-last Dec trading day to the 10th Jan trading day:
    ^RUT-^GSPC (1987-) mean > 1 pp, bootstrap p < 0.05, both halves positive, placement placebo p < 0.05 (placebo windows
    have each year's own trading-day length, 15 on a normal calendar); IWM-SPY (2000-) mean at least 1 pp, as claimed."""
    def spread_series(a, b):
        da, ca = a[0], a[1]; db, cb = b[0], b[1]
        common = sorted(set(da) & set(db)); ia = {d: i for i, d in enumerate(da)}; ib = {d: i for i, d in enumerate(db)}
        la = np.log(np.array([ca[ia[d]] for d in common])); lb = np.log(np.array([cb[ib[d]] for d in common]))
        return common, la - lb
    def per_year(days, s):
        ym = _trading_days_by_year_month(days); out, gaps = [], []
        for y in range(int(days[0][:4]), int(days[-1][:4])):
            dec, jan = ym.get((y, 12)), ym.get((y + 1, 1))
            if dec and jan and len(dec) >= 6 and len(jan) >= 10:
                out.append(s[jan[9]] - s[dec[-6]]); gaps.append(jan[9] - dec[-6])
        return np.array(out), np.array(gaps, dtype=int)
    d1, s1 = spread_series(rut, gspc); x, gaps = per_year(d1, s1)
    d2, s2 = spread_series(iwm, spy); xi, _ = per_year(d2, s2)
    rng = np.random.default_rng(seed)
    bs = np.array([rng.choice(x, x.size).mean() for _ in range(4000)]); p = float((np.sum(bs <= 0) + 1) / 4001)
    # placement placebo: one window per year at a random date, each of that year's own trading-day length
    null = np.empty(n_place)
    for i in range(n_place):
        k = rng.integers(0, len(s1) - gaps)
        null[i] = np.mean(s1[k + gaps] - s1[k])
    pp = float((np.sum(null >= x.mean()) + 1) / (n_place + 1))
    h = _halves(x)
    crit = [("^RUT-^GSPC mean > 1 pp", x.mean() > 0.01), ("bootstrap p < 0.05", p < 0.05), ("both halves positive", h[0] > 0 and h[1] > 0), ("placement placebo p < 0.05", pp < 0.05),
            ("IWM-SPY mean >= 1 pp (2000-)", None if xi.size == 0 else xi.mean() >= 0.01)]
    v, why = _verdict(crit)
    return {"n_years": int(x.size), "mean_pp": float(x.mean() * 100), "p": p, "placebo_p": pp, "placebo_window_days": sorted(set(gaps.tolist())), "halves_pp": [z * 100 for z in h],
            "iwm_spy_n_years": int(xi.size), "iwm_spy_mean_pp": float(xi.mean() * 100) if xi.size else None, "verdict": v,
            "reason": f"Russell minus S&P over the turn of the year {x.mean()*100:+.2f} pp over {x.size} years (p={p:.3f}, placebo p={pp:.3f}), halves {h[0]*100:+.2f}/{h[1]*100:+.2f}; IWM-SPY "
                      + (f"{xi.mean()*100:+.2f} pp over {xi.size} years" if xi.size else "n/a") + f" — {why}"}


def sell_in_may(gspc: tuple, spy: Optional[tuple], n_boot: int = 4000, seed: int = 0) -> dict:
    """T-352: Nov-Apr minus May-Oct mean monthly return > 50 bps with p < 0.05 on ^GSPC (1928-), SPY (1993-) difference at
    least 50 bps as the claim states (the pass's 'SPY > 0' is implied), 2002- diff > 0. p from resampling whole years
    (keeps the 12 months of a year together). ``spy=None`` skips the SPY arm (used by sell_in_may_v2)."""
    def by_year(days, c):
        ms, mc = monthly(days, c); r = mc[1:] / mc[:-1] - 1; ms = ms[1:]
        yrs = defaultdict(lambda: {"w": [], "s": []})
        for m, x in zip(ms, r):
            y, mo = int(m[:4]), int(m[5:7])
            key = y if mo >= 5 else y - 1               # season year: May(y)..Apr(y+1)
            (yrs[key]["s"] if 5 <= mo <= 10 else yrs[key]["w"]).append(x)
        return {y: (np.mean(v["w"]), np.mean(v["s"])) for y, v in yrs.items() if len(v["w"]) == 6 and len(v["s"]) == 6}
    g = by_year(*gspc); ys = sorted(g); d = np.array([g[y][0] - g[y][1] for y in ys])
    rng = np.random.default_rng(seed); bs = np.array([rng.choice(d, d.size).mean() for _ in range(n_boot)]); p = float((np.sum(bs <= 0) + 1) / (n_boot + 1))
    post = np.array([g[y][0] - g[y][1] for y in ys if y >= 2002])
    crit = [("^GSPC difference > 50 bps/month", d.mean() > 0.005), ("p < 0.05", p < 0.05), ("2002- difference > 0", post.mean() > 0)]
    out = {"n_years": int(d.size), "diff_bps_per_month": float(d.mean() * 1e4), "p": p, "post2002_diff_bps": float(post.mean() * 1e4), "first_year": ys[0]}
    spy_txt = ""
    if spy is not None:
        s = by_year(spy[0], spy[1]); ds = np.array([s[y][0] - s[y][1] for y in sorted(s)])
        crit.insert(2, ("SPY difference >= 50 bps/month (1993-)", ds.mean() >= 0.005))
        out["spy_diff_bps"] = float(ds.mean() * 1e4); spy_txt = f"; SPY {ds.mean()*1e4:+.0f}"
    v, why = _verdict(crit)
    return {**out, "verdict": v,
            "reason": f"Nov-Apr minus May-Oct {d.mean()*1e4:+.0f} bps/month on ^GSPC over {d.size} years from {ys[0]} (p={p:.3f}){spy_txt}; post-2002 {post.mean()*1e4:+.0f} — {why}"}


def _third_friday(y, m):
    d = date(y, m, 1); d += timedelta(days=(4 - d.weekday()) % 7); return d + timedelta(days=14)


def opex_week(days, c, n_arms: int = 3) -> dict:
    """T-353: SPY opex-week return (previous week's last close to the expiry-week close) minus other weeks > 20 bps,
    Bonferroni p < 0.05 (x3 arms), both halves positive. Weeks run Monday-Friday and close on their last trading day, so
    a holiday Friday neither drops the week nor merges two weeks; the opex week is the one containing the third Friday
    (expiry moves to the Thursday when that Friday is a holiday)."""
    wd, wc = weekly(days, c)
    r = wc[1:] / wc[:-1] - 1; ends = wd[1:]
    def has_third_friday(d):
        x = date.fromisoformat(d); fri = x + timedelta(days=4 - x.weekday())
        return fri == _third_friday(fri.year, fri.month)
    is_ox = np.array([has_third_friday(e) for e in ends])
    strat = np.where(is_ox, r, 0.0); other = np.where(~is_ox, r, 0.0) * (is_ox.sum() / (~is_ox).sum())
    p = min(1.0, block_bootstrap_pvalue(strat, other, n_boot=2000, block_len=4) * n_arms)
    d = r[is_ox].mean() - r[~is_ox].mean()
    h = len(r) // 2
    halves = [float(r[:h][is_ox[:h]].mean() - r[:h][~is_ox[:h]].mean()), float(r[h:][is_ox[h:]].mean() - r[h:][~is_ox[h:]].mean())]
    crit = [("excess > 20 bps", d > 0.002), ("Bonferroni p < 0.05", p < 0.05), ("both halves positive", all(x > 0 for x in halves))]
    v, why = _verdict(crit)
    return {"n_opex_weeks": int(is_ox.sum()), "excess_bps": float(d * 1e4), "p_bonferroni": float(p), "halves_bps": [x * 1e4 for x in halves], "verdict": v,
            "reason": f"SPY opex week {r[is_ox].mean()*1e4:+.1f} vs other weeks {r[~is_ox].mean()*1e4:+.1f} bps (excess {d*1e4:+.1f}, Bonferroni p={p:.3f}, halves {halves[0]*1e4:+.1f}/{halves[1]*1e4:+.1f}) — {why}"}


def btc_monday(days, c, rt_cost: float = 0.004) -> dict:
    """T-354: BTC Monday excess > 20 bps, Bonferroni (x7) p < 0.05, halves positive, and a Monday-only strategy net of
    0.4% per round trip has a higher Sharpe than buy-and-hold."""
    rep = weekday_effect(days, c)
    mon = rep["by_weekday"].get("Mon", {})
    r = c[1:] / c[:-1] - 1; wd = np.array([date.fromisoformat(d).weekday() for d in days[1:]])
    strat = np.where(wd == 0, r - rt_cost, 0.0)
    s_sr, bh_sr = _sr(strat, 365), _sr(r, 365)
    crit = [("Monday excess > 20 bps", mon.get("diff_bps", 0) > 20), ("Bonferroni p < 0.05", mon.get("p_two_sided_bonf", 1) < 0.05),
            ("halves agree", bool(mon.get("halves_agree"))), ("net Monday strategy Sharpe > buy-and-hold", s_sr > bh_sr)]
    v, why = _verdict(crit)
    return {"monday": mon, "strategy_sharpe": s_sr, "bh_sharpe": bh_sr, "verdict": v,
            "reason": f"BTC Monday {mon.get('diff_bps', float('nan')):+.1f} bps vs other days (Bonferroni p={mon.get('p_two_sided_bonf', float('nan')):.3f}); Monday-only net of 0.4% Sharpe {s_sr:.2f} vs buy-and-hold {bh_sr:.2f} — {why}"}


def gold_autumn(gld: tuple, gcf: Optional[tuple]) -> dict:
    """T-356: GLD Sep-Nov mean daily return minus other months > 5 bps/day, p < 0.05, halves positive, post-2013 > 0; GC=F
    (2000-) difference at least 5 bps/day as the claim states. ``gcf=None`` skips the GC=F arm (used by gold_autumn_v2)."""
    def diff(days, c, since=None):
        r = c[1:] / c[:-1] - 1; ds = days[1:]
        m = np.array([int(d[5:7]) in (9, 10, 11) for d in ds]); keep = np.array([since is None or d >= since for d in ds])
        r, m = r[keep], m[keep]
        return r, m, float(r[m].mean() - r[~m].mean())
    r, m, d = diff(*gld)
    strat = np.where(m, r, 0.0); other = np.where(~m, r, 0.0) * (m.sum() / (~m).sum())
    p = block_bootstrap_pvalue(strat, other, n_boot=2000, block_len=21)
    h = len(r) // 2
    halves = [float(r[:h][m[:h]].mean() - r[:h][~m[:h]].mean()), float(r[h:][m[h:]].mean() - r[h:][~m[h:]].mean())]
    _, _, post = diff(gld[0], gld[1], since="2013-01-01")
    crit = [("difference > 5 bps/day", d > 0.0005), ("p < 0.05", p < 0.05), ("both halves positive", all(x > 0 for x in halves)), ("post-2013 > 0", post > 0)]
    out = {"diff_bps": d * 1e4, "p": float(p), "halves_bps": [x * 1e4 for x in halves], "post2013_bps": post * 1e4}
    gcf_txt = ""
    if gcf is not None:
        _, _, dg = diff(gcf[0], gcf[1])
        crit.append(("GC=F difference >= 5 bps/day (2000-)", dg >= 0.0005))
        out["gcf_diff_bps"] = dg * 1e4; gcf_txt = f"; GC=F {dg*1e4:+.2f}"
    v, why = _verdict(crit)
    return {**out, "verdict": v,
            "reason": f"GLD Sep-Nov minus other months {d*1e4:+.2f} bps/day (p={p:.3f}), halves {halves[0]*1e4:+.2f}/{halves[1]*1e4:+.2f}, post-2013 {post*1e4:+.2f}{gcf_txt} — {why}"}


# --------------------------------------------------------------------- trend rules --

def _ma_pos(c: np.ndarray, fast: int, slow: int) -> np.ndarray:
    pos = np.zeros(len(c))
    cs = np.cumsum(np.concatenate([[0.0], c]))
    for i in range(slow - 1, len(c)):
        pos[i] = float((cs[i + 1] - cs[i + 1 - fast]) / fast > (cs[i + 1] - cs[i + 1 - slow]) / slow)
    return pos


def _apply(pos: np.ndarray, c: np.ndarray, cost_side: float, lag: int = 0) -> np.ndarray:
    """Long/flat returns on the return grid (r[i] = close i -> close i+1), switch cost on the position actually held.
    lag=0 holds pos[i] (signal through close i) over r[i]; lag=1 holds it from close i+1, over r[i+1]."""
    r = c[1:] / c[:-1] - 1; p = pos[:-1]
    if lag:
        p = np.concatenate([np.zeros(lag), pos[:-1 - lag]])
    ch = np.abs(np.diff(np.concatenate([[0.0], p])))
    return p * r - ch * cost_side


def golden_cross(btc: tuple, eth: tuple, cost_side: float = 0.0035) -> dict:
    """T-302: 50/200 long/flat on BTC and ETH (35 bps per side incl. slippage): drawdown reduction > 40% on both, Sharpe
    difference lower 95% bound > -0.2, DSR > 0.5 over the declared variants (50/200, 20/100, 100/300, 10/50). The 50/200
    rule and buy-and-hold are scored from the rule's own first valid position (return index 199); only the DSR variant
    set uses the common 300-day trim that the 100/300 variant needs."""
    variants = [(50, 200), (20, 100), (100, 300), (10, 50)]
    res, crit = {}, []
    for name, (days, c) in (("BTC", btc), ("ETH", eth)):
        R = {f: _apply(_ma_pos(c, *f), c, cost_side) for f in variants}
        g = R[(50, 200)][199:]; bh = (c[1:] / c[:-1] - 1)[199:]
        red = 1 - _mdd(g) / _mdd(bh)
        obs, lo = _sharpe_diff_lower(g, bh, 365, 30)
        dsr = deflated_sharpe_ratio(R[(50, 200)][300:], n_trials=len(variants), trial_sharpes=[sharpe_ratio(R[f][300:]) for f in variants])
        res[name] = {"start": days[200], "n_days": int(len(g)), "mdd": _mdd(g), "bh_mdd": _mdd(bh), "dd_reduction": red, "sharpe": _sr(g, 365), "bh_sharpe": _sr(bh, 365), "sharpe_diff_lower": lo, "dsr": float(dsr)}
        crit += [(f"{name} drawdown reduction > 40%", red > 0.40), (f"{name} Sharpe diff lower bound > -0.2", lo > -0.2), (f"{name} DSR > 0.5", dsr > 0.5)]
    v, why = _verdict(crit)
    return {**res, "n": min(x["n_days"] for x in res.values()), "verdict": v, "reason": "; ".join(f"{k}: MDD {x['mdd']*100:.0f}% vs {x['bh_mdd']*100:.0f}% (-{x['dd_reduction']*100:.0f}%), Sharpe {x['sharpe']:.2f} vs {x['bh_sharpe']:.2f} (lower {x['sharpe_diff_lower']:+.2f}), DSR {x['dsr']:.2f}" for k, x in res.items()) + f" — {why}"}


def _metals_run(a, b, lb: int, cost_side: float, bm: dict, start: Optional[str] = None, lbs=(6, 9, 12)) -> dict:
    """Inverse-vol (trailing 12-month) a/b pair, 12-1 style long/flat per leg vs the Huang-Li-Wang-Zhou historical-mean
    strategy on the same pair. Costs: cost_side times the weight switched on each leg (no cost in the first month).
    The benchmark's expanding mean of pair excess returns (over bm, monthly bill returns; {} = raw) starts at the window's
    first month (``start``, default the pair's first month); that month, where the benchmark has no history and would be
    forced flat, is dropped, so every scored month compares against a live benchmark. Returns the scored months and the
    strategy for each lookback in ``lbs`` (and ``lb``), the benchmark, the pair (buy-and-hold) and the bill return."""
    months, P = _aligned_monthly({"A": a, "B": b}); A, B = P["A"], P["B"]
    ra, rb = A[1:] / A[:-1] - 1, B[1:] / B[:-1] - 1; rf = np.array([bm.get(m, 0.0) for m in months[1:]])
    strats = {}
    for L in sorted(set(lbs) | {lb}):
        out, prev, pair = [], None, []
        for t in range(12, len(ra)):
            va, vb = ra[t - 12:t].std(), rb[t - 12:t].std(); wa = (1 / va) / (1 / va + 1 / vb); wb = 1 - wa
            # signal known at the start of month t: return from month-end t-L to t-1 (skips the most recent month)
            sa = float(A[t - 1] / A[t - L] - 1 > 0); sb = float(B[t - 1] / B[t - L] - 1 > 0)
            cost = 0.0 if prev is None else cost_side * (wa * abs(sa - prev[0]) + wb * abs(sb - prev[1]))
            out.append(wa * sa * ra[t] + wb * sb * rb[t] - cost); pair.append(wa * ra[t] + wb * rb[t]); prev = (sa, sb)
        strats[L] = np.array(out)
    pair = np.array(pair); rfm = rf[12:]; ms = months[13:]
    keep = np.array([start is None or m >= start for m in ms], dtype=bool)
    hm = _hist_mean_strategy((pair - rfm)[keep], pair[keep], 1)
    sl = slice(1, None)                                        # drop the window's first month (benchmark not yet live)
    kept = [m for m, k in zip(ms, keep) if k]
    return {"window_start": kept[0] if kept else None, "months": kept[sl], "strats": {L: v[keep][sl] for L, v in strats.items()},
            "hm": hm[sl], "pair": pair[keep][sl], "rf": rfm[keep][sl]}


def metals_tsmom(gld: tuple, slv: tuple, gcf: tuple, scf: tuple, cost_side: float = 0.0004, bill_days=None, bill_vals=None) -> dict:
    """T-312: GLD/SLV inverse-vol 12-1 TSMOM long/flat monthly vs the historical-mean long strategy on the same pair (the
    claim's Huang et al. null; scored only once the benchmark has history): difference > 0 with block-bootstrap 95% CI
    excluding 0 (block 12), drawdown reduction > 25% vs the pair held always (buy-and-hold), sign agreement with GC=F/SI=F
    over the same months, DSR > 0.5 over lookbacks (6-1, 9-1, 12-1), and a positive after-cost excess return over bills.
    Costs per switch (cost_side x weight switched). Without the T-bill series (bill_days/bill_vals) the benchmark uses raw
    returns and the excess-over-bills criterion is not implemented (verdict capped at inconclusive)."""
    have_bills = bill_days is not None and bill_vals is not None and len(bill_days) > 0
    bm = {d[:7]: v / 100 / 12 for d, v in zip(bill_days, bill_vals)} if have_bills else {}
    e = _metals_run(gld, slv, 12, cost_side, bm)
    s, hm, b, months = e["strats"][12], e["hm"], e["pair"], e["months"]
    d = s - hm; lo, hi = _mean_ci(d, 12)
    red = 1 - _mdd(s) / _mdd(b)
    f = _metals_run(gcf, scf, 12, cost_side, bm, start=e["window_start"])
    fm = set(months); fk = np.array([m in fm for m in f["months"]], dtype=bool)
    fd = (f["strats"][12] - f["hm"])[fk]
    dsr = deflated_sharpe_ratio(s, n_trials=3, trial_sharpes=[sharpe_ratio(e["strats"][L]) for L in (6, 9, 12)])
    ex = (s - e["rf"]).mean()
    crit = [("difference vs historical-mean > 0 with CI excluding 0", d.mean() > 0 and lo > 0), ("drawdown reduction > 25%", red > 0.25),
            ("sign agrees with GC=F/SI=F", None if fd.size == 0 else np.sign(fd.mean()) == np.sign(d.mean())), ("DSR > 0.5", dsr > 0.5),
            ("after-cost excess over bills > 0" if have_bills else "after-cost excess over bills > 0 (T-bill series not supplied)", ex > 0 if have_bills else None)]
    v, why = _verdict(crit)
    fdm = float(fd.mean() * 1e4) if fd.size else float("nan")
    return {"n_months": int(len(d)), "first_month": months[0] if months else None, "benchmark": "historical-mean strategy" + ("" if have_bills else " (raw returns; bills not supplied)"),
            "mean_diff_bps": float(d.mean() * 1e4), "ci_bps": [lo * 1e4, hi * 1e4], "dd_reduction": red, "futures_diff_bps": fdm, "futures_n_months": int(fd.size), "dsr": float(dsr),
            "excess_over_bills_bps": float(ex * 1e4) if have_bills else None, "verdict": v,
            "reason": f"metals TSMOM minus historical-mean strategy {d.mean()*1e4:+.1f} bps/month over {len(d)} months from {months[0] if months else 'n/a'} (95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}), drawdown {_mdd(s)*100:.0f}% vs buy-and-hold {_mdd(b)*100:.0f}% (-{red*100:.0f}%), futures {fdm:+.1f} over the same {fd.size} months, DSR {dsr:.2f}"
                      + (f", excess over bills {ex*1e4:+.1f} bps/month" if have_bills else "") + f" — {why}"}


def _crypto_weekly_pool(btc: tuple, eth: tuple, lb: int, cost_side: float, warmup: int = 26) -> tuple[list, np.ndarray, np.ndarray, int]:
    """Equal-weight BTC/ETH pool of the lb-week TSMOM long/flat rule and of the historical-mean strategy (long in week t
    when the expanding mean of the asset's weekly returns to t-1 is > 0), both charged cost_side per switch. Each asset's
    first ``warmup`` weeks are dropped from both legs before pooling, so the benchmark is never forced flat; the
    benchmark's first live week carries no entry cost. Returns (weeks, rule, benchmark, number of BTC-only weeks)."""
    legs = []
    for series in (btc, eth):
        wd, wc = weekly(series[0], series[1]); r = wc[1:] / wc[:-1] - 1
        pos = np.zeros(len(r))
        for t in range(lb, len(r)):
            pos[t] = float(wc[t] / wc[t - lb] - 1 > 0)
        s = pos * r - np.abs(np.diff(np.concatenate([[0.0], pos]))) * cost_side
        hp = np.array([float(t >= warmup and r[:t].mean() > 0) for t in range(len(r))])
        hc = np.abs(np.diff(np.concatenate([[0.0], hp])))
        if warmup < len(hc):
            hc[warmup] = 0.0
        h = hp * r - hc * cost_side
        k = wd[1:]
        legs.append(({k[t]: s[t] for t in range(warmup, len(r))}, {k[t]: h[t] for t in range(warmup, len(r))}))
    (sb, hb), (se, he) = legs
    ks = sorted(set(sb) | set(se))
    s = np.array([np.mean([x[k] for x in (sb, se) if k in x]) for k in ks]); h = np.array([np.mean([x[k] for x in (hb, he) if k in x]) for k in ks])
    return ks, s, h, sum(1 for k in ks if k not in se)


def crypto_weekly_tsmom(btc: tuple, eth: tuple, cost_side: float = 0.003) -> dict:
    """T-315: 1-week TSMOM long/flat on BTC and ETH (equal-weight pool): weekly difference vs the historical-mean long
    strategy (the claim's benchmark; each asset scored after its 26-week benchmark warm-up, both legs charged 30 bps per
    side per switch) > 0 with block bootstrap CI excluding 0 (block 8), 2019- difference > 0, DSR > 0.5 over lookbacks
    1, 2, 4 weeks."""
    ks, s, b, n_btc_only = _crypto_weekly_pool(btc, eth, 1, cost_side)
    d = s - b; lo, hi = _mean_ci(d, 8)
    post = np.array([x for k, x in zip(ks, d) if k >= "2019-01-01"])
    var = [_crypto_weekly_pool(btc, eth, lb, cost_side)[1] for lb in (1, 2, 4)]
    dsr = deflated_sharpe_ratio(s, n_trials=3, trial_sharpes=[sharpe_ratio(v) for v in var])
    crit = [("difference vs historical-mean > 0 with CI excluding 0", d.mean() > 0 and lo > 0), ("2019- difference > 0", post.mean() > 0), ("DSR > 0.5", dsr > 0.5)]
    v, why = _verdict(crit)
    return {"n_weeks": int(len(d)), "n_btc_only_weeks": int(n_btc_only), "first_week": ks[0] if ks else None, "mean_diff_bps": float(d.mean() * 1e4), "ci_bps": [lo * 1e4, hi * 1e4], "post2019_bps": float(post.mean() * 1e4), "dsr": float(dsr), "verdict": v,
            "reason": f"weekly TSMOM minus historical-mean strategy {d.mean()*1e4:+.1f} bps/week over {len(d)} weeks ({n_btc_only} BTC-only before ETH's warm-up ends; 95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}), 2019- {post.mean()*1e4:+.1f}, DSR {dsr:.2f} — {why}"}


def btc_reversal(days, c, rt_cost: float = 0.006, window: int = 60) -> dict:
    """T-320 (claim of NO tradable reversal): next-day return after a bottom-decile day (trailing 60-day decile) minus the
    unconditional mean, net of 0.6%. The claim holds unless the net difference's lower 95% bound (block 10) is > 0."""
    r = c[1:] / c[:-1] - 1; ds = days[1:]
    keep = [i for i in range(window, len(r) - 1) if ds[i] >= "2015-01-01" and r[i] <= np.quantile(r[i - window:i], 0.10)]
    nxt = np.array([r[i + 1] for i in keep]); mu = r[[i + 1 for i in range(window, len(r) - 1) if ds[i] >= "2015-01-01"]].mean()
    net = nxt - mu - rt_cost
    lo, hi = _mean_ci(net, 10)
    tradable = lo > 0
    return {"n_signals": len(keep), "gross_excess_bps": float((nxt.mean() - mu) * 1e4), "net_bps": float(net.mean() * 1e4), "ci_net_bps": [lo * 1e4, hi * 1e4],
            "verdict": "not_supported" if tradable else "supported",
            "reason": f"{len(keep)} bottom-decile days: next-day excess {(nxt.mean()-mu)*1e4:+.1f} bps gross, {net.mean()*1e4:+.1f} net of 0.6% (95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}) — " + ("a tradable reversal exists, the claim fails" if tradable else "no tradable reversal: the claim holds")}


# -------------------------------------------------------------- ETF rotation, tilts --

def _aligned_monthly(series: dict[str, tuple]) -> tuple[list, dict]:
    ms = {k: monthly(*v) for k, v in series.items()}
    common = sorted(set.intersection(*(set(m) for m, _ in ms.values())))
    out = {}
    for k, (m, c) in ms.items():
        idx = {x: i for i, x in enumerate(m)}
        out[k] = np.array([c[idx[x]] for x in common])
    return common, out


def gem(spy, efa, agg, bill_days, bill_vals, cost_switch: float = 0.0003) -> dict:
    """T-305: GEM (12-month) vs 60/40 SPY/AGG: Sharpe difference >= 0 with lower 95% bound > -0.15 (block 12), drawdown
    reduction > 25%, PBO < 0.5 across lookbacks 3..12. The ensemble-variance part is not implemented.
    Timing (controls: 'month-end close used next day'): the signal uses month-end closes and the trade fills at the close
    of the next trading day, so each holding period runs from one execution-day close to the next; GEM and the
    monthly-rebalanced 60/40 are both built on that execution-day grid from daily closes. Sharpe ratios (and the PBO's
    Sharpe ranks) use returns in excess of the T-bill return known at the signal date; drawdowns use raw returns.
    ``cost_switch`` is charged per switch (T-305: 3 bps per switch)."""
    series = {"SPY": spy, "EFA": efa, "AGG": agg}
    idx = {k: {d: i for i, d in enumerate(v[0])} for k, v in series.items()}
    common = sorted(set.intersection(*(set(v[0]) for v in series.values())))
    D = {k: np.array([v[1][idx[k][d]] for d in common]) for k, v in series.items()}
    last = {}
    for i, d in enumerate(common):
        last[d[:7]] = i
    months = [m for m in sorted(last) if last[m] + 1 < len(common)]      # a month-end signal needs a next trading day to fill
    me = np.array([last[m] for m in months], dtype=int)
    P = {k: v[me] for k, v in D.items()}                                 # month-end closes (signal)
    X = {k: v[me + 1] for k, v in D.items()}                             # next-trading-day closes (execution)
    bill_m = {}
    for d, v in zip(bill_days, bill_vals):
        bill_m[d[:7]] = v / 100
    rf = np.array([bill_m.get(m, np.nan) for m in months]); rf = np.where(np.isnan(rf), np.nanmean(rf), rf)
    R = {k: v[1:] / v[:-1] - 1 for k, v in X.items()}                   # R[k][t]: execution day after month-end t -> after t+1
    rf_p = rf[:-1] / 12                                                  # bill return for holding period t, known at month-end t
    def run(lb):
        out, prev = [], None
        for t in range(lb, len(months) - 1):
            ret = {k: P[k][t] / P[k][t - lb] - 1 for k in P}
            rf_lb = np.prod(1 + rf[t - lb:t] / 12) - 1
            pick = (max(("SPY", "EFA"), key=lambda k: ret[k]) if ret["SPY"] > rf_lb else "AGG")
            out.append(R[pick][t] - (cost_switch if prev and pick != prev else 0.0)); prev = pick
        return np.array(out)
    g = run(12); base = (0.6 * R["SPY"] + 0.4 * R["AGG"])[12:len(months) - 1]; rfg = rf_p[12:len(months) - 1]
    obs, lo = _sharpe_diff_lower(g - rfg, base - rfg, 12, 12)
    red = 1 - _mdd(g) / _mdd(base)
    L = min(len(run(lb)) for lb in range(3, 13))
    M = np.column_stack([run(lb)[-L:] - rf_p[len(months) - 1 - L:len(months) - 1] for lb in range(3, 13)])
    pbo = pbo_cscv(M, n_partitions=8)["pbo"]
    crit = [("Sharpe diff >= 0 with lower bound > -0.15", obs >= 0 and lo > -0.15), ("drawdown reduction > 25%", red > 0.25), ("PBO < 0.5", pbo < 0.5), ("ensemble lowers outcome variance", None)]
    v, why = _verdict(crit)
    sg, sb = _sr(g - rfg, 12), _sr(base - rfg, 12)
    return {"n_months": len(g), "first_month": months[12], "first_fill_day": common[me[12] + 1], "cost_per_switch_bps": cost_switch * 1e4, "sharpe": sg, "bench_sharpe": sb, "sharpe_diff": obs, "lower": lo, "mdd": _mdd(g), "bench_mdd": _mdd(base), "pbo": pbo, "verdict": v,
            "reason": f"GEM excess Sharpe {sg:.2f} vs 60/40 {sb:.2f} (diff {obs:+.2f}, lower {lo:+.2f}), MDD {_mdd(g)*100:.0f}% vs {_mdd(base)*100:.0f}%, PBO {pbo:.2f} over {len(g)} months (fills at the next day's close, {cost_switch*1e4:.0f} bps per switch) — {why}"}


SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]


def sector_rotation(sectors: dict[str, tuple], spy: tuple, bill_days, bill_vals, cost_side: float = 0.0004, n_perm: int = 1000, seed: int = 0) -> dict:
    """T-306: top-3 12-1 sector rotation, monthly alpha vs SPY (excess over bills): alpha > 0 with block-bootstrap CI
    excluding 0, above the 95th percentile of a random-top-3 permutation null, PBO < 0.5 over 4 lookbacks x 3 top-k,
    alpha positive with each sector left out and with each decade left out (decade of the month a return is earned).
    The permutation null tests rank information only: each random pick's gross return is charged the momentum
    strategy's own realised cost path, so the null does not also penalise random picks for their higher turnover."""
    months, P = _aligned_monthly({**sectors, "SPY": spy})
    bm = {d[:7]: v / 100 / 12 for d, v in zip(bill_days, bill_vals)}
    rf = np.array([bm.get(m, 0.0) for m in months])[1:]
    R = {k: v[1:] / v[:-1] - 1 for k, v in P.items()}
    names = [s for s in SECTORS if s in P]
    def run(lb, k, universe=names, rng=None):
        """(gross monthly return, cost) series; net = gross - cost."""
        gross, cost, prev = [], [], set()
        for t in range(lb, len(months) - 1):
            mom = {s: P[s][t - 1] / P[s][t - lb] - 1 for s in universe}
            top = set(rng.choice(universe, k, replace=False)) if rng is not None else set(sorted(universe, key=lambda s: -mom[s])[:k])
            turnover = len(top ^ prev) / (2 * k) if prev else 1.0
            gross.append(np.mean([R[s][t] for s in top])); cost.append(turnover * 2 * cost_side); prev = top
        return np.array(gross), np.array(cost)
    def net(lb, k, **kw):
        g_, c_ = run(lb, k, **kw); return g_ - c_
    def alpha(x, lb, mask=None):
        y = x - rf[lb:len(months) - 1]; m = R["SPY"][lb:len(months) - 1] - rf[lb:len(months) - 1]
        if mask is not None:
            y, m = y[mask], m[mask]
        A = np.column_stack([np.ones_like(m), m]); coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        return coef[0], y - coef[1] * m
    xg, xc = run(12, 3); x = xg - xc; a, resid = alpha(x, 12)
    lo, hi = _mean_ci(resid, 12)
    rng = np.random.default_rng(seed)
    null = np.array([alpha(run(12, 3, rng=rng)[0] - xc, 12)[0] for _ in range(n_perm)])
    loo = [alpha(net(12, 3, universe=[s for s in names if s != drop]), 12)[0] for drop in names]
    dec = np.array([int(months[t + 1][:3]) for t in range(12, len(months) - 1)])     # decade of the month each return is earned
    lodo = {f"{D}0s": float(alpha(x, 12, mask=dec != D)[0]) for D in sorted(set(dec.tolist())) if np.sum(dec != D) >= 24}
    grid = [(lb, k) for lb in (3, 6, 9, 12) for k in (1, 2, 3)]
    L = min(len(net(lb, k)) for lb, k in grid)
    pbo = pbo_cscv(np.column_stack([net(lb, k)[-L:] for lb, k in grid]), n_partitions=8)["pbo"]
    crit = [("alpha > 0 with CI excluding 0", a > 0 and lo > 0), ("alpha above 95th pct of permutation null", a > np.quantile(null, 0.95)), ("PBO < 0.5", pbo < 0.5), ("alpha > 0 leaving out each sector", all(z > 0 for z in loo)),
            ("alpha > 0 leaving out each decade", all(z > 0 for z in lodo.values()) if len(lodo) >= 2 else None)]
    v, why = _verdict(crit)
    return {"n_months": len(x), "first_month": months[12], "alpha_bps_month": float(a * 1e4), "ci_bps": [lo * 1e4, hi * 1e4], "null_q95_bps": float(np.quantile(null, 0.95) * 1e4), "pbo": pbo, "loo_min_bps": float(min(loo) * 1e4),
            "lodo_bps": {k: z * 1e4 for k, z in lodo.items()}, "verdict": v,
            "reason": f"sector top-3 alpha {a*1e4:+.1f} bps/month over {len(x)} months (95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}; cost-matched random-pick 95th pct {np.quantile(null,0.95)*1e4:+.1f}), PBO {pbo:.2f}, leave-one-sector-out min {min(loo)*1e4:+.1f}, leave-one-decade-out "
                      + "/".join(f"{k} {z*1e4:+.1f}" for k, z in lodo.items()) + f" — {why}"}


def svxy_regime(svxy: tuple, vix: dict, vix3m: dict, cost_switch: float = 0.001, test_from: str = "2018-01-01", opens=None) -> dict:
    """T-379: hold SVXY only when VIX3M/VIX > 1.05 (signal at close t, held t+1), 10 bps per switch. Test window 2018-:
    Sharpe > 0.5 with lower bound > 0, max drawdown < 50%, and Sharpe above always-long SVXY. SVIX arm not implemented.
    Point in time: Cboe's VIX/VIX3M close prints at 16:15 ET, after SVXY's 16:00 close, so the day-t signal fills at
    SVXY's next open (adjusted open = open x adjclose / close) and is held for day t+1's intraday leg and the following
    overnight leg; the switch cost is charged at that open. Opens come from ``opens``, a PriceSeries' ``.opens`` or a
    third tuple element; without them the fill falls back to the next close and the next-open criterion is not
    implemented (verdict capped at inconclusive)."""
    days, c = svxy[0], svxy[1]
    if opens is None:
        opens = getattr(svxy, "opens", None)
    if opens is None and len(svxy) > 2:
        opens = svxy[2]
    o = None if opens is None else np.asarray(opens, dtype=float)
    if o is not None and (o.shape != np.shape(c) or not np.all(np.isfinite(o)) or np.any(o <= 0)):
        o = None
    r = c[1:] / c[:-1] - 1; ds = days[1:]
    sig = np.array([float(d in vix and d in vix3m and vix3m[d] / vix[d] > 1.05) for d in days[:-1]])     # known after close t
    prev = np.concatenate([[0.0], sig[:-1]])
    if o is not None:
        on, intra = o[1:] / c[:-1] - 1, c[1:] / o[1:] - 1      # close t -> open t+1 (previous position), open t+1 -> close t+1 (new)
        s = (1 + prev * on) * (1 + sig * intra) - 1 - np.abs(sig - prev) * cost_switch
        fill = "next open"
    else:
        s = prev * r - np.abs(np.diff(np.concatenate([[0.0], prev]))) * cost_switch
        fill = "next close (opens not supplied)"
    m = np.array([d >= test_from for d in ds])
    st, bt = s[m], r[m]
    obs, lo = _sharpe_diff_lower(st, np.zeros_like(st), 252, 21)
    crit = [("test Sharpe > 0.5 with lower bound > 0", _sr(st, 252) > 0.5 and lo > 0), ("max drawdown < 50%", _mdd(st) > -0.5), ("Sharpe above always-long", _sr(st, 252) > _sr(bt, 252)), ("SVIX arm", None)]
    if o is None:
        crit.append(("signal filled at SVXY's next open (opens not supplied)", None))
    v, why = _verdict(crit)
    return {"n_test_days": int(m.sum()), "fill": fill, "sharpe": _sr(st, 252), "lower": lo, "mdd": _mdd(st), "always_sharpe": _sr(bt, 252), "always_mdd": _mdd(bt), "time_in_market": float(sig[m].mean()), "verdict": v,
            "reason": f"SVXY in contango only, 2018-, filled at the {fill}: Sharpe {_sr(st,252):.2f} (lower {lo:+.2f}), MDD {_mdd(st)*100:.0f}% vs always-long Sharpe {_sr(bt,252):.2f}, MDD {_mdd(bt)*100:.0f}% — {why}"}


def low_vol_tilt(usmv: tuple, spy: tuple, splv: Optional[tuple] = None, sphb: Optional[tuple] = None, start: str = "2011-11-01", end: str = "2026-09-30",
                 bill_days=None, bill_vals=None, window: int = 1260) -> dict:
    """T-384: USMV vs SPY over the claim window 2011-11..2026-09: lower 95% bound of the Sharpe difference > 0 (block 20)
    and positive in >= 3 of 4 rolling 5-year (1260-day) windows spaced evenly across the sample; SPLV-SPHB spread mean
    > 0 over the same window. Sharpe ratios use daily returns in excess of the T-bill rate known at t-1
    (bill_days/bill_vals, annual %); without them raw returns are used and the excess-return criterion is not implemented
    (verdict capped at inconclusive). ``splv``/``sphb`` None skips the spread arm (used by low_vol_v2)."""
    def align(a, b):
        da, ca = a[0], a[1]; db, cb = b[0], b[1]
        common = sorted(set(da) & set(db)); ia = {d: i for i, d in enumerate(da)}; ib = {d: i for i, d in enumerate(db)}
        A = np.array([ca[ia[d]] for d in common]); B = np.array([cb[ib[d]] for d in common])
        keep = np.array([start <= d <= end for d in common[1:]], dtype=bool)        # returns whose day lies in the window
        return [d for d, k in zip(common[1:], keep) if k], (A[1:] / A[:-1] - 1)[keep], (B[1:] / B[:-1] - 1)[keep], [d for d, k in zip(common[:-1], keep) if k]
    d, u, s, prev_days = align(usmv, spy)
    have_bills = bill_days is not None and bill_vals is not None and len(bill_days) > 0
    rf = _rf_per_period(prev_days, bill_days, bill_vals, 252) if have_bills else np.zeros(len(u))
    ue, se = u - rf, s - rf
    obs, lo = _sharpe_diff_lower(ue, se, 252, 20)
    n = len(ue)
    starts = np.linspace(0, n - window, 4).round().astype(int) if n >= window else []
    subs = [_sr(ue[i:i + window], 252) - _sr(se[i:i + window], 252) for i in starts]
    crit = [("Sharpe diff lower bound > 0", lo > 0), ("positive in >= 3 of 4 rolling 5-year windows", sum(x > 0 for x in subs) >= 3 if len(subs) == 4 else None)]
    if not have_bills:
        crit.append(("Sharpe on daily excess returns over T-bills (T-bill series not supplied)", None))
    out = {"n": int(n), "n_days": int(n), "sharpe_usmv": _sr(ue, 252), "sharpe_spy": _sr(se, 252), "diff": obs, "lower": lo, "excess_over_bills": bool(have_bills), "window_days": window, "subwindows": subs,
           "first_day": d[0] if d else None, "last_day": d[-1] if d else None}
    spread_txt = ""
    if splv is not None and sphb is not None:
        _, l, h, _ = align(splv, sphb)
        crit.append(("SPLV-SPHB mean > 0", (l - h).mean() > 0))
        out["splv_minus_sphb_bps_day"] = float((l - h).mean() * 1e4); spread_txt = f"; SPLV-SPHB {(l-h).mean()*1e4:+.2f} bps/day"
    v, why = _verdict(crit)
    return {**out, "verdict": v,
            "reason": f"USMV {'excess ' if have_bills else 'raw '}Sharpe {out['sharpe_usmv']:.2f} vs SPY {out['sharpe_spy']:.2f} over {out['first_day']}..{out['last_day']} ({n} days; diff {obs:+.2f}, lower {lo:+.2f}); rolling 5-year windows "
                      + "/".join(f"{x:+.2f}" for x in subs) + f"{spread_txt} — {why}"}


# ===================================================== verifier-corrected restatements =====
# Each v2 function tests the superseding theory's wording and pass rule; ids in the docstrings.

def _two_sided_sharpe_ci(a, b, ppy, block, seed=0):
    obs, lo = _sharpe_diff_lower(a, b, ppy, block, seed=seed, q=0.025)
    _, hi = _sharpe_diff_lower(a, b, ppy, block, seed=seed, q=0.975)
    return obs, lo, hi


def _hist_mean_strategy(excess: np.ndarray, raw: np.ndarray, min_hist: int) -> np.ndarray:
    """Huang-Li-Wang-Zhou historical-mean strategy: long in period t when the expanding mean of excess returns up to t-1 is > 0."""
    out = np.zeros(len(raw))
    for t in range(min_hist, len(raw)):
        out[t] = raw[t] if excess[:t].mean() > 0 else 0.0
    return out


def santa_v2(gspc, start_year: int = 1973, n_place: int = 2000, seed: int = 0) -> dict:
    """T-440: ^GSPC 1973-2026: Santa window excess over the mean 7-day window > 1 pp, placement p < 0.05, both halves positive.
    The barometer clause concerns variants not run here and does not gate the window claim."""
    days, c = gspc
    keep = [i for i, d in enumerate(days) if int(d[:4]) >= start_year - 1]
    days = [days[i] for i in keep]; c = c[keep]
    lr = np.log(c); ym = _trading_days_by_year_month(days); py = []
    for y in range(start_year, int(days[-1][:4])):
        dec, jan = ym.get((y, 12)), ym.get((y + 1, 1))
        if dec and jan and len(dec) >= 5 and len(jan) >= 2 and dec[-5] >= 1:
            py.append(lr[jan[1]] - lr[dec[-5] - 1])
    all7 = (lr[7:] - lr[:-7]).mean(); ex = np.array(py) - all7
    rng = np.random.default_rng(seed); n = len(lr) - 7
    null = np.array([np.mean([lr[k + 7] - lr[k] for k in rng.integers(0, n, len(py))]) - all7 for _ in range(n_place)])
    p = float((np.sum(null >= ex.mean()) + 1) / (n_place + 1)); h = _halves(ex)
    v, why = _verdict([("excess > 1 pp", ex.mean() > 0.01), ("placement p < 0.05", p < 0.05), ("both halves positive", h[0] > 0 and h[1] > 0)])
    return {"n_years": len(py), "excess_pp": float(ex.mean() * 100), "p": p, "halves_pp": [x * 100 for x in h], "verdict": v,
            "reason": f"post-publication ({start_year}-) Santa excess {ex.mean()*100:+.2f} pp over {len(py)} years (placement p={p:.3f}), halves {h[0]*100:+.2f}/{h[1]*100:+.2f} — {why}"}


def sell_in_may_v2(gspc) -> dict:
    """T-441: ^GSPC 1928-2026 Nov-Apr minus May-Oct > 50 bps/month with p < 0.05, and the difference > 0 over the claim's
    post-publication window November 2002-October 2026, computed directly from the monthly returns in that window (mean
    of Nov-Apr months minus mean of May-Oct months; an incomplete last month is dropped)."""
    rep = sell_in_may(gspc, None)
    ms, mc = monthly(gspc[0], gspc[1]); r = mc[1:] / mc[:-1] - 1; ms = ms[1:]
    if ms and gspc[0][-1] < _last_weekday(ms[-1]):
        ms, r = ms[:-1], r[:-1]                                   # the data stop before that month's last weekday
    sel = [(m, x) for m, x in zip(ms, r) if "2002-11" <= m <= "2026-10"]
    w = [x for m, x in sel if int(m[5:7]) in (11, 12, 1, 2, 3, 4)]; sm = [x for m, x in sel if 5 <= int(m[5:7]) <= 10]
    post = float(np.mean(w) - np.mean(sm)) if w and sm else None
    v, why = _verdict([("difference > 50 bps/month", rep["diff_bps_per_month"] > 50), ("p < 0.05", rep["p"] < 0.05), ("2002-11..2026-10 difference > 0", None if post is None else post > 0)])
    window = [sel[0][0], sel[-1][0]] if sel else None
    return {**rep, "post2002_diff_bps": None if post is None else post * 1e4, "post_window": window, "post_n_months": [len(w), len(sm)], "verdict": v,
            "reason": f"Nov-Apr minus May-Oct {rep['diff_bps_per_month']:+.0f} bps/month over {rep['n_years']} years (p={rep['p']:.3f}), "
                      + (f"{window[0]}..{window[1]} {post*1e4:+.0f} ({len(w)} winter / {len(sm)} summer months)" if post is not None else "post-2002 n/a") + f" — {why}"}


def btc_monday_v2(days, c) -> dict:
    """T-436: BTC Monday minus other days > 20 bps, p < 0.05 (two-sided, uncorrected as restated), both halves positive."""
    r = c[1:] / c[:-1] - 1; wd = np.array([date.fromisoformat(d).weekday() for d in days[1:]]); m = wd == 0
    strat = np.where(m, r, 0.0); other = np.where(~m, r, 0.0) * (m.sum() / (~m).sum())
    p = float(min(1.0, 2 * min(block_bootstrap_pvalue(strat, other, n_boot=2000, block_len=14), block_bootstrap_pvalue(other, strat, n_boot=2000, block_len=14, seed=1))))
    d = r[m].mean() - r[~m].mean(); h = len(r) // 2
    halves = [float(r[:h][m[:h]].mean() - r[:h][~m[:h]].mean()), float(r[h:][m[h:]].mean() - r[h:][~m[h:]].mean())]
    v, why = _verdict([("excess > 20 bps", d > 0.002), ("p < 0.05", p < 0.05), ("both halves positive", all(x > 0 for x in halves))])
    return {"n_days": int(len(r)), "excess_bps": d * 1e4, "p": p, "halves_bps": [x * 1e4 for x in halves], "verdict": v,
            "reason": f"BTC Monday {d*1e4:+.1f} bps vs other days (p={p:.3f}), halves {halves[0]*1e4:+.1f}/{halves[1]*1e4:+.1f} — {why}"}


def gold_autumn_v2(gld) -> dict:
    """T-437: GLD 2011-2026 Sep-Nov minus other months > 5 bps/day, p < 0.05, both halves positive (expected to fail)."""
    days, c = gld
    keep = [i for i, d in enumerate(days) if d >= "2010-12-31"]
    rep = gold_autumn(([days[i] for i in keep], c[keep]), None)
    v, why = _verdict([("difference > 5 bps/day", rep["diff_bps"] > 5), ("p < 0.05", rep["p"] < 0.05), ("both halves positive", all(x > 0 for x in rep["halves_bps"]))])
    return {**rep, "verdict": v, "reason": f"GLD 2011- Sep-Nov minus other months {rep['diff_bps']:+.2f} bps/day (p={rep['p']:.3f}), halves {rep['halves_bps'][0]:+.2f}/{rep['halves_bps'][1]:+.2f} — {why}"}


def opex_week_v2(days, c) -> dict:
    """T-438: as T-353 without the Bonferroni factor."""
    rep = opex_week(days, c, n_arms=1)
    return {**rep, "reason": rep["reason"].replace("Bonferroni p", "p")}


def _tom_null_pass(r: np.ndarray, tom: np.ndarray, adj: float, bw: int) -> bool:
    """The observed per-asset rule (turn_of_month + tom_replication) on one resampled series: at least 200 TOM and 200
    other days, studentized one-sided p < 0.05 for the paired TOM-vs-other series (Bartlett HAC t with bandwidth bw, the
    studentization turn_of_month's block bootstrap uses), net-of-cost difference > 0, both halves positive."""
    a, b = r[tom], r[~tom]
    if len(a) < 200 or len(b) < 200:
        return False
    paired = np.where(tom, r, 0.0) - np.where(~tom, r, 0.0) * (len(a) / len(b))
    h = len(r) // 2
    halves_ok = bool(r[:h][tom[:h]].mean() > r[:h][~tom[:h]].mean()) and bool(r[h:][tom[h:]].mean() > r[h:][~tom[h:]].mean())
    return _hac_t(paired, bw) > 1.6448536269514722 and (a.mean() - b.mean()) - adj > 0 and halves_ok


def tom_replication_v2(series, cost_bps, n_boot: int = 1000, seed: int = 0, block: int = 21) -> dict:
    """T-443: count of assets passing (diff > 0 net of cost, p < 0.05, halves > 0) >= 3, and a joint bootstrap p < 0.05
    for the count under the stated null: every asset on the union calendar of their trading days, each asset's TOM/non-TOM
    difference removed (TOM-day returns shifted by the non-TOM minus TOM mean), one set of 21-day circular calendar
    blocks per replicate shared by all assets (each asset takes its (return, TOM flag) on the drawn dates where it
    trades), which keeps the cross-asset correlation, and each asset's pass recomputed with the observed rule
    (_tom_null_pass). p = (#{null count >= k} + 1) / (n_boot + 1)."""
    base = tom_replication(series, cost_bps)
    k = base["assets_passing"]
    prepared = {}
    for s, (days, c) in series.items():
        r = c[1:] / c[:-1] - 1; ds = days[1:]; pos = {}
        for i, d in enumerate(ds):
            pos.setdefault(d[:7], []).append(i)
        tom = np.zeros(len(r), bool)
        for idxs in pos.values():
            tom[idxs[:3]] = True; tom[idxs[-4:]] = True
        r0 = r - (r[tom].mean() - r[~tom].mean()) * tom
        prepared[s] = (ds, r0, tom, cost_bps.get(s, 2.0) / 7.0 / 1e4)
    union = sorted(set().union(*(set(p[0]) for p in prepared.values())))
    U = len(union); at = {d: i for i, d in enumerate(union)}
    aligned = {}
    for s, (ds, r0, tom, adj) in prepared.items():
        ru = np.full(U, np.nan); tu = np.zeros(U, bool); ii = np.array([at[d] for d in ds], dtype=int)
        ru[ii] = r0; tu[ii] = tom
        aligned[s] = (ru, tu, adj)
    rng = np.random.default_rng(seed); nb = math.ceil(U / block); null = np.empty(n_boot, dtype=int)
    for j in range(n_boot):
        idx = ((rng.integers(0, U, nb)[:, None] + np.arange(block)[None, :]).ravel()[:U]) % U     # shared calendar blocks
        cnt = 0
        for ru, tu, adj in aligned.values():
            x = ru[idx]; f = tu[idx]; ok = ~np.isnan(x)
            cnt += _tom_null_pass(x[ok], f[ok], adj, block)
        null[j] = cnt
    p = float((np.sum(null >= k) + 1) / (n_boot + 1))
    v, why = _verdict([("at least 3 of 5 assets pass", k >= 3), ("joint p < 0.05 for the count", p < 0.05)])
    freq = {int(x): int(np.sum(null == x)) for x in sorted(set(null.tolist()))}
    return {**base, "joint_p": p, "null_count_freq": freq, "verdict": v,
            "reason": base["reason"].split(" — ")[0] + f"; joint p for {k} passes {p:.3f} (shared 21-day calendar blocks on demeaned series, {n_boot} draws) — {why}"}


def low_vol_v2(usmv, spy, bill_days=None, bill_vals=None) -> dict:
    """T-448: USMV vs SPY over 2011-11..2026-09, Sharpe difference on daily excess returns over T-bills (rate known at
    t-1): lower 95% bound > 0 over >= 3500 days; family-wide DSR not implemented. Without the T-bill series raw returns
    are used and the excess-return criterion is not implemented (verdict capped at inconclusive)."""
    rep = low_vol_tilt(usmv, spy, bill_days=bill_days, bill_vals=bill_vals)
    n = rep["n_days"]
    crit = [("Sharpe diff lower bound > 0", rep["lower"] > 0), (">= 3500 daily observations", n >= 3500), ("family-wide DSR", None)]
    if not rep["excess_over_bills"]:
        crit.append(("Sharpe on daily excess returns over T-bills (T-bill series not supplied)", None))
    v, why = _verdict(crit)
    return {**rep, "verdict": v, "reason": f"USMV {'excess' if rep['excess_over_bills'] else 'raw'} Sharpe {rep['sharpe_usmv']:.2f} vs SPY {rep['sharpe_spy']:.2f} over {n} days {rep['first_day']}..{rep['last_day']} (lower {rep['lower']:+.2f}) — {why}"}


def btc_reversal_v2(days, c, cost: float = 0.006, window: int = 250) -> dict:
    """T-469 (claim of a tradable reversal): next-day return after a day below the trailing-250-day 10th percentile minus the
    unconditional next-day mean: lower 95% bound > 0.6%, both halves > 0.6%; DSR not implemented (no declared grid)."""
    r = c[1:] / c[:-1] - 1; ds = days[1:]
    idx = [i for i in range(window, len(r) - 1) if ds[i] >= "2015-08-01"]
    sig = [i for i in idx if r[i] < np.quantile(r[i - window:i], 0.10)]
    mu = r[[i + 1 for i in idx]].mean(); x = np.array([r[i + 1] for i in sig]) - mu
    lo, hi = _mean_ci(x, 10); h = _halves(x)
    v, why = _verdict([("lower bound > 0.6%", lo > cost), ("both halves > 0.6%", h[0] > cost and h[1] > cost), ("DSR > 0.95", None)])
    return {"n_signals": len(sig), "excess_bps": float(x.mean() * 1e4), "ci_bps": [lo * 1e4, hi * 1e4], "halves_bps": [z * 1e4 for z in h], "verdict": v,
            "reason": f"{len(sig)} signals: next-day excess {x.mean()*1e4:+.1f} bps (95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}; needs > 60), halves {h[0]*1e4:+.1f}/{h[1]*1e4:+.1f} — {why}"}


def sector_rotation_v2(sectors, spy, bill_days, bill_vals, n_perm: int = 1000) -> dict:
    """T-475: T-306's criteria plus DSR > 0.95, window 2000-01 onward. The pass's PBO and DSR are both stated over the
    96-trial grid, which is not run here: both are not implemented (the 12-variant proxy PBO is reported as a
    diagnostic only), so the verdict is at best inconclusive."""
    rep = sector_rotation(sectors, spy, bill_days, bill_vals, n_perm=n_perm)
    crit = [("alpha > 0 with CI excluding 0", rep["alpha_bps_month"] > 0 and rep["ci_bps"][0] > 0), ("above permutation 95th pct", rep["alpha_bps_month"] > rep["null_q95_bps"]),
            ("PBO < 0.5 over the declared 96-trial grid", None), ("leave-one-out positive", rep["loo_min_bps"] > 0), ("DSR > 0.95 over the declared 96-trial grid", None)]
    v, why = _verdict(crit)
    return {**rep, "pbo_proxy_12_variants": rep["pbo"], "verdict": v, "reason": rep["reason"].split(" — ")[0].replace("PBO", "proxy PBO (12 variants, diagnostic)") + f" — {why}"}


def gem_v2(spy, efa, agg, bill_days, bill_vals) -> dict:
    """T-480: GEM Sharpe minus 60/40 > 0 with paired 95% interval excluding 0, PBO < 0.5 and DSR > 0.95 over the declared
    60-trial matrix (16 CSCV partitions). Costs: 3 bps per side per switch (6 bps a switch). The declared matrix is not
    run here: PBO and DSR are not implemented (the 10-lookback, 8-partition proxy PBO is reported as a diagnostic)."""
    rep = gem(spy, efa, agg, bill_days, bill_vals, cost_switch=0.0006)
    v, why = _verdict([("Sharpe diff > 0 with 95% CI excluding 0", rep["sharpe_diff"] > 0 and rep["lower"] > 0),
                       ("PBO < 0.5 over the declared 60-trial matrix (16 partitions)", None), ("DSR > 0.95 (n_trials = 60)", None)])
    return {**rep, "pbo_proxy_10_lookbacks": rep["pbo"], "verdict": v, "reason": rep["reason"].split(" — ")[0].replace("PBO", "proxy PBO (10 lookbacks, diagnostic)") + f" — {why}"}


def golden_cross_v2(btc, eth, cost_side: float = 0.0035, n_trials: int = 72) -> dict:
    """T-485: BTC 2015-04-: 50/200 Sharpe minus buy-and-hold > 0 with 95% interval excluding 0, DSR > 0.95 with the
    declared n_trials = 72, ETH point estimate > 0. Timing as the control states: SMA through close t, return from
    close t+1, so every variant holds its day-t signal over close t+1 -> t+2 and pays switch costs on that lagged
    position. The 50/200 test starts at the rule's own first held position (return index 200; BTC also >= 2015-04-01),
    not at the 100/300 variant's warm-up. Only 4 of the 72 trials are run: the DSR uses n_trials = 72 with the
    trial-Sharpe variance estimated from those 4 variants, each scored on its own valid window (index slow on, inside
    the claim window)."""
    variants = [(50, 200), (20, 100), (100, 300), (10, 50)]
    out = {}
    for name, (days, c) in (("BTC", btc), ("ETH", eth)):
        R = {f: _apply(_ma_pos(c, *f), c, cost_side, lag=1) for f in variants}; bh = c[1:] / c[:-1] - 1    # SMA through close t, return from close t+1
        ds = days[1:]; inwin = np.array([d >= "2015-04-01" for d in ds]) if name == "BTC" else np.ones(len(ds), bool)
        def own(f):
            mm = inwin.copy(); mm[:f[1]] = False; return mm             # first held position: signal at slow-1, held from return index slow
        m = own((50, 200))
        g = R[(50, 200)][m]; b = bh[m]
        obs, lo, hi = _two_sided_sharpe_ci(g, b, 365, 30)
        ts = [sharpe_ratio(R[f][own(f)]) for f in variants]
        dsr = deflated_sharpe_ratio(g, n_trials=n_trials, var_trials_sr=float(np.var(ts, ddof=1)))
        first = int(np.argmax(m)) if m.any() else None
        out[name] = {"diff": obs, "ci": [lo, hi], "dsr": float(dsr), "dsr_n_trials": n_trials, "start": ds[first] if first is not None else None, "n_days": int(m.sum())}
    v, why = _verdict([("BTC Sharpe diff > 0 with CI excluding 0", out["BTC"]["diff"] > 0 and out["BTC"]["ci"][0] > 0), ("BTC DSR > 0.95", out["BTC"]["dsr"] > 0.95), ("ETH diff > 0", out["ETH"]["diff"] > 0)])
    return {**out, "n": out["BTC"]["n_days"], "verdict": v, "reason": "SMA through close t, return from close t+1; " + "; ".join(f"{k} from {x['start']}: Sharpe diff {x['diff']:+.2f} (95% CI {x['ci'][0]:+.2f} to {x['ci'][1]:+.2f}), DSR {x['dsr']:.2f} (n_trials {n_trials}, variance of 4 run variants)" for k, x in out.items()) + f" — {why}"}


def crypto_weekly_v2(btc, eth, cost_side: float = 0.004, n_trials: int = 16) -> dict:
    """T-486: BTC+ETH equal weight, 1-week TSMOM minus the historical-mean strategy > 0 with 95% CI excluding 0, DSR > 0.95
    with the declared n_trials = 16, 2019- mean > 0. Costs 30 bps per side plus 10 bps slippage (0.4% per side) on both
    legs. Each asset's first 26 weeks (the benchmark's warm-up) are dropped from both legs before pooling; the weeks
    before ETH's warm-up ends are BTC-only and are counted in the report. Only lookbacks 1/2/4 of the 16 trials are run:
    the DSR uses n_trials = 16 with the trial-Sharpe variance estimated from those 3."""
    ks, s, h, n_btc_only = _crypto_weekly_pool(btc, eth, 1, cost_side)
    d = s - h
    lo, hi = _mean_ci(d, 8)
    ts = []
    for lb in (1, 2, 4):
        _, sl, hl, _ = _crypto_weekly_pool(btc, eth, lb, cost_side); ts.append(sharpe_ratio(sl - hl))
    dsr = deflated_sharpe_ratio(d, n_trials=n_trials, var_trials_sr=float(np.var(ts, ddof=1)))
    post = np.array([x for k, x in zip(ks, d) if k >= "2019-01-01"])
    v, why = _verdict([("mean d > 0 with CI excluding 0", d.mean() > 0 and lo > 0), ("DSR > 0.95", dsr > 0.95), ("2019- mean d > 0", post.mean() > 0)])
    return {"n_weeks": int(len(d)), "n_btc_only_weeks": int(n_btc_only), "first_week": ks[0] if ks else None, "cost_side_bps": cost_side * 1e4, "mean_bps": float(d.mean() * 1e4), "ci_bps": [lo * 1e4, hi * 1e4],
            "dsr": float(dsr), "dsr_n_trials": n_trials, "post2019_bps": float(post.mean() * 1e4), "verdict": v,
            "reason": f"weekly TSMOM minus historical-mean strategy {d.mean()*1e4:+.1f} bps/week over {len(d)} weeks ({n_btc_only} BTC-only; {cost_side*1e4:.0f} bps per side; 95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}), DSR {dsr:.2f} (n_trials {n_trials}), 2019- {post.mean()*1e4:+.1f} — {why}"}


def metals_v2(gld, slv, gcf, scf, bill_days, bill_vals, cost_side: float = 0.0004, n_trials: int = 24, start: str = "2007-05") -> dict:
    """T-487: 2007-05-: inverse-vol GLD/SLV 12-1 long/flat minus the historical-mean strategy on the same inverse-vol pair > 0
    with 95% CI excluding 0, DSR > 0.95 with the declared n_trials = 24, same sign on GC=F/SI=F. The benchmark's expanding
    mean starts at the window's first month and that month (no history, benchmark forced flat) is dropped, so d runs
    from the second window month; the futures check uses the same benchmark treatment over the same months. Costs per
    switch (cost_side x weight switched). Only lookbacks 6/9/12 of the 24 trials are run: the DSR uses n_trials = 24 with
    the trial-Sharpe variance estimated from those 3."""
    bm = {d[:7]: v / 100 / 12 for d, v in zip(bill_days, bill_vals)}
    e = _metals_run(gld, slv, 12, cost_side, bm, start=start)
    months, hm = e["months"], e["hm"]
    d = e["strats"][12] - hm
    lo, hi = _mean_ci(d, 12)
    ts = [sharpe_ratio(e["strats"][L] - hm) for L in (6, 9, 12)]
    dsr = deflated_sharpe_ratio(d, n_trials=n_trials, var_trials_sr=float(np.var(ts, ddof=1)))
    f = _metals_run(gcf, scf, 12, cost_side, bm, start=e["window_start"] or start)
    fm = set(months); fk = np.array([m in fm for m in f["months"]], dtype=bool)
    fd = (f["strats"][12] - f["hm"])[fk]
    v, why = _verdict([("mean d > 0 with CI excluding 0", d.mean() > 0 and lo > 0), ("DSR > 0.95", dsr > 0.95), ("futures same sign", None if fd.size == 0 else np.sign(fd.mean()) == np.sign(d.mean()))])
    fdm = float(fd.mean() * 1e4) if fd.size else float("nan")
    return {"n_months": int(len(d)), "first_month": months[0] if months else None, "mean_bps": float(d.mean() * 1e4), "ci_bps": [lo * 1e4, hi * 1e4], "dsr": float(dsr), "dsr_n_trials": n_trials,
            "futures_diff_bps": fdm, "futures_n_months": int(fd.size), "verdict": v,
            "reason": f"metals TSMOM minus historical-mean strategy {d.mean()*1e4:+.1f} bps/month over {len(d)} months from {months[0] if months else 'n/a'} (95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}), DSR {dsr:.2f} (n_trials {n_trials}), futures {fdm:+.1f} over the same {fd.size} months — {why}"}


def svxy_v2(svxy, vix, vix3m, cost_switch: float = 0.001, test_from: str = "2018-01-01", bill_days=None, bill_vals=None,
            claim_from: str = "2011-10-01", end: str = "2026-09-30") -> dict:
    """T-435: SVXY only after VIX3M/VIX > 1.05 (else SGOV) vs always SVXY: test-window Sharpe difference > 0 with p < 0.05,
    DSR > 0.95 with n_trials = 6 thresholds (1.00, 1.025, 1.05, 1.075, 1.10, 1.15). Timing as the procedure states:
    signal at close t, position from close t+1 (the return earned on close t+1 -> t+2), switch cost on the lagged
    position. Cash days earn the T-bill rate known at the start of the day (bill_days/bill_vals, annual %) as the SGOV
    proxy, and both Sharpe ratios (and their difference) are on daily excess returns over that rate, so crediting cash
    does not flatter the lower-volatility filtered leg; without the T-bill series cash earns 0, returns are raw and the
    SGOV criterion is not implemented (verdict capped at inconclusive). The DSR is on s - b, where the bill cancels.
    Both windows end at the claim's end (2026-09-30). min_n (2500) counts trading-day returns in the claim window
    2011-10..2026-09 (the 2018-2026 test window alone cannot reach it), reported as n."""
    days, c = svxy[0], svxy[1]; r = c[1:] / c[:-1] - 1; ds = days[1:]; m = np.array([test_from <= d <= end for d in ds])
    n_claim = int(sum(1 for d in ds if claim_from <= d <= end))
    have_bills = bill_days is not None and bill_vals is not None and len(bill_days) > 0
    rf = _rf_per_period(days[:-1], bill_days, bill_vals, 252) if have_bills else np.zeros(len(r))
    def strat(th):
        sig = np.array([float(d in vix and d in vix3m and vix3m[d] / vix[d] > th) for d in days[:-1]])    # VIX3M/VIX at close t
        pos = np.concatenate([[0.0], sig[:-1]])                       # held from close t+1: earns r[t+1]
        return (pos * r + (1 - pos) * rf - np.abs(np.diff(np.concatenate([[0.0], pos]))) * cost_switch)[m]
    s = strat(1.05); b = r[m]; rfm = rf[m]
    obs, lo = _sharpe_diff_lower(s - rfm, b - rfm, 252, 21, q=0.05)                 # Sharpe on excess returns: pos*(r - rf) - cost vs r - rf
    dsr = deflated_sharpe_ratio(s - b, n_trials=6, trial_sharpes=[sharpe_ratio(strat(th) - b) for th in (1.0, 1.025, 1.05, 1.075, 1.10, 1.15)])
    crit = [("Sharpe diff > 0 with one-sided p < 0.05", obs > 0 and lo > 0), ("DSR > 0.95", dsr > 0.95)]
    if not have_bills:
        crit.append(("cash leg earns the T-bill rate as SGOV proxy (T-bill series not supplied)", None))
    if n_claim < 2500:
        crit.append((f"claim-window sample >= min_n 2500 days ({n_claim})", None))
    v, why = _verdict(crit)
    return {"n": n_claim, "n_claim_window_days": n_claim, "n_test_days": int(m.sum()), "sharpe": _sr(s - rfm, 252), "always_sharpe": _sr(b - rfm, 252), "excess_over_bills": bool(have_bills), "sharpe_diff": obs, "lower90": lo, "dsr": float(dsr), "cash_leg": "T-bill" if have_bills else "zero (bills not supplied)", "strategy_mean_bps_day": float(s.mean() * 1e4), "verdict": v,
            "reason": f"SVXY contango filter (position from close t+1, cash at {'T-bill' if have_bills else '0'}) vs always, test {test_from}..{end} "
                      f"({int(m.sum())} days; claim window {n_claim} days vs min_n 2500): {'excess' if have_bills else 'raw'} Sharpe {_sr(s - rfm, 252):.2f} vs {_sr(b - rfm, 252):.2f}, "
                      f"diff {obs:+.2f} (one-sided 95% lower {lo:+.2f}), DSR {dsr:.2f} — {why}"}
