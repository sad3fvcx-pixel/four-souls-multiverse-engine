"""
Exceptions for the card subsystem.
"""

from __future__ import annotations

from fsme.util.errors import ContentValidationError, EngineError


class CardError(EngineError):
    """
    Base exception for all card-related errors.
    """


class InvalidCardError(ContentValidationError):
    """
    Raised when card content does not satisfy the card schema.
    """


class UnknownCardError(CardError):
    """
    Raised when a card identifier is not registered.
    """


class DuplicateCardError(CardError):
    """
    Raised when a card identifier is registered twice.

    Card identifiers are permanent and globally unique, so a collision is a
    content error rather than a reason to overwrite.
    """
