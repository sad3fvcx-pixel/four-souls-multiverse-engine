"""
Shared fixtures for the engine test suite.
"""

from __future__ import annotations

from typing import Any

import pytest

from fsme.cards import Ability, CardDefinition, CardInstance, CardType
from fsme.rng.rng import RNG
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


@pytest.fixture
def state() -> GameState:
    return make_state()


@pytest.fixture
def runtime(state: GameState) -> Runtime:
    return make_runtime(state)
