# src/fsme/effects/context.py

"""
Effect execution context for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .effect import Effect


@dataclass(slots=True)
class EffectContext:
    """
    Context shared during effect execution.
    """

    effect: Effect

    values: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def has(self, key: str) -> bool:
        return key in self.values

    def remove(self, key: str) -> None:
        self.values.pop(key, None)

    def clear(self) -> None:
        self.values.clear()