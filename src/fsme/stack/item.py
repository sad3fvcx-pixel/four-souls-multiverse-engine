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

    cancellable: bool = True
    """
    Whether a card may take this off the stack without it resolving.

    Almost everything here is cancellable, because almost everything here is a
    thing somebody chose to do and the game lets other players answer. A few
    objects are not: they are the second half of an action already taken, split
    off so that it happens *after* whatever it is waiting for.

    Putting a played loot card into the discard pile is the one today. Playing
    a card is a single action, and the engine only splits it in two so that the
    card reaches the discard after its own ability resolves. Cancelling the
    second half alone does not undo the play — the card has already left the
    hand — it just leaves the card in no zone at all, which is how O. The Fool
    ("cancel everything that hasn't resolved") deleted itself from the game.

    This is not a way to make an effect uncancellable. Anything a player did
    and anything a card is doing stays answerable; only bookkeeping that has no
    meaning on its own is out of reach.
    """

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
