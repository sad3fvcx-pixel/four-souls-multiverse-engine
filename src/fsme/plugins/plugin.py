# src/fsme/plugins/plugin.py

"""
Plugin base class for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Plugin(ABC):
    """
    Base class for every FSME plugin.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """
        Unique plugin identifier.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Human-readable plugin name.
        """

    @property
    @abstractmethod
    def version(self) -> str:
        """
        Plugin version.
        """

    @abstractmethod
    def load(self) -> None:
        """
        Load the plugin.
        """

    @abstractmethod
    def unload(self) -> None:
        """
        Unload the plugin.
        """