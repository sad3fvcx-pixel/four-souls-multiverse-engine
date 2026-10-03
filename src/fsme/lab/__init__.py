# src/fsme/lab/__init__.py

"""
The laboratory: everything that studies the game without being part of it.

FSME is two things that happen to live in one repository, and keeping them
apart is what lets either of them be trusted.

**The core** plays Four Souls. Rules, cards, effects, events, state, the stack,
the runtime, and the journal the engine keeps of what it did. It is the thing
that must be right, it is what a saved game and a replay depend on, and it
changes only when the rules do.

**The lab** — this package — asks questions about the game. It plays thousands
of games, counts what happened, weighs decisions, tests a card against its own
absence and writes reports. It changes constantly, because a question nobody
asked yesterday is worth adding today.

The direction of the dependency is the whole point and it runs one way only:
the lab imports the core, and the core has never heard of the lab. Nothing in
here can change how a game is played, which means no report can quietly become
part of the rules, and a measurement cannot alter the thing it measures. That
is enforced by a test rather than by good intentions — see
``tests/test_architecture.py``, which reads the imports and fails if a core
module ever reaches into this package.

Three tools live here:

``bot``
    A player that reasons out loud, so that games can be played by something
    other than chance and its reasoning can be argued with.

``simulation``
    Playing a great many games, on as many cores as there are, keeping the
    kilobyte of each that a question needs and dropping the rest.

``analysis``
    Turning journals into answers: summaries, studies, accounts of single
    games, the moments a game turned on, the decisions it was lost on, and the
    comparison of a deck with and without one card in it.
"""

from __future__ import annotations

__all__ = ["analysis", "bot", "simulation"]
