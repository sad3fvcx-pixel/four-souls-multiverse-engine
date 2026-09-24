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
from typing import Any

import pytest

from fsme.api import load_content
from fsme.content import ContentLibrary
from fsme.journal import Journal
from fsme.lab.analysis import Risks, risks
from fsme.lab.analysis.risk import WORTH_MENTIONING
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
    from fsme.lab.analysis import explain, summarise

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


# ----------------------------------------------------------------------
# A replay that comes out differently is not weighed as if it had not
# ----------------------------------------------------------------------


def _rewritten(journal: Journal, change: Any) -> Journal:
    """
    The journal as a file would hold it, with one change made to the entries.
    """
    data = journal.to_dict()
    change(data["entries"])

    return Journal.from_dict(data)


SPOILED = 40


def _spoiled(entries: list[dict[str, Any]]) -> None:
    entries[SPOILED]["digest"] = "not the fingerprint this command produced"


def _refused(entries: list[dict[str, Any]], players: int = 3) -> None:
    for entry in entries:
        if entry["command"] in ("end_phase", "end_turn"):
            entry["player"] = (int(entry["player"]) + 1) % players

            return

    raise AssertionError("no command in this game that only the active player gives")


def test_a_position_that_no_longer_matches_stops_the_weighing(
    a_journal: Journal, everything: ContentLibrary
) -> None:
    """
    Every command was accepted, so a check on refusals alone passed this and
    went on weighing a different game under this one's name.
    """
    told = risks(_rewritten(a_journal, _spoiled), everything, top=3)

    assert not told.faithful
    assert told.weighed + told.skipped == SPOILED + 1, "nothing after it is looked at"
    assert told.weighed > 0, "what came before it was weighed as it was"

    for found in (*told.riskiest, *told.worst, *told.best):
        assert found.index <= SPOILED, found


def test_a_refused_command_still_stops_the_weighing(
    a_journal: Journal, everything: ContentLibrary
) -> None:
    journal = _rewritten(a_journal, _refused)
    at = next(
        entry.index
        for entry, original in zip(journal.entries, a_journal.entries, strict=True)
        if entry.player != original.player
    )

    told = risks(journal, everything, top=3)

    assert not told.faithful
    assert told.weighed + told.skipped == at + 1


@pytest.mark.parametrize("players", [2, 4])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_a_game_that_replays_is_never_called_one_that_did_not(
    everything: ContentLibrary, seed: int, players: int
) -> None:
    """
    The fingerprint holds the random generator's state and the number of events,
    so matching it at every command is also proof that weighing a move left no
    trace in the game it was weighed in.
    """
    journal, _ = play_one(everything, seed=seed, players=players, thinking_seats=(0,))

    told = risks(journal, everything, top=3)

    assert told.faithful
    assert told.weighed + told.skipped == len(journal.entries)
