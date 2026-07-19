# src/fsme/logging/errors.py

"""
Logging-related exceptions for Four Souls Multiverse Engine.
"""

from __future__ import annotations


class LoggingError(Exception):
    """
    Base exception for the logging subsystem.
    """


class LoggerError(LoggingError):
    """
    Raised when the logger cannot perform an operation.
    """


class HandlerError(LoggingError):
    """
    Raised when a logging handler fails.
    """


class FormatterError(LoggingError):
    """
    Raised when a log formatter fails.
    """


class ConfigurationError(LoggingError):
    """
    Raised when the logging configuration is invalid.
    """


class LogWriteError(LoggingError):
    """
    Raised when a log record cannot be written.
    """


class LogReadError(LoggingError):
    """
    Raised when a log source cannot be read.
    """
}