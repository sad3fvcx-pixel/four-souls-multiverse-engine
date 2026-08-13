"""
Static modifiers.

A static is not an event: nothing triggers it, it never reaches the stack, and
it stops mattering the moment its card leaves play.
"""

from __future__ import annotations

from conftest import make_definition, make_game, make_instance

from fsme.cards import CardType, Static
from fsme.commands import Command, CommandType
from fsme.rules import ATTACK, LOOT_PLAYS, MAX_HP, STATS, static_value
from fsme.rules.statics import bonus
from fsme.state.modifiers import MONSTER_STATS


def gear(card_id: str, *statics: Static):
    return make_definition(
        card_id,
        card_type=CardType.TREASURE,
        abilities=(),
        statics=statics,
    )


def equip(state, player_id: int, definition, instance_id: str):
    card = make_instance(
        definition, controller=player_id, owner=player_id, instance_id=instance_id
    )
    state.player(player_id).treasures.add_top(card)

    return card


def started_game(**kwargs):
    runtime, state = make_game(**kwargs)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    return runtime, state


def test_a_static_raises_a_value_while_its_card_is_in_play() -> None:
    runtime, state = started_game()

    assert static_value(state, ATTACK, 0, 1) == 1

    card = equip(state, 0, gear("test.whetstone", Static(ATTACK, 1)), "instance:w")

    assert static_value(state, ATTACK, 0, 1) == 2

    state.player(0).treasures.cards.remove(card)

    assert static_value(state, ATTACK, 0, 1) == 1


def test_statics_add_up() -> None:
    runtime, state = started_game()

    equip(state, 0, gear("test.a", Static(ATTACK, 1)), "instance:a")
    equip(state, 0, gear("test.b", Static(ATTACK, 2)), "instance:b")

    assert bonus(state, ATTACK, 0) == 3


def test_a_static_reaches_only_who_it_says() -> None:
    runtime, state = started_game(players=3)

    equip(state, 0, gear("test.mine", Static(ATTACK, 1, scope="controller")), "i:1")
    equip(state, 1, gear("test.theirs", Static(ATTACK, 5, scope="opponents")), "i:2")
    equip(state, 2, gear("test.everyone", Static(ATTACK, 2, scope="all_players")), "i:3")

    assert bonus(state, ATTACK, 0) == 1 + 5 + 2
    assert bonus(state, ATTACK, 1) == 2
    assert bonus(state, ATTACK, 2) == 5 + 2


def test_a_value_never_falls_below_zero() -> None:
    runtime, state = started_game()

    equip(state, 0, gear("test.curse", Static(ATTACK, -5)), "instance:c")

    assert static_value(state, ATTACK, 0, 1) == 0


def test_an_attack_static_changes_combat_damage() -> None:
    from test_combat import FixedRNG

    runtime, state = make_game(rng=FixedRNG([6]))
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    equip(state, 0, gear("test.whetstone", Static(ATTACK, 1)), "instance:w")

    runtime.submit(Command(type=CommandType.END_PHASE, player=0))

    monster = state.active_monsters.cards[0]

    runtime.submit(
        Command(type=CommandType.ATTACK, player=0, payload={"index": 0})
    )

    # Two hit points, two damage in the first round.
    assert monster.alive is False


def test_a_max_hp_static_is_applied_and_withdrawn() -> None:
    """
    Hit point maxima are stored, so State-Based Actions keep them honest.
    """
    runtime, state = started_game()

    player = state.player(0)
    player.character = make_instance(
        make_definition("test.hero", card_type=CardType.CHARACTER, health=2),
        controller=0,
        owner=0,
        instance_id="instance:hero",
    )

    card = equip(state, 0, gear("test.meal", Static(MAX_HP, 1)), "instance:m")

    runtime.run()

    assert player.max_hp == 3

    player.hp = 3
    player.treasures.cards.remove(card)

    runtime.run()

    assert player.max_hp == 2
    assert player.hp == 2


def test_a_loot_play_static_grants_another_play() -> None:
    runtime, state = started_game()

    equip(state, 1, gear("test.pockets", Static(LOOT_PLAYS, 1)), "instance:p")

    runtime.submit(Command(type=CommandType.END_PHASE, player=0))
    runtime.submit(Command(type=CommandType.END_TURN, player=0))

    assert state.turn.active_player == 1

    assert runtime.submit(
        Command(type=CommandType.PLAY_LOOT, player=1, payload={"index": 0})
    ).accepted
    assert runtime.submit(
        Command(type=CommandType.PLAY_LOOT, player=1, payload={"index": 0})
    ).accepted

    third = runtime.submit(
        Command(type=CommandType.PLAY_LOOT, player=1, payload={"index": 0})
    )

    assert third.rejected


def test_a_character_card_contributes_its_statics() -> None:
    runtime, state = started_game()

    state.player(0).character = make_instance(
        make_definition(
            "test.brawler",
            card_type=CardType.CHARACTER,
            health=2,
            statics=(Static(ATTACK, 1),),
        ),
        controller=0,
        owner=0,
        instance_id="instance:brawler",
    )

    assert bonus(state, ATTACK, 0) == 1


def test_statics_are_not_triggers() -> None:
    """
    A static never reaches the stack: there is no moment at which it happens.
    """
    runtime, state = started_game()

    equip(state, 0, gear("test.whetstone", Static(ATTACK, 1)), "instance:w")

    before = len(runtime.history)

    runtime.run()

    assert state.stack.is_empty()
    assert len(runtime.history) == before


def test_the_demo_set_ships_static_cards() -> None:
    from pathlib import Path

    from fsme.content import ContentLoader
    from fsme.runtime.vocabulary import engine_vocabulary

    root = Path(__file__).resolve().parents[1] / "content"
    library = ContentLoader(engine_vocabulary()).load_root(root)

    with_statics = [
        definition
        for definition in library.definitions()
        if definition.statics
    ]

    assert with_statics
    assert {
        static.stat for definition in with_statics for static in definition.statics
    } <= set(STATS) | set(MONSTER_STATS)
