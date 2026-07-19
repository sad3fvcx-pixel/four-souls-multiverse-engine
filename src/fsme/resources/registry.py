# src/fsme/resources/registry.py

"""
Resource registry for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Iterator

from .resource import Resource


class ResourceRegistry:
    """
    Stores and manages engine resources.
    """

    def __init__(self) -> None:
        self._resources: dict[str, Resource] = {}

    def register(self, resource: Resource) -> None:
        """
        Register a resource.
        """
        self._resources[resource.identifier] = resource

    def unregister(self, identifier: str) -> None:
        """
        Remove a resource from the registry.
        """
        self._resources.pop(identifier, None)

    def get(self, identifier: str) -> Resource | None:
        """
        Return a resource by identifier.
        """
        return self._resources.get(identifier)

    def require(self, identifier: str) -> Resource:
        """
        Return a resource or raise KeyError.
        """
        try:
            return self._resources[identifier]
        except KeyError as exc:
            raise KeyError(
                f"Unknown resource '{identifier}'."
            ) from exc

    def contains(self, identifier: str) -> bool:
        """
        Return True if the resource exists.
        """
        return identifier in self._resources

    def clear(self) -> None:
        """
        Remove all resources.
        """
        self._resources.clear()

    def values(self) -> Iterator[Resource]:
        """
        Iterate over resources.
        """
        return iter(self._resources.values())

    def items(self):
        """
        Iterate over (identifier, resource) pairs.
        """
        return self._resources.items()

    def __len__(self) -> int:
        return len(self._resources)

    def __contains__(self, identifier: object) -> bool:
        if not isinstance(identifier, str):
            return False

        return identifier in self._resources

    def __iter__(self) -> Iterator[Resource]:
        return iter(self._resources.values())
