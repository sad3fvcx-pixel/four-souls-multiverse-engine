# src/fsme/commands/command.py

"""
Command objects for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import CommandType


@dataclass(slots=True)
class Command:
    """
    A request from a player, an AI, the network or a replay.

    Commands carry intent only. They never modify GameState, and every one of
    them passes through validation before anything happens.

    Like events, commands are ordered by a monotonic ``sequence`` rather than a
    timestamp: a replay must reproduce the order exactly, and wall-clock values
    would differ between runs.
    """

    type: CommandType

    player: int

    payload: dict[str, Any] = field(default_factory=dict)

    command_id: str = ""
    sequence: int = 0

    def get(self, key: str, default: Any = None) -> Any:
        """
        Read a payload value.
        """
        return self.payload.get(key, default)

    def require(self, key: str) -> Any:
        """
        Read a payload value that must be present.
        """
        if key not in self.payload:
            raise KeyError(f"command '{self.type}' requires payload key '{key}'")

        return self.payload[key]

    def has(self, key: str) -> bool:
        return key in self.payload

    def __str__(self) -> str:
        return f"{self.type}(player={self.player})#{self.sequence}"
