"""
Where a card is.

A card is in exactly one place. That sounds like nothing until you notice the
board is kept twice: `monster_area` is a row of slots, each a pile with a
face-up card on top, and `active_monsters` is a zone holding those face-up
cards so that everything else in the engine has one list to read.
`rules.slots` is the only code allowed to write both, and it exists because two
records of one thing drift apart the moment anything else touches either.

An effect that moved a card by searching the zones found `active_monsters`,
took the monster out of it, and left the slot untouched — so the card went into
a deck *and* stayed on the table, and the next sync put it back into the view
as well. This is that, from several directions.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from conftest import make_game, monster_definition
from test_official_cards import activate, choose, give, new_game

from fsme.cards import CardInstance
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.lab.bot import HeuristicBot
from fsme.lab.simulation import ScriptedAgent
from fsme.lab.simulation.runner import NAMES, _whose_move
from fsme.rules.slots import cover, place, sync
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def base_game() -> ContentLibrary:
    library = ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)

    only = ContentLibrary()
    only.add(library.get("base_game"))

    return only


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    from fsme.api import load_content

    return load_content(CONTENT_ROOT)


def a_monster(name: str) -> CardInstance:
    return CardInstance(
        definition=monster_definition(f"test.{name}"),
        instance_id=f"monster:{name}",
        controller=None,
        owner=None,
    )


def in_the_slots(state: Any) -> list[str]:
    """
    Every monster in the row, buried ones included.
    """
    return [
        card.instance_id for slot in state.monster_area for card in slot.cards
    ]


def times_in_the_deck(state: Any, card: CardInstance) -> int:
    return [held.instance_id for held in state.monster_deck.cards].count(
        card.instance_id
    )


# ----------------------------------------------------------------------
# One card, one place
# ----------------------------------------------------------------------


def test_a_standing_monster_moved_to_a_deck_leaves_its_slot() -> None:
    runtime, state = make_game(monsters=0, monster_deck=3, monster_slots=1)

    # Into the only slot before the game opens, so the deal does not put a
    # monster of its own there first.
    standing = a_monster("standing")
    place(state, standing)

    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    runtime.context.apply("move_cards", [standing], deck="monster", position="bottom")
    runtime.run()

    assert standing.instance_id not in in_the_slots(state), "it left the row"
    assert standing not in state.active_monsters.cards
    assert times_in_the_deck(state, standing) == 1, "and it is in the deck once"

    # The view is rebuilt from the row, so a card removed from the view alone
    # comes back the next time anything syncs. This is that check.
    sync(state)

    assert standing not in state.active_monsters.cards


def test_a_buried_monster_moved_to_a_deck_leaves_its_slot() -> None:
    """
    A covered monster is in no zone at all — only in the pile of its slot — so
    a search of the zones never found it and the move added a second copy.
    """
    runtime, state = make_game(monsters=0, monster_deck=3, monster_slots=1)

    under = a_monster("under")
    over = a_monster("over")

    place(state, under)
    cover(state, over, slot=0)

    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    assert in_the_slots(state) == ["monster:under", "monster:over"]

    runtime.context.apply("move_cards", [under], deck="monster", position="bottom")
    runtime.run()

    assert in_the_slots(state) == ["monster:over"]
    assert times_in_the_deck(state, under) == 1


def test_taking_the_top_monster_uncovers_the_one_beneath() -> None:
    """
    Leaving through the slots is what brings the covered monster back up.
    """
    runtime, state = make_game(monsters=0, monster_deck=3, monster_slots=1)

    under = a_monster("under")
    over = a_monster("over")

    place(state, under)
    cover(state, over, slot=0)

    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    # To the bottom, so that the slot it leaves is not refilled with it again.
    runtime.context.apply("move_cards", [over], deck="monster", position="bottom")
    runtime.run()

    assert in_the_slots(state) == ["monster:under"]
    assert list(state.active_monsters.cards) == [under]


def test_a_monster_taken_into_a_hand_is_not_still_on_the_table() -> None:
    """
    `take_card` searched the same zones and had the same hole.
    """
    runtime, state = make_game(monsters=0, monster_deck=3, monster_slots=1)

    standing = a_monster("standing")
    place(state, standing)

    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    taken = runtime.context.apply(
        "take_card", [standing], to="treasures", player=0
    )
    runtime.run()

    assert taken == 1
    assert standing in state.player(0).treasures.cards
    assert standing.instance_id not in in_the_slots(state)
    assert standing not in state.active_monsters.cards


# ----------------------------------------------------------------------
# The card that found it
# ----------------------------------------------------------------------

FLUSH = "treasure_deck-active_items-base_game-flush"
SWEEP_THE_MONSTERS = 0


def test_flush_puts_the_monsters_it_swept_into_the_deck_and_nowhere_else(
    base_game: ContentLibrary,
) -> None:
    """
    "Put each monster not being attacked on the bottom of the monster deck."

    The card is not the defect and its rules are unchanged: it asks for a move,
    and the move is what used to leave the monsters standing where they were.
    """
    game = new_game(base_game)
    state = game.state

    standing = list(state.active_monsters.cards)

    assert standing, "there are monsters to sweep"

    before = len(state.monster_deck)

    flush = give(game, FLUSH)

    assert activate(game, flush).accepted
    assert choose(game, 0, SWEEP_THE_MONSTERS).accepted

    for monster in standing:
        assert monster.instance_id not in in_the_slots(state), monster.instance_id
        assert monster not in state.active_monsters.cards
        assert times_in_the_deck(state, monster) == 1

    # Sweeping empties the slots, and an empty slot refills: the deck gives up
    # as many as it took back, less the ones now standing again.
    assert len(state.monster_deck) == before + len(standing) - len(
        state.active_monsters.cards
    )


# ----------------------------------------------------------------------
# Whole games
# ----------------------------------------------------------------------


def census(state: Any) -> Counter:
    """
    Every card in the game, by instance, wherever it is.

    `active_monsters` is deliberately not counted: it is the face-up view of
    the row, not a place a card can be. Counting it would report every standing
    monster twice and make this test agree with anything.
    """
    seen: Counter = Counter()

    zones: list[Any] = []

    for name in ("loot", "treasure", "monster", "room"):
        zones.append(getattr(state, f"{name}_deck", None))
        zones.append(getattr(state, f"{name}_discard", None))

    zones += [state.treasure_shop, state.room_area]
    zones += list(state.monster_area)

    for player in state.players:
        zones += [player.hand, player.treasures, player.curses, player.souls]

    for zone in zones:
        if zone is None:
            continue

        for card in zone.cards:
            ident = getattr(card, "instance_id", None) or getattr(
                card, "token_id", "?"
            )
            seen[ident] += 1

    return seen


@pytest.mark.parametrize("seed", (28, 51, 96, 137))
def test_no_card_is_ever_in_two_places_during_a_whole_game(
    everything: ContentLibrary, seed: int
) -> None:
    """
    Checked after every command of a whole four-player game, not at the end.

    Seed 28 is where this was first caught: `Flush!` at command 498, three
    monsters in the deck and still in their slots. Measured over two hundred
    games, five of them reached this state and every one was the same card.
    """
    from fsme.game import Game
    from fsme.journal import JournalKeeper

    game = Game.from_content(everything, list(NAMES[:4]), seed=seed)
    game.start()

    state = game.state
    keeper = JournalKeeper(game)
    agent = ScriptedAgent(seed)
    bot = HeuristicBot(seed)

    doubled = [name for name, count in census(state).items() if count > 1]

    assert not doubled, f"at the deal: {doubled}"

    for _ in range(20000):
        if game.is_over:
            break

        speaking = _whose_move(game)
        thought = (bot if speaking in range(4) else agent).choose(
            game, seats=(speaking,)
        )

        if thought is None:
            break

        if not keeper.submit(thought[0], label=thought[1]).accepted:
            break

        doubled = [name for name, count in census(state).items() if count > 1]

        assert not doubled, (
            f"seed {seed}, command {keeper.journal.entries[-1].index} "
            f"({keeper.journal.entries[-1].label}): {doubled}"
        )

    assert game.is_over, "the game finished"
