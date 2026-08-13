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
        targets = self._resolve_targets(op, context, ability, needs=spec.needs_target)
        params = _resolve_params(op.params, ability, context)

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
        if not isinstance(value, Mapping):
            resolved[key] = value

        elif "from" in value:
            stored = ability.get(str(value["from"]))
            number = int(stored) if isinstance(stored, int) else 0

            resolved[key] = number + int(value.get("plus", 0))

        elif "count" in value:
            resolved[key] = _counted(value, ability, context)

        elif "player_of" in value:
            group = _group(value["player_of"], ability, context)

            resolved[key] = group[0].player_id if group else None

        else:
            resolved[key] = value

    return resolved


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
