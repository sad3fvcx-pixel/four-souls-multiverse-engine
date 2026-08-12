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

    def __post_init__(self) -> None:
        if self.hp is None:
            self.hp = self.definition.health

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
        return self.definition.has_tag(tag)

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
