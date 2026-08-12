"""
Exceptions for the runtime subsystem.
"""

from __future__ import annotations

from fsme.util.errors import EngineError


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
