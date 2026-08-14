# src/fsme/content/library.py

"""
Loaded content.

A library is every set the engine knows about, already validated. It is built
before a game starts and never changes afterwards: definitions are immutable,
and a game that could gain cards halfway through would not be reproducible.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from fsme.cards import CardDefinition, CardRegistry, CardType

from .errors import ContentNotFoundError, DuplicateContentError, MissingDependencyError
from .manifest import Manifest


@dataclass(frozen=True, slots=True)
class Expansion:
    """
    One content set and the cards it brings.
    """

    manifest: Manifest

    definitions: tuple[CardDefinition, ...] = ()

    def __len__(self) -> int:
        return len(self.definitions)

    @property
    def id(self) -> str:
        return self.manifest.id

    def by_type(self, card_type: CardType) -> tuple[CardDefinition, ...]:
        return tuple(
            definition
            for definition in self.definitions
            if definition.type is card_type
        )

    def __str__(self) -> str:
        return f"{self.manifest} ({len(self.definitions)} cards)"


@dataclass(slots=True)
class ContentLibrary:
    """
    Every expansion available to a game.
    """

    expansions: dict[str, Expansion] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.expansions)

    def __contains__(self, expansion_id: object) -> bool:
        return expansion_id in self.expansions

    def __iter__(self) -> Iterator[Expansion]:
        return iter(self.expansions.values())

    def add(self, expansion: Expansion) -> Expansion:
        """
        Add an expansion to the library.
        """
        if expansion.id in self.expansions:
            raise DuplicateContentError(
                f"expansion '{expansion.id}' is already loaded"
            )

        self.expansions[expansion.id] = expansion

        return expansion

    def get(self, expansion_id: str) -> Expansion:
        """
        Return one expansion.
        """
        try:
            return self.expansions[expansion_id]
        except KeyError:
            raise ContentNotFoundError(
                f"expansion '{expansion_id}' is not loaded"
            ) from None

    def definitions(self) -> tuple[CardDefinition, ...]:
        """
        Return every card in the library, in a stable order.
        """
        cards: list[CardDefinition] = []

        for expansion_id in sorted(self.expansions):
            cards.extend(self.expansions[expansion_id].definitions)

        return tuple(cards)

    def without(self, card_ids: Iterable[str]) -> ContentLibrary:
        """
        The same library with some cards taken out of it.

        This is what a card test runs against: the game as it would be if the
        card had never been printed. Nothing is loaded again and nothing is
        mutated — the expansions are rebuilt around the cards that remain, so
        the library asked the question keeps its own answer.
        """
        removing = frozenset(card_ids)

        smaller = ContentLibrary()

        for expansion_id in sorted(self.expansions):
            expansion = self.expansions[expansion_id]

            smaller.add(
                Expansion(
                    manifest=expansion.manifest,
                    definitions=tuple(
                        definition
                        for definition in expansion.definitions
                        if definition.id not in removing
                    ),
                )
            )

        return smaller

    def check_dependencies(self) -> None:
        """
        Refuse a library where an expansion is missing something it needs.
        """
        for expansion in self:
            for required in expansion.manifest.requires:
                if required not in self.expansions:
                    raise MissingDependencyError(
                        f"expansion '{expansion.id}' requires '{required}', "
                        f"which is not loaded"
                    )

    def registry(self) -> CardRegistry:
        """
        Build the card registry a game plays with.

        Identifiers are globally unique, so two sets defining the same card is
        a content error and not something to silently resolve one way.
        """
        return CardRegistry(self.definitions())

    def cards_of(self, card_type: CardType) -> tuple[CardDefinition, ...]:
        """
        Return every card of one type across the whole library.
        """
        return tuple(
            definition
            for definition in self.definitions()
            if definition.type is card_type
        )

    def summary(self) -> str:
        """
        Return a one-line-per-expansion description.
        """
        if not self.expansions:
            return "no content loaded"

        return "\n".join(
            str(self.expansions[key]) for key in sorted(self.expansions)
        )
