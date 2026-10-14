"""Promotion capture, hedged: the arithmetic for "buy $X of crypto, get
$Y", deposit matches and transfer bonuses, and whether moving capital
from one offer to the next is worth the lock-up.

    python -m cryptobot.promos --bonus 250 --required 1000 --hold-days 30
    python -m cryptobot.promos --bonus 250 --required 1000 --hold-days 30 --margin-apr 0.06

The model: hold the required position for the hold period, short the
same notional on a US perp so price risk is gone (fees both ways plus
funding), optionally fund the position on margin, pay tax on the bonus.
What is left is the net dollar value of the offer and its annualised
return on the capital it ties up, which is the number to compare with
the next offer and with T-bills. See RESEARCH-2026-10.md addendum 7
for the offers found and the rules that stop a "bounce".
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field


@dataclass
class Promo:
    name: str
    bonus_usd: float
    required_usd: float
    hold_days: int = 0            # how long the position or deposit must stay
    clawback_days: int = 0        # bonus is taken back if funds leave before this
    kind: str = "crypto_buy"      # crypto_buy | deposit | transfer
    needs_price_exposure: bool = True   # a crypto buy must be held in a coin; a cash deposit need not
    notes: str = ""
    extra: dict = field(default_factory=dict)


def hedged_capture(bonus_usd: float, required_usd: float, hold_days: float, *,
                   needs_price_exposure: bool = True,
                   funding_8h: float = 0.0001,     # 0.01% per 8h paid by the short while held
                   perp_fee: float = 0.0004,       # 4 bp a side (Kalshi taker)
                   spot_fee: float = 0.0040,       # Kraken tier-1 maker since 2026-07-09; 0 on a zero-fee plan
                   spread: float = 0.0005,         # half-spread each way, each leg
                   margin_apr: float = 0.0,        # borrow cost if the capital is borrowed
                   tax_rate: float = 0.0) -> dict:
    """Net value of an offer after hedging, fees, funding, margin and tax."""
    lock_days = max(hold_days, 0.0)
    spot_cost = required_usd * 2 * (spot_fee + spread) if needs_price_exposure else 0.0
    hedge_cost = 0.0
    if needs_price_exposure and lock_days > 0:
        periods = lock_days * 3
        hedge_cost = required_usd * (2 * (perp_fee + spread) + max(funding_8h, 0.0) * periods)
    margin_cost = required_usd * margin_apr * lock_days / 365.0
    tax = bonus_usd * tax_rate
    net = bonus_usd - spot_cost - hedge_cost - margin_cost - tax
    capital_days = required_usd * max(lock_days, 1.0)
    return {"bonus": bonus_usd, "spot_cost": spot_cost, "hedge_cost": hedge_cost,
            "margin_cost": margin_cost, "tax": tax, "net": net,
            "net_pct_of_required": net / required_usd if required_usd else 0.0,
            "annualised_on_capital": net / capital_days * 365.0 if capital_days else 0.0}


def rank(promos: list[Promo], **costs) -> list[tuple[Promo, dict]]:
    """Offers by annualised net return on the capital they tie up; the
    clawback window counts as the lock-up when it is longer."""
    out = []
    for p in promos:
        lock = max(p.hold_days, p.clawback_days)
        r = hedged_capture(p.bonus_usd, p.required_usd, lock, needs_price_exposure=p.needs_price_exposure, **costs)
        out.append((p, r))
    out.sort(key=lambda t: t[1]["annualised_on_capital"], reverse=True)
    return out


def render(p: Promo, r: dict) -> str:
    lock = max(p.hold_days, p.clawback_days)
    return (f"{p.name}: bonus ${r['bonus']:,.0f} on ${p.required_usd:,.0f} locked {lock}d -> net ${r['net']:,.2f} "
            f"({r['net_pct_of_required']*100:+.1f}% of required, {r['annualised_on_capital']*100:+.1f}%/yr on capital); "
            f"costs: spot ${r['spot_cost']:.2f} hedge ${r['hedge_cost']:.2f} margin ${r['margin_cost']:.2f} tax ${r['tax']:.2f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="offer")
    ap.add_argument("--bonus", type=float, required=True)
    ap.add_argument("--required", type=float, required=True)
    ap.add_argument("--hold-days", type=float, default=0)
    ap.add_argument("--clawback-days", type=float, default=0)
    ap.add_argument("--cash", action="store_true", help="a cash deposit, no price exposure to hedge")
    ap.add_argument("--funding-8h", type=float, default=0.0001)
    ap.add_argument("--perp-fee", type=float, default=0.0004)
    ap.add_argument("--spot-fee", type=float, default=0.0040)
    ap.add_argument("--spread", type=float, default=0.0005)
    ap.add_argument("--margin-apr", type=float, default=0.0)
    ap.add_argument("--tax-rate", type=float, default=0.0)
    a = ap.parse_args(argv)
    p = Promo(a.name, a.bonus, a.required, int(a.hold_days), int(a.clawback_days),
              needs_price_exposure=not a.cash)
    r = hedged_capture(a.bonus, a.required, max(a.hold_days, a.clawback_days), needs_price_exposure=not a.cash,
                       funding_8h=a.funding_8h, perp_fee=a.perp_fee, spot_fee=a.spot_fee, spread=a.spread,
                       margin_apr=a.margin_apr, tax_rate=a.tax_rate)
    print(render(p, r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
