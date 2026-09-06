# src/fsme/effects/__init__.py

"""
Effect subsystem exports.

Effects are the only source of GameState changes. They are executed by the
Runtime, never by cards and never by themselves.
"""

from .context import EffectContext
from .effect import EffectOp
from .errors import (
    EffectError,
    EffectExecutionError,
    EffectRegistrationError,
    EffectResolutionError,
    InvalidEffectError,
    UnknownEffectError,
)
from .registry import EffectHandler, EffectRegistry, EffectSpec, builtin_registry
from .result import EffectResult

__all__ = [
    "EffectContext",
    "EffectHandler",
    "EffectOp",
    "EffectRegistry",
    "EffectResult",
    "EffectSpec",
    "builtin_registry",
    "EffectError",
    "EffectExecutionError",
    "EffectRegistrationError",
    "EffectResolutionError",
    "InvalidEffectError",
    "UnknownEffectError",
]
