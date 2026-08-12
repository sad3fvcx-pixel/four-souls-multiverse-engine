"""
The Runtime loop: event, trigger, stack, resolution, State-Based Actions.

The first test in this file is the stage 1 exit criterion.
"""

from __future__ import annotations

from conftest import make_definition, make_instance, make_runtime, make_state

from fsme.cards import Ability, CardType
from fsme.events import Event, EventType


def treasure(effects, *, trigger: str = "on_activate", conditions=(), card_id="test.item"):
    return make_definition(
        card_id,
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger=trigger,
                conditions=tuple(conditions),
                effects=tuple(effects),
            ),
        ),
    )


def monster(card_id="test.monster", *, health=2, abilities=()):
    return make_definition(
        card_id,
        card_type=CardType.MONSTER,
        health=health,
        abilities=abilities,
    )


def test_event_reaches_an_ability_through_the_stack() -> None:
    """
    Stage 1 exit criterion: emit -> listener -> stack -> resolve.
    """
    state = make_state()
    card = make_instance(treasure([{"gain_coins": 3}]))
    state.player(0).treasures.add_top(card)

    runtime = make_runtime(state)

    observed: list[Event] = []
    runtime.subscribe(EventType.ON_ACTIVATE, observed.append)

    runtime.dispatch(EventType.ON_ACTIVATE, source=card, controller=0)

    assert [event.type for event in observed] == [EventType.ON_ACTIVATE]
    assert state.player(0).pennies == 3
    assert state.stack.is_empty()
    assert runtime.is_stable()

    sequence = [event.type for event in runtime.history]

    assert sequence.index(EventType.STACK_PUSH) < sequence.index(EventType.COINS_GAINED)
    assert EventType.STACK_RESOLVE in sequence


def test_ability_does_not_resolve_when_its_condition_fails() -> None:
    state = make_state()
    card = make_instance(
        treasure([{"gain_coins": 3}], conditions=[{"player_has_coins": 5}])
    )
    state.player(0).treasures.add_top(card)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.ON_ACTIVATE, source=card, controller=0)

    assert state.player(0).pennies == 0
    assert EventType.STACK_PUSH not in [event.type for event in runtime.history]


def test_activation_fires_only_the_activated_card() -> None:
    """
    Activating one item must not trigger every other item in play.
    """
    state = make_state()

    first = make_instance(treasure([{"gain_coins": 1}], card_id="test.first"))
    second = make_instance(
        treasure([{"gain_coins": 10}], card_id="test.second"),
        instance_id="instance:2",
    )

    state.player(0).treasures.add_top(first)
    state.player(0).treasures.add_top(second)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.ON_ACTIVATE, source=first, controller=0)

    assert state.player(0).pennies == 1


def test_global_trigger_fires_for_every_holder() -> None:
    state = make_state()

    for index, player in enumerate(state.players):
        card = make_instance(
            treasure([{"gain_coins": 1}], trigger="turn_start", card_id="test.aura"),
            controller=index,
            owner=index,
            instance_id=f"instance:{index}",
        )
        player.treasures.add_top(card)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.TURN_START)

    assert [player.pennies for player in state.players] == [1, 1]


def test_effects_reach_other_players_through_targets() -> None:
    state = make_state(players=3)
    card = make_instance(
        treasure([{"for_each": "opponents", "effects": [{"deal_damage": 1}]}])
    )
    state.player(0).treasures.add_top(card)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.ON_ACTIVATE, source=card, controller=0)

    assert state.player(0).hp == 2
    assert state.player(1).hp == 1
    assert state.player(2).hp == 1


def test_state_based_actions_declare_death_after_resolution() -> None:
    state = make_state()
    card = make_instance(
        treasure([{"effect": "deal_damage", "amount": 5, "target": "opponents"}])
    )
    state.player(0).treasures.add_top(card)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.ON_ACTIVATE, source=card, controller=0)

    victim = state.player(1)

    assert victim.hp == 0
    assert victim.alive is False
    assert EventType.PLAYER_DIED in [event.type for event in runtime.history]


def test_dead_monster_leaves_play() -> None:
    state = make_state()

    gaper = make_instance(monster(), controller=None, owner=None)
    state.active_monsters.add_top(gaper)

    card = make_instance(
        treasure([{"effect": "deal_damage", "amount": 2, "target": "current_monster"}])
    )
    state.player(0).treasures.add_top(card)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.ON_ACTIVATE, source=card, controller=0)

    assert gaper.alive is False
    assert gaper not in state.active_monsters.cards
    assert gaper in state.monster_discard.cards
    assert EventType.MONSTER_KILLED in [event.type for event in runtime.history]


def test_victory_is_declared_once_the_soul_threshold_is_reached() -> None:
    state = make_state()
    state.souls_to_win = 2

    card = make_instance(treasure([{"gain_soul": 2}]))
    state.player(0).treasures.add_top(card)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.ON_ACTIVATE, source=card, controller=0)

    assert state.game_over is True
    assert state.winner == 0

    types = [event.type for event in runtime.history]

    assert EventType.WINNER_DECLARED in types
    assert EventType.GAME_END in types


def test_a_triggered_ability_can_cause_another_trigger() -> None:
    """
    Resolution generates events, and those events trigger further abilities.
    """
    state = make_state()

    striker = make_instance(
        treasure(
            [{"effect": "deal_damage", "amount": 1, "target": "opponents"}],
            card_id="test.striker",
        )
    )
    reactor = make_instance(
        treasure([{"gain_coins": 5}], trigger="damage_dealt", card_id="test.reactor"),
        instance_id="instance:2",
    )

    state.player(0).treasures.add_top(striker)
    state.player(0).treasures.add_top(reactor)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.ON_ACTIVATE, source=striker, controller=0)

    assert state.player(1).hp == 1
    assert state.player(0).pennies == 5
    assert runtime.is_stable()


def test_execution_context_exposes_only_the_intended_powers() -> None:
    """
    Effects reach the game through this object and nothing else, so its surface
    is the definition of what an effect is allowed to do.
    """
    state = make_state()
    runtime = make_runtime(state)
    context = runtime.context

    assert context.state is state

    public = {name for name in dir(context) if not name.startswith("_")}

    assert public == {"state", "rng", "emit", "push", "roll"}
