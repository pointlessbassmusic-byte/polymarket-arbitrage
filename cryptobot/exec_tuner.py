"""Learn the venue's fill behaviour from the execution log and set the
IOC limit distance accordingly.

The executors send immediate-or-cancel limits at mid +- max_slippage.
Too tight and entries are missed (an unfilled IOC is logged as a skip
with stage "unfilled"); too loose and the bot pays more than the book
requires. Both are visible within days in state/execution.jsonl, unlike
the strategy's edge, so this is the one parameter the desk tunes on
live data:

- unfilled share over the window >= `widen_at` (with enough attempts):
  widen by `step` (x1.25), up to `max_limit`;
- unfilled share <= `tighten_at` and mean adverse slippage below a
  quarter of the limit: tighten by `step`, down to `min_limit`;
- otherwise leave it.

One change per `cooldown_s`, persisted so a restart keeps the learned
value, and every change is explained and alerted.
"""
from __future__ import annotations

import json
import logging
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FILE = "exec_tuning.json"


@dataclass
class TunerConfig:
    min_attempts: int = 10
    widen_at: float = 0.20          # unfilled share that widens the limit
    tighten_at: float = 0.05        # unfilled share below which tightening is allowed
    step: float = 1.25
    min_limit: float = 0.001
    max_limit: float = 0.02
    cooldown_s: float = 86400.0


@dataclass
class Tuning:
    limit: float
    reason: str
    ts: float
    attempts: int = 0
    unfilled_share: float = 0.0
    slippage_bps: Optional[float] = None


def decide(current: float, fills: int, unfilled: int, slippage_bps: Optional[float],
           cfg: TunerConfig) -> tuple[float, str]:
    attempts = fills + unfilled
    if attempts < cfg.min_attempts:
        return current, f"keep {100 * current:.2f}%: {attempts} attempts, need {cfg.min_attempts}"
    share = unfilled / attempts
    limit_bps = current * 1e4
    if share >= cfg.widen_at:
        new = min(cfg.max_limit, current * cfg.step)
        if new > current:
            return new, (f"widen {100 * current:.2f}% -> {100 * new:.2f}%: {unfilled} of {attempts} "
                         f"IOC orders went unfilled ({100 * share:.0f}%)")
        return current, f"keep {100 * current:.2f}%: {100 * share:.0f}% unfilled but already at the cap"
    if share <= cfg.tighten_at and slippage_bps is not None and slippage_bps < 0.25 * limit_bps:
        new = max(cfg.min_limit, current / cfg.step)
        if new < current:
            return new, (f"tighten {100 * current:.2f}% -> {100 * new:.2f}%: {100 * share:.0f}% unfilled and "
                         f"mean adverse slippage {slippage_bps:.0f} bp is well inside the {limit_bps:.0f} bp limit")
        return current, f"keep {100 * current:.2f}%: already at the floor"
    return current, (f"keep {100 * current:.2f}%: {100 * share:.0f}% unfilled"
                     + (f", slippage {slippage_bps:.0f} bp" if slippage_bps is not None else ""))


class ExecTuner:
    def __init__(self, cfg: TunerConfig, path: Optional[Path] = None):
        self.cfg = cfg
        self.path = path
        self.state: dict[str, Tuning] = {}
        self.load()

    def load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            d = json.loads(self.path.read_text())
            fields = Tuning.__dataclass_fields__
            self.state = {k: Tuning(**{f: v for f, v in t.items() if f in fields}) for k, t in d.items()}
        except (OSError, ValueError, TypeError):
            logger.exception("exec tuning state unreadable; starting fresh")

    def save(self) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({k: vars(t) for k, t in self.state.items()}, indent=2))
        except OSError:
            logger.exception("exec tuning state write failed")

    def apply(self, name: str, executor, summary: Optional[dict]) -> Tuning:
        """Set executor.cfg.max_slippage from the execution summary."""
        current = float(getattr(executor.cfg, "max_slippage", 0.0) or 0.0)
        prev = self.state.get(name)
        if prev is not None and abs(prev.limit - current) > 1e-12:
            executor.cfg.max_slippage = prev.limit          # restore the learned value after a restart
            current = prev.limit
        fills = int((summary or {}).get("fills") or 0)
        unfilled = int((summary or {}).get("unfilled") or 0)
        xs = (summary or {}).get("slippage_bps_all") or []
        slip = statistics.mean(xs) if xs else None
        new, why = decide(current, fills, unfilled, slip, self.cfg)
        if prev is not None and new != current and time.time() - prev.ts < self.cfg.cooldown_s:
            new, why = current, f"keep {100 * current:.2f}%: last change {int((time.time() - prev.ts) / 3600)}h ago (cooldown)"
        if new != current:
            executor.cfg.max_slippage = new
        t = Tuning(limit=new, reason=why, ts=time.time() if new != current else (prev.ts if prev else 0.0),
                   attempts=fills + unfilled, unfilled_share=(unfilled / (fills + unfilled)) if fills + unfilled else 0.0,
                   slippage_bps=slip)
        t.changed = new != current  # type: ignore[attr-defined]
        self.state[name] = t
        self.save()
        return t
