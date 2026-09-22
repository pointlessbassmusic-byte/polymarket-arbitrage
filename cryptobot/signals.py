"""Pattern detection and asymmetric-opportunity scoring.

Four setups, all filtered through the same asymmetry lens — we only want
trades where the plausible upside is a multiple of the defined downside:

1. VOL_BREAKOUT   — 5m/30m move accelerating vs 1h/24h baseline, volume
                    confirming, buys outnumbering sells. Ride the swing with
                    a trailing stop.
2. MEAN_REVERT    — a coin dumped hard and fast (deep negative 1h vs flat
                    24h trend) into real liquidity: spring-back setup with a
                    tight stop below the flush low.
3. CROSS_DEX_ARB  — the same token priced differently in two pools with
                    enough depth on both sides to matter after fees.
4. VOL_REGIME_SHIFT — a quiet coin whose short-window vol suddenly dwarfs
                    its own history (z-score) before the big windows have
                    moved: earliest, lowest-confidence entry.

The asymmetry comes from structure, not prediction: stops are placed at the
level that invalidates the setup (near), targets at the prior extension
(far), so risk_reward = take_profit / stop_loss is mechanical and we simply
refuse anything under the configured minimum.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .models import Side, Signal, SignalType, TokenSnapshot, VolatilityProfile

logger = logging.getLogger(__name__)


@dataclass
class SignalConfig:
    # Universe hygiene — most "wild volatility" in microcaps is exit liquidity.
    min_liquidity_usd: float = 50_000.0
    min_volume_24h_usd: float = 100_000.0
    min_pair_age_hours: float = 24.0
    max_fdv_to_liquidity: float = 500.0   # thin float vs valuation = rug risk

    # Breakout thresholds
    breakout_move_5m: float = 0.03        # +3% in 5 minutes
    breakout_move_30m: float = 0.06
    breakout_min_buy_ratio: float = 0.55
    breakout_volume_surge: float = 2.0    # 1h volume vs 24h hourly average

    # Mean reversion thresholds
    revert_min_drop_1h: float = -0.15     # -15% in an hour
    revert_max_trend_24h: float = 0.10    # not already a one-way collapse

    # Regime shift. Held at 4.0 as the stable middle of the positive
    # range: a post-z-score-fix sweep spans +1.25% (z=4.5) to -1.50%
    # (z=5.0) on 3-10 trades per cell, which is noise rather than a
    # tunable signal. See cryptobot_config.yaml for the numbers.
    regime_min_zscore: float = 4.0
    regime_max_move_1h: float = 0.05      # big windows still quiet

    # Cross-DEX arb
    arb_min_spread: float = 0.02          # 2% gross gap
    arb_fee_buffer: float = 0.012         # 2x 0.3% swap fee + gas + slippage

    # Asymmetry gate
    min_risk_reward: float = 2.0


def _passes_hygiene(snap: TokenSnapshot, cfg: SignalConfig) -> bool:
    if snap.liquidity_usd < cfg.min_liquidity_usd:
        return False
    if snap.volume_24h_usd < cfg.min_volume_24h_usd:
        return False
    age = snap.age_hours
    if age is not None and age < cfg.min_pair_age_hours:
        return False
    if snap.fdv_usd and snap.liquidity_usd > 0:
        if snap.fdv_usd / snap.liquidity_usd > cfg.max_fdv_to_liquidity:
            return False
    return True


def _gated(sig: Signal, cfg: SignalConfig) -> Optional[Signal]:
    return sig if sig.risk_reward >= cfg.min_risk_reward else None


def detect_breakout(snap: TokenSnapshot, vol: VolatilityProfile,
                    cfg: SignalConfig) -> Optional[Signal]:
    if vol.move_5m < cfg.breakout_move_5m or vol.move_30m < cfg.breakout_move_30m:
        return None
    if snap.buy_sell_ratio < cfg.breakout_min_buy_ratio:
        return None
    hourly_avg = snap.volume_24h_usd / 24.0 if snap.volume_24h_usd else 0.0
    if hourly_avg <= 0 or snap.volume_1h_usd / hourly_avg < cfg.breakout_volume_surge:
        return None

    # Stop just under the 30m launch point, widened to at least ~2 units
    # of current realized vol (ATR-style: adaptive stops avoid getting
    # shaken out by noise that is normal for THIS token right now).
    stop = max(0.02, vol.move_30m * 0.5, 2.0 * vol.realized_vol_30m)
    target = max(vol.move_30m * 1.5, vol.move_1h)
    rr = target / stop if stop > 0 else 0.0
    confidence = min(1.0, 0.3 + 0.5 * snap.buy_sell_ratio + 0.1 * min(vol.zscore_5m / 3.0, 1.0))
    return _gated(Signal(
        ts=snap.ts, type=SignalType.VOL_BREAKOUT, key=snap.key, chain=snap.chain,
        symbol=snap.base_symbol, side=Side.LONG, price_usd=snap.price_usd,
        confidence=confidence, expected_move=target, stop_loss_pct=stop,
        take_profit_pct=target, risk_reward=rr, liquidity_usd=snap.liquidity_usd,
        token_address=snap.base_address, vol_30m=vol.realized_vol_30m,
        reason=(f"breakout: 5m {vol.move_5m:+.1%}, 30m {vol.move_30m:+.1%}, "
                f"buys {snap.buy_sell_ratio:.0%}, 1h vol surge "
                f"{snap.volume_1h_usd / hourly_avg:.1f}x"),
    ), cfg)


def detect_mean_revert(snap: TokenSnapshot, vol: VolatilityProfile,
                       cfg: SignalConfig) -> Optional[Signal]:
    if vol.move_1h > cfg.revert_min_drop_1h:
        return None
    # Skip coins in a genuine death spiral: the 24h trend must not confirm
    # the dump (i.e. the flush is local, not the whole day).
    if vol.move_24h < 2.0 * cfg.revert_min_drop_1h:
        return None
    if abs(vol.move_24h) > cfg.revert_max_trend_24h and vol.move_24h < 0:
        return None
    if snap.buy_sell_ratio < 0.40:  # nobody catching the knife yet
        return None

    drop = abs(vol.move_1h)
    # Below the flush low, widened by current realized vol (ATR-style).
    stop = max(0.03, drop * 0.25, 2.0 * vol.realized_vol_30m)
    target = drop * 0.5                  # half-retrace of the dump
    rr = target / stop if stop > 0 else 0.0
    return _gated(Signal(
        ts=snap.ts, type=SignalType.MEAN_REVERT, key=snap.key, chain=snap.chain,
        symbol=snap.base_symbol, side=Side.LONG, price_usd=snap.price_usd,
        confidence=0.4 + 0.2 * snap.buy_sell_ratio, expected_move=target,
        stop_loss_pct=stop, take_profit_pct=target, risk_reward=rr,
        liquidity_usd=snap.liquidity_usd, token_address=snap.base_address,
        vol_30m=vol.realized_vol_30m,
        reason=(f"mean-revert: 1h {vol.move_1h:+.1%} flush vs 24h "
                f"{vol.move_24h:+.1%} trend, targeting half-retrace"),
    ), cfg)


def detect_regime_shift(snap: TokenSnapshot, vol: VolatilityProfile,
                        cfg: SignalConfig) -> Optional[Signal]:
    if vol.samples < 12 or vol.zscore_5m < cfg.regime_min_zscore:
        return None
    if abs(vol.move_1h) > cfg.regime_max_move_1h or vol.move_5m <= 0:
        return None
    stop = max(0.02, 2.0 * vol.realized_vol_30m)
    target = stop * 3.0
    return _gated(Signal(
        ts=snap.ts, type=SignalType.VOL_REGIME_SHIFT, key=snap.key, chain=snap.chain,
        symbol=snap.base_symbol, side=Side.LONG, price_usd=snap.price_usd,
        confidence=0.35, expected_move=target, stop_loss_pct=stop,
        take_profit_pct=target, risk_reward=3.0, liquidity_usd=snap.liquidity_usd,
        token_address=snap.base_address, vol_30m=vol.realized_vol_30m,
        reason=(f"regime shift: 5m move z={vol.zscore_5m:.1f} while 1h still "
                f"{vol.move_1h:+.1%} — early wake-up"),
    ), cfg)


def detect_cross_dex_arb(pools: list[TokenSnapshot],
                         cfg: SignalConfig) -> Optional[Signal]:
    """Given all pools for ONE token, find a tradeable price gap.

    True atomic arb needs both legs; from a plain wallet the realistic play
    is buy-cheap-pool / sell-rich-pool in two transactions, so we demand a
    gap well above fees and real depth on both sides.
    """
    liquid = [p for p in pools if p.liquidity_usd >= cfg.min_liquidity_usd / 2]
    if len(liquid) < 2:
        return None
    lo = min(liquid, key=lambda p: p.price_usd)
    hi = max(liquid, key=lambda p: p.price_usd)
    if lo.price_usd <= 0:
        return None
    spread = hi.price_usd / lo.price_usd - 1.0
    net = spread - cfg.arb_fee_buffer
    if spread < cfg.arb_min_spread or net <= 0:
        return None
    return Signal(
        ts=lo.ts, type=SignalType.CROSS_DEX_ARB, key=lo.key, chain=lo.chain,
        symbol=lo.base_symbol, side=Side.LONG, price_usd=lo.price_usd,
        confidence=0.8, expected_move=net, stop_loss_pct=cfg.arb_fee_buffer,
        take_profit_pct=net, risk_reward=net / cfg.arb_fee_buffer,
        liquidity_usd=min(lo.liquidity_usd, hi.liquidity_usd),
        token_address=lo.base_address,
        reason=(f"cross-DEX gap {spread:.1%} ({net:.1%} net): buy "
                f"{lo.chain}:{lo.pair_address[:10]}… @ {lo.price_usd:.6g}, sell "
                f"{hi.chain}:{hi.pair_address[:10]}… @ {hi.price_usd:.6g}"),
    )


def detect_all(snap: TokenSnapshot, vol: VolatilityProfile,
               cfg: SignalConfig) -> list[Signal]:
    if not _passes_hygiene(snap, cfg):
        return []
    out = []
    for det in (detect_breakout, detect_mean_revert, detect_regime_shift):
        try:
            if sig := det(snap, vol, cfg):
                out.append(sig)
        except Exception:
            logger.exception("detector %s failed on %s", det.__name__, snap.key)
    return out
