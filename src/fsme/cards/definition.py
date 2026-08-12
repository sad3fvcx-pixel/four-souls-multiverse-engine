# src/fsme/cards/definition.py

"""
Immutable card definitions for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .types import CardType

_EMPTY_MAP: Mapping[str, Any] = MappingProxyType({})


def freeze(value: Any) -> Any:
    """
    Recursively convert loaded content into read-only data.

    CARD_SCHEMA.md and DEVELOPMENT_GUIDELINES.md both require definitions to be
    immutable after registration. Freezing at load time makes that structural
    rather than a convention: a mutation attempt raises instead of silently
    changing a card mid-game for every instance that shares the definition.
    """
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})

    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)

    return value


@dataclass(frozen=True, slots=True)
class Ability:
    """
    One trigger-condition-effect rule belonging to a card.

    The engine never stores card behaviour as code; it stores this structure
    and interprets it.
    """

    trigger: str

    conditions: tuple[Any, ...] = ()
    targets: tuple[Any, ...] = ()
    effects: tuple[Any, ...] = ()

    optional: bool = False

    scope: str | None = None
    """
    Which events this ability listens to.

    ``"self"`` reacts only when the event concerns this very card, ``"any"``
    reacts to every matching event. Left unset, the engine derives it from the
    trigger: activating one item must not fire every other item's activation
    ability, while a turn starting concerns everybody.
    """

    description: str = ""

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> Ability:
        """
        Build an ability from validated raw content.
        """
        return cls(
            trigger=str(data["trigger"]),
            conditions=tuple(freeze(item) for item in data.get("conditions", ())),
            targets=tuple(freeze(item) for item in data.get("targets", ())),
            effects=tuple(freeze(item) for item in data.get("effects", ())),
            optional=bool(data.get("optional", False)),
            scope=str(data["scope"]) if data.get("scope") else None,
            description=str(data.get("description", "")),
        )


@dataclass(frozen=True, slots=True)
class CardDefinition:
    """
    The immutable description of a card.

    Runtime information belongs to CardInstance; this object is shared by every
    copy of the card in every game.
    """

    id: str
    name: str
    type: CardType
    expansion: str

    abilities: tuple[Ability, ...] = ()

    health: int | None = None
    attack: int | None = None
    roll: int | None = None
    cost: int | None = None
    souls: int = 0

    tags: frozenset[str] = frozenset()

    metadata: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAP)

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> CardDefinition:
        """
        Build a definition from validated raw content.
        """
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            type=CardType(data["type"]),
            expansion=str(data["expansion"]),
            abilities=tuple(
                Ability.from_data(ability) for ability in data.get("abilities", ())
            ),
            health=data.get("health"),
            attack=data.get("attack"),
            roll=data.get("roll"),
            cost=data.get("cost"),
            souls=int(data.get("souls", 0)),
            tags=frozenset(data.get("tags", ())),
            metadata=freeze(data.get("metadata", {})),
        )

    def abilities_for(self, trigger: str) -> tuple[Ability, ...]:
        """
        Return every ability reacting to the given trigger.
        """
        return tuple(
            ability for ability in self.abilities if ability.trigger == trigger
        )

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def __str__(self) -> str:
        return f"{self.id} ({self.name})"
