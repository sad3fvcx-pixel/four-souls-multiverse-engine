# src/fsme/content/result.py

"""
Content loading result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ContentResult:
    """
    Result of a content loading operation.
    """

    success: bool = True

    message: str = ""

    loaded_cards: list[str] = field(default_factory=list)

    loaded_effects: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, message: str = "") -> "ContentResult":
        return cls(
            success=True,
            message=message,
        )

    @classmethod
    def failed(cls, message: str = "") -> "ContentResult":
        return cls(
            success=False,
            message=message,
        )