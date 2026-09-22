"""Round-trip trading cost model — the difference between a backtest
that prints money and a wallet that bleeds it.

Every DEX round trip pays, twice (entry + exit):
  * the pool's swap fee (0.3% on most v2 pools, 0.25-1% on memecoin pools);
  * price impact against finite depth — in an xy=k pool a trade of size s
    against one-sided depth ~L/2 moves the price by roughly s/(L/2), and
    you eat about half of that as execution shortfall;
  * routing slippage beyond the model (MEV, latency);
  * gas, a FLAT cost per transaction — negligible on Base/Solana, brutal
    on Ethereum mainnet for small size (an $8 swap x2 on a $30 position
    is -53% before the price moves at all).

The model is deliberately slightly pessimistic: being talked out of a
marginal trade is cheap, discovering the costs live is not.

Used three ways:
  1. an ENTRY GATE — a signal's expected move must clear the round trip
     by `min_edge_multiple`, and sizing must clear the gas floor;
  2. paper fills and backtest fills are charged the same costs, so the
     EdgeTracker learns NET expectancy;
  3. the dashboard reports net PnL, not fantasy PnL.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Typical total gas for ONE swap (approve amortized in), in USD.
# Conservative mid-estimates; override per chain in config as prices move.
# Consequence with the 1% gas cap: Ethereum mainnet demands ~$200+
# positions to be viable — small accounts should swing on the L2s/alt-L1s.
DEFAULT_GAS_USD = {
    "ethereum": 2.0,
    "base": 0.05,
    "arbitrum": 0.15,
    "optimism": 0.10,
    "polygon": 0.05,
    "bsc": 0.30,
    "solana": 0.03,
}


@dataclass
class CostConfig:
    dex_fee: float = 0.003              # per swap side (0.3% v2-style)
    extra_slippage: float = 0.002       # routing/MEV/latency per side
    gas_usd: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_GAS_USD))
    default_gas_usd: float = 5.0        # unknown chain -> assume expensive
    # A trade is only taken when expected_move >= round_trip * this.
    # 4.0 chosen by cost-aware backtest sweep: beat 3.0 at every
    # capitalization level once fills were charged real costs.
    min_edge_multiple: float = 4.0
    # ...AND when the asymmetry survives costs. See net_risk_reward: the
    # gross gate in SignalConfig is measured before fees, which lets
    # tight-stop setups through that are net losing bets.
    min_net_risk_reward: float = 1.25
    # Refuse entries where gas alone eats more than this fraction per side.
    max_gas_fraction: float = 0.01


class CostModel:
    def __init__(self, cfg: CostConfig | None = None):
        self.cfg = cfg or CostConfig()

    def gas_usd(self, chain: str) -> float:
        return self.cfg.gas_usd.get(chain, self.cfg.default_gas_usd)

    def price_impact(self, size_usd: float, liquidity_usd: float) -> float:
        """Expected execution shortfall from moving the pool, per side."""
        if liquidity_usd <= 0:
            return 1.0
        # Trade s against one-sided depth L/2 moves price ~ s/(L/2);
        # average fill sits about halfway up that move.
        return size_usd / liquidity_usd

    def round_trip_fraction(self, size_usd: float, liquidity_usd: float,
                            chain: str) -> float:
        """Total round-trip cost as a fraction of notional."""
        if size_usd <= 0:
            return 0.0
        per_side = (self.cfg.dex_fee + self.cfg.extra_slippage
                    + self.price_impact(size_usd, liquidity_usd)
                    + self.gas_usd(chain) / size_usd)
        return 2.0 * per_side

    def round_trip_usd(self, size_usd: float, liquidity_usd: float,
                       chain: str) -> float:
        return size_usd * self.round_trip_fraction(size_usd, liquidity_usd, chain)

    def net_risk_reward(self, take_profit_pct: float, stop_loss_pct: float,
                        size_usd: float, liquidity_usd: float,
                        chain: str) -> float:
        """Reward:risk AFTER costs — the number that actually decides.

        Costs are paid on the winner and the loser alike, so they shrink
        the numerator and grow the denominator at the same time:

            net RR = (target - round_trip) / (stop + round_trip)

        A 6.6%/2.6% setup reads 2.5:1 gross, but on Ethereum at $333 size
        (2.2% round trip) it is 0.92:1 — a losing bet wearing a winning
        gate. Tight stops suffer most, since the cost is a large fraction
        of a small stop.
        """
        rt = self.round_trip_fraction(size_usd, liquidity_usd, chain)
        net_win = take_profit_pct - rt
        net_loss = stop_loss_pct + rt
        if net_win <= 0 or net_loss <= 0:
            return 0.0
        return net_win / net_loss

    def entry_allowed(self, expected_move: float, size_usd: float,
                      liquidity_usd: float, chain: str,
                      take_profit_pct: float | None = None,
                      stop_loss_pct: float | None = None) -> tuple[bool, str]:
        """Gate: does this trade's edge survive its own costs?"""
        if size_usd <= 0:
            return False, "zero size"
        gas_frac = self.gas_usd(chain) / size_usd
        if gas_frac > self.cfg.max_gas_fraction:
            return False, (f"gas ${self.gas_usd(chain):.2f} is "
                           f"{gas_frac:.1%} of ${size_usd:.0f} position "
                           f"(max {self.cfg.max_gas_fraction:.1%}/side)")
        cost = self.round_trip_fraction(size_usd, liquidity_usd, chain)
        if expected_move < cost * self.cfg.min_edge_multiple:
            return False, (f"edge {expected_move:.1%} < "
                           f"{self.cfg.min_edge_multiple:.0f}x round-trip "
                           f"cost {cost:.1%}")
        if take_profit_pct is not None and stop_loss_pct is not None:
            net_rr = self.net_risk_reward(take_profit_pct, stop_loss_pct,
                                          size_usd, liquidity_usd, chain)
            if net_rr < self.cfg.min_net_risk_reward:
                return False, (f"net reward:risk {net_rr:.2f} < "
                               f"{self.cfg.min_net_risk_reward:.2f} "
                               f"(gross looks better; {cost:.1%} costs eat it)")
        return True, ""

    def min_viable_size(self, chain: str) -> float:
        """Smallest position where gas fits under max_gas_fraction."""
        return self.gas_usd(chain) / self.cfg.max_gas_fraction
