"""
Two fingerprints in one record.

A journal and a recording hold the cheap digest after every command, as they
always have, and the full one after every eighth command and after the last.
The cheap one places a difference at the command; the full one sees what the
cheap one does not, and places a difference only between the last full check
that matched and the first that did not. This file holds both halves to that,
and holds the formats that came before to what they always meant.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_digest_completeness import COLLISIONS, a_table
from test_replay import build_state, record_a_game

from fsme.api import load_content
from fsme.cards import CardInstance
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.journal import Journal, JournalFormatError, replay_journal, summarise
from fsme.lab.analysis import risks
from fsme.lab.bot import HeuristicBot
from fsme.lab.simulation import play_one
from fsme.lab.simulation.runner import _whose_move
from fsme.replay import (
    Recorder,
    Recording,
    ReplayDivergence,
    ReplayFormatError,
    ReplayPlayer,
    replay,
)
from fsme.replay.digest import (
    FULL_DIGEST_EVERY,
    full_checkpoint,
    state_digest,
    state_digest_v2,
)
from fsme.state import GameState

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture(scope="module")
def finished(everything: ContentLibrary) -> Journal:
    """
    A finished game whose last command is not itself an eighth.

    Played on RNG model 1, so that its journal is the format 3 journal the
    tests below rewrite into the formats that came before it.
    """
    for seed in range(40):
        journal, game = play_one(everything, seed, 2, rng_model="1")

        if game.is_over and not full_checkpoint(len(journal) - 1) and len(journal) > 24:
            return journal

    raise AssertionError("no finished game ended between two full checks")


def copied(journal: Journal) -> Journal:
    return Journal.from_dict(journal.to_dict())


def respoiled(journal: Journal, index: int, **change: str) -> Journal:
    spoiled = copied(journal)
    spoiled.entries[index] = replace(spoiled.entries[index], **change)

    return spoiled


# ----------------------------------------------------------------------
# Where the full digest is written
# ----------------------------------------------------------------------


def test_the_interval_is_eight() -> None:
    assert FULL_DIGEST_EVERY == 8
    assert [index for index in range(32) if full_checkpoint(index)] == [7, 15, 23, 31]


def test_a_journal_holds_the_full_digest_every_eighth_entry_and_at_the_last(
    finished: Journal,
) -> None:
    last = len(finished) - 1

    for entry in finished.entries:
        expected = full_checkpoint(entry.index) or entry.index == last

        assert bool(entry.full_digest) is expected, entry.index
        assert entry.digest, entry.index


def test_the_last_position_of_a_finished_game_is_checked_in_full_whatever_its_index(
    finished: Journal,
) -> None:
    last = finished.entries[-1]

    assert not full_checkpoint(last.index)
    assert last.full_digest


def test_a_journal_writes_format_three_and_keeps_its_full_digests(finished: Journal) -> None:
    written = finished.to_dict()

    assert written["format"] == "3"
    assert "full_digest" in written["entries"][7]
    assert "full_digest" not in written["entries"][6]
    assert [entry.full_digest for entry in copied(finished).entries] == [
        entry.full_digest for entry in finished.entries
    ]


def test_a_game_that_never_finished_has_no_full_digest_past_its_last_eighth(
    everything: ContentLibrary,
) -> None:
    journal, game = play_one(everything, 3, 2, steps=21)

    assert not game.is_over
    assert [entry.index for entry in journal.entries if entry.full_digest] == [7, 15]


# ----------------------------------------------------------------------
# Replaying a journal
# ----------------------------------------------------------------------


def test_a_finished_journal_replays_checked_in_full_to_its_end(
    everything: ContentLibrary, finished: Journal
) -> None:
    playback = replay_journal(finished, everything)

    assert playback.faithful, str(playback.divergence)
    assert playback.replayed == len(finished)
    assert playback.fully_checked == len(finished)
    assert summarise(playback, finished)["fully_checked"] == len(finished)


def test_the_cheap_digest_still_names_the_command(
    everything: ContentLibrary, finished: Journal
) -> None:
    playback = replay_journal(respoiled(finished, 10, digest="0" * 32), everything)

    assert playback.divergence is not None
    assert playback.divergence.index == 10
    assert playback.divergence.after is None
    assert playback.replayed == 11
    assert playback.fully_checked == 8


def test_a_full_mismatch_is_placed_between_two_full_checks_and_no_nearer(
    everything: ContentLibrary, finished: Journal
) -> None:
    playback = replay_journal(respoiled(finished, 15, full_digest="0" * 32), everything)

    assert not playback.faithful
    assert playback.divergence is not None
    assert playback.divergence.index == 15
    assert playback.divergence.after == 7
    assert playback.replayed == 16
    assert playback.fully_checked == 8
    assert "one of entries 8 to 15" in str(playback.divergence)


def test_a_full_mismatch_at_the_first_full_check_reaches_back_to_the_start(
    everything: ContentLibrary, finished: Journal
) -> None:
    playback = replay_journal(respoiled(finished, 7, full_digest="0" * 32), everything)

    assert playback.divergence is not None
    assert playback.divergence.after == -1
    assert playback.fully_checked == 0
    assert "one of entries 0 to 7" in str(playback.divergence)


def test_an_entry_without_a_full_digest_is_not_a_gap(
    everything: ContentLibrary, finished: Journal
) -> None:
    bare = copied(finished)
    bare.entries = [replace(entry, full_digest="") for entry in bare.entries]

    playback = replay_journal(bare, everything)

    assert playback.faithful, str(playback.divergence)
    assert playback.replayed == len(finished)
    assert playback.fully_checked == 0


def test_stopping_between_two_full_checks_says_how_far_each_was_checked(
    everything: ContentLibrary, finished: Journal
) -> None:
    playback = replay_journal(finished, everything, stop_at=12)

    assert playback.faithful
    assert playback.replayed == 12
    assert playback.fully_checked == 8


@pytest.mark.parametrize("version", ["1", "2"])
def test_a_journal_in_an_older_format_is_checked_by_the_cheap_digest_alone(
    everything: ContentLibrary, finished: Journal, version: str
) -> None:
    old: dict[str, Any] = finished.to_dict()
    old["format"] = version

    for entry in old["entries"]:
        entry.pop("full_digest", None)

    playback = replay_journal(Journal.from_dict(old), everything)

    assert playback.faithful, str(playback.divergence)
    assert playback.replayed == len(finished)
    assert playback.fully_checked == 0


def test_a_journal_in_a_later_format_is_refused(finished: Journal) -> None:
    ahead = finished.to_dict()
    ahead["format"] = "5"

    with pytest.raises(JournalFormatError):
        Journal.from_dict(ahead)


# ----------------------------------------------------------------------
# Weighing the moves of a game
# ----------------------------------------------------------------------


def test_moves_weighed_after_the_last_full_match_are_taken_back(
    everything: ContentLibrary, finished: Journal
) -> None:
    whole = risks(finished, everything)
    told = risks(respoiled(finished, 15, full_digest="0" * 32), everything)

    assert whole.faithful
    assert not told.faithful

    kept = told.worst + told.riskiest + told.best

    assert all(risk.index <= 7 for risk in kept)
    assert told.weighed + told.skipped == 8
    assert told.forced <= told.weighed


# ----------------------------------------------------------------------
# Recordings
# ----------------------------------------------------------------------

PLAYERS = ["Ann", "Bo"]
RECORDED_SEED = 5


def dealt(everything: ContentLibrary, change: Any = None) -> Any:
    """The position before the deal, built the same way every time."""
    def build() -> GameState:
        state = Game.from_content(
            everything, PLAYERS, seed=RECORDED_SEED, rng_model="1"
        ).state

        if change is not None:
            change(state)

        return state

    return build


@pytest.fixture(scope="module")
def recorded(everything: ContentLibrary) -> Recording:
    """
    Twenty-one commands of a real game: full checks at 7, 15 and the last.

    On RNG model 1, so the recording is format 2 and can be rewritten into the
    format before it.
    """
    game = Game.from_content(everything, PLAYERS, seed=RECORDED_SEED, rng_model="1")
    recorder = Recorder(game.runtime)
    assert recorder.submit(Command(type=CommandType.START_GAME, player=0)).accepted

    bot = HeuristicBot(RECORDED_SEED)

    while len(recorder) < 21:
        thought = bot.choose(game, seats=(_whose_move(game),))
        assert thought is not None
        recorder.submit(thought[0])

    return recorder.recording()


def played_back(
    recording: Recording, everything: ContentLibrary, change: Any = None
) -> ReplayPlayer:
    return ReplayPlayer(recording, dealt(everything, change), cards=everything.registry())


def test_a_recording_holds_the_full_digest_every_eighth_command_and_at_the_last(
    recorded: Recording,
) -> None:
    assert recorded.format_version == "2"
    assert [index for index, command in enumerate(recorded.commands) if command.full_digest] == [
        7, 15, 20,
    ]
    assert all(command.digest for command in recorded.commands)


def test_the_last_recorded_command_is_checked_in_full_whatever_its_index() -> None:
    _, recording = record_a_game()

    assert [bool(command.full_digest) for command in recording.commands] == [
        False, False, False, True,
    ]


def test_sealing_twice_gives_the_same_recording() -> None:
    recorder, first = record_a_game()

    assert recorder.recording() == first


def test_a_recording_replays_checked_in_full_to_its_end(
    recorded: Recording, everything: ContentLibrary
) -> None:
    player = played_back(recorded, everything)
    player.play()

    assert player.finished
    assert player.position == len(recorded)
    assert player.fully_checked == len(recorded)


def test_a_recording_between_two_full_checks_says_how_far_each_was_checked(
    recorded: Recording, everything: ContentLibrary
) -> None:
    player = played_back(recorded, everything)

    for _ in range(12):
        assert player.step()

    assert player.position == 12
    assert player.fully_checked == 8


def test_a_full_mismatch_in_a_recording_is_placed_between_two_full_checks(
    recorded: Recording, everything: ContentLibrary
) -> None:
    commands = list(recorded.commands)
    commands[15] = replace(commands[15], full_digest="0" * 32)
    broken = Recording(seed=recorded.seed, commands=tuple(commands)).sealed()

    player = played_back(broken, everything)

    with pytest.raises(ReplayDivergence) as raised:
        player.play()

    assert player.position == 15
    assert player.fully_checked == 8
    assert "full check at command 15" in str(raised.value)
    assert "one of commands 8 to 15" in str(raised.value)


def test_a_recording_in_format_one_is_checked_by_the_cheap_digest_alone(
    recorded: Recording, everything: ContentLibrary
) -> None:
    commands = tuple(replace(command, full_digest="") for command in recorded.commands)
    old = Recording(seed=recorded.seed, commands=commands, format_version="1").sealed()

    assert all("full_digest" not in command.to_dict() for command in old.commands)

    player = played_back(Recording.from_dict(old.to_dict()), everything)
    player.play()

    assert player.finished
    assert player.fully_checked == 0


def test_a_recording_in_a_later_format_is_refused(recorded: Recording) -> None:
    later = Recording(seed=recorded.seed, commands=recorded.commands, format_version="4").sealed()

    with pytest.raises(ReplayFormatError):
        replay(later, build_state)


# ----------------------------------------------------------------------
# What the full digest is there to see
# ----------------------------------------------------------------------


@pytest.mark.parametrize("difference", sorted(COLLISIONS))
def test_the_full_digest_tells_apart_what_the_cheap_one_cannot(difference: str) -> None:
    one, other = a_table(), a_table()
    COLLISIONS[difference](other)

    assert state_digest(one) == state_digest(other)
    assert state_digest_v2(one) != state_digest_v2(other)


def with_a_hidden_difference(change: Any) -> Any:
    """The starting position, changed in a way the cheap digest cannot see."""
    def build() -> GameState:
        state = build_state()
        change(state)

        return state

    return build


def counters_on_the_bottom_loot_card(state: GameState) -> None:
    card = state.loot_deck.cards[0]
    assert isinstance(card, CardInstance)
    card.counters["charge"] = 1


def test_a_hidden_difference_that_lasts_is_found_at_the_next_full_check(
    recorded: Recording, everything: ContentLibrary
) -> None:
    player = played_back(recorded, everything, counters_on_the_bottom_loot_card)

    for _ in range(7):
        assert player.step()

    with pytest.raises(ReplayDivergence) as raised:
        player.step()

    assert player.position == 7
    assert "one of commands 0 to 7" in str(raised.value)


def test_a_hidden_difference_gone_before_the_next_full_check_is_not_seen() -> None:
    """
    The limit the full digest every eighth command was accepted with: an attack
    that has gone two rounds without a hit is a difference neither digest can
    have seen once the attack at command 3, the last of this recording, has
    started over.
    """
    _, recording = record_a_game()

    def stalled(state: GameState) -> None:
        state.combat.stalled_rounds = 2

    player = replay(recording, with_a_hidden_difference(stalled))

    assert player.finished
    assert player.fully_checked == len(recording)
