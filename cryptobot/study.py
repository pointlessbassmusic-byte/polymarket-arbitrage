"""Walk-forward study: does a detector have a repeatable edge?

Aggregate PnL over one window cannot separate skill from luck. This
slices real history into consecutive non-overlapping windows, runs each
detector IN ISOLATION over every one, and reports three things that a
single backtest number hides:

  1. **Per-window consistency** — positive in how many windows, not just
     positive overall.
  2. **Gross vs net** — whether a detector loses because its signal is
     wrong, or because friction is larger than its edge. These have
     completely different remedies.
  3. **Whether the edge is distinguishable from zero** — a t-statistic
     and confidence interval on per-trade gross return, plus the trade
     count that would be needed to settle it.

Usage:
    python -m cryptobot.study PEPE BRETT MOG --days 21 --windows 6
    python -m cryptobot.study --cache candles.pkl --windows 6
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import pickle
import statistics
from dataclasses import replace
from pathlib import Path

from .backtest import Backtester, CANDLES_PER_DAY, resolve_pools
from .costs import CostConfig
from .risk import RiskConfig
from .signals import SignalConfig

logger = logging.getLogger(__name__)

# Thresholds that no real market reaches, used to silence a detector so
# the others can be measured on their own.
_SILENCED = dict(breakout_move_5m=9.0, breakout_move_30m=9.0,
                 revert_min_drop_1h=-9.0, regime_min_zscore=999.0)

DETECTORS = ("breakout", "mean_revert", "regime", "all")


def isolate(name: str, base: SignalConfig | None = None) -> SignalConfig:
    """A config in which only `name` can fire."""
    base = base or SignalConfig()
    if name == "all":
        return base
    cfg = replace(base, **_SILENCED)
    if name == "breakout":
        return replace(cfg, breakout_move_5m=base.breakout_move_5m,
                       breakout_move_30m=base.breakout_move_30m)
    if name == "mean_revert":
        return replace(cfg, revert_min_drop_1h=base.revert_min_drop_1h)
    if name == "regime":
        return replace(cfg, regime_min_zscore=base.regime_min_zscore)
    raise ValueError(f"unknown detector {name!r}")


def split_windows(pools: dict, n_windows: int) -> list[dict]:
    """Consecutive non-overlapping slices, each with its own warm-up."""
    if not pools:
        return []
    longest = max(len(c) for _, c in pools.values())
    size = longest // max(1, n_windows)
    out = []
    for w in range(n_windows):
        chunk = {k: (m, c[w * size:(w + 1) * size])
                 for k, (m, c) in pools.items()}
        chunk = {k: v for k, v in chunk.items()
                 if len(v[1]) > CANDLES_PER_DAY + 50}
        if chunk:
            out.append(chunk)
    return out


# Below this, a t-statistic on trade returns is not interpretable: the
# estimate of the standard deviation is itself too noisy, and a handful
# of trades can produce a large |t| by chance.
MIN_TRADES_FOR_INFERENCE = 10


def significance(trades) -> dict:
    """Is the per-trade GROSS edge distinguishable from zero?"""
    rets = [(t.pnl_usd + t.costs_usd) / t.size_usd
            for t in trades if t.size_usd > 0]
    n = len(rets)
    if n < 2:
        return {"n": n}
    mean = statistics.mean(rets)
    sd = statistics.stdev(rets)
    se = sd / math.sqrt(n) if n else float("inf")
    t = mean / se if se else 0.0
    return {
        "n": n, "mean": mean, "sd": sd, "se": se, "t": t,
        "ci_lo": mean - 1.96 * se, "ci_hi": mean + 1.96 * se,
        "enough": n >= MIN_TRADES_FOR_INFERENCE,
        "significant": abs(t) > 2.0 and n >= MIN_TRADES_FOR_INFERENCE,
        # Trades needed for |t|=2 if the sample mean and sd are the truth.
        "n_needed": (math.ceil((2 * sd / mean) ** 2)
                     if mean > 0 else None),
    }


def study(pools: dict, *, n_windows: int, bankroll: float,
          hold_hours: float, cost_cfg: CostConfig | None = None) -> dict:
    slices = split_windows(pools, n_windows)
    risk = RiskConfig(
        bankroll_usd=bankroll, risk_per_trade_pct=0.015,
        max_position_usd=bankroll * 0.25, min_position_usd=bankroll * 0.20,
        max_total_exposure_usd=bankroll * 0.75, max_open_positions=3,
        max_daily_loss_usd=bankroll * 0.10)
    results = {}
    for name in DETECTORS:
        cfg = isolate(name)
        per_window, trades = [], []
        for sl in slices:
            bt = Backtester(cfg, risk, cost_cfg=cost_cfg or CostConfig())
            rep = bt.run(sl, max_position_age_s=hold_hours * 3600)
            per_window.append((100.0 * rep["realized_pnl"] / bankroll,
                               rep["trades"]))
            trades += bt.portfolio.closed
        gross = sum(t.pnl_usd + t.costs_usd for t in trades)
        costs = sum(t.costs_usd for t in trades)
        notional = sum(t.size_usd for t in trades)
        results[name] = {
            "per_window": per_window,
            "trades": len(trades),
            "gross_usd": gross, "costs_usd": costs,
            "net_usd": gross - costs,
            "gross_pct_of_notional": (100 * gross / notional) if notional else 0.0,
            "breakeven_friction_pct": (100 * gross / notional) if notional else 0.0,
            "stats": significance(trades),
        }
    return {"windows": len(slices), "pools": len(pools), "results": results}


def render(report: dict) -> str:
    out = [f"{report['pools']} pools, {report['windows']} windows\n"]
    for name, r in report["results"].items():
        cells = " ".join(f"{p:+6.2f}%({n:2d})" for p, n in r["per_window"])
        pos = sum(1 for p, _ in r["per_window"] if p > 0.01)
        neg = sum(1 for p, _ in r["per_window"] if p < -0.01)
        out.append(f"{name:12s} {cells}")
        out.append(f"{'':12s} windows +{pos}/-{neg}"
                   f"/flat{len(r['per_window']) - pos - neg}"
                   f"   {r['trades']} trades")
        if r["trades"]:
            out.append(f"{'':12s} gross ${r['gross_usd']:+.2f}  "
                       f"costs ${r['costs_usd']:.2f}  "
                       f"NET ${r['net_usd']:+.2f}")
            s = r["stats"]
            if s.get("n", 0) >= 2:
                out.append(
                    f"{'':12s} per-trade gross {100*s['mean']:+.2f}% "
                    f"(se {100*s['se']:.2f}%, t={s['t']:.2f}) "
                    f"95% CI {100*s['ci_lo']:+.2f}%..{100*s['ci_hi']:+.2f}%")
                if not s.get("enough"):
                    out.append(f"{'':12s} -> too few trades to infer "
                               f"anything (need "
                               f"{MIN_TRADES_FOR_INFERENCE}+)")
                else:
                    verdict = ("edge is distinguishable from zero"
                               if s["significant"] else
                               "NOT distinguishable from zero")
                    need = (f"; ~{s['n_needed']} trades would settle it"
                            if s.get("n_needed") else "")
                    out.append(f"{'':12s} -> {verdict}{need}")
        out.append("")
    return "\n".join(out)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("symbols", nargs="*", help="token symbols to fetch")
    ap.add_argument("--days", type=float, default=21.0)
    ap.add_argument("--windows", type=int, default=6)
    ap.add_argument("--bankroll", type=float, default=200.0)
    ap.add_argument("--hold-hours", type=float, default=6.0)
    ap.add_argument("--cache", type=Path,
                    help="pickle of pools to load/save instead of refetching")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    pools = None
    if args.cache and args.cache.exists():
        pools = pickle.loads(args.cache.read_bytes())
        logger.info("loaded %d pools from %s", len(pools), args.cache)
    if pools is None:
        if not args.symbols:
            ap.error("give symbols to fetch, or a --cache that exists")
        pools = await resolve_pools(args.symbols, None, args.days)
        if args.cache:
            args.cache.write_bytes(pickle.dumps(pools))
    if not pools:
        print("no pools with enough history")
        return 1
    print(render(study(pools, n_windows=args.windows, bankroll=args.bankroll,
                       hold_hours=args.hold_hours)))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
