# src/fsme/config/utils.py

"""
Utility helpers for the configuration subsystem.
"""

from __future__ import annotations

from .config import Config


def is_config(value: object) -> bool:
    """
    Return True if the value is a Config.
    """
    return isinstance(value, Config)


def ensure_config(value: object) -> Config:
    """
    Ensure that the provided value is a Config.
    """
    if not isinstance(value, Config):
        raise TypeError(
            f"Expected Config, got {type(value).__name__}."
        )

    return value


def config_name(config: Config) -> str:
    """
    Return the configuration class name.
    """
    return config.__class__.__name__


def config_size(config: Config) -> int:
    """
    Return the number of stored configuration entries.
    """
    return len(config)