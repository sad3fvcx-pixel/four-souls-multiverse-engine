# src/fsme/resources/utils.py

"""
Utility helpers for the resource subsystem.
"""

from __future__ import annotations

from pathlib import Path

from .resource import Resource


def is_resource(value: object) -> bool:
    """
    Return True if the value is a Resource.
    """
    return isinstance(value, Resource)


def ensure_resource(value: object) -> Resource:
    """
    Ensure that the provided value is a Resource.
    """
    if not isinstance(value, Resource):
        raise TypeError(
            f"Expected Resource, got {type(value).__name__}."
        )

    return value


def normalize_path(path: str | Path) -> Path:
    """
    Return a normalized Path instance.
    """
    return Path(path).expanduser().resolve()


def resource_name(resource: Resource) -> str:
    """
    Return the resource file name.
    """
    return resource.path.name


def resource_stem(resource: Resource) -> str:
    """
    Return the resource file stem.
    """
    return resource.path.stem


def resource_suffix(resource: Resource) -> str:
    """
    Return the resource file suffix.
    """
    return resource.path.suffix


def resource_exists(resource: Resource) -> bool:
    """
    Return True if the resource exists.
    """
    return resource.path.exists()
