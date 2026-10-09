"""Cross-asset lead-lag study: do US stocks, foreign stocks, rates, the
dollar, VIX and oil predict BTC, the memecoin basket and the perp
universe, and does BTC's overnight move predict the S&P 500?

Pre-registered as `cross-asset-crypto-leadlag` in hypotheses.yaml; the
success bar is written there. Everything here is pure Python so it runs
where the bots run.

Inputs (scratch directory, see --dir):
  FRED CSVs      SP500 NASDAQCOM NIKKEI225 DGS10 DGS2 DFII10 T10YIE
                 DTWEXBGS VIXCLS DCOILWTICO   (fredgraph.csv format)
  BTC hourly     Coinbase candles [ts, low, high, open, close, vol]
                 (btc_hourly_2015_2019.pkl in --dir, btc_hourly.pkl beside it)
  baskets        hl_daily.pkl (18 memecoins), hl_all_daily.pkl (all perps)

Conventions: returns are log returns; BTC is sampled at 16:00 and 09:00
New York time from the hourly bars; yields are in percentage points and
their changes are used raw (0.10 = 10 bp); VIX changes are in points.
Known publication lags: the broad dollar index (DTWEXBGS) and WTI
(DCOILWTICO) are released about a week late by their sources, so they
describe comovement but could not be traded on the same day.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pickle
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo

from . import stats as S
from .fedliq_study import read_fred

ET = ZoneInfo("America/New_York")
DAY = 86400

ERAS = (
    ("2015-19", dt.date(2015, 7, 20), dt.date(2019, 12, 31)),
    ("2020-21", dt.date(2020, 1, 1), dt.date(2021, 12, 31)),
    ("2022-23", dt.date(2022, 1, 1), dt.date(2023, 12, 31)),
    ("2024-26", dt.date(2024, 1, 1), dt.date(2026, 12, 31)),
)
LATEST_ERAS = ("2022-23", "2024-26")

PREDICTORS = (
    # key, label, series kind
    ("spx", "S&P 500 (close-close)", "ret"),
    ("ndx", "Nasdaq (close-close)", "ret"),
    ("nky", "Nikkei 225 (same day, closes before US open)", "ret"),
    ("d10y", "10y yield change (pct pts)", "diff"),
    ("d2y", "2y yield change", "diff"),
    ("dreal", "10y real yield change", "diff"),
    ("dbe", "10y breakeven change", "diff"),
    ("usd", "broad dollar (lagged release)", "ret"),
    ("dvix", "VIX change (points)", "diff"),
    ("oil", "WTI (lagged release)", "ret"),
    ("btc_lag", "BTC own lag (16:00-16:00 ET)", "ret"),
    ("btc_sess", "BTC US session (09:00-16:00 ET)", "ret"),
    ("btc_ovn", "BTC overnight into t (16:00 t-1 to 09:00 t)", "ret"),
)
TARGETS = (
    ("btc1", "BTC next 24h from 16:00 ET"),
    ("btc5", "BTC next 5 days from 16:00 ET"),
    ("memes1", "18-memecoin basket, next UTC day"),
    ("perps1", "all-perp basket, next UTC day"),
)
FRED_SERIES = {
    "spx": ("SP500", "ret"), "ndx": ("NASDAQCOM", "ret"), "nky": ("NIKKEI225", "ret"),
    "d10y": ("DGS10", "diff"), "d2y": ("DGS2", "diff"), "dreal": ("DFII10", "diff"),
    "dbe": ("T10YIE", "diff"), "usd": ("DTWEXBGS", "ret"), "dvix": ("VIXCLS", "diff"),
    "oil": ("DCOILWTICO", "ret"),
}


# ------------------------------------------------------------- data access

def load_hourly(paths) -> dict[int, tuple[float, float]]:
    """Merge Coinbase hourly candle lists into {ts: (open, close)}."""
    out: dict[int, tuple[float, float]] = {}
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        for row in pickle.load(p.open("rb")):
            ts = int(row[0])
            out[ts] = (float(row[3]), float(row[4]))
    return out


def price_at_et(hourly: dict, day: dt.date, hour: int) -> float | None:
    """Open of the hourly bar that starts at `hour`:00 New York time on
    `day`; the neighbouring bars' prices if that bar is missing."""
    ts = int(dt.datetime(day.year, day.month, day.day, hour, tzinfo=ET).timestamp())
    bar = hourly.get(ts)
    if bar:
        return bar[0]
    prev = hourly.get(ts - 3600)
    if prev:
        return prev[1]
    nxt = hourly.get(ts + 3600)
    if nxt:
        return nxt[0]
    return None


def basket_returns(cache: Path, min_coins: int) -> dict[dt.date, float]:
    """Equal-weight daily log return of every coin in a Hyperliquid daily
    cache, keyed by the UTC date the candle opened on."""
    if not cache.exists():
        return {}
    data = pickle.load(cache.open("rb"))
    per_day: dict[dt.date, list[float]] = {}
    for _sym, (_meta, candles) in data.items():
        prev = None
        for c in candles:
            d = dt.datetime.fromtimestamp(int(c.ts), dt.timezone.utc).date()
            if prev is not None and prev > 0 and c.close > 0:
                per_day.setdefault(d, []).append(math.log(c.close / prev))
            prev = c.close
    return {d: statistics.fmean(v) for d, v in per_day.items() if len(v) >= min_coins}


def _series_change(series: dict[dt.date, float], kind: str) -> dict[dt.date, float]:
    out = {}
    prev = None
    for d in sorted(series):
        v = series[d]
        if prev is not None:
            if kind == "ret":
                if prev > 0 and v > 0:
                    out[d] = math.log(v / prev)
            else:
                out[d] = v - prev
        prev = v
    return out


def build_rows(d: Path, hourly: dict, memes: dict, perps: dict) -> list[dict]:
    """One row per US business day (a day with an S&P or Nasdaq print)."""
    changes = {}
    for key, (sid, kind) in FRED_SERIES.items():
        p = d / f"{sid}.csv"
        changes[key] = _series_change(read_fred(p), kind) if p.exists() else {}
    days = sorted(set(changes["spx"]) | set(changes["ndx"]))
    rows = []
    for day in days:
        if day < ERAS[0][1]:
            continue
        p16 = price_at_et(hourly, day, 16)
        p9 = price_at_et(hourly, day, 9)
        p16_prev = price_at_et(hourly, day - dt.timedelta(days=1), 16)
        p16_next = price_at_et(hourly, day + dt.timedelta(days=1), 16)
        p16_5 = price_at_et(hourly, day + dt.timedelta(days=5), 16)
        if not (p16 and p9 and p16_prev and p16_next):
            continue
        row = {"day": day,
               "btc_lag": math.log(p16 / p16_prev),
               "btc_sess": math.log(p16 / p9),
               "btc_ovn": math.log(p9 / p16_prev),
               "btc1": math.log(p16_next / p16),
               "btc5": math.log(p16_5 / p16) if p16_5 else None}
        for key in FRED_SERIES:
            row[key] = changes[key].get(day)
        # baskets: the UTC day after the signal day (opens 3-4h after 16:00 ET)
        nd = day + dt.timedelta(days=1)
        row["memes1"] = memes.get(nd)
        row["perps1"] = perps.get(nd)
        # reverse direction: next business day's S&P and the BTC move known before its open
        rows.append(row)
    for i in range(len(rows) - 1):
        nxt = rows[i + 1]
        rows[i]["spx_next"] = nxt.get("spx")
        rows[i]["ndx_next"] = nxt.get("ndx")
        rows[i]["btc_ovn_next"] = nxt["btc_ovn"]
    return rows


# -------------------------------------------------------------- regression

def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting (tiny systems)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    scale = max(abs(v) for row in a for v in row) or 1.0
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[piv][c]) < 1e-12 * scale:
            raise ValueError("singular design")
        m[c], m[piv] = m[piv], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                if f:
                    for k in range(c, n + 1):
                        m[r][k] -= f * m[c][k]
    return [m[i][n] / m[i][i] for i in range(n)]


def _inv(a: list[list[float]]) -> list[list[float]]:
    n = len(a)
    cols = [_solve(a, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def ols(y: list[float], X: list[list[float]], nw_lags: int = 5) -> dict:
    """OLS with an intercept and Newey-West (Bartlett, `nw_lags`) t-stats.
    X rows exclude the intercept. Returns beta[0] = intercept."""
    n = len(y)
    k = len(X[0]) + 1
    Z = [[1.0] + list(r) for r in X]
    xtx = [[sum(Z[t][i] * Z[t][j] for t in range(n)) for j in range(k)] for i in range(k)]
    xty = [sum(Z[t][i] * y[t] for t in range(n)) for i in range(k)]
    beta = _solve(xtx, xty)
    e = [y[t] - sum(beta[i] * Z[t][i] for i in range(k)) for t in range(n)]
    # S = sum_l w_l (Gamma_l + Gamma_l')
    Sm = [[0.0] * k for _ in range(k)]
    for lag in range(0, nw_lags + 1):
        w = 1.0 - lag / (nw_lags + 1.0)
        for t in range(lag, n):
            et = e[t] * e[t - lag]
            for i in range(k):
                zi = Z[t][i] * et
                for j in range(k):
                    g = zi * Z[t - lag][j]
                    Sm[i][j] += w * g
                    if lag:
                        Sm[j][i] += w * g
    inv = _inv(xtx)
    cov = [[sum(inv[i][a] * Sm[a][b] * inv[b][j] for a in range(k) for b in range(k))
            for j in range(k)] for i in range(k)]
    se = [math.sqrt(max(cov[i][i], 0.0)) for i in range(k)]
    t = [beta[i] / se[i] if se[i] > 0 else 0.0 for i in range(k)]
    ybar = sum(y) / n
    sst = sum((v - ybar) ** 2 for v in y)
    r2 = 1.0 - sum(v * v for v in e) / sst if sst > 0 else 0.0
    return {"beta": beta, "t": t, "n": n, "r2": r2}


def corr(xs, ys) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def era_of(day: dt.date) -> str | None:
    for name, a, b in ERAS:
        if a <= day <= b:
            return name
    return None


def _pairs(rows, x: str, y: str, era: str | None = None):
    xs, ys = [], []
    for r in rows:
        if r.get(x) is None or r.get(y) is None:
            continue
        if era and era_of(r["day"]) != era:
            continue
        xs.append(r[x])
        ys.append(r[y])
    return xs, ys


def univariate(rows, x: str, y: str) -> dict:
    """Full-sample and per-era slope, NW t and n for y ~ x."""
    out = {}
    for era in (None,) + tuple(e[0] for e in ERAS):
        xs, ys = _pairs(rows, x, y, era)
        if len(xs) < 60:
            out[era or "all"] = None
            continue
        fit = ols(ys, [[v] for v in xs])
        out[era or "all"] = {"beta": fit["beta"][1], "t": fit["t"][1], "n": fit["n"],
                             "corr": corr(xs, ys)}
    return out


def candidate(res: dict) -> bool:
    """The pre-registered bar: |t| >= 2.5 full sample and the same sign
    with |t| >= 1.5 in each of the two latest eras."""
    full = res.get("all")
    if not full or abs(full["t"]) < 2.5:
        return False
    sign = 1 if full["t"] > 0 else -1
    for era in LATEST_ERAS:
        e = res.get(era)
        if not e or e["t"] * sign < 1.5:
            return False
    return True


def multivariate(rows, xs: tuple, y: str, era: str | None = None) -> dict | None:
    X, Y = [], []
    for r in rows:
        if r.get(y) is None or any(r.get(x) is None for x in xs):
            continue
        if era and era_of(r["day"]) != era:
            continue
        X.append([r[x] for x in xs])
        Y.append(r[y])
    if len(Y) < 10 * (len(xs) + 1):
        return None
    fit = ols(Y, X)
    return {"n": fit["n"], "r2": fit["r2"],
            "coef": {x: (fit["beta"][i + 1], fit["t"][i + 1]) for i, x in enumerate(xs)}}


# ------------------------------------------------------------ conditionals

def divergence(rows, threshold: float = 0.005, target: str = "btc1") -> dict:
    """Next-day target after (stocks up, BTC down), (stocks down, BTC up),
    (both up), (both down), by era. Stocks = S&P 500 close-to-close."""
    cats = {"stocks up, BTC down": lambda s, b: s > threshold and b < -threshold,
            "stocks down, BTC up": lambda s, b: s < -threshold and b > threshold,
            "both up": lambda s, b: s > threshold and b > threshold,
            "both down": lambda s, b: s < -threshold and b < -threshold}
    out = {}
    for name, f in cats.items():
        out[name] = {}
        for era in (None,) + tuple(e[0] for e in ERAS):
            vals = [r[target] for r in rows
                    if r.get("spx") is not None and r.get(target) is not None
                    and f(r["spx"], r["btc_lag"]) and (era is None or era_of(r["day"]) == era)]
            out[name][era or "all"] = _mean_t(vals)
    return out


def _mean_t(vals) -> dict | None:
    n = len(vals)
    if n < 8:
        return {"n": n, "mean": None, "t": None}
    m = statistics.fmean(vals)
    sd = statistics.pstdev(vals)
    return {"n": n, "mean": m, "t": m / (sd / math.sqrt(n)) if sd > 0 else 0.0}


def rolling_corr(rows, x: str, y: str = "btc_lag") -> list[tuple[str, float, int]]:
    """Correlation of y with x by half-year."""
    buckets: dict[str, tuple[list, list]] = {}
    for r in rows:
        if r.get(x) is None or r.get(y) is None:
            continue
        h = f"{r['day'].year}H{1 if r['day'].month <= 6 else 2}"
        b = buckets.setdefault(h, ([], []))
        b[0].append(r[x])
        b[1].append(r[y])
    return [(h, corr(*buckets[h]), len(buckets[h][0])) for h in sorted(buckets)]


# ------------------------------------------------------------ trading rules

def walk_forward(rows, xs: tuple, cost_rt: float, start_year: int = 2018,
                 target: str = "btc1", mode: str = "ols") -> dict:
    """Fit on every prior year, trade the next 24h of BTC on the sign of
    the prediction when it clears half the round-trip cost. mode='sign'
    follows the sign of the first predictor instead (no fit). Cost is
    charged per unit change of position."""
    pos_prev = 0.0
    pnl: list[float] = []
    by_year: dict[int, list[float]] = {}
    for i, r in enumerate(rows):
        if r["day"].year < start_year or r.get(target) is None or any(r.get(x) is None for x in xs):
            continue
        if mode == "sign":
            pred = r[xs[0]]
        else:
            train = [q for q in rows if q["day"].year < r["day"].year
                     and q.get(target) is not None and not any(q.get(x) is None for x in xs)]
            if len(train) < 250:
                continue
            fit = _fit_cache(train, xs, target, r["day"].year)
            pred = fit[0] + sum(fit[j + 1] * r[x] for j, x in enumerate(xs))
        pos = 1.0 if pred > cost_rt / 2 else (-1.0 if pred < -cost_rt / 2 else 0.0)
        ret = pos * r[target] - abs(pos - pos_prev) * cost_rt / 2
        pos_prev = pos
        pnl.append(ret)
        by_year.setdefault(r["day"].year, []).append(ret)
    return {"pnl": pnl, "by_year": {y: sum(v) for y, v in by_year.items()},
            "sharpe": S.sharpe(pnl) * math.sqrt(252) if len(pnl) > 2 else 0.0,
            "psr": S.psr(pnl) if len(pnl) > 2 else 0.0, "n": len(pnl)}


_FITS: dict = {}


def _fit_cache(train, xs, target, year):
    key = (xs, target, year)
    if key not in _FITS:
        fit = ols([q[target] for q in train], [[q[x] for x in xs] for q in train], nw_lags=0)
        _FITS[key] = fit["beta"]
    return _FITS[key]


# ------------------------------------------------------------------ report

def _unit(x: str) -> float:
    """Scale a coefficient to 'per 1% move' for returns and 'per 0.1 (10 bp
    or 0.1 VIX point)' for differences."""
    kind = "ret" if x.startswith("btc") else FRED_SERIES.get(x, ("", "ret"))[1]
    return 0.01 if kind == "ret" else 0.1


def fmt_t(v):
    return "   —  " if v is None else f"{v:+5.2f}"


def render(rows, trials: dict) -> str:
    out = [f"rows (US business days with BTC prints): {len(rows)}  "
           f"{rows[0]['day']} .. {rows[-1]['day']}", ""]
    # 1. contemporaneous correlation by era
    out.append("1. Contemporaneous correlation of BTC (16:00-16:00 ET) with each series, by era")
    hdr = f"{'series':44s}" + "".join(f"{e[0]:>9s}" for e in ERAS) + "      all"
    out.append(hdr)
    for key, label, _k in PREDICTORS[:10]:
        line = f"{label[:44]:44s}"
        for era in tuple(e[0] for e in ERAS) + (None,):
            xs, ys = _pairs(rows, key, "btc_lag", era)
            line += f"{corr(xs, ys):+9.2f}" if len(xs) >= 60 else "        —"
        out.append(line)
    # 2. lead-lag table
    out.append("")
    out.append("2. Lead-lag: Newey-West t of next-period target on today's predictor "
               "(full | 2015-19 | 2020-21 | 2022-23 | 2024-26); * = clears the pre-registered bar")
    for tkey, tlabel in TARGETS:
        out.append(f"   target: {tlabel}")
        for key, label, _k in PREDICTORS:
            res = trials["uni"][(key, tkey)]
            cells = [fmt_t(res[e]["t"] if res.get(e) else None)
                     for e in ("all",) + tuple(x[0] for x in ERAS)]
            star = " *" if candidate(res) else ""
            n = res["all"]["n"] if res.get("all") else 0
            out.append(f"     {label[:40]:40s} {' | '.join(cells)}  n={n}{star}")
    # 3. multivariate
    out.append("")
    out.append("3. Multivariate OLS, all predictors (coef per 1% move or 1 pt / 10 bp; NW t)")
    for tkey, tlabel in TARGETS:
        for era, fit in trials["multi"][tkey].items():
            if not fit:
                continue
            terms = ", ".join(f"{x} {c * _unit(x):+.4f} (t {t:+.1f})"
                              for x, (c, t) in fit["coef"].items() if abs(t) >= 1.5)
            out.append(f"   {tlabel[:28]:28s} {era:8s} n={fit['n']:5d} R2={fit['r2']:.3f}  |t|>=1.5: {terms or 'none'}")
    # 4. divergence
    out.append("")
    out.append("4. Divergence days (|move| > 0.5%): mean next-24h BTC return, t, n")
    for name, per in trials["div"].items():
        cells = []
        for era in ("all",) + tuple(x[0] for x in ERAS):
            s = per.get(era)
            cells.append(f"{s['mean']*100:+.2f}% (t {s['t']:+.1f}, n {s['n']})" if s and s["mean"] is not None else f"— (n {s['n'] if s else 0})")
        out.append(f"   {name:22s} " + " | ".join(cells))
    # 5. reverse
    out.append("")
    out.append("5. Reverse direction: next S&P close-to-close on BTC moves known before that session")
    for key, label in (("btc_ovn_next", "BTC 16:00 t -> 09:00 t+1 (pre-open)"),
                       ("btc_lag", "BTC 16:00 t-1 -> 16:00 t (known at close)"),
                       ("btc_sess", "BTC US session t")):
        res = trials["rev"][key]
        cells = [fmt_t(res[e]["t"] if res.get(e) else None) for e in ("all",) + tuple(x[0] for x in ERAS)]
        out.append(f"   {label:42s} {' | '.join(cells)}  (corr all {res['all']['corr']:+.2f})" if res.get("all") else f"   {label}: n/a")
    out.append("   (no S&P open series is available free, so the pre-open BTC move overlaps "
               "the overnight futures move; a positive t here is information, not a trade)")
    # 6. rolling correlation
    out.append("")
    out.append("6. Correlation of BTC with the S&P, Nasdaq, 10y change, dollar, VIX by half-year")
    rc = {k: dict((h, c) for h, c, n in rolling_corr(rows, k)) for k in ("spx", "ndx", "d10y", "usd", "dvix")}
    halves = sorted(set().union(*[set(v) for v in rc.values()]))
    out.append(f"   {'half':8s}" + "".join(f"{k:>8s}" for k in rc))
    for h in halves:
        out.append(f"   {h:8s}" + "".join(f"{rc[k].get(h, float('nan')):+8.2f}" if h in rc[k] else "       —" for k in rc))
    # 7. walk-forward rules
    out.append("")
    out.append("7. Walk-forward rules on BTC next-24h (fit on all prior years; cost per round trip)")
    for name, wf in trials["wf"].items():
        yrs = " ".join(f"{y}:{v*100:+.0f}%" for y, v in sorted(wf["by_year"].items()))
        out.append(f"   {name:40s} Sharpe {wf['sharpe']:+.2f}  PSR {wf['psr']:.2f}  n={wf['n']}")
        out.append(f"     {yrs}")
    out.append("")
    out.append(f"trials looked at: {trials['count']}   candidates clearing the bar: "
               f"{', '.join(trials['cands']) or 'none'}")
    if trials.get("dsr") is not None:
        out.append(f"best rule DSR at {trials['count']} trials: {trials['dsr']:.2f} "
                   f"(var of SR across sign rules {trials['var_sr']:.2e})")
    return "\n".join(out)


def run(rows) -> dict:
    trials: dict = {"uni": {}, "multi": {}, "div": {}, "rev": {}, "wf": {}, "count": 0, "cands": []}
    for key, _l, _k in PREDICTORS:
        for tkey, _t in TARGETS:
            res = univariate(rows, key, tkey)
            trials["uni"][(key, tkey)] = res
            trials["count"] += 1
            if candidate(res):
                trials["cands"].append(f"{key}->{tkey}")
    # btc_lag is btc_sess + btc_ovn exactly, and the 10y breakeven is
    # DGS10 - DFII10 by definition, so joint fits leave those two out
    xs_all = tuple(k for k, _l, _k in PREDICTORS if k not in ("btc_lag", "dbe"))
    for tkey, _t in TARGETS:
        trials["multi"][tkey] = {"all": multivariate(rows, xs_all, tkey)}
        for era, _a, _b in ERAS:
            trials["multi"][tkey][era] = multivariate(rows, xs_all, tkey, era)
        trials["count"] += 1
    trials["div"] = divergence(rows)
    trials["count"] += len(trials["div"])
    for key in ("btc_ovn_next", "btc_lag", "btc_sess"):
        trials["rev"][key] = univariate(rows, key, "spx_next")
        trials["count"] += 1
    # rules: each is a trial
    stocks = ("spx", "ndx")
    macro = ("d10y", "d2y", "dreal", "dvix")
    tradeable = ("spx", "ndx", "nky", "d10y", "d2y", "dreal", "dvix", "btc_sess", "btc_ovn")
    for name, xs, mode, cost in (("follow the S&P (sign), 8 bp", ("spx",), "sign", 0.0008),
                                 ("follow the Nasdaq (sign), 8 bp", ("ndx",), "sign", 0.0008),
                                 ("OLS stocks only, 8 bp", stocks, "ols", 0.0008),
                                 ("OLS rates+VIX only, 8 bp", macro, "ols", 0.0008),
                                 ("OLS all same-day-known, 8 bp", tradeable, "ols", 0.0008),
                                 ("OLS all same-day-known, 20 bp", tradeable, "ols", 0.0020)):
        trials["wf"][name] = walk_forward(rows, xs, cost, mode=mode)
        trials["count"] += 1
    # DSR of the best rule against the family of single-predictor sign rules
    srs = []
    for key in tradeable:
        wf = walk_forward(rows, (key,), 0.0008, mode="sign")
        if wf["n"] > 2:
            srs.append(S.sharpe(wf["pnl"]))
    best = max(trials["wf"].values(), key=lambda w: w["sharpe"])
    if len(srs) >= 2 and best["n"] > 2:
        var_sr = statistics.pvariance(srs)
        trials["var_sr"] = var_sr
        trials["dsr"] = S.dsr(best["pnl"], trials["count"], var_sr)
    return trials


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="xasset", help="directory with the FRED CSVs and the 2015-19 hourly cache")
    ap.add_argument("--hourly", default="btc_hourly.pkl")
    ap.add_argument("--memes", default="hl_daily.pkl")
    ap.add_argument("--perps", default="hl_all_daily.pkl")
    ap.add_argument("--json", help="write the trial results here")
    a = ap.parse_args(argv)
    d = Path(a.dir)
    hourly = load_hourly([d / "btc_hourly_2015_2019.pkl", a.hourly])
    rows = build_rows(d, hourly, basket_returns(Path(a.memes), 3), basket_returns(Path(a.perps), 20))
    if not rows:
        print("no rows: check --dir and the hourly cache")
        return 1
    trials = run(rows)
    print(render(rows, trials))
    if a.json:
        slim = {"count": trials["count"], "cands": trials["cands"], "dsr": trials.get("dsr"),
                "uni": {f"{k[0]}->{k[1]}": v for k, v in trials["uni"].items()},
                "div": trials["div"], "rev": trials["rev"],
                "wf": {k: {kk: vv for kk, vv in v.items() if kk != "pnl"} for k, v in trials["wf"].items()}}
        Path(a.json).write_text(json.dumps(slim, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
