"""
Strategy templates: turn a leg description (as the strategy library states it) into a priced Position.
=====================================================================================================

The library describes legs with free-text rules such as ``strike_rule: "ATM"``, ``"OTM 5%"``, ``"ITM 10%"``,
``"delta 0.30"``, ``"K1" .. "K4"`` (ordered strikes, K1 lowest) or ``"same as leg 1"``. ``build_position`` parses
these tolerantly, prices each option leg with Black-Scholes at the given spot / IV / time (model-priced), and
returns a ``Position`` the payoff engine can analyse. Unparseable rules fall back to ordered strikes spaced
``step`` apart around spot, so every template in the library can at least be drawn and sanity-checked.
"""

from __future__ import annotations

import re
from typing import Optional

from mandel.options import bs
from mandel.options.payoff import Leg, Position

_PCT = re.compile(r"(-?\d+(?:\.\d+)?)\s*%")
_DELTA = re.compile(r"delta\s*(?:of\s*)?(-?\d*\.?\d+)", re.I)
_K = re.compile(r"\bK\s*(\d)\b", re.I)
_NUM = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*$")


def _strike_from_rule(rule: str, S: float, T: float, r: float, sigma: float, kind: str, step: float, k_slots: dict, q: float) -> float:
    s = (rule or "").strip()
    low = s.lower()
    m = _K.search(s)
    if m:
        i = int(m.group(1))
        if i not in k_slots:
            # ordered strikes K1 < K2 < ... centred on spot
            n = max(k_slots.get("_n", 0), i); k_slots["_n"] = n
        return k_slots.setdefault(i, S * (1 + step * (i - (k_slots["_n"] + 1) / 2)))
    if _NUM.match(s):
        return float(s)
    md = _DELTA.search(s)
    if md:
        d = float(md.group(1))
        if kind == "put" and d > 0:
            d = -d
        return bs.strike_for_delta(S, T, r, sigma, d, kind, q)
    mp = _PCT.search(s)
    pct = float(mp.group(1)) / 100 if mp else None
    if "atm" in low and pct is None:
        return S
    if "otm" in low or "out of the money" in low or "out-of-the-money" in low:
        p = pct if pct is not None else step
        return S * (1 + p) if kind == "call" else S * (1 - p)
    if "itm" in low or "in the money" in low or "in-the-money" in low:
        p = pct if pct is not None else step
        return S * (1 - p) if kind == "call" else S * (1 + p)
    if pct is not None:                       # "+5%" / "-5%" relative to spot
        return S * (1 + pct)
    if "spot" in low or "atm" in low or "at the money" in low:
        return S
    return S                                  # unknown: ATM (flagged by the caller via parsed=False)


def parse_strike_rule(rule: str) -> bool:
    """True when the rule is one the builder understands (used to flag templates that fell back to defaults)."""
    s = (rule or "").strip().lower()
    return bool(_K.search(s) or _NUM.match(s) or _DELTA.search(s) or _PCT.search(s) or any(w in s for w in ("atm", "otm", "itm", "at the money", "out of the money", "in the money", "spot")))


def build_position(template: dict, S: float, T: float = 30 / 365, r: float = 0.04, sigma: float = 0.20, step: float = 0.05, q: float = 0.0) -> tuple[Position, dict]:
    """Returns (Position, info). info: {parsed: bool, legs: [...], model_priced: True}. Underlying legs enter at S."""
    legs, parsed, k_slots = [], True, {}
    # pre-pass: count K-slots so ordered strikes are centred
    for lg in template.get("legs", []):
        m = _K.search(str(lg.get("strike_rule", "")))
        if m:
            k_slots["_n"] = max(k_slots.get("_n", 0), int(m.group(1)))
    for lg in template.get("legs", []):
        inst = (lg.get("instrument") or "").lower(); side = (lg.get("side") or "long").lower()
        qty = float(lg.get("qty") or 1.0)
        if inst in ("underlying", "stock", "future", "futures", "spot"):
            legs.append(Leg("underlying" if inst != "future" else "future", side, qty, entry=S)); continue
        if inst not in ("call", "put"):
            parsed = False; continue
        rule = str(lg.get("strike_rule", ""))
        if not parse_strike_rule(rule):
            parsed = False
        K = _strike_from_rule(rule, S, T, r, sigma, inst, step, k_slots, q)
        prem = float(bs.price(S, K, T, r, sigma, inst, q))
        legs.append(Leg(inst, side, qty, K, prem, T=T, sigma=sigma))
    pos = Position(legs, template.get("name", template.get("slug", "")))
    return pos, {"parsed": parsed, "model_priced": True, "n_legs": len(legs), "legs": [(l.side, l.qty, l.instrument, None if l.strike is None else round(l.strike, 4)) for l in legs]}


def classify_risk(pos: Position, S: float) -> dict:
    """Risk reading from the payoff grid over [0, 2S]: bounded loss, loss as a fraction of spot (per unit),
    'defined_risk' = bounded and max loss at most half of spot (spreads and wings), 'full_downside' = bounded but
    the position can lose most of spot (naked puts, covered calls, long stock)."""
    ex = pos.extremes(S, width=1.0)
    units = max(1.0, sum(abs(l.qty) for l in pos.legs))
    frac = -ex["max_loss"] / (S * units) if ex["max_loss"] < 0 else 0.0
    return {"max_loss_bounded": not ex["loss_unbounded"], "max_loss_fraction_of_spot": float(frac),
            "defined_risk": (not ex["loss_unbounded"]) and frac <= 0.5, "full_downside": (not ex["loss_unbounded"]) and frac > 0.5,
            "upside_unbounded": ex["profit_unbounded"], "downside_unbounded": ex["loss_unbounded"], **ex, "breakevens": pos.breakevens(S)}
