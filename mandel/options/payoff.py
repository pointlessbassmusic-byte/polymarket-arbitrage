"""Multi-leg positions: payoff at expiry, P&L, breakevens, max profit / loss, aggregate Greeks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np

from mandel.options import bs

Instrument = Literal["call", "put", "underlying", "future"]


@dataclass(frozen=True)
class Leg:
    instrument: Instrument
    side: Literal["long", "short"]
    qty: float = 1.0                 # contracts (1 contract = 1 unit of underlying here; multiply by 100 outside if needed)
    strike: Optional[float] = None    # options only
    premium: float = 0.0              # price paid (long) or received (short) per unit
    entry: Optional[float] = None     # underlying / future entry price
    T: float = 0.0                    # years to expiry (0 for the payoff-at-expiry view)
    sigma: float = 0.0                # IV used for Greeks

    @property
    def sign(self) -> float:
        return 1.0 if self.side == "long" else -1.0

    def intrinsic(self, S: np.ndarray) -> np.ndarray:
        if self.instrument == "call":
            return np.maximum(S - self.strike, 0.0)
        if self.instrument == "put":
            return np.maximum(self.strike - S, 0.0)
        return S - (self.entry if self.entry is not None else 0.0)

    def cost(self) -> float:
        """Cash paid at entry (positive = debit). Underlying/future legs carry no premium here (their P&L is in intrinsic)."""
        return self.premium if self.instrument in ("call", "put") else 0.0


@dataclass
class Position:
    legs: list[Leg] = field(default_factory=list)
    name: str = ""

    def net_debit(self) -> float:
        return float(sum(l.sign * l.qty * l.cost() for l in self.legs))

    def payoff(self, S) -> np.ndarray:
        """Value at expiry (before subtracting premium)."""
        S = np.asarray(S, dtype=float)
        return sum((l.sign * l.qty * l.intrinsic(S) for l in self.legs), np.zeros_like(S))

    def pnl(self, S) -> np.ndarray:
        return self.payoff(S) - self.net_debit()

    def grid(self, center: float, width: float = 0.6, n: int = 2001) -> np.ndarray:
        return np.linspace(max(center * (1 - width), 0.0), center * (1 + width), n)

    def breakevens(self, center: float, width: float = 0.6, n: int = 4001) -> list[float]:
        S = self.grid(center, width, n); p = self.pnl(S)
        out = []
        for i in range(len(S) - 1):
            if p[i] == 0:
                out.append(float(S[i]))
            elif p[i] * p[i + 1] < 0:
                out.append(float(S[i] - p[i] * (S[i + 1] - S[i]) / (p[i + 1] - p[i])))
        return sorted(set(round(x, 6) for x in out))

    def extremes(self, center: float, width: float = 0.6) -> dict:
        """Max profit / loss on the grid, with 'unbounded' flags from the slope at the grid edges."""
        S = self.grid(center, width); p = self.pnl(S)
        slope_hi = (p[-1] - p[-2]) / (S[-1] - S[-2]); slope_lo = (p[1] - p[0]) / (S[1] - S[0])
        return {"max_profit": float(p.max()), "max_loss": float(p.min()),
                "profit_unbounded": bool(slope_hi > 1e-9), "loss_unbounded": bool(slope_hi < -1e-9),
                "pnl_at_grid_low": float(p[0]), "slope_low": float(slope_lo), "slope_high": float(slope_hi)}

    def greeks(self, S: float, r: float = 0.0, q: float = 0.0) -> dict:
        tot = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
        for l in self.legs:
            if l.instrument in ("call", "put"):
                g = bs.greeks(S, l.strike, max(l.T, 1e-9), r, max(l.sigma, 1e-9), l.instrument, q)
                for k in tot:
                    tot[k] += l.sign * l.qty * float(g[k])
            else:
                tot["delta"] += l.sign * l.qty
        return tot

    def describe(self, center: float) -> dict:
        ex = self.extremes(center)
        return {"name": self.name, "legs": [(l.side, l.qty, l.instrument, l.strike, round(l.premium, 4)) for l in self.legs],
                "net_debit": round(self.net_debit(), 6), "breakevens": self.breakevens(center), **ex}


def priced_leg(instrument: Instrument, side: str, S: float, strike: float, T: float, r: float, sigma: float, qty: float = 1.0, q: float = 0.0) -> Leg:
    """Option leg priced by Black-Scholes at entry (model-priced: for logic tests, not for live prices)."""
    prem = float(bs.price(S, strike, T, r, sigma, instrument, q)) if instrument in ("call", "put") else 0.0
    return Leg(instrument, side, qty, strike, prem, entry=S if instrument in ("underlying", "future") else None, T=T, sigma=sigma)
