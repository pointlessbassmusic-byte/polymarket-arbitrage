"""Observation store with point-in-time access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator, Optional

from mandel.archive import Archive


def iso(ts) -> str:
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    if isinstance(ts, datetime):
        return ts.astimezone(timezone.utc).isoformat()
    return str(ts)


@dataclass
class Observation:
    source: str            # "polymarket" | "kalshi"
    kind: str              # "market" | "price" | "candle" | "book"
    key: str               # market id / token id / ticker
    observed_at: str       # ISO 8601 UTC
    available_at: str      # ISO 8601 UTC; when Mandel could have known it
    value: dict            # the payload, raw and lossless where possible

    def row(self) -> dict:
        return {"source": self.source, "kind": self.kind, "key": self.key, "observed_at": self.observed_at,
                "available_at": self.available_at, "value": self.value}


def point_in_time(rows: Iterable[dict], decision_ts: str) -> Iterator[dict]:
    """Yield only rows that were available at or before ``decision_ts`` (ISO strings compare lexically)."""
    for r in rows:
        if r.get("available_at", "9999") <= decision_ts:
            yield r


class ObservationStore:
    """Thin facade: writes observations as archive bundles and reads them back with the PIT filter."""

    def __init__(self, archive: Optional[Archive] = None):
        self.archive = archive if archive is not None else Archive()

    def write_bundle(self, name: str, observations: Iterable[Observation], recipe: str, tags: Iterable[str] = (), schema: str = ""):
        return self.archive.store(name, "data", (o.row() for o in observations), recipe=recipe, tags=tags, schema=schema)

    def read(self, name: str, decision_ts: Optional[str] = None) -> Iterator[dict]:
        rows = self.archive.load(name)
        return point_in_time(rows, decision_ts) if decision_ts else rows
