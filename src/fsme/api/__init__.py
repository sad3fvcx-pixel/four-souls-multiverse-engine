# src/fsme/api/__init__.py

"""
The engine, as something outside it can talk to.

A user interface, a bot or a network layer needs three things and no more: a
picture of the position, the list of moves the engine would accept, and a way
to submit one. This package is those three things, and it is deliberately thin
— every question it answers, it answers by asking the engine.
"""

from __future__ import annotations

from .moves import legal_moves
from .session import Session, load_content
from .view import events, snapshot

__all__ = [
    "Session",
    "events",
    "legal_moves",
    "load_content",
    "snapshot",
]
