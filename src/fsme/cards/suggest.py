# src/fsme/cards/suggest.py

"""
Offering the spelling somebody meant.

Its own module because two checks need it and one of them is imported by the
other. A misspelling is the commonest content mistake there is, and the engine
holds the whole vocabulary already.
"""

from __future__ import annotations

from collections.abc import Collection
from difflib import get_close_matches

SUGGESTIONS = 3
"""
How many spellings to offer before the list becomes something to read rather
than an answer.
"""

CLOSE_ENOUGH = 0.7
"""
How near a name has to be before offering it helps rather than misleads.
"""


def did_you_mean(name: str, known: Collection[str]) -> str:
    """
    Offer the nearest names the engine does know, when any are near.

    The most common content mistake is not a misunderstanding, it is a typo or
    a plural — ``gain_coinz`` for ``gain_coins``, ``draw_loots`` for
    ``draw_loot`` — and the engine holds the whole vocabulary already. Making
    somebody grep the source for the right spelling is a self-inflicted wound.
    """
    close = get_close_matches(name, sorted(known), n=SUGGESTIONS, cutoff=CLOSE_ENOUGH)

    if not close:
        return ""

    return " — did you mean " + " or ".join(f"'{one}'" for one in close) + "?"

