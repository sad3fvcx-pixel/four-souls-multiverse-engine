# src/fsme/serialization/handler.py

"""
Serialization handler for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .context import SerializationContext
from .result import SerializationResult


class SerializationHandler:
    """
    Handles serialization and deserialization operations.
    """

    def dumps(
        self,
        context: SerializationContext,
        obj: Any,
        *,
        indent: int | None = 4,
    ) -> SerializationResult:
        """
        Serialize an object to a JSON string.
        """
        data = context.serializer.dumps(
            obj,
            indent=indent,
        )

        return SerializationResult.ok(data=data)

    def loads(
        self,
        context: SerializationContext,
        data: str,
    ) -> SerializationResult:
        """
        Deserialize a JSON string.
        """
        obj = context.deserializer.loads(data)

        return SerializationResult.ok(data=obj)

    def dump(
        self,
        context: SerializationContext,
        obj: Any,
        path: str | Path,
        *,
        indent: int | None = 4,
    ) -> SerializationResult:
        """
        Serialize an object to a JSON file.
        """
        context.serializer.dump(
            obj,
            path,
            indent=indent,
        )

        return SerializationResult.ok()

    def load(
        self,
        context: SerializationContext,
        path: str | Path,
    ) -> SerializationResult:
        """
        Deserialize a JSON file.
        """
        obj = context.deserializer.load(path)

        return SerializationResult.ok(data=obj)