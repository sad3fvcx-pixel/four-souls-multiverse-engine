"""
The bot, and the record of what it was thinking.

A bot in an analytical engine is not judged by whether it wins. It is judged by
whether its reasoning can be read, because the point of writing the reasoning
down is to be able to find the mistakes in it. So most of what is tested here
is that the log says what the bot actually did — the numbers it chose from, not
a plausible account of them — and that it claims nothing it cannot know.

It does also happen to win, and that is measured rather than asserted from the
armchair.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import make_game, make_instance, monster_definition

from fsme.api import load_content
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary
from fsme.journal import Journal, JournalKeeper, render
from fsme.lab.bot import Decision, HeuristicBot
from fsme.lab.simulation import play_one
from fsme.rules.slots import place
from fsme.state import GamePhase

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


def reach_action_phase(runtime, state) -> None:
    runtime.submit(Command(type=CommandType.START_GAME, player=0))
    runtime.submit(Command(type=CommandType.END_PHASE, player=0))

    assert state.turn.phase is GamePhase.ACTION


def monster(name: str, **printed) -> object:
    return make_instance(
        monster_definition(f"test.{name}", **printed),
        controller=None,
        owner=None,
        instance_id=f"monster:{name}",
    )


# ----------------------------------------------------------------------
# What it knows
# ----------------------------------------------------------------------


def test_the_chance_of_hitting_is_the_die_and_not_a_guess() -> None:
    """
    One six-sided die against a printed difficulty. There is a right answer.
    """
    from fsme.game import Game

    runtime, state = make_game(monsters=0)

    place(state, monster("easy", roll=2, health=1, souls=1, attack=1))

    reach_action_phase(runtime, state)

    bot = HeuristicBot(1)
    game = Game(state)

    chosen = bot.choose(game)

    assert chosen is not None

    _, _, decision = chosen

    attack = next(
        evaluation
        for evaluation in decision.considered
        if evaluation.move.startswith("Attack")
    )

    chance = next(
        reason for reason in attack.reasons if "die is enough" in reason.what
    )

    # A difficulty of 2 is hit on five faces of six. The journal rounds what it
    # writes down, so the reading is compared at the precision it is kept in.
    assert chance.value == pytest.approx(5 / 6, abs=0.001)


def test_it_will_not_attack_what_would_kill_it_on_a_miss() -> None:
    """
    The one judgement the bot is asked to make about a fight.
    """
    from fsme.game import Game

    runtime, state = make_game(monsters=0)

    place(state, monster("nasty", roll=6, health=6, souls=1, attack=2))

    reach_action_phase(runtime, state)

    state.player(0).hp = 1

    bot = HeuristicBot(1)
    chosen = bot.choose(Game(state))

    assert chosen is not None

    command, label, decision = chosen

    attack = next(
        evaluation
        for evaluation in decision.considered
        if evaluation.move.startswith("Attack")
    )

    assert attack.score < 0
    assert any("would kill you" in reason.what for reason in attack.reasons)
    assert not label.startswith("Attack"), "it found something better to do"


def test_it_takes_the_soul_that_is_one_hit_away() -> None:
    from fsme.game import Game

    runtime, state = make_game(monsters=0)

    place(state, monster("finished", roll=2, health=1, souls=1, attack=1))

    reach_action_phase(runtime, state)

    state.player(0).hp = 2

    chosen = HeuristicBot(1).choose(Game(state))

    assert chosen is not None

    _, label, decision = chosen

    assert label.startswith("Attack")
    assert any("would finish it" in reason.what for reason in decision.chosen.reasons)


def test_it_says_when_it_has_no_opinion(everything: ContentLibrary) -> None:
    """
    A bot that invented a preference here would be lying in its own log.
    """
    journal, _ = play_one(everything, seed=3, players=2, thinking_seats=(0,))

    answers = [
        entry
        for entry in journal.entries
        if entry.decision and entry.decision.get("notes")
    ]

    assert answers
    assert any(
        "no opinion" in note
        for entry in answers
        for note in entry.decision["notes"]
    )


def test_it_never_claims_a_chance_of_winning(everything: ContentLibrary) -> None:
    """
    A bot reasoning one move ahead cannot know that, and a number named that
    way would be believed.
    """
    journal, _ = play_one(everything, seed=5, players=2, thinking_seats=(0,))

    written = json.dumps(journal.to_dict()).lower()

    assert "win chance" not in written
    assert "winchance" not in written
    assert "win_probability" not in written


# ----------------------------------------------------------------------
# What the journal keeps of it
# ----------------------------------------------------------------------


def test_the_journal_keeps_the_working_the_bot_actually_used(
    everything: ContentLibrary,
) -> None:
    """
    The property the whole decision log rests on: what is written down is the
    arithmetic the choice was made from, not a retelling of it.
    """
    from fsme.game import Game

    game = Game.from_content(everything, ["Ann", "Bo"], seed=8)
    game.start()

    keeper = JournalKeeper(game)
    bot = HeuristicBot(8)

    for _ in range(30):
        if game.is_over:
            break

        thought = bot.choose(game)

        assert thought is not None

        command, label, decision = thought

        keeper.submit(command, label=label, decision=decision.to_dict())

        entry = keeper.journal.entries[-1]

        assert entry.decision is not None
        assert entry.decision["chosen"]["move"] == decision.chosen.move
        assert entry.decision["chosen"]["score"] == decision.chosen.score
        assert entry.label == label

        # And what it was chosen over, not only what was chosen.
        assert len(entry.decision["considered"]) == len(decision.considered)


def test_the_working_survives_a_round_trip(
    everything: ContentLibrary, tmp_path: Path
) -> None:
    journal, _ = play_one(everything, seed=4, players=2, thinking_seats=(0,))

    back = Journal.load(journal.save(tmp_path / "thought.json"))

    assert back.to_dict() == journal.to_dict()

    thought = [entry for entry in back.entries if entry.decision]

    assert thought
    assert Decision.from_dict(thought[0].decision).by == "heuristic-1"


def test_a_journal_reads_the_reasoning_out(everything: ContentLibrary) -> None:
    journal, _ = play_one(everything, seed=4, players=2, thinking_seats=(0,))

    told = render(journal)

    assert "heuristic-1 scored it" in told
    assert "over:" in told, "and what it was chosen over"


def test_a_game_nobody_thought_about_keeps_no_working(
    everything: ContentLibrary,
) -> None:
    journal, _ = play_one(everything, seed=4, players=2)

    assert all(entry.decision is None for entry in journal.entries)


# ----------------------------------------------------------------------
# Whether it is any good
# ----------------------------------------------------------------------


def test_the_bot_beats_players_who_do_not_think() -> None:
    """
    Measured rather than assumed, at a table where the only difference between
    the seats is who is thinking.

    Sixteen games is few, and the margin asked for is wide enough to survive
    that: a player choosing at random wins about a quarter of four-handed
    games, and this asks for a third.
    """
    from fsme.lab.simulation import run_on_many_cores

    games = 16
    wins = 0

    for done in run_on_many_cores(
        CONTENT_ROOT, games, 4, jobs=4, thinking_seats=(0,)
    ):
        if done.winner == 0:
            wins += 1

    assert wins > games / 3, f"the bot won {wins} of {games}"
