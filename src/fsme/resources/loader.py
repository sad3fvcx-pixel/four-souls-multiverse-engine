# src/fsme/resources/loader.py

"""
Resource loader for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from pathlib import Path

from .registry import ResourceRegistry
from .resource import Resource


class ResourceLoader:
    """
    Discovers and registers resources from the filesystem.
    """

    def __init__(self, registry: ResourceRegistry) -> None:
        self._registry = registry

    def load_directory(
        self,
        directory: str | Path,
        resource_type: str,
        recursive: bool = True,
    ) -> int:
        """
        Load every file from a directory.

        Returns the number of loaded resources.
        """
        path = Path(directory)

        if not path.exists():
            return 0

        if not path.is_dir():
            raise NotADirectoryError(path)

        iterator = path.rglob("*") if recursive else path.glob("*")

        loaded = 0

        for file in iterator:
            if not file.is_file():
                continue

            identifier = self._build_identifier(path, file)

            resource = Resource(
                identifier=identifier,
                path=file,
                resource_type=resource_type,
            )

            self._registry.register(resource)
            loaded += 1

        return loaded

    @staticmethod
    def _build_identifier(root: Path, file: Path) -> str:
        """
        Build a stable resource identifier.
        """
        relative = file.relative_to(root)

        return relative.with_suffix("").as_posix()
