# src/fsme/effects/context.py

"""
Execution surface available to effect handlers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from fsme.events import Event, EventType
from fsme.rng.rng import RNG
from fsme.stack import StackItem
from fsme.state import GameState


class EffectContext(Protocol):
    """
    Everything an effect is allowed to do, and nothing more.

    This protocol is the boundary that keeps the dependency order intact.
    Effects sit below the Runtime and must not import it, so the Runtime's
    ExecutionContext satisfies this protocol structurally instead.

    An effect changing GameState is therefore always doing so through an
    object the Runtime created and handed to it.
    """

    @property
    def state(self) -> GameState:
        """
        The single authoritative game state.
        """
        ...

    @property
    def rng(self) -> RNG:
        """
        The only source of randomness available to gameplay.
        """
        ...

    @property
    def actor(self) -> int | None:
        """
        The player this work is being done for, when there is one.
        """
        ...

    def emit(
        self,
        event_type: EventType,
        *,
        source: Any | None = None,
        controller: int | None = None,
        targets: list[Any] | None = None,
        **payload: Any,
    ) -> Event:
        """
        Queue an event describing a change that just happened.
        """
        ...

    def push(self, item: StackItem) -> StackItem:
        """
        Place a pending action on the stack.
        """
        ...

    def roll(self, sides: int = 6) -> int:
        """
        Roll a die through the engine RNG.
        """
        ...

    def apply(
        self,
        effect: str,
        targets: Sequence[Any],
        **params: Any,
    ) -> Any:
        """
        Run another registered effect.

        This is how a rule such as combat deals damage: it goes through the
        same effect library as a card would, so there is one implementation of
        "deal damage" and one place it can be changed.
        """
        ...
