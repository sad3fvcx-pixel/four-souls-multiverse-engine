# src/fsme/validation/result.py

"""
Validation result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ValidationResult:
    """
    Result of a validation operation.
    """

    success: bool = True

    message: str = ""

    errors: list[str] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    @classmethod
    def ok(
        cls,
        message: str = "",
    ) -> "ValidationResult":
        """
        Create a successful validation result.
        """
        return cls(
            success=True,
            message=message,
        )

    @classmethod
    def failed(
        cls,
        message: str = "",
        *,
        errors: list[str] | None = None,
    ) -> "ValidationResult":
        """
        Create a failed validation result.
        """
        return cls(
            success=False,
            message=message,
            errors=errors or [],
        )

    def add_error(
        self,
        error: str,
    ) -> None:
        """
        Add a validation error.
        """
        self.errors.append(error)
        self.success = False

    def add_warning(
        self,
        warning: str,
    ) -> None:
        """
        Add a validation warning.
        """
        self.warnings.append(warning)