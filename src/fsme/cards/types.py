# src/fsme/cards/types.py

"""
Card type definitions for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class CardType(StrEnum):
    """
    Top-level card categories.
    """

    CHARACTER = "character"

    TREASURE = "treasure"

    LOOT = "loot"

    MONSTER = "monster"

    ROOM = "room"

    BONUS_SOUL = "bonus_soul"

    EVENT = "event"

    CURSE = "curse"

    STARTING_ITEM = "starting_item"

    SOUL = "soul"

    TOKEN = "token"

    OTHER = "other"

PRINTED_NUMBERS: Mapping[CardType, tuple[str, ...]] = MappingProxyType(
    {
        CardType.MONSTER: ("health", "attack", "roll"),
        CardType.TREASURE: ("cost",),
        CardType.CHARACTER: ("health",),
        CardType.ROOM: (),
        CardType.LOOT: (),
        CardType.CURSE: (),
    }
)
"""
The numbers each kind of card carries printed on it.

A monster has hit points and a difficulty; a loot card has neither, and asking
somebody for one would be asking them to invent a fact about their card.

Not a rule the loader enforces — a file giving a loot card hit points still
loads, and nothing in a game would ever read them. It is what the printed card
says, which is a different question from what the engine will accept, and the
only one worth putting to an author. The kinds missing from here are the ones
nobody has said anything about; silence is not a claim that they have none.
"""
