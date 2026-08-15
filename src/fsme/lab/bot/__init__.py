# src/fsme/lab/bot/__init__.py

"""
Players that are not people.

A bot here is judged by whether its reasoning can be read, not by whether it
wins: the point of writing a bot in an analytical engine is to have a player
whose mistakes you can find.
"""

from __future__ import annotations

from .evaluation import Decision, Evaluation, Reason
from .heuristic import NAME, HeuristicBot

__all__ = ["NAME", "Decision", "Evaluation", "HeuristicBot", "Reason"]
