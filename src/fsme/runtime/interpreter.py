# src/fsme/runtime/interpreter.py

"""
Effect DSL interpreter for Four Souls Multiverse Engine.

The interpreter turns a card's declarative ability into a queue of effect
operations. It decides *what will run*; it never runs anything.

Control flow is expanded as the queue is consumed rather than all at once. A
card that says "roll a die, and if you rolled a six, draw two loot" asks its
question after the die has landed — which it could not do if the branch had
been decided when the queue was built, before anything had happened. So a
branch stays in the queue as an operation and opens only when the operations
before it are done.
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

DEFAULT_TARGET_KEY = "__default_target__"
"""
Where a control operation remembers the target its contents inherit.

``for_each`` binds one object at a time and the effects inside it point at that
binding without naming it, so the binding has to travel with them.
"""


class Interpreter:
    """
    Builds and expands the effect queue of one ability.
    """

    def __init__(
        self,
        conditions: ConditionEvaluator,
        targets: TargetResolver,
        effects: EffectRegistry,
        *,
        max_ops: int = DEFAULT_MAX_OPS,
    ) -> None:
        self._conditions = conditions
        self._targets = targets
        self._effects = effects
        self._max_ops = max_ops

    @property
    def max_ops(self) -> int:
        return self._max_ops

    def build(
        self,
        nodes: Sequence[Any],
        default_target: str | None = None,
    ) -> list[EffectOp]:
        """
        Turn a list of DSL nodes into operations, one level deep.

        Control nodes stay whole. They are opened later, by :meth:`expand`,
        when the operations before them have already run.
        """
        if not isinstance(nodes, (list, tuple)):
            raise InterpreterError(f"expected a list of effects, got {nodes!r}")

        ops: list[EffectOp] = []

        for node in nodes:
            name, params, target = normalise(node)
            target = target or default_target

            if name in CONTROL_NAMES:
                control = dict(params)

                if target is not None:
                    control[DEFAULT_TARGET_KEY] = target

                ops.append(EffectOp(name=name, params=control))
            else:
                ops.append(self._operation(name, params, target))

            if len(ops) > self._max_ops:
                raise InterpreterError(
                    f"ability produced more than {self._max_ops} operations"
                )

        return ops

    def is_control(self, op: EffectOp) -> bool:
        """
        Return True if this operation is a branch, a loop or a stop.
        """
        return op.name in CONTROL_NAMES

    def expand(
        self,
        op: EffectOp,
        state: GameState,
        context: AbilityContext,
        rng: RNG,
    ) -> tuple[list[EffectOp], bool]:
        """
        Open one control operation into the operations it stands for.

        Returns the replacement operations and whether the ability should stop
        after them.
        """
        params = op.params
        default_target = params.get(DEFAULT_TARGET_KEY)

        if op.name == "stop":
            return [], True

        if op.name == "sequence":
            return self.build(
                params.get("effects", params.get("sequence", ())), default_target
            ), False

        if op.name == "if":
            return self._expand_if(params, state, context, default_target), False

        if op.name == "repeat":
            return self._expand_repeat(params, default_target), False

        if op.name == "for_each":
            return (
                self._expand_for_each(params, state, context, rng, default_target),
                False,
            )

        raise InterpreterError(f"unsupported control operation '{op.name}'")

    def _expand_if(
        self,
        params: Mapping[str, Any],
        state: GameState,
        context: AbilityContext,
        default_target: str | None,
    ) -> list[EffectOp]:
        conditions = params.get("if", params.get("conditions", ()))

        if not isinstance(conditions, (list, tuple)):
            conditions = [conditions]

        branch = (
            params.get("then", ())
            if self._conditions.evaluate_all(conditions, state, context)
            else params.get("else", ())
        )

        return self.build(branch, default_target)

    def _expand_repeat(
        self,
        params: Mapping[str, Any],
        default_target: str | None,
    ) -> list[EffectOp]:
        times = int(params.get("repeat", params.get("times", 0)))

        if times < 0:
            raise InterpreterError("repeat count must be non-negative")

        body = params.get("effects", ())
        ops: list[EffectOp] = []

        for _ in range(times):
            ops.extend(self.build(body, default_target))

            if len(ops) > self._max_ops:
                raise InterpreterError(
                    f"ability produced more than {self._max_ops} operations"
                )

        return ops

    def _expand_for_each(
        self,
        params: Mapping[str, Any],
        state: GameState,
        context: AbilityContext,
        rng: RNG,
        default_target: str | None,
    ) -> list[EffectOp]:
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

        for obj in objects:
            binding = f"__each:{len(context.targets)}"
            context.bind(binding, [obj])

            ops.extend(self.build(params.get("effects", ()), binding))

            if len(ops) > self._max_ops:
                raise InterpreterError(
                    f"ability produced more than {self._max_ops} operations"
                )

        return ops

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
