"""
Playing many games and counting them.

Three claims. A run is reproducible — the same seeds give the same games, or
nothing measured across them means anything. The counting matches the journals
it counted, entry for entry. And the tally does not quietly turn an absence of
evidence into a number: a thing that was never measured has no average.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fsme.analysis import Tally, report
from fsme.api import load_content
from fsme.content import ContentLibrary
from fsme.journal import Journal
from fsme.replay import state_digest
from fsme.simulation import ScriptedAgent, play_one, run

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture(scope="module")
def a_few(everything: ContentLibrary) -> list:
    """
    A handful of games, played once and shared by the tests that read them.
    """
    return list(run(everything, 6, 2))


def test_a_run_plays_the_games_it_was_asked_for(a_few: list) -> None:
    assert len(a_few) == 6
    assert [outcome.seed for outcome in a_few] == list(range(6))


def test_the_games_actually_finish(a_few: list) -> None:
    """
    Not a rule of the engine, but the thing a simulation depends on: a run
    made mostly of abandoned games is measuring nothing.
    """
    finished = [outcome for outcome in a_few if outcome.finished]

    assert len(finished) == len(a_few)
    assert all(outcome.winner is not None for outcome in finished)


def test_the_same_seed_is_the_same_game(everything: ContentLibrary) -> None:
    once, first = play_one(everything, seed=4, players=2)
    twice, second = play_one(everything, seed=4, players=2)

    assert once.to_dict() == twice.to_dict()
    assert state_digest(first.state) == state_digest(second.state)


def test_different_seeds_are_different_games(everything: ContentLibrary) -> None:
    one, _ = play_one(everything, seed=4, players=2)
    other, _ = play_one(everything, seed=5, players=2)

    assert one.to_dict() != other.to_dict()


def test_a_run_can_start_anywhere(everything: ContentLibrary) -> None:
    outcomes = list(run(everything, 2, 2, first_seed=100))

    assert [outcome.seed for outcome in outcomes] == [100, 101]


def test_the_journals_can_be_written_as_they_are_played(
    everything: ContentLibrary, tmp_path: Path
) -> None:
    list(run(everything, 3, 2, journals_into=tmp_path))

    written = sorted(tmp_path.glob("game-*.json"))

    assert len(written) == 3

    back = Journal.load(written[0])

    assert back.seed == 0
    assert len(back) > 0


def test_the_agent_only_ever_plays_what_the_engine_allows(
    everything: ContentLibrary,
) -> None:
    """
    The agent is not clever, and it is not allowed to be wrong either.
    """
    from fsme.game import Game

    game = Game.from_content(everything, ["Ann", "Bo"], seed=9)
    game.start()

    agent = ScriptedAgent(9)

    for _ in range(200):
        if game.is_over:
            break

        chosen = agent.choose(game)

        assert chosen is not None, "a game with nothing to do and no question"

        command, label = chosen

        assert label
        assert game.runtime.refuse_reason(command) is None
        assert game.submit(command).accepted


# ----------------------------------------------------------------------
# Counting
# ----------------------------------------------------------------------


def test_a_tally_counts_the_games_it_was_given(a_few: list) -> None:
    tally = Tally()

    for outcome in a_few:
        tally.add(outcome.journal)

    assert tally.games == len(a_few)
    assert tally.finished == sum(1 for outcome in a_few if outcome.finished)
    assert sum(tally.wins_by_seat.values()) == tally.finished


def test_the_counting_matches_the_journals(a_few: list) -> None:
    """
    Every number is a count of what was written down, so it can be recounted.
    """
    tally = Tally()

    for outcome in a_few:
        tally.add(outcome.journal)

    events = sum(
        len(entry.events)
        for outcome in a_few
        for entry in outcome.journal.entries
    )

    assert sum(tally.events.values()) == events
    assert tally.commands == sum(len(outcome.journal) for outcome in a_few)

    deaths = sum(
        1
        for outcome in a_few
        for entry in outcome.journal.entries
        for event in entry.events
        if event.type == "player_died"
    )

    assert tally.deaths == deaths


def test_characters_are_counted_by_the_seat_that_played_them(a_few: list) -> None:
    tally = Tally()

    for outcome in a_few:
        tally.add(outcome.journal)

    assert tally.characters

    played = sum(seen.games for seen in tally.characters.values())

    assert played == sum(len(outcome.journal.characters) for outcome in a_few)

    wins = sum(seen.wins for seen in tally.characters.values())

    assert wins == tally.finished


def test_a_thing_never_measured_has_no_average(a_few: list) -> None:
    """
    A monster that was on the table from the deal never entered play, so its
    life was not measured — and an unmeasured life is not a life of zero.
    """
    tally = Tally()

    for outcome in a_few:
        tally.add(outcome.journal)

    unmeasured = [seen for seen in tally.monsters.values() if not seen.measured]

    assert unmeasured, "some monsters were dealt onto the board, not revealed"
    assert all(seen.average_turns() is None for seen in unmeasured)


def test_an_empty_tally_claims_nothing() -> None:
    tally = Tally()

    assert tally.games == 0
    assert tally.average_turns() is None
    assert tally.hit_rate() is None
    assert "Nothing was played" in report(tally)


def test_a_tally_is_plain_data(a_few: list) -> None:
    tally = Tally()

    for outcome in a_few:
        tally.add(outcome.journal)

    written = tally.to_dict()

    assert json.loads(json.dumps(written)) == written


def test_the_report_says_what_it_knows_and_no_more(a_few: list) -> None:
    tally = Tally()

    for outcome in a_few:
        tally.add(outcome.journal)

    told = report(tally, top=5)

    assert f"{len(a_few)} games" in told
    assert "Characters" in told
    assert "Monsters" in told

    # The one claim that must never be overstated.
    assert "a correlation, not the card's doing" in told


# ----------------------------------------------------------------------
# On more than one core
# ----------------------------------------------------------------------


def test_the_same_run_split_across_cores_gives_the_same_numbers(
    everything: ContentLibrary,
) -> None:
    """
    The property the whole idea of a parallel run rests on.
    """
    from fsme.simulation import run_on_many_cores

    alone = Tally()

    for outcome in run(everything, 6, 2):
        alone.add(outcome.journal)

    together = Tally()

    for done in run_on_many_cores(CONTENT_ROOT, 6, 2, jobs=3):
        together.merge(done.tally)

    assert together.to_dict() == alone.to_dict()


def test_a_game_that_falls_over_is_counted_rather_than_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A run of a thousand games must not be lost to one of them.
    """
    from fsme.simulation import pool

    monkeypatch.setattr(pool, "_library", object())

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("the table caught fire")

    monkeypatch.setattr(pool, "play_one", explode)

    done = pool._one((7, 2, 10, None, False, ()))

    assert done.seed == 7
    assert done.finished is False
    assert "the table caught fire" in done.broke
    assert done.tally.games == 0


# ----------------------------------------------------------------------
# Comparing two runs
# ----------------------------------------------------------------------


def make_tally(games: int, turns_each: int, deaths_each: int = 1) -> Tally:
    tally = Tally()

    tally.games = games
    tally.finished = games
    tally.turns = turns_each * games
    tally.commands = turns_each * games * 4
    tally.deaths = deaths_each * games

    return tally


def test_a_difference_within_the_noise_is_not_offered_as_a_finding() -> None:
    from fsme.analysis import compare

    told = compare(
        "a card",
        make_tally(50, 100),
        make_tally(50, 101),
        appeared=40,
    )

    turns = next(d for d in told.differences if d.name == "turns a game")

    assert turns.change == pytest.approx(-1.0)
    assert not turns.tells_us_anything


def test_a_difference_well_beyond_the_noise_is() -> None:
    from fsme.analysis import compare

    told = compare(
        "a card",
        make_tally(200, 100),
        make_tally(200, 140),
        appeared=150,
    )

    turns = next(d for d in told.differences if d.name == "turns a game")

    assert turns.tells_us_anything
    assert told.can_be_about_the_card


def test_a_card_that_never_reached_the_table_explains_nothing() -> None:
    """
    Removing a card reshuffles every game, so two runs differ everywhere.
    """
    from fsme.analysis import compare, read_out

    told = compare(
        "a card",
        make_tally(200, 100),
        make_tally(200, 140),
        appeared=2,
    )

    assert not told.can_be_about_the_card

    reading = read_out(told)

    assert "too rarely" in reading
    assert "Nothing is marked" in reading
    assert "*" not in reading.split("Nothing is marked")[0].split("change")[1]


def test_a_comparison_is_plain_data() -> None:
    from fsme.analysis import compare

    told = compare("a card", make_tally(10, 50), make_tally(10, 60), appeared=8)

    written = told.to_dict()

    assert json.loads(json.dumps(written)) == written


def test_a_library_can_be_asked_for_itself_without_a_card(
    everything: ContentLibrary,
) -> None:
    card = "treasure_deck-active_items-base_game-guppy_s_paw"

    smaller = everything.without([card])

    assert card in {definition.id for definition in everything.definitions()}
    assert card not in {definition.id for definition in smaller.definitions()}
    assert len(smaller.definitions()) == len(everything.definitions()) - 1

    # And the library that was asked keeps its own answer.
    assert card in {definition.id for definition in everything.definitions()}
