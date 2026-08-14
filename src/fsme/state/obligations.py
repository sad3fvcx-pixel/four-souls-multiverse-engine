# src/fsme/state/obligations.py

"""
What a player must do before their turn can end.

The engine allows and forbids; this is the third thing cards ask for. "The
active player must attack that monster this turn if able" is neither a
permission nor a prohibition — it is a debt, and it is paid by doing the thing.

An obligation is kept on the turn because that is how long it lasts. Nothing
carries over: a turn that ends with an obligation nobody could pay ends anyway,
because "if able" is part of what the cards say.
"""

from __future__ import annotations

from dataclasses import dataclass

ATTACK = "attack"
"""Declaring an attack."""


@dataclass(slots=True)
class Obligation:
    """
    One thing a player owes this turn.

    ``card_id`` names the object it must be done to, when the card names one:
    Monster Manual points at a monster, while an extra attack owed after a
    monster dies may be spent on anything.
    """

    player_id: int

    action: str = ATTACK

    card_id: str | None = None

    remaining: int = 1

    def matches(self, action: str, player_id: int, card_id: str | None) -> bool:
        """
        Return whether doing this pays the debt.
        """
        if self.action != action or self.player_id != player_id:
            return False

        return self.card_id is None or self.card_id == card_id

    def __str__(self) -> str:
        what = self.card_id or "anything"

        return f"player {self.player_id} must {self.action} {what} ({self.remaining})"
