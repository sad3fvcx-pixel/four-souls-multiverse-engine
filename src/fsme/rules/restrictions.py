# src/fsme/rules/restrictions.py

"""
What cards in play forbid.

Most statics change a number. A few change what is legal: "other players can't
play loot cards on your turn", "this can't be attacked". They are read the same
way — every card in play has a say, every time the question is asked — but the
answer is yes or no rather than a total, so they live here rather than among the
sums.

A prohibition is checked while a command is being validated, which is where the
engine already decides what a player may do. Nothing is half-done as a result:
a forbidden action is refused before it changes anything.
"""

from __future__ import annotations

from typing import Any

from fsme.cards import CardInstance
from fsme.state import GameState

from .statics import cards_in_play, static_conditions_hold

PLAY_LOOT = "play_loot"
"""Playing a loot card."""

ACTIVATE = "activate"
"""Activating an item or a character."""

ATTACK = "attack"
"""Declaring an attack on a monster."""

PURCHASE = "purchase"
"""Buying from the shop."""

ACTIONS = (PLAY_LOOT, ACTIVATE, ATTACK, PURCHASE)


def forbidden_by(
    state: GameState,
    action: str,
    *,
    player: int | None = None,
    card: Any | None = None,
) -> CardInstance | None:
    """
    Return the card forbidding an action, or None if nothing does.

    ``player`` is who wants to act; ``card`` is what they want to act on, which
    is what "this can't be attacked" is about. A card that forbids something
    about itself says so with the scope ``self``.
    """
    for source in cards_in_play(state):
        for static in source.face.statics:
            if static.forbids != action:
                continue

            if not static_conditions_hold(static, source, state):
                continue

            if _catches(static.scope, source, player, card):
                return source

    return None


def _catches(
    scope: str,
    source: CardInstance,
    player: int | None,
    card: Any | None,
) -> bool:
    """
    Decide whether a prohibition reaches the player or card in question.
    """
    if scope == "self":
        return card is source

    controller = source.controller

    if scope == "controller":
        return player is not None and player == controller

    if scope == "opponents":
        return player is not None and controller is not None and player != controller

    return True


def refuse(
    state: GameState,
    action: str,
    *,
    player: int | None = None,
    card: Any | None = None,
) -> str | None:
    """
    Return the reason an action is refused, in words a client can show.
    """
    source = forbidden_by(state, action, player=player, card=card)

    if source is None:
        return None

    return f"'{source.name}' does not allow that"
