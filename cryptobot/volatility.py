"""Multi-window volatility engine.

DexScreener natively reports 5m / 1h / 6h / 24h change. The 30m window is
not reported by any free source, so we build it ourselves: the scanner
samples every token's price on each cycle and this engine keeps a rolling
price history per token, from which it computes 30m moves, realized vol,
and a z-score for how unusual the current 5m move is versus that token's
own recent behavior (a 10% candle is noise for one coin and an event for
another — z-score normalizes that).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

from .models import TokenSnapshot, VolatilityProfile


@dataclass
class _History:
    # (ts, price) samples, newest last. Bounded to ~26h so 24h lookups work.
    samples: Deque[tuple[float, float]] = field(default_factory=deque)
    # Recent 5m moves (fractions) for z-scoring.
    recent_5m_moves: Deque[float] = field(default_factory=lambda: deque(maxlen=288))

    def prune(self, now_ts: float, max_age: float = 26 * 3600) -> None:
        """Drop samples older than the longest window we report on."""
        while self.samples and now_ts - self.samples[0][0] > max_age:
            self.samples.popleft()


def _move_over(history: _History, now_ts: float, window_s: float,
               current_price: float) -> Optional[float]:
    """Fractional price change over `window_s`, using the oldest sample that
    is at least `window_s` old but no more than 2x the window (else stale)."""
    target = now_ts - window_s
    best: Optional[tuple[float, float]] = None
    for ts, price in history.samples:
        if ts <= target:
            best = (ts, price)
        else:
            break
    if best is None:
        return None
    ts, price = best
    if now_ts - ts > 2.0 * window_s or price <= 0:
        return None
    return current_price / price - 1.0


def _realized_vol(history: _History, now_ts: float, window_s: float) -> float:
    """Stdev of log returns between consecutive samples inside the window."""
    pts = [(ts, p) for ts, p in history.samples if now_ts - ts <= window_s and p > 0]
    if len(pts) < 3:
        return 0.0
    rets = [math.log(pts[i][1] / pts[i - 1][1]) for i in range(1, len(pts))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var)


class VolatilityEngine:
    def __init__(self) -> None:
        self._hist: dict[str, _History] = {}

    def observe(self, snap: TokenSnapshot) -> VolatilityProfile:
        """Record a snapshot and return the token's current volatility profile."""
        h = self._hist.setdefault(snap.key, _History())
        h.samples.append((snap.ts, snap.price_usd))
        h.prune(snap.ts)

        move_5m = snap.change_5m
        if move_5m is None:
            move_5m = _move_over(h, snap.ts, 300, snap.price_usd) or 0.0
        # Score this move against the PRIOR baseline, then record it.
        # Including it in its own baseline caps z at (n-1)/sqrt(n) — at the
        # 12-sample gate that is 3.18, so a threshold of 4.0 could never
        # fire, and every z-score was biased low.
        zscore = self._zscore(h, move_5m)
        h.recent_5m_moves.append(move_5m)

        move_30m = _move_over(h, snap.ts, 1800, snap.price_usd)
        if move_30m is None:
            # Fall back to interpolating between the native windows we do have.
            m1h = snap.change_1h or 0.0
            move_30m = 0.5 * m1h + 0.5 * move_5m

        move_1h = snap.change_1h
        if move_1h is None:
            move_1h = _move_over(h, snap.ts, 3600, snap.price_usd) or 0.0
        move_24h = snap.change_24h
        if move_24h is None:
            move_24h = _move_over(h, snap.ts, 86400, snap.price_usd) or 0.0

        return VolatilityProfile(
            key=snap.key,
            symbol=snap.base_symbol,
            move_5m=move_5m,
            move_30m=move_30m,
            move_1h=move_1h,
            move_24h=move_24h,
            realized_vol_30m=_realized_vol(h, snap.ts, 1800),
            zscore_5m=zscore,
            samples=len(h.samples),
        )

    # Noise floor for the z-score denominator. A near-flat history has
    # ~zero variance, and dividing by it either explodes or (worse, when
    # guarded by `return 0.0`) makes a dead-quiet coin that suddenly jumps
    # score z=0 — silencing the very "quiet coin waking up" case the
    # regime detector exists to catch. 0.1% per 5m sits well below any
    # real token's chop, so this binds only on pathologically flat series.
    MIN_STD_5M = 0.001

    @classmethod
    def _zscore(cls, h: _History, current: float) -> float:
        moves = list(h.recent_5m_moves)
        if len(moves) < 6:
            return 0.0
        mean = sum(moves) / len(moves)
        var = sum((m - mean) ** 2 for m in moves) / (len(moves) - 1)
        std = max(math.sqrt(var), cls.MIN_STD_5M)
        return (current - mean) / std

    def history_len(self, key: str) -> int:
        h = self._hist.get(key)
        return len(h.samples) if h else 0

    def retain(self, keys: set[str]) -> int:
        """Drop history for pairs we no longer track.

        A long-running scanner sees thousands of pairs; without this the
        per-pair history grows without bound, unlike `tracked` which is
        capped. Returns the number of pairs dropped.
        """
        stale = [k for k in self._hist if k not in keys]
        for k in stale:
            del self._hist[k]
        return len(stale)
