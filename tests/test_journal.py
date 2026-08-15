"""
The journal.

A replay says what was played. A journal says what was played, what else could
have been played, where the game stood at the time, and everything that
followed — and it has to say all of that without changing a thing about the
game it is describing.

Three claims are tested here, and they are the three the whole idea rests on.
A journal describes the game truthfully. Keeping one does not alter the game.
And a journal can be played back, loudly disagreeing at the first command whose
outcome no longer matches.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.api.moves import legal_moves
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.journal import (
    Journal,
    JournalFormatError,
    JournalKeeper,
    render,
    replay_journal,
    summarise,
)
from fsme.replay import state_digest

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


def scripted(
    library: ContentLibrary,
    seed: int = 3,
    players: int = 2,
    steps: int = 120,
    *,
    offers: bool = False,
) -> JournalKeeper:
    """
    Play a game through a keeper, the way the CLI does.
    """
    game = Game.from_content(
        library, ["Ann", "Bo", "Cy", "Di"][:players], seed=seed
    )

    game.start()

    keeper = JournalKeeper(
        game,
        offers=(
            (lambda played: [move["label"] for move in legal_moves(played)])
            if offers
            else None
        ),
    )

    rng = random.Random(seed)

    for _ in range(steps):
        if game.is_over:
            break

        decision = game.runtime.awaiting_decision

        if decision is not None:
            count = len(decision.options)
            lowest = max(0, min(decision.minimum, count))
            highest = max(lowest, min(decision.maximum, count))

            keeper.submit(
                Command(
                    type=CommandType.CHOOSE_TARGET,
                    player=decision.player,
                    payload={
                        "choices": rng.sample(
                            range(count), rng.randint(lowest, highest)
                        )
                        if count
                        else []
                    },
                ),
                label="answered",
            )

            continue

        moves = legal_moves(game)

        if not moves:
            break

        move = rng.choice(moves)

        keeper.submit(
            Command(
                type=CommandType(move["type"]),
                player=move["player"],
                payload=dict(move["payload"]),
            ),
            label=move["label"],
        )

    return keeper


def test_a_journal_records_every_accepted_command(
    everything: ContentLibrary,
) -> None:
    keeper = scripted(everything)

    assert len(keeper.journal) > 20

    for index, entry in enumerate(keeper.journal.entries):
        assert entry.index == index
        assert entry.command
        assert entry.digest, "each entry fingerprints the position it produced"


def test_a_refused_command_is_not_part_of_the_game(
    everything: ContentLibrary,
) -> None:
    """
    It changed nothing, so it is part of the session and not of the game.
    """
    keeper = scripted(everything, steps=10)

    before = len(keeper.journal)

    refused = keeper.submit(
        Command(type=CommandType.ATTACK, player=0, payload={"index": 99})
    )

    assert refused.rejected
    assert len(keeper.journal) == before


def test_keeping_a_journal_does_not_change_the_game(
    everything: ContentLibrary,
) -> None:
    """
    The claim that makes a journal usable at all: it observes and nothing more.
    """
    watched = scripted(everything, seed=11, steps=150)

    plain = Game.from_content(everything, ["Ann", "Bo"], seed=11)
    plain.start()

    for entry in watched.journal.entries:
        plain.submit(
            Command(
                type=CommandType(entry.command),
                player=entry.player,
                payload=dict(entry.payload),
            )
        )

    assert state_digest(plain.state) == state_digest(watched.game.state)


def test_a_journal_says_where_the_game_stood(everything: ContentLibrary) -> None:
    keeper = scripted(everything)

    first = keeper.journal.entries[0]

    assert first.before.turn >= 1
    assert first.before.phase
    assert first.before.waiting_kind in ("action", "priority", "decision")
    assert len(first.before.players) == 2
    assert "hp" in first.before.players[0]


def test_a_journal_can_record_what_else_was_possible(
    everything: ContentLibrary,
) -> None:
    keeper = scripted(everything, steps=40, offers=True)

    offered = [entry for entry in keeper.journal.entries if entry.offered]

    assert offered, "the alternatives were asked for and written down"
    assert any(len(entry.offered) > 1 for entry in offered)


def test_the_alternatives_are_left_out_unless_asked_for(
    everything: ContentLibrary,
) -> None:
    keeper = scripted(everything, steps=40)

    assert all(entry.offered == () for entry in keeper.journal.entries)


def test_a_journal_keeps_the_events_a_command_caused(
    everything: ContentLibrary,
) -> None:
    keeper = scripted(everything)

    told = [entry for entry in keeper.journal.entries if entry.events]

    assert told

    kinds = {event.type for entry in told for event in entry.events}

    assert "stack_push" in kinds


def test_a_finished_game_records_how_it_ended(everything: ContentLibrary) -> None:
    keeper = scripted(everything, seed=3, steps=4000)

    if not keeper.game.is_over:
        pytest.skip("this deal did not finish within the budget")

    assert keeper.journal.outcome["winner"] is not None
    assert keeper.journal.outcome["turns"] >= 1


def test_an_unfinished_game_says_so_by_saying_nothing(
    everything: ContentLibrary,
) -> None:
    keeper = scripted(everything, steps=20)

    assert keeper.journal.outcome == {}


# ----------------------------------------------------------------------
# On disk
# ----------------------------------------------------------------------


def test_a_journal_survives_a_round_trip(
    everything: ContentLibrary, tmp_path: Path
) -> None:
    keeper = scripted(everything, offers=True)

    written = keeper.journal.save(tmp_path / "party.json")
    back = Journal.load(written)

    assert back.to_dict() == keeper.journal.to_dict()


def test_a_journal_is_plain_data(everything: ContentLibrary) -> None:
    keeper = scripted(everything, steps=60)

    written = keeper.journal.to_dict()

    assert json.loads(json.dumps(written)) == written


def test_a_journal_from_another_format_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"format": "0", "entries": []}))

    with pytest.raises(JournalFormatError):
        Journal.load(path)


def test_something_that_is_not_a_journal_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "nonsense.json"
    path.write_text("this is not JSON at all")

    with pytest.raises(JournalFormatError):
        Journal.load(path)


# ----------------------------------------------------------------------
# Playing it back
# ----------------------------------------------------------------------


def test_a_journal_replays_into_the_same_game(everything: ContentLibrary) -> None:
    keeper = scripted(everything, seed=7, steps=200)

    playback = replay_journal(keeper.journal, everything)

    assert playback.faithful, str(playback.divergence)
    assert playback.replayed == len(keeper.journal)
    assert state_digest(playback.game.state) == state_digest(keeper.game.state)


def test_a_replay_can_stop_partway(everything: ContentLibrary) -> None:
    """
    A reader stepping through a game wants the position at any point, and the
    engine builds it rather than the file storing it.
    """
    keeper = scripted(everything, seed=7, steps=200)

    playback = replay_journal(keeper.journal, everything, stop_at=10)

    assert playback.replayed == 10
    assert playback.faithful


def test_a_tampered_journal_diverges_at_the_command_that_did_it(
    everything: ContentLibrary,
) -> None:
    """
    What a journal is for when an engine changes under it: the first entry
    that no longer holds is the change.
    """
    keeper = scripted(everything, seed=7, steps=120)

    journal = Journal.from_dict(keeper.journal.to_dict())

    spoiled = 5
    entries = journal.entries
    entries[spoiled] = type(entries[spoiled])(
        **{
            **{
                field: getattr(entries[spoiled], field)
                for field in (
                    "index",
                    "command",
                    "player",
                    "payload",
                    "label",
                    "before",
                    "offered",
                    "events",
                )
            },
            "digest": "not the fingerprint this command produced",
        }
    )

    playback = replay_journal(journal, everything)

    assert not playback.faithful
    assert playback.divergence is not None
    assert playback.divergence.index == spoiled
    assert playback.replayed == spoiled + 1


def test_a_summary_says_how_the_playback_went(everything: ContentLibrary) -> None:
    keeper = scripted(everything, seed=7, steps=80)

    told = summarise(replay_journal(keeper.journal, everything), keeper.journal)

    assert told["faithful"] is True
    assert told["replayed"] == len(keeper.journal)
    assert told["divergence"] is None


# ----------------------------------------------------------------------
# Reading it
# ----------------------------------------------------------------------


def test_a_journal_reads_as_a_game(everything: ContentLibrary) -> None:
    keeper = scripted(everything, seed=3, steps=150, offers=True)

    told = render(keeper.journal)

    assert "FSME journal" in told
    assert "Turn 1" in told
    assert "could have:" in told
    assert "did:" in told


def test_the_reading_leaves_out_the_housekeeping_unless_asked(
    everything: ContentLibrary,
) -> None:
    keeper = scripted(everything, seed=3, steps=150)

    quiet = render(keeper.journal)
    everything_said = render(keeper.journal, full=True)

    assert "stack push" not in quiet
    assert "stack push" in everything_said
    assert len(everything_said) > len(quiet)


def test_an_empty_journal_still_reads(everything: ContentLibrary) -> None:
    journal = Journal(seed=1, players=("Ann", "Bo"))

    told = render(journal)

    assert "Unfinished after 0 commands" in told


def test_the_session_keeps_a_journal_of_the_browser_game(
    everything: ContentLibrary,
) -> None:
    from fsme.api import Session

    session = Session(everything, players=2, seed=5)

    journal: Any = session.journal

    # The deal is the first entry, not something that happened before anybody
    # was writing. A journal that began at the second move could not say where
    # an opening hand or three starting cents came from.
    assert len(journal) == 1
    assert journal.entries[0].command == "start_game"

    moves = legal_moves(session.game)

    assert session.submit(moves[0])["accepted"]

    assert len(journal) == 2
    assert journal.entries[-1].label == moves[0]["label"]


def test_an_event_says_which_player_it_is_about(
    everything: ContentLibrary,
) -> None:
    """
    The disambiguator the step log needs, checked where it comes from.

    A journal entry is filed under whoever *submitted* the command, and that is
    routinely not the player the events are about. A priority window closes
    only when everybody has passed, so the last pass — somebody else's — is the
    command that lets an attack resolve. At a table of two it is always the
    other player, which made every roll of Bo's attack appear under Ann and
    read as though the attacker had changed hands halfway through.

    A previous audit established that the attacker never changes: 1577 combat
    blows across forty games, every one of them landing on the player who
    declared the attack. What was missing was any way to *see* that in the
    record. This asserts the record has it — ``controller`` on the attack's
    events names the declaring player — because a page can only show what the
    journal carries.
    """
    from fsme.api import Session
    from fsme.lab.bot import HeuristicBot
    from fsme.lab.simulation import ScriptedAgent
    from fsme.lab.simulation.runner import _whose_move

    session = Session(everything, players=2, seed=23)
    game = session.game

    bot = HeuristicBot(23)
    agent = ScriptedAgent(23)

    for _ in range(600):
        if game.is_over:
            break

        if game.runtime.awaiting_decision is not None:
            answered = agent.choose(game)

            if answered is None:
                break

            command, label = answered
        else:
            thought = bot.choose(game, seats=(_whose_move(game),))

            if thought is None:
                break

            command, label = thought[0], thought[1]

        if not session.submit(
            {
                "type": str(command.type),
                "player": command.player,
                "payload": dict(command.payload),
                "label": label,
            }
        )["accepted"]:
            break

    declared: int | None = None
    elsewhere = 0

    for entry in session.journal.entries:
        if (entry.label or "").startswith("Attack "):
            declared = entry.player

        for happening in entry.events:
            if happening.type != "attack_start":
                continue

            assert happening.controller is not None, (
                "an attack began and the event does not say whose"
            )
            assert happening.controller == declared, (
                f"attack_start says seat {happening.controller} and the "
                f"declaration was made by seat {declared}"
            )

            if entry.player != happening.controller:
                elsewhere += 1

    assert elsewhere, (
        "this game never resolved an attack on somebody else's command, so it "
        "does not test what it is here to test"
    )
