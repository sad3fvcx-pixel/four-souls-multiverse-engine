# src/fsme/runtime/effect_executor.py

"""
Effect execution for Four Souls Multiverse Engine.

This is where GameState actually changes. Everything above it decides what
should happen; this class performs it, one operation at a time, in the order
the interpreter fixed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from fsme.effects import EffectOp, EffectRegistry, EffectResult
from fsme.util.errors import EngineError

from .ability_context import AbilityContext
from .errors import AbilityResolutionError, StabilityError
from .execution_context import ExecutionContext
from .target_resolver import TargetResolver


class EffectExecutor:
    """
    Runs effect operations against a game.
    """

    def __init__(self, effects: EffectRegistry, targets: TargetResolver) -> None:
        self._effects = effects
        self._targets = targets

    def execute(
        self,
        op: EffectOp,
        context: ExecutionContext,
        ability: AbilityContext,
    ) -> EffectResult:
        """
        Execute one operation and record the result on the ability context.
        """
        spec = self._effects.spec(op.name)

        if op.asks:
            # Questions this effect asks for itself, in the order written: a
            # card that swaps two cards must ask about the first before it can
            # sensibly ask about the second.
            self._targets.resolve_all(op.asks, context.state, ability, context.rng)

        targets = self._resolve_targets(op, context, ability, needs=spec.needs_target)
        params = _resolve_params(op.params, ability, context, literal=spec.literal)

        try:
            value = spec.handler(context, targets, **params)
        except StabilityError:
            # The engine is stopping itself, not failing an effect. Wrapping it
            # would bury the reason under one message per nesting level.
            raise
        except EngineError as error:
            ability.record(EffectResult.failed(op.name, str(error)))

            raise AbilityResolutionError(
                f"effect '{op.name}' failed: {error}"
            ) from error

        result = EffectResult.ok(
            effect=op.name,
            value=value,
            targets=targets,
        )

        if spec.stores is not None:
            ability.store(spec.stores, value)

        if op.store:
            ability.store(op.store, value)

        return ability.record(result)

    def _resolve_targets(
        self,
        op: EffectOp,
        context: ExecutionContext,
        ability: AbilityContext,
        *,
        needs: bool,
    ) -> list[Any]:
        """
        Work out what an operation applies to.

        An explicit target wins. Otherwise an effect that needs one falls back
        to the ability's controller, which is what a card means when it says
        "gain 3 cents" without naming anybody.
        """
        if op.target is not None:
            return self._targets.resolve(
                op.target, context.state, ability, context.rng
            )

        if not needs:
            return []

        if ability.controller is None:
            return []

        state = context.state

        if not 0 <= ability.controller < len(state.players):
            return []

        return [state.player(ability.controller)]


def _resolve_params(
    params: Mapping[str, Any],
    ability: AbilityContext,
    context: ExecutionContext,
    literal: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """
    Fill in the values an ability only learns while it is running.

    A card that says "deal damage equal to the result" cannot state a number
    when it is written, so it names one instead::

        {"effect": "deal_damage", "amount": {"from": "dice"}, "target": "victim"}

    ``from`` reads what an earlier effect stored under that name — the die roll,
    in this case — and ``plus`` shifts it. ``count`` counts what a player has::

        {"count": "loot", "of": "rival", "minus": "controller"}

    which is how "loot until you have as many as they do" states its number.
    A name nothing has stored yet reads as zero, which is what "equal to a roll
    that did not happen" is worth.
    """
    resolved: dict[str, Any] = {}

    for key, value in params.items():
        if key in literal or not isinstance(value, Mapping):
            resolved[key] = value

        elif "from" in value:
            stored = ability.get(str(value["from"]))
            number = int(stored) if isinstance(stored, int) else 0

            resolved[key] = _shift(number, value)

        elif "count" in value:
            resolved[key] = _counted(value, ability, context)

        elif "from_event" in value:
            carried = (
                ability.event.get(str(value["from_event"]))
                if ability.event is not None
                else None
            )
            number = int(carried) if isinstance(carried, int) else 0

            resolved[key] = _shift(number, value)

        elif "last_result" in value:
            done = ability.last_value
            number = int(done) if isinstance(done, int) else 0

            resolved[key] = _shift(number, value)

        elif "player_of" in value:
            group = _group(value["player_of"], ability, context)

            resolved[key] = group[0].player_id if group else None

        else:
            resolved[key] = value

    return resolved


def _shift(number: int, spec: Mapping[str, Any]) -> int:
    """
    Scale and shift a number a card read from somewhere.

    ``times`` is what lets a card give back what it took: removing counters
    equal to the damage taken is the same number, negated.
    """
    return number * int(spec.get("times", 1)) + int(spec.get("plus", 0))


_COUNTS: dict[str, Callable[[Any], int]] = {
    "loot": lambda player: int(player.hand_size),
    "coins": lambda player: int(player.pennies),
    "souls": lambda player: int(player.soul_count),
    "treasures": lambda player: int(player.treasure_count),
    "hp": lambda player: int(player.hp),
}


def _counted(
    spec: Mapping[str, Any],
    ability: AbilityContext,
    context: ExecutionContext,
) -> int:
    """
    Count something across a group of players, optionally less another group.
    """
    what = str(spec["count"])

    try:
        counter = _COUNTS[what]
    except KeyError:
        raise AbilityResolutionError(
            f"cannot count '{what}'; countable things are "
            f"{', '.join(sorted(_COUNTS))}"
        ) from None

    total = sum(counter(player) for player in _group(spec.get("of"), ability, context))

    if "minus" in spec:
        total -= sum(
            counter(player)
            for player in _group(spec["minus"], ability, context)
        )

    return max(int(spec.get("floor", 0)), total)


WORKING_OUT = {
    "from": "the name an earlier step stored the number under",
    "from_event": "a number the event being answered carries",
    "last_result": "what the step before this one came to",
    "count": "something to count across a group of players",
    "player_of": "a group whose player is wanted",
    "of": "whose things to count",
    "minus": "a group to count and take away",
    "floor": "the smallest the count may come to",
    "times": "what to multiply the number by",
    "plus": "what to add to it afterwards",
}
"""
Every key this module reads when a card gives a way of working a number out
instead of the number.

One entry per ``spec.get`` and per branch of ``_resolve_params`` above, which
is what keeps it the same fact rather than a second copy of it. The first five
are the heads — a specification names exactly one — and the rest shape whatever
the head produced.

Named here so that a layer describing what a card may write can say "a whole
number, or one of these", which is what the cards actually say and what nothing
outside this file could otherwise know.
"""

COUNTABLE = tuple(sorted(_COUNTS))
"""
The things ``count`` can count, off the table that counts them.
"""


def _group(
    name: Any,
    ability: AbilityContext,
    context: ExecutionContext,
) -> list[Any]:
    """
    Return the players a counting specification is talking about.
    """
    if name is None:
        return []

    if str(name) in ("controller", "self"):
        controller = ability.controller

        if controller is None or not 0 <= controller < len(context.state.players):
            return []

        return [context.state.player(controller)]

    return [
        target
        for target in ability.targets.get(str(name), ())
        if hasattr(target, "player_id")
    ]
