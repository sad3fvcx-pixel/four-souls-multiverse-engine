# src/fsme/validation/resolver.py

"""
Validation resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Any

from .context import ValidationContext
from .handler import ValidationHandler
from .result import ValidationResult


class ValidationResolver:
    """
    Resolves validation operations.
    """

    def __init__(
        self,
        handler: ValidationHandler | None = None,
    ) -> None:
        self._handler = handler or ValidationHandler()

    @property
    def handler(self) -> ValidationHandler:
        """
        Return the validation handler.
        """
        return self._handler

    def validate(
        self,
        context: ValidationContext,
        value: Any,
    ) -> ValidationResult:
        """
        Validate an object.
        """
        return self._handler.validate(
            context=context,
            value=value,
        )