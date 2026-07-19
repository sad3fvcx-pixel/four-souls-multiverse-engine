# src/fsme/config/errors.py

"""
Configuration-related exceptions for Four Souls Multiverse Engine.
"""

from __future__ import annotations


class ConfigError(Exception):
    """
    Base exception for the configuration subsystem.
    """


class ConfigLoadError(ConfigError):
    """
    Raised when a configuration cannot be loaded.
    """


class ConfigSaveError(ConfigError):
    """
    Raised when a configuration cannot be saved.
    """


class ConfigKeyError(ConfigError):
    """
    Raised when a configuration key is invalid.
    """


class ConfigValueError(ConfigError):
    """
    Raised when a configuration value is invalid.
    """


class ConfigNotFoundError(ConfigError):
    """
    Raised when a requested configuration entry does not exist.
    """


class ConfigValidationError(ConfigError):
    """
    Raised when configuration validation fails.
    """