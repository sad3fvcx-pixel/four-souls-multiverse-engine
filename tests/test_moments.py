"""
Where a game turned, and what that claim is allowed to mean.

The measurement is a ledger read off the events, so the tests are mostly about
what it refuses to do: attribute a swing to a move whose events moved nothing,
credit a seat with something the engine did not record, or let a moment decided
by a die read as a moment decided by a player.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsme.api import load_content
from fsme.content import ContentLibrary
from fsme.journal import Journal
from fsme.lab.analysis import turning_points
from fsme.lab.analysis.moments import A_SOUL, Ledger, Turning
from fsme.lab.simulation import play_one

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture(scope="module")
def a_journal(everything: ContentLibrary) -> Journal:
    journal, _ = play_one(everything, seed=7, players=3, thinking_seats=(0,))

    return journal


@pytest.fixture(scope="module")
def turning(a_journal: Journal) -> Turning:
    return turning_points(a_journal, top=3)


def test_the_moments_are_measured_towards_whoever_won(
    a_journal: Journal, turning: Turning
) -> None:
    assert turning.towards == a_journal.outcome.get("winner")
    assert turning.won is (a_journal.outcome.get("winner") is not None)
    assert turning.towards_name == a_journal.players[turning.towards or 0]


def test_only_the_moves_that_moved_something_are_weighed(
    a_journal: Journal, turning: Turning
) -> None:
    # Most of a game is passing priority and ending phases. A report that
    # weighed those would be ranking noise.
    assert turning.moves == len(a_journal.entries)
    assert 0 < turning.weighed < turning.moves


def test_no_more_moments_are_named_than_were_asked_for(
    a_journal: Journal,
) -> None:
    assert len(turning_points(a_journal, top=2).moments) <= 2
    assert turning_points(a_journal, top=0).moments == []


def test_the_moments_are_the_largest_swings(turning: Turning) -> None:
    swings = [abs(moment.swing) for moment in turning.moments]

    assert swings == sorted(swings, reverse=True)


def test_a_soul_outweighs_anything_one_move_plausibly_pays() -> None:
    # A move hands over a handful of cents or a handful of hit points. Against
    # those the soul has to win, or the largest swings in a game would be the
    # turns somebody got paid rather than the turns somebody scored.
    assert Ledger(souls=1).standing == A_SOUL

    assert Ledger(coins=25).standing < A_SOUL
    assert Ledger(hp=10).standing < A_SOUL
    assert Ledger(deaths=1).standing > -A_SOUL

    # And where it stops winning is arithmetic anybody can check: a hundred
    # cents is ten items, and ten items is not less than a quarter of a game.
    assert Ledger(coins=100).standing >= A_SOUL


def test_a_moment_says_what_the_events_said(turning: Turning) -> None:
    for moment in turning.moments:
        # Every word in the caption names a seat at the table, because every
        # word came from an event the engine attributed to one.
        assert moment.ledgers
        assert moment.turn >= 0
        assert moment.label


def test_a_moment_decided_by_dice_says_so(turning: Turning) -> None:
    for moment in turning.moments:
        assert moment.decided_by_dice == bool(moment.dice)

        if moment.chance is not None:
            assert 0.0 <= moment.chance <= 1.0


def test_a_game_nobody_played_has_nothing_to_say() -> None:
    empty = Journal(seed=1, players=("Ann", "Bo"))

    told = turning_points(empty)

    assert told.moments == []
    assert told.weighed == 0


def test_a_game_with_one_seat_has_nothing_to_compare(
    everything: ContentLibrary,
) -> None:
    journal, _ = play_one(everything, seed=2, players=1)

    assert turning_points(journal).moments == []


def test_a_turning_is_plain_data(turning: Turning) -> None:
    written = turning.to_dict()

    assert written["seed"] == turning.seed
    assert len(written["moments"]) == len(turning.moments)

    for moment in written["moments"]:
        assert set(moment) >= {"turn", "swing", "said", "decided_by_dice"}


def test_the_account_says_no_other_line_of_play_was_tried(
    a_journal: Journal, turning: Turning
) -> None:
    from fsme.lab.analysis import explain, summarise

    told = explain(summarise(a_journal), turning=turning)

    assert "Where it turned" in told
    assert "not proof it had to go there" in told


def test_a_game_without_a_winner_says_who_it_is_measured_towards() -> None:
    from fsme.journal import Entry, Happening

    journal = Journal(
        seed=5,
        players=("Ann", "Bo"),
        entries=[
            Entry(
                index=0,
                command="attack",
                player=1,
                events=(Happening(type="soul_gained", controller=1),),
            )
        ],
    )

    told = turning_points(journal)

    assert told.won is False
    assert told.towards == 1
    assert told.towards_name == "Bo"
