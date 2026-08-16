# src/fsme/journal/file.py

"""
A journal as a file somebody keeps, sends on, or opens next year.

There is no second format here. A journal already serialises itself —
``Journal.to_dict`` and ``Journal.from_dict``, versioned by
``JOURNAL_FORMAT_VERSION`` — and this module puts that dictionary inside a
named envelope and takes it back out again. Everything a saved game contains is
whatever the journal contains, which is the point: the file that comes out of
Save is the same data the live page was reading, so a game that has been saved
and reloaded is not a different kind of thing from a game being watched.

The envelope earns its place by answering one question the journal cannot: *is
this one of ours at all*. A user picks a file from a disk full of files, and
``Journal.from_dict`` handed an arbitrary JSON object would either raise
something about a missing key or, worse, succeed on something that happened to
have the right shape. So the envelope is checked first, and each way it can be
wrong gets its own sentence — the same courtesy the report loader already
extends, for the same reason.
"""

from __future__ import annotations

import time
from typing import Any

from .entry import JOURNAL_FORMAT_VERSION, Journal, JournalFormatError

MARKER = "fsme-journal"
"""
What the file says it is.

A string rather than a mere version number, so a file that is not ours is
recognised as not ours instead of being read as a very old one.
"""

FILE_VERSION = 1
"""
The version of the envelope, which is not the version of the journal inside it.

Two numbers because they change for different reasons. The journal's format
changes when what a game records changes; this changes when what a *file*
carries around a journal changes — a second journal, a note, a signature. Today
it carries one journal and nothing else.
"""


def wrap(journal: Journal) -> dict[str, Any]:
    """
    A journal, ready to be written to a file.
    """
    return {
        "format": MARKER,
        "version": FILE_VERSION,
        "journal": journal.to_dict(),
    }


def unwrap(given: Any) -> Journal:
    """
    Read a saved journal back, or say precisely what is wrong with it.

    Checked in the order somebody would want to hear it: that this is a file at
    all, that it is one of ours, that this FSME is new enough to open it, that
    there is a game inside, and finally that the game is one this engine
    understands. A single "invalid file" would be true and useless.
    """
    if not isinstance(given, dict):
        raise JournalFormatError(
            "that file does not hold anything FSME can read — a saved journal"
            " is the file the Save journal button writes"
        )

    if given.get("format") != MARKER:
        named = given.get("format")

        if "fsme_report" in given:
            raise JournalFormatError(
                "that is a saved report, not a saved journal. Open it with"
                " Load report instead — it carries a game and an analysis of"
                " it, and this reads plain journals"
            )

        raise JournalFormatError(
            f"that is not an FSME journal: it calls itself {named!r}"
            if named
            else "that is not an FSME journal — it does not say what it is"
        )

    version = given.get("version")

    if not isinstance(version, int) or isinstance(version, bool):
        raise JournalFormatError(
            f"that journal file has no readable version, only {version!r}"
        )

    if version > FILE_VERSION:
        raise JournalFormatError(
            f"that journal file is written in version {version}, and this FSME"
            f" reads version {FILE_VERSION}. It was saved by a newer version."
        )

    inside = given.get("journal")

    if not isinstance(inside, dict):
        raise JournalFormatError(
            "that journal file has no game in it, so there is nothing to read"
        )

    # And now the journal's own version check, which is a different question
    # and gets its own answer.
    return Journal.from_dict(inside)


def suggested_name(journal: Journal) -> str:
    """
    What to call the file, so a directory of them can be told apart.

    The seed is the name of the game — the one thing that deals it again — so
    it is what the file is called. A journal without one is a journal of a game
    that cannot be re-dealt, and the time it was saved is the only handle left.
    """
    if journal.seed:
        return f"fsme-journal-seed-{journal.seed}.json"

    return f"fsme-journal-{time.strftime('%Y%m%d-%H%M%S')}.json"


__all__ = [
    "FILE_VERSION",
    "JOURNAL_FORMAT_VERSION",
    "MARKER",
    "JournalFormatError",
    "suggested_name",
    "unwrap",
    "wrap",
]
