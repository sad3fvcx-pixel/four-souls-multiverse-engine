# src/fsme/serialization/serializer.py

"""
Serialization utilities for Four Souls Multiverse Engine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Serializer:
    """
    Serialize and deserialize Python objects.
    """

    def dumps(
        self,
        obj: Any,
        *,
        indent: int | None = 4,
    ) -> str:
        """
        Serialize an object to a JSON string.
        """
        return json.dumps(
            obj,
            indent=indent,
            ensure_ascii=False,
        )

    def loads(
        self,
        data: str,
    ) -> Any:
        """
        Deserialize a JSON string.
        """
        return json.loads(data)

    def dump(
        self,
        obj: Any,
        path: str | Path,
        *,
        indent: int | None = 4,
    ) -> None:
        """
        Serialize an object to a JSON file.
        """
        path = Path(path)

        path.write_text(
            self.dumps(
                obj,
                indent=indent,
            ),
            encoding="utf-8",
        )

    def load(
        self,
        path: str | Path,
    ) -> Any:
        """
        Deserialize a JSON file.
        """
        path = Path(path)

        return self.loads(
            path.read_text(
                encoding="utf-8",
            )
        )