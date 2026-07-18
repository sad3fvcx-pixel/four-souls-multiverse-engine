"""
Four Souls Multiverse Engine

Common exception hierarchy.
Every engine-specific exception should inherit from EngineError.
"""

from __future__ import annotations


class EngineError(Exception):
    """Base class for all engine exceptions."""


class ValidationError(EngineError):
    """Raised when validation fails."""


class CommandValidationError(ValidationError):
    """Raised when a command is invalid."""


class ContentValidationError(ValidationError):
    """Raised when game content is invalid."""


class SerializationError(EngineError):
    """Raised when serialization or deserialization fails."""


class ReplayError(EngineError):
    """Raised when replay execution fails."""


class InvariantViolation(EngineError):
    """
    Raised when an engine invariant is violated.

    This exception usually indicates a bug inside the engine
    rather than an invalid user action.
    """


class UnsupportedVersionError(EngineError):
    """Raised when a file or schema version is unsupported."""


class ContentLoadError(EngineError):
    """Raised when content cannot be loaded."""


class StackError(EngineError):
    """Raised when stack processing fails."""


class EventError(EngineError):
    """Raised when event processing fails."""


class RNGError(EngineError):
    """Raised when deterministic RNG encounters an invalid state."""
