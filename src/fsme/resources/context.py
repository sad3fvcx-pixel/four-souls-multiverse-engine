# src/fsme/resources/context.py

"""
Context objects for the resource subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ResourceContext:
    """
    Context used during resource operations.
    """

    root_directory: Path

    recursive: bool = True

    resource_type: str = "generic"

    overwrite: bool = True

    follow_symlinks: bool = False

    def resolve(self, path: str | Path) -> Path:
        """
        Resolve a path relative to the root directory.
        """
        path = Path(path)

        if path.is_absolute():
            return path

        return self.root_directory / path
