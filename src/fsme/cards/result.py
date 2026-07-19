# src/fsme/cards/result.py

"""
Card operation result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CardResult:
    """
    Result of a card-related operation.
    """

    success: bool = True

    message: str = ""

    emitted_events: list[str] = field(default_factory=list)

    generated_effects: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, message: str = "") -> "CardResult":
        return cls(
            success=True,
            message=message,
        )

    @classmethod
    def failed(cls, message: str = "") -> "CardResult":
        return cls(
            success=False,
            message=message,
        )