"""
Whole games, played end to end by a scripted table.

The card tests ask whether one card does what it says. This asks something the
card tests cannot: whether a game made of all of them holds together. A table
of scripted players takes every legal action it can think of, and the engine is
watched for the three ways it could fail them — an exception out of a command,
a position it will not accept any move from, and a state that contradicts
itself.

The players are not clever. They are only thorough, and they are the same
players every run: the script draws from its own generator, seeded per game, so
a failure here can be reproduced by its seed alone.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from fsme.commands import Command, CommandResult, CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.game import Game
from fsme.replay import state_digest
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.state import GamePhase

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

SEEDS = (0, 1, 2, 7, 23)
TABLES = (2, 3, 4)

STEPS = 250
"""
How far each game is played.

Long enough to leave the opening behind and reach the parts of the game that
only happen once cards have accumulated; short enough that the suite stays
quick. Nothing here asserts that a game ends within it.
"""


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    """
    Every official card the engine knows, played together.
    """
    return ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)


def act(game: Game, kind: CommandType, player: int, **payload: Any) -> CommandResult:
    return game.submit(Command(type=kind, player=player, payload=payload))


def answer(game: Game, rng: random.Random) -> bool:
    """
    Answer whatever the game is waiting on, within what it asked for.
    """
    decision = game.runtime.awaiting_decision

    if decision is None:
        return False

    count = len(decision.options)
    lowest = max(0, min(decision.minimum, count))
    highest = max(lowest, min(decision.maximum, count))

    picks = rng.sample(range(count), rng.randint(lowest, highest)) if count else []

    result = act(game, CommandType.CHOOSE_TARGET, decision.player, choices=picks)

    assert result.accepted, (
        f"the engine asked {decision.kind} of player {decision.player} with "
        f"{count} options and then refused the answer: {result.reason}"
    )

    return True


def step(game: Game, rng: random.Random) -> bool:
    """
    Take one action, and say whether anything could be done at all.
    """
    if answer(game, rng):
        return True

    state = game.state

    if game.runtime.awaiting_priority:
        passed = act(game, CommandType.PASS_PRIORITY, state.priority.holder or 0)

        return bool(passed.accepted)

    seat = state.turn.active_player
    player = state.player(seat)

    moves: list[tuple[CommandType, dict[str, Any]]] = []

    for index, card in enumerate(player.treasures.cards):
        if not getattr(card, "tapped", False):
            moves.append(
                (CommandType.ACTIVATE_TREASURE, {"index": index, "ability": 0})
            )

    for index in range(player.hand_size):
        moves.append((CommandType.PLAY_LOOT, {"index": index}))

    if state.turn.phase is GamePhase.ACTION:
        for index in range(len(state.active_monsters)):
            moves.append((CommandType.ATTACK, {"index": index}))

        for index in range(len(state.treasure_shop)):
            moves.append((CommandType.BUY_TREASURE, {"index": index}))

        # The two moves that do not name a card: attacking the monster deck and
        # buying the top of the treasure deck, both unseen.
        moves.append((CommandType.ATTACK, {"source": "deck"}))
        moves.append((CommandType.BUY_TREASURE, {"source": "deck"}))

    rng.shuffle(moves)

    for kind, payload in moves:
        if act(game, kind, seat, **payload).accepted:
            return True

    if state.turn.phase is GamePhase.END:
        return bool(act(game, CommandType.END_TURN, seat).accepted)

    return bool(
        act(game, CommandType.END_PHASE, seat).accepted
        or act(game, CommandType.END_TURN, seat).accepted
    )


def check(game: Game) -> None:
    """
    Assert the things that must be true of any position, at any time.
    """
    state = game.state

    # A death is a state-based action, and those are taken when the engine
    # settles. While an ability is parked on a question there is a moment in
    # which a player stands at no hit points and has not died yet — the rules
    # say the same thing: the death goes into the queue, and the queue waits
    # its turn. So the hit points are checked always and the death only once
    # the engine has come to rest.
    settled = game.runtime.awaiting_decision is None

    for player in state.players:
        assert 0 <= player.hp <= player.max_hp, (
            f"player {player.player_id} has {player.hp} of {player.max_hp} hit points"
        )

        if settled:
            assert player.alive == (player.hp > 0), (
                f"player {player.player_id} is {'alive' if player.alive else 'dead'} "
                f"at {player.hp} hit points"
            )

    where: dict[int, str] = {}

    zones = [
        ("loot deck", state.loot_deck),
        ("loot discard", state.loot_discard),
        ("treasure deck", state.treasure_deck),
        ("treasure discard", state.treasure_discard),
        ("shop", state.treasure_shop),
        ("monsters", state.active_monsters),
        ("monster deck", state.monster_deck),
        ("monster discard", state.monster_discard),
        ("bonus souls", state.bonus_souls),
    ]

    for player in state.players:
        zones.extend(
            [
                (f"hand {player.player_id}", player.hand),
                (f"items {player.player_id}", player.treasures),
                (f"souls {player.player_id}", player.souls),
                (f"curses {player.player_id}", player.curses),
            ]
        )

    for name, zone in zones:
        for card in zone.cards:
            previous = where.get(id(card))

            assert previous is None, (
                f"{getattr(card, 'name', card)} is in two places at once: "
                f"{previous} and {name}"
            )

            where[id(card)] = name


def play(library: ContentLibrary, seed: int, players: int, steps: int = STEPS) -> Game:
    """
    Play one game as far as the budget allows, checking as it goes.
    """
    game = Game.from_content(
        library, ["Ann", "Bo", "Cy", "Di"][:players], seed=seed
    )

    assert game.start().accepted

    rng = random.Random(seed)

    for taken in range(steps):
        check(game)

        if game.is_over:
            break

        assert step(game, rng), (
            f"seed {seed}, {players} players: nothing could be done after "
            f"{taken} steps — turn {game.state.turn.turn_number}, "
            f"phase {game.state.turn.phase}, "
            f"stack {len(game.state.stack)}"
        )

    return game


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("players", TABLES)
def test_a_scripted_table_can_always_do_something(
    everything: ContentLibrary, seed: int, players: int
) -> None:
    """
    No position refuses every move, and none contradicts itself.
    """
    play(everything, seed, players)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_same_seed_plays_the_same_game(
    everything: ContentLibrary, seed: int
) -> None:
    """
    The same seed and the same script make the same game, exactly.

    Two runs are compared by their positions rather than by their commands: a
    digest that matches after every step is a stronger claim than a command
    log that matches, and it is the claim the engine actually makes.
    """
    first = play(everything, seed, 3, steps=120)
    second = play(everything, seed, 3, steps=120)

    assert state_digest(first.state) == state_digest(second.state)
    assert [str(event.type) for event in first.history] == [
        str(event.type) for event in second.history
    ]
