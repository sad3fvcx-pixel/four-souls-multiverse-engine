# src/fsme/config/config.py

"""
Configuration object for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Any


class Config:
    """
    Stores engine configuration values.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Return a configuration value.
        """
        return self._values.get(key, default)

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Store a configuration value.
        """
        self._values[key] = value

    def has(
        self,
        key: str,
    ) -> bool:
        """
        Return True if the key exists.
        """
        return key in self._values

    def remove(
        self,
        key: str,
    ) -> None:
        """
        Remove a configuration value.
        """
        self._values.pop(key, None)

    def clear(self) -> None:
        """
        Remove every configuration value.
        """
        self._values.clear()

    def as_dict(self) -> dict[str, Any]:
        """
        Return a shallow copy of the configuration.
        """
        return dict(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(
        self,
        key: object,
    ) -> bool:
        return key in self._values