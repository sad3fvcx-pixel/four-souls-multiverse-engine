# src/fsme/lab/analysis/__init__.py

"""
Turning games into numbers, and numbers into something a person can act on.

Everything here reads journals — or the summaries made from them — and counts.
Nothing is measured that the engine did not already record, and nothing is
called an effect that is only a correlation. That distinction is the whole
difference between a balance report and a misleading one, so it is made in the
wording of every table rather than left to the reader.
"""

from __future__ import annotations

from .compare import Comparison, Difference, compare, read_out
from .explain import explain
from .moments import Contribution, Ledger, Moment, Turning, turning_points
from .party import Review, review, reviewed
from .report import report
from .risk import Risks, Risky, risks
from .studied import written
from .study import Oddity, Pair, Split, Study, Suspect, Thinking, study
from .summary import GameSummary, SeatFacts, summarise
from .tally import Seen, Tally

__all__ = [
    "Comparison",
    "Contribution",
    "Difference",
    "GameSummary",
    "Ledger",
    "Moment",
    "Oddity",
    "Pair",
    "Review",
    "Risks",
    "Risky",
    "SeatFacts",
    "Seen",
    "Split",
    "Study",
    "Suspect",
    "Tally",
    "Thinking",
    "Turning",
    "compare",
    "explain",
    "read_out",
    "report",
    "review",
    "reviewed",
    "risks",
    "study",
    "summarise",
    "turning_points",
    "written",
]
