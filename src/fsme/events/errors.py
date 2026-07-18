# src/fsme/events/errors.py

"""
Exceptions for the event subsystem.
"""

from __future__ import annotations

from fsme.util.errors import EventError


class EventDispatchError(EventError):
    """
    Raised when an event cannot be dispatched.
    """


class EventHandlerError(EventError):
    """
    Raised when an event handler fails.
    """


class EventRegistrationError(EventError):
    """
    Raised when an invalid event registration is attempted.
    """


class EventQueueError(EventError):
    """
    Raised when an invalid queue operation is performed.
    """