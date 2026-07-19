# src/fsme/logging/dispatcher.py

"""
Logging dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import LoggingContext
from .resolver import LoggingResolver
from .result import LoggingResult


class LoggingDispatcher:
    """
    Dispatches logging operations.
    """

    def __init__(
        self,
        resolver: LoggingResolver | None = None,
    ) -> None:
        self._resolver = resolver or LoggingResolver()

    @property
    def resolver(self) -> LoggingResolver:
        """
        Return the logging resolver.
        """
        return self._resolver

    def log(
        self,
        context: LoggingContext,
        level: int,
        message: str,
    ) -> LoggingResult:
        """
        Dispatch a logging operation.
        """
        return self._resolver.log(
            context=context,
            level=level,
            message=message,
        )

    def debug(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Dispatch a DEBUG logging operation.
        """
        return self._resolver.debug(
            context=context,
            message=message,
        )

    def info(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Dispatch an INFO logging operation.
        """
        return self._resolver.info(
            context=context,
            message=message,
        )

    def warning(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Dispatch a WARNING logging operation.
        """
        return self._resolver.warning(
            context=context,
            message=message,
        )

    def error(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Dispatch an ERROR logging operation.
        """
        return self._resolver.error(
            context=context,
            message=message,
        )

    def critical(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Dispatch a CRITICAL logging operation.
        """
        return self._resolver.critical(
            context=context,
            message=message,
        )