"""
The engine as something outside it can talk to.

Two claims are worth testing about a client-facing layer, and they are the two
that keep a user interface honest. Everything it shows is a copy, so nothing a
client holds can change the game. And every move it offers is a move the engine
would accept — the list is produced by asking, not by reasoning.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fsme.api import Session, legal_moves, load_content, snapshot
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture
def session(everything: ContentLibrary) -> Session:
    return Session(everything, players=3, seed=5)


def test_a_view_is_json_and_nothing_else(session: Session) -> None:
    """
    A client gets data, never the engine's own objects.
    """
    view = session.view()

    # json.dumps refuses anything that is not plain data, which is the test.
    assert json.loads(json.dumps(view)) == view


def test_the_view_holds_what_a_table_needs(session: Session) -> None:
    state = snapshot(session.game)

    assert state["started"] is True
    assert len(state["players"]) == 3
    assert state["board"]["monster_slots"], "the monster area is laid out"
    assert state["board"]["decks"]["loot"] > 0
    assert state["waiting"]["kind"] in ("action", "priority", "decision")


def test_every_offered_move_is_one_the_engine_accepts(session: Session) -> None:
    """
    The list is not advice. Each entry is a command the engine has approved.
    """
    for move in legal_moves(session.game):
        command = Command(
            type=Session._command_type(move["type"]),
            player=move["player"],
            payload=dict(move["payload"]),
        )

        assert session.game.runtime.refuse_reason(command) is None, move["label"]


def test_no_move_is_offered_while_a_question_is_open(session: Session) -> None:
    """
    A game waiting on an answer has exactly one thing to do, and it is not a move.
    """
    for _ in range(200):
        if session.game.runtime.awaiting_decision is not None:
            assert legal_moves(session.game) == []

            return

        moves = legal_moves(session.game)

        if not moves:
            break

        session.submit(moves[0])

    pytest.skip("this deal never stopped to ask anything")


def test_a_refused_command_says_why(session: Session) -> None:
    outcome = session.submit(
        {"type": "attack", "player": 0, "payload": {"index": 99}}
    )

    assert outcome["accepted"] is False
    assert outcome["reason"]


def test_an_unknown_command_is_refused_rather_than_guessed(session: Session) -> None:
    with pytest.raises(ValueError):
        session.submit({"type": "eat_the_table", "player": 0, "payload": {}})


def test_the_log_only_ever_grows_forwards(session: Session) -> None:
    first = session.view(0)

    seen = first["history_length"]

    assert [event["index"] for event in first["events"]] == list(range(seen))

    moves = legal_moves(session.game)

    if moves:
        session.submit(moves[0])

    later = session.view(seen)

    assert all(event["index"] >= seen for event in later["events"])


def test_a_session_can_be_dealt_again(session: Session) -> None:
    before = snapshot(session.game)

    session.restart(seed=99)

    after = snapshot(session.game)

    assert after["seed"] == 99
    assert before["seed"] != after["seed"]


def test_a_session_refuses_a_table_nobody_could_sit_at(
    everything: ContentLibrary,
) -> None:
    with pytest.raises(ValueError):
        Session(everything, players=1)

    with pytest.raises(ValueError):
        Session(everything, players=9)


def test_a_whole_game_can_be_played_through_the_client_surface(
    everything: ContentLibrary,
) -> None:
    """
    The point of the layer: a client that only knows these three calls can
    play a game from the deal to a winner.
    """
    import random

    session = Session(everything, players=2, seed=4, interactive_priority=False)
    rng = random.Random(4)

    for _ in range(4000):
        game = session.game

        if game.is_over:
            assert snapshot(game)["winner"] is not None

            return

        decision = game.runtime.awaiting_decision

        if decision is not None:
            count = len(decision.options)
            lowest = max(0, min(decision.minimum, count))
            highest = max(lowest, min(decision.maximum, count))

            session.submit(
                {
                    "type": str(CommandType.CHOOSE_TARGET),
                    "player": decision.player,
                    "payload": {
                        "choices": rng.sample(
                            range(count), rng.randint(lowest, highest)
                        )
                        if count
                        else []
                    },
                }
            )

            continue

        moves = legal_moves(game)

        assert moves, "a game with nothing to do and no question to answer"

        assert session.submit(rng.choice(moves))["accepted"]

    pytest.fail("the game did not finish within the budget")
