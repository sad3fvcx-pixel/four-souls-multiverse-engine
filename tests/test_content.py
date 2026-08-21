"""
The content pipeline.

Read, parse, check the schema, check the meaning, resolve references, register.
Half-valid content must never reach a game.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fsme.cards import CardType
from fsme.content import (
    ContentLoader,
    InvalidContentError,
    IssueCategory,
    Manifest,
    Vocabulary,
    validate_manifest,
)
from fsme.database import ContentIndex
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

MANIFEST = {
    "id": "test_set",
    "name": "Test Set",
    "version": "1.0.0",
    "schema_version": "1",
}

GOOD_CARD = {
    "id": "test_set.coin",
    "name": "Coin",
    "type": "loot",
    "expansion": "test_set",
    "abilities": [{"trigger": "on_play", "effects": [{"gain_coins": 1}]}],
}


def write_set(root: Path, name: str, manifest: dict, *files: dict) -> Path:
    directory = root / "custom" / name
    directory.mkdir(parents=True)

    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    for index, payload in enumerate(files):
        (directory / f"cards{index}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    return directory


def loader() -> ContentLoader:
    return ContentLoader(engine_vocabulary())


# ----------------------------------------------------------------------
# The shipped content
# ----------------------------------------------------------------------


def test_the_repository_content_validates() -> None:
    report = loader().validate_root(CONTENT_ROOT)

    assert report.ok, str(report)


def test_the_demo_set_loads_with_every_card_type() -> None:
    library = loader().load_root(CONTENT_ROOT)

    assert "engine_demo" in library

    for card_type in (
        CardType.CHARACTER,
        CardType.STARTING_ITEM,
        CardType.LOOT,
        CardType.TREASURE,
        CardType.MONSTER,
    ):
        assert library.cards_of(card_type), card_type


def test_a_set_says_truthfully_whether_it_is_official() -> None:
    """
    The demo set was written for the engine and says so; the imported sets
    come from the published game and say that.
    """
    library = loader().load_root(CONTENT_ROOT)

    assert library.get("engine_demo").manifest.official is False
    assert library.get("base_game").manifest.official is True


def test_a_section_directory_can_itself_be_a_set() -> None:
    """
    The base game is one directory with a manifest in it, not a directory of
    directories. Both shapes are ordinary and both are read.
    """
    library = loader().load_root(CONTENT_ROOT)

    assert "base_game" in library
    assert len(library.get("base_game")) > 0


def test_a_directory_without_a_manifest_is_not_a_set(tmp_path) -> None:
    (tmp_path / "custom" / "notes").mkdir(parents=True)
    (tmp_path / "custom" / "notes" / "readme.json").write_text("{}", encoding="utf-8")

    library = loader().load_root(tmp_path)

    assert len(library) == 0


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------


def test_every_problem_is_reported_in_one_pass(tmp_path) -> None:
    write_set(
        tmp_path,
        "broken",
        MANIFEST,
        {
            "cards": [
                {"id": "test_set.a", "name": "A", "type": "loot"},
                {
                    "id": "test_set.b",
                    "name": "B",
                    "type": "spaceship",
                    "expansion": "test_set",
                    "abilities": [],
                },
            ]
        },
    )

    report = loader().validate_root(tmp_path)

    assert not report.ok
    assert len(report) >= 3


def test_unknown_effects_are_caught_as_semantic_problems(tmp_path) -> None:
    write_set(
        tmp_path,
        "semantic",
        MANIFEST,
        {
            "cards": [
                {
                    "id": "test_set.x",
                    "name": "X",
                    "type": "loot",
                    "expansion": "test_set",
                    "abilities": [
                        {"trigger": "on_play", "effects": [{"summon_dragon": 1}]}
                    ],
                }
            ]
        },
    )

    report = loader().validate_root(tmp_path)

    assert report.of_category(IssueCategory.SEMANTIC)
    assert "summon_dragon" in str(report)


def test_unknown_conditions_and_targets_are_caught(tmp_path) -> None:
    write_set(
        tmp_path,
        "vocabulary",
        MANIFEST,
        {
            "cards": [
                {
                    "id": "test_set.x",
                    "name": "X",
                    "type": "loot",
                    "expansion": "test_set",
                    "abilities": [
                        {
                            "trigger": "on_play",
                            "conditions": ["is_wednesday"],
                            "effects": [
                                {
                                    "effect": "gain_coins",
                                    "amount": 1,
                                    "target": "the_moon",
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    )

    report = loader().validate_root(tmp_path)

    assert "is_wednesday" in str(report)
    assert "the_moon" in str(report)


def test_a_card_claiming_the_wrong_expansion_is_caught(tmp_path) -> None:
    write_set(
        tmp_path,
        "mismatch",
        MANIFEST,
        {"cards": [dict(GOOD_CARD, expansion="somewhere_else")]},
    )

    report = loader().validate_root(tmp_path)

    assert report.of_category(IssueCategory.REFERENCE)


def test_duplicate_identifiers_are_caught_across_files(tmp_path) -> None:
    write_set(
        tmp_path,
        "duplicates",
        MANIFEST,
        {"cards": [GOOD_CARD]},
        {"cards": [GOOD_CARD]},
    )

    report = loader().validate_root(tmp_path)

    assert report.of_category(IssueCategory.DUPLICATE)


def test_a_dangling_starting_item_is_caught(tmp_path) -> None:
    """
    Reference resolution is its own stage: a character whose item does not
    exist is caught while loading, not when somebody tries to play it.
    """
    write_set(
        tmp_path,
        "dangling",
        MANIFEST,
        {
            "cards": [
                {
                    "id": "test_set.hero",
                    "name": "Hero",
                    "type": "character",
                    "expansion": "test_set",
                    "health": 2,
                    "metadata": {"starting_item": "test_set.missing"},
                    "abilities": [],
                }
            ]
        },
    )

    report = loader().validate_root(tmp_path)

    issues = report.of_category(IssueCategory.REFERENCE)

    assert issues
    assert "test_set.missing" in str(issues[0])


def test_broken_json_is_reported_with_its_line(tmp_path) -> None:
    directory = tmp_path / "custom" / "broken_json"
    directory.mkdir(parents=True)

    (directory / "manifest.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    (directory / "cards.json").write_text("{ not json", encoding="utf-8")

    report = loader().validate_root(tmp_path)

    issues = report.of_category(IssueCategory.FORMAT)

    assert issues
    assert "line" in issues[0].location


def test_an_unsupported_schema_version_is_refused(tmp_path) -> None:
    write_set(
        tmp_path,
        "future",
        dict(MANIFEST, schema_version="99"),
        {"cards": [GOOD_CARD]},
    )

    report = loader().validate_root(tmp_path)

    assert report.of_category(IssueCategory.VERSION)


def test_loading_invalid_content_raises_with_every_problem(tmp_path) -> None:
    write_set(
        tmp_path,
        "bad",
        MANIFEST,
        {"cards": [{"id": "test_set.a", "name": "A", "type": "loot"}]},
    )

    with pytest.raises(InvalidContentError) as error:
        loader().load_root(tmp_path)

    assert "expansion" in str(error.value)
    assert "abilities" in str(error.value)


def test_a_missing_dependency_is_refused(tmp_path) -> None:
    """
    Reported like any other problem with a file rather than raised on its own.

    It used to be raised after the report was already finished, so a set with
    a missing dependency and three broken cards told its author about the
    dependency and nothing else.
    """
    write_set(
        tmp_path,
        "dependent",
        dict(MANIFEST, requires=["nowhere"]),
        {"cards": [GOOD_CARD]},
    )

    with pytest.raises(InvalidContentError) as error:
        loader().load_root(tmp_path)

    assert "requires 'nowhere'" in str(error.value)


def test_manifest_validation_reports_missing_fields() -> None:
    report = validate_manifest({"name": "No Identity"})

    assert not report.ok
    assert "id" in str(report)
    assert "version" in str(report)


def test_an_empty_vocabulary_checks_structure_only(tmp_path) -> None:
    """
    Without a vocabulary the pipeline still enforces the schema; it just has
    nothing to check meaning against.
    """
    write_set(
        tmp_path,
        "loose",
        MANIFEST,
        {
            "cards": [
                {
                    "id": "test_set.x",
                    "name": "X",
                    "type": "loot",
                    "expansion": "test_set",
                    "abilities": [
                        {"trigger": "on_play", "effects": [{"summon_dragon": 1}]}
                    ],
                }
            ]
        },
    )

    assert ContentLoader(Vocabulary()).validate_root(tmp_path).ok
    assert not loader().validate_root(tmp_path).ok


# ----------------------------------------------------------------------
# Library and index
# ----------------------------------------------------------------------


def test_the_library_registers_every_card_once() -> None:
    library = loader().load_root(CONTENT_ROOT)
    registry = library.registry()

    assert len(registry) == len(library.definitions())


def test_the_index_answers_by_type_tag_and_expansion() -> None:
    index = ContentIndex.of(loader().load_root(CONTENT_ROOT))

    assert index.by_type(CardType.MONSTER)
    assert index.by_expansion("engine_demo")
    assert "boss" in index.tags()
    assert index.by_tag("boss")
    assert index.get("engine_demo.hollow_king") is not None
    assert index.get("nothing.here") is None


def test_the_index_counts_what_was_loaded() -> None:
    index = ContentIndex.of(loader().load_root(CONTENT_ROOT))

    counts = index.counts()

    assert counts["monster"] == len(index.by_type(CardType.MONSTER))
    assert sum(counts.values()) == len(index)


def test_a_manifest_describes_itself() -> None:
    manifest = Manifest.from_data(MANIFEST)

    assert str(manifest) == "test_set 1.0.0"
    assert manifest.official is False
