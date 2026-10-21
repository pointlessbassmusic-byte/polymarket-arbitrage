"""
A compact, cached daily panel of every archived daily-history bundle, for cross-sectional harnesses.
===================================================================================================

Loading the 901 daily-history bundles one by one through ``batch6c_cal._daily`` keeps every raw row in memory
(about 13 GB and four minutes): too much for one harness, and several at once exhausted the box (2026-10-21). This
module builds the panel once into mandel/ml_data/cache/daily_panel.npz (local, gitignored, rebuilt whenever any
daily-history bundle's sha256 changes) and serves date x symbol matrices.

    from mandel.experiments.panel_cache import daily_panel
    P = daily_panel(archive)      # P.days (YYYY-MM-DD), P.symbols, P.open / high / low / close / adjclose / volume
    P.col("AAPL", "adjclose")      # one symbol's series aligned to P.days (NaN where it did not trade)

Values are exactly what ``batch6c_cal._daily`` returns per bundle (``close`` as printed; ``adjclose`` with the same
carry-forward of the previous adjclose/close ratio when a bar lacks one), on the union of trading days. Every bundle
used is probed through ``archive.get`` so the runner's wiring trace sees what a harness depends on.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from mandel.paths import MANDEL_ROOT

CACHE = MANDEL_ROOT / "ml_data" / "cache" / "daily_panel.npz"
PREFIX = "daily-history-"
FIELDS = ("open", "high", "low", "close", "adjclose", "volume")


@dataclass
class Panel:
    days: np.ndarray
    symbols: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    adjclose: np.ndarray
    volume: np.ndarray

    def col(self, sym: str, field: str = "adjclose") -> np.ndarray:
        j = int(np.where(self.symbols == sym)[0][0])
        return getattr(self, field)[:, j]


def _entries(archive) -> list:
    return sorted((e for e in archive.entries() if e.name.startswith(PREFIX)), key=lambda e: e.name)


def _fingerprint(entries) -> str:
    h = hashlib.sha256()
    for e in entries:
        h.update(f"{e.name}:{getattr(e, 'sha256', '')}:{getattr(e, 'rows', '')}\n".encode())
    return h.hexdigest()[:20]


def _load_one(archive, name: str) -> dict:
    """{day: (open, high, low, close, adjclose, volume)} with batch6c_cal._daily's close and adjclose rules."""
    by = {}
    cap = getattr(archive.get(name), "created_at", None)
    for r in archive.load(name):
        if cap and r.get("available_at") and r["available_at"] > cap:
            continue
        v = r.get("value") or {}
        try:
            c = float(v.get("close"))
        except (TypeError, ValueError):
            continue
        if not (c > 0 and math.isfinite(c)):
            continue
        d = datetime.fromtimestamp(float(v["t"]), tz=timezone.utc).strftime("%Y-%m-%d")

        def f(k):
            try:
                x = float(v.get(k))
                return x if math.isfinite(x) else float("nan")
            except (TypeError, ValueError):
                return float("nan")
        a = f("adjclose")
        by[d] = (f("open"), f("high"), f("low"), c, a if a > 0 else float("nan"), f("volume"))
    return by


def build(archive) -> Panel:
    entries = _entries(archive)
    per = {}
    for e in entries:
        per[e.name[len(PREFIX):]] = _load_one(archive, e.name)
    days = np.array(sorted({d for by in per.values() for d in by}))
    syms = np.array(sorted(per))
    pos = {d: i for i, d in enumerate(days)}
    mats = {k: np.full((len(days), len(syms)), np.nan, dtype=np.float64) for k in FIELDS}
    for j, s in enumerate(syms):
        by = per[s]
        idx = np.array([pos[d] for d in sorted(by)], int)
        rows = np.array([by[d] for d in sorted(by)], float)
        for k, field in enumerate(FIELDS):
            mats[field][idx, j] = rows[:, k]
        # adjclose carry-forward of the previous adjclose/close ratio, per symbol, as batch6c_cal._daily does
        c, a = mats["close"][idx, j], mats["adjclose"][idx, j]
        ratio = 1.0
        for i in range(len(idx)):
            if np.isfinite(a[i]):
                ratio = a[i] / c[i]
            else:
                a[i] = c[i] * ratio
        mats["adjclose"][idx, j] = a
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, days=days, symbols=syms, fingerprint=np.array(_fingerprint(entries)), **mats)
    tmp.replace(CACHE)
    return Panel(days, syms, **mats)


_MEMO: dict = {}


def daily_panel(archive) -> Panel:
    """The cached panel, rebuilt when the archive's daily-history bundles changed. Probes every bundle it covers."""
    entries = _entries(archive)
    for e in entries:                         # cheap metadata probes: the wiring trace records the dependence
        archive.get(e.name)
    fp = _fingerprint(entries)
    if fp in _MEMO:
        return _MEMO[fp]
    if CACHE.exists():
        z = np.load(CACHE, allow_pickle=False)
        if str(z["fingerprint"]) == fp:
            p = Panel(z["days"], z["symbols"], *(z[k] for k in FIELDS))
            _MEMO[fp] = p
            return p
    p = build(archive)
    _MEMO[fp] = p
    return p
