# src/fsme/effects/builtin/__init__.py

"""
Built-in effect library.

These are the atomic operations cards combine through the Effect DSL. Adding a
card never adds code here; adding a mechanic does.
"""

from __future__ import annotations

from ..registry import EffectRegistry
from . import (
    coins,
    copying,
    curses,
    damage,
    decks,
    dice,
    loot,
    modifiers,
    replacement,
    rooms,
    treasure,
)

_MODULES = (
    coins,
    copying,
    curses,
    damage,
    decks,
    dice,
    loot,
    modifiers,
    replacement,
    rooms,
    treasure,
)


def register_builtin_effects(registry: EffectRegistry) -> EffectRegistry:
    """
    Register every built-in effect into the given registry.
    """
    for module in _MODULES:
        module.register(registry)

    return registry


__all__ = ["register_builtin_effects"]
