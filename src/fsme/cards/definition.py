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

    cost: Mapping[str, Any] = field(default_factory=lambda: _EMPTY_MAP)
    """
    What a player pays to use this ability.

    Four Souls prints two kinds of activated ability: ``↷`` taps the item, and
    ``$`` charges something else — cents, a discarded card, a counter — without
    tapping it. The engine treats them as one thing with different prices, so
    ``{"tap": true}`` and ``{"coins": 4}`` go through the same check and the
    same payment.
    """

    replacement: bool = False
    """
    Whether this ability changes an event instead of reacting to one.

    A replacement applies immediately, before the event happens, and never
    uses the stack. A triggered ability waits its turn and resolves after.
    Preventing damage and reacting to damage are different things, and this
    flag is the difference.
    """

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
            cost=freeze(data.get("cost", {})) or _EMPTY_MAP,
            replacement=bool(data.get("replacement", False)),
            scope=str(data["scope"]) if data.get("scope") else None,
            description=str(data.get("description", "")),
        )


@dataclass(frozen=True, slots=True)
class Static:
    """
    A value this card changes for as long as it is in play.

    A static is not an event and never resolves: nothing triggers it and it
    never reaches the stack. The engine simply asks what a number is, and every
    static in play has a say in the answer. That is why "+1 damage while you
    control this" cannot be written as an ability — there is no moment at which
    it happens.
    """

    stat: str = ""

    amount: int = 0

    forbids: str = ""
    """
    An action this card does not allow, for as long as it is in play.

    A prohibition is a static like any other: nothing triggers it, nothing
    resolves it, and the engine simply asks whether an action is allowed before
    letting a player take it. "Other players can't play loot cards on your
    turn" has no moment at which it happens either.
    """

    scope: str = "controller"
    """
    Who the modifier applies to: ``controller``, ``opponents`` or
    ``all_players``.
    """

    conditions: tuple[Any, ...] = ()
    """
    When the modifier applies, beyond its card being in play.

    Conditions are asked every time a value is read, so a modifier that depends
    on the state of the game turns itself on and off without anything having to
    notice that it did.
    """

    description: str = ""

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> Static:
        return cls(
            stat=str(data.get("stat", "")),
            amount=int(data.get("amount", 0)),
            forbids=str(data.get("forbids", "")),
            scope=str(data.get("scope", "controller")),
            conditions=tuple(
                freeze(item) for item in data.get("conditions", ())
            ),
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
    statics: tuple[Static, ...] = ()

    health: int | None = None
    attack: int | None = None
    roll: int | None = None
    cost: int | None = None
    souls: int = 0

    tags: frozenset[str] = frozenset()

    rewards: Mapping[str, int] = field(default_factory=lambda: _EMPTY_MAP)
    """
    What defeating this card pays out, beyond its printed souls.

    Keys the engine understands are ``cents``, ``loot`` and ``treasure``.
    Unknown keys are ignored rather than rejected, so a future reward type does
    not invalidate existing content.
    """

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
            statics=tuple(
                Static.from_data(static) for static in data.get("statics", ())
            ),
            health=data.get("health"),
            attack=data.get("attack"),
            roll=data.get("roll"),
            cost=data.get("cost"),
            souls=int(data.get("souls", 0)),
            tags=frozenset(data.get("tags", ())),
            rewards=freeze(data.get("rewards", {})),
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

    @property
    def is_eternal(self) -> bool:
        """
        Whether this card resists being destroyed or stolen.

        A character's starting item is eternal by definition — losing it would
        leave the character without the thing that defines it — and any card
        may declare itself eternal with a tag.
        """
        return self.type is CardType.STARTING_ITEM or self.has_tag("eternal")

    def __str__(self) -> str:
        return f"{self.id} ({self.name})"
