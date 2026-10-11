# src/fsme/lab/simulation/__init__.py

"""
Playing many games instead of one.

A run is a range of seeds played through the ordinary engine by a player who is
not clever, so that what is measured is the game rather than the player.
"""

from __future__ import annotations

from .agent import ScriptedAgent
from .pool import Finished, run_on_many_cores
from .runner import DEFAULT_STEPS, NAMES, Outcome, Progress, play_one, run

PAIRED_RNG_MODEL = "2"
"""
The generator a paired experiment is played on: the one place it is chosen.

A card test plays the same seeds with a card and without it. On model 2 a card
taken out of the content leaves every other card where it was, so the two games
stay one game until the card itself does something; on model 1 the deck it came
out of is shuffled into another deck. Model 2 is also what a new game is dealt
on by default, but a card test does not rely on that: it names the model it
needs.
"""

__all__ = [
    "DEFAULT_STEPS",
    "Finished",
    "NAMES",
    "Outcome",
    "PAIRED_RNG_MODEL",
    "Progress",
    "ScriptedAgent",
    "play_one",
    "run",
    "run_on_many_cores",
]
