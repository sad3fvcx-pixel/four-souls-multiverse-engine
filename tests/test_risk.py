"""
Decisions held against a yardstick, and the yardstick kept honest.

The danger in this module is not arithmetic, it is wording: a bot that looks
one move ahead disagreeing with a player is not a player making a mistake. So
the tests check that the disagreement is measured against what the engine
actually offered, that a forced move is never counted as a decision, that a
seat the bot itself played cannot be scored against it, and that the report
names the bot doing the judging.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsme.analysis import Risks, risks
from fsme.analysis.risk import WORTH_MENTIONING
from fsme.api import load_content
from fsme.content import ContentLibrary
from fsme.journal import Journal
from fsme.simulation import play_one

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture(scope="module")
def a_journal(everything: ContentLibrary) -> Journal:
    journal, _ = play_one(everything, seed=7, players=3, thinking_seats=(0,))

    return journal


@pytest.fixture(scope="module")
def weighed(a_journal: Journal, everything: ContentLibrary) -> Risks:
    return risks(a_journal, everything, top=3)


def test_the_replay_reproduces_the_game_it_is_judging(weighed: Risks) -> None:
    # Every number in the report is taken from a position the replay rebuilt.
    # If the replay diverged, the report would be about a different game.
    assert weighed.faithful

    assert weighed.weighed > 0
    assert weighed.weighed + weighed.skipped > 0


def test_the_yardstick_is_named(weighed: Risks) -> None:
    assert weighed.by == "heuristic-1"


def test_a_forced_move_is_never_called_a_decision(weighed: Risks) -> None:
    assert weighed.forced >= 0

    for risk in weighed.worst + weighed.riskiest:
        assert risk.was_a_choice
        assert risk.considered > 1


def test_the_bot_cannot_be_scored_against_itself(
    a_journal: Journal, everything: ContentLibrary
) -> None:
    told = risks(a_journal, everything, top=5, seat=0)

    assert told.bot_seats == (0,)

    # Seat 0 was the bot. It always played what it scored highest, so there is
    # nothing for it to have played instead.
    assert all(risk.regret == 0.0 for risk in told.worst)
    assert told.worst == []


def test_a_disagreement_is_the_gap_between_two_moves_on_offer(
    weighed: Risks,
) -> None:
    for risk in weighed.worst:
        assert risk.regret >= WORTH_MENTIONING
        assert risk.best >= risk.taken
        assert risk.regret == pytest.approx(risk.best - risk.taken)
        assert risk.instead


def test_the_dangers_are_the_reasons_that_counted_against_the_move(
    weighed: Risks,
) -> None:
    for risk in weighed.riskiest:
        assert risk.dangers
        assert all(danger.worth < 0 for danger in risk.dangers)


def test_the_same_move_made_twice_is_one_finding(weighed: Risks) -> None:
    # A player who walks into the same monster nine times has done one thing
    # nine times. Three rows of it would hide the other two findings.
    seen = [(risk.player, risk.label) for risk in weighed.riskiest]

    assert len(seen) == len(set(seen))
    assert all(risk.times >= 1 for risk in weighed.riskiest)


def test_only_one_seat_is_weighed_when_one_is_asked_for(
    a_journal: Journal, everything: ContentLibrary
) -> None:
    told = risks(a_journal, everything, top=5, seat=1)

    assert all(risk.player == 1 for risk in told.worst + told.riskiest)


def test_a_game_nobody_played_weighs_nothing(
    everything: ContentLibrary,
) -> None:
    told = risks(Journal(seed=1, players=("Ann", "Bo")), everything)

    assert told.weighed == 0
    assert told.worst == []
    assert told.riskiest == []


def test_the_report_calls_it_a_disagreement_and_not_a_mistake(
    a_journal: Journal, weighed: Risks
) -> None:
    from fsme.analysis import explain, summarise

    told = explain(summarise(a_journal), dangers=weighed)

    assert "The decisions" in told
    assert "not a proven mistake" in told
    assert "heuristic-1" in told


def test_the_risks_are_plain_data(weighed: Risks) -> None:
    written = weighed.to_dict()

    assert written["by"] == weighed.by
    assert written["faithful"] is True

    for risk in written["worst"]:
        assert set(risk) >= {"regret", "taken", "best", "instead", "times"}
