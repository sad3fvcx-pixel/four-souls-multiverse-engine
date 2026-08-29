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

TYPE_WORDS = {
    CardType.CHARACTER: "a character somebody plays as",
    CardType.TREASURE: "an item kept in play",
    CardType.LOOT: "a loot card, played from hand and discarded",
    CardType.MONSTER: "a monster to fight",
    CardType.ROOM: "a room that changes the table",
    CardType.BONUS_SOUL: "a soul earned for doing something",
    CardType.EVENT: "an event",
    CardType.CURSE: "a curse that sticks to a player",
    CardType.STARTING_ITEM: "a character's own starting item",
    CardType.SOUL: "a soul",
    CardType.TOKEN: "a token",
    CardType.OTHER: "something else",
}
"""
What each kind of card is, in the words a person would use for it.

The engine accepts all twelve. Six of them are what an author usually makes,
and the rest exist because the shipped content has them — so they are described
rather than hidden, and whatever offers them decides how prominent to be.
"""


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
