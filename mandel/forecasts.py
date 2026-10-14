"""
Forecast book.
==============

The central predictive hub's ground truth. Every probabilistic forecast made
by Mandel, by a child, or implied by a market price is recorded here with a
timestamp *before* resolution, then scored with proper scoring rules once
the question resolves. The per-source scoreboard is how Mandel knows
whether a child's model (or its own) is improving, and whether anyone beats
the market.

Rules
-----
- A forecast can only be recorded for an unresolved question.
- Resolutions are final; re-resolving raises.
- ``market_p`` (the market's implied probability at forecast time) is
  stored alongside, so skill versus the market can be computed later.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from mandel.ledger import Ledger, utcnow_iso
from mandel.paths import data_path
from mandel.validation.scoring import (
    brier_score, brier_skill_score, expected_calibration_error, log_loss,
)


@dataclass
class Forecast:
    id: str
    source: str              # "mandel", "child:<name>", "market:polymarket", ...
    question_id: str
    question: str
    p: float
    ts: str
    market_p: Optional[float] = None
    horizon: str = ""
    rationale: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class Resolution:
    question_id: str
    outcome: int
    resolved_at: str
    note: str = ""


@dataclass
class SourceScore:
    source: str
    n: int
    brier: float
    log_loss: float
    ece: float
    skill_vs_market: Optional[float]

    def as_dict(self) -> dict:
        return asdict(self)


class ForecastBook:
    def __init__(self, path: Optional[Path] = None, ledger: Optional[Ledger] = None):
        self.path = Path(path) if path else data_path("forecasts.jsonl")
        self.ledger = ledger if ledger is not None else Ledger()
        self.forecasts: list[Forecast] = []
        self.resolutions: dict[str, Resolution] = {}
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    d = json.loads(line)
                    t = d.pop("_type")
                    if t == "forecast":
                        self.forecasts.append(Forecast(**d))
                    elif t == "resolution":
                        self.resolutions[d["question_id"]] = Resolution(**d)

    def _append(self, kind: str, obj) -> None:
        d = asdict(obj)
        d["_type"] = kind
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    def record(
        self,
        source: str,
        question_id: str,
        question: str,
        p: float,
        market_p: Optional[float] = None,
        horizon: str = "",
        rationale: str = "",
        tags: list[str] | None = None,
    ) -> Forecast:
        if not 0.0 <= p <= 1.0:
            raise ValueError("p must be in [0, 1]")
        if question_id in self.resolutions:
            raise ValueError(f"question {question_id} already resolved; forecast refused")
        fc = Forecast(
            id="F-" + uuid.uuid4().hex[:10], source=source, question_id=question_id,
            question=question, p=float(p), ts=utcnow_iso(), market_p=market_p,
            horizon=horizon, rationale=rationale, tags=sorted(set(tags or [])),
        )
        self.forecasts.append(fc)
        self._append("forecast", fc)
        self.ledger.append("forecast.recorded", {"id": fc.id, "source": source, "question_id": question_id,
                                                 "p": fc.p, "market_p": market_p}, actor=source)
        return fc

    def resolve(self, question_id: str, outcome: int, note: str = "", actor: str = "mandel") -> Resolution:
        if outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")
        if question_id in self.resolutions:
            raise ValueError(f"question {question_id} already resolved")
        res = Resolution(question_id=question_id, outcome=int(outcome), resolved_at=utcnow_iso(), note=note)
        self.resolutions[question_id] = res
        self._append("resolution", res)
        self.ledger.append("forecast.resolved", {"question_id": question_id, "outcome": outcome}, actor=actor)
        return res

    # -- scoring -----------------------------------------------------------
    def scored_pairs(self, source: str) -> tuple[list[float], list[int], list[Optional[float]]]:
        """Latest forecast per resolved question for the source."""
        latest: dict[str, Forecast] = {}
        for fc in self.forecasts:
            if fc.source != source or fc.question_id not in self.resolutions:
                continue
            if fc.question_id not in latest or fc.ts > latest[fc.question_id].ts:
                latest[fc.question_id] = fc
        probs, outcomes, market = [], [], []
        for qid, fc in latest.items():
            probs.append(fc.p)
            outcomes.append(self.resolutions[qid].outcome)
            market.append(fc.market_p)
        return probs, outcomes, market

    def score_source(self, source: str) -> Optional[SourceScore]:
        probs, outcomes, market = self.scored_pairs(source)
        if not probs:
            return None
        skill = None
        if all(m is not None for m in market):
            skill = brier_skill_score(probs, outcomes, [float(m) for m in market])
        return SourceScore(
            source=source, n=len(probs), brier=brier_score(probs, outcomes),
            log_loss=log_loss(probs, outcomes),
            ece=expected_calibration_error(probs, outcomes, n_bins=min(10, max(2, len(probs) // 5))),
            skill_vs_market=skill,
        )

    def scoreboard(self) -> list[SourceScore]:
        sources = sorted({fc.source for fc in self.forecasts})
        out = [s for s in (self.score_source(src) for src in sources) if s is not None]
        return sorted(out, key=lambda s: s.brier)

    def open_questions(self) -> list[str]:
        return sorted({fc.question_id for fc in self.forecasts} - set(self.resolutions))
