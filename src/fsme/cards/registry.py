# src/fsme/cards/registry.py

"""
Card definition registry for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .definition import CardDefinition
from .errors import DuplicateCardError, UnknownCardError
from .types import CardType


class CardRegistry:
    """
    Every card definition available to a game, indexed by identifier.

    The registry is the engine's card vocabulary. It is filled once, before a
    game starts, and never changed afterwards: definitions are immutable and
    identifiers are permanent, so registering the same id twice is an error.
    """

    def __init__(self, definitions: Iterable[CardDefinition] = ()) -> None:
        self._definitions: dict[str, CardDefinition] = {}

        for definition in definitions:
            self.register(definition)

    def __contains__(self, card_id: object) -> bool:
        return card_id in self._definitions

    def __len__(self) -> int:
        return len(self._definitions)

    def __iter__(self) -> Iterator[CardDefinition]:
        return iter(self._definitions.values())

    def register(self, definition: CardDefinition) -> CardDefinition:
        """
        Add a definition to the registry.
        """
        if definition.id in self._definitions:
            raise DuplicateCardError(
                f"card '{definition.id}' is already registered"
            )

        self._definitions[definition.id] = definition

        return definition

    def register_all(self, definitions: Iterable[CardDefinition]) -> None:
        """
        Add several definitions.
        """
        for definition in definitions:
            self.register(definition)

    def get(self, card_id: str) -> CardDefinition:
        """
        Return a definition by identifier.
        """
        try:
            return self._definitions[card_id]
        except KeyError:
            raise UnknownCardError(f"unknown card '{card_id}'") from None

    def by_type(self, card_type: CardType) -> tuple[CardDefinition, ...]:
        """
        Return every definition of the given type.
        """
        return tuple(
            definition
            for definition in self._definitions.values()
            if definition.type is card_type
        )

    def by_expansion(self, expansion: str) -> tuple[CardDefinition, ...]:
        """
        Return every definition belonging to an expansion.
        """
        return tuple(
            definition
            for definition in self._definitions.values()
            if definition.expansion == expansion
        )

    def ids(self) -> frozenset[str]:
        """
        Return every registered identifier.
        """
        return frozenset(self._definitions)
