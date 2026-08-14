"""
Shared fixtures for the engine test suite.
"""

from __future__ import annotations

from typing import Any

import pytest

from fsme.cards import Ability, CardDefinition, CardInstance, CardType
from fsme.rng.rng import RNG
from fsme.rules.slots import place
from fsme.runtime import Runtime
from fsme.state import GameState, PlayerState


def make_definition(
    card_id: str = "test.card",
    *,
    name: str = "Test Card",
    card_type: CardType = CardType.TREASURE,
    abilities: tuple[Ability, ...] = (),
    health: int | None = None,
    **extra: Any,
) -> CardDefinition:
    """
    Build a card definition without going through a content file.
    """
    return CardDefinition(
        id=card_id,
        name=name,
        type=card_type,
        expansion="test",
        abilities=abilities,
        health=health,
        **extra,
    )


def make_instance(
    definition: CardDefinition,
    *,
    controller: int | None = 0,
    owner: int | None = 0,
    instance_id: str = "instance:1",
) -> CardInstance:
    """
    Put a definition into play.
    """
    return CardInstance(
        definition=definition,
        instance_id=instance_id,
        controller=controller,
        owner=owner,
    )


def make_state(players: int = 2, *, seed: int = 1) -> GameState:
    """
    Build a game state with the requested number of players.
    """
    state = GameState(seed=seed)

    for index in range(players):
        state.add_player(PlayerState(player_id=index, name=f"player{index}"))

    return state


def make_runtime(state: GameState | None = None, **kwargs: Any) -> Runtime:
    """
    Build a Runtime over a game state.
    """
    game_state = state if state is not None else make_state()

    return Runtime(game_state, rng=RNG(game_state.seed), **kwargs)


# ----------------------------------------------------------------------
# Content helpers
# ----------------------------------------------------------------------


def treasure_definition(
    card_id: str = "test.treasure",
    *,
    effects: tuple[Any, ...] = ({"gain_coins": 1},),
    trigger: str = "on_activate",
    conditions: tuple[Any, ...] = (),
) -> CardDefinition:
    """
    A treasure with one activated ability.
    """
    return make_definition(
        card_id,
        name="Test Treasure",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(trigger=trigger, conditions=conditions, effects=effects),
        ),
    )


def loot_definition(
    card_id: str = "test.loot",
    *,
    effects: tuple[Any, ...] = ({"gain_coins": 1},),
) -> CardDefinition:
    """
    A loot card that does something when played.
    """
    return make_definition(
        card_id,
        name="Test Loot",
        card_type=CardType.LOOT,
        abilities=(Ability(trigger="on_play", effects=effects),),
    )


def monster_definition(
    card_id: str = "test.monster",
    *,
    health: int = 2,
    attack: int = 1,
    roll: int = 4,
    souls: int = 1,
) -> CardDefinition:
    """
    A monster with the four printed combat values.
    """
    return make_definition(
        card_id,
        name="Test Monster",
        card_type=CardType.MONSTER,
        health=health,
        attack=attack,
        roll=roll,
        souls=souls,
    )


def make_game(
    *,
    players: int = 2,
    seed: int = 1,
    loot_cards: int = 12,
    monsters: int = 1,
    shop_items: int = 2,
    interactive_priority: bool = False,
    rng: RNG | None = None,
) -> tuple[Runtime, GameState]:
    """
    Build a playable game with decks, a shop and monsters on the board.

    The game is not started: a test decides when to submit ``start_game`` so
    that it can watch the opening happen.
    """
    state = make_state(players, seed=seed)

    for index in range(loot_cards):
        state.loot_deck.add_top(
            CardInstance(
                definition=loot_definition(f"test.loot{index}"),
                instance_id=f"loot:{index}",
            )
        )

    for index in range(monsters):
        place(
            state,
            CardInstance(
                definition=monster_definition(f"test.monster{index}"),
                instance_id=f"monster:{index}",
                controller=None,
                owner=None,
            ),
        )

    for index in range(shop_items):
        state.treasure_shop.add_top(
            CardInstance(
                definition=treasure_definition(f"test.shop{index}"),
                instance_id=f"shop:{index}",
                controller=None,
                owner=None,
            )
        )

    runtime = Runtime(
        state,
        rng=rng if rng is not None else RNG(state.seed),
        interactive_priority=interactive_priority,
    )

    return runtime, state


@pytest.fixture
def state() -> GameState:
    return make_state()


@pytest.fixture
def runtime(state: GameState) -> Runtime:
    return make_runtime(state)
