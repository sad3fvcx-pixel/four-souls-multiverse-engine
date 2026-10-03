# src/fsme/content/workspace.py

"""
Where an author's own sets live.

FSME ships as one executable, and a frozen build carries its cards *inside*
itself — unpacked into a temporary directory that the operating system wipes
when the program closes. That is the right place for the cards we ship and the
worst possible place for the cards somebody writes: a set saved there is gone
before it can be played twice.

So an author's work goes somewhere it survives, chosen by the program rather
than typed by the person. Nobody should have to know what `content/` is, where
they installed anything, or that a bundle exists at all.

The place is deliberately somewhere a person can find in a file manager and
back up, because eventually somebody will want to send a set to a friend, and
"it is in a folder called FSME in your documents" is an answer. A cache
directory would not be.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

FOLDER = "FSME"
"""
The name of the directory, as it appears to a person.
"""

SETS = "my sets"
"""
Where the author's expansions go, one directory each.

Spelled the way it would be said. This is read by people far more often than
by anything else.
"""

ENVIRONMENT = "FSME_HOME"
"""
An override, for somebody who has a reason.

Tests use it, and so does anybody keeping their work on another drive. It is
not something an ordinary author ever needs to know exists.
"""


def home() -> Path:
    """
    The directory FSME keeps an author's work in.

    ``FSME_HOME`` wins if it is set. Otherwise this is a folder in the place
    the operating system means by "the user's documents", falling back to the
    home directory when there is no such place.

    Nothing is created here — asking where something is should not make it.
    """
    override = os.environ.get(ENVIRONMENT, "").strip()

    if override:
        return Path(override).expanduser()

    return _documents() / FOLDER


def sets_directory() -> Path:
    """
    The directory holding one folder per set, made if it is not there yet.
    """
    where = home() / SETS
    where.mkdir(parents=True, exist_ok=True)

    return where


def _documents() -> Path:
    """
    Where this machine keeps a person's documents.

    Windows and macOS both have a Documents directory and both call it that.
    Elsewhere there may be one, translated or not, and if there is not then
    the home directory is where a person's things go.
    """
    house = Path.home()
    papers = house / "Documents"

    return papers if papers.is_dir() else house


def is_readable_name(name: str) -> bool:
    """
    Whether a set's name can be turned into an identifier at all.
    """
    return bool(identifier_for(name))


def identifier_for(name: str) -> str:
    """
    The identifier a set gets from the name a person typed.

    "Bob's Big Box" becomes ``bobs_big_box``. An author never types an
    identifier: they name their set, and the name is what they see everywhere
    afterwards. The identifier exists because cards need one and must be
    unique, and deriving it is the difference between one question and two.
    """
    # An apostrophe is dropped rather than replaced: "Bob's Box" is
    # `bobs_box`, which is what somebody would have written by hand.
    bare = name.strip().lower().replace("'", "").replace("\u2019", "")
    folded = re.sub(r"[^a-z0-9]+", "_", bare)

    return folded.strip("_")


def card_identifier(expansion: str, card_type: str, name: str) -> str:
    """
    The identifier one card gets, following the convention every set uses.

    ``expansion-type-name``, which is what the shipped content does and what
    keeps two authors' sets from colliding. Also never typed by anybody.
    """
    return "-".join(
        part
        for part in (expansion, card_type, identifier_for(name))
        if part
    )
