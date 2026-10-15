"""
Volatility and options harnesses.
=================================

Model-free tests on the free histories:
  * ``variance_risk_premium``: implied variance (VIX^2, or DVOL^2 for BTC) minus realised variance over the
    following window. Overlapping windows are autocorrelated, so the test is the studentized block bootstrap
    of the daily difference series; both halves of the sample must agree in sign.
  * ``skew_tail``: does a rich put skew (CBOE SKEW, top quintile) precede more 21-day drops below -5% than a
    cheap one (bottom quintile)? Block-shift null.
  * ``term_structure_reversion``: when VIX is above VIX3M (backwardation) does VIX fall over the next 21 days
    more than when in contango? Block-shift null.

Model-priced overlay backtests (``overlay_backtest``) price monthly SPY options with Black-Scholes using
VIX as a flat implied volatility and the 3-month bill as the rate. That is a logic test, not a market
test: a flat VIX overstates OTM call premium and understates OTM put premium, so call-selling results
are an upper bound. Every result carries ``model_priced: True``. The claims (T-54..T-57) name monthly
options, so the cycles are the standard monthly expiries (harness rule 10), not a 21-session grid from
whichever day the data happen to start on.

Rule 10 does not touch the other harnesses here: the variance premium, SKEW tail and term-structure tests
use every day (overlapping windows, blocks of at least twice the window or a block-shift null), and the
implied-move test pools every daily capture, so none of them rests on one phase of a cycle grid.
"""

from __future__ import annotations

import bisect
import math
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

import numpy as np

from mandel.options import bs
from mandel.validation.backtest_eval import block_bootstrap_pvalue, sharpe_ratio

TRADING_DAYS = 252


def index_closes(rows: Iterable[dict]) -> dict[str, float]:
    """{day: close} from cboe-*-history or fred-* or deribit-dvol rows."""
    out = {}
    for r in rows:
        v = r["value"]
        if "day" in v:
            out[v["day"]] = float(v.get("close", v.get("value")))
        elif "ts_ms" in v:
            out[datetime.fromtimestamp(v["ts_ms"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")] = float(v["close"])
    return out


def price_closes(rows: Iterable[dict], symbol: Optional[str] = None) -> dict[str, float]:
    out = {}
    for r in rows:
        v = r["value"]
        if symbol and v.get("symbol") != symbol:
            continue
        out[datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")] = float(v["close"])
    return out


def adj_closes(rows: Iterable[dict], symbol: Optional[str] = None) -> dict[str, float]:
    """{day: adjclose} (dividend-adjusted) for rows that carry it; empty when the history has no adjclose."""
    out = {}
    for r in rows:
        v = r["value"]
        if (symbol and v.get("symbol") != symbol) or v.get("adjclose") is None:
            continue
        out[datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")] = float(v["adjclose"])
    return out


def _aligned(idx: dict[str, float], px: dict[str, float]):
    days = sorted(d for d in px if d in idx)
    return days, np.array([idx[d] for d in days]), np.array([px[d] for d in days])


def _halves_agree(x: np.ndarray, sign: int) -> bool:
    h = x.size // 2
    return h > 20 and np.sign(x[:h].mean()) == sign and np.sign(x[h:].mean()) == sign


def variance_risk_premium(index_rows: Iterable[dict], price_rows: Iterable[dict], window: int = 21, symbol: Optional[str] = None,
                          index_is_pct: bool = True, n_boot: int = 2000, seed: int = 0, periods_per_year: int = TRADING_DAYS) -> dict:
    """Implied variance at t (annualised, from an index quoted in vol points) minus realised variance of the
    next ``window`` daily log returns (annualised). Reports vol-point VRP as well."""
    idx = index_closes(index_rows); px = price_closes(price_rows, symbol)
    days, iv, S = _aligned(idx, px)
    if days.__len__() < window + 100:
        return {"n": len(days), "verdict": "inconclusive", "reason": f"only {len(days)} aligned days"}
    r = np.diff(np.log(S))
    n = len(r) - window
    iv_var = ((iv[:n] / (100.0 if index_is_pct else 1.0)) ** 2)
    rv_var = np.array([np.sum(r[i:i + window] ** 2) * periods_per_year / window for i in range(n)])
    d = iv_var - rv_var
    p = block_bootstrap_pvalue(iv_var, rv_var, n_boot=n_boot, block_len=2 * window, seed=seed)
    out = {"n": int(n), "window": window, "mean_iv_vol": float(np.sqrt(iv_var.mean())), "mean_rv_vol": float(np.sqrt(rv_var.mean())),
           "vrp_variance_points": float(d.mean()), "vrp_vol_points": float(np.sqrt(iv_var.mean()) - np.sqrt(rv_var.mean())),
           "share_positive": float((d > 0).mean()), "p_value": float(p), "halves": [float(d[:n // 2].mean()), float(d[n // 2:].mean())],
           "first_day": days[0], "last_day": days[n - 1]}
    ok = p < 0.05 and d.mean() > 0 and _halves_agree(d, 1)
    out["verdict"] = "supported" if ok else "not_supported"
    out["reason"] = (f"implied {out['mean_iv_vol']*100:.1f} vs realised {out['mean_rv_vol']*100:.1f} vol pts over {n} days ({days[0]}..{days[n-1]}); "
                     f"VRP positive on {out['share_positive']*100:.0f}% of days, block-bootstrap p={p:.4f}, halves {out['halves'][0]:+.4f}/{out['halves'][1]:+.4f}")
    return out


def _block_shift_null(x: np.ndarray, stat, n_boot: int, seed: int, min_shift: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = len(x)
    out = np.empty(n_boot)
    for b in range(n_boot):
        k = int(rng.integers(min_shift, n - min_shift))
        out[b] = stat(np.roll(x, k))
    return out


def skew_tail(skew_rows: Iterable[dict], price_rows: Iterable[dict], window: int = 21, drop: float = -0.05, symbol: Optional[str] = None,
              n_boot: int = 2000, seed: int = 0, min_n: int = 2000) -> dict:
    """T-52 pass: difference > 0, p < 0.05, both halves > 0. A half with <= 20 top- or bottom-quintile days is not testable:
    that criterion is then unimplemented (None), so the verdict caps at inconclusive instead of passing on the other half.
    Fewer than ``min_n`` aligned forward windows (the trial's min_n, in days) is inconclusive."""
    from mandel.experiments.underlying2 import _verdict          # lazy: underlying2 -> underlying -> volatility
    idx = index_closes(skew_rows); px = price_closes(price_rows, symbol)
    days, sk, S = _aligned(idx, px)
    n = len(S) - window
    if n < min_n:
        return {"n": n, "min_n": min_n, "verdict": "inconclusive", "reason": f"only {n} aligned days (min_n {min_n})"}
    fwd = np.log(S[window:] / S[:-window]); sk = sk[:n]
    lo_q, hi_q = np.quantile(sk, [0.2, 0.8])
    def stat(s):
        hi = s >= hi_q; lo = s <= lo_q
        return float((fwd[hi] < drop).mean() - (fwd[lo] < drop).mean())
    d = stat(sk)
    null = _block_shift_null(sk, stat, n_boot, seed, window + 1)
    p = float((np.sum(null >= d) + 1) / (n_boot + 1))
    half = n // 2
    def stat_on(a, b):
        s = sk[a:b]; f = fwd[a:b]; hi = s >= hi_q; lo = s <= lo_q
        return float((f[hi] < drop).mean() - (f[lo] < drop).mean()) if hi.sum() > 20 and lo.sum() > 20 else float("nan")
    halves = [stat_on(0, half), stat_on(half, n)]
    untestable = any(math.isnan(h) for h in halves)
    verdict, why = _verdict([("difference > 0", d > 0), ("block-shift p < 0.05", p < 0.05),
                             ("both halves > 0" + (" (half not testable: <= 20 top- or bottom-quintile days)" if untestable else ""),
                              None if untestable else all(h > 0 for h in halves))])
    return {"n": int(n), "min_n": min_n, "window": window, "drop": drop, "crash_prob_top_minus_bottom": d, "p_value": p, "halves": halves,
            "halves_testable": not untestable,
            "crash_prob_top": float((fwd[sk >= hi_q] < drop).mean()), "crash_prob_bottom": float((fwd[sk <= lo_q] < drop).mean()),
            "mean_fwd_top": float(fwd[sk >= hi_q].mean()), "mean_fwd_bottom": float(fwd[sk <= lo_q].mean()),
            "verdict": verdict,
            "reason": f"P({window}d drop < {drop:.0%}) top SKEW quintile {float((fwd[sk >= hi_q] < drop).mean()):.3f} vs bottom {float((fwd[sk <= lo_q] < drop).mean()):.3f} (diff {d:+.3f}, block-shift p={p:.3f}, halves {halves[0]:+.3f}/{halves[1]:+.3f}); {why}"}


def term_structure_reversion(vix_rows: Iterable[dict], vix3m_rows: Iterable[dict], window: int = 21, n_boot: int = 2000, seed: int = 0) -> dict:
    v = index_closes(vix_rows); v3 = index_closes(vix3m_rows)
    days = sorted(d for d in v if d in v3)
    vix = np.array([v[d] for d in days]); ratio = np.array([v[d] / v3[d] for d in days])
    n = len(days) - window
    if n < 500:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} aligned days"}
    dvix = vix[window:] - vix[:-window]; ratio = ratio[:n]
    back = ratio > 1.0
    def stat(rt):
        b = rt > 1.0
        return float(dvix[b].mean() - dvix[~b].mean()) if b.sum() > 20 and (~b).sum() > 20 else 0.0
    d = stat(ratio)
    null = _block_shift_null(ratio, stat, n_boot, seed, window + 1)
    p = float((np.sum(null <= d) + 1) / (n_boot + 1))
    half = n // 2
    halves = [float(dvix[:half][back[:half]].mean() - dvix[:half][~back[:half]].mean()), float(dvix[half:][back[half:]].mean() - dvix[half:][~back[half:]].mean())]
    ok = p < 0.05 and d < 0 and all(h < 0 for h in halves)
    return {"n": int(n), "window": window, "share_backwardation": float(back.mean()), "dvix_backwardation": float(dvix[back].mean()), "dvix_contango": float(dvix[~back].mean()),
            "difference": d, "p_value": p, "halves": halves, "verdict": "supported" if ok else "not_supported",
            "reason": f"{window}d change in VIX after backwardation {float(dvix[back].mean()):+.2f} vs contango {float(dvix[~back].mean()):+.2f} pts (diff {d:+.2f}, block-shift p={p:.4f}, halves {halves[0]:+.2f}/{halves[1]:+.2f}; backwardation on {back.mean()*100:.0f}% of days)"}


# ------------------------------------------------------------- model-priced overlays --

def _third_friday(y: int, m: int) -> str:
    d = date(y, m, 1)
    d += timedelta(days=(4 - d.weekday()) % 7)
    return (d + timedelta(days=14)).isoformat()


def monthly_expiry_sessions(days: list[str]) -> list[int]:
    """Indices into the sorted trading days of the standard monthly option expiries: the third Friday of each month, or the
    prior session when it is not a trading day (a Good Friday, as in 2008 and 2019; Juneteenth 2026). Only months whose third Friday
    lies inside the data are listed, so the last expiry is one that has been observed."""
    out: list[int] = []
    if not days:
        return out
    for y in range(int(days[0][:4]), int(days[-1][:4]) + 1):
        for m in range(1, 13):
            tf = _third_friday(y, m)
            if days[0] <= tf <= days[-1]:
                j = bisect.bisect_right(days, tf) - 1
                if not out or j > out[-1]:
                    out.append(j)
    return out


def overlay_backtest(price_rows: Iterable[dict], vix_rows: Iterable[dict], rate_rows: Optional[Iterable[dict]], strategy: str, symbol: str = "SPY",
                     hold_days: int = 21, call_delta: float = 0.30, put_delta: float = -0.30, q: float = 0.0, iv_scale: float = 1.0,
                     calendar: str = "monthly_expiry", offset: int = 0) -> dict:
    """Monthly non-overlapping cycles. Options priced by Black-Scholes at entry with VIX/100 as IV and
    the bill rate; settled at intrinsic value at exit. Returns per-cycle simple returns on the position's notional.
    strategies: covered_call, cash_secured_put, collar, short_straddle, long_straddle, buy_and_hold.

    Cycles (harness rule 10): the claims name monthly options, so ``calendar='monthly_expiry'`` (the default) writes each
    option at one standard monthly expiry's close and settles it at the next (19-25 sessions, about the 21-session month the
    trials state; T is the cycle's own session count / 252). ``calendar='grid'`` is a fixed grid of ``hold_days`` sessions
    starting at session ``offset``: one of ``hold_days`` equally valid phases, a diagnostic, never a verdict basis on its own.

    Options are priced on the price-only close, but every stock leg (buy-and-hold, covered call, collar) also earns the
    dividends paid over the cycle, adjclose[t1]/adjclose[t0] - close[t1]/close[t0] (zero when the rows carry no adjclose),
    just as the cash-secured put earns bill interest on its strike. ``sharpe`` and ``benchmark_sharpe`` are Sharpe ratios
    of returns in excess of the per-cycle bill return exp(r*T) - 1 for funded positions (stock legs, cash-secured put);
    a straddle is unfunded, so its return is already an excess return and is not reduced by the bill."""
    price_rows = list(price_rows)
    px = price_closes(price_rows, symbol); adj = adj_closes(price_rows, symbol); vx = index_closes(vix_rows)
    rt = index_closes(rate_rows) if rate_rows is not None else {}
    days = sorted(d for d in px if d in vx)
    S = np.array([px[d] for d in days]); iv = np.array([vx[d] / 100.0 * iv_scale for d in days])
    A = np.array([adj.get(d, np.nan) for d in days])
    rate = np.array([rt.get(d, np.nan) for d in days]) / 100.0
    rate = np.where(np.isnan(rate), np.nanmean(rate) if np.isfinite(np.nanmean(rate)) else 0.0, rate)
    if calendar == "monthly_expiry":
        ex = monthly_expiry_sessions(days)
        cycles = list(zip(ex[:-1], ex[1:]))
        ppy = 12.0
        cal = "monthly expiry: written at one third-Friday expiry close (prior session on a holiday), settled at the next"
    elif calendar == "grid":
        if not 0 <= offset < hold_days:
            raise ValueError(f"offset {offset} outside the {hold_days} grid phases")
        cycles = [(i, i + hold_days) for i in range(offset, len(S) - hold_days, hold_days)]
        ppy = TRADING_DAYS / hold_days
        cal = f"grid: every {hold_days} sessions from session {offset} (one of {hold_days} phases; diagnostic only, rule 10)"
    else:
        raise ValueError(calendar)
    rets, bh, bill = [], [], []
    for i, i1 in cycles:
        T = (i1 - i) / TRADING_DAYS
        s0, s1, sig, r = S[i], S[i1], max(iv[i], 0.02), rate[i]
        a0, a1 = A[i], A[i1]
        div = float(a1 / a0 - s1 / s0) if (np.isfinite(a0) and np.isfinite(a1) and a0 > 0) else 0.0   # dividend return over the cycle
        dcash = s0 * div                                                                               # per share held
        if strategy == "buy_and_hold":
            pnl, notional = s1 - s0 + dcash, s0
        elif strategy == "covered_call":
            k = bs.strike_for_delta(s0, T, r, sig, call_delta, "call", q); prem = float(bs.price(s0, k, T, r, sig, "call", q))
            pnl, notional = (s1 - s0) + dcash + prem - max(s1 - k, 0.0), s0
        elif strategy == "cash_secured_put":
            k = s0; prem = float(bs.price(s0, k, T, r, sig, "put", q))
            pnl, notional = prem - max(k - s1, 0.0) + k * (math.exp(r * T) - 1), k
        elif strategy == "collar":
            kc = bs.strike_for_delta(s0, T, r, sig, call_delta, "call", q); kp = bs.strike_for_delta(s0, T, r, sig, put_delta, "put", q)
            pc = float(bs.price(s0, kc, T, r, sig, "call", q)); pp = float(bs.price(s0, kp, T, r, sig, "put", q))
            pnl, notional = (s1 - s0) + dcash + pc - pp - max(s1 - kc, 0.0) + max(kp - s1, 0.0), s0
        elif strategy in ("short_straddle", "long_straddle"):
            k = s0; prem = float(bs.price(s0, k, T, r, sig, "call", q)) + float(bs.price(s0, k, T, r, sig, "put", q))
            pay = abs(s1 - k)
            pnl = (prem - pay) if strategy == "short_straddle" else (pay - prem)
            notional = s0
        else:
            raise ValueError(strategy)
        rets.append(pnl / notional); bh.append((s1 - s0) / s0 + div); bill.append(math.exp(r * T) - 1)
    rets, bh, bill = np.array(rets), np.array(bh), np.array(bill)
    funded = strategy not in ("short_straddle", "long_straddle")
    def dd(x):
        c = np.cumprod(1 + x); peak = np.maximum.accumulate(c); return float((c / peak - 1).min())
    lens = [i1 - i for i, i1 in cycles]
    return {"strategy": strategy, "symbol": symbol, "model_priced": True, "iv_scale": iv_scale, "n_cycles": int(len(rets)),
            "first_day": days[cycles[0][0]] if cycles else (days[0] if days else None), "last_day": days[cycles[-1][1]] if cycles else (days[-1] if days else None),
            "calendar": cal, "cycle_sessions": [int(min(lens)), int(max(lens))] if lens else None,
            "mean_cycle_return": float(rets.mean()), "sharpe": float(sharpe_ratio(rets - bill if funded else rets, ppy)), "cagr": float(np.prod(1 + rets) ** (ppy / max(len(rets), 1)) - 1), "max_drawdown": dd(rets),
            "benchmark_sharpe": float(sharpe_ratio(bh - bill, ppy)), "benchmark_cagr": float(np.prod(1 + bh) ** (ppy / max(len(bh), 1)) - 1), "benchmark_max_drawdown": dd(bh),
            "sharpe_basis": ("excess of the per-cycle 3m bill" if funded else "raw (unfunded position: already an excess return)") + "; benchmark excess of the bill",
            "dividends_included": bool(np.isfinite(A).any()), "benchmark_total_return": bool(np.isfinite(A).any()),
            "returns": rets, "benchmark": bh, "bill_returns": bill}


def overlay_verdict(rep: dict, versus: str = "benchmark", n_boot: int = 2000, seed: int = 0) -> dict:
    """Mean-return test of the strategy against buy-and-hold (versus='benchmark') or against zero (versus='zero')."""
    rets = rep["returns"]; inc = rep["benchmark"] if versus == "benchmark" else np.zeros_like(rets)
    arrays = ("returns", "benchmark", "bill_returns")
    if len(rets) < 24:
        return {**{k: v for k, v in rep.items() if k not in arrays}, "verdict": "inconclusive", "reason": f"only {len(rets)} cycles"}
    p = block_bootstrap_pvalue(rets, inc, n_boot=n_boot, seed=seed)
    d = rets - inc
    out = {k: v for k, v in rep.items() if k not in arrays}
    out.update({"p_value_mean_excess": float(p), "mean_excess_per_cycle": float(d.mean()), "halves": [float(d[:len(d) // 2].mean()), float(d[len(d) // 2:].mean())], "versus": versus})
    return out


def _quote_day(available_at: str, days_sorted: list[str]) -> Optional[str]:
    """The trading day the capture's quotes belong to. A capture before 13:30 UTC (pre-open) carries the previous session's
    quotes, so it maps to the last trading day strictly before the capture day; a capture from 13:30 UTC on carries that
    day's live quotes and maps to its own day when that day traded. Weekend and pre-open captures collapse onto one day."""
    s = (available_at or "").strip()
    day = s[:10]
    if len(day) < 10:
        return None
    hhmm = s[11:16] if len(s) >= 16 else "00:00"
    if hhmm >= "13:30":
        j = bisect.bisect_right(days_sorted, day) - 1          # same day allowed
    else:
        j = bisect.bisect_left(days_sorted, day) - 1           # strictly before
    return days_sorted[j] if j >= 0 else None


def implied_move_vs_realised(surface_rows: Iterable[dict], price_rows_by_symbol: dict[str, dict[str, float]], target_dte: int = 30, min_captures: int = 30,
                             n_boot: int = 2000, seed: int = 0) -> dict:
    """From the daily surface captures: the ATM straddle's implied move (% of spot) at the expiry nearest target_dte vs the
    realised |log return| from the quote's own spot to that expiry. Statistic: mean(implied - realised) in %, equal weight per
    capture day (the symbols of one capture are averaged first), and the share of symbol-captures where implied exceeded realised.

    Point in time: the realised move starts at the quote's own underlying (row['underlying']; the close of the quote day when
    absent), not at the close of the capture day, because pre-open captures carry the previous session's quotes. DTE and the
    ~target_dte expiry are measured from that quote day.

    Dependence: consecutive daily captures share all but one session of their realised windows and the symbols are
    cross-correlated, so the test is the studentized block bootstrap of the per-day series with the block at least as long as
    the realised window (in captures). The sample gate counts independent expiry cycles (non-overlapping captures: the next
    one counted starts at or after the previous one's expiry), not rows: fewer than ``min_captures`` (the trial's min_n) is
    inconclusive. Needs the expiry to have passed."""
    by_capture: dict[tuple, list[dict]] = {}
    for r in surface_rows:
        v = r["value"]; cap = (r.get("available_at") or "")[:10]
        by_capture.setdefault((v["symbol"], cap), []).append({**v, "_available_at": r.get("available_at") or ""})
    sorted_days = {s: sorted(px) for s, px in price_rows_by_symbol.items() if px}
    pairs = []
    for (sym, cap), rows in by_capture.items():
        px = price_rows_by_symbol.get(sym)
        if not px:
            continue
        qd = _quote_day(rows[0]["_available_at"], sorted_days[sym])
        if qd is None:
            continue
        q_date = datetime.strptime(qd, "%Y-%m-%d").date()
        def dte_q(v):
            try:
                return (datetime.strptime(v["expiry"], "%Y-%m-%d").date() - q_date).days
            except (KeyError, ValueError):
                return 10 ** 6
        row = min(rows, key=lambda v: abs(dte_q(v) - target_dte))
        exp = row["expiry"]
        sd = sorted_days[sym]
        j = bisect.bisect_right(sd, exp) - 1                      # last close on or before the expiry
        exp_day = sd[j] if j >= 0 else None
        if exp_day is None or exp_day <= qd or exp > sd[-1]:
            continue                                              # expiry not yet observed
        spot = row.get("underlying")
        anchor = float(spot) if spot is not None and float(spot) > 0 else px.get(qd)
        if not anchor or anchor <= 0 or row.get("implied_move_pct") is None:
            continue
        realised = abs(math.log(px[exp_day] / anchor)) * 100
        pairs.append((sym, qd, exp_day, float(row["implied_move_pct"]), realised))
    # one observation per capture (quote) day: mean over the symbols resolved that day
    by_day: dict[str, list] = {}
    for sym, qd, exp_day, imp, real in pairs:
        by_day.setdefault(qd, []).append((imp, real, exp_day))
    qdays = sorted(by_day)
    imp_d = np.array([np.mean([x[0] for x in by_day[d]]) for d in qdays]); real_d = np.array([np.mean([x[1] for x in by_day[d]]) for d in qdays])
    exp_of = {d: max(x[2] for x in by_day[d]) for d in qdays}
    n_cycles, nxt = 0, None
    for d in qdays:                                               # greedy non-overlapping captures
        if nxt is None or d >= nxt:
            n_cycles += 1; nxt = exp_of[d]
    block_len = max([bisect.bisect_left(qdays, exp_of[d]) - i for i, d in enumerate(qdays)], default=1)   # captures sharing d's window
    n = len(qdays)
    out = {"n_resolved_captures": n, "n_symbol_captures": len(pairs), "n_independent_cycles": n_cycles, "n_captures_total": len(by_capture),
           "min_captures": min_captures, "min_n_unit": "independent expiry cycles", "block_len": int(block_len),
           "anchor": "quote's own underlying (row['underlying']); DTE from the quote day"}
    if n:
        d = imp_d - real_d
        out.update({"mean_implied_pct": float(imp_d.mean()), "mean_realised_pct": float(real_d.mean()), "mean_diff_pct": float(d.mean()),
                    "share_implied_exceeds": float(np.mean([p[3] > p[4] for p in pairs]))})
    if n_cycles < min_captures or n < 8:
        out.update({"verdict": "inconclusive", "reason": f"{n_cycles}/{min_captures} independent ~{target_dte}d expiry cycles ({n} resolved capture days, "
                                                          f"{len(pairs)} symbol-captures; overlapping captures share one realised path; chain capture started 2026-10-14)"})
        return out
    from mandel.experiments.underlying2 import _verdict          # lazy: underlying2 -> underlying -> volatility
    d = imp_d - real_d
    p = block_bootstrap_pvalue(imp_d, real_d, n_boot=n_boot, block_len=block_len, seed=seed)
    verdict, why = _verdict([("mean(implied - realised) > 0", d.mean() > 0), (f"block-bootstrap p < 0.05 (per-day series, block {block_len} captures)", p < 0.05)])
    out.update({"p_value": float(p), "verdict": verdict,
                "reason": f"implied move {imp_d.mean():.2f}% vs realised {real_d.mean():.2f}% over {n} resolved capture days ({n_cycles} independent expiry cycles; "
                          f"implied larger on {out['share_implied_exceeds']*100:.0f}% of {len(pairs)} symbol-captures), block-bootstrap p={p:.3f}; {why}"})
    return out
