# src/fsme/resources/result.py

"""
Result types for the resource subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass

from .resource import Resource


@dataclass(slots=True, frozen=True)
class ResourceResult:
    """
    Result of a resource operation.
    """

    success: bool

    resource: Resource | None = None

    message: str = ""

    @property
    def failed(self) -> bool:
        """
        Return True if the operation failed.
        """
        return not self.success

    @classmethod
    def ok(
        cls,
        resource: Resource | None = None,
        message: str = "",
    ) -> "ResourceResult":
        """
        Create a successful result.
        """
        return cls(
            success=True,
            resource=resource,
            message=message,
        )

    @classmethod
    def error(
        cls,
        message: str,
    ) -> "ResourceResult":
        """
        Create a failed result.
        """
        return cls(
            success=False,
            resource=None,
            message=message,
        )
