"""
Built-in effects change the game and announce every change.
"""

from __future__ import annotations

import pytest
from conftest import make_definition, make_instance, make_runtime, make_state

from fsme.cards import CardType
from fsme.effects import EffectExecutionError, EffectRegistrationError, builtin_registry
from fsme.events import EventType


def context_for(state=None):
    runtime = make_runtime(state)

    return runtime, runtime.context


def queued_types(state) -> list[EventType]:
    return [event.type for event in state.events]


def test_gain_and_lose_coins() -> None:
    runtime, ctx = context_for()
    player = ctx.state.player(0)

    ctx_registry = runtime.effects

    ctx_registry.execute("gain_coins", ctx, [player], amount=5)
    assert player.pennies == 5

    ctx_registry.execute("lose_coins", ctx, [player], amount=2)
    assert player.pennies == 3

    # A gain is offered for replacement before it happens, so it announces
    # itself twice: once as a proposal, once as a fact.
    assert queued_types(ctx.state) == [
        EventType.BEFORE_COINS_GAINED,
        EventType.COINS_GAINED,
        EventType.COINS_LOST,
    ]


def test_losing_more_coins_than_owned_stops_at_zero() -> None:
    runtime, ctx = context_for()
    player = ctx.state.player(0)
    player.pennies = 2

    lost = runtime.effects.execute("lose_coins", ctx, [player], amount=10)

    assert lost == 2
    assert player.pennies == 0


def test_damage_never_kills_directly() -> None:
    """
    An effect lowers hit points; only State-Based Actions declare death.
    """
    runtime, ctx = context_for()
    player = ctx.state.player(0)

    runtime.effects.execute("deal_damage", ctx, [player], amount=5)

    assert player.hp == 0
    assert player.alive is True


def test_heal_respects_maximum() -> None:
    runtime, ctx = context_for()
    player = ctx.state.player(0)
    player.hp = 1

    healed = runtime.effects.execute("heal", ctx, [player], amount=10)

    assert healed == 1
    assert player.hp == player.max_hp


def test_draw_loot_moves_cards_and_reshuffles() -> None:
    state = make_state()
    state.loot_discard.add_top("card-a")
    state.loot_discard.add_top("card-b")

    runtime, ctx = context_for(state)
    player = state.player(0)

    drawn = runtime.effects.execute("draw_loot", ctx, [player], count=2)

    assert drawn == 2
    assert player.hand_size == 2
    assert len(state.loot_discard) == 0


def test_draw_loot_stops_when_no_cards_remain() -> None:
    runtime, ctx = context_for()
    player = ctx.state.player(0)

    drawn = runtime.effects.execute("draw_loot", ctx, [player], count=3)

    assert drawn == 0
    assert player.hand_size == 0


def test_gain_soul_mints_tokens_with_deterministic_ids() -> None:
    runtime, ctx = context_for()
    player = ctx.state.player(0)

    runtime.effects.execute("gain_soul", ctx, [player], count=2)

    tokens = [soul.token_id for soul in player.souls.cards]

    assert player.soul_count == 2
    assert len(set(tokens)) == 2
    assert all(token.startswith("soul:") for token in tokens)


def test_recharge_and_deactivate_items() -> None:
    runtime, ctx = context_for()
    card = make_instance(make_definition(card_type=CardType.TREASURE))

    runtime.effects.execute("deactivate", ctx, [card])
    assert card.tapped is True

    runtime.effects.execute("recharge", ctx, [card])
    assert card.tapped is False


def test_effect_rejects_wrong_target_type() -> None:
    runtime, ctx = context_for()
    card = make_instance(make_definition())

    with pytest.raises(EffectExecutionError):
        runtime.effects.execute("gain_coins", ctx, [card], amount=1)


def test_registry_refuses_to_redefine_an_effect() -> None:
    """
    Definitions are immutable once registered.
    """
    registry = builtin_registry()

    with pytest.raises(EffectRegistrationError):
        registry.register("gain_coins", lambda ctx, targets, **kwargs: None)


def test_builtin_registry_covers_the_documented_vocabulary() -> None:
    names = builtin_registry().names()

    for expected in (
        "gain_coins",
        "lose_coins",
        "deal_damage",
        "heal",
        "kill",
        "draw_loot",
        "discard_loot",
        "gain_soul",
        "roll_dice",
    ):
        assert expected in names


def test_giving_an_item_to_nobody_does_nothing(runtime, state) -> None:
    """
    "Give an item to another player" in a game whose other players are all
    dead names nobody, and the rules pass over what cannot be carried out.
    """
    from conftest import make_instance, treasure_definition

    item = make_instance(
        treasure_definition("test.gift"), controller=0, owner=0, instance_id="gift"
    )
    state.player(0).treasures.add_top(item)

    assert runtime.context.apply("give_treasure", [item], to=None) == 0
    assert item in state.player(0).treasures.cards
