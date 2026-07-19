# src/fsme/config/result.py

"""
Configuration result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ConfigResult:
    """
    Result of a configuration operation.
    """

    success: bool = True

    message: str = ""

    value: Any = None

    warnings: list[str] = field(default_factory=list)

    @classmethod
    def ok(
        cls,
        value: Any = None,
        message: str = "",
    ) -> "ConfigResult":
        """
        Create a successful configuration result.
        """
        return cls(
            success=True,
            message=message,
            value=value,
        )

    @classmethod
    def failed(
        cls,
        message: str = "",
    ) -> "ConfigResult":
        """
        Create a failed configuration result.
        """
        return cls(
            success=False,
            message=message,
        )

    def add_warning(
        self,
        warning: str,
    ) -> None:
        """
        Add a warning.
        """
        self.warnings.append(warning)