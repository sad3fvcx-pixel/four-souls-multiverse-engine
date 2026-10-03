"""
Content-related exceptions for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from fsme.util.errors import ContentLoadError, ContentValidationError, EngineError


class ContentError(EngineError):
    """
    Base exception for the content subsystem.
    """


class InvalidContentError(ContentValidationError):
    """
    Raised when content fails validation.

    Carries every problem found in one pass, because someone fixing an
    expansion should see the whole list rather than one line at a time.
    """


class DuplicateContentError(ContentError):
    """
    Raised when two expansions claim the same identifier.
    """


class ContentNotFoundError(ContentError):
    """
    Raised when requested content does not exist.
    """


class MissingDependencyError(ContentError):
    """
    Raised when an expansion requires a set that was not loaded.
    """


__all__ = [
    "ContentError",
    "ContentLoadError",
    "ContentNotFoundError",
    "DuplicateContentError",
    "InvalidContentError",
    "MissingDependencyError",
]
