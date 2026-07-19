# src/fsme/validation/dispatcher.py

"""
Validation dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Any

from .context import ValidationContext
from .resolver import ValidationResolver
from .result import ValidationResult


class ValidationDispatcher:
    """
    Dispatches validation operations.
    """

    def __init__(
        self,
        resolver: ValidationResolver | None = None,
    ) -> None:
        self._resolver = resolver or ValidationResolver()

    @property
    def resolver(self) -> ValidationResolver:
        """
        Return the validation resolver.
        """
        return self._resolver

    def validate(
        self,
        context: ValidationContext,
        value: Any,
    ) -> ValidationResult:
        """
        Dispatch a validation operation.
        """
        return self._resolver.validate(
            context=context,
            value=value,
        )