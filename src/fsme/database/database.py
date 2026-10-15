# src/fsme/database/database.py

"""
Content indexing.

A library knows what was loaded; an index knows how to find it. Deck building,
a card editor's search box and any query more specific than "every card" would
otherwise walk the whole collection each time.

The index is built once from an immutable library, so it can never disagree
with what the game is actually playing with.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from fsme.cards import CardDefinition, CardType
from fsme.content import ContentLibrary


class ContentIndex:
    """
    Lookups over a loaded content library.
    """

    def __init__(self, definitions: Iterable[CardDefinition] = ()) -> None:
        self._by_id: dict[str, CardDefinition] = {}
        self._by_type: dict[CardType, list[CardDefinition]] = {}
        self._by_expansion: dict[str, list[CardDefinition]] = {}
        self._by_tag: dict[str, list[CardDefinition]] = {}

        for definition in definitions:
            self._add(definition)

    @classmethod
    def of(cls, library: ContentLibrary) -> ContentIndex:
        """
        Index a whole library.
        """
        return cls(library.definitions())

    def _add(self, definition: CardDefinition) -> None:
        self._by_id[definition.id] = definition

        self._by_type.setdefault(definition.type, []).append(definition)
        self._by_expansion.setdefault(definition.expansion, []).append(definition)

        for tag in sorted(definition.tags):
            self._by_tag.setdefault(tag, []).append(definition)

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, card_id: object) -> bool:
        return card_id in self._by_id

    def __iter__(self) -> Iterator[CardDefinition]:
        return iter(self._by_id.values())

    def get(self, card_id: str) -> CardDefinition | None:
        """
        Return a card by identifier, or None.
        """
        return self._by_id.get(card_id)

    def by_type(self, card_type: CardType) -> tuple[CardDefinition, ...]:
        """
        Return every card of a type, in load order.
        """
        return tuple(self._by_type.get(card_type, ()))

    def by_expansion(self, expansion: str) -> tuple[CardDefinition, ...]:
        """
        Return every card from one set.
        """
        return tuple(self._by_expansion.get(expansion, ()))

    def by_tag(self, tag: str) -> tuple[CardDefinition, ...]:
        """
        Return every card carrying a tag.
        """
        return tuple(self._by_tag.get(tag, ()))

    def types(self) -> tuple[CardType, ...]:
        """
        Return every card type present, in a stable order.
        """
        return tuple(sorted(self._by_type, key=str))

    def tags(self) -> tuple[str, ...]:
        """
        Return every tag present, in a stable order.
        """
        return tuple(sorted(self._by_tag))

    def expansions(self) -> tuple[str, ...]:
        """
        Return every expansion present, in a stable order.
        """
        return tuple(sorted(self._by_expansion))

    def counts(self) -> dict[str, int]:
        """
        Return how many cards there are of each type.
        """
        return {str(key): len(value) for key, value in sorted(
            self._by_type.items(), key=lambda item: str(item[0])
        )}
