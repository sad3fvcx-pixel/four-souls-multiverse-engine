# src/fsme/content/loader.py

"""
The content pipeline.

Read, parse, check the schema, check the meaning, resolve references, register.
No stage is skipped and nothing executable is ever loaded: a content file is
data the engine interprets, never code it runs.

The pipeline collects problems instead of stopping at the first one, then
refuses the whole batch. Half-valid content must never reach a game, and
someone repairing an expansion should see everything wrong with it at once.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fsme.cards import CardDefinition, validate_cards

from .constants import (
    CARD_FILE_EXTENSION,
    CONTENT_SCHEMA_VERSION,
    DEFAULT_ENCODING,
    MANIFEST_NAME,
)
from .errors import ContentLoadError
from .library import ContentLibrary, Expansion
from .manifest import Manifest, validate_manifest
from .report import IssueCategory, ValidationReport
from .vocabulary import Vocabulary

REFERENCE_FIELDS = ("starting_item",)
"""
Metadata keys naming another card.

Reference resolution is a pipeline stage of its own: a character whose starting
item does not exist must be caught while loading, not when somebody tries to
play it.
"""


class ContentLoader:
    """
    Turns directories of card files into a validated library.
    """

    def __init__(self, vocabulary: Vocabulary | None = None) -> None:
        self._vocabulary = vocabulary if vocabulary is not None else Vocabulary()

    @property
    def vocabulary(self) -> Vocabulary:
        return self._vocabulary

    # ------------------------------------------------------------------
    # Whole roots
    # ------------------------------------------------------------------

    def load_root(self, root: Path | str) -> ContentLibrary:
        """
        Load every expansion under a content root.

        Directories are visited in sorted order so that two runs over the same
        files register cards in the same order.
        """
        root_path = Path(root)

        if not root_path.is_dir():
            raise ContentLoadError(f"{root_path}: not a content directory")

        library = ContentLibrary()
        report = ValidationReport()

        for directory in self._expansion_directories(root_path):
            expansion = self._load_expansion(directory, report)

            if expansion is not None:
                self._register(library, expansion, report, directory)

        self._resolve_references(library, report)

        report.raise_if_failed(f"content in {root_path}")

        library.check_dependencies()

        return library

    def load_expansion(self, directory: Path | str) -> Expansion:
        """
        Load a single expansion directory.
        """
        report = ValidationReport()
        expansion = self._load_expansion(Path(directory), report)

        report.raise_if_failed(f"expansion in {directory}")

        if expansion is None:
            raise ContentLoadError(f"{directory}: no manifest found")

        return expansion

    def validate_root(self, root: Path | str) -> ValidationReport:
        """
        Check a content root without building anything.

        This is what a card editor calls while somebody is still typing.
        """
        root_path = Path(root)
        report = ValidationReport()

        if not root_path.is_dir():
            report.add(
                IssueCategory.REFERENCE,
                "not a content directory",
                file=str(root_path),
            )

            return report

        library = ContentLibrary()

        for directory in self._expansion_directories(root_path):
            expansion = self._load_expansion(directory, report)

            if expansion is not None:
                self._register(library, expansion, report, directory)

        self._resolve_references(library, report)

        return report

    # ------------------------------------------------------------------
    # One expansion
    # ------------------------------------------------------------------

    def _expansion_directories(self, root: Path) -> list[Path]:
        """
        Find every directory holding a manifest.

        The rule is the one somebody would guess: **a directory with a manifest
        in it is a set**, whether it sits at the top of the content root or one
        level inside it. ``CONTENT_SECTIONS`` names the four places the project
        keeps its own sets, and that is a filing convention rather than a
        restriction.

        It used to be a restriction, and that made a trap. Somebody assembling
        their own content directory — a copy of ``base_game`` beside a set of
        their own — got their set silently ignored, because the directory was
        not called one of four names. Nothing was reported: the cards simply
        were not there. A rule that quietly drops content is worse than a rule
        that is stricter, because the author has nothing to read.
        """
        directories: list[Path] = []

        if (root / MANIFEST_NAME).is_file():
            directories.append(root)

        for section in sorted(root.iterdir()):
            if not section.is_dir():
                continue

            # A directory may be a set in its own right — the base game is one
            # directory, not a directory of directories — or it may hold one
            # directory per set. Both shapes are ordinary, so both are read.
            if (section / MANIFEST_NAME).is_file():
                directories.append(section)

                continue

            for child in sorted(section.iterdir()):
                if child.is_dir() and (child / MANIFEST_NAME).is_file():
                    directories.append(child)

        return directories

    def _load_expansion(
        self,
        directory: Path,
        report: ValidationReport,
    ) -> Expansion | None:
        manifest_path = directory / MANIFEST_NAME
        raw_manifest = self._read_json(manifest_path, report)

        if raw_manifest is None:
            return None

        before = len(report)
        validate_manifest(raw_manifest, file=str(manifest_path), report=report)

        if len(report) > before:
            return None

        manifest = Manifest.from_data(raw_manifest)
        definitions = self._load_cards(directory, manifest, report)

        return Expansion(manifest=manifest, definitions=tuple(definitions))

    def _load_cards(
        self,
        directory: Path,
        manifest: Manifest,
        report: ValidationReport,
    ) -> list[CardDefinition]:
        definitions: list[CardDefinition] = []
        seen: dict[str, str] = {}

        for file_path in sorted(directory.rglob(f"*{CARD_FILE_EXTENSION}")):
            if file_path.name == MANIFEST_NAME or file_path.name.startswith("_"):
                # A leading underscore marks a file that belongs to the set but
                # is not a card file: hand-written behaviour waiting to be
                # merged in, notes, working material.
                continue

            cards = self._read_cards(file_path, report)

            if cards is None:
                continue

            if not self._check_cards(cards, file_path, manifest, seen, report):
                continue

            definitions.extend(CardDefinition.from_data(card) for card in cards)

        return definitions

    def _check_cards(
        self,
        cards: list[Any],
        file_path: Path,
        manifest: Manifest,
        seen: dict[str, str],
        report: ValidationReport,
    ) -> bool:
        """
        Run schema and semantic validation over one file's cards.
        """
        before = len(report)

        for message in validate_cards(
            cards,
            known_effects=self._vocabulary.effects or None,
            known_triggers=self._vocabulary.triggers or None,
            known_conditions=self._vocabulary.conditions or None,
            known_targets=self._vocabulary.targets or None,
            shapes=self._vocabulary.shapes or None,
            condition_shapes=self._vocabulary.condition_shapes or None,
            target_shapes=self._vocabulary.target_shapes or None,
        ):
            report.add(
                IssueCategory.SCHEMA
                if "missing" in message or "must be" in message
                else IssueCategory.SEMANTIC,
                message,
                expansion=manifest.id,
                file=str(file_path),
            )

        for card in cards:
            if not isinstance(card, Mapping):
                continue

            identifier = str(card.get("id", ""))

            if identifier and identifier in seen:
                report.add(
                    IssueCategory.DUPLICATE,
                    f"card '{identifier}' is already defined in {seen[identifier]}",
                    file=str(file_path),
                    identifier=identifier,
                )
            elif identifier:
                seen[identifier] = str(file_path)

            declared = str(card.get("expansion", ""))

            if declared and declared != manifest.id:
                report.add(
                    IssueCategory.REFERENCE,
                    f"card claims expansion '{declared}' but lives in "
                    f"'{manifest.id}'",
                    file=str(file_path),
                    identifier=identifier,
                )

            schema_version = str(
                card.get("schema_version", CONTENT_SCHEMA_VERSION)
            )

            if schema_version != CONTENT_SCHEMA_VERSION:
                report.add(
                    IssueCategory.VERSION,
                    f"card schema '{schema_version}' is not supported",
                    file=str(file_path),
                    identifier=identifier,
                )

        return len(report) == before

    def _register(
        self,
        library: ContentLibrary,
        expansion: Expansion,
        report: ValidationReport,
        directory: Path,
    ) -> None:
        if expansion.id in library:
            report.add(
                IssueCategory.DUPLICATE,
                f"expansion '{expansion.id}' is defined twice",
                file=str(directory),
                identifier=expansion.id,
            )

            return

        library.add(expansion)

    def _resolve_references(
        self,
        library: ContentLibrary,
        report: ValidationReport,
    ) -> None:
        """
        Check that every card pointing at another card can find it.

        References are resolved once the whole library is present, because a
        character may legitimately start with an item from a different set.
        """
        known = {definition.id for definition in library.definitions()}

        for expansion in library:
            for definition in expansion.definitions:
                for key in REFERENCE_FIELDS:
                    reference = definition.metadata.get(key)

                    if reference is None:
                        continue

                    if str(reference) not in known:
                        report.add(
                            IssueCategory.REFERENCE,
                            f"{key} '{reference}' does not exist in the "
                            f"loaded content",
                            identifier=definition.id,
                            location=key,
                        )

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def _read_json(self, path: Path, report: ValidationReport) -> Any | None:
        try:
            return json.loads(path.read_text(encoding=DEFAULT_ENCODING))
        except FileNotFoundError:
            report.add(IssueCategory.REFERENCE, "file not found", file=str(path))
        except json.JSONDecodeError as error:
            report.add(
                IssueCategory.FORMAT,
                f"invalid JSON: {error}",
                file=str(path),
                location=f"line {error.lineno}",
            )
        except OSError as error:
            report.add(
                IssueCategory.FORMAT, f"cannot read: {error}", file=str(path)
            )

        return None

    def _read_cards(
        self,
        path: Path,
        report: ValidationReport,
    ) -> list[Any] | None:
        data = self._read_json(path, report)

        if data is None:
            return None

        if isinstance(data, list):
            return data

        if isinstance(data, Mapping):
            if "cards" in data:
                cards = data["cards"]

                if not isinstance(cards, list):
                    report.add(
                        IssueCategory.SCHEMA,
                        "'cards' must be a list",
                        file=str(path),
                    )

                    return None

                return cards

            return [data]

        report.add(
            IssueCategory.SCHEMA,
            f"expected an object or a list, got {type(data).__name__}",
            file=str(path),
        )

        return None
