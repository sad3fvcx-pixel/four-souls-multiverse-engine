# src/fsme/logging/__init__.py

"""
Logging subsystem exports.
"""

from .constants import (
    DEFAULT_BACKUP_COUNT,
    DEFAULT_DATE_FORMAT,
    DEFAULT_ENCODING,
    DEFAULT_LOG_DIRECTORY,
    DEFAULT_LOG_FILENAME,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_LOGGER_NAME,
    DEFAULT_MAX_LOG_SIZE,
    DEFAULT_PROPAGATE,
)
from .context import LoggingContext
from .dispatcher import LoggingDispatcher
from .errors import (
    ConfigurationError,
    FormatterError,
    HandlerError,
    LoggerError,
    LoggingError,
    LogReadError,
    LogWriteError,
)
from .handler import LoggingHandler
from .logger import Logger
from .resolver import LoggingResolver
from .result import LoggingResult
from .utils import (
    ensure_logger,
    is_logger,
    logger_backend,
    logger_name,
)

__all__ = [
    "Logger",
    "LoggingContext",
    "LoggingHandler",
    "LoggingResolver",
    "LoggingDispatcher",
    "LoggingResult",
    "LoggingError",
    "LoggerError",
    "HandlerError",
    "FormatterError",
    "ConfigurationError",
    "LogWriteError",
    "LogReadError",
    "DEFAULT_LOGGER_NAME",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_LOG_FORMAT",
    "DEFAULT_DATE_FORMAT",
    "DEFAULT_LOG_DIRECTORY",
    "DEFAULT_LOG_FILENAME",
    "DEFAULT_MAX_LOG_SIZE",
    "DEFAULT_BACKUP_COUNT",
    "DEFAULT_ENCODING",
    "DEFAULT_PROPAGATE",
    "is_logger",
    "ensure_logger",
    "logger_name",
    "logger_backend",
]