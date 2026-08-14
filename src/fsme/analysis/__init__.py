# src/fsme/analysis/__init__.py

"""
Turning games into numbers.

Everything here reads journals and counts. Nothing is measured that the engine
did not already record, and nothing is called an effect that is only a
correlation — a distinction the tally is careful about, because it is the
difference between a balance report and a misleading one.
"""

from __future__ import annotations

from .report import report
from .tally import Seen, Tally

__all__ = ["Seen", "Tally", "report"]
