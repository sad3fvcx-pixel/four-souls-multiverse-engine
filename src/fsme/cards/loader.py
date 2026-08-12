# src/fsme/cards/loader.py

"""
Card content loading for Four Souls Multiverse Engine.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from pathlib import Path
from typing import Any

from .definition import CardDefinition
from .errors import InvalidCardError
from .registry import CardRegistry
from .validator import validate_cards


class CardLoader:
    """
    Turns content files into validated card definitions.

    Nothing executable is ever loaded from content: a file describes cards, and
    the engine decides what those descriptions mean.
    """

    def __init__(
        self,
        *,
        known_effects: Collection[str] | None = None,
        known_triggers: Collection[str] | None = None,
    ) -> None:
        self._known_effects = known_effects
        self._known_triggers = known_triggers

    def load_data(self, data: Any, *, origin: str = "<data>") -> list[CardDefinition]:
        """
        Validate and build definitions from already parsed content.
        """
        cards = self._extract(data, origin)

        errors = validate_cards(
            cards,
            known_effects=self._known_effects,
            known_triggers=self._known_triggers,
        )

        if errors:
            raise InvalidCardError(
                f"{origin}: invalid card content:\n  " + "\n  ".join(errors)
            )

        return [CardDefinition.from_data(card) for card in cards]

    def load_file(self, path: Path | str) -> list[CardDefinition]:
        """
        Load every card from one JSON file.
        """
        file_path = Path(path)

        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise InvalidCardError(f"{file_path}: invalid JSON: {error}") from error

        return self.load_data(raw, origin=str(file_path))

    def load_directory(self, path: Path | str) -> list[CardDefinition]:
        """
        Load every ``*.json`` file under a directory, recursively.

        Files are visited in sorted order so that two runs over the same
        content produce the same registration order.
        """
        directory = Path(path)

        if not directory.is_dir():
            raise InvalidCardError(f"{directory}: not a directory")

        definitions: list[CardDefinition] = []

        for file_path in sorted(directory.rglob("*.json")):
            definitions.extend(self.load_file(file_path))

        return definitions

    def load_into(
        self,
        registry: CardRegistry,
        path: Path | str,
    ) -> CardRegistry:
        """
        Load a file or directory straight into a registry.
        """
        source = Path(path)

        definitions = (
            self.load_directory(source)
            if source.is_dir()
            else self.load_file(source)
        )

        registry.register_all(definitions)

        return registry

    @staticmethod
    def _extract(data: Any, origin: str) -> list[Any]:
        """
        Accept the three shapes content files use.
        """
        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            if "cards" in data:
                cards = data["cards"]

                if not isinstance(cards, list):
                    raise InvalidCardError(f"{origin}: 'cards' must be a list")

                return cards

            return [data]

        raise InvalidCardError(
            f"{origin}: expected an object or a list, got {type(data).__name__}"
        )
