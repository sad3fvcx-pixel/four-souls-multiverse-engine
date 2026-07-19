# src/fsme/serialization/result.py

"""
Serialization result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SerializationResult:
    """
    Result of a serialization or deserialization operation.
    """

    success: bool = True

    message: str = ""

    data: object | None = None

    warnings: list[str] = field(default_factory=list)

    @classmethod
    def ok(
        cls,
        data: object | None = None,
        message: str = "",
    ) -> "SerializationResult":
        """
        Create a successful result.
        """
        return cls(
            success=True,
            message=message,
            data=data,
        )

    @classmethod
    def failed(
        cls,
        message: str,
    ) -> "SerializationResult":
        """
        Create a failed result.
        """
        return cls(
            success=False,
            message=message,
        )