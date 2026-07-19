# src/fsme/validation/handler.py

"""
Validation handler for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Any

from .context import ValidationContext
from .result import ValidationResult


class ValidationHandler:
    """
    Handles validation operations.
    """

    def validate(
        self,
        context: ValidationContext,
        value: Any,
    ) -> ValidationResult:
        """
        Validate an object using the configured validator.
        """
        if context.validator.validate(value):
            return ValidationResult.ok()

        return ValidationResult.failed(
            message="Validation failed.",
            errors=["Validation rules were not satisfied."],
        )