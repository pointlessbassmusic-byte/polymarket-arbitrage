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
- Question ids are normalised (trimmed, case-folded). A forecast can only
  be recorded for an unresolved question, and a resolved question's exact
  text cannot be re-opened under a new id.
- Resolutions are final and require at least one recorded forecast.
- Skill versus the market uses the latest ``market:*`` forecast recorded on
  the same question at or before the forecaster's own timestamp. A
  forecaster's self-reported ``market_p`` is used only when no market source
  exists, and the score says so.
"""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from mandel._io import append_line, file_lock
from mandel.ledger import Ledger, utcnow_iso
from mandel.paths import data_path
from mandel.validation.scoring import (
    brier_score, brier_skill_score, expected_calibration_error, log_loss,
)


def norm_qid(q: str) -> str:
    return re.sub(r"\s+", " ", str(q)).strip().casefold()


def _norm_text(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(t).casefold()).strip()


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
    market_reference: str = "none"      # "market-source" | "self-reported" | "mixed" | "none"

    def as_dict(self) -> dict:
        return asdict(self)


class ForecastBook:
    def __init__(self, path: Optional[Path] = None, ledger: Optional[Ledger] = None):
        self.path = Path(path) if path else data_path("forecasts.jsonl")
        self.ledger = ledger if ledger is not None else Ledger()
        self.forecasts: list[Forecast] = []
        self.resolutions: dict[str, Resolution] = {}
        self._load()

    def _load(self) -> None:
        self.forecasts, self.resolutions = [], {}
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
        append_line(self.path, json.dumps(d, ensure_ascii=False))

    @staticmethod
    def _check_prob(name: str, v: Optional[float], required: bool) -> Optional[float]:
        if v is None:
            if required:
                raise ValueError(f"{name} is required")
            return None
        if isinstance(v, bool):
            raise ValueError(f"{name} must be a number")
        f = float(v)
        if not (math.isfinite(f) and 0.0 <= f <= 1.0):
            raise ValueError(f"{name} must be in [0, 1], got {v!r}")
        return f

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
        p = self._check_prob("p", p, required=True)
        market_p = self._check_prob("market_p", market_p, required=False)
        qid = norm_qid(question_id)
        if not qid:
            raise ValueError("question_id is empty")
        if not str(source).strip():
            raise ValueError("source is empty")
        with file_lock(self.path):
            self._load()
            if qid in self.resolutions:
                raise ValueError(f"question {qid} already resolved; forecast refused")
            qtext = _norm_text(question)
            if qtext:
                for fc in self.forecasts:
                    if fc.question_id in self.resolutions and _norm_text(fc.question) == qtext:
                        raise ValueError(f"this question text already resolved as {fc.question_id}; "
                                         f"a new id does not reopen it")
            fc = Forecast(id="F-" + uuid.uuid4().hex[:10], source=source.strip(), question_id=qid,
                          question=question, p=p, ts=utcnow_iso(), market_p=market_p,
                          horizon=horizon, rationale=rationale, tags=sorted(set(tags or [])))
            self.forecasts.append(fc)
            self._append("forecast", fc)
        self.ledger.append("forecast.recorded", {"id": fc.id, "source": fc.source, "question_id": qid,
                                                 "p": fc.p, "market_p": market_p}, actor=fc.source)
        return fc

    def resolve(self, question_id: str, outcome: int, note: str = "", actor: str = "mandel") -> Resolution:
        if isinstance(outcome, bool) or outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")
        qid = norm_qid(question_id)
        with file_lock(self.path):
            self._load()
            if qid in self.resolutions:
                raise ValueError(f"question {qid} already resolved")
            if qid not in {fc.question_id for fc in self.forecasts}:
                raise ValueError(f"no forecasts recorded for {qid!r}; open questions: {self.open_questions()}")
            res = Resolution(question_id=qid, outcome=int(outcome), resolved_at=utcnow_iso(), note=note)
            self.resolutions[qid] = res
            self._append("resolution", res)
        self.ledger.append("forecast.resolved", {"question_id": qid, "outcome": int(outcome)}, actor=actor)
        return res

    # -- scoring -----------------------------------------------------------
    def _market_reference(self, fc: Forecast) -> tuple[Optional[float], str]:
        """Latest market:* forecast on the same question at or before fc.ts."""
        best: Optional[Forecast] = None
        for m in self.forecasts:
            if m.source.startswith("market:") and m.question_id == fc.question_id and m.ts <= fc.ts:
                if best is None or m.ts >= best.ts:
                    best = m
        if best is not None:
            return best.p, "market-source"
        if fc.market_p is not None:
            return fc.market_p, "self-reported"
        return None, "none"

    def scored_pairs(self, source: str) -> tuple[list[float], list[int], list[Optional[float]], list[str]]:
        """Latest forecast per resolved question for the source, with its market reference."""
        latest: dict[str, Forecast] = {}
        for fc in self.forecasts:
            if fc.source != source or fc.question_id not in self.resolutions:
                continue
            if fc.question_id not in latest or fc.ts >= latest[fc.question_id].ts:
                latest[fc.question_id] = fc
        probs, outcomes, market, refs = [], [], [], []
        for qid, fc in latest.items():
            ref_p, ref_kind = self._market_reference(fc)
            probs.append(fc.p)
            outcomes.append(self.resolutions[qid].outcome)
            market.append(ref_p)
            refs.append(ref_kind)
        return probs, outcomes, market, refs

    def score_source(self, source: str) -> Optional[SourceScore]:
        probs, outcomes, market, refs = self.scored_pairs(source)
        if not probs:
            return None
        skill, ref_label = None, "none"
        if all(m is not None for m in market):
            try:
                skill = brier_skill_score(probs, outcomes, [float(m) for m in market])
            except ValueError:
                skill = None
            kinds = set(refs)
            ref_label = refs[0] if len(kinds) == 1 else "mixed"
        return SourceScore(
            source=source, n=len(probs), brier=brier_score(probs, outcomes),
            log_loss=log_loss(probs, outcomes),
            ece=expected_calibration_error(probs, outcomes, n_bins=min(10, max(2, len(probs) // 5))),
            skill_vs_market=skill, market_reference=ref_label,
        )

    def scoreboard(self) -> list[SourceScore]:
        sources = sorted({fc.source for fc in self.forecasts})
        out = [s for s in (self.score_source(src) for src in sources) if s is not None]
        return sorted(out, key=lambda s: s.brier)

    def open_questions(self) -> list[str]:
        return sorted({fc.question_id for fc in self.forecasts} - set(self.resolutions))
