# src/fsme/stack/result.py

"""
Stack resolution result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StackResult:
    """
    Result of resolving a stack item.
    """

    success: bool = True

    resolved: bool = True

    cancelled: bool = False

    message: str = ""

    emitted_events: list[str] = field(default_factory=list)

    generated_items: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, message: str = "") -> "StackResult":
        return cls(
            success=True,
            resolved=True,
            cancelled=False,
            message=message,
        )

    @classmethod
    def cancelled_result(cls, message: str = "") -> "StackResult":
        return cls(
            success=True,
            resolved=False,
            cancelled=True,
            message=message,
        )

    @classmethod
    def failed(cls, message: str = "") -> "StackResult":
        return cls(
            success=False,
            resolved=False,
            cancelled=False,
            message=message,
        )