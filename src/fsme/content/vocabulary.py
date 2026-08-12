# src/fsme/content/vocabulary.py

"""
The names content is allowed to use.

Semantic validation asks whether a card refers to things the engine actually
implements. That question needs the engine's vocabulary, but the pipeline must
not depend on the engine's execution: content loading happens before a game
exists and must never touch one.

So the vocabulary arrives as plain names. The pipeline checks spelling against
a set of strings; whoever owns a live engine is the one who knows what is in
it, and hands the list over.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """
    Every name the engine answers to.
    """

    effects: frozenset[str] = frozenset()
    triggers: frozenset[str] = frozenset()
    conditions: frozenset[str] = frozenset()
    targets: frozenset[str] = frozenset()

    @classmethod
    def of(
        cls,
        *,
        effects: Collection[str] = (),
        triggers: Collection[str] = (),
        conditions: Collection[str] = (),
        targets: Collection[str] = (),
    ) -> Vocabulary:
        """
        Build a vocabulary from any collections of names.
        """
        return cls(
            effects=frozenset(effects),
            triggers=frozenset(triggers),
            conditions=frozenset(conditions),
            targets=frozenset(targets),
        )

    @property
    def is_empty(self) -> bool:
        """
        True when nothing can be checked against this vocabulary.

        An empty vocabulary means schema validation only: structure is still
        enforced, meaning is not.
        """
        return not (self.effects or self.triggers or self.conditions or self.targets)
