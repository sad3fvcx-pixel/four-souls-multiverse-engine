# src/fsme/content/errors.py

"""
Content-related exceptions for Four Souls Multiverse Engine.
"""

from __future__ import annotations


class ContentError(Exception):
    """
    Base exception for the content subsystem.
    """


class ContentLoadError(ContentError):
    """
    Raised when content cannot be loaded.
    """


class ContentUnloadError(ContentError):
    """
    Raised when content cannot be unloaded.
    """


class DuplicateContentError(ContentError):
    """
    Raised when attempting to register duplicate content.
    """


class ContentNotFoundError(ContentError):
    """
    Raised when requested content does not exist.
    """


class InvalidContentError(ContentError):
    """
    Raised when content validation fails.
    """