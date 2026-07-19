# src/fsme/serialization/utils.py

"""
Utility helpers for the serialization subsystem.
"""

from __future__ import annotations

from pathlib import Path

from .serializer import Serializer
from .deserializer import Deserializer


def is_serializer(value: object) -> bool:
    """
    Return True if the value is a Serializer.
    """
    return isinstance(value, Serializer)


def ensure_serializer(value: object) -> Serializer:
    """
    Ensure that the provided value is a Serializer.
    """
    if not isinstance(value, Serializer):
        raise TypeError(
            f"Expected Serializer, got {type(value).__name__}."
        )

    return value


def is_deserializer(value: object) -> bool:
    """
    Return True if the value is a Deserializer.
    """
    return isinstance(value, Deserializer)


def ensure_deserializer(value: object) -> Deserializer:
    """
    Ensure that the provided value is a Deserializer.
    """
    if not isinstance(value, Deserializer):
        raise TypeError(
            f"Expected Deserializer, got {type(value).__name__}."
        )

    return value


def serializer_name(serializer: Serializer) -> str:
    """
    Return the serializer class name.
    """
    return serializer.__class__.__name__


def normalize_path(path: str | Path) -> Path:
    """
    Return a normalized filesystem path.
    """
    return Path(path).expanduser().resolve()