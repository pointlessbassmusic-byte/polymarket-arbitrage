"""Bitcoin variance risk premium: step 2 of `btc-vrp-listed-options`, on a
free implied-volatility history instead of a year's wait.

The registered test waits for twelve months of IBIT surface rows "or
sooner with purchased history". Deribit publishes its 30-day BTC
implied-volatility index (DVOL) daily since 2021-03-24 through a public
endpoint, and on the collector's first day IBIT's own 30-day ATM implied
volatility (36.6%) and DVOL (37.0%) were half a point apart, so DVOL
stands in for the IBIT surface here. The deviation is recorded in the
registry; the IBIT rows keep accruing and will say how far the two
drift apart.

Two P&L models, both on daily BTC closes (Coinbase, public):

1. variance swap: short 30-day variance at DVOL squared, settled on the
   realised variance of the next 30 calendar days. The textbook premium,
   in vol points per unit of vega, before any trading friction.
2. the registered trade: a short 30-day at-the-money straddle,
   Black-Scholes marked each weekday at that day's DVOL, delta-hedged
   once a day at the close, held to expiry, charged commissions, half
   the quoted spread on entry and 1 bp on every hedge trade; returns on
   the margin a retail broker holds against a naked straddle.

Gate (registered): enter only when DVOL exceeds the trailing 20-day
realised vol by at least 5 points; 0 and 10 are sensitivities, and the
ungated always-short series says whether a premium exists at all. One
position at a time; a month with no position scores zero.

    python -m cryptobot.vrp_study --state state --fetch     # pulls DVOL and BTC closes
    python -m cryptobot.vrp_study --state state --gate 5
"""
from __future__ import annotations

import argparse
import asyncio
import bisect
import datetime as dt
import math
import statistics
from pathlib import Path
from typing import Optional

from . import stats as S
from .data.nasdaq import append_jsonl, read_jsonl

DVOL_URL = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
DVOL_START = dt.date(2021, 3, 24)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) cryptobot-research"}

TENOR_DAYS = 30
RV_DAYS = 20
ANNUAL = 365.0           # BTC trades every day; DVOL is annualised the same way


# ----------------------------------------------------------------- data

def dvol_file(state_dir: Path) -> Path:
    return Path(state_dir) / "options" / "dvol_btc.jsonl"


def btc_file(state_dir: Path) -> Path:
    return Path(state_dir) / "options" / "btc_daily.jsonl"


async def fetch_dvol(client, start: dt.date, end: dt.date, currency: str = "BTC") -> list[dict]:
    """Daily DVOL candles, paged a year at a time (the endpoint caps a
    reply at 1,000 points)."""
    out: dict[str, dict] = {}
    a = start
    while a <= end:
        b = min(end, a + dt.timedelta(days=360))
        params = {"currency": currency, "resolution": "1D",
                  "start_timestamp": int(dt.datetime.combine(a, dt.time(), dt.timezone.utc).timestamp() * 1000),
                  "end_timestamp": int(dt.datetime.combine(b + dt.timedelta(days=1), dt.time(), dt.timezone.utc).timestamp() * 1000)}
        r = await client.get(DVOL_URL, params=params)
        if r.status_code >= 400:
            raise RuntimeError(f"deribit -> {r.status_code}")
        for ts, o, h, l, c in (r.json().get("result") or {}).get("data") or []:
            d = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).date().isoformat()
            out[d] = {"date": d, "open": float(o), "high": float(h), "low": float(l), "close": float(c)}
        a = b + dt.timedelta(days=1)
    return [out[k] for k in sorted(out)]


async def fetch_btc_daily(client, start: dt.date, end: dt.date) -> list[dict]:
    """Coinbase daily BTC-USD closes, 300 candles a request, newest first."""
    out: dict[str, float] = {}
    a = start
    while a <= end:
        b = min(end, a + dt.timedelta(days=299))
        params = {"granularity": 86400, "start": f"{a.isoformat()}T00:00:00Z", "end": f"{b.isoformat()}T00:00:00Z"}
        r = await client.get(COINBASE_CANDLES, params=params)
        if r.status_code >= 400:
            raise RuntimeError(f"coinbase -> {r.status_code}")
        for ts, lo, hi, op, cl, vol in r.json():
            out[dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date().isoformat()] = float(cl)
        a = b + dt.timedelta(days=1)
    return [{"date": k, "close": out[k]} for k in sorted(out)]


async def fetch(state_dir: Path, client=None, today: Optional[dt.date] = None) -> dict[str, int]:
    """Fill or extend both series from their last stored day; returns new rows."""
    import httpx
    own = client is None
    client = client or httpx.AsyncClient(timeout=60, headers=UA)
    today = today or dt.date.today()
    added = {}
    try:
        for name, path, fn, first in (("dvol", dvol_file(state_dir), fetch_dvol, DVOL_START),
                                      ("btc", btc_file(state_dir), fetch_btc_daily, DVOL_START - dt.timedelta(days=RV_DAYS + 5))):
            have = {r["date"] for r in read_jsonl(path)}
            start = max(dt.date.fromisoformat(max(have)) - dt.timedelta(days=3), first) if have else first
            n = 0
            for row in await fn(client, start, today):
                if row["date"] not in have:
                    append_jsonl(path, row)
                    have.add(row["date"])
                    n += 1
            added[name] = n
    finally:
        if own:
            await client.aclose()
    return added


def load(state_dir: Path, source: str = "dvol") -> tuple[dict[dt.date, float], "Closes"]:
    """`dvol`: Deribit's index and BTC closes (the backtest). `ibit`: the
    collector's own IBIT rows (30-day ATM IV from Cboe's chain) and IBIT
    closes, trading days on 252: the out-of-sample paper track."""
    sd = Path(state_dir)
    if source == "ibit":
        iv = {dt.date.fromisoformat(r["date"]): r["iv30_atm"] for r in read_jsonl(sd / "options" / "ibit.jsonl") if r.get("iv30_atm")}
        px = {dt.date.fromisoformat(r["date"]): r["close"] for r in read_jsonl(sd / "options" / "ibit_closes.jsonl")}
        return iv, Closes(px, annual=252.0)
    iv = {dt.date.fromisoformat(r["date"]): r["close"] / 100.0 for r in read_jsonl(dvol_file(sd))}
    px = {dt.date.fromisoformat(r["date"]): r["close"] for r in read_jsonl(btc_file(sd))}
    return iv, Closes(px)


# ------------------------------------------------------------ volatility

class Closes:
    """Daily closes with the realised-vol arithmetic on OBSERVATIONS, so
    the same code serves BTC (every calendar day, annualised on 365) and
    IBIT (trading days, 252)."""

    def __init__(self, px: dict[dt.date, float], annual: float = ANNUAL):
        self.px = {d: float(v) for d, v in px.items() if v and v > 0}
        self.dates = sorted(self.px)
        self.idx = {d: i for i, d in enumerate(self.dates)}
        self.annual = annual

    def __contains__(self, d: dt.date) -> bool:
        return d in self.px

    def __getitem__(self, d: dt.date) -> float:
        return self.px[d]

    def __len__(self) -> int:
        return len(self.dates)

    def _vol(self, seg: list[dt.date]) -> Optional[float]:
        if len(seg) < 3:
            return None
        rets = [math.log(self.px[b] / self.px[a]) for a, b in zip(seg, seg[1:])]
        return math.sqrt(sum(r * r for r in rets) / len(rets) * self.annual)

    def realised(self, end: dt.date, n_obs: int) -> Optional[float]:
        """Annualised vol of the last `n_obs` returns ending at `end`."""
        i = self.idx.get(end)
        if i is None or i < n_obs:
            return None
        return self._vol(self.dates[i - n_obs:i + 1])

    def realised_between(self, start: dt.date, end: dt.date) -> Optional[float]:
        i0, i1 = self.idx.get(start), self.idx.get(end)
        if i0 is None or i1 is None:
            return None
        return self._vol(self.dates[i0:i1 + 1])

    def between(self, start: dt.date, end: dt.date) -> list[dt.date]:
        """Dates strictly inside (start, end)."""
        i0, i1 = self.idx.get(start), self.idx.get(end)
        return self.dates[i0 + 1:i1] if i0 is not None and i1 is not None else []

    def expiry_after(self, d: dt.date, tenor: int) -> Optional[dt.date]:
        """First weekday with a close on or after d + tenor days."""
        target = d + dt.timedelta(days=tenor)
        i = bisect.bisect_left(self.dates, target)
        while i < len(self.dates) and self.dates[i].weekday() >= 5:
            i += 1
        return self.dates[i] if i < len(self.dates) else None


def realised_vol(px: dict[dt.date, float], end: dt.date, days: int, annual: float = ANNUAL) -> Optional[float]:
    return Closes(px, annual).realised(end, days)


def gate_open(iv: float, rv: Optional[float], gate: Optional[float]) -> bool:
    if gate is None:
        return True
    return rv is not None and (iv - rv) >= gate / 100.0


# ---------------------------------------------------- Black-Scholes bits

def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _ninv(p: float) -> float:
    lo, hi = -8.0, 8.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _ncdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def bs(S0: float, K: float, sigma: float, tau: float) -> tuple[float, float, float]:
    """(call, put, call delta) with zero rates; put delta is call delta - 1."""
    if tau <= 0 or sigma <= 0:
        return max(S0 - K, 0.0), max(K - S0, 0.0), (1.0 if S0 > K else 0.0 if S0 < K else 0.5)
    v = sigma * math.sqrt(tau)
    d1 = (math.log(S0 / K) + 0.5 * v * v) / v
    d2 = d1 - v
    return S0 * _ncdf(d1) - K * _ncdf(d2), K * _ncdf(-d2) - S0 * _ncdf(-d1), _ncdf(d1)


def straddle(S0: float, K: float, sigma: float, tau: float) -> tuple[float, float]:
    """(price, delta) of a call plus a put, zero rates, per unit of underlying."""
    c, p, dc = bs(S0, K, sigma, tau)
    return c + p, 2.0 * dc - 1.0


def wing_strikes(S0: float, sigma: float, tau: float, delta: float) -> tuple[float, float]:
    """Strikes of the call with `delta` and the put with -`delta` (BS, flat vol)."""
    v = sigma * math.sqrt(tau)
    z = _ninv(delta)
    return S0 * math.exp(0.5 * v * v - z * v), S0 * math.exp(0.5 * v * v + z * v)


def position(S: float, K: float, Kc: Optional[float], Kp: Optional[float], sigma: float, tau: float) -> tuple[float, float]:
    """(value, delta) of the short straddle at K plus, when wings are set,
    the long call at Kc and the long put at Kp; value is what it costs to
    buy the position back, delta is the hedge to hold against it."""
    val, dlt = straddle(S, K, sigma, tau)
    if Kc is not None and Kp is not None:
        c, _, dc = bs(S, Kc, sigma, tau)
        _, p, dp = bs(S, Kp, sigma, tau)
        val -= c + p
        dlt -= dc + (dp - 1.0)
    return val, dlt


# ------------------------------------------------------------- the runs

WEEKDAYS_PER_TENOR = 21


def _closes(px) -> Closes:
    return px if isinstance(px, Closes) else Closes(px)


def _iv_on(iv: dict, d: dt.date, last: Optional[float]) -> Optional[float]:
    return iv.get(d, last)


def variance_swap_trades(iv: dict, px, gate: Optional[float], tenor: int = TENOR_DAYS,
                         cost_points: float = 0.0, overlap: bool = False) -> list[dict]:
    """Short-variance positions: P&L in vol points per unit of vega,
    (IV^2 - RV^2) / (2 IV), less `cost_points`. One at a time, or with
    `overlap` one every weekday at 1/21 of the size (the ladder, whose
    worst month does not hinge on one entry date)."""
    px = _closes(px)
    trades = []
    busy_until = None
    w = 1.0 / WEEKDAYS_PER_TENOR if overlap else 1.0
    for d in sorted(iv):
        if (busy_until and d <= busy_until) or d.weekday() >= 5 or d not in px:
            continue
        rv20 = px.realised(d, RV_DAYS)
        if not gate_open(iv[d], rv20, gate):
            continue
        end = px.expiry_after(d, tenor)
        rv_fwd = px.realised_between(d, end) if end else None
        if rv_fwd is None:
            continue
        pnl = (iv[d] ** 2 - rv_fwd ** 2) / (2 * iv[d]) * 100.0 - cost_points
        trades.append({"entry": d, "exit": end, "iv": iv[d] * 100, "rv20": (rv20 or 0) * 100,
                       "rv_fwd": rv_fwd * 100, "pnl": pnl * w})
        if not overlap:
            busy_until = end
    return trades


def straddle_trades(iv: dict, px, gate: Optional[float], tenor: int = TENOR_DAYS,
                    margin_frac: float = 0.25, half_spread_frac: float = 0.025,
                    commission_frac: float = 0.00014, hedge_bp: float = 1.0,
                    wing_delta: Optional[float] = None, overlap: bool = False,
                    close_dte: int = 0) -> list[dict]:
    """Short ATM straddle, sold at the close of a weekday with the gate
    open, marked at that day's implied vol (the last known one when a
    day has none), delta-hedged at every weekday close, settled at
    expiry. Costs as fractions of the spot notional: commission_frac a
    leg (0.65 USD a contract on 100 IBIT shares at ~46 USD),
    half_spread_frac of the premium a leg on entry (and on an early
    buy-back), hedge_bp on every hedge trade. Return on margin_frac of
    notional. With `wing_delta`, a call and a put at that delta are
    bought too (an iron butterfly: the option payoff is capped at the
    wing distance less the net premium; the hedge's own P&L is not, so
    the capital basis stays margin_frac of notional for every variant).
    `overlap`: a position every weekday at 1/21 size instead of one at a
    time. `close_dte`: buy the position back at the first weekday close
    with that many days or fewer to expiry, out of the pin-gamma zone."""
    px = _closes(px)
    trades = []
    busy_until = None
    w = 1.0 / WEEKDAYS_PER_TENOR if overlap else 1.0
    for d in sorted(iv):
        if (busy_until and d <= busy_until) or d.weekday() >= 5 or d not in px:
            continue
        rv20 = px.realised(d, RV_DAYS)
        if not gate_open(iv[d], rv20, gate):
            continue
        expiry = px.expiry_after(d, tenor)
        if expiry is None:
            continue
        S0, K = px[d], px[d]
        tau0 = (expiry - d).days / ANNUAL
        Kc = Kp = None
        prem, _ = straddle(S0, K, iv[d], tau0)
        cash = prem * (1 - half_spread_frac) - 2 * commission_frac * S0
        if wing_delta:
            Kc, Kp = wing_strikes(S0, iv[d], tau0, wing_delta)
            c, _, _ = bs(S0, Kc, iv[d], tau0)
            _, p, _ = bs(S0, Kp, iv[d], tau0)
            cash -= (c + p) * (1 + half_spread_frac) + 2 * commission_frac * S0
        margin = margin_frac * S0           # the same capital basis for every variant (the hedge needs it too)
        _, delta = position(S0, K, Kc, Kp, iv[d], tau0)
        hedge = delta                                   # units of spot held against the short position
        cash -= hedge * S0 + abs(hedge) * S0 * hedge_bp / 1e4
        sigma = iv[d]
        exit_day, exit_px = expiry, px[expiry]
        closed_early = False
        for day in px.between(d, expiry):
            if day.weekday() >= 5:
                continue                                 # IBIT cannot be hedged at a weekend close
            sigma = _iv_on(iv, day, sigma)
            tau = (expiry - day).days / ANNUAL
            S = px[day]
            if close_dte and (expiry - day).days <= close_dte:
                val, _ = position(S, K, Kc, Kp, sigma, tau)
                legs = 4 if Kc is not None else 2
                cash -= val * (1 + half_spread_frac) + legs * commission_frac * S
                exit_day, exit_px, closed_early = day, S, True
                break
            _, delta = position(S, K, Kc, Kp, sigma, tau)
            trade = delta - hedge
            cash -= trade * S + abs(trade) * S * hedge_bp / 1e4
            hedge = delta
        cash += hedge * exit_px - abs(hedge) * exit_px * hedge_bp / 1e4      # unwind the hedge
        if not closed_early:
            cash -= abs(exit_px - K)                                        # settle the straddle
            if Kc is not None:
                cash += max(exit_px - Kc, 0.0) + max(Kp - exit_px, 0.0)    # and the wings
        trades.append({"entry": d, "exit": exit_day, "iv": iv[d] * 100, "rv20": (rv20 or 0) * 100,
                       "premium_pct": prem / S0 * 100, "pnl_pct_notional": cash / S0 * 100,
                       "pnl": cash / margin * 100 * w})
        if not overlap:
            busy_until = exit_day
    return trades


def monthly_series(trades: list[dict], first: dt.date, last: dt.date) -> list[tuple[str, float]]:
    """One number a calendar month (P&L of the trades entered in it; 0
    when none), so months out of the market count as flat."""
    by: dict[str, float] = {}
    m = first.replace(day=1)
    while m <= last:
        by[m.strftime("%Y-%m")] = 0.0
        m = (m + dt.timedelta(days=32)).replace(day=1)
    for t in trades:
        by[t["entry"].strftime("%Y-%m")] = by.get(t["entry"].strftime("%Y-%m"), 0.0) + t["pnl"]
    return sorted(by.items())


def summarize(trades: list[dict], first: dt.date, last: dt.date) -> dict:
    months = monthly_series(trades, first, last)
    xs = [v for _, v in months]
    if not trades:
        return {"trades": 0, "months": len(xs)}
    sd = statistics.pstdev(xs) if len(xs) > 2 else 0.0
    cum, peak, mdd = 0.0, 0.0, 0.0
    for v in xs:
        cum += v
        peak = max(peak, cum)
        mdd = min(mdd, cum - peak)
    pnl = [t["pnl"] for t in trades]
    by_year: dict[int, float] = {}
    for m, v in months:
        by_year[int(m[:4])] = by_year.get(int(m[:4]), 0.0) + v
    return {"trades": len(trades), "months": len(xs), "mean_trade": statistics.fmean(pnl),
            "t_trade": statistics.fmean(pnl) / (statistics.pstdev(pnl) / math.sqrt(len(pnl))) if len(pnl) > 2 and statistics.pstdev(pnl) > 0 else 0.0,
            "win_rate": sum(1 for v in pnl if v > 0) / len(pnl), "mean_month": statistics.fmean(xs),
            "sharpe": statistics.fmean(xs) / sd * math.sqrt(12) if sd > 0 else 0.0,
            "psr": S.psr(xs) if len(xs) > 2 else 0.0, "max_drawdown": mdd, "worst_month": min(xs),
            "total": cum, "by_year": by_year, "months_2025": [(m, v) for m, v in months if m.startswith("2025")],
            "monthly": xs}


def run(iv: dict, px, gates=(None, 0.0, 5.0, 10.0), cost_points: float = 1.5,
        wing_delta: Optional[float] = None, overlap: bool = False, close_dte: int = 0, **straddle_kw) -> dict:
    """Every series here is a trial. The registered rule is the one-at-a-
    time straddle at the 5-point gate held to expiry; wings, the ladder
    and the early close are post-hoc variants, reported next to it and
    counted."""
    px = _closes(px)
    first, last = min(iv), max(iv)
    out = {"first": first, "last": last, "days": len(iv), "variance_swap": {}, "straddle": {}, "wings": {},
           "ladder": {}, "early": {}, "wing_delta": wing_delta, "close_dte": close_dte}
    for g in gates:
        out["variance_swap"][g] = summarize(variance_swap_trades(iv, px, g, cost_points=cost_points), first, last)
        out["straddle"][g] = summarize(straddle_trades(iv, px, g, **straddle_kw), first, last)
    if wing_delta:
        for g in (None, 5.0):
            out["wings"][g] = summarize(straddle_trades(iv, px, g, wing_delta=wing_delta, **straddle_kw), first, last)
    if overlap:
        out["ladder"]["straddle"] = summarize(straddle_trades(iv, px, 5.0, overlap=True, **straddle_kw), first, last)
        if wing_delta:
            out["ladder"]["wings"] = summarize(straddle_trades(iv, px, 5.0, wing_delta=wing_delta, overlap=True, **straddle_kw), first, last)
    if close_dte:
        out["early"]["straddle"] = summarize(straddle_trades(iv, px, 5.0, close_dte=close_dte, **straddle_kw), first, last)
        if overlap:
            out["early"]["ladder"] = summarize(straddle_trades(iv, px, 5.0, close_dte=close_dte, overlap=True, **straddle_kw), first, last)
    all_series = [s for grp in ("variance_swap", "straddle", "wings", "ladder", "early") for s in out[grp].values() if s.get("trades")]
    n_trials = 2 * len(gates) + len(out["wings"]) + len(out["ladder"]) + len(out["early"])
    srs = [s["sharpe"] for s in all_series]
    var_sr = statistics.pvariance(srs) if len(srs) > 1 else 0.0
    for s in all_series:
        s["dsr"] = S.dsr(s["monthly"], n_trials, var_sr)
        s["min_trl_months"] = S.min_trl(s["monthly"])
        s["trials"] = n_trials
    out["trials"] = n_trials
    out["verdict"] = passes(out["straddle"].get(5.0) or {})
    return out


def passes(s: dict) -> tuple[str, str]:
    """Written before running (registry): net Sharpe > 0.7 with PSR >= 0.95
    over the available window, worst month better than -15% of the
    committed capital, and the 2025 months with implied below realised
    flat or skipped by the gate; otherwise inconclusive."""
    if not s.get("trades"):
        return "inconclusive", "no trades"
    if s["worst_month"] <= -15.0:
        return "inconclusive", f"worst month {s['worst_month']:+.1f}% of margin"
    if s["sharpe"] > 0.7 and s["psr"] >= 0.95:
        if s.get("dsr", 1.0) < 0.95:
            return "inconclusive", f"clears the bar but DSR {s['dsr']:.2f} at {s.get('trials', '?')} trials"
        return "alive", "clears the bar"
    return "inconclusive", f"Sharpe {s['sharpe']:+.2f}, PSR {s['psr']:.2f}"


def render(res: dict) -> str:
    o = [f"BTC variance risk premium, implied vol {res['first']} .. {res['last']} ({res['days']} days), 30-day tenor, one position at a time"]

    def line(s: dict) -> str:
        if not s.get("trades"):
            return "no trades"
        yrs = " ".join(f"{y}:{v:+.1f}" for y, v in sorted(s["by_year"].items()))
        return (f"{s['trades']:3d} trades, mean {s['mean_trade']:+.2f} (t {s['t_trade']:+.1f}, win {s['win_rate']*100:.0f}%), "
                f"per month {s['mean_month']:+.2f}, Sharpe {s['sharpe']:+.2f}, PSR {s['psr']:.2f}"
                + (f", DSR {s['dsr']:.2f}" if "dsr" in s else "")
                + f", max DD {s['max_drawdown']:+.1f}, worst month {s['worst_month']:+.1f} | {yrs}")
    o.append("  variance swap, vol points per unit vega after 1.5 points of friction:")
    for g, s in res["variance_swap"].items():
        o.append(f"    gate {'none' if g is None else f'{g:>4.0f}'}: {line(s)}")
    o.append("  short ATM straddle, delta-hedged daily, % of margin (25% of notional), after commissions, spread and 1 bp hedges:")
    for g, s in res["straddle"].items():
        o.append(f"    gate {'none' if g is None else f'{g:>4.0f}'}: {line(s)}")
    if res.get("wings"):
        o.append(f"  iron butterfly (wings bought at {res['wing_delta']*100:.0f} delta), % of the same margin, same costs:")
        for g, s in res["wings"].items():
            o.append(f"    gate {'none' if g is None else f'{g:>4.0f}'}: {line(s)}")
    if res.get("ladder"):
        o.append("  ladder (a position every weekday at 1/21 size), gate 5:")
        for k, s in res["ladder"].items():
            o.append(f"    {k:>9}: {line(s)}")
    if res.get("early"):
        o.append(f"  bought back {res['close_dte']} days before expiry (out of the pin-gamma zone), gate 5:")
        for k, s in res["early"].items():
            o.append(f"    {k:>9}: {line(s)}")
    reg = res["straddle"].get(5.0) or {}
    if reg.get("months_2025"):
        o.append("  2025 by month, registered gate (5 points), % of margin: "
                 + " ".join(f"{m[5:]}:{v:+.1f}" if v else f"{m[5:]}:skip" for m, v in reg["months_2025"]))
    if "dsr" in reg:
        o.append(f"  registered rule (one straddle at a time, gate 5): DSR {reg['dsr']:.2f} at {res['trials']} trials, "
                 f"minimum track record {reg['min_trl_months']:.0f} months")
    v, why = res["verdict"]
    o.append(f"verdict: {v} ({why})")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", type=Path, default=Path("state"))
    ap.add_argument("--fetch", action="store_true", help="pull DVOL (Deribit, public) and BTC daily closes (Coinbase, public) first")
    ap.add_argument("--cost-points", type=float, default=1.5, help="variance-swap friction in vol points")
    ap.add_argument("--half-spread", type=float, default=0.025, help="half the quoted spread as a fraction of the premium, a leg")
    ap.add_argument("--margin", type=float, default=0.25, help="margin held against the straddle, fraction of notional")
    ap.add_argument("--wings", type=float, default=None, help="post-hoc variant: buy the wings at this delta (0.10)")
    ap.add_argument("--overlap", action="store_true", help="post-hoc view: a position every weekday at 1/21 size")
    ap.add_argument("--close-dte", type=int, default=0, help="post-hoc variant: buy back this many days before expiry")
    ap.add_argument("--source", choices=("dvol", "ibit"), default="dvol",
                    help="dvol: the Deribit backtest; ibit: the collector's own IBIT rows, the out-of-sample track")
    a = ap.parse_args(argv)
    if a.fetch:
        print("fetched " + ", ".join(f"{k}: {n} new rows" for k, n in asyncio.run(fetch(a.state)).items()))
    iv, px = load(a.state, a.source)
    if not iv or not len(px):
        print("vrp: no implied-vol or close rows yet" + (" (run with --fetch)" if a.source == "dvol" else ""))
        return 1
    print(render(run(iv, px, cost_points=a.cost_points, half_spread_frac=a.half_spread, margin_frac=a.margin,
                     wing_delta=a.wings, overlap=a.overlap, close_dte=a.close_dte)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
