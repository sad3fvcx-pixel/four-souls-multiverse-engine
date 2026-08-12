# src/fsme/runtime/interpreter.py

"""
Effect DSL interpreter for Four Souls Multiverse Engine.

The interpreter turns a card's declarative ability into a flat queue of effect
operations. It decides *what will run*; it never runs anything. Control flow is
resolved here because branching questions are pure — conditions may be asked
without changing the game — so by the time the executor starts, the sequence of
operations is already fixed and can be logged, replayed and reasoned about.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fsme.effects import EffectOp, EffectRegistry
from fsme.rng.rng import RNG
from fsme.state import GameState

from .ability_context import AbilityContext
from .condition_evaluator import ConditionEvaluator
from .errors import InterpreterError
from .target_resolver import TargetResolver

CONTROL_NAMES = frozenset({"sequence", "if", "repeat", "for_each", "stop"})

_MODIFIER_KEYS = frozenset({"target", "as", "optional", "description"})

DEFAULT_MAX_OPS = 512
DEFAULT_MAX_DEPTH = 16


class Interpreter:
    """
    Builds the effect queue of one ability.
    """

    def __init__(
        self,
        conditions: ConditionEvaluator,
        targets: TargetResolver,
        effects: EffectRegistry,
        *,
        max_ops: int = DEFAULT_MAX_OPS,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> None:
        self._conditions = conditions
        self._targets = targets
        self._effects = effects
        self._max_ops = max_ops
        self._max_depth = max_depth

    def build(
        self,
        nodes: Sequence[Any],
        state: GameState,
        context: AbilityContext,
        rng: RNG,
    ) -> list[EffectOp]:
        """
        Flatten an ability's effect list into executable operations.
        """
        ops, _ = self._build(nodes, state, context, rng, depth=0, default_target=None)

        return ops

    def _build(
        self,
        nodes: Sequence[Any],
        state: GameState,
        context: AbilityContext,
        rng: RNG,
        *,
        depth: int,
        default_target: str | None,
    ) -> tuple[list[EffectOp], bool]:
        if depth > self._max_depth:
            raise InterpreterError(
                f"effect nesting exceeded {self._max_depth} levels"
            )

        if not isinstance(nodes, (list, tuple)):
            raise InterpreterError(f"expected a list of effects, got {nodes!r}")

        ops: list[EffectOp] = []

        for node in nodes:
            name, params, target = normalise(node)
            target = target or default_target

            if name == "stop":
                return ops, True

            if name in CONTROL_NAMES:
                nested, stopped = self._expand_control(
                    name,
                    params,
                    state,
                    context,
                    rng,
                    depth=depth,
                    default_target=target,
                )
                ops.extend(nested)

                if stopped:
                    return ops, True

            else:
                ops.append(self._operation(name, params, target))

            if len(ops) > self._max_ops:
                raise InterpreterError(
                    f"ability produced more than {self._max_ops} operations"
                )

        return ops, False

    def _expand_control(
        self,
        name: str,
        params: Mapping[str, Any],
        state: GameState,
        context: AbilityContext,
        rng: RNG,
        *,
        depth: int,
        default_target: str | None,
    ) -> tuple[list[EffectOp], bool]:
        if name == "sequence":
            return self._build(
                params.get("effects", params.get("sequence", ())),
                state,
                context,
                rng,
                depth=depth + 1,
                default_target=default_target,
            )

        if name == "if":
            conditions = params.get("if", params.get("conditions", ()))

            if not isinstance(conditions, (list, tuple)):
                conditions = [conditions]

            branch = (
                params.get("then", ())
                if self._conditions.evaluate_all(conditions, state, context)
                else params.get("else", ())
            )

            return self._build(
                branch,
                state,
                context,
                rng,
                depth=depth + 1,
                default_target=default_target,
            )

        if name == "repeat":
            times = int(params.get("repeat", params.get("times", 0)))

            if times < 0:
                raise InterpreterError("repeat count must be non-negative")

            ops: list[EffectOp] = []

            for _ in range(times):
                nested, stopped = self._build(
                    params.get("effects", ()),
                    state,
                    context,
                    rng,
                    depth=depth + 1,
                    default_target=default_target,
                )
                ops.extend(nested)

                if stopped:
                    return ops, True

            return ops, False

        if name == "for_each":
            return self._expand_for_each(
                params, state, context, rng, depth=depth, default_target=default_target
            )

        raise InterpreterError(f"unsupported control node '{name}'")

    def _expand_for_each(
        self,
        params: Mapping[str, Any],
        state: GameState,
        context: AbilityContext,
        rng: RNG,
        *,
        depth: int,
        default_target: str | None,
    ) -> tuple[list[EffectOp], bool]:
        """
        Expand a loop over a target group.

        Each iteration binds one object under a private name so that the nested
        effects can address it without the executor needing loop machinery.
        """
        spec = params.get("for_each", params.get("of"))

        if spec is None:
            raise InterpreterError("for_each requires a target")

        objects = self._targets.resolve(spec, state, context, rng)

        ops: list[EffectOp] = []

        for index, obj in enumerate(objects):
            binding = f"__each:{depth}:{index}"
            context.bind(binding, [obj])

            nested, stopped = self._build(
                params.get("effects", ()),
                state,
                context,
                rng,
                depth=depth + 1,
                default_target=binding,
            )
            ops.extend(nested)

            if stopped:
                return ops, True

        return ops, False

    def _operation(
        self,
        name: str,
        params: Mapping[str, Any],
        target: str | None,
    ) -> EffectOp:
        """
        Build one effect operation, expanding the shorthand parameter.
        """
        spec = self._effects.spec(name)

        resolved = dict(params)
        shorthand = resolved.pop("__value__", None)

        if shorthand is not None:
            if spec.primary is None:
                raise InterpreterError(
                    f"effect '{name}' has no shorthand parameter; "
                    f"write it as an object instead"
                )

            resolved.setdefault(spec.primary, shorthand)

        return EffectOp(name=name, params=resolved, target=target)


def normalise(node: Any) -> tuple[str, Mapping[str, Any], str | None]:
    """
    Reduce every accepted effect spelling to a name, parameters and target.

    Accepted forms::

        "stop"
        {"gain_coins": 2}
        {"gain_coins": 2, "target": "all_players"}
        {"effect": "deal_damage", "amount": 1, "target": "current_monster"}
        {"if": ["dice_equals"], "then": [...], "else": [...]}
        {"repeat": 2, "effects": [...]}
        {"for_each": "opponents", "effects": [...]}

    A scalar shorthand value is returned under ``__value__``; only the
    interpreter knows which parameter it belongs to, because only the effect
    registry does.
    """
    if isinstance(node, str):
        return node, {}, None

    if not isinstance(node, Mapping):
        raise InterpreterError(f"invalid effect node: {node!r}")

    target = node.get("target")
    target = str(target) if target is not None else None

    if "effect" in node:
        params = {
            key: value
            for key, value in node.items()
            if key not in {"effect", "target"}
        }

        return str(node["effect"]), params, target

    control = [key for key in node if key in CONTROL_NAMES]

    if control:
        if len(control) > 1:
            raise InterpreterError(
                f"effect node mixes control keywords: {sorted(control)}"
            )

        return control[0], dict(node), target

    names = [key for key in node if key not in _MODIFIER_KEYS]

    if len(names) != 1:
        raise InterpreterError(
            f"effect node must name exactly one effect: {dict(node)!r}"
        )

    name = names[0]
    value = node[name]

    if isinstance(value, Mapping):
        return str(name), dict(value), target

    return str(name), {"__value__": value}, target
