# src/fsme/plugins/constants.py

"""
Constants for the plugin subsystem.
"""

from __future__ import annotations

DEFAULT_PLUGIN_NAMESPACE = "core"

DEFAULT_PLUGIN_VERSION = "1.0.0"

DEFAULT_PLUGINS_DIRECTORY = "plugins"

PLUGIN_MANIFEST_FILENAME = "plugin.json"

PLUGIN_CONFIG_FILENAME = "config.json"

PLUGIN_ENTRYPOINT = "plugin.py"

DEFAULT_ENABLED = True

DEFAULT_AUTOLOAD = True

DEFAULT_API_VERSION = 1

MAX_PLUGIN_ID_LENGTH = 128

MAX_PLUGIN_NAME_LENGTH = 256