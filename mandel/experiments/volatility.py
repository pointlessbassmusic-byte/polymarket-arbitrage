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
are an upper bound. Every result carries ``model_priced: True``.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
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
              n_boot: int = 2000, seed: int = 0) -> dict:
    idx = index_closes(skew_rows); px = price_closes(price_rows, symbol)
    days, sk, S = _aligned(idx, px)
    n = len(S) - window
    if n < 500:
        return {"n": n, "verdict": "inconclusive", "reason": f"only {n} aligned days"}
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
    ok = p < 0.05 and d > 0 and all(h > 0 for h in halves if not math.isnan(h))
    return {"n": int(n), "window": window, "drop": drop, "crash_prob_top_minus_bottom": d, "p_value": p, "halves": halves,
            "crash_prob_top": float((fwd[sk >= hi_q] < drop).mean()), "crash_prob_bottom": float((fwd[sk <= lo_q] < drop).mean()),
            "mean_fwd_top": float(fwd[sk >= hi_q].mean()), "mean_fwd_bottom": float(fwd[sk <= lo_q].mean()),
            "verdict": "supported" if ok else "not_supported",
            "reason": f"P({window}d drop < {drop:.0%}) top SKEW quintile {float((fwd[sk >= hi_q] < drop).mean()):.3f} vs bottom {float((fwd[sk <= lo_q] < drop).mean()):.3f} (diff {d:+.3f}, block-shift p={p:.3f}, halves {halves[0]:+.3f}/{halves[1]:+.3f})"}


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

def overlay_backtest(price_rows: Iterable[dict], vix_rows: Iterable[dict], rate_rows: Optional[Iterable[dict]], strategy: str, symbol: str = "SPY",
                     hold_days: int = 21, call_delta: float = 0.30, put_delta: float = -0.30, q: float = 0.0, iv_scale: float = 1.0) -> dict:
    """Monthly (hold_days) non-overlapping cycles. Options priced by Black-Scholes at entry with VIX/100 as IV and
    the bill rate; settled at intrinsic value at exit. Returns per-cycle simple returns on the position's notional.
    strategies: covered_call, cash_secured_put, collar, short_straddle, long_straddle, buy_and_hold."""
    px = price_closes(price_rows, symbol); vx = index_closes(vix_rows)
    rt = index_closes(rate_rows) if rate_rows is not None else {}
    days = sorted(d for d in px if d in vx)
    S = np.array([px[d] for d in days]); iv = np.array([vx[d] / 100.0 * iv_scale for d in days])
    rate = np.array([rt.get(d, np.nan) for d in days]) / 100.0
    rate = np.where(np.isnan(rate), np.nanmean(rate) if np.isfinite(np.nanmean(rate)) else 0.0, rate)
    T = hold_days / TRADING_DAYS
    rets, bh = [], []
    for i in range(0, len(S) - hold_days, hold_days):
        s0, s1, sig, r = S[i], S[i + hold_days], max(iv[i], 0.02), rate[i]
        if strategy == "buy_and_hold":
            pnl, notional = s1 - s0, s0
        elif strategy == "covered_call":
            k = bs.strike_for_delta(s0, T, r, sig, call_delta, "call", q); prem = float(bs.price(s0, k, T, r, sig, "call", q))
            pnl, notional = (s1 - s0) + prem - max(s1 - k, 0.0), s0
        elif strategy == "cash_secured_put":
            k = s0; prem = float(bs.price(s0, k, T, r, sig, "put", q))
            pnl, notional = prem - max(k - s1, 0.0) + k * (math.exp(r * T) - 1), k
        elif strategy == "collar":
            kc = bs.strike_for_delta(s0, T, r, sig, call_delta, "call", q); kp = bs.strike_for_delta(s0, T, r, sig, put_delta, "put", q)
            pc = float(bs.price(s0, kc, T, r, sig, "call", q)); pp = float(bs.price(s0, kp, T, r, sig, "put", q))
            pnl, notional = (s1 - s0) + pc - pp - max(s1 - kc, 0.0) + max(kp - s1, 0.0), s0
        elif strategy in ("short_straddle", "long_straddle"):
            k = s0; prem = float(bs.price(s0, k, T, r, sig, "call", q)) + float(bs.price(s0, k, T, r, sig, "put", q))
            pay = abs(s1 - k)
            pnl = (prem - pay) if strategy == "short_straddle" else (pay - prem)
            notional = s0
        else:
            raise ValueError(strategy)
        rets.append(pnl / notional); bh.append((s1 - s0) / s0)
    rets, bh = np.array(rets), np.array(bh)
    ppy = TRADING_DAYS / hold_days
    def dd(x):
        c = np.cumprod(1 + x); peak = np.maximum.accumulate(c); return float((c / peak - 1).min())
    return {"strategy": strategy, "symbol": symbol, "model_priced": True, "iv_scale": iv_scale, "n_cycles": int(len(rets)), "first_day": days[0], "last_day": days[min(len(days) - 1, (len(rets)) * hold_days)],
            "mean_cycle_return": float(rets.mean()), "sharpe": float(sharpe_ratio(rets, ppy)), "cagr": float(np.prod(1 + rets) ** (ppy / max(len(rets), 1)) - 1), "max_drawdown": dd(rets),
            "benchmark_sharpe": float(sharpe_ratio(bh, ppy)), "benchmark_cagr": float(np.prod(1 + bh) ** (ppy / max(len(bh), 1)) - 1), "benchmark_max_drawdown": dd(bh),
            "returns": rets, "benchmark": bh}


def overlay_verdict(rep: dict, versus: str = "benchmark", n_boot: int = 2000, seed: int = 0) -> dict:
    """Mean-return test of the strategy against buy-and-hold (versus='benchmark') or against zero (versus='zero')."""
    rets = rep["returns"]; inc = rep["benchmark"] if versus == "benchmark" else np.zeros_like(rets)
    if len(rets) < 24:
        return {**{k: v for k, v in rep.items() if k not in ("returns", "benchmark")}, "verdict": "inconclusive", "reason": f"only {len(rets)} cycles"}
    p = block_bootstrap_pvalue(rets, inc, n_boot=n_boot, seed=seed)
    d = rets - inc
    out = {k: v for k, v in rep.items() if k not in ("returns", "benchmark")}
    out.update({"p_value_mean_excess": float(p), "mean_excess_per_cycle": float(d.mean()), "halves": [float(d[:len(d) // 2].mean()), float(d[len(d) // 2:].mean())], "versus": versus})
    return out
