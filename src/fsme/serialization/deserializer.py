# src/fsme/serialization/deserializer.py

"""
Deserialization utilities for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .serializer import Serializer


class Deserializer:
    """
    Deserialize Python objects from JSON.
    """

    def __init__(
        self,
        serializer: Serializer | None = None,
    ) -> None:
        self._serializer = serializer or Serializer()

    @property
    def serializer(self) -> Serializer:
        return self._serializer

    def loads(
        self,
        data: str,
    ) -> Any:
        """
        Deserialize a JSON string.
        """
        return self._serializer.loads(data)

    def load(
        self,
        path: str | Path,
    ) -> Any:
        """
        Deserialize a JSON file.
        """
        return self._serializer.load(path)