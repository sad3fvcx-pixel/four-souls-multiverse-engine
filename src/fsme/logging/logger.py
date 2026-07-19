# src/fsme/logging/logger.py

"""
Logging utilities for Four Souls Multiverse Engine.
"""

from __future__ import annotations

import logging
from pathlib import Path


class Logger:
    """
    Wrapper around the standard Python logger.
    """

    def __init__(
        self,
        name: str = "fsme",
    ) -> None:
        self._logger = logging.getLogger(name)

    @property
    def logger(self) -> logging.Logger:
        """
        Return the underlying logger.
        """
        return self._logger

    def add_file_handler(
        self,
        path: str | Path,
        *,
        level: int = logging.INFO,
    ) -> None:
        """
        Add a file handler.
        """
        handler = logging.FileHandler(
            Path(path),
            encoding="utf-8",
        )
        handler.setLevel(level)
        self._logger.addHandler(handler)

    def add_stream_handler(
        self,
        *,
        level: int = logging.INFO,
    ) -> None:
        """
        Add a stream handler.
        """
        handler = logging.StreamHandler()
        handler.setLevel(level)
        self._logger.addHandler(handler)

    def set_level(
        self,
        level: int,
    ) -> None:
        """
        Set the logger level.
        """
        self._logger.setLevel(level)

    def debug(self, message: str) -> None:
        self._logger.debug(message)

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.error(message)

    def critical(self, message: str) -> None:
        self._logger.critical(message)