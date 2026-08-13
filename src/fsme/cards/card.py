# src/fsme/cards/card.py

"""
Runtime card objects for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .definition import CardDefinition


@dataclass(slots=True)
class CardInstance:
    """
    A card as it exists inside a running game.

    The definition stays immutable and shared; everything that can change
    during a game lives here.
    """

    definition: CardDefinition

    instance_id: str = ""

    owner: int | None = None
    controller: int | None = None

    zone: str = ""

    hp: int | None = None
    tapped: bool = False
    alive: bool = True

    last_damaged_by: int | None = None
    """
    The player who most recently damaged this card.

    A monster pays its reward to whoever defeated it, and that is not always
    the player who declared an attack.
    """

    counters: dict[str, int] = field(default_factory=dict)
    modifiers: list[Any] = field(default_factory=list)

    copy_of: CardDefinition | None = None
    """
    Another card whose rules this one is currently playing by.

    "This becomes a copy of that item" does not turn one card into another: the
    card is still itself, still owned by whoever owns it, still the physical
    thing that gets destroyed. What changes is which rules it has, so the copy
    is kept beside the definition rather than in place of it.
    """

    copy_expires: str = ""
    """
    When the copy lapses, empty when it does not.

    "Till end of turn" and "this change is indefinite" are printed on two
    different cards, and the difference between them is only this.
    """

    def __post_init__(self) -> None:
        if self.hp is None:
            self.hp = self.definition.health

    @property
    def face(self) -> CardDefinition:
        """
        The definition whose rules this card is playing by.

        Everything that asks what a card *does* — its abilities, its statics,
        which families it belongs to — asks this. Everything that asks what a
        card *is* asks the definition: a copy of an item is still the card it
        was printed as, and goes to its own discard pile.
        """
        return self.copy_of if self.copy_of is not None else self.definition

    @property
    def id(self) -> str:
        """
        Return the definition identifier.
        """
        return self.definition.id

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def max_hp(self) -> int:
        return self.definition.health or 0

    def has_tag(self, tag: str) -> bool:
        return self.face.has_tag(tag)

    def __str__(self) -> str:
        return f"{self.definition.name}[{self.instance_id or '?'}]"


@dataclass(slots=True)
class SoulToken:
    """
    A soul held by a player that did not come from a card.

    Souls are counted for victory the same way regardless of origin, so the
    engine represents the ones it mints itself as tokens rather than inventing
    card definitions for them.
    """

    token_id: str = ""

    def __str__(self) -> str:
        return f"soul[{self.token_id or '?'}]"
