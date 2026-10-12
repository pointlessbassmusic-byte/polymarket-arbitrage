"""Cointegration spread mean reversion between DOGE, SHIB and PEPE, the
memecoins a US account can short and go long on the same venue.

Pre-registered as `pairs-doge-shib-us` (hypotheses.yaml). The rule, as
written there: on each day t, regress log P_y on log P_x over the last
`beta_window` days (OLS, with intercept); require the residual to pass
an Engle-Granger test (Dickey-Fuller t on the residual at or below
`eg_crit`); z-score today's residual against the last `z_window`
residuals; enter when |z| >= z_entry, short the rich leg and long the
cheap one, $1 of notional each; exit when z crosses zero, when |z|
reaches z_stop, or after `max_days`. Costs: 8.5 bp per execution on
that leg (4 bp fee + 4.5 bp half-spread, Kalshi's books for $50-$2,000
orders), four executions a round trip; realised daily funding on both
legs (the long pays a positive rate, the short receives it). P&L is a
fraction of one leg's notional; with both legs at 1x the capital is
twice that.

    python -m cryptobot.pairs_study --cache hl_all_daily.pkl --funding hl_funding.pkl
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import pickle
import statistics
from dataclasses import dataclass, replace
from pathlib import Path

from . import stats as S

DAY = 86400
PAIRS = (("DOGE", "kSHIB"), ("DOGE", "kPEPE"), ("kSHIB", "kPEPE"))
COST_PER_EXECUTION = 0.00085


@dataclass(frozen=True)
class PairRule:
    beta_window: int = 90
    z_window: int = 60
    z_entry: float = 2.0
    z_exit: float = 0.0
    z_stop: float = 4.0
    max_days: int = 20
    eg_crit: float = -3.37        # Engle-Granger 5% critical value, two variables with a constant
    require_eg: bool = True

    def label(self) -> str:
        return f"z>={self.z_entry:g} stop{self.z_stop:g} {self.beta_window}/{self.z_window}d {'EG' if self.require_eg else 'noEG'}"


# ------------------------------------------------------------------ data

def load_closes(cache: Path, coins=None) -> dict[str, dict[int, float]]:
    pools = pickle.loads(Path(cache).read_bytes())
    out: dict[str, dict[int, float]] = {}
    for _, (meta, candles) in pools.items():
        if coins and meta.symbol not in coins:
            continue
        out[meta.symbol] = {int(c.ts // DAY) * DAY: float(c.close) for c in candles if c.close > 0}
    return out


def load_daily_funding(cache: Path | None) -> dict[str, dict[int, float]]:
    """{coin: {day: sum of the day's hourly rates}}; empty without a cache."""
    if not cache or not Path(cache).exists():
        return {}
    from .carry_study import daily_funding
    return daily_funding(pickle.loads(Path(cache).read_bytes()))


# ------------------------------------------------------------------ maths

def ols(y: list[float], x: list[float]) -> tuple[float, float, list[float]]:
    n = len(y)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((v - mx) ** 2 for v in x)
    beta = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx if sxx > 0 else 0.0
    alpha = my - beta * mx
    return alpha, beta, [b - alpha - beta * a for a, b in zip(x, y)]


def adf_t(e: list[float]) -> float:
    """Dickey-Fuller t-statistic of de_t on e_{t-1}, no constant, no lags:
    the Engle-Granger second stage on a cointegrating residual."""
    if len(e) < 10:
        return 0.0
    x = e[:-1]
    d = [e[i] - e[i - 1] for i in range(1, len(e))]
    sxx = sum(v * v for v in x)
    if sxx <= 0:
        return 0.0
    rho = sum(a * b for a, b in zip(x, d)) / sxx
    resid = [b - rho * a for a, b in zip(x, d)]
    dof = len(d) - 1
    s2 = sum(r * r for r in resid) / dof if dof > 0 else 0.0
    se = math.sqrt(s2 / sxx) if s2 > 0 else 0.0
    return rho / se if se > 0 else 0.0


def signal_on(y_log: list[float], x_log: list[float], rule: PairRule) -> dict | None:
    """Hedge ratio, residual z-score and EG t for the window ending at
    the last element (today's close)."""
    w = rule.beta_window
    if len(y_log) < w or len(x_log) < w:
        return None
    alpha, beta, e = ols(y_log[-w:], x_log[-w:])
    zw = e[-rule.z_window:]
    if len(zw) < rule.z_window:
        return None
    m, sd = statistics.fmean(zw), statistics.pstdev(zw)
    if sd <= 0:
        return None
    return {"alpha": alpha, "beta": beta, "z": (e[-1] - m) / sd, "adf_t": adf_t(e), "sd": sd}


def spread_z(y_log_now: float, x_log_now: float, sig: dict) -> float:
    """Today's z under a frozen hedge ratio and spread scale (used while a
    trade is open, so the exit is judged on the spread that was traded)."""
    e = y_log_now - sig["alpha"] - sig["beta"] * x_log_now
    return (e - sig["mean"]) / sig["sd"]


# ------------------------------------------------------------------ simulation

def simulate(closes: dict[str, dict[int, float]], funding: dict[str, dict[int, float]],
             pair: tuple[str, str], rule: PairRule, start: int, end: int,
             cost_exec: float = COST_PER_EXECUTION) -> dict:
    y, x = pair
    days = sorted(set(closes[y]) & set(closes[x]))
    days = [d for d in days if d <= end]
    y_log = [math.log(closes[y][d]) for d in days]
    x_log = [math.log(closes[x][d]) for d in days]
    trades: list[dict] = []
    daily: dict[int, float] = {}
    open_pos: dict | None = None
    for i, d in enumerate(days):
        if d < start:
            continue
        if open_pos:
            p = open_pos
            ry = closes[y][d] / closes[y][p["prev_day"]] - 1.0
            rx = closes[x][d] / closes[x][p["prev_day"]] - 1.0
            # side_y = +1 long y / short x, -1 short y / long x
            pnl = p["side_y"] * (ry - rx)
            fy = funding.get(y, {}).get(d, 0.0)
            fx = funding.get(x, {}).get(d, 0.0)
            fund = -p["side_y"] * fy + p["side_y"] * fx        # long pays, short receives
            p["gross"] += pnl
            p["funding"] += fund
            p["prev_day"] = d
            p["days"] += 1
            z = spread_z(y_log[i], x_log[i], p["sig"])
            reason = None
            # entered with z > 0 (y rich): done once z has fallen to z_exit; mirror below zero
            crossed = z <= rule.z_exit if p["entry_z"] > 0 else z >= -rule.z_exit
            if crossed:
                reason = "target"
            if abs(z) >= rule.z_stop and (z * p["entry_z"]) > 0:
                reason = "stop"
            if p["days"] >= rule.max_days:
                reason = reason or "time"
            day_pnl = pnl + fund
            if reason:
                day_pnl -= 2 * cost_exec
                p["fees"] += 2 * cost_exec
                p["exit_day"], p["exit_z"], p["exit_reason"] = d, z, reason
                p["net"] = p["gross"] + p["funding"] - p["fees"]
                trades.append(p)
                open_pos = None
            daily[d] = daily.get(d, 0.0) + day_pnl
            if open_pos:
                continue
        sig = signal_on(y_log[: i + 1], x_log[: i + 1], rule)
        if sig is None:
            continue
        if rule.require_eg and sig["adf_t"] > rule.eg_crit:
            continue
        if abs(sig["z"]) < rule.z_entry:
            continue
        # z > 0: y is rich -> short y, long x
        side_y = -1.0 if sig["z"] > 0 else 1.0
        w = rule.beta_window
        _a, _b, e = ols(y_log[i + 1 - w: i + 1], x_log[i + 1 - w: i + 1])
        sig["mean"] = statistics.fmean(e[-rule.z_window:])
        open_pos = {"pair": f"{y}/{x}", "entry_day": d, "prev_day": d, "side_y": side_y, "entry_z": sig["z"],
                    "beta": sig["beta"], "adf_t": sig["adf_t"], "sig": sig, "days": 0,
                    "gross": 0.0, "funding": 0.0, "fees": 2 * cost_exec}
        daily[d] = daily.get(d, 0.0) - 2 * cost_exec
    if open_pos:
        open_pos["exit_day"], open_pos["exit_reason"] = days[-1], "open"
        open_pos["net"] = open_pos["gross"] + open_pos["funding"] - open_pos["fees"]
        trades.append(open_pos)
    return {"pair": f"{y}/{x}", "rule": rule.label(), "trades": trades, "daily": daily}


def combine_daily(results: list[dict]) -> dict[int, float]:
    out: dict[int, float] = {}
    for r in results:
        for d, v in r["daily"].items():
            out[d] = out.get(d, 0.0) + v
    return out


def metrics(trades: list[dict], daily: dict[int, float]) -> dict:
    closed = [t for t in trades if t.get("exit_reason") != "open"]
    nets = [t["net"] for t in closed]
    days = sorted(daily)
    rets = [daily[d] for d in days]
    yrs = max((days[-1] - days[0]) / DAY, 1) / 365.25 if days else 0.0
    sd = statistics.pstdev(rets) if len(rets) > 2 else 0.0
    by_year: dict[int, float] = {}
    for d, v in daily.items():
        yv = dt.datetime.utcfromtimestamp(d).year
        by_year[yv] = by_year.get(yv, 0.0) + v
    pos_years = [y for y, v in by_year.items() if v > 0]
    recent = sum(v for y, v in by_year.items() if y >= 2025)
    return {"trades": len(closed), "mean_net": statistics.fmean(nets) if nets else 0.0,
            "hit": sum(1 for v in nets if v > 0) / len(nets) if nets else 0.0,
            "t": (statistics.fmean(nets) / (statistics.pstdev(nets) / math.sqrt(len(nets)))
                  if len(nets) > 2 and statistics.pstdev(nets) > 0 else 0.0),
            "ann_return_on_leg": sum(rets) / yrs if yrs else 0.0,
            "sharpe": statistics.fmean(rets) / sd * math.sqrt(365) if sd > 0 else 0.0,
            "psr": S.psr(rets) if len(rets) > 2 else 0.0,
            "by_year": dict(sorted(by_year.items())), "positive_years": len(pos_years),
            "net_2025_26": recent,
            "exits": {r: sum(1 for t in closed if t["exit_reason"] == r) for r in {t["exit_reason"] for t in closed}}}


def year_pairs_positive(by_year: dict[int, float]) -> float:
    """Share of two-year test sets with positive net: the CPCV with a
    fit-free rule collapses to this."""
    ys = sorted(by_year)
    if len(ys) < 2:
        return 0.0
    combos = [(a, b) for i, a in enumerate(ys) for b in ys[i + 1:]]
    return sum(1 for a, b in combos if by_year[a] + by_year[b] > 0) / len(combos)


def passes(m: dict, dsr: float | None) -> tuple[bool, str]:
    """Written before running: net Sharpe > 0.5 with PSR >= 0.95 over the
    walk-forward AND net positive in 2025-2026 AND >= 30 round trips AND
    DSR >= 0.95; net negative in 2025-2026 is killed."""
    if m["net_2025_26"] < 0:
        return False, "killed: net negative in 2025-2026"
    ok = m["sharpe"] > 0.5 and m["psr"] >= 0.95 and m["trades"] >= 30 and (dsr or 0.0) >= 0.95
    return ok, "alive" if ok else "inconclusive"


# ------------------------------------------------------------------ driver

def run(closes, funding, start: int, end: int, base: PairRule = PairRule(),
        z_grid=(1.5, 2.0, 2.5), eg_grid=(True, False), pairs=PAIRS) -> dict:
    out = {"registered": {}, "grid": [], "trials": 0}
    per_pair = []
    for pair in pairs:
        if pair[0] not in closes or pair[1] not in closes:
            continue
        r = simulate(closes, funding, pair, base, start, end)
        per_pair.append(r)
        out["registered"][r["pair"]] = metrics(r["trades"], r["daily"])
        out["trials"] += 1
    all_daily = combine_daily(per_pair)
    all_trades = [t for r in per_pair for t in r["trades"]]
    out["registered"]["combined"] = metrics(all_trades, all_daily)
    out["trades_detail"] = all_trades
    srs = []
    for z in z_grid:
        for eg in eg_grid:
            rule = replace(base, z_entry=z, require_eg=eg)
            if rule == base:
                combined = all_daily
            else:
                rs = [simulate(closes, funding, p, rule, start, end) for p in pairs
                      if p[0] in closes and p[1] in closes]
                combined = combine_daily(rs)
                out["trials"] += len(rs)
                all_t = [t for r in rs for t in r["trades"]]
            m = metrics(all_trades if rule == base else all_t, combined)
            out["grid"].append({"rule": rule.label(), **m})
            days = sorted(combined)
            srs.append(S.sharpe([combined[d] for d in days]) if len(days) > 2 else 0.0)
    best = max(out["grid"], key=lambda g: g["sharpe"])
    if len(srs) >= 2:
        var_sr = statistics.pvariance(srs)
        days = sorted(all_daily)
        out["dsr_registered"] = S.dsr([all_daily[d] for d in days], out["trials"], var_sr) if len(days) > 2 else 0.0
        out["best"] = best["rule"]
    out["verdict"] = passes(out["registered"]["combined"], out.get("dsr_registered"))
    out["cpcv_like"] = year_pairs_positive(out["registered"]["combined"]["by_year"])
    return out


def render(res: dict) -> str:
    o = ["registered rule (z>=2, 90/60d, EG required, stop 4, 20d), 8.5 bp per execution, realised funding:"]
    for name, m in res["registered"].items():
        yrs = " ".join(f"{y}:{v*100:+.1f}%" for y, v in m["by_year"].items())
        o.append(f"  {name:12s} trades {m['trades']:3d} mean net {m['mean_net']*100:+.2f}% (t {m['t']:+.1f}, hit {m['hit']*100:.0f}%) "
                 f"Sharpe {m['sharpe']:+.2f} PSR {m['psr']:.2f}  per leg-notional by year: {yrs}  exits {m['exits']}")
    c = res["registered"]["combined"]
    o.append(f"  2025-26 net {c['net_2025_26']*100:+.1f}%; two-year test sets positive {res['cpcv_like']*100:.0f}%")
    o.append("sensitivity grid (combined):")
    for g in res["grid"]:
        o.append(f"  {g['rule']:32s} trades {g['trades']:3d} mean {g['mean_net']*100:+.2f}% Sharpe {g['sharpe']:+.2f} "
                 f"PSR {g['psr']:.2f} 2025-26 {g['net_2025_26']*100:+.1f}%")
    if "dsr_registered" in res:
        o.append(f"trials {res['trials']}; registered rule DSR {res['dsr_registered']:.2f}; best grid cell {res['best']}")
    ok, why = res["verdict"]
    o.append(f"verdict: {why}")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default="hl_all_daily.pkl")
    ap.add_argument("--funding", default="hl_funding.pkl")
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--end", default="2026-12-31")
    ap.add_argument("--trades", action="store_true", help="print every trade")
    a = ap.parse_args(argv)
    coins = {c for p in PAIRS for c in p}
    closes = load_closes(Path(a.cache), coins)
    funding = load_daily_funding(Path(a.funding))
    start = int(dt.datetime.fromisoformat(a.start).replace(tzinfo=dt.timezone.utc).timestamp())
    end = int(dt.datetime.fromisoformat(a.end).replace(tzinfo=dt.timezone.utc).timestamp())
    res = run(closes, funding, start, end)
    print(render(res))
    if a.trades:
        for t in res["trades_detail"]:
            print(f"  {t['pair']:12s} {dt.datetime.utcfromtimestamp(t['entry_day']).date()} -> "
                  f"{dt.datetime.utcfromtimestamp(t['exit_day']).date()} side_y {t['side_y']:+.0f} z {t['entry_z']:+.2f}->"
                  f"{t.get('exit_z', float('nan')):+.2f} {t['exit_reason']:6s} gross {t['gross']*100:+.2f}% fund "
                  f"{t['funding']*100:+.2f}% net {t['net']*100:+.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
