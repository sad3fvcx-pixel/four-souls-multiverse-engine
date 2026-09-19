"""
The analytical layer.

Everything here reads journals and says something about them, and the risk is
always the same: saying more than the record supports. So the tests are mostly
about restraint — that a number is a count of something recorded, that a
correlation is not dressed as a cause, and that a table thin enough to be
meaningless says so.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fsme.api import load_content
from fsme.content import ContentLibrary
from fsme.lab.analysis import (
    GameSummary,
    SeatFacts,
    Tally,
    explain,
    study,
    summarise,
    written,
)
from fsme.lab.analysis.study import SEEN_AT_LEAST, TOGETHER_AT_LEAST
from fsme.lab.simulation import play_one

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture(scope="module")
def a_game(everything: ContentLibrary) -> GameSummary:
    journal, _ = play_one(everything, seed=3, players=3, thinking_seats=(0,))

    return summarise(journal)


@pytest.fixture(scope="module")
def some_games(everything: ContentLibrary) -> list[GameSummary]:
    return [
        summarise(play_one(everything, seed=seed, players=3)[0])
        for seed in range(8)
    ]


# ----------------------------------------------------------------------
# One game, reduced
# ----------------------------------------------------------------------


def test_a_summary_counts_what_the_journal_recorded(
    everything: ContentLibrary,
) -> None:
    journal, _ = play_one(everything, seed=3, players=3)

    summary = summarise(journal)

    assert summary.seed == 3
    assert summary.players == 3
    assert summary.commands == len(journal)

    moves = sum(seat.moves for seat in summary.seats)

    assert moves == len(journal), "every command belongs to a seat"

    deaths = sum(
        1
        for entry in journal.entries
        for event in entry.events
        if event.type == "player_died"
        and event.controller is not None
    )

    assert sum(seat.deaths for seat in summary.seats) == deaths


def test_a_summary_says_where_the_souls_came_from(a_game: GameSummary) -> None:
    """
    A game won on monsters and a game won on cards are different games.
    """
    winner = a_game.winning_seat

    assert winner is not None
    assert winner.souls == sum(winner.souls_from.values())
    assert set(winner.souls_from) <= {"monster", "card", "unnamed"}
    assert "monster" in winner.souls_from, "these were earned by fighting"


def test_a_summary_is_much_smaller_than_the_journal_it_came_from(
    everything: ContentLibrary,
) -> None:
    """
    The reason the whole layer works over ten thousand games.
    """
    journal, _ = play_one(everything, seed=5, players=2)

    summary = len(json.dumps(summarise(journal).to_dict()))
    whole = len(json.dumps(journal.to_dict()))

    assert summary * 20 < whole


def test_a_summary_is_plain_data(a_game: GameSummary) -> None:
    written_out = a_game.to_dict()

    assert json.loads(json.dumps(written_out)) == written_out


# ----------------------------------------------------------------------
# One game, explained
# ----------------------------------------------------------------------


def test_a_game_is_explained_as_an_account(a_game: GameSummary) -> None:
    told = explain(a_game)

    assert f"Game {a_game.seed}" in told
    assert "won as" in told
    assert "Their souls:" in told

    # The caution is not optional wording.
    assert "may simply have gone with it" in told or "dice decided it" in told


def test_an_unfinished_game_is_explained_as_unfinished() -> None:
    summary = GameSummary(seed=1, players=2, finished=False, winner=None)
    summary.seats = [SeatFacts(seat=0, name="Ann"), SeatFacts(seat=1, name="Bo")]

    told = explain(summary)

    assert "Nobody won" in told


def test_a_winner_who_did_nothing_special_is_told_so() -> None:
    """
    One game can be won by the player the dice favoured, and the account says
    so rather than inventing a reason.
    """
    summary = GameSummary(seed=1, players=2, finished=True, winner=0, turns=10)
    summary.seats = [
        SeatFacts(seat=0, name="Ann", won=True, souls=4, kills=2, moves=10),
        SeatFacts(seat=1, name="Bo", souls=3, kills=2, moves=10),
    ]

    told = explain(summary)

    assert "nothing the rest of the table did not do" in told
    assert "dice decided it" in told


# ----------------------------------------------------------------------
# Many games, studied
# ----------------------------------------------------------------------


def test_a_study_compares_winners_with_everybody_else(
    some_games: list[GameSummary],
) -> None:
    told = study(some_games)

    assert told.games == len(some_games)
    assert told.splits

    kills = next(split for split in told.splits if split.what == "monsters killed")

    assert kills.winners > 0
    assert kills.error is not None


def test_a_study_never_calls_a_correlation_a_cause(
    some_games: list[GameSummary],
) -> None:
    reading = written(study(some_games))

    assert "went with winning" in reading
    assert "symptoms" in reading
    assert "caused by" not in reading


def test_a_pair_nobody_saw_often_is_not_printed() -> None:
    """
    Two cards seen together twice will show a winrate of 100% and mean nothing.
    """
    summaries = []

    for seed in range(3):
        summary = GameSummary(seed=seed, players=2, finished=True, winner=0)
        summary.seats = [
            SeatFacts(seat=0, name="Ann", won=True, cards_used={"a", "b"}),
            SeatFacts(seat=1, name="Bo", cards_used={"c"}),
        ]
        summaries.append(summary)

    told = study(summaries)

    assert told.pairs == [], f"three games is under the floor of {TOGETHER_AT_LEAST}"


def test_a_pair_seen_often_enough_is_reported_with_its_lift() -> None:
    summaries = []

    for seed in range(10):
        summary = GameSummary(seed=seed, players=2, finished=True, winner=0)
        summary.seats = [
            SeatFacts(seat=0, name="Ann", won=True, cards_used={"a", "b"}),
            SeatFacts(seat=1, name="Bo", cards_used={"c"}),
        ]
        summaries.append(summary)

    told = study(summaries)

    assert len(told.pairs) == 1

    pair = told.pairs[0]

    assert (pair.one, pair.other) == ("a", "b")
    assert pair.together == 10
    assert pair.rate == 1.0
    assert pair.lift is not None and pair.lift > 1


def test_the_pairs_table_says_it_is_a_hypothesis(
    some_games: list[GameSummary],
) -> None:
    reading = written(study(some_games))

    assert "hypothesis" in reading
    assert "not a synergy" in reading


def test_an_unfinished_game_is_flagged_for_a_look() -> None:
    summary = GameSummary(seed=42, players=2, finished=False, commands=6000)
    summary.seats = [SeatFacts(seat=0, name="Ann"), SeatFacts(seat=1, name="Bo")]

    told = study([summary])

    assert [oddity.rule for oddity in told.oddities] == ["unfinished"]
    assert told.oddities[0].seed == 42


def test_a_winner_who_never_fought_is_flagged() -> None:
    summary = GameSummary(seed=7, players=2, finished=True, winner=0, turns=20)
    summary.seats = [
        SeatFacts(seat=0, name="Ann", won=True, souls=4, kills=0),
        SeatFacts(seat=1, name="Bo", kills=3),
    ]

    told = study([summary])

    assert any(oddity.rule == "won without fighting" for oddity in told.oddities)


def test_every_oddity_names_the_rule_and_the_seed(
    some_games: list[GameSummary],
) -> None:
    """
    A flag a reader cannot check is a flag a reader cannot dismiss.
    """
    told = study(some_games)

    for oddity in told.oddities:
        assert oddity.rule
        assert oddity.saying
        assert isinstance(oddity.seed, int)


def test_a_study_of_nothing_says_nothing() -> None:
    told = study([])

    assert told.games == 0
    assert "Nothing to study" in written(told)


def test_a_study_is_plain_data(some_games: list[GameSummary]) -> None:
    told = study(some_games).to_dict()

    assert json.loads(json.dumps(told)) == told


def test_the_bot_section_appears_only_when_a_bot_played(
    everything: ContentLibrary, some_games: list[GameSummary]
) -> None:
    assert "The bot" not in written(study(some_games))

    thought = [
        summarise(play_one(everything, seed=seed, players=3, thinking_seats=(0,))[0])
        for seed in range(3)
    ]

    reading = written(study(thought))

    assert "The bot" in reading
    assert "seats played" in reading


def test_a_player_only_ever_plays_their_own_moves(
    everything: ContentLibrary,
) -> None:
    """
    The engine offers every legal move at the table, including cards other
    players may respond with. A table where everybody plays everybody's cards
    is not a table anyone can be compared at.
    """
    journal, _ = play_one(everything, seed=11, players=3, thinking_seats=(0,))

    thought = [entry for entry in journal.entries if entry.decision]

    assert thought
    assert all(entry.player == 0 for entry in thought), (
        "the bot decided a move belonging to another seat"
    )


# ----------------------------------------------------------------------
# What to measure next
# ----------------------------------------------------------------------


def _seat(seat: int, *, won: bool, cards: set[str]) -> SeatFacts:
    return SeatFacts(seat=seat, name=f"P{seat}", won=won, cards_used=cards)


def _table(rows: list[tuple[bool, set[str]]], seed: int = 0) -> GameSummary:
    return GameSummary(
        seed=seed,
        players=len(rows),
        finished=any(won for won, _ in rows),
        winner=next(
            (seat for seat, (won, _) in enumerate(rows) if won), None
        ),
        seats=[
            _seat(seat, won=won, cards=cards)
            for seat, (won, cards) in enumerate(rows)
        ],
    )


def test_a_card_that_really_does_win_is_picked_out() -> None:
    """
    The rule has to fire on something, or the correction has eaten the signal
    along with the confound.
    """
    games = [
        _table(
            [
                (True, {"good", f"filler{seed}a", "common"}),
                (False, {"dull", f"filler{seed}b", "common"}),
                (False, {"dull", f"filler{seed}c", "common"}),
            ],
            seed=seed,
        )
        for seed in range(40)
    ]

    told = study(games)

    named = {suspect.card for suspect in told.suspects}

    assert "good" in named
    assert all(suspect.seats >= SEEN_AT_LEAST for suspect in told.suspects)


def test_a_card_only_the_busy_seats_used_is_not_called_a_winner() -> None:
    """
    The confound this section exists to survive.

    Nothing about ``late`` wins a game: it is used by whoever took the most
    turns, and whoever takes the most turns is whoever is winning. Compared
    against the whole table it looks like the best card in the deck; compared
    against seats that were equally busy it is nothing at all.
    """
    games = [
        _table(
            [
                (True, {f"a{seed}", f"b{seed}", f"c{seed}", "late"}),
                (False, {f"d{seed}"}),
                (False, {f"e{seed}"}),
            ],
            seed=seed,
        )
        for seed in range(40)
    ]

    told = study(games)

    assert "late" not in {suspect.card for suspect in told.suspects}


def test_a_card_hardly_anybody_used_is_never_suspected() -> None:
    games = [
        _table(
            [
                (True, {"rare"} if seed < 3 else {f"x{seed}"}),
                (False, {f"y{seed}"}),
            ],
            seed=seed,
        )
        for seed in range(30)
    ]

    told = study(games)

    assert "rare" not in {suspect.card for suspect in told.suspects}


def test_every_suspect_carries_the_command_that_would_settle_it(
    some_games: list[GameSummary],
) -> None:
    told = study(some_games)

    for suspect in told.suspects:
        assert suspect.command.startswith(f"fsme test-card {suspect.card}")
        assert suspect.rule
        assert suspect.saying


def test_the_section_says_its_own_rows_are_not_findings(
    some_games: list[GameSummary],
) -> None:
    reading = written(study(some_games))

    assert "Worth testing next" in reading
    assert "Nothing here is a finding" in reading


def test_a_verdict_says_what_a_card_test_found() -> None:
    from fsme.lab.analysis import Tally, compare

    told = compare(
        "Nothing (nothing)",
        Tally(games=20, finished=20),
        Tally(games=20, finished=20),
        appeared=0,
    )

    assert "never reached the table" in told.verdict
    assert told.told_us == ()

    scarce = compare(
        "Scarce (scarce)",
        Tally(games=20, finished=20),
        Tally(games=20, finished=20),
        appeared=1,
    )

    assert "too scarce to say" in scarce.verdict
    assert scarce.told_us == ()


# ----------------------------------------------------------------------
# How wide an error bar has to be
# ----------------------------------------------------------------------


def _run(turns: list[int]) -> Tally:
    """
    A tally of games with the given lengths and nothing else in them.
    """
    tally = Tally(games=len(turns), finished=len(turns))

    tally.turns = sum(turns)
    tally.turns_squared = sum(turn * turn for turn in turns)

    return tally


def test_the_interval_is_measured_rather_than_assumed() -> None:
    """
    The bug this exists to keep fixed.

    The earlier version took a per-game count's variance to equal its mean, as
    a Poisson count's does. Game lengths do not oblige, so the intervals came
    out several times too narrow and a forty-game card test announced an effect
    that a two-hundred-game test then reversed.
    """
    from fsme.lab.analysis import compare

    # Two runs with the same average and a spread far wider than that average
    # would imply: identical means, so the honest answer is "no difference".
    steady = _run([120] * 20)
    wild = _run([40, 200] * 10)

    assert steady.average_turns() == wild.average_turns() == 120

    told = compare("x (x)", steady, wild, appeared=20)

    turns = told.differences[0]

    assert turns.change == 0
    assert turns.error is not None

    # The spread of the wild run alone is about 80 turns, over 20 games that is
    # an error near 18 — not the 3.5 a Poisson assumption would have given.
    assert turns.error > 10


def test_a_spread_needs_more_than_one_game() -> None:
    assert Tally().spread_of(0, 0) is None
    assert _run([100]).spread_of(100, 10_000) is None

    spread = _run([100, 120]).spread_of(220, 100 * 100 + 120 * 120)

    assert spread is not None
    assert round(spread, 3) == round((2 * 10**2) ** 0.5, 3)


def test_the_squares_survive_being_added_up_across_processes() -> None:
    """
    A run is split across cores and added back; the spread must not care.
    """
    whole = _run([40, 200, 90, 130])

    halves = _run([40, 200])
    halves.merge(_run([90, 130]))

    assert halves.turns == whole.turns
    assert halves.turns_squared == whole.turns_squared
    assert halves.spread_of(halves.turns, halves.turns_squared) == whole.spread_of(
        whole.turns, whole.turns_squared
    )
