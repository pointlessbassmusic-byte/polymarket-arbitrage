"""Capital allocation across the desk's strategies, and the loss limits.

What live trading can teach quickly: execution cost, venue reliability,
drawdown. What it cannot teach quickly: whether the edge is real (the
registry's MinTRL for the bounce-short is 32-104 months). The allocator
is built around that split.

Weights come from a shrunk, uncertainty-aware blend of backtest and live
evidence:

    prior mean  = backtest mean per trade x confidence
                  (confidence = the registry's Deflated Sharpe, or PSR for a
                  pre-registered rule; 0.34 for the bounce-short, so the
                  backtest is believed about a third)
    posterior   = (pseudo_trades x prior + n_live x live mean) / (pseudo_trades + n_live)
    f*          = posterior / sd^2          (Kelly fraction of capital per slot)
    weight      = clamp(f* x kelly_fraction, learning_floor, max_deploy)

A good month moves the posterior by n_live / (pseudo_trades + n_live):
with pseudo_trades = 50 and five live trades, by 9%. That is deliberate.
The weight moves on evidence, not on a streak.

Hard gates, checked every cycle, override the weights:
- verdict killed, or no executor for the venue         -> 0
- real equity down max_drawdown from its peak          -> 0, "killed", manual resume
- execution worse than modelled (slippage over the limit on 10+ fills) -> halved, flagged
- manual mode                                          -> the operator's weights

Everything is explained in `reasons` so the dashboard can show why the
capital sits where it sits.
"""
from __future__ import annotations

import json
import logging
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FILE = "allocation.json"


@dataclass
class AllocatorConfig:
    mode: str = "auto"                 # auto | manual
    kelly_fraction: float = 0.5
    learning_floor: float = 0.5        # never deploy less than this while learning (auto mode)
    max_deploy: float = 1.0            # never more than this (no leverage)
    pseudo_trades: int = 50            # how many live trades it takes to halve the backtest's say
    max_drawdown_real: float = 0.25    # of real equity from its peak: stop new entries
    max_slippage_bps: float = 50.0     # mean adverse slippage over 10+ fills: halve the weight
    min_fills_for_exec: int = 10


@dataclass
class Evidence:
    """One strategy's case for capital."""
    name: str
    backtest_mean: float               # net return per trade, fraction
    backtest_sd: float
    confidence: float                  # DSR / PSR in [0, 1]
    verdict: str = "inconclusive"
    live_returns: list = field(default_factory=list)
    real_equity: float = 0.0
    armed: bool = False
    exec_slippage_bps: Optional[float] = None
    exec_fills: int = 0


@dataclass
class Decision:
    weights: dict                      # strategy -> fraction of capital
    cash: float
    reasons: dict                      # strategy -> text
    killed: dict                       # strategy -> reason
    posterior: dict                    # strategy -> {"mean", "f_star", "n_live"}
    ts: float = 0.0


def posterior_mean(ev: Evidence, cfg: AllocatorConfig) -> tuple[float, int]:
    prior = ev.backtest_mean * max(0.0, min(1.0, ev.confidence))
    n = len(ev.live_returns)
    live = statistics.mean(ev.live_returns) if n else 0.0
    return (cfg.pseudo_trades * prior + n * live) / (cfg.pseudo_trades + n), n


class Allocator:
    def __init__(self, cfg: AllocatorConfig, path: Optional[Path] = None):
        self.cfg = cfg
        self.path = path
        self.mode = cfg.mode
        self.manual: dict[str, float] = {}
        self.peaks: dict[str, float] = {}
        self.killed: dict[str, str] = {}
        self.last: Optional[Decision] = None
        self.history: list[dict] = []
        self.load()

    # -- persistence ---------------------------------------------------------

    def load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            d = json.loads(self.path.read_text())
        except (OSError, ValueError):
            logger.exception("allocation state unreadable; starting fresh")
            return
        self.mode = d.get("mode", self.mode)
        self.manual = {k: float(v) for k, v in (d.get("manual") or {}).items()}
        self.peaks = {k: float(v) for k, v in (d.get("peaks") or {}).items()}
        self.killed = dict(d.get("killed") or {})
        self.history = list(d.get("history") or [])[-200:]
        if d.get("last"):
            self.last = Decision(**d["last"])

    def save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({
                "mode": self.mode, "manual": self.manual, "peaks": self.peaks,
                "killed": self.killed, "history": self.history[-200:],
                "last": vars(self.last) if self.last else None}, indent=2))
        except OSError:
            logger.exception("allocation state write failed")

    # -- operator controls ----------------------------------------------------

    def set_manual(self, weights: dict[str, float]) -> tuple[bool, str]:
        clean = {}
        for k, v in weights.items():
            try:
                v = float(v)
            except (TypeError, ValueError):
                return False, f"{k}: not a number"
            if v < 0 or v > 1:
                return False, f"{k}: weight must be between 0 and 1"
            clean[k] = v
        if sum(clean.values()) > 1.0 + 1e-9:
            return False, "weights add up to more than 100% (no leverage)"
        self.manual = clean
        self.mode = "manual"
        self.save()
        return True, ""

    def set_mode(self, mode: str) -> tuple[bool, str]:
        if mode not in ("auto", "manual"):
            return False, "mode must be auto or manual"
        self.mode = mode
        self.save()
        return True, ""

    def resume(self, name: str, equity: float) -> None:
        """Operator acknowledges a drawdown kill: the peak resets to now."""
        self.killed.pop(name, None)
        self.peaks[name] = equity
        self.save()

    # -- the decision ------------------------------------------------------------

    def decide(self, evidence: dict[str, Evidence]) -> Decision:
        cfg = self.cfg
        weights, reasons, posterior = {}, {}, {}
        for name, ev in evidence.items():
            # drawdown kill, checked in every mode
            peak = max(self.peaks.get(name, 0.0), ev.real_equity)
            self.peaks[name] = peak
            if peak > 0 and ev.real_equity < peak * (1.0 - cfg.max_drawdown_real) and name not in self.killed:
                self.killed[name] = (f"real equity ${ev.real_equity:,.2f} is {100 * (1 - ev.real_equity / peak):.0f}% "
                                     f"below its peak ${peak:,.2f}; resume from the dashboard")
            m, n = posterior_mean(ev, cfg)
            var = ev.backtest_sd ** 2 if ev.backtest_sd > 0 else 1.0
            f_star = max(0.0, m) / var
            posterior[name] = {"mean": m, "f_star": f_star, "n_live": n, "prior": ev.backtest_mean * ev.confidence}
            if name in self.killed:
                weights[name], reasons[name] = 0.0, f"KILLED: {self.killed[name]}"
                continue
            if ev.verdict == "killed":
                weights[name], reasons[name] = 0.0, "registry verdict: killed"
                continue
            if not ev.armed:
                weights[name], reasons[name] = 0.0, "no armed executor for this venue (paper only)"
                continue
            if self.mode == "manual":
                weights[name] = max(0.0, min(1.0, self.manual.get(name, 0.0)))
                reasons[name] = f"manual: {100 * weights[name]:.0f}%"
                continue
            w = f_star * cfg.kelly_fraction
            why = (f"posterior {100 * m:+.2f}%/trade (backtest {100 * ev.backtest_mean:+.2f}% x confidence "
                   f"{ev.confidence:.2f}, {n} live trades), f* {f_star:.2f} x {cfg.kelly_fraction} Kelly")
            if w < cfg.learning_floor:
                why += f"; raised to the learning floor {100 * cfg.learning_floor:.0f}%"
                w = cfg.learning_floor
            if ev.exec_fills >= cfg.min_fills_for_exec and ev.exec_slippage_bps is not None \
                    and ev.exec_slippage_bps > cfg.max_slippage_bps:
                w *= 0.5
                why += (f"; HALVED: mean adverse slippage {ev.exec_slippage_bps:.0f} bp over {ev.exec_fills} fills "
                        f"exceeds {cfg.max_slippage_bps:.0f} bp")
            weights[name], reasons[name] = min(w, cfg.max_deploy), why
        total = sum(weights.values())
        if total > cfg.max_deploy:
            for k in weights:
                weights[k] *= cfg.max_deploy / total
                reasons[k] += f"; scaled to {100 * cfg.max_deploy:.0f}% total"
            total = cfg.max_deploy
        d = Decision(weights=weights, cash=max(0.0, 1.0 - total), reasons=reasons,
                     killed=dict(self.killed), posterior=posterior, ts=time.time())
        changed = self.last is None or any(abs(d.weights.get(k, 0) - self.last.weights.get(k, 0)) > 0.01
                                           for k in set(d.weights) | set(self.last.weights))
        if changed:
            self.history.append({"ts": d.ts, "weights": d.weights, "mode": self.mode})
        self.last = d
        self.save()
        d.changed = changed  # type: ignore[attr-defined]
        return d


def evidence_from_bot(name: str, bot, strat_cfg: dict, exec_summary: Optional[dict] = None) -> Evidence:
    """Assemble a strategy's evidence from its registry/config numbers,
    its real book and the execution log."""
    st = bot.state()
    real = st["books"]["real"]
    closed = getattr(bot.books["real"], "portfolio", None)
    live = []
    if closed is not None:
        live = [t.pnl_usd / t.size_usd for t in closed.closed if t.size_usd]
    slip, fills = None, 0
    if exec_summary and exec_summary.get("slippage_bps_all"):
        xs = exec_summary["slippage_bps_all"]
        slip, fills = statistics.mean(xs), len(xs)
    return Evidence(name=name, backtest_mean=float(strat_cfg.get("backtest_mean", 0.0)),
                    backtest_sd=float(strat_cfg.get("backtest_sd", 0.1)),
                    confidence=float(strat_cfg.get("confidence", 0.0)),
                    verdict=str(strat_cfg.get("verdict", "inconclusive")),
                    live_returns=live, real_equity=float(real["equity"]),
                    armed=bool(st.get("real_unlocked")), exec_slippage_bps=slip, exec_fills=fills)
