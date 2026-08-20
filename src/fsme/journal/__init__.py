# src/fsme/journal/__init__.py

"""
The story of a game, kept as data.

A replay says what was played. A journal says what was played, what else could
have been, where the game stood at the time, and everything that followed —
which is the difference between reproducing a game and being able to explain
one.

Everything in here is what the engine already produced. Nothing is measured,
instrumented or inferred: the events are the engine's events and the moves are
the engine's answers, kept instead of discarded.
"""

from __future__ import annotations

from .entry import (
    JOURNAL_FORMAT_VERSION,
    READABLE_FORMATS,
    Entry,
    Happening,
    Journal,
    JournalFormatError,
    Position,
)
from .file import FILE_VERSION, MARKER, read, suggested_name, unwrap, wrap
from .keeper import JournalKeeper
from .render import render
from .replay import Divergence, Playback, replay_journal, summarise

__all__ = [
    "Divergence",
    "FILE_VERSION",
    "MARKER",
    "Entry",
    "Happening",
    "JOURNAL_FORMAT_VERSION",
    "READABLE_FORMATS",
    "Journal",
    "JournalFormatError",
    "JournalKeeper",
    "Playback",
    "Position",
    "read",
    "render",
    "replay_journal",
    "suggested_name",
    "summarise",
    "unwrap",
    "wrap",
]
