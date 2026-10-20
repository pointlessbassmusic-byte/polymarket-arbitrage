"""Black-Scholes-Merton pricing, Greeks and implied volatility (vectorised, numpy only)."""

from __future__ import annotations

import math
from typing import Literal

import numpy as np

Kind = Literal["call", "put"]
_SQRT2 = math.sqrt(2.0)


def _ncdf(x):
    x = np.asarray(x, dtype=float)
    return 0.5 * (1.0 + _erf(x / _SQRT2))


def _erf(x):
    # vectorised erf via math.erf (exact to double precision); fine for the array sizes used here
    return np.vectorize(math.erf, otypes=[float])(x)


def _npdf(x):
    x = np.asarray(x, dtype=float)
    return np.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1d2(S, K, T, r, sigma, q):
    S, K, T, sigma = (np.asarray(a, dtype=float) for a in (S, K, T, sigma))
    T = np.maximum(T, 1e-12); sigma = np.maximum(sigma, 1e-12)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return d1, d1 - sigma * np.sqrt(T)


def _price_scalar(S: float, K: float, T: float, r: float, sigma: float, kind: str, q: float) -> np.float64:
    """price() for scalar inputs, operation for operation (np.exp / np.log on floats are bit-identical to the 0-d array
    path, math.exp is not); the array path costs ~40 us a call inside Python loops, this one ~3 us."""
    if kind not in ("call", "put"):
        raise ValueError("kind must be call or put")
    if T <= 0:
        return np.float64(max(S - K, 0.0) if kind == "call" else max(K - S, 0.0))
    sig = max(sigma, 1e-12); Tc = max(T, 1e-12)
    d1 = (np.log(S / K) + (r - q + 0.5 * sig ** 2) * Tc) / (sig * math.sqrt(Tc))
    d2 = d1 - sig * math.sqrt(Tc)
    n = lambda x: 0.5 * (1.0 + math.erf(x / _SQRT2))
    if kind == "call":
        return np.float64(S * np.exp(-q * T) * n(d1) - K * np.exp(-r * T) * n(d2))
    return np.float64(K * np.exp(-r * T) * n(-d2) - S * np.exp(-q * T) * n(-d1))


def price(S, K, T, r, sigma, kind: Kind = "call", q: float = 0.0):
    """European price. T in years; r, q continuous. At T<=0 returns intrinsic value."""
    if all(np.ndim(a) == 0 for a in (S, K, T, r, sigma, q)):
        return _price_scalar(float(S), float(K), float(T), float(r), float(sigma), kind, float(q))
    S, K, T = (np.asarray(a, dtype=float) for a in (S, K, T))
    d1, d2 = _d1d2(S, K, T, r, sigma, q)
    if kind == "call":
        val = S * np.exp(-q * T) * _ncdf(d1) - K * np.exp(-r * T) * _ncdf(d2)
        intrinsic = np.maximum(S - K, 0.0)
    elif kind == "put":
        val = K * np.exp(-r * T) * _ncdf(-d2) - S * np.exp(-q * T) * _ncdf(-d1)
        intrinsic = np.maximum(K - S, 0.0)
    else:
        raise ValueError("kind must be call or put")
    return np.where(T <= 0, intrinsic, val)


def greeks(S, K, T, r, sigma, kind: Kind = "call", q: float = 0.0) -> dict:
    """delta, gamma, vega (per 1.00 of vol), theta (per year, negative = decay), rho (per 1.00 of rate)."""
    S, K, T = (np.asarray(a, dtype=float) for a in (S, K, T))
    T = np.maximum(T, 1e-12)
    d1, d2 = _d1d2(S, K, T, r, sigma, q)
    sig = np.maximum(np.asarray(sigma, dtype=float), 1e-12)
    disc_q, disc_r = np.exp(-q * T), np.exp(-r * T)
    pdf = _npdf(d1)
    gamma = disc_q * pdf / (S * sig * np.sqrt(T))
    vega = S * disc_q * pdf * np.sqrt(T)
    if kind == "call":
        delta = disc_q * _ncdf(d1)
        theta = -S * disc_q * pdf * sig / (2 * np.sqrt(T)) - r * K * disc_r * _ncdf(d2) + q * S * disc_q * _ncdf(d1)
        rho = K * T * disc_r * _ncdf(d2)
    else:
        delta = -disc_q * _ncdf(-d1)
        theta = -S * disc_q * pdf * sig / (2 * np.sqrt(T)) + r * K * disc_r * _ncdf(-d2) - q * S * disc_q * _ncdf(-d1)
        rho = -K * T * disc_r * _ncdf(-d2)
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


def implied_vol(target, S, K, T, r, kind: Kind = "call", q: float = 0.0, tol: float = 1e-8, max_iter: int = 100) -> float:
    """Scalar implied volatility by bracketed bisection (robust to deep ITM/OTM). Returns nan when the price is
    outside no-arbitrage bounds."""
    S, K, T, target = float(S), float(K), float(T), float(target)
    if T <= 0:
        return float("nan")
    lo_bound = max(0.0, (S * math.exp(-q * T) - K * math.exp(-r * T)) * (1 if kind == "call" else -1))
    hi_bound = S * math.exp(-q * T) if kind == "call" else K * math.exp(-r * T)
    if target < lo_bound - 1e-12 or target > hi_bound + 1e-12:
        return float("nan")
    lo, hi = 1e-6, 5.0
    f_lo = float(price(S, K, T, r, lo, kind, q)) - target
    f_hi = float(price(S, K, T, r, hi, kind, q)) - target
    if f_lo > 0:
        return 0.0
    if f_hi < 0:
        return float("nan")
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = float(price(S, K, T, r, mid, kind, q)) - target
        if abs(f_mid) < tol:
            return mid
        if f_mid < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def strike_for_delta(S, T, r, sigma, delta_target: float, kind: Kind, q: float = 0.0) -> float:
    """Strike whose BSM delta equals delta_target (call delta in (0,1); put delta in (-1,0)). Closed form."""
    from math import exp, log, sqrt
    T = max(float(T), 1e-12); sigma = max(float(sigma), 1e-12)
    if kind == "call":
        nd1 = min(max(delta_target * exp(q * T), 1e-9), 1 - 1e-9)
    else:
        nd1 = min(max(1.0 + delta_target * exp(q * T), 1e-9), 1 - 1e-9)   # put delta = -e^{-qT} N(-d1)
    d1 = _ninv(nd1)
    return float(S * exp(-(d1 * sigma * sqrt(T)) + (r - q + 0.5 * sigma ** 2) * T))


def _ninv(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation, |err| < 1.2e-9)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        qq = math.sqrt(-2 * math.log(p))
        return (((((c[0] * qq + c[1]) * qq + c[2]) * qq + c[3]) * qq + c[4]) * qq + c[5]) / ((((d[0] * qq + d[1]) * qq + d[2]) * qq + d[3]) * qq + 1)
    if p <= phigh:
        qq = p - 0.5; rr = qq * qq
        return (((((a[0] * rr + a[1]) * rr + a[2]) * rr + a[3]) * rr + a[4]) * rr + a[5]) * qq / (((((b[0] * rr + b[1]) * rr + b[2]) * rr + b[3]) * rr + b[4]) * rr + 1)
    qq = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * qq + c[1]) * qq + c[2]) * qq + c[3]) * qq + c[4]) * qq + c[5]) / ((((d[0] * qq + d[1]) * qq + d[2]) * qq + d[3]) * qq + 1)
