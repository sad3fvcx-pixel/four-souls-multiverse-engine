# src/fsme/config/__init__.py

"""
Configuration subsystem exports.
"""

from .config import Config
from .constants import (
    DEFAULT_AUTO_LOAD,
    DEFAULT_AUTO_SAVE,
    DEFAULT_CONFIG_DIRECTORY,
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_ENCODING,
    DEFAULT_FORMAT,
    DEFAULT_NAMESPACE,
    DEFAULT_PROFILE,
    DEFAULT_SCHEMA_VERSION,
    MAX_KEY_LENGTH,
    MAX_VALUE_LENGTH,
)
from .context import ConfigContext
from .dispatcher import ConfigDispatcher
from .errors import (
    ConfigError,
    ConfigKeyError,
    ConfigLoadError,
    ConfigNotFoundError,
    ConfigSaveError,
    ConfigValidationError,
    ConfigValueError,
)
from .handler import ConfigHandler
from .resolver import ConfigResolver
from .result import ConfigResult
from .utils import (
    config_name,
    config_size,
    ensure_config,
    is_config,
)

__all__ = [
    "Config",
    "ConfigContext",
    "ConfigHandler",
    "ConfigResolver",
    "ConfigDispatcher",
    "ConfigResult",
    "ConfigError",
    "ConfigLoadError",
    "ConfigSaveError",
    "ConfigKeyError",
    "ConfigValueError",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "DEFAULT_CONFIG_DIRECTORY",
    "DEFAULT_CONFIG_FILENAME",
    "DEFAULT_PROFILE",
    "DEFAULT_ENCODING",
    "DEFAULT_FORMAT",
    "DEFAULT_AUTO_SAVE",
    "DEFAULT_AUTO_LOAD",
    "DEFAULT_SCHEMA_VERSION",
    "DEFAULT_NAMESPACE",
    "MAX_KEY_LENGTH",
    "MAX_VALUE_LENGTH",
    "is_config",
    "ensure_config",
    "config_name",
    "config_size",
]