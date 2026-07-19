# src/fsme/game/result.py

"""
Game operation result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GameResult:
    """
    Result of a game-level operation.
    """

    success: bool = True

    message: str = ""

    emitted_events: list[str] = field(default_factory=list)

    executed_commands: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, message: str = "") -> "GameResult":
        return cls(
            success=True,
            message=message,
        )

    @classmethod
    def failed(cls, message: str = "") -> "GameResult":
        return cls(
            success=False,
            message=message,
        )