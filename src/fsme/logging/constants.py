# src/fsme/logging/constants.py

"""
Constants for the logging subsystem.
"""

from __future__ import annotations

import logging

DEFAULT_LOGGER_NAME = "fsme"

DEFAULT_LOG_LEVEL = logging.INFO

DEFAULT_LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_LOG_DIRECTORY = "logs"

DEFAULT_LOG_FILENAME = "fsme.log"

DEFAULT_MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MiB

DEFAULT_BACKUP_COUNT = 5

DEFAULT_ENCODING = "utf-8"

DEFAULT_PROPAGATE = False