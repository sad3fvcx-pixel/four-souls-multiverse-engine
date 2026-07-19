# src/fsme/effects/effect.py

"""
Base effect definitions for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class Effect:
    """
    Represents a single executable game effect.
    """

    name: str

    payload: dict[str, Any] = field(default_factory=dict)

    effect_id: str = field(default_factory=lambda: uuid4().hex)

    def __str__(self) -> str:
        return self.name