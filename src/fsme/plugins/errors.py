# src/fsme/plugins/errors.py

"""
Plugin-related exceptions for Four Souls Multiverse Engine.
"""

from __future__ import annotations


class PluginError(Exception):
    """
    Base exception for the plugin subsystem.
    """


class PluginLoadError(PluginError):
    """
    Raised when a plugin cannot be loaded.
    """


class PluginUnloadError(PluginError):
    """
    Raised when a plugin cannot be unloaded.
    """


class PluginRegistrationError(PluginError):
    """
    Raised when plugin registration fails.
    """


class PluginNotFoundError(PluginError):
    """
    Raised when a requested plugin does not exist.
    """


class DuplicatePluginError(PluginError):
    """
    Raised when attempting to register a duplicate plugin.
    """


class InvalidPluginError(PluginError):
    """
    Raised when a plugin implementation is invalid.
    """