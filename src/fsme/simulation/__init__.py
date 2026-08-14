# src/fsme/simulation/__init__.py

"""
Playing many games instead of one.

A run is a range of seeds played through the ordinary engine by a player who is
not clever, so that what is measured is the game rather than the player.
"""

from __future__ import annotations

from .agent import ScriptedAgent
from .runner import DEFAULT_STEPS, NAMES, Outcome, Progress, play_one, run

__all__ = [
    "DEFAULT_STEPS",
    "NAMES",
    "Outcome",
    "Progress",
    "ScriptedAgent",
    "play_one",
    "run",
]
