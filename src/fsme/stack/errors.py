# src/fsme/stack/errors.py

"""
Exceptions for the stack subsystem.
"""

from __future__ import annotations

from fsme.util.errors import EngineError


class StackError(EngineError):
    """
    Base exception for all stack-related errors.
    """


class StackEmptyError(StackError):
    """
    Raised when an operation requires a non-empty stack.
    """


class StackResolutionError(StackError):
    """
    Raised when a stack item cannot be resolved.
    """


class InvalidStackItemError(StackError):
    """
    Raised when an invalid object is used as a stack item.
    """


class StackOverflowError(StackError):
    """
    Raised when the stack exceeds the configured limit.
    """