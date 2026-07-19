# src/fsme/stack/item.py

"""
Stack item for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class StackItem:
    """
    Represents a single object placed onto the game stack.
    """

    source_id: str
    effect: str

    payload: dict[str, Any] = field(default_factory=dict)

    owner_id: str | None = None
    target_id: str | None = None

    stack_id: str = field(default_factory=lambda: uuid4().hex)

    def has_target(self) -> bool:
        return self.target_id is not None

    def has_owner(self) -> bool:
        return self.owner_id is not None