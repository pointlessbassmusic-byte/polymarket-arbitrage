"""
Mandel: a self-improving predictive knowledge substrate.
=========================================================

Mandel is the central hub that learns from external resources and from
sibling Claude Code sessions ("the children"), proposes improvements to
itself and to them, and adopts only improvements that pass a validation
gate.

Honest framing: Mandel is a session-bound language model. It cannot
change its own weights. Everything it "learns" lives here, in versioned
files: insights with provenance, an append-only ledger, pre-registered
improvement proposals, forecast records, and the evaluators that decide
what counts as a real improvement. Self-improvement means improving this
substrate and the processes that read and write it.

Package layout
--------------
- ``mandel.ledger``       append-only, hash-chained event log (tamper-evident memory)
- ``mandel.store``        insights with provenance, confidence and validation status
- ``mandel.proposals``    improvement proposals with pre-registered success criteria
- ``mandel.forecasts``    forecast records and per-source calibration scoreboard
- ``mandel.children``     registry and message protocol for the child sessions
- ``mandel.validation``   proper scoring rules, walk-forward comparison, deflated Sharpe, the gate
- ``mandel.cli``          ``python -m mandel ...``
"""

__version__ = "0.1.0"
__codename__ = "Mandel"

from mandel.paths import MANDEL_ROOT, DATA_ROOT  # noqa: F401
