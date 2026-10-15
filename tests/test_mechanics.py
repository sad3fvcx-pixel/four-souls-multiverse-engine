"""
Dice modification, copying, deck searching, bonus souls and conditional
statics.
"""

from __future__ import annotations

import pytest
from conftest import make_definition, make_game, make_instance

from fsme.cards import Ability, CardInstance, CardType, Static
from fsme.commands import Command, CommandType
from fsme.effects import EffectExecutionError
from fsme.events import EventType
from fsme.rules import ATTACK, STARTING_COINS
from fsme.rules.statics import bonus
from fsme.state import DecisionKind


def started(**kwargs):
    runtime, state = make_game(**kwargs)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    return runtime, state


def equip(state, player_id, definition, instance_id="instance:1"):
    card = make_instance(
        definition, controller=player_id, owner=player_id, instance_id=instance_id
    )
    state.player(player_id).treasures.add_top(card)

    return card


def activate(runtime, player=0, index=0):
    return runtime.submit(
        Command(
            type=CommandType.ACTIVATE_TREASURE, player=player, payload={"index": index}
        )
    )


# ----------------------------------------------------------------------
# Dice modification
# ----------------------------------------------------------------------


def lucky_charm(card_id="test.charm", amount=1):
    return make_definition(
        card_id,
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="roll_modified",
                effects=({"modify_roll": amount},),
                replacement=True,
                scope="any",
            ),
        ),
    )


def roller(card_id="test.roller"):
    return make_definition(
        card_id,
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="on_activate",
                effects=(
                    {"roll_dice": 6},
                    {
                        "if": [{"dice_equals": 6}],
                        "then": [{"gain_coins": 10}],
                        "else": [{"gain_coins": 1}],
                    },
                ),
            ),
        ),
    )


def test_a_roll_can_be_modified_before_it_counts() -> None:
    from test_combat import FixedRNG

    runtime, state = make_game(rng=FixedRNG([5]))
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    equip(state, 0, roller(), "instance:roller")
    equip(state, 0, lucky_charm(amount=1), "instance:charm")

    activate(runtime)

    assert state.player(0).pennies == STARTING_COINS + 10

    rolls = [
        event
        for event in runtime.history
        if event.type is EventType.AFTER_ROLL
    ]

    assert rolls[-1].get("value") == 6


def test_a_modified_roll_stays_on_the_die() -> None:
    """
    A six-sided die cannot show a seven, however much is added to it.
    """
    from test_combat import FixedRNG

    runtime, state = make_game(rng=FixedRNG([6]))
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    equip(state, 0, roller(), "instance:roller")
    equip(state, 0, lucky_charm(amount=5), "instance:charm")

    activate(runtime)

    rolls = [
        event
        for event in runtime.history
        if event.type is EventType.AFTER_ROLL
    ]

    assert rolls[-1].get("value") == 6


def test_attack_rolls_go_through_the_same_window() -> None:
    from test_combat import FixedRNG

    runtime, state = make_game(rng=FixedRNG([3]))
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    equip(state, 0, lucky_charm(amount=1), "instance:charm")

    runtime.submit(Command(type=CommandType.END_PHASE, player=0))

    monster = state.active_monsters.cards[0]
    runtime.submit(Command(type=CommandType.ATTACK, player=0, payload={"index": 0}))

    # A monster needing 4 is hit by a natural 3 lifted to 4.
    assert monster.hp == 1


def test_modify_roll_does_nothing_outside_a_roll() -> None:
    """
    A card that shifts a roll shifts nothing when no roll is happening.

    It is played at the wrong moment rather than written wrongly, and a game
    is not stopped because somebody wasted a card.
    """
    runtime, state = started()

    assert runtime.context.apply("modify_roll", [], amount=1) == 0


# ----------------------------------------------------------------------
# Copying
# ----------------------------------------------------------------------


def test_an_ability_can_be_used_from_another_card() -> None:
    runtime, state = started()

    borrowed = equip(
        state,
        1,
        make_definition(
            "test.generous",
            card_type=CardType.TREASURE,
            abilities=(Ability(trigger="on_activate", effects=({"gain_coins": 4},)),),
        ),
        "instance:borrowed",
    )

    runtime.context._set_actor(0)
    runtime.context.apply("copy_ability", [borrowed])
    runtime.run()

    assert state.player(0).pennies == STARTING_COINS + 4
    assert state.player(1).pennies == STARTING_COINS


def test_the_top_of_the_stack_can_be_copied() -> None:
    runtime, state = started()

    equip(
        state,
        0,
        make_definition(
            "test.echo",
            card_type=CardType.TREASURE,
            abilities=(Ability(trigger="on_activate", effects=({"gain_coins": 2},)),),
        ),
        "instance:echo",
    )

    runtime.submit(
        Command(
            type=CommandType.ACTIVATE_TREASURE, player=0, payload={"index": 0}
        )
    )

    assert state.player(0).pennies == STARTING_COINS + 2


def test_copying_the_stack_needs_something_on_it() -> None:
    runtime, state = started()

    assert runtime.context.apply("copy_effect", []) == 0


def test_a_card_can_be_duplicated_into_play() -> None:
    runtime, state = started()

    original = equip(state, 1, make_definition("test.gem"), "instance:gem")

    runtime.context._set_actor(0)

    assert runtime.context.apply("duplicate", [original]) == 1

    copy = state.player(0).treasures.cards[-1]

    assert copy is not original
    assert copy.definition is original.definition
    assert copy.instance_id != original.instance_id
    assert copy.owner == 0


# ----------------------------------------------------------------------
# Decks
# ----------------------------------------------------------------------


def test_a_deck_can_be_shuffled_deterministically() -> None:
    first, state_a = started(loot_cards=20)
    second, state_b = started(loot_cards=20)

    first.context.apply("shuffle_deck", [], deck="loot")
    second.context.apply("shuffle_deck", [], deck="loot")

    assert [card.id for card in state_a.loot_deck.cards] == [
        card.id for card in state_b.loot_deck.cards
    ]


def test_revealing_shows_cards_without_moving_them() -> None:
    runtime, state = started(loot_cards=10)

    before = list(state.loot_deck.cards)

    revealed = runtime.context.apply("reveal_cards", [], deck="loot", count=3)
    runtime.run()

    assert len(revealed) == 3
    assert state.loot_deck.cards == before
    assert EventType.REVEALED in [event.type for event in runtime.history]


def test_an_unknown_deck_is_refused() -> None:
    runtime, state = started()

    with pytest.raises(EffectExecutionError):
        runtime.context.apply("shuffle_deck", [], deck="nowhere")


def test_searching_a_deck_asks_and_then_takes() -> None:
    runtime, state = started(loot_cards=10)

    equip(
        state,
        0,
        make_definition(
            "test.divining_rod",
            card_type=CardType.TREASURE,
            abilities=(
                Ability(
                    trigger="on_activate",
                    targets=({"target_deck_card": {"deck": "loot", "as": "found"}},),
                    effects=(
                        {
                            "effect": "take_card",
                            "to": "hand",
                            "shuffle": "loot",
                            "target": "found",
                        },
                    ),
                ),
            ),
        ),
        "instance:rod",
    )

    hand_before = state.player(0).hand_size
    deck_before = len(state.loot_deck)

    activate(runtime)

    decision = runtime.awaiting_decision

    assert decision is not None
    assert decision.kind is DecisionKind.CHOOSE_CARD
    assert len(decision.options) == deck_before

    wanted = decision.options[2]

    runtime.submit(
        Command(
            type=CommandType.CHOOSE_TARGET, player=0, payload={"choices": [2]}
        )
    )

    assert wanted in state.player(0).hand.cards
    assert state.player(0).hand_size == hand_before + 1
    assert len(state.loot_deck) == deck_before - 1


# ----------------------------------------------------------------------
# Bonus souls
# ----------------------------------------------------------------------


def test_a_bonus_soul_card_becomes_the_soul() -> None:
    runtime, state = started()

    soul_card = CardInstance(
        definition=make_definition(
            "test.bonus_soul",
            card_type=CardType.BONUS_SOUL,
            abilities=(),
        ),
        instance_id="soul:bonus",
    )
    state.room_area.add_top(soul_card)

    runtime.context._set_source(soul_card)
    runtime.context.apply("claim_soul", [state.player(1)])
    runtime.run()

    assert soul_card in state.player(1).souls.cards
    assert soul_card not in state.room_area.cards
    assert state.player(1).soul_count == 1


def test_claiming_without_a_card_is_refused() -> None:
    runtime, state = started()

    with pytest.raises(EffectExecutionError):
        runtime.context.apply("claim_soul", [state.player(0)])


# ----------------------------------------------------------------------
# Conditional statics
# ----------------------------------------------------------------------


def test_a_static_can_depend_on_the_state_of_the_game() -> None:
    """
    Conditions are asked every time a value is read, so the modifier turns
    itself on and off without anything having to notice that it did.
    """
    runtime, state = started()

    equip(
        state,
        0,
        make_definition(
            "test.bloodlust",
            card_type=CardType.TREASURE,
            statics=(
                Static(
                    ATTACK,
                    1,
                    conditions=({"player_hp": {"operator": "<=", "value": 1}},),
                ),
            ),
        ),
        "instance:bloodlust",
    )

    assert bonus(state, ATTACK, 0) == 0

    state.player(0).hp = 1

    assert bonus(state, ATTACK, 0) == 1

    state.player(0).hp = 2

    assert bonus(state, ATTACK, 0) == 0


def test_an_unconditional_static_always_applies() -> None:
    runtime, state = started()

    equip(
        state,
        0,
        make_definition(
            "test.plain",
            card_type=CardType.TREASURE,
            statics=(Static(ATTACK, 1),),
        ),
        "instance:plain",
    )

    assert bonus(state, ATTACK, 0) == 1
