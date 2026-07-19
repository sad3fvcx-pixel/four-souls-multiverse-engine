# src/fsme/logging/handler.py

"""
Logging handler for Four Souls Multiverse Engine.
"""

from __future__ import annotations

import logging

from .context import LoggingContext
from .result import LoggingResult


class LoggingHandler:
    """
    Handles logging operations.
    """

    def log(
        self,
        context: LoggingContext,
        level: int,
        message: str,
    ) -> LoggingResult:
        """
        Write a log message.
        """
        context.logger.logger.log(
            level,
            message,
        )

        return LoggingResult.ok(
            emitted_records=1,
        )

    def debug(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Write a DEBUG message.
        """
        return self.log(
            context=context,
            level=logging.DEBUG,
            message=message,
        )

    def info(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Write an INFO message.
        """
        return self.log(
            context=context,
            level=logging.INFO,
            message=message,
        )

    def warning(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Write a WARNING message.
        """
        return self.log(
            context=context,
            level=logging.WARNING,
            message=message,
        )

    def error(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Write an ERROR message.
        """
        return self.log(
            context=context,
            level=logging.ERROR,
            message=message,
        )

    def critical(
        self,
        context: LoggingContext,
        message: str,
    ) -> LoggingResult:
        """
        Write a CRITICAL message.
        """
        return self.log(
            context=context,
            level=logging.CRITICAL,
            message=message,
        )