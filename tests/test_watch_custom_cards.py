"""
The cards somebody wrote, in the game they watch.

FSME's front page offers "Watch a game — see the engine play, with your cards
in it", and for one release that last clause was not true: the desk loaded the
cards FSME ships and nothing else, so an author could make a set, save it, open
the watch page and never see it. Every other command already read both places.

These tests are about the two staying one pipeline. Nothing here loads content
its own way: what the desk reads is what `library` returns, which is what every
command returns, and a card somebody wrote is dealt exactly like a card we
shipped because it went through the same loader into the same library.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from fsme.api import Session
from fsme.cli.main import content_roots, library
from fsme.lab.desk import author

CONTENT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    A workspace of this test's own, so nothing touches a real one.
    """
    where = tmp_path / "FSME"
    monkeypatch.setenv("FSME_HOME", str(where))

    return where


def as_the_desk_does() -> Any:
    """
    Exactly what `fsme desk` loads, asked the way the desk asks it.
    """
    return library(argparse.Namespace(content=None))


def a_saved_card(name: str = "Lucky Penny") -> dict[str, Any]:
    """
    A set and a card in it, made through the Author UI's own path.
    """
    made = author.make_set("My Cards")
    saved = author.save_card(
        {
            "set": made["id"],
            "card": {
                "fields": {
                    "name": name,
                    "type": "loot",
                    "abilities": [
                        {
                            "fields": {
                                "trigger": "on_play",
                                "effects": [
                                    {
                                        "id": "gain_coins",
                                        "fields": {"amount": 3},
                                        "aim": "controller",
                                        "aim_fields": {},
                                    }
                                ],
                            }
                        }
                    ],
                },
                "groups": {},
            },
        }
    )

    assert saved["saved"], saved["problems"]

    return {"set": made["id"], "card": saved["card"]}


# ----------------------------------------------------------------------
# 1. The shipped cards still work
# ----------------------------------------------------------------------


def test_watch_mode_deals_the_shipped_cards(home: Path) -> None:
    """
    With no set of one's own, nothing changes: the game is the game.
    """
    loaded = as_the_desk_does()
    session = Session(loaded, players=2, seed=3)

    assert "base_game" in loaded.expansions
    assert session.chosen == (), "narrowed to something without being asked"
    assert len(list(session.playing.definitions())) > 1000
    assert session.view(0)["state"]["players"]


# ----------------------------------------------------------------------
# 2. And so does a set somebody wrote
# ----------------------------------------------------------------------


def test_a_card_somebody_wrote_is_in_the_game_they_watch(home: Path) -> None:
    """
    The whole issue, end to end: make a set, save it, and find the card in
    what the watch page would deal from.
    """
    mine = a_saved_card()
    session = Session(as_the_desk_does(), players=2, seed=3)

    dealt = {one.id for one in session.playing.definitions()}

    assert mine["card"]["id"] in dealt


def test_the_desk_reads_the_authors_sets_as_well_as_the_shipped_ones(
    home: Path,
) -> None:
    """
    Two roots, named by the one helper that knows where cards come from.
    """
    from fsme.content.workspace import sets_directory

    roots = content_roots(None)

    assert len(roots) == 2
    assert roots[0] == CONTENT or roots[0].is_dir()
    assert roots[1] == sets_directory().parent / sets_directory().name


def test_a_game_can_be_narrowed_to_the_shipped_set_and_a_written_one(
    home: Path,
) -> None:
    mine = a_saved_card()
    session = Session(as_the_desk_does(), players=2, seed=3)

    session.restart(sets=["base_game", mine["set"]])

    assert session.chosen == ("base_game", mine["set"])

    dealt = list(session.playing.definitions())

    assert mine["card"]["id"] in {one.id for one in dealt}
    assert any(one.expansion == "base_game" for one in dealt)


def test_choosing_nothing_widens_back_to_everything(home: Path) -> None:
    mine = a_saved_card()
    session = Session(as_the_desk_does(), players=2, seed=3)
    everything = len(list(session.playing.definitions()))

    session.restart(sets=["base_game", mine["set"]])

    assert len(list(session.playing.definitions())) < everything

    session.restart(sets=[])

    assert session.chosen == ()
    assert len(list(session.playing.definitions())) == everything


# ----------------------------------------------------------------------
# 3. And when it cannot be done, it says so
# ----------------------------------------------------------------------


def test_a_set_that_was_never_loaded_is_named_rather_than_ignored(
    home: Path,
) -> None:
    """
    Dealing without the cards somebody asked for, silently, is the bug this
    whole change exists to fix — so asking for a set that is not there is a
    refusal and not a shrug.
    """
    session = Session(as_the_desk_does(), players=2, seed=3)

    with pytest.raises(ValueError) as refused:
        session.restart(sets=["no_such_set_of_mine"])

    assert "no_such_set_of_mine" in str(refused.value)
    assert "base_game" in str(refused.value), "it should say what there is"


def test_a_choice_no_game_can_be_dealt_from_is_refused_and_put_back(
    home: Path,
) -> None:
    """
    A set of one loot card is content, and it is not a game — there is nothing
    to buy. The refusal has to leave the session as it was, or the restart that
    would undo the mistake fails for the same reason.
    """
    from fsme.util.errors import EngineError

    mine = a_saved_card()
    session = Session(as_the_desk_does(), players=2, seed=3)
    before = len(list(session.playing.definitions()))

    with pytest.raises(EngineError) as refused:
        session.restart(sets=[mine["set"]])

    assert "treasure" in str(refused.value)
    assert session.chosen == (), "left narrowed to content it cannot deal"
    assert len(list(session.playing.definitions())) == before

    # And the session still works.
    session.restart(seed=4)

    assert session.view(0)["state"]["players"]


def test_an_author_set_that_will_not_load_says_which_card_is_wrong(
    home: Path,
) -> None:
    """
    A set edited by hand into something the loader refuses. The message names
    the file and the card, because it is the same report every other command
    would print for the same set.
    """
    import json

    from fsme.content.errors import InvalidContentError
    from fsme.content.workspace import sets_directory

    a_saved_card()
    broken = sets_directory() / "my_cards" / "cards" / "broken.json"
    broken.write_text(
        json.dumps({"cards": [{"id": "my_cards-loot-x", "name": "X"}]}),
        encoding="utf-8",
    )

    with pytest.raises(InvalidContentError) as refused:
        as_the_desk_does()

    said = str(refused.value)

    assert "my_cards-loot-x" in said or "broken.json" in said, said


# ----------------------------------------------------------------------
# 4. One pipeline, not two
# ----------------------------------------------------------------------


def test_a_written_card_and_a_shipped_card_arrive_the_same_way(
    home: Path,
) -> None:
    """
    The point of the fix. Both are `CardDefinition`s in the same library, from
    the same loader, checked against the same vocabulary — there is nothing
    about one that says where it came from, because nothing about them differs.
    """
    mine = a_saved_card()
    loaded = as_the_desk_does()

    written = next(
        one for one in loaded.definitions() if one.id == mine["card"]["id"]
    )
    shipped = next(
        one for one in loaded.definitions() if one.expansion == "base_game"
    )

    assert type(written) is type(shipped)
    assert written.abilities, "a written card lost its rules on the way in"

    # Each is in its own set, and both sets are in the one library, reached by
    # the one lookup. There is no second shelf for cards somebody wrote.
    for one in (written, shipped):
        assert one in loaded.get(one.expansion).definitions


def test_the_desk_uses_the_same_loader_every_command_uses() -> None:
    """
    Read off the source: `front` must not grow a loader of its own again.

    This is the regression. The desk called `load_content(content_root(...))`
    while every other command called `library(args)`, and one root is exactly
    the bug — so what is checked is that the desk asks the same question.
    """
    import inspect

    from fsme.cli.main import front

    source = inspect.getsource(front)

    assert "library(args)" in source
    assert "load_content(" not in source


def test_the_watch_page_can_be_told_which_sets_to_deal_from() -> None:
    page = (
        Path(__file__).resolve().parents[1] / "src/fsme/web/static/index.html"
    ).read_text("utf-8")

    assert 'id="sets"' in page
    assert "/api/content" in page
    assert "sets: chosen" in page
