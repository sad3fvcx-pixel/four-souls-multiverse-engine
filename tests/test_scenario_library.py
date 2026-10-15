"""
A folder of experiments, and what identifies one.

Two identifiers, because two questions get asked. An `id` names the experiment
somebody is maintaining and survives being edited — renaming a study does not
make it a different study. A digest identifies the configuration and changes
the moment the game it sets up changes. This file is mostly about keeping those
two straight, and about the promise that a library is a convenience: deleting
one never stops a journal replaying.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fsme.api import load_content
from fsme.content import ContentLibrary
from fsme.journal import replay_journal
from fsme.journal.file import read, wrap
from fsme.lab.simulation import play_one
from fsme.scenario import (
    Content,
    Scenario,
    ScenarioError,
    Seat,
    Table,
    digest_of,
    open_library,
)
from fsme.scenario import save as save_scenario

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"
SHIPPED = Path(__file__).resolve().parents[1] / "scenarios"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


def a_shelf(tmp_path: Path, *scenarios: Scenario) -> Path:
    where = tmp_path / "scenarios"
    where.mkdir()

    for index, scenario in enumerate(scenarios):
        save_scenario(scenario, where / f"{scenario.id or index}.json")

    return where


# ----------------------------------------------------------------------
# Reading a folder
# ----------------------------------------------------------------------


def test_a_library_holds_the_scenarios_in_a_folder(tmp_path: Path) -> None:
    where = a_shelf(
        tmp_path,
        Scenario(id="one", name="The first", table=Table(shop_slots=0)),
        Scenario(id="two", name="The second", table=Table(souls_to_win=2)),
    )

    shelf = open_library(where)

    assert len(shelf) == 2
    assert shelf.ids() == ("one", "two")
    assert shelf.get("two").table.souls_to_win == 2


def test_a_scenario_without_an_id_is_called_after_its_file(tmp_path: Path) -> None:
    where = tmp_path / "scenarios"
    where.mkdir()
    save_scenario(Scenario(name="unnamed"), where / "an-experiment.json")

    shelf = open_library(where)

    assert shelf.ids() == ("an-experiment",)


def test_a_scenario_that_names_itself_is_not_renamed_by_its_file(
    tmp_path: Path,
) -> None:
    """
    A filename is a place, not a name. Moving a file must not rename the
    experiment inside it.
    """
    where = tmp_path / "scenarios"
    where.mkdir()
    save_scenario(Scenario(id="lost_expedition"), where / "whatever.json")

    assert open_library(where).ids() == ("lost_expedition",)


def test_a_library_says_what_it_holds_when_asked_for_something_else(
    tmp_path: Path,
) -> None:
    shelf = open_library(a_shelf(tmp_path, Scenario(id="one")))

    with pytest.raises(ScenarioError) as raised:
        shelf.get("two")

    said = str(raised.value)

    assert "no scenario called 'two'" in said
    assert "one" in said


def test_two_scenarios_with_one_name_are_refused(tmp_path: Path) -> None:
    where = tmp_path / "scenarios"
    where.mkdir()
    save_scenario(Scenario(id="same"), where / "a.json")
    save_scenario(Scenario(id="same"), where / "b.json")

    with pytest.raises(ScenarioError) as raised:
        open_library(where)

    assert "two scenarios are called 'same'" in str(raised.value)


def test_one_bad_file_refuses_the_whole_folder(tmp_path: Path) -> None:
    """
    Reported together, because a library with a broken file in it is a library
    somebody is about to fix.
    """
    where = tmp_path / "scenarios"
    where.mkdir()
    save_scenario(Scenario(id="fine"), where / "fine.json")
    (where / "broken.json").write_text('{"format": "something-else"}', encoding="utf-8")

    with pytest.raises(ScenarioError) as raised:
        open_library(where)

    assert "is written in format" in str(raised.value)


def test_a_folder_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ScenarioError) as raised:
        open_library(tmp_path / "nowhere")

    assert "not a directory of scenarios" in str(raised.value)


def test_the_shipped_scenarios_all_read() -> None:
    """
    The folder in the repository is a folder somebody will copy from.
    """
    shelf = open_library(SHIPPED)

    assert len(shelf) >= 2

    for entry in shelf:
        assert entry.id
        assert entry.scenario.name


# ----------------------------------------------------------------------
# What identifies a scenario
# ----------------------------------------------------------------------


def test_a_digest_is_about_the_game_and_not_the_label() -> None:
    """
    Renaming an experiment does not make it a different experiment, and neither
    does dealing it from another seed: what names one game is the pair.
    """
    setup = {
        "content": Content(expansions=("base_game",)),
        "table": Table(shop_slots=0),
        "players": (Seat(coins=9), Seat()),
    }

    one = Scenario(id="a", author="Ann", name="One", description="x", seed=1, **setup)
    same = Scenario(id="b", author="Bo", name="Another", seed=999, **setup)

    assert digest_of(one) == digest_of(same)


def test_a_digest_changes_when_the_game_does() -> None:
    base = Scenario(table=Table(shop_slots=0))

    assert digest_of(base) != digest_of(Scenario(table=Table(shop_slots=1)))
    assert digest_of(base) != digest_of(
        Scenario(table=Table(shop_slots=0), players=(Seat(coins=9),))
    )
    assert digest_of(base) != digest_of(
        Scenario(table=Table(shop_slots=0), interactive_priority=True)
    )


def test_a_digest_is_stable_across_readings(tmp_path: Path) -> None:
    from fsme.scenario import load as read_one

    scenario = Scenario(
        id="steady",
        content=Content(expansions=("base_game",)),
        players=(Seat(character="characters-base_game-isaac"),),
    )
    where = save_scenario(scenario, tmp_path / "steady.json")

    assert digest_of(read_one(where)) == digest_of(scenario)
    assert digest_of(read_one(where)) == digest_of(read_one(where))


def test_an_experiment_that_asks_for_nothing_has_no_digest() -> None:
    assert digest_of(Scenario(id="named", name="but empty")) == ""


# ----------------------------------------------------------------------
# The library is a convenience, not a dependency
# ----------------------------------------------------------------------


def test_a_journal_records_which_experiment_it_came_from(
    everything: ContentLibrary, tmp_path: Path
) -> None:
    scenario = Scenario(
        id="lost_expedition",
        name="Lost expedition",
        content=Content(expansions=("base_game",)),
        table=Table(shop_slots=0),
    )

    journal, _ = play_one(everything, seed=13, players=2, scenario=scenario)

    assert journal.scenario_id == "lost_expedition"
    assert journal.scenario_digest == digest_of(scenario)


def test_deleting_the_library_does_not_stop_a_journal_replaying(
    everything: ContentLibrary, tmp_path: Path
) -> None:
    """
    The promise the library is allowed to exist under.
    """
    from fsme.scenario import load as read_one

    where = a_shelf(
        tmp_path,
        Scenario(
            id="lost_expedition",
            content=Content(expansions=("base_game",)),
            table=Table(shop_slots=0),
            players=(Seat(coins=9), Seat()),
        ),
    )

    shelf = open_library(where)
    scenario = read_one(shelf.entry("lost_expedition").path)

    journal, game = play_one(everything, seed=13, players=2, scenario=scenario)

    assert game.is_over

    kept = tmp_path / "kept.json"
    kept.write_text(json.dumps(wrap(journal)), encoding="utf-8")

    for path in where.iterdir():
        path.unlink()

    where.rmdir()

    assert not where.exists()

    playback = replay_journal(read(kept), everything)

    assert playback.faithful, str(playback.divergence)
    assert playback.replayed == len(journal.entries)
