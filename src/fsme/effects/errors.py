# src/fsme/effects/errors.py

"""
Exceptions for the effect subsystem.
"""

from __future__ import annotations

from fsme.util.errors import EngineError


class EffectError(EngineError):
    """
    Base exception for all effect-related errors.
    """


class EffectResolutionError(EffectError):
    """
    Raised when an effect cannot be resolved.
    """


class EffectExecutionError(EffectError):
    """
    Raised when an effect handler fails during execution.
    """


class InvalidEffectError(EffectError):
    """
    Raised when an invalid effect object is encountered.
    """


class UnknownEffectError(EffectError):
    """
    Raised when no handler exists for an effect.
    """