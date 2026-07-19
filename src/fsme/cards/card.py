# src/fsme/cards/card.py

"""
Base card definition for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from fsme.effects import Effect


@dataclass(slots=True)
class Card:
    """
    Base class for every card in the game.
    """

    name: str

    effects: list[Effect] = field(default_factory=list)

    card_id: str = field(default_factory=lambda: uuid4().hex)

    def add_effect(self, effect: Effect) -> None:
        """
        Attach an effect to this card.
        """
        self.effects.append(effect)

    def remove_effect(self, effect: Effect) -> None:
        """
        Remove an effect from this card.
        """
        self.effects.remove(effect)

    def clear_effects(self) -> None:
        """
        Remove all effects from this card.
        """
        self.effects.clear()