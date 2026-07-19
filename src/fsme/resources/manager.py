# src/fsme/resources/manager.py

"""
Resource manager for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from pathlib import Path

from .loader import ResourceLoader
from .registry import ResourceRegistry
from .resource import Resource


class ResourceManager:
    """
    High-level interface for resource management.
    """

    def __init__(self) -> None:
        self._registry = ResourceRegistry()
        self._loader = ResourceLoader(self._registry)

    @property
    def registry(self) -> ResourceRegistry:
        """
        Return the resource registry.
        """
        return self._registry

    @property
    def loader(self) -> ResourceLoader:
        """
        Return the resource loader.
        """
        return self._loader

    def load(
        self,
        directory: str | Path,
        resource_type: str,
        recursive: bool = True,
    ) -> int:
        """
        Load resources from a directory.
        """
        return self._loader.load_directory(
            directory=directory,
            resource_type=resource_type,
            recursive=recursive,
        )

    def get(self, identifier: str) -> Resource | None:
        """
        Return a resource by identifier.
        """
        return self._registry.get(identifier)

    def require(self, identifier: str) -> Resource:
        """
        Return a resource or raise an exception.
        """
        return self._registry.require(identifier)

    def register(self, resource: Resource) -> None:
        """
        Register a resource.
        """
        self._registry.register(resource)

    def unregister(self, identifier: str) -> None:
        """
        Remove a resource.
        """
        self._registry.unregister(identifier)

    def clear(self) -> None:
        """
        Remove all registered resources.
        """
        self._registry.clear()

    def __contains__(self, identifier: object) -> bool:
        return identifier in self._registry

    def __len__(self) -> int:
        return len(self._registry)
