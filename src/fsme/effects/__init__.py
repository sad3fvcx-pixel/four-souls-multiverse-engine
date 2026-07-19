# src/fsme/effects/__init__.py

"""
Effect subsystem exports.
"""

from .constants import (
    CARD_EFFECT_SOURCE,
    DEFAULT_EFFECT_PRIORITY,
    PLAYER_EFFECT_SOURCE,
    REPLACEMENT_EFFECT_SOURCE,
    SYSTEM_EFFECT_SOURCE,
    TRIGGER_EFFECT_SOURCE,
)
from .context import EffectContext
from .dispatcher import EffectDispatcher
from .effect import Effect
from .errors import (
    EffectError,
    EffectExecutionError,
    EffectResolutionError,
    InvalidEffectError,
    UnknownEffectError,
)
from .handler import EffectHandler
from .resolver import EffectResolver
from .result import EffectResult
from .utils import (
    effect_name,
    ensure_effect,
    ensure_effects,
    is_effect,
)

__all__ = [
    "Effect",
    "EffectContext",
    "EffectDispatcher",
    "EffectHandler",
    "EffectResolver",
    "EffectResult",
    "EffectError",
    "EffectResolutionError",
    "EffectExecutionError",
    "InvalidEffectError",
    "UnknownEffectError",
    "DEFAULT_EFFECT_PRIORITY",
    "SYSTEM_EFFECT_SOURCE",
    "PLAYER_EFFECT_SOURCE",
    "CARD_EFFECT_SOURCE",
    "TRIGGER_EFFECT_SOURCE",
    "REPLACEMENT_EFFECT_SOURCE",
    "ensure_effect",
    "ensure_effects",
    "effect_name",
    "is_effect",
]