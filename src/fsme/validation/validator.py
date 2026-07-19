# src/fsme/validation/validator.py

"""
Validation utilities for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ValidationRule = Callable[[Any], bool]


class Validator:
    """
    Generic object validator.
    """

    def __init__(self) -> None:
        self._rules: list[ValidationRule] = []

    def add_rule(
        self,
        rule: ValidationRule,
    ) -> None:
        """
        Register a validation rule.
        """
        self._rules.append(rule)

    def remove_rule(
        self,
        rule: ValidationRule,
    ) -> None:
        """
        Remove a validation rule.
        """
        if rule in self._rules:
            self._rules.remove(rule)

    def clear(self) -> None:
        """
        Remove all validation rules.
        """
        self._rules.clear()

    def validate(
        self,
        value: Any,
    ) -> bool:
        """
        Validate a value against every registered rule.
        """
        return all(rule(value) for rule in self._rules)

    @property
    def rules(self) -> tuple[ValidationRule, ...]:
        """
        Return registered validation rules.
        """
        return tuple(self._rules)