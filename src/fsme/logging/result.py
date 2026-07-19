# src/fsme/logging/result.py

"""
Logging result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LoggingResult:
    """
    Result of a logging operation.
    """

    success: bool = True

    message: str = ""

    emitted_records: int = 0

    warnings: list[str] = field(default_factory=list)

    @classmethod
    def ok(
        cls,
        message: str = "",
        *,
        emitted_records: int = 0,
    ) -> "LoggingResult":
        """
        Create a successful logging result.
        """
        return cls(
            success=True,
            message=message,
            emitted_records=emitted_records,
        )

    @classmethod
    def failed(
        cls,
        message: str = "",
    ) -> "LoggingResult":
        """
        Create a failed logging result.
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
        Add a warning to the result.
        """
        self.warnings.append(warning)