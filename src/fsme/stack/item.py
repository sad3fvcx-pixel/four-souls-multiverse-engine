# src/fsme/stack/item.py

"""
Stack item for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StackItemType(StrEnum):
    """
    Kinds of object that may wait on the stack.

    STACK.md allows new kinds to appear without changing stack architecture.
    """

    ACTIVATED_ABILITY = "activated_ability"
    TRIGGERED_ABILITY = "triggered_ability"
    LOOT = "loot"
    TREASURE_ACTIVATION = "treasure_activation"
    DICE = "dice"
    COMBAT = "combat"
    ENGINE_EFFECT = "engine_effect"
    CUSTOM = "custom"



class StackItemStatus(StrEnum):
    """
    Lifecycle position of a stack item.
    """

    CREATED = "created"
    PENDING = "pending"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    FIZZLED = "fizzled"



@dataclass(slots=True)
class StackItem:
    """
    Represents a single pending action placed onto the game stack.

    A stack item carries data only; it never resolves itself. The Runtime
    reads it, executes the referenced ability and removes it.

    ``ability`` and ``source`` are typed as ``Any`` on purpose: the stack sits
    below cards and abilities in the dependency order and must not import them.
    """

    kind: StackItemType

    label: str = ""

    source: Any | None = None
    ability: Any | None = None

    controller: int | None = None

    targets: list[Any] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    event: Any | None = None

    stack_id: str = ""
    order: int = 0

    status: StackItemStatus = StackItemStatus.CREATED

    def has_targets(self) -> bool:
        return bool(self.targets)

    def cancel(self) -> None:
        self.status = StackItemStatus.CANCELLED

    def fizzle(self) -> None:
        self.status = StackItemStatus.FIZZLED

    def mark_resolving(self) -> None:
        self.status = StackItemStatus.RESOLVING

    def mark_resolved(self) -> None:
        self.status = StackItemStatus.RESOLVED

    def __str__(self) -> str:
        return f"{self.kind}:{self.label or '?'}#{self.order}"
