"""
Exceptions for the runtime subsystem.
"""

from __future__ import annotations

from typing import Any

from fsme.state import DecisionKind
from fsme.util.errors import EngineError


class DecisionRequired(Exception):  # noqa: N818 - control flow, not a failure
    """
    Raised when resolution cannot continue until a player chooses.

    This is deliberately not an EngineError. Nothing has gone wrong: the
    ability is simply not answerable yet, and the executor's error handling
    must let the signal through untouched so the Runtime can suspend and
    resume instead of reporting a failure.
    """

    def __init__(
        self,
        kind: DecisionKind,
        options: list[Any],
        *,
        bind: str,
        player: int | None = None,
        minimum: int = 1,
        maximum: int = 1,
        prompt: str = "",
    ) -> None:
        super().__init__(f"{kind} required for '{bind}'")

        self.kind = kind
        self.options = options
        self.bind = bind
        self.player = player
        self.minimum = minimum
        self.maximum = maximum
        self.prompt = prompt


class RuntimeExecutionError(EngineError):
    """
    Base exception for runtime failures.
    """


class UnknownConditionError(RuntimeExecutionError):
    """
    Raised when a card references a condition the engine does not implement.
    """


class UnknownTargetError(RuntimeExecutionError):
    """
    Raised when a card references a target the engine does not implement.
    """


class InterpreterError(RuntimeExecutionError):
    """
    Raised when a DSL fragment cannot be turned into effect operations.
    """


class AbilityResolutionError(RuntimeExecutionError):
    """
    Raised when an ability cannot be resolved.
    """


class StabilityError(RuntimeExecutionError):
    """
    Raised when the game state fails to stabilise.

    ENGINE_EXECUTION_MODEL.md requires the engine to keep resolving until the
    stack, the event queue and State-Based Actions are all quiet. A rule loop
    that never settles would otherwise hang the engine, so the Runtime stops
    and reports instead.
    """
