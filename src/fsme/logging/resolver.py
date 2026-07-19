# src/fsme/logging/resolver.py

"""
Logging resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import LoggingContext
from .handler import LoggingHandler
from .result import LoggingResult


class LoggingResolver:
    """
    Resolves logging operations.
    """

    def __init__(
        self,
        handler: LoggingHandler | None = None,
    ) -> None:
        self._handler = handler or LoggingHandler()

    @property
    def handler(self) -> LoggingHandler:
        """
        Return the logging handler.
        """
        return self._handler

    def log(
        self,
        context: LoggingContext,
        level: int,
        message: str,
    ) -> LoggingResult:
        """
        Resolve a logging operation.
        """
        return self._handler.log(
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
        Resolve a DEBUG logging operation.
        """
        return self._handler.debug(
            context=context,
            message=message,
        )

    def info(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Resolve an INFO logging operation.
        """
        return self._handler.info(
            context=context,
            message=message,
        )

    def warning(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Resolve a WARNING logging operation.
        """
        return self._handler.warning(
            context=context,
            message=message,
        )

    def error(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Resolve an ERROR logging operation.
        """
        return self._handler.error(
            context=context,
            message=message,
        )

    def critical(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Resolve a CRITICAL logging operation.
        """
        return self._handler.critical(
            context=context,
            message=message,
        )