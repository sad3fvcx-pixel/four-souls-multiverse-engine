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

These are the words for a choice — "type: an item kept in play" — and read as
fragments, which is why they are not what a card of this kind is *called*. That
is `TYPE_LABELS`.
"""


TYPE_LABELS: Mapping[CardType, str] = MappingProxyType(
    {
        CardType.LOOT: "Loot card",
        CardType.TREASURE: "Treasure",
        CardType.MONSTER: "Monster",
        CardType.CHARACTER: "Character",
        CardType.ROOM: "Room",
        CardType.CURSE: "Curse",
        CardType.STARTING_ITEM: "Starting item",
        CardType.EVENT: "Event",
        CardType.BONUS_SOUL: "Bonus soul",
        CardType.SOUL: "Soul",
        CardType.TOKEN: "Token",
        CardType.OTHER: "Other",
    }
)
"""
What a card of each kind is called, in a heading or on the card's own face.

`TYPE_WORDS` cannot do this. It completes a sentence about a choice, so it
reads as a fragment on its own — "Your an item kept in play" — and a page
wanting to say "Your treasure" has nowhere else to look. This is the missing
half, and the only fact about a card type that was ever kept anywhere but here.

The order is the other thing this says: the kinds in the order an author meets
them, most often made first. `CardType`'s own order is read elsewhere — it is
what `CARD_TYPES` offers in two search filters — so it cannot be about that.
"""


PRINTED_NUMBERS: Mapping[CardType, tuple[str, ...]] = MappingProxyType(
    {
        CardType.MONSTER: ("health", "attack", "roll"),
        CardType.TREASURE: ("cost",),
        CardType.CHARACTER: ("health", "attack"),
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

Being wrong here is not harmless, which is why a test checks it against the
content. A number left out of a kind that has one is a number the form greys
out and the builder then leaves off the card — so an author who opens such a
card and saves it loses it, silently. That is what happened to a character's
attack, which 93 of the 97 shipped characters carry and the card face prints.
"""
