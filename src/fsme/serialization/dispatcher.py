# src/fsme/serialization/dispatcher.py

"""
Serialization dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .context import SerializationContext
from .resolver import SerializationResolver
from .result import SerializationResult


class SerializationDispatcher:
    """
    Dispatches serialization operations.
    """

    def __init__(
        self,
        resolver: SerializationResolver | None = None,
    ) -> None:
        self._resolver = resolver or SerializationResolver()

    @property
    def resolver(self) -> SerializationResolver:
        return self._resolver

    def dumps(
        self,
        context: SerializationContext,
        obj: Any,
        *,
        indent: int | None = 4,
    ) -> SerializationResult:
        """
        Dispatch JSON serialization.
        """
        return self._resolver.dumps(
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
        Dispatch JSON deserialization.
        """
        return self._resolver.loads(
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
        Dispatch serialization to a file.
        """
        return self._resolver.dump(
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
        Dispatch deserialization from a file.
        """
        return self._resolver.load(
            context=context,
            path=path,
        )