# src/fsme/rules/procedures.py

"""
Stack procedures for Four Souls Multiverse Engine.

STACK.md section 5 allows the stack to hold engine effects and combat
resolution, not only card abilities. Those objects have no card behind them, so
they name a procedure instead, and the Runtime looks it up here when the item
reaches the top.

This is the extension point that lets a rule wait its turn on the stack exactly
like a card does, which is what keeps combat interruptible.
"""

from __future__ import annotations

from collections.abc import Callable

from fsme.effects import EffectContext
from fsme.stack import StackItem

from .errors import RuleRegistrationError, UnknownRuleError

StackProcedure = Callable[[StackItem, EffectContext], None]


class ProcedureRegistry:
    """
    Named procedures the stack may resolve.
    """

    def __init__(self) -> None:
        self._procedures: dict[str, StackProcedure] = {}

    def __contains__(self, name: object) -> bool:
        return name in self._procedures

    def __len__(self) -> int:
        return len(self._procedures)

    def register(self, name: str, procedure: StackProcedure) -> StackProcedure:
        """
        Register a stack procedure.
        """
        if name in self._procedures:
            raise RuleRegistrationError(f"procedure '{name}' is already registered")

        self._procedures[name] = procedure

        return procedure

    def get(self, name: str) -> StackProcedure:
        """
        Return a registered procedure.
        """
        try:
            return self._procedures[name]
        except KeyError:
            raise UnknownRuleError(f"unknown stack procedure '{name}'") from None

    def names(self) -> frozenset[str]:
        return frozenset(self._procedures)
