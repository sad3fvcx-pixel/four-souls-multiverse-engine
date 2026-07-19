# src/fsme/logging/utils.py

"""
Utility helpers for the logging subsystem.
"""

from __future__ import annotations

from .logger import Logger


def is_logger(value: object) -> bool:
    """
    Return True if the value is a Logger.
    """
    return isinstance(value, Logger)


def ensure_logger(value: object) -> Logger:
    """
    Ensure that the provided value is a Logger.
    """
    if not isinstance(value, Logger):
        raise TypeError(
            f"Expected Logger, got {type(value).__name__}."
        )

    return value


def logger_name(logger: Logger) -> str:
    """
    Return the logger class name.
    """
    return logger.__class__.__name__


def logger_backend(logger: Logger) -> str:
    """
    Return the underlying Python logger name.
    """
    return logger.logger.name