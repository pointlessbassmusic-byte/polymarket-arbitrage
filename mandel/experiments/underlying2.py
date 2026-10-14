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

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

import numpy as np

from mandel.experiments.overfit import pbo_cscv
from mandel.experiments.underlying import turn_of_month, weekday_effect
from mandel.validation.backtest_eval import block_bootstrap_pvalue, deflated_sharpe_ratio, sharpe_ratio


# ------------------------------------------------------------------------ loading --

def load_series(archive, symbol: str, adjusted: bool = True):
    """(days, closes) with closes = adjclose when present; drops bars not yet available at capture."""
    name = "daily-history-" + "".join(c if c.isalnum() or c in "-_." else "-" for c in symbol)
    entry = archive.get(name)
    cap = entry.created_at if entry else None
    by = {}
    for r in archive.load(name):
        if cap and r.get("available_at") and r["available_at"] > cap:
            continue
        v = r["value"]
        d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")
        c = v.get("adjclose") if adjusted and v.get("adjclose") is not None else v["close"]
        by[d] = float(c)
    days = sorted(by)
    return days, np.array([by[d] for d in days])


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


def quarter_end_reversal(days, c, start: str = "2000-01-01", n_boot: int = 4000, seed: int = 0) -> dict:
    """T-346: IWM last trading day of quarter minus first trading day of next quarter > 20 bps, bootstrap p < 0.05,
    both halves (2000-2012 / 2013-) positive, placebo (non-quarter month ends) p > 0.1."""
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
    qd = np.array([x[1] for x in q]); pd_ = np.array([x[1] for x in plc])
    rng = np.random.default_rng(seed)
    def p_pos(x):
        bs = np.array([rng.choice(x, x.size).mean() for _ in range(n_boot)]); return float((np.sum(bs <= 0) + 1) / (n_boot + 1))
    p, pp = p_pos(qd), p_pos(pd_)
    h1 = np.array([x[1] for x in q if x[0] < "2013"]); h2 = np.array([x[1] for x in q if x[0] >= "2013"])
    crit = [("mean > 20 bps", qd.mean() > 0.002), ("bootstrap p < 0.05", p < 0.05), ("both halves positive", h1.mean() > 0 and h2.mean() > 0), ("placebo p > 0.1", pp > 0.1)]
    v, why = _verdict(crit)
    return {"n_quarters": int(qd.size), "mean_bps": float(qd.mean() * 1e4), "p": p, "halves_bps": [float(h1.mean() * 1e4), float(h2.mean() * 1e4)], "placebo_mean_bps": float(pd_.mean() * 1e4), "placebo_p": pp,
            "verdict": v, "reason": f"IWM quarter-end minus next-day {qd.mean()*1e4:+.1f} bps over {qd.size} quarters (p={p:.3f}), halves {h1.mean()*1e4:+.1f}/{h2.mean()*1e4:+.1f}; placebo month ends {pd_.mean()*1e4:+.1f} bps (p={pp:.3f}) — {why}"}


def _trading_days_by_year_month(days):
    out = defaultdict(list)
    for i, d in enumerate(days):
        out[(int(d[:4]), int(d[5:7]))].append(i)
    return out


def santa_rally(gspc: tuple, spy: tuple, n_place: int = 2000, seed: int = 0) -> dict:
    """T-350: last 5 trading days of Dec + first 2 of Jan vs the average 7-trading-day window: excess > 1 pp with
    placement-bootstrap p < 0.05 on ^GSPC (1928-), positive on SPY, both halves agreeing. Barometer variants not tested."""
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
    _, ex_spy, _ = excess(*spy)
    h = _halves(ex)
    crit = [("^GSPC excess > 1 pp", obs > 0.01), ("placement p < 0.05", p < 0.05), ("SPY excess > 0", ex_spy.mean() > 0), ("halves agree (positive)", h[0] > 0 and h[1] > 0)]
    v, why = _verdict(crit)
    return {"n_years": len(py), "excess_pp": float(obs * 100), "p": p, "spy_excess_pp": float(ex_spy.mean() * 100), "halves_pp": [x * 100 for x in h], "verdict": v,
            "reason": f"Santa window excess over the average 7-day window {obs*100:+.2f} pp on ^GSPC over {len(py)} years (placement p={p:.3f}), SPY {ex_spy.mean()*100:+.2f} pp, halves {h[0]*100:+.2f}/{h[1]*100:+.2f} — {why}"}


def january_small_cap(iwm: tuple, spy: tuple, rut: tuple, gspc: tuple, n_place: int = 2000, seed: int = 0) -> dict:
    """T-351: small-minus-large from the close of the 6th-to-last Dec trading day to the 10th Jan trading day:
    ^RUT-^GSPC (1987-) mean > 1 pp, bootstrap p < 0.05, both halves positive, placement placebo p < 0.05; IWM-SPY reported."""
    def spread_series(a, b):
        da, ca = a; db, cb = b
        common = sorted(set(da) & set(db)); ia = {d: i for i, d in enumerate(da)}; ib = {d: i for i, d in enumerate(db)}
        la = np.log(np.array([ca[ia[d]] for d in common])); lb = np.log(np.array([cb[ib[d]] for d in common]))
        return common, la - lb
    def per_year(days, s):
        ym = _trading_days_by_year_month(days); out = []
        for y in range(int(days[0][:4]), int(days[-1][:4])):
            dec, jan = ym.get((y, 12)), ym.get((y + 1, 1))
            if dec and jan and len(dec) >= 6 and len(jan) >= 10:
                out.append(s[jan[9]] - s[dec[-6]])
        return np.array(out)
    d1, s1 = spread_series(rut, gspc); x = per_year(d1, s1)
    d2, s2 = spread_series(iwm, spy); xi = per_year(d2, s2)
    rng = np.random.default_rng(seed)
    bs = np.array([rng.choice(x, x.size).mean() for _ in range(4000)]); p = float((np.sum(bs <= 0) + 1) / 4001)
    L = 25; n = len(s1) - L
    null = np.array([np.mean([s1[k + L] - s1[k] for k in rng.integers(0, n, x.size)]) for _ in range(n_place)])
    pp = float((np.sum(null >= x.mean()) + 1) / (n_place + 1))
    h = _halves(x)
    crit = [("^RUT-^GSPC mean > 1 pp", x.mean() > 0.01), ("bootstrap p < 0.05", p < 0.05), ("both halves positive", h[0] > 0 and h[1] > 0), ("placement placebo p < 0.05", pp < 0.05)]
    v, why = _verdict(crit)
    return {"n_years": int(x.size), "mean_pp": float(x.mean() * 100), "p": p, "placebo_p": pp, "halves_pp": [z * 100 for z in h], "iwm_spy_mean_pp": float(xi.mean() * 100), "verdict": v,
            "reason": f"Russell minus S&P over the turn of the year {x.mean()*100:+.2f} pp over {x.size} years (p={p:.3f}, placebo p={pp:.3f}), halves {h[0]*100:+.2f}/{h[1]*100:+.2f}; IWM-SPY {xi.mean()*100:+.2f} pp — {why}"}


def sell_in_may(gspc: tuple, spy: tuple, n_boot: int = 4000, seed: int = 0) -> dict:
    """T-352: Nov-Apr minus May-Oct mean monthly return > 50 bps with p < 0.05 on ^GSPC (1928-), SPY diff > 0, 2002- diff > 0.
    p from resampling whole years (keeps the 12 months of a year together)."""
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
    s = by_year(*spy); ds = np.array([s[y][0] - s[y][1] for y in sorted(s)])
    post = np.array([g[y][0] - g[y][1] for y in ys if y >= 2002])
    crit = [("^GSPC difference > 50 bps/month", d.mean() > 0.005), ("p < 0.05", p < 0.05), ("SPY difference > 0", ds.mean() > 0), ("2002- difference > 0", post.mean() > 0)]
    v, why = _verdict(crit)
    return {"n_years": int(d.size), "diff_bps_per_month": float(d.mean() * 1e4), "p": p, "spy_diff_bps": float(ds.mean() * 1e4), "post2002_diff_bps": float(post.mean() * 1e4), "first_year": ys[0], "verdict": v,
            "reason": f"Nov-Apr minus May-Oct {d.mean()*1e4:+.0f} bps/month on ^GSPC over {d.size} years from {ys[0]} (p={p:.3f}); SPY {ds.mean()*1e4:+.0f}; post-2002 {post.mean()*1e4:+.0f} — {why}"}


def _third_friday(y, m):
    d = date(y, m, 1); d += timedelta(days=(4 - d.weekday()) % 7); return d + timedelta(days=14)


def opex_week(days, c, n_arms: int = 3) -> dict:
    """T-353: SPY Friday-to-third-Friday return in opex weeks minus other Friday-to-Friday weeks > 20 bps, Bonferroni p < 0.05
    (x3 arms), both halves positive."""
    wd, wc = [], []
    for d, x in zip(days, c):
        if date.fromisoformat(d).weekday() == 4:
            wd.append(d); wc.append(x)
    wc = np.array(wc); r = wc[1:] / wc[:-1] - 1; ends = wd[1:]
    tf = {_third_friday(int(d[:4]), int(d[5:7])).isoformat() for d in ends}
    is_ox = np.array([e in tf for e in ends])
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


def gold_autumn(gld: tuple, gcf: tuple) -> dict:
    """T-356: GLD Sep-Nov mean daily return minus other months > 5 bps/day, p < 0.05, halves positive, post-2013 > 0; GC=F reported."""
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
    _, _, post = diff(*gld, since="2013-01-01"); _, _, dg = diff(*gcf)
    crit = [("difference > 5 bps/day", d > 0.0005), ("p < 0.05", p < 0.05), ("both halves positive", all(x > 0 for x in halves)), ("post-2013 > 0", post > 0)]
    v, why = _verdict(crit)
    return {"diff_bps": d * 1e4, "p": float(p), "halves_bps": [x * 1e4 for x in halves], "post2013_bps": post * 1e4, "gcf_diff_bps": dg * 1e4, "verdict": v,
            "reason": f"GLD Sep-Nov minus other months {d*1e4:+.2f} bps/day (p={p:.3f}), halves {halves[0]*1e4:+.2f}/{halves[1]*1e4:+.2f}, post-2013 {post*1e4:+.2f}; GC=F {dg*1e4:+.2f} — {why}"}


# --------------------------------------------------------------------- trend rules --

def _ma_pos(c: np.ndarray, fast: int, slow: int) -> np.ndarray:
    pos = np.zeros(len(c))
    cs = np.cumsum(np.concatenate([[0.0], c]))
    for i in range(slow - 1, len(c)):
        pos[i] = float((cs[i + 1] - cs[i + 1 - fast]) / fast > (cs[i + 1] - cs[i + 1 - slow]) / slow)
    return pos


def _apply(pos: np.ndarray, c: np.ndarray, cost_side: float) -> np.ndarray:
    r = c[1:] / c[:-1] - 1; p = pos[:-1]
    ch = np.abs(np.diff(np.concatenate([[0.0], p])))
    return p * r - ch * cost_side


def golden_cross(btc: tuple, eth: tuple, cost_side: float = 0.0035) -> dict:
    """T-302: 50/200 long/flat on BTC and ETH (35 bps per side incl. slippage): drawdown reduction > 40% on both, Sharpe
    difference lower 95% bound > -0.2, DSR > 0.5 over the declared variants (50/200, 20/100, 100/300, 10/50)."""
    variants = [(50, 200), (20, 100), (100, 300), (10, 50)]
    res, crit = {}, []
    for name, (days, c) in (("BTC", btc), ("ETH", eth)):
        R = {f: _apply(_ma_pos(c, *f), c, cost_side)[300:] for f in variants}
        bh = (c[1:] / c[:-1] - 1)[300:]
        g = R[(50, 200)]
        red = 1 - _mdd(g) / _mdd(bh)
        obs, lo = _sharpe_diff_lower(g, bh, 365, 30)
        dsr = deflated_sharpe_ratio(g, n_trials=len(variants), trial_sharpes=[sharpe_ratio(R[f]) for f in variants])
        res[name] = {"mdd": _mdd(g), "bh_mdd": _mdd(bh), "dd_reduction": red, "sharpe": _sr(g, 365), "bh_sharpe": _sr(bh, 365), "sharpe_diff_lower": lo, "dsr": float(dsr)}
        crit += [(f"{name} drawdown reduction > 40%", red > 0.40), (f"{name} Sharpe diff lower bound > -0.2", lo > -0.2), (f"{name} DSR > 0.5", dsr > 0.5)]
    v, why = _verdict(crit)
    return {**res, "verdict": v, "reason": "; ".join(f"{k}: MDD {x['mdd']*100:.0f}% vs {x['bh_mdd']*100:.0f}% (-{x['dd_reduction']*100:.0f}%), Sharpe {x['sharpe']:.2f} vs {x['bh_sharpe']:.2f} (lower {x['sharpe_diff_lower']:+.2f}), DSR {x['dsr']:.2f}" for k, x in res.items()) + f" — {why}"}


def metals_tsmom(gld: tuple, slv: tuple, gcf: tuple, scf: tuple, cost_side: float = 0.0004) -> dict:
    """T-312: GLD/SLV inverse-vol 12-1 TSMOM long/flat monthly vs the same risk-parity portfolio always long: difference > 0
    with block-bootstrap 95% CI excluding 0 (block 12), drawdown reduction > 25%, sign agreement with GC=F/SI=F, DSR > 0.5
    over lookbacks (6-1, 9-1, 12-1)."""
    def run(a, b, lb):
        ma, ca = monthly(*a); mb, cb = monthly(*b)
        common = sorted(set(ma) & set(mb)); ia = {m: i for i, m in enumerate(ma)}; ib = {m: i for i, m in enumerate(mb)}
        A = np.array([ca[ia[m]] for m in common]); B = np.array([cb[ib[m]] for m in common])
        ra, rb = A[1:] / A[:-1] - 1, B[1:] / B[:-1] - 1
        strat, base = [], []
        for t in range(12, len(ra)):
            va, vb = ra[t - 12:t].std(), rb[t - 12:t].std()
            wa, wb = (1 / va) / (1 / va + 1 / vb), (1 / vb) / (1 / va + 1 / vb)
            # signal known at the start of month t: return from month-end t-lb to t-1 (skips the most recent month)
            sa = float(A[t - 1] / A[t - lb] - 1 > 0); sb = float(B[t - 1] / B[t - lb] - 1 > 0)
            strat.append(wa * sa * ra[t] + wb * sb * rb[t] - cost_side * 0.5); base.append(wa * ra[t] + wb * rb[t])
        return np.array(strat), np.array(base), common[13:]
    s, b, months = run(gld, slv, 12)
    d = s - b; lo, hi = _mean_ci(d, 12)
    red = 1 - _mdd(s) / _mdd(b)
    sf, bf, _ = run(gcf, scf, 12)
    var = {lb: run(gld, slv, lb)[0] for lb in (6, 9, 12)}
    dsr = deflated_sharpe_ratio(s, n_trials=3, trial_sharpes=[sharpe_ratio(v) for v in var.values()])
    crit = [("difference > 0 with CI excluding 0", d.mean() > 0 and lo > 0), ("drawdown reduction > 25%", red > 0.25),
            ("sign agrees with GC=F/SI=F", np.sign((sf - bf).mean()) == np.sign(d.mean())), ("DSR > 0.5", dsr > 0.5)]
    v, why = _verdict(crit)
    return {"n_months": int(len(d)), "first_month": months[0] if months else None, "mean_diff_bps": float(d.mean() * 1e4), "ci_bps": [lo * 1e4, hi * 1e4], "dd_reduction": red, "futures_diff_bps": float((sf - bf).mean() * 1e4), "dsr": float(dsr), "verdict": v,
            "reason": f"metals TSMOM minus always-long {d.mean()*1e4:+.1f} bps/month over {len(d)} months (95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}), drawdown {_mdd(s)*100:.0f}% vs {_mdd(b)*100:.0f}% (-{red*100:.0f}%), futures {(sf-bf).mean()*1e4:+.1f}, DSR {dsr:.2f} — {why}"}


def crypto_weekly_tsmom(btc: tuple, eth: tuple, cost_side: float = 0.003) -> dict:
    """T-315: 1-week TSMOM long/flat on BTC and ETH (equal-weight pool): weekly difference vs always-long > 0 with block
    bootstrap CI excluding 0 (block 8) after 30 bps per side, 2019- difference > 0, DSR > 0.5 over lookbacks 1, 2, 4 weeks."""
    def strat(series, lb):
        wd, wc = weekly(*series)
        r = wc[1:] / wc[:-1] - 1
        pos = np.zeros(len(r))
        for t in range(lb, len(r)):
            pos[t] = float(wc[t] / wc[t - lb] - 1 > 0)
        ch = np.abs(np.diff(np.concatenate([[0.0], pos])))
        return dict(zip(wd[1:], pos * r - ch * cost_side)), dict(zip(wd[1:], r))
    def pooled(lb):
        sb, bb = strat(btc, lb); se, be = strat(eth, lb)
        ks = sorted(set(sb) | set(se))
        s = np.array([np.mean([x[k] for x in (sb, se) if k in x]) for k in ks]); b = np.array([np.mean([x[k] for x in (bb, be) if k in x]) for k in ks])
        return ks, s, b
    ks, s, b = pooled(1)
    d = s - b; lo, hi = _mean_ci(d, 8)
    post = np.array([x for k, x in zip(ks, d) if k >= "2019-01-01"])
    var = [pooled(lb)[1] for lb in (1, 2, 4)]
    dsr = deflated_sharpe_ratio(s, n_trials=3, trial_sharpes=[sharpe_ratio(v) for v in var])
    crit = [("difference > 0 with CI excluding 0", d.mean() > 0 and lo > 0), ("2019- difference > 0", post.mean() > 0), ("DSR > 0.5", dsr > 0.5)]
    v, why = _verdict(crit)
    return {"n_weeks": int(len(d)), "mean_diff_bps": float(d.mean() * 1e4), "ci_bps": [lo * 1e4, hi * 1e4], "post2019_bps": float(post.mean() * 1e4), "dsr": float(dsr), "verdict": v,
            "reason": f"weekly TSMOM minus always-long {d.mean()*1e4:+.1f} bps/week over {len(d)} weeks (95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}), 2019- {post.mean()*1e4:+.1f}, DSR {dsr:.2f} — {why}"}


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
    reduction > 25%, PBO < 0.5 across lookbacks 3..12. The ensemble-variance part is not implemented."""
    months, P = _aligned_monthly({"SPY": spy, "EFA": efa, "AGG": agg})
    bill_m = {}
    for d, v in zip(bill_days, bill_vals):
        bill_m[d[:7]] = v / 100
    rf = np.array([bill_m.get(m, np.nan) for m in months]); rf = np.where(np.isnan(rf), np.nanmean(rf), rf)
    R = {k: v[1:] / v[:-1] - 1 for k, v in P.items()}
    def run(lb):
        out, prev = [], None
        for t in range(lb, len(months) - 1):
            ret = {k: P[k][t] / P[k][t - lb] - 1 for k in P}
            rf_lb = np.prod(1 + rf[t - lb:t] / 12) - 1
            pick = (max(("SPY", "EFA"), key=lambda k: ret[k]) if ret["SPY"] > rf_lb else "AGG")
            out.append(R[pick][t] - (cost_switch if prev and pick != prev else 0.0)); prev = pick
        return np.array(out)
    g = run(12); base = (0.6 * R["SPY"] + 0.4 * R["AGG"])[12:len(months) - 1]
    obs, lo = _sharpe_diff_lower(g, base, 12, 12)
    red = 1 - _mdd(g) / _mdd(base)
    L = min(len(run(lb)) for lb in range(3, 13))
    M = np.column_stack([run(lb)[-L:] for lb in range(3, 13)])
    pbo = pbo_cscv(M, n_partitions=8)["pbo"]
    crit = [("Sharpe diff >= 0 with lower bound > -0.15", obs >= 0 and lo > -0.15), ("drawdown reduction > 25%", red > 0.25), ("PBO < 0.5", pbo < 0.5), ("ensemble lowers outcome variance", None)]
    v, why = _verdict(crit)
    return {"n_months": len(g), "first_month": months[12], "sharpe": _sr(g, 12), "bench_sharpe": _sr(base, 12), "sharpe_diff": obs, "lower": lo, "mdd": _mdd(g), "bench_mdd": _mdd(base), "pbo": pbo, "verdict": v,
            "reason": f"GEM Sharpe {_sr(g,12):.2f} vs 60/40 {_sr(base,12):.2f} (diff {obs:+.2f}, lower {lo:+.2f}), MDD {_mdd(g)*100:.0f}% vs {_mdd(base)*100:.0f}%, PBO {pbo:.2f} over {len(g)} months — {why}"}


SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]


def sector_rotation(sectors: dict[str, tuple], spy: tuple, bill_days, bill_vals, cost_side: float = 0.0004, n_perm: int = 1000, seed: int = 0) -> dict:
    """T-306: top-3 12-1 sector rotation, monthly alpha vs SPY (excess over bills): alpha > 0 with block-bootstrap CI
    excluding 0, above the 95th percentile of a random-top-3 permutation null, PBO < 0.5 over 4 lookbacks x 3 top-k,
    alpha positive with each sector left out."""
    months, P = _aligned_monthly({**sectors, "SPY": spy})
    bm = {d[:7]: v / 100 / 12 for d, v in zip(bill_days, bill_vals)}
    rf = np.array([bm.get(m, 0.0) for m in months])[1:]
    R = {k: v[1:] / v[:-1] - 1 for k, v in P.items()}
    names = [s for s in SECTORS if s in P]
    def run(lb, k, universe=names, rng=None):
        out, prev = [], set()
        for t in range(lb, len(months) - 1):
            mom = {s: P[s][t - 1] / P[s][t - lb] - 1 for s in universe}
            top = set(rng.choice(universe, k, replace=False)) if rng is not None else set(sorted(universe, key=lambda s: -mom[s])[:k])
            turnover = len(top ^ prev) / (2 * k) if prev else 1.0
            out.append(np.mean([R[s][t] for s in top]) - turnover * 2 * cost_side); prev = top
        return np.array(out)
    def alpha(x, lb):
        y = x - rf[lb:len(months) - 1]; m = R["SPY"][lb:len(months) - 1] - rf[lb:len(months) - 1]
        A = np.column_stack([np.ones_like(m), m]); coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        return coef[0], y - coef[1] * m
    x = run(12, 3); a, resid = alpha(x, 12)
    lo, hi = _mean_ci(resid, 12)
    rng = np.random.default_rng(seed)
    null = np.array([alpha(run(12, 3, rng=rng), 12)[0] for _ in range(n_perm)])
    loo = [alpha(run(12, 3, universe=[s for s in names if s != drop]), 12)[0] for drop in names]
    grid = [(lb, k) for lb in (3, 6, 9, 12) for k in (1, 2, 3)]
    L = min(len(run(lb, k)) for lb, k in grid)
    pbo = pbo_cscv(np.column_stack([run(lb, k)[-L:] for lb, k in grid]), n_partitions=8)["pbo"]
    crit = [("alpha > 0 with CI excluding 0", a > 0 and lo > 0), ("alpha above 95th pct of permutation null", a > np.quantile(null, 0.95)), ("PBO < 0.5", pbo < 0.5), ("alpha > 0 leaving out each sector", all(z > 0 for z in loo))]
    v, why = _verdict(crit)
    return {"n_months": len(x), "first_month": months[12], "alpha_bps_month": float(a * 1e4), "ci_bps": [lo * 1e4, hi * 1e4], "null_q95_bps": float(np.quantile(null, 0.95) * 1e4), "pbo": pbo, "loo_min_bps": float(min(loo) * 1e4), "verdict": v,
            "reason": f"sector top-3 alpha {a*1e4:+.1f} bps/month over {len(x)} months (95% CI {lo*1e4:+.1f} to {hi*1e4:+.1f}; random-pick 95th pct {np.quantile(null,0.95)*1e4:+.1f}), PBO {pbo:.2f}, leave-one-out min {min(loo)*1e4:+.1f} — {why}"}


def svxy_regime(svxy: tuple, vix: dict, vix3m: dict, cost_switch: float = 0.001, test_from: str = "2018-01-01") -> dict:
    """T-379: hold SVXY only when VIX3M/VIX > 1.05 (signal at close t, held t+1), 10 bps per switch. Test window 2018-:
    Sharpe > 0.5 with lower bound > 0, max drawdown < 50%, and Sharpe above always-long SVXY. SVIX arm not implemented."""
    days, c = svxy
    r = c[1:] / c[:-1] - 1; ds = days[1:]
    sig = np.array([float(d in vix and d in vix3m and vix3m[d] / vix[d] > 1.05) for d in days[:-1]])
    ch = np.abs(np.diff(np.concatenate([[0.0], sig])))
    s = sig * r - ch * cost_switch
    m = np.array([d >= test_from for d in ds])
    st, bt = s[m], r[m]
    obs, lo = _sharpe_diff_lower(st, np.zeros_like(st), 252, 21)
    crit = [("test Sharpe > 0.5 with lower bound > 0", _sr(st, 252) > 0.5 and lo > 0), ("max drawdown < 50%", _mdd(st) > -0.5), ("Sharpe above always-long", _sr(st, 252) > _sr(bt, 252)), ("SVIX arm", None)]
    v, why = _verdict(crit)
    return {"n_test_days": int(m.sum()), "sharpe": _sr(st, 252), "lower": lo, "mdd": _mdd(st), "always_sharpe": _sr(bt, 252), "always_mdd": _mdd(bt), "time_in_market": float(sig[-len(r):][m].mean()), "verdict": v,
            "reason": f"SVXY in contango only, 2018-: Sharpe {_sr(st,252):.2f} (lower {lo:+.2f}), MDD {_mdd(st)*100:.0f}% vs always-long Sharpe {_sr(bt,252):.2f}, MDD {_mdd(bt)*100:.0f}% — {why}"}


def low_vol_tilt(usmv: tuple, spy: tuple, splv: tuple, sphb: tuple) -> dict:
    """T-384: USMV vs SPY (2011-11-): lower 95% bound of the Sharpe difference > 0 (block 20) and positive in >= 3 of 4
    sub-windows; SPLV-SPHB spread mean > 0."""
    def align(a, b):
        da, ca = a; db, cb = b
        common = sorted(set(da) & set(db)); ia = {d: i for i, d in enumerate(da)}; ib = {d: i for i, d in enumerate(db)}
        A = np.array([ca[ia[d]] for d in common]); B = np.array([cb[ib[d]] for d in common])
        return common, A[1:] / A[:-1] - 1, B[1:] / B[:-1] - 1
    d, u, s = align(usmv, spy)
    obs, lo = _sharpe_diff_lower(u, s, 252, 20)
    q = np.array_split(np.arange(len(u)), 4)
    subs = [_sr(u[i], 252) - _sr(s[i], 252) for i in q]
    _, l, h = align(splv, sphb)
    crit = [("Sharpe diff lower bound > 0", lo > 0), ("positive in >= 3 of 4 windows", sum(x > 0 for x in subs) >= 3), ("SPLV-SPHB mean > 0", (l - h).mean() > 0)]
    v, why = _verdict(crit)
    return {"sharpe_usmv": _sr(u, 252), "sharpe_spy": _sr(s, 252), "diff": obs, "lower": lo, "subwindows": subs, "splv_minus_sphb_bps_day": float((l - h).mean() * 1e4), "first_day": d[0], "verdict": v,
            "reason": f"USMV Sharpe {_sr(u,252):.2f} vs SPY {_sr(s,252):.2f} since {d[0]} (diff {obs:+.2f}, lower {lo:+.2f}); sub-windows " + "/".join(f"{x:+.2f}" for x in subs) + f"; SPLV-SPHB {(l-h).mean()*1e4:+.2f} bps/day — {why}"}
