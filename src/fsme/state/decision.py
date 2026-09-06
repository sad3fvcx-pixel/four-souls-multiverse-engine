# src/fsme/state/decision.py

"""
Pending player decisions for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DecisionKind(StrEnum):
    """
    What a player is being asked to pick.
    """

    CHOOSE_PLAYER = "choose_player"
    CHOOSE_MONSTER = "choose_monster"
    CHOOSE_TREASURE = "choose_treasure"
    CHOOSE_LOOT = "choose_loot"
    CHOOSE_CARD = "choose_card"
    CHOOSE_OPTION = "choose_option"


@dataclass(slots=True)
class PendingDecision:
    """
    A question the engine is waiting on before it can go any further.

    An ability that says "choose a player" cannot finish until somebody
    chooses, so the engine stops mid-resolution and records everything it needs
    to carry on afterwards. That record lives here, inside GameState, because
    a game saved while a player is deciding has to reload still deciding.

    ``continuation`` is the suspended ability: the stack object, its context and
    the effects it had not run yet. It is opaque to everything except the
    Runtime that created it.
    """

    decision_id: str

    player: int

    kind: DecisionKind

    options: list[Any] = field(default_factory=list)

    minimum: int = 1
    maximum: int = 1

    bind: str = "chosen"

    prompt: str = ""

    continuation: Any = None

    chosen: list[Any] | None = None
    """
    The answer, once a player has given one.

    The rules write it here and the Runtime picks it up on its next pass, the
    same way a passed priority is recorded and then acted on.
    """

    def accepts(self, count: int) -> bool:
        """
        Return True if choosing this many options satisfies the question.
        """
        return self.minimum <= count <= self.maximum

    def __str__(self) -> str:
        return f"{self.kind}(player={self.player}, options={len(self.options)})"
