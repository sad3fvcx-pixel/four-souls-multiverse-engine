"""
Identifier utilities for the Four Souls Multiverse Engine.
"""

from __future__ import annotations

from uuid import UUID, uuid4

# Public type alias used throughout the engine.
EngineId = UUID


def new_id() -> EngineId:
    """
    Generate a new unique engine identifier.
    """
    return uuid4()
