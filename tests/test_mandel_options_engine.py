"""Black-Scholes identities, implied vol round trip, delta-strike inversion, multi-leg payoffs."""

import math

import numpy as np
import pytest

from mandel.options import bs
from mandel.options.payoff import Leg, Position, priced_leg

S, K, T, r, sig = 100.0, 100.0, 0.5, 0.03, 0.25


def test_put_call_parity_and_known_value():
    c = float(bs.price(S, K, T, r, sig, "call")); p = float(bs.price(S, K, T, r, sig, "put"))
    assert abs((c - p) - (S - K * math.exp(-r * T))) < 1e-9
    assert abs(c - 7.7603) < 2e-3                       # d1=0.1732, d2=-0.0035: 100 N(d1) - 98.511 N(d2) = 7.760
    assert float(bs.price(S, K, 0.0, r, sig, "call")) == 0.0 and float(bs.price(120, K, 0.0, r, sig, "call")) == 20.0


def test_greeks_signs_and_finite_differences():
    g = bs.greeks(S, K, T, r, sig, "call")
    assert 0.5 < g["delta"] < 0.7 and g["gamma"] > 0 and g["vega"] > 0 and g["theta"] < 0
    h = 1e-3
    fd_delta = (float(bs.price(S + h, K, T, r, sig)) - float(bs.price(S - h, K, T, r, sig))) / (2 * h)
    fd_vega = (float(bs.price(S, K, T, r, sig + h)) - float(bs.price(S, K, T, r, sig - h))) / (2 * h)
    assert abs(fd_delta - g["delta"]) < 1e-5 and abs(fd_vega - g["vega"]) < 1e-4
    gp = bs.greeks(S, K, T, r, sig, "put")
    assert abs((g["delta"] - gp["delta"]) - 1.0) < 1e-9       # call delta - put delta = e^{-qT} = 1


def test_implied_vol_round_trip_and_bounds():
    for kind in ("call", "put"):
        for k in (80.0, 100.0, 125.0):
            px = float(bs.price(S, k, T, r, 0.37, kind))
            assert abs(bs.implied_vol(px, S, k, T, r, kind) - 0.37) < 1e-6
    assert math.isnan(bs.implied_vol(S + 1, S, S, T, r, "call"))   # above the upper bound (call worth more than spot)


def test_strike_for_delta_inverts():
    k = bs.strike_for_delta(S, T, r, sig, 0.30, "call")
    assert abs(float(bs.greeks(S, k, T, r, sig, "call")["delta"]) - 0.30) < 1e-6
    kp = bs.strike_for_delta(S, T, r, sig, -0.25, "put")
    assert abs(float(bs.greeks(S, kp, T, r, sig, "put")["delta"]) + 0.25) < 1e-6 and kp < S < k


def test_payoffs_of_classic_structures():
    # bull call spread 95/105: max profit = 10 - debit, max loss = debit
    long = priced_leg("call", "long", S, 95, T, r, sig); short = priced_leg("call", "short", S, 105, T, r, sig)
    bcs = Position([long, short], "bull call spread")
    ex = bcs.extremes(S); debit = bcs.net_debit()
    assert debit > 0 and abs(ex["max_profit"] - (10 - debit)) < 1e-6 and abs(ex["max_loss"] + debit) < 1e-6
    assert not ex["profit_unbounded"] and not ex["loss_unbounded"]
    be = bcs.breakevens(S); assert len(be) == 1 and abs(be[0] - (95 + debit)) < 1e-3
    # covered call: long stock + short call; profit capped, loss to zero
    cc = Position([Leg("underlying", "long", 1, entry=S), priced_leg("call", "short", S, 105, T, r, sig)], "covered call")
    exc = cc.extremes(S); credit = -cc.net_debit()
    assert abs(exc["max_profit"] - (5 + credit)) < 1e-6 and not exc["profit_unbounded"] and exc["pnl_at_grid_low"] < -50
    # long straddle: unbounded upside, loss = both premiums, two breakevens
    st = Position([priced_leg("call", "long", S, 100, T, r, sig), priced_leg("put", "long", S, 100, T, r, sig)], "straddle")
    exs = st.extremes(S)
    assert exs["profit_unbounded"] and abs(exs["max_loss"] + st.net_debit()) < 1e-6 and len(st.breakevens(S)) == 2
    # iron condor 90/95/105/110 short: credit = max profit; max loss = 5 - credit
    ic = Position([priced_leg("put", "long", S, 90, T, r, sig), priced_leg("put", "short", S, 95, T, r, sig),
                   priced_leg("call", "short", S, 105, T, r, sig), priced_leg("call", "long", S, 110, T, r, sig)], "iron condor")
    exi = ic.extremes(S); cr = -ic.net_debit()
    assert cr > 0 and abs(exi["max_profit"] - cr) < 1e-6 and abs(exi["max_loss"] + (5 - cr)) < 1e-6
    # position greeks: ATM straddle is near delta-neutral, long gamma/vega, short theta
    g = st.greeks(S, r)
    assert abs(g["delta"]) < 0.2 and g["gamma"] > 0 and g["vega"] > 0 and g["theta"] < 0
