# src/fsme/content/utils.py

"""
Utility helpers for the content subsystem.
"""

from __future__ import annotations

from pathlib import Path

from .registry import ContentRegistry


def is_registry(value: object) -> bool:
    """
    Return True if the value is a ContentRegistry.
    """
    return isinstance(value, ContentRegistry)


def ensure_registry(value: object) -> ContentRegistry:
    """
    Ensure that the provided value is a ContentRegistry.
    """
    if not isinstance(value, ContentRegistry):
        raise TypeError(
            f"Expected ContentRegistry, got {type(value).__name__}."
        )

    return value


def content_name(registry: ContentRegistry) -> str:
    """
    Return the registry class name.
    """
    return registry.__class__.__name__


def normalize_path(path: str | Path) -> Path:
    """
    Return a normalized filesystem path.
    """
    return Path(path).expanduser().resolve()