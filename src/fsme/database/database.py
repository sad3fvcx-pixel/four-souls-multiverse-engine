# src/fsme/database/database.py

"""
Content database for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Any


class Database:
    """
    In-memory database of engine content.
    """

    def __init__(self) -> None:
        self._tables: dict[str, dict[str, Any]] = {}

    def create_table(self, name: str) -> None:
        """
        Create a table if it does not already exist.
        """
        self._tables.setdefault(name, {})

    def insert(
        self,
        table: str,
        identifier: str,
        value: Any,
    ) -> None:
        """
        Insert a value into a table.
        """
        self.create_table(table)
        self._tables[table][identifier] = value

    def get(
        self,
        table: str,
        identifier: str,
    ) -> Any | None:
        """
        Return a value from a table.
        """
        return self._tables.get(table, {}).get(identifier)

    def remove(
        self,
        table: str,
        identifier: str,
    ) -> None:
        """
        Remove a value from a table.
        """
        if table in self._tables:
            self._tables[table].pop(identifier, None)

    def contains(
        self,
        table: str,
        identifier: str,
    ) -> bool:
        """
        Return True if a value exists.
        """
        return identifier in self._tables.get(table, {})

    def clear(self) -> None:
        """
        Remove all tables.
        """
        self._tables.clear()

    def table(self, name: str) -> dict[str, Any]:
        """
        Return a table, creating it if necessary.
        """
        self.create_table(name)
        return self._tables[name]

    def tables(self) -> tuple[str, ...]:
        """
        Return all table names.
        """
        return tuple(self._tables)
