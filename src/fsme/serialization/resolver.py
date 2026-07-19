# src/fsme/serialization/resolver.py

"""
Serialization resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .context import SerializationContext
from .handler import SerializationHandler
from .result import SerializationResult


class SerializationResolver:
    """
    Resolves serialization operations.
    """

    def __init__(
        self,
        handler: SerializationHandler | None = None,
    ) -> None:
        self._handler = handler or SerializationHandler()

    @property
    def handler(self) -> SerializationHandler:
        return self._handler

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
        return self._handler.dumps(
            context=context,
            obj=obj,
            indent=indent,
        )

    def loads(
        self,
        context: SerializationContext,
        data: str,
    ) -> SerializationResult:
        """
        Deserialize a JSON string.
        """
        return self._handler.loads(
            context=context,
            data=data,
        )

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
        return self._handler.dump(
            context=context,
            obj=obj,
            path=path,
            indent=indent,
        )

    def load(
        self,
        context: SerializationContext,
        path: str | Path,
    ) -> SerializationResult:
        """
        Deserialize a JSON file.
        """
        return self._handler.load(
            context=context,
            path=path,
        )