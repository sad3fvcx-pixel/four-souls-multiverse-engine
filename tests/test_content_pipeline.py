"""
What an expansion's author is told, and when.

A content pipeline audit asked where somebody who has never seen this code
still comes unstuck writing their own set. Most of the answers were already
good — a bad field, an unknown name, a wrong parameter are all refused before
a game, naming the file and the card. Four were not, and this covers them.

Two used to load and then stop the game somewhere in the middle of a study.
Two used to escape the report entirely and arrive as exceptions carrying none
of the context every other message has.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import validate_card
from fsme.content import Vocabulary
from fsme.content.errors import InvalidContentError
from fsme.runtime.vocabulary import engine_vocabulary

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return engine_vocabulary()


def a_card(card_id: str = "mine-loot-spark", **over: Any) -> dict:
    card: dict[str, Any] = {
        "id": card_id,
        "name": "Spark",
        "type": "loot",
        "expansion": "mine",
        "schema_version": "1",
        "abilities": [
            {"trigger": "on_play", "effects": [{"effect": "gain_coins", "amount": 1}]}
        ],
    }
    card.update(over)

    return card


def a_tree(tmp_path: Path, sets: dict[str, Any]) -> Path:
    """
    A content root of one or more sets, built where a test may write.
    """
    root = tmp_path / "root"

    for name, body in sets.items():
        cards = body["cards"] if isinstance(body, dict) else body
        manifest = body.get("manifest") if isinstance(body, dict) else None

        (root / name / "cards").mkdir(parents=True)
        (root / name / "manifest.json").write_text(
            json.dumps(
                manifest
                if manifest is not None
                else {
                    "id": name,
                    "name": name,
                    "version": "1.0.0",
                    "schema_version": "1",
                }
            ),
            encoding="utf-8",
        )

        for filename, group in cards.items():
            (root / name / "cards" / filename).write_text(
                json.dumps({"cards": group}), encoding="utf-8"
            )

    return root


def complaints(vocabulary: Vocabulary, card: dict) -> list[str]:
    return validate_card(
        card,
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
        condition_shapes=vocabulary.condition_shapes,
        target_shapes=vocabulary.target_shapes,
    )


def aiming(vocabulary: Vocabulary, targets: list, effects: list | None = None) -> list[str]:
    return complaints(
        vocabulary,
        a_card(
            abilities=[
                {
                    "trigger": "on_play",
                    "targets": targets,
                    "effects": effects
                    or [{"effect": "gain_coins", "amount": 1}],
                }
            ]
        ),
    )


# ----------------------------------------------------------------------
# A bare target name is a target, not a declaration
# ----------------------------------------------------------------------


def test_a_misspelled_bare_target_is_refused(vocabulary: Vocabulary) -> None:
    """
    The object form was always caught and the bare form never was, which is
    backwards: the bare form is the one an author reaches for first.
    """
    (message,) = aiming(vocabulary, ["target_playr"])

    assert "unknown target 'target_playr'" in message
    assert "target_player" in message


def test_a_bare_target_still_binds_under_its_own_name(
    vocabulary: Vocabulary,
) -> None:
    """
    `{"targets": ["all_players"]}` binds the group under the target's name,
    and an effect may then point at it. Binding is what a bare name does;
    declaring a name of its own is what `as` does.
    """
    assert (
        aiming(
            vocabulary,
            ["all_players"],
            [{"effect": "gain_coins", "amount": 1, "target": "all_players"}],
        )
        == []
    )


def test_a_name_introduced_by_as_is_still_the_cards_own(
    vocabulary: Vocabulary,
) -> None:
    assert (
        aiming(
            vocabulary,
            [{"target_player": {"as": "victim"}}],
            [{"effect": "kill", "target": "victim"}],
        )
        == []
    )


# ----------------------------------------------------------------------
# Card ids are global
# ----------------------------------------------------------------------


def test_one_id_in_two_sets_is_refused_with_both_files(tmp_path: Path) -> None:
    """
    This used to pass the whole report and then raise `DuplicateCardError` on
    first use, naming neither set. The registry keeps one table for the table,
    so a card id is global whether or not anybody said so.
    """
    root = a_tree(
        tmp_path,
        {
            "mine": {"cards": {"loot.json": [a_card()]}},
            "theirs": {
                "cards": {"loot.json": [a_card(expansion="theirs")]}
            },
        },
    )

    with pytest.raises(InvalidContentError) as raised:
        load_content(root)

    said = str(raised.value)

    assert "card id is used in two files" in said
    assert "mine" in said and "theirs" in said
    assert "must be unique" in said


def test_two_sets_with_different_ids_load_together(tmp_path: Path) -> None:
    root = a_tree(
        tmp_path,
        {
            "mine": {"cards": {"loot.json": [a_card()]}},
            "theirs": {
                "cards": {
                    "loot.json": [
                        a_card(card_id="theirs-loot-spark", expansion="theirs")
                    ]
                }
            },
        },
    )

    assert len(load_content(root).registry()) == 2


def test_one_id_twice_in_one_file_is_reported_once(tmp_path: Path) -> None:
    """
    Two cards in one file are the file's problem and are named once. Saying it
    twice, with the same path on both lines, is not more helpful.
    """
    root = a_tree(tmp_path, {"mine": {"cards": {"loot.json": [a_card(), a_card()]}}})

    with pytest.raises(InvalidContentError) as raised:
        load_content(root)

    said = str(raised.value)

    assert said.count("mine-loot-spark") == 1


# ----------------------------------------------------------------------
# A missing requirement is an ordinary problem with a file
# ----------------------------------------------------------------------


def test_a_missing_requirement_is_reported_with_everything_else(
    tmp_path: Path,
) -> None:
    """
    It used to be raised after the report was finished, so a set with a
    missing dependency *and* a broken card told its author about the
    dependency and nothing else.
    """
    root = a_tree(
        tmp_path,
        {
            "mine": {
                "manifest": {
                    "id": "mine",
                    "name": "Mine",
                    "version": "1.0.0",
                    "schema_version": "1",
                    "requires": ["nowhere"],
                },
                "cards": {
                    "loot.json": [
                        a_card(
                            abilities=[
                                {
                                    "trigger": "on_play",
                                    "effects": [{"effect": "gain_glory"}],
                                }
                            ]
                        )
                    ]
                },
            }
        },
    )

    with pytest.raises(InvalidContentError) as raised:
        load_content(root)

    said = str(raised.value)

    assert "requires 'nowhere'" in said
    assert "gain_glory" in said, "both problems, in one report"


def test_a_requirement_that_is_present_is_no_trouble(tmp_path: Path) -> None:
    root = a_tree(
        tmp_path,
        {
            "base": {"cards": {"loot.json": [a_card(card_id="base-loot-a",
                                                    expansion="base")]}},
            "mine": {
                "manifest": {
                    "id": "mine",
                    "name": "Mine",
                    "version": "1.0.0",
                    "schema_version": "1",
                    "requires": ["base"],
                },
                "cards": {"loot.json": [a_card()]},
            },
        },
    )

    assert len(load_content(root).registry()) == 2


def test_two_sets_that_require_each_other_are_not_an_error(
    tmp_path: Path,
) -> None:
    """
    Nothing reads sets in dependency order — directories are read sorted and
    every set is read on its own — so a requirement asserts that a set is
    present and says nothing about when. Both of these are present. Refusing
    them would be inventing a rule for a failure that cannot happen, and the
    day something does order by requirements is the day to add it.
    """
    def needing(name: str, other: str) -> dict:
        return {
            "manifest": {
                "id": name,
                "name": name,
                "version": "1.0.0",
                "schema_version": "1",
                "requires": [other],
            },
            "cards": {
                "loot.json": [a_card(card_id=f"{name}-loot-a", expansion=name)]
            },
        }

    root = a_tree(
        tmp_path, {"mine": needing("mine", "theirs"), "theirs": needing("theirs", "mine")}
    )

    assert len(load_content(root).registry()) == 2


# ----------------------------------------------------------------------
# A replay against different content says so
# ----------------------------------------------------------------------


def test_a_journal_played_against_other_content_is_told_why() -> None:
    from fsme.journal.replay import why_the_content_differs

    library = load_content(ROOT / "content")

    class Recorded:
        def __init__(self, written: str) -> None:
            self.content_version = written

    said = why_the_content_differs(Recorded("base_game@1.0.0,mine@2.0.0"), library)

    assert "not what this was played against" in said
    assert "base_game@1.0.0,mine@2.0.0" in said


def test_matching_content_says_nothing() -> None:
    """
    And says nothing rather than saying the content is the same, which it
    cannot know: two libraries with one identity are not proven identical.
    """
    from fsme.journal.replay import why_the_content_differs

    library = load_content(ROOT / "content")

    class Recorded:
        def __init__(self, written: str) -> None:
            self.content_version = written

    assert why_the_content_differs(Recorded(library.identity()), library) == ""
    assert why_the_content_differs(Recorded(""), library) == ""


# ----------------------------------------------------------------------
# The reference is read off the engine
# ----------------------------------------------------------------------


def test_the_reference_is_up_to_date() -> None:
    """
    `docs/REFERENCE.md` is generated. The four registry documents drifted
    because their lists were kept by hand; this one cannot, because a stale
    copy fails here.
    """
    reference = ROOT / "docs" / "REFERENCE.md"
    before = reference.read_text("utf-8")

    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "make_reference.py")],
        check=True,
        capture_output=True,
    )

    assert reference.read_text("utf-8") == before, (
        "docs/REFERENCE.md is out of date — run tools/make_reference.py"
    )


def test_the_reference_lists_every_name_the_engine_answers_to(
    vocabulary: Vocabulary,
) -> None:
    reference = (ROOT / "docs" / "REFERENCE.md").read_text("utf-8")

    for group in (
        vocabulary.effects,
        vocabulary.conditions,
        vocabulary.targets,
        vocabulary.triggers,
    ):
        missing = sorted(name for name in group if f"`{name}`" not in reference)

        assert missing == []
