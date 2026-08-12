"""
What defeating a monster pays out.
"""

from __future__ import annotations

from conftest import make_definition, make_game, make_instance, treasure_definition

from fsme.cards import CardInstance, CardType
from fsme.commands import Command, CommandType
from fsme.events import EventType


def rich_monster(card_id="test.rich", *, souls=1, **rewards):
    return make_definition(
        card_id,
        name="Rich Monster",
        card_type=CardType.MONSTER,
        health=1,
        attack=1,
        roll=4,
        souls=souls,
        rewards=rewards,
    )


def board(monster_definition, **kwargs):
    runtime, state = make_game(monsters=0, **kwargs)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    monster = CardInstance(
        definition=monster_definition,
        instance_id="monster:rich",
        controller=None,
        owner=None,
    )
    state.active_monsters.add_top(monster)

    return runtime, state, monster


def kill_with_an_item(runtime, state, effects):
    card = make_instance(
        treasure_definition("test.slayer", effects=effects),
        controller=0,
        owner=0,
        instance_id="instance:slayer",
    )
    state.player(0).treasures.add_top(card)

    return runtime.submit(
        Command(
            type=CommandType.ACTIVATE_TREASURE, player=0, payload={"index": 0}
        )
    )


def test_a_monster_killed_by_an_effect_pays_the_player_who_did_it() -> None:
    """
    Before, only combat knew who the killer was, so an item that finished a
    monster off earned nothing.
    """
    runtime, state, monster = board(rich_monster(souls=2))

    kill_with_an_item(
        runtime,
        state,
        ({"effect": "kill", "target": "current_monster"},),
    )

    assert monster.alive is False
    assert state.player(0).soul_count == 2
    assert EventType.MONSTER_KILLED in [event.type for event in runtime.history]


def test_printed_cent_and_loot_rewards_are_paid() -> None:
    runtime, state, monster = board(rich_monster(cents=7, loot=2))

    before = state.player(0).hand_size

    kill_with_an_item(
        runtime,
        state,
        ({"effect": "kill", "target": "current_monster"},),
    )

    assert state.player(0).pennies == 7
    assert state.player(0).hand_size == before + 2


def test_a_treasure_reward_comes_off_the_treasure_deck() -> None:
    runtime, state, monster = board(rich_monster(treasure=1))

    state.treasure_deck.add_top(
        CardInstance(
            definition=treasure_definition("test.prize"),
            instance_id="treasure:prize",
            controller=None,
            owner=None,
        )
    )

    kill_with_an_item(
        runtime,
        state,
        ({"effect": "kill", "target": "current_monster"},),
    )

    assert state.player(0).treasure_count == 2
    assert state.player(0).treasures.cards[-1].id == "test.prize"


def test_unknown_reward_keys_are_ignored() -> None:
    """
    Forward compatibility: a future reward type must not break old engines.
    """
    runtime, state, monster = board(rich_monster(cents=1, glitter=99))

    kill_with_an_item(
        runtime,
        state,
        ({"effect": "kill", "target": "current_monster"},),
    )

    assert state.player(0).pennies == 1


def test_a_monster_nobody_damaged_pays_nobody() -> None:
    runtime, state, monster = board(rich_monster(cents=5))

    monster.hp = 0
    runtime.run()

    assert monster.alive is False
    assert state.player(0).pennies == 0


def test_the_last_player_to_damage_a_monster_is_remembered() -> None:
    runtime, state, monster = board(rich_monster(souls=1), players=3)

    card = make_instance(
        treasure_definition(
            "test.poke",
            effects=({"effect": "deal_damage", "amount": 1, "target": "current_monster"},),
        ),
        controller=2,
        owner=2,
        instance_id="instance:poke",
    )
    state.player(2).treasures.add_top(card)

    runtime.submit(
        Command(
            type=CommandType.ACTIVATE_TREASURE, player=2, payload={"index": 0}
        )
    )

    assert monster.last_damaged_by == 2
    assert state.player(2).soul_count == 1
