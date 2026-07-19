# src/fsme/cards/errors.py

"""
Exceptions for the card subsystem.
"""

from __future__ import annotations

from fsme.util.errors import EngineError


class CardError(EngineError):
    """
    Base exception for all card-related errors.
    """


class CardResolutionError(CardError):
    """
    Raised when a card operation cannot be resolved.
    """


class CardExecutionError(CardError):
    """
    Raised when a card handler fails during execution.
    """


class InvalidCardError(CardError):
    """
    Raised when an invalid card object is encountered.
    """


class UnknownCardError(CardError):
    """
    Raised when an unknown card type or operation is encountered.
    """