# src/fsme/plugins/__init__.py

"""
Plugin subsystem exports.
"""

from .constants import (
    DEFAULT_API_VERSION,
    DEFAULT_AUTOLOAD,
    DEFAULT_ENABLED,
    DEFAULT_PLUGIN_NAMESPACE,
    DEFAULT_PLUGIN_VERSION,
    DEFAULT_PLUGINS_DIRECTORY,
    MAX_PLUGIN_ID_LENGTH,
    MAX_PLUGIN_NAME_LENGTH,
    PLUGIN_CONFIG_FILENAME,
    PLUGIN_ENTRYPOINT,
    PLUGIN_MANIFEST_FILENAME,
)
from .context import PluginContext
from .dispatcher import PluginDispatcher
from .errors import (
    DuplicatePluginError,
    InvalidPluginError,
    PluginError,
    PluginLoadError,
    PluginNotFoundError,
    PluginRegistrationError,
    PluginUnloadError,
)
from .handler import PluginHandler
from .manager import PluginManager
from .plugin import Plugin
from .resolver import PluginResolver
from .result import PluginResult
from .utils import (
    ensure_manager,
    ensure_plugin,
    is_manager,
    is_plugin,
    plugin_count,
    plugin_name,
)

__all__ = [
    "Plugin",
    "PluginManager",
    "PluginContext",
    "PluginHandler",
    "PluginResolver",
    "PluginDispatcher",
    "PluginResult",
    "PluginError",
    "PluginLoadError",
    "PluginUnloadError",
    "PluginRegistrationError",
    "PluginNotFoundError",
    "DuplicatePluginError",
    "InvalidPluginError",
    "DEFAULT_PLUGIN_NAMESPACE",
    "DEFAULT_PLUGIN_VERSION",
    "DEFAULT_PLUGINS_DIRECTORY",
    "PLUGIN_MANIFEST_FILENAME",
    "PLUGIN_CONFIG_FILENAME",
    "PLUGIN_ENTRYPOINT",
    "DEFAULT_ENABLED",
    "DEFAULT_AUTOLOAD",
    "DEFAULT_API_VERSION",
    "MAX_PLUGIN_ID_LENGTH",
    "MAX_PLUGIN_NAME_LENGTH",
    "is_plugin",
    "ensure_plugin",
    "is_manager",
    "ensure_manager",
    "plugin_name",
    "plugin_count",
]