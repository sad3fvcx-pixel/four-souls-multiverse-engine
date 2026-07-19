# src/fsme/effects/utils.py

"""
Utility functions for the effect subsystem.
"""

from __future__ import annotations

from collections.abc import Iterable

from .effect import Effect


def ensure_effect(obj: object) -> Effect:
    """
    Ensure that an object is an Effect.
    """
    if not isinstance(obj, Effect):
        raise TypeError(
            f"Expected Effect, got {type(obj).__name__}."
        )

    return obj


def ensure_effects(
    effects: Iterable[object],
) -> list[Effect]:
    """
    Validate an iterable of effects.
    """
    return [ensure_effect(effect) for effect in effects]


def effect_name(effect: Effect) -> str:
    """
    Return a human-readable effect name.
    """
    return effect.name


def is_effect(obj: object) -> bool:
    """
    Check whether an object is an Effect.
    """
    return isinstance(obj, Effect)