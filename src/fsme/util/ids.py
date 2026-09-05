"""
Identifier utilities for the Four Souls Multiverse Engine.

Gameplay identifiers must be deterministic: RNG.md forbids gameplay logic from
depending on operating-system randomness, and REPLAY_SYSTEM.md requires equal
inputs to produce equal outputs. Random UUIDs satisfy uniqueness but not
reproducibility, so every gameplay object takes its identifier from a counter
that lives inside GameState and is therefore saved, restored and replayed.
"""

from __future__ import annotations

from dataclasses import dataclass

# Public type alias used throughout the engine.
EngineId = str


@dataclass(slots=True)
class IdSequence:
    """
    Monotonic allocator of deterministic engine identifiers.

    Identifiers are namespaced by kind so that a single counter can serve
    every object type while remaining globally unique.
    """

    counter: int = 0

    def allocate(self, kind: str) -> EngineId:
        """
        Return the next identifier for the given kind.
        """
        self.counter += 1
        return f"{kind}:{self.counter}"

    def restore(self, counter: int) -> None:
        """
        Restore the allocator to a previously saved position.
        """
        if counter < 0:
            raise ValueError("id counter must be non-negative")

        self.counter = counter
