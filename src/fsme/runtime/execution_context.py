# src/fsme/runtime/execution_context.py

"""
The channel through which effects reach the game.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from fsme.effects import EffectRegistry
from fsme.effects.errors import EffectExecutionError
from fsme.events import Event, EventType
from fsme.rng.rng import RNG
from fsme.stack import StackItem
from fsme.state import GameState


class ExecutionContext:
    """
    The only object that lets gameplay code touch a running game.

    Effects and rules never see the Runtime itself. They receive this context,
    whose surface is the complete definition of what gameplay code may do: read
    the state, queue an event, push onto the stack, roll a die, run another
    registered effect. Because only the Runtime constructs it, the invariant
    "GameState changes only under the Runtime" holds by construction rather
    than by discipline.
    """

    __slots__ = (
        "_state",
        "_rng",
        "_effects",
        "_emit",
        "_push",
        "_propose",
        "_actor",
        "_event",
        "_source",
        "_answerable_rolls",
        "_settled_roll",
        "_request_roll",
    )

    def __init__(
        self,
        state: GameState,
        rng: RNG,
        effects: EffectRegistry,
        *,
        emit: Callable[[Event], Event],
        push: Callable[[StackItem], StackItem],
        propose: Callable[[Event], Event],
        request_roll: Callable[[int, bool], None] | None = None,
    ) -> None:
        self._state = state
        self._rng = rng
        self._effects = effects
        self._emit = emit
        self._push = push
        self._propose = propose
        self._actor: int | None = None
        self._event: Event | None = None
        self._source: Any | None = None
        self._answerable_rolls = False
        self._settled_roll: int | None = None
        self._request_roll = request_roll if request_roll is not None else _no_rolls

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def rng(self) -> RNG:
        return self._rng

    @property
    def actor(self) -> int | None:
        """
        The player on whose behalf the current work is being done.

        An effect needs this to attribute what it does. Damage has to remember
        who dealt it, or a monster that dies outside combat has nobody to pay
        its reward to. Only the Runtime sets it, and only around one piece of
        resolution at a time — gameplay is single-threaded, so there is exactly
        one actor at any moment.
        """
        return self._actor

    def _set_actor(self, player: int | None) -> None:
        """
        Runtime-only: name the player the next work is done for.
        """
        self._actor = player

    @property
    def source(self) -> Any | None:
        """
        The card whose ability is being resolved, when there is one.

        A card that attaches itself to a player has to be able to name itself,
        and the ability that does it should not have to be told which card it
        belongs to.
        """
        return self._source

    def _set_source(self, source: Any | None) -> None:
        """
        Runtime-only: name the card the next work belongs to.
        """
        self._source = source

    @property
    def answerable_rolls(self) -> bool:
        """
        Whether a roll should stop and let the table respond to it.

        Only true when the game is being played with priority windows: with
        nobody to answer, opening a window would only add a step.
        """
        return self._answerable_rolls

    def _set_answerable_rolls(self, answerable: bool) -> None:
        self._answerable_rolls = answerable

    def request_roll(self, sides: int = 6, *, attack: bool = False) -> None:
        """
        Ask the Runtime to roll and open the roll to the table.

        Used by the engine's own procedures, which cannot be parked the way an
        ability can: a combat round pushes the blow that follows and then asks
        for the roll, so the answer resolves in between.
        """
        self._request_roll(sides, attack)

    def take_settled_roll(self) -> int | None:
        """
        Take the result of a roll the table has finished answering.

        It is taken rather than read: the ability resumes at the very operation
        that rolled, and that operation must use this result instead of rolling
        again — but only once.
        """
        value = self._settled_roll
        self._settled_roll = None

        return value

    def _set_settled_roll(self, value: int | None) -> None:
        self._settled_roll = value

    @property
    def event(self) -> Event | None:
        """
        The event currently being offered for replacement, if any.

        A replacement ability edits this object; that is the whole of what it
        is allowed to do.
        """
        return self._event

    def _set_event(self, event: Event | None) -> None:
        """
        Runtime-only: name the event open for replacement.
        """
        self._event = event

    def propose(
        self,
        event_type: EventType,
        *,
        source: Any | None = None,
        controller: int | None = None,
        targets: list[Any] | None = None,
        **payload: Any,
    ) -> Event:
        """
        Offer an event for replacement before it happens.

        The returned event carries whatever the replacements made of it, and
        may be cancelled outright. The caller reads its payload back rather
        than trusting what it asked for.
        """
        return self._propose(
            Event(
                type=event_type,
                source=source,
                controller=controller,
                targets=list(targets or ()),
                payload=dict(payload),
            )
        )

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
        return self._emit(
            Event(
                type=event_type,
                source=source,
                controller=controller,
                targets=list(targets or ()),
                payload=dict(payload),
            )
        )

    def push(self, item: StackItem) -> StackItem:
        """
        Place a pending action on the stack.
        """
        return self._push(item)

    def roll(self, sides: int = 6) -> int:
        """
        Roll a die through the engine RNG.
        """
        if sides < 1:
            raise ValueError("dice must have at least one side")

        return self._rng.randint(1, sides)

    def apply(
        self,
        effect: str,
        targets: Sequence[Any],
        **params: Any,
    ) -> Any:
        """
        Run another registered effect.
        """
        return self._effects.execute(effect, self, targets, **params)


def _no_rolls(sides: int, attack: bool) -> None:
    """
    What asking for a roll window does when nothing can open one.
    """
    raise EffectExecutionError("no Runtime is here to open a roll")
