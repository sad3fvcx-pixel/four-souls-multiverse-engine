# src/fsme/runtime/effect_executor.py

"""
Effect execution for Four Souls Multiverse Engine.

This is where GameState actually changes. Everything above it decides what
should happen; this class performs it, one operation at a time, in the order
the interpreter fixed.
"""

from __future__ import annotations

from collections.abc import Mapping
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
        params = _resolve_params(op.params, ability)

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
    params: Mapping[str, Any], ability: AbilityContext
) -> dict[str, Any]:
    """
    Fill in the values an ability only learns while it is running.

    A card that says "deal damage equal to the result" cannot state a number
    when it is written, so it names one instead::

        {"effect": "deal_damage", "amount": {"from": "dice"}, "target": "victim"}

    ``from`` reads what an earlier effect stored under that name — the die roll,
    in this case — and ``plus`` shifts it. A name nothing has stored yet reads
    as zero, which is what "equal to a roll that did not happen" is worth.
    """
    resolved: dict[str, Any] = {}

    for key, value in params.items():
        if isinstance(value, Mapping) and "from" in value:
            stored = ability.get(str(value["from"]))
            number = int(stored) if isinstance(stored, int) else 0

            resolved[key] = number + int(value.get("plus", 0))
        else:
            resolved[key] = value

    return resolved
