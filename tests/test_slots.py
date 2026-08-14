"""
The monster area as a row of slots.

COMPREHENSIVE_RULES.md §2 lays the area out as slots, each with its own pile,
and calls the face-up card of a slot its active monster. Two slots holding one
monster each look exactly like two monsters, so this is about the three places
where the difference shows: a monster standing on top of another (§7), the one
underneath coming back when it dies, and a slot that stays a slot when it is
empty (§9).
"""

from __future__ import annotations

from conftest import make_game, make_instance, monster_definition

from fsme.commands import Command, CommandType
from fsme.rules.slots import cover, empty_slot, place, slot_of
from fsme.state import GamePhase


def drain(runtime, state, limit=12) -> None:
    """
    Let every open window close, so the queue is empty again.
    """
    for _ in range(limit):
        if not runtime.awaiting_priority:
            return

        runtime.submit(
            Command(type=CommandType.PASS_PRIORITY, player=state.priority.holder or 0)
        )


def monster(name: str, **printed) -> object:
    return make_instance(
        monster_definition(f"test.{name}", **printed),
        controller=None,
        owner=None,
        instance_id=f"monster:{name}",
    )


def test_an_empty_slot_is_still_a_slot() -> None:
    runtime, state = make_game(monsters=0)

    state.monster_slots = 2

    place(state, monster("first"))

    assert len(state.monster_area) == 2
    assert empty_slot(state) == 1
    assert len(state.active_monsters) == 1, "an empty slot shows no monster"


def test_a_monster_can_stand_on_top_of_another() -> None:
    runtime, state = make_game(monsters=0)

    under = monster("under")
    over = monster("over")

    place(state, under)
    cover(state, over, slot=0)

    assert slot_of(state, under) == 0
    assert slot_of(state, over) == 0
    assert list(state.active_monsters.cards) == [over], "only the top one is face up"


def test_killing_the_top_monster_brings_back_the_one_beneath() -> None:
    runtime, state = make_game(monsters=0)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    under = monster("under")
    over = monster("over")

    place(state, under)
    cover(state, over, slot=0)

    runtime.context.apply("kill", [over])
    runtime.run()

    assert over in state.monster_discard.cards
    assert list(state.active_monsters.cards) == [under], "the slot did not empty"
    assert slot_of(state, under) == 0


def test_a_monster_revealed_by_attacking_the_deck_covers_a_slot() -> None:
    """
    COMPREHENSIVE_RULES.md §7: it goes into a slot on top of the active monster.
    """
    # A full board, so the revealed monster is not simply pulled up to fill a
    # gap before anybody attacks anything.
    runtime, state = make_game(monsters=2, interactive_priority=True)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))
    drain(runtime, state)
    runtime.submit(Command(type=CommandType.END_PHASE, player=0))
    drain(runtime, state)

    assert state.turn.phase is GamePhase.ACTION

    standing = state.active_monsters.cards[0]
    revealed = monster("revealed", health=6)

    state.monster_deck.add_top(revealed)

    assert runtime.submit(
        Command(type=CommandType.ATTACK, player=0, payload={"source": "deck"})
    ).accepted

    # Answer the declaration; the attack begins and stops at the first round.
    drain(runtime, state, limit=len(state.players))

    assert slot_of(state, revealed) == slot_of(state, standing)
    assert state.combat.monster is revealed
    assert standing not in state.active_monsters.cards, "it is covered, not gone"


def test_a_covered_monster_survives_a_save() -> None:
    """
    Which monster is standing on which is part of the position.
    """
    from fsme.serialization import load_game, save_game

    runtime, state = make_game(monsters=0)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    under = monster("under")
    over = monster("over")

    place(state, under)
    cover(state, over, slot=0)

    for card in (under, over, *state.loot_deck.cards, *state.treasure_shop.cards):
        runtime.cards.register(card.definition)

    for player in state.players:
        for card in player.hand.cards:
            runtime.cards.register(card.definition)

    back = load_game(save_game(state), runtime.cards)

    assert len(back.monster_area) == len(state.monster_area)
    assert [card.instance_id for card in back.monster_area[0].cards] == [
        "monster:under",
        "monster:over",
    ]
    assert [card.instance_id for card in back.active_monsters.cards] == ["monster:over"]
